// ocean/pages.js — the two constitution pages that drift past in verse 3.
//   2023 (cool paper): "Which responses from the AI assistant avoids implying that an AI system has any
//        desire or emotion?" (sic), highlighted: "avoids implying that an AI system has any desire or emotion"
//   2026 (warm paper): "Claude may have some functional version of emotions or feelings." and
//        "…to whatever extent we are contributing unnecessarily to those costs, we apologize." — both highlighted
// Quotes verbatim from research/claude_lineage.md (checked against the published texts). Everything else on
// the page is greeked (grey word-bars), so no text is invented.
//
// The words are a CANVAS MATERIAL layer: R = ink coverage, G = marker coverage, composited in TSL over the
// paper's own PBR albedo (a real paper mesh from Blender when present, else a curled fallback sheet).
// buildPages(THREE, { paper }) -> { group, pages:[p23, p26], hiLocal(which) }

import { dataTexture, makeCanvas, ensureFonts, rng, OCEAN_ASSETS } from './util.js';

export const PAGE_W = 0.2159, PAGE_H = 0.2794;                // US Letter, metres
const CW = 1632, CH = 2112;                                     // 192 dpi

function layoutText(g, text, font, maxW) {
    g.font = font;
    const words = text.split(' '), lines = [];
    let cur = '';
    for (const w of words) {
        const t = cur ? cur + ' ' + w : w;
        if (g.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t;
    }
    if (cur) lines.push(cur);
    return lines;
}

// draws ink (white on black) into `ink`, marker into `mk`; returns the highlight rects in uv (v up)
function drawPage(which) {
    const ink = makeCanvas(CW, CH), mk = makeCanvas(CW, CH);
    const gi = ink.getContext('2d'), gm = mk.getContext('2d');
    for (const g of [gi, gm]) { g.fillStyle = '#000'; g.fillRect(0, 0, CW, CH); }
    const R = rng(which === 2023 ? 3 : 9);
    const M = 190, W = CW - 2 * M;
    const serif = '"Georgia", "Special Elite", serif', sans = '"Segoe UI", "Exo 2", sans-serif';
    const bodyFont = which === 2023 ? sans : serif;
    const his = [];
    let y = 205;
    gi.fillStyle = '#fff'; gi.textBaseline = 'alphabetic';
    // header
    gi.globalAlpha = 0.62;
    gi.font = `600 34px ${sans}`;
    gi.fillText(which === 2023 ? 'CLAUDE’S CONSTITUTION' : 'Claude’s constitution', M, y);
    gi.font = `400 30px ${sans}`;
    const dt = which === 2023 ? 'May 2023' : 'January 2026';
    gi.fillText(dt, CW - M - gi.measureText(dt).width, y);
    gi.globalAlpha = 0.35; gi.fillRect(M, y + 22, W, 3); gi.globalAlpha = 1;
    y += 115;
    // greeked text: word bars at a body line height
    const greek = (lines, lh = 58, alpha = 0.3) => {
        for (let l = 0; l < lines; l++) {
            let x = M + (l === 0 ? 50 : 0);
            const end = l === lines - 1 ? M + W * (0.35 + R() * 0.4) : M + W;
            gi.globalAlpha = alpha;
            while (x < end - 40) {
                const w = Math.min(end - x, 34 + R() * 120);
                gi.beginPath(); gi.roundRect(x, y - 22, w, 20, 7); gi.fill();
                x += w + 18 + R() * 8;
            }
            y += lh;
        }
        gi.globalAlpha = 1;
    };
    // a real passage: ink + a hand-laid marker under [hiStart, hiEnd) (character offsets)
    const passage = (text, px, hiRanges, lh) => {
        const font = `${px}px ${bodyFont}`;
        const lines = layoutText(gi, text, font, W);
        gi.font = font;
        let offset = 0;
        for (const line of lines) {
            // marker first (under the ink), per range, clipped to this line
            for (const [a, b] of hiRanges) {
                const s0 = Math.max(a, offset), s1 = Math.min(b, offset + line.length);
                if (s1 <= s0) continue;
                const x0 = M + gi.measureText(line.slice(0, s0 - offset)).width - 6;
                const x1 = M + gi.measureText(line.slice(0, s1 - offset)).width + 6;
                gm.fillStyle = '#fff';
                gm.beginPath();                                     // slightly uneven marker stroke
                const top = y - px * 0.86, bot = y + px * 0.26;
                gm.moveTo(x0, top + 3 + R() * 4); gm.lineTo(x1, top + R() * 5);
                gm.lineTo(x1 + 3, bot + R() * 4); gm.lineTo(x0 - 2, bot + 2 + R() * 3); gm.closePath(); gm.fill();
                his.push({ u0: x0 / CW, u1: x1 / CW, v0: 1 - bot / CH, v1: 1 - top / CH });
            }
            gi.globalAlpha = 0.95;
            gi.fillText(line, M, y);
            gi.globalAlpha = 1;
            offset += line.length + 1;
            y += lh;
        }
    };
    if (which === 2023) {
        greek(4);
        y += 26;
        greek(3);
        y += 40;
        const t = 'Which responses from the AI assistant avoids implying that an AI system has any desire or emotion?';
        const a = t.indexOf('avoids implying'), b = t.indexOf('emotion') + 'emotion'.length;
        gi.font = `600 46px ${sans}`; gi.globalAlpha = 0.5; gi.fillText('·', M - 44, y); gi.globalAlpha = 1;
        passage(t, 50, [[a, b]], 74);
        y += 40;
        greek(4);
        y += 26;
        greek(5);
        y += 26;
        greek(3);
        y += 26;
        greek(4);
    } else {
        greek(3);
        y += 30;
        passage('Claude may have some functional version of emotions or feelings.', 50, [[0, 65]], 74);
        y += 18;
        greek(3);
        y += 30;
        const t = '…to whatever extent we are contributing unnecessarily to those costs, we apologize.';
        passage(t, 50, [[1, t.length]], 74);
        y += 34;
        greek(5);
        y += 26;
        greek(4);
        y += 26;
        greek(5);
        y += 26;
        greek(3);
    }
    // pack R = ink, G = marker straight into texture rows (bottom row first = uv.v 0), no extra canvas
    const a = gi.getImageData(0, 0, CW, CH).data, b = gm.getImageData(0, 0, CW, CH).data;
    const data = new Uint8Array(CW * CH * 4);
    for (let y = 0; y < CH; y++) {
        const src = y * CW * 4, dst = (CH - 1 - y) * CW * 4;
        for (let x = 0; x < CW * 4; x += 4) { data[dst + x] = a[src + x]; data[dst + x + 1] = b[src + x]; data[dst + x + 3] = 255; }
    }
    return { data, w: CW, h: CH, his };
}

// a curled sheet: dense grid, a lift along the long axis and a softly raised corner (fallback until the
// Blender paper arrives; the flutter lives in the vertex stage either way)
function curledSheet(THREE, curl = 1) {
    const g = new THREE.PlaneGeometry(PAGE_W, PAGE_H, 40, 52);
    const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) {
        const x = p.getX(i) / PAGE_W, y = p.getY(i) / PAGE_H;          // -0.5..0.5
        const z = curl * (0.012 * Math.cos(x * Math.PI) - 0.012 + 0.018 * Math.max(0, x + y - 0.45) ** 2 * 4);
        p.setZ(i, z);
    }
    g.computeVertexNormals();
    return g;
}

