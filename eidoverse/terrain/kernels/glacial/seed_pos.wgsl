// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py streams at f90c6fc,
//     idx = np.flatnonzero(seed_mask);  pos = np.full(n * n, -1);  pos[idx] = np.arange(S)
// uMode 0 over the grid writes -1; uMode 1 over the seed list (core/prims.js nonzero's index list) writes each seed's
// position at its cell. A list's item i is element i of its raw array (core/prims.js lists).
//! sampler idx r32ui        the seed cells' row-major indices, in order (uMode 1)
//! image   outPos r32i      per cell: its seed's position in idx, -1 for none
//! uniform int uMode
//! uniform int uCount       the seeds (uMode 1)

fn kmain(p: vec2<i32>) {
  if (u.uMode == 0) {
    if (inside(p, outPos_size())) { outPos_store(p, -1); }
    return;
  }
  let s = p.y * idx_size().x + p.x;
  if (p.x >= idx_size().x || s >= u.uCount) { return; }
  outPos_b[idx_b[s]] = s;
}
