"""Detail (design section 4.12): rock breakup, the flow-steered gully octave, and planation. Every input is a function
of world metres, so a place gets the same rock at every level and on every run.

    op 'breakup'    Stage('breakup', {...}, levels='hero')    rock strength -> K, Sc, relief, failure, talus
    op 'gully'      Stage('gully', {...}, levels='hero')      Phacelle gullies down the flow on soil slopes
    op 'planation'  Stage('planation', {...}, levels='all')   a pediment plain with residual knobs (desert recipes)

Rock breakup. One GPU dispatch (kernels/breakup.glsl, Ekigar's lattice noise in world metres) gives the rock
strength R: three isotropic scales (50, 15 and 5 m by default), two joint sets (weak lines 4-5 m wide, the weathered
expression of a fracture, along their strikes and broken into segments) and, when asked, bedding planes (weak beds
every few metres of height, with dip; off by default: level planes terrace every moderately steep slope along its
contours). From R come
    kfac = 2^(-k_octaves R)            the erodibility factor: K *= kfac and K_factor (the fluvial stage reads it),
                                       and the hydraulic pass erodes rock at `rock` x kfac
    Sc   = tan(theta)                  the rock threshold, theta = the current slope + margin + spread R ('relative',
                                       for real data: rock that stands now stands where it is not weak), or rock_deg +
                                       spread R ('absolute'), or the Sc field's angle + spread R ('field', synthetic
                                       recipes); Sc_factor is its ratio to what the level had
Then, on exposed rock (rock_slope_deg), the process: differential weathering in closed form (weak rock has worn back,
strong rock stands proud: the relief D, about 8 % of each scale RMS, along the surface normal), and the threshold
relaxation (kernels/pipes_thermal.glsl): rock steeper than its own threshold fails, no deeper than max_fail_m (so a
scar stays a scar: a wall at exactly its threshold would otherwise fail all the way up once one cell gives), and the
debris slides at its repose angle and gathers as talus at the foot of walls and in couloirs. Ribs, buttresses and
couloirs come out where the strength says so: couloirs on joints that run down the fall line.
Scales by level: the strength sees every feature the level resolves (r(size / cell), r = smoothstep(1.5, 3)); the
relief adds only the band the parent level cannot resolve (r(size / cell) - r(size / (2 cell))), so a feature's relief
is applied once across the levels that inherit it, and nothing the DEM pixel already holds is added to a real place.

Gully octave. Ekigar's Phacelle filter: stripe noise whose stripes run along a
direction, each octave steered by the one before so the finer gullies run into the coarser. Here the direction is the
flow (the routed MFD direction where a flow vector is given, else down the surface smoothed at the octave's scale),
the stripes are world-space, the amplitude is metres, and it is masked to soil slopes between 10 and 35 degrees.

Planation. Ekigar's planationSurface rebuilt in metres: the ground is cut down to a gently tilted datum where the rock
is weak and keeps its relief where it is resistant (world-space noise), with an abrupt piedmont foot.

All three write h (blended to the pins at the end, like the hydraulic op: the border band fades from the detail to the
parent's surface), and breakup also bed, talus, wear, deposit, kfac, K_factor, Sc and Sc_factor (and K when the level
has one). Run by the level runner (run.py), the ops take its StageContext (pins, device, log) as ctx.

Order. In real_place and fluvial_range the breakup runs after the fluvial stage on each hero level, so its K_factor
and Sc_factor reach only the stages after it on that level (the hydraulic pass); for the fluvial stage to cut along
the rock's weaknesses, put the breakup before it.
"""
from __future__ import annotations

import math
import os
import time

import numpy as np

from ..core import grid as _grid
from ..core import twins as T
from ..core import world_noise as N
from . import hydraulic as HY

F = np.float32
TAU = 6.28318530717959
KERNEL_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'kernels',
                                            'breakup.glsl'))

