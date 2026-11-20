// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py best_donor at f90c6fc, each cell's largest-area
// donor (the way up a hollow to its divide), as a gather. numpy lists every (donor, receiver) pair by the donor's
// receiver direction k, then by cell; sorts them by A, stably; and assigns out[receiver] = donor in that order, so the
// last write wins: the largest A, and among equal A the largest k. Here a cell reads its neighbours j = 0..7 (the
// donor there has k = 7 - j) and keeps a strictly larger A, so the first j, the largest k, wins a tie: the same donor.
//! sampler recv             per cell: its receiver k, -1 none
//! sampler A                the drainage area (float32, as numpy's float64 copy compares)
//! image   outU r32i        the best donor's row-major index, -1 none

fn kmain(p: vec2<i32>) {
  let n = outU_size();
  if (!inside(p, n)) { return; }
  var best = -1;
  var ba = 0.0;
  for (var j = 0; j < 8; j++) {
    let q = p + OFF[j];
    if (!inside(q, n)) { continue; }
    if (i32(recv_at(q).x) != 7 - j) { continue; }
    let a = A_at(q).x;
    if (best < 0 || a > ba) {
      best = q.y * n.x + q.x;
      ba = a;
    }
  }
  outU_store(p, best);
}
