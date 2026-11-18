// Port of the inline kernel EXCESS ('threshold_excess') of blender/eidoblend/terrain/solvers/hillslope.py at f90c6fc.
//
// Transcribed statement for statement from the GLSL source in hillslope.py (PORT_PLAN.md 3.3: an inline kernel
// becomes a file of the same name), starting from the design probe's transcription
// (tests/design_probes/wgsl/threshold_excess.wgsl); the `//!` header is the GLSL's, unchanged. The changes are
// WGSL's: texelFetch(x, q, 0) is x_at(q), imageStore is outP_store, textureSize is st_size(), a uniform uX is u.uX,
// neighbour()'s `out` argument is a pointer, and the two ?: are ifs.
//
// The isotropic threshold's first pass, once per iteration: every cell's excess over its threshold (threshold.glsl
// reads it for the cell and its 8 neighbours; computing it there for all nine cost 55 fetches a cell, 3 ms a step at
// 1024^2). Twin: solvers/hillslope.py threshold_excess (upwind_excess).
//! sampler st     x: h (m)
//! sampler par    z: Sc, the threshold slope's tangent
//! image   outP r32f   x: phi = max(1 - Sc / G, 0), G the upwind (Rouy-Tourin) gradient magnitude
//! uniform float uDx
//! uniform int uBound

fn axis_h(p: vec2<i32>, k: i32, n: vec2<i32>, h: f32) -> f32 {
  var q: vec2<i32>;
  if (neighbour(p, k, n, u.uBound, &q)) { return st_at(q).x; }
  return h;
}

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let h = st_at(p).x;
  let gx = max(h - min(axis_h(p, 3, n, h), axis_h(p, 4, n, h)), 0.0);
  let gy = max(h - min(axis_h(p, 1, n, h), axis_h(p, 6, n, h)), 0.0);
  let g = sqrt(gx * gx + gy * gy) / u.uDx;
  let sc = par_at(p).z;
  var phi = 0.0;
  if (g > sc) { phi = 1.0 - sc / g; }
  outP_store(p, vec4<f32>(phi, 0.0, 0.0, 0.0));
}
