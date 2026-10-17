"""Names and addresses of the app, used by the window, the launcher and the update check."""

from linecat import __version__

APP_NAME = "Line Catalog Explorer"
"""Name shown to the user (window, splash, launcher)."""

APP_VERSION = __version__
"""Installed version (``0.0.0`` when linecat is not installed as a package)."""

DIST_NAME = "linecat"
"""Name of the package on PyPI."""

GITHUB_REPO = "vahid-anari/linecat"
"""GitHub repository (``owner/name``); its Releases hold the release notes."""

PYPI_URL = f"https://pypi.org/project/{DIST_NAME}/"
PYPI_JSON_URL = f"https://pypi.org/pypi/{DIST_NAME}/json"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=30"
