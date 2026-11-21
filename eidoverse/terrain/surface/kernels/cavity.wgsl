// Port of blender/eidoblend/terrain/surface/kernels/cavity.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged. The changes are WGSL's: texelFetch is <name>_at(q), imageStore is outE_store, textureSize is
// zT_size(), the uniforms are u.<name>, and `r *= 2` steps a while loop's counter.
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

const TAU: f32 = 6.28318530717959;

fn kmain(P: vec2<i32>) {
  let nD = zT_size();
  if (!inside(P, nD)) { return; }
  let zc = zT_at(P);
  var acc = 0.0;
  for (var k = 0; k < 16; k++) {
    let a = TAU * f32(k) / 16.0;
    let dir = vec2<f32>(cos(a), sin(a));
    var best = 0.0;
    var r = 2;
    while (r <= 32) {
      let o = vec2<i32>(floor(dir * f32(r) + 0.5));
      let q = clamp(P + o, vec2<i32>(0), nD - 1);
      best = max(best, (zT_at(q).z - zc.z) / (length(vec2<f32>(o)) * u.uTexel));
      r *= 2;
    }
    acc += best / sqrt(1.0 + best * best);
  }
  let fine = 0.5 * (tanh((zc.z - blurT_at(P).z) / (u.uTau * u.uTexel))
                    + tanh((zc.z - blur2T_at(P).z) / (u.uTau * 2.0 * u.uTexel)));
  outE_store(P, vec4<f32>(zc.y, 1.0 - acc / 16.0, fine, 0.0));
}
