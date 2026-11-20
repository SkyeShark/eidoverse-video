// Port of the tower loop of blender/eidoblend/terrain/solvers/karst.py evaluate() at f90c6fc ("towers on the common
// base"), as a kernel over the level's subsamples. numpy walks the towers whose box meets the window in index order,
// each over its own box of subsamples: rock = where(z > rock, z, rock), owner = t where it wins and the surface is
// its own, scree = max(scree, its talus cone). Here every subsample walks its 16 x 16 tile's list of those towers
// (solvers/karst.js towerBins: ascending, each with numpy's box), so it meets the same towers in the same order and
// keeps the same winner. The arithmetic is numpy's float32 lines, in their order; numpy's float64 parts (np.interp of
// the wall tables, the fluting's and the talus gate's periodic noise, the smoothsteps) are float32 here.
//
// Tables (solvers/karst.js towerTables), per tower t, 13 rows of `tw` (vec4):
//   0 cx_l cy_l R H              (cx_l = f32(cx - x0): the window-local centre)
//   1 ca sa el lean              (f32 cos/sin of the axis, f32(1 + elong))
//   2 cos(lean_dir) sin(lean_dir) floor (-1e30: none) npk
//   3 spur 2 (re, im), spur 3 (re, im)        4 spur 4, spur 5
//   5 scarp 0: cos(dir) sin(dir) cos(half) den       6 scarp 0 depth, scarp 1: cos(dir) sin(dir) cos(half)
//   7 scarp 1 den, depth; body_h body_R               8 body_tan B reach brow
//   9 wall-table row, its length, flute period 1 (0: off), flute period 2 (0: off)
//   10 box i0 i1 j0 j1           11 f32(cap_top H - floor), f32(floor_rough H), f32(crown H), talus on (1 / 0)
//   12 f32(floor_rough body_h), f32(crown body_h), 0, 0               (rough_box's amplitudes for the body)
// `ts` (u32), 4 per tower: the talus gate's salt, the two flutes' salts, 0
// `pk` (vec4), uK peaks x 5 rows per tower: (pdx pdy pc ps) (pe h r0 b) (rib 2 re im, rib 3 re im) (4, 5) (6, 7)
// `wt` (vec4): the wall tables' rows (D, D0, Z, 0)

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
//! uniform float uFluteM     fluting_m
//! uniform float uApronC     f32(1 - 2 apron_cover)
//! include karst/lib

const TW: i32 = 13;
const PKR: i32 = 5;

fn T(t: i32, r: i32) -> vec4<f32> { return tw_at(vec2<i32>(t * TW + r, 0)); }
fn PK(t: i32, k: i32, r: i32) -> vec4<f32> { return pk_at(vec2<i32>((t * u.uK + k) * PKR + r, 0)); }

// np.interp(d, D, Z) on one tower's wall table rows [off, off + len): Z[0] below D[0], Z[last] past D[last]
fn interp(d: f32, off: i32, len: i32, use0: bool) -> f32 {
  let first = wt_at(vec2<i32>(off, 0));
  let last = wt_at(vec2<i32>(off + len - 1, 0));
  let x0 = select(first.x, first.y, use0);
  let xl = select(last.x, last.y, use0);
  if (!(d >= x0)) { return first.z; }
  if (d >= xl) { return last.z; }
  var lo = 0;
  var hi = len - 1;
  loop {
    if (hi - lo <= 1) { break; }
    let mid = (lo + hi) / 2;
    let r = wt_at(vec2<i32>(off + mid, 0));
    if (select(r.x, r.y, use0) <= d) { lo = mid; } else { hi = mid; }
  }
  let a = wt_at(vec2<i32>(off + lo, 0));
  let b = wt_at(vec2<i32>(off + lo + 1, 0));
  let xa = select(a.x, a.y, use0);
  let xb = select(b.x, b.y, use0);
  let slope = (b.z - a.z) / (xb - xa);
  return slope * (d - xa) + a.z;
}

