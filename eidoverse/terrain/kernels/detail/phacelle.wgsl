// phacelle.wgsl (`//! include detail/phacelle`, after `//! include noise`): Phacelle noise for the gully octave.
// Port of blender/eidoblend/terrain/solvers/detail.py phacelle_noise at f90c6fc (numpy, its oracle), which is
// Ekigar's phacelle_noise (src/nodes/phacelle.js, MIT; the technique is Rune Skovbo Johansen's Phacelle noise,
// runevision.com) on Blender's lattice: Ekigar's integer hash2 of the lattice cell plus an integer offset per seed and
// octave (kernels/noise.wgsl eido_hash2, bit for bit with numpy's hash2). Stripes run ALONG the direction d; `freq`
// stripes per lattice cell; returns (cos, sin, side x, side y). The surface bake's gully filter (the last wave) reads
// the same function.
//
// Coordinates. numpy evaluates px = X / lam in float64, 40 km from the origin as well as at it; in float32 the phase
// would go (a 6 m wavelength 40 km out is 6,700 lattice cells, an f32 there 5e-4 cells off: 3e-3 rad). So a lattice
// coordinate comes as an integer cell and a fraction: phacelle_coord() builds them from the level's cell (0, 0) in
// doubles on the CPU (solvers/detail.js gullyTable) and the cell's index in integer arithmetic, so the fraction keeps
// about 1e-7 of a lattice cell anywhere.

const TAU: f32 = 6.28318530717959;

struct LatticeAt { c: vec2<i32>, f: vec2<f32> }

/** Cell p's lattice coordinate as (integer cell, fraction): cell (0, 0)'s centre at base + frac (base an integer,
 * frac in [0, 1)), and the step per cell cell / lam split as num / 4096 + lo (num an integer, |lo| <= 2^-13): p num
 * is an exact integer, so its whole part and its remainder are exact, and p lo is small. */
fn phacelle_coord(p: vec2<i32>, base: vec2<i32>, frac: vec2<f32>, num: i32, lo: f32) -> LatticeAt {
  let a = p * num;
  let whole = a >> vec2<u32>(12u, 12u);
  let part = vec2<f32>(a & vec2<i32>(4095, 4095)) * (1.0 / 4096.0);
  let f = frac + part + vec2<f32>(p) * lo;
  let fl = floor(f);
  return LatticeAt(base + whole + vec2<i32>(fl), f - fl);
}

/** detail.py phacelle_noise at lattice cell pc + fraction pf (the numpy's floor(px) and px - floor(px)), with the
 * direction d per cell and the lattice offset lo: (cos, sin, side x, side y). */
fn phacelle_noise(pc: vec2<i32>, pf: vec2<f32>, d: vec2<f32>, freq: f32, offset: f32, normalization: f32,
                  lo: vec2<i32>) -> vec4<f32> {
  let sdx = -d.y * freq * TAU;
  let sdy = d.x * freq * TAU;
  let off = offset * TAU;
  var phx = 0.0;
  var phy = 0.0;
  var wsum = 0.0;
  for (var i = -1; i < 3; i++) {
    for (var j = -1; j < 3; j++) {
      let r = eido_hash2(pc.x + i + lo.x, pc.y + j + lo.y);
      let vx = pf.x - f32(i) - r.x * 0.5;
      let vy = pf.y - f32(j) - r.y * 0.5;
      let w = max(0.0, exp((vx * vx + vy * vy) * -2.0) - 0.01111);
      wsum += w;
      let wave = vx * sdx + vy * sdy + off;
      phx += cos(wave) * w;
      phy += sin(wave) * w;
    }
  }
  let ix = phx / wsum;
  let iy = phy / wsum;
  let mag = max(1.0 - normalization, sqrt(ix * ix + iy * iy));
  return vec4<f32>(ix / mag, iy / mag, sdx, sdy);
}
