"""The masks package's fixtures (PORT_PLAN.md 8.2 row P7, 5.1): every case made by the Blender edition's own masks.py
in Blender's own Python (3.13, numpy 2.3.4: plan C6), for tests/masks/masks_test.mjs.

    <Blender's python> -I eidoverse/terrain/tests/masks/masks_expected.py [--only synthetic,refs,hero,floor] [--out <dir>]

The cases are the Blender masks package's own (blender/tests/terrain/masks/test_masks.py and its fixtures.py, used as
they are): the synthetic fields with known answers, the five sheet references stacked as the Blender tests stack them
(the context DEM, then the main tile pinned to it, with the drainage areas, lakes and sand of fixtures.reference_stack),
the design-shaped Lauterbrunnen stack with hero levels at 2 m and 0.5 m (fixtures.hero_stack), and every base save of
the chaos floor's runs (tests/parity/blender_chaos_floor.py: Blender's Terrain.save, masks included).

Inputs are rounded to float32 first (the level runner's fields are float32 in both editions; the DEM fixtures hold
float64), so masks.py and the port see the same numbers. Every case is made twice: masks.py as it is, and the same
code with its gaussian_blur's FFT in float64 (numpy 2.3.4 transforms float32 data in single precision, and that
round-off alone moves the smoothstepped curvature masks by up to 3e-3 of their range; the port's blur is a direct
convolution, PORT_PLAN.md 3.4). The second set is stored only where it differs.

Outputs (git-ignored), tests/out/masks/fixtures/ by default:
  manifest.json   the cases (levels, params, names, norms, skipped, the march shifts masks.py took), the versions and
                  the Blender key (tests/parity/_blender.py source_key)
  <case>.npz      L<i>__in__<field> (float32), L<i>__out__<mask> (masks.py, float32), L<i>__f64__<mask> (the float64
                  FFT, where it differs); a function case's arrays are in__<name> / out__<name> / f64__<name>
  floor.json      per floor base save: the mask parameters its run used, whether masks.py recomputed from the save's
                  fields gives the save's masks bit for bit, and per level and mask the float32 FFT's spread
                  (max |as is - float64 FFT|)
Runs numpy only; nothing is written into the Blender edition (no bytecode either).
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402

sys.dont_write_bytecode = True
ROOT = B.bare_terrain_package()
MASK_TESTS = os.path.join(ROOT, 'blender', 'tests', 'terrain', 'masks')
sys.path.insert(0, MASK_TESTS)

import numpy as np  # noqa: E402

F = None            # the Blender masks tests' fixtures module (imported in main, after the cache check)
M = None            # its masks module (masks.py, loaded by fixtures.py)
F32 = np.float32
OUT_DEFAULT = os.path.join(HERE, '..', 'out', 'masks', 'fixtures')
SCALES_200 = ['curv_profile_200m', 'curv_plan_200m', 'convex_200m', 'concave_200m']


# ------------------------------------------------------------------------------------------- the two blurs ---

def blur64(a, sigma_cells):
    """masks.py gaussian_blur with the transform in float64: the same float32 input, the same padding, the same
    transfer function, the result rounded to float32 once."""
    a = np.asarray(a, F32).astype(np.float64)
    if sigma_cells <= 0.0:
        return a.astype(F32)
    ny, nx = a.shape
    py, px = M._good_size(ny), M._good_size(nx)
    if (py, px) != (ny, nx):
        a = np.pad(a, ((0, py - ny), (0, px - nx)), mode='edge')
    fy = np.fft.fftfreq(py)[:, None]
    fx = np.fft.rfftfreq(px)[None, :]
    g = np.exp(-2.0 * (math.pi * sigma_cells) ** 2 * (fx * fx + fy * fy))
    out = np.fft.irfft2(np.fft.rfft2(a) * g, s=(py, px))
    return np.asarray(out[:ny, :nx], F32)


class Variant:
    """with Variant(True): masks.py's gaussian_blur is blur64 inside the block."""

    def __init__(self, f64):
        self.f64 = f64

    def __enter__(self):
        self.orig = M.gaussian_blur
        if self.f64:
            M.gaussian_blur = blur64
        return self

    def __exit__(self, *exc):
        M.gaussian_blur = self.orig


# --------------------------------------------------------------------------------------- the march shifts ---

