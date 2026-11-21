// The material's check 2 (SURFACING_DESIGN.md 5.4 package 2; PORT_PLAN.md 8.2 row P17: "sectors on the canyon's
// brink wall and a 45-degree wall without smear"): blender/tests/terrain/surfacing/check_sectors.py's views on the
// port. Steep faces read in the fixed sector frames, on real walls at their world positions: the judge's brink_down
// (the canyon's right-hand wall, diagonal to the axes) and wall_L4 (about 250 m of the steepest wall on the finest
// hero level, seen from 300 m along its mean facing), each with the scans and with a colour grid in place of every
// box layer's scan (check_sectors.grid_images: cells x cells squares a tile side, distinct colours, dark lines, a pale
// bar along each cell's top; a flat normal): grid cells must read square, with no streaks and no seam where the sector
// slots meet; and the field normal's slope as an emission (what the layer weights read). For the eye: the renders are
// written, 2x crops beside them, and the cameras recorded. Lit by a sun 70 degrees left of the view, 37.7 degrees up,
// and a sky fill (the views.mjs renders carry the review's sky).
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/surfacing/sectors_test.mjs
//         [--case canyon] [--views brink_down,wall_L4] [--cells 8]
//     (a GPU job, behind $EIDO_GPU_WRAP)
//
// Writes tests/out/surfacing/sectors/<case>_<view>_<scan|grid|slope>.png and sectors_test.json.

import * as M from './_material.mjs';
import * as Sf from '../../build/surfacing.js';

const A = M.argsOf();
const name = A.opt('--case', 'canyon');
const views = A.list('--views', ['brink_down', 'wall_L4']);
const cells = Number(A.opt('--cells', '8'));
const T = new M.C.Checks(`surfacing: sector frames on real walls (check 2), ${name}`);
const G = await M.gpu();
const { THREE, TSL, renderer } = G;
await Sf.tslModule({ TSL });
const outDir = M.out('sectors');
const W = 960, H = 540;

async function png(path, px, w, h, exposure = 1.0) {
    const Io = await import('../../core/io.js');
    const s = new Uint32Array(w * h * 4);
    const enc = (v) => (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055);
    for (let q = 0; q < w * h; q++) {
        for (let c = 0; c < 3; c++) {
            const v = exposure === null ? px[4 * q + c] : enc((px[4 * q + c] * exposure) / (1 + px[4 * q + c] * exposure));
            s[4 * q + c] = Math.round(255 * Math.min(Math.max(v, 0), 1));
        }
        s[4 * q + 3] = 255;
    }
    const f = G.R.field(h, w * 4, 1, s, 'u32');
    await Io.writePng(path, { field: f, width: w, height: h, channels: 4, bitDepth: 8 });
    f.destroy();
}

// check_sectors.grid_images, as layers of the scan arrays: the box layers' scans become the grid, their normal flat
function gridScans(scans, pal) {
    const n = scans.size, per = n * n * 4;
    const alb = new Uint8Array(scans.albedo.image.data), nra = new Uint8Array(scans.nrao.image.data);
    const c = Math.max(1, cells);
    const rng = (() => { let s = 5; return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296); })();
    const cols = Array.from({ length: c * c }, () => [0.25 + 0.65 * rng(), 0.25 + 0.65 * rng(), 0.25 + 0.65 * rng()]);
    const w = Math.max(3, Math.floor(n / (c * 40))), cp = Math.floor(n / c);
    const enc = (v) => Math.round(255 * (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055));
    const box = new Set(pal.layers.filter((L) => L.projection === 'box').map((L) => scans.sets[pal.layers.indexOf(L)].name));
    for (const set of box) {
        const k = scans.layerOf[set];
        for (let jj = 0; jj < n; jj++) {
            for (let ii = 0; ii < n; ii++) {
                const o = k * per + (jj * n + ii) * 4;
                let rgb = cols[Math.floor(jj * c / n) * c + Math.floor(ii * c / n)];
                if ((jj % cp) > cp - 4 * w) rgb = [0.95, 0.95, 0.95];      // the pale bar along each cell's top
                if ((ii % cp) < w || (jj % cp) < w) rgb = [0.08, 0.08, 0.08];
                // the grid's colours are linear in Blender's image (sRGB colourspace): stored here sRGB-encoded
                alb[o] = enc(rgb[0]); alb[o + 1] = enc(rgb[1]); alb[o + 2] = enc(rgb[2]); alb[o + 3] = 128;
                nra[o] = 128; nra[o + 1] = 128; nra[o + 2] = 204; nra[o + 3] = 255;
            }
        }
    }
    const mk = (data, srgb) => {
        const t = new THREE.DataArrayTexture(data, n, n, scans.albedo.image.depth);
        t.format = THREE.RGBAFormat;
        t.type = THREE.UnsignedByteType;
        t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        t.wrapS = t.wrapT = THREE.RepeatWrapping;
        t.magFilter = THREE.LinearFilter;
        t.minFilter = THREE.LinearMipmapLinearFilter;
        t.generateMipmaps = true;
        t.anisotropy = 16;
        t.needsUpdate = true;
        return t;
    };
    return { ...scans, albedo: mk(alb, true), nrao: mk(nra, false) };
}

