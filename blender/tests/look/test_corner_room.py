"""tests/look/test_corner_room.py: the lighting helpers in a room. The corner set's own models (eidoverse/assets/models/
corner_*.glb, laid out as eidoverse/sets/corner.js lays them, in Blender axes) in a plaster room with a window: low
evening sun through the window, the desk lamp as a PRACTICAL (its bulb glows and a real light sits in it; the shade
casts the shadow that makes the pool below and the scallop above), a uniform sky-blue world outside (no stock sky), a
chrome, a rough-metal and a white sphere on the floor and a glass pane.

The room is built the way EEVEE lights an interior: a closed shell of solid walls (0.3 m: the floor and ceiling slabs
run under and over the walls, the walls meet at the corners, every piece a closed box with its normals out), a
volume probe fitted to it (look.lighting.add_room_probe: its outermost samples inside the walls) and baked, a sphere
probe whose box is the room, and global illumination on (fast GI, the film preset's).

Judge: contact darkening under the chair and spheres; the lamp reading as the source of its light; the sun patch's
soft edge (the sun's real angle); chrome reflecting the room (not black); colour bleed from the rug; AgX roll-off on
the sunlit floor; the light inventory in the log. Checks (PASS / FAIL): fast GI on; no sky light at the wall bases or
under the white sphere (the warm room's floor strips and the sphere's underside no bluer than their neighbours); the
plaster walls without the grain of shading half-lit by the World; the volume probe's bake bringing the room's bounce.
    bash run_blender.sh blender/tests/look/test_corner_room.py --stage build
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <this> --stage render
    bash run_blender.sh <this> --stage measure          # the checks again on the stills on disk (no GPU)
"""
import json
import math
import os
import sys

import bpy
import numpy as np
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
FAILS = []
MODELS = os.path.join(FX.ASSETS, 'models')
# corner.js's layout (three, metres) -> Blender: (x, y, z) -> (x, -z, y); a yaw about three's +Y is the same yaw
# about Blender's +Z
RW, RD, RH = 4.4, 4.0, 2.7
WALL = 0.3
WIN = {'x': -1.36, 'y': 1.60, 'w': 1.0, 'h': 1.25}
DESK_TOP = 0.76


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''), flush=True)
    REPORT.setdefault('checks', []).append({'check': name, 'ok': bool(ok), 'detail': detail})
    if not ok:
        FAILS.append(name)
    return ok


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
        # thin glass: ray-traced refraction through a slab of the pane's thickness
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
    """A closed axis-aligned box from lo to hi (Blender metres), its normals out."""
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
    t = WALL
    hx, hy = RW / 2, RD / 2
    # a closed shell: the floor and ceiling slabs run under and over the walls, the side walls run past the corners,
    # and the back wall (Blender y = +2) stands round the window's hole
    slab('floor', (-hx - t, -hy - t, -t), (hx + t, hy + t, 0), floor_m, col)
    slab('ceiling', (-hx - t, -hy - t, RH), (hx + t, hy + t, RH + t), ceil_m, col)
    slab('wall_left', (-hx - t, -hy - t, 0), (-hx, hy + t, RH), plaster, col)
    slab('wall_right', (hx, -hy - t, 0), (hx + t, hy + t, RH), plaster, col)
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
    L.practical(sc, bulb, watts=6.0, kelvin_k=2700, strength=40.0, kind='POINT')
    if shade is not None:
        shade.visible_shadow = True
        for slot in shade.material_slots:       # light through linen: a warm glow on the shade itself
            p = next((n for n in slot.material.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)
            if p:
                p.inputs['Emission Color'].default_value = (*L.blackbody_rgb(2700), 1.0)
                p.inputs['Emission Strength'].default_value = 0.6
    # probes: a volume probe fitted to the room (its outermost samples inside the walls, floor and ceiling) for the
    # room's bounce, and a sphere probe whose box is the room for its reflections
    vp = L.add_room_probe(sc, 'room_volume', (-hx, -hy, 0.0), (hx, hy, RH), wall=t, samples=1024)
    REPORT['volume_probe'] = {'name': vp.name, 'resolution': [vp.data.resolution_x, vp.data.resolution_y,
                                                              vp.data.resolution_z],
                              'box': [list(vp.location), list(vp.scale)], 'escape_bias': vp.data.escape_bias}
    L.add_sphere_probe(sc, 'room_sphere', (0.0, 0.0, 1.2), box=(RW + t, RD + t, RH + t), falloff=0.1)
    try:
        L.create_rt_lighting(sc, gi=False)
        refused = False
    except ValueError:
        refused = True
    L.create_rt_lighting(sc, refl_max_rough=0.6)
    ee = sc.eevee
    check('create_rt_lighting: fast GI on inside screen-traced ray tracing; gi=False is refused',
          refused and ee.use_fast_gi and ee.use_raytracing and ee.ray_tracing_method == 'SCREEN',
          f'refused {refused}, fast GI {ee.use_fast_gi}, ray tracing {ee.use_raytracing} ({ee.ray_tracing_method})')
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
    RS.apply_auto_enhance(sc, 'film')
    corner = [bpy.data.objects[n] for n in ('corner_desk', 'corner_chair', 'corner_lamp', 'corner_rug')]
    REPORT['framing'] = CA.framing_audit(sc, subject=corner, frames=[12, 36])
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f'[corner] saved {BLEND}', flush=True)


