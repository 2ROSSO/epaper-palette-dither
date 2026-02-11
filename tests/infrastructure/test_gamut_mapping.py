"""gamut_mapping.py のテスト。"""

import numpy as np

from epaper_palette_dither.domain.color import EINK_PALETTE, RGB
from epaper_palette_dither.infrastructure.gamut_mapping import (
    _build_tetrahedron_faces,
    _clip_via_centroid,
    _closest_point_on_triangle,
    _compute_palette_hsl_range,
    _hue_clip,
    _hue_diff,
    _hsl_to_rgb_batch,
    _is_inside_tetrahedron,
    _project_to_tetrahedron_surface,
    _rgb_to_hsl_batch,
    anti_saturate,
    anti_saturate_centroid,
    apply_illuminant,
    gamut_map,
)


class TestRgbHslRoundtrip:
    def test_white_roundtrip(self) -> None:
        rgb = np.array([[[255, 255, 255]]], dtype=np.uint8)
        hsl = _rgb_to_hsl_batch(rgb)
        result = _hsl_to_rgb_batch(hsl)
        np.testing.assert_array_equal(result, rgb)

    def test_black_roundtrip(self) -> None:
        rgb = np.array([[[0, 0, 0]]], dtype=np.uint8)
        hsl = _rgb_to_hsl_batch(rgb)
        result = _hsl_to_rgb_batch(hsl)
        np.testing.assert_array_equal(result, rgb)

    def test_red_roundtrip(self) -> None:
        rgb = np.array([[[200, 0, 0]]], dtype=np.uint8)
        hsl = _rgb_to_hsl_batch(rgb)
        result = _hsl_to_rgb_batch(hsl)
        diff = np.abs(result.astype(int) - rgb.astype(int))
        assert diff.max() <= 1

    def test_various_colors_roundtrip(self) -> None:
        """様々な色でRGB→HSL→RGBの往復精度を検証。"""
        colors = np.array(
            [
                [[255, 0, 0], [0, 255, 0], [0, 0, 255]],
                [[128, 128, 128], [200, 100, 50], [50, 200, 100]],
            ],
            dtype=np.uint8,
        )
        hsl = _rgb_to_hsl_batch(colors)
        result = _hsl_to_rgb_batch(hsl)
        diff = np.abs(colors.astype(int) - result.astype(int))
        assert diff.max() <= 1

    def test_batch_shape(self) -> None:
        rgb = np.zeros((10, 20, 3), dtype=np.uint8)
        hsl = _rgb_to_hsl_batch(rgb)
        assert hsl.shape == (10, 20, 3)
        result = _hsl_to_rgb_batch(hsl)
        assert result.shape == (10, 20, 3)
        assert result.dtype == np.uint8


class TestRgbToHslBatch:
    def test_blue_hsl_lightness(self) -> None:
        """青のHSL明度は0.5（これがGrayout方式の鍵）。"""
        rgb = np.array([[[0, 0, 255]]], dtype=np.uint8)
        hsl = _rgb_to_hsl_batch(rgb)
        assert abs(hsl[0, 0, 2] - 0.5) < 0.01  # L = 0.5

    def test_grey_is_achromatic(self) -> None:
        rgb = np.array([[[128, 128, 128]]], dtype=np.uint8)
        hsl = _rgb_to_hsl_batch(rgb)
        assert abs(hsl[0, 0, 1]) < 0.01  # S ≈ 0

    def test_red_hue(self) -> None:
        rgb = np.array([[[255, 0, 0]]], dtype=np.uint8)
        hsl = _rgb_to_hsl_batch(rgb)
        assert abs(hsl[0, 0, 0]) < 0.01 or abs(hsl[0, 0, 0] - 1.0) < 0.01


class TestHueDiff:
    def test_same_hue(self) -> None:
        h = np.array([0.5])
        result = _hue_diff(h, 0.5)
        assert abs(result[0]) < 1e-10

    def test_wrap_around(self) -> None:
        h = np.array([0.95])
        result = _hue_diff(h, 0.05)
        # 0.95→0.05は反時計回りで-0.1
        assert abs(result[0] - (-0.1)) < 1e-10


