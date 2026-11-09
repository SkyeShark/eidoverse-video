"""SDF_NP: the engine's SDF_TSL primitive library over numpy arrays, for SDFs written in Python.

The WebGPU engine let a scene author write map(p) / shade(p, n, mat) in its host language (JavaScript building TSL
nodes). The Blender edition's host language is Python: the same primitives, combinators, rotations, mirrors and
hash / vnoise / fbm / fbm6, with the same names in snake_case, take (N, 3) float32 arrays and return (N,) arrays.
They are float32 throughout, like the GPU, and tests/sdf/test_library_parity.py checks them against the GLSL library.
A shade(p, n, mat) or surface(p, n, mat) may take the engine's 4th argument, ctx (ShadeContext: ro, rd,
soft_shadow / softShadow, calc_normal / calcNormal), as the TSL shade did.

    from eidoblend.sdf import SDF_NP as S, create_sdf_object
    def my_map(p):
        body = S.sd_sphere(p, 0.4)
        head = S.sd_sphere(p - S.vec3(0, 0.55, 0), 0.2)
        return S.smin(body, head, 0.1), 1.0
    def my_surface(p, n, mat):
        return {'albedo': S.mix(S.vec3(0.3, 0.5, 0.8), S.vec3(0.85, 0.5, 0.7), S.fbm(p * 3.0)[:, None])}
    create_sdf_object(map=my_map, surface=my_surface, bounds={'min': [-0.6, -0.6, -0.6], 'max': [0.6, 0.9, 0.6]})

A GLSL program and a Python one produce the same Blender object; Python is slower (numpy on the CPU) and is meant
for small or one-off shapes.
"""

from __future__ import annotations

import numpy as np

F = np.float32


def vec3(x, y, z):
    return np.array([x, y, z], F)


def vec2(x, y):
    return np.array([x, y], F)


def _a(x):
    return np.asarray(x, F)


def length(v):
    v = _a(v)
    return np.sqrt(np.sum(v * v, axis=-1))


def dot(a, b):
    return np.sum(_a(a) * _a(b), axis=-1)


def clamp(x, lo, hi):
    return np.minimum(np.maximum(x, F(lo)), F(hi))


def mix(a, b, t):
    a, b, t = _a(a), _a(b), _a(t)
    return a + (b - a) * t


def fract(x):
    x = _a(x)
    return x - np.floor(x)


def smoothstep(e0, e1, x):
    t = clamp((_a(x) - F(e0)) / (F(e1) - F(e0)), 0.0, 1.0)
    return t * t * (F(3.0) - F(2.0) * t)


# --- the TSL builder math SDF_TSL re-exported for custom SDF authors, as numpy (float32, GLSL semantics) ---

def vec4(x, y, z, w):
    return np.array([x, y, z, w], F)


def float_(x):
    """TSL float(x) (a trailing underscore: `float` is Python's)."""
    return _a(x)


def abs_(x):
    return np.abs(_a(x))


def max_(a, b):
    return np.maximum(_a(a), _a(b))


def min_(a, b):
    return np.minimum(_a(a), _a(b))


def sin(x):
    return np.sin(_a(x))


def cos(x):
    return np.cos(_a(x))


def floor(x):
    return np.floor(_a(x))


def sign(x):
    return np.sign(_a(x))


def sqrt(x):
    return np.sqrt(_a(x))


def pow_(x, y):
    return np.power(_a(x), _a(y))


def exp(x):
    return np.exp(_a(x))


def log(x):
    return np.log(_a(x))


def acos(x):
    return np.arccos(_a(x))


def asin(x):
    return np.arcsin(_a(x))


def atan(y, x=None):
    """GLSL atan(y, x) with two arguments, atan(y_over_x) with one."""
    return np.arctan(_a(y)) if x is None else np.arctan2(_a(y), _a(x))


def mod(x, y):
    """GLSL mod: x - y * floor(x / y) (the sign of y, unlike C's fmod)."""
    x, y = _a(x), _a(y)
    return x - y * np.floor(x / y)


