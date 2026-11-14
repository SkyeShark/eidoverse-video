// max_pass: one axis of a (2r + 1) maximum filter, edges padded with their own values (PORT_PLAN.md 3.4): the
// Blender edition's solvers/volcanic.py _dilate at f90c6fc (np.pad mode='edge', then the maximum over the square,
// which is the maximum over a row of the maxima over a column). uSign -1 takes the minimum instead (an erosion).
// Maximum and minimum only: exact.
//! include prims/lib
//! sampler src           the field (channel uChannel), or the previous pass's output
//! image   outB r32f
//! uniform int uAxis     0: along a row (x), 1: along a column (y)
//! uniform int uRadius
//! uniform int uSign     1: maximum, -1: minimum
//! uniform int uChannel

fn kmain(p: vec2<i32>) {
  let n = outB_size();
  if (!inside(p, n)) { return; }
  let len = select(n.y, n.x, u.uAxis == 0);
  let i = select(p.y, p.x, u.uAxis == 0);
  var m = src_at(p)[u.uChannel];
  for (var k = -u.uRadius; k <= u.uRadius; k++) {
    var q = p;
    let s = clamp(i + k, 0, len - 1);
    if (u.uAxis == 0) { q.x = s; } else { q.y = s; }
    let v = src_at(q)[u.uChannel];
    if (u.uSign < 0) { m = min(m, v); } else { m = max(m, v); }
  }
  outB_store(p, vec4<f32>(m, 0.0, 0.0, 0.0));
}
