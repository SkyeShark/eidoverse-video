"""Numpy twins of the terrain kernels: the harness (design section 2.5).

A twin does its kernel's arithmetic in float32 numpy, reading neighbours as whole-array shifts. Twins are test oracles
at 64-128 cells, never a production path. The parity test runs ONE dispatch against its twin on a non-square random
field (96 wide x 80 tall, so an axis mix-up fails) with pins, in every boundary mode, and passes at
max |gpu - twin| <= 1e-4 x the field's range (per output channel). Multi-step runs diverge chaotically, so those are
compared by metrics, not texels.

Twins live with the code that owns the kernel (a solver module) and register themselves by the kernel's name:

    import numpy as np
    from eidoblend.terrain.core import twins as T

    @T.twin('creep')                                   # kernels/creep.glsl
    def creep(s, u):                                   # s: {sampler: (H, W, C) float32}, u: {uniform: value}
        h = s['st'][..., 0]
        for k in range(8):
            hq, ok = T.neighbour(h, k, u['uBound'])    # the k-th neighbour of every cell, and where it exists
            ...
        return {'outS': T.rgba(hn, s['st'][..., 1])}   # {image: (H, W, C)}, every declared image

    # in Blender (gpu.compute): one dispatch against the twin
    rep = T.parity('creep', {'st': st, 'par': par}, {'uDx': 7.8, ..., 'uBound': T.BOUND_OPEN})
    assert rep['ok'], T.report_text(rep)
    # in plain Python: the twin alone, its outputs checked against the kernel file's //! declarations
    out = T.run_twin('creep', inputs, uniforms)

Input helpers: random_field, pin_pattern, rgba, BOUNDARY_CASES.

The primitives below mirror common.glsl one for one: OFF, LEN, WISO, WISO_SUM, opp, BOUND_*, inside, wrap,
neighbour / shift (array shifts), pin_apply, world_xy, tan_deg, pcg / pcg2 / pcg3 / pcg4, u01, cell_hash. The PCG
hashes and u01 are bit-exact against the GPU; the float arithmetic agrees to rounding.

This module imports no bpy: twins run in plain Python (see blender/tests/terrain_new/core/plain_import.py for
loading the terrain core outside Blender).
"""

from __future__ import annotations

import difflib

import numpy as np

# --------------------------------------------------------------------------- common.glsl, mirrored one for one ---

OFF = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))   # (column step, row step): SW S SE W E NW N NE
LEN = np.array([1.41421356, 1.0, 1.41421356, 1.0, 1.0, 1.41421356, 1.0, 1.41421356], np.float32)
WISO = np.array([0.16666667, 0.66666667, 0.16666667, 0.66666667, 0.66666667, 0.16666667, 0.66666667, 0.16666667],
                np.float32)
WISO_SUM = np.float32(3.33333333)
BOUND_OPEN, BOUND_PERIODIC, BOUND_PINNED = 0, 1, 2
BOUNDARY_CASES = (('open', BOUND_OPEN), ('periodic', BOUND_PERIODIC), ('pinned', BOUND_PINNED))


def opp(k):
    """The opposite neighbour index (common.glsl opp)."""
    return 7 - k


def inside(i, j, w, h):
    return (i >= 0) & (j >= 0) & (i < w) & (j < h)


def wrap(q, n):
    """Periodic wrap for q in [-n, 2n) (common.glsl wrap); numpy's floor modulo for anything else."""
    return np.mod(q, n)


def shift(a, dx, dy, mode=BOUND_OPEN, fill=0.0):
    """`a` read at (column + dx, row + dy) for every cell, over the first two axes: (values, ok). Periodic mode wraps
    (ok is all True); the open and pinned modes put `fill` where the read falls off the grid, and ok is False there."""
    a = np.asarray(a)
    h, w = a.shape[:2]
    if mode == BOUND_PERIODIC:
        return np.roll(a, (-dy, -dx), axis=(0, 1)), np.ones((h, w), bool)
    out = np.full_like(a, fill)
    ok = np.zeros((h, w), bool)
    j0, j1 = max(0, -dy), min(h, h - dy)
    i0, i1 = max(0, -dx), min(w, w - dx)
    if j1 > j0 and i1 > i0:
        out[j0:j1, i0:i1] = a[j0 + dy:j1 + dy, i0 + dx:i1 + dx]
        ok[j0:j1, i0:i1] = True
    return out, ok


def neighbour(a, k, mode=BOUND_OPEN, fill=0.0):
    """The k-th neighbour field of `a` (common.glsl neighbour + texelFetch): (values, ok)."""
    dx, dy = OFF[k]
    return shift(a, dx, dy, mode, fill)


