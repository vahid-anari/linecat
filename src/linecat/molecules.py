"""
Molecule registry and quantum-label utilities for spectral line catalogs.

This module defines:
- `MoleculeInfo`: a frozen, slotted dataclass bundling per-species metadata and behavior.
- `REGISTRY` (read-only): mapping from species code (e.g., "OH", "CH3OH") to `MoleculeInfo`.
- `Prefix`: state prefix literal, one of "U-S" or "L-S".

Public API (per species)
------------------------
Each `MoleculeInfo` exposes:
- `standardize_row(row, prefix) -> pd.Series`
    Normalize/augment a catalog row in place (e.g., compute Ω, parity symbol, v_t,
    adjust K_a signs, etc.).
- `quantum_label(df, prefix) -> pd.Series`
    Vectorized LaTeX label strings for the chosen state.

Metadata fields include: `quantum_numbers`, `filters`, `label_template`, `input_files`,
the partition function `Q` and temperature `T` .

Add a new species
-----------------
1) Implement `<name>_standardize(row, prefix)` and `<name>_label(df, prefix)`.
2) Construct a `MoleculeInfo(...)` with the species’ metadata and these functions.
3) Register it under its code in `REGISTRY`.

Notes
-----
- `REGISTRY` is a `MappingProxyType` view and cannot be mutated at runtime.
- `label_template` is LaTeX; labels assume math mode.
"""

from __future__ import annotations

__author__ = "Vahid Anari"
__license__ = "MIT"
__version__ = "0.1.0"

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Final, Literal, Tuple

import pandas as pd

Prefix = Literal["U-S", "L-S"]
StandardizeFunc = Callable[[pd.Series, Prefix], pd.Series]
LabelFunc = Callable[[pd.DataFrame, Prefix], pd.Series]


@dataclass(frozen=True, slots=True)
class MoleculeInfo:
    species: str
    latex_name:str
    input_files: Tuple[str, ...]
    Q: float
    T: float
    quantum_numbers: Tuple[str, ...]
    filters: Tuple[str, ...]
    label_template: str
    standardize: StandardizeFunc = field(repr=False, compare=False)
    label: LabelFunc = field(repr=False, compare=False)
    extra_spaces:int=0


# ---------- OH behavior ----------
def OH_standardize(row: pd.Series, prefix: Prefix) -> pd.Series:
    N = int(row[f'{prefix} N'])
    parity = int(row[f'{prefix} Parity'])
    J_plus_half = int(row[f'{prefix} J+0.5'])
    row[f'{prefix} Omega'] = '1/2' if N == J_plus_half else '3/2'
    row[f'{prefix} J'] = f'{2 * J_plus_half - 1}/2'
    row[f'{prefix} Parity'] = '-' if parity == 1 else '+'
    return row


def OH_label(df: pd.DataFrame, prefix: Prefix) -> pd.Series:
    J = df[f'{prefix} J'].astype(str)
    Omega = df[f'{prefix} Omega'].astype(str)
    F = df[f'{prefix} F'].astype(str)
    parity = df[f'{prefix} Parity'].astype(str)
    v = df[f'{prefix} v'].astype(str)
    return "$" + J + ",\\," + Omega + ",\\," + F + "^{" + parity + "},\\,(" + v + ")$"


# ---------- CH3OH behavior ----------
def CH3OH_standardize(row: pd.Series, prefix: Prefix) -> pd.Series:
    v = int(row[f'{prefix} v'])
    row[f'{prefix} v_t'] = v // 3
    r = v % 3
    if r == 0:
        parity = int(row[f'{prefix} A_P'])
        sym = 'A+' if parity > 0 else 'A-'
    else:
        sym = 'E'
        if r == 2:
            row[f'{prefix} K_a'] = -int(row[f'{prefix} K_a'])
    row[f'{prefix} Sym'] = sym
    return row


