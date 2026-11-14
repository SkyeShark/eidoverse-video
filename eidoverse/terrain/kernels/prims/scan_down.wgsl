// scan_down: the down-sweep of a prefix sum (scan_up's other half): one invocation per block of 256 items starts
// from the sum of everything before its block and writes the running sum of its items, in order. Exact.
//! include prims/lib
//! sampler src r32ui     the items
//! sampler base r32ui    per block: the sum of all items before it (with uTop 1: not read, the one block starts at 0)
//! image   outP r32ui    per item: the sum of the items before it (uInclusive 1: up to and including it)
//! uniform int uCount    the number of items
//! uniform int uTop
//! uniform int uInclusive
//! uniform int uBool     1: an item counts 1 when it is not zero (flags), 0: its value

const BLOCK: i32 = 256;

fn kmain(p: vec2<i32>) {
  let b = line_index(p);
  let nb = (u.uCount + BLOCK - 1) / BLOCK;
  if (b >= nb) { return; }
  var run = 0u;
  if (u.uTop == 0) { run = base_b[b]; }
  let end = min((b + 1) * BLOCK, u.uCount);
  for (var i = b * BLOCK; i < end; i++) {
    var v = src_b[i];
    if (u.uBool != 0 && v != 0u) { v = 1u; }
    if (u.uInclusive != 0) {
      run += v;
      outP_b[i] = run;
    } else {
      outP_b[i] = run;
      run += v;
    }
  }
}
