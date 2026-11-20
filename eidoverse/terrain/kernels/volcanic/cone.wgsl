// Port of blender/eidoblend/terrain/solvers/volcanic.py cinder_cone, _cone_breach and aged_cinder_cone's patch read
// at f90c6fc (`//! include volcanic/cone`, after volcanic/math and volcanic/az). The port's own kernel code: numpy
// evaluates the cone in float64 at any points; here it is float32 at an offset from the cone's vent.
//
// A cone is eight rgba32f texels (solvers/volcanic.js coneTexels), the plan's numbers in doubles rounded once:
//   a  (W, H, rcr, Rb)                    the basal width, height, crater rim radius, basal radius
//   b  (t, L, mode, floor)                tan(flank), the toe's width, 0 pile / 1 toe / 2 straight, the floor
//                                         (-extend_m for a pile, else 0)
//   c  (rim_tilt, tilt az rad, tc, depth) tc = tan(crater_wall_deg); depth = min(crater_depth_frac H, tc rcr)
//   d  (k, breach, baz rad, half rad)     k = crest w (t + tc); breach 1 when breach_azimuth_deg is given
//   e  (outline_noise, its table row, elongation (1: none), 0)
//   f  (ex, ey, 0, 0)                     compass(elongation_azimuth_deg)
//   g  (pox, poy, pstep, m)               an aged cone's patch: (grid origin - patch corner) / pc - 0.5, step / pc,
//                                         the patch's cells a side (0 for a fresh cone)
//   h  (ox - at.x, oy - at.y, 0, 0)       the evaluation grid's origin from the vent, metres
const TAN30: f32 = 0.5773502691896257;

struct Cone { a: vec4<f32>, b: vec4<f32>, c: vec4<f32>, d: vec4<f32>, e: vec4<f32>, f: vec4<f32>, g: vec4<f32>, h: vec4<f32> }

// cinder_cone at offset dv from the vent (fresh: the exact profile)
fn cone_fresh(dv: vec2<f32>, k: Cone) -> f32 {
  let W = k.a.x;
  let H = k.a.y;
  let rcr = k.a.z;
  let Rb = k.a.w;
  let t = k.b.x;
  let L = k.b.y;
  let mode = i32(k.b.z);
  var r = length(dv);
  let az = v_az(dv);
  if (k.e.z > 1.0) {
    let e = k.e.z;
    let ex = k.f.x;
    let ey = k.f.y;
    let a1 = (dv.x * ex + dv.y * ey) / e;
    let a2 = -dv.x * ey + dv.y * ex;
    r = sqrt(a1 * a1 + a2 * a2);
  }
  if (k.e.x != 0.0) {
    r = r / (1.0 + k.e.x * az_read(i32(k.e.y), az_sampler(az)));
  }
  var hrim = H;
  if (k.c.x != 0.0) { hrim = H * (1.0 + k.c.x * cos(az - k.c.y)); }
  var flank: f32;
  if (mode == 0) {
    flank = H - t * (r - rcr);
  } else if (mode == 1) {
    let rt = Rb - L;
    if (r <= rt) { flank = H - t * (r - rcr); } else if (r < Rb) { flank = t / (2.0 * L) * ((Rb - r) * (Rb - r)); } else { flank = 0.0; }
  } else {
    flank = select(0.0, H - t * (r - rcr), r < Rb);
  }
  if (k.c.x != 0.0) { flank = flank * (hrim / H); }
  let tc = k.c.z;
  let depth = k.c.w;
  let inner = max(hrim + tc * (r - rcr), H - depth);
  var z = v_crest_union(flank, inner, k.d.x);
  if (k.d.y != 0.0) {
    // _cone_breach: a ramp from the crater floor down to the base inside the sector, walls at 30 degrees off it
    let fl = H - depth;
    let d = v_mod(az - k.d.z + VPI, VTAU) - VPI;
    let lateral = max(abs(d) - k.d.w, 0.0) * max(r, rcr);
    let ramp = fl * (1.0 - clamp((r - 0.5 * rcr) / (Rb - 0.5 * rcr), 0.0, 1.0));
    let cut = ramp + TAN30 * lateral + select(VBIG, 0.0, abs(d) < 0.5 * VPI);
    z = v_smooth_min(z, cut, 0.02 * fl + 1e-3);
  }
  return max(z, k.b.w);
}

// aged_cinder_cone's read of its patch (the fresh cone blurred by FFT on its own grid): bilinear, the floor outside
fn cone_aged(q: vec2<i32>, k: Cone) -> f32 {
  let m = i32(k.g.w);
  let fx = k.g.x + (f32(q.x) + 0.5) * k.g.z;
  let fy = k.g.y + (f32(q.y) + 0.5) * k.g.z;
  let mf = f32(m - 1);
  let inside = fx >= 0.0 && fy >= 0.0 && fx <= mf && fy <= mf;
  if (!inside) { return k.b.w; }
  let i0 = clamp(i32(floor(fx)), 0, m - 2);
  let j0 = clamp(i32(floor(fy)), 0, m - 2);
  let tx = clamp(fx - f32(i0), 0.0, 1.0);
  let ty = clamp(fy - f32(j0), 0.0, 1.0);
  let p00 = patch_at(vec2<i32>(i0, j0)).x;
  let p10 = patch_at(vec2<i32>(i0 + 1, j0)).x;
  let p01 = patch_at(vec2<i32>(i0, j0 + 1)).x;
  let p11 = patch_at(vec2<i32>(i0 + 1, j0 + 1)).x;
  let v = (p00 * (1.0 - tx) + p10 * tx) * (1.0 - ty) + (p01 * (1.0 - tx) + p11 * tx) * ty;
  return max(v, k.b.w);
}

fn cone_read(tab: i32) -> Cone {
  return Cone(ctab_at(vec2<i32>(tab, 0)), ctab_at(vec2<i32>(tab + 1, 0)), ctab_at(vec2<i32>(tab + 2, 0)),
              ctab_at(vec2<i32>(tab + 3, 0)), ctab_at(vec2<i32>(tab + 4, 0)), ctab_at(vec2<i32>(tab + 5, 0)),
              ctab_at(vec2<i32>(tab + 6, 0)), ctab_at(vec2<i32>(tab + 7, 0)));
}

// the cone at grid point q (a grid of step `step`): its patch for an aged cone, else the exact profile
fn cone_at_grid(q: vec2<i32>, step: f32, k: Cone) -> f32 {
  if (k.g.w > 0.0) { return cone_aged(q, k); }
  return cone_fresh(k.h.xy + (vec2<f32>(q) + 0.5) * step, k);
}
