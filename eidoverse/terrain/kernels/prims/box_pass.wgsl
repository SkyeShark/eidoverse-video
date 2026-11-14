// box_pass: one axis of a box blur, the mean of the 2r + 1 cells around each cell (PORT_PLAN.md 3.4). The Blender
// edition at f90c6fc does it with running sums in float64: solvers/hydro.py box_blur (x then y, `passes` times; an
// axis that wraps is circular, the others hold their edge cells) and solvers/hydraulic.py _box (y then x, edges
// held). Here the window is summed directly, as differences from the cell's own value so float32 keeps the digits
// of the relief; its oracles are those functions.
//! include prims/lib
//! sampler src           the field (channel uChannel), or the previous pass's output
//! image   outB r32f
//! uniform int uAxis     0: along a row (x), 1: along a column (y)
//! uniform int uRadius   r
//! uniform int uWrap     1: the axis is circular; 0: past the edge the edge cell is held
//! uniform int uChannel

fn kmain(p: vec2<i32>) {
  let n = outB_size();
  if (!inside(p, n)) { return; }
  let len = select(n.y, n.x, u.uAxis == 0);
  let i = select(p.y, p.x, u.uAxis == 0);
  let c = src_at(p)[u.uChannel];
  let lift = (u.uRadius / len + 1) * len;              // whole turns that keep i + k >= 0: no % of a negative number
  var acc = 0.0;
  for (var k = -u.uRadius; k <= u.uRadius; k++) {
    var s = i + k;
    if (u.uWrap != 0) {
      s = (s + lift) % len;
    } else {
      s = clamp(s, 0, len - 1);
    }
    var q = p;
    if (u.uAxis == 0) { q.x = s; } else { q.y = s; }
    acc += src_at(q)[u.uChannel] - c;
  }
  outB_store(p, vec4<f32>(c + acc / f32(2 * u.uRadius + 1), 0.0, 0.0, 0.0));
}
