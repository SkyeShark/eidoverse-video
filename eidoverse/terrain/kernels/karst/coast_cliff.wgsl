// Port of blender/eidoblend/terrain/solvers/coast.py op_coast at f90c6fc, from "the face" to the deposits (with
// face_profile, beach_profile, compose's smooth_min and smooth_max), as a kernel over a level's cells. numpy's float64
// is float32 here; np.interp of the rock column's table (column_table, made on the CPU in doubles) is a lookup on
// its uniform stratigraphic heights and a binary search of its runs; tan of the per-cell face angle is the GPU's.
//     H      = land - sea;  t_h = clip(talus_frac max(H, 0) clip(1 + 0.45 n_talus, 0.3, 1.7), 0, talus_max_m)
//     foot   = sea + platform_top_m + t_h
//     face   = face_profile(sd, foot - sea, theta, column, col_off) + sea   (the knob's own wall where stacks stand)
//     y      = max(-sd, 0);  platform = smooth_max(sea + platform_top_m - y tan(platform_slope), sea - sea_floor_m, 4)
//              + platform_rough_m n_rough
//     rock   = min(smooth_min(land, max(face, platform), top_round_m), land)
//     apron  = foot - y tan(talus) - back, back = max(sd, 0) tan(talus); with the scars' debris lobes
//     shingle (exposed coast) and the Dean beach (sheltered bays, beach_amt = 1 - smoothstep(be0, be1, E))
//     h      = max(rock, max(apron, shingle)) + beach_amt max(beach - h, 0)
// outA: (h, rock, apron_part, deposit_add); outB: (wear_add, changed, the face's Sc value, col_off).

//! sampler land
//! sampler sd
//! sampler theta
//! sampler sw                the stacks' knob weight (uFlags 1)
//! sampler nt                the talus noise (uFlags 2)
//! sampler nr                the platform's noise (uFlags 4)
//! sampler bite
//! sampler E
//! sampler nw                the shingle width's noise (uFlags 8)
//! sampler col rg32f         the rock column's table: (zs, run) per row (uFlags 16)
//! sampler axes rg32f        row 0: X dx_ per column; row 1: Y dy_ per row (the beds' dip direction, metres)
//! image   outA rgba32f
//! image   outB rgba32f
//! uniform int uFlags        1 stacks' weight, 2 talus noise, 4 platform noise, 8 shingle noise, 16 a column, 32 scars
//! uniform int uNC           the column table's rows
//! uniform float uSea
//! uniform float uTalusFrac
//! uniform float uTalusMax
//! uniform float uPlatTop
//! uniform float uPlatTan    tan(platform_slope_deg)
//! uniform float uSeaFloor
//! uniform float uRoughM     platform_rough_m
//! uniform float uTopRound
//! uniform float uTanR       tan(talus_deg)
//! uniform float uScarDebris
//! uniform float uTanDebris
//! uniform float uDip        tan(column_dip_deg)
//! uniform float uZlo        the column table's first height and step
//! uniform float uDz
//! uniform float uBe0
//! uniform float uBe1
//! uniform float uShW        max(shingle_w_m, 1e-3)
//! uniform float uShVar
//! uniform float uShCrest
//! uniform float uShBerm
//! uniform float uBerm       beach_profile(y, P, 1)'s constants (doubles on the CPU): the berm's height ...
//! uniform float uBack       ... the dry backshore's width ...
//! uniform float uYw         ... the waterline's distance from the foot ...
//! uniform float uTanFace    ... tan(beach_face_deg) ...
//! uniform float uDeanA      ... and the Dean profile's A
//! include karst/lib

// np.interp(x, zs, run) on the column's uniform heights
fn run_at(x: f32) -> f32 {
  let first = col_at(vec2<i32>(0, 0)).xy;
  let last = col_at(vec2<i32>(u.uNC - 1, 0)).xy;
  if (!(x >= first.x)) { return first.y; }
  if (x >= last.x) { return last.y; }
  let j = clamp(i32(floor((x - u.uZlo) / u.uDz)), 0, u.uNC - 2);
  let a = col_at(vec2<i32>(j, 0)).xy;
  let b = col_at(vec2<i32>(j + 1, 0)).xy;
  return (b.y - a.y) / (b.x - a.x) * (x - a.x) + a.y;
}

// np.interp(r, run, zs): a binary search of the runs
fn z_at(r: f32) -> f32 {
  let first = col_at(vec2<i32>(0, 0)).xy;
  let last = col_at(vec2<i32>(u.uNC - 1, 0)).xy;
  if (!(r >= first.y)) { return first.x; }
  if (r >= last.y) { return last.x; }
  var lo = 0;
  var hi = u.uNC - 1;
  loop {
    if (hi - lo <= 1) { break; }
    let mid = (lo + hi) / 2;
    if (col_at(vec2<i32>(mid, 0)).y <= r) { lo = mid; } else { hi = mid; }
  }
  let a = col_at(vec2<i32>(lo, 0)).xy;
  let b = col_at(vec2<i32>(lo + 1, 0)).xy;
  return (b.x - a.x) / (b.y - a.y) * (r - a.y) + a.x;
}

