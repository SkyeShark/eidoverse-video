"""The glacial package's acceptance summary (design section 11, row 7), from the tests' and the judge's outputs:

    python blender/tests/terrain/glacial/acceptance.py [--lauterbrunnen TAG ...] [--yosemite TAG ...]

  - ice-flux mass balance closes            out/glacial/twin_tests.json, gpu_tests.json
  - jump flood against a brute-force twin   twin_tests.json (64^2), gpu_tests.json (128^2)
  - U-shape fit on a synthetic valley        gpu_tests.json
  - every kernel against its twin            gpu_tests.json (parity)
  - alpine_valley passes against Lauterbrunnen and Yosemite: the verdicts of the given gen.py tags
    (out/glacial/gen/<tag>_verdict.json, written by judge_fields.py)
Writes out/glacial/acceptance.json and prints it.
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'glacial')


def load(name):
    p = os.path.join(OUT, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def rows(res, *keys):
    out = []
    for k, v in (res or {}).get('results', {}).items():
        if any(s in k for s in keys):
            out.append(dict(test=k, ok=v['ok'], detail=v.get('detail')))
    return out


def verdicts(tags):
    out = []
    for t in tags:
        p = os.path.join(OUT, 'gen', t + '_verdict.json')
        if not os.path.exists(p):
            out.append(dict(tag=t, ok=False, detail='no verdict'))
            continue
        v = json.load(open(p, encoding='utf-8'))
        out.append(dict(tag=t, reference=v['reference'], ok=bool(v['passed']), failures=v['failures'],
                        bands=f"{sum(1 for r in v['rows'] if r['passed'])}/"
                              f"{sum(1 for r in v['rows'] if r['passed'] is not None)}"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lauterbrunnen', nargs='*', default=[])
    ap.add_argument('--yosemite', nargs='*', default=[])
    a = ap.parse_args()
    tw, gp = load('twin_tests.json'), load('gpu_tests.json')
    checks = {
        'ice-flux mass balance closes': rows(tw, 'mass balance') + rows(gp, 'mass balance'),
        'jump flood against a brute-force twin': rows(tw, 'jump flood') + rows(gp, 'brute force'),
        'U-shape fit on a synthetic valley': rows(gp, 'synthetic valley'),
        'every kernel against its twin': rows(gp, 'parity'),
        'alpine_valley passes against Lauterbrunnen': verdicts(a.lauterbrunnen),
        'alpine_valley passes against Yosemite Valley': verdicts(a.yosemite),
    }
    summary = {k: dict(passed=bool(v) and all(r['ok'] for r in v), rows=v) for k, v in checks.items()}
    with open(os.path.join(OUT, 'acceptance.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=1, default=str)
    for k, v in summary.items():
        print(f"{'PASS' if v['passed'] else 'FAIL'}  {k}")
        for r in v['rows']:
            print(f"      {'ok ' if r['ok'] else 'NO '} {r.get('test') or r.get('tag')}: "
                  f"{r.get('detail') or r.get('bands') or ''} {r.get('failures') or ''}")


main()
