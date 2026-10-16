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

from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Callable, Iterable, Mapping

import numpy as np
import pandas as pd

# First party
from linecat.molecules import MoleculeInfo, REGISTRY  # provides species metadata/behavior

ProgressFn = Callable[[int, int], None]
"""Called with (rows done, rows total) while a species is converted; raise to stop."""


class ConversionCancelled(Exception):
    """Raised from a progress callback to stop a conversion."""


@dataclass(frozen=True)
class ConversionResult:
    species: str
    path: Path
    rows: int

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
def _convert_wavenumber_to_kelvin(E_cm):
    """Convert energy from wavenumbers [cm^-1] to Kelvin (scalars or arrays)."""
    return E_cm * h * c / k_B


def _calculate_einstein_A_coefficient(I_log10, nu_MHz, g_up, E_up_K, E_lo_K, Q: float, T: float):
    """
    Einstein A-coefficient [s^-1], element-wise on arrays.

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
    # Population difference factor; linear approximation where ΔE is tiny
    R = np.exp(-E_lo_K / T) - np.exp(-E_up_K / T)
    R_linear = np.exp(-E_lo_K / T) * h * (nu_MHz * 1e6) / (k_B * T)
    R = np.where(np.isclose(R, 0.0), R_linear, R)
    return C_A_ij * (10.0 ** I_log10) * (nu_MHz ** 2) * Q / (g_up * R)


def _calculate_transition_dipole(A_ij, nu_MHz):
    """Transition dipole moment [Debye] from A_ij and frequency."""
    return C_d_ij * np.sqrt(A_ij / (nu_MHz ** 3))


def _calculate_line_strength(d_ij_D, g_up):
    """Line strength S_ij [Debye^2]."""
    return (d_ij_D ** 2) * g_up


def _formatted(values, spec: str) -> list[str]:
    return [format(v, spec) for v in values]


def _process_transitions(df: pd.DataFrame, molecule_info: MoleculeInfo) -> pd.DataFrame:
    """
    Add the derived physics and standardized quantum labels to a whole catalog table.

    - Applies species-specific standardization (both U-S and L-S).
    - Converts level energies to K.
    - Computes A_ij, d_ij, S_ij.
    Values are written as text with the same formats as the per-row converter of linecat ≤ 0.2.
    """
    df = df.copy()
    # Standardize quantum fields (both states)
    df = molecule_info.standardize(df, "U-S")
    df = molecule_info.standardize(df, "L-S")

    # Energies (cm^-1 → K); upper level = lower + ν/c (in cm^-1)
    E_lo_cm = df["L-S E (cm^-1)"].astype(float).to_numpy()
    nu_MHz = df["Frequency (MHz)"].astype(float).to_numpy()
    E_up_cm = E_lo_cm + (nu_MHz * 1e6 / c)
    E_lo_K = _convert_wavenumber_to_kelvin(E_lo_cm)
    E_up_K = _convert_wavenumber_to_kelvin(E_up_cm)

    # Radiative quantities
    I_log = df["Log Intensity (nm^2 MHz)"].astype(float).to_numpy()
    g = df["g_up"].astype(int).to_numpy()
    A_ij = _calculate_einstein_A_coefficient(I_log, nu_MHz, g, E_up_K, E_lo_K, molecule_info.Q, molecule_info.T)
    d_ij = _calculate_transition_dipole(A_ij, nu_MHz)
    S_ij = _calculate_line_strength(d_ij, g)

    # New columns, as text
    df["Wavelength (cm)"] = _formatted(c / (nu_MHz * 1e6), ".3E")
    df["U-S E (cm^-1)"] = _formatted(E_up_cm, ".5f")
    df["U-S E (K)"] = _formatted(E_up_K, ".5f")
    df["L-S E (K)"] = _formatted(E_lo_K, ".5f")
    df["A_ij (s^-1)"] = _formatted(A_ij, ".3E")
    df["log_10 A_ij"] = _formatted(np.log10(A_ij), ".5f")
    df["tau (s)"] = _formatted(1.0 / A_ij, ".3E")
    df["d_ij (D)"] = _formatted(d_ij, ".5f")
    df["S_ij mu^2 (D^2)"] = _formatted(S_ij, ".5f")
    return df


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
        # unknown quantum number token: keep the row with a marker value
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
                # decode each distinct token once
                codes = {tok: _decode_q_token(tok) for tok in df[old].unique()}
                df[old] = df[old].map(codes)

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


def find_cat_file(catalogs_dir: str | Path, file: str) -> Path | None:
    """Locate a species' `.cat` file: `<dir>/<SPECIES>/<name>` or, when a species folder was given, `<dir>/<name>`."""
    base = Path(catalogs_dir)
    for candidate in (base / file, base / Path(file).name):
        if candidate.is_file():
            return candidate
    return None


def species_in_folder(catalogs_dir: str | Path) -> list[str]:
    """Registered species whose `.cat` files are all present under `catalogs_dir` (see `find_cat_file`)."""
    return [code for code, info in REGISTRY.items()
            if all(find_cat_file(catalogs_dir, f) is not None for f in info.input_files)]


def convert_molecule_catalog(
    molecule_code: str,
    *,
    outdir: str | Path | None = None,
    catalogs_dir: str | Path | None = None,
    progress: ProgressFn | None = None,
) -> ConversionResult:
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
    progress : callable or None
        Called with (rows done, rows total) after reading and after each input
        file is processed; raising inside it (e.g. `ConversionCancelled`) stops
        the conversion before anything is written.

    Returns
    -------
    ConversionResult
        Species code, path of the written CSV and its number of lines.
    """
    info: MoleculeInfo = REGISTRY[molecule_code]
    outdir_path = Path(outdir) if outdir is not None else Path.cwd()
    catalogs_path = Path(catalogs_dir) if catalogs_dir is not None else Path.cwd()

    # Load every input file first, so the progress total is known
    frames = []
    for file in info.input_files:
        path = find_cat_file(catalogs_path, file)
        if path is None:
            raise FileNotFoundError(f"{info.species}: {file} not found under {catalogs_path}")
        df = _load_cdms_catalog(path, get_columns_info(info.extra_spaces))
        frames.append(_apply_quantum_names(df, info.quantum_numbers))
    total = sum(len(df) for df in frames)
    done = 0
    if progress is not None:
        progress(done, total)

    # Process each input file as a whole table, reporting progress
    parts = []
    for df in frames:
        parts.append(_process_transitions(df, info))
        done += len(df)
        if progress is not None:
            progress(done, total)
    df_tot = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

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
    return ConversionResult(info.species, output_file, len(df_sorted))


def convert_all(
    catalogs_dir: str | Path | None = None,
    outdir: str | Path | None = None,
    progress: Callable[[str, int, int], None] | None = None,
) -> list[ConversionResult]:
    """Convert every registered species whose `.cat` files are present in `catalogs_dir`.

    `progress` is called with (species, rows done, rows total).
    """
    catalogs_path = Path(catalogs_dir) if catalogs_dir is not None else Path.cwd()
    results = []
    for code in species_in_folder(catalogs_path):
        callback = (lambda done, total, code=code: progress(code, done, total)) if progress is not None else None
        results.append(convert_molecule_catalog(code, outdir=outdir, catalogs_dir=catalogs_path, progress=callback))
    return results


if __name__ == "__main__":
    convert_all()
