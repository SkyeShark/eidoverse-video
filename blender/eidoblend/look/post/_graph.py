"""look/post/_graph.py: an expression layer over compositor node groups, so a TSL post pass ports as code.

    g = G(tree)                                   # a CompositorNodeTree (a group being built)
    img = g.c(gi.outputs['Image'])                # a colour/vector field (V)
    xy = g.coords(img)                            # uv (y DOWN, as WebGPU's post passes), fc (pixels), res, px, S
    col = g.tap(img, xy.uv + g.v2(0.004, -0.0028))    # Map UV, edges clamped (ClampToEdge), y-down uv in
    l = g.dot(col, LUM)                           # scalar (S)
    out = g.mix(col, g.vec(l, l, l), weight)      # Vector Math / Mix nodes, built as the expression is written

Constants fold in Python (2 * 3 makes no node). Scalars are Math nodes; 3-vectors (colours, uv with z = 0) are
Vector Math nodes. uv here is y DOWN with fc in pixels from the top-left, exactly as the WebGPU passes saw them
(three's QuadMesh uv), so the TSL formulas port verbatim; tap() flips to Blender's y-up Map UV.

Every tree built by Python gets slow past a few hundred nodes (measured on 5.2: 500 linked nodes 0.26 s, 1000
1.5 s, 2000 8.8 s), so a big pass is split into function groups: fn() builds a node group once and call() drops
a group node; the compositor inlines them, so the split costs nothing at render time.
"""
from __future__ import annotations

import math

import bpy

_FOLD = {
    'ADD': lambda a, b: a + b, 'SUBTRACT': lambda a, b: a - b, 'MULTIPLY': lambda a, b: a * b,
    'DIVIDE': lambda a, b: a / b if b != 0 else 0.0, 'MINIMUM': min, 'MAXIMUM': max,
    'POWER': lambda a, b: a ** b if a > 0 or float(b).is_integer() else 0.0,
    'FLOOR': lambda a, b=0: float(math.floor(a)), 'FRACT': lambda a, b=0: a - math.floor(a),
    'ABSOLUTE': lambda a, b=0: abs(a), 'SQRT': lambda a, b=0: math.sqrt(max(a, 0.0)),
    'EXPONENT': lambda a, b=0: math.exp(a), 'SINE': lambda a, b=0: math.sin(a), 'COSINE': lambda a, b=0: math.cos(a),
    'LESS_THAN': lambda a, b: 1.0 if a < b else 0.0, 'GREATER_THAN': lambda a, b: 1.0 if a > b else 0.0,
    'FLOORED_MODULO': lambda a, b: a - b * math.floor(a / b) if b != 0 else 0.0,
    'LOGARITHM': lambda a, b=math.e: math.log(a) / math.log(b) if a > 0 else 0.0,
    'ARCTAN2': math.atan2, 'SIGN': lambda a, b=0: float((a > 0) - (a < 0)),
}

TAU = 2.0 * math.pi
LUM = (0.2126, 0.7152, 0.0722)          # three's luminance() / the WebGPU passes' LUM (Rec. 709)


def _ident(socks, identifier):
    """A socket by identifier (the Mix node's outputs all have the name 'Result')."""
    return next(s for s in socks if s.identifier == identifier)


def srgb_to_linear(c):
    """THREE.Color's sRGB -> linear-sRGB (a hex colour in the WebGPU code becomes this)."""
    return c * 0.0773993808 if c < 0.04045 else (c * 0.9478672986 + 0.0521327014) ** 2.4


def hex_lin(h):
    """'#ebe5d5' -> its linear values, as `new THREE.Color(hex)` gives them."""
    h = h.lstrip('#')
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


