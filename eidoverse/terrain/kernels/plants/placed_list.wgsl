// plants/placed_list: plants.py _plan's lists of the plants placed so far (blender/eidoblend/terrain/build/plants.py
// at f9fba8c): per placed plant its position and a radius, factor x size / size_m[1] (feet: foot_m x scale; the
// shade's casters: crown_m x scale), written from slot uFirst (the list grows group by group). Also its flags for the
// stats (1: within the species' radius, 8: home).
//! include plants/lib
//! sampler pl r32ui      the placed plants' records (16 numbers each)
//! image   outL r32ui    8 numbers a plant: xi, xf, yi, yf, radius, 0, 0, 0
//! image   outF r32ui    per plant: its flags (unwritten with uFlags 0)
//! uniform vec4 uS       factor (foot_m or crown_m), size_m[1], the species' radius, 0
//! uniform int  uFirst
//! uniform int  uFlags
//! uniform int  uCount

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let o = 16u * u32(i);
  let size = bitcast<f32>(pl_b[o + 7u]);
  if (u.uFlags != 0) {
    var f = 0u;
    if (bitcast<f32>(pl_b[o + 9u]) <= u.uS.z) { f |= 1u; }
    if (pl_b[o + 15u] != 0u) { f |= 8u; }
    outF_b[i] = f;
    return;
  }
  let d = 8u * u32(i + u.uFirst);
  for (var w = 0u; w < 4u; w++) { outL_b[d + w] = pl_b[o + w]; }
  outL_b[d + 4u] = bitcast<u32>(u.uS.x * size / u.uS.y);
  outL_b[d + 5u] = 0u;
  outL_b[d + 6u] = 0u;
  outL_b[d + 7u] = 0u;
}
