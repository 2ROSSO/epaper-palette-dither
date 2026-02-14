"""画像品質メトリクス。

PSNR, SSIM, Lab ΔE, Histogram Correlation, S-CIELAB の5指標と複合スコア。
外部依存なし（NumPyのみ）。
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from epaper_palette_dither.infrastructure.color_space import (
    rgb_to_lab_batch,
    srgb_to_linear_batch,
)


def compute_psnr(
    original: npt.NDArray[np.uint8],
    reconstructed: npt.NDArray[np.uint8],
) -> float:
    """Peak Signal-to-Noise Ratio を算出。

    Args:
        original: (H, W, 3) uint8
        reconstructed: (H, W, 3) uint8

    Returns:
        PSNR [dB]。同一画像の場合は float('inf')。
    """
    mse = float(np.mean((original.astype(np.float64) - reconstructed.astype(np.float64)) ** 2))
    if mse < 1e-10:
        return float("inf")
    return 10.0 * np.log10(255.0 ** 2 / mse)


def _box_filter_2d(img: npt.NDArray[np.float64], size: int) -> npt.NDArray[np.float64]:
    """cumsum ベースの box filter（2D、単チャンネル）。

    Args:
        img: (H, W) float64
        size: フィルタサイズ（奇数）

    Returns:
        フィルタ適用後の (H, W) float64
    """
    half = size // 2
    h, w = img.shape

    # パディング（edge）
    padded = np.pad(img, half, mode="edge")

    # 水平方向 cumsum
    cs = np.cumsum(padded, axis=1)
    horiz = cs[:, size:] - cs[:, :-size]

    # 垂直方向 cumsum
    cs = np.cumsum(horiz, axis=0)
    result = cs[size:, :] - cs[:-size, :]

    return result / (size * size)


def compute_ssim(
    original: npt.NDArray[np.uint8],
    reconstructed: npt.NDArray[np.uint8],
    window_size: int = 7,
) -> float:
    """Structural Similarity Index (SSIM) を算出。

    グレースケール（BT.709輝度）で計算。box filter による簡易実装。

    Args:
        original: (H, W, 3) uint8
        reconstructed: (H, W, 3) uint8
        window_size: ウィンドウサイズ（奇数推奨）

    Returns:
        SSIM 値 (-1〜1)。高いほど良い。
    """
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    # BT.709 輝度でグレースケール化
    x = (
        0.2126 * original[:, :, 0].astype(np.float64)
        + 0.7152 * original[:, :, 1].astype(np.float64)
        + 0.0722 * original[:, :, 2].astype(np.float64)
    )
    y = (
        0.2126 * reconstructed[:, :, 0].astype(np.float64)
        + 0.7152 * reconstructed[:, :, 1].astype(np.float64)
        + 0.0722 * reconstructed[:, :, 2].astype(np.float64)
    )

    mu_x = _box_filter_2d(x, window_size)
    mu_y = _box_filter_2d(y, window_size)

    mu_x_sq = mu_x * mu_x
    mu_y_sq = mu_y * mu_y
    mu_xy = mu_x * mu_y

    sigma_x_sq = _box_filter_2d(x * x, window_size) - mu_x_sq
    sigma_y_sq = _box_filter_2d(y * y, window_size) - mu_y_sq
    sigma_xy = _box_filter_2d(x * y, window_size) - mu_xy

    # clamp negative variance (numerical error)
    sigma_x_sq = np.maximum(sigma_x_sq, 0.0)
    sigma_y_sq = np.maximum(sigma_y_sq, 0.0)

    numerator = (2 * mu_xy + c1) * (2 * sigma_xy + c2)
    denominator = (mu_x_sq + mu_y_sq + c1) * (sigma_x_sq + sigma_y_sq + c2)

    ssim_map = numerator / denominator
    return float(np.mean(ssim_map))


def compute_lab_delta_e_mean(
    original: npt.NDArray[np.uint8],
    reconstructed: npt.NDArray[np.uint8],
) -> float:
    """平均 Lab ΔE（CIE76）を算出。

    Args:
        original: (H, W, 3) uint8
        reconstructed: (H, W, 3) uint8

    Returns:
        平均 ΔE。低いほど良い。
    """
    lab_orig = rgb_to_lab_batch(original)
    lab_recon = rgb_to_lab_batch(reconstructed)
    diff = lab_orig - lab_recon
    delta_e = np.sqrt(np.sum(diff * diff, axis=-1))
    return float(np.mean(delta_e))


def compute_histogram_correlation(
    original: npt.NDArray[np.uint8],
    reconstructed: npt.NDArray[np.uint8],
) -> float:
    """3チャンネル Histogram Correlation の平均を算出。

    Args:
        original: (H, W, 3) uint8
        reconstructed: (H, W, 3) uint8

    Returns:
        相関係数の平均 (-1〜1)。高いほど良い。
    """
    correlations = []
    for ch in range(3):
        h1, _ = np.histogram(original[:, :, ch], bins=256, range=(0, 256))
        h2, _ = np.histogram(reconstructed[:, :, ch], bins=256, range=(0, 256))

        h1 = h1.astype(np.float64)
        h2 = h2.astype(np.float64)

        h1_mean = h1 - np.mean(h1)
        h2_mean = h2 - np.mean(h2)

        num = np.sum(h1_mean * h2_mean)
        den = np.sqrt(np.sum(h1_mean ** 2) * np.sum(h2_mean ** 2))

        if den < 1e-10:
            correlations.append(1.0 if num < 1e-10 else 0.0)
        else:
            correlations.append(float(num / den))

    return float(np.mean(correlations))


# --- S-CIELAB (Zhang & Wandell 1997) ---

# XYZ → Opponent 変換行列 (Poirson-Wandell)
_OPP_FROM_XYZ = np.array([
    [0.2790, 0.7200, -0.1070],
    [-0.4490, 0.2900, -0.0770],
    [0.0860, -0.5900, 0.5010],
], dtype=np.float64)

_XYZ_FROM_OPP = np.linalg.inv(_OPP_FROM_XYZ)

# CSF パラメータ (weight, spread_degrees) — Zhang & Wandell 1997 Table 1
_CSF_A = [(1.00316, 0.02710), (0.10824, 0.13160), (-0.11140, 4.33600)]
_CSF_T = [(0.53067, 0.03920), (0.32921, 0.49400)]
_CSF_D = [(0.48810, 0.05360), (0.37148, 0.38600)]


def _separable_gaussian_2d(
    channel: npt.NDArray[np.float64],
    sigma: float,
) -> npt.NDArray[np.float64]:
    """分離型ガウシアンフィルタ（2D、単チャンネル）。"""
    if sigma < 0.3:
        return channel.copy()
    h, w = channel.shape
    radius = min(int(np.ceil(3.0 * sigma)), max(h, w))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()
    klen = len(kernel)

    # Edge パディング
    padded = np.pad(channel, radius, mode="edge")

    # 水平方向畳み込み → (h+2r, w)
    horiz = np.zeros((h + 2 * radius, w), dtype=np.float64)
    for i in range(klen):
        horiz += kernel[i] * padded[:, i:i + w]

    # 垂直方向畳み込み → (h, w)
    result = np.zeros((h, w), dtype=np.float64)
    for i in range(klen):
        result += kernel[i] * horiz[i:i + h, :]

    return result


def _apply_csf_filter(
    channel: npt.NDArray[np.float64],
    csf_params: list[tuple[float, float]],
    pixels_per_degree: float,
) -> npt.NDArray[np.float64]:
    """CSF sum-of-Gaussians フィルタを適用。"""
    result = np.zeros_like(channel)
    for weight, spread_deg in csf_params:
        sigma = spread_deg * pixels_per_degree
        filtered = _separable_gaussian_2d(channel, sigma)
        result += weight * filtered
    return result


def _rgb_to_xyz_batch(
    rgb_array: npt.NDArray[np.uint8],
) -> npt.NDArray[np.float64]:
    """sRGB uint8 → XYZ float64。"""
    linear = srgb_to_linear_batch(rgb_array)
    r = linear[:, :, 0]
    g = linear[:, :, 1]
    b = linear[:, :, 2]
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    return np.stack([x, y, z], axis=-1)


def _xyz_to_lab_batch(xyz: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """XYZ → Lab (D65白色点)。"""
    xn, yn, zn = 0.95047, 1.0, 1.08883
    xr = xyz[:, :, 0] / xn
    yr = xyz[:, :, 1] / yn
    zr = xyz[:, :, 2] / zn

    delta = 6.0 / 29.0
    delta_sq3 = delta ** 3

    def f(t: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return np.where(t > delta_sq3, np.cbrt(t), t / (3.0 * delta ** 2) + 4.0 / 29.0)

    fx, fy, fz = f(np.maximum(xr, 0.0)), f(np.maximum(yr, 0.0)), f(np.maximum(zr, 0.0))
    l_star = 116.0 * fy - 16.0
    a_star = 500.0 * (fx - fy)
    b_star = 200.0 * (fy - fz)
    return np.stack([l_star, a_star, b_star], axis=-1)


def compute_scielab_delta_e(
    original: npt.NDArray[np.uint8],
    reconstructed: npt.NDArray[np.uint8],
    pixels_per_degree: float = 40.0,
) -> float:
    """S-CIELAB ΔE を算出 (Zhang & Wandell 1997)。

    CSF 空間フィルタを適用後に Lab ΔE を計算。
    ディザリングの高周波色差が知覚的にブラーされ、
    人間の視覚系に近い色差評価が可能。

    Args:
        original: (H, W, 3) uint8
        reconstructed: (H, W, 3) uint8
        pixels_per_degree: 観視条件での角度あたりピクセル数
            E-Ink 4.2" (100 DPI) @ 30cm → ~40 ppd

    Returns:
        平均 S-CIELAB ΔE。低いほど良い。
    """
    # 1. RGB → XYZ
    xyz_orig = _rgb_to_xyz_batch(original)
    xyz_recon = _rgb_to_xyz_batch(reconstructed)

    # 2. XYZ → Opponent
    h, w = original.shape[:2]
    opp_orig = np.tensordot(xyz_orig, _OPP_FROM_XYZ.T, axes=([-1], [0]))
    opp_recon = np.tensordot(xyz_recon, _OPP_FROM_XYZ.T, axes=([-1], [0]))

    # 3. CSF フィルタ適用
    csf_params_list = [_CSF_A, _CSF_T, _CSF_D]
    for ch in range(3):
        opp_orig[:, :, ch] = _apply_csf_filter(
            opp_orig[:, :, ch], csf_params_list[ch], pixels_per_degree,
        )
        opp_recon[:, :, ch] = _apply_csf_filter(
            opp_recon[:, :, ch], csf_params_list[ch], pixels_per_degree,
        )

    # 4. Opponent → XYZ → Lab
    xyz_orig_f = np.tensordot(opp_orig, _XYZ_FROM_OPP.T, axes=([-1], [0]))
    xyz_recon_f = np.tensordot(opp_recon, _XYZ_FROM_OPP.T, axes=([-1], [0]))
    lab_orig = _xyz_to_lab_batch(xyz_orig_f)
    lab_recon = _xyz_to_lab_batch(xyz_recon_f)

    # 5. ΔE (CIE76)
    diff = lab_orig - lab_recon
    delta_e = np.sqrt(np.sum(diff * diff, axis=-1))
    return float(np.mean(delta_e))


def compute_composite_score(
    original: npt.NDArray[np.uint8],
    reconstructed: npt.NDArray[np.uint8],
) -> dict[str, float]:
    """5メトリクスと複合スコアをまとめて算出。

    Returns:
        {"psnr": float, "ssim": float, "lab_de": float,
         "hist_corr": float, "scielab_de": float, "composite": float}
    """
    psnr = compute_psnr(original, reconstructed)
    ssim = compute_ssim(original, reconstructed)
    lab_de = compute_lab_delta_e_mean(original, reconstructed)
    hist_corr = compute_histogram_correlation(original, reconstructed)
    scielab_de = compute_scielab_delta_e(original, reconstructed)

    # 正規化 → 0-1
    psnr_norm = float(np.clip(psnr / 50.0, 0.0, 1.0))
    ssim_norm = float(np.clip(ssim, 0.0, 1.0))
    lab_de_norm = float(np.clip(1.0 - lab_de / 30.0, 0.0, 1.0))
    hist_norm = float(np.clip(hist_corr, 0.0, 1.0))
    scielab_norm = float(np.clip(1.0 - scielab_de / 30.0, 0.0, 1.0))

    composite = (
        0.30 * ssim_norm
        + 0.25 * scielab_norm
        + 0.20 * lab_de_norm
        + 0.15 * psnr_norm
        + 0.10 * hist_norm
    )

    return {
        "psnr": psnr,
        "ssim": ssim,
        "lab_de": lab_de,
        "hist_corr": hist_corr,
        "scielab_de": scielab_de,
        "composite": composite,
    }
