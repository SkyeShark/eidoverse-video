// Port of blender/eidoblend/terrain/solvers/volcanic.py lava_rubble at f90c6fc, at the points of a grid: an aa flow's
// rubbly top, sum over scales of amp (1 - |tanh(0.9 n)|)^2, n = gradient_noise(x, y, scale, seed 7907 + 131 i + 29)
// / 0.24 (the grid path). And uMode 1, op_lava_rubble's weight: add = clip(1.6 lava, 0, 1) rubble. The port's own
// kernel: float32; the lattices keep an integer base and a float32 offset (noise.wgsl).
//! include volcanic/math
//! include volcanic/noise
//! sampler ntab          the scales' terms, two texels each (volcanic.js noiseTexels)
//! sampler amps          one amplitude per scale (a row)
//! sampler lava          mode 1: the flows' footprint; mode 0: a stand-in
//! sampler rub           mode 1: the rubble; mode 0: a stand-in
//! image   outF r32f
//! uniform int uMode
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  if (!inside(p, outF_size())) { return; }
  if (u.uMode == 1) {
    let w = clamp(1.6 * lava_at(p).x, 0.0, 1.0);
    outF_store(p, vec4<f32>(w * rub_at(p).x, 0.0, 0.0, 0.0));
    return;
  }
  var out = 0.0;
  for (var i = 0; i < u.uCount; i++) {
    let a = ntab_at(vec2<i32>(2 * i, 0));
    let b = ntab_at(vec2<i32>(2 * i + 1, 0));
    let l = lat_grid(vec2<i32>(a.xy), a.zw, b.x, p);
    let n = grad_noise(l.c, l.f, bitcast<u32>(b.y), true) / 0.24;
    let q = 1.0 - abs(tanh(0.9 * n));
    out = out + amps_at(vec2<i32>(i, 0)).x * (q * q);
  }
  outF_store(p, vec4<f32>(out, 0.0, 0.0, 0.0));
}
