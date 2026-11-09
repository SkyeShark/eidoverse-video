"""A saved water .blend, opened in a fresh Blender with no eidoblend on the path, plays and renders on its own.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/water3d/test_reopen_saved_blend.py -- blend=<file.blend> frames=60,144 tag=pour \
        [ref=<png path with {f} for the frame>]

The contract is that every bake is keyed or cached data (PLY sequences played by Geometry Nodes, EXR sequences,
drivers), so a saved file renders any frame with no Python of ours. This opens the file (run_blender.sh starts Blender
with --factory-startup, so Python drivers would not run either), checks that nothing of eidoblend is imported, that
every driver is valid, that each Geometry Nodes object plays a different mesh at each frame asked, renders the frames
to out/verify/reopen_<tag>_f####.png, and compares each with the reference render when one is given (mean absolute
difference over the image, 0-255; EEVEE's sampling noise alone stays within a few levels).
"""

import os
import sys

import bpy
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
A = dict(x.split('=', 1) for x in a if '=' in x)
BLEND = A['blend']
FRAMES = [int(x) for x in A.get('frames', '1').split(',')]
TAG = A.get('tag', os.path.splitext(os.path.basename(BLEND))[0])
REF = A.get('ref')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'verify')
os.makedirs(OUT, exist_ok=True)
ok = True


def check(name, cond, detail=''):
    print(('PASS ' if cond else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    return bool(cond)


bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
ok &= check('no eidoblend module is loaded', not any(m.startswith('eidoblend') for m in sys.modules),
            ', '.join(m for m in sys.modules if m.startswith('eidoblend'))[:120])
bad = []
for idb in list(bpy.data.materials) + list(bpy.data.objects) + list(bpy.data.node_groups) + \
        list(bpy.data.worlds) + list(bpy.data.lights) + list(bpy.data.scenes):
    ad = getattr(idb, 'animation_data', None)
    trees = [idb]
    nt = getattr(idb, 'node_tree', None)
    if nt is not None:
        trees.append(nt)
    for t in trees:
        ad = getattr(t, 'animation_data', None)
        if ad is None:
            continue
        for fc in ad.drivers:
            if not fc.driver.is_valid or (fc.driver.type == 'SCRIPTED' and not fc.driver.is_simple_expression):
                bad.append(f'{t.name}:{fc.data_path} ({fc.driver.expression})')
ok &= check('every driver is valid and runs without Python (simple expressions)', not bad, '; '.join(bad[:4]))
missing = []
for img in bpy.data.images:
    if img.source not in ('FILE', 'SEQUENCE') or img.packed_file is not None:
        continue
    p = bpy.path.abspath(img.filepath)               # a sequence names its first frame's file
    if not os.path.exists(p):
        missing.append(f'{img.name} ({p})')
ok &= check('every image the file uses is packed or on disk', not missing, '; '.join(missing[:4]))

gn = [ob for ob in sc.objects if any(m.type == 'NODES' for m in ob.modifiers)]
counts = {}
for f in FRAMES:
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in gn:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        n = len(me.vertices) if me is not None else 0
        co = np.zeros(n * 3)
        if n:
            me.vertices.foreach_get('co', co)
        ev.to_mesh_clear()
        counts.setdefault(ob.name, []).append((n, float(co.sum())))
for name, seq in counts.items():
    nonempty = all(n > 0 for n, _ in seq)
    differs = len(FRAMES) < 2 or len({round(s, 3) for _, s in seq}) == len(seq)
    ok &= check(f'{name} plays a mesh at every frame, a different one each frame', nonempty and differs,
                ', '.join(f'f{f}: {n} verts' for f, (n, _) in zip(FRAMES, seq)))

for f in FRAMES:
    p = os.path.join(OUT, f'reopen_{TAG}_f{f:04d}.png')
    sc.frame_set(f)
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    ok &= check(f'render frame {f}', os.path.exists(p), p)
    if REF and os.path.exists(p):
        rp = REF.replace('{f}', f'{f:04d}')
        if os.path.exists(rp):
            import OpenImageIO as oiio

            def rd(path):
                i = oiio.ImageInput.open(path)
                arr = np.asarray(i.read_image('uint8'))[..., :3].astype(np.float64)
                i.close()
                return arr
            x, y = rd(p), rd(rp)
            d = float(np.abs(x - y).mean()) if x.shape == y.shape else 999.0
            ok &= check(f'frame {f} matches the render made at bake time (mean |diff| < 4 of 255)', d < 4.0,
                        f'{d:.2f} vs {rp}')
print('ALL PASS' if ok else 'SOME FAIL')
