// ramp: a smoothstep ramp of a field, cell by cell (the port's own kernel, PORT_PLAN.md 3.2: numpy code of
// blender/eidoblend/terrain/solvers/hydraulic.py and detail.py at f90c6fc moved to the GPU). It replaces
//   hydraulic.rockness     t = clip((s - lo) / max(hi - lo, 1e-6), 0, 1); t * t * (3 - 2 t)
//   op_hydraulic on_slope  flat + (1 - flat) * (the same ramp of the slope between roughness_slope_deg)
//   detail._smoothstep     t = clip((x - e0) / max(e1 - e0, 1e-12), 0, 1); t * t * (3 - 2 t)
// as out = uA + uB * (t * t * (3 - 2 t)), t = clamp((x - uLo) / uDen, 0, 1), uDen the max(...) numpy divides by
// (computed in doubles by the caller). numpy evaluates in float64; this is float32 (graded against it).
//! sampler src           x: the field ramped (a slope in degrees, a resistance)
//! image   outF r32f
//! uniform float uLo
//! uniform float uDen
//! uniform float uA
//! uniform float uB

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let t = clamp((src_at(p).x - u.uLo) / u.uDen, 0.0, 1.0);
  outF_store(p, vec4<f32>(u.uA + u.uB * (t * t * (3.0 - 2.0 * t)), 0.0, 0.0, 0.0));
}
