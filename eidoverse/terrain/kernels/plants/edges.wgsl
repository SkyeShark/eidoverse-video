// plants/edges: the conflict graph of plants.py _hard_core (blender/eidoblend/terrain/build/plants.py at f9fba8c):
// two candidates of one priority conflict when both have a hard core (r > 0) and stand closer than 0.75 x the sum of
// their radii. Found on the hashed grid (plants/grid.wgsl, cells of 2 x 0.75 x the largest r). uMode 0 counts each
// candidate's conflicts; uMode 1 writes them at its offset (an exclusive scan of the counts): a CSR adjacency, each
// candidate's neighbours in the grid's order.
//! include plants/lib
//! include plants/grid
//! sampler cand r32ui    the group's candidates (16 numbers each: the position at 0-3, r at 11)
//! sampler gstart r32ui
//! sampler gcount r32ui
//! sampler gidx r32ui
//! sampler offs r32ui    per candidate: its first slot in outA (uMode 1)
//! image   outD r32ui    per candidate: its conflicts (uMode 0)
//! image   outA r32ui    the neighbours (uMode 1)
//! uniform vec4  uGO
//! uniform ivec2 uGW
//! uniform float uGInv
//! uniform int   uGMask
//! uniform float uCF
//! uniform int   uMode
//! uniform int   uCount

fn cpos(j: u32) -> vec4<f32> {
  let o = 16u * j;
  return vec4<f32>(bitcast<f32>(cand_b[o]), bitcast<f32>(cand_b[o + 1u]), bitcast<f32>(cand_b[o + 2u]),
                   bitcast<f32>(cand_b[o + 3u]));
}

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let ri = bitcast<f32>(cand_b[16u * u32(i) + 11u]);
  if (!(ri > 0.0)) {
    if (u.uMode == 0) { outD_b[i] = 0u; }
    return;
  }
  let pos = cpos(u32(i));
  let c = gcell(pos);
  var k = 0u;
  var at = 0u;
  if (u.uMode == 1) { at = offs_b[i]; }
  for (var dy = -1; dy <= 1; dy++) {
    for (var dx = -1; dx <= 1; dx++) {
      let cc = c + vec2<i32>(dx, dy);
      let b = gkey(cc);
      let s = gstart_b[b];
      let n = gcount_b[b];
      for (var t = 0u; t < n; t++) {
        let j = gidx_b[s + t];
        if (j == u32(i)) { continue; }
        let rj = bitcast<f32>(cand_b[16u * j + 11u]);
        if (!(rj > 0.0)) { continue; }
        let q = cpos(j);
        if (any(gcell(q) != cc)) { continue; }
        let lim = u.uCF * (ri + rj);
        if (pos_d2(pos, q) < lim * lim) {
          if (u.uMode == 1) { outA_b[at + k] = j; }
          k++;
        }
      }
    }
  }
  if (u.uMode == 0) { outD_b[i] = k; }
}
