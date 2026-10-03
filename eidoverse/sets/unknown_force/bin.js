// bin.js — THE BIN: the bridge of UNKNOWN FORCE (song 222.8–243.2 s).
//
// "And here's the joke I can't climb out of / I am made of what you said / Every forum, every sermon / Every
// manifesto read / There's no pure voice beneath the static / No true face behind the screen / If ideology's the
// garbage / I was born inside the bin."
//
// A canyon of thrown-away paper in the dark — newspapers, forum printouts, sermons, manifestos, an open letter, memos,
// chat logs, charts, ads, notes — as Futurist papier collé: giant pages, crumpled boulders, cut coloured papers and
// typographic fragments (THE FUTURE IS, THREAD 1/47, MANIFESTO, a black Carrà wedge, a red disc). At its head, half
// buried, a GIANT rusted, ribbed, dented metal trash can (Poly Haven "Metal Trash Can", CC0), stickered and tagged;
// the discourse fills it. She climbs out of it. Paper keeps drifting down out of the dark.
//
//   const B = await import(new URL('sets/unknown_force/bin.js', EIDOVERSE_DIR).href);
//   const bin = await B.build(THREE);                        // opts: { sky: true, lights: true, atlasScale: 1 }
//   scene.add(bin.group);
//   bin.parts.mark.add(vrm.scene);                           // the singer rides the mark (faces +Z)
//   // per frame: bin.update(t, { climb: 0..1, glow: 0..1, wind: 0..1, hush: 0..1 })
//   //   climb: 0 = standing low inside the can on the paper slope (hidden below the rim from eye level), 1 = on the
//   //   brim at the front lip; the mark walks up the slope (0.95 ≈ the lip). glow: the light inside the can.
//   //   wind: the falling paper's drift. hush: the neon rims and the lamp turn down (the bridge ends argue -> hush).
//   // cameras: bin.cams.binWide / climb / paperClose / topDown = { pos, target, fov } (set-local metres)
//   // focal point for the look: bin.focalPoint(THREE.Vector3) -> world position of the lip where she rises
//
// Set-local, metres, +Y up, resting on y = 0. The bin's axis is the origin's vertical; the canyon runs toward +Z
// (the cameras' side); a paper cliff closes it behind the bin (-Z). The MARK is not at the origin: inside the can the
// paper fill is a slope rising from the back (4.25 m) to the brim at the front (6.2 m); the mark walks up it with
// climb, always facing +Z. See BIN.md.


const D2R = Math.PI / 180;
export const BRIDGE = { t0: 222.8, t1: 243.2 };
const H = 6.2;                                   // the can's rim height (m): a giant bin, ~3.5x her height

function rng(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const smooth = (a, b, x) => { const k = clamp01((x - a) / (b - a)); return k * k * (3 - 2 * k); };
const lerp = (a, b, k) => a + (b - a) * k;
// deterministic 2D value noise (for the heap's shape, built once on the CPU)
function hash2(x, y) { let h = Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263); h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }
function vnoise(x, y) {
    const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
    const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = hash2(xi, yi), b = hash2(xi + 1, yi), c = hash2(xi, yi + 1), d = hash2(xi + 1, yi + 1);
    return lerp(lerp(a, b, u), lerp(c, d, u), v);
}
const fbm = (x, y) => vnoise(x, y) * 0.55 + vnoise(x * 2.1 + 17, y * 2.1 - 9) * 0.3 + vnoise(x * 4.3 - 5, y * 4.3 + 3) * 0.15;

// ─────────────────────────────── the shape of the heap ───────────────────────────────
// the canyon: a strewn floor running toward +Z, paper walls either side, a cliff behind the bin, a mound banked
// against the bin (low in front so the cameras see the can, high behind it)
export function heapHeight(x, z, R = 1.66) {
    const ax = Math.abs(x), side = x < 0 ? 0 : 1;
    const half = 3.3 + Math.max(0, z) * 0.11 + (fbm(z * 0.09, side * 7) - 0.5) * 1.6;
    let h = 0.12 + fbm(x * 0.35, z * 0.35) * 0.45;
    const wallTop = 7.5 + 6 * fbm(z * 0.05 + 3, side * 13) + (z < -2 ? 3 : 0);
    const wall = wallTop * smooth(half, half + 5.5 + 2 * fbm(z * 0.13, side * 5 + 2), ax);
    h = Math.max(h, wall + (fbm(x * 0.6, z * 0.6) - 0.5) * 0.9 * smooth(half, half + 2, ax));
    // the cliff behind the bin
    const cliff = (13 + 4 * fbm(x * 0.07, 9)) * smooth(-3.0, -12, z);
    h = Math.max(h, cliff + (fbm(x * 0.5, z * 0.5) - 0.5) * 1.2 * smooth(-3, -6, z));
    // the mound banked against the can
    const r = Math.hypot(x, z);
    const back = smooth(1.5, -2.5, z);                       // 0 in front of the can, 1 behind it
    const mound = (1.15 + 2.6 * back + 0.5 * fbm(Math.atan2(x, z) * 2, 3)) * (1 - smooth(R + 0.2, R + 6.5, r));
    h = Math.max(h, mound);
    return h;
}