MARCHES = []


def recording_march(orig):
    """_march as it is, recording each call's shifts: the loop of masks.py _march that picks them, repeated here
    only to list them (the port's masks.js marchShifts is checked against these lists)."""
    def wrapped(hp, m, ny, nx, cell, dists, directions, observer=None):
        tol = math.pi / directions + 1e-9
        shifts = []
        for k in range(directions):
            a = 2.0 * math.pi * k / directions
            ca, sa = math.cos(a), math.sin(a)
            seen = set()
            for d in dists:
                di, dj = int(round(ca * d / cell)), int(round(sa * d / cell))
                if (di, dj) in seen or (di == 0 and dj == 0) or max(abs(di), abs(dj)) > m:
                    continue
                if abs((math.atan2(dj, di) - a + math.pi) % (2.0 * math.pi) - math.pi) > tol:
                    continue
                seen.add((di, dj))
                shifts.append([k, di, dj])
        MARCHES.append(dict(m=int(m), cell=float(cell), directions=int(directions), dists=[float(d) for d in dists],
                            shifts=shifts))
        return orig(hp, m, ny, nx, cell, dists, directions, observer)
    return wrapped


# -------------------------------------------------------------------------------------------------- storing ---

class Case:
    def __init__(self, name, kind):
        self.name, self.kind = name, kind
        self.arrays = {}
        self.meta = dict(name=name, kind=kind)

    def put(self, key, a, dtype=F32):
        a = np.ascontiguousarray(np.asarray(a, dtype))
        self.arrays[key] = a
        return key

    def save(self, out_dir):
        path = os.path.join(out_dir, f'{self.name}.npz')
        np.savez_compressed(path, **self.arrays)
        self.meta['file'] = os.path.basename(path)
        self.meta['arrays'] = {k: dict(shape=list(v.shape), dtype=str(v.dtype)) for k, v in self.arrays.items()}
        self.meta['bytes'] = os.path.getsize(path)
        return self.meta


def level_dict(lv, shape):
    return dict(x0=float(lv['x0']), y0=float(lv['y0']), cell=float(lv['cell']), role=lv.get('role'),
                ny=int(shape[0]), nx=int(shape[1]))


def masks_meta(m):
    return dict(cell=m.cell, x0=m.x0, y0=m.y0, shape=list(m.shape), skipped=dict(m.skipped),
                norms=B.jsonable(m.norms.__dict__) if m.norms is not None else None, names=list(m.keys()))


def f32_inputs(fields):
    """A level's fields as float32 (what the port is given) and the same numbers as float64 (what masks.py is
    given, as the Blender tests give it float64 arrays)."""
    f32 = {k: np.asarray(v, F32) for k, v in fields.items()}
    return f32, {k: v.astype(np.float64) for k, v in f32.items()}


def store_stack(case, fl32, lv, outs, outs64, first=0):
    """Inputs, masks.py's masks and the float64 FFT's where they differ, per level (from level `first`)."""
    spread = {}
    for i in range(first, len(outs)):
        for k, v in fl32[i].items():
            case.put(f'L{i}__in__{k}', v)
        sp = {}
        for nm, v in outs[i].items():
            case.put(f'L{i}__out__{nm}', v)
            w = outs64[i][nm]
            d = float(np.abs(np.asarray(v, np.float64) - np.asarray(w, np.float64)).max())
            sp[nm] = d
            if d > 0:
                case.put(f'L{i}__f64__{nm}', w)
        spread[f'L{i}'] = sp
    case.meta['fft_spread'] = spread
    case.meta['levels'] = [level_dict(l, fl32[i]['h'].shape) for i, l in enumerate(lv)]
    case.meta['masks'] = [masks_meta(m) for m in outs]


# ---------------------------------------------------------------------------------------- synthetic cases ---

def _grid(n, cell):
    c = (np.arange(n) + 0.5 - n / 2) * cell
    return np.meshgrid(c, c)


