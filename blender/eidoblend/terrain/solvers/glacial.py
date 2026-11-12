"""The glacial carve (design section 4.5): troughs, hanging valleys, cirques and talus carved where ice would flow,
guided by the fluvial network. A procedural carve, not ice physics: the shallow-ice approximation carves narrow
defiles, not U-valleys (the research's finding).

    stage ops (OPS; run.py calls op(fields, level, params, seed, ctx=...)):
      'valley_uplift'  the uplift of a glaciated range around one main valley: a crest across its head and two side
                       ridges along it ('horseshoe', the default: Lauterbrunnen's setting), or a compose.uplift
                       shape (ridge, dome, plateau, massif). U on the coarsest level's passes, the rough start
                       surface on its first; the fields 'trough' etc. start at 0 so a `where` can read them
      'glacial'        on the coarsest level, once it is fully grown: the ice discharge, the glaciated centrelines,
                       the cirques, the jump flood, the U-carve, the fresh walls' threshold and lateral moraines. On
                       every finer level: the walls it inherits keep their steep threshold (the recipe keeps the
                       fluvial refinement off the trough with where='1 - trough'), and fail at it at the level's
                       own scale where the rock is weak, with fall-line couloirs and ribs (wall_flutes) on the
                       levels that resolve them. (The carve's seeds cannot reach a finer level: run.py carries fields
                       only, so a finer level refines the carved surface it inherits rather than re-carving.)

The carve, step by step (each a GPU kernel where the work is per cell):
  1. Ice discharge (kernels/ice_flux.glsl, iterated to convergence). Mass balance b(z) = clamp(beta (z - ELA),
     -b_abl, b_acc) at altitude z = h + base_elevation_m, routed down the D8 receivers of the lake-filled surface
     (or the water's MFD weights, p_ice > 0): Q = max(0, Q_in + a), a = b cell^2 on accumulating cells and
     b cell L on ablating ones, L = 2 W(Q_in) the tongue's width (a glacier ablates over its width, not over the
     one cell its discharge is routed through: with cell^2 a tongue ran 30 times too far). The same kernel with
     b = 1 everywhere gives the D8 drainage area.
  2. Centrelines (numpy): cells with ice, a drainage area of a channel, and a trough at least min_width_cells
     wide. Streams by main stem (each cell's largest donor continues its stream), positions and parameters
     smoothed along each stream. Per seed: f = min((Q / Q_ref)^0.4, f_max) with Q_ref the largest discharge in
     the main tile, half-width W = W_t f, the wall from the floor to the lip H = H_t f, the floor zf = z_c - d
     (z_c the channel, d = overdeepen H: depth grows with discharge, not with the floor downstream, so trunks
     overdeepen and tributaries hang above them by d_trunk (1 - f)); W and H wobble along the valley with world
     noise (wobble_*), and the sediment fill (graded_fill) grades every floor down-valley at floor_grade and meets
     the river below each glacier's end, so no reach of floor is a closed basin.
  3. Cirques (numpy): at glacier heads at or above ELA - cirque_band_m, spaced by blue-noise rejection, a bowl
     backed onto the divide above its head (its headwall reaching the crest there), elongated down-glacier and open
     on that side, its rim lobed, its floor at ELA - 50 m (never more than cirque_depth_m below the head, nor more
     than cirque_tarn_m below the glacier's trough at its lip). Where they meet, the walls between them stand as
     aretes and horns.
  4. Jump flood (kernels/jump_flood.glsl, Rong & Tan 2006, log2 passes + 1): every cell's four best seeds from
     DIFFERENT streams, ranked by the trough's target height there (not by distance: the target is a lower
     envelope, so a trunk's trough wins over a nearer tributary's, and a step in a floor becomes a riegel).
  5. U-carve (kernels/u_carve.glsl): the target T_s(x) = zf + max(H prof(r / W), fillz) per seed, the four joined
     by a smooth minimum (C1, join_m wide: no creases where troughs meet), the cirque bowls likewise, then
     h = smooth_min(h, T, trim_m): the trough cuts into the range and meets it at a trimline. The cross-section
     prof(rho) is flat on the floor (rho <= floor_frac), the wall ((rho - floor_frac) / (1 - floor_frac))^b up to
     the lip (rho = r / W = 1), then a shoulder 1 + shoulder_rise ((rho - 1) / shoulder_width)^shoulder_exp and
     the upper wall: the trough-in-trough of Lauterbrunnen, sheer walls under benches (Muerren, Wengen). fillz is
     the fill's top, rising floor_rise H from the river to the walls' foot (fans and aprons). Beyond the lip the
     carve is capped at cut H, easing to 0 at the trimline: benches where the ground was low, truncated spurs where
     it was high. The bedrock under the fill is T without the fill term, so h - bed is the valley fill.
  6. Fresh walls: the threshold pass (solvers/hillslope.py) with Sc = tan(wall_deg) x lognormal noise in the
     trough, the range's own Sc outside; the debris lands as talus at the walls' feet (the talus stage after
     this one sets it at 35 degrees).
  7. Lateral moraines: ridges of moraine_m along the trough below the ELA, at the foot of the walls.
The level runner's end stage fills what closed basins remain (recipe defaults lakes='sediment': flat floors;
'lake': ribbon lakes and tarns).

Fields written: h, bed, wear (+ the carve), deposit (+ the fill), talus, Sc (the walls' threshold), ice (the
glacier's thickness at the carving maximum, m), trough (0..1, the trough and cirque footprint), trough_floor (the
flat floor), trough_wall (the walls: trough minus floor), carve (the depth the ice removed, m: fresh rock), and on
the coarsest level ice_q (the ice discharge, m^3/yr) and glacial_streams (the stream id of each centreline cell, -1
elsewhere).

Parameters (metres, years, degrees; DEFAULTS below):
    ela_m 2400                  the equilibrium-line altitude of the carving glaciation (altitude, not h)
    beta 0.005, b_acc_m 2, b_abl_m 6     the mass balance: m/yr per m of height, the caps (ice equivalent)
    p_ice 0                     0: D8 routing (each cell's whole discharge on its steepest neighbour); > 0: the
                                water's MFD weights at that exponent (the design's; the discharge then spreads
                                over a valley floor's cells and the troughs follow no single centreline)
    ice_width_m 750, ice_width_q 5e7, ice_width_exp 0.4, ice_width_max_m 3000
                                the ablating tongue's half-width W(Q) = 750 (Q / 5e7)^0.4 m (a large valley
                                glacier: 5e7 m^3/yr, 1.5 km wide)
    trough_width_m 1200         the main tile's trunk trough: its width at the lip ...
    trough_depth_m 600          ... and its depth from the flat floor to the lip
    floor_frac 0.25             the flat floor's share of the trough's half-width (the wall starts at its edge)
    u_exponent 2.4              the wall's profile H ((rho - floor_frac) / (1 - floor_frac))^b
    floor_rise 0.06             the fill's rise from the river to the walls' foot, a share of H
    overdeepen 0.6              the floor's depth below the pre-glacial channel, a share of H
    wobble_m 700, wobble_w 0.12, wobble_h 0.1   W and H vary along the valley by world noise at this wavelength
    shoulder_width 0, shoulder_rise 0.25, shoulder_exp 2, upper_wall 1.5
                                the shoulder beyond the lip: shoulder_width W wide, rising shoulder_rise H (0: none),
                                then the upper wall rising upper_wall H per W to the trimline
    cut 0.6, cut_width 2        beyond the lip the ice lowers the ground by at most cut H, easing to 0 at
                                cut_width W past the lip (the trimline): benches where the ground was low, truncated
                                spurs where it was high, nothing planed beyond (an uncapped shoulder planed the side
                                ridges: the main tile lost 1.1 km of relief, and a 56-degree band ran along every
                                trough)
    floor_grade 0.012           the valley fill's top falls at least this grade down-valley: overdeepenings fill to
                                their downstream rim, a glacier's last reach to the river below it, then grade
                                up-valley (None: no fill)
    f_max 1.6                   the widest trough relative to the trunk's (glaciers beyond the main tile)
    channel_area_m2 1.5e6, min_width_cells 2    what counts as a glaciated centreline
    smooth_cells 6              the centrelines' smoothing along each stream (the D8 staircase, the confluences'
                                jumps in width and depth), as a Gaussian sigma in cells
    join_m 60, trim_m 20        the smooth minimum's widths: between troughs, and at the trimline
    cirques True, cirque_band_m 300, cirque_radius_m [400, 800], cirque_elong 1.35, cirque_depth_m 350,
    cirque_floor_m 50 (below the ELA), cirque_headwall_m 500, cirque_exp 2, cirque_floor_frac 0.35 (the flat floor's
    share of the bowl), cirque_spacing 1.5 (x the radius), cirque_open 2.5 (the bowl's reach down-glacier, x R_along),
    cirque_tarn_m 40 (the deepest the floor sits below the glacier's trough at the bowl's lip), cirque_lobes 0.15
    (the rim's lobed irregularity), cirque_headroom_m 0 (the headwall's reach above the crest)
    wall_deg 65, wall_noise 0.15, wall_scales_m [400, 120], wall_iters 64, refine_wall_iters 160
                                the fresh walls' threshold (lognormal at the wall scales) and its passes on the
                                carving level and on every finer one
    flute_weak 0.9, flute_strong 0.35, flute_scales_m [80, 40, 20], flute_stretch 5
                                fall-line flutes in the walls' threshold on the levels that resolve them (3 cells):
                                couloirs where it falls by flute_weak in ln tan, ribs where it rises by flute_strong,
                                the noise stretched flute_stretch times down the fall line
    rock_flutes 0, rock_flute_deg 38   the flutes, scaled by rock_flutes, on the range's own rock steeper than
                                rock_flute_deg (finer levels): couloirs and ribs on every face, not only the walls
    cap_join_m 40               the smooth maximum where the cap beyond the lip meets the trough
    moraine_m 25, moraine_at None, moraine_width 0.07
                                the lateral moraines' height for the trunk (scaled by f; 0: none), where they stand
                                (a share of W; None: floor_frac + 0.1, at the foot of the walls) and their width
"""
from __future__ import annotations

