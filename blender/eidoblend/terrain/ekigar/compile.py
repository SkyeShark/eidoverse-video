"""Compile and evaluate an Ekigar graph (src/graph/compile.js), over numpy grids.

Ekigar compiles a graph into one TSL expression that the GPU evaluates per pixel. Here the same recursion evaluates
every node over a whole grid of positions at once:

  * memoised by (node, position tag): an output feeding three consumers is computed once;
  * a node that needs its input at a DIFFERENT position (curvature, blur, thermal, seamless ...) asks for it through
    ctx.sample_input(dx, dy), which re-evaluates the upstream chain at the offset positions (real neighbour samples,
    which is what makes second derivatives correct rather than zero); resampling nests at most 3 deep;
  * position warps are threaded, not applied: a Warp node passes a modified p along its wire, so downstream
    generators build organic landform rather than a warped copy of finished terrain;
  * a disabled node is a pass-through; a mask wire mixes the node's output back toward its input;
  * periodic lattices are snapped to whole cells per tile, and every snap is reported in `warnings`.

    res = evaluate_graph(graph, target, resolution=512, tile=(1, 1))
    res['height'], res['field'] (4, N, N: h, dh/dx, dh/dy, aux), res['outs'][name], res['warnings']

Coordinates: p = uv * tile with uv at texel centres, (i + 0.5) / N; arrays are [row = v, column = u].
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from ._tsl import Vec, Params, Tile, clamp, mix
from . import _deriv
from .registry import OPERATORS, ports_of, graph_ports
from .model import evaluation_order, inputs_of
from .field_cpu import snap_freq

MAX_RESAMPLE_DEPTH = 3


def _zero():
    return Vec(0.0, 0.0, 0.0, 0.0)


class Ctx:
    """What an operator's apply() receives as ctx: p (vec2 positions), tile, resolution, and per node the inputs
    (port -> field), wired (set of connected port names) and sample_input(dx, dy)."""

    def __init__(self, p, tile, resolution=None, inputs=None, wired=None, sample_input=None):
        self.p = p
        self.tile = Tile.of(tile)
        self.resolution = resolution
        self.inputs = inputs
        self.wired = wired
        self.sample_input = sample_input

    def with_(self, **kw):
        c = Ctx(self.p, self.tile, self.resolution, self.inputs, self.wired, self.sample_input)
        for k, v in kw.items():
            setattr(c, k, v)
        return c


def _label(node, op):
    return node.get('title') or (op or {}).get('label') or node.get('op')


def _field_output_spec(graph, target, port='out'):
    node = graph['nodes'].get(target)
    if node is None:
        return None
    requested = port or 'out'
    outputs = ports_of(node['op'])['outputs']
    spec = next((p for p in outputs if p['name'] == requested), None)
    op = OPERATORS.get(node['op'])
    if spec is None:
        only = outputs[0] if len(outputs) == 1 else None
        if requested == 'out' and only and only['type'] == 'material':
            raise ValueError(f"{_label(node, op)}: cannot compile material output '{only['name']}' as a terrain field")
        raise ValueError(f"{_label(node, op)}: output '{requested}' is not declared")
    if spec['type'] == 'material':
        raise ValueError(f"{_label(node, op)}: cannot compile material output '{spec['name']}' as a terrain field")
    return spec


def _normalise(raw):
    if isinstance(raw, dict) and 'field' in raw:
        return raw['field'], raw.get('outs')
    return raw, None


def _defaults(op):
    return {k: v['default'] for k, v in op['params'].items()}


def snap_periods(op, node, raw, tile, warnings):
    """Snap every lattice period to a whole number of cells per tile, and say so (compile.js snapPeriods)."""
    t = tile.x if tile.x > 0 else (tile.y if tile.y > 0 else 0)
    if not (t > 0):
        return raw
    name = node.get('title') or op['label']
    out = raw
    for k, schema in op['params'].items():
        if not schema.get('periodFreq'):
            continue
        want = out.get(k)
        if not (isinstance(want, (int, float)) and want > 0):
            continue
        got = snap_freq(want, t)
        if abs(want - got) < 1e-9:
            continue
        out = dict(out)
        out[k] = got
        warnings.append(f'{name}: {k} {_js(want)} gives a {want * t:.3f}-cell period; snapped to {_js(got)}')
    if op.get('snap'):
        s = op['snap'](out, tile, snap_freq)
        out = s.get('params') or out
        for n in s.get('notes') or []:
            warnings.append(f'{name}: {n}')
    return out


def _js(v):
    f = float(v)
    return str(int(f)) if f.is_integer() else repr(f)


def is_live_param(schema):
    """Live (a uniform the UI can write in Ekigar) rather than structural."""
    return not (schema.get('structural') or schema.get('type') in ('enum', 'bool', 'int', 'vec2'))


def resolve_params(op, raw):
    """Structural params stay numbers / strings / bools; vec2 params become Vec; floats stay floats."""
    out = {}
    for k, schema in op['params'].items():
        v = raw.get(k)
        if schema.get('type') == 'vec2' and isinstance(v, (list, tuple)):
            out[k] = Vec(float(v[0]), float(v[1]))
        elif isinstance(v, bool):
            out[k] = v
        elif isinstance(v, (int, float)) and schema.get('type') == 'float':
            out[k] = float(v)
        else:
            out[k] = v
    return Params(out)


def compile_graph(graph, target, ctx, port='out'):
    """Evaluate node `target` at ctx.p. Returns dict(field, outs, order, missing, warnings, resamples)."""
    _field_output_spec(graph, target, port)
    order, missing = evaluation_order(graph, target, graph_ports)
    warnings = []
    memo = {}
    counter = {'resamples': 0}

    def pick(rec, port_name, node, op):
        if not port_name or port_name == 'out':
            return rec['field']
        m = (rec.get('outs') or {}).get(port_name)
        if m is not None:
            return Vec(m, 0.0, 0.0, m)
        warnings.append(f"{_label(node, op)}: output '{port_name}' is not produced in the field pass — using 'out'")
        return rec['field']

    def build(nid, p, tag, depth):
        key = (nid, tag)
        if key in memo:
            return memo[key]
        node = graph['nodes'].get(nid)
        if node is None:
            return {'field': _zero(), 'outs': None, 'p': p}
        op = OPERATORS.get(node['op'])
        if op is None:
            raise KeyError(f"node {nid} references unknown operator '{node['op']}'")
        wired = inputs_of(graph, nid)
        ports = ports_of(node['op'])
        first_in = next((wired[i['name']] for i in ports['inputs'] if wired.get(i['name'])), None)
        pos = p
        if first_in:
            pos = build(first_in['node'], p, tag, depth)['p']

        def frm(src):
            sn = graph['nodes'].get(src['node'])
            _field_output_spec(graph, src['node'], src.get('port') or 'out')
            rec = build(src['node'], p, tag, depth)
            return pick(rec, src.get('port'), sn or node, OPERATORS.get((sn or {}).get('op')) or op)

        if node.get('disabled'):
            r = {'field': frm(first_in) if first_in else _zero(), 'outs': None, 'p': pos}
            memo[key] = r
            return r

        merged = _defaults(op)
        merged.update(node.get('params') or {})
        params = resolve_params(op, snap_periods(op, node, merged, ctx.tile, warnings))

        if op.get('warpPosition'):
            if first_in:
                src_field = frm(first_in)
                src_p = build(first_in['node'], p, tag, depth)['p']
            else:
                src_field, src_p = _zero(), p
            r = {'field': src_field, 'outs': None, 'p': op['warpPosition'](params, ctx.with_(p=src_p))}
            memo[key] = r
            return r

        ins = {}
        connected = set()
        for prt in ports['inputs']:
            src = wired.get(prt['name'])
            if src:
                ins[prt['name']] = frm(src)
                connected.add(prt['name'])
            else:
                if prt.get('required'):
                    warnings.append(f"{_label(node, op)}: '{prt['name']}' not connected")
                ins[prt['name']] = _zero()
        in_field = ins.get(ports['inputs'][0]['name']) if ports['inputs'] else None
        if in_field is None:
            in_field = _zero()

        def sample_input(dx, dy):
            if not first_in or depth >= MAX_RESAMPLE_DEPTH:
                return in_field
            counter['resamples'] += 1
            off_p = pos + Vec(dx, dy)
            return build(first_in['node'], off_p, f'{tag}@{dx!r},{dy!r}#{depth}', depth + 1)['field']

        raw = op['apply'](in_field, params, ctx.with_(p=pos, inputs=ins, wired=connected, sample_input=sample_input))
        out, outs = _normalise(raw)
        mask_src = wired.get('mask') if ports['mask'] else None
        if mask_src:
            m = clamp(frm(mask_src).x, 0.0, 1.0)
            out = Vec(mix(in_field.x, out.x, m), mix(in_field.y, out.y, m),
                      mix(in_field.z, out.z, m), mix(in_field.w, out.w, m))
        r = {'field': out, 'outs': outs, 'p': pos}
        memo[key] = r
        return r

    result = build(target, ctx.p, '', 0) if target in graph['nodes'] else None
    node = graph['nodes'].get(target)
    if result is None:
        fld = _zero()
    elif port and port != 'out':
        fld = pick(result, port, node, OPERATORS.get(node['op']))
    else:
        fld = result['field']
    return {'field': fld, 'outs': (result or {}).get('outs'), 'order': order, 'missing': missing,
            'warnings': warnings, 'resamples': counter['resamples']}


def compile_preview_graph(graph, target, ctx, port='out'):
    """A viewport-safe field for a selected output: mask outputs keep their terrain in xyz and carry the selected mask
    in w, so inspecting a mask never replaces the terrain geometry with it. Adds `diagnostic`."""
    spec = _field_output_spec(graph, target, port)
    selected = compile_graph(graph, target, ctx, port)
    if not spec or spec['type'] == 'field':
        return dict(selected, diagnostic=False)
    if spec['type'] != 'mask':
        raise ValueError(f"cannot preview output type '{spec['type']}' as terrain")
    node = graph['nodes'][target]
    ports = ports_of(node['op'])
    wired = inputs_of(graph, target)
    own = next((p for p in ports['outputs'] if p['type'] == 'field'), None)
    field_in = next((p for p in ports['inputs'] if p['type'] == 'field' and wired.get(p['name'])), None)
    if own:
        src = {'node': target, 'port': own['name']}
    elif field_in:
        src = wired[field_in['name']]
    else:
        src = None
    terrain = compile_graph(graph, src['node'], ctx, src.get('port') or 'out')['field'] if src else _zero()
    sel = selected['field']
    return dict(selected, field=Vec(terrain.x, terrain.y, terrain.z, sel.x), diagnostic=True)


# --------------------------------------------------------------------------------------- grid evaluation ---

def grid_positions(nx, ny, tile, rows=None, pad=0, cols=None):
    """p = uv * tile at texel centres, as [row, col] arrays; `rows` = (r0, r1) evaluates a band of rows, `cols`
    = (c0, c1) a window of columns; `pad` adds texels around the band (for screen-space derivatives that read a
    neighbour)."""
    t = Tile.of(tile)
    tx = t.x or 1.0
    ty = t.y or 1.0
    r0, r1 = rows if rows else (0, ny)
    c0, c1 = cols if cols else (0, nx)
    i = np.arange(c0 - pad, c1 + pad, dtype=np.float64)
    j = np.arange(r0 - pad, r1 + pad, dtype=np.float64)
    u = (i + 0.5) / nx * tx
    v = (j + 0.5) / ny * ty
    px, py = np.meshgrid(u, v)
    return Vec(px, py)


def _bcast(a, shape):
    return np.broadcast_to(np.asarray(a, dtype=np.float64), shape).astype(np.float64, copy=True)


def default_workers():
    """Row bands evaluated in parallel threads (numpy releases the GIL inside its array loops)."""
    return max(1, min(8, (os.cpu_count() or 2) // 2))


MAX_DERIVATIVE_DEPTH = 8


def _cores_equal(a, b, pad, shape):
    """The cores (pad stripped) of two compile_graph results over one window of `shape` are identical, field and
    named outputs."""
    def core(v):
        return _bcast(v, shape)[pad:shape[0] - pad, pad:shape[1] - pad]
    for x, y in zip(a['field'].c, b['field'].c):
        if not np.array_equal(core(x), core(y), equal_nan=True):
            return False
    for k, v in (a.get('outs') or {}).items():
        w = (b.get('outs') or {}).get(k)
        if w is None or not np.array_equal(core(v), core(w), equal_nan=True):
            return False
    return True


def derivative_depth(graph, target, port='out', resolution=256, tile=(1.0, 1.0), field_resolution=None,
                     max_depth=MAX_DERIVATIVE_DEPTH, size=8):
    """How deeply screen-space derivatives nest in a graph's evaluation: 0 when it takes none, 1 for a slope mask on
    a plain height, 2 for patternedGround (the gradient of a relief built from the input's gradient) or a slope mask
    after a wave-3 landform under erosion, more when such nodes are chained. One derivative leaves its outermost ring
    one-sided, the next one two rings, and so on; the 'central' mode pads each band by this depth plus one ring of
    margin, so a band is exact and the result does not depend on the banding.

    Measured, not guessed: windows of the real grid (nine spots on a 3 x 3 lattice, size x size texels each) are
    evaluated with every central derivative's one-sided ring overwritten, once by huge values of random sign (they
    flip comparisons both ways) and once by NaN (it survives the clamps and smoothsteps a huge value saturates); the
    depth is the smallest pad at which no window's core changes. Returns max_depth if the graph nests deeper."""
    nx, ny = (resolution, resolution) if np.isscalar(resolution) else (int(resolution[0]), int(resolution[1]))
    t = Tile.of(tile)
    fres = field_resolution or nx
    size = max(2, min(size, nx, ny))
    spots = [(int(fy * (ny - size)), int(fx * (nx - size))) for fy in (1 / 6, 1 / 2, 5 / 6)
             for fx in (1 / 6, 1 / 2, 5 / 6)]
    old = _deriv.set_mode('forbid')
    old_scale = _deriv.set_scale(nx / float(fres), ny / float(fres))
    try:
        try:
            p = grid_positions(nx, ny, t, rows=(spots[0][0], spots[0][0] + size),
                               cols=(spots[0][1], spots[0][1] + size))
            with np.errstate(all='ignore'):
                compile_graph(graph, target, Ctx(p, t, resolution=fres), port)
            return 0                                      # no screen derivative anywhere in the graph
        except _deriv.NeedsGrid:
            pass
        _deriv.set_mode('central')
        for pad in range(1, max_depth + 1):
            leak = False
            for k, (r0, c0) in enumerate(spots):
                p = grid_positions(nx, ny, t, rows=(r0, r0 + size), cols=(c0, c0 + size), pad=pad)
                with np.errstate(all='ignore'):
                    clean = compile_graph(graph, target, Ctx(p, t, resolution=fres), port)
                    for poison in (np.random.default_rng(1009 + 7 * pad + k), 'nan'):
                        old_p = _deriv.set_poison(poison)
                        try:
                            dirty = compile_graph(graph, target, Ctx(p, t, resolution=fres), port)
                        finally:
                            _deriv.set_poison(old_p)
                        if not _cores_equal(clean, dirty, pad, p.x.shape):
                            leak = True
                            break
                if leak:
                    break
            if not leak:
                return pad
        return max_depth
    finally:
        _deriv.set_mode(old)
        _deriv.set_scale(*old_scale)


