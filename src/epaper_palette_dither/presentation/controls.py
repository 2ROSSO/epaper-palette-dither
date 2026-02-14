"""パラメータ制御パネル。

5グループ構成: Source / Color Processing / Dithering Quality / Actions / Reconvert
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QMenu,
    QSpinBox,
    QPushButton,
    QLabel,
)

from epaper_palette_dither.domain.image_model import ColorMode, DisplayPreset

_GAMUT_STRENGTH_DEFAULT = 0.70
_ILLUMINANT_RED_DEFAULT = 1.00
_ILLUMINANT_YELLOW_DEFAULT = 1.00
_ILLUMINANT_WHITE_DEFAULT = 1.00
_BLUR_RADIUS_DEFAULT = 1


class ControlPanel(QWidget):
    """パラメータ制御パネル。"""

    convert_clicked = pyqtSignal()
    gamut_only_clicked = pyqtSignal()
    rotate_clicked = pyqtSignal()
    save_clicked = pyqtSignal()
    reconvert_clicked = pyqtSignal()
    optimize_clicked = pyqtSignal()
    preset_changed = pyqtSignal(DisplayPreset)
    gamut_strength_changed = pyqtSignal(float)
    color_mode_changed = pyqtSignal(object)
    illuminant_red_changed = pyqtSignal(float)
    illuminant_yellow_changed = pyqtSignal(float)
    illuminant_white_changed = pyqtSignal(float)
    csf_chroma_weight_changed = pyqtSignal(float)
    error_clamp_changed = pyqtSignal(int)
    red_penalty_changed = pyqtSignal(float)
    yellow_penalty_changed = pyqtSignal(float)
    use_lab_changed = pyqtSignal(bool)
    lightness_remap_changed = pyqtSignal(bool)
    lightness_clip_limit_changed = pyqtSignal(float)
    blur_radius_changed = pyqtSignal(int)
    brightness_changed = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 0, 4, 0)
        main_layout.setSpacing(2)

        # === Row 1: Source | Color Processing | Dithering Quality ===
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        # --- Source グループ ---
        source_group = QGroupBox("Source")
        source_layout = QVBoxLayout(source_group)
        source_layout.setSpacing(4)

        # Target preset
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target:"))
        self._preset_combo = QComboBox()
        for preset in DisplayPreset:
            self._preset_combo.addItem(
                f"{preset.label} ({preset.width}x{preset.height})",
                preset,
            )
        self._preset_combo.setCurrentIndex(1)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        target_row.addWidget(self._preset_combo)
        source_layout.addLayout(target_row)

        # Auto-rotate + Rotate
        rotate_row = QHBoxLayout()
        self._auto_rotate_check = QCheckBox("Auto\u21bb")
        self._auto_rotate_check.setChecked(True)
        self._auto_rotate_check.setToolTip("縦長画像を読み込み時に自動で横向きに回転")
        rotate_row.addWidget(self._auto_rotate_check)

        self._rotate_btn = QPushButton("\u21bb Rotate")
        self._rotate_btn.setMinimumWidth(80)
        self._rotate_btn.setToolTip("元画像を時計回りに90°回転")
        self._rotate_btn.setEnabled(False)
        self._rotate_btn.clicked.connect(self.rotate_clicked.emit)
        rotate_row.addWidget(self._rotate_btn)
        source_layout.addLayout(rotate_row)

        row1.addWidget(source_group)

        # --- Color Processing グループ ---
        color_group = QGroupBox("Color Processing")
        color_layout = QVBoxLayout(color_group)
        color_layout.setSpacing(4)

        # Color mode + Lab + Gamut strength
        color_row1 = QHBoxLayout()
        color_row1.addWidget(QLabel("Color:"))
        self._color_mode_combo = QComboBox()
        for mode in ColorMode:
            self._color_mode_combo.addItem(mode.value, mode)
        self._color_mode_combo.setCurrentIndex(
            list(ColorMode).index(ColorMode.ILLUMINANT),
        )
        self._color_mode_combo.currentIndexChanged.connect(self._on_color_mode_changed)
        color_row1.addWidget(self._color_mode_combo)

        self._lab_checkbox = QCheckBox("Lab")
        self._lab_checkbox.setToolTip("Lab 空間でガマットマッピングを実行")
        self._lab_checkbox.setChecked(True)
        self._lab_checkbox.setVisible(False)
        self._lab_checkbox.toggled.connect(self.use_lab_changed.emit)
        color_row1.addWidget(self._lab_checkbox)

        self._gamut_spin = QDoubleSpinBox()
        self._gamut_spin.setRange(0.0, 1.0)
        self._gamut_spin.setSingleStep(0.05)
        self._gamut_spin.setDecimals(2)
        self._gamut_spin.setValue(_GAMUT_STRENGTH_DEFAULT)
        self._gamut_spin.setFixedWidth(90)
        self._gamut_spin.setToolTip("ガマットマッピング強度 (0.00〜1.00)")
        self._gamut_spin.setVisible(False)
        self._gamut_spin.valueChanged.connect(self._on_gamut_changed)
        color_row1.addWidget(self._gamut_spin)

        color_row1.addStretch()
        color_layout.addLayout(color_row1)

        # Illuminant Red / Yellow
        color_row2 = QHBoxLayout()
        self._illuminant_red_label = QLabel("Red:")
        color_row2.addWidget(self._illuminant_red_label)
        self._illuminant_red_spin = QDoubleSpinBox()
        self._illuminant_red_spin.setRange(0.0, 1.0)
        self._illuminant_red_spin.setSingleStep(0.05)
        self._illuminant_red_spin.setDecimals(2)
        self._illuminant_red_spin.setValue(_ILLUMINANT_RED_DEFAULT)
        self._illuminant_red_spin.setFixedWidth(90)
        self._illuminant_red_spin.valueChanged.connect(self.illuminant_red_changed.emit)
        color_row2.addWidget(self._illuminant_red_spin)

        self._illuminant_yellow_label = QLabel("Yel:")
        color_row2.addWidget(self._illuminant_yellow_label)
        self._illuminant_yellow_spin = QDoubleSpinBox()
        self._illuminant_yellow_spin.setRange(0.0, 1.0)
        self._illuminant_yellow_spin.setSingleStep(0.05)
        self._illuminant_yellow_spin.setDecimals(2)
        self._illuminant_yellow_spin.setValue(_ILLUMINANT_YELLOW_DEFAULT)
        self._illuminant_yellow_spin.setFixedWidth(90)
        self._illuminant_yellow_spin.valueChanged.connect(self.illuminant_yellow_changed.emit)
        color_row2.addWidget(self._illuminant_yellow_spin)

        color_row2.addStretch()
        color_layout.addLayout(color_row2)

        # Illuminant White + Reset
        color_row3 = QHBoxLayout()
        self._illuminant_white_label = QLabel("Whi:")
        color_row3.addWidget(self._illuminant_white_label)
        self._illuminant_white_spin = QDoubleSpinBox()
        self._illuminant_white_spin.setRange(0.0, 1.0)
        self._illuminant_white_spin.setSingleStep(0.05)
        self._illuminant_white_spin.setDecimals(2)
        self._illuminant_white_spin.setValue(_ILLUMINANT_WHITE_DEFAULT)
        self._illuminant_white_spin.setFixedWidth(90)
        self._illuminant_white_spin.setToolTip("明部の白保持 (0=無効, 1=明部を完全保持)")
        self._illuminant_white_spin.valueChanged.connect(self.illuminant_white_changed.emit)
        color_row3.addWidget(self._illuminant_white_spin)

        self._illuminant_reset_btn = QPushButton("\u21ba")
        self._illuminant_reset_btn.setObjectName("illuminantResetBtn")
        self._illuminant_reset_btn.setFixedWidth(30)
        self._illuminant_reset_btn.setToolTip("Illuminant パラメータをリセット")
        self._illuminant_reset_btn.clicked.connect(self._on_illuminant_reset)
        color_row3.addWidget(self._illuminant_reset_btn)

        color_row3.addStretch()
        color_layout.addLayout(color_row3)

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
        for w in self._illuminant_widgets:
            w.setVisible(True)

        row1.addWidget(color_group, stretch=1)

        # --- Dithering Quality グループ ---
        quality_group = QGroupBox("Dithering Quality")
        quality_layout = QVBoxLayout(quality_group)
        quality_layout.setSpacing(4)

        # CSF Chroma Weight
        csf_row = QHBoxLayout()
        csf_row.addWidget(QLabel("CSF:"))
        self._csf_chroma_spin = QDoubleSpinBox()
        self._csf_chroma_spin.setRange(0.0, 1.0)
        self._csf_chroma_spin.setSingleStep(0.05)
        self._csf_chroma_spin.setDecimals(2)
        self._csf_chroma_spin.setValue(0.60)
        self._csf_chroma_spin.setFixedWidth(90)
        self._csf_chroma_spin.setToolTip(
            "色差チャンネル減衰 (0.00=輝度のみ伝播, 1.00=従来通り)"
        )
        self._csf_chroma_spin.valueChanged.connect(self.csf_chroma_weight_changed.emit)
        csf_row.addWidget(self._csf_chroma_spin)
        quality_layout.addLayout(csf_row)

        # ErrClamp
        err_row = QHBoxLayout()
        err_row.addWidget(QLabel("ErrClamp:"))
        self._error_clamp_spin = QSpinBox()
        self._error_clamp_spin.setRange(0, 128)
        self._error_clamp_spin.setValue(85)
        self._error_clamp_spin.setFixedWidth(90)
        self._error_clamp_spin.setToolTip("誤差拡散クランプ (0=無効, 値が小さいほど強い抑制)")
        self._error_clamp_spin.valueChanged.connect(self.error_clamp_changed.emit)
        err_row.addWidget(self._error_clamp_spin)
        quality_layout.addLayout(err_row)

        # RedPen
        red_row = QHBoxLayout()
        red_row.addWidget(QLabel("RedPen:"))
        self._red_penalty_spin = QDoubleSpinBox()
        self._red_penalty_spin.setRange(0.0, 100.0)
        self._red_penalty_spin.setSingleStep(1.0)
        self._red_penalty_spin.setDecimals(1)
        self._red_penalty_spin.setValue(0.0)
        self._red_penalty_spin.setFixedWidth(90)
        self._red_penalty_spin.setToolTip("明部での赤ペナルティ (0=無効, CIEDE2000距離に加算)")
        self._red_penalty_spin.valueChanged.connect(self.red_penalty_changed.emit)
        red_row.addWidget(self._red_penalty_spin)
        quality_layout.addLayout(red_row)

        # YellowPen
        yel_row = QHBoxLayout()
        yel_row.addWidget(QLabel("YellowPen:"))
        self._yellow_penalty_spin = QDoubleSpinBox()
        self._yellow_penalty_spin.setRange(0.0, 100.0)
        self._yellow_penalty_spin.setSingleStep(1.0)
        self._yellow_penalty_spin.setDecimals(1)
        self._yellow_penalty_spin.setValue(0.0)
        self._yellow_penalty_spin.setFixedWidth(90)
        self._yellow_penalty_spin.setToolTip("暗部での黄ペナルティ (0=無効, CIEDE2000距離に加算)")
        self._yellow_penalty_spin.valueChanged.connect(self.yellow_penalty_changed.emit)
        yel_row.addWidget(self._yellow_penalty_spin)
        quality_layout.addLayout(yel_row)

        # CLAHE
        clahe_row = QHBoxLayout()
        self._clahe_check = QCheckBox("CLAHE")
        self._clahe_check.setToolTip("L* チャンネルに適応的ヒストグラム均等化を適用")
        self._clahe_check.setChecked(False)
        self._clahe_check.toggled.connect(self._on_clahe_toggled)
        clahe_row.addWidget(self._clahe_check)

        clahe_row.addWidget(QLabel("Clip:"))
        self._clahe_clip_spin = QDoubleSpinBox()
        self._clahe_clip_spin.setRange(1.0, 4.0)
        self._clahe_clip_spin.setSingleStep(0.25)
        self._clahe_clip_spin.setDecimals(2)
        self._clahe_clip_spin.setValue(2.0)
        self._clahe_clip_spin.setFixedWidth(90)
        self._clahe_clip_spin.setToolTip("CLAHE コントラスト制限 (1.0=弱い, 4.0=強い)")
        self._clahe_clip_spin.setEnabled(False)
        self._clahe_clip_spin.valueChanged.connect(self.lightness_clip_limit_changed.emit)
        clahe_row.addWidget(self._clahe_clip_spin)
        quality_layout.addLayout(clahe_row)

        row1.addWidget(quality_group)

        main_layout.addLayout(row1)

        # === Row 2: Actions | Reconvert ===
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        # --- Actions グループ ---
        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setSpacing(6)

        self._convert_btn = QPushButton("\u25b6 Convert")
        self._convert_btn.setObjectName("convertBtn")
        self._convert_btn.setMinimumWidth(100)
        self._convert_btn.clicked.connect(self.convert_clicked.emit)
        actions_layout.addWidget(self._convert_btn)

        self._gamut_only_btn = QPushButton("\U0001f3a8 Gamut Only")
        self._gamut_only_btn.setObjectName("gamutOnlyBtn")
        self._gamut_only_btn.setMinimumWidth(100)
        self._gamut_only_btn.setToolTip("ディザリングなしでガマットマッピングのみ適用")
        self._gamut_only_btn.clicked.connect(self.gamut_only_clicked.emit)
        actions_layout.addWidget(self._gamut_only_btn)

        self._save_btn = QPushButton("\U0001f4be Save")
        self._save_btn.setObjectName("saveBtn")
        self._save_btn.setMinimumWidth(80)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self.save_clicked.emit)
        actions_layout.addWidget(self._save_btn)

        self._optimize_btn = QPushButton("\u2699 Optimize")
        self._optimize_btn.setObjectName("optimizeBtn")
        self._optimize_btn.setMinimumWidth(100)
        self._optimize_btn.setToolTip("パラメータを自動最適化（Optuna TPE）\n右クリックで Trial 数を変更")
        self._optimize_btn.setEnabled(False)
        self._optimize_btn.clicked.connect(self.optimize_clicked.emit)
        self._optimize_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._optimize_btn.customContextMenuRequested.connect(self._show_optimize_menu)
        self._optimize_n_trials = 50
        actions_layout.addWidget(self._optimize_btn)

        row2.addWidget(actions_group)

        # --- Reconvert グループ ---
        reconvert_group = QGroupBox("Reconvert")
        reconvert_layout = QHBoxLayout(reconvert_group)
        reconvert_layout.setSpacing(6)

        reconvert_layout.addWidget(QLabel("Blur:"))
        self._blur_radius_spin = QSpinBox()
        self._blur_radius_spin.setRange(1, 20)
        self._blur_radius_spin.setValue(_BLUR_RADIUS_DEFAULT)
        self._blur_radius_spin.setFixedWidth(70)
        self._blur_radius_spin.setToolTip("ガウシアンブラー半径 (1〜20)")
        self._blur_radius_spin.valueChanged.connect(self.blur_radius_changed.emit)
        reconvert_layout.addWidget(self._blur_radius_spin)

        reconvert_layout.addWidget(QLabel("Bright:"))
        self._brightness_spin = QDoubleSpinBox()
        self._brightness_spin.setRange(0.50, 2.00)
        self._brightness_spin.setSingleStep(0.05)
        self._brightness_spin.setDecimals(2)
        self._brightness_spin.setValue(1.00)
        self._brightness_spin.setFixedWidth(90)
        self._brightness_spin.setToolTip("明るさ手動調整 (1.00=自動のみ)")
        self._brightness_spin.valueChanged.connect(self.brightness_changed.emit)
        reconvert_layout.addWidget(self._brightness_spin)

        reconvert_layout.addStretch()

        self._reconvert_btn = QPushButton("\u25c0 Reconvert")
        self._reconvert_btn.setObjectName("reconvertBtn")
        self._reconvert_btn.setMinimumWidth(110)
        self._reconvert_btn.setToolTip("ディザ結果をブラー＋逆ガマットで復元")
        self._reconvert_btn.setEnabled(False)
        self._reconvert_btn.clicked.connect(self.reconvert_clicked.emit)
        reconvert_layout.addWidget(self._reconvert_btn)

        row2.addWidget(reconvert_group, stretch=1)

        main_layout.addLayout(row2)

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

    def set_reconvert_enabled(self, enabled: bool) -> None:
        self._reconvert_btn.setEnabled(enabled)

    @property
    def auto_rotate(self) -> bool:
        return self._auto_rotate_check.isChecked()

    @property
    def blur_radius(self) -> int:
        return self._blur_radius_spin.value()

    @property
    def brightness(self) -> float:
        return self._brightness_spin.value()

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
            self._lab_checkbox.setVisible(
                mode in (ColorMode.ANTI_SATURATION, ColorMode.CENTROID_CLIP),
            )
            self.color_mode_changed.emit(mode)

    @property
    def current_color_mode(self) -> ColorMode:
        return self._color_mode_combo.currentData()

    def _on_gamut_changed(self, value: float) -> None:
        self.gamut_strength_changed.emit(value)

    def set_optimize_enabled(self, enabled: bool) -> None:
        self._optimize_btn.setEnabled(enabled)

    def get_current_params(self) -> dict[str, float]:
        """現在の全パラメータを dict で取得。"""
        return {
            "gamut_strength": self._gamut_spin.value(),
            "illuminant_red": self._illuminant_red_spin.value(),
            "illuminant_yellow": self._illuminant_yellow_spin.value(),
            "illuminant_white": self._illuminant_white_spin.value(),
            "csf_chroma_weight": self._csf_chroma_spin.value(),
            "error_clamp": float(self._error_clamp_spin.value()),
            "red_penalty": self._red_penalty_spin.value(),
            "yellow_penalty": self._yellow_penalty_spin.value(),
            "lightness_remap": 1.0 if self._clahe_check.isChecked() else 0.0,
            "lightness_clip_limit": self._clahe_clip_spin.value(),
            "blur_radius": float(self._blur_radius_spin.value()),
            "brightness": self._brightness_spin.value(),
        }

    def set_params(self, params: dict[str, float]) -> None:
        """dict からUIにパラメータを反映。"""
        if "gamut_strength" in params:
            self._gamut_spin.setValue(params["gamut_strength"])
        if "illuminant_red" in params:
            self._illuminant_red_spin.setValue(params["illuminant_red"])
        if "illuminant_yellow" in params:
            self._illuminant_yellow_spin.setValue(params["illuminant_yellow"])
        if "illuminant_white" in params:
            self._illuminant_white_spin.setValue(params["illuminant_white"])
        if "csf_chroma_weight" in params:
            self._csf_chroma_spin.setValue(params["csf_chroma_weight"])
        if "error_clamp" in params:
            self._error_clamp_spin.setValue(int(params["error_clamp"]))
        if "red_penalty" in params:
            self._red_penalty_spin.setValue(params["red_penalty"])
        if "yellow_penalty" in params:
            self._yellow_penalty_spin.setValue(params["yellow_penalty"])
        if "lightness_remap" in params:
            self._clahe_check.setChecked(params["lightness_remap"] >= 0.5)
        if "lightness_clip_limit" in params:
            self._clahe_clip_spin.setValue(params["lightness_clip_limit"])
        if "blur_radius" in params:
            self._blur_radius_spin.setValue(int(params["blur_radius"]))
        if "brightness" in params:
            self._brightness_spin.setValue(params["brightness"])

    def _on_clahe_toggled(self, checked: bool) -> None:
        self._clahe_clip_spin.setEnabled(checked)
        self.lightness_remap_changed.emit(checked)

    def _on_illuminant_reset(self) -> None:
        self._illuminant_red_spin.setValue(_ILLUMINANT_RED_DEFAULT)
        self._illuminant_yellow_spin.setValue(_ILLUMINANT_YELLOW_DEFAULT)
        self._illuminant_white_spin.setValue(_ILLUMINANT_WHITE_DEFAULT)

    @property
    def optimize_n_trials(self) -> int:
        return self._optimize_n_trials

    def _show_optimize_menu(self, pos: object) -> None:
        """Optimize ボタンの右クリックメニュー。"""
        menu = QMenu(self)
        trials_options = [25, 50, 100, 200, 500]
        for n in trials_options:
            action = QAction(f"{n} trials", self)
            action.setCheckable(True)
            action.setChecked(n == self._optimize_n_trials)
            action.triggered.connect(lambda checked, val=n: self._set_optimize_n_trials(val))
            menu.addAction(action)
        menu.exec(self._optimize_btn.mapToGlobal(pos))

    def _set_optimize_n_trials(self, n: int) -> None:
        self._optimize_n_trials = n
        self._optimize_btn.setToolTip(
            f"パラメータを自動最適化（Optuna TPE, {n} trials）\n右クリックで Trial 数を変更"
        )
