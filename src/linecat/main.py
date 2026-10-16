"""Entry point of the ``linecat`` command."""

import argparse
import sys
from pathlib import Path

from linecat import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linecat", description="Viewer for CDMS/JPL spectral line catalogs.")
    parser.add_argument("--version", action="version", version=f"linecat {__version__}")
    sub = parser.add_subparsers(dest="command")

    view = sub.add_parser("view", help="open the viewer (default)")
    view.add_argument("catalog", nargs="?", help="CSV catalog to open")

    convert = sub.add_parser("convert", help="convert CDMS .cat files to the CSV catalogs the viewer reads")
    convert.add_argument("species", nargs="*", help="species codes (OH, CH3OH, SiO, NH3); none = every one found")
    convert.add_argument("--catalogs", default=".", metavar="DIR", help="folder with the .cat files (default: .)")
    convert.add_argument("--output-dir", default=None, metavar="DIR", help="where to write the CSVs (default: DIR)")
    return parser


def run_convert(args: argparse.Namespace) -> int:
    from linecat.cdms import convert_all, convert_molecule_catalog
    from linecat.molecules import REGISTRY

    outdir = args.output_dir or args.catalogs
    if not args.species:
        written = convert_all(args.catalogs, outdir)
        if not written:
            print(f"No registered species has all its .cat files in {Path(args.catalogs).resolve()}", file=sys.stderr)
            return 1
        return 0
    unknown = [code for code in args.species if code not in REGISTRY]
    if unknown:
        print(f"Unknown species: {', '.join(unknown)}. Known: {', '.join(REGISTRY)}", file=sys.stderr)
        return 2
    for code in args.species:
        convert_molecule_catalog(code, outdir=outdir, catalogs_dir=args.catalogs)
    return 0


def run_view(catalog: str | None) -> int:
    from PySide6.QtWidgets import QApplication
    from sciwidgets.style import apply_sci_style

    from linecat.catalog_window import APP_STYLE_SHEET, CatalogWindow

    app = QApplication(sys.argv)
    app.setApplicationName("linecat")
    apply_sci_style(app, APP_STYLE_SHEET)
    window = CatalogWindow(catalog)
    window.show()
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
