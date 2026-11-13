"""Package 6's unit tests: palettes, the mask expression language, packed scans, the material, the strata image and
the rock scatter. No rendering (no GPU slot needed):

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/terrain/surfacing/test_surfacing.py [-k name]

Each test prints PASS / FAIL with its numbers; the run exits 1 on any failure.
"""
import math
import sys
import time
import traceback
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
BLENDER_DIR = HERE.parents[2]
sys.path.insert(0, str(BLENDER_DIR))
from eidoblend.terrain import masks as M  # noqa: E402
from eidoblend.terrain.build import dressing as D  # noqa: E402
from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.build import surfacing as S  # noqa: E402

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(f"[test] {'PASS' if ok else 'FAIL'} {name}: {detail}", flush=True)


def test_palettes_valid():
    bad = {}
    for n in P.names():
        pal = P.get(n)
        probs = P.check(pal)
        if probs:
            bad[n] = probs
        if len(pal['layers']) > P.MAX_LAYERS:
            bad[n] = ['too many layers']
    check('every palette validates', not bad, f'{len(P.names())} palettes' + (f'; {bad}' if bad else ''))
    unknown = {n: sorted(m for m in P.masks_used(P.get(n)) if P.known_mask(m)) for n in P.names()}
    unknown = {k: v for k, v in unknown.items() if v}
    check('palettes read only masks the masks package makes', not unknown, str(unknown or 'all known'))
    for place in P.PLACES:
        pal, rec = P.for_place(place)
        assert pal['name'] == rec['palette']
    check('every place resolves to a palette', True, f'{len(P.PLACES)} places')
    auto = {r: P.get('auto', recipe=r)['name'] for r in P.RECIPE_PALETTES}
    check("'auto' resolves every recipe", all(auto[r] == P.RECIPE_PALETTES[r] for r in auto), str(auto))
    try:
        P.get('alpin')
        check('unknown palette names the nearest', False, 'no error')
    except KeyError as e:
        check('unknown palette names the nearest', 'alpine' in str(e), str(e))
    try:
        P.get(dict(layers=[dict(name='x', set='Ground106', tile_m=2, weight='smoothstep(1, 2, slop)')]))
        check('a misspelt mask names the nearest', False, 'no error')
    except ValueError as e:
        check('a misspelt mask names the nearest', 'slope' in str(e), str(e)[:140])


def test_expressions():
    x = np.linspace(-50, 50, 101)
    y = np.zeros_like(x)
    m = dict(slope=np.linspace(0, 90, 101), talus=np.linspace(0, 2, 101))
    v = P.evaluate('smoothstep(30, 40, slope)', m)
    ref = np.clip((m['slope'] - 30) / 10, 0, 1)
    ref = ref * ref * (3 - 2 * ref)
    check('smoothstep matches GLSL', np.allclose(v, ref), f'max err {np.abs(v - ref).max():.2e}')
    v = P.evaluate('smoothstep(40, 30, slope)', m)
    check('a falling smoothstep (e0 > e1)', np.allclose(v, 1 - ref), '')
    v = P.evaluate('max(0.5*talus, 2 - slope/10) - -1', m)
    ref = np.maximum(0.5 * m['talus'], 2 - m['slope'] / 10) + 1
    check('arithmetic, max, unary minus', np.allclose(v, ref), '')
    v = P.evaluate('clamp(slope / 45, 0, 1) * mix(0, 2, 0.25)', m)
    check('clamp and mix', np.allclose(v, np.clip(m['slope'] / 45, 0, 1) * 0.5), '')
    v = P.evaluate('wear + 1', m)
    check('an absent mask reads 0', np.allclose(v, 1.0), '')
    n = P.evaluate('noise(20)', m, x, y)
    n2 = P.value_noise(np.random.default_rng(0).uniform(-1e4, 1e4, 20000), np.random.default_rng(1).uniform(-1e4, 1e4, 20000), 20.0)
    check('noise() is world-space, about 0..1, mean 0.5', 0.0 <= n.min() and n.max() <= 1.0 and abs(n2.mean() - 0.5) < 0.05
          and n2.std() > 0.15, f'mean {n2.mean():.3f} std {n2.std():.3f} range {n2.min():.2f}..{n2.max():.2f}')
    check('names_in finds every mask', P.names_in('smoothstep(1,2,slope)*rock_toe + max(snow, convex_20m)')
          == {'slope', 'rock_toe', 'snow', 'convex_20m'}, '')
    gx, gy = np.meshgrid(np.linspace(0, 3000, 600), np.linspace(0, 3000, 600))
    c = P.evaluate('cells(280, 1)', {}, gx, gy)
    distinct = len(np.unique(np.round(c, 9)))
    jumps = float((np.abs(np.diff(c, axis=1)) > 1e-12).mean())
    check('cells(): one value per Voronoi cell, spread over 0..1', 60 < distinct < 300 and jumps < 0.05
          and c.min() < 0.1 and c.max() > 0.9, f'{distinct} cells over 3 km, boundary steps {jumps:.3f}')
    # 'plants' reads masks every landform carries right, never the masks package's rock or vegetation (rock counts
    # ground eroded more than 20 m as rock: 0.8-0.95 of the gentle ground of an eroded canyon)
    pn = P.names_in('plants')
    ones = {k: np.array([1.0]) for k in pn}
    ones.update(slope=np.array([5.0]), snow=np.array([0.0]), talus=np.array([0.0]), sand=np.array([0.0]),
                height=np.array([500.0]), northness=np.array([0.0]))
    hi = P.evaluate('plants', ones, constants=dict(treeline_m=2000.0))[0]
    lo = P.evaluate('plants', dict(ones, height=np.array([2600.0])), constants=dict(treeline_m=2000.0))[0]
    check("'plants' reads slope, wetness, sky view, cover and the treeline, not rock or vegetation",
          not ({'rock', 'vegetation', 'rock_toe'} & pn) and hi > 0.95 and abs(lo - 0.2 * hi) < 0.02,
          f'masks {sorted(pn)}; below the treeline {hi:.2f}, 600 m above it {lo:.2f}')
    v = P.evaluate('treeline_m + base_elevation_m', {}, constants=dict(treeline_m=1950.0, base_elevation_m=800.0))
    check('terrain constants fold in (and are not masks)', float(v) == 2750.0
          and P.names_in('altitude - snowline_m') == {'height'}, f'{float(v)}')
    f = P.evaluate('fbm(40)', m, np.linspace(0, 4000, 101), np.zeros(101))
    f2 = P.value_noise(np.random.default_rng(2).uniform(-1e4, 1e4, 20000), np.random.default_rng(3).uniform(-1e4, 1e4, 20000),
                       40.0, 101, octaves=5, gain=0.6, stretch=2.2)
    check('fbm() is five octaves of world noise, about 0..1, mean 0.5', 0.0 <= f.min() and f.max() <= 1.0
          and abs(f2.mean() - 0.5) < 0.05 and f2.std() > 0.12, f'mean {f2.mean():.3f} std {f2.std():.3f}')
    t1 = P.parse('smoothstep(30, 40, slope) * plants')
    t2 = P.parse('plants')
    check('equal sub-expressions share one key (the material builds them once)',
          P.tree_key(t1[3]) == P.tree_key(t2) and hash(P.tree_key(t1)) is not None, '')
    for bad in ('slope ** 2', 'foo(slope)', 'smoothstep(1, slope)', 'slope if 1 else 2', 'noise(slope)'):
        try:
            P.parse(bad)
            check(f'rejects {bad!r}', False, 'parsed')
        except P.ExprError as e:
            check(f'rejects {bad!r}', True, str(e)[:80])


