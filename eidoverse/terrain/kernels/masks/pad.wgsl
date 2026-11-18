// Port of blender/eidoblend/terrain/masks.py at f90c6fc: pad_level's margins (_pad_axis, np.pad), before
// StackSampler gives the ring its parents' terrain (masks/outside.wgsl).
// The grid padded by uM cells on every side, columns first, then rows (np.pad along axis 1, then axis 0), each axis
// by its mode:
//   0 'odd'   2 a[edge] - a[edge + t] for t up to k = min(m, n - 1), and the value at k beyond (np.pad 'reflect' with
//             reflect_type 'odd', then 'edge'): a linear extrapolation through the edge
//   1 'nan'   no terrain (NOH, lib.wgsl)
//   2 'edge'  the edge held
//   3 'wrap'  periodic
// A value is made as a pair (tap, offset): 2 a0 - at = a0 + (a0 - at), whose difference float32 holds exactly
// beside a0 (Sterbenz), so a central difference across the edge keeps numpy's float64 digits (masks/gradient.wgsl).
// uPair 1 stores the pair (outP, rg32f); 0 their sum (outS, r32f), which is numpy's float64 value rounded once to
// float32 (the cast before its blur or march) wherever the difference is exact. The other image is a 1 x 1 dummy.
//! include masks/lib
//! sampler src           the grid (its first channel), ny x nx; NOH cells stay NOH
//! image   outS r32f     (ny + 2m) x (nx + 2m): the value (uPair 0)
//! image   outP rg32f    (ny + 2m) x (nx + 2m): (tap, offset) (uPair 1)
//! uniform int uM        the margin, cells
//! uniform ivec2 uMode   per axis (x, y): 0 odd, 1 nan, 2 edge, 3 wrap
//! uniform int uPair

fn tap(i: i32, j: i32) -> f32 { return src_at(vec2<i32>(i, j)).x; }

// row j (inside) padded along x, at column i (any)
fn xpad(j: i32, i: i32, n: vec2<i32>, k: i32) -> vec2<f32> {
  if (i >= 0 && i < n.x) { return vec2<f32>(tap(i, j), 0.0); }
  let mode = u.uMode.x;
  if (mode == 1) { return vec2<f32>(NOH, 0.0); }
  if (mode == 3) { return vec2<f32>(tap(wrap1(i, n.x), j), 0.0); }
  let left = i < 0;
  let e = select(n.x - 1, 0, left);
  let a0 = tap(e, j);
  if (mode == 2 || !has_h(a0)) { return vec2<f32>(a0, 0.0); }
  let t = min(select(i - (n.x - 1), -i, left), k);
  let at = tap(select(e - t, t, left), j);
  if (!has_h(at)) { return vec2<f32>(NOH, 0.0); }
  return vec2<f32>(a0, a0 - at);
}

// the x-padded grid padded along y, at row jj (any) and column i (any)
fn pad2(jj: i32, i: i32, n: vec2<i32>, kx: i32, ky: i32) -> vec2<f32> {
  if (jj >= 0 && jj < n.y) { return xpad(jj, i, n, kx); }
  let mode = u.uMode.y;
  if (mode == 1) { return vec2<f32>(NOH, 0.0); }
  if (mode == 3) { return xpad(wrap1(jj, n.y), i, n, kx); }
  let low = jj < 0;
  let e = select(n.y - 1, 0, low);
  let a0 = xpad(e, i, n, kx);
  if (mode == 2 || !has_h(a0.x)) { return a0; }
  let t = min(select(jj - (n.y - 1), -jj, low), ky);
  let at = xpad(select(e - t, t, low), i, n, kx);
  if (!has_h(at.x)) { return vec2<f32>(NOH, 0.0); }
  // 2 a0 - at as (a0's tap, the rest): a0 + (a0 - at), each side itself a pair
  return vec2<f32>(a0.x, a0.y + ((a0.x - at.x) + (a0.y - at.y)));
}

fn kmain(p: vec2<i32>) {
  let n = src_size();
  let m = u.uM;
  let np = n + vec2<i32>(2 * m, 2 * m);
  if (!inside(p, np)) { return; }
  let v = pad2(p.y - m, p.x - m, n, min(m, n.x - 1), min(m, n.y - 1));
  if (u.uPair != 0) {
    outP_store(p, vec4<f32>(v.x, v.y, 0.0, 0.0));
  } else {
    outS_store(p, vec4<f32>(v.x + v.y, 0.0, 0.0, 0.0));
  }
}
