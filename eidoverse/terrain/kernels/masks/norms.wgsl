// Port of blender/eidoblend/terrain/masks.py at f90c6fc: norms_from's wetness index and land, per cell:
// a = max(A, cell^2) / cell, twi = ln(a / max(tan slope, 1e-3)) (the slope of the level alone: _slope_tan), and land
// where the water depth (_water_depth: max(water, 0), else max(sea_level - h, 0)) is 0. numpy evaluates twi in
// float64; here float32. Its 5th and 95th percentiles over land are core/prims.js's exact selection (masks.js).
//! sampler A
//! sampler geo           (p, q, g, slope) of the level alone
//! sampler h
//! sampler water         the water field (uWater 1), else any field
//! image   outT r32f     twi
//! image   outL r32f     1 on land (water depth <= 0), 0 under water
//! uniform float uCell
//! uniform float uCell2
//! uniform int uWater    0 none, 1 the water field, 2 the sea level
//! uniform float uSea

fn kmain(p: vec2<i32>) {
  let n = outT_size();
  if (!inside(p, n)) { return; }
  let a = max(A_at(p).x, u.uCell2) / u.uCell;
  outT_store(p, vec4<f32>(log(a / max(geo_at(p).z, 1e-3)), 0.0, 0.0, 0.0));
  var wd = 0.0;
  if (u.uWater == 1) { wd = max(water_at(p).x, 0.0); } else if (u.uWater == 2) { wd = max(u.uSea - h_at(p).x, 0.0); }
  outL_store(p, vec4<f32>(select(0.0, 1.0, wd <= 0.0), 0.0, 0.0, 0.0));
}
