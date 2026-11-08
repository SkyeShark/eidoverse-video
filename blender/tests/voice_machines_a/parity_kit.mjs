// The era kit's own helpers (buildMips, rrPoints, roundedRectShape, roundedPolyline, speckle, keycap, rbox,
// loftRings, planarUVFacing) run unchanged in Deno, for the Python port's parity test:
//   deno run --no-config --no-lock --node-modules-dir=none --cached-only -A \
//       blender/tests/voice_machines_a/parity_kit.mjs <node_modules/three/build dir> <out_dir>
// The helpers are closures inside eraKit(THREE), so their source is cut out of c64.js's kit and evaluated with the
// names they close over. Writes <out_dir>/parity_kit_js.json and <out_dir>/parity_kit_speckle_js.png.
import { createCanvas } from 'npm:@napi-rs/canvas@0.1.69';

const [threeDir, out] = Deno.args;
if (!threeDir || !out) throw new Error('usage: parity_kit.mjs <node_modules/three/build dir> <out_dir>');
const THREE = await import(new URL('three.module.js', 'file:///' + threeDir.replace(/\\/g, '/').replace(/\/?$/, '/')).href);
// the RoundedBoxGeometry addon imports the bare 'three': point it at the same build
const addon = Deno.readTextFileSync(new URL('../examples/jsm/geometries/RoundedBoxGeometry.js',
    'file:///' + threeDir.replace(/\\/g, '/').replace(/\/?$/, '/')));
Deno.mkdirSync(out, { recursive: true });
const shim = `${out}/_rounded_box_geometry.mjs`;
Deno.writeTextFileSync(shim, addon.replace(/from 'three'/, `from '${new URL('three.module.js', 'file:///' + threeDir.replace(/\\/g, '/').replace(/\/?$/, '/')).href}'`));
const { RoundedBoxGeometry } = await import('file:///' + shim.replace(/\\/g, '/'));

const here = new URL('.', import.meta.url);
const src = Deno.readTextFileSync(new URL('../../../eidoverse/props/voice_machines/c64.js', here));
const kit = src.slice(src.indexOf('async function eraKit'));
function cut(text, head) {                       // a definition's source, by brace matching from its header
    const a = text.indexOf(head);
    if (a < 0) throw new Error('missing ' + head);
    let i = text.indexOf('{', text.indexOf('=>', a) > 0 && head.startsWith('const') ? text.indexOf('=>', a) : a), depth = 0;
    for (; i < text.length; i++) {
        const c = text[i];
        if (c === '{') depth++;
        else if (c === '}') { depth--; if (depth === 0) return text.slice(a, i + 1); }
    }
    throw new Error('unbalanced ' + head);
}
const names = ['const rng = (seed)', 'function buildMips(', 'const rbox = (', 'const roundedRectShape = (',
    'const planarUV = (', 'const rrPoints = (', 'const loftRings = (', 'const keycap = (', 'const roundedPolyline = (',
    'const planarUVFacing = (', 'const speckle = ('];
const body = names.map((n) => cut(kit, n)).join(';\n');
const K = new Function('THREE', 'RoundedBoxGeometry',
    `${body};\nreturn { rng, buildMips, rbox, roundedRectShape, planarUV, rrPoints, loftRings, keycap, roundedPolyline, planarUVFacing, speckle };`)(THREE, RoundedBoxGeometry);

const res = {};
// buildMips on a 37 x 23 image drawn with the kit's rng(5): 40 % fully transparent texels
{
    const r = K.rng(5), w = 37, h = 23, data = new Uint8Array(w * h * 4);
    for (let i = 0; i < w * h; i++) {
        const empty = r() < 0.4;
        data[i * 4] = Math.floor(r() * 256); data[i * 4 + 1] = Math.floor(r() * 256); data[i * 4 + 2] = Math.floor(r() * 256);
        data[i * 4 + 3] = empty ? 0 : Math.floor(r() * 256);
    }
    res.mips_input = Array.from(data);
    res.mips_plain = K.buildMips(data, w, h, false).map((l) => ({ w: l.width, h: l.height, data: Array.from(l.data) }));
    res.mips_weighted = K.buildMips(data, w, h, true).map((l) => ({ w: l.width, h: l.height, data: Array.from(l.data) }));
}
res.rr_points = [[0.02, 0.01, 0.003, 2, 0, 0], [0.08, 0.05, 0.012, 6, 0.01, -0.02], [0.05, 0.05, 0.4, 4, 0, 0]]
    .map((a) => ({ args: a, pts: K.rrPoints(...a) }));
