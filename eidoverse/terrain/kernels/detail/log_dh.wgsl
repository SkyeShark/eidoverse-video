// Port of numpy code of blender/eidoblend/terrain/solvers/hydraulic.py and blender/eidoblend/terrain/solvers/detail.py
// at f90c6fc, as a GPU kernel.
// log_dh: the numbers a detail op's log line reads, cell by cell (the port's own kernel, PORT_PLAN.md 3.2: numpy code
// of blender/eidoblend/terrain/solvers/hydraulic.py op_hydraulic and detail.py op_breakup at f90c6fc moved to the
// GPU). With d = a - b - uSeedK c (op_hydraulic: dh = fields['h'] - h_base; op_breakup: dh = fields['h'] - h_in, and
// |D| with b and c off) it writes (max(-d, 0), max(d, 0), |d|, d), whose percentiles and mean core/prims.js reads:
// np.percentile(np.maximum(-dh, 0), 99), np.percentile(np.maximum(dh, 0), 99), np.abs(dh).mean(),
// np.percentile(dh, 1 | 99). Float32 here against numpy's float64 (a log line).
//! sampler a             x: metres
//! sampler b             x: metres subtracted (uHasB)
//! sampler c             x: metres subtracted, times uSeedK (uSeedK != 0)
//! image   outL rgba32f
//! uniform float uSeedK
//! uniform int uHasB

fn kmain(p: vec2<i32>) {
  let n = outL_size();
  if (!inside(p, n)) { return; }
  var d = a_at(p).x;
  if (u.uHasB != 0) { d = d - b_at(p).x; }
  if (u.uSeedK != 0.0) { d = d - u.uSeedK * c_at(p).x; }
  outL_store(p, vec4<f32>(max(-d, 0.0), max(d, 0.0), abs(d), d));
}
