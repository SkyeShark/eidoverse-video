"""The volumetric EXAMPLES: every one compiles, is registered as the engine had it, and makes a finite, animated
medium; the make() knobs reach the volume's own uniforms; the explosion ring's post() is folded into its medium.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf_volumes/test_volume_examples.py [-- fit=1]

(GPU evaluation only, no render: light enough to run without queueing for the GPU.)

1. Registry: the eight volume examples with the engine's bounds and step counts (nuclear_blast's from its size).
2. Per example: the grids at three times through the loop are finite, occupied, and change with time; the
   brightest voxel's emission and the densest voxel are printed.
3. make(): the engine's knobs (speed, density, strength, seed, heat, size) set this volume's uniforms only; a second
   instance keeps its own (the engine's E._u were shared); look='lit' makes the fire + smoke examples a medium whose
   smoke scatters (albedo) and whose fire emits.
4. fit=1: the explosion ring's post(sum) folded into the medium (a power on each sample's density, then density
   and emission scales), fitted to the engine's march with post over the loop (tests/sdf/engine_march.py; prints
   RING_POST_FOLD).
5. timing=1: three baked frames of every example at the probe resolutions: seconds and MB of .vdb per frame (a
   bake: a GPU job; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py).
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402
import engine_march as EM  # noqa: E402  (tests/sdf, on sys.path through _vcommon)

import bpy  # noqa: E402

from eidoblend import sdf  # noqa: E402
from eidoblend.sdf import EXAMPLES  # noqa: E402
from eidoblend.sdf import examples_volumes as EV  # noqa: E402

A = V.args()
CACHE = os.path.join(V.OUT, 'cache_examples')

ENGINE = {   # sdf_raymarch_loader.js: bounds, steps
    'explosion_ring': ([-1.2, -0.25, -1.2], [1.2, 1.0, 1.2], 320),
    'flame': ([-0.65, 0.0, -0.65], [0.65, 1.45, 0.65], 56),
    'smoke': ([-0.95, 0.0, -0.95], [0.95, 2.6, 0.95], 80),
    'gyroid_fireball': ([-0.75, -0.75, -0.75], [0.75, 0.75, 0.75], 56),
    'bonfire': ([-0.9, 0.0, -0.9], [0.9, 2.8, 0.9], 92),
    'candle_flame': ([-0.16, 0.0, -0.16], [0.16, 0.62, 0.16], 56),
    'fire': ([-1.5, 0.0, -1.5], [1.5, 5.1, 1.5], 130),
    'nuclear_blast': ([-10.43, 0.0, -10.43], [10.43, 19.11, 10.43], 300),
}
# times through each loop (s): the ring loops 4.5 s, the fireball 3 s, the blast 20 s
TIMES = {'explosion_ring': (0.6, 1.8, 3.6), 'gyroid_fireball': (0.3, 1.2, 2.4), 'nuclear_blast': (2.0, 7.0, 14.0)}

V.C.stage(320, 180, 1, floor=False, sun=False)
print('[test] import errors:', sdf.EXAMPLE_IMPORT_ERRORS or 'none', flush=True)
V.check('examples_volumes imported', 'examples_volumes' not in sdf.EXAMPLE_IMPORT_ERRORS,
        sdf.EXAMPLE_IMPORT_ERRORS.get('examples_volumes', '')[-400:])

# ---- 1. registry --------------------------------------------------------------------------------------------------
for name, (lo, hi, steps) in ENGINE.items():
    ex = EXAMPLES.get(name)
    ok = ex is not None and ex.kind == 'volume'
    if ok:
        b = ex['bounds']
        ok = (np.allclose(b['min'], lo, atol=0.01) and np.allclose(b['max'], hi, atol=0.01) and ex['steps'] == steps)
    V.check(f'{name}: registered as the engine had it', ok,
            f"bounds {ex['bounds'] if ex else None}, steps {ex.get('steps') if ex else None}")

# ---- 2. grids over time ---------------------------------------------------------------------------------------------
stats = {}
for name in EV.VOLUME_EXAMPLES:
    cells = 72 if name != 'nuclear_blast' else 96
    try:
        vol = EXAMPLES[name].make(cells=cells, cache_dir=CACHE, build=False)
    except Exception as e:  # noqa: BLE001
        V.check(f'{name}: compiles and makes a volume', False, repr(e)[:600])
        continue
    sums = []
    for t in TIMES.get(name, (0.5, 1.5, 3.0)):
        try:
            g = vol.sample_grids(t)
        except Exception as e:  # noqa: BLE001
            V.check(f'{name}: compiles and makes a volume', False, repr(e)[:1200])
            break
        d, e = g['density'], g['emission']
        sums.append((float(d.sum()), float(e.sum()), float(d.max()), float(e.max()),
                     float((d > 1e-3).mean()), bool(np.isfinite(d).all() and np.isfinite(e).all())))
    if len(sums) < 3:
        continue
    stats[name] = sums
    V.check(f'{name}: finite grids', all(s[5] for s in sums), '')
    V.check(f'{name}: occupied at every time', all(s[4] > 1e-4 for s in sums),
            ', '.join(f't{i}: {s[4] * 100:.2f}% occupied, max density {s[2]:.3g}/m, max emission {s[3]:.3g}'
                      for i, s in enumerate(sums)))
    rel = [abs(sums[i][0] - sums[0][0]) / max(1e-9, sums[0][0]) + abs(sums[i][1] - sums[0][1]) / max(1e-9, sums[0][1])
           for i in (1, 2)]
    V.check(f'{name}: animated (the grids change over time)', min(rel) > 1e-3, f'relative change {rel}')
    vol.program.free()

# ---- 3. make() knobs -----------------------------------------------------------------------------------------------
a = EXAMPLES['bonfire'].make(speed=2.0, density=0.5, cells=32, cache_dir=CACHE, build=False)
b = EXAMPLES['bonfire'].make(cells=32, cache_dir=CACHE, build=False)
V.check('make(speed, density) -> this volume\'s uniforms', a.program.get_uniform('uSpeed') == 2.0
        and a.program.get_uniform('uDensity') == 0.5, str(a.sdf_live_uniforms))
V.check('a second instance keeps its own uniforms', b.program.get_uniform('uSpeed') == 1.0
        and b.program.get_uniform('uDensity') == 1.0, str(b.sdf_live_uniforms))
a.sdf_live_uniforms['density'] = 0.25
V.check('sdf_live_uniforms writes the uniform', a.program.get_uniform('uDensity') == 0.25, str(a.sdf_live_uniforms))
f = EXAMPLES['flame'].make(strength=1.5, cells=32, cache_dir=CACHE, build=False)
g = EXAMPLES['gyroid_fireball'].make(seed=3.0, cells=32, cache_dir=CACHE, build=False)
n = EXAMPLES['nuclear_blast'].make(size=0.3, heat=0.5, cells=32, cache_dir=CACHE, build=False)
V.check('flame strength, fireball seed, blast heat + size', f.program.get_uniform('uStrength') == 1.5
        and g.program.get_uniform('uSeed') == 3.0 and n.program.get_uniform('uHeat') == 0.5
        and n.program.get_uniform('uScale') == 0.3, '')
V.check('nuclear_blast size sets its bounds (the engine make())', np.allclose(n.spec.bounds_max, [7.45 * 0.3,
        13.65 * 0.3, 7.45 * 0.3]), f'{n.spec.bounds_min} .. {n.spec.bounds_max}')
for name in ('bonfire', 'candle_flame', 'fire', 'nuclear_blast'):
    lit = EXAMPLES[name].make(look='lit', cells=48, cache_dir=CACHE, build=False)
    t = TIMES.get(name, (0.5, 1.5, 3.0))[2 if name == 'nuclear_blast' else 1]   # the blast's smoke comes as it cools
    gl = lit.sample_grids(t)
    eng = EXAMPLES[name].make(cells=48, cache_dir=CACHE, build=False).sample_grids(t)
    alb = gl.get('albedo')
    smoke_vox = (gl['density'] > 1e-3) & (alb is not None) & (alb.max(-1) > 1e-3 if alb is not None else False)
    V.check(f'{name} look=lit: smoke scatters, fire emits', alb is not None and smoke_vox.any()
            and gl['emission'].max() > 0, f"{int(smoke_vox.sum())} scattering voxels, max emission "
            f"{gl['emission'].max():.3g}")
    rel = abs(gl['density'].sum() - eng['density'].sum()) / max(1e-9, eng['density'].sum())
    V.check(f'{name} look=lit: the same medium (total density)', rel < 0.02, f'{rel * 100:.3f}% apart')
# the grid boxes make() uses hold all the medium: sampled in the engine's box at 16 times through 12 s (the
# looping examples: their loop), nothing denser than 0.1 % of the peak lies outside the grid box
for name, gb in EV.GRID_BOUNDS.items():
    v = EXAMPLES[name].make(cells=96, cache_dir=CACHE, build=False, fit=False)
    lo3, hi3 = np.array(gb['min']), np.array(gb['max'])
    nx, ny, nz = (int(x) for x in v.dims)
    pb = np.stack(np.meshgrid(*[v.lo[i] + (np.arange(n) + 0.5) * v.voxel for i, n in enumerate((nx, ny, nz))],
                              indexing='ij'), -1)
    p3 = np.stack([pb[..., 0], pb[..., 2], -pb[..., 1]], -1)
    outside = np.any((p3 < lo3) | (p3 > hi3), axis=-1)
    loop = {'explosion_ring': 4.5, 'gyroid_fireball': 3.0}.get(name, 12.0)
    worst = 0.0
    for t in np.linspace(0.05, loop, 16):
        d = v.sample_grids(float(t))['density']
        worst = max(worst, float(d[outside].max(initial=0.0)) / max(1e-9, float(d.max())))
    V.check(f'{name}: the grid box holds all the medium', worst < 1e-3,
            f'densest voxel outside the box: {worst * 100:.4f}% of the peak')
    v.program.free()

# what each knob does to the medium: speed runs the clock (speed 2 at t = the default at 2t, exactly), density
# thins it, seed / strength / heat / size change it
def grids(name, t, **kw):
    v = EXAMPLES[name].make(cells=40, cache_dir=CACHE, build=False, **kw)
    g = v.sample_grids(t)
    v.program.free()
    return g


for name in ('explosion_ring', 'flame', 'smoke', 'gyroid_fireball', 'bonfire', 'candle_flame', 'fire'):
    a, b = grids(name, 0.7, speed=2.0), grids(name, 1.4)
    err = float(np.abs(a['density'] - b['density']).max()) / max(1e-9, float(b['density'].max()))
    V.check(f'{name}: speed=2 at t is the default at 2t', err < 1e-3, f'max relative difference {err:.2e}')
for name in ('smoke', 'gyroid_fireball', 'bonfire', 'candle_flame', 'fire', 'nuclear_blast'):
    t = TIMES.get(name, (0.5, 1.5, 3.0))[1]
    a, b = grids(name, t, density=0.5), grids(name, t)
    V.check(f'{name}: density=0.5 thins the medium', 0.3 < a['density'].sum() / max(1e-9, b['density'].sum()) < 0.75,
            f"total density x {a['density'].sum() / max(1e-9, b['density'].sum()):.3f}")
a, b = grids('gyroid_fireball', 1.2, seed=3.0), grids('gyroid_fireball', 1.2)
V.check('gyroid_fireball: seed changes the fireball', float(np.abs(a['density'] - b['density']).mean()) > 1e-3, '')
a, b = grids('flame', 1.0, strength=1.5), grids('flame', 1.0)
V.check('flame: strength changes the turbulence', float(np.abs(a['density'] - b['density']).mean()) > 1e-3, '')
a, b = grids('nuclear_blast', 7.0, heat=0.4), grids('nuclear_blast', 7.0)
V.check('nuclear_blast: heat=0.4 cools the colour', a['emission'].sum() < 0.8 * b['emission'].sum()
        and np.allclose(a['density'], b['density']), f"emission x {a['emission'].sum() / b['emission'].sum():.3f}")

try:
    EXAMPLES['smoke'].make(look='lit', build=False)
    V.check("look='lit' refused for a one-medium example", False, 'no error')
except ValueError as e:
    V.check("look='lit' refused for a one-medium example", 'sample_as' in str(e), str(e)[:120])

# ---- 5. timing=1: what a bake costs per frame, at the probe resolutions ---------------------------------------------
if A.get('timing', '0') == '1':
    import time
    CELLS = {'explosion_ring': 256, 'flame': 200, 'smoke': 180, 'gyroid_fireball': 192, 'bonfire': 200,
             'candle_flame': 256, 'fire': 220, 'nuclear_blast': 220}
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 3
    for name, cells in CELLS.items():
        vol = EXAMPLES[name].make(cells=cells, cache_dir=os.path.join(CACHE, 'timing'), build=False,
                                  name=f'timing_{name}')
        t0 = time.perf_counter()
        vol.bake(1, 3, time_offset=1.0, log=None)
        dt = (time.perf_counter() - t0) / 3.0
        mb = np.mean([os.path.getsize(os.path.join(vol.cache_dir, f'{vol.stem}_{f:04d}.vdb')) for f in (1, 2, 3)]) / 1e6
        n = int(np.prod(vol.dims))
        print(f'[timing] {name}: {vol.grid_info["dims"]} = {n / 1e6:.1f} M voxels of {vol.voxel * 1000:.1f} mm, '
              f'{dt:.2f} s and {mb:.1f} MB a frame', flush=True)
        V.check(f'{name}: bakes a frame in under 30 s', dt < 30.0, f'{dt:.2f} s')
        vol.program.free()

# ---- 4. the ring's post, folded -------------------------------------------------------------------------------------
if A.get('fit', '0') == '1':
    ring = EXAMPLES['explosion_ring'].make(cells=200, cache_dir=CACHE, build=False)
    cam = V.camera((0.0, -2.3, 1.0), (0.0, 0.0, 0.05), lens=50)
    prog = ring.program
    TIMES_FIT = (0.6, 1.4, 2.2, 3.0, 3.8)

    def march(post, gamma):
        """The engine's march at the fit times: the engine's look (its post, gamma 1) or the folded sample (no
        post)."""
        keep = prog.post
        prog.post = keep if post else None
        out = [EM.march(ring, cam, 240, 135, samples=1, t=t, values={'uFoldGamma': float(gamma)}).reshape(-1, 4)
               for t in TIMES_FIT]
        prog.post = keep
        return np.concatenate(out)

    target = march(True, 1.0)
    best = None
    for gamma in (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0):
        raw = march(False, gamma)
        m = (target[:, 3] > 0.02) | (raw[:, 3] > 0.02)
        a_raw = np.clip(raw[m, 3], 1e-4, 0.999)
        a_post = np.clip(target[m, 3], 0.0, 0.999)
        # the density scale k_d with 1 - (1 - a)^k_d matching post's alpha; then, as an emission-absorption medium
        # of colour c gives c (1 - T), the emission scale k_e with k_e c (1 - T^k_d) / k_d matching post's radiance
        ks = np.linspace(0.3, 4.0, 75)
        errs = [float(np.abs((1.0 - (1.0 - a_raw) ** k) - a_post).mean()) for k in ks]
        k_d = float(ks[int(np.argmin(errs))])
        c = raw[m, :3] / a_raw[:, None]
        pred = c * ((1.0 - (1.0 - a_raw) ** k_d) / k_d)[:, None]
        k_e = float(np.sum(target[m, :3] * pred) / max(1e-12, np.sum(pred * pred)))
        err = float(np.abs(pred * k_e - target[m, :3]).mean() + np.abs((1.0 - (1.0 - a_raw) ** k_d) - a_post).mean())
        print(f'[fit] gamma {gamma:.2f}: density_scale {k_d:.3f}, emission_scale {k_e:.3f}, error {err:.4f} '
              f'over {int(m.sum())} pixels', flush=True)
        if best is None or err < best[0]:
            best = (err, gamma, k_d, k_e)
    err, gamma, k_d, k_e = best
    print(f"[fit] explosion_ring post fold: RING_POST_FOLD = {{'gamma': {gamma}, 'density_scale': {k_d:.3f}, "
          f"'emission_scale': {k_e:.3f}}} (error {err:.4f})", flush=True)
    V.check('explosion ring post fold fitted', np.isfinite(k_d) and np.isfinite(k_e), f'{gamma}, {k_d:.3f}, {k_e:.3f}')
V.summary()
