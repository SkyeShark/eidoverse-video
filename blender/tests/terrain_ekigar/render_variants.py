"""Render every option arm (variant_scenes.py) as grey clay with the gallery's camera and light: out/variants/<name>.png
and out/variants/index.json. Generate the caches first on the CPU (python variant_scenes.py); a missing one is
generated here.

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 \\
        bash run_blender.sh <worktree>/blender/tests/terrain_ekigar/render_variants.py [--only op,op]
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
import variant_scenes  # noqa: E402

args = script_args()
only = args[args.index('--only') + 1].split(',') if '--only' in args else None
OUT = os.path.join(HERE, 'out', 'variants')
os.makedirs(OUT, exist_ok=True)

sc = gallery_rig.setup_scene(W=variant_scenes.WORLD, samples=12)
mat = ekigar.preview_material('grey')
index = {}
t_all = time.time()
for name, op, params in variant_scenes.arms(ekigar):
    if only and op not in only:
        continue
    path = variant_scenes.cache_path(OUT, name)
    hf = ekigar.Heightfield.load(path) if os.path.exists(path) else variant_scenes.generate(ekigar, op, params)
    obj = ekigar.build_mesh(hf, name=name, attributes=False)
    obj.data.materials.append(mat)
    sc.render.filepath = os.path.join(OUT, f'{name}.png')
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    st = hf.stats()
    index[name] = {'op': op, 'params': params, 'min': st['min'], 'max': st['max'], 'nonFinite': st['nonFinite'],
                   'warnings': hf.warnings, 'render_s': round(time.time() - t0, 2)}
    me = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(me)
    print(f'[variants] {name}', flush=True)
with open(os.path.join(OUT, 'index.json'), 'w') as f:
    json.dump(index, f, indent=1)
print(f'[variants] {len(index)} scenes in {time.time() - t_all:.0f}s', flush=True)
