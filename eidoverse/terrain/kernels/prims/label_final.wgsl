// label_final: the components numbered 1..n in the order of their roots, 0 for the background: what numpy's
// u, inv = np.unique(roots[mask], return_inverse=True); lab[mask] = inv + 1 gives (core/metrics.py label). With
// uRoots 1 it writes the root flags instead (1 where a cell is its own label), whose exclusive prefix sum `pos` the
// numbering reads. Exact.
//! include prims/lib
//! sampler lab r32ui     every cell's root (its component's smallest index), NONE for the background
//! sampler pos r32ui     the number of roots before each cell (not read with uRoots 1)
//! image   outL r32ui
//! uniform int uRoots

fn kmain(p: vec2<i32>) {
  let n = lab_size();
  if (!inside(p, n)) { return; }
  let l = lab_at(p);
  if (u.uRoots != 0) {
    var f = 0u;
    if (l == u32(p.y * n.x + p.x)) { f = 1u; }
    outL_store(p, f);
    return;
  }
  var v = 0u;
  if (l != NONE) { v = pos_b[l] + 1u; }
  outL_store(p, v);
}
