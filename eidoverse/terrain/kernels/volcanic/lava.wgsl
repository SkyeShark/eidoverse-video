// Port of the cell-by-cell parts of blender/eidoblend/terrain/solvers/volcanic.py lava_surface, _lava_surface_aa,
// lava_walkers' return and op_lava_flows at f90c6fc (numpy in the Blender edition; the blurs are core/prims.js's
// gaussianBlur, the walkers solvers/volcanic.js's, the noise numpy's standard normals drawn on the GPU). The port's own
// kernel, float32 in numpy's order. Window fields are a flow unit's window of the level; uOrg is the window's origin
// from the vent (metres). Modes (uMode):
//   0  P = min(visits / N, 1)                                             (a: the visit counts; uK0 N)
//   1  path = smoothstep(0.5 p_edge, 2 p_edge, a)                          (a: P blurred at 0.8)
//   2  the band's width cell by cell: lf = log2(clip(ws, 0.5, 2)); b + (b - b_lo) lf below 0, b + (b_hi - b) lf above
//                                                                          (a: b, b: b_lo, c: b_hi, d: ws)
//   3  core = smoothstep(c0 e^-2, c1 e^-2, b clip(1 + lobes, 0.2))         (a: b, b: lobes; uK0 c0, uK1 c1)
//   4  plate = smoothstep(uK0, 0.7, a)                                     (a: the core blurred)
//   5  aa levee: T = th plate + levee th plate (1 - smoothstep(0.55, 0.9, f2))   (a: plate, b: f2; uK0 th, uK1 levee)
//   6  aa rough: r + amp (1 - 2 |tanh(0.8 g / std)|)                       (a: r, b: g; uK0 amp, uK1 std)
//   7  T = max(T + coef r plate, 0)                                        (a: T, b: r, c: plate; uK0 coef)
//   8  the old levee: T = th (plate + levee plate (1 - smoothstep(0.6, 0.97, f2))) (a: plate, b: f2; uK0 th, uK1 levee)
//   9  the lobes and the old rough: r + amp g / std                        (a: r, b: g; uK0 amp, uK1 std)
//  10  (a - mean)^2                                                         (np.std's deviations; uK0 mean)
//  11  no_climb 'local': up = clip((lvl + 1.3 th - gw) / th, 0, 1), lvl = bw > 1e-4 ? bgw / max(bw, 1e-6) : gw;
//      outF T up, outG F smoothstep(0, 0.25, up)        (a: T, b: F, c: gw, d: bw; e: bgw = blur(gw pw); uK0 th)
//  12  no_climb: up = 1 - smoothstep(zv + 0.25 th, zv + th, gw); T up, F up (a: T, b: F, c: gw; uK0 zv, uK1 th)
//  13  the vent's taper: smoothstep(0, uK0, r); T taper, F taper           (a: T, b: F)
//  14  the channel's ramp: fr + (1 - fr) smoothstep(0.1 until, until, r / length) (x ws when given)
//                                                    (a: ws or a stand-in, uK0 fr, uK1 until, uLen length; uFlag ws)
//  15  the spread: clip(sqrt(tan(spread) / max(hypot(gx, gy), 1e-3)), 0.5, 1.6)   (a: gx, b: gy; uK0 tan(spread))
//  16  paste a window: outF[q + origin] = a[q]  (outF the level field, in place)
//  17  paste a window by the maximum: outF[q + origin] = max(outF, a[q])
//  18  bury: tv + max(g - ht, 0) smoothstep(0.35, 0.8, fv)                 (a: tv, b: g, c: ht, d: fv)
//  19  foot = max(foot, fv (1 - 0.6 age))                                   (a: foot, b: fv; uK0 age)
//  20  pw = smoothstep(0.02, 0.1, P); outG = gw pw                          (a: P, b: gw)
//! include volcanic/math
//! sampler a
//! sampler b
//! sampler c
//! sampler d
//! sampler e
//! image   outF r32f
//! image   outG r32f     modes 11, 12, 13, 20 (else a 1 x 1 stand-in)
//! uniform int uMode
//! uniform vec2 uOrg     the window's origin minus the vent, metres (13, 14)
//! uniform float uStep
//! uniform float uK0
//! uniform float uK1
//! uniform float uLen
//! uniform int uFlag
//! uniform ivec2 uAt     16, 17: the window's origin in the level (columns, rows)