def step(edge, x):
    return (_a(x) >= _a(edge)).astype(F)


def cross(a, b):
    return np.cross(_a(a), _a(b)).astype(F)


def reflect(i, n):
    i, n = _a(i), _a(n)
    return i - F(2.0) * dot(n, i)[..., None] * n


def select(cond, a, b):
    """TSL select(cond, a, b): a where cond, else b (np.where)."""
    return np.where(cond, a, b)


def normalize(v):
    v = _a(v)
    return v / np.maximum(length(v)[..., None], F(1e-20))


# ------------------------------------------------------------------------------------------------ distances ---

def sd_sphere(p, r):
    return length(p) - F(r)


def sd_box(p, b):
    q = np.abs(_a(p)) - _a(b)
    return length(np.maximum(q, F(0))) + np.minimum(np.max(q, axis=-1), F(0))


def sd_round_box(p, b, r):
    return sd_box(p, b) - F(r)


def sd_capsule(p, a, b, r):
    pa, ba = _a(p) - _a(a), _a(b) - _a(a)
    h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0)
    return length(pa - ba * h[..., None]) - F(r)


def sd_cap2(p, a, b, r1, r2):
    pa, ba = _a(p) - _a(a), _a(b) - _a(a)
    h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0)
    return length(pa - ba * h[..., None]) - mix(F(r1), F(r2), h)


sd_round_cone = sd_cap2


def sd_ellipsoid(p, r):
    r = _a(r)
    d = _a(p) / r
    return (length(d) - F(1)) * F(np.min(r))


def sd_torus(p, t):
    p = _a(p)
    q = np.stack([np.sqrt(p[..., 0] ** 2 + p[..., 2] ** 2) - F(t[0]), p[..., 1]], -1)
    return length(q) - F(t[1])


def sd_cone(p, c, h):
    p = _a(p)
    q = F(h) * np.array([c[0] / c[1], -1.0], F)
    w = np.stack([np.sqrt(p[..., 0] ** 2 + p[..., 2] ** 2), p[..., 1]], -1)
    a = w - q * clamp(dot(w, q) / dot(q, q), 0.0, 1.0)[..., None]
    b = w - q * np.stack([clamp(w[..., 0] / q[0], 0.0, 1.0), np.ones_like(w[..., 0])], -1)
    k = np.sign(q[1])
    d = np.minimum(dot(a, a), dot(b, b))
    s = np.maximum(k * (w[..., 0] * q[1] - w[..., 1] * q[0]), k * (w[..., 1] - q[1]))
    return np.sqrt(d) * np.sign(s)


def sd_tri_prism(p, hx, hz):
    p = _a(p)
    q = np.abs(p)
    inner = np.maximum(q[..., 0] * F(0.866025) + p[..., 1] * F(0.5), -p[..., 1]) - F(hx) * F(0.5)
    return np.maximum(q[..., 2] - F(hz), inner)


# --------------------------------------------------------------------------------------------------- ops ----

def smin(a, b, k):
    a, b, k = _a(a), _a(b), F(k)
    h = clamp(F(0.5) + F(0.5) * (b - a) / k, 0.0, 1.0)
    return mix(b, a, h) - k * h * (F(1) - h)


def smax(a, b, k):
    return -smin(-_a(a), -_a(b), k)


def op_u(a, b):
    """a, b: (dist, mat) pairs -> the nearer one's (dist, mat)."""
    cond = _a(a[0]) < _a(b[0])
    return np.where(cond, a[0], b[0]), np.where(cond, a[1], b[1])


def op_smooth_u(a, b, k):
    k = F(k)
    h = clamp(F(0.5) + F(0.5) * (_a(b[0]) - _a(a[0])) / k, 0.0, 1.0)
    d = mix(b[0], a[0], h) - k * h * (F(1) - h)
    return d, np.where(_a(a[0]) < _a(b[0]), a[1], b[1])


def op_sub(a, b):
    return np.maximum(-_a(a), _a(b))


def op_smooth_sub(a, b, k):
    return smax(-_a(a), b, k)


