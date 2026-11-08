"""ekigar-project/3 files written the way Ekigar's Save button writes them (project_files_dump.mjs builds the graphs
with Ekigar's own model.js and registry, saves the document main.js saves, reopens it and evaluates it with Ekigar's
compiler) load and evaluate in the port to the same field: a masked erosion under snow, a caldera behind a portal
with its floor mask as the target port, a disabled node, two combined branches across tabs, a Material Map beside
the terrain.

    python blender/tests/terrain_ekigar/test_project_files.py
"""
import json
import os
import subprocess
import sys

import numpy as np

import _ekigar_load
import parity_lib as L

ek = _ekigar_load.load()
HERE = _ekigar_load.HERE
OUT = os.path.join(_ekigar_load.OUT, 'project_files')
os.makedirs(OUT, exist_ok=True)
r = subprocess.run(['deno', 'run', '--no-config', '--no-lock', '-A',
                    f'--import-map={os.path.join(HERE, "import_map.json")}',
                    os.path.join(HERE, 'project_files_dump.mjs'), OUT, _ekigar_load.EKIGAR_ROOT],
                   capture_output=True, text=True, timeout=600)
if r.returncode != 0:
    print('FAIL project files dump:', r.stderr[-1500:])
    sys.exit(1)
index = json.load(open(os.path.join(OUT, 'index.json'), encoding='utf-8'))
ok_all = True
for item in index:
    path = item['file']
    proj, warns = ek.load_project(path)
    hf = ek.generate(path, resolution=48)          # the defaults: what a user gets loading Ekigar's file
    a = np.fromfile(os.path.join(OUT, f'{item["name"]}.bin'), dtype=np.float64)
    n = 48 * 48
    js = {c: a[i * n:(i + 1) * n].reshape(48, 48) for i, c in enumerate(item['channels'])}
    py = {'x': hf.field[0], 'y': hf.field[1], 'z': hf.field[2], 'w': hf.field[3]}
    py.update({f'out:{k}': v for k, v in hf.outs.items()})
    worst = 0.0
    # the heightfield lists each distinct compiler warning once (Ekigar's repeats one per resampled evaluation)
    ok = sorted(js) == sorted(py) and not warns and hf.warnings == list(dict.fromkeys(item['warnings']))
    for c in js:
        if c in py:
            good, tr, med, mx, sc = L.compare(py[c], js[c])
            ok &= good
            worst = max(worst, mx)
    ok_all &= ok
    print(f'{"PASS" if ok else "FAIL"} {item["name"]:28s} target {proj["target"]}.{proj.get("targetPort")} '
          f'channels {len(js)} worst {worst:.1e}' + ('' if sorted(js) == sorted(py) else
                                                     f' (channels js {sorted(js)} py {sorted(py)})'))
print('project files:', 'all load and evaluate like Ekigar' if ok_all else 'MISMATCH')
sys.exit(0 if ok_all else 1)
