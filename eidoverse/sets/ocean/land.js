// ocean/land.js — the shore of verse 3, in the DESIGN frame (her mark at the origin, the open sea
// toward the moon at -z/+x, the cove and the house's spit to the -x/-z).
//   · a small rise (her mark) at the tip of a low headland,
//   · a cove curling round to a sand spit where the house stands,
//   · beach -> dunes -> low dark hills inland.
// Heights are analytic from a signed distance to the coast polyline (+ water, - land), so the sea's
// shore attribute, the land mesh and the dune-grass placement all agree.
//
// makeCoast() -> { sdist(x,z), height(x,z), markY, house:{x,z,yaw,grade} }
// buildLand(THREE, coast, { EIDOVERSE_DIR }) -> { group, mats, update(t) }

import { rng, fileTexture, smooth, OCEAN_ASSETS } from './util.js';

const smoothstep = (a, b, x) => smooth((x - a) / (b - a));

// the coastline, land on the +z / inland side, walked from the far right to the far left
export const COAST = [
    [420, 48], [160, 22], [70, 10], [45, 6.2], [30, 4.4], [19, 2.5], [11.5, 1.0], [6.6, -0.7], [3.3, -2.5],
    [1.2, -4.0], [-0.9, -4.6], [-3.1, -4.0], [-5.6, -2.4], [-8.6, -1.4], [-12.2, -2.3], [-15.8, -5.2],
    [-18.3, -9.8], [-19.0, -15.0], [-17.8, -19.3], [-15.0, -21.7], [-11.6, -22.3], [-8.2, -22.6], [-5.6, -23.7],
    [-3.9, -26.2], [-4.4, -29.3], [-6.9, -31.8], [-11.4, -33.0], [-16.4, -32.7], [-22.5, -31.7], [-30, -33.2],
    [-46, -36.5], [-80, -41], [-200, -52], [-420, -66],
];
const INLAND = [[-420, 600], [420, 600]];                       // closes the land polygon far inland

export function makeCoast() {
    const poly = [...COAST, ...INLAND];
    const segs = [];
    for (let i = 0; i < COAST.length - 1; i++) segs.push([COAST[i], COAST[i + 1]]);
    const inside = (x, z) => {                                  // point in the land polygon (even-odd)
        let c = false;
        for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
            const [xi, zi] = poly[i], [xj, zj] = poly[j];
            if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) c = !c;
        }
        return c;
    };
    const sdist = (x, z) => {
        let best = 1e9;
        for (const [[ax, az], [bx, bz]] of segs) {
            const vx = bx - ax, vz = bz - az, wx = x - ax, wz = z - az;
            const t = Math.max(0, Math.min(1, (wx * vx + wz * vz) / (vx * vx + vz * vz)));
            const dx = wx - vx * t, dz = wz - vz * t;
            const d = dx * dx + dz * dz;
            if (d < best) best = d;
        }
        const d = Math.sqrt(best);
        return inside(x, z) ? -d : d;
    };
    // the house sits on the spit, its porch facing across the cove toward her rise
    const house = { x: -10.9, z: -28.1 };
    house.yaw = Math.atan2(-house.x, -house.z);                  // +z of the house points at her
    const rawHeight = (x, z, s) => {
        let h;
        if (s > 0) h = -Math.min(4.5, 0.2 * s + 0.004 * s * s);            // the shelving sea floor
        else {
            const d = -s;
            h = 0.58 * smoothstep(0, 7.5, d);                                 // the beach
            const dune = 0.5 + 0.5 * Math.sin(x * 0.105 + Math.sin(z * 0.071) * 2.1) * Math.cos(z * 0.087 + 0.7);
            h += smoothstep(4.5, 17, d) * (0.45 + 0.75 * dune);               // dune field
            h += smoothstep(30, 240, d) * (4.5 + 2.5 * Math.sin(x * 0.011 + 1.3) * Math.cos(z * 0.008));   // hills inland
        }
        const r2 = (x - 0.2) ** 2 + (z - 0.45) ** 2;
        h += 0.98 * Math.exp(-r2 / (2 * 2.35 * 2.35)) * smoothstep(-1.2, 3.0, -s);   // HER RISE
        h += 0.035 * Math.sin(x * 1.31 + z * 0.73) * Math.sin(z * 1.07 - x * 0.41) * smoothstep(0, 2, -s);
        return h;
    };
    const markRaw = rawHeight(0, 0, sdist(0, 0));
    // house pad: level grade under the footprint + porch
    const hs = sdist(house.x, house.z);
    const houseGrade = Math.max(0.42, rawHeight(house.x, house.z, hs)) + 0.02;
    const height = (x, z) => {
        const s = sdist(x, z);
        let h = rawHeight(x, z, s);
        const rm = Math.hypot(x, z);                                        // level ground under her feet
        h += (markRaw - h) * smoothstep(1.0, 0.45, rm);
        const c = Math.cos(house.yaw), sn = Math.sin(house.yaw);          // house pad (house-local axes)
        const lx = (x - house.x) * c - (z - house.z) * sn, lz = (x - house.x) * sn + (z - house.z) * c;
        const pad = Math.max(Math.abs(lx) / 3.6, Math.abs(lz - 0.6) / 3.9);
        h += (houseGrade - h) * smoothstep(1.45, 1.0, pad);
        return h;
    };
    return { sdist, height, markY: markRaw, house: { ...house, grade: houseGrade } };
}

