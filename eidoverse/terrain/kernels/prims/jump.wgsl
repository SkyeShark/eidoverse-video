// jump: one round of pointer jumping (list ranking): d = d + d[ptr], ptr = ptr[ptr]. After ceil(log2(longest
// path)) rounds ptr is every cell's terminal and d its number of steps to it, as numpy's loops in solvers/hydro.py
// path_steps (nd = d + d[ptr]; nptr = ptr[ptr]) and _terminal_of (t = t[t]) leave them; further rounds change
// nothing (a terminal points to itself with d = 0). Exact.
//! include prims/lib
//! sampler ptr r32ui     the pointer of every cell (a row-major index)
//! sampler dist r32ui    the steps along the pointers so far
//! image   outP r32ui
//! image   outD r32ui

fn kmain(p: vec2<i32>) {
  let n = ptr_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  let q = ptr_b[i];
  outP_store(p, ptr_b[q]);
  outD_store(p, dist_b[i] + dist_b[q]);
}
