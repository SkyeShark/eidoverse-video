"""Parity harness: the same graphs evaluated by Ekigar's own JS (through tsl_cpu_shim.mjs, float64, CPU) and by the
Python port, compared channel by channel.

    probes = [gen('fbm'), filt('blur', {'radius': 12}, tag='r12'), ...]
    results = run(probes, grid=48)            # runs the deno oracle once for all probes, then the port
    report(results)                           # PASS/FAIL lines

Both sides sample p = uv * tile at texel centres with GPU 2x2 'coarse' quad derivatives, so they see the same
discretisation. The comparison is per channel: the worst error after excluding the 0.3% most-different texels
(isolated discontinuity flips, where a floor() or a step lands on the other side of an f64 rounding) must be within
1e-7 of the channel's scale, and the median within 1e-9.
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

import _ekigar_load

HERE = _ekigar_load.HERE
DENO_ARGS = ['deno', 'run', '--no-config', '--no-lock', '-A', f'--import-map={os.path.join(HERE, "import_map.json")}',
             os.path.join(HERE, 'oracle_dump.mjs')]

_SEQ = [0]


def _nid():
    _SEQ[0] += 1
    return f'n{_SEQ[0]}'


def node(op, params=None, **kw):
    d = {'id': _nid(), 'op': op, 'params': dict(params or {})}
    d.update(kw)
    return d


def edge(a, b, port='in', from_port='out'):
    return {'from': {'node': a['id'], 'port': from_port}, 'to': {'node': b['id'], 'port': port}}


def probe(name, nodes, edges, target, port='out', **kw):
    d = {'name': name, 'graph': {'nodes': nodes, 'edges': edges}, 'target': target['id'], 'port': port}
    d.update(kw)
    return d


def safe(name):
    return ''.join(c if c.isalnum() or c in '-_' else '_' for c in name)


def gen(op, over=None, tag='', port='out'):
    n = node(op, over)
    return probe(safe(f'{op}{"_" + tag if tag else ""}{"_" + port if port != "out" else ""}'), [n], [], n, port)


def base_terrain():
    """fbm -> roughen: the varied terrain Ekigar's own smoke test feeds every filter."""
    a = node('fbm', {'frequency': 4, 'amplitude': 0.9})
    b = node('roughen', {'frequency': 16, 'amplitude': 0.04})
    return a, b, [edge(a, b)]


def filt(op, over=None, tag='', port='out'):
    a, b, es = base_terrain()
    n = node(op, over)
    return probe(safe(f'{op}{"_" + tag if tag else ""}{"_" + port if port != "out" else ""}'), [a, b, n],
                 es + [edge(b, n)], n, port)


