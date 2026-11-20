// Port of the inline kernel STRATA_WEATHER ('strata_weather') of blender/eidoblend/terrain/solvers/strata.py at
// f90c6fc.
//
// Transcribed statement for statement from the GLSL source in strata.py (PORT_PLAN.md 3.3: an inline kernel becomes
// a file of the same name); the `//!` header is the GLSL's, unchanged. Blender's source is the header, then
// FACIES_GLSL, then the body: FACIES_GLSL is kernels/strata/facies.wgsl here, prefixed by `//! include strata/facies`
// (core/gpu.js, PORT_PLAN.md 4.2). The other changes are WGSL's: texelFetch(x, q, 0) is x_at(q), imageStore is
// *_store, textureSize is st_size(), a uniform uX is u.uX, neighbour()'s `out` argument is a pointer, `?:` is an if,
// and take()'s argument is copied into a local (WGSL parameters are not assignable).
//
// One forced deviation, as in kernels/strata_cell.wgsl (whose header has the measurement): zs passes through exact()
// (`//! include detail/exact`), so this machine's shader compiler cannot fold h - zoff into the table coordinate
// (zs - uTZ0) / uTDz in another order; at a contact of the column the K factor jumps between neighbouring 0.5 m
// entries, and one float32 step of the coordinate there moves the factor by about 1e-4 of the jump.
//
// Weathering (the scarp-retreat process): exposed rock wears back at a rate set by its layer and the slope, whatever
// drains across it. The stream-power term needs drainage area, so on hillslopes it is weak: a weak layer once at its
// threshold angle never retreated, the cliffs above it never failed, and no bench widened (the Esplanade platform is
// 45 % of Toroweap's tile). Here a cell lowers by
//     E = uW f (K / uK0) min(G / uS0, uSat),   f = the column's K factor at its zs (loose cover: uLoose)
// G the upwind gradient magnitude (strata_threshold's), never below its lowest neighbour (no pits). Linear in G (uSat
// large, the default) it is a level-set motion: every contour retreats uW f / uS0 metres a year horizontally, at any
// slope, in every direction and at every cell size. (Saturated at G = uS0, uSat 1, a cliff cell lowered at a fixed
// rate whatever its height, so a cliff retreated a cell per (height / rate): faster on coarse levels, and faster
// where the grid made its step one cell (axis-aligned) than two (diagonal): the walls ran in straight 0- and
// 45-degree segments.) Shale under a cliff wears back fast, the cliff above fails over it (the composite threshold),
// the strong bed below stays a bench; gentle ground barely wears (the plateau and the benches stay flat). The fine
// debris leaves (suspended load). Twin: solvers/strata.py strata_weather.
//! sampler st     x: h (m); y, z, w carried
//! sampler zoff   x: z - zs (m)
//! sampler ctab   w: the column's K factor (1 row of uTN texels from uTZ0 every uTDz metres)
//! sampler par    y: K, the erodibility field (its noise varies the weathering alike)
//! sampler pin    x: pin_w, y: pin_h
//! sampler mk     x: wear, y: deposit, z: talus, w: loose thickness (m)
//! image   outS rgba32f
//! image   outM rgba32f
//! uniform float uDx
//! uniform float uDt
//! uniform float uW      lowering rate (m/yr) of K-factor-1 rock on a slope of uS0 or steeper
//! uniform float uS0     tan of the slope at which the rate is uW
//! uniform float uSat    the slope term's cap, G / uS0 <= uSat (large: linear; 1: the old saturated law)
//! uniform float uK0     the stage's K: the field's noise is K / uK0
//! uniform float uWl     lowering rate (m/yr) of loose cover: debris washes away
// (on the refining passes the rock rate is off and only uWl runs, so failed debris does not drape the cliffs below)
//! uniform float uAc     the drainage-area boost: x (1 + uAc min(sqrt(A / 1e5 m^2), 30) r), A = st.y
//! uniform float uAs0    r: 0 at this gradient (tan) and below ...
//! uniform float uAs1    ... 1 at this one and above: runoff gathering at a scarp (amphitheatres, a fraying
// escarpment) speeds its retreat; on gentle ground (benches, a desert floor) the gathered runoff is the stream-power
// incision's, not the scarp's (boosted there, every wash lowered its floor into a valley: Monument Valley's floor
// sank 60 m into the Cedar Mesa sandstone it is stripped to, and lost its westward rise)
//! uniform float uTZ0
//! uniform float uTDz
//! uniform int uTN
//! uniform vec3 uLv      the level: x0, y0, cell (m), for the cell's world position
//! uniform vec4 uFacW    the facies (strength, horizontal and vertical wavelength m, seed; strength 0: off): the
// rock's rate x exp(-strength facies_noise), so weak facies wear back into alcoves and strong ones stand as buttresses
//! uniform int uBound
//! include strata/facies
//! include detail/exact

