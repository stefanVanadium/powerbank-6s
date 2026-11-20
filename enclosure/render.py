"""README renders of the enclosure (pyvista, offscreen). Needs out/mesh/ from case.py.
Run: DISPLAY=:1 .venv/bin/python render.py  ->  ../images/case-front.png, ../images/case-back.png
"""
from pathlib import Path

import pyvista as pv

HERE = Path(__file__).parent
MESH = HERE / "out" / "mesh"
IMG = HERE.parent / "images"

LOOK = {  # mesh: (colour, opacity, metallic)
    "body": ("#b9bcc1", 1.0, True), "door": ("#b9bcc1", 1.0, True),
    "button1": ("#d0d2d6", 1.0, True), "button2": ("#d0d2d6", 1.0, True),
    "ink": ("#0b0b0d", 1.0, False),
    "qi2_ring": ("#8a8d92", 1.0, False), "display_panel": ("#10131c", 1.0, False),
    "engraving": ("#3a3b3e", 1.0, False), "feet": ("#111111", 1.0, False),
    "screw1": ("#2a2a2a", 1.0, True), "screw2": ("#2a2a2a", 1.0, True),
    "screw3": ("#2a2a2a", 1.0, True), "screw4": ("#2a2a2a", 1.0, True),
}


def shot(name, cam, up=(0, 0, 1)):
    p = pv.Plotter(off_screen=True, window_size=(1600, 1100))
    p.set_background("white")
    for stem, (col, op, metal) in LOOK.items():
        f = MESH / f"{stem}.stl"
        if f.exists():
            m = pv.read(f)
            if stem == "qi2_ring":          # printed under the ink: lift it for the render
                m = m.translate((0, 0, 0.1))
            p.add_mesh(m, color=col, opacity=op, smooth_shading=True,
                       specular=0.5 if metal else 0.3, specular_power=20, ambient=0.25, diffuse=0.8)
    p.camera_position = [cam, (0, 0, -5), up]
    p.camera.zoom(0.95)
    p.enable_eye_dome_lighting() if False else None
    p.enable_anti_aliasing("ssaa")
    p.screenshot(IMG / name)
    print(IMG / name)


shot("case-front.png", (150, -260, 300), (0, 0, 1))
shot("case-back.png", (-190, 230, -260), (0, 0, 1))
