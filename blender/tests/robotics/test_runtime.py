"""eidoverse/robotics/tests/runtime_test.mjs, ported (no render), plus the Blender edition's own runtime checks.

From the WebGPU test: loadPart keeps exact triangle ownership and leaves the donor untouched; an unknown part leaves
nothing behind; the catalog's content (>= 78 models, 67 shared maps, no duplicate files) and the rotary workholding's
recolour bindings; matching mounts seat without a half-turn on an upright camera, a cycle is refused and disposing the
parent disposes the child; the mirrored legs seat on the articulated pelvis; the humanoid's left and right limbs are
independent and the thumbs curl; the retired primitive presets stay retired; the A650 and S500 solvers agree with the
exported tool transforms (forward, and move_to back onto the same point). The WebGPU test's fabrication case is the
fabrication port's (eidoblend.fabrication).

The Blender edition's own: the loader's option checks; play() keys reproduce sample() at every frame and stop() removes
them; the joint sliders (rig.py) drive the modules exactly as set_joints does (a mirrored module and a prismatic jaw
included); track_travel / spin_rotors / fold / cooling_fan / rotary_setup / move_tool edge cases; the facade; and,
last, with the fabrication port imported (its hooks): create_ptfe_tube / service_loop forwarded, the dispenser's live
filament installed at load, and its 'filament-feed' keyed with the strand's Geometry Nodes inputs.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/test_runtime.py
"""

import math
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

from eidoblend.characters.robotics import (RoboticsKit, catalog, connect, load_part, make_bot,  # noqa: E402
                                           make_robot)
from eidoblend.characters.robotics.rig import rig_joints, set_slider, unrig_joints  # noqa: E402


def raises(fn, text):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        return text in str(e), str(e)
    return False, 'no error'


def parts_ownership():
    for rid in ('face', 'air/air', 'rotors_air_air/air_air_rotors'):
        K.clean_scene()
        donor = make_robot(rid, textures=False)
        if rid == 'face':
            name = 'FACE swept tilt yoke'
        else:
            name = next(n for n in donor.parts() if any(len(donor.part_ids.get(o.name) or []) > 1 for o in donor.part(n)))
        before = donor.stats()['triangles']
        expected = sum(sum(1 for p in donor.part_faces(o) if p == name) for o in donor.part(name))
        part = load_part(rid, name, textures=False)
        st = part.stats()
        ok = part.parts() == [name] and st['parts'] == 1 and st['triangles'] == expected and expected > 0
        lookups = all(len(part.part_faces(o)) == len(o.data.polygons) and all(p == name for p in part.part_faces(o))
                      for o in part.meshes() if not o.hide_render)
        K.check(f'load_part {rid} / {name}: {expected} triangles, one part, face lookup matches the filtered mesh',
                ok and lookups, f"{st['triangles']} triangles, parts {part.parts()}")
        part.dispose()
        K.check(f'load_part {rid}: the donor keeps its {before} triangles', donor.stats()['triangles'] == before)
        donor.dispose()
    K.clean_scene()
    n0 = len(bpy.data.objects)
    ok, msg = raises(lambda: load_part('face', '__missing_part__', textures=False), 'Unknown part')
    K.check(f'an unknown part is refused ({msg}) and leaves no donor in the file', ok and len(bpy.data.objects) == n0)


def catalog_content():
    c = catalog()
    K.check(f"catalog: {len(c['models'])} models (>= 78)", len(c['models']) >= 78)
    tex = c['textures']
    K.check(f'catalog: {len(tex)} shared maps (67), no duplicate files',
            len(tex) == 67 and len({t['path'] for t in tex}) == len(tex) and len({t['file_sha256'] for t in tex}) == len(tex))
    for rid in ('manufacturing/rotary_fixture', 'manufacturing/cnc_rotary'):
        K.clean_scene()
        r = make_robot(rid)
        wh = next((m for m in r.materials.materials if m.name.startswith('EIDO / rotary_workholding')), None)
        rc = wh.get('eidoverse_recolor') if wh else None
        rc = rc.to_dict() if hasattr(rc, 'to_dict') else rc
        ok = (rc and rc.get('fixed') == '../textures/rotary_workholding_fixed.png'
              and rc.get('mask') == '../textures/rotary_workholding_mask.png'
              and len(rc.get('default_primary_linear')) == 3 and len(rc.get('default_accent_linear')) == 3)
        labels = {n.label for n in wh.node_tree.nodes} if wh else set()
        K.check(f'{rid}: the workholding keeps its recolour bindings and is recoloured',
                bool(ok) and 'recolor fixed' in labels and 'recolor mask' in labels)
        r.dispose()
    for rid in ('delta', 'stewart', 'turret', 'kossel'):
        ok, msg = raises(lambda: make_robot(rid, textures=False), 'Unknown modular robot')
        K.check(f'retired primitive {rid!r} stays retired', ok, msg)


