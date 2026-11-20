// Port of blender/eidoblend/terrain/kernels/ice_flux.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2); the `//!` header is the GLSL's, unchanged.
// The only changes are WGSL's: texelFetch(x, q, 0) is x_at(q), imageStore is outQ_store, textureSize is st_size(),
// the uniforms are u.<name>, neighbour()'s `out` argument is a pointer, and the conditional expression for `a` is an
// if / else. solvers/glacial.js iceFluxConverge drives it.
//
/* ice_flux (design section 4.5, step 1): one Jacobi iteration of the ice discharge on a fixed routing surface,
   iterated to convergence by solvers/glacial.py ice_flux_converge:

       Q_in = mb.y + the upstream neighbours' discharge: D8 (uD8 1) the whole Q of each neighbour whose receiver
              (wT.x, its k) is this cell; MFD (uD8 0) each higher neighbour's Q x s^p / wsum (route_area's weights)
       a    = b dx^2                                     b >= 0: accumulation over the cell
            = b dx L,  L = clamp(2 W(Q_in), dx, uLmax)   b < 0: ablation over the tongue's width,
                                                         W(Q) = uWref (Q / uQw)^uWexp
       Q    = max(Q_in + a, 0)                           the terminus is where it reaches 0

   A glacier ablates over its width, not over the one cell its discharge is routed through (with dx^2 a tongue ran
   about 30 times too far). With b = 1 everywhere this is the D8 drainage area (m^2). On a filled surface the
   iteration is a sum over a tree: it stops changing after the longest flow path. Twin: solvers/glacial.py
   ice_flux. */
//! sampler st          x: the routing surface (m): lake-filled, tilted across flats (solvers/hydro.py)
//! sampler wT          x: D8: each cell's receiver k (0..7; -1 none); MFD: wsum of st.x at exponent uP
//! sampler qT          x: Q, the previous iterate (m^3/yr)
//! sampler mb          x: the mass balance b (m/yr of ice), y: Q_in, ice entering from outside the window (m^3/yr)
//! image   outQ r32f   x: Q (m^3/yr)
//! uniform float uDx   the cell, metres
//! uniform float uP    the MFD exponent (uD8 0)
//! uniform float uWref the ablating half-width at uQw (m)
//! uniform float uQw   the discharge of that width (m^3/yr)
//! uniform float uWexp the width's exponent
//! uniform float uLmax the widest ablating tongue (m)
//! uniform int uD8     1: D8 receivers; 0: MFD weights
//! uniform int uBound  BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED (pinned reads neighbours as open)

fn wpow(s: f32, e: f32) -> f32 { if (e == 1.0) { return s; } return pow(s, e); }

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let h = st_at(p).x;
  let m = mb_at(p).xy;
  var qin = m.y;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    if (u.uD8 == 1) {
      if (i32(wT_at(q).x) == 7 - k) { qin += qT_at(q).x; }
    } else {
      let hq = st_at(q).x;
      if (hq > h) {
        qin += qT_at(q).x * (wpow((hq - h) / (LEN[k] * u.uDx), u.uP) / max(wT_at(q).x, 1e-30));
      }
    }
  }
  let b = m.x;
  let L = clamp(2.0 * u.uWref * pow(max(qin, 0.0) / u.uQw, u.uWexp), u.uDx, max(u.uLmax, u.uDx));
  var a: f32;
  if (b >= 0.0) { a = b * u.uDx * u.uDx; } else { a = b * u.uDx * L; }
  outQ_store(p, vec4<f32>(max(qin + a, 0.0), 0.0, 0.0, 0.0));
}
