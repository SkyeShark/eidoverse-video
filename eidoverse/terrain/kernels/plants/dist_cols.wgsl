// plants/dist_cols: the second pass of plants.py _distance_to (blender/eidoblend/terrain/build/plants.py at f9fba8c):
// the squared distance to the nearest seed is the least over rows j' within R of (the row distance at j')^2 +
// (j - j')^2 (exact integers in float32), then sqrt x cell, capped. With uParent the parent level's distance at the
// cell (sampled by plants/sample) takes over where it is nearer (dist_channel's "a stream outside a window still
// counts").
//! sampler g r32f        per cell: the squared row distance (plants/dist_rows)
//! sampler par r32f      per cell: the parent's distance (unread without uParent)
//! image   outD r32f     metres
//! uniform int   uR
//! uniform float uCell
//! uniform float uCap
//! uniform int   uParent

fn kmain(p: vec2<i32>) {
  let n = g_size();
  if (!inside(p, n)) { return; }
  var best = g_at(p).x;
  let top = min(u.uR, n.y - 1);
  for (var dj = 1; dj <= top; dj++) {
    let d2 = f32(dj * dj);
    if (p.y - dj >= 0) { best = min(best, g_at(vec2<i32>(p.x, p.y - dj)).x + d2); }
    if (p.y + dj < n.y) { best = min(best, g_at(vec2<i32>(p.x, p.y + dj)).x + d2); }
  }
  var d = min(sqrt(best) * u.uCell, u.uCap);
  if (u.uParent != 0) { d = min(d, par_b[p.y * n.x + p.x]); }
  outD_store(p, vec4<f32>(d, 0.0, 0.0, 0.0));
}
