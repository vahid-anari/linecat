# Changelog

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
