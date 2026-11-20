// Port of the world functions blender/eidoblend/terrain/solvers/karst.py evaluate() puts on a level at f90c6fc (the
// lambdas it passes to _Grid.smooth, and cap_rough), as a kernel over a separable grid: G.smooth's world-anchored
// lattice, or the level's subsamples. numpy's float64 is float32 here.
//
//   uMode 0  a sum of octaves:   uA * (sum_t amp_t noise2_t) / uB
//              LOB    lobes_m * (noise2(130) + 0.45 noise2(60)) / 0.33
//              BENCH  3 * fbm2(160, 2, salt + 161, 0.5) / 0.33
//              JAG    jag * fbm2(90, 2, salt + 131, 0.45, lim) / 0.3        (the octaves under lim left out)
//              LUMP   fbm2(45, 2, salt + 137, 0.5, lim) / 0.3                (the caps' and the flanks' lumps)
//              MICRO  plain_micro_m * fbm2(160, 3, salt + 401, 0.45, lim) / 0.3
//   uMode 1  LEDGE: smoothstep(uA, uB, 0.5 + sum / 0.6)         (fbm2(30, 2, salt + 141, 0.5, lim))
//   uMode 2  KNOB:  patch = smoothstep(uA, uB, sum_{t<2} / 0.3 * 0.5) (fbm2(180, 2, salt + 151));
//                   pinnacles(term 2) x patch when uFlags & 1, else 0.35 x patch
//   uMode 3  PM:    _plinth_of x _base_membership (terms: 0-1 fbm2(1500, 2, salt + 31); 2 fbm2(300, 1, salt + 33); 3
//                   fbm2(120, 1, salt + 37); 4-6 the cluster field's broad fbm2(u, v, cluster_scale_m, 3, salt + 11);
//                   7-8 its ridged noise2(u, v, ridge_scale_m, salt + 13) + 0.35 noise2(.., 0.5 ridge_scale_m, salt + 17))
//                   uA plinth_m + base_m, uB base_rough_m, uC cluster_ridges, uD the cluster threshold, uE its band,
//                   uF its std, uG d0 (the river's corridor); uFlags 1: plinth_m > 0, 2: a river (rd: its distance)
//
// The terms' lattice coordinates come split (solvers/karst.js latticeTables): term t's gx is tx[row 2t][column] +
// ty[row 2t][row] and its gy tx[row 2t + 1][column] + ty[row 2t + 1][row], each an (integer cell, fraction) pair;
// the cluster field's rotated, stretched coordinates are sums of a column part and a row part, the others have one.

//! sampler tx rg32f      per term t: rows 2t, 2t + 1 the (cell, fraction) a grid column adds to gx, gy
//! sampler ty rg32f      the same for a grid row
//! sampler salts r32ui   per term: its salt
//! sampler amps          per term: its amplitude (the octave's weight)
//! sampler rd            uMode 3 with a river: the river's distance at the grid's points (metres)
//! image   outV r32f
//! uniform int uMode
//! uniform int uNT       the number of terms
//! uniform int uFlags
//! uniform float uA
//! uniform float uB
//! uniform float uC
//! uniform float uD
//! uniform float uE
//! uniform float uF
//! uniform float uG
//! include karst/lib

fn term(t: i32, p: vec2<i32>) -> f32 {
  let a = tx_at(vec2<i32>(p.x, 2 * t)).xy;
  let b = ty_at(vec2<i32>(p.y, 2 * t)).xy;
  let c = tx_at(vec2<i32>(p.x, 2 * t + 1)).xy;
  let d = ty_at(vec2<i32>(p.y, 2 * t + 1)).xy;
  var ix = i32(a.x) + i32(b.x);
  var fx = a.y + b.y;
  if (fx >= 1.0) { fx -= 1.0; ix += 1; }
  var iy = i32(c.x) + i32(d.x);
  var fy = c.y + d.y;
  if (fy >= 1.0) { fy -= 1.0; iy += 1; }
  return knoise2(ix, iy, fx, fy, salts_at(vec2<i32>(t, 0)));
}

// sum_t amp_t noise2_t over terms [t0, t1), in order (fbm2's out += a noise2)
fn octaves(t0: i32, t1: i32, p: vec2<i32>) -> f32 {
  var s = 0.0;
  for (var t = t0; t < t1; t++) { s += amps_at(vec2<i32>(t, 0)).x * term(t, p); }
  return s;
}

fn kmain(p: vec2<i32>) {
  let n = outV_size();
  if (!inside(p, n)) { return; }
  var v = 0.0;
  if (u.uMode == 0) {
    v = u.uA * octaves(0, u.uNT, p) / u.uB;
  } else if (u.uMode == 1) {
    v = ksmoothstep(u.uA, u.uB, 0.5 + octaves(0, u.uNT, p) / 0.6);
  } else if (u.uMode == 2) {
    let pat = ksmoothstep(u.uA, u.uB, octaves(0, 2, p) / 0.3 * 0.5);          /* karst.py's `patch` (a WGSL keyword) */
    if ((u.uFlags & 1) != 0) {
      let a = tx_at(vec2<i32>(p.x, 4)).xy;
      let b = ty_at(vec2<i32>(p.y, 4)).xy;
      let c = tx_at(vec2<i32>(p.x, 5)).xy;
      let d = ty_at(vec2<i32>(p.y, 5)).xy;
      var ix = i32(a.x) + i32(b.x);
      var fx = a.y + b.y;
      if (fx >= 1.0) { fx -= 1.0; ix += 1; }
      var iy = i32(c.x) + i32(d.x);
      var fy = c.y + d.y;
      if (fy >= 1.0) { fy -= 1.0; iy += 1; }
      v = kpinnacles(ix, iy, fx, fy, salts_at(vec2<i32>(2, 0))) * pat;
    } else {
      v = 0.35 * pat;
    }
  } else {
    // _plinth_of
    var out = u.uA * max(1.0 + 0.25 * octaves(0, 2, p) / 0.3, 0.3);
    if (u.uB > 0.0) { out = out + u.uB * (octaves(2, 3, p) + 0.8 * octaves(3, 4, p)) / 0.38; }
    out = max(out, 0.0);
    // _base_membership, from the cluster field's raw value
    let broad = octaves(4, 7, p) / 0.3;
    var raw = broad;
    if (u.uC > 0.0) {
      let nn = term(7, p) + 0.35 * term(8, p);
      let ridged = (1.0 - abs(nn) / 0.45) * 1.6;
      raw = (1.0 - u.uC) * broad + u.uC * ridged;
    }
    var m = 0.0;
    if ((u.uFlags & 1) == 0) {
      let t0 = u.uD + u.uE;
      m = ksmoothstep(t0, t0 + 0.9 * u.uF, raw);
      if ((u.uFlags & 2) != 0) { m = m * ksmoothstep(u.uG, u.uG + 450.0, rd_at(p).x); }
    } else {
      let b = 0.3 * u.uE;
      m = ksmoothstep(u.uD - b, u.uD + b, raw);
    }
    v = out * m;
  }
  outV_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
