// Port of numpy code of blender/eidoblend/terrain/surface/atlas.py at d67f19e (resample, _up2_axis) and
// far_colour.py (_to_cells), as a GPU kernel (the port's own, PORT_PLAN.md 3.2). resample: a level's map (four
// channels) on a grid of n texels over the same window:
//   uMode 0  a 2 x 2 box average (n = m / 2): a.reshape(n, 2, n, 2).mean(axis=(1, 3)) in float32
//   uMode 1  x2 bilinear (n = 2 m), cell-centred, edges clamped: _up2_axis along the rows, then along the columns,
//            out[2k] = 0.25 p[k - 1] + 0.75 p[k], out[2k + 1] = 0.75 p[k] + 0.25 p[k + 1]
//! sampler src
//! image   outR rgba32f
//! uniform int uMode

// the x2 row interpolation of column c at output row J (_up2_axis along axis 0)
fn up_rows(c: i32, J: i32, m: vec2<i32>) -> vec4<f32> {
  let k = J / 2;
  if (J % 2 == 0) {
    let a = src_at(vec2<i32>(c, max(k - 1, 0)));
    return 0.25 * a + 0.75 * src_at(vec2<i32>(c, k));
  }
  let b = src_at(vec2<i32>(c, min(k + 1, m.y - 1)));
  return 0.75 * src_at(vec2<i32>(c, k)) + 0.25 * b;
}

fn kmain(p: vec2<i32>) {
  let n = outR_size();
  if (!inside(p, n)) { return; }
  let m = src_size();
  if (u.uMode == 0) {
    let q = 2 * p;
    let s = ((src_at(q) + src_at(q + vec2<i32>(1, 0))) + src_at(q + vec2<i32>(0, 1))) + src_at(q + vec2<i32>(1, 1));
    outR_store(p, s * 0.25);
    return;
  }
  let k = p.x / 2;
  if (p.x % 2 == 0) {
    outR_store(p, 0.25 * up_rows(max(k - 1, 0), p.y, m) + 0.75 * up_rows(k, p.y, m));
  } else {
    outR_store(p, 0.75 * up_rows(k, p.y, m) + 0.25 * up_rows(min(k + 1, m.x - 1), p.y, m));
  }
}
