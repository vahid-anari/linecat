"""Transition table of the diagram window (a sciwidgets DataFrameView) and its PDF version."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import colors as mcolors
from PySide6.QtCore import QEvent, QItemSelection, QItemSelectionModel, QObject, QTimer, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QAbstractItemView

from sciwidgets.formatting import pretty_sci_text
from sciwidgets.table import DataFrameView

from linecat.diagram.elements import TRANS_COLOR, tex_fontsize_factor

TYPE_NAMES = {'pri': 'Primary', 'sec': 'Secondary'}
TYPE_KEYS = {name: key for key, name in TYPE_NAMES.items()}
COLUMNS = ['Number', 'Type', 'nu', 'tau', 'd_ij']
HEADERS = {
    'Number': 'No.',
    'Type': 'Type',
    'nu': '&nu;<br>(MHz)',
    'tau': '&tau;<br>(s)',
    'd_ij': 'd<sub>ij</sub><br>(D)',
}
FORMATS = {
    'nu': lambda v: f"{float(v):,.4f}",
    'tau': lambda v: pretty_sci_text(float(v), 4),
    'd_ij': lambda v: f"{float(v):.5f}",
}


def row_color(type_key: str) -> str:
    """The row colour of a transition type: its arrow colour at 30 % over white (as in the PDF)."""
    r, g, b = mcolors.to_rgb(TRANS_COLOR[type_key][0])
    return mcolors.to_hex((1 - 0.3 * (1 - r), 1 - 0.3 * (1 - g), 1 - 0.3 * (1 - b)))


def new_table_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def add_row(table_df: pd.DataFrame, type_key: str, number: int, tr) -> None:
    table_df.loc[len(table_df)] = [number, TYPE_NAMES[type_key], tr['nu'], tr['tau'], tr['d_ij (D)']]


def finish_frame(table_df: pd.DataFrame) -> pd.DataFrame:
    """Primary rows first, then secondary, each by number."""
    order = table_df['Type'].map({'Primary': 0, 'Secondary': 1})
    return (table_df.assign(_order=order).sort_values(['_order', 'Number'], kind='stable')
            .drop(columns='_order').reset_index(drop=True))


class TransitionSelection(QObject):
    """Bridge from the figure's hover handler to the table: emits the highlighted (type, number) keys."""

    hovered = Signal(list)


class TransitionTable(DataFrameView):
    """The transitions of one diagram: sortable, rows coloured by type, linked to the arrows.

    ``set_highlighted(keys)`` selects the rows of the given (type, number) keys
    without emitting; ``selectedKeysChanged(keys)`` is emitted when the user
    selects rows.
    """

    selectedKeysChanged = Signal(list)

    def __init__(self, table_df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._same_highlight_inactive()
        self.set_frame(
            table_df[COLUMNS].copy(),
            formats=FORMATS,
            headers=HEADERS,
            alignments={'Number': 'center', 'Type': 'center'},
            row_backgrounds=lambda row: row_color(TYPE_KEYS[row['Type']]),
        )
        self._quiet = False
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _same_highlight_inactive(self) -> None:
        """Rows highlighted from the diagram look the same whether or not the table has focus."""
        palette = self.palette()
        roles = (QPalette.Highlight, QPalette.HighlightedText)
        if all(palette.color(QPalette.Inactive, r) == palette.color(QPalette.Active, r) for r in roles):
            return
        for role in roles:
            palette.setColor(QPalette.Inactive, role, palette.color(QPalette.Active, role))
        self.setPalette(palette)

    def changeEvent(self, event) -> None:
        """After a switch between light and dark mode, the new highlight colours (from the event loop)."""
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            QTimer.singleShot(0, self, self._same_highlight_inactive)

    def natural_width(self) -> int:
        """Width that shows every column without a horizontal scroll bar."""
        return (self.horizontalHeader().length() + self.verticalHeader().sizeHint().width()
                + self.verticalScrollBar().sizeHint().width() + 2 * self.frameWidth() + 2)

    def fit_width(self) -> None:
        """Fix the table's width to its content."""
        self.setFixedWidth(self.natural_width())

    def key_of_row(self, row: int) -> tuple[str, int]:
        record = self.frame().iloc[row]
        return TYPE_KEYS[record['Type']], int(record['Number'])

    def set_highlighted(self, keys) -> None:
        keys = set(keys)
        model = self.model()
        selection = QItemSelection()
        for row in range(model.rowCount()):
            if self.key_of_row(row) in keys:
                selection.select(model.index(row, 0), model.index(row, model.columnCount() - 1))
        self._quiet = True
        try:
            self.selectionModel().select(selection, QItemSelectionModel.ClearAndSelect)
        finally:
            self._quiet = False

    def selected_keys(self) -> list[tuple[str, int]]:
        rows = sorted({index.row() for index in self.selectionModel().selectedRows()})
        return [self.key_of_row(row) for row in rows]

    def _on_selection_changed(self, *_args) -> None:
        if not self._quiet:
            self.selectedKeysChanged.emit(self.selected_keys())


def transition_table_figure(table_df: pd.DataFrame):
    """The transition table drawn by Matplotlib, for the second page of the PDF."""
    df = table_df[COLUMNS].copy()
    keys = df['Type'].map(TYPE_KEYS)
    df['Number'] = df['Number'].map(lambda x: f"${x}$")
    df['Type'] = df['Type'].map(lambda t: rf"$\mathrm{{{t}}}$")
    df['nu'] = df['nu'].map(lambda x: f"${float(x):,.4f}$")
    df['tau'] = df['tau'].map(lambda x: _scientific(float(x), 3))
    df['d_ij'] = df['d_ij'].map(lambda x: f"${x}$")

    m = len(df) + 3.0
    margin = 1. / m
    fig, ax = plt.subplots(figsize=(10, m / 3.), dpi=100)
    fig.subplots_adjust(left=0.05, right=0.95, top=1 - margin, bottom=margin)
    ax.axis("off")
    table = ax.table(
        cellText=df.values,
        colLabels=[r'$\mathbf{Number}$', r'$\mathbf{Type}$', r'$\mathbf{\nu \, (MHz)}$',
                   r'$\mathbf{\tau \, (s)}$', r'$\mathbf{d_{ij} \, (D)}$'],
        loc="center", cellLoc="center", bbox=[0, 0, 1, 1],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12 * tex_fontsize_factor())
    for col in range(len(COLUMNS)):
        table[(0, col)].set_text_props(fontsize=14 * tex_fontsize_factor(), fontweight='bold')
    table.auto_set_column_width(col=list(range(len(COLUMNS))))
    for row, key in enumerate(keys, start=1):
        text = table[row, 2].get_text()
        text.set_ha("right")
        text.set_x(0.95)
        for col in range(len(COLUMNS)):
            table[row, col].set_facecolor(mcolors.to_rgba(TRANS_COLOR[key][0], alpha=0.3))
    return fig


def _scientific(value: float, digits: int) -> str:
    mantissa, exponent = f"{value:.{digits}e}".split('e')
    return fr"${mantissa}\times 10^{{{int(exponent)}}}$"
