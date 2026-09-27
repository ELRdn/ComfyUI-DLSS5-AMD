#!/usr/bin/env python3
"""Prepare the pinned AMD runtime, then install from a user-supplied NVIDIA NR DLL."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from amd_nr.runtime_setup import HIP_LIBRARIES, download_setup, install_runtime, model_from_zip, probe_hip, setup_status
from amd_nr.filesystem import read_json, sha256_file, write_json


def configure_amf(ffmpeg: Path, config_path: Path, *, replace: bool = False,
                  device_id: str | None = None) -> dict:
    """Pin an installed AMF-capable FFmpeg in an existing private NR config."""
    if not config_path.name.endswith(".local.json"):
        raise ValueError("AMF configuration must be an existing .local.json file.")
    data = read_json(config_path)
    if data.get("schema") != 1:
        raise ValueError("Expected the existing native configuration schema 1.")
    executable = ffmpeg.expanduser().resolve(strict=True)
    if not executable.is_file() or executable.is_symlink() or executable.suffix.lower() != ".exe":
        raise ValueError("Select a regular Windows FFmpeg executable.")
    with executable.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("Selected FFmpeg has no Windows PE header.")
    def probe(*args: str) -> str:
        completed = subprocess.run([str(executable), *args], capture_output=True,
                                   text=True, timeout=15, check=True)
        return completed.stdout
    version = probe("-version").splitlines()[0]
    filters = probe("-hide_banner", "-filters")
    hwaccels = probe("-hide_banner", "-hwaccels")
    if not re.search(r"\bsr_amf\b", filters) or "amf" not in hwaccels.split():
        raise ValueError("FFmpeg lacks sr_amf or AMF hardware acceleration.")
    value = {"path": str(executable), "sha256": sha256_file(executable)}
    previous = data.get("amf_ffmpeg")
    if previous and previous != value and not replace:
        raise ValueError("An AMF FFmpeg is already pinned. Review it and pass --replace to change the pin.")
    if device_id is not None and not re.fullmatch(r"[0-9a-fA-F]{4,8}", device_id):
        raise ValueError("--device-id must be a 4-8 digit hexadecimal PCI device ID.")
    changed = previous != value or (device_id is not None and data.get("amf_expected_device_id") != device_id.lower())
    if changed:
        data["amf_ffmpeg"] = value
        if device_id is not None:
            data["amf_expected_device_id"] = device_id.lower()
        write_json(config_path, data)
    return {"config": str(config_path), "amf_ffmpeg": value, "version": version,
            "amf_expected_device_id": data.get("amf_expected_device_id"),
            "changed": changed, "neural_inference_tested": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="Read local prerequisites; no downloads or native DLL execution")
    status_model = status.add_mutually_exclusive_group()
    status_model.add_argument("--model-dll", type=Path)
    status_model.add_argument("--model-zip", type=Path, help="User-supplied ZIP containing one nvngx_dlssnr.dll")
    commands.add_parser("prepare", help="Download and verify the pinned public installer; never execute it")
    probe = commands.add_parser("probe-hip", help="Enumerate GPUs through one installed system HIP library")
    probe.add_argument("--library", choices=HIP_LIBRARIES, required=True)
    install = commands.add_parser("install", help="Run pinned setup in a fresh private folder, then write a new config")
    install_model = install.add_mutually_exclusive_group(required=True)
    install_model.add_argument("--model-dll", type=Path)
    install_model.add_argument("--model-zip", type=Path, help="User-supplied ZIP containing one nvngx_dlssnr.dll")
    install.add_argument("--hip-device", required=True, help="Index verified for the runtime's HIP library, not the ComfyUI CUDA index")
    install.add_argument("--engine", type=Path)
    install.add_argument("--config-output", type=Path)
    install.add_argument("--accept-runtime-license", action="store_true", help="Accept the external runtime's personal/non-commercial license")
    install.add_argument("--enable-config", action="store_true", help="Explicitly trust reviewed local artifacts; default is a disabled config")
    amf = commands.add_parser("configure-amf", help="Pin a local FFmpeg with sr_amf in an existing private config")
    amf.add_argument("--ffmpeg", type=Path, required=True)
    amf.add_argument("--config", type=Path, default=ROOT / "config" / "backend.local.json")
    amf.add_argument("--replace", action="store_true", help="Replace a different existing AMF FFmpeg pin")
    amf.add_argument("--device-id", help="Optional hexadecimal PCI device ID to require in each AMF execution log")
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            if args.model_zip:
                with model_from_zip(args.model_zip) as model:
                    result = setup_status(model=model)
                result["model"]["path"] = str(args.model_zip.resolve()) + "!/nvngx_dlssnr.dll"
            else:
                result = setup_status(model=args.model_dll)
        elif args.command == "prepare":
            result = {"installer": download_setup(), "executed": False, "model_downloaded": False}
        elif args.command == "probe-hip":
            result = probe_hip(args.library)
        elif args.command == "configure-amf":
            result = configure_amf(args.ffmpeg, args.config, replace=args.replace,
                                   device_id=args.device_id)
        else:
            if args.model_zip:
                with model_from_zip(args.model_zip) as model:
                    result = install_runtime(model, engine=args.engine, config_output=args.config_output,
                                             hip_device=args.hip_device, accept_runtime_license=args.accept_runtime_license,
                                             enable_config=args.enable_config)
            else:
                result = install_runtime(args.model_dll, engine=args.engine, config_output=args.config_output,
                                         hip_device=args.hip_device, accept_runtime_license=args.accept_runtime_license,
                                         enable_config=args.enable_config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Setup cancelled. Partial private setup files were retained for inspection.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
