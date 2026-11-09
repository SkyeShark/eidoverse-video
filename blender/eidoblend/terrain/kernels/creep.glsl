/* creep (design section 4.1, pass 3; 4.2): one explicit sub-step of nonlinear hillslope creep (Roering et al. 1999)

       dh = dt_sub D / dx^2 * sum_k WISO_k f_k (h_k - h),   f_k = min(1 / (1 - (s_k / Sc_k)^2), cap)

   with the isotropic 9-point weights (sides 2/3, diagonals 1/6), s_k = (h_k - h) / (L_k dx) and Sc_k the mean of the
   two cells' threshold tangents. Every pair's exchange is computed alike from both of its cells, so the sum of h is
   conserved (in the open and periodic modes). cap = 1 is linear diffusion (the aging stage's kappa t). Stable for
   dt_sub <= 0.9 dx^2 / (3.4 D cap) (the runner sub-steps). In BOUND_PINNED mode the height is pulled to its pin.
   Twin: solvers/hillslope.py creep. */
//! sampler st          x: h (m); y, z, w carried
//! sampler par         z: Sc, the threshold slope's tangent
//! sampler pin         x: pin_w (0..1), y: pin_h (m)
//! image   outS rgba32f
//! uniform float uDx   the cell, metres
//! uniform float uDtSub
//! uniform float uD    the creep diffusivity, m^2/yr
//! uniform float uCap
//! uniform int uBound

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float h = c.x;
  float sc = texelFetch(par, p, 0).z;
  float acc = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    float hq = texelFetch(st, q, 0).x;
    float scp = 0.5 * (sc + texelFetch(par, q, 0).z);
    float r = ((hq - h) / (LEN[k] * uDx)) / scp;
    float f = min(1.0 / max(1.0 - r * r, 1e-9), uCap);
    acc += WISO[k] * f * (hq - h);
  }
  float hn = h + uDtSub * uD * acc / (uDx * uDx);
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    hn = pin_apply(hn, pn.x, pn.y);
  }
  imageStore(outS, p, vec4(hn, c.y, c.z, c.w));
}
