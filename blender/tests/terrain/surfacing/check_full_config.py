"""The material's check 0 (SURFACING_DESIGN.md 5.4, package 2): the full configuration, measured cold, before anything
is built on it: the two-slot reader, hex tiling in the planar and the sector reads, the footprint fades with widened
windows, the ramps and their image, on the canyon's and the alpine palette, beside today's material in one process.

    bash run_blender.sh blender/tests/terrain/surfacing/check_full_config.py [--cases canyon,alpine_valley]
        [--smoke] [--reps 3] [--recompile] [--tag t1]
    (a GPU job: queue it with EIDO_GPU_WRAP on a shared machine, blender/tests/_where.py)

Per case, one scene (the judge's eye view: canyon brink_down, alpine_valley floor_lischmaad), make_sky light, 960 x 540
at 16 samples (--smoke: 240 x 135, 1 sample, to see it compile). Today's material (salted: a source the GPU driver
has not compiled before), then the per-texel material (its own fresh source), then the far material alone on the
whole terrain. Per material: its first frame (the cold compile, its images' first upload and a render; wall seconds
and this process's CPU seconds, which a busy machine stretches less), then --reps timed frames (the best counts),
then grey clay the same way (a discarded frame, then --reps timed ones), so each material's cost is against clay
frames rendered right after it. Every timed frame follows a frame of the same material: a material switch
recompiles. --recompile: each material once more with another salt, its images already on the GPU, so that first
frame is the compile alone; the ratio of the two materials' is the one to hold against the budget (1.5 x, section 7).

Records per material the Python build seconds, nodes (groups expanded), images, samplers, the first frame, the best
timed frame and its cost over clay. Writes out/surfacing/material/full_config[_<tag>].json and the last timed frames.
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
    return dict(cases=opt('--cases', 'canyon,alpine_valley').split(','), smoke='--smoke' in a, tag=opt('--tag', ''),
                reps=int(opt('--reps', '3')), recompile='--recompile' in a)


def group_of(mat):
    return next(n.node_tree for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeGroup')


def first_frame(sc):
    """(wall seconds, CPU seconds of this process) of one render: a material's first."""
    w0, c0 = time.time(), time.process_time()
    bpy.ops.render.render(write_still=False)
    return round(time.time() - w0, 1), round(time.process_time() - c0, 1)


def best(sc, reps, path=None):
    """The best of `reps` renders (the last one written to path)."""
    ts = [MS.frame(sc, path if k == reps - 1 else None) for k in range(reps)]
    return round(min(ts), 2)


def clay_frames(sc, me, clay, reps):
    slots = list(me.materials)
    me.materials.clear()
    me.materials.append(clay)
    MS.frame(sc)
    t = best(sc, reps)
    me.materials.clear()
    for m in slots:
        me.materials.append(m)
    return t


def main():
    a = args()
    out = {}
    tag = f"_{a['tag']}" if a['tag'] else ''
    os.makedirs(MS.OUT, exist_ok=True)
    rec_path = os.path.join(MS.OUT, f'full_config{tag}.json')
    k0 = int(time.time()) % 40 + 1
    reps = 1 if a['smoke'] else a['reps']
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
        r['clay_s'] = best(sc, reps)
        MS.log(f'[check0] {case}: clay {r["clay_s"]} s')
        mats = {}
        for label, data in (('today', None), ('per_texel', sd)):
            t0 = time.time()
            mat = MS.apply(t, obj, data, cameras=[cam])
            build = time.time() - t0
            MS.salt(mat, k0 if data is None else k0 + 50)
            mats[label] = mat
            ng = group_of(mat)
            nimg, nsamp = S._count_samplers(ng)
            first, first_cpu = first_frame(sc)
            frame_s = best(sc, reps, os.path.join(MS.OUT, f'full_config_{case}_{label}{tag}.png'))
            slots = len(me.materials)
            clay_s = clay_frames(sc, me, clay, reps)
            r[label] = dict(build_s=round(build, 1), nodes=S._nodes_in(ng), images=nimg, samplers=nsamp,
                            first_frame_s=first, first_frame_cpu_s=first_cpu, frame_s=frame_s, clay_s=clay_s,
                            material_s=round(frame_s - clay_s, 2), slots=slots, far_m=mat.get('eido_far_m'))
            MS.log(f'[check0] {case}/{label}: {r[label]}')
        # the far material alone on the whole terrain: its compile
        pal, strata = MS.palette_args(t)
        t0 = time.time()
        fm = S.far_material(pal, recipe=t.recipe, strata=strata, data=sd, constants=S.terrain_constants(obj),
                            name=f'{case}_far_only', log=MS.log)
        build = time.time() - t0
        MS.salt(fm, k0 + 100)
        me.materials.clear()
        me.materials.append(fm)
        me.polygons.foreach_set('material_index', [0] * len(me.polygons))
        first, first_cpu = first_frame(sc)
        frame_s = best(sc, reps, os.path.join(MS.OUT, f'full_config_{case}_far{tag}.png'))
        ng = group_of(fm)
        r['far'] = dict(build_s=round(build, 1), nodes=S._nodes_in(ng), samplers=S._count_samplers(ng)[1],
                        first_frame_s=first, first_frame_cpu_s=first_cpu, frame_s=frame_s)
        MS.log(f'[check0] {case}: far {r["far"]}')
        if a['recompile']:
            # each material again under another salt: its images are on the GPU, so the first frame is the compile
            for label in ('today', 'per_texel', 'today', 'per_texel'):
                mat = mats[label]
                MS.salt(mat, 3)
                me.materials.clear()
                me.materials.append(mat)
                first, first_cpu = first_frame(sc)
                r[label].setdefault('recompile_s', []).append(first)
                r[label].setdefault('recompile_cpu_s', []).append(first_cpu)
                MS.log(f'[check0] {case}/{label}: recompile {first} s (CPU {first_cpu} s)')
            lo = {k: min(r[k]['recompile_s']) for k in ('today', 'per_texel')}
            r['compile_ratio'] = round(lo['per_texel'] / max(lo['today'], 1e-6), 2)
            MS.log(f"[check0] {case}: compile alone, per-texel over today's: {r['compile_ratio']} "
                   f"({lo['per_texel']} s / {lo['today']} s)")
        me.materials.clear()
        me.materials.append(clay)
        MS.frame(sc)
        r['clay_after_s'] = best(sc, reps)
        r['total_s'] = round(time.time() - t_all, 1)
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
