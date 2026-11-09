"""The level runner (design sections 2.2-2.6, 4.1-4.3): every level of a plan, coarsest first.

    from eidoblend.terrain import run
    fields = run.run_levels(plan, recipe, values, stages, seed=7, flatten=[...], sea_level=None,
                            base_elevation_m=800.0, log=print)          # [Fields], one per level (api.py calls it)

Per level:
  1. its start: the coarsest level from nothing (h = bed = 0); every other level its parent's fields upsampled x2
     (core Fields.inherit: h and bed Catmull-Rom, the rest bilinear; U, K, Sc, G, K_factor, Sc_factor and the pins
     are per-level inputs and never inherited);
  2. pins: the coarsest level's outer ring is base level (the fluvial stage holds it); a child's border band (16
     cells) ramps from its parent's surface at the edge to free at 16 cells in, and the parent's drainage area and
     sediment flux that cross the window edge enter on the child's edge cells (hydro.inflow);
  3. the stages that select the level, in recipe order. The coarsest level first grows coarse-to-fine through its
     pre-passes (256, 512 ... cells, each upsampled into the next) when an evolving stage (fluvial, creep, talus,
     threshold, uplift - any op whose function has evolves = True) selects it; a constructional op (a cone, a DEM,
     a crater) runs once, on the first pass. Ops that take ctx= get a StageContext (solvers/fluvial.py); the
     wave-1 convention op(fields, level, params, seed) is called as is, and on a child level its height is then
     pulled to the parent's in the border band. A stage's `where` limits it: the fields it changed are blended
     with what they were by the mask (masks.py names, or field names);
  4. the end stages: on a level a process evolved, closed depressions become lakes (or sediment, with the recipe's
     defaults['lakes'] = 'sediment'; False skips them), keeping the parent's lakes; a depression reaching into a
     child's border band, or into a flatten area (a rigid block during erosion, which can lag its surroundings into
     a hollow; api.py levels it afterwards), fills with sediment instead; then on every level the drainage area A is
     routed to convergence across the lakes (the masks read it).

The cache: each level's fields are written under eidoverse/assets/cache/terrain/lv_<key>/, the key covering
everything that decides levels 0..i (stages, knob values, seed, the plan up to i, flatten, sea level, the code that
makes fields). Moving only the focus re-runs only the hero levels; api.py caches the finished terrain on top.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import time

import numpy as np

from .core import grid as Gd
from .core.fields import Fields
from .solvers import fluvial as FL
from .solvers import hydro as HY

F32 = np.float32
LEVEL_INPUTS = ('U', 'K', 'Sc', 'G', 'K_factor', 'Sc_factor', 'pin_w', 'pin_h')
SKIP = {k: 'skip' for k in LEVEL_INPUTS}
EVOLVING = {'uplift', 'fluvial', 'creep', 'talus', 'threshold'}
RUN_VERSION = 1


# ---------------------------------------------------------------------------------------------------- ops ---

def _registry():
    from . import recipes as R
    return R


def get_op(name):
    return _registry().get_op(name)


def _evolves(op_name):
    if op_name in EVOLVING:
        return True
    try:
        return bool(getattr(get_op(op_name), 'evolves', False))
    except KeyError:
        return False


def skipped_stages(info):
    """The stage labels a run skipped because their op is not registered (from run_levels' info record)."""
    out = []
    for rec in (info or {}).get('levels', []):
        for s in rec.get('skipped', []):
            if s not in out:
                out.append(s)
    return out


def _takes_ctx(fn):
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    return 'ctx' in sig.parameters or any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())


# --------------------------------------------------------------------------------------------------- pins ---

SEAM_HOLD = 2                  # cells at a child's edge held exactly on its parent's surface


def child_pins(lv, h_start, parent_level, parent_fields, parent_surface, sea_level=None, p=1.0):
    """A child level's pins: the border band holding the inherited surface, weight 1 on the outer SEAM_HOLD cells
    (so the slopes either side of the seam are the parent's: a river crossing the edge otherwise cut its sharper
    channel up to the edge, a 6-8 degree jump in single cells), easing to 0 at band cells in (C1); and the parent's
    inflow on the edge cells."""
    d = Gd.edge_distance(lv.n).astype(np.float64)
    t = np.clip((d - SEAM_HOLD) / float(max(lv.band - SEAM_HOLD, 1)), 0.0, 1.0)
    w = (1.0 - t * t * (3.0 - 2.0 * t)).astype(F32)
    ph = np.asarray(h_start, F32).copy()
    if sea_level is not None:
        sea = ph <= sea_level
        w = np.where(sea, F32(1), w)
        ph = np.where(sea, np.minimum(ph, F32(sea_level)), ph)
    A_in, qs_in = HY.inflow(parent_level, parent_fields, lv, p, parent_surface)
    return dict(pin_w=w, pin_h=ph, A_in=A_in, qs_in=qs_in)


