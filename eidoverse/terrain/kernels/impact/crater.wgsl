// Port of blender/eidoblend/terrain/solvers/impact.py impact_crater (_impact_crater_core, _apron_wall,
// _complex_interior, _central_peak) at f90c6fc, at the points of a grid: the crater as a height change over the
// pre-impact surface. numpy evaluates it in float64 over the square that holds the ejecta's reach; this is float32 at
// every point, zero outside that square (strength NaN). The port's own kernel.
//   planform   plan = polygon_factor x (1 + radius_noise n61) x (1 + edge_noise n64); plan_low = 1 + 0.25 (polygon - 1)
//              x (1 + radius_noise n61); rho = r / (R plan); hr = hm (1 + rim_noise n62)
//   inside     (rho < 1.6) a simple crater's parabolic bowl rim_ramp - d (1 - rho^2), or with cliffs and a fill the
//              debris apron under the layered face (_apron_wall), or a complex crater's floor, wall and terraces
//   blanket    hr rc^-n taper (rc = max(rho, 0.35)), with rays; delta = crest_union(inner, blanket, crest_round hm)
//   fill       the apron's loose share (talus under the face, the floor's fine sediment), or the infill's flat floor
//   relief     hummocks (fbm at hummock_scale D) scaled by the ejecta's thickness, blocks (gradient noise), a complex
//              crater's central peak cluster
//! include volcanic/math
//! include volcanic/az
//! include volcanic/noise
//! include volcanic/face
//! sampler azt r32f      the azimuth tables (rows named in prm)
//! sampler zst rg32f     the apron's layered face (a stand-in without cliffs)
//! sampler s0t r32f
//! sampler prm           the crater's numbers (solvers/impact.js craterTexels), rgba32f texels:
//                          0 (D, R, d, hm)
//                          1 (complex 1|0, floor_frac, fill_ratio (-1: none), fill_round)
//                          2 (polygon 1|0, radius_noise, edge_noise, rim_noise)
//                          3 (crest_round, ejecta_reach, ejecta_exponent, hummocks)
//                          4 (blocks, rays, the support's half-side, 0)
//                          5 (rows: polygon, n61, n64, n62)
//                          6 (rows: n63 (rays), n66 (apron vary); cliffs 1|0, mounds_m)
//                          7 apron: (tan talus, tan face, talus_frac, apron_vary)
//                          8 apron: (the face's U, the fill's z_c, terraces, peaks)
//                          9 complex: (peak height = height_frac d, peak base = 0.5 width_frac D, 0, 0)
//! sampler ntab          gradient-noise terms, two texels each (impact.js noiseTexels): (base x, base y, f0 x, f0 y),
//                        (step / scale, seed bits, 0, 0); terms 0-1 hummocks, 2 blocks 0.012 D, 3 blocks 0.006 D,
//                        4-5 the apron's mounds
//! sampler ttab          a complex crater's terraces: (q0, half, a0, span) each
//! sampler ptab          its central peaks: (dx0, dy0, h, rad) and (wobble row, 0, 0, 0) each, offsets from the
//                        grid's origin
//! image   outD r32f     delta
//! image   outE r32f     ejecta
//! image   outF r32f     fill
//! image   outT r32f     talus
//! image   outS r32f     strength (NaN off the wall)
//! uniform vec2 uOrg     the grid's origin minus the centre, metres
//! uniform float uStep

fn noise_term(t: i32, q: vec2<i32>) -> f32 {
  let a = ntab_at(vec2<i32>(2 * t, 0));
  let b = ntab_at(vec2<i32>(2 * t + 1, 0));
  let l = lat_grid(vec2<i32>(a.xy), a.zw, b.x, q);
  return grad_noise(l.c, l.f, bitcast<u32>(b.y), true);
}

// fbm of two octaves from term t (gain 0.5): total / (0.24 sqrt(norm))
fn fbm2(t: i32, q: vec2<i32>) -> f32 {
  let total = noise_term(t, q) + 0.5 * noise_term(t + 1, q);
  return total / (0.24 * sqrt(1.25));
}

