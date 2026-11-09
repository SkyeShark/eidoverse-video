"""The locomotion course (eidoblend.course, terrain_base.js): every preset and the course example built and checked,
the example rendered whole (the engine's materials and a dressed variant), every preset on a contact sheet, every
variant scene built, the template's character walk on the expanded course seen through its camera modes with the
engine's telemetry, the course example's whole run (examples/obstacle_course.js), and every variant scene run.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/terrain_extras/test_course.py [--no-render]
        [--parts presets,example,walk,walk_render,example_run,example_run_render,variants] [--walk-to 14.0]
        [--driver controller|walk_path] [--engine-literal] [--save]
    (renders through heavy.sh). The walk's bake is CPU work: run it outside the GPU slot with
    --parts walk --no-render --save (it saves out/course_walk.blend), then render its stills through the slot with
    --parts walk_render; the course example the same way (example_run, then example_run_render). --engine-literal
    walks without the stair-clip flags the engine's constructor never read. variants bakes 4 s of each variant scene
    and renders a still of each (short bakes: run it in the slot).

Checks (PASS/FAIL): piece counts and roles against plan_course; height_at against the geometry (rays straight down
onto the built meshes at 400 points per course, which must agree to 0.1 mm off the risers' edges); segment_at; the
bench, the ladder's rungs and fixture flags; the collider records; add_rigid_bodies; the variant scenes; the
template's walk (the controller by default): soles on the course surface while planted, none deep inside it, the
controller's state on every telemetry frame, the camera keyed every frame, the telemetry summary written.
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
from eidoblend.course import (EXAMPLES, PRESETS, add_bench, add_rigid_bodies, build_course, course_stage,  # noqa
                              plan_course, template)
from eidoblend.course.stage import look_at  # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RENDER = '--no-render' not in ARGS


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


PARTS = (arg('--parts') or 'presets,example,walk').split(',')
FAILS = []


def check(ok, msg):
    print(('PASS ' if ok else 'FAIL ') + msg)
    if not ok:
        FAILS.append(msg)


def new_scene(name, w=960, h=540, samples=16):
    """the context scene, emptied (headless Blender has no window to switch scenes with, and the builders and the
    characters family read bpy.context.scene)"""
    sc = bpy.context.scene
    if sc.rigidbody_world is not None:
        bpy.ops.rigidbody.world_remove()
    for ob in list(sc.objects):
        bpy.data.objects.remove(ob)
    for c in list(sc.collection.children):
        sc.collection.children.unlink(c)
        bpy.data.collections.remove(c)
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.eevee.taa_render_samples = samples
    sc.view_settings.view_transform = 'AgX'
    sc.render.image_settings.file_format = 'PNG'
    sc['probe'] = name
    return sc


def use(sc):
    pass


def render(sc, path):
    if not RENDER:
        return
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    check(os.path.exists(path), 'rendered ' + os.path.basename(path))


def frame_objects(cam, objs, sc, azim_deg=-60.0, elev_deg=28.0, margin=1.08):
    """aim the camera from (azimuth, elevation) so every corner of the objects' bounds is in frame"""
    bpy.context.view_layer.update()            # new objects' matrix_world and bound_box are stale until evaluated
    pts = []
    for o in objs:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    P = np.array([tuple(p) for p in pts])
    c = Vector(tuple((P.min(0) + P.max(0)) / 2))
    a, e = math.radians(azim_deg), math.radians(elev_deg)
    fwd = -Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd).normalized()
    cd = cam.data
    asp = sc.render.resolution_x / sc.render.resolution_y
    if cd.sensor_fit == 'VERTICAL':
        tv = math.tan(cd.angle / 2)
        th = tv * asp
    else:
        th = math.tan(cd.angle / 2)
        tv = th / asp
    d = 0.0
    for p in pts:
        q = p - c
        x, y, z = q.dot(right), q.dot(up), q.dot(fwd)
        d = max(d, abs(x) / th - z, abs(y) / tv - z)
    look_at(cam, tuple(c - fwd * d * margin), tuple(c))


def ray_heights(course, xs, ys):
    """the built meshes' top surface under each point (rays straight down through the evaluated objects)"""
    dg = bpy.context.evaluated_depsgraph_get()
    out = np.zeros(len(xs))
    for i, (x, y) in enumerate(zip(xs, ys)):
        best = 0.0
        for ob in course.objects:
            if ob.get('eido_course_role') in ('ground', 'rail', 'rung') or ob.type != 'MESH':
                continue
            inv = ob.matrix_world.inverted()
            o = inv @ Vector((x, y, 50.0))
            d = (inv.to_3x3() @ Vector((0, 0, -1))).normalized()
            ok, loc, nrm, _idx = ob.ray_cast(o, d, depsgraph=dg)
            if ok:
                best = max(best, (ob.matrix_world @ loc).z)
        out[i] = best
    return out


