"""World-space noise in metres (design sections 2.4 and 3: Ekigar's noise.py and field_cpu.snap_freq, moved).

Inputs must be functions of world position (design finding 2): a level samples the same function at its own cell
centres, so a place has the same uplift, erodibility and threshold at every level. Every function here takes world
x, y in metres (arrays) and a wavelength in metres (the noise lattice's spacing: features about that size).

    from eidoblend.terrain.core import world_noise as N
    x, y = level.xy()
    n = N.gradient(x, y, 400.0, seed=3)                  # Ekigar's gradient noise, one lattice
    v, dx, dy = N.gradient(x, y, 400.0, seed=3, derivatives=True)   # analytic derivatives, per metre
    f = N.fbm(x, y, 2000.0, octaves=5, seed=3)           # standard deviation 1/3 for any octaves and gain
    r = N.ridged(x, y, 1500.0, octaves=4, seed=3)        # ridges where the noise crosses zero, -1..1
    xw, yw = N.warp(x, y, amp_m=300.0, wavelength_m=3000.0, seed=4)   # domain warp
    F = N.field({'kind': 'sum', 'terms': [{'kind': 'fbm', 'wavelength_m': 2000, 'amp': 0.6},
                                          {'kind': 'fbm', 'wavelength_m': 300, 'amp': 0.6, 'seed': 1}]}, x, y)
    w = N.snap_wavelength(900.0, 8000.0)                  # 888.9 m: a whole number of lattice cells per tile
    N.snap_freq(freq, tile)                               # Ekigar's, for frequencies

Periodic tiles (dunes) pass period_m: each octave's lattice then wraps over the tile, which needs the wavelength to
divide the period (snap_wavelength) and an integer lacunarity; anything else raises rather than leaving a seam.

hash2 is Ekigar's integer lattice hash bit for bit; a seed offsets the lattice (an integer offset per seed and
octave, from the PCG hash), so seeds give unrelated fields and octaves are not aligned at the origin.
"""

from __future__ import annotations

import math

import numpy as np

HASH_BIAS = 1 << 23
_M1 = np.uint32(0x27d4eb2d)
_M2 = np.uint32(0x85ebca6b)
_M3 = np.uint32(0x2c1b3c6d)
_M4 = np.uint32(0x297a2d39)
_S13, _S15, _S16 = np.uint32(13), np.uint32(15), np.uint32(16)
GRADIENT_STD = 0.1761                  # standard deviation of one lattice of gradient(), measured over 4M points
_OFFSET_RANGE = 1 << 20


def round_half_up(v):
    """JS Math.round: halves round toward +infinity."""
    return int(math.floor(v + 0.5))


def snap_freq(freq, tile):
    """Nearest frequency to `freq` whose period over `tile` is a whole number of cells (unchanged when not tiling).
    Ekigar's field_cpu.snap_freq."""
    if not (tile and tile > 0):
        return freq
    n = max(1, round_half_up(freq * tile))
    return n / tile


def snap_wavelength(wavelength_m, period_m):
    """The wavelength nearest `wavelength_m` that fits a whole number of times in `period_m` (unchanged when
    period_m is None)."""
    if not period_m:
        return float(wavelength_m)
    return float(period_m) / max(1, round_half_up(float(period_m) / float(wavelength_m)))


def _pcg(v):
    v = np.uint32(v & 0xFFFFFFFF)
    with np.errstate(over='ignore'):
        state = v * np.uint32(747796405) + np.uint32(2891336453)
        word = ((state >> ((state >> np.uint32(28)) + np.uint32(4))) ^ state) * np.uint32(277803737)
        return int((word >> np.uint32(22)) ^ word)


def lattice_offset(seed, octave=0):
    """The integer lattice offset (ox, oy) of a seed and octave: 0 .. 2^20."""
    if seed == 0 and octave == 0:
        return 0, 0                                        # seed 0, octave 0 is Ekigar's own lattice
    a = _pcg(_pcg(int(seed) & 0xFFFFFFFF) + int(octave) * 0x9E3779B9)
    b = _pcg(a ^ 0x68E31DA4)
    return a % _OFFSET_RANGE, b % _OFFSET_RANGE


