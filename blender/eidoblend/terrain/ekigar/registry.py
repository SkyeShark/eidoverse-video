"""Ekigar's operator registry (src/core/registry.js): every operator's declaration, and the port model the graph
wires together.

    OPERATORS[id]            {label, category, doc, params (schema), apply(f, p, ctx), generator?, ...}
    list_operators()         the toolbox: id, label, category, generator, doc (hidden ids excluded)
    get_schema(id) / default_params(id) / structural_params(id)
    ports_of(id)             {inputs: [...], mask: {...} | None, outputs: [...]}
    graph_ports              the adapter model.py's connect()/evaluation_order() take

The operator order is the registry's own, so list_operators() reads like Ekigar's toolbox.
"""
from __future__ import annotations

import copy

from .ops_shared import COMBINE_MODE_VALUES
from . import ops_core, ops_derive, ops_modify, ops_primitive, ops_surface, ops_terrain
from . import landforms_wave1, landforms_wave2, landforms_wave3, landforms_wave4

_ORDER = [
    'constant', 'gradient', 'radialGradient', 'fbm', 'ridged', 'voronoi', 'phacelle', 'thermal', 'snow', 'crater',
    'terrace', 'stratify', 'curves', 'clampOp', 'warp', 'roughen', 'combine',
    'heightMask', 'slopeMask', 'angleMask', 'curvatureMask', 'peaksMask', 'textureBase', 'seamless', 'edgeFade',
    'materialMap', 'surface',
    'invert', 'clip', 'threshold', 'softClip', 'gamma', 'fold', 'blur', 'sharpen', 'median', 'dilate', 'recurve',
    'perlin', 'cellular', 'dotNoise', 'lineNoise', 'cracks', 'shape', 'cone', 'hemisphere', 'pattern',
    'steps', 'fractalTerraces', 'sandstone', 'sand',
    'mountain', 'mountainRange', 'canyon', 'island', 'volcano', 'rugged',
    'math', 'route', 'switchOp', 'compare',
]

_ALL = {}
for _m in (ops_core, ops_derive, ops_modify, ops_primitive, ops_surface, ops_terrain):
    _ALL.update(_m.OPS)

OPERATORS = {k: _ALL[k] for k in _ORDER}
missing = set(_ALL) - set(_ORDER)
if missing:
    raise RuntimeError(f'registry order is missing {sorted(missing)}')
for _wave in (landforms_wave1.WAVE1_LANDFORMS, landforms_wave2.WAVE2_LANDFORMS,
              landforms_wave3.WAVE3_LANDFORMS, landforms_wave4.WAVE4_LANDFORMS):
    OPERATORS.update(_wave)

LANDFORM_IDS = [k for w in (landforms_wave1.WAVE1_LANDFORMS, landforms_wave2.WAVE2_LANDFORMS,
                            landforms_wave3.WAVE3_LANDFORMS, landforms_wave4.WAVE4_LANDFORMS) for k in w]

BLEND_MODES = ['replace', 'add', 'subtract', 'multiply', 'max', 'min']
COMBINE_MODES = COMBINE_MODE_VALUES


def list_operators():
    """Everything the toolbox offers (`hidden` operators, i.e. the legacy `surface` id, excluded)."""
    return [{'id': k, 'label': o['label'], 'category': o['category'], 'generator': bool(o.get('generator')),
             'doc': o.get('doc')} for k, o in OPERATORS.items() if not o.get('hidden')]


def get_schema(op_id):
    o = OPERATORS.get(op_id)
    if o is None:
        raise KeyError(f"unknown operator '{op_id}'")
    return {'id': op_id, 'label': o['label'], 'category': o['category'], 'doc': o.get('doc'),
            'generator': bool(o.get('generator')),
            'params': {k: copy.deepcopy(v) for k, v in o['params'].items()}}


def default_params(op_id):
    return {k: copy.deepcopy(v['default']) for k, v in get_schema(op_id)['params'].items()}


def structural_params(op_id):
    """Parameters whose change rebuilds the shader in Ekigar (loop bounds, lattice periods, branch selectors)."""
    return [k for k, v in get_schema(op_id)['params'].items() if v.get('structural')]


# --------------------------------------------------------------------------------------------- port model ---

CATEGORY_PORTS = {
    'primitive': {'inputs': [], 'mask': False},
    'terrain': {'inputs': ['in'], 'mask': True},
    'modify': {'inputs': ['in'], 'mask': True},
    'surface': {'inputs': ['in'], 'mask': True},
    'simulate': {'inputs': ['in'], 'mask': True},
    'derive': {'inputs': ['in'], 'mask': False},
    'colorize': {'inputs': ['in'], 'mask': False},
    'utility': {'inputs': ['in'], 'mask': True},
    'output': {'inputs': ['in'], 'mask': False},
    'erosion': {'inputs': ['in'], 'mask': True},
    'stamp': {'inputs': ['in'], 'mask': True},
    'remap': {'inputs': ['in'], 'mask': True},
    'warp': {'inputs': ['in'], 'mask': True},
    'combine': {'inputs': ['in', 'in2'], 'mask': True},
}

