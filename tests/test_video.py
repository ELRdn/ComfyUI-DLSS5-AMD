from fractions import Fraction
import copy
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

from amd_nr.amf import AMFScaler
from amd_nr.backends import ReferenceBackend
from amd_nr.contracts import Limits
from amd_nr.errors import ContractError, ResourceError, RunCancelled
from amd_nr.filesystem import read_json
from amd_nr.video import VideoInfo, inspect_metadata, process_video, verify_timestamps


def metadata():
    return {'streams': [{'codec_type': 'video', 'avg_frame_rate': '24/1', 'r_frame_rate': '24/1',
        'nb_read_frames': '6', 'width': 32, 'height': 24, 'time_base': '1/1000', 'start_time': '0',
        'sample_aspect_ratio': '1:1'}]}


def test_metadata_and_timestamps():
    info = inspect_metadata(metadata(), 6)
    assert info.raw_bytes == 6 * 32 * 24 * 4
    verify_timestamps({'frames': [{'best_effort_timestamp_time': str(i / 24)} for i in range(6)]}, info)


@pytest.mark.parametrize('key,value', [
    ('color_transfer', 'smpte2084'), ('color_transfer', 'arib-std-b67'),
    ('color_transfer', 'linear'), ('color_primaries', 'bt2020'),
    ('sample_aspect_ratio', '4:3'), ('avg_frame_rate', '0/0'),
    ('r_frame_rate', '30/1'), ('width', 33), ('height', 0),
    ('nb_read_frames', 'N/A'), ('nb_read_frames', '301'), ('start_time', '0.2'),
    ('side_data_list', [{'rotation': 90}]), ('tags', {'rotate': '180'}),
    ('disposition', {'attached_pic': 1}),
])
def test_reject_metadata(key, value):
    data = metadata()
    data['streams'][0][key] = value
    with pytest.raises((ContractError, ResourceError)):
        inspect_metadata(data, 300)


def test_cover_art_and_multiple_streams_refused():
    data = metadata()
    data['streams'].append({**data['streams'][0], 'disposition': {'attached_pic': 1}})
    with pytest.raises(ContractError):
        inspect_metadata(data, 300)


@pytest.mark.parametrize('values', [[0], [0, .04, .12, .13, .16, .2], [float('nan')] * 6])
def test_vfr_and_missing_timestamps_refused(values):
    with pytest.raises(ContractError):
        verify_timestamps({'frames': [{'best_effort_timestamp_time': v} for v in values]},
                          inspect_metadata(metadata(), 6))


def test_missing_timestamp_key():
    with pytest.raises(ContractError):
        verify_timestamps({'frames': [{}] * 6}, inspect_metadata(metadata(), 6))


@pytest.fixture
def clip(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('FFmpeg/FFprobe not installed')
    yy, xx = np.mgrid[:24, :32]
    frames = np.stack([np.stack(((xx * 7 + i * 19) % 256, (yy * 11 + i * 3) % 256,
        ((xx + yy + i) % 2) * 255), axis=-1) for i in range(6)]).astype(np.uint8)
    raw = tmp_path / 'fixture.rgb'
    frames.tofile(raw)
    source = tmp_path / 'moving fixture 日本語.mkv'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
        '-s', '32x24', '-r', '24', '-i', str(raw), '-f', 'lavfi', '-i',
        'sine=frequency=880:sample_rate=48000:duration=0.25', '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'bgr0', '-c:a', 'pcm_s16le', str(source)],
        check=True, timeout=15)
    return source, frames


@pytest.mark.ffmpeg
@pytest.mark.parametrize('chunk', [1, 2, 4])
def test_actual_lossless_video_and_audio(clip, tmp_path, chunk):
    source, frames = clip
    output = tmp_path / f'out-{chunk}.mkv'
    updates = []
    report_path = process_video(source, output, ReferenceBackend(), work_root=tmp_path / 'runs',
        chunk_frames=chunk, max_frames=6, limits=Limits(min_free_disk_bytes=0),
        progress=lambda done, total: updates.append((done, total)))
    report = read_json(report_path)
    assert report['status'] == 'completed'
    assert report['audio_payload_sha256'] and len(report['audio_payload_sha256'][0]) == 64
    assert report['quality_improvement_proven'] is False
    assert report['audio_timestamps_independently_verified'] is False
    assert updates[-1] == (6, 6)
    assert all(not c['neural_execution_reported'] for c in report['chunks'])
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(output),
        '-map', '0:v:0', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
        capture_output=True, check=True, timeout=15).stdout
    np.testing.assert_array_equal(np.frombuffer(decoded, np.uint8).reshape(frames.shape), frames)
    assert not list(report_path.parent.glob('*.rgba'))
    assert not (report_path.parent / 'encoded.mkv').exists()


