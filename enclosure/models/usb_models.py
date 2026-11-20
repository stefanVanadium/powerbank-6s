"""3D models for the two port connectors, drawn from their datasheets.

KiCad 3D model frame = footprint frame with Y flipped (model +Y = footprint -Y), Z up from
the board top. Both are built in footprint coordinates and flipped at the end, so they
drop in with offset 0 and rotation 0.

USB-C  HRO TYPE-C-31-M-17 (C283540): L 6.80, rear 8.94 wide, mouth shell 8.34 x 2.56,
       height 3.16, SMD pads at fp y -2.15, shell legs at (+-4.32, -1.75 / 2.05),
       mouth face at fp y +4.65 (courtyard edge = board edge).
USB-A  Bossie BX-TYPE-A-MWC4P (C18077686): shell 13.15 x 5.72, depth 14.10, contacts at
       fp y -1.35 (x -3.5/-1/1/3.5), shell legs dia 2.3 at (+-6.57, +1.35), legs 3.0 below
       the board face, mouth at fp y +11.63.

Run: enclosure/.venv/bin/python enclosure/models/usb_models.py
"""
from pathlib import Path

from build123d import Box, Color, Compound, Cylinder, Pos, Rot, SlotCenterToCenter, Plane, extrude, export_step, mirror

OUT = Path(__file__).resolve().parents[2] / "lib" / "powerbank.3dshapes"
METAL = Color(0.78, 0.78, 0.80)
BLACK = Color(0.08, 0.08, 0.08)
WHITE = Color(0.92, 0.92, 0.90)
GOLD = Color(0.85, 0.68, 0.25)


def box(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def stadium_y(w, h, y0, y1, zc):
    """Stadium section in the XZ plane, extruded along +Y from y0 to y1."""
    s = SlotCenterToCenter(w - h, h)
    return Pos(0, y0, zc) * Rot(-90, 0, 0) * extrude(s, y1 - y0)


def flip(c):
    return mirror(c, Plane.XZ)


def usb_c():
    y_rear, y_front = -2.15, 4.65
    zc, w, h = 3.16 - 1.28, 8.34, 2.56
    shell = stadium_y(w, h, -0.25, y_front, zc) - stadium_y(w - 0.6, h - 0.6, -0.1, y_front + 0.1, zc)
    rear = box(-4.47, 4.47, y_rear + 0.4, -0.25, 0, 3.16)
    shell = shell + rear
    # side flanges carrying the THT legs
    for sx in (-1, 1):
        shell += box(sx * 4.17 - 0.3, sx * 4.17 + 0.3, -2.1, 2.6, 0, 1.2)
        for ly in (-1.75, 2.05):
            shell += box(sx * 4.32 - 0.25, sx * 4.32 + 0.25, ly - 0.5, ly + 0.5, -0.8, 0.2)
    shell.color, shell.label = METAL, "shell"
    tongue = box(-3.3, 3.3, -0.2, y_front - 0.6, zc - 0.35, zc + 0.35)
    tongue.color, tongue.label = BLACK, "tongue"
    pins = None
    for x in (-2.75, -1.52, -0.5, 0.5, 1.52, 2.75):
        p = box(x - 0.15, x + 0.15, y_rear - 0.4, y_rear + 0.6, 0, 0.12)
        pins = p if pins is None else pins + p
    pins.color, pins.label = GOLD, "pins"
    return Compound(children=[flip(shell), flip(tongue), flip(pins)], label="TYPE-C-31-M-17")


def usb_a():
    y_front = 11.63
    y_rear = y_front - 14.10
    W, H = 13.15, 5.72
    shell = box(-W / 2, W / 2, y_rear, y_front, 0, H) - box(-6.25, 6.25, y_rear + 1.0, y_front + 0.1, 0.30, H - 0.30)
    for sx in (-1, 1):
        shell += Pos(sx * 6.57, 1.35, -1.5) * Cylinder(1.0, 3.0)        # shell legs, 3.0 below the board face
    shell.color, shell.label = METAL, "shell"
    # housing: back wall + tongue (upper half of the mouth, contacts face down)
    housing = box(-6.25, 6.25, y_rear + 0.3, y_rear + 2.5, 0.3, H - 0.3)
    housing += box(-5.5, 5.5, y_rear + 2.5, y_front - 0.8, H - 0.3 - 2.4, H - 0.3)
    housing.color, housing.label = WHITE, "housing"
    pins = None
    for x in (-3.5, -1.0, 1.0, 3.5):
        p = box(x - 0.3, x + 0.3, -1.65, -1.05, -3.0, 0.8) + box(x - 0.3, x + 0.3, -1.65, y_rear + 0.3, 0.5, 0.8)
        pins = p if pins is None else pins + p
    pins.color, pins.label = GOLD, "pins"
    return Compound(children=[flip(shell), flip(housing), flip(pins)], label="BX-TYPE-A-MWC4P")


if __name__ == "__main__":
    for c, name in ((usb_c(), "USB-C_TYPE-C-31-M-17.step"), (usb_a(), "USB-A_BX-TYPE-A-MWC4P.step")):
        export_step(c, OUT / name)
        bb = c.bounding_box()
        print(name, [round(v, 2) for v in (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.min.Z, bb.max.Z)])
