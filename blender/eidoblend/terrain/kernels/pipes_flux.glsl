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

float rain_at(ivec2 q, float mult) {
  if (uRainP >= 1.0) return uRain * uDt * mult;
  return u01(cell_hash(q, uStep, uSeed)) < uRainP ? uRain * uDt / uRainP * mult : 0.0;
}

float d1_at(ivec2 q, float d) {
  vec4 sq = texelFetch(src, q, 0);
  return d + rain_at(q, sq.x) + sq.y * uDt;
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float b0 = texelFetch(base, p, 0).x;
  float d1 = d1_at(p, c.y);
  vec4 fA = texelFetch(fa, p, 0);
  vec4 fB = texelFetch(fb, p, 0);
  float f[8] = float[8](fA.x, fA.y, fA.z, fA.w, fB.x, fB.y, fB.z, fB.w);
  float keep = max(1.0 - uDamp * uDt, 0.0);
  float tot = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    float dH;
    if (neighbour(p, k, n, uBound, q)) {
      vec4 cq = texelFetch(st, q, 0);
      dH = ((b0 - texelFetch(base, q, 0).x) + (c.x - cq.x)) + (d1 - d1_at(q, cq.y));
    } else if (uOutflow == 1) {
      ivec2 m = p - OFF[k];
      float dm = 0.0;
      if (inside(m, n)) dm = (texelFetch(base, m, 0).x - b0) + (texelFetch(st, m, 0).x - c.x);
      dH = dm + d1;
    } else {
      f[k] = 0.0;
      continue;
    }
    f[k] = max(0.0, f[k] * keep + uDt * uPipe * WISO[k] * dH);
    tot += f[k];
  }
  float K = (tot * uDt > d1) ? d1 / (tot * uDt) : 1.0;
  imageStore(outA, p, vec4(f[0], f[1], f[2], f[3]) * K);
  imageStore(outB, p, vec4(f[4], f[5], f[6], f[7]) * K);
}