def on_edge(shape):
    h, w = shape[:2]
    e = np.zeros((h, w), bool)
    e[0, :] = e[-1, :] = e[:, 0] = e[:, -1] = True
    return e


def pin_apply(h, pin_w, pin_h):
    """common.glsl pin_apply: GLSL mix(h, pin_h, clamp(w, 0, 1)) = h (1 - a) + pin_h a."""
    a = np.clip(np.asarray(pin_w, np.float32), np.float32(0), np.float32(1))
    return (np.asarray(h, np.float32) * (np.float32(1) - a) + np.asarray(pin_h, np.float32) * a).astype(np.float32)


def world_xy(shape, lv):
    """Cell-centre world coordinates (x, y) of an (H, W) grid with lv = (x0, y0, cell), float32 like the kernel."""
    h, w = shape[:2]
    x0, y0, c = (np.float32(v) for v in lv)
    jj, ii = np.mgrid[0:h, 0:w].astype(np.float32)
    return x0 + (ii + np.float32(0.5)) * c, y0 + (jj + np.float32(0.5)) * c


def tan_deg(d):
    return np.tan(np.radians(np.asarray(d, np.float32))).astype(np.float32)


def _u32(v):
    """Integers (any sign) to uint32 by their low 32 bits: GLSL's uint(int) keeps the bit pattern."""
    a = np.asarray(v)
    if a.dtype == np.uint32:
        return a
    return (a.astype(np.int64) & 0xFFFFFFFF).astype(np.uint32)


_M1, _A1, _M2 = np.uint32(747796405), np.uint32(2891336453), np.uint32(277803737)
_S4, _S22, _S28, _S8 = np.uint32(4), np.uint32(22), np.uint32(28), np.uint32(8)


def pcg(v):
    """32-bit PCG hash (PCG-RXS-M-XS), bit for bit common.glsl's pcg."""
    v = _u32(v)
    with np.errstate(over='ignore'):
        state = v * _M1 + _A1
        word = ((state >> ((state >> _S28) + _S4)) ^ state) * _M2
        return (word >> _S22) ^ word


def pcg2(a, b):
    with np.errstate(over='ignore'):
        return pcg(pcg(a) + _u32(b))


def pcg3(a, b, c):
    with np.errstate(over='ignore'):
        return pcg(pcg(pcg(a) + _u32(b)) + _u32(c))


def pcg4(a, b, c, d):
    with np.errstate(over='ignore'):
        return pcg(pcg(pcg(pcg(a) + _u32(b)) + _u32(c)) + _u32(d))


def u01(hsh):
    """A hash to [0, 1) with 24 bits, exactly as the kernel's float(h >> 8u) * (1.0 / 16777216.0)."""
    return ((_u32(hsh) >> _S8).astype(np.float32) * np.float32(1.0 / 16777216.0)).astype(np.float32)


def cell_hash(shape, it, seed):
    """common.glsl cell_hash for every cell of an (H, W) grid at iteration `it` with `seed`."""
    h, w = shape[:2]
    jj, ii = np.mgrid[0:h, 0:w]
    return pcg4(ii, jj, np.full_like(ii, it), np.full_like(ii, seed))


# ------------------------------------------------------------------------------------------- the twin registry ---

TWINS = {}


def twin(name):
    """Decorator: register `fn(samplers, uniforms) -> {image: array}` as the twin of kernels/<name>.glsl."""
    def deco(fn):
        TWINS[name] = fn
        fn.kernel_name = name
        return fn
    return deco


def get_twin(name):
    if name in TWINS:
        return TWINS[name]
    near = difflib.get_close_matches(name, list(TWINS), n=3)
    raise KeyError(f'no twin registered for kernel {name!r}' + (f' (did you mean {near}?)' if near else '') +
                   '; import the module that defines it (twins register when their module is imported)')


# ------------------------------------------------------------------------------------------------ input helpers ---

def rgba(a, b=None, c=None, d=None):
    """Stack up to four (H, W) arrays into (H, W, 4) float32; None channels are zero."""
    first = next((np.asarray(x, np.float32) for x in (a, b, c, d) if x is not None), None)
    if first is None:
        raise ValueError('rgba needs at least one channel')
    out = np.zeros(first.shape[:2] + (4,), np.float32)
    for ch, x in enumerate((a, b, c, d)):
        if x is not None:
            out[..., ch] = x
    return out


