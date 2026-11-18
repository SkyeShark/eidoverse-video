// What the kernels of kernels/hydro/ share (`//! include hydro/lib`): exact sums of float32 values, where numpy adds
// float32 heights in float64 (exact for terrain heights) and rounds the result to float32 once: the lakes' deposit
// (deposit + filled - h) and the parent's lake water (ph + pw - h, and the largest lake level ph + pw); and numpy's
// float64 routing surfaces held exactly as float32 pairs (h + water, which is not a float32 value on many lake
// cells, and decides numpy's flats and receivers there: solvers/hydro.js says where).
//
// Integer arithmetic, not float tricks: a two-sum (Knuth's error-free addition) does not survive this machine's
// shader compiler, which reassociates and contracts float arithmetic (PORT_PLAN.md 2.3; measured again for this
// file: a two-sum shielded by multiplications with an opaque uniform 1.0 still came out 1 ulp off on the lakes
// fixtures). So each value's 24-bit significand is aligned in a 64-bit two's-complement integer (two u32 words, the
// largest value's significand at bits 36..59, so four of them add without overflow), the values are added exactly,
// and the sum is rounded once to float32, to nearest, ties to even. A value more than 2^36 below the largest keeps
// its shifted-out bits as a sticky bit, which decides a rounding exactly unless the sum cancels to within 2^-36 of
// the largest value (a lake's depth is above 1e-4 m and a parent's lake water above 1e-6 m: never). The kernels'
// float arithmetic cannot touch it. tests/hydro/hydro_test.mjs checks it on random triples and every lakes fixture.

const TOP: i32 = 36;

// a 64-bit two's-complement integer as vec2(hi, lo)
fn w_add(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
  let lo = a.y + b.y;
  var c = 0u;
  if (lo < a.y) { c = 1u; }
  return vec2<u32>(a.x + b.x + c, lo);
}
fn w_neg(a: vec2<u32>) -> vec2<u32> {
  let lo = ~a.y + 1u;
  var c = 0u;
  if (lo == 0u) { c = 1u; }
  return vec2<u32>(~a.x + c, lo);
}
fn w_greater(a: vec2<u32>, b: vec2<u32>) -> bool { return a.x > b.x || (a.x == b.x && a.y > b.y); }
// a >> r (logical), r in 0..63
fn w_shr(a: vec2<u32>, r: u32) -> vec2<u32> {
  if (r == 0u) { return a; }
  if (r < 32u) { return vec2<u32>(a.x >> r, (a.y >> r) | (a.x << (32u - r))); }
  return vec2<u32>(0u, a.x >> (r - 32u));
}
// a & (2^r - 1), r in 0..63
fn w_low(a: vec2<u32>, r: u32) -> vec2<u32> {
  if (r == 0u) { return vec2<u32>(0u, 0u); }
  if (r < 32u) { return vec2<u32>(0u, a.y & ((1u << r) - 1u)); }
  if (r == 32u) { return vec2<u32>(0u, a.y); }
  return vec2<u32>(a.x & ((1u << (r - 32u)) - 1u), a.y);
}
// 2^r, r in 0..62
fn w_pow2(r: u32) -> vec2<u32> {
  if (r < 32u) { return vec2<u32>(0u, 1u << r); }
  return vec2<u32>(1u << (r - 32u), 0u);
}

// a float32 as m * 2^(e - 23): its significand m (< 2^24, the hidden bit set for a normal number) and exponent e
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

// x's significand placed so that the exponent emax lands at bit TOP + 23, signed (a sticky bit for what falls off)
fn w_place(x: f32, emax: i32) -> vec2<u32> {
  let m = f_sig(x);
  if (m == 0u) { return vec2<u32>(0u, 0u); }
  let s = TOP - (emax - f_exp(x));
  var v = vec2<u32>(0u, 0u);
  if (s >= 32) {
    v = vec2<u32>(m << u32(s - 32), 0u);
  } else if (s > 0) {
    v = vec2<u32>(m >> u32(32 - s), m << u32(s));
  } else if (s == 0) {
    v = vec2<u32>(0u, m);
  } else if (s > -24) {
    let r = u32(-s);
    var sticky = 0u;
    if ((m & ((1u << r) - 1u)) != 0u) { sticky = 1u; }
    v = vec2<u32>(0u, (m >> r) | sticky);
  } else {
    v = vec2<u32>(0u, 1u);
  }
  if ((bitcast<u32>(x) >> 31u) != 0u) { v = w_neg(v); }
  return v;
}

