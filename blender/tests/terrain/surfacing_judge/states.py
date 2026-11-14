"""Where the renders of one state of the surfacing are (system Python): a state is what the boards put side by side
(before | after) and what baseline.py measures.

    from surfacing_judge import states as S
    S.render('canyon', 'approach_walk', 'v5')      # the textured render's path, or None
    S.layers('canyon', 'approach_walk', 'v5')      # its layer-map render's path, or None
    S.record('canyon', 'approach_walk', 'v5')      # the render's record (camera, seconds, window edges), or {}
    S.freeze('before', 'latest')                   # copy a state's files into out/surfacing_judge/states/before/

A state is named by
    a tag          of surfacing/review_views.py's renders: out/surfacing/review/<recipe>/<view>_<tag>.png, its layer
                   map <view>_<tag>_layers.png and <recipe>_<tag>_record.json;
    <folder>:<tag> the same file names under out/<folder>/<recipe>/ (another package's renders of the same cameras:
                   'surface_look:new');
    'latest'       each view's newest v<N> tag of review_views.py;
    a frozen state a folder out/surfacing_judge/states/<name>/<recipe>/ holding <view>.png, <view>_layers.png and
                   record.json. freeze() makes one, so a baseline stays as it was while new renders reuse the tags.
A frozen state of a name wins over a tag of the same name.

    python blender/tests/terrain/surfacing_judge/states.py freeze <name> [--from latest] [--recipes a,b]
    python blender/tests/terrain/surfacing_judge/states.py list <state>
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))

from surfacing_judge import OUT, OUT_ROOT, RENDERS  # noqa: E402
from surfacing_judge import views as V  # noqa: E402

STATES = os.path.join(OUT, 'states')


def _frozen(state, recipe):
    return os.path.join(STATES, state, recipe) if os.path.isdir(os.path.join(STATES, state)) else None


def _latest_tag(recipe, view):
    best = None
    for p in glob.glob(os.path.join(RENDERS, recipe, f'{view}_v*.png')):
        m = re.fullmatch(re.escape(view) + r'_v(\d+)\.png', os.path.basename(p))
        if m and (best is None or int(m.group(1)) > best):
            best = int(m.group(1))
    return None if best is None else f'v{best}'


def where(recipe, view, state):
    """(folder, tag) of a state's files for a view, or (frozen folder, None)."""
    d = _frozen(state, recipe)
    if d is not None:
        return d, None
    if ':' in state:
        folder, tag = state.split(':', 1)
        return os.path.join(OUT_ROOT, folder.replace('/', os.sep), recipe), tag
    return os.path.join(RENDERS, recipe), (_latest_tag(recipe, view) if state == 'latest' else state)


def _existing(p):
    return p if p and os.path.exists(p) else None


def render(recipe, view, state):
    d, tag = where(recipe, view, state)
    if tag is None:                                # a frozen state, or 'latest' of a view never rendered
        return _existing(os.path.join(d, f'{view}.png')) if _frozen(state, recipe) else None
    return _existing(os.path.join(d, f'{view}_{tag}.png'))


def layers(recipe, view, state):
    d, tag = where(recipe, view, state)
    if tag is None:
        return _existing(os.path.join(d, f'{view}_layers.png')) if _frozen(state, recipe) else None
    return _existing(os.path.join(d, f'{view}_{tag}_layers.png'))


def record(recipe, view, state):
    d, tag = where(recipe, view, state)
    if tag is None:
        p = os.path.join(d, 'record.json')
        if not _frozen(state, recipe) or not os.path.exists(p):
            return {}
        with open(p, encoding='utf-8') as f:
            return json.load(f).get(view, {})
    p = os.path.join(d, f'{recipe}_{tag}_record.json')
    if not os.path.exists(p):
        return {}
    with open(p, encoding='utf-8') as f:
        out = dict(json.load(f).get(f'{view}_{tag}', {}))
    if out:
        out['tag'] = tag
    return out


_LEVEL = re.compile(r'Level\((\d+) (\w+) ([-\d.e+]+) m @ ([-\d.e+]+) m x(\d+), x0 ([-\d.e+]+) y0 ([-\d.e+]+)')


