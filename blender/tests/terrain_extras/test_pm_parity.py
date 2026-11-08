"""eidoblend.materials' generators against the engine's own procedural_materials.js, pixel for pixel.

Runs with system Python (numpy only; no Blender):
    python blender/tests/terrain_extras/test_pm_parity.py [--refresh]
It runs eidoverse/procedural_materials.js under deno on @napi-rs/canvas (Skia: the 2D canvas the engine's
render_common.mjs shims in) through pm_dump.mjs, once (out/pm_engine/, --refresh to redo), then makes every case of
pm_cases.json with eidoblend/materials/_gen.py and compares the bytes:
  - the per-pixel generators (noise, voronoi, patches, weave, grain, height_to_normal, composite and the factories'
    maps): byte-identical expected (a sin() ulp can flip a truncation once in millions of pixels);
  - the drawn ones (scratches, smudges, pores): the same draw list from the same Mulberry32 stream, rasterised with
    box-filtered coverage where Skia anti-aliases its own way: held to a mean difference and to the same total ink.
Prints PASS/FAIL per case; exit 1 on any FAIL, 2 when deno or its cached canvas is missing.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
sys.path.insert(0, str(WORKTREE / 'blender' / 'eidoblend' / 'materials'))
import _gen  # noqa: E402  (a plain module: no bpy)

ENGINE = HERE / 'out' / 'pm_engine'
SRC = WORKTREE / 'eidoverse' / 'procedural_materials.js'
DRAWN = ('scratches', 'smudges', 'pores')


def snake(k):
    out = ''
    for ch in k:
        out += ('_' + ch.lower()) if ch.isupper() else ch
    return out


def kw(opts):
    return {snake(k): v for k, v in opts.items()}


def load(name, idx):
    m = idx['textures'][name]
    a = np.fromfile(ENGINE / (name + '.rgba'), dtype=np.uint8).reshape(m['h'], m['w'], 4)
    return a[..., :3]


def run_engine(refresh):
    if (ENGINE / 'index.json').exists() and not refresh:
        return True
    deno = shutil.which('deno')
    if not deno:
        print('SKIP: deno not on PATH')
        return False
    ENGINE.mkdir(parents=True, exist_ok=True)
    cmd = [deno, 'run', '--no-config', '--no-lock', '--cached-only', '-A', str(HERE / 'pm_dump.mjs'), str(SRC),
           str(HERE / 'pm_cases.json'), str(ENGINE)]
    subprocess.run(cmd, cwd=str(HERE))           # deno 2.8 panics at exit over napi finalisers: judge by the files
    return (ENGINE / 'index.json').exists()


GEN = {'scratches': _gen.scratches, 'smudges': _gen.smudges, 'noise': _gen.noise, 'voronoi': _gen.voronoi_tex,
       'patches': _gen.patches, 'pores': _gen.pores, 'weave': _gen.weave, 'grain': _gen.grain}


def compare(name, mine, eng, drawn):
    if mine.shape != eng.shape:
        return False, 'shape %s against %s' % (mine.shape, eng.shape)
    d = np.abs(mine.astype(np.int32) - eng.astype(np.int32))
    same = float((d == 0).mean())
    mean = float(d.mean())
    ink_m, ink_e = float(mine.mean()), float(eng.mean())
    msg = 'identical %.5f, mean |d| %.3f, max %d, ink %.2f / %.2f' % (same, mean, int(d.max()), ink_m, ink_e)
    if drawn:
        ok = mean <= 2.0 and abs(ink_m - ink_e) <= 1.5
    else:
        ok = same >= 0.9999 and int(d.max()) <= 1
    return ok, msg


def main():
    refresh = '--refresh' in sys.argv
    if not run_engine(refresh):
        print('FAIL: no engine dump (deno run of pm_dump.mjs)')
        return 2
    idx = json.loads((ENGINE / 'index.json').read_text())
    cases = json.loads((HERE / 'pm_cases.json').read_text())
    made = {}
    fails = 0
    for name, fn, args in cases['generators']:
        w, h, opts = args
        mine = GEN[fn](w, h, **kw(opts))
        made[name] = mine
        ok, msg = compare(name, mine, load(name, idx), fn in DRAWN)
        fails += not ok
        print('%s %-22s %s' % ('PASS' if ok else 'FAIL', name, msg))
    pending = list(cases['derived'])
    while pending:
        name, fn, args = pending.pop(0)
        refs = [args[0]] if fn == 'heightToNormal' else [args[0], args[1]]
        if any(r not in made for r in refs):
            pending.append([name, fn, args])
            continue
        if fn == 'heightToNormal':
            mine = _gen.height_to_normal(made[args[0]], **kw(args[1]))
        else:
            mine = _gen.composite(made[args[0]], made[args[1]], args[2], **kw(args[3]))
        made[name] = mine
        # a composite of a drawn texture inherits its anti-aliasing differences, and one of a different-sized
        # texture goes through drawImage's resampling filter (Skia's own): judge those like the drawn ones
        drawn = any(any(d in r for d in DRAWN) or r.startswith('comp_recipe') for r in refs) or \
            (fn == 'composite' and made[args[0]].shape != made[args[1]].shape)
        ok, msg = compare(name, mine, load(name, idx), drawn)
        fails += not ok
        print('%s %-22s %s' % ('PASS' if ok else 'FAIL', name, msg))
    # the factories' maps, made as the factories make them (procedural.py calls these same functions)
    F = idx['factories']
    checks = {
        'skin__map': lambda: _gen.skin_variation(512, 0xcc8866, 3),
        'skin__normalMap': lambda: _gen.pores(512, 512),
        'skin_cow__map': lambda: _gen.patches(256, 256, base_color=16773344, patch_color=1710618, scale=3,
                                              threshold=0.5, shape='blob'),
        'scaly__map': lambda: _gen.scaly_maps(512, 0x2a5a3a, 12, 2)[0],
        'scaly__normalMap': lambda: _gen.scaly_maps(512, 0x2a5a3a, 12, 2)[1],
        'worn_metal__map': lambda: _gen.worn_metal_maps(512, 0x3a5a3a, 0x888888, 0.4, 4)[0],
        'worn_metal__roughnessMap': lambda: _gen.worn_metal_maps(512, 0x3a5a3a, 0x888888, 0.4, 4)[1],
        'worn_metal__metalnessMap': lambda: _gen.worn_metal_maps(512, 0x3a5a3a, 0x888888, 0.4, 4)[2],
        'rubber__roughnessMap': lambda: _gen.noise(512, 512, scale=20, octaves=4, contrast=0.5),
        'rubber__normalMap': lambda: _gen.height_to_normal(_gen.noise(512, 512, scale=20, octaves=4, contrast=0.5),
                                                           strength=0.5),
        'fabric__roughnessMap': lambda: _gen.composite(_gen.weave(512, 512, density=30, variation=0.2),
                                                       _gen.smudges(512, 512, amount=0.5, seed=99), 'add',
                                                       strength=0.2),
        'painted_metal__clearcoatRoughnessMap': lambda: _gen.composite(_gen.scratches(512, 512), _gen.smudges(512, 512),
                                                                       'add', strength=0.4),
        'painted_metal_scratched__clearcoatRoughnessMap': lambda: _gen.scratches(256, 256, density=0.6, depth=0.8,
                                                                                 direction=1.2),
    }
    for name, fn in checks.items():
        ok, msg = compare(name, fn(), load(name, idx), name.startswith(('painted', 'fabric', 'skin__normal')))
        fails += not ok
        print('%s %-46s %s' % ('PASS' if ok else 'FAIL', name, msg))
    print('scalars the engine set:', json.dumps({k: v['scalars'] for k, v in F.items()})[:600])
    print('%s: %d failing' % ('FAIL' if fails else 'PASS', fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