class S:
    """A scalar: a Python float (folded) or an output socket."""
    __slots__ = ('g', 'v')

    def __init__(self, g, v):
        self.g, self.v = g, v

    @property
    def const(self):
        return isinstance(self.v, (int, float))

    def _b(self, op, o, rev=False):
        if isinstance(o, V) or (isinstance(o, tuple) and len(o) == 3):
            o = self.g.v(o)
            if op == 'MULTIPLY':
                return o * self
            a = self.g.splat(self)
            return a._b({'ADD': 'ADD', 'SUBTRACT': 'SUBTRACT', 'DIVIDE': 'DIVIDE'}[op], o, rev)
        a, b = (o, self) if rev else (self, o)
        return self.g.math(op, a, b)

    def __add__(self, o): return self._b('ADD', o)
    def __radd__(self, o): return self._b('ADD', o, True)
    def __sub__(self, o): return self._b('SUBTRACT', o)
    def __rsub__(self, o): return self._b('SUBTRACT', o, True)
    def __mul__(self, o): return self._b('MULTIPLY', o)
    def __rmul__(self, o): return self._b('MULTIPLY', o, True)
    def __truediv__(self, o): return self._b('DIVIDE', o)
    def __rtruediv__(self, o): return self._b('DIVIDE', o, True)
    def __neg__(self): return self.g.math('MULTIPLY', self, -1.0)


class V:
    """A 3-vector: a colour (rgb) or a 2D point with z = 0. v is a socket or a 3-tuple of floats."""
    __slots__ = ('g', 'v', '_sep')

    def __init__(self, g, v):
        self.g, self.v, self._sep = g, v, None

    @property
    def const(self):
        return isinstance(self.v, tuple)

    def _b(self, op, o, rev=False):
        g = self.g
        if isinstance(o, (int, float, S)):
            if op == 'MULTIPLY':
                return g.vscale(self, o)
            if op == 'DIVIDE' and not rev:
                return g.vscale(self, 1.0 / o if isinstance(o, (int, float)) else g.math('DIVIDE', 1.0, o))
            o = g.splat(o)
        a, b = (o, self) if rev else (self, o)
        return g.vmath(op, a, b)

    def __add__(self, o): return self._b('ADD', o)
    def __radd__(self, o): return self._b('ADD', o, True)
    def __sub__(self, o): return self._b('SUBTRACT', o)
    def __rsub__(self, o): return self._b('SUBTRACT', o, True)
    def __mul__(self, o): return self._b('MULTIPLY', o)
    def __rmul__(self, o): return self._b('MULTIPLY', o, True)
    def __truediv__(self, o): return self._b('DIVIDE', o)
    def __rtruediv__(self, o): return self._b('DIVIDE', o, True)
    def __neg__(self): return self.g.vscale(self, -1.0)

    def _comps(self):
        if self.const:
            return tuple(S(self.g, float(c)) for c in self.v)
        if self._sep is None:
            n = self.g.node('ShaderNodeSeparateXYZ')
            self.g.link(self, n.inputs[0])
            self._sep = tuple(S(self.g, n.outputs[i]) for i in range(3))
        return self._sep

    @property
    def x(self): return self._comps()[0]

    @property
    def y(self): return self._comps()[1]

    @property
    def z(self): return self._comps()[2]

    r, gc, b = x, y, z                   # colour channel aliases (.g is the builder)


class Coords:
    """uv (y down, pixel centres), fc (pixels from the top-left), res (W, H), px (one pixel in uv), S = H / 1080."""

    def __init__(self, g, img):
        ic = g.node('CompositorNodeImageCoordinates')
        g.link(img, ic.inputs['Image'])
        n = g.v(ic.outputs['Normalized'])
        p = g.v(ic.outputs['Pixel'])
        u, vv = n.x, n.y
        self.W = (p.x + 0.5) / u
        self.H = (p.y + 0.5) / vv
        self.S = self.H / 1080.0
        self.uv = g.vec(u, 1.0 - vv, 0.0)
        self.u, self.v = u, 1.0 - vv
        self.fx, self.fy = u * self.W, self.v * self.H
        self.fc = g.vec(self.fx, self.fy, 0.0)
        self.res = g.vec(self.W, self.H, 0.0)
        self.pxu, self.pxv = 1.0 / self.W, 1.0 / self.H


