// label_max: the deepest water of every lake, build/water.py _lake_cells' w[cells].max() (blender/eidoblend/terrain
// at f90c6fc), for all the level's lakes in one pass: an integer atomicMax on the depth's order-preserving key, per
// label. Exact, and the same whatever the order.
//! include prims/lib
//! sampler lab r32ui         the level's wet labels (0 dry)
//! sampler w r32f            the water depth
//! image   outM atomic_u32   a list over the labels: each lake's largest depth key (cleared by the caller)

fn kmain(p: vec2<i32>) {
  let n = lab_size();
  if (!inside(p, n)) { return; }
  let l = lab_b[p.y * n.x + p.x];
  if (l == 0u) { return; }
  atomicMax(&outM_b[l], fkey(w_b[p.y * n.x + p.x]));
}
