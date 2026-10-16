# linecat

[![tests](https://github.com/vahid-anari/linecat/actions/workflows/tests.yml/badge.svg)](https://github.com/vahid-anari/linecat/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**linecat** ("line catalog") is a desktop viewer for spectral line catalogs
such as [CDMS](https://cdms.astro.uni-koeln.de/). It loads a catalog converted
to CSV, filters the transitions by frequency range and by the quantum numbers of
the upper and lower states, shows the result in a table, exports the selection,
and draws an interactive energy-level diagram of the selected transitions
(with secondary transitions, hover information and a LaTeX/TikZ export).

Supported species: OH, CH3OH, SiO, NH3. Adding a species means adding its
quantum-number rules to `linecat/molecules.py`.

<img src="https://raw.githubusercontent.com/vahid-anari/linecat/main/docs/images/main_window.png" width="700" alt="linecat main window: quantum-number filters, frequency range and the table of OH lines">

<img src="https://raw.githubusercontent.com/vahid-anari/linecat/main/docs/images/diagram.png" width="700" alt="Energy-level diagram of the selected OH transitions with the transition table">

## Install (development)

```
git clone https://github.com/vahid-anari/linecat.git
cd linecat
pip install -e ".[dev]"
linecat
```

## Use

```
linecat                      open the viewer
linecat catalogs/CDMS_OH.csv open a catalog at start
linecat convert --catalogs catalogs           convert every species found
linecat convert OH CH3OH --catalogs catalogs  convert some species
linecat --version
```

File → Open Catalog… loads a CSV; the quantum-number filters and the
frequency range narrow the table; File → Export Table as CSV… writes what is
shown; Transitions → Show Energy-Level Diagram draws the selected lines
(hover for ν and τ, double-click a transition for the lines from its lower
level). Right-click a column header for colours, alignment, font and columns.

## Catalogs

The CDMS `.cat` sources are in `catalogs/`. Convert them to the CSV files the
viewer reads with `linecat convert --catalogs catalogs` (or File → Convert
CDMS Catalogs… in the app). The generated CSVs are not committed.

## Tests

```
pytest
```

The window tests run offscreen with the small catalog in `tests/data/`.
`python tools/screenshots.py` renders the two pictures above into
`docs/images/` (it needs `catalogs/CDMS_OH.csv`).

## License

MIT
