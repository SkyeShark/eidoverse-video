// Port of numpy code of blender/eidoblend/terrain/surface/__init__.py and maps.py at d67f19e, as a GPU kernel (the
// port's own, PORT_PLAN.md 3.2). decode: a map as the surface cache keeps it back to its physical values
// (__init__.py _unstored and _level_maps), texel by texel from the packed words encode.wgsl writes (and the npz holds
// as uint8 or float16 arrays):
//   uKind 0  uint8: x = byte x float32(1 / 255), then maps.decode: 'affine' x uA + uB, 'square' x x uA (uSquare)
//   uKind 1  float16: x + uB (the F maps' reference; 0 for the others)
//! sampler src r32ui
//! image   outF r32f
//! uniform int uKind
//! uniform int uSquare
//! uniform float uA
//! uniform float uB

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var v = 0.0;
  if (u.uKind == 0) {
    let word = src_at(vec2<i32>(p.x / 4, p.y));
    let byte = (word >> u32(8 * (p.x % 4))) & 255u;
    let x = f32(byte) * (1.0 / 255.0);
    if (u.uSquare != 0) { v = x * x * u.uA; } else { v = x * u.uA + u.uB; }
  } else {
    let word = src_at(vec2<i32>(p.x / 2, p.y));
    let h = unpack2x16float(word);
    v = select(h.x, h.y, (p.x % 2) == 1) + u.uB;
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
