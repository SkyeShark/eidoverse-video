/* u_carve (design section 4.5, steps 4-5): the trough target from the jump flood's candidates and the cirques, cut
   into the surface.
       T_s(x)  = zf + max(H prof(rho), fillz(rho))   per candidate seed, rho = r / W (r its distance in metres):
                 prof (jump_flood.glsl's) is 0 on the floor (rho <= ff, ff = uFloorFrac seedC.x: the seed's own floor
                 share, narrower in a tributary than in the trunk), the wall cliff((rho - ff) / (1 - ff)) up to the
                 lip (rho = 1): its slope ramps up over the toe (uToe of its run), stands at its steepest across the
                 core and eases off over the lip (uLip); then the shoulder 1 + uShH ((rho - 1) / uShW)^uShB, then
                 the upper wall rising uOut H per W to the trimline (uShW 0: the upper wall from the lip). fillz is
                 the valley fill's top, fill + rise H min(rho / ff, 1)^2, rise = uFloorRise seedC.y (the fans and
                 aprons rising from the river to the walls' foot, their height varying along the valley)
       cap     = the largest of the candidates' caps: unbounded inside an inner trough (rho <= 1) or a cirque bowl,
                 uCut H (1 - q)^2 beyond the lip, q = min((rho - 1) / uCutW, 1): the ice lowers the shoulders and
                 spurs by at most that, the most at the lip and nothing at the trimline (rho = 1 + uCutW), so capped
                 ground rises from the lip instead of standing as a shelf level with it (the smoothstep fade this
                 replaced kept the cap nearly whole for a trough's width beyond the lip: a flat old valley floor
                 there stayed a flat strip along the whole trough, and its rivers filled it with gravel)
       T       = smin over the candidates and the cirque bowls (the polynomial smooth minimum, uJoin metres wide:
                 troughs and cirques meet with no crease)
       T_rock  = the same without the fill term   (the bedrock under the fill)
       cirque  = z_floor + H_c t^uCirqExp - uCirqTilt along, t = max(rho - uCirqFloor, 0) / (1 - uCirqFloor): a
                 floor inside uCirqFloor of the bowl, falling down-glacier by uCirqTilt (the tangent) so the bowl
                 drains over its lip instead of holding a basin the end stage fills flat (stamped flat ovals), then
                 the headwall; rho the elliptical distance (R_across, R_along up-glacier, uCirqOpen R_along
                 down-glacier: an armchair open to its valley, not a closed crater), its rim lobed (1 + a (0.6
                 sin(3 theta + p3) + 0.4 sin(5 theta + p5)): no two bowls alike)
       h1      = smax(smin(h, T, uTrim), h - cap, min(uCapJoin, cap)) + moraine     the trimline, and the cap
                 joined by a smooth maximum as wide as the cap allows (a plain max left a crease where the bench met
                 a capped spur; at cap 0 it is h exactly); the lateral moraine (seedB.w high at uMorAt of the
                 half-width) only where the trough cut
       cut     = the shoulder cut, the largest over the candidates of max(smin(e, h - lip, uCapJoin), 0) with
                 e = seedC.z H (1 - q)^2, q = clamp((rho - 1) / uShCutW, 0, 1), lip = zf + H: beyond its lip the ice
                 lowered the old ground by e, the most at the lip, fading out over uShCutW W, never below the lip.
                 The carve to T leaves ground that lay under the target untouched, so an old valley floor at the
                 lip's height stayed a flat strip along both lips; the cut lowers it into a shoulder rising from the
                 lip, whose streams fall over the walls (the lip stands seedC.z H under the old valley floor:
                 solvers/glacial.py centrelines)
       h'      = h - smax(h - h1, cut, min(uCapJoin, cut))     (h1 exactly where the cut is 0)
       bed'    = min(smax(smin(bed, T_rock, uTrim), bed - cap, min(uCapJoin, cap)), h')
   Masks from the best candidate's rho and the cirques' (mapped so their floor edge falls at uFloorFrac too): trough
   (rho under 1 .. 1.3: the inner trough up to its lip, not its shoulders; the recipe keeps the river-carved range's
   refinement off it, and a mask that faded out below the lip let that refinement round the cliffs' upper third
   back to the range's 30-40 degrees), its flat floor (under the best seed's ff .. + 0.12), the walls (trough minus
   floor). ice: the glacier's surface at the carving maximum (zf + H (1 + uShH) at the best seed out to its
   shoulders' edge; z_floor + 0.35 H_c in a cirque) above h'. rho (outS.z): the same best rho the masks are made
   of, for the finer levels' lip band (solvers/glacial.py lip_open). In BOUND_PINNED mode h' is pulled to its pin.
   Twin: solvers/glacial.py u_carve. */
