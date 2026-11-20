// Port of blender/eidoblend/terrain/solvers/karst.py evaluate() at f90c6fc, from "level = plain['level']" to the cell
// means (_Grid.down), as a kernel over the level's cells, each reading its ss x ss subsamples:
//     rock_h   = level + rock
//     talus_ss = max(level + scree - max(rock_h, surface), 0) * (scree > 0)
//     h_ss     = max(surface, rock_h) + talus_ss
//     bed_ss   = min(h_ss, max(rock_h, level - alluvium_m))
// then the means of h, bed, talus, the plain's level, the water level and in_channel, the share of subsamples whose
// surface stands at the plain (surface >= level - 0.25: the dry test a context level's own cockpits take), and the
// owner at the cell's centre subsample (tower_id: owner[mid::ss, mid::ss]). numpy's float64 is float32 here.

//! sampler plain rgba32f      per subsample: level, surface, water level, in_channel
//! sampler rs rg32f           per subsample: rock, scree
//! sampler own r32i           per subsample: the owner
//! image   outA rgba32f       per cell: h, bed, talus, plain
//! image   outB rgba32f       per cell: water level, in_channel, the dry share, 0
//! image   outO r32i          per cell: tower_id
//! uniform int uSS
//! uniform float uAlluvium
fn kmain(p: vec2<i32>) {
  let n = outA_size();
  if (!inside(p, n)) { return; }
  let ss = u.uSS;
  var sh = 0.0;
  var sb = 0.0;
  var st = 0.0;
  var sl = 0.0;
  var sw = 0.0;
  var sc = 0.0;
  var sd = 0.0;
  for (var dj = 0; dj < ss; dj++) {
    for (var di = 0; di < ss; di++) {
      let q = p * ss + vec2<i32>(di, dj);
      let pl = plain_at(q);
      let r = rs_at(q).xy;
      let level = pl.x;
      let surface = pl.y;
      let rock_h = level + r.x;
      var talus = max(level + r.y - max(rock_h, surface), 0.0);
      if (!(r.y > 0.0)) { talus = 0.0; }
      let h = max(surface, rock_h) + talus;
      let bed = min(h, max(rock_h, level - u.uAlluvium));
      sh += h;
      sb += bed;
      st += talus;
      sl += level;
      sw += pl.z;
      sc += pl.w;
      if (surface >= level - 0.25) { sd += 1.0; }
    }
  }
  let k = f32(ss * ss);
  outA_store(p, vec4<f32>(sh / k, sb / k, st / k, sl / k));
  outB_store(p, vec4<f32>(sw / k, sc / k, sd / k, 0.0));
  let mid = ss / 2;
  outO_store(p, own_at(p * ss + vec2<i32>(mid, mid)));
}
