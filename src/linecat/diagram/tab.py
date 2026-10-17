"""One tab of the diagram window: the figures of a selection and their variants (secondary, LaTeX)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from sciwidgets.plot import ScrollableFigure

from linecat.diagram.table import TransitionTable

# zoom limits while fitting: below 50 % the labels get too small, so the diagram scrolls instead
FIT_MIN, FIT_MAX = 0.5, 3.0


class _ResizeWatcher(QObject):
    """Calls ``callback`` whenever the watched widget is resized."""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize:
            self._callback()
        return False


class DiagramTab:
    def __init__(self, fig, ax, latex_txt, lvls, arrows, lvls_df, trs_df, table_df, selection):
        self.comps_dict = {
            'pri': {
                'fig': fig,
                'table df': table_df,
                'ax': ax,
                'scroll': ScrollableFigure(fig),
                'table_scroll': self._make_table(table_df, selection, fig, arrows, lvls),
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
        # transition table on the left at the width of its content, diagram on the right
        self.row = QHBoxLayout()
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.addWidget(self.table_scroll, 0)
        self.row.addWidget(self.scroll, 1)
        self.layout.addLayout(self.row)

        self.comps_exist = {
            'pri': 1,
            'sec': 0,
            'pri-latex': 0,
            'sec-latex': 0,
        }
        self.use_latex_checkbox = False
        self.sec_trs_checkbox = False
        # Fit to Window: the zoom follows the space beside the table; on_fitted(h, v) reports the new zoom
        self.fit = True
        self.on_fitted = None
        self._watcher = _ResizeWatcher(self.apply_fit)
        self.scroll.viewport().installEventFilter(self._watcher)

    def comps_dict_name(self):
        if self.sec_trs_checkbox:
            name = 'sec'
        else:
            name = 'pri'
        if self.use_latex_checkbox:
            name += '-latex'
        return name

    @staticmethod
    def _make_table(table_df, selection, fig, arrows, lvls):
        """The transition table of one diagram, linked both ways to its arrows."""
        table = TransitionTable(table_df)
        selection.hovered.connect(table.set_highlighted)

        def highlight(keys):
            keys = set(keys)
            for lvl in lvls:
                lvl.selected(False)
            for arrow in arrows:
                chosen = (arrow.type, arrow.number) in keys
                arrow.selected(chosen)
                if chosen:
                    idx_up, idx_down = arrow.lvl_idx
                    lvls[idx_up].selected(True, trs=arrow.type)
                    lvls[idx_down].selected(True, trs=arrow.type)
            fig.canvas.draw_idle()

        table.selectedKeysChanged.connect(highlight)
        table.fit_width()
        table.configChanged.connect(lambda _config: table.fit_width())  # font or columns changed
        table._selection_bridge = selection  # keep the QObject alive with the table
        return table

    def add_comps(self, fig, ax, latex_txt, lvls, arrows, lvls_df, trs_df, table_df, selection):
        dict_name = self.comps_dict_name()
        self.comps_dict[dict_name] = {
            'fig': fig,
            'table df': table_df,
            'ax': ax,
            'scroll': ScrollableFigure(fig),
            'table_scroll': self._make_table(table_df, selection, fig, arrows, lvls),
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
        self.comps_dict[dict_name]['scroll'].viewport().installEventFilter(self._watcher)

    def apply_fit(self):
        """Zoom the shown diagram to the space it has, if Fit to Window is on and it is laid out."""
        if not self.fit or not self.scroll.isVisible():
            return
        viewport = self.scroll.viewport()
        avail_w, avail_h = viewport.width(), viewport.height()
        canvas_w, canvas_h = self.scroll.canvas_size()
        zoom_h, zoom_v = self.scroll.zoom()
        if avail_w < 50 or avail_h < 50 or canvas_w <= 0 or canvas_h <= 0:
            return
        # never squeeze below the size at which labels and transition circles stay apart
        min_h, min_v = getattr(self.scroll.figure, "legible_fraction", (FIT_MIN, FIT_MIN))
        h = min(FIT_MAX, max(FIT_MIN, min_h, avail_w / (canvas_w / zoom_h)))
        v = min(FIT_MAX, max(FIT_MIN, min_v, avail_h / (canvas_h / zoom_v)))
        h, v = int(h * 100) / 100, int(v * 100) / 100  # whole percents, rounded down so nothing overflows
        if (h, v) != (round(zoom_h, 2), round(zoom_v, 2)):
            self.get_comps_ref()['zoom factor'][:] = [h, v]
            self.scroll.set_zoom(h, v)
        if self.on_fitted is not None:
            self.on_fitted(self, h, v)

    def get_comps_ref(self):
        return self.comps_dict[self.comps_dict_name()]

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
        if self.table_scroll is not old_table:
            self.row.replaceWidget(old_table, self.table_scroll)
            old_table.hide()
            self.table_scroll.show()
        if self.scroll is not old_scroll:
            self.row.replaceWidget(old_scroll, self.scroll)
            old_scroll.hide()
            self.scroll.show()

    def figures(self):
        for comps in self.comps_dict.values():
            yield comps['fig']
