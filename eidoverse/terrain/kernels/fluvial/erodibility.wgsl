// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/fluvial.py erodibility() at
// f90c6fc and op_fluvial's K, which numpy makes in float64 from the GPU's float32 noise fields:
//     K = K0 max(1 + roughness / 3 n1, 0.2) max(1 + k_breakup / 3 n2, 0.2) exp(k_contrast n3) faults
//     K = max(K, 0.2 K0)                     (erodibility's return)
//     K = K K_factor                         (an earlier stage's modulation)
//     K = where(rigid, 0, K)                 (the sea and flatten areas)
// each factor only when its noise (uHas) or field (uMore) is given. float32 here, in numpy's order.
//! sampler n1      unit noise at the roughness scales
//! sampler n2      unit noise at the breakup scales the level resolves
//! sampler n3      unit noise at the contrast scales
//! sampler fz      the fault zones' factor (fluvial.py fault_zones)
//! sampler kf      K_factor
//! sampler rig     1 on rigid cells
//! image   outK r32f
//! uniform float uK0
//! uniform float uA3     roughness / 3
//! uniform float uKb3    k_breakup / 3
//! uniform float uKc     k_contrast
//! uniform ivec4 uHas    n1, n2, n3, fz
//! uniform ivec2 uMore   K_factor, rigid

fn kmain(p: vec2<i32>) {
  if (!inside(p, outK_size())) { return; }
  var k = u.uK0;
  if (u.uHas.x == 1) { k = k * max(1.0 + u.uA3 * n1_at(p).x, 0.2); }
  if (u.uHas.y == 1) { k = k * max(1.0 + u.uKb3 * n2_at(p).x, 0.2); }
  if (u.uHas.z == 1) { k = k * exp(u.uKc * n3_at(p).x); }
  if (u.uHas.w == 1) { k = k * fz_at(p).x; }
  k = max(k, 0.2 * u.uK0);
  if (u.uMore.x == 1) { k = k * kf_at(p).x; }
  if (u.uMore.y == 1 && rig_at(p).x > 0.5) { k = 0.0; }
  outK_store(p, vec4<f32>(k, 0.0, 0.0, 0.0));
}
