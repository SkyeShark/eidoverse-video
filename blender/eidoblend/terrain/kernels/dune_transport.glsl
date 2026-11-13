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

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 s = texelFetch(st, p, 0);
  float sand = s.g - texelFetch(plan, p, 0).r;
  for (int vy = uVMin.y; vy <= uVMax.y; vy++) {
    for (int vx = uVMin.x; vx <= uVMax.x; vx++) {
      ivec2 v = ivec2(vx, vy);
      for (int k = 1; k <= uMaxHops; k++) {
        ivec2 q = p - k * v;
        if (uBound == BOUND_PERIODIC) {
          q = wrap(q, n);
        } else if (!inside(q, n)) {
          continue;
        }
        vec4 r = texelFetch(plan, q, 0);
        if (r.r > 0.0 && int(r.g) == v.x && int(r.b) == v.y && int(r.a) == k) {
          sand += r.r;
        }
      }
    }
  }
  imageStore(outSt, p, vec4(s.r, sand, 0.0, 0.0));
}
