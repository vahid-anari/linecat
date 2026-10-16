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
    model = window.table_view.model_()
    cols = model.columns()
    assert model.headerData(cols.index("tau (s)"), 1) is not None
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

    pw.zoom(150, "h")
    assert tab.scroll.zoom() == (1.5, 1.0) and pw.hori_zoom_slider.get_value() == 150
    pw.coarse_scale_slider.set_value(40)
    pw.fine_scale_slider.set_value(1.25)
    pw.change_y_positions(None)
    assert tab.get_comps()["coarse scale factor"] == pytest.approx(0.4)

    pw.on_view_toggled("secondary", True)
    assert tab.comps_dict_name() == "sec" and tab.splitter.widget(0) is tab.scroll
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
