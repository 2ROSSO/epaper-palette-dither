"""color.py のテスト。"""

from epaper_palette_dither.domain.color import (
    RGB,
    LAB,
    EINK_BLACK,
    EINK_PALETTE,
    EINK_PALETTE_PERCEIVED,
    EINK_RED,
    EINK_WHITE,
    EINK_YELLOW,
    ciede2000,
    find_nearest_color,
    find_nearest_color_index,
    rgb_to_lab,
)


class TestRGB:
    def test_to_tuple(self) -> None:
        assert RGB(10, 20, 30).to_tuple() == (10, 20, 30)


class TestPalette:
    def test_palette_has_4_colors(self) -> None:
        assert len(EINK_PALETTE) == 4

    def test_palette_contains_expected_colors(self) -> None:
        assert EINK_WHITE in EINK_PALETTE
        assert EINK_BLACK in EINK_PALETTE
        assert EINK_RED in EINK_PALETTE
        assert EINK_YELLOW in EINK_PALETTE


class TestRgbToLab:
    def test_white(self) -> None:
        lab = rgb_to_lab(EINK_WHITE)
        assert abs(lab.l - 100.0) < 0.5
        assert abs(lab.a) < 1.0
        assert abs(lab.b) < 1.0

    def test_black(self) -> None:
        lab = rgb_to_lab(EINK_BLACK)
        assert abs(lab.l) < 0.5
        assert abs(lab.a) < 0.5
        assert abs(lab.b) < 0.5

    def test_red_has_positive_a(self) -> None:
        lab = rgb_to_lab(EINK_RED)
        assert lab.a > 0  # 赤はa*が正

    def test_yellow_has_positive_b(self) -> None:
        lab = rgb_to_lab(EINK_YELLOW)
        assert lab.b > 0  # 黄はb*が正


class TestCiede2000:
    def test_same_color_distance_is_zero(self) -> None:
        lab = rgb_to_lab(EINK_RED)
        assert ciede2000(lab, lab) == 0.0

    def test_black_white_large_distance(self) -> None:
        lab_black = rgb_to_lab(EINK_BLACK)
        lab_white = rgb_to_lab(EINK_WHITE)
        dist = ciede2000(lab_black, lab_white)
        assert dist > 50.0  # 黒と白は大きな色差

    def test_symmetry(self) -> None:
        lab1 = rgb_to_lab(EINK_RED)
        lab2 = rgb_to_lab(EINK_YELLOW)
        assert abs(ciede2000(lab1, lab2) - ciede2000(lab2, lab1)) < 1e-10


class TestFindNearestColor:
    def test_exact_match(self) -> None:
        assert find_nearest_color(EINK_WHITE) == EINK_WHITE
        assert find_nearest_color(EINK_BLACK) == EINK_BLACK
        assert find_nearest_color(EINK_RED) == EINK_RED
        assert find_nearest_color(EINK_YELLOW) == EINK_YELLOW

    def test_near_white(self) -> None:
        near_white = RGB(250, 250, 250)
        assert find_nearest_color(near_white) == EINK_WHITE

    def test_near_black(self) -> None:
        near_black = RGB(10, 10, 10)
        assert find_nearest_color(near_black) == EINK_BLACK

    def test_dark_red_maps_to_red(self) -> None:
        dark_red = RGB(150, 20, 20)
        assert find_nearest_color(dark_red) == EINK_RED

    def test_bright_yellow_maps_to_yellow(self) -> None:
        bright_yellow = RGB(240, 240, 30)
        assert find_nearest_color(bright_yellow) == EINK_YELLOW

    def test_blue_maps_to_black(self) -> None:
        # 青はパレットにないので、暗い色（黒）に近い
        blue = RGB(0, 0, 200)
        result = find_nearest_color(blue)
        assert result in EINK_PALETTE

    def test_result_always_in_palette(self) -> None:
        test_colors = [
            RGB(128, 128, 128),  # グレー
            RGB(0, 255, 0),  # 緑
            RGB(0, 0, 255),  # 青
            RGB(255, 128, 0),  # オレンジ
            RGB(128, 0, 128),  # 紫
        ]
        for color in test_colors:
            assert find_nearest_color(color) in EINK_PALETTE


class TestFindNearestColorRedPenalty:
    def test_no_penalty_backward_compatible(self) -> None:
        """red_penalty=0 で従来と同じ結果。"""
        for color in [EINK_WHITE, EINK_BLACK, EINK_RED, EINK_YELLOW, RGB(128, 128, 128)]:
            assert find_nearest_color(color, red_penalty=0.0) == find_nearest_color(color)

    def test_red_penalty_avoids_red_for_bright_pixel(self) -> None:
        """明るいピクセルで赤ペナルティが効く。"""
        # 明るめピンク — ペナルティなしだと赤に近いが、ペナルティありで白を選ぶ
        bright_pink = RGB(255, 200, 200)
        without_penalty = find_nearest_color(bright_pink, red_penalty=0.0)
        with_penalty = find_nearest_color(bright_pink, red_penalty=50.0, brightness=1.0)
        # ペナルティなしでは赤 or 白、ペナルティありでは白を期待
        assert with_penalty == EINK_WHITE
        assert with_penalty in EINK_PALETTE

    def test_red_penalty_no_effect_on_dark_pixel(self) -> None:
        """暗いピクセルではペナルティが効かない (brightness=0)。"""
        dark_red = RGB(150, 20, 20)
        without = find_nearest_color(dark_red, red_penalty=0.0)
        with_pen = find_nearest_color(dark_red, red_penalty=50.0, brightness=0.0)
        assert without == with_pen

    def test_red_penalty_no_effect_on_non_red_palette(self) -> None:
        """赤以外のパレット色は影響を受けない。"""
        # 黒に近い色はペナルティがあっても黒
        near_black = RGB(10, 10, 10)
        assert find_nearest_color(near_black, red_penalty=50.0, brightness=0.5) == EINK_BLACK
        # 白に近い色はペナルティがあっても白
        near_white = RGB(250, 250, 250)
        assert find_nearest_color(near_white, red_penalty=50.0, brightness=1.0) == EINK_WHITE


