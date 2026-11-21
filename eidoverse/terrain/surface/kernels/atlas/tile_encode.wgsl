// Port of numpy code of blender/eidoblend/terrain/surface/__init__.py (SurfaceData.tile, _encode, _linear_to_srgb),
// maps.py (encode) and atlas.py (write_image) at d67f19e, as a GPU kernel (the port's own, PORT_PLAN.md 3.2).
// tile_encode: a tile's four channels (physical values, size x size) as its texture layer holds them, written in the
// layer's corner. Per channel uKinds[c]:
//   0 the value (float)          1 unit: clamp(v, 0, 1)            2 signed: clamp(v, -1, 1) x 0.5 + 0.5
//   3 bend: clamp(v x s, -1, 1) x 0.5 + 0.5 (s = uScales[c])        4 thick: sqrt(clamp(v, 0, 1 / s) x s)
//   5 less the level's reference: v - uScales[c] (the F family)      6 sRGB: the sRGB curve of clamp(v, 0, 1) (C, P)
//   7 zero (an unused channel)
// uFormat 0 RGBA8: one word a texel, byte c = clip(rint(v_c x 255), 0, 255) (write_image's PNG bytes; WGSL's round
// is numpy's rint); 1 RGBA16F: two words a texel, the halves (r, g) and (b, a) (half precision, as the image keeps).
//! sampler c0
//! sampler c1
//! sampler c2
//! sampler c3
//! image   outW r32ui
//! uniform ivec4 uKinds
//! uniform vec4 uScales
//! uniform int uFormat
//! uniform int uSize     the tile's texels a side (an unused channel's sampler is a 1 x 1 stand-in)

fn enc(v: f32, kind: i32, s: f32) -> f32 {
  switch (kind) {
    case 1: { return clamp(v, 0.0, 1.0); }
    case 2: { return clamp(v, -1.0, 1.0) * 0.5 + 0.5; }
    case 3: { return clamp(v * s, -1.0, 1.0) * 0.5 + 0.5; }
    case 4: { return sqrt(clamp(v, 0.0, 1.0 / s) * s); }
    case 5: { return v - s; }
    case 6: {
      let c = clamp(v, 0.0, 1.0);
      if (c <= 0.0031308) { return c * 12.92; }
      return 1.055 * pow(c, 1.0 / 2.4) - 0.055;
    }
    case 7: { return 0.0; }
    default: { return v; }
  }
}

fn byte(v: f32) -> u32 {
  return u32(clamp(round(v * 255.0), 0.0, 255.0));
}

// channel c's value at tile texel t (0 for an unused channel: its stand-in is not read)
fn chan(c: i32, t: vec2<i32>, kind: i32) -> f32 {
  if (kind == 7) { return 0.0; }
  if (c == 0) { return c0_at(t).x; }
  if (c == 1) { return c1_at(t).x; }
  if (c == 2) { return c2_at(t).x; }
  return c3_at(t).x;
}

fn kmain(p: vec2<i32>) {
  let words = outW_size();
  if (p.x >= words.x || p.y >= words.y) { return; }
  var t = p;
  if (u.uFormat == 1) { t = vec2<i32>(p.x / 2, p.y); }
  if (t.x >= u.uSize || t.y >= u.uSize) { return; }
  let v = vec4<f32>(enc(chan(0, t, u.uKinds.x), u.uKinds.x, u.uScales.x), enc(chan(1, t, u.uKinds.y), u.uKinds.y, u.uScales.y),
                    enc(chan(2, t, u.uKinds.z), u.uKinds.z, u.uScales.z), enc(chan(3, t, u.uKinds.w), u.uKinds.w, u.uScales.w));
  if (u.uFormat == 0) {
    outW_store(p, byte(v.x) | (byte(v.y) << 8u) | (byte(v.z) << 16u) | (byte(v.w) << 24u));
  } else if (p.x % 2 == 0) {
    outW_store(p, pack2x16float(v.xy));
  } else {
    outW_store(p, pack2x16float(v.zw));
  }
}
