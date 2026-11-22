// Port of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c (its flora strokes' sky light as EEVEE gives it
// inside a sward), as a GPU kernel (the port's own step: the header of build/plant_instances.js says why).
// plants/flora_cell: per plant of a flora stroke (plants/flora_place's 5 numbers: x, z in three.js' frame, the stroke
// scale, the base height, the variant) the hashed key of the CELL-metre cell it stands in, for the count of cells the
// stroke occupies (its plants over that area: the density a plant stands in), and its scale squared (the leaf area it
// carries over the prototype's).
//! include plants/lib
//! sampler pl r32f       per plant its 5 numbers
//! image   outK r32ui    per plant its cell's key in a table of uMask + 1
//! image   outS r32f     per plant its scale squared
//! uniform float uInvCell
//! uniform int uMask
//! uniform int uVariant  the stroke's variant (a plant of another variant keys to the table's last slot, scale 0)
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = 5 * q;
  if (i32(round(pl_b[o + 4])) != u.uVariant) {
    outK_b[q] = u32(u.uMask);
    outS_b[q] = 0.0;
    return;
  }
  let cx = i32(floor(pl_b[o] * u.uInvCell));
  let cz = i32(floor(pl_b[o + 1] * u.uInvCell));
  var h = bitcast<u32>(cx) * 0x9E3779B1u ^ (bitcast<u32>(cz) * 0x85EBCA77u);
  h = h ^ (h >> 15u);
  h = h * 0x2C1B3C6Du;
  h = h ^ (h >> 12u);
  outK_b[q] = h & u32(u.uMask - 1);
  let s = pl_b[o + 2];
  outS_b[q] = s * s;
}
