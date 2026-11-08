"""Shared bits of the fabrication tests: paths, PASS / FAIL lines, the Deno dump, a studio for probe renders.

Run a test headless from the main checkout (renders through the GPU slot):
    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh <worktree>/blender/tests/fabrication/<test>.py [-- args]
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh <test>.py      # for renders
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(WORKTREE, 'blender'))
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
MAIN = os.environ.get('EIDO_MAIN_CHECKOUT', 'C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01')

RESULTS = {'pass': 0, 'fail': 0, 'lines': []}


def check(name, ok, detail=''):
    line = f"{'PASS' if ok else 'FAIL'} {name}" + (f'  ({detail})' if detail else '')
    print(line, flush=True)
    RESULTS['pass' if ok else 'fail'] += 1
    RESULTS['lines'].append(line)
    return ok


def near(a, b, e):
    return abs(a - b) <= e


def rejects(fn, words):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        return any(w.lower() in msg.lower() for w in words), msg
    return False, 'no error'


def summary(tag):
    print(f"[{tag}] {RESULTS['pass']} passed, {RESULTS['fail']} failed", flush=True)
    with open(os.path.join(OUT, f'{tag}_results.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(RESULTS['lines']) + f"\n{RESULTS['pass']} passed, {RESULTS['fail']} failed\n")
    return RESULTS['fail'] == 0


def deno_dump(script, out_name):
    """Run a .mjs dump of the WebGPU planners in Deno (three from the main checkout); returns its JSON."""
    build = os.path.join(MAIN, 'node_modules', 'three', 'build').replace('\\', '/')
    imap = os.path.join(OUT, 'three_import_map.json')
    with open(imap, 'w', encoding='utf-8') as f:
        json.dump({'imports': {'three/webgpu': 'file:///' + build + '/three.webgpu.js',
                               'three/tsl': 'file:///' + build + '/three.tsl.js'}}, f)
    deno = shutil.which('deno') or 'deno'
    r = subprocess.run([deno, 'run', '--no-config', '--no-lock', '-A', f'--import-map={imap}', script],
                       capture_output=True, text=True, cwd=WORKTREE)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise RuntimeError('deno dump failed')
    path = os.path.join(OUT, out_name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(r.stdout)
    return json.loads(r.stdout)


def t2b(p):
    return (p[0], -p[2], p[1])


# ------------------------------------------------------------------------------------------- probe renders ---

def studio(scene=None, background='#c6cfd1', sun=3.0, hemi=0.9, grid=False):
    """The robotics studio's light in Blender terms: a pale blue-grey room (the RoomEnvironment's soft wrap), a
    warm key from (2, 5, 3) in three's axes, a cool sky / dark ground hemisphere as world gradient."""
    import bpy
    from mathutils import Vector
    from eidoblend.fabrication._axes import color_linear
    scene = scene or bpy.context.scene
    w = bpy.data.worlds.new('studio')
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes['Background']
    grad = nt.nodes.new('ShaderNodeTexGradient')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, math.pi / 2, 0)
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    sky, ground = color_linear('#e6f2ff'), color_linear('#485654')
    room = color_linear(background)
    ramp.color_ramp.elements[0].color = (*[0.5 * g + 0.5 * r for g, r in zip(ground, room)], 1)
    ramp.color_ramp.elements[1].color = (*[0.5 * s + 0.5 * r for s, r in zip(sky, room)], 1)
    nt.links.new(tc.outputs['Normal'], grad.inputs['Vector'])
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Normal'], sep.inputs[0])
    m = nt.nodes.new('ShaderNodeMapRange')
    m.inputs['From Min'].default_value = -1
    m.inputs['From Max'].default_value = 1
    nt.links.new(sep.outputs['Z'], m.inputs['Value'])
    nt.links.new(m.outputs['Result'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = hemi
    scene.world = w
    li = bpy.data.lights.new('studio sun', 'SUN')
    li.energy = sun
    li.angle = math.radians(2.0)
    li.color = color_linear('#fff3e4')
    ob = bpy.data.objects.new('studio sun', li)
    scene.collection.objects.link(ob)
    d = Vector((2, -3, 5)).normalized()                     # three (2, 5, 3) -> Blender (2, -3, 5)
    ob.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    scene.view_settings.view_transform = 'AgX'
    scene.render.engine = 'BLENDER_EEVEE'
    return ob


def camera(scene, location, target, lens=50.0, clip_start=0.01, name='probe cam'):
    import bpy
    from mathutils import Vector
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = clip_start
    cd.clip_end = 50
    cam = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(cam)
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    return cam


def render_settings(scene, width=960, height=540, samples=16):
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.eevee.taa_render_samples = samples
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False


def render_still(scene, path, frame=None):
    import bpy
    if frame is not None:
        scene.frame_set(frame)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    ok = os.path.exists(path)
    print(f"[render] {path} {'written' if ok else 'MISSING'}", flush=True)
    return ok
