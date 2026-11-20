// The port's own kernel: the walls' threshold of blender/eidoblend/terrain/solvers/glacial.py at f90c6fc (numpy over
// the level, float64 then float32; here float32 in numpy's order), one mode per expression:
//   uMode 0  carve_level:  wall = clip(trough_wall 1.5, 0, 1);  Sc = sc_range (1 - wall) + _wall_sc wall
//   uMode 1  refine_level: Sc = sc_range exp(range_flutes) (1 - wall) + _wall_sc(h) wall
//   uMode 2  refine_level on a hero level: base = max(sc_range (1 - wall) + _wall_sc wall, 1.05 hypot(gx, gy));
//            Sc = base exp(wall flutes + (1 - wall) range_flutes)
//   uMode 3  refine_level's K and G (and sc_range): where(trough > 0.02, the median outside the trough, a)
//   uMode 4  refine_level's out = trough < 0.02 (clip(trough, 0, 1) < 0.02), as a mask (1 / 0) the median reads
// with _wall_sc = tan(wall_deg) exp(wall_noise n [+ flutes]) (n the unit noise at the wall scales, 0 without; the
// flutes in mode 1 only, _wall_sc(h=h_in)), sc_range the level's Sc (or tan 35 degrees: uHasSc 0). The trough tests
// against numpy's float64 0.02 use the float32 bounds that decide them the same way (uIn, uOut).
//! sampler wall             trough_wall (mode 0, 1, 2: the wall weight from it)
//! sampler trough           mode 3: the trough mask
//! sampler sc               sc_range (mode 0: the level's Sc), or the field to restore (mode 3)
//! sampler noise            the unit noise at the wall scales (uHasNoise)
//! sampler fl               the walls' flutes (mode 1, 2)
//! sampler rf               the range's own flutes (mode 1, 2)
//! sampler gx               mode 2: the inherited surface's gradient
//! sampler gy
//! image   outS r32f
//! uniform int uMode
//! uniform float uTanWall   tan(wall_deg)
//! uniform float uNoiseAmp  wall_noise
//! uniform int uHasNoise
//! uniform int uHasSc       0: sc_range is tan(35 degrees) everywhere
//! uniform float uTan35
//! uniform float uMedian    mode 3: the median outside the trough
//! uniform float uIn        mode 3: trough > 0.02 is trough >= this (the smallest float32 above 0.02)
//! uniform float uOut       mode 4: trough < 0.02 is trough <= this (the largest float32 below 0.02)

fn kmain(p: vec2<i32>) {
  if (!inside(p, outS_size())) { return; }
  if (u.uMode == 3) {
    var o = sc_at(p).x;
    if (trough_at(p).x >= u.uIn) { o = u.uMedian; }
    outS_store(p, vec4<f32>(o, 0.0, 0.0, 0.0));
    return;
  }
  if (u.uMode == 4) {
    outS_store(p, vec4<f32>(select(0.0, 1.0, trough_at(p).x <= u.uOut), 0.0, 0.0, 0.0));
    return;
  }
  let wall = clamp(wall_at(p).x * 1.5, 0.0, 1.0);
  var scr = u.uTan35;
  if (u.uHasSc != 0) { scr = sc_at(p).x; }
  var ln = 0.0;
  if (u.uHasNoise != 0) { ln = u.uNoiseAmp * noise_at(p).x; }
  var o = 0.0;
  if (u.uMode == 0) {
    o = scr * (1.0 - wall) + u.uTanWall * exp(ln) * wall;
  } else if (u.uMode == 1) {
    o = scr * exp(rf_at(p).x) * (1.0 - wall) + u.uTanWall * exp(ln + fl_at(p).x) * wall;
  } else {
    let g = vec2<f32>(gx_at(p).x, gy_at(p).x);
    let base = max(scr * (1.0 - wall) + u.uTanWall * exp(ln) * wall, 1.05 * sqrt(g.x * g.x + g.y * g.y));
    o = base * exp(wall * fl_at(p).x + (1.0 - wall) * rf_at(p).x);
  }
  outS_store(p, vec4<f32>(o, 0.0, 0.0, 0.0));
}
