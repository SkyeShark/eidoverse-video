// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's water and loose cover, float32 as numpy has them:
//   water     _water_depth: max(water, 0) of the water field, else max(sea_level - h, 0) (numpy's float64 difference,
//             rounded once), else none
//   wet_cell  smoothstep(0, 0.3, water) (0 without water); dry = 1 - wet_cell
//   cover     max(deposit, 0) + max(talus, 0) + max(sand, 0), added in that order to zeros, of the fields present;
//             cover_w = smoothstep(cover_m[0], cover_m[1], cover)
//! include masks/lib
//! sampler h
//! sampler water         the water field (uWater 1), else any field
//! sampler dep           deposit (uHas.x), talus (uHas.y), sand (uHas.z), else any field
//! sampler tal
//! sampler sand
//! image   outW r32f     the water depth (uWater 1 or 2; a 1 x 1 dummy otherwise)
//! image   outS rgba32f  (dry, cover_w, wet_cell, 0)
//! uniform int uWater    0 none, 1 the water field, 2 the sea level
//! uniform float uSea    float32(sea_level)
//! uniform ivec3 uHas
//! uniform vec2 uWet     smoothstep(0, 0.3): (e0, k)
//! uniform vec2 uCover   smoothstep(cover_m): (e0, k)

fn kmain(p: vec2<i32>) {
  let n = outS_size();
  if (!inside(p, n)) { return; }
  var wet = 0.0;
  if (u.uWater != 0) {
    var wd = 0.0;
    if (u.uWater == 1) { wd = max(water_at(p).x, 0.0); } else { wd = max(u.uSea - h_at(p).x, 0.0); }
    outW_store(p, vec4<f32>(wd, 0.0, 0.0, 0.0));
    wet = ss(wd, u.uWet);
  }
  var cov = 0.0;
  if (u.uHas.x != 0) { cov = cov + max(dep_at(p).x, 0.0); }
  if (u.uHas.y != 0) { cov = cov + max(tal_at(p).x, 0.0); }
  if (u.uHas.z != 0) { cov = cov + max(sand_at(p).x, 0.0); }
  outS_store(p, vec4<f32>(1.0 - wet, ss(cov, u.uCover), wet, 0.0));
}
