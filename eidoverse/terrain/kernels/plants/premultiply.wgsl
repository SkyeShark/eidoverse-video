// Port of blender/eidoblend/terrain/build/plant_instances.py at f9fba8c (its still billboard's baked albedo as the
// material reads it), as a GPU kernel (the port's own step: the header of build/plant_instances.js says why).
// plants/premultiply: a billboard bake's albedo (8-bit sRGB, straight alpha, its colour dilated 12 texels past the
// silhouette, SeedThree's bakeGroupToTextures) with its colour multiplied by its alpha in linear light and encoded back
// to sRGB bytes. Its mips then average the silhouette's colour alone, and the material's colour over alpha is that
// colour at every mip; straight mips averaged the dilated colour in, so colour over alpha over-brightened a far
// canopy's edges (to white where it clipped). With uFlip the rows are written bottom first (a canvas bake, top row
// first, made a DataTexture, which uploads its rows as they lie: the canvas texture's flipY).
//! include plants/lib
//! sampler px r32ui      the pixels, RGBA8 packed in a u32 each (R in the low byte), uW x uH
//! image   outP r32ui    the same pixels, the colour premultiplied
//! uniform int uW
//! uniform int uH
//! uniform int uFlip
//! uniform int uCount

fn dec(c: f32) -> f32 { return select(pow((c + 0.055) / 1.055, 2.4), c / 12.92, c <= 0.04045); }
fn enc(c: f32) -> f32 { return select(1.055 * pow(max(c, 0.0031308), 1.0 / 2.4) - 0.055, 12.92 * c, c <= 0.0031308); }

fn kmain(p: vec2<i32>) {
  let q = lin(p);
  if (q >= u.uCount) { return; }
  let v = px_b[q];
  let a = f32((v >> 24u) & 255u) / 255.0;
  var o = v & 0xFF000000u;
  for (var k = 0u; k < 3u; k++) {
    let c = f32((v >> (8u * k)) & 255u) / 255.0;
    let e = u32(clamp(round(enc(dec(c) * a) * 255.0), 0.0, 255.0));
    o = o | (e << (8u * k));
  }
  let y = q / u.uW;
  let x = q - y * u.uW;
  let yo = select(y, u.uH - 1 - y, u.uFlip != 0);
  outP_b[yo * u.uW + x] = o;
}
