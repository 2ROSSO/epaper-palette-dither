"""lightness_remap モジュールのテスト。"""

from __future__ import annotations

import numpy as np
import pytest

from epaper_palette_dither.infrastructure.lightness_remap import (
    _clahe_channel,
    clahe_lightness,
)


def _make_image(r: int, g: int, b: int, h: int = 32, w: int = 32) -> np.ndarray:
    """単色テスト画像を生成。"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 0] = r
    img[:, :, 1] = g
    img[:, :, 2] = b
    return img


class TestClaheChannel:
    def test_output_shape(self) -> None:
        """出力形状が入力と同じ。"""
        channel = np.random.default_rng(42).uniform(0, 100, (20, 30))
        result = _clahe_channel(channel, 2.0, 4, 0.0, 100.0)
        assert result.shape == channel.shape

    def test_uniform_image_unchanged(self) -> None:
        """均一画像は CLAHE で変化しない。"""
        channel = np.full((16, 16), 50.0, dtype=np.float64)
        result = _clahe_channel(channel, 2.0, 4, 0.0, 100.0)
        # 均一入力 → CDF は単一値 → ヒストグラム均等化で値がシフトする可能性あり
        # ただし全ピクセル同値なので結果も均一
        assert np.ptp(result) < 1.0  # 全ピクセルほぼ同値

    def test_output_in_range(self) -> None:
        """出力が指定範囲内。"""
        rng = np.random.default_rng(42)
        channel = rng.uniform(0, 100, (20, 30))
        result = _clahe_channel(channel, 2.0, 4, 0.0, 100.0)
        assert result.min() >= -1.0  # 数値誤差許容
        assert result.max() <= 101.0

    def test_contrast_enhancement(self) -> None:
        """低コントラスト入力でコントラストが向上する。"""
        rng = np.random.default_rng(42)
        # 狭い範囲 (40-60) に集中した値
        channel = rng.uniform(40, 60, (32, 32))
        result = _clahe_channel(channel, 2.0, 4, 0.0, 100.0)
        # CLAHE でレンジが広がるはず
        assert np.ptp(result) > np.ptp(channel)


class TestClaheLightness:
    def test_output_shape_and_dtype(self) -> None:
        """出力形状と dtype が正しい。"""
        img = np.random.default_rng(42).integers(0, 256, (32, 32, 3), dtype=np.uint8)
        result = clahe_lightness(img)
        assert result.shape == img.shape
        assert result.dtype == np.uint8

    def test_white_image_stays_white(self) -> None:
        """白画像は CLAHE で変化しない。"""
        img = _make_image(255, 255, 255)
        result = clahe_lightness(img)
        # 均一色なので大きな変化なし
        diff = np.abs(img.astype(np.int16) - result.astype(np.int16))
        assert diff.max() <= 2  # 数値誤差許容

    def test_black_image_stays_black(self) -> None:
        """黒画像は CLAHE で変化しない。"""
        img = _make_image(0, 0, 0)
        result = clahe_lightness(img)
        diff = np.abs(img.astype(np.int16) - result.astype(np.int16))
        assert diff.max() <= 2

    def test_clip_limit_1_weak_effect(self) -> None:
        """clip_limit=1.0 で弱い均等化。"""
        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        result = clahe_lightness(img, clip_limit=1.0)
        assert result.shape == img.shape

    def test_clip_limit_4_strong_effect(self) -> None:
        """clip_limit=4.0 で強い均等化。"""
        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        result = clahe_lightness(img, clip_limit=4.0)
        assert result.shape == img.shape

    def test_preserves_hue(self) -> None:
        """CLAHE は明度のみ変更し、色相を保持する。"""
        from epaper_palette_dither.infrastructure.color_space import rgb_to_lab_batch

        rng = np.random.default_rng(42)
        img = rng.integers(50, 200, (16, 16, 3), dtype=np.uint8)
        result = clahe_lightness(img, clip_limit=2.0)

        lab_orig = rgb_to_lab_batch(img)
        lab_result = rgb_to_lab_batch(result)

        # a*, b* はほぼ保持される（L* のみ変更）
        # Lab→RGB→Lab の量子化で微小差が出るため大きめの許容
        a_diff = np.abs(lab_orig[:, :, 1] - lab_result[:, :, 1]).mean()
        b_diff = np.abs(lab_orig[:, :, 2] - lab_result[:, :, 2]).mean()
        assert a_diff < 5.0, f"a* changed too much: {a_diff:.2f}"
        assert b_diff < 5.0, f"b* changed too much: {b_diff:.2f}"

    def test_different_clip_limits_differ(self) -> None:
        """異なる clip_limit で異なる結果。"""
        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        result1 = clahe_lightness(img, clip_limit=1.5)
        result2 = clahe_lightness(img, clip_limit=3.5)
        assert not np.array_equal(result1, result2)


class TestConverterIntegration:
    """ImageConverter との統合テスト。"""

    def test_lightness_remap_property(self) -> None:
        """lightness_remap プロパティ。"""
        from epaper_palette_dither.application.image_converter import ImageConverter

        converter = ImageConverter()
        assert converter.lightness_remap is False
        converter.lightness_remap = True
        assert converter.lightness_remap is True

    def test_lightness_clip_limit_property(self) -> None:
        """lightness_clip_limit プロパティ (1.0-4.0 にクランプ)。"""
        from epaper_palette_dither.application.image_converter import ImageConverter

        converter = ImageConverter()
        assert converter.lightness_clip_limit == 2.0
        converter.lightness_clip_limit = 0.5
        assert converter.lightness_clip_limit == 1.0
        converter.lightness_clip_limit = 5.0
        assert converter.lightness_clip_limit == 4.0
        converter.lightness_clip_limit = 3.0
        assert converter.lightness_clip_limit == 3.0

    def test_disabled_by_default(self) -> None:
        """デフォルトでは CLAHE 無効。"""
        from epaper_palette_dither.application.image_converter import ImageConverter
        from epaper_palette_dither.domain.image_model import ImageSpec

        img = np.random.default_rng(42).integers(0, 256, (32, 32, 3), dtype=np.uint8)
        converter = ImageConverter()
        spec = ImageSpec(target_width=32, target_height=32)

        # lightness_remap=False のデフォルトで変換
        result1 = converter.convert_array(img, spec)

        # 明示的に False 設定
        converter.lightness_remap = False
        result2 = converter.convert_array(img, spec)

        np.testing.assert_array_equal(result1, result2)

    def test_enabled_changes_output(self) -> None:
        """CLAHE 有効時に出力が変わる。"""
        from epaper_palette_dither.application.image_converter import ImageConverter
        from epaper_palette_dither.domain.image_model import ImageSpec

        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        spec = ImageSpec(target_width=32, target_height=32)

        converter = ImageConverter()
        converter.lightness_remap = False
        result_off = converter.convert_array_gamut_only(img, spec)

        converter.lightness_remap = True
        result_on = converter.convert_array_gamut_only(img, spec)

        assert not np.array_equal(result_off, result_on)
