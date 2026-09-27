from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import amd_nr.amf as amf
from amd_nr.errors import ContractError, EvidenceError, ResourceError


def test_factor_and_output_budget():
    assert amf.output_size(640, 360, 8) == (5120, 2880)
    assert amf.output_size(1920, 1080, 4) == (7680, 4320)
    for factor in (True, 1, 9, 2.0):
        with pytest.raises(ContractError):
            amf.output_size(640, 360, factor)
    with pytest.raises(ResourceError):
        amf.output_size(1920, 1080, 8)


def test_other_amf_gpu_is_rejected(tmp_path, monkeypatch):
    scaler = object.__new__(amf.AMFScaler)
    scaler.artifact = SimpleNamespace(path=tmp_path / 'fake.exe', sha256='0' * 64)
    scaler.cancel = None
    scaler.version = 'fake FFmpeg'
    scaler.expected_device_id = '7550'

    def fake_run(argv, *, log, **kwargs):
        Path(argv[-1]).write_bytes(bytes([127]) * (32 * 32 * 3))
        log.write_text('deviceID=0x164e\nUsing Algorithm VideoSR1.1\n')
        return 0.01

    monkeypatch.setattr(amf, 'run_process', fake_run)
    with pytest.raises(EvidenceError, match='different or unidentified GPU'):
        scaler.scale_rgb8(np.full((1, 16, 16, 3), 127, np.uint8), 2, tmp_path)
    assert not list(tmp_path.rglob('output.rgb'))
