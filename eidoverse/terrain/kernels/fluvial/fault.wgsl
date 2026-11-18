// The port's own kernel (no Blender counterpart): one fault zone of blender/eidoblend/terrain/solvers/fluvial.py
// fault_zones() at f90c6fc, which numpy makes in float64 at the level's cell centres:
//     d   = (x - cx) ay - (y - cy) ax - offset_m (+ wander_m n)      the distance across the trace, metres
//     g   = exp(-d^2 / 2 width^2) (x clip((1 - t) / 0.1, 0, 1), t = |along| / (length / 2), when length_m is given)
//     out = prev (1 + (k_factor - 1) g)
// The cell's offset from the fault's centre is (x0 - cx) in doubles (a uniform) plus (i + 0.5) cell in float32, as
// core/compose.js places its shapes.
//! sampler prev    the product of the zones so far (ones for the first)
//! sampler wan     the trace's wander noise (fbm, amp 3)
//! image   outF r32f
//! uniform vec2 uOrigin   (x0 - cx, y0 - cy)
//! uniform float uCell
//! uniform vec2 uAxis     (ax, ay) = (sin, cos) of the strike's azimuth
//! uniform float uOff
//! uniform float uWan     wander_m (0: none)
//! uniform float uWidth   max(width_m, 1e-6)
//! uniform float uHalfLen length_m / 2 (0: no length)
//! uniform float uK1      k_factor - 1

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let dx = u.uOrigin.x + (f32(p.x) + 0.5) * u.uCell;
  let dy = u.uOrigin.y + (f32(p.y) + 0.5) * u.uCell;
  var d = dx * u.uAxis.y - dy * u.uAxis.x - u.uOff;
  if (u.uWan > 0.0) { d = d + u.uWan * wan_at(p).x; }
  let r = d / u.uWidth;
  var g = exp(-0.5 * r * r);
  if (u.uHalfLen > 0.0) {
    let t = abs(dx * u.uAxis.x + dy * u.uAxis.y) / u.uHalfLen;
    g = g * clamp((1.0 - t) / 0.1, 0.0, 1.0);
  }
  outF_store(p, vec4<f32>(prev_at(p).x * (1.0 + u.uK1 * g), 0.0, 0.0, 0.0));
}
