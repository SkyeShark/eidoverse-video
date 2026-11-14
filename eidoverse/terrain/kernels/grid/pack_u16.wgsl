// Port of blender/eidoblend/terrain/core/io.py at f90c6fc: encode_r16's byte layout (.astype('<u2').tobytes()):
// integer samples (each below 65536, row-major) packed two to a word, little-endian, so the readback's bytes are
// the r16 file. One invocation per word. Exact.
//! sampler src r32ui        the samples
//! image   outW r32ui       ceil(count / 2) words, a list (rows of uLine words)
//! uniform int uCount       the samples
//! uniform int uLine        words per row of outW

fn kmain(p: vec2<i32>) {
  if (p.x >= u.uLine) { return; }
  let g = u32(p.y * u.uLine + p.x);
  let n = u32(u.uCount);
  if (2u * g >= n) { return; }
  var w = src_b[2u * g] & 0xFFFFu;
  if (2u * g + 1u < n) { w = w | ((src_b[2u * g + 1u] & 0xFFFFu) << 16u); }
  outW_b[g] = w;
}
