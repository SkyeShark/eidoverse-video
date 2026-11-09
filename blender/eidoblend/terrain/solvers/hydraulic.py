"""Hydraulic detail: the virtual-pipe shallow-water erosion model (design section 4.4), run on the hero levels for a
few thousand steps. It gives rain rills, small sediment fans and loose material settled at its repose angle; it is not
the backbone (it cannot build a valley network in any affordable time).

    op 'hydraulic'   Stage('hydraulic', {...}, levels='hero')     op_hydraulic(fields, level, params, seed)

The model (Mei, Decaudin & Hu 2007; Jako 2011), one step = four GPU passes:
    pipes_flux       rain falls; the 8 pipes' outflow fluxes grow with the water-surface drop (isotropic weights,
                     so rills do not comb along the grid axes) and are scaled so no cell sends more than it holds
    pipes_water      the water update, the velocity, and erosion / deposition against the capacity
                     C = Kc max(max(sin a, sin_min) min(|q|, q_cap) - qc, 0) depth_ramp: excess stream power
                     (|q| = discharge per unit width) over a critical value, so sheet flow leaves a planar slope alone
                     and flow gathered by the ground's micro-relief cuts rills; q_cap (rain x catchment_cells) keeps
                     the parent's rivers from being cut again, and max_depth bounds the cut below the start
    pipes_transport  suspended sediment moves with the water's own pipe fluxes (donor cell: what a cell sends its
                     neighbour receives, bit for bit), then the water evaporates. The design names Mei's semi-
                     Lagrangian advection, which creates and destroys sediment; this package's test is conservation
    pipes_thermal    loose debris above its repose angle slides to lower neighbours, mass-conserving; cohesive ground
                     fails only above its own threshold (rock breakup's Sc), no deeper than a floor
Everything runs in CELL UNITS (heights and lengths in cells), so Jako's numbers (dt 0.02, rain 0.012, Ks 0.5, Kd 1,
Ke 0.015, pipe area 20, g 9.81) apply unchanged at every cell size: the design's "scaled with the cell size". A rill
is then a few cells wide and a fraction of a cell deep at any level, and each hero level adds its own octave of rills
on top of the ones it inherits (gullies at 4 m cells, rills at 0.5 m).

Precision. The ground is held as the run's start surface b0 (a constant texture) plus the change since (the state):
a step's erosion of 1e-6 cells is kept in full where b0 is hundreds of cells. The water pass moves exactly what the
rounded ground lost into suspension, the transport pass's sender and receivers share one `precise` expression, and
the thermal pass carries its rounding into the next pass (Kahan): measured on the GPU, ground + sediment is conserved
to 1e-9 of the material moved over 3,000 steps and the water to its rain-in, evaporation-out budget.

Loose and cohesive. `bed`, the top of the cohesive ground (rock, or soil in place), splits the ground: loose debris
above it (deposits, talus) erodes at the full rate and slides at its repose angle; the cohesive ground erodes at
`soil` on gentle ground and `rock` x the rock breakup's erodibility factor (`kfac`) on steep ground (soil_slope_deg),
and never slides (unless rock_fail). A level without a bed field starts with no debris (bed = h).

The seed. Rills need something to gather the water: the op seeds world-space micro-relief (roughness x the cell, at
3 cells, on soil slopes, 40 % of it on flats), runs the water on it, and keeps the seed in the result only on levels of
0.5 m and finer (hummocks); on coarser levels only what the water did stays.

Fields read: h (required), bed, kfac (rock breakup), Sc (threshold of the cohesive ground, tangent, with rock_fail),
and the pins (the level runner's StageContext, or pin_w / pin_h fields; without them, on a level with a parent, the
band ramp of core/grid holds the ground at its start value within 16 cells of the edge).
Fields written: h, bed, wear (+= eroded depth, m), deposit (+= settled thickness, m), talus (+= what the cohesive
ground shed, net, m; only with rock_fail), wet (water standing plus water passing in the last 20 % of the steps:
depth + discharge x dt, m; the wet / dry pattern). The loop runs with open, draining edges; the pins are blended in
once at the end (finish), so the border band fades from the detail to the parent's surface.

The numpy twins below are the kernels' test oracles (core/twins.py), registered by kernel name; `run_numpy` steps
them for the conservation tests at 64-128 cells. Production is the GPU (PipeRunGPU); there is no CPU path in it.
"""
from __future__ import annotations

import math
import time

import numpy as np

from ..core import grid as _grid
from ..core import twins as T

F = np.float32
BIG_TAN = F(1.0e6)                     # a threshold no pair exceeds: rock that never fails in a pass

