"""Light and dark mode: View ▸ Appearance, the palette-based style sheet and the diagram's colours."""

import matplotlib.colors as mcolors
import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFileDialog
from sciwidgets.style import color_scheme, is_dark, set_color_scheme

import linecat.catalog_window as cw
from linecat.diagram.elements import DIAGRAM_COLORS
from linecat.widgets import APP_STYLE_SHEET


@pytest.fixture
def system_scheme(qapp):
    """Back to the system's colours after the test."""
    yield
    set_color_scheme(qapp, "system")
    qapp.processEvents()


def _open_diagram(window):
    window.filter_combos["U-S J"].set_value("3/2")
    window.update_filters()
    window.on_menu_action("Transitions", "show_diagram", False)
    return window.plot_window


def _same(a, b):
    return mcolors.to_hex(a) == mcolors.to_hex(b)


def test_style_sheet_has_no_fixed_colours():
    assert "#" not in APP_STYLE_SHEET and "white" not in APP_STYLE_SHEET
    assert "palette(base)" in APP_STYLE_SHEET


def test_appearance_menu_switches_and_is_remembered(window, qapp, system_scheme):
    view = next(a.menu() for a in window.menuBar().actions() if a.text() == "View")
    appearance = next(a.menu() for a in view.actions() if a.text() == "Appearance")
    assert [a.text() for a in appearance.actions()] == ["Same as System", "Light", "Dark"]
    window.on_menu_action("View", "appearance_dark", True)
    qapp.processEvents()
    assert is_dark() and color_scheme() == "dark"
    assert window.settings.value(cw.APPEARANCE_KEY) == "dark"
    assert [a.isChecked() for a in appearance.actions()] == [False, False, True]
    window.on_menu_action("View", "appearance_light", True)
    qapp.processEvents()
    assert not is_dark() and window.appearance() == "light"
    window.settings.setValue(cw.APPEARANCE_KEY, "dark")
    second = cw.CatalogWindow()  # a new window starts with the remembered choice
    assert color_scheme() == "dark"
    second.close()
    window.set_appearance("system")
    assert window.appearance() == "system"


def test_molecule_placeholder_is_greyed(window):
    window.molecule_box.clear()
    assert not window.molecule_box.details.isEnabled()


def test_diagram_follows_dark_mode_and_saves_light(window, qapp, system_scheme, tmp_path, monkeypatch):
    set_color_scheme(qapp, "light")
    qapp.processEvents()
    pw = _open_diagram(window)
    comps = pw.tabs_content[0].get_comps()
    fig, lvls, arrows = comps["fig"], comps["lvls"], comps["arrows"]
    light, dark = DIAGRAM_COLORS[False], DIAGRAM_COLORS[True]
    assert _same(fig.get_facecolor(), light["face"])
    arrows[0].selected(True)
    lvls[0].selected(True)

    set_color_scheme(qapp, "dark")
    for _ in range(3):
        qapp.processEvents()
    assert _same(fig.get_facecolor(), dark["face"])
    assert _same(lvls[0].lvl.get_color(), dark["ink"])
    assert _same(lvls[0].line.get_color(), dark["level_selected"])  # still highlighted
    assert _same(lvls[-1].line.get_color(), dark["ink"])
    assert _same(arrows[0].arrow.get_facecolor(), dark["trans"][arrows[0].type][1])
    assert _same(arrows[1].number_text.get_bbox_patch().get_facecolor(), dark["face"])

    saved = []
    from matplotlib.backends.backend_pdf import PdfPages
    original = PdfPages.savefig

    def record(pdf, figure=None, **kwargs):
        if figure is fig:
            saved.append((mcolors.to_hex(fig.get_facecolor()), mcolors.to_hex(lvls[-1].line.get_color())))
        return original(pdf, figure, **kwargs)

    monkeypatch.setattr(PdfPages, "savefig", record)
    out = tmp_path / "fig.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    pw.on_menu_action("File", "save_pdf", False)
    assert saved == [(mcolors.to_hex(light["face"]), mcolors.to_hex(light["ink"]))]
    assert _same(fig.get_facecolor(), dark["face"])  # dark again in the window

    pw.on_view_toggled("secondary", True)  # a figure built in dark mode starts dark
    sec = pw.tabs_content[0].get_comps()
    if sec["fig"] is not fig:
        assert _same(sec["fig"].get_facecolor(), dark["face"])

    set_color_scheme(qapp, "light")
    for _ in range(3):
        qapp.processEvents()
    assert _same(fig.get_facecolor(), light["face"])
    assert _same(lvls[0].line.get_color(), light["level_selected"])
    pal = pw.tabs_content[0].table_scroll.palette()
    for role in (QPalette.Highlight, QPalette.HighlightedText):
        assert pal.color(QPalette.Inactive, role) == pal.color(QPalette.Active, role)
    pw.close()


def _appearance_checks(win):
    view = next(a.menu() for a in win.menuBar().actions() if a.text() == "View")
    appearance = next(a.menu() for a in view.actions() if a.text() == "Appearance")
    return [a.isChecked() for a in appearance.actions()]


def test_diagram_window_has_appearance_too(window, qapp, system_scheme):
    pw = _open_diagram(window)
    assert _appearance_checks(pw) == [True, False, False]
    pw.on_menu_action("View", "appearance_dark", True)
    qapp.processEvents()
    assert is_dark() and window.appearance() == "dark"
    assert _appearance_checks(pw) == _appearance_checks(window) == [False, False, True]
    window.on_menu_action("View", "appearance_system", True)
    assert _appearance_checks(pw) == [True, False, False]
    pw.close()
