import numpy as np
import pytest
from amd_nr.contracts import (Limits, compose, rgba8, spec_for_shape, validate_images,
                              validate_mask, validate_mix)
from amd_nr.errors import ContractError, ResourceError

@pytest.mark.parametrize('shape', [(16, 24, 3), (0, 16, 24, 3), (1, 3, 16, 24), (1, 16, 24, 1),
                                  (1, 16, 24, 2), (1, 16, 24, 5), (1, 1, 1, 1, 3)])
def test_bad_shapes(shape):
    with pytest.raises(ContractError):
        validate_images(np.zeros(shape, np.float32))

@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), -0.001, 1.001])
def test_nonfinite_and_out_of_range(rgb, value):
    rgb[0, 0, 0, 0] = value
    with pytest.raises(ContractError):
        validate_images(rgb)

@pytest.mark.parametrize('dtype', [np.uint8, np.int16, np.bool_])
def test_reject_integer_pixels(dtype):
    with pytest.raises(ContractError):
        validate_images(np.zeros((1, 16, 16, 3), dtype=dtype))

@pytest.mark.parametrize('dtype', [np.float16, np.float32, np.float64])
def test_float_types(rgb, dtype):
    assert validate_images(rgb.astype(dtype)).frames == 2

@pytest.mark.parametrize('mix', [float('nan'), float('inf'), -0.1, 1.1, True, '1', None])
def test_mix_invalid(mix):
    with pytest.raises(ContractError):
        validate_mix(mix)

@pytest.mark.parametrize('mix', [0, 0.3, 1])
def test_mix_valid(mix):
    assert validate_mix(mix) == mix

@pytest.mark.parametrize('kwargs', [{'max_frames': 0}, {'max_edge': -1}, {'max_working_bytes': 0},
                                   {'min_free_disk_bytes': -1}, {'max_frames': True}])
def test_invalid_limits(kwargs):
    with pytest.raises(ContractError):
        Limits(**kwargs)

def test_memory_preflight(rgb):
    with pytest.raises(ResourceError):
        validate_images(rgb, Limits(max_working_bytes=10))
    with pytest.raises(ResourceError):
        validate_images(rgb, Limits(max_frames=1))
    with pytest.raises(ResourceError):
        validate_images(rgb, Limits(max_edge=20))

def test_rounding_bound_and_channel_order(rgb):
    packed = rgba8(rgb)
    assert np.all(packed[..., 3] == 255)
    error = np.abs(packed[..., :3].astype(np.float32) / 255 - rgb)
    assert error.max() <= 0.5 / 255 + 1e-6
    tiny = np.array([[[[1., 0., 0.]]]], dtype=np.float32)
    assert rgba8(tiny).reshape(-1).tolist() == [255, 0, 0, 255]

def test_preserve_float_alpha(rgb):
    alpha = np.random.default_rng(1).random((*rgb.shape[:3], 1), dtype=np.float32)
    image = np.concatenate((rgb, alpha), axis=-1)
    packed = rgba8(image)
    packed[..., :3] = 255
    result = compose(image, packed, 1.)
    np.testing.assert_array_equal(result[..., 3], alpha[..., 0])
    assert np.all(result[..., :3] == 1)

def test_zero_mix_is_exact(rgb):
    np.testing.assert_array_equal(compose(rgb, rgba8(1-rgb), 0), rgb)

@pytest.mark.parametrize('mask_shape', [(16,24), (1,16,24), (2,16,24)])
def test_mask_broadcast(rgb, mask_shape):
    spec = validate_images(rgb)
    mask = validate_mask(np.zeros(mask_shape, np.float32), spec)
    np.testing.assert_array_equal(compose(rgb, rgba8(1-rgb), 1, mask), rgb)

@pytest.mark.parametrize('shape', [(3,16,24), (1,16,25), (2,16,24,1)])
def test_invalid_mask_shape(rgb, shape):
    with pytest.raises(ContractError):
        validate_mask(np.ones(shape, np.float32), validate_images(rgb))

@pytest.mark.parametrize('value', [float('nan'), -0.1, 1.1])
def test_invalid_mask_values(rgb, value):
    with pytest.raises(ContractError):
        validate_mask(np.full((16,24), value, np.float32), validate_images(rgb))

def test_compose_reject_wrong_backend_shape(rgb):
    with pytest.raises(ContractError):
        compose(rgb, np.zeros((2,16,24,3), np.uint8), 1)

def test_noncontiguous_image(rgb):
    view = rgb[:, :, ::-1, :]
    validate_images(view)
    assert rgba8(view).flags.c_contiguous

def test_partial_mask_preserves_excluded_pixels(rgb):
    mask = np.zeros((1,16,24), np.float32)
    mask[:, :, :12] = 1
    out = compose(rgb, rgba8(1-rgb), 1, validate_mask(mask, validate_images(rgb)))
    np.testing.assert_array_equal(out[:, :, 12:, :], rgb[:, :, 12:, :])

@pytest.mark.parametrize('shape', [(True, 16, 24, 3), (1, 16.2, 24, 3), (1, '16', 24, 3)])
def test_shape_requires_actual_integers(shape):
    from amd_nr.contracts import spec_for_shape
    with pytest.raises(ContractError):
        spec_for_shape(shape)