import math
import time

import numpy as np

from ..core import compose as C
from ..core import grid as Gd
from ..core import twins as T
from . import fluvial as FL
from . import hydro as HY

F32 = np.float32
OPEN, PERIODIC, PINNED = T.BOUND_OPEN, T.BOUND_PERIODIC, T.BOUND_PINNED

DEFAULTS = dict(
    ela_m=2400.0, beta=0.005, b_acc_m=2.0, b_abl_m=6.0, p_ice=0.0,
    ice_width_m=750.0, ice_width_q=5.0e7, ice_width_exp=0.4, ice_width_max_m=3000.0,
    trough_width_m=1200.0, trough_depth_m=600.0, floor_frac=0.25, u_exponent=2.4, floor_rise=0.06, overdeepen=0.6,
    f_max=1.6, shoulder_width=0.0, shoulder_rise=0.25, shoulder_exp=2.0, upper_wall=1.5, cut=0.6, cut_width=2.0,
    floor_grade=0.012,
    wobble_m=700.0, wobble_w=0.12, wobble_h=0.1,
    channel_area_m2=1.5e6, min_width_cells=2.0, smooth_cells=6.0, join_m=60.0, trim_m=20.0,
    cirques=True, cirque_band_m=300.0, cirque_radius_m=(400.0, 800.0), cirque_elong=1.35, cirque_depth_m=350.0,
    cirque_floor_m=50.0, cirque_floor_frac=0.35, cirque_exp=2.0, cirque_spacing=1.5, cirque_headroom_m=0.0,
    cirque_headwall_m=500.0, cirque_open=2.5, cirque_tarn_m=40.0, cirque_lobes=0.15,
    wall_deg=65.0, wall_noise=0.15, wall_scales_m=(400.0, 120.0), wall_iters=64, wall_rate=0.12,
    flute_weak=0.9, flute_strong=0.35, flute_scales_m=(80.0, 40.0, 20.0), flute_stretch=5.0, cap_join_m=40.0,
    rock_flutes=0.0, rock_flute_deg=38.0,
    moraine_m=25.0, moraine_at=None, moraine_width=0.07,
    refine_wall_iters=160, seed=0,
)
MAX_CIRQUES = 512


def _p(params, key):
    v = (params or {}).get(key, DEFAULTS[key])
    return DEFAULTS[key] if v is None else v


def moraine_at(params):
    """Where the lateral moraine stands, a share of the half-width: given, or just past the flat floor's edge (at the
    foot of the walls, where the last glacier's margin lay)."""
    v = (params or {}).get('moraine_at')
    return float(v) if v is not None else float(_p(params, 'floor_frac')) + 0.1


# ================================================================================================ the twins ===

def d8_receivers(h, cell, bound=OPEN):
    """Each cell's steepest-descent neighbour k (common.glsl's order) as float32, -1 where none is lower (an open
    edge's outlet, a pit). Ties go to the lowest k, as a strict > over k = 0..7 does."""
    h = np.asarray(h, F32)
    best = np.zeros(h.shape, F32)
    out = np.full(h.shape, -1.0, F32)
    for k in range(8):
        hq, ok = T.neighbour(h, k, bound)
        s = (h - hq) / (T.LEN[k] * F32(cell))
        better = ok & (s > best)
        best = np.where(better, s, best)
        out = np.where(better, F32(k), out)
    return out


def wpow(s, e):
    return s if float(e) == 1.0 else np.power(s, F32(e)).astype(F32)


@T.twin('ice_flux')
def ice_flux(s, u):
    """kernels/ice_flux.glsl: one Jacobi iteration of the ice discharge (module doc, step 1)."""
    h, w, Q0 = s['st'][..., 0], s['wT'][..., 0], s['qT'][..., 0]
    b, qin = s['mb'][..., 0], s['mb'][..., 1].copy()
    dx, bound = u['uDx'], u['uBound']
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        for k in range(8):
            hq, ok = T.neighbour(h, k, bound)
            Qq, _ = T.neighbour(Q0, k, bound)
            if u['uD8'] == 1:
                rq, _ = T.neighbour(w, k, bound, fill=-1.0)
                take = ok & (rq.astype(np.int32) == 7 - k)
                qin = np.where(take, qin + Qq, qin)
            else:
                wq, _ = T.neighbour(w, k, bound)
                up = ok & (hq > h)
                sl = np.where(up, (hq - h) / (T.LEN[k] * dx), F32(1))
                qin = np.where(up, qin + Qq * (wpow(sl, u['uP']) / np.maximum(wq, F32(1e-30))), qin)
        L = np.clip(F32(2) * u['uWref'] * np.power(np.maximum(qin, F32(0)) / u['uQw'], u['uWexp']).astype(F32),
                    dx, max(u['uLmax'], dx)).astype(F32)
        a = np.where(b >= 0, b * dx * dx, b * dx * L)
    return {'outQ': np.maximum(qin + a, F32(0))[..., None]}


def _top4(C, m, sid):
    """The four best candidates (by metric, then index) of DIFFERENT streams, per cell: (idx (H, W, 4) float32,
    -1 where fewer). C, m, sid: (H, W, K) candidate index (-1 none), metric, stream id."""
    valid = C >= 0
    key_i = np.where(valid, C, np.float32(3.0e38))
    key_m = np.where(valid, m, np.inf)
    o1 = np.argsort(key_i, axis=-1, kind='stable')
    o2 = np.argsort(np.take_along_axis(key_m, o1, -1), axis=-1, kind='stable')
    order = np.take_along_axis(o1, o2, -1)
    Cs = np.take_along_axis(C, order, -1)
    Ss = np.take_along_axis(sid, order, -1)
    Vs = np.take_along_axis(valid, order, -1)
    out = np.full(C.shape[:2] + (4,), -1.0, F32)
    outs = np.full(C.shape[:2] + (4,), np.nan, F32)
    count = np.zeros(C.shape[:2], np.int64)
    for k in range(C.shape[2]):
        ck, sk, vk = Cs[..., k], Ss[..., k], Vs[..., k]
        dup = np.zeros(ck.shape, bool)
        for t in range(4):
            dup |= outs[..., t] == sk
        take = vk & ~dup & (count < 4)
        for t in range(4):
            put = take & (count == t)
            out[..., t] = np.where(put, ck, out[..., t])
            outs[..., t] = np.where(put, sk, outs[..., t])
        count = count + take
    return out


def _seed_lookup(idx, seedA, seedB):
    """Seed data for candidate indices idx (any shape, -1 none): (valid, A (..., 4), B (..., 4))."""
    h, w = seedA.shape[:2]
    valid = idx >= 0
    ci = np.where(valid, idx, 0).astype(np.int64)
    cy, cx = ci // w, ci % w
    return valid, seedA[cy, cx], seedB[cy, cx]


def prof(rho, u, dtype=F32):
    """The trough's cross-section above its floor, in units of H (jump_flood.glsl / u_carve.glsl prof), with the
    profile uniforms u (profile_uniforms): 0 on the floor (rho <= uFloorFrac), ((rho - uFloorFrac) / (1 -
    uFloorFrac))^uB up the wall to the lip (rho = r / W = 1), then the shoulder 1 + uShH ((rho - 1) / uShW)^uShB
    (uShW 0: the wall's law continues), then the upper wall 1 + uShH + uOut (rho - 1 - uShW) to the trimline."""
    rho = np.asarray(rho, dtype)
    ff = dtype(u['uFloorFrac'])
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        inner = np.power(np.maximum(rho - ff, dtype(0)) / (dtype(1) - ff), dtype(u['uB'])).astype(dtype)
        if float(u['uShW']) <= 0.0:
            return inner
        sw, sh = dtype(u['uShW']), dtype(u['uShH'])
        s = (np.maximum(rho - dtype(1), dtype(0)) / sw).astype(dtype)
        shoulder = (dtype(1) + sh * np.power(s, dtype(u['uShB']))).astype(dtype)
        upper = (dtype(1) + sh + dtype(u['uOut']) * (rho - dtype(1) - sw)).astype(dtype)
    return np.where(rho <= 1, inner, np.where(s <= 1, shoulder, upper)).astype(dtype)


def fillz(rho, fill, H, u, dtype=F32):
    """The valley fill's top above zf (the kernels' fillz): fill + uFloorRise H min(rho / uFloorFrac, 1)^2."""
    t = np.minimum(np.asarray(rho, dtype) / dtype(max(float(u['uFloorFrac']), 1e-3)), dtype(1))
    return (np.asarray(fill, dtype) + dtype(u['uFloorRise']) * np.asarray(H, dtype) * t * t).astype(dtype)


