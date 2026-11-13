/* strata_threshold (design section 4.9): the composite threshold of layered rock, as the excess the isotropic
   threshold exchange (threshold.glsl, uIso = 1) relaxes. Each layer of the column stands at its own angle; between
   two heights the column needs the horizontal run
       R(zs2) - R(zs1),   R(zs) = integral of dz / tan(theta(z)) from the column's base
   (strong layers little, weak layers much), tabulated at 0.5 m (rtab). A cell's downhill step spans
       span = G dx,   G = sqrt(max(h - min(h_W, h_E), 0)^2 + max(h - min(h_S, h_N), 0)^2) / dx
   (the upwind, Rouy-Tourin gradient magnitude: exact for a plane facing any direction), from its stratigraphic
   height zs = h - zoff down to zs - span. The column lets that drop stand over one cell when it needs no more run
   than dx, so the excess is
       phi = max(1 - dx / dR, 0),   dR = R(zs) - R(zs - span)
   which for one uniform layer is the stock excess 1 - tan(theta) / G (threshold_excess). The top L metres of a
   cell (its loose cover mk.w = h - bed: talus, deposits) rest at the repose angle instead, so
       dR = min(span, L) / tan(repose) + (R(zs - L) - R(zs - span) when span > L)
   When a weak layer under a cliff is cut back, the spans at the cliff's foot take in more weak rock and their run
   grows, so the cliff fails and retreats; strong layers stand at 60-85 degrees, weak ones at 25-35, and the debris
   rests at repose on the benches. Outside the table R continues linearly with its end layers' 1 / tan.
   The rock's run is scaled by the rock mass's strength at the cell (par.z, q = exp(-resist_run n), solvers/strata.py
   rock_mass; 1 for a uniform rock mass): strong spots stand steeper, weak ones lie back, so one layer is not one
   angle all along a wall. The loose cover's repose is not scaled.
   The facies (uFac.x > 0): the rock's run is further scaled by exp(-uFac.x f), f a value noise of the cell's world
   position (wavelength uFac.y metres) and its stratigraphic height zs (uFac.z metres), so each bed's strength
   changes along the wall and from bed to bed (a cliff here is a ledgy slope there: a lateral facies change),
   where rock_mass's n is the same through every bed at one place. f: facies_noise, about unit standard deviation.
   Twin: solvers/strata.py strata_threshold. */
//! sampler st          x: h (m)
//! sampler zoff        x: z - zs, the cell's stratigraphic offset (m: dip, warp, faults, the column's placement)
//! sampler mk          w: loose thickness h - bed (m)
//! sampler rtab        z: R, the column's horizontal run (m) at zs = uRZ0 + i uRDz (1 row of uRN texels)
//! sampler par         z: q, the rock mass's run factor (0 < q; 1 = the column as tabulated)
//! image   outP r32f   x: phi, the excess (0 where the column stands)
//! uniform float uDx   the cell, metres
//! uniform float uRZ0  the table's first height, m
//! uniform float uRDz  the table's step, m
//! uniform int uRN     the table's length
//! uniform float uRepose  tan of the loose cover's repose angle
//! uniform vec3 uLv    the level: x0, y0, cell (m), for the cell's world position
//! uniform vec4 uFac   the facies: strength (0: off), horizontal wavelength (m), vertical wavelength (m), seed
//! uniform int uBound

/* the facies noise (twin: solvers/strata.py facies_noise): two octaves of trilinear value noise on the PCG lattice
   at (x / L, y / L, zs / Lz), the second at twice the frequency and half the weight, offset by 17.3 lattice units,
   scaled to about unit standard deviation */
float lattice(ivec3 c, uint s) { return 2.0 * u01(pcg4(uint(c.x), uint(c.y), uint(c.z), s)) - 1.0; }
float vnoise3(vec3 q, uint s) {
  vec3 i = floor(q);
  vec3 f = q - i;
  vec3 u = f * f * (3.0 - 2.0 * f);
  ivec3 c = ivec3(i);
  float a = mix(lattice(c, s), lattice(c + ivec3(1, 0, 0), s), u.x);
  float b = mix(lattice(c + ivec3(0, 1, 0), s), lattice(c + ivec3(1, 1, 0), s), u.x);
  float d = mix(lattice(c + ivec3(0, 0, 1), s), lattice(c + ivec3(1, 0, 1), s), u.x);
  float e = mix(lattice(c + ivec3(0, 1, 1), s), lattice(c + ivec3(1, 1, 1), s), u.x);
  return mix(mix(a, b, u.y), mix(d, e, u.y), u.z);
}
float facies_noise(vec2 xy, float zs, vec4 fac) {
  vec3 q = vec3(xy / fac.y, zs / fac.z);
  uint s = uint(fac.w);
  return (vnoise3(q, s) + 0.5 * vnoise3(2.0 * q + vec3(17.3), s + 1u)) * 2.2;
}

float run_at(float z) {
  float t = (z - uRZ0) / uRDz;
  float tn = float(uRN - 1);
  if (t <= 0.0) {
    float r0 = texelFetch(rtab, ivec2(0, 0), 0).z;
    return r0 + t * (texelFetch(rtab, ivec2(1, 0), 0).z - r0);
  }
  if (t >= tn) {
    float r1 = texelFetch(rtab, ivec2(uRN - 1, 0), 0).z;
    return r1 + (t - tn) * (r1 - texelFetch(rtab, ivec2(uRN - 2, 0), 0).z);
  }
  int i0 = int(floor(t));
  float f = t - float(i0);
  return mix(texelFetch(rtab, ivec2(i0, 0), 0).z, texelFetch(rtab, ivec2(i0 + 1, 0), 0).z, f);
}

float axis_h(ivec2 p, int k, ivec2 n, float h) {
  ivec2 q;
  return neighbour(p, k, n, uBound, q) ? texelFetch(st, q, 0).x : h;
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float h = texelFetch(st, p, 0).x;
  float gx = max(h - min(axis_h(p, 3, n, h), axis_h(p, 4, n, h)), 0.0);
  float gy = max(h - min(axis_h(p, 1, n, h), axis_h(p, 6, n, h)), 0.0);
  float span = sqrt(gx * gx + gy * gy);
  float phi = 0.0;
  if (span > 0.0) {
    float zs = h - texelFetch(zoff, p, 0).x;
    float L = max(texelFetch(mk, p, 0).w, 0.0);
    float dR = min(span, L) / uRepose;
    if (span > L) {
      float q = texelFetch(par, p, 0).z;
      if (uFac.x > 0.0) q *= exp(-uFac.x * facies_noise(world_xy(p, uLv), zs, uFac));
      dR += q * (run_at(zs - L) - run_at(zs - span));
    }
    phi = dR > uDx ? 1.0 - uDx / dR : 0.0;
  }
  imageStore(outP, p, vec4(phi, 0.0, 0.0, 0.0));
}
