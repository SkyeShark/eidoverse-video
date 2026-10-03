// interiors_lib.js — shared helpers for the two UNKNOWN FORCE interiors (quiet_room.js, showroom.js).
//
// Canvas art is drawn with @napi-rs/canvas (Skia) and uploaded as DataTextures with CPU-built mip chains (the
// stack's automatic mip pass is unreliable; explicit levels work — same recipe as the DAISY voice machines).
// Tiling PBR sets are AmbientCG CC0 from the shared texture library (acg() below; globalThis.fetchPBR fetches an ID
// once, on first use).
// Everything here is deterministic: seeded RNG only, no Date, no Math.random.

export const fsPath = (u) => { const p = decodeURIComponent(u.pathname); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; };
export const FONT_DIR = fsPath(new URL('../../../eidoverse/assets/fonts/', import.meta.url));

export const clamp01 = (x) => Math.max(0, Math.min(1, x));
export const smooth = (x) => { x = clamp01(x); return x * x * (3 - 2 * x); };
export const lerp = (a, b, k) => a + (b - a) * k;
export const ramp = (x, a, b) => clamp01((x - a) / (b - a));

// mulberry32
export function rng(seed) {
    let a = seed >>> 0;
    return () => {
        a = (a + 0x6D2B79F5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

// ------------------------------------------------------------------------------------------------ canvas + fonts
let _napi = null;
export async function napi() {
    if (_napi) return _napi;
    _napi = await import('npm:@napi-rs/canvas@0.1.69');
    const F = FONT_DIR;
    const reg = (file, fam) => { try { _napi.GlobalFonts.registerFromPath(F + file, fam); } catch (e) { console.warn('[interiors] font', file, e.message); } };
    reg('Kalam-Bold.ttf', 'UF Kalam Bold');
    reg('Kalam-Regular.ttf', 'UF Kalam');
    reg('CaveatBrush-Regular.ttf', 'UF Caveat Brush');
    reg('SpecialElite-Regular.ttf', 'UF Special Elite');
    reg('BlackOpsOne-Regular.ttf', 'UF Black Ops');
    reg('Rajdhani-Bold.ttf', 'UF Rajdhani');
    reg('Michroma-Regular.ttf', 'UF Michroma');
    reg('ShareTechMono-Regular.ttf', 'UF Mono');
    reg('Orbitron.ttf', 'UF Orbitron');
    reg('Exo2.ttf', 'UF Exo');
    return _napi;
}
export function canvas(N, w, h) { const c = N.createCanvas(w, h); return [c, c.getContext('2d')]; }

// 2x2 box mip chain (alphaWeighted keeps transparent texels from darkening decal edges)
export function buildMips(data, w, h, alphaWeighted = false) {
    const levels = [{ data, width: w, height: h }];
    let sw = w, sh = h, src = data;
    while (sw > 1 || sh > 1) {
        const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1);
        const dst = new Uint8Array(dw * dh * 4);
        for (let y = 0; y < dh; y++) {
            const r0 = Math.min(sh - 1, y * 2) * sw, r1 = Math.min(sh - 1, y * 2 + 1) * sw;
            for (let x = 0; x < dw; x++) {
                const c0 = Math.min(sw - 1, x * 2), c1 = Math.min(sw - 1, x * 2 + 1);
                const a = (r0 + c0) * 4, b = (r0 + c1) * 4, c = (r1 + c0) * 4, d = (r1 + c1) * 4, o = (y * dw + x) * 4;
                if (alphaWeighted) {
                    const wa = src[a + 3], wb = src[b + 3], wc = src[c + 3], wd = src[d + 3], ws = wa + wb + wc + wd;
                    for (let k = 0; k < 3; k++) {
                        dst[o + k] = ws > 0
                            ? Math.round((src[a + k] * wa + src[b + k] * wb + src[c + k] * wc + src[d + k] * wd) / ws)
                            : (src[a + k] + src[b + k] + src[c + k] + src[d + k] + 2) >> 2;
                    }
                    dst[o + 3] = (ws + 2) >> 2;
                } else {
                    for (let k = 0; k < 4; k++) dst[o + k] = (src[a + k] + src[b + k] + src[c + k] + src[d + k] + 2) >> 2;
                }
            }
        }
        levels.push({ data: dst, width: dw, height: dh });
        sw = dw; sh = dh; src = dst;
    }
    return levels;
}

// RGBA8 rows (row 0 = TOP of the picture, canvas order) -> DataTexture. Rows are flipped so the picture's top lands at
// v = 1 on three.js UVs (PlaneGeometry reads upright; texture(tex, uv()) needs no flip).
export function dataTexture(THREE, rgba, w, h, o = {}) {
    const { srgb = true, mips = true, repeat = false, alphaWeighted = false, flip = true } = o;
    let data = rgba;
    if (flip) {
        const row = w * 4;
        data = new Uint8Array(w * h * 4);
        for (let y = 0; y < h; y++) data.set(rgba.subarray((h - 1 - y) * row, (h - y) * row), y * row);
    }
    const tex = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
    tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    tex.wrapS = tex.wrapT = repeat ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
    tex.magFilter = THREE.LinearFilter;
    tex.minFilter = mips ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
    tex.generateMipmaps = false;
    tex.anisotropy = 8;
    tex.flipY = false;
    tex.userData.noMips = true;           // the engine must not build a second chain
    if (mips) tex.mipmaps = buildMips(data, w, h, alphaWeighted);
    tex.needsUpdate = true;
    return tex;
}
export function canvasTexture(THREE, cv, o = {}) {
    const w = cv.width, h = cv.height;
    const src = cv.getContext('2d').getImageData(0, 0, w, h).data;
    return dataTexture(THREE, new Uint8Array(src.buffer, src.byteOffset, src.byteLength), w, h, o);
}
// per-pixel derived map (e.g. roughness from an albedo canvas): fn(r,g,b,a,x,y) -> [r,g,b] 0..255
export function derivedTexture(THREE, cv, fn, o = {}) {
    const w = cv.width, h = cv.height;
    const src = cv.getContext('2d').getImageData(0, 0, w, h).data;
    const out = new Uint8Array(w * h * 4);
    for (let y = 0, i = 0; y < h; y++) for (let x = 0; x < w; x++, i += 4) {
        const v = fn(src[i], src[i + 1], src[i + 2], src[i + 3], x, y);
        out[i] = v[0]; out[i + 1] = v[1]; out[i + 2] = v[2]; out[i + 3] = 255;
    }
    return dataTexture(THREE, out, w, h, { srgb: false, ...o });
}

// ------------------------------------------------------------------------------------------------ PBR sets
const _texCache = new Map();
async function loadTex(THREE, path, srgb) {
    const key = path + '|' + srgb;
    if (_texCache.has(key)) return _texCache.get(key);
    let b = null;
    try { b = Deno.readFileSync(path); } catch (e) { console.warn('[interiors] missing texture', path); }
    const t = b ? await globalThis.loadImageTexture(b, { srgb }) : null;
    if (t) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; }
    _texCache.set(key, t);
    return t;
}
// the sets whose ambient-occlusion map the interiors read (the others are lit without it)
const WITH_AO = new Set(['Carpet012', 'Carpet013', 'CorrugatedSteel005']);
// a CC0 AmbientCG set (1k) by ID from the shared texture library (globalThis.fetchPBR: fetched once, on first use):
// { map, normalMap, roughnessMap, aoMap? }
export async function acg(THREE, id) {
    const { files: F } = await globalThis.fetchPBR(id, { res: '1k' });
    const out = {
        map: await loadTex(THREE, F.diff, true),
        normalMap: await loadTex(THREE, F.normal, false),
        roughnessMap: await loadTex(THREE, F.rough, false),
    };
    if (WITH_AO.has(id) && F.ao) out.aoMap = await loadTex(THREE, F.ao, false);
    for (const k of Object.keys(out)) if (!out[k]) delete out[k];
    return out;
}

// one shared tiling noise: 4 independent periodic fbm channels (R period 4, G 8, B 32, A 64 cells per tile)
export function noiseTexture(THREE) {
    const KEY = '__ufInteriorNoise_v1';
    if (globalThis[KEY]) return globalThis[KEY];
    const N = 256, data = new Uint8Array(N * N * 4);
    const chans = [[4, 5, 11], [8, 4, 23], [32, 3, 37], [64, 2, 53]];
    for (let ch = 0; ch < 4; ch++) {
        const [P, oct, seed] = chans[ch], r = rng(seed), lats = [];
        for (let o = 0; o < oct; o++) {
            const p = P << o, L = new Float32Array(p * p);
            for (let i = 0; i < L.length; i++) L[i] = r();
            lats.push([p, L]);
        }
        for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
            let v = 0, amp = 0.5, tot = 0;
            for (let o = 0; o < oct; o++) {
                const [p, L] = lats[o], fx = x / N * p, fy = y / N * p;
                const xi = Math.floor(fx), yi = Math.floor(fy), xf = fx - xi, yf = fy - yi;
                const X0 = xi % p, X1 = (xi + 1) % p, Y0 = (yi % p) * p, Y1 = ((yi + 1) % p) * p;
                const u = xf * xf * (3 - 2 * xf), w = yf * yf * (3 - 2 * yf);
                const a = L[Y0 + X0], b = L[Y0 + X1], c = L[Y1 + X0], d = L[Y1 + X1];
                v += amp * (a + (b - a) * u + (c - a) * w + (a - b - c + d) * u * w);
                tot += amp; amp *= 0.5;
            }
            data[(y * N + x) * 4 + ch] = Math.round(255 * v / tot);
        }
    }
    const tex = dataTexture(THREE, data, N, N, { srgb: false, repeat: true, flip: false });
    globalThis[KEY] = tex;
    return tex;
}

