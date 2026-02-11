"""メインウィンドウ。

左右並列で元画像とディザリング結果を表示。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QLabel,
)

from epaper_palette_dither.application.dither_service import DitherService
from epaper_palette_dither.application.image_converter import ImageConverter
from epaper_palette_dither.domain.image_model import ImageSpec
from epaper_palette_dither.infrastructure.image_io import load_image, rotate_image_cw90, save_image
from epaper_palette_dither.presentation.image_viewer import ImageViewer
from epaper_palette_dither.presentation.controls import ControlPanel


class ConvertWorker(QThread):
    """バックグラウンドで変換処理を実行するワーカー。"""

    finished = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)
    progress = pyqtSignal(str, float)

    def __init__(
        self,
        converter: ImageConverter,
        image: np.ndarray,
        spec: ImageSpec,
        gamut_only: bool = False,
    ) -> None:
        super().__init__()
        self._converter = converter
        self._image = image
        self._spec = spec
        self._gamut_only = gamut_only

    def run(self) -> None:
        try:
            if self._gamut_only:
                result = self._converter.convert_array_gamut_only(
                    self._image,
                    self._spec,
                    progress=lambda s, p: self.progress.emit(s, p),
                )
            else:
                result = self._converter.convert_array(
                    self._image,
                    self._spec,
                    progress=lambda s, p: self.progress.emit(s, p),
                )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """E-Paper Palette Dither メインウィンドウ。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("E-Paper Palette Dither")
        self.setMinimumSize(800, 500)
        self.resize(1000, 600)

        self._source_image: np.ndarray | None = None
        self._result_image: np.ndarray | None = None
        self._worker: ConvertWorker | None = None

        self._converter = ImageConverter(DitherService())

        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # --- 画像ビューア（左右並列）---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左: 元画像
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        left_label = QLabel("Original")
        left_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #555;")
        left_layout.addWidget(left_label)
        self._source_viewer = ImageViewer("元画像")
        self._source_viewer.image_dropped.connect(self._on_image_dropped)
        left_layout.addWidget(self._source_viewer)

        # 右: ディザリング結果
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        right_label = QLabel("Dithered Preview")
        right_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #555;")
        right_layout.addWidget(right_label)
        self._result_viewer = ImageViewer("プレビュー")
        self._result_viewer.image_dropped.connect(self._on_image_dropped)
        right_layout.addWidget(self._result_viewer)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([500, 500])
        main_layout.addWidget(splitter, stretch=1)

        # --- コントロールパネル ---
        self._controls = ControlPanel()
        self._controls.convert_clicked.connect(self._on_convert)
        self._controls.gamut_only_clicked.connect(self._on_gamut_only)
        self._controls.rotate_clicked.connect(self._on_rotate)
        self._controls.save_clicked.connect(self._on_save)
        self._controls.gamut_strength_changed.connect(self._on_gamut_strength_changed)
        self._controls.color_mode_changed.connect(self._on_color_mode_changed)
        self._controls.illuminant_red_changed.connect(self._on_illuminant_red_changed)
        self._controls.illuminant_yellow_changed.connect(self._on_illuminant_yellow_changed)
        self._controls.illuminant_white_changed.connect(self._on_illuminant_white_changed)
        self._controls.perceived_palette_changed.connect(self._on_perceived_palette_changed)
        self._controls.error_clamp_changed.connect(self._on_error_clamp_changed)
        self._controls.red_penalty_changed.connect(self._on_red_penalty_changed)
        self._controls.yellow_penalty_changed.connect(self._on_yellow_penalty_changed)
        self._controls.set_convert_enabled(False)
        self._controls.set_gamut_only_enabled(False)
        self._controls.set_rotate_enabled(False)
        main_layout.addWidget(self._controls)

        # --- ステータスバー ---
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready — ドラッグ&ドロップまたはCtrl+Oで画像を読み込み")

        # --- メニューバー ---
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        open_action = file_menu.addAction("Open...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open)

        save_action = file_menu.addAction("Save As...")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save)

        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quit")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "画像を開く",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff);;All Files (*)",
        )
        if path:
            self._load_image(path)

    def _on_image_dropped(self, path: str) -> None:
        self._load_image(path)

    def _load_image(self, path: str) -> None:
        try:
            self._source_image = load_image(path)
            self._source_viewer.set_image_from_array(self._source_image)
            self._result_viewer.clear_image()
            self._result_image = None
            self._controls.set_convert_enabled(True)
            self._controls.set_gamut_only_enabled(True)
            self._controls.set_rotate_enabled(True)
            self._controls.set_save_enabled(False)
            h, w = self._source_image.shape[:2]
            self._status_bar.showMessage(f"読み込み完了: {Path(path).name} ({w}x{h})")
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"画像の読み込みに失敗しました:\n{e}")

    def _on_convert(self) -> None:
        self._start_conversion(gamut_only=False)

    def _on_gamut_only(self) -> None:
        self._start_conversion(gamut_only=True)

    def _on_rotate(self) -> None:
        if self._source_image is None:
            return
        self._source_image = rotate_image_cw90(self._source_image)
        self._source_viewer.set_image_from_array(self._source_image)
        self._result_image = None
        self._result_viewer.clear_image()
        self._controls.set_save_enabled(False)
        h, w = self._source_image.shape[:2]
        self._status_bar.showMessage(f"回転完了: {w}x{h}")

    def _start_conversion(self, gamut_only: bool) -> None:
        if self._source_image is None:
            return

        preset = self._controls.current_preset
        spec = ImageSpec(
            target_width=preset.width,
            target_height=preset.height,
        )

        self._controls.set_convert_enabled(False)
        self._controls.set_gamut_only_enabled(False)
        self._controls.set_rotate_enabled(False)
        label = "ガマットマッピング中..." if gamut_only else "変換中..."
        self._status_bar.showMessage(label)

        self._worker = ConvertWorker(
            self._converter, self._source_image, spec, gamut_only=gamut_only,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_convert_done)
        self._worker.error.connect(self._on_convert_error)
        self._worker.start()

    def _on_progress(self, stage: str, value: float) -> None:
        self._status_bar.showMessage(f"変換中: {stage} ({int(value * 100)}%)")

    def _on_convert_done(self, result: np.ndarray) -> None:
        self._result_image = result
        self._result_viewer.set_image_from_array(result)
        self._controls.set_convert_enabled(True)
        self._controls.set_gamut_only_enabled(True)
        self._controls.set_rotate_enabled(True)
        self._controls.set_save_enabled(True)
        h, w = result.shape[:2]
        self._status_bar.showMessage(f"変換完了: {w}x{h}")

    def _on_convert_error(self, message: str) -> None:
        self._controls.set_convert_enabled(True)
        self._controls.set_gamut_only_enabled(True)
        self._controls.set_rotate_enabled(True)
        QMessageBox.warning(self, "変換エラー", f"変換に失敗しました:\n{message}")
        self._status_bar.showMessage("変換エラー")

    def _on_gamut_strength_changed(self, strength: float) -> None:
        self._converter.gamut_strength = strength

    def _on_color_mode_changed(self, mode: object) -> None:
        self._converter.color_mode = mode  # type: ignore[assignment]

    def _on_illuminant_red_changed(self, value: float) -> None:
        self._converter.illuminant_red = value

    def _on_illuminant_yellow_changed(self, value: float) -> None:
        self._converter.illuminant_yellow = value

    def _on_illuminant_white_changed(self, value: float) -> None:
        self._converter.illuminant_white = value

    def _on_perceived_palette_changed(self, value: bool) -> None:
        self._converter.use_perceived_palette = value

    def _on_error_clamp_changed(self, value: int) -> None:
        self._converter.error_clamp = value

    def _on_red_penalty_changed(self, value: float) -> None:
        self._converter.red_penalty = value

    def _on_yellow_penalty_changed(self, value: float) -> None:
        self._converter.yellow_penalty = value

    def _on_save(self) -> None:
        if self._result_image is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "画像を保存",
            "dithered_output.png",
            "PNG (*.png);;BMP (*.bmp);;All Files (*)",
        )
        if path:
            try:
                save_image(self._result_image, path)
                self._status_bar.showMessage(f"保存完了: {Path(path).name}")
            except Exception as e:
                QMessageBox.warning(self, "保存エラー", f"保存に失敗しました:\n{e}")
