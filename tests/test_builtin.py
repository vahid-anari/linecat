import os
import stat

from linecat import __version__
from linecat.builtin import SOURCES_DIR, STAMP_NAME, builtin_csv, builtin_is_current, ensure_builtin_catalogs
from linecat.cdms import convert_molecule_catalog
from linecat.main import main
from linecat.molecules import REGISTRY


def test_sources_shipped_in_package():
    for info in REGISTRY.values():
        for file in info.input_files:
            assert (SOURCES_DIR / file).is_file(), file


def test_build_once_read_only_and_identical(tmp_path):
    folder = tmp_path / "catalogs"
    built = ensure_builtin_catalogs(folder)
    assert sorted(r.species for r in built) == sorted(REGISTRY)
    assert (folder / STAMP_NAME).read_text().strip() == __version__ and builtin_is_current(folder)
    oh = builtin_csv("OH", folder)
    assert not os.stat(oh).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    reference = convert_molecule_catalog("OH", outdir=tmp_path / "ref", catalogs_dir=SOURCES_DIR)
    assert oh.read_bytes() == reference.path.read_bytes()
    assert ensure_builtin_catalogs(folder) == []  # up to date: nothing done


def test_rebuilt_when_missing_or_other_version(tmp_path):
    folder = tmp_path / "catalogs"
    ensure_builtin_catalogs(folder)
    os.chmod(builtin_csv("SiO", folder), stat.S_IWUSR | stat.S_IRUSR)
    builtin_csv("SiO", folder).unlink()
    assert not builtin_is_current(folder)
    assert len(ensure_builtin_catalogs(folder)) == len(REGISTRY)
    (folder / STAMP_NAME).write_text("0.0.1\n")
    assert len(ensure_builtin_catalogs(folder)) == len(REGISTRY) and builtin_is_current(folder)


def test_cli_convert_uses_shipped_sources(tmp_path):
    assert main(["convert", "SiO", "--output-dir", str(tmp_path)]) == 0
    assert (tmp_path / "CDMS_SiO.csv").is_file()


def test_window_opens_builtin_catalog(window, builtin_folder):
    window.prepare_builtin_catalogs()
    assert builtin_is_current(builtin_folder)
    window.on_menu_action("File", "builtin_NH3", False)
    assert window.molecule_info.species == "NH3" and window.catalog_path == str(builtin_folder / "CDMS_NH3.csv")
    assert window.menu.action("builtin_OH").shortcut().toString() == "Ctrl+1"
