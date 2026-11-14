// reduce_u32: a reduction tree over an integer field: minimum, maximum and the number of cells that are not zero
// (what a label count, an argmin's first index, np.count_nonzero or a convergence test reads). Each output cell
// folds an 8 x 8 block. The first level binds the field itself to all three samplers with uFirst 1; later levels
// bind the previous level's three outputs. Exact.
//! include prims/lib
//! sampler inLo r32ui    the minimum so far (the field itself at the first level)
//! sampler inHi r32ui    the maximum so far
//! sampler inC r32ui     the count of nonzero cells so far
//! image   outLo r32ui   NONE where no cell is counted
//! image   outHi r32ui   0 where no cell is counted
//! image   outC r32ui
//! uniform int uFirst    1: the samplers are the field; 0: a previous level
//! uniform int uCount    at the first level only the first uCount cells in row-major order (a list's items)

const BLOCK: i32 = 8;

fn kmain(p: vec2<i32>) {
  let no = outLo_size();
  if (!inside(p, no)) { return; }
  let n = inLo_size();
  var lo = NONE;
  var hi = 0u;
  var nz = 0u;
  for (var j = 0; j < BLOCK; j++) {
    for (var i = 0; i < BLOCK; i++) {
      let q = p * BLOCK + vec2<i32>(i, j);
      if (!inside(q, n)) { continue; }
      let c = inC_at(q);
      if (u.uFirst != 0) {
        if (q.y * n.x + q.x >= u.uCount) { continue; }
        if (c != 0u) { nz += 1u; }
      } else {
        nz += c;
      }
      lo = min(lo, inLo_at(q));
      hi = max(hi, inHi_at(q));
    }
  }
  outLo_store(p, lo);
  outHi_store(p, hi);
  outC_store(p, nz);
}
