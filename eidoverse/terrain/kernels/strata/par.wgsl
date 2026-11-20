// The port's own kernel (no Blender counterpart): the forcing pack of blender/eidoblend/terrain/solvers/strata.py
// op_strata_fluvial() at f90c6fc, which numpy makes in float64 from the GPU's float32 noise and fields:
//     K = K (1 + joint_gain J)                                   (joints)
//     n = clip(rock mass, -2.5, 2.5) resist_noise;  n = clip(n + cores, -2.5, 3.5)  (n = cores without the noise)
//     K = K exp(-resist n),   Q = exp(-resist_run n)             (the rock mass; Q = 1 without)
//     K = K (k + (1 - k) t^2 (3 - 2 t)),   t = clip((slope - below) / max(above - below, 1e-6), 0, 1)   (the sod)
//     U = U_m_per_yr;   U = K = 0 on rigid cells (the sea, flatten areas)
//     par = (U, K, Q, G)
// K arrives as fluvial.js erodibility()'s (the roughness noise, the clamp at 0.2 K0, K_factor), as numpy's K does.
// float32 here, in numpy's order.
//! sampler kin      the erodibility so far
//! sampler jw       the joints' weakness (1 x 1 stand-in without)
//! sampler nz       the rock mass's noise, clipped at +-2.5 (1 x 1 stand-in without)
//! sampler co       the strong cores (1 x 1 stand-in without)
//! sampler sl       the slope in degrees (the sod; 1 x 1 stand-in without)
//! sampler rig      1 on rigid cells (1 x 1 stand-in without)
//! image   outP rgba32f
//! image   outK r32f
//! uniform ivec4 uHas    joints, rock-mass noise, cores, sod
//! uniform int uRigid
//! uniform float uGain
//! uniform float uResist
//! uniform float uResistRun
//! uniform float uNoise    resist_noise
//! uniform vec3 uSod       below_deg, above_deg, k
//! uniform float uU
//! uniform float uG

fn kmain(p: vec2<i32>) {
  let nn = outK_size();
  if (!inside(p, nn)) { return; }
  var k = kin_at(p).x;
  if (u.uHas.x == 1) { k = k * (1.0 + u.uGain * jw_at(p).x); }
  var q = 1.0;
  if (u.uHas.y == 1 || u.uHas.z == 1) {
    var n = 0.0;
    if (u.uHas.y == 1) { n = nz_at(p).x * u.uNoise; }
    if (u.uHas.z == 1) {
      if (u.uHas.y == 1) { n = clamp(n + co_at(p).x, -2.5, 3.5); } else { n = co_at(p).x; }
    }
    k = k * exp(-u.uResist * n);
    q = exp(-u.uResistRun * n);
  }
  if (u.uHas.w == 1) {
    let t = clamp((sl_at(p).x - u.uSod.x) / max(u.uSod.y - u.uSod.x, 1e-6), 0.0, 1.0);
    k = k * (u.uSod.z + (1.0 - u.uSod.z) * t * t * (3.0 - 2.0 * t));
  }
  var uu = u.uU;
  if (u.uRigid == 1 && rig_at(p).x > 0.5) {
    uu = 0.0;
    k = 0.0;
  }
  outP_store(p, vec4<f32>(uu, k, q, u.uG));
  outK_store(p, vec4<f32>(k, 0.0, 0.0, 0.0));
}
