"""色空間変換（NumPyベースのバッチ処理）。

RGB↔LAB変換を画像全体に対して高速に実行する。
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def rgb_to_lab_batch(rgb_array: npt.NDArray[np.uint8]) -> npt.NDArray[np.float64]:
    """RGB画像配列をLAB色空間に一括変換。

    Args:
        rgb_array: (H, W, 3) の uint8 配列 (RGB)

    Returns:
        (H, W, 3) の float64 配列 (LAB)
    """
    rgb_float = rgb_array.astype(np.float64) / 255.0

    # sRGB → リニアRGB
    mask = rgb_float <= 0.04045
    linear = np.where(mask, rgb_float / 12.92, ((rgb_float + 0.055) / 1.055) ** 2.4)

    r, g, b = linear[:, :, 0], linear[:, :, 1], linear[:, :, 2]

    # リニアRGB → XYZ (D65)
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b

    # D65 白色点で正規化
    x /= 0.95047
    # y /= 1.00000  (不要)
    z /= 1.08883

    # LAB変換の補助関数
    delta = 6.0 / 29.0
    delta_sq3 = delta**3

    def f(t: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return np.where(t > delta_sq3, np.cbrt(t), t / (3.0 * delta**2) + 4.0 / 29.0)

    fx, fy, fz = f(x), f(y), f(z)

    l_star = 116.0 * fy - 16.0
    a_star = 500.0 * (fx - fy)
    b_star = 200.0 * (fy - fz)

    return np.stack([l_star, a_star, b_star], axis=-1)


def lab_to_rgb_batch(lab_array: npt.NDArray[np.float64]) -> npt.NDArray[np.uint8]:
    """LAB色空間の配列をRGBに一括変換。

    Args:
        lab_array: (H, W, 3) の float64 配列 (LAB)

    Returns:
        (H, W, 3) の uint8 配列 (RGB)
    """
    l_star = lab_array[:, :, 0]
    a_star = lab_array[:, :, 1]
    b_star = lab_array[:, :, 2]

    # LAB → XYZ
    fy = (l_star + 16.0) / 116.0
    fx = a_star / 500.0 + fy
    fz = fy - b_star / 200.0

    delta = 6.0 / 29.0

    def f_inv(t: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return np.where(t > delta, t**3, 3.0 * delta**2 * (t - 4.0 / 29.0))

    x = 0.95047 * f_inv(fx)
    y = 1.00000 * f_inv(fy)
    z = 1.08883 * f_inv(fz)

    # XYZ → リニアRGB
    r_lin = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g_lin = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    b_lin = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z

    # リニアRGB → sRGB
    def to_srgb(c: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        c = np.clip(c, 0.0, 1.0)
        return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1.0 / 2.4) - 0.055)

    rgb_float = np.stack([to_srgb(r_lin), to_srgb(g_lin), to_srgb(b_lin)], axis=-1)
    return np.clip(rgb_float * 255.0 + 0.5, 0, 255).astype(np.uint8)