//! sampler candT       the jump flood's candidates (jump_flood.glsl)
//! sampler seedA       x, y (m from the grid's corner), zf, H (m)
//! sampler seedB       W (m), stream id, fill (m), moraine (m)
//! sampler seedC       the floor share's factor (x uFloorFrac), the fans' factor (x uFloorRise), the shoulder cut
//                      (a share of H), unused
//! sampler st          x: h, y: bed (m)
//! sampler cirq        texel (k, 0): x, y (m), z_floor, H_c (m); (k, 1): down-glacier x, y, R_across, R_along (m)
//                      texel (k, 2): the rim's 3- and 5-lobed phases (radians) and its lobes' amplitude
//! sampler pin         x: pin_w, y: pin_h
//! image   outS rgba32f  x: h', y: bed', z: rho (the best seed's r / W, a cirque's mapped), w: ice thickness (m)
//! image   outM rgba32f  x: carve depth h - h' (m), y: floor mask, z: wall mask, w: trough mask
//! uniform float uDx         the cell, metres
//! uniform float uToe        the share of the wall's run over which its slope ramps up from the floor (the apron)
//! uniform float uLip        the share over which it eases off into the shoulder (the rounded lip)
//! uniform float uFloorFrac  the floor's share of the half-width (the wall starts there)
//! uniform float uFloorRise  the fill's rise from the river to the foot of the walls, a share of H
//! uniform float uShW        the shoulder's width, a share of W (0: no shoulder)
//! uniform float uShH        the shoulder's rise to its outer edge, a share of H
//! uniform float uShB        the shoulder's exponent
//! uniform float uOut        the upper wall beyond the shoulder: its rise in H per W
//! uniform float uCut        the deepest cut beyond the lip, a share of H
//! uniform float uCutW       where the cut ends (the trimline), a share of W beyond the lip
//! uniform float uCapJoin    the smooth maximum's width where the cap meets the trough (m)
//! uniform float uShCutW     the shoulder cut's reach beyond the lip, a share of W
//! uniform float uJoin       the smooth minimum between troughs and cirques (m)
//! uniform float uTrim       the smooth minimum at the trimline (m)
//! uniform float uMorAt      the lateral moraine's place, a share of the half-width
//! uniform float uMorW       its width, a share of the half-width
//! uniform int uNCirq        the cirques in cirq
//! uniform float uCirqExp    the cirque headwall's exponent
//! uniform float uCirqFloor  the cirque floor's share of the bowl's radius
//! uniform float uCirqOpen   the bowl's reach down-glacier, a multiple of R_along
//! uniform float uCirqTilt   the bowl's fall down-glacier (a tangent, per metre along its axis)
//! uniform int uBound

float smin(float a, float b, float k) {
  if (k <= 0.0) return min(a, b);
  float hh = max(k - abs(a - b), 0.0) / k;
  return min(a, b) - hh * hh * k * 0.25;
}

float smax(float a, float b, float k) {
  return -smin(-a, -b, k);
}

float cliff(float t) {
  t = clamp(t, 0.0, 1.0);
  float c = 1.0 / (1.0 - 0.5 * (uToe + uLip));
  if (t < uToe) return c * t * t / (2.0 * max(uToe, 1e-6));
  if (t > 1.0 - uLip) {
    float u = 1.0 - t;
    return 1.0 - c * u * u / (2.0 * max(uLip, 1e-6));
  }
  return c * (t - 0.5 * uToe);
}

float prof(float rho, float ff) {
  if (rho <= 1.0) return cliff((rho - ff) / (1.0 - ff));
  if (uShW <= 0.0) return 1.0 + uOut * (rho - 1.0);
  float s = (rho - 1.0) / uShW;
  if (s <= 1.0) return 1.0 + uShH * pow(s, uShB);
  return 1.0 + uShH + uOut * (rho - 1.0 - uShW);
}

