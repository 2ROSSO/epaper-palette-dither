"""エントリーポイント: uv run python -m four_color_dither"""

import sys

from PyQt6.QtWidgets import QApplication

from four_color_dither.presentation.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
