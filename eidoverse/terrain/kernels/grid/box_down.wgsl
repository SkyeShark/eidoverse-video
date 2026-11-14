// Port of blender/eidoblend/terrain/core/grid.py at f90c6fc: box_down, the integer box average by f on both axes
// (a.reshape(h // f, f, w // f, f).mean(axis=(1, 3))). float32: each block row summed, the row sums summed, then
// divided by f * f (numpy sums the float64 copy and divides once).
//! sampler src           the field (its first channel); its size divides by f
//! image   outF r32f     h / f x w / f
//! uniform int uF

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  let f = u.uF;
  var s = 0.0;
  for (var b = 0; b < f; b++) {
    var r = 0.0;
    for (var a = 0; a < f; a++) { r += src_at(vec2<i32>(p.x * f + a, p.y * f + b)).x; }
    s += r;
  }
  outF_store(p, vec4<f32>(s / f32(f * f), 0.0, 0.0, 0.0));
}
