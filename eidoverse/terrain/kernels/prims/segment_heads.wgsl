// segment_heads: 1 at the first item of every run of equal keys in a sorted list, 0 elsewhere (numpy's
// first[1:] = key[1:] != key[:-1]: the first donor of each receiver, the first edge of each basin pair). A prefix
// sum of the flags numbers the segments. Exact.
//! include prims/lib
//! sampler keys r32ui    sorted keys, a list in row-major order
//! image   outF r32ui
//! uniform int uCount    the number of items

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  if (i >= u.uCount) { return; }
  var f = 1u;
  if (i > 0 && keys_b[i] == keys_b[i - 1]) { f = 0u; }
  outF_store(p, f);
}
