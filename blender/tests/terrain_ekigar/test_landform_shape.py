"""Ekigar's test/gpu/landform_shape.mjs, ported check for check: do the landforms have the SHAPE they claim?

  - the canyon cross-section: a flat floor (not the steepest part of the profile) and a real wall;
  - the mountain range covers the whole tile in mountains and is not a directional stripe;
  - active-footprint surface detail of the terrain landforms and of the terrace / surface filters, against the
    per-operator gates Ekigar set from renders it reviewed by eye.

Ekigar renders each field on the GPU and reads it back; here the port's own field (identical to Ekigar's, see the
parity tests) is measured with the same statistics, at the same default resolution (512; --n=256 to run faster).

    python blender/tests/terrain_ekigar/test_landform_shape.py [--n=512]
"""
import sys

import numpy as np

import _ekigar_load

ek = _ekigar_load.load()
N = 512
for a in sys.argv[1:]:
    if a.startswith('--n='):
        N = int(a[4:])
results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(f'{"PASS" if ok else "FAIL"} {name}{(": " + detail) if detail else ""}', flush=True)


def draw(graph, node):
    """The height channel at N x N, rows = v (row 0 at the bottom, as a render target reads back)."""
    return ek.evaluate_graph(graph, node, resolution=N, tile=(1.0, 1.0))['height']


def shot(op, over=None):
    g = ek.create_graph()
    n = ek.add_node(g, op, {'x': 0, 'y': 0}, dict(ek.default_params(op), **(over or {})))
    return draw(g, n)


def filter_shot(op, over=None):
    """The detailed positive-height fixture operator_response.mjs uses, then the operator."""
    g = ek.create_graph()
    broad = ek.add_node(g, 'fbm', {'x': 0, 'y': 0}, dict(ek.default_params('fbm'), frequency=4, amplitude=0.9))
    detail = ek.add_node(g, 'roughen', {'x': 1, 'y': 0},
                         dict(ek.default_params('roughen'), frequency=16, amplitude=0.04))
    node = ek.add_node(g, op, {'x': 2, 'y': 0}, dict(ek.default_params(op), **(over or {})))
    ek.connect(g, {'node': broad, 'port': 'out'}, {'node': detail, 'port': 'in'}, ek.graph_ports)
    ek.connect(g, {'node': detail, 'port': 'out'}, {'node': node, 'port': 'in'}, ek.graph_ports)
    return draw(g, detail), draw(g, node)


