"""画像I/O（Pillow ベース）。

画像の読み込み、保存、リサイズを担当。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image


def load_image(path: str | Path) -> npt.NDArray[np.uint8]:
    """画像ファイルを読み込み、RGB配列として返す。

    Args:
        path: 画像ファイルパス (JPEG, PNG等)

    Returns:
        (H, W, 3) の uint8 配列 (RGB)
    """
    with Image.open(path) as img:
        img = img.convert("RGB")
        return np.array(img, dtype=np.uint8)


def save_image(array: npt.NDArray[np.uint8], path: str | Path) -> None:
    """RGB配列を画像ファイルとして保存。

    Args:
        array: (H, W, 3) の uint8 配列 (RGB)
        path: 保存先パス (PNG, BMP等)
    """
    img = Image.fromarray(array, mode="RGB")
    img.save(path)


def rotate_image_cw90(array: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
    """画像を時計回りに90°回転。

    Args:
        array: (H, W, 3) の uint8 配列

    Returns:
        (W, H, 3) の uint8 配列（90° CW回転済み）
    """
    return np.rot90(array, k=-1).copy()


def resize_image(
    array: npt.NDArray[np.uint8],
    target_width: int,
    target_height: int,
    keep_aspect_ratio: bool = True,
) -> npt.NDArray[np.uint8]:
    """画像をリサイズ。

    Args:
        array: (H, W, 3) の uint8 配列
        target_width: 目標幅
        target_height: 目標高さ
        keep_aspect_ratio: アスペクト比を維持するか

    Returns:
        リサイズ済みの (H, W, 3) uint8 配列
    """
    img = Image.fromarray(array, mode="RGB")

    if keep_aspect_ratio:
        img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        # 目標サイズのキャンバスに中央配置（白背景）
        canvas = Image.new("RGB", (target_width, target_height), (255, 255, 255))
        offset_x = (target_width - img.width) // 2
        offset_y = (target_height - img.height) // 2
        canvas.paste(img, (offset_x, offset_y))
        return np.array(canvas, dtype=np.uint8)
    else:
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        return np.array(img, dtype=np.uint8)
