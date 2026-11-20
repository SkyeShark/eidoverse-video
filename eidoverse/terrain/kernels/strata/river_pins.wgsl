// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/rivers.py River.pins() at
// f90c6fc, which numpy evaluates over the channel's cells in float64 (bed(s, f), then the hold blend), then rounds to
// float32:
//     bed(s, f) = top - f (top - final),   top = max(interp(s, course s, top), final)   (top known and f < 1)
//     final(s)  = bed_m - gradient (s - s_through) - depth scour(s)    (smooth, the hero levels: - depth)
//     hold:       bed = wb pin_h + (1 - wb) bed,   wb = clip(hold, 0, 1)
//     pins:       pin_w = 1, pin_h = bed on the channel; the base pins elsewhere
// The arc length is the cell's nearest segment k and the parameter t along it (river_channel.wgsl), s = s_k + t L_k,
// and the course's per-point table (solvers/rivers.js, made in doubles and rounded once) keeps every term small:
// top and a replaced final are linear along a segment (np.interp; op_incise's graded bed has its breakpoints at
// course points), the bed line is line_k - t gradient L_k, and the scour's position past its crest is the segment's
// own offset s_k - c[j_k] plus t L_k, stepped past later crests. The scour takes max(sin, 0) before the power 0.6:
// float32's pi exceeds pi, so sin(pi v^0.75) at v = 1 is -8.7e-8 here where numpy's is +1.2e-16 (a negative base
// would give NaN), and v^0.75 is 0 at v = 0, as numpy's.
//! sampler mask r32f      1 on the channel
//! sampler segk r32ui     the nearest segment k
//! sampler segt r32f      the parameter along it
//! sampler bw r32f        the base pins' weight
//! sampler bh r32f        the base pins' height
//! sampler hold r32f      a child level's border-band weights (a 1 x 1 stand-in without)
//! sampler crs rgba32f    per course point k, 2 texels: (top_k, fin_k, gradient L_k, L_k), (s_k - c[j_k], j_k, 0, 0)
//! sampler cw r32f        the crests' spacings c[j + 1] - c[j]
//! image   outW r32f
//! image   outH r32f
//! uniform float uF       the fraction of the fall done
//! uniform float uDepth   the pools' depth (0: none)
//! uniform float uRiffle  the riffle's share of a pool's reach, min(max(r, 0), 0.9)
//! uniform int uNc        the crests' count
//! uniform ivec4 uMode    x: the final bed 0 (the bed line, with the pools) or 1 (a table: a replaced final),
//                         y: top known and f < 1, z: smooth (a hero level), w: hold given

const PI_F: f32 = 3.14159265358979;

fn scour(ds0: f32, j0: i32) -> f32 {
  var ds = ds0;
  var j = j0;
  while (j < u.uNc - 2 && ds >= cw_b[j]) {
    ds -= cw_b[j];
    j += 1;
  }
  let uu = clamp(ds / cw_b[j], 0.0, 1.0);
  let r = u.uRiffle;
  let v = clamp((uu - r) / (1.0 - r), 0.0, 1.0);
  if (uu > r) {
    let pv = select(0.0, pow(v, 0.75), v > 0.0);
    return pow(max(sin(PI_F * pv), 0.0), 0.6);
  }
  return 0.0;
}

fn kmain(p: vec2<i32>) {
  let n = outW_size();
  if (!inside(p, n)) { return; }
  let w = bw_at(p).x;
  let ph = bh_at(p).x;
  if (mask_at(p).x < 0.5) {
    outW_store(p, vec4<f32>(w, 0.0, 0.0, 0.0));
    outH_store(p, vec4<f32>(ph, 0.0, 0.0, 0.0));
    return;
  }
  let k = i32(segk_at(p));
  let t = segt_at(p).x;
  let a = crs_b[2 * k];
  let c = crs_b[2 * k + 1];
  let b = crs_b[2 * k + 2];
  var fin = 0.0;
  if (u.uMode.x == 1) {
    fin = a.y + t * (b.y - a.y);
  } else {
    fin = a.y - t * a.z;
    if (u.uDepth > 0.0) {
      if (u.uMode.z == 1) {
        fin -= u.uDepth;
      } else {
        fin -= u.uDepth * scour(c.x + t * a.w, i32(c.y));
      }
    }
  }
  var bed = fin;
  if (u.uMode.y == 1) {
    let top = max(a.x + t * (b.x - a.x), fin);
    bed = top - u.uF * (top - fin);
  }
  if (u.uMode.w == 1) {
    let wb = clamp(hold_at(p).x, 0.0, 1.0);
    bed = wb * ph + (1.0 - wb) * bed;
  }
  outW_store(p, vec4<f32>(1.0, 0.0, 0.0, 0.0));
  outH_store(p, vec4<f32>(bed, 0.0, 0.0, 0.0));
}
