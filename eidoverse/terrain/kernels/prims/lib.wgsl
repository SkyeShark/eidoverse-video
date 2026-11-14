// prims/lib.wgsl: what the kernels of kernels/prims/ share (`//! include prims/lib`). The primitives are the GPU
// building blocks of PORT_PLAN.md section 3.4: they replace numpy code the Blender edition runs over whole levels
// (blender/eidoblend/terrain at f90c6fc), and core/prims.js drives them.

const NONE: u32 = 0xFFFFFFFFu;            // no label, no receiver, not reached
const BIG: f32 = 0x1.fffffep+127f;        // the largest float: above every height

// A list of items (not a grid) is any field read as its raw array in row-major order: item i is element i, and a
// kernel over a list takes `uCount`, the number of items (the field may hold more). A kernel that runs one
// invocation per block of items is dispatched as rows of LINE invocations: block = line_index(p); core/prims.js
// lineGroups(blocks) gives the work groups.
const LINE: i32 = 4096;
fn line_index(p: vec2<i32>) -> i32 { return p.y * LINE + p.x; }

// A float as an unsigned key in numpy's sort order: negatives below positives, -0 and +0 one key (numpy compares
// them equal), every NaN last. An exact order statistic or a stable sort of floats works on these.
fn fkey(v: f32) -> u32 {
  let b = bitcast<u32>(v);
  if ((b & 0x7FFFFFFFu) > 0x7F800000u) { return 0xFFFFFFFFu; }
  if ((b & 0x7FFFFFFFu) == 0u) { return 0x80000000u; }
  if ((b & 0x80000000u) != 0u) { return ~b; }
  return b | 0x80000000u;
}

// The k-th neighbour of p (common.wgsl's OFF order) on a grid whose columns wrap when wx != 0 and whose rows wrap
// when wy != 0: the `wrap` pair of the Blender hydrology (solvers/hydro.py _padded and neighbour_table: a corner
// past an edge that does not wrap is off the map). False off an open edge.
fn neighbour_w(p: vec2<i32>, k: i32, n: vec2<i32>, wx: i32, wy: i32, q: ptr<function, vec2<i32>>) -> bool {
  var r = p + OFF[k];
  if (wx != 0) {
    if (r.x < 0) { r.x += n.x; } else if (r.x >= n.x) { r.x -= n.x; }
  }
  if (wy != 0) {
    if (r.y < 0) { r.y += n.y; } else if (r.y >= n.y) { r.y -= n.y; }
  }
  *q = r;
  return inside(r, n);
}

// an index folded onto [0, n) by reflection without repeating the edge (np.pad mode='reflect', any distance). The
// fold is symmetric about 0, so it starts from |i|: no % of a negative number, which backends may leave undefined
// (HLSL defines it only for operands of one sign; common.wgsl's wrap() avoids it for the same reason).
fn reflect_index(i: i32, n: i32) -> i32 {
  if (n == 1) { return 0; }
  let period = 2 * (n - 1);
  var m = abs(i) % period;
  if (m >= n) { m = period - m; }
  return m;
}

// Tiles, for the relaxations (fill, breadth-first steps, labels): a work group holds its 16 x 16 cells and a halo
// of one in workgroup memory, 18 x 18 slots from the halo's south-west corner, and sweeps them several times per
// dispatch, so a front crosses a whole tile in one dispatch instead of one cell. The halo holds the dispatch's
// input values. TOFF[k] is the slot step to the k-th neighbour, in OFF's order.
const TW: i32 = 18;
const TSLOTS: i32 = 324;
const TOFF = array<i32, 8>(-19, -18, -17, -1, 1, 17, 18, 19);

fn tile_lid(p: vec2<i32>) -> vec2<i32> { return vec2<i32>(p.x & 15, p.y & 15); }
fn tile_me(lid: vec2<i32>) -> i32 { return (lid.y + 1) * TW + lid.x + 1; }

// The cell that slot t of the tile whose first cell is org stands for: itself on the grid, the cell one wrap away
// when the slot is one step past an edge that wraps, else (-1, -1): off the map, or past the grid's last row or
// column where no cell of the grid has it as a neighbour.
fn tile_cell(org: vec2<i32>, t: i32, n: vec2<i32>, wx: i32, wy: i32) -> vec2<i32> {
  var q = org + vec2<i32>(t % TW - 1, t / TW - 1);
  if (wx != 0) {
    if (q.x == -1) { q.x = n.x - 1; } else if (q.x == n.x) { q.x = 0; }
  }
  if (wy != 0) {
    if (q.y == -1) { q.y = n.y - 1; } else if (q.y == n.y) { q.y = 0; }
  }
  if (inside(q, n)) { return q; }
  return vec2<i32>(-1, -1);
}
