from __future__ import annotations
# Standard library
import json
import re
import shutil

# Third-party
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
from matplotlib.patches import FancyArrowPatch
from matplotlib.transforms import blended_transform_factory, offset_copy
from matplotlib.backends.backend_pdf import PdfPages

# Qt / PySide6
from fractions import Fraction

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog,
    QGroupBox, QHBoxLayout, QLabel, QMainWindow, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget, QTabWidget, QTextEdit,
    QSplitter
)

from sciwidgets.dialogs import AskResult, ask_question, show_about_dialog, show_information, show_warning
from sciwidgets.formatting import pretty_sci_text
from sciwidgets.labels import set_latex_enabled
from sciwidgets.panel import ParameterPage
from sciwidgets.params import FloatSlider, IntSlider, NumericLineEdit, SliderFeature
from sciwidgets.plot import ScrollableFigure
from sciwidgets.table import DataFrameView
from sciwidgets.window import MenuBarController, StatusBarController, center_on_screen

from linecat import __version__
from linecat.cdms import convert_molecule_catalog

from linecat.molecules import MoleculeInfo, REGISTRY  # provides species metadata/behavior

MAX_PLOT_TRANSITIONS = 50  # above this the diagram asks before drawing
MAX_RECENT = 5
NATIVE_MENU_BAR = False  # menus inside each window (on macOS the global bar would otherwise be used)

H_STEPS = {
    'h-large': 2,
    'h-small': 0.75,
}

TRANS_COLOR = {
    'pri': ['darkred', 'tomato'],
    'sec': ['darkblue', 'deepskyblue']
}

BBOX_STYLES = {
    'nu_tau_label': dict(boxstyle="round,pad=0.3", facecolor='lightyellow', edgecolor='darkorange', linewidth=1.5),
    'lvl': dict(boxstyle="round,pad=0.3", facecolor='honeydew', edgecolor='darkgreen', linewidth=1.5),
    'pri-trs': dict(boxstyle="round,pad=0.3", facecolor='lightpink', edgecolor='darkred', linewidth=1.5),
    'sec-trs': dict(boxstyle="round,pad=0.3", facecolor='lightblue', edgecolor='darkblue', linewidth=1.5),
}
GROUPBOX_MARGIN = [7, 10, 7, 4]  # [left, top, right, bottom]
# Appended to the sciwidgets style sheet by linecat.main (same rules as Maxwell Bloch Studio)
APP_STYLE_SHEET = """
    QStatusBar { border-top: 1px solid #999999; }
    QGroupBox {
        font-size: 16pt;
        font-family: "Times New Roman";
        font-weight: bold;
        border: 1px solid #bcbcbc;
        border-radius: 6px;
        margin-top: 12px;
        padding-top: 8px;
        background: white;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        bottom: -3px;
        padding: 0 4px 0 4px;
    }
"""


