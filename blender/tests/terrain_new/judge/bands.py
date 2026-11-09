"""The bands (DESIGN.md section 10 item 3): how far a generated number may sit from the reference's. The specs are
the design's; calibrate.py runs every reference through itself and writes bands.json with the calibrated parts (the
spectrum-slope tolerance per reference, the anisotropy allowances) and every reference's own numbers.

A spec is a dict:
    abs / rel            two-sided: |g - r| <= max(abs, rel * |r|)
    max_plus             g <= r + max_plus
    max_factor (+ max_plus, floor)   g <= max(max_factor * r, r + max_plus, floor)
    range (lo, hi)       lo <= g <= hi, the design's absolute range for the landform
    min / max            g >= min / g <= max, absolute
    equals               g == r (flags)
    min_factor           g >= min_factor * r
An absolute spec (range, min, max) holds only when the reference itself satisfies it at the matched pixel; when the
real place falls outside the design's range (Yosemite's flat-floored trough has b = 3.8, not 1.5-2.5), the band
becomes the spec's `fallback` around the reference's own value, and the row says so.
"""
from __future__ import annotations

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BANDS_JSON = os.path.join(HERE, 'bands.json')

# section 10 item 3: the generic bands (key: Core's metric names; judge-side: bowl_area_frac)
GENERIC = {
    'relief_m': dict(rel=0.20),
    'hypsometric_integral': dict(abs=0.08),
    'slope_p50': dict(abs=3.0, rel=0.25),
    'slope_p90': dict(abs=4.0, rel=0.15),
    'slope_p99': dict(abs=5.0, rel=0.10),
    'frac_slope_lt5': dict(abs=0.05, rel=0.40),
    'spectrum_slope': dict(abs=0.5, calibrated='spectrum_slope_tol'),
    'depression_area_frac': dict(max_plus=0.01, families='non-basin'),
    'bowl_area_frac': dict(max_plus=0.01, families='basin'),
    'anisotropy_4': dict(max_factor=1.5, max_plus=0.05, calibrated='anisotropy_4_plus'),
    'anisotropy_8': dict(max_factor=1.5, max_plus=0.02, calibrated='anisotropy_8_plus'),
    # the floor: the Goosenecks' own 3 m lidar box-averaged to 6 m has 0.05 % of pairs over 80 degrees where the
    # stored reference (a Gaussian chain) has 0.02 %; real references reach 0.23 % (Lauterbrunnen), Ekigar's mesa
    # 0.54 %, its volcanic plug 1.1 %, its tower karst 3.6 %
    'cliff_pair_frac': dict(max_factor=2.0, floor=0.001),
}

# reported beside the banded numbers (not pass / fail)
GENERIC_INFO = ('relief_robust_m', 'slope_p10', 'frac_slope_gt30', 'frac_slope_gt40', 'frac_slope_gt50',
                'depression_area_frac', 'depression_count', 'flat_basin_area_frac', 'spectrum_knee_m',
                'spectrum_peak_m', 'spectrum_slope_long', 'spectrum_slope_short')

# section 10 item 4: the family numbers' bands
FAMILY = {
    'crater': {
        'crater_d_over_D': dict(abs=0.03, rel=0.20),
        'rim_height_over_D': dict(abs=0.01, rel=0.35),
        'wall_slope_p99': dict(abs=5.0, rel=0.10),
        'ejecta_reach_R': dict(abs=0.5, rel=0.30),
        'rim_roundness': dict(min_factor=0.4),
    },
    'volcano': {
        'profile_spearman': dict(max=-0.9, fallback=dict(abs=0.1)),
        'radial_aspect_frac': dict(min=0.7, fallback=dict(abs=0.1)),
        'summit_crater_m': dict(abs=30.0, rel=0.5),
    },
    'cinder_cones': {
        'cone_hw_max': dict(range=(0.15, 0.20), fallback=dict(abs=0.03)),
        'cone_flank_p90': dict(range=(28.0, 33.0), fallback=dict(abs=3.0)),
        'cone_count': dict(abs=2, rel=0.5),
    },
    'alpine_valley': {
        'u_exponent': dict(range=(1.5, 2.5), fallback=dict(abs=0.5, rel=0.25)),
        'hanging_step_m': dict(min=100.0, fallback=dict(rel=0.5)),
        'trough_width_m': dict(rel=0.5),
    },
    'canyon': {
        # the design's ">= 3 benches" holds only at Toroweap at its 8 m pixel (2.8-3.3 per wall); the Goosenecks show
        # 1.7-2.2 at 6 m, a mesa field 0.3-0.5, Ekigar's canyon 0-0.07: at least 0.6 x the reference's
        'benches_per_wall': dict(min_factor=0.6),
        'slope_bimodal': dict(equals=True),
        'cliff_tail_frac': dict(abs=0.03, rel=0.30),
    },
    'mesas': {
        'caprock_frac': dict(abs=0.01, rel=0.5),
        'butte_wall_p90': dict(min=60.0, fallback=dict(abs=5.0)),
    },
    'dunes': {
        'slip_face_p99': dict(range=(26.0, 34.0), fallback=dict(abs=5.0, rel=0.10)),
        'dune_spacing_m': dict(rel=0.30),
        'lee_aspect_peaks': dict(abs=1),
    },
    'karst': {
        'summit_spacing_m': dict(rel=0.25),
        'plain_frac': dict(rel=0.30),
    },
    'coast': {
        'clifftop_p50_m': dict(rel=0.25),
        'clifftop_p90_m': dict(rel=0.25),
        'cliff_face_p90': dict(abs=5.0, rel=0.10),
    },
    'rolling_hills': {
        'ridge_convex_frac': dict(min=0.7, fallback=dict(abs=0.1)),
    },
    'caldera': {
        'caldera_D_m': dict(rel=0.25),
        'caldera_d_over_D': dict(abs=0.01, rel=0.3),
        'caldera_wall_slope_p99': dict(abs=5.0, rel=0.10),
    },
}


