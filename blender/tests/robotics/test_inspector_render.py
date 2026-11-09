"""The Blender inspector scene (inspector.py, the port of robotics/inspector/viewer.js), built, driven and rendered:

    inspector_payloads__arm_hand_t2.png      the default model and its first clip, keyed over 20 s, frame at 2 s
    inspector_humanoid_wire_t3.png           the humanoid on 'run-circle' with the wireframe overlay on
    inspector_arm_joints.png                 manual mode: the A650's joint sliders moved, the arm posed by its drivers
    inspector_hand_reference.png             the hand closed on the grasp reference cylinder
    inspector_uv_<part>.png                  the UV split view of one part over its map (the hand's palm casting)
    inspector_pick.png                       the arm with the picked part's UV view beside it (inspector_uv_pick.png)
    inspector_fdm_process_t9.png / _work.png the FDM 'process' (the fabrication port's print of the inspector's ring)
                                             mid-print, then "Inspect workpiece"
    inspector_fdm_bracket_t12_work.png       set_source('bracket'): the fork bracket printing
    inspector_cnc_process_t10.png            the CNC 'process' (a pocket mill) in brass, after set_stock
    inspector_relief_process_t12(_work).png  the ball-nose relief carve (physical timing refused: 7.8 hours keyed)
    inspector_spool_wire_t8.png              the dispenser's wireframe following the live strand
    inspector_rotary_t16(_work).png          the rotary machine's 'process' (the sample turned in wood), then
                                             "Inspect workpiece" on its stock
    inspector_rotary_handle_t20_work.png     set_source('handle') on the rotary machine: the supplied mesh carved

Checks: the status line and the ports list match the robot's stats and ports, the sliders exist for every revolute /
prismatic joint with limits, the part's triangle count matches its ownership table, the UV view drew that many
triangles; a click (pick) at the image centre names the part of the triangle under it (the hit projects back onto the
centre, and its face's owner is that part) and a click on the background names none; set_time(t) shows sample(clip, t);
set_motion re-keys; the toggles hide and show; the wireframe is drawn one pixel wide (the Wireframe node in pixel
size, no world-space modifier); a joint slider moves only its joint (the others stay where they were on screen, mid
clip), and Reset after it returns to the motion's pose at 0 s with the sliders' drivers gone and the motion keyed
again; the process state line follows the time slider (equal to the job's own path at 1, 9 and 17 s, on the scene
too); the workpiece-source line (the default invitation, the FDM slicing note, the rotary report's triangles and
views); "Inspect workpiece" frames the rotary stock.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/test_inspector_render.py \
        [-- --no-process]
"""

import math
import os
import sys
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rk as K  # noqa: E402

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402

from eidoblend.characters.robotics.inspector import draw_uv, inspector_scene, part_triangles  # noqa: E402
from eidoblend.characters.robotics.rig import joint_names, set_slider  # noqa: E402
from eidoblend.characters.robotics.studio import world_box  # noqa: E402

OUT = os.path.join(K.OUT, 'inspector')
os.makedirs(OUT, exist_ok=True)
PROCESS = '--no-process' not in K.argv()


def shot(sc, name, t=None):
    f = 1 if t is None else 1 + int(round(t * sc.render.fps))
    p = os.path.join(OUT, name)
    K.check(f'{name}: still', K.still(sc, sc.camera, f, p))
    return p