// ------------------------------------------------------------------------------------------------ geometry
// Box-projected UVs in metres (per-triangle dominant axis), on a NON-indexed copy. scale = tiles per metre factor.
export function boxUV(geo, scale = 1, offset = [0, 0, 0]) {
    const g = geo.index ? geo.toNonIndexed() : geo;
    const p = g.attributes.position;
    const n = p.count;
    const uv = new Float32Array(n * 2);
    const a = [0, 0, 0], b = [0, 0, 0], c = [0, 0, 0];
    for (let i = 0; i < n; i += 3) {
        for (let k = 0; k < 3; k++) { a[k] = p.getComponent(i, k); b[k] = p.getComponent(i + 1, k); c[k] = p.getComponent(i + 2, k); }
        const e1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], e2 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
        const nx = Math.abs(e1[1] * e2[2] - e1[2] * e2[1]), ny = Math.abs(e1[2] * e2[0] - e1[0] * e2[2]), nz = Math.abs(e1[0] * e2[1] - e1[1] * e2[0]);
        for (let v = 0; v < 3; v++) {
            const x = p.getX(i + v) + offset[0], y = p.getY(i + v) + offset[1], z = p.getZ(i + v) + offset[2];
            let u, w;
            if (nx >= ny && nx >= nz) { u = z; w = y; } else if (ny >= nz) { u = x; w = z; } else { u = x; w = y; }
            uv[(i + v) * 2] = u * scale; uv[(i + v) * 2 + 1] = w * scale;
        }
    }
    g.setAttribute('uv', new p.constructor(uv, 2));
    return g;
}

