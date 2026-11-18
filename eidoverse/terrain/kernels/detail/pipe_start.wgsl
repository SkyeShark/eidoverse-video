// Port of numpy code of blender/eidoblend/terrain/solvers/hydraulic.py and blender/eidoblend/terrain/solvers/detail.py
// at f90c6fc, as a GPU kernel.
// pipe_start: the pipe model's start state and the thermal pass's parameters, cell by cell (the port's own kernel,
// PORT_PLAN.md 3.2: numpy code of blender/eidoblend/terrain/solvers/hydraulic.py and detail.py at f90c6fc moved to
// the GPU). It replaces
//   initial_state(b0, bed): T.rgba(0, d, s, min((bed - b0).astype(F), 0))   with d = s = 0, as both ops start it
//   T.rgba(sc, full(rep), full(floor))                                       the thermal pass's `par`
// for op_hydraulic (sc the Sc field with rock_fail, else BIG_TAN; floor -1e6) and detail.relax (sc the breakup's
// threshold, floor -max_fail_m / cell). The `base` texture, T.rgba(b0), is detail/to_cells' output itself. bed - b0
// of two float32 values, rounded once, is numpy's float64 difference cast to float32, to the bit.
//! sampler b0            x: the start surface, cell units
//! sampler bed           x: the cohesive top, cell units (uHasBed; else bed = b0)
//! sampler sc            x: the cohesive ground's threshold, a tangent (uHasSc; else uSc everywhere)
//! image   outState rgba32f
//! image   outPar rgba32f
//! uniform float uSc
//! uniform float uRep
//! uniform float uFloor
//! uniform int uHasBed
//! uniform int uHasSc

fn kmain(p: vec2<i32>) {
  let n = outState_size();
  if (!inside(p, n)) { return; }
  var rel = 0.0;
  if (u.uHasBed != 0) { rel = min(bed_at(p).x - b0_at(p).x, 0.0); }
  var s = u.uSc;
  if (u.uHasSc != 0) { s = sc_at(p).x; }
  outState_store(p, vec4<f32>(0.0, 0.0, 0.0, rel));
  outPar_store(p, vec4<f32>(s, u.uRep, u.uFloor, 0.0));
}
