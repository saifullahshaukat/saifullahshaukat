"""
Convert a portrait photo into a CLEAN, monochrome ASCII-art SVG (one light-gray
color, subject isolated on a dark background) that "types" itself in like a
terminal, then holds.

Monochrome is deliberate -- per-character rainbow color is what makes ASCII
portraits look noisy. One fill color + a good density ramp + high contrast (so a
busy background washes out to blank) reads as neat and legible.

GitHub renders SVGs embedded via <img> and runs their SMIL animations there (JS
does not run). Each row is revealed with a left-to-right clip wipe plus a small
block cursor riding the wipe edge, staggered top -> bottom, so the whole
portrait prints once and freezes.

    python scripts/make_ascii_svg.py [source-prepped.png] [saifullah-ascii.svg]
    STATIC=1 python scripts/make_ascii_svg.py   # frozen frame for previews
"""
from PIL import Image, ImageEnhance, ImageFilter
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# defaults to the prepped grayscale image (see prep_photo.py), which already has
# the background removed + local contrast applied.
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-prepped.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "saifullah-ascii.svg")

USER = "saifullah"
NAME = "Saifullah Shaukat"

# more columns = more detail (eyes need ~6+ chars across to read). the art
# stays ART_W px wide either way; cells shrink, keeping a ~1:1.875 char aspect.
COLS = int(os.environ.get("COLS", 180))
ART_W_TARGET = 800
CELL_W = ART_W_TARGET / COLS
CELL_H = CELL_W * 15 / 8
ROWS = round(COLS * 8 / 15)
RAMP = " .`:-=+*cs#%@"  # bright(sparse) -> dark(dense); leading space clears bg

# POSITIVE: bright pixels print dense (bright) glyphs, so the face reads like the
# photo on the dark terminal. 0 = the classic negative mapping (dark -> dense),
# which suits flat illustrations but turns a real face into a hard-to-read
# negative. Either way the background is blanked by the cutout alpha.
POSITIVE = os.environ.get("POSITIVE", "1") != "0"

# the prepped image already has bg removed + CLAHE local contrast; these were
# tuned by eye at the README's 370px display width.
CONTRAST = float(os.environ.get("CONTRAST", 1.3))
BRIGHTNESS = 1.0
GAMMA = float(os.environ.get("GAMMA", 1.3))      # >1 darkens mids (positive) / brightens (negative)
SHARPEN = True
WHITE_FLOOR = float(os.environ.get("WHITE_FLOOR", 0.80))  # negative mode: luminance above -> blank

PAD = 20
TITLEBAR_H = 30
STATUS_H = 30
ART_W = COLS * CELL_W
ART_H = ROWS * CELL_H
CANVAS_W = ART_W + PAD * 2
CANVAS_H = TITLEBAR_H + ART_H + STATUS_H + PAD

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
TITLE_TEXT = "#7d8590"
INK = "#c9d1d9"      # the single ascii color
CURSOR = "#c9d1d9"

# ---- reveal timing (one-shot; a cursor rasters top -> bottom) -------------
ROW_DUR = 5.8 / ROWS  # whole portrait prints in ~6s at any resolution
STAGGER = ROW_DUR       # == ROW_DUR -> a single cursor sweeping down

# ---- 1. sample the image into a COLS x ROWS grayscale grid ----------------
src = Image.open(SRC)
alpha = src.getchannel("A") if "A" in src.getbands() else None
im = src.convert("L")                           # grayscale
if SHARPEN:
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=140, threshold=2))
im = ImageEnhance.Brightness(im).enhance(BRIGHTNESS)
im = ImageEnhance.Contrast(im).enhance(CONTRAST)
im = im.resize((COLS, ROWS), Image.LANCZOS)
px = im.load()
ax = alpha.resize((COLS, ROWS), Image.LANCZOS).load() if alpha else None

STATIC = bool(os.environ.get("STATIC"))  # emit frozen state for previews