// compose.py smooth_min (C1, width k)
fn smin(a: f32, b: f32, k: f32) -> f32 {
  if (k <= 0.0) { return min(a, b); }
  let hh = max(k - abs(a - b), 0.0) / k;
  return min(a, b) - hh * hh * k * 0.25;
}

// a profile of one angle (degrees): foot + s tan(theta)
fn single(s: f32, foot: f32, th: f32) -> f32 { return foot + s * tan(th * 0.017453292519943295); }

fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  let fl = u.uFlags;
  let land = land_at(p).x;
  let sd = sd_at(p).x;
  let th = theta_at(p).x;
  let H = land - u.uSea;
  var tn = 1.0;
  if ((fl & 2) != 0) { tn = clamp(1.0 + 0.45 * nt_at(p).x, 0.3, 1.7); }
  let t_h = clamp(u.uTalusFrac * max(H, 0.0) * tn, 0.0, u.uTalusMax);
  let foot = u.uSea + u.uPlatTop + t_h;
  let footr = foot - u.uSea;
  var colOff = 0.0;
  var face = 0.0;
  if ((fl & 16) != 0) {
    colOff = -u.uDip * (axes_at(vec2<i32>(p.x, 0)).x + axes_at(vec2<i32>(p.y, 1)).x);
    let r0 = run_at(footr - colOff);
    var z = z_at(r0 + sd) + colOff;
    if (sd < 0.0) { z = footr + sd * 10.0; }
    face = z + u.uSea;
    if ((fl & 1) != 0) {
      let sw = sw_at(p).x;
      face = face + sw * (single(sd, footr, th) + u.uSea - face);
    }
  } else {
    face = single(sd, footr, th) + u.uSea;
  }
  // erosion: the land above the face and the wave-cut platform is cut away, the cliff top rounded
  let y = max(-sd, 0.0);
  var rough = 0.0;
  if ((fl & 4) != 0) { rough = u.uRoughM * nr_at(p).x; }
  var platform = u.uSea + u.uPlatTop - y * u.uPlatTan;
  platform = -smin(-platform, -(u.uSea - u.uSeaFloor), 4.0) + rough;
  let cutProf = max(face, platform);
  var rock = select(min(land, cutProf), smin(land, cutProf, u.uTopRound), u.uTopRound > 0.0);
  rock = min(rock, land);
  // deposition at the foot: the talus apron, the scars' debris lobes, the shingle beach, the sand beach
  let back = max(sd, 0.0) * u.uTanR;
  var apron = foot - y * u.uTanR - back;
  let bt = bite_at(p).x;
  if ((fl & 32) != 0 && bt > 0.05) {
    let lobe = u.uSea + u.uPlatTop + u.uScarDebris * bt - y * u.uTanDebris - back;
    apron = max(apron, lobe);
  }
  let beachAmt = 1.0 - ksmoothstep(u.uBe0, u.uBe1, E_at(p).x);
  let exposed = 1.0 - beachAmt;
  var wsh = u.uShW;
  if ((fl & 8) != 0) { wsh = wsh * exp(clamp(u.uShVar * nw_at(p).x, -1.2, 0.6)); }
  let crest = u.uShCrest;
  let berm = u.uShBerm * wsh;
  let tanf = (crest + 0.6) / max(wsh - berm, 1e-3);
  let shz = select(crest - (y - berm) * tanf, crest, y <= berm);
  var shingle = bitcast<f32>(0xff800000u);
  if (shz > -0.6 && exposed > 0.0) { shingle = u.uSea + exposed * shz - back; }
  // beach_profile(y, P, 1): the dry backshore at the berm, the beach face down to the waterline, then Dean's profile
  var bz = u.uBerm - (y - u.uBack) * u.uTanFace;
  if (y <= u.uBack) { bz = u.uBerm; }
  if (y > u.uYw) { bz = -u.uDeanA * pow(max(y - u.uYw, 0.0), 2.0 / 3.0); }
  let beach = u.uSea + bz - back;
  var h = max(rock, max(apron, shingle));
  h = h + beachAmt * max(beach - h, 0.0);
  let changed = abs(land - h) > 1e-3;
  var apronPart = 0.0;
  var depAdd = 0.0;
  var wearAdd = 0.0;
  if (changed) {
    apronPart = max(min(h, apron) - rock, 0.0);
    depAdd = max(h - rock - apronPart, 0.0);
    wearAdd = max(land - rock, 0.0);
  }
  let scFace = tan(clamp(th, 30.0, 89.0) * 0.017453292519943295);
  let sc = select(u.uTanR, scFace, changed && sd >= 0.0);
  outA_store(p, vec4<f32>(h, rock, apronPart, depAdd));
  outB_store(p, vec4<f32>(wearAdd, select(0.0, 1.0, changed), sc, colOff));
}
