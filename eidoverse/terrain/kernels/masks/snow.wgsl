// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's snow, float32 as numpy has it:
// alt = float32(h + base) + snow_aspect_m northness + snow_concave_m (concave_20m - convex_20m);
// snow = smoothstep(snowline - band, snowline + band, alt) (1 - smoothstep(snow_slope_deg, slope)) dry.
//! include masks/lib
//! sampler h
//! sampler geo           (p, q, g, slope)
//! sampler north         northness
//! sampler concave       concave_20m
//! sampler convex        convex_20m
//! sampler surf          (dry, cover_w, wet_cell, 0)
//! image   outF r32f
//! uniform float uBase       float32(base_elevation_m)
//! uniform float uAspect     float32(snow_aspect_m)
//! uniform float uConcave    float32(snow_concave_m)
//! uniform vec2 uLine        smoothstep(snowline -/+ band): (e0, k)
//! uniform vec2 uSlope       smoothstep(snow_slope_deg): (e0, k)

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let alt = ((h_at(p).x + u.uBase) + u.uAspect * north_at(p).x) + u.uConcave * (concave_at(p).x - convex_at(p).x);
  let v = (ss(alt, u.uLine) * (1.0 - ss(geo_at(p).w, u.uSlope))) * surf_at(p).x;
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