fn kmain(p: vec2<i32>) {
  let n = outR_size();
  if (!inside(p, n)) { return; }
  let tile = (p.y / 16) * u.uTilesX + p.x / 16;
  let start = i32(bins_at(vec2<i32>(tile, 0)));
  let count = i32(bins_at(vec2<i32>(tile, 1)));
  let xl = axes_at(vec2<i32>(p.x, 0)).x;
  let yl = axes_at(vec2<i32>(p.y, 1)).x;
  let LOB = lob_at(p).x;
  let jag = 1.0 + jag_at(p).x;
  var lg = u.uLedgeK;
  if (u.uLedge != 0) { lg = ledge_at(p).x; }
  var base = 0.0;
  if (u.uPM != 0) { base = pm_at(p).x; }
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
    let dx = xl - r0.x;
    let dy = yl - r0.y;
    let r = sqrt(dx * dx + dy * dy);
    let ca = r1.x;
    let sa = r1.y;
    let el = r1.z;
    let ra = (dx * ca + dy * sa) / el;
    let rb = (dy * ca - dx * sa) * el;
    let re = sqrt(ra * ra + rb * rb);
    let rinv = 1.0 / max(r, 1e-3);
    let c1 = dx * rinv;
    let s1 = dy * rinv;
    var stretch = 1.0 + r1.w * (c1 * r2.x + s1 * r2.y);
    // harmonics 2-5 by the angle-addition recurrences (no trigonometry per sample)
    let c2 = c1 * c1 - s1 * s1;
    let s2 = 2.0 * c1 * s1;
    let c3 = c2 * c1 - s2 * s1;
    let s3 = s2 * c1 + c2 * s1;
    let c4 = c2 * c2 - s2 * s2;
    let s4 = 2.0 * c2 * s2;
    let c5 = c4 * c1 - s4 * s1;
    let s5 = s4 * c1 + c4 * s1;
    let sp0 = T(t, 3);
    let sp1 = T(t, 4);
    stretch = stretch + sp0.x * c2 - sp0.y * s2;
    stretch = stretch + sp0.z * c3 - sp0.w * s3;
    stretch = stretch + sp1.x * c4 - sp1.y * s4;
    stretch = stretch + sp1.z * c5 - sp1.w * s5;
    // collapse scarps: the footprint pulled in over a sector, so the wall stands high there
    let r5 = T(t, 5);
    let r6 = T(t, 6);
    let r7 = T(t, 7);
    if (r6.x > 0.0) {
      let cosd = c1 * r5.x + s1 * r5.y;
      let uu = clamp((cosd - r5.z) / r5.w, 0.0, 1.0);
      stretch = stretch * (1.0 - r6.x * uu * uu * (3.0 - 2.0 * uu));
    }
    if (r7.y > 0.0) {
      let cosd = c1 * r6.y + s1 * r6.z;
      let uu = clamp((cosd - r6.w) / r7.x, 0.0, 1.0);
      stretch = stretch * (1.0 - r7.y * uu * uu * (3.0 - 2.0 * uu));
    }
    let R = r0.z;
    let H = r0.w;
    let rs = re / stretch - LOB;
    var d_in = R - rs;
    let r9 = T(t, 9);
    let saltT = ts_at(vec2<i32>(t * 4, 0));
    // vertical flutes: a periodic noise of the direction from the axis only (each octave the level resolves)
    var flo = 0.0;
    var fluted = false;
    if (r9.z > 0.0 || r9.w > 0.0) {
      let theta = atan2(dy, dx);
      var fl = 0.0;
      var wsum = 0.0;
      if (r9.z > 0.0) {
        let g = (theta + KPI) / KTWO_PI * r9.z;
        fl = fl + 0.7 * (1.0 - abs(knoise1p(g, i32(r9.z), ts_at(vec2<i32>(t * 4 + 1, 0)))));
        wsum += 0.7;
      }
      if (r9.w > 0.0) {
        let g = (theta + KPI) / KTWO_PI * r9.w;
        fl = fl + 0.3 * (1.0 - abs(knoise1p(g, i32(r9.w), ts_at(vec2<i32>(t * 4 + 2, 0)))));
        wsum += 0.3;
      }
      flo = u.uFluteM * (fl - 0.55 * wsum);
      fluted = true;
      d_in = d_in - flo;
    }
    // the wall: its table read at the distance inside the edge, the ledges where they hold; past the foot the rock
    // dips steeply under the alluvium
    let woff = i32(r9.x);
    let wlen = i32(r9.y);
    let wl = interp(d_in, woff, wlen, false);
    let w0 = interp(d_in, woff, wlen, true);
    var wallz = w0 + (wl - w0) * lg;
    if (d_in < 0.0) { wallz = d_in * u.uTanUnder; }
    // the summit: a block's cap, then the highest of the tower's peak cones
    let fl_t = r2.z;
    let isBlock = fl_t > -1.0e29;
    let r11 = T(t, 11);
    var summit = KNEG;
    if (isBlock) {
      let frac = clamp(d_in / R / jag, 0.0, 1.0);
      summit = fl_t + r11.x * frac + (r11.y * clump_at(p).x + r11.z * cknob_at(p).x);
    }
    let npk = i32(r2.w);
    for (var k = 0; k < npk; k++) {
      let q0 = PK(t, k, 0);
      let q1 = PK(t, k, 1);
      let pdx = dx - q0.x;
      let pdy = dy - q0.y;
      let pu = (pdx * q0.z + pdy * q0.w) / q1.x;
      let pv = (pdy * q0.z - pdx * q0.w) * q1.x;
      var rho = sqrt(pu * pu + pv * pv);
      let a23 = PK(t, k, 2);
      let a45 = PK(t, k, 3);
      let a67 = PK(t, k, 4);
      if (any(a23 != vec4<f32>(0.0)) || any(a45 != vec4<f32>(0.0)) || any(a67 != vec4<f32>(0.0))) {
        // the cone's ribs: its distance x g(theta), harmonics 2-7 by the angle-addition recurrences
        let rk = 1.0 / max(rho, 1e-3);
        let k1 = pu * rk;
        let l1 = pv * rk;
        var cm = k1;
        var sm = l1;
        var g = 1.0;
        let amp = array<vec2<f32>, 6>(a23.xy, a23.zw, a45.xy, a45.zw, a67.xy, a67.zw);
        for (var m = 0; m < 6; m++) {
          let cn = cm * k1 - sm * l1;
          let sn = sm * k1 + cm * l1;
          cm = cn;
          sm = sn;
          g = g + amp[m].x * cm - amp[m].y * sm;
        }
        rho = rho * g;
      }
      rho = rho * jag;
      if (fluted) { rho = rho + flo; }               /* the flutes run on up the peak's flanks */
      let x = rho / q1.z;
      let b = q1.w;
      var z = 0.0;
      if (x <= 1.0) { z = q1.y * (1.0 - x + b * x * (1.0 - x)); } else { z = q1.y * (-(1.0 + b) * (x - 1.0)); }
      summit = max(summit, z);
    }
    if (u.uPeakRough > 0.0 && !isBlock) {
      // lumps and knobs over the peak's upper flanks, fading in from 35 % of the height up
      let up = ksmoothstep(0.35, 0.75, summit / H);
      summit = summit + u.uPeakRough * up * (r11.y * rlump_at(p).x + r11.z * rknob_at(p).x);
    }
    if (u.uBench != 0) {
      // the beds' benches across the summit's flanks, fading out over the top quarter
      let kb = u.uBenchK * ksmoothstep(0.93, 0.72, summit / H);
      let ph = (summit + bench_at(p).x + base) / u.uBenchM;
      summit = summit - kb * u.uBenchM / KTWO_PI * sin(KTWO_PI * ph);
    }
    let r8 = T(t, 8);
    let brow = r8.w;
    var z = select(min(wallz, summit), ksmin(wallz, summit, brow), brow > 0.0);
    var d_out_edge = d_in;
    var own = d_in > 0.0;
    if (r7.z > 0.0) {
      // the massif body: the tower's own wall table at its wider footprint, meeting a rough skirt rising inward
      let Hb = r7.z;
      let Rb = r7.w;
      var d_b = Rb - rs;
      if (fluted) { d_b = d_b - flo; }
      var wb = interp(d_b, woff, wlen, false);
      let wb0 = interp(d_b, woff, wlen, true);
      wb = wb0 + (wb - wb0) * lg;
      if (d_b < 0.0) { wb = d_b * u.uTanUnder; }
      let r12 = T(t, 12);
      let top_b = Hb + max(d_b, 0.0) * r8.x + (r12.x * rlump_at(p).x + r12.y * rknob_at(p).x);
      let zb = select(min(wb, top_b), ksmin(wb, top_b, brow), brow > 0.0);
      own = (own && (z >= zb)) || ((d_b > 0.0) && (wb < top_b - brow) && (zb > z));
      z = max(z, zb);
      d_out_edge = max(d_in, d_b);
    }
    z = z + base;
    let win = z > rock;
    if (win) {
      rock = z;
      if (own) { owner = i32(T(t, 12).z); }                /* the plan's index of the tower (tower_id) */
    }
    // a talus cone at the foot under some of the tower's azimuths (its gullies' rockfall)
    if (r11.w > 0.0) {
      let theta = atan2(dy, dx);
      let g = (theta + KPI) / KTWO_PI * 7.0;
      let az = knoise1p(g, 7, saltT);
      let cc = u.uApronC;
      let gate = ksmoothstep(0.55 * cc, 0.55 * cc + 0.35, az);
      let Bt = r8.y * gate;
      let d_out = max(-d_out_edge, 0.0);
      var cone = Bt - d_out * u.uTanApron;
      if (!(d_out <= r8.z)) { cone = KNEG; }
      cone = cone + base;
      if (cone > scree) { scree = cone; }
    }
  }
  // the clusters' common base: flat at its height inside a cluster, under the peaks
  if (u.uPM != 0 && base > 0.5) { rock = max(rock, base); }
  outR_store(p, vec4<f32>(rock, scree, 0.0, 0.0));
  outO_store(p, owner);
}
