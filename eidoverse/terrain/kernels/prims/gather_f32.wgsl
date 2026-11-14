// gather_f32: out[i] = src[index[i]] for one channel of a float field (numpy's a[idx]). An index past the source
// reads 0. Exact (a copy).
//! include prims/lib
//! sampler src           the values to take from
//! sampler index r32ui   where each output item reads (a row-major cell index)
//! image   outG r32f
//! uniform int uChannel

fn kmain(p: vec2<i32>) {
  let n = outG_size();
  if (!inside(p, n)) { return; }
  let ns = src_size();
  let i = index_b[p.y * n.x + p.x];
  var v = 0.0;
  if (i < u32(ns.x * ns.y)) { v = src_at(vec2<i32>(i32(i) % ns.x, i32(i) / ns.x))[u.uChannel]; }
  outG_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
