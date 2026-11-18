// Port of numpy code of blender/eidoblend/terrain/solvers/hydraulic.py (finish) at f90c6fc, as a GPU kernel.
// finish_add: what a detail op adds to the level's record fields, cell by cell (the port's own kernel, PORT_PLAN.md
// 3.2: numpy code of blender/eidoblend/terrain/solvers/hydraulic.py finish() at f90c6fc moved to the GPU). It
// replaces, with keep = 1 - clip(pin_w, 0, 1) and dh = (h_new - h_base) * keep:
//   uMode 0  wear    = fields.get('wear', 0) + max(-dh, 0)
//   uMode 1  deposit = fields.get('deposit', 0) + max(dh, 0)
//   uMode 2  talus   = fields.get('talus', 0) + talus * keep
//   uMode 3  wet     = wet * keep
// (x: the change h_new - h_base, the talus or the wet field). numpy in float64; float32 here (graded against it).
//! sampler old           x: the field so far (uHasOld; else 0)
//! sampler x             x: the change, metres (modes 0, 1), the talus (2) or the wet field (3)
//! sampler pw            x: the pin weight (uHasPin)
//! image   outF r32f
//! uniform int uMode
//! uniform int uHasOld
//! uniform int uHasPin

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var keep = 1.0;
  if (u.uHasPin != 0) { keep = 1.0 - clamp(pw_at(p).x, 0.0, 1.0); }
  var o = 0.0;
  if (u.uHasOld != 0) { o = old_at(p).x; }
  let v = x_at(p).x * keep;
  var r: f32;
  if (u.uMode == 0) {
    r = o + max(-v, 0.0);
  } else if (u.uMode == 1) {
    r = o + max(v, 0.0);
  } else if (u.uMode == 2) {
    r = o + v;
  } else {
    r = v;
  }
  outF_store(p, vec4<f32>(r, 0.0, 0.0, 0.0));
}
