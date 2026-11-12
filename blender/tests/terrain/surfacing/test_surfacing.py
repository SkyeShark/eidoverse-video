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
    check("'plants' expands to vegetation with the stream-bed factor undone",
          P.names_in('plants') == {'vegetation', 'channels'}
          and np.isclose(P.evaluate('plants', dict(vegetation=np.array([0.1]), channels=np.array([1.0])))[0], 0.4), '')
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


def test_materials():
    worst = []
    for n in P.names():
        t0 = time.time()
        mat = S.surface_material(n, log=None, name=f'mat_{n}')
        ng = next(nd.node_tree for nd in mat.node_tree.nodes if nd.bl_idname == 'ShaderNodeGroup')
        imgs = {nd.image.name for nd in ng.nodes if nd.bl_idname == 'ShaderNodeTexImage' and nd.image}
        attrs = {nd.attribute_name[5:] for nd in ng.nodes if nd.bl_idname == 'ShaderNodeAttribute'}
        used = P.masks_used(P.get(n)) - set(P.names_in(P.get(n)['dressing']['density']) if P.get(n).get('dressing') else [])
        worst.append((n, len(imgs), len(ng.nodes), round(time.time() - t0, 2)))
        if len(imgs) > S.MAX_IMAGES or not used <= attrs | {'strata'}:
            check(f'material {n}', False, f'images {len(imgs)}, attributes {sorted(attrs)} vs used {sorted(used)}')
            return
        assert ng.name.startswith(S.GROUP_NAME)
    check('every palette builds under the sampler budget and reads its masks', True,
          '; '.join(f'{n}: {i} images, {k} nodes, {t} s' for n, i, k, t in worst))
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
          len(obj.data.materials) == 1 and 'slope' not in miss and 'rock' in miss, f'alpine lacks {miss[:6]}...')


def test_strata_image():
    img, z_lo, z_hi = S.strata_image('toroweap', name='t_strata')
    w = img.size[0]
    px = np.empty(w * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(w, 4)
    lay = P.column_layers('toroweap')
    errs = []
    for nm, b, t, col, rough, bed, jit in lay:
        i0, i1 = int((b - z_lo) / (z_hi - z_lo) * w), int((t - z_lo) / (z_hi - z_lo) * w)
        mean = px[i0 + 1:i1 - 1, :3].mean(0)
        errs.append(float(np.abs(np.log(mean / col)).max()))
    check('strata image: each formation averages its colour (beds jitter around it)', max(errs) < 0.12,
          f'{w} px over {z_lo:.0f}-{z_hi:.0f} m; worst log-ratio {max(errs):.3f}')
    ok = P.column_layers([(80.0, 1.0, 70.0, 3, 'Kaibab cliff'), (60.0, 2.0, 30.0, 1, 'Hermit slope')])
    check("a solver's column is coloured by layer name", np.allclose(ok[0][3], P.hex_linear('#c2b8a3'))
          and np.allclose(ok[1][3], P.hex_linear('#9a4f37')) and ok[1][1] == 80.0, '')
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
         test_rock_placement, test_instancer]

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
