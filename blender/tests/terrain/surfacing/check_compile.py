"""Where the per-texel material's shader compile goes (SURFACING_DESIGN.md 8.1): the same terrain and view, the
material built several ways, each a fresh source for the GPU driver, its first frame timed with every image already
on the GPU (so the first frame is the compile and one render).

    bash run_blender.sh blender/tests/terrain/surfacing/check_compile.py [--case canyon]
        [--variants today,full,linear,no_hex,no_far,steep_one] [--rounds 2] [--res 240x135]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

Variants (options over the palette's, on the material with baked data unless named today):
  today      the material without baked data (mesh attributes), for the ratio
  full       the per-texel material as apply_surface builds it
  near_hex   near_hex True: every hex read of a planar frame 'Auto' (Cubic near beside mipmapped Linear), the
             configuration before design 8.1's first lever (one Cubic near read at the plain coordinate)
  linear     interpolation 'Linear': no Cubic near read beside each mipmapped one
  no_hex     detile 'offset': one read per frame, no hex tiling (planar and sector frames)
  no_far     far_scale 1: no far read on the box layers' steep faces
  steep_all  steep_hex_share 0: every box layer hex-tiled in its sector frames (by default only the cliff-sized
             tiles are, the rest read each sector frame once)
  steep_one  steep_hex_m 0: the sector frames read once each, hex tiling on the planar reads only
  steep_hex  steep_hex_m 20: the sector frames hex-tiled on a 20 m lattice (three reads each)
A first, untimed pass renders `full` once so the atlases and scans are uploaded. Each variant is then built, salted
(its own salt every time: the GPU driver caches a source it has compiled) and rendered once (wall seconds and this
process's CPU seconds), in the order given; with --rounds 2 once more in reverse order; the lowest counts. A name
may be given twice (today,full,...,full,today brackets a single round against the machine's drift). Records per
variant the Python build seconds, the nodes the shader is compiled from (groups expanded, every instance), the
samplers and the compile seconds. Writes out/surfacing/material/compile_<case>.json.
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

# name: None (today's material) or the material options over the palette's
VARIANTS = {'today': None, 'full': {}, 'near_hex': dict(near_hex=True), 'linear': dict(interpolation='Linear'),
            'no_hex': dict(detile='offset'), 'no_far': dict(far_scale=1.0), 'steep_one': dict(steep_hex_m=0.0),
            'steep_all': dict(steep_hex_share=0.0), 'steep_hex': dict(steep_hex_m=20.0)}
VIEW = {'canyon': 'brink_down', 'alpine_valley': 'floor_lischmaad', 'toroweap': 'brink_down',
        'lauterbrunnen': 'floor_lischmaad'}


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    w, h = (int(v) for v in opt('--res', '240x135').split('x'))
    return dict(case=opt('--case', 'canyon'), rounds=int(opt('--rounds', '2')), res=(w, h),
                variants=opt('--variants', 'today,full,linear,no_hex,no_far,steep_one').split(','))


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
    salts = iter(range(int(time.time()) % 30 + 2, 10 ** 6))

    def build(name):
        k = next(salts)
        opts = VARIANTS[name]
        t0 = time.time()
        mat = S.surface_material(pal, recipe=t.recipe, strata=strata, options=dict(opts) if opts else None,
                                 constants=consts, data=None if opts is None else sd, name=f'{case}_{name}_{k}',
                                 log=None)
        secs = time.time() - t0
        if opts is None:
            S.pack_masks(obj, mat)
        MS.salt(mat, k)
        ng = next(n.node_tree for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')
        me.materials.clear()
        me.materials.append(mat)
        return round(secs, 1), S._nodes_in(ng), S._count_samplers(ng)[1]
    build('full')                                          # the images' upload, untimed
    first_frame()
    if 'today' in a['variants']:
        build('today')
        first_frame()
    rec = {}
    order = list(a['variants'])
    for names in [order, order[::-1]][:max(1, a['rounds'])]:
        for name in names:
            bs, nodes, samp = build(name)
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
    MS.log(f'[compile] {json.dumps({k: (v["best_s"], v.get("over_today"), v["nodes"]) for k, v in rec.items()})}')
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
