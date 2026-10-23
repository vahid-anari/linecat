"""The "Molecule" box of the main window: picture, name, CDMS tags, Q, number of lines, documentation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QMenu, QToolButton, QVBoxLayout, QWidget

from sciwidgets.labels import MathLabel

from linecat.builtin import molecule_docs, molecule_image
from linecat.molecules import MoleculeInfo
from linecat.widgets import GROUPBOX_MARGIN

PICTURE_SIZE = 110
BOX_WIDTH = 310  # fixed, so the filters don't move when another molecule is opened
NAME_HEIGHT = 34


def cdms_tags(info: MoleculeInfo) -> list[str]:
    """CDMS species tags of the molecule's entries, from its .cat file names (c017507.cat → 017507)."""
    tags = []
    for file in info.input_files:
        stem = Path(file).stem.split("-")[0]
        tags.append(stem[1:] if stem[:1].lower() == "c" else stem)
    return tags


def open_file(path: Path) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class MoleculeBox(QGroupBox):
    """Shows the loaded molecule; a grey placeholder until a catalog is open."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Molecule", parent)
        self.setFixedWidth(BOX_WIDTH)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*GROUPBOX_MARGIN)

        # picture on the left
        self.picture = QSvgWidget()
        self.picture.setFixedSize(QSize(PICTURE_SIZE, PICTURE_SIZE))
        layout.addWidget(self.picture, alignment=Qt.AlignVCenter)
        layout.addSpacing(10)

        # name, details and documentation on the right, left-aligned
        right = QVBoxLayout()
        right.setSpacing(4)
        # the name sits in a holder of fixed height, so the box keeps its size with no catalog
        self.name_holder = QWidget()
        self.name_holder.setFixedHeight(NAME_HEIGHT)
        holder_layout = QVBoxLayout(self.name_holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        self.name = MathLabel("", font_size=20, fix_size=True)
        holder_layout.addWidget(self.name, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        right.addWidget(self.name_holder)

        self.details = QLabel()
        self.details.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # room for four lines (tags may take two), so the box never changes height
        self.details.setFixedHeight(4 * self.details.fontMetrics().lineSpacing() + 4)
        right.addWidget(self.details)

        self.docs_menu = QMenu(self)
        self.docs_button = QToolButton()
        self.docs_button.setText("Documentation")
        self.docs_button.setToolTip("The CDMS documentation of this molecule's catalog entries")
        self.docs_button.setPopupMode(QToolButton.InstantPopup)
        self.docs_button.setMenu(self.docs_menu)
        right.addWidget(self.docs_button, alignment=Qt.AlignLeft)
        right.addStretch(1)
        layout.addLayout(right, 1)

        self.info: MoleculeInfo | None = None
        self.clear()

    def clear(self) -> None:
        """No catalog loaded."""
        self.info = None
        self.picture.load(b"")
        self.name.set_text("")
        self.details.setText("No catalog loaded")
        self.details.setEnabled(False)  # grey, in light and dark mode
        self.docs_menu.clear()
        self.docs_button.setEnabled(False)

    def set_molecule(self, info: MoleculeInfo, n_lines: int) -> None:
        """Show ``info`` and the number of lines of the loaded catalog."""
        self.info = info
        image = molecule_image(info.species)
        if image is not None:
            self.picture.load(str(image))
            self.picture.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        else:
            self.picture.load(b"")
        # a new label each time, so it follows the "Use LaTeX for Labels" setting
        old = self.name
        self.name = MathLabel(info.latex_name.strip("$"), font_size=20, fix_size=True)
        self.name_holder.layout().replaceWidget(old, self.name)
        old.deleteLater()
        tags = cdms_tags(info)
        tag_line = f"CDMS tags<br>{', '.join(tags)}" if len(tags) > 1 else f"CDMS tag {tags[0]}"
        self.details.setEnabled(True)
        self.details.setText(
            f"{tag_line}<br>"
            f"Q({info.T:g} K) = {info.Q:,.2f}<br>"
            f"{n_lines:,} lines"
        )
        self.docs_menu.clear()
        for path in molecule_docs(info.species):
            self.docs_menu.addAction(path.stem, lambda p=path: open_file(p))
        self.docs_button.setEnabled(not self.docs_menu.isEmpty())
