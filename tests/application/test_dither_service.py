"""dither_service.py / image_converter.py のテスト。"""

import tempfile
from pathlib import Path

import numpy as np

from epaper_palette_dither.application.dither_service import DitherService
from epaper_palette_dither.application.image_converter import ImageConverter
from epaper_palette_dither.domain.color import EINK_PALETTE, EINK_PALETTE_PERCEIVED
from epaper_palette_dither.domain.image_model import ColorMode, ImageSpec
from epaper_palette_dither.infrastructure.image_io import save_image


class TestDitherService:
    def setup_method(self) -> None:
        self.service = DitherService()

    def test_output_shape(self) -> None:
        array = np.zeros((10, 20, 3), dtype=np.uint8)
        result = self.service.dither_array(array, EINK_PALETTE)
        assert result.shape == (10, 20, 3)
        assert result.dtype == np.uint8

    def test_output_only_palette_colors(self) -> None:
        array = np.random.randint(0, 256, (5, 5, 3), dtype=np.uint8)
        result = self.service.dither_array(array, EINK_PALETTE)
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(5):
            for x in range(5):
                pixel = tuple(result[y, x])
                assert pixel in palette_set

    def test_fast_output_shape(self) -> None:
        array = np.zeros((10, 20, 3), dtype=np.uint8)
        result = self.service.dither_array_fast(array, EINK_PALETTE)
        assert result.shape == (10, 20, 3)
        assert result.dtype == np.uint8

    def test_fast_output_only_palette_colors(self) -> None:
        array = np.random.randint(0, 256, (5, 5, 3), dtype=np.uint8)
        result = self.service.dither_array_fast(array, EINK_PALETTE)
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(5):
            for x in range(5):
                pixel = tuple(result[y, x])
                assert pixel in palette_set

    def test_white_image_stays_white(self) -> None:
        array = np.full((4, 4, 3), 255, dtype=np.uint8)
        result = self.service.dither_array_fast(array, EINK_PALETTE)
        expected = np.full((4, 4, 3), 255, dtype=np.uint8)
        np.testing.assert_array_equal(result, expected)


