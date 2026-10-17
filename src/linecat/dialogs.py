"""Small dialogs of linecat: the large-diagram warning setting and the LaTeX commands of a diagram."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

LARGE_DEFAULT = 50  # transitions; above this linecat asks before drawing a diagram
LARGE_RANGE = (10, 1000)
KEY_ASK = 'view/ask_large_diagram'
KEY_LIMIT = 'view/large_diagram_limit'


def large_diagram_limit(settings: QSettings) -> int | None:
    """Number of transitions above which to ask before drawing, or ``None`` when never asked."""
    if not settings.value(KEY_ASK, True, type=bool):
        return None
    limit = settings.value(KEY_LIMIT, LARGE_DEFAULT, type=int)
    return min(max(limit, LARGE_RANGE[0]), LARGE_RANGE[1])


class LargeDiagramDialog(QDialog):
    """View ▸ Large Diagram Warning…: ask (or not) before drawing more than N transitions."""

    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Large Diagram Warning")
        self._settings = settings
        limit = large_diagram_limit(settings)

        self.ask = QCheckBox("Ask before drawing more than")
        self.ask.setChecked(limit is not None)
        self.limit = QSpinBox()
        self.limit.setRange(*LARGE_RANGE)
        self.limit.setValue(settings.value(KEY_LIMIT, LARGE_DEFAULT, type=int) if limit is None else limit)
        self.limit.setEnabled(self.ask.isChecked())
        self.ask.toggled.connect(self.limit.setEnabled)

        row = QHBoxLayout()
        row.addWidget(self.ask)
        row.addWidget(self.limit)
        row.addWidget(QLabel("transitions"))
        row.addStretch(1)
        note = QLabel("Large diagrams take longer to draw, especially with LaTeX.")
        note.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self._settings.setValue(KEY_ASK, self.ask.isChecked())
        self._settings.setValue(KEY_LIMIT, self.limit.value())
        super().accept()


class LatexCommandsDialog(QDialog):
    """The ``\\DrawLevel``/``\\DrawTr`` commands of a diagram, to copy or save as a ``.tex`` file."""

    def __init__(self, text: str, settings: QSettings, default_name: str = "diagram.tex",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LaTeX Commands")
        self.resize(720, 480)
        self._text = text
        self._settings = settings
        self._default_name = default_name

        self.view = QPlainTextEdit(readOnly=True)
        self.view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.view.setPlainText(text)

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self.copy)
        save_btn = QPushButton("Save…")
        save_btn.clicked.connect(self.save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        close_btn.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.copy_btn)
        buttons.addWidget(save_btn)
        buttons.addSpacing(10)
        buttons.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view, 1)
        layout.addLayout(buttons)

    def copy(self) -> None:
        """Put the commands on the clipboard; the button says "Copied" for a moment."""
        QGuiApplication.clipboard().setText(self._text)
        self.copy_btn.setText("Copied")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy"))

    def save(self, path: str | None = None) -> Path | None:
        """Write the commands to a ``.tex`` file (asks for the name unless ``path`` is given)."""
        if not path:
            folder = self._settings.value('paths/tex_dir', '', type=str)
            path, _ = QFileDialog.getSaveFileName(self, "Save LaTeX Commands",
                                                  str(Path(folder) / self._default_name) if folder
                                                  else self._default_name, "TeX Files (*.tex)")
            if not path:
                return None
        target = Path(path)
        if target.suffix.lower() != ".tex":
            target = target.with_suffix(".tex")
        target.write_text(self._text, encoding="utf-8")
        self._settings.setValue('paths/tex_dir', str(target.parent))
        return target