def synthetic(out_dir):
    metas = []
    # curvatures of a dome and a tilted ridge (test_curvature_curvatures_exact), pad_level then curvatures
    n, cell, a = 96, 2.0, 0.004
    X, Y = _grid(n, cell)
    for name, h in (('curv_dome', -a * (X ** 2 + Y ** 2)), ('curv_ridge', -a * X ** 2 + 0.3 * Y)):
        c = Case(name, 'curvatures')
        h32 = np.asarray(h, F32)
        hp = M.pad_level(h32.astype(np.float64), 1, cell)
        kp, kt = M.curvatures(hp, cell)
        c.put('in__h', h32)
        c.put('out__hp', hp)
        c.put('out__prof', kp)
        c.put('out__plan', kt)
        c.meta.update(cell=cell, m=1)
        metas.append(c.save(out_dir))
    # the V-valley's bend at two scales, and the scale pick (test_curvature_curvatures_exact, _picks_its_scale)
    computes = []
    for sigma in (20.0, 200.0):
        cellv = sigma / 10.0
        Xv, Yv = _grid(400, cellv)
        h = np.tan(math.radians(30.0)) * np.abs(Xv) + 0.01 * Yv
        s = M.scale_suffix(sigma)
        computes.append((f'v_valley_{int(sigma)}', {'h': h}, cellv, dict(names=[f'curv_plan_{s}', f'curv_profile_{s}'])))
    X, Y = _grid(800, 4.0)
    h = 150.0 * np.cos(2 * math.pi * X / 1600.0) + 12.0 * np.cos(2 * math.pi * (X + 0.6 * Y) / 160.0) + 0.05 * Y
    computes.append(('scale_pick', {'h': h}, 4.0, dict(names=['concave_20m', 'convex_20m', 'concave_200m', 'convex_200m'])))
    # wetness rises with the area at a fixed slope (test_wetness_sane): given norms
    X, Y = _grid(64, 10.0)
    A = np.broadcast_to(np.logspace(2, 7, 64)[None, :], (64, 64)).copy()
    computes.append(('wetness_mono', {'h': 0.2 * Y, 'A': A}, 10.0,
                     dict(names=['wetness'], norms=M.Norms(cell_m=10.0, h_lo=0.0, h_hi=1.0, flow_lo=1.0, flow_hi=6.0,
                                                           twi_lo=3.0, twi_hi=12.0))))
    # a periodic tile and its roll (test_periodic_tile)
    i = np.arange(128)
    I, J = np.meshgrid(i, i)
    hper = (30 * np.sin(2 * math.pi * I / 128) * np.cos(4 * math.pi * J / 128) + 12 * np.sin(2 * math.pi * (3 * I + 2 * J) / 128)
            + 5 * np.cos(2 * math.pi * 7 * J / 128))
    pnames = ['slope', 'northness', 'convex_20m', 'concave', 'peaks', 'occlusion', 'rock', 'rock_toe']
    Pp = M.MaskParams(wrap=(True, True), occlusion_radius_m=200.0)
    computes.append(('periodic', {'h': hper}, 6.0, dict(names=pnames, params=Pp)))
    # the api's fields (test_api): every default mask on a bare height (absent inputs skipped), and strata
    X, Y = _grid(48, 4.0)
    happ = 0.3 * X + 5 * np.sin(Y / 30.0)
    computes.append(('api_defaults', {'h': happ}, 4.0, dict()))
    computes.append(('api_strata', {'h': happ}, 4.0, dict(x0=100.0, y0=-50.0, names=['slope', 'strata'],
                                                          params=M.MaskParams(strata=dict(dip_deg=1.0, azimuth_deg=90.0)))))
    for name, fields, cellc, kw in computes:
        c = Case(name, 'compute')
        f32, f64 = f32_inputs(fields)
        outs = {}
        for variant in (False, True):
            with Variant(variant):
                MARCHES.clear()
                outs[variant] = M.compute(f64, cellc, **kw)
                marches = list(MARCHES)
        if name == 'periodic':                     # the roll by whole boxes of the widest decimation
            roll = (32, 64)
            fr = {'h': np.roll(f64['h'], roll, axis=(0, 1))}
            c.meta['roll'] = list(roll)
            rolled = {}
            for variant in (False, True):
                with Variant(variant):
                    rolled[variant] = M.compute(fr, cellc, names=pnames, params=Pp, norms=outs[False].norms)
        for k, v in f32.items():
            c.put(f'L0__in__{k}', v)
        sp = {}
        for nm, v in outs[False].items():
            c.put(f'L0__out__{nm}', v)
            d = float(np.abs(v.astype(np.float64) - outs[True][nm].astype(np.float64)).max())
            sp[nm] = d
            if d > 0:
                c.put(f'L0__f64__{nm}', outs[True][nm])
            if name == 'periodic':
                c.put(f'R0__out__{nm}', rolled[False][nm])
                if np.any(rolled[False][nm] != rolled[True][nm]):
                    c.put(f'R0__f64__{nm}', rolled[True][nm])
        params = kw.get('params') or M.MaskParams()
        c.meta.update(levels=[dict(x0=float(kw.get('x0', 0.0)), y0=float(kw.get('y0', 0.0)), cell=cellc, role='main',
                                   ny=f32['h'].shape[0], nx=f32['h'].shape[1])],
                      params=params.to_dict(), names=kw.get('names'), norms_given=B.jsonable(kw['norms'].__dict__) if 'norms' in kw else None,
                      masks=[masks_meta(outs[False])], fft_spread={'L0': sp}, marches=marches)
        metas.append(c.save(out_dir))
    # the sky view of a plane, a V-valley and a tilted plane (test_occlusion_sane)
    X, Y = _grid(200, 5.0)
    for name, h, radius in (('sky_flat', np.zeros((200, 200)), 300.0),
                            ('sky_v', np.tan(math.radians(30.0)) * np.abs(X), 2000.0),
                            ('sky_plane', 0.2 * X + 0.1 * Y, 400.0)):
        c = Case(name, 'sky_view')
        h32 = np.asarray(h, F32)
        MARCHES.clear()
        o = M.sky_view(h32.astype(np.float64), 5.0, radius)
        c.put('in__h', h32)
        c.put('out__sky', o)
        c.meta.update(cell=5.0, radius=radius, marches=list(MARCHES))
        metas.append(c.save(out_dir))
    return metas


