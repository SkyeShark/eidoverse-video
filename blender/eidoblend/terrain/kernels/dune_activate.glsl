/* dune_activate: every source cell decides, from integer hashes alone, whether it lifts a slab this iteration and
   where that slab comes down (design 4.6, steps 1 and 3; Werner 1995's slab model with the numbers of Paris et al.
   2019's Desertscapes code, and the wind's speed-up on the stoss after Momiji et al. 2000).

   A cell with sand (thicker than uMinSand) lifts one slab (uSlab metres, or what it has) with probability
   uPLift x (1 + uLiftBoost x f), unless it lies in a wind shadow (lifting is refused with the shadow's probability).
   f = clamp((rise - uSpeedFrom) / (uSpeedRef - uSpeedFrom), 0, 1), rise being dune_shadow's (the sand's thickness,
   or the height above the lowest ground upwind): the wind speeds up over a dune toward its crest, so the stoss erodes
   more the higher it climbs and the flux grows all the way to the crest, which keeps the stoss gentle (Momiji et al.
   2000; without it Werner's dunes are steep on both sides). A sheet thinner than uSpeedFrom is not a dune and gets
   no speed-up, so thin sand can still gather into dunes. With uSpeedPow > 1 the speed-up grows as f^uSpeedPow, faster
   toward the crest than at the toe (an integer power by repeated products, so the twin's float32 matches it bit for
   bit): every height of a dune then moves at its own speed (the flux's slope in the sand's thickness grows with it),
   the upper dune outruns its base and the flanks stretch into broad aprons under the sharp crest zone, where a linear
   speed-up only carries each face along at its angle. The same f can also lengthen the hop: the slab takes the long hop (uHop x uLong) with probability
   uSpeedup x f, else the short hop uHop. The hop is an integer vector chosen by stochastic rounding of the real one
   (any wind direction works on average and crests do not lock to the grid), followed up to uMaxHops times. At each landing cell the slab deposits with probability
   shadow + (1 - shadow) x (uPSand on sand, uPRock on bare rock); at the last hop it always deposits. Every decision
   is a hash of (source cell, iteration, seed) and a salt, so dune_transport, gathering at the landing cell, finds
   exactly this record: the plan written here.

   The hop is turned by the source cell's own angle first (the `wind` texture: its cosine and sine; the regional
   relief steers the wind, solvers/aeolian.py's Steering), so the wind's direction varies smoothly across the field.

   Plan record (rgba): (sand lifted, metres; hop x; hop y; the hop it lands at, 1..uMaxHops, or -1 when it left an
   open grid). A cell that lifts nothing writes zeros. Inputs are read as they stood at the start of the iteration.
   Twin: solvers/aeolian.py, twin 'dune_activate'. */
//! sampler st                bed (r) and sand thickness (g), metres
//! sampler shadow            the wind shadow 0..1 (r) and the rise above the ground upwind, metres (g): dune_shadow
//! sampler wind              the local turn of the wind: its cosine (r) and sine (g); (1, 0) where it is not turned
//! image   outPlan rgba32f   (lifted m, hop x, hop y, landing hop or -1)
//! uniform vec2 uHop         the short hop vector, cells (the wind's direction x the hop length), before the turn
//! uniform float uLong       the long hop's length, a multiple of the short one (1: no speed-up)
//! uniform float uSpeedup    the long hop's chance at full rise
//! uniform float uLiftBoost  the extra lifting at full rise, a multiple of uPLift
//! uniform float uSpeedFrom  the rise, metres, where the speed-up starts
//! uniform float uSpeedRef   the rise, metres, at which the speed-up is full
//! uniform int uSpeedPow     the speed-up's power: f^uSpeedPow (1: linear in the rise)
//! uniform float uSlab       slab thickness, metres
//! uniform float uMinSand    sand thinner than this, metres, is bare rock (not lifted; rock deposition odds)
//! uniform float uPLift      the chance a sand cell lifts a slab this iteration
//! uniform float uPSand      the chance a slab deposits on sand
//! uniform float uPRock      the chance a slab deposits on bare rock
//! uniform int uMaxHops      hops before a slab must deposit
//! uniform int uIter         the iteration (part of every hash)
//! uniform int uSeed         the seed (part of every hash)
//! uniform int uBound        BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float sand = texelFetch(st, p, 0).g;
  uint h = cell_hash(p, uIter, uSeed);
  vec4 rec = vec4(0.0);
  vec4 sh0 = texelFetch(shadow, p, 0);
  float f1 = clamp((sh0.g - uSpeedFrom) / max(uSpeedRef - uSpeedFrom, 1.0e-6), 0.0, 1.0);
  float f = f1;
  for (int i = 1; i < uSpeedPow; i++) {
    f = f * f1;
  }
  if (sand > uMinSand && u01(h) < uPLift * (1.0 + uLiftBoost * f) && u01(pcg2(h, 1u)) >= sh0.r) {
    vec2 h0 = u01(pcg2(h, 64u)) < uSpeedup * f ? uHop * uLong : uHop;
    vec2 cs = texelFetch(wind, p, 0).rg;
    vec2 hop = vec2(cs.x * h0.x - cs.y * h0.y, cs.y * h0.x + cs.x * h0.y);
    vec2 fl = floor(hop);
    vec2 fr = hop - fl;
    ivec2 v = ivec2(fl) + ivec2(u01(pcg2(h, 2u)) < fr.x ? 1 : 0, u01(pcg2(h, 3u)) < fr.y ? 1 : 0);
    int k = -1;
    for (int j = 1; j <= uMaxHops; j++) {
      ivec2 q = p + j * v;
      if (uBound == BOUND_PERIODIC) {
        q = wrap(q, n);
      } else if (!inside(q, n)) {
        break;                                    /* blown off an open edge: k stays -1, the sand leaves */
      }
      float sq = texelFetch(st, q, 0).g;
      float shq = texelFetch(shadow, q, 0).r;
      float pdep = shq + (1.0 - shq) * (sq > uMinSand ? uPSand : uPRock);
      if (j == uMaxHops || u01(pcg2(h, 3u + uint(j))) < pdep) {
        k = j;
        break;
      }
    }
    rec = vec4(min(sand, uSlab), float(v.x), float(v.y), float(k));
  }
  imageStore(outPlan, p, rec);
}
