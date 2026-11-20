// Port of blender/eidoblend/terrain/solvers/volcanic.py setting_shape, setting_plain, plain_surface, _apron_limit,
// op_volcano_setting's and op_volcano_plain's cell-by-cell expressions at f90c6fc. The world noise is
// core/world_noise.js fieldGpu's (Blender's field_gpu), given as fields `a` .. `d`; this kernel combines it with the
// analytic parts, float32 in numpy's order. The port's own kernel. Modes (uMode):
//   0  setting_shape: ring = smoothstep(basin, basin + ramp, r); x smoothstep(t -+ 0.45, n_cover) (a: 3 fbm, cover < 1);
//      x clip(1 + texture n_tex, 0) (b: 3 fbm, texture > 0); x smoothstep(half, half + 25, |az - open|) (open
//      sector); + plain; x clip(1 + tilt d / 20 km, 0) (tilt); clip(., 0)
//   1  plain_surface: setting_plain (plain_m, the shield's Gaussian, plain_m - slope L tanh(d / L) toward the down
//      azimuth, slope_up away) + amp (a + 0.33 b) (a, b: 3 fbm of 4 and 3 octaves), amp the roughness eased where the
//      regional slope eases out and faded under the cone (plain_rough_inner)
//   2  _apron_limit: 1 - smoothstep(R, R + taper, r), and 1 in the open sector
//   3  volcano_far on a refining level: smoothstep(keep, max(far, keep + 1), r), x smoothstep(0.02, 0.15, shape) with
//      a plain (a: the shape)
//   4  K_factor: pk + (1 - pk) smoothstep(0.02, 0.25, shape) (a: the shape)
//   5  plain_w: (1 - smoothstep(0.02, 0.12, shape)) x reach x apron_limit (a: shape, b: reach, c: limit)
//   6  the fresh start: plain + start_m shape / pk ((1 - rough) + rough (0.5 + 1.5 n)) (a: plain, b: shape, c: n fbm)
//   7  the setting's pins: w = max(edge_w, plain_w), h = edge_w > 0.5 ? edge_h : plain (a: edge_w, b: edge_h, c:
//      plain_w, d: plain); outF w, outG h
//   8  volcano_plain's fill: max(smooth_max(h, plain, blend) - h, 0) x dilated reach x (1 - smoothstep(0.6 F, F,
//      plain - h)) (F > 0) x limit (a: h, b: plain, c: the dilated reach, d: limit or a stand-in)
//   9  volcano_plain's reach mask and seeds: outF = plain - h > -0.5 blend; outG = r < 0.3 basin | apron > 0.5 (a: h,
//      b: plain, c: apron or a stand-in)
//! include volcanic/math
//! sampler a
//! sampler b
//! sampler c
//! sampler d
//! sampler prm           the setting's numbers (solvers/volcanic.js settingTexels), rgba32f texels:
//                          0 (basin, ramp, cover 1|0, t)            1 (texture, open 1|0, open az rad, open_half_deg)
//                          2 (plain, tilt, tilt ex, tilt ey)        3 (plain_m, shield_m, shield_radius_m, plain_slope)
//                          4 (slope_up, down ex, down ey, extent)   5 (rough, s0, inner 1|0, inner factor)
//                          6 (inner r0, inner r1, plain_radius (-1: none), taper)
//                          7 (keep, far, a plain 1|0, plain_k)      8 (start_m, start_roughness, pk, plain_blend_m)
//                          9 (plain_fill_max_m (0: none), 0.3 basin, a limit 1|0, an apron 1|0)
//! image   outF r32f
//! image   outG r32f     mode 7 and 9 only (else a 1 x 1 stand-in)
//! uniform int uMode
//! uniform vec2 uOrg     the level's origin minus the centre, metres
//! uniform float uStep

fn tp(k: i32) -> vec4<f32> { return prm_at(vec2<i32>(k, 0)); }

