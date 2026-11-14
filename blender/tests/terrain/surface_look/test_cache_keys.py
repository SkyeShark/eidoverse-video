"""palettes.py's edits never regenerate a cached terrain (SURFACING_DESIGN.md 5.1): plain Python, no Blender.

    python blender/tests/terrain/surface_look/test_cache_keys.py

A recipe's defaults are part of its terrain cache key, and palettes.py reaches six recipes' defaults: strata.palette_for
deep-copies PALETTES['desert_sandstone'] and PALETTES['badlands'] into canyon, incised_meanders, mesas_buttes and
badlands; tower_karst and sea_cliffs keep get('karst') and get('chalk_coast') (with DEFAULT_OPTIONS filled in), and
tower_karst calls palettes._cliff. real_place reads PLACES (a place's palette, mask_params and strata) into its
defaults. So every recipe's cache key is built twice, in fresh processes, once with the palettes.py of the last commit
(git show HEAD:...) and once with this checkout's, and must be the same:

  - the key itself (core.cache.make_key at the recipe's defaults: its size, 1024 cells, seed 1, no focus), for every
    recipe, and for real_place under each place of PLACES;
  - and, for the message when it fails, the payload it hashes (the recipe's to_dict(), and real_place's defaults_for
    each place), so the line names what changed.

Exit 0 when every key matches; 1 with the recipes whose key changed; 0 with a [skip] line where HEAD's file cannot be
read (not a git checkout).
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
BLENDER_DIR = os.path.normpath(os.path.join(TN, '..', '..'))
REPO = os.path.normpath(os.path.join(BLENDER_DIR, '..'))
REL = 'blender/eidoblend/terrain/build/palettes.py'
_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0

# what one process prints: python <this script> <blender dir> [palettes.py]
_KEYS_SCRIPT = r'''
import importlib.util, json, sys
sys.path.insert(0, sys.argv[1])
if len(sys.argv) > 2:
    import eidoblend.terrain.build as B
    spec = importlib.util.spec_from_file_location('eidoblend.terrain.build.palettes', sys.argv[2])
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    B.palettes = m
from eidoblend.terrain import recipes as R
from eidoblend.terrain.build import palettes as P
from eidoblend.terrain.core import cache as C, levels as LV

def key(rec, values, dfl):
    size = float(dfl.get('size') or 1000.0)
    plan = LV.plan_levels(size, 1024, tuple(dfl.get('centre', (0.0, 0.0))), dfl.get('context'), None, None,
                          warn=lambda m: None)
    extra = dict(mask_params=dfl.get('mask_params'), base_elevation_m=dfl.get('base_elevation_m'),
                 sea_level=dfl.get('sea_level'))
    return C.make_key(rec.to_dict(), values, size, 1024, 1, plan, None, extra=extra)

out = {}
for n in R.names():
    rec = R.resolve(n)
    if n == 'real_place':
        for dem in sorted(P.PLACES):
            try:
                values, _s = rec.resolve({'dem': dem})
                dfl = dict(rec.defaults)
                dfl.update(rec.defaults_for(values))
                out['real_place:' + dem] = dict(key=key(rec, values, dfl),
                                                payload=json.dumps(rec.defaults_for(values), sort_keys=True,
                                                                   default=str))
            except Exception as e:                       # a place without its DEM on this machine
                out['real_place:' + dem] = dict(key='unavailable: ' + type(e).__name__, payload='')
        continue
    values, _stages = rec.resolve(None)
    out[n] = dict(key=key(rec, values, dict(rec.defaults)),
                  payload=json.dumps(rec.to_dict(), sort_keys=True, default=str))
print('@@KEYS@@' + json.dumps(out))
'''


def _keys(palettes_file=None):
    with tempfile.TemporaryDirectory() as d:
        script = os.path.join(d, 'keys.py')
        with open(script, 'w', encoding='utf-8') as fh:
            fh.write(_KEYS_SCRIPT)
        args = [sys.executable, script, BLENDER_DIR] + ([palettes_file] if palettes_file else [])
        r = subprocess.run(args, capture_output=True, text=True, cwd=d, creationflags=_NO_WINDOW)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith('@@KEYS@@')), None)
    if line is None:
        raise RuntimeError(f'the keys did not print: {r.stderr[-2000:]}')
    return json.loads(line[len('@@KEYS@@'):])


def _first_difference(a, b):
    """Where two JSON payloads first differ, as a short excerpt."""
    i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return f'...{a[max(0, i - 60):i + 60]}... against HEAD\'s ...{b[max(0, i - 60):i + 60]}...'


def check(log=print):
    """[] when every recipe's cache key is HEAD's; else the recipes whose key changed (each with where its payload
    differs). None (skipped) when HEAD's palettes.py cannot be read."""
    r = subprocess.run(['git', '-C', REPO, 'show', f'HEAD:{REL}'], capture_output=True, creationflags=_NO_WINDOW)
    if r.returncode != 0:
        log('[skip] cache keys: HEAD\'s palettes.py is not readable here (not a git checkout)')
        return None
    with tempfile.TemporaryDirectory() as d:
        head_file = os.path.join(d, 'palettes_head.py')
        with open(head_file, 'wb') as fh:
            fh.write(r.stdout)
        head = _keys(head_file)
    now = _keys(None)
    bad = []
    for name in sorted(set(head) | set(now)):
        a, b = now.get(name), head.get(name)
        if a is None or b is None or a['key'] != b['key']:
            where = _first_difference(a['payload'], b['payload']) if a and b and a['payload'] != b['payload'] else ''
            bad.append(f'{name}: {(a or {}).get("key", "missing")[:12]} against HEAD\'s {(b or {}).get("key", "missing")[:12]}'
                       + (f' ({where})' if where else ''))
    n_rec = sum(1 for k in now if not k.startswith('real_place:'))
    n_pl = len(now) - n_rec
    log(f'[keys] {n_rec} recipes and real_place under {n_pl} places: '
        + ('every cache key equals HEAD\'s' if not bad else f'{len(bad)} CHANGED: {bad}'))
    return bad


def main():
    bad = check()
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
