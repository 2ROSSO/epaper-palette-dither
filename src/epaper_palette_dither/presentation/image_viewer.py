"""画像プレビューウィジェット。

ドラッグ&ドロップ、ズーム・パン対応。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QImage, QPixmap, QPainter, QWheelEvent, QMouseEvent, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy


class ImageViewer(QWidget):
    """画像表示ウィジェット。ズーム・パン対応。"""

    image_dropped = pyqtSignal(str)

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._scale = 1.0
        self._offset = QPointF(0, 0)
        self._drag_start: QPointF | None = None
        self._title = title

        self.setAcceptDrops(True)
        self.setMinimumSize(200, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._label = QLabel(title or "ドラッグ&ドロップで画像を読み込み")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("color: #888; font-size: 14px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def set_image_from_array(self, array: npt.NDArray[np.uint8]) -> None:
        """NumPy配列(RGB)から画像を設定。"""
        h, w = array.shape[:2]
        bytes_per_line = 3 * w
        qimage = QImage(array.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimage.copy())
        self._scale = 1.0
        self._offset = QPointF(0, 0)
        self._label.hide()
        self._fit_to_widget()
        self.update()

    def set_image_from_path(self, path: str | Path) -> None:
        """ファイルパスから画像を設定。"""
        self._pixmap = QPixmap(str(path))
        self._scale = 1.0
        self._offset = QPointF(0, 0)
        self._label.hide()
        self._fit_to_widget()
        self.update()

    def clear_image(self) -> None:
        """画像をクリア。"""
        self._pixmap = None
        self._label.show()
        self.update()

    def _fit_to_widget(self) -> None:
        """ウィジェットに画像をフィットさせる。"""
        if self._pixmap is None:
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        ww, wh = self.width(), self.height()
        if pw == 0 or ph == 0:
            return
        self._scale = min(ww / pw, wh / ph)
        self._offset = QPointF(
            (ww - pw * self._scale) / 2,
            (wh - ph * self._scale) / 2,
        )

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if self._pixmap is None:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.translate(self._offset)
        painter.scale(self._scale, self._scale)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.end()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """マウスホイールでズーム。"""
        if self._pixmap is None:
            return

        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 1 / 1.1

        # ズーム中心をマウス位置にする
        pos = event.position()
        old_scene = (pos - self._offset) / self._scale

        self._scale *= factor
        self._scale = max(0.1, min(10.0, self._scale))

        new_offset = pos - old_scene * self._scale
        self._offset = new_offset
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap is not None:
            self._drag_start = event.position()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            delta = event.position() - self._drag_start
            self._offset += delta
            self._drag_start = event.position()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_start = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """ダブルクリックでフィットにリセット。"""
        self._fit_to_widget()
        self.update()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        if self._pixmap is not None:
            self._fit_to_widget()
        super().resizeEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.image_dropped.emit(path)
