"""image_metrics モジュールのテスト。"""

from __future__ import annotations

import numpy as np
import pytest

from epaper_palette_dither.infrastructure.image_metrics import (
    _separable_gaussian_2d,
    compute_composite_score,
    compute_histogram_correlation,
    compute_lab_delta_e_mean,
    compute_psnr,
    compute_scielab_delta_e,
    compute_ssim,
)


def _make_image(r: int, g: int, b: int, h: int = 32, w: int = 32) -> np.ndarray:
    """単色テスト画像を生成。"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 0] = r
    img[:, :, 1] = g
    img[:, :, 2] = b
    return img


# ============================================================
# PSNR
# ============================================================
class TestComputePsnr:
    def test_identical_images_returns_inf(self) -> None:
        img = _make_image(128, 64, 200)
        assert compute_psnr(img, img) == float("inf")

    def test_different_images_returns_finite(self) -> None:
        a = _make_image(0, 0, 0)
        b = _make_image(255, 255, 255)
        psnr = compute_psnr(a, b)
        # MSE=255^2 → PSNR=0 dB (worst case), which is finite
        assert psnr >= 0.0
        assert psnr < 100.0
        assert psnr != float("inf")

    def test_small_difference_high_psnr(self) -> None:
        a = _make_image(100, 100, 100)
        b = _make_image(101, 100, 100)
        psnr = compute_psnr(a, b)
        # 1bit の差 → 非常に高い PSNR
        assert psnr > 40.0

    def test_large_difference_low_psnr(self) -> None:
        a = _make_image(0, 0, 0)
        b = _make_image(128, 128, 128)
        psnr = compute_psnr(a, b)
        assert psnr < 20.0


# ============================================================
# SSIM
# ============================================================
class TestComputeSsim:
    def test_identical_images_returns_one(self) -> None:
        img = _make_image(100, 150, 200)
        ssim = compute_ssim(img, img)
        assert ssim == pytest.approx(1.0, abs=1e-6)

    def test_different_images_less_than_one(self) -> None:
        a = _make_image(0, 0, 0)
        b = _make_image(255, 255, 255)
        ssim = compute_ssim(a, b)
        assert ssim < 1.0

    def test_similar_images_high_ssim(self) -> None:
        a = _make_image(100, 100, 100)
        b = _make_image(105, 100, 100)
        ssim = compute_ssim(a, b)
        assert ssim > 0.9

    def test_noise_reduces_ssim(self) -> None:
        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
        noise = rng.integers(0, 50, (64, 64, 3), dtype=np.int16)
        b = np.clip(a.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        ssim = compute_ssim(a, b)
        assert 0.0 < ssim < 1.0


# ============================================================
# Lab ΔE
# ============================================================
class TestComputeLabDeltaEMean:
    def test_identical_images_returns_zero(self) -> None:
        img = _make_image(80, 120, 200)
        de = compute_lab_delta_e_mean(img, img)
        assert de == pytest.approx(0.0, abs=1e-6)

    def test_different_images_positive(self) -> None:
        a = _make_image(255, 0, 0)
        b = _make_image(0, 0, 255)
        de = compute_lab_delta_e_mean(a, b)
        assert de > 0.0

    def test_small_difference_small_delta_e(self) -> None:
        a = _make_image(100, 100, 100)
        b = _make_image(105, 100, 100)
        de = compute_lab_delta_e_mean(a, b)
        assert de < 5.0

    def test_large_difference_large_delta_e(self) -> None:
        a = _make_image(0, 0, 0)
        b = _make_image(255, 255, 255)
        de = compute_lab_delta_e_mean(a, b)
        assert de > 50.0


# ============================================================
# Histogram Correlation
# ============================================================
class TestComputeHistogramCorrelation:
    def test_identical_images_returns_one(self) -> None:
        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        corr = compute_histogram_correlation(img, img)
        assert corr == pytest.approx(1.0, abs=1e-6)

    def test_solid_color_self_correlation(self) -> None:
        img = _make_image(128, 128, 128)
        # 単色同士: 分散0でゼロ除算保護 → 1.0
        corr = compute_histogram_correlation(img, img)
        assert corr == pytest.approx(1.0, abs=1e-6)

    def test_different_images_less_than_one(self) -> None:
        rng = np.random.default_rng(42)
        a = rng.integers(0, 128, (32, 32, 3), dtype=np.uint8)
        b = rng.integers(128, 256, (32, 32, 3), dtype=np.uint8)
        corr = compute_histogram_correlation(a, b)
        assert corr < 1.0


# ============================================================
# Composite Score
# ============================================================
# ============================================================
# S-CIELAB ΔE
# ============================================================
class TestSeparableGaussian2d:
    def test_identity_for_tiny_sigma(self) -> None:
        """sigma < 0.3 では入力がそのまま返る。"""
        img = np.random.default_rng(42).standard_normal((10, 10))
        result = _separable_gaussian_2d(img, 0.1)
        np.testing.assert_array_equal(result, img)

    def test_output_shape_matches_input(self) -> None:
        img = np.random.default_rng(42).standard_normal((20, 30))
        result = _separable_gaussian_2d(img, 2.0)
        assert result.shape == img.shape

    def test_uniform_image_unchanged(self) -> None:
        """均一画像は Gaussian blur で変化しない。"""
        img = np.full((16, 16), 42.0, dtype=np.float64)
        result = _separable_gaussian_2d(img, 3.0)
        np.testing.assert_allclose(result, img, atol=1e-10)

    def test_smoothing_reduces_variance(self) -> None:
        """ブラーで分散が減少する。"""
        rng = np.random.default_rng(42)
        img = rng.standard_normal((32, 32))
        result = _separable_gaussian_2d(img, 3.0)
        assert np.var(result) < np.var(img)


class TestComputeScielabDeltaE:
    def test_identical_images_returns_zero(self) -> None:
        img = _make_image(128, 64, 200)
        de = compute_scielab_delta_e(img, img)
        assert de == pytest.approx(0.0, abs=1e-4)

    def test_different_images_positive(self) -> None:
        a = _make_image(255, 0, 0)
        b = _make_image(0, 0, 255)
        de = compute_scielab_delta_e(a, b)
        assert de > 0.0

    def test_uniform_solid_in_reasonable_range(self) -> None:
        """均一色同士の S-CIELAB ΔE は妥当な範囲。"""
        a = _make_image(0, 0, 0)
        b = _make_image(255, 255, 255)
        scielab_de = compute_scielab_delta_e(a, b)
        # 黒白の差は大きい (Lab ΔE ~100)
        assert 50.0 < scielab_de < 150.0

    def test_dithered_pattern_lower_scielab(self) -> None:
        """ディザパターンは S-CIELAB で Lab ΔE より低い値を示す。"""
        # 市松模様（高周波ディザ）
        h, w = 32, 32
        checker = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                if (x + y) % 2 == 0:
                    checker[y, x] = [255, 255, 255]
                else:
                    checker[y, x] = [0, 0, 0]
        # 比較対象: 灰色均一画像
        gray = _make_image(128, 128, 128, h, w)

        lab_de = compute_lab_delta_e_mean(gray, checker)
        scielab_de = compute_scielab_delta_e(gray, checker)
        # ディザパターンは空間ブラーで灰色に近づくので S-CIELAB ΔE < Lab ΔE
        assert scielab_de < lab_de

    def test_high_ppd_stronger_blur(self) -> None:
        """高 ppd ではピクセルが小さくCSFブラーがより多くのピクセルを覆う → ΔE低下。"""
        h, w = 32, 32
        checker = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                if (x + y) % 2 == 0:
                    checker[y, x] = [255, 255, 255]
                else:
                    checker[y, x] = [0, 0, 0]
        gray = _make_image(128, 128, 128, h, w)

        de_high_ppd = compute_scielab_delta_e(gray, checker, pixels_per_degree=80.0)
        de_low_ppd = compute_scielab_delta_e(gray, checker, pixels_per_degree=20.0)
        # 高 ppd = 大きい sigma → 強いブラー → ΔE が小さい
        assert de_high_ppd < de_low_ppd


class TestComputeCompositeScore:
    def test_identical_images_perfect_score(self) -> None:
        img = _make_image(100, 150, 200)
        result = compute_composite_score(img, img)
        assert "psnr" in result
        assert "ssim" in result
        assert "lab_de" in result
        assert "hist_corr" in result
        assert "scielab_de" in result
        assert "composite" in result
        # 全指標が完璧 → composite = 0.30+0.25+0.20+0.15+0.10 = 1.0
        assert result["composite"] == pytest.approx(1.0, abs=1e-6)

    def test_composite_range(self) -> None:
        rng = np.random.default_rng(42)
        a = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        b = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        result = compute_composite_score(a, b)
        assert 0.0 <= result["composite"] <= 1.0

    def test_weights_sum_to_one(self) -> None:
        """重みの合計が 1.0 であることを間接的に検証。"""
        img = _make_image(128, 128, 128)
        result = compute_composite_score(img, img)
        # 全メトリクス完璧 → composite = 0.30+0.25+0.20+0.15+0.10 = 1.0
        assert result["composite"] == pytest.approx(1.0, abs=1e-6)
