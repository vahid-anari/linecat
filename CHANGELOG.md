# Changelog

## 0.2.1 — 2026-10-16

- Convert CDMS Catalogs… runs in the background with a progress dialog (Cancel keeps the species already done) and ends with a report; `linecat convert` prints its progress; `tqdm` no longer needed. Converting accepts the `catalogs/` folder or one species folder.
- Loading a file that is not a linecat catalog keeps the catalog already open (it used to be cleared).
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
