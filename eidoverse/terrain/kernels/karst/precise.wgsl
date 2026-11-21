// Port of the rounding of blender/eidoblend/terrain/solvers/karst.py evaluate()'s tower loop at f90c6fc: numpy's
// float32 lines rounded as numpy rounds them, and its float64 lines (np.interp of the wall tables, the fluting's and
// the talus gate's periodic noise, the smoothsteps) carried in double-float and rounded to float32 once, as numpy's
// .astype(np.float32) does (`//! include karst/precise`, after `//! include detail/exact`).
//
// Why: the loop works in window-local float32 metres, and where the rock is steep in plan its last bit is amplified
// (a wall table rises up to 57 m per metre at a foot's notch, the buried rock dips at tan 85 degrees, the talus gate
// turns 140 m of cone per radian of azimuth): numpy's own float32 evaluate moves by up to 4e-5 of the bed's range
// against the same lines in float64 (tests/karst_coast/karst_window_floor.py measures its window floor). A float32
// port that rounds differently, by a few ulps per operation, lands as far from numpy's as numpy's lands from the
// exact value. So each operation is kept as numpy computes it:
//   kx(x)       every float32 result passed through exact() (detail/exact.wgsl, P12's), so the shader compiler
//               neither fuses a product into an add nor reassociates: numpy's ufuncs round each operation once
//   kdiv, ksqrt correctly rounded, as numpy's float32 division and sqrt are (IEEE); WGSL allows 2.5 ulp for x / y
//               and leaves sqrt to inverseSqrt's accuracy. The built-in's result is corrected once by the exact
//               remainder (Dekker's product): measured in float32 emulation from first guesses up to 3 ulp off,
//               3,000,000 of 3,000,000 quotients and all but 2 of 3,000,000 roots correctly rounded
//   katan2      numpy's float32 arctan2 (the C library's atan2f) is correctly rounded on 999,998 of 1,000,000
//               arguments (measured, numpy 2.3.4): computed here in double-float (the reduction to |u| <= tan(pi/32)
//               about k pi / 16, u - u^3 / 3 in double-float, the series' tail in float32: about 2^-37 relative) and
//               rounded once; measured in float32 emulation, 2,899,999 of 2,900,000 equal to the correctly rounded
//   kdd_*       double-float values (vec2: hi, lo with |lo| <= ulp(hi) / 2; about 44 bits) for numpy's float64 lines
// Every value here is finite and far from float32's overflow and underflow.

var<private> KZ: u32;

/** Call first in kmain with any field's size: the zero exact() needs. */
fn kprecise(n: vec2<i32>) { KZ = exact_zero(n); }

/** x as computed: numpy rounds each float32 operation once. */
fn kx(x: f32) -> f32 { return exact(x, KZ); }

// ---- error-free transformations: Knuth's two-sum, Dekker's split and product

fn k2sum(a: f32, b: f32) -> vec2<f32> {
  let s = kx(a + b);
  let bv = kx(s - a);
  let av = kx(s - bv);
  return vec2<f32>(s, kx(kx(a - av) + kx(b - bv)));
}

/** two-sum for |a| >= |b| */
fn kfast2sum(a: f32, b: f32) -> vec2<f32> {
  let s = kx(a + b);
  return vec2<f32>(s, kx(b - kx(s - a)));
}

fn ksplit(a: f32) -> vec2<f32> {
  let c = kx(4097.0 * a);
  let hi = kx(c - kx(c - a));
  return vec2<f32>(hi, kx(a - hi));
}

/** a * b = p.x + p.y exactly */
fn k2prod(a: f32, b: f32) -> vec2<f32> {
  let p = kx(a * b);
  let A = ksplit(a);
  let B = ksplit(b);
  let e = kx(kx(kx(kx(kx(A.x * B.x) - p) + kx(A.x * B.y)) + kx(A.y * B.x)) + kx(A.y * B.y));
  return vec2<f32>(p, e);
}

// ---- numpy's float32 division and square root: correctly rounded

fn kdiv(a: f32, b: f32) -> f32 {
  let q = kx(a / b);
  let p = k2prod(q, b);
  let r = kx(kx(a - p.x) - p.y);
  return kx(q + kx(r / b));
}

