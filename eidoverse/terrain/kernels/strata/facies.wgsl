// Port of FACIES_GLSL in blender/eidoblend/terrain/solvers/strata.py at f90c6fc.
//
// The facies noise, shared text (no `//!` interface: an include). Blender concatenates FACIES_GLSL into the inline
// kernel STRATA_WEATHER's source; here kernels/strata_weather.wgsl declares `//! include strata/facies`, which the
// runner prefixes the same way (core/gpu.js, PORT_PLAN.md 4.2), and so does the port's own kernels/strata/final.wgsl
// (facies_factor). kernels/strata_threshold.wgsl keeps its own inline copy, as strata_threshold.glsl does. Changes:
// WGSL's syntax, and vnoise3's local `u` (the smoothstep weights) is `w3`, since `u` names the uniform block here.
//
// Two octaves of trilinear value noise on the PCG lattice at (x / L, y / L, zs / Lz), about unit standard deviation;
// fac = (strength, L, Lz, seed). Each bed's strength varies along the wall and from bed to bed (rock_mass's n is one
// value through every bed at a place). Twin: solvers/strata.py facies_noise.
fn lattice(c: vec3<i32>, s: u32) -> f32 { return 2.0 * u01(pcg4(u32(c.x), u32(c.y), u32(c.z), s)) - 1.0; }
fn vnoise3(q: vec3<f32>, s: u32) -> f32 {
  let i = floor(q);
  let f = q - i;
  let w3 = f * f * (3.0 - 2.0 * f);
  let c = vec3<i32>(i);
  let a = mix(lattice(c, s), lattice(c + vec3<i32>(1, 0, 0), s), w3.x);
  let b = mix(lattice(c + vec3<i32>(0, 1, 0), s), lattice(c + vec3<i32>(1, 1, 0), s), w3.x);
  let d = mix(lattice(c + vec3<i32>(0, 0, 1), s), lattice(c + vec3<i32>(1, 0, 1), s), w3.x);
  let e = mix(lattice(c + vec3<i32>(0, 1, 1), s), lattice(c + vec3<i32>(1, 1, 1), s), w3.x);
  return mix(mix(a, b, w3.y), mix(d, e, w3.y), w3.z);
}
fn facies_noise(xy: vec2<f32>, zs: f32, fac: vec4<f32>) -> f32 {
  let q = vec3<f32>(xy / fac.y, zs / fac.z);
  let s = u32(fac.w);
  return (vnoise3(q, s) + 0.5 * vnoise3(2.0 * q + vec3<f32>(17.3), s + 1u)) * 2.2;
}
