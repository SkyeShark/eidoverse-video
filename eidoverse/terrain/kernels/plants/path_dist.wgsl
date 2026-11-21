// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/path_dist: plants.py path_distance at points (the cover rasters' grid points: dfocus, the distance the far
// cover reads the instances' kept share at).
//! include plants/lib
//! include plants/focus
//! sampler foc r32f      the focus' points (plants/focus.wgsl)
//! sampler rec r32ui     the points' records (uStride numbers each, the position at words 0-3)
//! image   outD r32f
//! uniform int uStride
//! uniform int uCount
//! uniform int uFocusN

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = u32(q * u.uStride);
  let pos = vec4<f32>(bitcast<f32>(rec_b[o]), bitcast<f32>(rec_b[o + 1u]), bitcast<f32>(rec_b[o + 2u]),
                      bitcast<f32>(rec_b[o + 3u]));
  outD_b[q] = path_dist(pos);
}
