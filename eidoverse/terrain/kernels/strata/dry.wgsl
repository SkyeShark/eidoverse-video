// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/strata.py fill_dry_basins() at
// f90c6fc, numpy's float64 work on a level's heights after the fill (solvers/hydro.js fillDepressions, numpy's
// fill_depressions to the bit) and the labelling (core/prims.js label, metrics.label's numbering):
//   mode 0   depth = filled - h;   the depression mask depth > 1e-4 (u32)
//            (the float32 difference of two float32 heights is exact here, as numpy's float64 one; the comparison
//            with numpy's double 1e-4 is depth > uThr, the largest float32 below 1e-4, which decides it alike)
//   mode 1   keep = chan | roll(chan, +-1, axis 0) | roll(chan, +-1, axis 1)  (np.roll: wrapping);  a depression
//            touching it is kept: kept[label] = 1 (an atomic store of 1, order-free)
//   mode 2   fill = label > 0 & !kept[label] & edge distance >= hold;  h = h + depth (the fill's own height),
//            deposit = deposit + depth;  count the filled cells
//! sampler h          the level's height
//! sampler filled     its spill levels (mode 0)
//! sampler lab r32ui  the depressions' labels (modes 1-2)
//! sampler chan       the river's channel (mode 1; 1 x 1 stand-in without)
//! sampler dep        the deposit (mode 2; 1 x 1 stand-in without)
//! image   outM r32ui        mode 0: the depression mask
//! image   kept atomic_u32   modes 1-2: per label, 1 when the river's channel touches it
//! image   outH r32f         mode 2: h
//! image   outD r32f         mode 2: deposit
//! image   cnt atomic_u32    mode 2: [0] the filled cells
//! uniform int uMode
//! uniform float uThr
//! uniform int uHold
//! uniform int uHasDep
//! local   16 16

fn kmain(p: vec2<i32>) {
  let n = h_size();
  if (!inside(p, n)) { return; }
  if (u.uMode == 0) {
    let d = filled_at(p).x - h_at(p).x;
    outM_store(p, select(0u, 1u, d > u.uThr));
    return;
  }
  let l = lab_at(p);
  if (u.uMode == 1) {
    if (l == 0u) { return; }
    let xm = select(p.x - 1, n.x - 1, p.x == 0);
    let xp = select(p.x + 1, 0, p.x == n.x - 1);
    let ym = select(p.y - 1, n.y - 1, p.y == 0);
    let yp = select(p.y + 1, 0, p.y == n.y - 1);
    let k = chan_at(p).x > 0.5 || chan_at(vec2<i32>(xm, p.y)).x > 0.5 || chan_at(vec2<i32>(xp, p.y)).x > 0.5 ||
      chan_at(vec2<i32>(p.x, ym)).x > 0.5 || chan_at(vec2<i32>(p.x, yp)).x > 0.5;
    if (k) { atomicStore(&kept_b[l], 1u); }
    return;
  }
  let hh = h_at(p).x;
  var dd = 0.0;
  if (u.uHasDep == 1) { dd = dep_at(p).x; }
  var filling = l > 0u && atomicLoad(&kept_b[l]) == 0u;
  if (u.uHold > 0) {
    let e = min(min(p.x, p.y), min(n.x - 1 - p.x, n.y - 1 - p.y));
    filling = filling && e >= u.uHold;
  }
  if (filling) {
    let depth = filled_at(p).x - hh;
    outH_store(p, vec4<f32>(hh + depth, 0.0, 0.0, 0.0));
    outD_store(p, vec4<f32>(dd + depth, 0.0, 0.0, 0.0));
    atomicAdd(&cnt_b[0], 1u);
  } else {
    outH_store(p, vec4<f32>(hh, 0.0, 0.0, 0.0));
    outD_store(p, vec4<f32>(dd, 0.0, 0.0, 0.0));
  }
}