# --------------------------------------------------------------------------------------------- the api ---

def api_record():
    """masks.py's tables and small functions, for JSON-equal checks: the mask table, the default names, the parameter
    defaults, describe_masks(), and the helpers on a spread of arguments (errors as their messages)."""
    def err(fn, *a):
        try:
            return dict(value=B.jsonable(fn(*a)))
        except Exception as e:                                         # noqa: BLE001 - the message is the record
            return dict(error=type(e).__name__, message=str(e))
    return dict(
        MASKS={k: list(v) for k, v in M.MASKS.items()}, DEFAULT_NAMES=list(M.DEFAULT_NAMES), SCALED=list(M.SCALED),
        PASS_THROUGH=list(M.PASS_THROUGH), params=M.MaskParams().to_dict(), describe=M.describe_masks(),
        channel_area={repr(c): M.channel_area_for_cell(c) for c in (0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 7.6, 8.0, 15.625,
                                                                     31.25, 100.0)},
        scale_suffix={repr(s): M.scale_suffix(s) for s in (20.0, 2.5, 200.0, 0.5, 1000.0, 16.0, 31.25, 1e6, 0.001, 62.5)},
        parse_name={n: err(M.parse_name, n) for n in ('slope', 'convex', 'convex_20m', 'concave_200m', 'convex_2p5m',
                                                      'curv_plan_16m', 'slop', 'convex_20', 'vegetaton', 'rock_toe',
                                                      'curv_profile_0p5m', 'peak')},
        good_size={str(n): M._good_size(n) for n in (1, 7, 11, 13, 97, 127, 512, 541, 1000, 1037, 2049, 2071)},
        decimation=[[s, n, w, M._decimation(s, n, w)] for s in (1.0, 6.0, 6.0001, 8.9999, 9.0, 12.5, 40.0, 300.0, 1000.0)
                    for n in (128, 1000, 1024) for w in (False, True)],
        smoothstep=[[e0, e1, x, float(M.smoothstep(e0, e1, x))] for e0, e1 in ((0.0, 0.3), (34.0, 46.0), (1.0, 3.0),
                                                                                 (0.03, 0.3), (46.0, 34.0))
                    for x in (-1.0, 0.0, 0.1, 0.15, 0.3, 2.0, 35.0, 40.0, 45.9, 46.0, 50.0)],
        attribute_name=M.attribute_name('slope'))


# ------------------------------------------------------------------------------------ scale independence ---