def test_packing():
    sets = sorted({L['set'] for n in P.names() for L in P.get(n)['layers']})
    t0 = time.time()
    worst = []
    for s in sets:
        d = S.pack_set(s, log=None)
        ps = S.packed_set(s, log=None)
        a, b = ps['albedo'], ps['nrao']
        for img in (a, b):
            assert tuple(img.size) == tuple(ps['stats']['size']), (s, img.size)
        w, h = a.size
        pa = np.empty(w * h * 4, np.float32)
        a.pixels.foreach_get(pa)
        pa = pa.reshape(-1, 4)
        pb = np.empty(w * h * 4, np.float32)
        b.pixels.foreach_get(pb)
        pb = pb.reshape(-1, 4)
        hmean = float(pa[:, 3].mean())
        nz = 1 - (pb[:, 0] * 2 - 1) ** 2 - (pb[:, 1] * 2 - 1) ** 2
        lin = pa[:, :3] if a.is_float else P.srgb_to_linear(pa[:, :3])
        merr = float(np.abs(lin.mean(0) - np.array(ps['stats']['mean_albedo_linear'])).max())
        worst.append((s, hmean, float((nz < -0.05).mean()), merr))
    bad = [w for w in worst if abs(w[1] - 0.5) > 0.04 or w[2] > 0.02 or w[3] > 0.01]
    check('packed scans: height mean 0.5, normals unit, albedo mean as recorded', not bad,
          f'{len(sets)} sets in {time.time() - t0:.1f} s' + (f'; bad {bad}' if bad else ''))


def _readable(ng):
    """(the attribute names a node group reads, the masks it can read: directly as eido_<mask> or from its packs)."""
    import json as _json
    attrs = {nd.attribute_name for nd in ng.nodes if nd.bl_idname == 'ShaderNodeAttribute'}
    packs = _json.loads(ng.get('eido_mask_packs', '[]') or '[]')
    names = {an for an, _m in packs}
    out = {a[5:] for a in attrs if a.startswith('eido_') and a not in names}
    for an, ms in packs:
        if an in attrs:
            out |= set(ms)
    return attrs, out