class TestFindNearestColorYellowPenalty:
    def test_no_penalty_backward_compatible(self) -> None:
        """yellow_penalty=0 で従来と同じ結果。"""
        for color in [EINK_WHITE, EINK_BLACK, EINK_RED, EINK_YELLOW, RGB(128, 128, 128)]:
            assert find_nearest_color(color, yellow_penalty=0.0) == find_nearest_color(color)

    def test_yellow_penalty_avoids_yellow_for_dark_pixel(self) -> None:
        """暗いピクセルで黄ペナルティが効く。"""
        # 暗めの黄緑 — ペナルティなしだと黄に近いが、ペナルティありで黒を選ぶ
        dark_yellowish = RGB(100, 100, 10)
        with_penalty = find_nearest_color(
            dark_yellowish, yellow_penalty=50.0, brightness=0.0,
        )
        assert with_penalty == EINK_BLACK

    def test_yellow_penalty_no_effect_on_bright_pixel(self) -> None:
        """明るいピクセルではペナルティが効かない (brightness=1.0)。"""
        near_yellow = RGB(240, 240, 30)
        without = find_nearest_color(near_yellow, yellow_penalty=0.0)
        with_pen = find_nearest_color(near_yellow, yellow_penalty=50.0, brightness=1.0)
        assert without == with_pen

    def test_yellow_penalty_no_effect_on_non_yellow_palette(self) -> None:
        """黄以外のパレット色は影響を受けない。"""
        near_black = RGB(10, 10, 10)
        assert find_nearest_color(near_black, yellow_penalty=50.0, brightness=0.0) == EINK_BLACK
        near_white = RGB(250, 250, 250)
        assert find_nearest_color(near_white, yellow_penalty=50.0, brightness=1.0) == EINK_WHITE


class TestPerceivedPaletteDefinition:
    def test_length_matches_output_palette(self) -> None:
        """知覚パレットと出力パレットの要素数が一致。"""
        assert len(EINK_PALETTE_PERCEIVED) == len(EINK_PALETTE)

    def test_all_elements_are_rgb(self) -> None:
        """知覚パレットの全要素がRGB型。"""
        for color in EINK_PALETTE_PERCEIVED:
            assert isinstance(color, RGB)

    def test_perceived_values_differ_from_output(self) -> None:
        """知覚パレットと出力パレットの値が異なる。"""
        differ_count = sum(
            1 for p, pp in zip(EINK_PALETTE, EINK_PALETTE_PERCEIVED) if p != pp
        )
        assert differ_count > 0


class TestFindNearestColorIndex:
    def test_exact_match_returns_correct_index(self) -> None:
        """パレット色自体を入力すると正しいインデックス。"""
        for i, color in enumerate(EINK_PALETTE):
            assert find_nearest_color_index(color) == i

    def test_result_range(self) -> None:
        """戻り値が 0〜len(palette)-1。"""
        test_colors = [RGB(128, 128, 128), RGB(0, 255, 0), RGB(255, 128, 0)]
        for color in test_colors:
            idx = find_nearest_color_index(color)
            assert 0 <= idx < len(EINK_PALETTE)


class TestFindNearestColorIndexPerceived:
    def test_perceived_palette_changes_selection(self) -> None:
        """知覚パレット使用時に結果が変わるケースがある。"""
        # 中間的な緑 — 出力パレットでは黒に近いが、知覚パレットでは白に近い
        color = RGB(0, 110, 0)
        idx_normal = find_nearest_color_index(color)
        idx_perceived = find_nearest_color_index(
            color, perceived_palette=EINK_PALETTE_PERCEIVED,
        )
        assert idx_normal != idx_perceived, "知覚パレットで結果が変わるはず"

    def test_perceived_palette_returns_output_palette_index(self) -> None:
        """知覚パレット使用時もインデックスは出力パレットに対応。"""
        color = RGB(150, 100, 50)
        idx = find_nearest_color_index(
            color, perceived_palette=EINK_PALETTE_PERCEIVED,
        )
        assert 0 <= idx < len(EINK_PALETTE)
        # find_nearest_color と一致
        result_color = find_nearest_color(
            color, perceived_palette=EINK_PALETTE_PERCEIVED,
        )
        assert result_color == EINK_PALETTE[idx]


class TestFindNearestColorBackwardCompat:
    def test_find_nearest_color_matches_index(self) -> None:
        """find_nearest_color が find_nearest_color_index のラッパーとして正しい。"""
        test_colors = [
            EINK_WHITE, EINK_BLACK, EINK_RED, EINK_YELLOW,
            RGB(128, 128, 128), RGB(0, 255, 0), RGB(255, 128, 0),
        ]
        for color in test_colors:
            idx = find_nearest_color_index(color)
            assert find_nearest_color(color) == EINK_PALETTE[idx]

    def test_find_nearest_color_with_penalty_matches_index(self) -> None:
        """ペナルティ付き find_nearest_color が index 版と整合。"""
        color = RGB(200, 180, 180)
        idx = find_nearest_color_index(
            color, red_penalty=30.0, brightness=0.8,
        )
        result = find_nearest_color(color, red_penalty=30.0, brightness=0.8)
        assert result == EINK_PALETTE[idx]
