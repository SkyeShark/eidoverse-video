// Port of blender/eidoblend/terrain/masks.py at f90c6fc: rock_shadow's np.fmax(out, far, out=out) (neither holds
// NaN there: both are maxima from 0). Exact.
//! sampler a
//! sampler b
//! image   outF r32f

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  outF_store(p, vec4<f32>(max(a_at(p).x, b_at(p).x), 0.0, 0.0, 0.0));
}
