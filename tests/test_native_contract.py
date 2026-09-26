"""Contract tests use a named test double, not an AMD GPU or a neural renderer."""
import dataclasses
import json
import os
from pathlib import Path
import sys
import numpy as np
import pytest
from amd_nr.backends import NativeBackend, COLOR_ONLY_INI
from amd_nr.contracts import Limits
from amd_nr.errors import (ConfigurationError, ContractError, EvidenceError, ProcessError,
                           RunCancelled, RunTimeout)
from amd_nr.filesystem import read_json, sha256_file
from amd_nr.pipeline import run_images
from amd_nr.process import run_process

HELPER=Path(__file__).parent/'support'/'fake_engine.py'
LIMITS=Limits(min_free_disk_bytes=0)


def runner_for(mode):
    def runner(argv, **kwargs):
        kwargs['env_overrides']={**kwargs.get('env_overrides',{}),'AMD_NR_TEST_MODE':mode}
        return run_process([sys.executable,str(HELPER),*argv[1:]],**kwargs)
    return runner


def test_native_adapter_protocol_not_inference(rgb,native_config,monkeypatch):
    monkeypatch.setattr('amd_nr.backends.platform.system',lambda:'Windows')
    before=os.environ.get('HIP_VISIBLE_DEVICES')
    result=run_images(rgb,NativeBackend(native_config,runner_for('ok')),
                      work_root=native_config.work_root,limits=LIMITS,keep_debug_files=True)
    assert result.report['status']=='completed'
    # This is the fake coordinator's claim, not independent GPU verification.
    assert result.report['evidence']['independent_gpu_verification'] is False
    assert result.report['evidence']['engine_report']['TEST_DOUBLE_NOT_REAL_INFERENCE'] is True
    job=result.report_path.parent
    assert read_json(job/'child-env.json')['hip']=='2'
    assert os.environ.get('HIP_VISIBLE_DEVICES')==before
    assert (job/'dlssnr_on_amd.ini').read_text()==COLOR_ONLY_INI
    assert result.images.shape==rgb.shape
    for name, artifact in native_config.runtime.items():
        assert sha256_file(job/name)==artifact.sha256

@pytest.mark.parametrize('mode', ['missing','wrong_count','false_completed','fake_bool_count','disabled',
                                 'no_jobs','no_neural','error','bad_status','partial','bad_json','truncated'])
def test_reject_false_success_without_fallback(rgb,native_config,monkeypatch,mode):
    monkeypatch.setattr('amd_nr.backends.platform.system',lambda:'Windows')
    with pytest.raises(EvidenceError):
        run_images(rgb,NativeBackend(native_config,runner_for(mode)),
                   work_root=native_config.work_root,limits=LIMITS)
    manifests=list(native_config.work_root.glob('job-*/manifest.json'))
    assert len(manifests)==1
    report=read_json(manifests[0])
    assert report['status']=='failed'
    assert 'reference' not in report['backend']
    assert report['private_payload_cleaned'] is True
    assert not list(manifests[0].parent.glob('*.dll'))
    assert not list(manifests[0].parent.glob('*.rgba'))

def test_process_failure_not_neural_success(rgb,native_config,monkeypatch):
    monkeypatch.setattr('amd_nr.backends.platform.system',lambda:'Windows')
    with pytest.raises(ProcessError):
        run_images(rgb,NativeBackend(native_config,runner_for('exit')),
                   work_root=native_config.work_root,limits=LIMITS)

def test_native_platform_gate(rgb,native_config,monkeypatch):
    monkeypatch.setattr('amd_nr.backends.platform.system',lambda:'Linux')
    with pytest.raises(ConfigurationError,match='Windows'):
        run_images(rgb,NativeBackend(native_config),work_root=native_config.work_root,limits=LIMITS)

def test_changed_engine_pin_rejected_before_job(rgb,native_config):
    native_config.engine.path.write_bytes(b'MZ_CHANGED')
    with pytest.raises(ConfigurationError,match='SHA-256'):
        run_images(rgb,NativeBackend(native_config),work_root=native_config.work_root,limits=LIMITS)
    assert not list(native_config.work_root.glob('job-*'))

def test_native_odd_dimensions_not_resized(native_config,monkeypatch):
    monkeypatch.setattr('amd_nr.backends.platform.system',lambda:'Windows')
    with pytest.raises(ContractError,match='even'):
        run_images(np.zeros((1,17,24,3),np.float32),NativeBackend(native_config),
                   work_root=native_config.work_root,limits=LIMITS)

def test_native_envelope_not_silently_downscaled(rgb,native_config,monkeypatch):
    monkeypatch.setattr('amd_nr.backends.platform.system',lambda:'Windows')
    cfg=dataclasses.replace(native_config,max_width=16)
    with pytest.raises(ContractError,match='envelope'):
        run_images(rgb,NativeBackend(cfg),work_root=cfg.work_root,limits=LIMITS)

def test_cancellation_no_publication(rgb,native_config,monkeypatch):
    monkeypatch.setattr('amd_nr.backends.platform.system',lambda:'Windows')
    calls=0
    def cancel():
        nonlocal calls
        calls+=1
        if calls>=6: raise RunCancelled('test cancel')
    with pytest.raises(RunCancelled):
        run_images(rgb,NativeBackend(native_config,runner_for('sleep')),
                   work_root=native_config.work_root,limits=LIMITS,cancel=cancel)
    report=read_json(next(native_config.work_root.glob('job-*/manifest.json')))
    assert report['status']=='cancelled'