def _metric(xp, yp, A, B, u, mode):
    """jump_flood.glsl metric(): the target height (mode 0) or the distance (1), float32."""
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        ddx = (xp - A[..., 0]).astype(F32)
        ddy = (yp - A[..., 1]).astype(F32)
        r = np.sqrt(ddx * ddx + ddy * ddy).astype(F32)
        if mode == 1:
            return r
        rho = (r / B[..., 0]).astype(F32)
        wall = A[..., 3] * prof(rho, u)
        return (A[..., 2] + np.maximum(wall, fillz(rho, B[..., 2], A[..., 3], u))).astype(F32)


@T.twin('jump_flood')
def jump_flood(s, u):
    """kernels/jump_flood.glsl: one jump-flooding pass at step uStep (module doc, step 4)."""
    cand, sA, sB = s['candT'], s['seedA'], s['seedB']
    n0, n1 = cand.shape[:2]
    step, dx, mode = int(u['uStep']), F32(u['uDx']), int(u['uMetric'])
    jj, ii = np.mgrid[0:n0, 0:n1]
    xp = ((ii.astype(F32) + F32(0.5)) * dx)[..., None]
    yp = ((jj.astype(F32) + F32(0.5)) * dx)[..., None]
    cs = []
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            sh, ok = T.shift(cand, ox * step, oy * step, OPEN, fill=-1.0)
            for c in range(4):
                cs.append(np.where(ok, sh[..., c], F32(-1)))
    Cc = np.stack(cs, -1)
    valid, A, B = _seed_lookup(Cc, sA, sB)
    m = np.where(valid, _metric(xp, yp, A, B, u, mode), np.inf)
    return {'outC': _top4(Cc, m.astype(F32), np.where(valid, B[..., 1], np.nan))}


def smin(a, b, k):
    """compose.smooth_min in float32 (the kernels' smin); k a number or an array (0: the plain minimum)."""
    a = np.asarray(a, F32)
    b = np.asarray(b, F32)
    k = np.asarray(k, F32)
    if k.ndim == 0 and float(k) <= 0:
        return np.minimum(a, b)
    with np.errstate(invalid='ignore', divide='ignore'):
        hh = np.where(k > 0, np.maximum(k - np.abs(a - b), F32(0)) / np.where(k > 0, k, F32(1)), F32(0))
    return (np.minimum(a, b) - hh * hh * k * F32(0.25)).astype(F32)


def smax(a, b, k):
    """u_carve.glsl's smax: -smin(-a, -b, k)."""
    return (-smin(-np.asarray(a, F32), -np.asarray(b, F32), k)).astype(F32)


def _smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, F32) - F32(e0)) / F32(e1 - e0), F32(0), F32(1))
    return (t * t * (F32(3) - F32(2) * t)).astype(F32)


@T.twin('u_carve')
def u_carve(s, u):
    """kernels/u_carve.glsl: the U-carve (module doc, step 5)."""
    cand, sA, sB, st, cq, pin = s['candT'], s['seedA'], s['seedB'], s['st'], s['cirq'], s['pin']
    n0, n1 = cand.shape[:2]
    dx = F32(u['uDx'])
    join, trim = float(u['uJoin']), float(u['uTrim'])
    ff = F32(u['uFloorFrac'])
    ffc = F32(min(max(float(u['uFloorFrac']), 0.0), 0.95))
    cf = F32(min(max(float(u['uCirqFloor']), 0.0), 0.95))
    jj, ii = np.mgrid[0:n0, 0:n1]
    xp = (ii.astype(F32) + F32(0.5)) * dx
    yp = (jj.astype(F32) + F32(0.5)) * dx
    big = F32(1.0e30)
    Tf = np.full((n0, n1), big, F32)
    Tr = np.full((n0, n1), big, F32)
    ice_top = np.full((n0, n1), -big, F32)
    rw0 = np.full((n0, n1), F32(10.0), F32)
    mor = np.zeros((n0, n1), F32)
    cap = np.zeros((n0, n1), F32)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        for c in range(4):
            valid, A, B = _seed_lookup(cand[..., c], sA, sB)
            ddx = (xp - A[..., 0]).astype(F32)
            ddy = (yp - A[..., 1]).astype(F32)
            r = np.sqrt(ddx * ddx + ddy * ddy).astype(F32)
            rw = (r / B[..., 0]).astype(F32)
            wall = (A[..., 3] * prof(rw, u)).astype(F32)
            tf = (A[..., 2] + np.maximum(wall, fillz(rw, B[..., 2], A[..., 3], u))).astype(F32)
            tr = (A[..., 2] + wall).astype(F32)
            Tf = np.where(valid, smin(Tf, tf, join) if c else tf, Tf)
            Tr = np.where(valid, smin(Tr, tr, join) if c else tr, Tr)
            # the cap beyond the lip (module doc, step 5): uCut H, easing to 0 at the trimline
            tq = np.clip((rw - F32(1)) / F32(max(float(u['uCutW']), 1e-3)), F32(0), F32(1)).astype(F32)
            cc = np.where(rw <= 1, big, F32(u['uCut']) * A[..., 3] * (F32(1) - tq * tq * (F32(3) - F32(2) * tq)))
            cap = np.where(valid, np.maximum(cap, cc), cap).astype(F32)
            if c == 0:
                rw0 = np.where(valid, rw, rw0)
                ice_top = np.where(valid & (rw < F32(1) + F32(u['uShW'])),
                                   A[..., 2] + A[..., 3] * (F32(1) + F32(u['uShH'])), ice_top)
                # the lateral moraine: a ridge along the trough at uMorAt of its half-width (B.w: its height)
                g = (rw - F32(u['uMorAt'])) / F32(u['uMorW'])
                mor = np.where(valid, B[..., 3] * np.exp(-g * g).astype(F32), F32(0))
        for k in range(int(u['uNCirq'])):
            c0, c1 = cq[0, k], cq[1, k]
            ddx = (xp - c0[0]).astype(F32)
            ddy = (yp - c0[1]).astype(F32)
            along = (ddx * c1[0] + ddy * c1[1]).astype(F32)
            across = (-ddx * c1[1] + ddy * c1[0]).astype(F32)
            ua = (along / np.where(along > 0, c1[3] * F32(u['uCirqOpen']), c1[3])).astype(F32)
            uc = (across / c1[2]).astype(F32)
            c2 = cq[2, k]
            th = np.arctan2(uc, ua).astype(F32)
            lobes = (F32(1) + c2[2] * (F32(0.6) * np.sin(F32(3) * th + c2[0]) + F32(0.4) * np.sin(F32(5) * th + c2[1])))
            rho = (np.sqrt(ua * ua + uc * uc) / lobes).astype(F32)
            t = (np.maximum(rho - cf, F32(0)) / (F32(1) - cf)).astype(F32)
            tc = (c0[2] + c0[3] * np.power(t, F32(u['uCirqExp'])).astype(F32)).astype(F32)
            Tf = smin(Tf, tc, join)
            Tr = smin(Tr, tc, join)
            ice_top = np.where(rho < 1, np.maximum(ice_top, c0[2] + F32(0.35) * c0[3]), ice_top)
            cap = np.where(rho < 1, big, cap)
            rq = np.where(rho <= cf, rho * ffc / F32(max(float(cf), 1e-3)),
                          ffc + (rho - cf) * (F32(1) - ffc) / (F32(1) - cf)).astype(F32)
            rw0 = np.minimum(rw0, rq)
    h, bed = st[..., 0], st[..., 1]
    kc = np.minimum(F32(u['uCapJoin']), cap).astype(F32)
    hn = smax(smin(h, Tf, trim), (h - cap).astype(F32), kc)
    carved = (h - hn).astype(F32)
    hn = (hn + np.where(carved > 0, mor, F32(0))).astype(F32)
    bn = np.minimum(smax(smin(bed, Tr, trim), (bed - cap).astype(F32), kc), hn).astype(F32)
    if u['uBound'] == PINNED:
        hn = T.pin_apply(hn, pin[..., 0], pin[..., 1])
        bn = np.minimum(bn, hn)
    ice = np.where(ice_top > -big, np.maximum(ice_top - hn, F32(0)), F32(0)).astype(F32)
    floor = (F32(1) - _smoothstep(ff, ff + F32(0.12), rw0)).astype(F32)
    trough = (F32(1) - _smoothstep(F32(0.85), F32(1.15), rw0)).astype(F32)
    return {'outS': T.rgba(hn, bn, Tf, ice), 'outM': T.rgba(np.maximum(carved, F32(0)), floor * trough,
                                                               trough * (F32(1) - floor), trough)}


# ============================================================================================ mass balance ===

def mass_balance(h, base_elevation_m, params):
    """b (m/yr of ice) at every cell: clamp(beta (altitude - ELA), -b_abl, b_acc)."""
    z = np.asarray(h, np.float64) + float(base_elevation_m)
    b = float(_p(params, 'beta')) * (z - float(_p(params, 'ela_m')))
    return np.clip(b, -float(_p(params, 'b_abl_m')), float(_p(params, 'b_acc_m'))).astype(F32)


