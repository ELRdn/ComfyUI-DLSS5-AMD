"""Native executable paths are server configuration, NEVER workflow inputs."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil

from .errors import ConfigurationError
from .filesystem import read_json, sha256_file

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_NAMES = ("version.dll", "nvngx_dlssnr.dll", "dlssnr_on_amd_weights.bin")
PIN = "9303dfaa14c2ca83e237ff18318bdfc0b767f6fb"

@dataclass(frozen=True)
class Artifact:
    path: Path
    sha256: str

    def verify(self) -> None:
        if not self.path.is_file() or self.path.is_symlink():
            raise ConfigurationError(f"Missing/nonregular trusted artifact: {self.path}")
        if sha256_file(self.path) != self.sha256:
            raise ConfigurationError(f"SHA-256 mismatch: {self.path.name}. Review the new file before updating its pin.")

@dataclass(frozen=True)
class NativeConfig:
    engine: Artifact
    runtime: dict[str, Artifact]
    work_root: Path
    hip_device: str | None
    timeout_seconds: int = 600
    worker_seconds: int = 120
    fast_isolated: bool = False
    max_width: int = 1920
    max_height: int = 1080
    amf_ffmpeg: Artifact | None = None
    amf_expected_device_id: str | None = None

    def verify(self) -> None:
        self.engine.verify()
        with self.engine.path.open("rb") as f:
            if f.read(2) != b"MZ":
                raise ConfigurationError("Native engine must be a Windows executable (MZ header).")
        for artifact in self.runtime.values():
            artifact.verify()

    def private_manifest(self) -> dict:
        return {"adapter": "eikkapine-raw-v1", "expected_upstream_source_commit": PIN,
                "engine_source_attestation_verified": False,
                "engine_sha256": self.engine.sha256,
                "runtime_sha256": {name: item.sha256 for name, item in self.runtime.items()},
                "hip_device_requested": self.hip_device,
                "fast_isolated": self.fast_isolated,
                "timeout_seconds": self.timeout_seconds,
                "worker_seconds": self.worker_seconds,
                "device_execution_independently_verified": False,
                "amf_ffmpeg_sha256": self.amf_ffmpeg.sha256 if self.amf_ffmpeg else None,
                "amf_expected_device_id": self.amf_expected_device_id}

    def stage(self, job: Path) -> Path:
        """Copy fixed filenames into a new private directory; verify copied bytes."""
        engine = job / "dlss5_video_native.exe"
        for target, artifact in [(engine, self.engine)] + [(job / name, artifact) for name, artifact in self.runtime.items()]:
            if target.exists():
                raise ConfigurationError("Staging destination is not fresh.")
            with artifact.path.open("rb") as source, target.open("xb") as dest:
                shutil.copyfileobj(source, dest, 1024 * 1024)
            if sha256_file(target) != artifact.sha256:
                raise ConfigurationError(f"Staged artifact changed during copy: {target.name}")
        return engine


def config_path() -> Path:
    return Path(os.environ.get("AMD_NR_CONFIG", ROOT / "config" / "backend.local.json")).expanduser().resolve()


def _absolute(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\0" in value:
        raise ConfigurationError(f"{label} must be an absolute path string.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ConfigurationError(f"{label} must be absolute; no working-directory-dependent executable lookup.")
    return path


def _artifact(value: object, label: str) -> Artifact:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise ConfigurationError(f"{label} needs exactly path and sha256.")
    digest = value["sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ConfigurationError(f"{label}.sha256 must be 64 lowercase hexadecimal digits.")
    return Artifact(_absolute(value["path"], label), digest)


def load_native_config(path: Path | None = None) -> NativeConfig:
    path = path or config_path()
    if not path.is_file():
        raise ConfigurationError(f"Native backend is not configured: {path}. Read docs/WINDOWS_SETUP.md; no fallback was used.")
    data = read_json(path)
    allowed = {"schema", "trusted_local_artifacts", "engine", "runtime", "work_root", "hip_device",
               "timeout_seconds", "worker_seconds", "fast_isolated", "fast_mode_verified_for_these_hashes",
               "max_width", "max_height", "amf_ffmpeg", "amf_expected_device_id"}
    if set(data) - allowed:
        raise ConfigurationError(f"Unknown configuration keys: {sorted(set(data) - allowed)}")
    if type(data.get("schema")) is not int or data["schema"] != 1:
        raise ConfigurationError("Expected native configuration schema 1.")
    if data.get("trusted_local_artifacts") is not True:
        raise ConfigurationError("Review local executable/runtime provenance and explicitly set trusted_local_artifacts=true.")
    runtime = data.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != set(RUNTIME_NAMES):
        raise ConfigurationError(f"runtime must provide exactly {RUNTIME_NAMES}.")
    hip = data.get("hip_device")
    if hip is not None and (not isinstance(hip, str) or not re.fullmatch(r"[0-9]+", hip)):
        raise ConfigurationError("hip_device must be null or one numeric string. Device 1 is not universal.")
    amf_device = data.get("amf_expected_device_id")
    if amf_device is not None and (not isinstance(amf_device, str) or
                                   not re.fullmatch(r"[0-9a-fA-F]{4,8}", amf_device)):
        raise ConfigurationError("amf_expected_device_id must be a 4-8 digit hexadecimal PCI device ID or null.")
    if type(data.get("fast_isolated", False)) is not bool:
        raise ConfigurationError("fast_isolated must be Boolean.")
    fast = data.get("fast_isolated", False)
    if fast and data.get("fast_mode_verified_for_these_hashes") is not True:
        raise ConfigurationError("Fast mode requires explicit local verification of this exact runtime/engine pair.")
    numbers = {}
    for key, default, maximum in (("timeout_seconds", 600, 86400), ("worker_seconds", 120, 86400),
                                  ("max_width", 1920, 8192), ("max_height", 1080, 8192)):
        number = data.get(key, default)
        if type(number) is not int or not 1 <= number <= maximum:
            raise ConfigurationError(f"{key} must be an integer from 1 to {maximum}.")
        numbers[key] = number
    if numbers["worker_seconds"] > numbers["timeout_seconds"]:
        raise ConfigurationError("worker_seconds cannot exceed timeout_seconds.")
    return NativeConfig(engine=_artifact(data.get("engine"), "engine"),
                        runtime={name: _artifact(runtime[name], name) for name in RUNTIME_NAMES},
                        work_root=_absolute(data.get("work_root"), "work_root"), hip_device=hip,
                        fast_isolated=fast,
                        amf_ffmpeg=_artifact(data["amf_ffmpeg"], "amf_ffmpeg")
                        if data.get("amf_ffmpeg") is not None else None,
                        amf_expected_device_id=amf_device.lower() if amf_device else None, **numbers)


def config_fingerprint() -> str:
    """Hash config AND local artifact metadata so cached Comfy results invalidate.

    Full file hashes are always checked again on execution. Deliberately hostile
    mutation that preserves file metadata is outside this local trust boundary.
    """
    path = config_path()
    if not path.is_file():
        return "unconfigured"
    try:
        config = load_native_config(path)
        parts = [sha256_file(path)]
        for artifact in [config.engine, *config.runtime.values(), *([config.amf_ffmpeg] if config.amf_ffmpeg else [])]:
            stat = artifact.path.stat()
            parts.append(f"{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ctime_ns}")
        return "|".join(parts)
    except (ConfigurationError, OSError, ValueError) as exc:
        return f"invalid:{sha256_file(path)}:{type(exc).__name__}"
