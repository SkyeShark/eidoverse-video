/* crest: the maps read off the blur pyramid of a level's height (SURFACING_DESIGN.md 2.3, step 5), on the padded
   cell grid. Twin: surface/twins.py crest.

   crest    multi-scale convexity. Each octave s (1, 2, 4, 8, 16 cells) gives t_s = tanh((h - G_s h) / (tau s cell)):
            the height above the mean within s cells, against a relief ratio tau. A child level adds its parent's
            wider octaves (Kc: the parent's 16-cell term plus what the parent took from its own parent), so a ridge
            of the main level keeps its crest inside a hero window and the levels differ only by the child's finest
            octave. crest = clamp((sum of the five own terms + Kc) / uTerms, -1, 1): the mean over every octave the
            level holds (five own and one per coarser level), so it does not saturate on a deep hero level.
   valley   flat and low (an MRVBF-like index, Gallant & Dowling 2003). At each own octave of 1, 2, 4, 8 cells that
            is at least uSmin metres: flatness 1 / (1 + (S / t)^4) of the blurred height's slope S against a
            threshold t that falls with the scale (t = t_ref (s_ref / s)^0.63: MRVBF halves it per tripling), times
            lowness smoothstep(-1, 1, (G_2s h - G_s h) / (t s)): the ground below its wider mean. The largest over
            the octaves and the parent's wider ones (Kv: the parent's 8-cell term plus its own Kv).
   n20      the unit normal of the height blurred at 20 m (its x and y), or the parent's where 20 m is more than 16
            cells.
   steer    the unit downhill direction of the height blurred at 2 cells: what the gully filter follows where no
            routed flow vector is given.
   exposure max(0, -N . wind) on convex ground (crest > 0): the wind streaks' source. */
//! sampler hT              x: h, metres (less the level's reference height)
//! sampler pyrA            the blurs of h at 1, 2, 4 and 8 cells
//! sampler pyrB            x: the blur at 16 cells, y: at 20 metres
//! sampler parT            the parent's (Kc, Kv, n20 x, n20 y) at this grid's cells (read only with uHasParent)
//! image   outC rgba32f    crest, valley, n20 x, n20 y
//! image   outK rgba32f    Kc and Kv for the child level, steer x, steer y
//! image   outX rgba32f    x: wind exposure, y: the slope's tangent
//! uniform float uCell     metres
//! uniform float uTau      crest's relief ratio
//! uniform float uTerms    the octaves crest averages: 5 own plus one per coarser level (Kc's terms)
//! uniform float uSmin     valley's finest scale, metres
//! uniform vec2 uValley    (t_ref, s_ref): the flatness threshold (a tangent) at s_ref metres
//! uniform int uHasParent
//! uniform int uN20Own     1: n20 from pyrB.y; 0: the parent's
//! uniform vec2 uWind      the unit vector the wind blows toward (0, 0: none)

vec2 grad(sampler2D s, int c, ivec2 p, ivec2 n, float k) {
  float e = texelFetch(s, ivec2(min(p.x + 1, n.x - 1), p.y), 0)[c];
  float w = texelFetch(s, ivec2(max(p.x - 1, 0), p.y), 0)[c];
  float no = texelFetch(s, ivec2(p.x, min(p.y + 1, n.y - 1)), 0)[c];
  float so = texelFetch(s, ivec2(p.x, max(p.y - 1, 0)), 0)[c];
  return vec2(e - w, no - so) * k;
}

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(hT, 0);
  if (!inside(p, n)) return;
  float h = texelFetch(hT, p, 0).x;
  vec4 a = texelFetch(pyrA, p, 0);
  vec4 b = texelFetch(pyrB, p, 0);
  vec4 par = uHasParent == 1 ? texelFetch(parT, p, 0) : vec4(0.0);
  float k = 0.5 / uCell;

  float inv = 1.0 / (uTau * uCell);
  float t16 = tanh((h - b.x) * inv * 0.0625);
  float S = tanh((h - a.x) * inv) + tanh((h - a.y) * inv * 0.5) + tanh((h - a.z) * inv * 0.25)
          + tanh((h - a.w) * inv * 0.125) + t16 + par.x;
  float crest = clamp(S / uTerms, -1.0, 1.0);

  float V = 0.0;
  float V8 = 0.0;
  for (int j = 0; j < 4; j++) {
    float sig = float(1 << j) * uCell;
    if (sig < uSmin) continue;
    vec2 g = grad(pyrA, j, p, n, k);
    float t = uValley.x * pow(uValley.y / sig, 0.63);
    float r = length(g) / t;
    float flat_ = 1.0 / (1.0 + r * r * r * r);
    float nxt = j < 3 ? a[j + 1] : b.x;
    float v = flat_ * smoothstep(-1.0, 1.0, (nxt - a[j]) / (t * sig));
    V = max(V, v);
    if (j == 3) V8 = v;
  }
  float valley = max(V, par.y);

  vec2 n20 = par.zw;
  if (uN20Own == 1) {
    vec2 g = grad(pyrB, 1, p, n, k);
    n20 = -g / sqrt(1.0 + dot(g, g));
  }
  vec2 g2 = grad(pyrA, 1, p, n, k);
  float L = length(g2);
  vec2 steer = L > 1.0e-12 ? -g2 / L : vec2(0.0);

  vec2 gh = grad(hT, 0, p, n, k);
  float tanS = length(gh);
  vec2 nh = -gh / sqrt(1.0 + tanS * tanS);
  float ex = max(0.0, -(nh.x * uWind.x + nh.y * uWind.y)) * smoothstep(0.0, 0.4, crest);

  imageStore(outC, p, vec4(crest, valley, n20));
  imageStore(outK, p, vec4(t16 + par.x, max(par.y, V8), steer));
  imageStore(outX, p, vec4(ex, tanS, 0.0, 0.0));
}