class TestHueClip:
    def test_inside_range_unchanged(self) -> None:
        """範囲内の色相はそのまま。"""
        hue = np.array([[0.1]])
        result = _hue_clip(0.0, 0.2, hue)
        assert abs(result[0, 0] - 0.1) < 1e-10

    def test_outside_range_clipped(self) -> None:
        """範囲外の色相はクリップされる。"""
        hue = np.array([[0.5]])  # 範囲 0.0〜0.2 の外
        result = _hue_clip(0.0, 0.2, hue)
        # 0.0 か 0.2 のどちらかにクリップ
        assert result[0, 0] < 0.3 or result[0, 0] > 0.9


class TestComputePaletteHslRange:
    def test_eink_palette_range(self) -> None:
        """E-Inkパレットの色相範囲: 赤(0°)〜黄(60°)。"""
        h_min, h_range = _compute_palette_hsl_range(EINK_PALETTE)
        # 赤(≈0.0)から黄(≈1/6)の範囲
        assert h_range > 0.05
        assert h_range < 0.5  # 半周未満


class TestGamutMap:
    def test_output_shape_and_dtype(self) -> None:
        """出力のshape/dtypeが入力と一致。"""
        rgb = np.random.default_rng(42).integers(0, 256, (10, 15, 3), dtype=np.uint8)
        result = gamut_map(rgb, EINK_PALETTE)
        assert result.shape == (10, 15, 3)
        assert result.dtype == np.uint8

    def test_white_unchanged(self) -> None:
        """白は変化しない。"""
        rgb = np.full((2, 2, 3), 255, dtype=np.uint8)
        result = gamut_map(rgb, EINK_PALETTE)
        np.testing.assert_array_equal(result, rgb)

    def test_black_unchanged(self) -> None:
        """黒は変化しない。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        result = gamut_map(rgb, EINK_PALETTE)
        np.testing.assert_array_equal(result, rgb)

    def test_grey_unchanged(self) -> None:
        """グレーは変化しない（無彩色保存）。"""
        rgb = np.full((2, 2, 3), 128, dtype=np.uint8)
        result = gamut_map(rgb, EINK_PALETTE)
        diff = np.abs(result.astype(int) - rgb.astype(int))
        assert diff.max() <= 1

    def test_red_nearly_preserved(self) -> None:
        """パレット赤はほぼ保存される。"""
        rgb = np.full((2, 2, 3), 0, dtype=np.uint8)
        rgb[:, :, 0] = 200  # E-Ink赤 (200, 0, 0)
        result = gamut_map(rgb, EINK_PALETTE)
        diff = np.abs(result.astype(int) - rgb.astype(int))
        assert diff.max() <= 5

    def test_yellow_nearly_preserved(self) -> None:
        """パレット黄はほぼ保存される。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 0] = 255
        rgb[:, :, 1] = 255  # (255, 255, 0)
        result = gamut_map(rgb, EINK_PALETTE)
        diff = np.abs(result.astype(int) - rgb.astype(int))
        assert diff.max() <= 5

    def test_blue_becomes_grey_not_black(self) -> None:
        """青はグレーになる（黒ではなく！HSL明度0.5が保存される）。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 2] = 255  # 純青 (0, 0, 255)

        result = gamut_map(rgb, EINK_PALETTE, strength=1.0)

        # HSL明度0.5 → RGB(128, 128, 128) 付近のグレーになるはず
        avg = result.mean()
        assert avg > 100, f"青がグレーではなく暗すぎる: 平均={avg:.0f}"

    def test_blue_desaturated(self) -> None:
        """青の彩度が大幅に下がる。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 2] = 255

        result = gamut_map(rgb, EINK_PALETTE, strength=1.0)

        # ほぼ無彩色（R≈G≈B）になるはず
        r, g, b = result[0, 0, 0], result[0, 0, 1], result[0, 0, 2]
        max_diff = max(abs(int(r) - int(g)), abs(int(g) - int(b)), abs(int(r) - int(b)))
        assert max_diff < 10, f"彩度が残りすぎ: R={r}, G={g}, B={b}"

    def test_green_desaturated_or_shifted(self) -> None:
        """緑は彩度が低減される。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 1] = 200  # 緑 (0, 200, 0)

        original_hsl = _rgb_to_hsl_batch(rgb)
        result = gamut_map(rgb, EINK_PALETTE, strength=0.7)
        result_hsl = _rgb_to_hsl_batch(result)

        # 彩度が低減されている
        assert result_hsl[0, 0, 1] < original_hsl[0, 0, 1]

    def test_strength_zero_identity(self) -> None:
        """strength=0.0で恒等変換。"""
        rgb = np.random.default_rng(42).integers(0, 256, (5, 5, 3), dtype=np.uint8)
        result = gamut_map(rgb, EINK_PALETTE, strength=0.0)
        np.testing.assert_array_equal(result, rgb)

    def test_strength_increase_stronger_desaturation(self) -> None:
        """strength増加で彩度低減が強化される。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 2] = 255  # 青

        result_low = gamut_map(rgb, EINK_PALETTE, strength=0.3)
        result_high = gamut_map(rgb, EINK_PALETTE, strength=0.9)

        hsl_low = _rgb_to_hsl_batch(result_low)
        hsl_high = _rgb_to_hsl_batch(result_high)

        # 高strengthの方が彩度が低い
        assert hsl_high[0, 0, 1] < hsl_low[0, 0, 1]

    def test_lightness_preserved_for_blue(self) -> None:
        """青のHSL明度が保存される。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 2] = 255

        original_hsl = _rgb_to_hsl_batch(rgb)
        result = gamut_map(rgb, EINK_PALETTE, strength=0.7)
        result_hsl = _rgb_to_hsl_batch(result)

        # HSL明度は変わらない
        l_diff = abs(float(result_hsl[0, 0, 2]) - float(original_hsl[0, 0, 2]))
        assert l_diff < 0.05

    def test_lightness_gradient_order_preserved(self) -> None:
        """明度勾配の順序が保存される。"""
        gradient = np.zeros((1, 5, 3), dtype=np.uint8)
        for i in range(5):
            val = 255 - i * 50
            gradient[0, i, :] = val

        result = gamut_map(gradient, EINK_PALETTE)
        result_hsl = _rgb_to_hsl_batch(result)

        for i in range(4):
            assert result_hsl[0, i, 2] >= result_hsl[0, i + 1, 2]


# ---------------------------------------------------------------------------
# Anti-Saturation（凸包クリッピング）テスト
# ---------------------------------------------------------------------------

# E-Inkパレット頂点を正規化
_PALETTE_VERTS = np.array(
    [[c.r / 255.0, c.g / 255.0, c.b / 255.0] for c in EINK_PALETTE],
    dtype=np.float64,
)


class TestTetrahedronHelpers:
    """四面体ヘルパー関数のテスト。"""

    def test_palette_vertex_inside(self) -> None:
        """パレット頂点は四面体内部と判定される。"""
        face_verts, face_normals = _build_tetrahedron_faces(_PALETTE_VERTS)
        for v in _PALETTE_VERTS:
            pts = v.reshape(1, 3)
            assert _is_inside_tetrahedron(pts, face_verts, face_normals)[0]

    def test_centroid_inside(self) -> None:
        """パレット重心は四面体内部。"""
        face_verts, face_normals = _build_tetrahedron_faces(_PALETTE_VERTS)
        centroid = _PALETTE_VERTS.mean(axis=0).reshape(1, 3)
        assert _is_inside_tetrahedron(centroid, face_verts, face_normals)[0]

    def test_pure_blue_outside(self) -> None:
        """純青 (0,0,1) はE-Inkパレット四面体の外部。"""
        face_verts, face_normals = _build_tetrahedron_faces(_PALETTE_VERTS)
        blue = np.array([[0.0, 0.0, 1.0]])
        assert not _is_inside_tetrahedron(blue, face_verts, face_normals)[0]

    def test_pure_green_outside(self) -> None:
        """純緑 (0,1,0) はE-Inkパレット四面体の外部。"""
        face_verts, face_normals = _build_tetrahedron_faces(_PALETTE_VERTS)
        green = np.array([[0.0, 1.0, 0.0]])
        assert not _is_inside_tetrahedron(green, face_verts, face_normals)[0]


class TestAntiSaturate:
    """anti_saturate のテスト。"""

    def test_output_shape_and_dtype(self) -> None:
        """出力のshape/dtypeが入力と一致。"""
        rgb = np.random.default_rng(42).integers(0, 256, (10, 15, 3), dtype=np.uint8)
        result = anti_saturate(rgb, EINK_PALETTE)
        assert result.shape == (10, 15, 3)
        assert result.dtype == np.uint8

    def test_palette_vertices_unchanged(self) -> None:
        """パレット頂点（黒/白/赤/黄）は変化しない。"""
        for color in EINK_PALETTE:
            rgb = np.full((2, 2, 3), 0, dtype=np.uint8)
            rgb[:, :, 0] = color.r
            rgb[:, :, 1] = color.g
            rgb[:, :, 2] = color.b
            result = anti_saturate(rgb, EINK_PALETTE)
            diff = np.abs(result.astype(int) - rgb.astype(int))
            assert diff.max() <= 1, f"パレット色 {color} が変化: diff={diff.max()}"

    def test_gray_axis_unchanged(self) -> None:
        """グレー軸上の点は変化しない。"""
        for val in [0, 64, 128, 192, 255]:
            rgb = np.full((2, 2, 3), val, dtype=np.uint8)
            result = anti_saturate(rgb, EINK_PALETTE)
            diff = np.abs(result.astype(int) - rgb.astype(int))
            assert diff.max() <= 1, f"グレー {val} が変化: diff={diff.max()}"

    def test_green_retains_color_unlike_grayout(self) -> None:
        """緑はGrayout方式と異なり色情報を保持する（差別化確認）。

        Grayout方式は緑を無彩色に近づけるが、Anti-Saturation は
        四面体表面（黄色寄り）に射影するため、色チャンネル間に差が残る。
        """
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 1] = 200  # 純緑

        result_as = anti_saturate(rgb, EINK_PALETTE)
        result_gm = gamut_map(rgb, EINK_PALETTE, strength=1.0)

        # Anti-Saturation の結果は色チャンネル間に差がある
        r, g, b = int(result_as[0, 0, 0]), int(result_as[0, 0, 1]), int(result_as[0, 0, 2])
        max_diff_as = max(abs(r - g), abs(g - b), abs(r - b))
        assert max_diff_as > 5, (
            f"Anti-Saturation が完全脱彩度化: R={r}, G={g}, B={b}"
        )

        # Grayout の方がより脱彩度化されている（max_diffが小さい）
        rg, gg, bg = (
            int(result_gm[0, 0, 0]),
            int(result_gm[0, 0, 1]),
            int(result_gm[0, 0, 2]),
        )
        max_diff_gm = max(abs(rg - gg), abs(gg - bg), abs(rg - bg))
        assert max_diff_as > max_diff_gm, (
            f"Anti-Saturation({max_diff_as}) がGrayout({max_diff_gm})より"
            "脱彩度化されている"
        )

    def test_blue_moves_toward_gray(self) -> None:
        """青はグレー方向に移動する。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 2] = 255  # 純青

        result = anti_saturate(rgb, EINK_PALETTE)

        # 元の青 (0,0,255) よりもRとGが上がり、Bが下がるはず
        r, g, b = int(result[0, 0, 0]), int(result[0, 0, 1]), int(result[0, 0, 2])
        assert r > 0 or g > 0, f"グレー方向に移動していない: R={r}, G={g}, B={b}"

    def test_inside_convex_hull_unchanged(self) -> None:
        """凸包内部の色は変化しない。"""
        # パレット重心付近の色（内部にあるはず）
        centroid = np.mean(
            [[c.r, c.g, c.b] for c in EINK_PALETTE], axis=0,
        )
        rgb = np.full((2, 2, 3), 0, dtype=np.uint8)
        rgb[:, :, 0] = int(centroid[0])
        rgb[:, :, 1] = int(centroid[1])
        rgb[:, :, 2] = int(centroid[2])

        result = anti_saturate(rgb, EINK_PALETTE)
        diff = np.abs(result.astype(int) - rgb.astype(int))
        assert diff.max() <= 1, f"凸包内部の色が変化: diff={diff.max()}"

    def test_output_in_valid_range(self) -> None:
        """出力値が0-255範囲内。"""
        rgb = np.random.default_rng(99).integers(0, 256, (20, 30, 3), dtype=np.uint8)
        result = anti_saturate(rgb, EINK_PALETTE)
        assert result.min() >= 0
        assert result.max() <= 255

    def test_all_inside_image_unchanged(self) -> None:
        """全ピクセルが凸包内部の場合、画像がそのまま返る。"""
        # パレット重心付近の暗い色で画像を構成（確実に内部）
        centroid = np.mean(
            [[c.r, c.g, c.b] for c in EINK_PALETTE], axis=0,
        )
        rgb = np.full((5, 5, 3), 0, dtype=np.uint8)
        rgb[:, :, 0] = int(centroid[0])
        rgb[:, :, 1] = int(centroid[1])
        rgb[:, :, 2] = int(centroid[2])

        result = anti_saturate(rgb, EINK_PALETTE)
        diff = np.abs(result.astype(int) - rgb.astype(int))
        assert diff.max() <= 1

    def test_extreme_colors(self) -> None:
        """極端な色（マゼンタ、シアン等）が0-255範囲で出力される。"""
        extremes = np.array(
            [
                [[255, 0, 255], [0, 255, 255]],  # マゼンタ, シアン
                [[0, 128, 255], [128, 0, 255]],   # スカイブルー, パープル
            ],
            dtype=np.uint8,
        )
        result = anti_saturate(extremes, EINK_PALETTE)
        assert result.shape == extremes.shape
        assert result.dtype == np.uint8
        assert result.min() >= 0
        assert result.max() <= 255

    def test_1x1_image(self) -> None:
        """1x1画像が正常に処理される。"""
        rgb = np.array([[[0, 0, 255]]], dtype=np.uint8)
        result = anti_saturate(rgb, EINK_PALETTE)
        assert result.shape == (1, 1, 3)
        assert result.dtype == np.uint8

    def test_projection_stays_on_surface(self) -> None:
        """射影結果が四面体表面上（内部判定=True）にある。"""
        face_verts, face_normals = _build_tetrahedron_faces(_PALETTE_VERTS)

        outside_pts = np.array([
            [0.0, 0.0, 1.0],   # 純青
            [0.0, 1.0, 0.0],   # 純緑
            [0.5, 0.0, 0.5],   # パープル
            [0.0, 0.5, 0.5],   # ティール
        ])
        projected = _project_to_tetrahedron_surface(outside_pts, face_verts)

        # 射影結果は四面体上（内部 or 表面）にあるはず
        inside = _is_inside_tetrahedron(projected, face_verts, face_normals)
        assert inside.all(), (
            f"射影結果が四面体外部: {projected[~inside]}"
        )