SCALE_FREE = ['slope', 'northness', 'eastness', 'height_norm', 'curv_profile_20m', 'curv_plan_20m', 'convex_20m',
              'concave_20m', 'convex_200m', 'concave_200m', 'peaks', 'flow', 'channels', 'wetness', 'occlusion',
              'rock', 'rock_toe', 'snow', 'vegetation']
SCALE_CROPS = {'lauterbrunnen': (420, 440, 180), 'grand_canyon_toroweap': (560, 560, 180),
               'badlands_sd': (500, 450, 180), 'great_sand_dunes': (500, 500, 180), 'mount_fuji': (500, 500, 180)}


def scale_cases(out_dir):
    """test_scale_independence's fields (masks/test_masks.py, as it makes them): a 360-cell crop of each reference,
    its 2 x Catmull-Rom upsampling (test_masks.upsample2: masks.py _catmull_rom), the drainage area of each
    (fixtures.drainage_area), sand where the reference is a dune field; the norms and both mask sets masks.py makes."""
    import test_masks as TM                                          # the Blender masks tests, for upsample2 as it is
    metas = []
    for name, (ci, cj, half) in SCALE_CROPS.items():
        t0 = time.time()
        h_full, lv, meta = F.reference_level(name)
        h = np.asarray(h_full[cj - half:cj + half, ci - half:ci + half], F32).astype(np.float64)
        c = lv.cell
        hf = np.asarray(TM.upsample2(h), F32).astype(np.float64)
        P = F.params_for(name, channel_area_m2=2.0e4)
        A, _ = F.drainage_area(h, c)
        Af, _ = F.drainage_area(hf, c / 2)
        A, Af = np.asarray(A, F32).astype(np.float64), np.asarray(Af, F32).astype(np.float64)
        base, fine = {'h': h, 'A': A}, {'h': hf, 'A': Af}
        if name in F.SAND_TILES:
            base['sand'] = np.full(h.shape, F.SAND_TILES[name])
            fine['sand'] = np.full(hf.shape, F.SAND_TILES[name])
        norms = M.norms_from(base, c, P)
        names = SCALE_FREE if c <= 10.0 else [n for n in SCALE_FREE if '20m' not in n]
        cs = Case(f'scale_{name}', 'scale')
        for lvl, f in (('C', base), ('F', fine)):
            for k, v in f.items():
                cs.put(f'{lvl}__in__{k}', v)
        outs = {}
        for variant in (False, True):
            with Variant(variant):
                outs[variant] = (M.compute(base, c, names=names, norms=norms, params=P, strict=False),
                                 M.compute(fine, c / 2, names=names, norms=norms, params=P, strict=False))
        spread = {}
        for lvl, i in (('C', 0), ('F', 1)):
            sp = {}
            for nm, v in outs[False][i].items():
                cs.put(f'{lvl}__out__{nm}', v)
                w = outs[True][i][nm]
                sp[nm] = float(np.abs(v.astype(np.float64) - w.astype(np.float64)).max())
                if sp[nm] > 0:
                    cs.put(f'{lvl}__f64__{nm}', w)
            spread[lvl] = sp
        cs.meta.update(reference=name, cell=c, names=names, params=P.to_dict(), norms=B.jsonable(norms.__dict__),
                       fft_spread=spread, sand=F.SAND_TILES.get(name), crop=[ci, cj, half])
        metas.append(cs.save(out_dir))
        print(f'[masks fixtures] scale {name}: {time.time() - t0:.1f} s', flush=True)
    return metas


# -------------------------------------------------------------------------------------------- references ---

def reference_cases(out_dir, names_only=None):
    metas = []
    for name in F.SHEET_REFS:
        if names_only and name not in names_only:
            continue
        t0 = time.time()
        fl, lv, meta = F.reference_stack(name, log=lambda m: None)
        fl32, fl64 = zip(*[f32_inputs(f) for f in fl])
        P = F.params_for(name)
        names = list(M.DEFAULT_NAMES) + SCALES_200
        outs = {}
        for variant in (False, True):
            with Variant(variant):
                MARCHES.clear()
                outs[variant] = M.compute_stack(list(fl64), lv, names=names, params=P, strict=False)
                marches = list(MARCHES)
        c = Case(f'ref_{name}', 'stack')
        store_stack(c, fl32, lv, outs[False], outs[True])
        c.meta.update(params=P.to_dict(), names=names, strict=False, marches=marches, reference=name,
                      shape_stats=meta.get('shape_stats'))
        metas.append(c.save(out_dir))
        print(f'[masks fixtures] {name}: {len(outs[False])} levels in {time.time() - t0:.1f} s, '
              f'{metas[-1]["bytes"] / 1e6:.0f} MB', flush=True)
    return metas


