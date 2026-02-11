"""QSS テーマ定義。

ライトテーマ。アクセントカラー #4a90d9 (青) を一貫使用。
"""

# --- カラーパレット ---
_ACCENT = "#4a90d9"
_ACCENT_HOVER = "#3a7bc8"
_ACCENT_PRESSED = "#2e6ab3"

_GREEN = "#5cb85c"
_GREEN_HOVER = "#4cae4c"
_GREEN_PRESSED = "#449d44"

_AMBER = "#f0ad4e"
_AMBER_HOVER = "#ec971f"
_AMBER_PRESSED = "#d58512"

_PURPLE = "#9b59b6"
_PURPLE_HOVER = "#8e44ad"
_PURPLE_PRESSED = "#7d3c98"

_BG_LIGHT = "#f5f5f5"
_BORDER = "#ddd"
_BORDER_INPUT = "#bbb"
_BORDER_GROUP = "#ccc"
_TEXT = "#333"
_TEXT_MUTED = "#555"
_TEXT_PLACEHOLDER = "#888"
_DISABLED_BG = "#e8e8e8"
_DISABLED_TEXT = "#aaa"

APP_STYLESHEET = f"""
/* ===================== 全体ベース ===================== */
QMainWindow {{
    background-color: #f0f0f0;
}}

/* ===================== メニューバー ===================== */
QMenuBar {{
    background-color: #fafafa;
    border-bottom: 1px solid {_BORDER};
    padding: 2px 0;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 3px;
}}
QMenuBar::item:selected {{
    background-color: {_ACCENT};
    color: white;
}}
QMenu {{
    background-color: white;
    border: 1px solid {_BORDER};
    padding: 4px 0;
}}
QMenu::item {{
    padding: 5px 28px 5px 20px;
}}
QMenu::item:selected {{
    background-color: {_ACCENT};
    color: white;
}}

/* ===================== ステータスバー ===================== */
QStatusBar {{
    background-color: #fafafa;
    border-top: 1px solid {_BORDER};
    color: {_TEXT_MUTED};
    font-size: 12px;
    padding: 2px 8px;
}}

/* ===================== ImageViewer ===================== */
ImageViewer {{
    background-color: {_BG_LIGHT};
    border: 1px solid {_BORDER};
    border-radius: 3px;
}}
ImageViewer[dragActive="true"] {{
    border: 2px solid {_ACCENT};
    background-color: #eef4fb;
}}
ImageViewer QLabel {{
    color: {_TEXT_PLACEHOLDER};
    font-size: 14px;
    background: transparent;
    border: none;
}}

/* ===================== パネルラベル ===================== */
QLabel#panelLabel {{
    font-weight: bold;
    font-size: 12px;
    color: {_TEXT_MUTED};
    padding: 2px 0;
}}

/* ===================== QSplitter ===================== */
QSplitter::handle {{
    background-color: #e0e0e0;
    width: 3px;
    margin: 2px 1px;
    border-radius: 1px;
}}
QSplitter::handle:hover {{
    background-color: {_ACCENT};
}}

/* ===================== QGroupBox ===================== */
QGroupBox {{
    border: 1px solid {_BORDER_GROUP};
    border-radius: 4px;
    margin-top: 10px;
    padding: 8px 6px 4px 6px;
    font-weight: bold;
    color: #444;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 8px;
    color: #444;
}}

/* ===================== QComboBox ===================== */
QComboBox {{
    border: 1px solid {_BORDER_INPUT};
    border-radius: 3px;
    padding: 3px 6px;
    background-color: white;
    min-height: 20px;
}}
QComboBox:hover {{
    border-color: #999;
}}
QComboBox:focus {{
    border-color: {_ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    border: 1px solid {_BORDER};
    selection-background-color: {_ACCENT};
    selection-color: white;
    background-color: white;
}}

/* ===================== QSpinBox / QDoubleSpinBox ===================== */
QSpinBox, QDoubleSpinBox {{
    border: 1px solid {_BORDER_INPUT};
    border-radius: 3px;
    padding: 3px 4px;
    background-color: white;
    min-height: 20px;
}}
QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: #999;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {_ACCENT};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 16px;
    border: none;
    background: transparent;
}}

/* ===================== QCheckBox ===================== */
QCheckBox {{
    spacing: 4px;
    color: {_TEXT};
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {_BORDER_INPUT};
    border-radius: 3px;
    background-color: white;
}}
QCheckBox::indicator:checked {{
    background-color: {_ACCENT};
    border-color: {_ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: #999;
}}

/* ===================== QLabel (一般) ===================== */
QLabel {{
    color: {_TEXT};
}}

/* ===================== QPushButton 共通ベース ===================== */
QPushButton {{
    border: 1px solid {_BORDER_INPUT};
    border-radius: 4px;
    padding: 5px 12px;
    background-color: #fafafa;
    color: {_TEXT};
    font-weight: normal;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: #e8e8e8;
    border-color: #999;
}}
QPushButton:pressed {{
    background-color: #d8d8d8;
}}
QPushButton:disabled {{
    background-color: {_DISABLED_BG};
    color: {_DISABLED_TEXT};
    border-color: #ccc;
}}

/* --- Convert ボタン (青) --- */
QPushButton#convertBtn {{
    background-color: {_ACCENT};
    border-color: {_ACCENT_HOVER};
    color: white;
    font-weight: bold;
}}
QPushButton#convertBtn:hover {{
    background-color: {_ACCENT_HOVER};
}}
QPushButton#convertBtn:pressed {{
    background-color: {_ACCENT_PRESSED};
}}
QPushButton#convertBtn:disabled {{
    background-color: #a3c4e9;
    border-color: #a3c4e9;
    color: #dce8f5;
}}

/* --- Save ボタン (緑) --- */
QPushButton#saveBtn {{
    background-color: {_GREEN};
    border-color: {_GREEN_HOVER};
    color: white;
    font-weight: bold;
}}
QPushButton#saveBtn:hover {{
    background-color: {_GREEN_HOVER};
}}
QPushButton#saveBtn:pressed {{
    background-color: {_GREEN_PRESSED};
}}
QPushButton#saveBtn:disabled {{
    background-color: #a8d5a8;
    border-color: #a8d5a8;
    color: #d9eed9;
}}

/* --- Reconvert ボタン (アンバー) --- */
QPushButton#reconvertBtn {{
    background-color: {_AMBER};
    border-color: {_AMBER_HOVER};
    color: white;
    font-weight: bold;
}}
QPushButton#reconvertBtn:hover {{
    background-color: {_AMBER_HOVER};
}}
QPushButton#reconvertBtn:pressed {{
    background-color: {_AMBER_PRESSED};
}}
QPushButton#reconvertBtn:disabled {{
    background-color: #f5d49a;
    border-color: #f5d49a;
    color: #fbecd0;
}}

/* --- Gamut Only ボタン (グレー) --- */
QPushButton#gamutOnlyBtn {{
    background-color: #e0e0e0;
    border-color: #bbb;
    color: {_TEXT};
}}
QPushButton#gamutOnlyBtn:hover {{
    background-color: #d0d0d0;
    border-color: #999;
}}
QPushButton#gamutOnlyBtn:pressed {{
    background-color: #c0c0c0;
}}
QPushButton#gamutOnlyBtn:disabled {{
    background-color: {_DISABLED_BG};
    color: {_DISABLED_TEXT};
}}

/* --- Optimize ボタン (紫) --- */
QPushButton#optimizeBtn {{
    background-color: {_PURPLE};
    border-color: {_PURPLE_HOVER};
    color: white;
    font-weight: bold;
}}
QPushButton#optimizeBtn:hover {{
    background-color: {_PURPLE_HOVER};
}}
QPushButton#optimizeBtn:pressed {{
    background-color: {_PURPLE_PRESSED};
}}
QPushButton#optimizeBtn:disabled {{
    background-color: #c9a0d8;
    border-color: #c9a0d8;
    color: #e8d5f0;
}}

/* --- Illuminant Reset ボタン (小) --- */
QPushButton#illuminantResetBtn {{
    padding: 3px 6px;
    font-size: 14px;
}}
"""
