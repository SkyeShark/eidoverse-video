/* jump_flood (design section 4.5, step 4; Rong & Tan 2006): one jump-flooding pass. Every cell keeps the four best
   seeds of DIFFERENT streams it has heard of (candT: their packed cell indices i + j n.x as floats, best first, -1
   none) and hears the candidates of the 8 cells uStep away; all are ranked here by the metric, then by index (so a
   tie resolves the same way everywhere):
       uMetric 0: the trough's target height at this cell, zf + max(H prof(r / W), fillz(r / W)): a lower
                  envelope, so a trunk's trough wins over a nearer tributary's, and a step in a floor becomes a riegel
       uMetric 1: the distance r (the test against a brute-force twin)
   prof(rho) = 0 on the floor (rho <= uFloorFrac), ((rho - uFloorFrac) / (1 - uFloorFrac))^b up the wall to the lip
   (rho = 1), then the shoulder 1 + uShH ((rho - 1) / uShW)^uShB (a bench uShW W wide rising uShH H to its outer
   edge; uShW 0: the wall's law continues), then the upper wall up to the trimline, rising uOut H per W (so the
   carve ends at the trimline instead of planing the ridges beyond). fillz(rho) = fill + uFloorRise H
   min(rho / uFloorFrac, 1)^2: the valley fill's top, rising gently from the river to the foot of the walls.
   One entry per stream, so the U-carve's smooth minimum joins different troughs and never a stream's neighbouring
   seeds (which would sink every floor by a quarter of the join width). Steps uStep = 2^k ... 2, 1, then 1 again
   (solvers/glacial.py jfa_steps). Twin: solvers/glacial.py jump_flood. */
//! sampler candT       xyzw: four candidate seeds (packed cell index as float; -1 none), best first
//! sampler seedA       per seed cell: x, y (m from the grid's corner), zf (the floor under the fill), H (wall, m)
//                      (cell (i, j)'s centre is ((i + .5) dx, (j + .5) dx); H runs from the floor to the lip)
//! sampler seedB       per seed cell: W (half-width, m), stream id, fill (m above zf), moraine (m)
//! image   outC rgba32f
//! uniform int uStep   the jump, cells
//! uniform float uDx   the cell, metres
//! uniform float uB    the wall's exponent b
//! uniform float uFloorFrac  the floor's share of the half-width (the wall starts there)
//! uniform float uFloorRise  the fill's rise from the river to the foot of the walls, a share of H
//! uniform float uShW  the shoulder's width, a share of the half-width W (0: no shoulder)
//! uniform float uShH  the shoulder's rise to its outer edge, a share of H
//! uniform float uShB  the shoulder's exponent
//! uniform float uOut  the upper wall beyond the shoulder: its rise in H per W
//! uniform int uMetric 0: the target height; 1: the distance

float prof(float rho) {
  if (rho <= 1.0 || uShW <= 0.0) return pow(max(rho - uFloorFrac, 0.0) / (1.0 - uFloorFrac), uB);
  float s = (rho - 1.0) / uShW;
  if (s <= 1.0) return 1.0 + uShH * pow(s, uShB);
  return 1.0 + uShH + uOut * (rho - 1.0 - uShW);
}

float fillz(float rho, float fill, float H) {
  float t = min(rho / max(uFloorFrac, 1e-3), 1.0);
  return fill + uFloorRise * H * t * t;
}

float metric(int ci, ivec2 n, vec2 xp, out float sid) {
  ivec2 c = ivec2(ci % n.x, ci / n.x);
  vec4 a = texelFetch(seedA, c, 0);
  vec4 b = texelFetch(seedB, c, 0);
  sid = b.y;
  vec2 d = xp - a.xy;
  float r = sqrt(d.x * d.x + d.y * d.y);
  if (uMetric == 1) return r;
  float rho = r / b.x;
  return a.z + max(a.w * prof(rho), fillz(rho, b.z, a.w));
}

/* (ci, m, sid) into the sorted list: one entry per stream (the better kept), the four best streams */
void offer(inout float bi[4], inout float bm[4], inout float bs[4], float ci, float m, float sid) {
  for (int t = 0; t < 4; t++) {
    if (bi[t] >= 0.0 && bs[t] == sid) {
      if (!(m < bm[t] || (m == bm[t] && ci < bi[t]))) return;
      for (int u = t; u < 3; u++) {
        bi[u] = bi[u + 1];
        bm[u] = bm[u + 1];
        bs[u] = bs[u + 1];
      }
      bi[3] = -1.0;
      bm[3] = 3.0e38;
      bs[3] = -1.0;
      break;
    }
  }
  int at = 4;
  for (int t = 0; t < 4; t++) {
    if (at == 4 && (bi[t] < 0.0 || m < bm[t] || (m == bm[t] && ci < bi[t]))) at = t;
  }
  if (at == 4) return;
  for (int t = 3; t > at; t--) {
    bi[t] = bi[t - 1];
    bm[t] = bm[t - 1];
    bs[t] = bs[t - 1];
  }
  bi[at] = ci;
  bm[at] = m;
  bs[at] = sid;
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(candT, 0);
  if (!inside(p, n)) return;
  vec2 xp = (vec2(p) + 0.5) * uDx;
  float bi[4] = float[4](-1.0, -1.0, -1.0, -1.0);
  float bm[4] = float[4](3.0e38, 3.0e38, 3.0e38, 3.0e38);
  float bs[4] = float[4](-1.0, -1.0, -1.0, -1.0);
  for (int oy = -1; oy <= 1; oy++) {
    for (int ox = -1; ox <= 1; ox++) {
      ivec2 q = p + ivec2(ox, oy) * uStep;
      if (!inside(q, n)) continue;
      vec4 c4 = texelFetch(candT, q, 0);
      for (int t = 0; t < 4; t++) {
        float ci = c4[t];
        if (ci < 0.0) continue;
        float sid;
        float m = metric(int(ci), n, xp, sid);
        offer(bi, bm, bs, ci, m, sid);
      }
    }
  }
  imageStore(outC, p, vec4(bi[0], bi[1], bi[2], bi[3]));
}
