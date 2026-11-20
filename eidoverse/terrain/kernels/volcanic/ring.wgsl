// Port of blender/eidoblend/terrain/solvers/volcanic.py op_caldera_collapse's rim ring at f90c6fc: 1 on the cells
// within uW of the rim circle (np.abs(r - rim_radius_m) < max(cell, 1e-6)), 0 elsewhere; core/prims.js stats takes
// the mean of h over it. The port's own kernel (float32 radius against numpy's float64: a cell exactly uW off the
// circle can go either way).
//! image   outF r32f
//! uniform vec2 uOrg     the level's origin minus the centre, metres
//! uniform float uStep
//! uniform float uR      the rim's radius
//! uniform float uW

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let d = u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep;
  let r = length(d);
  outF_store(p, vec4<f32>(select(0.0, 1.0, abs(r - u.uR) < u.uW), 0.0, 0.0, 0.0));
}