def _box(a, r):
    """Separable box blur of radius r with edge clamping (for smooth test fields)."""
    for axis in (0, 1):
        n = a.shape[axis]
        idx = np.clip(np.arange(-r, n + r), 0, n - 1)
        p = np.take(a, idx, axis=axis)
        c = np.cumsum(p, axis=axis, dtype=np.float64)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
        a = (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis) - np.take(c, np.arange(n), axis=axis)) \
            / (2 * r + 1)
    return a


def random_field(shape=(80, 96), lo=0.0, hi=1.0, seed=0, smooth=0):
    """A random (H, W) float32 field in [lo, hi]: white noise, or smoothed by `smooth` box passes of radius 2 (so
    slopes look like ground rather than static), rescaled to the range."""
    rng = np.random.default_rng(seed)
    a = rng.random(tuple(shape[:2]))
    for _ in range(int(smooth)):
        a = _box(a, 2)
    a = (a - a.min()) / max(a.max() - a.min(), 1e-12)
    return (lo + (hi - lo) * a).astype(np.float32)


def pin_pattern(shape=(80, 96), seed=0, band=4, value=(0.0, 100.0)):
    """Test pins: (pin_w, pin_h). The weight ramps from 1 at the edge to 0 at `band` cells in (the border band, in
    small), plus a few random discs pinned fully (weight 1) and partly (0.5); the pinned heights are random in
    `value`."""
    h, w = shape[:2]
    rng = np.random.default_rng(seed + 7919)
    jj, ii = np.mgrid[0:h, 0:w]
    d = np.minimum(np.minimum(ii, w - 1 - ii), np.minimum(jj, h - 1 - jj)).astype(np.float32)
    pw = np.clip(1.0 - d / max(band, 1), 0.0, 1.0)
    for k in range(4):
        cx, cy, r = rng.uniform(0.2 * w, 0.8 * w), rng.uniform(0.2 * h, 0.8 * h), rng.uniform(3, 7)
        disc = (ii - cx) ** 2 + (jj - cy) ** 2 < r * r
        pw = np.where(disc, 1.0 if k % 2 == 0 else 0.5, pw)
    ph = rng.uniform(value[0], value[1], (h, w))
    return pw.astype(np.float32), ph.astype(np.float32)


# --------------------------------------------------------------------------------------------- running twins ---

def _spec_of(name):
    from . import gpu as G
    return G.load_source(name)[2]


def _prep_inputs(inputs, spec=None):
    out = {}
    for n, a in inputs.items():
        a = np.asarray(a, np.float32)
        if a.ndim == 2:
            a = a[:, :, None]
        if a.shape[2] == 3:
            a = np.concatenate([a, np.zeros(a.shape[:2] + (1,), np.float32)], axis=2)
        out[n] = np.ascontiguousarray(a)
    if spec is not None:
        missing = [s for s in spec.samplers if s not in out]
        extra = [s for s in out if s not in spec.samplers]
        if missing or extra:
            raise KeyError(f'kernel {spec.name!r} samplers {spec.samplers}: missing {missing}, unknown {extra}')
    return out


def _prep_uniforms(uniforms, spec=None):
    out = {}
    for n, v in (uniforms or {}).items():
        ty = spec.uniforms.get(n) if spec is not None else None
        if ty == 'int' or (ty is None and isinstance(v, (int, np.integer))):
            out[n] = int(v)
        elif ty is not None and ty.startswith('ivec'):
            out[n] = tuple(int(x) for x in v)
        elif ty is not None and ty.startswith('vec'):
            out[n] = np.asarray(v, np.float32)
        else:
            out[n] = np.float32(v)
    if spec is not None:
        missing = [u for u in spec.uniforms if u not in out]
        if missing:
            raise KeyError(f'kernel {spec.name!r}: uniforms not given: {missing}')
    return out


def run_twin(name_or_fn, inputs, uniforms, spec=None):
    """The twin's outputs {image: (H, W, C) float32}. `name_or_fn` is a kernel name (the registered twin, and the
    kernel file's declarations to check against) or a twin function (pass `spec` to check)."""
    if isinstance(name_or_fn, str):
        fn = get_twin(name_or_fn)
        spec = spec or _spec_of(name_or_fn)
    else:
        fn = name_or_fn
    s = _prep_inputs(inputs, spec)
    u = _prep_uniforms(uniforms, spec)
    shape = next(iter(s.values())).shape[:2] if s else None
    res = fn(s, u)
    out = {}
    for n, a in res.items():
        a = np.asarray(a, np.float32)
        out[n] = a[:, :, None] if a.ndim == 2 else a
    if spec is not None:
        from . import gpu as G
        for n, fmt in spec.images.items():
            if n not in out:
                raise KeyError(f'twin of {spec.name!r} did not return image {n!r}')
            c = G._FMT_CHANNELS[fmt]
            if out[n].shape[2] != c or (shape is not None and out[n].shape[:2] != shape):
                raise ValueError(f'twin of {spec.name!r}: image {n!r} is {out[n].shape}, the kernel writes '
                                 f'{shape} x {c} ({fmt})')
        extra = [n for n in out if n not in spec.images]
        if extra:
            raise KeyError(f'twin of {spec.name!r} returned images the kernel does not declare: {extra}')
    return out


