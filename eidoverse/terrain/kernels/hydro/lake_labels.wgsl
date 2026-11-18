// Port of the per-label reductions of blender/eidoblend/terrain/solvers/hydro.py lakes at f90c6fc, on the GPU
// (PORT_PLAN.md 3.2: "lakes (labels, per-label maximum by atomicMax)"):
//     np.maximum.at(maxd, lab.ravel(), depth.ravel())                        each depression's largest depth
//     touches[np.unique(lab[in_band & (lab > 0)])] = True                     it reaches into the border band
//     touches[np.unique(lab[no_lake & (lab > 0)])] = True                     it reaches into a flatten area
// Integer atomics on order-independent quantities only (plan 2.3): a depth is >= 0, so its float32 bits order as
// its value and atomicMax of the bits is the largest depth whatever the order; a touch is a 0/1 maximum. Exact.
//! include prims/lib
//! sampler lab r32ui        the depression labels (core/prims.js label: 1..n, 0 outside)
//! sampler depth            filled - h (lake_depth.wgsl)
//! sampler nolake           uNoLake 1: compose.flatten_mask of the flatten areas (a cell counts where it is > 0.5)
//! image   maxd atomic_u32  per label (a list of n + 1): the bits of its largest depth
//! image   touch atomic_u32 per label: 1 when one of its cells is in the border band or a flatten area
//! uniform int uBand        a child level's border band in cells (0: none): edge_distance < band
//! uniform int uNoLake

fn kmain(p: vec2<i32>) {
  let n = lab_size();
  if (!inside(p, n)) { return; }
  let l = lab_at(p);
  if (l == 0u) { return; }
  atomicMax(&maxd_b[l], bitcast<u32>(depth_at(p).x));
  let e = min(min(p.x, n.x - 1 - p.x), min(p.y, n.y - 1 - p.y));
  var t = false;
  if (u.uBand > 0 && e < u.uBand) { t = true; }
  if (u.uNoLake != 0 && nolake_at(p).x > 0.5) { t = true; }
  if (t) { atomicMax(&touch_b[l], 1u); }
}
