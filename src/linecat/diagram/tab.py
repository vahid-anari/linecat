"""One tab of the diagram window: the figures of a selection and their variants (secondary, LaTeX)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from sciwidgets.plot import ScrollableFigure


class DiagramTab:
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
