// Port of blender/eidoblend/terrain/surface/kernels/route_colour.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged. The changes are WGSL's: texelFetch is <name>_at(q), imageStore is outQ_store, textureSize is st_size(),
// the uniforms are u.<name>, and neighbour()'s `out` argument is a pointer.
/* route_colour: one Jacobi pass of the routing of sediment and its colour down the drainage (SURFACING_DESIGN.md
   2.3, the palette bake). route_area's scheme with four channels: with P a cell's sediment production and c the
   colour of its bare rock,

       Q = P + sum over higher neighbours q of Q_q share(q -> c)          (what the cell carries)
       R = P c + sum over higher neighbours q of R_q share(q -> c)        (and its colour, premultiplied)

   on the filled, tilted surface (fill.glsl) with route_area's multiple-flow shares, to convergence. The colour the
   sediment carries is R / Q, upstream rock colours weighted by where the ground erodes. Held cells (pinT) keep their
   start value: on a child level the margin holds the parent's Q and R, so a catchment the window truncates still
   carries its upstream colour in. Twin: surface/twins.py route_colour. */
//! sampler st          x: the routing surface (m)
//! sampler wsumT       x: wsum of st.x (flow_weights)
//! sampler qT          the previous iterate: x: Q, yzw: R
//! sampler srcT        x: P, yzw: P x colour (linear)
//! sampler pinT        y: 1 where the cell holds its start value
//! image   outQ rgba32f
//! uniform float uDx   the cell, metres
//! uniform float uP    the flow exponent p
//! uniform int uBound

fn wpow(s: f32, e: f32) -> f32 { if (e == 1.0) { return s; } return pow(s, e); }

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  var Q = qT_at(p);
  if (pinT_at(p).y < 0.5) {
    let h = st_at(p).x;
    Q = srcT_at(p);
    for (var k = 0; k < 8; k++) {
      var q: vec2<i32>;
      if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
      let hq = st_at(q).x;
      if (hq > h) {
        Q += qT_at(q) * (wpow((hq - h) / (LEN[k] * u.uDx), u.uP) / max(wsumT_at(q).x, 1e-30));
      }
    }
  }
  outQ_store(p, Q);
}
