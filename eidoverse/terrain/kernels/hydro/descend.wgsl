// Port of blender/eidoblend/terrain/solvers/hydro.py _descend at f90c6fc, in the path-maximum form (PORT_PLAN.md
// C11). numpy raises the filled surface along the receiver tree, outlets first, so every cell stands at least eps
// above its receiver: rs = max(f, rs(receiver) + eps), the cells taken in order of their steps to the outlet. Unrolled
// along a cell's path c = c_0 -> c_1 -> ... -> c_s (the outlet, s = path_steps(c)) that is
//
//     rs(c) = max over j of (f(c_j) + j eps) = s(c) eps + max over q on the path of (f(q) - s(q) eps),
//
// so the kernel makes each cell's key f - s eps (mode 0), core/prims.js pathMax carries the largest key down every
// path by pointer jumping (min and max only: exact), and mode 1 adds s eps back. In float32 a relaxation along the
// receivers rounds once per step and drifts by up to 82 ulp (5 mm) on a long flat; this form rounds a fixed few times
// per cell (the review measured 1 ulp from numpy's float64 on alpine_valley's main level). eps arrives as its float32
// value and the rest of its float64 value (uEpsHi + uEpsLo), so s eps is close to numpy's float64 product even after
// thousands of steps; fma() keeps the products unrounded where the backend fuses it. max(f, ...) is numpy's own
// np.maximum(f, ...), which also holds the result at or above f where a rounding would put it a step below.
//! sampler f              the filled surface (metres)
//! sampler steps r32ui    path_steps of the receivers
//! sampler pm             mode 1: the path maximum of the keys; mode 0: a 1 x 1 stand-in
//! image   outF r32f      mode 0: the key f - s eps; mode 1: the routing surface max(f, s eps + max)
//! uniform int uMode
//! uniform float uEpsHi   eps (metres), rounded to float32
//! uniform float uEpsLo   eps - uEpsHi, rounded to float32

fn kmain(p: vec2<i32>) {
  let n = f_size();
  if (!inside(p, n)) { return; }
  let fv = f_at(p).x;
  let s = f32(steps_at(p));
  if (u.uMode == 0) {
    outF_store(p, vec4<f32>(fma(-s, u.uEpsHi, fv) - s * u.uEpsLo, 0.0, 0.0, 0.0));
    return;
  }
  let rs = fma(s, u.uEpsHi, pm_at(p).x) + s * u.uEpsLo;
  outF_store(p, vec4<f32>(max(fv, rs), 0.0, 0.0, 0.0));
}
