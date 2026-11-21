// Port of numpy code of blender/eidoblend/terrain/surface/bake.py at d67f19e, as a GPU kernel (the port's own,
// PORT_PLAN.md 3.2). np_gradient: `gy, gx = np.gradient(hp, F(cell))` and g = sqrt(gx gx + gy gy) on the padded cell
// grid (the slope, the field normal's parts and the altitude the snowpack reads), as numpy computes them in
// float32: second-order central differences inside, (f[k + 1] - f[k - 1]) / float32(2 cell), and first-order ones at
// the edges, (f[1] - f[0]) / float32(cell) (np.gradient's edge_order 1).
//! sampler hp
//! image   outG rgba32f    gx, gy, g, 0
//! uniform float uDx       float32(cell)
//! uniform float uDx2      float32(2 cell)

fn axis(lo: f32, mid: f32, hi: f32, k: i32, n: i32) -> f32 {
  if (k == 0) { return (hi - mid) / u.uDx; }
  if (k == n - 1) { return (mid - lo) / u.uDx; }
  return (hi - lo) / u.uDx2;
}

fn kmain(p: vec2<i32>) {
  let n = hp_size();
  if (!inside(p, n)) { return; }
  let c = hp_at(p).x;
  let e = hp_at(vec2<i32>(min(p.x + 1, n.x - 1), p.y)).x;
  let w = hp_at(vec2<i32>(max(p.x - 1, 0), p.y)).x;
  let no = hp_at(vec2<i32>(p.x, min(p.y + 1, n.y - 1))).x;
  let so = hp_at(vec2<i32>(p.x, max(p.y - 1, 0))).x;
  let gx = axis(w, c, e, p.x, n.x);
  let gy = axis(so, c, no, p.y, n.y);
  outG_store(p, vec4<f32>(gx, gy, sqrt(gx * gx + gy * gy), 0.0));
}
