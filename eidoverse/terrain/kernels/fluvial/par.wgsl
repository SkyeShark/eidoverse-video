// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/fluvial.py op_fluvial's
// par_of(factor) at f90c6fc, T.rgba(U_run factor, K, Sc, G) with U_run = U uplift_scale (rigid cells' U already 0),
// which numpy makes in float64 and rounds to float32: route_incise's forcing pack.
//! sampler U
//! sampler K
//! sampler Sc
//! image   outP rgba32f
//! uniform float uScale   uplift_scale
//! uniform float uFactor  the relief controller's U factor
//! uniform float uG       deposition

fn kmain(p: vec2<i32>) {
  if (!inside(p, outP_size())) { return; }
  outP_store(p, vec4<f32>(U_at(p).x * u.uScale * u.uFactor, K_at(p).x, Sc_at(p).x, u.uG));
}
