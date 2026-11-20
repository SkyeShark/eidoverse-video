// Port of the cell-by-cell parts of blender/eidoblend/terrain/solvers/volcanic.py op_volcano_lakes, _carried_lakes
// and op_caldera_lake at f90c6fc. numpy reduces per depression with np.maximum.at, np.bincount and np.lexsort; here
// the same quantities come from integer atomics (exact: maxima of non-negative float bits, counts, the smallest index
// among the deepest cells), solvers/volcanic.js decides per depression (a few hundred objects) as numpy does, and the
// decisions come back as a flag per label. The port's own kernel. Modes (uMode):
//   0  per label (five words: stats[5 L ..]): maxd = max depth (atomicMax of its bits), area = cells, near = any cell
//      within uR of the centre, band = any cell in the border band (edge distance < uBand)   (a: depth)
//   1  per label: word 4 (from NONE) = the smallest row-major index of the cells whose depth is the label's max
//      (lexsort((-depth, lab))'s first of each label)                         (a: depth)
//   2  water = lake[lab] ? depth : 0; add = fill ? depth : 0, fill = lab > 0 & !lake & !dry (& edge distance > 2 on a
//      child level) (& band[lab] on a hero level with hero_pits 'keep')       (a: depth, b: edge distance; flags)
//   3  a playa: add = lab == uLabel ? max(smooth_max(h, top, k) - h, 0) : add  (a: h, c: add, in place on outF)
//   4  _carried_lakes: g > 0.5 LAKE_NONE ? max(g - h, 0) : 0                     (a: g, the lake levels dilated, b: h)
//   5  the finish: h2 = h + add; carried = add > 0 ? max(carried - add, 0) : carried; water = max(water, carried);
//      outF = h2, outG = water, outH = water > 1e-3 ? h2 + water : LAKE_NONE   (a: h, b: add, c: water, d: carried)
//   6  caldera_lake's water: lab == uLabel ? (Lhi - h) + Llo : 0               (a: h)
//   7  caldera_lake's surface: water > 0 ? Lhi : h; and the dilated-water mask's keys (a: h, b: water)
//   8  np.bincount(lab[a > uK]): stats[L] counts the cells of label L where a > uK (the caldera floor at 0.5, the
//      carried lakes at 1e-3)
//   9  caldera_lake's own pits: depth = max(filled - surf, 0) (a: filled, b: surf)
//  10  caldera_lake: own[dl] marked where water > 0 or the dilated water > 0.5 (a: water, b: dilated water)
//  11  caldera_lake: pit = water > 0 | own[dl] ? 0 : depth (a: depth, b: water)
//  12  basins_kept: the depressions deeper than uR kept as they are: L > 0 & maxd[L] > uR ? h : filled (a: h, b:
//      filled; the stats of mode 0)
//! include prims/lib
//! include volcanic/math
//! sampler a
//! sampler b
//! sampler c
//! sampler d
//! sampler lab r32ui
//! sampler flags r32ui      per label: bit 0 lake, bit 1 dry, bit 2 band (mode 2)
//! image   stats atomic_u32 per label: five words (modes 0, 1); a count (8); the own flag (10, 11)
//! image   outF r32f
//! image   outG r32f
//! image   outH r32f
//! uniform int uMode
//! uniform vec2 uOrg        the level's origin minus the centre (mode 0)
//! uniform float uStep
//! uniform float uR         mode 0: the lake radius (< 0: none); mode 3: top; modes 6, 7: Lhi
//! uniform float uK         mode 3: the fillet's width; mode 6: Llo
//! uniform int uBand        mode 0: the border band; mode 2: 1 on a child level, + 2 for hero_pits 'keep'
//! uniform int uLabel

const LAKE_NONE: f32 = -1.0e6;

