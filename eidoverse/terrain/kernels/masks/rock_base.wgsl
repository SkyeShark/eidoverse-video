// Port of blender/eidoblend/terrain/masks.py at f90c6fc: rock_base, exposed rock (rock > 0.5) with a lower
// neighbour that is not rock (the cliff's foot, where its talus starts), over the eight neighbours of the grid padded
// by one cell ('edge', or 'wrap' along a periodic axis: a neighbour past an open edge is the edge cell itself, never
// lower). Exact: comparisons only. uHeights 0 writes rock_base's 1 / 0; 1 writes rock_shadow's zr, h on a rock foot and
// NOH (numpy's NaN) elsewhere.
//! include masks/lib
//! sampler h
//! sampler rock
//! image   outZ r32f
//! uniform ivec2 uWrap
//! uniform int uHeights

fn nb(q: vec2<i32>, n: vec2<i32>) -> vec2<i32> {
  var r = q;
  if (u.uWrap.x != 0) { r.x = wrap1(r.x, n.x); } else { r.x = clamp(r.x, 0, n.x - 1); }
  if (u.uWrap.y != 0) { r.y = wrap1(r.y, n.y); } else { r.y = clamp(r.y, 0, n.y - 1); }
  return r;
}

fn kmain(p: vec2<i32>) {
  let n = outZ_size();
  if (!inside(p, n)) { return; }
  let hc = h_at(p).x;
  var base = false;
  if (rock_at(p).x > 0.5) {
    for (var dj = -1; dj <= 1; dj++) {
      for (var di = -1; di <= 1; di++) {
        if (dj == 0 && di == 0) { continue; }
        let q = nb(p + vec2<i32>(di, dj), n);
        if (!(rock_at(q).x > 0.5) && h_at(q).x < hc) { base = true; }
      }
    }
  }
  var v = select(0.0, 1.0, base);
  if (u.uHeights != 0) { v = select(NOH, hc, base); }
  outZ_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