def hero_case(out_dir):
    t0 = time.time()
    fields, levels, meta = F.hero_stack('lauterbrunnen', log=lambda m: None)
    fl32, fl64 = zip(*[f32_inputs(f) for f in fields])
    P = F.params_for('lauterbrunnen')
    outs = {}
    for variant in (False, True):
        with Variant(variant):
            MARCHES.clear()
            outs[variant] = M.compute_stack(list(fl64), levels, params=P)
            marches = list(MARCHES)
    c = Case('hero_lauterbrunnen', 'stack')
    # levels 0 and 1 are the reference case's (the same fields and parameters): stored once there, inputs here too
    store_stack(c, fl32, levels, outs[False], outs[True], first=0)
    c.meta.update(params=P.to_dict(), names=None, marches=marches, reference='lauterbrunnen')
    m = c.save(out_dir)
    print(f'[masks fixtures] hero stack: {len(outs[False])} levels in {time.time() - t0:.1f} s, {m["bytes"] / 1e6:.0f} MB',
          flush=True)
    return [m]


# ------------------------------------------------------------------------------------- the floor's saves ---

def _mask_params_of(info):
    """The MaskParams a run's generate() built (api.py generate): the recipe's defaults, its defaults_for(knobs),
    then sea_level and base_elevation_m from the run's info."""
    from eidoblend.terrain import recipes as RG
    R = RG.resolve(info['recipe']) if isinstance(info.get('recipe'), dict) else RG.get(info['recipe_name'])
    dfl = dict(R.defaults)
    if getattr(R, 'defaults_for', None) is not None:
        dfl.update(R.defaults_for(info['knobs']))
    mp = dict(dfl.get('mask_params') or {})
    mp['sea_level'] = info.get('sea_level')
    mp['base_elevation_m'] = info.get('base_elevation_m')
    return mp


def floor_cases(out_dir, folder=''):
    """folder: the parity outputs' folder of the floor runs (default: the current Blender key's, else the newest
    blender_* folder that holds runs)."""
    key = B.source_key()
    base = B.parity_root()
    root = os.path.join(base, folder or key['folder'])
    if not folder and not os.path.isdir(root):
        found = sorted((p for p in os.listdir(base) if p.startswith('blender_') and os.path.isdir(os.path.join(base, p))),
                       key=lambda p: os.path.getmtime(os.path.join(base, p)), reverse=True)
        root = os.path.join(base, found[0]) if found else root
    runs = []
    if not os.path.isdir(root):
        print(f'[masks fixtures] no floor runs under {root}: run tests/parity/floor_runs.sh first', flush=True)
        return runs
    for d in sorted(os.listdir(root)):
        save = os.path.join(root, d, 'base', 'terrain.npz')
        if not d.endswith('_draft') or not os.path.isfile(save):
            continue
        t0 = time.time()
        with open(os.path.join(root, d, 'base', 'terrain.json'), encoding='utf-8') as f:
            info = json.load(f)
        z = np.load(save)
        plan = info['plan']
        fields = [{} for _ in plan]
        saved = [{} for _ in plan]
        for k in z.files:
            lv, kind, nm = k.split('__', 2)
            i = int(lv[1:])
            (fields if kind == 'f' else saved)[i][nm] = z[k]
        entry = dict(run=d, save=os.path.relpath(save, root).replace('\\', '/'), recipe=info['recipe_name'], seed=info['seed'])
        try:
            mp = _mask_params_of(info)
            P = M.MaskParams(**mp)
            levels = [dict(x0=p['x0'], y0=p['y0'], cell=p['cell'], role=p['role']) for p in plan]
            f64 = [{k: np.asarray(v, np.float64) for k, v in f.items()} for f in fields]
            outs = {}
            for variant in (False, True):
                with Variant(variant):
                    outs[variant] = M.compute_stack(f64, levels, params=P)
            equal, spread = {}, {}
            for i, m in enumerate(outs[False]):
                eq, sp = {}, {}
                for nm, v in m.items():
                    s = saved[i].get(nm)
                    eq[nm] = bool(s is not None and np.array_equal(np.asarray(v, s.dtype).view(np.uint8),
                                                                   np.ascontiguousarray(s).view(np.uint8)))
                    sp[nm] = float(np.abs(v.astype(np.float64) - outs[True][i][nm].astype(np.float64)).max())
                missing = sorted(set(saved[i]) - set(m))
                if missing:
                    eq['<not recomputed>'] = missing
                equal[f'L{i}'] = eq
                spread[f'L{i}'] = sp
            entry.update(mask_params=B.jsonable(P.to_dict()), recompute_equal=equal, fft_spread=spread,
                         all_equal=all(v is True for lv in equal.values() for k, v in lv.items() if k != '<not recomputed>'),
                         seconds=round(time.time() - t0, 1))
        except Exception as e:                                         # noqa: BLE001 - recorded, the others still run
            entry['error'] = f'{type(e).__name__}: {e}'
        runs.append(entry)
        print(f"[masks fixtures] floor {d}: {'ERROR ' + entry['error'] if 'error' in entry else ('equal' if entry['all_equal'] else 'DIFFERS')}"
              f" ({entry.get('seconds', '?')} s)", flush=True)
    B.write_json(os.path.join(out_dir, 'floor.json'), dict(source='tests/masks/masks_expected.py', key=key,
                                                           folder=os.path.basename(root), versions=B.versions(), runs=runs))
    return runs


