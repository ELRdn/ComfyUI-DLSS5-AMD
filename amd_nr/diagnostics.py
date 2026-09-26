"""Local environment diagnostics; never load the external runtime to probe it."""
from __future__ import annotations

import platform
import shutil
import sys
from . import __version__
from .config import config_path, load_native_config


def diagnose() -> dict:
    report = {"schema": 1, "bridge_version": __version__, "platform": platform.platform(),
              "python": sys.version.split()[0], "native_platform_eligible": platform.system() == "Windows",
              "native_gpu_smoke_test": "NOT_RUN", "native_quality_gate": "NOT_RUN",
              "ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"),
              "native_config_present": config_path().is_file()}
    try:
        import torch
        report["torch"] = {"version": str(torch.__version__), "hip_build": torch.version.hip,
                           "cuda_available": torch.cuda.is_available(),
                           "note": "PyTorch GPU availability does not validate the external D3D12/HIP runtime."}
    except ImportError:
        report["torch"] = None
    try:
        config = load_native_config()
        config.verify()
        report["native_config"] = {"state": "hashes_verified_not_executed", **config.private_manifest()}
    except (OSError, RuntimeError, ValueError) as exc:
        report["native_config"] = {"state": "unavailable", "reason": str(exc)}
    return report
