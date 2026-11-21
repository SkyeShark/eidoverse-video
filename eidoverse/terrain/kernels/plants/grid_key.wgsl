// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/grid_key: each point's bucket in the hashed grid (plants/grid.wgsl), for a stable sort by bucket
// (core/prims.js sortPairs) and the buckets' starts (bincount, an exclusive scan): what the neighbour searches walk.
//! include plants/lib
//! include plants/grid
//! sampler rec r32ui     the points' records (uStride numbers each, the position at words uPos .. uPos + 3)
//! image   outK r32ui    per point: its bucket
//! uniform vec4  uGO
//! uniform ivec2 uGW
//! uniform float uGInv
//! uniform int   uGMask
//! uniform int   uStride
//! uniform int   uPos
//! uniform int   uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = u32(q * u.uStride + u.uPos);
  let pos = vec4<f32>(bitcast<f32>(rec_b[o]), bitcast<f32>(rec_b[o + 1u]), bitcast<f32>(rec_b[o + 2u]),
                      bitcast<f32>(rec_b[o + 3u]));
  outK_b[q] = gkey(gcell(pos));
}
