// Port of blender/eidoblend/terrain/solvers/karst.py _cockpit_floors at f90c6fc, its per-basin numbers, as a kernel
// over the coarse cells writing order-independent integer atomics (PORT_PLAN.md 2.3):
//   uPass 0  the depression mask: (filled - hc) > 1e-6 as 1 / 0 (outM, for core/prims.js label)
//   uPass 1  per label: np.minimum.at(bottom, lab, hc) and np.maximum.at(spill, lab, filled) as atomicMin / atomicMax
//            of the floats' order keys (prims/lib.wgsl fkey: exact); np.bincount(lab) (area); the rim cells
//            (inner & ~((rolling_min_1(lab_o) == lab) & (rolling_max_1(lab_o) == lab)), lab_o = lab where inner,
//            else -1, edges clamped) counted per label
//   uPass 2  at_bottom: a label holds a cell at its bottom (hc <= bottom[lab]: its key equal to the minimum's) whose
//            block is allowed
// The label arrays are lists of count + 1 items; the dispatch covers the coarse grid.

//! sampler hc
//! sampler filled
//! sampler al
//! sampler lab r32ui
//! image   outM r32ui
//! image   bot atomic_u32
//! image   spl atomic_u32
//! image   area atomic_u32
//! image   rim atomic_u32
//! image   atb atomic_u32
//! uniform int uPass
//! uniform int uW            the coarse grid's side
//! include prims/lib
fn labo(q: vec2<i32>) -> i32 {
  let c = clamp(q, vec2<i32>(0), vec2<i32>(u.uW - 1));
  let l = lab_at(c);
  return select(-1, i32(l), l > 0u);
}

fn kmain(p: vec2<i32>) {
  let n = vec2<i32>(u.uW, u.uW);
  if (!inside(p, n)) { return; }
  let h = hc_at(p).x;
  if (u.uPass == 0) {
    outM_store(p, select(0u, 1u, (filled_at(p).x - h) > 1e-6));
    return;
  }
  let l = lab_at(p);
  if (u.uPass == 1) {
    atomicMin(&bot_b[l], fkey(h));
    atomicMax(&spl_b[l], fkey(filled_at(p).x));
    atomicAdd(&area_b[l], 1u);
    if (l > 0u) {
      let me = i32(l);
      var lo = me;
      var hi = me;
      for (var dj = -1; dj <= 1; dj++) {
        for (var di = -1; di <= 1; di++) {
          let o = labo(p + vec2<i32>(di, dj));
          lo = min(lo, o);
          hi = max(hi, o);
        }
      }
      if (!(lo == me && hi == me)) { atomicAdd(&rim_b[l], 1u); }
    }
    return;
  }
  if (l > 0u && fkey(h) == atomicLoad(&bot_b[l]) && al_at(p).x > 0.5) { atomicMax(&atb_b[l], 1u); }
}
