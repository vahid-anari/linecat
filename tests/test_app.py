"""linecat as an app: launcher and update check through sciwidgets.app."""

import plistlib
import sys

from sciwidgets.app import launcher, update

from linecat.app_info import APP
from linecat.main import main


def test_app_info():
    assert APP.name == "Line Catalog Explorer" and APP.dist_name == "linecat" and APP.module == "linecat"
    assert APP.icon.is_file() and APP.marker == "Linecat"


def test_python_dash_m_linecat():
    import subprocess

    result = subprocess.run([sys.executable, "-m", "linecat", "--version"], capture_output=True, text=True,
                            check=False)
    assert result.returncode == 0 and result.stdout.startswith("linecat ")


def test_install_app_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(launcher, "current_system", lambda: "linux")
    monkeypatch.setattr(launcher.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    assert main(["install-app"]) == 0
    entry = tmp_path / ".local/share/applications/linecat.desktop"
    assert "Line Catalog Explorer is now in the applications menu" in capsys.readouterr().out
    assert "Exec=" in entry.read_text() and "-m linecat %f" in entry.read_text()
    assert main(["install-app", "--remove"]) == 0 and not entry.exists()


def test_launchers_made_by_linecat_0_8_are_still_recognised(tmp_path):
    """linecat 0.8–0.11 wrote LinecatPython into Info.plist; sciwidgets.app reads the same key."""
    app = tmp_path / "Applications" / "Line Catalog Explorer.app"
    (app / "Contents").mkdir(parents=True)
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(
        {"CFBundleShortVersionString": "0.11.0", "LinecatPython": "/env/bin/python"}))
    assert launcher.launcher_info(APP, "mac", tmp_path) == {"version": "0.11.0", "python": "/env/bin/python"}


def test_update_command_line(monkeypatch, capsys):
    monkeypatch.setattr(update, "fetch_latest_version", lambda info: info.version)
    assert main(["update", "--check"]) == 0
    assert "Line Catalog Explorer" in capsys.readouterr().out


def test_help_menu_check(window, monkeypatch):
    from sciwidgets.app import update_ui

    messages = []
    monkeypatch.setattr(update_ui, "show_information", lambda title, text, **k: messages.append(text))
    monkeypatch.setattr(update_ui.UpdateChecker, "check", lambda self: self.upToDate.emit())
    window.on_menu_action(None, "check_updates", False)
    assert messages and "is the latest version" in messages[0]
    messages.clear()
    window.check_for_updates(manual=False)                              # quiet at start-up
    assert messages == []
