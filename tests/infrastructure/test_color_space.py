"""color_space.py のテスト。"""

import numpy as np

from epaper_palette_dither.infrastructure.color_space import (
    lab_to_rgb_batch,
    linear_to_srgb_batch,
    rgb_to_lab_batch,
    srgb_to_linear_batch,
)


class TestRgbToLabBatch:
    def test_white(self) -> None:
        rgb = np.array([[[255, 255, 255]]], dtype=np.uint8)
        lab = rgb_to_lab_batch(rgb)
        assert abs(lab[0, 0, 0] - 100.0) < 0.5  # L*≈100
        assert abs(lab[0, 0, 1]) < 1.0  # a*≈0
        assert abs(lab[0, 0, 2]) < 1.0  # b*≈0

    def test_black(self) -> None:
        rgb = np.array([[[0, 0, 0]]], dtype=np.uint8)
        lab = rgb_to_lab_batch(rgb)
        assert abs(lab[0, 0, 0]) < 0.5  # L*≈0

    def test_batch_shape(self) -> None:
        rgb = np.zeros((10, 20, 3), dtype=np.uint8)
        lab = rgb_to_lab_batch(rgb)
        assert lab.shape == (10, 20, 3)

    def test_red_has_positive_a(self) -> None:
        rgb = np.array([[[200, 0, 0]]], dtype=np.uint8)
        lab = rgb_to_lab_batch(rgb)
        assert lab[0, 0, 1] > 0  # a*>0 for red


class TestLabToRgbBatch:
    def test_white_roundtrip(self) -> None:
        rgb_orig = np.array([[[255, 255, 255]]], dtype=np.uint8)
        lab = rgb_to_lab_batch(rgb_orig)
        rgb_back = lab_to_rgb_batch(lab)
        np.testing.assert_array_almost_equal(rgb_orig, rgb_back, decimal=0)

    def test_black_roundtrip(self) -> None:
        rgb_orig = np.array([[[0, 0, 0]]], dtype=np.uint8)
        lab = rgb_to_lab_batch(rgb_orig)
        rgb_back = lab_to_rgb_batch(lab)
        np.testing.assert_array_almost_equal(rgb_orig, rgb_back, decimal=0)

    def test_roundtrip_various_colors(self) -> None:
        """様々な色でRGB→LAB→RGBの往復精度を検証。"""
        colors = np.array(
            [
                [[255, 0, 0], [0, 255, 0], [0, 0, 255]],
                [[128, 128, 128], [200, 100, 50], [50, 200, 100]],
            ],
            dtype=np.uint8,
        )
        lab = rgb_to_lab_batch(colors)
        rgb_back = lab_to_rgb_batch(lab)
        # 往復で±1以内の誤差
        diff = np.abs(colors.astype(np.int16) - rgb_back.astype(np.int16))
        assert diff.max() <= 1, f"Max roundtrip error: {diff.max()}"

    def test_batch_shape(self) -> None:
        lab = np.zeros((5, 8, 3), dtype=np.float64)
        lab[:, :, 0] = 50.0  # L*=50
        rgb = lab_to_rgb_batch(lab)
        assert rgb.shape == (5, 8, 3)
        assert rgb.dtype == np.uint8


class TestSrgbToLinearBatch:
    def test_black_white(self) -> None:
        """黒→0.0, 白→1.0。"""
        rgb = np.array([[[0, 0, 0], [255, 255, 255]]], dtype=np.uint8)
        linear = srgb_to_linear_batch(rgb)
        np.testing.assert_allclose(linear[0, 0], [0.0, 0.0, 0.0], atol=1e-10)
        np.testing.assert_allclose(linear[0, 1], [1.0, 1.0, 1.0], atol=1e-6)

    def test_midgray(self) -> None:
        """sRGB 128 → リニア ≈ 0.216。"""
        rgb = np.array([[[128, 128, 128]]], dtype=np.uint8)
        linear = srgb_to_linear_batch(rgb)
        # sRGB 128/255 ≈ 0.502 → リニア ≈ 0.216
        np.testing.assert_allclose(linear[0, 0], [0.216, 0.216, 0.216], atol=0.002)

    def test_output_shape_and_dtype(self) -> None:
        rgb = np.zeros((10, 20, 3), dtype=np.uint8)
        linear = srgb_to_linear_batch(rgb)
        assert linear.shape == (10, 20, 3)
        assert linear.dtype == np.float64


class TestLinearToSrgbBatch:
    def test_roundtrip(self) -> None:
        """sRGB→linear→sRGB で ±1 以内の誤差。"""
        colors = np.array(
            [
                [[0, 0, 0], [255, 255, 255], [128, 128, 128]],
                [[200, 0, 0], [0, 255, 0], [0, 0, 255]],
                [[200, 100, 50], [50, 200, 100], [100, 50, 200]],
            ],
            dtype=np.uint8,
        )
        linear = srgb_to_linear_batch(colors)
        roundtrip = linear_to_srgb_batch(linear)
        diff = np.abs(colors.astype(np.int16) - roundtrip.astype(np.int16))
        assert diff.max() <= 1, f"Max roundtrip error: {diff.max()}"

    def test_clip_out_of_range(self) -> None:
        """範囲外入力（負値, >1.0）が 0-255 にクリップ。"""
        linear = np.array([[[-0.5, 1.5, 0.5]]], dtype=np.float64)
        result = linear_to_srgb_batch(linear)
        assert result[0, 0, 0] == 0    # 負値 → 0
        assert result[0, 0, 1] == 255  # >1.0 → 255
        assert 0 < result[0, 0, 2] < 255  # 正常値

    def test_output_dtype(self) -> None:
        linear = np.array([[[0.5, 0.5, 0.5]]], dtype=np.float64)
        result = linear_to_srgb_batch(linear)
        assert result.dtype == np.uint8
