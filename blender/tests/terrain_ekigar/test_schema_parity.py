"""Every public declaration of Ekigar's registry against the port: operator order, labels, categories, docs, flags,
every parameter's schema (type, default, range, values, structural / maskable / periodFreq, unit, doc), ports and
named outputs, the landform contract, blend modes, port types and connection rules, mask names and export formats.

    python blender/tests/terrain_ekigar/test_schema_parity.py
"""
import json
import os
import subprocess
import sys

import _ekigar_load

ek = _ekigar_load.load()
HERE = _ekigar_load.HERE
out_json = os.path.join(_ekigar_load.OUT, 'ekigar_schema.json')
os.makedirs(_ekigar_load.OUT, exist_ok=True)
r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', f'--import-map={os.path.join(HERE, "import_map.json")}',
                    os.path.join(HERE, 'schema_dump.mjs'), out_json, _ekigar_load.EKIGAR_ROOT],
                   capture_output=True, text=True, timeout=600)
if r.returncode != 0:
    print('FAIL schema dump:', r.stderr[-1500:])
    sys.exit(1)
js = json.load(open(out_json, encoding='utf-8'))
results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}", flush=True)


def norm(v):
    """JSON-normalise (Python tuples -> lists, ints and floats compare by value)."""
    return json.loads(json.dumps(v))


check('operator order', list(ek.OPERATORS) == js['order'], f'{len(js["order"])} operators')
check('list_operators', norm(ek.list_operators()) == js['list'])
check('blend modes and combine modes', ek.BLEND_MODES == js['blendModes'] and ek.COMBINE_MODES == js['combineModes'])

bad = []
for op, o in js['ops'].items():
    p = ek.OPERATORS[op]
    diffs = []
    for k in ('label', 'category', 'doc'):
        if (p.get(k) or None) != o[k]:
            diffs.append(k)
    for k, flag in (('generator', 'generator'), ('hidden', 'hidden'), ('needsResample', 'needsResample'),
                    ('warpsPosition', 'warpsPosition')):
        if bool(p.get(k)) != o[flag]:
            diffs.append(k)
    if (p.get('optionalInput') if 'optionalInput' in p else None) != o['optionalInput']:
        diffs.append('optionalInput')
    if p.get('visualFixture') != o['visualFixture']:
        diffs.append('visualFixture')
    if bool(p.get('snap')) != o['hasSnap'] or bool(p.get('warpPosition')) != o['hasWarpPosition']:
        diffs.append('snap/warpPosition')
    if norm(p['params']) != o['params']:
        pk = set(p['params']) ^ set(o['params'])
        detail = [k for k in o['params'] if k in p['params'] and norm(p['params'][k]) != o['params'][k]]
        diffs.append(f'params {sorted(pk)} {detail[:3]}')
    if norm(ek.ports_of(op)) != o['ports']:
        diffs.append('ports')
    if ek.structural_params(op) != o['structural']:
        diffs.append('structural')
    if diffs:
        bad.append(f'{op}: {", ".join(diffs)}')
check(f'every operator declaration matches ({len(js["ops"])})', not bad, '; '.join(bad[:6]))

cbad = []
for entry in js['landformContract']:
    o = ek.OPERATORS.get(entry['id'])
    if not o:
        cbad.append(f"{entry['id']} missing")
        continue
    if list(o['params']) != entry['params']:
        cbad.append(f"{entry['id']} params")
    if [x['name'] for x in o.get('outputs') or []] != entry['outputs']:
        cbad.append(f"{entry['id']} outputs")
check(f"landform contract ({len(js['landformContract'])} landforms)", not cbad, '; '.join(cbad))
check('port types and project format', norm(ek.PORT_TYPES) == js['portTypes'] and ek.PROJECT_FORMAT == js['projectFormat'])
check('connection rules', all(ek.can_connect(*k.split('>')) == v for k, v in js['canConnect'].items()))
check('mask names', ek.MASK_NAMES == js['maskNames'])
check('heightmap formats', norm(ek.HEIGHTMAP_FORMATS) == js['heightmapFormats'])
print(f'schema: {sum(results)}/{len(results)} pass')
sys.exit(0 if all(results) else 1)
