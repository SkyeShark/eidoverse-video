// Port of blender/eidoblend/terrain/kernels/dune_transport.glsl at f90c6fc.
//
// Transcribed statement for statement (PORT_PLAN.md 4.2); the //! header is Blender's, unchanged. GLSL's int(x) of a
// float is i32(x) (both truncate toward zero; the plan records hold whole numbers). The sum runs over the box in the
// GLSL's order, so the gather adds the same slabs in the same order as the twin.
//
/* dune_transport: the slab model's transport as a gather (design 4.6, step 3). No scatter and no atomics, so the
   result is deterministic and sand is conserved exactly (every lifted slab lands in one cell, or leaves an open
   edge).

   Each cell loses what it lifted (its own plan record) and gains every slab whose path ends on it. A slab from
   source s with integer hop v lands on s + k v at hop k, so the cell p looks at the sources p - k v for every hop v
   any source can pick (the box uVMin..uVMax of integer vectors, which solvers/aeolian.py's hop_box takes around the
   short and the long hop and every local turn of the wind the steering field holds) and every k = 1..uMaxHops, and
   adds the source's lifted sand when its record says exactly that hop and that k. A source's record holds one v and
   one k, and every vector is looked at once, so no slab is counted twice.
   Twin: solvers/aeolian.py, twin 'dune_transport' (the scatter it replaces: aeolian.scatter_step). */
//! sampler st                bed (r) and sand thickness (g), metres, at the start of the iteration
//! sampler plan              the plan records (dune_activate)
//! image   outSt rg32f       bed and sand after the transport
//! uniform ivec2 uVMin       the smallest integer hop any source can pick, each component, cells
//! uniform ivec2 uVMax       the largest
//! uniform int uMaxHops      hops before a slab must deposit
//! uniform int uBound        BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let s = st_at(p);
  var sand = s.g - plan_at(p).r;
  for (var vy = u.uVMin.y; vy <= u.uVMax.y; vy++) {
    for (var vx = u.uVMin.x; vx <= u.uVMax.x; vx++) {
      let v = vec2<i32>(vx, vy);
      for (var k = 1; k <= u.uMaxHops; k++) {
        var q = p - k * v;
        if (u.uBound == BOUND_PERIODIC) {
          q = wrap(q, n);
        } else if (!inside(q, n)) {
          continue;
        }
        let r = plan_at(q);
        if (r.r > 0.0 && i32(r.g) == v.x && i32(r.b) == v.y && i32(r.a) == k) {
          sand += r.r;
        }
      }
    }
  }
  outSt_store(p, vec4<f32>(s.r, sand, 0.0, 0.0));
}
