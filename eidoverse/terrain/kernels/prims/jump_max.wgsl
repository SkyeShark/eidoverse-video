// jump_max: one round of pointer jumping that carries a maximum along the path (path maxima): m = max(m, m[ptr]),
// ptr = ptr[ptr]. After ceil(log2(longest path)) rounds m is the largest value on the path from each cell to its
// terminal, the cell and the terminal included. Min and max only: exact. uSign -1 carries the minimum instead.
//! include prims/lib
//! sampler ptr r32ui     the pointer of every cell (a row-major index)
//! sampler val           the path value so far (r32f)
//! image   outP r32ui
//! image   outV r32f
//! uniform int uSign     1: maximum; -1: minimum

fn kmain(p: vec2<i32>) {
  let n = ptr_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  let q = i32(ptr_b[i]);
  let a = val_at(p).x;
  let b = val_at(vec2<i32>(q % n.x, q / n.x)).x;
  var m = max(a, b);
  if (u.uSign < 0) { m = min(a, b); }
  outP_store(p, ptr_b[q]);
  outV_store(p, vec4<f32>(m, 0.0, 0.0, 0.0));
}