@pytest.mark.ffmpeg
def test_video_overwrite_and_frame_limit(clip, tmp_path):
    source, _ = clip
    output = tmp_path / 'existing.mkv'
    output.write_bytes(b'KEEP ME')
    with pytest.raises(FileExistsError):
        process_video(source, output, ReferenceBackend(), work_root=tmp_path / 'runs')
    assert output.read_bytes() == b'KEEP ME'
    with pytest.raises(ResourceError):
        process_video(source, tmp_path / 'new.mkv', ReferenceBackend(), work_root=tmp_path / 'runs', max_frames=5)
    assert not (tmp_path / 'new.mkv').exists()


@pytest.mark.ffmpeg
def test_video_cancel_no_publication(clip, tmp_path):
    source, _ = clip
    output = tmp_path / 'cancelled.mkv'
    def cancel():
        raise RunCancelled('cancel test')
    with pytest.raises(RunCancelled):
        process_video(source, output, ReferenceBackend(), work_root=tmp_path / 'runs', cancel=cancel)
    assert not output.exists()
    report = read_json(next((tmp_path / 'runs').glob('video-*/video-manifest.json')))
    assert report['status'] == 'cancelled'


@pytest.mark.parametrize('options', [{'chunk_frames': 0}, {'max_frames': True}, {'mix': float('nan')}])
def test_video_argument_validation(tmp_path, options):
    source = tmp_path / 'input.mkv'
    source.write_bytes(b'placeholder')
    with pytest.raises(ContractError):
        process_video(source, tmp_path / 'out.mkv', ReferenceBackend(), work_root=tmp_path / 'runs', **options)

def test_coarse_timebase_must_not_hide_a_frame_shift():
    info = VideoInfo(32, 24, Fraction(24), 6, 0, Fraction(1,24))
    # A one-frame timeline shift is not accepted even with a coarse time base.
    with pytest.raises(ContractError):
        verify_timestamps({'frames': [{'best_effort_timestamp_time': str((i + 1) / 24)}
                                     for i in range(6)]}, info)


class RepeatAMF(AMFScaler):
    """Test double for video orchestration; no hardware inference claim."""

    def __init__(self, *, fail=False):
        self.artifact = SimpleNamespace(sha256='f' * 64)
        self.fail = fail

    def scale_rgb8(self, frames, factor, work_root):
        if self.fail:
            raise RuntimeError('AMF test failure')
        scaled = np.repeat(np.repeat(frames, factor, axis=1), factor, axis=2)
        return scaled, {'algorithm': 'TEST_DOUBLE', 'factor': factor}


@pytest.mark.ffmpeg
def test_video_upscale_preserves_frame_order_and_audio(clip, tmp_path):
    source, frames = clip
    output = tmp_path / 'upscaled.mkv'
    report_path = process_video(source, output, ReferenceBackend(), work_root=tmp_path / 'runs',
                                chunk_frames=2, max_frames=6, limits=Limits(min_free_disk_bytes=0),
                                upscaler=RepeatAMF(), upscale_factor=2)
    report = read_json(report_path)
    assert report['status'] == 'completed'
    assert report['video']['output_width'] == 64 and report['video']['output_height'] == 48
    assert len(report['chunks']) == 3 and report['audio_payload_sha256']
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(output),
                              '-map', '0:v:0', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
                             capture_output=True, check=True, timeout=15).stdout
    actual = np.frombuffer(decoded, dtype=np.uint8).reshape(6, 48, 64, 3)
    expected = np.repeat(np.repeat(frames, 2, axis=1), 2, axis=2)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.ffmpeg
def test_video_upscale_failure_never_publishes(clip, tmp_path):
    source, _ = clip
    output = tmp_path / 'no-upscaled-output.mkv'
    with pytest.raises(RuntimeError, match='AMF test failure'):
        process_video(source, output, ReferenceBackend(), work_root=tmp_path / 'runs',
                      max_frames=6, limits=Limits(min_free_disk_bytes=0),
                      upscaler=RepeatAMF(fail=True), upscale_factor=2)
    assert not output.exists()
    report = read_json(next((tmp_path / 'runs').glob('video-*/video-manifest.json')))
    assert report['status'] == 'failed'