def check_course(name, course, plan):
    roles = [o['eido_course_role'] for o in course.objects]
    check(len(course.objects) == len(plan.pieces), '%-26s %d objects for %d planned pieces' % (name, len(course.objects),
                                                                                             len(plan.pieces)))
    # height_at against the built geometry, away from vertical faces (risers, wall faces) by 2 cm
    rng = np.random.default_rng(7)
    y0, y1 = course.first_y - 0.5, course.end_y + 0.5
    ys = rng.uniform(y0, y1, 400)
    xs = rng.uniform(-1.4, 1.4, 400)
    edges = []
    for p in course.plan.pieces:
        if p.kind == 'box' and p.role not in ('rail', 'rung', 'ground'):
            hz = p.size[2] / 2
            c = math.cos(p.rot_x)
            for e in (-hz, hz):
                edges.append(-(p.center[2] + e * c))
        if p.kind == 'dome':
            edges += [-(p.center[2] - p.radius), -(p.center[2] + p.radius)]
    keep = np.array([min(abs(y - e) for e in edges) > 0.02 if edges else True for y in ys])
    xs, ys = xs[keep], ys[keep]
    xs = np.where(np.abs(np.abs(xs) - 0.5) < 0.02, xs + 0.05, xs)       # off the 1 m bumps' side faces
    h_fn = course.height_at(xs, ys)
    h_ray = ray_heights(course, xs, ys)
    err = np.abs(h_fn - h_ray)
    domes = any(p.kind == 'dome' for p in course.plan.pieces)
    tol = 0.006 if domes else 1e-4                  # the dome's 32 x 16 facets sit inside the true sphere
    k = int(np.argmax(err))
    check(float(err.max()) <= tol, '%-26s height_at matches the meshes at %d points: max %.2g m (limit %.0g; worst '
          'at x %.3f y %.3f: fn %.4f ray %.4f)' % (name, len(xs), float(err.max()), tol, xs[k], ys[k], h_fn[k],
                                                   h_ray[k]))
    return roles


