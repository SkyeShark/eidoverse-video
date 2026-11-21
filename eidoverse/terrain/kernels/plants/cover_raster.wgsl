// plants/cover_raster: plants.py _cover_raster (blender/eidoblend/terrain/build/plants.py at f9fba8c): an exponent
// on a k x k grid as cover, 1 - exp(-v), bilinearly resampled to the level's m x m raster over the same window
// (_upsample: texel centres, t = clip((i + 0.5) k / m - 0.5, 0, k - 1), along x then along y).
//! sampler v r32f        the exponent (k x k)
//! image   outC r32f     the cover (m x m)
//! uniform int uK

fn cov(i: i32, j: i32) -> f32 { return 1.0 - exp(-v_b[j * u.uK + i]); }

fn axis(i: i32, k: i32, m: i32) -> vec2<f32> {
  if (k == 1) { return vec2<f32>(0.0, 0.0); }
  let t = clamp((f32(i) + 0.5) * (f32(k) / f32(m)) - 0.5, 0.0, f32(k) - 1.0);
  let i0 = min(i32(floor(t)), k - 2);
  return vec2<f32>(f32(i0), t - f32(i0));
}

fn kmain(p: vec2<i32>) {
  let n = outC_size();
  if (!inside(p, n)) { return; }
  let k = u.uK;
  let m = n.x;
  if (k == m) {
    outC_store(p, vec4<f32>(cov(p.x, p.y), 0.0, 0.0, 0.0));
    return;
  }
  if (k == 1) {
    outC_store(p, vec4<f32>(cov(0, 0), 0.0, 0.0, 0.0));
    return;
  }
  let ax = axis(p.x, k, m);
  let ay = axis(p.y, k, m);
  let i0 = i32(ax.x);
  let j0 = i32(ay.x);
  let wx = ax.y;
  let wy = ay.y;
  let r0 = cov(i0, j0) * (1.0 - wx) + cov(i0 + 1, j0) * wx;
  let r1 = cov(i0, j0 + 1) * (1.0 - wx) + cov(i0 + 1, j0 + 1) * wx;
  outC_store(p, vec4<f32>(r0 * (1.0 - wy) + r1 * wy, 0.0, 0.0, 0.0));
}
