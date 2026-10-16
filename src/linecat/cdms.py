"""
CDMS catalog → CSV converter for molecules registered in `MoleculesInfo.REGISTRY`.

This module:
- Parses fixed-width CDMS .cat files.
- Applies species-specific standardization/labeling via `MoleculeInfo`.
- Computes radiative quantities (A_ij, d_ij, S_ij), wavelengths, and level energies (K).
- Exports a tidy CSV sorted by frequency.

Supported species
-----------------
Whatever appears in `REGISTRY` (e.g., "OH", "CH3OH", ...). Add more by
defining <name>_standardize / <name>_label functions and registering a `MoleculeInfo`.

Notes
-----
- Wavenumber energies are in cm⁻¹; conversion to Kelvin uses cgs constants.
- Quantum-number columns `Q1..Qk` are renamed using each species’ `quantum_numbers`.
"""

from __future__ import annotations

__author__ = "Vahid Anari"
__license__ = "MIT"
__version__ = "0.1.0"

from itertools import chain
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd
from tqdm import tqdm

# First party
from linecat.molecules import MoleculeInfo, REGISTRY  # provides species metadata/behavior

# Enable progress_apply on DataFrames
tqdm.pandas()

# =============================================================================
# Physical constants (cgs)
# =============================================================================
h: float = 6.62607015e-27  # Planck constant [erg·s]
c: float = 2.99792458e10  # Speed of light [cm/s]
k_B: float = 1.3806488e-16  # Boltzmann constant [erg/K]

# Prefactors for radiative transition formulas
C_A_ij: float = (8 * np.pi / c ** 2) * 1e4
C_d_ij: float = np.sqrt(3 * h * c ** 3 / (64 * np.pi ** 4) * 1e18)


# =============================================================================
# Fixed-width layout (CDMS)
# =============================================================================
def get_columns_info(s: int = 0) -> dict[str, tuple[int, int]]:
    return {
        "Frequency (MHz)": (0, 13),
        "Error (MHz)": (13, 21),
        "Log Intensity (nm^2 MHz)": (21, 29),
        "Degrees of Freedom (DR)": (29, 31),
        "L-S E (cm^-1)": (31, 41),
        "g_up": (41, 44),
        "Species ID (TAG)": (44, 51),
        "QNFMT": (51, 55),
        "U-S Q1": (55, 57),
        "U-S Q2": (57, 59),
        "U-S Q3": (59, 61),
        "U-S Q4": (61, 63),
        "U-S Q5": (63, 65),
        "U-S Q6": (65, 67),
        "L-S Q1": (s + 67, s + 69),
        "L-S Q2": (s + 69, s + 71),
        "L-S Q3": (s + 71, s + 73),
        "L-S Q4": (s + 73, s + 75),
        "L-S Q5": (s + 75, s + 77),
        "L-S Q6": (s + 77, s + 79),
    }


NEW_ORDER: tuple[str, ...] = ("Frequency (MHz)",
                              "Error (MHz)",
                              "Wavelength (cm)",
                              "Log Intensity (nm^2 MHz)",
                              "Degrees of Freedom (DR)",
                              "Species",
                              "Species ID (TAG)",
                              "QNFMT",
                              "log_10 A_ij",
                              "A_ij (s^-1)",
                              "tau (s)",
                              "S_ij mu^2 (D^2)",
                              "d_ij (D)",
                              "g_up",
                              "U-S E (cm^-1)",
                              "U-S E (K)",
                              "U-S filters",
                              "L-S E (cm^-1)",
                              "L-S E (K)",
                              "L-S filters",)


# =============================================================================
# Helpers
# =============================================================================
def _convert_wavenumber_to_kelvin(E_cm: float) -> float:
    """Convert energy from wavenumbers [cm^-1] to Kelvin."""
    return E_cm * h * c / k_B


def _calculate_einstein_A_coefficient(
        I_log10: float, nu_MHz: float, g_up: int, E_up_K: float, E_lo_K: float, Q: float, T: float
) -> float:
    """
    Einstein A-coefficient [s^-1].

    Parameters
    ----------
    I_log10 : log10 of line intensity [nm^2 MHz]
    nu_MHz  : frequency [MHz]
    g_up    : degeneracy of upper level
    E_up_K  : upper-level energy [K]
    E_lo_K  : lower-level energy [K]
    Q       : partition function at temperature T
    T       : temperature [K]
    """
    # Population difference factor
    R = np.exp(-E_lo_K / T) - np.exp(-E_up_K / T)
    if np.isclose(R, 0.0):
        # Linear approximation when ΔE is tiny
        R = np.exp(-E_lo_K / T) * h * (nu_MHz * 1e6) / (k_B * T)
    return C_A_ij * (10.0 ** I_log10) * (nu_MHz ** 2) * Q / (g_up * R)


