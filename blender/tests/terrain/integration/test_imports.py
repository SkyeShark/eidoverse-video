"""The terrain family's import smoke, in Blender (no kernel runs, no render, so no GPU slot):

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/terrain/integration/test_imports.py

1. every module under blender/eidoblend/terrain/ imports (the package scripts aside: bake.py runs as a script);
2. the package's exports resolve (make_terrain, Terrain, MaskSet, recipes, describe, terrain_height_at and the
   surface tools), recipes() lists every recipe module's recipes, and describe() prints each one;
3. every `eidoblend` import statement in the family's tests runs (blender/tests/terrain/<package>/*.py), so a test
   that names a module or a function that moved or went away fails here, in seconds.
Prints PASS / FAIL per line; Blender exits 0 either way, so the FAIL lines are the verdict.
"""
import ast
import importlib
import io
import os
import sys
import traceback
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
BLENDER_DIR = os.path.normpath(os.path.join(TN, '..', '..'))
TERRAIN = os.path.join(BLENDER_DIR, 'eidoblend', 'terrain')
sys.path.insert(0, BLENDER_DIR)
SCRIPTS = {'bake.py'}
RECORDS = {'triage', 'research', 'out', 'design_probes', '__pycache__'}


def main():
    bad = 0
    n = 0
    for dp, dns, fns in os.walk(TERRAIN):
        dns[:] = sorted(d for d in dns if d not in ('__pycache__', 'kernels'))
        for fn in sorted(fns):
            rel = os.path.relpath(os.path.join(dp, fn), TERRAIN).replace(os.sep, '/')
            if not fn.endswith('.py') or rel in SCRIPTS:
                continue
            mod = 'eidoblend.terrain.' + rel[:-3].replace('/', '.')
            mod = mod[:-len('.__init__')] if mod.endswith('.__init__') else mod
            n += 1
            try:
                importlib.import_module(mod)
            except Exception as e:                                       # noqa: BLE001
                bad += 1
                print(f'[imports] FAIL module {mod}: {type(e).__name__}: {e}', flush=True)
                traceback.print_exc(limit=3)
    print(f"[imports] {'PASS' if not bad else 'FAIL'} {n} modules of eidoblend.terrain imported ({bad} failed)",
          flush=True)
    import eidoblend.terrain as T
    for name in T.__all__:
        try:
            getattr(T, name)
            print(f'[imports] PASS export eidoblend.terrain.{name}', flush=True)
        except Exception as e:                                           # noqa: BLE001
            print(f'[imports] FAIL export eidoblend.terrain.{name}: {type(e).__name__}: {e}', flush=True)
    names = T.recipes.names()
    mods = sorted(f[:-3] for f in os.listdir(os.path.join(TERRAIN, 'recipes'))
                  if f.endswith('.py') and not f.startswith('_'))
    missing = [m for m in mods if m not in names]
    print(f"[imports] {'PASS' if not missing else 'FAIL'} recipes(): {len(names)} recipes ({', '.join(names)})"
          + (f'; modules without a recipe of their name: {missing}' if missing else ''), flush=True)
    for r in names:
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                T.describe(r)
            text = buf.getvalue()
            ok = r in text and 'knob' in text.lower()
            print(f"[imports] {'PASS' if ok else 'FAIL'} describe('{r}'): {len(text.splitlines())} lines", flush=True)
        except Exception as e:                                           # noqa: BLE001
            print(f"[imports] FAIL describe('{r}'): {type(e).__name__}: {e}", flush=True)
    for pkg in sorted(os.listdir(TN)):
        d = os.path.join(TN, pkg)
        if pkg in RECORDS or not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.py'):
                continue
            p = os.path.join(d, fn)
            try:
                tree = ast.parse(open(p, encoding='utf-8').read())
            except SyntaxError as e:
                print(f'[imports] FAIL {pkg}/{fn}: syntax error: {e}', flush=True)
                continue
            stmts = [nd for nd in ast.walk(tree)
                     if (isinstance(nd, ast.ImportFrom) and nd.level == 0 and (nd.module or '').startswith('eidoblend'))
                     or (isinstance(nd, ast.Import) and any(a.name.startswith('eidoblend') for a in nd.names))]
            if not stmts:
                continue
            errs = []
            for nd in stmts:
                code = ast.unparse(nd)
                try:
                    exec(compile(code, p, 'exec'), {})
                except Exception as e:                                   # noqa: BLE001
                    errs.append(f'{code}: {type(e).__name__}: {e}')
            print(f"[imports] {'FAIL' if errs else 'PASS'} {pkg}/{fn}: "
                  + (errs[0][:300] if errs else f'{len(stmts)} eidoblend import(s)'), flush=True)


main()
