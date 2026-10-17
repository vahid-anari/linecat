"""The diagram window: tabs of energy-level diagrams with zoom, scale, PDF and LaTeX export."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.transforms import offset_copy
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QMainWindow, QTabWidget, QVBoxLayout, QWidget,
)

from sciwidgets.dialogs import show_information, show_warning
from sciwidgets.window import MenuBarController, center_on_screen

from linecat.diagram.elements import (
    BBOX_STYLES, H_STEPS, LevelLine, TransitionArrow, assign_lvls_y_positions, fit_side_margins, frequency_parts,
    level_y_limits, lifetime_parts, size_to_content, tex_fontsize_factor,
)
from linecat.diagram.latex_cache import prerender_latex
from linecat.diagram.tab import DiagramTab
from linecat.diagram.table import (
    TransitionSelection, add_row, finish_frame, new_table_frame, transition_table_figure,
)
from linecat.molecules import MoleculeInfo
from linecat.widgets import GROUPBOX_MARGIN, NATIVE_MENU_BAR, align_widgets, busy, make_slider


HOVER_FONT_SIZE = 16
GROUP_GAP_LEVELS = 1.0  # groups of transitions share a column only if this many levels apart in height
HOVER_OFFSET_PX = (24, 18)  # the hover label sits this far right of and above the pointer (flipped near edges)

SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def plain_level(level):
    """A level label without LaTeX, for tab titles: ``$(6,\\,1)\\,6^-$`` -> ``(6, 1) 6−``."""
    text = re.sub(r"\\[,;: ]|~", " ", level)
    text = re.sub(r"\\(mathrm|text|mathbf)\{([^}]*)\}", r"\2", text)
    text = re.sub(r"[\$\\{}]", "", text)
    text = text.replace("^", "").replace("_", "").replace("-", "−")
    text = re.sub(r"\s*,\s*", ", ", text)
    return re.sub(r"\s+", " ", text).strip()


def frequency_range_text(nu_mhz):
    """``"20.9–22.2 GHz"`` for a series of frequencies in MHz (one unit, chosen by the largest)."""
    lo, hi = float(nu_mhz.min()), float(nu_mhz.max())
    _, prefix = frequency_parts(hi)
    scale = {"k": 1e-3, "M": 1.0, "G": 1e3, "T": 1e6}[prefix]
    lo_text, _ = frequency_parts(lo) if frequency_parts(lo)[1] == prefix else (f"{lo / scale:.3g}", prefix)
    hi_text, _ = frequency_parts(hi)
    if lo_text == hi_text:
        return f"{hi_text} {prefix}Hz"
    return f"{lo_text}–{hi_text} {prefix}Hz"


class DiagramWindow(QMainWindow):
    def __init__(self, parent, df, filtered_df, molecule_info: MoleculeInfo, latex_available):
        super().__init__(parent)
        self.setWindowTitle(f"Energy Levels and Transitions Diagram of {molecule_info.species}")

        # Variables
        self.molecule_info = molecule_info
        self.latex_available = latex_available
        self.settings = parent.settings if parent is not None else QSettings('linecat', 'linecat')
        self.df = self.build_compatible_df(df)
        self.tabs_content = []
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.refresh_tab)
        # Layout setup
        self.build_layout()
        first = self.build_compatible_df(filtered_df)
        self.build_new_tab(first, self.primary_title(first))
        self.show()
        center_on_screen(self, (1500, 1000), fallback=(1400, 900))

    def primary_title(self, trs_df):
        """Title of the first tab: molecule, frequency range and number of lines."""
        if trs_df.empty:
            return "Primary Transitions"
        name = self.molecule_info.species.translate(SUBSCRIPT_DIGITS)
        lines = f"{len(trs_df)} line" + ("s" if len(trs_df) != 1 else "")
        return f"{name} · {frequency_range_text(trs_df['nu'])} · {lines}"

    def build_layout(self):
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        self.menu = MenuBarController(self, {
            "File": [
                {"id": "save_pdf", "text": "Save Figure as PDF…", "shortcut": QKeySequence.Save},
                {"id": "latex_commands", "text": "LaTeX Commands…"},
            ],
            "View": [
                {"id": "fit", "text": "Fit to Window", "checkable": True, "shortcut": "Ctrl+0"},
                {"id": "sep"},
                {"id": "secondary", "text": "Secondary Transitions", "checkable": True},
                {"id": "use_latex", "text": "Use LaTeX for Rendering", "checkable": True,
                 "enabled": self.latex_available},
            ],
        }, native_menubar=NATIVE_MENU_BAR)
        self.menu.actionTriggered.connect(self.on_menu_action)
        top_layout = QHBoxLayout()
        top_layout.addStretch()
        top_layout.addWidget(self.make_zoom_group_box())
        top_layout.addSpacing(10)
        top_layout.addWidget(self.make_real_scale_group_box())
        align_widgets([self.hori_zoom_slider, self.vert_zoom_slider, self.coarse_scale_slider,
                       self.fine_scale_slider])
        top_layout.addStretch()
        layout.addLayout(top_layout, 0)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central_widget)

    def make_zoom_group_box(self):
        # Sliders
        self.hori_zoom_slider = make_slider('Horizontal', 10, 300, 100)
        self.hori_zoom_slider.valueChanged.connect(lambda x: self.zoom(x, direction='h'))
        self.vert_zoom_slider = make_slider('Vertical', 10, 600, 100)
        self.vert_zoom_slider.valueChanged.connect(lambda x: self.zoom(x, direction='v'))
        self.fit_checkbox = QCheckBox("Fit to window")
        self.fit_checkbox.setToolTip("Zoom the diagram to the space beside the table, also when the window is resized")
        self.fit_checkbox.toggled.connect(self.set_fit)
        # Group Box
        group_box = QGroupBox("Zoom")
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(*GROUPBOX_MARGIN)
        group_layout.addWidget(self.hori_zoom_slider)
        group_layout.addWidget(self.vert_zoom_slider)
        group_layout.addWidget(self.fit_checkbox, alignment=Qt.AlignHCenter)
        group_box.setLayout(group_layout)
        return group_box

    def make_real_scale_group_box(self):
        # Sliders
        self.coarse_scale_slider = make_slider('Coarse', 0, 95, 0)
        self.coarse_scale_slider.valueChanged.connect(self.change_y_positions)
        self.fine_scale_slider = make_slider('Fine', 0.0, 5.0, 0.0, val_fmt='{:.2f}')
        self.fine_scale_slider.valueChanged.connect(self.change_y_positions)
        self.coarse_scale_slider.setToolTip("Main scaling factor for Y-axis spacing")
        self.fine_scale_slider.setToolTip("Fine adjustment for Y-axis spacing")
        # Group Box
        group_box = QGroupBox("Real Scale")
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(*GROUPBOX_MARGIN)
        group_layout.addWidget(self.coarse_scale_slider)
        group_layout.addWidget(self.fine_scale_slider)
        group_box.setLayout(group_layout)
        return group_box

    def export_pdf(self):
        save_dir = self.settings.value('paths/pdf_dir', '', type=str)
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF File", save_dir, "PDF Files (*.pdf)")
        self.reactivate()
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self.settings.setValue('paths/pdf_dir', str(Path(path).parent))

        # Grab the figure from the current tab and save
        idx = self.tabs.currentIndex()
        tab_content = self.tabs_content[idx]
        comps = tab_content.get_comps()
        with mpl.rc_context({"text.usetex": tab_content.use_latex_checkbox}):
            table_fig = transition_table_figure(comps['table df'])
        if tab_content.use_latex_checkbox:
            prerender_latex(self, [table_fig])
        try:
            with PdfPages(path) as pdf:
                pdf.savefig(comps['fig'])
                pdf.savefig(table_fig)
        finally:
            plt.close(table_fig)

    def change_y_positions(self, event):
        coarse_scale_factor = self.coarse_scale_slider.get_value() / 100.
        fine_scale_factor = self.fine_scale_slider.get_value() / 100.
        idx = self.tabs.currentIndex()
        tab_content = self.tabs_content[idx]
        tab_content.set_real_size(coarse_scale_factor, fine_scale_factor)
        comps = tab_content.get_comps()
        lvls_df = comps['lvls df']
        lvls = comps['lvls']
        arrows = comps['arrows']
        fig = comps['fig']
        ax = comps['ax']
        ys = assign_lvls_y_positions(lvls_df, coarse_scale_factor + fine_scale_factor)
        for i, y in enumerate(ys):
            lvl = lvls[i]
            lvl.set_y(y)
        ax.set_ylim(*level_y_limits(ys))
        for arrow in arrows:
            arrow.set_y(ys)
        fig.canvas.draw_idle()

    def on_menu_action(self, _menu_path, action_id, checked):
        if action_id == 'save_pdf':
            self.export_pdf()
        elif action_id == 'latex_commands':
            self.latex_format()
        elif action_id == 'fit':
            self.fit_checkbox.setChecked(checked)
        elif action_id in ('secondary', 'use_latex'):
            self.on_view_toggled(action_id, checked)

    def on_view_toggled(self, action_id, checked):
        idx = self.tabs.currentIndex()
        tab_content = self.tabs_content[idx]
        if action_id == 'secondary':
            tab_content.sec_trs_checkbox = checked
        else:
            tab_content.use_latex_checkbox = checked
        comps_exist = tab_content.get_comps_exist()
        comps_state = tab_content.comps_dict_name()

        if comps_exist == 1:
            tab_content.set_canvas()
            self.refresh_tab()

        elif comps_exist == 0:
            if comps_state == 'sec':
                self.build_sec_comps(tab_content, 'sec-latex')
            elif self.latex_available:
                if comps_state == 'pri-latex':
                    self.add_pri_comps_to_tab_content(tab_content)
                else:
                    self.build_sec_comps(tab_content, 'sec')
            else:
                tab_content.set_comps_exist(-1)
                self.use_latex_checkbox_failed(tab_content)

        elif comps_exist == -1:
            if action_id == 'secondary':
                self.sec_trs_checkbox_failed(tab_content)
            else:
                self.use_latex_checkbox_failed(tab_content)

    def sec_trs_checkbox_failed(self, tab_content):
        show_warning("No Secondary Transition", "No secondary transitions found.", parent=self)
        self.reactivate()
        self.menu.set_checked('secondary', False)
        tab_content.sec_trs_checkbox = False

    def use_latex_checkbox_failed(self, tab_content):
        show_warning("LaTeX not available", "LaTeX was not found on this computer.", parent=self)
        self.reactivate()
        self.menu.set_checked('use_latex', False)
        tab_content.use_latex_checkbox = False

    def latex_format(self):
        """File ▸ LaTeX Commands…: the diagram of the current tab as \\DrawLevel/\\DrawTr commands."""
        from linecat import __version__
        from linecat.dialogs import LatexCommandsDialog

        idx = self.tabs.currentIndex()
        title = self.tabs.tabText(idx)
        header = (f"% {title} -- made by linecat {__version__} (Line Catalog Explorer)\n"
                  "% Needs the \\DrawLevel and \\DrawTr definitions of your diagram template.\n\n")
        name = re.sub(r"[^\w.-]+", "_", f"{self.molecule_info.species}_diagram").strip("_") + ".tex"
        LatexCommandsDialog(header + self.tabs_content[idx].get_comps()['latex text'], self.settings,
                            default_name=name, parent=self).exec()
        self.reactivate()

    def reactivate(self):
        """Bring this window back to the front: on macOS a closed dialog hands focus to the main window."""
        self.raise_()
        self.activateWindow()

    def close_tab(self, idx):
        if idx == 0:
            show_information("Not Allowed", "The first tab shows the selected transitions and stays open.",
                             parent=self)
            self.reactivate()
            return
        tab = self.tabs.widget(idx)
        self.tabs.removeTab(idx)
        tab.deleteLater()
        for fig in self.tabs_content[idx].figures():
            plt.close(fig)
        del self.tabs_content[idx]

    def closeEvent(self, event):
        for tab_content in self.tabs_content:
            for fig in tab_content.figures():
                plt.close(fig)
        super().closeEvent(event)

    def center_scroll(self):
        self.tabs_content[self.tabs.currentIndex()].scroll.center()

    def refresh_tab(self):
        idx = self.tabs.currentIndex()
        tab_content = self.tabs_content[idx]
        sec_trs_checked = tab_content.sec_trs_checkbox
        use_latex_checkbox = tab_content.use_latex_checkbox
        comps = tab_content.get_comps()
        fig = comps['fig']
        zoom = comps['zoom factor']
        coarse_scale_factor = comps['coarse scale factor']
        fine_scale_factor = comps['fine scale factor']
        self.menu.set_checked('secondary', sec_trs_checked)
        self.menu.set_checked('use_latex', use_latex_checkbox)
        self.hori_zoom_slider.set_value(round(zoom[0] * 100))
        self.vert_zoom_slider.set_value(round(zoom[1] * 100))
        self.show_fit_state(tab_content.fit)
        tab_content.apply_fit()
        self.coarse_scale_slider.set_value(round(coarse_scale_factor * 100.))
        self.fine_scale_slider.set_value(fine_scale_factor * 100.)
        self.center_scroll()
        fig.canvas.draw_idle()

    def zoom(self, perc=100, direction='h', use_own_factor=False):
        idx = self.tabs.currentIndex()
        tab_content = self.tabs_content[idx]
        if not use_own_factor:
            tab_content.set_zoom(perc, direction)
        zoom = tab_content.get_comps()['zoom factor']
        tab_content.scroll.set_zoom(zoom[0], zoom[1])
        self.center_scroll()
        self.hori_zoom_slider.set_value(round(zoom[0] * 100))
        self.vert_zoom_slider.set_value(round(zoom[1] * 100))

    def set_fit(self, checked):
        """Fit to Window on or off for the current tab (checkbox or View menu)."""
        if not self.tabs_content:
            return
        tab_content = self.tabs_content[self.tabs.currentIndex()]
        tab_content.fit = checked
        self.show_fit_state(checked)
        tab_content.apply_fit()

    def show_fit_state(self, fit):
        """Checkbox and menu item show the tab's Fit state; the zoom sliders are off while it fits."""
        self.fit_checkbox.blockSignals(True)
        self.fit_checkbox.setChecked(fit)
        self.fit_checkbox.blockSignals(False)
        self.menu.set_checked('fit', fit)
        self.hori_zoom_slider.setEnabled(not fit)
        self.vert_zoom_slider.setEnabled(not fit)

    def on_tab_fitted(self, tab_content, h, v):
        """Show the zoom a fitting tab chose, if it is the tab on show."""
        if self.tabs_content and self.tabs_content[self.tabs.currentIndex()] is tab_content:
            self.hori_zoom_slider.set_value(round(h * 100))
            self.vert_zoom_slider.set_value(round(v * 100))
            self.center_scroll()

    def reset_sliders(self):
        self.hori_zoom_slider.set_value(100)
        self.vert_zoom_slider.set_value(100)
        self.coarse_scale_slider.set_value(0)
        self.fine_scale_slider.set_value(0.0)

    def build_compatible_df(self, df):
        def make_tr_text(temp_df):
            return temp_df['upper lvl'] + '->' + temp_df['lower lvl']

        df = df.copy()
        transform = self.molecule_info.label
        df['upper lvl'] = transform(df, 'U-S')
        df['lower lvl'] = transform(df, 'L-S')
        df['upper E'] = df['U-S E (cm^-1)'].map(lambda x: f'{float(x):.4f}')
        df['lower E'] = df['L-S E (cm^-1)'].map(lambda x: f'{float(x):.4f}')
        df.rename(columns={
            'Frequency (MHz)': 'nu',
            'tau (s)': 'tau',
        }, inplace=True)
        df = df[['upper lvl', 'lower lvl', 'upper E', 'lower E', 'nu', 'tau', 'd_ij (D)']].copy()
        df['transition'] = make_tr_text(df)
        for col in ['upper E', 'lower E', 'nu', 'tau']:
            df[col] = df[col].astype(float)
        df = df.sort_values('nu', ascending=False).reset_index(drop=True)
        return df

    def get_unique_levels(self, df, sec=False):
        def extract_unique(df, lvl_col, e_col):
            out = df.drop_duplicates(subset=lvl_col, keep='first').copy()
            out.rename(columns={lvl_col: 'level', e_col: 'E'}, inplace=True)
            return out[['level', 'E']]

        upper_lvls_df = extract_unique(df, 'upper lvl', 'upper E')
        lower_lvls_df = extract_unique(df, 'lower lvl', 'lower E')
        new_lower_lvls = lower_lvls_df[~lower_lvls_df['level'].isin(upper_lvls_df['level'])].copy()
        upper_lvls_df['up'] = 1 if sec else 2
        new_lower_lvls['up'] = 0 if sec else 1
        all_lvls_df = pd.concat([upper_lvls_df, new_lower_lvls], ignore_index=True)
        all_lvls_df = all_lvls_df.sort_values(by=['E', 'up'], ascending=True).reset_index(drop=True)
        return all_lvls_df

    def find_sec_trs(self, pri_trs_df):
        sec_trs_list = []
        tr_lower_lvls = []
        for _, tr in pri_trs_df.iterrows():
            tr_lower_lvl = tr['lower lvl']
            temp_df = self.df[self.df['upper lvl'] == tr_lower_lvl].copy()
            temp_df = temp_df[~temp_df['transition'].isin(pri_trs_df['transition'])]
            if temp_df.empty or tr_lower_lvl in tr_lower_lvls:
                pass
            else:
                tr_lower_lvls.append(tr_lower_lvl)
                sec_trs_list.append(temp_df)
        sec_trs_df = pd.concat(sec_trs_list, ignore_index=True) if sec_trs_list else pd.DataFrame()
        return sec_trs_df

    def build_pri_comps(self, trs_df):
        lvls_df = self.get_unique_levels(trs_df)
        fig, ax, latex_txt, lines, arrows, table_df, selection = self.build_trs_fig(lvls_df, trs_df)
        return DiagramTab(fig, ax, latex_txt, lines, arrows, lvls_df, trs_df, table_df, selection)

    def build_sec_comps(self, tab_content, use):
        exist_another = tab_content.comps_exist[use]
        if exist_another == -1:
            tab_content.set_comps_exist(-1)
            self.sec_trs_checkbox_failed(tab_content)
            return False

        pri_trs_df = tab_content.comps_dict['pri']['trs df']
        if exist_another == 1:
            sec_trs_df = tab_content.comps_dict[use]['trs df']
            all_lvls = tab_content.comps_dict[use]['lvls df']
        else:
            sec_trs_df = self.find_sec_trs(pri_trs_df)
            if sec_trs_df.empty:
                tab_content.set_comps_exist(-1)
                self.sec_trs_checkbox_failed(tab_content)
                return False
            else:
                pri_lvls_df = tab_content.comps_dict['pri']['lvls df']
                sec_lvls_df = self.get_unique_levels(sec_trs_df, True)
                all_lvls = pd.concat([pri_lvls_df, sec_lvls_df], ignore_index=True).drop_duplicates(subset='level')
                all_lvls = all_lvls.sort_values(['E', 'up'], ascending=True).reset_index(drop=True)
        use_latex = tab_content.use_latex_checkbox
        fig, ax, latex_txt, lines, arrows, table_df, selection = self.build_trs_fig(all_lvls, pri_trs_df, sec_trs_df,
                                                                                     use_latex)
        self.reset_sliders()
        tab_content.add_comps(fig, ax, latex_txt, lines, arrows, all_lvls, sec_trs_df, table_df, selection)
        tab_content.set_canvas()
        self.refresh_tab()
        return True

    def add_pri_comps_to_tab_content(self, tab_content):
        self.hori_zoom_slider.set_value(100)
        self.vert_zoom_slider.set_value(100)
        pri_trs_df = tab_content.comps_dict['pri']['trs df']
        pri_lvls_df = tab_content.comps_dict['pri']['lvls df']
        fig, ax, latex_txt, lines, arrows, table_df, selection = self.build_trs_fig(pri_lvls_df, pri_trs_df,
                                                                                     use_latex=True)
        self.reset_sliders()
        tab_content.add_comps(fig, ax, latex_txt, lines, arrows, pri_lvls_df, pri_trs_df, table_df, selection)
        tab_content.set_canvas()
        self.refresh_tab()

    def build_new_tab(self, trs_df, title):
        if trs_df.empty:
            show_warning("No Transition", "No transitions found. Nothing to display.", parent=self)
        else:
            self.reset_sliders()
            tab_content = self.build_pri_comps(trs_df)
            tab_content.on_fitted = self.on_tab_fitted  # the tab refits whenever its diagram area is resized
            self.tabs_content.append(tab_content)
            idx = self.tabs.addTab(tab_content.widget, title)
            self.tabs.setCurrentIndex(idx)

    def build_trs_fig(self, lvls_df, pri_trs_df, sec_trs_df=None, use_latex=False):
        """Build the diagram and table figures; LaTeX rendering is switched on only while building."""
        if sec_trs_df is None:
            sec_trs_df = pd.DataFrame()
        with busy():
            with mpl.rc_context({"text.usetex": use_latex}):
                result = self._build_trs_fig(lvls_df, pri_trs_df, sec_trs_df, use_latex)
                hover_size = HOVER_FONT_SIZE * tex_fontsize_factor()
            fig, arrows = result[0], result[4]
            if use_latex:
                # run LaTeX for every label (and the hover texts) in the background before the first draw
                prerender_latex(self, [fig], extra=[(arrow.label, hover_size) for arrow in arrows])
            size_to_content(fig, fig.level_lines, *fig.diagram_counts)  # big diagrams get a bigger figure
            fit_side_margins(fig, fig.level_lines)
        fig.canvas.mpl_connect('resize_event', lambda _event, fig=fig: fit_side_margins(fig, fig.level_lines))
        return result

    def _build_trs_fig(self, lvls_df, pri_trs_df, sec_trs_df, use_latex):
        tr_arrows = []
        lvls = []
        lvls_text = ""
        pri_trs_text = ""
        sec_trs_text = ""
        N_LVLs = len(lvls_df)
        ys = assign_lvls_y_positions(lvls_df)
        lvls_df['y'] = ys
        Y_MIN, Y_MAX = level_y_limits(ys)

        def draw_level_line(ax, level_label, energy_label, w=0, y=0, header=False, molecule_name=""):
            return LevelLine(ax, level_label, energy_label, w=w, y=y, header=header, molecule_name=molecule_name)

        def draw_transition(ax, tr, x, h_step, type_, number):
            upper_lvl = lvls_df[lvls_df['level'] == tr['upper lvl']]
            lower_lvl = lvls_df[lvls_df['level'] == tr['lower lvl']]
            y_up = upper_lvl['y'].values[0]
            y_down = lower_lvl['y'].values[0]
            lvl_idx = [upper_lvl['y'].index[0], lower_lvl['y'].index[0]]
            return TransitionArrow(ax, x, y_up, y_down, h_step, lvl_idx, tr['upper lvl'], tr['lower lvl'],
                                   tr['nu'], tr['tau'], type_, number)

        def make_fig():
            fig, axes = plt.subplots(2, 1, sharex=True,
                                     figsize=(12, 6.5),  # inches
                                     dpi=100,
                                     gridspec_kw={'height_ratios': [1, N_LVLs + 1]})
            fig.subplots_adjust(top=0.97, bottom=0.02, left=0.2, right=0.8, hspace=0.0)
            fig.set_facecolor('white')
            return fig, axes

        def check_sec_trs(lvl):
            if sec_trs_df.empty:
                return 0, pd.DataFrame()
            trs_from_lvl = sec_trs_df[sec_trs_df['upper lvl'] == lvl]
            m = max(1, len(trs_from_lvl))
            return m, trs_from_lvl

        def convert_level_for_latex(level, with_comma=True):
            lvl = re.sub(r'[_^\\,]', ',', level)
            lvl = re.sub(r',+', ',', lvl)
            if with_comma:
                return re.sub(r'[\${}() \\]', '', lvl)
            else:
                return re.sub(r'[\${}(), \\]', '', lvl)

        def transition_text(tr, x):
            freq, unit = frequency_parts(tr['nu'])
            m, e = lifetime_parts(tr['tau'])
            # \DrawTr{<i>}{<f>}{<ν,G>}{<τman,τexp>}{<Δx_i,Δx_f>}{<loc>}{<pos>}{<dx,dy>}
            return (rf"\DrawTr"
                    fr"{{l_{convert_level_for_latex(tr['upper lvl'], False)}}}"
                    fr"{{l_{convert_level_for_latex(tr['lower lvl'], False)}}}"
                    fr"{{{freq},{unit}}}"
                    fr"{{{m},{e}}}"
                    f"{{{x},{x}}}"
                    "{right}{0.5}{0,0}\n"
                    )

        def level_text(lvl):
            # \DrawLevel{<x,y>}{<J,Ka,Kc,parity,vt>}{<E>}
            return (rf"\DrawLevel{{0,{lvl.y}}}"
                    f"{{{convert_level_for_latex(lvl.level)}}}"
                    f"{{{lvl.E:0.5f}}}\n"
                    )

        def make_final_text():
            sec_trs_txt = f'%-- Secondary Transitions:\n{sec_trs_text}' if sec_trs_text else ''
            return (f'%-- Levels:\n'
                    f'{lvls_text}\n'
                    f'%-- Primary Transitions:\n'
                    f'{pri_trs_text}\n'
                    + sec_trs_txt
                    )

        highlighted = []

        def place_hover_label(event, x, y, text):
            """Show ν and τ beside the pointer, on the side towards the middle of the diagram."""
            box = ax_line.bbox
            flip_x = event.x > (box.x0 + box.x1) / 2
            flip_y = event.y > (box.y0 + box.y1) / 2
            dx, dy = HOVER_OFFSET_PX
            nu_tau_label.set_text(text)
            nu_tau_label.set_position((x, y))
            nu_tau_label.set_ha("right" if flip_x else "left")
            nu_tau_label.set_va("top" if flip_y else "bottom")
            nu_tau_label.set_transform(offset_copy(ax_line.transData, fig=fig, x=-dx if flip_x else dx,
                                                   y=-dy if flip_y else dy, units='dots'))
            nu_tau_label.set_visible(True)

        def look_for_arrow(y):
            for arrow in tr_arrows:
                if arrow.y_up == y or arrow.y_down == y:
                    arrow.selected(True)
                    highlighted.append((arrow.type, arrow.number))
                else:
                    arrow.selected(False)

        def on_move(event):
            # Reset all visuals
            nu_tau_label.set_visible(False)
            highlighted.clear()
            for lvl in lvls:
                lvl.selected(False)
            for arrow in tr_arrows:
                arrow.selected(False)

            if event.inaxes == ax_line:
                x, y = event.xdata, event.ydata
                for arrow in tr_arrows:
                    if arrow.contain(x, y):
                        place_hover_label(event, x, y, arrow.label)
                        arrow.selected(True)
                        highlighted.append((arrow.type, arrow.number))
                        idx_up, idx_down = arrow.lvl_idx
                        lvls[idx_up].selected(True, trs=arrow.type)
                        lvls[idx_down].selected(True, trs=arrow.type)
                        break
            else:
                # Transform screen (event) to data coords
                x_ax, _ = ax_line.transAxes.inverted().transform((event.x, event.y))
                _, y_data = ax_line.transData.inverted().transform((event.x, event.y))

                y_min, y_max = ax_line.get_ylim()

                def mid(i):
                    return (lvls[i].y + lvls[i + 1].y) / 2.

                for i in range(len(lvls)):
                    if i == 0 and y_min <= y_data < mid(0):
                        look_for_arrow(lvls[0].y)
                        lvls[0].selected(True)
                        break
                    elif 0 < i < len(lvls) - 1 and mid(i - 1) <= y_data < mid(i):
                        look_for_arrow(lvls[i].y)
                        lvls[i].selected(True)
                        break
                    elif i == len(lvls) - 1 and mid(len(lvls) - 2) <= y_data < y_max:
                        look_for_arrow(lvls[-1].y)
                        lvls[-1].selected(True)
                        break

            fig.canvas.draw_idle()
            selection.hovered.emit(list(highlighted))

        def on_press(event):
            if event.inaxes == ax_line and event.button == 1 and event.dblclick:
                x, y = event.xdata, event.ydata
                for arrow in tr_arrows:
                    if arrow.contain(x, y):
                        new_trs_df = self.df[self.df['upper lvl'] == arrow.lower_lvl].copy()
                        self.build_new_tab(new_trs_df, f"From {plain_level(arrow.lower_lvl)}")

        # Make a figure
        fig, [ax_header, ax_line] = make_fig()

        # Transitions table dataframe and the bridge from hover to the table
        table_df = new_table_frame()
        selection = TransitionSelection()

        # Place the groups of transitions (those ending on one lower level, plus the secondary ones leaving
        # it) from left to right; a group moves left past every placed group it does not overlap in height
        y_of = dict(zip(lvls_df['level'], lvls_df['y']))
        groups = []
        for lower_lvl in pri_trs_df['lower lvl'].unique().tolist():
            trs_to_lvl = pri_trs_df[pri_trs_df['lower lvl'] == lower_lvl]
            m, trs_from_lvl = check_sec_trs(lower_lvl)
            top = max(y_of[u] for u in trs_to_lvl['upper lvl'])
            bottom = min([y_of[lower_lvl], *(y_of[lo] for lo in trs_from_lvl.get('lower lvl', []))])
            groups.append((trs_to_lvl, trs_from_lvl, m, top, bottom))
        placed = []  # (x0, x1, bottom, top)
        for trs_to_lvl, trs_from_lvl, m, top, bottom in groups:
            width = (max(len(trs_to_lvl), m) - 1) * H_STEPS['h-small']
            x0 = H_STEPS['h-large']
            for p_x0, p_x1, p_bottom, p_top in placed:
                if bottom < p_top + GROUP_GAP_LEVELS and top > p_bottom - GROUP_GAP_LEVELS:
                    x0 = max(x0, p_x1 + H_STEPS['h-large'])
            placed.append((x0, x0 + width, bottom, top))

        # Draw transition arrows
        pri_tr_number = 1
        sec_tr_number = 1
        for (trs_to_lvl, trs_from_lvl, m, _top, _bottom), (x0, x1, _b, _t) in zip(groups, placed):
            centre = (x0 + x1) / 2.
            x = centre - (len(trs_to_lvl) - 1) / 2. * H_STEPS['h-small']
            # Primary transitions
            for _, tr in trs_to_lvl.iterrows():
                pri_trs_text += transition_text(tr, x)
                tr_arrows.append(draw_transition(ax_line, tr, x, H_STEPS['h-small'], 'pri', pri_tr_number))
                add_row(table_df, 'pri', pri_tr_number, tr)
                pri_tr_number += 1
                x += H_STEPS['h-small']

            x = centre - (m - 1) / 2. * H_STEPS['h-small']
            # Secondary transitions
            for _, tr in trs_from_lvl.iterrows():
                sec_trs_text += transition_text(tr, x)
                tr_arrows.append(draw_transition(ax_line, tr, x, H_STEPS['h-small'], 'sec', sec_tr_number))
                add_row(table_df, 'sec', sec_tr_number, tr)
                sec_tr_number += 1
                x += H_STEPS['h-small']
        x_tr = max((x1 for _x0, x1, _b, _t in placed), default=0)

        table_df = finish_frame(table_df)

        # Draw energy levels
        WIDTH = x_tr + H_STEPS['h-large']
        header = draw_level_line(ax_header, self.molecule_info.label_template, r"$\mathbf{Energy\,(cm^{-1})}$", header=True,
                        molecule_name=self.molecule_info.latex_name)
        for _, level in lvls_df.iterrows():
            lvls_text += level_text(level)
            lvl = draw_level_line(ax_line, level.level, f'${level["E"]:0.4f}$', WIDTH, level.y)
            lvls.append(lvl)
        fig.level_lines = [header, *lvls]  # their labels set the side margins (fit_side_margins)
        fig.diagram_counts = (tr_arrows, N_LVLs, WIDTH)  # for size_to_content
        # Hover label
        nu_tau_label = ax_line.text(0, 0, '', ha="left", va="bottom", fontsize=HOVER_FONT_SIZE * tex_fontsize_factor(),
                                    color="k", zorder=3,
                                    linespacing=1.4, multialignment="left",
                                    transform=offset_copy(ax_line.transData, fig=fig, x=HOVER_OFFSET_PX[0],
                                                          y=HOVER_OFFSET_PX[1], units='dots'),
                                    bbox=BBOX_STYLES['nu_tau_label'])
        fig.canvas.mpl_connect("motion_notify_event", on_move)
        fig.canvas.mpl_connect("button_press_event", on_press)
        ax_line.set_xlim(0, WIDTH)
        ax_line.set_ylim(Y_MIN, Y_MAX)
        ax_line.axis("off")
        ax_header.set_ylim(-0.5, 0.5)
        ax_header.axis("off")
        return fig, ax_line, make_final_text(), lvls, tr_arrows, table_df, selection
