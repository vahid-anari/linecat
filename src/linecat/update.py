"""Updating linecat from PyPI, without Qt: version check, release notes, ``linecat update``.

Ported from Maxwell Bloch Studio. The latest version comes from PyPI; the notes of
the newer versions come from the GitHub Releases (written from ``CHANGELOG.md`` at
each release) and are optional. The app's menu uses the same pieces through
``linecat.update_ui``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from importlib import metadata
from pathlib import Path

from linecat.app_info import APP_NAME, APP_VERSION, DIST_NAME, PYPI_JSON_URL, RELEASES_API_URL

TIMEOUT_S = 10
MAX_NOTES = 10
"""At most this many versions' notes are shown."""


def parse_version(text: str) -> tuple[int, ...]:
    """``"0.9.1"`` or ``"v0.9.1"`` -> ``(0, 9, 1)``; parsing stops at the first non-numeric part."""
    parts: list[int] = []
    for p in text.strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def version_known(version: str = APP_VERSION) -> bool:
    """False for a linecat that is not installed as a package (version ``0.0.0``)."""
    return any(parse_version(version))


def newer_release_notes(releases: list, current: str, latest: str, limit: int = MAX_NOTES) -> list[tuple[str, str]]:
    """``(version, notes)`` of the GitHub releases after ``current`` up to ``latest``, newest first.

    Drafts, pre-releases and releases without notes are left out.
    """
    cur, top = parse_version(current), parse_version(latest)
    picked: list[tuple[tuple[int, ...], str, str]] = []
    for rel in releases:
        if not isinstance(rel, dict) or rel.get("draft") or rel.get("prerelease"):
            continue
        tag = str(rel.get("tag_name") or "")
        ver = parse_version(tag)
        body = str(rel.get("body") or "").strip()
        if ver and cur < ver <= top and body:
            picked.append((ver, tag.lstrip("vV"), body))
    picked.sort(reverse=True)
    return [(v, b) for _, v, b in picked[:limit]]


def _get_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_latest_version() -> str:
    """Latest version on PyPI. Raises ``OSError``/``ValueError``/``KeyError`` when it cannot be read."""
    return str(_get_json(PYPI_JSON_URL)["info"]["version"])


def fetch_release_notes(current: str, latest: str) -> list[tuple[str, str]]:
    """Notes of the versions after ``current`` up to ``latest``; empty if GitHub can't be read."""
    try:
        data = _get_json(RELEASES_API_URL)
    except (OSError, ValueError):
        return []
    return newer_release_notes(data, current, latest) if isinstance(data, list) else []


def install_kind() -> str:
    """How this copy was installed: ``"editable"``, ``"pipx"``, ``"pip"`` or ``"unknown"``."""
    try:
        dist = metadata.distribution(DIST_NAME)
    except metadata.PackageNotFoundError:
        return "unknown"
    direct = dist.read_text("direct_url.json")
    if direct:
        try:
            if json.loads(direct).get("dir_info", {}).get("editable"):
                return "editable"
        except ValueError:
            pass
    parts = Path(sys.prefix).parts
    if "pipx" in parts and "venvs" in parts:
        return "pipx"
    return "pip"


def update_command(kind: str) -> list[str] | None:
    """The command that updates an installation of the given kind, or ``None``."""
    if kind == "pipx":
        return [shutil.which("pipx") or "pipx", "upgrade", DIST_NAME]
    if kind == "pip":
        return [sys.executable, "-m", "pip", "install", "--upgrade", DIST_NAME]
    return None


EDITABLE_HINT = "This copy runs from a source folder (pip install -e); update it there with git pull."


def run_update(
    args: argparse.Namespace,
    *,
    latest_version: Callable[[], str] = fetch_latest_version,
    release_notes: Callable[[str, str], list[tuple[str, str]]] = fetch_release_notes,
    kind: Callable[[], str] = install_kind,
    ask: Callable[[str], str] = input,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> int:
    """``linecat update [--check] [--yes]``."""
    try:
        latest = latest_version()
    except (OSError, ValueError, KeyError) as exc:
        print(f"Could not check for updates: {exc}", file=sys.stderr)
        return 1

    if parse_version(latest) <= parse_version(APP_VERSION):
        print(f"{APP_NAME} {APP_VERSION} is the latest version.")
        return 0

    print(f"{APP_NAME} {latest} is available. You have version {APP_VERSION}.")
    notes = release_notes(APP_VERSION, latest)
    if notes:
        print("\nWhat's new:")
        for version, body in notes:
            print(f"\n{version}")
            print("\n".join(f"  {line}" for line in body.splitlines()))
        print()
    if args.check:
        return 0

    how = kind()
    if how == "editable":
        print(EDITABLE_HINT, file=sys.stderr)
        return 1
    command = update_command(how)
    if command is None:
        print(f"Cannot tell how {DIST_NAME} was installed; update it with "
              f"pipx upgrade {DIST_NAME} or pip install -U {DIST_NAME}.", file=sys.stderr)
        return 1

    shown = " ".join(command)
    if not args.yes:
        answer = ask(f"Run: {shown}  [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Nothing changed.")
            return 0
    print(f"Running: {shown}")
    return run(command).returncode