def part_presets():
    sheet = []
    for name, cfg in list(PRESETS.items()) + [('example_obstacle_course', EXAMPLES['obstacle_course']['config'])]:
        sc = new_scene('pre_' + name, 640, 360, 16)
        use(sc)
        plan = plan_course(cfg)
        course = build_course(cfg, name='c_' + name)
        st = course_stage(sc, course)
        check_course(name, course, plan)
        # frame the whole course from its side, above
        frame_objects(st.camera, [o for o in course.objects if o['eido_course_role'] != 'ground'], sc,
                      azim_deg=-35.0, elev_deg=24.0)
        path = os.path.join(OUT, 'course_preset_%s.png' % name)
        render(sc, path)
        sheet.append((name, path))
    # merge_solids: the large-stairs course's stacked boxes as one watertight solid of the same volume
    import bmesh
    from eidoblend.course import merge_solids
    from eidoblend.course.csg import compute_mesh_volume
    new_scene('merge', 640, 360)
    course = build_course(PRESETS['large_stairs_only'], name='c_merge')
    # the profile x 3 m, plus the 2 mm skirt under every floor-standing box (11 steps and the slab)
    want = 3.0 * (0.26 * sum(0.22 * k for k in range(1, 7)) + 2.0 * 1.32 + 0.26 * sum(0.22 * k for k in range(1, 6)))
    want += 0.002 * 3.0 * (0.26 * 11 + 2.0)
    merged = merge_solids(course)
    bm = bmesh.new()
    bm.from_mesh(merged.data)
    open_e = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    vol = compute_mesh_volume(merged)
    check(open_e == 0 and abs(vol - want) < 1e-4 * want and len([o for o in course.objects
                                                                   if o['eido_course_role'] == 'merged']) == 1,
          'merge_solids: the 11 stacked boxes and the slab become one manifold solid, %.4f m^3 (the profile x 3 m '
          'gives %.4f)' % (vol, want))
    # the template without a character: the example's bench, its follow camera, the telemetry's options
    new_scene('follow', 640, 360)
    sc = bpy.context.scene
    cs = template.CourseScene(sc, example='obstacle_course', character=None, camera_mode='follow',
                              telemetry={'enabled': True, 'sample_every': 2, 'max_frames': 5,
                                         'include_frames': False,
                                         'output_path': os.path.join(OUT, 'course_follow_telemetry.json')})
    cs.setup(frame_start=1)
    for f in range(1, 13):
        sc.frame_set(f)
        cs.frame(None, (f - 1) / 30.0, f)
    cs.cleanup()
    import json
    payload = json.load(open(os.path.join(OUT, 'course_follow_telemetry.json')))
    pos, tgt = template.camera_pose('follow', (0.0, -5.0, 0.9), None, {'R': 5.2, 'A': 0.0})
    check(cs.course.bench is not None and len(cs.frames) == 5 and payload['frames'] is None
          and abs(pos[0] - 5.2) < 1e-9 and abs(pos[2] - (0.9 + 0.45 + 5.2 * 0.07)) < 1e-9 and abs(tgt[2] - 0.6) < 1e-9,
          'template: the example builds its bench; follow camera at R 5.2, 0.45 + 0.07 R up, looking 0.3 m below the '
          'body; telemetry sampled every 2nd frame, capped at 5, frames left out on request')
    p2, t2 = template.camera_pose('follow', (0.0, 0.0, 1.0), None, {'R': 3.4, 'A': math.radians(46)})
    check(abs(p2[0] - 3.4 * math.cos(math.radians(46))) < 1e-9 and abs(p2[1] + 3.4 * math.sin(math.radians(46))) < 1e-9,
          'follow camera swung 46 degrees toward the ladder side (three z + R sin A -> Blender y - R sin A)')
    check(abs(template.damp(0.0, 1.0, 2.5, 1 / 30) - (1 - math.exp(-2.5 / 30))) < 1e-12,
          'damp = THREE.MathUtils.damp (1 - exp(-lambda dt) of the way)')
    # every variant scene builds (without its character), with its camera mode, recolour and telemetry
    from eidoblend.course import SCENES
    from eidoblend.course.builder import _lin
    ok_all, notes = True, []
    for vname, spec in SCENES.items():
        new_scene('variant_' + vname, 640, 360)
        cs = template.CourseScene(bpy.context.scene, variant=vname, character=None, log=lambda *a: None)
        cs.setup(frame_start=1)
        want_mode = spec.get('camera_mode', 'side')
        ok = cs.camera_mode == want_mode and len(cs.course.objects) > 1
        for key, opts in (spec.get('materials') or {}).items():
            m = cs.course.materials[key]
            col = tuple(m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value)[:3]
            ok &= max(abs(a - b) for a, b in zip(col, _lin(opts['color'])[:3])) < 1e-6
            if 'metalness' in opts:
                ok &= abs(m.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value
                          - opts['metalness']) < 1e-6
        if spec.get('telemetry'):
            ok &= cs.telemetry_cfg.get('enabled') is True and cs.telemetry_cfg.get('sample_every') == 1
        ok_all &= ok
        notes.append('%s %s' % (vname, 'ok' if ok else 'WRONG'))
    check(ok_all, 'variant scenes build with their camera, recolour and telemetry: %s' % ', '.join(notes))
    try:
        template.CourseScene(bpy.context.scene, PRESETS['ramp15'], driver='rapier')
        bad_driver = False
    except ValueError:
        bad_driver = True
    cs = template.CourseScene(bpy.context.scene, PRESETS['ramp15'], character=None,
                              telemetry={'enabled': True, 'sampleEvery': 3, 'includeFrames': False})
    check(bad_driver and cs.telemetry_cfg == {'enabled': True, 'sample_every': 3, 'include_frames': False},
          'an unknown driver raises; LOCOMOTION_TELEMETRY\'s camelCase keys are read')
    if RENDER:
        from PIL import Image, ImageDraw
        cols = 4
        rows = (len(sheet) + cols - 1) // cols
        S = Image.new('RGB', (cols * 640, rows * 380), (12, 14, 18))
        dr = ImageDraw.Draw(S)
        for i, (name, p) in enumerate(sheet):
            r, c = divmod(i, cols)
            if os.path.exists(p):
                S.paste(Image.open(p).convert('RGB'), (c * 640, r * 380))
            dr.text((c * 640 + 8, r * 380 + 362), name, fill=(220, 220, 220))
        S.save(os.path.join(OUT, 'course_presets_sheet.png'))
        check(True, 'course_presets_sheet.png (%d courses)' % len(sheet))


