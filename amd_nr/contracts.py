"""Image and runtime contracts, independent of ComfyUI and GPU libraries."""
from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral
import numpy as np

from .errors import ContractError, ResourceError

MIB = 1024 ** 2
GIB = 1024 ** 3

@dataclass(frozen=True)
class Limits:
    max_frames: int = 64
    max_edge: int = 8192
    max_working_bytes: int = 1024 * MIB
    min_free_disk_bytes: int = GIB

    def __post_init__(self) -> None:
        for name in ("max_frames", "max_edge", "max_working_bytes"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ContractError(f"{name} must be a positive integer.")
        if type(self.min_free_disk_bytes) is not int or self.min_free_disk_bytes < 0:
            raise ContractError("min_free_disk_bytes must be a nonnegative integer.")

@dataclass(frozen=True)
class FrameSpec:
    frames: int
    height: int
    width: int
    channels: int

    @property
    def raw_bytes(self) -> int:
        return self.frames * self.height * self.width * 4

    @property
    def estimated_working_bytes(self) -> int:
        # Conservative allowance for caller input, float copies, output, masks,
        # alpha and packed transfer buffers. Not a system-wide memory guarantee.
        return self.frames * self.height * self.width * 128

    def as_dict(self) -> dict:
        return {"frames": self.frames, "height": self.height,
                "width": self.width, "channels": self.channels,
                "layout": "BHWC", "color_contract": "SDR sRGB-like RGB [0,1]",
                "transfer_format": "RGBA8", "alpha": "straight, preserved"}


def spec_for_shape(shape: tuple, limits: Limits = Limits()) -> FrameSpec:
    if len(shape) != 4 or any(isinstance(v, bool) or not isinstance(v, Integral) or v < 1 for v in shape):
        raise ContractError("Expected a nonempty IMAGE batch [B,H,W,C].")
    b, h, w, c = map(int, shape)
    if c not in (3, 4):
        raise ContractError("IMAGE must have RGB (3) or straight RGBA (4) channels; not BCHW.")
    spec = FrameSpec(b, h, w, c)
    if b > limits.max_frames:
        raise ResourceError(f"Batch has {b} frames; limit is {limits.max_frames}. Use the video CLI or smaller batches.")
    if max(h, w) > limits.max_edge:
        raise ResourceError(f"Image edge exceeds {limits.max_edge} pixels.")
    if spec.estimated_working_bytes > limits.max_working_bytes:
        raise ResourceError("Conservative working-memory budget exceeded. Split the batch; no silent downscale is performed.")
    return spec


def validate_images(images: np.ndarray, limits: Limits = Limits()) -> FrameSpec:
    if not isinstance(images, np.ndarray):
        raise ContractError("Expected a NumPy floating-point BHWC array.")
    spec = spec_for_shape(images.shape, limits)
    if images.dtype.kind != "f":
        raise ContractError("Expected float IMAGE in [0,1], not integer pixels.")
    # Per-frame checks avoid a batch-sized temporary Boolean array.
    for index, image in enumerate(images):
        if not np.isfinite(image).all():
            raise ContractError(f"Frame {index} contains NaN or infinity.")
        if float(image.min()) < 0 or float(image.max()) > 1:
            raise ContractError(f"Frame {index} is outside [0,1]. HDR/linear grading must be explicit.")
    return spec


def rgba8(images: np.ndarray) -> np.ndarray:
    """Round-to-nearest (NumPy ties-to-even), not truncate; no color transform."""
    rgb = np.rint(images[..., :3].astype(np.float32) * 255.0).astype(np.uint8)
    result = np.empty((*images.shape[:3], 4), dtype=np.uint8)
    result[..., :3] = rgb
    # Transparent RGB has no defined compositing background. The neural runtime
    # always sees opaque color; original float alpha never crosses this bridge.
    result[..., 3] = 255
    return result


def validate_mix(mix: float) -> float:
    if isinstance(mix, bool) or not isinstance(mix, (float, int)) or not math.isfinite(mix) or not 0 <= mix <= 1:
        raise ContractError("mix must be finite and in [0,1]. It is output compositing, not model strength.")
    return float(mix)


def validate_mask(mask: np.ndarray | None, spec: FrameSpec) -> np.ndarray | None:
    if mask is None:
        return None
    if not isinstance(mask, np.ndarray) or mask.dtype.kind != "f":
        raise ContractError("Effect mask must be a floating-point array.")
    if mask.ndim == 2:
        mask = mask[None, ...]
    if mask.ndim != 3 or mask.shape[0] not in (1, spec.frames) or mask.shape[1:] != (spec.height, spec.width):
        raise ContractError("Effect mask must be [H,W], [1,H,W], or [B,H,W] at the exact image size.")
    if not np.isfinite(mask).all() or float(mask.min()) < 0 or float(mask.max()) > 1:
        raise ContractError("Effect mask values must be finite and in [0,1].")
    return mask.astype(np.float32, copy=False)[..., None]


def compose(images: np.ndarray, processed: np.ndarray, mix: float,
            mask: np.ndarray | None = None) -> np.ndarray:
    """Blend against the original float input, preserving excluded pixels exactly."""
    mix = validate_mix(mix)
    if processed.shape != (*images.shape[:3], 4) or processed.dtype != np.uint8:
        raise ContractError("Backend returned the wrong RGBA8 shape or dtype.")
    original = images.astype(np.float32, copy=False)
    result = original.copy()
    if mix == 0:
        return result
    weight = mix if mask is None else mix * mask
    color = processed[..., :3].astype(np.float32) / 255.0
    result[..., :3] = np.clip(original[..., :3] + weight * (color - original[..., :3]), 0, 1)
    return result
