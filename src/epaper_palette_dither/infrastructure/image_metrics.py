"""画像品質メトリクス。

PSNR, SSIM, Lab ΔE, Histogram Correlation の4指標と複合スコア。
外部依存なし（NumPyのみ）。
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from epaper_palette_dither.infrastructure.color_space import rgb_to_lab_batch


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


def compute_composite_score(
    original: npt.NDArray[np.uint8],
    reconstructed: npt.NDArray[np.uint8],
) -> dict[str, float]:
    """4メトリクスと複合スコアをまとめて算出。

    Returns:
        {"psnr": float, "ssim": float, "lab_de": float,
         "hist_corr": float, "composite": float}
    """
    psnr = compute_psnr(original, reconstructed)
    ssim = compute_ssim(original, reconstructed)
    lab_de = compute_lab_delta_e_mean(original, reconstructed)
    hist_corr = compute_histogram_correlation(original, reconstructed)

    # 正規化 → 0-1
    psnr_norm = float(np.clip(psnr / 50.0, 0.0, 1.0))
    ssim_norm = float(np.clip(ssim, 0.0, 1.0))
    lab_de_norm = float(np.clip(1.0 - lab_de / 30.0, 0.0, 1.0))
    hist_norm = float(np.clip(hist_corr, 0.0, 1.0))

    composite = (
        0.40 * ssim_norm
        + 0.30 * lab_de_norm
        + 0.20 * psnr_norm
        + 0.10 * hist_norm
    )

    return {
        "psnr": psnr,
        "ssim": ssim,
        "lab_de": lab_de,
        "hist_corr": hist_corr,
        "composite": composite,
    }
