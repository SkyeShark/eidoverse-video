// Port of blender/eidoblend/terrain/solvers/aeolian.py at f90c6fc: AVALANCHE_SRC, the avalanche kernel the Blender
// edition keeps as source text in that module (G.kernel(source=AVALANCHE_SRC, name='dune_avalanche')). Here it is a
// kernel file of the same name (PORT_PLAN.md 3.3), so the dispatch log names it as Blender's does.
//
// Transcribed statement for statement (PORT_PLAN.md 4.2); the //! header is Blender's, unchanged. GLSL's ?: picks one
// array element lazily (k < 8 ? OFF[k] : KOFF[k - 8]): here an if / else, since select() would read KOFF[k - 8] for
// k < 8 too. pin_apply is common.wgsl's (the twin's h (1 - a) + pin_h a).
//
/* dune_avalanche: sand slides where it is steeper than its angle of repose (design 4.6, step 4), and
   can creep a little everywhere (reptation: grains the saltating ones kick down the slope).
   For each neighbour pair, the higher cell's surface stands above the lower's by more than tan(repose) x the
   distance: a share uRate of that excess moves down; and a share uCreep x WISO[k] of the whole difference creeps down
   (the isotropic 9-point weights, so the creep is a diffusion with no grid direction). The neighbours are the 8 of
   common.glsl and the 8 knight's moves (distance sqrt 5): with 8 directions alone a plane facing 22.5 degrees off
   them stands 8 % steeper than one facing along them, and slip faces lock to the grid's eight directions; with 16
   the most is 2.7 %. Each pair's flow never takes more than a sixteenth of the upper cell's sand (so a cell can never
   give more than it has, and bare rock never moves). Both cells of a pair compute the same flow from the same texels,
   so the exchange is symmetric and sand is conserved exactly. Pins (pin_w, pin_sand) then hold the border band of a
   child level to its parent's sand. Twin: solvers/aeolian.py, twin 'dune_avalanche'. */
//! sampler st                bed (r) and sand thickness (g), metres
//! sampler pins              pin weight (r) 0..1 and pinned sand thickness (g), metres
//! image   outSt rg32f       bed and sand after one pass
//! uniform float uTanRepose  tan of the angle of repose
//! uniform float uRate       share of the excess moved per pass
//! uniform float uCreep      the creep's share of the height difference per pass (0: none)
//! uniform float uCell       metres
//! uniform int uBound        BOUND_OPEN / BOUND_PERIODIC / BOUND_PINNED

/* the 8 knight's moves, opposite = 7 - k as in common.glsl's OFF */
const KOFF = array<vec2<i32>, 8>(vec2<i32>(-2, -1), vec2<i32>(-1, -2), vec2<i32>(1, -2), vec2<i32>(2, -1),
                                 vec2<i32>(-2, 1), vec2<i32>(-1, 2), vec2<i32>(1, 2), vec2<i32>(2, 1));
const KLEN: f32 = 2.23606798;

fn kmain(p: vec2<i32>) {
  let n = st_size();
  if (!inside(p, n)) { return; }
  let s = st_at(p);
  let hc = s.r + s.g;
  var net = 0.0;
  for (var k = 0; k < 16; k++) {
    var q: vec2<i32>;
    if (k < 8) { q = p + OFF[k]; } else { q = p + KOFF[k - 8]; }
    if (u.uBound == BOUND_PERIODIC) {
      q = wrap(q, n);
    } else if (!inside(q, n)) {
      continue;
    }
    let sq = st_at(q);
    let hq = sq.r + sq.g;
    var len = KLEN;
    if (k < 8) { len = LEN[k]; }
    let lim = u.uTanRepose * len * u.uCell;
    let rate = u.uRate / len;                    /* the flow follows the pair's SLOPE excess, so a face drains at
                                                    the same rate whichever stencil direction it faces */
    var cw = 0.0;
    if (k < 8) { cw = u.uCreep * WISO[k]; }
    let down = rate * max(hc - hq - lim, 0.0) + cw * max(hc - hq, 0.0);
    let up = rate * max(hq - hc - lim, 0.0) + cw * max(hq - hc, 0.0);
    net += min(up, sq.g * 0.0625) - min(down, s.g * 0.0625);
  }
  let pn = pins_at(p);
  let sand = pin_apply(s.g + net, pn.r, pn.g);
  outSt_store(p, vec4<f32>(s.r, max(sand, 0.0), 0.0, 0.0));
}