class TestImageConverter:
    def test_convert_from_file(self) -> None:
        array = np.random.randint(0, 256, (50, 80, 3), dtype=np.uint8)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = Path(f.name)
        save_image(array, path)

        converter = ImageConverter()
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert(path, spec)

        assert result.shape[0] <= 15
        assert result.shape[1] <= 20
        assert result.dtype == np.uint8

        # 出力が4色のみ
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(result.shape[0]):
            for x in range(result.shape[1]):
                assert tuple(result[y, x]) in palette_set

        path.unlink()

    def test_convert_array(self) -> None:
        array = np.random.randint(0, 256, (50, 80, 3), dtype=np.uint8)
        converter = ImageConverter()
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_array(array, spec)

        assert result.shape == (15, 20, 3)
        assert result.dtype == np.uint8

    def test_progress_callback(self) -> None:
        array = np.zeros((10, 10, 3), dtype=np.uint8)
        converter = ImageConverter()
        spec = ImageSpec(target_width=10, target_height=10)

        stages: list[tuple[str, float]] = []
        converter.convert_array(array, spec, progress=lambda s, p: stages.append((s, p)))

        assert len(stages) >= 2
        assert stages[-1][1] == 1.0  # 最後は完了

    def test_convert_array_gamut_only_shape(self) -> None:
        array = np.random.randint(0, 256, (50, 80, 3), dtype=np.uint8)
        converter = ImageConverter()
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_array_gamut_only(array, spec)

        assert result.shape == (15, 20, 3)
        assert result.dtype == np.uint8

    def test_convert_array_gamut_only_not_quantized(self) -> None:
        """ガマットのみ変換は4色に量子化されない（ディザリングなし）。"""
        array = np.random.randint(0, 256, (50, 80, 3), dtype=np.uint8)
        converter = ImageConverter()
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_array_gamut_only(array, spec)

        # ガマットマッピングのみなのでパレット4色に限定されないことを確認
        unique_colors = {tuple(result[y, x]) for y in range(result.shape[0]) for x in range(result.shape[1])}
        assert len(unique_colors) > 4

    def test_convert_gamut_only_from_file(self) -> None:
        array = np.random.randint(0, 256, (50, 80, 3), dtype=np.uint8)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = Path(f.name)
        save_image(array, path)

        converter = ImageConverter()
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_gamut_only(path, spec)

        assert result.shape[0] <= 15
        assert result.shape[1] <= 20
        assert result.dtype == np.uint8

        path.unlink()

    def test_gamut_only_progress_callback(self) -> None:
        array = np.zeros((10, 10, 3), dtype=np.uint8)
        converter = ImageConverter()
        spec = ImageSpec(target_width=10, target_height=10)

        stages: list[tuple[str, float]] = []
        converter.convert_array_gamut_only(
            array, spec, progress=lambda s, p: stages.append((s, p)),
        )

        assert len(stages) >= 2
        assert stages[-1][1] == 1.0
        # ディザリングステージが含まれないことを確認
        stage_names = [s for s, _ in stages]
        assert "ディザリング" not in stage_names

    def test_color_mode_default_is_grayout(self) -> None:
        """デフォルトのカラーモードはGRAYOUT。"""
        converter = ImageConverter()
        assert converter.color_mode == ColorMode.GRAYOUT

    def test_color_mode_setter(self) -> None:
        """color_modeを切り替えられる。"""
        converter = ImageConverter()
        converter.color_mode = ColorMode.ANTI_SATURATION
        assert converter.color_mode == ColorMode.ANTI_SATURATION
        converter.color_mode = ColorMode.GRAYOUT
        assert converter.color_mode == ColorMode.GRAYOUT

    def test_convert_array_with_anti_saturation(self) -> None:
        """ANTI_SATURATIONモードでconvert_arrayが動作する。"""
        array = np.random.default_rng(42).integers(
            0, 256, (50, 80, 3), dtype=np.uint8,
        )
        converter = ImageConverter()
        converter.color_mode = ColorMode.ANTI_SATURATION
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_array(array, spec)

        assert result.shape == (15, 20, 3)
        assert result.dtype == np.uint8
        # ディザリング済みなのでパレット4色のみ
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(result.shape[0]):
            for x in range(result.shape[1]):
                assert tuple(result[y, x]) in palette_set

    def test_gamut_only_with_anti_saturation(self) -> None:
        """ANTI_SATURATIONモードでgamut_onlyが動作する。"""
        array = np.random.default_rng(42).integers(
            0, 256, (50, 80, 3), dtype=np.uint8,
        )
        converter = ImageConverter()
        converter.color_mode = ColorMode.ANTI_SATURATION
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_array_gamut_only(array, spec)

        assert result.shape == (15, 20, 3)
        assert result.dtype == np.uint8

    def test_mode_switch_produces_different_results(self) -> None:
        """GRAYOUTとANTI_SATURATIONで結果が異なる。"""
        # 緑の画像（両モードで差が出やすい色）
        array = np.zeros((10, 10, 3), dtype=np.uint8)
        array[:, :, 1] = 200

        converter = ImageConverter()
        spec = ImageSpec(target_width=10, target_height=10)

        converter.color_mode = ColorMode.GRAYOUT
        result_grayout = converter.convert_array_gamut_only(array, spec)

        converter.color_mode = ColorMode.ANTI_SATURATION
        result_anti_sat = converter.convert_array_gamut_only(array, spec)

        # 2つのモードで結果が異なるはず
        assert not np.array_equal(result_grayout, result_anti_sat)

    def test_convert_array_with_centroid_clip(self) -> None:
        """CENTROID_CLIPモードでconvert_arrayが動作する。"""
        array = np.random.default_rng(42).integers(
            0, 256, (50, 80, 3), dtype=np.uint8,
        )
        converter = ImageConverter()
        converter.color_mode = ColorMode.CENTROID_CLIP
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_array(array, spec)

        assert result.shape == (15, 20, 3)
        assert result.dtype == np.uint8
        # ディザリング済みなのでパレット4色のみ
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(result.shape[0]):
            for x in range(result.shape[1]):
                assert tuple(result[y, x]) in palette_set

    def test_gamut_only_with_centroid_clip(self) -> None:
        """CENTROID_CLIPモードでgamut_onlyが動作する。"""
        array = np.random.default_rng(42).integers(
            0, 256, (50, 80, 3), dtype=np.uint8,
        )
        converter = ImageConverter()
        converter.color_mode = ColorMode.CENTROID_CLIP
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_array_gamut_only(array, spec)

        assert result.shape == (15, 20, 3)
        assert result.dtype == np.uint8

    def test_centroid_clip_differs_from_anti_saturation(self) -> None:
        """CENTROID_CLIPとANTI_SATURATIONで結果が異なる。"""
        # 青の画像（2つのモードで差が出やすい色）
        array = np.zeros((10, 10, 3), dtype=np.uint8)
        array[:, :, 2] = 255

        converter = ImageConverter()
        spec = ImageSpec(target_width=10, target_height=10)

        converter.color_mode = ColorMode.ANTI_SATURATION
        result_anti_sat = converter.convert_array_gamut_only(array, spec)

        converter.color_mode = ColorMode.CENTROID_CLIP
        result_centroid = converter.convert_array_gamut_only(array, spec)

        assert not np.array_equal(result_anti_sat, result_centroid)

    def test_illuminant_default_values(self) -> None:
        """Illuminant のデフォルト値確認。"""
        converter = ImageConverter()
        assert converter.illuminant_red == 1.0
        assert converter.illuminant_yellow == 1.0
        assert converter.illuminant_white == 1.0

    def test_illuminant_setter_clamps(self) -> None:
        """Illuminant のセッターが 0.0〜1.0 にクランプする。"""
        converter = ImageConverter()
        converter.illuminant_red = -0.5
        assert converter.illuminant_red == 0.0
        converter.illuminant_red = 1.5
        assert converter.illuminant_red == 1.0
        converter.illuminant_yellow = -0.1
        assert converter.illuminant_yellow == 0.0
        converter.illuminant_yellow = 2.0
        assert converter.illuminant_yellow == 1.0
        converter.illuminant_white = -0.5
        assert converter.illuminant_white == 0.0
        converter.illuminant_white = 1.5
        assert converter.illuminant_white == 1.0

    def test_convert_array_with_illuminant(self) -> None:
        """ILLUMINANTモードでconvert_arrayが動作する。"""
        array = np.random.default_rng(42).integers(
            0, 256, (50, 80, 3), dtype=np.uint8,
        )
        converter = ImageConverter()
        converter.color_mode = ColorMode.ILLUMINANT
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_array(array, spec)

        assert result.shape == (15, 20, 3)
        assert result.dtype == np.uint8
        # ディザリング済みなのでパレット4色のみ
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(result.shape[0]):
            for x in range(result.shape[1]):
                assert tuple(result[y, x]) in palette_set

    def test_gamut_only_with_illuminant(self) -> None:
        """ILLUMINANTモードでgamut_onlyが動作する。"""
        array = np.random.default_rng(42).integers(
            0, 256, (50, 80, 3), dtype=np.uint8,
        )
        converter = ImageConverter()
        converter.color_mode = ColorMode.ILLUMINANT
        spec = ImageSpec(target_width=20, target_height=15)
        result = converter.convert_array_gamut_only(array, spec)

        assert result.shape == (15, 20, 3)
        assert result.dtype == np.uint8

    def test_illuminant_differs_from_grayout(self) -> None:
        """ILLUMINANTとGRAYOUTで結果が異なる。"""
        array = np.zeros((10, 10, 3), dtype=np.uint8)
        array[:, :, 2] = 255  # 青

        converter = ImageConverter()
        spec = ImageSpec(target_width=10, target_height=10)

        converter.color_mode = ColorMode.GRAYOUT
        result_grayout = converter.convert_array_gamut_only(array, spec)

        converter.color_mode = ColorMode.ILLUMINANT
        result_illuminant = converter.convert_array_gamut_only(array, spec)

        assert not np.array_equal(result_grayout, result_illuminant)

    def test_error_clamp_default(self) -> None:
        """error_clamp デフォルト 85。"""
        converter = ImageConverter()
        assert converter.error_clamp == 85

    def test_red_penalty_default(self) -> None:
        """red_penalty デフォルト 10.0。"""
        converter = ImageConverter()
        assert converter.red_penalty == 10.0

    def test_yellow_penalty_default(self) -> None:
        """yellow_penalty デフォルト 15.0。"""
        converter = ImageConverter()
        assert converter.yellow_penalty == 15.0

    def test_error_clamp_setter_clamps(self) -> None:
        """error_clamp の範囲クランプ (0-128)。"""
        converter = ImageConverter()
        converter.error_clamp = -10
        assert converter.error_clamp == 0
        converter.error_clamp = 200
        assert converter.error_clamp == 128
        converter.error_clamp = 50
        assert converter.error_clamp == 50

    def test_red_penalty_setter_clamps(self) -> None:
        """red_penalty の範囲クランプ (0-100)。"""
        converter = ImageConverter()
        converter.red_penalty = -5.0
        assert converter.red_penalty == 0.0
        converter.red_penalty = 150.0
        assert converter.red_penalty == 100.0
        converter.red_penalty = 25.5
        assert converter.red_penalty == 25.5

    def test_yellow_penalty_setter_clamps(self) -> None:
        """yellow_penalty の範囲クランプ (0-100)。"""
        converter = ImageConverter()
        converter.yellow_penalty = -5.0
        assert converter.yellow_penalty == 0.0
        converter.yellow_penalty = 150.0
        assert converter.yellow_penalty == 100.0
        converter.yellow_penalty = 25.5
        assert converter.yellow_penalty == 25.5

    def test_dither_with_error_clamp(self) -> None:
        """error_clamp > 0 で dither_array_fast が動作する。"""
        array = np.random.default_rng(42).integers(0, 256, (8, 8, 3), dtype=np.uint8)
        converter = ImageConverter()
        converter.error_clamp = 30
        spec = ImageSpec(target_width=8, target_height=8)
        result = converter.convert_array(array, spec)

        assert result.shape == (8, 8, 3)
        assert result.dtype == np.uint8
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(result.shape[0]):
            for x in range(result.shape[1]):
                assert tuple(result[y, x]) in palette_set

    def test_dither_with_red_penalty(self) -> None:
        """red_penalty > 0 で dither_array_fast が動作する。"""
        array = np.random.default_rng(42).integers(0, 256, (8, 8, 3), dtype=np.uint8)
        converter = ImageConverter()
        converter.red_penalty = 20.0
        spec = ImageSpec(target_width=8, target_height=8)
        result = converter.convert_array(array, spec)

        assert result.shape == (8, 8, 3)
        assert result.dtype == np.uint8
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(result.shape[0]):
            for x in range(result.shape[1]):
                assert tuple(result[y, x]) in palette_set

    def test_dither_with_yellow_penalty(self) -> None:
        """yellow_penalty > 0 で dither_array_fast が動作する。"""
        array = np.random.default_rng(42).integers(0, 256, (8, 8, 3), dtype=np.uint8)
        converter = ImageConverter()
        converter.yellow_penalty = 20.0
        spec = ImageSpec(target_width=8, target_height=8)
        result = converter.convert_array(array, spec)

        assert result.shape == (8, 8, 3)
        assert result.dtype == np.uint8
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(result.shape[0]):
            for x in range(result.shape[1]):
                assert tuple(result[y, x]) in palette_set

    def test_dither_with_all_params(self) -> None:
        """error_clamp + red_penalty + yellow_penalty 併用で動作する。"""
        array = np.random.default_rng(42).integers(0, 256, (8, 8, 3), dtype=np.uint8)
        converter = ImageConverter()
        converter.error_clamp = 30
        converter.red_penalty = 20.0
        converter.yellow_penalty = 20.0
        spec = ImageSpec(target_width=8, target_height=8)
        result = converter.convert_array(array, spec)

        assert result.shape == (8, 8, 3)
        assert result.dtype == np.uint8
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(result.shape[0]):
            for x in range(result.shape[1]):
                assert tuple(result[y, x]) in palette_set


