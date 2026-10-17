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


def test_molecule_resources_shipped():
    from linecat.builtin import general_docs, molecule_docs, molecule_image

    for code in REGISTRY:
        assert molecule_image(code) is not None and molecule_image(code).suffix == ".svg"
        assert molecule_docs(code), code
    assert [p.stem for p in molecule_docs("OH")] == ["OH, v=0", "OH, v=1", "OH, v=2"]
    assert len(general_docs()) >= 1


def test_molecule_box(window, builtin_folder, monkeypatch):
    import linecat.molecule_box as mb
    from linecat.molecule_box import cdms_tags

    assert cdms_tags(REGISTRY["OH"]) == ["017507", "017508", "017509"]
    assert cdms_tags(REGISTRY["CH3OH"]) == ["032504"]
    window.prepare_builtin_catalogs()
    width = window.molecule_box.width()
    window.on_menu_action("File", "builtin_OH", False)
    box = window.molecule_box
    assert box.info.species == "OH" and box.docs_button.isEnabled() and box.width() == width
    assert "017507, 017508, 017509" in box.details.text() and "2,581 lines" in box.details.text()
    opened = []
    monkeypatch.setattr(mb, "open_file", lambda path: opened.append(path))
    monkeypatch.setattr(mb.QDesktopServices, "openUrl", lambda url: opened.append(url))
    box.docs_menu.actions()[0].trigger()
    assert opened and "OH, v=0.pdf" in str(opened[0].toLocalFile() if hasattr(opened[0], "toLocalFile") else opened[0])
    assert window.menu.action("gdoc_0") is not None


def test_help_user_guide(window, monkeypatch):
    import linecat.catalog_window as cw
    from linecat.builtin import user_guide

    assert user_guide().name == "user_guide.pdf"
    assert window.menu.action("user_guide") is not None
    opened, warned = [], []
    monkeypatch.setattr(cw, "open_file", lambda path: opened.append(path))
    monkeypatch.setattr(cw, "show_warning", lambda *a, **k: warned.append(a))
    window.on_menu_action("Help", "user_guide", False)
    assert (opened == [user_guide()]) != bool(warned)  # opens the PDF, or explains how to build it
