"""App style sheet and small widget helpers shared by the windows."""

from __future__ import annotations

import shutil
from contextlib import contextmanager

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from sciwidgets.params import FloatSlider, IntSlider, SliderFeature

NATIVE_MENU_BAR = False  # menus inside each window (on macOS the global bar would otherwise be used)

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



def latex_available() -> bool:
    """Return True when a ``latex`` executable is on the PATH."""
    return shutil.which("latex") is not None



@contextmanager
def busy(window=None, message=None):
    """Wait cursor (and a busy status-bar message) while a slow step runs on the GUI thread.

    The status bar is repainted directly: running the event loop here (processEvents) also runs
    pending deletions in the middle of a build, which crashed the tests on Python 3.10.
    """
    QApplication.setOverrideCursor(Qt.WaitCursor)
    if window is not None and message:
        window.status.set_state(message, busy=True)
        window.statusBar().repaint()
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def make_slider(label, min_val, max_val, init_val, val_fmt=None):
    """Percent slider without range labels or context menu (zoom and scale controls); upright name."""
    name = rf"\mathrm{{{label}}}"
    if isinstance(min_val, float):
        return FloatSlider(name, min_val, max_val, unit=r"\%", init_val=init_val, val_fmt=val_fmt or "{:.2f}",
                           show_range=False, features=SliderFeature.NONE)
    return IntSlider(name, min_val, max_val, unit=r"\%", init_val=init_val, show_range=False,
                     features=SliderFeature.NONE)


def align_widgets(widgets):
    """Give sciwidgets parameter widgets a common name width and value width, kept up to date."""
    widgets = list(widgets)

    def realign(*_args):
        names = max(w.get_name_width() for w in widgets)
        values = max(w.get_value_width() for w in widgets)
        for w in widgets:
            w.set_name_width(names)
            w.set_value_width(values)

    for w in widgets:
        w.nameWidthChanged.connect(realign)
        w.valueWidthChanged.connect(realign)
    realign()


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
