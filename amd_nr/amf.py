"""Server-configured AMD AMF VideoSR1.1 scaling after native NR.

This is a separate FFmpeg/AMF stage. It is not DLSS super-resolution.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Callable

import numpy as np

from .config import Artifact, NativeConfig
from .contracts import GIB, Limits, spec_for_shape
from .errors import ConfigurationError, ContractError, EvidenceError
from .filesystem import check_disk
from .process import run_process

UPSCALE_LIMITS = Limits(max_working_bytes=4 * GIB)


def output_size(width: int, height: int, factor: int, frames: int = 1) -> tuple[int, int]:
    if type(factor) is not int or not 2 <= factor <= 8:
        raise ContractError("AMF scale factor must be an integer from 2 to 8.")
    out_width, out_height = width * factor, height * factor
    spec_for_shape((frames, out_height, out_width, 3), UPSCALE_LIMITS)
    return out_width, out_height


class AMFScaler:
    """Pinned local FFmpeg executable; no executable path comes from a workflow."""

    def __init__(self, config: NativeConfig, *, cancel: Callable[[], None] | None = None):
        artifact = config.amf_ffmpeg
        if artifact is None:
            raise ConfigurationError("AMF VideoSR is not configured. Set amf_ffmpeg in config/backend.local.json.")
        artifact.verify()
        with artifact.path.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise ConfigurationError("AMF FFmpeg must be a Windows executable (MZ header).")
        self.artifact: Artifact = artifact
        self.expected_device_id = config.amf_expected_device_id
        self.cancel = cancel
        self.version = self._probe()

    def _probe(self) -> str:
        if self.cancel:
            self.cancel()
        executable = str(self.artifact.path)
        try:
            version = subprocess.run([executable, "-version"], capture_output=True,
                                     text=True, timeout=15, check=True)
            filters = subprocess.run([executable, "-hide_banner", "-filters"], capture_output=True,
                                     text=True, timeout=15, check=True)
            hwaccels = subprocess.run([executable, "-hide_banner", "-hwaccels"], capture_output=True,
                                      text=True, timeout=15, check=True)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ConfigurationError("The pinned AMF FFmpeg could not be probed.") from exc
        if not re.search(r"\bsr_amf\b", filters.stdout) or "amf" not in hwaccels.stdout.split():
            raise ConfigurationError("The pinned FFmpeg lacks sr_amf or AMF hardware acceleration.")
        if self.cancel:
            self.cancel()
        return version.stdout.splitlines()[0]

    def scale_rgb8(self, frames: np.ndarray, factor: int, work_root: Path) -> tuple[np.ndarray, dict]:
        if not isinstance(frames, np.ndarray) or frames.dtype != np.uint8 or frames.ndim != 4 or frames.shape[-1] != 3:
            raise ContractError("AMF scaling expects uint8 RGB frames [B,H,W,3].")
        count, height, width, _ = frames.shape
        out_width, out_height = output_size(width, height, factor, count)
        root = Path(work_root).resolve()
        check_disk(root, (frames.nbytes + count * out_width * out_height * 3) * 2,
                   UPSCALE_LIMITS.min_free_disk_bytes)
        job = Path(tempfile.mkdtemp(prefix="amf-", dir=root))
        raw_in, raw_out, log = job / "input.rgb", job / "output.rgb", job / "ffmpeg.log"
        succeeded = False
        try:
            np.ascontiguousarray(frames).tofile(raw_in)
            filtergraph = (f"format=rgba,hwupload,sr_amf={out_width}:{out_height}:"
                           "algorithm=sr1-1:format=rgba:keep-ratio=false:fill=false,"
                           "hwdownload,format=rgba,format=rgb24")
            run_process([str(self.artifact.path), "-nostdin", "-hide_banner", "-loglevel", "debug",
                         "-init_hw_device", "amf=amf", "-filter_hw_device", "amf",
                         "-f", "rawvideo", "-pix_fmt", "rgb24", "-video_size", f"{width}x{height}",
                         "-framerate", "1", "-i", str(raw_in), "-frames:v", str(count),
                         "-vf", filtergraph, "-f", "rawvideo", "-pix_fmt", "rgb24", str(raw_out)],
                        cwd=job, log=log, timeout=120, cancel=self.cancel, max_log_bytes=2 * 1024 * 1024)
            expected = count * out_width * out_height * 3
            if not raw_out.is_file() or raw_out.stat().st_size != expected:
                raise EvidenceError("AMF returned the wrong frame count or RGB output size.")
            log_text = log.read_text(encoding="utf-8", errors="replace")
            if "Using Algorithm VideoSR1.1" not in log_text:
                raise EvidenceError("AMF did not confirm VideoSR1.1; refusing ordinary scaling output.")
            match = re.search(r"deviceID=0x([0-9A-Fa-f]+)", log_text)
            device_id = match.group(1).lower() if match else None
            if self.expected_device_id and device_id != self.expected_device_id:
                raise EvidenceError("AMF selected a different or unidentified GPU; refusing output.")
            data = np.fromfile(raw_out, dtype=np.uint8).reshape(count, out_height, out_width, 3)
            evidence = {"backend": "FFmpeg sr_amf", "algorithm": "VideoSR1.1",
                        "ffmpeg_sha256": self.artifact.sha256, "ffmpeg_version": self.version,
                        "d3d11_device_id": device_id,
                        "input_size": [width, height], "output_size": [out_width, out_height],
                        "frames": count, "factor": factor,
                        "output_rgb_sha256": hashlib.sha256(data.tobytes()).hexdigest()}
            succeeded = True
            return data, evidence
        finally:
            raw_in.unlink(missing_ok=True)
            raw_out.unlink(missing_ok=True)
            if succeeded:
                log.unlink(missing_ok=True)
                job.rmdir()
