// unpack: one RGBA pack into its four single fields, on the GPU. What blender/eidoblend/terrain/core/gpu.py
// unpack() does in numpy at f90c6fc ({name: a[..., c]}); core/gpu.js Runner.unpack() runs it. A channel nobody
// asked for is bound to a 1 x 1 dummy: a store outside a field does nothing, so only the dummy's one cell is written.
//! sampler src         the pack (rgba32f)
//! image   o0 r32f
//! image   o1 r32f
//! image   o2 r32f
//! image   o3 r32f

fn kmain(p: vec2<i32>) {
  let n = src_size();
  if (!inside(p, n)) { return; }
  let v = src_at(p);
  o0_store(p, vec4<f32>(v.x, 0.0, 0.0, 0.0));
  o1_store(p, vec4<f32>(v.y, 0.0, 0.0, 0.0));
  o2_store(p, vec4<f32>(v.z, 0.0, 0.0, 0.0));
  o3_store(p, vec4<f32>(v.w, 0.0, 0.0, 0.0));
}
