"""ekigar-project migration and graph serialisation against Ekigar's own model.js, document by document: format-2
Surface nodes with numbered mask slots, a monolithic layer array, internal mask rules, a legacy material chain, a
removed mask source, a field pass-through, unknown fields at every level, portals, groups, notes and tabs.

    python blender/tests/terrain_ekigar/test_project_parity.py
"""
import json
import os
import subprocess
import sys

import _ekigar_load

ek = _ekigar_load.load()
HERE = _ekigar_load.HERE
OUT = _ekigar_load.OUT
os.makedirs(OUT, exist_ok=True)

N = lambda i, op, **kw: dict({'id': i, 'op': op, 'params': {}, 'x': 0, 'y': 0}, **kw)  # noqa: E731
E = lambda a, ap, b, bp, **kw: dict({'from': {'node': a, 'port': ap}, 'to': {'node': b, 'port': bp}}, **kw)  # noqa: E731
docs = [
    {'format': 'ekigar-project/2', 'tile': {'x': 1, 'y': 1}, 'target': 'n2',
     'graph': {'nodes': [N('n1', 'fbm'), N('n2', 'surface', layer={'name': 'grass', 'rules': [{'mask': 'slope'}]}),
                         N('n3', 'slopeMask'), N('n4', 'heightMask')],
               'edges': [E('n1', 'out', 'n2', 'in'), E('n3', 'out', 'n2', 'mask2'), E('n4', 'out', 'n2', 'mask1'),
                         E('n2', 'out', 'n5', 'in')]}},
    {'format': 'ekigar-project/2',
     'graph': {'nodes': [N('n1', 'surface', layers=[{'name': 'a', 'maskStack': [1, 2]}, {'name': 'b', 'bandMin': 0.2},
                                                     {'id': 'dup'}, {'id': 'dup'}])],
               'edges': [E('n9', 'out', 'n1', 'mask3')]}},
    {'format': 'ekigar-project/2', 'materialTarget': 'nX',
     'graph': {'nodes': [N('n1', 'fbm'), N('n2', 'layers'), N('n3', 'materialMap', layers=[])],
               'edges': [E('n1', 'out', 'n2', 'in'), E('n2', 'out', 'n3', 'mask'), E('n1', 'out', 'n3', 'mask2')]}},
    {'format': 'ekigar-project/3', 'futureRoot': {'keep': True}, 'target': 'n1', 'targetPort': 'wear',
     'graph': {'nodes': [N('n1', 'phacelle', title='Erode', disabled=True, futureNode=[1, 2], tab=1),
                         N('n2', 'fbm')],
               'edges': [E('n2', 'out', 'n1', 'in', viaPortal='base', futureEdge='x')],
               'portals': [{'name': 'base', 'node': 'n2', 'port': 'out'}],
               'groups': [{'id': 'gr1', 'name': 'G', 'children': ['n1']}],
               'notes': [{'id': 'nt1', 'markdown': '# hi'}],
               'tabs': [{'index': 0, 'name': 'Graph 1'}, {'index': 1, 'name': 'Detail'}],
               'graphExtra': 42}},
    {},
]
src = os.path.join(OUT, 'project_docs.json')
dst = os.path.join(OUT, 'project_js.json')
json.dump(docs, open(src, 'w'))
r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A', f'--import-map={os.path.join(HERE, "import_map.json")}',
                    os.path.join(HERE, 'project_dump.mjs'), src, dst, _ekigar_load.EKIGAR_ROOT],
                   capture_output=True, text=True, timeout=300)
if r.returncode != 0:
    print('FAIL project dump:', r.stderr[-1500:])
    sys.exit(1)
js = json.load(open(dst))
ok_all = True
for i, (doc, want) in enumerate(zip(docs, js)):
    proj, warns = ek.migrate_project(doc)
    g = ek.from_json(doc.get('graph') or {'nodes': [], 'edges': []})
    got = json.loads(json.dumps({'project': proj, 'warnings': warns, 'roundTrip': ek.to_json(g)}))
    for k in ('project', 'warnings', 'roundTrip'):
        ok = got[k] == want[k]
        ok_all &= ok
        if not ok:
            print(f'FAIL document {i} {k}:\n  py {json.dumps(got[k])[:600]}\n  js {json.dumps(want[k])[:600]}')
    if all(got[k] == want[k] for k in ('project', 'warnings', 'roundTrip')):
        print(f'PASS document {i}: migration, warnings and graph round trip match Ekigar')
print('projects:', 'all match' if ok_all else 'MISMATCH')
sys.exit(0 if ok_all else 1)
