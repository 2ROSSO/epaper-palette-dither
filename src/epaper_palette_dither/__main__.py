"""エントリーポイント: uv run python -m epaper_palette_dither"""

import sys

from PyQt6.QtWidgets import QApplication

from epaper_palette_dither.presentation.main_window import MainWindow
from epaper_palette_dither.presentation.styles import APP_STYLESHEET


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
