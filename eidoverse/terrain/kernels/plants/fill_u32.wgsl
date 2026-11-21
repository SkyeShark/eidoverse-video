// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/fill_u32: uValue in every item of a u32 list (the level index the points of one level's grid read).
//! include plants/lib
//! image   outV r32ui
//! uniform int uValue
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  outV_b[q] = bitcast<u32>(u.uValue);
}