def hash2(ix, iy):
    """Ekigar's lattice hash of integer cells (already wrapped): gradient (gx, gy) in [-1, 1)."""
    wx = ((np.asarray(ix, np.int64) + HASH_BIAS) & 0xFFFFFFFF).astype(np.uint32)
    wy = ((np.asarray(iy, np.int64) + HASH_BIAS) & 0xFFFFFFFF).astype(np.uint32)
    with np.errstate(over='ignore'):
        h = (wx * _M1) ^ (wy * _M2)
        h ^= h >> _S15
        h *= _M3
        h ^= h >> _S13
        h *= _M4
        h ^= h >> _S16
    gx = (h & np.uint32(0xFFFF)).astype(np.float64) * (1.0 / 32767.5) - 1.0
    gy = (h >> _S16).astype(np.float64) * (1.0 / 32767.5) - 1.0
    return gx, gy


def lattice_noise(px, py, period=None, offset=(0, 0), derivatives=False):
    """Ekigar's noised on lattice coordinates (px, py) (cells of the lattice), wrapping over `period` cells (an
    integer, or None), with the lattice shifted by an integer `offset`. Returns the value, or (value, d/dpx, d/dpy)."""
    px = np.asarray(px, np.float64)
    py = np.asarray(py, np.float64)
    fx0 = np.floor(px)
    fy0 = np.floor(py)
    fx = px - fx0
    fy = py - fy0
    ix = fx0.astype(np.int64) + int(offset[0])
    iy = fy0.astype(np.int64) + int(offset[1])
    if period:
        p = int(period)
        ix0, ix1 = np.mod(ix, p), np.mod(ix + 1, p)
        iy0, iy1 = np.mod(iy, p), np.mod(iy + 1, p)
    else:
        ix0, ix1, iy0, iy1 = ix, ix + 1, iy, iy + 1
    ux = fx * fx * fx * (fx * (fx * 6.0 - 15.0) + 10.0)
    uy = fy * fy * fy * (fy * (fy * 6.0 - 15.0) + 10.0)
    gax, gay = hash2(ix0, iy0)
    gbx, gby = hash2(ix1, iy0)
    gcx, gcy = hash2(ix0, iy1)
    gdx, gdy = hash2(ix1, iy1)
    va = gax * fx + gay * fy
    vb = gbx * (fx - 1.0) + gby * fy
    vc = gcx * fx + gcy * (fy - 1.0)
    vd = gdx * (fx - 1.0) + gdy * (fy - 1.0)
    q = va - vb - vc + vd
    value = va + ux * (vb - va) + uy * (vc - va) + ux * uy * q
    if not derivatives:
        return value
    dux = fx * fx * 30.0 * (fx * (fx - 2.0) + 1.0)
    duy = fy * fy * 30.0 * (fy * (fy - 2.0) + 1.0)
    dx = (gax + ux * (gbx - gax) + uy * (gcx - gax) + ux * uy * (gax - gbx - gcx + gdx) + dux * (uy * q + vb - va))
    dy = (gay + ux * (gby - gay) + uy * (gcy - gay) + ux * uy * (gay - gby - gcy + gdy) + duy * (ux * q + vc - va))
    return value, dx, dy


def _period_cells(period_m, wavelength_m):
    if not period_m:
        return None
    c = float(period_m) / float(wavelength_m)
    if abs(c - round(c)) > 1e-6:
        raise ValueError(f'wavelength {wavelength_m:g} m does not divide the tile period {period_m:g} m; use '
                         f'snap_wavelength({wavelength_m:g}, {period_m:g}) = {snap_wavelength(wavelength_m, period_m):g}')
    return int(round(c))


def gradient(x, y, wavelength_m, seed=0, period_m=None, derivatives=False, octave=0):
    """One lattice of gradient noise at world (x, y) metres; values about +-0.7 (std GRADIENT_STD). With
    derivatives: (value, d/dx, d/dy), the derivatives per metre."""
    w = float(wavelength_m)
    r = lattice_noise(np.asarray(x, np.float64) / w, np.asarray(y, np.float64) / w, _period_cells(period_m, w),
                      lattice_offset(seed, octave), derivatives)
    if not derivatives:
        return r
    return r[0], r[1] / w, r[2] / w


def _octaves(wavelength_m, octaves, lacunarity, gain, period_m):
    if period_m and abs(lacunarity - round(lacunarity)) > 1e-9:
        raise ValueError(f'a periodic fbm needs an integer lacunarity, got {lacunarity}')
    w, a = float(wavelength_m), 1.0
    out = []
    for i in range(int(octaves)):
        out.append((i, w, a))
        w /= lacunarity
        a *= gain
    return out


