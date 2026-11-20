// Port of blender/eidoblend/terrain/kernels/strata_threshold.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2); the `//!` header is the GLSL's, unchanged.
// The changes are WGSL's: texelFetch(x, q, 0) is x_at(q), imageStore is outP_store, textureSize is st_size(), a
// uniform uX is u.uX, neighbour()'s `out` argument is a pointer, `?:` is select(), and vnoise3's local `u` (the GLSL's
// smoothstep weights) is `w3`, since `u` names the uniform block here. The facies functions stay inline, as the GLSL
// file has them (solvers/strata.py FACIES_GLSL is the same text, which strata_weather.wgsl includes as
// kernels/strata/facies.wgsl).
//
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
fn lattice(c: vec3<i32>, s: u32) -> f32 { return 2.0 * u01(pcg4(u32(c.x), u32(c.y), u32(c.z), s)) - 1.0; }
fn vnoise3(q: vec3<f32>, s: u32) -> f32 {
  let i = floor(q);
  let f = q - i;
  let w3 = f * f * (3.0 - 2.0 * f);
  let c = vec3<i32>(i);
  let a = mix(lattice(c, s), lattice(c + vec3<i32>(1, 0, 0), s), w3.x);
  let b = mix(lattice(c + vec3<i32>(0, 1, 0), s), lattice(c + vec3<i32>(1, 1, 0), s), w3.x);
  let d = mix(lattice(c + vec3<i32>(0, 0, 1), s), lattice(c + vec3<i32>(1, 0, 1), s), w3.x);
  let e = mix(lattice(c + vec3<i32>(0, 1, 1), s), lattice(c + vec3<i32>(1, 1, 1), s), w3.x);
  return mix(mix(a, b, w3.y), mix(d, e, w3.y), w3.z);
}
fn facies_noise(xy: vec2<f32>, zs: f32, fac: vec4<f32>) -> f32 {
  let q = vec3<f32>(xy / fac.y, zs / fac.z);
  let s = u32(fac.w);
  return (vnoise3(q, s) + 0.5 * vnoise3(2.0 * q + vec3<f32>(17.3), s + 1u)) * 2.2;
}

fn run_at(z: f32) -> f32 {
  let t = (z - u.uRZ0) / u.uRDz;
  let tn = f32(u.uRN - 1);
  if (t <= 0.0) {
    let r0 = rtab_at(vec2<i32>(0, 0)).z;
    return r0 + t * (rtab_at(vec2<i32>(1, 0)).z - r0);
  }
  if (t >= tn) {
    let r1 = rtab_at(vec2<i32>(u.uRN - 1, 0)).z;
    return r1 + (t - tn) * (r1 - rtab_at(vec2<i32>(u.uRN - 2, 0)).z);
  }
  let i0 = i32(floor(t));
  let f = t - f32(i0);
  return mix(rtab_at(vec2<i32>(i0, 0)).z, rtab_at(vec2<i32>(i0 + 1, 0)).z, f);
}

fn axis_h(p: vec2<i32>, k: i32, n: vec2<i32>, h: f32) -> f32 {
  var q: vec2<i32>;
  if (neighbour(p, k, n, u.uBound, &q)) { return st_at(q).x; }
  return h;
}

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let h = st_at(p).x;
  let gx = max(h - min(axis_h(p, 3, n, h), axis_h(p, 4, n, h)), 0.0);
  let gy = max(h - min(axis_h(p, 1, n, h), axis_h(p, 6, n, h)), 0.0);
  let span = sqrt(gx * gx + gy * gy);
  var phi = 0.0;
  if (span > 0.0) {
    let zs = h - zoff_at(p).x;
    let L = max(mk_at(p).w, 0.0);
    var dR = min(span, L) / u.uRepose;
    if (span > L) {
      var q = par_at(p).z;
      if (u.uFac.x > 0.0) { q *= exp(-u.uFac.x * facies_noise(world_xy(p, u.uLv), zs, u.uFac)); }
      dR += q * (run_at(zs - L) - run_at(zs - span));
    }
    phi = select(0.0, 1.0 - u.uDx / dR, dR > u.uDx);
  }
  outP_store(p, vec4<f32>(phi, 0.0, 0.0, 0.0));
}