# name -> (default, unit, what it is). Cell units are heights and lengths divided by the level's cell.
PARAMS = {
    'steps': (3000, '', 'pipe-model steps per level (the design: 2,000-5,000)'),
    'dt': (0.02, 's', "model seconds per step (Jako)"),
    'rain': (0.012, 'cells/s', "rain depth per model second (Jako's Kr)"),
    'rain_cover': (1.0, '', 'the fraction of cells rained on each step (below 1: random cells, the same mean)'),
    'pipe': (196.2, '', 'pipe cross-section x gravity / pipe length (Jako: 20 x 9.81 / 1)'),
    'damp': (0.5, '1/s', 'flux friction: a terminal speed on long slopes, and standing water settles'),
    'Kc': (0.04, 's/cell', 'transport capacity per unit of excess stream power'),
    'Ks': (0.5, '1/s', 'erosion (dissolving) rate (Jako)'),
    'Kd': (1.0, '1/s', 'deposition rate (Jako)'),
    'Ke': (0.015, '1/s', 'evaporation (Jako)'),
    'sin_min': (0.02, '', 'the smallest tilt the capacity sees'),
    'qc': (0.3, 'cells^2/s', 'critical stream power (tilt x discharge per unit width): sheet flow under it does '
                             'not erode, gathered flow over it cuts rills'),
    'catchment_cells': (150.0, 'cells', 'the capacity sees at most the discharge of this much slope length upstream '
                                        '(rain x cells): rills and gullies, not the parent\'s rivers cut again'),
    'max_depth': (0.5, 'cells', 'the deepest the pass cuts below the surface it started from'),
    'dmax': (0.5, 'cells', 'water deeper than this carries nothing (ponds and lakes drop their load)'),
    'soil': (0.5, '', 'erodibility of soil in place, relative to loose debris'),
    'rock': (0.05, '', 'erodibility of rock relative to loose debris (x the rock breakup factor kfac)'),
    'soil_slope_deg': ((35.0, 50.0), 'deg', 'ground is soil below the first slope, rock above the second'),
    'max_step': (0.01, 'cells', 'the most a cell is lowered in one step'),
    'thermal_rate': (0.06, '', 'the thermal pass rate (<= 1/8)'),
    'repose_deg': (35.0, 'deg', 'repose angle of loose debris (talus, deposits)'),
    'rock_fail': (False, 'bool', 'the cohesive ground also fails in the thermal pass at its threshold (the Sc '
                                 'field); else only loose debris moves'),
    'roughness': (0.12, 'cells', "micro-relief seeded on soil slopes before the rain (standard deviation): the "
                                 "clods, stones and roots a DEM cannot hold, which the water gathers into rills"),
    'roughness_cells': (3.0, 'cells', 'the micro-relief wavelength'),
    'roughness_slope_deg': ((8.0, 20.0), 'deg', 'the micro-relief grows to full between these slopes, where water '
                                                'gathers it into rills'),
    'roughness_flat': (0.4, '', 'its share on gentle ground: soil hummocks, no rills (the swissALTI3D 0.5 m truth '
                                'around the Lauterbrunnen eye spot holds about 5 cm of relief within 2 m on the floor)'),
    'roughness_keep_m': ((0.5, 2.0), 'm', 'the micro-relief is a seed that steers the water; the result keeps it on '
                                          'levels with cells up to the first size (sub-metre hummocks) and drops it '
                                          'from the second up (a 12 m stipple on a 4 m level reads as orange peel, '
                                          'not ground): there only what the water did stays'),
    'outflow': (True, 'bool', 'water leaves through the level edge where the ground runs downhill'),
    'anchor': (True, 'bool', "keep only the change narrower than anchor_m (anchor): detail without moving the "
                             "landform the levels above hold"),
    'anchor_m': (None, 'm', "the anchor's scale (None: 1.5 x the main level's cell, 12 m at Lauterbrunnen)"),
    'wet_tail': (0.2, '', 'the last fraction of the steps averaged into the wet field'),
}


RUNNER_KEYS = ('enabled',)              # stage parameters the level runner reads itself (run.py)


def defaults(params=None):
    """The op's parameters: PARAMS defaults overridden by `params`; an unknown name raises naming the nearest."""
    import difflib
    out = {k: v[0] for k, v in PARAMS.items()}
    for k, v in (params or {}).items():
        if k in RUNNER_KEYS:
            continue
        if k not in PARAMS:
            near = difflib.get_close_matches(k, list(PARAMS), n=3)
            raise KeyError(f'hydraulic: no parameter {k!r}' + (f'; did you mean {near}?' if near else
                                                                  f'; valid: {sorted(PARAMS)}'))
        out[k] = v
    return out


# ------------------------------------------------------------------------------------------- the numpy twins ---

def _rain(shape, u, mult):
    """Water added by this step's rain, per cell (pipes_*.glsl rain_at)."""
    P = F(u['uRainP'])
    amt = F(u['uRain']) * F(u['uDt'])
    if P >= 1:
        return (amt * mult).astype(F)
    hit = T.u01(T.cell_hash(shape, u['uStep'], u['uSeed'])) < P
    return np.where(hit, F(amt / P) * mult, F(0)).astype(F)


def _d1(d, src, u):
    """Depth after rain and inflow (rain_at + inflow * dt)."""
    return (d + _rain(d.shape, u, src[..., 0]) + src[..., 1] * F(u['uDt'])).astype(F)


