// Port of the tower loop of blender/eidoblend/terrain/solvers/karst.py evaluate() at f90c6fc ("towers on the common
// base"), as a kernel over the level's subsamples. numpy walks the towers whose box meets the window in index order,
// each over its own box of subsamples: rock = where(z > rock, z, rock), owner = t where it wins and the surface is
// its own, scree = max(scree, its talus cone). Here every subsample walks its 16 x 16 tile's list of those towers
// (solvers/karst.js towerTables: ascending, each with numpy's box), so it meets the same towers in the same order and
// keeps the same winner. The arithmetic is numpy's lines in their order, rounded as numpy rounds them
// (karst/precise.wgsl): its float32 lines one rounding per operation, division, sqrt and arctan2 correctly rounded;
// its float64 lines (np.interp of the wall tables, the fluting's and the talus gate's periodic noise, the
// smoothsteps) in double-float, rounded to float32 once. The benches' np.sin is the built-in (float32, as numpy's).
//
// Tables (solvers/karst.js towerTables), per tower t, 13 rows of `tw` (vec4):
//   0 cx_l cy_l R H              (cx_l = f32(cx - x0): the window-local centre)
//   1 ca sa el lean              (f32 cos/sin of the axis, f32(1 + elong))
//   2 cos(lean_dir) sin(lean_dir) floor (-1e30: none) npk
//   3 spur 2 (re, im), spur 3 (re, im)        4 spur 4, spur 5
//   5 scarp 0: cos(dir) sin(dir) cos(half) den       6 scarp 0 depth, scarp 1: cos(dir) sin(dir) cos(half)
//   7 scarp 1 den, depth; body_h body_R               8 body_tan B reach brow
//   9 wall-table entry, its length, flute period 1 (0: off), flute period 2 (0: off)
//   10 box i0 i1 j0 j1           11 f32(cap_top H - floor), f32(floor_rough H), f32(crown H), talus on (1 / 0)
//   12 f32(floor_rough body_h), f32(crown body_h), the plan's index of the tower, 0
// `ts` (u32), 4 per tower: the talus gate's salt, the two flutes' salts, 0
// `pk` (vec4), uK peaks x 5 rows per tower: (pdx pdy pc ps) (pe h r0 b) (rib 2 re im, rib 3 re im) (4, 5) (6, 7)
// `wt` (vec4), 3 rows per wall-table entry, float64 values as double-floats (hi, lo):
//   (D, D0)  (Z, slope over D)  (slope over D0, 0)        numpy's slopes: (Z[r + 1] - Z[r]) / (D[r + 1] - D[r])

//! sampler tw rgba32f
//! sampler ts r32ui
//! sampler pk rgba32f
//! sampler wt rgba32f
//! sampler bins r32ui        per tile: the list's start (row 0) and count (row 1)
//! sampler list r32ui        the towers of every tile, tile after tile
//! sampler axes rg32f        row 0: xs_l per column (f32(xs - x0)); row 1: ys_l per row
//! sampler lob
//! sampler jag
//! sampler ledge             (uLedge 1; else uLedgeK)
//! sampler bench             (uBench 1)
//! sampler pm                (uPM 1)
//! sampler rlump             the flanks' lumps and knobs (G.smooth): rough['lump'], rough['knob']
//! sampler rknob
//! sampler clump             the caps' lumps and knobs at the subsamples (cap_rough's fbm2 and pinnacles x patch)
//! sampler cknob
//! image   outR rg32f        x: rock (relative to the plain's level), y: scree
//! image   outO r32i         the owner: the tower whose wall or summit is the surface, -1 elsewhere
//! uniform int uTilesX
//! uniform int uK            peaks_max: the peak slots per tower in `pk`
//! uniform int uLedge
//! uniform int uBench
//! uniform int uPM
//! uniform float uLedgeK     f32(ledge_cover)
//! uniform float uTanUnder   f32(tan(85 deg))
//! uniform float uTanApron   f32(tan(apron_deg))
//! uniform float uPeakRough  f32(peak_rough); 0: none
//! uniform float uBenchK     f32(benches)
//! uniform float uBenchM     f32(bench_m)
//! uniform float uFluteM     fluting_m (float64) as hi, lo
//! uniform float uFluteMl
//! uniform float uFluteOff   0.55 x the flutes' weight sum (float64) as hi, lo
//! uniform float uFluteOffl
//! uniform float uGateA      the talus gate's smoothstep: f32(0.55 c) and f32(f32(0.55 c + 0.35) - f32(0.55 c)),
//! uniform float uGateDen    c = f32(1 - 2 apron_cover), as numpy's float32 scalars have them
//! include karst/lib
//! include detail/exact
//! include karst/precise

