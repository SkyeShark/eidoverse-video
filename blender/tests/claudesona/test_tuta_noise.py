"""The TuTa's value noise (claudesona/tuta.py, the 'cs.vnoise3' group: smooth value noise over integer cells, each cell's
value Blender's White Noise) against the JS's vnoise3 (claudesona_wardrobe.js: the same smooth value noise, each cell's
value three's TSL hash, PCG, of the cell's integer coordinates), over the same 200,000 points in the noise's own
coordinates (the TuTa's rest position x 9 for its grime ... x 2600 for its fuzz): a wide box of cells, and a box of
40 cells a side. No render.

The port's noise is evaluated by the group's own node graph rebuilt in Geometry Nodes (the same nodes: White Noise is one
function in shaders and in Geometry Nodes) on a point cloud; the JS's in numpy, uint32 for uint32 (the hash's
multiplies wrap at 2^32 as WGSL's do). Checked: the two are the same noise in distribution and in space (mean,
standard deviation, the histogram's largest gap, the correlation between points a quarter, half and one cell apart)
and different draws (their point-by-point correlation is near zero): the flecks fall elsewhere, at the same size,
spacing and contrast.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/claudesona/test_tuta_noise.py
"""

import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.fx._nodes import Builder, new_group  # noqa: E402

N_PTS = 200_000
LAGS = (0.25, 0.5, 1.0)                    # cells
OUT = os.path.join(S.OUT, 'tuta_noise')
os.makedirs(OUT, exist_ok=True)


# ---- the JS: vnoise3 over three's TSL hash (PCG), uint32 exact ---------------------------------------------------
def pcg(seed):
    with np.errstate(over='ignore'):
        state = seed * np.uint32(747796405) + np.uint32(2891336453)
        word = ((state >> ((state >> np.uint32(28)) + np.uint32(4))) ^ state) * np.uint32(277803737)
        return ((word >> np.uint32(22)) ^ word).astype(np.float64) / 2.0 ** 32


def ihash(a, b, c):
    with np.errstate(over='ignore'):
        return pcg((a * np.uint32(1597334677)) ^ (b * np.uint32(3812015801)) ^ (c * np.uint32(2654435769)))


def vnoise3_js(p):
    q = p + 512.0
    i = np.floor(q)
    f = q - i
    w = f * f * (3.0 - 2.0 * f)
    iu = i.astype(np.int64).astype(np.uint32)

    def h(dx, dy, dz):
        return ihash(iu[:, 0] + np.uint32(dx), iu[:, 1] + np.uint32(dy), iu[:, 2] + np.uint32(dz))

    def mix(a, b, t):
        return a + (b - a) * t
    x00, x10 = mix(h(0, 0, 0), h(1, 0, 0), w[:, 0]), mix(h(0, 1, 0), h(1, 1, 0), w[:, 0])
    x01, x11 = mix(h(0, 0, 1), h(1, 0, 1), w[:, 0]), mix(h(0, 1, 1), h(1, 1, 1), w[:, 0])
    return mix(mix(x00, x10, w[:, 1]), mix(x01, x11, w[:, 1]), w[:, 2])


