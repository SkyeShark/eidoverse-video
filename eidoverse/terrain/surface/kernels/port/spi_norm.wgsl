// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). spi_norm: the main tile's stream power, the values spi's 5th-95th percentile norms are taken over
// (bake.py _Baker._spi_norms), cell by cell:
//     outV = log10(max(A, cell^2) / cell x max(g, 1e-3))        g: the slope of the height blurred at 20 m
//     outL = 1 on land (masks.py _water_depth <= 0: the water field where the level has one, else the sea level over
//            the ground, else everywhere)
// numpy evaluates it in float64 from float32 fields; this is float32 (graded against Blender's bake).
//! sampler A
//! sampler geo                 z: the slope's tangent (masks.js gradient)
//! sampler water
//! sampler h
//! image   outV r32f
//! image   outL r32f
//! uniform float uCell
//! uniform float uCell2
//! uniform int uWater          0 none, 1 the water field, 2 the sea level
//! uniform float uSea

fn kmain(p: vec2<i32>) {
  let n = outV_size();
  if (!inside(p, n)) { return; }
  let a = max(A_at(p).x, u.uCell2) / u.uCell;
  let g = max(geo_at(p).z, 1e-3);
  var wd = 0.0;
  if (u.uWater == 1) { wd = max(water_at(p).x, 0.0); }
  if (u.uWater == 2) { wd = max(u.uSea - h_at(p).x, 0.0); }
  outV_store(p, vec4<f32>(log2(a * g) * 0.30102999566398120, 0.0, 0.0, 0.0));
  outL_store(p, vec4<f32>(select(0.0, 1.0, wd <= 0.0), 0.0, 0.0, 0.0));
}
