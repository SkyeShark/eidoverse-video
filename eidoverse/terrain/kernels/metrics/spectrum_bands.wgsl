// Port of blender/eidoblend/terrain/core/metrics.py at f90c6fc: radial_spectrum's bands: the power |F|^2 of every
// rfft2 coefficient summed and counted per log-spaced band of wavenumber (np.digitize, np.bincount with weights).
//
// The band of a coefficient is decided in integers, so no coefficient changes band by a float32 rounding. With
// jj = min(j, ny - j) (np.fft.fftfreq's magnitude) and column i (np.fft.rfftfreq), k^2 = (jj / (ny c))^2 +
// (i / (nx c))^2, so m = jj^2 a + i^2 b with a = (nx / g)^2 and b = (ny / g)^2 (g their greatest common divisor) is
// k^2 times a constant, and edges[t] <= k < edges[t + 1] is M[t] <= m < M[t + 1] with M[t] = ceil of the edge's
// square times that constant, computed in doubles by core/metrics.js. m can pass 32 bits on a field that is not
// square, so it is kept as two words.
//
// Two modes over one set of bindings:
//   0  outF[row j, band t] = (the sum of |F|^2 over the row's coefficients in band t, their count)
//   1  outF[0, band t] = (the sum over the rows of mode 0's sums, of its counts); `src` is mode 0's output. The
//      rows are summed in 64 blocks, then the blocks: a float32 sum in a fixed order, the same on every run.
//! include prims/lib
//! sampler src              mode 0: the rfft2 coefficients (rg32f: re, im), ny rows of nx / 2 + 1; mode 1: mode 0's
//! sampler edges r32ui      M[t] as two words (high, low), t = 0 .. bands: a list of 2 (bands + 1) items
//! image   outF rg32f       mode 0: ny rows of `bands` columns; mode 1: one row
//! uniform int uMode
//! uniform int uNy          the field's rows
//! uniform int uA           (nx / g)^2
//! uniform int uB           (ny / g)^2

// x * y as (high, low) words
fn mul64(x: u32, y: u32) -> vec2<u32> {
  let x0 = x & 0xFFFFu;
  let x1 = x >> 16u;
  let y0 = y & 0xFFFFu;
  let y1 = y >> 16u;
  let w0 = x0 * y0;
  let t = x1 * y0 + (w0 >> 16u);
  let w1 = (t & 0xFFFFu) + x0 * y1;
  return vec2<u32>(x1 * y1 + (t >> 16u) + (w1 >> 16u), (w1 << 16u) | (w0 & 0xFFFFu));
}

fn add64(a: vec2<u32>, b: vec2<u32>) -> vec2<u32> {
  let lo = a.y + b.y;
  var hi = a.x + b.x;
  if (lo < a.y) { hi += 1u; }
  return vec2<u32>(hi, lo);
}

// a >= b
fn ge64(a: vec2<u32>, b: vec2<u32>) -> bool { return a.x > b.x || (a.x == b.x && a.y >= b.y); }

fn kmain(p: vec2<i32>) {
  let no = outF_size();
  if (!inside(p, no)) { return; }
  let ns = src_size();
  if (u.uMode == 1) {
    var part: array<f32, 64>;
    var cnt = 0.0;
    let per = (ns.y + 63) / 64;
    for (var k = 0; k < 64; k++) {
      var s = 0.0;
      for (var j = k * per; j < min((k + 1) * per, ns.y); j++) {
        let v = src_at(vec2<i32>(p.x, j));
        s += v.x;
        cnt += v.y;
      }
      part[k] = s;
    }
    var tot = 0.0;
    for (var k = 0; k < 64; k++) { tot += part[k]; }
    outF_store(p, vec4<f32>(tot, cnt, 0.0, 0.0));
    return;
  }
  let lo = vec2<u32>(edges_b[2 * p.x], edges_b[2 * p.x + 1]);
  let hi = vec2<u32>(edges_b[2 * p.x + 2], edges_b[2 * p.x + 3]);
  let jj = u32(min(p.y, u.uNy - p.y));
  let base = mul64(jj * jj, u32(u.uA));
  var sum = 0.0;
  var cnt = 0.0;
  for (var i = 0; i < ns.x; i++) {
    let m = add64(base, mul64(u32(i * i), u32(u.uB)));
    if (ge64(m, lo) && !ge64(m, hi)) {
      let f = src_at(vec2<i32>(i, p.y));
      sum += f.x * f.x + f.y * f.y;
      cnt += 1.0;
    }
  }
  outF_store(p, vec4<f32>(sum, cnt, 0.0, 0.0));
}
