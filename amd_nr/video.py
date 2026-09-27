"""Bounded-RAM, disk-backed SDR/CFR video processing. Output is lossless FFV1/MKV.

This is not zero-copy streaming: raw intermediates use O(video length) disk.
Default limits intentionally target short verification clips, not full films.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Callable

import numpy as np

from .amf import AMFScaler, output_size
from .backends import NativeBackend, ReferenceBackend
from .contracts import Limits, spec_for_shape, validate_mix
from .errors import ConfigurationError, ContractError, EvidenceError, ResourceError, RunCancelled
from .filesystem import check_disk, publish_new_file, read_json, sha256_file, write_json
from .pipeline import run_images
from .process import run_process

@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: Fraction
    frames: int
    audio_streams: int
    time_base: Fraction

    @property
    def raw_bytes(self) -> int:
        return self.width * self.height * self.frames * 4


def inspect_metadata(metadata: dict, max_frames: int) -> VideoInfo:
    videos = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
    if len(videos) != 1:
        raise ContractError("Video input must contain exactly one real video stream.")
    v = videos[0]
    if v.get("disposition", {}).get("attached_pic"):
        raise ContractError("Attached pictures are not a supported video stream.")
    if v.get("color_transfer") in {"smpte2084", "arib-std-b67", "linear"} or v.get("color_primaries") == "bt2020":
        raise ContractError("HDR, linear-light, and BT.2020 video need an explicit SDR grade first.")
    if any(float(s.get("rotation", 0)) != 0 for s in v.get("side_data_list", [])) or float(v.get("tags", {}).get("rotate", 0)) != 0:
        raise ContractError("Bake video rotation before processing; metadata-only rotation is not supported.")
    sar = v.get("sample_aspect_ratio", "1:1")
    if sar not in {"1:1", "0:1", "N/A", None}:
        raise ContractError("Export square pixels (sample aspect ratio 1:1) first.")
    try:
        fps = Fraction(v["avg_frame_rate"])
        nominal = Fraction(v["r_frame_rate"])
        frames = int(v["nb_read_frames"])
        width, height = int(v["width"]), int(v["height"])
        time_base = Fraction(v.get("time_base", "1/1000"))
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise ContractError("FFprobe could not establish frame count, dimensions, or constant FPS.") from exc
    if not 0 < fps <= 240 or fps != nominal or time_base <= 0:
        raise ContractError("Use a constant-frame-rate export (not VFR).")
    if min(width, height) < 16 or width % 2 or height % 2 or max(width, height) > 8192:
        raise ContractError("Video dimensions must be even, >=16, and <=8192.")
    if frames < 1 or frames > max_frames:
        raise ResourceError(f"Video has {frames} frames; configured limit is {max_frames}. Trim a test clip explicitly.")
    # All timestamps start at zero in our lossless raw-frame reconstruction.
    for stream in metadata.get("streams", []):
        if stream.get("codec_type") in {"video", "audio"}:
            if abs(float(stream.get("start_time", 0))) > max(0.002, min(2 * float(time_base), float(1 / fps) * 0.1)):
                raise ContractError("Nonzero stream start offsets are unsupported. Export a zero-origin clip first.")
    audio = sum(s.get("codec_type") == "audio" for s in metadata.get("streams", []))
    return VideoInfo(width, height, fps, frames, audio, time_base)


def verify_timestamps(payload: dict, info: VideoInfo) -> None:
    try:
        values = [float(frame["best_effort_timestamp_time"]) for frame in payload["frames"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractError("Missing decoded video timestamps; CFR cannot be verified.") from exc
    if len(values) != info.frames or not np.isfinite(values).all():
        raise ContractError("Decoded timestamp count is inconsistent.")
    tolerance = max(1e-6, min(2 * float(info.time_base), float(1 / info.fps) * 0.1))
    expected = np.arange(info.frames, dtype=np.float64) / float(info.fps)
    if np.max(np.abs(np.asarray(values) - expected)) > tolerance:
        raise ContractError("Decoded timestamps are not on the requested CFR grid.")


def _probe(ffprobe: str, source: Path, target: Path, cancel: Callable | None) -> dict:
    run_process([ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe",
                 "-count_frames", "-show_streams", "-show_format", "-of", "json", str(source)],
                cwd=target.parent, log=target, timeout=120, cancel=cancel)
    return read_json(target)


def _audio_hashes(ffmpeg: str, source: Path, count: int, job: Path,
                  prefix: str, cancel: Callable | None) -> list[str]:
    hashes = []
    for index in range(count):
        path = job / f"{prefix}-audio-{index}.txt"
        run_process([ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
                     "-i", str(source), "-map", f"0:a:{index}", "-c", "copy", "-f", "hash",
                     "-hash", "sha256", "-"], cwd=job, log=path, timeout=120, cancel=cancel)
        match = re.fullmatch(r"SHA256=([0-9a-fA-F]{64})\s*", path.read_text().strip())
        if not match:
            raise EvidenceError("Could not hash copied audio packet payloads.")
        hashes.append(match.group(1).lower())
    return hashes


def process_video(source: Path, destination: Path, backend: NativeBackend | ReferenceBackend, *,
                  work_root: Path, mix: float = 1.0, chunk_frames: int = 1,
                  max_frames: int = 300, limits: Limits = Limits(),
                  upscaler: AMFScaler | None = None, upscale_factor: int = 1,
                  cancel: Callable[[], None] | None = None,
                  progress: Callable[[int, int], None] | None = None) -> Path:
    mix = validate_mix(mix)
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file() or source.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise ContractError("Use an existing local MP4, MOV, MKV, or WebM file.")
    if destination.suffix.lower() != ".mkv":
        raise ContractError("Validation output must be .mkv (lossless FFV1 RGB with copied audio).")
    if destination.exists() or destination == source:
        raise FileExistsError("Choose a new output path; input and existing files are never replaced.")
    if type(chunk_frames) is not int or not 1 <= chunk_frames <= limits.max_frames:
        raise ContractError("chunk_frames must be a positive integer within the image batch limit.")
    if type(max_frames) is not int or not 1 <= max_frames <= 10000:
        raise ContractError("max_frames must be 1..10000; use deliberate short test clips.")
    if upscaler is None and upscale_factor != 1:
        raise ContractError("An AMF upscaler is required when video dimensions change.")
    if upscaler is not None and not isinstance(upscaler, AMFScaler):
        raise ContractError("Expected a server-configured AMF scaler.")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ConfigurationError("FFmpeg and FFprobe must be installed on PATH; neither is downloaded automatically.")
    root = Path(work_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    job = Path(tempfile.mkdtemp(prefix="video-", dir=root))
    manifest = {"schema": 1, "status": "started", "backend": backend.name,
                "source_sha256": sha256_file(source), "source_name": source.name,
                "output_name": destination.name, "disk_backed": True,
                "temporally_accumulated": False, "quality_improvement_proven": False,
                "chunk_frames": chunk_frames, "mix": mix, "chunks": []}
    report_path = job / "video-manifest.json"
    write_json(report_path, manifest)
    start = time.monotonic()
    raw_in, raw_out, staged = job / "input.rgba", job / "output.rgba", job / "encoded.mkv"
    failure: BaseException | None = None
    try:
        metadata = _probe(ffprobe, source, job / "source-probe.json", cancel)
        info = inspect_metadata(metadata, max_frames)
        spec_for_shape((min(chunk_frames, info.frames), info.height, info.width, 3), limits)
        if upscaler is not None:
            out_width, out_height = output_size(info.width, info.height, upscale_factor,
                                                min(chunk_frames, info.frames))
            manifest["upscale"] = {"backend": "FFmpeg sr_amf", "algorithm": "VideoSR1.1",
                                    "factor": upscale_factor, "ffmpeg_sha256": upscaler.artifact.sha256,
                                    "output_width": out_width, "output_height": out_height}
        else:
            out_width, out_height = info.width, info.height
        output_raw_bytes = out_width * out_height * info.frames * 4
        manifest["video"] = {"width": info.width, "height": info.height, "fps": str(info.fps),
                             "frames": info.frames, "audio_streams": info.audio_streams,
                             "output_width": out_width, "output_height": out_height,
                             "output_codec": "FFV1 RGB8", "subtitles_chapters_metadata": "not preserved"}
        # Raw source + result + lossless encoded output + publication temp reserve.
        check_disk(root, info.raw_bytes * 2 + output_raw_bytes * 3, limits.min_free_disk_bytes)
        check_disk(destination.parent, output_raw_bytes * 2, limits.min_free_disk_bytes)
        timestamp_file = job / "timestamps.json"
        run_process([ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams", "v:0",
                     "-show_frames", "-show_entries", "frame=best_effort_timestamp_time",
                     "-of", "json", str(source)], cwd=job, log=timestamp_file, timeout=120, cancel=cancel)
        verify_timestamps(read_json(timestamp_file), info)
        run_process([ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
                     "-i", str(source), "-map", "0:v:0", "-an", "-sn", "-dn",
                     "-fps_mode", "passthrough", "-pix_fmt", "rgba", "-f", "rawvideo", str(raw_in)],
                    cwd=job, log=job / "decode.log", timeout=600, cancel=cancel)
        if raw_in.stat().st_size != info.raw_bytes:
            raise EvidenceError("Decoded raw frame count differs from probed frame count.")
        frame_bytes = info.width * info.height * 4
        with raw_in.open("rb") as inp, raw_out.open("xb") as out:
            for offset in range(0, info.frames, chunk_frames):
                count = min(chunk_frames, info.frames - offset)
                if cancel:
                    cancel()
                payload = inp.read(count * frame_bytes)
                frames = np.frombuffer(payload, dtype=np.uint8).reshape(count, info.height, info.width, 4)
                rgb = frames[..., :3].astype(np.float32) / 255.0
                result = run_images(rgb, backend, work_root=job / "frame-jobs", mix=mix,
                                    limits=limits, cancel=cancel)
                from .contracts import rgba8
                if upscaler is not None:
                    rgb8 = np.rint(result.images[..., :3] * 255).astype(np.uint8)
                    scaled, amf_evidence = upscaler.scale_rgb8(rgb8, upscale_factor, job / "amf-jobs")
                    output_rgba = np.empty((count, out_height, out_width, 4), dtype=np.uint8)
                    output_rgba[..., :3] = scaled
                    output_rgba[..., 3] = 255
                else:
                    output_rgba = rgba8(result.images)
                    amf_evidence = None
                output_rgba.tofile(out)
                chunk = {"first_frame": offset, "count": count,
                    "manifest": str(result.report_path.relative_to(job)),
                    "neural_execution_reported": result.report["evidence"]["neural_execution_reported"]}
                if amf_evidence is not None:
                    chunk["amf"] = amf_evidence
                manifest["chunks"].append(chunk)
                if progress:
                    progress(offset + count, info.frames)
        if raw_out.stat().st_size != output_raw_bytes:
            raise EvidenceError("Processed raw size is inconsistent.")
        run_process([ffmpeg, "-nostdin", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
                     "-video_size", f"{out_width}x{out_height}", "-framerate", str(info.fps),
                     "-i", str(raw_out), "-protocol_whitelist", "file,pipe", "-i", str(source),
                     "-map", "0:v:0", "-map", "1:a?", "-map_metadata", "-1", "-map_chapters", "-1",
                     "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgr0", "-c:a", "copy", str(staged)],
                    cwd=job, log=job / "encode.log", timeout=600, cancel=cancel)
        final = _probe(ffprobe, staged, job / "output-probe.json", cancel)
        final_info = inspect_metadata(final, max_frames)
        output_timestamps = job / "output-timestamps.json"
        run_process([ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams", "v:0",
                     "-show_frames", "-show_entries", "frame=best_effort_timestamp_time",
                     "-of", "json", str(staged)], cwd=job, log=output_timestamps, timeout=120, cancel=cancel)
        verify_timestamps(read_json(output_timestamps), final_info)
        if (final_info.width, final_info.height, final_info.frames, final_info.fps, final_info.audio_streams) != (
                out_width, out_height, info.frames, info.fps, info.audio_streams):
            raise EvidenceError("Encoded dimensions, frame count, FPS or audio count changed.")
        input_audio = _audio_hashes(ffmpeg, source, info.audio_streams, job, "input", cancel)
        output_audio = _audio_hashes(ffmpeg, staged, info.audio_streams, job, "output", cancel)
        if input_audio != output_audio:
            raise EvidenceError("Copied audio payload hashes differ; refusing publication.")
        if cancel:
            cancel()
        digest = sha256_file(staged)
        manifest.update(status="verified_pending_publication", output_sha256=digest,
                        audio_payload_sha256=input_audio,
                        audio_timestamps_independently_verified=False,
                        source_color_tags={k: v for s in metadata.get("streams", []) if s.get("codec_type") == "video"
                                           for k, v in s.items() if k.startswith("color_")})
        write_json(report_path, manifest)
        publish_new_file(staged, destination)
        manifest["status"] = "completed"
    except BaseException as exc:
        failure = exc
        cancelled = isinstance(exc, (RunCancelled, KeyboardInterrupt)) or type(exc).__name__ == "InterruptProcessingException"
        manifest.update(status="cancelled" if cancelled else "failed",
                        error={"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        manifest["elapsed_seconds"] = time.monotonic() - start
        for path in (raw_in, raw_out, staged):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                manifest.setdefault("cleanup_warnings", []).append(str(exc))
        try:
            write_json(report_path, manifest)
        except OSError:
            if failure is None:
                raise
    return report_path
