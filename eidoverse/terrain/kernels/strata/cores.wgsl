// The port's own kernel (no Blender counterpart): blender/eidoblend/terrain/solvers/strata.py rock_cores() and
// _box_noise() at f90c6fc, which numpy evaluates in float64 core by core over each core's box:
//     u = dx sin(ang) + dy cos(ang),   v = dx cos(ang) - dy sin(ang)          (dx, dy from the core's centre)
//     d = (|u / a|^pw + |v / b|^pw)^(1 / pw)
//     d = d / max(1 + wobble box(x, y), 0.3)      box: four plane waves sum(sin(2 pi (x cos th + y sin th) / lam
//                                                 + phase)) / 2, drawn per core by solvers/strata.js (numpy's draws)
//     out = max(out, s exp(-d^8))                 inside the core's box only, as numpy writes only its box
// Per core the table holds its box (i0, i1, j0, j1), the offsets of the box's first cell centre from the core's
// centre (doubles, rounded once), and per wave its phase at that cell (reduced modulo 2 pi in doubles) and its steps
// per column and per row, so the float32 arithmetic stays on the box's own extent. d^8 is three products (numpy's
// pow(d, 8)).
//! sampler ci r32i       per core, 4 integers: i0, i1, j0, j1
//! sampler cf rgba32f    per core, 6 texels: (dx0, dy0, sin ang, cos ang), (a, b, s, 0), then per wave (phase at the
//                        box's first cell, its step per column, per row, 0)
//! image   outC r32f
//! uniform int uN        the cores
//! uniform float uCell
//! uniform float uPw     the outline's power
//! uniform float uWob    the outline's wobble (0: none)

fn kmain(p: vec2<i32>) {
  let n = outC_size();
  if (!inside(p, n)) { return; }
  var out = 0.0;
  for (var c = 0; c < u.uN; c++) {
    let i0 = ci_b[4 * c];
    let i1 = ci_b[4 * c + 1];
    let j0 = ci_b[4 * c + 2];
    let j1 = ci_b[4 * c + 3];
    if (p.x < i0 || p.x >= i1 || p.y < j0 || p.y >= j1) { continue; }
    let g = cf_b[6 * c];
    let h = cf_b[6 * c + 1];
    let di = f32(p.x - i0) * u.uCell;
    let dj = f32(p.y - j0) * u.uCell;
    let dx = g.x + di;
    let dy = g.y + dj;
    let uu = dx * g.z + dy * g.w;
    let vv = dx * g.w - dy * g.z;
    let au = abs(uu / h.x);
    let av = abs(vv / h.y);
    let pu = select(0.0, pow(au, u.uPw), au > 0.0);
    let pv = select(0.0, pow(av, u.uPw), av > 0.0);
    let ss = pu + pv;
    var d = select(0.0, pow(ss, 1.0 / u.uPw), ss > 0.0);
    if (u.uWob > 0.0) {
      var bx = 0.0;
      for (var w = 0; w < 4; w++) {
        let k = cf_b[6 * c + 2 + w];
        bx += sin(k.x + f32(p.x - i0) * k.y + f32(p.y - j0) * k.z);
      }
      d = d / max(1.0 + u.uWob * (bx / 2.0), 0.3);
    }
    let d2 = d * d;
    let d4 = d2 * d2;
    out = max(out, h.z * exp(-(d4 * d4)));
  }
  outC_store(p, vec4<f32>(out, 0.0, 0.0, 0.0));
}