# ---------------------------------------------------------------------------
# _closest_point_on_triangle 単体テスト
# ---------------------------------------------------------------------------

# テスト用三角形: v0=(0,0,0), v1=(1,0,0), v2=(0,1,0) — XY平面上
_TRI_V0 = np.array([0.0, 0.0, 0.0])
_TRI_V1 = np.array([1.0, 0.0, 0.0])
_TRI_V2 = np.array([0.0, 1.0, 0.0])


class TestClosestPointOnTriangle:
    """_closest_point_on_triangle の7リージョン網羅テスト。"""

    def test_region_face_interior(self) -> None:
        """面内部: 三角形の真上の点は面に垂直射影される。"""
        pts = np.array([[0.2, 0.2, 1.0]])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)
        np.testing.assert_allclose(result[0], [0.2, 0.2, 0.0], atol=1e-10)

    def test_region_vertex_a(self) -> None:
        """頂点A領域: v0の外側の点はv0に射影される。"""
        pts = np.array([[-1.0, -1.0, 0.0]])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)
        np.testing.assert_allclose(result[0], [0.0, 0.0, 0.0], atol=1e-10)

    def test_region_vertex_b(self) -> None:
        """頂点B領域: v1の外側の点はv1に射影される。"""
        pts = np.array([[2.0, -1.0, 0.0]])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)
        np.testing.assert_allclose(result[0], [1.0, 0.0, 0.0], atol=1e-10)

    def test_region_vertex_c(self) -> None:
        """頂点C領域: v2の外側の点はv2に射影される。"""
        pts = np.array([[-1.0, 2.0, 0.0]])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)
        np.testing.assert_allclose(result[0], [0.0, 1.0, 0.0], atol=1e-10)

    def test_region_edge_ab(self) -> None:
        """辺AB領域: v0-v1の下にある点は辺AB上に射影される。"""
        pts = np.array([[0.5, -1.0, 0.0]])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)
        np.testing.assert_allclose(result[0], [0.5, 0.0, 0.0], atol=1e-10)

    def test_region_edge_ac(self) -> None:
        """辺AC領域: v0-v2の左にある点は辺AC上に射影される。"""
        pts = np.array([[-1.0, 0.5, 0.0]])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)
        np.testing.assert_allclose(result[0], [0.0, 0.5, 0.0], atol=1e-10)

    def test_region_edge_bc(self) -> None:
        """辺BC領域: v1-v2の斜辺外側の点は辺BC上に射影される。"""
        pts = np.array([[1.0, 1.0, 0.0]])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)
        np.testing.assert_allclose(result[0], [0.5, 0.5, 0.0], atol=1e-10)

    def test_result_on_triangle_plane(self) -> None:
        """射影結果が三角形の平面上にある。"""
        pts = np.array([
            [0.3, 0.3, 5.0],
            [-2.0, -2.0, 3.0],
            [2.0, 2.0, -1.0],
        ])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)
        # XY平面上の三角形なのでZ=0
        np.testing.assert_allclose(result[:, 2], 0.0, atol=1e-10)

    def test_batch_multiple_points(self) -> None:
        """バッチ処理: 複数点を同時に正しく処理できる。"""
        pts = np.array([
            [-1.0, -1.0, 0.0],  # → v0
            [2.0, -1.0, 0.0],   # → v1
            [-1.0, 2.0, 0.0],   # → v2
            [0.2, 0.2, 1.0],    # → 面内部
        ])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)
        np.testing.assert_allclose(result[0], [0.0, 0.0, 0.0], atol=1e-10)
        np.testing.assert_allclose(result[1], [1.0, 0.0, 0.0], atol=1e-10)
        np.testing.assert_allclose(result[2], [0.0, 1.0, 0.0], atol=1e-10)
        np.testing.assert_allclose(result[3], [0.2, 0.2, 0.0], atol=1e-10)

    def test_result_is_nearest(self) -> None:
        """射影結果が三角形上の他の点より近いことを確認。"""
        pts = np.array([[0.8, 0.8, 0.5]])
        result = _closest_point_on_triangle(pts, _TRI_V0, _TRI_V1, _TRI_V2)

        # 結果への距離
        dist_result = np.linalg.norm(pts[0] - result[0])

        # 三角形上のサンプル点との比較
        samples = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.33, 0.33, 0.0],
        ])
        for s in samples:
            dist_s = np.linalg.norm(pts[0] - s)
            assert dist_result <= dist_s + 1e-10


