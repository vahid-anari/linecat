"""Conversion of CDMS .cat files with a progress dialog (worker thread) and a final report."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QProgressDialog, QWidget

from sciwidgets.dialogs import show_critical, show_information

from linecat.cdms import ConversionCancelled, ConversionResult, convert_molecule_catalog


class ConvertWorker(QThread):
    """Convert a list of species in the background, one after the other."""

    progress = Signal(str, int, int)  # species, rows done, rows total
    finished_ok = Signal(list)  # list[ConversionResult]
    failed = Signal(str)

    def __init__(self, species: list[str], folder: str, parent=None) -> None:
        super().__init__(parent)
        self._species = list(species)
        self._folder = folder
        self._cancelled = False
        self.results: list[ConversionResult] = []

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            for code in self._species:
                result = convert_molecule_catalog(
                    code, outdir=self._folder, catalogs_dir=self._folder,
                    progress=lambda done, total, code=code: self._report(code, done, total),
                )
                self.results.append(result)
        except ConversionCancelled:
            self.finished_ok.emit(self.results)
            return
        except Exception as exc:  # noqa: BLE001 - shown to the user
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.finished_ok.emit(self.results)

    def _report(self, code: str, done: int, total: int) -> None:
        if self._cancelled:
            raise ConversionCancelled
        self.progress.emit(code, done, total)


def report_text(results: list[ConversionResult], cancelled: bool) -> str:
    """HTML lines of the final report."""
    lines = [f"<b>{r.species}</b>: {r.rows:,} lines &rarr; {r.path.name}" for r in results]
    if cancelled:
        lines.append("<i>Cancelled.</i>")
    return "<br>".join(lines) if lines else "Nothing converted."


def convert_with_progress(parent: QWidget, species: list[str], folder: str, on_done) -> ConvertWorker:
    """Run the conversion in a thread behind a progress dialog; call ``on_done(results)`` at the end.

    The dialog has a Cancel button; species already converted are kept. Errors
    are shown in a dialog and ``on_done`` gets the species finished before it.
    """
    dialog = QProgressDialog("Preparing…", "Cancel", 0, 100, parent)
    dialog.setWindowTitle("Converting CDMS catalogs")
    dialog.setWindowModality(Qt.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    dialog.setMinimumWidth(420)

    worker = ConvertWorker(species, folder, parent)
    index = {code: i for i, code in enumerate(species)}

    def on_progress(code: str, done: int, total: int) -> None:
        percent = 100 * done // total if total else 100
        dialog.setLabelText(f"{code} ({index[code] + 1} of {len(species)}): {done:,} / {total:,} lines")
        dialog.setValue(percent)

    def finish(results: list, cancelled: bool) -> None:
        dialog.close()
        show_information("Conversion finished" if not cancelled else "Conversion cancelled",
                         f"{len(results)} of {len(species)} species converted in {Path(folder).name}/",
                         report_text(results, cancelled), parent=parent)
        on_done(results)

    worker.progress.connect(on_progress)
    worker.finished_ok.connect(lambda results: finish(results, worker.isCancelled()))
    worker.failed.connect(lambda message: (dialog.close(),
                                           show_critical("Conversion failed", message, parent=parent),
                                           on_done(worker.results)))
    dialog.canceled.connect(worker.cancel)
    worker.isCancelled = lambda: worker._cancelled
    worker.start()
    return worker
