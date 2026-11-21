// plants/lib.wgsl: what the plant planner's kernels share (`//! include plants/lib`). The port's own kernels of the
// numpy code in blender/eidoblend/terrain/build/plants.py at f9fba8c (PORT_PLAN.md 3.5); build/plants.js drives them.
//
// u64 as vec2<u32>(hi, lo): plants.py's hashes are numpy uint64 arithmetic (wrapping), so these are exact.
// A uniform number u = k / 2^53 is kept as its 53-bit integer k (hi 21 bits, lo 32 bits); a comparison of u with a
// float32 threshold is made exactly on k (u53_lt), so a decision differs from plants.py's float64 one only where the
// threshold itself does (float32 arithmetic where numpy's is float64).
// A position is vec4<f32>(xi, xf, yi, yf): metres as an integer part and a fraction in [0, 1) per axis (Blender's
// frame), so a distance between two plants keeps micrometres anywhere on a 30 km terrain.

const P_LINE: i32 = 4096;                    // prims/lib.wgsl LINE: list fields are rows of this many items
// item q of a list kernel dispatched in rows of P_LINE invocations (core/prims.js lineGroups(count))
fn lin(p: vec2<i32>) -> i32 { return p.y * P_LINE + p.x; }

// ------------------------------------------------------------------------------------------------ u64 ---

fn mul32(a: u32, b: u32) -> vec2<u32> {
  let a0 = a & 0xFFFFu;
  let a1 = a >> 16u;
  let b0 = b & 0xFFFFu;
  let b1 = b >> 16u;
  let p00 = a0 * b0;
  let p01 = a0 * b1;
  let p10 = a1 * b0;
  let p11 = a1 * b1;
  let mid = (p00 >> 16u) + (p01 & 0xFFFFu) + (p10 & 0xFFFFu);
  return vec2<u32>(p11 + (p01 >> 16u) + (p10 >> 16u) + (mid >> 16u), (p00 & 0xFFFFu) | (mid << 16u));
}

fn u64_mul(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
  let lo = mul32(a.y, b.y);
  return vec2<u32>(lo.x + a.x * b.y + a.y * b.x, lo.y);
}

fn u64_add(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
  let lo = a.y + b.y;
  return vec2<u32>(a.x + b.x + select(0u, 1u, lo < a.y), lo);
}

fn u64_neg(a: vec2<u32>) -> vec2<u32> { return u64_add(~a, vec2<u32>(0u, 1u)); }

// a >> k for 0 < k < 32
fn u64_shr(a: vec2<u32>, k: u32) -> vec2<u32> { return vec2<u32>(a.x >> k, (a.y >> k) | (a.x << (32u - k))); }

fn u64_le(a: vec2<u32>, b: vec2<u32>) -> bool { return a.x < b.x || (a.x == b.x && a.y <= b.y); }
fn u64_lt(a: vec2<u32>, b: vec2<u32>) -> bool { return a.x < b.x || (a.x == b.x && a.y < b.y); }

const GOLD = vec2<u32>(0x9E3779B9u, 0x7F4A7C15u);
const MIX1 = vec2<u32>(0xBF58476Du, 0x1CE4E5B9u);
const MIX2 = vec2<u32>(0x94D049BBu, 0x133111EBu);
const H0 = vec2<u32>(0x243F6A88u, 0x85A308D3u);

// plants.py _mix: splitmix64's finaliser
fn mix64(z0: vec2<u32>) -> vec2<u32> {
  var z = u64_mul(z0 ^ u64_shr(z0, 30u), MIX1);
  z = u64_mul(z ^ u64_shr(z, 27u), MIX2);
  return z ^ u64_shr(z, 31u);
}

// one link of plants.py _h's chain: mix((h ^ k) + GOLD)
fn hstep(h: vec2<u32>, k: vec2<u32>) -> vec2<u32> { return mix64(u64_add(h ^ k, GOLD)); }

// an integer key as numpy makes one: k.astype(np.int64).astype(np.uint64)
fn key_i(k: i32) -> vec2<u32> { return vec2<u32>(select(0u, 0xFFFFFFFFu, k < 0), bitcast<u32>(k)); }

