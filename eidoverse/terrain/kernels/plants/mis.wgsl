// plants/mis: plants.py _hard_core (blender/eidoblend/terrain/build/plants.py at f9fba8c) as its own rounds, run on
// the GPU over the conflict graph (plants/edges): a candidate is accepted when no undecided neighbour has a lower
// rank, then its undecided neighbours are rejected; sequential inhibition in rank order is the fixed point, and the
// rounds are _hard_core's own, so its certainty rule is the same (an accepted candidate is certain when it is not
// tainted and every lower-ranked neighbour, rejected before it, was certainly rejected; a rejected one is certain
// when a certain candidate accepted in that round rejects it). Rank: the mark's 53-bit integer, then the id
// (lexsort's keys; x and y never decide between two candidates of distinct ids).
//
// uPhase: 3 the start (a candidate without a hard core is accepted and certain); per round 0 (who is new), 1 (the new
// accepted, their certainty), 2 (their undecided neighbours rejected); 4 counts the undecided (cnt[0]); 5 counts the
// candidates within the exact radius that are not certain (cnt[1]) and writes newf = accepted and within it.
//! include plants/lib
//! sampler cand r32ui    the group's candidates (16 numbers each: dist 9, r 11, mark 12-13, id 4-5)
//! sampler offs r32ui    per candidate: its first neighbour in adj
//! sampler deg r32ui     per candidate: its neighbours
//! sampler adj r32ui     the neighbours (plants/edges)
//! image   state r32ui   0 undecided, 1 accepted, 2 rejected
//! image   cert r32ui    1: certain
//! image   newf r32ui    1: accepted this round (phase 5: kept)
//! image   cnt atomic_u32
//! uniform int   uPhase
//! uniform float uTaint  a candidate farther than this from the focus is tainted
//! uniform float uExact  the group's exact radius
//! uniform int   uCount

fn rank_lt(a: u32, b: u32) -> bool {
  let oa = 16u * a;
  let ob = 16u * b;
  let ma = vec2<u32>(cand_b[oa + 12u], cand_b[oa + 13u]);
  let mb = vec2<u32>(cand_b[ob + 12u], cand_b[ob + 13u]);
  if (any(ma != mb)) { return u64_lt(ma, mb); }
  return u64_lt(vec2<u32>(cand_b[oa + 4u], cand_b[oa + 5u]), vec2<u32>(cand_b[ob + 4u], cand_b[ob + 5u]));
}

fn kmain(p: vec2<i32>) {
  let i = lin(p);
  if (i >= u.uCount) { return; }
  let ui = u32(i);
  let o = 16u * ui;
  let s0 = offs_b[i];
  let n = deg_b[i];
  if (u.uPhase == 3) {
    let hard = bitcast<f32>(cand_b[o + 11u]) > 0.0;
    state_b[i] = select(1u, 0u, hard);
    cert_b[i] = select(1u, 0u, hard);
    newf_b[i] = 0u;
    return;
  }
  if (u.uPhase == 0) {
    var nw = 0u;
    if (state_b[i] == 0u) {
      nw = 1u;
      for (var t = 0u; t < n; t++) {
        let j = adj_b[s0 + t];
        if (state_b[j] == 0u && rank_lt(j, ui)) { nw = 0u; break; }
      }
    }
    newf_b[i] = nw;
    return;
  }
  if (u.uPhase == 1) {
    if (newf_b[i] == 0u) { return; }
    state_b[i] = 1u;
    var ok = !(bitcast<f32>(cand_b[o + 9u]) > u.uTaint);
    for (var t = 0u; t < n && ok; t++) {
      let j = adj_b[s0 + t];
      if (rank_lt(j, ui) && cert_b[j] == 0u) { ok = false; }
    }
    cert_b[i] = select(0u, 1u, ok);
    return;
  }
  if (u.uPhase == 2) {
    if (state_b[i] != 0u) { return; }
    var rej = false;
    var sure = false;
    for (var t = 0u; t < n; t++) {
      let j = adj_b[s0 + t];
      if (newf_b[j] != 0u) {
        rej = true;
        if (cert_b[j] != 0u) { sure = true; }
      }
    }
    if (rej) {
      state_b[i] = 2u;
      cert_b[i] = select(0u, 1u, sure);
    }
    return;
  }
  if (u.uPhase == 4) {
    if (state_b[i] == 0u) { atomicAdd(&cnt_b[0], 1u); }
    return;
  }
  if (u.uPhase == 5) {
    let inside = bitcast<f32>(cand_b[o + 9u]) <= u.uExact;
    if (inside && cert_b[i] == 0u) { atomicAdd(&cnt_b[1], 1u); }
    newf_b[i] = select(0u, 1u, inside && state_b[i] == 1u);
  }
}
