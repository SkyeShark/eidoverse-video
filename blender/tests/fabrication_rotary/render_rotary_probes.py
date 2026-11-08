"""Renders probe stills of saved rotary builds (test_rotary_examples.py, test_rotary_mesh_carve.py, test_rotary_chips.py,
test_rotary_target_vs_carved.py, test_rotary_materials_lineup.py) with EEVEE: each frame as it plays, jumped to, from
the build's own camera or from extra close-up cameras. Several builds render in one Blender run.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/fabrication_rotary/render_rotary_probes.py -- blend=out/rotary_example.blend \
        [frames=1,37,73] [scale=50] [samples=16] [tag=rotary] [views=scene,close,side] [size=WxH]
    ... render_rotary_probes.py -- jobs="out/rotary_example.blend@73,241@close@rotary;out/rotary_mesh_example.blend@1,97@scene"

jobs: ';'-separated <blend>@<frames>@<views>[@<tag>] (frames and views as below), one after another in this run.
views: 'scene' the build's camera; 'close' a 3/4 close-up on the stock from the cutter's side; 'side' straight at the
stock from the front (-Y), level with the axis; 'top' down on it. Writes out/probes/<tag>_<view>_f<frame>.png.
Prints a FAIL line for any still that was not written.
"""

import os
import sys
import time

import bpy
from mathutils import Vector

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
HERE = os.path.dirname(os.path.abspath(__file__))
args = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
OUT = os.path.join(HERE, 'out', 'probes')
os.makedirs(OUT, exist_ok=True)
MISSING = []


def add_camera(sc, name, eye, target, lens=50):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start, cd.clip_end = 0.005, 20
    ob = bpy.data.objects.new(name, cd)
    sc.collection.objects.link(ob)
    ob.location = eye
    ob.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def render(blend, frames, views, tag):
    blend = blend if os.path.isabs(blend) else os.path.join(HERE, blend)
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    tag = tag or os.path.splitext(os.path.basename(blend))[0]
    frames = frames or [sc.frame_start]
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = int(args.get('samples', 16))
    if args.get('size'):
        w, h = (int(v) for v in args['size'].split('x'))
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.resolution_percentage = 100
    else:
        sc.render.resolution_percentage = int(args.get('scale', 50))
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    scene_cam = sc.camera
    frame_ob = bpy.data.objects.get('Rotary stock frame')
    cams = {}
    if frame_ob is not None:
        bpy.context.view_layer.update()
        c = frame_ob.matrix_world.translation.copy()
        if 'close' in views:
            cams['close'] = add_camera(sc, 'probe close', c + Vector((-0.10, -0.16, 0.07)), c + Vector((0.004, 0, 0)),
                                       lens=60)
        if 'side' in views:
            cams['side'] = add_camera(sc, 'probe side', c + Vector((0.004, -0.30, 0.0)), c + Vector((0.004, 0, 0)),
                                      lens=85)
        if 'top' in views:
            cams['top'] = add_camera(sc, 'probe top', c + Vector((0.004, -0.01, 0.30)), c + Vector((0.004, 0, 0)),
                                     lens=85)
    if 'scene' in views:
        cams['scene'] = scene_cam
    for f in frames:
        for v in views:
            cam = cams.get(v)
            if cam is None:
                continue
            sc.camera = cam
            sc.frame_set(f)
            sc.render.filepath = os.path.join(OUT, f'{tag}_{v}_f{f:04d}.png')
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            ok = os.path.exists(sc.render.filepath)
            if not ok:
                MISSING.append(sc.render.filepath)
            print(f'rendered {sc.render.filepath} in {time.time() - t0:.1f} s' if ok else
                  f'FAIL not written: {sc.render.filepath}', flush=True)
    sc.camera = scene_cam


def frame_list(text):
    return [int(v) for v in text.split(',')] if text else None


if args.get('jobs'):
    for spec in args['jobs'].split(';'):
        parts = spec.split('@') + [''] * 3
        render(parts[0], frame_list(parts[1]), (parts[2] or 'scene').split(','), parts[3] or None)
else:
    render(args['blend'], frame_list(args.get('frames')), args.get('views', 'scene').split(','), args.get('tag'))
print('\n%d FAIL' % len(MISSING) if MISSING else '\nALL WRITTEN')
