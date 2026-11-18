// Port of blender/eidoblend/terrain/masks.py at f90c6fc: pad_level's margins (_pad_axis, np.pad), before
// StackSampler gives the ring its parents' terrain (masks/outside.wgsl).
// The grid padded by uM cells on every side, columns first, then rows (np.pad along axis 1, then axis 0), each axis
// by its mode:
//   0 'odd'   2 a[edge] - a[edge + t] for t up to k = min(m, n - 1), and the value at k beyond (np.pad 'reflect' with
//             reflect_type 'odd', then 'edge'): a linear extrapolation through the edge
//   1 'nan'   no terrain (NOH, lib.wgsl)
//   2 'edge'  the edge held
//   3 'wrap'  periodic
// Two forms. uPair 0 stores the value (outS, r32f): 2 a0 - at, one rounding of numpy's exact float64 value, which is
// what numpy's cast before its blur or march gives (a corner, the odd extrapolation of one, rounds twice). uPair 1
// stores a pair (tap, offset) (outP, rg32f): (a0, a0 - at), for the central differences of masks/gradient.wgsl, which
// add the taps' difference and the offsets' so that the difference at the edge is 2 (a1 - a0) rounded as numpy's
// is (the two roundings of a0 - a1 and a1 - a0 are each other's negatives). The other image is a 1 x 1 dummy.
//! include masks/lib
//! sampler src           the grid (its first channel), ny x nx; NOH cells stay NOH
//! image   outS r32f     (ny + 2m) x (nx + 2m): the value (uPair 0)
//! image   outP rg32f    (ny + 2m) x (nx + 2m): (tap, offset) (uPair 1)
//! uniform int uM        the margin, cells
//! uniform ivec2 uMode   per axis (x, y): 0 odd, 1 nan, 2 edge, 3 wrap
//! uniform int uPair

fn tap(i: i32, j: i32) -> f32 { return src_at(vec2<i32>(i, j)).x; }

// row j (inside) padded along x, at column i (any): (tap, offset, value)
fn xpad(j: i32, i: i32, n: vec2<i32>, k: i32) -> vec3<f32> {
  if (i >= 0 && i < n.x) {
    let v = tap(i, j);
    return vec3<f32>(v, 0.0, v);
  }
  let mode = u.uMode.x;
  if (mode == 1) { return vec3<f32>(NOH, 0.0, NOH); }
  if (mode == 3) {
    let v = tap(wrap1(i, n.x), j);
    return vec3<f32>(v, 0.0, v);
  }
  let left = i < 0;
  let e = select(n.x - 1, 0, left);
  let a0 = tap(e, j);
  if (mode == 2 || !has_h(a0)) { return vec3<f32>(a0, 0.0, a0); }
  let t = min(select(i - (n.x - 1), -i, left), k);
  let at = tap(select(e - t, t, left), j);
  if (!has_h(at)) { return vec3<f32>(NOH, 0.0, NOH); }
  return vec3<f32>(a0, a0 - at, 2.0 * a0 - at);
}

// the x-padded grid padded along y, at row jj (any) and column i (any): (tap, offset, value)
fn pad2(jj: i32, i: i32, n: vec2<i32>, kx: i32, ky: i32) -> vec3<f32> {
  if (jj >= 0 && jj < n.y) { return xpad(jj, i, n, kx); }
  let mode = u.uMode.y;
  if (mode == 1) { return vec3<f32>(NOH, 0.0, NOH); }
  if (mode == 3) { return xpad(wrap1(jj, n.y), i, n, kx); }
  let low = jj < 0;
  let e = select(n.y - 1, 0, low);
  let a0 = xpad(e, i, n, kx);
  if (mode == 2 || !has_h(a0.x)) { return a0; }
  let t = min(select(jj - (n.y - 1), -jj, low), ky);
  let at = xpad(select(e - t, t, low), i, n, kx);
  if (!has_h(at.x)) { return vec3<f32>(NOH, 0.0, NOH); }
  // 2 a0 - at: as a pair (a0's tap, the rest), and as one value
  return vec3<f32>(a0.x, a0.y + ((a0.x - at.x) + (a0.y - at.y)), 2.0 * a0.z - at.z);
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
    outS_store(p, vec4<f32>(v.z, 0.0, 0.0, 0.0));
  }
}
