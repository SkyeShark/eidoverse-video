/* flow_weights (design section 4.1, pass 1): every cell's total downhill weight

       wsum = sum_k max(s_k, 0)^p,   s_k = (h - h_k) / (L_k dx)

   so a neighbour k receives the share max(s_k, 0)^p / wsum of the cell's flow (multiple flow directions, slope to
   the power p; p = 1 by default). route_incise and route_area read it to split each upstream neighbour's drainage
   area and sediment flux. Twin: solvers/fluvial.py flow_weights. */
//! sampler st          x: the surface the water follows, h (m)
//! image   outW r32f   x: wsum, the sum of the downhill slopes to the power p
//! uniform float uDx   the cell, metres
//! uniform float uP    the flow exponent p
//! uniform int uBound  BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED (common.glsl)

float wpow(float s, float e) { return e == 1.0 ? s : pow(s, e); }

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float h = texelFetch(st, p, 0).x;
  float ws = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    float s = (h - texelFetch(st, q, 0).x) / (LEN[k] * uDx);
    if (s > 0.0) ws += wpow(s, uP);
  }
  imageStore(outW, p, vec4(ws, 0.0, 0.0, 0.0));
}
