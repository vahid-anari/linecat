"""Entry point of the ``linecat`` command."""

import sys

from PySide6.QtWidgets import QApplication

from linecat.catalog_window import DisplayDataApp


def main() -> int:
    app = QApplication(sys.argv)
    window = DisplayDataApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
