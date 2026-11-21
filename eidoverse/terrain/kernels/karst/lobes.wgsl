// Port of the lobes of blender/eidoblend/terrain/solvers/karst.py evaluate() at f90c6fc, on G.smooth's lattice:
//     LOB = G.smooth(lambda X, Y: lobes_m * (noise2(X, Y, 130, salt + 101) + 0.45 * noise2(X, Y, 60, salt + 102))
//                    / 0.33, max(60, 2.5 cell)).astype(float32)
// numpy's float64 in double-float (karst/precise.wgsl): every tower's footprint is d = R - (re / stretch - LOB), read
// on its wall table, up to 57 m per metre steep at a foot's notch and dipping at tan 85 degrees under the plain, so
// the lobes' last float32 bits become the rock's millimetres. In float32 (karst/world.wgsl's world noise, within 6e-7
// of their 36 m range) they moved a foot's rock by up to 0.9 mm against numpy's. This kernel writes the lattice's
// values as double-floats; karst/bilinear_dd.wgsl reads them onto the subsamples and rounds once.

//! sampler gx rgba32f        per lattice column, row k (octave k = 0, 1): (cell, fraction hi, fraction lo, 0) of x / 130, x / 60
//! sampler gy rgba32f        per lattice row: the same of y
//! sampler salts r32ui       the octaves' salts (salt + 101, salt + 102)
//! image   outV rg32f        the lattice values (hi, lo)
//! uniform float uAmp        lobes_m (float64) as hi, lo
//! uniform float uAmpl
//! include karst/lib
//! include detail/exact
//! include karst/precise

const KDD_045 = vec2<f32>(0.44999998807907104, 1.1920929132713809e-8);
const KDD_033 = vec2<f32>(0.33000001311302185, -1.3113021779531664e-8);

fn octave(p: vec2<i32>, k: i32) -> vec2<f32> {
  let a = gx_at(vec2<i32>(p.x, k));
  let b = gy_at(vec2<i32>(p.y, k));
  return kdd_noise2(i32(a.x), i32(b.x), a.yz, b.yz, salts_at(vec2<i32>(k, 0)));
}

fn kmain(p: vec2<i32>) {
  let n = outV_size();
  if (!inside(p, n)) { return; }
  kprecise(n);
  // lobes_m * (n1 + 0.45 * n2) / 0.33, as Python groups it
  let s = kdd_add(octave(p, 0), kdd_mul(KDD_045, octave(p, 1)));
  let v = kdd_div(kdd_mul(vec2<f32>(u.uAmp, u.uAmpl), s), KDD_033);
  outV_store(p, vec4<f32>(v.x, v.y, 0.0, 0.0));
}