def _calculate_transition_dipole(A_ij: float, nu_MHz: float) -> float:
    """Transition dipole moment [Debye] from A_ij and frequency."""
    return C_d_ij * np.sqrt(A_ij / (nu_MHz ** 3))


def _calculate_line_strength(d_ij_D: float, g_up: int) -> float:
    """Line strength S_ij [Debye^2]."""
    return (d_ij_D ** 2) * g_up


def _process_transition_row(row: pd.Series, molecule_info: MoleculeInfo) -> pd.Series:
    """
    Enrich a catalog row with derived physics and standardized quantum labels.

    - Applies species-specific standardization (both U-S and L-S).
    - Converts level energies to K.
    - Computes A_ij, d_ij, S_ij.
    """
    # Standardize quantum fields (both states)
    row = molecule_info.standardize(row, "U-S")
    row = molecule_info.standardize(row, "L-S")

    # Energies (cm^-1 → K); upper level = lower + ν/c (in cm^-1)
    E_lo_cm = float(row["L-S E (cm^-1)"])
    nu_MHz = float(row["Frequency (MHz)"])
    E_up_cm = E_lo_cm + (nu_MHz * 1e6 / c)
    E_lo_K = _convert_wavenumber_to_kelvin(E_lo_cm)
    E_up_K = _convert_wavenumber_to_kelvin(E_up_cm)

    # Radiative quantities
    I_log = float(row["Log Intensity (nm^2 MHz)"])
    g = int(row["g_up"])
    A_ij = _calculate_einstein_A_coefficient(I_log, nu_MHz, g, E_up_K, E_lo_K, molecule_info.Q, molecule_info.T)
    d_ij = _calculate_transition_dipole(A_ij, nu_MHz)
    S_ij = _calculate_line_strength(d_ij, g)

    # Populate new columns
    row["Wavelength (cm)"] = f"{c / (nu_MHz * 1e6):.3E}"
    row["U-S E (cm^-1)"] = f"{E_up_cm:.5f}"
    row["U-S E (K)"] = f"{E_up_K:.5f}"
    row["L-S E (K)"] = f"{E_lo_K:.5f}"
    row["A_ij (s^-1)"] = f"{A_ij:.3E}"
    row["log_10 A_ij"] = f"{np.log10(A_ij):.5f}"
    row["tau (s)"] = f"{1.0 / A_ij:.3E}"
    row["d_ij (D)"] = f"{d_ij:.5f}"
    row["S_ij mu^2 (D^2)"] = f"{S_ij:.5f}"
    return row


def _load_cdms_catalog(path: str | Path, columns: Mapping[str, tuple[int, int]]) -> pd.DataFrame:
    """Load a fixed-width CDMS .cat file into a DataFrame (all columns as strings)."""
    return pd.read_fwf(
        path,
        colspecs=list(columns.values()),
        names=list(columns.keys()),
        dtype=str,
    )


def _add_filters(state: str, filters: Iterable[str]) -> tuple[str, ...]:
    """Build ('U-S F1', 'U-S F2', ...) or ('L-S F1', ...)."""
    prefix = f"{state}-S"
    return tuple(f"{prefix} {f}" for f in filters)


def _decode_q_token(tok) -> int | None:
    """
    Decode a CDMS 2-char quantum token to an integer per CDMS rules.
    Rules:
      - '00'..'99'  → 0..99
      - '-d'        → -1..-9
      - 'A0'..'Z9'  → 100..359  (A=10,...,Z=35 → 10*code + digit)
      - 'a0'..'z9'  → -10..-359 (a=1,...,z=35 → -(10*code + digit))
    """

    s = str(tok).strip()
    if tok is None or s == "" or s.lower() == "nan" or pd.isna(tok):
        print("Encountered NaN; replacing with 1000.")
        return 1000

    # digits 0..99
    if s.isdigit():
        return int(s)

    # '-d' for -1..-9
    elif s[0] == '-':
        return -int(s[1])

    # Uppercase letter + digit: 100..359
    elif 'A' <= s[0] <= 'Z':
        code = (ord(s[0]) - ord('A')) + 10
        return code * 10 + int(s[1])

    # Lowercase letter + digit: -10..-359
    elif 'a' <= s[0] <= 'z':
        code = (ord(s[0]) - ord('a')) + 1
        return -(code * 10 + int(s[1]))


