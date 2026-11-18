// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/fluvial.py offset_block_means()
// at f90c6fc, the low-pass lock's targets: each block's mean over its cells inside the grid (block (J, I) covers cells
// b (J, I) - off .. + b, clipped; 0 where it holds none), which numpy computes in float64 from a summed-area table
// and FluvialRun rounds to float32.
//
// The lock's first residuals (lock_restrict: the block's float32 mean minus its target) are the size of float32
// rounding, so a target made by a float32 sum (a millimetre off on a 1,000 m block) would be larger than what it is
// compared with. Here each block's sum is exact and its mean rounded once: every float32 value is placed as an
// integer in units of 2^(e - 63), e the exponent of the block's largest |value| (a 96-bit two's-complement sum: 2^24
// values of under 2^64 never overflow it; a value 2^40 below the largest loses its lowest bits), then divided by the
// cell count exactly (long division in base 2^8, 32 bits past the point, the remainder kept as a sticky bit) and
// rounded to the nearest float32, ties to even. numpy's own float64 summed-area table rounds too (about 1e-16 of
// the sums), so a block whose true mean lies that close to a float32 tie may round the other way there: rare, and
// one float32 step.
//! sampler h            the level's start (the lock's h0)
//! image   outT r32f    the blocks' means
//! uniform int uB       the block, cells
//! uniform ivec2 uOff   the block grid's offset, cells

fn f_sig(x: f32) -> u32 {
  let b = bitcast<u32>(x);
  let m = b & 0x7FFFFFu;
  if (((b >> 23u) & 0xFFu) == 0u) { return m; }
  return m | 0x800000u;
}
fn f_exp(x: f32) -> i32 {
  let e = i32((bitcast<u32>(x) >> 23u) & 0xFFu);
  if (e == 0) { return -126; }
  return e - 127;
}

// 96-bit two's-complement integers as vec3(w2, w1, w0), w0 the lowest word
fn add96(a: vec3<u32>, b: vec3<u32>) -> vec3<u32> {
  let lo = a.z + b.z;
  let c0 = select(0u, 1u, lo < a.z);
  let mid = a.y + b.y;
  var c1 = select(0u, 1u, mid < a.y);
  let mid2 = mid + c0;
  c1 = c1 + select(0u, 1u, mid2 < mid);
  return vec3<u32>(a.x + b.x + c1, mid2, lo);
}
fn neg96(a: vec3<u32>) -> vec3<u32> {
  let lo = ~a.z + 1u;
  let c = select(0u, 1u, lo == 0u);
  let mid = ~a.y + c;
  let c2 = select(0u, 1u, c == 1u && mid == 0u);
  return vec3<u32>(~a.x + c2, mid, lo);
}
// v in units of 2^(emax - 63), truncated toward zero
fn place96(v: f32, emax: i32) -> vec3<u32> {
  let m = f_sig(v);
  if (m == 0u) { return vec3<u32>(0u, 0u, 0u); }
  let s = f_exp(v) - emax + 40;
  var w = vec3<u32>(0u, 0u, 0u);
  if (s < 0) {
    let r = -s;
    if (r < 24) { w = vec3<u32>(0u, 0u, m >> u32(r)); }
  } else if (s == 0) {
    w = vec3<u32>(0u, 0u, m);
  } else if (s < 32) {
    w = vec3<u32>(0u, m >> u32(32 - s), m << u32(s));
  } else if (s == 32) {
    w = vec3<u32>(0u, m, 0u);
  } else {
    let t = s - 32;
    w = vec3<u32>(m >> u32(32 - t), m << u32(t), 0u);
  }
  if ((bitcast<u32>(v) >> 31u) != 0u) { w = neg96(w); }
  return w;
}

var<private> Q: array<u32, 16>;                           // the quotient's base-2^8 digits, Q[0] the highest
fn qbit(k: i32) -> u32 {
  if (k < 0) { return 0u; }
  return (Q[15 - k / 8] >> u32(k % 8)) & 1u;
}

fn kmain(p: vec2<i32>) {
  if (!inside(p, outT_size())) { return; }
  let n = h_size();
  let c0 = clamp(u.uB * p - u.uOff, vec2<i32>(0, 0), n);
  let c1 = clamp(u.uB * p - u.uOff + u.uB, vec2<i32>(0, 0), n);
  let cnt = (c1.y - c0.y) * (c1.x - c0.x);
  if (cnt <= 0) {
    outT_store(p, vec4<f32>(0.0, 0.0, 0.0, 0.0));
    return;
  }
  var emax = -1000;
  for (var j = c0.y; j < c1.y; j++) {
    for (var i = c0.x; i < c1.x; i++) {
      let v = h_at(vec2<i32>(i, j)).x;
      if (f_sig(v) != 0u) { emax = max(emax, f_exp(v)); }
    }
  }
  if (emax == -1000) {
    outT_store(p, vec4<f32>(0.0, 0.0, 0.0, 0.0));
    return;
  }
  var s = vec3<u32>(0u, 0u, 0u);
  for (var j = c0.y; j < c1.y; j++) {
    for (var i = c0.x; i < c1.x; i++) { s = add96(s, place96(h_at(vec2<i32>(i, j)).x, emax)); }
  }
  let neg = (s.x >> 31u) != 0u;
  var mag = s;
  if (neg) { mag = neg96(s); }
  // |sum| 2^32 / cnt, digit by digit in base 2^8 (a block of up to 2^24 cells keeps rem 2^8 + digit in a u32)
  let c = u32(cnt);
  var rem = 0u;
  for (var k = 0; k < 16; k++) {
    var dg = 0u;
    if (k < 12) {
      let word = select(select(mag.z, mag.y, k < 8), mag.x, k < 4);
      dg = (word >> u32(24 - 8 * (k % 4))) & 0xFFu;
    }
    let cur = rem * 256u + dg;
    Q[k] = cur / c;
    rem = cur % c;
  }
  var top = -1;
  for (var k = 0; k < 16; k++) {
    if (Q[k] != 0u) {
      top = 8 * (15 - k) + (31 - i32(countLeadingZeros(Q[k])));
      break;
    }
  }
  if (top < 0) {
    outT_store(p, vec4<f32>(0.0, 0.0, 0.0, 0.0));
    return;
  }
  var mant = 0u;
  for (var t = 0; t < 24; t++) { mant = (mant << 1u) | qbit(top - t); }
  let guard = qbit(top - 24);
  var sticky = rem != 0u;
  for (var k = 0; k < top - 24; k++) { if (qbit(k) != 0u) { sticky = true; } }
  if (guard == 1u && (sticky || (mant & 1u) == 1u)) {
    mant = mant + 1u;
    if (mant == 0x1000000u) {
      mant = 0x800000u;
      top = top + 1;
    }
  }
  // the value is mant 2^(top - 23) 2^(emax - 95)
  let be = top + emax - 95 + 127;
  if (be <= 0 || be >= 255) {
    // a subnormal or an overflow: not a terrain's height; the float32 mean instead
    var f = 0.0;
    for (var j = c0.y; j < c1.y; j++) { for (var i = c0.x; i < c1.x; i++) { f += h_at(vec2<i32>(i, j)).x; } }
    outT_store(p, vec4<f32>(f / f32(cnt), 0.0, 0.0, 0.0));
    return;
  }
  var bits = (u32(be) << 23u) | (mant & 0x7FFFFFu);
  if (neg) { bits = bits | 0x80000000u; }
  outT_store(p, vec4<f32>(bitcast<f32>(bits), 0.0, 0.0, 0.0));
}
