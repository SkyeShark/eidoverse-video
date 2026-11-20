// Small reads solvers/coast.js needs between the coast's numpy lines (blender/eidoblend/terrain/solvers/coast.py at
// f90c6fc), as a kernel: uChannel >= 0 copies that channel of `src` (a channel of a pack, as numpy indexes it);
// uChannel -1 is op_coast's record mask np.abs(phi) < uK as 1 / 0.

//! sampler src
//! image   outF r32f
//! uniform int uChannel
//! uniform float uK
fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let v = src_at(p);
  if (u.uChannel < 0) {
    outF_store(p, vec4<f32>(select(0.0, 1.0, abs(v.x) < u.uK), 0.0, 0.0, 0.0));
    return;
  }
  outF_store(p, vec4<f32>(v[u.uChannel], 0.0, 0.0, 0.0));
}
