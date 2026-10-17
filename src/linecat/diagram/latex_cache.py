"""Run LaTeX for the labels of a figure in the background, behind a progress dialog.

With ``text.usetex`` Matplotlib runs ``latex`` (and on some versions ``dvipng``)
once for every distinct label the first time it is drawn, which freezes the
window for seconds on a large diagram. ``prerender_latex`` does that work in
worker threads first; Matplotlib keeps the results in its TeX cache, so the
first draw afterwards is quick.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib as mpl
from matplotlib.text import Text
from matplotlib.texmanager import TexManager
from PySide6.QtCore import QEventLoop, Qt, QThread, Signal
from PySide6.QtWidgets import QProgressDialog


def latex_jobs(figures, extra=()):
    """The distinct (text, font size) pairs that LaTeX will render for ``figures``, plus ``extra``."""
    pairs = list(extra)
    for fig in figures:
        for text in fig.findobj(Text):
            if text.get_usetex():
                pairs.append((text.get_text(), float(text.get_fontsize())))
    # Matplotlib renders a multi-line text one line at a time
    return sorted({(line, size) for text, size in pairs for line in text.split("\n") if line.strip()})


def _uses_dvipng():
    # Matplotlib before 3.11 always rasterises TeX with dvipng; 3.11 made it a choice
    return mpl.rcParams.get("text.latex.engine", "latex+dvipng") == "latex+dvipng"


def render_one(tex, size, dpi):
    """Run LaTeX for one label; Matplotlib caches the result."""
    if _uses_dvipng():
        TexManager.get_grey(tex, size, dpi)
    TexManager.make_dvi(tex, size)


class _LatexWorker(QThread):
    progress = Signal(int)

    def __init__(self, jobs, dpi, parent=None):
        super().__init__(parent)
        self._jobs = jobs
        self._dpi = dpi

    def run(self):
        done = 0
        with ThreadPoolExecutor(max_workers=max(1, os.cpu_count() or 1)) as pool:
            futures = [pool.submit(render_one, tex, size, self._dpi) for tex, size in self._jobs]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:  # noqa: BLE001 - a label LaTeX cannot render fails again, visibly, when drawn
                    pass
                done += 1
                self.progress.emit(done)


def prerender_latex(parent, figures, extra=(), dpi=None):
    """Render the LaTeX labels of ``figures`` (and ``extra`` (text, size) pairs) behind a progress dialog.

    The dialog shows only when the work takes more than a moment; the window stays responsive meanwhile.
    ``dpi`` is the resolution the figures will be drawn at (it matters only for dvipng).
    """
    jobs = latex_jobs(figures, extra)
    if not jobs:
        return
    if dpi is None:
        ratio = parent.devicePixelRatioF() if parent is not None else 1.0
        dpi = max(float(getattr(fig, "_original_dpi", fig.dpi)) for fig in figures) * ratio if figures else 100.0
    dialog = QProgressDialog("Rendering labels with LaTeX…", None, 0, len(jobs), parent)
    dialog.setWindowTitle("LaTeX")
    dialog.setWindowModality(Qt.WindowModal)
    dialog.setMinimumDuration(400)
    dialog.setMinimumWidth(360)
    worker = _LatexWorker(jobs, dpi, parent)
    worker.progress.connect(lambda done: (dialog.setValue(done),
                                          dialog.setLabelText(f"Rendering labels with LaTeX… {done} of {len(jobs)}")))
    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    worker.start()
    loop.exec()
    worker.wait()
    dialog.close()
    dialog.deleteLater()
    worker.deleteLater()
