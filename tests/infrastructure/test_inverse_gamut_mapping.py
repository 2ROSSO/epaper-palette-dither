"""inverse_gamut_mapping.py のテスト。"""

import numpy as np

from epaper_palette_dither.domain.color import EINK_PALETTE
from epaper_palette_dither.infrastructure.gamut_mapping import (
    _rgb_to_hsl_batch,
    apply_illuminant,
    gamut_map,
)
from epaper_palette_dither.infrastructure.inverse_gamut_mapping import (
    inverse_apply_illuminant,
    inverse_gamut_map,
)


# ---------------------------------------------------------------------------
# inverse_gamut_map（Grayout逆変換）テスト
# ---------------------------------------------------------------------------


class TestInverseGamutMap:
    """inverse_gamut_map のテスト。"""

    def test_output_shape_and_dtype(self) -> None:
        """出力のshape/dtypeが入力と一致。"""
        rgb = np.random.default_rng(42).integers(0, 256, (10, 15, 3), dtype=np.uint8)
        result = inverse_gamut_map(rgb, EINK_PALETTE)
        assert result.shape == (10, 15, 3)
        assert result.dtype == np.uint8

    def test_output_in_valid_range(self) -> None:
        """出力値が0-255範囲内。"""
        rgb = np.random.default_rng(42).integers(0, 256, (20, 30, 3), dtype=np.uint8)
        result = inverse_gamut_map(rgb, EINK_PALETTE)
        assert result.min() >= 0
        assert result.max() <= 255

    def test_strength_zero_identity(self) -> None:
        """strength=0.0で恒等変換。"""
        rgb = np.random.default_rng(42).integers(0, 256, (5, 5, 3), dtype=np.uint8)
        result = inverse_gamut_map(rgb, EINK_PALETTE, strength=0.0)
        np.testing.assert_array_equal(result, rgb)

    def test_roundtrip_in_gamut_colors(self) -> None:
        """in-gamut色（赤系）のroundtrip: gamut_map → inverse ≈ identity。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 0] = 180
        rgb[:, :, 1] = 80
        rgb[:, :, 2] = 20

        strength = 0.7
        mapped = gamut_map(rgb, EINK_PALETTE, strength=strength)
        restored = inverse_gamut_map(mapped, EINK_PALETTE, strength=strength)

        diff = np.abs(restored.astype(int) - rgb.astype(int))
        assert diff.max() <= 5, f"roundtrip誤差が大きい: max_diff={diff.max()}"

    def test_white_unchanged(self) -> None:
        """白はそのまま。"""
        rgb = np.full((2, 2, 3), 255, dtype=np.uint8)
        result = inverse_gamut_map(rgb, EINK_PALETTE)
        np.testing.assert_array_equal(result, rgb)

    def test_black_unchanged(self) -> None:
        """黒はそのまま。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        result = inverse_gamut_map(rgb, EINK_PALETTE)
        np.testing.assert_array_equal(result, rgb)

    def test_grey_unchanged(self) -> None:
        """グレー（無彩色）はそのまま。"""
        rgb = np.full((2, 2, 3), 128, dtype=np.uint8)
        result = inverse_gamut_map(rgb, EINK_PALETTE)
        diff = np.abs(result.astype(int) - rgb.astype(int))
        assert diff.max() <= 1

    def test_saturation_restored(self) -> None:
        """脱彩度化された色の彩度が復元される。"""
        rgb_original = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb_original[:, :, 1] = 150
        rgb_original[:, :, 2] = 100

        strength = 0.5
        mapped = gamut_map(rgb_original, EINK_PALETTE, strength=strength)
        restored = inverse_gamut_map(mapped, EINK_PALETTE, strength=strength)

        hsl_mapped = _rgb_to_hsl_batch(mapped)
        hsl_restored = _rgb_to_hsl_batch(restored)
        assert hsl_restored[0, 0, 1] >= hsl_mapped[0, 0, 1]


# ---------------------------------------------------------------------------
# inverse_apply_illuminant（Illuminant逆変換）テスト
# ---------------------------------------------------------------------------


