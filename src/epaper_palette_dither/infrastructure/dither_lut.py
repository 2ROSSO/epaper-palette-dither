"""ディザリング用LUT（ルックアップテーブル）生成。

RGB→パレットインデックスの3D LUTを事前構築し、
ディザリングループ内の最近色検索をO(1)化する。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import numpy.typing as npt

from epaper_palette_dither.domain.color import EINK_PALETTE, RGB
from epaper_palette_dither.infrastructure.color_space import rgb_to_lab_batch

# 量子化ステップ (step=4: 64³ = 262,144エントリ, 最大RGB誤差 sqrt(3)*2 ≈ 3.5)
LUT_STEP = 4
LUT_SIZE = 256 // LUT_STEP  # 64


def build_lut(
    palette: Sequence[RGB] = EINK_PALETTE,
) -> npt.NDArray[np.uint8]:
    """RGB→パレットインデックスの3D LUTを構築。

    Lab Euclidean距離で最近色を決定。ペナルティなし。

    Args:
        palette: カラーパレット

    Returns:
        (64, 64, 64) の uint8 配列。各要素はパレットインデックス。
    """
    # 量子化RGB座標グリッド (64³)
    steps = np.arange(LUT_SIZE, dtype=np.uint8) * LUT_STEP + LUT_STEP // 2
    rr, gg, bb = np.meshgrid(steps, steps, steps, indexing="ij")
    # (64, 64, 64, 3) の RGB配列
    grid_rgb = np.stack([rr, gg, bb], axis=-1)

    # (64, 64, 64, 3) → Lab変換のため (64³, 1, 3) にreshape
    flat_rgb = grid_rgb.reshape(-1, 1, 3)
    flat_lab = rgb_to_lab_batch(flat_rgb)  # (N, 1, 3)
    flat_lab = flat_lab.reshape(-1, 3)  # (N, 3)

    # パレット Lab値 (P, 3)
    pal_rgb_arr = np.array([c.to_tuple() for c in palette], dtype=np.uint8).reshape(1, -1, 3)
    pal_lab = rgb_to_lab_batch(pal_rgb_arr.reshape(-1, 1, 3)).reshape(-1, 3)

    # 距離計算: (N, 1, 3) - (1, P, 3) → (N, P)
    diff = flat_lab[:, np.newaxis, :] - pal_lab[np.newaxis, :, :]
    dist_sq = np.sum(diff ** 2, axis=-1)

    # 最近パレットインデックス
    indices = np.argmin(dist_sq, axis=-1).astype(np.uint8)
    return indices.reshape(LUT_SIZE, LUT_SIZE, LUT_SIZE)
