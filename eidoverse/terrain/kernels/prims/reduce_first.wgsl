// reduce_first: the first level of a reduction tree (PORT_PLAN.md 3.4): each output cell reduces an 8 x 8 block of
// one channel of a field to its minimum, maximum, sum and counts. What numpy's a.min(), a.max(), a.sum() and
// np.count_nonzero(a) do over a level in the Blender edition's controllers, norms and convergence checks; reduce_next
// folds the blocks until one cell is left, and core/prims.js reads that cell. Min, max and the counts are exact; the
// sum is a float32 sum in a fixed tree (the cells of a block in row-major order, then the blocks), so it is the
// same number on every run.
//! include prims/lib
//! sampler src           the field
//! sampler mask          with uMask 1: only cells whose mask is > 0 are counted (a 1 x 1 dummy otherwise)
//! image   outS rgba32f  x: min, y: max, z: sum; (BIG, -BIG, 0) where no cell is counted
//! image   outN r32ui    the cells counted
//! image   outC r32ui    of them, the cells that are not zero
//! uniform int uChannel  the channel of src
//! uniform int uMask
//! uniform int uCount    only the first uCount cells in row-major order (a list's items); the cell count of a grid

const BLOCK: i32 = 8;

fn kmain(p: vec2<i32>) {
  let no = outS_size();
  if (!inside(p, no)) { return; }
  let n = src_size();
  var lo = BIG;
  var hi = -BIG;
  var sum = 0.0;
  var cnt = 0u;
  var nz = 0u;
  for (var j = 0; j < BLOCK; j++) {
    for (var i = 0; i < BLOCK; i++) {
      let q = p * BLOCK + vec2<i32>(i, j);
      if (!inside(q, n) || q.y * n.x + q.x >= u.uCount) { continue; }
      if (u.uMask != 0 && !(mask_at(q).x > 0.0)) { continue; }
      let v = src_at(q)[u.uChannel];
      lo = min(lo, v);
      hi = max(hi, v);
      sum += v;
      cnt += 1u;
      if (v != 0.0) { nz += 1u; }
    }
  }
  outS_store(p, vec4<f32>(lo, hi, sum, 0.0));
  outN_store(p, cnt);
  outC_store(p, nz);
}
