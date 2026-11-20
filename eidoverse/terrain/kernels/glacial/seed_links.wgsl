// The port's own kernel: the links of blender/eidoblend/terrain/solvers/glacial.py streams at f90c6fc, one invocation
// per seed (the list's item s):
//   uMode 0  rcv:  rk = recv[idx]; rcv_cell = the neighbour rk of the seed's cell (-1 off the grid or rk < 0);
//                  rcv = pos[rcv_cell] where rcv_cell >= 0, else -1 (the receiver's position, -1 when it is no seed)
//   uMode 1  main: each receiver's largest-discharge donor, ties the lower position: numpy sorts the donors by
//                  (receiver, -q, position) (np.lexsort) and keeps each receiver's first. A seed's donors are seeds
//                  among its eight neighbours whose rcv is it, so this gathers them and keeps the same one: the
//                  largest Q[cell], then the lowest position (exact: the float32 discharges compare as numpy's float64)
//   uMode 2  next: cont = rcv >= 0 & main[rcv] == s (numpy: is_main & (rcv >= 0), is_main the main donors), the
//                  stream's next seed cont ? rcv : -1 (the parent the pointer jumping follows); flags: bit 0 cont,
//                  bit 1 head (no donor: main < 0, numpy's ~has_donor); ends: 1 at a stream's last seed (next < 0)
//   uMode 3  sid:  np.unique(parent, return_inverse=True)[1]: the rank of the seed's stream end among every
//                  stream end (rank: the exclusive scan of the ends, in position order, as np.unique sorts them)
//! sampler idx r32ui        the seed cells' row-major indices (np.flatnonzero)
//! sampler recv             per cell: its receiver k (glacial/recv_k.wgsl), -1 none
//! sampler pos r32i         per cell: its seed's position, -1 none (glacial/seed_pos.wgsl)
//! sampler Q                per cell: the ice discharge
//! sampler la r32i          uMode 1 and 2: rcv
//! sampler lb r32i          uMode 2: main
//! sampler ua r32ui         uMode 3: each seed's stream end (core/prims.js pathSteps' terminal)
//! sampler ub r32ui         uMode 3: the ends' ranks (core/prims.js cumsum, exclusive)
//! image   outL r32i        rcv, main, next or sid
//! image   outF r32ui       uMode 2: the flags
//! image   outT r32ui       uMode 2: the ends
//! uniform int uMode
//! uniform int uCount       the seeds

fn kmain(p: vec2<i32>) {
  let w = outL_size().x;
  let s = p.y * w + p.x;
  if (p.x >= w || s >= u.uCount) { return; }
  if (u.uMode == 3) {
    outL_b[s] = i32(ub_b[ua_b[s]]);
    return;
  }
  if (u.uMode == 2) {
    let r = la_b[s];
    let cont = r >= 0 && lb_b[r] == s;
    let head = lb_b[s] < 0;
    var nx = -1;
    if (cont) { nx = r; }
    outL_b[s] = nx;
    outF_b[s] = select(0u, 1u, cont) | select(0u, 2u, head);
    outT_b[s] = select(0u, 1u, nx < 0);
    return;
  }
  let n = recv_size();
  let c = i32(idx_b[s]);
  let pc = vec2<i32>(c % n.x, c / n.x);
  if (u.uMode == 0) {
    let k = i32(recv_at(pc).x);
    var r = -1;
    if (k >= 0) {
      let q = pc + OFF[k];
      if (inside(q, n)) { r = pos_at(q); }
    }
    outL_b[s] = r;
    return;
  }
  var best = -1;
  var bq = 0.0;
  for (var j = 0; j < 8; j++) {
    let q = pc + OFF[j];
    if (!inside(q, n)) { continue; }
    let d = pos_at(q);
    if (d < 0 || la_b[d] != s) { continue; }
    let qq = Q_at(q).x;
    if (best < 0 || qq > bq || (qq == bq && d < best)) {
      best = d;
      bq = qq;
    }
  }
  outL_b[s] = best;
}
