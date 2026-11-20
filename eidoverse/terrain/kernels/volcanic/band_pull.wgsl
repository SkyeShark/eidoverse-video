// Port of blender/eidoblend/terrain/solvers/volcanic.py _pull_band at f90c6fc: a child level's border band pulled to
// its parent's surface, then the bed kept under it.
//     w = clip(float64(pin_w), 0, 1);  h = (h64 (1 - w) + float64(pin_h) w).astype(float32);  bed = minimum(bed, h)
// numpy's products are exact in float64 (two 24-bit significands) and the sum is rounded once (run.py's _band_pull,
// kernels/hydro/band_pull.wgsl, rounds 1 - w and pin_h w to float32 first: another rounding). Here h (1 - w) is
// fma(-h, w, h), one rounding, and pin_h w is added by a second fma: within one float32 step of numpy's.
//! sampler h
//! sampler bed              uBed 1: the bed; else a 1 x 1 stand-in
//! sampler pinW
//! sampler pinH
//! image   outH r32f
//! image   outB r32f        uBed 1: minimum(bed, h); else a 1 x 1 stand-in
//! uniform int uBed

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  let w = clamp(pinW_at(p).x, 0.0, 1.0);
  let hh = h_at(p).x;
  let hv = fma(pinH_at(p).x, w, fma(-hh, w, hh));
  outH_store(p, vec4<f32>(hv, 0.0, 0.0, 0.0));
  if (u.uBed != 0) { outB_store(p, vec4<f32>(min(bed_at(p).x, hv), 0.0, 0.0, 0.0)); }
}
