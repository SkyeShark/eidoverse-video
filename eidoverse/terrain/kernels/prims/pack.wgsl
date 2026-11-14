// pack: up to four single fields into one RGBA pack, on the GPU. What blender/eidoblend/terrain/core/gpu.py pack()
// does in numpy at f90c6fc (np.zeros((h, w, 4)); out[..., c] = arrays[name]); core/gpu.js Runner.pack() runs it.
// A channel that is not given stays zero: its sampler is bound to a 1 x 1 dummy and never read.
//! sampler c0          channel 0 (r32f)
//! sampler c1          channel 1
//! sampler c2          channel 2
//! sampler c3          channel 3
//! image   outP rgba32f
//! uniform ivec4 uHas  1 where the channel is given

fn kmain(p: vec2<i32>) {
  let n = outP_size();
  if (!inside(p, n)) { return; }
  var v = vec4<f32>(0.0, 0.0, 0.0, 0.0);
  if (u.uHas.x != 0) { v.x = c0_at(p).x; }
  if (u.uHas.y != 0) { v.y = c1_at(p).x; }
  if (u.uHas.z != 0) { v.z = c2_at(p).x; }
  if (u.uHas.w != 0) { v.w = c3_at(p).x; }
  outP_store(p, v);
}
