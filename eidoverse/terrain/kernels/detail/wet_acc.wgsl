// Port of numpy code of blender/eidoblend/terrain/solvers/hydraulic.py at f90c6fc, as a GPU kernel.
// wet_acc: one sample of the hydraulic op's wet field, added cell by cell (the port's own kernel, PORT_PLAN.md 3.2:
// numpy code of blender/eidoblend/terrain/solvers/hydraulic.py op_hydraulic at f90c6fc moved to the GPU). It replaces
//   wet += run.state()[..., 1] + run.velocity()[..., 2] * dt        (every 100 steps of the last wet_tail of them)
// so the step loop reads nothing back (PORT_PLAN.md 4.5: a solver loop never waits inside a step); numpy adds into
// float64, this into float32 (about six samples; graded against it).
//! sampler st            the pipe model's state: y the water depth (cell units)
//! sampler vel           pipes_water's outV: z the discharge per unit width
//! sampler old           x: the sum so far (uHasOld)
//! image   outW r32f
//! uniform float uDt
//! uniform int uHasOld

fn kmain(p: vec2<i32>) {
  let n = outW_size();
  if (!inside(p, n)) { return; }
  var w = 0.0;
  if (u.uHasOld != 0) { w = old_at(p).x; }
  outW_store(p, vec4<f32>(w + (st_at(p).y + vel_at(p).z * u.uDt), 0.0, 0.0, 0.0));
}
