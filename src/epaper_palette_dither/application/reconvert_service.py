"""逆ディザリング（Reconvert）サービス。

ディザリング結果からガウシアンブラー＋逆ガマットマッピングで
元画像の近似復元を行う。
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageFilter

from epaper_palette_dither.domain.color import EINK_PALETTE, RGB
from epaper_palette_dither.domain.image_model import ColorMode
from epaper_palette_dither.infrastructure.color_space import srgb_to_linear_batch
from epaper_palette_dither.infrastructure.inverse_gamut_mapping import (
    inverse_apply_illuminant,
    inverse_gamut_map,
)

ProgressCallback = Callable[[str, float], None]


def _gaussian_blur_float(
    data: npt.NDArray[np.float64],
    radius: int,
) -> npt.NDArray[np.float64]:
    """float64 配列に分離型ガウシアンブラーを適用。

    PIL の GaussianBlur は 8bit モードのみ対応のため、
    リニア空間 float 配列用に NumPy で実装。

    Args:
        data: (H, W, 3) float64 配列
        radius: ブラー半径（≈ sigma）

    Returns:
        ブラー後の (H, W, 3) float64 配列
    """
    if radius <= 0:
        return data.copy()

    sigma = float(radius)
    half = int(2.0 * sigma + 0.5)
    ksize = 2 * half + 1
    x = np.arange(ksize, dtype=np.float64) - half
    kernel = np.exp(-x * x / (2.0 * sigma * sigma))
    kernel /= kernel.sum()

    # 水平方向（edge パディング）
    padded = np.pad(data, ((0, 0), (half, half), (0, 0)), mode="edge")
    horiz = np.zeros_like(data)
    for k in range(ksize):
        horiz += kernel[k] * padded[:, k : k + data.shape[1], :]

    # 垂直方向（edge パディング）
    padded = np.pad(horiz, ((half, half), (0, 0), (0, 0)), mode="edge")
    result = np.zeros_like(data)
    for k in range(ksize):
        result += kernel[k] * padded[k : k + data.shape[0], :, :]

    return result


class ReconvertService:
    """逆ディザリングサービス。"""

    def reconvert_array(
        self,
        dithered: npt.NDArray[np.uint8],
        blur_radius: int,
        color_mode: ColorMode,
        gamut_strength: float = 0.7,
        illuminant_red: float = 1.0,
        illuminant_yellow: float = 1.0,
        illuminant_white: float = 1.0,
        palette: Sequence[RGB] = EINK_PALETTE,
        brightness: float = 1.0,
        progress: ProgressCallback | None = None,
    ) -> npt.NDArray[np.uint8]:
        """ディザリング結果を逆変換して近似復元。

        Step1: ガウシアンブラーで離散的なドットパターンを平滑化
        Step2: 逆ガマットマッピングで色空間を復元

        Args:
            dithered: (H, W, 3) ディザリング済み uint8 配列
            blur_radius: ガウシアンブラー半径
            color_mode: 使用した色変換モード
            gamut_strength: Grayout強度
            illuminant_red: Illuminant Red パラメータ
            illuminant_yellow: Illuminant Yellow パラメータ
            illuminant_white: Illuminant White パラメータ
            palette: カラーパレット
            brightness: 手動明るさ乗数 (1.0=変更なし)
            progress: 進捗コールバック

        Returns:
            復元された (H, W, 3) uint8 配列
        """
        if progress:
            progress("ブラー", 0.1)

        # Step 1: sRGB 空間 Gaussian Blur
        # ディザパターンはsRGB値で元画像を再現するため、sRGBブラーが知覚的に正確
        pil_image = Image.fromarray(dithered, "RGB")
        blurred_pil = pil_image.filter(
            ImageFilter.GaussianBlur(radius=blur_radius),
        )
        blurred = np.array(blurred_pil, dtype=np.uint8)

        # 輝度はリニア空間で算出（BT.709 はリニアRGBに対して正しい係数）
        blurred_linear = srgb_to_linear_batch(blurred)
        blurred_lum = float(np.mean(
            0.2126 * blurred_linear[:, :, 0]
            + 0.7152 * blurred_linear[:, :, 1]
            + 0.0722 * blurred_linear[:, :, 2],
        ))

        if progress:
            progress("逆ガマットマッピング", 0.5)

        # Step 2: 逆ガマットマッピング
        if color_mode == ColorMode.GRAYOUT:
            result = inverse_gamut_map(blurred, palette, gamut_strength)
        elif color_mode == ColorMode.ILLUMINANT:
            r_scale = illuminant_red + illuminant_yellow
            g_scale = illuminant_yellow
            result = inverse_apply_illuminant(
                blurred, r_scale, g_scale, 0.0, illuminant_white,
            )
        else:
            # ANTI_SATURATION / CENTROID_CLIP: 逆変換不可 → ブラーのみ
            result = blurred

        if progress:
            progress("明るさ補正", 0.8)

        # Step 3: 明るさ補正（リニア空間で輝度比較 + 手動乗数）
        effective_brightness = brightness
        result_linear = srgb_to_linear_batch(result)
        result_lum = float(np.mean(
            0.2126 * result_linear[:, :, 0]
            + 0.7152 * result_linear[:, :, 1]
            + 0.0722 * result_linear[:, :, 2],
        ))
        if result_lum > 1e-6 and blurred_lum > 1e-6:
            auto_ratio = blurred_lum / result_lum
            auto_ratio = float(np.clip(auto_ratio, 0.5, 2.0))
            effective_brightness *= auto_ratio

        if abs(effective_brightness - 1.0) > 1e-6:
            result = np.clip(
                result.astype(np.float64) * effective_brightness + 0.5,
                0, 255,
            ).astype(np.uint8)

        if progress:
            progress("完了", 1.0)

        return result