// keep only position/normal/uv, non-indexed: the common denominator for merging
export function clean(geo) {
    let g = geo.index ? geo.toNonIndexed() : geo;
    for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
    if (!g.attributes.normal) g.computeVertexNormals();
    if (!g.attributes.uv) {
        const n = g.attributes.position.count;
        g.setAttribute('uv', new g.attributes.position.constructor(new Float32Array(n * 2), 2));
    }
    return g;
}

// Merge the static meshes of `root` (recursively) into one mesh per material. Meshes flagged userData.keep stay.
// Returns the new meshes (already added under `root`).
export function mergeStatic(THREE, BGU, root, { shadows = true } = {}) {
    root.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(root.matrixWorld).invert();
    const buckets = new Map();
    const victims = [];
    root.traverse((o) => {
        if (!o.isMesh || o.isInstancedMesh || o.userData.keep || o === root) return;
        let p = o.parent, kept = false;
        while (p && p !== root) { if (p.userData.keep) { kept = true; break; } p = p.parent; }
        if (kept) return;
        const m = o.material;
        if (Array.isArray(m)) return;
        const g = clean(o.geometry.clone());
        g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld));
        if (!buckets.has(m)) buckets.set(m, { geos: [], cast: false, recv: false });
        const bk = buckets.get(m);
        bk.geos.push(g); bk.cast ||= o.castShadow; bk.recv ||= o.receiveShadow;
        victims.push(o);
    });
    for (const o of victims) o.parent.remove(o);
    const out = [];
    for (const [m, bk] of buckets) {
        const merged = BGU.mergeGeometries(bk.geos, false);
        if (!merged) { console.warn('[interiors] merge failed for', m.name); continue; }
        const mesh = new THREE.Mesh(merged, m);
        mesh.name = 'merged:' + (m.name || 'mat');
        mesh.castShadow = shadows && bk.cast; mesh.receiveShadow = bk.recv;
        root.add(mesh);
        out.push(mesh);
    }
    return out;
}

