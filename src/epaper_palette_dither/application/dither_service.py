"""ディザリング実行ユースケース。

画像のディザリング変換を実行するサービス。
DI でアルゴリズムを注入可能。
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import numpy.typing as npt

from epaper_palette_dither.domain.color import EINK_PALETTE, RGB, find_nearest_color, rgb_to_lab
from epaper_palette_dither.domain.dithering import DitherAlgorithm, FloydSteinbergDither


# --- sRGB → Lab インライン変換用定数 ---
_SRGB_TO_LINEAR_LUT = np.empty(256, dtype=np.float64)
for _i in range(256):
    _v = _i / 255.0
    _SRGB_TO_LINEAR_LUT[_i] = _v / 12.92 if _v <= 0.04045 else ((_v + 0.055) / 1.055) ** 2.4

_LAB_DELTA = 6.0 / 29.0
_LAB_DELTA_SQ3 = _LAB_DELTA ** 3
_LAB_DELTA_SQ3_INV = 1.0 / (3.0 * _LAB_DELTA ** 2)
_LAB_OFFSET = 4.0 / 29.0

# D65 白色点の逆数
_XN_INV = 1.0 / 0.95047
_ZN_INV = 1.0 / 1.08883


def _rgb_to_lab_inline(r: int, g: int, b: int) -> tuple[float, float, float]:
    """RGB(0-255) → Lab をインライン計算。オブジェクト生成なし。"""
    r_lin = _SRGB_TO_LINEAR_LUT[r]
    g_lin = _SRGB_TO_LINEAR_LUT[g]
    b_lin = _SRGB_TO_LINEAR_LUT[b]

    # リニアRGB → XYZ (D65)
    xr = (0.4124564 * r_lin + 0.3575761 * g_lin + 0.1804375 * b_lin) * _XN_INV
    yr = 0.2126729 * r_lin + 0.7151522 * g_lin + 0.0721750 * b_lin
    zr = (0.0193339 * r_lin + 0.1191920 * g_lin + 0.9503041 * b_lin) * _ZN_INV

    # Lab f() 関数
    fx = xr ** (1.0 / 3.0) if xr > _LAB_DELTA_SQ3 else xr * _LAB_DELTA_SQ3_INV + _LAB_OFFSET
    fy = yr ** (1.0 / 3.0) if yr > _LAB_DELTA_SQ3 else yr * _LAB_DELTA_SQ3_INV + _LAB_OFFSET
    fz = zr ** (1.0 / 3.0) if zr > _LAB_DELTA_SQ3 else zr * _LAB_DELTA_SQ3_INV + _LAB_OFFSET

    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _precompute_palette_lab(
    palette: Sequence[RGB],
) -> tuple[list[tuple[int, int, int]], list[tuple[float, float, float]]]:
    """パレットのRGBタプルとLabタプルを事前計算。"""
    pal_rgb = [(c.r, c.g, c.b) for c in palette]
    pal_lab = [_rgb_to_lab_inline(c.r, c.g, c.b) for c in palette]
    return pal_rgb, pal_lab


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
        csf_chroma_weight: float = 1.0,
    ) -> npt.NDArray[np.uint8]:
        """NumPyベースの高速Floyd-Steinbergディザリング。

        domain層のPure Python実装をバイパスし、
        NumPyで直接処理することで大幅に高速化。
        Lab Euclidean距離による最近色検索 + LUTキャッシュ。

        Args:
            rgb_array: (H, W, 3) の uint8 配列
            palette: 使用するカラーパレット
            error_clamp: 誤差拡散クランプ値 (0=無効, 値が小さいほど強い抑制)
            red_penalty: 明部での赤ペナルティ係数 (0=無効, Lab距離に加算)
            yellow_penalty: 暗部での黄ペナルティ係数 (0=無効, Lab距離に加算)
            csf_chroma_weight: 色差チャンネル減衰 (0.0=輝度のみ, 1.0=従来通り)

        Returns:
            ディザリング済みの (H, W, 3) uint8 配列
        """
        from epaper_palette_dither.infrastructure.dither_lut import build_lut

        h, w = rgb_array.shape[:2]
        work = rgb_array.astype(np.float64)

        # パレット事前計算
        pal_rgb, pal_lab = _precompute_palette_lab(palette)
        n_pal = len(pal_rgb)

        # ペナルティ判定用: 赤パレット・黄パレットのインデックス
        use_penalty = red_penalty > 0.0 or yellow_penalty > 0.0
        red_idx = [
            i for i, c in enumerate(pal_rgb)
            if c[0] > 150 and c[1] < 50 and c[2] < 50
        ]
        yellow_idx = [
            i for i, c in enumerate(pal_rgb)
            if c[0] > 200 and c[1] > 200 and c[2] < 50
        ]

        # LUT構築（ペナルティなし用）
        lut = build_lut(palette)

        # ペナルティなし + error_clamp=0 の最速パス用にパレットRGB配列を準備
        pal_rgb_arr = np.array(pal_rgb, dtype=np.float64)

        # ローカル変数キャッシュ（ループ高速化）
        _round = round
        _max = max
        _min = min
        _sqrt = math.sqrt
        srgb_lut = _SRGB_TO_LINEAR_LUT
        lab_delta_sq3 = _LAB_DELTA_SQ3
        lab_delta_sq3_inv = _LAB_DELTA_SQ3_INV
        lab_offset = _LAB_OFFSET
        xn_inv = _XN_INV
        zn_inv = _ZN_INV

        ec = error_clamp
        neg_ec = -error_clamp

        # CSF チャンネル重み付け用定数 (BT.709 opponent 色空間)
        # 順変換: L = Wr*R + Wg*G + Wb*B, C1 = R-G, C2 = 0.5*(R+G)-B
        # 逆変換: 連立方程式から導出
        use_csf = csf_chroma_weight < 1.0
        _Wr = 0.2126
        _Wg = 0.7152
        _Wb = 0.0722
        _inv_r_c1 = _Wg + 0.5 * _Wb    # 0.7513
        _inv_g_c1 = -(_Wr + 0.5 * _Wb)  # -0.2487
        _inv_b_c1 = 0.5 * (1.0 - _Wb) - _Wr  # 0.2513
        _inv_rg_c2 = _Wb                # 0.0722
        _inv_b_c2 = -(_Wr + _Wg)        # -0.9278
        csf_w = csf_chroma_weight

        for y in range(h):
            row = work[y]
            next_row = work[y + 1] if y + 1 < h else None
            for x in range(w):
                old_r = row[x, 0]
                old_g = row[x, 1]
                old_b = row[x, 2]

                # クランプ (float → int)
                ri = _max(0, _min(255, _round(old_r)))
                gi = _max(0, _min(255, _round(old_g)))
                bi = _max(0, _min(255, _round(old_b)))

                if use_penalty:
                    # ペナルティあり: Lab Euclidean + ペナルティ
                    brightness = _max(0.0, _min(1.0, (
                        0.2126 * ri + 0.7152 * gi + 0.0722 * bi
                    ) / 255.0))

                    # インラインrgb_to_lab
                    r_lin = srgb_lut[ri]
                    g_lin = srgb_lut[gi]
                    b_lin = srgb_lut[bi]
                    xr = (0.4124564 * r_lin + 0.3575761 * g_lin + 0.1804375 * b_lin) * xn_inv
                    yr = 0.2126729 * r_lin + 0.7151522 * g_lin + 0.0721750 * b_lin
                    zr = (0.0193339 * r_lin + 0.1191920 * g_lin + 0.9503041 * b_lin) * zn_inv
                    fx = xr ** (1.0 / 3.0) if xr > lab_delta_sq3 else xr * lab_delta_sq3_inv + lab_offset
                    fy = yr ** (1.0 / 3.0) if yr > lab_delta_sq3 else yr * lab_delta_sq3_inv + lab_offset
                    fz = zr ** (1.0 / 3.0) if zr > lab_delta_sq3 else zr * lab_delta_sq3_inv + lab_offset
                    pL = 116.0 * fy - 16.0
                    pa = 500.0 * (fx - fy)
                    pb = 200.0 * (fy - fz)

                    best_idx = 0
                    best_dist = float("inf")
                    for i in range(n_pal):
                        cL, ca, cb = pal_lab[i]
                        dL = pL - cL
                        da = pa - ca
                        db = pb - cb
                        dist_sq = dL * dL + da * da + db * db
                        # ペナルティ加算: sqrt必要
                        dist = _sqrt(dist_sq)
                        if i in red_idx:
                            dist += red_penalty * brightness
                        if i in yellow_idx:
                            dist += yellow_penalty * (1.0 - brightness)
                        if dist < best_dist:
                            best_dist = dist
                            best_idx = i

                    nr, ng, nb = pal_rgb[best_idx]
                else:
                    # ペナルティなし: LUT検索 (O(1))
                    idx = lut[ri >> 2, gi >> 2, bi >> 2]
                    nr, ng, nb = pal_rgb[idx]

                new_r = float(nr)
                new_g = float(ng)
                new_b = float(nb)
                row[x, 0] = new_r
                row[x, 1] = new_g
                row[x, 2] = new_b

                # 誤差計算
                err_r = old_r - new_r
                err_g = old_g - new_g
                err_b = old_b - new_b

                # Error Clamping
                if ec > 0:
                    if err_r > ec:
                        err_r = ec
                    elif err_r < neg_ec:
                        err_r = neg_ec
                    if err_g > ec:
                        err_g = ec
                    elif err_g < neg_ec:
                        err_g = neg_ec
                    if err_b > ec:
                        err_b = ec
                    elif err_b < neg_ec:
                        err_b = neg_ec

                # CSF チャンネル重み付け: 色差チャンネルを減衰
                if use_csf:
                    # RGB → opponent (luminance, red-green, blue-yellow)
                    err_lum = _Wr * err_r + _Wg * err_g + _Wb * err_b
                    err_rg = err_r - err_g
                    err_by = 0.5 * (err_r + err_g) - err_b

                    # 色差チャンネル減衰
                    err_rg *= csf_w
                    err_by *= csf_w

                    # opponent → RGB 逆変換
                    err_r = err_lum + _inv_r_c1 * err_rg + _inv_rg_c2 * err_by
                    err_g = err_lum + _inv_g_c1 * err_rg + _inv_rg_c2 * err_by
                    err_b = err_lum + _inv_b_c1 * err_rg + _inv_b_c2 * err_by

                # Floyd-Steinberg エラー拡散 (スカラー演算)
                if x + 1 < w:
                    row[x + 1, 0] += err_r * 0.4375
                    row[x + 1, 1] += err_g * 0.4375
                    row[x + 1, 2] += err_b * 0.4375
                if next_row is not None:
                    if x - 1 >= 0:
                        next_row[x - 1, 0] += err_r * 0.1875
                        next_row[x - 1, 1] += err_g * 0.1875
                        next_row[x - 1, 2] += err_b * 0.1875
                    next_row[x, 0] += err_r * 0.3125
                    next_row[x, 1] += err_g * 0.3125
                    next_row[x, 2] += err_b * 0.3125
                    if x + 1 < w:
                        next_row[x + 1, 0] += err_r * 0.0625
                        next_row[x + 1, 1] += err_g * 0.0625
                        next_row[x + 1, 2] += err_b * 0.0625

        return np.clip(work + 0.5, 0, 255).astype(np.uint8)
