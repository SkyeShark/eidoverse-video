"""The material's check 0 (SURFACING_DESIGN.md 5.4, package 2): the full configuration, measured cold, before anything
is built on it: the two-slot reader, hex tiling in the planar and the sector reads, the footprint fades with widened
windows, the ramps and their image, on the canyon's and the alpine palette, beside today's material in one process.

    bash run_blender.sh blender/tests/terrain/surfacing/check_full_config.py [--cases canyon,alpine_valley]
        [--smoke] [--tag t1]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

Per case, one scene (the judge's eye view: canyon brink_down, alpine_valley floor_lischmaad), make_sky light, 960 x 540
at 16 samples (--smoke: 240 x 135, 1 sample, to see it compile): grey clay (a warm-up frame, then a timed one), then
today's material (salted: a source the GPU driver has not compiled before), its first frame (the cold compile and a
render) and a timed one, then the per-texel material (its own fresh source) the same way, then the far material alone
on the whole terrain. Every timed frame follows a frame of the same material: a material switch recompiles. Records
per material the Python build seconds, nodes (groups expanded), images, samplers, the first frame, the timed frame and
its cost over clay. Writes out/surfacing/material/full_config[_<tag>].json and the timed frames' images.
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

VIEW = {'canyon': 'brink_down', 'alpine_valley': 'floor_lischmaad', 'toroweap': 'brink_down',
        'lauterbrunnen': 'floor_lischmaad'}


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    return dict(cases=opt('--cases', 'canyon,alpine_valley').split(','), smoke='--smoke' in a, tag=opt('--tag', ''))


def group_of(mat):
    return next(n.node_tree for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')


def main():
    a = args()
    out = {}
    tag = f"_{a['tag']}" if a['tag'] else ''
    os.makedirs(MS.OUT, exist_ok=True)
    rec_path = os.path.join(MS.OUT, f'full_config{tag}.json')
    k0 = int(time.time()) % 40 + 1
    for case in a['cases']:
        r = {}
        t_all = time.time()
        sc = MS.scene(samples=1 if a['smoke'] else 16, res=(240, 135) if a['smoke'] else (MS.W, MS.H))
        t0 = time.time()
        t, obj = MS.terrain(case)
        r['terrain_s'] = round(time.time() - t0, 1)
        t0 = time.time()
        sd = MS.surface(t)
        r['bake_s'] = round(time.time() - t0, 1)
        r['bake_info'] = {k: sd.info.get(k) for k in ('cache_hit', 'seconds', 'load_seconds', 'palette_bake')}
        cam = MS.camera(sc, t, case, VIEW[case])
        sky_dir = os.path.join(MS.OUT, '_sky', case)
        MS.light(sc, cam, sky_dir)
        me = obj.data
        clay = me.materials[0]
        MS.frame(sc)
        r['clay_s'] = round(MS.frame(sc), 2)
        MS.log(f'[check0] {case}: clay {r["clay_s"]} s')
        for label, data in (('today', None), ('per_texel', sd)):
            t0 = time.time()
            mat = MS.apply(t, obj, data, cameras=[cam])
            build = time.time() - t0
            MS.salt(mat, k0 if data is None else k0 + 50)
            ng = group_of(mat)
            nimg, nsamp = S._count_samplers(ng)
            first = MS.frame(sc)
            second = MS.frame(sc, os.path.join(MS.OUT, f'full_config_{case}_{label}{tag}.png'))
            r[label] = dict(build_s=round(build, 1), nodes=S._nodes_in(ng), images=nimg, samplers=nsamp,
                            first_frame_s=round(first, 1), frame_s=round(second, 2),
                            material_s=round(second - r['clay_s'], 2), slots=len(me.materials),
                            far_m=mat.get('eido_far_m'))
            MS.log(f'[check0] {case}/{label}: {r[label]}')
        # the far material alone on the whole terrain: its compile
        t0 = time.time()
        fm = S.far_material(*MS.palette_args(t)[:1], recipe=t.recipe, strata=MS.palette_args(t)[1], data=sd,
                            constants=S.terrain_constants(obj), name=f'{case}_far_only', log=MS.log)
        build = time.time() - t0
        MS.salt(fm, k0 + 100)
        me.materials.clear()
        me.materials.append(fm)
        me.polygons.foreach_set('material_index', [0] * len(me.polygons))
        first = MS.frame(sc)
        second = MS.frame(sc, os.path.join(MS.OUT, f'full_config_{case}_far{tag}.png'))
        ng = group_of(fm)
        r['far'] = dict(build_s=round(build, 1), nodes=S._nodes_in(ng), samplers=S._count_samplers(ng)[1],
                        first_frame_s=round(first, 1), frame_s=round(second, 2))
        me.materials.clear()
        me.materials.append(clay)
        MS.frame(sc)
        r['clay_after_s'] = round(MS.frame(sc), 2)
        r['total_s'] = round(time.time() - t_all, 1)
        MS.log(f'[check0] {case}: far {r["far"]}, clay after {r["clay_after_s"]} s')
        out[case] = r
        MS.clean(sky_dir)
        with open(rec_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=1, default=str)
    MS.log(f'[check0] done -> {rec_path}')


try:
    main()
except Exception:                                           # noqa: BLE001
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    os._exit(1)
sys.stdout.flush()
os._exit(0)
