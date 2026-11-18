// Port of blender/eidoblend/terrain/masks.py at f90c6fc: curvatures, float32 step for step as numpy has them:
//   p = (e - w) k1, q = (n - s) k1, r = (e - c - c + w) k2, t = (n - c - c + s) k2,
//   sxy = (ne - nw - se + sw) kxy, pp = p p, qq = q q, pq2 = 2 p q sxy, g2 = pp + qq, inv = 1 / max(g2, 1e-30),
//   hss = (pp r + pq2 + qq t) inv, hnn = (qq r - pq2 + pp t) inv, iso = 0.5 (r + t), wgt = g2 / (g2 + tan^2),
//   profile = -(iso + wgt (hss - iso)), plan = -(iso + wgt (hnn - iso))
// (k1 = 0.5 / cell, k2 = 1 / cell^2, kxy = 0.25 / cell^2, tan = tan(flat_slope_deg): float32 of the doubles), on every
// interior cell of the smoothed grid; its outer ring copies the next one (np.pad(..., 1, mode='edge')).
//! sampler hb            the smoothed grid
//! image   outP r32f     profile curvature, 1/m (+ convex)
//! image   outT r32f     plan curvature, 1/m
//! uniform float uK1
//! uniform float uK2
//! uniform float uKxy
//! uniform float uTan2

fn b(i: i32, j: i32) -> f32 { return hb_at(vec2<i32>(i, j)).x; }

fn kmain(p: vec2<i32>) {
  let n = outP_size();
  if (!inside(p, n)) { return; }
  let q = clamp(p, vec2<i32>(1, 1), n - vec2<i32>(2, 2));
  let c = b(q.x, q.y);
  let e = b(q.x + 1, q.y);
  let w = b(q.x - 1, q.y);
  let no = b(q.x, q.y + 1);
  let so = b(q.x, q.y - 1);
  let gp = (e - w) * u.uK1;
  let gq = (no - so) * u.uK1;
  let r = (((e - c) - c) + w) * u.uK2;
  let t = (((no - c) - c) + so) * u.uK2;
  let sxy = (((b(q.x + 1, q.y + 1) - b(q.x - 1, q.y + 1)) - b(q.x + 1, q.y - 1)) + b(q.x - 1, q.y - 1)) * u.uKxy;
  let pp = gp * gp;
  let qq = gq * gq;
  let pq2 = ((2.0 * gp) * gq) * sxy;
  let g2 = pp + qq;
  let inv = 1.0 / max(g2, 1e-30);
  let hss = ((pp * r + pq2) + qq * t) * inv;
  let hnn = ((qq * r - pq2) + pp * t) * inv;
  let iso = 0.5 * (r + t);
  let wgt = g2 / (g2 + u.uTan2);
  outP_store(p, vec4<f32>(-(iso + wgt * (hss - iso)), 0.0, 0.0, 0.0));
  outT_store(p, vec4<f32>(-(iso + wgt * (hnn - iso)), 0.0, 0.0, 0.0));
}
