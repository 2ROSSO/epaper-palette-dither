"""dithering.py のテスト。"""

from four_color_dither.domain.color import EINK_BLACK, EINK_PALETTE, EINK_WHITE, RGB
from four_color_dither.domain.dithering import FloydSteinbergDither


class TestFloydSteinbergDither:
    def setup_method(self) -> None:
        self.dither = FloydSteinbergDither()

    def test_single_white_pixel(self) -> None:
        pixels = [[(255, 255, 255)]]
        result = self.dither.dither(pixels, 1, 1, EINK_PALETTE)
        assert result[0][0] == EINK_WHITE.to_tuple()

    def test_single_black_pixel(self) -> None:
        pixels = [[(0, 0, 0)]]
        result = self.dither.dither(pixels, 1, 1, EINK_PALETTE)
        assert result[0][0] == EINK_BLACK.to_tuple()

    def test_output_only_contains_palette_colors(self) -> None:
        """出力が4色のみで構成されていることを検証。"""
        # 3x3のグラデーション画像
        pixels = [
            [(0, 0, 0), (128, 0, 0), (255, 0, 0)],
            [(0, 128, 0), (128, 128, 128), (255, 128, 0)],
            [(0, 0, 255), (128, 128, 0), (255, 255, 255)],
        ]
        result = self.dither.dither(pixels, 3, 3, EINK_PALETTE)
        palette_tuples = {c.to_tuple() for c in EINK_PALETTE}
        for row in result:
            for pixel in row:
                assert pixel in palette_tuples, f"Pixel {pixel} not in palette"

    def test_uniform_color_image(self) -> None:
        """単色画像のディザリング。白画像は全て白のまま。"""
        size = 4
        pixels = [[(255, 255, 255)] * size for _ in range(size)]
        result = self.dither.dither(pixels, size, size, EINK_PALETTE)
        for row in result:
            for pixel in row:
                assert pixel == EINK_WHITE.to_tuple()

    def test_preserves_dimensions(self) -> None:
        """出力の次元が入力と一致。"""
        w, h = 5, 3
        pixels = [[(100, 100, 100)] * w for _ in range(h)]
        result = self.dither.dither(pixels, w, h, EINK_PALETTE)
        assert len(result) == h
        assert all(len(row) == w for row in result)

    def test_red_image_mostly_red(self) -> None:
        """赤い画像のディザリング結果に赤が含まれる。"""
        size = 4
        pixels = [[(200, 0, 0)] * size for _ in range(size)]
        result = self.dither.dither(pixels, size, size, EINK_PALETTE)
        palette_tuples = {c.to_tuple() for c in EINK_PALETTE}
        flat = [pixel for row in result for pixel in row]
        for pixel in flat:
            assert pixel in palette_tuples
        # 赤ピクセルが少なくとも1つは存在するはず
        red_count = sum(1 for p in flat if p == (200, 0, 0))
        assert red_count > 0
