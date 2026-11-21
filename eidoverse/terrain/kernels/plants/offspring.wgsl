// Port of numpy code of blender/eidoblend/terrain/build/plants.py at f9fba8c, as a GPU kernel.
// plants/offspring: plants.py _candidates' plants (blender/eidoblend/terrain/build/plants.py at f9fba8c): per cluster
// centre, its offspring in order, ho = _h(hp, ok); a radius min(sigma sqrt(-2 log1p(-_u(ho, 6))), 3 sigma) and an
// angle 2 pi _u(ho, 7) about the centre; the age and height of _age_size from the centre's draw _u(hp, 4) (a stand
// shares an age) and the plant's own _u(ho, 8); the tone 0.6 _u(hp, 9) + 0.4 _u(ho, 10). Plant k of a centre goes to
// slot offs[centre] + k.
//
// A candidate's record (16 numbers): 0-3 xi, xf, yi, yf; 4-5 id (ho: hi, lo); 6 age; 7 size (the height, metres);
// 8 tone; 9 the path distance to the focus; 10 seeded (an `around` candidate); 11 r (the hard-core radius); 12-13
// the mark's 53-bit integer (hi, lo); 14 the finest level holding it; 15 home. Floats as their bits. This kernel
// writes 0-8 and zeroes the rest; plants/prefilter and plants/thin fill them.
//! include plants/lib
//! sampler par r32ui     the centres' records (plants/parents)
//! sampler offs r32ui    per centre: the offspring of the centres before it (an exclusive scan)
//! image   outC r32ui    the candidates' records, 16 numbers each
//! uniform vec4  uAge    the Weibull's shape and scale, the stand's share, -log1p(-(1 - 1e-12))
//! uniform ivec2 uClip   floor((1 - 1e-12) 2^53) (hi, lo as int bits): plants.py's min(u, 1 - 1e-12)
//! uniform vec4  uSize   size_m (min, max), sigma_m, 1 - exp(-3)
//! uniform int   uCount  the centres

// -expm1(x) for x <= 0: a series near 0 (no cancellation), 1 - exp(x) farther
fn one_minus_exp(x: f32) -> f32 {
  if (x > -0.5) {
    var s = 1.0;
    for (var n = 12; n >= 2; n--) { s = 1.0 + x * s / f32(n); }
    return -x * s;
  }
  return 1.0 - exp(x);
}

// plants.py _age_size's w(u) = scale (-log1p(-min(u, 1 - 1e-12)))^(1 / shape)
fn weibull(k: vec2<u32>) -> f32 {
  let clip = vec2<u32>(bitcast<u32>(u.uClip.x), bitcast<u32>(u.uClip.y));
  var t: f32;
  if (u64_lt(clip, k)) { t = u.uAge.w; } else { t = neglog1m(k); }
  if (!(t > 0.0)) { return 0.0; }
  return u.uAge.y * exp(log(t) / u.uAge.x);
}

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let o8 = 8u * u32(i);
  let n = par_b[o8 + 6u];
  if (n == 0u) { return; }
  let px = vec2<f32>(bitcast<f32>(par_b[o8]), bitcast<f32>(par_b[o8 + 1u]));
  let py = vec2<f32>(bitcast<f32>(par_b[o8 + 2u]), bitcast<f32>(par_b[o8 + 3u]));
  let hp = vec2<u32>(par_b[o8 + 4u], par_b[o8 + 5u]);
  let h1 = hstep(H0, hp);
  let wStand = weibull(u53(hp, 4u));
  let toneStand = 0.6 * u53f(u53(hp, 9u));
  let sig = u.uSize.z;
  let base = offs_b[i];
  for (var k = 0u; k < n; k++) {
    let ho = hstep(h1, vec2<u32>(0u, k));
    let rr = min(sig * sqrt(2.0 * neglog1m(u53(ho, 6u))), 3.0 * sig);
    let cs = cossin2pi(u53(ho, 7u));
    let x = coord_add(px, rr * cs.x);
    let y = coord_add(py, rr * cs.y);
    let kk = u.uAge.z;
    let age = clamp(kk * wStand + (1.0 - kk) * weibull(u53(ho, 8u)), 0.02, 1.0);
    let grow = one_minus_exp(-3.0 * age) / u.uSize.w;
    let size = u.uSize.x + (u.uSize.y - u.uSize.x) * grow;
    let tone = toneStand + 0.4 * u53f(u53(ho, 10u));
    let o = 16u * (base + k);
    outC_b[o] = bitcast<u32>(x.x);
    outC_b[o + 1u] = bitcast<u32>(x.y);
    outC_b[o + 2u] = bitcast<u32>(y.x);
    outC_b[o + 3u] = bitcast<u32>(y.y);
    outC_b[o + 4u] = ho.x;
    outC_b[o + 5u] = ho.y;
    outC_b[o + 6u] = bitcast<u32>(age);
    outC_b[o + 7u] = bitcast<u32>(size);
    outC_b[o + 8u] = bitcast<u32>(tone);
    for (var z = 9u; z < 16u; z++) { outC_b[o + z] = 0u; }
  }
}
