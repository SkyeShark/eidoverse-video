"""The mask language (build/palettes.py's parse trees) compiled to GLSL, for the palette bake's kernels
(SURFACING_DESIGN.md 2.1, 2.3). Its twin is palettes.evaluate: on noise-free expressions the two agree to float32;
noise(), fbm() and cells() compile to Blender's own noise (surface/noise.glsl) at the coordinates the material's
nodes read (build/surfacing.py's _Compiler), so a term evaluated in the bake equals the shader's.

    from eidoblend.terrain.surface import expr_glsl as XG
    c = XG.Compiler(read=lambda name: f'm_{name}', constants=pal['constants'], noise3=True, texel_m=8.0)
    src = c.expr('smoothstep(30, 45, slope + 5*(fbm(80, 3) - 0.5))')   # a GLSL float expression
    c.names                                  # the maps it reads (the kernel provides `read(name)` for each)
    c.helpers()                              # the GLSL functions the expressions call (noise.glsl not included)

The position is `uPos` in the generated code's frame: a vec3 the kernel defines (world x, y and the ground's z).
texel_m: the footprint the bake samples at; a noise term's deviation from its mean is scaled by
smoothstep(1, 4, scale / texel) and fbm's detail dropped to log2(scale / (2 texel)), so a term finer than a texel
reads its mean instead of aliasing (the material's footprint rule, SURFACING_DESIGN.md 3.2). texel_m=None keeps every
term at full strength (the parity tests); texel_m='uniform' computes both in the shader from the uniform uFoot
(metres; the kernel declares it and includes FOOTPRINT), so one source serves every level."""
from __future__ import annotations

import math

HELPERS = r'''
float xg_smooth(float e0, float e1, float x) {
  if (e1 == e0) return x >= e0 ? 1.0 : 0.0;
  float t = clamp((x - e0) / (e1 - e0), 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}
float xg_div(float a, float b) { return a / (abs(b) < 1e-12 ? 1e-12 : b); }
float xg_pow(float a, float b) { return pow(max(a, 0.0), b); }
'''

# Compiler(texel_m='uniform'): the footprint fade and fbm detail at the uniform uFoot (Compiler._fade, ._detail)
FOOTPRINT = r'''
float xg_fade(float s) {
  float t = clamp((s / uFoot - 1.0) / 3.0, 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}
float xg_detail(float s, float d) { return min(d, max(0.0, log2(max(s / (2.0 * uFoot), 1e-9)))); }
'''


def _d(v):
    """A number as a GLSL literal, a GLSL expression (str) as it is."""
    return v if isinstance(v, str) else _f(v)


def _mul(k, v):
    """k * v as GLSL: folded when v is a number."""
    return f'({_f(k)} * {v})' if isinstance(v, str) else _f(k * v)


def _f(v):
    """A float literal GLSL reads exactly as Python's float32 of it."""
    v = float(v)
    if math.isinf(v):
        return '3.4e38' if v > 0 else '-3.4e38'
    s = repr(v)
    if 'e' in s or 'E' in s:
        m, e = s.lower().split('e')
        if '.' not in m:
            m += '.0'
        return f'{m}e{int(e)}'
    if '.' not in s:
        s += '.0'
    return s


