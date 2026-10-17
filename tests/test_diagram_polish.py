"""Diagram polish (0.10.0): size from content, column packing, labels, tab titles, limit, LaTeX dialog."""

import itertools

import numpy as np
import pytest

from linecat.diagram.elements import (
    DEFAULT_SIZE, frequency_parts, hover_text, level_y_limits, lifetime_parts, short_number,
)
from linecat.diagram.window import frequency_range_text, plain_level
from linecat.dialogs import KEY_ASK, KEY_LIMIT, LargeDiagramDialog, LatexCommandsDialog, large_diagram_limit


@pytest.fixture
def big_window(qapp, monkeypatch):
    """The main window with the built-in NH3 catalog and its first 70 lines selected."""
    import linecat.catalog_window as cw
    import linecat.diagram.window as dw
    from linecat.builtin import builtin_csv, ensure_builtin_catalogs

    ensure_builtin_catalogs()
    monkeypatch.setattr(cw, "latex_available", lambda: False)
    monkeypatch.setattr(cw, "show_warning", lambda *a, **k: None)
    monkeypatch.setattr(dw, "show_warning", lambda *a, **k: None)
    monkeypatch.setattr(dw, "show_information", lambda *a, **k: None)
    win = cw.CatalogWindow(str(builtin_csv("NH3")))
    win.show()
    win.filtered_df = win.filtered_df.iloc[:70]
    win.open_diagram()
    yield win
    win.plot_window.close()
    win.close()


# ----- numbers and labels -----

def test_frequency_and_lifetime_parts():
    assert frequency_parts(0.5) == ("500", "k")                         # kHz with a small k
    assert frequency_parts(88.9495) == ("88.9", "M")
    assert frequency_parts(22235.08) == ("22.2", "G")
    assert frequency_parts(1.2e6) == ("1.20", "T")
    assert lifetime_parts(3.888e8) == ("3.89", 8)
    assert short_number(4.567) == "4.57" and short_number(456.7) == "457"


def test_hover_text_has_two_lines_with_units():
    nu, tau = hover_text(22235.08, 3.888e8).split("\n")
    assert r"\nu = 22.2" in nu and r"\mathrm{GHz}" in nu
    assert r"\tau = 3.89\times 10^{8}" in tau and r"\mathrm{s}" in tau


def test_plain_level_and_range():
    assert plain_level(r"$(6,\,1)\,6^-$") == "(6, 1) 6−"
    assert plain_level(r"$9/2,\,1/2,\,5^+,\,(2)$") == "9/2, 1/2, 5+, (2)"
    import pandas as pd

    assert frequency_range_text(pd.Series([18400.0, 22235.0])) == "18.4–22.2 GHz"
    assert frequency_range_text(pd.Series([88.9, 787.7])) == "88.9–788 MHz"
    assert frequency_range_text(pd.Series([1667.0])) == "1.67 GHz"


def test_level_limits_pad_by_level_spacing():
    lo, hi = level_y_limits(np.arange(10.0))
    assert lo == pytest.approx(-0.6) and hi == pytest.approx(9.6)


# ----- size and layout -----

def test_small_diagram_keeps_default_size(window):
    window.filter_combos["U-S J"].set_value("3/2")
    window.update_filters()
    window.on_menu_action("Transitions", "show_diagram", False)
    pw = window.plot_window
    fig = pw.tabs_content[0].scroll.figure
    assert tuple(fig.get_size_inches()) >= DEFAULT_SIZE or fig.get_size_inches()[1] == DEFAULT_SIZE[1]
    assert pw.tabs.tabText(0).startswith("OH · ") and pw.tabs.tabText(0).endswith("lines")
    pw.close()


