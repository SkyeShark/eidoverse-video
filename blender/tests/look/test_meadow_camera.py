"""tests/look/test_meadow_camera.py: the camera toolkit and the exposure check on the meadow film's two set-ups.

The WebGPU meadow (work/claude_body/film/tools/dlss5nr/meadow/meadow.js) had two cameras: a low tracking camera ahead
of me and to my left, easing round as I come on, the sky behind me; and a tripod at the path's side turning to follow
me past. Here both are built with look.camera on claude_robot.vrm walking through scanned grass in late-afternoon sun
(a neutral world and a sun light: the sky is the sky family's, not this fixture's), then checked: the motion (bounce),
framing, focus and safety audits; the exposure picked by measurement (metered to 18 % grey, the highlight check as the
ceiling, the pick and the ceiling confirmed by real renders); probe stills of both shots, each measured, with a rack
focus in the second from a mark on the meadow beyond the path (picked in the picture) to my chest.

A third camera, not a shot: a long lens down in the grass at the path's side, panning with my legs as I pass. Its
sightline (my ankle back to the lens) runs through five metres of grass blades, so it checks that excluding the
Geometry Nodes scatters excludes their instances (without the exclusion the same path must be blocked by the grass
sources, or the check proves nothing).

    # build (no render): the scene, both shots, every audit; saves out/meadow_camera.blend
    bash run_blender.sh blender/tests/look/test_meadow_camera.py --stage build
    # render (through the GPU slot): exposure sweep + probe stills + contact sheet
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
from eidoblend.look import probe as P                        # noqa: E402
from eidoblend.look import render_settings as RS             # noqa: E402
from eidoblend.look.camera_safety import CameraSafety        # noqa: E402

A = FX.args()
STAGE = FX.arg(A, '--stage', 'all')
OUT = os.path.join(FX.OUT, 'meadow')
BLEND = os.path.join(OUT, 'meadow_camera.blend')
os.makedirs(OUT, exist_ok=True)
REPORT = {}
FAIL = []


def build():
    sc = FX.new_scene(fps=24, frames=(1, 240))
    elev, az = float(FX.arg(A, '--sun-elev', '16')), float(FX.arg(A, '--sun-az', '-70'))
    _w, sun = FX.outdoor_world(sc, elevation_deg=elev, azimuth_deg=az, sun_w_m2=float(FX.arg(A, '--sun-w', '4.5')))
    FX.ground(sc)
    arm, meshes = FX.robot(sc, walk=True, start=(0.0, -7.5, 0.0), speed=1.44)
    grass = FX.meadow_dressing(sc, path_x=0.0, half_gap=0.5, area=(30.0, 60.0), centre_y=0.0)
    RS.apply_auto_enhance(sc, 'film')
    sc.view_settings.exposure = 0.0

    hips = C.bone_target(arm, 'hips')
    chest = C.bone_target(arm, 'chest')
    cams = bpy.data.collections.new('cameras')
    sc.collection.children.link(cams)

    # shot 1, 'track' (meadow.js MW_CAM=track): low, ahead of me on my left, easing round as I come on, aimed a little
    # ahead of my hips; three's offset (sin a, 1.3, cos a + 0.6) x 3.8 with a = 0.95 - 0.35 t/12, in Blender axes
    # (I walk +Y; my left is -X). Three's 34 deg vertical fov; f/2.8 on a full-frame sensor.
    cam1 = C.make_camera('cam_track', fov=34, fstop=2.8, collection=cams, scene=sc)
    fps = C.fps_of(sc)
    span1 = (1, 120)

    def a_of(u):
        t = u * (span1[1] - span1[0]) / fps
        return 0.95 - 0.35 * min(1.0, t / 12.0)
    off = lambda u: Vector((-math.sin(a_of(u)) * 3.8, math.cos(a_of(u)) * 3.8 + 0.6, 0.0))
    REPORT['track'] = C.track(sc, cam1, span1, hips, off, height=1.3, aim_height=1.05, aim_offset=(0, 0.25, 0),
                              smooth_s=0.5)
    REPORT['track_focus'] = C.focus_on(sc, cam1, span1, chest)['range']
    C.add_shot(sc, 'track', span1[0], cam1)

    # shot 2, 'pan' (MW_CAM=pan): a tripod at the path's side turning to follow me past; the same 34 deg lens opened
    # to f/2. The focus racks (frames 128-150) from a mark on the meadow beyond the path, picked IN the picture at the
    # shot's first frame (left of me, just under the horizon), to my chest: the far grass is sharp and I am soft, then
    # the reverse.
    cam2 = C.make_camera('cam_pan', fov=34, fstop=2.0, collection=cams, scene=sc)
    span2 = (121, 240)
    pos2 = Vector((-3.6, 1.2, 1.3))
    REPORT['pan'] = C.pan(sc, cam2, span2, pos2, hips, aim_offset=(0, 0.6, 0), follow='xy', aim_height=1.1, smooth_s=0.4)
    mark = C.point_in_frame(sc, cam2, (0.30, 0.58), frame=span2[0])
    if mark is None:
        raise RuntimeError('the focus mark ray met nothing')
    sc.frame_set(span2[0])
    REPORT['pan_mark'] = {'point': [round(v, 2) for v in mark], 'depth_m': round(C.view_depth(cam2, mark), 2)}
    REPORT['pan_focus'] = C.focus_on(sc, cam2, span2, {'point': mark},
                                     rack={'to': chest, 'frames': (128, 150), 'ease': 'smooth'})['range']
    C.add_shot(sc, 'pan', span2[0], cam2)
    sc.camera = cam1
    # not a shot: a long lens down in the grass (12 cm up; the fixture's grass is 5-30 cm, half of a 5 m run at 10 cm
    # meets a blade), 5.5 m out on the path's right, panning with my legs as I pass (frames 100-160), f/2.8 on my left
    # shin: the blades between are the foreground. Its sightline runs from my ankle back to the lens through them.
    camlow = C.make_camera('cam_low', fov=16, fstop=2.8, collection=cams, scene=sc)
    span3 = (100, 160)
    knee, ankle = C.bone_target(arm, 'leftLowerLeg'), C.bone_target(arm, 'leftLowerLeg', tail=True)
    shin = lambda: (knee() + ankle()) * 0.5
    C.pan(sc, camlow, span3, (5.5, 1.2, 0.12), hips, follow='xy', aim_height=0.5, smooth_s=0.4)
    C.focus_on(sc, camlow, span3, shin)
    from eidoblend.look import lighting as L
    L.log_lights(sc)

    # ---- the audits
    rec = []
    rec += CA.camera_motion_audit(sc)
    rec += CA.framing_audit(sc, subject=arm)
    # the rack starts on the far meadow on purpose: I am soft there by design (allowed), but something must be sharp
    rec += CA.focus_audit(sc, chest, every=2, allow_soft={'pan': (121, 150)})
    cs = CameraSafety(sc, padding=0.5, min_distance=0.3)
    cs.exclude(*grass)
    cs.exclude(arm, sightline_only=True)
    safety = {}
    for name, (fa, fb, cam) in C.shot_spans(sc).items():
        safety[name] = cs.check_camera(cam, (fa, fb), target=chest)
    # the low camera: its lens 12 cm up, so clearance is judged at 8 cm (the ground plane is not a wall)
    safety['low'] = cs.check_camera(camlow, span3, target=ankle, min_distance=0.08)
    bare = CameraSafety(sc, padding=0.5, min_distance=0.3).exclude(arm, sightline_only=True)
    control = bare.check_camera(camlow, span3, target=ankle, min_distance=0.08, log=False)
    grass_names = {o.name for c in bpy.data.collections if c.name == 'meadow_sources' for o in c.all_objects}
    hit = [i for i in control if i['kind'] in ('blocked', 'tight_sightline') and i['object'] in grass_names]
    REPORT['low_control'] = {'issues_without_exclusion': control,
                             'frames_blocked_by_grass': sum(i['frames'][1] - i['frames'][0] + 1 for i in hit)}
    print(f"[meadow] low camera without the grass excluded: {len(hit)} run(s), "
          f"{REPORT['low_control']['frames_blocked_by_grass']} frame(s) blocked by grass sources "
          f"({sorted({i['object'] for i in hit})}); with it excluded: {len(safety['low'])} issue(s)", flush=True)
    if not hit:
        FAIL.append('the low camera\'s sightline never met the grass without exclusion: the exclusion is untested')
    REPORT['audits'] = rec
    REPORT['safety'] = safety
    for r in rec:
        if r['outcome'] != 'PASS':
            FAIL.append(r['message'])
    for name, iss in safety.items():
        for i in iss:
            FAIL.append(f"safety {name}: {i}")
    for name, (fa, fb, cam) in C.shot_spans(sc).items():
        h, v = C.fov_of(cam, sc)
        REPORT.setdefault('lenses', {})[name] = {'lens_mm': round(cam.data.lens, 2), 'fov_h': round(h, 2),
                                                 'fov_v': round(v, 2), 'fstop': cam.data.dof.aperture_fstop}
    print('[meadow] lenses', REPORT['lenses'], flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f'[meadow] saved {BLEND}', flush=True)


def render():
    bpy.ops.wm.open_mainfile(filepath=BLEND, load_ui=False)
    sc = bpy.context.scene
    arm = bpy.data.objects['claude']
    RS.apply_auto_enhance(sc, 'probe')
    print('[meadow] look:', RS.summary(sc), flush=True)

    def subject_box(f):
        sc.frame_set(f)
        pb = CA.projected_box(sc, C.camera_at(sc, f), arm)
        return pb['box'] if pb and pb['box'] else None

    # exposure from frame 60: me in full sun, facing the tracking camera
    sc.frame_set(60)
    sc.camera = C.camera_at(sc, 60)
    ae = EX.auto_expose(sc, os.path.join(OUT, 'sweep'), region=subject_box(60))
    pk = ae['pick']
    REPORT['exposure'] = {'set': ae['exposure'], 'target_median': ae['target'],
                          'pick': {k: pk[k] for k in ('exposure', 'clipped', 'worst_cell', 'luma_median', 'reason',
                                                      'ceiling', 'headroom')},
                          'confirmed': ae['confirmed'],
                          'rows': [{k: r[k] for k in ('exposure', 'clipped', 'worst_cell', 'luma_median', 'luma_p99')}
                                   | ({'subject_median': r['region']['luma_median']} if 'region' in r else {})
                                   for r in ae['rows']]}
    for c in ae['confirmed']:
        if c['changed']:
            print(f"[meadow] the confirming render moved {c['role']}: {c}", flush=True)
    # for looking at, all from the one render: the pick, a stop either side, and where the clipping starts (the
    # ceiling + 1 stop, its clipped pixels painted magenta)
    for s in (-1.0, 0.0, 1.0):
        EX.save_display(sc, os.path.join(OUT, f'exposure_pick{s:+.0f}.png'), exposure=ae['exposure'] + s)
    if pk['ceiling'] is not None:
        over = os.path.join(OUT, 'exposure_ceiling+1.png')
        EX.save_display(sc, over, exposure=pk['ceiling'] + 1.0)
        FS.write_rgb(os.path.join(OUT, 'exposure_ceiling+1_clipmask.png'), FS.clip_mask(FS.read_rgb(over)))
        print(f"[meadow] ceiling + 1 stop: {FS.check_highlights(FS.frame_stats(FS.read_rgb(over)))[1]}", flush=True)

    times = [float(t) for t in (FX.arg(A, '--at', '0.5,2.5,4.5,5.5,6.2,9.0')).split(',')]
    rows = P.render_stills(sc, at=times, out_dir=OUT, name='meadow', region_fn=subject_box)
    REPORT['stills'] = [{k: r[k] for k in ('t', 'frame', 'camera', 'path', 'seconds', 'highlights_ok', 'highlights')}
                        for r in rows]
    for r in rows:
        if not r['highlights_ok']:
            FAIL.append(f"highlights t={r['t']}: {r['highlights']}")
    FS.sheet([r['path'] for r in rows], os.path.join(OUT, 'meadow_sheet.jpg'), cols=3, tile=640,
             labels=[f"t={r['t']}s {r['camera']} clip {r['stats']['clipped'] * 100:.2f}%" for r in rows])
    # the rack, frame by frame through its start: the far meadow sharp and me soft, then the pull to my chest
    rack = P.render_stills(sc, frames=[121, 128, 136, 144, 150, 160], out_dir=os.path.join(OUT, 'rack'), name='rack')
    FS.sheet([r['path'] for r in rack], os.path.join(OUT, 'rack_sheet.jpg'), cols=3, tile=640,
             labels=[f"frame {r['frame']}" for r in rack])
    # the low camera in the grass (not a shot: the markers' cameras unbound for it, so the camera set by hand renders)
    keep = [m.camera for m in sc.timeline_markers]
    for m in sc.timeline_markers:
        m.camera = None
    sc.camera = bpy.data.objects['cam_low']
    low = P.render_stills(sc, frames=[112, 130, 148], out_dir=os.path.join(OUT, 'low'), name='low')
    FS.sheet([r['path'] for r in low], os.path.join(OUT, 'low_sheet.jpg'), cols=3, tile=640,
             labels=[f"cam_low frame {r['frame']}" for r in low])
    for c, m in zip(keep, sc.timeline_markers):
        m.camera = c


if STAGE in ('build', 'all'):
    build()
if STAGE in ('render', 'all'):
    render()
REPORT['fail'] = FAIL
with open(os.path.join(OUT, f'report_{STAGE}.json'), 'w', encoding='utf-8') as fh:
    json.dump(REPORT, fh, indent=1, default=str)
print(f"[meadow] {STAGE}: {'PASS' if not FAIL else 'FAIL'} ({len(FAIL)} finding(s))", flush=True)
for f in FAIL:
    print('  -', f, flush=True)