def run_oracle(probes, grid, out_dir, dmode='coarse'):
    spec = {'probes': [dict(p, grid=[grid, grid], dmode=dmode, resolution=grid) for p in probes]}
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    sp = os.path.join(out_dir, 'spec.json')
    with open(sp, 'w') as f:
        json.dump(spec, f)
    r = subprocess.run(DENO_ARGS + [sp, out_dir, _ekigar_load.EKIGAR_ROOT], capture_output=True, text=True,
                       timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(f'oracle failed: {r.stderr[-2000:]}')
    return r.stdout


def load_oracle(out_dir, name):
    meta = json.load(open(os.path.join(out_dir, f'{name}.json')))
    if meta.get('error'):
        return meta, None
    gw, gh = meta['grid']
    a = np.fromfile(os.path.join(out_dir, f'{name}.bin'), dtype=np.float64)
    n = gw * gh
    ch = {c: a[i * n:(i + 1) * n].reshape(gh, gw) for i, c in enumerate(meta['channels'])}
    return meta, ch


def evaluate_py(ek, pr, grid, dmode='coarse'):
    g = ek.model.from_json(pr['graph'])
    res = ek.compile.evaluate_graph(g, pr['target'], port=pr.get('port', 'out'), resolution=grid,
                                    tile=pr.get('tile', (1.0, 1.0)), derivatives=dmode)
    ch = {'x': res['field'][0], 'y': res['field'][1], 'z': res['field'][2], 'w': res['field'][3]}
    for k, v in res['outs'].items():
        ch[f'out:{k}'] = v
    return res, ch


def compare(a, b):
    """(ok, worst_after_trim, median, max, scale) for two channels."""
    bad = ~np.isfinite(a) | ~np.isfinite(b)
    if bad.any():
        same_bad = (~np.isfinite(a) == ~np.isfinite(b)).all()
        if not same_bad:
            return False, float('inf'), float('inf'), float('inf'), 0.0
        a = np.where(bad, 0.0, a)
        b = np.where(bad, 0.0, b)
    d = np.abs(a - b)
    scale = max(1.0, float(np.abs(b).max()))
    trimmed = float(np.quantile(d, 0.997))
    med = float(np.median(d))
    ok = trimmed <= 1e-7 * scale and med <= 1e-9 * scale
    return ok, trimmed, med, float(d.max()), scale


def run(probes, grid=48, out_dir=None, dmode='coarse', verbose=True):
    ek = _ekigar_load.load()
    import importlib
    for m in ('model', 'compile'):
        importlib.import_module(f'{ek.__name__}.{m}')
    ek.model = sys.modules[f'{ek.__name__}.model']
    ek.compile = sys.modules[f'{ek.__name__}.compile']
    out_dir = out_dir or os.path.join(_ekigar_load.OUT, 'oracle')
    log = run_oracle(probes, grid, out_dir, dmode)
    if verbose:
        print(log.strip().splitlines()[-1] if log.strip() else 'oracle: (no output)')
    results = []
    for pr in probes:
        meta, js = load_oracle(out_dir, pr['name'])
        if js is None:
            results.append({'name': pr['name'], 'ok': False, 'why': 'oracle error: ' + meta['error'][:300]})
            continue
        try:
            res, py = evaluate_py(ek, pr, grid, dmode)
        except Exception:  # noqa: BLE001  (reported as a FAIL line)
            import traceback
            results.append({'name': pr['name'], 'ok': False, 'why': 'python error: ' + traceback.format_exc()[-800:]})
            continue
        chans = []
        ok_all = True
        for c, arr in js.items():
            if c not in py:
                chans.append((c, False, 'missing in port'))
                ok_all = False
                continue
            ok, tr, med, mx, sc = compare(py[c], arr)
            ok_all &= ok
            chans.append((c, ok, f'p99.7 {tr:.1e} med {med:.1e} max {mx:.1e} (scale {sc:.2g})', mx / sc))
        extra = [c for c in py if c not in js]
        if extra:
            chans.append(('extra', False, f'port produces channels the oracle does not: {extra}'))
            ok_all = False
        warn_js = meta.get('warnings') or []
        warn_py = res['warnings']
        if warn_js != warn_py:
            chans.append(('warnings', False, f'js {warn_js} vs py {warn_py}'))
            ok_all = False
        results.append({'name': pr['name'], 'ok': ok_all, 'channels': chans,
                        'range': (float(js['x'].min()), float(js['x'].max()))})
    return results


def report(results, label='parity'):
    n_ok = 0
    overall = 0.0
    for r in results:
        if r['ok']:
            n_ok += 1
            worst = max((c[3] for c in r['channels'] if len(c) > 3), default=0.0)
            overall = max(overall, worst)
            print(f"PASS {label} {r['name']:<44} h {r['range'][0]:.3f}..{r['range'][1]:.3f}  max diff {worst:.1e}")
        else:
            print(f"FAIL {label} {r['name']}: " + (r.get('why') or '; '.join(f'{c[0]}: {c[2]}' for c in
                                                                         r['channels'] if not c[1])))
    print(f'{label}: {n_ok}/{len(results)} probes match Ekigar; worst difference over every channel '
          f'{overall:.1e} of the channel scale')
    return n_ok == len(results)
