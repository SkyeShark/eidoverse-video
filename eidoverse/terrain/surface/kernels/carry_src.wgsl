// Port of blender/eidoblend/terrain/surface/kernels/carry_src.glsl at d67f19e.
//
// Transcribed statement for statement from the GLSL (PORT_PLAN.md 4.2, 3.5); the `//!` header is the GLSL's,
// unchanged. The changes are WGSL's: texelFetch is <name>_at(q), imageStore is outS_store, textureSize is
// hT_size(), the uniforms are u.<name>, `float s[8]` is an array<f32, 8>, and uint() is u32().
/* carry_src: one Jacobi pass of debris provenance (SURFACING_DESIGN.md 2.3, step 10): which bare rock a cell's
   loose material came from, and how far down the fall path it lies. Twin: surface/twins.py carry_src.

   A source is bare rock: slope over the rock angle (a smoothstep over uRockDeg, past its half), under no loose
   cover. A source holds its own stratigraphic height and distance 0. Every other cell takes the state of one of its
   upslope neighbours that is a source or carries one, with the step's length added; a cell with no such neighbour
   carries none (valid 0). The neighbour is drawn by the cell's own hash with weights (slope / steepest)^4: the
   steepest wins most often, but on a slope between two grid directions the paths alternate between them and follow
   the true fall line, instead of running straight along the eight grid directions (the straight-edged parallelograms
   of a steepest-neighbour trace). The draw is fixed per cell, so the passes converge. A pinned cell (the margin of a
   child level, holding its parent's state) keeps what it has. Passes repeat until nothing changes, at most
   reach / cell of them: an upslope chain is strictly uphill, so the order of the passes cannot loop. */
//! sampler hT              x: h, metres (less the level's reference height)
//! sampler auxT            x: loose cover (m), y: the cell's own stratigraphic height zs (less the reference), z: pinned
//! sampler stT             x: the source's zs (less the reference), y: metres down the fall path, z: valid (0 | 1)
//! image   outS rgba32f
//! uniform float uCell     metres
//! uniform vec2 uRockDeg   bare rock: a smoothstep of the slope, degrees
//! uniform vec2 uCover     loose cover that hides the rock: a smoothstep, metres
//! uniform int uSalt       the draw's salt (the level)

fn kmain(p: vec2<i32>) {
  let n = hT_size();
  if (!inside(p, n)) { return; }
  let aux = auxT_at(p);
  let st = stT_at(p);
  if (aux.z > 0.5) {
    outS_store(p, st);
    return;
  }
  let h = hT_at(p).x;
  let e = hT_at(vec2<i32>(min(p.x + 1, n.x - 1), p.y)).x;
  let w = hT_at(vec2<i32>(max(p.x - 1, 0), p.y)).x;
  let no = hT_at(vec2<i32>(p.x, min(p.y + 1, n.y - 1))).x;
  let so = hT_at(vec2<i32>(p.x, max(p.y - 1, 0))).x;
  let tanS = length(vec2<f32>(e - w, no - so)) * (0.5 / u.uCell);
  let bare = smoothstep(u.uRockDeg.x, u.uRockDeg.y, degrees(atan(tanS)))
           * (1.0 - smoothstep(u.uCover.x, u.uCover.y, aux.x));
  if (bare > 0.5) {
    outS_store(p, vec4<f32>(aux.y, 0.0, 1.0, 0.0));
    return;
  }
  var s: array<f32, 8>;
  var smax = 0.0;
  for (var k = 0; k < 8; k++) {
    s[k] = 0.0;
    let q = p + OFF[k];
    if (!inside(q, n)) { continue; }
    if (stT_at(q).z < 0.5) { continue; }
    s[k] = max((hT_at(q).x - h) / LEN[k], 0.0);
    smax = max(smax, s[k]);
  }
  var pick = vec4<f32>(aux.y, 1.0e9, 0.0, 0.0);
  if (smax > 0.0) {
    var wsum = 0.0;
    for (var k = 0; k < 8; k++) {
      let r = s[k] / smax;
      s[k] = r * r * r * r;
      wsum += s[k];
    }
    let uu = u01(pcg3(u32(p.x), u32(p.y), u32(u.uSalt))) * wsum;
    var acc = 0.0;
    var kp = -1;
    for (var k = 0; k < 8; k++) {
      if (s[k] <= 0.0) { continue; }
      acc += s[k];
      kp = k;
      if (uu < acc) { break; }
    }
    let sq = stT_at(p + OFF[kp]);
    pick = vec4<f32>(sq.x, sq.y + LEN[kp] * u.uCell, 1.0, 0.0);
  }
  outS_store(p, pick);
}