class TestDitherServiceParams:
    def setup_method(self) -> None:
        self.service = DitherService()

    def test_error_clamp_reduces_error_spread(self) -> None:
        """error_clamp で誤差拡散が制限される。"""
        # 白画像 — error_clamp なし vs あり
        array = np.full((8, 8, 3), 255, dtype=np.uint8)
        result_no_clamp = self.service.dither_array_fast(array, EINK_PALETTE, error_clamp=0)
        result_with_clamp = self.service.dither_array_fast(array, EINK_PALETTE, error_clamp=30)

        # 白画像はどちらも全白になるはず
        expected = np.full((8, 8, 3), 255, dtype=np.uint8)
        np.testing.assert_array_equal(result_no_clamp, expected)
        np.testing.assert_array_equal(result_with_clamp, expected)

    def test_red_penalty_reduces_red_in_bright(self) -> None:
        """red_penalty で明部の赤ドットが減る。"""
        # 明るめの暖色画像（赤がディザに出やすい）
        array = np.full((8, 8, 3), 220, dtype=np.uint8)
        array[:, :, 0] = 240  # R チャンネル強め

        result_no_pen = self.service.dither_array_fast(
            array, EINK_PALETTE, error_clamp=0, red_penalty=0.0,
        )
        result_with_pen = self.service.dither_array_fast(
            array, EINK_PALETTE, error_clamp=0, red_penalty=50.0,
        )

        # 赤ピクセル (200,0,0) の数を比較
        red_tuple = (200, 0, 0)
        red_count_no = sum(
            1 for y in range(8) for x in range(8)
            if tuple(result_no_pen[y, x]) == red_tuple
        )
        red_count_with = sum(
            1 for y in range(8) for x in range(8)
            if tuple(result_with_pen[y, x]) == red_tuple
        )

        # ペナルティありで赤ピクセルが同じか減るはず
        assert red_count_with <= red_count_no

    def test_yellow_penalty_reduces_yellow_in_dark(self) -> None:
        """yellow_penalty で暗部の黄ドットが減る。"""
        # 暗めの画像（黄がディザに出やすい）
        array = np.full((8, 8, 3), 40, dtype=np.uint8)
        array[:, :, 1] = 60  # G チャンネル少し強め

        result_no_pen = self.service.dither_array_fast(
            array, EINK_PALETTE, error_clamp=0, red_penalty=0.0, yellow_penalty=0.0,
        )
        result_with_pen = self.service.dither_array_fast(
            array, EINK_PALETTE, error_clamp=0, red_penalty=0.0, yellow_penalty=50.0,
        )

        # 黄ピクセル (255,255,0) の数を比較
        yellow_tuple = (255, 255, 0)
        yellow_count_no = sum(
            1 for y in range(8) for x in range(8)
            if tuple(result_no_pen[y, x]) == yellow_tuple
        )
        yellow_count_with = sum(
            1 for y in range(8) for x in range(8)
            if tuple(result_with_pen[y, x]) == yellow_tuple
        )

        # ペナルティありで黄ピクセルが同じか減るはず
        assert yellow_count_with <= yellow_count_no


