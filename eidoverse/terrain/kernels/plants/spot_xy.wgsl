// plants/spot_xy: the spots' ground points as two float32 numbers each (Blender x, y): what build/mesh.js heightField
// and plants/ground_normal read (plants.py _view: z = height_at(x, y), the normal its triangle's).
//! include plants/lib
//! sampler kp r32ui      the spots' records (16 numbers each: the position at 0-3)
//! image   outP r32f     per spot: x, y
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let o = 16u * u32(i);
  outP_b[2 * i] = coord_f32(vec2<f32>(bitcast<f32>(kp_b[o]), bitcast<f32>(kp_b[o + 1u])));
  outP_b[2 * i + 1] = coord_f32(vec2<f32>(bitcast<f32>(kp_b[o + 2u]), bitcast<f32>(kp_b[o + 3u])));
}
