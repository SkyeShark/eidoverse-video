// Port of blender/eidoblend/terrain/kernels/pipes_transport.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2); the `//!` header is the GLSL's, unchanged.
// The changes are WGSL's: texelFetch is <name>_at(q), imageStore is outS_store, textureSize is st2_size(), uniforms
// are u.<name>, neighbour()'s `out` argument is a pointer, `?:` is if / else, and a vec4's runtime component is
// v[k] as in GLSL.
//
// `precise`, which WGSL does not have (the one change that is not a spelling). The GLSL marks den_of's and part()'s
// lines precise so the sender (subtracting) and every receiver (adding) of one pipe's sediment compute it with the
// same bits, uncontracted and unreordered. This machine's compiler rewrites unmarked float arithmetic (measured on
// the other two pipe kernels' precise lines, tests/detail/kernels_test.mjs), so each precise value goes through
// exact() (`//! include detail/exact`: an identity the compiler cannot see through, kernels/detail/exact.wgsl), which
// keeps every line as written; tests/detail/conservation_test.mjs holds ground + sediment over 3,000 steps.
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
//! include detail/exact

// (only den_of reads it, and a GLSL `precise` value's operands are computed precisely too: exact() on each step)
fn rain_at(q: vec2<i32>, mult: f32) -> f32 {
  let z = exact_zero(st2_size());
  if (u.uRainP >= 1.0) { return exact(exact(u.uRain * u.uDt, z) * mult, z); }
  if (u01(cell_hash(q, u.uStep, u.uSeed)) < u.uRainP) {
    return exact(exact(exact(u.uRain * u.uDt, z) / u.uRainP, z) * mult, z);
  }
  return 0.0;
}

/* A sender's denominator max(d1, dt * its total outflow) and the sediment it sends through one pipe. Both are
   `precise` and written once, so the sender (subtracting) and the receiver (adding) get the same bits: the compiler
   may not contract or reorder them differently at the two sites. (`precise` is exact() here: this file's header) */
fn den_of(q: vec2<i32>, A: vec4<f32>, B: vec4<f32>) -> f32 {
  let z = exact_zero(st2_size());
  let sq = src_at(q);
  let tot = exact(exact(exact(A.x + A.y, z) + exact(A.z + A.w, z), z) +
                  exact(exact(B.x + B.y, z) + exact(B.z + B.w, z), z), z);
  let d1 = exact(exact(st0_at(q).y + rain_at(q, sq.x), z) + exact(sq.y * u.uDt, z), z);
  let den = exact(max(max(d1, exact(tot * u.uDt, z)), 1e-30), z);
  return den;
}

fn part(s: f32, f: f32, den: f32) -> f32 {
  let z = exact_zero(st2_size());
  let w = exact(f * u.uDt, z);
  let frac = exact(w / den, z);
  let a = exact(s * frac, z);
  return a;
}

fn kmain(p: vec2<i32>) {
  let n = st2_size();
  if (!inside(p, n)) { return; }
  let c = st2_at(p);
  let fA = fa_at(p);
  let fB = fb_at(p);
  let den = den_of(p, fA, fB);
  /* what this cell sends, pipe by pipe, with exactly the arithmetic its receivers use below (so the two agree to the
     bit and the total is conserved to the rounding of the sums alone) */
  var sent = 0.0;
  for (var k = 0; k < 8; k++) {
    var fk: f32;
    if (k < 4) { fk = fA[k]; } else { fk = fB[k - 4]; }
    if (fk > 0.0) { sent += part(c.z, fk, den); }
  }
  var s = c.z - sent;
  for (var k = 0; k < 8; k++) {
    var r: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &r)) { continue; }
    let rA = fa_at(r);
    let rB = fb_at(r);
    let j = 7 - k;                                   /* r's pipe toward p */
    var fin: f32;
    if (j < 4) { fin = rA[j]; } else { fin = rB[j - 4]; }
    if (fin <= 0.0) { continue; }
    s += part(st2_at(r).z, fin, den_of(r, rA, rB));
  }
  let d = c.y * max(1.0 - u.uKe * u.uDt, 0.0);
  outS_store(p, vec4<f32>(c.x, d, s, c.w));
}