const got = await M.caseData(name, G, { palette: true });
if (!got) {
    T.ok(`${name}: the case is there`, false, 'see the skip line');
    Deno.exit(M.finish(T, 'sectors_test'));
}
const { t, sd } = got;
const judge = JSON.parse(Deno.readTextFileSync(`${M.W.blenderTests()}/surfacing_judge/views.json`));
const plan = judge[{ lauterbrunnen: 'real_place', meteor_crater: 'impact_crater', toroweap: 'canyon' }[name] ?? name];
const main = t.levels.find((l) => l.role === 'main') ?? t.levels[0];
const cx = main.x0 + main.side / 2, cy = main.y0 + main.side / 2;
const rec = { case: name, views: {} };
// the cameras: a judge view, or wall_L4 (the finest level's 250 m window with the most ground over 50 degrees, seen
// from 300 m along its mean facing)
async function camOf(v) {
    if (v !== 'wall_L4') {
        const jv = plan.views.find((x) => x.name === v);
        const ex = jv.cam[0] + cx, ey = jv.cam[1] + cy;
        const ez = jv.cam_z[0] === 'ground' ? t.ring.heightAt(ex, ey) + Number(jv.cam_z[1]) : Number(jv.cam_z[1]);
        return { eye: [ex, ey, ez], target: [jv.aim[0] + cx, jv.aim[1] + cy, jv.aim[2]], lens: Number(jv.lens) };
    }
    const k = t.levels.length - 1, lv = t.levels[k];
    const tm = await Sf.terrainMap(sd, null, { THREE, TSL, R: G.R });
    void tm;
    const maps = await sd.maps(k);
    const n = Math.round(Math.sqrt(maps.slope.length)), cell = lv.side / n;
    const win = Math.max(8, Math.round(250 / cell));
    let best = null;
    for (let j = 0; j + win <= n; j += Math.max(1, win >> 2)) {
        for (let i = 0; i + win <= n; i += Math.max(1, win >> 2)) {
            let steep = 0, ax = 0, ay = 0;
            for (let q = j; q < j + win; q += 4) for (let p = i; p < i + win; p += 4) {
                const s = maps.slope[q * n + p];
                if (s > 50) {
                    steep++;
                    const a = (maps.aspect[q * n + p] * Math.PI) / 180;
                    ax += Math.sin(a); ay += Math.cos(a);
                }
            }
            if (!best || steep > best.steep) best = { steep, i, j, ax, ay };
        }
    }
    const mx = lv.x0 + (best.i + win / 2) * cell, my = lv.y0 + (best.j + win / 2) * cell;
    const l = Math.hypot(best.ax, best.ay) || 1;
    const fx = best.ax / l, fy = best.ay / l;               // the mean facing (downslope, horizontal)
    const mz = t.ring.heightAt(mx, my);
    const ex = mx + 300 * fx, ey = my + 300 * fy;
    return { eye: [ex, ey, Math.max(t.ring.heightAt(ex, ey) + 2, mz)], target: [mx, my, mz], lens: 35.0 };
}
const scans = await Sf.scanArrays(sd.palette, { THREE, R: G.R, log: null });
const grid = gridScans(scans, sd.palette);
const variants = [['scan', null], ['grid', grid]];
const mats = {};
for (const [k, sc] of variants) {
    mats[k] = await Sf.surfaceMaterial(sd.palette, { data: sd, THREE, R: G.R, TSL, recipe: t.recipe, scans: sc ?? undefined, log: null,
        constants: Sf.terrainConstants(t) });
}
const tm = await Sf.terrainMap(sd, null, { THREE, TSL, R: G.R });
const slopeMat = new THREE.MeshBasicNodeMaterial();
slopeMat.colorNode = TSL.vec4(TSL.vec3(tm.slope.div(90.0)), 1.0);
for (const v of views) {
    const c = await camOf(v);
    const d = [c.target[0] - c.eye[0], c.target[1] - c.eye[1]];
    const hd = Math.atan2(d[1], d[0]) + (70 * Math.PI) / 180, el = (37.7 * Math.PI) / 180;
    const sunDir = [Math.cos(hd) * Math.cos(el), Math.sin(el), -Math.sin(hd) * Math.cos(el)];
    const r = { camera: c, seconds: {} };
    for (const [k] of [...variants, ['slope']]) {
        const mat = k === 'slope' ? slopeMat : mats[k];
        t.mesh.material = [mat, mat];
        const scene = new THREE.Scene();
        scene.add(t.mesh);
        if (k !== 'slope') {
            const sun = new THREE.DirectionalLight(0xffffff, 3.2);
            sun.position.set(c.target[0] + 1000 * sunDir[0], c.target[2] + 1000 * sunDir[1], -c.target[1] + 1000 * sunDir[2]);
            sun.target.position.set(c.target[0], c.target[2], -c.target[1]);
            scene.add(sun, sun.target, new THREE.HemisphereLight(0xb8cff0, 0x40342a, 0.9));
        }
        const t0 = performance.now();
        const { px } = await M.renderPersp(G, scene, { eye: c.eye, target: c.target, lens: c.lens, w: W, h: H });
        r.seconds[k] = +((performance.now() - t0) / 1000).toFixed(1);
        await png(`${outDir}/${name}_${v}_${k}.png`, px, W, H, k === 'slope' ? null : 1.0);
        scene.remove(t.mesh);
    }
    rec.views[v] = r;
    console.log(`[sectors] ${name} ${v}: ${JSON.stringify(r)}`);
}
T.ok(`${name}: the sector views render with the scans, the grid and the slope (look at them: ${outDir})`,
    Object.keys(rec.views).length === views.length, Object.keys(rec.views).join(', '));
G.renderer.dispose();
Deno.exit(M.finish(T, `sectors_test_${name}`, rec));
