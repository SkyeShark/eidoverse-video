// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/sample: plants.py _Points.sample (blender/eidoblend/terrain/build/plants.py at f9fba8c) for one map: the
// bilinear value at each point of the raster of the level it is located on (a level without the map hands its points
// to the next coarser level that has it, else the next finer: the table's fallback), the taps on texel centres
// clamped to the outermost ones (core/grid.sample_bilinear's arithmetic). The texel coordinate is made from the
// position's integer part and fraction with a fixed-point reciprocal (plants/lib.wgsl coord_div), so a 2048-texel
// level keeps its weights to 1e-7 where one float32 division would lose 2e-4.
//! include plants/lib
//! sampler rec r32ui     the points' records (uStride numbers each, the position at words uPos .. uPos + 3)
//! sampler lvl r32ui     per point: the level it is located on (plants/locate)
//! sampler stack r32f    the map's rasters of the levels that have it, one after another (row 0 south)
//! sampler tab r32ui     per level 12 numbers: the raster's first element in stack, its size n (0: none), the level
//                        read in its place, the reciprocal 2^40 / texel (hi, lo), 1 / texel (float bits), the window's
//                        x0 and y0 (integer part, fraction: float bits), 0, 0
//! image   outV r32f     per point: the value
//! uniform int uStride
//! uniform int uPos
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = u32(q * u.uStride + u.uPos);
  let pos = vec4<f32>(bitcast<f32>(rec_b[o]), bitcast<f32>(rec_b[o + 1u]), bitcast<f32>(rec_b[o + 2u]),
                      bitcast<f32>(rec_b[o + 3u]));
  let L = lvl_b[q];
  let j = tab_b[12u * L + 2u];
  let t = 12u * j;
  let first = tab_b[t];
  let n = i32(tab_b[t + 1u]);
  let W = vec2<u32>(tab_b[t + 3u], tab_b[t + 4u]);
  let inv = bitcast<f32>(tab_b[t + 5u]);
  let x0 = vec2<f32>(bitcast<f32>(tab_b[t + 6u]), bitcast<f32>(tab_b[t + 7u]));
  let y0 = vec2<f32>(bitcast<f32>(tab_b[t + 8u]), bitcast<f32>(tab_b[t + 9u]));
  // (x - x0) / texel - 0.5 as (integer, fraction)
  var gx = coord_div(coord_add(vec2<f32>(pos.x - x0.x, 0.0), pos.y - x0.y), W, 40u, inv);
  var gy = coord_div(coord_add(vec2<f32>(pos.z - y0.x, 0.0), pos.w - y0.y), W, 40u, inv);
  gx = coord_add(gx, -0.5);
  gy = coord_add(gy, -0.5);
  var i0 = i32(gx.x);
  var ti = gx.y;
  var j0 = i32(gy.x);
  var tj = gy.y;
  // np.clip(fi, 0, n - 1), then i0 = min(floor(fi), n - 2), ti = fi - i0
  if (i0 < 0) { i0 = 0; ti = 0.0; }
  if (i0 >= n - 1) { i0 = max(n - 2, 0); ti = select(0.0, 1.0, n >= 2); }
  if (j0 < 0) { j0 = 0; tj = 0.0; }
  if (j0 >= n - 1) { j0 = max(n - 2, 0); tj = select(0.0, 1.0, n >= 2); }
  let i1 = min(i0 + 1, n - 1);
  let j1 = min(j0 + 1, n - 1);
  let f = i32(first);
  let v00 = stack_b[f + j0 * n + i0];
  let v10 = stack_b[f + j0 * n + i1];
  let v01 = stack_b[f + j1 * n + i0];
  let v11 = stack_b[f + j1 * n + i1];
  outV_b[q] = (v00 * (1.0 - ti) + v10 * ti) * (1.0 - tj) + (v01 * (1.0 - ti) + v11 * ti) * tj;
}
