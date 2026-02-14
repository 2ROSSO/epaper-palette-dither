"""明度リマッピング (CLAHE)。

L* チャンネルに Contrast Limited Adaptive Histogram Equalization を適用し、
パレットの明度範囲を有効活用する。
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from epaper_palette_dither.infrastructure.color_space import lab_to_rgb_batch, rgb_to_lab_batch


def _clahe_channel(
    channel: npt.NDArray[np.float64],
    clip_limit: float,
    grid_size: int,
    value_min: float,
    value_max: float,
    n_bins: int = 256,
) -> npt.NDArray[np.float64]:
    """単チャンネルに対する CLAHE 実装。

    Args:
        channel: (H, W) float64
        clip_limit: コントラスト制限係数 (1.0=弱い, 4.0=強い)
        grid_size: グリッド分割数
        value_min: チャンネルの最小値
        value_max: チャンネルの最大値
        n_bins: ヒストグラムのビン数

    Returns:
        CLAHE 適用後の (H, W) float64
    """
    h, w = channel.shape
    result = np.empty_like(channel)

    # 値を [0, n_bins-1] にスケーリング
    val_range = value_max - value_min
    if val_range < 1e-10:
        return channel.copy()
    scaled = (channel - value_min) / val_range * (n_bins - 1)
    scaled = np.clip(scaled, 0, n_bins - 1)

    # グリッド境界
    row_step = h / grid_size
    col_step = w / grid_size

    # 各グリッドブロックの CDF を事前計算
    cdfs = np.empty((grid_size, grid_size, n_bins), dtype=np.float64)

    for gy in range(grid_size):
        y0 = int(round(gy * row_step))
        y1 = int(round((gy + 1) * row_step))
        y1 = max(y1, y0 + 1)
        for gx in range(grid_size):
            x0 = int(round(gx * col_step))
            x1 = int(round((gx + 1) * col_step))
            x1 = max(x1, x0 + 1)

            block = scaled[y0:y1, x0:x1]
            n_pixels = block.size

            # ヒストグラム
            hist = np.zeros(n_bins, dtype=np.float64)
            indices = np.clip(block.astype(np.int32), 0, n_bins - 1)
            for val in indices.ravel():
                hist[val] += 1.0

            # クリッピング
            actual_clip = clip_limit * n_pixels / n_bins
            excess = 0.0
            for i in range(n_bins):
                if hist[i] > actual_clip:
                    excess += hist[i] - actual_clip
                    hist[i] = actual_clip

            # 超過分を均等再分配
            redistrib = excess / n_bins
            hist += redistrib

            # CDF
            cdf = np.cumsum(hist)
            cdf_min = cdf[cdf > 0].min() if np.any(cdf > 0) else 0.0
            denom = n_pixels - cdf_min
            if denom < 1.0:
                cdfs[gy, gx, :] = np.arange(n_bins, dtype=np.float64)
            else:
                cdfs[gy, gx, :] = (cdf - cdf_min) / denom * (n_bins - 1)

    # バイリニア補間で全ピクセルをリマッピング
    for y in range(h):
        # グリッド中心からの相対位置
        gy_f = (y + 0.5) / row_step - 0.5
        gy0 = int(np.floor(gy_f))
        gy1 = gy0 + 1
        fy = gy_f - gy0
        gy0 = max(0, min(grid_size - 1, gy0))
        gy1 = max(0, min(grid_size - 1, gy1))

        for x in range(w):
            gx_f = (x + 0.5) / col_step - 0.5
            gx0 = int(np.floor(gx_f))
            gx1 = gx0 + 1
            fx = gx_f - gx0
            gx0 = max(0, min(grid_size - 1, gx0))
            gx1 = max(0, min(grid_size - 1, gx1))

            val = scaled[y, x]
            idx = int(np.clip(val, 0, n_bins - 2))
            frac = val - idx

            # 4ブロックの CDF を線形補間
            v00 = cdfs[gy0, gx0, idx] * (1 - frac) + cdfs[gy0, gx0, idx + 1] * frac
            v01 = cdfs[gy0, gx1, idx] * (1 - frac) + cdfs[gy0, gx1, idx + 1] * frac
            v10 = cdfs[gy1, gx0, idx] * (1 - frac) + cdfs[gy1, gx0, idx + 1] * frac
            v11 = cdfs[gy1, gx1, idx] * (1 - frac) + cdfs[gy1, gx1, idx + 1] * frac

            # バイリニア補間
            top = v00 * (1 - fx) + v01 * fx
            bot = v10 * (1 - fx) + v11 * fx
            mapped = top * (1 - fy) + bot * fy

            result[y, x] = mapped / (n_bins - 1) * val_range + value_min

    return result


def clahe_lightness(
    rgb_array: npt.NDArray[np.uint8],
    clip_limit: float = 2.0,
    grid_size: int = 8,
) -> npt.NDArray[np.uint8]:
    """L* チャンネルに CLAHE を適用。

    Args:
        rgb_array: (H, W, 3) uint8 RGB
        clip_limit: コントラスト制限 (1.0=弱い, 4.0=強い)
        grid_size: CLAHE グリッドサイズ

    Returns:
        CLAHE 適用後の (H, W, 3) uint8 RGB
    """
    lab = rgb_to_lab_batch(rgb_array)
    l_star = lab[:, :, 0]

    l_enhanced = _clahe_channel(l_star, clip_limit, grid_size, 0.0, 100.0)
    l_enhanced = np.clip(l_enhanced, 0.0, 100.0)

    lab_enhanced = lab.copy()
    lab_enhanced[:, :, 0] = l_enhanced

    return lab_to_rgb_batch(lab_enhanced)
