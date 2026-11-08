"""A small expression layer over node trees (Geometry Nodes and shaders), so the TSL graphs port as code.

    b = Builder(tree)
    x, y, z = b.sep(b.position())               # scalars (S), one Separate XYZ
    h = b.min(h, b.sqrt(r2 - d2)) + 0.003        # Math nodes, built as the expression is written; constants fold
    v = b.vec(x, y, h)                           # Combine XYZ (V); V + V, V * S are Vector Math
    c = b.lt(progress, start)                    # Compare -> a boolean (Bl); b.switch(c, if_false, if_true)
    b.link(v, set_position.inputs['Position'])

Every helper takes Python numbers too; nodes are laid out in creation order, hidden, so a big graph stays legible.
"""

from __future__ import annotations

import math

import bpy

_FOLD = {
    'ADD': lambda a, b: a + b, 'SUBTRACT': lambda a, b: a - b, 'MULTIPLY': lambda a, b: a * b,
    'DIVIDE': lambda a, b: a / b if b else 0.0, 'MINIMUM': min, 'MAXIMUM': max,
    'POWER': lambda a, b: a ** b if a > 0 or float(b).is_integer() else 0.0,
    'SQRT': lambda a: math.sqrt(max(a, 0.0)), 'ABSOLUTE': abs, 'SINE': math.sin, 'COSINE': math.cos,
    'FLOOR': lambda a: float(math.floor(a)), 'FRACT': lambda a: a - math.floor(a), 'EXPONENT': math.exp,
}


class S:
    """A scalar: a Python float (folded) or an output socket."""
    __slots__ = ('b', 'v')

    def __init__(self, b, v):
        self.b, self.v = b, v

    def _op(self, op, o, rev=False):
        return self.b.math(op, o, self) if rev else self.b.math(op, self, o)

    def __add__(self, o): return self._op('ADD', o)
    def __radd__(self, o): return self._op('ADD', o, True)
    def __sub__(self, o): return self._op('SUBTRACT', o)
    def __rsub__(self, o): return self._op('SUBTRACT', o, True)
    def __mul__(self, o):
        if isinstance(o, V):
            return o * self
        return self._op('MULTIPLY', o)
    def __rmul__(self, o): return self._op('MULTIPLY', o, True)
    def __truediv__(self, o): return self._op('DIVIDE', o)
    def __rtruediv__(self, o): return self._op('DIVIDE', o, True)
    def __neg__(self): return self.b.math('MULTIPLY', self, -1.0)


class V:
    """A vector socket."""
    __slots__ = ('b', 'v')

    def __init__(self, b, v):
        self.b, self.v = b, v

    def _op(self, op, o, rev=False):
        return self.b.vmath(op, o, self) if rev else self.b.vmath(op, self, o)

    def __add__(self, o): return self._op('ADD', o)
    def __radd__(self, o): return self._op('ADD', o, True)
    def __sub__(self, o): return self._op('SUBTRACT', o)
    def __rsub__(self, o): return self._op('SUBTRACT', o, True)
    def __mul__(self, o):
        if isinstance(o, (int, float, S)):
            return self.b.vscale(self, o)
        return self._op('MULTIPLY', o)
    __rmul__ = __mul__
    def __neg__(self): return self.b.vscale(self, -1.0)


class Bl:
    """A boolean socket."""
    __slots__ = ('b', 'v')

    def __init__(self, b, v):
        self.b, self.v = b, v

    def __and__(self, o): return self.b.boolean('AND', self, o)
    def __or__(self, o): return self.b.boolean('OR', self, o)
    def __invert__(self): return self.b.boolean('NOT', self)