BREAKUP = {
    'scales_m': ((50.0, 15.0, 5.0), 'm', 'wavelengths of the strength noise'),
    'scale_amps': ((1.0, 0.75, 0.55), '', 'their relative amplitudes'),
    # joints and beds as their weathered expression: a couloir along a fracture is metres wide, a weak interval
    # between massive beds several metres thick (narrower ones only resolve below 0.5 m and belong to the material)
    'joints': (({'strike_deg': 15.0, 'spacing_m': 25.0, 'width_m': 5.0, 'stretch': 2.5, 'strength': 0.9,
                 'depth_m': 1.0},
                {'strike_deg': 105.0, 'spacing_m': 35.0, 'width_m': 4.0, 'stretch': 2.0, 'strength': 0.7,
                 'depth_m': 0.8}), 'list',
               'joint sets: strike (degrees from +x, counter-clockwise), mean spacing, the weak line\'s width, '
               'how much longer than wide its lattice is, strength lost on the line, relief cut on the line (m)'),
    'bedding': (None, 'dict',
                "weak beds, e.g. {'spacing_m': 20, 'width_m': 6, 'strength': 1, 'depth_m': 2, 'dip_deg': 0, "
                "'azimuth_deg': 0, 'z0_m': 0}: every spacing_m metres of stratigraphic height, width_m thick, they fail "
                "back into ledges while the strong rock between them stands. Off by default: as level planes they "
                "terrace every moderately steep rock slope along its contours (the design's strata failure mode); "
                "layered rock is the strata column's job (package 10)"),
    'k_octaves': (1.0, '', 'kfac = 2^(-k_octaves R): R of +-0.33 gives x0.8-1.26'),
    'threshold': ('auto', 'choice', "'relative' (the current slope + spread R), 'absolute' (rock_deg + spread R), "
                                    "'field' (the Sc field x tan-ratio of spread R); 'auto': field when the level has "
                                    "an Sc field, else relative"),
    'rock_deg': (70.0, 'deg', "the mean rock threshold ('absolute')"),
    'spread_deg': (14.0, 'deg', 'the threshold change per unit of strength'),
    'margin_deg': (4.0, 'deg', "'relative': the threshold stands this much above the current slope, so only rock "
                               "weaker than -margin / spread fails (a wall exactly at its threshold would fail all "
                               "the way up once one cell gives)"),
    'max_fail_m': (2.0, 'm', 'the deepest rock fails below the breakup surface: scars stay local (deeper ones leave '
                             'planar failure faces at the threshold angle)'),
    'min_deg': (40.0, 'deg', 'the lowest rock threshold'),
    'max_deg': (88.0, 'deg', 'the highest rock threshold'),
    'relief': (0.25, '', "the weathered relief of each isotropic scale, as a fraction of its wavelength (0.25: about "
                         "8 % of it RMS, rock's roughness)"),
    'normal_cap': (4.0, '', 'the largest vertical stretch of a normal displacement (walls steeper than ~76 deg)'),
    'rock_slope_deg': ((38.0, 52.0), 'deg', 'exposed rock: a smoothstep of the slope'),
    'iterations': (400, '', 'threshold-relaxation passes'),
    'anchor': (True, 'bool', "keep only the change narrower than anchor_m (hydraulic.anchor)"),
    'anchor_m': (None, 'm', "the anchor's scale (None: 1.5 x the main level's cell)"),
    'rate': (0.06, '', 'relaxation rate (<= 1/8)'),
    'repose_deg': (35.0, 'deg', 'the repose angle of the debris'),
    'soil_deg': (38.0, 'deg', 'the threshold written into Sc on soil when the level has none'),
}

GULLY = {
    'wavelength_m': (None, 'm', 'the first octave\'s gully spacing (None: 12 cells)'),
    'octaves': (3, '', 'octaves, each half the wavelength'),
    'amp_m': (None, 'm', 'the first octave\'s depth (None: 0.08 x the wavelength)'),
    'gain': (0.5, '', 'amplitude ratio between octaves'),
    'steer': (0.6, '', 'how much each octave turns the next one into its own gullies'),
    'slope_deg': ((10.0, 18.0, 30.0, 38.0), 'deg', 'the mask: fades in between the first two, out between the last two'),
    'flow_smooth_m': (None, 'm', 'the surface is smoothed this much before its downhill direction is taken (None: '
                                  'the first wavelength)'),
    'normalization': (0.5, '', "Phacelle's amplitude normalisation"),
    'anchor': (True, 'bool', "keep only the change narrower than anchor_m (hydraulic.anchor)"),
    'anchor_m': (None, 'm', "the anchor's scale (None: 1.5 x the main level's cell)"),
}

