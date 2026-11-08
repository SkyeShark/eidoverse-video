"""A small expression layer over Blender node trees, so a shader written in TSL ports as code, not clicks.

    b = Builder(material.node_tree)              # or a node group's tree (shader or geometry nodes)
    p = b.vec(b.node('ShaderNodeTexCoord').outputs['Object'])
    x, y, z = p.xyz()                            # scalars (Expr), one Separate XYZ shared by all three
    n = b.group('eido.snoise', Vector=b.combine(x, z, -y))   # call a node-group function
    d = (n * 0.35 + 0.85) * density              # Math nodes, built as the expression is written
    b.link(d, principled.inputs['Density'])

Constants fold in Python: (2 * 3) makes no node. Scalars are Math nodes; vectors are Vector Math nodes or
three scalars combined. Node locations are laid out by creation order so a graph stays readable.
"""

from __future__ import annotations

import bpy

_MATH = {
    '+': 'ADD', '-': 'SUBTRACT', '*': 'MULTIPLY', '/': 'DIVIDE',
}


class Expr:
    """A scalar value in a node tree: a Python float (folded) or an output socket."""

    __slots__ = ('b', 'v')

    def __init__(self, b, v):
        self.b = b
        self.v = v

    # arithmetic -----------------------------------------------------------------------------------
    def _bin(self, op, other, rev=False):
        a, c = (other, self) if rev else (self, other)
        return self.b.math(_MATH[op], a, c)

    def __add__(self, o): return self._bin('+', o)
    def __radd__(self, o): return self._bin('+', o, True)
    def __sub__(self, o): return self._bin('-', o)
    def __rsub__(self, o): return self._bin('-', o, True)
    def __mul__(self, o): return self._bin('*', o)
    def __rmul__(self, o): return self._bin('*', o, True)
    def __truediv__(self, o): return self._bin('/', o)
    def __rtruediv__(self, o): return self._bin('/', o, True)
    def __neg__(self): return self.b.math('MULTIPLY', self, -1.0)

    @property
    def const(self):
        return isinstance(self.v, (int, float))


class Vec:
    """A vector socket (Vector Math based)."""

    __slots__ = ('b', 'v')

    def __init__(self, b, v):
        self.b = b
        self.v = v

    def _bin(self, op, other, rev=False):
        a, c = (other, self) if rev else (self, other)
        return self.b.vmath(op, a, c)

    def __add__(self, o): return self._bin('ADD', o)
    def __radd__(self, o): return self._bin('ADD', o, True)
    def __sub__(self, o): return self._bin('SUBTRACT', o)
    def __rsub__(self, o): return self._bin('SUBTRACT', o, True)
    def __mul__(self, o):
        if isinstance(o, (int, float, Expr)):
            return self.b.vscale(self, o)
        return self._bin('MULTIPLY', o)
    __rmul__ = __mul__

    def xyz(self):
        sep = self.b.node('ShaderNodeSeparateXYZ')
        self.b.link(self, sep.inputs[0])
        return tuple(Expr(self.b, sep.outputs[i]) for i in range(3))


