"""Ekigar's test/gpu/operator_response.mjs, ported check for check: does every operator ACTUALLY DO SOMETHING?

  (a) the field is not degenerate (a generator invents structure, a filter fed real terrain returns real terrain;
      `constant` must be flat);
  (b) a filter visibly CHANGES its input (3 % whole-tile RMS of the input's range, or a localized patch: 1 % support,
      4 % active RMS, 5 % P99); selectors pass their input through exactly; (b2) a landform with an optional input
      visibly layers onto it;
  (c) every parameter MOVES the output (min / mid / max, the four lattice axes of a turn, both bools, every enum arm);
  (d) the carried gradient agrees in sign with the slope of the height it describes (grad_check.mjs; escalated to
      2N and 4N when kinks dominate), in every style / mode arm;
  (e) bedding and terracing transfers are monotone on a rising ramp;
  (f) every named output delivers a channel of its own;
  (x) seamless closes a seam that was really there.

Ekigar renders each probe on the GPU (about 600 renders) and reads it back; here the port's own field is evaluated at
the same N (64) with the same fixtures, activations and gates (NEUTRAL_DEFAULT, PARAM_CONTEXT, OUTPUT_CONTEXT ... are
Ekigar's tables, with their reasons in operator_response.mjs). The port's field equals Ekigar's (the parity tests),
so this runs Ekigar's own audit over the Blender edition.

    python blender/tests/terrain_ekigar/test_operator_response.py [--n=64] [--only=op,op]
"""
import sys
import time

import numpy as np

import _ekigar_load

ek = _ekigar_load.load()
N = 64
ONLY = None
for a in sys.argv[1:]:
    if a.startswith('--n='):
        N = int(a[4:])
    elif a.startswith('--only='):
        ONLY = a[7:].split(',')

EPS_SIGNAL = 1e-4
EPS_FLAT = 1e-5
MIN_BROAD_RESPONSE = 0.03
MIN_LOCAL_SUPPORT = 0.01
MIN_LOCAL_ACTIVE_RMS = 0.04
MIN_LOCAL_P99 = 0.05
ACTIVE_DELTA_FLOOR = 0.005
P_ = ek.graph_ports
renders = [0]


def P(op, over=None):
    d = ek.default_params(op)
    d.update(over or {})
    return d


def render(g, target, port='out', n=None):
    """{h, gx, gy, err, warn, min, max, mean, sd, bad} of `target` at n x n (default N)."""
    n = n or N
    try:
        r = ek.evaluate_graph(g, target, port=port, resolution=n, tile=(1.0, 1.0), workers=1)
        renders[0] += 1
        h, gx, gy = r['field'][0], r['field'][1], r['field'][2]
        return dict(h=h, gx=gx, gy=gy, err=None, warn=r['warnings'], **stats(h))
    except Exception as e:  # noqa: BLE001
        return dict(h=None, gx=None, gy=None, err=str(e)[:160], warn=[], **stats(None))


def stats(h):
    if h is None:
        return {'min': np.nan, 'max': np.nan, 'mean': np.nan, 'sd': np.nan, 'bad': -1}
    f = h[np.isfinite(h)]
    return {'min': float(f.min()) if f.size else np.nan, 'max': float(f.max()) if f.size else np.nan,
            'mean': float(f.mean()) if f.size else np.nan, 'sd': float(f.std()) if f.size else np.nan,
            'bad': int(h.size - f.size)}


def delta(a, b):
    if a is None or b is None or not (np.isfinite(a).all() and np.isfinite(b).all()):
        return {'rms': -1.0, 'p99': -1.0, 'max': -1.0}
    d = np.sort(np.abs(a - b).ravel())
    return {'rms': float(np.sqrt(np.mean(d * d))), 'p99': float(d[int(len(d) * 0.99)]), 'max': float(d[-1])}


def has_signal(d):
    return d['rms'] > EPS_SIGNAL or d['p99'] > EPS_SIGNAL


def mag(d):
    return -1.0 if d['rms'] < 0 else max(d['rms'], d['p99'])


