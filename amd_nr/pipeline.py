"""Audited image pipeline. Native failure never switches to a reference backend."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import tempfile
import time
from typing import Callable

import numpy as np

from . import __version__
from .backends import NativeBackend, ReferenceBackend
from .contracts import Limits, compose, rgba8, validate_images, validate_mask, validate_mix
from .errors import RunCancelled
from .filesystem import check_disk, workspace_lock, write_json

@dataclass
class ImageResult:
    images: np.ndarray
    report: dict
    report_path: Path


def _hash_frames(images: np.ndarray) -> list[str]:
    return [hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest() for frame in images]


def _cleanup(job: Path) -> None:
    # Logs may still include local paths. Do not auto-upload them.
    keep = {"manifest.json", "engine-report.json", "process.log"}
    for path in job.iterdir():
        if path.name in keep and path.is_file() and not path.is_symlink():
            continue
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path)


def run_images(images: np.ndarray, backend: ReferenceBackend | NativeBackend, *,
               work_root: Path, mix: float = 1.0, effect_mask: np.ndarray | None = None,
               limits: Limits = Limits(), keep_debug_files: bool = False,
               cancel: Callable[[], None] | None = None) -> ImageResult:
    spec = validate_images(images, limits)
    mix = validate_mix(mix)
    mask = validate_mask(effect_mask, spec)
    if cancel:
        cancel()
    root = Path(work_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = workspace_lock(backend.config.work_root) if backend.is_native else nullcontext()
    with lock:
        # Fail on missing files/platform before large media staging where possible.
        if backend.is_native:
            backend.config.verify()
        required = backend.required_disk(spec)
        check_disk(root, required, limits.min_free_disk_bytes)
        job = Path(tempfile.mkdtemp(prefix="job-", dir=root))
        manifest_path = job / "manifest.json"
        manifest = {"schema": 1, "bridge_version": __version__, "job_id": job.name,
                    "created_utc": datetime.now(timezone.utc).isoformat(), "status": "started",
                    "backend": backend.name, "image": spec.as_dict(), "mix": mix,
                    "effect_mask": None if mask is None else {
                        "sha256": hashlib.sha256(np.ascontiguousarray(mask).tobytes()).hexdigest(),
                        "shape": list(mask.shape), "white_means": "apply_effect"},
                    "input_dtype": str(images.dtype), "input_frame_sha256": _hash_frames(images),
                    "keep_debug_files": keep_debug_files, "quality_improvement_proven": False}
        write_json(manifest_path, manifest)
        start = time.monotonic()
        result: ImageResult | None = None
        failure: BaseException | None = None
        try:
            packed = rgba8(images)
            manifest["transfer_frame_sha256"] = _hash_frames(packed)
            backend_result = backend.execute(packed, spec, job, cancel)
            if cancel:
                cancel()
            output = compose(images, backend_result.rgba, mix, mask)
            manifest.update(status="completed", evidence=backend_result.evidence,
                            output_dtype=str(output.dtype), output_frame_sha256=_hash_frames(output),
                            quantization_step=1 / 255,
                            quantization_rounding="round-to-nearest ties-to-even",
                            semantic_note="Native reports indicate execution, not improved detail or temporal stability.")
            result = ImageResult(output, manifest, manifest_path)
        except BaseException as exc:
            failure = exc
            cancelled = isinstance(exc, (RunCancelled, KeyboardInterrupt)) or type(exc).__name__ == "InterruptProcessingException"
            manifest.update(status="cancelled" if cancelled else "failed",
                            error={"type": type(exc).__name__, "message": str(exc)})
            raise
        finally:
            manifest["elapsed_seconds"] = time.monotonic() - start
            if not keep_debug_files:
                try:
                    _cleanup(job)
                    manifest["private_payload_cleaned"] = True
                except OSError as exc:
                    manifest["private_payload_cleaned"] = False
                    manifest["cleanup_warning"] = str(exc)
            # A manifest-write error should not hide the original inference failure.
            try:
                write_json(manifest_path, manifest)
            except OSError:
                if failure is None:
                    raise
        assert result is not None
        return result
