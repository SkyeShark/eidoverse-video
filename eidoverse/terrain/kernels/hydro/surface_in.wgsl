// Port of the routing-surface inputs of blender/eidoblend/terrain/run.py at f90c6fc:
//     mode 0 (_surface):           h + water                       (h alone without water)
//     mode 1 (the end stage):      maximum(filled, h + water)      filled: what lakes() returned
// numpy adds the float32 fields in float64, exactly, and routes that float64 surface. On a lake cell h + water is the
// spill level only where the depth's float32 rounding was exact; elsewhere it lies a fraction of a float32 step above
// or below, and those fractions decide numpy's flats and receivers on the lake. So the sum is kept exactly, as a
// float32 pair (hydro/lib: hi its rounding, lo the rest), and the routing works on the pair (solvers/hydro.js).
//! include hydro/lib
//! sampler h
//! sampler water            uWater 1: the lake water; else a 1 x 1 stand-in
//! sampler filled           mode 1: the spill levels lakes() used; else a 1 x 1 stand-in
//! image   outF rg32f       numpy's float64 value as (hi, lo)
//! uniform int uMode
//! uniform int uWater

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  var v = vec2<f32>(h_at(p).x, 0.0);
  if (u.uWater != 0) { v = p_sum(h_at(p).x, water_at(p).x); }
  if (u.uMode == 1) {
    let f = vec2<f32>(filled_at(p).x, 0.0);
    if (p_less(v, f)) { v = f; }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0));
}
