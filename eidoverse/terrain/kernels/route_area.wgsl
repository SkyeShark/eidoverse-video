// Port of blender/eidoblend/terrain/kernels/route_area.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2); the `//!` header is the GLSL's, unchanged.
// The only changes are WGSL's: texelFetch(x, q, 0) is x_at(q), imageStore is outA_store, textureSize is st_size(),
// the uniforms are u.<name>, and neighbour()'s `out` argument is a pointer. The pin sampler is the GLSL's RGBA
// texture: solvers/hydro.js routeToConvergence packs A_in into its z channel, as route_to_convergence does.
//
/* route_area (design sections 4.1 "after the last step" and 4.3): one Jacobi iteration of drainage-area routing on a
   fixed surface,

       A = dx^2 + A_in + sum over higher neighbours q of A_q * max(s_qc, 0)^p / wsum_q

   iterated to convergence (the runner stops when the largest relative change is under 1e-4, checked every 128
   iterations). The surface is the lake-filled one with a small tilt across each lake toward its spill (solvers/
   hydro.py routing_surface), so water crosses lakes; A_in is the area entering from outside the window (a child
   level's border inflow). Twin: solvers/hydro.py route_area. */
//! sampler st          x: the routing surface (m)
//! sampler wsumT       x: wsum of st.x (flow_weights)
//! sampler aT          x: A, the previous iterate (m^2)
//! sampler pin         z: A_in (m^2)
//! image   outA r32f   x: A (m^2)
//! uniform float uDx   the cell, metres
//! uniform float uP    the flow exponent p
//! uniform int uBound

fn wpow(s: f32, e: f32) -> f32 { if (e == 1.0) { return s; } return pow(s, e); }

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let h = st_at(p).x;
  var A = u.uDx * u.uDx + pin_at(p).z;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let hq = st_at(q).x;
    if (hq > h) {
      let share = wpow((hq - h) / (LEN[k] * u.uDx), u.uP) / max(wsumT_at(q).x, 1e-30);
      A += aT_at(q).x * share;
    }
  }
  outA_store(p, vec4<f32>(A, 0.0, 0.0, 0.0));
}