def default_model():
    sc = K.clean_scene()
    insp = inspector_scene('payloads/arm_hand', scene=sc, resolution=(640, 360))
    K.probe_render(sc, (640, 360), 16)
    r = insp['robot']
    s = r.stats()
    K.check(f"default model: status '{insp['status']}'", str(s['triangles']) in insp['status'].replace(',', ''))
    K.check(f"ports list ({len(r.ports)} ports)", all(n in insp['ports'] for n in r.ports))
    K.check(f"clip {insp['clip']} keyed over 20 s", sc.frame_end == 480 and r._played is not None)
    # the time slider shows the sample at that time (a frame time: the keys are exact there)
    insp.set_time(2.0)
    bpy.context.view_layer.update()
    got = {n: o.matrix_world.copy() for n, o in r.roots.items()}
    r.stop()
    r.sample(insp['clip'], 2.0)
    bpy.context.view_layer.update()
    worst = max(K.mdiff(o.matrix_world, got[n]) for n, o in r.roots.items())
    K.check('set_time(2.0) shows sample(clip, 2.0)', worst < 2e-5, f'worst {worst:.1e}')
    insp.set_motion(insp['clip'])                                   # re-key it (setMotion)
    K.check(f"set_motion re-keyed {insp['clip']}", r._played is not None and r._played['clip'] == insp['clip'])
    insp.set_colors('#d8dcd9', '#3d7f86')
    pk = insp.pickers()
    K.check(f'the pickers show the palette ({pk})', pk['primary'] == '#d8dcd9' and pk['accent'] == '#3d7f86')
    shot(sc, 'inspector_payloads__arm_hand_t2.png', 2.0)
    # the asset list, and switching the model in the same inspector (the old robot disposed)
    from eidoblend.characters.robotics.inspector import asset_list
    ids = [i for i, _l in asset_list()]
    old = r.group.name
    insp.load('camera')
    K.check(f"asset list: {len(ids)} entries without the rotors_ variants; load('camera') replaced the arm",
            len(ids) == 85 and not any(i.startswith('rotors_') for i in ids) and old not in bpy.data.objects
            and insp['robot'].id == 'interaction/camera' and insp['clip'] == 'joints')


def humanoid_wire():
    sc = K.clean_scene()
    insp = inspector_scene('humanoid', clip='run-circle', wireframe=True, scene=sc, resolution=(640, 360))
    K.probe_render(sc, (640, 360), 16)
    K.check(f"wireframe overlay: {len(insp['wire'])} objects", len(insp['wire']) == len(insp['robot'].meshes()))
    mats = {s.material for w in insp['wire'] for s in w.material_slots}
    pixel = all(any(n.type == 'WIREFRAME' and n.use_pixel_size and abs(n.inputs['Size'].default_value - 1.0) < 1e-9
                    for n in m.node_tree.nodes) for m in mats)
    K.check(f"the wire is one pixel wide at any size ({len(mats)} material: the Wireframe node in pixel size; no "
            'world-space Wireframe modifier)', pixel and len(mats) == 1
            and not any(md.type == 'WIREFRAME' for w in insp['wire'] for md in w.modifiers))
    insp.set_wireframe(False)
    off = all(w.hide_render for w in insp['wire'])
    insp.set_wireframe(True)
    K.check('the wireframe toggle hides and shows the overlay', off and not any(w.hide_render for w in insp['wire']))
    shot(sc, 'inspector_humanoid_wire_t3.png', 3.0)


def arm_joints_and_pick():
    sc = K.clean_scene()
    insp = inspector_scene('arm', joints=True, scene=sc, resolution=(640, 360))
    K.probe_render(sc, (640, 360), 16)
    r = insp['robot']
    want = joint_names(r)
    K.check(f'joint sliders for {want}', sorted(insp['joints']) == sorted(want) and len(want) == 6)
    for n, v in zip(sorted(want), (0.4, 0.6, -0.7, 0.5, 0.9, 0.3)):
        set_slider(r, n, v)
    insp.set_joint('a650_j6', 0.3)
    shot(sc, 'inspector_arm_joints.png')
    # a click on the arm (the image centre, else the first point of a 7 x 7 grid that hits) and one on the background
    insp.fit()
    part, xy = '', None
    for x, y in [(0.5, 0.5)] + [(i / 8, j / 8) for j in range(1, 8) for i in range(1, 8)]:
        part = insp.pick(x, y)
        if part:
            xy = (x, y)
            break
    hit = insp['hit']
    if xy is not None and hit is not None:
        bpy.context.view_layer.update()
        u, v, _d = world_to_camera_view(sc, sc.camera, hit['location'])
        owner = r.part_faces(hit['object'])[hit['face']]
        ok = abs(u - xy[0]) < 2e-3 and abs((1 - v) - xy[1]) < 2e-3 and owner == part
        K.check(f"pick{xy} names '{part}' ({insp['part_triangles']} triangles): the hit projects back onto the "
                'clicked point and its face belongs to that part',
                ok and insp['part_triangles'] == part_triangles(r, part), f'({u:.4f}, {1 - v:.4f})')
    else:
        K.check('a click on the image hits the arm', False, str(hit))
    K.check("pick(0.02, 0.02) on the background names no part", insp.pick(0.02, 0.02) == '' and insp['hit'] is None)
    if part:
        insp.pick_part(part)
        rec = insp.draw_uv(os.path.join(OUT, 'inspector_uv_pick.png'))
        K.check(f"the picked part's UV view drew {rec['triangles']} triangles", rec['triangles'] > 0)
    shot(sc, 'inspector_pick.png')