def part_example():
    ex = EXAMPLES['obstacle_course']
    for dressed in (False, True):
        sc = new_scene('example_' + ('dressed' if dressed else 'engine'), 960, 384, 16)
        use(sc)
        mats = None
        if dressed:
            from eidoblend.materials import procedural as PM
            mats = {'obstacle': PM.create_worn_metal(paint_color=0xd97550, metal_color=0x9a9a9a, wear_amount=0.28,
                                                     wear_scale=3, repeat=(0.5, 0.5), name='course_worn_paint'),
                    'ground': PM.create_rubber(color=0x2a2a2a, grain_scale=24, repeat=(0.25, 0.25),
                                               name='course_ground_rubber'),
                    'rail': PM.create_painted_metal(color=0xb8c2cc, scratches=True, repeat=(4, 4),
                                                    name='course_rail_paint')}
        course = build_course(ex['config'], materials=mats, name='ex' + ('_d' if dressed else ''))
        bench = add_bench(course, ex['bench'])
        st = course_stage(sc, course)
        if not dressed:
            plan = plan_course(ex['config'])
            check_course('example_obstacle_course', course, plan)
            seg26 = course.segment(26)
            top = bench.location.z + bench.dimensions.z / 2
            check(bench is not None and abs(bench.location.y - (seg26['y0'] + seg26['y1']) / 2) < 1e-5
                  and abs(top - 0.45) < 1e-6 and abs(bench.location.z - bench.dimensions.z / 2 + 0.002) < 1e-6,
                  'bench in the middle of segment 26 (y %.3f), its pan at 0.45 m, 2 mm into the floor'
                  % bench.location.y)
            on_floor = [o for o in course.objects if o['eido_course_role'] in ('step', 'slab', 'bump', 'wall', 'ladder')
                        and abs(o.location.z - o.dimensions.z / 2 + 0.002) < 1e-6]
            flagged = [o for o in course.objects if o.get('no_support_check')]
            check(len(on_floor) > 0 and not any(o.get('no_support_check') for o in on_floor)
                  and all(o['eido_course_role'] in ('ramp', 'rail', 'rung', 'step', 'slab', 'bump', 'wall', 'ladder',
                                                    'ground')
                          for o in flagged),
                  'support declarations per part: %d floor-standing pieces undeclared (2 mm skirt), %d declared '
                  '(ramps, raised pieces, the ladder fixtures, the ground)' % (len(on_floor), len(flagged)))
            rungs = [o for o in course.objects if o['eido_course_role'] == 'rung']
            rails = [o for o in course.objects if o['eido_course_role'] == 'rail']
            flags_ok = all(o.get('no_clipping_check') and o.get('allow_intersect') and o.get('no_z_fight_check')
                           for o in rungs + rails)
            check(len(rungs) == 8 and len(rails) == 2 and flags_ok,
                  'ladder: 2 rails, %d rungs (0.25 m up, every 0.28 m, below 2.45 m), fixture flags set' % len(rungs))
            s = course.segment_at(course.segment(18)['y0'] + 0.5)
            check(s is not None and s['kind'] == 'gap', 'segment_at finds the gap (segment 18) mid-jump')
            cols = [o for o in course.objects if o.get('eido_collider')]
            made = add_rigid_bodies(course)
            check(len(made) == len(cols) + 1 and all(o.rigid_body.type == 'PASSIVE' for o in made),
                  'add_rigid_bodies: %d passive bodies (the pieces, the ground and the bench)' % len(made))
            ball = [o for o in made if o.get('eido_collider') == 'ball']
            check(not ball or all(o.rigid_body.collision_shape == 'SPHERE' for o in ball), 'domes collide as balls')
        # the whole course from above its side
        st.camera.data.angle = math.radians(26)
        frame_objects(st.camera, [o for o in course.objects if o['eido_course_role'] != 'ground'] + [bench], sc,
                      azim_deg=-28.0, elev_deg=30.0, margin=1.04)
        render(sc, os.path.join(OUT, 'course_example_%s.png' % ('dressed' if dressed else 'engine')))
        if not dressed:
            # three close views along it: the vault walls and the mount, the run stairs and the gap, the ladder
            for tag, seg_i, side in (('walls', 12, 1), ('gap', 18, 1), ('ladder', 28, -1)):
                s = course.segment(seg_i)
                yc = (s['y0'] + s['y1']) / 2
                look_at(st.camera, (6.0 * side, yc - 4.5, 3.4), (0.0, yc, s['floor0'] + 0.6))
                st.camera.data.angle = math.radians(45)
                render(sc, os.path.join(OUT, 'course_example_%s.png' % tag))