// plants.py _u(h, stream) as its 53-bit integer: (mix(h + stream GOLD + MIX2)) >> 11
fn u53(h: vec2<u32>, stream: u32) -> vec2<u32> {
  let s = u64_add(u64_mul(vec2<u32>(0u, stream), GOLD), MIX2);
  return u64_shr(mix64(u64_add(h, s)), 11u);
}

// the uniform as a float32 (rounded)
fn u53f(k: vec2<u32>) -> f32 { return (f32(k.x) * 4294967296.0 + f32(k.y)) * 0x1p-53f; }

// u < p for u = k / 2^53 and a float32 p, exactly (k < p 2^53): p 2^53 is an integer for p >= 2^-29, compared as a u64
fn u53_lt(k: vec2<u32>, p: f32) -> bool {
  if (p >= 1.0) { return true; }
  if (!(p > 0.0)) { return false; }
  let bits = bitcast<u32>(p);
  let e = i32((bits >> 23u) & 0xFFu);
  if (e >= 97) {
    let mant = (bits & 0x7FFFFFu) | 0x800000u;
    let s = u32(e - 97);                     // p 2^53 = mant 2^s, s in 0..29
    var vhi = 0u;
    if (s > 0u) { vhi = mant >> (32u - s); }
    let v = vec2<u32>(vhi, mant << s);
    return u64_lt(k, v);
  }
  if (k.x != 0u || k.y >= 16777216u) { return false; }
  return f32(k.y) < p * 9007199254740992.0;
}

// -log1p(-u) for the uniform u = k / 2^53 (the Thomas offset's radius, the Weibull's age): a series below 1/2, the
// log of 1 - u made exactly from k above (where float32's log keeps its relative error)
fn neglog1m(k: vec2<u32>) -> f32 {
  if (k.x < 0x100000u) {                     // u < 1/2
    let t = u53f(k);
    var s = 1.0 / 26.0;
    for (var n = 25; n >= 1; n--) { s = 1.0 / f32(n) + t * s; }
    return t * s;
  }
  let m = u64_add(vec2<u32>(0x200000u, 0u), u64_neg(k));     // 2^53 - k, exact
  let one_minus = (f32(m.x) * 4294967296.0 + f32(m.y)) * 0x1p-53f;
  return -log(one_minus);
}

// cos and sin of 2 pi u for the uniform u = k / 2^53: the quadrant from k's integer bits, the rest in [-pi/4, pi/4]
// by Cephes' single-precision polynomials (an angle's own rounding stays float32's, not the built-ins' absolute bound)
fn cossin2pi(k: vec2<u32>) -> vec2<f32> {
  // q = round(4 u) = (k + 2^50) >> 51; r = k - q 2^51 (signed, |r| <= 2^50)
  let kk = u64_add(k, vec2<u32>(0x40000u, 0u));
  let q = kk.x >> 19u;                       // 0..4
  let r = u64_add(k, u64_neg(vec2<u32>(q << 19u, 0u)));
  var rf: f32;
  if ((r.x & 0x80000000u) != 0u) {
    let a = u64_neg(r);
    rf = -(f32(a.x) * 4294967296.0 + f32(a.y));
  } else {
    rf = f32(r.x) * 4294967296.0 + f32(r.y);
  }
  let x = rf * 0x1p-53f * 6.2831853071795864769;
  let z = x * x;
  let sn = x + x * z * (-1.6666654611e-1 + z * (8.3321608736e-3 + z * -1.9515295891e-4));
  let cs = 1.0 - 0.5 * z + z * z * (4.166664568298827e-2 + z * (-1.388731625493765e-3 + z * 2.443315711809948e-5));
  let qq = q & 3u;
  if (qq == 0u) { return vec2<f32>(cs, sn); }
  if (qq == 1u) { return vec2<f32>(-sn, cs); }
  if (qq == 2u) { return vec2<f32>(-cs, -sn); }
  return vec2<f32>(sn, -cs);
}

