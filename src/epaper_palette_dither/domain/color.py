"""E-Ink 4色パレット定義と色距離計算。

Pure Pythonで実装（外部ライブラリ依存なし）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class RGB:
    """RGB色空間の色。各チャンネル 0-255。"""

    r: int
    g: int
    b: int

    def to_tuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)


@dataclass(frozen=True)
class LAB:
    """CIE L*a*b* 色空間の色。"""

    l: float  # noqa: E741
    a: float
    b: float


# --- E-Ink 4色パレット ---

EINK_WHITE = RGB(255, 255, 255)
EINK_BLACK = RGB(0, 0, 0)
EINK_RED = RGB(200, 0, 0)
EINK_YELLOW = RGB(255, 255, 0)

EINK_PALETTE: tuple[RGB, ...] = (EINK_WHITE, EINK_BLACK, EINK_RED, EINK_YELLOW)

# --- 知覚パレット（e-paper実測値ベース） ---

EINK_WHITE_PERCEIVED = RGB(177, 175, 157)
EINK_BLACK_PERCEIVED = RGB(46, 38, 43)
EINK_RED_PERCEIVED = RGB(177, 51, 37)
EINK_YELLOW_PERCEIVED = RGB(198, 166, 26)

EINK_PALETTE_PERCEIVED: tuple[RGB, ...] = (
    EINK_WHITE_PERCEIVED, EINK_BLACK_PERCEIVED,
    EINK_RED_PERCEIVED, EINK_YELLOW_PERCEIVED,
)


# --- RGB → LAB 変換（Pure Python） ---


def _srgb_to_linear(c: int) -> float:
    """sRGBコンポーネント(0-255)をリニアRGBに変換。"""
    v = c / 255.0
    if v <= 0.04045:
        return v / 12.92
    return ((v + 0.055) / 1.055) ** 2.4


def _lab_f(t: float) -> float:
    """LAB変換の補助関数。"""
    delta = 6.0 / 29.0
    if t > delta**3:
        return t ** (1.0 / 3.0)
    return t / (3.0 * delta**2) + 4.0 / 29.0


def rgb_to_lab(color: RGB) -> LAB:
    """RGB色をCIE L*a*b*に変換。D65光源基準。"""
    # sRGB → リニアRGB
    r_lin = _srgb_to_linear(color.r)
    g_lin = _srgb_to_linear(color.g)
    b_lin = _srgb_to_linear(color.b)

    # リニアRGB → XYZ (D65)
    x = 0.4124564 * r_lin + 0.3575761 * g_lin + 0.1804375 * b_lin
    y = 0.2126729 * r_lin + 0.7151522 * g_lin + 0.0721750 * b_lin
    z = 0.0193339 * r_lin + 0.1191920 * g_lin + 0.9503041 * b_lin

    # D65 白色点
    xn, yn, zn = 0.95047, 1.00000, 1.08883

    # XYZ → L*a*b*
    fx = _lab_f(x / xn)
    fy = _lab_f(y / yn)
    fz = _lab_f(z / zn)

    l_star = 116.0 * fy - 16.0
    a_star = 500.0 * (fx - fy)
    b_star = 200.0 * (fy - fz)

    return LAB(l_star, a_star, b_star)


# --- 色距離計算（CIEDE2000） ---


def ciede2000(lab1: LAB, lab2: LAB) -> float:
    """CIEDE2000色差を計算。

    参考: "The CIEDE2000 Color-Difference Formula" (Sharma et al., 2005)
    """
    l1, a1, b1 = lab1.l, lab1.a, lab1.b
    l2, a2, b2 = lab2.l, lab2.a, lab2.b

    # Step 1: 計算
    c1_ab = math.sqrt(a1**2 + b1**2)
    c2_ab = math.sqrt(a2**2 + b2**2)
    c_ab_mean = (c1_ab + c2_ab) / 2.0

    c_ab_mean_7 = c_ab_mean**7
    g = 0.5 * (1.0 - math.sqrt(c_ab_mean_7 / (c_ab_mean_7 + 25.0**7)))

    a1_prime = a1 * (1.0 + g)
    a2_prime = a2 * (1.0 + g)

    c1_prime = math.sqrt(a1_prime**2 + b1**2)
    c2_prime = math.sqrt(a2_prime**2 + b2**2)

    h1_prime = math.degrees(math.atan2(b1, a1_prime)) % 360.0
    h2_prime = math.degrees(math.atan2(b2, a2_prime)) % 360.0

    # Step 2: Delta値
    delta_l_prime = l2 - l1
    delta_c_prime = c2_prime - c1_prime

    if c1_prime * c2_prime == 0.0:
        delta_h_prime = 0.0
    elif abs(h2_prime - h1_prime) <= 180.0:
        delta_h_prime = h2_prime - h1_prime
    elif h2_prime - h1_prime > 180.0:
        delta_h_prime = h2_prime - h1_prime - 360.0
    else:
        delta_h_prime = h2_prime - h1_prime + 360.0

    delta_H_prime = 2.0 * math.sqrt(c1_prime * c2_prime) * math.sin(
        math.radians(delta_h_prime / 2.0)
    )

    # Step 3: CIEDE2000
    l_prime_mean = (l1 + l2) / 2.0
    c_prime_mean = (c1_prime + c2_prime) / 2.0

    if c1_prime * c2_prime == 0.0:
        h_prime_mean = h1_prime + h2_prime
    elif abs(h1_prime - h2_prime) <= 180.0:
        h_prime_mean = (h1_prime + h2_prime) / 2.0
    elif h1_prime + h2_prime < 360.0:
        h_prime_mean = (h1_prime + h2_prime + 360.0) / 2.0
    else:
        h_prime_mean = (h1_prime + h2_prime - 360.0) / 2.0

    t = (
        1.0
        - 0.17 * math.cos(math.radians(h_prime_mean - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * h_prime_mean))
        + 0.32 * math.cos(math.radians(3.0 * h_prime_mean + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * h_prime_mean - 63.0))
    )

    sl = 1.0 + 0.015 * (l_prime_mean - 50.0) ** 2 / math.sqrt(
        20.0 + (l_prime_mean - 50.0) ** 2
    )
    sc = 1.0 + 0.045 * c_prime_mean
    sh = 1.0 + 0.015 * c_prime_mean * t

    c_prime_mean_7 = c_prime_mean**7
    rc = 2.0 * math.sqrt(c_prime_mean_7 / (c_prime_mean_7 + 25.0**7))
    delta_theta = 30.0 * math.exp(
        -(((h_prime_mean - 275.0) / 25.0) ** 2)
    )
    rt = -math.sin(math.radians(2.0 * delta_theta)) * rc

    return math.sqrt(
        (delta_l_prime / sl) ** 2
        + (delta_c_prime / sc) ** 2
        + (delta_H_prime / sh) ** 2
        + rt * (delta_c_prime / sc) * (delta_H_prime / sh)
    )


def find_nearest_color_index(
    color: RGB,
    palette: Sequence[RGB] = EINK_PALETTE,
    red_penalty: float = 0.0,
    yellow_penalty: float = 0.0,
    brightness: float = 0.0,
    perceived_palette: Sequence[RGB] | None = None,
) -> int:
    """パレットから最も近い色のインデックスをCIEDE2000で検索。

    Args:
        color: 検索対象の色
        palette: 出力用カラーパレット
        red_penalty: 赤パレット色へのペナルティ係数 (0=無効)
        yellow_penalty: 黄パレット色へのペナルティ係数 (0=無効)
        brightness: 正規化輝度 (0.0〜1.0)。ペナルティと組み合わせて使用
        perceived_palette: 知覚パレット。指定時はCIEDE2000距離を知覚値で計算

    Returns:
        最近傍色のインデックス
    """
    lab = rgb_to_lab(color)
    dist_palette = perceived_palette if perceived_palette is not None else palette
    best_idx = 0
    best_dist = float("inf")

    for i, (p, dp) in enumerate(zip(palette, dist_palette)):
        dist = ciede2000(lab, rgb_to_lab(dp))
        # ペナルティ判定は常に出力パレットで行う
        if red_penalty > 0.0 and p.r > 150 and p.g < 50 and p.b < 50:
            dist += red_penalty * brightness
        if yellow_penalty > 0.0 and p.r > 200 and p.g > 200 and p.b < 50:
            dist += yellow_penalty * (1.0 - brightness)
        if dist < best_dist:
            best_dist = dist
            best_idx = i

    return best_idx


def find_nearest_color(
    color: RGB,
    palette: Sequence[RGB] = EINK_PALETTE,
    red_penalty: float = 0.0,
    yellow_penalty: float = 0.0,
    brightness: float = 0.0,
    perceived_palette: Sequence[RGB] | None = None,
) -> RGB:
    """パレットから最も近い色をCIEDE2000で検索。

    Args:
        color: 検索対象の色
        palette: 出力用カラーパレット
        red_penalty: 赤パレット色へのペナルティ係数 (0=無効)
        yellow_penalty: 黄パレット色へのペナルティ係数 (0=無効)
        brightness: 正規化輝度 (0.0〜1.0)。ペナルティと組み合わせて使用
        perceived_palette: 知覚パレット。指定時はCIEDE2000距離を知覚値で計算
    """
    idx = find_nearest_color_index(
        color, palette, red_penalty, yellow_penalty, brightness, perceived_palette,
    )
    return palette[idx]