def test_materials():
    worst = []
    for n in P.names():
        t0 = time.time()
        mat = S.surface_material(n, log=None, name=f'mat_{n}')
        ng = next(nd.node_tree for nd in mat.node_tree.nodes if nd.bl_idname == 'ShaderNodeGroup')
        imgs = {nd.image.name for nd in ng.nodes if nd.bl_idname == 'ShaderNodeTexImage' and nd.image}
        attrs, readable = _readable(ng)
        used = P.material_masks(P.get(n))
        worst.append((n, len(imgs), len(attrs), len(ng.nodes), round(time.time() - t0, 2)))
        if len(imgs) > S.MAX_IMAGES or not used <= readable | {'strata'} or len(attrs) > S.ATTRS_DIRECT:
            check(f'material {n}', False, f'images {len(imgs)}, attributes {sorted(attrs)}: reads {sorted(readable)} '
                                          f'vs used {sorted(used)}')
            return
        assert ng.name.startswith(S.GROUP_NAME)
    check('every palette builds under the sampler and attribute budgets and reads its masks', True,
          '; '.join(f'{n}: {i} images, {a} attributes, {k} nodes, {t} s' for n, i, a, k, t in worst))
    # EEVEE fails a material that reads 15 mesh attributes ('uses too many attributes', 11-13): every palette and
    # every recipe's 'auto' look (the cinder field's reads 16 masks) compiles with at most ATTRS_DIRECT, packed
    over = {}
    for r in P.RECIPE_PALETTES:
        pal = P.get('auto', recipe=r)
        mat = S.surface_material(pal, log=None, name=f'auto_{r}')
        ng = next(nd.node_tree for nd in mat.node_tree.nodes if nd.bl_idname == 'ShaderNodeGroup')
        attrs, readable = _readable(ng)
        used = P.material_masks(pal)
        if len(attrs) > S.ATTRS_DIRECT or not used <= readable | {'strata'}:
            over[r] = (len(used), len(attrs), sorted(used - readable - {'strata'}))
    check("every recipe's 'auto' material reads all its masks within the attribute budget (packed past "
          f"{S.ATTRS_DIRECT})", not over, str(over or 'all within'))
    clay = S.clay_material()
    b = next(nd for nd in clay.node_tree.nodes if nd.bl_idname == 'ShaderNodeBsdfPrincipled')
    check('palette=None is grey clay 0.18', abs(b.inputs['Base Color'].default_value[0] - 0.18) < 1e-6, '')
    # apply_surface on a mesh, for every palette (farmland reads no mask at all: its eido_masks is an empty array)
    me = bpy.data.meshes.new('t')
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    me.attributes.new('eido_slope', 'FLOAT', 'POINT')
    obj = bpy.data.objects.new('t', me)
    msgs = []
    for n in P.names():
        S.apply_surface(obj, n, log=msgs.append)
    miss = S.missing_masks(obj, 'alpine')
    check('apply_surface assigns every palette and names the masks the mesh lacks',
          len(obj.data.materials) == 1 and 'slope' not in miss and 'talus' in miss and 'convex_20m' in miss,
          f'alpine lacks {miss[:6]}...')
    # the packs apply_surface writes carry the masks' own values (a mask the mesh lacks packs as 0)
    import json as _json
    for nm, vals in (('eido_slope', (12.5, 47.0, 81.0)), ('eido_flow', (0.1, 0.5, 0.9))):
        a = me.attributes.get(nm) or me.attributes.new(nm, 'FLOAT', 'POINT')
        a.data.foreach_set('value', np.array(vals, np.float32))
    mat = S.apply_surface(obj, 'alpine', log=None)
    packs = _json.loads(mat['eido_mask_packs'])
    got = {}
    for an, ms in packs:
        buf = np.zeros(9, np.float32)
        me.attributes[an].data.foreach_get('vector', buf)
        for c, m in enumerate(ms):
            got[m] = buf.reshape(3, 3)[:, c]
    ok = (len(packs) >= 2 and np.allclose(got['slope'], (12.5, 47.0, 81.0)) and np.allclose(got['flow'], (0.1, 0.5, 0.9))
          and np.allclose(got['talus'], 0.0))
    check('apply_surface packs the masks three to an attribute with their own values (absent masks 0)', ok,
          f"{len(packs)} packs {[an for an, _m in packs]}; slope {got.get('slope')}, flow {got.get('flow')}")


def _image_rows(img):
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)


def _mean_colour(col):
    if isinstance(col, list):                            # beds drawn by weight: their weighted mean
        w = np.array([c[1] for c in col])
        return (np.array([c[0] for c in col]) * (w / w.sum())[:, None]).sum(0)
    return col


