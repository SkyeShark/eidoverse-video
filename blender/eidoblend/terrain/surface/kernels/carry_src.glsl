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

void main() {
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 n = textureSize(hT, 0);
  if (!inside(p, n)) return;
  vec4 aux = texelFetch(auxT, p, 0);
  vec4 st = texelFetch(stT, p, 0);
  if (aux.z > 0.5) {
    imageStore(outS, p, st);
    return;
  }
  float h = texelFetch(hT, p, 0).x;
  float e = texelFetch(hT, ivec2(min(p.x + 1, n.x - 1), p.y), 0).x;
  float w = texelFetch(hT, ivec2(max(p.x - 1, 0), p.y), 0).x;
  float no = texelFetch(hT, ivec2(p.x, min(p.y + 1, n.y - 1)), 0).x;
  float so = texelFetch(hT, ivec2(p.x, max(p.y - 1, 0)), 0).x;
  float tanS = length(vec2(e - w, no - so)) * (0.5 / uCell);
  float bare = smoothstep(uRockDeg.x, uRockDeg.y, degrees(atan(tanS)))
             * (1.0 - smoothstep(uCover.x, uCover.y, aux.x));
  if (bare > 0.5) {
    imageStore(outS, p, vec4(aux.y, 0.0, 1.0, 0.0));
    return;
  }
  float s[8];
  float smax = 0.0;
  for (int k = 0; k < 8; k++) {
    s[k] = 0.0;
    ivec2 q = p + OFF[k];
    if (!inside(q, n)) continue;
    if (texelFetch(stT, q, 0).z < 0.5) continue;
    s[k] = max((texelFetch(hT, q, 0).x - h) / LEN[k], 0.0);
    smax = max(smax, s[k]);
  }
  vec4 pick = vec4(aux.y, 1.0e9, 0.0, 0.0);
  if (smax > 0.0) {
    float wsum = 0.0;
    for (int k = 0; k < 8; k++) {
      float r = s[k] / smax;
      s[k] = r * r * r * r;
      wsum += s[k];
    }
    float u = u01(pcg3(uint(p.x), uint(p.y), uint(uSalt))) * wsum;
    float acc = 0.0;
    int kp = -1;
    for (int k = 0; k < 8; k++) {
      if (s[k] <= 0.0) continue;
      acc += s[k];
      kp = k;
      if (u < acc) break;
    }
    vec4 sq = texelFetch(stT, p + OFF[kp], 0);
    pick = vec4(sq.x, sq.y + LEN[kp] * uCell, 1.0, 0.0);
  }
  imageStore(outS, p, pick);
}
