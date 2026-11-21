// Port of blender/eidoblend/terrain/surface/kernels/blur.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged. The changes are WGSL's: texelFetch is src_at(q), imageStore is outB_store, textureSize is src_size(),
// the uniforms are u.<name>, and the ternaries are select() (both arms are plain values).
/* blur: one pass of a separable Gaussian, four widths at once (SURFACING_DESIGN.md 2.3, step 5). Two dispatches make
   four blurs of one field: the first along x with uFan = 1 (every output channel blurs src.x with its own width), the
   second along y with uFan = 0 (channel by channel). Indices clamp at the grid's edge (the bake pads the level with
   its parents' terrain, so the edge is far from the cells it keeps). Twin: surface/twins.py blur. */
//! sampler src         the field(s) to blur
//! image   outB rgba32f
//! uniform vec4 uSigma     the standard deviation of each output channel, texels (0: the channel is copied)
//! uniform ivec2 uDir      (1, 0): along x; (0, 1): along y
//! uniform int uFan        1: every channel blurs src.x; 0: channel c blurs src[c]

fn kmain(p: vec2<i32>) {
  let n = src_size();
  if (!inside(p, n)) { return; }
  let smax = max(max(u.uSigma.x, u.uSigma.y), max(u.uSigma.z, u.uSigma.w));
  let R = min(i32(ceil(3.0 * smax)), 96);
  let inv = vec4<f32>(select(1.0e30, 0.5 / (u.uSigma.x * u.uSigma.x), u.uSigma.x > 0.0),
                      select(1.0e30, 0.5 / (u.uSigma.y * u.uSigma.y), u.uSigma.y > 0.0),
                      select(1.0e30, 0.5 / (u.uSigma.z * u.uSigma.z), u.uSigma.z > 0.0),
                      select(1.0e30, 0.5 / (u.uSigma.w * u.uSigma.w), u.uSigma.w > 0.0));
  var acc = vec4<f32>(0.0);
  var ws = vec4<f32>(0.0);
  for (var i = -R; i <= R; i++) {
    let q = clamp(p + i * u.uDir, vec2<i32>(0), n - 1);
    var v = src_at(q);
    if (u.uFan == 1) { v = vec4<f32>(v.x); }
    let w = exp(-f32(i * i) * inv);
    acc += w * v;
    ws += w;
  }
  outB_store(p, acc / ws);
}
