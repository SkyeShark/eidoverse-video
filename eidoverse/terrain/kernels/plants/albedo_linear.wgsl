// plants/albedo_linear: an 8-bit sRGB image's pixels as linear colour (dressing.py _image_mean_linear, which the rock
// recolour divides by): per pixel, one channel (uChannel) decoded from sRGB, for a mean over the image.
//! include plants/lib
//! sampler px r32ui      the pixels, RGBA8 packed in a u32 each (R in the low byte)
//! image   outL r32f
//! uniform int uChannel
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let c = f32((px_b[q] >> (8u * u32(u.uChannel))) & 255u) / 255.0;
  outL_b[q] = select(pow((c + 0.055) / 1.055, 2.4), c / 12.92, c <= 0.04045);
}
