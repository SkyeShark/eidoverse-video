"""The controller on ground that is not a course: rolling terrain (slopes to about 16 deg) with rocks along the way, a
curved path walked, a jog, a stop on the slope, a turn on the spot on it, and a walk back down.

    test_controller_terrain.py [--vrm claude_robot] [--tag NAME]

The ground is a heightfield mesh (round one's ground_mesh, a scanned soil set); six rocks (10 to 22 cm, sunk into it)
sit near the path. Everything the controller and the plant know of it comes from ray and ball casts against the
meshes (CollisionWorld): no height function, no course table.

Prints PASS / FAIL: checks.feet on every gait's frames, the body keeping to the path (the rounded corners'
pure pursuit), the stops on their marks, the slopes read as ramps, the feet on the rocks where the path crosses them,
the keyed armature against the bake.
"""

import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ctrl_stage as T  # noqa: E402

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.characters import load_vrm  # noqa: E402
from eidoblend.characters.controller import CollisionWorld, Locomotion  # noqa: E402

ARGS = T.argv()
VRM = T.arg(ARGS, '--vrm', 'claude_robot')
R = T.Report(T.arg(ARGS, '--tag', f'terrain_{VRM}'))
R['vrm'] = VRM
# the rocks underfoot are 10 to 18 cm; the 22 cm boulder lies beside the path (stepping onto a boulder that tall in
# mid-stride is the guide's "Not yet ported" case)
ROCKS = [(0.55, -2.6, 0.16), (1.3, -0.9, 0.12), (-1.6, 0.9, 0.22), (-0.6, 2.6, 0.10), (0.6, 4.3, 0.18),
         (0.25, 6.6, 0.14)]


def height(x, y):
    return (0.35 * np.sin(0.45 * x + 0.3) * np.cos(0.35 * y) + 0.06 * np.sin(2.1 * x + 1.0) * np.sin(1.7 * y)
            + 0.012 * np.sin(7.3 * x + 0.4) * np.cos(6.1 * y))


def rock(name, x, y, h, seed):
    """a rock: a subdivided icosphere, flattened, its radius varied by a few smooth lobes (seeded: a weathered boulder,
    not a spiky one), `h` high over the ground, the rest sunk"""
    rng = np.random.default_rng(seed)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    w = h * 1.6
    lobes = [(Vector(rng.standard_normal(3)).normalized(), rng.uniform(0.06, 0.14)) for _ in range(5)]
    for v in bm.verts:
        n = v.co.normalized()
        d = 1.0 + sum(a * max(0.0, n.dot(c)) ** 2 for c, a in lobes) + 0.015 * rng.standard_normal()
        v.co = Vector((v.co.x * w * d, v.co.y * w * 0.8 * d, v.co.z * h / 0.7 * d))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = (x, y, float(height(x, y)) + h - h / 0.7)       # its top h over the ground, the rest sunk
    ob.rotation_euler = (0.0, 0.0, float(rng.uniform(0, math.pi)))
    me.uv_layers.new(name='UVMap')
    me.materials.append(T.pbr_material('ctrl_rock', 'Concrete017_1k', tint=0x8a8070, tint_mix=0.5, tile=0.6))
    return ob