// log1p(x) for -1 < x <= 0 (the shade's crowns): a series for |x| < 1/2, else the log of 1 + x
fn log1p_neg(x: f32) -> f32 {
  if (x > -0.5) {
    let t = -x;
    var s = 1.0 / 26.0;
    for (var n = 25; n >= 1; n--) { s = 1.0 / f32(n) + t * s; }
    return -t * s;
  }
  return log(1.0 + x);
}

// ---------------------------------------------------------------------------------------------- positions ---

// i x c as (integer part, fraction in [0, 1]) for an integer i and a fixed-point c = C / 2^F (C a u64, F in 32..56,
// |i| C < 2^63): the 64-bit product's top bits are the integer part, its low F bits the fraction
fn fixmul(i: i32, C: vec2<u32>, F: u32) -> vec2<f32> {
  let m = u32(abs(i));
  let lo = mul32(m, C.y);
  var v = vec2<u32>(lo.x + m * C.x, lo.y);
  if (i < 0) { v = u64_neg(v); }
  let sh = F - 32u;
  let ip = bitcast<i32>(v.x) >> sh;
  var hl = 0u;
  if (sh > 0u) { hl = v.x & ((1u << sh) - 1u); }
  let fr = f32(hl) * pow2i(32 - i32(F)) + f32(v.y) * pow2i(-i32(F));
  return vec2<f32>(f32(ip), fr);
}

// 2^e exactly, for -126 <= e <= 127 (the built-in exp2 promises only a few ulp)
fn pow2i(e: i32) -> f32 { return bitcast<f32>(u32(127 + e) << 23u); }

// a coordinate (integer part, fraction) plus o metres, renormalised to a fraction in [0, 1)
fn coord_add(c: vec2<f32>, o: f32) -> vec2<f32> {
  let oi = floor(o);
  let t = c.y + (o - oi);
  let ti = floor(t);
  return vec2<f32>(c.x + oi + ti, t - ti);
}

// a - b along one axis, metres (a and b coordinates)
fn coord_sub(a: vec2<f32>, b: vec2<f32>) -> f32 { return (a.x - b.x) + (a.y - b.y); }

// the squared distance of two positions
fn pos_d2(a: vec4<f32>, b: vec4<f32>) -> f32 {
  let dx = coord_sub(a.xy, b.xy);
  let dy = coord_sub(a.zw, b.zw);
  return dx * dx + dy * dy;
}

// a coordinate as one float32 (what the spots file stores)
fn coord_f32(c: vec2<f32>) -> f32 { return c.x + c.y; }

// a coordinate divided by s: its integer part times a fixed-point reciprocal (W = 2^F / s, u64) plus its fraction
// times 1/s, as (integer part, fraction): the noise lattice and the level texels, without float32's loss at 10 km
fn coord_div(c: vec2<f32>, W: vec2<u32>, F: u32, inv: f32) -> vec2<f32> {
  return coord_add(fixmul(i32(c.x), W, F), c.y * inv);
}

// ------------------------------------------------------------------------- palettes.py's scatter noise ---
// value_noise (noise(), fbm()) and voronoi_cells (cells()): the numpy side of the mask language, as plants.py and
// dressing.py read it (the material reads the shader's noise instead: surface/noise.js).

fn hash2(ix: i32, iy: i32, seed: i32) -> f32 {
  var h = bitcast<u32>(ix) * 374761393u + bitcast<u32>(iy) * 668265263u + bitcast<u32>(seed) * 2147483647u;
  h = (h ^ (h >> 13u)) * 1274126177u;
  h = h ^ (h >> 16u);
  return f32(h & 0xFFFFFFu) / 16777215.0;
}