float fillz(float rho, float fill, float H, float ff, float rise) {
  float t = min(rho / max(ff, 1e-3), 1.0);
  return fill + rise * H * t * t;
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
  vec4 s4 = texelFetch(st, p, 0);
  float h = s4.x;
  float cap = 0.0;
  float cut = 0.0;
  float ffm = clamp(uFloorFrac, 0.0, 0.95);
  for (int c = 0; c < 4; c++) {
    float ci = c4[c];
    if (ci < 0.0) continue;
    int ii = int(ci);
    ivec2 cp = ivec2(ii % n.x, ii / n.x);
    vec4 a = texelFetch(seedA, cp, 0);
    vec4 b = texelFetch(seedB, cp, 0);
    vec4 e = texelFetch(seedC, cp, 0);
    float ff = clamp(uFloorFrac * e.x, 0.0, 0.95);
    vec2 d = xp - a.xy;
    float r = sqrt(d.x * d.x + d.y * d.y);
    float rw = r / b.x;
    float wall = a.w * prof(rw, ff);
    float tf = a.z + max(wall, fillz(rw, b.z, a.w, ff, uFloorRise * e.y));
    float tr = a.z + wall;
    float tq = clamp((rw - 1.0) / max(uCutW, 1e-3), 0.0, 1.0);
    cap = max(cap, rw <= 1.0 ? 1.0e30 : uCut * a.w * (1.0 - tq) * (1.0 - tq));
    if (e.z > 0.0) {
      float sq = clamp((rw - 1.0) / max(uShCutW, 1e-3), 0.0, 1.0);
      float ec = e.z * a.w * (1.0 - sq) * (1.0 - sq);
      cut = max(cut, max(smin(ec, h - (a.z + a.w), uCapJoin), 0.0));
    }
    Tf = c == 0 ? tf : smin(Tf, tf, uJoin);
    Tr = c == 0 ? tr : smin(Tr, tr, uJoin);
    if (c == 0) {
      rw0 = rw;
      ffm = ff;
      if (rw < 1.0 + uShW) ice_top = a.z + a.w * (1.0 + uShH);
      float g = (rw - uMorAt) / uMorW;
      mor = b.w * exp(-g * g);
    }
  }
  float cf = clamp(uCirqFloor, 0.0, 0.95);
  float ff = clamp(uFloorFrac, 0.0, 0.95);
  for (int k = 0; k < uNCirq; k++) {
    vec4 c0 = texelFetch(cirq, ivec2(k, 0), 0);
    vec4 c1 = texelFetch(cirq, ivec2(k, 1), 0);
    vec4 c2 = texelFetch(cirq, ivec2(k, 2), 0);
    vec2 d = xp - c0.xy;
    float along = d.x * c1.x + d.y * c1.y;
    float across = -d.x * c1.y + d.y * c1.x;
    float ua = along / (along > 0.0 ? c1.w * uCirqOpen : c1.w);
    float uc = across / c1.z;
    float th = atan(uc, ua);
    float rho = sqrt(ua * ua + uc * uc) / (1.0 + c2.z * (0.6 * sin(3.0 * th + c2.x) + 0.4 * sin(5.0 * th + c2.y)));
    float tc = c0.z + c0.w * pow(max(rho - cf, 0.0) / (1.0 - cf), uCirqExp) - uCirqTilt * along;
    Tf = smin(Tf, tc, uJoin);
    Tr = smin(Tr, tc, uJoin);
    if (rho < 1.0) {
      ice_top = max(ice_top, c0.z + 0.35 * c0.w);
      cap = 1.0e30;
    }
    float rq = rho <= cf ? rho * ff / max(cf, 1e-3) : ff + (rho - cf) * (1.0 - ff) / (1.0 - cf);
    if (rq < rw0) ffm = ff;
    rw0 = min(rw0, rq);
  }
  float kc = min(uCapJoin, cap);
  float hn = smax(smin(h, Tf, uTrim), h - cap, kc);
  if (h - hn > 0.0) hn += mor;
  hn = h - smax(h - hn, cut, min(uCapJoin, cut));
  float carved = h - hn;
  float bn = min(smax(smin(s4.y, Tr, uTrim), s4.y - cap, kc), hn);
  if (uBound == BOUND_PINNED) {
    vec4 pn = texelFetch(pin, p, 0);
    hn = pin_apply(hn, pn.x, pn.y);
    bn = min(bn, hn);
  }
  float ice = ice_top > -1.0e30 ? max(ice_top - hn, 0.0) : 0.0;
  float t1 = clamp((rw0 - ffm) / 0.12, 0.0, 1.0);
  float floorm = 1.0 - t1 * t1 * (3.0 - 2.0 * t1);
  float t2 = clamp((rw0 - 1.0) / 0.3, 0.0, 1.0);
  float trough = 1.0 - t2 * t2 * (3.0 - 2.0 * t2);
  imageStore(outS, p, vec4(hn, bn, rw0, ice));
  imageStore(outM, p, vec4(max(carved, 0.0), floorm * trough, trough * (1.0 - floorm), trough));
}
