// The port's own kernel (no Blender counterpart): the channel masks of blender/eidoblend/terrain/solvers/
// hillslope.py op_soil_hills at f90c6fc, which numpy makes in float64:
//     chan = A >= a_ch (| h <= sea)          the channels by their routed area (and the sea)
//     lake = (filled - h) > 1e-4 (| hollow)  a filled hollow is no channel by its area
//     chan &= ~lake;  core = chan            (bit 0 chan, bit 1 core, bit 2 lake of the u32 written)
// Exact comparisons: uACh is the smallest float32 at or above a_ch, so a float32 A passes exactly when numpy's
// float64 test does; (filled - h) - 1e-4 > 0 is decided by its exact sign (hydro/lib's sum_sign4, with 1e-4 split
// into two float32 parts), as numpy's float64 difference of two float32 values is exact.
//! include hydro/lib
//! sampler A
//! sampler h
//! sampler filled
//! sampler hollow
//! image   outB r32ui
//! uniform float uACh
//! uniform float uEpsHi
//! uniform float uEpsLo
//! uniform int uSea
//! uniform float uSea32
//! uniform int uHollow

fn kmain(p: vec2<i32>) {
  if (!inside(p, outB_size())) { return; }
  let h = h_at(p).x;
  var chan = A_at(p).x >= u.uACh;
  if (u.uSea == 1 && h <= u.uSea32) { chan = true; }
  var lake = sum_sign4(filled_at(p).x, -h, -u.uEpsHi, -u.uEpsLo) > 0;
  if (u.uHollow == 1 && hollow_at(p).x > 0.5) { lake = true; }
  chan = chan && !lake;
  var bits = 0u;
  if (chan) { bits = 3u; }
  if (lake) { bits = bits | 4u; }
  outB_store(p, bits);
}
