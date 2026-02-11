"""画像ドメインモデル。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ColorMode(Enum):
    """色変換の前処理モード。"""

    GRAYOUT = "Grayout"
    ANTI_SATURATION = "Anti-Saturation"
    CENTROID_CLIP = "Centroid Clip"
    ILLUMINANT = "Illuminant"


class DisplayPreset(Enum):
    """E-Inkディスプレイのプリセット解像度。"""

    SANTEK_29 = (296, 128, "Santek 2.9\"")
    SANTEK_42 = (400, 300, "Santek 4.2\"")

    def __init__(self, width: int, height: int, label: str) -> None:
        self._width = width
        self._height = height
        self._label = label

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def label(self) -> str:
        return self._label

    @property
    def size(self) -> tuple[int, int]:
        return (self._width, self._height)


@dataclass
class ImageSpec:
    """画像変換の仕様。"""

    target_width: int
    target_height: int
    keep_aspect_ratio: bool = True
    orientation_landscape: bool = True
