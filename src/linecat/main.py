"""Entry point of the ``linecat`` command."""

import argparse
import sys
from pathlib import Path

from linecat import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linecat", description="Line Catalog Explorer: viewer for CDMS/JPL spectral line catalogs.")
    parser.add_argument("--version", action="version", version=f"linecat {__version__}")
    sub = parser.add_subparsers(dest="command")

    view = sub.add_parser("view", help="open the viewer (default)")
    view.add_argument("catalog", nargs="?", help="CSV catalog to open")

    convert = sub.add_parser("convert", help="convert CDMS .cat files to the CSV catalogs the viewer reads")
    convert.add_argument("species", nargs="*", help="species codes (OH, CH3OH, SiO, NH3); none = every one found")
    convert.add_argument("--catalogs", default=None, metavar="DIR",
                         help="folder with the .cat files (default: the CDMS files shipped with linecat)")
    convert.add_argument("--output-dir", default=None, metavar="DIR",
                         help="where to write the CSVs (default: DIR, or the current folder for the shipped files)")
    return parser


def _print_progress(species: str, done: int, total: int) -> None:
    percent = 100 * done // total if total else 100
    end = "\n" if done >= total else ""
    print(f"\r{species}: {done:,} / {total:,} lines ({percent}%)", end=end, flush=True)


def run_convert(args: argparse.Namespace) -> int:
    from linecat.builtin import SOURCES_DIR
    from linecat.cdms import convert_all, convert_molecule_catalog
    from linecat.molecules import REGISTRY

    outdir = args.output_dir or args.catalogs or "."
    args.catalogs = args.catalogs or SOURCES_DIR
    if args.species:
        unknown = [code for code in args.species if code not in REGISTRY]
        if unknown:
            print(f"Unknown species: {', '.join(unknown)}. Known: {', '.join(REGISTRY)}", file=sys.stderr)
            return 2
        results = [
            convert_molecule_catalog(code, outdir=outdir, catalogs_dir=args.catalogs,
                                     progress=lambda d, t, code=code: _print_progress(code, d, t))
            for code in args.species
        ]
    else:
        results = convert_all(args.catalogs, outdir, progress=_print_progress)
        if not results:
            print(f"No registered species has all its .cat files in {Path(args.catalogs).resolve()}", file=sys.stderr)
            return 1
    for result in results:
        print(f"{result.species}: {result.rows:,} lines -> {result.path}")
    return 0


APP_DISPLAY_NAME = "Line Catalog Explorer"


def run_view(catalog: str | None) -> int:
    from PySide6.QtGui import QColor, QIcon
    from PySide6.QtWidgets import QApplication
    from sciwidgets.splash import SplashScreen
    from sciwidgets.style import apply_sci_style

    from linecat.builtin import APP_ICON, APP_IMAGE

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("linecat")
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setWindowIcon(QIcon(str(APP_ICON)))

    base = 35
    splash = SplashScreen(
        APP_IMAGE,
        size=(16 * base, 9 * base),
        title=APP_DISPLAY_NAME.replace(" ", "\n"),
        subtitle=f"Version {__version__}",
        font_family="Times New Roman",
        subtitle_color=QColor(215, 205, 255),
        delay=0.05,
    )
    splash.show_message("Starting...")

    from linecat.catalog_window import APP_STYLE_SHEET, CatalogWindow  # the slow imports, behind the splash

    apply_sci_style(app, APP_STYLE_SHEET)
    splash.show_message("Building the window...")
    window = CatalogWindow(catalog)
    window.show()
    splash.finish(window)
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] not in ("view", "convert", "-h", "--help", "--version"):
        argv = ["view", *argv]
    args = build_parser().parse_args(argv)
    if args.command == "convert":
        return run_convert(args)
    return run_view(getattr(args, "catalog", None))


if __name__ == "__main__":
    sys.exit(main())
