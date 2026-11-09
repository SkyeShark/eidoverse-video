/* threshold (design section 4.1, pass 4; 4.2): one iteration of the mass-conserving threshold relaxation, which
   keeps slopes at or under their threshold (hillslopes failing at their angle; talus at repose). Every neighbour
   pair exchanges an amount computed alike from both of its cells, so the sum of h is conserved (open and periodic
   modes); the moved material lands where the rivers carry it away.

   uIso = 1 (the default): isotropic. Each cell's slope is the upwind (Rouy-Tourin) gradient magnitude
       G = sqrt(max(h - min(h_W, h_E), 0)^2 + max(h - min(h_S, h_N), 0)^2) / dx,
   exact for a plane facing any direction, and its excess phi = max(1 - Sc / G, 0) (phiT: written for the same h
   by solvers/hillslope.py's inline kernel threshold_excess, once per iteration). The pair (c, k) exchanges
       x = rate WISO_k (h_c - h_k) (phi_c + phi_k) / 2,
   a nonlinear diffusion that runs only where the slope is over its threshold, along the gradient with the
   isotropic 9-point weights, until G <= Sc everywhere.
   uIso = 0: the design's pair excess, x = rate max(|h_c - h_k| - Sc_pair L_k dx, 0) from the higher cell. Its
   stable slopes form an octagon (8 % steeper between the grid directions) and it relaxes axis-facing slopes slower
   than diagonal ones (the excess is counted in height over a pair √2 longer): on the first range's threshold slopes
   that printed 4-fold (0.12) and 8-fold (0.07) aspect bias, against the San Gabriels' 0.02 and 0.004.

   uLoose = 1 limits it to loose material: a cell gives at most an eighth of its loose thickness (mk.w, h - bed) to
   each neighbour, so bedrock walls stand and only debris relaxes (the talus stage). The accumulators: a net gain is
   talus; a net loss takes talus, then deposit, then other loose cover, then rock (wear); mk.w, the loose
   thickness, follows the net change. In BOUND_PINNED mode the height is pulled to its pin, and the pull is counted
   in the layers as route_incise.glsl counts it (pin_layers: added as deposit, taken loose first, then rock).
   Twin: solvers/hillslope.py threshold. */
//! sampler st          x: h (m); y, z, w carried
//! sampler par         z: Sc, the threshold slope's tangent
//! sampler pin         x: pin_w (0..1), y: pin_h (m)
//! sampler mk          x: wear (m), y: deposit (m), z: talus (m), w: loose thickness h - bed (m)
//! sampler phiT        x: every cell's excess phi (isotropic mode; a 1 x 1 dummy in pair mode)
//! image   outS rgba32f
//! image   outM rgba32f
//! uniform float uDx   the cell, metres
//! uniform float uRate the share moved per iteration (pair excess 0.06; isotropic 0.12)
//! uniform int uLoose  1: only loose material moves
//! uniform int uIso    1: isotropic (upwind gradient magnitude); 0: the design's pair excess
//! uniform int uBound

/* the pin's change d of the height in the layers m (as route_incise.glsl) */
vec4 pin_layers(vec4 m, float d) {
  if (d >= 0.0) return vec4(m.x, m.y + d, m.z, m.w + d);
  float q = -d;
  float other = max(m.w - m.y - m.z, 0.0);
  float a = min(q, m.y);
  m.y -= a;
  q -= a;
  a = min(q, m.z);
  m.z -= a;
  q -= a;
  q -= min(q, other);
  m.w = max(m.w - (-d - q), 0.0);
  m.x += q;
  return m;
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(st, 0);
  if (!inside(p, n)) return;
  vec4 c = texelFetch(st, p, 0);
  float h = c.x;
  float sc = texelFetch(par, p, 0).z;
  vec4 m = texelFetch(mk, p, 0);
  float phc = uIso == 1 ? texelFetch(phiT, p, 0).x : 0.0;
  float dh = 0.0;
  for (int k = 0; k < 8; k++) {
    ivec2 q;
    if (!neighbour(p, k, n, uBound, q)) continue;
    float hq = texelFetch(st, q, 0).x;
    float x;                                              // what c gives q (negative: what it receives)
    if (uIso == 1) {
      x = uRate * WISO[k] * ((h - hq) * (0.5 * (phc + texelFetch(phiT, q, 0).x)));
    } else {
      float t = 0.5 * (sc + texelFetch(par, q, 0).z) * LEN[k] * uDx;
      float e = uRate * max(abs(h - hq) - t, 0.0);
      x = h > hq ? e : -e;
    }
    if (uLoose == 1) {
      float giver = h > hq ? m.w : texelFetch(mk, q, 0).w;
      x = sign(x) * min(abs(x), 0.125 * max(giver, 0.0));
    }
    dh -= x;
  }
  float tal = m.z;
  float dep = m.y;
  float wear = m.x;
  if (dh >= 0.0) {
    tal += dh;
  } else {
    float other = max(m.w - dep - tal, 0.0);
    float r = -dh;
    float a = min(r, tal);
    tal -= a;
    r -= a;
    a = min(r, dep);
    dep -= a;
    r -= a;
    r -= min(r, other);
    wear += r;
  }
  float hn = h + dh;
  vec4 mo = vec4(wear, dep, tal, max(m.w + dh, 0.0));
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    float hp = pin_apply(hn, pn.x, pn.y);
    mo = pin_layers(mo, hp - hn);
    hn = hp;
  }
  imageStore(outS, p, vec4(hn, c.y, c.z, c.w));
  imageStore(outM, p, mo);
}