class TestDitherServicePerceived:
    """知覚パレット対応のディザリングテスト。"""

    def setup_method(self) -> None:
        self.service = DitherService()

    def test_perceived_output_only_hardware_palette(self) -> None:
        """知覚パレット有効時も出力はハードウェアパレット色のみ。"""
        array = np.random.default_rng(42).integers(0, 256, (8, 8, 3), dtype=np.uint8)
        result = self.service.dither_array_fast(
            array, EINK_PALETTE, perceived_palette=EINK_PALETTE_PERCEIVED,
        )
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(8):
            for x in range(8):
                assert tuple(result[y, x]) in palette_set

    def test_perceived_differs_from_normal(self) -> None:
        """知覚パレット有無で結果が異なる。"""
        array = np.random.default_rng(42).integers(0, 256, (8, 8, 3), dtype=np.uint8)
        result_normal = self.service.dither_array_fast(array, EINK_PALETTE)
        result_perceived = self.service.dither_array_fast(
            array, EINK_PALETTE, perceived_palette=EINK_PALETTE_PERCEIVED,
        )
        assert not np.array_equal(result_normal, result_perceived)

    def test_perceived_with_params(self) -> None:
        """知覚パレット + error_clamp + penalty 併用で動作。"""
        array = np.random.default_rng(42).integers(0, 256, (8, 8, 3), dtype=np.uint8)
        result = self.service.dither_array_fast(
            array, EINK_PALETTE,
            error_clamp=50, red_penalty=10.0, yellow_penalty=15.0,
            perceived_palette=EINK_PALETTE_PERCEIVED,
        )
        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(8):
            for x in range(8):
                assert tuple(result[y, x]) in palette_set

    def test_perceived_shape_preserved(self) -> None:
        """知覚パレット有効時も形状が維持される。"""
        array = np.zeros((12, 16, 3), dtype=np.uint8)
        result = self.service.dither_array_fast(
            array, EINK_PALETTE, perceived_palette=EINK_PALETTE_PERCEIVED,
        )
        assert result.shape == (12, 16, 3)
        assert result.dtype == np.uint8


