"""Column knowledge of the catalog table: pretty headers, formats, colours, alignment, filter labels."""

from __future__ import annotations

from sciwidgets.formatting import pretty_sci_text

TABLE_BACKGROUNDS = {'U-': 'tan', 'L-': 'lightskyblue'}


TABLE_FORMATS = {
    'Frequency (MHz)': lambda v: f"{float(v):,.3f}",
    'Error (MHz)': lambda v: f"{float(v):.4f}",
    'Wavelength (cm)': lambda v: pretty_sci_text(float(v), 4),
    'tau (s)': lambda v: pretty_sci_text(float(v), 4),
    'A_ij (s^-1)': lambda v: pretty_sci_text(float(v), 4),
    'U-S E (cm^-1)': lambda v: f"{float(v):,.5f}",
    'L-S E (cm^-1)': lambda v: f"{float(v):,.5f}",
    'U-S E (K)': lambda v: f"{float(v):,.5f}",
    'L-S E (K)': lambda v: f"{float(v):,.5f}",
}


TEXT_COLUMNS = ('Species', 'Sym', 'Parity')


def table_alignment(column):
    """Right-align everything but the text columns (species, symmetry, parity)."""
    return 'center' if column.split(' ')[-1] in TEXT_COLUMNS else 'right'


def table_background(column):
    """Background of a catalog column: tan for the upper state, blue for the lower state."""
    for prefix, color in TABLE_BACKGROUNDS.items():
        if column.startswith(prefix):
            return color
    return None



# Non-prefixed headers → pretty text
BASE_PRETTY_MAP: dict[str, str] = {
    "Frequency (MHz)": "Frequency<br>(MHz)",
    "Error (MHz)": "Error<br>(MHz)",
    "Wavelength (cm)": "Wavelength<br>(cm)",
    "Log Intensity (nm^2 MHz)": "Log Intensity<br>(nm<sup>2</sup> MHz)",
    "Degrees of Freedom (DR)": "DoF",
    "Species ID (TAG)": "Species<br>(TAG)",
    "log_10 A_ij": "log<sub>10</sub> A<sub>ij</sub>",
    "A_ij (s^-1)": "A<sub>ij</sub><br>(s<sup>-1</sup>)",
    "tau (s)": "&tau;<br>(s)",
    "S_ij mu^2 (D^2)": "S<sub>ij</sub>&mu;<sup>2</sup><br>(D<sup>2</sup>)",
    "d_ij (D)": "d<sub>ij</sub><br>(D)",
    "g_up": "g<sub>up</sub>",
    "Species": "Species",
}


# Tail renames for state-prefixed columns (applies to both U-S and L-S)
STATE_TAIL_RENAMES: dict[str, str] = {
    "E (cm^-1)": "Energy (cm<sup>-1</sup>)",
    "E (K)": "Energy (K)",
    "K_a": "K<sub>a</sub>",
    "K_c": "K<sub>c</sub>",
    "v_t": "v<sub>t</sub>",
    "Omega": "&Omega;",
    "J+0.5": "J+&frac12;",
}


STATE_PREFIXES: tuple[str, ...] = ("U-S", "L-S")


# Quantum-number labels in the filter boxes (math text for MathLabel)
FILTER_LABELS: dict[str, str] = {
    "Omega": r"\Omega",
    "K_a": "K_a",
    "K_c": "K_c",
    "v_t": "v_t",
    "Sym": r"\mathrm{Sym}",
    "Parity": r"\mathrm{Parity}",
}


def filter_label(key: str) -> str:
    """Math label of a quantum number in the filter boxes."""
    return FILTER_LABELS.get(key, key)


def pretty_header(h: str) -> str:
    # 1) Non-prefixed direct remap
    if h in BASE_PRETTY_MAP:
        return BASE_PRETTY_MAP[h]

    # 2) Generic state-prefixed mapping: "<prefix> <tail>" → "<prefix><br><pretty tail>"
    for pref in STATE_PREFIXES:
        pref_with_space = f"{pref} "
        if h.startswith(pref_with_space):
            tail = h[len(pref_with_space):]
            tail_pretty = STATE_TAIL_RENAMES.get(tail, tail)
            return f"{pref}<br>{tail_pretty}"

    # 3) Fallback: unchanged
    return h