def manual_mode_and_reset():
    """viewer.js's joint slider (manual = true; setJoints one joint) and Reset (manual = false; time = 0; sample()),
    mid clip on the A650's 'joints'; no render"""
    sc = K.clean_scene()
    insp = inspector_scene('arm', scene=sc, resolution=(640, 360))
    r = insp['robot']
    clip = insp['clip']

    def pose():
        bpy.context.view_layer.update()
        return {n: o.matrix_world.copy() for n, o in r.roots.items()}

    def worst(a, b, skip=()):
        return max((K.mdiff(a[n], b[n]) for n in a if n not in skip), default=0.0)
    insp.set_time(2.0)
    at2 = pose()
    insp.set_joint('a650_j6', 0.3)
    moved = pose()
    others = worst(at2, moved, skip=('a650_j6',))
    K.check(f"a slider mid clip moves only its joint: the other joints stay where they were at 2 s ({others:.1e}), "
            f"a650_j6 turned ({K.mdiff(at2['a650_j6'], moved['a650_j6']):.3f})",
            others < 1e-5 and K.mdiff(at2['a650_j6'], moved['a650_j6']) > 1e-3 and insp.manual)
    insp.set_joint('a650_j2', 99.0)
    lim = r.specs['a650_j2']['limits']
    K.check(f"a slider value beyond the joint's range is clamped to it ({r.group['joint:a650_j2']:.4f} in {lim})",
            abs(r.group['joint:a650_j2'] - lim[1]) < 1e-9)
    insp.reset()
    back = pose()
    insp.set_time(0.0)
    at0 = pose()
    drivers = sum(len(o.animation_data.drivers) for o in r.roots.values() if o.animation_data)
    K.check(f"Reset after the sliders: the '{clip}' pose at 0 s (worst {worst(back, at0):.1e}), manual mode off, "
            f"the clip keyed again, no slider drivers left ({drivers})",
            worst(back, at0) < 1e-5 and not insp.manual and r._played is not None and r._played['clip'] == clip
            and drivers == 0 and not insp['joints'] and not any(k.startswith('joint:') for k in r.group.keys()))
    insp.set_time(2.0)
    K.check('the time slider after Reset shows the clip at 2 s again', worst(pose(), at2) < 1e-5)
    insp.set_joint('a650_j3', -0.4)
    insp.set_time(1.0)
    got, manual = pose(), insp.manual
    r.stop()
    r.sample(clip, 1.0)
    want = pose()
    K.check('the time slider leaves manual mode too (set_time(1) after a slider shows sample(clip, 1))',
            worst(got, want) < 1e-5 and not manual, f'worst {worst(got, want):.1e}')
    insp.dispose()


def hand_reference():
    sc = K.clean_scene()
    part = 'DH palm casting'
    insp = inspector_scene('hand', reference=True, scene=sc, resolution=(640, 360),
                           uv=os.path.join(OUT, 'inspector_uv_palm.png'))
    r = insp['robot']
    if part not in r.parts():
        part = sorted(r.parts())[0]
    insp_uv = draw_uv(r, os.path.join(OUT, 'inspector_uv_part.png'), part=part)
    n = part_triangles(r, part)
    K.check(f"part picker '{part}': {n} triangles; the UV view drew {insp_uv['triangles']}",
            n > 0 and insp_uv['triangles'] <= n)
    K.check('UV split view written', os.path.exists(os.path.join(OUT, 'inspector_uv_palm.png')))
    insp.set_reference(False)
    hidden = all(o.hide_render for o in insp['references'])
    insp.set_reference(True)
    K.check('the grasp-reference toggle hides and shows the cylinder', hidden and
            not any(o.hide_render for o in insp['references']))
    K.probe_render(sc, (640, 360), 16)
    r.stop()
    r.grasp(1.0)
    from eidoblend.characters.robotics.studio import frame_camera
    frame_camera(sc.camera, [r.group], margin=1.1, visible_only=True)
    shot(sc, 'inspector_hand_reference.png')