def _readable(fig, arrows, lvls):
    """No two level labels overlap in height, and no two transition circles overlap."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = sorted((t.get_window_extent(renderer) for lvl in lvls for t in (lvl.lvl,)), key=lambda b: b.y0)
    labels_ok = all(b.y0 >= a.y1 - 1 for a, b in itertools.pairwise(boxes))
    circles = [a.number_text.get_bbox_patch().get_window_extent(renderer) for a in arrows]
    circles_ok = not any(a.overlaps(b) and a.width and (min(a.x1, b.x1) - max(a.x0, b.x0)) > 2
                         and (min(a.y1, b.y1) - max(a.y0, b.y0)) > 2
                         for a, b in itertools.combinations(circles, 2))
    return labels_ok, circles_ok


def test_big_diagram_grows_and_stays_readable(big_window):
    pw = big_window.plot_window
    tab = pw.tabs_content[0]
    comps = tab.get_comps()
    fig = comps['fig']
    tab.fit = False
    tab.scroll.set_zoom(1.0, 1.0)
    width, height = fig.get_size_inches()
    assert height > DEFAULT_SIZE[1] * 2                                 # many levels: a taller figure
    assert width < 2 * DEFAULT_SIZE[0]                                  # groups share columns
    assert _readable(fig, comps['arrows'], comps['lvls']) == (True, True)
    assert fig.legible_fraction[1] == pytest.approx(1.0)
    assert pw.tabs.tabText(0).startswith("NH₃ · ") and "70 lines" in pw.tabs.tabText(0)


def test_fit_stops_at_readable_size(big_window, qapp):
    pw = big_window.plot_window
    pw.resize(1100, 700)
    for _ in range(5):
        qapp.processEvents()
    tab = pw.tabs_content[0]
    tab.apply_fit()
    assert tab.scroll.zoom()[1] >= tab.scroll.figure.legible_fraction[1] - 0.01


def test_first_tab_cannot_close_and_double_click_title(big_window):
    pw = big_window.plot_window
    pw.close_tab(0)
    assert pw.tabs.count() == 1
    arrow = pw.tabs_content[0].get_comps()['arrows'][0]
    trs = pw.df[pw.df['upper lvl'] == arrow.lower_lvl].copy()
    if not trs.empty:
        pw.build_new_tab(trs, f"From {plain_level(arrow.lower_lvl)}")
        assert pw.tabs.tabText(1).startswith("From (")


def test_hover_label_turns_towards_the_middle(window):
    from matplotlib.backend_bases import MouseEvent

    window.filter_combos["U-S J"].set_value("3/2")
    window.update_filters()
    window.on_menu_action("Transitions", "show_diagram", False)
    pw = window.plot_window
    comps = pw.tabs_content[0].get_comps()
    fig, ax = comps['fig'], comps['ax']
    fig.canvas.draw()
    label = next(t for t in ax.texts if t.get_bbox_patch() is not None and t.get_fontsize() >= 16)
    sides = set()
    for arrow in comps['arrows']:
        x, y = ax.transData.transform((arrow.x, arrow.y_mid))
        fig.canvas.callbacks.process("motion_notify_event", MouseEvent("motion_notify_event", fig.canvas, x, y))
        if label.get_visible():
            sides.add(label.get_ha())
            assert "\n" in label.get_text()
    assert sides <= {"left", "right"} and sides
    pw.close()


# ----- large-diagram limit -----

def test_large_diagram_limit_setting(qapp, tmp_path):
    from PySide6.QtCore import QSettings

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    assert large_diagram_limit(settings) == 50
    dialog = LargeDiagramDialog(settings)
    dialog.limit.setValue(120)
    dialog.accept()
    assert large_diagram_limit(settings) == 120
    dialog = LargeDiagramDialog(settings)
    assert dialog.limit.value() == 120
    dialog.ask.setChecked(False)
    assert not dialog.limit.isEnabled()
    dialog.accept()
    assert large_diagram_limit(settings) is None
    assert settings.value(KEY_ASK, type=bool) is False and settings.value(KEY_LIMIT, type=int) == 120


def test_limit_decides_whether_to_ask(window, monkeypatch):
    import linecat.catalog_window as cw

    asked, opened = [], []
    monkeypatch.setattr(cw, "ask_question", lambda *a, **k: asked.append(a) or cw.AskResult.CANCEL)
    monkeypatch.setattr(window, "open_diagram", lambda: opened.append(1))
    n = len(window.filtered_df)
    window.settings.setValue(KEY_ASK, True)
    window.settings.setValue(KEY_LIMIT, 10)
    window.show_button()
    assert (len(asked), len(opened)) == ((1, 0) if n > 10 else (0, 1))
    assert not asked or "View ▸ Large Diagram Warning" in asked[0][2]
    window.settings.setValue(KEY_ASK, False)
    window.show_button()
    assert opened
    window.settings.remove(KEY_ASK)
    window.settings.remove(KEY_LIMIT)


# ----- LaTeX commands -----

def test_latex_dialog_copy_and_save(qapp, tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QGuiApplication

    settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    dialog = LatexCommandsDialog("% x\n\\DrawLevel{0,1}{1}{2}\n", settings)
    dialog.copy()
    assert QGuiApplication.clipboard().text().startswith("% x") and dialog.copy_btn.text() == "Copied"
    path = dialog.save(str(tmp_path / "diagram"))
    assert path.suffix == ".tex" and path.read_text().startswith("% x")
    assert settings.value('paths/tex_dir') == str(tmp_path)


def test_latex_commands_pattern(window, monkeypatch):
    import re

    import linecat.dialogs as dialogs

    texts = []
    monkeypatch.setattr(dialogs.LatexCommandsDialog, "exec", lambda self: texts.append(self._text) or 0)
    window.filter_combos["U-S J"].set_value("3/2")
    window.update_filters()
    window.on_menu_action("Transitions", "show_diagram", False)
    pw = window.plot_window
    pw.on_view_toggled("secondary", True)
    pw.latex_format()
    text = texts[0]
    assert text.startswith("% OH · ") and "% \\Level{name}{label}{energy in cm^-1}" in text
    levels = re.findall(r"^\\Level\{(L\d+)\}\{(.+)\}\{([^}]*)\}$", text, re.M)
    names = [name for name, _, _ in levels]
    assert names == [f"L{i}" for i in range(1, len(levels) + 1)]
    energies = [float(e) for _, _, e in levels]
    assert energies == sorted(energies) and all(label.startswith("$") for _, label, _ in levels)
    transitions = re.findall(r"^\\Transition\{(pri|sec)\}\{(\d+)\}\{(L\d+)\}\{(L\d+)\}\{([^}]*)\}\{([^}]*)\}$",
                             text, re.M)
    comps = pw.tabs_content[0].get_comps()
    assert len(transitions) == len(comps['arrows'])
    assert {t for t, *_ in transitions} == {"pri", "sec"}
    for _, _, upper, lower, nu, tau in transitions:
        assert upper in names and lower in names
        assert float(nu) > 0 and re.fullmatch(r"\d\.\d+e-?\d+", tau)
    assert "DrawLevel" not in text and "DrawTr" not in text
    pw.close()


def test_level_energy_is_the_catalog_lower_state_value(window):
    window.filter_combos["U-S J"].set_value("3/2")
    window.update_filters()
    window.on_menu_action("Transitions", "show_diagram", False)
    pw = window.plot_window
    row = pw.df.iloc[0]
    assert pw.level_energy(row['lower lvl']) == row['lower E exact']
    pw.close()


def test_tex_number():
    from linecat.diagram.export import tex_number

    assert tex_number("1.014E+03") == "1.014e3" and tex_number(" 6.277E-08") == "6.277e-8"
    assert tex_number("538570.553") == "538570.553"


def test_tests_never_use_the_real_settings(window):
    from PySide6.QtCore import QSettings

    assert window.settings.format() == QSettings.IniFormat               # throwaway file, also on macOS
    assert window.settings.value(KEY_LIMIT) is None