fn ksqrt(x: f32) -> f32 {
  if (!(x > 0.0)) { return sqrt(x); }
  let s = kx(sqrt(x));
  let p = k2prod(s, s);
  let r = kx(kx(x - p.x) - p.y);
  return kx(s + kx(r / kx(s + s)));
}

/** karst.py _smin(a, b, k) on float32 arrays and a float32 k, rounded as numpy rounds it */
fn ksmin_x(a: f32, b: f32, k: f32) -> f32 {
  if (k <= 0.0) { return min(a, b); }
  let hh = kdiv(max(kx(k - abs(kx(a - b))), 0.0), k);
  return kx(min(a, b) - kx(kx(hh * hh) * kx(k * 0.25)));
}

// ---- double-float: numpy's float64 lines

fn kdd(a: f32) -> vec2<f32> { return vec2<f32>(a, 0.0); }

fn kdd_add(a: vec2<f32>, b: vec2<f32>) -> vec2<f32> {
  let s = k2sum(a.x, b.x);
  let t = k2sum(a.y, b.y);
  let u = kfast2sum(s.x, kx(s.y + t.x));
  return kfast2sum(u.x, kx(u.y + t.y));
}

fn kdd_mul(a: vec2<f32>, b: vec2<f32>) -> vec2<f32> {
  let p = k2prod(a.x, b.x);
  return kfast2sum(p.x, kx(p.y + kx(kx(a.x * b.y) + kx(a.y * b.x))));
}

fn kdd_div(a: vec2<f32>, b: vec2<f32>) -> vec2<f32> {
  let q1 = kx(a.x / b.x);
  let r = kdd_add(a, -kdd_mul(kdd(q1), b));
  let q2 = kx(r.x / b.x);
  let r2 = kdd_add(r, -kdd_mul(kdd(q2), b));
  let q3 = kx(r2.x / b.x);
  return kdd_add(kfast2sum(q1, q2), kdd(q3));
}

fn kdd_abs(a: vec2<f32>) -> vec2<f32> { return select(a, -a, a.x < 0.0 || (a.x == 0.0 && a.y < 0.0)); }

// float64 constants as double-floats (hi = the float32 nearest, lo = the float32 nearest the rest)
const KDD_PI = vec2<f32>(3.1415927410125732, -8.742277657347586e-8);
const KDD_PI_2 = vec2<f32>(1.5707963705062866, -4.371138828673793e-8);
const KDD_2PI = vec2<f32>(6.2831854820251465, -1.7484555314695172e-7);
const KDD_THIRD = vec2<f32>(0.3333333432674408, -9.934107758624577e-9);
const KDD_TAN1 = vec2<f32>(0.1989123672246933, 1.5496470773257442e-10);      // tan(k pi / 16)
const KDD_TAN2 = vec2<f32>(0.4142135679721832, -5.5990883041090456e-9);
const KDD_TAN3 = vec2<f32>(0.6681786179542542, 1.9965044728564862e-8);
const KDD_PI16_1 = vec2<f32>(0.19634954631328583, -5.463923535842241e-9);    // k pi / 16
const KDD_PI16_2 = vec2<f32>(0.39269909262657166, -1.0927847071684482e-8);
const KDD_PI16_3 = vec2<f32>(0.5890486240386963, -1.4906100798128818e-9);
const KDD_PI16_4 = vec2<f32>(0.7853981852531433, -2.1855694143368964e-8);

