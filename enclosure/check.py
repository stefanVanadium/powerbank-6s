"""Collision check: enclosure parts against the real board (out/pcb.step, kicad-cli export).

Reports pairs closer than MIN_GAP (overlap = 0). Board solids are named by the footprint whose
bbox holds their centre (out/fps.json). Thermal pads, foam and cells touch by design.
Run: .venv/bin/python check.py
"""
import json
import sys
from pathlib import Path

from build123d import Pos, import_step

import case

HERE = Path(__file__).parent
MIN_GAP = 0.1
SKIP = ("thermal pads", "foam", "ink", "qi2 ring", "engraving", "feet")
SKIP_PREFIX = ("cell",)


def owner(fps, s):
    bb = s.bounding_box()
    cx, cy = (bb.min.X + bb.max.X) / 2 + 76.0, 68.0 - (bb.min.Y + bb.max.Y) / 2
    for ref, x0, y0, x1, y1, _ in fps:
        if x0 - 0.2 <= cx <= x1 + 0.2 and y0 - 0.2 <= cy <= y1 + 0.2:
            return ref
    return "board"


def main():
    pcb = Pos(-76.0, 68.0, 0) * import_step(HERE / "out" / "pcb.step")
    solids = list(pcb.solids())
    fps = json.loads((HERE / "out" / "fps.json").read_text())
    parts = case.build()
    bad = 0
    for shape, label, _ in parts:
        if label in SKIP or label.startswith(SKIP_PREFIX):
            continue
        pb = shape.bounding_box()
        hits = {}
        for s in solids:
            sb = s.bounding_box()
            if (sb.min.X > pb.max.X + MIN_GAP or sb.max.X < pb.min.X - MIN_GAP or sb.min.Y > pb.max.Y + MIN_GAP
                    or sb.max.Y < pb.min.Y - MIN_GAP or sb.min.Z > pb.max.Z + MIN_GAP or sb.max.Z < pb.min.Z - MIN_GAP):
                continue
            # the board itself may touch the standoffs and bosses: those are the supports
            if label.startswith(("standoff", "body")) and sb.min.Z > -0.06 and sb.max.Z < case.PCB_TOP + 0.06 and sb.size.X * sb.size.Y > 20:
                continue
            d = shape.distance_to(s)
            if d < MIN_GAP:
                ref = owner(fps, s)
                if label.startswith("button") and ref.startswith("SW"):
                    if d >= 0.05:
                        continue
                if d < hits.get(ref, (9,))[0]:
                    p = shape.closest_points(s)[0]
                    hits[ref] = (d, f"({p.X:.1f},{p.Y:.1f},{p.Z:.2f})")
        if hits:
            bad += 1
            print(f"{label}: " + ", ".join(f"{r} {d:.3f} at {p}" for r, (d, p) in sorted(hits.items())))
    # cells against the door / foam stack and the body
    body, door = parts[0][0], parts[1][0]
    cells = [p for p in parts if p[1].startswith("cell")]
    for c, label, _ in cells:
        for other, name in ((body, "body"), (door, "door")):
            d = c.distance_to(other)
            if d < MIN_GAP:
                bad += 1
                print(f"{label} <-> {name}: {d:.3f}")
    print("OK" if bad == 0 else f"{bad} part(s) too close")
    return bad


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
