"""The pictures and the animation of the linecat docs (``docs/figures``).

    python tools/figures.py                   # everything
    python tools/figures.py diagram --dark    # diagram_dark.png, to check dark mode
    python tools/figures.py --list

Each item starts the app in a fresh process with empty settings (no update
check, no launcher refresh), so your own settings never show. The built-in
catalogs are built on the first run, which takes a little longer. With LaTeX
installed the diagrams are drawn with it, as in the User Guide. How it works:
sciwidgets.devtools (pictures with title bar and shadow on macOS need
``pip install -e ".[dev]"`` and Screen Recording permission for the terminal).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sciwidgets.devtools import Gif, Player, Shot, capture, main

SIZE = (930, 545)
"""Window size of the pictures (the main window and the diagram window)."""


# ------------------------------------------------------------------- starting the app
def linecat() -> int:
    """Start the app like ``linecat`` does, without the splash and the update check."""
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from sciwidgets.style import apply_sci_style

    from linecat.app_info import APP_NAME
    from linecat.builtin import APP_ICON
    from linecat.catalog_window import APP_STYLE_SHEET, CatalogWindow

    app = QApplication([])
    app.setApplicationName("linecat")
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(QIcon(str(APP_ICON)))
    apply_sci_style(app, APP_STYLE_SHEET)
    window = CatalogWindow()
    window.show()
    return app.exec()


# ------------------------------------------------------------------- helpers
def _open(p: Player, species: str, **filters: str) -> Iterator[float]:
    """Open a built-in catalog and set upper-state filters (``J="5"`` is the filter U-S J)."""
    win = p.win
    win.open_builtin(species)
    yield from p.wait_until(lambda: win.df is not None)
    for key, value in filters.items():
        win.filter_combos[f"U-S {key}"].set_value(value)
        win.update_filters()
    path = str(win.catalog_path or "")
    win.status.set_path(path.replace(str(Path.home()), "~"))  # no user name in the pictures
    yield 0.4


def _methanol_diagram(p: Player, secondary: bool = True) -> Iterator[float]:
    """The diagram of the User Guide: CH3OH from 5(1,5), v_t = 0 (three lines), with the secondary
    transitions at 27 % real scale; ``p.win`` becomes the diagram window."""
    yield from _open(p, "CH3OH", J="5", K_a="1", K_c="5", v_t="0")
    main_window = p.win
    main_window.show_button()
    pw = main_window.plot_window
    pw.resize(*SIZE)
    p.win = pw
    yield 1.0
    if secondary:
        pw.menu.set_checked("secondary", True)
        pw.on_menu_action("View", "secondary", True)
        yield 1.0
        pw.coarse_scale_slider.set_value(27)
        pw.change_y_positions(None)
    yield 0.8


def _diagram(p: Player):
    """The figure, its level lines and its arrows in the current tab of the diagram window."""
    comps = p.win.tabs_content[p.win.tabs.currentIndex()].get_comps()
    return comps["fig"], comps["lvls"], comps["arrows"]


def _point(p: Player, fig, x: float, y: float):
    """A point of the figure in display (pixel) coordinates as a point of ``p.win``."""
    from PySide6.QtCore import QPoint, QPointF
    canvas = fig.canvas
    ratio = canvas.device_pixel_ratio
    local = QPoint(round(x / ratio), round(canvas.height() - y / ratio))
    return QPointF(p.win.mapFromGlobal(canvas.mapToGlobal(local)))


def _arrow_point(p: Player, arrow, along: float = 0.7):
    """A point on an arrow, ``along`` of the way from its lower to its upper level."""
    ax = arrow.arrow.axes
    x, y = ax.transData.transform((arrow.x, arrow.y_down + along * (arrow.y_up - arrow.y_down)))
    return _point(p, ax.figure, x, y)


def _level_point(p: Player, level):
    """A point on a level's quantum-number label (left of the line)."""
    fig = level.ax.figure
    box = level.lvl.get_window_extent(fig.canvas.get_renderer())
    return _point(p, fig, (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)


def _hover(p: Player, to, seconds: float = 0.6) -> Iterator[float]:
    """Glide the mouse to a point, moving the pointer over the widgets on the way (hover effects)."""
    from PySide6.QtCore import QEvent, Qt
    for wait in p.move(to, seconds):
        p._send(QEvent.MouseMove, Qt.NoButton, Qt.NoButton)
        yield wait


def _level(lvls, energy: str):
    return next(level for level in lvls if energy in level.e_label)


def _capture_diagram(p: Player, out: Path) -> None:
    """Take the diagram window (the script's ``p.win``) rather than the main window."""
    p.win.raise_()
    p.win.activateWindow()
    p.app.processEvents()
    capture(p.win, out)


# ------------------------------------------------------------------- picture states
def main_window(p: Player) -> Iterator[float]:
    """CH3OH filtered to the transitions from the upper level 5(1,5)."""
    yield from _open(p, "CH3OH", J="5", K_a="1", K_c="5")


def diagram(p: Player) -> Iterator[float]:
    """The diagram window of the User Guide."""
    yield from _methanol_diagram(p)


def hover_arrow(p: Player) -> Iterator[float]:
    """The pointer over primary transition 1: the arrow, its levels and its table row light up."""
    yield from _methanol_diagram(p)
    _fig, _lvls, arrows = _diagram(p)
    first = next(a for a in arrows if a.type == "pri" and a.number == 1)
    yield from _hover(p, _arrow_point(p, first, 0.62))
    yield 0.6


def hover_level(p: Player) -> Iterator[float]:
    """The pointer over the level 4(1,4): every transition from or to it lights up."""
    yield from _methanol_diagram(p)
    _fig, lvls, _arrows = _diagram(p)
    yield from _hover(p, _level_point(p, _level(lvls, "26.10")))
    yield 0.6


def molecule_docs(p: Player) -> Iterator[float]:
    """The Molecule box of the OH catalog with its Documentation menu open."""
    from PySide6.QtCore import QTimer
    yield from _open(p, "OH")
    button = p.win.molecule_box.docs_button
    yield from p.move(p.at(button), 0.3)
    QTimer.singleShot(0, button.showMenu)  # the menu runs its own event loop; the script goes on
    yield 0.8


def _capture_molecule_box(p: Player, out: Path) -> None:
    """The Molecule box and the open menu below it, cut out of the window."""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QApplication
    from sciwidgets.devtools import _composite
    win, box = p.win, p.win.molecule_box
    image = _composite(win)
    area = QRect(box.mapTo(win, QPoint(0, 0)), box.size())
    menu = QApplication.activePopupWidget()
    if menu is not None:
        area = area.united(QRect(win.mapFromGlobal(menu.mapToGlobal(QPoint(0, 0))), menu.size()))
    area = area.adjusted(-8, -8, 8, 8).intersected(win.rect())
    ratio = image.devicePixelRatio()
    image.copy(QRect(area.topLeft() * ratio, area.size() * ratio)).save(str(out))


# ------------------------------------------------------------------- animation
def tour(p: Player) -> Iterator[float]:
    """Hover over transitions and a level, show the secondary transitions, real scale, then dark mode."""
    # opened before the first frame, so the whole animation shows the diagram window
    for _ in _methanol_diagram(p, secondary=False):
        pass
    pw = p.win
    yield 0.8
    _fig, lvls, arrows = _diagram(p)
    for number in (1, 2):
        arrow = next(a for a in arrows if a.type == "pri" and a.number == number)
        yield from _hover(p, _arrow_point(p, arrow, 0.6), 0.7)
        yield 1.0
    yield from p.open_menu("View")
    yield from p.choose("Secondary Transitions")
    yield 1.0
    yield from p.drag_slider(pw.coarse_scale_slider, 27, 1.2)
    yield 0.6
    _fig, lvls, arrows = _diagram(p)
    yield from _hover(p, _level_point(p, _level(lvls, "26.10")), 0.8)
    yield 1.2
    yield from p.open_menu("View")
    yield from p.choose("Appearance")
    yield from p.choose("Dark")
    yield 1.0
    arrow = next(a for a in arrows if a.type == "sec" and a.number == 2)
    yield from _hover(p, _arrow_point(p, arrow, 0.5), 0.8)
    yield 1.2


SHOTS = {
    "main_window": Shot(linecat, main_window, size=SIZE),
    "diagram": Shot(linecat, diagram, capture=_capture_diagram),
    "hover_arrow": Shot(linecat, hover_arrow, capture=_capture_diagram),
    "hover_level": Shot(linecat, hover_level, capture=_capture_diagram),
    "molecule_docs": Shot(linecat, molecule_docs, capture=_capture_molecule_box),
}

GIFS = {
    "tour": Gif(linecat, tour, width=900),
}

if __name__ == "__main__":
    raise SystemExit(main(SHOTS, GIFS))
