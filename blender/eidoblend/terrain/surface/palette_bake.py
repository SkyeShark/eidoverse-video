"""The palette's maps (SURFACING_DESIGN.md 2.3, the palette bake), on the bake's levels, coarsest first:

    from eidoblend.terrain.surface import palette_bake as PB
    colour = PB.bake(sd, palette)             # per level {'down_colour' (n, n, 3), 'down_share', 'far_colour' (n, n, 3),
                                              # 'far_roughness'}, linear; cached beside the bake by the palette's hash
    PB.rock_colour(pal, zs)                   # the palette's bare-rock colour (linear) at stratigraphic heights

Provenance colour P (down_colour, down_share). Sediment production P = fresh x bare (the mask language's `bare`)
plus a small background, in m^2 of eroding ground per cell; the source colour c is the palette's bare-rock colour at
the cell's stratigraphic height (the strata column's formation there, or the rock layer's colour). Both are routed
down the bake's filled surface with the multiple-flow shares (route_colour.glsl, route_area's scheme with four
channels): Q = P + sum f Q_up, R = P c + sum f R_up, to convergence. down_colour = R / Q, the rock colours upstream
weighted by where the ground erodes; down_share = Q / (Q + Q0), how much of the ground is carried sediment. A child
level's margin holds its parent's Q and R (the specific values, as the drainage area's), so a catchment the window
truncates still carries its upstream colour in.

Far colour C (far_colour, far_roughness): the palette's ground per texel, every layer at its scan's mean
(surface/far_colour.py, when it is there); without it the bake writes P only. C is made first; P is routed after it
while the palette bake stays within its budget (BUDGET_S), else deferred (bake's p_mode). Each level's C and P are
then pinned to its parent's across the border band (pin_levels), as the bake pins its maps.

The device is the bake's ('gpu' in Blender, the numpy twins in plain Python). No bpy.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time

import numpy as np

from . import bake as B
from . import twins as TW

F = np.float32
BACKGROUND = 1.0e-3            # production on every cell (m^2 per m^2): a catchment with no eroding rock still
                               # carries its bedrock's colour
Q0_M2 = 1000.0                 # the eroding area upstream at which half the ground is carried sediment
BUDGET_S = 30.0                # the palette bake's budget cold (SURFACING_DESIGN.md 7): past it P is deferred
PALETTE_BAKE_VERSION = 1


def palette_hash(pal):
    """A hash of the palette dict (its layers, options, strata and constants) and of the palette bake's code."""
    blob = json.dumps(pal, sort_keys=True, default=str, separators=(',', ':'))
    code = B.code_hash(B.PALETTE_CODE)
    return hashlib.sha1((blob + f'|v{PALETTE_BAKE_VERSION}|{code}').encode('utf-8')).hexdigest()[:16]


def _mean_colour(col):
    if isinstance(col, list):
        w = np.array([c[1] for c in col], np.float64)
        return (np.array([c[0] for c in col], np.float64) * w[:, None]).sum(0) / max(w.sum(), 1e-9)
    return np.asarray(col, np.float64)


def rock_layer(pal):
    """The palette's bare-rock layer: the strata layer, else one named for rock, cliff or wall, else the first box
    (steep-face) layer, else the first layer."""
    layers = pal['layers']
    for L in layers:
        if L.get('strata'):
            return L
    for key in ('rock', 'cliff', 'wall', 'face'):
        for L in layers:
            if key in str(L.get('name', '')).lower():
                return L
    for L in layers:
        if L.get('projection') == 'box':
            return L
    return layers[0]