def part_walk():
    sc = new_scene('walk', 960, 540, 16)
    use(sc)
    sc.render.fps = 30
    walk_to = float(arg('--walk-to', '14.0'))
    driver = arg('--driver', 'controller')
    tag_d = '' if driver == 'controller' else '_' + driver
    tel = os.path.join(OUT, 'course_walk%s_telemetry.json' % tag_d)
    t0 = time.time()
    lo = {} if '--engine-literal' in ARGS else None      # the engine's constructor never read the stair-clip flags
    cs = template.CourseScene(sc, PRESETS['obstacle_course_expanded'], character='claude_robot',
                              camera_mode='side', walk_to=walk_to, driver=driver, locomotion_opts=lo,
                              telemetry={'enabled': True, 'output_path': tel})
    cs.setup(frame_start=1)
    print('[walk] setup %.1f s; report keys %s' % (time.time() - t0, list(cs.report.keys())[:12]
                                                   if isinstance(cs.report, dict) else type(cs.report)))
    ad = cs.h.arm.animation_data
    fr = ad.action.frame_range if ad and ad.action else (1, 1)
    f0, f1 = int(fr[0]), int(fr[1])
    sc.frame_start, sc.frame_end = f0, f1
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        cs.frame(None, (f - f0) / 30.0, f)
    out = cs.cleanup()
    check(out is not None and os.path.exists(out), 'telemetry written (%d frames)' % len(cs.frames))
    summ = cs.summary()
    # the soles against the course's own surface, split by what round one's walk_path can take: flats, bumps and
    # ramps (a gait over uneven ground) versus steps and the dome (stair and obstacle adaptation: the controller's)
    gaps, hard, planted = [], [], []
    prev = {}
    for fr_ in cs.frames:
        kind = (fr_['terrain'] or {}).get('kind')
        for side, ft in fr_['feet'].items():
            (hard if kind in ('stairs', 'dome') else gaps).append(ft['soleGapY'])
            p = np.array(ft['actual'])
            # a planted foot: its lowest sole point all but still (under 0.12 m/s) and near the surface
            if side in prev and kind not in ('stairs', 'dome'):
                v = float(np.linalg.norm(p - prev[side])) * 30.0
                if v < 0.12 and abs(ft['soleGapY']) < 0.05:
                    planted.append(ft['soleGapY'])
            prev[side] = p
    gaps, hard, planted = np.array(gaps), np.array(hard), np.array(planted)
    check(len(planted) > 0 and float(np.percentile(np.abs(planted), 90)) < 0.006,
          'flats, bumps, ramps: planted soles on the course surface, 90th percentile |gap| %.4f m over %d contacts'
          % (float(np.percentile(np.abs(planted), 90)) if len(planted) else -1, len(planted)))
    deep = [(fr_['frame'], (fr_['terrain'] or {}).get('label'), side, ft['soleGapY'])
            for fr_ in cs.frames for side, ft in fr_['feet'].items()
            if (fr_['terrain'] or {}).get('kind') not in ('stairs', 'dome') and ft['soleGapY'] < -0.01]
    check(len(deep) <= 0.01 * len(gaps),
          'flats, bumps, ramps: %d of %d sole samples more than 1 cm under the course surface (worst %.4f m%s)'
          % (len(deep), len(gaps), float(gaps.min()),
             (': frame %d, %s, %s foot' % min(deep, key=lambda d: d[3])[:3]) if deep else ''))
    if len(hard):
        print('%s stairs and dome (%s): %.1f %% of sole samples more than 1 cm inside the course, worst %.3f m'
              % ('LIMIT' if driver == 'walk_path' else 'MEASURE', driver, 100 * float((hard < -0.01).mean()),
                 float(hard.min())))
    if driver == 'controller':
        acts = [f.get('actions') for f in cs.frames if f.get('actions')]
        led = sorted({max(a, key=lambda k: (a[k] or {}).get('weight') or 0) for a in acts})
        check(len(acts) == len(cs.frames) and 'walk' in led and ('stairsUp' in led or 'stairsDown' in led),
              'the controller drove the walk: its state on every telemetry frame, leading clips %s' % led)
        check_engine_telemetry(cs, summ)
    labels = sorted(summ['byTerrain'].keys())
    print('[walk] terrain segments walked:', labels)
    check(any('stairs' in k for k in labels) and any('dome' in k for k in labels) and any('ramp' in k for k in labels),
          'the walk crossed bumps, the dome, ramps and stairs (%d segments)' % len(labels))
    cam = cs.stage.camera
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(cam.animation_data.action, cam.animation_data.action_slot)
    nkeys = len(cb.fcurves[0].keyframe_points) if cb else 0
    check(nkeys == f1 - f0 + 1, 'camera keyed every frame (%d keys for %d frames)' % (nkeys, f1 - f0 + 1))
    # stills: each camera mode at three moments (the dome, the ramp up, the small stairs)
    picks = []
    for want in ('8:dome', '10:ramp:up', '14:stairs:up'):
        for fr_ in cs.frames:
            if fr_['terrain'] and fr_['terrain']['label'] == want:
                picks.append((want.split(':')[1], fr_['frame']))
                break
    print('[walk] picks', picks)
    shots = []
    for mode in ('side', 'three_quarter', 'hands_closeup'):
        for tag, f in picks:
            sc.frame_set(f)
            pos, tgt = template.camera_pose(mode, tuple(cs.body()), tuple(cs.hand()) if cs.hand() else None)
            shots.append({'path': 'course_walk%s_%s_%s_f%03d.png' % (tag_d, mode, tag, f), 'frame': f,
                          'pos': list(pos), 'tgt': list(tgt)})
    if cam.animation_data:
        cam.animation_data_clear()
    render_shots(sc, cam, shots)
    if '--save' in ARGS:                 # bake here (CPU), render later from the file: --parts walk_render
        sc['eido_walk_shots'] = json.dumps(shots)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'course_walk%s.blend' % tag_d), compress=True)
        print('[walk] saved course_walk%s.blend for --parts walk_render' % tag_d)


