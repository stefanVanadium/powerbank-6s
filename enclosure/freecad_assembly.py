"""Build out/powerbank_case.FCStd from the parts case.py exported to out/step/.

Run inside FreeCAD (GUI, so the colours are kept):
  ~/Applications/FreeCAD_1.1.4-Linux-x86_64-py311.AppImage enclosure/freecad_assembly.py
The geometry stays in case.py: change a dimension there, re-run case.py, then this macro.
"""
import os
from pathlib import Path

import FreeCAD as App
import Part

HERE = Path(os.environ.get("PB_ENCLOSURE", "/home/stefan/Documents/kicad/powerbank/enclosure"))
STEP = HERE / "out" / "step"
FCSTD = HERE / "out" / "powerbank_case.FCStd"

STYLE = {  # name: (rgb, transparency %, group)
    "body": ((0.72, 0.73, 0.75), 0, "Enclosure"),
    "door": ((0.72, 0.73, 0.75), 0, "Enclosure"),
    "glass": ((0.70, 0.82, 0.90), 75, "Enclosure"),
    "ink": ((0.03, 0.03, 0.03), 0, "Enclosure"),
    "qi2_ring": ((0.55, 0.55, 0.55), 0, "Enclosure"),
    "button1": ((0.80, 0.80, 0.82), 0, "Enclosure"),
    "button2": ((0.80, 0.80, 0.82), 0, "Enclosure"),
    "engraving": ((0.15, 0.15, 0.15), 0, "Enclosure"),
    "thermal_pads": ((0.90, 0.45, 0.20), 0, "Internals"),
    "foam": ((0.15, 0.15, 0.15), 0, "Internals"),
    "feet": ((0.05, 0.05, 0.05), 0, "Hardware"),
    "qi2_module": ((0.25, 0.25, 0.32), 0, "Placeholders"),
    "display_panel": ((0.05, 0.05, 0.12), 0, "Placeholders"),
}
DIMS = [
    ("Outside", "158.6 x 142.6 x 39.15 mm"),
    ("Wall", "3.0 mm 6061, board gap 0.3"),
    ("Glass", "1.5 mm tempered, 132.0 x 135.6, R3"),
    ("Mid-frame", "Z 11.0..13.0 (board back = Z 0)"),
    ("Door", "2.5 mm 6061, 4x M3x6 countersunk Torx"),
    ("Standoffs", "4x M3 x 22 hex 5.5 F-M, Helicoil M3x1.5D in bosses"),
    ("Thermal pads", "1.5 mm gap pad -> 1.0 compressed, 12 FETs + 4 inductors"),
    ("Qi2", "placeholder dia 56 x 7, window dia 58"),
    ("Display", "placeholder 27.8 x 32.6 x 1.6 bare panel"),
    ("Source", "enclosure/case.py (build123d) - edit there, re-run"),
]

doc = App.newDocument("powerbank_case")
groups = {}


def group(name):
    if name not in groups:
        groups[name] = doc.addObject("App::DocumentObjectGroup", name)
    return groups[name]


for f in sorted(STEP.glob("*.step")):
    name = f.stem
    shape = Part.read(str(f))
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    rgb, transp, g = STYLE.get(name, ((0.8, 0.7, 0.4), 0, "Hardware"))
    if name.startswith("cell"):
        rgb, g = (0.10, 0.35, 0.70), "Placeholders"
    group(g).addObject(obj)
    if App.GuiUp:
        obj.ViewObject.ShapeColor = rgb
        obj.ViewObject.Transparency = transp

# the real board, from kicad-cli (placed in enclosure coordinates)
import Import
before = set(doc.Objects)
Import.insert(str(HERE / "out" / "pcb.step"), doc.Name)
for o in set(doc.Objects) - before:
    if o.InList == [] or all(p not in set(doc.Objects) - before for p in o.InList):
        o.Placement = App.Placement(App.Vector(-76.0, 68.0, 0), App.Rotation()).multiply(o.Placement)
        o.Label = "PCB (powerbank.kicad_pcb)"
        group("PCB").addObject(o)

sheet = doc.addObject("Spreadsheet::Sheet", "Dimensions")
for i, (k, v) in enumerate(DIMS, start=1):
    sheet.set(f"A{i}", k)
    sheet.set(f"B{i}", "'" + v)
doc.recompute()
doc.saveAs(str(FCSTD))
print("saved", FCSTD)

if App.GuiUp:
    import FreeCADGui as Gui
    v = Gui.ActiveDocument.ActiveView
    v.viewIsometric()
    v.fitAll()