def rock_colour(pal, zs, x=None, y=None):
    """Linear RGB (..., 3) of the palette's bare rock at stratigraphic heights zs (metres, the masks' strata frame):
    the strata column's formation colour there (its z_offset_m and fault throws applied; a repeating column wraps,
    past the ends the end formations continue), or the rock layer's colour when the palette draws no strata."""
    from ..build import palettes as P
    zs = np.asarray(zs, np.float64)
    st = pal.get('strata') or {}
    if st.get('column') and any(L.get('strata') for L in pal['layers']):
        layers = P.column_layers(st['column'], looks=bool(st.get('looks', False)))
        z = zs + float(st.get('z_offset_m', 0.0))
        if x is not None and st.get('faults'):
            for f in st['faults']:
                s = math.radians(float(f.get('strike_deg', 0.0)))
                nx, ny = math.cos(s), -math.sin(s)
                want = {'west': (-1, 0), 'east': (1, 0), 'north': (0, 1), 'south': (0, -1)}[f.get('down', 'west')]
                if nx * want[0] + ny * want[1] < 0:
                    nx, ny = -nx, -ny
                d = (np.asarray(x) - float(f.get('x', 0.0))) * nx + (np.asarray(y) - float(f.get('y', 0.0))) * ny
                w = max(float(f.get('width_m', 50.0)), 1e-3)
                t = np.clip((d + 0.5 * w) / w, 0.0, 1.0)
                z = z + t * t * (3 - 2 * t) * float(f.get('throw_m', 0.0))
        z_lo, z_hi = layers[0][1], layers[-1][2]
        if P.column_repeats(st['column']) and z_hi > z_lo:
            z = z_lo + np.mod(z - z_lo, z_hi - z_lo)
        tops = np.array([L[2] for L in layers])
        idx = np.clip(np.searchsorted(tops, z, side='right'), 0, len(layers) - 1)
        cols = np.array([_mean_colour(L[3]) for L in layers])
        return cols[idx].astype(F)
    c = np.asarray(P.hex_linear(rock_layer(pal)['colour']), F)
    return np.broadcast_to(c, zs.shape + (3,)).astype(F)


def _level_masks(sd, i):
    m = sd.maps(i)
    return m


def _production(sd, pal, i):
    """(P (m^2 of eroding ground per cell), c (linear rock colour)) on level i's cells."""
    from ..build import palettes as P
    lv = sd.levels[i]
    m = _level_masks(sd, i)
    consts = dict(pal.get('constants') or {})
    bare = np.clip(np.asarray(P.evaluate('bare', m, constants=consts, flat=True), np.float64), 0.0, 1.0)
    fresh = np.asarray(m.get('fresh', np.zeros(bare.shape)), np.float64)
    prod = (fresh * bare + BACKGROUND) * float(lv.cell) ** 2
    zs = np.asarray(m['strata'], np.float64) if 'strata' in m else np.asarray(sd.terrain.fields(i)['h'], np.float64)
    X, Y = lv.xy()
    c = rock_colour(pal, zs, X, Y)
    return prod.astype(F), c


