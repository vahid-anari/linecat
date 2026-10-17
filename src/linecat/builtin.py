"""Built-in catalogs: the CDMS sources shipped with linecat, converted once into a per-user folder.

The `.cat` files live in the package (`linecat/data/molecules/<SPECIES>/`, next to the species'
CDMS documentation PDFs and its picture). Their CSVs are written
read-only to the user's application-data folder (on macOS
`~/Library/Application Support/linecat/catalogs/`), next to a stamp file holding the linecat
version that built them. `ensure_builtin_catalogs` rebuilds them when a CSV is missing or the
stamp differs, so a new converter version regenerates them by itself.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Callable

from linecat import __version__
from linecat.cdms import ConversionResult, convert_molecule_catalog
from linecat.molecules import REGISTRY

DATA_DIR = Path(__file__).resolve().parent / "data"
SOURCES_DIR = DATA_DIR / "molecules"  # one folder per species: .cat files, documentation PDFs, <SPECIES>.svg
DOCS_DIR = DATA_DIR / "docs"  # general CDMS documentation
STAMP_NAME = ".linecat-version"


def molecule_image(species: str) -> Path | None:
    """The species' picture (`<SPECIES>.svg` in its folder), if there is one."""
    path = SOURCES_DIR / species / f"{species}.svg"
    return path if path.is_file() else None


def molecule_docs(species: str) -> list[Path]:
    """The CDMS documentation PDFs of the species' entries, sorted by name."""
    folder = SOURCES_DIR / species
    return sorted(folder.glob("*.pdf")) if folder.is_dir() else []


def general_docs() -> list[Path]:
    """The general CDMS documentation PDFs, sorted by name."""
    return sorted(DOCS_DIR.glob("*.pdf")) if DOCS_DIR.is_dir() else []


def builtin_dir() -> Path:
    """Folder that holds the built-in CSV catalogs (created on demand)."""
    from PySide6.QtCore import QStandardPaths

    base = QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)
    return Path(base) / "linecat" / "catalogs"


def builtin_csv(species: str, folder: Path | None = None) -> Path:
    """Path of the built-in CSV of ``species``."""
    return (folder or builtin_dir()) / f"CDMS_{REGISTRY[species].species}.csv"


def builtin_is_current(folder: Path | None = None) -> bool:
    """True when every species' CSV exists and was built by this linecat version."""
    folder = folder or builtin_dir()
    stamp = folder / STAMP_NAME
    if not stamp.is_file() or stamp.read_text().strip() != __version__:
        return False
    return all(builtin_csv(code, folder).is_file() for code in REGISTRY)


def _remove(path: Path) -> None:
    if path.exists():
        os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)
        path.unlink()


def ensure_builtin_catalogs(
    folder: Path | None = None,
    progress: Callable[[str, int, int], None] | None = None,
) -> list[ConversionResult]:
    """Build the built-in CSVs if any is missing or out of date; return what was built (empty if nothing).

    `progress` is called with (species, rows done, rows total), as for `cdms.convert_all`.
    """
    folder = folder or builtin_dir()
    if builtin_is_current(folder):
        return []
    folder.mkdir(parents=True, exist_ok=True)
    _remove(folder / STAMP_NAME)
    results = []
    for code in REGISTRY:
        target = builtin_csv(code, folder)
        _remove(target)
        callback = (lambda done, total, code=code: progress(code, done, total)) if progress is not None else None
        result = convert_molecule_catalog(code, outdir=folder, catalogs_dir=SOURCES_DIR, progress=callback)
        os.chmod(result.path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # read-only
        results.append(result)
    (folder / STAMP_NAME).write_text(__version__ + "\n")
    return results