def fbm(x, y, wavelength_m, octaves=4, lacunarity=2.0, gain=0.5, seed=0, period_m=None, derivatives=False):
    """Fractal sum of `octaves` lattices from `wavelength_m` down by `lacunarity`, amplitudes falling by `gain`;
    normalised to a standard deviation of 1/3 (so +-1 holds nearly every value) for any octaves and gain. With
    derivatives: (value, d/dx, d/dy) per metre, with the same normalisation."""
    octs = _octaves(wavelength_m, octaves, lacunarity, gain, period_m)
    norm = (1.0 / 3.0) / (GRADIENT_STD * math.sqrt(sum(a * a for _, _, a in octs)))
    v = dx = dy = 0.0
    for i, w, a in octs:
        r = gradient(x, y, w, seed, period_m, derivatives, octave=i)
        if derivatives:
            v, dx, dy = v + a * r[0], dx + a * r[1], dy + a * r[2]
        else:
            v = v + a * r
    if derivatives:
        return v * norm, dx * norm, dy * norm
    return v * norm


def ridged(x, y, wavelength_m, octaves=4, lacunarity=2.0, gain=0.5, seed=0, period_m=None):
    """Ridged noise: each octave 1 - 2 |n| / 0.7 (a ridge where the noise crosses zero), summed by amplitude and
    divided by the amplitude sum: about -1..1, ridges near 1."""
    octs = _octaves(wavelength_m, octaves, lacunarity, gain, period_m)
    v = 0.0
    for i, w, a in octs:
        v = v + a * (1.0 - 2.0 * np.abs(gradient(x, y, w, seed, period_m, octave=i)) / 0.7)
    return v / sum(a for _, _, a in octs)


def warp(x, y, amp_m, wavelength_m, seed=0, octaves=3, period_m=None):
    """Domain warp: (x + amp fbm1, y + amp fbm2), two independent fbm fields (std 1/3) scaled to amp_m metres."""
    wx = fbm(x, y, wavelength_m, octaves, seed=seed * 2 + 101, period_m=period_m)
    wy = fbm(x, y, wavelength_m, octaves, seed=seed * 2 + 102, period_m=period_m)
    return np.asarray(x, np.float64) + amp_m * wx, np.asarray(y, np.float64) + amp_m * wy


# ----------------------------------------------------------------------------------- JSON field specifications ---

FIELD_KINDS = ('const', 'gradient', 'fbm', 'ridged', 'sum', 'product', 'warp')


def field(spec, x, y, seed=0):
    """Evaluate a JSON field spec at world (x, y): recipes describe their noise inputs as data.

        {'kind': 'const', 'value': v}
        {'kind': 'gradient' | 'fbm' | 'ridged', 'wavelength_m': w, 'octaves': 4, 'lacunarity': 2, 'gain': 0.5,
         'seed': 0, 'period_m': None, 'amp': 1, 'offset': 0}        -> offset + amp * noise
        {'kind': 'sum' | 'product', 'terms': [spec, ...]}
        {'kind': 'warp', 'amp_m': a, 'wavelength_m': w, 'seed': 0, 'of': spec}
    A spec's own 'seed' adds to the call's seed. Returns float64 like x."""
    if isinstance(spec, (int, float)):
        return np.full(np.shape(x), float(spec))
    kind = spec.get('kind')
    s = int(seed) + int(spec.get('seed', 0))
    amp, off = float(spec.get('amp', 1.0)), float(spec.get('offset', 0.0))
    if kind == 'const':
        return np.full(np.shape(x), float(spec['value']))
    if kind in ('gradient', 'fbm', 'ridged'):
        w, per = float(spec['wavelength_m']), spec.get('period_m')
        if kind == 'gradient':
            v = gradient(x, y, w, s, per)
        else:
            f = fbm if kind == 'fbm' else ridged
            v = f(x, y, w, int(spec.get('octaves', 4)), float(spec.get('lacunarity', 2.0)),
                  float(spec.get('gain', 0.5)), s, per)
        return off + amp * v
    if kind in ('sum', 'product'):
        terms = [field(t, x, y, s) for t in spec['terms']]
        out = terms[0]
        for t in terms[1:]:
            out = out + t if kind == 'sum' else out * t
        return off + amp * out
    if kind == 'warp':
        xw, yw = warp(x, y, float(spec['amp_m']), float(spec['wavelength_m']), s, int(spec.get('octaves', 3)),
                      spec.get('period_m'))
        return off + amp * field(spec['of'], xw, yw, s)
    raise ValueError(f'field kind {kind!r} is not one of {FIELD_KINDS}')


# ------------------------------------------------------------------------------------- the GPU evaluation path ---
# numpy needs about 1.2 s per lattice at 1024^2 on this machine (design target: all inputs of a level <= 1 s), so
# production evaluates field specs in a compute kernel; field() above is its twin. Lattice coordinates are built from
# an integer base and a fractional origin computed in float64 on the CPU, so float32 keeps 1e-7 of a lattice cell.

