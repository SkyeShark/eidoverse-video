// Port of blender/eidoblend/terrain/kernels/pipes_flux.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2); the `//!` header is the GLSL's, unchanged.
// The changes are WGSL's: texelFetch(st, q, 0) is st_at(q), imageStore is outA_store, textureSize is st_size(),
// uniforms are u.<name>, neighbour()'s `out` argument is a pointer, the conditional operator `?:` is if / else, and
// the flux array is a function-scope var (WGSL indexes a var by a runtime index).
//
/* pipes_flux: pass 1 of the virtual-pipe shallow-water model (design section 4.4; Mei, Decaudin & Hu 2007, Jako 2011)
   in its 8-pipe form. Its numpy twin is solvers/hydraulic.py `pipes_flux`.

   Units: CELL UNITS. Lengths and heights are metres / cell (a cell is 1 long), time is seconds of the model clock,
   so Jako's parameters apply unchanged at every cell size ("scaled with the cell size").

   Precision: the ground is b = b0 + delta, b0 the surface the run started from (the `base` texture, constant) and
   delta (st.x) the change since, so a step's erosion of 1e-6 cells is kept in full even where b0 is hundreds of
   cells (a float32 b would round it away). Height differences are taken as (b0_c - b0_k) + (delta_c - delta_k).

   Rain falls first: a cell's water after rain is d1 = d + rain + inflow * dt, where rain is uRain * dt on every cell
   (uRainP >= 1) or uRain * dt / uRainP on a random uRainP of the cells each step (PCG hash of cell, step and seed),
   times the cell's rain multiplier. Each neighbour's d1 is recomputed here the same way, so no texture holds it.

   Flux through pipe k (the 8 neighbours, OFF / LEN / WISO of common.glsl) grows with the water-surface drop:
       f_k = max(0, f_k * (1 - uDamp dt) + dt * uPipe * WISO[k] * dH_k),   dH_k = (b - b_k) + (d1 - d1_k)
   WISO (sides 2/3, diagonals 1/6) makes the eight pipes the isotropic 9-point Laplacian, so channels do not prefer
   the grid axes (4 pipes comb rills along x and y). uDamp is a linear friction that gives water a terminal speed on
   long slopes. The outflow is then scaled so a cell never sends more water than it holds:
       K = min(1, d1 / (dt * sum_k f_k)).
   Edges (OPEN / PINNED modes): with uOutflow 1 the pipe off the grid leads to a dry virtual cell whose ground
   continues the slope (b_virtual = 2 b - b_opposite), so water leaves downhill edges; with uOutflow 0 the edge is a
   wall. PERIODIC wraps. */
//! sampler st          x: delta (ground - base, cell units), y: d water depth, z: s suspended sediment, w: bed - base
//! sampler base        x: b0, the ground the run started from (cell units)
//! sampler fa          the outflow fluxes of the previous step to neighbours k = 0..3 (SW, S, SE, W)
//! sampler fb          k = 4..7 (E, NW, N, NE)
//! sampler src         x: rain multiplier, y: inflow (depth per second), z: erodibility (pipes_water), w: unused
//! image   outA rgba32f
//! image   outB rgba32f
//! uniform float uDt       model seconds per step
//! uniform float uRain     rain, depth (cell units) per second
//! uniform float uRainP    the fraction of cells rained on each step (1: all)
//! uniform float uPipe     pipe cross-section x gravity / pipe length (Jako: 20 x 9.81 / 1)
//! uniform float uDamp     friction, per second
//! uniform int uStep
//! uniform int uSeed
//! uniform int uBound
//! uniform int uOutflow

fn rain_at(q: vec2<i32>, mult: f32) -> f32 {
  if (u.uRainP >= 1.0) { return u.uRain * u.uDt * mult; }
  if (u01(cell_hash(q, u.uStep, u.uSeed)) < u.uRainP) { return u.uRain * u.uDt / u.uRainP * mult; }
  return 0.0;
}

fn d1_at(q: vec2<i32>, d: f32) -> f32 {
  let sq = src_at(q);
  return d + rain_at(q, sq.x) + sq.y * u.uDt;
}

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  let b0 = base_at(p).x;
  let d1 = d1_at(p, c.y);
  let fA = fa_at(p);
  let fB = fb_at(p);
  var f = array<f32, 8>(fA.x, fA.y, fA.z, fA.w, fB.x, fB.y, fB.z, fB.w);
  let keep = max(1.0 - u.uDamp * u.uDt, 0.0);
  var tot = 0.0;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    var dH: f32;
    if (neighbour(p, k, n, u.uBound, &q)) {
      let cq = st_at(q);
      dH = ((b0 - base_at(q).x) + (c.x - cq.x)) + (d1 - d1_at(q, cq.y));
    } else if (u.uOutflow == 1) {
      let m = p - OFF[k];
      var dm = 0.0;
      if (inside(m, n)) { dm = (base_at(m).x - b0) + (st_at(m).x - c.x); }
      dH = dm + d1;
    } else {
      f[k] = 0.0;
      continue;
    }
    f[k] = max(0.0, f[k] * keep + u.uDt * u.uPipe * WISO[k] * dH);
    tot += f[k];
  }
  var K = 1.0;
  if (tot * u.uDt > d1) { K = d1 / (tot * u.uDt); }
  outA_store(p, vec4<f32>(f[0], f[1], f[2], f[3]) * K);
  outB_store(p, vec4<f32>(f[4], f[5], f[6], f[7]) * K);
}
