// Port of numpy code of blender/eidoblend/terrain/solvers/hydraulic.py at f90c6fc, as a GPU kernel.
// hydraulic_seed: the hydraulic op's erodibility and its micro-relief seed, cell by cell (the port's own kernel,
// PORT_PLAN.md 3.2: numpy code of blender/eidoblend/terrain/solvers/hydraulic.py op_hydraulic at f90c6fc moved to
// the GPU). It replaces
//   src.z = (erodibility(rk, soil, rock, kfac) * band_fade).astype(F),
//           erodibility = (soil * (1 - t) + rock * kf * t).astype(F)        (kf 1 without a kfac field)
//   bump  = r * (1 - rk) * on_slope * band_fade                             (h0 = h_in + bump, metres)
// band_fade = 1 - clip(pin_w, 0, 1) (1 everywhere on a level with no pins). numpy evaluates in float64 and casts
// where the op casts; this is float32 (graded against it).
//! sampler rk            x: rockness, 0 on soil, 1 on rock (detail/ramp of the smoothed slope)
//! sampler onslope       x: the micro-relief's share by slope (detail/ramp), when uHasR
//! sampler r             x: the micro-relief, metres (core/world_noise.js fbm), when uHasR
//! sampler kf            x: the rock breakup's erodibility factor kfac, when uHasKf
//! sampler pw            x: the pin weight, when uHasPw
//! image   outE r32f     the cohesive ground's erodibility x band_fade (the pipe model's src.z)
//! image   outB r32f     the micro-relief seed, metres (uHasR)
//! uniform float uSoil
//! uniform float uRock
//! uniform int uHasKf
//! uniform int uHasR
//! uniform int uHasPw

fn kmain(p: vec2<i32>) {
  let n = outE_size();
  if (!inside(p, n)) { return; }
  let t = rk_at(p).x;
  var kf = 1.0;
  if (u.uHasKf != 0) { kf = kf_at(p).x; }
  var fade = 1.0;
  if (u.uHasPw != 0) { fade = 1.0 - clamp(pw_at(p).x, 0.0, 1.0); }
  let erod = u.uSoil * (1.0 - t) + u.uRock * kf * t;
  outE_store(p, vec4<f32>(erod * fade, 0.0, 0.0, 0.0));
  if (u.uHasR != 0) {
    outB_store(p, vec4<f32>(r_at(p).x * (1.0 - t) * onslope_at(p).x * fade, 0.0, 0.0, 0.0));
  }
}
