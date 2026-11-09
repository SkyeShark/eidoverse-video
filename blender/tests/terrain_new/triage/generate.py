"""Generate every triage subject's heightfield on the CPU (no GPU, no Blender) into the cache render.py reads.

    python generate.py [--only a,b] [--group landform] [--shard 0/3] [--force]

Writes <CACHE>/<name>.npz: 'height' (field units, float32), 'aux' (the ridge channel), 'ov' (the mask painted on the
clay, when the subject has one) and 'meta' (json: W, vertical scale, z_base, tile, warnings, relief, timings).
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..', 'terrain_ekigar')))
sys.path.insert(0, HERE)
import _ekigar_load  # noqa: E402
import scenes  # noqa: E402

ek = _ekigar_load.load()


def build(s):
    """(graph, target, input-node-or-None) for a subject."""
    b = s['build']
    if b[0] == 'ex':
        g, t, _fx = ek.operator_example(b[1], b[2] or None)
        return g, t, None
    if b[0] == 'fixture':
        g, t, _fx = ek.fixture_graph()
        return g, t, None
    if b[0] == 'default':
        g, t = ek.examples.default_project_graph()
        return g, t, None
    if b[0] == 'chain':
        g, ids = ek.chain_graph([(op, dict(ek.default_params(op), **p)) for op, p in b[1]])
        return g, ids[-1], None
    if b[0] == 'maskex':
        g, t, _fx = ek.operator_example(b[1], b[2] or None)
        src = [e['from']['node'] for e in g['edges'].values() if e['to']['node'] == t and e['to']['port'] == 'in']
        return g, t, src[0]
    if b[0] == 'masks':
        g, ids = ek.chain_graph([(op, dict(ek.default_params(op), **p)) for op, p in b[1]])
        return g, ids[-1], None
    raise ValueError(b)


def generate(s):
    t0 = time.time()
    g, target, terrain_node = build(s)
    kw = dict(resolution=s['res'], world_size=s['W'], vertical_scale=scenes.VS)
    ov = None
    if terrain_node is not None:                       # a derive op: the terrain is its input, the mask its output
        hf = ek.generate(g, target=terrain_node, z_base='min', **kw)
        m = ek.generate(g, target=target, **kw)
        ov = m.height
    else:
        hf = ek.generate(g, target=target, z_base='min', **kw)
        if s['build'][0] == 'masks':
            ov = hf.mask(s['build'][2][0])
    st = hf.stats()
    meta = {'name': s['name'], 'W': hf.world_size, 'vs': hf.vertical_scale, 'z_base': hf.z_base,
            'tile': hf.tile.as_dict(), 'warnings': hf.warnings, 'relief_m': st['heightRangeMetres'],
            'texel_m': hf.world_size / hf.resolution[0], 'nonFinite': st['nonFinite'],
            'flatFraction': st['flatFraction'], 'outs': sorted(hf.outs), 'generate_s': round(time.time() - t0, 1)}
    arrays = {'height': hf.height.astype(np.float32), 'aux': hf.aux.astype(np.float32)}
    if ov is not None:
        arrays['ov'] = np.asarray(ov, dtype=np.float32)
        meta['ov_range'] = [float(np.nanmin(ov)), float(np.nanmax(ov))]
    os.makedirs(scenes.CACHE, exist_ok=True)
    np.savez_compressed(scenes.cache_path(s['name']), meta=json.dumps(meta), **arrays)
    return meta


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None)
    ap.add_argument('--group', default=None)
    ap.add_argument('--shard', default=None, help='k/n: every n-th subject starting at k')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    subs = [s for s in scenes.SUBJECTS if s['build'][0] != 'dem']
    if a.only:
        want = a.only.split(',')
        subs = [s for s in subs if s['name'] in want]
    if a.group:
        subs = [s for s in subs if s['group'] in a.group.split(',')]
    if a.shard:
        k, n = (int(v) for v in a.shard.split('/'))
        subs = subs[k::n]
    for s in subs:
        if not a.force and os.path.exists(scenes.cache_path(s['name'])):
            continue
        try:
            m = generate(s)
            print(f"{s['name']:34s} {m['generate_s']:6.1f}s relief {m['relief_m']:9.1f} m  "
                  f"warn {len(m['warnings'])} nonfinite {m['nonFinite']}", flush=True)
        except Exception as ex:   # keep going: a subject that fails to generate is itself a finding
            print(f"{s['name']:34s} FAILED: {type(ex).__name__}: {ex}", flush=True)
