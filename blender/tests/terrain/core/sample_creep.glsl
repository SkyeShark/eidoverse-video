/* The design probe's creep pass (design_probes/gpu_spl.py CREEP), written to the house kernel conventions as the
   runner's worked example and its parity test subject. It is not the fluvial package's creep kernel.

   Nonlinear creep (Roering et al. 1999): flux to all 8 neighbours with the isotropic weights and the factor
   min(1 / (1 - (s/Sc)^2), cap); one explicit sub-step of dt_sub years. Boundary modes from common.glsl; in PINNED
   mode a cell is pulled to its pin after the update. */
//! sampler st          x: h (m), y: A (m^2, carried through)
//! sampler par         z: Sc (tangent of the threshold slope)
//! sampler pin         x: pin_w (0..1), y: pin_h (m)
//! image   outS rgba32f
//! uniform float uDx
//! uniform float uDtSub
//! uniform float uD
//! uniform float uCap
//! uniform int uBound
void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float hc = c.x;
  float sc = texelFetch(par, p, 0).z;
  float acc = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    float hq = texelFetch(st, q, 0).x;
    float s = (hq - hc) / (LEN[k] * uDx);
    float r = s / sc;
    float f = min(1.0 / max(1.0 - r * r, 1e-9), uCap);
    acc += WISO[k] * f * (hq - hc);
  }
  float hn = hc + uDtSub * uD * acc / (uDx * uDx);
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    hn = pin_apply(hn, pn.x, pn.y);
  }
  imageStore(outS, p, vec4(hn, c.y, 0.0, 0.0));
}
