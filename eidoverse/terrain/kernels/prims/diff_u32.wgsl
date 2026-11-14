// diff_u32: 1 where two integer fields differ, 0 where they agree: with reduce_u32, the "did anything change"
// test of an iteration (numpy's np.array_equal in the Blender edition's loops). Exact.
//! include prims/lib
//! sampler a r32ui
//! sampler b r32ui
//! image   outF r32ui

fn kmain(p: vec2<i32>) {
  let n = a_size();
  if (!inside(p, n)) { return; }
  var f = 0u;
  if (a_at(p) != b_at(p)) { f = 1u; }
  outF_store(p, f);
}