def ice_flux_converge(dev, surface, b, cell, recv=None, p_ice=0.0, Q_in=None, params=None, bound=OPEN, tol=1e-6,
                      check=128, max_iter=None):
    """The ice discharge Q (m^3/yr) on a fixed routing surface: ice_flux.glsl iterated from Q = 0 until the largest
    change over `check` iterations is under tol x the largest Q (a discharge on a filled surface is a DAG sum:
    it stops changing after its longest flow path). Returns (Q float32 (n, n), iterations)."""
    surface = np.asarray(surface, F32)
    ny, nx = surface.shape
    st = dev.texture(surface)
    d8 = p_ice is None or float(p_ice) <= 0.0
    if d8:
        wT = dev.texture(recv if recv is not None else d8_receivers(surface, cell, bound))
    else:
        wT = dev.empty((ny, nx), 1)
        dev.run('flow_weights', {'st': st}, {'outW': wT}, {'uDx': cell, 'uP': float(p_ice), 'uBound': bound})
    qin = np.zeros((ny, nx), F32) if Q_in is None else np.asarray(Q_in, F32)
    mb = dev.texture(np.stack([np.asarray(b, F32), qin], -1))
    src, dst = dev.texture(np.zeros((ny, nx), F32)), dev.empty((ny, nx), 1)
    uni = {'uDx': float(cell), 'uP': float(p_ice or 0.0), 'uWref': float(_p(params, 'ice_width_m')),
           'uQw': float(_p(params, 'ice_width_q')), 'uWexp': float(_p(params, 'ice_width_exp')),
           'uLmax': float(_p(params, 'ice_width_max_m')), 'uD8': 1 if d8 else 0, 'uBound': bound}
    max_iter = int(max_iter or 8 * max(ny, nx))
    prev = np.zeros((ny, nx))
    it = 0
    while it < max_iter:
        for _ in range(check):
            dev.run('ice_flux', {'st': st, 'wT': wT, 'qT': src, 'mb': mb}, {'outQ': dst}, uni)
            src, dst = dst, src
        it += check
        cur = dev.read(src)[..., 0].astype(np.float64)
        change = float(np.max(np.abs(cur - prev))) / max(float(cur.max()), 1e-30)
        prev = cur
        if change <= tol:
            break
    return prev.astype(F32), it


def flux_budget(Q, b, recv, cell, params, Q_in=None, bound=OPEN):
    """The ice-flux mass balance of a converged Q (a check, numpy float64): accumulation (sum of b cell^2 where
    b >= 0), the ablation actually realised (where b < 0: min(-a, Q_in of the cell)), the inflow from outside, and
    the outflow (the discharge of cells whose receiver is off the grid or that have none). Closes when
    accumulation + inflow - ablation = outflow."""
    Q = np.asarray(Q, np.float64)
    b = np.asarray(b, np.float64)
    rk = np.asarray(recv).astype(np.int64)
    ny, nx = Q.shape
    qin = np.zeros_like(Q) if Q_in is None else np.asarray(Q_in, np.float64).copy()
    has_out = np.zeros(Q.shape, bool)
    for k in range(8):
        dxk, dyk = T.OFF[k]
        src = rk == k                                   # cells whose receiver is k: they pass Q to (i + dx, j + dy)
        Qs, ok = T.shift(np.where(src, Q, 0.0), -dxk, -dyk, bound)
        qin += np.where(ok, Qs, 0.0)
    for k in range(8):
        dxk, dyk = T.OFF[k]
        _, ok = T.shift(Q, dxk, dyk, bound)
        has_out |= (rk == k) & ok
    W = np.clip(2.0 * float(_p(params, 'ice_width_m')) * np.power(np.maximum(qin, 0.0) / float(_p(params, 'ice_width_q')),
                                                                   float(_p(params, 'ice_width_exp'))),
                cell, max(float(_p(params, 'ice_width_max_m')), cell))
    a = np.where(b >= 0, b * cell * cell, b * cell * W)
    acc = float(a[a > 0].sum())
    abl = float(np.minimum(-a, qin)[a < 0].sum())
    inflow = float(np.asarray(Q_in, np.float64).sum()) if Q_in is not None else 0.0
    out = float(Q[~has_out].sum())
    resid = acc + inflow - abl - out
    return dict(accumulation=acc, inflow=inflow, ablation=abl, outflow=out, residual=resid,
                rel_residual=resid / max(acc + inflow, 1e-30))


# ======================================================================================= the centrelines ===

def _flat_neighbour(idx, k, ny, nx):
    """The flat index of neighbour k of flat cells idx (-1 off the grid)."""
    j, i = np.divmod(idx, nx)
    di, dj = T.OFF[k]
    i2, j2 = i + di, j + dj
    ok = (i2 >= 0) & (j2 >= 0) & (i2 < nx) & (j2 < ny)
    return np.where(ok, j2 * nx + i2, -1)


def streams(seed_mask, recv, Q):
    """The glaciated centrelines as streams (main stems: every cell's largest donor continues its stream).
    Returns dict(idx (S,) flat cell index, rcv (S,) the receiver's position in idx or -1, main (S,) the main donor's
    position or -1, sid (S,) stream id (0..), head (S,) bool: no donor). numpy."""
    ny, nx = seed_mask.shape
    idx = np.flatnonzero(seed_mask)
    S = idx.size
    pos = np.full(ny * nx, -1, np.int64)
    pos[idx] = np.arange(S)
    rk = np.asarray(recv).ravel()[idx].astype(np.int64)
    rcv_cell = np.full(S, -1, np.int64)
    for k in range(8):
        sel = rk == k
        if sel.any():
            rcv_cell[sel] = _flat_neighbour(idx[sel], k, ny, nx)
    rcv = np.where(rcv_cell >= 0, pos[np.maximum(rcv_cell, 0)], -1)
    q = np.asarray(Q, np.float64).ravel()[idx]
    # the main donor of each receiver: its largest-discharge donor (ties: the lower index)
    main = np.full(S, -1, np.int64)
    d = np.flatnonzero(rcv >= 0)
    if d.size:
        order = np.lexsort((d, -q[d], rcv[d]))             # by receiver, then discharge descending, then index
        dd = d[order]
        r_sorted = rcv[dd]
        first = np.ones(dd.size, bool)
        first[1:] = r_sorted[1:] != r_sorted[:-1]
        main[r_sorted[first]] = dd[first]
    parent = np.arange(S)
    is_main = np.zeros(S, bool)
    is_main[main[main >= 0]] = True
    cont = is_main & (rcv >= 0)
    parent[cont] = rcv[cont]
    while True:                                           # pointer jumping to each stream's downstream end
        p2 = parent[parent]
        if np.array_equal(p2, parent):
            break
        parent = p2
    _, sid = np.unique(parent, return_inverse=True)
    has_donor = np.zeros(S, bool)
    has_donor[rcv[rcv >= 0]] = True
    return dict(idx=idx, rcv=rcv, main=main, sid=sid.astype(np.int64), head=~has_donor, cont=cont)


def smooth_along(values, st, sigma_cells, link_tributaries=False):
    """Values per seed smoothed along each stream (repeated [1, 2, 1] / 4 passes: a Gaussian of sigma_cells). The
    upstream neighbour is the main donor; the downstream one the receiver when it continues the stream (with
    link_tributaries also a tributary's junction, so its last cells stay attached to the trunk). (S,) or (S, k)."""
    v = np.asarray(values, np.float64).copy()
    n = int(round(2.0 * float(sigma_cells) ** 2))
    if n <= 0 or v.shape[0] == 0:
        return v
    up = st['main']
    down = np.where(st['cont'] | (link_tributaries & (st['rcv'] >= 0)), st['rcv'], -1)
    has_up, has_dn = up >= 0, down >= 0
    upi, dni = np.maximum(up, 0), np.maximum(down, 0)
    for _ in range(n):
        vu = np.where(has_up[:, None] if v.ndim > 1 else has_up, v[upi], v)
        vd = np.where(has_dn[:, None] if v.ndim > 1 else has_dn, v[dni], v)
        v = 0.25 * vu + 0.5 * v + 0.25 * vd
    return v


