"""ocean/_nodes.py: TSL as code, for both Geometry Nodes and shader node trees.

The ocean's shaders are long analytic formulas (Gerstner swells, a log-polar face layout, fifteen Gaussians of
relief and their gradient, glints). Written as scalar expressions here, one Python function builds the same graph in
a Geometry Nodes tree (the vertex stage: displacement) and in a material (the fragment stage: colour), the way the
WebGPU edition shares its TSL between positionNode and colorNode.

    nb = NB(tree)                                  # a ShaderNodeTree or a GeometryNodeTree (or a group's tree)
    x, y = nb.s(sock_x), nb.s(sock_y)              # scalars (E): numbers fold in Python, sockets become Math nodes
    r = nb.sqrt(x * x + y * y)
    nb.link(r * 0.5, some_node.inputs[0])

Vectors are tuples of scalars (vec3 helpers below), so a graph is plain Math nodes plus a few texture reads.
"""

from __future__ import annotations

import math

import bpy

_FOLD = {
    'ADD': lambda a, b: a + b, 'SUBTRACT': lambda a, b: a - b, 'MULTIPLY': lambda a, b: a * b,
    'DIVIDE': lambda a, b: a / b if b != 0 else 0.0, 'POWER': lambda a, b: (a ** b) if (a > 0 or float(b).is_integer()) else 0.0,
    'MINIMUM': min, 'MAXIMUM': max, 'ARCTAN2': math.atan2,
    'LESS_THAN': lambda a, b: 1.0 if a < b else 0.0, 'GREATER_THAN': lambda a, b: 1.0 if a > b else 0.0,
    'LOGARITHM': lambda a, b: math.log(a) / math.log(b) if a > 0 else 0.0,
}
_FOLD1 = {
    'SINE': math.sin, 'COSINE': math.cos, 'EXPONENT': math.exp, 'SQRT': lambda a: math.sqrt(max(a, 0.0)),
    'ABSOLUTE': abs, 'FLOOR': lambda a: float(math.floor(a)), 'FRACT': lambda a: a - math.floor(a),
    'SIGN': lambda a: (a > 0) - (a < 0), 'ARCSINE': lambda a: math.asin(max(-1.0, min(1.0, a))),
}


class E:
    """A scalar in a node tree: a Python float (folded) or an output socket."""

    __slots__ = ('nb', 'v')

    def __init__(self, nb, v):
        self.nb = nb
        self.v = v

    @property
    def const(self):
        return isinstance(self.v, (int, float))

    def __add__(self, o): return self.nb.math('ADD', self, o)
    def __radd__(self, o): return self.nb.math('ADD', o, self)
    def __sub__(self, o): return self.nb.math('SUBTRACT', self, o)
    def __rsub__(self, o): return self.nb.math('SUBTRACT', o, self)
    def __mul__(self, o): return self.nb.math('MULTIPLY', self, o)
    def __rmul__(self, o): return self.nb.math('MULTIPLY', o, self)
    def __truediv__(self, o): return self.nb.math('DIVIDE', self, o)
    def __rtruediv__(self, o): return self.nb.math('DIVIDE', o, self)
    def __neg__(self): return self.nb.math('MULTIPLY', self, -1.0)


def _val(x):
    return x.v if isinstance(x, E) else x


