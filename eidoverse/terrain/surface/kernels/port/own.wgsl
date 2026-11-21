// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2: per-cell work is GPU compute). own: a level's inputs cell by cell, before they are padded:
//   uMode 0  centre   (a - hi) - lo: h - href (and the strata mask's zs - href), href split in two float32 parts
//                     (hi = f32(href), lo = f32(href - hi)), so the difference keeps the digits numpy's float64
//                     h - href rounds to float32 once
//   uMode 1  cover    max(a, 0) + max(b, 0) + max(c, 0) over the fields uHas names (deposit, talus, sand), added in
//                     that order in float32 from zero, as bake.py's `cover += np.maximum(f[nm], 0)`
//   uMode 2  max0     max(a, 0): water, sand
//   uMode 3  aspec    max(a, uCell2) / uCell: the specific catchment (A over the cell's width)
//   uMode 4  max2     max(a, b): the catchment, the larger of the level's own and its parent's
//   uMode 5  cap      min(a, uHi): a 'thick' map held to its encoding's t_max before the pins (np.minimum(v, t_max))
//   uMode 6  margin   1 on the margin of a padded grid (uM cells wide), 0 in its window: the hero re-routing's
//                     pinned cells (bake.py _route: tgt[..., 1] = 1, tgt[m:m + n, m:m + n, 1] = 0)
//   uMode 7  floor    max(a, uHi): np.maximum(A, F(cell * cell))
//! sampler a
//! sampler b
//! sampler c
//! image   outF r32f
//! uniform int uMode
//! uniform ivec4 uHas      mode 1: which of a, b, c are given
//! uniform float uHi
//! uniform float uLo
//! uniform float uCell
//! uniform float uCell2
//! uniform int uM

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var v = 0.0;
  if (u.uMode == 0) {
    v = (a_at(p).x - u.uHi) - u.uLo;
  } else if (u.uMode == 1) {
    if (u.uHas.x != 0) { v = v + max(a_at(p).x, 0.0); }
    if (u.uHas.y != 0) { v = v + max(b_at(p).x, 0.0); }
    if (u.uHas.z != 0) { v = v + max(c_at(p).x, 0.0); }
  } else if (u.uMode == 2) {
    v = max(a_at(p).x, 0.0);
  } else if (u.uMode == 3) {
    v = max(a_at(p).x, u.uCell2) / u.uCell;
  } else if (u.uMode == 4) {
    v = max(a_at(p).x, b_at(p).x);
  } else if (u.uMode == 5) {
    v = min(a_at(p).x, u.uHi);
  } else if (u.uMode == 6) {
    if (!inside(p - vec2<i32>(u.uM), n - vec2<i32>(2 * u.uM))) { v = 1.0; }
  } else {
    v = max(a_at(p).x, u.uHi);
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
