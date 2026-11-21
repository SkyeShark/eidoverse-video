// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/copy_rec: records [0, uCount) of src into dst from slot uFirst (np.concatenate of a priority group's
// species' candidates, in species order). Exact (a copy).
//! include plants/lib
//! sampler src r32ui
//! image   outR r32ui
//! uniform int uStride
//! uniform int uCount
//! uniform int uFirst

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let s = u32(u.uStride);
  let a = u32(q) * s;
  let b = u32(q + u.uFirst) * s;
  for (var w = 0u; w < s; w++) { outR_b[b + w] = src_b[a + w]; }
}
