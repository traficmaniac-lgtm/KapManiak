from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from src.ui.main_window import APP_QSS, MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