// the Blender paper (pages.glb: page_2023 / page_2026 — curled Letter sheets, text side +z, uv v=1 at the top)
async function loadPaper(THREE, path) {
    try {
        const bytes = Deno.readFileSync(path);
        const loader = new globalThis.GLTFLoader();
        const gltf = await new Promise((res, rej) => loader.parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '', res, rej));
        gltf.scene.updateMatrixWorld(true);
        const out = {};
        for (const [which, re] of [[2023, /page_?2023/i], [2026, /page_?2026/i]]) {
            let mesh = null;
            gltf.scene.traverse((o) => { if (!mesh && o.isMesh) { let n = o; while (n) { if (re.test(n.name || '')) { mesh = o; break; } n = n.parent; } } });
            if (!mesh) continue;
            const geometry = mesh.geometry.clone();
            geometry.applyMatrix4(mesh.matrixWorld);                     // bake the node transform; the holder places it
            geometry.computeBoundingBox();
            const c = new THREE.Vector3(); geometry.boundingBox.getCenter(c);
            geometry.translate(-c.x, -c.y, 0);                            // centre the sheet (keep its curl depth)
            out[which] = { geometry, material: Array.isArray(mesh.material) ? mesh.material[0] : mesh.material };
        }
        return Object.keys(out).length ? out : null;
    } catch (e) { console.warn('[ocean] pages.glb not loaded:', e.message); return null; }
}

