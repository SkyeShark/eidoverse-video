// Port of blender/eidoblend/terrain/kernels/pipes_water.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2); the `//!` header is the GLSL's, unchanged.
// The changes are WGSL's: texelFetch is <name>_at(q), imageStore is outS_store / outV_store, textureSize is
// st_size(), uniforms are u.<name>, neighbour()'s `out` argument is a pointer, `?:` is if / else, and the GLSL's
// `float[8]` / `bool[8]` arrays are function-scope vars.
//
// `precise`, which WGSL does not have (the one change that is not a spelling). The GLSL marks `lowered = dl - e;
// took = dl - lowered` (and its deposition twin) precise, so that the compiler cannot fold took back to e: exactly
// what the rounded ground lost goes into suspension. Written plainly, this machine's compiler folds it (measured:
// the exchange was the ground's own loss on 2,035 of 15,628 eroding cells of the fixtures), so each precise value
// goes through exact() (`//! include detail/exact`: an identity the compiler cannot see through), which keeps the
// lines as written; tests/detail/kernels_test.mjs checks the exchange cell by cell, conservation_test.mjs the mass.
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
//! include detail/exact

fn rain_at(q: vec2<i32>, mult: f32) -> f32 {
  if (u.uRainP >= 1.0) { return u.uRain * u.uDt * mult; }
  if (u01(cell_hash(q, u.uStep, u.uSeed)) < u.uRainP) { return u.uRain * u.uDt / u.uRainP * mult; }
  return 0.0;
}

fn flux_of(q: vec2<i32>, k: i32) -> f32 {                 /* q's outflow through its pipe k */
  if (k < 4) { return fa_at(q)[k]; }
  return fb_at(q)[k - 4];
}

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  let b0 = base_at(p).x;
  let sc = src_at(p);
  let d1 = c.y + rain_at(p, sc.x) + sc.y * u.uDt;
  let fA = fa_at(p);
  let fB = fb_at(p);
  var fo = array<f32, 8>(fA.x, fA.y, fA.z, fA.w, fB.x, fB.y, fB.z, fB.w);
  var outs = 0.0;
  var ins = 0.0;
  var q = vec2<f32>(0.0);
  var above = 0.0;                              /* how far this cell stands above its lowest neighbour */
  var rel: array<f32, 8>;                       /* b_k - b_c */
  var ok: array<bool, 8>;
  for (var k = 0; k < 8; k++) {
    outs += fo[k];
    var r: vec2<i32>;
    ok[k] = neighbour(p, k, n, u.uBound, &r);
    var fi = 0.0;
    rel[k] = 0.0;
    if (ok[k]) {
      fi = flux_of(r, 7 - k);
      rel[k] = (base_at(r).x - b0) + (st_at(r).x - c.x);
      above = max(above, -rel[k]);
    }
    ins += fi;
    q += 0.5 * vec2<f32>(OFF[k]) * (fo[k] - fi);
  }
  let d2 = max(d1 + u.uDt * (ins - outs), 0.0);
  let dbar = 0.5 * (d1 + d2);
  var vel = vec2<f32>(0.0);
  if (dbar > 1e-12) { vel = q / dbar; }
  /* tilt: central differences (one-sided at an open edge); k = 3 W, 4 E, 1 S, 6 N */
  let gx = (rel[4] - rel[3]) / max(f32(ok[4]) + f32(ok[3]), 1.0);
  let gy = (rel[6] - rel[1]) / max(f32(ok[6]) + f32(ok[1]), 1.0);
  let g2 = gx * gx + gy * gy;
  let sina = sqrt(g2 / (1.0 + g2));
  let cap = u.uKc * max(max(sina, u.uSinMin) * min(length(q), u.uQcap) - u.uQc, 0.0) *
            clamp(1.0 - d2 / u.uDmax, 0.0, 1.0);
  var dl = c.x;
  var s = c.z;
  var bed = c.w;
  if (cap > s) {
    var want = min(u.uKs * u.uDt * (cap - s), u.uMaxStep);
    want = min(want, above);
    want = min(want, max(dl + u.uMaxDepth, 0.0));
    let loose = max(dl - bed, 0.0);
    let e1 = min(want, loose);
    let e2 = (want - e1) * clamp(u.uRock * sc.z, 0.0, 1.0);
    let e = e1 + e2;
    /* exactly what the (rounded) ground lost goes into suspension, so ground + sediment is conserved; `precise`
       keeps the compiler from folding dl - (dl - e) back to e (exact(): see this file's header) */
    let z = exact_zero(n);
    let lowered = exact(dl - e, z);
    let took = exact(dl - lowered, z);
    s += took;
    dl = lowered;
    bed = min(bed, dl);
  } else {
    let dep = min(u.uKd * u.uDt * (s - cap), s);
    let z = exact_zero(n);
    let raised = exact(dl + dep, z);
    let gave = exact(raised - dl, z);
    s -= gave;
    dl = raised;
  }
  if (u.uBound == BOUND_PINNED) {
    let pn = pin_at(p);
    dl = pin_apply(dl, pn.x, pn.y);
    bed = min(bed, dl);
  }
  outS_store(p, vec4<f32>(dl, d2, s, bed));
  outV_store(p, vec4<f32>(vel, length(q), cap));            /* z: discharge per unit width, cells^2/s */
}
