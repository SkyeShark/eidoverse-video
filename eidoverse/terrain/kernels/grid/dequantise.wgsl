// Port of blender/eidoblend/terrain/core/io.py at f90c6fc: read_heightmap's metres from a png16 or r16 heightmap,
// min_m + v / 65535 * (max_m - min_m), with the north-up row flip (and real_place's own formula the same way). numpy
// computes it in float64; the port's fields are float32, so each of the 65536 values is computed once in
// JavaScript doubles exactly as numpy does and rounded to float32 once (core/io.js dequantiseTable), and each cell
// looks its value up: the float64 result rounded once, bit for bit.
//! sampler q r32ui          the integer samples (row 0 north when uFlip): one per cell, or (uPacked) the r16 file's
//                           words, two little-endian uint16 samples each
//! sampler table r32f       one float32 value per sample value, in a list
//! image   outF r32f        the values, row 0 south
//! uniform int uFlip
//! uniform int uCount       the table's length (larger samples take its last value)
//! uniform int uPacked

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var j = p.y;
  if (u.uFlip != 0) { j = n.y - 1 - p.y; }
  var s: u32;
  if (u.uPacked != 0) {
    let k = u32(j * n.x + p.x);
    s = (q_b[k >> 1u] >> ((k & 1u) * 16u)) & 0xFFFFu;
  } else {
    s = q_at(vec2<i32>(p.x, j));
  }
  let v = min(s, u32(u.uCount - 1));
  outF_store(p, vec4<f32>(table_b[v], 0.0, 0.0, 0.0));
}
