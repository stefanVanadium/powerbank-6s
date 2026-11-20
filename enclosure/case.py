"""Enclosure for the 6S power bank: milled 6061 body, glass front, screwed cell door.

Parts
  body     one 6061 piece milled from both sides: four walls, an internal mid-frame under the
           glass (heat sink for the converters, through thermal pads) and the 4 board bosses
  glass    1.5 mm tempered glass bonded into the front pocket, black ink inside with a
           window for the display; the Qi2 coil sits right under it (no metal in the way)
  door     2.5 mm 6061 plate in a rebate on the back, 4 M3 countersunk Torx screws into
           steel M3 x 22 hex standoffs, which also hold the board against the mid-frame
           bosses (Helicoil M3 x 1.5D inserts in the bosses)
  buttons  2 aluminium plungers in the right bezel, over SW1 / SW2
  + thermal pads, foam strips, standoffs, screws, Qi2 / display / cell placeholders

Axes: X = board x - 76 (board centre), Y = 68 - board y (ports at +Y), Z = 0 on the board's
back face, front (glass) at +Z, cell door at -Z.

Run: .venv/bin/python case.py  ->  out/*.step / *.stl, out/mesh/*.stl
"""

import json
import math
import re
from pathlib import Path

from build123d import (
    Axis, Box, Color, Compound, Cone, Cylinder, Face, Plane, Pos, Rectangle, RectangleRounded,
    RegularPolygon, Rot, SlotCenterToCenter, Text, Vector, Wire, chamfer, export_step, export_stl,
    extrude, fillet, mirror,
)
from shapely.geometry import LineString, Polygon as SPolygon
from shapely.ops import unary_union

HERE = Path(__file__).parent
OUT = HERE / "out"
LOGO_SVG = Path.home() / "Documents/logo-vanadium/final/vanadium-logo-mono-negru.svg"
FONT = str(Path.home() / ".local/share/fonts/Inter/InterVariable.ttf")
HEIGHTS = json.loads((OUT / "heights.json").read_text())   # ref -> [x0, y0, x1, y1, z0, z1] (board mm, from pcb.step)
PARTS = {k: v for k, v in HEIGHTS}


def b2e(xb, yb):
    return xb - 76.0, 68.0 - yb


# --- board ---------------------------------------------------------------------------
BOARD_W, BOARD_L, PCB_T = 152.0, 136.0, 1.6
PCB_TOP = PCB_T
HOLES = [(5, 5), (147, 5), (5, 131), (147, 131)]          # H1..H4, M3

# --- shell -----------------------------------------------------------------------------
GAP = 0.3                       # board edge to wall
WALL = 3.0
IN_W, IN_L, IN_R = BOARD_W + 2 * GAP, BOARD_L + 2 * GAP, 3.0 + GAP
OUT_W, OUT_L, OUT_R = IN_W + 2 * WALL, IN_L + 2 * WALL, IN_R + WALL
FRONT_CHAMFER, BACK_FILLET = 0.6, 1.2

# --- front stack: mid-frame + glass ------------------------------------------------------
PAD = 1.0                       # thermal pad, compressed (1.5 mm Gap Pad, ~30 %)
MID_BOT = 11.0                  # mid-frame underside; tallest parts under it: headers 10.14
GLASS_SEAT = 13.0               # mid-frame top = glass seat
ADH = 0.15                      # die-cut VHB / OCA tape
GLASS_T = 1.5
Z_FRONT = GLASS_SEAT + ADH + GLASS_T      # 14.65
BEZEL_SIDE = 13.3               # right band carries the two buttons, left mirrors it
BEZEL_END = 3.5
GLASS_W, GLASS_L, GLASS_R = OUT_W - 2 * BEZEL_SIDE, OUT_L - 2 * BEZEL_END, 3.0

