// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's convex and concave at one scale, float32:
// bend = (profile + plan) scale; convex = smoothstep(bend[0], bend[1], bend), concave = the same of -bend.
//! include masks/lib
//! sampler kp            profile curvature at the kept cells
//! sampler kt            plan curvature
//! image   outV r32f     convex
//! image   outC r32f     concave
//! uniform float uS      float32(scale, metres)
//! uniform vec2 uBend    smoothstep(bend): (e0, k)

fn kmain(p: vec2<i32>) {
  let n = outV_size();
  if (!inside(p, n)) { return; }
  let bend = (kp_at(p).x + kt_at(p).x) * u.uS;
  outV_store(p, vec4<f32>(ss(bend, u.uBend), 0.0, 0.0, 0.0));
  outC_store(p, vec4<f32>(ss(-bend, u.uBend), 0.0, 0.0, 0.0));
}
