// Port of blender/eidoblend/terrain/core/compose.py at f90c6fc: start_surface's last step, the rough start of an
// erosion run: height_m u / max(peak, 1e-9) ((1 - roughness) + roughness n), with u the uplift shape and n = 0.5 +
// 1.5 fbm (both fields from core/compose.js). numpy evaluates in float64 and rounds once; this is float32, in
// numpy's order.
//! sampler shape            u, the uplift shape (or shape())
//! sampler rough            n, the roughening noise
//! image   outF r32f
//! uniform float uHeight    height_m
//! uniform float uPeak      max(peak, 1e-9)
//! uniform float uRough     roughness

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let s = u.uHeight * shape_at(p).x / u.uPeak;
  outF_store(p, vec4<f32>(s * ((1.0 - u.uRough) + u.uRough * rough_at(p).x), 0.0, 0.0, 0.0));
}
