"""linecat as an app: its name, and the description used by the launcher and the update check."""

from pathlib import Path

from sciwidgets.app import AppInfo

from linecat import __version__

APP_NAME = "Line Catalog Explorer"
"""Name shown to the user (window, splash, launcher)."""

APP_VERSION = __version__
"""Installed version (``0.0.0`` when linecat is not installed as a package)."""

DIST_NAME = "linecat"
"""Name of the package on PyPI."""

APP = AppInfo(
    name=APP_NAME,
    version=APP_VERSION,
    dist_name=DIST_NAME,
    module="linecat",
    command="linecat",
    github_repo="vahid-anari/linecat",
    icon=Path(__file__).resolve().parent / "data" / "icons" / "app_icon.png",
    bundle_id="io.github.vahid-anari.linecat",
    linux_id="linecat",
    marker="Linecat",  # keys recorded in installed launchers (LinecatPython, X-Linecat-*): keep
    comment="Filter spectral line catalogs and draw energy-level diagrams",
    categories="Science;Astronomy;Physics;",
)
"""linecat for ``sciwidgets.app`` (launcher, update check)."""
