from __future__ import annotations

import sys
from PyQt6.QtWidgets import QApplication
from .ui.hologram_window import HologramWindow


def main():
    app = QApplication(sys.argv)
    win = HologramWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
