// Port of the routing-surface inputs of blender/eidoblend/terrain/run.py at f90c6fc:
//     mode 0 (_surface):           h + water                       (float64 in numpy: h alone without water)
//     mode 1 (the end stage):      maximum(filled, h + water)      filled: what lakes() returned
// numpy's float64 sum of two float32 values is exact, and float32's addition is correctly rounded, so the result is
// numpy's value rounded once; rounding is monotone, so the maximum and the fill that follows commute with it. Where
// numpy's sum is not a float32 value (a lake whose bed lies below half its surface's height), the port's routing
// surface starts from that rounding (solvers/hydro.js names it).
//! sampler h
//! sampler water            uWater 1: the lake water; else a 1 x 1 stand-in
//! sampler filled           mode 1: the spill levels lakes() used; else a 1 x 1 stand-in
//! image   outF r32f
//! uniform int uMode
//! uniform int uWater

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  var v = h_at(p).x;
  if (u.uWater != 0) { v = v + water_at(p).x; }
  if (u.uMode == 1) { v = max(filled_at(p).x, v); }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
