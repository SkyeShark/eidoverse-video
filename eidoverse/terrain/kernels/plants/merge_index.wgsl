// Port of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c, as a GPU kernel (the port's own step: the
// header of build/plant_instances.js says why).
// plants/merge_index: the triangles of a merged foliage part (plants/merge_instances): per instance the part's
// indices offset by the instance's first vertex; a part without an index reads 0 .. uNi - 1 (uIdentity 1).
//! include plants/lib
//! sampler idx r32ui     the part's indices (uNi)
//! image   outI r32ui    per instance its uNi indices
//! uniform int uNi
//! uniform int uNv
//! uniform int uIdentity
//! uniform int uCount    instances x uNi

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let j = q / u.uNi;
  let r = q - j * u.uNi;
  var b = u32(r);
  if (u.uIdentity == 0) { b = idx_b[r]; }
  outI_b[q] = b + u32(j * u.uNv);
}
