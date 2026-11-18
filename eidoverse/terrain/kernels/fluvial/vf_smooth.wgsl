// The port's own kernel (no Blender counterpart): one pass of the along-network smoothing of blender/eidoblend/
// terrain/solvers/fluvial.py op_valley_floor at f90c6fc. numpy's edges are the channel cells whose receiver is a
// channel cell (a -> b); a pass is
//     s = lvl + bincount(a, lvl[b]) + bincount(b, lvl[a]);  lvl = where(chan, s / deg, lvl),  deg = 1 + the edges
// Here, as a gather: a channel cell adds its receiver's level (when that is a channel cell) and then its donors' (the
// neighbours whose receiver it is), the donors in index order as np.bincount adds them, the donors' sum kept apart as
// numpy keeps it.
//! sampler lvl
//! sampler chan
//! sampler rec r32i
//! image   outL r32f

fn kmain(p: vec2<i32>) {
  let n = chan_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  let me = lvl_at(p).x;
  if (!(chan_at(p).x > 0.5)) {
    outL_store(p, vec4<f32>(me, 0.0, 0.0, 0.0));
    return;
  }
  var s = me;
  var deg = 1.0;
  let r = rec_at(p);
  if (r >= 0 && chan_b[r] > 0.5) {
    s = s + lvl_b[r];
    deg = deg + 1.0;
  }
  var d = 0.0;
  for (var k = 0; k < 8; k++) {
    let q = p + OFF[k];
    if (!inside(q, n)) { continue; }
    if (rec_at(q) == i && chan_at(q).x > 0.5) {
      d = d + lvl_at(q).x;
      deg = deg + 1.0;
    }
  }
  outL_store(p, vec4<f32>((s + d) / deg, 0.0, 0.0, 0.0));
}
