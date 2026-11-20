// Port of the cell-by-cell parts of blender/eidoblend/terrain/solvers/volcanic.py op_volcano_age, furrow_k_factor
// and _keep_mask at f90c6fc (numpy in the Blender edition; the fluvial run itself is solvers/fluvial.js's). The port's
// own kernel, float32 in numpy's order. Modes (uMode), r and az about the centre:
//   0  kf = young_factor + (1 - young_factor) smoothstep(0, young_radius_m, r)
//   1  kf (a) x exp(sector_contrast n91(az) - 0.5 sector_contrast^2)          (n91: table row uRow)
//   2  _keep_mask: w = max over the kept craters of 1 - smoothstep(0.8 R, R, |x - at|)   (ktab)
//   3  the kept craters: lowered = h + w (min(h, h_keep) - h); outF lowered, outG h - lowered (a: h, b: h_keep, c: w)
//   4  furrow m = max(m, smoothstep(0, 0.6, -streak))                           (a: m, b: the streak)
//   5  furrow m = max(m, smoothstep(0.05, 0.4, cut / uK0))                      (a: m, b: the ravines' cut)
//   6  furrow k: m = 1 - (1 - smoothstep(r_hi, 1.3 r_hi, r)) (1 - clip(m, 0, 1)); k_floor + (1 - k_floor) m
//      (a: the blurred m; uK0 r_hi, uK1 k_floor)
//   7  the seed texture weighted by the k_profile: tx (a) x clip(interp (b), 0, 1)
//! include volcanic/math
//! include volcanic/az
//! sampler azt r32f
//! sampler a
//! sampler b
//! sampler c
//! sampler ktab          the kept craters: (x0 - at.x, y0 - at.y, R, 0) each
//! image   outF r32f
//! image   outG r32f     mode 3 only (else a 1 x 1 stand-in)
//! uniform int uMode
//! uniform vec2 uOrg     the level's origin minus the centre
//! uniform float uStep
//! uniform float uK0
//! uniform float uK1
//! uniform int uRow
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let d = u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep;
  let r = length(d);
  var v = 0.0;
  switch u.uMode {
    case 0: { v = u.uK0 + (1.0 - u.uK0) * v_smoothstep(0.0, u.uK1, r); }
    case 1: {
      let sc = u.uK0;
      v = a_at(p).x * exp(sc * az_read(u.uRow, az_sampler(v_az(d))) - 0.5 * sc * sc);
    }
    case 2: {
      var w = 0.0;
      for (var k = 0; k < u.uCount; k++) {
        let t = ktab_at(vec2<i32>(k, 0));
        let rr = length(t.xy + (vec2<f32>(p) + 0.5) * u.uStep);
        w = max(w, 1.0 - v_smoothstep(0.8 * t.z, t.z, rr));
      }
      v = w;
    }
    case 3: {
      let h = a_at(p).x;
      let lowered = h + c_at(p).x * (min(h, b_at(p).x) - h);
      v = lowered;
      outG_store(p, vec4<f32>(h - lowered, 0.0, 0.0, 0.0));
    }
    case 4: { v = max(a_at(p).x, v_smoothstep(0.0, 0.6, -b_at(p).x)); }
    case 5: { v = max(a_at(p).x, v_smoothstep(0.05, 0.4, b_at(p).x / u.uK0)); }
    case 6: {
      let m = clamp(a_at(p).x, 0.0, 1.0);
      let mm = 1.0 - (1.0 - v_smoothstep(u.uK0, 1.3 * u.uK0, r)) * (1.0 - m);
      v = u.uK1 + (1.0 - u.uK1) * mm;
    }
    default: { v = a_at(p).x * clamp(b_at(p).x, 0.0, 1.0); }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
