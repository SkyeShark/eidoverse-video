"""Render Ekigar's operator gallery in Blender EEVEE: every operator and landform on the fixture Ekigar's own visual
suite judges it on, with that suite's camera and light (gallery_rig.py), as grey clay and as Ekigar's shaded
preview. Writes out/gallery/<mode>/<NN>_<op>.png and out/gallery/index.json (field stats per scene).

Generate the fields first on the CPU (python gallery_scenes.py: out/gallery/cache/); a scene whose cache is missing is
generated here.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \\
        bash run_blender.sh <worktree>/blender/tests/terrain_ekigar/render_gallery.py [--only op,op] [--modes grey,shaded]
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from eidoblend.common import script_args  # noqa: E402
from eidoblend.terrain import ekigar  # noqa: E402
import gallery_rig  # noqa: E402
import gallery_scenes  # noqa: E402

args = script_args()
only = None
modes = ['grey', 'shaded']
samples = 16
out_root = os.path.join(HERE, 'out', 'gallery')
i = 0
while i < len(args):
    if args[i] == '--only':
        only = args[i + 1].split(',')
        i += 1
    elif args[i] == '--modes':
        modes = args[i + 1].split(',')
        i += 1
    elif args[i] == '--samples':
        samples = int(args[i + 1])
        i += 1
    elif args[i] == '--out':
        out_root = args[i + 1]
        i += 1
    i += 1

sc = gallery_rig.setup_scene(W=gallery_scenes.WORLD, samples=samples)
mats = {m: ekigar.preview_material(m) for m in modes}
for m in modes:
    os.makedirs(os.path.join(out_root, m), exist_ok=True)
index = {}
t_all = time.time()
for name, graph, target, fixture in gallery_scenes.scenes(ekigar):
    op = name.split('_', 1)[1]
    if only and op not in only:
        continue
    t0 = time.time()
    path = gallery_scenes.cache_path(os.path.join(HERE, 'out', 'gallery'), name)
    hf = ekigar.Heightfield.load(path) if os.path.exists(path) else gallery_scenes.generate(ekigar, graph, target,
                                                                                             fixture)
    t_gen = time.time() - t0
    obj = ekigar.build_mesh(hf, name=op)
    st = hf.stats()
    index[name] = {'fixture': fixture, 'min': st['min'], 'max': st['max'], 'flatFraction': st['flatFraction'],
                   'nonFinite': st['nonFinite'], 'warnings': hf.warnings, 'outputs': sorted(hf.outs),
                   'load_or_generate_s': round(t_gen, 2)}
    for m in modes:
        obj.data.materials.clear()
        obj.data.materials.append(mats[m])
        sc.render.filepath = os.path.join(out_root, m, f'{name}.png')
        bpy.ops.render.render(write_still=True)
    me = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(me)
    print(f'[gallery] {name:32s} {fixture:14s} h {st["min"]:.3f}..{st["max"]:.3f} total {time.time() - t0:.1f}s',
          flush=True)
with open(os.path.join(out_root, 'index.json'), 'w') as f:
    json.dump(index, f, indent=1)
print(f'[gallery] {len(index)} scenes in {time.time() - t_all:.0f}s', flush=True)
