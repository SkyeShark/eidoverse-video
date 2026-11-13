"""The layered-rock package's acceptance summary (design section 11, row 10), in plain Python:

    python blender/tests/terrain/layered_rock/acceptance.py [--gen <dir>] [--final <tag>=<recipe> ...]

Reads out/layered_rock/strata_tests.json (the numpy-twin tests: composite threshold, tables, K(z) lookup, meander
geometry, talus, weathering), out/layered_rock/kernel_tests.json (the GPU kernels against their twins) and, for each
final generated terrain (<gen>/<tag>_verdict_<reference>.json and _crop_verdict_*.json, written by judge_fields.py;
<gen> defaults to out/layered_rock/gen), the judge's bands; writes out/layered_rock/acceptance.json and prints one
line per check.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'layered_rock'))
GEN = os.path.join(OUT, 'gen')


def load(path):
    return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else None


def main():
    global GEN
    a = sys.argv[1:]
    finals = {}
    for k, v in zip(a[::2], a[1::2]):
        if k == '--final':
            tag, recipe = v.split('=', 1)
            finals[tag] = recipe
        elif k == '--gen':
            GEN = v
    rows = []
    for name, path in (('twins', os.path.join(OUT, 'strata_tests.json')),
                       ('gpu kernels', os.path.join(OUT, 'kernel_tests.json'))):
        r = load(path)
        if r is None:
            rows.append(dict(check=f'{name}: {os.path.basename(path)}', passed=False, evidence='not run'))
            continue
        for k, v in r.items():
            if k.startswith('_') or not isinstance(v, dict):
                continue
            rows.append(dict(check=f'{name}: {k}', passed=bool(v.get('ok')), evidence=json.dumps(v.get('detail'))[:300]))
    for tag, recipe in finals.items():
        for path in sorted(glob.glob(os.path.join(GEN, f'{tag}_verdict_*.json')) +
                           glob.glob(os.path.join(GEN, f'{tag}_crop_verdict_*.json'))):
            v = load(path)
            v = v[0] if isinstance(v, list) else v
            judged = [r for r in v['rows'] if r.get('passed') is not None]
            fails = [f"{r['metric']} {r['gen']:.3g} (ref {r['ref']:.3g}, band {r['band']})" for r in judged
                     if not r['passed'] and isinstance(r.get('gen'), (int, float))]
            rows.append(dict(check=f"{recipe} ({tag}) vs {v.get('reference')}" + (' (crop)' if '_crop_' in path
                                                                                     else ''),
                             passed=not fails, evidence=f"{len(judged) - len(fails)}/{len(judged)} bands"
                                                         + (': fails ' + '; '.join(fails) if fails else '')))
    with open(os.path.join(OUT, 'acceptance.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=1)
    for r in rows:
        print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['check']}: {r['evidence'][:200]}")


main()
