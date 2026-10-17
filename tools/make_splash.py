"""Draw the splash image: the CH3OH stick spectrum below 1 THz, from the shipped CDMS files.

Run from the repository root: python tools/make_splash.py
Writes src/linecat/data/icons/app_image.png (2400 x 1350). The app draws the
name and version on top of it at start-up; the left side is kept free for them.
Line heights are the true log intensities (lines within 1.8 decades of the strongest).
"""
import tempfile

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFilter

from linecat.builtin import SOURCES_DIR
from linecat.cdms import convert_molecule_catalog

OUT = "src/linecat/data/icons/app_image.png"
W, H = 2400, 1350
FMAX_GHZ = 1000
YLO, YHI = -4.0, -2.2          # log10 intensity at the baseline and at the top
LINE = (235, 238, 255)
BASELINE = (225, 228, 255)

with tempfile.TemporaryDirectory() as tmp:
    csv = convert_molecule_catalog("CH3OH", outdir=tmp, catalogs_dir=SOURCES_DIR).path
    d = pd.read_csv(csv, usecols=["Frequency (MHz)", "Log Intensity (nm^2 MHz)"])
f = d["Frequency (MHz)"].to_numpy() / 1e3
li = d["Log Intensity (nm^2 MHz)"].to_numpy()
keep = (f <= FMAX_GHZ) & (li > YLO + 0.1)
f, li = f[keep], li[keep]

# deep indigo (bottom-left) to violet (top-right), as in the icon
yy, xx = np.mgrid[0:1:H * 1j, 0:1:W * 1j]
g = (0.55 * xx + 0.45 * (1 - yy))[..., None]
c0, c1, c2 = np.array([18, 12, 52]), np.array([52, 36, 120]), np.array([126, 104, 210])
col = np.where(g < 0.5, c0 + (c1 - c0) * (g / 0.5), c1 + (c2 - c1) * ((g - 0.5) / 0.5))
img = Image.fromarray(col.astype(np.uint8), "RGB").convert("RGBA")

left, right, base, top = 0.40 * W, 0.96 * W, 0.78 * H, 0.14 * H
height = (li - YLO) / (YHI - YLO)
sticks = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(sticks)
for i in np.argsort(height):    # strong lines drawn last, on top
    x = left + f[i] / FMAX_GHZ * (right - left)
    draw.line((x, base, x, base - height[i] * (base - top)), fill=LINE + (int(70 + 185 * height[i]),), width=2)
img = Image.alpha_composite(img, sticks.filter(ImageFilter.GaussianBlur(5)))   # soft glow
img = Image.alpha_composite(img, sticks)

axis = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(axis).line((left - 30, base + 2, right + 10, base + 2), fill=BASELINE + (255,), width=3)
img = Image.alpha_composite(img, axis)
img.convert("RGB").save(OUT)
print(f"-> {OUT}")
