"""Allow ``python -m PyPhast`` to launch the GUI."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import __app_name__
from .gui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName(__app_name__)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
