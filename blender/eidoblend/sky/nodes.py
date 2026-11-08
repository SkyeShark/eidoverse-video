"""Shader-node building for the sky worlds' materials: the TSL graphs, written as Blender node graphs.

`Graph(tree)` wraps a node tree with expression helpers (`g.mul(a, b)`, `g.smoothstep(e0, e1, x)`, `g.vdot(a, b)` ...)
whose arguments are sockets or plain numbers, so a TSL line such as
    smoothstep(-0.22, 0.30, dot(inward, sunDir))
reads here as
    g.smoothstep(-0.22, 0.30, g.vdot(inward, sun_dir))
GLSL smoothstep(e0, e1, x) is the Map Range node's SMOOTHSTEP mode (for e0 > e1 too). Shared groups:
  eido_h21        the sin-free Hoskins hash21 the WebGPU materials use (house style), exact in float32
  eido_vnoise2    2D value noise with the smoothstep fade over eido_h21 (ringworld.js vn / vn2)
  eido_vnoise2_rep  the same noise on a lattice that wraps every Rep cells (ringworld.js vnT, the full wave field)
"""
import bpy


class Graph:
    def __init__(self, tree, x0=-1600, dx=180):
        self.t = tree
        self.N = tree.nodes
        self.L = tree.links
        self._x = x0
        self._dx = dx
        self._y = 0

    # ---- placement and plumbing ----
    def node(self, kind, label=None, **props):
        n = self.N.new(kind)
        n.location = (self._x, self._y)
        self._y -= 140
        if self._y < -2400:
            self._y = 0
            self._x += self._dx
        for k, v in props.items():
            setattr(n, k, v)
        if label:
            n.name = n.label = label
        return n

    def link(self, src, dst):
        self.L.new(src, dst)

    def _set(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        elif isinstance(v, (tuple, list)):
            dv = sock.default_value
            n = len(dv)
            vv = list(v) + [1.0] * (n - len(v))
            sock.default_value = vv[:n]
        else:
            if hasattr(sock.default_value, '__len__'):
                sock.default_value = [float(v)] * len(sock.default_value)
            else:
                sock.default_value = float(v)

    # ---- scalars ----
    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            self._set(n.inputs[i], v)
        return n.outputs[0]

    def add(self, a, b):
        return self.math('ADD', a, b)

    def sub(self, a, b):
        return self.math('SUBTRACT', a, b)

    def mul(self, a, b):
        return self.math('MULTIPLY', a, b)

    def div(self, a, b):
        return self.math('DIVIDE', a, b)

    def madd(self, a, b, c):
        return self.math('MULTIPLY_ADD', a, b, c)

    def min(self, a, b):
        return self.math('MINIMUM', a, b)

    def max(self, a, b):
        return self.math('MAXIMUM', a, b)

    def clamp01(self, a):
        return self.math('ADD', a, 0.0, clamp=True)

    def clamp(self, a, lo, hi):
        return self.min(self.max(a, lo), hi)

    def pow(self, a, b):
        return self.math('POWER', a, b)

    def exp(self, a):
        return self.math('EXPONENT', a)

    def abs(self, a):
        return self.math('ABSOLUTE', a)

    def floor(self, a):
        return self.math('FLOOR', a)

    def fract(self, a):
        return self.math('FRACT', a)

    def sqrt(self, a):
        return self.math('SQRT', a)

    def sin(self, a):
        return self.math('SINE', a)

    def cos(self, a):
        return self.math('COSINE', a)

    def atan2(self, y, x):
        return self.math('ARCTAN2', y, x)

    def neg(self, a):
        return self.math('MULTIPLY', a, -1.0)

    def one_minus(self, a):
        return self.math('SUBTRACT', 1.0, a)

    def lerp(self, a, b, t):
        n = self.node('ShaderNodeMix', data_type='FLOAT', clamp_factor=False)
        self._set(n.inputs['Factor'], t)
        self._set(n.inputs['A'], a)
        self._set(n.inputs['B'], b)
        return n.outputs['Result']

    def smoothstep(self, e0, e1, x):
        """GLSL smoothstep(e0, e1, x), also for e0 > e1 (Map Range SMOOTHSTEP)."""
        n = self.node('ShaderNodeMapRange', data_type='FLOAT', interpolation_type='SMOOTHSTEP', clamp=True)
        self._set(n.inputs['Value'], x)
        self._set(n.inputs['From Min'], e0)
        self._set(n.inputs['From Max'], e1)
        n.inputs['To Min'].default_value = 0.0
        n.inputs['To Max'].default_value = 1.0
        return n.outputs['Result']

    def step(self, edge, x):
        """GLSL step(edge, x) = x >= edge."""
        return self.math('SUBTRACT', 1.0, self.math('LESS_THAN', x, edge))

    # ---- vectors ----
    def vmath(self, op, a, b=None, c=None, scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self._set(n.inputs[i], v)
        if scale is not None:
            self._set(n.inputs['Scale'], scale)
        out = n.outputs['Value'] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs['Vector']
        return out

    def vadd(self, a, b):
        return self.vmath('ADD', a, b)

    def vsub(self, a, b):
        return self.vmath('SUBTRACT', a, b)

    def vmul(self, a, b):
        return self.vmath('MULTIPLY', a, b)

    def vscale(self, a, s):
        return self.vmath('SCALE', a, scale=s)

    def vdot(self, a, b):
        return self.vmath('DOT_PRODUCT', a, b)

    def vnorm(self, a):
        return self.vmath('NORMALIZE', a)

    def vlen(self, a):
        return self.vmath('LENGTH', a)

    def vcross(self, a, b):
        return self.vmath('CROSS_PRODUCT', a, b)

    def vfract(self, a):
        return self.vmath('FRACTION', a)

    def vfloor(self, a):
        return self.vmath('FLOOR', a)

    def vabs(self, a):
        return self.vmath('ABSOLUTE', a)

    def vexp_neg(self, a):
        """exp(-a) per component."""
        x, y, z = self.sep(a)
        return self.comb(self.exp(self.neg(x)), self.exp(self.neg(y)), self.exp(self.neg(z)))

    def vlerp(self, a, b, t):
        n = self.node('ShaderNodeMix', data_type='VECTOR', factor_mode='UNIFORM', clamp_factor=False)
        self._set(n.inputs['Factor'], t)
        self._set(n.inputs[4], a)     # A (vector)
        self._set(n.inputs[5], b)     # B (vector)
        return n.outputs[1]

    def comb(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        self._set(n.inputs['X'], x)
        self._set(n.inputs['Y'], y)
        self._set(n.inputs['Z'], z)
        return n.outputs['Vector']

    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self._set(n.inputs['Vector'], v)
        return n.outputs['X'], n.outputs['Y'], n.outputs['Z']

    def const_vec(self, v, label=None):
        return self.comb(*v)

    def value(self, v, label=None):
        n = self.node('ShaderNodeValue', label=label)
        n.outputs[0].default_value = float(v)
        return n.outputs[0]

    # ---- textures ----
    def image(self, img, vector=None, interpolation='Linear', extension='REPEAT', label=None):
        n = self.node('ShaderNodeTexImage', label=label, interpolation=interpolation, extension=extension)
        n.image = img
        if vector is not None:
            self._set(n.inputs['Vector'], vector)
        return n

    def group(self, tree, **inputs):
        n = self.node('ShaderNodeGroup')
        n.node_tree = tree
        for k, v in inputs.items():
            self._set(n.inputs[k], v)
        return n


def new_group(name, inputs=(), outputs=(), kind='ShaderNodeTree'):
    """A fresh node group with (name, socket type) inputs and outputs; returns (tree, group input, group output)."""
    old = bpy.data.node_groups.get(name)
    if old:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, kind)
    for n, t in inputs:
        ng.interface.new_socket(n, in_out='INPUT', socket_type=t)
    for n, t in outputs:
        ng.interface.new_socket(n, in_out='OUTPUT', socket_type=t)
    gi = ng.nodes.new('NodeGroupInput')
    go = ng.nodes.new('NodeGroupOutput')
    gi.location = (-2000, 0)
    go.location = (1800, 0)
    return ng, gi, go


def hash21_group():
    """eido_h21: fract((b.x + b.y) * b.z), a = fract(p.xyx * 0.1031), b = a + dot(a, a.yzx + 33.33)."""
    ng = bpy.data.node_groups.get('eido_h21')
    if ng:
        return ng
    ng, gi, go = new_group('eido_h21', [('P', 'NodeSocketVector')], [('Value', 'NodeSocketFloat')])
    g = Graph(ng)
    px, py, _ = g.sep(gi.outputs['P'])
    a = g.vfract(g.vscale(g.comb(px, py, px), 0.1031))
    ax, ay, az = g.sep(a)
    d = g.vdot(a, g.vadd(g.comb(ay, az, ax), (33.33, 33.33, 33.33)))
    b = g.vadd(a, g.comb(d, d, d))
    bx, by, bz = g.sep(b)
    g.link(g.fract(g.mul(g.add(bx, by), bz)), go.inputs['Value'])
    return ng


def vnoise2_group():
    """eido_vnoise2: value noise over the integer lattice of P.xy, smoothstep fade (ringworld.js vn)."""
    ng = bpy.data.node_groups.get('eido_vnoise2')
    if ng:
        return ng
    h = hash21_group()
    ng, gi, go = new_group('eido_vnoise2', [('P', 'NodeSocketVector')], [('Value', 'NodeSocketFloat')])
    g = Graph(ng)
    p = gi.outputs['P']
    px, py, _ = g.sep(p)
    p2 = g.comb(px, py, 0.0)
    i = g.vfloor(p2)
    f = g.vfract(p2)
    fx, fy, _ = g.sep(f)
    sx = g.mul(g.mul(fx, fx), g.sub(3.0, g.mul(fx, 2.0)))
    sy = g.mul(g.mul(fy, fy), g.sub(3.0, g.mul(fy, 2.0)))

    def hh(dx, dy):
        return g.group(h, P=g.vadd(i, (dx, dy, 0.0))).outputs['Value']

    a, b, c, d = hh(0, 0), hh(1, 0), hh(0, 1), hh(1, 1)
    g.link(g.lerp(g.lerp(a, b, sx), g.lerp(c, d, sx), sy), go.inputs['Value'])
    return ng


def vnoise2_rep_group():
    """eido_vnoise2_rep: eido_vnoise2 whose lattice wraps every Rep cells (GLSL floored mod), ringworld.js vnT and
    ring_cloud_field.js noise: h2(mod(floor(P) + corner, Rep))."""
    ng = bpy.data.node_groups.get('eido_vnoise2_rep')
    if ng:
        return ng
    h = hash21_group()
    ng, gi, go = new_group('eido_vnoise2_rep', [('P', 'NodeSocketVector'), ('Rep', 'NodeSocketVector')],
                           [('Value', 'NodeSocketFloat')])
    g = Graph(ng)
    px, py, _ = g.sep(gi.outputs['P'])
    rx, ry, _ = g.sep(gi.outputs['Rep'])
    ix, iy = g.floor(px), g.floor(py)
    fx, fy = g.fract(px), g.fract(py)
    sx = g.mul(g.mul(fx, fx), g.sub(3.0, g.mul(fx, 2.0)))
    sy = g.mul(g.mul(fy, fy), g.sub(3.0, g.mul(fy, 2.0)))

    def hh(dx, dy):
        cx = g.math('FLOORED_MODULO', g.add(ix, float(dx)), rx)
        cy = g.math('FLOORED_MODULO', g.add(iy, float(dy)), ry)
        return g.group(h, P=g.comb(cx, cy, 0.0)).outputs['Value']

    a, b, c, d = hh(0, 0), hh(1, 0), hh(0, 1), hh(1, 1)
    g.link(g.lerp(g.lerp(a, b, sx), g.lerp(c, d, sx), sy), go.inputs['Value'])
    return ng


def keyed_values_group(name, values):
    """A node group holding per-frame values to key: {name: float | (r, g, b) | ('vec', (x, y, z))}.

    Every output is one keyed node inside the group, so all the materials using the group share one set of keys.
    Returns (tree, {name: node}). Floats are Value nodes; 3-vectors are Combine XYZ nodes (key their inputs)."""
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    else:
        for item in list(ng.interface.items_tree):
            ng.interface.remove(item)
        ng.nodes.clear()
        if ng.animation_data:
            ng.animation_data_clear()
    go = ng.nodes.new('NodeGroupOutput')
    go.location = (600, 0)
    handles = {}
    y = 0
    for key, v in values.items():
        if isinstance(v, (tuple, list)):
            ng.interface.new_socket(key, in_out='OUTPUT', socket_type='NodeSocketVector')
            n = ng.nodes.new('ShaderNodeCombineXYZ')
            for ax, c in zip('XYZ', v):
                n.inputs[ax].default_value = float(c)
            out = n.outputs['Vector']
        else:
            ng.interface.new_socket(key, in_out='OUTPUT', socket_type='NodeSocketFloat')
            n = ng.nodes.new('ShaderNodeValue')
            n.outputs[0].default_value = float(v)
            out = n.outputs[0]
        n.name = n.label = key
        n.location = (0, y)
        y -= 120
        ng.links.new(out, go.inputs[key])
        handles[key] = n
    return ng, handles


def key_values(handles, frame, values, interpolation='LINEAR'):
    """Insert one frame of keyed_values_group values; returns the keyed (node, path) list."""
    for key, v in values.items():
        n = handles.get(key)
        if n is None:
            continue
        if n.bl_idname == 'ShaderNodeCombineXYZ':
            for ax, c in zip('XYZ', v):
                n.inputs[ax].default_value = float(c)
                n.inputs[ax].keyframe_insert('default_value', frame=frame)
        else:
            n.outputs[0].default_value = float(v)
            n.outputs[0].keyframe_insert('default_value', frame=frame)


def set_interpolation(id_data, interpolation='LINEAR'):
    """Every key of id_data's action to `interpolation` (Python's keyframe_insert ignores the preference)."""
    from .world_nodes import _fcurves
    ad = getattr(id_data, 'animation_data', None)
    if not ad or not ad.action:
        return 0
    n = 0
    for fc in _fcurves(ad):
        for kp in fc.keyframe_points:
            kp.interpolation = interpolation
            n += 1
    return n