def _apply_quantum_names(df: pd.DataFrame, quantum_numbers: Iterable[str], drop_extras: bool = True) -> pd.DataFrame:
    """Rename Q1..Qk → names from `quantum_numbers` for both 'U-S' and 'L-S' prefixes."""
    qn = tuple(quantum_numbers)
    prefixes = ("U-S", "L-S")
    rename_map: dict[str, str] = {}

    for prefix in prefixes:
        for i, name in enumerate(qn, start=1):
            old = f"{prefix} Q{i}"
            new = f"{prefix} {name}"
            if old in df.columns:
                rename_map[old] = new
                df[old] = df[old].map(_decode_q_token)

    df = df.rename(columns=rename_map)

    if drop_extras:
        extras: list[str] = []
        for prefix in prefixes:
            k = len(qn) + 1
            while (col := f"{prefix} Q{k}") in df.columns:
                extras.append(col)
                k += 1
        if extras:
            df = df.drop(columns=extras)

    return df


def convert_molecule_catalog(
    molecule_code: str, *, outdir: str | Path | None = None, catalogs_dir: str | Path | None = None
) -> Path:
    """
    Convert one species from CDMS .cat → CSV using species rules from `REGISTRY`.

    Parameters
    ----------
    molecule_code : str
        Key in REGISTRY (e.g., "OH", "CH3OH").
    outdir : str | Path | None
        Directory to write the CSV (defaults to current working directory).
    catalogs_dir : str | Path | None
        Folder that holds the species' `.cat` files (`input_files` are relative
        to it; defaults to the current working directory).

    Returns
    -------
    Path
        Path to the written CSV file.
    """
    info: MoleculeInfo = REGISTRY[molecule_code]
    outdir_path = Path(outdir) if outdir is not None else Path.cwd()
    catalogs_path = Path(catalogs_dir) if catalogs_dir is not None else Path.cwd()

    # Process each input file
    df_tot = pd.DataFrame()
    for file in info.input_files:
        df = _load_cdms_catalog(catalogs_path / file, get_columns_info(info.extra_spaces))
        df = _apply_quantum_names(df, info.quantum_numbers)
        df = df.progress_apply(lambda x: _process_transition_row(x, info), axis=1)
        df_tot = pd.concat([df_tot, df], ignore_index=True)

    # Compute expanded column order (replace placeholders)
    placeholders = {
        "U-S filters": _add_filters("U", info.filters),
        "L-S filters": _add_filters("L", info.filters),
    }
    new_order = tuple(chain.from_iterable(placeholders.get(x, (x,)) for x in NEW_ORDER))

    # Species label & reorder
    df_tot["Species"] = info.species

    missing = [c for c in new_order if c not in df_tot.columns]
    if missing:
        raise KeyError(f"Missing columns for reordering: {missing}")

    df_tot = df_tot[list(new_order)]
    df_tot["Frequency (MHz)"] = df_tot["Frequency (MHz)"].astype(float)
    df_sorted = df_tot.sort_values(by="Frequency (MHz)")

    # Write
    outdir_path.mkdir(parents=True, exist_ok=True)
    output_file = outdir_path / f"CDMS_{info.species}.csv"
    df_sorted.to_csv(output_file, index=False)
    print(f"Conversion for {info.species} complete! {len(df_sorted)} rows → {output_file}")
    return output_file


def convert_all(catalogs_dir: str | Path | None = None, outdir: str | Path | None = None) -> list[Path]:
    """Convert every registered species whose `.cat` files are present in `catalogs_dir`."""
    catalogs_path = Path(catalogs_dir) if catalogs_dir is not None else Path.cwd()
    written = []
    for code, info in REGISTRY.items():
        if all((catalogs_path / f).is_file() for f in info.input_files):
            written.append(convert_molecule_catalog(code, outdir=outdir, catalogs_dir=catalogs_dir))
    return written


if __name__ == "__main__":
    convert_all()
