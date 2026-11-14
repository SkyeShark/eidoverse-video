"""Where the per-texel material's shader compile goes (SURFACING_DESIGN.md 8.1): the same terrain and view, the
material built several ways, each a fresh source for the GPU driver, its first frame timed with every image already
on the GPU (so the first frame is the compile and one render).

    bash run_blender.sh blender/tests/terrain/surfacing/check_compile.py [--case canyon]
        [--variants today,full,linear,no_hex,no_far] [--res 240x135]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

Variants (options over the palette's, on the material with baked data unless named today):
  today    the material without baked data (mesh attributes), for the ratio
  full     the per-texel material as apply_surface builds it
  linear   interpolation 'Linear': no Cubic near read beside each mipmapped one
  no_hex   detile 'offset': one read per frame, no hex tiling (planar and sector frames)
  no_far   far_scale 1: no far read on the box layers' steep faces
A first, untimed pass renders `full` once so the atlases and scans are uploaded. Each variant is then built, salted
and rendered once (wall seconds and this process's CPU seconds), in the order given, then once more in reverse
order under another salt; the lower of the two counts. Writes out/surfacing/material/compile_<case>.json.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _material_scene as MS  # noqa: E402

import bpy  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

VARIANTS = {'today': None, 'full': {}, 'linear': dict(interpolation='Linear'), 'no_hex': dict(detile='offset'),
            'no_far': dict(far_scale=1.0)}
VIEW = {'canyon': 'brink_down', 'alpine_valley': 'floor_lischmaad', 'toroweap': 'brink_down',
        'lauterbrunnen': 'floor_lischmaad'}


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    w, h = (int(v) for v in opt('--res', '240x135').split('x'))
    return dict(case=opt('--case', 'canyon'), variants=opt('--variants', 'today,full,linear,no_hex,no_far').split(','),
                res=(w, h))


def first_frame():
    w0, c0 = time.time(), time.process_time()
    bpy.ops.render.render(write_still=False)
    return round(time.time() - w0, 1), round(time.process_time() - c0, 1)


def main():
    a = args()
    case = a['case']
    sc = MS.scene(samples=1, res=a['res'])
    t, obj = MS.terrain(case)
    sd = MS.surface(t)
    cam = MS.camera(sc, t, case, VIEW[case])
    sky = os.path.join(MS.OUT, '_sky', case + '_compile')
    MS.light(sc, cam, sky)
    pal, strata = MS.palette_args(t)
    consts = S.terrain_constants(obj)
    me = obj.data

    def build(name, k):
        opts = VARIANTS[name]
        t0 = time.time()
        mat = S.surface_material(pal, recipe=t.recipe, strata=strata, options=dict(opts) if opts else None,
                                 constants=consts, data=None if name == 'today' else sd, name=f'{case}_{name}_{k}',
                                 log=None)
        secs = time.time() - t0
        if name == 'today':
            S.pack_masks(obj, mat)
        MS.salt(mat, k)
        ng = next(n.node_tree for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')
        me.materials.clear()
        me.materials.append(mat)
        return mat, round(secs, 1), S._nodes_in(ng), S._count_samplers(ng)[1]
    k0 = int(time.time()) % 30 + 2
    build('full', k0)                                      # the images' upload, untimed
    first_frame()
    if 'today' in a['variants']:
        build('today', k0)
        first_frame()
    rec = {}
    order = list(a['variants'])
    for rnd, names in enumerate((order, order[::-1])):
        for name in names:
            _mat, bs, nodes, samp = build(name, k0 + 40 + 7 * rnd + order.index(name))
            wall, cpu = first_frame()
            r = rec.setdefault(name, dict(build_s=bs, nodes=nodes, samplers=samp, compile_s=[], compile_cpu_s=[]))
            r['compile_s'].append(wall)
            r['compile_cpu_s'].append(cpu)
            MS.log(f'[compile] {case}/{name}: {wall} s (CPU {cpu} s), {nodes} nodes, {samp} samplers')
    base = min(rec['today']['compile_s']) if 'today' in rec else None
    for name, r in rec.items():
        r['best_s'] = min(r['compile_s'])
        if base:
            r['over_today'] = round(r['best_s'] / base, 2)
    MS.clean(sky)
    path = os.path.join(MS.OUT, f'compile_{case}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, indent=1)
    MS.log(f'[compile] {json.dumps({k: (v["best_s"], v.get("over_today")) for k, v in rec.items()})}')
    MS.log(f'[compile] done -> {path}')


try:
    main()
except Exception:                                           # noqa: BLE001
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)
sys.stdout.flush()
os._exit(0)
