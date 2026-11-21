// Port of blender/eidoblend/terrain/surface/kernels/phacelle.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged (its block-comment continuation lines included). The changes are WGSL's: texelFetch is <name>_at(q),
// imageStore is out*_store, textureSize is <name>_size(), the uniforms are u.<name>; the GLSL's
// cell_at(sampler2D s, ivec2 P) is one function per sampler it reads (cell_at_steerT, cell_at_coverT, cell_at_gateT:
// WGSL passes no sampler to a function), the same body each; `vec4(equal(ivec4(0, 1, 2, 3), ivec4(ch)))` is a
// select() of the same comparison; the cd ternary is select(); `as` is a WGSL keyword, so as_ stays as_. The GLSL's
// /*__WORLD_NOISE__*/ marker (core/world_noise.GLSL_NOISE pasted in by surface/bake.py) is `//! include noise`: the
// port's kernels/noise.wgsl, the same lattice hash (eido_hash2) bit for bit.
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
//! include noise

const TAU: f32 = 6.28318530717959;

/* a cell-grid field at a detail texel: the cell itself at one texel per cell, bilinear at two */
fn cell_at_steerT(P: vec2<i32>) -> vec4<f32> {
  let n = steerT_size();
  if (u.uF == 1) { return steerT_at(clamp(P, vec2<i32>(0), n - 1)); }
  let c = (vec2<f32>(P) + 0.5) / f32(u.uF) - 0.5;
  let fl = floor(c);
  let t = c - fl;
  let i0 = clamp(vec2<i32>(fl), vec2<i32>(0), n - 1);
  let i1 = clamp(vec2<i32>(fl) + 1, vec2<i32>(0), n - 1);
  let v00 = steerT_at(i0);
  let v10 = steerT_at(vec2<i32>(i1.x, i0.y));
  let v01 = steerT_at(vec2<i32>(i0.x, i1.y));
  let v11 = steerT_at(i1);
  return mix(mix(v00, v10, t.x), mix(v01, v11, t.x), t.y);
}

fn cell_at_coverT(P: vec2<i32>) -> vec4<f32> {
  let n = coverT_size();
  if (u.uF == 1) { return coverT_at(clamp(P, vec2<i32>(0), n - 1)); }
  let c = (vec2<f32>(P) + 0.5) / f32(u.uF) - 0.5;
  let fl = floor(c);
  let t = c - fl;
  let i0 = clamp(vec2<i32>(fl), vec2<i32>(0), n - 1);
  let i1 = clamp(vec2<i32>(fl) + 1, vec2<i32>(0), n - 1);
  let v00 = coverT_at(i0);
  let v10 = coverT_at(vec2<i32>(i1.x, i0.y));
  let v01 = coverT_at(vec2<i32>(i0.x, i1.y));
  let v11 = coverT_at(i1);
  return mix(mix(v00, v10, t.x), mix(v01, v11, t.x), t.y);
}

fn cell_at_gateT(P: vec2<i32>) -> vec4<f32> {
  let n = gateT_size();
  if (u.uF == 1) { return gateT_at(clamp(P, vec2<i32>(0), n - 1)); }
  let c = (vec2<f32>(P) + 0.5) / f32(u.uF) - 0.5;
  let fl = floor(c);
  let t = c - fl;
  let i0 = clamp(vec2<i32>(fl), vec2<i32>(0), n - 1);
  let i1 = clamp(vec2<i32>(fl) + 1, vec2<i32>(0), n - 1);
  let v00 = gateT_at(i0);
  let v10 = gateT_at(vec2<i32>(i1.x, i0.y));
  let v01 = gateT_at(vec2<i32>(i0.x, i1.y));
  let v11 = gateT_at(i1);
  return mix(mix(v00, v10, t.x), mix(v01, v11, t.x), t.y);
}

