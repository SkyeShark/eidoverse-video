// scan_up: the up-sweep of a prefix sum over a list in row-major order (np.cumsum): one invocation per block of
// 256 items adds the block up. core/prims.js repeats it until one block is left, then scan_down writes the prefix
// sums back down. Unsigned integers: exact (modulo 2^32).
//! include prims/lib
//! sampler src r32ui     the items
//! image   outB r32ui    one total per block of 256 (a list: item b at row-major index b)
//! uniform int uCount    the number of items
//! uniform int uBool     1: an item counts 1 when it is not zero (flags), 0: its value

const BLOCK: i32 = 256;

fn kmain(p: vec2<i32>) {
  let b = line_index(p);
  let nb = (u.uCount + BLOCK - 1) / BLOCK;
  if (b >= nb) { return; }
  var sum = 0u;
  let end = min((b + 1) * BLOCK, u.uCount);
  for (var i = b * BLOCK; i < end; i++) {
    var v = src_b[i];
    if (u.uBool != 0 && v != 0u) { v = 1u; }
    sum += v;
  }
  outB_b[b] = sum;
}
