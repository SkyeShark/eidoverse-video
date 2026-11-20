// Port of the end of blender/eidoblend/terrain/solvers/coast.py nearest_crossing at f90c6fc (the numpy lines after
// the jump flood), as a kernel: the port runs no per-cell loop on the CPU (PORT_PLAN.md 2.4).
//
//     s = dev.read(A.src)
//     d = np.hypot(s[..., 0] - ii, s[..., 1] - jj)          (float64 there, float32 here)
//     d = np.where(s[..., 3] > 0.5, d, np.inf)
//     payload = s[..., 2]
// and, when uSign is 1, the sign and scale its callers apply next (plan_shore: np.where(sea, -d, d) * cell;
// op_coast: np.where(cut, -dist, dist) * cell), with a cell that has no crossing anywhere at +-uFar instead of
// +-inf (op_coast's np.where(np.isfinite(sd), sd, np.where(cut, -1e7, 1e7))).
//
// outD x: the distance (cells; uSign 1: metres, signed, - where neg > 0.5), y: the payload, z: 1 where a crossing
// was found, 0 where none was.

//! sampler st      the jump flood's state: x, y the nearest crossing (cells), z its payload, w 1 when one is known
//! sampler neg     x > 0.5 where the distance takes the minus sign (uSign 1)
//! image   outD rgba32f
//! uniform int uSign      0: the unsigned distance in cells (inf where none); 1: signed metres
//! uniform float uCell    metres per cell (uSign 1)
//! uniform float uFar     the stand-in distance of a cell with no crossing (uSign 1), metres
fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let s = st_at(p);
  let found = s.w > 0.5;
  let dx = s.x - f32(p.x);
  let dy = s.y - f32(p.y);
  var d = sqrt(dx * dx + dy * dy);
  if (u.uSign == 0) {
    if (!found) { d = bitcast<f32>(0x7f800000u); }
    outD_store(p, vec4<f32>(d, s.z, select(0.0, 1.0, found), 0.0));
    return;
  }
  var sd = d * u.uCell;
  if (!found) { sd = u.uFar; }
  if (neg_at(p).x > 0.5) { sd = -sd; }
  outD_store(p, vec4<f32>(sd, s.z, select(0.0, 1.0, found), 0.0));
}
