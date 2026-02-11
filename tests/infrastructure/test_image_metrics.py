"""image_metrics モジュールのテスト。"""

from __future__ import annotations

import numpy as np
import pytest

from epaper_palette_dither.infrastructure.image_metrics import (
    compute_composite_score,
    compute_histogram_correlation,
    compute_lab_delta_e_mean,
    compute_psnr,
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
class TestComputeCompositeScore:
    def test_identical_images_perfect_score(self) -> None:
        img = _make_image(100, 150, 200)
        result = compute_composite_score(img, img)
        assert "psnr" in result
        assert "ssim" in result
        assert "lab_de" in result
        assert "hist_corr" in result
        assert "composite" in result
        # SSIM=1, LabDE=0, Hist=1 → composite=0.4+0.3+0.2+0.1=1.0
        # PSNR=inf → clamp(inf/50,0,1)=1.0
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
        # 全メトリクス完璧 → composite = 0.4+0.3+0.2+0.1 = 1.0
        assert result["composite"] == pytest.approx(1.0, abs=1e-6)
