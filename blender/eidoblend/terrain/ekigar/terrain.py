"""The generator's output: a Heightfield (height + named masks at a chosen resolution and world size), the project
files that describe one (ekigar-project/3), and the height_at sampler. Plain numpy: no bpy.

    hf = generate('mountainRange', resolution=1024, world_size=2000)            # one operator, default params
    hf = generate(project_dict_or_path)                                        # an ekigar-project/3 file
    hf = generate(graph, target='n7', resolution=512, world_size=400)          # a graph you built
    hf.heights_m          (ny, nx) metres, Blender z
    hf.height_at(x, y)    metres at Blender (x, y), exactly on the mesh build_mesh makes (same triangles)
    hf.mask('slope'), hf.mask('wear'), hf.masks()                              # every mask, by name
    hf.save('t.npz'); Heightfield.load('t.npz')

World frame (Ekigar's, in Blender axes): the tile spans x, y in [-W/2, W/2] around `origin`; texel (i, j) sits at
x = (i + 0.5)/nx W - W/2, y = (j + 0.5)/ny W - W/2 (rows are v, +y); z = (h - z_base) * vertical_scale * W, with
Ekigar's defaults W = 400 m and vertical_scale = 0.3.
"""
from __future__ import annotations

import json

import numpy as np

from . import model as _model
from .compile import evaluate_graph
from .masks import build_masks
from .registry import OPERATORS, default_params, ports_of, graph_ports
from ._tsl import Tile
from .display_grid import display_heights
from .hydrology import hydrology as _hydrology, HYDROLOGY_MASKS

DEFAULT_WORLD_SIZE = 400.0
DEFAULT_VERTICAL_SCALE = 0.3


# ------------------------------------------------------------------------------------------------- projects ---

def load_project(src):
    """An ekigar-project file (path, JSON text or dict), migrated to format 3. Returns (project, warnings)."""
    if isinstance(src, dict):
        doc = src
    elif isinstance(src, str) and src.lstrip().startswith('{'):
        doc = json.loads(src)
    else:
        with open(src, 'r', encoding='utf-8') as f:
            doc = json.load(f)
    return _model.migrate_project(doc)


def project_graph(project):
    return _model.from_json(project.get('graph') or {'nodes': [], 'edges': []})


def terminal_node(graph):
    """The node nothing consumes that is not a material map (main.js's terminalNode): the natural preview target."""
    consumed = {e['from']['node'] for e in graph['edges'].values()}
    cands = [n for n in graph['nodes'].values() if n['id'] not in consumed
             and n['op'] not in ('materialMap', 'surface')]
    return cands[-1]['id'] if cands else None


def make_project(graph, target=None, target_port='out', tile=(1.0, 1.0), world_size=DEFAULT_WORLD_SIZE,
                 res=1024, cut=None, material_target=None, materials=None, base=None):
    """An ekigar-project/3 document (what Ekigar's Save writes), ready for json.dump."""
    t = Tile.of(tile)
    doc = dict(base or {})
    doc.update({
        'format': _model.PROJECT_FORMAT, 'tile': t.as_dict(), 'worldSize': world_size, 'res': res,
        'cut': cut or {}, 'graph': _model.to_json(graph), 'target': target or terminal_node(graph),
        'targetPort': target_port, 'materialTarget': material_target, 'materials': materials or [],
        'conversionWarnings': list((base or {}).get('conversionWarnings') or []),
    })
    return doc


def save_project(path, graph, **kw):
    doc = make_project(graph, **kw)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=2)
    return doc


def single_operator_graph(op, params=None):
    """A graph of one operator (its defaults overridden by `params`); returns (graph, node_id)."""
    if op not in OPERATORS:
        raise KeyError(f"unknown operator '{op}'")
    g = _model.create_graph()
    nid = _model.add_node(g, op, params=dict(default_params(op), **(params or {})))
    return g, nid


def chain_graph(steps):
    """A linear graph from [(op, params), ...]: each node's first input takes the previous node. Returns
    (graph, ids)."""
    g = _model.create_graph()
    ids = []
    for op, params in steps:
        nid = _model.add_node(g, op, params=dict(params or {}))
        if ids:
            ins = ports_of(op)['inputs']
            if ins:
                r = _model.connect(g, {'node': ids[-1], 'port': 'out'}, {'node': nid, 'port': ins[0]['name']},
                                   graph_ports)
                if not r['ok']:
                    raise ValueError(r['reason'])
        ids.append(nid)
    return g, ids


# ----------------------------------------------------------------------------------------------- heightfield ---

