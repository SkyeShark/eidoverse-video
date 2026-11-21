// plants/bit: 1 where an item lies in [uLo, uHi) and its flags hold every bit of uMask and none of uNot, else 0: a
// numpy boolean mask of the planner's flags, for core/prims.js nonzero (the compaction of {k: v[keep]}; a range: one
// species' part of its priority group). With uMaxCell > 0, also off a level coarser than it (plants.py _thin's
// max_cell_m: the flags are then the candidates' finest levels, and lvt the level table).
//! include plants/lib
//! sampler flags r32ui
//! sampler lvt r32f      the level table (plants/locate), read with uMaxCell > 0
//! image   outB r32ui
//! uniform int   uMask
//! uniform int   uNot
//! uniform int   uLo
//! uniform int   uHi
//! uniform float uMaxCell
//! uniform int   uCount

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let f = flags_b[i];
  if (u.uMaxCell > 0.0) {
    outB_b[i] = select(0u, 1u, lvt_b[12u * f + 9u] <= u.uMaxCell * (1.0 + 1e-9));
    return;
  }
  let m = bitcast<u32>(u.uMask);
  outB_b[i] = select(0u, 1u, i >= u.uLo && i < u.uHi && (f & m) == m && (f & bitcast<u32>(u.uNot)) == 0u);
}