# ------------------------------------------------------------------------------------------------ the measures
def _pixels(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)[::-1, :, :3]          # rows top-down; the PNG's display values


def _project(sc, frame, pts, size):
    """World points -> pixel (x, y) in an image of `size` (w, h), top-left origin, through the frame's camera."""
    from bpy_extras.object_utils import world_to_camera_view
    sc.frame_set(frame)
    cam = C.camera_at(sc, frame)
    W, H = size
    out = []
    for p in pts:
        c = world_to_camera_view(sc, cam, Vector(p))
        out.append((int(round(c.x * W)), int(round((1 - c.y) * H))))
    return out


def _region(px, xy, r=3):
    """mean RGB of the (2r + 1)^2 pixels round xy, or None when they are not all in the frame"""
    x, y = xy
    h, w = px.shape[:2]
    if not (r <= x < w - r and r <= y < h - r):
        return None
    return px[y - r:y + r + 1, x - r:x + r + 1].reshape(-1, 3).mean(0)


def _strip(sc, px, frame, pts):
    """mean RGB over the pixels of a line of world points (those in the frame: at least half of them)"""
    got = [g for g in (_region(px, xy) for xy in _project(sc, frame, pts, (px.shape[1], px.shape[0]))) if g is not None]
    if len(got) * 2 < len(pts):
        raise RuntimeError(f'only {len(got)} of {len(pts)} measuring points are in frame {frame}')
    return np.mean(got, 0)


def _blue(rgb):
    """the sky's tint in a warm room: blue's share of the pixel, whatever its brightness (contact shadow darkens a
    wall base without changing its hue; light from the sky turns it blue)"""
    return float(rgb[2] / max(float(np.sum(rgb)), 1e-4))


