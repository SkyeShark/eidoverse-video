/* cavity: short-radius sky view on the detail grid (SURFACING_DESIGN.md 2.3, step 4), and the detail scalars' image.
   A horizon march over the height plus the sub-cell relief: 16 azimuths, at 2, 4, 8, 16 and 32 texels along each
   (the whole-texel offset nearest the azimuth, its true length), the steepest tangent up to the terrain there;
   cavity = 1 - mean(sin horizon angle), masks.py's sky_view at the scale of a crease (Zaksek et al. 2011): 1 open,
   low in gullies, joints and at wall feet. crest_fine is the level's own finest convexity of the same surface, the
   mean of the crest term at 1 and 2 texels: tanh((z - G_s z) / (tau s)). It is read on the height plus the sub-cell
   relief, never on the height alone: on a detail grid at half the cell the height's own finest term is the
   Catmull-Rom upsampling's imprint, grid-aligned streaks. Indices clamp at the padded grid's edge. Twin:
   surface/twins.py cavity. */
//! sampler zT              phacelle's outR on the detail grid: y: crease, z: the height plus the sub-cell relief
//! sampler blurT           zT blurred at one texel, channel by channel (z: the surface's)
//! sampler blur2T          zT blurred at two texels
//! image   outE rgba32f    crease, cavity, crest_fine, 0
//! uniform float uTexel    the detail grid's texel, metres
//! uniform float uTau      crest_fine's relief ratio

const float TAU = 6.28318530717959;

void main() {
  ivec2 P = ivec2(gl_GlobalInvocationID.xy);
  ivec2 nD = textureSize(zT, 0);
  if (!inside(P, nD)) return;
  vec4 zc = texelFetch(zT, P, 0);
  float acc = 0.0;
  for (int k = 0; k < 16; k++) {
    float a = TAU * float(k) / 16.0;
    vec2 dir = vec2(cos(a), sin(a));
    float best = 0.0;
    for (int r = 2; r <= 32; r *= 2) {
      ivec2 o = ivec2(floor(dir * float(r) + 0.5));
      ivec2 q = clamp(P + o, ivec2(0), nD - 1);
      best = max(best, (texelFetch(zT, q, 0).z - zc.z) / (length(vec2(o)) * uTexel));
    }
    acc += best / sqrt(1.0 + best * best);
  }
  float fine = 0.5 * (tanh((zc.z - texelFetch(blurT, P, 0).z) / (uTau * uTexel))
                      + tanh((zc.z - texelFetch(blur2T, P, 0).z) / (uTau * 2.0 * uTexel)));
  imageStore(outE, P, vec4(zc.y, 1.0 - acc / 16.0, fine, 0.0));
}