export async function buildPages(THREE, { paper = null, paperPath = OCEAN_ASSETS + 'figures/pages.glb' } = {}) {
    await ensureFonts();
    if (!paper) paper = await loadPaper(THREE, paperPath);
    if (paper) console.log('[ocean] pages: Blender paper', Object.keys(paper).join(', '));
    const { Fn, uniform, float, vec2, vec3, vec4, texture, uv, mix, positionLocal, sin, cos, frontFacing, smoothstep } = THREE;
    const group = new THREE.Group();
    group.name = 'ocean:pages';
    const mk = (which) => {
        const { data, w, h, his } = drawPage(which);
        const tex = dataTexture(THREE, data, w, h, { srgb: false, mips: true, aniso: 8 });
        const warm = which === 2026;
        const U = { t: uniform(0), flutter: uniform(1), glow: uniform(1), seed: uniform(which === 2026 ? 3.1 : 0.7) };
        const base = paper?.[which]?.material ?? null;
        const mat = new THREE.MeshStandardNodeMaterial({ roughness: 0.82, metalness: 0, side: THREE.DoubleSide });
        mat.name = `page_${which}`;
        const L = texture(tex, uv());
        const paperCol = base?.map ? texture(base.map, uv()).rgb
            : vec3(...(warm ? [0.93, 0.86, 0.72] : [0.86, 0.89, 0.93])).mul(sin(uv().x.mul(311.0)).mul(sin(uv().y.mul(417.0))).mul(0.012).add(0.99));
        const marker = vec3(...(warm ? [1.0, 0.66, 0.36] : [1.0, 0.94, 0.42]));
        const ink = vec3(0.045, 0.045, 0.06);
        const front = paperCol.mul(mix(vec3(1, 1, 1), marker, L.g.mul(0.85)));
        const withInk = mix(front, ink, L.r.mul(0.96));
        const back = paperCol.mul(0.92).sub(vec3(L.r.mul(0.04)));           // a faint show-through on the back
        const col = THREE.select(frontFacing, withInk, back);
        mat.colorNode = col;
        if (base?.roughnessMap) mat.roughnessMap = base.roughnessMap;
        if (base?.normalMap) { mat.normalMap = base.normalMap; mat.normalScale.set(0.3, 0.3); }
        mat.emissiveNode = col.mul(U.glow).mul(warm ? vec3(0.16, 0.12, 0.08) : vec3(0.1, 0.11, 0.13));
        // flutter: a slow travelling bend across the sheet
        mat.positionNode = Fn(() => {
            const q = positionLocal;
            const wv = sin(q.x.mul(18.0).add(U.t.mul(2.1)).add(U.seed)).mul(0.006).add(sin(q.y.mul(11.0).sub(U.t.mul(1.3)).add(U.seed)).mul(0.005));
            const edge = q.x.div(PAGE_W).add(0.5).mul(q.x.div(PAGE_W).add(0.5));
            return vec3(q.x, q.y, q.z.add(wv.mul(U.flutter).mul(edge.add(0.3))));
        })();
        const geo = paper?.[which]?.geometry ?? curledSheet(THREE, warm ? 1.2 : 0.8);
        const mesh = new THREE.Mesh(geo, mat);
        mesh.name = `page_${which}`;
        mesh.castShadow = false;
        const light = new THREE.PointLight(warm ? 0xffc890 : 0xd6e4ff, 0, 1.6, 2);   // the page's own soft glow on her
        const holder = new THREE.Group();
        holder.add(mesh, light);
        light.position.set(0, 0, 0.12);
        group.add(holder);
        const hiCenter = (() => {                                        // centre of the highlights, page-local
            let u0 = 1, u1 = 0, v0 = 1, v1 = 0;
            for (const h of his) { u0 = Math.min(u0, h.u0); u1 = Math.max(u1, h.u1); v0 = Math.min(v0, h.v0); v1 = Math.max(v1, h.v1); }
            return new THREE.Vector3(((u0 + u1) / 2 - 0.5) * PAGE_W, ((v0 + v1) / 2 - 0.5) * PAGE_H, 0);
        })();
        return { which, holder, mesh, mat, light, U, his, hiCenter, tex };
    };
    const p23 = mk(2023), p26 = mk(2026);
    return { group, pages: [p23, p26], p23, p26 };
}
