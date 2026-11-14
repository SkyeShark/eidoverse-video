// int_keys: signed integers as unsigned sort keys in their order (the sign bit flipped), so the radix sort orders
// an int32 field as np.argsort(kind='stable') does. Exact.
//! include prims/lib
//! sampler src r32i
//! image   outK r32ui

fn kmain(p: vec2<i32>) {
  let n = src_size();
  if (!inside(p, n)) { return; }
  outK_store(p, bitcast<u32>(src_at(p)) ^ 0x80000000u);
}
