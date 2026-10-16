"""linecat: viewer for spectral line catalogs."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("linecat")
except PackageNotFoundError:
    __version__ = "0.0.0"
