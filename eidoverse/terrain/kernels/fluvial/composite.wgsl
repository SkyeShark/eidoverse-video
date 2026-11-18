// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/fluvial.py composite_uplift() at
// f90c6fc, which numpy makes in float64 from the GPU's float32 shape and noise:
//     b = fraction max(1 + texture n - cut, 0)                         the regional background
//     u = b, or smooth_max(u_shape, b, blend)                          core/compose.py smooth_max
//     u = u max(1 + per_km t, 0.05),  t = ((x - cx) sin az + (y - cy) cos az) / 1000      the tilt
// The tilt's cell offset is (x0 - cx) in doubles (a uniform) plus (i + 0.5) cell in float32.
//! sampler us      the uplift shape (core/compose.js uplift)
//! sampler nr      the regional noise
//! image   outU r32f
//! uniform ivec4 uHas     shape, regional, tilt, 0
//! uniform float uFrac
//! uniform float uTex
//! uniform float uCut
//! uniform float uBlend
//! uniform vec2 uOrigin   tilt: (x0 - cx, y0 - cy)
//! uniform float uCell
//! uniform vec2 uDir      tilt: (sin az, cos az)
//! uniform float uPerKm

fn smooth_min(a: f32, b: f32, k: f32) -> f32 {
  if (k <= 0.0) { return min(a, b); }
  let hh = max(k - abs(a - b), 0.0) / k;
  return min(a, b) - hh * hh * k * 0.25;
}

fn kmain(p: vec2<i32>) {
  if (!inside(p, outU_size())) { return; }
  var v = 0.0;
  if (u.uHas.x == 1) { v = us_at(p).x; }
  if (u.uHas.y == 1) {
    let b = u.uFrac * max(1.0 + u.uTex * nr_at(p).x - u.uCut, 0.0);
    if (u.uHas.x == 1) { v = -smooth_min(-v, -b, u.uBlend); } else { v = b; }
  }
  if (u.uHas.z == 1) {
    let dx = u.uOrigin.x + (f32(p.x) + 0.5) * u.uCell;
    let dy = u.uOrigin.y + (f32(p.y) + 0.5) * u.uCell;
    let t = (dx * u.uDir.x + dy * u.uDir.y) / 1000.0;
    v = v * max(1.0 + u.uPerKm * t, 0.05);
  }
  outU_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