# ---------------------------------------------------------------------------
# Centroid Clip（重心方向レイキャスト）テスト
# ---------------------------------------------------------------------------


class TestClipViaCentroid:
    """_clip_via_centroid のテスト。"""

    def test_fallback_for_centroid_point(self) -> None:
        """重心自身を入力した場合、フォールバック処理で結果を返す。"""
        face_verts, face_normals = _build_tetrahedron_faces(_PALETTE_VERTS)
        centroid = _PALETTE_VERTS.mean(axis=0)
        pts = centroid.reshape(1, 3)
        result = _clip_via_centroid(pts, centroid, face_verts, face_normals)
        assert result.shape == (1, 3)
        # フォールバック（最近点射影）の結果が返る
        inside = _is_inside_tetrahedron(result, face_verts, face_normals)
        assert inside[0]

    def test_ray_hits_surface(self) -> None:
        """外部点がレイキャストで四面体表面に到達する。"""
        face_verts, face_normals = _build_tetrahedron_faces(_PALETTE_VERTS)
        centroid = _PALETTE_VERTS.mean(axis=0)

        outside_pts = np.array([
            [0.0, 0.0, 1.0],   # 純青
            [0.0, 1.0, 0.0],   # 純緑
            [0.5, 0.0, 0.5],   # パープル
        ])
        result = _clip_via_centroid(
            outside_pts, centroid, face_verts, face_normals,
        )
        assert result.shape == (3, 3)
        # 結果は四面体表面上（内部判定=True）
        inside = _is_inside_tetrahedron(result, face_verts, face_normals)
        assert inside.all(), f"表面外の結果: {result[~inside]}"


