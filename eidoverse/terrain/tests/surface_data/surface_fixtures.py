"""The surface data package's fixtures (PORT_PLAN.md 5.1, 8.2 row P14), made by the Blender edition's own code with
Blender's own Python (3.13, numpy 2.3.4; plan C6), numpy only: no Blender, no GPU.

    <Blender's python> -I eidoverse/terrain/tests/surface_data/surface_fixtures.py [--kernels] [--noise] [--expr]
        [--palettes] [--out <dir>]                                                     (no flag: all four)

The Blender edition is found as tests/parity/_blender.py finds it ($EIDO_BLENDER_EDITION, or blender/ in this
checkout) and is only read. Point $EIDO_BLENDER_EDITION at a checkout (or an exported tree: `git archive <commit>`)
of the commit the port is compared with: the manifests record its surface code hash (surface/bake.code_hash, the
key every Blender surface bake carries) and its palettes code hash, and the commit when it is a git checkout (else
$EIDO_SURFACE_COMMIT, which names an exported tree's commit). Outputs go to <out>/<kind>/ (default
eidoverse/terrain/tests/out/surface_data/fixtures/blender_<commit>/), in tests/parity/fixtures.py's format: a
manifest.json and one little-endian .bin per distinct array.

--kernels   Every surface bake kernel's numpy twin (surface/twins.py) on the Blender package's own kernel cases
            (blender/tests/terrain/surface_data/test_kernels.py cases(): the 96 x 80 terrain-like field with a cliff
            band, a valley, loose cover, sand, snow and catchments from 2 m to 2 km), recorded once each with
            tests/parity/fixtures.py's KernelRecorder (its install_twin_gpu replaces the GPU by the twins), so
            tests/parity/_common.mjs kernelCases() runs them through the port's kernels. The cases are the Blender
            test's, not a copy of them.
--noise     surface/noise.py, the twin of noise.glsl: its uint32 hashes (Jenkins' lookup3 hash2/3/4, the Voronoi
            PCG hashes) on integer grids reaching negative and large values, Perlin noise and the safe noise (the
            1e5 wrap, the 1e6 shift), the Noise Texture's fBM with whole, fractional, zero and clamped detail, and
            the six variants of blender/tests/terrain/surface_data/test_noise.py at its 128 x 96 scattered points;
            and Blender's own renders of those six Noise and Voronoi nodes (out/surface_data/noise_render/*.exr,
            made by that test in Blender), read with OpenImageIO, with the plane's pixel centres.
--expr      blender/tests/terrain/surface_data/test_expr.py's cases: every palette's expressions with every noise at
            its mean, evaluated by palettes.evaluate (float64) on its 4096 random map values per name; then each
            recipe's 'auto' palette (its RECIPE_LOOKS applied) with the expressions no case before it has, labelled
            auto:<recipe>.
--palettes  build/palettes.py as data, for build/palettes.js's JSON-equality test: the module's tables, get() of
            every palette name and of 'auto' for every recipe, check(), material_masks, masks_used, ramp_rows,
            names_in, known_mask over every name, climate_sun cases, column_layers, for_place for every place.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'parity'))
import _blender as B  # noqa: E402
import fixtures as FX  # noqa: E402

import numpy as np  # noqa: E402

F = np.float32


def surface_key(edition):
    """What the fixtures are keyed by: the commit (git, else $EIDO_SURFACE_COMMIT), the surface code hash the Blender
    bake keys by (surface/bake.code_hash()), the palette bake's (PALETTE_CODE) and palettes.py's sha1."""
    import hashlib
    from eidoblend.terrain.surface import bake as SB
    commit = B.git(edition, 'rev-parse', 'HEAD') or os.environ.get('EIDO_SURFACE_COMMIT') or 'unknown'
    pal = os.path.join(edition, 'blender', 'eidoblend', 'terrain', 'build', 'palettes.py')
    with open(pal, 'rb') as f:
        pal_sha = hashlib.sha1(f.read()).hexdigest()
    return dict(commit=commit, surface_code=SB.code_hash(), palette_code=SB.code_hash(SB.PALETTE_CODE),
                palettes_sha1=pal_sha, folder=f'blender_{commit[:7]}')


# ------------------------------------------------------------------------------------------------- kernels ---

def kernel_fixtures(out, key):
    edition = B.blender_edition()
    test = os.path.join(edition, 'blender', 'tests', 'terrain', 'surface_data', 'test_kernels.py')
    store = FX.Store(os.path.join(out, 'kernels'), 'kernels', key)
    rec = FX.KernelRecorder(store)
    G, T, _FL = FX.install_twin_gpu(rec)
    from eidoblend.terrain.surface import twins as TW
    rec.test = 'surface_data/test_kernels.py'
    ns = {'__name__': 'surface_fixture_kernels', '__file__': test}
    t0 = time.perf_counter()
    exec(FX._definitions(test), ns)
    for tag, (inputs, uniforms) in ns['cases']().items():
        name = next(k for k in sorted(TW.KERNELS, key=len, reverse=True) if tag.startswith(k))
        k = G.kernel(source=TW.source(name), name=TW.PREFIX + name)
        T.parity(k, inputs, uniforms, twin=T.get_twin(TW.PREFIX + name), tol=1e-4)
        rec.label(tag)
    kernels = {}
    for c in store.manifest['cases']:
        kernels[c['kernel']] = kernels.get(c['kernel'], 0) + 1
    man = store.finish(sources=[dict(test='surface_data/test_kernels.py', cases=len(store.manifest['cases']),
                                     seconds=round(time.perf_counter() - t0, 2))], kernels=kernels)
    print(f"[surface fixtures] kernels: {len(man['cases'])} cases of {len(kernels)} kernels -> {store.dir}", flush=True)
    return man


# --------------------------------------------------------------------------------------------------- noise ---

NOISE_VARIANTS = [('noise3_d2', 'n3', (1 / 40.0, 2.0, 0.5)), ('noise4_d2', 'n4', (3.7, 1 / 55.0, 2.0, 0.5)),
                  ('fbm3_d5', 'n3', (1 / 90.0, 5.0, 0.6)), ('noise3_d2p5', 'n3', (1 / 25.0, 2.5, 0.55)),
                  ('vor2', 'v2', (1 / 30.0,)), ('vor3', 'v3', (1 / 45.0,))]
# test_noise.py's render plane: 512 m at (3000, -2000, 37.5), 256 x 256 pixels of 2 m
PLANE = dict(x0=3000.0 - 256.0, y0=-2000.0 - 256.0, z=37.5, side=512.0, n=256)


def _twin(BN, kind, args, co):
    if kind == 'n3':
        return BN.noise_node3(co, *args)
    if kind == 'n4':
        w, s, d, r = args
        return BN.noise_node4(co, w, s, d, r)
    if kind == 'v2':
        return BN.voronoi_f1_colour2(co[..., :2], args[0], 1.0)[..., 0]
    return BN.voronoi_f1_colour3(co, args[0], 1.0)[..., 0]


def noise_fixtures(out, key, renders=None):
    from eidoblend.terrain.surface import noise as BN
    rec = FX.FunctionRecorder(FX.Store(os.path.join(out, 'noise'), 'functions/noise', key), 'noise')
    s = rec.store
    U = np.uint32
    # integer lattice coordinates: around 0, negative, beyond 2^31 as int32 bits, the hashes' wrap
    rng = np.random.default_rng(5)
    ints = np.concatenate([np.arange(-40, 40), rng.integers(-2 ** 31, 2 ** 31 - 1, 160),
                           np.array([2 ** 31 - 1, -2 ** 31, 100000, -100000, 1000000, 0xdeadbeef - 2 ** 32])])
    kx, ky = np.meshgrid(ints[:64], ints[64:128])
    kz = (kx * 7 + ky * 13) & 0xFFFFFFFF
    kw = (kx * 3 - ky * 5) & 0xFFFFFFFF
    k32 = lambda a: (np.asarray(a, np.int64) & 0xFFFFFFFF).astype(U)        # noqa: E731
    rec.case('hash2/3/4 of int32 lattice coordinates (as uint32 bits)', 'noise.hash',
             dict(note='kx, ky, kz, kw as uint32 bits of int32 values'),
             dict(kx=k32(kx), ky=k32(ky), kz=k32(kz), kw=k32(kw)),
             dict(h2=BN.hash2(k32(kx), k32(ky)), h3=BN.hash3(k32(kx), k32(ky), k32(kz)),
                  h4=BN.hash4(k32(kx), k32(ky), k32(kz), k32(kw))))
    px, py, pz = (k32(kx), k32(ky), k32(kz))
    p2 = BN.pcg2d_i(px, py)
    p3 = BN.pcg3d_i(px, py, pz)
    rec.case("the Voronoi node's PCG hashes (pcg2d_i, pcg3d_i) on int32 bits", 'noise.pcg',
             {}, dict(kx=px, ky=py, kz=pz), dict(pcg2x=p2[0], pcg2y=p2[1], pcg3x=p3[0], pcg3y=p3[1], pcg3z=p3[2]))
    # Perlin noise and the safe noise at points near and far (past the 1e5 wrap and the 1e6 shift)
    pts = np.concatenate([rng.uniform(-50, 50, (2000, 4)), rng.uniform(-3e4, 3e4, (2000, 4)),
                          rng.uniform(-3e5, 3e5, (1000, 4)), rng.uniform(-3e6, 3e6, (1000, 4)),
                          np.stack(np.meshgrid(np.arange(-2.0, 2.01, 0.25), np.arange(-2.0, 2.01, 0.25),
                                               [0.0, 0.5], [1.25]), -1).reshape(-1, 4)]).astype(F)
    x, y, z, w = (pts[:, k] for k in range(4))
    rec.case('perlin3, perlin4, snoise3, snoise4 at points to 3e6 m', 'noise.perlin', {}, dict(p=pts),
             dict(perlin3=BN.perlin3(x, y, z), perlin4=BN.perlin4(x, y, z, w), snoise3=BN.snoise3(x, y, z),
                  snoise4=BN.snoise4(x, y, z, w)))
    co = pts[:, :3]
    outs, args = {}, []
    for tag, d, r in (('d0', 0.0, 0.5), ('d2', 2.0, 0.5), ('d2p5', 2.5, 0.55), ('d5', 5.0, 0.6), ('d16', 16.0, 0.5),
                      ('r0', 3.0, 0.0), ('dneg', -1.0, 0.5), ('d1p25', 1.25, 0.7)):
        outs[f'node3_{tag}'] = BN.noise_node3(co, 1 / 37.0, d, r)
        outs[f'node4_{tag}'] = BN.noise_node4(co, 2.3, 1 / 53.0, d, r)
        args.append(dict(tag=tag, detail=d, roughness=r, scale3=1 / 37.0, scale4=1 / 53.0, w=2.3))
    outs['vor2'] = BN.voronoi_f1_colour2(co[:, :2], 1 / 31.0, 1.0)
    outs['vor2_r05'] = BN.voronoi_f1_colour2(co[:, :2], 1 / 31.0, 0.5)
    outs['vor3'] = BN.voronoi_f1_colour3(co, 1 / 47.0, 1.0)
    outs['vor3_r05'] = BN.voronoi_f1_colour3(co, 1 / 47.0, 0.5)
    rec.case("the Noise Texture's Fac (3D, 4D) and the Voronoi F1 colour", 'noise.nodes',
             dict(nodes=args, voronoi=dict(scale2=1 / 31.0, scale3=1 / 47.0)), dict(co=co), outs)
    # test_noise.py's six variants at its scattered points
    rng3 = np.random.default_rng(3)
    H, W = 96, 128
    cs = np.stack([rng3.uniform(-16000, 16000, (H, W)), rng3.uniform(-16000, 16000, (H, W)),
                   rng3.uniform(-200, 2000, (H, W))], -1).astype(F)
    rec.case("test_noise.py's variants at its 128 x 96 points", 'noise.variants',
             dict(variants=[[n, k, list(a)] for n, k, a in NOISE_VARIANTS]), dict(co=cs),
             {n: _twin(BN, k, a, cs) for n, k, a in NOISE_VARIANTS})
    # Blender's renders of the nodes (test_noise.py render_parity), with the pixel centres
    if renders and os.path.isdir(renders):
        import OpenImageIO as oiio
        N = PLANE['n']
        xs = PLANE['x0'] + (np.arange(N) + 0.5) * (PLANE['side'] / N)
        ys = PLANE['y0'] + (np.arange(N) + 0.5) * (PLANE['side'] / N)
        XX, YY = np.meshgrid(xs, ys)
        plane = np.stack([XX, YY, np.full_like(XX, PLANE['z'])], -1).astype(F)
        imgs, twins_, made = {}, {}, {}
        for n, k, a in NOISE_VARIANTS:
            p = os.path.join(renders, f'{n}.exr')
            if not os.path.exists(p):
                continue
            inp = oiio.ImageInput.open(p)
            img = np.asarray(inp.read_image('float'), np.float32)[::-1]       # files run top to bottom
            inp.close()
            imgs[n] = np.ascontiguousarray(img[..., 0])
            twins_[f'{n}_twin'] = _twin(BN, k, a, plane)
            made[n] = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(p)))
        rec.case("Blender's Noise Texture and Voronoi nodes rendered by test_noise.py (EEVEE, Emission, 2 m pixels)",
                 'noise.render', dict(plane=PLANE, variants=[[n, k, list(a)] for n, k, a in NOISE_VARIANTS],
                                      rendered=made), dict(co=plane), dict(imgs, **twins_))
    man = s.finish()
    print(f"[surface fixtures] noise: {len(man['cases'])} cases -> {s.dir}", flush=True)
    return man


# ---------------------------------------------------------------------------------------------- expressions ---

def expr_fixtures(out, key):
    from eidoblend.terrain.build import palettes as P
    edition = B.blender_edition()
    test = os.path.join(edition, 'blender', 'tests', 'terrain', 'surface_data', 'test_expr.py')
    ns = {'__name__': 'surface_fixture_expr', '__file__': test}
    exec(FX._definitions(test), ns)
    rec = FX.FunctionRecorder(FX.Store(os.path.join(out, 'expr'), 'functions/expr', key), 'expr')
    rng = np.random.default_rng(11)

    def record(label, pal, exprs, **args):
        names = set()
        for _k, e in exprs:
            names |= P.names_in(e)
        names = sorted(names)
        maps = ns['sample_maps'](names, rng)
        outs = {}
        for k, (_label, e) in enumerate(exprs):
            outs[f'e{k:03d}'] = np.broadcast_to(np.asarray(P.evaluate(e, maps, constants=pal.get('constants'), flat=True),
                                                           np.float64), (ns['NPTS'],)).copy()
        rec.case(label, 'palettes.evaluate', dict(args, constants=B.jsonable(pal.get('constants')),
                                                  exprs=[[lb, e] for lb, e in exprs], tol=ns['TOL']),
                 {f'm_{nm}': np.asarray(maps[nm], np.float64) for nm in names}, outs)

    seen = set()
    for name in P.names():
        pal = P.get(name)
        exprs = ns['expressions'](pal)
        seen |= {e for _k, e in exprs}
        record(name, pal, exprs, palette=name)
    # the recipes' 'auto' palettes (RECIPE_LOOKS over their palettes, as make_terrain resolves them), each with the
    # expressions no case before it has: test_expr.py takes the base palettes only, and the looks' own terms (the
    # crater's ejecta and grassland, the meanders' benches) reach the port's material and far colour as well. Drawn
    # after the base palettes, so those cases' maps stay what they were
    looks = 0
    for r in REGISTRY:
        try:
            pal = P.get('auto', r)
        except Exception:                                    # noqa: BLE001 - a recipe without an 'auto' palette
            continue
        exprs = [(lb, e) for lb, e in ns['expressions'](pal) if e not in seen]
        seen |= {e for _k, e in exprs}
        if exprs:
            record(f'auto:{r}', pal, exprs, palette='auto', recipe=r)
            looks += 1
    man = rec.store.finish()
    print(f"[surface fixtures] expr: {len(man['cases'])} cases ({len(man['cases']) - looks} palettes, {looks} recipes' "
          f"'auto' palettes) -> {rec.store.dir}", flush=True)
    return man


# ------------------------------------------------------------------------------------------------ palettes ---

def maps_fixtures(out, key):
    """surface/maps.py as data: every MapSpec (dataclasses.asdict), FAMILIES, PAIRS, SHADER, describe(), spec() of
    scaled names, decode_rule of every map at two cell sets, encode and decode of sample values."""
    import dataclasses
    from eidoblend.terrain.surface import maps as MP
    d = dict(MAPS={k: dataclasses.asdict(v) for k, v in MP.MAPS.items()}, order=list(MP.MAPS),
             FAMILIES=B.jsonable(MP.FAMILIES), PAIRS=B.jsonable(MP.PAIRS), SHADER=list(MP.SHADER),
             describe=MP.describe())
    d['spec'] = {}
    for nm in ('convex_200m', 'curv_plan_50m', 'concave_2p5m', 'curv_profile_20m', 'settle'):
        d['spec'][nm] = dataclasses.asdict(MP.spec(nm))
    d['spec_errors'] = {}
    for nm in ('setle', 'n2O', 'nothing_like_it'):
        try:
            MP.spec(nm)
        except KeyError as e:
            d['spec_errors'][nm] = str(e).strip('"\'')
    d['known'] = {nm: MP.known(nm) for nm in ('n20', 'normal', 'convex_200m', 'settle', 'slope', 'nope', 'detail_g')}
    cells = [32.0, 8.0, 2.0, 0.5]
    refs = [501.2, 500.0, 499.5, 0.0]
    d['decode_rule'] = {}
    vals = np.array([-3.0, -1.0, -0.37, 0.0, 1e-3, 0.25, 0.5, 0.9999, 1.0, 1.7, 20.0, 70.0, 300.0], F)
    d['encode'] = {}
    for nm, s in MP.MAPS.items():
        try:
            d['decode_rule'][nm] = B.jsonable(MP.decode_rule(s, cells, refs))
        except ValueError as e:
            d['decode_rule'][nm] = dict(error=str(e))
        if s.encoding in ('unit', 'signed', 'bend', 'thick', 'float'):
            for cell in (1.0, 8.0):
                enc = MP.encode(s, vals, cell)
                d['encode'][f'{nm}@{cell}'] = dict(encoded=[float(x) for x in enc],
                                                   decoded=[float(x) for x in MP.decode(s, enc, cell)])
    d['values'] = [float(x) for x in vals]
    path = os.path.join(out, 'maps')
    os.makedirs(path, exist_ok=True)
    B.write_json(os.path.join(path, 'maps.json'), dict(key=key, versions=B.versions(), data=d))
    print(f"[surface fixtures] maps: {len(MP.MAPS)} maps -> {path}", flush=True)


REGISTRY = ('alpine_valley', 'badlands', 'caldera', 'canyon', 'cinder_cones', 'dunes', 'fluvial_range', 'impact_crater',
            'incised_meanders', 'meadow', 'mesas_buttes', 'real_place', 'rolling_hills', 'sea_cliffs', 'stratovolcano',
            'tower_karst')


def palette_fixtures(out, key):
    from eidoblend.terrain.build import palettes as P
    d = {}
    for nm in ('DEFAULT_OPTIONS', 'LANDSCAPE_MACRO', 'LANDSCAPE', 'MAX_LAYERS', 'PROJECTIONS', 'STRATA_DEFAULTS',
               'CONSTANTS', '_FILLED_CONSTANTS', 'STRATA_COLUMNS', 'FORMATION_LOOKS', 'LAYER_COLOURS', 'PALETTES',
               'PALETTE_LOOKS', 'RECIPE_PALETTES', 'RECIPE_LOOKS', 'PLACES', 'DERIVED', 'SURFACE_MAPS'):
        if hasattr(P, nm):
            d[nm] = B.jsonable(getattr(P, nm))
    d['_FUNCS'] = {k: list(v) for k, v in P._FUNCS.items()}
    d['names'] = P.names()
    # the registry's sixteen recipes (PORT_PLAN.md 3.2) and every recipe the looks name
    recipe_names = sorted(set(REGISTRY) | set(P.RECIPE_LOOKS) | set(P.RECIPE_PALETTES))
    d['recipes'] = recipe_names
    got = {}
    for nm in P.names():
        pal = P.get(nm)
        got[nm] = dict(pal=B.jsonable(pal), material_masks=sorted(P.material_masks(pal)),
                       masks_used=sorted(P.masks_used(pal)), ramp_rows=_ramp_rows(P, pal))
    for r in recipe_names:
        try:
            pal = P.get('auto', r)
            got[f'auto:{r}'] = dict(pal=B.jsonable(pal), material_masks=sorted(P.material_masks(pal)),
                                    masks_used=sorted(P.masks_used(pal)), ramp_rows=_ramp_rows(P, pal),
                                    resolve_name=P.resolve_name('auto', r))
        except Exception as e:                                       # noqa: BLE001 - recorded
            got[f'auto:{r}'] = dict(error=f'{type(e).__name__}: {e}')
    d['get'] = got
    places = {}
    for dem in sorted(P.PLACES):
        try:
            pal, place = P.for_place(dem)
            places[dem] = dict(pal=B.jsonable(pal), place=B.jsonable(place))
        except Exception as e:                                       # noqa: BLE001
            places[dem] = dict(error=f'{type(e).__name__}: {e}')
    d['for_place'] = places
    sample = sorted(set(list(P.DERIVED) + list(P.SURFACE_MAPS) + ['slope', 'convex_20m', 'concave_150m', 'curv_plan',
                                                                     'nope', 'snowpacks', 'n20', 'slope_20m',
                                                                     'canopy_far', 'height', 'altitude']))
    d['known_mask'] = {nm: bool(P.known_mask(nm)) for nm in sample}
    exprs = ['smoothstep(30, 45, slope + 5*(fbm(80, 3) - 0.5))', 'max(a, b, c)', '-x', 'pow(slope, 2) / 3',
             'clamp(1.1*canopy_expected + 0.05, 0, 1) * smoothstep(0.02, 0.08, canopy_expected)', 'bare', 'cover',
             'altitude + 220*northness', 'cells(70, 5, 2.5)', 'mix(1, 2, 0.5)', '1 - 2 - 3', '2 * -3', 'abs(-x)']
    d['parse'] = {}
    for e in exprs:
        try:
            d['parse'][e] = dict(tree=B.jsonable(P.parse(e)), names=sorted(P.names_in(e)))
        except Exception as e2:                                      # noqa: BLE001
            d['parse'][e] = dict(error=f'{type(e2).__name__}: {e2}')
    d['climate_sun'] = [[c, list(P.climate_sun(c))] for c in (None, {}, {'latitude_deg': 36.2},
                                                              {'latitude_deg': -33.9}, {'latitude_deg': 91},
                                                              {'sun_azimuth_deg': 400, 'latitude_deg': 10},
                                                              {'sun_elevation_deg': 12.5})]
    d['column_layers'] = {}
    for nm in sorted(P.STRATA_COLUMNS):
        for looks in (False, True):
            d['column_layers'][f'{nm}:{looks}'] = dict(layers=B.jsonable(P.column_layers(nm, looks=looks)),
                                                        repeats=bool(P.column_repeats(nm)))
    d['hex_linear'] = {h: [float(v) for v in P.hex_linear(h)] for h in ('#000000', '#ffffff', '#5f7a33', '#e2ded3',
                                                                         '#0b0c0d', '7f4f3f')}
    path = os.path.join(out, 'palettes')
    os.makedirs(path, exist_ok=True)
    rec = dict(key=key, versions=B.versions(), date=time.strftime('%Y-%m-%d %H:%M:%S'), data=d)
    B.write_json(os.path.join(path, 'palettes.json'), rec)
    print(f"[surface fixtures] palettes: {len(P.names())} palettes, {len(recipe_names)} recipes -> {path}", flush=True)
    return rec


def _ramp_rows(P, pal):
    rows, index = P.ramp_rows(pal)
    return dict(rows=np.asarray(rows, np.float64).round(9).tolist(), index=B.jsonable(index))


def main():
    a = B.script_args()
    flags = {x for x in a if x.startswith('--')}
    every = not (flags & {'--kernels', '--noise', '--expr', '--palettes', '--maps'})
    edition = B.bare_terrain_package()
    key = surface_key(edition)
    out = a[a.index('--out') + 1] if '--out' in a else os.path.join(B.TERRAIN, 'tests', 'out', 'surface_data',
                                                                     'fixtures', key['folder'])
    renders = a[a.index('--renders') + 1] if '--renders' in a else os.path.join(
        edition, 'blender', 'tests', 'terrain', 'out', 'surface_data', 'noise_render')
    os.makedirs(out, exist_ok=True)
    v = B.versions()
    print(f"[surface fixtures] Blender edition {key['commit'][:7]} (surface code {key['surface_code'][:10]}), Python "
          f"{v['python']}, numpy {v['numpy']} -> {out}", flush=True)
    if v['numpy'] != '2.3.4':
        print(f"[surface fixtures] WARNING: numpy {v['numpy']} is not Blender 5.2's 2.3.4: run this with Blender's own "
              "Python (plan C6)", flush=True)
    B.write_json(os.path.join(out, 'key.json'), dict(key, versions=v))
    if every or '--maps' in flags:
        maps_fixtures(out, key)
    if every or '--kernels' in flags:
        kernel_fixtures(out, key)
    if every or '--noise' in flags:
        noise_fixtures(out, key, renders)
    if every or '--expr' in flags:
        expr_fixtures(out, key)
    if every or '--palettes' in flags:
        palette_fixtures(out, key)
    return 0


if __name__ == '__main__':
    sys.exit(main())

_ = (json, math, subprocess)
