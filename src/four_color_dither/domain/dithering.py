"""ディザリングアルゴリズム定義。

Protocol + Floyd-Steinberg実装。
domain層のためPure Python（typing依存のみ）。
実際の画像処理はinfrastructure/application層でNumPyを使う。
"""

from __future__ import annotations

from typing import Protocol, Sequence

from four_color_dither.domain.color import RGB


class DitherAlgorithm(Protocol):
    """ディザリングアルゴリズムのProtocol。

    infrastructure層で具体的な実装（NumPyベース等）を提供する。
    """

    def dither(
        self,
        pixels: list[list[tuple[int, int, int]]],
        width: int,
        height: int,
        palette: Sequence[RGB],
    ) -> list[list[tuple[int, int, int]]]:
        """2D画像データにディザリングを適用。

        Args:
            pixels: 画像のピクセルデータ [y][x] = (r, g, b)
            width: 画像の幅
            height: 画像の高さ
            palette: 使用するカラーパレット

        Returns:
            ディザリング済みのピクセルデータ
        """
        ...


class FloydSteinbergDither:
    """Floyd-Steinbergディザリングの Pure Python 実装。

    エラー拡散パターン:
            [*] [7]
       [3] [5] [1]
       ※ [*]=現在のピクセル、数値=エラー拡散の重み(/16)
    """

    def dither(
        self,
        pixels: list[list[tuple[int, int, int]]],
        width: int,
        height: int,
        palette: Sequence[RGB],
    ) -> list[list[tuple[int, int, int]]]:
        from four_color_dither.domain.color import find_nearest_color

        # 浮動小数点で作業用コピーを作成
        work: list[list[list[float]]] = [
            [[float(c) for c in pixel] for pixel in row] for row in pixels
        ]

        for y in range(height):
            for x in range(width):
                old_r, old_g, old_b = work[y][x]

                # 現在のピクセルを0-255にクランプしてRGBに変換
                clamped = RGB(
                    _clamp(round(old_r)),
                    _clamp(round(old_g)),
                    _clamp(round(old_b)),
                )

                # 最近傍色を検索
                nearest = find_nearest_color(clamped, palette)

                # 結果を反映
                work[y][x] = [float(nearest.r), float(nearest.g), float(nearest.b)]

                # 量子化誤差
                err_r = old_r - nearest.r
                err_g = old_g - nearest.g
                err_b = old_b - nearest.b

                # エラー拡散
                _diffuse(work, x + 1, y, width, height, err_r, err_g, err_b, 7.0 / 16.0)
                _diffuse(work, x - 1, y + 1, width, height, err_r, err_g, err_b, 3.0 / 16.0)
                _diffuse(work, x, y + 1, width, height, err_r, err_g, err_b, 5.0 / 16.0)
                _diffuse(work, x + 1, y + 1, width, height, err_r, err_g, err_b, 1.0 / 16.0)

        # 結果をintタプルに変換
        result: list[list[tuple[int, int, int]]] = [
            [(_clamp(round(p[0])), _clamp(round(p[1])), _clamp(round(p[2]))) for p in row]
            for row in work
        ]
        return result


def _clamp(value: int, min_val: int = 0, max_val: int = 255) -> int:
    """値を指定範囲にクランプ。"""
    return max(min_val, min(max_val, value))


def _diffuse(
    work: list[list[list[float]]],
    x: int,
    y: int,
    width: int,
    height: int,
    err_r: float,
    err_g: float,
    err_b: float,
    factor: float,
) -> None:
    """エラーを隣接ピクセルに拡散。"""
    if 0 <= x < width and 0 <= y < height:
        work[y][x][0] += err_r * factor
        work[y][x][1] += err_g * factor
        work[y][x][2] += err_b * factor
