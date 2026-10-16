"""Window-level tests: catalog loading, filters, export, menus, diagram. Offscreen, no LaTeX."""

import pandas as pd
import pytest
from PySide6.QtWidgets import QFileDialog

import linecat.catalog_window as cw
import linecat.diagram.window as dw


def test_load_and_status(window, oh_csv):
    assert len(window.df) == 129 and len(window.filtered_df) == 129
    assert window.status.get_path() == str(oh_csv)
    assert window.menu.action("export").isEnabled() and window.menu.action("show_diagram").isEnabled()
    assert window.menu.action("recent_0").text() == "oh_small.csv"
    expected = sorted(f"{p} {k}" for p in ("U-S", "L-S") for k in ("J", "Omega", "F", "Parity", "v"))
    assert sorted(window.filter_combos) == expected
    assert window.filter_combos["U-S J"].items()[:2] == ["All", "1/2"]
    assert window.freq_range.range_value[1] == pytest.approx(float(window.df["Frequency (MHz)"].astype(float).max()))


def test_quantum_filter_and_dependent_combos(window):
    window.filter_combos["U-S J"].set_value("3/2")
    window.update_filters()
    assert set(window.filtered_df["U-S J"]) == {"3/2"}
    assert "All" in window.filter_combos["L-S J"].items() and len(window.filter_combos["L-S J"].items()) < 11
    assert window.table_view.model_().rowCount() == len(window.filtered_df)
    window.on_menu_action("View", "reset_filters", False)
    assert len(window.filtered_df) == 129 and window.filter_combos["U-S J"].get_value() == "All"


def test_frequency_range(window):
    fr = window.freq_range
    fr.from_value.set_value(1000)
    fr.to_value.set_value(20000)
    fr.update_range()
    f = window.filtered_df["Frequency (MHz)"].astype(float)
    assert len(window.filtered_df) > 0 and f.min() >= 1000 and f.max() <= 20000
    fr.unit_combo.setCurrentText("GHz")
    fr._set_line_edit_range()
    assert fr.from_value.get_value() == pytest.approx(1.0) and fr.to_value.get_value() == pytest.approx(20.0)


def test_table_headers_and_formats(window):
    from PySide6.QtCore import Qt

    model = window.table_view.model_()
    cols = model.columns()
    assert model.headerData(cols.index("tau (s)"), Qt.Horizontal) == "&tau;<br>(s)"
    nu = model.data(model.index(0, cols.index("Frequency (MHz)")))
    assert "," in nu or "." in nu
    tau = model.data(model.index(0, cols.index("tau (s)")))
    assert "×10<sup>" in tau or tau.replace(".", "").isdigit()


def test_export_visible_columns(window, tmp_path, monkeypatch):
    out = tmp_path / "out.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    window.table_view.set_visible_columns(["Frequency (MHz)", "tau (s)"])
    window.on_menu_action("File", "export", False)
    df = pd.read_csv(out)
    assert list(df.columns) == ["Frequency (MHz)", "tau (s)"] and len(df) == 129


def test_recent_list_and_clear(window, oh_csv, tmp_path):
    other = tmp_path / "second.csv"
    other.write_text(oh_csv.read_text())
    window.load_file(str(other))
    assert window.recent_catalogs()[:2] == [str(other), str(oh_csv)]
    assert window.menu.action("recent_0").text() == "second.csv"
    window.on_menu_action("File", "clear_recent", False)
    assert window.recent_catalogs() == [] and window.menu.action("export").isEnabled()


