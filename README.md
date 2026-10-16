# linecat

**linecat** ("line catalog") is a desktop viewer for spectral line catalogs
such as [CDMS](https://cdms.astro.uni-koeln.de/). It loads a catalog converted
to CSV, filters the transitions by frequency range and by the quantum numbers of
the upper and lower states, shows the result in a table, exports the selection,
and draws an interactive energy-level diagram of the selected transitions
(with secondary transitions, hover information and a LaTeX/TikZ export).

Supported species: OH, CH3OH, SiO, NH3. Adding a species means adding its
quantum-number rules to `linecat/molecules.py`.

## Install (development)

```
git clone https://github.com/vahid-anari/linecat.git
cd linecat
pip install -e ".[dev]"
linecat
```

## Catalogs

The CDMS `.cat` sources are in `catalogs/`. Convert them to the CSV files the
viewer reads with

```
cd catalogs
python -m linecat.cdms
```

The generated CSVs are not committed.

## Tests

```
pytest
```

## License

MIT
