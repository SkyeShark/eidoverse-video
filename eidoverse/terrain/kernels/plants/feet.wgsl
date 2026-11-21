// plants/feet: the end of plants.py _thin (blender/eidoblend/terrain/build/plants.py at f9fba8c): a candidate still
// kept is dropped within 0.75 x (a placed plant's foot + its own hard-core radius) of any plant placed before it
// (the earlier priorities' plants), found on the hashed grid (plants/grid.wgsl) of their positions. Clears bit 32 of
// the flags (plants/thin).
//! include plants/lib
//! include plants/grid
//! sampler cand r32ui    the candidates' records (16 numbers each: the position at 0-3, r at 11)
//! sampler pb r32ui      the placed plants, 8 numbers each: the position, the foot radius
//! sampler gstart r32ui  per bucket: its first entry in gidx
//! sampler gcount r32ui  per bucket: its entries
//! sampler gidx r32ui    the placed plants by bucket
//! image   flags r32ui
//! uniform vec4  uGO
//! uniform ivec2 uGW
//! uniform float uGInv
//! uniform int   uGMask
//! uniform float uCF
//! uniform int   uCount

fn ppos(j: u32) -> vec4<f32> {
  return vec4<f32>(bitcast<f32>(pb_b[8u * j]), bitcast<f32>(pb_b[8u * j + 1u]), bitcast<f32>(pb_b[8u * j + 2u]),
                   bitcast<f32>(pb_b[8u * j + 3u]));
}

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let f = flags_b[i];
  if ((f & 32u) == 0u) { return; }
  let o = 16u * u32(i);
  let pos = vec4<f32>(bitcast<f32>(cand_b[o]), bitcast<f32>(cand_b[o + 1u]), bitcast<f32>(cand_b[o + 2u]),
                      bitcast<f32>(cand_b[o + 3u]));
  let rc = bitcast<f32>(cand_b[o + 11u]);
  let c = gcell(pos);
  var blocked = false;
  for (var dy = -1; dy <= 1; dy++) {
    for (var dx = -1; dx <= 1; dx++) {
      let cc = c + vec2<i32>(dx, dy);
      let b = gkey(cc);
      let s = gstart_b[b];
      let n = gcount_b[b];
      for (var t = 0u; t < n; t++) {
        let j = gidx_b[s + t];
        let q = ppos(j);
        if (any(gcell(q) != cc)) { continue; }          // another cell hashed into this bucket
        let lim = u.uCF * (bitcast<f32>(pb_b[8u * j + 4u]) + rc);
        if (pos_d2(pos, q) < lim * lim) { blocked = true; }
      }
    }
  }
  if (blocked) { flags_b[i] = f & ~32u; }
}