def test_bad_catalog_is_refused(window, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(cw, "show_warning", lambda title, text, *a, **k: warnings.append(title))
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    window.load_file(str(bad))
    assert warnings == ["Failed"]
    assert len(window.df) == 129 and window.status.get_path().endswith("oh_small.csv")  # previous catalog kept


def test_diagram_window(window, tmp_path, monkeypatch):
    window.filter_combos["U-S J"].set_value("3/2")
    window.update_filters()
    fr = window.freq_range
    fr.from_value.set_value(1000)
    fr.to_value.set_value(60000)
    fr.update_range()
    assert 0 < len(window.filtered_df) <= cw.MAX_PLOT_TRANSITIONS
    window.on_menu_action("Transitions", "show_diagram", False)
    pw = window.plot_window
    tab = pw.tabs_content[0]
    assert pw.tabs.count() == 1 and len(tab.get_comps()["arrows"]) == len(window.filtered_df)
    assert [a.text() for a in pw.menuBar().actions()] == ["File", "View"]

    pw.fit_checkbox.setChecked(False)  # by hand from here on
    pw.zoom(150, "h")
    pw.zoom(100, "v")
    assert tab.scroll.zoom() == (1.5, 1.0) and pw.hori_zoom_slider.get_value() == 150
    pw.coarse_scale_slider.set_value(40)
    pw.fine_scale_slider.set_value(1.25)
    pw.change_y_positions(None)
    assert tab.get_comps()["coarse scale factor"] == pytest.approx(0.4)

    pw.on_view_toggled("secondary", True)
    assert tab.comps_dict_name() == "sec" and tab.row.itemAt(1).widget() is tab.scroll
    assert len(tab.get_comps()["arrows"]) > len(window.filtered_df)  # secondary arrows added
    pw.on_view_toggled("secondary", False)
    assert tab.comps_dict_name() == "pri" and tab.scroll.zoom() == (1.5, 1.0)

    out = tmp_path / "fig.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    pw.on_menu_action("File", "save_pdf", False)
    assert out.stat().st_size > 1000

    arrow = tab.get_comps()["arrows"][0]
    pw.build_new_tab(pw.df[pw.df["upper lvl"] == arrow.lower_lvl].copy(), "x")
    assert pw.tabs.count() == 2
    pw.close_tab(1)
    assert pw.tabs.count() == 1
    pw.close()


def test_diagram_latex_unavailable(window, monkeypatch):
    warned = []
    monkeypatch.setattr(dw, "show_warning", lambda title, *a, **k: warned.append(title))
    window.filter_combos["U-S J"].set_value("1/2")
    window.update_filters()
    assert len(window.filtered_df) <= cw.MAX_PLOT_TRANSITIONS
    window.on_menu_action("Transitions", "show_diagram", False)
    pw = window.plot_window
    assert not pw.menu.action("use_latex").isEnabled()
    pw.on_view_toggled("use_latex", True)
    assert warned == ["LaTeX not available"] and pw.menu.get_checked("use_latex") is False
    pw.close()


def test_frequency_range_switch(window):
    fr = window.freq_range
    fr.from_value.set_value(1000)
    fr.to_value.set_value(20000)
    fr.update_range()
    narrowed = len(window.filtered_df)
    assert 0 < narrowed < 129
    fr.groupbox.setChecked(False)
    assert len(window.filtered_df) == 129 and not fr.from_value.isEnabled()
    assert fr.range_value[1] == pytest.approx(20000)  # the typed range is kept
    fr.groupbox.setChecked(True)
    assert len(window.filtered_df) == narrowed
    fr.groupbox.setChecked(False)
    window.on_menu_action("View", "reset_filters", False)
    assert fr.is_enabled() and len(window.filtered_df) == 129


def test_quantum_grid_layout(window):
    page = window.filter_page
    assert page.title() == "Quantum Numbers"
    assert len(page.combos) == 10 and all(c.get_value() == "All" for c in page.combos.values())


def test_wavelength_format(window):
    model = window.table_view.model_()
    col = model.columns().index("Wavelength (cm)")
    texts = [model.data(model.index(r, col)) for r in range(model.rowCount())]
    assert not any("E+" in t or "E-" in t for t in texts)


def _open_diagram(window):
    window.filter_combos["U-S J"].set_value("3/2")
    window.update_filters()
    fr = window.freq_range
    fr.from_value.set_value(1000)
    fr.to_value.set_value(60000)
    fr.update_range()
    window.on_menu_action("Transitions", "show_diagram", False)
    return window.plot_window


def test_diagram_table_linked_to_arrows(window):
    pw = _open_diagram(window)
    tab = pw.tabs_content[0]
    comps = tab.get_comps()
    table, arrows = tab.table_scroll, comps["arrows"]
    assert table.model_().rowCount() == len(arrows)
    from PySide6.QtCore import Qt

    assert table.model_().headerData(2, Qt.Horizontal) == "&nu;<br>(MHz)"

    # hover in the figure → rows selected, no echo back to the arrows
    comps["table_scroll"]._selection_bridge.hovered.emit([("pri", 2), ("pri", 3)])
    assert table.selected_keys() == [("pri", 2), ("pri", 3)]

    # rows chosen by the user → arrows highlighted
    seen = []
    table.selectedKeysChanged.connect(seen.append)
    table.clearSelection()
    table.selectRow(0)
    key = table.key_of_row(0)
    assert seen[-1] == [key]
    chosen = [a for a in arrows if (a.type, a.number) == key][0]
    assert chosen.arrow.get_linewidth() == 2
    assert all(a.arrow.get_linewidth() < 2 for a in arrows if a is not chosen)

    # sorting keeps the keys right
    table.sortByColumn(3, Qt.DescendingOrder)
    keys = [table.key_of_row(r) for r in range(table.model_().rowCount())]
    assert sorted(keys) == sorted((a.type, a.number) for a in arrows)
    pw.close()


def test_diagram_sliders_upright_and_aligned(window):
    pw = _open_diagram(window)
    sliders = [pw.hori_zoom_slider, pw.vert_zoom_slider, pw.coarse_scale_slider, pw.fine_scale_slider]
    assert all(s._name_label._text.startswith(r"$\mathrm{") for s in sliders)
    assert len({s._effective_name_width() for s in sliders}) == 1
    assert len({s._effective_value_width() for s in sliders}) == 1
    pw.close()


def test_diagram_layout_table_left_fixed_width(window):
    pw = _open_diagram(window)
    tab = pw.tabs_content[0]
    assert tab.row.itemAt(0).widget() is tab.table_scroll and tab.row.itemAt(1).widget() is tab.scroll
    table = tab.table_scroll
    assert table.width() == table.natural_width() and table.horizontalScrollBar().maximum() == 0
    pw.on_view_toggled("secondary", True)
    assert tab.row.itemAt(0).widget() is tab.table_scroll and tab.row.itemAt(1).widget() is tab.scroll
    assert tab.table_scroll.width() == tab.table_scroll.natural_width()
    pw.close()


def _settle(qapp):
    import time

    for _ in range(5):
        qapp.processEvents()
        time.sleep(0.02)


def _fits(tab):
    w, h = tab.scroll.canvas_size()
    vp = tab.scroll.viewport()
    return w <= vp.width() and h <= vp.height()


def test_fit_to_window_follows_resize(window, qapp):
    pw = _open_diagram(window)
    pw.resize(1100, 800)
    _settle(qapp)
    tab = pw.tabs_content[0]
    assert tab.fit and pw.fit_checkbox.isChecked() and pw.menu.get_checked('fit')
    assert not pw.hori_zoom_slider.isEnabled() and _fits(tab)
    assert pw.hori_zoom_slider.get_value() == round(tab.scroll.zoom()[0] * 100)
    small = tab.scroll.zoom()
    pw.resize(1400, 950)
    _settle(qapp)
    assert tab.scroll.zoom()[0] > small[0] and _fits(tab)
    # off: the zoom stays where it is and the sliders work again
    pw.on_menu_action("View", "fit", False)
    assert not tab.fit and not pw.fit_checkbox.isChecked() and pw.hori_zoom_slider.isEnabled()
    kept = tab.scroll.zoom()
    pw.resize(1100, 800)
    _settle(qapp)
    assert tab.scroll.zoom() == kept
    pw.close()


def test_new_tab_fits_and_keeps_old_tab(window, qapp):
    pw = _open_diagram(window)
    pw.resize(1100, 800)
    _settle(qapp)
    first = pw.tabs_content[0]
    pw.fit_checkbox.setChecked(False)
    pw.hori_zoom_slider.set_value(150)
    pw.zoom(150, 'h')
    arrow = first.get_comps()['arrows'][0]
    pw.build_new_tab(pw.df[pw.df['upper lvl'] == arrow.lower_lvl].copy(), "next")
    _settle(qapp)
    new = pw.tabs_content[-1]
    assert new.fit and pw.fit_checkbox.isChecked() and _fits(new)
    assert pw.hori_zoom_slider.get_value() == round(new.scroll.zoom()[0] * 100)
    pw.tabs.setCurrentIndex(0)
    _settle(qapp)
    assert first.scroll.zoom()[0] == 1.5 and not pw.fit_checkbox.isChecked()
    assert pw.hori_zoom_slider.get_value() == 150
    pw.close()


def test_secondary_view_fits_too(window, qapp):
    pw = _open_diagram(window)
    pw.resize(1100, 800)
    _settle(qapp)
    pw.on_view_toggled("secondary", True)
    _settle(qapp)
    assert _fits(pw.tabs_content[0])
    pw.close()


def test_transition_table_selection_same_without_focus(window):
    from PySide6.QtGui import QPalette

    pw = _open_diagram(window)
    pal = pw.tabs_content[0].table_scroll.palette()
    for role in (QPalette.Highlight, QPalette.HighlightedText):
        assert pal.color(QPalette.Inactive, role) == pal.color(QPalette.Active, role)
    pw.close()


def test_side_margins_fit_labels(window, qapp):
    pw = _open_diagram(window)
    pw.fit_checkbox.setChecked(False)
    for percent in (40, 100, 250):
        pw.zoom(percent, "h")
        _settle(qapp)
        fig = pw.tabs_content[0].get_comps()["fig"]
        renderer = fig.canvas.get_renderer()
        right = max(line.energy.get_window_extent(renderer).x1 for line in fig.level_lines)
        left = min(line.lvl.get_window_extent(renderer).x0 for line in fig.level_lines)
        assert 0 < left and right < fig.bbox.width
    pw.close()


def test_prerender_latex_runs_every_label_once(qapp, monkeypatch):
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    import linecat.diagram.latex_cache as lc

    with mpl.rc_context({"text.usetex": True}):
        fig = plt.figure()
        fig.text(0.1, 0.1, r"$5^+_{1,5}$", fontsize=14)
        fig.text(0.1, 0.5, r"$5^+_{1,5}$", fontsize=14)
    fig.text(0.1, 0.9, "plain", fontsize=14)  # not LaTeX
    calls = []
    monkeypatch.setattr(lc, "render_one", lambda tex, size, dpi: calls.append((tex, size)))
    lc.prerender_latex(None, [fig], extra=[("hover", 19.2)])
    assert sorted(calls) == [(r"$5^+_{1,5}$", 14.0), ("hover", 19.2)]
    plt.close(fig)


def test_busy_restores_cursor(qapp):
    from PySide6.QtWidgets import QApplication

    from linecat.widgets import busy

    with busy():
        assert QApplication.overrideCursor() is not None
    assert QApplication.overrideCursor() is None
