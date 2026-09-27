"""Explicit local setup for the pinned external runtime. Standard library only.

No model download, DLL loading for version inspection, driver installation,
game-folder writes, or successful-inference claim is part of setup.
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import platform
import re
import shutil
import struct
import subprocess
import tempfile
import time
import urllib.request
import uuid
import zipfile

from .process import stop_process_tree

ROOT = Path(__file__).resolve().parent.parent
PROXY_NAMES = ("version.dll", "dxgi.dll", "winmm.dll", "dbghelp.dll", "wininet.dll", "winhttp.dll")
HIP_LIBRARIES = ("amdhip64_6.dll", "amdhip64_7.dll", "amdhip64.dll")
MAX_MODEL_BYTES = 512 * 1024 * 1024


def load_lock(root: Path = ROOT) -> dict:
    lock = json.loads((root / "runtime.lock.json").read_text(encoding="utf-8"))
    if lock["schema"] != 1 or lock["tag"] != "v0.2.17":
        raise ValueError("Only the reviewed v0.2.17 setup protocol is supported.")
    expected_url = ("https://github.com/danielblnc/DLSS-NR-on-AMD/releases/"
                    "download/v0.2.17/dlssnr_on_amd_setup.exe")
    if lock["installer"]["url"] != expected_url:
        raise ValueError("Unexpected runtime installer URL.")
    return lock


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def regular_file(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular local file: {path}")
    return path.resolve()


def verify_file(path: Path, expected: dict) -> dict:
    path = regular_file(path)
    size = path.stat().st_size
    if size != expected["bytes"] or sha256(path) != expected["sha256"]:
        raise ValueError(f"Pinned size/SHA-256 mismatch: {path.name}")
    return {"path": str(path), "bytes": size, "sha256": expected["sha256"]}


def pe_x64(path: Path, *, dll: bool = False) -> None:
    path = regular_file(path)
    with path.open("rb") as source:
        dos = source.read(64)
        if len(dos) != 64 or dos[:2] != b"MZ":
            raise ValueError(f"Not a Windows PE file: {path.name}")
        offset = struct.unpack_from("<I", dos, 60)[0]
        if offset < 64 or offset > path.stat().st_size - 26:
            raise ValueError("Invalid PE header offset.")
        source.seek(offset)
        header = source.read(26)
    if header[:4] != b"PE\0\0" or struct.unpack_from("<H", header, 4)[0] != 0x8664:
        raise ValueError("Expected a Windows x64 PE file.")
    if struct.unpack_from("<H", header, 24)[0] != 0x20B:
        raise ValueError("Expected a PE32+ image.")
    if dll and not struct.unpack_from("<H", header, 22)[0] & 0x2000:
        raise ValueError("Expected a DLL image.")


def file_version(path: Path) -> str:
    """Read a VERSIONINFO resource through Windows; never load the target DLL."""
    if os.name != "nt":
        raise OSError("DLL version inspection requires Windows.")
    from ctypes import wintypes
    system = ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetSystemDirectoryW(system, len(system)):
        raise OSError("Cannot find Windows System32.")
    api = ctypes.WinDLL(str(Path(system.value) / "version.dll"), use_last_error=True)
    api.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    api.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    api.GetFileVersionInfoW.restype = wintypes.BOOL
    api.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                 ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    api.VerQueryValueW.restype = wintypes.BOOL
    unused = wintypes.DWORD()
    size = api.GetFileVersionInfoSizeW(str(path), ctypes.byref(unused))
    if not size or size > 16 * 1024 * 1024:
        raise ValueError("Missing or invalid DLL version resource.")
    data = ctypes.create_string_buffer(size)
    if not api.GetFileVersionInfoW(str(path), 0, size, data):
        raise ctypes.WinError(ctypes.get_last_error())
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    if not api.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)) or length.value < 52:
        raise ValueError("Missing fixed DLL version information.")
    info = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))
    if info[0] != 0xFEEF04BD:
        raise ValueError("Invalid DLL version signature.")
    return ".".join(str(x) for x in (info[2] >> 16, info[2] & 65535, info[3] >> 16, info[3] & 65535))


def inspect_model(path: Path, lock: dict) -> dict:
    path = regular_file(path)
    if path.name.lower() != lock["model"]["name"]:
        raise ValueError("Choose nvngx_dlssnr.dll; SR/RR/FG DLLs are different files.")
    pe_x64(path, dll=True)
    version = file_version(path)
    if version != lock["model"]["file_version"]:
        raise ValueError(f"Expected model version {lock['model']['file_version']}; found {version}.")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path), "file_version": version}


@contextmanager
def model_from_zip(archive: Path, *, root: Path = ROOT):
    """Extract only one user-supplied NR DLL into a private temporary directory."""
    archive = regular_file(archive)
    with zipfile.ZipFile(archive) as source:
        matches = []
        for member in source.infolist():
            name = member.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if not parts or parts[-1].lower() != "nvngx_dlssnr.dll":
                continue
            if (member.is_dir() or name.startswith("/") or ".." in parts or
                    parts[0].endswith(":") or member.flag_bits & 1 or
                    member.file_size > MAX_MODEL_BYTES or member.file_size == 0 or
                    (member.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("Unsafe or oversized nvngx_dlssnr.dll entry in ZIP.")
            matches.append(member)
        if len(matches) != 1:
            raise ValueError("ZIP must contain exactly one nvngx_dlssnr.dll; other DLSS DLLs are not substitutes.")
        private = root / "local-build" / "model-import"
        private.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="nr-dll-", dir=private) as temporary:
            target = Path(temporary) / "nvngx_dlssnr.dll"
            count = 0
            with source.open(matches[0]) as incoming, target.open("xb") as outgoing:
                while chunk := incoming.read(1024 * 1024):
                    count += len(chunk)
                    if count > MAX_MODEL_BYTES:
                        raise ValueError("NR DLL exceeded the import size limit.")
                    outgoing.write(chunk)
            if count != matches[0].file_size:
                raise ValueError("ZIP entry size changed during extraction.")
            yield target


def verify_engine(path: Path, lock: dict) -> dict:
    pe_x64(path)
    record = json.loads((path.parent / "build-record.json").read_text(encoding="utf-8-sig"))
    digest = sha256(path)
    if record.get("expected_source_commit") != lock["host_commit"] or record.get("engine_sha256") != digest:
        raise ValueError("Host build record does not match the pinned source and executable.")
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest}


class _ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlsplit
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in {
            "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"
        }:
            raise ValueError("Unexpected installer download redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_setup(root: Path = ROOT, *, opener=None) -> dict:
    lock = load_lock(root)
    expected = lock["installer"]
    cache = root / "local-build" / "runtime-downloads" / lock["tag"]
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / expected["name"]
    if target.exists() or target.is_symlink():
        return verify_file(target, expected)
    if opener is None:
        opener = urllib.request.build_opener(_ReleaseRedirect()).open
    request = urllib.request.Request(expected["url"], headers={"User-Agent": "ComfyUI-AMDNR-setup/0.1"})
    fd, name = tempfile.mkstemp(prefix="setup-", suffix=".partial", dir=cache)
    partial = Path(name)
    try:
        with os.fdopen(fd, "wb") as destination, opener(request, timeout=30) as response:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > expected["bytes"]:
                    raise ValueError("Installer download exceeded its pinned size.")
                destination.write(chunk)
        verify_file(partial, expected)
        os.link(partial, target)  # Publish exclusively; never overwrite an existing download.
    finally:
        partial.unlink(missing_ok=True)
    return verify_file(target, expected)


def probe_hip(library: str) -> dict:
    """Run this in a disposable process; DLL versions can enumerate GPUs differently."""
    if os.name != "nt" or library not in HIP_LIBRARIES:
        raise ValueError("Select an installed Windows HIP library by its supported name.")
    for name in ("HIP_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES"):
        os.environ.pop(name, None)  # Only this short-lived CLI process.
    system = ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetSystemDirectoryW(system, len(system)):
        raise OSError("Cannot find Windows System32.")
    path = Path(system.value) / library
    api = ctypes.WinDLL(str(regular_file(path)))
    api.hipInit.argtypes, api.hipInit.restype = [ctypes.c_uint], ctypes.c_int
    api.hipGetDeviceCount.argtypes, api.hipGetDeviceCount.restype = [ctypes.POINTER(ctypes.c_int)], ctypes.c_int
    api.hipDeviceGetName.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    api.hipDeviceGetPCIBusId.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    code = api.hipInit(0)
    if code:
        raise RuntimeError(f"hipInit failed: {code}")
    count = ctypes.c_int()
    code = api.hipGetDeviceCount(ctypes.byref(count))
    if code or not 0 <= count.value <= 64:
        raise RuntimeError(f"hipGetDeviceCount failed: {code}")
    devices = []
    for index in range(count.value):
        name, bus = ctypes.create_string_buffer(256), ctypes.create_string_buffer(64)
        if api.hipDeviceGetName(name, len(name), index) or api.hipDeviceGetPCIBusId(bus, len(bus), index):
            raise RuntimeError(f"HIP metadata query failed for device {index}")
        devices.append({"index": index, "name": name.value.decode(errors="replace"),
                        "pci_bus_id": bus.value.decode(errors="replace")})
    return {"library": str(path), "devices": devices, "neural_inference_tested": False}


def run_installer(executable: Path, directory: Path, timeout: float = 120) -> None:
    """The no-argument/stdin protocol is specific to the pinned v0.2.17 release."""
    options = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    with (directory / "setup-output.log").open("xb") as log:
        process = subprocess.Popen([str(executable)], cwd=directory, shell=False, stdin=subprocess.PIPE,
                                   stdout=log, stderr=subprocess.STDOUT, **options)
        try:
            process.communicate(input=b"y\n\n\n\n", timeout=timeout)
            if process.returncode:
                raise RuntimeError(f"Runtime setup exited {process.returncode}; inspect setup-output.log.")
        except BaseException:
            stop_process_tree(process)
            raise


def copy_checked(source: Path, target: Path, expected: dict) -> None:
    verify_file(source, expected)
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
    verify_file(target, expected)


def write_new_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Hardlink publication makes a configuration visible only after a complete write.
    fd, name = tempfile.mkstemp(prefix=".setup-", suffix=".partial", dir=path.parent)
    partial = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            json.dump(data, out, ensure_ascii=False, indent=2, allow_nan=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.link(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def install_runtime(model: Path, *, root: Path = ROOT, engine: Path | None = None,
                    config_output: Path | None = None, hip_device: str,
                    accept_runtime_license: bool = False, enable_config: bool = False) -> dict:
    if platform.system() != "Windows":
        raise OSError("Runtime installation requires Windows x64.")
    if not accept_runtime_license:
        raise ValueError("Read the pinned runtime LICENSE; personal/non-commercial use only. Pass --accept-runtime-license to accept it.")
    if not re.fullmatch(r"[0-9]+", hip_device):
        raise ValueError("Supply one verified numeric HIP device index.")
    lock = load_lock(root)
    output = (config_output or root / "config" / "backend.local.json").absolute()
    if not output.name.endswith(".local.json"):
        raise ValueError("Configuration must end in .local.json to keep private paths out of source packages.")
    if output.exists() or output.is_symlink():
        raise FileExistsError("Configuration already exists; existing settings are never overwritten.")
    model_info = inspect_model(model, lock)
    engine = engine or root / "local-build" / "native" / "dlss5_video_native.exe"
    engine_info = verify_engine(engine, lock)
    setup_info = download_setup(root)
    base = root / "local-build" / "runtime"
    base.mkdir(parents=True, exist_ok=True)
    required = model_info["bytes"] * 2 + 2 * lock["weights"]["bytes"] + 1024 ** 3
    if shutil.disk_usage(base).free < required:
        raise OSError(f"Insufficient free space for runtime setup: need {required} bytes.")
    job = base / (time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8])
    job.mkdir()
    staging = job / "setup"
    staging.mkdir()
    setup = staging / lock["installer"]["name"]
    copy_checked(Path(setup_info["path"]), setup, setup_info)
    copy_checked(model, staging / lock["model"]["name"], model_info)
    copy_checked(engine, staging / "dlss5_video_native.exe", engine_info)
    run_installer(setup, staging)
    # Keep the source copies and setup's rich INI for inspection; publish only exact expected outputs.
    verify_file(staging / lock["model"]["name"], model_info)
    verify_file(staging / "dlss5_video_native.exe", engine_info)
    proxies = [staging / name for name in PROXY_NAMES if (staging / name).exists()]
    if len(proxies) != 1:
        raise ValueError("Expected exactly one newly generated runtime proxy; inspect the setup directory.")
    verify_file(proxies[0], lock["proxy"])
    weights = staging / lock["weights"]["name"]
    verify_file(weights, lock["weights"])
    runtime = job / "artifacts"
    runtime.mkdir()
    artifacts = {}
    for name, source, expected in (("version.dll", proxies[0], lock["proxy"]),
                                   (lock["model"]["name"], staging / lock["model"]["name"], model_info),
                                   (lock["weights"]["name"], weights, lock["weights"])):
        target = runtime / name
        copy_checked(source, target, expected)
        artifacts[name] = {"path": str(target.resolve()), "sha256": expected["sha256"]}
    config = {"schema": 1, "trusted_local_artifacts": enable_config,
              "engine": {"path": engine_info["path"], "sha256": engine_info["sha256"]},
              "runtime": artifacts, "work_root": str((root / "runs" / "native").resolve()),
              "hip_device": hip_device, "timeout_seconds": 600, "worker_seconds": 120,
              "fast_isolated": False, "fast_mode_verified_for_these_hashes": False,
              "max_width": 1920, "max_height": 1080}
    installed_model = {**model_info, "path": artifacts[lock["model"]["name"]]["path"]}
    record = {"schema": 1, "runtime_tag": lock["tag"], "setup": setup_info, "model": installed_model,
              "host": engine_info, "artifacts": artifacts, "runtime_license_accepted": True,
              "config": str(output), "config_enabled": enable_config,
              "neural_inference_tested": False, "image_quality_tested": False}
    write_new_json(job / "installation-record.json", record)
    write_new_json(output, config)
    return record


def setup_status(root: Path = ROOT, model: Path | None = None) -> dict:
    lock = load_lock(root)
    cached = root / "local-build" / "runtime-downloads" / lock["tag"] / lock["installer"]["name"]
    engine = root / "local-build" / "native" / "dlss5_video_native.exe"
    report = {"runtime_tag": lock["tag"], "model_required": lock["model"],
              "runtime_license": lock["license_url"], "neural_inference_tested": False}
    for key, action in (("installer", lambda: verify_file(cached, lock["installer"])),
                        ("host", lambda: verify_engine(engine, lock))):
        try:
            report[key] = {"status": "verified", **action()}
        except (OSError, ValueError, KeyError) as exc:
            report[key] = {"status": "unavailable", "reason": str(exc)}
    if model is not None:
        report["model"] = {"status": "inspected", **inspect_model(model, lock)}
    else:
        report["model"] = {"status": "user_file_required"}
    return report
