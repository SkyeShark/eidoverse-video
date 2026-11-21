// Port of blender/eidoblend/terrain/surface/kernels/streak.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged. The changes are WGSL's: texelFetch is exT_at(q), imageStore is outS_store, textureSize is exT_size(),
// the uniforms are u.<name>.
/* streak: wind exposure trailed downwind (SURFACING_DESIGN.md 2.3, step 11). Each cell takes the exposure of the
   ground upwind of it along the wind's line, weighted exp(-distance / uLength): a convex, wind-facing spot leaves a
   tail uLength cells long and one cell wide (10 : 1 by default). The line is sampled every cell, bilinearly; indices
   clamp at the padded grid's edge. Twin: surface/twins.py streak. */
//! sampler exT             x: wind exposure on convex ground (crest's outX)
//! image   outS r32f
//! uniform vec2 uWind      the unit vector the wind blows toward
//! uniform float uLength   the tail's length, cells

fn exposure(pos: vec2<f32>, n: vec2<i32>) -> f32 {
  let fl = floor(pos);
  let t = pos - fl;
  let i0 = clamp(vec2<i32>(fl), vec2<i32>(0), n - 1);
  let i1 = clamp(vec2<i32>(fl) + 1, vec2<i32>(0), n - 1);
  let v00 = exT_at(i0).x;
  let v10 = exT_at(vec2<i32>(i1.x, i0.y)).x;
  let v01 = exT_at(vec2<i32>(i0.x, i1.y)).x;
  let v11 = exT_at(i1).x;
  return mix(mix(v00, v10, t.x), mix(v01, v11, t.x), t.y);
}

fn kmain(p: vec2<i32>) {
  let n = exT_size();
  if (!inside(p, n)) { return; }
  let R = min(i32(ceil(3.0 * u.uLength)), 96);
  var acc = 0.0;
  var ws = 0.0;
  for (var t = 0; t <= R; t++) {
    let w = exp(-f32(t) / u.uLength);
    acc += w * exposure(vec2<f32>(p) - f32(t) * u.uWind, n);
    ws += w;
  }
  outS_store(p, vec4<f32>(acc / ws, 0.0, 0.0, 0.0));
}
