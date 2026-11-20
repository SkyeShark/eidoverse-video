// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py centrelines at f90c6fc,
//     chan = (Q > 0) & (A >= channel_area_m2)
//     win  = the main tile's cells (fluvial._main_window);  Q_ref = Q[chan & win].max(), else Q[chan].max()
// as two masks the reductions read (core/prims.js stats with a mask). numpy compares the float32 area with the
// float64 constant; uArea is the smallest float32 at or above it, so the test is the same.
//! sampler Q                the ice discharge (m^3/yr)
//! sampler A                the D8 drainage area (m^2)
//! image   outC r32f        1 on chan, else 0
//! image   outW r32f        1 on chan inside the main tile's window, else 0
//! uniform float uArea      the smallest float32 at or above channel_area_m2
//! uniform ivec4 uWin       the main window's rows j0..j1 and columns i0..i1 (end exclusive)

fn kmain(p: vec2<i32>) {
  if (!inside(p, outC_size())) { return; }
  let c = Q_at(p).x > 0.0 && A_at(p).x >= u.uArea;
  let w = p.y >= u.uWin.x && p.y < u.uWin.y && p.x >= u.uWin.z && p.x < u.uWin.w;
  outC_store(p, vec4<f32>(select(0.0, 1.0, c), 0.0, 0.0, 0.0));
  outW_store(p, vec4<f32>(select(0.0, 1.0, c && w), 0.0, 0.0, 0.0));
}