def centrelines(h, Q, A, recv, level, main, params, base_elevation_m, seed=0):
    """The seeds of the U-carve (module doc, step 2): dict with the streams, per-seed world position (x, y),
    channel height zc, discharge q, f, W, H, d, zf, fill, moraine height, and Q_ref. None when no cell qualifies."""
    cell = float(level.cell)
    Wt = 0.5 * float(_p(params, 'trough_width_m'))
    ff = float(_p(params, 'floor_frac'))
    b = float(_p(params, 'u_exponent'))
    Hvis = float(_p(params, 'trough_depth_m'))
    Ht = Hvis / max(1.0 - ff ** b, 1e-3)
    dt = float(_p(params, 'overdeepen')) * Ht
    Q = np.asarray(Q, np.float64)
    chan = (Q > 0) & (np.asarray(A, np.float64) >= float(_p(params, 'channel_area_m2')))
    if not chan.any():
        return None
    j0, j1, i0, i1 = FL._main_window(level, main)
    win = np.zeros(Q.shape, bool)
    win[j0:j1, i0:i1] = True
    qref = float(Q[chan & win].max()) if (chan & win).any() else float(Q[chan].max())
    f = np.minimum(np.power(np.maximum(Q, 0.0) / max(qref, 1e-30), 0.4), float(_p(params, 'f_max')))
    seeds = chan & (Wt * f >= float(_p(params, 'min_width_cells')) * cell)
    if not seeds.any():
        return None
    st = streams(seeds, recv, Q)
    idx = st['idx']
    jj, ii = np.divmod(idx, Q.shape[1])
    x = level.x0 + (ii + 0.5) * cell
    y = level.y0 + (jj + 0.5) * cell
    sig = float(_p(params, 'smooth_cells'))
    xy = smooth_along(np.stack([x, y], 1), st, sig, link_tributaries=True)
    zc = smooth_along(np.asarray(h, np.float64).ravel()[idx], st, sig)
    fs = smooth_along(f.ravel()[idx], st, sig)
    W = Wt * fs
    H = Ht * fs
    d = dt * fs
    # the walls wander along the valley: W and H vary with world noise at the seeds (no two reaches alike, no
    # extruded tube), after the smoothing so it is not smoothed away
    wl, aw, ah = float(_p(params, 'wobble_m')), float(_p(params, 'wobble_w')), float(_p(params, 'wobble_h'))
    if wl > 0 and (aw > 0 or ah > 0):
        from ..core import world_noise as N
        n1 = 3.0 * np.asarray(N.fbm(xy[:, 0], xy[:, 1], wl, 3, seed=int(seed) * 31 + 801), np.float64)
        n2 = 3.0 * np.asarray(N.fbm(xy[:, 0], xy[:, 1], wl, 3, seed=int(seed) * 31 + 802), np.float64)
        W = W * np.clip(1.0 + aw * n1, 0.6, 1.4)
        H = H * np.clip(1.0 + ah * n2, 0.6, 1.4)
    zf = zc - d
    # every stream's end meets the river below it: where the ice ends on the grid, and where it runs off the grid's
    # edge, which is base level (pinned at the river's height). (Exempting the edge left the trunk's fill ungraded
    # at the coarsest level's edge and cost the generated tile its hanging valleys: 103 m to 31 m)
    fill = graded_fill(zf, np.zeros_like(zf), xy[:, 0], xy[:, 1], st, _p(params, 'floor_grade'), outlet=zc)
    ela_f = float(_p(params, 'ela_m')) - float(base_elevation_m)
    mor = np.where(zc < ela_f, float(_p(params, 'moraine_m')) * fs, 0.0)
    return dict(streams=st, idx=idx, x=xy[:, 0], y=xy[:, 1], zc=zc, q=Q.ravel()[idx], f=fs, W=W, H=H, d=d, zf=zf,
                fill=fill, moraine=mor, Q_ref=qref, Ht=Ht, Wt=Wt, dt=dt)


def graded_fill(zf, fill0, x, y, st, grade, outlet=None, max_iter=100000):
    """The valley fill's thickness above each seed's floor: at least fill0, and enough that the fill's top falls
    down-valley by at least `grade` (m/m) from each seed to its receiver, so an overdeepened basin fills to its
    downstream rim and then grades up-valley (Lauterbrunnen's floor falls 2 % over 5 km) instead of filling flat to
    one spill level. With `outlet` (the pre-glacial channel at each seed), a stream's last seed fills at least to
    the channel there: where a glacier ended, its trough's floor joins the river that carries on below it (left
    deep to its end, the trough closed in a wall and the level runner's end stage filled 7 km of it dead flat to the
    river's level). grade None: fill0. numpy float64."""
    fill0 = np.asarray(fill0, np.float64)
    if grade is None or zf.size == 0:
        return fill0
    rc = st['rcv']
    has = rc >= 0
    rci = np.maximum(rc, 0)
    L = np.where(has, np.hypot(x - x[rci], y - y[rci]), 0.0)
    top = zf + fill0
    if outlet is not None:
        top = np.where(has, top, np.maximum(top, np.asarray(outlet, np.float64)))
    for _ in range(max_iter):
        new = np.maximum(top, np.where(has, top[rci] + float(grade) * L, -np.inf))
        if np.array_equal(new, top):
            break
        top = new
    return top - zf


def best_donor(recv, A):
    """Each cell's largest-area donor (the cell draining into it with the largest A; -1 where none), flat indices:
    the way up a hollow to its divide."""
    ny, nx = A.shape
    r = np.asarray(recv).ravel().astype(np.int64)
    a = np.asarray(A, np.float64).ravel()
    idx = np.arange(ny * nx)
    ts, ds = [], []
    for k in range(8):
        sel = idx[r == k]
        t = _flat_neighbour(sel, k, ny, nx)
        ok = t >= 0
        ts.append(t[ok])
        ds.append(sel[ok])
    t = np.concatenate(ts)
    d = np.concatenate(ds)
    order = np.argsort(a[d], kind='stable')                   # the largest donor written last
    out = np.full(ny * nx, -1, np.int64)
    out[t[order]] = d[order]
    return out


def cirques(cl, params, base_elevation_m, level, h=None, up=None, seed=0):
    """The cirques (module doc, step 3): (N, 11) float64 rows (cx, cy, z_floor, headwall H_c, dir_x, dir_y,
    R_across, R_along, the rim's 3- and 5-lobed phases, their amplitude), world metres. With h and up (best_donor),
    each bowl backs onto the divide above its glacier head: the walk up the hollow's largest donors finds the divide,
    the bowl's centre sits 0.85 R_along down-glacier of it and its headwall reaches the crest there (the bowl at rho
    0.85 stands at the divide's height), so the crests stay and the walls under them steepen into aretes and horns
    (a bowl centred on the head with a fixed headwall cut the peaks down: the range lost a third of its relief).
    The floor stands at most cirque_tarn_m below the glacier's trough floor at the bowl's lip (1.5 R_along down
    its stream): it drains, or holds a tarn, instead of sinking into a pit that the end stage fills flat (a field of
    oval flat-floored bowls, the look of a racetrack, not of the Sierra)."""
    if cl is None or not bool(_p(params, 'cirques')):
        return np.zeros((0, 11))
    cell = float(level.cell)
    st = cl['streams']
    ela_f = float(_p(params, 'ela_m')) - float(base_elevation_m)
    band = float(_p(params, 'cirque_band_m'))
    heads = np.flatnonzero(st['head'] & (cl['zc'] >= ela_f - band))
    if not heads.size:
        return np.zeros((0, 11))
    tarn = float(_p(params, 'cirque_tarn_m'))
    lobes = float(_p(params, 'cirque_lobes'))
    rng = np.random.default_rng(int(seed) * 7919 + 4243)
    order = heads[np.argsort(-(cl['q'][heads] * rng.uniform(0.7, 1.3, heads.size)), kind='stable')]
    r_lo, r_hi = (float(v) for v in _p(params, 'cirque_radius_m'))
    elong = float(_p(params, 'cirque_elong'))
    spacing = float(_p(params, 'cirque_spacing'))
    depth_max = float(_p(params, 'cirque_depth_m'))
    below = float(_p(params, 'cirque_floor_m'))
    headwall = float(_p(params, 'cirque_headwall_m'))
    cf = min(max(float(_p(params, 'cirque_floor_frac')), 0.0), 0.95)
    cexp = float(_p(params, 'cirque_exp'))
    t85 = max((0.85 - cf) / (1.0 - cf), 1e-3) ** cexp
    room = float(_p(params, 'cirque_headroom_m'))
    hz = np.asarray(h, np.float64).ravel() if h is not None else None
    n1 = level.n
    # the down-glacier direction: from the divide (or the head) to the seed about half a radius down its stream
    down = np.where(st['cont'] | (st['rcv'] >= 0), st['rcv'], -1)
    out = []
    for hd in order:
        R = rng.uniform(r_lo, r_hi)
        Ra = R * elong
        k, steps = hd, 0
        while steps < max(3, int(0.5 * R / cell)) and down[k] >= 0:
            k = down[k]
            steps += 1
        zh = float(cl['zc'][hd])
        zfl = max(ela_f - below, zh - depth_max)
        lip, steps = hd, 0
        while steps < max(3, int(1.5 * Ra / cell)) and down[lip] >= 0:
            lip = down[lip]
            steps += 1
        zfl = max(zfl, float(cl['zf'][lip] + cl['fill'][lip]) - tarn)
        if zfl > zh - 20.0:
            continue
        if up is not None and hz is not None:
            c = int(cl['idx'][hd])
            for _ in range(int(3.0 * Ra / cell)):
                u = int(up[c])
                if u < 0:
                    break
                c = u
            dj, di = divmod(c, n1)
            ox, oy = level.x0 + (di + 0.5) * cell, level.y0 + (dj + 0.5) * cell
            z_crest = float(hz[c])
        else:
            ox, oy, z_crest = float(cl['x'][hd]), float(cl['y'][hd]), None
        vx, vy = cl['x'][k] - ox, cl['y'][k] - oy
        L = math.hypot(vx, vy)
        if L < 1e-6:
            continue
        vx, vy = vx / L, vy / L
        if z_crest is not None and z_crest > zh:
            cx, cy = ox + 0.85 * Ra * vx, oy + 0.85 * Ra * vy
            Hc = max((z_crest + room - zfl) / t85, headwall)
        else:
            cx, cy = ox + 0.35 * R * vx, oy + 0.35 * R * vy
            Hc = headwall + (zh - zfl)
        if any(math.hypot(cx - o[0], cy - o[1]) < spacing * 0.5 * (R + o[6]) for o in out):
            continue
        out.append((cx, cy, zfl, Hc, vx, vy, R, Ra, rng.uniform(0, 2 * math.pi), rng.uniform(0, 2 * math.pi),
                    lobes * rng.uniform(0.6, 1.4)))
        if len(out) >= MAX_CIRQUES:
            break
    return np.asarray(out, np.float64).reshape(-1, 11)


