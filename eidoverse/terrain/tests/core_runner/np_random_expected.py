"""numpy's own draws, for core/np_random.js to reproduce draw for draw (PORT_PLAN.md 8.2, P1; tests/core_runner/
np_random_test.mjs reads what this writes).

    <Blender's python> -I eidoverse/terrain/tests/core_runner/np_random_expected.py [out_dir]

Run it with the Python whose numpy the plans are drawn by, Blender's own (in a Blender folder, <version>/python/bin/
python), never another (PORT_PLAN.md 5.1). numpy only; no Blender, no GPU. The default out_dir is
tests/out/core_runner/np_random_<numpy version>/; the manifest records the Python, numpy and zlib versions.

Fifty seeds in every form the Blender terrain hands to np.random.default_rng (blender/eidoblend/terrain: ints,
int expressions, [seed, salt], [seed, salt, k], salts wider than 32 bits), and for each the same program of draws:
every Generator method the terrain calls (random, uniform, integers, standard_normal, normal, exponential, poisson,
choice) in every call form it uses (scalar, a count, a shape; choice with and without replacement and weights), in
one stream, so the half-word buffer of the 32-bit draws and the rejection loops stay in step across methods. Then
4,000 normals and 4,000 exponentials per seed, and one long stream of a million of each, to reach every ziggurat
strip, wedge and tail.

Writes manifest.json (numpy's version, the seeds, the program) and one little-endian float64 .bin per stream (every
draw's values flattened in C order; integers are exact in a double).
"""
import json
import os
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'out', 'core_runner', 'np_random_' + np.__version__)
os.makedirs(OUT, exist_ok=True)

KARST, CONE, RIBS, SCAR, EDGE, BODY, WALL = 0x4B41525354, 0x434F4E45, 0x52494253, 0x53434152, 0x45444745, 0x424F4459, 0x57414C4C
SEEDS = [
    0, 1, 2, 3, 5, 7, 11, 42, 1907, 65535, 65536, 4294967295, 4294967296, 12345678901, 2 ** 63 + 5, 2 ** 64 - 1, 2 ** 100 + 3,
    abs(-3) * 7919 + 17, (9 * 7919 + 17) & 0xFFFFFFFF, 4 * 7919 + 4243, 6 * 7919 + 101, 8 * 31 + 7, 5 * 4421 + 613,
    3 * 977 + sum(ord(c) for c in 'sandstone') % 7919, (2 + 14) * 7919 + 4243, 7 + 7919 * 3, 7 + 104729 + 7919 * 3,
    [1, 65], [2, 67], [3, KARST], [4294967295, KARST], [4, CONE], [5, RIBS], [6, SCAR], [7, EDGE], [8, BODY],
    [9, WALL, 0], [9, WALL, 12], [9, WALL, 311], [1, 7177, 3], [2, 7179, 3], [3, 9097], [4, 9091], [5, 9113, 0], [5, 9113, 4],
    [abs(-7), 31], [0, 0], [0, 1], [1, 0], [123456789, 987654321, 5],
]
assert len(SEEDS) == 50