fn kmain(p: vec2<i32>) {
  let own = u.uMode == 4 || u.uMode == 5 || u.uMode == 7 || u.uMode == 9;    // no labels (lab a stand-in): a's cells
  let n = select(lab_size(), a_size(), own);
  if (!inside(p, n)) { return; }
  var L = 0u;
  if (!own) { L = lab_at(p); }
  let idx = u32(p.y * n.x + p.x);
  switch u.uMode {
    case 0: {
      if (L == 0u) { return; }
      atomicMax(&stats_b[5u * L], bitcast<u32>(max(a_at(p).x, 0.0)));
      atomicAdd(&stats_b[5u * L + 1u], 1u);
      if (u.uR >= 0.0) {
        let dd = u.uOrg + (vec2<f32>(p) + 0.5) * u.uStep;
        if (length(dd) < u.uR) { atomicMax(&stats_b[5u * L + 2u], 1u); }
      }
      let e = min(min(p.x, p.y), min(n.x - 1 - p.x, n.y - 1 - p.y));
      if (e < u.uBand) { atomicMax(&stats_b[5u * L + 3u], 1u); }
    }
    case 1: {
      if (L == 0u) { return; }
      if (bitcast<u32>(max(a_at(p).x, 0.0)) == atomicLoad(&stats_b[5u * L])) { atomicMin(&stats_b[5u * L + 4u], idx); }
    }
    case 2: {
      let dep = a_at(p).x;
      var water = 0.0;
      var add = 0.0;
      if (L > 0u) {
        let f = flags_at(vec2<i32>(i32(L), 0));
        let lake = (f & 1u) != 0u;
        let dry = (f & 2u) != 0u;
        let band = (f & 4u) != 0u;
        if (lake) { water = dep; }
        var fill = !lake && !dry;
        if ((u.uBand & 1) != 0) { fill = fill && b_at(p).x > 2.0; }
        if ((u.uBand & 2) != 0) { fill = fill && band; }
        if (fill) { add = dep; }
      }
      outF_store(p, vec4<f32>(water, 0.0, 0.0, 0.0));
      outG_store(p, vec4<f32>(add, 0.0, 0.0, 0.0));
    }
    case 3: {
      if (L == u32(u.uLabel)) {
        let h = a_at(p).x;
        outF_store(p, vec4<f32>(max(v_smooth_max(h, u.uR, u.uK) - h, 0.0), 0.0, 0.0, 0.0));
      }
    }
    case 4: {
      let g = a_at(p).x;
      outF_store(p, vec4<f32>(select(0.0, max(g - b_at(p).x, 0.0), g > 0.5 * LAKE_NONE), 0.0, 0.0, 0.0));
    }
    case 5: {
      let h = a_at(p).x;
      let add = b_at(p).x;
      let h2 = h + add;
      var carried = d_at(p).x;
      if (add > 0.0) { carried = max(carried - add, 0.0); }
      let water = max(c_at(p).x, carried);
      outF_store(p, vec4<f32>(h2, 0.0, 0.0, 0.0));
      outG_store(p, vec4<f32>(water, 0.0, 0.0, 0.0));
      outH_store(p, vec4<f32>(select(LAKE_NONE, h2 + water, water > 1e-3), 0.0, 0.0, 0.0));
    }
    case 6: {
      var w = 0.0;
      if (L == u32(u.uLabel)) { w = (u.uR - a_at(p).x) + u.uK; }
      outF_store(p, vec4<f32>(w, 0.0, 0.0, 0.0));
    }
    case 7: {
      outF_store(p, vec4<f32>(select(a_at(p).x, u.uR, b_at(p).x > 0.0), 0.0, 0.0, 0.0));
    }
    case 8: {
      if (L > 0u && a_at(p).x > u.uK) { atomicAdd(&stats_b[L], 1u); }
    }
    case 9: {
      outF_store(p, vec4<f32>(max(a_at(p).x - b_at(p).x, 0.0), 0.0, 0.0, 0.0));
    }
    case 10: {
      if (L > 0u && (a_at(p).x > 0.0 || b_at(p).x > 0.5)) { atomicStore(&stats_b[L], 1u); }
    }
    case 12: {
      var v = b_at(p).x;
      if (L > 0u && bitcast<f32>(atomicLoad(&stats_b[5u * L])) > u.uR) { v = a_at(p).x; }
      outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
    }
    default: {
      var v = a_at(p).x;
      if (b_at(p).x > 0.0) { v = 0.0; } else if (L > 0u && atomicLoad(&stats_b[L]) != 0u) { v = 0.0; }
      outF_store(p, vec4<f32>(v, 0.0, 0.0, 0.0));
    }
  }
}