fn kmain(p: vec2<i32>) {
  let n = outD_size();
  if (!inside(p, n)) { return; }
  let nan = bitcast<f32>(0x7FC00000u);
  let t0 = prm_at(vec2<i32>(0, 0));
  let t1 = prm_at(vec2<i32>(1, 0));
  let t2 = prm_at(vec2<i32>(2, 0));
  let t3 = prm_at(vec2<i32>(3, 0));
  let t4 = prm_at(vec2<i32>(4, 0));
  let t5 = prm_at(vec2<i32>(5, 0));
  let t6 = prm_at(vec2<i32>(6, 0));
  let d = u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep;
  let reach = t4.z;
  if (!(d.x >= -reach && d.x <= reach && d.y >= -reach && d.y <= reach)) {
    outD_store(p, vec4<f32>(0.0));
    outE_store(p, vec4<f32>(0.0));
    outF_store(p, vec4<f32>(0.0));
    outT_store(p, vec4<f32>(0.0));
    outS_store(p, vec4<f32>(nan, 0.0, 0.0, 0.0));
    return;
  }
  let D = t0.x;
  let R = t0.y;
  let dd = t0.z;
  let hm = t0.w;
  let complex = t1.x != 0.0;
  let r = length(d);
  let az = v_az(d);
  let s = az_sampler(az);
  var plan = 1.0;
  if (t2.x != 0.0) { plan = az_read(i32(t5.x), s); }
  var plan_low = 1.0 + 0.25 * (plan - 1.0);
  if (t2.y != 0.0) {
    let rn_f = 1.0 + t2.y * az_read(i32(t5.y), s);
    plan = plan * rn_f;
    plan_low = plan_low * rn_f;
  }
  if (t2.z != 0.0) { plan = plan * (1.0 + t2.z * az_read(i32(t5.z), s)); }
  let rho = r / (R * plan);
  var hr = hm;
  if (t2.w != 0.0) { hr = hm * (1.0 + t2.w * az_read(i32(t5.w), s)); }
  let mr = min(rho, 1.6);
  let rim_ramp = hm + (hr - hm) * (mr * mr);
  var inner = VBIG;
  var apron = false;
  var a_strength = nan;
  var a_rock = 0.0;
  var a_coarse = 0.0;
  if (rho < 1.6) {
    if (!complex) {
      var inn = rim_ramp - dd * (1.0 - rho * rho);
      if (t6.z != 0.0 && t1.z >= 0.0) {
        // _apron_wall: a concave debris apron from the floor's centre to the foot of the layered face
        let t7 = prm_at(vec2<i32>(7, 0));
        let t8 = prm_at(vec2<i32>(8, 0));
        let tt = t7.x;
        let tw = t7.y;
        let tf = t7.z;
        let z_c = t8.y;
        let Hw = hm - z_c;
        let z_t = z_c + tf * Hw;
        let Hf = hm - z_t;
        let Rp = R * plan;
        let Rpl = R * plan_low;
        let rr = rho * Rp;
        let u_t = max(Rp - Hf / tw, 0.2 * Rp);
        let u_a = max(Rpl - Hf / tw, 0.2 * Rpl);
        let pw = max(tt * u_a / (z_t - z_c), 1.0);
        let q = rr / u_a;
        var ap: f32;
        if (q < 1.0) { ap = z_c + (z_t - z_c) * pow(clamp(q, 0.0, 1.0), pw); } else { ap = z_t + tt * (rr - u_a); }
        if (t7.w != 0.0) {
          let dz = t7.w * tf * Hw * az_read(i32(t6.y), s);
          ap = ap + dz * v_smoothstep(0.7, 1.0, q);
        }
        if (t6.w != 0.0) { ap = ap + t6.w * fbm2(4, p) * (1.0 - v_smoothstep(0.3, 0.6, q)); }
        let fz = layered_face(rr - u_t, az, t8.x, tw);
        let rock_face = z_t + fz.x;
        var wall = v_smooth_max(ap, rock_face, 0.012 * Hw);
        let ramp = clamp((rr - u_t) * (tw / Hf), 0.0, 1.0);
        wall = wall + (rim_ramp - hm) * ramp;
        let bowl = rim_ramp - dd * (1.0 - rho * rho);
        let rock = max(bowl, rock_face + (rim_ramp - hm) * ramp);
        inn = wall;
        apron = true;
        a_strength = select(1.1 * tt, fz.y, rock_face >= ap);
        a_rock = min(rock, wall);
        a_coarse = v_smoothstep(0.55, 0.85, q);
      }
      inner = inn;
    } else {
      // _complex_interior: a flat floor out to floor_frac, a concave wall, terraces as arcs
      let rf = clamp(t1.y, 0.05, 0.85);
      let fz = hm - dd;
      let sw = max((rho - rf) / (1.0 - rf), 0.0);
      var z = fz + (rim_ramp - fz) * pow(min(sw, 1.6), 1.8);
      let nt = i32(prm_at(vec2<i32>(8, 0)).z);
      for (var k = 0; k < nt; k++) {
        let tr = ttab_at(vec2<i32>(k, 0));
        let off = v_mod(az - tr.z + VPI, VTAU) - VPI;
        let arc = v_smoothstep(0.5 * tr.w, 0.35 * tr.w, abs(off));
        let band = 0.5 * (1.0 + cos(clamp((sw - tr.x) / tr.y, -1.0, 1.0) * VPI));
        let wq = fz + (rim_ramp - fz) * pow(min(tr.x, 1.6), 1.8);
        z = z + arc * band * (wq - z);
      }
      inner = select(z, fz, rho < rf);
    }
  }
  let ne = t3.z;
  let reachE = t3.y;
  let taper = 1.0 - v_smoothstep(0.62 * reachE, reachE, rho);
  let rc = max(rho, 0.35);
  var fall: f32;
  if (ne == 3.0) { fall = 1.0 / (rc * rc * rc); } else { fall = pow(rc, -ne); }
  var blanket = hr * fall * taper;
  if (t4.y != 0.0) {
    let st = max(az_read(i32(t6.x), s), 0.0);
    blanket = blanket * (1.0 + t4.y * (st * st - 0.5) * v_smoothstep(1.05, 1.7, rho));
  }
  var delta = v_crest_union(inner, blanket, t3.x * hm);
  var fill = 0.0;
  var talus = 0.0;
  if (apron) {
    let ins = rho < 1.0 && delta <= inner + 1e-6;
    let loose = select(0.0, max(delta - a_rock, 0.0), ins);
    talus = loose * a_coarse;
    fill = loose - talus;
  } else if (t1.z >= 0.0) {
    let z_fill = hm - t1.z * D;
    let filled = v_smooth_max(delta, z_fill, max(t1.w, 1e-3) * (z_fill - (hm - dd)));
    if (rho < 1.0) {
      fill = max(filled - delta, 0.0);
      delta = filled;
    }
  }
  let outside = v_smoothstep(0.92, 1.02, rho);
  let thick = select(0.0, min(blanket, 1.2 * hr), rho > 0.9) * outside;
  if (t3.w != 0.0) { delta = delta + t3.w * thick * fbm2(0, p); }
  if (t4.x != 0.0) {
    var lump = v_smoothstep(0.36, 0.6, noise_term(2, p));
    lump = lump + 0.6 * v_smoothstep(0.4, 0.62, noise_term(3, p));
    let ro = max(rho, 1.0);
    delta = delta + t4.x * hm * lump * v_smoothstep(0.85, 0.98, rho) * taper / (ro * ro * ro);
  }
  if (complex) {
    // _central_peak: a main summit and lesser ones, each a rounded cone whose radius wanders with azimuth
    let np = i32(prm_at(vec2<i32>(8, 0)).w);
    var pk = 0.0;
    for (var k = 0; k < np; k++) {
      let a = ptab_at(vec2<i32>(2 * k, 0));
      let b = ptab_at(vec2<i32>(2 * k + 1, 0));
      let dq = a.xy + (vec2<f32>(p) + 0.5) * u.uStep;
      let rr = length(dq);
      let wob = 1.0 + 0.18 * az_read(i32(b.x), az_sampler(v_az(dq)));
      let q = clamp(1.0 - rr / (a.w * wob), 0.0, 1.0);
      pk = max(pk, a.z * pow(q, 1.6) * (3.0 - 2.0 * q));
    }
    delta = delta + pk;
  }
  let ejecta = max(thick * (0.5 + 0.5 * v_smoothstep(1.0, 1.3, rho)), 0.0);
  var strength = nan;
  if (t6.z != 0.0) {
    if (apron) { strength = select(nan, a_strength, rho < 1.0); }
  }
  outD_store(p, vec4<f32>(delta, 0.0, 0.0, 0.0));
  outE_store(p, vec4<f32>(ejecta, 0.0, 0.0, 0.0));
  outF_store(p, vec4<f32>(fill, 0.0, 0.0, 0.0));
  outT_store(p, vec4<f32>(talus, 0.0, 0.0, 0.0));
  outS_store(p, vec4<f32>(strength, 0.0, 0.0, 0.0));
}