# --- back stack: cells + door -------------------------------------------------------------
# Keystone 1042: body 14.86 mm (DigiKey), open floor; the cell rests on the side rails
# (z 5.11 at 8 mm from the axis in the EasyEDA model) -> axis ~9.9 mm under the board,
# outer surface at 19.2 mm for a 18.6 mm cell. MEASURE on a real holder before milling.
CELL_D, CELL_L, CELL_AXIS = 18.6, 65.0, -9.9
CELL_X = [21, 43, 65, 87, 109, 131]       # board x, holders BT1..BT6 at board y 77
CELL_PLUS_UP = [True, False, True, False, True, False]   # BT pad 2 (+) at board y 37.6 for BT1/3/5
STANDOFF = 22.0                 # M3 x 22 hex 5.5, female-male
DOOR_IN = -STANDOFF
DOOR_T = 2.5
Z_BACK = DOOR_IN - DOOR_T       # -24.5
REBATE = 1.5                    # door overlaps the wall by this much
FOAM_Z = (DOOR_IN, CELL_AXIS - CELL_D / 2 - 0.05)       # 2.75 thick here, 3 mm foam pre-load

# --- bosses, screws ------------------------------------------------------------------------
BOSS_D = 6.0                    # H2 sits 0.45 mm from the USB-A2 shell
HELICOIL_DRILL = 3.2            # M3 STI tap drill (Helicoil M3 x 1.5D, 4.5 mm)
HELICOIL_DEPTH = 7.0
SCREW_CLEAR, CSK_D = 3.4, 6.5

# --- thermal bosses: mid-frame -> pad -> part -------------------------------------------------
HOT = [f"Q_{s}_C{c}" for c in (1, 2, 3) for s in ("HS1", "HS2", "LS1", "LS2")]
HOT += ["L_BB_C1", "L_BB_C2", "L_BB_C3", "L_5V"]
HOT_SHRINK = 0.4                # boss face 0.4 mm inside the part body outline

# --- Qi2, display, buttons ---------------------------------------------------------------------
QI2_C = b2e(54.0, 100.0)        # nothing taller than 3.71 (L_3V3) under a 62 mm circle; ring + display centred as a pair
QI2_D, QI2_T = 56.0, 7.0        # placeholder: module not bought yet (coil + magnets + board)
QI2_WINDOW = 58.0
DISP_C = b2e(100.0, 110.0)
PANEL = (27.8, 32.6, 1.6)       # bare 1.54" 240x240 ST7789 IPS (FPC); exact part not bought yet
AA = (27.72, 27.72)
AA_DY = 1.8                     # active area offset toward the top (FPC at the bottom)
BUTTONS = [b2e(147.0, 96.0), b2e(147.0, 112.0)]   # SW1, SW2 (TS-1088, top 3.54)
SW_TOP = 3.54
BTN_HOLE, BTN_D, BTN_FLANGE = 6.2, 6.0, 8.0
L12_POCKET_TOP = 12.0           # L_12V (top 11.0) gets a blind pocket in the mid-frame

# --- ports (+Y wall), from the datasheets ----------------------------------------------------------
# TYPE-C-31-M-17: mouth 8.34 x 2.56, 3.16 tall, mouth bottom 0.6 above the board
# BX-TYPE-A-MWC4P: shell 13.15 x 5.72 on the board
USBC = [("C1 IN/OUT", 26.0), ("C2", 59.0), ("C3", 92.0)]
USBA = [("A1", 118.0), ("A2", 137.0)]
USBC_Z = PCB_TOP + 3.16 - 1.28
USBA_Z = PCB_TOP + 5.72 / 2
USBC_HOLE, USBC_POCKET = (8.74, 2.96), (12.6, 6.8)      # pocket: plug overmold (spec max 12.35 x 6.5)
USBA_HOLE, USBA_POCKET = (13.55, 6.12), (16.6, 9.0)
POCKET_DEPTH = 2.3              # leaves a 0.7 mm lip; receptacle face 1.0 mm behind it
LABEL_Z, LABEL_H = 11.0, 2.0


# ===================================================================================================
def rr(w, l, r, cx=0.0, cy=0.0):
    return Pos(cx, cy) * RectangleRounded(w, l, r)


def prism(face, z0, z1):
    return Pos(0, 0, z0) * extrude(face, z1 - z0)


