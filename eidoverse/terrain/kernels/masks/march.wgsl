// Port of blender/eidoblend/terrain/masks.py at f90c6fc: _march, the largest tangent of the horizon per azimuth:
// for every shift (di, dj) of the table, tan = (src[m + j + dj, m + i + di] - z) / (hypot(di, dj) cell) in float32
// as numpy computes it ((h - z) times float32(1 / distance)), its largest value per azimuth starting from 0 (np.fmax:
// a shift onto no terrain, NOH, never raises it). The table (masks.js marchShifts) holds the shifts _march takes,
// with Python's rounding and its skips, sorted by azimuth. uMode 1 writes each azimuth's maximum ((dirs x ny) x nx,
// row k ny + j: sky_view's far field); uMode 0 the largest over every azimuth (rock_shadow).
//! include masks/lib
//! sampler src           the padded grid, margin uM (NOH where there is no terrain)
//! sampler obs           the observer's height at the kept cells, ny x nx
//! sampler shifts        per entry (di, dj, float32(1 / (hypot(di, dj) cell)), azimuth k)
//! image   outB r32f
//! uniform int uM
//! uniform int uCount    entries
//! uniform int uDirs
//! uniform int uMode

fn kmain(p: vec2<i32>) {
  let n = obs_size();
  if (!inside(p, n)) { return; }
  let z = obs_at(p).x;
  let m = u.uM;
  var best = 0.0;
  var all = 0.0;
  var k = -1;
  for (var e = 0; e < u.uCount; e++) {
    let s = shifts_at(vec2<i32>(e, 0));
    let ke = i32(s.w);
    if (ke != k) {
      if (u.uMode == 1 && k >= 0) { outB_store(vec2<i32>(p.x, k * n.y + p.y), vec4<f32>(best, 0.0, 0.0, 0.0)); }
      k = ke;
      best = 0.0;
    }
    let v = src_at(vec2<i32>(m + p.x + i32(s.x), m + p.y + i32(s.y))).x;
    if (has_h(v)) {
      let t = (v - z) * s.z;
      best = max(best, t);
      all = max(all, t);
    }
  }
  if (u.uMode == 1) {
    if (k >= 0) { outB_store(vec2<i32>(p.x, k * n.y + p.y), vec4<f32>(best, 0.0, 0.0, 0.0)); }
  } else {
    outB_store(p, vec4<f32>(all, 0.0, 0.0, 0.0));
  }
}
