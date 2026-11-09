/* pipes_water: pass 2 of the virtual-pipe model (design section 4.4): the water update, the velocity, and erosion or
   deposition against the transport capacity. Its numpy twin is solvers/hydraulic.py `pipes_water`. Cell units, and
   the ground as base + delta (see pipes_flux.glsl).

   Water: d2 = d1 + dt (sum of the neighbours' fluxes into this cell - sum of this cell's outflows), d1 the depth after
   rain (recomputed exactly as pipes_flux does). Velocity (cells per second): the net volume flux through the cell,
   q = 0.5 sum_k OFF[k] (f_out_k - f_in_k) (the 4-pipe model's dWx generalised to 8 pipes), divided by the mean depth.

   Capacity: C = Kc * max(max(sin a, uSinMin) * min(|q|, uQcap) - uQc, 0) * clamp(1 - d2 / uDmax, 0, 1). |q| = depth x
   speed is the discharge per unit width, so C is excess stream power (q S above a critical uQc, the soil's critical
   shear): sheet flow on a planar slope stays under it and leaves the ground alone, while flow gathered by the
   ground's micro-relief exceeds it and cuts rills (Jako's |v| alone erodes a thin film as hard as a channel: sheet
   erosion, no rills). uQcap caps the discharge the capacity sees at a small catchment's: this pass makes rills and
   gullies, and a river that gathers a whole hero window (the backbone's channel, already in the parent) is not cut
   deeper here. The depth ramp lets deep (ponded) water drop its load. sin a is the ground's tilt (central
   differences).

   Under capacity the ground is eroded by Ks dt (C - s): loose debris (above `bed`, the top of the cohesive ground)
   first, then the cohesive ground at its erodibility uRock x src.z (soil about 0.5, rock about 0.05 x the rock
   breakup's K factor), never deeper than uMaxStep a step, nor below the lowest neighbour (no pits), nor more than
   uMaxDepth below where the run started (detail stays detail); `bed` follows the ground down. Over capacity,
   Kd dt (s - C) settles as loose debris. PINNED mode holds the ground to its pin (the border band). */
//! sampler st          x: delta (ground - base), y: d water, z: s suspended sediment, w: bed - base: the step's start
//! sampler base        x: b0 (cell units)
//! sampler fa          this step's outflow fluxes k = 0..3 (pipes_flux)
//! sampler fb          k = 4..7
//! sampler src         x: rain multiplier, y: inflow (depth per second), z: erodibility of the cohesive ground
//! sampler pin         x: pin_w (0..1), y: pin_h - base (cell units)
//! image   outS rgba32f
//! image   outV rgba32f
//! uniform float uDt
//! uniform float uRain
//! uniform float uRainP
//! uniform float uKc       capacity coefficient (seconds per cell)
//! uniform float uKs       dissolving (erosion) rate, per second
//! uniform float uKd       deposition rate, per second
//! uniform float uSinMin   the smallest tilt the capacity sees (so flats still carry a little)
//! uniform float uQc       critical stream power (tilt x discharge per unit width, cells^2/s)
//! uniform float uQcap     the largest discharge per unit width the capacity sees (cells^2/s)
//! uniform float uMaxDepth the deepest the run cuts below its start (cell units)
//! uniform float uDmax     water deeper than this (cell units) carries nothing
//! uniform float uRock     a multiplier on src.z (1 in production)
//! uniform float uMaxStep  the most a cell is lowered in one step (cell units)
//! uniform int uStep
//! uniform int uSeed
//! uniform int uBound

float rain_at(ivec2 q, float mult) {
  if (uRainP >= 1.0) return uRain * uDt * mult;
  return u01(cell_hash(q, uStep, uSeed)) < uRainP ? uRain * uDt / uRainP * mult : 0.0;
}

float flux_of(ivec2 q, int k) {                 /* q's outflow through its pipe k */
  return k < 4 ? texelFetch(fa, q, 0)[k] : texelFetch(fb, q, 0)[k - 4];
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float b0 = texelFetch(base, p, 0).x;
  vec4 sc = texelFetch(src, p, 0);
  float d1 = c.y + rain_at(p, sc.x) + sc.y * uDt;
  vec4 fA = texelFetch(fa, p, 0);
  vec4 fB = texelFetch(fb, p, 0);
  float fo[8] = float[8](fA.x, fA.y, fA.z, fA.w, fB.x, fB.y, fB.z, fB.w);
  float outs = 0.0;
  float ins = 0.0;
  vec2 q = vec2(0.0);
  float above = 0.0;                            /* how far this cell stands above its lowest neighbour */
  float rel[8];                                 /* b_k - b_c */
  bool ok[8];
  for (int k = 0; k < 8; k++) {
    outs += fo[k];
    ivec2 r;
    ok[k] = neighbour(p, k, n, uBound, r);
    float fi = 0.0;
    rel[k] = 0.0;
    if (ok[k]) {
      fi = flux_of(r, 7 - k);
      rel[k] = (texelFetch(base, r, 0).x - b0) + (texelFetch(st, r, 0).x - c.x);
      above = max(above, -rel[k]);
    }
    ins += fi;
    q += 0.5 * vec2(OFF[k]) * (fo[k] - fi);
  }
  float d2 = max(d1 + uDt * (ins - outs), 0.0);
  float dbar = 0.5 * (d1 + d2);
  vec2 vel = dbar > 1e-12 ? q / dbar : vec2(0.0);
  /* tilt: central differences (one-sided at an open edge); k = 3 W, 4 E, 1 S, 6 N */
  float gx = (rel[4] - rel[3]) / max(float(ok[4]) + float(ok[3]), 1.0);
  float gy = (rel[6] - rel[1]) / max(float(ok[6]) + float(ok[1]), 1.0);
  float g2 = gx * gx + gy * gy;
  float sina = sqrt(g2 / (1.0 + g2));
  float cap = uKc * max(max(sina, uSinMin) * min(length(q), uQcap) - uQc, 0.0) * clamp(1.0 - d2 / uDmax, 0.0, 1.0);
  float dl = c.x;
  float s = c.z;
  float bed = c.w;
  if (cap > s) {
    float want = min(uKs * uDt * (cap - s), uMaxStep);
    want = min(want, above);
    want = min(want, max(dl + uMaxDepth, 0.0));
    float loose = max(dl - bed, 0.0);
    float e1 = min(want, loose);
    float e2 = (want - e1) * clamp(uRock * sc.z, 0.0, 1.0);
    float e = e1 + e2;
    /* exactly what the (rounded) ground lost goes into suspension, so ground + sediment is conserved; `precise`
       keeps the compiler from folding dl - (dl - e) back to e */
    precise float lowered = dl - e;
    precise float took = dl - lowered;
    s += took;
    dl = lowered;
    bed = min(bed, dl);
  } else {
    float dep = min(uKd * uDt * (s - cap), s);
    precise float raised = dl + dep;
    precise float gave = raised - dl;
    s -= gave;
    dl = raised;
  }
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    dl = pin_apply(dl, pn.x, pn.y);
    bed = min(bed, dl);
  }
  imageStore(outS, p, vec4(dl, d2, s, bed));
  imageStore(outV, p, vec4(vel, length(q), cap));            /* z: discharge per unit width, cells^2/s */
}
