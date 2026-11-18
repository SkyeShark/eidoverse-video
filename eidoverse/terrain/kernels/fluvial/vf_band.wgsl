// The port's own kernel (no Blender counterpart): the cross-sections of blender/eidoblend/terrain/solvers/fluvial.py
// op_valley_floor at f90c6fc, which numpy makes in float64:
//     valid = chan[t];  hand = h - h[t];  half = W[t] / 2
//     band  = valid & (|dist - half| <= cell)          the cells half a floor's width from their channel cell
// outK is the channel cell a band cell counts for (its row-major index t), or 0xFFFFFFFF for every other cell: the
// sort key of the floors' sums (numpy's np.bincount over t[band]).
//! sampler t r32ui
//! sampler dist
//! sampler chan
//! sampler h
//! sampler W
//! image   outK r32ui
//! image   outH r32f
//! uniform float uCell

fn kmain(p: vec2<i32>) {
  let n = chan_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  let ti = t_b[i];
  let valid = chan_b[ti] > 0.5;
  let hand = h_b[i] - h_b[ti];
  let half = 0.5 * W_b[ti];
  let band = valid && abs(dist_b[i] - half) <= u.uCell;
  outK_store(p, select(0xFFFFFFFFu, ti, band));
  outH_store(p, vec4<f32>(hand, 0.0, 0.0, 0.0));
}