GLSL_NOISE = r'''
vec2 eido_hash2(int ix, int iy) {                 /* Ekigar's hash2 on integer lattice cells, bit for bit */
  uint wx = uint(ix + 8388608);
  uint wy = uint(iy + 8388608);
  uint h = (wx * 0x27d4eb2du) ^ (wy * 0x85ebca6bu);
  h ^= h >> 15u;
  h *= 0x2c1b3c6du;
  h ^= h >> 13u;
  h *= 0x297a2d39u;
  h ^= h >> 16u;
  return vec2(float(h & 0xFFFFu), float(h >> 16u)) * (1.0 / 32767.5) - 1.0;
}
int eido_pmod(int i, int p) {                     /* exact floor modulo (GLSL % is undefined for negatives) */
  int q = int(floor(float(i) / float(p)));
  int r = i - p * q;
  if (r < 0) r += p;
  if (r >= p) r -= p;
  return r;
}
/* Ekigar's noised value at lattice cell (ix, iy) + fraction f, wrapping over p cells when p > 0 */
float eido_lattice(ivec2 ic, vec2 f, int p) {
  int ix0 = ic.x, ix1 = ic.x + 1, iy0 = ic.y, iy1 = ic.y + 1;
  if (p > 0) { ix0 = eido_pmod(ix0, p); ix1 = eido_pmod(ix1, p); iy0 = eido_pmod(iy0, p); iy1 = eido_pmod(iy1, p); }
  vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  vec2 ga = eido_hash2(ix0, iy0), gb = eido_hash2(ix1, iy0), gc = eido_hash2(ix0, iy1), gd = eido_hash2(ix1, iy1);
  float va = ga.x * f.x + ga.y * f.y;
  float vb = gb.x * (f.x - 1.0) + gb.y * f.y;
  float vc = gc.x * f.x + gc.y * (f.y - 1.0);
  float vd = gd.x * (f.x - 1.0) + gd.y * (f.y - 1.0);
  float q = va - vb - vc + vd;
  return va + u.x * (vb - va) + u.y * (vc - va) + u.x * u.y * q;
}
'''

KERNEL_FIELD = r'''//! sampler terms     two texels per lattice term: (mode, 1/w, amp, period), (base x, base y, frac x, frac y)
//! sampler disp      x, y: the cell's displacement in metres (a warp), zero when unwarped
//! image   outF r32f
//! uniform int uTerms
//! uniform float uCell
//! uniform float uConst
''' + GLSL_NOISE + r'''
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = imageSize(outF);
  if (!inside(p, n)) return;
  vec2 local = (vec2(p) + 0.5) * uCell + texelFetch(disp, p, 0).xy;
  float acc = uConst;
  for (int t = 0; t < uTerms; t++) {
    vec4 a = texelFetch(terms, ivec2(2 * t, 0), 0);
    vec4 b = texelFetch(terms, ivec2(2 * t + 1, 0), 0);
    vec2 lc = b.zw + local * a.y;
    vec2 fl = floor(lc);
    float v = eido_lattice(ivec2(b.xy) + ivec2(fl), lc - fl, int(a.w));
    acc += a.z * (a.x > 0.5 ? abs(v) : v);
  }
  imageStore(outF, p, vec4(acc, 0.0, 0.0, 0.0));
}
'''


def _leaf_terms(spec, seed, x0, y0):
    """A const / gradient / fbm / ridged spec as GPU lattice terms: ([(mode, 1/w, amp, period, bx, by, fx, fy)],
    constant). A periodic term's base is reduced modulo its period (the same cells, small numbers)."""
    kind = spec.get('kind')
    s = int(seed) + int(spec.get('seed', 0))
    amp, off = float(spec.get('amp', 1.0)), float(spec.get('offset', 0.0))
    if kind == 'const':
        return [], float(spec['value'])
    w0, per = float(spec['wavelength_m']), spec.get('period_m')
    if kind == 'gradient':
        octs, coef, const = [(0, w0, 1.0)], [amp], off
        mode = 0
    else:
        octs = _octaves(w0, int(spec.get('octaves', 4)), float(spec.get('lacunarity', 2.0)),
                        float(spec.get('gain', 0.5)), per)
        if kind == 'fbm':
            norm = (1.0 / 3.0) / (GRADIENT_STD * math.sqrt(sum(a * a for _, _, a in octs)))
            coef, const, mode = [amp * a * norm for _, _, a in octs], off, 0
        else:                                                         # ridged: a (1 - 2|n|/0.7) / sum a
            tot = sum(a for _, _, a in octs)
            coef, const, mode = [-amp * 2.0 * a / (0.7 * tot) for _, _, a in octs], off + amp, 1
    terms = []
    for (i, w, _a), c in zip(octs, coef):
        pc = _period_cells(per, w) or 0
        ox, oy = lattice_offset(s, i)
        bx, by = math.floor(x0 / w), math.floor(y0 / w)
        fx, fy = x0 / w - bx, y0 / w - by
        bx, by = bx + ox, by + oy
        if pc:
            bx, by = bx % pc, by % pc
        terms.append((mode, 1.0 / w, c, pc, bx, by, fx, fy))
    return terms, const


