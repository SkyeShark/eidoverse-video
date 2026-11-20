// Port of the numpy world functions of blender/eidoblend/terrain/solvers/karst.py at f90c6fc (_pcg, _hash2, _fade,
// noise2, _noise1_periodic, pinnacles, _smoothstep, _smin, cone_profile), as WGSL the karst kernels share
// (`//! include karst/lib`). numpy evaluates them in float64; here they are float32, with one difference of method:
// a world coordinate reaches a kernel already divided by the wavelength and split, on the CPU in doubles, into its
// integer lattice cell and its fraction (solvers/karst.js latticeTables), so the fraction is exact to float32 however
// far from the origin the level lies. The hash is integer-exact (numpy's uint32 arithmetic).

// np.cos / np.sin of k (2 pi / 16), numpy's float64 values rounded to float32 (karst.py _GX16, _GY16)
const KGX16 = array<f32, 16>(1.0, 0.9238795325112867, 0.7071067811865476, 0.38268343236508984, 6.123233995736766e-17,
    -0.3826834323650897, -0.7071067811865475, -0.9238795325112867, -1.0, -0.9238795325112868, -0.7071067811865477,
    -0.38268343236509034, -1.8369701987210297e-16, 0.38268343236509, 0.7071067811865474, 0.9238795325112865);
const KGY16 = array<f32, 16>(0.0, 0.3826834323650898, 0.7071067811865476, 0.9238795325112867, 1.0, 0.9238795325112867,
    0.7071067811865476, 0.3826834323650899, 1.2246467991473532e-16, -0.38268343236508967, -0.7071067811865475,
    -0.9238795325112865, -1.0, -0.9238795325112866, -0.7071067811865477, -0.3826834323650904);
const KPI: f32 = 3.141592653589793;
const KTWO_PI: f32 = 6.283185307179586;
const KNEG: f32 = -1.0e9;                 // karst.py NEG: no rock here

// _hash2(ix, iy, salt): pcg(a + pcg(b + salt)) on uint32 (common.wgsl pcg is karst.py's _pcg)
fn khash2(ix: i32, iy: i32, salt: u32) -> u32 {
  return pcg(bitcast<u32>(ix) + pcg(bitcast<u32>(iy) + salt));
}

fn kfade(t: f32) -> f32 { return t * t * t * (t * (t * 6.0 - 15.0) + 10.0); }

// noise2 at a lattice point given as integer cells (ix, iy) and fractions (fx, fy) in [0, 1): about -1..1
fn knoise2(ix: i32, iy: i32, fx: f32, fy: f32, salt: u32) -> f32 {
  let k00 = khash2(ix, iy, salt) & 15u;
  let k10 = khash2(ix + 1, iy, salt) & 15u;
  let k01 = khash2(ix, iy + 1, salt) & 15u;
  let k11 = khash2(ix + 1, iy + 1, salt) & 15u;
  let n00 = KGX16[k00] * fx + KGY16[k00] * fy;
  let n10 = KGX16[k10] * (fx - 1.0) + KGY16[k10] * fy;
  let n01 = KGX16[k01] * fx + KGY16[k01] * (fy - 1.0);
  let n11 = KGX16[k11] * (fx - 1.0) + KGY16[k11] * (fy - 1.0);
  let ux = kfade(fx);
  let uy = kfade(fy);
  let a = n00 + (n10 - n00) * ux;
  let b = n01 + (n11 - n01) * ux;
  return (a + (b - a) * uy) * 1.41;
}

// pinnacles at a lattice point of spacing-sized cells (ix, iy) + (fx, fy): one knob per cell, jittered inside it,
// its apex 0.55-1 high by its own hash, falling linearly to 0 at 0.75 spacing from it; the highest knob wins. 0..1
fn kpinnacles(ix: i32, iy: i32, fx: f32, fy: f32, salt: u32) -> f32 {
  var best = 0.0;
  var first = true;
  for (var dj = -1; dj <= 1; dj++) {
    for (var di = -1; di <= 1; di++) {
      let hsh = khash2(ix + di, iy + dj, salt);
      let jx = f32(hsh & 0xFFFFu) / 65535.0;
      let jy = f32((hsh >> 16u) & 0xFFFFu) / 65535.0;
      let top = 0.55 + 0.45 * (f32(pcg(hsh) & 0xFFFFu) / 65535.0);
      let ex = fx - (f32(di) + 0.1 + 0.8 * jx);
      let ey = fy - (f32(dj) + 0.1 + 0.8 * jy);
      let d = sqrt(ex * ex + ey * ey);
      let v = top * clamp(1.0 - d / 0.75, 0.0, 1.0);
      if (first) { best = v; first = false; } else { best = max(best, v); }
    }
  }
  return best;
}

// _noise1_periodic(s, period, salt): 1-D gradient noise of s >= 0, periodic with `period` cells; about -1..1. The
// lattice gradients g[k] = _hash2(k, 0, salt) / 2^31 - 1
fn knoise1p(s: f32, period: i32, salt: u32) -> f32 {
  let P = max(period, 1);
  let fi = floor(s);
  let f = s - fi;
  let i = i32(fi);
  let i0 = i % P;                         /* s >= 0 here: % of non-negative numbers only (core/gpu.js) */
  let i1 = (i + 1) % P;
  let g0 = f32(khash2(i0, 0, salt)) / 2147483648.0 - 1.0;
  let g1 = f32(khash2(i1, 0, salt)) / 2147483648.0 - 1.0;
  let d0 = g0 * f;
  let d1 = g1 * (f - 1.0);
  return 2.0 * (d0 + (d1 - d0) * kfade(f));
}

fn ksmoothstep(a: f32, b: f32, x: f32) -> f32 {
  let t = clamp((x - a) / (b - a), 0.0, 1.0);
  return t * t * (3.0 - 2.0 * t);
}

// _smin(a, b, k): min(a, b) where they differ by more than k, a C1 blend within k
fn ksmin(a: f32, b: f32, k: f32) -> f32 {
  if (k <= 0.0) { return min(a, b); }
  let hh = max(k - abs(a - b), 0.0) / k;
  return min(a, b) - hh * hh * (k * 0.25);
}
