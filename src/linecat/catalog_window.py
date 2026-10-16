"""The main window: catalog loading, filters, table, menus and status bar."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QSettings, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from sciwidgets.dialogs import AskResult, ask_question, show_about_dialog, show_warning
from sciwidgets.labels import set_latex_enabled
from sciwidgets.table import DataFrameView
from sciwidgets.window import MenuBarController, StatusBarController, center_on_screen

from linecat import __version__
from linecat.builtin import builtin_csv, builtin_dir, ensure_builtin_catalogs
from linecat.cdms import species_in_folder
from linecat.convert_dialog import convert_with_progress
from linecat.diagram import DiagramWindow
from linecat.filters import FrequencyRange, QuantumFilters
from linecat.headers import TABLE_FORMATS, pretty_header, table_alignment, table_background
from linecat.molecules import REGISTRY, MoleculeInfo
from linecat.widgets import APP_STYLE_SHEET, NATIVE_MENU_BAR, busy, latex_available

__all__ = ["APP_STYLE_SHEET", "CatalogWindow", "latex_available"]

MAX_PLOT_TRANSITIONS = 50  # above this the diagram asks before drawing


MAX_RECENT = 5



class CatalogWindow(QMainWindow):
    """
    Main window for loading, filtering, displaying, and exporting spectral data.

    Manages the PySide6 GUI components for:
      - Loading CSV catalogs
      - Applying frequency and quantum-state filters
      - Displaying results in a table
      - Exporting the filtered data to CSV

    Attributes
    ----------
    df : pd.DataFrame or None
        Complete dataset loaded from a CSV file.
    ranged_df : pd.DataFrame or None
        Subset of `df` filtered by the selected frequency range.
    filtered_df : pd.DataFrame or None
        Subset of `ranged_df` further filtered by quantum-state selections.
    filter_keys : list of str
        Quantum-number labels used to build filter controls.
    filter_page : QuantumFilters
        Grid of combo boxes for the quantum-state filters (keys like 'U-S J').
    freq_range : FrequencyRange
        Widget for specifying and converting the frequency range.
    table_view : DataFrameView
        Table showing the filtered lines.
    menu, status : MenuBarController, StatusBarController
        Menu bar (File, View, Transitions, Help) and status bar (catalog path, line counts).
    """

    def __init__(self, catalog=None):
        """
        Initialize the main window: menu bar, status bar, filters, frequency range and table.

        Parameters
        ----------
        catalog : str or None
            CSV catalog to open at start.
        """
        super().__init__()
        self.setWindowTitle("linecat")

        self.settings = QSettings('linecat', 'linecat')
        self.latex_available = latex_available()
        self.use_latex = self.latex_available and self.settings.value('view/use_latex', True, type=bool)
        set_latex_enabled(self.use_latex)
        self.molecule_info: MoleculeInfo = REGISTRY['OH']
        self.catalog_path = None

        # Menu bar and status bar
        self.menu = MenuBarController(self, self.menu_spec(), native_menubar=NATIVE_MENU_BAR)
        self.menu.actionTriggered.connect(self.on_menu_action)
        self.status = StatusBarController(self, ready_text="No catalog loaded", path_label="Catalog",
                                          show_memory=False, show_time=False)

        # Filters for molecular quantum states
        self.filter_keys = self.molecule_info.filters
        self.filter_page = self.create_filter_page()

        # Table for displaying results
        self.table_view = DataFrameView()
        self.table_view.set_config(self.load_table_config())
        self.table_view.configChanged.connect(lambda cfg: self.settings.setValue('table/config', json.dumps(cfg)))

        # Frequency-range selector widget
        self.freq_range = FrequencyRange(self.update_range)

        # Layout construction
        main_layout = QVBoxLayout()
        self.top_layout = top_layout = QHBoxLayout()
        top_layout.addStretch(1)
        top_layout.addWidget(self.filter_page)
        top_layout.addSpacing(20)
        top_layout.addWidget(self.freq_range.groupbox)
        top_layout.addStretch(1)
        main_layout.addLayout(top_layout, 0)
        main_layout.addSpacing(3)
        main_layout.addWidget(self.table_view, 1)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # DataFrame placeholders
        self.load = False
        self.df = None
        self.ranged_df = None
        self.filtered_df = None

        center_on_screen(self, (1400, 900), fallback=(1200, 700))
        if catalog:
            self.load_file(catalog)
        # build the built-in catalogs (first start, or after an update) once the window is up
        QTimer.singleShot(0, self.prepare_builtin_catalogs)

    # ----- menus -----
    def menu_spec(self):
        recent = [{"id": f"recent_{i}", "text": Path(p).name} for i, p in enumerate(self.recent_catalogs())]
        recent += [{"id": "sep"}, {"id": "clear_recent", "text": "Clear Menu", "enabled": bool(recent)}]
        builtin = [{"id": f"builtin_{code}", "text": code, "shortcut": f"Ctrl+{i}"}
                   for i, code in enumerate(REGISTRY, start=1)]
        builtin += [{"id": "sep"}, {"id": "builtin_folder", "text": "Show Built-in Catalogs Folder"}]
        return {
            "File": [
                {"submenu": "Open Built-in Catalog", "items": builtin},
                {"id": "open", "text": "Open Catalog…", "shortcut": QKeySequence.Open},
                {"submenu": "Open Recent", "items": recent},
                {"id": "sep"},
                {"id": "export", "text": "Export Table as CSV…", "shortcut": "Ctrl+E", "enabled": False},
                {"id": "convert", "text": "Convert CDMS Catalogs…"},
                {"id": "sep"},
                {"id": "quit", "text": "Quit", "shortcut": QKeySequence.Quit},
            ],
            "View": [
                {"id": "choose_columns", "text": "Choose Columns…", "enabled": False},
                {"id": "reset_filters", "text": "Reset Filters", "enabled": False},
                {"id": "sep"},
                {"id": "use_latex", "text": "Use LaTeX for Labels", "checkable": True, "checked": self.use_latex,
                 "enabled": self.latex_available},
            ],
            "Transitions": [
                {"id": "show_diagram", "text": "Show Energy-Level Diagram", "shortcut": "Ctrl+D", "enabled": False},
            ],
            "Help": [
                {"id": "about", "text": "About linecat"},
            ],
        }

    def on_menu_action(self, _menu_path, action_id, checked):
        if action_id == 'builtin_folder':
            self.show_builtin_folder()
        elif action_id.startswith('builtin_'):
            self.open_builtin(action_id.removeprefix('builtin_'))
        elif action_id == 'open':
            self.load_file()
        elif action_id.startswith('recent_'):
            recent = self.recent_catalogs()
            index = int(action_id.split('_')[1])
            if index < len(recent):
                self.load_file(recent[index])
        elif action_id == 'clear_recent':
            self.settings.setValue('recent', json.dumps([]))
            self.rebuild_menus()
        elif action_id == 'export':
            self.export_to_csv()
        elif action_id == 'convert':
            self.convert_catalogs()
        elif action_id == 'quit':
            self.close()
        elif action_id == 'choose_columns':
            self.open_select_columns_dialog()
        elif action_id == 'reset_filters':
            self.reset_filters()
        elif action_id == 'use_latex':
            self.set_use_latex(checked)
        elif action_id == 'show_diagram':
            self.show_button()
        elif action_id == 'about':
            self.show_about()

    def rebuild_menus(self):
        """Rebuild the menu bar (after a change of the recent list) and restore the dynamic states."""
        self.menu.set_menu_spec(self.menu_spec(), native_menubar=NATIVE_MENU_BAR)
        self.set_loaded_actions_enabled(self.df is not None)

    def set_loaded_actions_enabled(self, enabled):
        for action_id in ('export', 'choose_columns', 'reset_filters', 'show_diagram'):
            self.menu.set_enabled(action_id, enabled)

    def recent_catalogs(self):
        try:
            recent = json.loads(self.settings.value('recent', '[]', type=str))
        except ValueError:
            return []
        return [p for p in recent if isinstance(p, str)][:MAX_RECENT]

    def add_recent_catalog(self, path):
        recent = [p for p in self.recent_catalogs() if p != path]
        self.settings.setValue('recent', json.dumps([path] + recent[:MAX_RECENT - 1]))
        self.rebuild_menus()

    def set_use_latex(self, enabled):
        """Render the filter labels with LaTeX (when available) or with mathtext."""
        self.use_latex = bool(enabled) and self.latex_available
        self.settings.setValue('view/use_latex', self.use_latex)
        set_latex_enabled(self.use_latex)
        self.set_filter_keys()
        if self.ranged_df is not None:
            self.load = True
            self.update_filters()

    def reset_filters(self):
        """All quantum-number filters back to 'All' and the full frequency range."""
        if self.df is None:
            return
        self.load = True
        self.freq_range.reset()
        self.update_range([0, 'max'])

    # ----- built-in catalogs -----
    def prepare_builtin_catalogs(self):
        """Build the built-in CSVs if any is missing or was made by another linecat version."""
        try:
            with busy(self, "Preparing the built-in catalogs…"):
                built = ensure_builtin_catalogs()
        except Exception as exc:  # noqa: BLE001 - shown to the user
            show_warning("Built-in catalogs", "The built-in catalogs could not be prepared.",
                         f"{type(exc).__name__}: {exc}", parent=self)
            return False
        if built:
            self.status.set_state(f"Built-in catalogs ready ({', '.join(r.species for r in built)})")
        elif self.df is None:
            self.status.set_state("No catalog loaded")
        return True

    def open_builtin(self, code):
        """Open the built-in catalog of a species (rebuilt first if it went missing)."""
        if self.prepare_builtin_catalogs():
            self.load_file(str(builtin_csv(code)))

    def show_builtin_folder(self):
        folder = builtin_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def show_about(self):
        show_about_dialog(
            "About linecat",
            f"<p><b>linecat</b> {__version__}<br>Viewer for CDMS/JPL spectral line catalogs.</p>"
            "<p>Vahid Anari — MIT License<br>"
            '<a href="https://github.com/vahid-anari/linecat">github.com/vahid-anari/linecat</a></p>'
            '<p>Catalog data: <a href="https://cdms.astro.uni-koeln.de/">CDMS</a>, Universität zu Köln — '
            "please cite Müller et al. 2001, A&amp;A 370, L49; Müller et al. 2005, J. Mol. Struct. 742, 215; "
            "Endres et al. 2016, J. Mol. Spectrosc. 327, 95.</p>",
            parent=self,
        )

    def convert_catalogs(self):
        """Convert the CDMS .cat files of every registered species found in a folder to CSV."""
        start_dir = self.settings.value('paths/catalogs_dir', '', type=str)
        folder = QFileDialog.getExistingDirectory(self, "Folder with the CDMS .cat files", start_dir)
        if not folder:
            return
        self.settings.setValue('paths/catalogs_dir', folder)
        found = species_in_folder(folder)
        if not found:
            show_warning(
                "Nothing to convert",
                f"No registered species ({', '.join(REGISTRY)}) has all its .cat files in that folder.",
                "Choose a folder that holds species folders (OH/, CH3OH/, …) or one species folder (e.g. OH/).",
                parent=self,
            )
            return
        self.status.set_state(f"Converting {', '.join(found)}…")

        def done(results):
            self.status.set_state(f"Converted {', '.join(r.species for r in results)} → {Path(folder).name}/"
                                  if results else "Nothing converted")
            if len(results) == 1:
                self.load_file(str(results[0].path))

        self._convert_worker = convert_with_progress(self, found, folder, done)

    def load_table_config(self):
        """Table colors, visible columns and font saved by an earlier run (QSettings 'table/config')."""
        try:
            config = json.loads(self.settings.value('table/config', '{}', type=str))
        except ValueError:
            return {}
        return config if isinstance(config, dict) else {}

    @staticmethod
    def molecule_for(df):
        """The registered molecule of a catalog (from its `Species` column), or None."""
        if 'Species' not in df.columns or df.empty:
            return None
        return REGISTRY.get(df['Species'].iloc[0])

    def create_filter_page(self):
        """The quantum-number filters for the current molecule (combo paths like 'U-S J')."""
        page = QuantumFilters(self.filter_keys)
        page.changed.connect(self.update_filters)
        return page

    @property
    def filter_combos(self):
        """Mapping from filter identifiers (e.g. 'U-S J') to their combo box."""
        return dict(self.filter_page.combos)

    def set_filter_keys(self):
        """Rebuild the quantum-number filters for the current molecule."""
        self.filter_keys = self.molecule_info.filters
        old = self.filter_page
        self.filter_page = self.create_filter_page()
        self.top_layout.replaceWidget(old, self.filter_page)
        old.setParent(None)
        old.deleteLater()

    def update_range(self, range_vals):
        """
        Apply a new frequency range to the data and refresh filters.

        Parameters
        ----------
        range_vals : list of float or str, or None
            Two-element list [min_MHz, max_MHz], where `max_MHz` can be the
            string 'max' to indicate the full dataset range; None when the
            range filter is switched off (all frequencies).

        Returns
        -------
        None
        """
        if self.df is None:
            return
        if range_vals is None:
            self.ranged_df = self.df.astype({'Frequency (MHz)': float})
            self.update_filters()
            return
        min_val, max_val = range_vals
        if max_val == 'max':
            max_val = float(self.df['Frequency (MHz)'].astype(float).max())
            self.freq_range.set_range(min_val, max_val)
        df = self.df.astype({'Frequency (MHz)': float})
        self.ranged_df = df[(df['Frequency (MHz)'] >= float(min_val))
                            & (df['Frequency (MHz)'] <= float(max_val))]
        self.update_filters()

    def update_filters(self):
        """
        Apply user-selected quantum-state filters and refresh the table display.

        Reads the current selections from each filter combo box, filters the
        internally stored DataFrame (`self.ranged_df`) accordingly, and updates
        the QTableWidget. Also repopulates each combo box’s items to reflect
        valid options based on the current filtered subset.

        Returns
        -------
        None
        """
        if self.ranged_df is None:
            return

        # Determine current selections
        combos = self.filter_combos
        if self.load:
            current = {k: 'All' for k in combos}
            for combo in combos.values():
                combo.set_value('All')
            self.load = False
        else:
            current = {k: combo.get_value() for k, combo in combos.items()}

        # Apply filters
        self.filtered_df = self.ranged_df.copy()
        for key, val in current.items():
            if val != 'All':
                self.filtered_df = self.filtered_df[self.filtered_df[key] == val]
        self.display_table()

        # Update combo options (set_items is silent)
        for key, combo in combos.items():
            temp = self.ranged_df
            for col, val in current.items():
                if col != key and val != 'All':
                    temp = temp[temp[col] == val]
            vals = temp[key].unique()
            try:
                sorted_vals = sorted(vals, key=lambda x: float(Fraction(str(x))))
            except (ValueError, ZeroDivisionError):
                sorted_vals = sorted(vals, key=str)
            combo.set_items(['All'] + [str(v) for v in sorted_vals], current=current.get(key, 'All'))

    def load_file(self, path=None):
        """
        Load a CSV catalog into a DataFrame (asks for the file when ``path`` is None).

        Reads the file into `self.df`, picks the molecule from its `Species`
        column, rebuilds the filters, applies the full frequency range and
        enables the catalog-dependent menu items.

        Parameters
        ----------
        path : str or None
            CSV file; ``None`` opens a file dialog in the last-used folder.
        """
        if path is None:
            open_dir = self.settings.value('paths/open_dir', '', type=str)
            path, _ = QFileDialog.getOpenFileName(self, "Open Catalog", open_dir, "CSV Files (*.csv)")
            if not path:
                return
        with busy(self, f"Loading {Path(path).name}…"):
            self._load_file(path)

    def _load_file(self, path):
        try:
            df = pd.read_csv(path, dtype=str)
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            show_warning("Cannot open catalog", f"{Path(path).name}: {exc}", parent=self)
            return
        if df.empty:
            show_warning("Failed", f"{Path(path).name} is empty.", parent=self)
            return

        info = self.molecule_for(df)
        if info is None:
            show_warning("Failed", f"{Path(path).name}: unknown species or not a linecat catalog.", parent=self)
            return
        self.df = df
        self.molecule_info = info
        self.load = True
        self.catalog_path = path
        self.settings.setValue('paths/open_dir', str(Path(path).parent))
        self.add_recent_catalog(path)
        self.status.set_path(path)
        self.set_filter_keys()
        self.update_range([0, 'max'])
        self.set_loaded_actions_enabled(True)

    def open_select_columns_dialog(self):
        """Open the table's column chooser (also in the header's right-click menu)."""
        if self.df is not None:
            self.table_view.choose_columns()

    def display_table(self):
        if self.filtered_df is None:
            return
        df = self.filtered_df
        self.table_view.set_frame(
            df,
            formats={col: fmt for col, fmt in TABLE_FORMATS.items() if col in df.columns},
            backgrounds=table_background,
            alignments=table_alignment,
            headers={col: pretty_header(col) for col in df.columns},
        )
        self.status.set_state(f"{len(df):,} of {len(self.df):,} lines")

    def export_to_csv(self):
        """
        Export the currently displayed data to a CSV file chosen by the user.

        Opens a save-file dialog for CSV selection and writes the table as
        shown (filtered rows, visible columns, current sort order).

        Returns
        -------
        None
        """
        if self.df is None:
            return
        export_dir = self.settings.value('paths/export_dir', '', type=str)
        path, _ = QFileDialog.getSaveFileName(self, "Export Table as CSV", export_dir, "CSV Files (*.csv)")
        if path:
            if not path.lower().endswith('.csv'):
                path += '.csv'
            self.settings.setValue('paths/export_dir', str(Path(path).parent))
            self.table_view.export_csv(path)
            self.status.set_state(f"Exported {len(self.table_view.visible_frame()):,} lines to {Path(path).name}")

    def open_diagram(self):
        with busy():
            self.plot_window = DiagramWindow(self, self.df.copy(), self.filtered_df.copy(), self.molecule_info,
                                             self.latex_available)

    def show_button(self):
        """
            Show the DiagramWindow if the number of filtered transitions is acceptable.

            Asks before drawing when there are more than MAX_PLOT_TRANSITIONS transitions,
            asking the user whether to continue.
            """
        if self.filtered_df is None or self.filtered_df.empty:
            show_warning("No Transition", "There are no transitions. Nothing to display.", parent=self)
        elif len(self.filtered_df) <= MAX_PLOT_TRANSITIONS:
            self.open_diagram()
        else:
            reply = ask_question(
                "Large Number of Transitions",
                f"You are trying to plot more than {MAX_PLOT_TRANSITIONS} transitions.",
                "This may slow down the rendering. Do you want to continue?",
                yes_btn_label="Continue",
                parent=self,
            )
            if reply == AskResult.YES:
                self.open_diagram()
