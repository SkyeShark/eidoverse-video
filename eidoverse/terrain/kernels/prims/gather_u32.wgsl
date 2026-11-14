// gather_u32: out[i] = src[index[i]] over lists in row-major order (numpy's a[idx]: keys taken in a sort's order,
// values through a permutation). An index past the source reads NONE. Exact.
//! include prims/lib
//! sampler src r32ui     the values to take from
//! sampler index r32ui   where each output item reads
//! image   outG r32ui

fn kmain(p: vec2<i32>) {
  let n = outG_size();
  if (!inside(p, n)) { return; }
  let ns = src_size();
  let i = index_b[p.y * n.x + p.x];
  var v = NONE;
  if (i < u32(ns.x * ns.y)) { v = src_b[i]; }
  outG_store(p, v);
}
