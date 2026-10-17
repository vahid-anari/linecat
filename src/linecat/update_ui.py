"""The update check in the app: background check, update notice, "Update Now" and restart.

Ported from Maxwell Bloch Studio. The check reads the latest version from PyPI
and, when it is newer, the release notes from GitHub; both requests go through
``QNetworkAccessManager``, so they run without blocking the window.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from html import escape

from PySide6.QtCore import QObject, QProcess, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontDatabase
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from linecat.app_info import APP_NAME, APP_VERSION, PYPI_JSON_URL, RELEASES_API_URL
from linecat.update import newer_release_notes, parse_version, version_known

REQUEST_TIMEOUT_MS = 5000


class UpdateChecker(QObject):
    """Query PyPI asynchronously and report whether a newer version exists."""

    updateAvailable = Signal(str, object)
    """``(latest_version, notes)``; ``notes`` are ``(version, markdown)`` pairs, newest first (may be empty)."""

    upToDate = Signal()
    checkFailed = Signal(str)

    def __init__(self, parent: QObject | None = None, current: str = APP_VERSION) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._current = current

    def check(self) -> None:
        """Start a check; the result arrives through the signals."""
        if not version_known(self._current):
            self.checkFailed.emit("The running version is unknown (linecat is not installed as a package).")
            return
        reply = self._manager.get(self._request(PYPI_JSON_URL))
        reply.finished.connect(lambda: self._on_version(reply))

    @staticmethod
    def _request(url: str) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", f"{APP_NAME}/{APP_VERSION}".encode())
        request.setTransferTimeout(REQUEST_TIMEOUT_MS)
        return request

    def _on_version(self, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.checkFailed.emit(reply.errorString())
                return
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
            self.handle_latest(str(data["info"]["version"]))
        except (ValueError, KeyError, TypeError) as exc:
            self.checkFailed.emit(str(exc))
        finally:
            reply.deleteLater()

    def handle_latest(self, latest: str) -> None:
        """Compare ``latest`` with the running version; fetch the notes if it is newer."""
        if parse_version(latest) <= parse_version(self._current):
            self.upToDate.emit()
            return
        request = self._request(RELEASES_API_URL)
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        reply = self._manager.get(request)
        reply.finished.connect(lambda: self._on_notes(reply, latest))

    def _on_notes(self, reply: QNetworkReply, latest: str) -> None:
        notes: list[tuple[str, str]] = []
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = json.loads(bytes(reply.readAll()).decode("utf-8"))
                if isinstance(data, list):
                    notes = newer_release_notes(data, self._current, latest)
        except (ValueError, TypeError):
            notes = []
        finally:
            reply.deleteLater()
        self.updateAvailable.emit(latest, notes)


def notes_markdown(notes: Sequence[tuple[str, str]]) -> str:
    """The notes of several versions as one Markdown text, one ``###`` heading per version."""
    return "\n\n".join(f"### {version}\n\n{body.strip()}" for version, body in notes)


