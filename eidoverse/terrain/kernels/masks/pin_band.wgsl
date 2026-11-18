// Port of blender/eidoblend/terrain/masks.py at f90c6fc: pin_band, a child level's mask pinned to its parent's in
// its outer band, in place, float32 as numpy has it: d the cell's distance from the nearest edge (cells), w = 1 -
// smoothstep(0, band, d); where w > 0 and the parent holds the cell's centre, the parent's mask read bilinearly
// (rows (a[y0, x0] (1 - tx) + a[y0, x0 + 1] tx) (1 - ty) + (a[y0 + 1, x0] (1 - tx) + a[y0 + 1, x0 + 1] tx) ty) and
// v = cur + w (pv - cur). The tables are numpy's float64 positions in the parent (masks.js pinTable).
//! include masks/lib
//! sampler par           the parent's mask
//! sampler colT          per child column: (x0, tx, inside, 0)
//! sampler rowT          per child row: (y0, ty, inside, 0)
//! image   outV r32f     the child's mask, changed in place
//! uniform vec2 uBand    smoothstep(0, band): (e0, k)

fn pa(i: i32, j: i32) -> f32 { return par_at(vec2<i32>(i, j)).x; }

fn kmain(p: vec2<i32>) {
  let n = outV_size();
  if (!inside(p, n)) { return; }
  let d = min(min(p.y, n.y - 1 - p.y), min(p.x, n.x - 1 - p.x));
  let w = 1.0 - ss(f32(d), u.uBand);
  if (!(w > 0.0)) { return; }
  let cx = colT_at(vec2<i32>(p.x, 0));
  let ry = rowT_at(vec2<i32>(p.y, 0));
  if (cx.z == 0.0 || ry.z == 0.0) { return; }
  let x0 = i32(cx.x);
  let y0 = i32(ry.x);
  let tx = cx.y;
  let ty = ry.y;
  let pv = (pa(x0, y0) * (1.0 - tx) + pa(x0 + 1, y0) * tx) * (1.0 - ty) + (pa(x0, y0 + 1) * (1.0 - tx) + pa(x0 + 1, y0 + 1) * tx) * ty;
  let cur = outV_load(p).x;
  outV_store(p, vec4<f32>(cur + w * (pv - cur), 0.0, 0.0, 0.0));
}
