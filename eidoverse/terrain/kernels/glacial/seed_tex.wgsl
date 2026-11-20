// The port's own kernel: blender/eidoblend/terrain/solvers/glacial.py seed_textures at f90c6fc, the jump flood's
// inputs on the level's grid, as a gather (each cell reads its own seed through pos, so no two writes meet):
//     cand0 = (idx, -1, -1, -1) at a seed cell, else -1
//     seedA = (x - x0, y - y0, zf, H)                   else 0
//     seedB = (max(W, 1e-3), stream id, fill, moraine)  else (1, 0, 0, 0)
//     seedC = (floor_f, rise_f, shoulder_cut, 0)        else (1, 1, 0, 0)   (default_seed_c)
// numpy writes float64 values cast to float32; these are the float32 per-seed values of solvers/glacial.js. outG is
// carve_level's glacial_streams: each seed cell's stream id, -1 elsewhere.
//! sampler pos r32i         per cell: its seed's position, -1 none
//! sampler V                per seed: x, y (m from the level's corner), zc, fs
//! sampler P                per seed: W, H, d, zf
//! sampler E                per seed: moraine, floor_f, rise_f, taper
//! sampler fill             per seed: the valley fill (m above zf)
//! sampler sid r32i         per seed: its stream id
//! image   cand0 rgba32f
//! image   seedA rgba32f
//! image   seedB rgba32f
//! image   seedC rgba32f
//! image   outG r32f        glacial_streams
//! uniform float uShCut     shoulder_cut (seedC.z of every seed)

fn kmain(p: vec2<i32>) {
  let n = cand0_size();
  if (!inside(p, n)) { return; }
  let s = pos_at(p);
  if (s < 0) {
    cand0_store(p, vec4<f32>(-1.0, -1.0, -1.0, -1.0));
    seedA_store(p, vec4<f32>(0.0, 0.0, 0.0, 0.0));
    seedB_store(p, vec4<f32>(1.0, 0.0, 0.0, 0.0));
    seedC_store(p, vec4<f32>(1.0, 1.0, 0.0, 0.0));
    outG_store(p, vec4<f32>(-1.0, 0.0, 0.0, 0.0));
    return;
  }
  let v = V_b[s];
  let q = P_b[s];
  let e = E_b[s];
  cand0_store(p, vec4<f32>(f32(p.y * n.x + p.x), -1.0, -1.0, -1.0));
  seedA_store(p, vec4<f32>(v.x, v.y, q.w, q.y));
  seedB_store(p, vec4<f32>(max(q.x, 1e-3), f32(sid_b[s]), fill_b[s], e.x));
  seedC_store(p, vec4<f32>(e.y, e.z, u.uShCut, 0.0));
  outG_store(p, vec4<f32>(f32(sid_b[s]), 0.0, 0.0, 0.0));
}
