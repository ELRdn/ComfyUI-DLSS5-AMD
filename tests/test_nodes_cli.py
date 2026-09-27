import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np
from PIL import Image
import pytest
import torch

from amd_nr import nodes
from amd_nr.cli import load_image, main
from amd_nr.errors import ConfigurationError, ContractError


def test_root_comfy_style_dynamic_import():
    root = Path(__file__).resolve().parents[1]
    name = 'test_comfy_custom_node_package'
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        assert len(module.NODE_CLASS_MAPPINGS) == 9
        assert module.NODE_CLASS_MAPPINGS.keys() == module.NODE_DISPLAY_NAME_MAPPINGS.keys()
    finally:
        for key in list(sys.modules):
            if key == name or key.startswith(name + '.'):
                del sys.modules[key]


def test_node_declared_functions_and_io():
    for cls in nodes.NODE_CLASS_MAPPINGS.values():
        schema = cls.INPUT_TYPES()
        assert isinstance(schema['required'], dict)
        assert isinstance(cls.RETURN_TYPES, tuple)
        assert callable(getattr(cls, cls.FUNCTION))
        assert cls.CATEGORY.startswith('AMD NR/')


def test_roundtrip_tensor_and_compare(rgb, monkeypatch, tmp_path):
    monkeypatch.setattr(nodes.tempfile, 'gettempdir', lambda: str(tmp_path))
    original = torch.from_numpy(rgb)
    result, text = nodes.AMDNRRoundtrip().roundtrip(original)
    assert result.dtype == torch.float32 and result.shape == original.shape
    assert json.loads(text)['evidence']['neural_execution_reported'] is False
    comparison, metrics = nodes.AMDNRCompare().compare(original, result)
    assert comparison.shape == (2, 16, 48, 3)
    assert json.loads(metrics)['max_abs_rgb'] <= .5 / 255 + 1e-6
    np.testing.assert_array_equal(original.numpy(), rgb)


@pytest.mark.parametrize('factor', [1, 2, 4])
def test_bicubic_ordinary_resize(rgb, factor):
    out, = nodes.AMDNRResize().resize(torch.from_numpy(rgb), factor)
    assert out.shape == (2, 16 * factor, 24 * factor, 3)
    assert torch.isfinite(out).all() and out.min() >= 0 and out.max() <= 1


def test_invalid_node_inputs(rgb):
    with pytest.raises(ContractError): nodes._array(np.zeros((1, 16, 16, 3)))
    with pytest.raises(ContractError): nodes._array(torch.zeros((1, 16, 16, 3), dtype=torch.uint8))
    with pytest.raises(ContractError): nodes.AMDNRSettings().create(float('inf'))
    with pytest.raises(ContractError): nodes.AMDNRResize().resize(torch.from_numpy(rgb), True)
    with pytest.raises(ContractError): nodes.AMDNRApply().apply(torch.from_numpy(rgb), {'mix': 1})
    with pytest.raises(ContractError): nodes.AMDNRCompare().compare(torch.from_numpy(rgb), torch.zeros(1, 2, 3, 3))


def test_combined_node_refuses_missing_amf_before_native(rgb, native_config, monkeypatch):
    monkeypatch.setattr(nodes, 'load_native_config', lambda: native_config)
    monkeypatch.setattr(nodes, 'run_images', lambda *args, **kwargs: pytest.fail('NR ran before AMF configuration'))
    with pytest.raises(ConfigurationError, match='AMF VideoSR is not configured'):
        nodes.AMDNRRenderUpscale().apply(torch.from_numpy(rgb[:1]), factor=2)
    with pytest.raises(ContractError, match='integer from 2 to 8'):
        nodes.AMDNRRenderUpscale().apply(torch.from_numpy(rgb[:1]), factor=True)


def test_diagnostics_does_not_execute_native(tmp_path, monkeypatch):
    monkeypatch.setenv('AMD_NR_CONFIG', str(tmp_path / 'missing.json'))
    result = nodes.AMDNRDiagnostics().inspect()
    assert isinstance(result['result'][0], str)
    assert json.loads(result['result'][0])['native_config']['state'] == 'unavailable'


def test_video_node_path_validation(tmp_path, monkeypatch):
    fake = types.ModuleType('folder_paths')
    fake.get_input_directory = lambda: str(tmp_path)
    fake.get_output_directory = lambda: str(tmp_path / 'out')
    monkeypatch.setitem(sys.modules, 'folder_paths', fake)
    for name in ['../outside.mp4', 'https://example.invalid/x.mp4', 'sub\\file.mp4', '/file.mp4']:
        with pytest.raises(ContractError):
            nodes.AMDNRVideoFile().process(name, nodes.NRSettings())


def test_cli_reference_png_and_no_overwrite(tmp_path, capsys):
    image = np.arange(16 * 24 * 4, dtype=np.uint8).reshape(16, 24, 4)
    source = tmp_path / 'input.png'; output = tmp_path / 'output.png'
    Image.fromarray(image).save(source)
    args = ['image', str(source), str(output), '--backend', 'reference', '--work-root', str(tmp_path / 'runs')]
    assert main(args) == 0
    with Image.open(output) as result:
        np.testing.assert_array_equal(np.array(result), image)
        assert json.loads(result.info['AMD_NR_Provenance'])['neural_execution_reported'] is False
    assert main(args) == 2
    assert 'already exists' in capsys.readouterr().err


def test_cli_missing_native_fails_instead_of_cpu(tmp_path, monkeypatch):
    monkeypatch.setenv('AMD_NR_CONFIG', str(tmp_path / 'missing.json'))
    source = tmp_path / 'input.png'
    Image.new('RGB', (16, 16)).save(source)
    output = tmp_path / 'no-result.png'
    assert main(['image', str(source), str(output)]) == 2
    assert not output.exists()


def test_cli_doctor_and_selftest(tmp_path):
    assert main(['doctor', '--output', str(tmp_path / 'doctor.json')]) == 0
    assert main(['selftest', '--output', str(tmp_path / 'selftest')]) == 0
    report = json.loads((tmp_path / 'selftest' / 'selftest.json').read_text())
    assert report['neural_inference_tested'] is False


def test_cli_generates_disabled_config(native_config, tmp_path):
    path = tmp_path / 'config.json'
    assert main(['init-config', '--engine', str(native_config.engine.path),
        '--runtime-dir', str(native_config.engine.path.parent), '--work-root', str(tmp_path / 'runs'),
        '--output', str(path)]) == 0
    config = json.loads(path.read_text())
    assert config['trusted_local_artifacts'] is False
    assert config['hip_device'] is None
    assert config['engine']['sha256'] == native_config.engine.sha256


def test_icc_requires_explicit_conversion(tmp_path):
    source = tmp_path / 'tagged.png'
    Image.new('RGB', (16, 16)).save(source, icc_profile=b'fake-icc-test-fixture')
    with pytest.raises(ContractError): load_image(source)
