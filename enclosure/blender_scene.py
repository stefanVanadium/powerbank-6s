"""Product renders in Blender (Cycles), from the case meshes of case.py (out/mesh/*.stl).
Same studio and materials as the mp3 player renders.

  blender -b --python blender_scene.py -- hero <grey|black>
  blender -b --python blender_scene.py -- explode_anim [frames] [variant]

Inputs: out/mesh/*.stl (case.py), out/screen.png (screen.py), out/pcb.glb (kicad-cli pcb export glb, see
export_pcb below). Output: out/render/hero_<variant>.png, out/render/explode_anim/####.png
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
RENDER = OUT / "render"
MM = 0.001
Z_BACK, Z_FRONT = -24.5 * MM, 14.65 * MM          # case.py
H = Z_FRONT - Z_BACK
INK_TOP = 13.15 * MM                               # glass underside (GLASS_SEAT + ADH)
AA, AA_C = 27.72 * MM, (24.0 * MM, -40.2 * MM)     # display active area, centre (DISP_C + AA_DY)

VARIANTS = {   # anodized colour (same values as the mp3 player)
    "black": (0.016, 0.017, 0.019),
    "grey": (0.20, 0.205, 0.215),
}
# mesh -> material key; z offset (mm) so coplanar layers under the glass don't fight
PARTS = {"body": ("alu", 0), "door": ("alu", 0), "button1": ("alu", 0), "button2": ("alu", 0),
         "glass": ("glass", 0), "ink": ("ink", -0.02), "qi2_ring": ("ring", 0.035),
         "display_panel": ("display", -0.02), "engraving": ("engraving", 0), "feet": ("rubber", 0),
         "screw1": ("screw", 0), "screw2": ("screw", 0), "screw3": ("screw", 0), "screw4": ("screw", 0)}
INNER = {"qi2_module": ("qi2", 0), "thermal_pads": ("pad", 0), "foam": ("foam", 0),
         **{f"cell{i}": ("cell", 0) for i in range(1, 7)}, **{f"standoff{i}": ("steel", 0) for i in range(1, 5)}}
PCB_OFFSET = Vector((-76.0 * MM, 68.0 * MM, 0.0))   # board glb (x, -y) -> enclosure frame
# kicad-cli pcb export glb -f --subst-models --include-tracks --include-pads --include-zones \
#     --include-soldermask --include-silkscreen -o enclosure/out/pcb.glb powerbank.kicad_pcb


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                break
        except TypeError:
            continue
    for d in prefs.devices:
        d.use = d.type != "CPU"
    sc.cycles.device = "GPU"
    sc.cycles.samples = 256
    sc.cycles.use_denoising = True
    # Debian's Blender has no OpenImageDenoise: use OptiX on the GPU
    sc.cycles.denoiser = "OPTIX" if prefs.compute_device_type == "OPTIX" else "OPENIMAGEDENOISE"
    print("cycles device", prefs.compute_device_type, [d.name for d in prefs.devices if d.use])
    sc.cycles.max_bounces = 10
    sc.cycles.transmission_bounces = 8
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.film_transparent = False
    world = bpy.data.worlds.new("world")
    sc.world = world
    world.use_nodes = True
    # dim light from the world, but a light grey background where the camera sees it
    nt = world.node_tree
    bg = nt.nodes["Background"]
    bg.inputs[0].default_value = (0.9, 0.9, 0.92, 1)
    bg.inputs[1].default_value = 0.06
    seen = nt.nodes.new("ShaderNodeBackground")
    seen.inputs[0].default_value = (0.30, 0.30, 0.31, 1)
    seen.inputs[1].default_value = 1.0
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(seen.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["World Output"].inputs["Surface"])
    sc.render.use_persistent_data = True
    return sc


def mat(name, color, metallic=0.0, rough=0.5, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Metallic"].default_value = metallic
    p.inputs["Roughness"].default_value = rough
    for k, v in kw.items():
        p.inputs[k].default_value = v
    return m


def blasted(name, color):
    """Bead blasted anodized aluminium: metallic, fine noise in the roughness and bump."""
    m = mat(name, color, metallic=1.0, rough=0.38)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 9000.0
    tex.inputs["Detail"].default_value = 2.0
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = 0.32
    ramp.inputs["To Max"].default_value = 0.46
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], p.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.00002
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def import_stl(path, collection):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=str(path), global_scale=MM)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        for c in o.users_collection:
            c.objects.unlink(o)
        collection.objects.link(o)
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
        o.select_set(False)
    return new


def studio(sc, size=1.0):
    """Seamless backdrop and three soft area lights, scaled around the origin."""
    bpy.ops.mesh.primitive_plane_add(size=4 * size, location=(0, 0, 0))
    floor = bpy.context.object
    bpy.ops.object.modifier_add(type="SOLIDIFY")
    floor.data.materials.append(mat("backdrop", (0.16, 0.16, 0.17), rough=0.75))
    # curve up behind
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for name, loc, energy, sz, color in (
            # low side lights: the top faces mirror the dark ceiling, the edges catch the light
            ("key", (0.40 * size, -0.20 * size, 0.14 * size), 8 * size ** 2, 0.30 * size, (1, 0.97, 0.93)),
            ("fill", (-0.40 * size, -0.25 * size, 0.10 * size), 2.5 * size ** 2, 0.45 * size, (0.93, 0.96, 1)),
            ("rim", (0.0, 0.45 * size, 0.16 * size), 6 * size ** 2, 0.25 * size, (1, 1, 1)),
            ("top", (0.0, -0.05 * size, 0.6 * size), 1.2 * size ** 2, 0.15 * size, (1, 1, 1))):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, sz, color
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        d = Vector((0, 0, 0.01 * size)) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return floor


def camera(sc, loc, target, lens=85, fstop=None, focus=None):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    cd.clip_start = 0.001
    cam = bpy.data.objects.new("cam", cd)
    sc.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = focus or (Vector(target) - Vector(loc)).length
    sc.camera = cam
    return cam


def pose(root, loc, rot_deg):
    root.location = loc
    root.rotation_euler = Euler([math.radians(a) for a in rot_deg])


def screen_mat():
    m = mat("screen", (0, 0, 0), rough=0.2)
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(str(OUT / "screen.png"))
    nt.links.new(img.outputs["Color"], p.inputs["Emission Color"])
    p.inputs["Emission Strength"].default_value = 1.6
    return m


def shared_materials():
    return {
        "chamfer": mat("diamond cut", (0.95, 0.95, 0.96), metallic=1.0, rough=0.06),
        "engraving": mat("laser marking", (0.86, 0.87, 0.88), metallic=0.6, rough=0.55),
        "glass": mat("cover glass", (1, 1, 1), rough=0.0, **{"Transmission Weight": 1.0, "IOR": 1.5}),
        "ink": mat("black ink", (0.006, 0.006, 0.007), rough=0.35),
        "ring": mat("printed ring", (0.16, 0.165, 0.17), rough=0.5),
        "display": mat("display glass", (0.01, 0.01, 0.012), rough=0.15),
        "screen": screen_mat(),
        "screw": mat("black oxide", (0.05, 0.05, 0.055), metallic=1.0, rough=0.3),
        "rubber": mat("rubber feet", (0.02, 0.02, 0.02), rough=0.85),
        "qi2": mat("qi2 module", (0.025, 0.025, 0.03), rough=0.6),
        "pad": mat("gap pad", (0.75, 0.5, 0.55), rough=0.8),
        "foam": mat("pe foam", (0.03, 0.03, 0.03), rough=0.95),
        "cell": mat("18650 wrap", (0.02, 0.12, 0.45), rough=0.25),
        "steel": mat("steel", (0.8, 0.8, 0.82), metallic=1.0, rough=0.25),
    }


def split_chamfer(obj, chamfer, base):
    """Polished front chamfer: faces at ~45 deg at the front edge get the second material."""
    obj.data.materials.clear()
    obj.data.materials.append(base)
    obj.data.materials.append(chamfer)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for f in bm.faces:
        n, c = f.normal, f.calc_center_median()
        f.material_index = 1 if (0.45 < n.z < 0.9 and c.z > Z_FRONT - 1.0 * MM) else 0
    bm.to_mesh(obj.data)
    bm.free()


def build_device(name, variant, mats, inner=False):
    """One powerbank as a collection under an empty (origin at the case centre)."""
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new(name, None)
    col.objects.link(root)
    alu = blasted(f"alu {variant}", VARIANTS[variant])
    centre = Vector((0, 0, (Z_BACK + Z_FRONT) / 2))
    objs, parts = [], {}
    for p, (key, dz) in ({**PARTS, **INNER} if inner else PARTS).items():
        for o in import_stl(OUT / "mesh" / f"{p}.stl", col):
            o.location.z += dz * MM
            o.data.materials.clear()
            o.data.materials.append(alu if key == "alu" else mats[key])
            if p == "body":
                split_chamfer(o, mats["chamfer"], alu)
            objs.append(o)
            parts.setdefault(p, []).append(o)
    bpy.ops.mesh.primitive_plane_add(size=AA, location=(*AA_C, INK_TOP - 0.01 * MM))
    scr = bpy.context.object
    for c in scr.users_collection:
        c.objects.unlink(scr)
    col.objects.link(scr)
    scr.data.materials.append(mats["screen"])
    objs.append(scr)
    parts["screen"] = [scr]
    if inner:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(OUT / "pcb.glb"))
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            for c in o.users_collection:
                c.objects.unlink(o)
            col.objects.link(o)
        top = [o for o in new if o.parent is None]
        for o in top:
            o.location += PCB_OFFSET
        objs += top
        parts["pcb"] = top
    for o in objs:
        o.parent = root
        o.matrix_parent_inverse = Matrix.Translation(-centre)
    LAST_PARTS.clear()
    LAST_PARTS.update(parts)
    return root


LAST_PARTS = {}


def render(sc, path):
    RENDER.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("wrote", path)


def hero(variant, samples=256):
    sc = reset()
    sc.cycles.samples = samples
    mats = shared_materials()
    front = build_device(f"powerbank {variant}", variant, mats)
    pose(front, (0.0, 0.0, H / 2), (0, 0, 22))
    back = build_device(f"powerbank {variant} back", variant, mats)
    pose(back, (0.17, 0.165, H / 2), (0, 180, -18))
    studio(sc, 1.4)
    cam = (0.22, -0.53, 0.44)
    camera(sc, cam, (0.075, 0.07, 0.0), lens=70, fstop=8.0, focus=(Vector(cam) - Vector((0.0, 0.0, H))).length)
    render(sc, RENDER / f"hero_{variant}.png")


# exploded offsets along the case normal (mm, front +), in the order the parts fly out
EXPLODE = [
    (("screw1", "screw2", "screw3", "screw4"), -150), (("door", "feet"), -120), (("foam",), -98),
    (("cell1", "cell2", "cell3", "cell4", "cell5", "cell6"), -72),
    (("pcb", "standoff1", "standoff2", "standoff3", "standoff4"), -38), (("thermal_pads",), -22),
    (("qi2_module", "display_panel", "screen"), 40), (("button1", "button2"), 62),
    (("glass", "ink", "qi2_ring"), 84),
]


def explode_anim(frames=210, variant="grey", samples=32, only=None):
    """Assembled -> exploded (staggered, eased) -> hold -> back together, camera orbiting.
    The case stands on its bottom edge, front toward the camera; the stack opens front/back."""
    sc = reset()
    sc.cycles.samples = samples
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.world.node_tree.nodes["Background.001"].inputs[0].default_value = (0.012, 0.012, 0.014, 1)
    mats = shared_materials()
    d = build_device("powerbank exploded", variant, mats, inner=True)
    pose(d, (0, 0, (142.6 / 2 + 0.5) * MM), (90, 0, -26))
    studio(sc, 1.5)
    target = Vector((0.0, 0.0, 0.075))
    pivot = bpy.data.objects.new("orbit", None)
    sc.collection.objects.link(pivot)
    pivot.location = target
    cam = camera(sc, (0.47, -0.58, 0.24), target, lens=58, fstop=16.0)
    bpy.context.view_layer.update()
    cam.parent = pivot
    cam.matrix_parent_inverse = pivot.matrix_world.inverted()
    out_start, out_len, stagger = 20, 45, 3
    hold_end = 130
    n = len(EXPLODE)
    for i, (names, dz) in enumerate(EXPLODE):
        off = Vector((0, 0, dz * MM))
        for p in names:
            for o in LAST_PARTS.get(p, []):
                base = o.location.copy()
                f0 = out_start + i * stagger
                f1 = hold_end + (n - 1 - i) * stagger      # reassemble in reverse order
                for f, loc in ((f0, base), (f0 + out_len, base + off), (f1, base + off), (f1 + out_len, base)):
                    o.location = loc
                    o.keyframe_insert("location", frame=f)
                for fc in o.animation_data.action.fcurves:
                    for k in fc.keyframe_points:
                        k.interpolation = "BEZIER"
                        k.easing = "EASE_IN_OUT"
    pivot.rotation_euler = (0, 0, math.radians(-12))
    pivot.keyframe_insert("rotation_euler", frame=1)
    pivot.rotation_euler = (0, 0, math.radians(18))
    pivot.keyframe_insert("rotation_euler", frame=frames)
    sc.frame_start, sc.frame_end = 1, frames
    sc.render.image_settings.file_format = "PNG"
    if only:                                   # test stills: only=[frame, ...]
        for f in only:
            sc.frame_set(f)
            render(sc, RENDER / f"explode_test_{f:04d}.png")
        return
    (RENDER / "explode_anim").mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(RENDER / "explode_anim" / "####")
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["hero", "grey"]
    if args[0] == "hero":
        hero(args[1] if len(args) > 1 else "grey", int(args[2]) if len(args) > 2 else 256)
    elif args[0] == "explode_anim":
        explode_anim(int(args[1]) if len(args) > 1 else 210, args[2] if len(args) > 2 else "grey")
    elif args[0] == "explode_test":      # stills of single frames: explode_test <frame> [frame ...]
        explode_anim(variant="grey", samples=16, only=[int(a) for a in args[1:]] or [1, 100])
