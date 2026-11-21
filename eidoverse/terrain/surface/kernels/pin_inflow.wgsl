// Port of blender/eidoblend/terrain/surface/kernels/pin_inflow.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged. The changes are WGSL's: texelFetch is <name>_at(q), imageStore is outP_store, textureSize is st_size(),
// the uniforms are u.<name>, and neighbour()'s `out` argument is a pointer.
/* pin_inflow: the source term that holds route_area's drainage area at a target on pinned cells (SURFACING_DESIGN.md
   2.3, step 8: "inflow is pinned from the parent across the border"). Twin: surface/twins.py pin_inflow.

   route_area iterates A = dx^2 + A_in + sum over higher neighbours q of A_q share(q -> c). For a pinned cell

       A_in = target - dx^2 - sum over higher pinned neighbours q of target_q share(q -> c)

   so at the fixed point every pinned cell whose higher neighbours are all pinned reads exactly its target, whatever
   the surface does there, and the free cells next to them receive the targets' flow by the surface's own shares. On
   a child level the pinned cells are the margin around its window and the target is the parent's specific catchment
   (its drainage area over its cell) times the child's cell: a river enters the window where the parent has it,
   carrying the parent's catchment. A free cell's A_in is 0. The shares are route_area's, term for term. */
//! sampler st          x: the routing surface (m)
//! sampler wsumT       x: wsum of st.x (flow_weights)
//! sampler tgtT        x: the target drainage area (m^2), y: 1 where the cell is pinned to it
//! image   outP r32f   x: A_in (m^2)
//! uniform float uDx   the cell, metres
//! uniform float uP    the flow exponent p
//! uniform int uBound

fn wpow(s: f32, e: f32) -> f32 { if (e == 1.0) { return s; } return pow(s, e); }

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let tg = tgtT_at(p);
  var a_in = 0.0;
  if (tg.y > 0.5) {
    let h = st_at(p).x;
    var A = u.uDx * u.uDx;
    for (var k = 0; k < 8; k++) {
      var q: vec2<i32>;
      if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
      let hq = st_at(q).x;
      let tq = tgtT_at(q);
      if (hq > h && tq.y > 0.5) {
        A += tq.x * wpow((hq - h) / (LEN[k] * u.uDx), u.uP) / max(wsumT_at(q).x, 1e-30);
      }
    }
    a_in = tg.x - A;
  }
  outP_store(p, vec4<f32>(a_in, 0.0, 0.0, 0.0));
}