// palettes.value_noise(x, y, scale, seed, octaves, gain, stretch) at a position; W = 2^F / scale (u64), inv = 1 /
// scale. The octaves' x 2 + 17.3 and y 2 - 9.1 on (integer, fraction) lattice coordinates
fn value_noise(pos: vec4<f32>, W: vec2<u32>, F: u32, inv: f32, seed: i32, octaves: i32, gain: f32, stretch: f32) -> f32 {
  var gx = coord_div(pos.xy, W, F, inv);
  var gy = coord_div(pos.zw, W, F, inv);
  var tot = 0.0;
  var amp = 1.0;
  var norm = 0.0;
  for (var o = 0; o < octaves; o++) {
    let ix = i32(gx.x);
    let iy = i32(gy.x);
    let fx = gx.y;
    let fy = gy.y;
    let ux = fx * fx * fx * (fx * (fx * 6.0 - 15.0) + 10.0);
    let uy = fy * fy * fy * (fy * (fy * 6.0 - 15.0) + 10.0);
    let s = seed * 31 + o * 17;
    let v00 = hash2(ix, iy, s);
    let v10 = hash2(ix + 1, iy, s);
    let v01 = hash2(ix, iy + 1, s);
    let v11 = hash2(ix + 1, iy + 1, s);
    let v = (v00 * (1.0 - ux) + v10 * ux) * (1.0 - uy) + (v01 * (1.0 - ux) + v11 * ux) * uy;
    tot = tot + amp * v;
    norm += amp;
    amp *= gain;
    // x 2 + 17.3: 17 + 0.3 (numpy's float64 17.3 - 17 is 0.3 to float32); y 2 - 9.1: -10 + 0.9
    let tx = 2.0 * fx + 0.3;
    let ty = 2.0 * fy + 0.9;
    gx = vec2<f32>(2.0 * gx.x + 17.0 + floor(tx), tx - floor(tx));
    gy = vec2<f32>(2.0 * gy.x - 10.0 + floor(ty), ty - floor(ty));
  }
  let v = tot / norm;
  return clamp(0.5 + (v - 0.5) * stretch, 0.0, 1.0);
}

// Python's % of a non-negative divisor (the result's sign is the divisor's), without a negative operand
fn pymod(a: i32, m: i32) -> i32 {
  let r = abs(a) % m;
  if (a < 0 && r != 0) { return m - r; }
  return r;
}

// palettes.voronoi_cells(x, y, scale, seed[, z, z_stretch]): a random value per cell of a Voronoi partition; z the
// ground's height (metres) and zk its stretch (0: the 2D partition)
fn voronoi_cells(pos: vec4<f32>, W: vec2<u32>, F: u32, inv: f32, seed: i32, z: f32, zk: f32) -> f32 {
  let gx = coord_div(pos.xy, W, F, inv);
  let gy = coord_div(pos.zw, W, F, inv);
  let three = zk > 0.0;
  let gz = z * zk * inv;
  let ix = i32(gx.x);
  let iy = i32(gy.x);
  let iz = i32(floor(gz));
  var best = 3.4e38;
  var val = 0.0;
  var k0 = 0;
  var k1 = 0;
  if (three) { k0 = -1; k1 = 1; }
  for (var dk = k0; dk <= k1; dk++) {
    for (var dj = -1; dj <= 1; dj++) {
      for (var di = -1; di <= 1; di++) {
        let cx = ix + di;
        let cy = iy + dj;
        var d: f32;
        var v: f32;
        if (three) {
          let cz = iz + dk;
          let salt = pymod(cz * 7919, 104729);
          let px = f32(di) + hash2(cx, cy + salt, seed * 13 + 1);
          let py = f32(dj) + hash2(cx, cy + salt, seed * 13 + 2);
          let pz = f32(cz) + hash2(cx, cy + salt, seed * 13 + 4);
          d = (gx.y - px) * (gx.y - px) + (gy.y - py) * (gy.y - py) + (gz - pz) * (gz - pz);
          v = hash2(cx, cy + salt, seed * 13 + 3);
        } else {
          let px = f32(di) + hash2(cx, cy, seed * 13 + 1);
          let py = f32(dj) + hash2(cx, cy, seed * 13 + 2);
          d = (gx.y - px) * (gx.y - px) + (gy.y - py) * (gy.y - py);
          v = hash2(cx, cy, seed * 13 + 3);
        }
        if (d < best) {
          best = d;
          val = v;
        }
      }
    }
  }
  return val;
}

// plants.py _smooth and palettes' smoothstep: Hermite between e0 and e1, x >= e0 when the edges are equal
fn pl_smooth(e0: f32, e1: f32, x: f32) -> f32 {
  if (e1 == e0) { return select(0.0, 1.0, x >= e0); }
  let t = clamp((x - e0) / (e1 - e0), 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}