class NB:
    """A node builder over one tree. Shader trees and Geometry Nodes trees share the Math / Combine / Separate /
    texture nodes, so one expression builds in either."""

    def __init__(self, tree, x0=-2400, y0=1400, rows=40):
        self.tree = tree
        self.gn = tree.bl_idname == 'GeometryNodeTree'
        self.count = 0
        self.x0, self.y0, self.rows = x0, y0, rows
        self._cache = {}

    # ------------------------------------------------------------------------------------------- plumbing
    def node(self, kind, **props):
        n = self.tree.nodes.new(kind)
        col, row = divmod(self.count, self.rows)
        n.location = (self.x0 + col * 170, self.y0 - row * 40)
        n.hide = True
        self.count += 1
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, src, dst):
        src = _val(src)
        if isinstance(src, (int, float)):
            dst.default_value = float(src)
            return
        if isinstance(src, (tuple, list)):
            vals = [_val(c) for c in src]
            if all(isinstance(c, (int, float)) for c in vals):
                n = len(dst.default_value)
                vv = list(vals)[:n] + [1.0] * max(0, n - len(vals))
                dst.default_value = vv
                return
            src = self.combine(*src)
            src = src.v if isinstance(src, E) else src
        self.tree.links.new(src, dst)

    def s(self, x):
        return x if isinstance(x, E) else E(self, x)

    def value(self, v, label=None):
        n = self.node('ShaderNodeValue')
        n.outputs[0].default_value = float(v)
        if label:
            n.label = n.name = label
            n.hide = False
        return E(self, n.outputs[0])

    def driven(self, label, source, data_path, default=0.0, expr='x'):
        """A Value node driven by source.<data_path> (e.g. '["porch"]' on an object): a uniform that follows a keyed
        custom property. (Attribute (Object) nodes would read it too, but a material holds only a few of those.)"""
        e = self.value(default, label=label)
        fc = self.tree.driver_add(f'nodes["{label}"].outputs[0].default_value')
        d = fc.driver
        d.type = 'SCRIPTED'
        for old in list(d.variables):
            d.variables.remove(old)
        var = d.variables.new()
        var.name = 'x'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = source
        var.targets[0].data_path = data_path
        d.expression = expr
        return e

    # ------------------------------------------------------------------------------------------- scalar maths
    def math(self, op, a, b=None, c=None):
        args = [x for x in (a, b, c) if x is not None]
        vals = [_val(x) for x in args]
        if all(isinstance(v, (int, float)) for v in vals):
            if len(vals) == 1 and op in _FOLD1:
                return E(self, float(_FOLD1[op](vals[0])))
            if len(vals) == 2 and op in _FOLD:
                return E(self, float(_FOLD[op](vals[0], vals[1])))
        # algebraic shortcuts that keep graphs small
        if op == 'MULTIPLY' and len(vals) == 2:
            for i, v in enumerate(vals):
                if isinstance(v, (int, float)):
                    if v == 1.0:
                        return self.s(args[1 - i])
                    if v == 0.0:
                        return E(self, 0.0)
        if op == 'ADD' and len(vals) == 2:
            for i, v in enumerate(vals):
                if isinstance(v, (int, float)) and v == 0.0:
                    return self.s(args[1 - i])
        if op == 'SUBTRACT' and len(vals) == 2 and isinstance(vals[1], (int, float)) and vals[1] == 0.0:
            return self.s(args[0])
        if op == 'DIVIDE' and len(vals) == 2 and isinstance(vals[1], (int, float)) and vals[1] != 0.0:
            if vals[1] == 1.0:
                return self.s(args[0])
            return self.math('MULTIPLY', args[0], 1.0 / vals[1])
        n = self.node('ShaderNodeMath', operation=op)
        for i, v in enumerate(vals):
            self.link(v, n.inputs[i])
        return E(self, n.outputs[0])

    def sin(self, a): return self.math('SINE', a)
    def cos(self, a): return self.math('COSINE', a)
    def exp(self, a): return self.math('EXPONENT', a)
    def sqrt(self, a): return self.math('SQRT', a)
    def abs(self, a): return self.math('ABSOLUTE', a)
    def floor(self, a): return self.math('FLOOR', a)
    def fract(self, a): return self.math('FRACT', a)
    def min(self, a, b): return self.math('MINIMUM', a, b)
    def max(self, a, b): return self.math('MAXIMUM', a, b)
    def pow(self, a, b): return self.math('POWER', a, b)
    def atan2(self, y, x): return self.math('ARCTAN2', y, x)
    def asin(self, a): return self.math('ARCSINE', a)

    def log(self, a):
        """natural log"""
        return self.math('LOGARITHM', a, math.e)

    def step(self, edge, x):
        """GLSL step(edge, x) = x >= edge ? 1 : 0"""
        return 1.0 - self.math('LESS_THAN', x, edge)

    def lt(self, a, b):
        return self.math('LESS_THAN', a, b)

    def gt(self, a, b):
        return self.math('GREATER_THAN', a, b)

    def clamp(self, a, lo=0.0, hi=1.0):
        return self.min(self.max(a, lo), hi)

    def mix(self, a, b, t):
        if isinstance(a, tuple):
            return tuple(self.mix(a[i], b[i] if isinstance(b, tuple) else b, t) for i in range(len(a)))
        if isinstance(b, tuple):
            return tuple(self.mix(a, b[i], t) for i in range(len(b)))
        return self.s(a) + (self.s(b) - a) * t

    def smoothstep(self, e0, e1, x):
        """WGSL smoothstep (well-defined for e0 > e1 too, as TSL uses it)"""
        t = self.clamp((self.s(x) - e0) / (e1 - e0))
        return t * t * (3.0 - 2.0 * t)

    # ------------------------------------------------------------------------------------------- vec3 tuples
    def combine(self, x, y, z=0.0):
        n = self.node('ShaderNodeCombineXYZ')
        for i, c in enumerate((x, y, z)):
            self.link(c, n.inputs[i])
        return n.outputs[0]

    def separate(self, sock):
        n = self.node('ShaderNodeSeparateXYZ')
        self.link(sock, n.inputs[0])
        return tuple(E(self, n.outputs[i]) for i in range(3))

    @staticmethod
    def vadd(a, b): return tuple(a[i] + b[i] for i in range(len(a)))

    @staticmethod
    def vsub(a, b): return tuple(a[i] - b[i] for i in range(len(a)))

    @staticmethod
    def vscale(a, k): return tuple(a[i] * k for i in range(len(a)))

    @staticmethod
    def vmul(a, b): return tuple(a[i] * b[i] for i in range(len(a)))

    def vdot(self, a, b):
        acc = a[0] * b[0]
        for i in range(1, len(a)):
            acc = acc + a[i] * b[i]
        return self.s(acc)

    def vlen(self, a):
        return self.sqrt(self.vdot(a, a))

    def vnorm(self, a):
        k = 1.0 / self.max(self.vlen(a), 1e-12)
        return tuple(c * k for c in a)

    # ------------------------------------------------------------------------------------------- inputs
    def attr(self, name, kind='GEOMETRY', out='Fac'):
        """A named attribute: shader Attribute node (GEOMETRY / OBJECT custom property / INSTANCER) or, in Geometry
        Nodes, a Named Attribute (float / vector). out 'Fac' -> scalar, 'Vector' -> tuple of 3."""
        key = ('attr', name, kind, out)
        if key in self._cache:
            return self._cache[key]
        if self.gn:
            n = self.node('GeometryNodeInputNamedAttribute', data_type='FLOAT_VECTOR' if out == 'Vector' else 'FLOAT')
            n.inputs['Name'].default_value = name
            sock = n.outputs['Attribute']
        else:
            n = self.node('ShaderNodeAttribute', attribute_type=kind, attribute_name=name)
            sock = n.outputs['Vector' if out == 'Vector' else 'Fac']
        res = self.separate(sock) if out == 'Vector' else E(self, sock)
        self._cache[key] = res
        return res

    def image(self, img, u, v, interpolation='Linear', extension='EXTEND'):
        """Sample an image at (u, v) -> (r, g, b, a) scalars. Closest gives exact texel values (the lookup tables)."""
        vec = self.combine(u, v, 0.0)
        if self.gn:
            n = self.node('GeometryNodeImageTexture', interpolation=interpolation, extension=extension)
            n.inputs['Image'].default_value = img
            self.tree.links.new(vec, n.inputs['Vector'])
        else:
            n = self.node('ShaderNodeTexImage', interpolation=interpolation, extension=extension)
            n.image = img
            self.tree.links.new(vec, n.inputs['Vector'])
        r, g, b = self.separate(n.outputs['Color'])
        return r, g, b, E(self, n.outputs['Alpha'])

    def noise3(self, x, y, z):
        """three's mx_noise_float(vec3) * 0.5 + 0.5: Blender's Noise Texture at detail 0, normalized, is exactly that
        (measured by the fx family, tests/fx/test_noise_parity.py)."""
        n = self.node('ShaderNodeTexNoise', noise_dimensions='3D')
        if hasattr(n, 'normalize'):
            n.normalize = True
        n.inputs['Scale'].default_value = 1.0
        n.inputs['Detail'].default_value = 0.0
        n.inputs['Distortion'].default_value = 0.0
        if 'Roughness' in n.inputs:
            n.inputs['Roughness'].default_value = 0.5
        self.tree.links.new(self.combine(x, y, z), n.inputs['Vector'])
        return E(self, n.outputs['Fac'])


# ------------------------------------------------------------------------------------------------- node groups
def new_tree(name, kind='GeometryNodeTree', inputs=(), outputs=()):
    """A fresh node group with typed interface sockets -> (tree, group_input, group_output)."""
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    tree = bpy.data.node_groups.new(name, kind)
    for n, t in outputs:
        tree.interface.new_socket(n, in_out='OUTPUT', socket_type=t)
    for item in inputs:
        n, t = item[0], item[1]
        s = tree.interface.new_socket(n, in_out='INPUT', socket_type=t)
        if len(item) > 2 and item[2] is not None:
            s.default_value = item[2]
    gi = tree.nodes.new('NodeGroupInput')
    go = tree.nodes.new('NodeGroupOutput')
    gi.location = (-2800, 0)
    go.location = (2400, 0)
    return tree, gi, go


def clear_material(mat):
    """An empty node tree with one Material Output."""
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (2400, 0)
    return nt, out
