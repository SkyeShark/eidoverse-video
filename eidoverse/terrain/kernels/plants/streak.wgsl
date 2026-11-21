// plants/streak: plants.py _Ground.fall_streak's line integral convolution (blender/eidoblend/terrain/build/plants.py
// at f9fba8c), per texel of a level's 20 m normal grid: the world noise averaged along the texel's streamline down
// and up the 20 m normal's slope, k steps of max(cell, 12 m) either way (the fall line's direction read at the
// nearest texel, the noise bilinear), the noise itself on ground under 3 degrees. uMode 1 maps the raw values to
// the levels' shared stretch, clip(0.1 + 0.8 (a - lo) / max(hi - lo, 1e-6), 0, 1), lo and hi the main level's 5th
// and 95th percentiles. A streamline is followed as its offset from its own texel's centre (float32 metres, at most
// 240 m), and the texel and the weights are taken from the offset's whole cells and fraction: Blender's float64
// positions decide which cell's direction a step reads, and a float32 position measured from the window's corner
// (an error of up to 5e-4 m at 8 km) took the neighbouring cell's at one texel in a thousand.
//! sampler nx r32f       the 20 m normal's x (n x n)
//! sampler ny r32f       and y
//! sampler noise r32f    the world noise at the texel centres (plants/noise_raster), n x n
//! image   outV r32f     the raw streak (uMode 0), or the mapped value (uMode 1, read from noise)
//! uniform float uCell   the grid's texel, metres
//! uniform float uStep   max(cell, 12)
//! uniform int   uK      max(round(240 / step), 1)
//! uniform vec2  uLoHi   lo, hi (uMode 1)
//! uniform int   uMode

const SIN3: f32 = 0.052335956242943835;

fn nv(n: i32, i: i32, j: i32) -> f32 { return noise_b[j * n + i]; }

fn kmain(p: vec2<i32>) {
  let sz = nx_size();
  if (!inside(p, sz)) { return; }
  let n = sz.x;
  if (u.uMode == 1) {
    let a = noise_b[p.y * n + p.x];
    outV_store(p, vec4<f32>(clamp(0.1 + 0.8 * (a - u.uLoHi.x) / max(u.uLoHi.y - u.uLoHi.x, 1e-6), 0.0, 1.0), 0.0, 0.0, 0.0));
    return;
  }
  let g0 = length(vec2<f32>(nx_at(p).x, ny_at(p).x));
  let here = nv(n, p.x, p.y);
  if (g0 < SIN3) {
    outV_store(p, vec4<f32>(here, 0.0, 0.0, 0.0));
    return;
  }
  let cell = u.uCell;
  var acc = here;
  var cnt = 1.0;
  for (var sgn = 0; sgn < 2; sgn++) {
    let s = select(-1.0, 1.0, sgn == 0);
    var dx = 0.0;                            // the streamline's offset from the texel's centre, metres
    var dy = 0.0;
    for (var t = 0; t < u.uK; t++) {
      // floor((px - x0) / cell) = p + floor(0.5 + d / cell)
      let ii = clamp(p.x + i32(floor(0.5 + dx / cell)), 0, n - 1);
      let jj = clamp(p.y + i32(floor(0.5 + dy / cell)), 0, n - 1);
      let ax = nx_at(vec2<i32>(ii, jj)).x;
      let ay = ny_at(vec2<i32>(ii, jj)).x;
      let g = length(vec2<f32>(ax, ay));
      var ux = 0.0;
      var uy = 0.0;
      if (!(g < SIN3)) {
        ux = ax / max(g, 1e-12);
        uy = ay / max(g, 1e-12);
      }
      dx = dx + s * u.uStep * ux;
      dy = dy + s * u.uStep * uy;
      // fi = clip((px - x0) / cell - 0.5, 0, n - 1.001) = p + d / cell, as whole cells and a fraction
      let qx = dx / cell;
      let qy = dy / cell;
      var i0 = p.x + i32(floor(qx));
      var ti = qx - floor(qx);
      var j0 = p.y + i32(floor(qy));
      var tj = qy - floor(qy);
      if (i0 < 0) { i0 = 0; ti = 0.0; }
      if (f32(i0 - (n - 2)) + ti > 0.999) { i0 = n - 2; ti = 0.999; }
      if (j0 < 0) { j0 = 0; tj = 0.0; }
      if (f32(j0 - (n - 2)) + tj > 0.999) { j0 = n - 2; tj = 0.999; }
      acc += (nv(n, i0, j0) * (1.0 - ti) + nv(n, i0 + 1, j0) * ti) * (1.0 - tj) +
             (nv(n, i0, j0 + 1) * (1.0 - ti) + nv(n, i0 + 1, j0 + 1) * ti) * tj;
      cnt += 1.0;
    }
  }
  outV_store(p, vec4<f32>(acc / cnt, 0.0, 0.0, 0.0));
}
