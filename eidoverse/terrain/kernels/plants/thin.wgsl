// plants/thin: plants.py _thin's decisions (blender/eidoblend/terrain/build/plants.py at f9fba8c), per candidate,
// after its density, stature and exclusions are evaluated (the species' generated kernel) and its shade is known
// (plants/shade): the size the site lets it reach, prob = min(dens / dmax, 1) (an `around` candidate: its `where`),
// home = dens >= dmax / 2 and allowed, keep = allowed and _u(id, 11) < prob, then _u(id, 12) < 1 - shade (1 - tol);
// the record gains its hard-core radius, its mark _u(id, 13), its finest level and home. Every comparison of a
// uniform is exact on its 53-bit integer (plants/lib.wgsl u53_lt).
//
// The flags (one number a candidate) say what the stats count: 1 own (within the species' radius), 2 drawn (own and
// of the cluster process, not seeded), 4 clipped (drawn, dens > dmax x 1.0001), 8 home, 16 kept by the density,
// 32 kept by the density and the shade (plants/feet may clear it).
//! include plants/lib
//! sampler dens r32f     per candidate: its density, plants per m^2 (>= 0)
//! sampler allowed r32ui per candidate: 1 where the exclusions allow it
//! sampler stat r32f     per candidate: the stature factor (1 without a stature rule)
//! sampler shade r32f    per candidate: the shade of the trees placed before
//! sampler lvl r32ui     per candidate: the finest level holding it
//! sampler pw r32f       per candidate: an `around` candidate's `where` (unread without seeded candidates)
//! image   cand r32ui    the candidates' records: words 7, 11-15 written
//! image   outF r32ui    the flags
//! uniform vec4 uS       dmax (parents_per_ha mu 1e-4), the species' radius, 1 - shade tolerance, has stature
//! uniform vec4 uC       core_m, size_m[1], 0, 0
//! uniform int uCount

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let o = 16u * u32(i);
  let id = vec2<u32>(cand_b[o + 4u], cand_b[o + 5u]);
  var size = bitcast<f32>(cand_b[o + 7u]);
  if (u.uS.w > 0.5) { size = size * clamp(stat_b[i], 0.05, 1.0); }
  let dist = bitcast<f32>(cand_b[o + 9u]);
  let seeded = cand_b[o + 10u] != 0u;
  let d = dens_b[i];
  let dmax = u.uS.x;
  let ok = allowed_b[i] != 0u;
  let own = dist <= u.uS.y;
  let drawn = own && !seeded;
  var prob = min(d / dmax, 1.0);
  if (seeded) { prob = clamp(pw_b[i], 0.0, 1.0); }
  let home = d >= 0.5 * dmax && ok;
  let keepD = ok && u53_lt(u53(id, 11u), prob);
  let keep = keepD && u53_lt(u53(id, 12u), 1.0 - shade_b[i] * u.uS.z);
  let mark = u53(id, 13u);
  cand_b[o + 7u] = bitcast<u32>(size);
  cand_b[o + 11u] = bitcast<u32>(u.uC.x * size / u.uC.y);
  cand_b[o + 12u] = mark.x;
  cand_b[o + 13u] = mark.y;
  cand_b[o + 14u] = lvl_b[i];
  cand_b[o + 15u] = select(0u, 1u, home);
  var f = 0u;
  if (own) { f |= 1u; }
  if (drawn) { f |= 2u; }
  if (drawn && d > dmax * 1.0001) { f |= 4u; }
  if (home) { f |= 8u; }
  if (keepD) { f |= 16u; }
  if (keep) { f |= 32u; }
  outF_b[i] = f;
}