def _channels(fa, fb):
    return [fa[..., 0], fa[..., 1], fa[..., 2], fa[..., 3], fb[..., 0], fb[..., 1], fb[..., 2], fb[..., 3]]


def _rel(base, dl, k, mode):
    """b_k - b_c for the k-th neighbour, as the kernels take it: (b0_k - b0_c) + (delta_k - delta_c); and ok."""
    b0q, ok = T.neighbour(base, k, mode)
    dq, _ = T.neighbour(dl, k, mode)
    return ((b0q - base) + (dq - dl)).astype(F), ok


@T.twin('pipes_flux')
def pipes_flux(s, u):
    st, src, base = s['st'], s['src'], s['base'][..., 0]
    dl, d = st[..., 0], st[..., 1]
    mode, dt = u['uBound'], F(u['uDt'])
    d1 = _d1(d, src, u)
    f = _channels(s['fa'], s['fb'])
    keep = F(max(F(1) - F(u['uDamp']) * dt, F(0)))
    coef = dt * F(u['uPipe'])
    tot = np.zeros_like(dl)
    out = []
    for k in range(8):
        b0q, ok = T.neighbour(base, k, mode)
        dq, _ = T.neighbour(dl, k, mode)
        d1q, _ = T.neighbour(d1, k, mode)
        dh_in = ((base - b0q) + (dl - dq)) + (d1 - d1q)
        dx, dy = T.OFF[k]
        b0m, okm = T.shift(base, -dx, -dy, mode)
        dm, _ = T.shift(dl, -dx, -dy, mode)
        dh_out = np.where(okm, (b0m - base) + (dm - dl), F(0)) + d1
        dh = np.where(ok, dh_in, dh_out)
        fk = np.maximum(F(0), f[k] * keep + coef * T.WISO[k] * dh).astype(F)
        if not u['uOutflow']:
            fk = np.where(ok, fk, F(0))
        tot = (tot + fk).astype(F)
        out.append(fk)
    tdt = (tot * dt).astype(F)
    K = np.where(tdt > d1, d1 / np.where(tdt > 0, tdt, F(1)), F(1)).astype(F)
    o = [(x * K).astype(F) for x in out]
    return {'outA': np.stack(o[:4], -1), 'outB': np.stack(o[4:], -1)}


@T.twin('pipes_water')
def pipes_water(s, u):
    st, src, pin, base = s['st'], s['src'], s['pin'], s['base'][..., 0]
    b, sed, bed = st[..., 0], st[..., 2], st[..., 3]
    mode, dt = u['uBound'], F(u['uDt'])
    d1 = _d1(st[..., 1], src, u)
    fo = _channels(s['fa'], s['fb'])
    outs = np.zeros_like(b)
    ins = np.zeros_like(b)
    qx = np.zeros_like(b)
    qy = np.zeros_like(b)
    above = np.zeros_like(b)
    bn, oks = [], []
    for k in range(8):
        outs = (outs + fo[k]).astype(F)
        rel, ok = _rel(base, b, k, mode)
        j = 7 - k
        fj = (s['fa'] if j < 4 else s['fb'])[..., j % 4]
        fin, _ = T.neighbour(fj, k, mode)
        fin = np.where(ok, fin, F(0))
        bn.append(np.where(ok, rel, F(0)))
        oks.append(ok)
        above = np.where(ok, np.maximum(above, -rel), above)
        ins = (ins + fin).astype(F)
        dx, dy = T.OFF[k]
        qx = (qx + F(0.5 * dx) * (fo[k] - fin)).astype(F)
        qy = (qy + F(0.5 * dy) * (fo[k] - fin)).astype(F)
    d2 = np.maximum(d1 + dt * (ins - outs), F(0)).astype(F)
    dbar = (F(0.5) * (d1 + d2)).astype(F)
    safe = np.where(dbar > F(1e-12), dbar, F(1))
    vx = np.where(dbar > F(1e-12), qx / safe, F(0)).astype(F)
    vy = np.where(dbar > F(1e-12), qy / safe, F(0)).astype(F)
    gx = (bn[4] - bn[3]) / np.maximum(oks[4].astype(F) + oks[3].astype(F), F(1))
    gy = (bn[6] - bn[1]) / np.maximum(oks[6].astype(F) + oks[1].astype(F), F(1))
    g2 = (gx * gx + gy * gy).astype(F)
    sina = np.sqrt(g2 / (F(1) + g2)).astype(F)
    qlen = np.sqrt(qx * qx + qy * qy).astype(F)
    cap = (F(u['uKc']) * np.maximum(np.maximum(sina, F(u['uSinMin'])) * np.minimum(qlen, F(u['uQcap']))
                                    - F(u['uQc']), F(0))
           * np.clip(F(1) - d2 / F(u['uDmax']), F(0), F(1))).astype(F)
    under = cap > sed
    want = np.minimum(F(u['uKs']) * dt * (cap - sed), F(u['uMaxStep']))
    want = np.minimum(want, above)
    want = np.minimum(want, np.maximum(b + F(u['uMaxDepth']), F(0)))
    loose = np.maximum(b - bed, F(0))
    e1 = np.minimum(want, loose)
    e2 = (want - e1) * np.clip(F(u['uRock']) * src[..., 2], F(0), F(1))
    e = (e1 + e2).astype(F)
    dep = np.minimum(F(u['uKd']) * dt * (sed - cap), sed).astype(F)
    b2 = np.where(under, b - e, b + dep).astype(F)
    s2 = np.where(under, sed + (b - b2), sed - (b2 - b)).astype(F)      # exactly what the rounded ground changed
    bed2 = np.where(under, np.minimum(bed, b2), bed).astype(F)
    if mode == T.BOUND_PINNED:
        b2 = T.pin_apply(b2, pin[..., 0], pin[..., 1])
        bed2 = np.minimum(bed2, b2)
    return {'outS': T.rgba(b2, d2, s2, bed2), 'outV': T.rgba(vx, vy, qlen, cap)}


