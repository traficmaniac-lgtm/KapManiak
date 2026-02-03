import os
import sys

from PySide6.QtWidgets import QApplication

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ui import ResonanceWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    window = ResonanceWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