res.rounded_rect_shape = [[0.1, 0.06, 0.012, 0.01, -0.02, false], [0.04, 0.03, 0.006, 0, 0, true]]
    .map((a) => ({ args: a, pts: K.roundedRectShape(...a).getPoints(12).map((p) => [p.x, p.y]) }));
{
    const pts = [[0, 0, 0], [0.12, 0.0, 0.02], [0.14, 0.09, 0.02], [0.02, 0.1, -0.03], [0.03, 0.2, 0.0]];
    const path = K.roundedPolyline(pts, 0.03);
    res.rounded_polyline = { pts, radius: 0.03, points: path.getPoints(12).map((p) => [p.x, p.y, p.z]), length: path.getLength(),
                             n_curves: path.curves.length };
}
// keycap and rbox bounds (three axes: y up, z toward the viewer)
const bounds = (g) => { g.computeBoundingBox(); const b = g.boundingBox; return [b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z]; };
res.keycap = { args: [0.018, 0.018, 0.0125, 0.013, 0.009, 0.0012], bounds: bounds(K.keycap(0.018, 0.018, 0.0125, 0.013, 0.009, 0.0012)) };
// the top face's half width at its top: the taper (largest |x| among vertices above 99 % of the height)
{
    const g = K.keycap(0.018, 0.018, 0.0125, 0.013, 0.009, 0.0012), p = g.attributes.position;
    let top = 0;
    for (let i = 0; i < p.count; i++) if (p.getY(i) > 0.009 / 2 * 0.98) top = Math.max(top, Math.abs(p.getX(i)));
    res.keycap.top_half_width = top;
}
res.rbox = { args: [0.3, 0.07, 0.18, 0.012, 3], bounds: bounds(K.rbox(0.3, 0.07, 0.18, 0.012, 3)) };
{   // loftRings through rrPoints rings: a rounded-square knob, 5 rings
    const rings = [];
    const prof = [[0.0, 0.020], [0.004, 0.021], [0.012, 0.020], [0.016, 0.017], [0.018, 0.012]];
    for (const [y, s] of prof) rings.push(K.rrPoints(s, s, s * 0.3, 4).map(([x, z]) => [x, y, z]));
    const g = K.loftRings(rings);
    const uv = g.attributes.uv;
    let umax = 0, vmax = 0;
    for (let i = 0; i < uv.count; i++) { umax = Math.max(umax, uv.getX(i)); vmax = Math.max(vmax, uv.getY(i)); }
    res.loft = { rings, n_vertices: g.attributes.position.count, n_triangles: g.index.count / 3, umax, vmax, bounds: bounds(g) };
}
{   // planarUVFacing on a bevelled box: the fraction of triangles turned to the front that print
    const g = K.rbox(0.3, 0.07, 0.18, 0.012, 3).toNonIndexed();
    K.planarUVFacing(g, -0.15, -0.035, 0.15, 0.035, 'xy', [0, 0, 1], 0.35);
    const uv = g.attributes.uv;
    let printed = 0, tris = uv.count / 3;
    for (let i = 0; i < uv.count; i += 3) if (uv.getX(i) !== -0.25) printed++;
    res.planar_uv_facing = { printed_fraction: printed / tris };
}
// speckle on a white 200 x 120 canvas
{
    const cv = createCanvas(200, 120), ctx = cv.getContext('2d');
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, 200, 120);
    K.speckle(ctx, 200, 120, 300, 11, ['#3e372d', '#c9b27a', '#000000'], 2.5, 0.6);
    Deno.writeFileSync(`${out}/parity_kit_speckle_js.png`, await cv.encode('png'));
    res.speckle = { w: 200, h: 120, n: 300, seed: 11, colors: ['#3e372d', '#c9b27a', '#000000'], r_max: 2.5, alpha: 0.6 };
}
Deno.writeTextFileSync(`${out}/parity_kit_js.json`, JSON.stringify(res));
console.log('parity_kit: wrote', `${out}/parity_kit_js.json`);