export async function buildLand(THREE, coast, ctx = {}) {
    const { Fn, uniform, float, vec2, vec3, vec4, positionGeometry, texture, mix, smoothstep: ss, sin, cos, normalMap,
        clamp, instanceIndex, hash, positionLocal } = THREE;
    const group = new THREE.Group();
    group.name = 'ocean:land';

    // ---------------------------------------------------------------- mesh (polar, fine at her feet)
    const NR = 300, NS = 720, R0 = 0.04, RMAX = 1500;
    const gro = Math.pow(RMAX / R0, 1 / NR);
    const nV = (NR + 1) * NS + 1;
    const pos = new Float32Array(nV * 3), sArr = new Float32Array(nV);
    pos[0] = 0; pos[1] = coast.height(0, 0); pos[2] = 0; sArr[0] = coast.sdist(0, 0);
    for (let i = 0; i <= NR; i++) {
        const r = R0 * Math.pow(gro, i);
        for (let j = 0; j < NS; j++) {
            const a = (j / NS) * Math.PI * 2, x = Math.sin(a) * r, z = -Math.cos(a) * r;
            const k = 1 + i * NS + j;
            sArr[k] = coast.sdist(x, z);
            pos[k * 3] = x; pos[k * 3 + 1] = coast.height(x, z); pos[k * 3 + 2] = z;
        }
    }
    const idx = [];
    for (let j = 0; j < NS; j++) idx.push(0, 1 + (j + 1) % NS, 1 + j);        // CCW seen from above (+y)
    for (let i = 0; i < NR; i++) for (let j = 0; j < NS; j++) {
        const a = 1 + i * NS + j, b = 1 + i * NS + (j + 1) % NS, c = 1 + (i + 1) * NS + j, d = 1 + (i + 1) * NS + (j + 1) % NS;
        const lo = Math.max(pos[a * 3 + 1], pos[b * 3 + 1], pos[c * 3 + 1], pos[d * 3 + 1]);
        if (lo < -1.6) continue;                                // deep sea floor: hidden by the water
        idx.push(a, b, c, b, d, c);                            // CCW seen from above (+y)
    }
    const uvArr = new Float32Array(nV * 2);                 // world-planar uvs: normalMap derives its tangent frame from these
    for (let k = 0; k < nV; k++) { uvArr[k * 2] = pos[k * 3] / 3.1; uvArr[k * 2 + 1] = pos[k * 3 + 2] / 3.1; }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('uv', new THREE.BufferAttribute(uvArr, 2));
    geo.setAttribute('shore', new THREE.BufferAttribute(sArr, 1));
    geo.setIndex(idx);
    geo.computeVertexNormals();
    geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), RMAX);

    // ---------------------------------------------------------------- PBR: Poly Haven CC0 (sources.json)
    const T = OCEAN_ASSETS + 'tex/';
    const ld = (p, srgb) => fileTexture(THREE, T + p, { srgb });
    const [sD, sN, sA, wD, wN, wA, gD, gN, gA] = await Promise.all([
        ld('sand/coast_sand_01_diff_2k.jpg', true), ld('sand/coast_sand_01_nor_gl_2k.jpg'), ld('sand/coast_sand_01_arm_2k.jpg'),
        ld('sand/sand_03_diff_2k.jpg', true), ld('sand/sand_03_nor_gl_2k.jpg'), ld('sand/sand_03_arm_2k.jpg'),
        ld('grass/withered_grass_diff_2k.jpg', true), ld('grass/withered_grass_nor_gl_2k.jpg'), ld('grass/withered_grass_arm_2k.jpg'),
    ]);
    const mat = new THREE.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 });
    mat.name = 'ocean_land';
    const p = positionGeometry;
    const uvS = p.xz.div(3.1), uvS2 = vec2(p.x.mul(0.8).sub(p.z.mul(0.6)), p.x.mul(0.6).add(p.z.mul(0.8))).div(8.3);
    const uvW = p.xz.div(2.4), uvG = p.xz.div(2.2);
    const h = p.y;
    const macro = sin(p.x.mul(0.37).add(sin(p.z.mul(0.23)).mul(1.7))).mul(cos(p.z.mul(0.31).sub(p.x.mul(0.11)))).mul(0.5).add(0.5);
    const wet = float(1).sub(ss(0.1, 0.42, h));
    const grassN = sin(p.x.mul(0.61).add(cos(p.z.mul(0.43)).mul(2.0))).mul(sin(p.z.mul(0.53).sub(p.x.mul(0.21)))).mul(0.5).add(0.5);
    const rise = ss(1.2, 0.35, positionGeometry.xz.sub(vec2(0.2, 0.45)).length().div(3.4));   // around her
    const grass = clamp(ss(0.95, 1.35, h).mul(ss(0.25, 0.6, grassN)).add(rise.mul(ss(0.9, 1.15, h)).mul(0.85)), 0, 1);
    const dryC = mix(texture(sD, uvS).rgb, texture(sD, uvS2).rgb, 0.35).mul(macro.mul(0.25).add(0.85));
    const wetC = texture(wD, uvW).rgb.mul(0.42);
    const grassC = texture(gD, uvG).rgb.mul(0.92);
    mat.colorNode = mix(mix(dryC, wetC, wet), grassC, grass);
    const rS = texture(sA, uvS).g, rW = texture(wA, uvW).g.mul(0.3).add(0.42), rG = texture(gA, uvG).g;
    mat.roughnessNode = mix(mix(rS, rW, wet), rG, grass);
    const aoN = mix(mix(texture(sA, uvS).r, float(1), wet), texture(gA, uvG).r, grass);
    mat.aoNode = aoN;
    const nS = texture(sN, uvS), nW = texture(wN, uvW), nG = texture(gN, uvG);
    mat.normalNode = normalMap(mix(mix(nS, nW, wet), nG, grass), vec2(1.0, 1.0));
    const land = new THREE.Mesh(geo, mat);
    land.name = 'ocean_land';
    land.receiveShadow = true;
    group.add(land);

    // ---------------------------------------------------------------- dune grass: geometry blades, instanced
    const R = rng(29);
    const blades = [];
    const tuftGeo = (() => {
        const P = [], I = [], UVs = [];
        const nb = 13, segs = 5;
        for (let b = 0; b < nb; b++) {
            const az = R() * Math.PI * 2, lean = 0.15 + R() * 0.55, H = 0.32 + R() * 0.48, w0 = 0.006 + R() * 0.006;
            const ox = (R() - 0.5) * 0.09, oz = (R() - 0.5) * 0.09;
            const base = P.length / 3;
            for (let s = 0; s <= segs; s++) {
                const t = s / segs, y = H * t, off = Math.sin(lean) * H * t * t;
                const cx = ox + Math.sin(az) * off, cz = oz + Math.cos(az) * off;
                const w = w0 * (1 - t * 0.92);
                const px = Math.cos(az) * w, pz = -Math.sin(az) * w;
                P.push(cx - px, y * Math.cos(lean * t * 0.6), cz - pz, cx + px, y * Math.cos(lean * t * 0.6), cz + pz);
                UVs.push(0, t, 1, t);
                if (s < segs) { const q = base + s * 2; I.push(q, q + 1, q + 2, q + 1, q + 3, q + 2); }
            }
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
        g.setAttribute('uv', new THREE.Float32BufferAttribute(UVs, 2));
        g.setIndex(I);
        g.computeVertexNormals();
        return g;
    })();
    for (let tries = 0; tries < 60000 && blades.length < 2600; tries++) {
        const x = (R() - 0.5) * 110, z = -34 + R() * 80;
        const hh = coast.height(x, z), s = coast.sdist(x, z);
        if (s > -2.5 || hh < 0.7) continue;
        const rm = Math.hypot(x - 0.0, z - 0.0);
        if (rm < 0.95) continue;                                   // her feet stay clear
        const hx = x - coast.house.x, hz = z - coast.house.z;
        if (Math.hypot(hx, hz) < 4.6) continue;                    // the house pad
        const gN = 0.5 + 0.5 * Math.sin(x * 0.61 + Math.cos(z * 0.43) * 2.0) * Math.sin(z * 0.53 - x * 0.21);
        const want = (hh > 1.0 ? 0.55 : 0.2) * (0.3 + gN) + (rm < 4 ? 0.5 : 0);
        if (R() > want) continue;
        blades.push([x, hh - 0.02, z, R() * Math.PI * 2, 0.7 + R() * 0.7]);
    }
    const gcv = document.createElement('canvas');
    gcv.width = 16; gcv.height = 256;
    const gg = gcv.getContext('2d');
    const grd = gg.createLinearGradient(0, 256, 0, 0);
    grd.addColorStop(0, '#5a5436'); grd.addColorStop(0.35, '#8f8458'); grd.addColorStop(0.8, '#c9b98a'); grd.addColorStop(1, '#e2d5ad');
    gg.fillStyle = grd; gg.fillRect(0, 0, 16, 256);
    const gTex = new THREE.CanvasTexture(gcv);
    gTex.colorSpace = THREE.SRGBColorSpace;
    const gMat = new THREE.MeshStandardNodeMaterial({ roughness: 0.78, metalness: 0, side: THREE.DoubleSide });
    gMat.name = 'ocean_dunegrass';
    const U = { t: uniform(0), wind: uniform(1) };
    const ph = hash(instanceIndex.toFloat().add(3.0)).mul(6.283);
    const vv = THREE.uv().y;
    gMat.colorNode = texture(gTex, vec2(0.5, vv)).rgb.mul(hash(instanceIndex.toFloat().add(11.0)).mul(0.35).add(0.75));
    gMat.positionNode = Fn(() => {
        const q = positionLocal;
        const sway = sin(U.t.mul(1.1).add(ph)).mul(0.6).add(sin(U.t.mul(2.3).add(ph.mul(1.7))).mul(0.25)).mul(U.wind);
        const k = q.y.mul(q.y).mul(0.16);
        return vec3(q.x.add(sway.mul(k)), q.y, q.z.add(sway.mul(k).mul(0.6)));
    })();
    const inst = new THREE.InstancedMesh(tuftGeo, gMat, blades.length);
    const m4 = new THREE.Matrix4(), qq = new THREE.Quaternion(), sc = new THREE.Vector3();
    blades.forEach(([x, y, z, yaw, s], i) => {
        qq.setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
        sc.set(s, s * (0.85 + 0.3 * ((i * 7919) % 13) / 13), s);
        m4.compose(new THREE.Vector3(x, y, z), qq, sc);
        inst.setMatrixAt(i, m4);
    });
    inst.instanceMatrix.needsUpdate = true;
    inst.name = 'ocean_dunegrass';
    if (blades.length > 0) group.add(inst);

    // ---------------------------------------------------------------- her flowers, closed for the night
    let daisies = null;
    try {
        const { build } = await import('./daisies.js');          // the DAISY film's instanced daisy field (vendored with this set)
        daisies = await build(THREE, {
            count: 420, width: 5.2, depth: 4.6, center: [0.25, 0.5], seed: 5, heightFn: coast.height,
            faceDir: [0.1, 0.6, 1.0], clear: [{ a: [-0.25, 0.0], b: [0.25, 0.0], w: 1.25 }], close: 1.0,
            stemHeight: [0.16, 0.28], headScale: 1.2,
        });
        group.add(daisies.group);
    } catch (e) { console.warn('[ocean] daisies unavailable:', e.message); }

    return {
        group, mats: [mat, gMat], grassCount: blades.length,
        update(t) {
            U.t.value = t;
            daisies?.update(t, { close: 1, pulse: 0, wind: 0.35 });
        },
    };
}
