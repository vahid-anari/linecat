"""Updating from PyPI: versions, release notes, `linecat update`, the update dialogs and the Help menu."""

import argparse
import subprocess
import sys

import pytest
from PySide6.QtWidgets import QApplication

from linecat import update
from linecat.app_info import APP_VERSION, DIST_NAME
from linecat.main import main
from linecat.update import MAX_NOTES, newer_release_notes, parse_version, run_update

# ----- versions and notes -----

@pytest.mark.parametrize("text, expected", [
    ("0.9.1", (0, 9, 1)), ("v0.9.1", (0, 9, 1)), ("V8.6", (8, 6)), (" 9.1.1 ", (9, 1, 1)), ("", ()),
])
def test_parse_version(text, expected):
    assert parse_version(text) == expected


def test_versions_compare_as_numbers():
    assert parse_version("0.10.0") > parse_version("0.9.9")
    assert not update.version_known("0.0.0") and update.version_known("0.9.0")


RELEASES = [{"tag_name": f"v0.9.{i}", "body": f"- {i}"} for i in (6, 5, 4, 3, 2)]


def test_picks_versions_after_current_up_to_latest():
    assert newer_release_notes(RELEASES, "0.9.2", "0.9.5") == [("0.9.5", "- 5"), ("0.9.4", "- 4"), ("0.9.3", "- 3")]
    assert newer_release_notes(RELEASES, "0.9.6", "0.9.6") == []
    assert [v for v, _ in newer_release_notes(RELEASES[::-1], "0.9.3", "0.9.6")] == ["0.9.6", "0.9.5", "0.9.4"]


def test_skips_drafts_prereleases_empty_notes_and_junk():
    releases = ["junk", None, {"body": "no tag"}, {"tag_name": "nightly", "body": "x"},
                {"tag_name": "v0.9.5", "body": "- five", "draft": True},
                {"tag_name": "v0.9.4", "body": "- four", "prerelease": True},
                {"tag_name": "v0.9.3", "body": "   "}, {"tag_name": "v0.9.2", "body": None},
                {"tag_name": "v0.9.1", "body": "\n- one\n\n"}]
    assert newer_release_notes(releases, "0.9.0", "0.9.5") == [("0.9.1", "- one")]


def test_limit():
    releases = [{"tag_name": f"v1.0.{i}", "body": f"- {i}"} for i in range(1, 30)]
    notes = newer_release_notes(releases, "1.0.0", "1.0.29")
    assert len(notes) == MAX_NOTES and notes[0][0] == "1.0.29"


# ----- linecat update -----

def do_update(check=False, yes=False, latest="99.0.0", notes=(), kind="pip", answer="n"):
    calls = []

    def run(command):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    code = run_update(argparse.Namespace(check=check, yes=yes), latest_version=lambda: latest,
                      release_notes=lambda current, newest: list(notes), kind=lambda: kind,
                      ask=lambda prompt: answer, run=run)
    return code, calls


def test_update_up_to_date(capsys):
    assert do_update(latest=APP_VERSION) == (0, [])
    assert "is the latest version" in capsys.readouterr().out


def test_update_check_shows_notes(capsys):
    assert do_update(check=True, notes=[("99.0.0", "- big news")]) == (0, [])
    out = capsys.readouterr().out
    assert "99.0.0 is available" in out and "- big news" in out


def test_update_asks_first(capsys):
    assert do_update(answer="n") == (0, [])
    assert "Nothing changed" in capsys.readouterr().out


def test_update_pip_and_pipx():
    assert do_update(answer="y", kind="pip") == (0, [[sys.executable, "-m", "pip", "install", "--upgrade", DIST_NAME]])
    code, calls = do_update(yes=True, kind="pipx")
    assert code == 0 and calls[0][1:] == ["upgrade", DIST_NAME]


def test_update_refuses_editable_and_unknown(capsys):
    assert do_update(yes=True, kind="editable") == (1, [])
    assert "git pull" in capsys.readouterr().err
    assert do_update(yes=True, kind="unknown") == (1, [])
    assert "pip install -U linecat" in capsys.readouterr().err


def test_update_offline(capsys):
    def offline():
        raise OSError("no network")

    assert run_update(argparse.Namespace(check=True, yes=False), latest_version=offline) == 1
    assert "Could not check" in capsys.readouterr().err


