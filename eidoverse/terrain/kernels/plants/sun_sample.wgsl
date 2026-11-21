// plants/sun_sample: plant_instances.py sun_shade at the spots' card centres, one level: the level's sweep
// (plants/sun_sweep) read bilinear (clamped) at the point's (s, w), less the point's own z + s tan(el); the largest
// over the levels so far. The card centre: the spot's base (_base_z: sink x scale under the ground, deeper by the
// drop across the foot) raised by its billboard's centre, scale x k x centre of its individual.
//! include plants/lib
//! sampler rec r32f      the spots' records, 12 numbers each
//! sampler vk r32f       per individual: k (the size per unit scale), the billboard's centre height (tree units)
//! sampler pm r32f       the level's sweep, nw x ns
//! sampler ex r32f       per spot: the excess so far
//! image   outE r32f     per spot: the excess after this level
//! uniform vec4 uDir     ux, uy, tan(el), 0
//! uniform vec4 uGrid    s0, w0, ns, nw
//! uniform vec4 uBase    sink, foot, the cell, the individuals
//! uniform int  uCount

fn pmb(ns: i32, i: i32, j: i32) -> f32 { return pm_b[j * ns + i]; }

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = 12 * q;
  let x = rec_b[o];
  let y = rec_b[o + 1];
  let sc = rec_b[o + 4];
  let tn = sqrt(rec_b[o + 7] * rec_b[o + 7] + rec_b[o + 8] * rec_b[o + 8]) / max(rec_b[o + 9], 0.2);
  let zb = rec_b[o + 2] - sc * (u.uBase.x + u.uBase.y * min(tn, 2.0));
  let v = clamp(i32(rec_b[o + 10]), 0, i32(u.uBase.w) - 1);
  let pz = zb + sc * vk_b[2 * v] * vk_b[2 * v + 1];
  let ux = u.uDir.x;
  let uy = u.uDir.y;
  let sp = -(x * ux + y * uy);
  let wp = -x * uy + y * ux;
  let c = u.uBase.z;
  let ns = i32(u.uGrid.z);
  let nw = i32(u.uGrid.w);
  let ci = clamp((sp - u.uGrid.x) / c, 0.0, f32(ns) - 1.001);
  let cj = clamp((wp - u.uGrid.y) / c, 0.0, f32(nw) - 1.001);
  let i0 = i32(ci);
  let j0 = i32(cj);
  let ti = ci - f32(i0);
  let tj = cj - f32(j0);
  let m = (pmb(ns, i0, j0) * (1.0 - ti) + pmb(ns, i0 + 1, j0) * ti) * (1.0 - tj) +
          (pmb(ns, i0, j0 + 1) * (1.0 - ti) + pmb(ns, i0 + 1, j0 + 1) * ti) * tj;
  outE_b[q] = max(ex_b[q], m - (pz + sp * u.uDir.z));
}
