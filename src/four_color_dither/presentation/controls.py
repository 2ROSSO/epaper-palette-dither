"""パラメータ制御パネル。

ディスプレイプリセット選択、ガマットマッピング強度、変換・保存ボタン等。
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QLabel,
)

from four_color_dither.domain.image_model import ColorMode, DisplayPreset

_GAMUT_STRENGTH_DEFAULT = 0.70
_ILLUMINANT_RED_DEFAULT = 1.00
_ILLUMINANT_YELLOW_DEFAULT = 1.00
_ILLUMINANT_WHITE_DEFAULT = 1.00


class ControlPanel(QWidget):
    """パラメータ制御パネル。"""

    convert_clicked = pyqtSignal()
    gamut_only_clicked = pyqtSignal()
    rotate_clicked = pyqtSignal()
    save_clicked = pyqtSignal()
    preset_changed = pyqtSignal(DisplayPreset)
    gamut_strength_changed = pyqtSignal(float)
    color_mode_changed = pyqtSignal(object)
    illuminant_red_changed = pyqtSignal(float)
    illuminant_yellow_changed = pyqtSignal(float)
    illuminant_white_changed = pyqtSignal(float)
    error_clamp_changed = pyqtSignal(int)
    red_penalty_changed = pyqtSignal(float)
    yellow_penalty_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # プリセット選択
        layout.addWidget(QLabel("Target:"))
        self._preset_combo = QComboBox()
        for preset in DisplayPreset:
            self._preset_combo.addItem(
                f"{preset.label} ({preset.width}x{preset.height})",
                preset,
            )
        # デフォルトを4.2インチに
        self._preset_combo.setCurrentIndex(1)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        layout.addWidget(self._preset_combo)

        # カラーモード選択
        layout.addWidget(QLabel("Color:"))
        self._color_mode_combo = QComboBox()
        for mode in ColorMode:
            self._color_mode_combo.addItem(mode.value, mode)
        self._color_mode_combo.currentIndexChanged.connect(self._on_color_mode_changed)
        layout.addWidget(self._color_mode_combo)

        # ガマットマッピング強度スピンボックス（Grayout専用）
        self._gamut_spin = QDoubleSpinBox()
        self._gamut_spin.setRange(0.0, 1.0)
        self._gamut_spin.setSingleStep(0.05)
        self._gamut_spin.setDecimals(2)
        self._gamut_spin.setValue(_GAMUT_STRENGTH_DEFAULT)
        self._gamut_spin.setFixedWidth(90)
        self._gamut_spin.setToolTip("ガマットマッピング強度 (0.00〜1.00)")
        self._gamut_spin.valueChanged.connect(self._on_gamut_changed)
        layout.addWidget(self._gamut_spin)

        # Illuminant パラメータ（Red / Yellow）
        self._illuminant_red_label = QLabel("Red:")
        layout.addWidget(self._illuminant_red_label)
        self._illuminant_red_spin = QDoubleSpinBox()
        self._illuminant_red_spin.setRange(0.0, 1.0)
        self._illuminant_red_spin.setSingleStep(0.05)
        self._illuminant_red_spin.setDecimals(2)
        self._illuminant_red_spin.setValue(_ILLUMINANT_RED_DEFAULT)
        self._illuminant_red_spin.setFixedWidth(90)
        self._illuminant_red_spin.valueChanged.connect(self.illuminant_red_changed.emit)
        layout.addWidget(self._illuminant_red_spin)

        self._illuminant_yellow_label = QLabel("Yellow:")
        layout.addWidget(self._illuminant_yellow_label)
        self._illuminant_yellow_spin = QDoubleSpinBox()
        self._illuminant_yellow_spin.setRange(0.0, 1.0)
        self._illuminant_yellow_spin.setSingleStep(0.05)
        self._illuminant_yellow_spin.setDecimals(2)
        self._illuminant_yellow_spin.setValue(_ILLUMINANT_YELLOW_DEFAULT)
        self._illuminant_yellow_spin.setFixedWidth(90)
        self._illuminant_yellow_spin.valueChanged.connect(self.illuminant_yellow_changed.emit)
        layout.addWidget(self._illuminant_yellow_spin)

        self._illuminant_white_label = QLabel("White:")
        layout.addWidget(self._illuminant_white_label)
        self._illuminant_white_spin = QDoubleSpinBox()
        self._illuminant_white_spin.setRange(0.0, 1.0)
        self._illuminant_white_spin.setSingleStep(0.05)
        self._illuminant_white_spin.setDecimals(2)
        self._illuminant_white_spin.setValue(_ILLUMINANT_WHITE_DEFAULT)
        self._illuminant_white_spin.setFixedWidth(90)
        self._illuminant_white_spin.setToolTip("明部の白保持 (0=無効, 1=明部を完全保持)")
        self._illuminant_white_spin.valueChanged.connect(self.illuminant_white_changed.emit)
        layout.addWidget(self._illuminant_white_spin)

        self._illuminant_reset_btn = QPushButton("\u21ba")
        self._illuminant_reset_btn.setFixedWidth(30)
        self._illuminant_reset_btn.setToolTip("Illuminant パラメータをリセット")
        self._illuminant_reset_btn.clicked.connect(self._on_illuminant_reset)
        layout.addWidget(self._illuminant_reset_btn)

        # Illuminant ウィジェットをリストに保持（表示切替用）
        self._illuminant_widgets = [
            self._illuminant_red_label,
            self._illuminant_red_spin,
            self._illuminant_yellow_label,
            self._illuminant_yellow_spin,
            self._illuminant_white_label,
            self._illuminant_white_spin,
            self._illuminant_reset_btn,
        ]
        # 初期状態: 非表示
        for w in self._illuminant_widgets:
            w.setVisible(False)

        layout.addStretch()

        # 回転ボタン
        self._rotate_btn = QPushButton("↻ Rotate")
        self._rotate_btn.setMinimumWidth(80)
        self._rotate_btn.setToolTip("元画像を時計回りに90°回転")
        self._rotate_btn.setEnabled(False)
        self._rotate_btn.clicked.connect(self.rotate_clicked.emit)
        layout.addWidget(self._rotate_btn)

        # Error Clamping
        layout.addWidget(QLabel("ErrClamp:"))
        self._error_clamp_spin = QSpinBox()
        self._error_clamp_spin.setRange(0, 128)
        self._error_clamp_spin.setValue(85)
        self._error_clamp_spin.setFixedWidth(90)
        self._error_clamp_spin.setToolTip("誤差拡散クランプ (0=無効, 値が小さいほど強い抑制)")
        self._error_clamp_spin.valueChanged.connect(self.error_clamp_changed.emit)
        layout.addWidget(self._error_clamp_spin)

        # Red Penalty
        layout.addWidget(QLabel("RedPen:"))
        self._red_penalty_spin = QDoubleSpinBox()
        self._red_penalty_spin.setRange(0.0, 100.0)
        self._red_penalty_spin.setSingleStep(1.0)
        self._red_penalty_spin.setDecimals(1)
        self._red_penalty_spin.setValue(10.0)
        self._red_penalty_spin.setFixedWidth(90)
        self._red_penalty_spin.setToolTip("明部での赤ペナルティ (0=無効, CIEDE2000距離に加算)")
        self._red_penalty_spin.valueChanged.connect(self.red_penalty_changed.emit)
        layout.addWidget(self._red_penalty_spin)

        # Yellow Penalty
        layout.addWidget(QLabel("YellowPen:"))
        self._yellow_penalty_spin = QDoubleSpinBox()
        self._yellow_penalty_spin.setRange(0.0, 100.0)
        self._yellow_penalty_spin.setSingleStep(1.0)
        self._yellow_penalty_spin.setDecimals(1)
        self._yellow_penalty_spin.setValue(15.0)
        self._yellow_penalty_spin.setFixedWidth(90)
        self._yellow_penalty_spin.setToolTip("暗部での黄ペナルティ (0=無効, CIEDE2000距離に加算)")
        self._yellow_penalty_spin.valueChanged.connect(self.yellow_penalty_changed.emit)
        layout.addWidget(self._yellow_penalty_spin)

        # 変換ボタン
        self._convert_btn = QPushButton("▶ Convert")
        self._convert_btn.setMinimumWidth(100)
        self._convert_btn.clicked.connect(self.convert_clicked.emit)
        layout.addWidget(self._convert_btn)

        # ガマットのみボタン
        self._gamut_only_btn = QPushButton("\U0001f3a8 Gamut Only")
        self._gamut_only_btn.setMinimumWidth(100)
        self._gamut_only_btn.setToolTip("ディザリングなしでガマットマッピングのみ適用")
        self._gamut_only_btn.clicked.connect(self.gamut_only_clicked.emit)
        layout.addWidget(self._gamut_only_btn)

        # 保存ボタン
        self._save_btn = QPushButton("💾 Save")
        self._save_btn.setMinimumWidth(80)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self.save_clicked.emit)
        layout.addWidget(self._save_btn)

    @property
    def current_preset(self) -> DisplayPreset:
        return self._preset_combo.currentData()

    @property
    def gamut_strength(self) -> float:
        return self._gamut_spin.value()

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_btn.setEnabled(enabled)

    def set_rotate_enabled(self, enabled: bool) -> None:
        self._rotate_btn.setEnabled(enabled)

    def set_convert_enabled(self, enabled: bool) -> None:
        self._convert_btn.setEnabled(enabled)

    def set_gamut_only_enabled(self, enabled: bool) -> None:
        self._gamut_only_btn.setEnabled(enabled)

    def _on_preset_changed(self, index: int) -> None:
        preset = self._preset_combo.itemData(index)
        if preset is not None:
            self.preset_changed.emit(preset)

    def _on_color_mode_changed(self, index: int) -> None:
        mode = self._color_mode_combo.itemData(index)
        if mode is not None:
            self._gamut_spin.setVisible(mode == ColorMode.GRAYOUT)
            is_illuminant = mode == ColorMode.ILLUMINANT
            for w in self._illuminant_widgets:
                w.setVisible(is_illuminant)
            self.color_mode_changed.emit(mode)

    @property
    def current_color_mode(self) -> ColorMode:
        return self._color_mode_combo.currentData()

    def _on_gamut_changed(self, value: float) -> None:
        self.gamut_strength_changed.emit(value)

    def _on_illuminant_reset(self) -> None:
        self._illuminant_red_spin.setValue(_ILLUMINANT_RED_DEFAULT)
        self._illuminant_yellow_spin.setValue(_ILLUMINANT_YELLOW_DEFAULT)
        self._illuminant_white_spin.setValue(_ILLUMINANT_WHITE_DEFAULT)
