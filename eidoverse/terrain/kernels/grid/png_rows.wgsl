// Port of blender/eidoblend/terrain/core/io.py at f90c6fc: the per-byte parts of a PNG (encode_png, decode_png).
//
// Mode 0, encode: integer samples (h rows of w x channels, row 0 the image's top) to the filtered byte stream
// encode_png hands zlib: per row the filter type 2 (Up), then the row's bytes (16-bit samples big-endian) minus the
// previous row's, modulo 256 (row 0 as it is). One invocation per output word of four stream bytes (little-endian
// in the word: the readback's bytes are the stream in order). Exact.
//
// Mode 1, decode: the inflated stream (as encode makes it, or any PNG whose rows use the None or Up filter) back to
// the samples: per byte column, down the rows, cur = line + prev (Up) or line (None), modulo 256. One invocation per
// sample column, walking the rows. core/io.js refuses the other filter types (Sub, Average, Paeth) before this
// runs, naming them: no reference PNG uses them (PORT_PLAN.md 3.2). Exact.
//! sampler src r32ui        mode 0: the samples (h x w c); mode 1: the stream's words, a list
//! image   outW r32ui       mode 0: the stream's words, a list (rows of uLine words); mode 1: the samples
//! uniform int uMode
//! uniform ivec2 uSize      the image: (samples per row (w c), rows h)
//! uniform int uBps         bytes per sample, 1 or 2
//! uniform int uWords       mode 0: the stream's length in words
//! uniform int uLine        mode 0: words per row of outW
//! local   64 1

// byte t of the stream in src_b (mode 1)
fn sbyte(t: u32) -> u32 { return (src_b[t >> 2u] >> ((t & 3u) * 8u)) & 0xFFu; }

// byte c of row r of the raw (unfiltered) rows (mode 0)
fn rawbyte(r: u32, c: u32) -> u32 {
  let bps = u32(u.uBps);
  let s = src_b[r * u32(u.uSize.x) + c / bps];
  if (bps == 1u) { return s & 0xFFu; }
  if ((c & 1u) == 0u) { return (s >> 8u) & 0xFFu; }
  return s & 0xFFu;
}

fn kmain(p: vec2<i32>) {
  let bps = u32(u.uBps);
  let stride = u32(u.uSize.x) * bps;
  let rowLen = stride + 1u;
  let h = u32(u.uSize.y);
  if (u.uMode == 0) {
    let g = u32(p.y * u.uLine + p.x);
    if (p.x >= u.uLine || g >= u32(u.uWords)) { return; }
    var word = 0u;
    for (var b = 0u; b < 4u; b++) {
      let o = 4u * g + b;
      let r = o / rowLen;
      if (r >= h) { break; }
      let c = o - r * rowLen;
      var v = 2u;
      if (c > 0u) {
        v = rawbyte(r, c - 1u);
        if (r > 0u) { v = (v + 256u - rawbyte(r - 1u, c - 1u)) & 0xFFu; }
      }
      word = word | (v << (8u * b));
    }
    outW_b[g] = word;
    return;
  }
  let s = u32(p.x);
  if (p.y != 0 || s >= u32(u.uSize.x)) { return; }
  var prev0 = 0u;
  var prev1 = 0u;
  for (var r = 0u; r < h; r++) {
    let base = r * rowLen;
    let kind = sbyte(base);
    let o = base + 1u + s * bps;
    var cur0 = sbyte(o);
    if (kind == 2u) { cur0 = (cur0 + prev0) & 0xFFu; }
    prev0 = cur0;
    var v = cur0;
    if (bps == 2u) {
      var cur1 = sbyte(o + 1u);
      if (kind == 2u) { cur1 = (cur1 + prev1) & 0xFFu; }
      prev1 = cur1;
      v = (cur0 << 8u) | cur1;
    }
    outW_b[r * u32(u.uSize.x) + s] = v;
  }
}
