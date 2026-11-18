// The port's own kernel (no Blender counterpart): the rill lines of blender/eidoblend/terrain/solvers/hillslope.py
// op_soil_hills at f90c6fc, which numpy makes in float64:
//   uMode 0   d = where(chan, rill clip((A / a_ch)^0.25, 1, gmax), 0)          the depth along the channels
//   uMode 1   cut = min(blurred / peak, gmax rill) (1 - clip(pin_w, 0, 1))     (blurred: d's Gaussian, or d itself
//                                                                             when peak is 1: a narrow rill)
//! sampler bits r32ui    bit 0: chan
//! sampler A
//! sampler src           mode 1: the blurred depth
//! sampler pinw
//! image   outF r32f
//! uniform int uMode
//! uniform float uRill
//! uniform float uACh
//! uniform float uGmax
//! uniform float uPeak

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  if (u.uMode == 0) {
    var d = 0.0;
    if ((bits_at(p) & 1u) != 0u) { d = u.uRill * clamp(pow(A_at(p).x / u.uACh, 0.25), 1.0, u.uGmax); }
    outF_store(p, vec4<f32>(d, 0.0, 0.0, 0.0));
    return;
  }
  let cut = min(src_at(p).x / u.uPeak, u.uGmax * u.uRill) * (1.0 - clamp(pinw_at(p).x, 0.0, 1.0));
  outF_store(p, vec4<f32>(cut, 0.0, 0.0, 0.0));
}
