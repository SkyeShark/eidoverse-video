"""tests/sets_daisy/render_saved.py: render a set's stills from its SAVED .blend, nothing rebuilt.

The tests build a set, key it, save out/<set>/<set>.blend and write out/<set>/stills.json ([{name, frame, u, camera?}]).
This opens each .blend and renders those frames through the cameras its timeline markers bind (or the still's named
camera), so the GPU slot holds only the renders, and every still proves the contract: the saved file plays and renders
any frame on its own.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_daisy/render_saved.py funeral bridge [--only shot03_bar04,erupt]
    ... heavy.sh 24 ... render_saved.py corner        (its own process: the camp's render peaks at 12.1-12.7 GB)

Writes out/<set>/<set>_<name>.png; prints a PASS/FAIL line per still (the file exists, no magenta, not black).
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _common as C                                        # noqa: E402

import bpy                                                  # noqa: E402

A = C.args()
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
names = [a for a in argv if not a.startswith('--') and a not in A.values()]
only = set(A['only'].split(',')) if A.get('only') else None


def render_set(name):
    d = os.path.join(C.OUT, name)
    blend = os.path.join(d, f'{name}.blend')
    lst = os.path.join(d, 'stills.json')
    if not (os.path.isfile(blend) and os.path.isfile(lst)):
        C.check(f'{name}: a saved .blend and its stills list', False, f'{blend} / {lst}')
        return
    with open(lst, encoding='utf-8') as f:
        stills = json.load(f)
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=blend)
    print(f'[render_saved] {name}: opened in {time.time() - t0:.1f} s, {len(stills)} stills', flush=True)
    sc = bpy.context.scene
    # stills through the timeline's own cameras first, then the ones naming a camera of their own (whose render needs
    # the markers gone: the render pipeline re-applies the marker cameras at the frame)
    stills.sort(key=lambda s: 1 if s.get('camera') else 0)
    for s in stills:
        if only and s['name'] not in only:
            continue
        path = os.path.join(d, f"{name}_{s['name']}.png")
        if s.get('camera'):
            for mk in list(sc.timeline_markers):
                sc.timeline_markers.remove(mk)
            cam = bpy.data.objects.get(s['camera'])
            if cam is None:
                C.check(f"{name} still {s['name']}", False, f"no camera {s['camera']}")
                continue
            sc.frame_set(int(s['frame']))
            sc.camera = cam
            sc.render.filepath = path
            sc.render.image_settings.media_type = 'IMAGE'
            sc.render.image_settings.file_format = 'PNG'
            t1 = time.time()
            bpy.ops.render.render(write_still=True)
            ok, dt = os.path.isfile(path), time.time() - t1
            print(f"[render] frame {s['frame']} -> {os.path.basename(path)} ({dt:.1f} s)", flush=True)
        else:
            ok, dt = C.render_still(sc, int(s['frame']), path)
        st = C.image_stats(path) if ok else {'mean': 0, 'max': 0, 'magenta': 1}
        C.check(f"{name} still {s['name']} (u {s.get('u', 0):.2f}, frame {s['frame']})",
                ok and st['magenta'] < 0.001 and st['max'] > 0.05, f"mean {st['mean']:.3f} max {st['max']:.2f} ({dt:.1f} s)")


for n in names:
    render_set(n)
sys.exit(1 if C.summary('render_saved') else 0)
