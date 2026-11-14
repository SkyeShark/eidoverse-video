"""The judge in one command (DESIGN.md section 10; "a recipe agent can run one command and get numbers, bands and a
sheet"). From the worktree root, in system Python (it starts Blender itself, through a GPU slot):

    python blender/tests/terrain/judge/run.py --recipe alpine_valley [--reference lauterbrunnen]
           [--seeds 1,2] [--quality film] [--param ela_m=2300 --param relief_m=2800] [--textured]
    python blender/tests/terrain/judge/run.py --field my_terrain.npz --reference mount_fuji
    python blender/tests/terrain/judge/run.py --triage volcano --reference mount_fuji      # Ekigar's triage

    --recipe     generated in Blender at the reference's extent (size = the reference tile), one row per seed; the
                 reference defaults to the recipe's first in refs.RECIPE_REFERENCES (real_place: its dem knob, and
                 --reference sets the dem; its field is the reference's own data, so no source chain is applied)
    --textured   also the textured aerial and eye of the built terrain (its palette; item 6)
    --field      an .npz of a heightfield (h, cell; row 0 = south, metres; optional water, sea_level, frame,
                 context_h + context_cell), or a Terrain.save() file; repeatable
    --triage     a subject of the triage cache (triage/scenes.py), Ekigar's field in metres
    --no-render  numbers and bands only (no Blender): the sheet's view cells say "not rendered"
    --out        default blender/tests/terrain/out/judge/<recipe or reference>/

Writes <out>/verdicts.json (every number, band and verdict), <out>/compare_<reference>.png (the sheet), the renders,
and prints each verdict's table. Exit code 0 when every row passes, 1 otherwise, 2 on an error.

The GPU: Blender here is a GPU job (DESIGN.md section 11). With EIDO_GPU_WRAP set (blender/tests/_where.py) it
queues through it, retried every 60 s for up to 60 minutes while the queue says every slot is busy (exit 75); without
it, Blender runs directly through this checkout's run_blender.sh.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
WORKTREE = os.path.normpath(os.path.join(TN, '..', '..', '..'))
sys.path.insert(0, TN)
sys.path.insert(0, os.path.dirname(TN))                       # blender/tests: _where

import numpy as np  # noqa: E402

import _where  # noqa: E402
from judge import judge, refs  # noqa: E402
from judge import sheet as S  # noqa: E402

def run_blender(script, args, log_path, timeout_min=60):
    """Run a Blender script through _where.blender_cmd: queued by $EIDO_GPU_WRAP when it is set (retrying while the
    queue says every slot is busy, exit 75), else directly. -> (rc, 'EIDO_GPU_WRAP' | 'direct' | None)"""
    env = dict(os.environ, HEAVY_VRAM_GB='4', GPU_MEMCAP_GB='12')       # the job's VRAM estimate and RAM cap
    cmd = _where.blender_cmd(script, *args)
    if os.environ.get('EIDO_GPU_WRAP'):
        t_end = time.time() + 60 * timeout_min
        while True:
            with open(log_path, 'w', encoding='utf-8') as log:
                rc = subprocess.call(cmd, cwd=WORKTREE, env=env, stdout=log, stderr=subprocess.STDOUT)
            if rc != 75:
                return rc, 'EIDO_GPU_WRAP'
            if time.time() > t_end:
                return 75, None
            print('[judge] every GPU slot is busy: waiting 60 s', flush=True)
            time.sleep(60)
    with open(log_path, 'w', encoding='utf-8') as log:
        rc = subprocess.call(cmd, cwd=WORKTREE, stdout=log, stderr=subprocess.STDOUT)
    return rc, 'direct'


def triage_field(subject, out_dir):
    sys.path.insert(0, os.path.join(TN, 'triage'))
    import scenes
    d = np.load(scenes.cache_path(subject), allow_pickle=False)
    m = json.loads(str(d['meta']))
    z = d['height'].astype(np.float64) * m['vs'] * m['W']
    path = os.path.join(out_dir, f'ekigar_{subject}.npz')
    np.savez(path, h=z.astype(np.float32), cell=m['W'] / z.shape[0], frame='south_up')
    return path


def parse_param(s):
    k, v = s.split('=', 1)
    try:
        v = json.loads(v)
    except ValueError:
        pass
    return k, v


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--recipe')
    ap.add_argument('--reference')
    ap.add_argument('--seeds', default='1')
    ap.add_argument('--quality', default='film')
    ap.add_argument('--param', action='append', default=[])
    ap.add_argument('--textured', action='store_true')
    ap.add_argument('--field', action='append', default=[])
    ap.add_argument('--triage', action='append', default=[])
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--out')
    a = ap.parse_args()
    if not (a.recipe or a.field or a.triage):
        ap.error('give --recipe, --field or --triage')
    params = dict(parse_param(p) for p in a.param)
    if a.recipe == 'real_place':                  # its DEM is the reference: either names the other
        if a.reference and 'dem' not in params:
            params['dem'] = a.reference
        a.reference = a.reference or params.get('dem')
    ref_name = a.reference or (refs.RECIPE_REFERENCES.get(a.recipe, [None])[0] if a.recipe else None)
    if ref_name is None:
        ap.error('--reference is needed (no default reference for this recipe)')
    ref = refs.load(ref_name)
    out = os.path.abspath(a.out or os.path.join(TN, 'out', 'judge', a.recipe or ref_name))
    os.makedirs(out, exist_ok=True)
    items = []
    if a.recipe:
        for s in [int(v) for v in a.seeds.split(',') if v]:
            items.append(dict(label=f'{a.recipe}_seed{s}', recipe=a.recipe, seed=s, quality=a.quality, params=params,
                              textured=a.textured))
    for p in a.field:
        items.append(dict(label=os.path.splitext(os.path.basename(p))[0], field=os.path.abspath(p)))
    for t in a.triage:
        items.append(dict(label=f'ekigar_{t}', field=triage_field(t, out)))
    log = print
    t0 = time.time()
    bres = {}
    if a.recipe or not a.no_render:
        if a.no_render and a.recipe:
            log('[judge] --no-render with --recipe: the terrain is still generated in Blender (GPU kernels)')
        job = dict(reference=ref_name, out_dir=out, cache_root=os.path.join(out, '_sky_cache'), samples=a.samples,
                   items=items)
        job_path = os.path.join(out, 'job.json')
        with open(job_path, 'w', encoding='utf-8') as f:
            json.dump(job, f, indent=1)
        log(f'[judge] Blender: {len(items)} item(s) against {ref_name} (log {out}/blender.log)')
        rc, slot = run_blender(os.path.join(HERE, 'blender_job.py'), ['--job', job_path], os.path.join(out, 'blender.log'))
        log(f'[judge] Blender finished rc={rc} ({slot}) in {time.time() - t0:.0f}s')
        res_path = os.path.join(out, 'blender_job_result.json')
        bres = json.load(open(res_path, encoding='utf-8')) if os.path.exists(res_path) else {}
        for it in items:
            r = bres.get(it['label'], {})
            if not r.get('ok', False):
                log(f"[judge] {it['label']}: Blender side failed: {r.get('error', 'no result (see blender.log)')}")
            if it.get('recipe'):
                it['field'] = os.path.join(out, it['label'] + '.npz')
    verdicts = []
    for it in items:
        if not it.get('field') or not os.path.exists(it['field']):
            log(f"[judge] {it['label']}: no field to judge")
            continue
        v = judge(it['field'], ref, label=it['label'],
                  source_chain=not (a.recipe == 'real_place'))
        eye = bres.get(it['label'], {}).get('eye') if (a.recipe or not a.no_render) else None
        if eye and eye.get('best_effort'):
            v.notes.append(f"eye level: no spot sees the {eye.get('kind')} view's target clearly (best clearance "
                           f"{eye.get('clearance_m', 0):.0f} m on a {eye.get('footing_deg', 0):.0f} degree footing): "
                           f"a best-effort view")
        for tag, err in (bres.get(it['label'], {}).get('errors') or {}).items():
            v.notes.append(f'{tag} views not rendered: {err}')
        verdicts.append(v)
        print(v.table(), flush=True)
    with open(os.path.join(out, 'verdicts.json'), 'w', encoding='utf-8') as f:
        json.dump([v.to_dict() for v in verdicts], f, indent=1)
    if verdicts:
        png = S.compose(os.path.join(out, f'compare_{ref_name}.png'), ref, verdicts, out,
                        title=f"{a.recipe or 'given fields'} vs {ref.title}: "
                              f"{sum(v.passed for v in verdicts)} of {len(verdicts)} pass")
        log(f'[judge] sheet: {png}')
    log(f'[judge] verdicts: {os.path.join(out, "verdicts.json")} ({time.time() - t0:.0f}s)')
    sys.exit(0 if verdicts and all(v.passed for v in verdicts) else 1)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:                                                   # noqa: BLE001
        import traceback
        traceback.print_exc()
        sys.exit(2)
