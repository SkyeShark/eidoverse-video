"""The terrain guide's examples run (SURFACING_DESIGN.md 5.4, package 5, item 4): every Python example of
tools-guides/terrain-surfaces.md's sections on the surface, the plants and the call's generate-then-build pattern,
executed in order in one namespace, in Blender as a GPU job (the bake's kernels, the planning, a material build):

    bash run_blender.sh blender/tests/terrain/surfacing_judge/test_guide.py
    (on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

A line holding a placeholder (<repo>, <dir>) is left out (sys.path is set here). Before the examples, make_terrain is
imported (the section's first example does it), `cam` is a camera object in the scene and (x, y) a point on the
meadow: the names the examples assume. Prints [PASS] / [FAIL]
per example with its first line, and a summary.
"""
import os
import re
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
BLENDER_DIR = os.path.normpath(os.path.join(TN, '..', '..'))
REPO = os.path.normpath(os.path.join(BLENDER_DIR, '..'))
GUIDE = os.path.join(REPO, 'tools-guides', 'terrain-surfaces.md')
if BLENDER_DIR not in sys.path:
    sys.path.insert(0, BLENDER_DIR)
# the sections whose examples run, in the guide's order: (heading, which python blocks of it: None for all)
SECTIONS = (('### The call', [1]), ('### The surface', None), ('### Maps for your own shaders', None),
            ('### Plants', None), ('### Saving and reopening', None))


def blocks(text):
    """[(heading, index within its section, code)] of the guide's ```python blocks."""
    out = []
    heading, k = None, 0
    for m in re.finditer(r'^(#{2,3} [^\n]+)$|^```python\n(.*?)^```', text, re.M | re.S):
        if m.group(1):
            heading, k = m.group(1).strip(), 0
        else:
            out.append((heading, k, m.group(2)))
            k += 1
    return out


def main():
    import bpy
    text = open(GUIDE, encoding='utf-8').read()
    want = []
    for h, k, code in blocks(text):
        for sec, which in SECTIONS:
            if h == sec and (which is None or k in which):
                want.append((h, k, code))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    cam = bpy.data.objects.new('guide_cam', bpy.data.cameras.new('guide_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    from eidoblend.terrain import make_terrain               # the section's first example imports it
    ns = {'cam': cam, 'x': 0.0, 'y': -20.0, 'make_terrain': make_terrain, '__name__': 'guide'}
    ok = 0
    t0 = time.time()
    for h, k, code in want:
        lines = [ln for ln in code.splitlines() if '<repo>' not in ln and '<dir>' not in ln]
        first = next((ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith('#')), '')
        t1 = time.time()
        try:
            exec(compile('\n'.join(lines), f'{os.path.basename(GUIDE)}: {h} [{k}]', 'exec'), ns)
            ok += 1
            print(f'[PASS] {h} [{k}] ({time.time() - t1:.0f} s): {first[:110]}', flush=True)
        except Exception as e:                                   # noqa: BLE001 - recorded, the next example runs
            traceback.print_exc()
            print(f'[FAIL] {h} [{k}]: {first[:110]}: {type(e).__name__}: {e}', flush=True)
    print(f'[test_guide] {ok} / {len(want)} examples run in {time.time() - t0:.0f} s', flush=True)
    os._exit(0 if ok == len(want) else 1)


main()
