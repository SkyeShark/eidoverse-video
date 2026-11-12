"""Render controller tests' stills from their saved, keyed .blend files (the bakes ran on the CPU; only this takes the GPU
slot, once for any number of tests).

    render_shots.py <out/TAG_shots.json> [<out/TAG2_shots.json> ...] [--only PREFIX[,PREFIX...]] [--sheet-cols 4]

Each shot: a camera at `pos` looking at `target` with `lens`, at `frame` (with `action` assigned first when the shot
names another bake of the same armature) -> out/<tag>_<name>.png (960x540, 16 samples, EEVEE, the light saved in the
.blend). Each sheet: its shots, half size, labelled, in rows -> out/<tag>_<sheet>.png.

    bash C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/gpu_slot.sh \\
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/render_shots.py \\
        C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-blender/blender/tests/controller/out/course_claude_robot_shots.json
"""

import json
import os
import sys
import time

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')))
from eidoblend.characters.springs import use_springs  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ONLY = tuple(ARGS[ARGS.index('--only') + 1].split(',')) if '--only' in ARGS else None   # name prefixes, comma separated
COLS = int(ARGS[ARGS.index('--sheet-cols') + 1]) if '--sheet-cols' in ARGS else 4
SPECS = [a for a in ARGS if a.endswith('.json')]


def render(spec_path):
    t0 = time.time()
    spec = json.load(open(spec_path, encoding='utf-8'))
    out, tag = os.path.dirname(os.path.abspath(spec_path)), spec['tag']
    bpy.ops.wm.open_mainfile(filepath=spec['blend'])
    sc = bpy.context.scene
    cd = bpy.data.cameras.new('shot_cam')
    cd.clip_start, cd.clip_end = 0.05, 300.0
    cam = bpy.data.objects.new('shot_cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    done = {}
    for s in spec['shots']:
        if ONLY and not s['name'].startswith(ONLY):
            continue
        if s.get('action'):
            act = bpy.data.actions[s['action']]
            for ob in sc.objects:
                if ob.type == 'ARMATURE' and ob.animation_data is not None and ob.animation_data.action is not None:
                    ob.animation_data.action = act
                    if len(act.slots):
                        ob.animation_data.action_slot = act.slots[0]
                    if bpy.data.actions.get(act.name + '|springs') is not None:
                        use_springs(ob, act.name + '|springs')      # that take's own spring chains with it
        cd.lens = s.get('lens', 35.0)
        cam.location = Vector(s['pos'])
        cam.rotation_mode = 'QUATERNION'
        cam.rotation_quaternion = (Vector(s['target']) - Vector(s['pos'])).to_track_quat('-Z', 'Y')
        sc.frame_set(s['frame'])
        p = os.path.join(out, f'{tag}_{s["name"]}.png')
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        done[s['name']] = p if os.path.exists(p) else None
        print(f'[render_shots] {tag} {s["name"]} f{s["frame"]}: {"ok" if done[s["name"]] else "MISSING"}', flush=True)
    for name, names in (spec.get('sheets') or {}).items():
        sheet([done.get(n) for n in names], os.path.join(out, f'{tag}_{name}.png'), names)
    print(f'[render_shots] {tag}: {sum(1 for v in done.values() if v)}/{len(done)} stills in {time.time() - t0:.1f} s',
          flush=True)


def sheet(paths, out, labels, cols=None):
    from PIL import Image, ImageDraw
    cols = cols or COLS
    ims = [(Image.open(p).convert('RGB') if p and os.path.exists(p) else None) for p in paths]
    real = [im for im in ims if im is not None]
    if not real:
        return
    w, h = real[0].size
    tw, th = w // 2, h // 2
    rows = (len(ims) + cols - 1) // cols
    sh = Image.new('RGB', (cols * tw, rows * th), (16, 16, 16))
    for i, (im, lab) in enumerate(zip(ims, labels)):
        if im is None:
            continue
        im = im.resize((tw, th))
        ImageDraw.Draw(im).text((6, 4), lab, fill=(255, 255, 0))
        sh.paste(im, ((i % cols) * tw, (i // cols) * th))
    sh.save(out)


for sp in SPECS:
    try:
        render(sp)
    except Exception as e:  # noqa: BLE001 - one test's failure must not stop the others' stills
        import traceback
        traceback.print_exc()
        print(f'[render_shots] FAILED {sp}: {e}', flush=True)
