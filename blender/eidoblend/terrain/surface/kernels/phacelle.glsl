/* phacelle: the relief below the cell, on the detail grid (SURFACING_DESIGN.md 2.3, step 3). Twin: surface/twins.py
   phacelle (solvers/detail.py's phacelle_noise arithmetic, octave by octave, with the changes below). The octave
   table is built on the CPU in float64, an integer lattice base plus a fraction, as the breakup kernel's terms are,
   so float32 keeps the stripes' phase far from the origin. surface/bake.py puts core/world_noise.GLSL_NOISE (Ekigar's
   lattice hash, bit for bit with numpy) in the marked place.

   Gullies, a spectrum. The octaves are keyed by world wavelength and run from the terrain's top octave (the first
   under 12 cells of its main level, 256 m at most) down to 2 texels, the same octaves and lattices on every level,
   so a child carries its parent's wavelengths and adds the finer ones (each level steers them down its own fall
   line, so the gullies' courses differ a little between levels). Stripes run along the downhill
   direction (the routed flow vector where the level has one, else the descent of the height blurred at 2 cells);
   every octave turns the next into its own gully walls (steer), so small gullies branch off the big ones. One octave
   of equal stripes reads as a corrugation (a washboard on a smooth stamped cone, 11-20), so each octave varies:
   - spacing: each lattice point's stripes have their own wavelength, 2^(uSpec.x u) of the octave's, u in [-1, 1);
   - depth: each point carries its gullies' depth, log-normal of spread uSpec.y (most faint, a few deep), blended
     with a kernel uSpec.z times longer down the flow than across it (inside the 1.5-cell disk every point of the
     4 x 4 neighbourhood covers, as the filter's own weights are, so nothing jumps where the neighbourhood moves),
     so a gully keeps its depth for a few wavelengths and its neighbours differ;
   - water: an octave's gullies start where the specific catchment (coverT.w, metres) reaches uInit.x times its
     wavelength (uInit.y times that on loose debris, deposit and talus over uLoose metres: it swallows the runoff),
     so the slopes below divides and short rises stay smooth and the gullies grow downslope;
   - cover: none on sand (coverT.y over uInit.zw metres: dunes do not gully), and each octave is buried under a
     snowpack (coverT.z) of uBury times its amplitude;
   - the geometry: an octave the level's cells can hold (B.w >= 0) steps back where the level's own height already
     has relief at that scale (gateT, channel B.w: 1 smooth, 0 where the valleys are), so a gullied DEM is not
     gullied twice.
   They are masked to soil: slopes fading in over uSlope.xy and out over uSlope.zw degrees, not on bare rock.
   Rock. On bare rock (slope over uRockDeg, no loose cover) the relief is the breakup strength's next band instead
   (rockT.w: solvers/detail.py's relief D of the rock noise and joints the level's cells cannot resolve, metres along
   the normal): ribs and joints.

   Out: outD = (the field normal's x and y, the relief's gradient gx and gy in metres of height per metre);
        outR = (the relief in metres, crease, the height plus uStrength x the relief (what the cavity march reads),
                soil weight - rock weight).
   crease is the relief's curvature, normalised: for the gullies, each octave's shape weighted by its local depth
   and by amplitude / wavelength^2 (its Laplacian's weight), floors -1 and crests +1; for rock, minus the five-point
   Laplacian of D over 4 uRockRef. */
