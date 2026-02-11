"""ディザリング実行ユースケース。

画像のディザリング変換を実行するサービス。
DI でアルゴリズムを注入可能。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import numpy.typing as npt

from epaper_palette_dither.domain.color import (
    EINK_PALETTE,
    RGB,
    find_nearest_color,
    find_nearest_color_index,
    rgb_to_lab,
)
from epaper_palette_dither.domain.dithering import DitherAlgorithm, FloydSteinbergDither


class DitherService:
    """ディザリングサービス。NumPyベースの高速処理。"""

    def __init__(self, algorithm: DitherAlgorithm | None = None) -> None:
        self._algorithm = algorithm or FloydSteinbergDither()

    def dither_array(
        self,
        rgb_array: npt.NDArray[np.uint8],
        palette: Sequence[RGB] = EINK_PALETTE,
        error_clamp: int = 0,
        red_penalty: float = 0.0,
        yellow_penalty: float = 0.0,
    ) -> npt.NDArray[np.uint8]:
        """NumPy配列に対してディザリングを実行。

        Args:
            rgb_array: (H, W, 3) の uint8 配列
            palette: 使用するカラーパレット
            error_clamp: 誤差拡散クランプ値 (0=無効)
            red_penalty: 赤ペナルティ係数 (0=無効)
            yellow_penalty: 黄ペナルティ係数 (0=無効)

        Returns:
            ディザリング済みの (H, W, 3) uint8 配列
        """
        h, w = rgb_array.shape[:2]

        # NumPy配列 → Pure Pythonリスト（domain層のインターフェース）
        pixels: list[list[tuple[int, int, int]]] = [
            [(int(rgb_array[y, x, 0]), int(rgb_array[y, x, 1]), int(rgb_array[y, x, 2]))
             for x in range(w)]
            for y in range(h)
        ]

        result = self._algorithm.dither(pixels, w, h, palette)

        # リスト → NumPy配列
        return np.array(result, dtype=np.uint8)

    def dither_array_fast(
        self,
        rgb_array: npt.NDArray[np.uint8],
        palette: Sequence[RGB] = EINK_PALETTE,
        error_clamp: int = 0,
        red_penalty: float = 0.0,
        yellow_penalty: float = 0.0,
        perceived_palette: Sequence[RGB] | None = None,
    ) -> npt.NDArray[np.uint8]:
        """NumPyベースの高速Floyd-Steinbergディザリング。

        domain層のPure Python実装をバイパスし、
        NumPyで直接処理することで大幅に高速化。

        Args:
            rgb_array: (H, W, 3) の uint8 配列
            palette: 使用するカラーパレット（出力値）
            error_clamp: 誤差拡散クランプ値 (0=無効, 値が小さいほど強い抑制)
            red_penalty: 明部での赤ペナルティ係数 (0=無効, CIEDE2000距離に加算)
            yellow_penalty: 暗部での黄ペナルティ係数 (0=無効, CIEDE2000距離に加算)
            perceived_palette: 知覚パレット。指定時は距離計算・誤差計算を知覚値で行う

        Returns:
            ディザリング済みの (H, W, 3) uint8 配列
        """
        h, w = rgb_array.shape[:2]
        work = rgb_array.astype(np.float64)

        # パレットのLAB値を事前計算
        palette_rgb = np.array([c.to_tuple() for c in palette], dtype=np.float64)
        palette_lab = np.array([
            (lab := rgb_to_lab(c), (lab.l, lab.a, lab.b))[1]
            for c in palette
        ])

        # 知覚パレットのRGB値を事前計算（誤差計算用）
        if perceived_palette is not None:
            perceived_rgb = np.array(
                [c.to_tuple() for c in perceived_palette], dtype=np.float64,
            )

        for y in range(h):
            for x in range(w):
                old = work[y, x].copy()
                clamped = RGB(
                    max(0, min(255, round(old[0]))),
                    max(0, min(255, round(old[1]))),
                    max(0, min(255, round(old[2]))),
                )

                # 最近傍インデックスを取得
                if red_penalty > 0.0 or yellow_penalty > 0.0:
                    brightness = max(0.0, min(1.0, (
                        0.2126 * clamped.r + 0.7152 * clamped.g + 0.0722 * clamped.b
                    ) / 255.0))
                    idx = find_nearest_color_index(
                        clamped, palette, red_penalty, yellow_penalty,
                        brightness, perceived_palette,
                    )
                else:
                    idx = find_nearest_color_index(
                        clamped, palette, perceived_palette=perceived_palette,
                    )

                # 出力: ハードウェアパレット色
                new = palette_rgb[idx]
                work[y, x] = new

                # 誤差: 知覚パレット指定時は知覚値で計算
                if perceived_palette is not None:
                    err = old - perceived_rgb[idx]
                else:
                    err = old - new

                # Error Clamping
                if error_clamp > 0:
                    err = np.clip(err, -error_clamp, error_clamp)

                # Floyd-Steinberg エラー拡散
                if x + 1 < w:
                    work[y, x + 1] += err * 7.0 / 16.0
                if y + 1 < h:
                    if x - 1 >= 0:
                        work[y + 1, x - 1] += err * 3.0 / 16.0
                    work[y + 1, x] += err * 5.0 / 16.0
                    if x + 1 < w:
                        work[y + 1, x + 1] += err * 1.0 / 16.0

        return np.clip(work + 0.5, 0, 255).astype(np.uint8)