def op_int(a, b):
    return np.maximum(_a(a), _a(b))


def op_rotate_y(p, a):
    p = _a(p)
    c, s = np.cos(F(a)), np.sin(F(a))
    return np.stack([c * p[..., 0] + s * p[..., 2], p[..., 1], -s * p[..., 0] + c * p[..., 2]], -1)


def op_rotate_x(p, a):
    p = _a(p)
    c, s = np.cos(F(a)), np.sin(F(a))
    return np.stack([p[..., 0], c * p[..., 1] - s * p[..., 2], s * p[..., 1] + c * p[..., 2]], -1)


def op_rotate_z(p, a):
    p = _a(p)
    c, s = np.cos(F(a)), np.sin(F(a))
    return np.stack([c * p[..., 0] - s * p[..., 1], s * p[..., 0] + c * p[..., 1], p[..., 2]], -1)


def op_mirror_x(p):
    p = _a(p).copy()
    p[..., 0] = np.abs(p[..., 0])
    return p


def op_mirror_z(p):
    p = _a(p).copy()
    p[..., 2] = np.abs(p[..., 2])
    return p


# ------------------------------------------------------------------------------------------------- noise ----

_HASH_OFFSET = np.array([0.71, 0.113, 0.419], F)


def hash(p):  # noqa: A001 - the engine's name
    # float32, operation by operation: the GLSL _hash is `precise`, so the GPU computes exactly this
    p = fract(_a(p) * F(0.3183099) + _HASH_OFFSET) * F(17.0)
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    return fract(x * y * z * (x + y + z))


_CORNERS = [np.array(c, F) for c in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0),
                                     (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1))]


def vnoise(x):
    x = _a(x)
    i = np.floor(x)
    f = x - i
    f = f * f * (F(3.0) - F(2.0) * f)
    c = [hash(i + o) for o in _CORNERS]
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    return mix(mix(mix(c[0], c[1], fx), mix(c[2], c[3], fx), fy),
               mix(mix(c[4], c[5], fx), mix(c[6], c[7], fx), fy), fz)


def fbm(p):
    v, a, pp = np.zeros(_a(p).shape[:-1], F), F(0.5), _a(p)
    for _ in range(4):
        v = v + vnoise(pp) * a
        pp = pp * F(2.03)
        a = a * F(0.5)
    return v


def fbm6(p):
    v, a, pp = np.zeros(_a(p).shape[:-1], F), F(0.5), _a(p)
    for _ in range(6):
        v = v + vnoise(pp) * a
        pp = pp * F(2.07)
        a = a * F(0.5)
    return v


# --------------------------------------------------------------------- time and uniforms of a Python SDF ----
# TSL's `time` node and `uniform(v)` nodes let an engine map() animate and take live knobs. A Python map() reads the
# program it is being evaluated for: S.time is its uTime (seconds) and S.uniform('uName') the current value of a
# uniform the spec declared (uniforms={'uName': ...}), so bake() and set_uniform() drive Python SDFs too.
_CURRENT = [None]


class current:
    """with current(program): Python stages called inside read that program's uTime and uniforms."""

    def __init__(self, prog):
        self.prog = prog

    def __enter__(self):
        self._prev = _CURRENT[0]
        _CURRENT[0] = self.prog
        return self.prog

    def __exit__(self, *exc):
        _CURRENT[0] = self._prev
        return False


def uniform(name, default=None):
    """The current value of a spec uniform ('uRadius' or 'radius') as float32 (a scalar, or an array for vectors)."""
    prog = _CURRENT[0]
    if prog is None:
        if default is None:
            raise RuntimeError(f'SDF_NP.uniform({name!r}): no SDF is being evaluated')
        return _a(default)
    vals = prog.values
    if name not in vals:
        alt = 'u' + name[:1].upper() + name[1:]
        if alt in vals:
            name = alt
        elif default is not None:
            return _a(default)
        else:
            raise KeyError(f'{prog.label}: no uniform {name!r}')
    v = vals[name]
    return F(v) if isinstance(v, float) else _a(v)


