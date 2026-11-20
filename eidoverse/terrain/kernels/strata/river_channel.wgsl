// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/rivers.py channel() at f90c6fc,
// which numpy runs per segment over each segment's box. Here every cell visits the segments of its 16 x 16 tile
// (binned in course order by solvers/rivers.js, each with its box as numpy computes it), keeps those whose box holds
// it, and takes the nearest by a strict `<` in course order, numpy's rule:
//     t = clip(((X - a) . v) / L2, 0, 1),   dd = |X - (a + t v)|,   better = dd < d
// in float32 on offsets from the segment's start (the box's first cell centre minus a, made in doubles), so the
// arithmetic stays on a few hundred metres. A cell whose distance lies within uEps of the half width is flagged
// (outA): rivers.js decides it again in doubles, as numpy does, and kernels/strata/river_fix.wgsl writes it.
//! sampler tstart r32ui   the tile's first entry in tseg (tiles row-major, uTilesX across, one entry more than tiles)
//! sampler tseg r32ui     the segments of every tile, in course order (indices into segi and segf)
//! sampler segi r32i      per segment, 8 integers: k (its index on the course), i0, i1, j0, j1 (its box), 0, 0, 0
//! sampler segf rgba32f   per segment, 2 texels: (ox, oy, vx, vy), (L2, 0, 0, 0)
//! image   outD r32f      the distance to the course (m), +inf off every box
//! image   outK r32ui     the nearest segment's k (0xffffffff off every box)
//! image   outT r32f      the parameter along it (0..1)
//! image   outM r32f      1 on the channel (d <= uHalf), else 0
//! image   outA r32ui     1 where |d - uHalf| <= uEps: decided again in doubles
//! image   cnt atomic_u32  [0] channel cells not flagged, [1] flagged cells
//! uniform float uCell
//! uniform float uHalf
//! uniform float uEps
//! uniform int uTilesX

fn kmain(p: vec2<i32>) {
  let n = outD_size();
  if (!inside(p, n)) { return; }
  let tile = (p.y / 16) * u.uTilesX + (p.x / 16);
  let e0 = tstart_b[tile];
  let e1 = tstart_b[tile + 1];
  var best = bitcast<f32>(0x7f800000u);
  var bk = 0xffffffffu;
  var bt = 0.0;
  for (var e = e0; e < e1; e++) {
    let q = i32(tseg_b[e]);
    let i0 = segi_b[8 * q + 1];
    let i1 = segi_b[8 * q + 2];
    let j0 = segi_b[8 * q + 3];
    let j1 = segi_b[8 * q + 4];
    if (p.x < i0 || p.x >= i1 || p.y < j0 || p.y >= j1) { continue; }
    let a = segf_b[2 * q];
    let L2 = segf_b[2 * q + 1].x;
    let ex = a.x + f32(p.x - i0) * u.uCell;
    let ey = a.y + f32(p.y - j0) * u.uCell;
    let t = clamp((ex * a.z + ey * a.w) / L2, 0.0, 1.0);
    let dx = ex - t * a.z;
    let dy = ey - t * a.w;
    let dd = sqrt(dx * dx + dy * dy);
    if (dd < best) {
      best = dd;
      bk = u32(segi_b[8 * q]);
      bt = t;
    }
  }
  let on = best <= u.uHalf;
  let near = bk != 0xffffffffu && abs(best - u.uHalf) <= u.uEps;
  outD_store(p, vec4<f32>(best, 0.0, 0.0, 0.0));
  outK_store(p, bk);
  outT_store(p, vec4<f32>(bt, 0.0, 0.0, 0.0));
  outM_store(p, vec4<f32>(select(0.0, 1.0, on), 0.0, 0.0, 0.0));
  outA_store(p, select(0u, 1u, near));
  if (near) {
    atomicAdd(&cnt_b[1], 1u);
  } else if (on) {
    atomicAdd(&cnt_b[0], 1u);
  }
}