PLANATION = {
    'datum_m': (None, 'm', 'the plain\'s height at the level centre (None: the 15th percentile of h)'),
    'tilt_deg': (0.8, 'deg', 'the pediment\'s slope'),
    'azimuth_deg': (0.0, 'deg', 'the direction the plain falls toward (from +x, counter-clockwise)'),
    'resist_wavelength_m': (900.0, 'm', 'the size of the resistant patches'),
    'coverage': (0.6, '', 'the fraction of the ground planed flat'),
    'selectivity': (2.5, '', 'higher leaves fewer, sharper residuals'),
    'residual': (0.9, '', 'the original relief kept on resistant ground'),
    'piedmont_m': (40.0, 'm', 'the width of a residual\'s foot (the break of slope)'),
    'plain_relief_m': (1.5, 'm', 'relief left on the plain (noise at 60 m)'),
}


def _params(table, params, op):
    import difflib
    out = {k: v[0] for k, v in table.items()}
    for k, v in (params or {}).items():
        if k in HY.RUNNER_KEYS:
            continue
        if k not in table:
            near = difflib.get_close_matches(k, list(table), n=3)
            raise KeyError(f'{op}: no parameter {k!r}' + (f'; did you mean {near}?' if near else
                                                            f'; valid: {sorted(table)}'))
        out[k] = v
    return out


def _smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, np.float64) - e0) / max(e1 - e0, 1e-12), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def resolvable(size_m, cell):
    """How much of a feature `size_m` across a grid of `cell` resolves: 0 under 1.5 cells, 1 over 3."""
    return float(_smoothstep(1.5, 3.0, float(size_m) / float(cell)))


def band(size_m, cell):
    """The share of a feature's relief a level adds: what it resolves minus what its parent (2 x cell) resolved."""
    return resolvable(size_m, cell) - resolvable(size_m, 2.0 * cell)


# ----------------------------------------------------------------------------------------- the term table ---

JOINT_ZERO_SPACING = 0.6          # gradient noise crosses zero about every 0.6 lattice cells along a line
JOINT_SLOPE = 1.6                 # |dn/d(lattice)| at a zero crossing, about (measured: tests/terrain/detail)


