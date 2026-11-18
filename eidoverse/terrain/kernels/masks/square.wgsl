// Port of blender/eidoblend/terrain/masks.py at f90c6fc: the peaks' gr * gr (the window grid squared, which numpy
// squares in float64 and rounds once before its blur; here float32 of the float32 grid).
//! sampler a
//! image   outF r32f

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let v = a_at(p).x;
  outF_store(p, vec4<f32>(v * v, 0.0, 0.0, 0.0));
}
