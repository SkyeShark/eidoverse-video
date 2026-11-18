// Port of blender/eidoblend/terrain/masks.py at f90c6fc: StackSampler (with _catmull_rom and _bilinear) as
// pad_level uses it: the ring of a padded grid takes its parents' terrain where a parent holds the point.
// One dispatch per parent layer, finest first (masks.py sorts its layers by cell): a ring cell that no finer layer
// gave a value (`done`) and that this layer holds (inside its cell centres, per axis: the index tables are -1
// outside) takes the layer's value, and is done. The index and weight tables are numpy's float64 arithmetic
// (masks.js StackSampler.axisTable: fx = (x - x0) / c - 0.5, the Catmull-Rom weights of t = fx - floor(fx), or
// bilinear with the tap clipped to n - 2), rounded once to float32. The sums run over differences from the tap at the
// point's own cell (the weights sum to 1), so float32 keeps the digits of the relief, not of the altitude: the pair
// (tap, offset) is stored as such (uPair 1, the gradient's padding) or as tap - centre + offset (uPair 0).
//! include masks/lib
//! sampler lay           the parent level's height, lny x lnx
//! sampler colI r32i     per padded column: the layer column of the tap at the point's cell, -1 outside
//! sampler colW          per padded column: the weights (Catmull-Rom w0..w3; bilinear 1 - tx, tx)
//! sampler rowI r32i     per padded row: likewise
//! sampler rowW
//! image   outS r32f     the padded grid (uPair 0)
//! image   outP rg32f    the padded grid as (tap, offset) pairs (uPair 1)
//! image   done r32ui    1 where a layer gave the cell its value
//! uniform int uM        the margin
//! uniform ivec2 uRing   (columns, rows): 1 where the margin columns / rows are ring (an axis that wraps is not)
//! uniform ivec2 uN      the window's kept size (nx, ny)
//! uniform int uCubic    1 Catmull-Rom, 0 bilinear
//! uniform int uPair
//! uniform float uCentre subtracted from the value (uPair 0): the blur's centre

fn lt(i: i32, j: i32) -> f32 { return lay_at(vec2<i32>(i, j)).x; }

fn kmain(p: vec2<i32>) {
  let np = done_size();
  if (!inside(p, np)) { return; }
  let m = u.uM;
  let ring_col = u.uRing.x != 0 && (p.x < m || p.x >= m + u.uN.x);
  let ring_row = u.uRing.y != 0 && (p.y < m || p.y >= m + u.uN.y);
  if (!(ring_col || ring_row)) { return; }
  if (done_load(p) != 0u) { return; }
  let ix = colI_at(vec2<i32>(p.x, 0));
  let iy = rowI_at(vec2<i32>(p.y, 0));
  if (ix < 0 || iy < 0) { return; }
  let wx = colW_at(vec2<i32>(p.x, 0));
  let wy = rowW_at(vec2<i32>(p.y, 0));
  let ln = lay_size();
  let r0 = lt(ix, iy);
  var d = 0.0;
  if (u.uCubic != 0) {
    // _catmull_rom: per row, wx[0] a[r, c0] + wx[1] a[r, c1] + wx[2] a[r, c2] + wx[3] a[r, c3]; out += wy[dj] row
    let c0 = clamp(ix - 1, 0, ln.x - 1);
    let c1 = clamp(ix, 0, ln.x - 1);
    let c2 = clamp(ix + 1, 0, ln.x - 1);
    let c3 = clamp(ix + 2, 0, ln.x - 1);
    for (var dj = 0; dj < 4; dj++) {
      let r = clamp(iy + dj - 1, 0, ln.y - 1);
      let row = wx.x * (lt(c0, r) - r0) + wx.y * (lt(c1, r) - r0) + wx.z * (lt(c2, r) - r0) + wx.w * (lt(c3, r) - r0);
      d += wy[dj] * row;
    }
  } else {
    // _bilinear: (v00 (1 - tx) + v10 tx) (1 - ty) + (v01 (1 - tx) + v11 tx) ty, with v00 the tap
    let v10 = lt(ix + 1, iy) - r0;
    let v01 = lt(ix, iy + 1) - r0;
    let v11 = lt(ix + 1, iy + 1) - r0;
    d = (v10 * wx.y) * wy.x + (v01 * wx.x + v11 * wx.y) * wy.y;
  }
  if (u.uPair != 0) {
    outP_store(p, vec4<f32>(r0, d, 0.0, 0.0));
  } else {
    outS_store(p, vec4<f32>((r0 - u.uCentre) + d, 0.0, 0.0, 0.0));
  }
  done_store(p, 1u);
}
