// Port of blender/eidoblend/terrain/surface/kernels/fill.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged. The changes are WGSL's: texelFetch is <name>_at(q), imageStore is outW_store, textureSize is
// wT_size(), the uniforms are u.<name>.
/* fill: one Jacobi pass of a depression fill with a tilt (Planchon & Darboux 2001, written as a gather), on the
   padded cell grid (SURFACING_DESIGN.md 2.3, step 8). Twin: surface/twins.py fill.

       W' = max(z, min(W, min over the 8 neighbours q of W_q + uEps LEN_q))

   from W = a very large number on every free cell. Held cells (zT.y) keep their W: the boundary, the padded grid's
   outer ring at W = z (water leaves anywhere on the edge, as the level runner's own fill). On a child level the
   margin inside that ring is its parents' terrain, so water leaves the window where that terrain takes it.
   The fixed point is the least surface over z on which every free cell has a neighbour at least uEps LEN lower,
   at most uCap over the ground: a pit up to uCap deep (the elevation data's noise) fills and drains, a deeper basin
   (a crater, a sinkhole, an interdune pan) stays a sink where its water ends, instead of a flat lake to its rim
   that the routing spreads across. It is reached when a pass changes nothing, after as many passes as the longest
   way from the boundary. */
//! sampler wT          x: W, the filled surface so far (metres, less the level's reference height)
//! sampler zT          x: z, the ground and its lake water (the same frame), y: 1 where W is held
//! image   outW r32f
//! uniform float uEps  the least drop per cell step, metres
//! uniform float uCap  the deepest fill, metres

fn kmain(p: vec2<i32>) {
  let n = wT_size();
  if (!inside(p, n)) { return; }
  let z = zT_at(p);
  var W = wT_at(p).x;
  if (z.y < 0.5) {
    for (var k = 0; k < 8; k++) {
      let q = p + OFF[k];
      if (!inside(q, n)) { continue; }
      W = min(W, wT_at(q).x + u.uEps * LEN[k]);
    }
    W = max(z.x, min(W, z.x + u.uCap));
  }
  outW_store(p, vec4<f32>(W, 0.0, 0.0, 0.0));
}
