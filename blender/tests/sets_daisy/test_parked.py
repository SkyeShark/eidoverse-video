"""tests/sets_daisy/test_parked.py: each DAISY set built at the origin and PARKED far from it must be the same set, moved.

The film tests build every set at the origin, where a part placed in world space instead of set-local space cannot
show. The WebGPU contract parks a set by its group (the corner's README parks it at three (800, 0, 800)), so this
builds the funeral (with its bridge vignette) and the corner twice, at the origin and parked, and checks:
  - every object of the set (the corner's grass and trees too) sits at its origin-build place + the offset;
  - the set's own cameras (make_cameras, right after build, as the film tests call it) carry the offset;
  - stills from the same set-local views (new angles the film never took: the room from the stage, the vigil from the
    mezzanine, the phones across the crowd, the bridge from the roadway, the camp from above, the room from its far
    corner, the spark in flight) render the same at both places.
The stills double as views of the sets as assets. Writes out/parked/<set>_<view>_{origin,parked}.png.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 24 bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy/test_parked.py [-- --no-render --only funeral|corner]
"""

import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _common as C                                        # noqa: E402

import bpy                                                  # noqa: E402
import numpy as np                                          # noqa: E402
from mathutils import Vector                                # noqa: E402

from eidoblend.look import camera as LC                     # noqa: E402
from eidoblend.sets.daisy import corner as CO               # noqa: E402
from eidoblend.sets.daisy import funeral as FU              # noqa: E402

A = C.args()
FPS = 30
OUT = os.path.join(C.OUT, 'parked')
os.makedirs(OUT, exist_ok=True)
render = 'no-render' not in A['flags']
only = A.get('only')
sc = C.clean_scene(FPS, (1, 60))
C.probe_look(sc, interior=True)
sc.eevee.shadow_pool_size = '2048'

PARK = {'funeral': Vector((137.0, -251.0, 12.0)), 'corner': Vector((800.0, -800.0, 0.0))}   # corner: three (800, 0, 800)


def base(name):
    return re.sub(r'\.\d{3}$', '', name)


def world_of(o):
    """the object's world matrix from its parent chain: matrix_world is stale for an object made after the last
    depsgraph evaluation and never re-evaluated while it is keyed hidden (the room's haze on a bridge frame)"""
    m = o.matrix_basis.copy()
    while o.parent is not None:
        m = o.parent.matrix_basis @ o.matrix_parent_inverse @ m
        o = o.parent
    return m


def places(objs):
    """{name: world position} of every object but the instancing sources (Geometry Nodes reads them in ORIGINAL
    space, so where they stand never shows): a geometry's world bounding-box centre (the flora plants its grass in world
    space under an object at the origin), else the object's origin"""
    out = {}
    for o in objs:
        try:
            if any(c.name.endswith(':sources') for c in o.users_collection):
                continue
            m = world_of(o)
            if o.type in ('MESH', 'CURVE', 'CURVES', 'POINTCLOUD', 'VOLUME'):
                bb = [Vector(c) for c in o.bound_box]
                out[base(o.name)] = m @ (sum(bb, Vector()) / 8.0)
            else:
                out[base(o.name)] = m.translation.copy()
        except ReferenceError:
            pass
    return out


def camera_places(cams, frames):
    out = {}
    for f in frames:
        sc.frame_set(f)
        for k, cam in cams.items():
            if not cam.hide_render:
                out[(k, f)] = cam.matrix_world.translation.copy()
    return out


def drop_cameras(cams):
    for mk in list(sc.timeline_markers):
        sc.timeline_markers.remove(mk)
    for cam in cams.values():
        bpy.data.objects.remove(cam, do_unlink=True)


def still_cam(name, root, pos_b, tgt_b, fov):
    """a camera at set-local (Blender axes) pos looking at tgt, through the set's root."""
    bpy.context.view_layer.update()
    M = root.matrix_world
    cam = LC.make_camera(f'parked:{name}', fov=fov, scene=sc)
    cam.matrix_world = LC.look_matrix(M @ Vector(pos_b), M @ Vector(tgt_b))
    return cam


def shoot(tag, shots):
    """shots: [(view, frame, cam)] -> {view: path}"""
    paths = {}
    for view, f, cam in shots:
        p = os.path.join(OUT, f'{view}_{tag}.png')
        if render:
            sc.frame_set(f)
            sc.camera = cam
            sc.render.filepath = p
            sc.render.image_settings.media_type = 'IMAGE'
            sc.render.image_settings.file_format = 'PNG'
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            print(f'[render] {view} ({tag}, frame {f}) {time.time() - t0:.1f} s', flush=True)
        paths[view] = p
    return paths


