/* dune_transport: the slab model's transport as a gather (design 4.6, step 3). No scatter and no atomics, so the
   result is deterministic and sand is conserved exactly (every lifted slab lands in one cell, or leaves an open
   edge).

   Each cell loses what it lifted (its own plan record) and gains every slab whose path ends on it. A slab from
   source s with integer hop v lands on s + k v at hop k, so the cell p looks at the sources p - k v for every hop v
   the stochastic rounding can give (the four integer corners around the short hop uHop, then the four around the
   long hop uHop x uLong that are not already among the first four) and every k = 1..uMaxHops, and adds the
   source's lifted sand when its record says exactly that hop and that k. A source's record holds one v and one k,
   and no vector is looked at twice, so no slab is counted twice.
   Twin: solvers/aeolian.py, twin 'dune_transport' (the scatter it replaces: aeolian.scatter_step). */
//! sampler st                bed (r) and sand thickness (g), metres, at the start of the iteration
//! sampler plan              the plan records (dune_activate)
//! image   outSt rg32f       bed and sand after the transport
//! uniform vec2 uHop         the short hop vector dune_activate rounded, cells
//! uniform float uLong       the long hop's length, a multiple of the short one (1: no long hops)
//! uniform int uMaxHops      hops before a slab must deposit
//! uniform int uBound        BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 s = texelFetch(st, p, 0);
  float sand = s.g - texelFetch(plan, p, 0).r;
  ivec2 fs = ivec2(floor(uHop));
  ivec2 fl = ivec2(floor(uHop * uLong));
  int sets = uLong > 1.0 ? 2 : 1;
  for (int c = 0; c < 4 * sets; c++) {
    ivec2 v = (c < 4 ? fs : fl) + ivec2(c & 1, (c >> 1) & 1);
    if (c >= 4) {
      ivec2 r = v - fs;
      if (r.x >= 0 && r.x <= 1 && r.y >= 0 && r.y <= 1) continue;    /* a short-hop corner already looked at */
    }
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
  imageStore(outSt, p, vec4(s.r, sand, 0.0, 0.0));
}
