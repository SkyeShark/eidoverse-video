// pipe_out: a pipe-model run back to metres, cell by cell (the port's own kernel, PORT_PLAN.md 3.2: numpy code of
// blender/eidoblend/terrain/solvers/hydraulic.py op_hydraulic and detail.py op_breakup at f90c6fc moved to the GPU).
// It replaces
//   op_hydraulic   h_new - h_base = (st.x + st.z) * cell, bed_new - h_base = st.w * cell (the suspended sediment
//                  settles where it is), talus = max(tal, 0) * cell (rock_fail), wet = (wet / max(nwet, 1)) * cell
//   op_breakup     h2 - h_in = (h1 - h_in) + dl * cell, bed2 - h_in = (h1 - h_in) + bed_rel * cell,
//                  talus = max(net, 0) * cell                                       (h1 - h_in: the weathering, add)
// as changes from the surface the op started from, never the large surfaces themselves: the float32 sum of a
// metre-scale height and a millimetre change is what solvers/hydraulic.js finish() forms once, at the end (numpy holds
// h_new in float64, so its h_new - h_base is the change to the last bits). graded against numpy.
//! sampler st            the pipe model's final state (x delta, z sediment, w bed - base; cell units)
//! sampler ta            the thermal accumulator (x: net change by sliding) (uTalus)
//! sampler add           x: metres added to both changes (uHasAdd: op_breakup's weathering)
//! sampler wet           x: the wet field's sum of samples (uWet; 0 when there were none)
//! image   outDH r32f    h_new - h_base, metres
//! image   outDB r32f    bed_new - h_base, metres
//! image   outTal r32f   the talus, metres (uTalus)
//! image   outWet r32f   the wet field, metres (uWet)
//! uniform float uCell
//! uniform float uNWet   max(nwet, 1)
//! uniform int uHasAdd
//! uniform int uTalus
//! uniform int uWet

fn kmain(p: vec2<i32>) {
  let n = outDH_size();
  if (!inside(p, n)) { return; }
  let s = st_at(p);
  var a = 0.0;
  if (u.uHasAdd != 0) { a = add_at(p).x; }
  outDH_store(p, vec4<f32>(a + (s.x + s.z) * u.uCell, 0.0, 0.0, 0.0));
  outDB_store(p, vec4<f32>(a + s.w * u.uCell, 0.0, 0.0, 0.0));
  if (u.uTalus != 0) { outTal_store(p, vec4<f32>(max(ta_at(p).x, 0.0) * u.uCell, 0.0, 0.0, 0.0)); }
  if (u.uWet != 0) { outWet_store(p, vec4<f32>((wet_at(p).x / u.uNWet) * u.uCell, 0.0, 0.0, 0.0)); }
}