def levels(rec):
    """The level windows a render record lists (its 'levels', as core/levels.Level prints them): [dict(index, role,
    side, cell, n, x0, y0)], coarsest first."""
    out = []
    for s in rec.get('levels') or []:
        m = _LEVEL.match(str(s))
        if m:
            i, role, side, cell, n, x0, y0 = m.groups()
            out.append(dict(index=int(i), role=role, side=float(side), cell=float(cell), n=int(n), x0=float(x0),
                            y0=float(y0)))
    return out


def same_camera(v, rec, tol_m=5.0):
    """Whether a render record's camera stands where the view's does (within tol_m across), from the record's main
    window; None when the record cannot say."""
    lv = [L for L in levels(rec) if L['role'] == 'main']
    if not rec or 'camera' not in rec or not lv:
        return None
    cx, cy = lv[0]['x0'] + lv[0]['side'] / 2.0, lv[0]['y0'] + lv[0]['side'] / 2.0
    dx, dy = rec['camera'][0] - cx - v['cam'][0], rec['camera'][1] - cy - v['cam'][1]
    return bool((dx * dx + dy * dy) ** 0.5 <= tol_m)


def freeze(name, source='latest', recipes=None, log=print):
    """Copy the renders, layer maps and records of `source` into the frozen state `name` (a view already there is
    kept: a frozen state is written once per view; a render whose record puts its camera elsewhere than the view's
    is left out, so several sources can fill one state). Returns the number of renders copied."""
    n = 0
    for recipe, rec in V.load().items():
        if recipes and recipe not in recipes:
            continue
        d = os.path.join(STATES, name, recipe)
        rp = os.path.join(d, 'record.json')
        recs = {}
        if os.path.exists(rp):
            with open(rp, encoding='utf-8') as f:
                recs = json.load(f)
        for v in rec['views']:
            src = render(recipe, v['name'], source)
            dst = os.path.join(d, f"{v['name']}.png")
            if not src or os.path.exists(dst):
                continue
            if same_camera(v, record(recipe, v['name'], source)) is False:
                if log:
                    log(f"[states] {name}: {recipe}/{v['name']}: {os.path.basename(src)} has another camera: left out")
                continue
            os.makedirs(d, exist_ok=True)
            shutil.copyfile(src, dst)
            lay = layers(recipe, v['name'], source)
            if lay:
                shutil.copyfile(lay, os.path.join(d, f"{v['name']}_layers.png"))
            r = record(recipe, v['name'], source)
            r['from'] = os.path.basename(src)
            recs[v['name']] = r
            n += 1
            if log:
                log(f"[states] {name}: {recipe}/{v['name']} <- {os.path.basename(src)}")
        if recs:
            os.makedirs(d, exist_ok=True)
            with open(rp, 'w', encoding='utf-8') as f:
                json.dump(recs, f, indent=1)
    return n


def listing(state):
    rows = []
    for recipe, rec in V.load().items():
        for v in rec['views']:
            rows.append((recipe, v['name'], render(recipe, v['name'], state), layers(recipe, v['name'], state)))
    return rows


def main(argv):
    if '--plan' in argv:
        V.load(argv[argv.index('--plan') + 1])
    if len(argv) >= 2 and argv[0] == 'freeze':
        src = argv[argv.index('--from') + 1] if '--from' in argv else 'latest'
        only = set(argv[argv.index('--recipes') + 1].split(',')) if '--recipes' in argv else None
        print(freeze(argv[1], src, only), 'renders frozen into', os.path.join(STATES, argv[1]))
        return 0
    if len(argv) >= 2 and argv[0] == 'list':
        have = 0
        for recipe, view, r, lay in listing(argv[1]):
            have += bool(r)
            print(f"{recipe:17s} {view:20s} {'render' if r else '-     '} {'layers' if lay else '-'}"
                  + (f'   {os.path.basename(r)}' if r else ''))
        print(have, 'views rendered in state', argv[1])
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