def breakup_terms(p, level, seed):
    """The breakup kernel's term table for a level: (1, 3 N, 4) float32, and the bedding uniforms."""
    cell = float(level.cell)
    x0, y0 = float(level.x0), float(level.y0)
    rows = []

    def term(mode, a_s, width, a_d, M, octave):
        M = np.asarray(M, np.float64)
        ox, oy = N.lattice_offset(int(seed) + 7919 * (octave // 64), octave % 64)
        o = M @ np.array([x0, y0])
        bx, by = math.floor(o[0]), math.floor(o[1])
        fx, fy = o[0] - bx, o[1] - by
        rows.append([(mode, a_s, width, a_d), (bx + ox, by + oy, fx, fy), (M[0, 0], M[0, 1], M[1, 0], M[1, 1])])

    amps = np.asarray(p['scale_amps'], np.float64)
    ss = float((amps ** 2).sum())
    norm = (1.0 / 3.0) / (N.GRADIENT_STD * math.sqrt(ss)) if ss > 0 else 0.0
    for i, (lam, a) in enumerate(zip(p['scales_m'], amps)):
        lam = float(lam)
        term(0, a * norm * resolvable(lam, cell), 0.0, p['relief'] * lam * a * norm * band(lam, cell),
             np.eye(2) / lam, i)
    for j, js in enumerate(p['joints'] or ()):
        th = math.radians(float(js.get('strike_deg', 0.0)))
        u = np.array([math.cos(th), math.sin(th)])
        v = np.array([-math.sin(th), math.cos(th)])
        sp = float(js.get('spacing_m', 15.0))
        lam_x = sp * JOINT_ZERO_SPACING
        lam_u = lam_x * float(js.get('stretch', 5.0))
        w = float(js.get('width_m', 1.5))
        w_eff = max(w, 1.5 * cell)
        wn = JOINT_SLOPE * 0.5 * w_eff / lam_x                      # half the line's width, in noise units
        M = np.stack([u / lam_u, v / lam_x])
        term(1, 0.0, wn, 0.0, M, 16 + 2 * j)
        lam_s = lam_u * 0.7
        term(2, float(js.get('strength', 0.8)) * (w / w_eff), 0.12,
             float(js.get('depth_m', 1.0)) * band(w, cell), np.stack([u / lam_s, v / lam_s]), 17 + 2 * j)
    terms = np.zeros((1, max(3 * len(rows), 3), 4), np.float32)
    for t, r in enumerate(rows):
        for q in range(3):
            terms[0, 3 * t + q] = r[q]
    bed = p['bedding']
    bu = dict(uBedSpacing=1.0, uBedWidth=1.0, uBedAmpS=0.0, uBedAmpD=0.0, uBedZ0=0.0, uDipX=0.0, uDipY=0.0)
    if bed:
        wz = float(bed.get('width_m', 2.0))
        on = resolvable(wz / math.tan(math.radians(70.0)), cell)     # on a 70-degree wall a bed is wz / 2.75 wide
        dip = math.tan(math.radians(float(bed.get('dip_deg', 0.0))))
        az = math.radians(float(bed.get('azimuth_deg', 0.0)))
        bu = dict(uBedSpacing=float(bed.get('spacing_m', 15.0)), uBedWidth=wz,
                  uBedAmpS=float(bed.get('strength', 0.5)) * on,
                  uBedAmpD=float(bed.get('depth_m', 0.6)) * (on - resolvable(wz / math.tan(math.radians(70.0)),
                                                                             2 * cell)),
                  uBedZ0=float(bed.get('z0_m', 0.0)), uDipX=dip * math.cos(az), uDipY=dip * math.sin(az))
    return terms, len(rows), bu


def breakup_uniforms(p, level, n_terms, bed_u, slope_deg_mean=None):
    mn, mx = float(p['min_deg']), float(p['max_deg'])
    u = dict(uTerms=int(n_terms), uCell=float(level.cell), uX0=float(level.x0), uY0=float(level.y0),
             uKOct=float(p['k_octaves']), uRockDeg=float(p['rock_deg']), uSpreadDeg=float(p['spread_deg']),
             uMinDeg=mn, uMaxDeg=mx)
    u.update(bed_u)
    return u


# ------------------------------------------------------------------------------------------- the twin ---

@T.twin('breakup')
def breakup(s, u):
    """The numpy twin of breakup.glsl (world noise from core/world_noise.lattice_noise, Ekigar's hash bit for bit)."""
    terms, st = s['terms'], s['st']
    h = st[..., 0]
    shape = h.shape
    jj, ii = np.mgrid[0:shape[0], 0:shape[1]].astype(F)
    cell = F(u['uCell'])
    lx = (ii + F(0.5)) * cell
    ly = (jj + F(0.5)) * cell
    R = np.zeros(shape, F)
    D = np.zeros(shape, F)
    line = np.zeros(shape, F)
    for t in range(int(u['uTerms'])):
        a = terms[0, 3 * t]
        b = terms[0, 3 * t + 1]
        m = terms[0, 3 * t + 2]
        lcx = (b[2] + m[0] * lx + m[1] * ly).astype(F)
        lcy = (b[3] + m[2] * lx + m[3] * ly).astype(F)
        v = N.lattice_noise(lcx.astype(np.float64), lcy.astype(np.float64), None, (int(b[0]), int(b[1]))).astype(F)
        mode = int(a[0] + 0.5)
        if mode == 0:
            R = R + a[1] * v
            D = D + a[3] * v
        elif mode == 1:
            ln = np.maximum(F(1) - np.abs(v) / a[2], F(0))
            line = (ln * ln).astype(F)
        else:
            e = a[2]
            tt = np.clip((v + e) / (F(2) * e), F(0), F(1))
            w = (line * tt * tt * (F(3) - F(2) * tt)).astype(F)
            R = R - a[1] * w
            D = D - a[3] * w
    if u['uBedAmpS'] > 0 or u['uBedAmpD'] > 0:
        x = F(u['uX0']) + lx
        y = F(u['uY0']) + ly
        zs = ((h - (F(u['uDipX']) * x + F(u['uDipY']) * y) - F(u['uBedZ0'])) / F(u['uBedSpacing'])).astype(F)
        dist = np.abs(zs - np.floor(zs + F(0.5))) * F(u['uBedSpacing'])
        ln = np.maximum(F(1) - dist / (F(0.5) * F(u['uBedWidth'])), F(0))
        ln = ln * ln
        R = R - F(u['uBedAmpS']) * ln
        D = D - F(u['uBedAmpD']) * ln
    kfac = np.exp2(-F(u['uKOct']) * R).astype(F)
    deg = np.clip(F(u['uRockDeg']) + F(u['uSpreadDeg']) * R, F(u['uMinDeg']), F(u['uMaxDeg']))
    sc = np.tan(np.radians(deg.astype(F))).astype(F)
    return {'outB': T.rgba(R, kfac, sc, D)}


_SOURCE = {}


def breakup_source():
    """breakup.glsl with core/world_noise.GLSL_NOISE put in its place."""
    if 'src' not in _SOURCE:
        with open(KERNEL_PATH, encoding='utf-8') as f:
            _SOURCE['src'] = f.read().replace('/*__WORLD_NOISE__*/', N.GLSL_NOISE)
    return _SOURCE['src']


def breakup_kernel():
    from ..core import gpu as G
    return G.kernel(source=breakup_source(), name='breakup')


def strength(p, level, h, seed, backend='gpu'):
    """(R, kfac, Sc of the 'absolute' rule, D) on a level: (n, n) float32 each."""
    terms, nt, bu = breakup_terms(p, level, seed)
    u = breakup_uniforms(p, level, nt, bu)
    st = T.rgba(np.asarray(h, F))
    if backend == 'gpu':
        from ..core import gpu as G
        k = breakup_kernel()
        out = G.empty(np.shape(h))
        G.run(k, None, samplers={'terms': G.texture(terms), 'st': G.texture(st)}, images={'outB': out}, uniforms=u)
        a = G.read(out)
    else:
        a = T.run_twin(breakup, {'st': st, 'terms': terms}, u, spec=_breakup_spec())['outB']   # st first: the shape
    return a[..., 0], a[..., 1], a[..., 2], a[..., 3]


def _breakup_spec():
    from ..core import gpu as G
    return G.parse_spec(breakup_source(), 'breakup')


# --------------------------------------------------------------------------------------- relaxation ---

def relax(b0, bed, sc, repose_tan, iterations, rate, backend='gpu', mode=T.BOUND_OPEN, floor=-1.0e6):
    """`iterations` thermal passes (kernels/pipes_thermal.glsl) on ground b0 with cohesive top `bed` (cell units):
    returns (delta, bed - b0, net change by sliding), the ground being b0 + delta. `floor` (cell units, a number or
    an array): the cohesive ground fails no deeper than this below b0."""
    shape = np.shape(b0)
    par = T.rgba(sc, np.full(shape, repose_tan, F), np.broadcast_to(np.asarray(floor, F), shape))
    pin = np.zeros(shape + (4,), F)
    st = HY.initial_state(b0, bed)
    base = T.rgba(b0)
    u = {'uRate': float(rate), 'uBound': int(mode)}
    if backend == 'gpu':
        from ..core import gpu as G
        k = G.kernel('pipes_thermal')
        S = [G.texture(st), G.empty(shape)]
        TA = [G.empty(shape), G.empty(shape)]
        tb, tp, tq = G.texture(base), G.texture(par), G.texture(pin)
        for _ in range(int(iterations)):
            G.run(k, None, samplers={'st': S[0], 'base': tb, 'par': tp, 'pin': tq, 'tacc': TA[0]},
                  images={'outS': S[1], 'outT': TA[1]}, uniforms=u)
            S.reverse()
            TA.reverse()
        a = G.read(S[0])
        net = G.read(TA[0])[..., 0]
    else:
        tacc = np.zeros(shape + (4,), F)
        a = st
        for _ in range(int(iterations)):
            r = T.run_twin('pipes_thermal', {'st': a, 'base': base, 'par': par, 'pin': pin, 'tacc': tacc}, u)
            a, tacc = r['outS'], r['outT']
        net = tacc[..., 0]
    return a[..., 0], a[..., 3], net


# ------------------------------------------------------------------------------------------- breakup ---

def op_breakup(fields, level, params=None, seed=0, log=None, backend='gpu', ctx=None, **_kw):
    """Stage op 'breakup' (module doc). ctx: the level runner's StageContext (pins, device, log)."""
    log = HY.log_of(log, ctx, '[terrain.detail] ')
    backend = HY.backend_of(backend, ctx)
    p = _params(BREAKUP, params, 'breakup')
    t0 = time.perf_counter()
    cell = float(level.cell)
    h_in = np.asarray(fields['h'], np.float64)
    shape = h_in.shape
    R, kfac, sc_abs, D = strength(p, level, h_in, seed, backend)
    hs = HY._box(h_in, 2)
    gx, gy = _grid.gradient(hs, cell)
    tan_s = np.hypot(gx, gy)
    slope = np.degrees(np.arctan(tan_s))
    rock = _smoothstep(p['rock_slope_deg'][0], p['rock_slope_deg'][1], slope)
    edge = HY.band_fade(fields, level, ctx)
    # differential weathering: the relief D along the surface normal (a normal offset d moves the height d / cos)
    nf = np.minimum(np.sqrt(1.0 + tan_s * tan_s), float(p['normal_cap']))
    h1 = h_in + rock * edge * D.astype(np.float64) * nf
    # the rock threshold
    mode = p['threshold']
    if mode == 'auto':
        mode = 'field' if 'Sc' in fields else 'relative'
    mn, mx = float(p['min_deg']), float(p['max_deg'])
    if mode == 'relative':
        theta = np.clip(slope + p['margin_deg'] + p['spread_deg'] * R, mn, mx)
        sc_rock = np.tan(np.radians(theta))
    elif mode == 'absolute':
        sc_rock = sc_abs.astype(np.float64)
    elif mode == 'field':
        base = np.degrees(np.arctan(np.asarray(fields['Sc'], np.float64)))
        sc_rock = np.tan(np.radians(np.clip(base + p['spread_deg'] * R, mn, mx)))
    else:
        raise ValueError(f"breakup: threshold {mode!r} is not 'auto', 'relative', 'absolute' or 'field'")
    # soil does not fail here: its threshold is out of reach where rock is 0
    sc_eff = (sc_rock * rock + 1.0e3 * (1.0 - rock)).astype(F)
    href = float(h1.min())
    to_c = lambda a: ((np.asarray(a, np.float64) - href) / cell).astype(F)     # noqa: E731
    bed1 = np.minimum(np.asarray(fields['bed'], np.float64), h1) if 'bed' in fields else h1
    rep = math.tan(math.radians(float(p['repose_deg'])))
    dl, bed_rel, net = relax(to_c(h1), to_c(bed1), sc_eff, rep, p['iterations'], p['rate'], backend,
                             floor=-float(p['max_fail_m']) / cell)
    h2 = h1 + dl.astype(np.float64) * cell
    bed2 = h1 + bed_rel.astype(np.float64) * cell
    pw, ph = HY.pins_for(fields, level, h_in, ctx)
    HY.finish(fields, h2, bed2, h_in, pw, ph, talus=np.maximum(net.astype(np.float64), 0.0) * cell, level=level,
              anchor_m=HY.anchor_scale_m(level, p['anchor_m']) if p['anchor'] else None)
    # the rock's numbers for the stages after this one: the erodibility factor (kfac, also as the fluvial stage's
    # K_factor) and the threshold (Sc; Sc_factor is its ratio to what the level had)
    fields['kfac'] = kfac
    fields['K_factor'] = kfac
    if 'K' in fields:
        fields['K'] = np.asarray(fields['K'], np.float64) * kfac
    soil_sc = np.asarray(fields['Sc'], np.float64) if 'Sc' in fields else \
        np.full(shape, math.tan(math.radians(float(p['soil_deg']))))
    sc_new = soil_sc * (1.0 - rock) + sc_rock * rock
    fields['Sc_factor'] = sc_new / np.maximum(soil_sc, 1e-6)
    fields['Sc'] = sc_new
    dh = fields['h'] - h_in
    log(f'level {level.index} ({cell:.3g} m x{level.n}): breakup in {time.perf_counter() - t0:.1f} s; rock '
        f'{rock.mean() * 100:.0f} % of the level, relief |D| p99 {np.percentile(np.abs(D), 99):.2f} m, change '
        f'p1/p99 {np.percentile(dh, 1):+.2f} / {np.percentile(dh, 99):+.2f} m, talus max {fields["talus"].max():.2f} m')
    return fields


# --------------------------------------------------------------------------------------------- gully ---

def phacelle_noise(px, py, dx, dy, freq, offset, normalization, lattice_offset=(0, 0)):
    """Ekigar's phacelle_noise on lattice coordinates (px, py) with a direction field (dx, dy):
    (cos, sin, side x, side y). The stripes run ALONG (dx, dy); `freq` stripes per lattice cell."""
    sdx = -dy * freq * TAU
    sdy = dx * freq * TAU
    off = offset * TAU
    pix = np.floor(px)
    piy = np.floor(py)
    pfx = px - pix
    pfy = py - piy
    phx = np.zeros_like(px)
    phy = np.zeros_like(px)
    wsum = np.zeros_like(px)
    ox, oy = lattice_offset
    for i in range(-1, 3):
        for j in range(-1, 3):
            rx, ry = N.hash2(pix.astype(np.int64) + i + ox, piy.astype(np.int64) + j + oy)
            vx = pfx - i - rx * 0.5
            vy = pfy - j - ry * 0.5
            w = np.maximum(0.0, np.exp((vx * vx + vy * vy) * -2.0) - 0.01111)
            wsum += w
            wave = vx * sdx + vy * sdy + off
            phx += np.cos(wave) * w
            phy += np.sin(wave) * w
    ix = phx / wsum
    iy = phy / wsum
    mag = np.maximum(1.0 - normalization, np.sqrt(ix * ix + iy * iy))
    return ix / mag, iy / mag, sdx, sdy


def flow_direction(h, cell, smooth_m, flow=None):
    """A unit downhill direction per cell: the given flow vector field (x, y components) where it is, else down the
    surface box-smoothed over smooth_m."""
    if flow is not None:
        fx, fy = (np.asarray(a, np.float64) for a in flow)
    else:
        r = max(1, int(round(smooth_m / cell / 2.0)))
        gx, gy = _grid.gradient(HY._box(h, r), cell)
        fx, fy = -gx, -gy
    L = np.hypot(fx, fy)
    ok = L > 1e-12
    return np.where(ok, fx / np.where(ok, L, 1.0), 0.0), np.where(ok, fy / np.where(ok, L, 1.0), 0.0)


def gully_relief(level, h, p, seed, flow=None):
    """The gully octaves' relief in metres (before the mask), and the mask."""
    cell = float(level.cell)
    lam0 = float(p['wavelength_m'] or 12.0 * cell)
    amp0 = float(p['amp_m'] if p['amp_m'] is not None else 0.08 * lam0)
    X, Y = level.xy()
    dx, dy = flow_direction(h, cell, float(p['flow_smooth_m'] or lam0), flow)
    s = _grid.slope_deg(HY._box(h, 1), cell)
    a0, a1, a2, a3 = p['slope_deg']
    mask = _smoothstep(a0, a1, s) * (1.0 - _smoothstep(a2, a3, s))
    out = np.zeros_like(X)
    lam, amp = lam0, amp0
    gxs, gys = dx.copy(), dy.copy()
    for o in range(int(p['octaves'])):
        if lam < 3.0 * cell:
            break
        ox, oy = N.lattice_offset(int(seed) + 4242, o)
        c, sn, sdx, sdy = phacelle_noise(X / lam, Y / lam, gxs, gys, 1.0, 0.25, float(p['normalization']), (ox, oy))
        out += amp * c
        # steer the next octave down this octave's own gully walls (Ekigar's gully-weight feedback)
        gx = -sn * sdx / lam
        gy = -sn * sdy / lam
        gxs = gxs + float(p['steer']) * gx * lam / TAU
        gys = gys + float(p['steer']) * gy * lam / TAU
        L = np.hypot(gxs, gys)
        gxs, gys = gxs / np.maximum(L, 1e-12), gys / np.maximum(L, 1e-12)
        lam *= 0.5
        amp *= float(p['gain'])
    return out, mask


def op_gully(fields, level, params=None, seed=0, log=None, ctx=None, **_kw):
    """Stage op 'gully' (module doc): numpy, one evaluation per level."""
    log = HY.log_of(log, ctx, '[terrain.detail] ')
    p = _params(GULLY, params, 'gully')
    t0 = time.perf_counter()
    h_in = np.asarray(fields['h'], np.float64)
    flow = (fields['flow_x'], fields['flow_y']) if ('flow_x' in fields and 'flow_y' in fields) else None
    g, mask = gully_relief(level, h_in, p, seed, flow)
    h = h_in + g * mask
    pw, ph = HY.pins_for(fields, level, h_in, ctx)
    HY.finish(fields, h, (np.asarray(fields['bed'], np.float64) if 'bed' in fields else h), h_in, pw, ph,
              level=level, anchor_m=HY.anchor_scale_m(level, p['anchor_m']) if p['anchor'] else None)
    log(f'level {level.index} ({level.cell:.3g} m x{level.n}): gully octave in {time.perf_counter() - t0:.1f} s, '
        f'on {mask.mean() * 100:.0f} % of the level, |relief| p99 {np.percentile(np.abs(g * mask), 99):.2f} m')
    return fields


# ------------------------------------------------------------------------------------------ planation ---

def op_planation(fields, level, params=None, seed=0, log=None, backend='gpu', ctx=None, **_kw):
    """Stage op 'planation' (module doc)."""
    log = HY.log_of(log, ctx, '[terrain.detail] ')
    backend = HY.backend_of(backend, ctx)
    p = _params(PLANATION, params, 'planation')
    h_in = np.asarray(fields['h'], np.float64)
    X, Y = level.xy()
    cx, cy = level.centre
    az = math.radians(float(p['azimuth_deg']))
    datum0 = float(p['datum_m']) if p['datum_m'] is not None else float(np.percentile(h_in, 15))
    datum = datum0 - math.tan(math.radians(float(p['tilt_deg']))) * ((X - cx) * math.cos(az) + (Y - cy) * math.sin(az))
    spec = {'kind': 'fbm', 'wavelength_m': float(p['resist_wavelength_m']), 'octaves': 4}
    if backend == 'gpu':
        res = N.field_gpu(spec, level, int(seed) + 6007).astype(np.float64)
    else:
        res = N.field(spec, X, Y, int(seed) + 6007)
    resistance = np.clip(res * 1.5 + 0.5, 0.0, 1.0)
    cov = float(p['coverage'])
    # a narrow transition: a cell is planed or resistant, so the plain is flat and the knobs rise from it abruptly
    hard = _smoothstep(cov - 0.04, cov + 0.04, resistance) ** float(p['selectivity'])
    relief = np.maximum(h_in - datum, 0.0) * float(p['residual']) * hard
    foot = _smoothstep(0.0, max(float(p['piedmont_m']) * math.tan(math.radians(25.0)), 1e-6), relief)
    small = {'kind': 'fbm', 'wavelength_m': 60.0, 'octaves': 3, 'amp': 3.0 * float(p['plain_relief_m'])}
    detail = N.field_gpu(small, level, int(seed) + 6011) if backend == 'gpu' else N.field(small, X, Y, int(seed) + 6011)
    h = datum + relief * foot + np.asarray(detail, np.float64) * (1.0 - hard)
    pw, ph = HY.pins_for(fields, level, h_in, ctx)
    HY.finish(fields, h, np.minimum(np.asarray(fields.get('bed', h)), h), h_in, pw, ph)
    log(f'level {level.index}: planation, residuals on {(hard > 0.5).mean() * 100:.0f} % of the level')
    return fields


OPS = {'breakup': op_breakup, 'gully': op_gully, 'planation': op_planation}
