/* pipes_transport: pass 3 of the virtual-pipe model (design section 4.4): sediment moves with the water, then the
   water evaporates. Its numpy twin is solvers/hydraulic.py `pipes_transport`. Cell units (see pipes_flux.glsl).

   The design names Mei's semi-Lagrangian advection; it does not conserve sediment (a back-traced bilinear read
   creates and destroys mass), and this package's test is that water plus sediment are conserved. So the suspended
   sediment travels with the water's own pipe fluxes (donor cell): a cell that sends the fraction
       phi = dt * f_k / max(d1, dt * sum_k f_k)
   of its water (d1: its depth after rain, which bounds what pipes_flux let it send) through pipe k sends the same
   fraction of its sediment. What one cell sends is exactly what its neighbour receives, so the total is conserved
   to rounding; the only losses are the open edge's outflow. Then d *= max(1 - Ke dt, 0). */
//! sampler st2         x: delta (ground - base), y: d2, z: s, w: bed - base, after pipes_water
//! sampler st0         the step's start (its water depth gives d1)
//! sampler fa          this step's outflow fluxes k = 0..3
//! sampler fb          k = 4..7
//! sampler src         x: rain multiplier, y: inflow (depth per second)
//! image   outS rgba32f
//! uniform float uDt
//! uniform float uRain
//! uniform float uRainP
//! uniform float uKe       evaporation, per second
//! uniform int uStep
//! uniform int uSeed
//! uniform int uBound

float rain_at(ivec2 q, float mult) {
  if (uRainP >= 1.0) return uRain * uDt * mult;
  return u01(cell_hash(q, uStep, uSeed)) < uRainP ? uRain * uDt / uRainP * mult : 0.0;
}

/* A sender's denominator max(d1, dt * its total outflow) and the sediment it sends through one pipe. Both are
   `precise` and written once, so the sender (subtracting) and the receiver (adding) get the same bits: the compiler
   may not contract or reorder them differently at the two sites. */
float den_of(ivec2 q, vec4 A, vec4 B) {
  vec4 sq = texelFetch(src, q, 0);
  precise float tot = ((A.x + A.y) + (A.z + A.w)) + ((B.x + B.y) + (B.z + B.w));
  precise float d1 = (texelFetch(st0, q, 0).y + rain_at(q, sq.x)) + sq.y * uDt;
  precise float den = max(max(d1, tot * uDt), 1e-30);
  return den;
}

float part(float s, float f, float den) {
  precise float w = f * uDt;
  precise float frac = w / den;
  precise float a = s * frac;
  return a;
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st2, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st2, p, 0);
  vec4 fA = texelFetch(fa, p, 0);
  vec4 fB = texelFetch(fb, p, 0);
  float den = den_of(p, fA, fB);
  /* what this cell sends, pipe by pipe, with exactly the arithmetic its receivers use below (so the two agree to the
     bit and the total is conserved to the rounding of the sums alone) */
  float sent = 0.0;
  for (int k = 0; k < 8; k++) {
    float fk = k < 4 ? fA[k] : fB[k - 4];
    if (fk > 0.0) sent += part(c.z, fk, den);
  }
  float s = c.z - sent;
  for (int k = 0; k < 8; k++) {
    ivec2 r;
    if (!neighbour(p, k, n, uBound, r)) continue;
    vec4 rA = texelFetch(fa, r, 0);
    vec4 rB = texelFetch(fb, r, 0);
    int j = 7 - k;                                   /* r's pipe toward p */
    float fin = j < 4 ? rA[j] : rB[j - 4];
    if (fin <= 0.0) continue;
    s += part(texelFetch(st2, r, 0).z, fin, den_of(r, rA, rB));
  }
  float d = c.y * max(1.0 - uKe * uDt, 0.0);
  imageStore(outS, p, vec4(c.x, d, s, c.w));
}