@T.twin('pipes_transport')
def pipes_transport(s, u):
    st2, st0, src = s['st2'], s['st0'], s['src']
    mode, dt = u['uBound'], F(u['uDt'])
    d1 = _d1(st0[..., 1], src, u)
    fa, fb = s['fa'], s['fb']
    tot = (((fa[..., 0] + fa[..., 1]) + (fa[..., 2] + fa[..., 3]))
           + ((fb[..., 0] + fb[..., 1]) + (fb[..., 2] + fb[..., 3]))).astype(F)        # pipes_transport den_of
    den = np.maximum(np.maximum(d1, tot * dt), F(1e-30)).astype(F)
    own = _channels(fa, fb)

    def part(sv, f, dn):
        return (sv * ((f * dt) / dn)).astype(F)
    sent = np.zeros_like(den)
    for k in range(8):
        sent = (sent + np.where(own[k] > 0, part(st2[..., 2], own[k], den), F(0))).astype(F)
    sed = (st2[..., 2] - sent).astype(F)
    for k in range(8):
        j = 7 - k
        fj = (fa if j < 4 else fb)[..., j % 4]
        fin, ok = T.neighbour(fj, k, mode)
        dq, _ = T.neighbour(den, k, mode)                 # the sending neighbour's own denominator
        sq, _ = T.neighbour(st2[..., 2], k, mode)
        sed = (sed + np.where(ok & (fin > 0), part(sq, fin, np.where(ok, dq, F(1))), F(0))).astype(F)
    d = (st2[..., 1] * F(max(F(1) - F(u['uKe']) * dt, F(0)))).astype(F)
    return {'outS': T.rgba(st2[..., 0], d, sed, st2[..., 3])}


@T.twin('pipes_thermal')
def pipes_thermal(s, u):
    st, par, pin, base = s['st'], s['par'], s['pin'], s['base'][..., 0]
    b, bed = st[..., 0], st[..., 3]
    mode, rate = u['uBound'], F(u['uRate'])
    tc = np.maximum(b - bed, F(0))
    db = np.zeros_like(b)
    for k in range(8):
        bq, ok = T.neighbour(b, k, mode)
        b0q, _ = T.neighbour(base, k, mode)
        bedq, _ = T.neighbour(bed, k, mode)
        scq, _ = T.neighbour(par[..., 0], k, mode)
        rpq, _ = T.neighbour(par[..., 1], k, mode)
        flq, _ = T.neighbour(par[..., 2], k, mode)
        dh = ((base - b0q) + (b - bq)).astype(F)
        adh = np.abs(dh)
        t_hi = np.where(dh > 0, tc, np.maximum(bq - bedq, F(0)))
        room = np.where(dh > 0, np.maximum(b - par[..., 2], F(0)), np.maximum(bq - flq, F(0)))
        e_rock = np.minimum(np.maximum(adh - F(0.5) * (par[..., 0] + scq) * T.LEN[k], F(0)), room)
        e_loose = np.minimum(np.maximum(adh - F(0.5) * (par[..., 1] + rpq) * T.LEN[k], F(0)), t_hi)
        m = (rate * np.maximum(e_rock, e_loose)).astype(F)
        m = np.where(ok, m, F(0))
        db = (db + np.where(dh > 0, -m, m)).astype(F)
    ta = s['tacc']
    dbc = (db + ta[..., 1]).astype(F)
    b2 = (b + dbc).astype(F)
    carry = (dbc - (b2 - b)).astype(F)                     # what float32 rounding dropped (Kahan)
    bed2 = np.minimum(bed, b2)
    if mode == T.BOUND_PINNED:
        b2 = T.pin_apply(b2, pin[..., 0], pin[..., 1])
        bed2 = np.minimum(bed2, b2)
    return {'outS': T.rgba(b2, st[..., 1], st[..., 2], bed2),
            'outT': T.rgba((ta[..., 0] + db).astype(F), carry)}


# --------------------------------------------------------------------------------------------- the stepping ---

