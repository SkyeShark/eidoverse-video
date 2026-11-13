"""The glacial package's acceptance summary (design section 11, row 7), from the tests' and the judge's outputs:

    python blender/tests/terrain/glacial/acceptance.py [--gen-dir DIR] [--lauterbrunnen TAG ...] [--yosemite TAG ...]

  - ice-flux mass balance closes            out/glacial/twin_tests.json, gpu_tests.json
  - jump flood against a brute-force twin   twin_tests.json (64^2), gpu_tests.json (128^2)
  - U-shape fit on a synthetic valley        gpu_tests.json: the carved trunk a box trough, tributaries hanging
  - the trough's walls and the trunk river   twin_tests.json: the recipe's cross-section (cliffs at wall_deg over a
                                            level floor), one trunk river pinned down the valley's axis
  - the shoulders, lips and trough heads     twin_tests.json: the shoulder cut (no rim, no flat strip beyond a lip),
                                            lip_open (rims on the lip band come down), the head taper (and the
                                            recipe's carve with it: no seed of no size out-ranking the troughs)
  - the walls at every level's resolution    twin_tests.json: sharpen_walls puts back what the upsampling smoothed
  - every kernel against its twin            gpu_tests.json (parity)
  - alpine_valley passes against Lauterbrunnen and Yosemite: the verdicts of the given gen.py tags
    (<gen-dir>/<tag>_verdict.json, written by judge_fields.py; gen-dir default out/glacial/gen)
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


def verdicts(tags, gen_dir):
    out = []
    for t in tags:
        p = os.path.join(gen_dir, t + '_verdict.json')
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
    ap.add_argument('--gen-dir', default=os.path.join(OUT, 'gen'))
    ap.add_argument('--lauterbrunnen', nargs='*', default=[])
    ap.add_argument('--yosemite', nargs='*', default=[])
    a = ap.parse_args()
    tw, gp = load('twin_tests.json'), load('gpu_tests.json')
    checks = {
        'ice-flux mass balance closes': rows(tw, 'mass balance') + rows(gp, 'mass balance'),
        'jump flood against a brute-force twin': rows(tw, 'jump flood') + rows(gp, 'brute force'),
        'U-shape fit on a synthetic valley': rows(gp, 'synthetic valley'),
        "the trough's walls and the trunk river": rows(tw, 'trunk wall', 'trunk river', 'profile continuous',
                                                        'never falls'),
        'the shoulders, lips and trough heads': rows(tw, 'the shoulder cut', 'lip_open', 'head_distance',
                                                     "the recipe's carve with its head taper"),
        "the walls at every level's resolution": rows(tw, 'sharpen_walls'),
        'every kernel against its twin': rows(gp, 'parity'),
        'alpine_valley passes against Lauterbrunnen': verdicts(a.lauterbrunnen, a.gen_dir),
        'alpine_valley passes against Yosemite Valley': verdicts(a.yosemite, a.gen_dir),
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
