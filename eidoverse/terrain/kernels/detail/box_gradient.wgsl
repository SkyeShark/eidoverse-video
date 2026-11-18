// Port of numpy code of blender/eidoblend/terrain/solvers/hydraulic.py and blender/eidoblend/terrain/solvers/detail.py
// (with blender/eidoblend/terrain/core/grid.py gradient and slope_deg) at f90c6fc, as a GPU kernel.
// box_gradient: the gradient and slope of a box-smoothed surface, cell by cell (the port's own kernel, PORT_PLAN.md
// 3.2: numpy code of blender/eidoblend/terrain/solvers/hydraulic.py and detail.py at f90c6fc moved to the GPU). It
// replaces
//   gy, gx = np.gradient(hydraulic._box(h, r), cell)          (op_breakup, flow_direction: r 2 and the octave's)
//   slope_deg = degrees(arctan(hypot(gx, gy)))                (rockness, op_hydraulic's on_slope, gully_relief's mask)
// _box is the separable mean of (2r + 1) x (2r + 1) cells, indices clamped at the edges, and np.gradient is a central
// difference, one-sided on the edge rows. In a better-conditioned form of the same quantity (PORT_PLAN.md 2.3): the
// box is linear, so the difference of two box means is the box mean of the heights' differences,
//   gx[j, i] = sum_m sum_k (h[j + m, a + k] - h[j + m, b + k]) / ((2r + 1)^2 den)     (indices clamped)
// with (a, b, den) = (i + 1, i - 1, 2 cell) inside and (1, 0, cell), (n - 1, n - 2, cell) on the edges; likewise gy.
// Each difference is of two nearby heights, nearly exact in float32. Smoothing first and then differencing (numpy's
// order) would round every smoothed height to half an ulp of the height (3e-5 m at 1,000 m) and divide that by the
// cell: about 1e-5 of the slope, against float64's nothing (measured on the function fixtures, tests/detail/).
//! sampler h             x: the surface, metres
//! image   outGx r32f    dh/dx (east) of the smoothed surface
//! image   outGy r32f    dh/dy (north)
//! image   outS r32f     its slope, degrees
//! uniform int uR        the box radius r (cells)
//! uniform float uCell

fn hc(i: i32, j: i32, n: vec2<i32>) -> f32 { return h_at(vec2<i32>(clamp(i, 0, n.x - 1), clamp(j, 0, n.y - 1))).x; }

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let r = u.uR;
  // np.gradient's pair and step along each axis
  var ax = p.x + 1;
  var bx = p.x - 1;
  var dx = 2.0 * u.uCell;
  if (p.x == 0) { ax = 1; bx = 0; dx = u.uCell; } else if (p.x == n.x - 1) { ax = n.x - 1; bx = n.x - 2; dx = u.uCell; }
  var ay = p.y + 1;
  var by = p.y - 1;
  var dy = 2.0 * u.uCell;
  if (p.y == 0) { ay = 1; by = 0; dy = u.uCell; } else if (p.y == n.y - 1) { ay = n.y - 1; by = n.y - 2; dy = u.uCell; }
  var sx = 0.0;
  var sy = 0.0;
  for (var m = -r; m <= r; m++) {
    for (var k = -r; k <= r; k++) {
      sx += hc(ax + k, p.y + m, n) - hc(bx + k, p.y + m, n);
      sy += hc(p.x + m, ay + k, n) - hc(p.x + m, by + k, n);
    }
  }
  let w = f32((2 * r + 1) * (2 * r + 1));
  var gx = 0.0;
  var gy = 0.0;
  if (n.x >= 2) { gx = sx / w / dx; }
  if (n.y >= 2) { gy = sy / w / dy; }
  outGx_store(p, vec4<f32>(gx, 0.0, 0.0, 0.0));
  outGy_store(p, vec4<f32>(gy, 0.0, 0.0, 0.0));
  outS_store(p, vec4<f32>(degrees(atan(sqrt(gx * gx + gy * gy))), 0.0, 0.0, 0.0));
}