# ============================================================================================ the textures ===

def seed_textures(cl, level, shape=None):
    """The jump flood's inputs on a level's grid: (cand0 (n, n, 4), seedA (n, n, 4), seedB (n, n, 4)) float32.
    seedA: x, y (metres from the level's corner: the kernels' frame), zf, H; seedB: W, stream id, fill, moraine."""
    n0, n1 = shape or (level.n, level.n)
    cand = np.full((n0, n1, 4), -1.0, F32)
    A = np.zeros((n0, n1, 4), F32)
    B = np.zeros((n0, n1, 4), F32)
    B[..., 0] = 1.0
    if cl is None:
        return cand, A, B
    idx = cl['idx']
    jj, ii = np.divmod(idx, n1)
    cand[jj, ii, 0] = idx.astype(F32)
    A[jj, ii] = np.stack([cl['x'] - level.x0, cl['y'] - level.y0, cl['zf'], cl['H']], 1).astype(F32)
    B[jj, ii] = np.stack([np.maximum(cl['W'], 1e-3), cl['streams']['sid'].astype(np.float64), cl['fill'],
                          cl['moraine']], 1).astype(F32)
    return cand, A, B


def cirque_texture(cq, level):
    """(3, max(N, 1), 4) float32: row 0 (cx, cy, z_floor, H_c) in the kernels' frame, row 1 (dir_x, dir_y,
    R_across, R_along), row 2 (the rim's 3- and 5-lobed phases, their amplitude, 0)."""
    n = max(len(cq), 1)
    out = np.zeros((3, n, 4), F32)
    out[1, :, 0] = 1.0
    out[1, :, 2:] = 1.0
    if len(cq):
        out[0, :len(cq)] = np.stack([cq[:, 0] - level.x0, cq[:, 1] - level.y0, cq[:, 2], cq[:, 3]], 1)
        out[1, :len(cq)] = cq[:, 4:8]
        if cq.shape[1] >= 11:
            out[2, :len(cq), :3] = cq[:, 8:11]
    return out


def jfa_steps(reach_cells, n):
    """The jump flood's steps: powers of two from the one covering `reach_cells` down to 1, then 1 again."""
    k = 1
    while k < min(max(reach_cells, 1.0), n):
        k *= 2
    out = []
    while k >= 1:
        out.append(k)
        k //= 2
    return out + [1]


def profile_uniforms(params):
    """The cross-section's uniforms (jump_flood.glsl, u_carve.glsl): uB, uFloorFrac, uFloorRise, uShW, uShH, uShB."""
    return {'uB': float(_p(params, 'u_exponent')), 'uFloorFrac': float(_p(params, 'floor_frac')),
            'uFloorRise': float(_p(params, 'floor_rise')), 'uShW': float(_p(params, 'shoulder_width')),
            'uShH': float(_p(params, 'shoulder_rise')), 'uShB': float(_p(params, 'shoulder_exp')),
            'uOut': float(_p(params, 'upper_wall'))}


def carve_uniforms(params):
    """profile_uniforms() plus u_carve.glsl's cap beyond the lip: uCut, uCutW, uCapJoin."""
    return dict(profile_uniforms(params), uCut=float(_p(params, 'cut')), uCutW=float(_p(params, 'cut_width')),
                uCapJoin=float(_p(params, 'cap_join_m')))


def jump_flood_run(dev, cand0, seedA, seedB, cell, prof_u, steps, metric=0):
    """Every jump-flooding pass on a device; returns the final candidates' texture and the seed textures. prof_u:
    profile_uniforms()."""
    sa, sb = dev.texture(seedA), dev.texture(seedB)
    src, dst = dev.texture(cand0), dev.empty(cand0.shape[:2], 4)
    for k in steps:
        dev.run('jump_flood', {'candT': src, 'seedA': sa, 'seedB': sb}, {'outC': dst},
                dict(prof_u, uStep=int(k), uDx=float(cell), uMetric=int(metric)))
        src, dst = dst, src
    return src, sa, sb


def _metric64(r, A, B, prof_u, metric):
    if metric == 1:
        return r
    rho = r / B[..., 0]
    return A[..., 2] + np.maximum(A[..., 3] * prof(rho, prof_u, np.float64),
                                  fillz(rho, B[..., 2], A[..., 3], prof_u, np.float64))


def brute_force(cand_seeds, seedA, seedB, cell, prof_u, metric=0, chunk=2048, per_stream=False):
    """The exact lower envelope over EVERY seed (the jump flood's oracle, numpy float64): the best metric per cell
    (n, n); with per_stream, the best metric of each stream at each cell, sorted, as (n, n, 4) (inf where fewer
    streams). cand_seeds: the seed cells' flat indices. prof_u: profile_uniforms()."""
    n0, n1 = seedA.shape[:2]
    idx = np.asarray(cand_seeds, np.int64)
    jj, ii = np.divmod(idx, n1)
    A = seedA[jj, ii].astype(np.float64)
    B = seedB[jj, ii].astype(np.float64)
    gy, gx = np.mgrid[0:n0, 0:n1]
    px = ((gx + 0.5) * cell).ravel()
    py = ((gy + 0.5) * cell).ravel()
    if not per_stream:
        best = np.full(px.size, np.inf)
        for s in range(0, idx.size, chunk):
            a, bb = A[s:s + chunk], B[s:s + chunk]
            r = np.hypot(px[:, None] - a[None, :, 0], py[:, None] - a[None, :, 1])
            best = np.minimum(best, _metric64(r, a[None], bb[None], prof_u, metric).min(axis=1))
        return best.reshape(n0, n1)
    sids = np.unique(B[:, 1])
    per = np.full((px.size, sids.size), np.inf)
    for k, sid in enumerate(sids):
        sel = B[:, 1] == sid
        a, bb = A[sel], B[sel]
        for s in range(0, a.shape[0], chunk):
            r = np.hypot(px[:, None] - a[None, s:s + chunk, 0], py[:, None] - a[None, s:s + chunk, 1])
            m = _metric64(r, a[None, s:s + chunk], bb[None, s:s + chunk], prof_u, metric).min(axis=1)
            per[:, k] = np.minimum(per[:, k], m)
    per.sort(axis=1)
    out = np.full((px.size, 4), np.inf)
    out[:, :min(4, sids.size)] = per[:, :4]
    return out.reshape(n0, n1, 4)


def decode_best(cand, seedA, seedB, cell, prof_u, metric=0, slot=None):
    """The metric of each cell's candidates (inf where none): what the jump flood found. (n, n) for the first
    candidate, or (n, n, 4) for all four with slot='all'."""
    n0, n1 = cand.shape[:2]
    jj, ii = np.mgrid[0:n0, 0:n1]
    xp = (ii + 0.5) * cell
    yp = (jj + 0.5) * cell
    out = []
    for c in (range(4) if slot == 'all' else (0,)):
        valid, A, B = _seed_lookup(cand[..., c], seedA, seedB)
        A = A.astype(np.float64)
        B = B.astype(np.float64)
        r = np.hypot(xp - A[..., 0], yp - A[..., 1])
        out.append(np.where(valid, _metric64(r, A, B, prof_u, metric), np.inf))
    return np.stack(out, -1) if slot == 'all' else out[0]


# ================================================================================================ the uplift ===

HORSESHOE = dict(kind='horseshoe', centre=(0.0, 0.0), azimuth_deg=0.0, crest_offset_m=7500.0,
                 crest_length_m=26000.0, crest_width_m=9000.0, side_offset_m=5200.0, side_shift_m=1500.0,
                 side_length_m=17000.0, side_width_m=5200.0, side_height=0.8, join=0.12, texture=0.3)


def horseshoe(spec, x, y, seed, level=None):
    """A crest across a valley's head and two side ridges along it (core/compose ridges: warped, textured, joined
    by smooth maximum), about 0..1. azimuth_deg: the compass direction the valley drains toward."""
    s = dict(HORSESHOE, **spec)
    cx, cy = (float(v) for v in s['centre'])
    az = math.radians(float(s['azimuth_deg']))
    dn = (math.sin(az), math.cos(az))                    # down the valley
    ac = (math.cos(az), -math.sin(az))                   # across it (to the right looking down-valley)
    co = float(s['crest_offset_m'])
    crest = dict(kind='ridge', centre=[cx - co * dn[0], cy - co * dn[1]], azimuth_deg=math.degrees(az) + 90.0,
                 length_m=float(s['crest_length_m']), width_m=float(s['crest_width_m']), spurs=0,
                 texture=float(s['texture']), seed=1)
    f = C.uplift(crest, x, y, seed, level=level)
    so, sh = float(s['side_offset_m']), float(s['side_shift_m'])
    for k, side in enumerate((-1.0, 1.0)):
        ridge = dict(kind='ridge', centre=[cx + side * so * ac[0] - sh * dn[0], cy + side * so * ac[1] - sh * dn[1]],
                     azimuth_deg=math.degrees(az), length_m=float(s['side_length_m']),
                     width_m=float(s['side_width_m']), spurs=0, texture=float(s['texture']), seed=2 + k)
        f = C.smooth_max(f, float(s['side_height']) * C.uplift(ridge, x, y, seed, level=level), float(s['join']))
    return np.clip(f, 0.0, None)


