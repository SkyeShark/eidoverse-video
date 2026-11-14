// Port of blender/eidoblend/terrain/core/grid.py at f90c6fc: upsample2 and crop_upsample2 (_up1 along rows, then
// along columns), as one gather per child cell.
//
// The x2 cell-centred child of a window of the parent: child cell (I, J) of the window starting at parent cell
// (i0, j0) sits in parent cell (i0 + I / 2, j0 + J / 2), a quarter cell west / south of its centre when I / J is even
// (_up1's `lo`) and a quarter east / north when odd (`hi`). Parent taps past the parent's edge are clamped, as _up1
// pads by repeating the edge, so a window at an edge equals upsample2(a) cropped there (crop_upsample2's 2-cell
// margin never reaches its own padding). The whole field is the window (0, 0) of 2h x 2w cells.
//   Catmull-Rom (h, bed): lo = CR75 . a[k-2 .. k+1], hi = CR25 . a[k-1 .. k+2] (weights at t = 0.75 and 0.25)
//   bilinear (masks, A, qs): lo = 0.25 a[k-1] + 0.75 a[k], hi = 0.75 a[k] + 0.25 a[k+1]
//   nearest: a[k]
// numpy evaluates both passes in float64 and rounds to float32 once; this is float32 throughout, in numpy's order
// (rows first, then columns; each dot product left to right). The weights are dyadic, exact in float32.
//! sampler src              the parent field (its first channel)
//! image   outF r32f        the child window, 2 mj rows x 2 m columns
//! uniform ivec2 uOrigin    (i0, j0): the window's first parent cell
//! uniform int uKind        0 Catmull-Rom, 1 bilinear, 2 nearest

const CR25 = array<f32, 4>(-0.0703125, 0.8671875, 0.2265625, -0.0234375);
const CR75 = array<f32, 4>(-0.0234375, 0.2265625, 0.8671875, -0.0703125);

fn tap(i: i32, j: i32, n: vec2<i32>) -> f32 {
  return src_at(vec2<i32>(clamp(i, 0, n.x - 1), clamp(j, 0, n.y - 1))).x;
}

// one row-interpolated value at parent column i: the vertical pass for child row parity hy around parent row ky
fn rows(i: i32, ky: i32, hy: i32, n: vec2<i32>) -> f32 {
  if (u.uKind == 0) {
    let j0 = ky - 2 + hy;
    var w = CR75;
    if (hy == 1) { w = CR25; }
    return w[0] * tap(i, j0, n) + w[1] * tap(i, j0 + 1, n) + w[2] * tap(i, j0 + 2, n) + w[3] * tap(i, j0 + 3, n);
  }
  if (hy == 0) { return 0.25 * tap(i, ky - 1, n) + 0.75 * tap(i, ky, n); }
  return 0.75 * tap(i, ky, n) + 0.25 * tap(i, ky + 1, n);
}

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let n = src_size();
  let k = u.uOrigin + vec2<i32>(p.x >> 1, p.y >> 1);
  let hx = p.x & 1;
  let hy = p.y & 1;
  var v: f32;
  if (u.uKind == 2) {
    v = tap(k.x, k.y, n);
  } else if (u.uKind == 0) {
    let i0 = k.x - 2 + hx;
    var w = CR75;
    if (hx == 1) { w = CR25; }
    v = w[0] * rows(i0, k.y, hy, n) + w[1] * rows(i0 + 1, k.y, hy, n) + w[2] * rows(i0 + 2, k.y, hy, n) +
        w[3] * rows(i0 + 3, k.y, hy, n);
  } else {
    if (hx == 0) {
      v = 0.25 * rows(k.x - 1, k.y, hy, n) + 0.75 * rows(k.x, k.y, hy, n);
    } else {
      v = 0.75 * rows(k.x, k.y, hy, n) + 0.25 * rows(k.x + 1, k.y, hy, n);
    }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
