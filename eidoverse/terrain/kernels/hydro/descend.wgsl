// Port of blender/eidoblend/terrain/solvers/hydro.py _descend at f90c6fc, in the path-maximum form (PORT_PLAN.md
// C11). numpy raises the filled surface along the receiver tree, outlets first, so every cell stands at least eps
// above its receiver: rs = max(f, rs(receiver) + eps), the cells taken in order of their steps to the outlet. Unrolled
// along a cell's path c = c_0 -> c_1 -> ... -> c_s (the outlet, s = path_steps(c)) that is
//
//     rs(c) = max over j of (f(c_j) + j eps) = f(q*) + (s(c) - s(q*)) eps,   q* the path cell of the largest key
//                                                                            f(q) - s(q) eps
//
// so mode 0 makes each cell's key and its own index, kernels/hydro/jump_argmax.wgsl carries the largest key and its
// cell down every path by pointer jumping (a maximum: exact), and mode 1 adds the steps between back to that cell's
// height. In float32 a relaxation along the receivers rounds once per step and drifts by up to 82 ulp (5 mm) on a long
// flat. Adding s eps back to the largest key itself (s eps + max, the plan's form) cancels where the ground is near
// 0 m and the path long: rolling_hills' base-level plain lost 1,262 steps of a 7e-5 m height that way (9e-9 m). Made
// from q*'s own height and the integer step difference, the result is one or two roundings of numpy's value (worst
// 0.9 ulp on the floor runs' levels; exactly f where the cell is its own maximum). eps arrives as its float32 value
// and the rest of its float64 value (uEpsHi + uEpsLo), so s eps is close to numpy's float64 product even after
// thousands of steps, and fma() keeps the products unrounded where the backend fuses it. max(f, ...) is numpy's own
// np.maximum(f, ...), rounded as numpy's astype(float32) of it rounds. The surface is read as an exact pair
// (hydro/lib): a float32 field is (f, 0); numpy's float64 h + water across a lake is (hi, lo).
//! sampler f              the filled surface (metres): r32f, or rg32f (hi, lo)
//! sampler steps r32ui    path_steps of the receivers
//! sampler arg r32ui      mode 1: the cell of each path's largest key (jump_argmax.wgsl); mode 0: a 1 x 1 stand-in
//! image   outF r32f      mode 0: the key f - s eps; mode 1: the routing surface
//! image   outA r32ui     mode 0: each cell's own index; mode 1: a 1 x 1 stand-in (not written)
//! uniform int uMode
//! uniform float uEpsHi   eps (metres), rounded to float32
//! uniform float uEpsLo   eps - uEpsHi, rounded to float32

fn kmain(p: vec2<i32>) {
  let n = f_size();
  if (!inside(p, n)) { return; }
  let fv = f_at(p).xy;
  let sc = steps_at(p);
  if (u.uMode == 0) {
    let s = f32(sc);
    outF_store(p, vec4<f32>(fma(-s, u.uEpsHi, fv.x) - s * u.uEpsLo + fv.y, 0.0, 0.0, 0.0));
    outA_store(p, u32(p.y * n.x + p.x));
    return;
  }
  let q = i32(arg_at(p));
  let fq = f_at(vec2<i32>(q % n.x, q / n.x)).xy;
  let ds = f32(sc - steps_b[q]);
  let rs = fma(ds, u.uEpsHi, fq.x) + (ds * u.uEpsLo + fq.y);
  outF_store(p, vec4<f32>(max(fv.x, rs), 0.0, 0.0, 0.0));
}
