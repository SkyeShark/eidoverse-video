// The port's own kernel (no Blender counterpart): one step of the coarse grids of blender/eidoblend/terrain/solvers/
// hillslope.py soil_solve at f90c6fc, which numpy makes with _block2 (2 x 2 block means and maxima, float64):
//     h2  = mean(h)                         the coarse start
//     hw2 = max(hold)                       a coarse cell is held when any of its cells is
//     hh2 = mean(hold hh) / mean(hold)      at their mean height (where mean(hold) > 1e-9; else mean(h))
//     pw2 = mean(pin_w), ph2 = mean(pin_h)
// con packs (hold, hh, pin_w, pin_h) as soil_jacobi reads them. The means of four float32 values are their exact sum
// rounded once and quartered (hydro/lib's sum4), numpy's float64 mean rounded to float32; mean(hold hh) multiplies in
// float32.
//! include hydro/lib
//! sampler h
//! sampler con
//! image   outH r32f
//! image   outC rgba32f

fn kmain(p: vec2<i32>) {
  if (!inside(p, outH_size())) { return; }
  let q = 2 * p;
  let a = con_at(q);
  let b = con_at(q + vec2<i32>(1, 0));
  let c = con_at(q + vec2<i32>(0, 1));
  let d = con_at(q + vec2<i32>(1, 1));
  let hm = sum4(h_at(q).x, h_at(q + vec2<i32>(1, 0)).x, h_at(q + vec2<i32>(0, 1)).x, h_at(q + vec2<i32>(1, 1)).x) * 0.25;
  let hw = max(max(a.x, b.x), max(c.x, d.x));
  let num = (a.x * a.y + b.x * b.y + c.x * c.y + d.x * d.y) * 0.25;
  let den = sum4(a.x, b.x, c.x, d.x) * 0.25;
  var hh = hm;
  if (den > 1e-9) { hh = num / max(den, 1e-12); }
  let pw = sum4(a.z, b.z, c.z, d.z) * 0.25;
  let ph = sum4(a.w, b.w, c.w, d.w) * 0.25;
  outH_store(p, vec4<f32>(hm, 0.0, 0.0, 0.0));
  outC_store(p, vec4<f32>(hw, hh, pw, ph));
}
