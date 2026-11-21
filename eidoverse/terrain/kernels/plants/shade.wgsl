// plants/shade: plants.py _shade_at (blender/eidoblend/terrain/build/plants.py at f9fba8c): 0..1 shade at points
// from the shade-casting plants placed so far: full within half of radius x a crown's radius of its trunk, none beyond
// radius x it; crowns add up as 1 - product(1 - s), summed as logs. The casters are found on the hashed grid
// (plants/grid.wgsl, cells of radius x the largest crown); each is counted once (its own cell). The sum's order is the
// grid's (fixed: the same every run), not _pairs' (float32 here, float64 there).
//! include plants/lib
//! include plants/grid
//! sampler rec r32ui     the points' records (uStride numbers each, the position at words uPos .. uPos + 3)
//! sampler cb r32ui      the casters, 8 numbers each: the position, the crown radius
//! sampler gstart r32ui
//! sampler gcount r32ui
//! sampler gidx r32ui
//! image   outS r32f     per point: its shade
//! uniform vec4  uGO
//! uniform ivec2 uGW
//! uniform float uGInv
//! uniform int   uGMask
//! uniform float uRad    the species' shade radius, in crown radii
//! uniform float uReach  the grid's cell: uRad x the largest crown radius (_pairs' reach)
//! uniform int   uStride
//! uniform int   uPos
//! uniform int   uCount

const LOG_1E9: f32 = -20.72326583694641;   // log1p(-(1 - 1e-9)): plants.py's floor under a full crown

fn cpos(j: u32) -> vec4<f32> {
  return vec4<f32>(bitcast<f32>(cb_b[8u * j]), bitcast<f32>(cb_b[8u * j + 1u]), bitcast<f32>(cb_b[8u * j + 2u]),
                   bitcast<f32>(cb_b[8u * j + 3u]));
}

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let o = u32(q * u.uStride + u.uPos);
  let pos = vec4<f32>(bitcast<f32>(rec_b[o]), bitcast<f32>(rec_b[o + 1u]), bitcast<f32>(rec_b[o + 2u]),
                      bitcast<f32>(rec_b[o + 3u]));
  let c = gcell(pos);
  var logs = 0.0;
  for (var dy = -1; dy <= 1; dy++) {
    for (var dx = -1; dx <= 1; dx++) {
      let cc = c + vec2<i32>(dx, dy);
      let b = gkey(cc);
      let s0 = gstart_b[b];
      let n = gcount_b[b];
      for (var t = 0u; t < n; t++) {
        let j = gidx_b[s0 + t];
        let cp = cpos(j);
        if (any(gcell(cp) != cc)) { continue; }
        let d = sqrt(pos_d2(pos, cp));
        if (d > u.uReach) { continue; }
        let reach = u.uRad * bitcast<f32>(cb_b[8u * j + 4u]);
        let s = 1.0 - pl_smooth(0.5 * reach, reach, d);
        if (s > 0.0) {
          if (s >= 1.0) { logs += LOG_1E9; } else { logs += log1p_neg(-s); }
        }
      }
    }
  }
  outS_b[q] = 1.0 - exp(logs);
}
