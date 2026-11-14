// Port of blender/eidoblend/terrain/core/grid.py at f90c6fc: _box_axis, the exact area-weighted average along one
// axis (resample_box runs it on rows, then on columns). Output pixel k covers source cells [k r, (k + 1) r): with
// F(e) = (sum of the cells below floor(e)) + frac(e) a[floor(e)], out_k = (F(e_k+1) - F(e_k)) / r.
//
// numpy forms F from running sums (np.cumsum in float64) and differences them; this gathers the same quantity
// directly, sum a[k0 .. k1 - 1] + f1 a[k1] - f0 a[k0], in float32, since a difference of float32 running sums would
// lose the small differences of large sums. The edges (floor index and fraction) are computed in JavaScript doubles
// as numpy computes them (np.minimum(k r, n)) and read from `edges`, so no float32 product k r enters.
//! sampler src              the field (its first channel)
//! sampler edges            rg32f, n_out + 1 entries in a row: (floor index, fraction) of each pixel edge
//! image   outF r32f        the field averaged along the axis
//! uniform int uAxis        0 along rows (numpy's axis 0, j), 1 along columns (axis 1, i)
//! uniform float uR         dst_cell / src_cell

fn at(t: i32, other: i32) -> f32 {
  if (u.uAxis == 0) { return src_at(vec2<i32>(other, t)).x; }
  return src_at(vec2<i32>(t, other)).x;
}

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  var k = p.y;
  var other = p.x;
  if (u.uAxis == 1) { k = p.x; other = p.y; }
  let e0 = edges_at(vec2<i32>(k, 0)).xy;
  let e1 = edges_at(vec2<i32>(k + 1, 0)).xy;
  let k0 = i32(e0.x);
  let k1 = i32(e1.x);
  var s = 0.0;
  for (var t = k0; t < k1; t++) { s += at(t, other); }
  s = s + e1.y * at(k1, other) - e0.y * at(k0, other);
  outF_store(p, vec4<f32>(s / u.uR, 0.0, 0.0, 0.0));
}