class Compiler:
    """Expressions -> GLSL float expressions over `read(name)` (a GLSL expression per map name) and uPos."""

    def __init__(self, read, constants=None, noise3=True, texel_m=None, flat=False):
        from ..build import palettes as P
        self.P = P
        self.read = read
        self.consts = dict(P.CONSTANTS)
        self.consts.update(constants or {})
        self.noise3 = bool(noise3)
        self.texel = texel_m
        self.flat = bool(flat)
        self.names = set()
        self.noises = {}                                  # key -> (glsl name, glsl definition)

    def expr(self, src):
        t = self.P.parse(src) if not isinstance(src, tuple) else src
        return self._c(t)

    def _c(self, t):
        k = t[0]
        if k == 'num':
            return _f(t[1])
        if k == 'const':
            return _f(self.consts.get(t[1], self.P.CONSTANTS[t[1]]))
        if k == 'mask':
            self.names.add(t[1])
            return f'({self.read(t[1])})'
        if k == 'neg':
            return f'(-{self._c(t[1])})'
        if k == 'op':
            a, b = self._c(t[2]), self._c(t[3])
            if t[1] == '/':
                return f'xg_div({a}, {b})'
            return f'({a} {t[1]} {b})'
        f, args = t[1], t[2]
        if f in ('noise', 'fbm', 'cells'):
            if self.flat:
                return '0.5'
            seed = int(args[1][1]) if len(args) > 1 else 0
            scale = float(args[0][1])
            if f == 'cells':
                return self._cells(scale, seed, float(args[2][1]) if len(args) > 2 else 0.0)
            return self._noise(f, scale, seed)
        v = [self._c(a) for a in args]
        if f == 'smoothstep':
            return f'xg_smooth({v[0]}, {v[1]}, {v[2]})'
        if f in ('min', 'max'):
            out = v[0]
            for e in v[1:]:
                out = f'{f}({out}, {e})'
            return out
        if f == 'clamp':
            return f'clamp({v[0]}, {v[1]}, {v[2]})'
        if f == 'abs':
            return f'abs({v[0]})'
        if f == 'pow':
            return f'xg_pow({v[0]}, {v[1]})'
        if f == 'mix':
            return f'({v[0]} + ({v[1]} - {v[0]}) * {v[2]})'
        raise self.P.ExprError(f)

    def _fade(self, scale):
        """The footprint fade of a term of `scale` metres: a number, or a GLSL expression with texel_m='uniform'."""
        if self.texel is None:
            return 1.0
        if self.texel == 'uniform':
            return f'xg_fade({_f(scale)})'
        r = scale / float(self.texel)
        t = min(max((r - 1.0) / 3.0, 0.0), 1.0)
        return t * t * (3.0 - 2.0 * t)

    def _detail(self, scale, detail):
        if self.texel is None:
            return detail
        if self.texel == 'uniform':
            return f'xg_detail({_f(scale)}, {_f(detail)})'
        return float(min(detail, max(0.0, math.log2(max(scale / (2.0 * float(self.texel)), 1e-9)))))

    def _noise(self, f, scale, seed):
        """noise(): 3D (landscape palettes) or 4D noise, detail 2, roughness 0.5, stretched x2.5 about 0.5; fbm():
        3D, detail 5, roughness 0.6, stretched x3; both clamped to 0..1 (surfacing._Compiler.noise / .fbm)."""
        key = (f, scale, seed)
        if key not in self.noises:
            name = f'xg_{f}{len(self.noises)}'
            fade = self._fade(scale)
            if f == 'fbm':
                n = self.node3(scale, self._detail(scale, 5.0), 0.6, 5.3 + 1.9 * seed)
                body = f'clamp(({n} - 0.5) * {_mul(3.0, fade)} + 0.5, 0.0, 1.0)'
            else:
                if self.noise3:
                    n = self.node3(scale, self._detail(scale, 2.0), 0.5, 0.37 + 7.31 * seed)
                else:
                    n = (f'bn_noise_node4(uPos, {_f(0.37 + 7.31 * seed + 0.013 * scale)}, {_f(1.0 / scale)}, '
                         f'{_d(self._detail(scale, 2.0))}, 0.5)')
                body = f'clamp(({n} - 0.5) * {_mul(2.5, fade)} + 0.5, 0.0, 1.0)'
            self.noises[key] = (name, body)
        return self.noises[key][0]

    @staticmethod
    def node3(scale_m, detail, roughness, seed):
        """surfacing._noise3: a 3D Noise Texture at (pos + off scale_m) x (1 / scale_m), off from the seed."""
        off = (37.7 * seed + 11.3, -51.9 * seed + 7.1, 23.3 * seed - 3.7)
        o = ', '.join(_f(v * float(scale_m)) for v in off)
        return (f'bn_noise_node3(uPos + vec3({o}), {_f(1.0 / max(float(scale_m), 1e-6))}, {_d(detail)}, '
                f'{_f(roughness)})')

    def _cells(self, scale, seed, k):
        """cells(): Blender's Voronoi F1 cell colour (red) of (x, y) + (97.13 seed, -61.7 seed), or of (x, y, k z)
        (3D) with z_stretch k (surfacing._Compiler.cells). A cell value has no mean to fade to: kept as it is."""
        key = ('cells', scale, seed, k)
        if key not in self.noises:
            name = f'xg_cells{len(self.noises)}'
            off = f'vec3({_f(97.13 * seed)}, {_f(-61.7 * seed)}, 0.0)'
            if k > 0.0:
                body = (f'bn_voronoi_f1_colour3((uPos + {off}) * vec3(1.0, 1.0, {_f(k)}), '
                        f'{_f(1.0 / max(scale, 1e-6))}, 1.0).x')
            else:
                body = f'bn_voronoi_f1_colour2((uPos + {off}).xy, {_f(1.0 / max(scale, 1e-6))}, 1.0).x'
            self.noises[key] = (name, body)
        return self.noises[key][0]

    def declarations(self):
        """GLSL statements that define the noise terms the expressions use: `float xg_noise0 = ...;` (put them
        where uPos is defined, before the expressions)."""
        return '\n'.join(f'  float {n} = {b};' for n, b in self.noises.values())

    @staticmethod
    def helpers():
        return HELPERS


def flat_twin(expr, maps, constants=None):
    """palettes.evaluate with every noise at its mean: what Compiler(flat=True) computes."""
    from ..build import palettes as P
    return P.evaluate(expr, maps, constants=constants, flat=True)


__all__ = ['Compiler', 'HELPERS', 'FOOTPRINT', 'flat_twin']
