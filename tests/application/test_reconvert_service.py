"""reconvert_service.py のテスト。"""

import numpy as np

from epaper_palette_dither.domain.color import EINK_PALETTE
from epaper_palette_dither.domain.image_model import ColorMode
from epaper_palette_dither.application.reconvert_service import ReconvertService


class TestReconvertService:
    """ReconvertService のテスト。"""

    def setup_method(self) -> None:
        self.service = ReconvertService()
        rng = np.random.default_rng(42)
        palette_rgb = np.array(
            [c.to_tuple() for c in EINK_PALETTE], dtype=np.uint8,
        )
        indices = rng.integers(0, len(EINK_PALETTE), (20, 30))
        self.dithered = palette_rgb[indices]

    def test_output_shape_and_dtype_grayout(self) -> None:
        result = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.GRAYOUT,
        )
        assert result.shape == self.dithered.shape
        assert result.dtype == np.uint8

    def test_output_shape_and_dtype_illuminant(self) -> None:
        result = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.ILLUMINANT,
        )
        assert result.shape == self.dithered.shape
        assert result.dtype == np.uint8

    def test_output_shape_and_dtype_anti_saturation(self) -> None:
        result = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.ANTI_SATURATION,
        )
        assert result.shape == self.dithered.shape
        assert result.dtype == np.uint8

    def test_output_shape_and_dtype_centroid_clip(self) -> None:
        result = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.CENTROID_CLIP,
        )
        assert result.shape == self.dithered.shape
        assert result.dtype == np.uint8

    def test_blur_changes_values(self) -> None:
        result = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.GRAYOUT,
        )
        assert not np.array_equal(result, self.dithered)

    def test_different_blur_radius_gives_different_result(self) -> None:
        result_small = self.service.reconvert_array(
            self.dithered, blur_radius=1, color_mode=ColorMode.GRAYOUT,
        )
        result_large = self.service.reconvert_array(
            self.dithered, blur_radius=5, color_mode=ColorMode.GRAYOUT,
        )
        assert not np.array_equal(result_small, result_large)

    def test_progress_callback_called(self) -> None:
        calls: list[tuple[str, float]] = []

        def on_progress(stage: str, value: float) -> None:
            calls.append((stage, value))

        self.service.reconvert_array(
            self.dithered, blur_radius=3,
            color_mode=ColorMode.GRAYOUT, progress=on_progress,
        )
        assert len(calls) >= 2
        assert calls[-1][0] == "完了"
        assert calls[-1][1] == 1.0

    def test_output_in_valid_range(self) -> None:
        for mode in ColorMode:
            result = self.service.reconvert_array(
                self.dithered, blur_radius=3, color_mode=mode,
            )
            assert result.min() >= 0
            assert result.max() <= 255

    def test_1x1_image(self) -> None:
        tiny = np.array([[[200, 0, 0]]], dtype=np.uint8)
        result = self.service.reconvert_array(
            tiny, blur_radius=1, color_mode=ColorMode.GRAYOUT,
        )
        assert result.shape == (1, 1, 3)

    def test_brightness_default_no_change(self) -> None:
        """brightness=1.0 のとき明示指定と省略で結果が同じ。"""
        result_default = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.GRAYOUT,
        )
        result_explicit = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.GRAYOUT,
            brightness=1.0,
        )
        np.testing.assert_array_equal(result_default, result_explicit)

    def test_brightness_boost_brighter(self) -> None:
        """brightness=1.5 で結果が明るくなる。"""
        result_normal = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.GRAYOUT,
        )
        result_bright = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.GRAYOUT,
            brightness=1.5,
        )
        mean_normal = float(np.mean(result_normal.astype(np.float64)))
        mean_bright = float(np.mean(result_bright.astype(np.float64)))
        assert mean_bright > mean_normal

    def test_auto_brightness_preserves_blurred_luminance(self) -> None:
        """逆ガマットマッピングで暗化しても自動補正でブラー後輝度に近づく。"""
        from PIL import Image, ImageFilter

        from epaper_palette_dither.infrastructure.color_space import (
            srgb_to_linear_batch,
        )

        # sRGBブラー後にリニア空間で輝度算出（サービス内部と同じロジック）
        pil_image = Image.fromarray(self.dithered, "RGB")
        blurred = np.array(
            pil_image.filter(ImageFilter.GaussianBlur(radius=3)),
            dtype=np.uint8,
        )
        blurred_linear = srgb_to_linear_batch(blurred)
        blurred_lum = float(np.mean(
            0.2126 * blurred_linear[:, :, 0]
            + 0.7152 * blurred_linear[:, :, 1]
            + 0.0722 * blurred_linear[:, :, 2],
        ))

        result = self.service.reconvert_array(
            self.dithered, blur_radius=3, color_mode=ColorMode.GRAYOUT,
        )
        # 結果もリニア空間で輝度比較
        result_linear = srgb_to_linear_batch(result)
        result_lum = float(np.mean(
            0.2126 * result_linear[:, :, 0]
            + 0.7152 * result_linear[:, :, 1]
            + 0.0722 * result_linear[:, :, 2],
        ))
        # 自動補正後の輝度がブラー後輝度の±20%以内
        assert abs(result_lum - blurred_lum) < blurred_lum * 0.2

    def test_brightness_output_in_valid_range(self) -> None:
        """極端な値でも 0-255 範囲内。"""
        for brt in [0.5, 2.0]:
            result = self.service.reconvert_array(
                self.dithered, blur_radius=3, color_mode=ColorMode.GRAYOUT,
                brightness=brt,
            )
            assert result.min() >= 0
            assert result.max() <= 255
            assert result.dtype == np.uint8