def compare(got, want, tol=1e-4, channels=None):
    """Per output channel: max |got - want| against tol x the twin's range there. `channels` limits the check
    ({image: [channel, ...]}) when a kernel leaves some channels unused. Returns a report dict with 'ok' and
    'worst' (the largest error / range ratio) and one row per channel."""
    rows = []
    for n, w in want.items():
        g = got[n]
        if g.shape != w.shape:
            raise ValueError(f'image {n!r}: GPU {g.shape} vs twin {w.shape}')
        for c in range(w.shape[2]):
            if channels is not None and c not in channels.get(n, range(w.shape[2])):
                continue
            wc, gc = w[..., c].astype(np.float64), g[..., c].astype(np.float64)
            finite = bool(np.isfinite(gc).all() and np.isfinite(wc).all())
            err = float(np.max(np.abs(gc - wc))) if finite else float('inf')
            rng = float(wc.max() - wc.min()) if finite else 0.0
            scale = max(rng, 1e-6 * float(np.max(np.abs(wc))) if finite else 0.0, 1e-20)
            ratio = err / scale
            at = np.unravel_index(int(np.argmax(np.abs(gc - wc))), wc.shape) if finite else None
            rows.append({'image': n, 'channel': c, 'max_abs': err, 'range': rng, 'ratio': ratio,
                         'at_row_col': [int(at[0]), int(at[1])] if at is not None else None,
                         'ok': finite and ratio <= tol})
    worst = max((r['ratio'] for r in rows), default=0.0)
    return {'ok': all(r['ok'] for r in rows), 'worst': worst, 'tol': tol, 'channels': rows}


def report_text(rep):
    lines = [f"parity {'PASS' if rep['ok'] else 'FAIL'}: worst |gpu - twin| / range = {rep['worst']:.3g} "
             f"(tolerance {rep['tol']:g})"]
    for r in rep['channels']:
        lines.append(f"  {r['image']}[{r['channel']}]: max |d| {r['max_abs']:.4g} over range {r['range']:.4g} "
                     f"= {r['ratio']:.3g} at row/col {r['at_row_col']}{'' if r['ok'] else '   <-- FAIL'}")
    return '\n'.join(lines)


def parity(kernel, inputs, uniforms, twin=None, tol=1e-4, channels=None, defines=None):
    """In Blender: ONE dispatch of `kernel` (a name, a Kernel, or a path to a .glsl file) on `inputs`
    ({sampler: (H, W[, C]) array}) against its twin (registered by the kernel's name, or given). Returns the
    compare() report plus 'kernel', 'shape' and 'gpu_ms' (dispatch + readback)."""
    import time
    from . import gpu as G
    if isinstance(kernel, G.Kernel):
        k = kernel
    elif isinstance(kernel, str) and kernel.endswith('.glsl'):
        k = G.kernel(path=kernel, defines=defines)
    else:
        k = G.kernel(kernel, defines=defines)
    fn = twin or get_twin(k.name)
    s = _prep_inputs(inputs, k.spec)
    u = _prep_uniforms(uniforms, k.spec)
    shape = next(iter(s.values())).shape[:2]
    tex = {n: G.texture(a) for n, a in s.items()}
    for n, t in tex.items():                                       # the GPU must see exactly what the twin sees
        if not np.array_equal(G.read(t), s[n]):
            raise RuntimeError(f'texture round trip of {n!r} is not exact')
    outs = {n: G.empty(shape, fmt=fmt) for n, fmt in k.spec.images.items()}
    t0 = time.perf_counter()
    G.run(k, None, samplers=tex, images=outs, uniforms=u)
    got = {n: G.read(t) for n, t in outs.items()}
    ms = (time.perf_counter() - t0) * 1000.0
    want = run_twin(fn, s, u, spec=k.spec)
    rep = compare(got, want, tol, channels)
    rep.update(kernel=k.name, shape=[int(shape[0]), int(shape[1])], gpu_ms=round(ms, 3))
    return rep