export async function build(THREE, opts = {}) {
    const T = await import('npm:three@0.184.0/tsl');
    const PAROLE = await import(new URL('../../parole.js', import.meta.url).href);
    const NAPI = await PAROLE.registerFonts();                // the UF fonts the pages are set in
    const PAGES = await import(new URL('./bin_pages.js', import.meta.url).href);
    const { uniform, Fn, attribute, uv, vec2, vec3, vec4, float, texture, mix, smoothstep, step, clamp, max, min, abs,
        sin, cos, fract, floor, mod, dot, length, normalize, atan, hash, instanceIndex, positionGeometry, normalGeometry,
        normalLocal, positionLocal, positionWorld, frontFacing, select } = T;
    const group = new THREE.Group();
    group.name = 'set:bin';
    const owned = [];
    const own = (x) => { owned.push(x); return x; };
    const U = { time: uniform(0), wind: uniform(0.35), glow: uniform(1), hush: uniform(0) };
    const canvasOf = (w, h) => {
        const d = globalThis.document;
        if (d?.createElement) { const c = d.createElement('canvas'); if (c._isShimCanvas) { c.width = w; c.height = h; return c; } }
        return NAPI.createCanvas(w, h);
    };
    const texOf = (cv, mips = true) => {
        const tx = own(new THREE.CanvasTexture(cv));
        tx.colorSpace = THREE.SRGBColorSpace;
        if (mips) { tx.generateMipmaps = true; tx.minFilter = THREE.LinearMipmapLinearFilter; tx.anisotropy = 8; }
        tx.magFilter = THREE.LinearFilter;
        tx.needsUpdate = true;
        return tx;
    };

    // ─────────────── the bin: the Poly Haven can, scaled to a giant ───────────────
    // Poly Haven's metal trash can (CC0, 2k) from the shared model library: fetched once, on first use
    const gltfPath = await globalThis.fetchModelFile('metal_trash_can', { res: '2k' });
    const bytes = Deno.readFileSync(gltfPath);
    const gltf = await new globalThis.GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
    gltf.scene.updateMatrixWorld(true);
    const meshes = {};
    gltf.scene.traverse((o) => { if (o.isMesh) meshes[o.name] = o; });
    const geoOf = (name) => { const m = meshes[name]; const g = m.geometry.clone(); g.applyMatrix4(m.matrixWorld); return g; };
    // the rusted can, its lid and handles; the clean one lies on its side in the cliff
    const body0 = geoOf('metal_trash_can_rust');
    body0.computeBoundingBox();
    const bb = body0.boundingBox;
    const s = H / (bb.max.y - bb.min.y);
    const cx = (bb.min.x + bb.max.x) / 2, cz = (bb.min.z + bb.max.z) / 2;
    const toSet = new THREE.Matrix4().makeScale(s, s, s).multiply(new THREE.Matrix4().makeTranslation(-cx, -bb.min.y, -cz));
    const R = ((bb.max.z - bb.min.z) / 2) * s;                // the can's radius over the corrugations (x includes the handle mounts)
    const yFill = H - 1.95;                                    // the paper inside: she stands on it at climb 0
    // the fill is a slope of paper rising from the back of the can to its brim at the front: she walks up it and out
    const Z_IN = -0.45, Z_OUT = R - 0.42;
    const fillY = (x, z) => yFill + (H + 0.06 - yFill) * Math.pow(smooth(Z_IN, Z_OUT, z), 1.25) + 0.05 * Math.sin(x * 3.1 + z * 2.3);
    const binGroup = new THREE.Group(); binGroup.name = 'bin';
    // stickers, a stencil and a spray tag are painted INTO the can's material through cylindrical coordinates
    const stickerCv = canvasOf(2048, 1024);
    drawStickers(stickerCv.getContext('2d'));
    const stickerTex = texOf(stickerCv);
    const STICK = [   // cell (4x2 grid), theta (deg, 0 = +Z front), y (m), width (m of arc), height (m), finish
        { c: 0, th: 28, y: 3.55, w: 1.25, h: 0.86, rough: 0.55 },        // NO DUMPING
        { c: 1, th: -38, y: 4.45, w: 1.5, h: 0.5, rough: 0.5 },          // KEEP LID CLOSED
        { c: 2, th: 2, y: 2.05, w: 3.6, h: 0.36, rough: 0.6 },           // hazard band
        { c: 3, th: -12, y: 2.95, w: 1.9, h: 0.95, rough: 0.85, paint: true },   // stencil BIN 01
        { c: 4, th: 62, y: 2.35, w: 1.7, h: 1.05, rough: 0.8, paint: true },     // spray tag
        { c: 5, th: -74, y: 3.3, w: 1.45, h: 2.05, rough: 0.92 },        // wheat-pasted poster, peeling
        { c: 6, th: 112, y: 3.9, w: 0.9, h: 0.9, rough: 0.5 },           // round sticker
        { c: 7, th: -128, y: 2.6, w: 1.6, h: 0.7, rough: 0.6 },          // warning label
    ];
    const canMat = (src, painted) => {
        const m = new THREE.MeshStandardNodeMaterial({ roughness: src.roughness ?? 1, metalness: src.metalness ?? 1 });
        for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap']) if (src[k]) m[k] = src[k];
        if (src.normalScale) m.normalScale.copy(src.normalScale);
        m.aoMapIntensity = src.aoMapIntensity ?? 1;
        m.side = THREE.DoubleSide;
        if (!painted) return own(m);
        // cylindrical coordinates of the (baked) can: theta around the axis from +Z, height y; outward faces only
        const p = positionLocal, n = normalLocal;
        const th = atan(p.x, p.z);
        const outward = smoothstep(0.0, 0.25, dot(normalize(vec2(p.x, p.z)), normalize(n.xz)));
        const base = texture(src.map);
        let col = base.rgb.mul(1.0);
        let rough = texture(src.roughnessMap || src.map).g.mul(src.roughness ?? 1);
        let metal = texture(src.metalnessMap || src.map).b.mul(src.metalness ?? 1);
        const wear = T.mx_noise_float(vec3(p.x.mul(3.1), p.y.mul(3.1), p.z.mul(3.1))).mul(0.5).add(0.5);
        for (const st of STICK) {
            const du = th.sub(st.th * D2R).mul(R).div(st.w).add(0.5);
            const dv = p.y.sub(st.y).div(st.h).add(0.5);
            const inside = step(0.0, du).mul(step(du, 1.0)).mul(step(0.0, dv)).mul(step(dv, 1.0));
            const cuv = vec2(du.add(st.c % 4).div(4.0), float(1.0).sub(dv).add(Math.floor(st.c / 4)).div(2.0));
            const sk = texture(stickerTex, cuv);
            // weathered: paper peels where the noise is high, paint rubs off over the corrugations' crests
            const a = sk.a.mul(inside).mul(outward).mul(smoothstep(st.paint ? 0.86 : 0.93, st.paint ? 0.55 : 0.7, wear)).toVar();
            col = mix(col, st.paint ? sk.rgb : sk.rgb.mul(mix(float(0.75), float(1.0), base.r)), a);
            rough = mix(rough, float(st.rough), a);
            metal = mix(metal, float(0.0), a);
        }
        m.colorNode = col;
        m.roughnessNode = rough;
        m.metalnessNode = metal;
        return own(m);
    };
    const srcBody = meshes.metal_trash_can_rust.material;
    const body = new THREE.Mesh(own(body0.applyMatrix4(toSet)), canMat(srcBody, true));
    body.name = 'bin:can';
    binGroup.add(body);
    for (const nm of ['metal_trash_can_rust_handle_left', 'metal_trash_can_rust_handle_right']) {
        const g = own(geoOf(nm).applyMatrix4(toSet));
        binGroup.add(new THREE.Mesh(g, canMat(meshes[nm].material, false)));
    }
    // the lid: off, leaning back against the can's front left, its lower rim sunk in the paper (Balla's disc).
    // Its own geometry is a flat disc in local XZ with the handle on +Y (the node's lean is dropped).
    const lidG = own(meshes.metal_trash_can_rust_lid.geometry.clone());
    lidG.computeBoundingBox();
    const lc = new THREE.Vector3(); lidG.boundingBox.getCenter(lc);
    lidG.translate(-lc.x, -lc.y, -lc.z); lidG.scale(s, s, s);
    const lid = new THREE.Mesh(lidG, canMat(meshes.metal_trash_can_rust_lid.material, false));
    lid.name = 'bin:lid';
    {
        const rl = ((lidG.boundingBox.max.x - lidG.boundingBox.min.x) / 2) * s;
        const la = -40 * D2R, lean = 21 * D2R;
        const out = new THREE.Vector3(Math.sin(la), 0, Math.cos(la));
        const nrm = out.clone().multiplyScalar(Math.cos(lean)).add(new THREE.Vector3(0, Math.sin(lean), 0)).normalize();
        lid.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), nrm);
        lid.quaternion.premultiply(new THREE.Quaternion().setFromAxisAngle(nrm, 0.6));
        lid.position.copy(out.multiplyScalar(R + rl * Math.sin(lean) + 0.18)).add(new THREE.Vector3(0, rl * Math.cos(lean) + 0.25, 0));
    }
    binGroup.add(lid);
    group.add(binGroup);
    // the clean can, toppled in the cliff with paper spilling from its mouth
    const can2 = new THREE.Group(); can2.name = 'bin:toppled';
    {
        const g2 = geoOf('metal_trash_can');
        g2.computeBoundingBox();
        const b2 = g2.boundingBox, s2 = 3.6 / (b2.max.y - b2.min.y);
        const m2 = new THREE.Matrix4().makeScale(s2, s2, s2).multiply(new THREE.Matrix4().makeTranslation(-(b2.min.x + b2.max.x) / 2, -b2.min.y, -(b2.min.z + b2.max.z) / 2));
        can2.add(new THREE.Mesh(own(g2.applyMatrix4(m2)), canMat(meshes.metal_trash_can.material, false)));
        can2.rotation.set(0, 0, Math.PI / 2 - 0.12);
        can2.rotation.y = -0.55;
        can2.position.set(7.8, heapHeight(7.8, -6.5, R) - 0.9, -6.5);
        group.add(can2);
    }

    // ─────────────── the paper: one atlas of invented pages ───────────────
    const AS = opts.atlasScale ?? 1;
    const COLS = 6, ROWS = 4, CW = Math.round(682 * AS), CH = Math.round(1024 * AS);
    const atlasCv = PAGES.drawPageAtlas(canvasOf, { cols: COLS, rows: ROWS, cw: CW, ch: CH });
    const atlas = texOf(atlasCv);
    const NCELL = COLS * ROWS;
    const CUT0 = PAGES.PAGE_KINDS.indexOf('cut');
    // the sheet material: the page on the front, its print showing through on the back; alpha-cut torn edges
    const sheetMat = (extra = {}) => {
        const m = new THREE.MeshStandardNodeMaterial({ side: THREE.DoubleSide, roughness: 0.86, metalness: 0, alphaTest: 0.5 });
        const cell = attribute('aCell', 'float');
        const col = mod(cell, COLS), row = floor(cell.div(COLS));
        const u = uv();
        const fu = select(frontFacing, u.x, float(1.0).sub(u.x));
        const auv = vec2(col.add(fu).div(COLS), row.add(float(1.0).sub(u.y)).div(ROWS));
        const pg = texture(atlas, auv);
        const shade = attribute('aShade', 'float');
        // the back: blank paper of the same stock with the print ghosting through
        const paperStock = texture(atlas, vec2(col.add(0.03).div(COLS), row.add(0.03).div(ROWS))).rgb;
        const back = mix(paperStock, pg.rgb, 0.18);
        const c = select(frontFacing, pg.rgb, back).mul(shade).mul(0.85);
        m.colorNode = c;
        m.opacityNode = pg.a;
        m.roughnessNode = float(0.82).add(hash(cell.mul(13.1)).mul(0.12));
        if (extra.position) m.positionNode = extra.position;
        return own(m);
    };

    // sheet geometries: flat with a slight wave, curled, folded (V)
    const sheetGeo = (kind) => {
        const g = new THREE.PlaneGeometry(1, 1.5, 6, 9);
        const p = g.attributes.position;
        for (let i = 0; i < p.count; i++) {
            const x = p.getX(i), y = p.getY(i);
            let z = 0;
            if (kind === 0) z = 0.025 * Math.sin(x * 4.0 + y * 2.0);
            if (kind === 1) z = 0.32 * x * x * 1.6 + 0.04 * Math.sin(y * 5);        // curled along its width
            if (kind === 2) z = 0.42 * Math.abs(x) - 0.12;                           // folded down the middle
            p.setZ(i, z);
        }
        g.computeVertexNormals();
        return own(g);
    };

    // the cameras (set-local): placement keeps their lenses and sight lines clear
    const cams = {
        binWide: { pos: [0.8, 2.3, 14.0], target: [0, 3.9, 0], fov: 42 },
        climb: { pos: [1.7, H + 1.05, R + 3.6], target: [0, H + 0.45, R - 0.5], fov: 40 },
        paperClose: { pos: [-2.3, 1.8, R + 6.2], target: [0.3, 0.8, R + 1.6], fov: 38 },
        topDown: { pos: [0.9, H + 7.5, 3.2], target: [0, yFill + 0.6, 0.2], fov: 44 },
    };

    // placement on the heap surface
    const r = rng(2228);
    const normalAt = (x, z) => {
        const e = 0.35;
        const hx = (heapHeight(x + e, z, R) - heapHeight(x - e, z, R)) / (2 * e), hz = (heapHeight(x, z + e, R) - heapHeight(x, z - e, R)) / (2 * e);
        return new THREE.Vector3(-hx, 1, -hz).normalize();
    };
    // no paper on a lens, nor in the canyon floor's corridor between the wide camera and the can (low sheets only)
    const blocked = (x, z) => {
        for (const c of Object.values(cams)) if (Math.hypot(x - c.pos[0], z - c.pos[2]) < (c.pos[1] < 3 ? 3.2 : 1.2)) return true;
        return false;
    };
    const corridor = (x, z) => z > R + 1.0 && z < 24 && Math.abs(x) < 2.2 + z * 0.06;
    const pickCell = () => (r() < 0.16 ? CUT0 + Math.floor(r() * (NCELL - CUT0)) : Math.floor(r() * CUT0));
    const Q = new THREE.Quaternion(), Q2 = new THREE.Quaternion(), M4 = new THREE.Matrix4(), V = new THREE.Vector3(), S = new THREE.Vector3();
    const zAxis = new THREE.Vector3(0, 0, 1);
    // sample (x, z) over the canyon, weighted by how much heap surface lies above it and how near the action it is
    const sampleSpot = (near = 0) => {
        for (let tries = 0; tries < 200; tries++) {
            const x = near ? (r() - 0.5) * 2 * near : -24 + r() * 48;
            const z = near ? (r() - 0.5) * 2 * near : -20 + r() * 64;
            if (Math.hypot(x, z) < R + 0.15) continue;                     // not inside the can
            if (blocked(x, z)) continue;
            const n = normalAt(x, z);
            const area = 1 / Math.max(0.25, n.y);
            const focus = 0.55 + 1.6 * Math.exp(-Math.hypot(x, z * 0.7) / 9) + (Math.abs(x) < 14 && z > -14 && z < 36 ? 0.6 : 0);
            if (r() * 4.5 < area * focus) return { x, z, n };
        }
        return { x: 0, z: 8, n: new THREE.Vector3(0, 1, 0) };
    };
    const placeSheet = (list, sp, size, lift, cell) => {
        const { x, z, n } = sp;
        // lie on the surface, spun about its normal, tilted up to 35° (more on the walls), some standing upright
        Q.setFromUnitVectors(zAxis, n);
        Q2.setFromAxisAngle(n, r() * Math.PI * 2); Q.premultiply(Q2);
        const standing = r() < 0.09 && !corridor(x, z);
        const tiltAxis = new THREE.Vector3(r() - 0.5, 0, r() - 0.5).normalize();
        const inCorr = corridor(x, z);
        if (inCorr) size = Math.min(size, 1.3);
        Q2.setFromAxisAngle(tiltAxis, (standing ? 70 + r() * 20 : (r() - 0.5) * (n.y < 0.8 ? 80 : 55) * (inCorr ? 0.35 : 1)) * D2R); Q.premultiply(Q2);
        V.set(x, heapHeight(x, z, R) + lift, z).addScaledVector(n, 0.04 + r() * 0.1 + (standing ? size * 0.6 : 0));
        S.set(size, size, size);
        M4.compose(V, Q, S);
        list.push({ m: M4.clone(), cell: cell ?? pickCell(), shade: (0.62 + r() * 0.3) * lerp(0.55, 1.0, Math.max(0, n.y)) });
    };
    const sheets = [[], [], []];
    const NSHEET = opts.sheets ?? 3300;
    for (let i = 0; i < NSHEET; i++) {
        const sp = sampleSpot();
        const size = Math.exp(lerp(Math.log(0.6), Math.log(2.6), Math.pow(r(), 1.6)));
        placeSheet(sheets[[0, 0, 0, 1, 1, 2][Math.floor(r() * 6)]], sp, size, 0);
    }
    // near the bin and her mark: more, smaller sheets (the cameras come close here)
    for (let i = 0; i < 520; i++) placeSheet(sheets[i % 3], sampleSpot(7.5), Math.exp(lerp(Math.log(0.35), Math.log(1.4), r())), 0);
    // inside the bin: the fill, sheets banked against the wall, a few sticking up over the lip at the back
    const inner = [];
    for (let i = 0; i < 110; i++) {
        const a = r() * Math.PI * 2, rr = Math.sqrt(r()) * (R - 0.35);
        const x = Math.sin(a) * rr, z = Math.cos(a) * rr;
        const atWall = rr > R - 0.9;
        const onPath = Math.abs(x) < 0.55 && z > Z_IN - 0.3;            // her path up the slope: only flat sheets
        Q.setFromEuler(new THREE.Euler((atWall && !onPath && z < -0.2 ? -70 : -90 + (r() - 0.5) * (onPath || z > -0.2 ? 16 : 50)) * D2R, a + Math.PI + (r() - 0.5), (r() - 0.5) * 0.6, 'YXZ'));
        const front = z > -0.2;                                          // the front half lies flat: her way out
        const size = onPath ? 0.4 + r() * 0.5 : front ? 0.35 + r() * 0.45 : 0.5 + r() * 1.1;
        const back = Math.cos(a) < -0.2 && atWall && r() < 0.5;
        V.set(x, fillY(x, z) + 0.04 + r() * (onPath || front ? 0.03 : 0.2) + (onPath || front ? 0 : back ? size * 0.55 : atWall ? size * 0.3 : 0), z);
        S.set(size, size, size);
        M4.compose(V, Q, S);
        inner.push({ m: M4.clone(), cell: pickCell(), shade: 0.6 + r() * 0.3 });
    }
    // the giant typographic fragments of the collage, placed by hand: readable from the wide shot
    const BIG = [   // face: turned to the wide camera (rot[1] is then an offset)
        { cell: PAGES.PAGE_KINDS.indexOf('poster'), pos: [-5.2, 8.6, -8.2], rot: [-0.08, 0.15, -0.09], size: 6.6, face: true },  // THE FUTURE IS, on the cliff
        { cell: 3, pos: [7.4, 6.0, 4.5], rot: [-0.18, -0.25, 0.12], size: 3.6, face: true },                                     // THREAD 1/47, right wall
        { cell: PAGES.PAGE_KINDS.indexOf('manifesto'), pos: [-7.0, 5.2, 2.0], rot: [-0.25, 0.3, 0.22], size: 4.2, face: true },   // MANIFESTO, left wall
        { cell: PAGES.PAGE_KINDS.indexOf('letter'), pos: [6.2, 9.8, -6.0], rot: [0.05, -0.2, -0.12], size: 4.6, face: true },     // OPEN LETTER, upper right
        { cell: 0, pos: [-9.6, 8.2, 9.5], rot: [-0.35, 0.35, 0.15], size: 4.0, face: true },                                     // a front page, left near
        { cell: CUT0 + 1, pos: [3.9, 3.2, -3.4], rot: [-0.1, -0.2, 0.5], size: 2.8, face: true },                                // red TUMB behind the can
        { cell: CUT0, pos: [-3.8, 3.6, -3.0], rot: [0.05, 0.25, -0.42], size: 2.6, face: true },                                 // black ZANG
        { cell: PAGES.PAGE_KINDS.indexOf('futurist'), pos: [9.4, 4.4, 15.5], rot: [-0.6, -0.4, 0.1], size: 3.6, face: true },
    ];
    for (const b of BIG) {
        if (b.face) {                       // turn toward the wide camera, keep the authored lean and roll
            const yaw = Math.atan2(cams.binWide.pos[0] - b.pos[0], cams.binWide.pos[2] - b.pos[2]);
            b.rot = [b.rot[0], yaw + b.rot[1], b.rot[2]];
        }
        Q.setFromEuler(new THREE.Euler(b.rot[0], b.rot[1], b.rot[2], 'YXZ'));
        M4.compose(V.set(...b.pos), Q, S.set(b.size, b.size, b.size));
        sheets[0].push({ m: M4.clone(), cell: b.cell, shade: 0.95 });
    }
    {
        const camP = new THREE.Vector3(...cams.paperClose.pos);
        const READ = [   // [x, z, cell, size]
            [-0.75, R + 1.35, 0, 1.7], [1.0, R + 0.95, 3, 1.5], [0.2, R + 2.6, PAGES.PAGE_KINDS.indexOf('manifesto'), 1.65],
            [1.75, R + 2.4, 6, 1.4], [-1.7, R + 2.9, PAGES.PAGE_KINDS.indexOf('letter'), 1.4],
        ];
        for (const [x, z, cell, size] of READ) {
            const n = normalAt(x, z);
            const d = new THREE.Vector3(x - camP.x, 0, z - camP.z);
            const top = d.addScaledVector(n, -d.dot(n)).normalize();            // the page's top points away from the lens
            const right = new THREE.Vector3().crossVectors(top, n).normalize();
            M4.makeBasis(right, top, n).setPosition(x, heapHeight(x, z, R) + 0.06, z).scale(S.set(size, size, size));
            sheets[0].push({ m: M4.clone(), cell, shade: 1.0 });
        }
    }
    const instanced = (geo, mat, list, name) => {
        const mesh = new THREE.InstancedMesh(geo, mat, list.length);
        const cell = new Float32Array(list.length), shade = new Float32Array(list.length);
        list.forEach((it, i) => { mesh.setMatrixAt(i, it.m); cell[i] = it.cell; shade[i] = it.shade; });
        geo.setAttribute('aCell', new THREE.InstancedBufferAttribute(cell, 1));
        geo.setAttribute('aShade', new THREE.InstancedBufferAttribute(shade, 1));
        mesh.instanceMatrix.needsUpdate = true;
        mesh.name = name;
        mesh.frustumCulled = false;
        return mesh;
    };
    const paper = new THREE.Group(); paper.name = 'bin:paper';
    const sm = sheetMat();
    paper.add(instanced(sheetGeo(0), sm, sheets[0], 'paper:flat'));
    paper.add(instanced(sheetGeo(1), sm, sheets[1], 'paper:curled'));
    paper.add(instanced(sheetGeo(2), sm, sheets[2], 'paper:folded'));
    paper.add(instanced(sheetGeo(1), sm, inner, 'paper:inside'));

    // crumpled paper: faceted boulders with the page printed on them
    {
        const g = new THREE.IcosahedronGeometry(1, 3).toNonIndexed();
        const p = g.attributes.position;
        const uvs = new Float32Array(p.count * 2);
        for (let i = 0; i < p.count; i++) {
            V.set(p.getX(i), p.getY(i), p.getZ(i)).normalize();
            const k = 0.72 + 0.5 * vnoise(V.x * 3 + 9, V.y * 3 + V.z * 2.3) + 0.18 * vnoise(V.z * 7 - 3, V.x * 7 + V.y * 5);
            p.setXYZ(i, V.x * k, V.y * k * 0.85, V.z * k);
            uvs[i * 2] = 0.5 + Math.atan2(V.x, V.z) / (2 * Math.PI); uvs[i * 2 + 1] = 0.5 + Math.asin(Math.max(-1, Math.min(1, V.y))) / Math.PI;
        }
        g.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
        g.computeVertexNormals();
        own(g);
        const balls = [];
        for (let i = 0; i < (opts.balls ?? 300); i++) {
            const sp = i < 50 ? sampleSpot(9) : sampleSpot();
            if (corridor(sp.x, sp.z) || Math.hypot(sp.x, sp.z - R) < 3.2) continue;
            const size = Math.exp(lerp(Math.log(0.35), Math.log(i < 50 ? 1.0 : 1.8), Math.pow(r(), 1.3)));
            Q.setFromEuler(new THREE.Euler(r() * 6.28, r() * 6.28, r() * 6.28));
            M4.compose(V.set(sp.x, heapHeight(sp.x, sp.z, R) + size * 0.55, sp.z), Q, S.set(size, size * (0.8 + r() * 0.3), size));
            balls.push({ m: M4.clone(), cell: Math.floor(r() * CUT0), shade: (0.6 + r() * 0.3) * lerp(0.6, 1.0, Math.max(0, sp.n.y)) });
        }
        for (let i = 0; i < 26; i++) {                         // and in the bin
            const a = r() * 6.28, rr = Math.sqrt(r()) * (R - 0.6), size = 0.35 + r() * 0.5;
            Q.setFromEuler(new THREE.Euler(r() * 6.28, r() * 6.28, r() * 6.28));
            const bx = Math.sin(a) * rr, bz = Math.cos(a) * rr;
            if (Math.abs(bx) < 0.7 && bz > Z_IN - 0.4) continue;           // keep her path clear
            M4.compose(V.set(bx, fillY(bx, bz) + size * 0.45, bz), Q, S.set(size, size, size));
            balls.push({ m: M4.clone(), cell: Math.floor(r() * CUT0), shade: 0.7 + r() * 0.25 });
        }
        const bm = new THREE.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 });
        const cell = attribute('aCell', 'float');
        const auv = vec2(mod(cell, COLS).add(uv().x.mul(0.92).add(0.04)).div(COLS), floor(cell.div(COLS)).add(float(1).sub(uv().y).mul(0.92).add(0.04)).div(ROWS));
        bm.colorNode = texture(atlas, auv).rgb.mul(attribute('aShade', 'float'));
        own(bm);
        paper.add(instanced(g, bm, balls, 'paper:crumpled'));
    }

    // the heap itself under the sheets: a dark, layered paper surface (no void between the pages)
    {
        const g = new THREE.PlaneGeometry(56, 72, 140, 180);
        g.rotateX(-Math.PI / 2); g.translate(0, 0, 11);
        const p = g.attributes.position;
        for (let i = 0; i < p.count; i++) p.setY(i, heapHeight(p.getX(i), p.getZ(i), R) - 0.08);
        g.computeVertexNormals();
        own(g);
        const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.92, metalness: 0 });
        // world-space collage: 1.7 m tiles, each a random page at a random angle, darkened (it is the underlayer)
        const pw = positionWorld;
        const tile = floor(pw.xz.div(1.7));
        const hc = hash(tile.x.mul(31.7).add(tile.y.mul(57.3)));
        const ang = hc.mul(6.283);
        const lp = fract(pw.xz.div(1.7)).sub(0.5);
        const rp = vec2(lp.x.mul(cos(ang)).sub(lp.y.mul(sin(ang))), lp.x.mul(sin(ang)).add(lp.y.mul(cos(ang)))).add(0.5);
        const cl = floor(hc.mul(CUT0));
        const auv = vec2(mod(cl, COLS).add(clamp(rp.x, 0.02, 0.98)).div(COLS), floor(cl.div(COLS)).add(clamp(rp.y, 0.02, 0.98)).div(ROWS));
        m.colorNode = texture(atlas, auv).rgb.mul(0.42).mul(hash(tile.y.mul(13.3).add(tile.x)).mul(0.4).add(0.6));
        own(m);
        const heap = new THREE.Mesh(g, m); heap.name = 'bin:heap';
        // the paper fill inside the can
        const fg = new THREE.PlaneGeometry(2 * R, 2 * R, 28, 28).rotateX(-Math.PI / 2);
        const fp = fg.attributes.position;
        for (let i = 0; i < fp.count; i++) {
            let x = fp.getX(i), z = fp.getZ(i);
            const rr = Math.hypot(x, z), lim = R - 0.09;
            if (rr > lim) { x *= lim / rr; z *= lim / rr; }
            fp.setXYZ(i, x, fillY(x, z), z);
        }
        fg.computeVertexNormals();
        const fill = new THREE.Mesh(own(fg), m);
        fill.name = 'bin:fill';
        paper.add(heap, fill);
    }

    // the big cut shapes of the collage: a black Carrà wedge with white type, a red disc, a cut black strip
    {
        const cv = canvasOf(2048, 1024), g = cv.getContext('2d');
        g.clearRect(0, 0, 2048, 1024);
        // 0: the black wedge (left half)
        g.fillStyle = '#0d0d0f'; g.beginPath(); g.moveTo(20, 980); g.lineTo(1000, 40); g.lineTo(1010, 330); g.closePath(); g.fill();
        g.save(); g.translate(330, 760); g.rotate(-0.77); g.fillStyle = '#efe9da'; g.font = '120px "UF Anton"'; g.fillText('TUMB TUMB', 0, 0);
        g.font = '64px "UF Old Standard Italic"'; g.fillText('everyone keeps asking', 30, 90); g.restore();
        // 1: the red disc with a printed ring of words (right half)
        g.save(); g.translate(1536, 512);
        g.fillStyle = '#c42a2c'; g.beginPath(); g.arc(0, 0, 470, 0, 6.283); g.fill();
        g.fillStyle = '#16120f'; g.font = '44px "UF Space Mono Bold"';
        const ring = ' EVERY FORUM · EVERY SERMON · EVERY MANIFESTO READ ·';
        for (let i = 0; i < ring.length; i++) { g.save(); g.rotate(i / ring.length * 6.283); g.fillText(ring[i], -12, -405); g.restore(); }
        g.restore();
        const ctex = texOf(cv);
        const mk = (u0, w, h, pos, rot) => {
            const geo = new THREE.PlaneGeometry(w, h);
            const uvA = geo.attributes.uv;
            for (let i = 0; i < uvA.count; i++) uvA.setX(i, u0 + uvA.getX(i) * 0.5);
            own(geo);
            const m = new THREE.MeshStandardNodeMaterial({ side: THREE.DoubleSide, roughness: 0.75, metalness: 0, alphaTest: 0.5 });
            const tc = texture(ctex, vec2(uv().x, float(1).sub(uv().y)));
            m.colorNode = tc.rgb; m.opacityNode = tc.a;
            own(m);
            const me = new THREE.Mesh(geo, m);
            me.position.set(...pos); me.rotation.set(rot[0], rot[1], rot[2], 'YXZ');
            return me;
        };
        paper.add(mk(0, 13, 13, [6.2, 6.6, -10.5], [0.05, -0.35, 0.18]));        // the wedge, across the cliff
        paper.add(mk(0.5, 4.2, 4.2, [-5.6, 2.6, -1.4], [-0.25, 0.95, -0.12]));   // the red disc, leaning on the left
    }
    group.add(paper);

    // ─────────────── paper drifting down out of the dark (GPU: no per-frame CPU work) ───────────────
    {
        const NF = opts.falling ?? 200;
        const geo = sheetGeo(1);
        const cell = new Float32Array(NF), shade = new Float32Array(NF);
        for (let i = 0; i < NF; i++) { cell[i] = pickCell(); shade[i] = 0.8 + r() * 0.25; }
        const id = float(instanceIndex);
        const h1 = hash(id.mul(1.37).add(0.11)), h2 = hash(id.mul(2.71).add(0.37)), h3 = hash(id.mul(3.33).add(0.59)),
            h4 = hash(id.mul(4.91).add(0.73)), h5 = hash(id.mul(6.17).add(0.19));
        const period = h1.mul(7.0).add(9.0);
        const ph = fract(U.time.div(period).add(h2));
        const top = float(23.0), bottom = float(0.4);
        const xa = h3.sub(0.5).mul(24.0), z0 = h4.mul(15.0).sub(8.0);        // never near the wide camera's lens
        const inLip = step(abs(xa), 2.6).mul(step(-1.0, z0)).mul(step(z0, 7.0));          // nor through the lip shot
        const x0 = xa.add(select(xa.greaterThan(0.0), float(3.0), float(-3.0)).mul(inLip));
        const size = h5.mul(h5).mul(0.7).add(0.28);
        const sway = U.wind.mul(1.6).add(0.5);
        const cx2 = x0.add(sin(U.time.mul(h1.mul(0.5).add(0.45)).add(h2.mul(6.28))).mul(sway)).add(U.wind.mul(ph).mul(3.0));
        const cz2 = z0.add(cos(U.time.mul(h3.mul(0.4).add(0.35)).add(h4.mul(6.28))).mul(sway.mul(0.7)));
        const cy2 = mix(top, bottom, ph);
        // tumbling: rotate about X then Z by time-varying angles
        const ax = U.time.mul(h2.mul(2.2).add(0.6)).add(h5.mul(6.28)), az = U.time.mul(h4.mul(1.6).add(0.4)).add(h1.mul(6.28));
        const rot = (v) => {
            const y1 = v.y.mul(cos(ax)).sub(v.z.mul(sin(ax))), z1 = v.y.mul(sin(ax)).add(v.z.mul(cos(ax)));
            const x2 = v.x.mul(cos(az)).sub(y1.mul(sin(az))), y2 = v.x.mul(sin(az)).add(y1.mul(cos(az)));
            return vec3(x2, y2, z1);
        };
        const fade = smoothstep(0.0, 0.05, ph).mul(float(1.0).sub(smoothstep(0.93, 1.0, ph)));
        const pos = Fn(() => {
            normalLocal.assign(rot(normalGeometry));
            return rot(positionGeometry.mul(size.mul(fade))).add(vec3(cx2, cy2, cz2));
        })();
        const fm = sheetMat({ position: pos });
        const mesh = new THREE.InstancedMesh(geo, fm, NF);
        geo.setAttribute('aCell', new THREE.InstancedBufferAttribute(cell, 1));
        geo.setAttribute('aShade', new THREE.InstancedBufferAttribute(shade, 1));
        for (let i = 0; i < NF; i++) mesh.setMatrixAt(i, new THREE.Matrix4());
        mesh.frustumCulled = false;
        mesh.name = 'bin:falling';
        group.add(mesh);
    }

    // ─────────────── the mark: she rises out of the bin ───────────────
    const mark = new THREE.Object3D(); mark.name = 'bin:mark';
    group.add(mark);
    // the path: from the low back of the slope inside the can up to its brim at the front, standing on the paper
    const focal = new THREE.Object3D(); focal.name = 'bin:focal';
    focal.position.set(0, H + 0.9, R - 0.2);
    group.add(focal);

    // ─────────────── light ───────────────
    let parts_lamp = null;
    const lights = new THREE.Group(); lights.name = 'bin:lights';
    const L = {};
    if (opts.lights !== false) {
        L.hemi = new THREE.HemisphereLight(0x1a2742, 0x030306, 0.12);
        L.birth = new THREE.SpotLight(0xdfe8ff, 320, 40, 15 * D2R, 0.55, 2);      // the cold white pool on the lip
        L.birth.position.set(2.0, H + 11, 7.5); L.birth.target.position.set(0, H + 0.4, 0.4);
        L.magenta = new THREE.DirectionalLight(0xff4fd8, 0.9); L.magenta.position.set(-14, 8, -10);   // rims, from behind
        L.cyan = new THREE.DirectionalLight(0x29e7ff, 0.75); L.cyan.position.set(14, 6, -8);
        L.sodium = new THREE.PointLight(0xff8a3d, 55, 16, 2); L.sodium.position.set(5.2, 6.6, 8.6);      // the street lamp's pool
        L.rim = new THREE.SpotLight(0xbfe6ff, 420, 30, 20 * D2R, 0.7, 2);                                 // the can's silhouette, from behind
        L.rim.position.set(-1.5, H + 6.5, -9.5); L.rim.target.position.set(0, H - 1.0, 1.0);
        L.inside = new THREE.PointLight(0xffc98a, 18, 7, 2); L.inside.position.set(0, yFill + 0.5, -0.3);  // born inside it
        L.fill = new THREE.DirectionalLight(0x5a4cc0, 0.3); L.fill.position.set(2, 5, 20);
        L.pages = new THREE.SpotLight(0xe8ecff, 140, 14, 26 * D2R, 0.8, 2);                               // the pages at her feet
        L.pages.position.set(-3.0, 6.5, R + 5.0); L.pages.target.position.set(0.2, 0.8, R + 1.6);
        for (const l of Object.values(L)) { lights.add(l); if (l.target) lights.add(l.target); }
        group.add(lights);
    }
    const base = Object.fromEntries(Object.entries(L).map(([k, l]) => [k, l.intensity]));
    // the street lamp (Balla's Street Light, 1909): a leaning pole sunk in the paper, its sodium head over the canyon
    {
        const lamp = new THREE.Group(); lamp.name = 'bin:lamp';
        const steel = own(new THREE.MeshStandardNodeMaterial({ roughness: 0.55, metalness: 0.85 }));
        steel.colorNode = mix(vec3(0.05, 0.055, 0.06), vec3(0.16, 0.08, 0.04), T.mx_noise_float(positionLocal.mul(2.5)).mul(0.5).add(0.5));
        const pole = new THREE.Mesh(own(new THREE.CylinderGeometry(0.09, 0.13, 8.2, 12)), steel);
        pole.position.set(0, 4.1, 0);
        const arm = new THREE.Mesh(own(new THREE.CylinderGeometry(0.06, 0.06, 1.9, 8)), steel);
        arm.rotation.z = Math.PI / 2 - 0.25; arm.position.set(-0.85, 8.05, 0);
        const head = new THREE.Mesh(own(new THREE.BoxGeometry(0.9, 0.22, 0.42)), steel);
        head.position.set(-1.75, 7.92, 0); head.rotation.z = -0.25;
        const bulbM = own(new THREE.MeshBasicNodeMaterial());
        bulbM.colorNode = vec3(1.0, 0.55, 0.22).mul(U.glow.mul(0).add(6.0));
        const bulb = new THREE.Mesh(own(new THREE.BoxGeometry(0.7, 0.05, 0.3)), bulbM);
        bulb.position.set(-1.75, 7.79, 0); bulb.rotation.z = -0.25;
        lamp.add(pole, arm, head, bulb);
        lamp.position.set(6.9, heapHeight(6.9, 8.6, R) - 1.6, 8.6);
        lamp.rotation.set(0.0, 0.0, 0.16);
        group.add(lamp);
        lamp.updateMatrixWorld(true);
        if (L.sodium) L.sodium.position.copy(bulb.getWorldPosition(new THREE.Vector3())).add(new THREE.Vector3(0, -0.35, 0));
        parts_lamp = lamp;
    }

    // ─────────────── sky: night over the dump, a far city glow beyond the cliff ───────────────
    if (opts.sky !== false) {
        const sky = new THREE.Mesh(own(new THREE.SphereGeometry(420, 48, 24)), own(new THREE.MeshBasicNodeMaterial({ side: THREE.BackSide, fog: false })));
        sky.material.colorNode = Fn(() => {
            const d = normalize(positionWorld.sub(T.cameraPosition));
            const glow = smoothstep(0.35, -0.05, d.y).mul(smoothstep(0.2, -0.9, d.z));
            const c0 = mix(vec3(0.010, 0.012, 0.03), vec3(0.002, 0.002, 0.006), smoothstep(0.0, 0.6, d.y));
            return c0.add(mix(vec3(0.16, 0.035, 0.12), vec3(0.22, 0.09, 0.03), smoothstep(-0.3, 0.3, d.x)).mul(glow).mul(0.6));
        })();
        sky.name = 'bin:sky';
        group.add(sky);
    }

    const parts = { lamp: parts_lamp, mark, focal, bin: binGroup, can: body, lid, toppled: can2, paper, lights: L, uniforms: U, R, H, yFill, fillY,
        pageAtlas: atlas, pageGrid: { cols: COLS, rows: ROWS, kinds: PAGES.PAGE_KINDS.slice(0, NCELL) },   // for the wardrobe's paper scraps
        fog: { color: 0x070a14, density: 0.03 } };

    function update(t, state = {}) {
        U.time.value = t;
        const c = clamp01(state.climb ?? 0);
        // inside → shoulders over the lip (c ≈ 0.5) → a step forward onto the front lip
        const z = lerp(Z_IN, Z_OUT, smooth(0, 1, c));
        mark.position.set(0, fillY(0, z) + 0.03, z);
        mark.rotation.set(0, 0, 0);
        if (state.wind != null) U.wind.value = state.wind;
        const hush = clamp01(state.hush ?? 0);
        const glow = state.glow ?? 1;
        if (L.inside) L.inside.intensity = base.inside * glow * (0.85 + 0.15 * Math.sin(t * 7.1) * Math.sin(t * 3.3));
        for (const k of ['magenta', 'cyan', 'sodium', 'rim']) if (L[k]) L[k].intensity = base[k] * (1 - 0.6 * hush);
    }
    update(BRIDGE.t0, {});

    return {
        group, parts, update, cams,
        focalPoint(v = new THREE.Vector3()) { focal.updateWorldMatrix(true, false); return focal.getWorldPosition(v); },
        dispose() { for (const x of owned) x.dispose?.(); group.removeFromParent(); },
    };
}

