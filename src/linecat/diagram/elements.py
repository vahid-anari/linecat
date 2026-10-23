"""Drawing elements of the energy-level diagram: level lines, transition arrows, level positions."""

from __future__ import annotations

import matplotlib as mpl
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch
from matplotlib.transforms import blended_transform_factory, offset_copy

H_STEPS = {
    'h-large': 1.25,
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


# The diagram's colours in light and dark mode. Light is the printed figure (the PDF is always light);
# dark keeps the hues, with lighter lines and text and dark label boxes, as the sciwidgets plots do.
DIAGRAM_COLORS = {
    False: {
        'face': 'white',
        'ink': 'k',
        'level_selected': 'g',
        'trans': TRANS_COLOR,
        'bbox': BBOX_STYLES,
    },
    True: {
        'face': '#2a2a2a',
        'ink': '#dedede',
        'level_selected': '#5ccf55',
        'trans': {'pri': ['#ec6a5a', '#ffaa9e'], 'sec': ['#749ffb', '#9fdcff']},
        'bbox': {
            'nu_tau_label': dict(BBOX_STYLES['nu_tau_label'], facecolor='#33301a', edgecolor='#ff8c00'),
            'lvl': dict(BBOX_STYLES['lvl'], facecolor='#1b2e1b', edgecolor='#51a34b'),
            'pri-trs': dict(BBOX_STYLES['pri-trs'], facecolor='#4a1f26', edgecolor='#ec6a5a'),
            'sec-trs': dict(BBOX_STYLES['sec-trs'], facecolor='#16324a', edgecolor='#749ffb'),
        },
    },
}


def diagram_colors(dark: bool) -> dict:
    """The colours of the diagram in dark (``True``) or light (``False``) mode."""
    return DIAGRAM_COLORS[bool(dark)]


def set_figure_dark(fig, dark: bool) -> None:
    """Show a diagram figure (made by the diagram window) in dark or light colours, keeping its highlights."""
    colors = diagram_colors(dark)
    fig.set_facecolor(colors['face'])
    for line in getattr(fig, 'level_lines', ()):
        line.set_dark(dark)
    for arrow in getattr(fig, 'diagram_counts', ((),))[0]:
        arrow.set_dark(dark)
    label = getattr(fig, 'hover_label', None)
    if label is not None:
        label.set_color(colors['ink'])
        label.set_bbox(colors['bbox']['nu_tau_label'])
    fig.diagram_dark = bool(dark)



def tex_fontsize_factor():
    if mpl.rcParams['text.usetex']:
        return 1.2
    return 1.


# gap between a level line and its labels, and the free space kept at the figure's edges (points)
LABEL_GAP_PT = 8
EDGE_PAD_PT = 6


def fit_side_margins(fig, level_lines):
    """Set the figure's left and right margins so the level labels and energies fit with a small gap.

    Measured at the figure's current size, with room for a selected label (2 pt larger, boxed); call it again
    whenever the figure is resized (zoom).
    """
    if not level_lines:
        return
    renderer = fig.canvas.get_renderer()
    width = fig.bbox.width
    px = fig.dpi / 72.0
    left = right = 0.0
    for line in level_lines:
        grow = (line.font_size + 2) / line.font_size
        box = (0.3 * (line.font_size + 2) + 2) * px  # bbox pad and edge of a selected label
        left = max(left, line.lvl.get_window_extent(renderer).width * grow + box)
        right = max(right, line.energy.get_window_extent(renderer).width * grow + box)
    gap = (LABEL_GAP_PT + EDGE_PAD_PT) * px
    lo = min(max((left + gap) / width, 0.02), 0.45)
    hi = max(min(1 - (right + gap) / width, 0.98), 0.55)
    params = fig.subplotpars
    if abs(params.left - lo) > 1e-4 or abs(params.right - hi) > 1e-4:
        fig.subplots_adjust(left=lo, right=hi)


def short_number(n):
    """Three significant figures without exponent: 4.56, 45.6, 456."""
    if n < 10:
        return f"{n:.2f}"
    if n < 100:
        return f"{n:.1f}"
    return f"{n:.0f}"


def frequency_parts(nu_mhz):
    """``(value, prefix)`` of a frequency in MHz in kHz, MHz, GHz or THz: 22235.08 -> ("22.2", "G")."""
    if nu_mhz < 1:
        return short_number(nu_mhz * 1e3), "k"
    if nu_mhz < 1e3:
        return short_number(nu_mhz), "M"
    if nu_mhz < 1e6:
        return short_number(nu_mhz / 1e3), "G"
    return short_number(nu_mhz / 1e6), "T"


def lifetime_parts(tau):
    """``(mantissa, exponent)`` of a lifetime in seconds: 3.888e8 -> ("3.89", 8)."""
    mantissa, exponent = f"{tau:.2e}".split("e")
    return mantissa, int(exponent)


def hover_text(nu_mhz, tau):
    """The two-line label shown next to the pointer over a transition."""
    value, prefix = frequency_parts(nu_mhz)
    mantissa, exponent = lifetime_parts(tau)
    return (rf"$\nu = {value}\ \mathrm{{{prefix}Hz}}$" "\n"
            rf"$\tau = {mantissa}\times 10^{{{exponent}}}\ \mathrm{{s}}$")


# smallest readable spacing, as multiples of the text: levels one label height + 25 % apart,
# neighbouring transition circles their own width + 15 % apart
LEVEL_PITCH = 1.25
COLUMN_PITCH = 1.15
DEFAULT_SIZE = (12.0, 6.5)  # inches; small diagrams keep this size


LEVEL_PAD = 0.6  # free space above the top and below the bottom level, in average level spacings


def level_y_limits(ys):
    """y limits of the level axes: the levels plus ``LEVEL_PAD`` average spacings at both ends."""
    pad = LEVEL_PAD * max(ys[-1] - ys[0], 1e-9) / max(len(ys) - 1, 1)
    return ys[0] - pad, ys[-1] + pad


def size_to_content(fig, level_lines, arrows, n_levels, width_units):
    """Make the figure big enough that level labels and transition circles never overlap.

    The figure keeps ``DEFAULT_SIZE`` unless its content needs more: the height gives every level
    one label height (+25 %), the width spreads apart only those circles that would touch at their
    heights. ``fig.legible_fraction`` (width, height) is the smallest zoom at which it stays readable;
    Fit to Window stops there and the diagram scrolls instead.
    """
    renderer = fig.canvas.get_renderer()
    dpi = fig.dpi
    labels = [t for line in level_lines[1:] for t in (line.lvl, line.energy)]
    label_h = max((t.get_window_extent(renderer).height for t in labels), default=0) / dpi
    left = max(line.lvl.get_window_extent(renderer).width for line in level_lines) / dpi
    right = max(line.energy.get_window_extent(renderer).width for line in level_lines) / dpi
    # height: levels 1 data unit apart; the line axes span (n - 1) + 2 LEVEL_PAD units and (n + 1)/(n + 2)
    # of the plotting height (the header row takes the rest); top/bottom margins 0.05 together
    span = max(n_levels - 1, 1) + 2 * LEVEL_PAD
    share = 0.95 * (n_levels + 1) / (n_levels + 2)
    need_h = label_h * LEVEL_PITCH * span / share
    height = max(DEFAULT_SIZE[1], need_h)
    # width: inches per x unit so that circles closer than their size in y are that far apart in x
    font = 12 * tex_fontsize_factor() / 72
    digits = len(str(max(len(arrows), 1)))
    circle = (np.hypot(0.6 * digits * font, font) + 0.6 * font) * COLUMN_PITCH
    y_scale = height * share / span  # inches per y unit
    x_scale = 0.0
    xs = np.array([a.x for a in arrows])
    ys = np.array([a.y_mid for a in arrows]) * y_scale
    for i in range(len(arrows) - 1):
        dx = np.abs(xs[i + 1:] - xs[i])
        near = (np.abs(ys[i + 1:] - ys[i]) < circle) & (dx > 0)
        if near.any():
            x_scale = max(x_scale, circle / dx[near].min())
    gaps = 2 * (LABEL_GAP_PT + EDGE_PAD_PT) / 72 * 1.2
    need_w = x_scale * width_units / 0.95 + (left + right) * 1.15 + gaps
    width = max(DEFAULT_SIZE[0], need_w)
    fig.set_size_inches(width, height)
    fig.legible_fraction = (min(1.0, need_w / width), min(1.0, need_h / height))


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



class LevelLine:
    def __init__(self, ax, lvl_label, e_label, w=0, y=0, header=False, molecule_name="", dark=False):
        self.ax = ax
        self.colors = diagram_colors(dark)
        self.state = (False, None)  # the last selected() call
        self.lvl_label = lvl_label
        self.e_label = e_label
        self.w = w
        self.y = y
        self.header = header
        self.font_size = self.set_font_size()
        transform = blended_transform_factory(ax.transAxes, ax.transData)
        # labels a fixed distance in points from the line ends, so the margins can be fitted to them
        self.lvl = ax.text(0, y, lvl_label,
                           ha="right", va="center",
                           fontsize=self.font_size, color=self.colors['ink'],
                           transform=offset_copy(transform, fig=ax.figure, x=-LABEL_GAP_PT, units='points'))
        self.energy = ax.text(1, y, e_label,
                              ha="left", va="center",
                              fontsize=self.font_size, color=self.colors['ink'],
                              transform=offset_copy(transform, fig=ax.figure, x=LABEL_GAP_PT, units='points'))
        self.name = None
        if header:
            self.name = ax.text(0.5, y, molecule_name,
                                ha="center", va="center",
                                fontsize=self.font_size * 1.5, color=self.colors['ink'],
                                transform=transform)
        if not header:
            self.line, = ax.plot([0, w], [y, y], color=self.colors['ink'], linewidth=1, zorder=0)

    def set_font_size(self):
        font_size = 14 * tex_fontsize_factor()
        if self.header:
            font_size += 2
        return font_size

    def set_dark(self, dark):
        """Dark or light colours; a highlighted level stays highlighted."""
        self.colors = diagram_colors(dark)
        for text in (self.lvl, self.energy, self.name):
            if text is not None:
                text.set_color(self.colors['ink'])
        if not self.header:
            self.selected(*self.state)

    def selected(self, selected, trs=None):
        self.state = (selected, trs)
        bboxes = self.colors['bbox']
        if trs is not None:
            if trs == 'pri':
                bbox = bboxes['pri-trs']
            else:
                bbox = bboxes['sec-trs']
            self.line.set(color=self.colors['trans'][trs][1], linewidth=3, zorder=2)
            self.lvl.set(fontsize=self.font_size + 2, zorder=2)
            self.energy.set(fontsize=self.font_size + 2, zorder=2)
            self.lvl.set_bbox(bbox)
            self.energy.set_bbox(bbox)
        elif selected:
            self.line.set(color=self.colors['level_selected'], linewidth=3, zorder=2)
            self.lvl.set(fontsize=self.font_size + 2, zorder=2)
            self.energy.set(fontsize=self.font_size + 2, zorder=2)
            self.lvl.set_bbox(bboxes['lvl'])
            self.energy.set_bbox(bboxes['lvl'])
        else:
            self.line.set(color=self.colors['ink'], linewidth=1, zorder=0)
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
    def __init__(self, ax, x, y_up, y_down, w, lvl_idx, upper_lvl, lower_lvl, nu, tau, type_, number, dark=False):
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
        self.face = diagram_colors(dark)['face']
        self.color = diagram_colors(dark)['trans'][type_]
        self.is_selected = False
        self.label = hover_text(nu, tau)
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
                fc=self.face, ec=self.color[0],
                lw=1
            )
        )

    def set_dark(self, dark):
        """Dark or light colours; a highlighted arrow stays highlighted."""
        colors = diagram_colors(dark)
        self.face = colors['face']
        self.color = colors['trans'][self.type]
        self.selected(self.is_selected)

    def contain(self, x, y):
        if x is None or y is None:
            return False
        return self.x_left <= x <= self.x_right and self.y_down <= y < self.y_up

    def selected(self, selected):
        self.is_selected = bool(selected)
        if selected:
            self.arrow.set_color(self.color[1])
            self.arrow.set_linewidth(2)
            self.number_text.set(color=self.color[1], fontsize=15)
            self.number_text.set_bbox(
                dict(
                    boxstyle="circle,pad=0.3",
                    fc=self.face, ec=self.color[1],
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
                    fc=self.face, ec=self.color[0],
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

    def make_label_text(self, nu, tau):
        return hover_text(nu, tau)