fn open_off(az: f32) -> f32 {           // |degrees(mod(az - open + pi, TAU) - pi)|
  return abs(degrees(v_mod(az - tp(1).z + VPI, VTAU) - VPI));
}

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  let d = u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep;
  let r = length(d);
  let az = v_az(d);
  var v = 0.0;
  var g = 0.0;
  switch u.uMode {
    case 0: {
      let t0 = tp(0); let t1 = tp(1); let t2 = tp(2);
      var o = v_smoothstep(t0.x, t0.x + t0.y, r);
      if (t0.z != 0.0) { o = o * v_smoothstep(t0.w - 0.45, t0.w + 0.45, a_at(p).x); }
      if (t1.x > 0.0) { o = o * max(1.0 + t1.x * b_at(p).x, 0.0); }
      if (t1.y != 0.0) { o = o * v_smoothstep(t1.w, t1.w + 25.0, open_off(az)); }
      o = o + t2.x;
      if (t2.y != 0.0) {
        let dd = (d.x * t2.z + d.y * t2.w) / 20000.0;
        o = o * max(1.0 + t2.y * dd, 0.0);
      }
      v = max(o, 0.0);
    }
    case 1: {
      let t3 = tp(3); let t4 = tp(4); let t5 = tp(5); let t6 = tp(6);
      var pl = t3.x;
      if (t3.y != 0.0) { pl = pl + t3.y * exp(-((r / t3.z) * (r / t3.z))); }
      let s = t3.w;
      let su = t4.x;
      let dd = d.x * t4.y + d.y * t4.z;
      let L = t4.w;
      if (s != 0.0 || su != 0.0) {
        let tt = L * tanh(dd / L);
        pl = pl - select(su, s, dd > 0.0) * tt;
      }
      if (t5.x > 0.0) {
        var amp = t5.x;
        if (t5.y > 0.0) {
          let th = tanh(dd / L);
          amp = t5.x * clamp(1.0 - th * th, 0.15, 1.0);
        }
        if (t5.z != 0.0) { amp = amp * (t5.w + (1.0 - t5.w) * v_smoothstep(t6.x, t6.y, r)); }
        pl = pl + amp * (a_at(p).x + 0.33 * b_at(p).x);
      }
      v = pl;
    }
    case 2: {
      let t1 = tp(1); let t6 = tp(6);
      var lim = 1.0;
      if (t6.z >= 0.0) { lim = 1.0 - v_smoothstep(t6.z, t6.z + t6.w, r); }
      if (t1.y != 0.0) { lim = max(lim, 1.0 - v_smoothstep(t1.w, t1.w + 25.0, open_off(az))); }
      v = lim;
    }
    case 3: {
      let t7 = tp(7);
      let fw = v_smoothstep(t7.x, max(t7.y, t7.x + 1.0), r);
      v = select(fw, fw * v_smoothstep(0.02, 0.15, a_at(p).x), t7.z != 0.0);
    }
    case 4: {
      let pk = tp(7).w;
      v = pk + (1.0 - pk) * v_smoothstep(0.02, 0.25, a_at(p).x);
    }
    case 5: {
      v = (1.0 - v_smoothstep(0.02, 0.12, a_at(p).x)) * b_at(p).x * c_at(p).x;
    }
    case 6: {
      let t8 = tp(8);
      let rough = t8.y;
      let nn = 0.5 + 1.5 * c_at(p).x;
      v = a_at(p).x + t8.x * b_at(p).x / t8.z * ((1.0 - rough) + rough * nn);
    }
    case 7: {
      let ew = a_at(p).x;
      v = max(ew, c_at(p).x);
      g = select(d_at(p).x, b_at(p).x, ew > 0.5);
    }
    case 8: {
      let t8 = tp(8); let t9 = tp(9);
      let h = a_at(p).x;
      let pl = b_at(p).x;
      var fill = max(v_smooth_max(h, pl, t8.w) - h, 0.0);
      fill = fill * c_at(p).x;
      if (t9.x > 0.0) { fill = fill * (1.0 - v_smoothstep(0.6 * t9.x, t9.x, pl - h)); }
      if (t9.z != 0.0) { fill = fill * d_at(p).x; }
      v = fill;
    }
    default: {
      let t8 = tp(8); let t9 = tp(9);
      let h = a_at(p).x;
      let pl = b_at(p).x;
      v = select(0.0, 1.0, pl - h > -0.5 * t8.w);
      var sd = r < t9.y;
      if (t9.w != 0.0) { sd = sd || c_at(p).x > 0.5; }
      g = select(0.0, 1.0, sd);
    }
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
  if (u.uMode == 7 || u.uMode == 9) { outG_store(p, vec4<f32>(g, 0.0, 0.0, 0.0)); }
}