/** np.arctan2(y, x) on float32: correctly rounded (numpy's, but for one argument in 500,000) */
fn katan2(y: f32, x: f32) -> f32 {
  let ax = abs(x);
  let ay = abs(y);
  let mx = max(ax, ay);
  let mn = min(ax, ay);
  if (!(mx > 0.0)) { return 0.0; }                  /* arctan2(0, +0): the only zero pair a subsample makes */
  // t = mn / mx in [0, 1], a double-float
  let th = kdiv(mn, mx);
  let p = k2prod(th, mx);
  let t = kfast2sum(th, kx(kx(kx(mn - p.x) - p.y) / mx));
  // atan(t) = k pi / 16 + atan(u), u = (t - c) / (1 + t c), c = tan(k pi / 16), |u| <= tan(pi / 32)
  let k = i32(clamp(floor(atan(t.x) * 5.092957973480225 + 0.5), 0.0, 4.0));
  var c = vec2<f32>(1.0, 0.0);
  var b = KDD_PI16_4;
  if (k == 1) { c = KDD_TAN1; b = KDD_PI16_1; }
  if (k == 2) { c = KDD_TAN2; b = KDD_PI16_2; }
  if (k == 3) { c = KDD_TAN3; b = KDD_PI16_3; }
  var u = t;
  if (k > 0) { u = kdd_div(kdd_add(t, -c), kdd_add(kdd(1.0), kdd_mul(t, c))); }
  let u2 = kdd_mul(u, u);
  let u3 = kdd_mul(u2, u);
  let x2 = u2.x;
  // the series' tail u^5 (1/5 - u^2/7 + u^4/9 - u^6/11 + u^8/13), float32 (under 2e-5 of the angle)
  let poly = kx(0.20000000298023224 - kx(x2 * kx(0.1428571492433548 - kx(x2 * kx(0.1111111119389534
      - kx(x2 * kx(0.09090909361839294 - kx(x2 * 0.07692307978868484))))))));
  var r = kdd_add(kdd_add(u, -kdd_mul(u3, KDD_THIRD)), kdd(kx(kx(u3.x * x2) * poly)));
  if (k > 0) { r = kdd_add(b, r); }
  if (ay > ax) { r = kdd_add(KDD_PI_2, -r); }
  if (x < 0.0) { r = kdd_add(KDD_PI, -r); }
  return select(r.x, -r.x, (bitcast<u32>(y) >> 31u) == 1u);
}

/** karst.py _noise1_periodic(s, period, salt) in float64: s a double-float lattice coordinate */
fn kdd_noise1p(s: vec2<f32>, period: i32, salt: u32) -> vec2<f32> {
  let P = max(period, 1);
  var fi = floor(s.x);
  if (fi == s.x && s.y < 0.0) { fi = fi - 1.0; }    /* floor of hi + lo */
  let f = k2sum(kx(s.x - fi), s.y);                  /* s - i: exact to the double-float's bits */
  let i = i32(fi);
  let i0 = ((i % P) + P) % P;                         /* np.mod: non-negative */
  let i1 = (((i + 1) % P) + P) % P;
  // the gradients _hash2(k, 0, salt) / 2^31 - 1: 32 bits, a double-float exactly
  let h0 = khash2(i0, 0, salt);
  let h1 = khash2(i1, 0, salt);
  let g0 = kfast2sum(kx(f32(h0 & 0xFFFFFF00u) * 4.656612873077393e-10 - 1.0), f32(h0 & 0xFFu) * 4.656612873077393e-10);
  let g1 = kfast2sum(kx(f32(h1 & 0xFFFFFF00u) * 4.656612873077393e-10 - 1.0), f32(h1 & 0xFFu) * 4.656612873077393e-10);
  let d0 = kdd_mul(g0, f);
  let d1 = kdd_mul(g1, kdd_add(f, kdd(-1.0)));
  // _fade(f) = f f f (f (f 6 - 15) + 10)
  let fd = kdd_mul(kdd_mul(kdd_mul(f, f), f), kdd_add(kdd_mul(f, kdd_add(kdd_mul(f, kdd(6.0)), kdd(-15.0))), kdd(10.0)));
  let v = kdd_add(d0, kdd_mul(kdd_add(d1, -d0), fd));
  return kdd_mul(kdd(2.0), v);
}

/** karst.py _smoothstep(a, b, x) in float64, x a double-float, a and (b - a) as numpy has them; rounded to float32 */
fn kdd_smoothstep(x: vec2<f32>, a: vec2<f32>, den: vec2<f32>) -> f32 {
  var t = kdd_div(kdd_add(x, -a), den);
  if (t.x < 0.0 || (t.x == 0.0 && t.y < 0.0)) { t = vec2<f32>(0.0, 0.0); }
  if (t.x > 1.0 || (t.x == 1.0 && t.y > 0.0)) { t = vec2<f32>(1.0, 0.0); }
  return kdd_mul(kdd_mul(t, t), kdd_add(kdd(3.0), -kdd_mul(kdd(2.0), t))).x;
}