class Heightfield:
    """A generated terrain: Ekigar's field on a grid plus where it sits in the world."""

    def __init__(self, field, outs=None, tile=(1.0, 1.0), world_size=DEFAULT_WORLD_SIZE,
                 vertical_scale=DEFAULT_VERTICAL_SCALE, origin=(0.0, 0.0), z_base=0.0, warnings=None, meta=None):
        self.field = np.asarray(field, dtype=np.float64)        # (4, ny, nx): h, dh/dx, dh/dy, aux
        self.outs = dict(outs or {})
        self.tile = Tile.of(tile)
        self.world_size = float(world_size)
        self.vertical_scale = float(vertical_scale)
        self.origin = (float(origin[0]), float(origin[1]))
        self.z_base = float(z_base)
        self.warnings = list(warnings or [])
        self.meta = dict(meta or {})
        self._masks = None

    # grid ---------------------------------------------------------------------------------------------------------
    @property
    def height(self):
        """Ekigar's field height (field units: a unit of height is vertical_scale * world_size metres)."""
        return self.field[0]

    @property
    def aux(self):
        return self.field[3]

    @property
    def resolution(self):
        return self.field.shape[2], self.field.shape[1]

    @property
    def metres_per_unit(self):
        return self.vertical_scale * self.world_size

    @property
    def heights_m(self):
        """Blender z of every texel, metres."""
        return (self.height - self.z_base) * self.metres_per_unit

    def grid_xy(self, side=None):
        """Blender (x, y) of every texel centre, each (ny, nx); with `side`, of a side x side display grid's vertices."""
        nx, ny = (side, side) if side else self.resolution
        w = self.world_size
        x = (np.arange(nx) + 0.5) / nx * w - w / 2 + self.origin[0]
        y = (np.arange(ny) + 0.5) / ny * w - w / 2 + self.origin[1]
        return np.meshgrid(x, y)

    def set_z_base(self, mode):
        """Where z = 0 sits: 'field' (field height 0, Ekigar's frame), 'min', 'mid', 'max', or a field height."""
        h = self.height
        self.__dict__.pop('_display', None)
        self.z_base = {'field': 0.0, 'min': float(h.min()), 'mid': float((h.min() + h.max()) * 0.5),
                       'max': float(h.max())}.get(mode, mode if isinstance(mode, (int, float)) else 0.0)
        return self

    # masks --------------------------------------------------------------------------------------------------------
    def masks(self):
        """Every mask by name: masks.js's set from finite differences of the height (slope, aspect, curvatures,
        concave/convex/converge, ridge ...) plus the target node's named outputs (erosion wear/flow, a landform's
        floor/wall/rim ...)."""
        if self._masks is None:
            nx, ny = self.resolution
            m = build_masks(self.height, aux=self.aux, texel=1.0 / nx, world_size=self.world_size,
                            vertical_scale=self.vertical_scale, wrap=(self.tile.x > 0, self.tile.y > 0))
            flat = {k: v for k, v in m.items() if k not in ('raw', 'geoNormal')}
            flat.update(self.outs)
            flat['_geoNormal'] = m['geoNormal']
            self._masks = flat
        return {k: v for k, v in self._masks.items() if not k.startswith('_')}

    def mask(self, name):
        """One mask by name: masks.js's set, the target's named outputs, or (computed on first use) a hydrology mask
        (accumulation, channels, lake, wetness, moisture, deposition, occlusion, vegetation)."""
        m = self.masks()
        if name in m:
            return m[name]
        if name in HYDROLOGY_MASKS:
            return self.hydrology()[name]
        raise KeyError(f"no mask '{name}' (have {sorted(m) + HYDROLOGY_MASKS})")

    def hydrology(self, **kw):
        """The plan's tier-B masks and raw arrays (hydrology.py): filled surface, lake depth, flow accumulation and
        the masks built on them. Cached; keyword arguments (sea_level, method, ...) recompute."""
        cache = self.__dict__.get('_hydro')
        if cache is None or kw:
            cache = _hydrology(self, **kw)
            self.__dict__['_hydro'] = cache
        return cache

    def hydrology_masks(self):
        """The hydrology masks already computed (empty until hydrology() or mask('<name>') ran)."""
        h = self.__dict__.get('_hydro')
        return {} if h is None else {k: h[k] for k in HYDROLOGY_MASKS if k in h}

    def normals(self):
        """Blender-axes surface normal of every texel (3, ny, nx), from central differences in metres."""
        self.masks()
        g = self._masks['_geoNormal']
        return g / np.linalg.norm(g, axis=0, keepdims=True)

    # sampling -----------------------------------------------------------------------------------------------------
    def _cell(self, x, y, dims=None, wrap=False):
        """Grid cell (i0, j0) and fractions of Blender (x, y) on a (nx, ny) vertex grid over the tile (default: the
        field's texels). Off the grid it clamps to the edge, or with `wrap` (on a periodic tile) continues into the
        neighbouring copy, as a tiled layout or a crop across the seam has it."""
        nx, ny = dims or self.resolution
        w = self.world_size
        u = (np.asarray(x, dtype=np.float64) - self.origin[0] + w / 2) / w * nx - 0.5
        v = (np.asarray(y, dtype=np.float64) - self.origin[1] + w / 2) / w * ny - 0.5
        if wrap:
            i0 = np.floor(u).astype(np.int64)
            j0 = np.floor(v).astype(np.int64)
            return np.mod(i0, nx), np.mod(j0, ny), u - i0, v - j0, True
        u = np.clip(u, 0.0, nx - 1.0)
        v = np.clip(v, 0.0, ny - 1.0)
        i0 = np.minimum(np.floor(u).astype(np.int64), nx - 2)
        j0 = np.minimum(np.floor(v).astype(np.int64), ny - 2)
        return i0, j0, u - i0, v - j0, False

    def display_z(self, side):
        """Blender z (metres) of the vertices of a side x side display grid over the tile: Ekigar's terrain_mesh.js
        layout (vertices on display texel centres, the field read bilinear and wrapping). Cached per side."""
        cache = self.__dict__.setdefault('_display', {})
        if side not in cache:
            cache[side] = (display_heights(self.height, side) - self.z_base) * self.metres_per_unit
        return cache[side]

    def height_at(self, x, y, grid=None, side=None, wrap=False):
        """Height in metres at Blender (x, y) on the triangulated mesh build_mesh makes: each quad
        (a, b, c, d) = (i, j), (i+1, j), (i+1, j+1), (i, j+1) is split along a-c, as Blender splits a quad. `side`
        reads the side x side display grid build_mesh(hf, side=...) makes; `wrap` continues across a periodic tile's
        edge: it reads the mesh build_mesh(hf, wrap=True) makes (its seam row and column included), and so every
        copy of it laid at multiples of world_size, and a crop across the seam. Otherwise points outside the mesh
        clamp to its edge."""
        if side is not None:
            z = self.display_z(int(side))
            dims = (int(side), int(side))
        else:
            z = self.heights_m if grid is None else grid
            dims = (z.shape[1], z.shape[0])
        i0, j0, fx, fy, wrapped = self._cell(x, y, dims, wrap)
        nx, ny = dims
        i1 = np.mod(i0 + 1, nx) if wrapped else i0 + 1
        j1 = np.mod(j0 + 1, ny) if wrapped else j0 + 1
        ha = z[j0, i0]
        hb = z[j0, i1]
        hc = z[j1, i1]
        hd = z[j1, i0]
        lower = fx >= fy
        return np.where(lower, ha + fx * (hb - ha) + fy * (hc - hb), ha + fy * (hd - ha) + fx * (hc - hd))

    def sample(self, name, x, y):
        """A mask (or 'height' in field units) at Blender (x, y), bilinear."""
        a = self.height if name == 'height_field' else self.mask(name)
        i0, j0, fx, fy, _w = self._cell(x, y)
        return ((a[j0, i0] * (1 - fx) + a[j0, i0 + 1] * fx) * (1 - fy)
                + (a[j0 + 1, i0] * (1 - fx) + a[j0 + 1, i0 + 1] * fx) * fy)

    def normal_at(self, x, y):
        n = self.normals()
        i0, j0, fx, fy, _w = self._cell(x, y)
        out = ((n[:, j0, i0] * (1 - fx) + n[:, j0, i0 + 1] * fx) * (1 - fy)
               + (n[:, j0 + 1, i0] * (1 - fx) + n[:, j0 + 1, i0 + 1] * fx) * fy)
        return out / np.linalg.norm(out, axis=0, keepdims=True)

    # io -----------------------------------------------------------------------------------------------------------
    def stats(self):
        return stats_of(self)

    def save(self, path):
        """Write <path>.npz (field + named outputs) with the frame in its metadata."""
        meta = {'tile': self.tile.as_dict(), 'world_size': self.world_size, 'vertical_scale': self.vertical_scale,
                'origin': self.origin, 'z_base': self.z_base, 'warnings': self.warnings, 'meta': self.meta}
        arrays = {'field': self.field.astype(np.float32)}
        for k, v in self.outs.items():
            arrays['out__' + k] = np.asarray(v, dtype=np.float32)
        np.savez_compressed(path, meta=json.dumps(meta, default=str), **arrays)

    @classmethod
    def load(cls, path):
        d = np.load(path, allow_pickle=False)
        meta = json.loads(str(d['meta']))
        outs = {k[5:]: d[k].astype(np.float64) for k in d.files if k.startswith('out__')}
        return cls(d['field'].astype(np.float64), outs, meta['tile'], meta['world_size'], meta['vertical_scale'],
                   meta['origin'], meta['z_base'], meta['warnings'], meta.get('meta'))


