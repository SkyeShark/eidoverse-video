// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/gather_rec: records by index (numpy's {k: v[keep]} over a dict of per-candidate arrays, as one array of
// records): out[q] = src[index[q]], uStride numbers a record, for q < uCount. Exact (a copy).
//! include plants/lib
//! sampler src r32ui     the records
//! sampler index r32ui   which record each output takes
//! image   outR r32ui    the records taken, in order
//! uniform int uStride
//! uniform int uCount
//! uniform int uFirst    the first output slot written (a list made of several parts)

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let s = u32(u.uStride);
  let a = index_b[q] * s;
  let b = u32(q + u.uFirst) * s;
  for (var w = 0u; w < s; w++) { outR_b[b + w] = src_b[a + w]; }
}
