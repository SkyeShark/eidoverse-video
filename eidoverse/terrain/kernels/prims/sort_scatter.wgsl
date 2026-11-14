// sort_scatter: the moving half of one pass of the stable radix sort (sort_count): one invocation per block of 512
// items walks its items in order and puts each at the next free slot of its digit, starting from the block's base
// for that digit. Items with equal digits keep their order (blocks in order, items in order within a block), which
// is what makes the whole sort stable; every slot is written by exactly one item. Exact.
//! include prims/lib
//! sampler keys r32ui    the keys
//! sampler vals r32ui    the values carried with them (with uIota 1: not read, a value is the item's own index)
//! sampler base r32ui    per (digit, block): the first slot, index digit * blocks + block
//! image   outK r32ui    the keys, ordered by this digit
//! image   outV r32ui    their values
//! uniform int uCount
//! uniform int uShift
//! uniform int uIota

const BLOCK: i32 = 512;

fn kmain(p: vec2<i32>) {
  let b = line_index(p);
  let nb = (u.uCount + BLOCK - 1) / BLOCK;
  if (b >= nb) { return; }
  var c: array<u32, 256>;
  let end = min((b + 1) * BLOCK, u.uCount);
  for (var i = b * BLOCK; i < end; i++) {
    let key = keys_b[i];
    let d = (key >> u32(u.uShift)) & 255u;
    let slot = base_b[i32(d) * nb + b] + c[d];
    c[d] += 1u;
    outK_b[slot] = key;
    if (u.uIota != 0) { outV_b[slot] = u32(i); } else { outV_b[slot] = vals_b[i]; }
  }
}
