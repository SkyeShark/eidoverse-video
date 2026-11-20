// The port's own kernel: one sweep of blender/eidoblend/terrain/solvers/glacial.py head_distance at f90c6fc, numpy's
// own relaxation, repeated until nothing changes (solvers/glacial.js; numpy stops at the first sweep equal to the last):
//     seg = hypot(x - x[main], y - y[main]) where main >= 0, else 0
//     dist = dist[main] + seg where main >= 0, else 0          (from dist = 0)
// Each sweep carries the sums one seed further down every main stem, in numpy's order. float32 here, float64 there.
//! sampler D                per seed: the distance so far (m)
//! sampler V                per seed: x, y (m)
//! sampler main r32i
//! image   outD r32f
//! image   changed atomic_u32  with uCounted 1: [0] gains the seeds this sweep changed
//! uniform int uCount
//! uniform int uCounted

fn kmain(p: vec2<i32>) {
  let w = outD_size().x;
  let s = p.y * w + p.x;
  if (p.x >= w || s >= u.uCount) { return; }
  let m = main_b[s];
  var nd = 0.0;
  if (m >= 0) {
    let d = V_b[s].xy - V_b[m].xy;
    nd = D_b[m] + sqrt(d.x * d.x + d.y * d.y);
  }
  if (u.uCounted != 0 && nd != D_b[s]) { atomicAdd(&changed_b[0], 1u); }
  outD_b[s] = nd;
}
