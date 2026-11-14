"""The plant spots of a terrain as the judge reads them (SURFACING_DESIGN.md section 4.5), numpy only and on its own:
the format is read here from its description, not through the plant layer's code, so the judge also checks that a
saved file says what the format promises (a three.js placer reads the same two files).

    from surfacing_judge import plants as PL
    spots = PL.load('<base>')                 # <base>.plants.json + <base>.plants.<species>.f32
    spots.species                             # the header's species list (name, kind, size_m, count, fields, ...)
    a = spots.table('spruce')                 # {field: float32 array}: x, y, z, yaw, scale, age, tint, nx, ny, nz, ...
    PL.check(spots)                           # what the files get wrong against the format ([] when nothing)
    PL.density(spots, 'spruce', window)       # stems per hectare in a rectangle (x0, y0, x1, y1)
    PL.spacing(spots, 'spruce', window, core_m, sigma_m)   # inhibited below the core, clustered at sigma?
    PL.edge_density(spots, 'spruce')          # stems per hectare either side of each window edge (a gate: 10 %)
    PL.save(base, header, tables)             # writes the format (the tests' fixtures)

    python blender/tests/terrain/surfacing_judge/plants.py <base> [--terrain <source>]
        # every species of a saved spots file: what it gets wrong against the format (with --terrain, a terrain
        # list's source as check_views.py takes it: plants off the ground too), stems per hectare, the nearest
        # pair against the hard core, and the pair correlation at the core and at the cluster scale

Records are headerless little-endian float32, stride = len(fields), the convention of core/io.py's r32 sidecar.
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

if __package__ in (None, ''):                          # run as a script: the package from its folder's parent
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
    __package__ = 'surfacing_judge'
    import surfacing_judge  # noqa: F401,E402

from . import measures as M  # noqa: E402

FORMAT = 'eidoverse-terrain-plants/1'
FIELDS = ('x', 'y', 'z', 'yaw', 'scale', 'age', 'tint', 'nx', 'ny', 'nz', 'variant', 'level')
KINDS = ('tree', 'shrub', 'grass', 'forb', 'groundcover')


class Spots:
    def __init__(self, base, header, tables):
        self.base = base
        self.header = header
        self.species = header.get('species', [])
        self._tables = tables

    def names(self):
        return [s['name'] for s in self.species]

    def entry(self, name):
        for s in self.species:
            if s['name'] == name:
                return s
        raise KeyError(f'no species {name!r} in {self.base}; it has: {", ".join(self.names())}')

    def table(self, name):
        return self._tables[name]

    def count(self, name=None):
        return sum(len(t['x']) for n, t in self._tables.items() if name in (None, n))


def load(base):
    """The spots saved at <base>.plants.json (a path with or without that ending)."""
    base = str(base)
    for end in ('.plants.json', '.json'):
        if base.endswith(end):
            base = base[:-len(end)]
            break
    with open(base + '.plants.json', encoding='utf-8') as f:
        header = json.load(f)
    tables = {}
    folder = os.path.dirname(base)
    for s in header.get('species', []):
        fields = list(s.get('fields') or FIELDS)
        path = os.path.join(folder, os.path.basename(s['file'])) if s.get('file') else \
            f"{base}.plants.{s['name']}.f32"
        raw = np.fromfile(path, dtype='<f4') if os.path.exists(path) else np.zeros(0, '<f4')
        n = len(raw) // max(len(fields), 1)
        rec = raw[:n * len(fields)].reshape(n, len(fields))
        tables[s['name']] = {k: rec[:, i] for i, k in enumerate(fields)}
        tables[s['name']]['_bytes'] = len(raw) * 4
    return Spots(base, header, tables)


def save(base, header, tables):
    """Write spots in the format: header (the JSON without counts and files, which are filled in) and tables
    {species: {field: array}}. Returns the header written."""
    header = json.loads(json.dumps(header))
    header['format'] = FORMAT
    folder = os.path.dirname(os.path.abspath(base))
    os.makedirs(folder, exist_ok=True)
    for s in header['species']:
        fields = list(s.setdefault('fields', list(FIELDS)))
        t = tables[s['name']]
        n = len(t[fields[0]])
        rec = np.stack([np.asarray(t[k], '<f4') for k in fields], 1) if n else np.zeros((0, len(fields)), '<f4')
        s['count'] = int(n)
        s['file'] = f"{os.path.basename(base)}.plants.{s['name']}.f32"
        rec.astype('<f4').tofile(os.path.join(folder, s['file']))
    with open(base + '.plants.json', 'w', encoding='utf-8') as f:
        json.dump(header, f, indent=1)
    return header


def check(spots, height_at=None, tolerance_m=0.05):
    """What a saved spots file gets wrong against the format: a list of sentences ([] when it is sound). With
    height_at (the terrain's), also the plants that float over or sink under the ground by more than tolerance_m."""
    out = []
    h = spots.header
    if h.get('format') != FORMAT:
        out.append(f"format is {h.get('format')!r}, not {FORMAT!r}")
    for key in ('frame', 'terrain', 'species'):
        if key not in h:
            out.append(f'the header has no {key!r}')
    for s in spots.species:
        nm = s.get('name', '?')
        fields = list(s.get('fields') or [])
        if fields[:3] != ['x', 'y', 'z']:
            out.append(f'{nm}: fields must begin x, y, z (got {fields[:3]})')
        if s.get('kind') not in KINDS:
            out.append(f"{nm}: kind {s.get('kind')!r} is not one of {', '.join(KINDS)}")
        t = spots.table(nm)
        n = len(t.get('x', ()))
        if t['_bytes'] != n * len(fields) * 4:
            out.append(f"{nm}: the .f32 holds {t['_bytes']} bytes, not a whole number of {len(fields)}-float records")
        if s.get('count') != n:
            out.append(f"{nm}: the header counts {s.get('count')} plants, the file holds {n}")
        if not n:
            continue
        for k in fields:
            if not np.isfinite(t[k]).all():
                out.append(f'{nm}: {k} holds values that are not finite')
        if 'scale' in t and float(t['scale'].min()) <= 0.0:
            out.append(f'{nm}: a scale of 0 or less')
        if all(k in t for k in ('nx', 'ny', 'nz')):
            ln = np.sqrt(t['nx'] ** 2 + t['ny'] ** 2 + t['nz'] ** 2)
            if float(np.abs(ln - 1.0).max()) > 1e-3:
                out.append(f'{nm}: the ground normals are not unit vectors (lengths {ln.min():.3f}-{ln.max():.3f})')
        if height_at is not None:
            dz = t['z'].astype(np.float64) - np.asarray(height_at(t['x'].astype(np.float64),
                                                                  t['y'].astype(np.float64)))
            bad = int((np.abs(dz) > tolerance_m).sum())
            if bad:
                out.append(f'{nm}: {bad} of {n} plants are off the ground by more than {tolerance_m:g} m '
                           f'({dz.min():+.2f} .. {dz.max():+.2f} m)')
    return out


def density(spots, name, window=None):
    """Stems per hectare of a species: in the rectangle (x0, y0, x1, y1), or over its own bounding box."""
    t = spots.table(name)
    x, y = t['x'].astype(np.float64), t['y'].astype(np.float64)
    if not len(x):
        return 0.0
    if window is None:
        window = (float(x.min()), float(y.min()), float(x.max()), float(y.max()))
    x0, y0, x1, y1 = window
    k = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
    return M.stems_per_ha(int(k.sum()), (x1 - x0) * (y1 - y0))


def core_violations(spots, name, core_m=None, window=None):
    """The pairs of a species standing inside each other's hard core: two plants nearer than core_m x the smaller of
    their scales (the design's rejection rule: a candidate within core_m x its scale of an accepted plant). Returns
    dict(pairs, worst: the smallest distance over what was required, or None, nearest_m)."""
    t = spots.table(name)
    x, y = t['x'].astype(np.float64), t['y'].astype(np.float64)
    s = t['scale'].astype(np.float64) if 'scale' in t else np.ones(len(x))
    if window is not None:
        x0, y0, x1, y1 = window
        k = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
        x, y, s = x[k], y[k], s[k]
    core = float(core_m if core_m is not None else spots.entry(name).get('core_m') or 0.0)
    if len(x) < 2 or core <= 0.0:
        return dict(pairs=0, worst=None, nearest_m=None)
    bad, worst, nearest = 0, None, math.inf
    for a, b, d in M.pairs_within(x, y, core * float(s.max())):
        need = core * np.minimum(s[a], s[b])
        nearest = min(nearest, float(d.min()))
        k = d < need * (1.0 - 1e-6)
        if k.any():
            bad += int(k.sum()) // 2                    # each pair comes twice, once from either end
            w = float((d[k] / need[k]).min())
            worst = w if worst is None else min(worst, w)
    return dict(pairs=bad, worst=worst, nearest_m=(None if not math.isfinite(nearest) else nearest))


def spacing(spots, name, window, core_m=None, sigma_m=None):
    """A species' pattern from its pair correlation (measures.plant_pattern): inhibited below its hard core,
    clustered at its cluster scale. core_m and sigma_m default to the species entry's core_m and cluster sigma_m."""
    e = spots.entry(name)
    core_m = float(core_m if core_m is not None else e.get('core_m') or 1.0)
    cl = e.get('cluster') or {}
    sigma_m = sigma_m if sigma_m is not None else (cl.get('sigma_m') if isinstance(cl, dict) else None)
    t = spots.table(name)
    return M.plant_pattern(t['x'], t['y'], window, core_m, sigma_m)


def edge_density(spots, name, windows=None, strip_m=50.0, min_count=20):
    """Stems per hectare of a species in strip_m strips either side of every level window's edge (section 6's gate:
    within 10 % across an edge). windows: [(x0, y0, side), ...], default the header's terrain levels after the first
    (a level's window is its edge with its parent). Returns [dict(level, edge, inner, outer, ratio, verdict)], an
    edge left out where either strip holds under min_count plants (too few to say)."""
    t = spots.table(name)
    x, y = t['x'].astype(np.float64), t['y'].astype(np.float64)
    if windows is None:
        lv = (spots.header.get('terrain') or {}).get('levels') or []
        windows = [(float(L[0]), float(L[1]), float(L[2])) for L in lv[1:]]
    out = []
    for i, (x0, y0, sd) in enumerate(windows):
        x1, y1 = x0 + sd, y0 + sd
        along_x = (x >= x0) & (x <= x1)
        along_y = (y >= y0) & (y <= y1)
        edges = {'south': (along_x & (y >= y0) & (y < y0 + strip_m), along_x & (y < y0) & (y >= y0 - strip_m)),
                 'north': (along_x & (y <= y1) & (y > y1 - strip_m), along_x & (y > y1) & (y <= y1 + strip_m)),
                 'west': (along_y & (x >= x0) & (x < x0 + strip_m), along_y & (x < x0) & (x >= x0 - strip_m)),
                 'east': (along_y & (x <= x1) & (x > x1 - strip_m), along_y & (x > x1) & (x <= x1 + strip_m))}
        area = strip_m * sd
        for edge, (inner, outer) in edges.items():
            ni, no = int(inner.sum()), int(outer.sum())
            if ni < min_count or no < min_count:
                continue
            r = (ni / area) / (no / area)
            out.append(dict(level=i + 1, edge=edge, inner=M.stems_per_ha(ni, area), outer=M.stems_per_ha(no, area),
                            ratio=float(r), verdict=M.verdict('plants_edge_ratio', r)))
    return out


def report(spots, height_at=None):
    """Per species: count, stems per hectare over its own extent, the hard-core pairs, and the pattern (module doc)."""
    out = dict(problems=check(spots, height_at), species={})
    for s in spots.species:
        nm = s['name']
        t = spots.table(nm)
        if not len(t.get('x', ())):
            out['species'][nm] = dict(count=0)
            continue
        x, y = t['x'].astype(np.float64), t['y'].astype(np.float64)
        win = (float(x.min()), float(y.min()), float(x.max()), float(y.max()))
        row = dict(count=int(len(x)), kind=s.get('kind'), stems_per_ha=density(spots, nm, win),
                   core=core_violations(spots, nm))
        if len(x) >= 50 and min(win[2] - win[0], win[3] - win[1]) > 0:
            p = spacing(spots, nm, win)
            row['pattern'] = {k: p[k] for k in ('g_core', 'inhibited', 'g_cluster', 'clustered', 'g_far') if k in p}
        row['edges'] = edge_density(spots, nm)
        out['species'][nm] = row
    return out


def main(argv):
    if not argv or argv[0].startswith('--'):
        print(__doc__)
        return 2
    spots = load(argv[0])
    height_at = None
    if '--terrain' in argv:
        from .check_views import load_terrain
        st = load_terrain((spots.header.get('terrain') or {}).get('recipe'), argv[argv.index('--terrain') + 1])
        height_at = st.height_at
    print(json.dumps(report(spots, height_at), indent=1, default=float))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