def _band_pull(fields, pins):
    """A legacy op's height pulled to the parent's in the border band (what the GPU stages do every step)."""
    if pins is None or 'h' not in fields:
        return
    w = np.clip(pins['pin_w'], 0.0, 1.0)
    fields['h'] = (np.asarray(fields['h'], np.float64) * (1.0 - w) + pins['pin_h'] * w).astype(F32)
    if 'bed' in fields:
        fields['bed'] = np.minimum(fields['bed'], fields['h'])


# ------------------------------------------------------------------------------------------------- where ---

def where_mask(expr, fields, level, mask_params=None):
    """A stage's `where` expression evaluated on a level: field names read the fields, anything else is a mask
    (masks.py, computed from the current fields). 0..1, float64."""
    names = expr.names()
    need = [n for n in names if n not in fields]
    got = {}
    if need:
        from . import masks as M
        got = M.compute(fields, level.cell, level.x0, level.y0, names=need, params=mask_params)
        missing = [n for n in need if n not in got]
        if missing:
            raise KeyError(f'where {expr}: no field or mask {missing} on {level}')
    env = {n: np.asarray(fields[n] if n in fields else got[n], np.float64) for n in names}
    return np.clip(np.asarray(expr.eval(env), np.float64), 0.0, 1.0)


def _blend(before, fields, m):
    for k in list(fields.keys()):
        new = np.asarray(fields[k], np.float64)
        old = np.asarray(before[k], np.float64) if k in before else np.zeros_like(new)
        if new.shape == m.shape:
            fields[k] = (old + m * (new - old)).astype(F32)


# ------------------------------------------------------------------------------------------------- cache ---

def _level_key(plan, i, stages, values, seed, flatten, sea_level, base_elevation_m, lakes_mode, dev):
    from .core import cache as CA
    payload = dict(v=RUN_VERSION, plan=[lv.to_dict() for lv in plan[:i + 1]],
                   stages=[s.to_dict() for s in stages], values=values, seed=int(seed), flatten=flatten,
                   sea=sea_level, base=base_elevation_m, lakes=lakes_mode, device=dev.name, code=CA.code_hash())
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return 'lv_' + hashlib.sha1(blob.encode('utf-8')).hexdigest()


def _jsonable(v):
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v


# --------------------------------------------------------------------------------------------- the runner ---