class G:
    def __init__(self, tree, x0=-1600, y0=900):
        self.tree = tree
        self.nodes, self.links = tree.nodes, tree.links
        self.count = 0
        self.x0, self.y0 = x0, y0
        self._time = None

    # ---------------------------------------------------------------------------------------- plumbing
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
        if isinstance(src, (S, V)):
            src = src.v
        if isinstance(src, bpy.types.NodeSocket):
            self.links.new(src, dst)
            return
        if isinstance(src, (int, float)):
            dv = dst.default_value
            if isinstance(dv, (int, float, bool)):
                dst.default_value = type(dv)(src) if not isinstance(dv, bool) else bool(src)
            else:
                n = len(dv)
                dst.default_value = (float(src),) * min(n, 3) + ((1.0,) if n == 4 else ())
            return
        if isinstance(src, (tuple, list)):
            n = len(dst.default_value)
            v = tuple(float(x) for x in src)
            dst.default_value = v[:n] if len(v) >= n else v + (1.0,) * (n - len(v))
            return
        raise TypeError(f'cannot link {src!r}')

    def s(self, x):
        return x if isinstance(x, S) else S(self, x)

    def v(self, x):
        if isinstance(x, V):
            return x
        if isinstance(x, (int, float)):
            return V(self, (float(x),) * 3)
        if isinstance(x, (tuple, list)):
            x = tuple(float(c) for c in x)
            return V(self, (x + (0.0, 0.0, 0.0))[:3])
        return V(self, x)

    c = v                                               # a colour socket is a V (rgb)

    def splat(self, x):
        x = self.s(x)
        if x.const:
            return V(self, (x.v,) * 3)
        return self.vec(x, x, x)

    def s2(self, x):
        """A scalar as a 2D point (x, x, 0): the WebGPU vec2 splat (a plain splat would put x in z too)."""
        x = self.s(x)
        if x.const:
            return V(self, (x.v, x.v, 0.0))
        return self.vec(x, x, 0.0)

    def xy(self, a):
        """A V with z dropped to 0 (after a splatting op on a 2D point)."""
        return self.vec(a.x, a.y, 0.0)

    # ---------------------------------------------------------------------------------------- scalars
    def math(self, op, a, b=None, c=None, clamp=False):
        args = [x for x in (a, b, c) if x is not None]
        vals = [x.v if isinstance(x, S) else x for x in args]
        if not clamp and all(isinstance(v, (int, float)) for v in vals) and op in _FOLD:
            return S(self, float(_FOLD[op](*vals)))
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, v in enumerate(vals):
            self.link(v, n.inputs[i])
        return S(self, n.outputs[0])

    def floor(self, a): return self._u('FLOOR', a)
    def fract(self, a): return self._u('FRACT', a)
    def abs(self, a): return self._u('ABSOLUTE', a)
    def sqrt(self, a): return self._u('SQRT', a)
    def exp(self, a): return self._u('EXPONENT', a)
    def sin(self, a): return self._u('SINE', a)
    def cos(self, a): return self._u('COSINE', a)
    def sign(self, a): return self._u('SIGN', a)

    def _u(self, op, a):
        if isinstance(a, V):
            if op == 'SQRT':                     # Vector Math has no square root: power 0.5 (0 below 0, as SQRT)
                return self.vmath('POWER', self.vmath('MAXIMUM', (0.0, 0.0, 0.0), a), (0.5, 0.5, 0.5))
            if op == 'EXPONENT':
                return self.vec(*(self.math('EXPONENT', c) for c in a._comps()))
            vop = {'FRACT': 'FRACTION'}.get(op, op)
            return self.vmath(vop, a)
        return self.math(op, a)

    def log(self, a):
        return self.math('LOGARITHM', a, math.e)

    def pow(self, a, b):
        if isinstance(a, V):
            return self.vmath('POWER', a, self.splat(b) if not isinstance(b, V) else b)
        return self.math('POWER', a, b)

    def atan2(self, y, x):
        return self.math('ARCTAN2', y, x)

    def mod(self, a, b):
        if isinstance(a, V):
            return self.vmath('FLOORED_MODULO', a, self.splat(b) if not isinstance(b, V) else b)
        return self.math('FLOORED_MODULO', a, b)

    def min(self, a, b):
        if isinstance(a, V) or isinstance(b, V):
            return self.vmath('MINIMUM', self._vv(a), self._vv(b))
        return self.math('MINIMUM', a, b)

    def max(self, a, b):
        if isinstance(a, V) or isinstance(b, V):
            return self.vmath('MAXIMUM', self._vv(a), self._vv(b))
        return self.math('MAXIMUM', a, b)

    def _vv(self, x):
        return x if isinstance(x, V) else (self.v(x) if isinstance(x, (tuple, list)) else self.splat(x))

    def clamp(self, a, lo=0.0, hi=1.0):
        if isinstance(a, V):
            return self.min(self.max(a, lo), hi)
        a = self.s(a)
        if a.const:
            return S(self, min(max(a.v, lo), hi))
        if (lo, hi) == (0.0, 1.0):
            n = self.node('ShaderNodeMath', operation='ADD', use_clamp=True)
            self.link(a, n.inputs[0])
            n.inputs[1].default_value = 0.0
            return S(self, n.outputs[0])
        return self.min(self.max(a, lo), hi)

    def step(self, edge, x):
        """GLSL step(edge, x): 1 where x >= edge (per component for a V)."""
        if isinstance(x, V) or isinstance(edge, V):
            d = self.clamp(self._vv(edge) - self._vv(x), 0.0, 1.0)
            return 1.0 - self.vmath('CEIL', d)
        return 1.0 - self.math('LESS_THAN', x, edge)

    def smoothstep(self, e0, e1, x):
        """GLSL smoothstep (Map Range SMOOTHSTEP, clamped); reversed edges work as in GLSL."""
        if isinstance(x, V):
            n = self.node('ShaderNodeMapRange', data_type='FLOAT_VECTOR', interpolation_type='SMOOTHSTEP', clamp=True)
            ins = {s.identifier: s for s in n.inputs}
            self.link(x, ins['Vector'])
            self.link(self._vv(e0), ins['From_Min_FLOAT3'])
            self.link(self._vv(e1), ins['From_Max_FLOAT3'])
            self.link((0.0, 0.0, 0.0), ins['To_Min_FLOAT3'])
            self.link((1.0, 1.0, 1.0), ins['To_Max_FLOAT3'])
            return V(self, n.outputs['Vector'])
        if all(isinstance(self.s(q).v, (int, float)) for q in (e0, e1, x)):
            e0, e1, xv = self.s(e0).v, self.s(e1).v, self.s(x).v
            t = min(max((xv - e0) / (e1 - e0), 0.0), 1.0) if e1 != e0 else 0.0
            return S(self, t * t * (3 - 2 * t))
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True)
        self.link(x, n.inputs['Value'])
        self.link(e0, n.inputs['From Min'])
        self.link(e1, n.inputs['From Max'])
        n.inputs['To Min'].default_value, n.inputs['To Max'].default_value = 0.0, 1.0
        return S(self, n.outputs['Result'])

    def mix(self, a, b, t):
        """GLSL mix: floats, vectors with a scalar t, or vectors with a vector t (Mix node, factor unclamped)."""
        if not isinstance(a, V) and not isinstance(b, V) and not isinstance(t, V) \
                and not (isinstance(a, tuple) or isinstance(b, tuple)):
            a, b, t = self.s(a), self.s(b), self.s(t)
            if t.const and t.v == 0.0:
                return a
            if t.const and t.v == 1.0:
                return b
            if a.const and b.const and t.const:
                return S(self, a.v + (b.v - a.v) * t.v)
            n = self.node('ShaderNodeMix', data_type='FLOAT', clamp_factor=False)
            ins = {s.identifier: s for s in n.inputs}
            self.link(t, ins['Factor_Float'])
            self.link(a, ins['A_Float'])
            self.link(b, ins['B_Float'])
            return S(self, _ident(n.outputs, 'Result_Float'))
        a, b = self._vv(a), self._vv(b)
        nonu = isinstance(t, V) or isinstance(t, tuple)
        if not nonu and self.s(t).const and self.s(t).v == 0.0:
            return a
        if not nonu and self.s(t).const and self.s(t).v == 1.0:
            return b
        n = self.node('ShaderNodeMix', data_type='VECTOR', clamp_factor=False,
                      factor_mode='NON_UNIFORM' if nonu else 'UNIFORM')
        ins = {s.identifier: s for s in n.inputs}
        self.link(t if not nonu else self._vv(t), ins['Factor_Vector' if nonu else 'Factor_Float'])
        self.link(a, ins['A_Vector'])
        self.link(b, ins['B_Vector'])
        return V(self, _ident(n.outputs, 'Result_Vector'))

    # ---------------------------------------------------------------------------------------- vectors
    def vec(self, x, y, z=0.0):
        x, y, z = self.s(x), self.s(y), self.s(z)
        if x.const and y.const and z.const:
            return V(self, (x.v, y.v, z.v))
        n = self.node('ShaderNodeCombineXYZ')
        for i, c in enumerate((x, y, z)):
            self.link(c, n.inputs[i])
        return V(self, n.outputs[0])

    v2 = vec

    def vmath(self, op, a, b=None, c=None):
        scal = op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE')
        n = self.node('ShaderNodeVectorMath', operation=op)
        self.link(self._vv(a), n.inputs[0])
        if b is not None:
            self.link(self._vv(b), n.inputs[1])
        if c is not None:
            self.link(self._vv(c), n.inputs[2])
        return S(self, n.outputs['Value']) if scal else V(self, n.outputs['Vector'])

    def vscale(self, a, k):
        k = self.s(k)
        if k.const and k.v == 1.0:
            return self._vv(a)
        a = self._vv(a)
        if a.const and k.const:
            return V(self, tuple(c * k.v for c in a.v))
        n = self.node('ShaderNodeVectorMath', operation='SCALE')
        self.link(a, n.inputs[0])
        self.link(k, n.inputs['Scale'])
        return V(self, n.outputs['Vector'])

    def dot(self, a, b):
        a, b = self._vv(a), self._vv(b)
        if a.const and b.const:
            return S(self, sum(x * y for x, y in zip(a.v, b.v)))
        return self.vmath('DOT_PRODUCT', a, b)

    def length(self, a):
        return self.vmath('LENGTH', self._vv(a))

    def normalize(self, a):
        return self.vmath('NORMALIZE', self._vv(a))

    def lum(self, c):
        return self.dot(c, LUM)

    def comps(self, a):
        return self._vv(a)._comps()

    def max3(self, c):
        r, gg, b = self.comps(c)
        return self.max(r, self.max(gg, b))

    def min3(self, c):
        r, gg, b = self.comps(c)
        return self.min(r, self.min(gg, b))

    # ---------------------------------------------------------------------------------------- images
    def coords(self, img):
        return Coords(self, img)

    def tap(self, img, uv, interp='Bilinear', ext='Extend'):
        """The image at uv (y DOWN, normalised), edges clamped; returns its colour as a V (Map UV with Extend, Z = 1:
        Map UV reads Z as coverage). ext='Repeat' wraps instead (a RepeatWrapping texture)."""
        return V(self, self.tap_rgba(img, uv, interp, ext))

    def tap_rgba(self, img, uv, interp='Bilinear', ext='Extend'):
        uv = self._vv(uv)
        u, vd = uv.x, uv.y
        c = self.node('ShaderNodeCombineXYZ')
        self.link(u, c.inputs['X'])
        self.link(1.0 - vd, c.inputs['Y'])
        c.inputs['Z'].default_value = 1.0
        mu = self.node('CompositorNodeMapUV')
        mu.inputs['Extension X'].default_value = ext
        mu.inputs['Extension Y'].default_value = ext
        if interp != 'Bilinear':
            mu.inputs['Interpolation'].default_value = interp
        self.link(img, mu.inputs['Image'])
        self.links.new(c.outputs[0], mu.inputs['UV'])
        return mu.outputs['Image']

    def alpha(self, img):
        n = self.node('CompositorNodeSeparateColor')
        self.link(img, n.inputs['Image'])
        return S(self, n.outputs['Alpha'])

    def rgba(self, rgb, a=1.0):
        """A colour image from an rgb V and an alpha S."""
        rgb = self._vv(rgb)
        r, gg, b = self.comps(rgb)
        n = self.node('CompositorNodeCombineColor')
        for sock, v in zip(('Red', 'Green', 'Blue', 'Alpha'), (r, gg, b, a)):
            self.link(v, n.inputs[sock])
        return n.outputs['Image']

    def image(self, x):
        """A field as an image socket for Map UV / Blur (a V's vector socket; a scalar as grey)."""
        if isinstance(x, S):
            n = self.node('CompositorNodeCombineColor')
            for sock in ('Red', 'Green', 'Blue'):
                self.link(x, n.inputs[sock])
            n.inputs['Alpha'].default_value = 1.0
            return n.outputs['Image']
        return self._vv(x).v

    def blur(self, img, radius_px, kind='Gaussian'):
        """The compositor's Blur on an image; radius_px may be a socket (S). Gaussian: sigma = radius / 3."""
        n = self.node('CompositorNodeBlur')
        n.inputs['Type'].default_value = kind
        self.link(img, n.inputs['Image'])
        r = self.s(radius_px)
        if r.const:
            n.inputs['Size'].default_value = (r.v, r.v)
        else:
            self.link(self.vec(r, r, 0.0), n.inputs['Size'])
        return n.outputs['Image']

    # ---------------------------------------------------------------------------------------- noise and time
    def hash(self, x):
        """three's TSL hash(x) -> 0..1: Blender's White Noise (a bit hash of the float), 1D."""
        n = self.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D')
        self.link(x, n.inputs['W'])
        return S(self, n.outputs['Value'])

    def hash3(self, x, y, z):
        """The integer hash3(x, y, z) of the WebGPU passes -> 0..1: White Noise 3D on integer-valued floats."""
        n = self.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
        self.link(self.vec(x, y, z), n.inputs['Vector'])
        return S(self, n.outputs['Value'])

    def time(self):
        """(seconds, frame) from Scene Time."""
        if self._time is None:
            n = self.node('CompositorNodeSceneTime')
            self._time = (S(self, n.outputs['Seconds']), S(self, n.outputs['Frame']))
        return self._time

    def vnoise(self, p, salt):
        """The WebGPU passes' value noise: hash3 at the four lattice corners of p (in cells, positive), smoothstep
        interpolated. One shared function group (eido_vnoise), so a pass calls it without growing its own tree."""
        return self.call(_vnoise_fn(), p=self._vv(p), salt=salt)['v']

    def sanitize(self, c, hi=64.0):
        """Clamp a colour to [0, hi] with NaN -> 0 and +Inf -> hi on the GPU and the CPU compositor: the constant is
        the FIRST operand of Maximum / Minimum (measured 11-07: the CPU device keeps a NaN that comes first, as
        std::max does; the GPU returns the other operand either way)."""
        c = self._vv(c)
        return self.vmath('MINIMUM', (hi, hi, hi), self.vmath('MAXIMUM', (0.0, 0.0, 0.0), c))

    def fwidth(self, f, co, img=None):
        """GLSL fwidth(f) for a computed scalar field: f materialised as an image and differenced against its right
        and lower neighbours (|df/dx| + |df/dy|, one pixel apart). co: the pass's Coords."""
        im = self.image(f)
        fx = self.tap(im, co.uv + self.vec(co.pxu, 0.0)).x
        fy = self.tap(im, co.uv + self.vec(0.0, co.pxv)).x
        return self.abs(fx - f) + self.abs(fy - f)

    def mips(self, img, threshold=None, knee=0.01, n=5):
        """three's BloomNode pyramid of an image: a luminance high pass (smoothstep(threshold, threshold + knee) of
        Rec. 709 luma; None passes everything), then n levels, each half the size of the one before, blurred by a
        Gaussian of radius 6, 10, 14, 18, 22 px at its own size (sigma = radius / 3): sigma about 4, 14, 39, 104,
        256 px at full size. Returns the level images (sample them with tap())."""
        src = img
        if threshold is not None:
            c = self.c(img)
            k = self.smoothstep(threshold, threshold + knee, self.lum(c))
            src = self.image(c * k)
        out = []
        for i, radius in enumerate((6, 10, 14, 18, 22)[:n]):
            sc = self.node('CompositorNodeScale')
            sc.inputs['Type'].default_value = 'Relative'
            sc.inputs['X'].default_value = sc.inputs['Y'].default_value = 0.5
            self.link(src, sc.inputs['Image'])
            bl = self.node('CompositorNodeBlur')
            bl.inputs['Type'].default_value = 'Gaussian'
            bl.inputs['Size'].default_value = (radius, radius)
            self.links.new(sc.outputs['Image'], bl.inputs['Image'])
            src = bl.outputs['Image']
            out.append(src)
        return out

    def mip_composite(self, levels, uv, factors=(1.0, 0.8, 0.6, 0.4, 0.2)):
        """BloomNode.getTextureNode() at strength 1, radius 0: the levels summed with factors 1, 0.8, 0.6, 0.4, 0.2,
        sampled at uv."""
        acc = None
        for lv, f in zip(levels, factors):
            term = self.tap(lv, uv) * f
            acc = term if acc is None else acc + term
        return acc

    # ---------------------------------------------------------------------------------------- groups
    def call(self, tree, **inputs):
        """Instance a function group; returns {output name: S/V/socket}."""
        n = self.node('CompositorNodeGroup')
        n.node_tree = tree
        for k, v in inputs.items():
            if k not in n.inputs:
                raise KeyError(f'{tree.name}: no input {k!r} ({[s.name for s in n.inputs]})')
            sock = n.inputs[k]
            if isinstance(v, bpy.types.NodeSocket) or isinstance(v, (S, V)):
                self.link(v, sock)
            else:
                self.link(v, sock)
        outs = {}
        for s in n.outputs:
            if s.type == 'VALUE':
                outs[s.name] = S(self, s)
            elif s.type == 'VECTOR':
                outs[s.name] = V(self, s)
            else:
                outs[s.name] = s
        return outs


