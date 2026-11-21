// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/one_minus_exp: 1 - exp(-v) item by item (plants.py _level_cover's shade of the undergrowth, 1 - exp(-the
// trees' exponent)), or uValue everywhere with uFill 1 (a list of one value: a level index, a cap).
//! include plants/lib
//! sampler v r32f
//! image   outV r32f
//! uniform int   uFill
//! uniform float uValue
//! uniform int   uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  if (u.uFill != 0) {
    outV_b[q] = u.uValue;
    return;
  }
  outV_b[q] = 1.0 - exp(-v_b[q]);
}
