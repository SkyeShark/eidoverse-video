/* dune_shadow: the wind shadow of every cell, and its height above the ground upwind (design 4.6, step 2).

   Shadow (Werner 1995's shadow zone): a cell lies in the lee of the ground upwind of it when that ground rises
   above a line at the shadow angle from the cell. This pass finds the steepest elevation angle (as a tangent) from
   the cell to the surface upwind, sampled every cell along the wind out to uReach cells, bilinear between texels so
   any wind direction works and the shadow edge does not lock to the grid. The shadow ramps from 0 at tan(lo) to 1
   at tan(hi) (Paris et al. 2019 ramp it; Werner's rule is the step at 15 degrees, lo = hi). In a shadow a slab is
   never lifted and always deposits.

   Rise (for the wind's speed-up on the stoss, after Momiji et al. 2000), metres: uRiseMode 0, how far the cell
   stands above the lowest ground on the same upwind ray (0 where nothing upwind is lower), which grows from a dune's
   windward toe up to uReach cells along its stoss; uRiseMode 1, the sand's thickness (Momiji's height), which grows
   from the toe all the way to the crest of a dune on bare ground or a thinner sheet.

   Open and pinned grids stop the march where the upwind ray leaves the grid; periodic grids wrap.
   Twin: solvers/aeolian.py, twin 'dune_shadow'. */
//! sampler st                bed (r) and sand thickness (g), metres
//! image   outShadow rg32f   shadow 0..1 (r), rise above the lowest ground upwind, metres (g)
//! uniform vec2 uDir         the unit direction the sand moves, (x east, y north)
//! uniform float uTanLo      the tangent where the shadow starts
//! uniform float uTanHi      the tangent where it is complete
//! uniform int uReach        how far upwind the ray looks, cells
//! uniform float uCell       metres
//! uniform int uRiseMode     0: rise above the lowest ground upwind; 1: the sand's thickness
//! uniform int uBound        BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED

float surface_at(ivec2 q) {
  vec4 s = texelFetch(st, q, 0);
  return s.r + s.g;
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float h0 = surface_at(p);
  float best = -1.0e30;
  float lowest = h0;
  for (int d = 1; d <= uReach; d++) {
    vec2 q = vec2(p) - float(d) * uDir;          /* texel centres sit at whole numbers */
    vec2 f = floor(q);
    vec2 t = q - f;
    ivec2 a = ivec2(f);
    ivec2 b = a + ivec2(1, 1);
    if (uBound == BOUND_PERIODIC) {
      a = wrap(a, n);
      b = wrap(b, n);
    } else if (!inside(a, n) || !inside(b, n)) {
      break;                                      /* the ray has left the grid: nothing further upwind */
    }
    float h00 = surface_at(ivec2(a.x, a.y));
    float h10 = surface_at(ivec2(b.x, a.y));
    float h01 = surface_at(ivec2(a.x, b.y));
    float h11 = surface_at(ivec2(b.x, b.y));
    float hq = mix(mix(h00, h10, t.x), mix(h01, h11, t.x), t.y);
    best = max(best, (hq - h0) / (float(d) * uCell));
    lowest = min(lowest, hq);
  }
  float s = clamp((best - uTanLo) / max(uTanHi - uTanLo, 1.0e-6), 0.0, 1.0);
  float rise = uRiseMode == 1 ? texelFetch(st, p, 0).g : h0 - lowest;
  imageStore(outShadow, p, vec4(s, rise, 0.0, 0.0));
}
