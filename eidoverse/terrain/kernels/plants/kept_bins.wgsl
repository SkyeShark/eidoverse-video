// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/kept_bins: plants.py _kept_profile's sums (blender/eidoblend/terrain/build/plants.py at f9fba8c): per
// distance band of R / 48 from the focus, the crown area (size^2) of the placed plants and of those the view keeps,
// as 64-bit fixed-point sums (size^2 x 2^16, rounded; a carry into the high word): exact integers in any order,
// where plants.py's np.bincount sums float64 in the plants' order. JavaScript takes the shares from them.
//! include plants/lib
//! sampler cand r32ui    the placed plants' records (size 7, dist 9)
//! sampler keep r32ui    per placed plant: 1 when the view keeps it
//! image   outB atomic_u32  48 bands x 4 numbers: placed (lo, hi), kept (lo, hi)
//! uniform float uR      the species' radius
//! uniform int   uCount

fn add64(at: u32, v: u32) {
  if (v == 0u) { return; }
  let old = atomicAdd(&outB_b[at], v);
  if (old + v < old) { atomicAdd(&outB_b[at + 1u], 1u); }
}

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let o = 16u * u32(i);
  let size = bitcast<f32>(cand_b[o + 7u]);
  let d = bitcast<f32>(cand_b[o + 9u]);
  let b = min(i32(d / u.uR * 48.0), 48);
  if (b >= 48) { return; }
  let w = u32(min(round(size * size * 65536.0), 4294967040.0));
  add64(4u * u32(b), w);
  if (keep_b[i] != 0u) { add64(4u * u32(b) + 2u, w); }
}
