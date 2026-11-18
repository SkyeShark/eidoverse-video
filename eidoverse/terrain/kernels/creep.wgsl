// Port of blender/eidoblend/terrain/kernels/creep.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2), starting from the design probe's
// transcription (tests/design_probes/wgsl/creep.wgsl); the `//!` header is the GLSL's, unchanged. The changes are
// WGSL's: texelFetch(x, q, 0) is x_at(q), imageStore is outS_store, textureSize is st_size(), a uniform uX is u.uX,
// and neighbour()'s `out` argument is a pointer.
//
/* creep (design section 4.1, pass 3; 4.2): one explicit sub-step of nonlinear hillslope creep (Roering et al. 1999)

       dh = dt_sub D / dx^2 * sum_k WISO_k f_k (h_k - h),   f_k = min(1 / (1 - (s_k / Sc_k)^2), cap)

   with the isotropic 9-point weights (sides 2/3, diagonals 1/6), s_k = (h_k - h) / (L_k dx) and Sc_k the mean of the
   two cells' threshold tangents. Every pair's exchange is computed alike from both of its cells, so the sum of h is
   conserved (in the open and periodic modes). cap = 1 is linear diffusion (the aging stage's kappa t). Stable for
   dt_sub <= 0.9 dx^2 / (3.4 D cap) (the runner sub-steps). In BOUND_PINNED mode the height is pulled to its pin.
   Twin: solvers/hillslope.py creep. */
//! sampler st          x: h (m); y, z, w carried
//! sampler par         z: Sc, the threshold slope's tangent
//! sampler pin         x: pin_w (0..1), y: pin_h (m)
//! image   outS rgba32f
//! uniform float uDx   the cell, metres
//! uniform float uDtSub
//! uniform float uD    the creep diffusivity, m^2/yr
//! uniform float uCap
//! uniform int uBound

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  let h = c.x;
  let sc = par_at(p).z;
  var acc = 0.0;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let hq = st_at(q).x;
    let scp = 0.5 * (sc + par_at(q).z);
    let r = ((hq - h) / (LEN[k] * u.uDx)) / scp;
    let f = min(1.0 / max(1.0 - r * r, 1e-9), u.uCap);
    acc += WISO[k] * f * (hq - h);
  }
  var hn = h + u.uDtSub * u.uD * acc / (u.uDx * u.uDx);
  if (u.uBound == BOUND_PINNED) {
    let pn = pin_at(p);
    hn = pin_apply(hn, pn.x, pn.y);
  }
  outS_store(p, vec4<f32>(hn, c.y, c.z, c.w));
}
