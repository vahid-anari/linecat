import pandas as pd

from linecat.molecules import REGISTRY


def test_registry_species():
    assert set(REGISTRY) == {"OH", "CH3OH", "SiO", "NH3"}


def test_oh_standardize_and_label():
    info = REGISTRY["OH"]
    df = pd.DataFrame({"U-S N": [1, 2], "U-S Parity": [1, 0], "U-S J+0.5": [2, 2], "U-S F": [2, 1], "U-S v": [0, 0]})
    df = info.standardize(df, "U-S")
    assert list(df["U-S Omega"]) == ["3/2", "1/2"]
    assert list(df["U-S J"]) == ["3/2", "3/2"]
    assert list(df["U-S Parity"]) == ["-", "+"]
    label = info.label(df, "U-S").iloc[0]
    assert label == "$3/2,\\,3/2,\\,2^{-},\\,(0)$"


def test_ch3oh_standardize_sets_symmetry():
    info = REGISTRY["CH3OH"]
    df = pd.DataFrame({"U-S v": [2, 1, 3, 3], "U-S K_a": [3, 3, 2, 2], "U-S A_P": [0, 0, 1, -1]})
    df = info.standardize(df, "U-S")
    assert list(df["U-S v_t"]) == [0, 0, 1, 1]
    assert list(df["U-S Sym"]) == ["E", "E", "A+", "A-"]
    assert list(df["U-S K_a"]) == [-3, 3, 2, 2]


def test_nh3_standardize_parity():
    df = REGISTRY["NH3"].standardize(pd.DataFrame({"U-S v": [0, 1]}), "U-S")
    assert list(df["U-S Parity"]) == ["+", "-"]
