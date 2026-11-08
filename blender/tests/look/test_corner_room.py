"""tests/look/test_corner_room.py: the lighting helpers in a room. The corner set's own models (eidoverse/assets/models/
corner_*.glb, laid out as eidoverse/sets/corner.js lays them, in Blender axes) in a plaster room with a window: low
evening sun through the window, the desk lamp as a PRACTICAL (its bulb glows and a real light sits in it; the shade
casts the shadow that makes the pool below and the scallop above), a uniform sky-blue world outside (no stock sky), a
baked volume probe and a sphere probe, a chrome, a rough-metal and a white sphere on the floor and a glass pane.

Judge: contact darkening under the chair and spheres; the lamp reading as the source of its light; the sun patch's
soft edge (the sun's real angle); chrome reflecting the room (not black); colour bleed from the rug; AgX roll-off on
the sunlit floor; the light inventory in the log. And against Cycles: both stills are path traced too
(corner_vs_cycles_sheet.jpg), the ground truth for where the room's light comes from.
    bash run_blender.sh blender/tests/look/test_corner_room.py --stage build
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this> --stage render
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as FX                                       # noqa: E402

from eidoblend.look import camera as C                       # noqa: E402
from eidoblend.look import camera_audit as CA                # noqa: E402
from eidoblend.look import exposure as EX                    # noqa: E402
from eidoblend.look import frame_stats as FS                 # noqa: E402
from eidoblend.look import lighting as L                     # noqa: E402
from eidoblend.look import probe as P                        # noqa: E402
from eidoblend.look import render_settings as RS             # noqa: E402

A = FX.args()
STAGE = FX.arg(A, '--stage', 'all')
OUT = os.path.join(FX.OUT, 'corner')
BLEND = os.path.join(OUT, 'corner_room.blend')
os.makedirs(OUT, exist_ok=True)
REPORT = {}
MODELS = os.path.join(FX.ASSETS, 'models')
# corner.js's layout (three, metres) -> Blender: (x, y, z) -> (x, -z, y); a yaw about three's +Y is the same yaw
# about Blender's +Z
RW, RD, RH = 4.4, 4.0, 2.7
WIN = {'x': -1.36, 'y': 1.60, 'w': 1.0, 'h': 1.25}
DESK_TOP = 0.76


def B(x, y, z):
    return C.three_to_blender((x, y, z))


def mat(name, colour, rough=0.9, metal=0.0, transmission=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*colour, 1.0)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if transmission:
        # thin glass in EEVEE: dithered, ray-traced refraction, slab thickness (BLENDED drew this pane as a dark
        # panel with sparkles; this reads as Cycles does, the floor through it; measured 11-07)
        p.inputs['Transmission Weight'].default_value = transmission
        p.inputs['IOR'].default_value = ior
        m.surface_render_method = 'DITHERED'
        m.use_raytrace_refraction = True
        m.thickness_mode = 'SLAB'
        out = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial')
        th = m.node_tree.nodes.new('ShaderNodeValue')
        th.outputs[0].default_value = 0.015
        m.node_tree.links.new(th.outputs[0], out.inputs['Thickness'])
    return m


def slab(name, lo, hi, m, col):
    """An axis-aligned box from lo to hi (Blender metres)."""
    lo, hi = Vector(lo), Vector(hi)
    me = bpy.data.meshes.new(name)
    v = [(x, y, z) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def glb(name, pos, yaw, col):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(MODELS, f'corner_{name}.glb'))
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(f'corner_{name}', None)
    col.objects.link(root)
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
        if o.parent is None:
            o.parent = root
    root.location = pos
    root.rotation_euler = (0, 0, yaw)
    print(f'[corner] {name}: {[o.name for o in new]}', flush=True)
    return root, new


def build():
    sc = FX.new_scene(fps=24, frames=(1, 48))
    col = bpy.data.collections.new('room')
    sc.collection.children.link(col)
    plaster = mat('plaster', (0.53, 0.60, 0.52), rough=0.95)
    floor_m = mat('oak_floor', (0.42, 0.27, 0.15), rough=0.55)
    ceil_m = mat('ceiling', (0.80, 0.79, 0.76), rough=0.95)
    t = 0.12
    hx, hy = RW / 2, RD / 2
    # the floor, ceiling and walls as slabs (the back wall, at Blender y = +2, round the window hole)
    slab('floor', (-hx - t, -hy - t, -t), (hx + t, hy + t, 0), floor_m, col)
    slab('ceiling', (-hx - t, -hy - t, RH), (hx + t, hy + t, RH + t), ceil_m, col)
    slab('wall_left', (-hx - t, -hy, 0), (-hx, hy, RH), plaster, col)
    slab('wall_right', (hx, -hy, 0), (hx + t, hy, RH), plaster, col)
    slab('wall_front', (-hx, -hy - t, 0), (hx, -hy, RH), plaster, col)
    wx0, wx1 = WIN['x'] - WIN['w'] / 2, WIN['x'] + WIN['w'] / 2
    wz0, wz1 = WIN['y'] - WIN['h'] / 2, WIN['y'] + WIN['h'] / 2
    slab('wall_back_l', (-hx, hy, 0), (wx0, hy + t, RH), plaster, col)
    slab('wall_back_r', (wx1, hy, 0), (hx, hy + t, RH), plaster, col)
    slab('wall_back_sill', (wx0, hy, 0), (wx1, hy + t, wz0), plaster, col)
    slab('wall_back_head', (wx0, hy, wz1), (wx1, hy + t, RH), plaster, col)
    # the corner set's models
    glb('desk', B(-1.58, 0, -1.69), 0.0, col)
    glb('window', B(WIN['x'], WIN['y'], -RD / 2), 0.0, col)
    glb('chair', B(-1.50, 0, -1.10), math.pi + 0.22, col)
    glb('rug', B(-1.30, 0, -0.95), 0.06, col)
    _lamp_root, lamp = glb('lamp', B(-1.93, DESK_TOP, -1.76), 0.3, col)
    glb('mug', B(-1.08, DESK_TOP, -1.43), 0.4, col)
    glb('books', B(-2.00, DESK_TOP, -1.46), 0.35, col)
    # the spheres on the floor and a glass pane: chrome, rough metal, white
    for name, pos, m in (('chrome', (-0.55, 0.55, 0.16), mat('chrome', (0.95, 0.95, 0.95), rough=0.04, metal=1.0)),
                         ('rough_metal', (-0.15, 0.25, 0.16), mat('brushed', (0.9, 0.86, 0.8), rough=0.42, metal=1.0)),
                         ('white', (0.3, 0.6, 0.16), mat('white', (0.8, 0.8, 0.8), rough=0.6))):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.16, location=pos, segments=64, ring_count=32)
        s = bpy.context.object
        s.name = name
        bpy.ops.object.shade_smooth()
        s.data.materials.append(m)
        for c in list(s.users_collection):
            c.objects.unlink(s)
        col.objects.link(s)
    slab('glass_pane', (0.7, 0.2, 0.0), (1.1, 0.215, 0.62), mat('glass', (1, 1, 1), rough=0.0, transmission=1.0), col)
    # the world outside: a uniform sky blue (the sky family's make_sky is the real one)
    w = bpy.data.worlds.new('outside')
    sc.world = w
    if w.node_tree is None:
        w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.45, 0.6, 0.85, 1.0)
    bg.inputs['Strength'].default_value = 0.35
    # the evening sun through the window (from beyond the back wall, low, warm)
    L.sun(sc, elevation_deg=14, azimuth_deg=20, strength=2.2, kelvin_k=3600, name='sun')
    # the lamp: its bulb a practical (glows + a real point light in it); its shade casts shadow (pool and scallop)
    bulb = next((o for o in lamp if 'bulb' in o.name.lower()), None)
    shade = next((o for o in lamp if 'shade' in o.name.lower()), None)
    REPORT['lamp_parts'] = [o.name for o in lamp]
    if bulb is None:
        raise RuntimeError(f'no bulb in corner_lamp.glb: {[o.name for o in lamp]}')
    bpy.context.view_layer.update()
    lt = L.practical(sc, bulb, watts=6.0, kelvin_k=2700, strength=40.0, kind='POINT')
    if shade is not None:
        shade.visible_shadow = True
        for slot in shade.material_slots:       # light through linen: a warm glow on the shade itself
            p = next((n for n in slot.material.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
            if p:
                p.inputs['Emission Color'].default_value = (*L.blackbody_rgb(2700), 1.0)
                p.inputs['Emission Strength'].default_value = 0.6
    # probes: a volume probe for the room's bounce (its outer samples inside the walls, floor and ceiling: a probe that
    # stops at the walls fades them to the world's light), a sphere probe for its reflections
    REPORT['volume_probe'] = L.add_room_probe(sc, 'room_volume', (-hx, -hy, 0.0), (hx, hy, RH), wall=t, spacing=0.35,
                                              samples=1024).name
    L.add_sphere_probe(sc, 'room_sphere', (-0.5, 0.6, 1.0), radius=3.0)
    # indoors the baked probe carries the bounce: fast GI's screen-space scan, in either mode, lit the floor contacts
    # and the wall bases with the world through the walls (a blue crescent under the white sphere, bright strips,
    # grain); with it off EEVEE agreed with Cycles (measured 11-07)
    L.create_rt_lighting(sc, refl_max_rough=0.6, gi=False)
    REPORT['lights'] = L.log_lights(sc)
    # cameras: the corner (wide), the spheres (close, low)
    cams = bpy.data.collections.new('cameras')
    sc.collection.children.link(cams)
    wide = C.make_camera('cam_corner', lens=24, fstop=5.6, collection=cams, scene=sc)
    C.hold(sc, wide, (1, 24), (0.9, -1.75, 1.45), (-1.25, 1.35, 0.85))
    C.focus_on(sc, wide, (1, 24), (-1.6, 1.5, 0.9))
    close = C.make_camera('cam_spheres', lens=50, fstop=4.0, collection=cams, scene=sc)
    C.hold(sc, close, (25, 48), (0.55, -1.3, 0.42), (-0.25, 0.45, 0.16))
    C.focus_on(sc, close, (25, 48), bpy.data.objects['rough_metal'])
    C.add_shot(sc, 'corner', 1, wide)
    C.add_shot(sc, 'spheres', 25, close)
    RS.apply_auto_enhance(sc, 'film', ao=False)
    corner = [bpy.data.objects[n] for n in ('corner_desk', 'corner_chair', 'corner_lamp', 'corner_rug')]
    REPORT['framing'] = CA.framing_audit(sc, subject=corner, frames=[12, 36])
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f'[corner] saved {BLEND}', flush=True)


def render():
    bpy.ops.wm.open_mainfile(filepath=BLEND, load_ui=False)
    sc = bpy.context.scene
    RS.apply_auto_enhance(sc, 'probe', ao=False)
    REPORT['bake'] = L.bake_light_probes(sc)
    sc.frame_set(12)
    sc.camera = C.camera_at(sc, 12)
    ae = EX.auto_expose(sc, os.path.join(OUT, 'sweep'))
    REPORT['exposure'] = {'set': ae['exposure'], 'reason': ae['pick']['reason'], 'ceiling': ae['pick']['ceiling']}
    rows = P.render_stills(sc, frames=[12, 36], out_dir=OUT, name='corner')
    REPORT['stills'] = [{k: r[k] for k in ('frame', 'camera', 'path', 'seconds', 'highlights')} for r in rows]
    # the ground truth: the same two stills path traced in Cycles (same lights, materials, exposure)
    refs = []
    for r in rows:
        p = os.path.join(OUT, f"corner_cycles_f{r['frame']}.png")
        REPORT.setdefault('cycles_s', {})[r['frame']] = round(P.render_reference(sc, p, r['frame'], samples=512), 1)
        refs.append(p)
    FS.sheet([rows[0]['path'], refs[0], rows[1]['path'], refs[1]], os.path.join(OUT, 'corner_vs_cycles_sheet.jpg'),
             cols=2, tile=640, labels=['EEVEE frame 12', 'Cycles 512 spp frame 12', 'EEVEE frame 36', 'Cycles frame 36'])
    # noise against samples: the spheres at 16 (the probe preset), 32 (the film's) and 64
    import time as _t
    for n in (32, 64):
        sc.eevee.taa_render_samples = n
        t0 = _t.perf_counter()
        P.render_still(sc, os.path.join(OUT, f'corner_f36_{n}spp.png'), 36)
        REPORT[f'spheres_{n}spp_s'] = round(_t.perf_counter() - t0, 2)
    sc.eevee.taa_render_samples = 16
    # the same corner without the volume probe's bake: what the bake brings (the room's bounce)
    keep = sc.render.filepath
    for o in sc.objects:
        if o.type == 'LIGHT_PROBE' and o.data.type == 'VOLUME':
            o.hide_render = True
    P.render_still(sc, os.path.join(OUT, 'corner_no_volume_probe.png'), 12)
    sc.render.filepath = keep
    FS.sheet([rows[0]['path'], os.path.join(OUT, 'corner_no_volume_probe.png'), rows[1]['path']],
             os.path.join(OUT, 'corner_sheet.jpg'), cols=3, tile=640,
             labels=['corner (volume probe baked)', 'corner, volume probe off', 'spheres'])


if STAGE in ('build', 'all'):
    build()
if STAGE in ('render', 'all'):
    render()
with open(os.path.join(OUT, f'report_{STAGE}.json'), 'w', encoding='utf-8') as fh:
    json.dump(REPORT, fh, indent=1, default=str)
print(f'[corner] {STAGE} done', flush=True)