// ------------------------------------------------------------------------------------------------ environment
// An LDR equirect painted from a direction function paint(dx,dy,dz) -> [r,g,b] (0..1, sRGB). Memory row 0 = DOWN
// (three's equirect v = 0), so the picture needs no flip. Used as material.envMap (PMREM'd by the engine's
// EnvironmentNode) so every surface of the set reflects the SET's light, never the conductor's sky.
export function equirectEnv(THREE, W, H, paint) {
    const data = new Uint8Array(W * H * 4);
    for (let y = 0; y < H; y++) {
        const lat = ((y + 0.5) / H - 0.5) * Math.PI;
        const cl = Math.cos(lat), sl = Math.sin(lat);
        for (let x = 0; x < W; x++) {
            const phi = ((x + 0.5) / W - 0.5) * 2 * Math.PI;
            const c = paint(Math.cos(phi) * cl, sl, Math.sin(phi) * cl);
            const i = (y * W + x) * 4;
            data[i] = Math.round(clamp01(c[0]) * 255); data[i + 1] = Math.round(clamp01(c[1]) * 255);
            data[i + 2] = Math.round(clamp01(c[2]) * 255); data[i + 3] = 255;
        }
    }
    const tex = dataTexture(THREE, data, W, H, { srgb: true, flip: false });
    tex.mapping = THREE.EquirectangularReflectionMapping;
    tex.wrapS = THREE.RepeatWrapping;
    return tex;
}