const TW: i32 = 13;
const PKR: i32 = 5;
const KDD_UP_A = vec2<f32>(0.3499999940395355, 5.9604645663569045e-9);      // _smoothstep(0.35, 0.75, .)
const KDD_UP_DEN = vec2<f32>(0.4000000059604645, -5.9604645663569045e-9);
const KDD_KB_A = vec2<f32>(0.9300000071525574, -7.1525572131747595e-9);      // _smoothstep(0.93, 0.72, .)
const KDD_KB_DEN = vec2<f32>(-0.20999999344348907, -6.556510889765832e-9);
const KDD_07 = vec2<f32>(0.699999988079071, 1.1920929132713809e-8);          // the flutes' weights
const KDD_03 = vec2<f32>(0.30000001192092896, -1.1920929132713809e-8);

fn T(t: i32, r: i32) -> vec4<f32> { return tw_at(vec2<i32>(t * TW + r, 0)); }
fn PK(t: i32, k: i32, r: i32) -> vec4<f32> { return pk_at(vec2<i32>((t * u.uK + k) * PKR + r, 0)); }

/** a double-float <= a float32 */
fn kdd_le(a: vec2<f32>, x: f32) -> bool { return a.x < x || (a.x == x && a.y <= 0.0); }

/** the wall table's D (or D0) of entry r */
fn WD(e: i32, use0: bool) -> vec2<f32> {
  let w = wt_at(vec2<i32>(3 * e, 0));
  return select(w.xy, w.zw, use0);
}

// np.interp(d, D, Z).astype(f32) on one tower's wall table, entries [off, off + len): numpy's arr_interp (its
// precomputed slopes, Z[0] below D[0], Z[last] from D[last] on) in double-float, rounded once
fn interp(d: f32, off: i32, len: i32, use0: bool) -> f32 {
  if (!kdd_le(WD(off, use0), d)) { return wt_at(vec2<i32>(3 * off + 1, 0)).x; }
  if (kdd_le(WD(off + len - 1, use0), d)) { return wt_at(vec2<i32>(3 * (off + len - 1) + 1, 0)).x; }
  var lo = 0;
  var hi = len - 1;
  loop {
    if (hi - lo <= 1) { break; }
    let mid = (lo + hi) / 2;
    if (kdd_le(WD(off + mid, use0), d)) { lo = mid; } else { hi = mid; }
  }
  let e = off + lo;
  let zs = wt_at(vec2<i32>(3 * e + 1, 0));
  let slope = select(zs.zw, wt_at(vec2<i32>(3 * e + 2, 0)).xy, use0);
  let v = kdd_add(kdd_mul(slope, kdd_add(kdd(d), -WD(e, use0))), zs.xy);
  return v.x;
}

/** f32(np.interp) blended by the ledges (wall_D's ledges where they hold, wall_D0 where they have broken off) */
fn wall(d: f32, off: i32, len: i32, lg: f32) -> f32 {
  let wl = interp(d, off, len, false);
  let w0 = interp(d, off, len, true);
  return kx(w0 + kx(kx(wl - w0) * lg));
}

