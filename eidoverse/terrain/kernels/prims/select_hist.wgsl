// select_hist: one pass of an exact radix select (PORT_PLAN.md 2.3, 3.4): for each of uRanks order statistics
// (at most 16) sought at once, the histogram of the next 8 bits of the cells' keys (lib.wgsl fkey), over the cells
// whose higher bits already match that statistic's prefix. Four passes (uShift 24, 16, 8, 0), each followed by
// select_pick, leave the exact key of every k-th smallest value; core/prims.js turns keys back into floats and
// interpolates as numpy does. This is what np.percentile and np.median compute in the Blender edition's
// controllers and norms, without sorting. A work group counts its cells in workgroup memory and adds its nonzero
// bins to `hist`: integer atomics, order-independent, so the counts are the same whatever the scheduling.
//! include prims/lib
//! sampler src              the field
//! sampler mask             with uMask 1: only cells whose mask is > 0 (a 1 x 1 dummy otherwise)
//! sampler state r32ui      per statistic r (row r): column 0 the key bits found so far, column 1 its rank among the
//                           cells that match them
//! image   hist atomic_u32  row r: the 256 counts of statistic r (cleared before every pass)
//! uniform int uShift       the bit position of this pass's digit: 24, 16, 8, 0
//! uniform int uRanks       the number of statistics, 1 to 16
//! uniform int uChannel     the channel of src
//! uniform int uMask
//! uniform int uCount       only the first uCount cells in row-major order (a list's items)

var<workgroup> wh: array<atomic<u32>, 4096>;

fn kmain(p: vec2<i32>) {
  let lid = tile_lid(p);
  let me = lid.y * 16 + lid.x;
  for (var b = me; b < 4096; b += 256) { atomicStore(&wh[b], 0u); }
  workgroupBarrier();
  let n = src_size();
  var take = inside(p, n) && p.y * n.x + p.x < u.uCount;
  if (take && u.uMask != 0) { take = mask_at(p).x > 0.0; }
  if (take) {
    let key = fkey(src_at(p)[u.uChannel]);
    let digit = (key >> u32(u.uShift)) & 255u;
    for (var r = 0; r < u.uRanks; r++) {
      if (u.uShift < 24) {
        let high = u32(u.uShift + 8);
        if ((key >> high) != (state_at(vec2<i32>(0, r)) >> high)) { continue; }
      }
      atomicAdd(&wh[u32(r) * 256u + digit], 1u);
    }
  }
  workgroupBarrier();
  for (var b = me; b < u.uRanks * 256; b += 256) {
    let c = atomicLoad(&wh[b]);
    if (c != 0u) { atomicAdd(&hist_b[b], c); }
  }
}
