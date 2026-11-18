// Port of blender/eidoblend/terrain/masks.py at f90c6fc: sky_view's near march and its sum. Per azimuth k the
// largest horizon tangent over the near shifts (masks/march.wgsl's arithmetic, from 0), then the far field of its
// block (np.fmax with _fmax_blocks' nearest upsampling: coarse cell (j / f, i / f)), then
// 1 - (1 / dirs) sum_k b / sqrt(1 + b^2) in numpy's steps: tmp = b b; tmp += 1; tmp = sqrt(tmp); tmp = b / tmp;
// acc += tmp, over k in order; acc *= -1 / dirs; acc += 1.
//! include masks/lib
//! sampler src           the level padded by uM cells (NOH beyond every level)
//! sampler obs           h
//! sampler shifts        the near march's shifts (di, dj, 1 / distance, k), sorted by azimuth
//! sampler far           the far field per azimuth ((dirs x Ny) x Nx), or a 1 x 1 dummy (uF 0)
//! image   outF r32f
//! uniform int uM
//! uniform int uCount
//! uniform int uDirs
//! uniform int uF        the far field's block factor; 0: no far field
//! uniform int uFarH     Ny: the far field's rows per azimuth
//! uniform float uInvDirs   float32(-1 / dirs)

fn kmain(p: vec2<i32>) {
  let n = outF_size();
  if (!inside(p, n)) { return; }
  var best: array<f32, 64>;
  for (var k = 0; k < u.uDirs; k++) { best[k] = 0.0; }
  let z = obs_at(p).x;
  let m = u.uM;
  for (var e = 0; e < u.uCount; e++) {
    let s = shifts_at(vec2<i32>(e, 0));
    let v = src_at(vec2<i32>(m + p.x + i32(s.x), m + p.y + i32(s.y))).x;
    if (has_h(v)) {
      let k = i32(s.w);
      best[k] = max(best[k], (v - z) * s.z);
    }
  }
  var acc = 0.0;
  for (var k = 0; k < u.uDirs; k++) {
    var b = best[k];
    if (u.uF > 0) { b = max(b, far_at(vec2<i32>(p.x / u.uF, k * u.uFarH + p.y / u.uF)).x); }
    var t = b * b;
    t = t + 1.0;
    t = sqrt(t);
    t = b / t;
    acc = acc + t;
  }
  acc = acc * u.uInvDirs;
  acc = acc + 1.0;
  outF_store(p, vec4<f32>(acc, 0.0, 0.0, 0.0));
}
