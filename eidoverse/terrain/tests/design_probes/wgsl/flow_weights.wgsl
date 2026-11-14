// flow_weights: blender/eidoblend/terrain/kernels/flow_weights.glsl in WGSL (header copied unchanged)
//! sampler st          x: the surface the water follows, h (m)
//! image   outW r32f   x: wsum, the sum of the downhill slopes to the power p
//! uniform float uDx   the cell, metres
//! uniform float uP    the flow exponent p
//! uniform int uBound  BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED (common.glsl)

fn wpow(s: f32, e: f32) -> f32 { if (e == 1.0) { return s; } return pow(s, e); }

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let h = st_at(p).x;
  var ws = 0.0;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (!neighbour(p, k, n, u.uBound, &q)) { continue; }
    let s = (h - st_at(q).x) / (LEN[k] * u.uDx);
    if (s > 0.0) { ws += wpow(s, u.uP); }
  }
  outW_store(p, vec4<f32>(ws, 0.0, 0.0, 0.0));
}