//! sampler hgT             field_normal's output on the detail grid: h, dh/dx, dh/dy, tan(slope)
//! sampler steerT          the cell grid: z, w: the unit downhill direction
//! sampler octT            two texels per octave: (lattice base x, base y, fraction x, fraction y),
/*                          (1 / wavelength, amplitude in metres, 1, the geometry gate's channel or -1) */
//! sampler rockT           the detail grid: w: the rock relief D, metres (read only with uRockOn)
//! sampler coverT          the cell grid: loose cover (deposit + talus + sand), sand, snowpack (metres), specific
/*                          catchment (metres) */
//! sampler gateT           the cell grid: the geometry gates, one per crest scale (8, 16, 32, 64 m)
//! image   outD rgba32f
//! image   outR rgba32f
//! uniform int uOct        octaves in the table
//! uniform float uTexel    the detail grid's texel, metres
//! uniform int uF          detail texels per cell: 1 or 2
//! uniform float uSteer    how much each octave turns the next
//! uniform float uNorm     the filter's amplitude normalisation
//! uniform vec4 uSlope     the soil mask, degrees: in over x..y, out over z..w
//! uniform vec2 uRockDeg   bare rock: a smoothstep of the slope, degrees
//! uniform vec2 uCover     loose cover that hides the rock: a smoothstep, metres
//! uniform float uNormalCap    the largest stretch of a normal displacement into height
//! uniform float uRockRef  the rock relief's amplitude, metres (crease's scale)
//! uniform int uRockOn
//! uniform float uStrength the relief's share in outR.z
//! uniform vec4 uSpec      the spectrum: spacing jitter (log2), depth spread (log-normal), depth kernel length, 0
//! uniform vec4 uInit      initiation: catchment over wavelength, its factor on loose debris, sand (smoothstep, m)
//! uniform vec2 uLoose     loose debris (deposit + talus) that swallows the runoff: a smoothstep, metres
//! uniform vec2 uBury      a snowpack of x..y times an octave's amplitude buries it

/*__WORLD_NOISE__*/

const float TAU = 6.28318530717959;

/* a cell-grid field at a detail texel: the cell itself at one texel per cell, bilinear at two */
vec4 cell_at(sampler2D s, ivec2 P) {
  ivec2 n = textureSize(s, 0);
  if (uF == 1) return texelFetch(s, clamp(P, ivec2(0), n - 1), 0);
  vec2 c = (vec2(P) + 0.5) / float(uF) - 0.5;
  vec2 fl = floor(c);
  vec2 t = c - fl;
  ivec2 i0 = clamp(ivec2(fl), ivec2(0), n - 1);
  ivec2 i1 = clamp(ivec2(fl) + 1, ivec2(0), n - 1);
  vec4 v00 = texelFetch(s, i0, 0);
  vec4 v10 = texelFetch(s, ivec2(i1.x, i0.y), 0);
  vec4 v01 = texelFetch(s, ivec2(i0.x, i1.y), 0);
  vec4 v11 = texelFetch(s, i1, 0);
  return mix(mix(v00, v10, t.x), mix(v01, v11, t.x), t.y);
}

