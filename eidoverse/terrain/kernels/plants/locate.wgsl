// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/locate: plants.py _Points (blender/eidoblend/terrain/build/plants.py at f9fba8c) for a list of points: the
// finest level whose window holds each point (inclusive), and the finest coarse level (the main level in its tile,
// the context levels beyond: what every density reads, _Ground.coarse); the coarsest level considered takes the
// points no window holds.
//! include plants/lib
//! sampler rec r32ui     the points' records (uStride numbers each, the position at words uPos .. uPos + 3)
//! sampler lvt r32f      per level 12 numbers: x0 (integer, fraction), y0, x1, y1 (the window's corners), coarse
//                        (1: a main or context level), cell, n, 0
//! image   outF r32ui    per point: its finest level
//! image   outC r32ui    per point: its finest coarse level
//! uniform int uStride
//! uniform int uPos
//! uniform int uLevels
//! uniform int uCount

fn inside_level(pos: vec4<f32>, k: i32) -> bool {
  let b = 12 * k;
  return coord_sub(pos.xy, vec2<f32>(lvt_b[b], lvt_b[b + 1])) >= 0.0 &&
         coord_sub(pos.xy, vec2<f32>(lvt_b[b + 4], lvt_b[b + 5])) <= 0.0 &&
         coord_sub(pos.zw, vec2<f32>(lvt_b[b + 2], lvt_b[b + 3])) >= 0.0 &&
         coord_sub(pos.zw, vec2<f32>(lvt_b[b + 6], lvt_b[b + 7])) <= 0.0;
}

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = u32(q * u.uStride + u.uPos);
  let pos = vec4<f32>(bitcast<f32>(rec_b[o]), bitcast<f32>(rec_b[o + 1u]), bitcast<f32>(rec_b[o + 2u]),
                      bitcast<f32>(rec_b[o + 3u]));
  var fine = 0;
  for (var k = u.uLevels - 1; k >= 1; k--) {
    if (inside_level(pos, k)) {
      fine = k;
      break;
    }
  }
  var coarse = -1;
  var last = -1;                             // the coarsest coarse level: it takes the rest
  for (var k = u.uLevels - 1; k >= 0; k--) {
    if (lvt_b[12 * k + 8] < 0.5) { continue; }
    last = k;
    if (coarse < 0 && inside_level(pos, k)) { coarse = k; }
  }
  if (coarse < 0) { coarse = max(last, 0); }
  outF_b[q] = u32(fine);
  outC_b[q] = u32(coarse);
}
