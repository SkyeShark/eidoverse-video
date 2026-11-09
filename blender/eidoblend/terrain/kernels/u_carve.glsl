/* u_carve (design section 4.5, steps 4-5): the trough target from the jump flood's candidates and the cirques, cut
   into the surface.
       T_s(x)  = zf + max(H (r / W)^b, fill)     per candidate seed (r its distance in metres): a U whose flat floor
                                                 is the valley fill, its wall H (r / W)^b up to the trimline
       T       = smin over the candidates and the cirque bowls (the polynomial smooth minimum, uJoin metres wide:
                 troughs and cirques meet with no crease)
       T_rock  = the same without the fill term   (the bedrock under the fill)
       cirque  = z_floor + H_c rho^uCirqExp       rho the elliptical distance (R_across, R_along down-glacier)
       h'      = smin(h, T, uTrim) + moraine     the trimline; the lateral moraine (seedB.w high at uMorAt of the
                                                 half-width) only where the trough cut
       bed'    = min(smin(bed, T_rock, uTrim), h')
   Masks from the best candidate's r / W and the cirques' rho: trough (r / W under 0.85 .. 1.15), its flat floor
   (under uFloorFrac .. + 0.12), the walls (trough minus floor). ice: the glacier's surface at the carving maximum
   (zf + H at the best seed inside its trough; z_floor + 0.35 H_c in a cirque) above h'. In BOUND_PINNED mode h' is
   pulled to its pin. Twin: solvers/glacial.py u_carve. */
//! sampler candT       the jump flood's candidates (jump_flood.glsl)
//! sampler seedA       x, y (m from the grid's corner), zf, H (m)
//! sampler seedB       W (m), stream id, fill (m), moraine (m)
//! sampler st          x: h, y: bed (m)
//! sampler cirq        texel (k, 0): x, y (m), z_floor (m), H_c (m); texel (k, 1): down-glacier x, y, R_across, R_along
//! sampler pin         x: pin_w, y: pin_h
//! image   outS rgba32f  x: h', y: bed', z: the target T, w: ice thickness (m)
//! image   outM rgba32f  x: carve depth h - h' (m), y: floor mask, z: wall mask, w: trough mask
//! uniform float uDx         the cell, metres
//! uniform float uB          the wall's exponent b
//! uniform float uJoin       the smooth minimum between troughs and cirques (m)
//! uniform float uTrim       the smooth minimum at the trimline (m)
//! uniform float uFloorFrac  the flat floor's share of the half-width
//! uniform float uMorAt      the lateral moraine's place, a share of the half-width
//! uniform float uMorW       its width, a share of the half-width
//! uniform int uNCirq        the cirques in cirq
//! uniform float uCirqExp    the cirque headwall's exponent
//! uniform int uBound

float smin(float a, float b, float k) {
  if (k <= 0.0) return min(a, b);
  float hh = max(k - abs(a - b), 0.0) / k;
  return min(a, b) - hh * hh * k * 0.25;
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(candT, 0);
  if (!inside(p, n)) return;
  vec2 xp = (vec2(p) + 0.5) * uDx;
  float Tf = 1.0e30;
  float Tr = 1.0e30;
  float ice_top = -1.0e30;
  float rw0 = 10.0;
  float mor = 0.0;
  vec4 c4 = texelFetch(candT, p, 0);
  for (int c = 0; c < 4; c++) {
    float ci = c4[c];
    if (ci < 0.0) continue;
    int ii = int(ci);
    ivec2 cp = ivec2(ii % n.x, ii / n.x);
    vec4 a = texelFetch(seedA, cp, 0);
    vec4 b = texelFetch(seedB, cp, 0);
    vec2 d = xp - a.xy;
    float r = sqrt(d.x * d.x + d.y * d.y);
    float rw = r / b.x;
    float wall = a.w * pow(rw, uB);
    float tf = a.z + max(wall, b.z);
    float tr = a.z + wall;
    Tf = c == 0 ? tf : smin(Tf, tf, uJoin);
    Tr = c == 0 ? tr : smin(Tr, tr, uJoin);
    if (c == 0) {
      rw0 = rw;
      if (rw < 1.0) ice_top = a.z + a.w;
      float g = (rw - uMorAt) / uMorW;
      mor = b.w * exp(-g * g);
    }
  }
  for (int k = 0; k < uNCirq; k++) {
    vec4 c0 = texelFetch(cirq, ivec2(k, 0), 0);
    vec4 c1 = texelFetch(cirq, ivec2(k, 1), 0);
    vec2 d = xp - c0.xy;
    float along = d.x * c1.x + d.y * c1.y;
    float across = -d.x * c1.y + d.y * c1.x;
    float ua = along / c1.w;
    float uc = across / c1.z;
    float rho = sqrt(ua * ua + uc * uc);
    float tc = c0.z + c0.w * pow(rho, uCirqExp);
    Tf = smin(Tf, tc, uJoin);
    Tr = smin(Tr, tc, uJoin);
    if (rho < 1.0) ice_top = max(ice_top, c0.z + 0.35 * c0.w);
    rw0 = min(rw0, rho);
  }
  vec4 s4 = texelFetch(st, p, 0);
  float h = s4.x;
  float hn = smin(h, Tf, uTrim);
  float carved = h - hn;
  if (carved > 0.0) hn += mor;
  float bn = min(smin(s4.y, Tr, uTrim), hn);
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    hn = pin_apply(hn, pn.x, pn.y);
    bn = min(bn, hn);
  }
  float ice = ice_top > -1.0e30 ? max(ice_top - hn, 0.0) : 0.0;
  float t1 = clamp((rw0 - uFloorFrac) / 0.12, 0.0, 1.0);
  float floorm = 1.0 - t1 * t1 * (3.0 - 2.0 * t1);
  float t2 = clamp((rw0 - 0.85) / 0.3, 0.0, 1.0);
  float trough = 1.0 - t2 * t2 * (3.0 - 2.0 * t2);
  imageStore(outS, p, vec4(hn, bn, Tf, ice));
  imageStore(outM, p, vec4(max(carved, 0.0), floorm * trough, trough * (1.0 - floorm), trough));
}