class Builder:
    def __init__(self, tree, x0=-1600, y0=700):
        self.tree = tree
        self.nodes = tree.nodes
        self.links = tree.links
        self.count = 0
        self.x0, self.y0 = x0, y0
        self.geo = tree.bl_idname == 'GeometryNodeTree'

    def node(self, kind, **props):
        n = self.nodes.new(kind)
        col, row = divmod(self.count, 30)
        n.location = (self.x0 + col * 180, self.y0 - row * 40)
        n.hide = True
        self.count += 1
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, src, dst):
        if isinstance(src, (S, V, Bl)):
            src = src.v
        if isinstance(src, bool):
            dst.default_value = src
            return
        if isinstance(src, (int, float)):
            dst.default_value = float(src) if not isinstance(dst.default_value, int) else int(src)
            return
        if isinstance(src, (tuple, list)):
            dst.default_value = tuple(float(x) for x in src)
            return
        self.links.new(src, dst)

    # scalars -------------------------------------------------------------------------------------------------
    def s(self, x):
        return x if isinstance(x, S) else S(self, x)

    def math(self, op, a, b=None, c=None):
        args = [x for x in (a, b, c) if x is not None]
        vals = [x.v if isinstance(x, S) else x for x in args]
        if op in _FOLD and all(isinstance(v, (int, float)) for v in vals):
            return S(self, float(_FOLD[op](*vals)))
        n = self.node('ShaderNodeMath', operation=op)
        for i, v in enumerate(vals):
            self.link(v, n.inputs[i])
        return S(self, n.outputs[0])

    def min(self, a, b): return self.math('MINIMUM', a, b)
    def max(self, a, b): return self.math('MAXIMUM', a, b)
    def sqrt(self, a): return self.math('SQRT', a)
    def abs(self, a): return self.math('ABSOLUTE', a)
    def sin(self, a): return self.math('SINE', a)
    def cos(self, a): return self.math('COSINE', a)
    def floor(self, a): return self.math('FLOOR', a)
    def fract(self, a): return self.math('FRACT', a)
    def exp(self, a): return self.math('EXPONENT', a)
    def pow(self, a, b): return self.math('POWER', a, b)
    def mod(self, a, b): return self.math('FLOORED_MODULO', a, b)

    def clamp(self, a, lo=0.0, hi=1.0):
        return self.min(self.max(a, lo), hi)

    def mix(self, a, b, t):
        return a + (b - a) * t

    # vectors -------------------------------------------------------------------------------------------------
    def vec(self, x, y=None, z=None):
        if y is None and isinstance(x, (V,)):
            return x
        if y is None:
            return V(self, x)
        n = self.node('ShaderNodeCombineXYZ')
        for i, c in enumerate((x, y, z)):
            self.link(c, n.inputs[i])
        return V(self, n.outputs[0])

    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self.link(v, n.inputs[0])
        return S(self, n.outputs[0]), S(self, n.outputs[1]), S(self, n.outputs[2])

    def vmath(self, op, a, b=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.link(a, n.inputs[0])
        if b is not None:
            self.link(b, n.inputs[1])
        if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE'):
            return S(self, n.outputs['Value'])
        return V(self, n.outputs['Vector'])

    def vscale(self, a, k):
        n = self.node('ShaderNodeVectorMath', operation='SCALE')
        self.link(a, n.inputs[0])
        self.link(k, n.inputs['Scale'])
        return V(self, n.outputs['Vector'])

    def dot(self, a, b): return self.vmath('DOT_PRODUCT', a, b)
    def cross(self, a, b): return self.vmath('CROSS_PRODUCT', a, b)
    def normalize(self, a): return self.vmath('NORMALIZE', a)
    def length(self, a): return self.vmath('LENGTH', a)

    def vmix(self, a, b, t):
        return a + (b - a) * t

    # comparisons and choices (Geometry Nodes) ----------------------------------------------------------------
    def compare(self, op, a, b, data_type='FLOAT'):
        n = self.node('FunctionNodeCompare', data_type=data_type, operation=op)
        ins = [s for s in n.inputs if s.enabled]
        self.link(a, ins[0])
        self.link(b, ins[1])
        return Bl(self, n.outputs[0])

    def lt(self, a, b): return self.compare('LESS_THAN', a, b)
    def le(self, a, b): return self.compare('LESS_EQUAL', a, b)
    def gt(self, a, b): return self.compare('GREATER_THAN', a, b)
    def ge(self, a, b): return self.compare('GREATER_EQUAL', a, b)

    def boolean(self, op, a, b=None):
        n = self.node('FunctionNodeBooleanMath', operation=op)
        self.link(a, n.inputs[0])
        if b is not None:
            self.link(b, n.inputs[1])
        return Bl(self, n.outputs[0])

    def switch(self, cond, if_false, if_true, kind='FLOAT'):
        n = self.node('GeometryNodeSwitch', input_type=kind)
        self.link(cond, n.inputs['Switch'])
        self.link(if_false, n.inputs['False'])
        self.link(if_true, n.inputs['True'])
        out = n.outputs[0]
        return V(self, out) if kind == 'VECTOR' else Bl(self, out) if kind == 'BOOLEAN' else S(self, out)

    def select(self, cond, if_true, if_false, kind='FLOAT'):
        return self.switch(cond, if_false, if_true, kind)

    # geometry inputs -----------------------------------------------------------------------------------------
    def position(self):
        return V(self, self.node('GeometryNodeInputPosition').outputs[0])

    def index(self):
        return S(self, self.node('GeometryNodeInputIndex').outputs[0])

    def named(self, name, data_type='FLOAT'):
        n = self.node('GeometryNodeInputNamedAttribute', data_type=data_type)
        n.inputs['Name'].default_value = name
        out = n.outputs['Attribute']
        return V(self, out) if data_type == 'FLOAT_VECTOR' else Bl(self, out) if data_type == 'BOOLEAN' else S(self, out)

    def sample_index(self, geometry, value, index, data_type='FLOAT', domain='POINT', clamp=True):
        n = self.node('GeometryNodeSampleIndex', data_type=data_type, domain=domain, clamp=clamp)
        self.link(geometry, n.inputs['Geometry'])
        self.link(value, n.inputs['Value'])
        self.link(index, n.inputs['Index'])
        out = n.outputs[0]
        return V(self, out) if data_type == 'FLOAT_VECTOR' else S(self, out)

    def object_geometry(self, ob, relative=False):
        n = self.node('GeometryNodeObjectInfo', transform_space='RELATIVE' if relative else 'ORIGINAL')
        n.inputs['Object'].default_value = ob
        return n.outputs['Geometry']

    def value(self, v, label=None):
        n = self.node('ShaderNodeValue')
        n.outputs[0].default_value = float(v)
        if label:
            n.name = n.label = label
            n.hide = False
        return S(self, n.outputs[0])


def new_tree(name, kind='GeometryNodeTree', inputs=(), outputs=()):
    """A fresh node group with typed interface sockets: (tree, group input node, group output node)."""
    tree = bpy.data.node_groups.new(name, kind)
    for n, t in inputs:
        tree.interface.new_socket(n, in_out='INPUT', socket_type=t)
    for n, t in outputs:
        tree.interface.new_socket(n, in_out='OUTPUT', socket_type=t)
    gi = tree.nodes.new('NodeGroupInput')
    go = tree.nodes.new('NodeGroupOutput')
    gi.location = (-1900, 0)
    go.location = (1600, 0)
    return tree, gi, go


def modifier_input(mod, name):
    """The input slot of a nodes modifier by its interface name (Blender 5.2 keeps the value at
    mod.properties.inputs.<identifier>.value, keyable like any property)."""
    for item in mod.node_group.interface.items_tree:
        if getattr(item, 'in_out', None) == 'INPUT' and item.name == name:
            return getattr(mod.properties.inputs, item.identifier)
    raise KeyError(name)


def set_modifier_input(mod, name, value):
    slot = modifier_input(mod, name)
    slot.value = value
    return slot
