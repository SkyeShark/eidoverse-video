// Port of numpy code of blender/eidoblend/terrain/build/palettes.py (value_noise) and
// blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/noise_raster: palettes.value_noise(X, Y, scale, seed, octaves, gain, stretch) at points (the grid points of
// plants/grid_points): fall_streak's world noise (blender/eidoblend/terrain/build/plants.py at f9fba8c), on the
// position's integer part and fraction (plants/lib.wgsl value_noise).
//! include plants/lib
//! sampler pts r32ui     4 numbers a point (plants/grid_points)
//! image   outV r32f     per point
//! uniform ivec2 uW      2^uF / scale (hi, lo as int bits)
//! uniform int   uF
//! uniform float uInv    1 / scale
//! uniform ivec4 uN      seed, octaves, 0, 0
//! uniform vec2  uG      gain, stretch
//! uniform int   uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = 4u * u32(q);
  let pos = vec4<f32>(bitcast<f32>(pts_b[o]), bitcast<f32>(pts_b[o + 1u]), bitcast<f32>(pts_b[o + 2u]),
                      bitcast<f32>(pts_b[o + 3u]));
  let W = vec2<u32>(bitcast<u32>(u.uW.x), bitcast<u32>(u.uW.y));
  outV_b[q] = value_noise(pos, W, u32(u.uF), u.uInv, u.uN.x, u.uN.y, u.uG.x, u.uG.y);
}
