#!/usr/bin/env python3
"""Render asciinema cast stdout to a PNG terminal screenshot."""
import json, sys
from PIL import Image, ImageDraw, ImageFont

cast_path, png_path = sys.argv[1], sys.argv[2]
lines = open(cast_path, encoding="utf-8").read().splitlines()
header = json.loads(lines[0])
cols = int(header.get("width") or 100)
rows = int(header.get("height") or 28)
blob = []
for L in lines[1:]:
    try:
        ev = json.loads(L)
    except Exception:
        continue
    if isinstance(ev, list) and len(ev) >= 3 and ev[1] == "o":
        blob.append(ev[2])
text = "".join(blob).replace("\r\n", "\n").replace("\r", "\n")
# Expand tabs, keep last `rows` lines that fit
raw_lines = text.split("\n")
# Soft-wrap long lines
wrapped = []
for line in raw_lines:
    while len(line) > cols:
        wrapped.append(line[:cols])
        line = line[cols:]
    wrapped.append(line)
# Prefer showing the end (results), but keep header if possible
if len(wrapped) > rows:
    # Keep first 8 lines (header+curl) + last rows-8
    keep_head = min(8, rows // 3)
    wrapped = wrapped[:keep_head] + ["…"] + wrapped[-(rows - keep_head - 1) :]
wrapped = wrapped[:rows]
while len(wrapped) < rows:
    wrapped.append("")

# Font
font = None
for fp in (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
):
    try:
        font = ImageFont.truetype(fp, 15)
        break
    except Exception:
        pass
if font is None:
    font = ImageFont.load_default()

# Measure
bbox = font.getbbox("M")
cw, ch = bbox[2] - bbox[0], bbox[3] - bbox[1]
line_h = ch + 4
pad = 16
W = pad * 2 + cw * cols
H = pad * 2 + line_h * rows
img = Image.new("RGB", (W, H), (30, 30, 30))
draw = ImageDraw.Draw(img)
fg = (220, 220, 220)
accent = (120, 200, 140)
for i, line in enumerate(wrapped):
    color = accent if line.startswith("  •") or "NOVO" in line or "HONDA" in line or "SUCCEEDED" in line or line.startswith("runId:") else fg
    if line.startswith("═") or line.startswith(" Demo:"):
        color = (240, 240, 240)
    if "Bearer $APIFY_TOKEN" in line or "never printed" in line:
        color = (180, 180, 100)
    draw.text((pad, pad + i * line_h), line[:cols], font=font, fill=color)
img.save(png_path, "PNG")
print(f"wrote {png_path} {img.size} lines={len(wrapped)}")
