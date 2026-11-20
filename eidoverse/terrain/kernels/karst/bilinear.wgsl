// Port of blender/eidoblend/terrain/solvers/karst.py at f90c6fc: the bilinear step of _Grid.smooth and _bilinear_sep,
// as a kernel. A field on a separable lattice v (rows, columns) read at the output's rows and columns, whose lattice
// cell (i0, j0) and fractions (fx, fy) the CPU computed in doubles per output column and row (ax, ay: (i0, fx) and
// (j0, fy)). numpy's order: the rows first, then the columns,
//     rows = v[j0] (1 - fy) + v[j0 + 1] fy
//     out  = rows[:, i0] (1 - fx) + rows[:, i0 + 1] fx
// in float32 here (float64 there). A table of fractions 0 and cells i + 1 is G.smooth's crop v[1:n + 1, 1:n + 1].
// uMode 0 reads channel uChannel of v; uMode 3 is the river frame's signed distance at the subsamples (_river_frame_
// level: the magnitude and the side interpolated apart, mag x (bilinear(sign) >= 0 ? 1 : -1): interpolated across
// the jump where the exact band meets the far field, the signed value passed through 0).

//! sampler v
//! sampler ax rg32f      per output column: (i0, fx)
//! sampler ay rg32f      per output row: (j0, fy)
//! image   outF r32f
//! uniform int uMode
//! uniform int uChannel
fn val(q: vec2<i32>, m: i32) -> f32 {
  let x = v_at(q)[u.uChannel];
  if (m == 1) { return abs(x); }
  if (m == 2) { return sign(x); }
  return x;
}

fn bil(p: vec2<i32>, m: i32) -> f32 {
  let a = ax_at(vec2<i32>(p.x, 0)).xy;
  let b = ay_at(vec2<i32>(p.y, 0)).xy;
  let i0 = i32(a.x);
  let j0 = i32(b.x);
  let fx = a.y;
  let fy = b.y;
  let r0 = val(vec2<i32>(i0, j0), m) * (1.0 - fy) + val(vec2<i32>(i0, j0 + 1), m) * fy;
  let r1 = val(vec2<i32>(i0 + 1, j0), m) * (1.0 - fy) + val(vec2<i32>(i0 + 1, j0 + 1), m) * fy;
  return r0 * (1.0 - fx) + r1 * fx;
}

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var v = 0.0;
  if (u.uMode == 3) {
    v = bil(p, 1) * select(-1.0, 1.0, bil(p, 2) >= 0.0);
  } else {
    v = bil(p, 0);
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