fn axis_h(p: vec2<i32>, k: i32, n: vec2<i32>, h: f32) -> f32 {
  var q: vec2<i32>;
  if (neighbour(p, k, n, u.uBound, &q)) { return st_at(q).x; }
  return h;
}
/* q >= 0 metres taken off the top of the layers m: deposit, then talus, then other loose cover, then rock (wear) */
fn take(m0: vec4<f32>, q: f32) -> vec4<f32> {
  var m = m0;
  let other = max(m.w - m.y - m.z, 0.0);
  var r = q;
  var a = min(r, m.y);
  m.y -= a;
  r -= a;
  a = min(r, m.z);
  m.z -= a;
  r -= a;
  r -= min(r, other);
  m.w = max(m.w - (q - r), 0.0);
  m.x += r;
  return m;
}

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let c = st_at(p);
  let h = c.x;
  let gx = max(h - min(axis_h(p, 3, n, h), axis_h(p, 4, n, h)), 0.0);
  let gy = max(h - min(axis_h(p, 1, n, h), axis_h(p, 6, n, h)), 0.0);
  let G = sqrt(gx * gx + gy * gy) / u.uDx;
  var hlow = h;
  for (var k = 0; k < 8; k++) {
    var q: vec2<i32>;
    if (neighbour(p, k, n, u.uBound, &q)) { hlow = min(hlow, st_at(q).x); }
  }
  let zs = exact(h - zoff_at(p).x, exact_zero(n));
  let t = clamp((zs - u.uTZ0) / u.uTDz, 0.0, f32(u.uTN - 1));
  let i0 = min(i32(floor(t)), u.uTN - 2);
  var kf = mix(ctab_at(vec2<i32>(i0, 0)).w, ctab_at(vec2<i32>(i0 + 1, 0)).w, t - f32(i0));
  var m = mk_at(p);
  let w = clamp(max(m.w, 0.0), 0.0, 1.0);
  if (u.uFacW.x > 0.0) { kf *= exp(-u.uFacW.x * facies_noise(world_xy(p, u.uLv), zs, u.uFacW)); }
  let rate = mix(u.uW * kf, u.uWl, w);
  let ramp = clamp((G - u.uAs0) / max(u.uAs1 - u.uAs0, 1e-6), 0.0, 1.0);
  let boost = 1.0 + u.uAc * min(sqrt(max(c.y, 0.0) / 1e5), 30.0) * ramp;
  let E = rate * (par_at(p).y / u.uK0) * min(G / u.uS0, u.uSat) * boost;
  var hn = max(h - u.uDt * E, min(h, hlow));
  m = take(m, h - hn);
  if (u.uBound == BOUND_PINNED) {
    let pn = pin_at(p);
    let hp = pin_apply(hn, pn.x, pn.y);
    let d = hp - hn;
    if (d >= 0.0) {
      m.y += d;
      m.w += d;
    } else {
      m = take(m, -d);
    }
    hn = hp;
  }
  outS_store(p, vec4<f32>(hn, c.y, c.z, c.w));
  outM_store(p, m);
}
