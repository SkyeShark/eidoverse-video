// float_keys: a float field as unsigned sort keys in numpy's order (lib.wgsl fkey), so the integer radix sort
// orders floats exactly as np.argsort(kind='stable') and np.lexsort do. uNegate 1 gives the keys of -v, the
// Blender edition's descending order (np.lexsort((d, -q[d], rcv[d]))).
//! include prims/lib
//! sampler src           the floats
//! image   outK r32ui    their keys
//! uniform int uChannel
//! uniform int uNegate

fn kmain(p: vec2<i32>) {
  let n = src_size();
  if (!inside(p, n)) { return; }
  var v = src_at(p)[u.uChannel];
  if (u.uNegate != 0) { v = -v; }
  outK_store(p, fkey(v));
}