def evaluate_graph(graph, target, port='out', resolution=256, tile=(1.0, 1.0), derivatives='coarse',
                   field_resolution=None, chunk_rows=None, outs=True, workers=None):
    """Evaluate a graph node over a resolution x resolution grid (or (nx, ny)).

    derivatives  'coarse' (default): the GPU's 2x2 quad derivatives, as Ekigar's own render takes them, so the field
                 is Ekigar's (every parity test runs this mode). 'central': per-texel central differences, smoother
                 slope masks but a different field for the twelve operators that take screen derivatives (slopeMask,
                 angleMask and the ten wave-3 landforms; under an erosion that becomes different heights); each band
                 is padded by the graph's measured derivative_depth plus one ring of margin, so it is exact at every
                 edge. 'fine': per-row / per-column quad differences.
    field_resolution  the resolution the neighbourhood operators measure texels in (Ekigar's ctx.resolution; defaults
                 to the grid width, as in Ekigar where they are the same)
    chunk_rows   rows per band (default: the grid split into one band per worker, at most 1M texels each)
    workers      threads evaluating bands at once (default default_workers(); 1 = serial)

    Every band is the same pointwise evaluation of the graph (quads never straddle a band; central bands carry the
    padding their derivatives consume), so the result does not depend on the banding or the core count.
    Returns dict(height, field (4, ny, nx), outs {name: (ny, nx)}, warnings, order, missing, resamples,
    derivative_pad)."""
    nx, ny = (resolution, resolution) if np.isscalar(resolution) else (int(resolution[0]), int(resolution[1]))
    if derivatives not in ('coarse', 'central', 'fine'):
        raise ValueError(f"evaluate_graph: derivatives {derivatives!r} is 'coarse', 'central' or 'fine'")
    t = Tile.of(tile)
    fres = field_resolution or nx
    workers = default_workers() if workers is None else max(1, int(workers))
    if chunk_rows is None:
        per_worker = -(-ny // workers)
        chunk_rows = min(per_worker, max(16, (1 << 20) // max(1, nx)))
    chunk_rows = max(2, (int(chunk_rows) + 1) & ~1) if chunk_rows < ny else ny
    pad = 0
    if derivatives == 'central':
        depth = derivative_depth(graph, target, port, (nx, ny), t, fres)
        pad = depth + 1 if depth else 0                   # one ring of margin over the measured nesting
    old = _deriv.set_mode(derivatives)
    old_scale = _deriv.set_scale(nx / float(fres), ny / float(fres))
    fld = np.zeros((4, ny, nx))
    out_maps = {}
    metas = {}

    def band(r0):
        r1 = min(ny, r0 + chunk_rows)
        p = grid_positions(nx, ny, t, rows=(r0, r1), pad=pad)
        with np.errstate(all='ignore'):
            res = compile_graph(graph, target, Ctx(p, t, resolution=fres), port)
        shape = p.x.shape
        sl = (slice(pad, shape[0] - pad), slice(pad, shape[1] - pad))
        for c in range(4):
            fld[c, r0:r1] = _bcast(res['field'].c[c], shape)[sl]
        if outs and res.get('outs'):
            for k, v in res['outs'].items():
                arr = out_maps.setdefault(k, np.zeros((ny, nx)))
                arr[r0:r1] = _bcast(v, shape)[sl]
        metas[r0] = res

    starts = list(range(0, ny, chunk_rows))
    try:
        if workers == 1 or len(starts) == 1:
            for r0 in starts:
                band(r0)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(band, starts))
    finally:
        _deriv.set_mode(old)
        _deriv.set_scale(*old_scale)
    meta = metas[0]
    return {'height': fld[0], 'field': fld, 'outs': out_maps, 'warnings': meta['warnings'], 'order': meta['order'],
            'missing': meta['missing'], 'resamples': meta['resamples'], 'resolution': (nx, ny), 'tile': t,
            'derivatives': derivatives, 'derivative_pad': pad}
