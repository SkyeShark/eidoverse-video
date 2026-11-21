// plants/rock_column: one number of each candidate's 20 (plants/rock_place) as a list: the kept flag as a u32 (uMode
// 0), or the number at uCol as a float (uMode 1).
//! include plants/lib
//! sampler src r32f      20 numbers a candidate
//! image   outU r32ui
//! image   outF r32f
//! uniform int uCol
//! uniform int uMode
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let v = src_b[20 * q + u.uCol];
  if (u.uMode == 0) { outU_b[q] = select(0u, 1u, v > 0.5); } else { outF_b[q] = v; }
}
