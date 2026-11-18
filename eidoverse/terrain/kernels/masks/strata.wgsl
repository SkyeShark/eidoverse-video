// Port of blender/eidoblend/terrain/masks.py at f90c6fc: compute's strata from params.strata (no zs field):
// zs = h + base - tan(dip) (x cos az + y sin az) - warp, x and y the cells' world centres. numpy evaluates it in
// float64; here x cos az and y sin az come per column and row from masks.js (numpy's float64 products, rounded once)
// and the rest is float32.
//! sampler h
//! sampler colT          per column: float32(x cos az)
//! sampler rowT          per row: float32(y sin az)
//! sampler warp          the warp's metres (uWarp 1), else any field
//! image   outF r32f
//! uniform float uBase       float32(base_elevation_m)
//! uniform float uTan        float32(tan(dip))
//! uniform int uWarp
//! uniform float uWarpNum    a warp that is one number

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var zs = (h_at(p).x + u.uBase) - u.uTan * (colT_at(vec2<i32>(p.x, 0)).x + rowT_at(vec2<i32>(p.y, 0)).x);
  if (u.uWarp != 0) { zs = zs - warp_at(p).x; } else { zs = zs - u.uWarpNum; }
  outF_store(p, vec4<f32>(zs, 0.0, 0.0, 0.0));
}
