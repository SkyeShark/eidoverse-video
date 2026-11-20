// The port's own kernel: the per-seed start of blender/eidoblend/terrain/solvers/glacial.py centrelines at f90c6fc,
// one invocation per seed:
//     x = level.x0 + (ii + 0.5) cell,  y = level.y0 + (jj + 0.5) cell   (here from the level's corner: x - x0, y - y0,
//                                                                         the frame seedA keeps; exact in float32)
//     zc = h[idx],  f = min((max(Q, 0) / max(Q_ref, 1e-30))^0.4, f_max)[idx],  q = Q[idx]
// numpy evaluates f in float64; this is float32 (pow: plan 2.3's measured error).
//! sampler idx r32ui        the seed cells (np.flatnonzero)
//! sampler h
//! sampler Q
//! image   outV rgba32f     per seed: x, y (m from the level's corner), zc (m), f
//! image   outQ r32f        per seed: its discharge q
//! uniform float uCell
//! uniform float uQref      Q_ref
//! uniform float uFmax      f_max
//! uniform int uCount       the seeds

fn kmain(p: vec2<i32>) {
  let w = outV_size().x;
  let s = p.y * w + p.x;
  if (p.x >= w || s >= u.uCount) { return; }
  let n = h_size();
  let c = i32(idx_b[s]);
  let pc = vec2<i32>(c % n.x, c / n.x);
  let qv = Q_at(pc).x;
  let f = min(pow(max(qv, 0.0) / max(u.uQref, 1e-30), 0.4), u.uFmax);
  outV_b[s] = vec4<f32>((f32(pc.x) + 0.5) * u.uCell, (f32(pc.y) + 0.5) * u.uCell, h_at(pc).x, f);
  outQ_b[s] = qv;
}