const E2: f32 = 0.1353352832366127;     // exp(-2)

fn kmain(p: vec2<i32>) {
  let n = a_size();
  if (u.uMode == 16 || u.uMode == 17) {
    if (!inside(p, n)) { return; }
    let q = p + u.uAt;
    var v = a_at(p).x;
    if (u.uMode == 17) { v = max(outF_load(q).x, v); }
    outF_store(q, vec4<f32>(v, 0.0, 0.0, 0.0));
    return;
  }
  let m = outF_size();
  if (!inside(p, m)) { return; }
  let x = a_at(p).x;
  var v = 0.0;
  var g = 0.0;
  switch u.uMode {
    case 0: { v = min(x / u.uK0, 1.0); }
    case 1: { v = v_smoothstep(0.5 * u.uK0, 2.0 * u.uK0, x); }
    case 2: {
      let lf = log2(clamp(d_at(p).x, 0.5, 2.0));
      v = select(x + (c_at(p).x - x) * lf, x + (x - b_at(p).x) * lf, lf < 0.0);
    }
    case 3: { v = v_smoothstep(u.uK0 * E2, u.uK1 * E2, x * max(1.0 + b_at(p).x, 0.2)); }
    case 4: { v = v_smoothstep(u.uK0, 0.7, x); }
    case 5: { v = u.uK0 * x + u.uK1 * u.uK0 * x * (1.0 - v_smoothstep(0.55, 0.9, b_at(p).x)); }
    case 6: { v = x + u.uK0 * (1.0 - 2.0 * abs(tanh(0.8 * (b_at(p).x / u.uK1)))); }
    case 7: { v = max(x + u.uK0 * b_at(p).x * c_at(p).x, 0.0); }
    case 8: {
      let lev = x * (1.0 - v_smoothstep(0.6, 0.97, b_at(p).x));
      v = u.uK0 * (x + u.uK1 * lev);
    }
    case 9: { v = x + u.uK0 * b_at(p).x / u.uK1; }
    case 10: { let dd = x - u.uK0; v = dd * dd; }
    case 11: {
      let th = u.uK0;
      let gw = c_at(p).x;
      let bw = d_at(p).x;
      let lvl = select(gw, e_at(p).x / max(bw, 1e-6), bw > 1e-4);
      let up = clamp((lvl + 1.3 * th - gw) / th, 0.0, 1.0);
      v = x * up;
      g = b_at(p).x * v_smoothstep(0.0, 0.25, up);
    }
    case 12: {
      let zv = u.uK0;
      let th = u.uK1;
      let up = 1.0 - v_smoothstep(zv + 0.25 * th, zv + 1.0 * th, c_at(p).x);
      v = x * up;
      g = b_at(p).x * up;
    }
    case 13: {
      let r = length(u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep);
      let taper = v_smoothstep(0.0, u.uK0, r);
      v = x * taper;
      g = b_at(p).x * taper;
    }
    case 14: {
      let dv = length(u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep) / u.uLen;
      let ramp = u.uK0 + (1.0 - u.uK0) * v_smoothstep(0.1 * u.uK1, u.uK1, dv);
      v = select(ramp, x * ramp, u.uFlag != 0);
    }
    case 15: {
      let gy = b_at(p).x;
      let ts = max(sqrt(x * x + gy * gy), 1e-3);
      v = clamp(sqrt(u.uK0 / ts), 0.5, 1.6);
    }
    case 18: { v = x + max(b_at(p).x - c_at(p).x, 0.0) * v_smoothstep(0.35, 0.8, d_at(p).x); }
    case 19: { v = max(x, b_at(p).x * (1.0 - 0.6 * u.uK0)); }
    default: {
      let pw = v_smoothstep(0.02, 0.1, x);
      v = pw;
      g = b_at(p).x * pw;
    }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
  if (u.uMode == 11 || u.uMode == 12 || u.uMode == 13 || u.uMode == 20) { outG_store(p, vec4<f32>(g, 0.0, 0.0, 0.0)); }
}
