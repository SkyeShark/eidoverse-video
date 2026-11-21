// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). settle: the settled layer's start and its map (bake.py step 6), cell by cell:
//   uMode 0  start    outF = layer + max(a - layer, 0) on a child (a: its parent's settled layer, cropped and
//                     upsampled), layer on the coarsest: numpy's np.full(layer) += np.maximum(inherit - F(layer), 0)
//   uMode 1  map      at the window's cells (uM in): clamp(a / layer, 0, 2) x 0.5 (a: the relaxed layer, metres)
//! sampler a
//! image   outF r32f
//! uniform int uMode
//! uniform int uChild
//! uniform int uM
//! uniform float uLayer

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var v = 0.0;
  if (u.uMode == 0) {
    v = u.uLayer;
    if (u.uChild != 0) { v = v + max(a_at(p).x - u.uLayer, 0.0); }
  } else {
    v = clamp(a_at(p + vec2<i32>(u.uM)).x / u.uLayer, 0.0, 2.0) * 0.5;
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
