from __future__ import annotations

import os
import sys

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
os.environ["ABSL_LOGGING_MIN_LOG_LEVEL"] = "3"

from PyQt6.QtWidgets import QApplication

from src.jarvis_air.ui.hologram_window import HologramWindow


def main():
    app = QApplication(sys.argv)

    win = HologramWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