def shade_surface(c, shade_as='albedo'):
    """A Python shade()'s colour as SdfSurface fields: base colour (clamped) or emission (shade_as='emission')."""
    c = np.maximum(_a(c), F(0.0))
    if shade_as == 'emission':
        return {'albedo': (0.0, 0.0, 0.0), 'roughness': 1.0, 'emission': c, 'specular': 0.0}
    return {'albedo': np.minimum(c, F(1.0)), 'roughness': 0.6}


class _Lib:
    """SDF_NP: the library as one namespace (S.sd_sphere ...), the way SDF_TSL was one object."""

    def __init__(self):
        for k, v in list(globals().items()):
            if callable(v) and not k.startswith('_') and k not in ('annotations', 'current', 'shade_surface'):
                setattr(self, k, v)
                if k.endswith('_'):                 # float_ / abs_ / max_ / min_ / pow_ are S.float, S.abs ...
                    setattr(self, k[:-1], v)

    @property
    def time(self):
        """TSL's `time`: the uTime (seconds) of the SDF being evaluated (0 outside an evaluation)."""
        prog = _CURRENT[0]
        return F(prog.values.get('uTime', 0.0)) if prog is not None else F(0.0)

    def __repr__(self):
        return '<SDF_NP: ' + ', '.join(sorted(k for k in vars(self))) + ', time>'


SDF_NP = _Lib()


# ------------------------------------------------------------------------------------ CPU evaluation paths ---

def call_map(fn, points):
    """(d, mat) arrays from a Python map(p): it may return d, (d, mat) or {'dist': d, 'mat': m}."""
    p = np.asarray(points, F).reshape(-1, 3)
    r = fn(p)
    if isinstance(r, dict):
        d, m = r['dist'], r.get('mat', 1.0)
    elif isinstance(r, tuple):
        d, m = r
    else:
        d, m = r, 1.0
    d = np.broadcast_to(np.asarray(d, F), (len(p),)).astype(F)
    m = np.broadcast_to(np.asarray(m, F), (len(p),)).astype(F)
    return d, m


def box_dist(p, bmin, bmax):
    bmin, bmax = np.asarray(bmin, F), np.asarray(bmax, F)
    return sd_box(np.asarray(p, F) - (bmin + bmax) * F(0.5), (bmax - bmin) * F(0.5))


_K = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], F)


def _clipped(prog, p):
    d, m = call_map(prog.map, p)
    if prog.values['sdfUseClip'] > 0.5:
        d = np.maximum(d, box_dist(p, prog.values['sdfClipMin'], prog.values['sdfClipMax']))
    return d, m


def grad(prog, points, h):
    p = np.asarray(points, F).reshape(-1, 3)
    with current(prog):
        d, m = _clipped(prog, p)
        g = np.zeros_like(p)
        for k in _K:
            g += k * _clipped(prog, p + k * F(h))[0][:, None]
    return d, m, g / F(4.0 * h)