// ------------------------------------------------------------------------------------------------ hand-drawn marker
// All coordinates in canvas px. r = rng(). Kalam Bold reads as a chisel marker; Caveat Brush as a fat bullet tip.
export function marker(ctx, text, x, y, o = {}) {
    const { size = 60, color = '#c3141e', font = 'UF Kalam Bold', rot = 0, r = rng(1), align = 'left', jit = 0.035,
        alpha = 0.93, track = 1.0 } = o;
    ctx.save();
    ctx.translate(x, y); ctx.rotate(rot);
    ctx.font = `${size}px "${font}"`;
    ctx.textBaseline = 'alphabetic';
    const w = ctx.measureText(text).width * track;
    let cx = align === 'center' ? -w / 2 : align === 'right' ? -w : 0;
    ctx.fillStyle = color;
    for (const ch of text) {
        const cw = ctx.measureText(ch).width * track;
        if (ch !== ' ') {
            ctx.save();
            ctx.translate(cx + (r() - 0.5) * size * jit, (r() - 0.5) * size * jit * 1.3);
            ctx.rotate((r() - 0.5) * 0.07);
            const a = alpha * (0.82 + 0.18 * r());
            ctx.globalAlpha = a; ctx.fillText(ch, 0, 0);
            ctx.globalAlpha = a * 0.3; ctx.fillText(ch, size * 0.012, size * 0.008);     // ink pooling on the stroke
            ctx.restore();
        }
        cx += cw * (0.97 + r() * 0.05);
    }
    ctx.restore();
    return w;
}
// a wobbly marker polyline (pts: [[x,y],...]); dashed = [on, off] px
export function mline(ctx, pts, o = {}) {
    const { w = 6, color = '#c3141e', r = rng(2), jit = 1.6, alpha = 0.92, dashed = null } = o;
    ctx.save();
    ctx.strokeStyle = color; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.globalAlpha = alpha;
    if (dashed) ctx.setLineDash(dashed);
    ctx.beginPath();
    for (let i = 0; i < pts.length - 1; i++) {
        const [x0, y0] = pts[i], [x1, y1] = pts[i + 1];
        const L = Math.hypot(x1 - x0, y1 - y0), n = Math.max(2, Math.round(L / 40));
        for (let k = 0; k <= n; k++) {
            if (i > 0 && k === 0) continue;
            const t = k / n;
            const px = x0 + (x1 - x0) * t + (k > 0 && k < n ? (r() - 0.5) * jit * 2 : 0);
            const py = y0 + (y1 - y0) * t + (k > 0 && k < n ? (r() - 0.5) * jit * 2 : 0);
            if (i === 0 && k === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
    }
    ctx.stroke();
    ctx.restore();
}
export function marrow(ctx, x0, y0, x1, y1, o = {}) {
    const { w = 6, head = 26 } = o;
    mline(ctx, [[x0, y0], [x1, y1]], o);
    const a = Math.atan2(y1 - y0, x1 - x0);
    for (const s of [-1, 1]) mline(ctx, [[x1, y1], [x1 - Math.cos(a + s * 0.45) * head, y1 - Math.sin(a + s * 0.45) * head]], { ...o, w: w * 0.95 });
}
// hand-drawn ellipse with an overshoot (the loop people draw around a number)
export function mring(ctx, cx, cy, rx, ry, o = {}) {
    const { r = rng(3), turns = 1.12 } = o;
    const pts = [];
    const a0 = r() * Math.PI * 2, n = 40;
    for (let i = 0; i <= n; i++) {
        const t = a0 + (i / n) * Math.PI * 2 * turns;
        const k = 1 + (r() - 0.5) * 0.06 + (i / n) * 0.05;
        pts.push([cx + Math.cos(t) * rx * k, cy + Math.sin(t) * ry * k]);
    }
    mline(ctx, pts, { ...o, jit: 0.6 });
}
// a whiteboard surface: enamel white with tonal blotches, erased GHOSTS of older writing and eraser swipes
export function boardBase(ctx, W, H, r, o = {}) {
    const { ghosts = [], tint = '#eceeea' } = o;
    ctx.fillStyle = tint; ctx.fillRect(0, 0, W, H);
    // faint tonal drift (a big sheet of enamel is never one value)
    for (let i = 0; i < 26; i++) {
        const x = r() * W, y = r() * H, rad = (0.15 + r() * 0.4) * Math.max(W, H);
        const g = ctx.createRadialGradient(x, y, 0, x, y, rad);
        const dark = r() < 0.6;
        g.addColorStop(0, dark ? `rgba(150,158,160,${0.03 + r() * 0.05})` : `rgba(255,255,255,${0.05 + r() * 0.06})`);
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    }
    // ghosts: earlier sessions' writing, mostly wiped (grey, red-grey)
    for (const gh of ghosts) {
        marker(ctx, gh.t, gh.x * W, gh.y * H, { size: gh.s * H, color: gh.c || '#7d8384', alpha: gh.a ?? 0.12, r, rot: gh.rot || 0, font: gh.f || 'UF Kalam Bold' });
    }
    // eraser swipes: long soft strokes that lift the ghosts unevenly and leave a haze
    ctx.save();
    for (let i = 0; i < 22; i++) {
        const x = r() * W, y = r() * H, len = (0.15 + r() * 0.35) * W, hh = (0.05 + r() * 0.06) * H, a = (r() - 0.5) * 0.5;
        ctx.save(); ctx.translate(x, y); ctx.rotate(a);
        const g = ctx.createLinearGradient(0, -hh, 0, hh);
        const al = 0.22 + r() * 0.3;
        g.addColorStop(0, 'rgba(236,238,234,0)'); g.addColorStop(0.5, `rgba(236,238,234,${al})`); g.addColorStop(1, 'rgba(236,238,234,0)');
        ctx.fillStyle = g; ctx.fillRect(-len / 2, -hh, len, hh * 2);
        // the swipe's own residue: faint grey streaks along it
        ctx.globalAlpha = 0.05 + r() * 0.05; ctx.strokeStyle = '#8f9596'; ctx.lineWidth = 1 + r() * 2;
        for (let k = 0; k < 6; k++) { const yy = (r() - 0.5) * hh * 1.6; ctx.beginPath(); ctx.moveTo(-len / 2, yy); ctx.lineTo(len / 2, yy + (r() - 0.5) * 6); ctx.stroke(); }
        ctx.restore();
    }
    ctx.restore();
}
// whiteboard roughness from the finished albedo: enamel is glossy, dry ink and eraser haze are matte
export function boardRoughness(THREE, cv, r, base = 0.16) {
    const W = cv.width, H = cv.height;
    // a low-frequency smudge field (fingerprints, wipe streaks)
    const cells = 24, field = new Float32Array((cells + 1) * (cells + 1));
    for (let i = 0; i < field.length; i++) field[i] = r();
    const f = (x, y) => {
        const fx = x / W * cells, fy = y / H * cells, xi = Math.floor(fx), yi = Math.floor(fy), xf = fx - xi, yf = fy - yi;
        const a = field[yi * (cells + 1) + xi], b = field[yi * (cells + 1) + xi + 1], c = field[(yi + 1) * (cells + 1) + xi], d = field[(yi + 1) * (cells + 1) + xi + 1];
        const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
        return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
    };
    return derivedTexture(THREE, cv, (R, G, B, A, x, y) => {
        const lum = (0.2126 * R + 0.7152 * G + 0.0722 * B) / 255;
        const sat = (Math.max(R, G, B) - Math.min(R, G, B)) / 255;
        const ink = clamp01((0.86 - lum) * 2.2 + sat * 0.8);
        const v = base + f(x, y) * 0.16 + ink * 0.38;
        const q = Math.round(clamp01(v) * 255);
        return [q, q, q];
    });
}

// ------------------------------------------------------------------------------------------------ material kit
// The recipe both interiors use: every material gets a unique program cache key (structurally identical node graphs
// otherwise alias to one pipeline and share texture bindings on this stack), the SET's own env map, and triplanar
// breakup of value and roughness from the shared noise — never a flat colour.
export function materialKit(THREE, { env, prefix = 'uf', track = (x) => x } = {}) {
    const { vec2, vec3, float, uv, texture, positionLocal, normalLocal, clamp, abs, max, normalMap } = THREE;
    const NOISE = noiseTexture(THREE);
    let id = 0;
    const tri = (scale) => {
        const p = positionLocal.mul(scale);
        const n = abs(normalLocal);
        const w = n.div(max(n.x.add(n.y).add(n.z), 1e-4));
        return texture(NOISE, p.yz).mul(w.x).add(texture(NOISE, p.xz).mul(w.y)).add(texture(NOISE, p.xy).mul(w.z));
    };
    const keyed = (m, name) => { const k = `${prefix}-${name}-${id++}`; m.customProgramCacheKey = () => k; m.name = name; track(m); return m; };
    const envd = (m, i = 1) => { if (env) { m.envMap = env; m.envMapIntensity = i; } return m; };
    function pbr(name, set, o = {}) {
        const { tint = [1, 1, 1], tile = 1, rough = 1, roughAdd = 0, metal = 0, nScale = 1, vary = 0.18, varyScale = 0.6,
            envI = 1, physical = false, extra = {} } = o;
        const M = physical ? THREE.MeshPhysicalNodeMaterial : THREE.MeshStandardNodeMaterial;
        const m = new M({ metalness: metal, roughness: 1, ...extra });
        const tuv = uv().mul(tile);
        const n = tri(varyScale);
        const base = set.map ? texture(set.map, tuv).rgb : vec3(1);
        m.colorNode = base.mul(vec3(...tint)).mul(n.z.sub(0.5).mul(vary * 2).add(1));
        const r0 = set.roughnessMap ? texture(set.roughnessMap, tuv).r : float(0.6);
        m.roughnessNode = clamp(r0.mul(rough).add(roughAdd).add(n.y.sub(0.5).mul(0.16)), 0.03, 1);
        if (set.normalMap) m.normalNode = normalMap(texture(set.normalMap, tuv), vec2(nScale, nScale));
        if (set.metalnessMap) m.metalnessNode = texture(set.metalnessMap, tuv).r.mul(metal);
        return keyed(envd(m, envI), name);
    }
    function solid(name, col, o = {}) {
        const { rough = 0.5, roughVar = 0.25, metal = 0, vary = 0.2, scale = 2.0, envI = 1, physical = false, extra = {} } = o;
        const M = physical ? THREE.MeshPhysicalNodeMaterial : THREE.MeshStandardNodeMaterial;
        const m = new M({ metalness: metal, roughness: rough, ...extra });
        const n = tri(scale);
        const n2 = tri(scale * 7.3);
        m.colorNode = vec3(...col).mul(n.z.sub(0.5).mul(vary * 2).add(1)).mul(n2.x.sub(0.5).mul(vary).add(1));
        m.roughnessNode = clamp(float(rough).add(n.w.sub(0.5).mul(roughVar * 2)).add(n2.y.sub(0.5).mul(roughVar)), 0.03, 1);
        return keyed(envd(m, envI), name);
    }
    return { NOISE, tri, keyed, envd, pbr, solid };
}
