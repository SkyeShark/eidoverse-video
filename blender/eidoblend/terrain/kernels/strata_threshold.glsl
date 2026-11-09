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
   Twin: solvers/strata.py strata_threshold. */
//! sampler st          x: h (m)
//! sampler zoff        x: z - zs, the cell's stratigraphic offset (m: dip, warp, faults, the column's placement)
//! sampler mk          w: loose thickness h - bed (m)
//! sampler rtab        z: R, the column's horizontal run (m) at zs = uRZ0 + i uRDz (1 row of uRN texels)
//! image   outP r32f   x: phi, the excess (0 where the column stands)
//! uniform float uDx   the cell, metres
//! uniform float uRZ0  the table's first height, m
//! uniform float uRDz  the table's step, m
//! uniform int uRN     the table's length
//! uniform float uRepose  tan of the loose cover's repose angle
//! uniform int uBound

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
    if (span > L) dR += run_at(zs - L) - run_at(zs - span);
    phi = dR > uDx ? 1.0 - uDx / dR : 0.0;
  }
  imageStore(outP, p, vec4(phi, 0.0, 0.0, 0.0));
}
