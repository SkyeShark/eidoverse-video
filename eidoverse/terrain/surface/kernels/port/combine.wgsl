// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). combine: rgba fields put together, cell by cell, where bake.py stacks numpy arrays (one channel
// of a field cropped to a window is pick.wgsl's):
//   uMode 0  tk       (a.x, a.y, b.z, b.w): what a child reads of its parent's crest pass, np.concatenate([outK
//                     [..., :2], outC[..., 2:4]], axis=2) (a = outK, b = outC)
//   uMode 2  steer    (0, 0, a.x, b.x) at the window cell nearest (edges held): the routed flow's unit vector padded
//                     by np.pad(..., mode='edge'), a = flow_x / L, b = flow_y / L of the own window (uOffset = -m)
//! sampler a
//! sampler b
//! image   outF rgba32f
//! uniform int uMode
//! uniform ivec2 uOffset

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var v = vec4<f32>(0.0);
  if (u.uMode == 0) {
    let k = a_at(p);
    let c = b_at(p);
    v = vec4<f32>(k.x, k.y, c.z, c.w);
  } else {
    let q = clamp(p + u.uOffset, vec2<i32>(0), a_size() - 1);
    v = vec4<f32>(0.0, 0.0, a_at(q).x, b_at(q).x);
  }
  outF_store(p, v);
}
