// Port of numpy code of blender/eidoblend/terrain/surface/__init__.py and maps.py at d67f19e, as a GPU kernel (the
// port's own, PORT_PLAN.md 3.2, 3.5: the encoding per family in the kernel, one readback per level). encode: a map as
// the surface cache stores it (__init__.py _stored and _level_arrays), packed into 32-bit words row by row:
//   uKind 0..3  uint8, four texels a word (byte k of word i holds texel 4 i + k of its row), as
//               np.rint(maps.encode(s, a, cell) * F(255)).astype(np.uint8): 0 unit clamp(a, 0, 1); 1 signed
//               clamp(a, -1, 1) x 0.5 + 0.5; 2 bend clamp(a x uScale, -1, 1) x 0.5 + 0.5 (uScale the curvature's scale,
//               metres); 3 thick sqrt(clamp(a, 0, t_max) x uScale) (uScale float32(1 / t_max)). WGSL's round() is
//               numpy's rint (halves to even); pack4x8unorm is not used, it rounds halves up
//   uKind 4     float16, two texels a word (the low half the even texel), as np.asarray(a - uRef, np.float16): the
//               D maps, the F maps less their level's reference (uRef), and every other map the cache keeps in half
// The output field is (rows, ceil(columns / 4)) or (rows, ceil(columns / 2)) words; a texel past the row's end is 0.
//! sampler src
//! image   outW r32ui
//! uniform int uKind
//! uniform float uScale
//! uniform float uRef

fn enc8(x: f32) -> u32 {
  var v = 0.0;
  if (u.uKind == 0) {
    v = clamp(x, 0.0, 1.0);
  } else if (u.uKind == 1) {
    v = clamp(x, -1.0, 1.0) * 0.5 + 0.5;
  } else if (u.uKind == 2) {
    v = clamp(x * u.uScale, -1.0, 1.0) * 0.5 + 0.5;
  } else {
    v = sqrt(clamp(x, 0.0, 1.0 / u.uScale) * u.uScale);
  }
  return u32(round(v * 255.0));
}

fn kmain(p: vec2<i32>) {
  let n = outW_size();
  if (!inside(p, n)) { return; }
  let w = src_size().x;
  if (u.uKind < 4) {
    var word = 0u;
    for (var k = 0; k < 4; k++) {
      let i = 4 * p.x + k;
      if (i < w) { word = word | (enc8(src_at(vec2<i32>(i, p.y)).x) << u32(8 * k)); }
    }
    outW_store(p, word);
  } else {
    let i = 2 * p.x;
    let a = src_at(vec2<i32>(i, p.y)).x - u.uRef;
    var b = 0.0;
    if (i + 1 < w) { b = src_at(vec2<i32>(i + 1, p.y)).x - u.uRef; }
    outW_store(p, pack2x16float(vec2<f32>(a, b)));
  }
}
