"""The diagram as LaTeX commands: one ``\\Level`` per level and one ``\\Transition`` per arrow.

linecat ships no definitions for them; the pattern is described in the User Guide so that
anyone can write their own two macros and draw the diagram as they like::

    \\Level{name}{label}{energy in cm^-1}
    \\Transition{type}{number}{upper}{lower}{frequency in MHz}{lifetime in s}

Levels are named L1, L2, … from the lowest energy up; ``type`` is ``pri`` or ``sec`` and
``number`` the transition's number in the diagram and its table. Values are the catalog's.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

PATTERN = (
    "% \\Level{name}{label}{energy in cm^-1}\n"
    "% \\Transition{type}{number}{upper}{lower}{frequency in MHz}{lifetime in s}\n"
)


def tex_number(text) -> str:
    """A catalog number as written there, exponents in plain e-notation: ``1.014E+03`` -> ``1.014e3``."""
    text = str(text).strip()
    if "e" in text.lower():
        mantissa, exponent = text.lower().split("e")
        return f"{mantissa}e{int(exponent)}"
    return text


def latex_commands(levels: Iterable[str], transitions: Iterable[tuple[str, int, object]],
                   level_energy: Callable[[str], str]) -> str:
    """The commands for ``levels`` (labels, lowest energy first) and ``transitions``.

    ``transitions`` holds ``(type, number, row)`` with the row's ``upper lvl``, ``lower lvl``,
    ``nu exact`` and ``tau exact``; ``level_energy(label)`` gives a level's energy as text.
    """
    levels = list(levels)
    names = {label: f"L{i}" for i, label in enumerate(levels, start=1)}
    lines = [PATTERN]
    for label in levels:
        lines.append(f"\\Level{{{names[label]}}}{{{label}}}{{{tex_number(level_energy(label))}}}\n")
    ordered = sorted(transitions, key=lambda t: (t[0] != "pri", t[1]))
    for type_, number, row in ordered:
        lines.append(f"\\Transition{{{type_}}}{{{number}}}{{{names[row['upper lvl']]}}}"
                     f"{{{names[row['lower lvl']]}}}{{{tex_number(row['nu exact'])}}}"
                     f"{{{tex_number(row['tau exact'])}}}\n")
    return "".join(lines)
