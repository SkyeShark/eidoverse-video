// Port of numpy code of blender/eidoblend/terrain/surface/__init__.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). derive: the names SurfaceData.maps() derives from others, cell by cell, in numpy's float32
// order:
//   uMode 0  insolation  max(0, sin s (sin a sin az + cos a cos az) cos el + cos s sin el), s and a the masks' slope
//                        and aspect in radians, az and el the bake's sun (uSun = sin az, cos az, cos el, sin el)
//   uMode 1  slope_20m   degrees(atan(sqrt(nxy2 / (1 - nxy2)))), nxy2 = min(n20_x^2 + n20_y^2, 0.9999)
//   uMode 2  src_strata  h + src_dz
//! sampler a
//! sampler b
//! image   outF r32f
//! uniform int uMode
//! uniform vec4 uSun

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var v = 0.0;
  if (u.uMode == 0) {
    let s = radians(a_at(p).x);
    let az = radians(b_at(p).x);
    v = max(sin(s) * (sin(az) * u.uSun.x + cos(az) * u.uSun.y) * u.uSun.z + cos(s) * u.uSun.w, 0.0);
  } else if (u.uMode == 1) {
    let x = a_at(p).x;
    let y = b_at(p).x;
    let nxy2 = min(x * x + y * y, 0.9999);
    v = degrees(atan(sqrt(nxy2 / (1.0 - nxy2))));
  } else {
    v = a_at(p).x + b_at(p).x;
  }
  outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
}
