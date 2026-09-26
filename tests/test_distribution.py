import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from amd_nr.nodes import NODE_CLASS_MAPPINGS
from amd_nr.config import PIN

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('file', sorted((ROOT / 'workflows').glob('*.json')))
def test_workflow_references_and_node_types(file):
    data = json.loads(file.read_text())
    known = set(NODE_CLASS_MAPPINGS) | {'LoadImage', 'SaveImage'}
    if '.api.' in file.name:
        for node in data.values():
            assert node['class_type'] in known
            if node['class_type'] in NODE_CLASS_MAPPINGS:
                required = NODE_CLASS_MAPPINGS[node['class_type']].INPUT_TYPES()['required']
                assert set(required) <= set(node['inputs'])
            for value in node['inputs'].values():
                if isinstance(value, list):
                    assert value[0] in data and isinstance(value[1], int)
    else:
        nodes = {n['id']: n for n in data['nodes']}
        links = {l[0]: l for l in data['links']}
        assert len(nodes) == len(data['nodes']) and len(links) == len(data['links'])
        for n in nodes.values(): assert n['type'] in known
        for lid, src, srcslot, dst, dstslot, dtype in links.values():
            assert lid in nodes[src]['outputs'][srcslot]['links']
            assert nodes[dst]['inputs'][dstslot]['link'] == lid
            assert nodes[src]['outputs'][srcslot]['type'] == dtype
            assert nodes[dst]['inputs'][dstslot]['type'] == dtype
        for n in nodes.values():
            for inp in n['inputs']:
                if inp['link'] is not None: assert inp['link'] in links


def test_lock_and_git_blob_algorithm():
    lock = json.loads((ROOT / 'upstream.lock.json').read_text())
    assert lock['commit'] == PIN
    assert len(lock['git_blobs']) == 5
    spec = importlib.util.spec_from_file_location('fetch_upstream', ROOT / 'scripts' / 'fetch_upstream.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert module.git_blob_id(b'') == 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'


def test_example_is_disabled_and_no_torch_install():
    assert len(list((ROOT / "workflows").glob("*.json"))) == 6
    data = json.loads((ROOT / 'config' / 'backend.example.json').read_text())
    assert data['trusted_local_artifacts'] is False
    assert data['fast_isolated'] is False
    assert data['hip_device'] is None
    assert all(not line.strip().startswith('torch') for line in (ROOT / 'requirements.txt').read_text().splitlines())
