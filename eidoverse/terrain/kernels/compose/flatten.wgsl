// Port of blender/eidoblend/terrain/core/compose.py at f90c6fc: flatten_weight, flatten_mask and flatten_exact over a
// window's cells, and resolve_flat_heights' `inside` set.
//   weight  1 inside the radius, a C1 smoothstep down to 0 at radius + falloff (with no falloff: r <= radius)
//   mask    the erosion stages' rigid-block mask: 1 inside any area's radius plus its falloff (r <= radius + falloff)
//   exact   each area flattened to its height inside its radius, blended with its weight, in order:
//           out = out (1 - w) + z w
// A hard edge (r <= R) decides cells exactly as numpy does: core/compose.js finds, per row, the first and last
// column numpy's float64 np.hypot(x - ax, y - ay) <= R takes (the set is an interval; a table per area, in doubles)
// and the kernel reads it; a float32 distance would move cells lying on the circle. The smooth falloff is float32
// (numpy's float64 rounded once), positions relative to the window's origin.
//! sampler h                exact: the heights (its first channel); anything otherwise
//! sampler areas            two texels per area: (ax - x0, ay - y0, radius, falloff), (height, 0, 0, 0)
//! sampler rows r32i        per area and row j: the hard edge's first and last column, at (2 a, j) and (2 a + 1, j)
//                           (first > last: none)
//! image   outF r32f
//! uniform int uMode        0 weight of area uArea, 1 mask, 2 exact
//! uniform int uAreas
//! uniform int uArea
//! uniform float uCell

fn hard(a: i32, p: vec2<i32>) -> bool {
  return p.x >= rows_at(vec2<i32>(2 * a, p.y)) && p.x <= rows_at(vec2<i32>(2 * a + 1, p.y));
}

fn weight(a: i32, p: vec2<i32>) -> f32 {
  let g = areas_at(vec2<i32>(2 * a, 0));
  if (g.w <= 0.0) { return select(0.0, 1.0, hard(a, p)); }
  let d = (vec2<f32>(p) + 0.5) * u.uCell - g.xy;
  let r = sqrt(d.x * d.x + d.y * d.y);
  let t = clamp((g.z + g.w - r) / g.w, 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  var v = 0.0;
  if (u.uMode == 0) {
    v = weight(u.uArea, p);
  } else if (u.uMode == 1) {
    for (var a = 0; a < u.uAreas; a++) {
      if (hard(a, p)) { v = 1.0; }
    }
  } else {
    v = h_at(p).x;
    for (var a = 0; a < u.uAreas; a++) {
      let w = weight(a, p);
      let z = areas_at(vec2<i32>(2 * a + 1, 0)).x;
      v = v * (1.0 - w) + z * w;
    }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
