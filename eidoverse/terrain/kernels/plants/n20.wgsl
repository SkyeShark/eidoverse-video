// plants/n20: plants.py _normal_20m and its fallbacks (blender/eidoblend/terrain/build/plants.py at f9fba8c), for a
// level without the surface bake's n20: uMode 0 pads h - mu by reflection by m cells on every side (np.pad
// mode='reflect', the edge not repeated); uMode 1 takes the blurred padded field's middle n x n, adds mu back, and
// gives the normal of it (np.gradient: central differences inside, one-sided at the edges; (-gx, -gy) / sqrt(1 + gx^2
// + gy^2)); uMode 2 the normal from the masks' slope and aspect (degrees): (t sin a, t cos a) / sqrt(1 + t^2), t the
// slope's tangent. Float32 where numpy's is float64.
//! include prims/lib
//! sampler a r32f        mode 0: h (n x n); mode 1: the blurred padded field; mode 2: slope
//! sampler b r32f        mode 2: aspect (unread otherwise)
//! image   outX r32f     mode 0: the padded field ((n + 2m)^2); modes 1, 2: the normal's x (n x n)
//! image   outY r32f     modes 1, 2: the normal's y
//! uniform int   uMode
//! uniform int   uM      the padding, cells
//! uniform int   uN      the level's n
//! uniform float uMu     h's mean
//! uniform float uCell

fn hb(i: i32, j: i32) -> f32 {
  let w = u.uN + 2 * u.uM;
  return a_b[(j + u.uM) * w + i + u.uM] + u.uMu;
}

fn kmain(p: vec2<i32>) {
  let n = u.uN;
  if (u.uMode == 0) {
    let w = n + 2 * u.uM;
    if (p.x >= w || p.y >= w) { return; }
    let i = reflect_index(p.x - u.uM, n);
    let j = reflect_index(p.y - u.uM, n);
    outX_b[p.y * w + p.x] = a_b[j * n + i] - u.uMu;
    return;
  }
  if (p.x >= n || p.y >= n) { return; }
  var gx: f32;
  var gy: f32;
  if (u.uMode == 1) {
    let c = u.uCell;
    if (p.x == 0) { gx = (hb(1, p.y) - hb(0, p.y)) / c; }
    else if (p.x == n - 1) { gx = (hb(n - 1, p.y) - hb(n - 2, p.y)) / c; }
    else { gx = (hb(p.x + 1, p.y) - hb(p.x - 1, p.y)) / (2.0 * c); }
    if (p.y == 0) { gy = (hb(p.x, 1) - hb(p.x, 0)) / c; }
    else if (p.y == n - 1) { gy = (hb(p.x, n - 1) - hb(p.x, n - 2)) / c; }
    else { gy = (hb(p.x, p.y + 1) - hb(p.x, p.y - 1)) / (2.0 * c); }
    let L = sqrt(1.0 + gx * gx + gy * gy);
    outX_b[p.y * n + p.x] = -gx / L;
    outY_b[p.y * n + p.x] = -gy / L;
    return;
  }
  let t = tan(radians(a_b[p.y * n + p.x]));
  let az = radians(b_b[p.y * n + p.x]);
  let L = sqrt(1.0 + t * t);
  outX_b[p.y * n + p.x] = t * sin(az) / L;
  outY_b[p.y * n + p.x] = t * cos(az) / L;
}
