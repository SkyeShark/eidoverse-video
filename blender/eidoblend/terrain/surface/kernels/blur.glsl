/* blur: one pass of a separable Gaussian, four widths at once (SURFACING_DESIGN.md 2.3, step 5). Two dispatches make
   four blurs of one field: the first along x with uFan = 1 (every output channel blurs src.x with its own width), the
   second along y with uFan = 0 (channel by channel). Indices clamp at the grid's edge (the bake pads the level with
   its parents' terrain, so the edge is far from the cells it keeps). Twin: surface/twins.py blur. */
//! sampler src         the field(s) to blur
//! image   outB rgba32f
//! uniform vec4 uSigma     the standard deviation of each output channel, texels (0: the channel is copied)
//! uniform ivec2 uDir      (1, 0): along x; (0, 1): along y
//! uniform int uFan        1: every channel blurs src.x; 0: channel c blurs src[c]

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(src, 0);
  if (!inside(p, n)) return;
  float smax = max(max(uSigma.x, uSigma.y), max(uSigma.z, uSigma.w));
  int R = min(int(ceil(3.0 * smax)), 96);
  vec4 inv = vec4(uSigma.x > 0.0 ? 0.5 / (uSigma.x * uSigma.x) : 1.0e30,
                  uSigma.y > 0.0 ? 0.5 / (uSigma.y * uSigma.y) : 1.0e30,
                  uSigma.z > 0.0 ? 0.5 / (uSigma.z * uSigma.z) : 1.0e30,
                  uSigma.w > 0.0 ? 0.5 / (uSigma.w * uSigma.w) : 1.0e30);
  vec4 acc = vec4(0.0);
  vec4 ws = vec4(0.0);
  for (int i = -R; i <= R; i++) {
    ivec2 q = clamp(p + i * uDir, ivec2(0), n - 1);
    vec4 v = texelFetch(src, q, 0);
    if (uFan == 1) v = vec4(v.x);
    vec4 w = exp(-float(i * i) * inv);
    acc += w * v;
    ws += w;
  }
  imageStore(outB, p, acc / ws);
}