def stats_of(hf, sea_level=None, water=None):
    """Height range, slope histogram, NaN count and water fraction of a Heightfield (the plan's statsOf).
    waterFraction: the share of texels under water, the sea (at or below `sea_level`, a field height) plus lakes
    deeper than half a metre when the hydrology has been computed (water=True computes it); None when neither."""
    h = hf.height
    s = hf.mask('slope')
    hist, edges = np.histogram(np.clip(s, 0, 1), bins=10, range=(0.0, 1.0))
    wet = None
    if sea_level is not None:
        wet = h <= sea_level
    if water or hf.__dict__.get('_hydro') is not None:
        lake = hf.hydrology()['lakeDepth_m'] > 0.5
        wet = lake if wet is None else (wet | lake)
    return {'min': float(np.nanmin(h)), 'max': float(np.nanmax(h)), 'mean': float(np.nanmean(h)),
            'std': float(np.nanstd(h)), 'nonFinite': int((~np.isfinite(hf.field)).sum()),
            'heightRangeMetres': float((np.nanmax(h) - np.nanmin(h)) * hf.metres_per_unit),
            'slopeHistogram': {'edges': edges.tolist(), 'counts': hist.tolist()},
            'flatFraction': float((s < 0.02).mean()),
            'waterFraction': None if wet is None else float(np.mean(wet))}


