"""Package 9's acceptance in one file: the final verdict of each recipe on each seed (vc.py's runs), their level
seams and run times, and the plain-Python tests (test_profiles.py, test_aging.py).

    python blender/tests/terrain/volcanoes_craters/acceptance.py --tags stratovolcano=r11 caldera=r8 ...

Writes blender/tests/terrain/out/volcanoes_craters/acceptance.json and prints the table.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
GEN = os.path.join(TN, 'out', 'volcanoes_craters', 'gen')
OUT = os.path.join(TN, 'out', 'volcanoes_craters', 'acceptance.json')


def run_test(name):
    p = subprocess.run([sys.executable, os.path.join(HERE, name)], cwd=HERE, capture_output=True, text=True,
                       timeout=900)
    lines = [ln for ln in p.stdout.splitlines() if ln.startswith(('PASS', 'FAIL', 'INFO')) or 'checks pass' in ln]
    return dict(script=name, exit=p.returncode, summary=lines[-1] if lines else p.stderr[-300:],
                failures=[ln for ln in lines if ln.startswith('FAIL')])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tags', nargs='+', required=True, help='recipe=tag pairs')
    a = ap.parse_args()
    out = dict(recipes={}, tests=[])
    for pair in a.tags:
        recipe, tag = pair.split('=')
        rows = []
        for vp in sorted(glob.glob(os.path.join(GEN, f'{tag}_{recipe}_s*_verdict.json'))):
            v = json.load(open(vp, encoding='utf-8'))
            base = vp[:-len('_verdict.json')]
            rec = json.load(open(base + '_record.json', encoding='utf-8'))
            seams = json.load(open(base + '_seams.json', encoding='utf-8')) if os.path.exists(base + '_seams.json') \
                else []
            judged = [r for r in v['rows'] if r.get('passed') is not None]
            rows.append(dict(run=os.path.basename(base), reference=v['reference'], passed=v['passed'],
                             bands=f"{sum(1 for r in judged if r['passed'])}/{len(judged)}",
                             failures=v['failures'], seconds=rec.get('seconds'),
                             seams=[dict(cell=s['child_cell_m'], dh=round(s['edge_max_dh_m'], 3),
                                         jump=round(s['edge_slope_jump_deg'], 2)) for s in seams],
                             numbers={r['metric']: [round(r['gen'], 4) if isinstance(r['gen'], float) else r['gen'],
                                                    round(r['ref'], 4) if isinstance(r['ref'], float) else r['ref'],
                                                    r['band']] for r in judged}))
        out['recipes'][recipe] = rows
    for t in ('test_profiles.py', 'test_aging.py'):
        out['tests'].append(run_test(t))
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    for recipe, rows in out['recipes'].items():
        for r in rows:
            print(f"{r['run']}: {'PASS' if r['passed'] else 'FAIL'} {r['bands']} vs {r['reference']}, {r['seconds']} s"
                  + (f"; failures: {r['failures']}" if r['failures'] else ''))
    for t in out['tests']:
        print(f"{t['script']}: {t['summary']}")
    print(OUT)


if __name__ == '__main__':
    main()