fn kmain(P: vec2<i32>) {
  let nD = hgT_size();
  if (!inside(P, nD)) { return; }
  let hg = hgT_at(P);
  var d = cell_at_steerT(P).zw;
  let dl = length(d);
  d = select(vec2<f32>(0.0), d / dl, dl > 1.0e-12);
  let cov = cell_at_coverT(P);
  let gate = cell_at_gateT(P);
  let local = (vec2<f32>(P) + 0.5) * u.uTexel;
  let loose = smoothstep(u.uLoose.x, u.uLoose.y, cov.x - cov.y);
  let a_init = u.uInit.x * (1.0 + (u.uInit.y - 1.0) * loose);
  let sand = 1.0 - smoothstep(u.uInit.z, u.uInit.w, cov.y);
  let sc = 1.5 / u.uSpec.z;                    /* the depth kernel's sigma across the flow, lattice cells */
  let isc2 = 1.0 / (sc * sc);
  let s2 = u.uSpec.y;
  var relief = 0.0;
  var grad = vec2<f32>(0.0);
  var cn = 0.0;
  var cd = 0.0;
  for (var o = 0; o < u.uOct; o++) {
    let A = octT_at(vec2<i32>(2 * o, 0));
    let B = octT_at(vec2<i32>(2 * o + 1, 0));
    let lc = A.zw + local * B.x;
    let fl = floor(lc);
    let pf = lc - fl;
    let ic = vec2<i32>(A.xy) + vec2<i32>(fl);
    let dp = vec2<f32>(-d.y, d.x);
    let sd = dp * TAU;
    var ph = vec2<f32>(0.0);
    var ws = 0.0;
    var fs = 0.0;
    var ks = 0.0;
    var as_ = 0.0;
    var dk = vec2<f32>(0.0);
    var da = vec2<f32>(0.0);
    for (var i = -1; i <= 2; i++) {
      for (var j = -1; j <= 2; j++) {
        let r = eido_hash2(ic.x + i, ic.y + j);
        let e = eido_hash2(ic.x + i + 1013, ic.y + j - 7919);
        let e2 = eido_hash2(ic.x + i - 3571, ic.y + j + 2797);
        let v = pf - vec2<f32>(f32(i), f32(j)) - r * 0.5;
        let w = max(0.0, exp(dot(v, v) * -2.0) - 0.01111);
        let f = exp2(u.uSpec.x * e.x);
        let wave = dot(v, sd) * f + 0.25 * TAU;
        ph += vec2<f32>(cos(wave), sin(wave)) * w;
        ws += w;
        fs += w * f;
        let n = (e.y + e2.x) * 1.22474487;
        let a = exp(s2 * n - 0.5 * s2 * s2);
        let vc = dot(v, dp);
        let bump = max(0.0, 1.0 - dot(v, v) * (1.0 / 2.25));
        let ex = exp(-0.5 * vc * vc * isc2);
        let K = bump * bump * ex;
        let gk = (B.x * ex) * (bump * (-4.0 / 2.25) * v - (bump * bump * vc * isc2) * dp);
        ks += K;
        as_ += K * a;
        dk += gk;
        da += gk * a;
      }
    }
    let q = ph / ws;
    let mag = max(1.0 - u.uNorm, length(q));
    let c = q.x / mag;
    let s = q.y / mag;
    let g = -s * sd * (fs / ws) * B.x;
    let Am = (as_ + 1.0e-6) / (ks + 1.0e-6);
    let gA = (da - Am * dk) / (ks + 1.0e-6);
    let amp = B.y;
    let ab = max(amp, 1.0e-6);
    var W = smoothstep(0.5, 2.0, cov.w * B.x / a_init) * sand
            * (1.0 - smoothstep(u.uBury.x * ab, u.uBury.y * ab, cov.z));
    if (B.w > -0.5) {
      let ch = i32(B.w + 0.5);
      W *= dot(gate, select(vec4<f32>(0.0), vec4<f32>(1.0), vec4<i32>(0, 1, 2, 3) == vec4<i32>(ch)));
    }
    relief += amp * W * Am * c;
    grad += (amp * W) * (Am * g + c * gA);
    let k2 = amp * B.x * B.x;
    cn += k2 * W * Am * c;
    cd += k2;
    d = d + (u.uSteer * min(W * Am, 1.0)) * g / (B.x * TAU);
    d = d / max(length(d), 1.0e-12);
  }
  let slope = degrees(atan(hg.w));
  let cover_w = smoothstep(u.uCover.x, u.uCover.y, cov.x);
  let rock = smoothstep(u.uRockDeg.x, u.uRockDeg.y, slope) * (1.0 - cover_w);
  let soil = smoothstep(u.uSlope.x, u.uSlope.y, slope) * (1.0 - smoothstep(u.uSlope.z, u.uSlope.w, slope)) * (1.0 - rock);
  var rel = soil * relief;
  var gr = soil * grad;
  var cr = soil * select(0.0, cn / cd, cd > 0.0);
  if (u.uRockOn == 1) {
    let D = rockT_at(P).w;
    let De = rockT_at(vec2<i32>(min(P.x + 1, nD.x - 1), P.y)).w;
    let Dw = rockT_at(vec2<i32>(max(P.x - 1, 0), P.y)).w;
    let Dn = rockT_at(vec2<i32>(P.x, min(P.y + 1, nD.y - 1))).w;
    let Ds = rockT_at(vec2<i32>(P.x, max(P.y - 1, 0))).w;
    let nf = min(sqrt(1.0 + hg.w * hg.w), u.uNormalCap);
    rel += rock * nf * D;
    gr += rock * nf * vec2<f32>(De - Dw, Dn - Ds) * (0.5 / u.uTexel);
    cr += rock * clamp(-(De + Dw + Dn + Ds - 4.0 * D) / (4.0 * u.uRockRef), -1.0, 1.0);
  }
  let L2 = sqrt(1.0 + hg.y * hg.y + hg.z * hg.z);
  outD_store(P, vec4<f32>(-hg.y / L2, -hg.z / L2, gr));
  outR_store(P, vec4<f32>(rel, clamp(cr, -1.0, 1.0), hg.x + u.uStrength * rel, soil - rock));
}