class TestAntiSaturateCentroid:
    """anti_saturate_centroid のテスト。"""

    def test_output_shape_and_dtype(self) -> None:
        """出力のshape/dtypeが入力と一致。"""
        rgb = np.random.default_rng(42).integers(
            0, 256, (10, 15, 3), dtype=np.uint8,
        )
        result = anti_saturate_centroid(rgb, EINK_PALETTE)
        assert result.shape == (10, 15, 3)
        assert result.dtype == np.uint8

    def test_inside_unchanged(self) -> None:
        """凸包内部のピクセルは変化しない。"""
        centroid = np.mean(
            [[c.r, c.g, c.b] for c in EINK_PALETTE], axis=0,
        )
        rgb = np.full((2, 2, 3), 0, dtype=np.uint8)
        rgb[:, :, 0] = int(centroid[0])
        rgb[:, :, 1] = int(centroid[1])
        rgb[:, :, 2] = int(centroid[2])

        result = anti_saturate_centroid(rgb, EINK_PALETTE)
        diff = np.abs(result.astype(int) - rgb.astype(int))
        assert diff.max() <= 1, f"内部の色が変化: diff={diff.max()}"

    def test_palette_vertices_unchanged(self) -> None:
        """パレット頂点は変化しない。"""
        for color in EINK_PALETTE:
            rgb = np.full((2, 2, 3), 0, dtype=np.uint8)
            rgb[:, :, 0] = color.r
            rgb[:, :, 1] = color.g
            rgb[:, :, 2] = color.b
            result = anti_saturate_centroid(rgb, EINK_PALETTE)
            diff = np.abs(result.astype(int) - rgb.astype(int))
            assert diff.max() <= 1, (
                f"パレット色 {color} が変化: diff={diff.max()}"
            )

    def test_blue_has_warm_tint(self) -> None:
        """青の射影結果が R > B（暖色寄り）。

        重心方向レイキャストは色のある面に交差するため、
        Anti-Saturation（最近点射影でグレー化）と異なり暖色成分を持つ。
        """
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 2] = 255  # 純青

        result = anti_saturate_centroid(rgb, EINK_PALETTE)
        r, g, b = int(result[0, 0, 0]), int(result[0, 0, 1]), int(result[0, 0, 2])
        assert r > b, f"暖色成分なし: R={r}, G={g}, B={b}"

    def test_green_retains_color(self) -> None:
        """緑の射影結果が彩度を持つ。"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        rgb[:, :, 1] = 200  # 純緑

        result = anti_saturate_centroid(rgb, EINK_PALETTE)
        r, g, b = int(result[0, 0, 0]), int(result[0, 0, 1]), int(result[0, 0, 2])
        max_diff = max(abs(r - g), abs(g - b), abs(r - b))
        assert max_diff > 5, f"完全脱彩度化: R={r}, G={g}, B={b}"

    def test_different_colors_give_different_results(self) -> None:
        """異なる色が異なる結果になる。"""
        blue = np.zeros((2, 2, 3), dtype=np.uint8)
        blue[:, :, 2] = 255

        green = np.zeros((2, 2, 3), dtype=np.uint8)
        green[:, :, 1] = 200

        result_blue = anti_saturate_centroid(blue, EINK_PALETTE)
        result_green = anti_saturate_centroid(green, EINK_PALETTE)
        assert not np.array_equal(result_blue, result_green)

    def test_output_on_surface(self) -> None:
        """外部点の射影結果が四面体表面上にある。"""
        face_verts, face_normals = _build_tetrahedron_faces(_PALETTE_VERTS)

        # 外部色を含む画像
        extremes = np.array(
            [
                [[0, 0, 255], [0, 200, 0]],
                [[255, 0, 255], [0, 255, 255]],
            ],
            dtype=np.uint8,
        )
        result = anti_saturate_centroid(extremes, EINK_PALETTE)

        # 結果を正規化して内部判定
        pixels = result.reshape(-1, 3).astype(np.float64) / 255.0
        inside = _is_inside_tetrahedron(pixels, face_verts, face_normals)
        assert inside.all(), (
            f"表面外のピクセル: {pixels[~inside]}"
        )


# ---------------------------------------------------------------------------
# apply_illuminant（色付き照明シミュレーション）テスト
# ---------------------------------------------------------------------------


class TestApplyIlluminant:
    """apply_illuminant のテスト。"""

    def test_output_shape_and_dtype(self) -> None:
        """出力のshape/dtypeが入力と一致。"""
        rgb = np.random.default_rng(42).integers(0, 256, (10, 15, 3), dtype=np.uint8)
        result = apply_illuminant(rgb)
        assert result.shape == (10, 15, 3)
        assert result.dtype == np.uint8

    def test_identity_with_all_ones(self) -> None:
        """スケール (1, 1, 1) で恒等変換。"""
        rgb = np.random.default_rng(42).integers(0, 256, (5, 5, 3), dtype=np.uint8)
        result = apply_illuminant(rgb, r_scale=1.0, g_scale=1.0, b_scale=1.0)
        np.testing.assert_array_equal(result, rgb)

    def test_all_zeros_gives_black(self) -> None:
        """スケール (0, 0, 0) で全黒。"""
        rgb = np.random.default_rng(42).integers(0, 256, (5, 5, 3), dtype=np.uint8)
        result = apply_illuminant(rgb, r_scale=0.0, g_scale=0.0, b_scale=0.0)
        # 丸め (+0.5) があるため、元が0以外のピクセルは1になりうる
        assert result.max() <= 1

    def test_r_scale_only(self) -> None:
        """R=1.0, G=0, B=0 で赤チャンネルのみ残り、G/Bは消える。"""
        rgb = np.array([[[100, 150, 200]]], dtype=np.uint8)
        result = apply_illuminant(rgb, r_scale=1.0, g_scale=0.0, b_scale=0.0)
        # 輝度補正でRはブーストされるがG/Bは0のまま
        assert result[0, 0, 0] > 100
        assert result[0, 0, 1] <= 1
        assert result[0, 0, 2] <= 1

    def test_output_clipped_to_255(self) -> None:
        """出力値が0-255範囲内。"""
        rgb = np.full((2, 2, 3), 255, dtype=np.uint8)
        result = apply_illuminant(rgb, r_scale=1.0, g_scale=1.0, b_scale=1.0)
        assert result.min() >= 0
        assert result.max() <= 255

    def test_default_parameters_warm_bias(self) -> None:
        """デフォルトパラメータで R >= G >= B（暖色バイアス）。"""
        rgb = np.full((1, 1, 3), 200, dtype=np.uint8)
        result = apply_illuminant(rgb)
        r, g, b = int(result[0, 0, 0]), int(result[0, 0, 1]), int(result[0, 0, 2])
        assert r >= g >= b, f"暖色バイアスなし: R={r}, G={g}, B={b}"

    def test_white_becomes_warm(self) -> None:
        """白 → 暖色（デフォルト）。"""
        rgb = np.full((1, 1, 3), 255, dtype=np.uint8)
        result = apply_illuminant(rgb)
        r, g, b = int(result[0, 0, 0]), int(result[0, 0, 1]), int(result[0, 0, 2])
        assert r == 255, f"R チャンネルが変化: {r}"
        assert g < 255, f"G チャンネルが変化なし: {g}"
        assert b < g, f"B >= G: R={r}, G={g}, B={b}"

    def test_1x1_image(self) -> None:
        """1x1画像が正常に処理される。"""
        rgb = np.array([[[128, 64, 32]]], dtype=np.uint8)
        result = apply_illuminant(rgb)
        assert result.shape == (1, 1, 3)
        assert result.dtype == np.uint8

    def test_white_preserve_zero_no_effect(self) -> None:
        """white_preserve=0 で白保持なし（従来動作）。"""
        rgb = np.full((1, 1, 3), 255, dtype=np.uint8)
        result_no = apply_illuminant(rgb, white_preserve=0.0)
        result_default = apply_illuminant(rgb)
        np.testing.assert_array_equal(result_no, result_default)

    def test_white_preserve_keeps_white(self) -> None:
        """white_preserve=1 で白ピクセルが元のまま保持される。"""
        rgb = np.full((1, 1, 3), 255, dtype=np.uint8)
        result = apply_illuminant(rgb, white_preserve=1.0)
        # 白ピクセルは lum=1.0, preserve=1.0 なので元の色が完全保持
        np.testing.assert_array_equal(result, rgb)

    def test_white_preserve_dark_pixel_unaffected(self) -> None:
        """白保持は暗いピクセルにほとんど影響しない。"""
        rgb = np.array([[[50, 50, 50]]], dtype=np.uint8)
        result_no = apply_illuminant(rgb, white_preserve=0.0)
        result_wp = apply_illuminant(rgb, white_preserve=1.0)
        # 暗いピクセル(lum≈0.2) → preserve = 0.04 → ほぼ変化なし
        diff = np.abs(result_no.astype(int) - result_wp.astype(int))
        assert diff.max() <= 5, f"暗部に白保持が影響しすぎ: diff={diff.max()}"

    def test_white_preserve_gradient(self) -> None:
        """明るいほど白保持が強い（勾配テスト）。"""
        # 暗い→明るいグラデーション
        dark = np.full((1, 1, 3), 50, dtype=np.uint8)
        bright = np.full((1, 1, 3), 240, dtype=np.uint8)
        dark_no = apply_illuminant(dark, white_preserve=0.0)
        dark_wp = apply_illuminant(dark, white_preserve=1.0)
        bright_no = apply_illuminant(bright, white_preserve=0.0)
        bright_wp = apply_illuminant(bright, white_preserve=1.0)
        # 明るいピクセルの方が白保持の影響が大きい
        diff_dark = np.abs(dark_no.astype(int) - dark_wp.astype(int)).max()
        diff_bright = np.abs(bright_no.astype(int) - bright_wp.astype(int)).max()
        assert diff_bright > diff_dark
