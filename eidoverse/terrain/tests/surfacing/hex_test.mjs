// Hex tiling's grid against Blender's (SURFACING_DESIGN.md 3.3; build/surfacing.js hexGrid against surfacing.py
// hex_grid_group): the same 40 m plane, top-down, its object coordinates into the grid (1 / 10 m, seed 7.1, turned),
// each slot's barycentric weight, offset, turn and turned position as an unlit emission, against EEVEE's render of the
// Blender group (tests/surfacing/blender_probe_hex.py). Within EEVEE's half-float film (2^-11 of a value under 1;
// 2^-11 x 8 for the turned positions, metres up to 8), on every pixel but those a lattice line or a hexagon's border
// crosses (a floor() of a value within a float step of an integer), counted.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surfacing/hex_test.mjs [<dir>]
//     (a GPU job; <dir>: the probe's output, default tests/out/surfacing/probe_hex)

import * as M from './_material.mjs';
import * as Sf from '../../build/surfacing.js';
import { readNpySync } from '../../core/io.js';

const dir = Deno.args[0] ?? M.out('probe_hex');
const T = new M.C.Checks('surfacing: the hex grid against Blender\'s');
if (!M.W.exists(`${dir}/hex.json`)) {
    T.ok('the Blender probe is there', false, `run blender_probe_hex.py into ${dir}`);
    Deno.exit(M.finish(T, 'hex_test'));
}
const info = JSON.parse(Deno.readTextFileSync(`${dir}/hex.json`));
const G = await M.gpu();
const { THREE, TSL } = G;
await Sf.tslModule({ TSL });
const side = info.side_m, n = info.px;
const geo = new THREE.PlaneGeometry(side, side);
geo.rotateX(-Math.PI / 2);
geo.translate(side / 2, 0, -side / 2);
const p = TSL.positionLocal;
const pos = TSL.vec3(p.x, p.z.negate(), p.y);
const grid = Sf.hexGrid(pos, info.inverse_size, info.seed, true);
const pick = (sock, ch) => {
    const c = Number(sock.slice(-1));
    const k = sock.slice(0, -1);
    const v = grid[c][k];
    if (ch === 'None') return v;
    return [v.x, v.y, v.z][Number(ch)];
};
const FILM = 2 ** -11;
const res = {};
let allOk = true;
for (const [name, outs] of Object.entries(info.passes)) {
    const mat = new THREE.MeshBasicNodeMaterial();
    const ch = outs.map(([s, c]) => pick(s, c));
    mat.colorNode = TSL.vec4(ch[0], ch[1], ch[2], 1.0);
    mat.toneMapped = false;
    const mesh = new THREE.Mesh(geo, mat);
    const { px } = await M.renderTop(G, mesh, { cx: side / 2, cy: side / 2, side, n, top: 10.0 });
    const b = readNpySync(`${dir}/hex_${name}.npy`);
    let bad = 0, mx = 0;
    for (let j = 0; j < n; j++) {
        for (let i = 0; i < n; i++) {
            for (let c = 0; c < 3; c++) {
                const want = b.data[(j * n + i) * 4 + c];                    // Blender's row 0: the bottom (south)
                const got = px[((n - 1 - j) * n + i) * 4 + c];               // ours: row 0 north
                const tol = Math.max(FILM, Math.abs(want) * FILM * 1.01) * 2;
                const e = Math.abs(got - want);
                if (e > tol) bad++;
                else mx = Math.max(mx, e);
            }
        }
    }
    res[name] = { bad, of: 3 * n * n, max_within: mx };
    const ok = bad <= 0.003 * 3 * n * n;
    if (!ok) allOk = false;
    console.log(`[hex] ${name} (${outs.map((o) => o.join('.')).join(', ')}): ${bad} of ${3 * n * n} past the film's step, elsewhere max ${M.C.sci(mx, 2)}`);
    mat.dispose();
}
T.ok('hexGrid equals Blender\'s eido_hex_grid: weights, offsets, turns and turned positions per slot', allOk,
    Object.entries(res).map(([k, v]) => `${k}: ${v.bad} of ${v.of} past the film's step`).join('; '));
G.renderer.dispose();
Deno.exit(M.finish(T, 'hex_test', { passes: res, blender: info.blender }));
