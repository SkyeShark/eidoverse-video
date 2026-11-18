// Port of blender/eidoblend/terrain/kernels/dune_shadow.glsl at f90c6fc.
//
// Transcribed statement for statement (PORT_PLAN.md 4.2): texelFetch(st, q, 0) is st_at(q), textureSize(st, 0) is
// st_size(), imageStore is outShadow_store, the uniforms are u.<name>; the //! header is Blender's, unchanged. The
// GLSL's mix() stays mix() (WGSL's mix is the same a (1 - t) + b t); the bilinear sample's ivec2(f) of a floored
// vector is vec2<i32>(f).
//
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

   The wind is steered: at each cell it blows along uDir turned by the cell's own angle (the `wind` texture holds the
   angle's cosine and sine; solvers/aeolian.py's Steering: the regional relief turns each wind by a smooth angle that
   varies across the field), and the ray looks upwind along that local direction.

   Open and pinned grids stop the march where the upwind ray leaves the grid; periodic grids wrap.
   Twin: solvers/aeolian.py, twin 'dune_shadow'. */
//! sampler st                bed (r) and sand thickness (g), metres
//! sampler wind              the local turn of the wind: its cosine (r) and sine (g); (1, 0) where it is not turned
//! image   outShadow rg32f   shadow 0..1 (r), rise above the lowest ground upwind, metres (g)
//! uniform vec2 uDir         the unit direction the sand moves, (x east, y north), before the local turn
//! uniform float uTanLo      the tangent where the shadow starts
//! uniform float uTanHi      the tangent where it is complete
//! uniform int uReach        how far upwind the ray looks, cells
//! uniform float uCell       metres
//! uniform int uRiseMode     0: rise above the lowest ground upwind; 1: the sand's thickness
//! uniform int uBound        BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED

fn surface_at(q: vec2<i32>) -> f32 {
  let s = st_at(q);
  return s.r + s.g;
}

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let h0 = surface_at(p);
  var best = -1.0e30;
  var lowest = h0;
  let cs = wind_at(p).rg;
  let dir = vec2<f32>(cs.x * u.uDir.x - cs.y * u.uDir.y, cs.y * u.uDir.x + cs.x * u.uDir.y);
  for (var d = 1; d <= u.uReach; d++) {
    let q = vec2<f32>(p) - f32(d) * dir;           /* texel centres sit at whole numbers */
    let f = floor(q);
    let t = q - f;
    var a = vec2<i32>(f);
    var b = a + vec2<i32>(1, 1);
    if (u.uBound == BOUND_PERIODIC) {
      a = wrap(a, n);
      b = wrap(b, n);
    } else if (!inside(a, n) || !inside(b, n)) {
      break;                                      /* the ray has left the grid: nothing further upwind */
    }
    let h00 = surface_at(vec2<i32>(a.x, a.y));
    let h10 = surface_at(vec2<i32>(b.x, a.y));
    let h01 = surface_at(vec2<i32>(a.x, b.y));
    let h11 = surface_at(vec2<i32>(b.x, b.y));
    let hq = mix(mix(h00, h10, t.x), mix(h01, h11, t.x), t.y);
    best = max(best, (hq - h0) / (f32(d) * u.uCell));
    lowest = min(lowest, hq);
  }
  let s = clamp((best - u.uTanLo) / max(u.uTanHi - u.uTanLo, 1.0e-6), 0.0, 1.0);
  let rise = select(h0 - lowest, st_at(p).g, u.uRiseMode == 1);
  outShadow_store(p, vec4<f32>(s, rise, 0.0, 0.0));
}
