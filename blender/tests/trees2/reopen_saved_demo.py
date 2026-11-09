"""A saved SeedThree scene renders on its own: reopen a .blend in a fresh Blender that
never imports the SeedThree add-on, step to another frame and render it.

    bash run_blender.sh blender/tests/trees2/reopen_saved_demo.py -- <file.blend>:<frame>[+<frame>...] ... [--out <dir>]
    (in a batch: reopen_saved_demo.py:<file.blend>:1+40,<other.blend>:1+48)

Run it before anything imports seedthree (first in a run_batch.py batch, or alone).
Factory startup leaves Python auto-execution off, so only simple-expression drivers
run: the LOD switches, the sun binding and the cast-only twin must all be such. For
each frame it checks that no driver is invalid, reports which LOD levels render and
where the camera is, and writes <out>/reopen_<file>_f<frame>.png.
"""

import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, (': ' + detail) if detail else ''))


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    argv = [a for a in argv if a != '--']
    od = os.path.join(HERE, 'out', 'verify')
    if '--out' in argv:
        i = argv.index('--out')
        od = argv[i + 1]
        del argv[i:i + 2]
    os.makedirs(od, exist_ok=True)
    check('the SeedThree add-on is not loaded', 'seedthree' not in sys.modules)
    for item in argv:
        drive = item[:2] if len(item) > 2 and item[1] == ':' and item[2] in '\\/' else ''
        path, _, frames = item[len(drive):].partition(':')
        path = drive + path
        frames = [int(f) for f in frames.replace(',', '+').split('+') if f] or [1]
        bpy.ops.wm.open_mainfile(filepath=path)
        scene = bpy.context.scene
        name = os.path.splitext(os.path.basename(path))[0]
        scene.render.resolution_percentage = 50
        scene.eevee.taa_render_samples = 8
        drivers = []
        for coll in (bpy.data.objects, bpy.data.node_groups, bpy.data.lights):
            for idb in coll:
                ad = getattr(idb, 'animation_data', None)
                if ad:
                    drivers += [(idb.name, fc) for fc in ad.drivers]
        cam0 = None
        for f in frames:
            scene.frame_set(f)
            bad = [(n, fc.data_path, fc.driver.expression) for n, fc in drivers if not fc.driver.is_valid]
            simple = [(n, fc.data_path) for n, fc in drivers if fc.driver.type == 'SCRIPTED' and not fc.driver.is_simple_expression]
            check('%s f%d: every driver valid (%d drivers)' % (name, f, len(drivers)), not bad, str(bad[:4]))
            check('%s f%d: every scripted driver is a simple expression' % (name, f), not simple, str(simple[:4]))
            shown = sorted({o.get('seedthree_lod') or ('BB' if o.get('seedthree_billboard_card') else '?')
                            for o in scene.objects if o.type == 'MESH' and not o.hide_render
                            and (o.get('seedthree_lod') or o.get('seedthree_billboard_card'))})
            cam = scene.camera.matrix_world.translation.copy()
            print('[reopen] %s f%d: rendering levels %s, camera at %s' % (name, f, shown, tuple(round(c, 2) for c in cam)))
            if cam0 is None:
                cam0 = cam
            p = os.path.join(od, 'reopen_%s_f%03d.png' % (name, f))
            scene.render.filepath = p
            scene.render.image_settings.file_format = 'PNG'
            bpy.ops.render.render(write_still=True)
            check('%s f%d rendered' % (name, f), os.path.isfile(p), p)
    bad = [n for n, ok in RESULTS if not ok]
    print('[reopen_saved_demo] %d/%d PASS%s' % (len(RESULTS) - len(bad), len(RESULTS), ('; FAIL: ' + ', '.join(bad)) if bad else ''))


main()