fn kmain(p: vec2<i32>) {
  let n = outR_size();
  if (!inside(p, n)) { return; }
  kprecise(n);
  let tile = (p.y / 16) * u.uTilesX + p.x / 16;
  let start = i32(bins_at(vec2<i32>(tile, 0)));
  let count = i32(bins_at(vec2<i32>(tile, 1)));
  let xl = axes_at(vec2<i32>(p.x, 0)).x;
  let yl = axes_at(vec2<i32>(p.y, 1)).x;
  let LOB = lob_at(p).x;
  let jag = kx(1.0 + jag_at(p).x);
  var lg = u.uLedgeK;
  if (u.uLedge != 0) { lg = ledge_at(p).x; }
  var base = 0.0;
  if (u.uPM != 0) { base = pm_at(p).x; }
  let FM = vec2<f32>(u.uFluteM, u.uFluteMl);
  let FOFF = vec2<f32>(u.uFluteOff, u.uFluteOffl);
  var rock = KNEG;
  var scree = 0.0;
  var owner = -1;
  for (var e = start; e < start + count; e++) {
    let t = i32(list_at(vec2<i32>(e, 0)));
    let r10 = T(t, 10);
    if (p.x < i32(r10.x) || p.x >= i32(r10.y) || p.y < i32(r10.z) || p.y >= i32(r10.w)) { continue; }
    let r0 = T(t, 0);
    let r1 = T(t, 1);
    let r2 = T(t, 2);
    let dx = kx(xl - r0.x);
    let dy = kx(yl - r0.y);
    let r = ksqrt(kx(kx(dx * dx) + kx(dy * dy)));
    let ca = r1.x;
    let sa = r1.y;
    let el = r1.z;
    let ra = kdiv(kx(kx(dx * ca) + kx(dy * sa)), el);
    let rb = kx(kx(kx(dy * ca) - kx(dx * sa)) * el);
    let re = ksqrt(kx(kx(ra * ra) + kx(rb * rb)));
    let rinv = kdiv(1.0, max(r, 1e-3));
    let c1 = kx(dx * rinv);
    let s1 = kx(dy * rinv);
    var stretch = kx(1.0 + kx(r1.w * kx(kx(c1 * r2.x) + kx(s1 * r2.y))));
    // harmonics 2-5 by the angle-addition recurrences (no trigonometry per sample)
    let c2 = kx(kx(c1 * c1) - kx(s1 * s1));
    let s2 = kx(kx(2.0 * c1) * s1);
    let c3 = kx(kx(c2 * c1) - kx(s2 * s1));
    let s3 = kx(kx(s2 * c1) + kx(c2 * s1));
    let c4 = kx(kx(c2 * c2) - kx(s2 * s2));
    let s4 = kx(kx(2.0 * c2) * s2);
    let c5 = kx(kx(c4 * c1) - kx(s4 * s1));
    let s5 = kx(kx(s4 * c1) + kx(c4 * s1));
    let sp0 = T(t, 3);
    let sp1 = T(t, 4);
    stretch = kx(kx(stretch + kx(sp0.x * c2)) - kx(sp0.y * s2));
    stretch = kx(kx(stretch + kx(sp0.z * c3)) - kx(sp0.w * s3));
    stretch = kx(kx(stretch + kx(sp1.x * c4)) - kx(sp1.y * s4));
    stretch = kx(kx(stretch + kx(sp1.z * c5)) - kx(sp1.w * s5));
    // collapse scarps: the footprint pulled in over a sector, so the wall stands high there
    let r5 = T(t, 5);
    let r6 = T(t, 6);
    let r7 = T(t, 7);
    if (r6.x > 0.0) {
      let cosd = kx(kx(c1 * r5.x) + kx(s1 * r5.y));
      let uu = clamp(kdiv(kx(cosd - r5.z), r5.w), 0.0, 1.0);
      stretch = kx(stretch * kx(1.0 - kx(kx(kx(r6.x * uu) * uu) * kx(3.0 - kx(2.0 * uu)))));
    }
    if (r7.y > 0.0) {
      let cosd = kx(kx(c1 * r6.y) + kx(s1 * r6.z));
      let uu = clamp(kdiv(kx(cosd - r6.w), r7.x), 0.0, 1.0);
      stretch = kx(stretch * kx(1.0 - kx(kx(kx(r7.y * uu) * uu) * kx(3.0 - kx(2.0 * uu)))));
    }
    let R = r0.z;
    let H = r0.w;
    let rs = kx(kdiv(re, stretch) - LOB);
    var d_in = kx(R - rs);
    let r9 = T(t, 9);
    let saltT = ts_at(vec2<i32>(t * 4, 0));
    // vertical flutes: a periodic noise of the direction from the axis only (each octave the level resolves); numpy
    // takes the angle to float64: g = (theta + pi) / (2 pi) per, the noise and its sum in float64, flo to float32
    var flo = 0.0;
    var fluted = false;
    if (r9.z > 0.0 || r9.w > 0.0) {
      let th = kdd_add(kdd(katan2(dy, dx)), KDD_PI);
      var fl = vec2<f32>(0.0, 0.0);
      if (r9.z > 0.0) {
        let g = kdd_mul(kdd_div(th, KDD_2PI), kdd(r9.z));
        let nz = kdd_noise1p(g, i32(r9.z), ts_at(vec2<i32>(t * 4 + 1, 0)));
        fl = kdd_mul(KDD_07, kdd_add(kdd(1.0), -kdd_abs(nz)));
      }
      if (r9.w > 0.0) {
        let g = kdd_mul(kdd_div(th, KDD_2PI), kdd(r9.w));
        let nz = kdd_noise1p(g, i32(r9.w), ts_at(vec2<i32>(t * 4 + 2, 0)));
        fl = kdd_add(fl, kdd_mul(KDD_03, kdd_add(kdd(1.0), -kdd_abs(nz))));
      }
      flo = kdd_mul(FM, kdd_add(fl, -FOFF)).x;
      fluted = true;
      d_in = kx(d_in - flo);
    }
    // the wall: its table read at the distance inside the edge, the ledges where they hold; past the foot the rock
    // dips steeply under the alluvium
    let woff = i32(r9.x);
    let wlen = i32(r9.y);
    var wallz = wall(d_in, woff, wlen, lg);
    if (d_in < 0.0) { wallz = kx(d_in * u.uTanUnder); }
    // the summit: a block's cap, then the highest of the tower's peak cones
    let fl_t = r2.z;
    let isBlock = fl_t > -1.0e29;
    let r11 = T(t, 11);
    var summit = KNEG;
    if (isBlock) {
      let frac = clamp(kdiv(kdiv(d_in, R), jag), 0.0, 1.0);
      summit = kx(kx(fl_t + kx(r11.x * frac)) + kx(kx(r11.y * clump_at(p).x) + kx(r11.z * cknob_at(p).x)));
    }
    let npk = i32(r2.w);
    for (var k = 0; k < npk; k++) {
      let q0 = PK(t, k, 0);
      let q1 = PK(t, k, 1);
      let pdx = kx(dx - q0.x);
      let pdy = kx(dy - q0.y);
      let pu = kdiv(kx(kx(pdx * q0.z) + kx(pdy * q0.w)), q1.x);
      let pv = kx(kx(kx(pdy * q0.z) - kx(pdx * q0.w)) * q1.x);
      var rho = ksqrt(kx(kx(pu * pu) + kx(pv * pv)));
      let a23 = PK(t, k, 2);
      let a45 = PK(t, k, 3);
      let a67 = PK(t, k, 4);
      if (any(a23 != vec4<f32>(0.0)) || any(a45 != vec4<f32>(0.0)) || any(a67 != vec4<f32>(0.0))) {
        // the cone's ribs: its distance x g(theta), harmonics 2-7 by the angle-addition recurrences
        let rk = kdiv(1.0, max(rho, 1e-3));
        let k1 = kx(pu * rk);
        let l1 = kx(pv * rk);
        var cm = k1;
        var sm = l1;
        var g = 1.0;
        let amp = array<vec2<f32>, 6>(a23.xy, a23.zw, a45.xy, a45.zw, a67.xy, a67.zw);
        for (var m = 0; m < 6; m++) {
          let cn = kx(kx(cm * k1) - kx(sm * l1));
          let sn = kx(kx(sm * k1) + kx(cm * l1));
          cm = cn;
          sm = sn;
          g = kx(kx(g + kx(amp[m].x * cm)) - kx(amp[m].y * sm));
        }
        rho = kx(rho * g);
      }
      rho = kx(rho * jag);
      if (fluted) { rho = kx(rho + flo); }            /* the flutes run on up the peak's flanks */
      let x = kdiv(rho, q1.z);
      let b = q1.w;
      var z = 0.0;
      if (x <= 1.0) {
        z = kx(q1.y * kx(kx(1.0 - x) + kx(kx(b * x) * kx(1.0 - x))));
      } else {
        z = kx(q1.y * kx(-kx(1.0 + b) * kx(x - 1.0)));
      }
      summit = max(summit, z);
    }
    if (u.uPeakRough > 0.0 && !isBlock) {
      // lumps and knobs over the peak's upper flanks, fading in from 35 % of the height up
      let up = kdd_smoothstep(kdd(kdiv(summit, H)), KDD_UP_A, KDD_UP_DEN);
      summit = kx(summit + kx(kx(u.uPeakRough * up) * kx(kx(r11.y * rlump_at(p).x) + kx(r11.z * rknob_at(p).x))));
    }
    if (u.uBench != 0) {
      // the beds' benches across the summit's flanks, fading out over the top quarter
      let kb = kx(u.uBenchK * kdd_smoothstep(kdd(kdiv(summit, H)), KDD_KB_A, KDD_KB_DEN));
      let ph = kdiv(kx(kx(summit + bench_at(p).x) + base), u.uBenchM);
      summit = kx(summit - kx(kdiv(kx(kb * u.uBenchM), KTWO_PI) * sin(kx(KTWO_PI * ph))));
    }
    let r8 = T(t, 8);
    let brow = r8.w;
    var z = ksmin_x(wallz, summit, brow);
    var d_out_edge = d_in;
    var own = d_in > 0.0;
    if (r7.z > 0.0) {
      // the massif body: the tower's own wall table at its wider footprint, meeting a rough skirt rising inward
      let Hb = r7.z;
      let Rb = r7.w;
      var d_b = kx(Rb - rs);
      if (fluted) { d_b = kx(d_b - flo); }
      var wb = wall(d_b, woff, wlen, lg);
      if (d_b < 0.0) { wb = kx(d_b * u.uTanUnder); }
      let r12 = T(t, 12);
      let top_b = kx(kx(Hb + kx(max(d_b, 0.0) * r8.x)) + kx(kx(r12.x * rlump_at(p).x) + kx(r12.y * rknob_at(p).x)));
      let zb = ksmin_x(wb, top_b, brow);
      own = (own && (z >= zb)) || ((d_b > 0.0) && (wb < kx(top_b - brow)) && (zb > z));
      z = max(z, zb);
      d_out_edge = max(d_in, d_b);
    }
    z = kx(z + base);
    let win = z > rock;
    if (win) {
      rock = z;
      if (own) { owner = i32(T(t, 12).z); }                /* the plan's index of the tower (tower_id) */
    }
    // a talus cone at the foot under some of the tower's azimuths (its gullies' rockfall): numpy's g in float32,
    // its noise and the gate's smoothstep in float64, the gate to float32
    if (r11.w > 0.0) {
      let g = kx(kdiv(kx(katan2(dy, dx) + KPI), KTWO_PI) * 7.0);
      let az = kdd_noise1p(kdd(g), 7, saltT);
      let gate = kdd_smoothstep(az, kdd(u.uGateA), kdd(u.uGateDen));
      let Bt = kx(r8.y * gate);
      let d_out = max(-d_out_edge, 0.0);
      var cone = kx(Bt - kx(d_out * u.uTanApron));
      if (!(d_out <= r8.z)) { cone = KNEG; }
      cone = kx(cone + base);
      if (cone > scree) { scree = cone; }
    }
  }
  // the clusters' common base: flat at its height inside a cluster, under the peaks
  if (u.uPM != 0 && base > 0.5) { rock = max(rock, base); }
  outR_store(p, vec4<f32>(rock, scree, 0.0, 0.0));
  outO_store(p, owner);
}