def provenance(sd, pal, log=print, deadline=None):
    """[(down_colour (n, n, 3), down_share (n, n))] per level (module doc). With a deadline (time.perf_counter()
    seconds), None as soon as the next level, at the mean time of the levels routed so far, would pass it."""
    from ..solvers import fluvial as FL
    from ..core import twins as T
    from ..core import grid as Gd
    be = sd.options.get('backend', 'auto')
    if be == 'auto':
        try:
            import gpu  # noqa: F401
            be = 'gpu'
        except ImportError:
            be = 'twin'
    dev = FL.device('twin' if be == 'twin' else 'gpu')
    m = B.MARGIN
    out, keep = [], {}
    spent = []
    for i, lv in enumerate(sd.levels):
        t0 = time.perf_counter()
        if deadline is not None and t0 + (sum(spent) / len(spent) if spent else 0.0) > deadline:
            return None
        n, cell = lv.n, float(lv.cell)
        N_ = n + 2 * m
        b = sd._baked_level(i)
        W = b.get('_fill')
        if W is None:
            raise KeyError(f'level {i}: the bake has no routing surface (_fill): bake again with this code')
        W = np.asarray(W, F)
        prod, c = _production(sd, pal, i)
        src = np.zeros((N_, N_, 4), F)
        pin = np.zeros((N_, N_, 4), F)
        q0 = np.zeros((N_, N_, 4), F)
        par = keep.get(lv.parent) if lv.parent is not None else None
        if par is None:
            from .. import masks as M
            P_ = M.pad_level(prod.astype(np.float64), m, cell, fill='edge').astype(F)
            src[..., 0] = P_
            for k in range(3):
                src[..., 1 + k] = P_ * M.pad_level(c[..., k].astype(np.float64), m, cell, fill='edge').astype(F)
        else:
            src[m:m + n, m:m + n, 0] = prod
            src[m:m + n, m:m + n, 1:] = prod[..., None] * c
            i0, j0, mc = lv.in_parent(sd.levels)
            win = (i0 - m // 2 + m, j0 - m // 2 + m, mc + m)
            for k in range(4):
                q0[..., k] = Gd.crop_upsample2(par[..., k], *win, 'bilinear') * F(0.5)
            pin[..., 1] = 1.0
            pin[m:m + n, m:m + n, 1] = 0.0
        st = dev.texture(W)
        ws = dev.empty((N_, N_), 1)
        dev.run('flow_weights', {'st': st}, {'outW': ws}, {'uDx': cell, 'uP': float(sd.options.get('flow_p', 1.0)),
                                                         'uBound': T.BOUND_OPEN})
        tS, tP = dev.texture(src), dev.texture(pin)
        a, bb = dev.texture(q0), dev.empty((N_, N_), 4)
        u = {'uDx': cell, 'uP': float(sd.options.get('flow_p', 1.0)), 'uBound': T.BOUND_OPEN}
        prev = q0[..., 0].astype(np.float64)
        it, check = 0, 128
        while it < 8 * N_:
            for _ in range(check):
                dev.run(TW.inline('route_colour'), {'st': st, 'wsumT': ws, 'qT': a, 'srcT': tS, 'pinT': tP},
                        {'outQ': bb}, u)
                a, bb = bb, a
            it += check
            cur = dev.read(a)
            q = cur[..., 0].astype(np.float64)
            change = float(np.max(np.abs(q - prev) / np.maximum(q, 1e-12)))
            prev = q
            if change < 1e-4:
                break
        keep[i] = cur
        w = cur[m:m + n, m:m + n]
        Q = np.maximum(w[..., 0], F(1e-12))
        down = np.clip(w[..., 1:] / Q[..., None], 0.0, 1.0).astype(F)
        share = (Q / (Q + F(Q0_M2))).astype(F)
        out.append((down, share))
        spent.append(time.perf_counter() - t0)
        if log:
            log(f'[surface] palette bake: provenance on level {i} in {spent[-1]:.2f} s ({it} passes)')
        gp = sd.levels[lv.parent].parent if lv.parent is not None else None
        if gp is not None:
            keep.pop(gp, None)
    return out


def _prune(folder, key, keep=2):
    """Delete a bake's palette bakes beyond the `keep` most recently written palettes."""
    import glob
    tags = {}
    for p in glob.glob(os.path.join(folder, f'surface_{key}_pal*_L0.npz')):
        tags[os.path.basename(p)[len(f'surface_{key}_'):-len('_L0.npz')]] = os.path.getmtime(p)
    for tag in sorted(tags, key=tags.get, reverse=True)[keep:]:
        for p in glob.glob(os.path.join(folder, f'surface_{key}_{tag}_L*.npz')):
            try:
                os.remove(p)
            except OSError:
                pass


def pin_levels(sd, out, names=('far_colour', 'far_roughness', 'down_colour', 'down_share')):
    """Each level's palette maps blended to its parent's over the border band (masks.pin_band, B.BAND cells),
    coarsest first, as the bake pins its own maps: a child's border is then its parent's. In place."""
    from .. import masks as M
    for i, lv in enumerate(sd.levels):
        if lv.parent is None:
            continue
        plv = sd.levels[lv.parent]
        child = M.Masks(lv.cell, lv.x0, lv.y0, (lv.n, lv.n))
        parent = M.Masks(plv.cell, plv.x0, plv.y0, (plv.n, plv.n))
        for nm in names:
            a, b = out[i].get(nm), out[lv.parent].get(nm)
            if a is None or b is None:
                continue
            if a.ndim == 3:
                for c in range(a.shape[2]):
                    child[f'{nm}.{c}'] = np.ascontiguousarray(a[..., c], F)
                    parent[f'{nm}.{c}'] = np.ascontiguousarray(b[..., c], F)
            else:
                out[i][nm] = child[nm] = np.ascontiguousarray(a, F)
                parent[nm] = np.ascontiguousarray(b, F)
        M.pin_band(child, parent, B.BAND, skip=())
        for nm in names:
            a = out[i].get(nm)
            if a is not None and a.ndim == 3:
                out[i][nm] = np.stack([child[f'{nm}.{c}'] for c in range(a.shape[2])], -1).astype(F)


def bake(sd, pal, cache=None, log=print, p_mode='budget', budget_s=BUDGET_S):
    """The palette bake of a SurfaceData: per level {'far_colour', 'far_roughness'[, 'down_colour', 'down_share']},
    cached as <cache>/surface_<key>_pal<hash>_L<i>.npz (float16). C first, then P by p_mode: True always, False
    never, 'budget' while the palette bake stays within budget_s (each level's routing projected from the levels
    done). Past the budget P is deferred: the levels it routed are dropped, and the material's sediment layers mix
    toward the debris' own column colour (SURFACING_DESIGN.md 2.3). A cached bake without P gains it with
    p_mode=True. sd.info['palette_bake'] records what was made, cached or deferred and the seconds."""
    tag = 'pal' + palette_hash(pal)
    sd._colour_tag = tag
    n = len(sd.levels)
    files = [os.path.join(cache, f'surface_{sd.key}_{tag}_L{i}.npz') for i in range(n)] if cache else None
    t0 = time.perf_counter()
    rec = dict(tag=tag)
    out = None
    if files and all(os.path.exists(p) for p in files):
        out = []
        for p in files:
            with np.load(p, allow_pickle=False) as z:
                out.append({k: np.asarray(z[k], F) for k in z.files})
        rec.update(C='cached' if 'far_colour' in out[0] else 'absent',
                   P='cached' if 'down_colour' in out[0] else 'deferred')
        if p_mode is not True or 'down_colour' in out[0]:
            rec['seconds'] = round(time.perf_counter() - t0, 3)
            sd.info['palette_bake'] = rec
            return out
    if out is None:
        out = [{} for _ in range(n)]
        try:
            from . import far_colour as FC
        except ImportError:
            FC = None
        if FC is not None:
            t1 = time.perf_counter()
            for i, (rgb, rough) in enumerate(FC.bake(sd, pal, log=log)):
                out[i]['far_colour'] = rgb
                out[i]['far_roughness'] = rough
            rec.update(C='made', C_seconds=round(time.perf_counter() - t1, 2))
        else:
            rec['C'] = 'absent'
    if p_mode:
        t1 = time.perf_counter()
        prov = provenance(sd, pal, log=log, deadline=None if p_mode is True else t0 + float(budget_s))
        if prov is None:
            rec['P'] = 'deferred'
            if log:
                log(f'[surface] palette bake {tag}: provenance deferred (past the {budget_s:g} s budget)')
        else:
            for d, (dc, ds) in zip(out, prov):
                d['down_colour'], d['down_share'] = dc, ds
            rec.update(P='made', P_seconds=round(time.perf_counter() - t1, 2))
    else:
        rec['P'] = 'skipped'
    pin_levels(sd, out)
    if files:
        for p, d in zip(files, out):
            tmp = p + '.tmp.npz'
            np.savez(tmp, **{k: np.asarray(v, np.float16) for k, v in d.items()})
            os.replace(tmp, p)
        _prune(cache, sd.key, keep=2)
    rec['seconds'] = round(time.perf_counter() - t0, 3)
    sd.info['palette_bake'] = rec
    if log:
        log(f'[surface] palette bake {tag}: {rec["seconds"]:.2f} s (C {rec.get("C")}, P {rec.get("P")})')
    return out


__all__ = ['bake', 'provenance', 'pin_levels', 'rock_colour', 'rock_layer', 'palette_hash', 'BACKGROUND', 'Q0_M2',
           'BUDGET_S']