def run_levels(plan, recipe, values, stages, seed=0, flatten=None, sea_level=None, base_elevation_m=0.0, log=print,
               device=None, cache=True, info=None):
    """Every level's Fields, coarsest first (module doc). device: 'gpu' (default) or 'twin' (tests). info: a dict
    to receive the run's record (per level: seconds, stages, fluvial passes, lakes, route iterations)."""
    dev = FL.device(device)
    flatten = list(flatten or [])
    defaults = dict(getattr(recipe, 'defaults', {}) or {})
    lakes_mode = defaults.get('lakes', 'lake')
    mask_params = None
    shared = {}
    out = []
    record = info if info is not None else {}
    record['levels'] = []
    surfaces = {}
    t_all = time.perf_counter()
    sel = [st.select(plan, warn=log) for st in stages]
    for i, lv in enumerate(plan):
        t0 = time.perf_counter()
        mine = [st for st, s in zip(stages, sel) if i in s]
        key = None
        if cache:
            from .core import cache as CA
            key = _level_key(plan, i, stages, values, seed, flatten, sea_level, base_elevation_m, lakes_mode, dev)
            C = CA.Cache(key)
            if C.complete():
                f = C.load_level(0, lv)
                meta = C.read_meta() or {}
                shared = dict(meta.get('shared') or {})
                out.append(f)
                surfaces[i] = _surface(f, sea_level)
                rec = dict(meta.get('record') or {}, cache='hit', seconds=round(time.perf_counter() - t0, 2))
                record['levels'].append(rec)
                log(f'[terrain.run] level {i} {lv}: cache hit ({rec["seconds"]} s)')
                continue
        evolving = any(_evolves(st.op) for st in mine)
        subs = [lv.with_cells(m) for m in lv.prepass] + [lv] if (i == 0 and lv.prepass and evolving) else [lv]
        parent = out[lv.parent] if lv.parent is not None else None
        if parent is None:
            fields = Fields(subs[0], {'h': 0.0, 'bed': 0.0})
            pins = None
        else:
            fields = parent.inherit(lv, rules=SKIP)
            pins = child_pins(lv, fields['h'], plan[lv.parent], parent, surfaces.get(lv.parent), sea_level)
        evolved = False
        stage_rec = []
        skipped = []
        for k, sub in enumerate(subs):
            if k > 0:
                fields = fields.inherit(sub, rules=SKIP)
            ctx = FL.StageContext(plan=plan, index=i, level=sub, prepass=k if len(subs) > 1 and k < len(subs) - 1
                                  else None, fresh=(parent is None and k == 0), role='grow' if parent is None
                                  else 'refine', pins=pins, shared=shared, seed=seed, sea_level=sea_level,
                                  base_elevation_m=base_elevation_m, flatten=flatten, device=dev, log=log,
                                  values=values)
            for st in mine:
                if k > 0 and not _evolves(st.op):
                    continue
                if st.params.get('enabled', True) is False:
                    continue
                try:
                    fn = get_op(st.op)
                except KeyError:
                    if k == 0:
                        skipped.append(st.label)
                        log(f"[terrain.run] level {i}: stage {st.label!r} skipped: op {st.op!r} is not registered "
                            f"(its package has not landed)")
                    continue
                ts = time.perf_counter()
                before = fields.copy() if st.where_expr is not None else None
                if _takes_ctx(fn):
                    fn(fields, sub, st.params, seed, ctx=ctx)
                else:
                    fn(fields, sub, st.params, seed)
                    if parent is not None:
                        _band_pull(fields, pins)
                if before is not None:
                    _blend(before, fields, where_mask(st.where_expr, fields, sub, mask_params))
                stage_rec.append(dict(stage=st.label, cells=sub.n, seconds=round(time.perf_counter() - ts, 3)))
            evolved = evolved or ctx.evolved
        if 'h' not in fields:
            raise RuntimeError(f'level {i} ({lv}) has no height after its stages')
        if parent is None and 'relief' not in shared:
            shared['relief'] = FL.window_relief(fields['h'], lv, _main_of(plan))
        # the end stages: lakes on evolved levels, then the drainage area to convergence on every level
        te = time.perf_counter()
        nlakes = 0
        if evolved and lakes_mode:
            thr = HY.depression_threshold(shared.get('relief') or float(np.ptp(fields['h'])))
            no_lake = None
            if flatten:
                from .core import compose as CO
                X, Y = lv.xy()
                no_lake = CO.flatten_mask([{'at': f['at'], 'radius': f.get('radius', 10.0),
                                            'falloff': f.get('falloff', 0.0)} for f in flatten
                                           if f.get('radius') is not None], X, Y) > 0.5
            filled, nlakes = HY.lakes(fields, lv, thr, 'sediment' if lakes_mode == 'sediment' else 'lake',
                                      parent=(plan[lv.parent], parent) if parent is not None else None,
                                      sea_level=sea_level, band=lv.band if parent is not None else 0,
                                      no_lake=no_lake)
            top = np.asarray(fields['h'], np.float64) + np.asarray(fields['water'], np.float64)
            surf = HY.routing_surface(np.maximum(filled, top), sea_level=sea_level)
        else:
            surf = _surface(fields, sea_level)
        A, iters = HY.route_to_convergence(dev, surf, lv.cell, A0=fields.get('A'),
                                           A_in=pins['A_in'] if pins is not None else None)
        fields['A'] = A
        surfaces[i] = surf
        if 'qs' not in fields:
            fields['qs'] = np.zeros((lv.n, lv.n), F32)
        rec = dict(level=str(lv), role=lv.role, passes=len(subs), stages=stage_rec, skipped=skipped, lakes=nlakes,
                   route_iterations=iters, end_seconds=round(time.perf_counter() - te, 2),
                   seconds=round(time.perf_counter() - t0, 2), cache='miss' if cache else 'off')
        record['levels'].append(rec)
        log(f'[terrain.run] level {i} {lv}: {len(mine)} stages' + (f' over {len(subs)} passes' if len(subs) > 1
                                                                   else '')
            + f', lakes {nlakes}, route {iters} it, {rec["seconds"]} s')
        out.append(fields)
        if cache and key is not None:
            C.save_level(0, fields)
            C.write_meta(dict(levels=1, level=lv.to_dict(), shared=_jsonable(_shareable(shared)),
                              record=_jsonable(rec)))
    record['seconds'] = round(time.perf_counter() - t_all, 2)
    record['shared'] = _jsonable(_shareable(shared))
    return out


def _surface(fields, sea_level):
    """The routing surface of a level: its lakes as their flat water, every depression filled, flats tilted."""
    h = np.asarray(fields['h'], np.float64)
    if 'water' in fields:
        h = h + np.asarray(fields['water'], np.float64)
    filled, _ = HY.fill_depressions(h, sea_level=sea_level)
    return HY.routing_surface(filled, sea_level=sea_level)


def _shareable(shared):
    return {k: v for k, v in shared.items() if k in ('uplift', 'U_factor', 'relief', 'fluvial_log', 'lake_modes')}


def _main_of(plan):
    for lv in plan:
        if lv.role == 'main':
            return lv
    return plan[-1]
