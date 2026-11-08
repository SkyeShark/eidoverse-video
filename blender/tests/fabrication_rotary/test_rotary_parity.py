"""Parity of the rotary planner with the WebGPU edition: compares the Blender port's numbers with the JSON that
rotary_js_dump.mjs wrote from the untouched JS (eidoverse/robotics/rotary_*.js) in Deno (see its header). Nothing
renders and no scene is built, but eidoblend.fabrication loads bpy when imported, so run it inside Blender:

    bash run_blender.sh <worktree>/blender/tests/fabrication_rotary/test_rotary_parity.py

Every position in the dump is in three's axes: the port's stock coordinates are (x, y, z)_three -> (x, -z, y).
Prints PASS / FAIL per check and exits 1 on any FAIL.
"""

import json
import math
import os
import sys
import time

sys.dont_write_bytecode = True                  # no __pycache__ in the repository
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', '..')))

import numpy as np                                                         # noqa: E402

from eidoblend.fabrication.cutting import stock_profile                    # noqa: E402
from eidoblend.fabrication.rotary import path as RP                         # noqa: E402
from eidoblend.fabrication.rotary.setup import rotary_fixture_setup         # noqa: E402

DUMP = os.path.join(HERE, 'out', 'js_parity')
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + detail) if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def load(name):
    with open(os.path.join(DUMP, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def b3(p):
    """three (x, y, z) -> Blender (x, -z, y)"""
    return (p[0], -p[2], p[1])


def snake(k):
    out = ''
    for ch in k:
        out += ('_' + ch.lower()) if ch.isupper() else ch
    return out


def opts(o):
    return {snake(k): v for k, v in o.items()}


def close(a, b, tol):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


# --------------------------------------------------------------------------------------------------- basics ---
B = load('basics')
worst = 0.0
ok = True
for rec in B['setups']:
    mine = rotary_fixture_setup(**opts(rec['o']))
    js = rec['r']
    for k, v in js.items():
        if k == 'joints':
            for j, jv in v.items():
                worst = max(worst, abs(mine['joints'][j] - jv))
        else:
            worst = max(worst, abs(mine[snake(k)] - v))
check('rotary_fixture_setup matches the JS for 5 blanks', worst < 1e-15, f'worst {worst:.2e}')
errs_ok = True
for rec in B['setupErrors']:
    o = {snake(k): (float('nan') if v is None else v) for k, v in rec['o'].items()}
    try:
        rotary_fixture_setup(**o)
        msg = None
    except ValueError as e:
        msg = str(e)
    errs_ok &= (msg == rec['e'])
check('rotary_fixture_setup rejects the same blanks with the same messages', errs_ok)
S = opts(B['blankS'])
worst = max(abs(RP.rotary_blank_distance(b3(p), S) - d) for p, d in B['blank'])
check('rotary_blank_distance (box, 60-degree seat, pilot) matches at 500 points', worst < 1e-15, f'worst {worst:.2e}')
w1 = max(abs(RP.sample_rotary(x, t) - r) for x, t, r, _ in B['sample'])
w2 = max(abs(RP.sample_rotary(x, t, {'start': -.03, 'end': .05, 'stock_width': .03, 'stock_height': .044}) - r2)
         for x, t, _, r2 in B['sample'])
check('sample_rotary matches at 300 points (default and resized blank)', max(w1, w2) < 1e-15, f'worst {max(w1, w2):.2e}')
verts, tris = RP.rotary_surface_arrays(RP.sample_rotary, nx=12, na=20)
jsv = np.asarray(B['surface']['position']).reshape(-1, 3)
jsv = np.stack([jsv[:, 0], -jsv[:, 2], jsv[:, 1]], 1)
check('rotary_surface vertices and triangles match', np.abs(verts - jsv).max() < 2e-7 and
      np.array_equal(tris.ravel(), np.asarray(B['surface']['index'])), f'max {np.abs(verts - jsv).max():.2e}')
mat_ok = all(dict(stock_profile(n)) == {snake(k): v for k, v in js.items()} for n, js in B['materials'].items())
check('stock_profile (the fabrication family version rotary uses) equals cutting.js, aliases included', mat_ok)

# ------------------------------------------------------------------------------------------------- programs ---
P = load('programs')
TARGETS = {'custom_fn': lambda x, a: .0125 + .002 * np.cos(2 * a) + .001 * np.sin(40 * x)}
for name, rec in P['programs'].items():
    t0 = time.time()
    src = TARGETS.get(name, RP.sample_rotary)
    p = RP.rotary_program(src, **opts(rec['o']))
    dt = time.time() - t0
    jm = rec['moves']
    same_n = len(jm) == len(p.moves)
    pos = max((max(abs(a - b) for a, b in zip(m['position'], b3(j['position']))) for m, j in zip(p.moves, jm)),
              default=0.0)
    meta = all(m['type'] == j['type'] and m['stage'] == j['stage'] and m['angle'] == j['angle'] and
               m['feed'] == j.get('feed') for m, j in zip(p.moves, jm))
    check(f'program {name}: {len(jm)} moves, positions, angles, types, stages, feeds', same_n and pos < 1e-15 and meta,
          f'n {len(p.moves)}/{len(jm)} pos {pos:.2e} meta {meta} ({dt:.2f} s)')
    st = [(s['name'], s['first_move']) for s in p.stages] == [(s['name'], s['firstMove']) for s in rec['stages']]
    se = all(close(p.settings[snake(k)], v, 1e-15) if isinstance(v, (int, float)) else
             (p.settings[snake(k)] == v if k != 'centreSeat' else True) for k, v in rec['settings'].items())
    check(f'program {name}: stages and settings', st and se)
    segs = p.path.segments
    sw = max(max(abs(s[k] - j[k]) for k in ('t0', 't1')) for s, j in zip(segs, rec['segments']))
    check(f'program {name}: {len(segs)} timed segments, duration {p.path.duration:.4f} s', len(segs) == len(rec['segments'])
          and sw < 1e-9 and close(p.path.duration, rec['duration'], 1e-12), f'worst t {sw:.2e}')
    smp = 0.0
    for js in rec['samples']:
        mine = p.path.sample(js['time'] if js['time'] < rec['duration'] else js['time'] + (0 if not js['done'] else 0))
        smp = max(smp, max(abs(a - b) for a, b in zip(mine['position'], b3(js['position']))), abs(mine['angle'] - js['angle']),
                  abs(mine['speed'] - js['speed']), abs(mine['fraction'] - js['fraction']))
        smp = max(smp, 0 if (mine['index'] == js['index'] and mine['type'] == js['type']) else 1)
    check(f'program {name}: path.sample at 8 times', smp < 1e-9, f'worst {smp:.2e}')
errs = []
for rec in P['errors']:
    o = opts(rec['o'])
    if o.get('stepdown') is None and 'stepdown' in rec['o']:
        o['stepdown'] = math.inf
    src = RP.sample_rotary
    if rec['o'] == {'angles': 16, 'sampleStep': .004}:
        src = (lambda x, a: .003) if len([e for e in errs if e[0] == 'c']) == 0 else (lambda x, a: .03)
        errs.append(('c',))
    try:
        RP.rotary_program(src, **o)
        msg = None
    except ValueError as e:
        msg = str(e)
    errs.append((msg, rec['e']))
bad = [e for e in errs if len(e) == 2 and e[0] != e[1]]
check('rotary_program rejects the same 11 bad requests with the same messages', not bad, str(bad[:3]))

# ---------------------------------------------------------------------------------------- paths and sweeps ---
Q = load('paths')
for name, rec in Q['handPaths'].items():
    moves = [dict(m, position=b3(m['position'])) for m in rec['moves']]
    kw = {'feed': .02, 'rapid': .1, 'acceleration': .5, 'rotation_speed': 1.1} if name == 'wiggle' else {}
    path = RP.RotaryPath(moves, **kw)
    sw = max(max(abs(s[k] - j[k]) for k in ('t0', 't1')) for s, j in zip(path.segments, rec['segments']))
    smp = 0.0
    for js in rec['samples']:
        mine = path.sample(js['time'])
        smp = max(smp, max(abs(a - b) for a, b in zip(mine['position'], b3(js['position']))), abs(mine['angle'] - js['angle']),
                  abs(mine['speed'] - js['speed']))
    check(f'RotaryPath {name}: segments, duration and 41 samples', len(path.segments) == len(rec['segments']) and
          sw < 1e-12 and smp < 1e-12 and close(path.duration, rec['duration'], 1e-14), f'seg {sw:.1e} sample {smp:.1e}')
bad_moves = [
    [{'position': (0, 0, 0), 'angle': 0, 'type': 'rapid'}, {'position': (.01, 0, 0), 'angle': .5, 'type': 'index'}],
    [{'position': (0, 0, 0), 'angle': 0, 'type': 'rapid'}, {'position': (0, 0, 0), 'angle': .5, 'type': 'cut'}],
    [{'position': (0, 0, 0), 'angle': 0, 'type': 'rapid'}, {'position': (.01, -.01, 0), 'angle': 0, 'type': 'cut'}],
    [{'position': (0, 0, 0), 'angle': 0, 'type': 'rapid'}, {'position': (.01, 0, 0), 'angle': 0, 'type': 'plunge'}],
    [{'position': (0, 0, 0), 'angle': 0, 'type': 'rapid'}, {'position': (0, 0, 0), 'angle': 0, 'type': 'rapid'}],
    [{'position': (0, 0, 0), 'angle': 0, 'type': 'rapid'}, {'position': (math.nan, 0, 0), 'angle': 0, 'type': 'rapid'}],
    [{'position': (0, 0, 0), 'angle': 0, 'type': 'rapid'}, {'position': (.01, 0, 0), 'angle': 0, 'type': 'rapid'}],
]
msgs = []
for k, m in enumerate(bad_moves):
    try:
        RP.RotaryPath(m, **({'rapid': -1} if k == 6 else {}))
        msgs.append(None)
    except ValueError as e:
        msgs.append(str(e))
check('RotaryPath rejects the same 7 bad programs with the same messages', msgs == [r['e'] for r in Q['errors']],
      str([(a, b['e']) for a, b in zip(msgs, Q['errors']) if a != b['e']]))
worst, n = 0.0, 0
for rec in Q['sweeps']:
    s = {'a': b3(rec['s']['a']), 'b': b3(rec['s']['b']), 'a0': rec['s']['a0']}
    d = RP.sweep_distance(b3(rec['p']), s, rec['R'], rec['fl'], rec['f'], rec['tool'])
    worst = max(worst, abs(d - rec['d']))
    n += 1
check(f'sweep_distance (ball and flat) matches at {n} random strokes and points', worst < 1e-15, f'worst {worst:.2e}')

# ------------------------------------------------------------------------------------------ index and removal ---
from eidoblend.fabrication.rotary.removal import rotary_removal          # noqa: E402
from eidoblend.fabrication.rotary.sweeps import index_rotary_sweeps     # noqa: E402

X = load('index_removal')
small = RP.rotary_program(RP.sample_rotary, angles=16, sample_step=.004)
for key, bmin, bmax, dims, band in (('index', (-.07, -.027, -.027), (.07, .027, .027), (32, 16, 16), 0),
                                    ('indexB', (-.072, -.02, -.02), (.072, .02, .02), (40, 16, 16), .002)):
    idx = index_rotary_sweeps(small.path, small.settings, {'min': bmin, 'max': bmax}, dims, band)
    js = X[key]
    jc = js['counts']
    dx, dy, dz = dims
    mism = 0
    for z3 in range(dz):
        for y3 in range(dy):
            for x in range(dx):
                mine = len(idx.bins[x + dx * ((dy - 1 - z3) + dy * y3)])
                mism += mine != jc[x + dx * (y3 + dy * z3)]
    check(f'index_rotary_sweeps {key}: per-bin stroke counts (three z mirrored to -Y), max bin {idx.max_bin}',
          mism == 0 and idx.max_bin == js['maxBin'] and np.allclose(idx.cell, js['cell']), f'{mism} bins differ')
check('index_rotary_sweeps texture rows: headers, links, records sizes', len(idx.records) == len(small.path.segments) * 8)
RS_ = X['removalSettings']


def mk(repeat):
    moves = [{'position': b3(m['position']), 'angle': m['angle'], 'type': m['type']} for m in
             Q['handPaths']['removal_twice' if repeat else 'removal_once']['moves']]
    return RP.RotaryPath(moves)


for name, path, settings, res in (('hand_once', mk(False), opts(RS_), (36, 20, 20)),
                                  ('hand_twice', mk(True), opts(RS_), (36, 20, 20)),
                                  ('small_ball', small.path, small.settings, (48, 16, 16)),
                                  ('small_flat', None, None, (40, 18, 14))):
    if name == 'small_flat':
        fp = RP.rotary_program(RP.sample_rotary, angles=16, sample_step=.004, tool='flat', flute_length=.018)
        path, settings = fp.path, fp.settings
    t0 = time.time()
    r = rotary_removal(path, settings, res)
    dt = time.time() - t0
    js = X['removals'][name]
    je = js['events']
    n_ok = len(r.events) == len(je)
    pos = max((max(abs(a - b) for a, b in zip(e['position'], b3(j['position']))) for e, j in zip(r.events, je)), default=0)
    tw = max((abs(e['time'] - j['time']) for e, j in zip(r.events, je)), default=0)
    vw = max((abs(e['volume'] - j['volume']) for e, j in zip(r.events, je)), default=0)
    check(f'rotary_removal {name}: {len(je)} events, positions, times, volumes; removed volume ({dt:.2f} s)',
          n_ok and pos < 1e-12 and tw < 1e-9 and vw < 1e-18 and close(r.removed_volume, js['removedVolume'], 1e-9),
          f'n {len(r.events)}/{len(je)} pos {pos:.1e} t {tw:.1e} vol {r.removed_volume:.6e}/{js["removedVolume"]:.6e}')
    # queries counts sweep tests per voxel through the bins; a stroke box edge that lands exactly on a bin edge
    # floors differently once three's z is mirrored to -Y, so the count agrees to within a percent, not exactly
    check(f'rotary_removal {name}: diagnostic query count {r.queries} vs {js["queries"]} (within 1 %)',
          abs(r.queries - js['queries']) <= max(2, .01 * js['queries']))

# ---------------------------------------------------------------------------------------------- mesh programs ---
from eidoblend.fabrication.rotary.mesh import mesh_envelope, rotary_mesh_program   # noqa: E402

M = load('mesh')


def tris(flat):
    a = np.asarray(flat, dtype=float).reshape(-1, 3)
    return np.stack([a[:, 0], -a[:, 2], a[:, 1]], 1).reshape(-1, 3, 3)


env = M['envelope']
e = mesh_envelope(tris(M['group']['triangles']), env['angle'], env['opts']['minX'], env['opts']['maxX'],
                  env['opts']['minZ'], env['opts']['maxZ'], env['opts']['step'])
jh = np.array([-np.inf if v is None else v for v in env['heights']])
fin = np.isfinite(jh)
check('mesh_envelope: same covered cells and heights (clipped triangles, upper bound per cell)',
      e.nx == env['nx'] and e.nz == env['nz'] and np.array_equal(fin, np.isfinite(e.heights)) and
      np.abs(e.heights[fin] - jh[fin]).max() < 1e-15, f'{fin.sum()} cells, max {np.abs(e.heights[fin] - jh[fin]).max():.1e}')
for name in ('group', 'group_moved', 'flat_box', 'knot_fit'):
    rec = M[name]
    t0 = time.time()
    corners = tris(rec['triangles'])
    p = rotary_mesh_program((corners.reshape(-1, 3), np.arange(len(corners) * 3).reshape(-1, 3)), **opts(rec['o']))
    dt = time.time() - t0
    jp = rec['program']
    jm = jp['moves']
    pos = max((max(abs(a - b) for a, b in zip(m['position'], b3(j['position']))) for m, j in zip(p.moves, jm)),
              default=0.0)
    meta = all(m['type'] == j['type'] and m['stage'] == j['stage'] and abs(m['angle'] - j['angle']) < 1e-15
               for m, j in zip(p.moves, jm))
    rep = jp['report']
    rep_ok = (p.report.reach_limited_samples == rep['reachLimitedSamples'] and
              close(p.report.minimum_requested_tip, rep['minimumRequestedTip'], 1e-12) and
              p.report.source['triangles'] == rep['source']['triangles'] and
              close(p.report.reach_floor, rep['reachFloor'], 1e-15))
    check(f'rotary_mesh_program {name}: {len(jm)} moves, report ({dt:.2f} s)', len(p.moves) == len(jm) and pos < 1e-12
          and meta and rep_ok and [s['name'] for s in p.stages] == [s['name'] for s in jp['stages']],
          f'n {len(p.moves)}/{len(jm)} pos {pos:.1e} meta {meta} reach {p.report.reach_limited_samples}/'
          f'{rep["reachLimitedSamples"]} tip {p.report.minimum_requested_tip:.6f}/{rep["minimumRequestedTip"]:.6f}')
    check(f'rotary_mesh_program {name}: path duration {p.path.duration:.3f} s', close(p.path.duration, jp['duration'], 1e-9)
          and len(p.path.segments) == jp['nsegs'])
    if name == 'knot_fit':
        f_ok = all(close(a, b, 1e-12) for a, b in zip(p.report.source['fit']['offset'],
                                                       b3(rep['source']['fit']['offset'])))
        check('fit_source_geometry: the fitted knot has the same scale and offset',
              close(p.report.source['fit']['scale'], rep['source']['fit']['scale'], 1e-12) and f_ok)

print('\n%d FAIL' % len(FAILS) if FAILS else '\nALL PASS')
if __name__ == '__main__' and 'bpy' not in sys.modules:
    sys.exit(1 if FAILS else 0)