class TestImageConverterPerceived:
    """ImageConverter の知覚パレット対応テスト。"""

    def test_default_perceived_is_false(self) -> None:
        """デフォルトでは知覚パレット無効。"""
        converter = ImageConverter()
        assert converter.use_perceived_palette is False

    def test_perceived_setter(self) -> None:
        """use_perceived_palette プロパティのセッター。"""
        converter = ImageConverter()
        converter.use_perceived_palette = True
        assert converter.use_perceived_palette is True
        converter.use_perceived_palette = False
        assert converter.use_perceived_palette is False

    def test_perceived_convert_output_palette_only(self) -> None:
        """知覚パレット有効時も変換結果はハードウェアパレット色のみ。"""
        array = np.random.default_rng(42).integers(0, 256, (20, 30, 3), dtype=np.uint8)
        converter = ImageConverter()
        converter.use_perceived_palette = True
        spec = ImageSpec(target_width=10, target_height=8)
        result = converter.convert_array(array, spec)

        palette_set = {c.to_tuple() for c in EINK_PALETTE}
        for y in range(result.shape[0]):
            for x in range(result.shape[1]):
                assert tuple(result[y, x]) in palette_set

    def test_perceived_convert_differs(self) -> None:
        """知覚パレット有無で変換結果が異なる。"""
        array = np.random.default_rng(42).integers(0, 256, (20, 30, 3), dtype=np.uint8)
        spec = ImageSpec(target_width=10, target_height=8)

        converter = ImageConverter()
        result_normal = converter.convert_array(array, spec)

        converter.use_perceived_palette = True
        result_perceived = converter.convert_array(array, spec)

        assert not np.array_equal(result_normal, result_perceived)

    def test_perceived_gamut_only_unchanged(self) -> None:
        """簡易版: ガマットマッピングのみは知覚パレットの影響を受けない。"""
        array = np.random.default_rng(42).integers(0, 256, (20, 30, 3), dtype=np.uint8)
        spec = ImageSpec(target_width=10, target_height=8)

        converter = ImageConverter()
        result_normal = converter.convert_array_gamut_only(array, spec)

        converter.use_perceived_palette = True
        result_perceived = converter.convert_array_gamut_only(array, spec)

        # 簡易版ではガマットマッピングに知覚パレットを使わないため結果が同一
        np.testing.assert_array_equal(result_normal, result_perceived)

    def test_perceived_with_each_color_mode(self) -> None:
        """全ColorModeで知覚パレット有効時にディザリングが動作する。"""
        array = np.random.default_rng(42).integers(0, 256, (20, 30, 3), dtype=np.uint8)
        spec = ImageSpec(target_width=10, target_height=8)
        palette_set = {c.to_tuple() for c in EINK_PALETTE}

        for mode in ColorMode:
            converter = ImageConverter()
            converter.color_mode = mode
            converter.use_perceived_palette = True
            result = converter.convert_array(array, spec)

            assert result.dtype == np.uint8, f"Failed for {mode}"
            for y in range(result.shape[0]):
                for x in range(result.shape[1]):
                    assert tuple(result[y, x]) in palette_set, (
                        f"Non-palette pixel at ({x},{y}) for {mode}"
                    )
