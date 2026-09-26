"""Validate upstream's report contract; report evidence is not a quality score."""
from __future__ import annotations

from pathlib import Path

from .contracts import FrameSpec
from .errors import ContractError, EvidenceError
from .filesystem import read_json, sha256_file


def validate_native_report(job: Path, output: Path, spec: FrameSpec) -> dict:
    report_path = job / "engine-report.json"
    try:
        report = read_json(report_path)
    except (OSError, ContractError) as exc:
        raise EvidenceError("Missing or malformed native completion report; refusing output.") from exc
    if report.get("completed") is not True or report.get("enabled") is not True:
        raise EvidenceError("Native renderer did not confirm enabled, completed processing.")
    if report.get("status") != "ok" or report.get("error") != "":
        raise EvidenceError("Native report contains a failure or unsupported status.")
    for field in ("input_frames", "output_frames", "neural_frames_completed"):
        if type(report.get(field)) is not int or report[field] != spec.frames:
            raise EvidenceError(f"Invalid {field}; expected exactly {spec.frames}.")
    jobs = report.get("neural_jobs_logged")
    if type(jobs) is not int or jobs < 2 * spec.frames:
        raise EvidenceError("Expected at least two logged completions per isolated input frame.")
    if Path(str(output) + ".partial").exists():
        raise EvidenceError("Partial native output remains; refusing publication.")
    if output.is_symlink() or not output.is_file() or output.stat().st_size != spec.raw_bytes:
        raise EvidenceError("Native RGBA8 output is missing or its byte count is wrong.")
    # The fresh private job directory has no prior report before process start.
    # The pinned native coordinator attests per-frame log checks/fenced readback.
    # This wrapper does not pretend the JSON is cryptographic proof of inference.
    return {"level": "native_coordinator_report", "neural_execution_reported": True,
            "independent_gpu_verification": False, "temporal_history": False,
            "quality_improvement_proven": False, "engine_report": report,
            "engine_report_sha256": sha256_file(report_path)}
