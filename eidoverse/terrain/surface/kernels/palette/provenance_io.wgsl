// Port of numpy code of blender/eidoblend/terrain/surface/palette_bake.py at d67f19e (provenance), as a GPU kernel
// (the port's own, PORT_PLAN.md 3.2). provenance_io: the colour routing's inputs and outputs on a level's padded grid
// (N = n + 2 m cells, uM = m):
//   uMode 0  src: (P, P r, P g, P b) of the production a (x) and the rock colour b (rgb); uM 0: both are padded
//            already (the coarsest level: masks.pad_level 'edge'), else both are the window's (n x n) and the margin
//            is 0
//   uMode 1  pin: (0, 1 on the margin, 0 inside, 0, 0): the margin holds the parent's values
//   uMode 2  the window's results from the converged state a (rgba: Q, R): (clip(R / max(Q, 1e-12), 0, 1),
//            Q / (Q + uQ0)): down_colour and down_share (n x n)
//   uMode 3  the routing's change: |q - prev| / max(q, 1e-12) of a.x (now) and b.x (the last check), for its maximum
//! sampler a
//! sampler b
//! image   outV rgba32f
//! uniform int uMode
//! uniform int uM
//! uniform float uQ0

fn kmain(p: vec2<i32>) {
  let n = outV_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 0) {
    if (u.uM == 0) {
      let P = a_at(p).x;
      outV_store(p, vec4<f32>(P, P * b_at(p).xyz));
      return;
    }
    let q = p - vec2<i32>(u.uM, u.uM);
    if (q.x < 0 || q.y < 0 || q.x >= n.x - 2 * u.uM || q.y >= n.y - 2 * u.uM) {
      outV_store(p, vec4<f32>(0.0));
      return;
    }
    let P = a_at(q).x;
    outV_store(p, vec4<f32>(P, P * b_at(q).xyz));
    return;
  }
  if (u.uMode == 1) {
    let inner = p.x >= u.uM && p.y >= u.uM && p.x < n.x - u.uM && p.y < n.y - u.uM;
    outV_store(p, vec4<f32>(0.0, select(1.0, 0.0, inner), 0.0, 0.0));
    return;
  }
  if (u.uMode == 2) {
    let w = a_at(p + vec2<i32>(u.uM, u.uM));
    let Q = max(w.x, 1e-12);
    outV_store(p, vec4<f32>(clamp(w.yzw / Q, vec3<f32>(0.0), vec3<f32>(1.0)), Q / (Q + u.uQ0)));
    return;
  }
  let q = a_at(p).x;
  outV_store(p, vec4<f32>(abs(q - b_at(p).x) / max(q, 1e-12), 0.0, 0.0, 0.0));
}
