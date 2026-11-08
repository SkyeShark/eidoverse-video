"""The headless agent API of the Ekigar plan (section 11), over the port: the same registry, compiler and evaluator
the generator runs, so an agent and a human see one definition of every knob.

    list_operators() / get_schema(op) / describe(op) / default_params(op)
    default_project()                      an ekigar-project/3 dict: fBm under Phacelle erosion
    validate(project)                      {'ok', 'notes'}: unknown operators, missing inputs, bad wires, cycles
    tiling_report(project)                 {'tiling', 'notes'}: every lattice snap the compiler will make
    evaluate(project, resolution=...)      a Heightfield (terrain.generate)
    point_field(project)                   the design tier's field: evaluate(x, y) and gradient_fd at any points
    stats_of(heightfield)                  height range, slope histogram, non-finite count
    to_project(graph, ...) / from_project(doc)
    bake(project, out_dir, ...)            heightmap + map set + sidecar files (export.py)
"""
from __future__ import annotations

import numpy as np

from . import model as _model
from .registry import OPERATORS, list_operators, get_schema, default_params, ports_of, graph_ports
from .compile import evaluate_graph
from .terrain import (generate as evaluate, stats_of, make_project as to_project, load_project, project_graph,
                      terminal_node)
from .examples import default_project_graph
from . import export as _export


def describe(op_id):
    """A plain-text account of one operator: what it does, its ports and every parameter with range and doc."""
    s = get_schema(op_id)
    p = ports_of(op_id)
    lines = [f"{s['label']} ({op_id}, {s['category']}{', generator' if s['generator'] else ''})", s['doc'] or '']
    ins = ', '.join(f"{i['name']}:{i['type']}{'' if i['required'] else '?'}" for i in p['inputs']) or 'none'
    outs = ', '.join(f"{o['name']}:{o['type']}" for o in p['outputs'])
    lines.append(f"inputs {ins}{'; mask' if p['mask'] else ''}; outputs {outs}")
    for k, v in s['params'].items():
        rng = f" [{v.get('min')}..{v.get('max')}]" if 'min' in v else (f" {v.get('values')}" if 'values' in v else '')
        flags = ' structural' if v.get('structural') else ''
        doc = f" — {v['doc']}" if v.get('doc') else ''
        lines.append(f"  {k}: {v['type']} = {v['default']}{rng}{flags}{doc}")
    return '\n'.join(lines)


def default_project():
    g, t = default_project_graph()
    return to_project(g, target=t)


def from_project(doc):
    """(graph, project) from an ekigar-project document, migrated to format 3."""
    project, _w = load_project(doc)
    return project_graph(project), project


def validate(project):
    """Check a project without evaluating it at full size: unknown operators, wires to undeclared ports or of the
    wrong type, cycles, required inputs left unwired. Returns {'ok', 'notes'}."""
    notes = []
    graph, proj = from_project(project)
    for n in graph['nodes'].values():
        if n['op'] not in OPERATORS:
            notes.append(f"node {n['id']}: unknown operator '{n['op']}'")
    for e in graph['edges'].values():
        a, b = graph['nodes'].get(e['from']['node']), graph['nodes'].get(e['to']['node'])
        if not a or not b:
            notes.append(f"edge {e['id']}: endpoint missing")
            continue
        if a['op'] not in OPERATORS or b['op'] not in OPERATORS:
            continue
        ot = graph_ports.output_type(a['op'], e['from'].get('port'))
        it = graph_ports.input_type(b['op'], e['to'].get('port'))
        if not _model.can_connect(ot, it):
            notes.append(f"edge {a['id']}.{e['from'].get('port')} -> {b['id']}.{e['to'].get('port')}: "
                         f"{ot} cannot drive {it}")
    target = proj.get('target') if proj.get('target') in graph['nodes'] else terminal_node(graph)
    if target and not any('unknown operator' in x for x in notes):
        try:
            order, missing = _model.evaluation_order(graph, target, graph_ports)
            for m in missing:
                notes.append(f"node {m['node']}: required input '{m['port']}' is not connected")
        except ValueError as ex:
            notes.append(str(ex))
    return {'ok': not notes, 'notes': notes}