def quality_metrics(output, reference=None):
    """landform_shape.mjs qualityMetrics: detail inside the operator's eroded active footprint."""
    def frange(a):
        f = a[np.isfinite(a)]
        return float(f.max() - f.min())
    span = max(frange(output), 1e-9)
    effect_span = max(frange(reference) if reference is not None else span, 1e-9)
    active_floor = max(1e-5, effect_span * 0.005)
    base = reference if reference is not None else 0.0
    active = (np.isfinite(output) & np.isfinite(base) & (np.abs(output - base) >= active_floor)).astype(np.uint8)
    for _ in range(max(2, round(N / 128))):                      # erode by the 3x3 neighbourhood, wrapping
        keep = np.ones_like(active)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                keep &= np.roll(np.roll(active, -dy, 0), -dx, 1)
        active = active & keep
    at = lambda dx, dy: np.roll(np.roll(output, -dy, 0), -dx, 1)  # noqa: E731
    c, l, r, d, u = output, at(-1, 0), at(1, 0), at(0, -1), at(0, 1)
    finite = np.isfinite(c) & np.isfinite(l) & np.isfinite(r) & np.isfinite(d) & np.isfinite(u)
    sel = (active > 0) & finite
    gx = (r - l) * 0.5 * N / span
    gy = (u - d) * 0.5 * N / span
    lap = (l + r + d + u - 4 * c) / span * (N / 256) ** 2
    laps = np.sort(np.abs(lap[sel]))
    pixels = int(sel.sum())
    trim_n = int(np.floor(len(laps) * 0.95))
    return {'pixels': pixels, 'footprint': float(active.mean()),
            'flatFraction': float((np.hypot(gx, gy)[sel] < 0.02).mean()) if pixels else 1.0,
            'roughness': float(np.sqrt(np.mean(lap[sel] ** 2))) if pixels else 0.0,
            'trimmedRoughness': float(np.sqrt(np.mean(laps[:trim_n] ** 2))) if trim_n else 0.0,
            'medianLaplacian': float(laps[len(laps) // 2]) if len(laps) else 0.0,
            'detailCoverage': float((laps >= 0.001).mean()) if pixels else 0.0, 'range': span}


def metric_text(q):
    return (f"ROI {q['footprint'] * 100:.1f}%/{q['pixels']} px, flat {q['flatFraction'] * 100:.1f}%, "
            f"lap RMS {q['roughness']:.3e}, trim95 {q['trimmedRoughness']:.3e}, median {q['medianLaplacian']:.2e}, "
            f"detail {q['detailCoverage'] * 100:.0f}%")


# --- canyon cross-section -----------------------------------------------------------------------------------------
params = ek.default_params('canyon')
h = shot('canyon', {'style': 'classic', 'direction': 0})
line = h[0]
ci = int(np.argmin(line))
sc = params['scale']


def at_r(rr):
    i = int(round((ci / N + rr * sc) * N))
    return float(line[i]) if 0 <= i < N else float('nan')


def slope_r(rr):
    d = 0.02
    a, b = at_r(rr - d), at_r(rr + d)
    return abs((b - a) / (2 * d)) if np.isfinite(a) and np.isfinite(b) else float('nan')


peak, peak_r = 0.0, 0.0
for rr in np.arange(0.02, 1.0 + 1e-9, 0.005):
    s = slope_r(rr)
    if np.isfinite(s) and s > peak:
        peak, peak_r = s, rr
floor_s = slope_r(0.1) / peak
check('canyon floor is flat, not the steepest part of the profile', floor_s < 0.60,
      f'|d/dr| at r=0.10 is {floor_s * 100:.1f}% of the peak {peak:.3f} at r={peak_r:.3f} (the parabola gave 86%)')
wall_peak, wall_at = 0.0, 0.0
for rr in np.arange(params['slot'] + 0.15, 1.15 + 1e-9, 0.005):
    s = slope_r(rr)
    if np.isfinite(s) and s > wall_peak:
        wall_peak, wall_at = s, rr
check('canyon has a real wall', wall_peak > 0.6,
      f"peak |d/dr| in the wall band is {wall_peak:.3f} at r={wall_at:.3f} (the parabola's wall gave 0.128)")

# --- mountain range covers the whole tile -------------------------------------------------------------------------
def coverage(hh):
    """Percent of 16 x 16 blocks whose local relief is at least a quarter of the tile's."""
    B = 16
    bs = hh.shape[0] // B
    blocks = hh[:B * bs, :B * bs].reshape(B, bs, B, bs)
    local = blocks.max(axis=(1, 3)) - blocks.min(axis=(1, 3))
    return 100.0 * float((local > 0.25 * (hh.max() - hh.min())).mean())


h = shot('mountainRange')
pct = coverage(h)
if pct > 80 or '--no-oracle' in sys.argv:
    check('mountain range covers the whole tile in mountains', pct > 80,
          f'{pct:.0f}% of blocks have local relief (a mid-tile band scored ~40%)')
else:
    # Ekigar revised the range (registry.js, 07-29) after this gate was set (07-27): measure Ekigar's own field,
    # its JS under deno, at the same N. The same number means the gate fails in Ekigar too, not in the port.
    import os
    import parity_lib
    pr = parity_lib.gen('mountainRange')
    od = os.path.join(_ekigar_load.OUT, 'oracle_shape')
    parity_lib.run_oracle([pr], N, od)
    _meta, js = parity_lib.load_oracle(od, pr['name'])
    pct_js = coverage(js['x'])
    same = abs(pct_js - pct) < 1e-9 and float(np.abs(js['x'] - h).max()) < 1e-9
    print(f"{'EKIGAR' if same else 'FAIL'} mountain range covers the whole tile in mountains: {pct:.1f}% of blocks "
          f"have local relief (gate 80%); Ekigar's own field at {N} scores {pct_js:.1f}% (max height difference "
          f"{float(np.abs(js['x'] - h).max()):.1e}): {'the gate fails in Ekigar itself' if same else 'PORT DIFFERS'}",
          flush=True)
    results.append(same)
ratio = float(np.var(h.mean(axis=1)) / max(np.var(h.mean(axis=0)), 1e-12))
check('mountain range is not a directional stripe', 1 / 6 < ratio < 6, f'row/col variance ratio {ratio:.2f}')

# --- active-footprint surface detail ------------------------------------------------------------------------------
LAND_DETAIL_GATES = {
    'crater': (0.006, 0.05), 'mountain': (0.0035, 0.05), 'mountainRange': (0.008, 0.05),
    'canyon': (0.004, 0.05), 'island': (0.0035, 0.05), 'volcano': (0.006, 0.05),
}
for op, (min_rough, max_flat) in LAND_DETAIL_GATES.items():
    q = quality_metrics(shot(op))
    check(f'{op} active footprint is measurable', q['footprint'] >= 0.01 and q['pixels'] >= 64, metric_text(q))
    check(f'{op} has distributed surface detail', q['trimmedRoughness'] >= min_rough,
          f"trimmed normalized Laplacian {q['trimmedRoughness']:.3e}; need {min_rough:.1e}")
    check(f'{op} has no dead-flat active region', q['flatFraction'] <= max_flat,
          f"{q['flatFraction'] * 100:.1f}% flat inside eroded footprint; max {max_flat * 100:.0f}%")

SURFACE_DETAIL_GATES = {
    'terrace': (0.008, 0.10, 0.70), 'steps': (0.010, 0.30, 0.90), 'fractalTerraces': (0.009, None, 0.25),
    'stratify': (0.006, None, 0.50), 'sandstone': (0.006, None, 0.25),
}
for op, (min_rough, min_flat, max_flat) in SURFACE_DETAIL_GATES.items():
    base, output = filter_shot(op)
    q = quality_metrics(output, base)
    check(f'{op} changes a measurable surface region', q['footprint'] >= 0.01 and q['pixels'] >= 64, metric_text(q))
    check(f'{op} carries distributed surface detail', q['trimmedRoughness'] >= min_rough,
          f"trimmed normalized Laplacian {q['trimmedRoughness']:.3e}; need {min_rough:.1e}")
    ok = q['flatFraction'] <= max_flat and (min_flat is None or q['flatFraction'] >= min_flat)
    check(f'{op} has the expected tread/flat balance', ok,
          f"{q['flatFraction'] * 100:.1f}% flat; expected {0 if min_flat is None else min_flat * 100:.0f}.."
          f"{max_flat * 100:.0f}%")

print(f'landform shape: {sum(results)}/{len(results)} pass')
sys.exit(0 if all(results) else 1)
