"""画像変換パイプライン。

リサイズ→ガマットマッピング→ディザリング→出力の一連処理。
進捗コールバック対応。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import numpy.typing as npt

from epaper_palette_dither.domain.color import EINK_PALETTE, RGB
from epaper_palette_dither.domain.image_model import ColorMode, ImageSpec
from epaper_palette_dither.application.dither_service import DitherService
from epaper_palette_dither.infrastructure.gamut_mapping import (
    anti_saturate,
    anti_saturate_centroid,
    anti_saturate_centroid_lab,
    anti_saturate_lab,
    apply_illuminant,
    gamut_map,
)
from epaper_palette_dither.infrastructure.image_io import load_image, resize_image, save_image
from epaper_palette_dither.infrastructure.lightness_remap import clahe_lightness


ProgressCallback = Callable[[str, float], None]
"""進捗コールバック: (stage_name, progress_0_to_1)"""


class ImageConverter:
    """画像変換パイプライン。"""

    def __init__(
        self,
        dither_service: DitherService | None = None,
        palette: Sequence[RGB] = EINK_PALETTE,
    ) -> None:
        self._dither_service = dither_service or DitherService()
        self._palette = palette
        self._gamut_strength: float = 0.7
        self._color_mode: ColorMode = ColorMode.ILLUMINANT
        self._illuminant_red: float = 1.0
        self._illuminant_yellow: float = 1.0
        self._illuminant_white: float = 1.0
        self._error_clamp: int = 85
        self._red_penalty: float = 0.0
        self._yellow_penalty: float = 0.0
        self._use_lab_space: bool = True
        self._csf_chroma_weight: float = 0.6
        self._lightness_remap: bool = False
        self._lightness_clip_limit: float = 2.0

    @property
    def gamut_strength(self) -> float:
        return self._gamut_strength

    @gamut_strength.setter
    def gamut_strength(self, value: float) -> None:
        self._gamut_strength = max(0.0, min(1.0, value))

    @property
    def color_mode(self) -> ColorMode:
        return self._color_mode

    @color_mode.setter
    def color_mode(self, value: ColorMode) -> None:
        self._color_mode = value

    @property
    def illuminant_red(self) -> float:
        return self._illuminant_red

    @illuminant_red.setter
    def illuminant_red(self, value: float) -> None:
        self._illuminant_red = max(0.0, min(1.0, value))

    @property
    def illuminant_yellow(self) -> float:
        return self._illuminant_yellow

    @illuminant_yellow.setter
    def illuminant_yellow(self, value: float) -> None:
        self._illuminant_yellow = max(0.0, min(1.0, value))

    @property
    def illuminant_white(self) -> float:
        return self._illuminant_white

    @illuminant_white.setter
    def illuminant_white(self, value: float) -> None:
        self._illuminant_white = max(0.0, min(1.0, value))

    @property
    def error_clamp(self) -> int:
        return self._error_clamp

    @error_clamp.setter
    def error_clamp(self, value: int) -> None:
        self._error_clamp = max(0, min(128, value))

    @property
    def red_penalty(self) -> float:
        return self._red_penalty

    @red_penalty.setter
    def red_penalty(self, value: float) -> None:
        self._red_penalty = max(0.0, min(100.0, value))

    @property
    def yellow_penalty(self) -> float:
        return self._yellow_penalty

    @yellow_penalty.setter
    def yellow_penalty(self, value: float) -> None:
        self._yellow_penalty = max(0.0, min(100.0, value))

    @property
    def use_lab_space(self) -> bool:
        return self._use_lab_space

    @use_lab_space.setter
    def use_lab_space(self, value: bool) -> None:
        self._use_lab_space = value

    @property
    def csf_chroma_weight(self) -> float:
        return self._csf_chroma_weight

    @csf_chroma_weight.setter
    def csf_chroma_weight(self, value: float) -> None:
        self._csf_chroma_weight = max(0.0, min(1.0, value))

    @property
    def lightness_remap(self) -> bool:
        return self._lightness_remap

    @lightness_remap.setter
    def lightness_remap(self, value: bool) -> None:
        self._lightness_remap = value

    @property
    def lightness_clip_limit(self) -> float:
        return self._lightness_clip_limit

    @lightness_clip_limit.setter
    def lightness_clip_limit(self, value: float) -> None:
        self._lightness_clip_limit = max(1.0, min(4.0, value))

    def _apply_lightness_remap(
        self, rgb_array: npt.NDArray[np.uint8],
    ) -> npt.NDArray[np.uint8]:
        """明度リマッピング (CLAHE) を適用。無効時はそのまま返す。"""
        if not self._lightness_remap:
            return rgb_array
        return clahe_lightness(rgb_array, self._lightness_clip_limit)

    def _apply_color_processing(
        self, rgb_array: npt.NDArray[np.uint8],
    ) -> npt.NDArray[np.uint8]:
        """現在のモードに応じた色変換前処理を適用。"""
        if self._color_mode == ColorMode.ANTI_SATURATION:
            if self._use_lab_space:
                return anti_saturate_lab(rgb_array, self._palette)
            return anti_saturate(rgb_array, self._palette)
        if self._color_mode == ColorMode.CENTROID_CLIP:
            if self._use_lab_space:
                return anti_saturate_centroid_lab(rgb_array, self._palette)
            return anti_saturate_centroid(rgb_array, self._palette)
        if self._color_mode == ColorMode.ILLUMINANT:
            r_scale = self._illuminant_red + self._illuminant_yellow
            g_scale = self._illuminant_yellow
            return apply_illuminant(
                rgb_array, r_scale, g_scale, 0.0, self._illuminant_white,
            )
        return gamut_map(rgb_array, self._palette, self._gamut_strength)

    def convert_pre_resized(
        self,
        resized: npt.NDArray[np.uint8],
    ) -> npt.NDArray[np.uint8]:
        """リサイズ済み画像にガマットマッピング＋ディザリングのみ実行。

        Args:
            resized: リサイズ済みの (H, W, 3) uint8 配列

        Returns:
            ディザリング済みの (H, W, 3) uint8 配列
        """
        mapped = self._apply_color_processing(resized)
        mapped = self._apply_lightness_remap(mapped)
        return self._dither_service.dither_array_fast(
            mapped, self._palette, self._error_clamp,
            self._red_penalty, self._yellow_penalty,
            self._csf_chroma_weight,
        )

    def convert(
        self,
        input_path: str | Path,
        spec: ImageSpec,
        progress: ProgressCallback | None = None,
    ) -> npt.NDArray[np.uint8]:
        """画像を変換パイプラインで処理。

        Args:
            input_path: 入力画像パス
            spec: 変換仕様（サイズ等）
            progress: 進捗コールバック

        Returns:
            ディザリング済みの (H, W, 3) uint8 配列
        """
        if progress:
            progress("読み込み", 0.0)

        image = load_image(input_path)

        if progress:
            progress("リサイズ", 0.15)

        resized = resize_image(
            image,
            spec.target_width,
            spec.target_height,
            spec.keep_aspect_ratio,
        )

        if progress:
            progress("ガマットマッピング", 0.3)

        mapped = self._apply_color_processing(resized)
        mapped = self._apply_lightness_remap(mapped)

        if progress:
            progress("ディザリング", 0.5)

        result = self._dither_service.dither_array_fast(
            mapped, self._palette, self._error_clamp,
            self._red_penalty, self._yellow_penalty,
            self._csf_chroma_weight,
        )

        if progress:
            progress("完了", 1.0)

        return result

    def convert_and_save(
        self,
        input_path: str | Path,
        output_path: str | Path,
        spec: ImageSpec,
        progress: ProgressCallback | None = None,
    ) -> None:
        """画像を変換して保存。"""
        result = self.convert(input_path, spec, progress)
        save_image(result, output_path)

    def convert_array(
        self,
        image: npt.NDArray[np.uint8],
        spec: ImageSpec,
        progress: ProgressCallback | None = None,
    ) -> npt.NDArray[np.uint8]:
        """NumPy配列を直接変換（GUI用）。

        Args:
            image: (H, W, 3) の uint8 配列
            spec: 変換仕様
            progress: 進捗コールバック

        Returns:
            ディザリング済みの配列
        """
        if progress:
            progress("リサイズ", 0.1)

        resized = resize_image(
            image,
            spec.target_width,
            spec.target_height,
            spec.keep_aspect_ratio,
        )

        if progress:
            progress("ガマットマッピング", 0.25)

        mapped = self._apply_color_processing(resized)
        mapped = self._apply_lightness_remap(mapped)

        if progress:
            progress("ディザリング", 0.5)

        result = self._dither_service.dither_array_fast(
            mapped, self._palette, self._error_clamp,
            self._red_penalty, self._yellow_penalty,
            self._csf_chroma_weight,
        )

        if progress:
            progress("完了", 1.0)

        return result

    def convert_array_gamut_only(
        self,
        image: npt.NDArray[np.uint8],
        spec: ImageSpec,
        progress: ProgressCallback | None = None,
    ) -> npt.NDArray[np.uint8]:
        """リサイズ→ガマットマッピングのみ（ディザリングなし）。

        Args:
            image: (H, W, 3) の uint8 配列
            spec: 変換仕様
            progress: 進捗コールバック

        Returns:
            ガマットマッピング済みの (H, W, 3) uint8 配列
        """
        if progress:
            progress("リサイズ", 0.1)

        resized = resize_image(
            image,
            spec.target_width,
            spec.target_height,
            spec.keep_aspect_ratio,
        )

        if progress:
            progress("ガマットマッピング", 0.3)

        mapped = self._apply_color_processing(resized)
        mapped = self._apply_lightness_remap(mapped)

        if progress:
            progress("完了", 1.0)

        return mapped

    def convert_gamut_only(
        self,
        input_path: str | Path,
        spec: ImageSpec,
        progress: ProgressCallback | None = None,
    ) -> npt.NDArray[np.uint8]:
        """ファイルからガマットマッピングのみ実行。

        Args:
            input_path: 入力画像パス
            spec: 変換仕様
            progress: 進捗コールバック

        Returns:
            ガマットマッピング済みの (H, W, 3) uint8 配列
        """
        if progress:
            progress("読み込み", 0.0)

        image = load_image(input_path)
        return self.convert_array_gamut_only(image, spec, progress)
