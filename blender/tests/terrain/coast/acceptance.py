"""The coast package's acceptance in one file (design section 11, row 11: "exposure against a brute-force ray count;
the Dean profile"; done when sea_cliffs passes against Seven Sisters / Moher). System Python, no Blender: it reads
what the other scripts wrote and judges the generated fields with the judge (numbers only).

    python blender/tests/terrain/coast/acceptance.py --tag r18 [--seeds 1,2,3]

Reads out/coast/test_coast.json (plain twins), out/coast/gpu_tests.json (kernels on the GPU),
out/coast/gen/<tag>_<rock>_s<seed>.npz (gen.py) and writes out/coast/acceptance.json.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'coast')
sys.path.insert(0, os.path.join(TN, 'core'))
import plain_import  # noqa: E402

plain_import.install()
sys.path.insert(0, TN)

from judge import judge, refs  # noqa: E402

REFS = {'chalk': 'seven_sisters', 'layered': 'cliffs_of_moher'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True, help='the gen.py tag of both rocks, or chalk:<tag>,layered:<tag>')
    ap.add_argument('--seeds', default='1,2,3')
    a = ap.parse_args()
    tags = dict(kv.split(':', 1) for kv in a.tag.split(',')) if ':' in a.tag else {r: a.tag for r in REFS}
    res = dict(tags=tags)
    for name in ('test_coast', 'gpu_tests'):
        p = os.path.join(OUT, name + '.json')
        if os.path.exists(p):
            d = json.load(open(p, encoding='utf-8'))
            res[name] = {k: v for k, v in d.items() if isinstance(v, dict) and 'ok' in v}
    for rock, ref_name in REFS.items():
        ref = refs.load(ref_name)
        rows = {}
        for s in [int(v) for v in a.seeds.split(',')]:
            p = os.path.join(OUT, 'gen', f'{tags[rock]}_{rock}_s{s}.npz')
            if not os.path.exists(p):
                continue
            v = judge(p, ref, label=f'{tags[rock]}_{rock}_s{s}')
            dv = v.to_dict()
            judged = [r for r in dv['rows'] if r.get('passed') is not None]
            num = dict(dv['numbers'].get('generated') or {}, **(dv['numbers'].get('generated_family') or {}))
            rows[f'seed{s}'] = dict(passed=v.passed, failures=v.failures,
                                    bands=f"{sum(1 for r in judged if r['passed'])}/{len(judged)}",
                                    numbers={k: num.get(k) for k in (
                                        'relief_m', 'hypsometric_integral', 'slope_p50', 'slope_p90', 'slope_p99',
                                        'clifftop_p50_m', 'clifftop_p90_m', 'cliff_face_p90', 'depression_area_frac')})
            print(v.table(), flush=True)
        res[rock] = dict(reference=ref_name, seeds=rows,
                         passed=sum(r['passed'] for r in rows.values()), of=len(rows))
    # the control for Moher's 30 m radar reference: an ideal coast (a straight vertical 110 m cliff, a plateau
    # dipping inland 2 %) through the same judge. What it fails, no sharp cliff can pass against that reference
    import math
    import numpy as np
    n, cell = 1024, 6000.0 / 1024
    X, Y = np.meshgrid((np.arange(n) + 0.5) * cell, (np.arange(n) + 0.5) * cell)
    nrm = (-math.sin(math.radians(60.0)), math.cos(math.radians(60.0)))
    d = (X - 3000.0) * nrm[0] + (Y - 3000.0) * nrm[1] - 200.0
    step = np.where(d > 0, -10.0, 110.0 + 0.02 * np.minimum(d, 0.0))
    v = judge(dict(h=step, cell=cell, sea_level=0.0), refs.load('cliffs_of_moher'), label='ideal_vertical_step')
    dv = v.to_dict()
    res['moher_control_ideal_step'] = dict(
        failures=v.failures, rows={r['metric']: dict(generated=r.get('gen'), band=r.get('band'),
                                                     passed=r.get('passed'))
                                   for r in dv['rows'] if r.get('metric') in ('spectrum_slope', 'slope_p99',
                                                                               'cliff_face_p90', 'slope_p90')})
    print(v.table(), flush=True)
    with open(os.path.join(OUT, 'acceptance.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps({k: (v if not isinstance(v, dict) or 'seeds' not in v else
                          {kk: vv for kk, vv in v.items() if kk != 'seeds'}) for k, v in res.items()
                      if k not in ('test_coast', 'gpu_tests')}, indent=1))


if __name__ == '__main__':
    main()
