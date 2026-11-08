"""Ekigar's example scenes: the operator gallery its visual-regression suite renders (test/gpu/visual_regression.mjs
buildOperatorGraph), every operator on the fixture it is judged on, with the same camera and light.

    graph, target, fixture = operator_example('caldera')
    for op, graph, target, fixture in gallery(): ...
    EXAMPLES['reference']()          # the shared detailed fixture alone

Fixtures: primitives stand alone; terrain landforms marked visualFixture sit on a 'smooth' fBm, a 'slope' or 'coast'
gradient, or the 'detailed-base' fixture; optional-input landforms stand alone; required-input ones get a flat plane;
every filter gets the detailed-base fixture (fBm 4 / amplitude 0.9 / 4 octaves under a roughen of 16 / 0.04).

GALLERY_VIEW is the suite's camera and light in Ekigar's unit-tile frame (three.js, Y up); render_gallery.py in the
tests turns it into a Blender camera and sun.
"""
from __future__ import annotations

import math

from . import model as _model
from .registry import OPERATORS, ports_of, default_params, graph_ports

GALLERY_VIEW = {
    'vertical_scale': 0.30, 'field_resolution': 256, 'image': (480, 360),
    'camera': {'azimuth_deg': 42, 'elevation_deg': 36, 'distance': 1.38, 'fov_deg': 40, 'look': (0, 0, 0)},
    'sun': {'position_three': (-0.7, 0.6, -0.45), 'colour': '#fff0dc', 'intensity': 3.1},
    'hemisphere': {'sky': '#9fb3c8', 'ground': '#2b2118', 'intensity': 0.5},
    'background': '#0b0f14', 'tone_mapping': 'ACES filmic',
    'terrain_centred': 'the mesh is lowered by the mid height so the camera frames every operator alike',
}


def _P(op, **over):
    d = default_params(op)
    d.update(over)
    return d


def _wire(graph, frm, to, port='in'):
    r = _model.connect(graph, {'node': frm, 'port': 'out'}, {'node': to, 'port': port}, graph_ports)
    if not r['ok']:
        raise ValueError(f'cannot wire {port}: {r["reason"]}')


def add_base_fixture(graph):
    """The shared detailed fixture: fBm (frequency 4, amplitude 0.9, 4 octaves) under a roughen (16, 0.04)."""
    broad = _model.add_node(graph, 'fbm', {'x': 0, 'y': 0}, _P('fbm', frequency=4, amplitude=0.9, octaves=4))
    detail = _model.add_node(graph, 'roughen', {'x': 1, 'y': 0}, _P('roughen', frequency=16, amplitude=0.04))
    _wire(graph, broad, detail)
    return detail


def add_smooth_fixture(graph):
    return _model.add_node(graph, 'fbm', {'x': 0, 'y': 0}, _P('fbm', frequency=3, amplitude=0.55, octaves=3))


def operator_example(op_id, params=None):
    """The gallery scene for one operator: (graph, target, fixture name)."""
    spec = OPERATORS[op_id]
    ports = ports_of(op_id)
    graph = _model.create_graph()
    node = _model.add_node(graph, op_id, {'x': 3, 'y': 0}, dict(_P(op_id), **(params or {})))
    if spec['category'] == 'primitive':
        return graph, node, 'standalone'
    primary = ports['inputs'][0] if ports['inputs'] else None
    vf = spec.get('visualFixture')
    if spec['category'] == 'terrain' and primary:
        if vf == 'smooth':
            _wire(graph, add_smooth_fixture(graph), node, primary['name'])
            return graph, node, 'smooth'
        if vf == 'slope':
            s = _model.add_node(graph, 'gradient', {'x': 0, 'y': 0}, _P('gradient', angle=math.pi / 4, scale=-0.35))
            _wire(graph, s, node, primary['name'])
            return graph, node, 'slope'
        if vf == 'coast':
            c = _model.add_node(graph, 'gradient', {'x': 0, 'y': 0}, _P('gradient', angle=0, scale=-0.6))
            _wire(graph, c, node, primary['name'])
            return graph, node, 'coast'
        if vf == 'detailed-base':
            _wire(graph, add_base_fixture(graph), node, primary['name'])
            return graph, node, 'detailed-base'
        if not primary['required'] and op_id != 'rugged':
            return graph, node, 'standalone'
        if primary['required']:
            flat = _model.add_node(graph, 'constant', {'x': 0, 'y': 0}, _P('constant', value=0))
            _wire(graph, flat, node, primary['name'])
            return graph, node, 'flat'
    source = add_base_fixture(graph)
    if primary:
        _wire(graph, source, node, primary['name'])
    for port in ports['inputs'][1:]:
        if port['required']:
            _wire(graph, add_base_fixture(graph), node, port['name'])
    return graph, node, 'detailed-base'


def fixture_graph():
    """The reference fixture on its own (the gallery's 00 image)."""
    graph = _model.create_graph()
    return graph, add_base_fixture(graph), 'reference'


def gallery_ids():
    """Every operator the gallery renders: all but the hidden legacy id and the material (colorize) node."""
    return [k for k, o in OPERATORS.items() if not o.get('hidden') and o['category'] != 'colorize']


def gallery():
    out = []
    for op in gallery_ids():
        g, t, fx = operator_example(op)
        out.append((op, g, t, fx))
    return out


def default_project_graph():
    """The starter terrain: fBm under Phacelle erosion (the M0 base field as a graph). Returns (graph, target)."""
    g = _model.create_graph()
    a = _model.add_node(g, 'fbm', {'x': 0, 'y': 0}, _P('fbm'))
    b = _model.add_node(g, 'phacelle', {'x': 1, 'y': 0}, _P('phacelle'))
    _wire(g, a, b)
    return g, b


EXAMPLES = {'reference': fixture_graph, 'default': default_project_graph}
for _op in gallery_ids():
    EXAMPLES[_op] = (lambda op=_op: operator_example(op))