void main() {
  ivec2 P = ivec2(gl_GlobalInvocationID.xy);
  ivec2 nD = textureSize(hgT, 0);
  if (!inside(P, nD)) return;
  vec4 hg = texelFetch(hgT, P, 0);
  vec2 d = cell_at(steerT, P).zw;
  float dl = length(d);
  d = dl > 1.0e-12 ? d / dl : vec2(0.0);
  vec4 cov = cell_at(coverT, P);
  vec4 gate = cell_at(gateT, P);
  vec2 local = (vec2(P) + 0.5) * uTexel;
  float loose = smoothstep(uLoose.x, uLoose.y, cov.x - cov.y);
  float a_init = uInit.x * (1.0 + (uInit.y - 1.0) * loose);
  float sand = 1.0 - smoothstep(uInit.z, uInit.w, cov.y);
  float sc = 1.5 / uSpec.z;                    /* the depth kernel's sigma across the flow, lattice cells */
  float isc2 = 1.0 / (sc * sc);
  float s2 = uSpec.y;
  float relief = 0.0;
  vec2 grad = vec2(0.0);
  float cn = 0.0;
  float cd = 0.0;
  for (int o = 0; o < uOct; o++) {
    vec4 A = texelFetch(octT, ivec2(2 * o, 0), 0);
    vec4 B = texelFetch(octT, ivec2(2 * o + 1, 0), 0);
    vec2 lc = A.zw + local * B.x;
    vec2 fl = floor(lc);
    vec2 pf = lc - fl;
    ivec2 ic = ivec2(A.xy) + ivec2(fl);
    vec2 dp = vec2(-d.y, d.x);
    vec2 sd = dp * TAU;
    vec2 ph = vec2(0.0);
    float ws = 0.0;
    float fs = 0.0;
    float ks = 0.0;
    float as_ = 0.0;
    vec2 dk = vec2(0.0);
    vec2 da = vec2(0.0);
    for (int i = -1; i <= 2; i++) {
      for (int j = -1; j <= 2; j++) {
        vec2 r = eido_hash2(ic.x + i, ic.y + j);
        vec2 e = eido_hash2(ic.x + i + 1013, ic.y + j - 7919);
        vec2 e2 = eido_hash2(ic.x + i - 3571, ic.y + j + 2797);
        vec2 v = pf - vec2(float(i), float(j)) - r * 0.5;
        float w = max(0.0, exp(dot(v, v) * -2.0) - 0.01111);
        float f = exp2(uSpec.x * e.x);
        float wave = dot(v, sd) * f + 0.25 * TAU;
        ph += vec2(cos(wave), sin(wave)) * w;
        ws += w;
        fs += w * f;
        float n = (e.y + e2.x) * 1.22474487;
        float a = exp(s2 * n - 0.5 * s2 * s2);
        float vc = dot(v, dp);
        float bump = max(0.0, 1.0 - dot(v, v) * (1.0 / 2.25));
        float ex = exp(-0.5 * vc * vc * isc2);
        float K = bump * bump * ex;
        vec2 gk = (B.x * ex) * (bump * (-4.0 / 2.25) * v - (bump * bump * vc * isc2) * dp);
        ks += K;
        as_ += K * a;
        dk += gk;
        da += gk * a;
      }
    }
    vec2 q = ph / ws;
    float mag = max(1.0 - uNorm, length(q));
    float c = q.x / mag;
    float s = q.y / mag;
    vec2 g = -s * sd * (fs / ws) * B.x;
    float Am = (as_ + 1.0e-6) / (ks + 1.0e-6);
    vec2 gA = (da - Am * dk) / (ks + 1.0e-6);
    float amp = B.y;
    float ab = max(amp, 1.0e-6);
    float W = smoothstep(0.5, 2.0, cov.w * B.x / a_init) * sand
              * (1.0 - smoothstep(uBury.x * ab, uBury.y * ab, cov.z));
    if (B.w > -0.5) {
      int ch = int(B.w + 0.5);
      W *= dot(gate, vec4(equal(ivec4(0, 1, 2, 3), ivec4(ch))));
    }
    relief += amp * W * Am * c;
    grad += (amp * W) * (Am * g + c * gA);
    float k2 = amp * B.x * B.x;
    cn += k2 * W * Am * c;
    cd += k2;
    d = d + (uSteer * min(W * Am, 1.0)) * g / (B.x * TAU);
    d = d / max(length(d), 1.0e-12);
  }
  float slope = degrees(atan(hg.w));
  float cover_w = smoothstep(uCover.x, uCover.y, cov.x);
  float rock = smoothstep(uRockDeg.x, uRockDeg.y, slope) * (1.0 - cover_w);
  float soil = smoothstep(uSlope.x, uSlope.y, slope) * (1.0 - smoothstep(uSlope.z, uSlope.w, slope)) * (1.0 - rock);
  float rel = soil * relief;
  vec2 gr = soil * grad;
  float cr = soil * (cd > 0.0 ? cn / cd : 0.0);
  if (uRockOn == 1) {
    float D = texelFetch(rockT, P, 0).w;
    float De = texelFetch(rockT, ivec2(min(P.x + 1, nD.x - 1), P.y), 0).w;
    float Dw = texelFetch(rockT, ivec2(max(P.x - 1, 0), P.y), 0).w;
    float Dn = texelFetch(rockT, ivec2(P.x, min(P.y + 1, nD.y - 1)), 0).w;
    float Ds = texelFetch(rockT, ivec2(P.x, max(P.y - 1, 0)), 0).w;
    float nf = min(sqrt(1.0 + hg.w * hg.w), uNormalCap);
    rel += rock * nf * D;
    gr += rock * nf * vec2(De - Dw, Dn - Ds) * (0.5 / uTexel);
    cr += rock * clamp(-(De + Dw + Dn + Ds - 4.0 * D) / (4.0 * uRockRef), -1.0, 1.0);
  }
  float L2 = sqrt(1.0 + hg.y * hg.y + hg.z * hg.z);
  imageStore(outD, P, vec4(-hg.y / L2, -hg.z / L2, gr));
  imageStore(outR, P, vec4(rel, clamp(cr, -1.0, 1.0), hg.x + uStrength * rel, soil - rock));
}
