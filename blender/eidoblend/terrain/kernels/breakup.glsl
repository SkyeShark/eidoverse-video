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

/*__WORLD_NOISE__*/

float lattice_term(int t, vec2 local) {
  vec4 b = texelFetch(terms, ivec2(3 * t + 1, 0), 0);
  vec4 m = texelFetch(terms, ivec2(3 * t + 2, 0), 0);
  vec2 lc = vec2(b.z + m.x * local.x + m.y * local.y, b.w + m.z * local.x + m.w * local.y);
  vec2 fl = floor(lc);
  return eido_lattice(ivec2(b.xy) + ivec2(fl), lc - fl, 0);
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = imageSize(outB);
  if (!inside(p, n)) return;
  vec2 local = (vec2(p) + 0.5) * uCell;
  float R = 0.0;
  float D = 0.0;
  float line = 0.0;
  for (int t = 0; t < uTerms; t++) {
    vec4 a = texelFetch(terms, ivec2(3 * t, 0), 0);
    float v = lattice_term(t, local);
    int mode = int(a.x + 0.5);
    if (mode == 0) {
      R += a.y * v;
      D += a.w * v;
    } else if (mode == 1) {
      float l = max(1.0 - abs(v) / a.z, 0.0);
      line = l * l;
    } else {
      float w = line * smoothstep(-a.z, a.z, v);
      R -= a.y * w;
      D -= a.w * w;
    }
  }
  if (uBedAmpS > 0.0 || uBedAmpD > 0.0) {
    float x = uX0 + local.x;
    float y = uY0 + local.y;
    float zs = (texelFetch(st, p, 0).x - (uDipX * x + uDipY * y) - uBedZ0) / uBedSpacing;
    float dist = abs(zs - floor(zs + 0.5)) * uBedSpacing;
    float l = max(1.0 - dist / (0.5 * uBedWidth), 0.0);
    l = l * l;
    R -= uBedAmpS * l;
    D -= uBedAmpD * l;
  }
  float kfac = exp2(-uKOct * R);
  float sc = tan(radians(clamp(uRockDeg + uSpreadDeg * R, uMinDeg, uMaxDeg)));
  imageStore(outB, p, vec4(R, kfac, sc, D));
}
