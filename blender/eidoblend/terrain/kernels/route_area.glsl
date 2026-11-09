/* route_area (design sections 4.1 "after the last step" and 4.3): one Jacobi iteration of drainage-area routing on a
   fixed surface,

       A = dx^2 + A_in + sum over higher neighbours q of A_q * max(s_qc, 0)^p / wsum_q

   iterated to convergence (the runner stops when the largest relative change is under 1e-4, checked every 128
   iterations). The surface is the lake-filled one with a small tilt across each lake toward its spill (solvers/
   hydro.py routing_surface), so water crosses lakes; A_in is the area entering from outside the window (a child
   level's border inflow). Twin: solvers/hydro.py route_area. */
//! sampler st          x: the routing surface (m)
//! sampler wsumT       x: wsum of st.x (flow_weights)
//! sampler aT          x: A, the previous iterate (m^2)
//! sampler pin         z: A_in (m^2)
//! image   outA r32f   x: A (m^2)
//! uniform float uDx   the cell, metres
//! uniform float uP    the flow exponent p
//! uniform int uBound

float wpow(float s, float e) { return e == 1.0 ? s : pow(s, e); }

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  float h = texelFetch(st, p, 0).x;
  float A = uDx * uDx + texelFetch(pin, p, 0).z;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    float hq = texelFetch(st, q, 0).x;
    if (hq > h) {
      float share = wpow((hq - h) / (LEN[k] * uDx), uP) / max(texelFetch(wsumT, q, 0).x, 1e-30);
      A += texelFetch(aT, q, 0).x * share;
    }
  }
  imageStore(outA, p, vec4(A, 0.0, 0.0, 0.0));
}
