"""Render the README screenshots: ``python tools/screenshots.py [CATALOG.csv] [--no-latex]``.

Opens the main window with a catalog (default: the built-in OH catalog),
selects J = 3/2 between 1 and 60 GHz, opens the energy-level diagram and
saves both windows to ``docs/images/``. Uses a throwaway settings folder, so
your own linecat settings are not touched. Run it on the Mac (Retina, LaTeX)
for the published pictures.
"""

import argparse
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the README screenshots into docs/images/.")
    parser.add_argument("catalog", nargs="?", default=None, help="CSV catalog (default: built-in OH)")
    parser.add_argument("--no-latex", action="store_true", help="mathtext labels even if LaTeX is installed")
    args = parser.parse_args()
    if args.catalog is None:
        from linecat.builtin import builtin_csv, ensure_builtin_catalogs

        ensure_builtin_catalogs()
        catalog = builtin_csv("OH")
    else:
        catalog = Path(args.catalog)
    if not catalog.is_file():
        print(f"{catalog} not found", file=sys.stderr)
        return 1
    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, tempfile.mkdtemp())

    from sciwidgets.labels import set_latex_enabled
    from sciwidgets.style import apply_sci_style

    import linecat.catalog_window as cw
    from linecat.catalog_window import APP_STYLE_SHEET, CatalogWindow, latex_available

    if args.no_latex:
        cw.latex_available = lambda: False

    app = QApplication(sys.argv[:1])
    app.setApplicationName("linecat")
    apply_sci_style(app, APP_STYLE_SHEET)
    set_latex_enabled(not args.no_latex and latex_available())
    OUT.mkdir(parents=True, exist_ok=True)

    win = CatalogWindow(str(catalog))
    win.resize(1400, 820)
    win.show()
    fr = win.freq_range
    fr.from_value.set_value(1000)
    fr.to_value.set_value(60000)
    fr.update_range()
    win.filter_combos["U-S J"].set_value("3/2")
    win.update_filters()

    def shoot_main():
        win.grab().save(str(OUT / "main_window.png"))
        win.show_button()
        win.plot_window.resize(1400, 950)
        QTimer.singleShot(1500, shoot_diagram)

    def shoot_diagram():
        win.plot_window.grab().save(str(OUT / "diagram.png"))
        print(f"saved {OUT / 'main_window.png'} and {OUT / 'diagram.png'}")
        app.quit()

    QTimer.singleShot(1500, shoot_main)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
