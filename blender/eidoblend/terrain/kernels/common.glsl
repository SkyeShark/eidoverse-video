/* common.glsl: prefixed to every terrain kernel by core/gpu.py (design section 2.5). Its numpy twin is the set of
   primitives in core/twins.py (OFF, LEN, WISO, neighbour, pin_apply, pcg ...), kept bit-compatible.

   Frames. A texel (x, y) is the array cell [row j = y, column i = x]; row 0 is the SOUTH edge, so +y is north and
   +x is east. A cell centre is at world x = x0 + (i + 0.5) * cell, y = y0 + (j + 0.5) * cell (metres).
   Inputs are sampler2Ds read with texelFetch (no filtering); outputs are image2Ds; work groups are 16 x 16. */

/* The 8 neighbours, k = 0..7: SW, S, SE, W, E, NW, N, NE. OFF[k] = (column step, row step). The opposite of k is
   7 - k. LEN[k] is the distance in cells. WISO[k] are the isotropic 9-point weights (sides 2/3, diagonals 1/6):
   the Laplacian is sum_k WISO[k] (h_k - h) / cell^2, its centre weight -10/3 (WISO_SUM). */
const ivec2 OFF[8] = ivec2[8](ivec2(-1, -1), ivec2(0, -1), ivec2(1, -1), ivec2(-1, 0), ivec2(1, 0),
                              ivec2(-1, 1), ivec2(0, 1), ivec2(1, 1));
const float LEN[8] = float[8](1.41421356, 1.0, 1.41421356, 1.0, 1.0, 1.41421356, 1.0, 1.41421356);
const float WISO[8] = float[8](0.16666667, 0.66666667, 0.16666667, 0.66666667, 0.66666667, 0.16666667,
                               0.66666667, 0.16666667);
const float WISO_SUM = 3.33333333;
int opp(int k) { return 7 - k; }

/* Boundary modes, passed to a kernel as `//! uniform int uBound` (or fixed by a define).
   OPEN      the grid ends: a neighbour off the edge does not exist (zero flux through the edge)
   PERIODIC  the grid wraps on both axes (periodic dune tiles)
   PINNED    neighbours as OPEN; cells with a pin weight hold their pin value (pin_apply) - borders, sea, flats */
#define BOUND_OPEN 0
#define BOUND_PERIODIC 1
#define BOUND_PINNED 2

bool inside(ivec2 q, ivec2 n) { return q.x >= 0 && q.y >= 0 && q.x < n.x && q.y < n.y; }

/* periodic wrap for q in [-n, 2n): one exact integer step back onto the grid (GLSL leaves % undefined for negative
   operands, and a float floor(q / n) can land one cell off when the division rounds down) */
ivec2 wrap(ivec2 q, ivec2 n) {
  return ivec2(q.x < 0 ? q.x + n.x : (q.x >= n.x ? q.x - n.x : q.x),
               q.y < 0 ? q.y + n.y : (q.y >= n.y ? q.y - n.y : q.y));
}

/* the k-th neighbour of p under a boundary mode; false when it does not exist (off an OPEN or PINNED edge) */
bool neighbour(ivec2 p, int k, ivec2 n, int mode, out ivec2 q) {
  q = p + OFF[k];
  if (mode == BOUND_PERIODIC) {
    q = wrap(q, n);
    return true;
  }
  return inside(q, n);
}

bool on_edge(ivec2 p, ivec2 n) { return p.x == 0 || p.y == 0 || p.x == n.x - 1 || p.y == n.y - 1; }

/* A Dirichlet pin, stored as two fields: pin_w (weight 0..1) and pin_h (the value). Weight 1 holds the value,
   0 leaves the cell free; the border band ramps from 1 at a child's edge to 0 at 16 cells in. */
float pin_apply(float h, float pin_w, float pin_h) { return mix(h, pin_h, clamp(pin_w, 0.0, 1.0)); }

/* world position of a cell centre; lv = (x0, y0, cell) of the level, metres */
vec2 world_xy(ivec2 p, vec3 lv) { return lv.xy + (vec2(p) + 0.5) * lv.z; }

/* Angles are degrees in every interface and tangents inside kernels. */
float tan_deg(float d) { return tan(radians(d)); }

/* 32-bit PCG hash (PCG-RXS-M-XS; Jarzynski & Olano 2020, "Hash Functions for GPU Rendering"). pcg2/pcg3/pcg4
   chain it over more words. u01 maps a hash to [0, 1) with 24 bits, exact in float32. */
uint pcg(uint v) {
  uint state = v * 747796405u + 2891336453u;
  uint word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
  return (word >> 22u) ^ word;
}
uint pcg2(uint a, uint b) { return pcg(pcg(a) + b); }
uint pcg3(uint a, uint b, uint c) { return pcg(pcg(pcg(a) + b) + c); }
uint pcg4(uint a, uint b, uint c, uint d) { return pcg(pcg(pcg(pcg(a) + b) + c) + d); }
float u01(uint h) { return float(h >> 8u) * (1.0 / 16777216.0); }
/* a cell's hash at an iteration with a seed: what the dune and dither decisions read */
uint cell_hash(ivec2 p, int iter, int seed) { return pcg4(uint(p.x), uint(p.y), uint(iter), uint(seed)); }
