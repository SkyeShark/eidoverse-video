// Port of blender/eidoblend/terrain/kernels/flow_weights.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2), starting from the design probe's
// transcription (tests/design_probes/wgsl/flow_weights.wgsl); the `//!` header is the GLSL's, unchanged. The only
// changes are WGSL's: texelFetch(st, q, 0) is st_at(q), imageStore is outW_store, textureSize is st_size(), uDx is
// u.uDx, and neighbour()'s `out` argument is a pointer.
//
/* flow_weights (design section 4.1, pass 1): every cell's total downhill weight

       wsum = sum_k max(s_k, 0)^p,   s_k = (h - h_k) / (L_k dx)

   so a neighbour k receives the share max(s_k, 0)^p / wsum of the cell's flow (multiple flow directions, slope to
   the power p; p = 1 by default). route_incise and route_area read it to split each upstream neighbour's drainage
   area and sediment flux. Twin: solvers/fluvial.py flow_weights. */
//! sampler st          x: the surface the water follows, h (m)
//! image   outW r32f   x: wsum, the sum of the downhill slopes to the power p
//! uniform float uDx   the cell, metres
//! uniform float uP    the flow exponent p
//! uniform int uBound  BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED (common.glsl)

fn wpow(s: f32, e: f32) -> f32 { if (e == 1.0) { return s; } return pow(s, e); }

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let h = st_at(p).x;
  var ws = 0.0;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let s = (h - st_at(q).x) / (LEN[k] * u.uDx);
    if (s > 0.0) { ws += wpow(s, u.uP); }
  }
  outW_store(p, vec4<f32>(ws, 0.0, 0.0, 0.0));
}