def uniforms(p, step, seed, mode, outflow=True):
    """The kernels' uniforms for step `step` (one dict; each pass takes the ones it declares)."""
    return {'uDt': p['dt'], 'uRain': p['rain'], 'uRainP': p['rain_cover'], 'uPipe': p['pipe'], 'uDamp': p['damp'],
            'uKc': p['Kc'], 'uKs': p['Ks'], 'uKd': p['Kd'], 'uKe': p['Ke'], 'uSinMin': p['sin_min'], 'uQc': p['qc'],
            'uQcap': p['rain'] * p['catchment_cells'], 'uMaxDepth': p['max_depth'],
            'uDmax': p['dmax'], 'uRock': 1.0, 'uMaxStep': p['max_step'], 'uRate': p['thermal_rate'],
            'uStep': int(step), 'uSeed': int(seed), 'uBound': int(mode), 'uOutflow': int(bool(outflow))}


def _pick(spec_uniforms, u):
    return {k: u[k] for k in spec_uniforms}


_SPECS = {}


def spec(name):
    """A kernel's parsed //! interface (plain Python, cached)."""
    if name not in _SPECS:
        from ..core import gpu as G
        _SPECS[name] = G.load_source(name)[2]
    return _SPECS[name]


def initial_state(b0, bed=None, d=None, s=None):
    """The state texture's start: (delta = 0, water, sediment, bed - b0), all cell units; the ground is b0 + delta."""
    shape = np.shape(b0)
    z = np.zeros(shape, F)
    bed_rel = z if bed is None else (np.asarray(bed, np.float64) - np.asarray(b0, np.float64)).astype(F)
    return T.rgba(z, z if d is None else d, z if s is None else s, np.minimum(bed_rel, F(0)))


def step_numpy(state, flux, base, src, par, pin, tacc, p, step, seed, mode, outflow=True):
    """One model step with the twins (tests only): returns (state, (fa, fb), tacc, vel). `base` is (H, W, 4) with
    b0 in x."""
    u = uniforms(p, step, seed, mode, outflow)
    fa, fb = flux
    r = T.run_twin('pipes_flux', {'st': state, 'base': base, 'fa': fa, 'fb': fb, 'src': src},
                   _pick(spec('pipes_flux').uniforms, u))
    fa, fb = r['outA'], r['outB']
    w = T.run_twin('pipes_water', {'st': state, 'base': base, 'fa': fa, 'fb': fb, 'src': src, 'pin': pin},
                   _pick(spec('pipes_water').uniforms, u))
    tr = T.run_twin('pipes_transport', {'st2': w['outS'], 'st0': state, 'fa': fa, 'fb': fb, 'src': src},
                    _pick(spec('pipes_transport').uniforms, u))
    th = T.run_twin('pipes_thermal', {'st': tr['outS'], 'base': base, 'par': par, 'pin': pin, 'tacc': tacc},
                    _pick(spec('pipes_thermal').uniforms, u))
    return th['outS'], (fa, fb), th['outT'], w['outV']


def run_numpy(b0, bed, src, par, pin, p, seed=0, mode=T.BOUND_OPEN, outflow=True, steps=None, d=None, s=None,
              record=None):
    """The model on numpy twins (tests at 64-128 cells), from ground b0 (cell units) with cohesive top `bed`.
    Returns the final state (H, W, 4) = (delta, d, s, bed - b0), the sliding accumulator, and, if `record` is a list,
    (step, water total, delta + sediment total) per step: the conserved mass is the sum of delta + s."""
    shape = np.shape(b0)
    base = T.rgba(b0)
    state = initial_state(b0, bed, d, s)
    flux = (np.zeros(shape + (4,), F), np.zeros(shape + (4,), F))
    tacc = np.zeros(shape + (4,), F)
    for i in range(int(steps if steps is not None else p['steps'])):
        state, flux, tacc, _v = step_numpy(state, flux, base, src, par, pin, tacc, p, i, seed, mode, outflow)
        if record is not None:
            record.append((i, float(state[..., 1].sum(dtype=np.float64)), mass(state, tacc)))
    return state, tacc


def mass(state, tacc):
    """The conserved total, cell units: the ground's change + the suspended sediment + the rounding the thermal pass
    still carries."""
    return float(state[..., 0].sum(dtype=np.float64) + state[..., 2].sum(dtype=np.float64)
                 + tacc[..., 1].sum(dtype=np.float64))


# ------------------------------------------------------------------------------------------------ the GPU ---

