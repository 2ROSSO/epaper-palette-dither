"""メインウィンドウ。

3パネル並列で元画像・ディザリング結果・Reconvert結果を表示。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QLabel,
    QDialog,
    QTextEdit,
    QDialogButtonBox,
)

from epaper_palette_dither.application.dither_service import DitherService
from epaper_palette_dither.application.image_converter import ImageConverter
from epaper_palette_dither.application.optimizer_service import OptimizerService, OptimizeResult
from epaper_palette_dither.application.reconvert_service import ReconvertService
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


class ReconvertWorker(QThread):
    """バックグラウンドでReconvert処理を実行するワーカー。"""

    finished = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)
    progress = pyqtSignal(str, float)

    def __init__(
        self,
        service: ReconvertService,
        dithered: np.ndarray,
        blur_radius: int,
        converter: ImageConverter,
        brightness: float = 1.0,
    ) -> None:
        super().__init__()
        self._service = service
        self._dithered = dithered
        self._blur_radius = blur_radius
        self._converter = converter
        self._brightness = brightness

    def run(self) -> None:
        try:
            result = self._service.reconvert_array(
                self._dithered,
                blur_radius=self._blur_radius,
                color_mode=self._converter.color_mode,
                gamut_strength=self._converter.gamut_strength,
                illuminant_red=self._converter.illuminant_red,
                illuminant_yellow=self._converter.illuminant_yellow,
                illuminant_white=self._converter.illuminant_white,
                brightness=self._brightness,
                progress=lambda s, p: self.progress.emit(s, p),
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class OptimizerWorker(QThread):
    """バックグラウンドでパラメータ最適化を実行するワーカー。"""

    finished = pyqtSignal(object)  # OptimizeResult
    error = pyqtSignal(str)
    progress = pyqtSignal(str, float)

    def __init__(
        self,
        service: OptimizerService,
        source_image: np.ndarray,
        spec: ImageSpec,
        converter: ImageConverter,
        initial_params: dict[str, float],
        n_trials: int = 50,
    ) -> None:
        super().__init__()
        self._service = service
        self._source_image = source_image
        self._spec = spec
        self._color_mode = converter.color_mode
        self._initial_params = initial_params
        self._n_trials = n_trials
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            result = self._service.optimize(
                self._source_image,
                self._spec,
                self._color_mode,
                self._initial_params,
                n_trials=self._n_trials,
                progress=lambda s, p: self.progress.emit(s, p),
                cancelled=lambda: self._cancelled,
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
        self.resize(1200, 600)

        self._source_image: np.ndarray | None = None
        self._result_image: np.ndarray | None = None
        self._reconvert_image: np.ndarray | None = None
        self._worker: ConvertWorker | None = None
        self._reconvert_worker: ReconvertWorker | None = None
        self._optimizer_worker: OptimizerWorker | None = None

        self._converter = ImageConverter(DitherService())
        self._reconvert_service = ReconvertService()
        self._optimizer_service = OptimizerService()

        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # --- 画像ビューア（3パネル並列）---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左: 元画像
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        left_label = QLabel("Original")
        left_label.setObjectName("panelLabel")
        left_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(left_label)
        self._source_viewer = ImageViewer("元画像")
        self._source_viewer.image_dropped.connect(self._on_image_dropped)
        left_layout.addWidget(self._source_viewer)

        # 中: ディザリング結果
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(2)
        center_label = QLabel("Dithered Preview")
        center_label.setObjectName("panelLabel")
        center_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(center_label)
        self._result_viewer = ImageViewer("プレビュー")
        self._result_viewer.image_dropped.connect(self._on_image_dropped)
        center_layout.addWidget(self._result_viewer)

        # 右: Reconvert結果
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        right_label = QLabel("Reconverted")
        right_label.setObjectName("panelLabel")
        right_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(right_label)
        self._reconvert_viewer = ImageViewer("復元画像")
        self._reconvert_viewer.image_dropped.connect(self._on_image_dropped)
        right_layout.addWidget(self._reconvert_viewer)

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 400, 400])
        main_layout.addWidget(splitter, stretch=1)

        # --- コントロールパネル ---
        self._controls = ControlPanel()
        self._controls.convert_clicked.connect(self._on_convert)
        self._controls.gamut_only_clicked.connect(self._on_gamut_only)
        self._controls.rotate_clicked.connect(self._on_rotate)
        self._controls.save_clicked.connect(self._on_save)
        self._controls.reconvert_clicked.connect(self._on_reconvert)
        self._controls.gamut_strength_changed.connect(self._on_gamut_strength_changed)
        self._controls.color_mode_changed.connect(self._on_color_mode_changed)
        self._controls.illuminant_red_changed.connect(self._on_illuminant_red_changed)
        self._controls.illuminant_yellow_changed.connect(self._on_illuminant_yellow_changed)
        self._controls.illuminant_white_changed.connect(self._on_illuminant_white_changed)
        self._controls.csf_chroma_weight_changed.connect(self._on_csf_chroma_weight_changed)
        self._controls.error_clamp_changed.connect(self._on_error_clamp_changed)
        self._controls.red_penalty_changed.connect(self._on_red_penalty_changed)
        self._controls.yellow_penalty_changed.connect(self._on_yellow_penalty_changed)
        self._controls.use_lab_changed.connect(self._on_use_lab_changed)
        self._controls.lightness_remap_changed.connect(self._on_lightness_remap_changed)
        self._controls.lightness_clip_limit_changed.connect(self._on_lightness_clip_limit_changed)
        self._controls.optimize_clicked.connect(self._on_optimize)
        self._controls.set_convert_enabled(False)
        self._controls.set_gamut_only_enabled(False)
        self._controls.set_rotate_enabled(False)
        self._controls.set_reconvert_enabled(False)
        self._controls.set_optimize_enabled(False)
        main_layout.addWidget(self._controls)

        # --- ステータスバー ---
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready \u2014 ドラッグ&ドロップまたはCtrl+Oで画像を読み込み")

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
            # 縦長画像を自動で横向きに回転
            h, w = self._source_image.shape[:2]
            if self._controls.auto_rotate and h > w:
                self._source_image = rotate_image_cw90(self._source_image)
            self._source_viewer.set_image_from_array(self._source_image)
            self._result_viewer.clear_image()
            self._reconvert_viewer.clear_image()
            self._result_image = None
            self._reconvert_image = None
            self._controls.set_convert_enabled(True)
            self._controls.set_gamut_only_enabled(True)
            self._controls.set_rotate_enabled(True)
            self._controls.set_save_enabled(False)
            self._controls.set_reconvert_enabled(False)
            self._controls.set_optimize_enabled(True)
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
        self._reconvert_image = None
        self._result_viewer.clear_image()
        self._reconvert_viewer.clear_image()
        self._controls.set_save_enabled(False)
        self._controls.set_reconvert_enabled(False)
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
        self._controls.set_reconvert_enabled(False)
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
        self._reconvert_image = None
        self._reconvert_viewer.clear_image()
        self._controls.set_convert_enabled(True)
        self._controls.set_gamut_only_enabled(True)
        self._controls.set_rotate_enabled(True)
        self._controls.set_save_enabled(True)
        self._controls.set_reconvert_enabled(True)
        h, w = result.shape[:2]
        self._status_bar.showMessage(f"変換完了: {w}x{h}")

    def _on_convert_error(self, message: str) -> None:
        self._controls.set_convert_enabled(True)
        self._controls.set_gamut_only_enabled(True)
        self._controls.set_rotate_enabled(True)
        QMessageBox.warning(self, "変換エラー", f"変換に失敗しました:\n{message}")
        self._status_bar.showMessage("変換エラー")

    def _on_reconvert(self) -> None:
        if self._result_image is None:
            return

        self._controls.set_reconvert_enabled(False)
        self._controls.set_convert_enabled(False)
        self._controls.set_gamut_only_enabled(False)
        self._status_bar.showMessage("Reconvert中...")

        self._reconvert_worker = ReconvertWorker(
            self._reconvert_service,
            self._result_image,
            self._controls.blur_radius,
            self._converter,
            brightness=self._controls.brightness,
        )
        self._reconvert_worker.progress.connect(self._on_reconvert_progress)
        self._reconvert_worker.finished.connect(self._on_reconvert_done)
        self._reconvert_worker.error.connect(self._on_reconvert_error)
        self._reconvert_worker.start()

    def _on_reconvert_progress(self, stage: str, value: float) -> None:
        self._status_bar.showMessage(f"Reconvert: {stage} ({int(value * 100)}%)")

    def _on_reconvert_done(self, result: np.ndarray) -> None:
        self._reconvert_image = result
        self._reconvert_viewer.set_image_from_array(result)
        self._controls.set_reconvert_enabled(True)
        self._controls.set_convert_enabled(True)
        self._controls.set_gamut_only_enabled(True)
        h, w = result.shape[:2]
        self._status_bar.showMessage(f"Reconvert完了: {w}x{h}")

    def _on_reconvert_error(self, message: str) -> None:
        self._controls.set_reconvert_enabled(True)
        self._controls.set_convert_enabled(True)
        self._controls.set_gamut_only_enabled(True)
        QMessageBox.warning(self, "Reconvertエラー", f"Reconvertに失敗しました:\n{message}")
        self._status_bar.showMessage("Reconvertエラー")

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

    def _on_csf_chroma_weight_changed(self, value: float) -> None:
        self._converter.csf_chroma_weight = value

    def _on_error_clamp_changed(self, value: int) -> None:
        self._converter.error_clamp = value

    def _on_red_penalty_changed(self, value: float) -> None:
        self._converter.red_penalty = value

    def _on_yellow_penalty_changed(self, value: float) -> None:
        self._converter.yellow_penalty = value

    def _on_use_lab_changed(self, enabled: bool) -> None:
        self._converter.use_lab_space = enabled

    def _on_lightness_remap_changed(self, enabled: bool) -> None:
        self._converter.lightness_remap = enabled

    def _on_lightness_clip_limit_changed(self, value: float) -> None:
        self._converter.lightness_clip_limit = value

    def _on_optimize(self) -> None:
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
        self._controls.set_reconvert_enabled(False)
        self._controls.set_optimize_enabled(False)
        self._status_bar.showMessage("最適化中...")

        self._optimizer_worker = OptimizerWorker(
            self._optimizer_service,
            self._source_image,
            spec,
            self._converter,
            self._controls.get_current_params(),
            n_trials=self._controls.optimize_n_trials,
        )
        self._optimizer_worker.progress.connect(self._on_optimize_progress)
        self._optimizer_worker.finished.connect(self._on_optimize_done)
        self._optimizer_worker.error.connect(self._on_optimize_error)
        self._optimizer_worker.start()

    def _on_optimize_progress(self, stage: str, value: float) -> None:
        self._status_bar.showMessage(f"最適化: {stage} ({int(value * 100)}%)")

    def _on_optimize_done(self, result: object) -> None:
        opt_result: OptimizeResult = result  # type: ignore[assignment]

        # UI にパラメータを反映
        self._controls.set_params(opt_result.best_params)

        # ボタン復元
        self._controls.set_convert_enabled(True)
        self._controls.set_gamut_only_enabled(True)
        self._controls.set_rotate_enabled(True)
        self._controls.set_optimize_enabled(True)
        if self._result_image is not None:
            self._controls.set_reconvert_enabled(True)

        self._status_bar.showMessage(
            f"最適化完了: composite={opt_result.best_score:.4f}"
        )

        # ログダイアログ表示
        dialog = QDialog(self)
        dialog.setWindowTitle("Optimize Result")
        dialog.resize(500, 400)
        layout = QVBoxLayout(dialog)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFontFamily("Consolas, monospace")
        text_edit.setPlainText("\n".join(opt_result.log))
        layout.addWidget(text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec()

    def _on_optimize_error(self, message: str) -> None:
        self._controls.set_convert_enabled(True)
        self._controls.set_gamut_only_enabled(True)
        self._controls.set_rotate_enabled(True)
        self._controls.set_optimize_enabled(True)
        if self._result_image is not None:
            self._controls.set_reconvert_enabled(True)
        QMessageBox.warning(self, "最適化エラー", f"最適化に失敗しました:\n{message}")
        self._status_bar.showMessage("最適化エラー")

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
