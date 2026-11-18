// Port of blender/eidoblend/terrain/kernels/breakup.glsl at f90c6fc.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2); the `//!` header is the GLSL's, unchanged,
// with one line added: `//! include noise`, which prefixes kernels/noise.wgsl (Ekigar's lattice noise, ported by
// the core inputs package) where the GLSL has `/*__WORLD_NOISE__*/` and solvers/detail.py breakup_source()
// substitutes core/world_noise.GLSL_NOISE (PORT_PLAN.md 4.2: the runner's include is that substitution). The other
// changes are WGSL's: texelFetch(terms, ivec2(..), 0) is terms_at(vec2<i32>(..)), imageStore is outB_store,
// imageSize is outB_size(), uniforms are u.<name>, and int() / ivec2() are i32() / vec2<i32>() (both truncate toward
// zero, as GLSL's do).
/* breakup: rock strength in world space (design section 4.12), one dispatch per level. Its numpy twin is
   solvers/detail.py `breakup`. solvers/detail.py prefixes core/world_noise.GLSL_NOISE (Ekigar's lattice noise, bit
   for bit with numpy) after these declarations.

   The term table (three texels per term, built on the CPU per level) holds lattice terms evaluated at world metres:
       texel 0: (mode, a_s, width, a_d)     a_s: amplitude in the strength R; a_d: amplitude in the relief D (metres)
       texel 1: (base x, base y, frac x, frac y)   the lattice cell and fraction of the level's origin (float64 on the
                                                   CPU, so float32 keeps sub-millimetre precision far from (0, 0))
       texel 2: (m00, m01, m10, m11)        lattice coordinates per metre of offset from the origin: a rotation and a
                                            stretch, so joint sets run along their strike
   modes: 0  an isotropic octave (the 50, 15 and 5 m scales):   R += a_s n, D += a_d n
          1  a joint line (stretched along its strike): line = max(0, 1 - |n| / width)^2, kept for the next term
          2  the joint's segments: line *= smoothstep(-width, width, n); R -= a_s line, D -= a_d line
   Bedding planes (uBedAmpS / uBedAmpD > 0): weak beds every uBedSpacing metres of stratigraphic height
   zs = h - (uDipX x + uDipY y) - uBedZ0, each uBedWidth thick: R -= a line, D -= a line.

   Out: x R (strength, about -1..1, + strong), y the erodibility factor kfac = 2^(-uKOct R), z the rock threshold
   tan(clamp(uRockDeg + uSpreadDeg R, uMinDeg, uMaxDeg)), w D (relief in metres for this level's band; the CPU
   applies it to exposed rock along the surface normal). */
//! sampler terms       the lattice terms, three texels each (above)
//! sampler st          x: h (metres) for the bedding
//! image   outB rgba32f
//! uniform int uTerms
//! uniform float uCell
//! uniform float uX0
//! uniform float uY0
//! uniform float uKOct
//! uniform float uRockDeg
//! uniform float uSpreadDeg
//! uniform float uMinDeg
//! uniform float uMaxDeg
//! uniform float uBedSpacing
//! uniform float uBedWidth
//! uniform float uBedAmpS
//! uniform float uBedAmpD
//! uniform float uBedZ0
//! uniform float uDipX
//! uniform float uDipY
//! include noise

fn lattice_term(t: i32, local: vec2<f32>) -> f32 {
  let b = terms_at(vec2<i32>(3 * t + 1, 0));
  let m = terms_at(vec2<i32>(3 * t + 2, 0));
  let lc = vec2<f32>(b.z + m.x * local.x + m.y * local.y, b.w + m.z * local.x + m.w * local.y);
  let fl = floor(lc);
  return eido_lattice(vec2<i32>(b.xy) + vec2<i32>(fl), lc - fl, 0);
}

fn kmain(p: vec2<i32>) {
  let n = outB_size();
  if (!inside(p, n)) { return; }
  let local = (vec2<f32>(p) + 0.5) * u.uCell;
  var R = 0.0;
  var D = 0.0;
  var line = 0.0;
  for (var t = 0; t < u.uTerms; t++) {
    let a = terms_at(vec2<i32>(3 * t, 0));
    let v = lattice_term(t, local);
    let mode = i32(a.x + 0.5);
    if (mode == 0) {
      R += a.y * v;
      D += a.w * v;
    } else if (mode == 1) {
      let l = max(1.0 - abs(v) / a.z, 0.0);
      line = l * l;
    } else {
      let w = line * smoothstep(-a.z, a.z, v);
      R -= a.y * w;
      D -= a.w * w;
    }
  }
  if (u.uBedAmpS > 0.0 || u.uBedAmpD > 0.0) {
    let x = u.uX0 + local.x;
    let y = u.uY0 + local.y;
    let zs = (st_at(p).x - (u.uDipX * x + u.uDipY * y) - u.uBedZ0) / u.uBedSpacing;
    let dist = abs(zs - floor(zs + 0.5)) * u.uBedSpacing;
    var l = max(1.0 - dist / (0.5 * u.uBedWidth), 0.0);
    l = l * l;
    R -= u.uBedAmpS * l;
    D -= u.uBedAmpD * l;
  }
  let kfac = exp2(-u.uKOct * R);
  let sc = tan(radians(clamp(u.uRockDeg + u.uSpreadDeg * R, u.uMinDeg, u.uMaxDeg)));
  outB_store(p, vec4<f32>(R, kfac, sc, D));
}
