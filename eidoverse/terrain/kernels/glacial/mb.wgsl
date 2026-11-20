// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py ice_flux_converge at f90c6fc stacks the mass
// balance and the inflow, np.stack([b, Q_in], -1), into the two-channel texture ice_flux.wgsl reads (mb): this writes
// that rg32f field (Q_in 0 without one).
//! sampler b                the mass balance (m/yr of ice)
//! sampler qin              the ice entering from outside the window (m^3/yr), with uHasIn
//! image   outM rg32f
//! uniform int uHasIn

fn kmain(p: vec2<i32>) {
  if (!inside(p, outM_size())) { return; }
  var q = 0.0;
  if (u.uHasIn != 0) { q = qin_at(p).x; }
  outM_store(p, vec4<f32>(b_at(p).x, q, 0.0, 0.0));
}
