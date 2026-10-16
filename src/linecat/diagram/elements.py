"""Drawing elements of the energy-level diagram: level lines, transition arrows, level positions."""

from __future__ import annotations

import matplotlib as mpl
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch
from matplotlib.transforms import blended_transform_factory

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



def tex_fontsize_factor():
    if mpl.rcParams['text.usetex']:
        return 1.2
    return 1.


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
