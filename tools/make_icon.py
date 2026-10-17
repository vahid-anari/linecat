"""Draw the app icon: three energy levels and one transition, as in the diagram window.

Run from the repository root: python tools/make_icon.py
Writes src/linecat/data/icons/app_icon.png (1024 x 1024, transparent corners,
macOS icon grid). Same family as Maxwell Bloch Studio's icon, in indigo.
"""
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = "src/linecat/data/icons/app_icon.png"
S = 1024                      # canvas
SIDE = 824                    # icon body (macOS grid)
OFF = (S - SIDE) // 2
R = int(0.2237 * SIDE)        # corner radius
LEVEL_GLOW = "#c9c2ff"
ARROW = "#ff6b5a"


def background():
    """Deep indigo (bottom-left) to violet (top-right), as in the splash."""
    yy, xx = np.mgrid[0:1:SIDE * 1j, 0:1:SIDE * 1j]
    g = (0.55 * xx + 0.45 * (1 - yy))[..., None]
    c0, c1, c2 = np.array([18, 12, 52]), np.array([52, 36, 120]), np.array([126, 104, 210])
    col = np.where(g < 0.5, c0 + (c1 - c0) * (g / 0.5), c1 + (c2 - c1) * ((g - 0.5) / 0.5))
    return Image.fromarray(col.astype(np.uint8), "RGB").convert("RGBA")


def glow_lines(segments, color, passes, core):
    """Line segments drawn several times, wide and blurred to narrow and sharp."""
    out = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
    for i, (width, blur, alpha) in enumerate(passes):
        layer = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for seg in segments:
            draw.line(seg, fill=core if i == len(passes) - 1 else color, width=width)
        if blur:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        if alpha < 1:
            layer.putalpha(layer.getchannel("A").point(lambda v, a=alpha: int(v * a)))
        out = Image.alpha_composite(out, layer)
    return out


def arrow_head(tip, w, h, color):
    out = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
    x, y = tip
    poly = [(x, y), (x - w / 2, y - h), (x + w / 2, y - h)]
    glow = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
    ImageDraw.Draw(glow).polygon(poly, fill=color)
    out = Image.alpha_composite(out, glow.filter(ImageFilter.GaussianBlur(18)))
    ImageDraw.Draw(out).polygon(poly, fill=color)
    return out


def overlay(alpha_mask, rgb):
    layer = Image.new("RGBA", (SIDE, SIDE), rgb + (0,))
    layer.putalpha(alpha_mask)
    return layer


img = background()
x0, x1 = 0.17 * SIDE, 0.83 * SIDE
levels = [0.27 * SIDE, 0.50 * SIDE, 0.75 * SIDE]
img = Image.alpha_composite(img, glow_lines([(x0, y, x1, y) for y in levels], LEVEL_GLOW,
                                            ((60, 34, 0.5), (30, 14, 0.8), (16, 4, 1.0), (10, 0, 1.0)), "white"))
ax, top, tip = 0.5 * SIDE, levels[0] + 18, levels[2] - 22
img = Image.alpha_composite(img, glow_lines([(ax, top, ax, tip - 70)], ARROW,
                                            ((70, 30, 0.45), (40, 10, 0.9), (30, 0, 1.0)), ARROW))
img = Image.alpha_composite(img, arrow_head((ax, tip), 120, 100, ARROW))

# glossy highlight, light rim on top, dark rim at the bottom (as Studio's icon)
hl = Image.new("L", (SIDE, SIDE), 0)
ImageDraw.Draw(hl).ellipse((-SIDE * 0.3, -SIDE * 0.9, SIDE * 1.3, SIDE * 0.38), fill=34)
img = Image.alpha_composite(img, overlay(hl.filter(ImageFilter.GaussianBlur(90)), (255, 255, 255)))
mask = Image.new("L", (SIDE, SIDE), 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIDE - 1, SIDE - 1), R, fill=255)
rim = np.array(ImageChops.subtract(mask, mask.filter(ImageFilter.GaussianBlur(10))), dtype=float)
up = np.linspace(1, 0, SIDE)[:, None]
img = Image.alpha_composite(img, overlay(Image.fromarray((rim * up * 0.9).astype(np.uint8)), (255, 255, 255)))
img = Image.alpha_composite(img, overlay(Image.fromarray((rim * (1 - up) * 0.8).astype(np.uint8)), (0, 10, 30)))

out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
shadow_mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(shadow_mask).rounded_rectangle((OFF, OFF + 12, OFF + SIDE, OFF + SIDE + 12), R, fill=90)
shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
shadow.putalpha(shadow_mask.filter(ImageFilter.GaussianBlur(18)))
out = Image.alpha_composite(out, shadow)
out.paste(img, (OFF, OFF), mask)
out.save(OUT)
print(f"-> {OUT}")