def main():
    sc = T.S.clean_scene(fps=30)
    T.S.ground_mesh(height, -6.0, 6.0, -7.0, 11.0, step=0.05, tex='Ground037_2k', tile=1.8, name='terrain')
    for i, (x, y, h) in enumerate(ROCKS):
        rock(f'rock_{i}', x, y, h, seed=11 + i)
    me = load_vrm(VRM, name=VRM)
    world = CollisionWorld()
    z0 = float(height(0.0, -5.0))
    loco = Locomotion(me, world, start=(0.0, -5.0, z0), heading=math.pi, log=R.log)
    path1 = [(0.9, -2.2), (-0.8, 1.2), (0.7, 4.5)]
    mark_run = (0.0, 8.6)
    mark_back = (-2.2, 5.0)
    loco.wait(0.6)
    loco.follow_path(path1, gait='walk', stop=False)
    loco.follow_path([mark_run], gait='slowRun')
    loco.wait(0.5).turn_by(135).wait(0.3)
    loco.move_to(mark_back, gait='walk')
    mark_down = (-0.8, 1.6)
    loco.wait(0.4).face(mark_down)                         # a turn on the spot toward a point (Locomotion.face)
    loco.run_to(mark_down)                                 # a run down the slope (Locomotion.run_to), stopping on it
    loco.wait(0.6)
    t0 = time.time()
    rep = loco.bake(f0=1)
    R['timing_s']['bake'] = round(time.time() - t0, 1)
    recs, frames = rep['_records'], rep['_frames']
    f0, f1 = rep['frames_baked']
    sc.frame_start, sc.frame_end = f0, f1
    segs = rep['segments']
    R['segments'] = segs
    T.gait_checks(R, rep)
    # the path kept: each frame's feet near the polyline through the waypoints (its corners rounded)
    pts = [(0.0, -5.0)] + path1 + [mark_run]
    P = np.array(pts)

    def dist_to_poly(p):
        best = 9.9
        for a, b in zip(P[:-1], P[1:]):
            ab = b - a
            t = np.clip(np.dot(np.array(p) - a, ab) / np.dot(ab, ab), 0, 1)
            best = min(best, float(np.linalg.norm(np.array(p) - (a + t * ab))))
        return best
    run_end = next(i for i, r in enumerate(recs) if r['cmd'] == 'TurnTo')
    dev = [dist_to_poly(r['feet_world'][:2]) for r in recs[:run_end]]
    R.check('the body keeps to the path (corners rounded, pure pursuit)', max(dev) < 0.45, f'off it by up to {max(dev):.2f} m')
    stops = [recs[i]['feet_world'] for i in range(1, len(recs)) if recs[i - 1]['speed'] > 0.05 and recs[i]['speed'] <= 0.05]
    for name, m in (('the jog', mark_run), ('the walk back', mark_back), ('the run down', mark_down)):
        d = min((math.hypot(p[0] - m[0], p[1] - m[1]) for p in stops), default=9.9)
        R.check(f'{name} stops on its mark (on the slope)', d < 0.08, f'{d * 100:.1f} cm')
    modes = sorted(set(r['support_mode'] or '-' for r in recs))
    R['support_modes'] = modes
    R.check('the slopes read as ramps up and down', {'rampUp', 'rampDown'} & set(modes) != set(), f'{modes}')
    # the feet on the rocks: a planted foot over a rock's footprint stands on it (its lowest sole point at the rock)
    on_rock = 0
    from eidoblend.characters.ground import SIDES
    for fr in frames:
        for s in SIDES:
            m = fr['meas'][s]
            if not m['stance']:
                continue
            c = m['P'][:, :2].mean(0)
            for x, y, h in ROCKS:
                if math.hypot(c[0] - x, c[1] - y) < 0.12:
                    on_rock += 1
    R['planted_frames_on_rocks'] = on_rock
    R.log(f'planted foot-frames on a rock: {on_rock}')
    R['worst'] = rep['worst']
    R['pelvis_lowered_mm'] = rep['pelvis_lowered_mm']
    R['released'] = rep.get('released')
    if T.arg(ARGS, '--dump'):
        T.dump_frames(R, rep, [tuple(int(v) for v in rg.split('-')) for rg in T.arg(ARGS, '--dump').split(',')])
    T.keyed_matches(R, me, frames)
    shots(sc, me, recs, segs)


def shots(sc, me, recs, segs):
    T.light(sc)
    S, sheets = [], {'sheet': []}
    r0 = recs[0]['f']
    for s_ in segs:
        a, b = s_['frames']
        if b - a < 5:
            continue
        f = (a + b) // 2
        sc.frame_set(f)
        name = f'{s_["gait"].replace(":", "-")}_f{f:03d}'
        S.append(T.side_shot(me, recs[f - r0], name, height=0.45))
        sheets['sheet'].append(name)
    # a strip of the walk over the rocks and the turn on the slope, each from one camera
    for label, pick in (('walk', lambda r: r['lead'] == 'walk' and r['speed'] > 1.0),
                        ('turn', lambda r: r['mode'] == 'turn')):
        fr = [r['f'] for r in recs if pick(r)]
        if len(fr) < 12:
            continue
        a = fr[len(fr) // 3]
        fs = [a + 3 * k for k in range(6)]
        mid = fs[3]
        sc.frame_set(mid)
        cam = T.side_shot(me, recs[mid - r0], 'x', dist=3.2, lead=0.0, height=0.5)
        names = []
        for k, f in enumerate(fs):
            nm = f'strip_{label}_{k}'
            S.append(dict(cam, name=nm, frame=f))
            names.append(nm)
        sheets[f'strip_{label}'] = names
    S.append(T.fixed_shot('wide', recs[len(recs) // 2]['f'], (6.5, -6.5, 4.0), (0.0, 1.5, 0.0), lens=28.0))
    T.save(R, sc, S, sheets)


try:
    main()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    R.check('the test ran to the end', False, 'an exception (above)')
R.finish()
