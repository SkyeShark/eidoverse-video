// to_cells: metres to the pipe model's cell units, cell by cell (the port's own kernel, PORT_PLAN.md 3.2: numpy
// code of blender/eidoblend/terrain/solvers/hydraulic.py op_hydraulic and detail.py op_breakup at f90c6fc moved to
// the GPU). It replaces their
//   to_c(a) = ((a - href) / cell).astype(F)
// for a = h + add (op_hydraulic's h0 = h_in + the micro-relief, op_breakup's h1 = h_in + the weathering; numpy adds
// in float64, here ((h - href) + add) / cell keeps the small term's digits in float32), written as T.rgba(b0), the
// pipe model's `base` texture; for bed_m = min(bed, h0): to_c is monotonic, so to_c(min(bed, h0)) is
// min(to_c(bed), to_c(h0)), uHasCap's min(.., cap) with cap the b0 field; and with uPin the pin pack the pipe
// kernels read, T.rgba(pin_w, to_c(pin_h) - b0) (numpy subtracts the two float32 arrays; uPin 2: pin_w 0, the
// coarsest level's). numpy's float64 to_c rounds once; this rounds two or three times (graded against it).
//! sampler h             x: metres (h_in, bed or pin_h)
//! sampler add           x: metres added to h (uHasAdd)
//! sampler cap           x: cell units, the result's upper bound (uHasCap), or b0 (uPin)
//! sampler pw            x: the pin weight (uPin 1)
//! image   outF rgba32f  (c, 0, 0, 0); with uPin (pin_w, c - b0, 0, 0)
//! uniform float uHref
//! uniform float uCell
//! uniform int uHasAdd
//! uniform int uHasCap
//! uniform int uPin

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var a = 0.0;
  if (u.uHasAdd != 0) { a = add_at(p).x; }
  var c = ((h_at(p).x - u.uHref) + a) / u.uCell;
  if (u.uHasCap != 0) { c = min(c, cap_at(p).x); }
  if (u.uPin != 0) {
    var w = 0.0;
    if (u.uPin == 1) { w = pw_at(p).x; }
    outF_store(p, vec4<f32>(w, c - cap_at(p).x, 0.0, 0.0));
    return;
  }
  outF_store(p, vec4<f32>(c, 0.0, 0.0, 0.0));
}
