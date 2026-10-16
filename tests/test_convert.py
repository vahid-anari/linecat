import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from linecat.cdms import ConversionCancelled, ConversionResult, convert_molecule_catalog  # noqa: E402

CATALOGS = Path(__file__).resolve().parent.parent / "catalogs"


def test_progress_callback_and_result(tmp_path):
    calls = []
    result = convert_molecule_catalog("SiO", outdir=tmp_path, catalogs_dir=CATALOGS,
                                      progress=lambda d, t: calls.append((d, t)))
    assert isinstance(result, ConversionResult) and result.species == "SiO" and result.path.is_file()
    assert calls[0][0] == 0 and calls[-1][0] == calls[-1][1] == result.rows
    assert [d for d, _ in calls] == sorted(d for d, _ in calls)
    assert len(calls) >= 3


def test_cancel_stops(tmp_path):
    def cancel_early(done, total):
        if done > 0:
            raise ConversionCancelled

    with pytest.raises(ConversionCancelled):
        convert_molecule_catalog("SiO", outdir=tmp_path, catalogs_dir=CATALOGS, progress=cancel_early)
    assert not (tmp_path / "CDMS_SiO.csv").exists()


def test_convert_with_progress_dialog(tmp_path, qapp):
    import shutil

    from PySide6.QtWidgets import QWidget

    import linecat.convert_dialog as cd

    (tmp_path / "SiO").mkdir()
    shutil.copy(CATALOGS / "SiO" / "c044505.cat", tmp_path / "SiO" / "c044505.cat")
    shown = []
    cd.show_information = lambda title, text, informative_text="", parent=None: shown.append(
        (title, text, informative_text))
    parent = QWidget()
    done = []
    worker = cd.convert_with_progress(parent, ["SiO"], str(tmp_path), done.append)
    assert worker.wait(120000)
    qapp.processEvents()
    assert len(done) == 1 and done[0][0].species == "SiO" and (tmp_path / "CDMS_SiO.csv").is_file()
    assert shown and shown[0][0] == "Conversion finished" and "SiO" in shown[0][2]
    assert cd.report_text([], True) == "<i>Cancelled.</i>" and cd.report_text([], False) == "Nothing converted."
