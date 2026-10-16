import pandas as pd

from linecat.molecules import REGISTRY


def test_registry_species():
    assert set(REGISTRY) == {"OH", "CH3OH", "SiO", "NH3"}


def test_oh_standardize_and_label():
    info = REGISTRY["OH"]
    row = pd.Series({"U-S N": 1, "U-S Parity": 1, "U-S J+0.5": 2, "U-S F": 2, "U-S v": 0})
    row = info.standardize(row, "U-S")
    assert row["U-S Omega"] == "3/2"
    assert row["U-S J"] == "3/2"
    assert row["U-S Parity"] == "-"
    label = info.label(pd.DataFrame([row]), "U-S").iloc[0]
    assert label == "$3/2,\\,3/2,\\,2^{-},\\,(0)$"


def test_ch3oh_standardize_sets_symmetry():
    info = REGISTRY["CH3OH"]
    row = pd.Series({"U-S v": 2, "U-S K_a": 3, "U-S A_P": 0})
    row = info.standardize(row, "U-S")
    assert row["U-S v_t"] == 0
    assert row["U-S Sym"] == "E"
    assert row["U-S K_a"] == -3
