// Port of the end of blender/eidoblend/terrain/solvers/karst.py evaluate() at f90c6fc, as a kernel over the level's
// cells: the cockpits' soil floors put in, the river's water, the outputs.
//     floor   = the plan's floor map at the cell (fmap[fj][:, fi] where both lie inside it), else the level's own
//               basins' floors (own: _cockpit_floors on this level) where it has them, else -inf
//     soil    = floor > h + 0.05;  h = max(h, floor), then float32
//     wet     = (in_channel mean > 0.5) & (h < water level mean);  water = water level - h where wet
//     deposit = max(h - bed, 0); tower_id -1 where the soil floor is the surface
// uFill 0 leaves the cockpits unfilled (the floor map's own evaluation). The floor map's column and row of each cell
// come from the CPU in doubles (fidx: per column fi, per row fj; -1 outside the map).

//! sampler A rgba32f         per cell: h, bed, talus, plain (compose.wgsl)
//! sampler B rgba32f         per cell: water level, in_channel, dry share, 0
//! sampler own r32i          per cell: the owner (tower_id before the soil)
//! sampler fmap              the plan's floor map (or a stand-in)
//! sampler fidx r32i         row 0: fi per column; row 1: fj per row
//! sampler lvl               the level's own floors (uOwn 1)
//! image   outH r32f
//! image   outW r32f         the water's depth
//! image   outD r32f         deposit
//! image   outT r32i         tower_id
//! uniform int uFill
//! uniform int uOwn
fn kmain(p: vec2<i32>) {
  let n = outH_size();
  if (!inside(p, n)) { return; }
  let a = A_at(p);
  let b = B_at(p);
  var h = a.x;
  var tid = own_at(p);
  if (u.uFill != 0) {
    let fi = fidx_at(vec2<i32>(p.x, 0));
    let fj = fidx_at(vec2<i32>(p.y, 1));
    var fl = bitcast<f32>(0xff800000u);
    if (fi >= 0 && fj >= 0) {
      fl = fmap_at(vec2<i32>(fi, fj)).x;
    } else if (u.uOwn != 0) {
      fl = lvl_at(p).x;
    }
    if (fl > h + 0.05) { tid = -1; }
    h = max(h, fl);
  }
  var water = 0.0;
  if (b.y > 0.5 && h < b.x) { water = b.x - h; }
  outH_store(p, vec4<f32>(h, 0.0, 0.0, 0.0));
  outW_store(p, vec4<f32>(water, 0.0, 0.0, 0.0));
  outD_store(p, vec4<f32>(max(h - a.y, 0.0), 0.0, 0.0, 0.0));
  outT_store(p, tid);
}