class ShadeContext:
    """The engine's 4th shade argument, ctx = {softShadow, calcNormal, ro, rd}, for a Python shade(p, n, mat, ctx) or
    surface(p, n, mat, ctx). ro is the viewer in the SDF's local frame and rd the view ray. In a bake the viewer stands
    straight along each normal (as cameraPosition does in the GLSL), so ro = p + n * 1000 and rd = -n, and a fresnel
    term reads head-on. soft_shadow(ro, rd, mint, maxt, k) marches and calc_normal(p) differentiates the SDF's own
    map, as the engine's did (also under the engine's names, softShadow and calcNormal)."""

    def __init__(self, prog, p, n):
        self.prog = prog
        p, n = _a(p), _a(n)
        self.ro = p + n * F(1000.0)
        self.rd = -n

    def _dist(self, p):
        prog = self.prog
        if callable(prog.map):
            return call_map(prog.map, p)[0]
        return prog.dist(p)[0]                      # a GLSL map: its dist kernel on the GPU

    def calc_normal(self, p):
        """The engine's calcNormal: the tetrahedral difference of map at h = 0.0004, normalised."""
        p = _a(p).reshape(-1, 3)
        g = np.zeros_like(p)
        for k in _K:
            g += k * self._dist(p + k * F(0.0004))[:, None]
        return normalize(g)

    def soft_shadow(self, ro, rd, mint, maxt, k):
        """The engine's softShadow: 48 sphere-traced steps from ro along rd; 0 on a hit under 0.0005, else the
        min of k * h / t, clamped to [0, 1]."""
        ro = _a(ro).reshape(-1, 3)
        rd = np.broadcast_to(_a(rd), ro.shape)
        res = np.ones(len(ro), F)
        t = np.full(len(ro), F(mint))
        live = np.ones(len(ro), bool)
        for _ in range(48):
            idx = np.nonzero(live)[0]
            if len(idx) == 0:
                break
            h = self._dist(ro[idx] + rd[idx] * t[idx, None])
            hit = h < F(0.0005)
            res[idx[hit]] = F(0.0)
            go = idx[~hit]
            res[go] = np.minimum(res[go], F(k) * h[~hit] / t[go])
            t[go] += h[~hit]
            live[idx[hit]] = False
            live[go[t[go] >= F(maxt)]] = False
        return clamp(res, 0.0, 1.0)

    softShadow = soft_shadow
    calcNormal = calc_normal


def _takes_ctx(fn):
    """Whether a Python shade / surface takes the engine's 4th argument, ctx."""
    import inspect
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return False
    pos = [q for q in params if q.kind in (q.POSITIONAL_ONLY, q.POSITIONAL_OR_KEYWORD)]
    return len(pos) >= 4 or any(q.kind == q.VAR_POSITIONAL for q in params)


def call_shading(fn, prog, p, n, m):
    """A Python shade(p, n, mat) or surface(p, n, mat), or the engine's TSL form with ctx: shade(p, n, mat, ctx)."""
    if _takes_ctx(fn):
        return fn(p, n, m, ShadeContext(prog, p, n))
    return fn(p, n, m)


def surface(prog, points, project, grad_h, normal_h):
    p = np.asarray(points, F).reshape(-1, 3).copy()
    iso = F(prog.values.get('sdfIso', 0.0))
    for _ in range(int(project)):
        d, _m, g = grad(prog, p, grad_h)
        d = d - iso
        p -= (d / np.maximum(np.sum(g * g, -1), F(1e-12)))[:, None] * g
    d, m, g = grad(prog, p, normal_h)
    n = normalize(g)
    with current(prog):
        if callable(prog.surface):
            s = call_shading(prog.surface, prog, p, n, m)
        elif getattr(prog, 'surface_from_shade', False) and callable(prog.shade):
            s = shade_surface(call_shading(prog.shade, prog, p, n, m), prog.shade_as)
        else:
            s = {}
    out = surface_channels(s, len(p))
    out.update(position=p, dist=d, normal=n, mat=m)
    return out


def surface_channels(s, nn):
    """A Python surface()'s dict (any SdfSurface field, snake_case: albedo, roughness, metallic, emission, sheen,
    sheen_tint, subsurface, coat, specular, transmission; scalars or per-point arrays) as full channel arrays."""
    s = s or {}

    def ch(key, default, width):
        v = s.get(key, default)
        v = np.asarray(v, F)
        if width == 1:
            return np.broadcast_to(v.reshape(-1) if v.ndim else v, (nn,)).astype(F)
        return np.broadcast_to(v, (nn, width)).astype(F)

    return {
        'albedo': ch('albedo', (0.8, 0.8, 0.8), 3), 'roughness': ch('roughness', 0.5, 1),
        'emission': ch('emission', (0, 0, 0), 3), 'metallic': ch('metallic', 0.0, 1),
        'sheen_tint': ch('sheen_tint', (1, 1, 1), 3), 'sheen': ch('sheen', 0.0, 1),
        'subsurface': ch('subsurface', 0.0, 1), 'coat': ch('coat', 0.0, 1), 'specular': ch('specular', 0.5, 1),
        'transmission': ch('transmission', 0.0, 1),
    }
