// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py smooth_along at f90c6fc over four per-seed
// values at once (repeated round(2 sigma^2) times by solvers/glacial.js: a Gaussian of sigma cells):
//     up = main;  down = rcv where cont | (link_tributaries & rcv >= 0), else -1
//     vu = v[up] where up >= 0, else v;  vd = v[down] where down >= 0, else v
//     v = 0.25 vu + 0.5 v + 0.25 vd
// channels x and y with link_tributaries (a tributary's last cells stay attached to the trunk: centrelines' xy),
// channels z and w without (its zc and f).
// numpy smooths in float64. In float32 the same sums round at the values' own size every pass (positions of tens of
// kilometres: millimetres a pass, 288 passes), so here each seed's value is kept as its start r (the cell's centre,
// its h, its f: seed_init.wgsl, exact) plus an offset e, and the pass is the same sum on the offsets with the
// neighbours' start differences, which are small and exact (whole cells, nearby heights):
//     e = 0.25 ((r[up] - r) + e[up]) + 0.5 e + 0.25 ((r[down] - r) + e[down])      (uMode 0, from e = 0)
//     v = r + e                                                                     (uMode 1)
// the same quantity, rounded at the offsets' size each pass and once at the value's (PORT_PLAN.md risk 2: a
// better-conditioned form where an f32 form loses to float64).
//! sampler V                per seed: the start values r (x, y, zc, f)
//! sampler E                per seed: the offsets so far
//! sampler main r32i        the main donor (up), -1 none
//! sampler rcv r32i         the receiver, -1 none
//! sampler flags r32ui      bit 0: cont (the receiver continues the stream)
//! image   outV rgba32f     uMode 0: the offsets after this pass; uMode 1: the smoothed values
//! uniform int uMode
//! uniform int uCount       the seeds

fn kmain(p: vec2<i32>) {
  let w = outV_size().x;
  let s = p.y * w + p.x;
  if (p.x >= w || s >= u.uCount) { return; }
  let r = V_b[s];
  let e = E_b[s];
  if (u.uMode == 1) {
    outV_b[s] = r + e;
    return;
  }
  let up = main_b[s];
  let rc = rcv_b[s];
  var eu = e;
  if (up >= 0) { eu = (V_b[up] - r) + E_b[up]; }
  var el = e;
  var ec = e;
  if (rc >= 0) {
    el = (V_b[rc] - r) + E_b[rc];
    if ((flags_b[s] & 1u) != 0u) { ec = el; }
  }
  let a = 0.25 * eu.xy + 0.5 * e.xy + 0.25 * el.xy;
  let b = 0.25 * eu.zw + 0.5 * e.zw + 0.25 * ec.zw;
  outV_b[s] = vec4<f32>(a, b);
}