# ---------------------------------------------------------------------------------------------------- generate ---

def generate(source, resolution=None, world_size=None, vertical_scale=DEFAULT_VERTICAL_SCALE, target=None,
             port='out', tile=None, params=None, origin=(0.0, 0.0), z_base='field', derivatives='coarse',
             field_resolution=None, workers=None):
    """Evaluate Ekigar terrain into a Heightfield.

    source  an operator id ('volcano'), an ekigar-project dict / path / JSON text, or a graph from model.py
            (create_graph / from_json); params override an operator's defaults when source is an id
    resolution  texels per side (default: the project's `res`, else 512); world_size metres (project's worldSize,
            else 400); tile the periodic tile (project's, else (1, 1))
    target / port  the node and output to evaluate (default: the project's target, else the terminal node)
    z_base  'field' | 'min' | 'mid' | 'max' | a field height: what sits at z = 0
    derivatives  how screen-space derivatives are taken: 'coarse' (default), the GPU's 2x2 quads as in Ekigar, so a
            project is the terrain Ekigar draws; 'central' measures the slope at every texel (smoother slope and
            angle masks) but departs from Ekigar for slopeMask, angleMask and the ten wave-3 landforms, and an
            erosion after a wave-3 landform turns that into different heights (compile.evaluate_graph)
    field_resolution  the resolution neighbourhood radii are measured in (Ekigar's ctx.resolution). It defaults to
            `resolution`, except for a project generated at another size than its `res`: then the project's res, so
            a 1024 project evaluated at 4096 is the same terrain with more texels, not one with 4x narrower blurs
    """
    project = None
    if isinstance(source, str) and source in OPERATORS:
        graph, nid = single_operator_graph(source, params)
        target = target or nid
    elif isinstance(source, dict) and 'nodes' in source and isinstance(source['nodes'], dict):
        graph = source
    elif isinstance(source, dict) and 'nodes' in source and 'graph' not in source:
        graph = _model.from_json(source)              # a serialised graph (to_json) on its own
    else:
        project, _w = load_project(source)
        graph = project_graph(project)
    if project is not None:
        authored = project.get('res')
        if field_resolution is None and authored and resolution and resolution != authored:
            # keep the look the project was authored with: neighbourhood radii stay in its texels
            field_resolution = authored
        resolution = resolution or authored or 512
        world_size = world_size or project.get('worldSize') or DEFAULT_WORLD_SIZE
        tile = tile if tile is not None else project.get('tile') or (1.0, 1.0)
        if target is None:
            target = project.get('target') if project.get('target') in graph['nodes'] else terminal_node(graph)
            port = project.get('targetPort') or port if target == project.get('target') else port
    resolution = resolution or 512
    world_size = world_size or DEFAULT_WORLD_SIZE
    tile = tile if tile is not None else (1.0, 1.0)
    target = target or terminal_node(graph)
    if target is None:
        raise ValueError('the graph has no node to evaluate')
    res = evaluate_graph(graph, target, port=port, resolution=resolution, tile=tile, derivatives=derivatives,
                         field_resolution=field_resolution, workers=workers)
    # Ekigar's compiler repeats a node's snap warning for every resampled evaluation (a snow or blur after an
    # erosion re-builds it at each offset); the heightfield keeps each distinct warning once, in order
    warnings = list(dict.fromkeys(res['warnings']))
    hf = Heightfield(res['field'], res['outs'], res['tile'], world_size, vertical_scale, origin, 0.0,
                     warnings, {'target': target, 'port': port, 'order': res['order'],
                                       'missing': res['missing'], 'graph': _model.to_json(graph)})
    hf.set_z_base(z_base)
    return hf