EXTRA_OUTPUTS = {
    'phacelle': [
        {'name': 'wear', 'type': 'mask', 'doc': 'height removed by the erosion, relative to its strength'},
        {'name': 'ridge', 'type': 'mask', 'doc': 'ridge/crease map from the octave chain'},
        {'name': 'flow', 'type': 'mask', 'doc': 'where the erosion steepened the surface — the gullies it cut'},
    ],
    'thermal': [{'name': 'talus', 'type': 'mask', 'doc': 'material deposited below unstable slopes as talus'}],
    'snow': [{'name': 'depth', 'type': 'mask', 'doc': 'accumulated snow depth'}],
    'crater': [
        {'name': 'rim', 'type': 'mask', 'doc': 'raised rim band'},
        {'name': 'ejecta', 'type': 'mask', 'doc': 'the debris apron outside the rim, fading out over `ejecta` radii'},
    ],
    'voronoi': [{'name': 'cells', 'type': 'mask', 'doc': 'cell distance field'}],
    'canyon': [{'name': 'depth', 'type': 'mask', 'doc': 'how deeply the channel cut here'}],
    'volcano': [
        {'name': 'crater', 'type': 'mask', 'doc': 'inside the summit hollow'},
        {'name': 'rim', 'type': 'mask', 'doc': 'the crater rim crest band'},
        {'name': 'breach', 'type': 'mask', 'doc': 'the outflow gap cut through the rim'},
    ],
    'sandstone': [{'name': 'layers', 'type': 'mask', 'doc': 'position within the current bed, 0 at its base'}],
    'stratify': [{'name': 'layers', 'type': 'mask', 'doc': 'position within the current stratum'}],
    'cellular': [{'name': 'cells', 'type': 'mask', 'doc': 'the selected distance function'}],
    'cracks': [{'name': 'cracks', 'type': 'mask', 'doc': 'crack network coverage'}],
}

PORT_OVERRIDES = {
    'textureBase': {'inputs': [{'name': 'in', 'type': 'field'}, {'name': 'guide', 'type': 'mask'}],
                    'optional': ['guide'], 'mask': False},
    'materialMap': {'inputs': [{'name': 'mask', 'type': 'mask', 'required': True}], 'mask': False,
                    'outputs': [{'name': 'material', 'type': 'material'}]},
    'surface': {'inputs': [{'name': 'mask', 'type': 'mask', 'required': True}], 'mask': False,
                'outputs': [{'name': 'material', 'type': 'material'}]},
    'voronoi': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'roughen': {'inputs': ['in'], 'mask': True},
    'cellular': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'dotNoise': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'lineNoise': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'cracks': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'shape': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'cone': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'hemisphere': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'pattern': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'combine': {'inputs': ['in', 'in2', 'in3'], 'optional': ['in2', 'in3'], 'mask': True},
    'route': {'inputs': ['in1', 'in2', 'in3', 'in4'], 'optional': ['in1', 'in2', 'in3', 'in4'], 'mask': False},
    'switchOp': {'inputs': ['in', 'in2'], 'optional': ['in2'], 'mask': True},
    'compare': {'inputs': ['in', 'in2'], 'optional': ['in2'], 'mask': False},
    'mountain': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'mountainRange': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'island': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'volcano': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'rugged': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
    'canyon': {'inputs': ['in'], 'optional': ['in'], 'mask': True},
}


def ports_of(op_id):
    o = OPERATORS.get(op_id)
    if o is None:
        raise KeyError(f"unknown operator '{op_id}'")
    base = CATEGORY_PORTS.get(o['category'], {'inputs': ['in'], 'mask': True})
    ov = PORT_OVERRIDES.get(op_id, {})
    inputs = ov.get('inputs', base['inputs'])
    mask = ov.get('mask', base['mask'])
    optional = set(ov.get('optional', ['in'] if o.get('optionalInput') else []))
    ins = []
    for inp in inputs:
        spec = {'name': inp, 'type': 'field'} if isinstance(inp, str) else dict(inp)
        spec['required'] = spec['required'] if 'required' in spec else spec['name'] not in optional
        ins.append(spec)
    outputs = ov.get('outputs') or ([{'name': 'out', 'type': 'mask' if o['category'] == 'derive' else 'field'}]
                                    + list(o.get('outputs') or EXTRA_OUTPUTS.get(op_id, [])))
    return {'inputs': ins, 'mask': {'name': 'mask', 'type': 'mask', 'required': False} if mask else None,
            'outputs': outputs}


class _GraphPorts:
    """The interface model.py expects, so the graph never imports operators. An undeclared port has type None, which
    can_connect refuses: a wire to a port that does not exist is rejected, never silently dropped."""

    @staticmethod
    def output_type(op, port):
        p = next((x for x in ports_of(op)['outputs'] if x['name'] == port), None)
        return p['type'] if p else None

    @staticmethod
    def input_type(op, port):
        ports = ports_of(op)
        if port == 'mask' and ports['mask']:
            return ports['mask']['type']
        p = next((x for x in ports['inputs'] if x['name'] == port), None)
        return p['type'] if p else None

    @staticmethod
    def required_inputs(op):
        return [x['name'] for x in ports_of(op)['inputs'] if x['required']]


graph_ports = _GraphPorts()
