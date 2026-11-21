// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). crest_mean: the window's crest, the mean of the metre-scale terms a level holds (bake.py
// _crest_metres: np.clip(np.mean([crop(terms[k]) for k in use], axis=0), -1, 1)). numpy's float32 mean over the
// first axis adds the terms in order and divides by their count; so does this, over the first uN of t0..t4.
//! sampler t0
//! sampler t1
//! sampler t2
//! sampler t3
//! sampler t4
//! image   outF r32f
//! uniform int uN          the terms used (1..5)
//! uniform int uM          the margin, cells

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let q = p + vec2<i32>(u.uM);
  var s = t0_at(q).x;
  if (u.uN > 1) { s = s + t1_at(q).x; }
  if (u.uN > 2) { s = s + t2_at(q).x; }
  if (u.uN > 3) { s = s + t3_at(q).x; }
  if (u.uN > 4) { s = s + t4_at(q).x; }
  outF_store(p, vec4<f32>(clamp(s / f32(u.uN), -1.0, 1.0), 0.0, 0.0, 0.0));
}
