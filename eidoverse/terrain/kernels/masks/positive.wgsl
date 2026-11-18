// Port of blender/eidoblend/terrain/masks.py at f90c6fc: a pass-through process field (wear, deposit, talus, sand)
// as compute writes it: np.maximum(v, 0). Exact.
//! sampler a
//! image   outF r32f

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  outF_store(p, vec4<f32>(max(a_at(p).x, 0.0), 0.0, 0.0, 0.0));
}
