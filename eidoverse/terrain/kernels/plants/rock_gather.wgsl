// Port of numpy code of blender/eidoblend/terrain/build/dressing.py at f9fba8c, as a GPU kernel.
// plants/rock_gather: the kept rocks' numbers in order (build/dressing.js): out[q] = the 20 numbers of rocks[index[q]]
// (plants/rock_place), and the 16 of its matrix apart (what an InstancedMesh reads), and its model as a u32 key.
//! include plants/lib
//! sampler src r32f      20 numbers a candidate
//! sampler index r32ui   which candidate each output takes
//! image   outM r32f     16 numbers a rock: its matrix
//! image   outK r32ui    its model
//! image   outS r32f     its size
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let a = 20u * index_b[q];
  for (var w = 0u; w < 16u; w++) { outM_b[16u * u32(q) + w] = src_b[a + 4u + w]; }
  outK_b[q] = u32(src_b[a + 2u]);
  outS_b[q] = src_b[a + 3u];
}