def uplift_shape(spec, level, seed, dev):
    x, y = level.xy()
    lvl = level if (dev is not None and dev.name == 'gpu') else None
    if spec.get('kind') == 'horseshoe':
        return horseshoe(spec, x, y, seed, level=lvl)
    return C.uplift(spec, x, y, seed, level=lvl)


MASK_FIELDS = ('ice', 'trough', 'trough_floor', 'trough_wall', 'carve')


def op_valley_uplift(fields, level, params, seed=0, ctx=None):
    """Stage 'valley_uplift' (module doc): U (m/yr) on the coarsest level's passes, normalised by the shape's peak on
    its first pass; on a fresh level the start surface (the shape scaled to start_m, roughened, as compose's
    start_surface) and zero glacial masks, so a where='1 - trough' on the fluvial stage reads 0 there."""
    ctx = ctx or FL.standalone_context(fields, level)
    dev = ctx.device or FL.device()
    spec = dict(params.get('shape') or HORSESHOE)
    s = int(seed) + int(params.get('seed', 0))
    for k in MASK_FIELDS:
        if k not in fields:
            fields[k] = 0.0
    if ctx.role != 'grow':
        return fields
    u = uplift_shape(spec, level, s, dev)
    sh = ctx.shared.setdefault('valley_uplift', {})
    if 'peak' not in sh:
        sh.update(peak=float(np.max(u)), spec=spec, seed=s, U=float(params.get('U_m_per_yr', 3e-3)))
    fields['U'] = (sh['U'] * u / max(sh['peak'], 1e-12)).astype(F32)
    if ctx.fresh:
        size = float(spec.get('crest_length_m', spec.get('radius_m', spec.get('length_m', 10000.0) * 0.5)))
        n = 0.5 + 1.5 * FL._field({'kind': 'fbm', 'wavelength_m': 0.3 * size, 'octaves': 5}, level, s + 31, dev)
        r = float(params.get('start_roughness', 0.4))
        h0 = float(params.get('start_m', 600.0)) * u / max(sh['peak'], 1e-9) * ((1.0 - r) + r * n)
        fields['h'] = h0.astype(F32)
        fields['bed'] = fields['h']
    return fields


op_valley_uplift.evolves = True


# =================================================================================================== the carve ===

def _wall_sc(level, params, seed, dev, h=None):
    """The fresh walls' threshold (tangent): tan(wall_deg) x exp(wall_noise n + flutes), n unit noise at the wall
    scales the level resolves (strong and weak rock: ribs stand, chutes fail), the flutes (wall_flutes) when the
    surface h is given."""
    t = math.tan(math.radians(float(_p(params, 'wall_deg'))))
    sc = FL._scales(_p(params, 'wall_scales_m'), level.cell, 3.0)
    a = float(_p(params, 'wall_noise'))
    ln = np.zeros((level.n, level.n))
    if a > 0 and sc:
        ln = ln + a * FL._unit_noise(sc, level, seed, dev, 601)
    if h is not None:
        ln = ln + wall_flutes(h, level, params, seed, dev)
    return t * np.exp(ln)


FLUTE_ORIENTATIONS = 8


def wall_flutes(h, level, params, seed, dev=None):
    """ln-tangent offsets of the walls' threshold that run down the fall line, at the flute scales the level
    resolves at 3 cells or more: narrow weak lines, where the rock fails back to about wall_deg - 18 degrees into
    couloirs that shed their debris as talus cones at the walls' foot, and strong rock between them standing as ribs
    and buttresses at about wall_deg + 6 (the vertical fluting of the real walls at 8 m: Lauterbrunnen's Staubbach
    wall, El Capitan). 0 where no scale is resolved.
    The pattern: ridged noise stretched flute_stretch times along a fall direction, in FLUTE_ORIENTATIONS fixed
    world frames (each one dispatch of the world-noise field, the frame a linear map of world metres), blended per
    cell by the surface's own downhill direction (smoothed at the largest scale). A frame that turned with the slope
    cell by cell would shear the stripes far from the origin (a degree's turn 5 km out moves them 90 m)."""
    from . import detail as DT
    from ..core import world_noise as N
    weak, strong = float(_p(params, 'flute_weak')), float(_p(params, 'flute_strong'))
    scales = [float(s) for s in _p(params, 'flute_scales_m') if float(s) >= 3.0 * level.cell]
    if not scales or (weak <= 0 and strong <= 0):
        return np.zeros((level.n, level.n))
    stretch = float(_p(params, 'flute_stretch'))
    X, Y = level.xy()
    dx, dy = DT.flow_direction(np.asarray(h, np.float64), level.cell, max(scales))
    theta = np.mod(np.arctan2(dy, dx), math.pi)                         # stripes are the same either way down
    spec = {'kind': 'sum', 'terms': [{'kind': 'ridged', 'wavelength_m': lam, 'octaves': 1, 'seed': 9100 + i,
                                      'amp': 0.6 ** i} for i, lam in enumerate(scales)]}
    norm = sum(0.6 ** i for i in range(len(scales)))
    gpu = dev is not None and getattr(dev, 'name', '') == 'gpu'
    total = np.zeros((level.n, level.n))
    step = math.pi / FLUTE_ORIENTATIONS
    for k in range(FLUTE_ORIENTATIONS):
        a = k * step
        d = np.abs(np.mod(theta - a + 0.5 * math.pi, math.pi) - 0.5 * math.pi)
        wk = np.clip(1.0 - d / step, 0.0, 1.0)
        if not wk.any():
            continue
        ga, ta = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        u = X * ta[0] + Y * ta[1]
        v = (X * ga[0] + Y * ga[1]) / stretch
        if gpu:
            nk = N.field_gpu(spec, level, int(seed) + 31 * k, disp=(u - X, v - Y)).astype(np.float64)
        else:
            nk = np.asarray(N.field(spec, u, v, int(seed) + 31 * k), np.float64)
        total = total + wk * nk
    # the ridged lines' top fifth are weak (the noise's 70th-85th percentiles are 0.74-0.86): couloirs a quarter of
    # the wall, ribs between
    t = np.clip((total / norm - 0.74) / 0.12, 0.0, 1.0)
    w = t * t * (3.0 - 2.0 * t)
    return strong * (1.0 - w) - weak * w


def _walls(dev, fields, level, Sc, pins, iters, rate):
    """The threshold pass with Sc on the level (the layers counted: losses wear rock, gains are talus)."""
    from .hillslope import _Pass
    run = _Pass(dev, fields, np.asarray(Sc, F32), pins)
    for _ in range(int(iters)):
        run.threshold(level.cell, rate, False, PINNED)
    run.write(fields, 'bed' in fields)


