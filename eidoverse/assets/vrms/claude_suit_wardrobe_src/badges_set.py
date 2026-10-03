"""Edit badges.json from the command line and keep it in its compact, readable layout.

    python eidoverse/assets/vrms/claude_suit_wardrobe_src/badges_set.py mod_gold ray_origin='[-0.29,-0.377,1.657]' ray_dir='[0,0.766,-0.643]'
    python eidoverse/assets/vrms/claude_suit_wardrobe_src/badges_set.py --print
"""
import json
import os
import sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'badges.json')


def fmt(v):
    return json.dumps(v, ensure_ascii=False, separators=(', ', ': '))


def save(d):
    lines = ['{', f'  "_doc": {fmt(d["_doc"])},', f'  "uv_extent": {d["uv_extent"]},', '  "badges": {']
    keys = list(d['badges'])
    for i, k in enumerate(keys):
        lines.append(f'    "{k}": {{')
        items = list(d['badges'][k].items())
        for j, (kk, vv) in enumerate(items):
            lines.append(f'      "{kk}": {fmt(vv)}' + (',' if j < len(items) - 1 else ''))
        lines.append('    }' + (',' if i < len(keys) - 1 else ''))
    lines += ['  }', '}']
    open(P, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')


d = json.load(open(P, encoding='utf-8'))
if len(sys.argv) > 2:
    b = d['badges'][sys.argv[1]]
    for kv in sys.argv[2:]:
        k, v = kv.split('=', 1)
        b[k] = json.loads(v)
    save(d)
for k, b in d['badges'].items():
    print(k, {x: b[x] for x in ('bone', 'ray_origin', 'ray_dir', 'up', 'rot')})