def tiling_report(project, probe_resolution=8):
    """Every lattice snap the compiler makes for this project's tile, and non-integral lacunarity, as notes."""
    graph, proj = from_project(project)
    tile = proj.get('tile') or {'x': 1, 'y': 1}
    if not (tile.get('x', 0) > 0 or tile.get('y', 0) > 0):
        return {'tiling': False, 'notes': ['not periodic on either axis']}
    notes = []
    for n in graph['nodes'].values():
        lac = (n.get('params') or {}).get('lacunarity')
        if lac is not None and not float(lac).is_integer():
            notes.append(f"{n['id']}: lacunarity {lac} is not an integer — octaves above the first cannot tile")
    target = proj.get('target') if proj.get('target') in graph['nodes'] else terminal_node(graph)
    if target:
        res = evaluate_graph(graph, target, resolution=probe_resolution, tile=tile, workers=1)
        notes += list(dict.fromkeys(w for w in res['warnings'] if 'snapped' in w))   # once each (see generate)
    return {'tiling': True, 'notes': notes}


class PointField:
    """The plan's design-tier field: a graph evaluated at any points, no grid (section 11's evaluate(x, y) and
    gradientFD). Positions are Ekigar's p = uv * tile (0..1 across a unit tile); metres() converts Blender metres on
    a tile of world_size. Graphs that take screen-space derivatives need a grid and raise _deriv.NeedsGrid."""

    def __init__(self, graph, target, port='out', tile=(1.0, 1.0), resolution=512):
        self.graph, self.target, self.port = graph, target, port
        self.tile = tile
        self.resolution = resolution

    def evaluate(self, x, y):
        """{'height', 'dx', 'dy', 'aux', 'outs'} at points (arrays broadcast), dx/dy the carried gradient per tile
        unit (approximate under erosion: use gradient_fd for masks)."""
        from .compile import compile_graph, Ctx
        from ._tsl import Vec
        from . import _deriv
        px, py = np.broadcast_arrays(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64))
        old = _deriv.set_mode('forbid')
        try:
            with np.errstate(all='ignore'):
                r = compile_graph(self.graph, self.target, Ctx(Vec(px.copy(), py.copy()), self.tile,
                                                               resolution=self.resolution), self.port)
        finally:
            _deriv.set_mode(old)
        f = r['field']
        shape = px.shape
        b = lambda a: np.broadcast_to(np.asarray(a, dtype=np.float64), shape).copy()  # noqa: E731
        return {'height': b(f.x), 'dx': b(f.y), 'dy': b(f.z), 'aux': b(f.w),
                'outs': {k: b(v) for k, v in (r.get('outs') or {}).items()}}

    def gradient_fd(self, x, y, h=None):
        """Slope from central differences of the final height (what masks key off): {dx, dy, slope, aspect}."""
        from .field_cpu import gradient_fd
        return gradient_fd(self, np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64), h)

    @staticmethod
    def metres(x, y, world_size, tile=(1.0, 1.0)):
        """Blender metres on a tile of world_size centred on the origin -> Ekigar's p."""
        t = tile if isinstance(tile, (tuple, list)) else (tile, tile)
        return ((np.asarray(x) / world_size + 0.5) * (t[0] or 1.0), (np.asarray(y) / world_size + 0.5) * (t[1] or 1.0))


def point_field(project, target=None, port=None):
    """A PointField over a project (dict, path, JSON) or a graph: the plan's evaluate(project)."""
    if isinstance(project, dict) and 'nodes' in project and isinstance(project['nodes'], dict):
        graph, proj = project, {}
    else:
        graph, proj = from_project(project)
    tgt = target or (proj.get('target') if proj.get('target') in graph['nodes'] else terminal_node(graph))
    tile = proj.get('tile') or {'x': 1, 'y': 1}
    return PointField(graph, tgt, port or (proj.get('targetPort') if tgt == proj.get('target') else None) or 'out',
                      (tile.get('x', 1), tile.get('y', 1)), proj.get('res') or 512)


def bake(project, out_dir, resolution=None, world_size=None, vertical_scale=0.3, formats=('png16', 'r32'),
         green='ekigar'):
    """Evaluate and write the deliverables: <out_dir>/ekigar_height.{png,r32,json} (heightmap.js) and the
    ekigar_*.png map set with terrain.json (bake.js). Returns {'heightfield', 'heightmap', 'maps'}."""
    hf = evaluate(project, resolution=resolution, world_size=world_size, vertical_scale=vertical_scale)
    graph_json = hf.meta.get('graph')
    hm = _export.export_heightmap(hf.height, out_dir, formats=formats, world_size=hf.world_size,
                                  vertical_scale=hf.vertical_scale)
    maps = _export.export_maps(hf.height, hf.aux, out_dir, world_size=hf.world_size,
                               vertical_scale=hf.vertical_scale, tile=hf.tile, stack=graph_json, green=green)
    return {'heightfield': hf, 'heightmap': hm, 'maps': maps}


__all__ = ['list_operators', 'get_schema', 'describe', 'default_params', 'default_project', 'validate',
           'tiling_report', 'evaluate', 'point_field', 'PointField', 'stats_of', 'to_project', 'from_project', 'bake']