# =============================================================================
# Utility Classes
# =============================================================================
TABLE_BACKGROUNDS = {'U-': 'tan', 'L-': 'lightskyblue'}
TABLE_FORMATS = {
    'Frequency (MHz)': lambda v: f"{float(v):,.3f}",
    'Error (MHz)': lambda v: f"{float(v):.4f}",
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


class FrequencyRange:
    """
    Widget for selecting and converting frequency ranges across multiple units.

    Maintains an internal frequency range in MHz, updates the UI inputs when
    units change, and converts values to and from MHz for display and callbacks.

    Parameters
    ----------
    callback_func : callable
        Function to invoke with the updated frequency range [min_MHz, max_MHz].

    Attributes
    ----------
    range_value : list of float
        Current frequency range in MHz: [min, max].
    units_dict : dict of str → float
        Mapping of unit labels to their conversion factors into MHz.
    unit : str
        Last valid unit label (used to revert the combo on invalid input).
    from_value : NumericLineEdit
        Input widget for the lower‐bound value.
    to_value : NumericLineEdit
        Input widget for the upper‐bound value.
    unit_combo : QComboBox
        Dropdown for selecting display units.
    apply_button : QPushButton
        Button that applies the new range when clicked.
    layout : QVBoxLayout
        Container layout holding all of the widget’s UI elements.
    """

    def __init__(self, callback_func):
        """
        Initialize the frequency-range selector widget.

        Parameters
        ----------
        callback_func : callable
            Function to invoke with the updated frequency range [min_MHz, max_MHz].

        Returns
        -------
        None
        """
        self.callback_func = callback_func
        self.range_value = [0.0, 1e10]

        c = 2.99792458e8  # speed of light in m/s
        self.units_dict = {
            'Hz': 1e-6, 'KHz': 1e-3, 'MHz': 1.0, 'GHz': 1e3,
            'THz': 1e6, 'Å': c * 1e4, 'nm': c * 1e3,
            'μm': c, 'mm': c * 1e-3, 'm': c * 1e-6,
        }
        self.unit = 'MHz'
        self.from_value = self._make_line_edit()
        self.to_value = self._make_line_edit()
        unit_layout, self.unit_combo = create_combo(
            'Frequency Unit',
            items=list(self.units_dict.keys()),
            item=self.unit,
        )
        self.apply_button = create_button('Apply', self.update_range)

        self.groupbox = QGroupBox('Frequency Range')
        self.layout = QVBoxLayout(self.groupbox)
        self.layout.setContentsMargins(*GROUPBOX_MARGIN)
        self.layout.addStretch()
        self.layout.addLayout(self._labeled('From', self.from_value))
        self.layout.addLayout(self._labeled('To', self.to_value))
        self.layout.addLayout(unit_layout)
        self.layout.addWidget(self.apply_button, alignment=Qt.AlignHCenter)
        self.layout.addStretch()

    @staticmethod
    def _make_line_edit():
        return NumericLineEdit(0.0, val_fmt='{:.3f}', min_limit=0.0, place_holder_text='e.g. 123.45')

    @staticmethod
    def _labeled(text, widget):
        layout = QHBoxLayout()
        layout.addWidget(create_label(text, 'Right'))
        layout.addWidget(widget)
        return layout

    def _get_conversion_factor(self):
        """
        Get the conversion factor from the selected unit to MHz.

        Returns
        -------
        float
            Multiplicative factor for converting between the current unit and MHz.
        """
        return self.units_dict.get(self.unit_combo.currentText(), 1.0)

    def _unit_has_Hz(self):
        """
        Determine if the current unit label includes 'Hz'.

        Returns
        -------
        bool
            True if 'Hz' is in the selected unit label, False otherwise.
        """
        return 'Hz' in self.unit_combo.currentText()

    def _convert_to_mhz(self, value):
        """
        Convert an input value from the selected unit to MHz.

        Parameters
        ----------
        value : float
            Value in the currently selected display units.

        Returns
        -------
        float
            Converted value in MHz.
            If the unit is not a frequency (reciprocal units) and the input is zero,
            returns infinity.
        """
        factor = self._get_conversion_factor()
        if self._unit_has_Hz():
            return factor * value
        if value == 0:
            return float('inf')
        return factor / value

    def _convert_from_mhz(self, value):
        """
        Convert a frequency in MHz to the selected display unit.

        Parameters
        ----------
        value : float
            Frequency in MHz.

        Returns
        -------
        float
            Value in the currently selected display units.
            If the unit is not a frequency (reciprocal units) and the input is zero,
            returns infinity.
        """
        factor = self._get_conversion_factor()
        if self._unit_has_Hz():
            return value / factor
        if value == 0:
            return float('inf')
        return factor / value

    def _get_new_range(self):
        """
        Read UI inputs, convert them to MHz, and return ordered bounds.

        Returns
        -------
        tuple of float
            A 2-tuple (min_MHz, max_MHz) with the lower and upper frequency bounds in MHz.
        """
        low = self._convert_to_mhz(self.from_value.get_value())
        high = self._convert_to_mhz(self.to_value.get_value())
        if self._unit_has_Hz():
            return low, high
        return high, low

    def _set_line_edit_range(self):
        """
        Update UI inputs to reflect the internal frequency range in display units.

        Converts the stored `range_value` (in MHz) into the currently selected units
        and updates the 'From' and 'To' NumericLineEdit widgets accordingly, handling
        reciprocal units as needed.

        Returns
        -------
        None
        """
        mn = self._convert_from_mhz(self.range_value[0])
        mx = self._convert_from_mhz(self.range_value[1])
        if self._unit_has_Hz():
            self.from_value.set_value(mn)
            self.to_value.set_value(mx)
        else:
            self.from_value.set_value(mx)
            self.to_value.set_value(mn)

    def reset(self):
        """Back to the full range (0 to 1e10 MHz) in MHz, without calling back."""
        self.unit = 'MHz'
        self.unit_combo.setCurrentText(self.unit)
        self.set_range(0.0, 1e10)

    def set_range(self, min_mhz, max_mhz):
        """Show a range (in MHz) in the fields without calling back."""
        self.range_value = [float(min_mhz), float(max_mhz)]
        self._set_line_edit_range()

    def update_range(self):
        """
        Validate and apply a new frequency range from the UI inputs.

        Converts the ‘From’ and ‘To’ values to MHz and ensures the lower bound
        is less than the upper bound. On success, updates the internal range,
        stores the selected unit, and invokes the callback. On failure, reverts
        the unit selection and resets the displayed inputs.

        Returns
        -------
        None
        """
        new_min, new_max = self._get_new_range()
        if new_min < new_max and [new_min, new_max] != self.range_value:
            self.unit = self.unit_combo.currentText()
            self.range_value = [new_min, new_max]
            self.callback_func(self.range_value)
        else:
            self.unit_combo.setCurrentText(self.unit)
        self._set_line_edit_range()


class LevelLine:
    def __init__(self, ax, lvl_label, e_label, w=0, y=0, header=False, molecule_name=""):
        self.ax = ax
        self.lvl_label = lvl_label
        self.e_label = e_label
        self.w = w
        self.y = y
        self.header = header
        self.font_size = self.set_font_size()
        transform = blended_transform_factory(ax.transAxes, ax.transData)
        self.lvl = ax.text(-0.02, y, lvl_label,
                           ha="right", va="center",
                           fontsize=self.font_size, color='k',
                           transform=transform)
        self.energy = ax.text(1.02, y, e_label,
                              ha="left", va="center",
                              fontsize=self.font_size, color='k',
                              transform=transform)
        if header:
            ax.text(0.5, y, molecule_name,
                    ha="center", va="center",
                    fontsize=self.font_size * 1.5, color='k',
                    transform=transform)
        if not header:
            self.line, = ax.plot([0, w], [y, y], color='k', linewidth=1, zorder=0)

    def set_font_size(self):
        font_size = 14 * tex_fontsize_factor()
        if self.header:
            font_size += 2
        return font_size

    def selected(self, selected, trs=None):
        if trs is not None:
            if trs == 'pri':
                bbox = BBOX_STYLES['pri-trs']
            else:
                bbox = BBOX_STYLES['sec-trs']
            self.line.set(color=TRANS_COLOR[trs][1], linewidth=3, zorder=2)
            self.lvl.set(fontsize=self.font_size + 2, zorder=2)
            self.energy.set(fontsize=self.font_size + 2, zorder=2)
            self.lvl.set_bbox(bbox)
            self.energy.set_bbox(bbox)
        elif selected:
            self.line.set(color='g', linewidth=3, zorder=2)
            self.lvl.set(fontsize=self.font_size + 2, zorder=2)
            self.energy.set(fontsize=self.font_size + 2, zorder=2)
            self.lvl.set_bbox(BBOX_STYLES['lvl'])
            self.energy.set_bbox(BBOX_STYLES['lvl'])
        else:
            self.line.set(color='k', linewidth=1, zorder=0)
            self.lvl.set(fontsize=self.font_size, zorder=0)
            self.energy.set(fontsize=self.font_size, zorder=0)
            self.lvl.set_bbox(None)
            self.energy.set_bbox(None)

    def set_y(self, y):
        self.y = y
        self.line.set_data([0, self.w], [y, y])
        self.lvl.set_y(y)
        self.energy.set_y(y)


class TransitionArrow:
    def __init__(self, ax, x, y_up, y_down, w, lvl_idx, upper_lvl, lower_lvl, nu, tau, type_, number):
        self.x = x
        self.x_left = x - w / 2.
        self.x_right = x + w / 2.
        self.y_up = y_up
        self.y_down = y_down
        self.y_mid = (y_up + y_down) / 2.
        self.lvl_idx = lvl_idx
        self.upper_lvl = upper_lvl
        self.lower_lvl = lower_lvl
        self.linewidth = 0.01
        self.type = type_
        self.number = number
        self.color = TRANS_COLOR[type_]
        self.label = self.make_label_text(nu, tau)
        self.arrow = FancyArrowPatch(
            (x, y_up), (x, y_down),
            arrowstyle='simple',
            mutation_scale=20,
            zorder=1,
            lw=self.linewidth,
            color=self.color[0]
        )
        ax.add_patch(self.arrow)
        self.number_text = self.draw_transition_number(ax)

    def draw_transition_number(self, ax):
        return ax.text(
            self.x, self.y_mid, str(self.number),
            ha="center", va="center",
            fontsize=12 * tex_fontsize_factor(),
            color=self.color[0],
            zorder=1,
            bbox=dict(
                boxstyle="circle,pad=0.3",
                fc="white", ec=self.color[0],
                lw=1
            )
        )

    def contain(self, x, y):
        if x is None or y is None:
            return False
        return self.x_left <= x <= self.x_right and self.y_down <= y < self.y_up

    def selected(self, selected):
        if selected:
            self.arrow.set_color(self.color[1])
            self.arrow.set_linewidth(2)
            self.number_text.set(color=self.color[1], fontsize=15)
            self.number_text.set_bbox(
                dict(
                    boxstyle="circle,pad=0.3",
                    fc="white", ec=self.color[1],
                    lw=2
                )
            )
        else:
            self.arrow.set_color(self.color[0])
            self.arrow.set_linewidth(self.linewidth)
            self.number_text.set(color=self.color[0], fontsize=12)
            self.number_text.set_bbox(
                dict(
                    boxstyle="circle,pad=0.3",
                    fc="white", ec=self.color[0],
                    lw=1
                )
            )

    def set_y(self, ys):
        y_up = ys[self.lvl_idx[0]]
        y_down = ys[self.lvl_idx[1]]
        self.y_up = y_up
        self.y_down = y_down
        self.y_mid = (y_up + y_down) / 2.
        self.arrow.set_positions((self.x, y_up), (self.x, y_down))
        self.number_text.set_position((self.x, self.y_mid))

    def beauty_digits(self, n):
        if n < 10:
            return f"{n:.2f}"
        elif n < 100:
            return f"{n:.1f}"
        else:
            return f"{n:.0f}"

    def freq_unit(self, nu):
        if nu < 1:
            nu *= 1000
            return self.beauty_digits(nu), 'K'
        elif nu < 1000:
            return self.beauty_digits(nu), 'M'
        else:
            nu /= 1000
            if nu < 1000:
                return self.beauty_digits(nu), 'G'
            else:
                nu /= 1000
                return self.beauty_digits(nu), 'T'

    def make_label_text(self, nu, tau):
        freq, unit = self.freq_unit(nu)
        tau = f"{tau:.2e}"
        m, e = tau.split('e')
        return fr"$\nu = {freq}\,\mathrm{{{unit}Hz}}\, , \tau = {m}\times 10^{{{int(e)}}} (s)$"


class TabContent:
    def __init__(self, fig, ax, latex_txt, lvls, arrows, lvls_df, trs_df, table_fig):
        self.comps_dict = {
            'pri': {
                'fig': fig,
                'table_fig': table_fig,
                'ax': ax,
                'scroll': ScrollableFigure(fig),
                'table_scroll': ScrollableFigure(table_fig),
                'latex text': latex_txt,
                'lvls': lvls,
                'arrows': arrows,
                'lvls df': lvls_df,
                'trs df': trs_df,
                'zoom factor': [1., 1.],
                'coarse scale factor': 0.,
                'fine scale factor': 0.,
            }
        }
        self.scroll = self.comps_dict['pri']['scroll']
        self.table_scroll = self.comps_dict['pri']['table_scroll']
        self.widget = QWidget()
        self.layout = QVBoxLayout(self.widget)
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.scroll)
        self.splitter.addWidget(self.table_scroll)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        self.layout.addWidget(self.splitter)

        self.comps_exist = {
            'pri': 1,
            'sec': 0,
            'pri-latex': 0,
            'sec-latex': 0,
        }
        self.use_latex_checkbox = False
        self.sec_trs_checkbox = False

    def comps_dict_name(self):
        if self.sec_trs_checkbox:
            name = 'sec'
        else:
            name = 'pri'
        if self.use_latex_checkbox:
            name += '-latex'
        return name

    def add_comps(self, fig, ax, latex_txt, lvls, arrows, lvls_df, trs_df, table_fig):
        dict_name = self.comps_dict_name()
        self.comps_dict[dict_name] = {
            'fig': fig,
            'table_fig': table_fig,
            'ax': ax,
            'scroll': ScrollableFigure(fig),
            'table_scroll': ScrollableFigure(table_fig),
            'latex text': latex_txt,
            'lvls': lvls,
            'arrows': arrows,
            'lvls df': lvls_df,
            'trs df': trs_df,
            'zoom factor': [1., 1.],
            'coarse scale factor': 0.,
            'fine scale factor': 0.,
        }
        self.comps_exist[dict_name] = 1

    def set_zoom(self, perc, direction):
        name = self.comps_dict_name()
        comps = self.comps_dict[name]
        if direction == 'h':
            comps['zoom factor'][0] = perc / 100.0
        else:
            comps['zoom factor'][1] = perc / 100.0

    def set_real_size(self, coarse_scale_factor, fine_scale_factor):
        name = self.comps_dict_name()
        comps = self.comps_dict[name]
        comps['coarse scale factor'] = coarse_scale_factor
        comps['fine scale factor'] = fine_scale_factor

    def set_comps_exist(self, state):
        name = self.comps_dict_name()
        self.comps_exist[name] = state

    def get_comps(self):
        name = self.comps_dict_name()
        return self.comps_dict[name].copy()

    def get_comps_exist(self):
        name = self.comps_dict_name()
        return self.comps_exist[name]

    def set_canvas(self):
        name = self.comps_dict_name()
        old_scroll, old_table = self.scroll, self.table_scroll
        self.scroll = self.comps_dict[name]['scroll']
        self.table_scroll = self.comps_dict[name]['table_scroll']
        if self.scroll is not old_scroll:
            self.splitter.replaceWidget(0, self.scroll)
            old_scroll.hide()
            self.scroll.show()
        if self.table_scroll is not old_table:
            self.splitter.replaceWidget(1, self.table_scroll)
            old_table.hide()
            self.table_scroll.show()

    def figures(self):
        for comps in self.comps_dict.values():
            yield comps['fig']
            yield comps['table_fig']


