"""テストベクトル生成スクリプト。

Python実装から期待値を生成し、JSON形式で保存する。
JS実装のクロス言語テストに使用。

Usage:
    uv run python scriptable/tests/generate-vectors.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# プロジェクトルートからインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np

from epaper_palette_dither.domain.color import (
    EINK_PALETTE,
    RGB,
    ciede2000,
    find_nearest_color,
    rgb_to_lab,
)
from epaper_palette_dither.infrastructure.gamut_mapping import (
    anti_saturate,
    anti_saturate_centroid,
    anti_saturate_lab,
    anti_saturate_centroid_lab,
    apply_illuminant,
    gamut_map,
)
from epaper_palette_dither.infrastructure.lightness_remap import clahe_lightness
from epaper_palette_dither.application.dither_service import DitherService


def _rgb_tuple(rgb: RGB) -> list[int]:
    return [rgb.r, rgb.g, rgb.b]


def _lab_list(r: int, g: int, b: int) -> list[float]:
    lab = rgb_to_lab(RGB(r, g, b))
    return [round(lab.l, 6), round(lab.a, 6), round(lab.b, 6)]


def generate_color_vectors() -> dict:
    """色計算テストベクトル生成。"""
    vectors = {}

    # --- rgbToLab ---
    lab_cases = [
        # パレット4色
        [255, 255, 255],
        [0, 0, 0],
        [200, 0, 0],
        [255, 255, 0],
        # 境界値・中間値
        [128, 128, 128],
        [0, 0, 255],
        [0, 255, 0],
        [255, 0, 255],
        [128, 64, 32],
        [1, 1, 1],
    ]
    vectors["rgbToLab"] = [
        {"input": c, "expected": _lab_list(*c)} for c in lab_cases
    ]

    # --- ciede2000 ---
    ciede_pairs = [
        ([255, 255, 255], [0, 0, 0]),         # 白 vs 黒
        ([255, 255, 255], [200, 0, 0]),        # 白 vs 赤
        ([255, 255, 255], [255, 255, 0]),      # 白 vs 黄
        ([200, 0, 0], [255, 255, 0]),          # 赤 vs 黄
        ([0, 0, 0], [200, 0, 0]),              # 黒 vs 赤
        ([0, 0, 0], [255, 255, 0]),            # 黒 vs 黄
        ([128, 128, 128], [128, 128, 128]),    # 同色
        ([0, 0, 255], [200, 0, 0]),            # 青 vs 赤
        ([100, 200, 50], [150, 100, 200]),     # 緑 vs 紫
        ([255, 128, 0], [0, 128, 255]),        # オレンジ vs 水色
    ]
    vectors["ciede2000"] = []
    for c1, c2 in ciede_pairs:
        lab1 = rgb_to_lab(RGB(*c1))
        lab2 = rgb_to_lab(RGB(*c2))
        dist = ciede2000(lab1, lab2)
        vectors["ciede2000"].append({
            "input1": c1,
            "input2": c2,
            "expected": round(dist, 6),
        })

    # --- findNearestColor ---
    nearest_cases = [
        # [r, g, b, redPenalty, yellowPenalty, brightness]
        [255, 255, 255, 0, 0, 0],      # 白→白
        [0, 0, 0, 0, 0, 0],            # 黒→黒
        [200, 0, 0, 0, 0, 0],          # 赤→赤
        [255, 255, 0, 0, 0, 0],        # 黄→黄
        [128, 128, 128, 0, 0, 0],      # グレー→最近色
        [0, 0, 255, 0, 0, 0],          # 青→最近色
        [255, 128, 0, 0, 0, 0],        # オレンジ→最近色
        [100, 50, 50, 0, 0, 0],        # 暗い赤→最近色
        # ペナルティあり
        [180, 100, 80, 10.0, 0.0, 0.8],   # 明部赤ペナルティ
        [180, 100, 80, 0.0, 15.0, 0.2],   # 暗部黄ペナルティ
        [200, 180, 50, 10.0, 15.0, 0.7],  # 両ペナルティ
        [200, 180, 50, 10.0, 15.0, 0.3],  # 両ペナルティ（暗部）
    ]
    vectors["findNearestColor"] = []
    for case in nearest_cases:
        r, g, b = case[0], case[1], case[2]
        red_pen, yellow_pen, brightness = case[3], case[4], case[5]
        result = find_nearest_color(
            RGB(r, g, b), EINK_PALETTE, red_pen, yellow_pen, brightness,
        )
        vectors["findNearestColor"].append({
            "input": [r, g, b],
            "redPenalty": red_pen,
            "yellowPenalty": yellow_pen,
            "brightness": brightness,
            "expected": _rgb_tuple(result),
        })

    return vectors


def generate_gamut_vectors() -> dict:
    """ガマットマッピングテストベクトル生成。"""
    vectors = {}
    palette = list(EINK_PALETTE)

    # 3×3 テスト画像（多様な色）
    test_image = np.array([
        [[255, 0, 0],   [0, 255, 0],   [0, 0, 255]],
        [[255, 255, 0], [128, 128, 128], [255, 0, 255]],
        [[0, 255, 255], [200, 100, 50], [50, 50, 50]],
    ], dtype=np.uint8)

    # --- Grayout ---
    for strength in [0.5, 0.7, 1.0]:
        result = gamut_map(test_image, palette, strength)
        vectors[f"grayout_{strength}"] = {
            "input": test_image.tolist(),
            "strength": strength,
            "expected": result.tolist(),
        }

    # --- Anti-Saturation ---
    result = anti_saturate(test_image, palette)
    vectors["antiSaturate"] = {
        "input": test_image.tolist(),
        "expected": result.tolist(),
    }

    # --- Centroid Clip ---
    result = anti_saturate_centroid(test_image, palette)
    vectors["centroidClip"] = {
        "input": test_image.tolist(),
        "expected": result.tolist(),
    }

    # --- Anti-Saturation Lab ---
    result = anti_saturate_lab(test_image, palette)
    vectors["antiSaturateLab"] = {
        "input": test_image.tolist(),
        "expected": result.tolist(),
    }

    # --- Centroid Clip Lab ---
    result = anti_saturate_centroid_lab(test_image, palette)
    vectors["centroidClipLab"] = {
        "input": test_image.tolist(),
        "expected": result.tolist(),
    }

    # --- Illuminant ---
    for params in [
        {"r": 1.0, "g": 0.7, "b": 0.0, "white": 0.0},
        {"r": 2.0, "g": 1.0, "b": 0.0, "white": 1.0},
        {"r": 1.5, "g": 0.5, "b": 0.0, "white": 0.5},
    ]:
        result = apply_illuminant(
            test_image, params["r"], params["g"], params["b"], params["white"],
        )
        key = f"illuminant_r{params['r']}_g{params['g']}_b{params['b']}_w{params['white']}"
        vectors[key] = {
            "input": test_image.tolist(),
            "rScale": params["r"],
            "gScale": params["g"],
            "bScale": params["b"],
            "whitePreserve": params["white"],
            "expected": result.tolist(),
        }

    return vectors


def generate_dither_vectors() -> dict:
    """ディザリングテストベクトル生成。"""
    vectors = {}
    service = DitherService()

    # 3×3 テスト画像
    test_image = np.array([
        [[255, 0, 0],   [0, 255, 0],   [0, 0, 255]],
        [[255, 255, 0], [128, 128, 128], [255, 0, 255]],
        [[0, 255, 255], [200, 100, 50], [50, 50, 50]],
    ], dtype=np.uint8)

    # デフォルトパラメータ
    result = service.dither_array_fast(test_image)
    vectors["default"] = {
        "input": test_image.tolist(),
        "errorClamp": 0,
        "redPenalty": 0.0,
        "yellowPenalty": 0.0,
        "expected": result.tolist(),
    }

    # ErrClamp付き
    result = service.dither_array_fast(test_image, error_clamp=85)
    vectors["errClamp85"] = {
        "input": test_image.tolist(),
        "errorClamp": 85,
        "redPenalty": 0.0,
        "yellowPenalty": 0.0,
        "expected": result.tolist(),
    }

    # ペナルティ付き
    result = service.dither_array_fast(
        test_image, error_clamp=85, red_penalty=10.0, yellow_penalty=15.0,
    )
    vectors["withPenalties"] = {
        "input": test_image.tolist(),
        "errorClamp": 85,
        "redPenalty": 10.0,
        "yellowPenalty": 15.0,
        "expected": result.tolist(),
    }

    # CSF chroma weight 付き
    result = service.dither_array_fast(test_image, error_clamp=85, csf_chroma_weight=0.6)
    vectors["csfWeight06"] = {
        "input": test_image.tolist(),
        "errorClamp": 85,
        "redPenalty": 0.0,
        "yellowPenalty": 0.0,
        "csfChromaWeight": 0.6,
        "expected": result.tolist(),
    }

    # CSF chroma weight = 0.0 (輝度のみ)
    result = service.dither_array_fast(test_image, error_clamp=85, csf_chroma_weight=0.0)
    vectors["csfWeight00"] = {
        "input": test_image.tolist(),
        "errorClamp": 85,
        "redPenalty": 0.0,
        "yellowPenalty": 0.0,
        "csfChromaWeight": 0.0,
        "expected": result.tolist(),
    }

    # 単色画像テスト
    for color_name, color in [("white", [255, 255, 255]), ("black", [0, 0, 0]),
                               ("red", [200, 0, 0]), ("gray", [128, 128, 128])]:
        img = np.full((3, 3, 3), color, dtype=np.uint8)
        result = service.dither_array_fast(img)
        vectors[f"solid_{color_name}"] = {
            "input": img.tolist(),
            "errorClamp": 0,
            "redPenalty": 0.0,
            "yellowPenalty": 0.0,
            "expected": result.tolist(),
        }

    return vectors


def generate_clahe_vectors() -> dict:
    """CLAHE テストベクトル生成。"""
    vectors = {}

    # 4×4 グラデーション画像
    gradient = np.zeros((4, 4, 3), dtype=np.uint8)
    for y in range(4):
        for x in range(4):
            val = int((y * 4 + x) / 15 * 255)
            gradient[y, x] = [val, val, val]

    # デフォルト clip_limit=2.0
    result = clahe_lightness(gradient.copy(), clip_limit=2.0, grid_size=2)
    vectors["gradient_clip2"] = {
        "input": gradient.tolist(),
        "clipLimit": 2.0,
        "gridSize": 2,
        "expected": result.tolist(),
    }

    # 強い clip_limit=4.0
    result = clahe_lightness(gradient.copy(), clip_limit=4.0, grid_size=2)
    vectors["gradient_clip4"] = {
        "input": gradient.tolist(),
        "clipLimit": 4.0,
        "gridSize": 2,
        "expected": result.tolist(),
    }

    # 3×3 カラー画像
    color_image = np.array([
        [[255, 0, 0],   [0, 255, 0],   [0, 0, 255]],
        [[255, 255, 0], [128, 128, 128], [255, 0, 255]],
        [[0, 255, 255], [200, 100, 50], [50, 50, 50]],
    ], dtype=np.uint8)
    result = clahe_lightness(color_image.copy(), clip_limit=2.0, grid_size=2)
    vectors["color_clip2"] = {
        "input": color_image.tolist(),
        "clipLimit": 2.0,
        "gridSize": 2,
        "expected": result.tolist(),
    }

    return vectors


def main() -> None:
    print("Generating test vectors...")

    all_vectors = {
        "color": generate_color_vectors(),
        "gamut": generate_gamut_vectors(),
        "dither": generate_dither_vectors(),
        "clahe": generate_clahe_vectors(),
    }

    output_path = Path(__file__).parent / "test-vectors.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_vectors, f, indent=2, ensure_ascii=False)

    # サマリー
    n_color = (
        len(all_vectors["color"]["rgbToLab"])
        + len(all_vectors["color"]["ciede2000"])
        + len(all_vectors["color"]["findNearestColor"])
    )
    n_gamut = len(all_vectors["gamut"])
    n_dither = len(all_vectors["dither"])
    n_clahe = len(all_vectors["clahe"])
    print(f"Generated: {n_color} color, {n_gamut} gamut, {n_dither} dither, {n_clahe} clahe vectors")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