def fdm_process():
    sc = K.clean_scene()
    insp = inspector_scene('fdm', scene=sc, resolution=(640, 360))
    K.probe_render(sc, (640, 360), 16)
    job = insp['job']
    K.check(f"fdm opens on 'process': a print job of {job.duration:g} s (time lapse 18 s)",
            insp['clip'] == 'process' and job is not None and abs(job.duration - 18) < 1e-9)
    K.check(f"the workpiece-source line without a supplied mesh: '{insp['source_info']}'",
            insp['source_info'].startswith('Load a model or choose a mesh example')
            and sc['inspector_source_info'] == insp['source_info'])
    lines, fed = [], []
    for t in (1.0, 9.0, 17.0):
        insp.set_time(t)
        st = job.path.sample(t / job.duration * job.path.duration)
        want = (f"{st.type} | {st.filament_length * 1000:.1f} mm fed | "
                f"{(st.filament_retraction or 0) * 1000:.2f} mm retracted")
        lines.append((insp.process_state(), want, sc['inspector_process_state']))
        fed.append(st.filament_length)
    K.check('the process state line follows the time slider: ' + ' / '.join(a for a, _w, _s in lines),
            all(a == w == s for a, w, s in lines) and fed[0] < fed[1] < fed[2])
    insp.set_time(9.0)
    insp.set_filament_color('#da642c')
    shot(sc, 'inspector_fdm_process_t9.png', 9.0)
    insp.frame_work()
    shot(sc, 'inspector_fdm_process_t9_work.png', 9.0)
    # the workpiece list: the fork bracket sample instead of the demonstration ring
    insp.set_source('bracket')
    K.check(f"set_source('bracket'): a new print job ({insp['job'].layers} layers)",
            insp['clip'] == 'process' and insp.source_name == 'bracket' and insp['job'].layers > 0)
    K.check(f"the workpiece-source line names it with the slicing note: '{insp['source_info']}'",
            insp['source_info'] == 'bracket. Closed solids are sliced with 25% infill. Supports are not generated '
            'automatically.')
    insp.set_time(12.0)
    insp.frame_work()
    shot(sc, 'inspector_fdm_bracket_t12_work.png', 12.0)


def cnc_process():
    sc = K.clean_scene()
    insp = inspector_scene('cnc', scene=sc, resolution=(640, 360))
    K.probe_render(sc, (640, 360), 16)
    insp.set_stock(material='brass')
    job = insp['job']
    speeds = []
    for t in (1.0, 9.0):
        insp.set_time(t)
        st = job.path.sample(t / job.duration * job.path.duration)
        speeds.append((insp.process_state(), f"{st.speed * 60000:.0f} mm/min"))
    K.check('cnc: the state line follows the time slider (the feed at 1 s and 9 s): '
            + ' / '.join(a for a, _w in speeds), all(a.endswith(w) for a, w in speeds) and speeds[0][0] != speeds[1][0])
    insp.set_time(10.0)
    state = insp.process_state()
    K.check(f"cnc: a pocket mill restarted in brass: '{state}'", insp['job'] is not None and 'brass' in state)
    shot(sc, 'inspector_cnc_process_t10.png', 10.0)


def relief_process():
    """the ball-nose machine's 'process': the fabrication port's relief carve of the original sample; physical timing
    (7.8 hours of machining, every frame keyed) is refused with the numbers"""
    sc = K.clean_scene()
    insp = inspector_scene('cnc_relief', scene=sc, resolution=(640, 360))
    K.probe_render(sc, (640, 360), 16)
    insp.set_time(12.0)
    state = insp.process_state()
    K.check(f"cnc_relief: the relief carve's state line '{state}'", insp['job'] is not None and 'rpm' in state)
    shot(sc, 'inspector_relief_process_t12.png', 12.0)
    insp.frame_work()
    shot(sc, 'inspector_relief_process_t12_work.png', 12.0)
    try:
        insp.set_timing('physical')
        K.check('physical timing of the relief is refused', False, 'accepted')
    except ValueError as e:
        K.check(f'physical timing of the relief is refused ({str(e)[:70]})', 'keyed frames' in str(e))


