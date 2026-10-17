# Changelog

## 0.12.0 — 2026-10-17

- The launcher (`linecat install-app`) and the update check (`linecat update`, Help ▸ Check for Updates…) now come from sciwidgets 0.11 (`sciwidgets.app`), shared with Maxwell Bloch Studio; `launcher.py`, `update.py` and `update_ui.py` are gone. Nothing changes for users; installed launchers keep working.

## 0.11.0 — 2026-10-17

- Diagram window: pinch on the trackpad zooms in and out around the point between the fingers (both directions together); ⌘ + mouse wheel does the same. Zooming this way switches Fit to Window off and the zoom sliders follow; a two-finger double tap switches Fit to Window on again. Limits as the sliders (10–300 % across, 10–600 % up).

## 0.10.3 — 2026-10-17

- File ▸ Export Table as CSV… writes all columns (hidden ones too), the filtered lines in the current sort order, so the file opens again as a catalog of its own; before, hiding Species or the quantum numbers left them out and the file could not be reopened properly.
- LaTeX Commands in a simple, documented pattern for any molecule: `\Level{name}{label}{energy}` and `\Transition{type}{number}{upper}{lower}{frequency in MHz}{lifetime in s}`, levels named L1, L2, … from the lowest energy, exact catalog values; no positions and no CDMS-specific level names (replaces `\DrawLevel`/`\DrawTr`, which needed one particular template). User Guide: the pattern and how to define the commands yourself.

## 0.10.2 — 2026-10-17