def upright_camera():
    K.clean_scene()
    body = make_robot('mobility/body', textures=False)
    cam = make_robot('camera', textures=False)
    body.group.rotation_euler = (0, 0, 0.7)
    body.group.location = (0.3, 0.2, 0.5)
    bpy.context.view_layer.update()
    connect(body, cam, port='body_base/sensor_0', child_port='camera_base/input')
    bpy.context.view_layer.update()
    a, b = body.port('body_base/sensor_0'), cam.port('camera_base/input')
    ma, mb = a['owner'].matrix_world @ a['matrix'], b['owner'].matrix_world @ b['matrix']
    d = (ma.translation - mb.translation).length
    n = (ma.to_3x3() @ Vector((0, 0, 1))).normalized().dot((mb.to_3x3() @ Vector((0, 0, 1))).normalized())
    up = (cam.group.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized().dot(
        (body.group.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized())
    K.check('the camera seats on sensor_0: frames meet, normals oppose, no half-turn', d < 1e-6 and abs(n + 1) < 1e-6
            and abs(up - 1) < 1e-6, f'{d * 1000:.5f} mm, {n:.7f}, {up:.7f}')
    ok, msg = raises(lambda: cam.attach(body, port='camera_base/input', child_port='body_base/payload'), '')
    K.check(f'a cycle / mismatched interface is refused ({msg})', ok and msg != 'no error')
    body.dispose()
    K.check('disposing the parent disposes the attached camera', cam.disposed)


def mirrored_legs():
    K.clean_scene()
    hip = make_robot('humanoid_modules/pelvis', textures=False)
    for side in ('left', 'right'):
        leg = make_robot(f'humanoid_modules/{side}_leg', textures=False)
        hip.attach(leg, port=f'pelvis_{side}_roll/{side}_leg', child_port='leg_mount/input')
        bpy.context.view_layer.update()
        a, b = hip.port(f'pelvis_{side}_roll/{side}_leg'), leg.port('leg_mount/input')
        d = ((a['owner'].matrix_world @ a['matrix']).translation - (b['owner'].matrix_world @ b['matrix']).translation).length
        K.check(f'the {side} leg seats on the articulated pelvis ({len(leg.parts())} parts, < 30)',
                d < 1e-6 and len(leg.parts()) < 30, f'{d * 1000:.5f} mm')
    hip.dispose()


def humanoid_limbs():
    K.clean_scene()
    r = make_robot('humanoid', textures=False)
    hands = [n for n in r.roots if n.endswith('hand_base')]
    knees = [n for n in r.roots if n.endswith('leg_knee')]
    K.check(f'the humanoid keeps both hands and both knees ({hands}, {knees})', len(hands) == 2 and len(knees) == 2)
    r.grasp(1)
    thumbs = {n: v for n, v in r.state.items() if n.endswith('dh_thumb_mcp')}
    K.check(f'grasp(1) curls both thumbs ({thumbs})', len(thumbs) == 2 and all(v > 0.4 for v in thumbs.values()))
    refs = r.grasp_reference()
    bpy.context.view_layer.update()
    K.check('grasp_reference: one cylinder under each hand', len(refs) == 2 and all(o.parent.name.endswith('hand_base')
                                                                                   for o in refs))
    # the running controller's own API (running.js): frame, apply, restore, bounds, duration
    run = r.running
    f = run.frame('circle', 1.0)
    lo, hi = run.bounds('circle')
    inside = all(lo[i] - 1e-6 <= fr['base'][i] <= hi[i] + 1e-6           # mathutils Vectors hold float32
                 for fr in run.data['clips']['circle']['frames'] for i in range(3))
    before = {n: o.matrix_basis.copy() for n, o in run.nodes.items()}
    run.apply('circle', 1.0)
    moved = any(K.mdiff(o.matrix_basis, before[n]) > 1e-6 for n, o in run.nodes.items())
    run.restore()
    back = max(K.mdiff(o.matrix_basis, run.original[n]) for n, o in run.nodes.items())
    K.check(f"running: frame() has base / yaw / pitch / {len(f['joints'])} joints, bounds() holds the run, apply() "
            f"moves, restore() returns (duration {run.duration('circle'):.2f} s)",
            set(f) == {'time', 'base', 'yaw', 'pitch', 'joints'} and inside and moved and back < 1e-5,
            f'keys {sorted(f)}, inside {inside}, moved {moved}, restore error {back:.1e} (float32 transforms)')
    r.dispose()


def solvers_vs_meshes():
    K.clean_scene()
    arm = make_robot('arm', textures=False)
    q = [.2, .4, -.6, .25, .6, -.2]
    arm.joints(q)
    bpy.context.view_layer.update()
    target = Matrix(arm.ik.forward(q))
    tip = arm.roots['a650_j6'].matrix_world @ Vector((0.018, 0, 0))
    K.check('A650: ik.forward lands on the exported a650_j6 TCP', (tip - target.translation).length < 1e-6,
            f'{(tip - target.translation).length:.2e} m')
    arm.reset()
    arm.move_to(target, [0, .3, -.5, 0, .3, 0])
    bpy.context.view_layer.update()
    tip = arm.roots['a650_j6'].matrix_world @ Vector((0.018, 0, 0))
    K.check('A650: move_to brings the TCP back onto the target', (tip - target.translation).length < 3e-5,
            f'{(tip - target.translation).length:.2e} m')
    ok, msg = raises(lambda: arm.move_to(Matrix.Translation((3, 0, 0))), 'unreachable')
    K.check(f'A650: an unreachable target is refused ({msg})', ok)
    arm.dispose()
    sc = make_robot('scara', textures=False)
    j = [.2, .8, .04, -.4]
    sc.scara_joints(j)
    bpy.context.view_layer.update()
    f = sc.scara.forward(j)
    p = sc.roots['s500_tool'].matrix_world.translation
    K.check('S500: scara.forward lands on the exported s500_tool', (p - Vector(f[:3])).length < 1e-6,
            f'{(p - Vector(f[:3])).length:.2e} m')
    sc.reset()
    sc.move_scara(f[:3], f[3], seed=j)
    bpy.context.view_layer.update()
    p2 = sc.roots['s500_tool'].matrix_world.translation
    K.check('S500: move_scara reaches the same point', (p2 - Vector(f[:3])).length < 1e-6)
    ok, msg = raises(lambda: sc.move_scara((2, 0, 0.2)), 'unreachable')
    K.check(f'S500: an unreachable target is refused ({msg})', ok)
    sc.dispose()


def loader_options():
    K.clean_scene()
    for kw, text in (({'foo': 1}, "Unknown modular loader option 'foo'"), ({'position': (0, 0)}, 'position must be'),
                     ({'rotation': (0, math.nan, 0)}, 'rotation must be'), ({'scale': -1}, 'positive uniform'),
                     ({'scale': 0}, 'positive uniform')):
        ok, msg = raises(lambda: make_robot('gripper', textures=False, **kw), text)
        K.check(f'loader refuses {kw}: {msg}', ok)
    r = make_robot('gripper', textures=False, position=(1, 2, 3), rotation=(0, 0, 0.5), scale=2.0)
    K.check('loader places the group (position, rotation, scale)', tuple(r.group.location) == (1, 2, 3)
            and abs(r.group.rotation_euler.z - 0.5) < 1e-7 and tuple(r.group.scale) == (2, 2, 2))
    r.dispose()
    b = make_bot(textures=False)
    K.check('make_bot loads the humanoid by default', b.id == 'humanoid/humanoid_receiver_study')
    b.dispose()
    r = RoboticsKit.load('gripper', textures=False)
    K.check('RoboticsKit facade: version, ready, catalog, load', RoboticsKit.version == 1 and RoboticsKit.ready()
            and 'models' in RoboticsKit.catalog() and r.id == 'foundations/tooling')
    r.dispose()
    ok, msg = raises(lambda: RoboticsKit.create_ptfe_tube(points=[[0, 0, 0]] * 4), 'filament.js')
    K.check(f'create_ptfe_tube names its owner until the fabrication port registers it ({msg[:60]})', ok)


def keyed_play():
    sc = K.clean_scene()
    sc.frame_start, sc.frame_end = 1, 48
    for rid, clip in (('mantis', 'drive-circle'), ('humanoid', 'run-circle'), ('drone', 'flight'),
                      ('payloads/arm_hand', 'joints'), ('quadruped', 'walk')):
        K.clean_scene()
        sc.frame_start, sc.frame_end = 1, 48
        r = make_robot(rid, textures=False)
        rec = r.play(clip, speed=1.5, start=0.25)
        objs = r.motion_objects()
        keyed = {}
        for f in (1, 9, 17, 33, 48):
            sc.frame_set(f)
            keyed[f] = [o.matrix_world.copy() for o in objs]
        n_keyed = len(rec['objects'])
        r.stop()
        worst = 0.0
        for f, ms in keyed.items():
            t = max(0.0, ((f - 1) / 24 - 0.25) * 1.5)
            r.sample(clip, t)
            bpy.context.view_layer.update()
            worst = max(worst, max(K.mdiff(o.matrix_world, m) for o, m in zip(objs, ms)))
        K.check(f'{rid} {clip}: the keyed frames equal sample() at (t - start) * speed ({n_keyed} objects keyed)',
                worst < 2e-5 and n_keyed > 0, f'worst {worst:.1e}')
        K.check(f'{rid}: stop() removed the keys', all(o.animation_data is None or o.animation_data.action is None
                                                       for o in objs))
        r.dispose()


def sliders():
    for rid, joints in (('humanoid', ('left_shoulder / m360_yaw', 'right_leg / leg_knee', 'left_hand / dh_index_1')),
                        ('gripper', ('jaw_left', 'jaw_right')), ('rotary_fixture', ('rotary_output',))):
        K.clean_scene()
        r = make_robot(rid, textures=False)
        made = rig_joints(r)
        worst = 0.0
        joints = tuple(joints) + tuple(n for n in made if r.rest[r.roots[n].name].to_3x3().determinant() < 0)[:3]
        for n in joints:
            if n not in made:
                K.check(f'{rid}: slider for {n}', False, 'no slider')
                continue
            s = r.specs[n]
            lo, hi = s.get('limits') or (-math.pi, math.pi)
            lo, hi = max(lo, -math.pi), min(hi, math.pi)
            v = lo + 0.73 * (hi - lo)
            set_slider(r, n, v)
            got = {t: r.roots[t].matrix_world.copy() for t in r.roots}
            unrig_joints(r)
            r.reset()
            r.set_joints({n: v})
            bpy.context.view_layer.update()
            worst = max(worst, max(K.mdiff(r.roots[t].matrix_world, m) for t, m in got.items()))
            r.reset()
            made = rig_joints(r)
        mirrored = [n for n in joints if r.rest[r.roots[n].name].to_3x3().determinant() < 0]
        K.check(f'{rid}: the sliders drive {list(joints)} exactly as set_joints ({len(made)} sliders; mirrored: '
                f'{mirrored})', worst < 2e-5, f'worst {worst:.1e}')
        r.dispose()
    # no kit joint has a reflected LOCAL rest (the humanoid's left side inherits its reflection), so reflect one here:
    # three's split of a mirrored rest turns the joint differently from Blender's, and the slider must follow three's
    K.clean_scene()
    r = make_robot('arm', textures=False)
    n = 'a650_j3'
    o = r.roots[n]
    r.rest[o.name] = r.rest[o.name] @ Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
    r.reset()
    rig_joints(r)
    set_slider(r, n, 0.61)
    got = {t: r.roots[t].matrix_world.copy() for t in r.roots}
    unrig_joints(r)
    r.reset()
    r.set_joints({n: 0.61})
    bpy.context.view_layer.update()
    w = max(K.mdiff(r.roots[t].matrix_world, m) for t, m in got.items())
    K.check(f'a reflected rest: the slider turns {n} exactly as set_joints (three\'s decomposition)', w < 2e-5,
            f'worst {w:.1e}')
    r.dispose()


def controls():
    K.clean_scene()
    rover = make_robot('rover', textures=False)
    ok, msg = raises(lambda: rover.track_travel({'nope': 1}), 'Invalid track travel')
    K.check(f'track_travel refuses an unknown track ({msg})', ok)
    tracks = list(rover.report['mobile']['tracks'])
    res = rover.track_travel({tracks[0]: 0.1})
    K.check(f'track_travel rolls the wheels ({len(res["wheels"])}) and moves {len(rover.track_bindings)} shoes',
            len(res['wheels']) > 0 and len(rover.track_bindings) > 0)
    rover.dispose()
    drone = make_robot('drone', textures=False)
    drone.fold(1.0)
    ok, msg = raises(lambda: drone.spin_rotors(1.0), 'Deploy booms')
    K.check(f'spin_rotors refuses folded booms ({msg})', ok)
    drone.fold(0.0)
    drone.spin_rotors(1.0)
    K.check('fold(0) then spin_rotors works', True)
    for bad in (-0.1, 1.1, math.nan):
        ok, _ = raises(lambda: drone.fold(bad), 'Fold phase')
        K.check(f'fold({bad}) refused', ok)
    drone.dispose()
    fdm = make_robot('fdm', textures=False)
    fdm.cooling_fan(0.5)
    K.check('cooling_fan turns the extruder fan', abs(fdm.state.get('extruder_fan', 0) - math.fmod(0.5 * 4800 / 60 * 2 * math.pi, 2 * math.pi)) < 1e-9)
    ok, msg = raises(lambda: fdm.axes([1, 0, 0]), 'travel exceeded on X')
    K.check(f'axes refuses travel past the limits ({msg})', ok)
    ok, msg = raises(lambda: fdm.cooling_fan(-1), 'nonnegative')
    K.check(f'cooling_fan refuses negative time ({msg})', ok)
    fdm.dispose()
    rf = make_robot('rotary_fixture', textures=False)
    setup = rf.rotary_setup(stock_length=0.12, stock_width=0.03, stock_height=0.04, quill=0.002)
    K.check('rotary_setup sets the tailstock, quill, handwheel and jaws', all(abs(rf.state[n] - v) < 1e-12
                                                                              for n, v in setup['joints'].items()))
    ok, msg = raises(lambda: rf.set_joints({'rotary_output': 0.3, 'rotary_chuck': 0.4}), 'share the same A-axis')
    K.check(f'the A axis couples output and chuck ({msg})', ok)
    rf.set_joints({'rotary_chuck': 0.3})
    K.check('setting the chuck turns the output with it', abs(rf.state['rotary_output'] - 0.3) < 1e-12)
    rf.dispose()
    g = make_robot('gripper', textures=False)
    for bad in (-0.001, 0.045):
        ok, _ = raises(lambda: g.jaw_gap(bad), 'Jaw gap')
        K.check(f'jaw_gap({bad}) refused', ok)
    ok, msg = raises(lambda: g.joints([0] * 6), 'no A650')
    K.check(f'an A650 call on the gripper says so ({msg})', ok)
    ok, msg = raises(lambda: g.set_joints({'jaw_left': 0.5}), 'outside')
    K.check(f'set_joints refuses a value past the limits ({msg})', ok)
    g.set_joints({'jaw_left': 0.5}, clamp=True)
    K.check('set_joints(clamp=True) clamps to the limit', abs(g.state['jaw_left'] - g.specs['jaw_left']['limits'][1]) < 1e-12)
    ok, msg = raises(lambda: g.port('nope'), 'Unknown port nope; available:')
    K.check(f'an unknown port is refused with the list ({msg[:60]})', ok)
    g.reset()
    g.set_joints({'jaw_left': 0.01})
    n = g.key_joints(5)
    jaw = g.roots['jaw_left']
    fcs = []
    if jaw.animation_data and jaw.animation_data.action:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(jaw.animation_data.action, jaw.animation_data.action_slot)
        fcs = [fc for fc in cb.fcurves if any(abs(k.co.x - 5) < 1e-6 and k.interpolation == 'LINEAR'
                                              for k in fc.keyframe_points)]
    K.check(f'key_joints(5) keyed the joint set_joints moved ({n} object, {len(fcs)} LINEAR channels)',
            n == 1 and len(fcs) >= 3)
    jaw.animation_data_clear()
    ok, msg = raises(lambda: g.sample('walk', 1), 'No walk clip')
    K.check(f'an absent sample is refused ({msg})', ok)
    ok, msg = raises(lambda: g.sample('joints', -1), 'nonnegative')
    K.check(f'a negative sample time is refused ({msg})', ok)
    g.dispose()


def framing():
    """studio.frame_camera against studio.js frameCamera on the same box (js_parity_dump.mjs's case)"""
    import json
    from eidoblend.characters.robotics.studio import frame_camera, make_camera
    js = json.load(open(os.path.join(K.DUMP, '_summary.json'), encoding='utf-8'))['solvers']['frameCamera']
    sc = K.clean_scene()
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    cam = make_camera(35, 'framing', sc)
    lo, hi = (-0.4, 0.0, -0.3), (0.6, 1.2, 0.5)                       # three's box
    blo = Vector((lo[0], -hi[2], lo[1]))
    bhi = Vector((hi[0], -lo[2], hi[1]))
    target = frame_camera(cam, [(blo, bhi)], direction=(0.9, -1.5, 0.55), margin=1.25)
    tj, pj = js['target'], js['position']
    e_t = (target - Vector((tj[0], -tj[2], tj[1]))).length
    e_p = (cam.location - Vector((pj[0], -pj[2], pj[1]))).length
    e_c = abs(cam.data.clip_start - js['near']) + abs(cam.data.clip_end - js['far'])
    K.check('frame_camera matches frameCamera (target, position, near, far)', e_t < 1e-6 and e_p < 1e-5 and e_c < 1e-4,
            f'target {e_t:.1e}, position {e_p:.1e}, clip {e_c:.1e}')


def saved_file_plays():
    """the keyed-data contract: a saved .blend, reopened, poses every frame on its own (last: it opens a new file)"""
    sc = K.clean_scene()
    sc.frame_start, sc.frame_end = 1, 48
    r = make_robot('mantis', textures=False)
    r.play('drive-circle')
    names = [o.name for o in r.motion_objects()]
    want = {}
    for f in (7, 30, 48):
        sc.frame_set(f)
        want[f] = [bpy.data.objects[n].matrix_world.copy() for n in names]
    path = os.path.join(K.OUT, '_saved_file_plays.blend')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    worst = 0.0
    for f, ms in want.items():
        sc.frame_set(f)
        worst = max(worst, max(K.mdiff(bpy.data.objects[n].matrix_world, m) for n, m in zip(names, ms)))
    K.check(f'a saved, reopened file poses all {len(names)} moving objects at frames 7, 30, 48 on its own', worst < 1e-6,
            f'worst {worst:.1e}')
    for p in (path, path + '1'):
        if os.path.exists(p):
            os.remove(p)


def loader_subassembly_and_filament():
    """the subassembly option given explicitly (as the catalog's humanoid_modules entries give it), a missing root
    refused without leftovers, and the filament option on the palette (the dispenser's mask.b colour)"""
    from eidoblend.characters.robotics.materials import to_linear
    K.clean_scene()
    # the option overrides the entry's own: the left-leg entry told to cut the right leg (and the torso entry told to
    # cut the pelvis, keeping only its own module) gives exactly the catalog's right-leg (pelvis) entry
    for rid, sub, ref in (('humanoid_modules/left_leg', {'root': 'right_leg / leg_mount', 'keepModule': None},
                           'humanoid_modules/right_leg'),
                          ('humanoid_modules/torso', {'root': 'pelvis / pelvis_base', 'keepModule': 'pelvis'},
                           'humanoid_modules/pelvis')):
        a = make_robot(rid, textures=False, subassembly=sub)
        b = make_robot(ref, textures=False)
        sa, sb = a.stats(), b.stats()
        bpy.context.view_layer.update()
        same = all(K.mdiff(a.roots[n].matrix_world, b.roots[n].matrix_world) < 1e-6 for n in b.roots if n in a.roots)
        K.check(f"subassembly={sub} on {rid} = the catalog's {ref} ({sa['triangles']} triangles, {sa['parts']} "
                'parts, same roots in the same place)', sorted(a.parts()) == sorted(b.parts()) and
                sa['triangles'] == sb['triangles'] and sorted(a.roots) == sorted(b.roots) and same)
        a.dispose()
        b.dispose()
    n0 = len(bpy.data.objects)
    ok, msg = raises(lambda: make_robot('humanoid_modules/torso', textures=False, subassembly={'root': 'no such node'}),
                     'Subassembly root is missing or ambiguous')
    K.check(f'a missing subassembly root is refused and leaves nothing ({msg})', ok and len(bpy.data.objects) == n0)
    s = make_robot('filament_spool', filament='#da642c')
    got = s.materials.colors()['filament']
    want = to_linear('#da642c')
    K.check('the filament option sets the palette filament (mask.b)', max(abs(x - y) for x, y in zip(got, want)) < 1e-6,
            f'{tuple(round(v, 4) for v in got)}')
    s.set_colors(filament='#218675')
    got = s.materials.colors()['filament']
    K.check("set_colors(filament=...) changes it", max(abs(x - y) for x, y in zip(got, to_linear('#218675'))) < 1e-6)
    s.dispose()


def with_fabrication():
    """last (it registers the fabrication port's hooks for the rest of the session): RoboticsKit.create_ptfe_tube and
    service_loop forward to filament.js's port, and a dispenser loads with its live filament, whose 'filament-feed'
    play() keys (the reel's turn and the strand's Geometry Nodes inputs), so the saved file pays the strand out alone"""
    from eidoblend.characters.robotics import RoboticsKit as RK
    try:
        import eidoblend.fabrication  # noqa: F401
    except Exception as e:  # noqa: BLE001
        K.check('the fabrication port imports (its hooks)', False, str(e))
        return
    sc = K.clean_scene()
    tube = RK.create_ptfe_tube(points=[(0, 0, 0), (0, 0, .1), (.1, 0, .1), (.1, 0, 0)])
    K.check('RoboticsKit.create_ptfe_tube forwards to the fabrication port (a PTFE tube object)',
            getattr(tube, 'mesh', None) is not None and tube.mesh.name in bpy.data.objects)
    pts = RK.service_loop((0, 0, 0), (.1, 0, 0), .2)
    K.check('RoboticsKit.service_loop forwards too (four control points)', len(pts) == 4)
    sc.frame_start, sc.frame_end = 1, 48
    spool = make_robot('filament_spool', textures=False)
    K.check(f"filament_spool loads with the live filament ({spool.clips})", spool.filament is not None
            and spool.clips[0] == 'filament-feed')
    rec = spool.play('filament-feed')
    K.check(f"play('filament-feed') keys the reel and the strand's inputs ({len(rec['inputs'])} inputs, "
            f"{len(rec['objects'])} objects)", len(rec['inputs']) > 0 and len(rec['objects']) > 0)
    slots = [(o, s) for o, s, _p in spool._modifier_slots()]
    want = {}
    for f in (12, 40):
        sc.frame_set(f)
        want[f] = [tuple(s.value) if hasattr(s.value, '__len__') else s.value for _o, s in slots]
    spool.stop()
    worst = 0.0
    for f, vals in want.items():
        spool.sample('filament-feed', (f - 1) / 24)
        got = [tuple(s.value) if hasattr(s.value, '__len__') else s.value for _o, s in slots]
        for a, b in zip(vals, got):
            a, b = (a if isinstance(a, tuple) else (a,)), (b if isinstance(b, tuple) else (b,))
            worst = max(worst, max(abs(x - y) for x, y in zip(a, b)))
    K.check('the keyed strand inputs equal sample() at frames 12 and 40', worst < 1e-5, f'worst {worst:.1e}')
    spool.dispose()


for fn in (parts_ownership, catalog_content, upright_camera, mirrored_legs, humanoid_limbs, solvers_vs_meshes,
           loader_options, keyed_play, sliders, controls, framing, loader_subassembly_and_filament, saved_file_plays,
           with_fabrication):
    try:
        fn()
    except Exception:  # noqa: BLE001
        K.check(fn.__name__, False, traceback.format_exc().splitlines()[-1])
        traceback.print_exc()
K.save_results('runtime')
