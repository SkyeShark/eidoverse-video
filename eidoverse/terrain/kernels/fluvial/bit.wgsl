// The port's own kernel (no Blender counterpart): one bit of a u32 bit field as a 0 / 1 float field, for a count of
// its cells (blender/eidoblend/terrain/solvers/hillslope.py op_soil_hills at f90c6fc: int(chan.sum()), a numpy
// sum over a boolean mask; here the cells counted by core/prims.js stats).
//! sampler b r32ui      the bit field (soil_chan, soil_down: bit 0 chan, bit 1 core, bit 2 lake)
//! image   outF r32f
//! uniform int uBit     the bit's mask (1, 2, 4)

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  outF_store(p, vec4<f32>(select(0.0, 1.0, (b_at(p) & u32(u.uBit)) != 0u), 0.0, 0.0, 0.0));
}