- User Guide: new screenshots — the main window (CH3OH filtered to the 6.7 GHz maser's upper level), the diagram window, hovering over an arrow and over a level, and the Molecule box with its documentation menu. README pictures updated with them.

## 0.10.1 — 2026-10-17

- Boltzmann constant: the exact 2019 SI value k_B = 1.380649 × 10⁻¹⁶ erg/K (was 1.3806488 × 10⁻¹⁶, the 2010 value, while h and c were already the 2019 ones). Only last digits change: energies in K by about 1.4 × 10⁻⁷, and the last digit of some S_ij μ², A_ij, τ and d_ij. The built-in catalogs rebuild themselves at the first start.
- User Guide, appendix: hc/k_B = 1.43877688 K per cm⁻¹ (it showed 1.43877709, the value of the old k_B).
- Tests: the windows' settings now go to a throwaway INI file on every system. On macOS the tests used the real linecat settings, so a large-diagram limit set in the app made a test wait for an answer (and a test reset that setting).

## 0.10.0 — 2026-10-17

- Diagrams are as large as their content needs: every level gets at least a line of text and transition circles never overlap; groups of transitions at different heights share a column, so a large selection grows downwards (NH3 with 70 lines: 12 in wide instead of 44). Fit to Window stops at that readable size and the diagram scrolls instead of squeezing the labels together. Less empty space above the top and below the bottom level.
- The hover label shows ν and τ on two lines with units and opens towards the middle of the diagram (never off the edge).
- Tab titles: the first tab names the selection ("NH₃ · 18.4–22.2 GHz · 70 lines"); a tab opened from an arrow reads "From (6, 1) 6−". The first tab is recognised by its place, not its title.
- View ▸ Large Diagram Warning…: ask before drawing more than N transitions (default 50, 10–1000) or never; the question says where to change it.
- LaTeX Commands: monospaced, Copy says "Copied", Save… writes a `.tex` file; a header comment names the selection. Fixed: frequencies below 1 MHz were written with "K" instead of "k"; one function formats frequencies and lifetimes for the hover label and the export.

## 0.9.0 — 2026-10-17

- linecat is on PyPI: `pipx install linecat` (or `pip install linecat`).
- Updates, as in Maxwell Bloch Studio: a quiet check a couple of seconds after start-up, Help → Check for Updates…, and `linecat update [--check] [--yes]`. A newer version is shown with its release notes; Update Now runs `pipx upgrade linecat` or `pip install -U linecat` (whichever matches the installation) and offers a restart. Copies installed with `pip install -e` are told to `git pull`.
- README and User Guide: installing from PyPI, Updating; PyPI metadata (keywords, classifiers, changelog link).

## 0.8.0 — 2026-10-17

- `linecat install-app` adds Line Catalog Explorer to Applications (macOS, with Launchpad, Spotlight and the Dock), the Start menu (Windows) or the applications menu (Linux), with the app icon; `--remove` removes it. Ported from Maxwell Bloch Studio: the launcher starts this installation's Python (`python -m linecat`, now available) and keeps the installing terminal's PATH so LaTeX is found; it is rebuilt by itself after an update.
- User Guide: Starting with a double-click; README and command-line table updated.

## 0.7.1 — 2026-10-17

- The splash stays at least 3.5 seconds (`SPLASH_SECONDS` in `main.py`), so it can be seen; a slower start-up adds nothing.

## 0.7.0 — 2026-10-17

- App identity: the app is called **Line Catalog Explorer** (the package and command stay `linecat`).
- App icon (three energy levels and a transition, on indigo) and a start-up splash (the CH3OH stick spectrum below 1 THz) with the name and version, as in Maxwell Bloch Studio. The slow imports now run behind the splash.
- `tools/make_icon.py` and `tools/make_splash.py` draw both pictures into `src/linecat/data/icons/`; the splash is computed from the shipped CDMS files.

## 0.6.0 — 2026-10-16

- User Guide (Help → User Guide): getting started, the main window, the energy-level diagram, converting CDMS catalogs, the command line, adding a species, and the equations behind the derived columns as an appendix.
- Guide sources in `docs/` (`user_guide.tex`, `equations.tex`, `style.sty` as in Maxwell Bloch Studio); `tools/build_docs.sh` builds the PDF into the package.

## 0.5.0 — 2026-10-16

- Molecule box left of the filters: a picture of the molecule, its name, CDMS tag(s), partition function Q(300 K) and number of lines, and a Documentation button that opens the CDMS documentation of its entries (included, no internet needed).
- Help → CDMS Documentation opens the general CDMS documents (included).
- One folder per species inside linecat (`data/molecules/<SPECIES>/`: `.cat` files, documentation PDFs, picture); general documents in `data/docs/`.
- README screenshots moved to `docs/figures/`; `tools/screenshots.py` removed (screenshots are taken by hand).

## 0.4.0 — 2026-10-16

- Built-in catalogs: the CDMS files of OH, CH3OH, SiO and NH3 ship with linecat. On first start and after each update they are converted (about a second) to read-only CSVs in the application-data folder (macOS: `~/Library/Application Support/linecat/catalogs/`); a missing file is rebuilt.
- File → Open Built-in Catalog → OH / CH3OH / SiO / NH3 (⌘1–⌘4), File → Show Built-in Catalogs Folder.
- `linecat convert` uses the shipped files unless `--catalogs` is given (output: the current folder, or `--output-dir`).
- The repository's `catalogs/` folder is gone (the sources moved to `src/linecat/data/cdms/`; the unused full CH3OH file `c032504.cat` was dropped).
- README and About name the CDMS references to cite.

## 0.3.0 — 2026-10-16

- Converting CDMS catalogs is about 150× faster: CH3OH (38,743 lines) takes under a second instead of about two minutes. The physics is computed on whole columns instead of row by row; the CSVs are byte-for-byte the same as before.
- The progress dialog of Convert CDMS Catalogs… only shows when a conversion takes more than half a second; the final report is unchanged.
- For adding a species: `<name>_standardize(df, prefix)` now receives the whole table and returns it (it used to get one row).
- Tests compare the converter's output with reference CSVs made by the previous converter (`tests/data/cdms/`).

## 0.2.2 — 2026-10-16

- Fixed a crash on Python 3.10 and 3.11: the wait cursor no longer runs the event loop in the middle of building a diagram, and sciwidgets 0.10.4 (now required) keeps PySide6 6.12.0 away from Python < 3.12, where it crashes on tables.
- Removed a pandas `SettingWithCopyWarning` when building the diagram levels.

## 0.2.1 — 2026-10-16

- Convert CDMS Catalogs… runs in the background with a progress dialog (Cancel keeps the species already done) and ends with a report; `linecat convert` prints its progress; `tqdm` no longer needed. Converting accepts the `catalogs/` folder or one species folder.
- Loading a file that is not a linecat catalog keeps the catalog already open (it used to be cleared).
- Quantum-number filters as one grid (a column per quantum number, rows Upper and Lower).
- The Frequency Range box has an on/off checkbox in its title; switched off it shows all frequencies and keeps the typed range.
- Wavelength column as a×10ⁿ like τ and A_ij.
- Diagram window: the transition table is a real table on the left, as wide as its content (sortable, rows coloured by type, linked both ways to the arrows — hovering an arrow selects its row, selecting rows highlights their arrows), the diagram on the right; the PDF keeps the drawn table as its second page. Slider names upright and the four sliders aligned.
- Fit to Window (checkbox in the Zoom box, View ▸ Fit to Window, ⌘0), on for every new tab: the diagram is zoomed to the space beside the table (50–300 %) and follows window resizes; each tab keeps its own setting and zoom.
- The diagram's side margins follow its labels, so long level labels and the "Energy (cm⁻¹)" title are never cut, at any zoom.
- Switching LaTeX on runs LaTeX for all labels in the background, in parallel, behind a progress dialog (the window no longer freezes; hovering an arrow afterwards is instant). Opening a catalog or a diagram shows a wait cursor and a status message.
- Opening a large catalog (and every filter change) is about 3× faster — sciwidgets 0.10.3.
- The diagram window stays in front after saving a PDF, the LaTeX Commands dialog and warnings.
- Selected rows in the transition table are always blue with white text, also when the diagram has focus.
- The diagram no longer opens at half size on Retina screens (cut-off "Energy" title) — fixed in sciwidgets 0.10.1; after picking a column colour or font the diagram window stays in front — sciwidgets 0.10.2; linecat now requires 0.10.3.
- Window tests (offscreen, small OH catalog in `tests/data/`), screenshots in the README, `tools/screenshots.py`.
- Code split into modules (`catalog_window`, `filters`, `headers`, `widgets`, `diagram/`); classes renamed `CatalogWindow`, `DiagramWindow`, `DiagramTab`. No change for users.

## 0.2.0 — 2026-10-16

- Menu bar (File, View, Transitions, Help) and status bar replace the buttons and labels: Open Catalog… (⌘O), Open Recent, Export Table as CSV… (⌘E), Convert CDMS Catalogs…, Choose Columns…, Reset Filters, Use LaTeX for Labels, Show Energy-Level Diagram (⌘D), About. The status bar shows the catalog path and "n of N lines".
- The diagram window has its own menu (Save Figure as PDF…, LaTeX Commands…, Secondary Transitions, Use LaTeX for Rendering) instead of the Export/View boxes.
- Table on `sciwidgets.table`: HTML headers (τ, cm⁻¹, subscripts), τ and A_ij as a×10ⁿ, sorting by header click, right-click menu for column colours, text colours, alignment, hidden columns and font — all remembered between runs.
- Filters built as a `sciwidgets.panel` page; fractions sorted numerically.
- `linecat [CATALOG.csv]` opens a catalog at start; `linecat convert [SPECIES …] [--catalogs DIR] [--output-dir DIR]` converts CDMS `.cat` files; `linecat --version`.
- File dialogs remember their last folder; the "Loaded"/"Exported"/"Saved" pop-ups are gone (status bar instead).
- Fixes: figures closed when a tab or the diagram window closes; LaTeX rendering switched on only while a figure is built; the catalog DataFrame is no longer modified by the diagram; LaTeX-unavailable pop-up at startup removed.

## 0.1.0 — 2026-10-16

- First packaged version of the spectral catalog viewer (`DisplayData.py`), unchanged behaviour.