def carve_level(fields, level, params, seed, ctx, dev):
    """The carve on the coarsest level (module doc, steps 1-7). Returns a record dict."""
    t0 = time.perf_counter()
    cell = float(level.cell)
    n = level.n
    base = float(ctx.base_elevation_m or 0.0)
    h = np.asarray(fields['h'], np.float64)
    bed = np.asarray(fields['bed'], np.float64) if 'bed' in fields else h.copy()
    # 1. the ice discharge and the D8 drainage area on the lake-filled, tilted surface
    surf = HY.routing_surface(HY.fill_depressions(h, sea_level=ctx.sea_level)[0], sea_level=ctx.sea_level)
    recv = d8_receivers(surf, cell)
    b = mass_balance(h, base, params)
    if ctx.sea_level is not None:
        b = np.where(h <= ctx.sea_level, -float(_p(params, 'b_abl_m')), b).astype(F32)
    Q, it_q = ice_flux_converge(dev, surf, b, cell, recv, float(_p(params, 'p_ice')), params=params)
    A, it_a = ice_flux_converge(dev, surf, np.ones_like(b), cell, recv, float(_p(params, 'p_ice')),
                                params=dict(params or {}, ice_width_m=0.0))
    t1 = time.perf_counter()
    # 2-3. the centrelines and cirques
    cl = centrelines(h, Q, A, recv, level, ctx.main, params, base, seed)
    cq = cirques(cl, params, base, level, h=h, up=best_donor(recv, A), seed=seed)
    rec = dict(level=str(level), ice_iterations=it_q, area_iterations=it_a, glaciated_frac=float((Q > 0).mean()),
               Q_max=float(Q.max()), Q_ref=cl['Q_ref'] if cl else None, seeds=int(cl['idx'].size) if cl else 0,
               streams=int(cl['streams']['sid'].max() + 1) if cl else 0, cirques=int(len(cq)),
               trunk=dict(W=cl['Wt'], H=cl['Ht'], d=cl['dt']) if cl else None)
    fields['ice_q'] = Q
    gs = np.full(n * n, -1.0, F32)
    if cl is not None:
        gs[cl['idx']] = cl['streams']['sid']
    fields['glacial_streams'] = gs.reshape(n, n)
    if cl is None and not len(cq):
        ctx.log(f'[terrain.glacial] {level}: no glaciated centreline (ELA {_p(params, "ela_m"):g} m, the range '
                f'reaches {h.max() + base:.0f} m): nothing carved')
        rec.update(seconds=round(time.perf_counter() - t0, 2), carved=False)
        return rec
    # 4. the jump flood
    cand0, sA, sB = seed_textures(cl, level)
    pu = profile_uniforms(params)
    wmax = float(np.max(cl['W'])) if cl is not None else 0.0
    # the jump reaches past the shoulders: the target can lie under the surface out to the trimline
    steps = jfa_steps((2.0 + 2.0 * pu['uShW']) * wmax / cell, n)
    cT, saT, sbT = jump_flood_run(dev, cand0, sA, sB, cell, pu, steps)
    t2 = time.perf_counter()
    # 5. the U-carve
    pins = ctx.pins or FL.edge_pins(n, np.asarray(fields['h'], F32), ctx.sea_level)
    st = dev.texture(T.rgba(h, bed, None, None))
    cqT = dev.texture(cirque_texture(cq, level))
    pinT = dev.texture(T.rgba(pins['pin_w'], pins['pin_h'], None, None))
    oS, oM = dev.empty((n, n), 4), dev.empty((n, n), 4)
    dev.run('u_carve', {'candT': cT, 'seedA': saT, 'seedB': sbT, 'st': st, 'cirq': cqT, 'pin': pinT},
            {'outS': oS, 'outM': oM},
            dict(carve_uniforms(params), uDx=cell, uJoin=float(_p(params, 'join_m')), uTrim=float(_p(params, 'trim_m')),
                 uMorAt=moraine_at(params), uMorW=float(_p(params, 'moraine_width')), uNCirq=int(len(cq)),
                 uCirqExp=float(_p(params, 'cirque_exp')), uCirqFloor=float(_p(params, 'cirque_floor_frac')),
                 uCirqOpen=float(_p(params, 'cirque_open')), uBound=PINNED))
    S = dev.read(oS)
    M = dev.read(oM)
    h_new, bed_new = S[..., 0].astype(np.float64), S[..., 1].astype(np.float64)
    carved = M[..., 0].astype(np.float64)
    # the layers: the carve takes the loose cover first, then rock; the fill on the floor is deposit
    loose_old = np.maximum(h - bed, 0.0)
    loose_new = np.maximum(h_new - bed_new, 0.0)
    took = np.maximum(h - h_new, 0.0)
    wear = np.asarray(fields.get('wear', np.zeros((n, n))), np.float64) + np.maximum(took - loose_old, 0.0)
    dep_old = np.asarray(fields.get('deposit', np.zeros((n, n))), np.float64)
    tal_old = np.asarray(fields.get('talus', np.zeros((n, n))), np.float64)
    hit = carved > 1e-3
    deposit = np.where(hit, loose_new, dep_old)
    talus = np.where(hit, 0.0, tal_old)
    fields['h'] = h_new
    fields['bed'] = bed_new
    fields['wear'] = wear
    fields['deposit'] = deposit
    fields['talus'] = talus
    fields['ice'] = S[..., 3]
    fields['trough_floor'] = M[..., 1]
    fields['trough_wall'] = M[..., 2]
    fields['trough'] = M[..., 3]
    fields['carve'] = M[..., 0]
    # 6. the fresh walls: steep in the trough and the cirques, the range's own threshold outside
    wall = np.clip(np.asarray(M[..., 2], np.float64) * 1.5, 0.0, 1.0)
    sc_range = np.asarray(fields['Sc'], np.float64) if 'Sc' in fields else \
        np.full((n, n), math.tan(math.radians(35.0)))
    Sc = sc_range * (1.0 - wall) + _wall_sc(level, params, seed, dev) * wall
    _walls(dev, fields, level, Sc, pins, _p(params, 'wall_iters'), float(_p(params, 'wall_rate')))
    fields['Sc'] = Sc.astype(F32)
    ctx.evolved = True
    t3 = time.perf_counter()
    rec.update(carved=True, jfa_steps=steps, carve_max_m=float(carved.max()), carve_mean_in_trough_m=float(
        carved[M[..., 3] > 0.5].mean()) if (M[..., 3] > 0.5).any() else 0.0, trough_frac=float(M[..., 3].mean()),
        seconds=dict(ice=round(t1 - t0, 2), jfa=round(t2 - t1, 2), carve_walls=round(t3 - t2, 2)))
    return rec


def refine_level(fields, level, params, seed, ctx, dev):
    """A finer level (module doc): the walls it inherits keep their steep threshold, and fail at it at this level's
    scale where the rock is weak. The fluvial refinement (where='1 - trough') left the level's U, K, Sc and G at 0 in
    the trough: K and G are restored to the level's own outside it, Sc to the walls' threshold."""
    n = level.n
    if 'trough' not in fields or float(np.max(fields['trough'])) <= 0.0:
        return dict(level=str(level), refined=False)
    tr = np.clip(np.asarray(fields['trough'], np.float64), 0.0, 1.0)
    wall = np.clip(np.asarray(fields.get('trough_wall', tr), np.float64) * 1.5, 0.0, 1.0)
    out = tr < 0.02
    for k in ('K', 'G'):
        if k in fields and out.any():
            a = np.asarray(fields[k], np.float64)
            fields[k] = np.where(tr > 0.02, float(np.median(a[out])), a).astype(F32)
    if 'Sc' in fields and out.any():
        sc_out = float(np.median(np.asarray(fields['Sc'], np.float64)[out]))
        sc_range = np.where(tr > 0.02, sc_out, np.asarray(fields['Sc'], np.float64))
    else:
        sc_range = np.full((n, n), math.tan(math.radians(35.0)))
    h_in = np.asarray(fields['h'], np.float64)
    rf = float(_p(params, 'rock_flutes'))
    range_flutes = np.zeros((n, n))
    if rf > 0:
        # the range's own rock faces carry couloirs and ribs too (the real tile's spectrum holds ten times this
        # range's power at 30 m against 2 km): the flutes, scaled, on ground steeper than rock_flute_deg
        s = Gd.slope_deg(h_in, level.cell)
        t = np.clip((s - float(_p(params, 'rock_flute_deg'))) / 8.0, 0.0, 1.0)
        range_flutes = rf * t * t * (3.0 - 2.0 * t) * wall_flutes(h_in, level, params, seed + 7, dev)
    if ctx.depth < 0:
        # a hero level refines without moving the landform: no threshold stands under the slope the level inherits
        # (its parent's walls, cliffs, truncated spurs and headwalls stand), so only the flutes' weak lines and new
        # detail fail. With the range's own threshold and the walls' noise alone they collapsed by hundreds of metres
        # (850 m at 1 m cells)
        gx, gy = Gd.gradient(h_in, level.cell)
        base = np.maximum(sc_range * (1.0 - wall) + _wall_sc(level, params, seed, dev) * wall,
                          1.05 * np.hypot(gx, gy))
        Sc = base * np.exp(wall * wall_flutes(h_in, level, params, seed, dev) + (1.0 - wall) * range_flutes)
    else:
        Sc = sc_range * np.exp(range_flutes) * (1.0 - wall) + _wall_sc(level, params, seed, dev, h=h_in) * wall
    pins = ctx.pins or FL.edge_pins(n, np.asarray(fields['h'], F32), ctx.sea_level)
    iters = int(_p(params, 'refine_wall_iters'))
    if iters > 0:
        _walls(dev, fields, level, Sc, pins, iters, float(_p(params, 'wall_rate')))
        ctx.evolved = True
    fields['Sc'] = Sc.astype(F32)
    return dict(level=str(level), refined=True, wall_frac=float((wall > 0.5).mean()))


def op_glacial(fields, level, params, seed=0, ctx=None):
    """Stage 'glacial' (module doc): the carve on the coarsest level once it is fully grown (after its last
    coarse-to-fine pass), the walls' refinement below it."""
    ctx = ctx or FL.standalone_context(fields, level)
    if ctx.prepass is not None:
        return fields
    dev = ctx.device or FL.device()
    t0 = time.perf_counter()
    s = int(seed) + int(_p(params, 'seed'))
    if ctx.role == 'grow' or 'ice_q' not in fields and float(np.max(fields.get('trough', 0.0))) <= 0.0:
        rec = carve_level(fields, level, params, s, ctx, dev)
        rec['mode'] = 'carve'
    else:
        rec = refine_level(fields, level, params, s, ctx, dev)
        rec['mode'] = 'refine'
    rec['seconds_total'] = round(time.perf_counter() - t0, 2)
    ctx.shared.setdefault('glacial_log', []).append(rec)
    if rec['mode'] == 'carve' and rec.get('carved'):
        ctx.log(f"[terrain.glacial] carve {level.n}^2 @ {level.cell:.3g} m: Q_ref {rec['Q_ref']:.3g} m3/yr, "
                f"{rec['seeds']} seeds in {rec['streams']} streams, {rec['cirques']} cirques, trough "
                f"{rec['trough_frac'] * 100:.1f} % of the level, carve max {rec['carve_max_m']:.0f} m, "
                f"{rec['seconds_total']} s")
    elif rec['mode'] == 'refine':
        ctx.log(f"[terrain.glacial] walls {level.n}^2 @ {level.cell:.3g} m: {rec.get('wall_frac', 0) * 100:.1f} % "
                f"wall, {rec['seconds_total']} s")
    return fields


op_glacial.evolves = True               # called on every pass of the coarsest level; it acts on the last one only

OPS = {'glacial': op_glacial, 'valley_uplift': op_valley_uplift}
