// Port of blender/eidoblend/terrain/core/metrics.py at f90c6fc: aspect_harmonics' per-cell terms.
//
// aspect_harmonics sums w e^(i m theta) over the cells steeper than a minimum slope, theta = arctan2(gy, gx) the
// gradient's direction and w = hypot(gx, gy) its magnitude, for m = 2, 4, 8. This kernel writes each cell's terms;
// core/metrics.js sums them (float32 sums in a fixed tree, core/prims.js) and takes the amplitudes in doubles.
//
// Deviation from metrics.py, forced by float32: cos(m theta) and sin(m theta) come from the unit vector (gx, gy) / w
// by the double-angle identities, not from atan2 and then cos and sin of m theta (whose float32 errors, 2 ulp of
// atan2 and the cosine's, grow with m). The same numbers, better conditioned (PORT_PLAN.md risk 2); numpy's
// aspect_harmonics is the oracle.
//! sampler gx               dh/dx east   (core/grid.js gradient)
//! sampler gy               dh/dy north
//! image   outA rgba32f     w, w cos 2t, w sin 2t, w cos 4t   (zero where the cell is not steep enough)
//! image   outB rgba32f     w sin 4t, w cos 8t, w sin 8t, 1 where the cell counts
//! uniform float uTan       tan(min_slope_deg): a cell counts when w > uTan

fn kmain(p: vec2<i32>) {
  let n = gx_size();
  if (!inside(p, n)) { return; }
  let x = gx_at(p).x;
  let y = gy_at(p).x;
  let w = sqrt(x * x + y * y);
  if (!(w > u.uTan)) {
    outA_store(p, vec4<f32>(0.0));
    outB_store(p, vec4<f32>(0.0));
    return;
  }
  let c1 = x / w;
  let s1 = y / w;
  let c2 = c1 * c1 - s1 * s1;
  let s2 = 2.0 * s1 * c1;
  let c4 = c2 * c2 - s2 * s2;
  let s4 = 2.0 * s2 * c2;
  let c8 = c4 * c4 - s4 * s4;
  let s8 = 2.0 * s4 * c4;
  outA_store(p, vec4<f32>(w, w * c2, w * s2, w * c4));
  outB_store(p, vec4<f32>(w * s4, w * c8, w * s8, 1.0));
}