def load():
    """bands.json (the calibrated parts), or {} before calibrate.py has run."""
    if os.path.exists(BANDS_JSON):
        with open(BANDS_JSON, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _finite(v):
    return isinstance(v, (int, float)) and math.isfinite(v)


def _fmt(v):
    if isinstance(v, bool):
        return str(int(v))
    if not _finite(v):
        return '-'
    a = abs(v)
    return f'{v:.0f}' if a >= 100 else f'{v:.1f}' if a >= 10 else f'{v:.2f}' if a >= 0.995 else f'{v:.3f}'


def evaluate(key, spec, r, g, calibration=None):
    """One row: dict(metric, ref, gen, band (text), lo, hi, passed (True / False / None when not judged), note)."""
    row = dict(metric=key, ref=r, gen=g, lo=None, hi=None, passed=None, note='')
    if not (_finite(r) or isinstance(r, bool)) or not (_finite(g) or isinstance(g, bool)):
        row['band'] = 'not measurable'
        row['note'] = 'not found on ' + ('the reference' if not _finite(r) else 'the generated field')
        if _finite(r) and not _finite(g):
            row['passed'] = False                   # the reference has the feature, the generated field does not
        return row
    spec = dict(spec)
    cal = calibration or {}
    if spec.get('calibrated') and spec['calibrated'] in cal:
        v = cal[spec['calibrated']]
        if 'max_plus' in spec:
            spec['max_plus'] = v
        else:
            spec['abs'] = v
    lo = hi = None
    absolute = [k for k in ('range', 'min', 'max') if k in spec]
    if absolute:
        if 'range' in spec:
            lo, hi = spec['range']
        else:
            lo, hi = spec.get('min'), spec.get('max')
        ref_ok = (lo is None or r >= lo - 1e-12) and (hi is None or r <= hi + 1e-12)
        if not ref_ok and 'fallback' in spec:
            fb = spec['fallback']
            tol = max(fb.get('abs', 0.0), fb.get('rel', 0.0) * abs(r))
            # a one-sided limit stays one-sided: beyond the reference on the design's side is no fault
            lo = r - tol if 'min' in spec or 'range' in spec else None
            hi = r + tol if 'max' in spec or 'range' in spec else None
            row['note'] = 'the reference is outside the design\'s range: judged against the reference'
    elif 'equals' in spec:
        row.update(lo=r, hi=r, passed=bool(g) == bool(r), band=f'= {_fmt(r)}')
        return row
    elif 'min_factor' in spec:
        lo = spec['min_factor'] * r
    elif 'max_factor' in spec or 'max_plus' in spec:
        hi = max(spec.get('max_factor', 1.0) * r, r + spec.get('max_plus', 0.0), spec.get('floor', -math.inf))
    else:
        tol = max(spec.get('abs', 0.0), spec.get('rel', 0.0) * abs(r))
        lo, hi = r - tol, r + tol
    row['lo'], row['hi'] = lo, hi
    row['passed'] = bool((lo is None or g >= lo - 1e-12) and (hi is None or g <= hi + 1e-12))
    row['band'] = ('<= ' + _fmt(hi) if lo is None else '>= ' + _fmt(lo) if hi is None
                   else f'{_fmt(lo)} .. {_fmt(hi)}')
    return row


def generic_rows(gnum, rnum, basins_allowed, calibration=None):
    rows = []
    for key, spec in GENERIC.items():
        fam = spec.get('families')
        if fam == 'basin' and not basins_allowed or fam == 'non-basin' and basins_allowed:
            continue
        row = evaluate(key, spec, rnum.get(key), gnum.get(key), calibration)
        row['kind'] = 'generic'
        rows.append(row)
    for key in GENERIC_INFO:
        if any(r['metric'] == key for r in rows):
            continue
        rows.append(dict(metric=key, ref=rnum.get(key), gen=gnum.get(key), band='info', passed=None, note='',
                         kind='info'))
    return rows


def family_rows(family, gfam, rfam, calibration=None):
    rows = []
    for key, spec in FAMILY.get(family, {}).items():
        row = evaluate(key, spec, rfam.get(key), gfam.get(key), calibration)
        row['kind'] = 'family'
        rows.append(row)
    target = gfam.get('target_spacing_m')
    if family == 'dunes' and _finite(target):
        row = evaluate('dune_spacing_m (target)', dict(rel=0.30), target, gfam.get('dune_spacing_m'))
        row['kind'] = 'family'
        row['note'] = 'against the recipe\'s target spacing'
        rows.append(row)
    return rows