_SOCK = {'S': 'NodeSocketFloat', 'V': 'NodeSocketVector', 'C': 'NodeSocketColor'}


def fn(name, ins, outs, body, rebuild=False, version=1):
    """A function group built once: ins / outs are [(name, 'S' | 'V' | 'C', default)] and body(g, inputs) returns
    {output: S | V | socket}. 'C' inputs are images (colour fields); 'V' are vectors. A group already in the file is
    reused when its `version` matches (a changed layout bumps the version, so an older file's group is rebuilt)."""
    t = bpy.data.node_groups.get(name)
    if t is not None and not rebuild and t.get('eido_fn') == version:
        return t
    if t is not None:
        bpy.data.node_groups.remove(t)
    t = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    t['eido_fn'] = version
    for spec in ins:
        nm, kind = spec[0], spec[1]
        s = t.interface.new_socket(name=nm, in_out='INPUT', socket_type=_SOCK[kind])
        if len(spec) > 2 and spec[2] is not None:
            d = spec[2]
            s.default_value = d if kind == 'S' else (tuple(d) + (1.0,) * 4)[:4 if kind == 'C' else 3]
    for spec in outs:
        t.interface.new_socket(name=spec[0], in_out='OUTPUT', socket_type=_SOCK[spec[1]])
    g = G(t)
    gi, go = g.node('NodeGroupInput'), g.node('NodeGroupOutput')
    gi.hide = go.hide = False
    gi.location, go.location = (-2000, 0), (2600, 0)
    args = {}
    for spec in ins:
        sock = gi.outputs[spec[0]]
        args[spec[0]] = S(g, sock) if spec[1] == 'S' else (V(g, sock) if spec[1] == 'V' else sock)
    res = body(g, args)
    for spec in outs:
        val = res[spec[0]]
        if spec[1] == 'C' and isinstance(val, V):
            val = val.v
        g.link(val, go.inputs[spec[0]])
    t['eido_nodes'] = len(t.nodes)
    return t


