// The port's own kernel (no Blender counterpart): the floor levels of blender/eidoblend/terrain/solvers/fluvial.py
// op_valley_floor at f90c6fc, which numpy makes as
//     lvl = clip(where(cnt > 0, tot / max(cnt, 1), 0), 0, depth_max_m),  cnt, tot = np.bincount(t[band]) (weights hand)
// Here the band cells are sorted by their channel cell (core/prims.js sortPairs: stable, so each channel cell's band
// cells stay in index order, the order np.bincount adds them in), and the first of each run sums its run in that
// order and writes the channel cell's level. Every other cell's level is 0 (the field the caller gives is zeroed).
//! sampler sk r32ui     the sorted keys (channel cells; 0xFFFFFFFF last)
//! sampler sv r32ui     the band cells, in that order
//! sampler hand
//! image   outL r32f    n x n
//! uniform int uCount   the sorted items
//! uniform float uDepthMax

fn kmain(p: vec2<i32>) {
  let m = sk_size();
  if (!inside(p, m)) { return; }
  let i = p.y * m.x + p.x;
  if (i >= u.uCount) { return; }
  let k = sk_b[i];
  if (k == 0xFFFFFFFFu) { return; }
  if (i > 0 && sk_b[i - 1] == k) { return; }
  var s = 0.0;
  var c = 0;
  var j = i;
  loop {
    if (j >= u.uCount || sk_b[j] != k) { break; }
    s = s + hand_b[sv_b[j]];
    c = c + 1;
    j = j + 1;
  }
  let w = outL_size().x;
  let q = vec2<i32>(i32(k % u32(w)), i32(k / u32(w)));
  outL_store(q, vec4<f32>(clamp(s / f32(c), 0.0, u.uDepthMax), 0.0, 0.0, 0.0));
}
