// h_keep: the inline kernel H_KEEP of blender/eidoblend/terrain/solvers/fluvial.py in WGSL
//! sampler st   x: h
//! image   outH r32f

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  outH_store(p, vec4<f32>(st_at(p).x, 0.0, 0.0, 0.0));
}