class TestInverseApplyIlluminant:
    """inverse_apply_illuminant のテスト。"""

    def test_output_shape_and_dtype(self) -> None:
        """出力のshape/dtypeが入力と一致。"""
        rgb = np.random.default_rng(42).integers(0, 256, (10, 15, 3), dtype=np.uint8)
        result = inverse_apply_illuminant(rgb)
        assert result.shape == (10, 15, 3)
        assert result.dtype == np.uint8

    def test_output_in_valid_range(self) -> None:
        """出力値が0-255範囲内。"""
        rgb = np.random.default_rng(42).integers(0, 256, (20, 30, 3), dtype=np.uint8)
        result = inverse_apply_illuminant(rgb)
        assert result.min() >= 0
        assert result.max() <= 255

    def test_identity_scales_roundtrip(self) -> None:
        """スケール (1,1,1) で恒等変換。"""
        rgb = np.random.default_rng(42).integers(0, 256, (5, 5, 3), dtype=np.uint8)
        result = inverse_apply_illuminant(
            rgb, r_scale=1.0, g_scale=1.0, b_scale=1.0,
        )
        np.testing.assert_array_equal(result, rgb)

    def test_roundtrip_no_white_preserve(self) -> None:
        """apply → inverse ≈ identity (white_preserve=0, 穏やかなスケール)。"""
        rgb = np.random.default_rng(42).integers(50, 200, (5, 5, 3), dtype=np.uint8)
        r_s, g_s, b_s = 1.0, 0.9, 0.8
        illuminated = apply_illuminant(
            rgb, r_scale=r_s, g_scale=g_s, b_scale=b_s, white_preserve=0.0,
        )
        restored = inverse_apply_illuminant(
            illuminated, r_scale=r_s, g_scale=g_s, b_scale=b_s, white_preserve=0.0,
        )
        diff = np.abs(restored.astype(int) - rgb.astype(int))
        assert diff.max() <= 5, f"roundtrip誤差が大きい: max_diff={diff.max()}"

    def test_roundtrip_with_white_preserve(self) -> None:
        """apply → inverse ≈ identity (white_preserve>0)。"""
        rgb = np.random.default_rng(42).integers(50, 200, (5, 5, 3), dtype=np.uint8)
        r_s, g_s, b_s = 1.0, 0.9, 0.8
        wp = 0.5
        illuminated = apply_illuminant(
            rgb, r_scale=r_s, g_scale=g_s, b_scale=b_s, white_preserve=wp,
        )
        restored = inverse_apply_illuminant(
            illuminated, r_scale=r_s, g_scale=g_s, b_scale=b_s, white_preserve=wp,
        )
        diff = np.abs(restored.astype(int) - rgb.astype(int))
        assert diff.max() <= 5, f"roundtrip誤差が大きい: max_diff={diff.max()}"

    def test_roundtrip_default_illuminant(self) -> None:
        """デフォルト Illuminant パラメータ (b_scale=0, wp=1.0) での roundtrip。

        b_scale=0 は B チャンネル情報を喪失するため誤差が大きいが、
        R/G チャンネルは正確に復元される。
        入力を 50-130 に制限し R チャンネルの clip を回避。
        """
        rgb = np.random.default_rng(42).integers(50, 130, (5, 5, 3), dtype=np.uint8)
        # デフォルト: red=1.0, yellow=1.0 → r_scale=2.0, g_scale=1.0, b_scale=0.0
        r_s, g_s, b_s = 2.0, 1.0, 0.0
        wp = 1.0
        illuminated = apply_illuminant(
            rgb, r_scale=r_s, g_scale=g_s, b_scale=b_s, white_preserve=wp,
        )
        restored = inverse_apply_illuminant(
            illuminated, r_scale=r_s, g_scale=g_s, b_scale=b_s, white_preserve=wp,
        )
        # R/G チャンネルは正確に復元
        diff_rg = np.abs(restored[:, :, :2].astype(int) - rgb[:, :, :2].astype(int))
        assert diff_rg.max() <= 5, f"R/G roundtrip誤差が大きい: max_diff={diff_rg.max()}"
        # B チャンネルは情報喪失（b_scale=0）→ ブラー後の値をそのまま保持
        # 順変換でBが潰されるため、復元値は順変換後の値に近く、元の値とは大きく乖離する
        # これは意図的: 青みアーティファクトを防ぐため、精度よりも安全性を優先
        diff_b = np.abs(restored[:, :, 2].astype(int) - rgb[:, :, 2].astype(int))
        assert diff_b.mean() <= 90, f"B平均誤差が大きい: mean_diff={diff_b.mean():.1f}"

    def test_no_blue_explosion(self) -> None:
        """b_scale=0 で逆変換しても青が爆発しないことを確認。

        スケール≈0 のチャンネルは preserve ベースでブレンドされるため、
        暗い入力では output_B に近い値になる。
        """
        # 暖色系の入力（illuminant順変換後に近い色分布）
        rgb = np.array([[[180, 90, 10]]], dtype=np.uint8)
        result = inverse_apply_illuminant(
            rgb, r_scale=2.0, g_scale=1.0, b_scale=0.0, white_preserve=1.0,
        )
        # B チャンネルは入力B + 小マージン以下（preserve ブレンド分）
        assert result[0, 0, 2] <= rgb[0, 0, 2] + 15, (
            f"B={result[0, 0, 2]} が入力B={rgb[0, 0, 2]} を大きく超過"
        )

    def test_no_blue_on_red_pixel(self) -> None:
        """赤ピクセルの逆変換で青みが発生しないことを確認。

        赤(200,0,0) → illuminant順変換 → 逆変換で B が上がらないこと。
        """
        # 純赤のIlluminant順変換結果をシミュレート
        red_input = np.array([[[200, 0, 0]]], dtype=np.uint8)
        illuminated = apply_illuminant(
            red_input, r_scale=2.0, g_scale=1.0, b_scale=0.0, white_preserve=1.0,
        )
        restored = inverse_apply_illuminant(
            illuminated, r_scale=2.0, g_scale=1.0, b_scale=0.0, white_preserve=1.0,
        )
        # B チャンネルはほぼ 0 のまま（青みなし、preserve ブレンド分のマージン）
        assert restored[0, 0, 2] <= 15, (
            f"赤ピクセルの復元で B={restored[0, 0, 2]} が発生（青み）"
        )

    def test_black_unchanged(self) -> None:
        """黒はそのまま。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        result = inverse_apply_illuminant(rgb)
        diff = np.abs(result.astype(int) - rgb.astype(int))
        assert diff.max() <= 1
