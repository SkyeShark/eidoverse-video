"""The terrains a judge render was made on, made again by the Blender edition (PORT_PLAN.md 8.2 row P18): the look
package renders the port on the very ground Blender's final check rendered, and a later round may have saved over the
judge's terrains or removed a view's snapshot since. Blender's terrain is deterministic on one machine (its reruns are
bit-identical), so the same code at the same settings makes the same terrain again.

    EIDO_BLENDER_EDITION=<an export of the blender branch at the commit of the renders' code> bash <its run_blender.sh> \\
        eidoverse/terrain/tests/surface_look/blender_terrains.py -- --review <the final check's out/surfacing/review>
        --views <recipe/view,...> --out <folder> [--ref final2] [--plan <views.json>] [--check <a saved terrain>]
    (a Blender job, behind $EIDO_GPU_WRAP like every Blender run: 4 GB VRAM, 12 GB RAM)

Per view, the record of its --ref render (<review>/<recipe>/<recipe>_<ref>_record.json) says how its terrain was made:
a view whose record has no focus took the judge's terrain (surfacing_judge/make_terrains.py: api.generate(recipe,
size=its reference's extent, seed=1, params=views.json's, quality='film', focus=None)), saved here as <recipe>.npz;
a view with a focus took one generated at that focus (shots.terrain_for: the same with focus=the record's), saved as
<recipe>_<view>_j.npz. The terrain cache is not used (cache=False), so nothing of another round's is read or written.
The levels are checked against the record's (window and cell of every level). --check <a saved terrain of the
judge, made by the renders' code and never saved over>: that recipe is made again first and compared array by array
(the proof that this export makes the renders' terrains). Writes <out>/<name>.npz and .json (Terrain.save), and
<out>/blender_terrains.json (per terrain: the levels' agreement with the record, seconds, the check).
"""
import json
import os
import re
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TESTS, 'parity'))
import _blender as B  # noqa: E402

_LEVEL = re.compile(r'Level\((\d+) (\w+) ([-\d.e+]+) m @ ([-\d.e+]+) m x(\d+), x0 ([-\d.e+]+) y0 ([-\d.e+]+)')


def levels_of(strings):
    out = []
    for s in strings or []:
        m = _LEVEL.match(str(s))
        if m:
            i, role, side, cell, n, x0, y0 = m.groups()
            out.append(dict(role=role, side=float(side), cell=float(cell), n=int(n), x0=float(x0), y0=float(y0)))
    return out


def same_levels(t, strings, tol=0.01):
    want = levels_of(strings)
    have = [dict(role=lv.role, side=float(lv.side), cell=float(lv.cell), n=int(lv.n), x0=float(lv.x0), y0=float(lv.y0))
            for lv in t.levels]
    if len(want) != len(have):
        return False, f'{len(have)} levels, the record {len(want)}'
    for a, b in zip(have, want):
        if a['role'] != b['role'] or a['n'] != b['n'] or any(abs(a[k] - b[k]) > tol * max(1.0, b['cell'])
                                                             for k in ('side', 'cell', 'x0', 'y0')):
            return False, f'level {a} against the record\'s {b}'
    return True, 'every level\'s window and cell as the record\'s'


def compare_saves(a, b):
    """Two Terrain.save files array by array: (equal, the first difference or None, arrays compared)."""
    import numpy as np
    with np.load(a) as za, np.load(b) as zb:
        ka, kb = sorted(za.files), sorted(zb.files)
        if ka != kb:
            return False, f'arrays differ: {sorted(set(ka) ^ set(kb))[:6]}', 0
        for k in ka:
            x, y = za[k], zb[k]
            if x.shape != y.shape or x.dtype != y.dtype or not np.array_equal(x, y):
                d = float(np.abs(x.astype(np.float64) - y.astype(np.float64)).max()) if x.shape == y.shape else None
                return False, f'{k}: max |difference| {d}', len(ka)
        return True, None, len(ka)


