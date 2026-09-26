"""Local command-line entry point. It never installs drivers or downloads weights."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

from . import __version__
from .backends import NativeBackend, ReferenceBackend
from .config import RUNTIME_NAMES, load_native_config
from .diagnostics import diagnose
from .errors import BridgeError, ContractError
from .filesystem import publish_new_file, sha256_file, write_json
from .pipeline import run_images


def _backend(args):
    if args.backend == "reference":
        return ReferenceBackend(), args.work_root or Path(tempfile.gettempdir()) / "amd-nr-reference"
    config = load_native_config(args.config)
    return NativeBackend(config), args.work_root or config.work_root


def load_image(source: Path) -> np.ndarray:
    from PIL import Image, ImageOps
    with Image.open(source) as image:
        from .contracts import spec_for_shape
        spec_for_shape((1, image.height, image.width, 4))  # Before decoding/copying.
        image = ImageOps.exif_transpose(image)
        if image.mode not in {"RGB", "RGBA", "L", "LA", "P"}:
            raise ContractError("Convert HDR, CMYK or high-bit-depth input explicitly to SDR RGB(A) first.")
        if image.info.get("icc_profile"):
            raise ContractError("ICC-tagged input requires explicit conversion to sRGB before this validation CLI.")
        has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
        array = np.array(image.convert("RGBA" if has_alpha else "RGB"), dtype=np.float32) / 255.0
    return array[None, ...]


def image_command(args) -> None:
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    if args.output.suffix.lower() != ".png":
        raise ContractError("Use .png for the lossless image validation path.")
    if args.output.exists():
        raise FileExistsError("Output already exists.")
    backend, root = _backend(args)
    result = run_images(load_image(args.source), backend, work_root=root,
                        mix=args.mix, keep_debug_files=args.keep_debug_files)
    encoded = result.report_path.parent / "encoded.png"
    metadata = PngInfo()
    metadata.add_text("AMD_NR_Provenance", json.dumps({"bridge_version": __version__, "backend": backend.name,
                      "neural_execution_reported": result.report["evidence"]["neural_execution_reported"],
                      "quality_improvement_proven": False}))
    Image.fromarray(np.rint(result.images[0] * 255).astype(np.uint8)).save(encoded, pnginfo=metadata)
    try:
        publish_new_file(encoded, args.output.resolve())
    finally:
        encoded.unlink(missing_ok=True)
    print(json.dumps({"output": str(args.output.resolve()), "manifest": str(result.report_path),
                      "neural_execution_reported": result.report["evidence"]["neural_execution_reported"]}, indent=2))


def init_config(args) -> None:
    from .config import PIN
    engine, runtime_root = args.engine.resolve(), args.runtime_dir.resolve()
    if not engine.is_file():
        raise FileNotFoundError(engine)
    runtime = {}
    for name in RUNTIME_NAMES:
        path = runtime_root / name
        if name == "version.dll" and not path.is_file():
            path = runtime_root / "version.dll.bak"
        if not path.is_file():
            raise FileNotFoundError(f"Missing user-supplied {name}")
        runtime[name] = {"path": str(path), "sha256": sha256_file(path)}
    if args.hip_device is not None and (not args.hip_device.isascii() or not args.hip_device.isdecimal()):
        raise ContractError("Choose one numeric HIP device index, or leave it unset.")
    data = {"schema": 1, "trusted_local_artifacts": False,
            "engine": {"path": str(engine), "sha256": sha256_file(engine)},
            "runtime": runtime, "work_root": str(args.work_root.resolve()),
            "hip_device": args.hip_device, "timeout_seconds": 600, "worker_seconds": 120,
            "fast_isolated": False, "fast_mode_verified_for_these_hashes": False,
            "max_width": 1920, "max_height": 1080}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
        out.write("\n")
    print(f"Wrote DISABLED configuration: {args.output}\nReview provenance/licenses and hashes before setting trusted_local_artifacts=true.\nExpected upstream source commit: {PIN}")


def selftest(args) -> None:
    from PIL import Image
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    yy, xx = np.mgrid[:48, :64]
    image = np.stack((xx / 63.0, yy / 47.0, ((xx // 4 + yy // 4) % 2).astype(float)), axis=-1).astype(np.float32)
    batch = np.stack((image, np.flip(image, axis=1)), axis=0)
    result = run_images(batch, ReferenceBackend(), work_root=root / "runs")
    assert result.images.shape == batch.shape
    assert result.report["evidence"]["neural_execution_reported"] is False
    assert np.max(np.abs(result.images - batch)) <= 0.5 / 255 + 1e-6
    Image.fromarray(np.rint(batch[0] * 255).astype(np.uint8)).save(root / "input.png")
    Image.fromarray(np.rint(result.images[0] * 255).astype(np.uint8)).save(root / "reference_NOT_DLSS.png")
    summary = {"status": "passed", "scope": "CPU transport self-test ONLY", "neural_inference_tested": False,
               "frames": 2, "manifest": str(result.report_path), "environment": diagnose()}
    write_json(root / "selftest.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="amd-nr", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Inspect configuration without loading native DLLs")
    doctor.add_argument("--output", type=Path)
    image = sub.add_parser("image", help="Process a local SDR image into a new PNG")
    video = sub.add_parser("video", help="Process a short local SDR/CFR clip into lossless MKV")
    for item in (image, video):
        item.add_argument("source", type=Path)
        item.add_argument("output", type=Path)
        item.add_argument("--backend", choices=("native", "reference"), default="native",
                          help="reference is a CPU transport test, NOT DLSS")
        item.add_argument("--config", type=Path)
        item.add_argument("--work-root", type=Path)
        item.add_argument("--mix", type=float, default=1.0)
    image.add_argument("--keep-debug-files", action="store_true", help="Retain private media/runtime copies; large and never upload them")
    video.add_argument("--chunk-frames", type=int, default=1)
    video.add_argument("--max-frames", type=int, default=300)
    init = sub.add_parser("init-config", help="Hash user-supplied artifacts into a DISABLED config")
    init.add_argument("--engine", type=Path, required=True)
    init.add_argument("--runtime-dir", type=Path, required=True)
    init.add_argument("--work-root", type=Path, required=True)
    init.add_argument("--hip-device")
    init.add_argument("--output", type=Path, required=True)
    smoke = sub.add_parser("selftest", help="CPU transport smoke test, with no GPU claim")
    smoke.add_argument("--output", type=Path, default=Path("selftest-output"))
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            report = diagnose()
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                write_json(args.output, report)
            print(json.dumps(report, indent=2, ensure_ascii=False))
        elif args.command == "image":
            image_command(args)
        elif args.command == "init-config":
            init_config(args)
        elif args.command == "selftest":
            selftest(args)
        else:
            from .video import process_video
            backend, root = _backend(args)
            path = process_video(args.source, args.output, backend, work_root=root, mix=args.mix,
                                 chunk_frames=args.chunk_frames, max_frames=args.max_frames,
                                 progress=lambda done, total: print(f"{done}/{total} frames", file=sys.stderr))
            print(str(path))
        return 0
    except (BridgeError, OSError, ValueError) as exc:
        print(f"ERROR [{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Cancelled; incomplete output was not published.", file=sys.stderr)
        return 130
