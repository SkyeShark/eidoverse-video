// Port of blender/eidoblend/terrain/solvers/volcanic.py cinder_cone at f90c6fc, at every point of a grid: what
// aged_cinder_cone evaluates on its patch before the blur (c = (arange(m) + 0.5) pc - half about the vent), and a
// fresh cone anywhere. The port's own kernel; the cone is kernels/volcanic/cone.wgsl's.
//! include volcanic/math
//! include volcanic/az
//! include volcanic/cone
//! sampler azt r32f
//! sampler ctab          the cone (eight texels; texel h holds the grid's origin from the vent)
//! sampler patch r32f    unused here (cone.wgsl's aged read): a stand-in
//! image   outZ r32f
//! uniform float uStep

fn kmain(p: vec2<i32>) {
  let n = outZ_size();
  if (!inside(p, n)) { return; }
  let k = cone_read(0);
  let z = cone_fresh(k.h.xy + (vec2<f32>(p) + 0.5) * u.uStep, k);
  outZ_store(p, vec4<f32>(z, 0.0, 0.0, 0.0));
}
