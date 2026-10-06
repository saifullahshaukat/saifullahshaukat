"""
Prepare a portrait photo for clean ASCII conversion:
  1. remove the background (rembg) so only the subject is left
  2. boost local contrast with CLAHE (contrast-limited adaptive histogram
     equalization) so the face gets real highlights and shadows instead of a
     flat mid-gray that turns into uniform `::::` at ascii resolution
  3. stretch tones over the subject so the brightest skin lands near white
  4. composite onto pure white (white -> blank ascii) and crop square around
     the subject

Output: source-prepped.png (grayscale + cutout alpha), consumed by make_ascii_svg.py.
Run once per photo change (local only -- CI never needs rembg/opencv).

    python scripts/prep_photo.py <input.jpg> [output.png]
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image
from rembg import remove

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.jpg")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

UPSCALE = 2           # small avatars (460px) get resampled up before filtering
CLAHE_CLIP = 2.2      # higher = punchier local contrast (and more noise)
CLAHE_TILES = 8
TONE_PCT = (2, 97)    # subject luminance percentiles mapped to black / white
CROP_PAD = 0.06       # breathing room around the subject, as a fraction of side

# 1. cut out the subject
src = Image.open(INP).convert("RGBA")
if UPSCALE != 1:
    src = src.resize((src.width * UPSCALE, src.height * UPSCALE), Image.LANCZOS)
cut = remove(src)
rgb = np.array(cut.convert("RGB"))
alpha = np.array(cut.split()[-1])                 # 0 = background
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

# 2. local contrast
gray = cv2.bilateralFilter(gray, 7, 30, 7)        # knock down jpeg/skin noise first
clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(CLAHE_TILES, CLAHE_TILES))
local = clahe.apply(gray)

# 3. tone stretch over the subject only
lo, hi = np.percentile(local[alpha > 128], TONE_PCT)
tone = np.clip((local.astype(np.float32) - lo) / max(hi - lo, 1), 0, 1) * 255

# 4. paste onto white (feathered a hair to avoid a halo), square crop
mask = cv2.GaussianBlur(alpha.astype(np.float32) / 255.0, (0, 0), 1.5)
out = tone * mask + 255.0 * (1.0 - mask)

ys, xs = np.where(alpha > 20)
side = int(max(xs.max() - xs.min(), ys.max() - ys.min()) * (1 + CROP_PAD))
cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
canvas = np.full((side, side), 255, np.uint8)
x0, y0 = cx - side // 2, cy - side // 2
sx0, sy0 = max(x0, 0), max(y0, 0)
sx1, sy1 = min(x0 + side, out.shape[1]), min(y0 + side, out.shape[0])
canvas[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = out[sy0:sy1, sx0:sx1].astype(np.uint8)

# keep the cutout mask as alpha so make_ascii_svg.py can blank the background
# without relying on "white == empty" (which also eats bright skin)
mask_canvas = np.zeros((side, side), np.uint8)
mask_canvas[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = (mask[sy0:sy1, sx0:sx1] * 255).astype(np.uint8)

Image.merge("LA", [Image.fromarray(canvas), Image.fromarray(mask_canvas)]).save(OUT)
print("wrote", OUT, canvas.shape)