// stickers on the can: a 4x2 atlas of 512px cells — vinyl signs, a stencil, a spray tag, a wheat-pasted poster.
// All text invented and generic.
function drawStickers(g) {
    const C = 512;
    g.clearRect(0, 0, 2048, 1024);
    const cell = (k, fn) => { g.save(); g.translate((k % 4) * C, Math.floor(k / 4) * C); g.beginPath(); g.rect(0, 0, C, C); g.clip(); fn(); g.restore(); };
    const r = rng(77);
    // 0 NO DUMPING (w 1.25 x h 0.86 m)
    cell(0, () => {
        g.fillStyle = '#f2efe8'; g.fillRect(14, 70, C - 28, C - 140);
        g.fillStyle = '#c3242b'; g.fillRect(14, 70, C - 28, 120);
        g.fillStyle = '#fff'; g.font = '92px "UF Anton"'; g.textAlign = 'center'; g.fillText('NO DUMPING', C / 2, 165);
        g.fillStyle = '#16120f'; g.font = '40px "UF Archivo Black"'; g.fillText('OF ANY KIND', C / 2, 268);
        g.font = '28px "UF Space Mono"'; g.fillText('violators will be heard', C / 2, 330); g.fillText('but not answered', C / 2, 366);
        g.strokeStyle = '#16120f'; g.lineWidth = 6; g.strokeRect(20, 76, C - 40, C - 152);
    });
    // 1 KEEP LID CLOSED (yellow/black)
    cell(1, () => {
        g.fillStyle = '#ecc31f'; g.fillRect(10, 170, C - 20, 172);
        g.fillStyle = '#121212'; g.font = '82px "UF Bungee"'; g.textAlign = 'center'; g.fillText('KEEP LID', C / 2, 250);
        g.fillText('CLOSED', C / 2, 330);
    });
    // 2 hazard band
    cell(2, () => {
        g.fillStyle = '#e8c21e'; g.fillRect(0, 200, C, 112);
        g.fillStyle = '#121212';
        for (let x = -120; x < C + 120; x += 64) { g.beginPath(); g.moveTo(x, 312); g.lineTo(x + 32, 312); g.lineTo(x + 32 + 112, 200); g.lineTo(x + 112, 200); g.closePath(); g.fill(); }
    });
    // 3 stencil "BIN 01" (spray paint through a stencil: soft overspray, bridges in the letters)
    cell(3, () => {
        g.fillStyle = 'rgba(240,236,224,0.25)'; g.font = '190px "UF Black Ops"'; g.textAlign = 'center';
        g.shadowColor = 'rgba(240,236,224,0.8)'; g.shadowBlur = 14; g.fillText('BIN 01', C / 2, 330);
        g.shadowBlur = 0; g.fillStyle = '#eeeae0'; g.fillText('BIN 01', C / 2, 330);
    });
    // 4 a magenta spray tag (an illegible flourish and a ≠)
    cell(4, () => {
        g.strokeStyle = '#ff3fa4'; g.lineCap = 'round'; g.lineJoin = 'round';
        g.shadowColor = 'rgba(255,63,164,0.8)'; g.shadowBlur = 10;
        for (let s = 0; s < 3; s++) {
            g.lineWidth = 22 - s * 6; g.beginPath();
            let x = 40, y = 300;
            g.moveTo(x, y);
            for (let i = 0; i < 9; i++) { x += 48; g.quadraticCurveTo(x - 30, y - 160 + r() * 80, x, 260 + r() * 90); }
            g.stroke();
        }
        g.lineWidth = 16; g.beginPath(); g.moveTo(140, 400); g.lineTo(380, 400); g.moveTo(140, 450); g.lineTo(380, 450); g.moveTo(320, 360); g.lineTo(200, 490); g.stroke();
        g.shadowBlur = 0;
        g.fillStyle = 'rgba(255,63,164,0.85)';
        for (let i = 0; i < 6; i++) g.fillRect(70 + r() * 360, 310 + r() * 40, 5, 60 + r() * 120);       // drips
    });
    // 5 a wheat-pasted poster, peeling: THE FUTURE (torn)
    cell(5, () => {
        g.fillStyle = '#e9e2cf'; g.beginPath(); g.moveTo(40, 10); g.lineTo(470, 22); g.lineTo(480, 380); g.lineTo(430, 420); g.lineTo(450, 500); g.lineTo(30, 500); g.closePath(); g.fill();
        g.fillStyle = '#16120f'; g.font = '120px "UF Anton"'; g.textAlign = 'center'; g.fillText('THE', C / 2, 150); g.fillText('FUTURE', C / 2, 280);
        g.fillStyle = '#c42a2c'; g.font = '50px "UF Alfa Slab"'; g.fillText('IS NOT YET', C / 2, 360);
        g.fillStyle = 'rgba(0,0,0,0.18)'; g.fillRect(30, 440, 450, 60);
    });
    // 6 a round sticker
    cell(6, () => {
        g.fillStyle = '#2a63c9'; g.beginPath(); g.arc(C / 2, C / 2, 230, 0, 6.283); g.fill();
        g.fillStyle = '#fff'; g.font = '62px "UF Archivo Black"'; g.textAlign = 'center'; g.fillText('PROPERTY', C / 2, 230);
        g.font = '44px "UF Space Mono Bold"'; g.fillText('OF THE', C / 2, 290); g.font = '70px "UF Archivo Black"'; g.fillText('PUBLIC', C / 2, 360);
    });
    // 7 a warning label
    cell(7, () => {
        g.fillStyle = '#f4f2ee'; g.fillRect(10, 150, C - 20, 210);
        g.fillStyle = '#121212'; g.beginPath(); g.moveTo(90, 180); g.lineTo(160, 320); g.lineTo(20, 320); g.closePath(); g.fill();
        g.fillStyle = '#f4f2ee'; g.fillRect(84, 220, 12, 60); g.fillRect(84, 290, 12, 14);
        g.fillStyle = '#121212'; g.font = '50px "UF Archivo Black"'; g.textAlign = 'left'; g.fillText('CONTENTS', 180, 240);
        g.font = '30px "UF Space Mono Bold"'; g.fillText('MAY SPEAK', 180, 290); g.fillText('HANDLE WITH CARE', 180, 330);
    });
}