def test_strata_image():
    img, z_lo, z_hi = S.strata_image('toroweap', name='t_strata')
    px = _image_rows(img)[0]
    w = px.shape[0]
    lay = P.column_layers('toroweap')
    errs = []
    for nm, b, t, col, rough, bed, jit in lay:
        i0, i1 = int((b - z_lo) / (z_hi - z_lo) * w), int((t - z_lo) / (z_hi - z_lo) * w)
        mean = px[i0 + 1:i1 - 1, :3].mean(0)
        errs.append(float(np.abs(np.log(mean / _mean_colour(col))).max()))
    check('strata image: each formation averages its colour (beds jitter around it)', max(errs) < 0.15,
          f'{w} px over {z_lo:.0f}-{z_hi:.0f} m; worst log-ratio {max(errs):.3f}')
    # the material's form: 8 facies rows (the same formations, their own beds), darker bedding planes, the column run
    # on past its ends
    img, z_lo2, z_hi2 = S.strata_image('toroweap', name='t_strata8', rows=8, parting=0.3, pad_m=200.0)
    rows = _image_rows(img)
    lum = rows[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    differ = float(np.mean(np.abs(lum[0] - lum[5]) > 1e-4))
    W2 = rows.shape[1]
    worst = 0.0
    for _n, b, t, *_ in P.column_layers('toroweap'):
        i0, i1 = int((b - z_lo2) / (z_hi2 - z_lo2) * W2) + 2, int((t - z_lo2) / (z_hi2 - z_lo2) * W2) - 2
        m0, m5 = rows[0, i0:i1, :3].mean(0), rows[5, i0:i1, :3].mean(0)
        worst = max(worst, float(np.abs(np.log(np.maximum(m0, 1e-4) / np.maximum(m5, 1e-4))).max()))
    same_formation = worst < 0.15
    steps = np.diff(lum[0])
    dark_lines = int(np.sum((steps[:-1] < -0.004) & (steps[1:] > 0.004)))          # one-pixel dips: partings
    check('strata image rows: beds differ between facies rows, partings darken the bedding planes, the ends run on',
          rows.shape[0] == 8 and differ > 0.3 and dark_lines > 100 and same_formation
          and abs((z_lo - z_lo2) - 200.0) < 1e-6 and abs((z_hi2 - z_hi) - 200.0) < 1e-6,
          f'{rows.shape[0]} rows x {rows.shape[1]} px; rows 0 and 5 differ on {100 * differ:.0f} % of the pixels; '
          f'{dark_lines} one-pixel partings in row 0; range {z_lo2:.0f}-{z_hi2:.0f} m')
    img, zl, zh = S.strata_image('alpine_limestone', name='t_alp')
    check('a repeating column spans one period and is read with REPEAT', bool(img.get('eido_repeat'))
          and abs((zh - zl) - sum(f[1] for f in P.STRATA_COLUMNS['alpine_limestone']['formations'])) < 1e-6,
          f'period {zh - zl:.0f} m')
    looks = P.column_layers([dict(name='Redwall limestone', thickness_m=170.0), dict(name='Hermit shale',
                                                                                     thickness_m=265.0)], looks=True)
    check('looks=True colours the solver\'s formations by name (FORMATION_LOOKS)',
          np.allclose(looks[0][3], P.hex_linear('#8d6455')) and np.allclose(looks[1][3], P.hex_linear('#8b5a48'))
          and looks[1][5] == 1.2, '')
    ok = P.column_layers([(80.0, 1.0, 70.0, 3, 'Kaibab cliff'), (60.0, 2.0, 30.0, 1, 'Hermit slope')])
    lc = dict(P.LAYER_COLOURS)
    check("a solver's column is coloured by layer name", np.allclose(ok[0][3], P.hex_linear(lc['kaibab']))
          and np.allclose(ok[1][3], P.hex_linear(lc['hermit'])) and ok[1][1] == 80.0, '')
    img, z_lo, z_hi = S.strata_image('badlands_cedar_pass', name='b_strata')
    w = img.size[0]
    px = np.empty(w * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(w, 4)
    lay = [L for L in P.column_layers('badlands_cedar_pass') if L[0].startswith('Brule, Scenic')][0]
    i0, i1 = int((lay[1] - z_lo) / (z_hi - z_lo) * w), int((lay[2] - z_lo) / (z_hi - z_lo) * w)
    seg = px[i0:i1, :3]
    redness = seg[:, 0] / np.maximum(seg[:, 2], 1e-4)
    beds = int(np.sum(np.abs(np.diff(redness)) > 0.05)) + 1
    check('multi-colour bedding: the Scenic member is many thin beds of buff, red and maroon',
          beds >= 15 and redness.max() / redness.min() > 1.4,
          f'{beds} beds in {lay[2] - lay[1]:.0f} m, red/blue ratio {redness.min():.2f}..{redness.max():.2f}')
    # the beds in relief: the same beds as the colour image (its colours unchanged), each bed one hardness, hard and
    # soft beds both common, and a ledge flagged on the top metre of each hard bed under a soft one
    plain, _a, _b = S.strata_image('toroweap', name='t_plain', rows=4, parting=0.25)
    img, _a, _b = S.strata_image('toroweap', name='t_relief', rows=4, parting=0.25, relief=True)
    rimg = bpy.data.images.get(img.get('eido_relief', ''))
    cp, cr = _image_rows(plain), _image_rows(img)
    rel = _image_rows(rimg) if rimg is not None else None
    ok = rel is not None and rel.shape == cr.shape and np.array_equal(cp, cr)
    detail = 'no relief image'
    if ok:
        r0, g0 = rel[0, :, 0], rel[0, :, 1]
        col_steps = np.flatnonzero(np.any(np.abs(np.diff(cr[0, :, :3], axis=0)) > 1e-6, axis=1))
        rel_steps = np.flatnonzero(np.abs(np.diff(r0)) > 1e-6)
        inside = float(np.isin(rel_steps, col_steps).mean()) if len(rel_steps) else 0.0
        hard, soft = float((r0 >= 0.7).mean()), float((r0 <= 0.35).mean())
        tops = np.flatnonzero(np.diff(g0) < -0.5)                       # the last pixel of each ledge
        under_soft = float(np.mean([r0[i] - r0[min(i + 1, len(r0) - 1)] > 0.3 for i in tops])) if len(tops) else 0.0
        ok = inside == 1.0 and hard > 0.25 and soft > 0.2 and len(tops) > 50 and under_soft == 1.0
        detail = (f'{len(rel_steps)} relief steps, all on bed boundaries: {inside == 1.0}; hard {100 * hard:.0f} % '
                  f'soft {100 * soft:.0f} % of the column; {len(tops)} ledges, each over a softer bed: '
                  f'{under_soft == 1.0}; colours unchanged by relief')
    check('strata relief: the same beds, hard and soft, with ledges on the hard beds under soft ones', ok, detail)


def _composite(pal, masks, x, y, consts=None):
    """The material's coverage composite with numpy (a layer covers what lies below it): exclusive weights."""
    cov = [np.clip(P.evaluate(L['weight'], masks, x, y, consts or pal['constants']), 0, 1) for L in pal['layers']]
    excl = [None] * len(cov)
    rem = np.ones_like(cov[0])
    for i in range(len(cov) - 1, -1, -1):
        excl[i] = cov[i] * rem
        rem = rem * (1 - cov[i])
    return {L['name']: e for L, e in zip(pal['layers'], excl)}


def test_mask_driven_placement():
    """A canyon wall in section (rim, cliff, talus, bench, cliff, talus, river) with the masks an eroded recipe gives
    it: rock 1 and vegetation 0 everywhere (the masks package counts ground eroded 600 m as rock). The desert
    palette must still put soil and scrub on the flats, talus on the repose slopes, cliffs on the walls, slickrock
    on the rims and sand in the river, from slope, curvature, flow and wetness: what Skye saw as 'flat cutoff by
    height' was the whole canyon reading as the rock layer."""
    segs = [(2.0, 60, 0.0, 0.0, 0.2, 0.3), (12.0, 6, 0.7, 0.0, 0.2, 0.2), (70.0, 20, 0.0, 0.0, 0.05, 0.05),
            (31.0, 40, 0.0, 0.5, 0.1, 0.1), (5.0, 50, 0.0, 0.0, 0.3, 0.35), (62.0, 20, 0.2, 0.0, 0.05, 0.05),
            (30.0, 40, 0.0, 0.6, 0.15, 0.1), (1.0, 30, 0.0, 0.0, 0.97, 0.9)]
    cols = []
    for slope, n, cvx, ccv, flow, wet in segs:
        cols += [(slope, cvx, ccv, flow, wet)] * n
    a = np.array(cols, np.float64)
    ny = 60
    S_, CV, CC, FL, WT = (np.repeat(a[None, :, k], ny, 0) for k in range(5))
    nx = a.shape[0]
    X, Y = np.meshgrid(np.arange(nx) * 4.0, np.arange(ny) * 4.0)
    river = (np.abs(S_ - 1.0) < 1e-9)
    masks = dict(slope=S_, convex_20m=CV, concave_20m=CC, flow=FL, wetness=WT, occlusion=np.full(S_.shape, 0.85),
                 deposit=np.where(river, 1.2, 0.0), talus=np.zeros(S_.shape), sand=np.zeros(S_.shape),
                 rock_toe=np.zeros(S_.shape), rock=np.ones(S_.shape), vegetation=np.zeros(S_.shape),
                 wear=np.full(S_.shape, 600.0), height=np.full(S_.shape, 900.0), northness=np.zeros(S_.shape))
    pal = P.get('desert_sandstone')
    w = _composite(pal, masks, X, Y)
    flat = (S_ < 8) & ~river

    def share(names, sel):
        return float(sum(w[n][sel] for n in names).mean())
    res = dict(flats_soil_scrub=share(('soil', 'scrub'), flat), flats_scrub=share(('scrub',), flat),
               repose_talus=share(('talus',), (S_ > 28) & (S_ < 34)), walls_cliff=share(('cliff',), S_ > 55),
               rims_slickrock=share(('slickrock',), CV > 0.5), river_wash=share(('wash',), river))
    ok = (res['flats_soil_scrub'] > 0.75 and 0.05 < res['flats_scrub'] < 0.6 and res['repose_talus'] > 0.5
          and res['walls_cliff'] > 0.8 and res['rims_slickrock'] > 0.3 and res['river_wash'] > 0.6)
    w2 = _composite(pal, dict(masks, rock=np.zeros(S_.shape), vegetation=np.ones(S_.shape)), X, Y)
    same = max(float(np.abs(w[k] - w2[k]).max()) for k in w)
    check('desert layers come from slope, curvature, flow and wetness, not the wear-polluted rock mask',
          ok and same < 1e-9, ', '.join(f'{k} {v:.2f}' for k, v in res.items()) + f'; rock/vegetation swapped: max '
          f'change {same:.1e}')
    # alpine: pasture on the floor, forest on the lower walls' gentler slopes, rock on the walls, snow only above the
    # snowline in the hollows and on benches, never on the walls
    pal = P.get('alpine')
    m2 = dict(masks, height=np.full(S_.shape, 600.0))
    wa = _composite(pal, m2, X, Y, dict(pal['constants'], base_elevation_m=800.0))
    m3 = dict(masks, height=np.full(S_.shape, 2200.0), concave_20m=np.full(S_.shape, 0.6))
    wb = _composite(pal, m3, X, Y, dict(pal['constants'], base_elevation_m=800.0))
    res = dict(low_floor_pasture=float(wa['pasture'][flat].mean()),
               low_slopes_forest=float(wa['forest'][(S_ > 28) & (S_ < 34)].mean()),
               low_walls_rock=float(wa['rock'][S_ > 55].mean()),
               high_benches_snow=float(wb['snow'][S_ < 8].mean()), high_walls_snow=float(wb['snow'][S_ > 55].mean()))
    check('alpine layers: pasture on the floor, forest on the lower slopes, rock walls, snow in hollows and on benches '
          'above the snowline but not on the walls',
          res['low_floor_pasture'] > 0.5 and res['low_slopes_forest'] > 0.3 and res['low_walls_rock'] > 0.8
          and res['high_benches_snow'] > 0.5 and res['high_walls_snow'] < 0.1,
          ', '.join(f'{k} {v:.2f}' for k, v in res.items()))
    # no landscape palette reads the masks the wear-based rock pollutes
    bad = {n: sorted({'rock', 'vegetation'} & set().union(*[P.names_in(L['weight']) for L in P.get(n)['layers']]))
           for n in P.names()}
    bad = {k: v for k, v in bad.items() if v}
    check("no palette's layer weights read the masks package's rock or vegetation", not bad, str(bad or 'none'))


def test_shape_driven_cover():
    """The cover follows the ground's shape, never a height line (Skye 11-12: "just flat cutoff by height?"):
    snow near the snowline lies in the gullies and is shed off the ribs between them (signed plan curvature, as a
    young cone's shallow gullies carry it); below the treeline scree does not spot a wooded slope (the leopard spots
    of the 11-12 Lauterbrunnen renders) but shows above it; contour-stretched cells run along a hillside; and the
    cinder field and the river-carved range take their dry looks under 'auto'."""
    n = 400
    X, Y = np.meshgrid(np.arange(n) * 5.0, np.arange(n) * 5.0)
    # a flank across the snowline: gullies and ribs alternating every 100 m along x (plan curvature -/+ 4e-3 /m,
    # Fuji's measured p5 and p95), the altitude rising along y from 500 m under the line to 500 m over it
    pal = P.get('volcanic')
    sl = pal['constants']['snowline_m']
    kt = -4e-3 * np.cos(2 * np.pi * X / 200.0)
    alt = sl - 500.0 + Y * (1000.0 / (n * 5.0))
    zeros = np.zeros(X.shape)
    m = dict(slope=np.full(X.shape, 30.0), height=alt, curv_plan_20m=kt, curv_profile_20m=zeros, northness=zeros,
             flow=np.full(X.shape, 0.3), concave_20m=zeros, convex_20m=zeros, occlusion=np.full(X.shape, 0.9),
             wetness=np.full(X.shape, 0.3), talus=zeros, deposit=zeros, sand=zeros, snow=zeros, lava=zeros,
             rock_toe=zeros)
    w = _composite(pal, m, X, Y, dict(pal['constants'], base_elevation_m=0.0))['snow']
    band = (alt > sl - 250) & (alt < sl)
    gully, rib = kt < -3e-3, kt > 3e-3
    g_s, r_s = float(w[band & gully].mean()), float(w[band & rib].mean())
    # a contour edge would make each row of the band one value: the snow must vary along the contours instead
    along = float(np.mean([w[j].std() for j in range(n) if band[j, 0]]))
    check('snow near the snowline lies in the gullies, not on the ribs between them, and its edge is no contour',
          g_s > 0.6 and r_s < 0.25 and along > 0.25, f'250 m under the line: gullies {g_s:.2f}, ribs {r_s:.2f}; '
          f'spread along a contour {along:.2f}')
    # the alpine palette on a 30-40 degree slope with no talus: below the treeline forest (scree under it in the
    # order), above it scree and rock, never scree laid over the forest
    pal = P.get('alpine')
    slope = 30.0 + 10.0 * X / X.max()
    ma = dict(m, slope=slope, flow=np.full(X.shape, 0.2), wetness=np.full(X.shape, 0.2), curv_plan_20m=zeros)
    lo = _composite(pal, dict(ma, height=np.full(X.shape, 600.0)), X, Y, dict(pal['constants'], base_elevation_m=800.0))
    hi = _composite(pal, dict(ma, height=np.full(X.shape, 1800.0)), X, Y, dict(pal['constants'], base_elevation_m=800.0))
    res = dict(low_forest=float(lo['forest'].mean()), low_scree=float(lo['scree'].mean()),
               high_bare=float((hi['scree'] + hi['rock']).mean()), high_forest=float(hi['forest'].mean()))
    check('alpine scree and rock: none spotting the forest below the treeline, bare ground above it',
          res['low_forest'] > 0.75 and res['low_scree'] < 0.12 and res['high_bare'] > 0.5 and res['high_forest'] < 0.1,
          ', '.join(f'{k} {v:.2f}' for k, v in res.items()))
    # contour-stretched cells on a hillside rising along x: a cell spans far more along the contour (y) than across it
    hill = 0.25 * X
    c = P.evaluate('cells(500, 1, 14)', dict(height=hill), X, Y)
    across = float((np.abs(np.diff(c, axis=1)) > 1e-12).mean())
    along_c = float((np.abs(np.diff(c, axis=0)) > 1e-12).mean())
    flat = P.evaluate('cells(500, 1)', {}, X, Y)
    check('cells(scale, seed, z_stretch) run along the contours of a hillside',
          along_c < 0.5 * across and len(np.unique(np.round(flat, 9))) > 4,
          f'boundary steps across the contours {across:.4f}, along them {along_c:.4f}')
    # the dry looks
    cin = P.get('auto', recipe='cinder_cones')
    fr = P.get('auto', recipe='fluvial_range')
    L = {x['name']: x for x in cin['layers']}
    mc = dict(m, slope=np.where(X < 1000, 4.0, 30.0), height=np.full(X.shape, 120.0), curv_plan_20m=zeros,
              peaks=zeros, wetness=np.full(X.shape, 0.6), flow=np.full(X.shape, 0.2))
    wc = _composite(cin, mc, X, Y, dict(cin['constants'], base_elevation_m=0.0))
    plain, cone = X < 1000, X >= 1000
    ok = (float(wc['forest'][plain].mean()) < 0.4 and float(wc['scoria'][cone].mean()) > 0.8
          and L['forest']['canopy']['crown_m'] < 6 and fr['constants']['snowline_m'] > 4000
          and not any(x.get('strata') for x in fr['layers']))
    check("'auto' looks: the cinder field's plain under straw grass and scattered juniper, cinders on the cones; the "
          'river-carved range chaparral and granite without snow',
          ok, f"plain forest {float(wc['forest'][plain].mean()):.2f}, cone cinders {float(wc['scoria'][cone].mean()):.2f}, "
          f"range snowline {fr['constants']['snowline_m']:.0f} m")


def test_constants_and_looks():
    import json as _json
    me = bpy.data.meshes.new('tc')
    ob = bpy.data.objects.new('tc', me)
    ob['eido_terrain'] = _json.dumps(dict(base_elevation_m=800.0, knobs=dict(snowline_m=2750.0, treeline_m=1950.0)))
    c1 = S.terrain_constants(ob)
    ob['eido_terrain'] = _json.dumps(dict(base_elevation_m=713.5, knobs=dict(dem='lauterbrunnen')))
    c2 = S.terrain_constants(ob)
    check("terrain_constants reads the base elevation, the recipe's knobs and a real place's mask parameters",
          c1 == dict(base_elevation_m=800.0, snowline_m=2750.0, treeline_m=1950.0)
          and c2 == dict(base_elevation_m=713.5, snowline_m=2750.0, treeline_m=1950.0), f'{c1}; {c2}')
    pal = P.get('auto', recipe='impact_crater')
    check("the impact crater's 'auto' palette reads Meteor Crater's column at object z (the recipe writes no zs)",
          pal['strata']['column'] == 'meteor_crater' and pal['strata']['source'] == 'position'
          and 'strata' not in P.masks_used(pal), str({k: pal['strata'][k] for k in ('column', 'source', 'z_offset_m')}))


def test_rock_placement():
    # a 40 m wide band of talus (1 m thick) on a 20-degree plane, the rest bare
    tan20 = math.tan(math.radians(20))

    def height_at(x, y):
        return np.asarray(x) * tan20

    def mask_at(n, x, y):
        x = np.asarray(x)
        if n == 'talus':
            return np.where(np.abs(np.asarray(y)) < 20, 1.0, 0.0)
        if n == 'slope':
            return np.full(x.shape, 20.0)
        return None
    spec = dict(density='2.0*smoothstep(0.2, 1.0, talus)', size_m=(0.1, 2.0), alpha=2.4, bury=0.35, align=1.0,
                tilt_deg=0.0, squash=(1.0, 1.0), lod_m_per_m=0.0)
    r = D.place_rocks(spec, mask_at, height_at, None, focus=(0, 0), radius_m=100, seed=3, n_models=2,
                      model_dims=[(1.0, 0.6, 0.5), (0.5, 0.8, 0.4)])
    x, y = r['xyz'][:, 0], r['xyz'][:, 1]
    inside = np.abs(y) < 20
    area = 0.0
    for yy in np.linspace(-20, 20, 4001)[:-1]:
        area += 2 * math.sqrt(max(100 ** 2 - (yy + 0.005) ** 2, 0)) * 0.01
    dens = inside.sum() / area
    check('rock density matches the expression (2 per m^2 on talus, 0 off it)', abs(dens - 2.0) < 0.1
          and (~inside).sum() == 0, f'{dens:.3f} per m^2, {(~inside).sum()} off the talus')
    s = r['size']
    frac = (s > 1.0).mean()
    want = ((1.0 / 0.1) ** -2.4 - (2.0 / 0.1) ** -2.4) / (1 - (2.0 / 0.1) ** -2.4)
    check('sizes follow the power law N(>s) ~ s^-2.4', abs(frac - want) / want < 0.25,
          f'fraction over 1 m {frac:.5f}, expected {want:.5f}, {len(s)} rocks')
    # burial: the centre sits (0.5 - bury) of the rock's height above the ground along the surface normal
    up_z = math.cos(math.radians(20))
    dz = r['xyz'][:, 2] - height_at(x, y)
    hgt = np.array([0.5, 0.4])[r['pick']] * r['scale'][:, 2]
    check('rocks are buried 35 % of their height', np.allclose(dz, 0.15 * hgt * up_z, atol=1e-6), '')
    # alignment: align=1 turns the local Z onto the 20-degree normal
    a, b, g = r['euler'][:, 0], r['euler'][:, 1], r['euler'][:, 2]
    # the local Z axis: the third column of R = Rz(g) Ry(b) Rx(a)
    Rz = np.stack([np.sin(a) * np.sin(g) + np.cos(a) * np.sin(b) * np.cos(g),
                   -np.sin(a) * np.cos(g) + np.cos(a) * np.sin(b) * np.sin(g), np.cos(a) * np.cos(b)], 1)
    n = np.array([-tan20, 0, 1]) / math.hypot(tan20, 1)
    check('align=1 stands each rock on the surface normal', np.allclose(Rz @ n, 1.0, atol=1e-6),
          f'min cos {float((Rz @ n).min()):.6f}')
    r2 = D.place_rocks(dict(spec, lod_m_per_m=0.01), mask_at, height_at, None, focus=(0, 0), radius_m=100, seed=3)
    d2 = np.hypot(r2['xyz'][:, 0], r2['xyz'][:, 1])
    check('far ground keeps only the larger rocks (lod)', bool(np.all(r2['size'] >= np.maximum(0.1, 0.01 * d2) - 1e-9)), '')
    r3 = D.place_rocks(spec, mask_at, height_at, None, focus=(0, 0), radius_m=100, seed=4, n_models=3,
                       model_dims=[(1, 1, 0.5)] * 3, model_sizes=[(0.0, 0.4), (0.3, 5.0), (math.inf, math.inf)])
    s3, p3 = r3['size'], r3['pick']
    okp = np.where(p3 == 0, s3 <= 0.4, np.where(p3 == 1, s3 >= 0.3, False))
    both = (s3 > 0.3) & (s3 < 0.4)
    check('size-ranged models: each rock is a model whose range holds its size, never an unnamed one',
          bool(okp.all()) and set(np.unique(p3[both])) == {0, 1},
          f'{len(s3)} rocks, picks {np.bincount(p3, minlength=3).tolist()}')


def test_instancer():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tan10 = math.tan(math.radians(10))

    def height_at(x, y):
        return np.asarray(x) * tan10

    def mask_at(n, x, y):
        return np.ones(np.shape(x)) if n == 'talus' else None
    spec = dict(P.get('alpine')['dressing'], density='0.5*smoothstep(0.2, 1.0, talus)')
    res = D.scatter_rocks(spec=spec, mask_at=mask_at, height_at=height_at, focus=(0, 0), radius_m=20, seed=1, log=None)
    dg = bpy.context.evaluated_depsgraph_get()
    n_inst = sum(1 for inst in dg.object_instances if inst.is_instance and inst.parent
                 and inst.parent.original == res['object'])
    check('every placed rock is a Geometry Nodes instance of a model', n_inst == res['count'] and res['count'] > 300,
          f"{res['count']} placed, {n_inst} instances")
    src = bpy.data.collections.get(f"{D.SOURCE_COLLECTION}_{spec['colour'].lstrip('#')}")
    check('the rock models stay out of the scene (only instances show)',
          src is not None and src.name not in [c.name for c in bpy.context.scene.collection.children_recursive],
          f'{len(src.objects)} source meshes')
    # a second spec with the same colour shares the source collection: its instances must be its own models only,
    # and each rock's model must hold its size
    spec2 = dict(spec, models=[('rock_07', 0.0, 0.5)], size_m=(0.12, 0.5))
    res2 = D.scatter_rocks(spec=spec2, mask_at=mask_at, height_at=height_at, focus=(60, 0), radius_m=15, seed=2,
                           name='rocks2', log=None)
    dg = bpy.context.evaluated_depsgraph_get()
    used = {inst.object.original.get('eido_model') for inst in dg.object_instances
            if inst.is_instance and inst.parent and inst.parent.original == res2['object']}
    check("instances of one spec are only its models (Collection Info's alphabetical children)",
          used == {'rock_07'} and res2['count'] > 0, f"{res2['count']} rocks, models used {sorted(used)}")


TESTS = [test_palettes_valid, test_expressions, test_packing, test_materials, test_strata_image,
         test_mask_driven_placement, test_shape_driven_cover, test_constants_and_looks, test_rock_placement, test_instancer]

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    only = argv[argv.index('-k') + 1] if '-k' in argv else None
    for t in TESTS:
        if only and only not in t.__name__:
            continue
        try:
            t()
        except Exception as e:
            traceback.print_exc()
            check(t.__name__, False, f'{type(e).__name__}: {e}')
    n_bad = sum(1 for r in RESULTS if not r[1])
    print(f'[test] {len(RESULTS) - n_bad} passed, {n_bad} failed', flush=True)
    sys.exit(1 if n_bad else 0)
