"""Design probe (PORT_PLAN.md section 2.4): numpy's own draws for np_random_probe.mjs to reproduce bit for bit. The
seeds take the forms the Blender terrain passes to np.random.default_rng: an int, an int expression, and lists
[seed, salt] / [seed, salt, k] with large salts ('KARST' = 0x4B41525354 spans two 32-bit words).

    python eidoverse/terrain/tests/design_probes/np_random_expected.py <out.json>
"""
import json
import sys

import numpy as np

seeds = [0, 1, 7, 3 * 7919 + 17, 12345678901, [5, 65], [11, 7177, 3], [4294967295, 9097], [7, 0x4B41525354],
         [abs(-3) & 0xFFFFFFFF, 0x57414C4C, 12]]
draws = [{'m': 'random', 'n': 5}, {'m': 'uniform', 'n': 5, 'lo': -1.0, 'hi': 1.0},
         {'m': 'integers', 'n': 7, 'lo': 0, 'hi': 10}, {'m': 'uniform', 'n': 3, 'lo': 0.7, 'hi': 1.3},
         {'m': 'integers', 'n': 5, 'lo': 3, 'hi': 1000003}, {'m': 'random', 'n': 4}]
cases = []
for s in seeds:
    g = np.random.default_rng(s)
    vals = []
    for d in draws:
        if d['m'] == 'random':
            vals += [float(v) for v in g.random(d['n'])]
        elif d['m'] == 'uniform':
            vals += [float(v) for v in g.uniform(d['lo'], d['hi'], d['n'])]
        else:
            vals += [int(v) for v in g.integers(d['lo'], d['hi'], d['n'])]
    cases.append({'seed': s, 'draws': draws, 'values': vals})
with open(sys.argv[1], 'w', encoding='utf-8') as f:
    json.dump({'numpy': np.__version__, 'cases': cases}, f, indent=1)
print(f'{len(cases)} seeds, {sum(len(c["values"]) for c in cases)} draws, numpy {np.__version__}')
