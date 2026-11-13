"""The judge's one command split in two, so its Blender half can run inside a chain that already holds a GPU slot
(judge/run.py would queue for a second slot):

    python judge_sheet.py job --recipe dunes --reference namib_star_dunes --out <dir> [--textured] [--seeds 1]
           [--params '{"winds": [[282, 1.0], [102, 0.7], [192, 0.5]], "sand_m": 35}']
        writes <dir>/job.json exactly as judge/run.py does (--params: the recipe's knobs, as its --param); then, in
        the slot (chain_review_judge.sh runs it there):
    bash run_blender.sh <worktree>/blender/tests/terrain/judge/blender_job.py --job <dir>/job.json
    python judge_sheet.py sheet --out <dir>
        judge/run.py's own second half on that job's results: every verdict (judge.judge), verdicts.json, the
        compare sheet compare_<reference>.png, and each verdict's table on stdout.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'core'))
sys.path.insert(0, TN)
import plain_import  # noqa: E402
plain_import.install()

from judge import judge, refs  # noqa: E402
from judge import sheet as S  # noqa: E402


def make_job(a):
    ref = refs.load(a.reference)
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    items = [dict(label=f'{a.recipe}_seed{s}', recipe=a.recipe, seed=int(s), quality='film',
                  params=json.loads(a.params or '{}'), textured=a.textured) for s in a.seeds.split(',') if s]
    job = dict(reference=ref.name, out_dir=out, cache_root=os.path.join(out, '_sky_cache'), samples=16, items=items)
    with open(os.path.join(out, 'job.json'), 'w', encoding='utf-8') as f:
        json.dump(job, f, indent=1)
    print(os.path.join(out, 'job.json'))


def make_sheet(a):
    out = os.path.abspath(a.out)
    job = json.load(open(os.path.join(out, 'job.json'), encoding='utf-8'))
    ref = refs.load(job['reference'])
    res_path = os.path.join(out, 'blender_job_result.json')
    bres = json.load(open(res_path, encoding='utf-8')) if os.path.exists(res_path) else {}
    verdicts = []
    for it in job['items']:
        field = os.path.join(out, it['label'] + '.npz')
        if not os.path.exists(field):
            print(f"[judge] {it['label']}: no field ({bres.get(it['label'], {}).get('error', 'see blender.log')})")
            continue
        v = judge(field, ref, label=it['label'])
        for tag, err in (bres.get(it['label'], {}).get('errors') or {}).items():
            v.notes.append(f'{tag} views not rendered: {err}')
        verdicts.append(v)
        print(v.table(), flush=True)
    with open(os.path.join(out, 'verdicts.json'), 'w', encoding='utf-8') as f:
        json.dump([v.to_dict() for v in verdicts], f, indent=1)
    if verdicts:
        png = S.compose(os.path.join(out, f'compare_{ref.name}.png'), ref, verdicts, out,
                        title=f"dunes vs {ref.title}: {sum(v.passed for v in verdicts)} of {len(verdicts)} pass")
        print(png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('what', choices=('job', 'sheet'))
    ap.add_argument('--recipe', default='dunes')
    ap.add_argument('--reference', default='namib_star_dunes')
    ap.add_argument('--seeds', default='1')
    ap.add_argument('--textured', action='store_true')
    ap.add_argument('--params', default='')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    make_job(a) if a.what == 'job' else make_sheet(a)


if __name__ == '__main__':
    main()
