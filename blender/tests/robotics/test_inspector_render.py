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

Checks: the status line and the ports list match the robot's stats and ports, the sliders exist for every revolute /
prismatic joint with limits, the part's triangle count matches its ownership table, the UV view drew that many
triangles; a click (pick) at the image centre names the part of the triangle under it (the hit projects back onto the
centre, and its face's owner is that part) and a click on the background names none; set_time(t) shows sample(clip, t);
set_motion re-keys; the toggles hide and show; the process jobs report their state line.

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/robotics/test_inspector_render.py \
        [-- --no-process]
"""

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
    insp.set_time(9.0)
    state = insp.process_state()
    K.check(f"the process state line: '{state}'", 'mm fed' in state)
    insp.set_filament_color('#da642c')
    shot(sc, 'inspector_fdm_process_t9.png', 9.0)
    insp.frame_work()
    shot(sc, 'inspector_fdm_process_t9_work.png', 9.0)
    # the workpiece list: the fork bracket sample instead of the demonstration ring
    insp.set_source('bracket')
    K.check(f"set_source('bracket'): a new print job ({insp['job'].layers} layers)",
            insp['clip'] == 'process' and insp.source_name == 'bracket' and insp['job'].layers > 0)
    insp.set_time(12.0)
    insp.frame_work()
    shot(sc, 'inspector_fdm_bracket_t12_work.png', 12.0)


def cnc_process():
    sc = K.clean_scene()
    insp = inspector_scene('cnc', scene=sc, resolution=(640, 360))
    K.probe_render(sc, (640, 360), 16)
    insp.set_stock(material='brass')
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
    cases = [default_model, humanoid_wire, arm_joints_and_pick, hand_reference]
    if PROCESS:
        cases += [fdm_process, cnc_process, relief_process, spool_wire]
    for fn in cases:
        try:
            fn()
        except Exception:  # noqa: BLE001
            K.check(fn.__name__, False, traceback.format_exc().splitlines()[-1])
            traceback.print_exc()
    K.save_results('inspector_render')


main()