P5 = [0.1, 0.2, 0.3, 0.25, 0.15]
W6 = np.array([3.0, 1.0, 0.0, 2.0, 2.5, 1.5])
PROGRAM = [
    {'m': 'random'}, {'m': 'random'}, {'m': 'random', 'size': 5}, {'m': 'random', 'size': [2, 3]},
    {'m': 'uniform', 'low': -1.0, 'high': 1.0}, {'m': 'uniform', 'low': 0.7, 'high': 1.3, 'size': 4},
    {'m': 'uniform', 'low': 0.0, 'high': 6.283185307179586, 'size': [3, 2]}, {'m': 'uniform', 'low': -12.0, 'high': 12.0},
    # 32-bit draws: one leaves a buffered half word that a later 32-bit draw takes, with 64-bit draws in between
    {'m': 'integers', 'low': 10}, {'m': 'random'}, {'m': 'integers', 'low': 2, 'high': 5}, {'m': 'integers', 'low': 0, 'high': 3, 'size': 7},
    {'m': 'integers', 'low': 1 << 31}, {'m': 'integers', 'low': 1 << 30}, {'m': 'integers', 'low': 2, 'high': 4, 'size': 5},
    {'m': 'integers', 'low': 5, 'high': 6}, {'m': 'integers', 'low': 0, 'high': 2 ** 32}, {'m': 'integers', 'low': 0, 'high': 2 ** 32 + 10, 'size': 3},
    {'m': 'integers', 'low': -5, 'high': 5, 'size': 6}, {'m': 'integers', 'low': 3, 'high': 1000003, 'size': 5}, {'m': 'integers', 'low': 7},
    {'m': 'standard_normal'}, {'m': 'standard_normal', 'size': 8}, {'m': 'normal', 'loc': 0.0, 'scale': 12.0, 'size': [3, 4]},
    {'m': 'normal', 'loc': 2.5, 'scale': 0.55}, {'m': 'normal', 'loc': 0.0, 'scale': 1.0, 'size': 3},
    {'m': 'exponential', 'scale': 3.0}, {'m': 'exponential', 'scale': 1.0, 'size': 6},
    {'m': 'poisson', 'lam': 0.0}, {'m': 'poisson', 'lam': 3.7}, {'m': 'poisson', 'lam': 9.99}, {'m': 'poisson', 'lam': 10.0},
    {'m': 'poisson', 'lam': 250.0}, {'m': 'poisson', 'lam': 1.0e5}, {'m': 'poisson', 'lam': 4.2, 'size': 5}, {'m': 'poisson', 'lam': 31.4, 'size': 5},
    {'m': 'choice', 'a': 40, 'size': 7, 'replace': False},                     # Floyd's algorithm, then a shuffle
    {'m': 'choice', 'a': 20000, 'size': 3000, 'replace': False},               # the tail shuffle
    {'m': 'choice', 'a': 20000, 'size': 300, 'replace': False},                # Floyd's again (300 <= 20000 // 50)
    {'m': 'choice', 'a': 12, 'size': 12, 'replace': False, 'shuffle': False},
    {'m': 'choice', 'a': 5, 'p': P5}, {'m': 'choice', 'a': 5, 'p': P5, 'size': 6},
    {'m': 'choice', 'a': 6, 'p': (W6 / W6.sum()).tolist()},
    {'m': 'choice', 'a': [-1.0, 1.0]}, {'m': 'choice', 'a': [10.5, 20.5, 30.5, 40.5], 'size': 5},
    {'m': 'choice', 'a': 9, 'size': 5}, {'m': 'choice', 'a': 6, 'size': 4, 'replace': False, 'p': (W6 / W6.sum()).tolist()},
    {'m': 'random'}, {'m': 'standard_normal', 'size': 4000}, {'m': 'exponential', 'scale': 1.0, 'size': 4000}, {'m': 'random'},
]
LONG = [{'m': 'standard_normal', 'size': 1000000}, {'m': 'exponential', 'scale': 1.0, 'size': 1000000},
        {'m': 'normal', 'loc': 0.0, 'scale': 12.0, 'size': 1000}, {'m': 'random', 'size': 10}]


def draw(g, op):
    m, size = op['m'], op.get('size')
    size = tuple(size) if isinstance(size, list) else size
    if m == 'random':
        v = g.random(size)
    elif m == 'uniform':
        v = g.uniform(op['low'], op['high'], size)
    elif m == 'integers':
        v = g.integers(op['low'], op.get('high'), size)
    elif m == 'standard_normal':
        v = g.standard_normal(size)
    elif m == 'normal':
        v = g.normal(op['loc'], op['scale'], size)
    elif m == 'exponential':
        v = g.exponential(op['scale'], size)
    elif m == 'poisson':
        v = g.poisson(op['lam'], size)
    elif m == 'choice':
        v = g.choice(op['a'], size, replace=op.get('replace', True), p=op.get('p'), shuffle=op.get('shuffle', True))
    else:
        raise ValueError(m)
    return np.asarray(v, np.float64).ravel()


def stream(seed, program, name):
    g = np.random.default_rng(seed)
    parts = [draw(g, op) for op in program]
    a = np.concatenate(parts).astype('<f8')
    a.tofile(os.path.join(OUT, name))
    return {'seed': seed if isinstance(seed, list) else str(seed), 'file': name, 'counts': [int(p.size) for p in parts]}


cases = [stream(s, PROGRAM, 'seed%02d.bin' % i) for i, s in enumerate(SEEDS)]
long_case = stream([12345, 0x57414C4C], LONG, 'long.bin')
with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump({'numpy': np.__version__, 'python': sys.version.split()[0], 'zlib': zlib.ZLIB_RUNTIME_VERSION,
               'python_executable': os.path.basename(sys.executable), 'program': PROGRAM, 'cases': cases,
               'long_program': LONG, 'long': long_case}, f, indent=1)
print('[np_random_expected] numpy %s: %d seeds x %d draws (%d values each), a long stream of %d -> %s' % (
    np.__version__, len(cases), len(PROGRAM), sum(cases[0]['counts']), sum(long_case['counts']), OUT))
