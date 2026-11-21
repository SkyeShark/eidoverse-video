// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). pad_child: a child level's field padded by its parents' terrain (bake.py _Baker._pad):
//     out = up * uScale + uShift      in the margin (up: the parent's padded field cropped and upsampled onto this
//                                     level's padded grid, core/grid.js cropUpsample2)
//     out = own                       in the window (its n x n cells at uM cells in)
// numpy's `out *= F(scale); out += F(shift)` in float32, then the window assigned.
//! sampler up
//! sampler own
//! image   outF r32f
//! uniform int uM          the margin, cells
//! uniform float uScale
//! uniform float uShift

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let q = p - vec2<i32>(u.uM);
  var v = 0.0;
  if (inside(q, own_size())) {
    v = own_at(q).x;
  } else {
    v = up_at(p).x * u.uScale + u.uShift;
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
