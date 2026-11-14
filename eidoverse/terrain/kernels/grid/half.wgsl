// Port of blender/eidoblend/terrain/api.py at f90c6fc: _cache_dtype's float16 (np.asarray(a, np.float16)), numpy's
// casts between float32 and float16, on the GPU, for the npz files both editions write: Terrain.save and the cache
// store the bounded masks as float16.
//   mode 0, unpack: words of two little-endian float16 values each (a Float16Array's bytes, uploaded as they are)
//           to float32, exactly (every float16 is a float32): numpy's npy_halfbits_to_floatbits, in integer
//           arithmetic, so no GPU's handling of float16 subnormals enters
//   mode 1, pack:   a float field to float16 words as numpy's float32 -> float16 cast rounds them, transcribed from
//           numpy's npy_floatbits_to_halfbits (round to nearest even; overflow to infinity; subnormals; a NaN keeps
//           its payload's top bits and stays a NaN), in integer arithmetic, so no GPU rounding mode enters
//! sampler src              mode 0: the words (a list, r32ui read as raw bits); mode 1: the float field
//! sampler words r32ui      mode 0: the packed float16 words
//! image   outF r32f        mode 0: the float32 values (h x w)
//! image   outW r32ui       mode 1: the packed words, a list (rows of uLine words)
//! uniform int uMode
//! uniform int uCount       the values
//! uniform int uLine        mode 1: words per row of outW

fn half_bits(f: u32) -> u32 {
  let h_sgn = (f & 0x80000000u) >> 16u;
  let f_exp = f & 0x7f800000u;
  if (f_exp >= 0x47800000u) {
    if (f_exp == 0x7f800000u) {
      let f_sig = f & 0x007fffffu;
      if (f_sig != 0u) {
        var ret = 0x7c00u + (f_sig >> 13u);
        if (ret == 0x7c00u) { ret = ret + 1u; }
        return h_sgn + ret;
      }
      return h_sgn + 0x7c00u;
    }
    return h_sgn + 0x7c00u;
  }
  if (f_exp <= 0x38000000u) {
    if (f_exp < 0x33000000u) { return h_sgn; }
    let e = f_exp >> 23u;
    var f_sig = 0x00800000u + (f & 0x007fffffu);
    f_sig = f_sig >> (113u - e);
    if (((f_sig & 0x00003fffu) != 0x00001000u) || ((f & 0x000007ffu) != 0u)) { f_sig = f_sig + 0x00001000u; }
    return h_sgn + (f_sig >> 13u);
  }
  let h_exp = (f_exp - 0x38000000u) >> 13u;
  var f_sig = f & 0x007fffffu;
  if ((f_sig & 0x00003fffu) != 0x00001000u) { f_sig = f_sig + 0x00001000u; }
  return h_sgn + h_exp + (f_sig >> 13u);
}

fn float_bits(h: u32) -> u32 {
  var h_exp = h & 0x7c00u;
  let f_sgn = (h & 0x8000u) << 16u;
  if (h_exp == 0u) {
    var h_sig = h & 0x03ffu;
    if (h_sig == 0u) { return f_sgn; }
    h_sig = h_sig << 1u;
    var e = 0u;
    while ((h_sig & 0x0400u) == 0u) {
      h_sig = h_sig << 1u;
      e = e + 1u;
    }
    return f_sgn + ((127u - 15u - e) << 23u) + ((h_sig & 0x03ffu) << 13u);
  }
  if (h_exp == 0x7c00u) { return f_sgn + 0x7f800000u + ((h & 0x03ffu) << 13u); }
  return f_sgn + (((h & 0x7fffu) + 0x1c000u) << 13u);
}

fn kmain(p: vec2<i32>) {
  let n = u32(u.uCount);
  if (u.uMode == 0) {
    let s = outF_size();
    if (!inside(p, s)) { return; }
    let k = u32(p.y * s.x + p.x);
    if (k >= n) { return; }
    let h = (words_b[k >> 1u] >> ((k & 1u) * 16u)) & 0xFFFFu;
    outF_b[k] = bitcast<f32>(float_bits(h));
    return;
  }
  if (p.x >= u.uLine) { return; }
  let g = u32(p.y * u.uLine + p.x);
  if (2u * g >= n) { return; }
  var w = half_bits(bitcast<u32>(src_b[2u * g]));
  if (2u * g + 1u < n) { w = w | (half_bits(bitcast<u32>(src_b[2u * g + 1u])) << 16u); }
  outW_b[g] = w;
}