def leak_measures(sc, wide_png, close_png):
    """Floor strips 4 cm from the left and back walls' bases against the floor 60 cm out; the white sphere's
    underside against its side; the back wall's grain (each pixel's departure from its 3 x 3 mean)."""
    hx, hy = RW / 2, RD / 2
    pw, pc = _pixels(wide_png), _pixels(close_png)
    m = {}
    ys = np.linspace(-0.6, 1.2, 10)                  # along the left wall, short of the rug and the desk
    xs = np.linspace(-0.1, 1.2, 10)                  # along the back wall, right of the rug
    m['left_base'] = _strip(sc, pw, 12, [(-hx + 0.04, y, 0.0) for y in ys])
    m['left_open'] = _strip(sc, pw, 12, [(-hx + 0.6, y, 0.0) for y in ys])
    m['back_base'] = _strip(sc, pw, 12, [(x, hy - 0.04, 0.0) for x in xs])
    m['back_open'] = _strip(sc, pw, 12, [(x, hy - 0.6, 0.0) for x in xs])
    c, r = Vector((0.3, 0.6, 0.16)), 0.16
    cam = C.camera_at(sc, 36).matrix_world.translation
    to_cam = (cam - c)
    to_cam.z = 0
    to_cam.normalize()
    side = Vector((-to_cam.y, to_cam.x, 0.0))
    under, mid = [], []
    for k in np.linspace(-0.5, 0.5, 7):
        d = (to_cam + side * float(k)).normalized()
        under.append(c + (d * math.sin(math.radians(140)) + Vector((0, 0, math.cos(math.radians(140))))) * r)
        mid.append(c + (d * math.sin(math.radians(80)) + Vector((0, 0, math.cos(math.radians(80))))) * r)
    m['sphere_under'] = _strip(sc, pc, 36, under)
    m['sphere_side'] = _strip(sc, pc, 36, mid)
    # the back wall's grain, right of the window at mid height
    (x0, y0), (x1, y1) = _project(sc, 12, [(0.2, hy, 1.9), (1.4, hy, 1.2)], (pw.shape[1], pw.shape[0]))
    patch = pw[min(y0, y1):max(y0, y1), min(x0, x1):max(x0, x1)].mean(2)
    k = sum(np.roll(np.roll(patch, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9.0
    d = (patch - k)[2:-2, 2:-2]
    m['wall_grain'] = float(np.sqrt((d * d).mean())) if d.size else float('nan')
    return {k_: (v.tolist() if isinstance(v, np.ndarray) else v) for k_, v in m.items()}


def render():
    bpy.ops.wm.open_mainfile(filepath=BLEND, load_ui=False)
    sc = bpy.context.scene
    RS.apply_auto_enhance(sc, 'probe')
    ee = sc.eevee
    check('global illumination on: fast GI inside EEVEE\'s ray tracing', ee.use_fast_gi and ee.use_raytracing and
          ee.ray_tracing_options.trace_max_roughness < 1.0,
          f'fast GI {ee.use_fast_gi} ({ee.fast_gi_method}), ray tracing {ee.use_raytracing}')
    REPORT['bake'] = L.bake_light_probes(sc)
    sc.frame_set(12)
    sc.camera = C.camera_at(sc, 12)
    ae = EX.auto_expose(sc, os.path.join(OUT, 'sweep'))
    REPORT['exposure'] = {'set': ae['exposure'], 'reason': ae['pick']['reason'], 'ceiling': ae['pick']['ceiling']}
    rows = P.render_stills(sc, frames=[12, 36], out_dir=OUT, name='corner')
    REPORT['stills'] = [{k: r[k] for k in ('frame', 'camera', 'path', 'seconds', 'highlights')} for r in rows]
    # noise against samples: the spheres at 16 (the probe preset), 32 (the film's) and 64
    import time as _t
    for n in (32, 64):
        ee.taa_render_samples = n
        t0 = _t.perf_counter()
        P.render_still(sc, os.path.join(OUT, f'corner_f36_{n}spp.png'), 36)
        REPORT[f'spheres_{n}spp_s'] = round(_t.perf_counter() - t0, 2)
    ee.taa_render_samples = 16
    # the same corner without the volume probe: the world lights the room as if it had no walls (what the bake brings
    # is the room's own bounce, and the walls holding the sky out)
    keep = sc.render.filepath
    for o in sc.objects:
        if o.type == 'LIGHT_PROBE' and o.data.type == 'VOLUME':
            o.hide_render = True
    P.render_still(sc, NO_PROBE, 12)
    sc.render.filepath = keep
    for o in sc.objects:
        if o.type == 'LIGHT_PROBE' and o.data.type == 'VOLUME':
            o.hide_render = False
    FS.sheet([rows[0]['path'], NO_PROBE, rows[1]['path']], os.path.join(OUT, 'corner_sheet.jpg'), cols=3, tile=640,
             labels=['corner (volume probe baked)', 'corner, volume probe off', 'spheres'])
    measure(sc)


NO_PROBE = os.path.join(OUT, 'corner_no_volume_probe.png')


def measure(sc=None):
    """The light checks on the stills on disk (corner_probe_at0.46s.png, ..._at1.46s.png, the no-probe still)."""
    if sc is None:
        bpy.ops.wm.open_mainfile(filepath=BLEND, load_ui=False)
        sc = bpy.context.scene
    wide, close = (os.path.join(OUT, P.still_name('corner', (f - sc.frame_start) / C.fps_of(sc))) for f in (12, 36))
    m = leak_measures(sc, wide, close)
    REPORT['measures'] = m
    tol = 0.03
    for wall in ('left', 'back'):
        b, o = m[f'{wall}_base'], m[f'{wall}_open']
        check(f'no sky light at the {wall} wall\'s base: the floor there no bluer than 60 cm out',
              _blue(b) <= _blue(o) + tol, f'blue share {_blue(b):.3f} at the base, {_blue(o):.3f} out; '
              f'luma {np.mean(b):.3f} / {np.mean(o):.3f}')
    su, ss = m['sphere_under'], m['sphere_side']
    check('no sky light under the white sphere: its underside no bluer than its side', _blue(su) <= _blue(ss) + tol,
          f'blue share {_blue(su):.3f} under, {_blue(ss):.3f} side')
    check('the back wall without the grain of light from outside the room', m['wall_grain'] < 0.012,
          f'grain {m["wall_grain"]:.4f}')
    pts = [(x, 1.0, 0.0) for x in np.linspace(-0.1, 1.2, 10)]
    floor_with, floor_without = _strip(sc, _pixels(wide), 12, pts), _strip(sc, _pixels(NO_PROBE), 12, pts)
    check('the baked probe holds the room: without it the floor turns sky-blue',
          _blue(floor_without) > _blue(floor_with) + 0.05,
          f'blue share {_blue(floor_with):.3f} baked, {_blue(floor_without):.3f} without the probe')


if STAGE in ('build', 'all'):
    build()
if STAGE in ('render', 'all'):
    render()
if STAGE == 'measure':
    measure()
REPORT['fails'] = FAILS
with open(os.path.join(OUT, f'report_{STAGE}.json'), 'w', encoding='utf-8') as fh:
    json.dump(REPORT, fh, indent=1, default=str)
print(f'[corner] {STAGE} done' + (f': {len(FAILS)} FAIL' if FAILS else ''), flush=True)
if FAILS:
    sys.exit(1)