def main():
    a = B.script_args()

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    review, out, ref = opt('--review'), opt('--out'), opt('--ref', 'final2')
    root = B.import_blender_terrain()
    tn = os.path.join(root, 'blender', 'tests', 'terrain')
    if tn not in sys.path:
        sys.path.insert(0, tn)
    from judge import refs
    from eidoblend.terrain import api as A
    plan_path = opt('--plan', os.path.join(tn, 'surfacing_judge', 'views.json'))
    with open(plan_path, encoding='utf-8') as f:
        plan = json.load(f)
    os.makedirs(out, exist_ok=True)
    rep_path = os.path.join(out, 'blender_terrains.json')
    rep = json.load(open(rep_path, encoding='utf-8')) if os.path.exists(rep_path) else {}
    rep['edition'] = dict(commit=B.git(root, 'rev-parse', '--short', 'HEAD') or os.environ.get('EIDO_SURFACE_COMMIT'),
                          plan=os.path.basename(plan_path))
    jobs = []
    if opt('--check'):
        chk = opt('--check')
        jobs.append(('check', os.path.splitext(os.path.basename(chk))[0], None, chk))
    for item in (opt('--views') or '').split(','):
        if item:
            recipe, view = item.split('/', 1)
            jobs.append(('view', recipe, view, None))
    done = set()
    for kind, recipe, view, chk in jobs:
        rec = {}
        if view:
            with open(os.path.join(review, recipe, f'{recipe}_{ref}_record.json'), encoding='utf-8') as f:
                rec = json.load(f).get(f'{view}_{ref}') or {}
        focus = rec.get('focus')
        name = f'{recipe}_{view}_j' if focus else recipe
        if name in done:
            continue
        done.add(name)
        p = plan[recipe]
        size = refs.load(p['reference']).extent if p.get('reference') else None
        if focus:                                        # review_views.render_group: the camera over the recipe's centre
            from surfacing_judge import shots as SH
            v0 = next(x for x in p['views'] if x['name'] == view)
            c0 = SH.recipe_centre(recipe, p.get('params'))
            focus = [(c0[0] + v0['cam'][0], c0[1] + v0['cam'][1])]
        t0 = time.time()
        row = dict(view=view, focus=focus, record_focus=rec.get('focus'), size=size, params=p.get('params'))
        try:
            t = A.generate(recipe, size=size, seed=1, params=p.get('params'), quality='film', focus=focus, cache=False,
                           log=lambda *_: None)
            row['seconds'] = round(time.time() - t0, 1)
            if kind == 'check':
                path = os.path.join(out, f'_check_{name}.npz')
                t.save(path)
                eq, first, n = compare_saves(path, chk)
                row['check'] = dict(against=os.path.basename(chk), equal=eq, first_difference=first, arrays=n)
                for ext in ('.npz', '.json'):
                    try:
                        os.remove(os.path.splitext(path)[0] + ext)
                    except OSError:
                        pass
                print(f'[blender_terrains] check {name}: {"bit-identical" if eq else "DIFFERS: " + str(first)} '
                      f'({n} arrays, {row["seconds"]} s)', flush=True)
            else:
                ok, why = same_levels(t, rec.get('levels'))
                row['levels_as_record'] = dict(ok=ok, why=why)
                path = os.path.join(out, name + '.npz')
                t.save(path)
                row['saved'] = os.path.basename(path)
                print(f'[blender_terrains] {name}: {len(t.levels)} levels ({why}), {row["seconds"]} s', flush=True)
            del t
        except Exception as e:                           # noqa: BLE001 - reported, the run goes on
            traceback.print_exc()
            row['error'] = f'{type(e).__name__}: {e}'
        rep[name] = row
        with open(rep_path, 'w', encoding='utf-8') as f:
            json.dump(rep, f, indent=1)
    print('[blender_terrains] done', flush=True)


try:
    main()
except Exception:                                        # noqa: BLE001
    traceback.print_exc()
    os._exit(1)
os._exit(0)
