import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

DATA = Path(__file__).resolve().parent / "data"


@pytest.fixture(scope="session")
def qapp():
    # settings go to a throwaway folder so the tests never touch the user's QSettings
    QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, tempfile.mkdtemp())
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tempfile.mkdtemp())
    from sciwidgets.labels import set_latex_enabled
    from sciwidgets.style import apply_sci_style

    set_latex_enabled(False)  # mathtext: fast and independent of a local LaTeX
    app = QApplication.instance() or QApplication([])
    apply_sci_style(app)
    return app


@pytest.fixture(scope="session", autouse=True)
def builtin_folder(tmp_path_factory):
    """Built-in catalogs go to a throwaway folder, never the user's application-data folder."""
    import linecat.builtin
    import linecat.catalog_window

    folder = tmp_path_factory.mktemp("builtin")
    patch = pytest.MonkeyPatch()
    for module in (linecat.builtin, linecat.catalog_window):
        patch.setattr(module, "builtin_dir", lambda: folder)
    yield folder
    patch.undo()


@pytest.fixture
def oh_csv():
    return DATA / "oh_small.csv"


@pytest.fixture
def window(qapp, monkeypatch, oh_csv):
    """A CatalogWindow with the small OH catalog loaded; LaTeX off, dialogs disabled."""
    import linecat.catalog_window as cw
    import linecat.diagram.window as dw

    monkeypatch.setattr(cw, "latex_available", lambda: False)
    monkeypatch.setattr(cw, "show_warning", lambda *a, **k: None)
    monkeypatch.setattr(dw, "show_warning", lambda *a, **k: None)
    monkeypatch.setattr(dw, "show_information", lambda *a, **k: None)
    win = cw.CatalogWindow(str(oh_csv))
    win.show()
    yield win
    win.close()