def rotary_process():
    """the XYZ + A machine's 'process' (the fabrication port's rotary_carve of the sample, turned in wood): the state
    line follows the slider (its A angle the path's), "Inspect workpiece" frames the stock (an empty with a Volume to
    Mesh child), and set_source('handle') carves the supplied mesh with the report's source line. 4 fps and a
    128 x 48 x 48 stock field keep the per-frame stock cache small; the cache is deleted at the end."""
    import shutil
    cache = os.path.join(OUT, '_rotary_stock_cache')
    try:
        sc = K.clean_scene(fps=4)
        opts = {'cache_dir': cache, 'resolution': (128, 48, 48), 'max_particles': 400}
        insp = inspector_scene('cnc_rotary', scene=sc, fps=4, resolution=(640, 360), process_options=opts)
        K.probe_render(sc, (640, 360), 16)
        job = insp['job']
        K.check(f"cnc_rotary opens on 'process': the rotary time lapse of {job.duration:g} s in "
                f"{insp.stock_material}", insp['clip'] == 'process' and abs(job.duration - 32) < 1e-9
                and insp.stock_material == 'wood')
        lines = []
        for t in (8.0, 16.0):
            insp.set_time(t)
            st = job.path.sample(t / job.duration * job.path.duration)
            lines.append((insp.process_state(), f" | A {math.degrees(st['angle']):.1f}°"))
        K.check('rotary: the state line follows the slider (A angle at 8 s and 16 s): ' + ' / '.join(a for a, _w in lines),
                all(w in a for a, w in lines) and lines[0][0] != lines[1][0])
        shot(sc, 'inspector_rotary_t16.png', 16.0)
        before = sc.camera.location.copy()
        target = insp.frame_work()
        lo, hi = world_box([job.mesh])
        K.check(f"rotary: Inspect workpiece frames the stock (camera moved {(sc.camera.location - before).length:.2f} m "
                'onto the centre of its evaluated surface)', lo.x <= hi.x and (sc.camera.location - before).length > 0.05
                and (target - (lo + hi) / 2).length < 1e-6)
        shot(sc, 'inspector_rotary_t16_work.png', 16.0)
        insp.set_source('handle')
        rep = insp['job'].program.report
        tris = rep['source']['triangles']
        K.check(f"rotary: set_source('handle') carves it; the source line: '{insp['source_info']}'",
                insp['source_info'].startswith(f"handle. {tris:,} source triangles; {rep['orientations']} indexed "
                                                'views. ') and insp['source_info'].endswith('Undercuts and holding ends '
                                                                                           'may remain.'))
        insp.set_time(20.0)
        insp.frame_work()
        shot(sc, 'inspector_rotary_handle_t20_work.png', 20.0)
        insp.dispose()
    finally:
        shutil.rmtree(cache, ignore_errors=True)


def spool_wire():
    """the dispenser with the fabrication port's live filament (its installer is registered once the process cases
    imported eidoblend.fabrication): the wireframe of the strand follows the strand's Geometry Nodes surface"""
    import eidoblend.fabrication  # noqa: F401
    from mathutils import Vector
    sc = K.clean_scene()
    insp = inspector_scene('filament_spool', wireframe=True, scene=sc, resolution=(640, 360))
    K.probe_render(sc, (640, 360), 16)
    insp.set_time(8.0)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    procedural = [w for w in insp['wire'] if w.get('procedural_source')]
    worst = 0.0
    for w in procedural:
        src = w.parent
        a = [src.matrix_world @ Vector(c) for c in src.evaluated_get(dg).bound_box]
        b = [w.matrix_world @ Vector(c) for c in w.evaluated_get(dg).bound_box]
        worst = max(worst, (a[0] - b[0]).length, (a[6] - b[6]).length)
    K.check(f"filament_spool: {len(procedural)} wire overlay(s) follow the live strand's evaluated surface",
            len(procedural) > 0 and worst < 2e-3, f'box offset {worst * 1000:.2f} mm (wire thickness included)')
    shot(sc, 'inspector_spool_wire_t8.png', 8.0)


def main():
    cases = [default_model, humanoid_wire, arm_joints_and_pick, manual_mode_and_reset, hand_reference]
    if PROCESS:
        cases += [fdm_process, cnc_process, relief_process, rotary_process, spool_wire]
    for fn in cases:
        try:
            fn()
        except Exception:  # noqa: BLE001
            K.check(fn.__name__, False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
    K.save_results('inspector_render')


main()