rows_txt = []
for y in range(ROWS):
    chars = []
    for x in range(COLS):
        if ax is not None and ax[x, y] < 128:
            chars.append(" ")                   # background
            continue
        lum = px[x, y] / 255.0
        lum = pow(lum, GAMMA)
        if POSITIVE:
            # subject never drops to blank, so dark hair still outlines the head
            idx = max(1, int(lum * (len(RAMP) - 1) + 0.5))
        elif lum >= WHITE_FLOOR:
            chars.append(" ")
            continue
        else:
            idx = int((1.0 - lum) * (len(RAMP) - 1) + 0.5)
        chars.append(RAMP[max(0, min(len(RAMP) - 1, idx))])
    rows_txt.append("".join(chars))

art_top = TITLEBAR_H + PAD * 0.35

# ---- 2. assemble SVG ------------------------------------------------------
parts = []
parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W:g}" height="{CANVAS_H:g}" '
    f'viewBox="0 0 {CANVAS_W:g} {CANVAS_H:g}" font-family="ui-monospace, SFMono-Regular, '
    f'Menlo, Consolas, monospace">'
)
parts.append('<defs>'
             f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/>'
             f'</linearGradient></defs>')

parts.append(f'<rect width="{CANVAS_W:g}" height="{CANVAS_H:g}" rx="12" fill="url(#bg)"/>')
parts.append(f'<rect x="0.5" y="0.5" width="{CANVAS_W-1:g}" height="{CANVAS_H-1:g}" rx="12" '
             f'fill="none" stroke="{FRAME}" stroke-width="1"/>')

parts.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{CANVAS_W:g}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>')
for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
    parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
parts.append(f'<text x="{CANVAS_W/2:g}" y="{TITLEBAR_H/2 + 4}" fill="{TITLE_TEXT}" font-size="12" '
             f'text-anchor="middle">{USER}@github: ~$ ./portrait.sh</text>')

# one <text> per row (single color -> no per-char markup, tiny file)
font_size = CELL_H * 0.86
for ry, line in enumerate(rows_txt):
    if not line.strip():
        continue  # blank rows draw nothing; skip their clip/cursor markup too
    y = art_top + ry * CELL_H + CELL_H * 0.74
    row_y = art_top + ry * CELL_H
    delay = ry * STAGGER
    safe = html.escape(line)
    text = (f'<text xml:space="preserve" x="{PAD}" y="{y:.1f}" fill="{INK}" '
            f'font-size="{font_size:.1f}" textLength="{ART_W:g}" lengthAdjust="spacing">{safe}</text>')

    if STATIC:
        parts.append(text)
        continue

    parts.append(
        f'<clipPath id="r{ry}"><rect x="{PAD}" y="{row_y:.1f}" height="{CELL_H:.2f}" width="0">'
        f'<animate attributeName="width" from="0" to="{ART_W:g}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/></rect></clipPath>'
    )
    parts.append(f'<g clip-path="url(#r{ry})">{text}</g>')
    parts.append(
        f'<rect y="{row_y+1:.1f}" width="{CELL_W:.2f}" height="{CELL_H-2:.2f}" fill="{CURSOR}" opacity="0">'
        f'<animate attributeName="x" from="{PAD}" to="{PAD+ART_W:g}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0.85" begin="{delay:.3f}s"/>'
        f'<set attributeName="opacity" to="0" begin="{delay+ROW_DUR:.3f}s"/></rect>'
    )

# status bar with a steady blinking cursor
status_line_y = TITLEBAR_H + ART_H + PAD * 0.35
status_y = status_line_y + 19
prompt = f"{USER}@github:~$ whoami "
parts.append(f'<line x1="0" y1="{status_line_y:.1f}" x2="{CANVAS_W:g}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>')
parts.append(f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
             f'{prompt}<tspan fill="{INK}">{NAME}</tspan></text>')
status_chars = len(prompt + NAME + " ")   # cursor sits after the name
parts.append(f'<rect x="{PAD + status_chars * 13 * 0.6:.1f}" y="{status_y-12:.1f}" width="8" height="14" fill="{INK}">'
             f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
             f'dur="1s" repeatCount="indefinite"/></rect>')

parts.append("</svg>")
svg = "".join(parts)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)
print("wrote", OUT, len(svg), "bytes;", f"{CANVAS_W:g} x {CANVAS_H:g}")
