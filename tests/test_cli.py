
import pandas as pd

from linecat.builtin import SOURCES_DIR
from linecat.main import build_parser, main

CATALOGS = SOURCES_DIR  # the CDMS files shipped with linecat


def test_parser_defaults():
    args = build_parser().parse_args(["view", "x.csv"])
    assert args.command == "view" and args.catalog == "x.csv"
    args = build_parser().parse_args(["convert", "OH", "--catalogs", "cats"])
    assert args.command == "convert" and args.species == ["OH"] and args.catalogs == "cats"


def test_convert_unknown_species(capsys):
    assert main(["convert", "XYZ"]) == 2
    assert "Unknown species" in capsys.readouterr().err


def test_convert_nothing_found(tmp_path, capsys):
    assert main(["convert", "--catalogs", str(tmp_path)]) == 1


def test_convert_sio(tmp_path):
    assert main(["convert", "SiO", "--catalogs", str(CATALOGS), "--output-dir", str(tmp_path)]) == 0
    df = pd.read_csv(tmp_path / "CDMS_SiO.csv", dtype=str)
    assert df["Species"].iloc[0] == "SiO" and {"Frequency (MHz)", "U-S J", "L-S v", "tau (s)"} <= set(df.columns)
    assert len(df) > 1000


def test_species_folder_accepted(tmp_path):
    from linecat.cdms import find_cat_file, species_in_folder

    assert species_in_folder(CATALOGS) == ["OH", "CH3OH", "SiO", "NH3"]
    assert species_in_folder(CATALOGS / "SiO") == ["SiO"]
    assert find_cat_file(CATALOGS / "SiO", "SiO/c044505.cat") == CATALOGS / "SiO" / "c044505.cat"
    assert species_in_folder(tmp_path) == []
    assert main(["convert", "--catalogs", str(CATALOGS / "SiO"), "--output-dir", str(tmp_path)]) == 0
    assert (tmp_path / "CDMS_SiO.csv").is_file()

