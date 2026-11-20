// A mask as a float field (0 / 1), for core/prims.js's masked selections and reductions (a mask there is a float field,
// on where > 0), from the expressions of blender/eidoblend/terrain/solvers/volcanic.py at f90c6fc: uMode 0 `lab == L`
// (a playa's cells), 1 `lab != 0`, 2 `f > uT` (caldera_floor > 0.5). The port's own kernel; exact.
//! sampler lab r32ui
//! sampler f
//! image   outF r32f
//! uniform int uMode
//! uniform int uLabel
//! uniform float uT

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  var on = false;
  if (u.uMode == 0) { on = lab_at(p) == u32(u.uLabel); }
  else if (u.uMode == 1) { on = lab_at(p) != 0u; }
  else { on = f_at(p).x > u.uT; }
  outF_store(p, vec4<f32>(select(0.0, 1.0, on), 0.0, 0.0, 0.0));
}
