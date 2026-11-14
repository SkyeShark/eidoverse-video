// compact: stream compaction (np.flatnonzero(flags) in the Blender edition: lake cells, channel subsets, seeds):
// the row-major indices of the flagged items, in order. `pos` is the exclusive prefix sum of the flags counted as
// 0 or 1 (scan_up / scan_down with uBool 1), so item i goes to slot pos[i]: every slot is written by exactly one
// item. Exact.
//! include prims/lib
//! sampler flags r32ui   not zero: keep the item
//! sampler pos r32ui     the number of kept items before each item
//! image   outI r32ui    the kept items' indices, packed at the front (the rest is left as it was)
//! uniform int uCount    the number of items

fn kmain(p: vec2<i32>) {
  let n = flags_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  if (i < u.uCount && flags_b[i] != 0u) { outI_b[pos_b[i]] = u32(i); }
}