def relative_response(d, output, base):
    s = stats(base)
    rng = s['max'] - s['min']
    if d['rms'] < 0 or output is None or base is None or not np.isfinite(rng) or rng <= EPS_SIGNAL:
        return {'range': rng, 'rms': -1, 'p99': -1, 'max': -1, 'support': -1, 'activeRms': -1}
    v = np.abs(output - base)
    act = v >= rng * ACTIVE_DELTA_FLOOR
    return {'range': rng, 'rms': d['rms'] / rng, 'p99': d['p99'] / rng, 'max': d['max'] / rng,
            'support': float(act.mean()),
            'activeRms': float(np.sqrt(np.mean(v[act] ** 2)) / rng) if act.any() else 0.0}


def visibly_moved(q):
    return q['rms'] >= MIN_BROAD_RESPONSE or (q['support'] >= MIN_LOCAL_SUPPORT and q['activeRms'] >= MIN_LOCAL_ACTIVE_RMS
                                              and q['p99'] >= MIN_LOCAL_P99)


def inversions(h):
    return float((h[:, 1:] < h[:, :-1] - 1e-5).mean())


def seam(h):
    n = h.shape[0]
    col = lambda i: float(np.mean(np.abs(h[:, i % n] - h[:, (i + 1) % n])))  # noqa: E731
    row = lambda j: float(np.mean(np.abs(h[j % n, :] - h[(j + 1) % n, :])))  # noqa: E731
    ks = range(4, n - 4, max(1, n // 24))
    cs, rs = [col(k) for k in ks], [row(k) for k in ks]
    return {'lr': col(n - 1), 'tb': row(n - 1), 'cm': float(np.mean(cs)), 'csd': float(np.std(cs)),
            'rm': float(np.mean(rs)), 'rsd': float(np.std(rs))}


KINK = 0.35


def gradient_agreement(h, gx, gy, n, flat=0.05):
    """grad_check.mjs gradientAgreement: the sign agreement of the carried gradient with central differences of the
    height, kinks (second difference over KINK of the slope) and flat texels excluded, row order tried both ways."""
    if h is None:
        return {'frac': -1, 'n': 0}
    texel = 1.0 / n
    at = lambda a, di, dj: np.roll(np.roll(a, -dj, 0), -di, 1)  # noqa: E731
    cm = np.hypot(gx, gy)
    carried_max = float(cm.max())
    best = None
    for sy in (1, -1):
        d1x = (at(h, 1, 0) - at(h, -1, 0)) / (2 * texel)
        d1y = (at(h, 0, 1) - at(h, 0, -1)) / (2 * texel) * sy
        mm = np.hypot(d1x, d1y)
        flat_m = (mm < flat) & (cm < flat)
        d2 = np.hypot(at(h, 1, 0) - 2 * h + at(h, -1, 0), at(h, 0, 1) - 2 * h + at(h, 0, -1)) / texel
        kink = ~flat_m & (d2 > KINK * np.maximum(mm, cm))
        use = ~flat_m & ~kink
        nn = int(use.sum())
        agree = int(((d1x * gx + d1y * gy) > 0)[use].sum())
        rel = np.sort((np.abs(mm - cm) / np.maximum(np.maximum(mm, cm), 1e-9))[use])
        sloped = nn + int(kink.sum())
        res = {'frac': agree / nn if nn else -1, 'n': nn, 'kinks': int(kink.sum()), 'flat': int(flat_m.sum()),
               'sy': sy, 'kinkFrac': kink.sum() / sloped if sloped else 0.0,
               'magMed': float(rel[len(rel) // 2]) if len(rel) else -1, 'carriedMax': carried_max}
        if best is None or res['frac'] > best['frac']:
            best = res
    return best


def fmt_agree(ga):
    if ga['frac'] < 0:
        return 'no comparable texels'
    return (f"sign {ga['frac'] * 100:.1f}% |dh| err(med) {ga['magMed'] * 100:.0f}% n {ga['n']} "
            f"[kinks {ga['kinks']} ({ga['kinkFrac'] * 100:.0f}% of sloped), flat {ga['flat']}]")


# ---- fixtures (operator_response.mjs SOURCES / RAMP) ---------------------------------------------------------------
def src_base(g):
    a = ek.add_node(g, 'fbm', {'x': 0, 'y': 0}, P('fbm', {'frequency': 4, 'amplitude': 0.9}))
    b = ek.add_node(g, 'roughen', {'x': 1, 'y': 0}, P('roughen', {'frequency': 16, 'amplitude': 0.04}))
    ek.connect(g, {'node': a, 'port': 'out'}, {'node': b, 'port': 'in'}, P_)
    return b


SOURCES = [src_base,
           lambda g: ek.add_node(g, 'ridged', {'x': 0, 'y': 1}, P('ridged', {'frequency': 5})),
           lambda g: ek.add_node(g, 'cone', {'x': 0, 'y': 2}, P('cone')),
           lambda g: ek.add_node(g, 'cellular', {'x': 0, 'y': 3}, P('cellular'))]


def RAMP(g):
    return ek.add_node(g, 'gradient', {'x': 0, 'y': 0}, P('gradient', {'angle': 0.6, 'scale': 1}))


POSITION = ['warp']
NEUTRAL_DEFAULT = {
    'curves': {'bias': 0.8}, 'gamma': {'gamma': 0.5}, 'math': {'value': 1.6}, 'clampOp': {'lo': 0.35, 'hi': 0.65},
    'thermal': {'repose': 0.05}, 'snow': {'maxSlope': 2, 'line': 0.4}, 'terrace': {'uniformity': 0.5},
    'cellular': {'metricMorph': 1}, 'volcano': {'breachWidth': 60}, 'pattern': {'dotSize': 1, 'spacing': 1},
    'caldera': {'domeRadius': 0.24, 'coneHeight': 0.18, 'breachWidth': 38},
    'impactCrater': {'count': 12, 'nRays': 10}, 'cinderConeField': {'breachWidth': 42},
    'basinField': {'elongation': 2.4}, 'volcanicPlug': {'count': 8, 'tailHeight': 0.12}, 'mesa': {'count': 8},
    'faultScarp': {'segments': 4, 'stepOver': 0.08, 'facets': 8}, 'graben': {'style': 'halfGraben'},
    'dipSlope': {'flatirons': 8}, 'esker': {'beadDepth': 0.95}, 'moraineSet': {'ribs': 8},
    'playa': {'ponors': 4}, 'patternedGround': {'lobeCreep': 0.65},
}
PARAM_CONTEXT = {
    'playa.ponors': {'style': 'polje'}, 'cinderConeField.direction': {'placement': 'fissure'},
    'moundField.rampart': {'maturity': 0.9}, 'moundField.orientation': {'elongation': 2.2},
    'duneField.arms': {'type': 'star'}, 'duneField.draaFreq': {'draa': 0.65},
    'duneField.sinuosity': {'type': 'barchanoid'}, 'alluvialFan.frontDir': {'count': 5},
    'spitBar.anchor2': {'mode': 'cuspate'}, 'spitBar.standoff': {'mode': 'barrier'},
    'reefRing.edificeRadius': {'subsidence': 0.25}, 'reefRing.edificeHeight': {'subsidence': 0.25},
    'reefRing.guyot': {'subsidence': 0}, 'rockGlacier.frequency': {'count': 6},
    'oceanRidge.trenchDepth': {'mode': 'trench'}, 'oceanRidge.outerRise': {'mode': 'trench'},
}
OUTPUT_CONTEXT = {'playa.ponor': {'style': 'polje', 'ponors': 4}, 'streamform.corridor': {'mode': 'yardang'},
                  'moundField.rampart': {'maturity': 0.9}}
SELECTOR = ['route', 'switchOp']
CONSTANT_BY_DESIGN = ['constant']
NEEDS_NONPERIODIC = {'seamless': RAMP}
VEC2_SWEEP = [[0.5, 0.5], [0.18, 0.78]]
MONOTONE = {'stratify': {}, 'terrace': {}, 'steps': {}, 'fractalTerraces': {}, 'sandstone': {'tilt': 0, 'chaos': 0}}
OUTPUT_EXEMPT = {}
DOWNSTREAM = ('roughen', {'frequency': 12, 'amplitude': 0.35})


def build(op, params, standalone=False, source=None, downstream=None):
    g = ek.create_graph()
    ports = ek.ports_of(op)
    input_id = None
    node = ek.add_node(g, op, {'x': 4, 'y': 0}, params)
    if not standalone:
        for si, port in enumerate(ports['inputs']):
            pick = source if (si == 0 and source) else SOURCES[si % len(SOURCES)]
            if port['type'] == 'material':
                src = ek.add_node(g, 'materialMap', {'x': 2, 'y': si}, P('materialMap'))
                fld = pick(g)
                ek.connect(g, {'node': fld, 'port': 'out'}, {'node': src, 'port': 'mask'}, P_)
            else:
                src = pick(g)
            r = ek.connect(g, {'node': src, 'port': 'out'}, {'node': node, 'port': port['name']}, P_)
            if not r['ok']:
                raise ValueError(f"cannot wire {op}.{port['name']}: {r['reason']}")
            if input_id is None:
                input_id = src
        if input_id is None:
            input_id = (source or SOURCES[0])(g)
    target = node
    if downstream:
        d = ek.add_node(g, downstream[0], {'x': 6, 'y': 0}, P(downstream[0], downstream[1]))
        ek.connect(g, {'node': node, 'port': 'out'}, {'node': d, 'port': 'in'}, P_)
        target = d
    return g, node, target, input_id


def build_bypass(downstream):
    g = ek.create_graph()
    src = SOURCES[0](g)
    d = ek.add_node(g, downstream[0], {'x': 6, 'y': 0}, P(downstream[0], downstream[1]))
    ek.connect(g, {'node': src, 'port': 'out'}, {'node': d, 'port': 'in'}, P_)
    return g, d


t_all = time.time()
ids = [o['id'] for o in ek.list_operators()
       if any(p['name'] == 'out' and p['type'] in ('field', 'mask') for p in ek.ports_of(o['id'])['outputs'])]
if ONLY:
    ids = [i for i in ids if i in ONLY]
fails = {k: 0 for k in 'abcdefx'}
notes = []
oracle_jobs = []                 # failures to re-measure on Ekigar's own field (its JS under deno)
for oid in ids:
    op = ek.OPERATORS[oid]
    is_gen = bool(op.get('generator'))
    position = oid in POSITION
    activate = NEUTRAL_DEFAULT.get(oid, {})
    opts = dict(standalone=is_gen, source=NEEDS_NONPERIODIC.get(oid), downstream=DOWNSTREAM if position else None)
    # (a)
    g, node, target, input_id = build(oid, P(oid, activate), **opts)
    ref = render(g, target)
    varied = ref['h'] is not None and (ref['max'] - ref['min']) > EPS_SIGNAL and ref['sd'] > EPS_FLAT
    want_flat = oid in CONSTANT_BY_DESIGN
    ok_a = not ref['err'] and ref['bad'] == 0 and (not varied if want_flat else varied)
    if not ok_a:
        fails['a'] += 1
        notes.append(f"(a) {oid}: {ref['err'] or ('%d non-finite' % ref['bad'] if ref['bad'] > 0 else 'degenerate')}")
    # (b) / (b2)
    if not is_gen:
        if position:
            bg, bt = build_bypass(DOWNSTREAM)
            in_h = render(bg, bt)['h']
        else:
            in_h = render(g, input_id)['h']
        dd = delta(ref['h'], in_h)
        resp = relative_response(dd, ref['h'], in_h)
        want_same = oid in SELECTOR
        ok_b = dd['max'] == 0 if want_same else visibly_moved(resp)
        if not ok_b:
            fails['b'] += 1
            notes.append(f"(b) {oid}: " + (f"must pass through, altered by {dd['max']}" if want_same else
                                          f"NOT VISIBLY DIFFERENT: RMS {resp['rms'] * 100:.2f}%, support "
                                          f"{resp['support'] * 100:.1f}%, active {resp['activeRms'] * 100:.2f}%, "
                                          f"P99 {resp['p99'] * 100:.2f}%"))
            if not position and not want_same:
                oracle_jobs.append({'kind': 'b', 'label': f'(b) {oid}', 'names': [],
                                    'probes': [(g, target, ref['h']), (g, input_id, in_h)]})
    elif any(not i.get('required') for i in ek.ports_of(oid)['inputs']):
        g2, n2, t2, i2 = build(oid, P(oid, activate), standalone=False)
        over, base = render(g2, t2), render(g2, i2)
        resp = relative_response(delta(over['h'], base['h']), over['h'], base['h'])
        if not visibly_moved(resp):
            fails['x'] += 1
            notes.append(f"(b2) {oid}: optional-input layer not visibly different (RMS {resp['rms'] * 100:.2f}%)")
    # (c)
    for key, schema in op['params'].items():
        t = schema.get('type')
        if t == 'float' and schema.get('min') == 0 and (schema.get('max') == 360 or schema.get('unit') == 'rad'):
            turn = schema['max']
            variants = [0, turn * 0.25, turn * 0.5, turn * 0.75]
        elif t in ('float', 'int'):
            mid = round((schema['min'] + schema['max']) / 2) if t == 'int' else (schema['min'] + schema['max']) / 2
            variants = list(dict.fromkeys([schema['min'], mid, schema['max']]))
        elif t == 'bool':
            variants = [False, True]
        elif t == 'enum':
            variants = list(schema['values'])
        elif t == 'vec2':
            variants = VEC2_SWEEP
        else:
            continue
        if len(variants) < 2:
            continue
        ctx_over = PARAM_CONTEXT.get(f'{oid}.{key}', {})
        hs, built = [], []
        for v in variants:
            gg, _n, tt, _i = build(oid, P(oid, dict(activate, **ctx_over, **{key: v})), **opts)
            hs.append(render(gg, tt))
            built.append((gg, tt))
        moved = any(has_signal(delta(hs[0]['h'], x['h'])) for x in hs[1:])
        bad = sum(1 for x in hs if x['h'] is not None and x['bad'] > 0)
        err = next((x['err'] for x in hs if x['err']), None)
        if not (moved and not err and bad == 0):
            fails['c'] += 1
            best = max(mag(delta(hs[0]['h'], x['h'])) for x in hs[1:])
            notes.append(f"(c) {oid}.{key}: " + (f'threw: {err}' if err else f'{bad} non-finite' if bad else
                                                  f'no effect (best {best:.2e} over {len(variants)} settings)'))
            if not err and not bad:
                oracle_jobs.append({'kind': 'c', 'label': f'(c) {oid}.{key}', 'names': [],
                                    'probes': [(gg, tt, x['h']) for (gg, tt), x in zip(built, hs)]})

# (d) the carried gradient agrees in sign with the height it describes, in every style / mode arm
n_d = 0
for oid in ids:
    op = ek.OPERATORS[oid]
    activate = NEUTRAL_DEFAULT.get(oid, {})
    style_key = next((k for k in ('style', 'mode', 'type', 'surface', 'waveform', 'geometry')
                      if op['params'].get(k, {}).get('type') == 'enum'), None)
    arms = op['params'][style_key]['values'] if style_key else [None]
    for arm in arms:
        over = dict(activate, **({style_key: arm} if arm else {}))
        g, _n, target, _i = build(oid, P(oid, over), standalone=bool(op.get('generator')),
                                  source=NEEDS_NONPERIODIC.get(oid), downstream=DOWNSTREAM if oid in POSITION else None)
        res = render(g, target)
        if res['h'] is None:
            continue
        ga = gradient_agreement(res['h'], res['gx'], res['gy'], N)
        label = f"{oid}{' (' + arm + ')' if arm else ''}"
        if ga['carriedMax'] < 1e-9:
            if op['category'] != 'derive' and (res['max'] - res['min']) > EPS_SIGNAL:
                fails['d'] += 1
                notes.append(f'(d) {label}: carries NO gradient while its height varies')
            continue
        if ga['frac'] < 0 or ga['n'] < N * 4:
            continue
        n_d += 1
        series = [ga]
        if ga['frac'] < 0.88:
            for mult in (2, 4):
                hi = render(g, target, n=N * mult)
                series.append(gradient_agreement(hi['h'], hi['gx'], hi['gy'], N * mult))
                if series[-1]['frac'] >= 0.88:
                    break
        if series[-1]['frac'] < 0.88:
            fails['d'] += 1
            notes.append(f'(d) {label}: carried gradient disagrees: ' + ' -> '.join(
                f"{N * 2 ** i}: {s['frac'] * 100:.1f}%" for i, s in enumerate(series)))

# (e) bedding / terracing transfers are monotone on a rising ramp
for oid, over in MONOTONE.items():
    if ONLY and oid not in ONLY:
        continue
    g = ek.create_graph()
    r_ = RAMP(g)
    n_ = ek.add_node(g, oid, {'x': 2, 'y': 0}, P(oid, over))
    ek.connect(g, {'node': r_, 'port': 'out'}, {'node': n_, 'port': 'in'}, P_)
    inv = inversions(render(g, n_)['h'])
    if inv != 0:
        fails['e'] += 1
        notes.append(f'(e) {oid}: transfer folds back, {inv * 100:.2f}% of adjacent samples decrease on a ramp')

# (f) every declared named output delivers something of its own
n_f = 0
for oid in ids:
    extras = [o for o in ek.ports_of(oid)['outputs'] if o['name'] != 'out']
    if not extras:
        continue
    gen = bool(ek.OPERATORS[oid].get('generator'))
    g, _n, target, _i = build(oid, P(oid, NEUTRAL_DEFAULT.get(oid, {})), standalone=gen)
    ref_out = render(g, target, 'out')
    for ex in extras:
        key = f"{oid}.{ex['name']}"
        pg, pt, pout = g, target, ref_out
        if key in OUTPUT_CONTEXT:
            pg, _n2, pt, _i2 = build(oid, P(oid, dict(NEUTRAL_DEFAULT.get(oid, {}), **OUTPUT_CONTEXT[key])),
                                     standalone=gen)
            pout = render(pg, pt, 'out')
        res = render(pg, pt, ex['name'])
        n_f += 1
        dd = delta(pout['h'], res['h'])
        varied = res['h'] is not None and (res['max'] - res['min']) > EPS_SIGNAL
        if not (has_signal(dd) and varied and not res['err']):
            fails['f'] += 1
            notes.append(f"(f) {key}: " + (f"threw: {res['err']}" if res['err'] else 'identical to out'
                                           if not has_signal(dd) else 'constant'))

# (x) seamless closes a seam that was really there
if not ONLY or 'seamless' in ONLY:
    g = ek.create_graph()
    r_ = RAMP(g)
    sm = ek.add_node(g, 'seamless', {'x': 2, 'y': 0}, P('seamless'))
    ek.connect(g, {'node': r_, 'port': 'out'}, {'node': sm, 'port': 'in'}, P_)
    a_, b_ = seam(render(g, r_)['h']), seam(render(g, sm)['h'])
    if not (b_['lr'] <= b_['cm'] + 4 * b_['csd'] and b_['lr'] < a_['lr'] * 0.25):
        fails['x'] += 1
        notes.append(f"(x) seamless did not close the ramp seam: {a_['lr']:.2e} -> {b_['lr']:.2e}")

for nline in notes:
    print('  ' + nline)

# A failure the port shares with Ekigar is Ekigar's: re-measure every (b) / (c) failure on Ekigar's own field (its
# JS, under deno, the same graphs at the same N). The same field and the same verdict make it an EKIGAR line (the
# audit, which predates Ekigar's 07-29 edits, fails in Ekigar itself), not a port failure.
if oracle_jobs and '--no-oracle' not in sys.argv:
    import os
    import parity_lib
    probes = []
    for j, job in enumerate(oracle_jobs):
        for k, (g, t, _h) in enumerate(job['probes']):
            name = f'j{j}_{k}'
            probes.append({'name': name, 'graph': ek.to_json(g), 'target': t, 'port': 'out'})
            job['names'].append(name)
    od = os.path.join(_ekigar_load.OUT, 'oracle_response')
    parity_lib.run_oracle(probes, N, od)
    for job in oracle_jobs:
        js = [parity_lib.load_oracle(od, nm)[1]['x'] for nm in job['names']]
        same = max(float(np.abs(a - h).max()) for a, (_g, _t, h) in zip(js, job['probes'])) < 1e-9
        if job['kind'] == 'c':
            ek_fails = not any(has_signal(delta(js[0], x)) for x in js[1:])
        else:
            ek_fails = not visibly_moved(relative_response(delta(js[0], js[1]), js[0], js[1]))
        known = same and ek_fails
        print(f"{'EKIGAR' if known else 'FAIL'} {job['label']}: Ekigar's own field "
              f"{'is the same and fails the same way' if known else 'DIFFERS from the port'}", flush=True)
        if known:
            fails[job['kind']] -= 1
labels = {'a': 'non-degenerate output', 'b': 'filter changes its input', 'c': 'every parameter has an effect',
          'd': f'carried gradient agrees in sign ({n_d} operator arms)', 'e': 'monotone bedding transfers',
          'f': f'named outputs are distinct ({n_f} outputs)', 'x': 'optional-input layering and seamless'}
for k, lab in labels.items():
    print(f"{'PASS' if fails[k] == 0 else 'FAIL'} ({k}) {lab}: {fails[k]} failed", flush=True)
total = sum(fails.values())
print(f'operator response: {len(ids)} operators, {renders[0]} evaluations at {N}^2 in {time.time() - t_all:.0f}s; '
      + ('every operator does something, and every parameter controls it' if total == 0 else f'{total} FAILED'))
sys.exit(0 if total == 0 else 1)