# ---- the port: tuta._vnoise_group's graph, in Geometry Nodes ------------------------------------------------------
def vnoise_gn(points):
    """evaluate the 'cs.vnoise3' graph (tuta._vnoise_group, node for node) at points through Geometry Nodes"""
    tree, gi, go = new_group('test.vnoise3', 'GeometryNodeTree', [('Geometry', 'NodeSocketGeometry')],
                             [('Geometry', 'NodeSocketGeometry')])
    b = Builder(tree)
    pos = b.node('GeometryNodeInputPosition')
    x, y, z = b.vec(pos.outputs[0]).xyz()
    q = [x + 512.0, y + 512.0, z + 512.0]
    i = [b.floor(c) for c in q]
    f = [b.fract(c) for c in q]
    w = [c * c * (3.0 - c * 2.0) for c in f]

    def h(dx, dy, dz):
        wn = b.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
        b.link(b.combine(i[0] + dx, i[1] + dy, i[2] + dz), wn.inputs['Vector'])
        return b.s(wn.outputs['Value'])
    x00 = b.mix(h(0, 0, 0), h(1, 0, 0), w[0])
    x10 = b.mix(h(0, 1, 0), h(1, 1, 0), w[0])
    x01 = b.mix(h(0, 0, 1), h(1, 0, 1), w[0])
    x11 = b.mix(h(0, 1, 1), h(1, 1, 1), w[0])
    val = b.mix(b.mix(x00, x10, w[1]), b.mix(x01, x11, w[1]), w[2])
    st = b.node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    st.inputs['Name'].default_value = 'vn'
    b.link(gi.outputs[0], st.inputs['Geometry'])
    b.link(val, st.inputs['Value'])
    b.link(st.outputs['Geometry'], go.inputs[0])
    me = bpy.data.meshes.new('pts')
    me.vertices.add(len(points))
    me.vertices.foreach_set('co', points.astype(np.float32).ravel())
    ob = bpy.data.objects.new('pts', me)
    bpy.context.scene.collection.objects.link(ob)
    md = ob.modifiers.new('vn', 'NODES')
    md.node_group = tree
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    em = ev.to_mesh()
    out = np.empty(len(em.vertices), np.float32)
    em.attributes['vn'].data.foreach_get('value', out)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    return out.astype(np.float64)


def stats(a, b_lag):
    return {'mean': float(a.mean()), 'std': float(a.std()),
            'lag_corr': [float(np.corrcoef(a, x)[0, 1]) for x in b_lag]}


def ks(a, b):
    xs = np.sort(np.concatenate([a, b]))
    ca = np.searchsorted(np.sort(a), xs, side='right') / len(a)
    cb = np.searchsorted(np.sort(b), xs, side='right') / len(b)
    return float(np.abs(ca - cb).max())


def main():
    C, R = S.Checks('tuta_noise'), {}
    S.clean_scene()
    rng = np.random.default_rng(7)
    # in the noise's own coordinates (the TuTa's X * 9 for the grime ... X * 2600 for the fuzz): every scale is this
    # one function of cells. Over the body's box at x 9 there are only about 150 cells, whose own random values then
    # decide the numbers, so the statistics are taken over a wide box of cells
    for name, lo, hi in (('cells -300..300', -300.0, 300.0), ('cells 0..40', 0.0, 40.0)):
        P = rng.uniform(lo, hi, (N_PTS, 3))
        d = rng.normal(size=(N_PTS, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        pts = [P] + [P + d * lag for lag in LAGS]
        js = [vnoise3_js(p) for p in pts]
        port = [vnoise_gn(p) for p in pts]
        sj, sp = stats(js[0], js[1:]), stats(port[0], port[1:])
        gap = ks(js[0], port[0])
        same_draw = float(np.corrcoef(js[0], port[0])[0, 1])
        R[name] = {'js': sj, 'port': sp, 'ks': gap, 'pointwise_corr': same_draw}
        lags = ', '.join(f'{lag:g} cell {a:.3f} / {b:.3f}' for lag, a, b in zip(LAGS, sj['lag_corr'], sp['lag_corr']))
        C.check(f'{name}: the same noise (JS / port)',
                abs(sj['mean'] - sp['mean']) < 0.01 and abs(sj['std'] - sp['std']) < 0.01 and gap < 0.02
                and all(abs(a - b) < 0.02 for a, b in zip(sj['lag_corr'], sp['lag_corr'])),
                f"mean {sj['mean']:.4f} / {sp['mean']:.4f}, std {sj['std']:.4f} / {sp['std']:.4f}, histogram gap "
                f"{gap:.4f}; correlation at {lags}")
        C.check(f'{name}: a different draw', abs(same_draw) < 0.05, f'point-by-point correlation {same_draw:+.4f}')
    with open(os.path.join(OUT, 'tuta_noise.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1)
    print(f"[tuta_noise] {'PASS' if C.all_pass else 'FAIL'}: {sum(not r['pass'] for r in C.rows)} failed check(s)")


main()