def CH3OH_label(df: pd.DataFrame, prefix: Prefix) -> pd.Series:
    J = df[f'{prefix} J'].astype(str)
    Ka = df[f'{prefix} K_a'].astype(str)
    Kc = df[f'{prefix} K_c'].astype(str)
    Sym = df[f'{prefix} Sym'].astype(str).str[-1]
    vt = df[f'{prefix} v_t'].astype(str)
    return "$" + J + "_{" + Ka + ", " + Kc + "}^{" + Sym + "}\\,(" + vt + ")$"


# ---------- SiO behavior ----------
def SiO_standardize(row: pd.Series, prefix: Prefix) -> pd.Series:
    return row


def SiO_label(df: pd.DataFrame, prefix: Prefix) -> pd.Series:
    J = df[f'{prefix} J'].astype(str)
    v = df[f'{prefix} v'].astype(str)
    return "$" + J + "\\,(" + v + ")$"

# ---------- NH3 behavior ----------
def NH3_standardize(row: pd.Series, prefix: Prefix) -> pd.Series:
    v = int(row[f'{prefix} v'])
    row[f'{prefix} Parity'] = '-' if v == 1 else '+'
    return row


def NH3_label(df: pd.DataFrame, prefix: Prefix) -> pd.Series:
    J = df[f'{prefix} J'].astype(str)
    K = df[f'{prefix} K'].astype(str)
    F = df[f'{prefix} F'].astype(str)
    parity = df[f'{prefix} Parity'].astype(str)
    return "$(" + J + ",\\," + K + ")\\," + F + "^{" + parity + "}$"


# =============================================================================
# Molecule registry (Species → MoleculeInfo)
# Add new species by defining its standardize/label functions and registering here.
# =============================================================================
REGISTRY: Final[Mapping[str, MoleculeInfo]] = MappingProxyType({
    "OH": MoleculeInfo(
        species="OH",
        latex_name=r"$\mathrm{OH}$",
        input_files=("OH/c017507.cat", "OH/c017508.cat", "OH/c017509.cat"),
        Q=81.4940,
        T=300.0,
        quantum_numbers=('N', 'Parity', 'v', 'J+0.5', 'F'),
        filters=("J", "Omega", "F", "Parity", "v"),
        label_template=r"$\mathbf{J,\,\Omega,\,F^p,\,(v)}$",
        standardize=OH_standardize,
        label=OH_label,
    ),
    "CH3OH": MoleculeInfo(
        species="CH3OH",
        latex_name=r"$\mathrm{CH_3OH}$",
        input_files=("CH3OH/c032504-5Q.cat",),
        Q=37027.3292,
        T=300.0,
        quantum_numbers=('J', 'K_a', 'K_c', 'v', 'A_P'),
        filters=("J", "K_a", "K_c", "Sym", "v_t"),
        label_template=r"$\mathbf{J_{K_a, K_c}^p\,(v_t)}$",
        standardize=CH3OH_standardize,
        label=CH3OH_label,
    ),
    "SiO": MoleculeInfo(
        species="SiO",
        latex_name=r"$\mathrm{SiO}$",
        input_files=("SiO/c044505.cat",),
        Q=289.2668,
        T=300.0,
        quantum_numbers=('J', 'v'),
        filters=("J", "v"),
        label_template=r"$\mathbf{J\,(v)}$",
        standardize=SiO_standardize,
        label=SiO_label,
    ),
    "NH3": MoleculeInfo(
        species="NH3",
        latex_name=r"$\mathrm{NH_3}$",
        input_files=("NH3/c017506.cat",),
        Q=1766.3450,
        T=300.0,
        quantum_numbers=('J', 'K', 'v', 'F'),
        filters=("J", "K", "F", "Parity"),
        label_template=r"$\mathbf{(J, \, K)\,(F^p)}$",
        standardize=NH3_standardize,
        label=NH3_label,
        extra_spaces=8

    ),
})