class Builder:
    def __init__(self, tree, x0=-1400, y0=600):
        self.tree = tree
        self.nodes = tree.nodes
        self.links = tree.links
        self.count = 0
        self.x0, self.y0 = x0, y0

    # plumbing -------------------------------------------------------------------------------------
    def node(self, kind, **props):
        n = self.nodes.new(kind)
        col, row = divmod(self.count, 24)
        n.location = (self.x0 + col * 190, self.y0 - row * 46)
        n.hide = True
        self.count += 1
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, src, dst_socket):
        if isinstance(src, (Expr, Vec)):
            src = src.v
        if isinstance(src, (int, float)):
            dst_socket.default_value = float(src)
            return
        if isinstance(src, (tuple, list)):
            n = len(dst_socket.default_value)
            v = tuple(src)[:n] if len(src) >= n else tuple(src) + (1.0,) * (n - len(src))
            dst_socket.default_value = v
            return
        self.links.new(src, dst_socket)

    def s(self, x):
        """Wrap a socket or number as a scalar Expr."""
        return x if isinstance(x, Expr) else Expr(self, x)

    def vec(self, x):
        return x if isinstance(x, Vec) else Vec(self, x)

    # scalar math ----------------------------------------------------------------------------------
    def math(self, op, a, b=None, c=None, fold=True):
        args = [x for x in (a, b, c) if x is not None]
        vals = [x.v if isinstance(x, Expr) else x for x in args]
        if fold and all(isinstance(v, (int, float)) for v in vals):
            return Expr(self, _fold(op, *vals))
        n = self.node('ShaderNodeMath', operation=op)
        for i, v in enumerate(vals):
            self.link(v, n.inputs[i])
        return Expr(self, n.outputs[0])

    def floor(self, a): return self.math('FLOOR', a)
    def fract(self, a): return self.math('FRACT', a)
    def abs(self, a): return self.math('ABSOLUTE', a)
    def min(self, a, b): return self.math('MINIMUM', a, b)
    def max(self, a, b): return self.math('MAXIMUM', a, b)
    def sqrt(self, a): return self.math('SQRT', a)
    def inv_sqrt(self, a): return self.math('INVERSE_SQRT', a)
    def exp(self, a): return self.math('EXPONENT', a)
    def pow(self, a, b): return self.math('POWER', a, b)
    def mod(self, a, b): return self.math('FLOORED_MODULO', a, b)     # GLSL/TSL mod
    def sin(self, a): return self.math('SINE', a)
    def cos(self, a): return self.math('COSINE', a)

    def step(self, edge, x):
        """GLSL step(edge, x) = x >= edge ? 1 : 0."""
        return 1.0 - self.math('LESS_THAN', x, edge)

    def clamp(self, a, lo=0.0, hi=1.0):
        return self.min(self.max(a, lo), hi)

    def mix(self, a, b, t):
        return a + (b - a) * t

    def smoothstep(self, e0, e1, x):
        t = self.clamp((self.s(x) - e0) / (e1 - e0))
        return t * t * (3.0 - 2.0 * t)

    # vectors --------------------------------------------------------------------------------------
    def combine(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        for i, c in enumerate((x, y, z)):
            self.link(c, n.inputs[i])
        return Vec(self, n.outputs[0])

    def vmath(self, op, a, b=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.link(a, n.inputs[0])
        if b is not None:
            self.link(b, n.inputs[1])
        out = n.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs['Vector']
        return Expr(self, out) if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else Vec(self, out)

    def vscale(self, a, k):
        n = self.node('ShaderNodeVectorMath', operation='SCALE')
        self.link(a, n.inputs[0])
        self.link(k, n.inputs['Scale'])
        return Vec(self, n.outputs['Vector'])

    def rgb_mix(self, a, b, t, blend='MIX'):
        n = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_factor=False)
        ins = {s.identifier: s for s in n.inputs}
        outs = {s.identifier: s for s in n.outputs}
        self.link(t, ins['Factor_Float'])
        self.link(a, ins['A_Color'])
        self.link(b, ins['B_Color'])
        return Vec(self, outs['Result_Color'])

    def value(self, v, label=None):
        n = self.node('ShaderNodeValue')
        n.outputs[0].default_value = float(v)
        if label:
            n.label = n.name = label
            n.hide = False
        return Expr(self, n.outputs[0])

    def group(self, name, **inputs):
        n = self.node('ShaderNodeGroup' if self.tree.bl_idname == 'ShaderNodeTree' else 'GeometryNodeGroup')
        n.node_tree = bpy.data.node_groups[name]
        for k, v in inputs.items():
            self.link(v, n.inputs[k])
        return n


def _fold(op, *v):
    import math
    a = v[0]
    b = v[1] if len(v) > 1 else 0.0
    if op == 'ADD': return a + b
    if op == 'SUBTRACT': return a - b
    if op == 'MULTIPLY': return a * b
    if op == 'DIVIDE': return a / b if b != 0 else 0.0
    if op == 'FLOOR': return float(math.floor(a))
    if op == 'FRACT': return a - math.floor(a)
    if op == 'ABSOLUTE': return abs(a)
    if op == 'MINIMUM': return min(a, b)
    if op == 'MAXIMUM': return max(a, b)
    if op == 'SQRT': return math.sqrt(max(a, 0.0))
    if op == 'INVERSE_SQRT': return 1.0 / math.sqrt(a) if a > 0 else 0.0
    if op == 'EXPONENT': return math.exp(a)
    if op == 'POWER': return a ** b if a > 0 or float(b).is_integer() else 0.0
    if op == 'FLOORED_MODULO': return a - b * math.floor(a / b) if b != 0 else 0.0
    if op == 'LESS_THAN': return 1.0 if a < b else 0.0
    if op == 'GREATER_THAN': return 1.0 if a > b else 0.0
    if op == 'SINE': return math.sin(a)
    if op == 'COSINE': return math.cos(a)
    raise ValueError(op)


def new_group(name, kind='ShaderNodeTree', inputs=(), outputs=()):
    """A fresh node group with typed interface sockets; returns (tree, group_input, group_output)."""
    if name in bpy.data.node_groups:
        bpy.data.node_groups.remove(bpy.data.node_groups[name])
    tree = bpy.data.node_groups.new(name, kind)
    for n, t in inputs:
        tree.interface.new_socket(n, in_out='INPUT', socket_type=t)
    for n, t in outputs:
        tree.interface.new_socket(n, in_out='OUTPUT', socket_type=t)
    gi = tree.nodes.new('NodeGroupInput')
    go = tree.nodes.new('NodeGroupOutput')
    gi.location = (-1700, 0)
    go.location = (1400, 0)
    return tree, gi, go


def snoise_group(kind='ShaderNodeTree', name='eido.snoise'):
    """The node group 'eido.snoise': TSL curlNoise.js `snoise(v)` as shader nodes (Vector -> Value).
    The same arithmetic as _noise.snoise and the GLSL in _gpu.py, scalar by scalar. kind='GeometryNodeTree'
    builds the identical graph for Geometry Nodes (the parity test evaluates it that way)."""
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_group(name, kind, [('Vector', 'NodeSocketVector')], [('Value', 'NodeSocketFloat')])
    b = Builder(tree)
    vx, vy, vz = b.vec(gi.outputs['Vector']).xyz()
    C0, C1 = 1.0 / 6.0, 1.0 / 3.0
    s = (vx + vy + vz) * C1
    ix, iy, iz = b.floor(vx + s), b.floor(vy + s), b.floor(vz + s)
    t = (ix + iy + iz) * C0
    x0 = (vx - ix + t, vy - iy + t, vz - iz + t)
    # g = step(x0.yzx, x0.xyz)
    g = (b.step(x0[1], x0[0]), b.step(x0[2], x0[1]), b.step(x0[0], x0[2]))
    l = (1.0 - g[0], 1.0 - g[1], 1.0 - g[2])
    lzxy = (l[2], l[0], l[1])
    i1 = tuple(b.min(g[k], lzxy[k]) for k in range(3))
    i2 = tuple(b.max(g[k], lzxy[k]) for k in range(3))
    x1 = tuple(x0[k] - i1[k] + C0 for k in range(3))
    x2 = tuple(x0[k] - i2[k] + C1 for k in range(3))
    x3 = tuple(x0[k] - 0.5 for k in range(3))
    ix, iy, iz = b.mod(ix, 289.0), b.mod(iy, 289.0), b.mod(iz, 289.0)

    def permute(x):
        return b.mod(x * x * 34.0 + x, 289.0)

    p = [permute(iz + o) for o in (0.0, i1[2], i2[2], 1.0)]
    p = [permute(p[k] + iy + o) for k, o in enumerate((0.0, i1[1], i2[1], 1.0))]
    p = [permute(p[k] + ix + o) for k, o in enumerate((0.0, i1[0], i2[0], 1.0))]
    nsx = 0.142857142857 * 2.0
    nsy = 0.142857142857 * 0.5 - 1.0
    nsz = 0.142857142857
    j = [p[k] - 49.0 * b.floor(p[k] * (nsz * nsz)) for k in range(4)]
    x_ = [b.floor(j[k] * nsz) for k in range(4)]
    X = [x_[k] * nsx + nsy for k in range(4)]
    Y = [b.floor(j[k] - 7.0 * x_[k]) * nsx + nsy for k in range(4)]
    h = [1.0 - b.abs(X[k]) - b.abs(Y[k]) for k in range(4)]
    b0 = (X[0], X[1], Y[0], Y[1])
    b1 = (X[2], X[3], Y[2], Y[3])
    sh = [-b.step(h[k], 0.0) for k in range(4)]         # -step(h, 0): step(edge=h, x=0)

    def fl2(v):
        return b.floor(v) * 2.0 + 1.0

    # a0 = b0.xzyw + floor(b0)*2+1 .xzyw * sh.xxyy
    a0 = (b0[0] + fl2(b0[0]) * sh[0], b0[2] + fl2(b0[2]) * sh[0],
          b0[1] + fl2(b0[1]) * sh[1], b0[3] + fl2(b0[3]) * sh[1])
    a1 = (b1[0] + fl2(b1[0]) * sh[2], b1[2] + fl2(b1[2]) * sh[2],
          b1[1] + fl2(b1[1]) * sh[3], b1[3] + fl2(b1[3]) * sh[3])
    P = [(a0[0], a0[1], h[0]), (a0[2], a0[3], h[1]), (a1[0], a1[1], h[2]), (a1[2], a1[3], h[3])]
    XS = [x0, x1, x2, x3]

    def dot(a, c):
        return a[0] * c[0] + a[1] * c[1] + a[2] * c[2]

    acc = None
    for k in range(4):
        nrm = b.inv_sqrt(dot(P[k], P[k]))
        m = b.max(0.6 - dot(XS[k], XS[k]), 0.0)
        term = m * m * m * (dot(P[k], XS[k]) * nrm)
        acc = term if acc is None else acc + term
    out = 0.5 + 12.0 * acc
    b.link(out, go.inputs['Value'])
    return tree


def fire_ramp(b, t, start, mid, end):
    """fluid_grid.js fireRamp(t): black -> end -> mid -> start, through three smoothsteps (RGB Vec)."""
    c = b.rgb_mix((0.0, 0.0, 0.0, 1.0), (*end, 1.0), b.smoothstep(0.05, 0.35, t))
    c = b.rgb_mix(c, (*mid, 1.0), b.smoothstep(0.35, 0.65, t))
    c = b.rgb_mix(c, (*start, 1.0), b.smoothstep(0.65, 1.0, t))
    return c


def hue_rotate(b, rgb, angle):
    """three TSL hue(color, angle) as vector math; angle in radians (an Expr or a float)."""
    if isinstance(angle, (int, float)) and angle == 0.0:
        return rgb
    import math
    k = (0.57735, 0.57735, 0.57735)
    ca = b.cos(angle) if not isinstance(angle, (int, float)) else math.cos(angle)
    sa = b.sin(angle) if not isinstance(angle, (int, float)) else math.sin(angle)
    cr = b.vmath('CROSS_PRODUCT', k, rgb)
    dk = b.vmath('DOT_PRODUCT', k, rgb)
    return b.vscale(rgb, ca) + b.vscale(cr, sa) + b.vscale(k, dk * (1.0 - ca))


def saturate_color(b, rgb, amount):
    """three TSL saturation(color, amount): mix(luminance, color, amount), Rec.709 weights."""
    lum = b.vmath('DOT_PRODUCT', rgb, (0.2126, 0.7152, 0.0722))
    lv = b.combine(lum, lum, lum)
    return lv + b.vscale(rgb - lv, amount)
