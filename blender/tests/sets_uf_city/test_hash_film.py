"""The kit's hash12 as the film rendered it (no GPU):

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_city/test_hash_film.py

citykit.js's hash12 writes Dave Hoskins' hash, but its p3.addAssign(...) runs outside a Fn(), where three r184 skips
the assignment (the film's probe logs carry 'No stack defined for assign operation' at citykit.js:256 for every call):
every frame of the film was rendered with fract((a + b) a), a = fract(x .1031), b = fract(y .1031). This test

  - evaluates NB.hash12 / hash11 written as nodes (a Geometry Nodes tree: the same math nodes the materials use) on
    100 000 window cells and compares them with that formula in float32 (KIT.hash12_np), in both modes ('film', the
    default, and 'hoskins', the source as written);
  - measures what the hash does to the facades, from the facade material's own expressions: the share of lit windows
    at three lit fractions, the share of warm ones at three warmths, and the column structure at litP 0.2 (columns
    lit on 80 % of their floors or more, columns never lit); the film's form must show the film's numbers.
Prints PASS / FAIL.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from eidoblend.sets.unknown_force import citykit as KIT  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('[uf-hash] %s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


class FakeKit:
    def __init__(self, mode):
        self.opts = {'hash': mode}
        self.made = KIT.Made()


R = np.random.default_rng(1909)
N = 100_000
cx = np.floor(R.uniform(0, 64, N)).astype(np.float32)
cy = np.floor(R.uniform(0, 140, N)).astype(np.float32)
seed = R.uniform(0, 1, N).astype(np.float32)
X = (cx + seed * np.float32(113.1)).astype(np.float32)          # h1's arguments in facade_material
Y = (cy + seed * np.float32(71.7)).astype(np.float32)


def eval_nodes(mode, which):
    """NB.hash12(x, y) (or hash11(x)) built in a Geometry Nodes tree over N points at (X, Y, 0); the stored values."""
    K = FakeKit(mode)
    g = KIT.GN(f'uf_hash_probe_{mode}_{which}', K)
    nb = g.nb
    pos = KIT.V(nb, nb.new('GeometryNodeInputPosition').outputs[0], 'v')
    h = nb.hash12(pos.x, pos.y) if which == 'hash12' else nb.hash11(pos.x)
    geo = g.store(g.gin.outputs['Geometry'], 'h', h, 'FLOAT')
    nb.links.new(geo, g.gout.inputs['Geometry'])
    me = bpy.data.meshes.new('uf_hash_probe')
    co = np.stack([X, Y, np.zeros(N, np.float32)], 1)
    me.vertices.add(N)
    me.vertices.foreach_set('co', co.ravel())
    ob = bpy.data.objects.new('uf_hash_probe', me)
    bpy.context.scene.collection.objects.link(ob)
    g.modifier(ob, K)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg).data
    out = np.empty(N, np.float32)
    ev.attributes['h'].data.foreach_get('value', out)
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    K.made.dispose()
    return out


def circ(a, b):
    d = np.abs(a.astype(np.float64) - b.astype(np.float64))
    return np.minimum(d, 1 - d)


for mode in KIT.HASH_MODES:
    got = eval_nodes(mode, 'hash12')
    want = KIT.hash12_np(X, Y, mode)
    d = circ(got, want)
    check(f'hash12 as nodes = the {mode!r} formula (100 000 cells)', np.mean(d < 1e-4) > 0.999,
          f'{np.mean(d < 1e-4) * 100:.3f} % within 1e-4, max {d.max():.2g}')
    got11 = eval_nodes(mode, 'hash11')
    want11 = KIT.hash12_np(X, X * np.float32(1.731) + np.float32(17.17), mode)
    d11 = circ(got11, want11)
    check(f'hash11 as nodes = the {mode!r} formula', np.mean(d11 < 1e-4) > 0.999,
          f'{np.mean(d11 < 1e-4) * 100:.3f} % within 1e-4')
check('the default is the film\'s form', KIT.HASH_MODE == 'film')
try:
    KIT.make_kit({'hash': 'nope'})
    check('make_kit refuses an unknown hash', False)
except ValueError:
    check('make_kit refuses an unknown hash', True)

# ---- what the hash does to the facades (facade_material's expressions, per window cell)
S = np.float32
film = KIT.hash12_np(X, Y, 'film')
hosk = KIT.hash12_np(X, Y, 'hoskins')
check('the film\'s hash is low-biased (mean 0.37, median 0.31), Hoskins\' uniform',
      abs(film.mean() - 0.368) < 0.01 and abs(np.median(film) - 0.309) < 0.015 and abs(hosk.mean() - 0.5) < 0.01,
      f'film mean {film.mean():.3f} median {np.median(film):.3f}; hoskins mean {hosk.mean():.3f}')


def lit_share(mode, litF):
    h1 = KIT.hash12_np(cx + seed * S(113.1), cy + seed * S(71.7), mode)
    hf = KIT.hash12_np(cy * S(1.31) + seed * S(9.7), seed * S(57.3), mode)
    return float(np.mean(h1 <= litF * (hf * S(1.25) + S(0.35))))


def warm_share(mode, warmth):
    hc = KIT.hash12_np(cx + seed * S(19.1), cy + S(3.3), mode)
    return float(np.mean(hc <= warmth))


lf = {m: [lit_share(m, f) * 100 for f in (0.10, 0.18, 0.26)] for m in KIT.HASH_MODES}
ws = {m: [warm_share(m, w) * 100 for w in (0.3, 0.55, 0.8)] for m in KIT.HASH_MODES}
print('[uf-hash] lit windows at litF 0.10 / 0.18 / 0.26: film %s %%, hoskins %s %%' %
      ([round(v, 1) for v in lf['film']], [round(v, 1) for v in lf['hoskins']]), flush=True)
print('[uf-hash] warm windows at warmth 0.3 / 0.55 / 0.8: film %s %%, hoskins %s %%' %
      ([round(v, 1) for v in ws['film']], [round(v, 1) for v in ws['hoskins']]), flush=True)
check('lit windows as the film (18.2 / 28.5 / 37.2 %)', max(abs(a - b) for a, b in zip(lf['film'], (18.2, 28.5, 37.2))) < 1.5)
check('warm windows as the film (49 / 72.5 / 89.5 %)', max(abs(a - b) for a, b in zip(ws['film'], (49.0, 72.5, 89.5))) < 2.0)
# column structure: one building (a seed), 64 columns x 60 floors, litP 0.2
cols_on, cols_off = {}, {}
for mode in KIT.HASH_MODES:
    on80, never = [], []
    for sd in R.uniform(0, 1, 200).astype(np.float32):
        gx, gy = np.meshgrid(np.arange(64, dtype=np.float32), np.arange(60, dtype=np.float32))
        h1 = KIT.hash12_np(gx + sd * S(113.1), gy + sd * S(71.7), mode)
        lit = h1 <= S(0.2)
        frac = lit.mean(0)
        on80.append(np.mean(frac >= 0.8))
        never.append(np.mean(frac == 0))
    cols_on[mode], cols_off[mode] = float(np.mean(on80)) * 100, float(np.mean(never)) * 100
print('[uf-hash] columns lit on >= 80 %% of floors: film %.1f %%, hoskins %.1f %%; never lit: film %.1f %%, hoskins %.1f %%'
      % (cols_on['film'], cols_on['hoskins'], cols_off['film'], cols_off['hoskins']), flush=True)
check('the film\'s whole lit and dark columns (about 21 % / 19 %; none with Hoskins\')',
      cols_on['film'] > 15 and cols_off['film'] > 13 and cols_on['hoskins'] < 0.5 and cols_off['hoskins'] < 0.5)
fails = [n for n, ok in results if not ok]
print(f'[uf-hash] {len(results) - len(fails)}/{len(results)} passed' + (f'; FAILED: {fails}' if fails else ''))
