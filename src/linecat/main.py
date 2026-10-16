"""Entry point of the ``linecat`` command."""

import sys

from PySide6.QtWidgets import QApplication
from sciwidgets.labels import set_latex_enabled
from sciwidgets.style import apply_sci_style

from linecat.catalog_window import APP_STYLE_SHEET, DisplayDataApp, latex_available


def main() -> int:
    app = QApplication(sys.argv)
    apply_sci_style(app, APP_STYLE_SHEET)
    set_latex_enabled(latex_available())
    window = DisplayDataApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
