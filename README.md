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

<img src="https://raw.githubusercontent.com/vahid-anari/linecat/main/docs/figures/main_window.png" width="700" alt="linecat main window: quantum-number filters, frequency range and the table of OH lines">

<img src="https://raw.githubusercontent.com/vahid-anari/linecat/main/docs/figures/diagram.png" width="700" alt="Energy-level diagram of the selected OH transitions with the transition table">

## Install (development)

```
git clone https://github.com/vahid-anari/linecat.git
cd linecat
pip install -e ".[dev]"
linecat
```

## Use

```
linecat                       open the viewer
linecat my_catalog.csv        open a catalog at start
linecat convert               convert the shipped CDMS files into the current folder
linecat convert OH --catalogs my_cats --output-dir out   convert your own .cat files
linecat --version
```

File → Open Built-in Catalog → OH / CH3OH / SiO / NH3 (⌘1–⌘4) opens a
catalog that ships with linecat; File → Open Catalog… loads any other CSV; the quantum-number filters and the
frequency range narrow the table; File → Export Table as CSV… writes what is
shown; Transitions → Show Energy-Level Diagram draws the selected lines
(hover for ν and τ, double-click a transition for the lines from its lower
level). Right-click a column header for colours, alignment, font and columns.

## Catalogs

linecat ships, for OH, CH3OH, SiO and NH3, the CDMS `.cat` files, the CDMS
documentation of each entry (PDF) and a picture of the molecule, one folder per
species (`src/linecat/data/molecules/<SPECIES>/`); the main window shows them in
its Molecule box, and Help → CDMS Documentation opens the general CDMS
documents. On first start, and after every linecat update, it
converts them to read-only CSV files in the application-data folder
(macOS: `~/Library/Application Support/linecat/catalogs/`; File → Show
Built-in Catalogs Folder). If a file goes missing it is rebuilt. Your own
`.cat` files (a newer CDMS release, say) can be converted with File → Convert
CDMS Catalogs… or `linecat convert --catalogs DIR`.

The catalog data come from the Cologne Database for Molecular Spectroscopy
([CDMS](https://cdms.astro.uni-koeln.de/)); please cite Müller et al. 2001,
A&A 370, L49; Müller et al. 2005, J. Mol. Struct. 742, 215; and Endres et al.
2016, J. Mol. Spectrosc. 327, 95. The catalog format and the SPCAT program are
described by Pickett et al. 1998, J. Quant. Spectrosc. Radiat. Transfer 60, 883.
The CDMS documentation pages included with linecat are reproduced with credit
to CDMS.

## User Guide

Help → User Guide opens the guide (PDF). Its sources are in `docs/`
(`user_guide.tex`, with the equations in `equations.tex`); after a change,
`sh tools/build_docs.sh` rebuilds it into `src/linecat/data/user_guide.pdf`
(needs a TeX installation, e.g. MacTeX).

## Tests

```
pytest
```

The window tests run offscreen with the small catalog in `tests/data/`.
The screenshots in `docs/figures/` are taken by hand on a Mac (⌘⇧4, Space,
⌥-click for a window without shadow).

## License

MIT
