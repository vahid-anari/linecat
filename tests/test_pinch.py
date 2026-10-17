"""Pinch zoom, ⌘ + wheel zoom and two-finger double tap in the diagram window (0.11.0)."""

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QNativeGestureEvent, QPointingDevice, QWheelEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture
def diagram(window, qapp):
    window.filter_combos["U-S J"].set_value("3/2")
    window.update_filters()
    window.on_menu_action("Transitions", "show_diagram", False)
    pw = window.plot_window
    pw.resize(1300, 900)
    for _ in range(5):
        qapp.processEvents()
    yield pw
    pw.close()


def _pinch(canvas, value, gesture=Qt.ZoomNativeGesture):
    pos = QPointF(canvas.width() / 2, canvas.height() / 3)
    event = QNativeGestureEvent(gesture, QPointingDevice.primaryPointingDevice(), 2, pos, pos,
                                QPointF(canvas.mapToGlobal(pos.toPoint())), value, QPointF(0, 0))
    QApplication.sendEvent(canvas, event)


def test_pinch_zooms_both_ways_and_ends_fit(diagram):
    tab = diagram.tabs_content[0]
    assert tab.fit
    h0, v0 = tab.scroll.zoom()
    _pinch(tab.scroll.canvas, 0.25)
    h1, v1 = tab.scroll.zoom()
    assert h1 == pytest.approx(h0 * 1.25) and v1 == pytest.approx(v0 * 1.25)
    assert not tab.fit and not diagram.fit_checkbox.isChecked() and diagram.hori_zoom_slider.isEnabled()
    assert diagram.hori_zoom_slider.get_value() == round(h1 * 100)
    assert tab.get_comps()['zoom factor'] == [h1, v1]


def test_pinch_stops_at_the_slider_limits(diagram):
    tab = diagram.tabs_content[0]
    for _ in range(40):
        _pinch(tab.scroll.canvas, -0.5)
    assert tab.scroll.zoom() == pytest.approx((0.1, 0.1))
    for _ in range(40):
        _pinch(tab.scroll.canvas, 1.0)
    assert tab.scroll.zoom() == pytest.approx((3.0, 6.0))


def test_double_tap_fits_again(diagram):
    tab = diagram.tabs_content[0]
    _pinch(tab.scroll.canvas, 0.5)
    assert not tab.fit
    _pinch(tab.scroll.canvas, 0.0, Qt.SmartZoomNativeGesture)
    assert tab.fit and diagram.fit_checkbox.isChecked()


def test_command_wheel_zooms_plain_wheel_scrolls(diagram):
    tab = diagram.tabs_content[0]
    canvas = tab.scroll.canvas
    pos = QPointF(10, 10)

    def wheel(modifiers):
        event = QWheelEvent(pos, QPointF(canvas.mapToGlobal(pos.toPoint())), QPoint(0, 0), QPoint(0, 120),
                            Qt.NoButton, modifiers, Qt.NoScrollPhase, False)
        QApplication.sendEvent(canvas, event)

    before = tab.scroll.zoom()
    wheel(Qt.NoModifier)
    assert tab.scroll.zoom() == before and tab.fit                       # plain wheel: scrolling only
    wheel(Qt.ControlModifier)
    assert tab.scroll.zoom()[0] == pytest.approx(before[0] * 1.0015 ** 120) and not tab.fit


def test_pinch_keeps_the_point_under_the_fingers(diagram):
    tab = diagram.tabs_content[0]
    _pinch(tab.scroll.canvas, 1.0)                                      # big enough to scroll both ways
    viewport = tab.scroll.viewport()
    hbar, vbar = tab.scroll.horizontalScrollBar(), tab.scroll.verticalScrollBar()
    hbar.setValue(hbar.maximum() // 2)
    vbar.setValue(vbar.maximum() // 2)
    anchor = QPoint(viewport.width() // 3, viewport.height() // 3)
    h0, v0 = tab.scroll.zoom()
    fx = (hbar.value() + anchor.x()) / tab.scroll.canvas.width()        # fraction of the diagram under it
    fy = (vbar.value() + anchor.y()) / tab.scroll.canvas.height()
    tab.zoom_by(1.2, anchor)
    assert (hbar.value() + anchor.x()) / tab.scroll.canvas.width() == pytest.approx(fx, abs=0.01)
    assert (vbar.value() + anchor.y()) / tab.scroll.canvas.height() == pytest.approx(fy, abs=0.01)
