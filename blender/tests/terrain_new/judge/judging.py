"""judge(result, reference) -> Verdict: a generated terrain's numbers beside its reference's, each in its band
(DESIGN.md section 10 items 1-4). Numpy only: runs in Blender's Python and the system's. Renders and the compare
sheet are run.py's (they need Blender and Pillow).

    v = judge(t, 'mount_fuji')                 # a Terrain, a saved terrain (<path>.npz from Terrain.save), a dict
                                               # (h=, cell=, water=, sea_level=, frame='south_up'|'north_up'),
                                               # an .npz with those keys, or an (h, cell) pair (row 0 = south)
    v.passed, v.failures, print(v.table()), v.to_dict(), v.save('verdict.json')

`hints` pass what the recipe knows to the family readers (dunes: target_spacing_m; crater: centre (column, row) and
radius_m on the matched grid; volcano: vent). `family` overrides the reference's family (a canyon recipe judged on
a mesa reference, say). `source_chain=False` for a field that is already the reference's data (the real_place
recipe's main level, the self-test): the radar references' softening chain (match.py step 4) is then not applied
a second time.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

from . import bands as B
from . import family as F
from . import generic as G
from . import match as MA
from . import refs

_REF_CACHE = {}


class Verdict:
    """The judge's answer: rows of numbers (generic, family, info), the verdict, the reasons and the notes."""

    def __init__(self, reference, family, label, matched, rows, gnum, rnum, gfam, rfam):
        self.reference = reference
        self.family = family
        self.label = label
        self.pixel = matched.pixel
        self.extent = matched.extent
        self.notes = list(matched.notes)
        self.rows = rows
        self.numbers = dict(generated=gnum, reference=rnum, generated_family=gfam, reference_family=rfam)
        for r in rows:
            if r.get('note') and r['passed'] is not None:
                self.notes.append(f"{r['metric']}: {r['note']}")

    @property
    def judged(self):
        return [r for r in self.rows if r['passed'] is not None]

    @property
    def passed(self):
        return all(r['passed'] for r in self.judged)

    @property
    def failures(self):
        return [f"{r['metric']}: generated {B._fmt(r['gen'])}, reference {B._fmt(r['ref'])}, band {r['band']}"
                + (f" ({r['note']})" if r.get('note') else '') for r in self.judged if not r['passed']]

    def summary(self):
        n = len(self.judged)
        bad = n - sum(1 for r in self.judged if r['passed'])
        return (f"{self.label or 'generated'} vs {self.reference} ({self.family}, {self.pixel:g} m, "
                f"{self.extent / 1000:g} km): {'PASS' if self.passed else 'FAIL'} ({n - bad}/{n} bands)")

    def table(self):
        lines = [self.summary()]
        lines += ['  note: ' + n for n in self.notes]
        lines.append(f"  {'metric':26s} {'generated':>11s} {'reference':>11s}  {'band':22s} verdict")
        for r in self.rows:
            if r['kind'] == 'info':
                continue
            v = 'PASS' if r['passed'] else ('FAIL' if r['passed'] is False else '-')
            lines.append(f"  {r['metric']:26s} {B._fmt(r['gen']):>11s} {B._fmt(r['ref']):>11s}  {r['band']:22s} {v}")
        info = [r for r in self.rows if r['kind'] == 'info']
        if info:
            lines.append('  also: ' + ', '.join(f"{r['metric']} {B._fmt(r['gen'])} (ref {B._fmt(r['ref'])})"
                                                 for r in info))
        return '\n'.join(lines)

    def to_dict(self):
        def clean(v):
            if isinstance(v, dict):
                return {k: clean(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [clean(x) for x in v]
            if isinstance(v, (np.floating, float)):
                return float(v) if math.isfinite(v) else None
            if isinstance(v, np.integer):
                return int(v)
            if isinstance(v, np.bool_):
                return bool(v)
            return v
        return clean(dict(reference=self.reference, family=self.family, label=self.label, pixel_m=self.pixel,
                          extent_m=self.extent, passed=self.passed, failures=self.failures, notes=self.notes,
                          rows=self.rows, numbers=self.numbers))

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=1)
        return path

    def __repr__(self):
        return f'Verdict({self.summary()})'


# --------------------------------------------------------------------------------------------- the inputs ---

def _load_saved_terrain(base):
    """The main level of a Terrain.save() file: (h, cell, water, sea_level)."""
    with open(base + '.json', encoding='utf-8') as f:
        meta = json.load(f)
    plan = meta['plan']
    i = next(k for k, lv in enumerate(plan) if lv.get('role') == 'main')
    d = np.load(base + '.npz')
    h = d[f'L{i}__f__h']
    water = d[f'L{i}__f__water'] if f'L{i}__f__water' in d.files else None
    return h, float(plan[i]['cell']), water, meta.get('sea_level')


def unpack(result):
    """(h row 0 = south float64, cell m, water or None, sea_level or None) from any accepted result."""
    if hasattr(result, 'fields') and hasattr(result, 'main'):                       # a Terrain
        f = result.fields('main')
        water = f['water'] if 'water' in f else None
        sea = getattr(result, 'info', {}).get('sea_level') if isinstance(getattr(result, 'info', None), dict) else None
        return np.asarray(f['h'], np.float64), float(result.main.cell), water, sea
    if isinstance(result, (tuple, list)) and len(result) == 2:
        return np.asarray(result[0], np.float64), float(result[1]), None, None
    if isinstance(result, str):
        base = os.path.splitext(result)[0]
        if os.path.exists(base + '.json') and os.path.exists(base + '.npz'):
            with open(base + '.json', encoding='utf-8') as f:
                if 'plan' in json.load(f):
                    return _load_saved_terrain(base)
        d = np.load(base + '.npz' if not result.endswith('.npz') else result)
        result = {k: d[k] for k in d.files}
        for k in ('cell', 'sea_level'):
            if k in result and np.ndim(result[k]) == 0:
                result[k] = float(result[k])
        if 'frame' in result:
            result['frame'] = str(result['frame'])
    if isinstance(result, dict):
        h = np.asarray(result['h'], np.float64)
        water = result.get('water')
        if result.get('frame', 'south_up') == 'north_up':
            h = h[::-1]
            water = None if water is None else np.asarray(water)[::-1]
        sea = result.get('sea_level')
        return h, float(result['cell']), water, (None if sea is None or not math.isfinite(sea) else float(sea))
    raise TypeError('judge() takes a Terrain, a saved terrain path, an .npz path, a dict(h=, cell=, ...) or (h, cell)')


def _reference_numbers(ref, matched, family):
    key = (ref.name, matched.pixel, matched.ref.shape, family, round(matched.extent, 3))
    if key not in _REF_CACHE:
        rnum = G.numbers(matched.ref, matched.pixel, matched.ref_water)
        rfam = F.family_numbers(family, matched.ref, matched.pixel, None, sea_level=ref.sea_level)
        _REF_CACHE[key] = (rnum, rfam)
    return _REF_CACHE[key]


def judge(result, reference, family=None, hints=None, label=None, calibration=None, source_chain=True):
    """The verdict of a generated terrain against a reference (a name from refs.names() or a refs.Reference)."""
    ref = refs.load(reference) if isinstance(reference, str) else reference
    h, cell, water, sea = unpack(result)
    fam = family or ref.family
    m = MA.match(h, cell, ref, water=water, sea_level=sea, source_chain=source_chain)
    gnum = G.numbers(m.gen, m.pixel, m.gen_water)
    rnum, rfam = _reference_numbers(ref, m, fam)
    gfam = F.family_numbers(fam, m.gen, m.pixel, hints, sea_level=(sea if sea is not None else ref.sea_level))
    if calibration is None:
        calibration = B.load().get('references', {}).get(ref.name, {}).get('calibration', {})
        glob = B.load().get('calibration', {})
        calibration = dict(glob, **calibration)
    rows = B.generic_rows(gnum, rnum, fam in refs.BASIN_FAMILIES, calibration)
    rows += B.family_rows(fam, gfam, rfam, calibration)
    return Verdict(ref.name, fam, label, m, rows, gnum, rnum, gfam, rfam)
