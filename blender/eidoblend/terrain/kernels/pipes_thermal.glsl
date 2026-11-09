/* pipes_thermal: the thermal pass of the virtual-pipe model (design sections 4.4 step 8, 4.2 and 4.12): threshold
   failure through 8 pipes, mass-conserving, for two materials. Its numpy twin is solvers/hydraulic.py
   `pipes_thermal`. Cell units (heights / cell, so a threshold is a tangent and a pipe is LEN[k] long), the ground as
   base + delta (see pipes_flux.glsl).

   For each neighbour pair (this cell c and q) the higher cell sheds toward the lower one
       moved = uRate * max(e_rock, e_loose)
       e_rock  = min(max(|dh| - Sc_pair * LEN[k], 0),       Sc_pair: the mean of the two cells' thresholds; the
                     delta_hi - floor_hi)                   higher cell's floor (par.z) bounds how deep its cohesive
                                                            ground fails, so a failure stays a local scar instead of
                                                            retreating up a whole wall
       e_loose = min(max(|dh| - R_pair * LEN[k], 0), t_hi)  R_pair: the mean repose; t_hi: the higher cell's loose
                                                            cover (ground - bed): debris slides at repose, the
                                                            cohesive ground only above its own threshold (rock
                                                            breakup's noisy one)
   The exchange depends only on the pair, so what c loses q gains: the total is conserved (the design's threshold
   pass, with the repose rule of section 4.2 on loose material). `bed` is the top of the cohesive ground (rock, or
   soil in place): what fails becomes loose debris where it lands (bed stays below it). outT.x accumulates each cell's
   net change by sliding (signed; its positive part is the talus thickness). uRate <= 1/8 keeps every cell from
   shedding more than its excess. Water and sediment pass through. PINNED mode holds the ground to its pin.
   Float32: an exchange of 1e-7 cells added to a change of several cells is partly rounded away, and over thousands
   of passes that loses mass systematically (measured: 4e-6 of the material moved; 1e-11 in float64). outT.y carries
   what the rounding dropped into the next pass (Kahan's compensation), so it is not lost. */
//! sampler st          x: delta (ground - base), y: d water, z: s sediment, w: bed - base
//! sampler base        x: b0 (cell units)
//! sampler par         x: threshold of the cohesive ground (tangent), y: repose of debris (tangent), z: failure floor
/*                      (par.z: the delta, cell units, the cohesive ground may fail down to; -1e6 for none) */
//! sampler pin         x: pin_w (0..1), y: pin_h - base (cell units)
//! sampler tacc        x: net change by sliding so far (cell units), y: the rounding carried from the last pass
//! image   outS rgba32f
//! image   outT rgba32f
//! uniform float uRate
//! uniform int uBound
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float b0 = texelFetch(base, p, 0).x;
  vec4 pc = texelFetch(par, p, 0);
  float tc = max(c.x - c.w, 0.0);
  float db = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    vec4 cq = texelFetch(st, q, 0);
    vec4 pq = texelFetch(par, q, 0);
    float dh = (b0 - texelFetch(base, q, 0).x) + (c.x - cq.x);
    float adh = abs(dh);
    float t_hi = dh > 0.0 ? tc : max(cq.x - cq.w, 0.0);
    float room = dh > 0.0 ? max(c.x - pc.z, 0.0) : max(cq.x - pq.z, 0.0);
    float e_rock = min(max(adh - 0.5 * (pc.x + pq.x) * LEN[k], 0.0), room);
    float e_loose = min(max(adh - 0.5 * (pc.y + pq.y) * LEN[k], 0.0), t_hi);
    float m = uRate * max(e_rock, e_loose);
    db += dh > 0.0 ? -m : m;
  }
  vec4 ta = texelFetch(tacc, p, 0);
  /* `precise`: without it the compiler may fold dbc - ((x + dbc) - x) to 0 and drop the compensation (GLSL allows
     such rewrites; the GPU's drift was unchanged until these were marked) */
  precise float dbc = db + ta.y;
  precise float dl = c.x + dbc;
  precise float carry = dbc - (dl - c.x);
  float bed = min(c.w, dl);
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    dl = pin_apply(dl, pn.x, pn.y);
    bed = min(bed, dl);
  }
  imageStore(outS, p, vec4(dl, c.y, c.z, bed));
  imageStore(outT, p, vec4(ta.x + db, carry, 0.0, 0.0));
}
