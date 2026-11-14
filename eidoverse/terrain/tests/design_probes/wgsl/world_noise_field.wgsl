// world_noise_field: KERNEL_FIELD + GLSL_NOISE of blender/eidoblend/terrain/core/world_noise.py in WGSL (Ekigar's
// integer lattice hash bit for bit; the term table is built on the CPU from the field spec, as field_gpu builds it)
//! sampler terms     two texels per lattice term: (mode, 1/w, amp, period), (base x, base y, frac x, frac y)
//! sampler disp      x, y: the cell's displacement in metres (a warp), zero when unwarped
//! image   outF r32f
//! uniform int uTerms
//! uniform float uCell
//! uniform float uConst

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

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let local = (vec2<f32>(p) + 0.5) * u.uCell + disp_at(p).xy;
  var acc = u.uConst;
  for (var t = 0; t < u.uTerms; t++) {
    let a = terms_at(vec2<i32>(2 * t, 0));
    let b = terms_at(vec2<i32>(2 * t + 1, 0));
    let lc = b.zw + local * a.y;
    let fl = floor(lc);
    let v = eido_lattice(vec2<i32>(b.xy) + vec2<i32>(fl), lc - fl, i32(a.w));
    acc += a.z * select(v, abs(v), a.x > 0.5);
  }
  outF_store(p, vec4<f32>(acc, 0.0, 0.0, 0.0));
}