def main():
    global F, M
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--only', default='')
    ap.add_argument('--refs', default='', help='reference names (default: the five sheet references)')
    ap.add_argument('--out', default=OUT_DEFAULT)
    ap.add_argument('--floor-folder', default='', help="the parity outputs' folder of the floor runs (blender_<commit>_<hash>)")
    a = ap.parse_args()
    only = set(x for x in a.only.split(',') if x)
    out_dir = os.path.abspath(a.out)
    os.makedirs(out_dir, exist_ok=True)
    cache = os.path.join(ROOT, 'blender', 'tests', 'terrain', 'out', 'masks', 'cache')
    need = [os.path.join(cache, f'{n}_A_lakes.npz') for n in
            ('lauterbrunnen', 'grand_canyon_toroweap', 'mount_fuji', 'badlands_sd', 'great_sand_dunes')]
    need.append(os.path.join(cache, 'lauterbrunnen_hero_stack.npz'))
    if (not only or only & {'refs', 'hero'}) and not all(os.path.isfile(p) for p in need):
        sys.exit('masks fixtures: the Blender masks tests\' drainage-area cache is missing (blender/tests/terrain/out/'
                 'masks/cache/): run python blender/tests/terrain/masks/test_masks.py in the Blender edition once; this '
                 'tool reads it and never writes there')
    import fixtures as _F                                             # the Blender masks tests' fixtures, as they are
    F, M = _F, _F.M
    M._march = recording_march(M._march)
    t0 = time.time()
    man_path = os.path.join(out_dir, 'manifest.json')
    old = B.read_json(man_path, {}) or {}
    cases = {c['name']: c for c in old.get('cases', [])}
    api = old.get('api')
    if not only or 'api' in only or 'synthetic' in only:
        api = api_record()
    if not only or 'scale' in only:
        for c in scale_cases(out_dir):
            cases[c['name']] = c
    if not only or 'synthetic' in only:
        for c in synthetic(out_dir):
            cases[c['name']] = c
    if not only or 'refs' in only:
        for c in reference_cases(out_dir, set(x for x in a.refs.split(',') if x) or None):
            cases[c['name']] = c
    if not only or 'hero' in only:
        for c in hero_case(out_dir):
            cases[c['name']] = c
    if not only or 'floor' in only:
        floor_cases(out_dir, a.floor_folder)
    B.write_json(man_path, dict(source='tests/masks/masks_expected.py: the Blender edition\'s masks.py', key=B.source_key(),
                                versions=B.versions(), api=api, cases=sorted(cases.values(), key=lambda c: c['name'])))
    print(f'[masks fixtures] {len(cases)} cases in {time.time() - t0:.1f} s -> {out_dir}', flush=True)


if __name__ == '__main__':
    main()