def box(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def cyl(x, y, d, z0, z1):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(d / 2, z1 - z0)


def part_box(ref, shrink=0.0):
    x0, y0, x1, y1, z0, z1 = PARTS[ref]
    a, b = b2e(x0 + shrink, y0 + shrink), b2e(x1 - shrink, y1 - shrink)
    return a[0], b[0], a[1], b[1], z1


def port_hole(cx, cz, w, h, y0, y1, stadium):
    if stadium:
        s = SlotCenterToCenter(w - h, h)
    else:
        s = RectangleRounded(w, h, 0.5)
    return Pos(cx, y0, cz) * Rot(-90, 0, 0) * extrude(s, y1 - y0)


# --- body -------------------------------------------------------------------------------------------
def outer_shell():
    s = prism(rr(OUT_W, OUT_L, OUT_R), Z_BACK, Z_FRONT)
    s = chamfer(s.edges().group_by(Axis.Z)[-1], FRONT_CHAMFER)
    return fillet(s.edges().group_by(Axis.Z)[0], BACK_FILLET)


def thermal_bosses():
    out = None
    for ref in HOT:
        x0, x1, y0, y1, top = part_box(ref, HOT_SHRINK)
        b = box(x0, x1, y0, y1, top + PAD, MID_BOT + 0.01)
        out = b if out is None else out + b
    return out


def port_cuts():
    y_in, y_out = IN_L / 2 - 0.1, OUT_L / 2 + 0.5
    cuts = []
    for _, xb in USBC:
        x = xb - 76.0
        cuts.append(port_hole(x, USBC_Z, *USBC_HOLE, y_in, y_out, True))
        cuts.append(port_hole(x, USBC_Z, *USBC_POCKET, OUT_L / 2 - POCKET_DEPTH, y_out, True))
    for _, xb in USBA:
        x = xb - 76.0
        cuts.append(port_hole(x, USBA_Z, *USBA_HOLE, y_in, y_out, False))
        p = RectangleRounded(*USBA_POCKET, 1.0)
        cuts.append(Pos(x, OUT_L / 2 - POCKET_DEPTH, USBA_Z) * Rot(-90, 0, 0) * extrude(p, POCKET_DEPTH + 0.5))
    return cuts


def build_body():
    body = outer_shell()
    body -= prism(rr(IN_W, IN_L, IN_R), Z_BACK - 1, MID_BOT)
    body -= prism(rr(IN_W + 2 * REBATE, IN_L + 2 * REBATE, IN_R + REBATE), Z_BACK - 1, DOOR_IN)
    body -= prism(rr(GLASS_W + 0.2, GLASS_L + 0.2, GLASS_R + 0.1), GLASS_SEAT, Z_FRONT + 1)
    # board bosses with Helicoil holes for the standoffs' male thread
    for xb, yb in HOLES:
        x, y = b2e(xb, yb)
        body += cyl(x, y, BOSS_D, PCB_TOP, MID_BOT + 0.01)
    body += thermal_bosses()
    for xb, yb in HOLES:
        x, y = b2e(xb, yb)
        body -= cyl(x, y, HELICOIL_DRILL, PCB_TOP - 0.1, PCB_TOP + HELICOIL_DEPTH)
    # mid-frame openings: Qi2 coil, display, L_12V pocket, buttons
    body -= cyl(*QI2_C, QI2_WINDOW, MID_BOT - 0.1, GLASS_SEAT + 0.1)
    body -= prism(Pos(*DISP_C) * Rectangle(PANEL[0] + 0.2, PANEL[1] + 0.2), MID_BOT - 0.1, GLASS_SEAT + 0.1)
    x0, x1, y0, y1, _ = part_box("L_12V", -0.8)
    body -= box(x0, x1, y0, y1, MID_BOT - 0.1, L12_POCKET_TOP)
    for x, y in BUTTONS:
        body -= cyl(x, y, BTN_HOLE, MID_BOT - 0.1, Z_FRONT + 1)
    for c in port_cuts():
        body -= c
    return body


# --- glass ---------------------------------------------------------------------------------------------
def build_glass():
    return prism(rr(GLASS_W, GLASS_L, GLASS_R), GLASS_SEAT + ADH, Z_FRONT)


def build_ink():
    """Black ceramic ink on the inside of the glass, with the display window."""
    ink = prism(rr(GLASS_W - 0.01, GLASS_L - 0.01, GLASS_R), GLASS_SEAT + ADH - 0.02, GLASS_SEAT + ADH)
    ink -= prism(Pos(DISP_C[0], DISP_C[1] + AA_DY) * Rectangle(AA[0] + 0.4, AA[1] + 0.4), GLASS_SEAT, Z_FRONT)
    return ink


def build_qi2_ring():
    """Printed light-grey ring on the ink: where to put the phone."""
    z0 = GLASS_SEAT + ADH - 0.03
    return cyl(*QI2_C, QI2_D - 4, z0, z0 + 0.01) - cyl(*QI2_C, QI2_D - 6, z0 - 1, z0 + 1)


# --- door -------------------------------------------------------------------------------------------------
def screw_cut(x, y):
    c = cyl(x, y, SCREW_CLEAR, Z_BACK - 1, DOOR_IN + 1)
    h = (CSK_D - SCREW_CLEAR) / 2
    c += Pos(x, y, Z_BACK + h / 2 - 0.001) * Cone(CSK_D / 2, SCREW_CLEAR / 2, h)
    return c


FEET = [(sx * 60.0, sy * 52.0) for sx in (-1, 1) for sy in (-1, 1)]
FOOT_D, FOOT_DEPTH = 10.2, 0.6   # 3M SJ5302-type bumpers, 10 x 2.5 mm


def build_door():
    door = prism(rr(IN_W + 2 * REBATE - 0.2, IN_L + 2 * REBATE - 0.2, IN_R + REBATE - 0.1), Z_BACK, DOOR_IN)
    door = fillet(door.edges().group_by(Axis.Z)[0], 0.8)
    for xb, yb in HOLES:
        door -= screw_cut(*b2e(xb, yb))
    for x, y in FEET:
        door -= cyl(x, y, FOOT_D, Z_BACK - 1, Z_BACK + FOOT_DEPTH)
    return door


def build_feet():
    out = None
    for x, y in FEET:
        f = cyl(x, y, 10.0, Z_BACK + FOOT_DEPTH - 2.5, Z_BACK + FOOT_DEPTH)
        out = f if out is None else out + f
    return out


def build_foam():
    """Two strips of 3 mm PE foam on the door, pressing the cells into the holders."""
    out = None
    for yb in (55.0, 99.0):
        y = 68.0 - yb
        f = box(-68, 68, y - 4, y + 4, *FOAM_Z)
        out = f if out is None else out + f
    return out


# --- buttons ------------------------------------------------------------------------------------------------
def build_button(x, y):
    b = cyl(x, y, BTN_D, MID_BOT, Z_FRONT - 0.2)
    b += cyl(x, y, BTN_FLANGE, MID_BOT - 0.6, MID_BOT - 0.05)
    b += cyl(x, y, 2.4, SW_TOP + 0.1, MID_BOT - 0.55)
    return fillet(b.edges().filter_by(lambda e: e.is_closed and abs(e.center().Z - (Z_FRONT - 0.2)) < 1e-3), 0.4)


# --- hardware, placeholders ------------------------------------------------------------------------------------
def build_standoff(x, y):
    s = Pos(x, y, (DOOR_IN + 0) / 2) * extrude(RegularPolygon(5.5 / math.sqrt(3), 6), STANDOFF / 2, both=True)
    s -= cyl(x, y, 2.5, DOOR_IN - 0.1, DOOR_IN + 5.0)              # female end
    s += cyl(x, y, 2.9, 0, PCB_TOP + 5.5)                          # male M3 x 6 through the board
    return s


def build_screw(x, y):
    h = (CSK_D - SCREW_CLEAR) / 2 + 0.05
    s = Pos(x, y, Z_BACK + h / 2) * Cone(3.0, 3.0 - h, h)
    s += cyl(x, y, 2.4, Z_BACK + h, Z_BACK + 6.0)                  # M3 x 6, minor dia (inside the standoff)
    return s


def build_qi2():
    z1 = GLASS_SEAT + ADH
    return cyl(*QI2_C, QI2_D, z1 - QI2_T, z1)


def build_panel():
    z1 = GLASS_SEAT + ADH
    return prism(Pos(*DISP_C) * Rectangle(*PANEL[:2]), z1 - PANEL[2], z1)


def build_cells():
    out = []
    for xb in CELL_X:
        x, y = b2e(xb, 77.0)
        out.append(Pos(x, y, CELL_AXIS) * Rot(90, 0, 0) * Cylinder(CELL_D / 2, CELL_L))
    return out


def build_pads():
    out = None
    for ref in HOT:
        x0, x1, y0, y1, top = part_box(ref, HOT_SHRINK)
        p = box(x0, x1, y0, y1, top, top + PAD)
        out = p if out is None else out + p
    return out


# --- engraving --------------------------------------------------------------------------------------------------
ENGRAVE = 0.03


def _ring(wire, n=24):
    pts = []
    for e in wire.order_edges():
        pts += [tuple(e.position_at(i / n))[:2] for i in range(n)]
    return pts


def face_to_shapely(face):
    return SPolygon(_ring(face.outer_wire()), [_ring(w) for w in face.inner_wires()]).buffer(0)


def shapely_faces(geom, tr):
    out = []
    for pg in (geom.geoms if hasattr(geom, "geoms") else [geom]):
        if pg.area < 1e-4:
            continue
        outer = Wire.make_polygon([tr(p) for p in pg.exterior.coords[:-1]], close=True)
        inners = [Wire.make_polygon([tr(p) for p in r.coords[:-1]], close=True) for r in pg.interiors]
        out.append(Face(outer, inners))
    return out


def text_geom(s, size):
    t = Text(s, size, font_path=FONT)
    return unary_union([face_to_shapely(f) for f in t.faces()])


def logo_geom(width):
    svg = LOGO_SVG.read_text()
    v_d = re.search(r'<path d="(M[^"]+Z)" fill="#fff"', svg).group(1)
    v = [tuple(map(float, p.split())) for p in re.findall(r"(\d+ \d+)", v_d)]
    lines_d = re.search(r'<path d="(M[^"]+)" fill="none" stroke="#000" stroke-width="([\d.]+)"', svg)
    stroke = float(lines_d.group(2))
    lines = []
    for sub in re.findall(r"M[^M]+", lines_d.group(1)):
        nums = list(map(float, re.findall(r"-?\d+(?:\.\d+)?", sub)))
        x, y = nums[0], nums[1]
        pts = [(x, y)]
        for dx, dy in zip(nums[2::2], nums[3::2]):
            x, y = x + dx, y + dy
            pts.append((x, y))
        lines.append(LineString(pts))
    gaps = unary_union([ln.buffer(stroke / 2, cap_style="flat") for ln in lines])
    ink = SPolygon(v).difference(gaps)
    s = width / (max(p[0] for p in v) - min(p[0] for p in v))
    from shapely import affinity
    return affinity.scale(affinity.translate(ink, -500, -500), s, -s, origin=(0, 0))


def solids_from(geom, tr, z0, z1):
    return [Pos(0, 0, z0) * extrude(f, z1 - z0) for f in shapely_faces(geom, tr)]


def build_engraving():
    """Laser marking: logo + text on the door (outside, read from the back, so X is mirrored),
    cell polarity on the door's inside, port labels on the +Y wall."""
    parts = []
    zb = Z_BACK
    back = lambda dx, dy: (lambda p: Vector(-(p[0] + dx), p[1] + dy, 0))
    parts += solids_from(logo_geom(30.0), back(0, 10.0), zb - ENGRAVE, zb)
    parts += solids_from(text_geom('made by "humans"', 3.2), back(0, -14.0), zb - ENGRAVE, zb)
    parts += solids_from(text_geom("6S 18650  ·  15–25.2 V  ·  100 W", 2.6), back(0, -40.0), zb - ENGRAVE, zb)
    # inside of the door, right over each cell: number + polarity at both ends
    zi = DOOR_IN
    for i, xb in enumerate(CELL_X):
        x, y = b2e(xb, 77.0)
        top, bot = (y + 26.0, y - 26.0)
        plus, minus = (top, bot) if CELL_PLUS_UP[i] else (bot, top)
        for s, yy, size in ((str(i + 1), y, 9.0), ("+", plus, 9.0), ("−", minus, 9.0)):
            parts += solids_from(text_geom(s, size), lambda p, x=x, yy=yy: Vector(p[0] + x, p[1] + yy, 0), zi, zi + ENGRAVE)
    # port labels on the +Y face, read from outside (looking at -Y: +X is on the left)
    yo = OUT_L / 2
    for name, xb in USBC + USBA:
        g = text_geom(name, LABEL_H)
        for f in shapely_faces(g, lambda p: Vector(p[0], p[1], 0)):
            s = extrude(f, ENGRAVE)
            s = Pos(xb - 76.0, yo, LABEL_Z) * Rot(0, 0, 180) * Rot(90, 0, 0) * s
            s = mirror(s, Plane.YZ.offset(xb - 76.0)) if False else s
            parts.append(s)
    bad = [p for p in parts if not p.is_valid]
    return Compound(children=[p for p in parts if p.is_valid]), len(bad)


# ====================================================================================================================
METAL = Color(0.70, 0.71, 0.73)
DARK = Color(0.16, 0.16, 0.17)


def build():
    parts = [
        (build_body(), "body", METAL),
        (build_door(), "door", METAL),
        (build_glass(), "glass", Color(0.75, 0.85, 0.9, 0.25)),
        (build_ink(), "ink", Color(0.03, 0.03, 0.03)),
        (build_qi2_ring(), "qi2 ring", Color(0.55, 0.55, 0.55)),
        (build_pads(), "thermal pads", Color(0.85, 0.45, 0.2)),
        (build_foam(), "foam", Color(0.15, 0.15, 0.15)),
        (build_feet(), "feet", Color(0.05, 0.05, 0.05)),
        (build_qi2(), "qi2 module", Color(0.25, 0.25, 0.3)),
        (build_panel(), "display panel", Color(0.05, 0.05, 0.1)),
    ]
    for i, (x, y) in enumerate(BUTTONS):
        parts.append((build_button(x, y), f"button{i + 1}", METAL))
    for i, (xb, yb) in enumerate(HOLES):
        x, y = b2e(xb, yb)
        parts.append((build_standoff(x, y), f"standoff{i + 1}", Color(0.8, 0.7, 0.4)))
        parts.append((build_screw(x, y), f"screw{i + 1}", DARK))
    for i, c in enumerate(build_cells()):
        parts.append((c, f"cell{i + 1}", Color(0.1, 0.35, 0.7)))
    eng, nbad = build_engraving()
    if nbad:
        print(f"  engraving: {nbad} invalid piece(s) dropped")
    parts.append((eng, "engraving", DARK))
    for s, label, col in parts:
        s.label, s.color = label, col
    return parts


def slug(label):
    return label.replace(" ", "_")


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "mesh").mkdir(exist_ok=True)
    (OUT / "step").mkdir(exist_ok=True)
    parts = build()
    for shape, label, _ in parts:
        name = slug(label)
        export_stl(shape, OUT / "mesh" / f"{name}.stl", tolerance=0.01, angular_tolerance=0.1)
        export_step(shape, OUT / "step" / f"{name}.step")      # one file per part, for FreeCAD
        if name in ("body", "door", "button1", "glass"):
            export_step(shape, OUT / f"case_{name}.step")
    export_step(Compound(children=[p[0] for p in parts], label="powerbank_case"), OUT / "case_assembly.step")
    print(f"case {OUT_W:.1f} x {OUT_L:.1f} x {Z_FRONT - Z_BACK:.2f} mm (Z {Z_BACK} .. {Z_FRONT})")
    for shape, label, _ in parts:
        print(f"  {label}: {shape.volume:.0f} mm3, valid {shape.is_valid}")
    body, door = parts[0][0], parts[1][0]
    print(f"aluminium: body {body.volume * 2.70e-3:.0f} g, door {door.volume * 2.70e-3:.0f} g")


if __name__ == "__main__":
    main()