def _vnoise_fn():
    def body(g, a):
        p, salt = a['p'], a['salt']
        i, f = g.floor(p), g.fract(p)
        s = f * f * (3.0 - 2.0 * f)
        ix, iy, sx, sy = i.x, i.y, s.x, s.y
        c00, c10 = g.hash3(ix, iy, salt), g.hash3(ix + 1.0, iy, salt)
        c01, c11 = g.hash3(ix, iy + 1.0, salt), g.hash3(ix + 1.0, iy + 1.0, salt)
        return {'v': g.mix(g.mix(c00, c10, sx), g.mix(c01, c11, sx), sy)}
    return fn('eido_vnoise', [('p', 'V', (0.0, 0.0, 0.0)), ('salt', 'S', 0.0)], [('v', 'S')], body)


def bayer4(g, p):
    """The 4x4 ordered-dither threshold of the WebGPU passes at integer pixel p (a V): (0.5 .. 15.5) / 16."""
    def b2(a, b):
        return a * 2.0 + b * 3.0 - a * b * 4.0
    lo = b2(g.mod(p.x, 2.0), g.mod(p.y, 2.0))
    hi = b2(g.mod(g.floor(p.x / 2.0), 2.0), g.mod(g.floor(p.y / 2.0), 2.0))
    return (lo * 4.0 + hi + 0.5) / 16.0
