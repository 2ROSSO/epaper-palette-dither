"""逆ガマットマッピング（Reconvert用）。

ディザリング結果からの復元処理。
Grayout: HSL彩度の逆復元。
Illuminant: チャンネルスケール逆数。
Anti-Saturation / Centroid Clip: 逆変換不可（パススルー）。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import numpy.typing as npt

from epaper_palette_dither.domain.color import RGB
from epaper_palette_dither.infrastructure.gamut_mapping import (
    _DEFAULT_HUE_TOLERANCE,
    _compute_palette_hsl_range,
    _hsl_to_rgb_batch,
    _hue_clip,
    _hue_diff,
    _rgb_to_hsl_batch,
)


def inverse_gamut_map(
    rgb_array: npt.NDArray[np.uint8],
    palette: Sequence[RGB],
    strength: float = 0.7,
) -> npt.NDArray[np.uint8]:
    """Grayout方式の逆変換（HSL彩度復元）。

    gamut_map で適用された彩度削減を逆算して復元する。
    式: new_s = s_orig * (1 - strength * (1 - desaturation))
    逆算: s_orig = new_s / (1 - strength * (1 - desaturation))

    Args:
        rgb_array: (H, W, 3) の uint8 配列 (RGB)
        palette: パレット色のシーケンス
        strength: マッピング強度 (0.0=無効, 1.0=最大)

    Returns:
        (H, W, 3) の uint8 配列 (RGB)
    """
    if strength <= 0.0:
        return rgb_array.copy()

    strength = min(strength, 1.0)

    h_min, h_range = _compute_palette_hsl_range(palette)
    hue_tolerance = _DEFAULT_HUE_TOLERANCE

    hsl = _rgb_to_hsl_batch(rgb_array)
    h = hsl[:, :, 0]
    s = hsl[:, :, 1]

    # 色相をパレット範囲にクリップ（順変換と同じ計算で desaturation を求める）
    h_clipped = _hue_clip(h_min, h_range, h)
    h_diff = np.abs(((h_clipped - h + 0.5) % 1.0) - 0.5)

    desaturation = np.where(
        h_diff >= hue_tolerance,
        0.0,
        1.0 - h_diff / hue_tolerance,
    )

    # 逆算: s_orig = s / factor, where factor = 1 - strength * (1 - desaturation)
    factor = 1.0 - strength * (1.0 - desaturation)
    # factor が 0 に近い場合（完全脱彩度化）は復元不可 → そのまま
    safe_factor = np.where(np.abs(factor) > 1e-12, factor, 1.0)
    restored_s = s / safe_factor

    # 色相復元: dithered画像の色相はパレット4色のブレンドのため
    # 元の色相情報は失われている → そのまま使う

    new_hsl = np.stack([h, restored_s, hsl[:, :, 2]], axis=-1)
    return _hsl_to_rgb_batch(new_hsl)


def inverse_apply_illuminant(
    rgb_array: npt.NDArray[np.uint8],
    r_scale: float = 1.0,
    g_scale: float = 0.7,
    b_scale: float = 0.1,
    white_preserve: float = 0.0,
) -> npt.NDArray[np.uint8]:
    """Illuminant逆変換（チャンネルスケール逆数）。

    apply_illuminant の逆操作。
    illuminated = original * scales (輝度補正済み)
    → original = illuminated / scales

    white_preserve > 0 の場合、スケールの大きいチャンネルから
    元画像の平均輝度を推定し、正しい preserve 値を求める。

    Args:
        rgb_array: (H, W, 3) の uint8 配列 (RGB)
        r_scale: R チャンネルのスケール係数
        g_scale: G チャンネルのスケール係数
        b_scale: B チャンネルのスケール係数
        white_preserve: 白保持の強さ

    Returns:
        (H, W, 3) の uint8 配列 (RGB)
    """
    output = rgb_array.astype(np.float64)

    # BT.709 輝度重み（順変換と同じ正規化）
    lum_factor = 0.2126 * r_scale + 0.7152 * g_scale + 0.0722 * b_scale
    norm = 1.0 / lum_factor if lum_factor > 1e-12 else 1.0
    scales = np.array(
        [r_scale * norm, g_scale * norm, b_scale * norm], dtype=np.float64,
    )

    # 逆スケール: 0 除算を回避
    safe_scales = np.where(np.abs(scales) > 1e-12, scales, 1.0)
    inv_scales = np.where(
        np.abs(scales) > 1e-12, 1.0 / safe_scales, 0.0,
    )

    if white_preserve > 0.0:
        # 順変換: out = original*(scales*(1-p) + p)  where p = (mean(original)/255)²*wp
        # 逆変換: original = out / (scales*(1-p) + p)
        # 問題: p は未知の original の平均に依存する
        #
        # 解決策: スケールの大きいチャンネル（R/G）から元画像を概算し、
        # 失われたチャンネル（B≈0）は他チャンネルの平均で代用して
        # 元画像の平均輝度を推定する。

        # Phase 1: white_preserve を無視した粗い逆変換
        rough = output * inv_scales[np.newaxis, np.newaxis, :]

        # スケール≈0 のチャンネルは情報喪失 → 他チャンネルの平均で推定
        valid_chs = [i for i in range(3) if abs(scales[i]) > 1e-12]
        zero_chs = [i for i in range(3) if abs(scales[i]) <= 1e-12]
        if valid_chs and zero_chs:
            valid_mean = np.mean(rough[:, :, valid_chs], axis=-1)
            for ch in zero_chs:
                rough[:, :, ch] = valid_mean

        # Phase 2: R/G は正確に逆変換、B（スケール≈0）はブラー値を保持
        estimate = np.clip(rough, 0, 255)
        for _ in range(2):
            lum = np.mean(estimate, axis=-1) / 255.0
            preserve = np.clip((lum * lum) * white_preserve, 0.0, 1.0)
            preserve_3d = preserve[:, :, np.newaxis]
            combined = scales[np.newaxis, np.newaxis, :] * (1.0 - preserve_3d) + preserve_3d
            safe_combined = np.where(
                np.abs(combined) > 1e-12, combined, 1.0,
            )
            estimate = np.clip(output / safe_combined, 0, 255)

            # スケール≈0 のチャンネルは情報喪失 → preserve ベースでブレンド
            # 明部(preserve≈1): 逆変換推定値を信頼（白を正しく復元）
            # 暗部(preserve≈0): output値を使用（青み防止）
            for ch in zero_chs:
                estimate[:, :, ch] = (
                    preserve * estimate[:, :, ch]
                    + (1.0 - preserve) * output[:, :, ch]
                )

        result = estimate
    else:
        result = output * inv_scales[np.newaxis, np.newaxis, :]

    return np.clip(result + 0.5, 0, 255).astype(np.uint8)