def field_gpu(spec, level, seed=0, as_texture=False, disp=None):
    """field(spec) at a level's cell centres, evaluated on the GPU: an (n, n) float32 array (or the R32F texture).
    `disp` (dx, dy) metres moves every sample point first (field(spec, x + dx, y + dy) in numpy terms). Sums of
    leaves go in one dispatch; products are multiplied in numpy; warps evaluate their displacement on the GPU first.
    Needs Blender (core/gpu.py)."""
    from . import gpu as G
    n = level.n
    k = G.kernel(source=KERNEL_FIELD, name='world_noise_field')

    def leaves(sp, s):
        """Flatten a sum of leaves into terms, or None when the spec needs more than one dispatch."""
        kind = sp.get('kind') if isinstance(sp, dict) else 'num'
        if kind == 'num':
            return [], float(sp)
        if kind in ('const', 'gradient', 'fbm', 'ridged'):
            return _leaf_terms(sp, s, level.x0, level.y0)
        if kind == 'sum' and float(sp.get('amp', 1.0)) == 1.0:
            ss = s + int(sp.get('seed', 0))
            terms, const = [], float(sp.get('offset', 0.0))
            for t in sp['terms']:
                r = leaves(t, ss)
                if r is None:
                    return None
                terms += r[0]
                const += r[1]
            return terms, const
        return None

    def dispatch(terms, const, disp):
        tt = np.zeros((1, max(2 * len(terms), 2), 4), np.float32)
        for t, (mode, iw, c, pc, bx, by, fx, fy) in enumerate(terms):
            if abs(bx) >= 1 << 24 or abs(by) >= 1 << 24:
                raise ValueError('world noise lattice base beyond float32 integers: world coordinates too large')
            tt[0, 2 * t] = (mode, iw, c, pc)
            tt[0, 2 * t + 1] = (bx, by, fx, fy)
        out = G.empty((n, n), channels=1)
        G.run(k, None, samplers={'terms': G.texture(tt), 'disp': disp}, images={'outF': out},
              uniforms={'uTerms': len(terms), 'uCell': level.cell, 'uConst': const})
        return G.read(out)[..., 0]

    def ev(sp, s, disp):
        r = leaves(sp, s)
        if r is not None:
            return dispatch(r[0], r[1], disp)
        kind = sp.get('kind')
        ss = s + int(sp.get('seed', 0))
        amp, off = float(sp.get('amp', 1.0)), float(sp.get('offset', 0.0))
        if kind in ('sum', 'product'):
            parts = [ev(t, ss, disp) for t in sp['terms']]
            out = parts[0]
            for q in parts[1:]:
                out = out + q if kind == 'sum' else out * q
            return (off + amp * out).astype(np.float32)
        if kind == 'warp':
            a, w, octs, per = float(sp['amp_m']), float(sp['wavelength_m']), int(sp.get('octaves', 3)), \
                sp.get('period_m')
            d = G.read(disp)
            dx = ev({'kind': 'fbm', 'wavelength_m': w, 'octaves': octs, 'period_m': per, 'amp': a}, ss * 2 + 101,
                    disp)
            dy = ev({'kind': 'fbm', 'wavelength_m': w, 'octaves': octs, 'period_m': per, 'amp': a}, ss * 2 + 102,
                    disp)
            nd = G.texture(np.stack([d[..., 0] + dx, d[..., 1] + dy], axis=-1))
            return (off + amp * ev(sp['of'], ss, nd)).astype(np.float32)
        raise ValueError(f'field kind {kind!r} is not one of {FIELD_KINDS}')

    d0 = G.empty((n, n), channels=2) if disp is None else G.texture(np.stack([np.asarray(disp[0], np.float32),
                                                                              np.asarray(disp[1], np.float32)], -1))
    res = ev(spec, int(seed), d0)
    return G.texture(res) if as_texture else np.ascontiguousarray(res, np.float32)
