"""Parity of the fabrication planners with the WebGPU originals, number for number (no render).

fab_parity_dump.mjs runs eidoverse/robotics/*.js untouched in Deno; this script makes the same calls in the Blender
port and compares: FeedPath timing and samples, FilamentPath dwells, swept cutter heights, the pocket program, stock
removal (volume, events, final heights), the relief program, the original relief sample, slicing (layers, perimeter
and infill lengths per layer, print time) and mesh sections. three's (x, y, z) is Blender's (x, -z, y).

    cd C:/Users/sdn52/OneDrive/Desktop/eidoverse-video-prealpha-0.01
    bash run_blender.sh <worktree>/blender/tests/fabrication/test_fabrication_parity.py
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _util as U  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend import fabrication as fab  # noqa: E402
from eidoblend.fabrication import three_geometry as tg  # noqa: E402
from eidoblend.fabrication.cutting import distance_time, stock_profile  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
js = U.deno_dump(os.path.join(U.HERE, 'fab_parity_dump.mjs'), 'js_dump.json')
t2b = U.t2b


def vclose(a, b, e):
    return all(abs(x - y) <= e for x, y in zip(a, b))


def conv_points(points):
    return [dict(p, position=t2b(p['position'])) for p in points]


# --- FeedPath -------------------------------------------------------------------------------------------------
pts = conv_points([
    {'position': [0, .03, 0], 'type': 'rapid'}, {'position': [.01, .03, -.01], 'type': 'rapid'},
    {'position': [.01, .018, -.01], 'type': 'cut', 'feed': .001}, {'position': [.03, .018, -.01], 'type': 'cut'},
    {'position': [.03, .018, .02], 'type': 'cut'}, {'position': [.0, .018, .025], 'type': 'cut'},
    {'position': [0, .03, .025], 'type': 'rapid'}, {'position': [.02, .002, .0], 'type': 'extrude'},
    {'position': [.04, .002, .0], 'type': 'extrude'}, {'position': [.04, .002, .02], 'type': 'extrude'},
    {'position': [.02, .002, .03], 'type': 'extrude'}])
for name, opts in (('blend', dict(feed=.012, rapid=.1, acceleration=.3, blend_tolerance=.000025, bead_area=2e-7)),
                   ('sharp', dict(feed=.02, rapid=.08, acceleration=.25, blend_tolerance=0))):
    ref = js['feed_' + name]
    p = fab.FeedPath(pts, **opts)
    U.check(f'feed {name}: duration, length, volume, segment kinds',
            U.near(p.duration, ref['duration'], 1e-12) and U.near(p.length, ref['length'], 1e-12)
            and U.near(p.volume, ref['volume'], 1e-18) and [s.kind for s in p.segments] == ref['kinds'],
            f"{p.duration:.9f} vs {ref['duration']:.9f}, {len(p.segments)} segments")
    worst = 0.0
    for i, r in enumerate(ref['samples']):
        s = p.sample(p.duration * i / 40)
        worst = max(worst, max(abs(a - b) for a, b in zip(s.position, t2b(r['position']))),
                    abs(s.speed - r['speed']), abs(s.distance - r['distance']),
                    max(abs(a - b) for a, b in zip(s.acceleration, t2b(r['acceleration']))))
        if s.type != r['type'] or s.index != r['index']:
            worst = 1.0
    U.check(f'feed {name}: 41 samples (position, speed, distance, acceleration)', worst < 1e-12, f'worst {worst:.2e}')
    walked = []
    p.walk(p.duration * .2, p.duration * .5, .004, lambda a, b, t: walked.append(t))
    U.check(f'feed {name}: walk visits', len(walked) == ref['walked'], f"{len(walked)} vs {ref['walked']}")
    lines = [s for s in p.segments if s.kind == 'line'][:6]
    dt = [[distance_time(s, s.length * f) for f in (0, .25, .5, 1)] for s in lines]
    U.check(f'feed {name}: distance_time inverse', np.allclose(dt, ref['distance_time'], atol=1e-12))

# --- FilamentPath ---------------------------------------------------------------------------------------------
ref = js['filament']
geo = fab.FeedPath(pts, feed=.025, rapid=.1, acceleration=.5, blend_tolerance=.000015, bead_area=math.pi * .0008 * .0004 / 4)
f = fab.FilamentPath(geo)
U.check('filament path: duration, retraction time, filament length',
        U.near(f.duration, ref['duration'], 1e-12) and U.near(f.retraction_time, ref['retractionTime'], 1e-12)
        and U.near(f.filament_length, ref['filamentLength'], 1e-12))
U.check('filament path: spans', [[s.type, round(s.t0, 10), round(s.t1, 10)] for s in f.spans]
        == [[a, round(b, 10), round(c, 10)] for a, b, c in ref['spans']])
worst = 0.0
for i, r in enumerate(ref['samples']):
    s = f.sample(f.duration * i / 60)
    worst = max(worst, abs(s.filament_length - r['filamentLength']), abs(s.filament_retraction - r['filamentRetraction']),
                abs(s.filament_speed - r['filamentSpeed']), abs(s.speed - r['speed']),
                max(abs(a - b) for a, b in zip(s.position, t2b(r['position']))))
    if s.type != r['type']:
        worst = 1.0
U.check('filament path: 61 samples', worst < 1e-12, f'worst {worst:.2e}')

# --- swept cutter heights -------------------------------------------------------------------------------------
worst = 0.0
for kind, x, z, a, b, r, h in js['swept']:
    mine = fab.swept_cutter_height(x, -z, t2b(a), t2b(b), r, kind)
    if h is None:
        worst = max(worst, 0.0 if mine == math.inf else 1.0)
    else:
        worst = max(worst, abs(mine - h))
U.check(f"swept cutter heights: {len(js['swept'])} cases", worst < 1e-15, f'worst {worst:.2e}')

# --- pocket and removal ---------------------------------------------------------------------------------------
prof = stock_profile('aluminum')
pocket = fab.pocket_program(feed=prof.feed, plunge=prof.plunge, stepdown=prof.stepdown, cut_depth=prof.cut_depth,
                            stock_height=.020, radius=.003)
ok = len(pocket) == len(js['pocket']) and all(vclose(p['position'], t2b(q['position']), 1e-15) and p['type'] == q['type']
                                                  and p.get('feed') == q.get('feed') for p, q in zip(pocket, js['pocket']))
U.check('pocket program (aluminum defaults)', ok, f"{len(pocket)} points")
dflt = fab.pocket_program()
U.check('pocket program (defaults)', len(dflt) == len(js['pocket_default']) and all(
    vclose(p['position'], t2b(q['position']), 1e-15) for p, q in zip(dflt, js['pocket_default'])))
path = fab.FeedPath(pocket, feed=prof.feed, rapid=.08, acceleration=.25, blend_tolerance=0)
removal = fab.sample_removal(path, width=.078, depth=.128, height=.020, radius=.003, resolution=128, flute_length=.018,
                             cutter='flat')
ref = js['removal']
U.check('removal: volume, events, engaged segments',
        U.near(removal.removed_volume, ref['removedVolume'], 1e-15) and len(removal.events) == ref['events']
        and sum(i.engaged for i in removal.intervals) == ref['engaged'],
        f"{removal.removed_volume:.6e} vs {ref['removedVolume']:.6e}, {len(removal.events)} vs {ref['events']}")
U.check('removal: final heightfield', U.near(float(removal.final_heights.astype(np.float64).sum()), ref['heights_sum'], 1e-6)
        and U.near(float(removal.final_heights.min()), ref['heights_min'], 1e-9))
worst = 0.0
for e, r in zip(removal.events[:5] + removal.events[-3:], ref['first'] + ref['last']):
    worst = max(worst, abs(e.time - r['time']), abs(e.volume - r['volume']) * 1e6, abs(e.distance - r['distance']),
                abs(e.floor - r['floor']), max(abs(a - b) for a, b in zip(e.position, t2b(r['position']))))
U.check('removal: first and last events (time, volume, distance, floor, position)', worst < 1e-9, f'worst {worst:.2e}')
cuts = [s for s in fab.chords(path) if s.type == 'cut']
bins = fab.index_cutter_sweeps(cuts, .078, .128, .003)
U.check('cutter bins: candidates and largest bin', len(cuts) == js['bins']['cuts'] and len(bins['indices']) == js['bins']['total']
        and bins['maximum_bin'] == js['bins']['maximumBin'],
        f"{len(bins['indices'])} / {bins['maximum_bin']} vs {js['bins']['total']} / {js['bins']['maximumBin']}")

# --- relief ---------------------------------------------------------------------------------------------------
wood = stock_profile('wood')
prog = fab.relief_program(fab.sample_relief, feed=wood.feed, plunge=wood.plunge, stepdown=wood.stepdown, flute_length=.017)
ref = js['relief']
stages_ok = [(s['name'], s['start_index'], s['end_index']) for s in prog['stages']] == \
    [(s['name'], s['startIndex'], s['endIndex']) for s in ref['stages']] and all(
        U.near(s['end_distance'], r['endDistance'], 1e-9) for s, r in zip(prog['stages'], ref['stages']))
U.check('relief program: point count and rough / finish stages', len(prog['points']) == ref['points'] and stages_ok,
        f"{len(prog['points'])} vs {ref['points']} points, {len(prog['stages'])} stages")
s = [0.0, 0.0, 0.0]
for p in prog['points']:
    for k in range(3):
        s[k] += p['position'][k]
ok = vclose(s, t2b(ref['sum']), 1e-9) and all(vclose(p['position'], t2b(q['position']), 1e-15) and p['type'] == q['type']
                                               for p, q in zip(prog['points'][:8] + prog['points'][-4:] + prog['points'][5000:5006],
                                                               ref['first'] + ref['last'] + ref['mid']))
U.check('relief program: points (sums, first, last, middle)', ok)
coarse = fab.relief_program(fab.sample_relief, feed=wood.feed, plunge=wood.plunge, stepdown=wood.stepdown, sample_step=.002,
                            stepover=.0015)
U.check('relief program (coarse): stages', len(coarse['points']) == js['relief_coarse']['points'] and all(
    s['name'] == r[0] and s['end_index'] == r[1] and U.near(s['end_distance'], r[2], 1e-9)
    for s, r in zip(coarse['stages'], js['relief_coarse']['stages'])))
slope = fab.relief_program(lambda x, y: .012 + .42 * x, stock_width=.036, stock_depth=.034, width=.024, depth=.020,
                           stock_height=.025, radius=.003, sample_step=.0015, stepover=.001)
U.check('relief program (slope): points', len(slope['points']) == js['relief_slope']['points'] and all(
    vclose(p['position'], t2b(q['position']), 1e-15) for p, q in zip(slope['points'][100:110], js['relief_slope']['sample'])))
U.check('sample_relief = sampleRelief(x, -y)', all(
    U.near(fab.sample_relief(x, -z), v, 1e-16) for (x, z), v in zip([[0, 0], [.01, .02], [-.02, -.03], [.013, -.019]],
                                                                   js['sample_relief'])))

# --- slicing --------------------------------------------------------------------------------------------------
sources = {
    'box': (tg.make_object('box', tg.box(1, 1, 1)), dict(size=.008, infill=.3)),
    'sleeve': (tg.make_object('sleeve', tg.lathe([[.014, 0], [.020, 0], [.020, .006], [.014, .006], [.014, 0]], 48)),
               dict(size=.04, infill=.25)),
    'handle': (fab.manufacturing_sample('handle', as_parts=True), dict(size=.04)),
    'bracket': (fab.manufacturing_sample('bracket'), dict(size=.04)),
    'ring': (fab.manufacturing_sample('ring'), dict(size=.04, layer_height=.0008)),
}
bpy.context.view_layer.update()
for name, (src, opts) in sources.items():
    ref = js['slices'][name]
    spec = fab.slice_geometry(src, **opts)
    extrude = rapid = 0.0
    per = {}
    for i in range(1, len(spec['points'])):
        a, b = spec['points'][i - 1]['position'], spec['points'][i]['position']
        l = math.dist(a, b)
        if spec['points'][i]['type'] == 'extrude':
            extrude += l
            k = f'{b[2]:.6f}'
            per[k] = per.get(k, 0.0) + l
        else:
            rapid += l
    worst = max(abs(per.get(k, 0.0) - v) for k, v in ref['perLayer'].items())
    U.check(f'slice {name}: layers, contours, extruded length, per-layer lengths',
            spec['layers'] == ref['layers'] and len(spec['contours']) == ref['contours']
            and U.near(extrude, ref['extrude'], 1e-9 * max(1, ref['extrude'])) and worst < 1e-9,
            f"{spec['layers']} layers, {len(spec['contours'])} contours, extrude {extrude:.9f} vs {ref['extrude']:.9f}, "
            f"worst layer {worst:.1e}")
    # moves match exactly, except where a placement goes through sin / cos: CPython's libm and V8's fdlibm differ by
    # an ulp now and then (sin(pi / 4) here), and an ulp decides whether a quad diagonal's slice point is exactly in
    # line with its neighbours (kept or merged); lengths and travel stay equal to 1e-9
    moves = sum(p['type'] == 'extrude' for p in spec['points'])
    slack = 2 if name == 'handle' else 0
    U.check(f"slice {name}: extrusion moves, points and travel",
            abs(moves - ref['extrudes']) <= slack and abs(len(spec['points']) - ref['points']) <= slack
            and U.near(rapid, ref['rapid'], 1e-9 * max(1, ref['rapid'])),
            f"{sum(p['type'] == 'extrude' for p in spec['points'])} vs {ref['extrudes']} moves, {len(spec['points'])} vs "
            f"{ref['points']} points; travel {rapid:.9f} vs {ref['rapid']:.9f} m")
    if 'duration' in ref:
        g = fab.FeedPath(spec['points'], feed=.025, rapid=.10, acceleration=.5, bead_area=math.pi * .0008 * .0004 / 4,
                         blend_tolerance=.000015)
        fp = fab.FilamentPath(g)
        U.check(f'slice {name}: deposited volume and filament length', U.near(fp.volume, ref['volume'], 1e-6 * ref['volume'])
                and U.near(fp.filament_length, ref['filamentLength'], 1e-6 * ref['filamentLength']),
                f"{fp.volume:.6e} vs {ref['volume']:.6e}; print time {fp.duration:.1f} vs {ref['duration']:.1f} s")
fit = fab.fit_source_geometry(sources['handle'][0], size=.04, base=.00065)
ref = js['handle_fit']
U.check('fit: scale and offset', U.near(fit.manufacturing_source['fit']['scale'], ref['scale'], 1e-12)
        and vclose(fit.manufacturing_source['fit']['offset'], t2b(ref['offset']), 1e-12))
cut = fab.mesh_slicer(fit, polygons=True)
worst, shapes = 0.0, True
for z, polys in zip([.002, .006, .01, .014, .02], js['handle_sections']):
    mine = cut(z)
    if len(mine) != len(polys) or any(len(a) != len(b) for a, b in zip(mine, polys)):
        shapes = False
        continue
    for a, b in zip(mine, polys):
        for ra, rb in zip(a, b):
            ar = abs(sum(ra[i][0] * ra[i + 1][1] - ra[i + 1][0] * ra[i][1] for i in range(len(ra) - 1)) / 2)
            worst = max(worst, abs(ar - rb[1]))
U.check('mesh sections of the handle: polygons and areas', shapes and worst < 1e-12, f'worst area {worst:.1e}')
ok = U.summary('parity')
sys.exit(0 if ok else 1)