class PipeRunGPU:
    """The pipe model's textures on the GPU and its step loop (production). b0, bed in cell units; pin as
    (pin_w, pin_h - b0)."""

    def __init__(self, b0, bed, src, par, pin, d=None, s=None):
        from ..core import gpu as G
        self.G = G
        G.init()
        shape = np.shape(b0)
        self.S = [G.texture(initial_state(b0, bed, d, s)), G.empty(shape), G.empty(shape)]
        self.base = G.texture(T.rgba(b0))
        self.FA = [G.empty(shape), G.empty(shape)]
        self.FB = [G.empty(shape), G.empty(shape)]
        self.V = G.empty(shape)
        self.TA = [G.empty(shape), G.empty(shape)]
        self.src = G.texture(src)
        self.par = G.texture(par)
        self.pin = G.texture(pin)
        self.k = {n: G.kernel(n) for n in ('pipes_flux', 'pipes_water', 'pipes_transport', 'pipes_thermal')}

    def step(self, p, i, seed, mode, outflow=True, thermal=True):
        G, k = self.G, self.k
        u = uniforms(p, i, seed, mode, outflow)
        S0, S1, S2 = self.S
        G.run(k['pipes_flux'], None, samplers={'st': S0, 'base': self.base, 'fa': self.FA[0], 'fb': self.FB[0],
                                               'src': self.src},
              images={'outA': self.FA[1], 'outB': self.FB[1]}, uniforms=_pick(k['pipes_flux'].spec.uniforms, u))
        G.run(k['pipes_water'], None, samplers={'st': S0, 'base': self.base, 'fa': self.FA[1], 'fb': self.FB[1],
                                                'src': self.src, 'pin': self.pin},
              images={'outS': S1, 'outV': self.V}, uniforms=_pick(k['pipes_water'].spec.uniforms, u))
        G.run(k['pipes_transport'], None, samplers={'st2': S1, 'st0': S0, 'fa': self.FA[1], 'fb': self.FB[1],
                                                    'src': self.src},
              images={'outS': S2}, uniforms=_pick(k['pipes_transport'].spec.uniforms, u))
        if thermal:
            G.run(k['pipes_thermal'], None, samplers={'st': S2, 'base': self.base, 'par': self.par, 'pin': self.pin,
                                                      'tacc': self.TA[0]},
                  images={'outS': S0, 'outT': self.TA[1]}, uniforms=_pick(k['pipes_thermal'].spec.uniforms, u))
            self.TA.reverse()
        else:
            self.S = [S2, S0, S1]
        self.FA.reverse()
        self.FB.reverse()

    def state(self):
        return self.G.read(self.S[0])

    def talus(self):
        return self.G.read(self.TA[0])[..., 0]

    def accum(self):
        """The thermal accumulator (x: net change by sliding, y: the rounding carried)."""
        return self.G.read(self.TA[0])

    def velocity(self):
        """The last water pass's (vx, vy, discharge per unit width, capacity)."""
        return self.G.read(self.V)

    def mass(self):
        return mass(self.state(), self.accum())


# ------------------------------------------------------------------------------------------------ helpers ---

def rockness(h, cell, slope_deg):
    """0 on soil, 1 on rock: a smoothstep of the slope (degrees, on the surface smoothed over 2 cells, so a rill
    does not flip it) between the two slopes."""
    s = _grid.slope_deg(_box(h, 2), cell)
    lo, hi = slope_deg
    t = np.clip((s - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def erodibility(t, soil, rock, kfac=None):
    """The cohesive ground's erodibility relative to loose debris: `soil` where rockness t is 0, `rock` x the rock
    breakup factor where it is 1."""
    kf = 1.0 if kfac is None else np.asarray(kfac, np.float64)
    return (soil * (1.0 - t) + rock * kf * t).astype(F)


def micro_relief(level, seed, amp_m, wavelength_m, backend='gpu'):
    """World-space micro-relief in metres (fbm of 2 octaves, standard deviation amp_m): the same place gets the same
    bumps on every run, and each level its own octave."""
    from ..core import world_noise as N
    spec = {'kind': 'fbm', 'wavelength_m': float(wavelength_m), 'octaves': 2, 'amp': 3.0 * float(amp_m)}
    if backend == 'gpu':
        return N.field_gpu(spec, level, seed).astype(np.float64)
    X, Y = level.xy()
    return N.field(spec, X, Y, seed)


def _box(a, r):
    """Separable box blur of radius r cells, edges clamped (numpy, float64)."""
    a = np.asarray(a, np.float64)
    for axis in (0, 1):
        n = a.shape[axis]
        idx = np.clip(np.arange(-r, n + r), 0, n - 1)
        pa = np.take(a, idx, axis=axis)
        c = np.cumsum(pa, axis=axis)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
        a = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis) - np.take(c, np.arange(n), axis=axis)) \
            / (2 * r + 1)
    return a


def pins_for(fields, level, h_start, ctx=None):
    """(pin_w, pin_h in metres): the level runner's pins (its StageContext, or pin fields) when it has them; else, on
    a level with a parent, the border band of core/grid (weight 1 on the edge to 0 at `band` cells in) holding the
    ground at its value when the stage started; on the coarsest level (no parent) none."""
    pins = getattr(ctx, 'pins', None)
    if pins is not None and 'pin_w' in pins and 'pin_h' in pins:
        return np.asarray(pins['pin_w'], np.float64), np.asarray(pins['pin_h'], np.float64)
    if 'pin_w' in fields and 'pin_h' in fields:
        return np.asarray(fields['pin_w'], np.float64), np.asarray(fields['pin_h'], np.float64)
    if getattr(level, 'parent', None) is None:
        return np.zeros(np.shape(h_start)), np.asarray(h_start, np.float64)
    return (_grid.border_ramp(level.n, getattr(level, 'band', 16)).astype(np.float64),
            np.asarray(h_start, np.float64))


