"""image_io.py のテスト。"""

import tempfile
from pathlib import Path

import numpy as np

from epaper_palette_dither.infrastructure.image_io import (
    load_image,
    resize_image,
    rotate_image_cw90,
    save_image,
)


class TestLoadAndSave:
    def test_save_and_load_png(self) -> None:
        array = np.zeros((10, 20, 3), dtype=np.uint8)
        array[:, :, 0] = 200  # 赤チャンネル
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = Path(f.name)
        save_image(array, path)
        loaded = load_image(path)
        np.testing.assert_array_equal(array, loaded)
        path.unlink()

    def test_save_and_load_bmp(self) -> None:
        array = np.full((5, 5, 3), 128, dtype=np.uint8)
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            path = Path(f.name)
        save_image(array, path)
        loaded = load_image(path)
        np.testing.assert_array_equal(array, loaded)
        path.unlink()

    def test_loaded_shape(self) -> None:
        array = np.zeros((30, 40, 3), dtype=np.uint8)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = Path(f.name)
        save_image(array, path)
        loaded = load_image(path)
        assert loaded.shape == (30, 40, 3)
        assert loaded.dtype == np.uint8
        path.unlink()


class TestRotateCW90:
    def test_shape_transform(self) -> None:
        array = np.zeros((10, 20, 3), dtype=np.uint8)
        rotated = rotate_image_cw90(array)
        assert rotated.shape == (20, 10, 3)

    def test_four_rotations_identity(self) -> None:
        rng = np.random.default_rng(42)
        array = rng.integers(0, 256, size=(10, 20, 3), dtype=np.uint8)
        result = array
        for _ in range(4):
            result = rotate_image_cw90(result)
        np.testing.assert_array_equal(array, result)

    def test_dtype_preserved(self) -> None:
        array = np.zeros((5, 8, 3), dtype=np.uint8)
        rotated = rotate_image_cw90(array)
        assert rotated.dtype == np.uint8

    def test_memory_contiguous(self) -> None:
        array = np.zeros((10, 20, 3), dtype=np.uint8)
        rotated = rotate_image_cw90(array)
        assert rotated.flags["C_CONTIGUOUS"]


class TestResize:
    def test_resize_exact(self) -> None:
        array = np.zeros((100, 200, 3), dtype=np.uint8)
        resized = resize_image(array, 50, 25, keep_aspect_ratio=False)
        assert resized.shape == (25, 50, 3)

    def test_resize_keep_aspect(self) -> None:
        array = np.zeros((100, 200, 3), dtype=np.uint8)
        resized = resize_image(array, 400, 300, keep_aspect_ratio=True)
        # キャンバスサイズは目標通り
        assert resized.shape == (300, 400, 3)

    def test_resize_square_to_landscape(self) -> None:
        array = np.zeros((100, 100, 3), dtype=np.uint8)
        resized = resize_image(array, 400, 300, keep_aspect_ratio=True)
        assert resized.shape == (300, 400, 3)

    def test_resize_dtype(self) -> None:
        array = np.zeros((50, 50, 3), dtype=np.uint8)
        resized = resize_image(array, 20, 20, keep_aspect_ratio=False)
        assert resized.dtype == np.uint8
