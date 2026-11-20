// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py at f90c6fc, mass_balance and carve_level's
// sea override (PORT_PLAN.md 3.2, the glacial row):
//     z = h + base_elevation_m;  b = clip(beta (z - ela_m), -b_abl_m, b_acc_m).astype(float32)
//     b = where(h <= sea_level, -b_abl_m, b)
// numpy's z - ela_m is h + (base_elevation_m - ela_m) exactly (float32 h, float64 sums); here that offset is rounded
// once (uOff, in doubles) and the rest is float32, in numpy's order.
//! sampler h
//! image   outB r32f
//! uniform float uBeta     beta (m/yr of ice per m of height)
//! uniform float uOff      base_elevation_m - ela_m
//! uniform float uAbl      b_abl_m
//! uniform float uAcc      b_acc_m
//! uniform int uSea        1: cells at or below the sea level ablate at b_abl_m
//! uniform float uSeaLevel the largest float32 at or below the sea level

fn kmain(p: vec2<i32>) {
  if (!inside(p, outB_size())) { return; }
  let hv = h_at(p).x;
  var b = clamp(u.uBeta * (hv + u.uOff), -u.uAbl, u.uAcc);
  if (u.uSea != 0 && hv <= u.uSeaLevel) { b = -u.uAbl; }
  outB_store(p, vec4<f32>(b, 0.0, 0.0, 0.0));
}