class UpdateDialog(QDialog):
    """Tell the user a newer version exists, what changed, and offer to update now.

    ``exec()`` returns ``UpdateDialog.UPDATE_NOW`` when "Update Now" was clicked.

    Args:
        latest: Latest version on PyPI.
        current: Running version.
        update_command: Command that updates this installation (shown), or ``""``.
        notes: ``(version, markdown)`` pairs, newest first; may be empty.
        project_url: PyPI page; releases_url: page with all release notes.
        can_update: Offer the "Update Now" button.
        hint: Shown instead of the command when the app cannot update itself.
    """

    UPDATE_NOW = 2

    def __init__(self, latest: str, current: str, update_command: str, notes: Sequence[tuple[str, str]],
                 project_url: str, releases_url: str, parent: QWidget | None = None, *,
                 can_update: bool = False, hint: str = "", dist_name: str = "linecat") -> None:
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.resize(620, 520)

        heading = QLabel(f"<b>{escape(APP_NAME)} {escape(latest)}</b> is available.<br>"
                         f"You have version {escape(current)}.")
        if hint:
            how_text = escape(hint)
        elif can_update:
            how_text = ("<b>Update Now</b> runs, while the app stays open:"
                        f"<pre>    {escape(update_command)}</pre>"
                        "Restart the app afterwards to use the new version.")
        else:
            command = update_command or f"pipx upgrade {dist_name}"
            how_text = ("To update, close the app and run in a terminal:"
                        f"<pre>    {escape(command)}</pre>"
                        f"(or <code>pip install -U {escape(dist_name)}</code> in the environment "
                        "where you installed it).")
        how = QLabel(how_text)
        how.setWordWrap(True)
        how.setTextInteractionFlags(Qt.TextSelectableByMouse)

        whats_new = QLabel("<b>What's new</b>")
        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(notes_markdown(notes))

        notes_btn = QPushButton("Open Release Notes")
        notes_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(releases_url)))
        pypi_btn = QPushButton("Open PyPI Page")
        pypi_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(project_url)))
        later_btn = QPushButton("Later")
        later_btn.clicked.connect(self.accept)
        self.update_btn = QPushButton("Update Now")
        self.update_btn.setEnabled(can_update)
        self.update_btn.clicked.connect(lambda: self.done(self.UPDATE_NOW))
        (self.update_btn if can_update else later_btn).setDefault(True)

        buttons = QHBoxLayout()
        buttons.addWidget(notes_btn)
        buttons.addWidget(pypi_btn)
        buttons.addStretch(1)
        buttons.addWidget(later_btn)
        buttons.addWidget(self.update_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(how)
        if notes:
            layout.addWidget(whats_new)
            layout.addWidget(browser, 1)
        else:
            whats_new.hide()
            browser.hide()
            layout.addStretch(1)
            self.resize(560, 260)
        layout.addLayout(buttons)


class UpdateProgressDialog(QDialog):
    """Run the update command, show its output, then offer a restart.

    ``succeeded`` and ``restart_requested`` tell the outcome. After a failure the
    dialog shows ``manual_hint`` (what to do by hand).
    """

    def __init__(self, command: Sequence[str], latest: str, manual_hint: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Updating")
        self.resize(640, 380)
        self._command = list(command)
        self._latest = latest
        self._manual_hint = manual_hint
        self.succeeded = False
        self.restart_requested = False

        self._status = QLabel(f"Updating {APP_NAME} to {latest}…")
        self._status.setWordWrap(True)
        self._output = QPlainTextEdit(readOnly=True)
        self._output.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self._output.appendPlainText("$ " + " ".join(self._command))

        self._later = QPushButton("Later")
        self._later.clicked.connect(self.reject)
        self._restart = QPushButton("Restart Now")
        self._restart.clicked.connect(self._choose_restart)
        self._close = QPushButton("Close")
        self._close.clicked.connect(self.reject)
        for button in (self._later, self._restart, self._close):
            button.hide()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._close)
        buttons.addWidget(self._later)
        buttons.addWidget(self._restart)

        layout = QVBoxLayout(self)
        layout.addWidget(self._status)
        layout.addWidget(self._output, 1)
        layout.addLayout(buttons)

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_output)
        self._proc.finished.connect(self._finished)
        self._proc.errorOccurred.connect(self._error)
        self._done = False

    def start(self) -> None:
        """Start the update (``exec`` calls it)."""
        self._proc.start(self._command[0], self._command[1:])

    def exec(self) -> int:
        self.start()
        return super().exec()

    def wait(self, msecs: int = 30000) -> bool:
        """Block until the command has finished (for tests)."""
        return self._proc.waitForFinished(msecs)

    def reject(self) -> None:
        if not self._done:  # no closing while pip is replacing files
            return
        super().reject()

    def _read_output(self) -> None:
        text = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        if text:
            self._output.appendPlainText(text.rstrip("\n"))

    def _finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._read_output()
        if exit_status == QProcess.NormalExit and exit_code == 0:
            self._succeed()
        else:
            self._fail(f"The update stopped with exit code {exit_code}.")

    def _error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            self._fail(f"Could not start {self._command[0]}.")

    def _succeed(self) -> None:
        self._done = True
        self.succeeded = True
        self._status.setText(f"<b>Updated to {self._latest}.</b> Restart now to use the new version?")
        self._later.show()
        self._restart.show()
        self._restart.setDefault(True)

    def _fail(self, reason: str) -> None:
        if self._done:
            return
        self._done = True
        self._status.setText(f"<b>The update did not finish.</b> {reason}<br>{self._manual_hint}")
        self._close.show()
        self._close.setDefault(True)

    def _choose_restart(self) -> None:
        self.restart_requested = True
        self.accept()


def restart_command() -> list[str]:
    """How to start the app again in the same Python (picks up the new version)."""
    return [sys.executable, "-m", "linecat"]


def restart_app(close_window: Callable[[], bool],
                start_detached: Callable[[str, list], object] = QProcess.startDetached) -> bool:
    """Close the main window and start the app again; ``False`` if the window did not close."""
    if not close_window():
        return False
    command = restart_command()
    start_detached(command[0], command[1:])
    return True
