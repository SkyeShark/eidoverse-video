// sort_count: the counting half of one pass of a stable least-significant-digit radix sort (np.argsort(kind=
// 'stable') and np.lexsort in the Blender edition: glacial streams by receiver, discharge and index; cells by their
// steps to the outlet). One invocation per block of 512 items counts the block's keys by this pass's 8-bit digit.
// The counts are laid out digit by digit (index digit * blocks + block), so one prefix sum over them (scan_up /
// scan_down) gives every (block, digit) the slot where its first item goes: all smaller digits first, then the
// same digit in earlier blocks. Exact.
//! include prims/lib
//! sampler keys r32ui    the keys, a list in row-major order
//! image   outH r32ui    256 * blocks counts: index digit * blocks + block
//! uniform int uCount    the number of items
//! uniform int uShift    the digit's bit position: 0, 8, 16, 24

const BLOCK: i32 = 512;

fn kmain(p: vec2<i32>) {
  let b = line_index(p);
  let nb = (u.uCount + BLOCK - 1) / BLOCK;
  if (b >= nb) { return; }
  var c: array<u32, 256>;
  let end = min((b + 1) * BLOCK, u.uCount);
  for (var i = b * BLOCK; i < end; i++) {
    let d = (keys_b[i] >> u32(u.uShift)) & 255u;
    c[d] += 1u;
  }
  for (var d = 0; d < 256; d++) { outH_b[d * nb + b] = c[d]; }
}
