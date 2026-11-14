"""expr_glsl against palettes.evaluate (SURFACING_DESIGN.md 5.4, package 1, item 2: within 1e-5): every palette's
expressions (layer weights, patch and ledge `where`, streaks_where, ramp and satmap `t`, tone, damp_where) with every
noise at its mean, compiled to GLSL and evaluated on the GPU at 4096 points of random maps in their units, against
the numpy evaluation in float64.

    bash run_blender.sh blender/tests/terrain/surface_data/test_expr.py
    (queue it with EIDO_GPU_WRAP on a shared machine: blender/tests/_where.py)

Writes out/surface_data/expr.json. Exit 0 when every expression of every palette agrees within 1e-5.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'core'))
import plain_import  # noqa: E402

plain_import.install()
import numpy as np  # noqa: E402

from eidoblend.terrain.build import palettes as P  # noqa: E402
from eidoblend.terrain.surface import expr_glsl as XG  # noqa: E402

OUT = os.path.join(HERE, '..', 'out', 'surface_data')
F = np.float32
NPTS = 4096
TOL = 1e-5


def expressions(pal):
    out = []
    for L in pal['layers']:
        out.append((f"{L['name']}.weight", L['weight']))
        pts = L.get('patches') or []
        for k, pt in enumerate([pts] if isinstance(pts, dict) else pts):
            if pt.get('where'):
                out.append((f"{L['name']}.patch{k}", pt['where']))
        if L.get('streaks_where'):
            out.append((f"{L['name']}.streaks_where", L['streaks_where']))
        if (L.get('ledges') or {}).get('where'):
            out.append((f"{L['name']}.ledges", L['ledges']['where']))
        if L.get('ramp'):
            out.append((f"{L['name']}.ramp", L['ramp']['t']))
    o = pal['options']
    for key in ('tone', 'damp_where'):
        if o.get(key):
            out.append((key, o[key]))
    if o.get('satmap'):
        out.append(('satmap', o['satmap']['t']))
    return out


def sample_maps(names, rng):
    out = {}
    for nm in names:
        if nm in ('slope',):
            v = rng.uniform(0, 85, NPTS)
        elif nm == 'aspect':
            v = rng.uniform(0, 360, NPTS)
        elif nm in ('northness', 'eastness', 'crest', 'crest_fine', 'crease', 'n20_x', 'n20_y'):
            v = rng.uniform(-1, 1, NPTS)
        elif nm in ('height', 'strata', 'src_strata'):
            v = rng.uniform(0, 3500, NPTS)
        elif nm.startswith('curv'):
            v = rng.uniform(-0.04, 0.04, NPTS)
        elif nm in ('deposit', 'talus', 'sand', 'water', 'wear', 'snowpack', 'lava'):
            v = rng.uniform(0, 1, NPTS) ** 2 * 8.0
        else:
            v = rng.uniform(0, 1, NPTS)
        out[nm] = v.astype(F).astype(np.float64)
    return out


def check_palette(name, pal, rng):
    from eidoblend.terrain.core import gpu as G
    exprs = expressions(pal)
    comp = XG.Compiler(read=lambda nm: f'@@{nm}@@', constants=pal.get('constants'), flat=True)
    glsl = [comp.expr(e) for _k, e in exprs]
    names = sorted(comp.names)
    maps = sample_maps(names, rng)
    slot = {nm: (k // 4, k % 4) for k, nm in enumerate(names)}
    ns = max(1, (len(names) + 3) // 4)
    cases = []
    for k, src in enumerate(glsl):
        for nm, (s, c) in slot.items():
            src = src.replace(f'@@{nm}@@', f'texelFetch(maps{s}, ivec2(p.x, 0), 0).{"xyzw"[c]}')
        cases.append(f'    case {k}: v = {src}; break;')
    head = ''.join(f'//! sampler maps{s}\n' for s in range(ns))
    kern = (head + '//! image outV r32f\n' + XG.HELPERS + '\nvoid main() {\n  ivec2 p = ivec2(gl_GlobalInvocationID.xy);\n'
            f'  if (p.x >= {NPTS} || p.y >= {len(glsl)}) return;\n  float v = 0.0;\n  switch (p.y) {{\n'
            + '\n'.join(cases) + '\n  }\n  imageStore(outV, p, vec4(v, 0.0, 0.0, 0.0));\n}\n')
    k = G.kernel(source=kern, name=f'expr_{name}')
    samp = {}
    for s in range(ns):
        a = np.zeros((1, NPTS, 4), F)
        for nm, (ss, c) in slot.items():
            if ss == s:
                a[0, :, c] = maps[nm]
        samp[f'maps{s}'] = G.texture(a)
    o = G.empty((len(glsl), NPTS), 1)
    G.run(k, None, samplers=samp, images={'outV': o})
    got = G.read(o)[..., 0].astype(np.float64)
    rows = []
    for k_, (label, e) in enumerate(exprs):
        want = np.broadcast_to(np.asarray(P.evaluate(e, maps, constants=pal.get('constants'), flat=True),
                                          np.float64), (NPTS,))
        d = np.abs(got[k_] - want)
        rows.append(dict(expr=label, max=float(d.max()), ok=bool(d.max() <= TOL), range=[float(want.min()),
                                                                                         float(want.max())]))
    return rows


def main():
    rng = np.random.default_rng(11)
    t0 = time.perf_counter()
    rep = {}
    ok = True
    for name in P.names():
        rows = check_palette(name, P.get(name), rng)
        rep[name] = rows
        bad = [r for r in rows if not r['ok']]
        ok &= not bad
        worst = max(r['max'] for r in rows)
        print(f"[test_expr] {name}: {len(rows)} expressions, worst |gpu - numpy| {worst:.2e}"
              + (f", FAIL: {[r['expr'] for r in bad]}" if bad else ''), flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'expr.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(ok=ok, tol=TOL, seconds=round(time.perf_counter() - t0, 1), palettes=rep), f, indent=1)
    print(f"[test_expr] {'PASS' if ok else 'FAIL'}", flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)
