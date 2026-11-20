// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/strata.py offset() at f90c6fc,
// which numpy evaluates in float64 on the level's cell centres from the GPU's float32 noise:
//     out = -zs0 + tan(dip) (x cos az + y sin az)                          (mode 0, with up to four warps)
//     out = out + 3 amp f            for every warp, in order              (modes 0 and 1)
//     out = out - throw drop(side)   for every fault, drop = t^2 (3 - 2 t), t = clip(side / w + 0.5, 0, 1)   (mode 2)
//     out = out + rise (d / half_width)^2                                   (mode 3, the fold)
// A plane or a line's across-coordinate is evaluated as its value at cell (0, 0) plus its steps per column and per
// row, each made in doubles by solvers/strata.js and rounded once, so the float32 arithmetic here works on the
// level's own extent instead of world coordinates. float32 here, in numpy's order.
//! sampler prev     the offset so far (modes 1-3; a 1 x 1 stand-in in mode 0)
//! sampler w0       the warps' fields (1 x 1 stand-ins where unused)
//! sampler w1
//! sampler w2
//! sampler w3
//! image   outZ r32f
//! uniform int uMode     0: the plane and up to four warps, 1: four more warps, 2: a fault, 3: the fold
//! uniform vec4 uW       the warps' weights, 3 amp (0: unused)
//! uniform vec3 uP       the plane (mode 0) or the across-coordinate (modes 2-3): at cell (0, 0), per column, per row
//! uniform vec2 uF       mode 2: the fault zone's width (m) and its throw (m); mode 3: the half width (m), the rise (m)

fn kmain(p: vec2<i32>) {
  let n = outZ_size();
  if (!inside(p, n)) { return; }
  let lin = u.uP.x + f32(p.x) * u.uP.y + f32(p.y) * u.uP.z;
  var out = 0.0;
  if (u.uMode == 0) {
    out = lin;
  } else {
    out = prev_at(p).x;
  }
  if (u.uMode <= 1) {
    if (u.uW.x != 0.0) { out = out + u.uW.x * w0_at(p).x; }
    if (u.uW.y != 0.0) { out = out + u.uW.y * w1_at(p).x; }
    if (u.uW.z != 0.0) { out = out + u.uW.z * w2_at(p).x; }
    if (u.uW.w != 0.0) { out = out + u.uW.w * w3_at(p).x; }
  } else if (u.uMode == 2) {
    let t = clamp(lin / u.uF.x + 0.5, 0.0, 1.0);
    out = out - u.uF.y * (t * t * (3.0 - 2.0 * t));
  } else {
    let r = lin / u.uF.x;
    out = out + u.uF.y * (r * r);
  }
  outZ_store(p, vec4<f32>(out, 0.0, 0.0, 0.0));
}
