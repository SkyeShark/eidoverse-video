// The port's own kernel (no Blender counterpart): the element-wise sums of blender/eidoblend/terrain/solvers/strata.py
// at f90c6fc that numpy makes in float64 from the GPU's float32 noise fields:
//     mode 0   out = prev + w f              (_noise_m's roughness, rock_mass's scales, plateau_surface's h - drop)
//     mode 1   out = clip(prev, lo, hi)      (rock_mass's clip at +-2.5)
// float32 here, in numpy's order (prev a 1 x 1 stand-in in mode 0 starts the sum at w f, as numpy's 0 + w f).
//! sampler prev     the sum so far
//! sampler f        the field added (mode 0)
//! image   outA r32f
//! uniform int uMode
//! uniform int uFirst    1: no sum yet (prev is a stand-in)
//! uniform float uW
//! uniform vec2 uClip    lo, hi (mode 1)

fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  var a = 0.0;
  if (u.uFirst == 0) { a = prev_at(p).x; }
  if (u.uMode == 0) {
    a = a + u.uW * f_at(p).x;
  } else {
    a = clamp(a, u.uClip.x, u.uClip.y);
  }
  outA_store(p, vec4<f32>(a, 0.0, 0.0, 0.0));
}
