import json
from dataclasses import asdict
from pathlib import Path

import pytest
from amd_nr.config import config_fingerprint, load_native_config
from amd_nr.errors import ConfigurationError, ContractError


def payload(config):
    return {'schema': 1, 'trusted_local_artifacts': True,
        'engine': {'path': str(config.engine.path), 'sha256': config.engine.sha256},
        'runtime': {k: {'path': str(v.path), 'sha256': v.sha256} for k, v in config.runtime.items()},
        'work_root': str(config.work_root), 'hip_device': '2', 'timeout_seconds': 10, 'worker_seconds': 5}


def test_config_roundtrip_and_fingerprint(native_config, tmp_path, monkeypatch):
    path = tmp_path / 'backend.json'
    path.write_text(json.dumps(payload(native_config)))
    loaded = load_native_config(path)
    loaded.verify()
    assert loaded.engine == native_config.engine
    monkeypatch.setenv('AMD_NR_CONFIG', str(path))
    before = config_fingerprint()
    native_config.engine.path.write_bytes(b'MZ MODIFIED')
    assert config_fingerprint() != before
    with pytest.raises(ConfigurationError):
        loaded.verify()


@pytest.mark.parametrize('key,value', [
    ('schema', True), ('schema', 2), ('trusted_local_artifacts', False),
    ('hip_device', '0,1'), ('hip_device', 1), ('hip_device', '１'),
    ('amf_expected_device_id', '0x7550'), ('amf_expected_device_id', '755'),
    ('amf_expected_device_id', 'zzzz'), ('amf_expected_device_id', True),
    ('fast_isolated', 'yes'), ('fast_isolated', True),
    ('timeout_seconds', 0), ('timeout_seconds', True), ('worker_seconds', 11),
    ('max_width', 9000), ('work_root', 'relative/path'), ('unknown_option', 1),
    ('engine', {'path': '/anywhere', 'sha256': 'bad'}), ('runtime', {}),
])
def test_invalid_config(native_config, tmp_path, key, value):
    data = payload(native_config)
    data[key] = value
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(data))
    with pytest.raises((ConfigurationError, ContractError)):
        load_native_config(path)


def test_fast_mode_requires_specific_opt_in(native_config, tmp_path):
    data = payload(native_config)
    data.update(fast_isolated=True, fast_mode_verified_for_these_hashes=True)
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(data))
    assert load_native_config(path).fast_isolated


def test_amf_device_id_is_normalized(native_config, tmp_path):
    data = payload(native_config)
    data['amf_expected_device_id'] = 'ABCD'
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(data))
    assert load_native_config(path).amf_expected_device_id == 'abcd'


def test_missing_config_and_no_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv('AMD_NR_CONFIG', str(tmp_path / 'missing.json'))
    assert config_fingerprint() == 'unconfigured'
    with pytest.raises(ConfigurationError):
        load_native_config()


def test_stage_hash_change_rejected(native_config, tmp_path):
    job = tmp_path / 'job'; job.mkdir()
    native_config.engine.path.write_bytes(b'MZ wrong hash')
    with pytest.raises(ConfigurationError):
        native_config.stage(job)
