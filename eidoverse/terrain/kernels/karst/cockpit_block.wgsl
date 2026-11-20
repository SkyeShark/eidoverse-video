// Port of blender/eidoblend/terrain/solvers/karst.py _cockpit_floors at f90c6fc, its first lines, as a kernel:
//     hc = h[:m f, :m f].reshape(m, f, m, f).mean(axis=(1, 3))          (float64 there, float32 here)
//     al = allowed[:m f, :m f].reshape(m, f, m, f).all(axis=(1, 3))
// over the m x m coarse cells, f the block (1: a copy).

//! sampler h
//! sampler allowed           > 0.5 where a basin's bottom may lie
//! image   outH r32f
//! image   outA r32f         1 where every cell of the block is allowed, else 0
//! uniform int uF
fn kmain(p: vec2<i32>) {
  let n = outH_size();
  if (!inside(p, n)) { return; }
  let f = u.uF;
  var s = 0.0;
  var all = 1.0;
  for (var dj = 0; dj < f; dj++) {
    for (var di = 0; di < f; di++) {
      let q = p * f + vec2<i32>(di, dj);
      s += h_at(q).x;
      if (!(allowed_at(q).x > 0.5)) { all = 0.0; }
    }
  }
  outH_store(p, vec4<f32>(s / f32(f * f), 0.0, 0.0, 0.0));
  outA_store(p, vec4<f32>(all, 0.0, 0.0, 0.0));
}