def test_update_command_line(monkeypatch, capsys):
    monkeypatch.setattr(update.run_update, "__kwdefaults__",
                        {**update.run_update.__kwdefaults__, "latest_version": lambda: APP_VERSION})
    assert main(["update", "--check"]) == 0
    assert "is the latest version" in capsys.readouterr().out


def test_install_kind_of_this_copy():
    assert update.install_kind() in ("editable", "pip", "pipx", "unknown")


# ----- in the app -----

def test_checker_compares_without_network(qapp):
    from linecat.update_ui import UpdateChecker

    seen = []
    checker = UpdateChecker(current="0.0.0")
    checker.checkFailed.connect(lambda msg: seen.append(("failed", msg)))
    checker.check()                                                     # unknown version: no request
    assert seen and seen[0][0] == "failed"
    checker = UpdateChecker(current="1.0.0")
    checker.upToDate.connect(lambda: seen.append("up to date"))
    checker.handle_latest("1.0.0")
    assert seen[-1] == "up to date"


def run_progress(code):
    from linecat.update_ui import UpdateProgressDialog

    dialog = UpdateProgressDialog([sys.executable, "-c", code], "99.0", "Run it by hand.")
    dialog.start()
    assert dialog.wait()
    QApplication.processEvents()
    return dialog


def test_successful_update_offers_restart(qapp):
    dialog = run_progress("print('Successfully upgraded')")
    assert dialog.succeeded and "Successfully upgraded" in dialog._output.toPlainText()
    assert "Updated to 99.0" in dialog._status.text() and dialog._restart.isVisibleTo(dialog)
    dialog._choose_restart()
    assert dialog.restart_requested
    dialog.deleteLater()


def test_failed_update_shows_the_manual_way(qapp):
    dialog = run_progress("import sys; print('No network'); sys.exit(1)")
    assert not dialog.succeeded and "No network" in dialog._output.toPlainText()
    assert "did not finish" in dialog._status.text() and "Run it by hand." in dialog._status.text()
    assert dialog._close.isVisibleTo(dialog) and not dialog._restart.isVisibleTo(dialog)
    dialog.deleteLater()


def test_restart_closes_then_starts_same_python():
    from linecat.update_ui import restart_app, restart_command

    started = []
    assert restart_app(lambda: True, lambda program, args: started.append([program, *args]))
    assert started == [restart_command()] == [[sys.executable, "-m", "linecat"]]
    started.clear()
    assert not restart_app(lambda: False, lambda program, args: started.append(program))
    assert started == []


@pytest.mark.parametrize("can_update, hint", [(True, ""), (False, "Use git pull."), (False, "")])
def test_update_dialog_button(qapp, can_update, hint):
    from linecat.update_ui import UpdateDialog

    dialog = UpdateDialog("99.0", "1.0", "pipx upgrade linecat", [("99.0", "- news")], "https://pypi.org",
                          "https://github.com", can_update=can_update, hint=hint)
    assert dialog.update_btn.isEnabled() is can_update
    if can_update:
        dialog.update_btn.click()
        assert dialog.result() == UpdateDialog.UPDATE_NOW
    dialog.deleteLater()


def test_help_menu_check(window, monkeypatch):
    import linecat.catalog_window as cw
    from linecat import update_ui

    messages = []
    monkeypatch.setattr(cw, "show_information", lambda title, text, **k: messages.append(text))
    monkeypatch.setattr(update_ui.UpdateChecker, "check", lambda self: self.upToDate.emit())
    window.on_menu_action(None, "check_updates", False)
    assert messages and "is the latest version" in messages[0]

    messages.clear()
    window.check_for_updates(manual=False)                              # quiet at start-up
    assert messages == []


def test_update_available_opens_the_dialog(window, monkeypatch):
    from linecat import update_ui

    shown = []
    monkeypatch.setattr(update_ui.UpdateDialog, "exec", lambda self: shown.append(self) or 0)
    window._on_update_available("99.0.0", [("99.0.0", "- news")])
    assert len(shown) == 1 and "99.0.0" in shown[0].findChildren(update_ui.QLabel)[0].text()
