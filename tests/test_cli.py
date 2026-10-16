from pathlib import Path

import pandas as pd

from linecat.main import build_parser, main

CATALOGS = Path(__file__).resolve().parent.parent / "catalogs"


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
