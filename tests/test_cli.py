
import pandas as pd

from linecat.builtin import SOURCES_DIR
from linecat.main import build_parser, main

CATALOGS = SOURCES_DIR  # the CDMS files shipped with linecat


def test_parser_defaults():
    args = build_parser().parse_args(["view", "x.csv"])
    assert args.command == "view" and args.catalog == "x.csv"
    args = build_parser().parse_args(["convert", "OH", "--catalogs", "cats"])
    assert args.command == "convert" and args.species == ["OH"] and args.catalogs == "cats"


def test_convert_unknown_species(capsys):
    assert main(["convert", "XYZ"]) == 2
    assert "Unknown species" in capsys.readouterr().err


def test_convert_nothing_found(tmp_path, capsys):
    assert main(["convert", "--catalogs", str(tmp_path)]) == 1


def test_convert_sio(tmp_path):
    assert main(["convert", "SiO", "--catalogs", str(CATALOGS), "--output-dir", str(tmp_path)]) == 0
    df = pd.read_csv(tmp_path / "CDMS_SiO.csv", dtype=str)
    assert df["Species"].iloc[0] == "SiO" and {"Frequency (MHz)", "U-S J", "L-S v", "tau (s)"} <= set(df.columns)
    assert len(df) > 1000


def test_species_folder_accepted(tmp_path):
    from linecat.cdms import find_cat_file, species_in_folder

    assert species_in_folder(CATALOGS) == ["OH", "CH3OH", "SiO", "NH3"]
    assert species_in_folder(CATALOGS / "SiO") == ["SiO"]
    assert find_cat_file(CATALOGS / "SiO", "SiO/c044505.cat") == CATALOGS / "SiO" / "c044505.cat"
    assert species_in_folder(tmp_path) == []
    assert main(["convert", "--catalogs", str(CATALOGS / "SiO"), "--output-dir", str(tmp_path)]) == 0
    assert (tmp_path / "CDMS_SiO.csv").is_file()



def test_view_shows_splash_then_window(qapp, monkeypatch, oh_csv):
    from sciwidgets.splash import SplashScreen

    import linecat.catalog_window as cw
    from linecat import main as cli

    monkeypatch.setattr(cw, "latex_available", lambda: False)
    monkeypatch.setattr(type(qapp), "exec", lambda self: 0)
    monkeypatch.setattr(cli.sys, "argv", ["linecat"])
    monkeypatch.setattr(cli, "SPLASH_SECONDS", 0)
    assert cli.run_view(str(oh_csv)) == 0
    assert qapp.applicationDisplayName() == cli.APP_DISPLAY_NAME
    assert not qapp.windowIcon().isNull()
    assert SplashScreen.current() is None  # finished once the window was shown
    for widget in qapp.topLevelWidgets():
        if isinstance(widget, cw.CatalogWindow):
            widget.close()


def test_splash_stays_for_the_minimum_time(qapp, monkeypatch, oh_csv):
    from PySide6.QtCore import QTimer

    import linecat.catalog_window as cw
    from linecat import main as cli

    monkeypatch.setattr(cw, "latex_available", lambda: False)
    monkeypatch.setattr(cli.sys, "argv", ["linecat"])
    monkeypatch.setattr(cli, "SPLASH_SECONDS", 30)
    timers = []
    monkeypatch.setattr(QTimer, "singleShot", lambda ms, fn: timers.append((ms, fn)))
    seen = {}

    def run(self):
        windows = [w for w in self.topLevelWidgets() if isinstance(w, cw.CatalogWindow) and not w.isVisible()]
        splash_timers = [fn for ms, fn in timers if getattr(fn, "__name__", "") == "show_window" and ms > 20_000]
        seen["delay"] = len(splash_timers) == 1
        splash_timers[0]()
        seen["shown"] = any(w.isVisible() for w in windows)
        for w in windows:
            w.close()
        return 0

    monkeypatch.setattr(type(qapp), "exec", run)
    assert cli.run_view(str(oh_csv)) == 0
    assert seen == {"delay": True, "shown": True}