fn w_emax(e: i32, x: f32) -> i32 {
  if (f_sig(x) == 0u) { return e; }
  return max(e, f_exp(x));
}

// the exact sum a + b + c + d, as a 64-bit integer t in units of 2^(emax - 23 - TOP): vec3(t.hi, t.lo, emax), emax
// -1000 when all four are zero
fn w_sum4(a: f32, b: f32, c: f32, d: f32) -> vec3<i32> {
  let emax = w_emax(w_emax(w_emax(w_emax(-1000, a), b), c), d);
  if (emax == -1000) { return vec3<i32>(0, 0, -1000); }
  let t = w_add(w_add(w_place(a, emax), w_place(b, emax)), w_add(w_place(c, emax), w_place(d, emax)));
  return vec3<i32>(bitcast<i32>(t.x), bitcast<i32>(t.y), emax);
}

// the sign of a + b + c + d, exactly: -1, 0 or 1
fn sum_sign4(a: f32, b: f32, c: f32, d: f32) -> i32 {
  let s = w_sum4(a, b, c, d);
  if (s.x < 0) { return -1; }
  if (s.x == 0 && s.y == 0) { return 0; }
  return 1;
}

// a + b + c rounded once to float32 (nearest, ties to even): numpy's float64 sum of three float32 values, rounded
fn sum3(a: f32, b: f32, c: f32) -> f32 { return sum4(a, b, c, 0.0); }

// a + b + c + d rounded once to float32 (nearest, ties to even)
fn sum4(a: f32, b: f32, c: f32, d: f32) -> f32 {
  let s = w_sum4(a, b, c, d);
  if (s.z == -1000) { return 0.0; }
  var t = vec2<u32>(bitcast<u32>(s.x), bitcast<u32>(s.y));
  var neg = false;
  if ((t.x >> 31u) != 0u) {
    neg = true;
    t = w_neg(t);
  }
  if (t.x == 0u && t.y == 0u) { return 0.0; }
  var p = 0;                                          // the highest set bit of |sum|
  if (t.x != 0u) { p = 63 - i32(countLeadingZeros(t.x)); } else { p = 31 - i32(countLeadingZeros(t.y)); }
  var m = 0u;
  var e = s.z - 23 - TOP;                             // |sum| = t * 2^e, and then m * 2^e
  if (p > 23) {
    let r = u32(p - 23);
    m = w_shr(t, r).y;
    let rem = w_low(t, r);
    let half = w_pow2(r - 1u);
    if (w_greater(rem, half) || (rem.x == half.x && rem.y == half.y && (m & 1u) != 0u)) { m = m + 1u; }
    e = e + i32(r);
    if (m == 0x1000000u) {
      m = 0x800000u;
      e = e + 1;
    }
  } else {
    m = t.y << u32(23 - p);
    e = e - (23 - p);
  }
  let be = e + 23 + 127;                              // m in [2^23, 2^24): the float32 exponent's bits
  if (be <= 0 || be >= 255) { return ((a + b) + c) + d; }   // a subnormal or an overflow: not a terrain's number
  var bits = (u32(be) << 23u) | (m & 0x7FFFFFu);
  if (neg) { bits = bits | 0x80000000u; }
  return bitcast<f32>(bits);
}

// An exact float64 value of numpy's held as a pair (hi, lo): hi its float32 rounding (nearest, ties to even), lo the
// rest, exactly (numpy's sum of two float32 values: the rounding error of a float32 sum is a float32). Normalised
// pairs order and compare as their values do: lexicographically. A float32 field read as a pair has lo = 0.
fn p_less(a: vec2<f32>, b: vec2<f32>) -> bool { return a.x < b.x || (a.x == b.x && a.y < b.y); }
fn p_equal(a: vec2<f32>, b: vec2<f32>) -> bool { return a.x == b.x && a.y == b.y; }
// a + b of two float32 values as a pair
fn p_sum(a: f32, b: f32) -> vec2<f32> {
  let hi = a + b;
  return vec2<f32>(hi, sum3(a, b, -hi));
}
// (a - b) of two pairs, rounded once to float32
fn p_diff(a: vec2<f32>, b: vec2<f32>) -> f32 { return sum4(a.x, -b.x, a.y, -b.y); }
