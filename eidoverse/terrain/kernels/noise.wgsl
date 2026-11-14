// Port of blender/eidoblend/terrain/core/world_noise.py at f90c6fc: GLSL_NOISE, Ekigar's integer lattice noise, one
// for one. A kernel that needs it declares `//! include noise` (core/gpu.js prefixes this file), as the Blender
// kernels have GLSL_NOISE substituted (world_noise_field, solvers/detail.py breakup_source()).
//
// eido_hash2 is Ekigar's hash2 on integer lattice cells, bit for bit (measured: the design probes); its gradient
// f32(h & 0xFFFF) * (1 / 32767.5) - 1 may contract to a fused multiply-add and so differ from numpy in the last bits
// (PORT_PLAN.md 2.3). eido_pmod is the exact floor modulo (WGSL's % of a negative number is not, here). Lattice
// coordinates come as an integer cell and a float32 fraction, built on the CPU in float64 (world_noise.js
// leafTerms), so float32 keeps 1e-7 of a cell at any distance from the origin.

fn eido_hash2(ix: i32, iy: i32) -> vec2<f32> {
  let wx = u32(ix + 8388608);
  let wy = u32(iy + 8388608);
  var h = (wx * 0x27d4eb2du) ^ (wy * 0x85ebca6bu);
  h ^= h >> 15u;
  h *= 0x2c1b3c6du;
  h ^= h >> 13u;
  h *= 0x297a2d39u;
  h ^= h >> 16u;
  return vec2<f32>(f32(h & 0xFFFFu), f32(h >> 16u)) * (1.0 / 32767.5) - 1.0;
}

fn eido_pmod(i: i32, p: i32) -> i32 {
  let q = i32(floor(f32(i) / f32(p)));
  var r = i - p * q;
  if (r < 0) { r += p; }
  if (r >= p) { r -= p; }
  return r;
}

// Ekigar's noised value at lattice cell ic + fraction f, wrapping over p cells when p > 0
fn eido_lattice(ic: vec2<i32>, f: vec2<f32>, p: i32) -> f32 {
  var ix0 = ic.x;
  var ix1 = ic.x + 1;
  var iy0 = ic.y;
  var iy1 = ic.y + 1;
  if (p > 0) { ix0 = eido_pmod(ix0, p); ix1 = eido_pmod(ix1, p); iy0 = eido_pmod(iy0, p); iy1 = eido_pmod(iy1, p); }
  let uu = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  let ga = eido_hash2(ix0, iy0);
  let gb = eido_hash2(ix1, iy0);
  let gc = eido_hash2(ix0, iy1);
  let gd = eido_hash2(ix1, iy1);
  let va = ga.x * f.x + ga.y * f.y;
  let vb = gb.x * (f.x - 1.0) + gb.y * f.y;
  let vc = gc.x * f.x + gc.y * (f.y - 1.0);
  let vd = gd.x * (f.x - 1.0) + gd.y * (f.y - 1.0);
  let q = va - vb - vc + vd;
  return va + uu.x * (vb - va) + uu.y * (vc - va) + uu.x * uu.y * q;
}
