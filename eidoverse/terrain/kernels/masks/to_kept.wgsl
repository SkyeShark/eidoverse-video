// Port of blender/eidoblend/terrain/masks.py at f90c6fc: to_kept, a field on a window grid (factor f, margin mc) at
// the level's own cells: a crop at f = 1, else bilinear, float32 as numpy computes it (rows first:
// r = b[y0] (1 - ty) + b[y0 + 1] ty, then r[:, x0] (1 - tx) + r[:, x0 + 1] tx). The tables are numpy's float64
// fy = (j + 0.5) / f - 0.5 + mc as (floor, fraction rounded to float32), per kept column and row (masks.js).
//! sampler b             the window-grid field
//! sampler colT          per kept column: (x0, tx); a 1 x 1 dummy at f = 1
//! sampler rowT          per kept row: (y0, ty)
//! image   outF r32f     ny x nx
//! uniform int uF
//! uniform int uMc

fn bv(i: i32, j: i32) -> f32 { return b_at(vec2<i32>(i, j)).x; }

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  if (u.uF == 1) {
    outF_store(p, vec4<f32>(bv(p.x + u.uMc, p.y + u.uMc), 0.0, 0.0, 0.0));
    return;
  }
  let cx = colT_at(vec2<i32>(p.x, 0));
  let ry = rowT_at(vec2<i32>(p.y, 0));
  let x0 = i32(cx.x);
  let y0 = i32(ry.x);
  let tx = cx.y;
  let ty = ry.y;
  let r0 = bv(x0, y0) * (1.0 - ty) + bv(x0, y0 + 1) * ty;
  let r1 = bv(x0 + 1, y0) * (1.0 - ty) + bv(x0 + 1, y0 + 1) * ty;
  outF_store(p, vec4<f32>(r0 * (1.0 - tx) + r1 * tx, 0.0, 0.0, 0.0));
}