def band_fade(fields, level, ctx=None):
    """1 - the pin weight: where a detail op may put its relief at full strength."""
    w, _h = pins_for(fields, level, np.zeros((level.n, level.n)), ctx)
    return 1.0 - np.clip(w, 0.0, 1.0)


def backend_of(backend, ctx):
    """'gpu' in production; 'numpy' (the twins) when the runner's device is its twin device (tests)."""
    dev = getattr(ctx, 'device', None)
    if dev is not None and str(getattr(dev, 'name', 'gpu')) not in ('gpu', 'GPU'):
        return 'numpy'
    return backend


def log_of(log, ctx, prefix):
    if log is not None:
        return log
    if ctx is not None and getattr(ctx, 'log', None) is not None:
        return lambda m: ctx.log(prefix + m)
    return lambda m: print(prefix + m, flush=True)


# ------------------------------------------------------------------------------------------------- the op ---

def op_hydraulic(fields, level, params=None, seed=0, log=None, backend='gpu', ctx=None, **_kw):
    """Stage op 'hydraulic' (module doc): runs the pipe model on this level's fields in place. ctx: the level
    runner's StageContext (its pins, device and log), when run.py calls it."""
    log = log_of(log, ctx, '[terrain.hydraulic] ')
    backend = backend_of(backend, ctx)
    p = defaults(params)
    t0 = time.perf_counter()
    cell = float(level.cell)
    h_in = np.asarray(fields['h'], np.float64)
    shape = h_in.shape
    href = float(h_in.min())
    to_c = lambda a: ((np.asarray(a, np.float64) - href) / cell).astype(F)      # noqa: E731 metres -> cell units
    rk = rockness(h_in, cell, p['soil_slope_deg'])
    kf = np.asarray(fields['kfac'], F) if 'kfac' in fields else None
    # in the border band the ground stops eroding (ramping with the pin weight): water still drains out through the
    # open edge, but cuts no channels along it for the pin blend to half-erase (they showed as streaks in the band)
    src = T.rgba(np.ones(shape, F), None,
                 (erodibility(rk, p['soil'], p['rock'], kf) * band_fade(fields, level, ctx)).astype(F))
    h0 = h_in
    if p['roughness'] > 0:
        r = micro_relief(level, int(seed) + 7001, p['roughness'] * cell, p['roughness_cells'] * cell, backend)
        s_deg = _grid.slope_deg(_box(h_in, 2), cell)
        lo, hi = p['roughness_slope_deg']
        on_slope = np.clip((s_deg - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
        on_slope = on_slope * on_slope * (3.0 - 2.0 * on_slope)
        on_slope = float(p['roughness_flat']) + (1.0 - float(p['roughness_flat'])) * on_slope
        h0 = h_in + r * (1.0 - rk) * on_slope * band_fade(fields, level, ctx)
    bed_m = np.minimum(np.asarray(fields['bed'], np.float64), h0) if 'bed' in fields else h0
    rep = F(math.tan(math.radians(float(p['repose_deg']))))
    sc = np.asarray(fields['Sc'], F) if (p['rock_fail'] and 'Sc' in fields) else np.full(shape, BIG_TAN, F)
    par = T.rgba(sc, np.full(shape, rep, F), np.full(shape, -1.0e6, F))      # z: no failure floor
    pw, ph = pins_for(fields, level, h_in, ctx)
    b0 = to_c(h0)
    pin = T.rgba(pw, (to_c(ph) - b0).astype(F))
    # the loop runs open (water leaves downhill edges) and the pins are blended in ONCE at the end: applied every
    # step, a pin of any weight above 0 wins over thousands of steps and the whole 16-cell band would lose its detail
    mode = T.BOUND_OPEN
    steps = int(p['steps'])
    tail0 = int(steps * (1.0 - float(p['wet_tail'])))
    wet = np.zeros(shape, np.float64)
    nwet = 0
    # the wet field: water standing (depth) plus water passing (discharge per unit width x one step), cell units
    dt = float(p['dt'])
    if backend == 'gpu':
        run = PipeRunGPU(b0, to_c(bed_m), src, par, pin)
        for i in range(steps):
            run.step(p, i, seed, mode, p['outflow'])
            if i >= tail0 and (i - tail0) % 100 == 0:
                wet += run.state()[..., 1] + run.velocity()[..., 2] * dt
                nwet += 1
        st = run.state()
        tal = run.talus()
    else:
        base = T.rgba(b0)
        state = initial_state(b0, to_c(bed_m))
        flux = (np.zeros(shape + (4,), F), np.zeros(shape + (4,), F))
        tacc = np.zeros(shape + (4,), F)
        for i in range(steps):
            state, flux, tacc, v = step_numpy(state, flux, base, src, par, pin, tacc, p, i, seed, mode,
                                              p['outflow'])
            if i >= tail0 and (i - tail0) % 100 == 0:
                wet += state[..., 1] + v[..., 2] * dt
                nwet += 1
        st, tal = state, tacc[..., 0]
    # back to metres: the start surface (float64) + the change (+ what is still suspended, which settles where it is).
    # The seed stays only on fine levels (roughness_keep_m): elsewhere the change goes onto the unseeded surface
    klo, khi = p['roughness_keep_m']
    t = min(max((cell - klo) / max(khi - klo, 1e-9), 0.0), 1.0)
    keep = 1.0 - t * t * (3.0 - 2.0 * t)
    h_base = h_in + keep * (h0 - h_in)
    h_new = h_base + (st[..., 0].astype(np.float64) + st[..., 2]) * cell
    bed_new = h_base + st[..., 3].astype(np.float64) * cell
    # without rock_fail only deposits slide, so what the thermal pass moved stays in `deposit`; with it, what the
    # cohesive ground shed is talus
    finish(fields, h_new, bed_new, h_base, pw, ph,
           talus=np.maximum(tal.astype(np.float64), 0.0) * cell if p['rock_fail'] else None,
           wet=(wet / max(nwet, 1)) * cell, level=level,
           anchor_m=anchor_scale_m(level, p['anchor_m']) if p['anchor'] else None)
    dh = fields['h'] - h_base
    sec = time.perf_counter() - t0
    log(f'level {level.index} ({level.cell:.3g} m x{level.n}): {steps} steps in {sec:.1f} s; eroded '
        f'{np.percentile(np.maximum(-dh, 0), 99):.3f} m p99, deposited {np.percentile(np.maximum(dh, 0), 99):.3f} m '
        f'p99, |dh| mean {np.abs(dh).mean():.4f} m')
    return fields


def anchor(change, scale_cells):
    """The part of a level's change narrower than `scale_cells`: the change minus its low-pass (three box passes, a
    near-Gaussian of sigma about scale / 2). A detail op that keeps only this adds rills, couloirs and hummocks but
    leaves broad change (a gully 3 parent pixels wide, a fan's bulk, a wall's retreat) to the levels above, which hold
    the landform: on a real place, the DEM. (An exact 2 x 2 block projection removes a 2-cell rill's volume with its
    block mean: 74 % of its depth; this keeps it.)"""
    d = np.asarray(change, np.float64)
    r = max(1, int(round(0.4 * float(scale_cells))))          # three box passes of radius r: sigma (r (r + 1))^0.5
    return d - _box(_box(_box(d, r), r), r)


def anchor_scale_m(level, p_anchor_m=None):
    """The anchor's scale in metres: given, or 1.5 main-level cells (the main cell is cell x 2^-depth on a hero level;
    12 m at Lauterbrunnen's 8 m DEM: measured there, the hero levels at the DEM's pixel then keep their slope
    percentiles within 0.3 degrees, relief within 0.7 % and the hypsometric integral within 0.001, while the fine
    relief is what a 16 m anchor gives), else three of the level's cells."""
    if p_anchor_m:
        return float(p_anchor_m)
    depth = int(getattr(level, 'depth', 0) or 0)
    if depth < 0:
        return 1.5 * float(level.cell) * 2.0 ** (-depth)
    return 3.0 * float(level.cell)


def finish(fields, h_new, bed_new, h_base, pin_w, pin_h, talus=None, wet=None, level=None, anchor_m=None):
    """Write a detail op's result into the fields: with anchor_m (metres; on a level with a parent), only the change
    narrower than that (anchor); h blended to the pins once (h = mix(h_new, pin_h, pin_w): the border band fades from
    the detail to its parent's surface), bed under it, and wear / deposit / talus added from the process change
    h_new - h_base (faded the same way: where the processes acted, whatever the anchor kept)."""
    w = np.clip(np.asarray(pin_w, np.float64), 0.0, 1.0)
    keep = 1.0 - w
    dh = (h_new - h_base) * keep
    if anchor_m and level is not None and getattr(level, 'parent', None) is not None:
        moved = anchor(h_new - h_base, float(anchor_m) / float(level.cell)) - (h_new - h_base)
        h_new = h_new + moved
        bed_new = bed_new + moved
    h = h_new * keep + np.asarray(pin_h, np.float64) * w
    fields['h'] = h
    fields['bed'] = np.minimum(np.minimum(bed_new, h_new) * keep + np.asarray(pin_h, np.float64) * w, h)
    fields['wear'] = np.asarray(fields.get('wear', 0.0)) + np.maximum(-dh, 0.0)
    fields['deposit'] = np.asarray(fields.get('deposit', 0.0)) + np.maximum(dh, 0.0)
    if talus is not None:
        fields['talus'] = np.asarray(fields.get('talus', 0.0)) + talus * keep
    if wet is not None:
        fields['wet'] = wet * keep
    return fields


OPS = {'hydraulic': op_hydraulic}
