from pathlib import Path
import sys

# Works both from a source ZIP and a regular checkout, without pip installation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pytest
from amd_nr.config import Artifact, NativeConfig, RUNTIME_NAMES
from amd_nr.filesystem import sha256_file

@pytest.fixture
def rgb():
    return np.random.default_rng(314159).random((2, 16, 24, 3), dtype=np.float32)

@pytest.fixture
def native_config(tmp_path):
    source = tmp_path / 'trusted assets 日本語'
    source.mkdir()
    engine = source / 'test-engine.exe'
    engine.write_bytes(b'MZ\x00TEST FIXTURE NOT A REAL EXECUTABLE')
    runtime = {}
    for name in RUNTIME_NAMES:
        path = source / name
        path.write_bytes(('TEST FIXTURE ' + name).encode())
        runtime[name] = Artifact(path, sha256_file(path))
    return NativeConfig(Artifact(engine, sha256_file(engine)), runtime,
                        tmp_path / 'work root', '2', timeout_seconds=10, worker_seconds=5)
