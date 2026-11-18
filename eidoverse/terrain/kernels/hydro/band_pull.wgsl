// Port of blender/eidoblend/terrain/run.py _band_pull at f90c6fc: a legacy op's height pulled to the parent's in
// the border band (what the GPU stages do every step), then the bed kept under it.
//     w = clip(pin_w, 0, 1);  h = (h64 * (1 - w) + pin_h * w).astype(float32);  bed = minimum(bed, h)
// numpy's operands: 1 - w and pin_h * w are float32 arrays (a Python float beside a float32 array stays float32),
// h64 * (1 - w) is exact in float64 (two 24-bit significands), and the float64 sum is rounded to float32 once. So
// the kernel rounds 1 - w and pin_h * w as numpy does and adds the product with fma(), one rounding of numpy's exact
// sum where the backend fuses it.
//! sampler h
//! sampler bed              uBed 1: the bed; else a 1 x 1 stand-in
//! sampler pinW             pin_w
//! sampler pinH             pin_h
//! image   outH r32f
//! image   outB r32f        uBed 1: minimum(bed, h); else a 1 x 1 stand-in
//! uniform int uBed

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let w = clamp(pinW_at(p).x, 0.0, 1.0);
  let hv = fma(h_at(p).x, 1.0 - w, pinH_at(p).x * w);
  outH_store(p, vec4<f32>(hv, 0.0, 0.0, 0.0));
  if (u.uBed != 0) { outB_store(p, vec4<f32>(min(bed_at(p).x, hv), 0.0, 0.0, 0.0)); }
}