def load_px(p):
    img = bpy.data.images.load(p, check_existing=False)
    px = np.empty(img.size[0] * img.size[1] * img.channels, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(-1, 4)[:, :3] * 255.0


def compare(set_name, a, b, off):
    """places / cameras / stills of the origin build (a) and the parked one (b)."""
    pa, pb = a['places'], b['places']
    common = sorted(set(pa) & set(pb))
    missing = sorted(set(pa) ^ set(pb))
    worst = max(((pb[k] - pa[k] - off).length, k) for k in common) if common else (0.0, '')
    if worst[0] >= 2e-3:
        print(f'[parked] {set_name} {worst[1]}: origin {tuple(round(x, 3) for x in pa[worst[1]])} '
              f'parked {tuple(round(x, 3) for x in pb[worst[1]])}', flush=True)
    # 10 cm: the SeedThree wind phases its sway by world position, so a swaying tree's box moves a few cm when parked;
    # a part left behind is off by the whole offset (hundreds of metres)
    C.check(f'{set_name}: every object parked with the set (origin place + offset)',
            worst[0] < 0.1 and not missing, f'{len(common)} objects, worst {worst[0]:.2e} m ({worst[1]})'
            + (f'; only in one build: {missing[:6]}' if missing else ''))
    ca, cb = a['cams'], b['cams']
    keys = sorted(set(ca) & set(cb))
    cw = max(((cb[k] - ca[k] - off).length, k) for k in keys) if keys else (9e9, None)
    C.check(f'{set_name}: make_cameras right after build carries the offset', keys and cw[0] < 2e-3,
            f'{len(keys)} camera samples, worst {cw[0]:.2e} m ({cw[1]})')
    if not render:
        return
    for view in a['stills']:
        x, y = load_px(a['stills'][view]), load_px(b['stills'][view])
        d = np.abs(x - y).max(axis=1)
        mean, big = float(d.mean()), float((d > 24).mean())
        C.check(f'{set_name} {view}: the parked still is the origin still', mean < 1.5 and big < 0.01,
                f'mean |diff| {mean:.2f} / 255, {100 * big:.2f}% of pixels off by > 24')


# ======================================================================================================== funeral
def funeral_run(tag, location):
    t0 = time.time()
    F = FU.build(location=location)
    print(f'[funeral {tag}] built in {time.time() - t0:.1f} s', flush=True)
    cams = F.make_cameras((1, 60), u0=4.0)                     # right after build, as test_funeral calls it
    cam_pos = camera_places(cams, (5, 30, 55))
    drop_cameras(cams)
    fx = F.post.apply(sc)
    # one lighting state per frame: the vigil, the dark with the phones, the golden return, the bridge in fog
    states = [(1, 5.0), (2, 20.0), (3, 32.0), (4, 1.5)]
    keys = None
    for f, u in states:
        k = F.update(u, {'u': u}, frame=f)
        F.post.drive(fx, u, k)
        keys = k if keys is None else keys.merge(k)
    keys.finish()
    root = F.kit.root
    br = FU.BRIDGE_AT
    shots = [
        ('funeral_golden_from_stage', 3, still_cam('stage', root, FU.V(0.0, 2.6, 9.2), FU.V(0.0, 2.1, -11.0), 62)),
        ('funeral_vigil_from_mezzanine', 1, still_cam('mezz', root, FU.V(-5.6, 4.9, -10.4), FU.V(0.4, 0.9, 6.2), 55)),
        ('funeral_phones_across_crowd', 2, still_cam('side', root, FU.V(8.3, 2.1, 1.5), FU.V(-2.0, 1.4, 2.5), 52)),
        ('bridge_from_roadway', 4, still_cam('road', root, FU.V(br[0] - 10.0, br[1] + 1.6, br[2] + 22.0),
                                             FU.V(br[0] - 8.0, br[1] + 55.0, br[2] - 57.0), 52)),
    ]
    stills = shoot(tag, shots)
    objs = list(F.kit.top.all_objects)
    rec = {'places': places(objs), 'cams': cam_pos, 'stills': stills}
    for _v, _f, cam in shots:
        bpy.data.objects.remove(cam, do_unlink=True)
    F.dispose()
    return rec


# ========================================================================================================= corner
def corner_run(tag, location):
    t0 = time.time()
    CR = CO.build(location=location)
    print(f'[corner {tag}] built in {time.time() - t0:.1f} s', flush=True)
    cams = CR.make_cameras((1, 60), u0=CO.B(22))               # the camp's first shot, right after build
    cam_pos = camera_places(cams, (5, 30, 55))
    drop_cameras(cams)
    B = CO.B
    t_spark = CR.spark['t0'] + 0.6 * (CR.spark['t1'] - CR.spark['t0'])
    states = [(1, B(20) + 1.0), (2, B(23) + 0.9), (3, t_spark)]
    keys = None
    for f, u in states:
        k = CR.update(u, {'u': u}, frame=f)
        keys = k if keys is None else keys.merge(k)
    keys.finish()
    root = CR.kit.root
    R, P = CO.ROOM_AT, CO.CAMP_AT
    cs = CR.camera(t_spark)
    shots = [
        ('corner_room_from_far_corner', 1, still_cam('far', root, CO.V(R[0] + 1.95, 1.62, R[2] + 1.8),
                                                     CO.V(R[0] - 1.6, 0.95, R[2] - 1.7), 62)),
        ('corner_camp_from_above', 2, still_cam('above', root, CO.V(P[0] + 7.0, 9.5, P[2] + 9.0),
                                                CO.V(P[0], 0.0, P[2] - 6.5), 56)),
        ('corner_spark_in_flight', 3, still_cam('spark', root, cs['pos'], cs['target'], cs['fov'])),
    ]
    stills = shoot(tag, shots)
    objs = list(CR.kit.top.all_objects) + [o for o in CR.camp.get('extra_objects', []) if o is not None]
    rec = {'places': places(objs), 'cams': cam_pos, 'stills': stills}
    for _v, _f, cam in shots:
        bpy.data.objects.remove(cam, do_unlink=True)
    CR.dispose()
    return rec


if only in (None, 'funeral'):
    a = funeral_run('origin', (0.0, 0.0, 0.0))
    b = funeral_run('parked', tuple(PARK['funeral']))
    compare('funeral', a, b, PARK['funeral'])
if only in (None, 'corner'):
    sc.frame_end = 60
    a = corner_run('origin', (0.0, 0.0, 0.0))
    b = corner_run('parked', tuple(PARK['corner']))
    compare('corner', a, b, PARK['corner'])
sys.exit(1 if C.summary('test_parked') else 0)
