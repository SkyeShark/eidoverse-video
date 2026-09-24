// ocean/util.js — small shared helpers for the verse-3 ocean set.
// Everything deterministic: seeded RNG, CPU mip chains (the stack's auto-mipmap pass is broken,
// explicit mip uploads work — render_scene.mjs "CPU mip chains"), canvas → texture with the
// rows flipped so standard UVs read the canvas upright.

// asset roots, resolved from this module's own URL (independent of the working directory): the set's pack
// eidoverse/assets/sets/ocean/ and the shared engine assets eidoverse/assets/ (fonts)
export const fsPath = (u) => { const p = decodeURIComponent(u.pathname); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; };
export const OCEAN_ASSETS = fsPath(new URL('../../assets/sets/ocean/', import.meta.url));
export const ENGINE_ASSETS = fsPath(new URL('../../assets/', import.meta.url));

export const clamp01 = (x) => Math.max(0, Math.min(1, x));
export const smooth = (x) => { x = clamp01(x); return x * x * (3 - 2 * x); };
export const lerp = (a, b, k) => a + (b - a) * k;
export const seg = (u, a, b) => clamp01((u - a) / (b - a));
export const ease = (u, a, b) => smooth(seg(u, a, b));

export function rng(seed = 1) {
    let s = (seed * 2654435761) >>> 0;
    return () => {
        s = (s + 0x6D2B79F5) >>> 0;
        let t = s;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

// 2x2 box-filter mip chain for RGBA8 data
export function buildMips(data, w, h) {
    const levels = [{ data, width: w, height: h }];
    let sw = w, sh = h, src = data;
    while (sw > 1 || sh > 1) {
        const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1);
        const dst = new Uint8Array(dw * dh * 4);
        for (let y = 0; y < dh; y++) {
            const y0 = Math.min(sh - 1, y * 2), y1 = Math.min(sh - 1, y * 2 + 1);
            for (let x = 0; x < dw; x++) {
                const x0 = Math.min(sw - 1, x * 2), x1 = Math.min(sw - 1, x * 2 + 1);
                const o = (y * dw + x) * 4;
                const a = (y0 * sw + x0) * 4, b = (y0 * sw + x1) * 4, c = (y1 * sw + x0) * 4, d = (y1 * sw + x1) * 4;
                dst[o] = (src[a] + src[b] + src[c] + src[d]) >> 2;
                dst[o + 1] = (src[a + 1] + src[b + 1] + src[c + 1] + src[d + 1]) >> 2;
                dst[o + 2] = (src[a + 2] + src[b + 2] + src[c + 2] + src[d + 2]) >> 2;
                dst[o + 3] = (src[a + 3] + src[b + 3] + src[c + 3] + src[d + 3]) >> 2;
            }
        }
        levels.push({ data: dst, width: dw, height: dh });
        sw = dw; sh = dh; src = dst;
    }
    return levels;
}

// RGBA8 array -> DataTexture (optionally mipped). Row 0 of `data` is uv.y = 0 (the bottom).
export function dataTexture(THREE, data, w, h, { srgb = false, wrap = 'clamp', mips = true, aniso = 8 } = {}) {
    const tex = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
    tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    const W = wrap === 'repeat' ? THREE.RepeatWrapping : wrap === 'mirror' ? THREE.MirroredRepeatWrapping : THREE.ClampToEdgeWrapping;
    tex.wrapS = tex.wrapT = W;
    tex.magFilter = THREE.LinearFilter;
    tex.flipY = false;
    tex.generateMipmaps = false;
    if (mips) {
        tex.mipmaps = buildMips(data, w, h);
        tex.minFilter = THREE.LinearMipmapLinearFilter;
        tex.anisotropy = aniso;
    } else tex.minFilter = THREE.LinearFilter;
    tex.needsUpdate = true;
    return tex;
}

// canvas -> DataTexture, rows flipped (canvas top = uv.y 1), so PlaneGeometry/GLB uvs read it upright
export function canvasTexture(THREE, cv, opts = {}) {
    const w = cv.width, h = cv.height;
    const src = cv.getContext('2d').getImageData(0, 0, w, h).data;
    const data = new Uint8Array(w * h * 4);
    const row = w * 4;
    for (let y = 0; y < h; y++) data.set(src.subarray(y * row, (y + 1) * row), (h - 1 - y) * row);
    return dataTexture(THREE, data, w, h, opts);
}

// Native napi canvases created AT their final size: growing a small canvas (what document.createElement +
// width/height does) trips V8's external-memory accounting check in a fresh process (reproduced standalone).
let _napiCreate = null;
export async function initCanvas() {
    if (_napiCreate) return;
    try { _napiCreate = (await import('npm:@napi-rs/canvas@0.1.69')).createCanvas; } catch (e) { _napiCreate = null; }
}
export function makeCanvas(w, h) {
    if (_napiCreate) return _napiCreate(w, h);
    const cv = document.createElement('canvas');
    cv.width = w; cv.height = h;
    return cv;
}

// image file (filesystem path) -> texture via the engine's native loader
export async function fileTexture(THREE, path, { srgb = false, repeat = true } = {}) {
    const tex = await globalThis.loadImageTexture(Deno.readFileSync(path), srgb ? { srgb: true } : {});
    if (repeat) tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    return tex;
}

// fonts: Windows system faces when present (Skia sees them), bundled faces as the fallback
let _fontsDone = false;
export async function ensureFonts() {
    await initCanvas();
    if (_fontsDone) return;
    _fontsDone = true;
    try {
        const { GlobalFonts } = await import('npm:@napi-rs/canvas@0.1.69');
        const reg = (p, fam) => { try { if (Deno.statSync(p).isFile) GlobalFonts.registerFromPath(p, fam); } catch (e) { } };
        reg('C:/Windows/Fonts/georgia.ttf', 'Georgia');
        reg('C:/Windows/Fonts/georgiai.ttf', 'Georgia');
        reg('C:/Windows/Fonts/segoeui.ttf', 'Segoe UI');
        reg('C:/Windows/Fonts/segoeuib.ttf', 'Segoe UI');
        reg(ENGINE_ASSETS + 'fonts/SpecialElite-Regular.ttf', 'Special Elite');
        reg(ENGINE_ASSETS + 'fonts/Exo2.ttf', 'Exo 2');
    } catch (e) { console.warn('[ocean] font registration skipped:', e.message); }
}
