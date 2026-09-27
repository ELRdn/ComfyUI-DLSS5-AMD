"""Classic ComfyUI node API. All heavy imports and native work are lazy."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import uuid

import numpy as np

from .amf import AMFScaler, output_size
from .backends import NativeBackend, ReferenceBackend
from .config import ROOT, config_fingerprint, load_native_config
from .contracts import Limits, spec_for_shape, validate_images, validate_mix
from .diagnostics import diagnose
from .errors import ContractError
from .pipeline import run_images

@dataclass(frozen=True)
class NRSettings:
    mix: float = 1.0

    def __post_init__(self) -> None:
        validate_mix(self.mix)


def _cancel() -> None:
    try:
        import comfy.model_management as management
    except ImportError:
        return
    management.throw_exception_if_processing_interrupted()


def _array(image) -> np.ndarray:
    import torch
    if not isinstance(image, torch.Tensor) or not image.is_floating_point():
        raise ContractError("Expected a floating-point ComfyUI IMAGE tensor.")
    spec_for_shape(tuple(image.shape))  # Budget check before any CPU transfer.
    array = image.detach().to(device="cpu", dtype=torch.float32).contiguous().numpy()
    validate_images(array)
    return array


def _tensor(array: np.ndarray):
    import torch
    return torch.from_numpy(np.ascontiguousarray(array, dtype=np.float32))


def _json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)


class AMDNRSettings:
    CATEGORY = "AMD NR/Experimental"
    RETURN_TYPES = ("AMD_NR_SETTINGS",)
    RETURN_NAMES = ("settings",)
    FUNCTION = "create"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                                                "tooltip": "Output blend only. NOT upscaling, model strength or temporal control."})}}

    def create(self, mix=1.0):
        return (NRSettings(validate_mix(mix)),)


class AMDNRApply:
    CATEGORY = "AMD NR/Experimental"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "evidence_json")
    FUNCTION = "apply"
    DESCRIPTION = "Experimental Windows/AMD native NR. Requires trusted server config; never falls back. SDR only, no temporal history."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "settings": ("AMD_NR_SETTINGS",)},
                "optional": {"effect_mask": ("MASK", {"tooltip": "White applies the effect; black preserves the original. Not automatically inverted alpha."})}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return config_fingerprint()

    def apply(self, image, settings, effect_mask=None):
        if not isinstance(settings, NRSettings):
            raise ContractError("Connect AMD NR Settings; arbitrary backend configuration is not accepted.")
        array = _array(image)
        mask = None
        if effect_mask is not None:
            import torch
            if not isinstance(effect_mask, torch.Tensor) or not effect_mask.is_floating_point():
                raise ContractError("Expected a floating-point effect MASK tensor.")
            batch, height, width = array.shape[:3]
            if tuple(effect_mask.shape) not in ((height, width), (1, height, width), (batch, height, width)):
                raise ContractError("Effect mask shape must match the image before any CPU transfer.")
            mask = effect_mask.detach().to(device="cpu", dtype=torch.float32).numpy()
        config = load_native_config()
        result = run_images(array, NativeBackend(config), work_root=config.work_root,
                            mix=settings.mix, effect_mask=mask, cancel=_cancel)
        return (_tensor(result.images), _json(result.report))


class AMDNRRenderUpscale:
    CATEGORY = "AMD NR/Experimental"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("upscaled_image", "evidence_json")
    FUNCTION = "apply"
    DESCRIPTION = "One-node color NR followed by AMD AMF VideoSR1.1. RGB SDR only; separate scaling stage, no temporal data."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",),
                             "factor": ("INT", {"default": 2, "min": 2, "max": 8}),
                             "mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05})}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return config_fingerprint()

    def apply(self, image, factor=2, mix=1.0):
        array = _array(image)
        if array.shape[-1] != 3:
            raise ContractError("NR + AMF upscale accepts RGB only; composite alpha before this node.")
        output_size(array.shape[2], array.shape[1], factor, array.shape[0])
        mix = validate_mix(mix)
        config = load_native_config()
        scaler = AMFScaler(config, cancel=_cancel)
        native = run_images(array, NativeBackend(config), work_root=config.work_root,
                            mix=mix, cancel=_cancel)
        rgb8 = np.rint(native.images * 255).astype(np.uint8)
        scaled, amf_evidence = scaler.scale_rgb8(rgb8, factor, config.work_root)
        report = {"native": native.report, "upscale": amf_evidence,
                  "meaning": "NR ran at input dimensions; separate AMD AMF VideoSR1.1 produced output dimensions. No DLSS super-resolution claim."}
        return (_tensor(scaled.astype(np.float32) / 255.0), _json(report))


class AMDNRRoundtrip:
    CATEGORY = "AMD NR/Diagnostics"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "diagnostic_json_NOT_DLSS")
    FUNCTION = "roundtrip"
    DESCRIPTION = "CPU RGBA8 transport test only. It does not perform DLSS or improve images."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}}

    def roundtrip(self, image):
        result = run_images(_array(image), ReferenceBackend(),
                            work_root=Path(tempfile.gettempdir()) / "comfy-amd-nr-diagnostics", cancel=_cancel)
        return (_tensor(result.images), _json(result.report))


class AMDNRResize:
    CATEGORY = "AMD NR/Utilities (NOT DLSS)"
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "resize"
    DESCRIPTION = "Ordinary bicubic resize; not neural rendering, FSR, or learned super-resolution."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",), "factor": ([1, 2, 4], {"default": 2})}}

    def resize(self, image, factor=2):
        import torch.nn.functional as functional
        if type(factor) is not int or factor not in (1, 2, 4):
            raise ContractError("Resize factor must be 1, 2, or 4.")
        array = _array(image)
        b, h, w, c = array.shape
        spec_for_shape((b, h * factor, w * factor, c))
        result = functional.interpolate(_tensor(array).permute(0, 3, 1, 2),
                                        size=(h * factor, w * factor), mode="bicubic", align_corners=False)
        return (result.clamp(0, 1).permute(0, 2, 3, 1).contiguous(),)


class AMDNRCompare:
    CATEGORY = "AMD NR/Diagnostics"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("original_left_processed_right", "difference_metrics_NOT_quality")
    FUNCTION = "compare"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"original": ("IMAGE",), "processed": ("IMAGE",)}}

    def compare(self, original, processed):
        left, right = _array(original), _array(processed)
        if left.shape != right.shape:
            raise ContractError("Compare inputs must have exactly the same shape.")
        b, h, w, _ = left.shape
        spec_for_shape((b, h, w * 2, 3))
        delta = np.abs(left[..., :3].astype(np.float64) - right[..., :3])
        report = {"meaning": "Pixel differences, NOT improvement scores or inference proof.",
                  "mean_abs_rgb": float(delta.mean()), "max_abs_rgb": float(delta.max()),
                  "per_frame_mean_abs_rgb": [float(x.mean()) for x in delta]}
        return (_tensor(np.concatenate((left[..., :3], right[..., :3]), axis=2)), _json(report))


class AMDNRDiagnostics:
    CATEGORY = "AMD NR/Diagnostics"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("diagnostics_json",)
    OUTPUT_NODE = True
    FUNCTION = "inspect"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")  # Diagnostics explicitly re-check current local state.

    def inspect(self):
        text = _json(diagnose())
        return {"ui": {"text": [text]}, "result": (text,)}


class AMDNRVideoFile:
    CATEGORY = "AMD NR/Experimental"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("lossless_mkv_path", "evidence_json")
    OUTPUT_NODE = True
    FUNCTION = "process"
    DESCRIPTION = "Short SDR/CFR clips only. Disk-backed bounded RAM, lossless MKV output, copied audio. Not temporal NR."

    @classmethod
    def INPUT_TYPES(cls):
        try:
            import folder_paths
            root = Path(folder_paths.get_input_directory())
            names = sorted(p.name for p in root.iterdir() if p.is_file() and not p.is_symlink()
                           and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"})
        except (ImportError, OSError):
            names = []
        return {"required": {"video": (names or ["PUT_A_CLIP_IN_COMFY_INPUT"],),
                             "settings": ("AMD_NR_SETTINGS",),
                             "max_frames": ("INT", {"default": 300, "min": 1, "max": 10000}),
                             "chunk_frames": ("INT", {"default": 1, "min": 1, "max": 8})}}

    @classmethod
    def IS_CHANGED(cls, video, **kwargs):
        try:
            import folder_paths
            path = Path(folder_paths.get_input_directory()) / video
            stat = path.stat()
            return f"{config_fingerprint()}|{stat.st_size}|{stat.st_mtime_ns}|{stat.st_ctime_ns}"
        except (ImportError, OSError):
            return "missing|" + config_fingerprint()

    def process(self, video, settings, max_frames=300, chunk_frames=1):
        from .filesystem import read_json
        from .video import process_video
        if not isinstance(settings, NRSettings):
            raise ContractError("Connect AMD NR Settings.")
        source = _selected_input_video(video)
        config = load_native_config()
        import folder_paths
        destination = Path(folder_paths.get_output_directory()) / "amd_nr" / f"AMDNR_{uuid.uuid4().hex}.mkv"
        report_path = process_video(source, destination, NativeBackend(config), work_root=config.work_root,
                                    mix=settings.mix, max_frames=max_frames, chunk_frames=chunk_frames, cancel=_cancel)
        text = _json(read_json(report_path))
        return {"ui": {"text": [str(destination)]}, "result": (str(destination), text)}


def _selected_input_video(video: str) -> Path:
    import folder_paths
    root = Path(folder_paths.get_input_directory()).resolve()
    if not isinstance(video, str) or Path(video).name != video or "/" in video or "\\" in video:
        raise ContractError("Select one filename from the ComfyUI input folder.")
    source = (root / video).resolve()
    if source.parent != root:
        raise ContractError("Video source must remain in the ComfyUI input folder.")
    return source


class AMDNRVideoUpscaleFile(AMDNRVideoFile):
    CATEGORY = "AMD NR/Experimental"
    RETURN_NAMES = ("lossless_upscaled_mkv_path", "evidence_json")
    FUNCTION = "process_upscale"
    DESCRIPTION = "One-node short SDR/CFR video NR then AMD AMF VideoSR1.1; lossless MKV, copied audio. No temporal NR."

    @classmethod
    def INPUT_TYPES(cls):
        required = dict(super().INPUT_TYPES()["required"])
        required.pop("settings")
        required.update({"factor": ("INT", {"default": 2, "min": 2, "max": 8}),
                         "mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05})})
        return {"required": required}

    def process_upscale(self, video, factor=2, mix=1.0, max_frames=300, chunk_frames=1):
        import folder_paths
        from .filesystem import read_json
        from .video import process_video
        source = _selected_input_video(video)
        config = load_native_config()
        scaler = AMFScaler(config, cancel=_cancel)
        destination = Path(folder_paths.get_output_directory()) / "amd_nr" / f"AMDNR_AMF_{uuid.uuid4().hex}.mkv"
        report_path = process_video(source, destination, NativeBackend(config), work_root=config.work_root,
                                    mix=mix, max_frames=max_frames, chunk_frames=chunk_frames,
                                    upscaler=scaler, upscale_factor=factor, cancel=_cancel)
        text = _json(read_json(report_path))
        return {"ui": {"text": [str(destination)]}, "result": (str(destination), text)}


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in
    (AMDNRSettings, AMDNRApply, AMDNRRenderUpscale, AMDNRRoundtrip, AMDNRResize,
     AMDNRCompare, AMDNRDiagnostics, AMDNRVideoFile, AMDNRVideoUpscaleFile)}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AMDNRSettings": "AMD NR · Settings (experimental)",
    "AMDNRApply": "AMD NR · Native Render (experimental)",
    "AMDNRRenderUpscale": "AMD NR · Render + AMF VideoSR1.1 (image)",
    "AMDNRRoundtrip": "AMD NR · CPU Roundtrip — NOT DLSS",
    "AMDNRResize": "AMD NR · Bicubic Resize — NOT DLSS",
    "AMDNRCompare": "AMD NR · A/B Difference (not a quality score)",
    "AMDNRDiagnostics": "AMD NR · Environment Report",
    "AMDNRVideoFile": "AMD NR · Video File → Lossless MKV (experimental)",
    "AMDNRVideoUpscaleFile": "AMD NR · Video + AMF VideoSR1.1 → Lossless MKV",
}