def check_engine_telemetry(cs, summ):
    """the engine's _locRecordTelemetry fields on the controller's frames: the IK per limb, the ahead probes, the
    actions' time scales, and the summary's IK metrics; the template's cameras ride the capsule centre"""
    fr = cs.frames
    ik_ok = [f for f in fr if (f.get('ik') or {}).get('left') and (f.get('ik') or {}).get('right')]
    errs = [f['ik'][s]['targetError'] for f in ik_ok for s in ('left', 'right') if f['ik'][s]['targetError'] is not None]
    sup = [f for f in fr if (f.get('support') or {}).get('aheadProbeSpread') is not None]
    ts = [f for f in fr if ((f.get('actions') or {}).get('walk') or {}).get('timeScale') is not None]
    shapes = sorted({(f.get('support') or {}).get('stairShape') for f in fr} - {None})
    check(len(ik_ok) == len(fr) and len(errs) > len(fr) // 2 and len(sup) == len(fr) and len(ts) == len(fr),
          'engine telemetry on every frame: the foot IK per limb (%d target errors, median %.4f m), the ahead '
          'probes, the actions\' time scales; stair shapes seen %s' % (len(errs), float(np.median(errs)) if errs
                                                                       else -1, shapes))
    m = summ['metrics']
    have = [k for k in ('leftTargetError', 'rightTargetErrorXZ', 'leftSoleGapY', 'rightTargetSpeed', 'leftHitSpeed',
                        'leftMeshSoleGapY', 'bodyJerkY', 'speedError') if k in m]
    check(len(have) == 8, 'summary: the engine\'s metrics (%s) plus the mesh soles' % ', '.join(have))
    f = fr[len(fr) // 2]
    c, hips = f['body']['center'], f['body'].get('hips')
    check(hips is not None and 0.25 < c[2] - hips[2] < 0.6,
          'the cameras\' body point is the capsule centre (%.3f m), %.3f m over the hips' % (c[2], c[2] - hips[2]))


def part_example_run():
    """examples/obstacle_course.js whole, through the template: the controller directed as the example's renderFrame
    directs it, baked on the CPU, its follow camera keyed, saved for --parts example_run_render"""
    sc = new_scene('example_run', 960, 540, 16)
    sc.render.fps = 30
    tel = os.path.join(OUT, 'course_example_run_telemetry.json')
    t0 = time.time()
    cs = template.CourseScene(sc, example='obstacle_course', telemetry={'enabled': True, 'output_path': tel})
    cs.setup(frame_start=1)
    t_bake = time.time() - t0
    ad = cs.h.arm.animation_data
    f0, f1 = (int(v) for v in ad.action.frame_range)
    sc.frame_start, sc.frame_end = f0, f1
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        cs.frame(None, (f - f0) / 30.0, f)
    cs.cleanup()
    print('[example_run] bake %.1f s, %d frames (%.1f s of film)' % (t_bake, f1 - f0 + 1, (f1 - f0 + 1) / 30.0))
    check(cs.camera_mode == 'follow' and cs.character == 'aporia' and cs.course.bench is not None,
          'the example\'s own camera (follow), character (aporia) and bench')
    fixtures = [o for o in cs.course.objects if o.get('eido_course_role') in ('rail', 'rung')]
    check(fixtures and not any(o in cs.colliders() for o in fixtures) and cs.course.bench in cs.colliders(),
          'the ladder\'s %d rails and rungs are visual (no colliders), the bench is solid' % len(fixtures))
    runs = {}
    for f in range(f0, f1 + 1):
        m = (cs.flags.get(f) or {}).get('maneuver')
        if not m:
            continue
        rs = runs.setdefault(m, [])
        if rs and rs[-1][1] == f - 1:
            rs[-1][1] = f
        else:
            rs.append([f, f])
    print('[example_run] maneuvers', runs)
    for k, n in (('vault', 2), ('mount', 2), ('jump', 1), ('ladder', 1), ('land', 1)):
        check(len(runs.get(k, [])) >= n, 'the example\'s %s plays (%d or more): %s' % (k, n, runs.get(k)))
    recs = cs.records
    seated = [f for f in recs if recs[f]['mode'] == 'seated']
    check(len(seated) > 30, 'the sit stop: seated on the bench for %d frames' % len(seated))
    if seated:
        fs = seated[len(seated) // 2]
        sc.frame_set(fs)
        hz = cs.hips_world()
        b = cs.course.bench
        top = b.location.z + b.dimensions.z / 2
        check(abs(hz.y - b.location.y) < 0.35 and 0.0 < hz.z - top < 0.35,
              'seated: the hips over the bench pan (%.2f m along the course from its middle, %.2f m over the pan)'
              % (hz.y - b.location.y, hz.z - top))
    gw = max((recs[f]['weights'].get('cheer', 0.0) for f in recs), default=0.0)
    check(gw > 1.0, 'the cheer gesture over the walk (weight up to %.2f)' % gw)
    sal = [f for f in recs if recs[f]['mode'] == 'emote' and recs[f]['weights'].get('salute', 0.0) > 0.5]
    check(len(sal) > 10, 'the finale salute (%d frames)' % len(sal))
    top_seg = cs.course.segment(EXAMPLES['obstacle_course']['zones']['finale'])
    end = recs[max(recs)]['feet_world']
    check(top_seg['y0'] < end[1] < top_seg['y1'] and abs(end[2] - top_seg['floor0']) < 0.08,
          'the finale stands on the ladder\'s top platform (feet at %s; the platform %.2f m up)'
          % (tuple(round(v, 2) for v in end), top_seg['floor0']))
    # the follow camera pushes in while she maneuvers or sits, and stands off at 5.2 m on the plain walk
    cam = cs.stage.camera
    near, far = [], []
    for f in range(f0, f1 + 1, 3):
        sc.frame_set(f)
        b = cs.body(f)
        d = math.hypot(cam.matrix_world.translation.x - b.x, cam.matrix_world.translation.y - b.y)
        if (cs.flags.get(f) or {}).get('phase') == 'sit' and (cs.flags.get(f - 45) or {}).get('phase') == 'sit':
            near.append(d)
        elif not cs.follow_close(f) and all(not cs.follow_close(g) for g in range(max(f0, f - 60), f)):
            far.append(d)
    check(near and far and max(near) < 3.6 and min(far) > 5.0,
          'follow camera: %.2f to %.2f m from her while seated, %.2f to %.2f m on the plain walk'
          % (min(near or [0]), max(near or [0]), min(far or [0]), max(far or [0])))
    # stills along the run, through the template's own keyed follow camera
    picks = []
    for k, i in (('vault', 0), ('mount', 0), ('jump', 0), ('vault', 1), ('mount', 1), ('ladder', 0)):
        if len(runs.get(k, [])) > i:
            a, b2 = runs[k][i]
            picks.append(('%s%d' % (k, i + 1), (a + b2) // 2))
    if seated:
        picks.append(('seated', seated[len(seated) // 2]))
    ges = [f for f in recs if recs[f]['weights'].get('cheer', 0.0) > 1.0]
    if ges:
        picks.append(('cheer', ges[len(ges) // 2]))
    if sal:
        picks.append(('salute', sal[len(sal) // 2]))
    shots = [{'path': 'course_example_run_%s_f%04d.png' % (t, f), 'frame': f} for t, f in picks]
    sc['eido_example_shots'] = json.dumps(shots)
    print('[example_run] picks', picks)
    if RENDER:
        for s in shots:
            sc.frame_set(s['frame'])
            render(sc, os.path.join(OUT, s['path']))
    if '--save' in ARGS:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'course_example_run.blend'), compress=True)
        print('[example_run] saved course_example_run.blend for --parts example_run_render')


def part_variants():
    """every variant scene (presets.SCENES) run for its first 4 s with its character, and a still through its own
    camera mode at 3.5 s: its recolour, its expression, the hand camera, the raw animation of the noik scene"""
    from eidoblend.course import SCENES
    sheet = []
    for vname, spec in SCENES.items():
        sc = new_scene('variant_run_' + vname, 640, 360, 16)
        sc.render.fps = 30
        tel = None
        if spec.get('telemetry'):
            tel = dict(spec['telemetry'], output_path=os.path.join(OUT, 'course_variant_%s_telemetry.json' % vname))
        t0 = time.time()
        cs = template.CourseScene(sc, variant=vname, duration=4.0, telemetry=tel, log=lambda *a: None)
        cs.setup(frame_start=1)
        ad = cs.h.arm.animation_data
        f0, f1 = (int(v) for v in ad.action.frame_range)
        sc.frame_start, sc.frame_end = f0, f1
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            cs.frame(None, (f - f0) / 30.0, f)
        if tel:
            cs.cleanup()
        fs = min(f1, f0 + 105)
        sc.frame_set(fs)
        b = cs.body(fs)
        seg = cs.course.segment_at(b.y)
        check(cs.h is not None and f1 - f0 > 60 and b.y > cs.course.start[1] + 3.0,
              'variant %-30s %s, %s camera, %d frames baked in %.0f s; at 3.5 s %.1f m along (%s)'
              % (vname, cs.character, cs.camera_mode, f1 - f0 + 1, time.time() - t0, b.y - cs.course.start[1],
                 seg['label'] if seg else 'on the course'))
        path = os.path.join(OUT, 'course_variant_%s.png' % vname)
        render(sc, path)
        sheet.append((vname, path))
    if RENDER:
        from PIL import Image, ImageDraw
        cols = 4
        rows = (len(sheet) + cols - 1) // cols
        S = Image.new('RGB', (cols * 640, rows * 380), (12, 14, 18))
        dr = ImageDraw.Draw(S)
        for i, (name, p) in enumerate(sheet):
            r, c = divmod(i, cols)
            if os.path.exists(p):
                S.paste(Image.open(p).convert('RGB'), (c * 640, r * 380))
            dr.text((c * 640 + 8, r * 380 + 362), name, fill=(220, 220, 220))
        S.save(os.path.join(OUT, 'course_variants_sheet.png'))


def part_example_run_render():
    """render a saved example run's stills (the GPU half of --parts example_run --no-render --save)"""
    bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, 'course_example_run.blend'))
    sc = bpy.context.scene
    for s in json.loads(sc['eido_example_shots']):
        sc.frame_set(s['frame'])
        render(sc, os.path.join(OUT, s['path']))


def render_shots(sc, cam, shots):
    for s in shots:
        sc.frame_set(s['frame'])
        look_at(cam, tuple(s['pos']), tuple(s['tgt']))
        render(sc, os.path.join(OUT, s['path']))


def part_walk_render():
    """render a saved walk's stills (the GPU half of --parts walk --no-render --save)"""
    tag_d = '' if arg('--driver', 'controller') == 'controller' else '_' + arg('--driver')
    path = os.path.join(OUT, 'course_walk%s.blend' % tag_d)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    shots = json.loads(sc['eido_walk_shots'])
    render_shots(sc, sc.camera, shots)


def main():
    t0 = time.time()
    if 'presets' in PARTS:
        part_presets()
    if 'example' in PARTS:
        part_example()
    if 'walk' in PARTS:
        part_walk()
    if 'walk_render' in PARTS:
        part_walk_render()
    if 'example_run' in PARTS:
        part_example_run()
    if 'example_run_render' in PARTS:
        part_example_run_render()
    if 'variants' in PARTS:
        part_variants()
    print('%s: %d failing (%.1f s)' % ('FAIL' if FAILS else 'PASS', len(FAILS), time.time() - t0))


main()
