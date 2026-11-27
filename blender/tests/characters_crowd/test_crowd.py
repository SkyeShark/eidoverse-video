"""The crowd tools (eidoblend.characters.crowd): a small column of the public robot body marching on the beat with a
lantern in its right hand, and a small crowd waving in canon with a hold, each built, checked and shown in two stills.
Blender (a GPU job: EEVEE, 960 x 540, 16 samples):

    bash run_blender.sh blender/tests/characters_crowd/test_crowd.py [--no-render] [--vrm claude_robot] [--bpm 116]

Checks (PASS / FAIL):
  1. the stride: its poses, its length the clip's own on this body within 1 %, its seam (the pose one stride on
     against the first, in its own moving frame) under 1 mm, the vertex order checked
  2. the column's feet: two bodies' floor points through 48 film frames never slide over 1 mm while they stay down
  3. the column's instancer: every point shows the pose its phase asks for, a lantern with every body, no body before
     Show From
  4. the lanterns hang plumb (their up axis within 0.5 degrees of the world's) and stay with the hand
  5. the canon: every point shows the pose its start asks for before, through and after the hold, and the body stopped
     alone holds its pose from its stop on
  6. the stills (out/crowd_*.png): written, neither black nor blown
A PASS is not a look: open the stills.
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend import common  # noqa: E402
from eidoblend.characters import crowd, load_vrm  # noqa: E402

OUT = os.path.join(HERE, 'out')
FAILS = []
R = {'started': time.strftime('%Y-%m-%d %H:%M:%S')}


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def mat(name, rgb, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1.0)
        b.inputs['Emission Strength'].default_value = strength
    return m


def lantern_object():
    """a small hand lantern as one mesh, its origin at the top of its wire bail (where the fist holds it), hanging
    below: a base, a glass with a warm light in it, a cap, the bail (a tube along a half ring)"""
    import bmesh
    bm = bmesh.new()

    def cyl(r1, r2, z0, z1, mi, seg=24):
        g = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=z1 - z0,
                                  matrix=Matrix.Translation((0.0, 0.0, (z0 + z1) / 2.0)))
        for f in {f for v in g['verts'] for f in v.link_faces}:
            f.material_index = mi
    cyl(0.062, 0.062, -0.300, -0.282, 0)          # the base
    cyl(0.048, 0.048, -0.282, -0.150, 1)          # the glass
    cyl(0.066, 0.020, -0.150, -0.110, 0)          # the cap
    # the bail: a tube along a half ring over the cap, its top at the origin (in the fist)
    rad, r_w, n_a, n_t = 0.050, 0.0032, 20, 8
    rings = []
    for i in range(n_a + 1):
        a = math.pi * i / n_a
        c = Vector((-rad * math.cos(a), 0.0, -0.115 + (0.115 - 0.0) * math.sin(a)))
        t = Vector((rad * math.sin(a), 0.0, 0.115 * math.cos(a))).normalized()
        nrm = Vector((0.0, 1.0, 0.0))
        bi = t.cross(nrm)
        rings.append([bm.verts.new(c + (nrm * math.cos(2 * math.pi * k / n_t) + bi * math.sin(2 * math.pi * k / n_t)) * r_w)
                      for k in range(n_t)])
    for i in range(n_a):
        for k in range(n_t):
            f = bm.faces.new((rings[i][k], rings[i][(k + 1) % n_t], rings[i + 1][(k + 1) % n_t], rings[i + 1][k]))
            f.material_index = 0
    me = bpy.data.meshes.new('lantern')
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat('lantern.metal', (0.05, 0.05, 0.045), 0.38, 0.9))
    me.materials.append(mat('lantern.glass', (0.9, 0.75, 0.5), 0.2, 0.0, (1.0, 0.62, 0.28), 6.0))
    for p in me.polygons:
        p.use_smooth = True
    return me


def stage(sc):
    """a level floor, a low warm sun, a cool sky"""
    fl = bpy.data.meshes.new('floor')
    s = 80.0
    fl.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    fl.materials.append(mat('floor', (0.16, 0.155, 0.15), 0.7))
    sc.collection.objects.link(bpy.data.objects.new('floor', fl))
    sun = bpy.data.lights.new('sun', 'SUN')
    sun.energy, sun.angle, sun.color = 3.2, math.radians(2.0), (1.0, 0.86, 0.7)
    so = bpy.data.objects.new('sun', sun)
    so.rotation_euler = (math.radians(62.0), 0.0, math.radians(-128.0))
    sc.collection.objects.link(so)
    w = bpy.data.worlds.new('sky')
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.36, 0.45, 0.62, 1.0)
    bg.inputs['Strength'].default_value = 0.55
    sc.world = w
    r, ee = sc.render, sc.eevee
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = 960, 540, 100
    ee.taa_render_samples = 16
    ee.use_shadows = True
    ee.use_raytracing = True
    ee.use_fast_gi = True
    sc.view_settings.view_transform = 'AgX'
    r.image_settings.file_format = 'PNG'


def camera(sc, name, pos, aim, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_width, cd.clip_start, cd.clip_end = lens, 36.0, 0.05, 500.0
    ob = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(ob)
    ob.location = pos
    ob.rotation_euler = (Vector(aim) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def still(sc, cam, frame, name):
    sc.frame_set(frame)
    sc.camera = cam
    p = os.path.join(OUT, f'crowd_{name}.png')
    sc.render.filepath = p
    t = time.time()
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p, check_existing=False)
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)[:, :3]
    m, hi = float(px.mean()), float((px > 0.98).mean())
    bpy.data.images.remove(img)
    check(0.02 < m < 0.9 and hi < 0.05, f'{os.path.basename(p)}: mean {m:.3f}, blown {hi * 100:.2f} % ({time.time() - t:.1f} s)')
    R.setdefault('stills', []).append(p)


def local(M, p):
    return tuple(M @ Vector(p))


def main():
    a = common.script_args()
    vrm = a[a.index('--vrm') + 1] if '--vrm' in a else 'claude_robot'
    bpm = float(a[a.index('--bpm') + 1]) if '--bpm' in a else 116.0
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps, sc.render.fps_base = 24, 1.0
    stage(sc)
    t0 = time.time()
    me = load_vrm(vrm, name='donor')
    R['load_s'] = round(time.time() - t0, 1)

    # 1. the stride, the lantern in the right fist
    lamp = crowd.HeldProp(lantern_object(), bone='rightHand', grip='fist', hang=True, name='lantern')
    t = time.time()
    cyc = crowd.stride_cycle(me, 'walk', bpm=bpm, poses_per_frame=2, props=[lamp], curl={'right': 80.0},
                             face={'happy': 1.0}, name='march')
    R['stride'] = {k: v for k, v in cyc.record.items() if not isinstance(v, dict)}
    R['stride_s'] = round(time.time() - t, 1)
    n = cyc.poses
    check(n == int(round(2 * 120.0 * 24 / bpm)) or n == int(round(120.0 * 24 / bpm * 2)), f'the stride: {n} poses at {bpm:g} bpm '
          f'({cyc.stride_frames:g} film frames, {cyc.record["bpm_used"]} bpm used)')
    check(abs(cyc.stride - cyc.record['clip_stride_m']) < 0.01 * cyc.record['clip_stride_m'],
          f'its length {cyc.stride:.4f} m, the clip\'s own on this body {cyc.record["clip_stride_m"]} m')
    check(cyc.record['seam_mm'] < 1.0, f'the seam: the pose one stride on against the first, {cyc.record["seam_mm"]} mm')
    check(cyc.record['vertex_order_checked_on'] == 3, f'every checked pose names pose 0\'s vertices ({cyc.record["verts"]} '
          f'vertices, {cyc.record["tris"]} triangles a pose)')

    # 2-4. the column: 3 files of 6 ranks marching toward +X, the head's middle at the origin on the ref frame
    ref, show = 1.0, (10.0, 4000.0)
    pts = crowd.formation(files=3, ranks=6, interval=0.85, distance=1.05, origin=(0.0, 0.0, 0.0), heading=90.0,
                          jitter={'lateral': 0.03, 'along': 0.05, 'phase': 0.03, 'seed': 11})
    col = crowd.crowd_object('column', pts, crowd.column_group(cyc, ref_frame=ref, show=show))
    fs = [crowd.feet_slide(col, cyc, list(range(40, 88)), point=p) for p in (0, 10)]
    R['feet'] = fs
    check(all(f['worst_slide_mm'] < 1.0 and f['pairs'] >= 40 for f in fs),
          f'the feet stay planted: the contact\'s worst slip {[f["worst_slide_mm"] for f in fs]} mm a frame over '
          f'{[f["pairs"] for f in fs]} pairs on the ground (frames 40-87; the soles\' roll about it moves other points up '
          f'to {[f["worst_spread_mm"] for f in fs]} mm)')
    sp = [crowd.shown_poses(col, cyc, f) for f in (37, 61)]
    check(all(s['wrong'] == 0 and s['found'] == len(pts) for s in sp), f'every point shows the pose its phase asks for: {sp}')
    ins = crowd.instances_at(col, 61)
    lamps = [(nm, M) for nm, M in ins if '.lantern.' in nm]
    bodies = [(nm, M) for nm, M in ins if '.body.' in nm]
    check(len(lamps) == len(bodies) == len(pts), f'a lantern with every body: {len(bodies)} bodies, {len(lamps)} lanterns')
    check(not crowd.instances_at(col, 5), 'nothing before Show From')
    tilt = max(math.degrees(Vector(M.col[2][:3]).normalized().angle(Vector((0, 0, 1)))) for _nm, M in lamps)
    check(tilt < 0.5, f'the lanterns hang plumb: the largest tilt {tilt:.3f} deg')
    # the lantern stays with the hand: its bail's top is where the fist is, on every pose (the pose's own record)
    gaps = []
    for i, ob in enumerate(sorted(cyc.props['lantern'].objects, key=lambda o: o.name)):
        gaps.append(ob.matrix_world.translation.copy())
    step = max((gaps[i + 1] - gaps[i]).length for i in range(len(gaps) - 1))
    check(step < 0.08, f'the grip moves with the swinging hand, at most {step * 1000:.1f} mm a pose')

    # 5. the canon: the same donor, a one-shot clip; 2 lines of 5, a hold, one body stopped alone
    crowd.reset_donor(me)
    t = time.time()
    wave = crowd.once_flipbook(me, 'wave_goodbye', every=2, name='wave')
    R['wave'] = {k: v for k, v in wave.record.items() if k != 'pose_frames'}
    R['wave_s'] = round(time.time() - t, 1)
    crowd.drop_donor(me)
    g = crowd.grid(lines=2, units=5, line_pitch=2.2, unit_pitch=1.25, origin=(0.0, 14.0, 0.0), heading=0.0)
    starts = crowd.canon_starts(g, first=12, step_line=10, step_unit=4)
    hold = (64.0, 24.0)
    stops = [None] * len(g)
    stops[3] = 50.0
    cw = crowd.crowd_object('canon', g, crowd.once_group(wave, hold=hold), starts=starts, stops=stops)
    frames = (30, 63, 70, 87, 100)
    sp = {f: crowd.shown_poses(cw, wave, f) for f in frames}
    check(all(s['wrong'] == 0 for s in sp.values()), f'the canon: every point the pose its start asks for on {list(frames)}: '
          f'{ {f: (s["wrong"], s["got_first"]) for f, s in sp.items()} }')
    held = [crowd.shown_poses(cw, wave, f)['got_first'] for f in (64, 76, 88)]
    check(held[0] == held[1] == held[2], f'through the hold every body holds the pose of its first frame: {held}')
    p3 = [int(nm.rsplit('.', 1)[1]) for nm, _M in crowd.instances_at(cw, 110, 'crowd.wave.body.')][3]
    p3b = [int(nm.rsplit('.', 1)[1]) for nm, _M in crowd.instances_at(cw, 51, 'crowd.wave.body.')][3]
    check(p3 == p3b, f'the body stopped alone on 50 holds its pose: {p3b} on 51, {p3} on 110')

    # 6. the stills: the column from the kerb and close on one body; the canon wide and close
    if '--no-render' in a:
        print('[test] --no-render: no stills')
    else:
        f = 61
        head = crowd.instances_at(col, f, 'crowd.march.body.')
        mid = head[1][1]                                        # the head rank's middle file
        hx = mid.translation.x
        still(sc, camera(sc, 'cam_kerb', (hx + 4.6, -4.2, 1.55), (hx - 2.2, 0.0, 0.95), 35.0), f, 'column_kerb_f061')
        still(sc, camera(sc, 'cam_close', local(mid, (0.9, -1.9, 1.35)), local(mid, (-0.12, -0.15, 0.95)), 50.0), f,
              'column_close_lantern_f061')
        still(sc, camera(sc, 'cam_canon', (6.8, 4.6, 3.2), (0.0, 13.0, 0.9), 35.0), 40, 'canon_wide_f040')
        g0 = crowd.instances_at(cw, 40, 'crowd.wave.body.')[0][1]
        still(sc, camera(sc, 'cam_canon_close', local(g0, (0.6, -2.6, 1.45)), local(g0, (0.0, 0.0, 1.2)), 50.0), 40,
              'canon_close_f040')
    R['fails'] = FAILS
    R['seconds'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, 'crowd.json'), 'w', encoding='utf-8') as fh:
        json.dump(R, fh, indent=1, default=str)
    print(f'[test] {len(FAILS)} failed in {R["seconds"]} s', flush=True)
    if FAILS:
        raise SystemExit(1)


main()
