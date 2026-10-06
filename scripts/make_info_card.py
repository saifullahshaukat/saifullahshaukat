"""
Render a `neofetch`-style info card SVG that sits beside the ASCII portrait:
a terminal title bar, `user@host` header, colored key/value rows and the
classic row of color blocks. Each line fades + slides in on a stagger so the
card "prints" like command output, then holds.

GitHub runs CSS keyframes inside <img>-embedded SVGs (never JS), so all motion
lives in the <style> block below.

The canvas is sized so that at README width 490 it is exactly as tall as the
portrait (840 x 880 canvas) shown at width 370, so the two panels line up.

Edit ROWS to change the content -- the heatmap already covers GitHub stats,
so this card is for who you are and what you work on.

    python scripts/make_info_card.py [info-card.svg]
    STATIC=1 python scripts/make_info_card.py   # frozen frame for previews
"""
import html
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "info-card.svg")
STATIC = bool(os.environ.get("STATIC"))

USER, HOST = "saifullah", "github"

# (key, value). " · " separates items; long values wrap on those separators.
ROWS = [
    ("Role", "Full Stack Developer · Automation Architect · AI Workflow Engineer"),
    ("Now", "Project Manager @ Lead4s LLC"),
    ("Prev", "Lead Web Systems Developer @ Lead Nationwide"),
    ("Uptime", "5+ years · 50+ production systems shipped"),
    ("Stack", "React · Next.js · TypeScript · Node.js · Python · PHP"),
    ("Voice", "Asterisk · FreeSWITCH · Drachtio · WebRTC"),
    ("Infra", "n8n · Docker · Caddy · PostgreSQL · Redis"),
    ("Focus", "Telephony middleware · Voice AI · Self-hosted automation"),
    ("Highlights", "Infra for $1M+/yr operations · ~70% less manual data work"),
    ("Location", "Pakistan"),
]

# ---- geometry -------------------------------------------------------------
PORTRAIT_W, PORTRAIT_H = 840, 880        # make_ascii_svg.py canvas at COLS=180
DISPLAY_PORTRAIT, DISPLAY_CARD = 370, 490  # README <img width=...>
W = 490
H = round(W * (DISPLAY_PORTRAIT * PORTRAIT_H / PORTRAIT_W) / DISPLAY_CARD, 2)

PAD = 20
TITLEBAR_H = 30
FONT = 12
LINE_H = 17
VALUE_X = PAD + 92          # value column (keys up to 10 chars + ": ")
WRAP = 46                   # value chars per line; safe for 0.6em-wide fonts

BG = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#c9d1d9"
KEY = "#22d3ee"
HEAD = "#39d353"
BLOCKS = [  # normal + bright terminal palette, two rows like neofetch
    ["#484f58", "#ff7b72", "#3fb950", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#b1bac4"],
    ["#6e7681", "#ffa198", "#56d364", "#e3b341", "#79c0ff", "#d2a8ff", "#56d4dd", "#ffffff"],
]
BLOCK_W, BLOCK_H = 26, 13

# ---- timing (one-shot) ----------------------------------------------------
START = 0.35
STAGGER = 0.11
LINE_DUR = 0.45


def wrap(value):
    """Greedy-join ' · ' items into WRAP-wide lines; textwrap any oversize item."""
    lines, cur = [], ""
    for item in value.split(" · "):
        for piece in textwrap.wrap(item, WRAP) or [""]:
            cand = f"{cur} · {piece}" if cur else piece
            if len(cand) <= WRAP:
                cur = cand
            else:
                lines.append(cur)
                cur = piece
    lines.append(cur)
    return lines


def value_tspans(line):
    """Mute the ' · ' separators so the items read as a list."""
    out = []
    for i, item in enumerate(line.split(" · ")):
        if i:
            out.append(f'<tspan fill="{MUTED}"> · </tspan>')
        out.append(html.escape(item))
    return "".join(out)


# ---- build the printed lines: (key or None, value markup) ------------------
lines = []
header = (f'<tspan fill="{HEAD}" font-weight="700">{USER}</tspan>@'
          f'<tspan fill="{HEAD}" font-weight="700">{HOST}</tspan>')
lines.append(("__raw__", header))
lines.append(("__raw__", f'<tspan fill="{MUTED}">{"-" * len(USER + "@" + HOST)}</tspan>'))
for key, value in ROWS:
    for i, chunk in enumerate(wrap(value)):
        lines.append((key if i == 0 else None, value_tspans(chunk)))

first_y = TITLEBAR_H + PAD + FONT
blocks_y = first_y + len(lines) * LINE_H - FONT + 8
blocks_end = blocks_y + BLOCK_H * len(BLOCKS)
assert blocks_end <= H - 12, f"card content overflows: {blocks_end} > {H - 12}"

# ---- assemble -------------------------------------------------------------
css = (
    f".l{{opacity:0;animation:in {LINE_DUR}s cubic-bezier(.2,.8,.2,1) both}}"
    "@keyframes in{0%{opacity:0;transform:translateX(-8px)}100%{opacity:1;transform:translateX(0)}}"
    "@media (prefers-reduced-motion: reduce){.l{opacity:1;transform:none;animation:none}}"
)

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:g}" viewBox="0 0 {W} {H:g}" '
    f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="{FONT}">',
    f"<style>{css}</style>",
    f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
    f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
    f'<rect width="{W}" height="{H:g}" rx="12" fill="url(#bg)"/>',
    f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1:g}" rx="12" fill="none" stroke="{FRAME}"/>',
    f'<line x1="0" y1="{TITLEBAR_H}" x2="{W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
]
for i, dot in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
    parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dot}"/>')
parts.append(f'<text x="{W/2:g}" y="{TITLEBAR_H/2 + 4}" fill="{MUTED}" text-anchor="middle">'
             f'{USER}@{HOST}: ~$ neofetch</text>')


def line_group(i, inner):
    if STATIC:
        return f"<g>{inner}</g>"
    return f'<g class="l" style="animation-delay:{START + i * STAGGER:.2f}s">{inner}</g>'


for i, (key, markup) in enumerate(lines):
    y = first_y + i * LINE_H
    if key == "__raw__":
        inner = f'<text x="{PAD}" y="{y}" fill="{INK}">{markup}</text>'
    else:
        inner = ""
        if key:
            inner += f'<text x="{PAD}" y="{y}" fill="{KEY}" font-weight="700">{html.escape(key)}:</text>'
        inner += f'<text x="{VALUE_X}" y="{y}" fill="{INK}">{markup}</text>'
    parts.append(line_group(i, inner))

# neofetch color blocks
for r, row in enumerate(BLOCKS):
    inner = "".join(f'<rect x="{PAD + j * BLOCK_W}" y="{blocks_y + r * BLOCK_H}" width="{BLOCK_W}" '
                    f'height="{BLOCK_H}" fill="{c}"/>' for j, c in enumerate(row))
    parts.append(line_group(len(lines) + r, inner))

parts.append("</svg>")
svg = "".join(parts)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg)
print(f"wrote {OUT}: {W} x {H:g}, {len(lines)} lines, {len(svg)} bytes")
