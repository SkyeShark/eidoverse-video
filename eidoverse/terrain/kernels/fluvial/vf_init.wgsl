// The port's own kernel (no Blender counterpart): the paths of blender/eidoblend/terrain/solvers/fluvial.py
// op_valley_floor at f90c6fc, which numpy starts from the D8 receivers:
//   uMode 0   the count of the channel cells inside the window (not on its outer ring) with no receiver: numpy's
//             np.any((rec < 0) & chan & inner), which switches op_valley_floor to the lake-filled routing surface
//   uMode 1   every cell's pointer to its first channel cell down its path and the path's length to it, before the
//             pointer jumping: stop = chan | no receiver; t = stop ? the cell : its receiver; dist = stop ? 0 :
//             cell sqrt(di^2 + dj^2)
//   uMode 2   outT = the cell's own index (the path maximum's starting cell)
//! sampler rec r32i    d8_receivers: row-major index, -1 none
//! sampler chan        1 on channel cells
//! image   outT r32ui
//! image   outD r32f
//! image   count atomic_u32
//! uniform int uMode
//! uniform float uCell

fn kmain(p: vec2<i32>) {
  let n = chan_size();
  if (!inside(p, n)) { return; }
  let i = p.y * n.x + p.x;
  let r = rec_at(p);
  let c = chan_at(p).x > 0.5;
  if (u.uMode == 0) {
    let inner = p.x > 0 && p.y > 0 && p.x < n.x - 1 && p.y < n.y - 1;
    if (r < 0 && c && inner) { atomicAdd(&count_b[0], 1u); }
    return;
  }
  if (u.uMode == 2) {
    outT_store(p, u32(i));
    return;
  }
  if (c || r < 0) {
    outT_store(p, u32(i));
    outD_store(p, vec4<f32>(0.0, 0.0, 0.0, 0.0));
    return;
  }
  let di = r % n.x - p.x;
  let dj = r / n.x - p.y;
  outT_store(p, u32(r));
  outD_store(p, vec4<f32>(u.uCell * sqrt(f32(di * di + dj * dj)), 0.0, 0.0, 0.0));
}
