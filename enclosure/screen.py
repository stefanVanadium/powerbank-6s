"""Screen texture for the Blender renders: the 240 x 240 status screen of the 1.54" IPS.
Run: .venv/bin/python screen.py  ->  out/screen.png
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "out"
FONT = str(Path.home() / ".local/share/fonts/Inter/InterVariable.ttf")
BG, FG, DIM, ACC, OUTC = (6, 7, 9), (235, 237, 240), (110, 114, 122), (88, 214, 141), (250, 190, 70)

im = Image.new("RGB", (240, 240), BG)
d = ImageDraw.Draw(im)
f = lambda s: ImageFont.truetype(FONT, s)


def centre(y, text, font, fill):
    w = d.textlength(text, font=font)
    d.text(((240 - w) / 2, y), text, font=font, fill=fill)


# state of charge: arc + percentage
d.arc((40, 18, 200, 178), 135, 405, fill=(30, 32, 36), width=10)
d.arc((40, 18, 200, 178), 135, 135 + 270 * 0.86, fill=ACC, width=10)
centre(62, "86%", f(46), FG)
centre(118, "21.9 V  ·  6S", f(15), DIM)
# per-port power
rows = [("C1", "IN 45 W", ACC), ("C2", "OUT 20 W", OUTC), ("A1", "OUT 9 W", OUTC)]
for i, (port, txt, col) in enumerate(rows):
    y = 186 + i * 16
    d.text((34, y), port, font=f(13), fill=DIM)
    w = d.textlength(txt, font=f(13))
    d.text((206 - w, y), txt, font=f(13), fill=col)
im.resize((960, 960), Image.LANCZOS).save(OUT / "screen.png")
print(OUT / "screen.png")