class PlotWindow(QMainWindow):
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
        self.build_new_tab(self.build_compatible_df(filtered_df), "Primary Transitions")
        self.show()
        center_on_screen(self, (1500, 1000), fallback=(1400, 900))

    def build_layout(self):
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        self.menu = MenuBarController(self, {
            "File": [
                {"id": "save_pdf", "text": "Save Figure as PDF…", "shortcut": QKeySequence.Save},
                {"id": "latex_commands", "text": "LaTeX Commands…"},
            ],
            "View": [
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
        # Group Box
        group_box = QGroupBox("Zoom")
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(*GROUPBOX_MARGIN)
        group_layout.addWidget(self.hori_zoom_slider)
        group_layout.addWidget(self.vert_zoom_slider)
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
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self.settings.setValue('paths/pdf_dir', str(Path(path).parent))

        # Grab the figure from the current tab and save
        idx = self.tabs.currentIndex()
        tab_content = self.tabs_content[idx]
        comps = tab_content.get_comps()
        fig = comps['fig']
        table_fig = comps['table_fig']
        with PdfPages(path) as pdf:
            pdf.savefig(fig)
            pdf.savefig(table_fig)

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
        HEIGHT = ys[-1] - ys[0]
        Y_MIN = ys[0] - 0.05 * HEIGHT
        Y_MAX = ys[-1] + 0.05 * HEIGHT
        ax.set_ylim(Y_MIN, Y_MAX)
        for arrow in arrows:
            arrow.set_y(ys)
        fig.canvas.draw_idle()

    def on_menu_action(self, _menu_path, action_id, checked):
        if action_id == 'save_pdf':
            self.export_pdf()
        elif action_id == 'latex_commands':
            self.latex_format()
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
        self.menu.set_checked('secondary', False)
        tab_content.sec_trs_checkbox = False

    def use_latex_checkbox_failed(self, tab_content):
        show_warning("LaTeX not available", "LaTeX was not found on this computer.", parent=self)
        self.menu.set_checked('use_latex', False)
        tab_content.use_latex_checkbox = False

    def latex_format(self):
        idx = self.tabs.currentIndex()
        tab_content = self.tabs_content[idx]
        comps = tab_content.get_comps()
        text = comps['latex text']

        # build a simple dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("LaTeX Commands")
        dlg.resize(600, 400)

        main_layout = QVBoxLayout(dlg)

        # read-only text area
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(text)
        main_layout.addWidget(te)

        # button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        copy_btn = QPushButton("Copy")
        btn_row.addWidget(copy_btn)

        btn_row.addSpacing(10)

        close_btn = QPushButton("Close")
        btn_row.addWidget(close_btn)

        main_layout.addLayout(btn_row)

        # connections
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(text))
        close_btn.clicked.connect(dlg.reject)

        dlg.exec()

    def close_tab(self, idx):
        tab_title = self.tabs.tabText(idx)
        if tab_title == "Primary Transitions":
            show_information("Not Allowed", "You cannot close the Primary Transitions tab.", parent=self)
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
        new_lower_lvls = lower_lvls_df[~lower_lvls_df['level'].isin(upper_lvls_df['level'])]
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
        fig, ax, latex_txt, lines, arrows, table_fig = self.build_trs_fig(lvls_df, trs_df)
        return TabContent(fig, ax, latex_txt, lines, arrows, lvls_df, trs_df, table_fig)

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
        fig, ax, latex_txt, lines, arrows, table_fig = self.build_trs_fig(all_lvls, pri_trs_df, sec_trs_df, use_latex)
        self.reset_sliders()
        tab_content.add_comps(fig, ax, latex_txt, lines, arrows, all_lvls, sec_trs_df, table_fig)
        tab_content.set_canvas()
        self.refresh_tab()
        return True

    def add_pri_comps_to_tab_content(self, tab_content):
        self.hori_zoom_slider.set_value(100)
        self.vert_zoom_slider.set_value(100)
        pri_trs_df = tab_content.comps_dict['pri']['trs df']
        pri_lvls_df = tab_content.comps_dict['pri']['lvls df']
        fig, ax, latex_txt, lines, arrows, table_fig = self.build_trs_fig(pri_lvls_df, pri_trs_df, use_latex=True)
        self.reset_sliders()
        tab_content.add_comps(fig, ax, latex_txt, lines, arrows, pri_lvls_df, pri_trs_df, table_fig)
        tab_content.set_canvas()
        self.refresh_tab()

    def build_new_tab(self, trs_df, title):
        if trs_df.empty:
            show_warning("No Transition", "No transitions found. Nothing to display.", parent=self)
        else:
            self.reset_sliders()
            tab_content = self.build_pri_comps(trs_df)
            self.tabs_content.append(tab_content)
            idx = self.tabs.addTab(tab_content.widget, title)
            self.tabs.setCurrentIndex(idx)

    def build_trs_fig(self, lvls_df, pri_trs_df, sec_trs_df=None, use_latex=False):
        """Build the diagram and table figures; LaTeX rendering is switched on only while building."""
        if sec_trs_df is None:
            sec_trs_df = pd.DataFrame()
        with mpl.rc_context({"text.usetex": use_latex}):
            return self._build_trs_fig(lvls_df, pri_trs_df, sec_trs_df, use_latex)

    def _build_trs_fig(self, lvls_df, pri_trs_df, sec_trs_df, use_latex):
        tr_arrows = []
        lvls = []
        lvls_text = ""
        pri_trs_text = ""
        sec_trs_text = ""
        N_LVLs = len(lvls_df)
        ys = assign_lvls_y_positions(lvls_df)
        lvls_df['y'] = ys
        HEIGHT = ys[-1] - ys[0]
        Y_MIN = ys[0] - 0.05 * HEIGHT
        Y_MAX = ys[-1] + 0.05 * HEIGHT

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

        def make_table_fig(n_rows):
            m = n_rows + 2.0
            margin = 1. / m
            h = m / 3.
            fig, ax = plt.subplots(figsize=(10, h), dpi=100)
            fig.subplots_adjust(left=0.05, right=0.95, top=1 - margin, bottom=margin)
            ax.axis("off")
            return fig, ax

        def make_table(ax, df):
            df['nu'] = df['nu'].map(lambda x: f"{x:,.4f}")
            df['tau'] = df['tau'].map(lambda x: scientific_display(x, 3))
            for col in ['Number', 'nu', 'd_ij']:
                df[col] = df[col].map(lambda x: f"${x}$")
            df = df[['Number', 'Type', 'nu', 'tau', 'd_ij']]
            table = ax.table(
                cellText=df.values,
                colLabels=[r'$\mathbf{Number}$', r'$\mathbf{Type}$', r'$\mathbf{\nu \, (MHz)}$',
                           r'$\mathbf{\tau \, (s)}$', r'$\mathbf{d_{ij} \, (D)}$'],
                loc="center",
                cellLoc="center",
                bbox=[0, 0, 1, 1],
            )

            table.auto_set_font_size(False)
            table.set_fontsize(12 * tex_fontsize_factor())
            n_cols = len(df.columns)
            for col in range(n_cols):
                cell = table[(0, col)]
                cell.set_text_props(fontsize=14 * tex_fontsize_factor(), fontweight='bold')
            table.auto_set_column_width(col=list(range(len(df.columns))))
            return table

        def align_column(table, col_idx, alignment):
            cells = table.get_celld()
            n_rows = max(r for (r, c) in cells.keys())
            for r in range(1, n_rows + 1):
                cell = table[r, col_idx]
                text = cell.get_text()
                if alignment == 'left':
                    text.set_ha("left")
                    text.set_x(0.05)
                elif alignment == 'right':
                    text.set_ha("right")
                    text.set_x(0.95)

        def set_row_face_color(table, row_idx, color):
            cells = table.get_celld()
            n_cols = max(c for (r, c) in cells.keys()) + 1
            for c in range(n_cols):
                cell = table[row_idx, c]
                cell.set_facecolor(mcolors.to_rgba(color, alpha=0.3))

        def change_row_color(arrow, selected=False):
            type_ = arrow.type
            number = arrow.number
            color = arrow.color[1] if selected else arrow.color[0]
            row_idx = table_df.index[(table_df['type_'] == type_) & (table_df['Number'] == number)][0]
            set_row_face_color(transition_table, row_idx + 1, color)

        def scientific_display(value, float_point):
            value = f"{value:.{float_point}e}"
            m, e = value.split('e')
            return fr"${m}\times 10^{{{int(e)}}}$"

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
            def beauty_digits(n):
                if n < 10:
                    return f"{n:.2f}"
                elif n < 100:
                    return f"{n:.1f}"
                else:
                    return f"{n:.0f}"

            def freq_unit(nu):
                if nu < 1:
                    nu *= 1000
                    return beauty_digits(nu), 'K'
                elif nu < 1000:
                    return beauty_digits(nu), 'M'
                else:
                    nu /= 1000
                    if nu < 1000:
                        return beauty_digits(nu), 'G'
                    else:
                        nu /= 1000
                        return beauty_digits(nu), 'T'

            freq, unit = freq_unit(tr['nu'])
            tau = f"{tr['tau']:.2e}"
            m, e = tau.split('e')
            # \DrawTr{<i>}{<f>}{<ν,G>}{<τman,τexp>}{<Δx_i,Δx_f>}{<loc>}{<pos>}{<dx,dy>}
            return (rf"\DrawTr"
                    fr"{{l_{convert_level_for_latex(tr['upper lvl'], False)}}}"
                    fr"{{l_{convert_level_for_latex(tr['lower lvl'], False)}}}"
                    fr"{{{freq},{unit}}}"
                    fr"{{{m},{int(e)}}}"
                    f"{{{x},{x}}}"
                    "{right}{0.5}{0,0}\n"
                    )

        def level_text(lvl):
            # \DrawLevel{<x,y>}{<J,Ka,Kc,parity,vt>}{<E>}
            return (rf"\DrawLevel{{0,{lvl.y}}}"
                    f"{{{convert_level_for_latex(lvl.level)}}}"
                    f"{{{level.E:0.5f}}}\n"
                    )

        def make_final_text():
            sec_trs_txt = f'%-- Secondary Transitions:\n{sec_trs_text}' if sec_trs_text else ''
            return (f'%-- Levels:\n'
                    f'{lvls_text}\n'
                    f'%-- Primary Transitions:\n'
                    f'{pri_trs_text}\n'
                    + sec_trs_txt
                    )

        def look_for_arrow(y):
            for arrow in tr_arrows:
                if arrow.y_up == y or arrow.y_down == y:
                    arrow.selected(True)
                    change_row_color(arrow, True)
                else:
                    arrow.selected(False)
                    change_row_color(arrow, False)

        def on_move(event):
            # Reset all visuals
            nu_tau_label.set_visible(False)
            for lvl in lvls:
                lvl.selected(False)
            for arrow in tr_arrows:
                arrow.selected(False)
                change_row_color(arrow, False)

            if event.inaxes == ax_line:
                x, y = event.xdata, event.ydata
                for arrow in tr_arrows:
                    if arrow.contain(x, y):
                        nu_tau_label.set_text(arrow.label)
                        nu_tau_label.set_position((x, y))
                        nu_tau_label.set_visible(True)
                        arrow.selected(True)
                        change_row_color(arrow, True)
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
            table_fig.canvas.draw_idle()

        def on_press(event):
            if event.inaxes == ax_line and event.button == 1 and event.dblclick:
                x, y = event.xdata, event.ydata
                for arrow in tr_arrows:
                    if arrow.contain(x, y):
                        title = convert_level_for_latex(arrow.lower_lvl)
                        title = re.sub(r',', ', ', title)
                        new_trs_df = self.df[self.df['upper lvl'] == arrow.lower_lvl].copy()
                        self.build_new_tab(new_trs_df, f'({title})')

        # Make a figure
        fig, [ax_header, ax_line] = make_fig()

        # Transitions table dataframe
        table_df = pd.DataFrame(columns=['type_', 'Type', 'Number', 'nu', 'tau', 'd_ij'])

        # Draw transition arrows
        pri_tr_number = 1
        sec_tr_number = 1
        x_tr = 0
        for lower_lvl in pri_trs_df['lower lvl'].unique().tolist():
            x_tr += H_STEPS['h-large']
            trs_to_lvl = pri_trs_df[pri_trs_df['lower lvl'] == lower_lvl]
            n = len(trs_to_lvl)
            m, trs_from_lvl = check_sec_trs(lower_lvl)
            delta_x = (max(n, m) - 1) * H_STEPS['h-small']
            x_tr += delta_x / 2.
            x = x_tr - (n - 1) / 2. * H_STEPS['h-small']
            # Primary transitions
            for _, tr in trs_to_lvl.iterrows():
                pri_trs_text += transition_text(tr, x)
                tr_arrows.append(draw_transition(ax_line, tr, x, H_STEPS['h-small'], 'pri', pri_tr_number))
                table_df.loc[len(table_df)] = ['pri', r'$\mathrm{Primary}$', pri_tr_number, tr['nu'], tr['tau'],
                                               tr['d_ij (D)']]
                pri_tr_number += 1
                x += H_STEPS['h-small']

            x = x_tr - (m - 1) / 2. * H_STEPS['h-small']
            # Secondary transitions
            for _, tr in trs_from_lvl.iterrows():
                sec_trs_text += transition_text(tr, x)
                tr_arrows.append(draw_transition(ax_line, tr, x, H_STEPS['h-small'], 'sec', sec_tr_number))
                table_df.loc[len(table_df)] = ['sec', r'$\mathrm{Secondary}$', sec_tr_number, tr['nu'], tr['tau'],
                                               tr['d_ij (D)']]
                sec_tr_number += 1
                x += H_STEPS['h-small']

            x_tr += delta_x / 2.

        # Create transitions table
        table_df.sort_values(by=['Type', 'Number'], ascending=True, inplace=True)
        table_df.reset_index(drop=True, inplace=True)
        n_rows = len(table_df) + 1
        table_fig, table_ax = make_table_fig(n_rows)
        transition_table = make_table(table_ax, table_df.copy())
        align_column(transition_table, 2, 'right')
        for arrow in tr_arrows:
            change_row_color(arrow, False)

        # Draw energy levels
        WIDTH = x_tr + H_STEPS['h-large']
        draw_level_line(ax_header, self.molecule_info.label_template, r"$\mathbf{Energy\,(cm^{-1})}$", header=True,
                        molecule_name=self.molecule_info.latex_name)
        for _, level in lvls_df.iterrows():
            lvls_text += level_text(level)
            lvl = draw_level_line(ax_line, level.level, f'${level["E"]:0.4f}$', WIDTH, level.y)
            lvls.append(lvl)
        # Hover label
        nu_tau_label = ax_line.text(0, 0, '', ha="left", va="bottom", fontsize=16 * tex_fontsize_factor(),
                                    color="k", zorder=3,
                                    transform=offset_copy(ax_line.transData, fig=fig, x=50, y=30, units='dots'),
                                    bbox=BBOX_STYLES['nu_tau_label'])
        fig.canvas.mpl_connect("motion_notify_event", on_move)
        fig.canvas.mpl_connect("button_press_event", on_press)
        ax_line.set_xlim(0, WIDTH)
        ax_line.set_ylim(Y_MIN, Y_MAX)
        ax_line.axis("off")
        ax_header.set_ylim(-0.5, 0.5)
        ax_header.axis("off")
        return fig, ax_line, make_final_text(), lvls, tr_arrows, table_fig


# =============================================================================
# Main Application Class
# =============================================================================
class DisplayDataApp(QMainWindow):
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
    filter_page : ParameterPage
        Combo boxes for the quantum-state filters (paths like 'U-S J').
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
        top_layout = QHBoxLayout()
        self.top_center = QVBoxLayout()
        self.top_center.addWidget(self.filter_page)
        top_layout.addStretch(1)
        top_layout.addLayout(self.top_center)
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

    # ----- menus -----
    def menu_spec(self):
        recent = [{"id": f"recent_{i}", "text": Path(p).name} for i, p in enumerate(self.recent_catalogs())]
        recent += [{"id": "sep"}, {"id": "clear_recent", "text": "Clear Menu", "enabled": bool(recent)}]
        return {
            "File": [
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
        if action_id == 'open':
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

    def show_about(self):
        show_about_dialog(
            "About linecat",
            f"<p><b>linecat</b> {__version__}<br>Viewer for CDMS/JPL spectral line catalogs.</p>"
            "<p>Vahid Anari — MIT License<br>"
            '<a href="https://github.com/vahid-anari/linecat">github.com/vahid-anari/linecat</a></p>'
            '<p>Catalog data: <a href="https://cdms.astro.uni-koeln.de/">CDMS</a>, Universität zu Köln.</p>',
            parent=self,
        )

    def convert_catalogs(self):
        """Convert the CDMS .cat files of every registered species found in a folder to CSV."""
        start_dir = self.settings.value('paths/catalogs_dir', '', type=str)
        folder = QFileDialog.getExistingDirectory(self, "Folder with the CDMS .cat files", start_dir)
        if not folder:
            return
        self.settings.setValue('paths/catalogs_dir', folder)
        found = [code for code, info in REGISTRY.items()
                 if all((Path(folder) / f).is_file() for f in info.input_files)]
        if not found:
            show_warning("Nothing to convert",
                         "No registered species has all its .cat files in that folder.", parent=self)
            return
        self.status.set_state(f"Converting {', '.join(found)}…")
        written = [convert_molecule_catalog(code, outdir=folder, catalogs_dir=folder) for code in found]
        self.status.set_state(f"Converted {', '.join(found)} → {Path(folder).name}/")
        if len(written) == 1:
            self.load_file(str(written[0]))

    def load_table_config(self):
        """Table colors, visible columns and font saved by an earlier run (QSettings 'table/config')."""
        try:
            config = json.loads(self.settings.value('table/config', '{}', type=str))
        except ValueError:
            return {}
        return config if isinstance(config, dict) else {}

    def check_molecule_info(self):
        species = self.df['Species'].iloc[0]
        if species not in REGISTRY.keys():
            return False

        self.molecule_info = REGISTRY[species]
        return True

    def create_filter_page(self):
        """
        Build a ParameterPage with one combo box per quantum number for each state.

        Returns
        -------
        ParameterPage
            Two groups ('Upper State', 'Lower State'); widget paths are the
            column names, e.g. 'U-S J'.
        """
        def group(title, prefix):
            return {"group": title, "row": [
                {"type": "combo-box", "path": prefix + key, "label": filter_label(key), "items": ["All"]}
                for key in self.filter_keys
            ]}

        page = ParameterPage({"column": [group("Upper State", "U-S "), group("Lower State", "L-S ")]})
        page.valueChanged.connect(lambda _path, _value: self.update_filters())
        return page

    @property
    def filter_combos(self):
        """Mapping from filter identifiers (e.g. 'U-S J') to their ParameterComboBox."""
        return {path: self.filter_page.get_widget(path) for path in self.filter_page.paths()}

    def set_filter_keys(self):
        """
        Configure quantum-state filter keys and rebuild the filter page.

        Updates `self.filter_keys` from the current molecule and replaces the
        page of combo boxes with one built for the new set of quantum numbers.

        Returns
        -------
        None
        """
        self.filter_keys = self.molecule_info.filters
        old = self.filter_page
        self.filter_page = self.create_filter_page()
        self.top_center.replaceWidget(old, self.filter_page)
        old.setParent(None)
        old.deleteLater()

    def update_range(self, range_vals):
        """
        Apply a new frequency range to the data and refresh filters.

        Parameters
        ----------
        range_vals : list of float or str
            Two-element list [min_MHz, max_MHz], where `max_MHz` can be the
            string 'max' to indicate the full dataset range.

        Returns
        -------
        None
        """
        if self.df is None:
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
        try:
            df = pd.read_csv(path, dtype=str)
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            show_warning("Cannot open catalog", f"{Path(path).name}: {exc}", parent=self)
            return
        if df.empty:
            show_warning("Failed", f"{Path(path).name} is empty.", parent=self)
            return

        self.df = df
        self.load = True
        if not self.check_molecule_info():
            self.df = None
            show_warning("Failed", f"{Path(path).name}: unknown species or not a linecat catalog.", parent=self)
            return
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

    def show_button(self):
        """
            Show the PlotWindow if the number of filtered transitions is acceptable.

            Asks before drawing when there are more than MAX_PLOT_TRANSITIONS transitions,
            asking the user whether to continue.
            """
        if self.filtered_df is None or self.filtered_df.empty:
            show_warning("No Transition", "There are no transitions. Nothing to display.", parent=self)
        elif len(self.filtered_df) <= MAX_PLOT_TRANSITIONS:
            self.plot_window = PlotWindow(self, self.df.copy(), self.filtered_df.copy(), self.molecule_info,
                                          self.latex_available)
        else:
            reply = ask_question(
                "Large Number of Transitions",
                f"You are trying to plot more than {MAX_PLOT_TRANSITIONS} transitions.",
                "This may slow down the rendering. Do you want to continue?",
                yes_btn_label="Continue",
                parent=self,
            )
            if reply == AskResult.YES:
                self.plot_window = PlotWindow(self, self.df.copy(), self.filtered_df.copy(), self.molecule_info,
                                              self.latex_available)


# =============================================================================
# Helper UI Creation Functions
# =============================================================================
def latex_available() -> bool:
    """Return True when a ``latex`` executable is on the PATH."""
    return shutil.which("latex") is not None


def make_slider(label, min_val, max_val, init_val, val_fmt=None):
    """Percent slider without range labels or context menu (zoom and scale controls)."""
    if isinstance(min_val, float):
        return FloatSlider(label, min_val, max_val, unit=r"\%", init_val=init_val, val_fmt=val_fmt or "{:.2f}",
                           show_range=False, features=SliderFeature.NONE)
    return IntSlider(label, min_val, max_val, unit=r"\%", init_val=init_val, show_range=False,
                     features=SliderFeature.NONE)


def tex_fontsize_factor():
    if mpl.rcParams['text.usetex']:
        return 1.2
    return 1.


def create_label(text, alignment='Center', h_size_policy=QSizePolicy.Fixed, v_size_policy=QSizePolicy.Fixed):
    """
    Create and configure a QLabel with text, alignment, and size policies.

    A convenience function to instantiate a QLabel and apply alignment and
    size-policy settings in a single call.

    Parameters
    ----------
    text : str
        The text to display in the label.
    alignment : {'Center', 'Right', 'Left'}, optional
        Text alignment within the label.  Defaults to 'Center'.
    h_size_policy : QSizePolicy.Policy, optional
        Horizontal size policy for the label.  Defaults to QSizePolicy.Fixed.
    v_size_policy : QSizePolicy.Policy, optional
        Vertical size policy for the label.  Defaults to QSizePolicy.Fixed.

    Returns
    -------
    QLabel
        A QLabel instance configured with the specified text, alignment, and
        size policies.
    """
    label = QLabel(text)
    label.setSizePolicy(h_size_policy, v_size_policy)
    if alignment == 'Center':
        label.setAlignment(Qt.AlignCenter)
    elif alignment == 'Right':
        label.setAlignment(Qt.AlignRight)
    else:
        label.setAlignment(Qt.AlignLeft)
    return label


def create_button(name, callback_func, enable=True):
    """
    Create and configure a QPushButton with a click callback and enable state.

    Parameters
    ----------
    name : str
        Text to display on the button.
    callback_func : callable
        Function to invoke when the button is clicked.
    enable : bool, optional
        Whether the button is enabled initially.  Defaults to True.

    Returns
    -------
    QPushButton
        The configured QPushButton instance.
    """
    button = QPushButton(name)
    button.clicked.connect(callback_func)
    button.setEnabled(enable)
    button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return button


def create_combo(name, callback_func=None, items=None, item='', width=None):
    """
    Create a labeled QComboBox.

    Parameters
    ----------
    name : str
        Label text.
    callback_func : callable or None, optional
        Function to connect to the combo's ``currentIndexChanged`` signal.
    items : list of str or None, optional
        Items to populate the combo box.
    item : str, optional
        Initial selected item (must match one of ``items``).
    width : int or None, optional
        Fixed pixel width for the combo box.

    Returns
    -------
    layout : QHBoxLayout
        Layout containing the label and the combo box.
    combo : QComboBox
        The configured combo box widget.
    """
    layout = QHBoxLayout()
    layout.setSpacing(1)
    label = create_label(name, alignment='Right')
    label.setStyleSheet('padding: 0px;')
    layout.addWidget(label)

    combo = QComboBox()
    combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    if width is not None:
        combo.setFixedWidth(width)
    if items:
        combo.addItems(items)
        if item:
            combo.setCurrentText(item)
    if callback_func:
        combo.currentIndexChanged.connect(callback_func)
    layout.addWidget(combo)
    return layout, combo


def sorted_str_list(columns):
    """
    Return sorted string representations of an iterable.

    Converts each value in `columns` to a string and returns them in sorted order.

    Parameters
    ----------
    columns : iterable
        Values to convert to strings and sort.

    Returns
    -------
    list of str
        Sorted list of the string representations of the input values.
    """
    return [str(val) for val in sorted(columns)]


def eval_lvls_energy_diff(E_column):
    df = pd.DataFrame()
    df['E_diff'] = E_column.shift(-1) - E_column
    df['E_diff'] = df['E_diff'].shift(1)
    df.loc[0, 'E_diff'] = 0
    return df['E_diff']


def assign_lvls_y_positions(df, real_size_factor=0.):
    E = list(df['E'])
    N = len(E)
    ys = np.empty(N)
    for n, E_n in enumerate(E):
        ys[n] = (n - E_n) * (1. - real_size_factor) + E_n
    return ys


# =============================================================================
# Pretty headers (HTML, rendered by DataFrameView)
# =============================================================================
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
