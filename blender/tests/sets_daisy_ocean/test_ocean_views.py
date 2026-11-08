"""The saved verse (test_ocean_shots.py's ocean_verse3_<tag>.blend) reopened in a fresh Blender: a still re-rendered from
the keys alone must match the first session's, and a few extra views the film's shots never hold long: the whole
headland from above, the faces surfacing at the waterline, the robot breaking up, the human of light coming apart, the
echoes' lanterns over the sea before they sink.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy_ocean/test_ocean_views.py [--tag night]
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

args = C.argv()
tag = args[args.index('--tag') + 1] if '--tag' in args else 'night'
SRC = os.path.join(C.OUT, 'shots_' + tag)
blend = os.path.join(SRC, f'ocean_verse3_{tag}.blend')
bpy.ops.wm.open_mainfile(filepath=blend)
sys.path.insert(0, C.BLENDER_DIR)
from eidoblend.sets.daisy.ocean.land import make_coast  # noqa: E402
from eidoblend.sets.daisy.ocean.util import B3  # noqa: E402

OUT = os.path.join(C.OUT, 'views_' + tag)
os.makedirs(OUT, exist_ok=True)
ck = C.Checks('views')
sc = bpy.context.scene
FPS = sc.render.fps
group = bpy.data.objects['set:ocean']
layout = bpy.data.objects['ocean:layout']
PSI = layout.rotation_euler.z
MARK_Y = make_coast().markY


def set_world(p3):
    """design (three) -> world"""
    from eidoblend.sets.daisy.ocean import _three as T
    return group.matrix_world @ Vector(B3(T.apply_axis_angle(p3, (0.0, 1.0, 0.0), PSI)))


def frame_of(u):
    return sc.frame_start + int(round(u * FPS))


def render(name, f, cam=None):
    sc.frame_set(f)
    if cam is not None:
        sc.camera = cam
    path = os.path.join(OUT, f'{name}_f{f:04d}.png')
    sc.render.filepath = path
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[views] {name} frame {f} {time.time() - t1:.1f}s', flush=True)
    return path


from PIL import Image  # noqa: E402

# ---- the saved keys alone reproduce a still of the first session
set_cam = sc.camera
first = [p for p in os.listdir(SRC) if p.startswith('B_reveal_f') and p.endswith('.png')]
if first:
    f = int(first[0].split('_f')[1][:4])
    again = render('B_reveal_reopened', f, set_cam)
    a = np.asarray(Image.open(os.path.join(SRC, first[0])).convert('RGB'), np.float32)
    b = np.asarray(Image.open(again).convert('RGB'), np.float32)
    d = np.abs(a - b)
    ck.check('the reopened .blend renders the same still (keys only, no handlers)', d.mean() < 1.0,
             f'mean |diff| {d.mean():.3f} / 255, p99 {np.percentile(d, 99):.1f}')

# ---- extra views (design frame, three axes)
pc = bpy.data.objects.new('probe_cam', bpy.data.cameras.new('probe_cam'))
sc.collection.objects.link(pc)
pc.data.sensor_fit = 'VERTICAL'
pc.data.clip_start, pc.data.clip_end = 0.05, 3200.0
pc.rotation_mode = 'QUATERNION'


def aim(pos3, tgt3, fov):
    p, t = set_world(pos3), set_world(tgt3)
    pc.location = p
    pc.rotation_quaternion = (t - p).to_track_quat('-Z', 'Y')
    pc.data.angle_y = math.radians(fov)


E = MARK_Y + 1.52
views = [
    ('X_aerial_headland', 33.0, (7.0, 16.0, 20.0), (-4.0, 0.0, -14.0), 50.0),
    ('X_waterline_faces', 27.0, (2.6, MARK_Y - 0.3, -3.2), (5.0, -0.6, -22.0), 50.0),
    ('X_echo_lanterns', 0.8, (-0.4, E + 0.35, 3.2), (6.0, 1.5, -60.0), 45.0),
    # her flowers shut for the night round her feet (the film's shots never hold them), the sea beyond
    ('X_rise_daisies', 30.5, (1.5, MARK_Y + 0.5, 2.1), (-0.2, MARK_Y + 0.15, -0.6), 42.0),
    # the dune grass along the cove toward the house, the porch light on
    ('X_dunes_to_house', 30.5, (-6.0, 1.75, 4.5), (-11.0, 1.2, -24.0), 38.0),
]
stills = []
for name, u, p3, t3, fov in views:
    aim(p3, t3, fov)
    stills.append((name, render(name, frame_of(u), pc)))
for name, u in (('E_robot_breaking_up', 16.3), ('E_human_coming_apart', 17.85)):
    stills.append((name, render(name, frame_of(u), set_cam)))
# the sea's look uniforms, each against the aerial: thicker haze, no moon, a cold moon
sea = bpy.data.objects['ocean_of_faces']
aim(*views[0][2:])
base = np.asarray(Image.open(stills[0][1]).convert('RGB'), np.float32)
for name, k, v in (('U_fog_x4', 'fog', 0.0044), ('U_moonI_0', 'moonI', 0.0), ('U_moonCol_red', 'moonCol', (1.0, 0.3, 0.2))):
    old = sea[k]
    sea[k] = v
    sea.update_tag()                               # a property set from Python: tag it so the drivers follow
    p = render(name, frame_of(views[0][1]), pc)
    sea[k] = old
    sea.update_tag()
    a = np.asarray(Image.open(p).convert('RGB'), np.float32)
    ck.check(f'sea uniform {k} -> {v} changes the picture', np.abs(a - base).mean() > 0.5, f'mean |diff| {np.abs(a - base).mean():.2f} / 255')
    stills.append((name, p))
for name, p in stills:
    a = np.asarray(Image.open(p).convert('RGB'), np.float32) / 255.0
    ck.check(f'{name}: rendered', a.mean() > 0.005, f'mean {a.mean():.3f}')
# ---- the reveal in motion (u 4.0 - 7.0 from the film's camera, 480 x 270): the faces sweep out and surface on the swell
if '--no-motion' not in args:
    import subprocess
    seq = os.path.join(OUT, 'reveal_seq')
    os.makedirs(seq, exist_ok=True)
    sc.camera = set_cam
    r = sc.render
    keep = (r.resolution_x, r.resolution_y, sc.frame_start, sc.frame_end, r.filepath)
    r.resolution_x, r.resolution_y = 480, 270
    f0, f1 = frame_of(4.0), frame_of(7.0)
    sc.frame_start, sc.frame_end = f0, f1
    r.filepath = os.path.join(seq, 'f_')
    t1 = time.time()
    bpy.ops.render.render(animation=True)
    print(f'[views] reveal sequence {f1 - f0 + 1} frames {time.time() - t1:.1f}s', flush=True)
    r.resolution_x, r.resolution_y, sc.frame_start, sc.frame_end, r.filepath = keep
    mp4 = os.path.join(OUT, 'reveal_u4-7_480p.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', str(f0),
                    '-i', os.path.join(seq, 'f_%04d.png'), '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                    '-shortest', '-c:v', 'libx264', '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-crf', '18',
                    '-c:a', 'aac', '-b:a', '96k', mp4], check=False)
    ck.check('the reveal plays as an H.264 clip', os.path.exists(mp4) and os.path.getsize(mp4) > 10000,
             f'{os.path.getsize(mp4) // 1024} KB' if os.path.exists(mp4) else 'missing')
th = [Image.open(p).convert('RGB').resize((480, 270)) for _n, p in stills]
sheet = Image.new('RGB', (480 * 3, 270 * ((len(th) + 2) // 3)))
for i, t in enumerate(th):
    sheet.paste(t, ((i % 3) * 480, (i // 3) * 270))
sheet.save(os.path.join(OUT, f'views_sheet_{tag}.png'))
ck.summary()
with open(os.path.join(OUT, 'test_ocean_views.json'), 'w') as f:
    json.dump(ck.rows, f, indent=1)
