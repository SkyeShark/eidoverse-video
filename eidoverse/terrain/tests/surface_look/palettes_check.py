"""The look package's first check (PORT_PLAN.md 8.2 row P18): build/palettes.js JSON-equal to the Blender edition's
committed build/palettes.py (the palettes are P14's data port; this checks it, it does not own it).

    <Blender's python> -I eidoverse/terrain/tests/surface_look/palettes_check.py [--override <dir>]

The Blender edition is found as tests/parity/_blender.py finds it ($EIDO_BLENDER_EDITION, or blender/ in this
checkout) and is only read. P14's own generator (tests/surface_data/palettes_port.py: block(), data_names(), fmt())
writes palettes.py's module-level data as palettes.js holds it; here each table is compared by name with palettes.js's
data block, and palettes.py's functions are compared, by their source (ast), between the commit palettes.js names and
the edition's HEAD, so the record says whether regenerating the data block alone would be the whole re-port.

    --override <dir>   also write <dir>/palettes.js: build/palettes.js with the edition's data block in place of its
                       own and its three relative imports made absolute, so a judge render can read the edition's
                       palettes through an import map (Blender's review_views.py --palettes: a render's palettes from
                       another file). A test input under tests/out, never a file of the port.

Writes tests/out/surface_look/palettes_check.json (equal, both commits, the tables that differ, the functions whose
source differs) and exits 1 when the data differ.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.normpath(os.path.join(HERE, '..'))
TERRAIN = os.path.normpath(os.path.join(TESTS, '..'))
sys.path.insert(0, os.path.join(TESTS, 'parity'))
sys.path.insert(0, os.path.join(TESTS, 'surface_data'))
import _blender as B  # noqa: E402
import palettes_port as PP  # noqa: E402  (P14's generator, used as it is)

OUT = os.path.join(TESTS, 'out', 'surface_look')
PAL_PY = 'blender/eidoblend/terrain/build/palettes.py'


def tables_of(block):
    """palettes.js's data block -> {name: the JSON text after `export const NAME = `, its `;` dropped}."""
    out, name, buf = {}, None, []
    for line in block.split('\n'):
        m = re.match(r'export const (\w+) = (.*)$', line)
        if m:
            if name:
                out[name] = '\n'.join(buf).rstrip().rstrip(';')
            name, buf = m.group(1), [m.group(2)]
        elif name and not line.startswith('// palettes data>'):
            buf.append(line)
    if name:
        out[name] = '\n'.join(buf).rstrip().rstrip(';')
    return out


def functions_of(src):
    """Top-level functions of a Python source -> {name: ast.dump of the def} (comments and layout ignored)."""
    tree = ast.parse(src)
    return {n.name: ast.dump(n, include_attributes=False) for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def main():
    a = B.script_args()
    edition = B.bare_terrain_package()
    from eidoblend.terrain.build import palettes as P
    with open(PP.TARGET, encoding='utf-8') as f:
        text = f.read()
    i, j = text.index(PP.START), text.index(PP.END) + len(PP.END)
    port_block = text[i:j]
    m = re.search(r'palettes\.py at (\w+)', text.split('\n', 1)[0])
    port_commit = m.group(1) if m else None
    head = B.git(edition, 'rev-parse', '--short', 'HEAD') or os.environ.get('EIDO_SURFACE_COMMIT') or 'unknown'
    last = B.git(edition, 'log', '-1', '--format=%h', '--', PAL_PY) or None
    new_block = PP.block(P, last or head)
    old_t, new_t = tables_of(port_block), tables_of(new_block)
    changed = [n for n in new_t if n in old_t and new_t[n] != old_t[n]]
    added = [n for n in new_t if n not in old_t]
    removed = [n for n in old_t if n not in new_t]
    # the functions: palettes.py at the port's commit against the edition's HEAD (git show, read-only)
    funcs = None
    if port_commit:
        old_src = B.git(edition, 'show', f'{port_commit}:{PAL_PY}')
        with open(os.path.join(edition, *PAL_PY.split('/')), encoding='utf-8') as f:
            new_src = f.read()
        if old_src:
            fo, fn = functions_of(old_src), functions_of(new_src)
            funcs = dict(changed=[k for k in fn if k in fo and fn[k] != fo[k]],
                         added=[k for k in fn if k not in fo], removed=[k for k in fo if k not in fn])
    equal = not (changed or added or removed)
    res = dict(check='build/palettes.js JSON-equal to the committed build/palettes.py', equal=equal,
               port_file_commit=port_commit, edition_head=head, palettes_py_last_commit=last,
               tables=len(new_t), tables_changed=changed, tables_added=added, tables_removed=removed,
               functions=funcs, owner='P14',
               how=('regenerate: <Blender\'s python> -I eidoverse/terrain/tests/surface_data/palettes_port.py, then '
                    'tests/surface_data/palettes_test.mjs'))
    if '--override' in a:
        d = os.path.abspath(a[a.index('--override') + 1])
        os.makedirs(d, exist_ok=True)
        body = text[:i] + new_block + text[j:]
        # the copy's relative imports, made absolute (it lives outside build/)
        for rel in ('../masks.js', '../surface/maps.js', '../core/levels.js'):
            url = 'file:///' + os.path.normpath(os.path.join(TERRAIN, 'build', rel)).replace('\\', '/').lstrip('/')
            body = body.replace(f"from '{rel}'", f"from '{url}'")
        body = body.replace(f'at {port_commit}', f'at {last or head} (judge override: the data block regenerated)', 1) \
            if port_commit else body
        p = os.path.join(d, 'palettes.js')
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(body)
        res['override'] = p.replace('\\', '/')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'palettes_check.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1)
    print(f"[palettes_check] palettes.js (palettes.py at {port_commit}) {'equals' if equal else 'differs from'} "
          f"palettes.py at {last} (edition HEAD {head}): {len(changed)} of {len(new_t)} tables differ "
          f"{changed}, added {added}, removed {removed}; functions {funcs}")
    return 0 if equal else 1


if __name__ == '__main__':
    sys.exit(main())
