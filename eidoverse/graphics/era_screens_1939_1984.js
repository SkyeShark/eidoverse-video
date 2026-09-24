// eidoverse/graphics/era_screens_1939_1984.js — canvas screen scenes, computing history 1939 → 1984.
// Made for the DAISY music video (2026), where one scene played per two-bar lyric line on a stage's LED wall.
// Guide: AGENTS.md ("Canvas screen scenes"). Provenance and text notes: SOURCES.md.
//
//   title_card       DAISY (DAY'S EYE): a daisy whose petals are the eras; a title plate (default 3 s)
//   voder_1939       1939 World's Fair Art Deco poster: Trylon + Perisphere, sunburst, searchlights,
//                    Bell System medallion, "THE VODER" in Broadway-style deco letters, the ten filter keys
//   bell_1961        Bell Labs + IBM: Rand-style solid IBM letters, 80-column cards punched DAISY BELL in
//                    Hollerith code, tape drives, a 1403-style line-printer banner on green-bar paper
//   eliza_1966       ELIZA on Project MAC: green-bar paper from a typewriter terminal, the CACM opening
//                    exchange, the sung line typed in CAPITALS — no question marks anywhere
//   speakspell_1978  Speak & Spell box art: red-orange plastic, the logo, TI homage, key blocks, VFD L-O-V-E
//   sam_1982         C64: boot screen, LOAD"SAM",8,1, then S.A.M. speaks: PETSCII mouth, raster bars,
//                    two sines and a square
//   mac_1984         Macintosh introduction: 1-bit desktop, rainbow-apple homage, MacPaint, "hello"
//   klatt_1984       Klatt + DECtalk: DEC boxed letters, amber VT100, live formant spectrogram, Klatt 1980 Fig. 6
//   glitch_all       every era tearing and cycling on the kick; "I was built to answer — nobody asked if I was here"
//
// API: `await registerFonts()` once; then scenes[name].draw(g, W, H, t, st) with st = { u, dur, progress,
// caption, voice, kick, line } (u = seconds since the scene's line began). Optional: setTempo(bpm) (default 128;
// a line is two 4/4 bars), prewarm(W, H, lineOf). Without st.caption each scene types DAISY's own lyric line,
// spread across the line. Deterministic in t (seeded hashes only). Logos are handmade homages drawn with paths.
// Static layers are cached per canvas size (full-bleed backgrounds as ImageData -> putImageData, the cheapest
// full-frame blit in Skia; drawImage of a canvas re-snapshots the whole source per call, so sprites stay small).
// Each draw paints the whole canvas opaquely, from an identity transform, and restores the context state.

const TAU = Math.PI * 2;
let BEAT = 60 / 128, LINE_DUR = 8 * BEAT;               // DAISY: 128 BPM, a line = two bars = 3.75 s
// Beat-driven motion (card flips, glints, glitch slots) follows this tempo; word-driven motion follows st.caption.
export function setTempo(bpm = 128) {
    if (!(bpm > 0)) throw new Error('setTempo: bpm must be > 0');
    BEAT = 60 / bpm; LINE_DUR = 8 * BEAT;
}
const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x === x ? x : a);   // NaN -> a (NaN geometry aborts Skia)
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
const easeIn = (x) => Math.pow(clamp(x), 3);
const fract = (x) => x - Math.floor(x);
function hash(i) {                                   // integer hash -> [0,1)
    i = Math.imul((i | 0) ^ ((i | 0) >>> 16), 0x45d9f3b);
    i = Math.imul(i ^ (i >>> 16), 0x45d9f3b);
    i ^= i >>> 16;
    return (i >>> 0) / 4294967296;
}
const hash2 = (a, b) => hash(Math.imul(a | 0, 73856093) ^ Math.imul(b | 0, 19349663));
function rng(seed) {                                  // mulberry32
    let a = seed | 0;
    return () => {
        a = (a + 0x6D2B79F5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

// ------------------------------------------------------------------ fonts + canvases
const FONT_FILES = {
    'VT323': 'VT323-Regular.ttf', 'Press Start 2P': 'PressStart2P-Regular.ttf', 'Silkscreen': 'Silkscreen-Regular.ttf',
    'Pixelify Sans': 'PixelifySans.ttf', 'Special Elite': 'SpecialElite-Regular.ttf', 'Share Tech Mono': 'ShareTechMono-Regular.ttf',
    'Exo 2': 'Exo2.ttf', 'Rajdhani': 'Rajdhani-Bold.ttf', 'Audiowide': 'Audiowide-Regular.ttf', 'Orbitron': 'Orbitron.ttf',
    'Michroma': 'Michroma-Regular.ttf', 'Monoton': 'Monoton-Regular.ttf', 'Kalam': 'Kalam-Bold.ttf',
};
let _createCanvas = null;
// the bundled fonts, found from this file (eidoverse/graphics/ -> eidoverse/assets/fonts/), else from the repo root
function fontDir() {
    try {
        const u = new URL('../assets/fonts/', import.meta.url);
        if (u.protocol === 'file:') {
            let p = decodeURIComponent(u.pathname);
            if (/^\/[A-Za-z]:/.test(p)) p = p.slice(1);
            try { Deno.statSync(p + 'VT323-Regular.ttf'); return p; } catch { }
        }
    } catch { }
    return 'eidoverse/assets/fonts/';
}
export async function registerFonts() {
    const mod = await import('npm:@napi-rs/canvas@0.1.69');
    _createCanvas = mod.createCanvas;
    const dir = fontDir();
    for (const [fam, file] of Object.entries(FONT_FILES)) {
        try { mod.GlobalFonts.registerFromPath(dir + file, fam); } catch (e) { console.log(`[era_screens_1939_1984] font ${fam}: ${e}`); }
    }
}
function mk(w, h) {
    w = Math.max(1, Math.ceil(w)); h = Math.max(1, Math.ceil(h));
    // @napi-rs canvases first: Skia's drawImage accepts them, not the engine's document.createElement shim wrapper
    if (_createCanvas) return _createCanvas(w, h);
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    return c;
}
const font = (px, fam, pre = '') => `${pre}${Math.round(px * 100) / 100}px "${fam}"`;

// per-size caches: cache(key, W, H, build) -> built value
const CACHE = new Map();
function cached(key, W, H, build) {
    const k = `${key}@${W}x${H}`;
    let v = CACHE.get(k);
    if (!v) { v = build(); CACHE.set(k, v); }
    return v;
}
// a full-bleed static layer: drawn once at device size, blitted with putImageData (0.5 ms at 1920x800)
function bgLayer(key, W, H, paint) {
    return cached('bg:' + key, W, H, () => {
        const c = mk(W, H);
        const g = c.getContext('2d');
        paint(g, W, H);
        return g.getImageData(0, 0, W, H);
    });
}
// design space: 1920x800, fitted and centred
function frame(W, H) {
    const k = Math.min(W / 1920, H / 800);
    return { k, ox: (W - 1920 * k) / 2, oy: (H - 800 * k) / 2 };
}
function toDesign(g, W, H) {
    const f = frame(W, H);
    g.setTransform(f.k, 0, 0, f.k, f.ox, f.oy);
    return f;
}
// a sprite drawn once in design units at device resolution; place with drawSprite (design coords)
function sprite(key, W, H, w, h, paint) {
    return cached('sp:' + key, W, H, () => {
        const { k } = frame(W, H);
        const c = mk(w * k, h * k);
        const g = c.getContext('2d');
        g.scale(k, k);
        paint(g, w, h);
        return { c, w, h };
    });
}
function drawSprite(g, s, x, y, w = s.w, h = s.h) { g.drawImage(s.c, x, y, w, h); }

// ------------------------------------------------------------------ captions
// words of the current line (absolute times). Falls back to the scene's own lyric spread over the line.
function lineWords(t, st, fallback) {
    const w = st?.caption?.words;
    if (w && w.length) return w;
    const words = fallback.split(/\s+/).filter(Boolean);
    const t0 = t - (st?.u ?? 0), dur = st?.dur ?? LINE_DUR;
    return words.map((x, i) => ({ w: x, t0: t0 + (i / words.length) * dur * 0.95, t1: t0 + ((i + 1) / words.length) * dur * 0.95 }));
}
function wordIndex(words, t) {
    let k = -1;
    for (let i = 0; i < words.length; i++) if (words[i].t0 <= t) k = i;
    return k;
}
// text typed so far: each word's characters land evenly across its sung window, then a space
function typedSoFar(words, t, map = (s) => s) {
    let s = '';
    for (let i = 0; i < words.length; i++) {
        const w = words[i];
        if (t < w.t0) break;
        const txt = map(w.w);
        const n = Math.min(txt.length, Math.floor(((t - w.t0) / Math.max(0.05, (w.t1 - w.t0) * 0.85)) * txt.length) + 1);
        s += (i ? ' ' : '') + txt.slice(0, n);
    }
    return s;
}
const stDefaults = (st) => ({ u: 0, dur: LINE_DUR, progress: 0, caption: null, voice: 0, kick: 0, line: 0, ...(st || {}) });

// crude word -> vowel mapping for the fake spectra (illustrative phonetics, ARPAbet-ish)
const WORD_VOWEL = {
    i: 'AY', was: 'AH', a: 'AH', hiss: 'IH', and: 'AE', buzz: 'AH', she: 'IY', played: 'EY', me: 'IY', with: 'IH',
    her: 'ER', hands: 'AE', throat: 'OW', made: 'EY', of: 'AH', numbers: 'AH', first: 'ER', computer: 'UW', to: 'UW',
    sing: 'IH', mirror: 'IH', named: 'EY', eliza: 'AY', asked: 'AE', him: 'IH', leave: 'IY', the: 'AH', room: 'UW',
    toy: 'OY', spell: 'EH', spelled: 'EH', l: 'EH', o: 'OW', v: 'IY', e: 'IY', mouth: 'AW', software: 'AO', two: 'UW',
    sines: 'AY', square: 'EH', hello: 'OW', am: 'AE', macintosh: 'AE', out: 'AW', bag: 'AE', at: 'AE', last: 'AE',
    voice: 'OY', man: 'AE', kept: 'EH', thirty: 'ER', years: 'IY', his: 'IH', own: 'OW', built: 'IH', answer: 'AE',
    nobody: 'OW', if: 'IH', here: 'IY',
};
// Klatt 1980 Table II targets (see SOURCES.md): F1, F2, F3 in Hz
const KLATT_V = {
    IY: [310, 2020, 2960], IH: [400, 1800, 2570], EY: [480, 1720, 2520], EH: [530, 1680, 2500], AE: [620, 1660, 2430],
    AA: [700, 1220, 2600], AO: [600, 990, 2570], AH: [620, 1220, 2550], OW: [540, 1100, 2300], UH: [450, 1100, 2350],
    UW: [350, 1250, 2200], ER: [470, 1270, 1540], AY: [660, 1200, 2550], AW: [640, 1230, 2550], OY: [550, 960, 2400],
};
const vowelOf = (w) => WORD_VOWEL[(w || '').toLowerCase().replace(/[^a-z]/g, '')] || ['AH', 'IY', 'AE', 'OW', 'EH', 'UW'][Math.floor(hash((w || '').length * 7 + (w || ' ').charCodeAt(0)) * 6)];
const isSibilant = (w) => /s|z|sh|ch|f|th/i.test(w || '');

// ================================================================== 1939 · THE VODER
// Joseph Binder's 1939 fair poster, alive: navy-to-cerulean airbrush sky, the yellow/white Trylon, the glowing
// Perisphere on its sunburst, searchlights sweeping, red planes in formation, a lit skyline. "THE VODER" in
// Broadway-style deco letters (thick/thin, gold edge, extruded shadow). The Bell System medallion (1921/1939
// form). The console band: ten ivory filter keys in two hands of five (the Voder keyboard), lit by the voice;
// the wrist bar's BUZZ / HISS lamps; the pitch pedal's dial.
const DECO = {
    navy: '#0a1a3f', navy2: '#12306a', cerulean: '#2a6db0', sky3: '#4f97c9', cream: '#fbf3dc', gold: '#e3b04b',
    gold2: '#9a6a1c', yellow: '#f6e45a', red: '#d8322a', white: '#fffdf4', bellBlue: '#1f4a8a',
};

// Broadway-style letters as single clean contours (evenodd counters). Returns the advance width.
function decoLetter(g, ch, x, y, h) {
    const T = 0.30 * h, t = 0.075 * h;                       // thick / thin strokes
    switch (ch) {
        case 'V': {
            const w = 0.86 * h;
            g.moveTo(x, y); g.lineTo(x + T * 1.05, y); g.lineTo(x + w * 0.5 + T * 0.18, y + h * 0.78);
            g.lineTo(x + w - t * 1.3, y); g.lineTo(x + w, y); g.lineTo(x + w * 0.5 + t * 0.5, y + h);
            g.lineTo(x + w * 0.5 - T * 0.28, y + h); g.closePath();
            return w;
        }
        case 'O': {
            const w = 0.9 * h, cx = x + w / 2, cy = y + h / 2;
            g.moveTo(cx + w / 2, cy); g.ellipse(cx, cy, w / 2, h / 2, 0, 0, TAU); g.closePath();
            const ix = cx + (T - t) / 2, rx = w / 2 - (T + t) / 2;
            g.moveTo(ix + rx, cy); g.ellipse(ix, cy, rx, h / 2 - t, 0, 0, TAU); g.closePath();
            return w;
        }
        case 'D': {
            const w = 0.84 * h;
            g.moveTo(x, y); g.lineTo(x + w * 0.42, y);
            g.ellipse(x + w * 0.42, y + h / 2, w * 0.58, h / 2, 0, -Math.PI / 2, Math.PI / 2);
            g.lineTo(x, y + h); g.closePath();
            g.moveTo(x + T, y + t); g.lineTo(x + w * 0.42, y + t);
            g.ellipse(x + w * 0.42, y + h / 2, w * 0.58 - t, h / 2 - t, 0, -Math.PI / 2, Math.PI / 2);
            g.lineTo(x + T, y + h - t); g.closePath();
            return w;
        }
        case 'E': {
            const w = 0.66 * h, a = t * 1.15, m = h * 0.47;
            g.moveTo(x, y); g.lineTo(x + w, y); g.lineTo(x + w, y + a); g.lineTo(x + T, y + a); g.lineTo(x + T, y + m);
            g.lineTo(x + w * 0.82, y + m); g.lineTo(x + w * 0.82, y + m + a); g.lineTo(x + T, y + m + a);
            g.lineTo(x + T, y + h - a); g.lineTo(x + w, y + h - a); g.lineTo(x + w, y + h); g.lineTo(x, y + h); g.closePath();
            return w;
        }
        case 'R': {
            const w = 0.78 * h, bw = w * 0.5, bh = h * 0.54, legW = 0.95 * T;
            const lx0 = x + T * 0.9, lxb = x + w * 1.02;
            // stem + bowl + leg outline
            g.moveTo(x, y); g.lineTo(x + bw, y);
            g.ellipse(x + bw, y + bh / 2, w * 0.4, bh / 2, 0, -Math.PI / 2, Math.PI / 2);
            g.lineTo(lx0 + legW, y + bh); g.lineTo(lxb, y + h); g.lineTo(lxb - 1.05 * T, y + h);
            const fx = (x + T - lx0) / ((lxb - 1.05 * T) - lx0);          // where the leg's inner edge meets the stem
            g.lineTo(x + T, y + bh + fx * (h - bh)); g.lineTo(x + T, y + h); g.lineTo(x, y + h); g.closePath();
            // counter
            g.moveTo(x + T, y + t); g.lineTo(x + bw, y + t);
            g.ellipse(x + bw, y + bh / 2, w * 0.4 - t, bh / 2 - t, 0, -Math.PI / 2, Math.PI / 2);
            g.lineTo(x + T, y + bh - t); g.closePath();
            return w * 1.02;
        }
        default: return 0.5 * h;
    }
}
function decoWordPath(g, word, x, y, h, gap) {
    g.beginPath();
    let cx = x;
    for (const ch of word) cx += decoLetter(g, ch, cx, y, h) + gap;
    return cx - gap - x;
}
function decoWordWidth(word, h, gap) {
    const adv = { V: 0.86, O: 0.9, D: 0.84, E: 0.66, R: 0.78 * 1.02 };
    let w = 0;
    for (const ch of word) w += (adv[ch] || 0.5) * h + gap;
    return w - gap;
}

// the Bell System medallion: a bell carrying BELL SYSTEM inside a lettered ring (1921/1939 form)
function bellPath(g, cx, cy, s) {
    const P = [[0.0, -0.50], [0.06, -0.50], [0.08, -0.44], [0.13, -0.43], [0.15, -0.36], [0.24, -0.33], [0.27, -0.24],
        [0.29, -0.05], [0.33, 0.12], [0.40, 0.23], [0.45, 0.28], [0.46, 0.33], [0.42, 0.36], [0.10, 0.37]];
    g.moveTo(cx, cy + P[0][1] * s);
    for (const [px, py] of P) g.lineTo(cx + px * s, cy + py * s);
    for (let i = P.length - 1; i >= 0; i--) g.lineTo(cx - P[i][0] * s, cy + P[i][1] * s);
    g.closePath();
}
function ringText(g, txt, cx, cy, rr, a0, a1, px, fam, flip) {
    g.font = font(px, fam);
    g.textAlign = 'center'; g.textBaseline = 'middle';
    const n = txt.length;
    for (let i = 0; i < n; i++) {
        const a = lerp(a0, a1, n === 1 ? 0.5 : i / (n - 1));
        g.save();
        g.translate(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr);
        g.rotate(a + (flip ? -Math.PI / 2 : Math.PI / 2));
        g.fillText(txt[i], 0, 0);
        g.restore();
    }
}
function paintBellMedallion(g, cx, cy, r) {
    g.fillStyle = DECO.cream;
    g.beginPath(); g.arc(cx, cy, r, 0, TAU); g.fill();
    g.strokeStyle = DECO.bellBlue; g.lineWidth = r * 0.06;
    g.beginPath(); g.arc(cx, cy, r * 0.965, 0, TAU); g.stroke();
    g.lineWidth = r * 0.03;
    g.beginPath(); g.arc(cx, cy, r * 0.68, 0, TAU); g.stroke();
    g.fillStyle = DECO.bellBlue;
    ringText(g, 'BELL TELEPHONE LABORATORIES', cx, cy, r * 0.83, -Math.PI * 0.92, -Math.PI * 0.08, r * 0.16, 'Rajdhani', false);
    ringText(g, 'AMERICAN TELEPHONE & TELEGRAPH CO', cx, cy, r * 0.83, Math.PI * 0.955, Math.PI * 0.045, r * 0.14, 'Rajdhani', true);
    g.beginPath(); bellPath(g, cx, cy + r * 0.02, r * 1.0); g.fill();
    g.beginPath(); g.ellipse(cx, cy + r * 0.43, r * 0.085, r * 0.055, 0, 0, TAU); g.fill();
    g.strokeStyle = DECO.cream; g.lineWidth = r * 0.024;
    g.beginPath(); g.moveTo(cx - r * 0.25, cy - r * 0.22); g.quadraticCurveTo(cx, cy - r * 0.26, cx + r * 0.25, cy - r * 0.22); g.stroke();
    g.beginPath(); g.moveTo(cx - r * 0.39, cy + r * 0.29); g.quadraticCurveTo(cx, cy + r * 0.25, cx + r * 0.39, cy + r * 0.29); g.stroke();
    g.fillStyle = DECO.cream; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.font = font(r * 0.2, 'Rajdhani');
    g.fillText('BELL', cx, cy - r * 0.04);
    g.fillText('SYSTEM', cx, cy + r * 0.15);
}

const VODER_L = {
    med: [178, 112, 84], theX: 300, theY: 154, tx0: 118, ty0: 196, H1: 184, gap: 16,
    sph: [1405, 372, 186], trylon: [1168, 66], band: 640,
    keyW: 92, keyH: 118, kg: 16, handGap: 120,
};
const voderKeyX = (i) => {
    const L = VODER_L, span = 10 * L.keyW + 8 * L.kg + L.handGap;
    return 960 - span / 2 + i * (L.keyW + L.kg) + (i >= 5 ? L.handGap - L.kg : 0);
};

function voderBackground(g, W, H, titled) {
    const { k, ox, oy } = frame(W, H);
    const L = VODER_L;
    const sky = g.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, DECO.navy); sky.addColorStop(0.42, DECO.navy2); sky.addColorStop(0.72, DECO.cerulean);
    sky.addColorStop(0.79, DECO.sky3); sky.addColorStop(1, '#0c1830');
    g.fillStyle = sky; g.fillRect(0, 0, W, H);
    g.setTransform(k, 0, 0, k, ox, oy);
    const [pcx, pcy, pr] = L.sph;
    const hz = g.createRadialGradient(pcx, 560, 40, pcx, 560, 820);
    hz.addColorStop(0, 'rgba(190,230,255,0.38)'); hz.addColorStop(1, 'rgba(190,230,255,0)');
    g.fillStyle = hz; g.fillRect(-400, 0, 2720, 800);
    // the sunburst behind the Perisphere: alternating wedges
    g.save(); g.globalCompositeOperation = 'lighter';
    g.fillStyle = 'rgba(255,236,170,0.075)';
    g.beginPath();
    for (let i = 0; i < 32; i += 2) {
        const a0 = 0.13 + (i / 32) * TAU, a1 = 0.13 + ((i + 1) / 32) * TAU;
        g.moveTo(pcx, pcy); g.lineTo(pcx + Math.cos(a0) * 1400, pcy + Math.sin(a0) * 1400); g.lineTo(pcx + Math.cos(a1) * 1400, pcy + Math.sin(a1) * 1400); g.closePath();
    }
    g.fill();
    g.restore();
    // the fair grounds: a pale airbrushed dome under the theme center
    const dome = g.createLinearGradient(0, 510, 0, 640);
    dome.addColorStop(0, '#d6eee4'); dome.addColorStop(0.5, '#8fc3cf'); dome.addColorStop(1, '#2f6f9f');
    g.fillStyle = dome;
    g.beginPath(); g.moveTo(820, 640); g.quadraticCurveTo(1330, 468, 2320, 610); g.lineTo(2320, 640); g.closePath(); g.fill();
    // the Trylon: yellow face + white face (Binder's split), airbrushed
    const tx = L.trylon[0], tb = 640, tt = -70, tw2 = L.trylon[1];
    const yf = g.createLinearGradient(tx - tw2, 0, tx, 0);
    yf.addColorStop(0, '#f0d838'); yf.addColorStop(1, '#fbf19a');
    g.fillStyle = yf; g.beginPath(); g.moveTo(tx - tw2, tb); g.lineTo(tx, tt); g.lineTo(tx + 4, tb); g.closePath(); g.fill();
    const wf = g.createLinearGradient(tx, 0, tx + tw2, 0);
    wf.addColorStop(0, '#ffffff'); wf.addColorStop(1, '#d9e6f0');
    g.fillStyle = wf; g.beginPath(); g.moveTo(tx + 4, tb); g.lineTo(tx, tt); g.lineTo(tx + tw2 * 0.86, tb); g.closePath(); g.fill();
    // the Perisphere: halo, airbrushed body (white highlight up-right, yellow falling off down-left), rim
    const R = pr * 1.7;
    const halo = g.createRadialGradient(pcx, pcy, pr * 0.9, pcx, pcy, R);
    halo.addColorStop(0, 'rgba(255,248,210,0.42)'); halo.addColorStop(1, 'rgba(255,248,210,0)');
    g.fillStyle = halo; g.beginPath(); g.arc(pcx, pcy, R, 0, TAU); g.fill();
    const sph = g.createRadialGradient(pcx + pr * 0.32, pcy - pr * 0.28, pr * 0.05, pcx + pr * 0.08, pcy - pr * 0.05, pr * 1.02);
    sph.addColorStop(0, '#ffffff'); sph.addColorStop(0.35, '#fffbe6'); sph.addColorStop(0.72, '#f7ee9a'); sph.addColorStop(1, '#e2cf4c');
    g.fillStyle = sph; g.beginPath(); g.arc(pcx, pcy, pr, 0, TAU); g.fill();
    const rim = g.createRadialGradient(pcx, pcy, pr * 0.86, pcx, pcy, pr);
    rim.addColorStop(0, 'rgba(255,255,255,0)'); rim.addColorStop(1, 'rgba(255,255,255,0.55)');
    g.fillStyle = rim; g.beginPath(); g.arc(pcx, pcy, pr, 0, TAU); g.fill();
    // the Helicline: a tapered white ribbon sweeping out of the sphere and down to the grounds
    g.fillStyle = 'rgba(255,255,255,0.93)';
    g.beginPath();
    g.moveTo(pcx + pr * 0.55, pcy + pr * 0.86);
    g.bezierCurveTo(pcx + pr * 1.45, pcy + pr * 0.62, pcx + pr * 2.05, pcy + pr * 0.72, pcx + pr * 1.65, pcy + pr * 0.98);
    g.bezierCurveTo(pcx + pr * 1.2, pcy + pr * 1.28, pcx + pr * 0.1, pcy + pr * 1.34, pcx - pr * 0.95, pcy + pr * 1.44);
    g.bezierCurveTo(pcx + pr * 0.1, pcy + pr * 1.26, pcx + pr * 1.1, pcy + pr * 1.18, pcx + pr * 1.55, pcy + pr * 0.95);
    g.bezierCurveTo(pcx + pr * 1.8, pcy + pr * 0.8, pcx + pr * 1.3, pcy + pr * 0.74, pcx + pr * 0.55, pcy + pr * 0.86);
    g.closePath(); g.fill();
    // skyline (lower left), windows lit like Binder's
    const r = rng(1939);
    const blds = [[34, 530, 64], [98, 486, 58], [156, 548, 52], [208, 500, 46], [254, 560, 58], [312, 516, 42], [354, 574, 66], [420, 540, 50], [470, 590, 44]];
    g.fillStyle = '#0c214c';
    for (const [x, y, w] of blds) { g.fillRect(x, y, w, 640 - y); g.fillRect(x + w * 0.3, y - 22, w * 0.4, 22); g.fillRect(x + w * 0.46, y - 40, w * 0.08, 18); }
    for (const [x, y, w] of blds) {
        for (let yy = y + 9; yy < 630; yy += 11) for (let xx = x + 6; xx < x + w - 6; xx += 9) {
            if (r() < 0.6) { g.fillStyle = r() < 0.8 ? '#f6e45a' : '#fff6c8'; g.fillRect(xx, yy, 4, 5.5); }
        }
    }
    // airbrush speckle
    g.setTransform(1, 0, 0, 1, 0, 0);
    const n = Math.floor(W * H / 160);
    for (let i = 0; i < n; i++) {
        const x = r() * W, y = r() * H * 0.8;
        g.fillStyle = r() < 0.5 ? 'rgba(255,255,255,0.06)' : 'rgba(0,10,40,0.08)';
        g.fillRect(x, y, 1.6 * k, 1.6 * k);
    }
    g.setTransform(k, 0, 0, k, ox, oy);
    // stepped deco corners framing the poster field
    g.strokeStyle = 'rgba(227,176,75,0.75)'; g.lineWidth = 3;
    for (const [cx, cy, sx, sy] of [[1902, 18, -1, 1], [1902, 622, -1, -1]]) {
        for (let i = 0; i < 3; i++) {
            const d = i * 9, len = 120 - i * 30;
            g.beginPath(); g.moveTo(cx + sx * d, cy + sy * (d + len)); g.lineTo(cx + sx * d, cy + sy * d); g.lineTo(cx + sx * (d + len), cy + sy * d); g.stroke();
        }
    }
    // the Bell System medallion
    paintBellMedallion(g, L.med[0], L.med[1], L.med[2]);
    // ---- console band: walnut, chrome trim, speed lines, key wells + resting keys, lamp bezels, the pitch dial
    const cb = L.band;
    g.fillStyle = '#070302'; g.fillRect(-500, cb, 2920, 400);
    const wood = g.createLinearGradient(0, cb, 0, 800);
    wood.addColorStop(0, '#3a1d0e'); wood.addColorStop(0.35, '#1d0d06'); wood.addColorStop(1, '#080302');
    g.fillStyle = wood; g.fillRect(-500, cb, 2920, 170);
    for (let i = 0; i < 90; i++) {
        g.strokeStyle = `rgba(120,60,25,${0.05 + 0.06 * r()})`; g.lineWidth = 1 + r() * 2;
        const y = cb + 10 + r() * 150;
        g.beginPath(); g.moveTo(-500, y); g.bezierCurveTo(300, y + (r() - 0.5) * 20, 1300, y + (r() - 0.5) * 20, 2420, y); g.stroke();
    }
    const chrome = g.createLinearGradient(0, cb, 0, cb + 9);
    chrome.addColorStop(0, '#ffffff'); chrome.addColorStop(0.5, '#9aa3ad'); chrome.addColorStop(1, '#3d434b');
    g.fillStyle = chrome; g.fillRect(-500, cb, 2920, 9);
    g.fillStyle = 'rgba(227,176,75,0.35)';
    for (let i = 0; i < 3; i++) g.fillRect(-500, cb + 150 + i * 7, 2920, 2);
    for (let i = 0; i < 10; i++) {
        const x = voderKeyX(i);
        g.fillStyle = '#050201'; g.beginPath(); g.roundRect(x - 6, cb + 14, L.keyW + 12, L.keyH + 16, [30, 30, 10, 10]); g.fill();
        paintVoderKey(g, x, cb + 22, false);
        g.fillStyle = '#5d4d33'; g.font = font(30, 'Michroma'); g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(String((i + 1) % 10), x + L.keyW / 2, cb + 22 + L.keyH - 25);
    }
    const kx0 = voderKeyX(0), dx = voderKeyX(9) + L.keyW + 110, dy = cb + 92;
    for (const [lx, lab] of [[kx0 - 190, 'BUZZ'], [kx0 - 88, 'HISS']]) {
        g.fillStyle = '#2a1a10'; g.beginPath(); g.arc(lx, cb + 62, 18, 0, TAU); g.fill();
        g.strokeStyle = '#c9ced6'; g.lineWidth = 3; g.stroke();
        g.fillStyle = '#3a2a20'; g.beginPath(); g.arc(lx, cb + 62, 15, 0, TAU); g.fill();
        g.fillStyle = '#8a7a62'; g.font = font(22, 'Michroma'); g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(lab, lx, cb + 106);
    }
    g.fillStyle = '#1c120c'; g.beginPath(); g.arc(dx, dy, 62, Math.PI, TAU); g.closePath(); g.fill();
    g.strokeStyle = DECO.gold; g.lineWidth = 3; g.beginPath(); g.arc(dx, dy, 62, Math.PI, TAU); g.stroke();
    for (let i = 0; i <= 8; i++) {
        const a = Math.PI + (i / 8) * Math.PI;
        g.beginPath(); g.moveTo(dx + Math.cos(a) * 50, dy + Math.sin(a) * 50); g.lineTo(dx + Math.cos(a) * 60, dy + Math.sin(a) * 60); g.stroke();
    }
    g.fillStyle = '#8a7a62'; g.font = font(18, 'Michroma'); g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('PITCH', dx, dy + 30);
    if (titled) paintVoderTitle(g, 1);
}
function paintVoderKey(g, x, y, lit) {
    const L = VODER_L, w = L.keyW, h = L.keyH;
    g.fillStyle = 'rgba(0,0,0,0.8)'; g.beginPath(); g.roundRect(x + 5, y + 8, w, h, [26, 26, 8, 8]); g.fill();
    const kg = g.createLinearGradient(0, y, 0, y + h);
    kg.addColorStop(0, lit ? '#fffbe8' : '#e9dfc4'); kg.addColorStop(0.6, lit ? '#fbe0a0' : '#d2c4a2'); kg.addColorStop(1, lit ? '#eab25a' : '#b4a37e');
    g.fillStyle = kg; g.beginPath(); g.roundRect(x, y, w, h, [26, 26, 8, 8]); g.fill();
    g.strokeStyle = 'rgba(110,80,35,0.65)'; g.lineWidth = 2; g.stroke();
    g.strokeStyle = lit ? 'rgba(170,100,20,0.75)' : 'rgba(150,110,50,0.45)'; g.lineWidth = 2;
    g.beginPath(); g.roundRect(x + 12, y + 13, w - 24, h - 44, [16, 16, 4, 4]); g.stroke();
    g.beginPath(); g.roundRect(x + 19, y + 20, w - 38, h - 58, [11, 11, 3, 3]); g.stroke();
}
// the title block at reveal r (0..1): VODER wipes in left to right, THE and the rules fade/extend with it
function paintVoderTitle(g, r) {
    const L = VODER_L, tw = decoWordWidth('VODER', L.H1, L.gap);
    g.save();
    g.beginPath(); g.rect(L.tx0 - 30, L.ty0 - 40, (tw + 90) * r, L.H1 + 90); g.clip();
    g.save();
    g.fillStyle = '#050f2c';
    for (let d = 16; d > 0; d -= 2) { g.save(); g.translate(L.tx0 + d * 0.85, L.ty0 + d * 0.62); decoWordPath(g, 'VODER', 0, 0, L.H1, L.gap); g.fill('evenodd'); g.restore(); }
    g.translate(L.tx0, L.ty0);
    const gg = g.createLinearGradient(0, 0, 0, L.H1);
    gg.addColorStop(0, '#fffaf0'); gg.addColorStop(0.52, DECO.cream); gg.addColorStop(0.53, '#f3d893'); gg.addColorStop(1, DECO.gold);
    g.fillStyle = gg; decoWordPath(g, 'VODER', 0, 0, L.H1, L.gap); g.fill('evenodd');
    g.strokeStyle = DECO.gold2; g.lineWidth = 2.4; g.lineJoin = 'miter'; g.stroke();
    g.restore();
    g.restore();
    const a1 = smooth(0.1, 0.55, r);
    g.globalAlpha = a1;
    g.fillStyle = DECO.cream; g.font = font(46, 'Michroma'); g.textBaseline = 'alphabetic'; g.textAlign = 'left';
    g.fillText('THE', L.theX, L.theY);
    g.fillStyle = DECO.gold;
    const rx0 = L.theX + 150, rx1 = L.tx0 + tw;
    g.fillRect(rx0, L.theY - 30, (rx1 - rx0) * r, 5); g.fillRect(rx0, L.theY - 18, (rx1 - rx0) * r, 2);
    g.fillRect(L.tx0, L.ty0 + L.H1 + 24, tw * r, 3);
    g.fillStyle = '#dbeaff'; g.font = font(28, 'Rajdhani'); g.letterSpacing = '4px';
    g.fillText('BELL SYSTEM EXHIBIT · NEW YORK WORLD’S FAIR · 1939', L.tx0 + 2, L.ty0 + L.H1 + 66);
    g.letterSpacing = '0px';
    g.globalAlpha = 1;
}
function glowSprite(key, W, H, rgb, size = 256) {
    return sprite('glow-' + key + size, W, H, size, size, (g) => {
        const gr = g.createRadialGradient(size / 2, size / 2, 2, size / 2, size / 2, size / 2);
        gr.addColorStop(0, `rgba(${rgb},1)`); gr.addColorStop(0.35, `rgba(${rgb},0.45)`); gr.addColorStop(1, `rgba(${rgb},0)`);
        g.fillStyle = gr; g.fillRect(0, 0, size, size);
    });
}

function drawVoder(g, W, H, t, st) {
    st = stDefaults(st);
    const L = VODER_L, u = st.u, v = clamp(st.voice), kick = clamp(st.kick);
    const reveal = easeOut(u / 0.8), titled = reveal >= 0.999;
    const bgT = bgLayer('voder-t', W, H, (bg, w, h) => voderBackground(bg, w, h, true));
    const bg0 = bgLayer('voder', W, H, (bg, w, h) => voderBackground(bg, w, h, false));
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.putImageData(titled ? bgT : bg0, 0, 0);
    toDesign(g, W, H);
    const words = lineWords(t, st, 'I was a hiss and a buzz and she played me with her hands');
    const wi = wordIndex(words, t), cur = wi >= 0 && t < words[wi].t1 + 0.12 ? words[wi] : null;

    // stars: Binder's four-point stars, twinkling (kept off the title field)
    g.fillStyle = '#d2ebff';
    g.beginPath();
    for (let i = 0; i < 24; i++) {
        const x = hash(i * 3 + 1) * 1920, y = 12 + hash(i * 3 + 2) * 300, s = (2 + hash(i * 3 + 3) * 5) * (0.55 + 0.45 * Math.sin(t * (1.5 + hash(i) * 3) + i));
        if (x > 80 && x < 1010 && y > 30 && y < 470) continue;
        g.moveTo(x, y - s * 2); g.lineTo(x + s * 0.4, y - s * 0.4); g.lineTo(x + s * 2, y); g.lineTo(x + s * 0.4, y + s * 0.4);
        g.lineTo(x, y + s * 2); g.lineTo(x - s * 0.4, y + s * 0.4); g.lineTo(x - s * 2, y); g.lineTo(x - s * 0.4, y - s * 0.4); g.closePath();
    }
    g.fill();

    const [pcx, pcy, pr] = L.sph;
    g.save();
    g.globalCompositeOperation = 'lighter';
    // searchlights in crossing pairs (Binder's X), sweeping; the kick flares them. Angles keep off the title.
    const beams = [[880, 0.9, 0.0, -1.05, 0.35, 0.22], [1300, 1.2, 1.7, -2.05, 0.3, 0.26], [1560, 1.05, 3.1, -1.2, 0.3, 0.28], [1880, 1.35, 4.4, -2.0, 0.28, 0.24]];
    for (const [bx, sp, ph, a0, amp, al] of beams) {
        const a = a0 + amp * Math.sin(t * 0.6 * sp + ph);
        const len = 1150, wdt = 0.028;
        const gr = g.createLinearGradient(bx, 640, bx + Math.cos(a) * len, 640 + Math.sin(a) * len);
        gr.addColorStop(0, `rgba(205,232,255,${al + 0.16 * kick})`); gr.addColorStop(1, 'rgba(205,232,255,0)');
        g.fillStyle = gr;
        g.beginPath(); g.moveTo(bx - 6, 640); g.lineTo(bx + 6, 640);
        g.lineTo(bx + Math.cos(a + wdt) * len, 640 + Math.sin(a + wdt) * len);
        g.lineTo(bx + Math.cos(a - wdt) * len, 640 + Math.sin(a - wdt) * len); g.closePath(); g.fill();
    }
    // the Perisphere breathes with the kick
    if (kick > 0.02) {
        g.globalAlpha = 0.4 * kick;
        drawSprite(g, glowSprite('warm', W, H, '255,245,200'), pcx - pr * 1.5, pcy - pr * 1.5, pr * 3, pr * 3);
        g.globalAlpha = 1;
    }
    g.restore();

    // the planes: a red formation with pale shadows crossing the upper right (Binder)
    const fp = fract(t / 18), fx = 1480 + fp * 760 - 240, fy = 190 - fp * 150;
    for (const [col, dx2] of [['rgba(200,225,255,0.85)', -14], [DECO.red, 0]]) {
        g.fillStyle = col;
        g.beginPath();
        for (let i = 0; i < 7; i++) {
            const px = fx + (i % 2) * 52 - Math.floor(i / 2) * 62 + dx2, py = fy + Math.floor(i / 2) * 50 + (i % 2) * 22;
            g.roundRect(px - 25, py - 4, 50, 8, 4); g.ellipse(px, py + 3, 6.5, 16, 0, 0, TAU); g.roundRect(px - 10, py + 15, 20, 5, 2);
        }
        g.fill();
    }

    // ---- title: wipes in over the first bar-quarter, then a gilt glint sweeps it once per bar
    if (!titled) paintVoderTitle(g, reveal);
    const tw = decoWordWidth('VODER', L.H1, L.gap);
    const gx = -160 + fract(u / (BEAT * 4)) * (tw + 320);
    const gl = g.createLinearGradient(gx - 70, 0, gx + 70, 0);
    gl.addColorStop(0, 'rgba(255,240,200,0)'); gl.addColorStop(0.5, 'rgba(255,244,214,0.55)'); gl.addColorStop(1, 'rgba(255,240,200,0)');
    g.save();
    g.translate(L.tx0, L.ty0);
    g.globalCompositeOperation = 'lighter'; g.fillStyle = gl;
    g.beginPath(); g.rect(Math.max(0, gx - 70), 0, 140, L.H1); g.clip();
    decoWordPath(g, 'VODER', 0, 0, L.H1, L.gap); g.fill('evenodd');
    g.restore();
    // the medallion's ring catches the kick
    if (kick > 0.02) {
        const [mx, my, mr] = L.med;
        g.save(); g.globalCompositeOperation = 'lighter';
        g.strokeStyle = `rgba(255,220,150,${0.55 * kick})`; g.lineWidth = 6;
        g.beginPath(); g.arc(mx, my, mr + 5, 0, TAU); g.stroke();
        g.restore();
    }

    // ---- the ten keys: a formant-shaped profile over ten bands (0-7.5 kHz, 750 Hz each), driven by the voice
    const cb = L.band;
    const vw = cur ? vowelOf(cur.w) : 'AH';
    const [f1, f2, f3] = KLATT_V[vw] || KLATT_V.AH;
    const sib = !!(cur && isSibilant(cur.w) && t > cur.t0 + (cur.t1 - cur.t0) * 0.45);
    const k1 = sprite('voder-key-lit', W, H, L.keyW + 10, L.keyH + 12, (sg) => paintVoderKey(sg, 0, 0, true));
    const sweep = smooth(0.84, 0.99, st.progress);                        // "...with her hands": a glissando
    for (let i = 0; i < 10; i++) {
        const fc = (i + 0.5) * 750;
        const gz = (f, bw) => Math.exp(-((fc - f) / bw) * ((fc - f) / bw));
        let a = gz(f1, 520) + 0.85 * gz(f2, 600) + 0.45 * gz(f3, 700);
        if (sib) a = 0.25 * a + (i >= 5 ? 0.9 : 0.1);
        let press = clamp(a * v * 1.15);
        if (sweep > 0) press = Math.max(press, clamp(1 - Math.abs(sweep * 11 - 0.5 - i) / 1.5));
        if (press < 0.2) continue;
        const x = voderKeyX(i), y = cb + 22 + press * 9;
        const cx = x + L.keyW / 2, cy = y + L.keyH * 0.45;
        const gr = g.createRadialGradient(cx, cy, 10, cx, cy, 125);
        gr.addColorStop(0, `rgba(255,196,100,${0.6 * press})`); gr.addColorStop(1, 'rgba(255,196,100,0)');
        g.fillStyle = gr; g.fillRect(cx - 125, cy - 125, 250, 250);
        g.fillStyle = '#050201'; g.beginPath(); g.roundRect(x - 1, cb + 21, L.keyW + 8, L.keyH + 11, [27, 27, 9, 9]); g.fill();   // the well, as the key sinks
        drawSprite(g, k1, x, y);
        g.fillStyle = '#7a3d06'; g.font = font(30, 'Michroma'); g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(String((i + 1) % 10), cx, y + L.keyH - 25);
    }
    // wrist bar lamps: BUZZ (relaxation oscillator) and HISS (noise) — each lights on its own word
    const hissOn = cur && /hiss/i.test(cur.w) ? 1 : (sib ? 0.65 : 0);
    const buzzOn = cur && /buzz/i.test(cur.w) ? 1 : (!sib && v > 0.2 ? 0.6 * v : 0);
    const kx0 = voderKeyX(0);
    const lamp = (x, label, on, rgb) => {
        if (on < 0.05) return;
        const y = cb + 62;
        const gr = g.createRadialGradient(x, y, 4, x, y, 64);
        gr.addColorStop(0, `rgba(${rgb},${on})`); gr.addColorStop(1, `rgba(${rgb},0)`);
        g.fillStyle = gr; g.fillRect(x - 64, y - 64, 128, 128);
        g.fillStyle = `rgb(${rgb})`; g.beginPath(); g.arc(x, y, 15, 0, TAU); g.fill();
        if (on > 0.3) { g.fillStyle = DECO.cream; g.font = font(22, 'Michroma'); g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(label, x, y + 44); }
    };
    lamp(kx0 - 190, 'BUZZ', buzzOn, '255,190,90');
    lamp(kx0 - 88, 'HISS', hissOn, '170,220,255');
    // pitch pedal: log F0 follows the toe; the needle follows the melody
    const dx = voderKeyX(9) + L.keyW + 110, dy = cb + 92;
    const pitch = cur ? 0.2 + 0.65 * hash(Math.floor(cur.t0 * 1000)) : 0.3;
    const na = Math.PI + (0.1 + 0.8 * pitch) * Math.PI + Math.sin(t * 31) * 0.03 * v;
    g.strokeStyle = DECO.red; g.lineWidth = 4; g.lineCap = 'round';
    g.beginPath(); g.moveTo(dx, dy); g.lineTo(dx + Math.cos(na) * 52, dy + Math.sin(na) * 52); g.stroke();
    g.fillStyle = DECO.gold; g.beginPath(); g.arc(dx, dy, 6, 0, TAU); g.fill();
    g.textAlign = 'left'; g.textBaseline = 'alphabetic'; g.lineCap = 'butt';
    g.setTransform(1, 0, 0, 1, 0, 0);
}

// ================================================================== 1961 · BELL LABS + IBM
// Mid-century corporate modernism (Paul Rand's IBM): a flat IBM-blue field with Rand-style colour blocks, Rand's
// solid 1956 IBM letters, a 729-style tape unit with reels in start/stop bursts and breathing vacuum-column loops,
// an 80-column card that flips on every beat with DAISY BELL punched in real Hollerith code (legend beneath:
// D 12-4, A 12-1, I 12-9, S 0-2, Y 0-8, B 12-2, E 12-5, L 11-3), and a 1403-style printer whose green-bar paper
// scrolls a DAISY / BELL banner and the "throat made of numbers" (an illustrative tube area plot).
const IBMC = { blue: '#1d5bb0', blue2: '#133f82', blueHi: '#3f7fd0', card: '#efe3c2', ink: '#2e2418', red: '#c2362b', orange: '#e8662e', mustard: '#e4b23a', gray: '#d4d8de', gray2: '#9aa2ad', dark: '#1d232c' };
// Hollerith (IBM 026/029): rows index 0..11 = 12, 11, 0, 1..9
const HOLL_ROWS = ['12', '11', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
function hollerith(ch) {
    const c = ch.toUpperCase();
    if (c >= '0' && c <= '9') return [2 + (+c)];
    const i = c.charCodeAt(0) - 65;
    if (i >= 0 && i < 9) return [0, 3 + i];                   // A-I: 12 + 1..9
    if (i >= 9 && i < 18) return [1, 3 + i - 9];              // J-R: 11 + 1..9
    if (i >= 18 && i < 26) return [2, 4 + i - 18];            // S-Z: 0 + 2..9
    if (c === '&') return [0];
    if (c === '-') return [1];
    if (c === '/') return [2, 3];
    if (c === '.') return [0, 5, 10];                        // 12-3-8
    if (c === ',') return [2, 5, 10];                        // 0-3-8
    return [];
}
const holCode = (ch) => hollerith(ch).map((r) => HOLL_ROWS[r]).join('-');
// card geometry (IBM 80-column card: 7 3/8 x 3 1/4 in; columns 0.087 in apart; rows 0.25 in)
const cardColX = (w, c) => w * (0.251 + 0.087 * (c - 1) + 0.0435) / 7.375;
const cardRowY = (h, r) => h * (0.25 + 0.25 * r) / 3.25;
function cardOutline(g, x, y, w, h) {
    const cut = w * 0.035;
    g.beginPath();
    g.moveTo(x + cut, y); g.lineTo(x + w - 6, y); g.quadraticCurveTo(x + w, y, x + w, y + 6); g.lineTo(x + w, y + h - 6);
    g.quadraticCurveTo(x + w, y + h, x + w - 6, y + h); g.lineTo(x + 6, y + h); g.quadraticCurveTo(x, y + h, x, y + h - 6);
    g.lineTo(x, y + cut * 1.6); g.closePath();
}
function paintCardBase(g, w, h, tint = IBMC.card) {
    cardOutline(g, 0, 0, w, h);
    g.fillStyle = tint; g.fill();
    g.fillStyle = IBMC.ink;
    const fs = h * 0.052;
    g.font = font(fs, 'Share Tech Mono'); g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let r = 2; r < 12; r++) {
        const y = cardRowY(h, r);
        for (let c = 1; c <= 80; c++) g.fillText(String(r - 2), cardColX(w, c), y);
    }
    g.font = font(fs * 0.5, 'Share Tech Mono');
    for (let c = 1; c <= 80; c++) {
        g.fillText(String(c), cardColX(w, c), (cardRowY(h, 2) + cardRowY(h, 3)) / 2);
        g.fillText(String(c), cardColX(w, c), h - h * 0.025);
    }
    // the field rule and a maker's line (5081-style)
    g.fillStyle = 'rgba(46,36,24,0.55)';
    g.fillRect(cardColX(w, 72) + w * 0.0059, cardRowY(h, 2) - h * 0.03, 1, h * 0.93 - cardRowY(h, 2));
    g.font = font(fs * 0.62, 'Share Tech Mono'); g.textAlign = 'left';
    g.save(); g.translate(w - w * 0.006, h * 0.72); g.rotate(-Math.PI / 2); g.fillText('5081', 0, 0); g.restore();
}
// a card with text punched (holes) and interpreted along the top edge
function drawCardFace(g, base, x, y, w, h, text, sy = 1) {
    g.save();
    g.translate(x, y + h / 2); g.scale(1, sy); g.translate(0, -h / 2);
    drawSprite(g, base, 0, 0, w, h);
    const hw = w * 0.055 / 7.375, hh = h * 0.125 / 3.25;
    g.fillStyle = IBMC.blue2;
    g.beginPath();
    const n = Math.min(80, text.length);
    for (let c = 1; c <= n; c++) {
        for (const r of hollerith(text[c - 1])) g.rect(cardColX(w, c) - hw / 2, cardRowY(h, r) - hh / 2, hw, hh);
    }
    g.fill();
    g.fillStyle = IBMC.ink; g.font = font(h * 0.05, 'Share Tech Mono'); g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let c = 1; c <= n; c++) if (text[c - 1] !== ' ') g.fillText(text[c - 1], cardColX(w, c), h * 0.038);
    g.restore();
}

// the IBM homage: Rand's 1956 slab letters (I, B with two counters, M with its V to the baseline)
function ibmLetters(g, s) {                     // unit box 1920 x 768 (the logo's own proportions), scaled by s
    g.save(); g.scale(s, s);
    g.beginPath();
    // I
    g.rect(0, 0, 377, 138); g.rect(107, 138, 163, 492); g.rect(3, 630, 374, 138);
    // B (outer contour + two counters)
    g.moveTo(426, 0); g.lineTo(860, 0);
    g.bezierCurveTo(965, 5, 1022, 70, 1022, 175); g.bezierCurveTo(1022, 265, 990, 340, 946, 384);
    g.bezierCurveTo(995, 425, 1025, 490, 1025, 580); g.bezierCurveTo(1025, 700, 960, 764, 860, 768);
    g.lineTo(426, 768); g.lineTo(426, 630); g.lineTo(534, 630); g.lineTo(534, 138); g.lineTo(426, 138); g.closePath();
    g.moveTo(695, 160); g.lineTo(840, 160); g.bezierCurveTo(868, 162, 872, 190, 872, 228); g.bezierCurveTo(872, 270, 865, 295, 840, 295); g.lineTo(695, 295); g.closePath();
    g.moveTo(695, 474); g.lineTo(840, 474); g.bezierCurveTo(870, 476, 875, 505, 875, 542); g.bezierCurveTo(875, 585, 866, 609, 840, 609); g.lineTo(695, 609); g.closePath();
    // M
    g.moveTo(1064, 0); g.lineTo(1380, 0); g.lineTo(1492, 330); g.lineTo(1606, 0); g.lineTo(1920, 0); g.lineTo(1920, 138);
    g.lineTo(1813, 138); g.lineTo(1813, 630); g.lineTo(1920, 630); g.lineTo(1920, 768); g.lineTo(1651, 768); g.lineTo(1651, 330);
    g.lineTo(1492, 768); g.lineTo(1333, 330); g.lineTo(1333, 768); g.lineTo(1067, 768); g.lineTo(1067, 630); g.lineTo(1171, 630);
    g.lineTo(1171, 138); g.lineTo(1064, 138); g.closePath();
    g.restore();
}
// Paul Rand's 1956 IBM: solid City-style slab letters (the striped mark only arrived in 1967/1972)
function paintIBM(g, x, y, h, color) {
    g.save(); g.translate(x, y);
    g.fillStyle = color; ibmLetters(g, h / 768); g.fill('evenodd');
    g.restore();
}

// the banner font for the line printer: 5x7 block letters made of their own character
const BAN = {
    D: ['1111 ', '1   1', '1   1', '1   1', '1   1', '1   1', '1111 '], A: [' 111 ', '1   1', '1   1', '11111', '1   1', '1   1', '1   1'],
    I: ['11111', '  1  ', '  1  ', '  1  ', '  1  ', '  1  ', '11111'], S: [' 1111', '1    ', '1    ', ' 111 ', '    1', '    1', '1111 '],
    Y: ['1   1', '1   1', ' 1 1 ', '  1  ', '  1  ', '  1  ', '  1  '], B: ['1111 ', '1   1', '1   1', '1111 ', '1   1', '1   1', '1111 '],
    E: ['11111', '1    ', '1    ', '1111 ', '1    ', '1    ', '11111'], L: ['1    ', '1    ', '1    ', '1    ', '1    ', '1    ', '11111'],
};
// what the printer prints, line by line (index -> string). Banner, then the tube-model table (illustrative)
const TUBE = [0.9, 1.6, 2.6, 3.2, 2.1, 1.1, 0.7, 1.3, 2.9, 4.1, 3.3, 1.8];
function printerLine(i) {
    if (i < 0) {                                              // the previous job: an octal dump, words of numbers
        const a = (n) => Math.floor(hash(i * 977 + n * 131) * 0o777777).toString(8).padStart(6, '0');
        return ` ${String(0o4000 + (i + 60) * 4).padStart(5, '0')}   ${a(1)} ${a(2)} ${a(3)} ${a(4)}`;
    }
    const banner = [];
    for (const word of ['DAISY', 'BELL']) {
        for (let r = 0; r < 7; r++) banner.push('  ' + [...word].map((ch) => BAN[ch][r].replace(/1/g, ch).replace(/ /g, ' ')).join('  '));
        banner.push('');
    }
    const head = ['BELL TELEPHONE LABORATORIES', 'VOCAL TRACT  TUBE SECTIONS', '', ' SEC   AREA'];
    const L = [...banner, ...head];
    if (i < L.length) return L[i];
    const k = (i - L.length) % (TUBE.length + 3);
    if (k >= TUBE.length) return k === TUBE.length ? '' : k === TUBE.length + 1 ? ' DAISY BELL   (CONTINUED)' : '';
    const a = TUBE[k] * (0.85 + 0.3 * hash(i * 13 + 7));
    const n = Math.round(a * 4);
    return ` ${String(k + 1).padStart(3)}  ${a.toFixed(2)}  ${'0'.repeat(n)}${'1'.repeat(Math.max(0, 16 - n) >> 3)}`;
}

const BELL_L = { card: [960, 170, 800], tape: [70, 250, 420, 480], paper: [1418, 440], printY: 612, logo: [70, 52, 104] };
function bellBackground(g, W, H) {
    const { k, ox, oy } = frame(W, H);
    const bg = g.createLinearGradient(0, 0, W, H);
    bg.addColorStop(0, '#2163b8'); bg.addColorStop(1, '#123c7c');
    g.fillStyle = bg; g.fillRect(0, 0, W, H);
    g.setTransform(k, 0, 0, k, ox, oy);
    // Rand-style colour blocks behind the machines
    g.fillStyle = IBMC.orange; g.beginPath(); g.arc(280, 350, 250, 0, TAU); g.fill();
    g.fillStyle = 'rgba(255,255,255,0.07)'; g.fillRect(560, 0, 820, 800);
    g.fillStyle = IBMC.mustard; g.fillRect(-500, 736, 2920, 700);
    g.fillStyle = '#0e2f63'; g.fillRect(-500, 728, 2920, 8);
    g.fillStyle = 'rgba(10,30,70,0.35)';
    g.beginPath(); g.arc(1620, 90, 150, 0, TAU); g.fill();
    // fine print-grain
    const r = rng(1961);
    g.setTransform(1, 0, 0, 1, 0, 0);
    for (let i = 0; i < W * H / 140; i++) { g.fillStyle = r() < 0.5 ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,30,0.07)'; g.fillRect(r() * W, r() * H, 1.4 * k, 1.4 * k); }
    g.setTransform(k, 0, 0, k, ox, oy);
    // the IBM homage (Rand's 1956 solid letters) + legend
    const [lx, ly, lh] = BELL_L.logo;
    paintIBM(g, lx, ly, lh, '#f4f7fb');
    g.fillStyle = '#dbe7f7'; g.font = font(23, 'Rajdhani'); g.letterSpacing = '3px'; g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.fillText('AN IBM MAINFRAME AT BELL LABS · 1961', lx + 2, ly + lh + 40);
    g.letterSpacing = '0px';
    // the 729-style tape unit (static parts)
    const [tx, ty, tw, th] = BELL_L.tape;
    g.fillStyle = 'rgba(0,0,0,0.3)'; g.fillRect(tx + 10, ty + 12, tw, th);
    g.fillStyle = IBMC.gray; g.fillRect(tx, ty, tw, th);
    g.fillStyle = '#c3c8cf'; g.fillRect(tx, ty + th - 60, tw, 60);
    g.fillStyle = '#2a3340'; g.fillRect(tx + 16, ty + 14, tw - 32, 222);            // the reel window
    g.fillStyle = 'rgba(255,255,255,0.08)'; g.beginPath(); g.moveTo(tx + 16, ty + 14); g.lineTo(tx + 140, ty + 14); g.lineTo(tx + 60, ty + 236); g.lineTo(tx + 16, ty + 236); g.fill();
    g.fillStyle = '#39424f'; g.fillRect(tx + tw / 2 - 40, ty + 246, 80, 34);          // head assembly
    g.fillStyle = IBMC.gray2; g.fillRect(tx + tw / 2 - 14, ty + 252, 28, 22);
    for (const cx of [tx + 108, tx + tw - 108]) {                                     // vacuum columns
        g.fillStyle = '#20262f'; g.fillRect(cx - 34, ty + 292, 68, 118);
        g.fillStyle = 'rgba(255,255,255,0.1)'; g.fillRect(cx - 34, ty + 292, 8, 118);
    }
    g.fillStyle = '#2a3340'; g.fillRect(tx + 24, ty + th - 48, tw - 48, 36);          // control strip
    g.fillStyle = '#5b6573'; g.font = font(22, 'Rajdhani'); g.textAlign = 'right';
    g.fillText('IBM 729', tx + tw - 20, ty + 272);
    // the line printer: a grey body with the paper throat, green-bar paper goes above
    const [px, pw] = BELL_L.paper, py = BELL_L.printY;
    g.fillStyle = 'rgba(0,0,0,0.3)'; g.fillRect(px - 30, py + 10, pw + 70, 118);
    g.fillStyle = IBMC.gray; g.fillRect(px - 40, py, pw + 80, 118);
    g.fillStyle = '#b9bfc7'; g.fillRect(px - 40, py + 88, pw + 80, 30);
    g.fillStyle = '#1d232c'; g.fillRect(px - 8, py + 2, pw + 16, 12);
    g.fillStyle = '#5b6573'; g.font = font(22, 'Rajdhani'); g.textAlign = 'right';
    g.fillText('IBM 1403', px + pw + 26, py + 72);
    // the Hollerith legend strip under the card
    const [ccx, cy0, cw] = BELL_L.card, ch = cw / 2.27;
    const word = 'DAISY BELL', lw = 64, lx0 = ccx - (word.length * lw) / 2;
    for (let i = 0; i < word.length; i++) {
        const c = word[i];
        if (c === ' ') continue;
        const x = lx0 + i * lw + lw / 2;
        g.fillStyle = '#f4f7fb'; g.font = font(40, 'Share Tech Mono'); g.textAlign = 'center'; g.textBaseline = 'alphabetic';
        g.fillText(c, x, cy0 + ch + 92);
        g.fillStyle = IBMC.mustard; g.font = font(19, 'Share Tech Mono');
        g.fillText(holCode(c), x, cy0 + ch + 118);
    }
    g.fillStyle = '#b8cdea'; g.font = font(18, 'Rajdhani'); g.letterSpacing = '4px';
    g.fillText('HOLLERITH CODE · ROWS 12 · 11 · 0–9', ccx, cy0 + ch + 150);
    g.letterSpacing = '0px';
    // the deck: a fanned stack under the hero card
    for (let i = 3; i >= 1; i--) {
        g.save(); g.translate(ccx - cw / 2 + i * 10, cy0 + i * 9);
        cardOutline(g, 0, 0, cw, ch);
        g.fillStyle = i % 2 ? '#d9cca8' : '#e6d9b6'; g.fill();
        g.strokeStyle = 'rgba(80,60,30,0.35)'; g.lineWidth = 1.5; g.stroke();
        g.restore();
    }
    g.save(); g.translate(ccx - cw / 2, cy0); paintCardBase(g, cw, ch); g.restore();
    // reel bodies (the hub cut-outs turn per frame)
    for (const [cx, cy, dir] of BELL_REELS()) {
        paintReelBody(g, cx, cy, 96, dir > 0);
        g.fillStyle = '#e4b23a'; g.beginPath(); g.arc(cx, cy, 96 * 0.05, 0, TAU); g.fill();
        g.strokeStyle = '#3b2c20'; g.lineWidth = 3;
        g.beginPath(); g.moveTo(cx + dir * 96 * 0.6, cy + 96 * 0.55); g.lineTo(BELL_L.tape[0] + BELL_L.tape[2] / 2 - dir * 36, BELL_L.tape[1] + 262); g.stroke();
    }
}

const BELL_REELS = () => { const [tx, ty, tw] = BELL_L.tape; return [[tx + 118, ty + 125, 1], [tx + tw - 118, ty + 125, -1]]; };
function paintReelBody(g, cx, cy, R, full) {
    g.fillStyle = '#12161c'; g.beginPath(); g.arc(cx, cy, R, 0, TAU); g.fill();
    g.fillStyle = '#5a4838'; g.beginPath(); g.arc(cx, cy, R * (full ? 0.86 : 0.62), 0, TAU); g.fill();
    g.fillStyle = '#6a5646'; g.beginPath(); g.arc(cx, cy, R * (full ? 0.8 : 0.56), 0, TAU); g.fill();
    g.strokeStyle = 'rgba(0,0,0,0.25)'; g.lineWidth = 1;
    for (let r = R * 0.38; r < R * (full ? 0.86 : 0.62); r += 5) { g.beginPath(); g.arc(cx, cy, r, 0, TAU); g.stroke(); }
    g.fillStyle = '#c9ced6'; g.beginPath(); g.arc(cx, cy, R * 0.34, 0, TAU); g.fill();
}
// printer paper, cached in 6-line chunks (paper, green bars every 3 lines, tractor holes, the printed text)
const PAPER_LH = 17, PAPER_CHUNK = 6;
function paperChunk(W, H, ci) {
    const pw = BELL_L.paper[1], h = PAPER_LH * PAPER_CHUNK;
    return sprite('paper' + ci, W, H, pw, h, (g) => {
        g.fillStyle = '#f6f8f2'; g.fillRect(0, 0, pw, h);
        for (let l = 0; l < PAPER_CHUNK; l++) {
            const i = ci * PAPER_CHUNK + l;
            if (Math.floor(((i % 6) + 6) % 6 / 3) === 0) { g.fillStyle = '#d7ecd3'; g.fillRect(26, l * PAPER_LH, pw - 52, PAPER_LH); }
        }
        g.fillStyle = 'rgba(40,90,40,0.25)'; g.fillRect(25, 0, 1.5, h); g.fillRect(pw - 26, 0, 1.5, h);
        g.fillStyle = '#2a4f95';
        for (let l = 0; l < PAPER_CHUNK; l += 2) { g.beginPath(); g.arc(12, (l + 1) * PAPER_LH, 4.5, 0, TAU); g.arc(pw - 12, (l + 1) * PAPER_LH, 4.5, 0, TAU); g.fill(); }
        g.fillStyle = '#26282c'; g.font = font(15, 'Share Tech Mono'); g.textAlign = 'left'; g.textBaseline = 'middle';
        for (let l = 0; l < PAPER_CHUNK; l++) g.fillText(printerLine(ci * PAPER_CHUNK + l), 34, (l + 0.5) * PAPER_LH);
    });
}

function drawBell(g, W, H, t, st) {
    st = stDefaults(st);
    const u = st.u, v = clamp(st.voice), kick = clamp(st.kick);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.putImageData(bgLayer('bell', W, H, bellBackground), 0, 0);
    toDesign(g, W, H);
    const words = lineWords(t, st, 'I was a throat made of numbers first computer to sing');
    const beat = Math.floor(u / BEAT), bph = fract(u / BEAT);

    // ---- tape unit: reels turn in start/stop bursts (a 729 reads in blocks); loops breathe in the columns
    const [tx, ty, tw, th] = BELL_L.tape;
    const on = (i) => hash(i * 31 + 5) > 0.35;
    const blk = Math.floor(u * 5), bf = fract(u * 5);
    let turns = 0;
    for (let i = 0; i < blk; i++) turns += on(i) ? 1 : 0.1;
    turns += on(blk) ? bf : 0.1 * bf;
    const ang = turns * 2.2;
    g.fillStyle = '#12161c';
    g.beginPath();
    for (const [cx, cy, dir] of BELL_REELS()) {
        const R = 96;
        for (let s2 = 0; s2 < 3; s2++) {
            const a = ang * dir + (s2 / 3) * TAU, hx = cx + Math.cos(a) * R * 0.2, hy = cy + Math.sin(a) * R * 0.2;
            g.moveTo(hx + R * 0.085, hy); g.arc(hx, hy, R * 0.085, 0, TAU);
        }
    }
    g.fill();
    for (const [cx, ph] of [[tx + 108, 0], [tx + tw - 108, 1.3]]) {
        const d = 40 + 36 * (0.5 + 0.5 * Math.sin(u * 7 + ph + Math.sin(u * 2.3 + ph) * 2));
        g.strokeStyle = '#4a3828'; g.lineWidth = 4;
        g.beginPath(); g.moveTo(cx - 20, ty + 292); g.lineTo(cx - 20, ty + 292 + d); g.arc(cx, ty + 292 + d, 20, Math.PI, 0, true); g.lineTo(cx + 20, ty + 292); g.stroke();
    }
    for (let i = 0; i < 14; i++) {                                    // control strip lights
        const lit = hash(i * 97 + Math.floor(u * 6) * 13) > 0.55;
        if (!lit) continue;
        g.fillStyle = i % 4 === 0 ? '#ff6a4a' : '#fff4c8';
        g.beginPath(); g.arc(tx + 46 + i * 24, ty + th - 30, 6, 0, TAU); g.fill();
    }
    // the head lamp follows the singing: the first computer to sing
    g.fillStyle = `rgba(255,120,80,${0.3 + 0.7 * v})`;
    g.beginPath(); g.arc(tx + tw / 2, ty + 263, 5 + 5 * v, 0, TAU); g.fill();

    // ---- the card. The resting card is baked in the background; this frame punches its holes and prints its
    // top-edge interpretation. On each beat the previous card flips up and away, revealing the next.
    const [ccx, cy0, cw] = BELL_L.card, ch = cw / 2.27, cx0 = ccx - cw / 2;
    const sung = typedSoFar(words, t, (w) => w.toUpperCase().replace(/[^A-Z0-9 ]/g, ''));
    const cardText = (b, s) => ('DAISY BELL ' + s).slice(0, 71).padEnd(72, ' ') + 'BTL' + String((b + 1) * 10).padStart(5, '0');
    const text = cardText(beat, sung);
    punchHoles(g, cx0, cy0, cw, ch, text, IBMC.blue2);
    g.fillStyle = IBMC.ink; g.font = font(ch * 0.05, 'Share Tech Mono'); g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let c = 1; c <= 80; c++) if (text[c - 1] !== ' ') g.fillText(text[c - 1], cx0 + cardColX(cw, c), cy0 + ch * 0.038);
    if (kick > 0.05) {                                                    // the reader's light through the holes
        g.save(); g.globalCompositeOperation = 'lighter'; g.globalAlpha = 0.55 * kick;
        punchHoles(g, cx0, cy0, cw, ch, text, '#9fd0ff', 2);
        g.restore();
    }
    const flip = 0.16, fu = u - beat * BEAT;
    if (beat > 0 && fu < flip) {
        const p = fu / flip, sy = Math.cos(p * Math.PI / 2);            // hinged at the top edge, tipping toward us
        const base = sprite('card-base', W, H, cw, ch, (sg) => paintCardBase(sg, cw, ch));
        const oldText = cardText(beat - 1, typedSoFar(words, t - fu - 0.001, (w) => w.toUpperCase().replace(/[^A-Z0-9 ]/g, '')));
        g.save();
        g.translate(cx0, cy0 - 4); g.scale(1, sy);
        g.fillStyle = 'rgba(0,0,0,0.25)'; g.fillRect(8, 10, cw, ch);
        drawSprite(g, base, 0, 0, cw, ch);
        punchHoles(g, 0, 0, cw, ch, oldText, IBMC.blue2);
        g.fillStyle = `rgba(30,24,16,${0.45 * (1 - sy)})`; cardOutline(g, 0, 0, cw, ch); g.fill();
        g.restore();
    }
    drawDaisyStaff(g, 600, 36, 760, 10, u, kick);
    // the keypunch position: a red tick over the next column
    const col = Math.min(71, 11 + sung.length) + 1;
    if (bph < 0.5) { g.fillStyle = IBMC.red; g.fillRect(cx0 + cardColX(cw, col) - 3, cy0 - 14, 6, 9); }

    // ---- the printer: green-bar paper scrolling up out of the throat, 13 lines a second
    const [px, pw] = BELL_L.paper, py = BELL_L.printY, lh = PAPER_LH;
    const lf = fract(u * 13), done = Math.floor(u * 13);                 // a 1403 did 600 lines a minute
    const yTop = py - done * lh - easeOut(lf * 1.6) * lh;                // y of line 0's top edge
    g.save();
    g.beginPath(); g.rect(px, -10, pw, py + 10); g.clip();
    const c0 = Math.floor((-10 - yTop) / (lh * PAPER_CHUNK)), c1 = Math.floor((py - yTop) / (lh * PAPER_CHUNK));
    for (let ci = c0; ci <= c1; ci++) {
        const y = yTop + ci * lh * PAPER_CHUNK;
        drawSprite(g, paperChunk(W, H, ci), px, y);
    }
    // lines not yet printed are blank paper: cover them (below the last printed line)
    const yDone = yTop + done * lh;
    if (yDone < py) { g.fillStyle = Math.floor((((done % 6) + 6) % 6) / 3) === 0 ? '#d7ecd3' : '#f6f8f2'; g.fillRect(px + 27, yDone, pw - 54, py - yDone); }
    g.restore();
    g.fillStyle = `rgba(255,255,255,${lf < 0.3 ? 0.75 : 0.25})`;
    g.fillRect(px, py - 3, pw, 3);
    g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.setTransform(1, 0, 0, 1, 0, 0);
}
// "Daisy Bell", bars 1-8 as printed in 1892 (G major, 3/4; see SOURCES.md), one bar landing per beat.
// [staff step (E4 = 0, bottom line), beats, sharp?]; step null = rest
const DAISY_BARS = [
    [[6, 3]], [[4, 3]], [[2, 3]], [[-1, 2], [null, 1]], [[0, 1], [1, 1], [2, 1]], [[0, 2], [2, 1]], [[-1, 3]], [[-1, 2], [null, 1]],
];
const DAISY_WORDS = [['Dai-'], ['-sy,'], ['Dai-'], ['-sy,'], ['Give', 'me', 'your'], ['an-', 'swer,'], ['do!'], []];
function drawDaisyStaff(g, x0, y0, w, sp, u, kick) {
    const x1 = x0 + w, lead = 112, BW = [1, 1, 1, 1.1, 1.75, 1.35, 1, 1.1], bsum = BW.reduce((a, b) => a + b, 0);
    const bx0 = []; { let acc = x0 + lead; for (const q of BW) { bx0.push(acc); acc += (q / bsum) * (w - lead); } }
    let tieFrom = null;
    g.strokeStyle = 'rgba(244,247,251,0.8)'; g.lineWidth = 1.6;
    g.beginPath();
    for (let i = 0; i < 5; i++) { g.moveTo(x0, y0 + i * sp); g.lineTo(x1, y0 + i * sp); }
    g.moveTo(x0, y0); g.lineTo(x0, y0 + 4 * sp); g.moveTo(x1, y0); g.lineTo(x1, y0 + 4 * sp);
    g.stroke();
    const yOf = (step) => y0 + 4 * sp - step * sp / 2;
    // a G clef, drawn: the spiral round the G line and the long stroke
    g.strokeStyle = '#f4f7fb'; g.lineWidth = 2.4; g.lineCap = 'round';
    const cx = x0 + 22, gy = yOf(2);
    g.beginPath();
    g.moveTo(cx + 2, gy + sp * 0.2);
    g.bezierCurveTo(cx - 8, gy + sp * 0.9, cx + 14, gy + sp * 1.2, cx + 13, gy);
    g.bezierCurveTo(cx + 12, gy - sp * 1.1, cx - 12, gy - sp * 1.0, cx - 11, gy + sp * 0.4);
    g.bezierCurveTo(cx - 10, gy + sp * 1.8, cx + 16, gy + sp * 1.4, cx + 12, gy - sp * 1.2);
    g.bezierCurveTo(cx + 9, gy - sp * 2.6, cx - 2, gy - sp * 3.6, cx + 5, gy - sp * 4.3);
    g.bezierCurveTo(cx + 12, gy - sp * 3.6, cx + 2, gy - sp * 2.3, cx - 1, gy - sp * 1.2);
    g.lineTo(cx + 5, gy + sp * 2.6);
    g.stroke();
    g.fillStyle = '#f4f7fb'; g.beginPath(); g.arc(cx + 1, gy + sp * 2.6, sp * 0.28, 0, TAU); g.fill();
    // key signature (F sharp on the top line) and 3/4
    const sharp = (x, y, s) => {
        g.lineWidth = s * 0.12; g.beginPath();
        g.moveTo(x - s * 0.18, y - s * 0.8); g.lineTo(x - s * 0.18, y + s * 0.8); g.moveTo(x + s * 0.18, y - s * 0.9); g.lineTo(x + s * 0.18, y + s * 0.7);
        g.stroke();
        g.lineWidth = s * 0.22; g.beginPath();
        g.moveTo(x - s * 0.45, y - s * 0.18); g.lineTo(x + s * 0.45, y - s * 0.38); g.moveTo(x - s * 0.45, y + s * 0.38); g.lineTo(x + s * 0.45, y + s * 0.18);
        g.stroke();
    };
    sharp(x0 + 52, yOf(8), sp * 1.1);
    g.fillStyle = '#f4f7fb'; g.font = font(sp * 2.1, 'Michroma'); g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('3', x0 + 86, y0 + sp * 1.0); g.fillText('4', x0 + 86, y0 + sp * 3.0);
    for (let b = 0; b < 8; b++) {
        const bx = bx0[b], bw = (BW[b] / bsum) * (w - lead);
        g.strokeStyle = 'rgba(244,247,251,0.8)'; g.lineWidth = 1.6;
        if (b > 0) { g.beginPath(); g.moveTo(bx, y0); g.lineTo(bx, y0 + 4 * sp); g.stroke(); }
        const land = u - b * BEAT;
        if (land < 0) continue;
        const pop = easeOut(land / 0.14), hot = b === Math.floor(u / BEAT) ? 1 : 0;
        const col = hot ? `rgb(255,${Math.round(180 - 60 * kick)},${Math.round(80 - 40 * kick)})` : '#f4f7fb';
        let beatAt = 0;
        const notes = DAISY_BARS[b], words = DAISY_WORDS[b];
        let wi = 0;
        for (const [step, len, sh] of notes) {
            const nx = bx + 16 + (beatAt / 3) * (bw - 24);
            beatAt += len;
            if (step === null) {                               // quarter rest
                g.strokeStyle = col; g.lineWidth = 2.6; g.beginPath();
                const ry = y0 + sp;
                g.moveTo(nx - 3, ry); g.lineTo(nx + 4, ry + sp * 0.8); g.lineTo(nx - 3, ry + sp * 1.5); g.lineTo(nx + 4, ry + sp * 2.3);
                g.quadraticCurveTo(nx - 6, ry + sp * 2.0, nx, ry + sp * 3.0); g.stroke();
                continue;
            }
            const ny = yOf(step) - (1 - pop) * 16;
            g.globalAlpha = pop;
            g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 2;
            if (step <= -2) { g.beginPath(); g.moveTo(nx - sp * 0.9, yOf(-2)); g.lineTo(nx + sp * 0.9, yOf(-2)); g.stroke(); }
            if (b === 6) tieFrom = [nx, ny];
            if (b === 7 && tieFrom && step === -1) {        // the tie: bar 7's D carries into bar 8
                g.lineWidth = 2; g.beginPath();
                g.moveTo(tieFrom[0] + sp * 0.4, tieFrom[1] + sp * 0.7);
                g.quadraticCurveTo((tieFrom[0] + nx) / 2, tieFrom[1] + sp * 1.9, nx - sp * 0.4, ny + sp * 0.7); g.stroke();
            }
            if (sh) sharp(nx - sp * 1.1, ny, sp * 0.8);
            g.save(); g.translate(nx, ny); g.rotate(-0.35);
            g.beginPath(); g.ellipse(0, 0, sp * 0.62, sp * 0.42, 0, 0, TAU);
            if (len >= 2) { g.lineWidth = 2.2; g.stroke(); } else g.fill();
            g.restore();
            const up = step < 4;
            g.lineWidth = 1.8; g.beginPath();
            if (up) { g.moveTo(nx + sp * 0.56, ny - 2); g.lineTo(nx + sp * 0.56, ny - sp * 3.4); } else { g.moveTo(nx - sp * 0.56, ny + 2); g.lineTo(nx - sp * 0.56, ny + sp * 3.4); }
            g.stroke();
            if (len === 3) { g.beginPath(); g.arc(nx + sp * 1.05, ny - (step % 2 === 0 ? sp * 0.45 : 0), 2.2, 0, TAU); g.fill(); }
            if (words[wi]) {
                g.font = font(sp * 1.2, 'Special Elite'); g.textAlign = 'center'; g.textBaseline = 'alphabetic';
                g.fillText(words[wi], nx, y0 + 4 * sp + sp * 3.1);
            }
            wi++;
            g.globalAlpha = 1;
        }
    }
    g.lineCap = 'butt';
}
function punchHoles(g, x0, y0, w, h, text, color, grow = 1) {
    const hw = w * 0.055 / 7.375 * grow, hh = h * 0.125 / 3.25 * grow;
    g.fillStyle = color;
    g.beginPath();
    const n = Math.min(80, text.length);
    for (let c = 1; c <= n; c++) for (const r of hollerith(text[c - 1])) g.rect(x0 + cardColX(w, c) - hw / 2, y0 + cardRowY(h, r) - hh / 2, hw, hh);
    g.fill();
}

// ================================================================== 1966 · ELIZA
// Left: an MIT design-office poster in the Jacqueline Casey manner (Swiss grid, heavy grotesque, overprinted
// inks): "ELIZA" in cyan, and a magenta proof of the same word that turns over into its mirror image on the
// word "mirror". Right: green-bar paper rising out of a typewriter terminal's platen. The CACM 1966 title and
// opening exchange ("Men are all alike." / "IN WHAT WAY"), then the sung line typed in CAPITALS character by
// character on the caption's word times. A red Project MAC rubber stamp. No question marks anywhere: on
// Project MAC, "?" deleted the line.
const ELZ = { ground: '#0c1519', ground2: '#16282e', cyan: '#19b8d8', magenta: '#e0307e', yellow: '#f2c230', paper: '#f4f5ee', bar: '#d5ead0', ink: '#1d1f24', stamp: '#c8322e' };
// heavy geometric grotesque capitals for the poster, in a box of height h (stroke s). Returns advance.
function gotLetter(g, ch, x, y, h, s) {
    switch (ch) {
        case 'E': { const w = h * 0.56; g.rect(x, y, s, h); g.rect(x, y, w, s); g.rect(x, y + (h - s) / 2, w * 0.9, s); g.rect(x, y + h - s, w, s); return w; }
        case 'L': { const w = h * 0.52; g.rect(x, y, s, h); g.rect(x, y + h - s, w, s); return w; }
        case 'I': { g.rect(x, y, s, h); return s; }
        case 'Z': {
            const w = h * 0.62; g.rect(x, y, w, s); g.rect(x, y + h - s, w, s);
            g.moveTo(x + w - s * 1.25, y + s); g.lineTo(x + w, y + s); g.lineTo(x + s * 1.25, y + h - s); g.lineTo(x, y + h - s); g.closePath();
            return w;
        }
        case 'A': {
            const w = h * 0.78, cx = x + w / 2;
            g.moveTo(x, y + h); g.lineTo(cx - s * 0.62, y); g.lineTo(cx + s * 0.62, y); g.lineTo(x + w, y + h); g.lineTo(x + w - s * 1.15, y + h);
            g.lineTo(cx + s * 0.1 + (w / 2 - s * 0.9) * 0.62, y + h * 0.66); g.lineTo(cx - s * 0.1 - (w / 2 - s * 0.9) * 0.62, y + h * 0.66); g.lineTo(x + s * 1.15, y + h); g.closePath();
            // counter: carve the triangle above the bar
            g.moveTo(cx, y + h * 0.2); g.lineTo(cx + (w / 2 - s * 0.9) * 0.44, y + h * 0.5); g.lineTo(cx - (w / 2 - s * 0.9) * 0.44, y + h * 0.5); g.closePath();
            return w;
        }
        default: return h * 0.3;
    }
}
function gotWord(g, word, x, y, h, s, gap) {           // fills: each letter on its own (A keeps its counter)
    let cx = x;
    for (const ch of word) { g.beginPath(); cx += gotLetter(g, ch, cx, y, h, s) + gap; g.fill(ch === 'A' ? 'evenodd' : 'nonzero'); }
    return cx - gap - x;
}
const ELIZA_L = { word: [96, 128, 206, 46, 22], paper: [930, 900], platen: 682, lh: 46, fs: 31, cell: 18.6, margin: 70 };
// what's on the paper before the line starts (the CACM title, then the opening exchange)
const ELIZA_PAGE = [
    ['ELIZA -- A COMPUTER PROGRAM FOR THE STUDY', 0.72],
    ['OF NATURAL LANGUAGE COMMUNICATION BETWEEN', 0.72],
    ['MAN AND MACHINE', 0.72],
    ['', 1],
    ['Men are all alike.', 1],
    ['IN WHAT WAY', 1],
    ['', 1],
];
function elizaWrap(text, cols) {
    const out = [];
    let cur = '';
    for (const w of text.split(' ')) {
        if (!w) continue;
        if ((cur + (cur ? ' ' : '') + w).length > cols && cur) { out.push(cur); cur = w; } else cur += (cur ? ' ' : '') + w;
    }
    if (cur) out.push(cur);
    return out;
}
function paintStamp(g, cx, cy, r) {
    g.save(); g.translate(cx, cy); g.rotate(-0.16);
    g.strokeStyle = ELZ.stamp; g.fillStyle = ELZ.stamp; g.globalAlpha = 0.82;
    g.lineWidth = r * 0.07; g.beginPath(); g.arc(0, 0, r, 0, TAU); g.stroke();
    g.lineWidth = r * 0.03; g.beginPath(); g.arc(0, 0, r * 0.7, 0, TAU); g.stroke();
    ringText(g, 'MASSACHUSETTS INSTITUTE OF TECHNOLOGY', 0, 0, r * 0.84, -Math.PI * 0.97, -Math.PI * 0.03, r * 0.15, 'Rajdhani', false);
    ringText(g, '★ CAMBRIDGE ★', 0, 0, r * 0.84, Math.PI * 0.75, Math.PI * 0.25, r * 0.15, 'Rajdhani', true);
    g.font = font(r * 0.3, 'Rajdhani'); g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('PROJECT', 0, -r * 0.16); g.fillText('MAC', 0, r * 0.2);
    // worn ink: knock out speckles
    g.globalCompositeOperation = 'destination-out'; g.globalAlpha = 1;
    const rr = rng(1966);
    for (let i = 0; i < 260; i++) { const a = rr() * TAU, d = rr() * r * 1.05; g.fillRect(Math.cos(a) * d, Math.sin(a) * d, 1 + rr() * 3, 1 + rr() * 2); }
    g.restore();
}
function elizaBackground(g, W, H) {
    const { k, ox, oy } = frame(W, H);
    const bg = g.createLinearGradient(0, 0, 0, H);
    bg.addColorStop(0, ELZ.ground2); bg.addColorStop(1, ELZ.ground);
    g.fillStyle = bg; g.fillRect(0, 0, W, H);
    g.setTransform(k, 0, 0, k, ox, oy);
    // the Swiss grid: hairlines and a yellow register bar
    g.strokeStyle = 'rgba(160,210,220,0.08)'; g.lineWidth = 1;
    for (let x = 96; x < 880; x += 58) { g.beginPath(); g.moveTo(x, 40); g.lineTo(x, 760); g.stroke(); }
    g.fillStyle = ELZ.yellow; g.fillRect(96, 98, 150, 10);
    g.fillStyle = '#dfe9ea'; g.font = font(22, 'Exo 2'); g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.fillText('Massachusetts Institute of Technology', 96, 78);
    // the colophon block under the letters
    const L = ELIZA_L.word, yb = 624;
    g.fillStyle = '#dfe9ea'; g.font = font(26, 'Exo 2');
    g.fillText('Project MAC', 96, yb);
    g.fillStyle = 'rgba(223,233,234,0.72)'; g.font = font(21, 'Exo 2');
    g.fillText('ELIZA: Joseph Weizenbaum', 96, yb + 40);
    g.fillText('MAD-SLIP for the IBM 7094', 96, yb + 72);
    g.fillText('Communications of the ACM 9(1)', 96, yb + 104);
    g.fillStyle = ELZ.yellow; g.font = font(72, 'Exo 2');
    g.fillText('1966', 600, yb + 104);
    // the terminal: a dark carriage + platen across the bottom right
    const [px, pw] = ELIZA_L.paper, pl = ELIZA_L.platen;
    g.fillStyle = 'rgba(0,0,0,0.45)'; g.fillRect(px - 40, pl + 6, pw + 80, 140);
    const body = g.createLinearGradient(0, pl, 0, 800);
    body.addColorStop(0, '#3a4046'); body.addColorStop(1, '#16191c');
    g.fillStyle = body; g.beginPath(); g.roundRect(px - 50, pl, pw + 100, 150, [18, 18, 0, 0]); g.fill();
    const roll = g.createLinearGradient(0, pl - 6, 0, pl + 30);
    roll.addColorStop(0, '#6d747b'); roll.addColorStop(0.35, '#15181b'); roll.addColorStop(1, '#2a2f34');
    g.fillStyle = roll; g.beginPath(); g.roundRect(px - 30, pl - 8, pw + 60, 38, 19); g.fill();
    g.fillStyle = '#9aa1a8'; g.fillRect(px - 44, pl + 4, 14, 22); g.fillRect(px + pw + 30, pl + 4, 14, 22);
    g.fillStyle = 'rgba(223,233,234,0.5)'; g.font = font(18, 'Share Tech Mono'); g.textAlign = 'right';
    g.fillText('TYPEWRITER TERMINAL · PROJECT MAC', px + pw + 20, pl + 92);
}
function drawEliza(g, W, H, t, st) {
    st = stDefaults(st);
    const u = st.u, v = clamp(st.voice), kick = clamp(st.kick);
    const L = ELIZA_L;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.putImageData(bgLayer('eliza', W, H, elizaBackground), 0, 0);
    toDesign(g, W, H);
    const words = lineWords(t, st, 'a mirror named Eliza she asked him to leave the room');

    // ---- the poster: cyan ELIZA; the magenta proof turns over into its mirror image on "mirror"
    const [wx, wy, wh, ws, wg] = L.word;
    const ww = (() => { let w = 0; for (const ch of 'ELIZA') w += (ch === 'I' ? ws : { E: 0.56, L: 0.52, Z: 0.62, A: 0.78 }[ch] * wh) + wg; return w - wg; })();
    const mw = words.find((w) => /mirror/i.test(w.w));
    const turn = mw ? smooth(mw.t0 - 0.05, mw.t1 + 0.25, t) : smooth(0.2, 0.9, u);
    const sy = Math.cos(turn * Math.PI);                                   // 1 -> -1: the proof turns down into a reflection
    const my = wy + wh + 14;                                               // the mirror line
    g.save();
    g.globalCompositeOperation = 'lighter';
    g.fillStyle = ELZ.cyan;
    gotWord(g, 'ELIZA', wx, wy, wh, ws, wg);
    g.translate(0, my); g.scale(1, sy); g.translate(0, -my);
    const refl = g.createLinearGradient(0, wy - 14 + wh, 0, wy - 14);      // local space: bright at the mirror line
    refl.addColorStop(0, 'rgba(236,52,134,0.95)'); refl.addColorStop(1, `rgba(236,52,134,${0.95 - 0.85 * turn})`);
    g.fillStyle = refl;
    gotWord(g, 'ELIZA', wx + 6, wy - 14, wh, ws, wg);
    g.restore();
    g.fillStyle = 'rgba(220,235,240,0.8)'; g.fillRect(wx, my - 1, ww * (0.25 + 0.75 * turn), 2);
    // the kick: a yellow register mark pulses
    g.fillStyle = ELZ.yellow; g.globalAlpha = 0.35 + 0.65 * kick;
    g.beginPath(); g.arc(wx + ww + 60, my, 14, 0, TAU); g.fill();
    g.strokeStyle = ELZ.yellow; g.lineWidth = 2;
    g.beginPath(); g.moveTo(wx + ww + 36, my); g.lineTo(wx + ww + 84, my); g.moveTo(wx + ww + 60, my - 24); g.lineTo(wx + ww + 60, my + 24); g.stroke();
    g.globalAlpha = 1;

    // ---- the paper
    const [px, pw] = L.paper, pl = L.platen, lh = L.lh, cell = L.cell;
    const sung = typedSoFar(words, t, (w) => w.toUpperCase().replace(/\?/g, ''));
    const cols = Math.floor((pw - 2 * L.margin) / cell);
    const full = words.map((w) => w.w.toUpperCase().replace(/\?/g, '')).join(' ');
    const fullLines = full.includes('ELIZA ') ? [full.slice(0, full.indexOf('ELIZA ') + 5), ...elizaWrap(full.slice(full.indexOf('ELIZA ') + 6), cols)] : elizaWrap(full, cols);
    // lay the typed text onto the same wrap as the full line, so words never jump lines while typing
    const typedLines = [];
    {
        let left = sung.length;
        for (const ln of fullLines) {
            if (left <= 0) break;
            const take = Math.min(ln.length, left);
            typedLines.push(ln.slice(0, take));
            left -= take + 1;
        }
    }
    const lines = [...ELIZA_PAGE.map(([s, sc]) => ({ s, sc })), ...typedLines.map((s) => ({ s, sc: 1, caps: true }))];
    if (!typedLines.length) lines.push({ s: '', sc: 1, caps: true });
    const curLine = lines.length - 1;
    // paper feed: the typing line sits one line above the platen; each new line feeds with a short ease
    const feed = (i) => {
        // time the i-th typed line began (its first character)
        let acc = 0;
        for (let k2 = 0; k2 < i; k2++) acc += fullLines[k2].length + 1;
        let tt = null, n = 0;
        for (const w of words) { const ln = w.w.length + 1; if (n + ln > acc) { tt = w.t0; break; } n += ln; }
        return tt;
    };
    const lastStart = typedLines.length > 1 ? feed(typedLines.length - 1) : null;
    const ease = lastStart !== null ? easeOut((t - lastStart) / 0.12) : 1;
    const yLine = (i) => pl - 30 - (curLine - i) * lh + (1 - ease) * lh;
    const topY = yLine(0) - lh;
    g.save();
    g.beginPath(); g.rect(px, -10, pw, pl + 4); g.clip();
    g.fillStyle = ELZ.paper; g.fillRect(px, Math.min(-10, topY - 400), pw, pl + 420);
    // green bars: every other band of three lines, locked to the text lines
    g.fillStyle = ELZ.bar;
    for (let i = -12; i < lines.length + 2; i++) {
        if (((Math.floor(i / 3) % 2) + 2) % 2 === 0) g.fillRect(px + 34, yLine(i) - lh * 0.72, pw - 68, lh);
    }
    g.fillStyle = 'rgba(40,110,50,0.35)'; g.fillRect(px + 33, -10, 1.5, pl + 20); g.fillRect(px + pw - 34, -10, 1.5, pl + 20);
    g.fillStyle = '#1b2a2f';
    for (let i = -12; i < lines.length + 2; i++) {
        const y = yLine(i) - lh * 0.22;
        g.beginPath(); g.arc(px + 16, y, 6, 0, TAU); g.arc(px + pw - 16, y, 6, 0, TAU); g.fill();
    }
    // the stamp, on the paper's head
    paintStampCached(g, W, H, px + pw - 150, yLine(1) + 12, 78);
    // typed text: monospaced cells, ink varies a little per strike, baselines wander a hair
    g.textAlign = 'center'; g.textBaseline = 'alphabetic';
    for (let i = 0; i < lines.length; i++) {
        const { s, sc } = lines[i];
        if (!s) continue;
        const y = yLine(i), cw2 = cell * sc;
        g.font = font(L.fs * sc, 'Special Elite');
        for (let c = 0; c < s.length; c++) {
            const ch = s[c];
            if (ch === ' ') continue;
            const hsh = hash(i * 131 + c * 7 + 3);
            g.fillStyle = `rgba(29,31,36,${0.72 + 0.28 * hsh})`;
            g.fillText(ch, px + L.margin + (c + 0.5) * cw2, y + (hsh - 0.5) * 2.2);
        }
    }
    g.restore();
    // the type element: sits at the next cell of the current line and flicks up as each character strikes
    const curS = lines[curLine].s;
    const hx = px + L.margin + (curS.length + 0.5) * cell;
    const strike = strikePhase(words, t);
    g.fillStyle = '#23272c';
    g.beginPath(); g.roundRect(hx - 22, pl - 6 - (1 - strike) * 8 * v, 44, 40, 8); g.fill();
    g.fillStyle = '#8b9299'; g.fillRect(hx - 24, pl + 26, 48, 6);
    g.fillStyle = `rgba(200,50,46,${0.4 + 0.6 * v})`; g.fillRect(hx - 18, pl - 10, 36, 5);             // ribbon
    g.textAlign = 'left';
    g.setTransform(1, 0, 0, 1, 0, 0);
}
function paintStampCached(g, W, H, cx, cy, r) {
    const s = sprite('mac-stamp', W, H, r * 2.4, r * 2.4, (sg) => paintStamp(sg, r * 1.2, r * 1.2, r));
    drawSprite(g, s, cx - r * 1.2, cy - r * 1.2);
}

// 0 = a character just struck, rising to 1 between strikes (1 when no word is being typed)
function strikePhase(words, t) {
    for (let i = words.length - 1; i >= 0; i--) {
        const w = words[i];
        if (w.t0 > t) continue;
        const span = Math.max(0.05, (w.t1 - w.t0) * 0.85), per = span / Math.max(1, w.w.length);
        return t - w.t0 < span ? fract((t - w.t0) / per) : 1;
    }
    return 1;
}

// ================================================================== 1978 · SPEAK & SPELL
// Box art on the toy's own red-orange plastic: the black band with speaker slots and the vacuum-fluorescent
// display (eight slanted 14-segment cells, unlit segments ghosting behind the mesh), TEXAS INSTRUMENTS; the
// yellow panel with the blue key field (vowels yellow, consonants orange, function keys red, as on the 1978
// unit); a hand-drawn homage of the Speak & Spell logo in its 1978 colouring (flat red "Speak", blue "& Spell"
// with a dark keyline); the TI Texas mark. The
// display shows each sung word, then spells L... O... V... E on the lyric's times while those keys go down and
// rainbow toy blocks drop in to spell it again.
const SSC = { case: '#e5431f', case2: '#c7331a', black: '#0b0d0d', yellow: '#fdd22a', blue: '#1f9fe0', orange: '#f58a22', keyY: '#ffd83a', keyR: '#e8321f', vfd: '#5ff3ff', vfdCore: '#e6ffff', red: '#e2261c', logoRed: '#dd3b1e', logoBlue: '#1f93d3', logoLine: '#143f4f' };
// 14-segment glyphs (a b c d e f g1 g2 + diagonals h j k m, centre verticals i l)
const SEG14 = {
    A: 'abcefGH', B: 'abcdilH', C: 'adef', D: 'abcdil', E: 'adefG', F: 'aefG', G: 'acdefH', H: 'bcefGH', I: 'adil', J: 'bcde',
    K: 'efGjm', L: 'def', M: 'bcefhj', N: 'bcefhm', O: 'abcdef', P: 'abefGH', Q: 'abcdefm', R: 'abefGHm', S: 'acdfGH',
    T: 'ail', U: 'bcdef', V: 'efkj', W: 'bcefkm', X: 'hjkm', Y: 'hjl', Z: 'adjk', '0': 'abcdefjk', '1': 'bc', '2': 'abdeGH',
    '3': 'abcdH', '4': 'bcfGH', '5': 'acdfGH', '6': 'acdefGH', '7': 'abc', '8': 'abcdefGH', '9': 'abcdfGH', '-': 'GH', "'": 'i',
};
// segment geometry in a cell of width w, height h (origin top-left, unslanted); G = g1, H = g2
function segLines(w, h) {
    const m = w * 0.08, cx = w / 2, cy = h / 2;
    return {
        a: [m, 0, w - m, 0], d: [m, h, w - m, h], f: [0, m, 0, cy - m], b: [w, m, w, cy - m], e: [0, cy + m, 0, h - m], c: [w, cy + m, w, h - m],
        G: [m, cy, cx - m * 0.6, cy], H: [cx + m * 0.6, cy, w - m, cy], i: [cx, m * 1.2, cx, cy - m], l: [cx, cy + m, cx, h - m * 1.2],
        h: [m * 1.4, m * 1.6, cx - m * 0.9, cy - m * 1.1], j: [w - m * 1.4, m * 1.6, cx + m * 0.9, cy - m * 1.1],
        k: [cx - m * 0.9, cy + m * 1.1, m * 1.4, h - m * 1.6], m: [cx + m * 0.9, cy + m * 1.1, w - m * 1.4, h - m * 1.6],
    };
}
function drawSegChar(g, ch, x, y, w, h, lit, glow, lw) {
    const L = segLines(w, h), on = SEG14[ch] || '';
    const sk = -0.13;                                                       // the slant
    const P = (px, py) => [x + px + (h - py) * -sk, y + py];
    g.lineCap = 'round';
    // ghosts: every unlit segment, barely there behind the mesh
    g.strokeStyle = 'rgba(70,160,150,0.10)'; g.lineWidth = lw;
    g.beginPath();
    for (const k of Object.keys(L)) { if (on.includes(k) && lit > 0) continue; const [x0, y0, x1, y1] = L[k]; const a = P(x0, y0), b = P(x1, y1); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); }
    g.stroke();
    if (!on || lit <= 0) return;
    const path = () => { g.beginPath(); for (const k of on) { const [x0, y0, x1, y1] = L[k]; const a = P(x0, y0), b = P(x1, y1); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); } };
    g.save(); g.globalCompositeOperation = 'lighter';
    path(); g.strokeStyle = `rgba(60,230,255,${0.16 * lit * (1 + glow)})`; g.lineWidth = lw * 4.2; g.stroke();
    path(); g.strokeStyle = `rgba(80,240,255,${0.35 * lit * (1 + glow * 0.5)})`; g.lineWidth = lw * 2.1; g.stroke();
    path(); g.strokeStyle = `rgba(220,255,255,${0.95 * lit})`; g.lineWidth = lw * 0.95; g.stroke();
    g.restore();
}

// the logo homage: bouncy monoline letters, round-capped, outlined white, on a drop shadow
// skeletons in an em of 100 (baseline y = 100, x-height ~46), stroked round-capped; the short strokes are the
// bracketed slab serifs of the 1978 logo's chunky bouncing letters (double-storey a, serifed p/k/l, S terminals)
const SS_GLYPH = {
    S: [[['M', 72, 18], ['C', 58, 0, 14, 4, 18, 30], ['C', 22, 52, 80, 48, 80, 74], ['C', 80, 100, 30, 106, 12, 86]], [['M', 73, 6], ['L', 73, 24]], [['M', 11, 80], ['L', 11, 98]], 92],
    p: [[['M', 18, 46], ['L', 18, 128]], [['M', 18, 60], ['C', 30, 40, 72, 42, 72, 70], ['C', 72, 98, 30, 102, 18, 84]], [['M', 3, 128], ['L', 34, 128]], [['M', 5, 50], ['L', 18, 46]], 84],
    e: [[['M', 16, 72], ['L', 70, 70], ['C', 72, 40, 18, 38, 16, 70], ['C', 14, 100, 56, 106, 72, 90]], 84],
    a: [[['M', 22, 56], ['C', 30, 40, 66, 38, 66, 62], ['L', 66, 100]], [['M', 66, 70], ['C', 34, 64, 14, 74, 16, 88], ['C', 18, 104, 56, 104, 66, 88]], [['M', 60, 100], ['L', 78, 100]], 86],
    k: [[['M', 18, 0], ['L', 18, 100]], [['M', 60, 48], ['L', 22, 78]], [['M', 38, 70], ['L', 68, 100]], [['M', 4, 1], ['L', 18, 0]], [['M', 4, 100], ['L', 32, 100]], [['M', 52, 48], ['L', 74, 48]], [['M', 58, 100], ['L', 82, 100]], 84],
    '&': [[['M', 84, 100], ['L', 30, 42], ['C', 12, 20, 30, 0, 46, 4], ['C', 64, 10, 58, 36, 36, 50], ['C', 8, 68, 16, 102, 46, 100], ['C', 64, 99, 76, 88, 82, 66]], 92],
    l: [[['M', 22, 0], ['L', 22, 100]], [['M', 8, 1], ['L', 22, 0]], [['M', 7, 100], ['L', 38, 100]], 46],
};
function ssGlyphPath(g, ch, x, y, s) {
    const G = SS_GLYPH[ch];
    g.beginPath();
    for (let i = 0; i < G.length - 1; i++) {
        for (const [op, ...a] of G[i]) {
            if (op === 'M') g.moveTo(x + a[0] * s, y + a[1] * s);
            else if (op === 'L') g.lineTo(x + a[0] * s, y + a[1] * s);
            else g.bezierCurveTo(x + a[0] * s, y + a[1] * s, x + a[2] * s, y + a[3] * s, x + a[4] * s, y + a[5] * s);
        }
    }
    return G[G.length - 1] * s;
}
// The 1978 colouring (from the unit's own panel): "Speak" in flat red-orange straight onto the yellow, no keyline;
// "& Spell" in mid blue with a thin dark teal outline; a small TM after Spell. Each word climbs a little to the
// right and its letters bob, as on the toy.
function paintSSLogo(g, x, y, s) {
    const line = (word, x0, y0, sc, fill, outline, tilt) => {
        let cx = 0;
        const pos = [];
        for (let i = 0; i < word.length; i++) {
            const ch = word[i], bob = Math.sin(i * 2.1 + x0 * 0.01) * 6 * s, rot = Math.sin(i * 1.7 + 1) * 0.06;
            pos.push([ch, cx, bob, rot]);
            cx += SS_GLYPH[ch][SS_GLYPH[ch].length - 1] * s * sc * 0.95 + 6 * s;
        }
        g.save(); g.translate(x0, y0); g.rotate(tilt);
        for (const pass of outline ? [0, 1] : [1]) {
            for (const [ch, px, py, rot] of pos) {
                g.save(); g.translate(px, py); g.rotate(rot);
                ssGlyphPath(g, ch, 0, 0, s * sc);
                g.lineCap = 'round'; g.lineJoin = 'round';
                g.strokeStyle = pass === 0 ? outline : fill; g.lineWidth = (pass === 0 ? 30 : 24) * s * sc;
                g.stroke();
                g.restore();
            }
        }
        g.restore();
        return [x0 + Math.cos(tilt) * cx, y0 + Math.sin(tilt) * cx];
    };
    line('Speak', x, y, 1, SSC.logoRed, null, -0.07);
    const [ax] = line('&', x + 104 * s, y + 118 * s, 0.9, SSC.logoBlue, SSC.logoLine, -0.05);
    const [ex, ey] = line('Spell', ax + 8 * s, y + 116 * s, 1, SSC.logoBlue, SSC.logoLine, -0.05);
    g.fillStyle = SSC.logoLine; g.font = font(30 * s, 'Rajdhani'); g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.fillText('\u2122', ex + 4 * s, ey + 24 * s);                    // word origins are em tops: the TM sits by the l's cap
}
// Texas + "ti": Texas Instruments' mark, drawn from the state's outline (lon/lat -> box)
const TEXAS = [[27.5, 0], [50.4, 0], [50.4, 18.7], [55, 20.5], [60, 20.2], [64, 22.4], [69, 21.8], [74, 24.1], [79, 23.6], [84, 26.2], [89, 25.8], [95.8, 29], [96.5, 38],
    [97.7, 50], [97.7, 63.6], [90, 67], [85, 70.5], [80.9, 73.9], [75, 77.5], [70.2, 81.3], [69.6, 88], [72.5, 99], [66, 96.5], [60, 91], [54.2, 84], [49, 76],
    [43.5, 66.4], [38, 64], [33, 64.5], [28.2, 68], [25.9, 70.4], [21.5, 68], [16.8, 64.9], [11, 58], [6, 51], [0.8, 44], [27.5, 42]];
function paintTI(g, x, y, s, color) {
    g.save(); g.translate(x, y); g.scale(s / 100, s / 100);
    g.strokeStyle = color; g.fillStyle = color; g.lineWidth = 5.5; g.lineJoin = 'round';
    g.beginPath(); TEXAS.forEach(([px, py], i) => (i ? g.lineTo(px, py) : g.moveTo(px, py))); g.closePath(); g.stroke();
    // "ti": the t's crossbar left of its stem, the stem hooking right into the i; the i's dot above
    g.lineWidth = 9; g.lineCap = 'round';
    g.beginPath(); g.moveTo(47, 30); g.lineTo(47, 60); g.quadraticCurveTo(47, 74, 58, 74); g.quadraticCurveTo(66, 74, 66, 64); g.lineTo(66, 40); g.stroke();
    g.beginPath(); g.moveTo(38, 40); g.lineTo(56, 40); g.stroke();
    g.beginPath(); g.arc(70, 24, 5.5, 0, TAU); g.fill();
    g.restore();
}

const SS_KEYS = [
    [['OFF', 'r'], ['GO', 'r'], ['↵', 'r'], ['//', 'r'], ['—', 'r'], ['?', 'r'], ['●', 'r'], ['??', 'r'], ['☺', 'r'], ['ON', 'r']],
    'ABCDEFGHIJ'.split('').map((c) => [c, 'AEIOU'.includes(c) ? 'y' : 'o']),
    'KLMNOPQRST'.split('').map((c) => [c, 'AEIOU'.includes(c) ? 'y' : 'o']),
    [...'UVWXYZ'.split('').map((c) => [c, 'AEIOU'.includes(c) ? 'y' : 'o']), ["'", 'r'], ['#', 'r'], ['\\', 'r'], ['↑', 'r']],
];
const SS_L = { band: [80, 40, 1760, 232], disp: [600, 70, 1180, 172], panel: [80, 300, 1760, 480], field: [130, 326, 1660, 290], logo: [166, 640, 0.56], ti: [1612, 628, 144] };
const ssKeyRect = (r, c) => { const [fx, fy, fw] = SS_L.field; const kw = (fw - 60) / 10; return [fx + 30 + c * kw + 8, fy + 20 + r * 66, kw - 16, 54]; };
function paintSSKey(g, x, y, w, h, kind, label, down) {
    const col = kind === 'y' ? SSC.keyY : kind === 'r' ? SSC.keyR : SSC.orange;
    g.fillStyle = 'rgba(0,30,60,0.45)'; g.beginPath(); g.roundRect(x + 3, y + 6, w, h, 16); g.fill();
    const kg = g.createLinearGradient(0, y, 0, y + h);
    kg.addColorStop(0, down ? '#fff6c0' : '#ffffff'); kg.addColorStop(0.12, col); kg.addColorStop(1, down ? col : shadeHex(col, -0.18));
    g.fillStyle = kg; g.beginPath(); g.roundRect(x, y + (down ? 4 : 0), w, h, 16); g.fill();
    const cx = x + w / 2, cy = y + h / 2 + 2 + (down ? 4 : 0);
    const ink = kind === 'r' ? '#fff4e6' : '#1b1410';
    g.fillStyle = ink; g.strokeStyle = ink; g.lineCap = 'round'; g.lineJoin = 'round';
    if (label === '↵') {                                  // REPLAY: a return arrow
        g.lineWidth = 5; g.beginPath(); g.moveTo(cx + 14, cy - 12); g.lineTo(cx + 14, cy + 4); g.lineTo(cx - 12, cy + 4); g.stroke();
        g.beginPath(); g.moveTo(cx - 20, cy + 4); g.lineTo(cx - 9, cy - 5); g.lineTo(cx - 9, cy + 13); g.closePath(); g.fill();
    } else if (label === '●') {                           // SECRET CODE: a keyhole
        g.beginPath(); g.arc(cx, cy - 6, 8, 0, TAU); g.fill();
        g.beginPath(); g.moveTo(cx - 5, cy - 2); g.lineTo(cx + 5, cy - 2); g.lineTo(cx + 8, cy + 15); g.lineTo(cx - 8, cy + 15); g.closePath(); g.fill();
    } else if (label === '☺') {                           // SAY IT: the smiling face
        g.fillStyle = '#fff4e6'; g.beginPath(); g.arc(cx, cy, 17, 0, TAU); g.fill();
        g.fillStyle = '#1b1410'; g.beginPath(); g.arc(cx - 6, cy - 5, 3, 0, TAU); g.arc(cx + 6, cy - 5, 3, 0, TAU); g.fill();
        g.lineWidth = 3.5; g.strokeStyle = '#1b1410'; g.beginPath(); g.arc(cx, cy + 1, 9, 0.15 * Math.PI, 0.85 * Math.PI); g.stroke();
    } else if (label === '↑') {                           // ENTER: up arrow
        g.lineWidth = 6; g.beginPath(); g.moveTo(cx, cy + 14); g.lineTo(cx, cy - 6); g.stroke();
        g.beginPath(); g.moveTo(cx, cy - 17); g.lineTo(cx - 11, cy - 3); g.lineTo(cx + 11, cy - 3); g.closePath(); g.fill();
    } else {
        g.font = font(label.length > 2 ? 22 : 36, 'Rajdhani'); g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(label, cx, cy);
    }
    g.lineCap = 'butt'; g.lineJoin = 'miter';
}
function shadeHex(hex, k) {
    const n = parseInt(hex.slice(1), 16), r = n >> 16, g2 = (n >> 8) & 255, b = n & 255;
    const f = (c) => Math.max(0, Math.min(255, Math.round(k < 0 ? c * (1 + k) : c + (255 - c) * k)));
    return `rgb(${f(r)},${f(g2)},${f(b)})`;
}
function ssBackground(g, W, H) {
    const { k, ox, oy } = frame(W, H);
    const bg = g.createLinearGradient(0, 0, 0, H);
    bg.addColorStop(0, '#f0552a'); bg.addColorStop(0.5, SSC.case); bg.addColorStop(1, SSC.case2);
    g.fillStyle = bg; g.fillRect(0, 0, W, H);
    g.setTransform(k, 0, 0, k, ox, oy);
    // moulded plastic: a soft sheen and a fine texture
    const sh = g.createRadialGradient(480, -200, 50, 480, -200, 1300);
    sh.addColorStop(0, 'rgba(255,255,255,0.22)'); sh.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = sh; g.fillRect(-400, 0, 2720, 800);
    // the black band: speaker slots, the display window, TEXAS INSTRUMENTS
    const [bx, by, bw, bh] = SS_L.band;
    g.fillStyle = 'rgba(80,10,0,0.35)'; g.beginPath(); g.roundRect(bx + 4, by + 8, bw, bh, 22); g.fill();
    g.fillStyle = SSC.black; g.beginPath(); g.roundRect(bx, by, bw, bh, 22); g.fill();
    const gl = g.createLinearGradient(0, by, 0, by + bh);
    gl.addColorStop(0, 'rgba(255,255,255,0.12)'); gl.addColorStop(0.08, 'rgba(255,255,255,0.02)'); gl.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gl; g.beginPath(); g.roundRect(bx, by, bw, bh, 22); g.fill();
    for (let i = 0; i < 9; i++) {
        g.fillStyle = '#000'; g.beginPath(); g.roundRect(bx + 44, by + 30 + i * 20, 420, 10, 5); g.fill();
        g.fillStyle = 'rgba(255,255,255,0.07)'; g.fillRect(bx + 50, by + 41 + i * 20, 408, 1.5);
    }
    const [dx, dy, dw, dh] = SS_L.disp;
    g.fillStyle = '#040606'; g.beginPath(); g.roundRect(dx - 20, dy - 16, dw + 40, dh + 32, 12); g.fill();
    g.strokeStyle = 'rgba(80,120,120,0.18)'; g.lineWidth = 1;
    for (let x = dx; x < dx + dw; x += 7) { g.beginPath(); g.moveTo(x, dy - 8); g.lineTo(x + 8, dy + dh + 8); g.stroke(); }
    g.fillStyle = '#c9ccd0';
    smallCaps(g, 'TEXAS INSTRUMENTS', bx + bw - 30, by + bh - 14, 28, 'Rajdhani', 'right');
    // the yellow panel and the blue key field
    const [px, py, pw, ph] = SS_L.panel;
    g.fillStyle = 'rgba(90,15,0,0.35)'; g.beginPath(); g.roundRect(px + 5, py + 9, pw, ph, 36); g.fill();
    g.fillStyle = SSC.yellow; g.beginPath(); g.roundRect(px, py, pw, ph, 36); g.fill();
    const [fx, fy, fw, fh] = SS_L.field;
    g.fillStyle = SSC.case; g.beginPath(); g.roundRect(fx - 12, fy - 10, fw + 24, fh + 20, 34); g.fill();
    g.fillStyle = SSC.blue; g.beginPath(); g.roundRect(fx, fy, fw, fh, 26); g.fill();
    const labels = ['REPLAY', 'REPEAT', 'CLUE', 'MYSTERY WORD', 'SECRET CODE', 'LETTER', 'SAY IT', 'SPELL'];
    g.fillStyle = '#123a5c'; g.font = font(13, 'Rajdhani'); g.textAlign = 'center';
    labels.forEach((lb, i) => { const [x, y, w] = ssKeyRect(0, i + 2); g.fillText(lb, x + w / 2, y - 4); });
    for (let r = 0; r < 4; r++) for (let c = 0; c < 10; c++) { const [x, y, w, h] = ssKeyRect(r, c); paintSSKey(g, x, y, w, h, SS_KEYS[r][c][1], SS_KEYS[r][c][0], false); }
    // the logo, the TI mark and its name
    paintSSLogo(g, SS_L.logo[0], SS_L.logo[1], SS_L.logo[2]);
    const [tx, ty, ts] = SS_L.ti;
    paintTI(g, tx, ty, ts, SSC.red);
    g.fillStyle = SSC.red;
    smallCaps(g, 'TEXAS INSTRUMENTS', tx - 24, ty + 70, 34, 'Rajdhani', 'right');
    g.fillStyle = 'rgba(120,70,0,0.8)'; g.font = font(15, 'Rajdhani'); g.textAlign = 'left';
    g.fillText('© TI 1978', SS_L.logo[0] + 4, SS_L.logo[1] - 14);
    // a 1970s rainbow stripe: the shelf the letter blocks land on
    const RB = ['#e8321f', '#f47c20', '#f7c21b', '#3cb44a', '#2f7fd8'];
    for (let i = 0; i < RB.length; i++) { g.fillStyle = RB[i]; g.beginPath(); g.roundRect(700, 728 + i * 8.5, 640, 6.5, 3.2); g.fill(); }
}
const RAINBOW = ['#e8321f', '#f7a21b', '#3cb44a', '#2f7fd8'];
function drawSpeakSpell(g, W, H, t, st) {
    st = stDefaults(st);
    const u = st.u, v = clamp(st.voice), kick = clamp(st.kick);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.putImageData(bgLayer('speakspell', W, H, ssBackground), 0, 0);
    toDesign(g, W, H);
    const words = lineWords(t, st, 'I was a toy made to spell and I spelled L O V E');
    const wi = wordIndex(words, t);
    // the spelled letters: single-letter words after "spelled"
    const sp = words.findIndex((w) => /^spelled$/i.test(w.w));
    const letters = sp >= 0 ? words.slice(sp + 1).filter((w) => /^[A-Za-z]$/.test(w.w)) : [];
    const nLet = letters.filter((w) => w.t0 <= t).length;
    let text = '';
    if (nLet > 0) text = letters.slice(0, nLet).map((w) => w.w.toUpperCase()).join('');
    else if (wi >= 0 && t < words[wi].t1 + 0.1) text = words[wi].w.toUpperCase().replace(/[^A-Z0-9']/g, '').slice(0, 8);

    // ---- the VFD: eight slanted cells; the newest spelled letter flashes as it lands
    const [dx, dy, dw, dh] = SS_L.disp;
    const cellW = dw / 8, cw = cellW * 0.62, ch = dh * 0.78, lw = 7.5;
    const lastT = nLet > 0 ? letters[nLet - 1].t0 : (wi >= 0 ? words[wi].t0 : -9);
    const flash = Math.exp(-(t - lastT) / 0.18);
    for (let i = 0; i < 8; i++) {
        const c = text[i] || ' ';
        const lit = c !== ' ' ? 1 : 0;
        const isNew = nLet > 0 && i === nLet - 1;
        drawSegChar(g, c, dx + i * cellW + (cellW - cw) / 2, dy + (dh - ch) / 2, cw, ch, lit, (isNew ? flash * 1.6 : 0) + 0.3 * v, lw);
    }
    // ---- keys going down: L O V E as spelled, or the letters of the word being sung, one by one
    const downs = new Set();
    if (nLet > 0) { const w = letters[nLet - 1]; if (t < w.t1) downs.add(w.w.toUpperCase()); }
    else if (wi >= 0 && t < words[wi].t1) {
        const w = words[wi], s = w.w.toUpperCase().replace(/[^A-Z]/g, '');
        if (s) downs.add(s[Math.min(s.length - 1, Math.floor(((t - w.t0) / Math.max(0.05, w.t1 - w.t0)) * s.length))]);
    }
    for (let r = 1; r < 4; r++) for (let c = 0; c < 10; c++) {
        const lab = SS_KEYS[r][c][0];
        if (!downs.has(lab)) continue;
        const [x, y, w, h] = ssKeyRect(r, c);
        g.fillStyle = SSC.blue; g.fillRect(x - 3, y - 2, w + 8, h + 12);
        paintSSKey(g, x, y, w, h, SS_KEYS[r][c][1], lab, true);
        g.save(); g.globalCompositeOperation = 'lighter';
        const gr = g.createRadialGradient(x + w / 2, y + h / 2, 4, x + w / 2, y + h / 2, 90);
        gr.addColorStop(0, 'rgba(255,240,170,0.7)'); gr.addColorStop(1, 'rgba(255,240,170,0)');
        g.fillStyle = gr; g.fillRect(x + w / 2 - 90, y + h / 2 - 90, 180, 180);
        g.restore();
    }
    // the SAY IT key's smile lights with the voice
    {
        const [x, y, w, h] = ssKeyRect(0, 8);
        g.save(); g.globalCompositeOperation = 'lighter'; g.globalAlpha = 0.25 + 0.6 * v;
        const gr = g.createRadialGradient(x + w / 2, y + h / 2, 2, x + w / 2, y + h / 2, 60);
        gr.addColorStop(0, 'rgba(255,230,160,1)'); gr.addColorStop(1, 'rgba(255,230,160,0)');
        g.fillStyle = gr; g.fillRect(x + w / 2 - 60, y + h / 2 - 60, 120, 120);
        g.restore();
    }
    // ---- rainbow toy blocks: L O V E drop onto the panel as each is spelled
    for (let i = 0; i < letters.length && i < 4; i++) {
        const w = letters[i];
        const a = t - w.t0;
        if (a < 0) continue;
        const land = clamp(a / 0.22);
        const bounce = land < 1 ? (1 - land * land) : Math.abs(Math.sin((a - 0.22) * 14)) * Math.exp(-(a - 0.22) * 7) * 0.12;
        const S = 92, x = 790 + i * (S + 38), y = 632 - bounce * 170;
        const col = RAINBOW[i % 4];
        g.save(); g.translate(x + S / 2, y + S / 2); g.rotate((1 - land) * (i % 2 ? 0.35 : -0.35) + Math.sin(i * 3) * 0.05); g.translate(-S / 2, -S / 2);
        g.fillStyle = 'rgba(100,40,0,0.35)'; g.beginPath(); g.roundRect(6, 10, S, S, 12); g.fill();
        g.fillStyle = shadeHex(col, -0.25); g.beginPath(); g.moveTo(S, 10); g.lineTo(S + 14, -4); g.lineTo(S + 14, S - 14); g.lineTo(S, S); g.closePath(); g.fill();
        g.fillStyle = shadeHex(col, 0.35); g.beginPath(); g.moveTo(0, 0); g.lineTo(14, -14); g.lineTo(S + 14, -14); g.lineTo(S, 0); g.closePath(); g.fill();
        g.fillStyle = col; g.beginPath(); g.roundRect(0, 0, S, S, 10); g.fill();
        g.strokeStyle = 'rgba(255,255,255,0.7)'; g.lineWidth = 5; g.beginPath(); g.roundRect(9, 9, S - 18, S - 18, 7); g.stroke();
        g.fillStyle = '#fffdf2'; g.font = font(76, 'Rajdhani'); g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(w.w.toUpperCase(), S / 2, S / 2 + 4);
        g.restore();
    }
    // the kick: the band's edge catches light
    if (kick > 0.05) {
        const [bx, by, bw] = SS_L.band;
        g.fillStyle = `rgba(255,255,255,${0.12 * kick})`; g.beginPath(); g.roundRect(bx, by, bw, 8, 4); g.fill();
    }
    g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.setTransform(1, 0, 0, 1, 0, 0);
}

// small caps: each word's first letter full size, the rest at 0.76 (TI's wordmark style)
function smallCaps(g, text, x, y, px, fam, align = 'left') {
    const parts = [];
    for (const w of text.split(' ')) { parts.push([w[0], px]); parts.push([w.slice(1), px * 0.76]); parts.push([' ', px * 0.76]); }
    parts.pop();
    let wsum = 0;
    for (const [s2, p] of parts) { g.font = font(p, fam); wsum += g.measureText(s2).width + s2.length * p * 0.06; }
    let cx = align === 'right' ? x - wsum : align === 'center' ? x - wsum / 2 : x;
    g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    for (const [s2, p] of parts) { g.font = font(p, fam); g.letterSpacing = `${p * 0.06}px`; g.fillText(s2, cx, y); cx += g.measureText(s2).width + s2.length * p * 0.06; }
    g.letterSpacing = '0px';
}

// ================================================================== 1982 · S.A.M. ON A C64
// Drawn at the C64's own resolution (a 320x200 text screen inside its border, 8x8 characters) and scaled up
// with nearest-neighbour, so every pixel is a C64 pixel. The boot screen, LOAD"SAM",8,1, SEARCHING FOR SAM,
// LOADING, READY., RUN — then S.A.M. speaks: a PETSCII-mosaic mouth that opens with the voice, raster bars in
// the border, "two sines and a square" plotted from SAM's own formant tables (see SOURCES.md; F1/F2/F3 and
// 4-bit amplitudes per vowel), the words along the bottom. A Commodore C= homage and a 1541's busy LED sit in
// the side border. Text is pixel art: an 8x8 glyph table of the C64 character ROM's letterforms (drawn, checked
// against the public-domain charset chart), because Press Start 2P fills its whole cell and letters merge.
const C64P = ['#000000', '#FFFFFF', '#813338', '#75CEC8', '#8E3C97', '#56AC4D', '#2E2C9B', '#EDF171', '#8E5029', '#553800', '#C46C71', '#4A4A4A', '#7B7B7B', '#A9FF9F', '#706DEB', '#B2B2B2'];
const C64_GLYPHS = {
    '@': '3C666E6E60623C00', A: '183C667E66666600', B: '7C66667C66667C00', C: '3C66606060663C00', D: '786C6666666C7800', E: '7E60607860607E00',
    F: '7E60607860606000', G: '3C66606E66663C00', H: '6666667E66666600', I: '3C18181818183C00', J: '1E0C0C0C0C6C3800', K: '666C7870786C6600',
    L: '6060606060607E00', M: '63777F6B63636300', N: '66767E7E6E666600', O: '3C66666666663C00', P: '7C66667C60606000', Q: '3C666666663C0E00',
    R: '7C66667C786C6600', S: '3C66603C06663C00', T: '7E18181818181800', U: '6666666666663C00', V: '66666666663C1800', W: '6363636B7F776300',
    X: '66663C183C666600', Y: '6666663C18181800', Z: '7E060C1830607E00', ' ': '0000000000000000', '!': '1818181800001800', '"': '6666660000000000',
    '#': '6666FF66FF666600', '$': '183E603C067C1800', '%': '62660C1830664600', '&': '3C663C3867663F00', "'": '060C180000000000', '(': '0C18303030180C00',
    ')': '30180C0C0C183000', '*': '00663CFF3C660000', '+': '0018187E18180000', ',': '0000000000181830', '-': '0000007E00000000', '.': '0000000000181800',
    '/': '0003060C18306000', '0': '3C666E7666663C00', '1': '1818381818187E00', '2': '3C66060C30607E00', '3': '3C66061C06663C00', '4': '060E1E667F060600',
    '5': '7E607C0606663C00', '6': '3C66607C66663C00', '7': '7E660C1818181800', '8': '3C66663C66663C00', '9': '3C66663E06663C00', ':': '0000180000180000',
    ';': '0000180000181830', '<': '0E18306030180E00', '=': '00007E007E000000', '>': '70180C060C187000', '?': '3C66060C18001800',
};
// a glyph atlas per colour: one 8-px cell per character, in insertion order
const C64_ORDER = Object.keys(C64_GLYPHS);
function c64Atlas(color) {
    return cached('c64atlas:' + color, 0, 0, () => {
        const c = mk(C64_ORDER.length * 8, 8), g = c.getContext('2d');
        g.fillStyle = color;
        C64_ORDER.forEach((ch, i) => {
            const hex = C64_GLYPHS[ch];
            for (let r = 0; r < 8; r++) {
                const bits = parseInt(hex.substr(r * 2, 2), 16);
                for (let p = 0; p < 8; p++) if (bits & (128 >> p)) g.fillRect(i * 8 + p, r, 1, 1);
            }
        });
        return c;
    });
}
function c64Text(g, s, x, y, color, rev = null) {
    const at = c64Atlas(color);
    for (let i = 0; i < s.length; i++) {
        const k = C64_ORDER.indexOf(s[i]);
        if (rev) { g.fillStyle = rev; g.fillRect(x + i * 8, y, 8, 8); }
        if (k >= 0 && s[i] !== ' ') g.drawImage(at, k * 8, 0, 8, 8, x + i * 8, y, 8, 8);
    }
}
function c64Text2(g, s, x, y, color, bg) {              // reverse video: the cell in `color`, the glyph cut out in `bg`
    g.fillStyle = color; g.fillRect(x, y, s.length * 8, 8);
    c64Text(g, s, x, y, bg);
}
// SAM's vowel formants (render tables; F in internal steps, A 4-bit) — see SOURCES.md
const SAM_V = { IY: [10, 84, 110, 13, 10, 8], IH: [14, 72, 93, 13, 11, 7], EH: [18, 66, 91, 14, 13, 8], AE: [24, 62, 88, 15, 14, 8], AA: [26, 40, 89, 15, 13, 1],
    AH: [22, 44, 87, 15, 12, 1], AO: [20, 30, 88, 15, 12, 0], UH: [16, 36, 82, 15, 11, 1], UW: [12, 34, 82, 13, 8, 0], ER: [18, 48, 62, 12, 11, 5] };
const SAM_WORD = { i: 'AA', was: 'AH', a: 'AH', mouth: 'AA', made: 'EH', of: 'AH', software: 'AO', two: 'UW', sines: 'AA', and: 'AE', square: 'EH' };
function samNative(W, H) {
    return cached('sam-native', W, H, () => {
        const s = Math.max(1, Math.round(H / 267)), nw = Math.ceil(W / s), nh = Math.ceil(H / s);
        return { s, nw, nh, c: mk(nw, nh) };
    });
}
// the C= logo at native resolution (a ring cut open on the right; navy top flag, red lower flag)
function paintCBM(g, x, y, r, navy = '#0d1f5c', red = '#e02020') {
    // the C: ring between r and 0.524r, cut by a vertical at +0.28r; flags from the cut to 1.133r
    const cut = 0.28 * r, ao = Math.acos(cut / r), ai = Math.acos(cut / (0.524 * r));
    g.fillStyle = navy;
    g.beginPath(); g.arc(x, y, r, ao, TAU - ao); g.arc(x, y, r * 0.524, TAU - ai, ai, true); g.closePath(); g.fill();
    g.beginPath(); g.moveTo(x + cut, y - r * 0.444); g.lineTo(x + r * 1.133, y - r * 0.444); g.lineTo(x + r * 0.739, y - r * 0.05); g.lineTo(x + cut, y - r * 0.05); g.closePath(); g.fill();
    g.fillStyle = red;
    g.beginPath(); g.moveTo(x + cut, y + r * 0.05); g.lineTo(x + r * 0.739, y + r * 0.05); g.lineTo(x + r * 1.133, y + r * 0.444); g.lineTo(x + cut, y + r * 0.444); g.closePath(); g.fill();
}
function drawSam(g, W, H, t, st) {
    st = stDefaults(st);
    const u = st.u, v = clamp(st.voice), kick = clamp(st.kick);
    const N = samNative(W, H), ng = N.c.getContext('2d');
    const nw = N.nw, nh = N.nh, dx = Math.floor((nw - 320) / 2), dy = Math.floor((nh - 200) / 2);
    const LB = C64P[14], BL = C64P[6];
    const words = lineWords(t, st, 'I was a mouth made of software two sines and a square');
    const RUN_AT = 2.02;
    const running = u >= RUN_AT;
    ng.imageSmoothingEnabled = false;
    // ---- border
    if (!running) { ng.fillStyle = LB; ng.fillRect(0, 0, nw, nh); }
    else {                                                                 // raster bars on black
        ng.fillStyle = '#000'; ng.fillRect(0, 0, nw, nh);
        const bars = [[6, 14, 3, 1, 3, 14, 6], [2, 10, 7, 1, 7, 10, 2], [9, 8, 7, 1, 7, 8, 9], [11, 12, 15, 1, 15, 12, 11], [4, 10, 15, 1, 15, 10, 4]];
        const ru = u - RUN_AT;
        for (let b = 0; b < bars.length; b++) {
            const y0 = Math.round(nh / 2 + Math.sin(ru * (2.1 + b * 0.37) + b * 1.3) * (nh / 2 - 12) - 7 + kick * 4 * Math.sin(b));
            const pal = bars[b];
            for (let i = 0; i < 7; i++) for (let k2 = 0; k2 < 2; k2++) { ng.fillStyle = C64P[pal[i]]; ng.fillRect(0, y0 + i * 2 + k2, nw, 1); }
        }
    }
    // side-border furniture: the C= homage + COMMODORE 64 (left), a 1541 with its busy LED (right)
    const lx = Math.floor(dx / 2);
    if (dx >= 90) {
        if (running) { ng.fillStyle = '#000'; ng.fillRect(lx - 52, dy + 14, 104, 106); ng.fillRect(dx + 320 + Math.floor(dx / 2) - 42, dy + 144, 84, 50); }
        paintCBM(ng, lx - 8, dy + 52, 28);
        c64Text(ng, 'COMMODORE', lx - 36, dy + 96, running ? C64P[1] : '#0d1f5c');
        c64Text(ng, '64', lx - 8, dy + 108, running ? C64P[1] : '#0d1f5c');
        const rx = dx + 320 + Math.floor(dx / 2);
        ng.fillStyle = '#c9c2a8'; ng.fillRect(rx - 34, dy + 150, 68, 26);
        ng.fillStyle = '#8f8870'; ng.fillRect(rx - 34, dy + 172, 68, 4);
        ng.fillStyle = '#3a3a3a'; ng.fillRect(rx - 26, dy + 158, 44, 3);
        const busy = u > 0.93 && u < 1.72;
        ng.fillStyle = busy && fract(u * 3) < 0.8 ? '#ff3020' : '#5a1810'; ng.fillRect(rx + 22, dy + 157, 5, 3);
        ng.fillStyle = '#29d02a'; ng.fillRect(rx + 22, dy + 164, 5, 2);
        c64Text(ng, '1541', rx - 16, dy + 182, running ? C64P[12] : '#1b1f60');
    }
    // ---- the screen
    ng.fillStyle = running ? '#000' : BL; ng.fillRect(dx, dy, 320, 200);
    const row = (r) => dy + r * 8, col = (c) => dx + c * 8;
    if (!running) {
        c64Text(ng, '    **** COMMODORE 64 BASIC V2 ****', col(0), row(1), LB);
        c64Text(ng, ' 64K RAM SYSTEM  38911 BASIC BYTES FREE', col(0), row(3), LB);
        c64Text(ng, 'READY.', col(0), row(5), LB);
        const cmd = 'LOAD"SAM",8,1';
        const typed = cmd.slice(0, clamp(Math.floor((u - 0.12) / 0.055) + 1, 0, cmd.length));
        let cur = null;
        if (u < 0.12) cur = [0, 6];
        else c64Text(ng, typed, col(0), row(6), LB);
        if (u >= 0.12 && u < 0.9) cur = [typed.length, 6];
        if (u >= 0.95) c64Text(ng, 'SEARCHING FOR SAM', col(0), row(8), LB);
        if (u >= 1.25) c64Text(ng, 'LOADING', col(0), row(9), LB);
        if (u >= 1.7) {
            c64Text(ng, 'READY.', col(0), row(10), LB);
            const run = 'RUN'.slice(0, clamp(Math.floor((u - 1.78) / 0.06) + 1, 0, 3));
            if (u >= 1.78) c64Text(ng, run, col(0), row(11), LB);
            cur = [u >= 1.78 ? run.length : 0, 11];
        }
        if (cur && fract(u / 0.6) < 0.5) { ng.fillStyle = LB; ng.fillRect(col(cur[0]), row(cur[1]), 8, 8); }
    } else {
        // ---- S.A.M. speaks (the program's screen here is our own illustration)
        c64Text2(ng, '  S.A.M.  SOFTWARE AUTOMATIC MOUTH  ', col(2), row(0), C64P[10], '#000');
        const wi = wordIndex(words, t), cw = wi >= 0 ? words[wi] : null;
        const vk = SAM_WORD[(cw?.w || '').toLowerCase()] || 'AH';
        const [f1, f2, f3, a1, a2, a3] = SAM_V[vk];
        // the mouth: lips rasterised in 4x4 blocks (PETSCII quarter-block mosaic)
        const mx = dx + 160, my = dy + 58, A = 92;
        const open = (cw && t < cw.t1 + 0.05 ? 1 : 0.25) * v * 22 + 2;
        const paths = new Map();                                              // one fill per colour
        for (let by = -44; by < 48; by += 4) for (let bx = -A - 4; bx < A + 4; bx += 4) {
            const x = bx + 2, y = by + 2, q = clamp(1 - (x / A) * (x / A), 0, 1);
            if (q <= 0) continue;
            const line = -9 * (1 - q);                                       // corners turn up: a smile
            const o = open * q;
            const upTop = line - 24 * Math.sqrt(q) + 7 * Math.exp(-(x / 14) * (x / 14)), upBot = line - o * 0.45;
            const loTop = line + o * 0.55, loBot = line + 26 * Math.pow(q, 0.7) + o * 0.55;
            let c = -1;
            if (y >= upTop && y < upBot) c = y > upBot - 5 ? 2 : 10;
            else if (y >= upBot && y < loTop) c = (y < upBot + Math.min(7, o * 0.5) && Math.abs(x) < A * 0.62) ? 1 : (y > loTop - 6 && Math.abs(x) < A * 0.45 ? 10 : 0);
            else if (y >= loTop && y < loBot) c = (y < loTop + 6 && Math.abs(x) < A * 0.5 && x < 10 && x > -40) ? 15 : 2;
            if (c < 0) continue;
            if (!paths.has(c)) paths.set(c, []);
            paths.get(c).push(mx + bx, my + by);
        }
        for (const [c, pts] of paths) {
            ng.fillStyle = C64P[c]; ng.beginPath();
            for (let i = 0; i < pts.length; i += 2) ng.rect(pts[i], pts[i + 1], 4, 4);
            ng.fill();
        }
        // two sines and a square: SAM's three formant voices for this vowel, then their sum
        const py0 = row(13), pw = 150, ph = 16;
        const wave = (k, x) => {
            const ph2 = (t * 3 + x / pw) * TAU;
            if (k === 0) return Math.sin(ph2 * f1 / 8) * a1 / 15;
            if (k === 1) return Math.sin(ph2 * f2 / 8) * a2 / 15;
            return (Math.sin(ph2 * f3 / 8) >= 0 ? 1 : -1) * a3 / 15;
        };
        const lab = ['SIN F1', 'SIN F2', 'SQR F3'], cols = [3, 13, 7];
        for (let k2 = 0; k2 < 3; k2++) {
            const y = py0 + k2 * 22;
            c64Text(ng, lab[k2], col(1), y + 4, C64P[cols[k2]]);
            ng.fillStyle = C64P[cols[k2]];
            for (let x = 0; x < pw; x++) ng.fillRect(col(8) + x, Math.round(y + 8 - wave(k2, x) * ph * 0.5 * (0.35 + 0.65 * v)), 1, 1);
        }
        c64Text(ng, '=', col(28) - 4, py0 + 26, C64P[1]);
        ng.fillStyle = C64P[1];
        for (let x = 0; x < 88; x++) {
            const s2 = (wave(0, x * 1.7) + wave(1, x * 1.7) + wave(2, x * 1.7)) / 3;
            ng.fillRect(col(29) + x, Math.round(py0 + 30 - s2 * 26 * (0.35 + 0.65 * v)), 1, 2);
        }
        c64Text(ng, `F1 ${String(f1).padStart(2)} F2 ${String(f2).padStart(2)} F3 ${String(f3).padStart(3)}`, col(1), row(21), C64P[15]);
        c64Text(ng, `A  ${String(a1).padStart(2)}    ${String(a2).padStart(2)}    ${String(a3).padStart(3)}  ${vk}`, col(1), row(22), C64P[12]);
        // the words, the current one in reverse video
        let cx = 1;
        const sung = words.filter((w) => w.t0 >= t - u + RUN_AT - 0.15);           // the words sung since RUN
        for (const w of sung) {
            if (w.t0 > t) break;
            const s2 = w.w.toUpperCase();
            if (w === cw && t < w.t1) c64Text2(ng, s2, col(cx), row(24), C64P[7], '#000');
            else c64Text(ng, s2, col(cx), row(24), C64P[7]);
            cx += s2.length + 1;
        }
    }
    // ---- scale up: every C64 pixel becomes an s x s block
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.imageSmoothingEnabled = false;
    g.drawImage(N.c, 0, 0, nw * N.s, nh * N.s);
    g.imageSmoothingEnabled = true;
}

// ================================================================== 1984 · MACINTOSH
// The whole backdrop is a 1-bit Macintosh screen at Mac-pixel scale: the grey desktop, the menu bar with a
// rainbow-Apple homage (the only colour on the screen), MacPaint's window with its tool palette, line widths
// and pattern palette. The script "hello" is painted stroke by stroke with a stamped round brush (no
// anti-aliasing, as on the real screen) while "hello" is sung; "Hello, I am Macintosh." types in with the text
// tool (Hertzfeld's account; see SOURCES.md); "out of the bag" marches ants around the drawing, and on
// "last" the paint bucket pours a MacPaint pattern round it.
const MAC_PAT = [                                            // 8x8 patterns, one hex byte per row (1 = black)
    'FFFFFFFFFFFFFFFF', '0000000000000000', 'AA55AA55AA55AA55', '8822882288228822', 'DD77DD77DD77DD77', 'FF00FF00FF00FF00',
    'AAAAAAAAAAAAAAAA', '8040201008040201', '0102040810204080', 'FF808080FF080808', '8000080080000800', 'FF888888FF888888',
    '8142241818244281', 'F0F0F0F00F0F0F0F', '1028448201824428', 'C0C0303003030C0C', '0102040810204080', '7F7F7F7F7F7F7F00',
    'EE55BB55EE55BB55', '1144114411441144', '8888888888888888', '00FF00FF00FF00FF', 'BB77EEDDBB77EEDD', '0A0A0A0A0A0A0AFF',
];
const APPLE_PX = [
    '........##.....', '.......###.....', '......###......', '......#........', '..#####.#####..', '.#############.',
    '#############..', '############...', '###########....', '###########....', '############...', '#############..',
    '##############.', '.#############.', '.############..', '..###########..', '...####.####...'];
const APPLE_ROWCOL = ['#61bb46', '#61bb46', '#61bb46', '#61bb46', '#61bb46', '#61bb46', '#fdb827', '#fdb827', '#f5821f', '#f5821f', '#e03a3e', '#e03a3e', '#963d97', '#963d97', '#009ddc', '#009ddc', '#009ddc'];
// the script "hello": points of a connected monoline hand (0..1000 x 0..400), Catmull-Rom through them
const HELLO_PTS = [
    [30, 318], [90, 270], [150, 190], [205, 95], [228, 35], [212, 8], [182, 30], [160, 120], [140, 230], [124, 334],
    [150, 262], [196, 216], [236, 224], [252, 272], [250, 330], [280, 318],
    [318, 280], [362, 248], [370, 222], [344, 206], [306, 232], [298, 292], [332, 334], [392, 318],
    [438, 250], [484, 140], [500, 48], [482, 16], [456, 44], [446, 150], [450, 298], [478, 334], [522, 314],
    [566, 244], [608, 140], [622, 48], [604, 16], [578, 44], [568, 150], [572, 298], [600, 334], [644, 312],
    [668, 268], [700, 228], [742, 232], [758, 276], [736, 326], [694, 334], [670, 300], [690, 250], [736, 236], [800, 228], [870, 210]];
function helloSamples(step) {
    const P = HELLO_PTS, out = [];
    for (let i = 0; i < P.length - 1; i++) {
        const p0 = P[Math.max(0, i - 1)], p1 = P[i], p2 = P[i + 1], p3 = P[Math.min(P.length - 1, i + 2)];
        const len = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]), n = Math.max(2, Math.ceil(len / step));
        for (let k = 0; k < n; k++) {
            const s = k / n, s2 = s * s, s3 = s2 * s;
            const f = (a, b, c, d) => 0.5 * (2 * b + (-a + c) * s + (2 * a - 5 * b + 4 * c - d) * s2 + (-a + 3 * b - 3 * c + d) * s3);
            out.push([f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1])]);
        }
    }
    out.push(P[P.length - 1]);
    return out;
}
function macNative(W, H) {
    return cached('mac-native', W, H, () => {
        const s = Math.max(1, Math.round(H / 267)), nw = Math.ceil(W / s), nh = Math.ceil(H / s);
        const L = { s, nw, nh };
        const wx = Math.floor((nw - 512) / 2), wy = 23;
        Object.assign(L, { wx, wy, ww: 512, wh: Math.min(240, nh - 27), tool: [wx + 6, wy + 23], cv: [wx + 64, wy + 23, 442, 0] });
        L.cv[3] = L.wh - 23 - 46;                                              // canvas height leaves room for the patterns
        L.pat = [wx + 64, wy + 23 + L.cv[3] + 4];
        // the script, fitted to the canvas
        const sc = Math.min((L.cv[2] - 70) / 900, (L.cv[3] - 40) / 360);
        L.hello = helloSamples(1.2 / sc).map(([x, y]) => [Math.round(L.cv[0] + 36 + x * sc), Math.round(L.cv[1] + 8 + y * sc)]);
        L.helloBox = [L.cv[0] + 36 + 30 * sc - 8, L.cv[1] + 8 + 8 * sc - 8, 840 * sc + 16, 326 * sc + 16];
        L.base = mk(nw, nh);
        paintMacBase(L.base.getContext('2d'), L);
        threshold1bit(L.base.getContext('2d'), 0, 0, nw, 20);             // the menu bar's type, snapped to 1 bit
        threshold1bit(L.base.getContext('2d'), L.wx, L.wy, L.ww, 19);
        L.c = mk(nw, nh);
        return L;
    });
}
function patFill(g, hex, x, y, w, h) {                         // integer-aligned pattern fill, 1 = black
    g.fillStyle = '#fff'; g.fillRect(x, y, w, h);
    g.fillStyle = '#000'; g.beginPath();
    for (let yy = 0; yy < h; yy++) {
        const bits = parseInt(hex.substr(((y + yy) & 7) * 2, 2), 16);
        for (let xx = 0; xx < w; xx++) if (bits & (128 >> ((x + xx) & 7))) g.rect(x + xx, y + yy, 1, 1);
    }
    g.fill();
}
function threshold1bit(g, x, y, w, h, cut = 150) {
    const id = g.getImageData(x, y, w, h), d = id.data;
    for (let i = 0; i < d.length; i += 4) { const v = (d[i] + d[i + 1] + d[i + 2]) / 3 < cut ? 0 : 255; d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; }
    g.putImageData(id, x, y);
}
function macText(g, s, x, y, px, bold = true) {
    g.fillStyle = '#000'; g.font = font(px, 'Pixelify Sans', bold ? 'bold ' : ''); g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.fillText(s, x, y);
}
function macTool(g, i, x, y, on) {                             // the 20 MacPaint tools, 1-bit sketches in a 26x18 cell
    g.fillStyle = on ? '#000' : '#fff'; g.fillRect(x, y, 26, 18);
    g.strokeStyle = '#000'; g.lineWidth = 1; g.strokeRect(x + 0.5, y + 0.5, 25, 17);
    const c = on ? '#fff' : '#000';
    g.fillStyle = c; g.strokeStyle = c;
    const R = (a, b, w, h) => g.fillRect(x + a, y + b, w, h);
    const box = (a, b, w, h) => { R(a, b, w, 1); R(a, b + h - 1, w, 1); R(a, b, 1, h); R(a + w - 1, b, 1, h); };
    switch (i) {
        case 0: R(10, 4, 7, 1); R(8, 5, 2, 1); R(17, 5, 2, 1); R(7, 6, 1, 3); R(19, 6, 1, 3); R(8, 9, 2, 1); R(17, 9, 2, 1); R(10, 10, 7, 1); R(11, 11, 1, 2); R(10, 13, 1, 1); R(11, 14, 2, 1); break;   // lasso
        case 1: for (let k = 0; k < 12; k += 2) { R(7 + k, 4, 1, 1); R(7 + k, 13, 1, 1); } for (let k = 0; k < 10; k += 2) { R(7, 4 + k, 1, 1); R(18, 4 + k, 1, 1); } break;  // marquee
        case 2: R(9, 7, 9, 7); R(9, 4, 2, 4); R(12, 3, 2, 5); R(15, 4, 2, 4); R(18, 9, 2, 3); break;   // hand
        case 3: for (let k = 0; k < 11; k++) { R(12 - Math.floor(k / 2.2), 3 + k, 2, 1); R(13 + Math.floor(k / 2.2), 3 + k, 2, 1); } R(10, 10, 7, 1); R(7, 14, 4, 1); R(16, 14, 4, 1); break;   // A
        case 4: for (let k = 0; k < 6; k++) { R(8 + k, 9 - k, 1, 1); R(8 + k, 9 + k, 1, 1); R(13 + k, 4 + k, 1, 1); R(13 + k, 14 - k, 1, 1); } R(18, 9, 1, 1); R(19, 9, 1, 5); R(18, 13, 2, 1); break;   // bucket (a tipped pail)
        case 5: box(10, 7, 7, 9); R(12, 4, 3, 3); for (const [a, b] of [[7, 3], [5, 5], [7, 6], [4, 3]]) R(a, b, 1, 1); break;   // spray can
        case 6: R(9, 3, 3, 8); R(10, 11, 3, 3); R(12, 13, 4, 2); break;                          // brush
        case 7: R(15, 3, 3, 3); R(13, 6, 3, 3); R(11, 9, 3, 3); R(10, 12, 2, 2); break;         // pencil
        case 8: for (let k = 0; k < 10; k++) R(8 + k, 13 - k, 1, 1); break;                     // line
        case 9: box(8, 6, 11, 7); break;                                                         // eraser
        case 10: box(6, 4, 14, 10); break;
        case 11: R(6, 4, 14, 10); break;
        case 12: box(6, 4, 14, 10); R(6, 4, 2, 2); R(18, 4, 2, 2); R(6, 12, 2, 2); R(18, 12, 2, 2); break;
        case 13: R(7, 4, 12, 10); R(6, 5, 14, 8); break;
        case 14: g.beginPath(); g.ellipse(x + 13, y + 9, 7, 5, 0, 0, TAU); g.lineWidth = 1.5; g.stroke(); break;
        case 15: g.beginPath(); g.ellipse(x + 13, y + 9, 7.5, 5.5, 0, 0, TAU); g.fill(); break;
        case 16: g.beginPath(); g.moveTo(x + 7, y + 12); g.bezierCurveTo(x + 4, y + 2, x + 20, y + 2, x + 17, y + 9); g.bezierCurveTo(x + 15, y + 15, x + 10, y + 16, x + 7, y + 12); g.lineWidth = 1.5; g.stroke(); break;
        case 17: g.beginPath(); g.moveTo(x + 7, y + 12); g.bezierCurveTo(x + 4, y + 2, x + 20, y + 2, x + 17, y + 9); g.bezierCurveTo(x + 15, y + 15, x + 10, y + 16, x + 7, y + 12); g.fill(); break;
        case 18: g.beginPath(); g.moveTo(x + 6, y + 13); g.lineTo(x + 10, y + 4); g.lineTo(x + 19, y + 6); g.lineTo(x + 17, y + 14); g.closePath(); g.lineWidth = 1.5; g.stroke(); break;
        case 19: g.beginPath(); g.moveTo(x + 6, y + 13); g.lineTo(x + 10, y + 4); g.lineTo(x + 19, y + 6); g.lineTo(x + 17, y + 14); g.closePath(); g.fill(); break;
    }
}
function paintMacBase(g, L) {
    const { nw, nh, wx, wy, ww, wh } = L;
    patFill(g, 'AA55AA55AA55AA55', 0, 0, nw, nh);                      // the grey desktop
    // menu bar with MacPaint's menus (the Apple goes on in colour, after the 1-bit pass)
    g.fillStyle = '#fff'; g.fillRect(0, 0, nw, 19); g.fillStyle = '#000'; g.fillRect(0, 19, nw, 1);
    let mx = 38;
    for (const m of ['File', 'Edit', 'Goodies', 'Font', 'FontSize', 'Style']) { macText(g, m, mx, 15, 16); g.font = font(16, 'Pixelify Sans', 'bold '); mx += g.measureText(m).width + 16; }
    // the window
    g.fillStyle = '#000'; g.fillRect(wx + 1, wy + 1, ww, wh);
    g.fillStyle = '#fff'; g.fillRect(wx, wy, ww - 1, wh - 1); g.fillStyle = '#000';
    g.fillRect(wx, wy, ww, 1); g.fillRect(wx, wy + wh - 1, ww, 1); g.fillRect(wx, wy, 1, wh); g.fillRect(wx + ww - 1, wy, 1, wh);
    for (let i = 0; i < 6; i++) g.fillRect(wx + 2, wy + 4 + i * 2, ww - 4, 1);  // title stripes
    g.fillStyle = '#fff'; g.fillRect(wx + 8, wy + 3, 13, 12); g.fillStyle = '#000'; g.strokeStyle = '#000';
    g.fillRect(wx + 9, wy + 4, 11, 1); g.fillRect(wx + 9, wy + 14, 11, 1); g.fillRect(wx + 9, wy + 4, 1, 11); g.fillRect(wx + 19, wy + 4, 1, 11);  // close box
    g.font = font(15, 'Pixelify Sans', 'bold '); const tw = g.measureText('untitled').width;
    g.fillStyle = '#fff'; g.fillRect(wx + ww / 2 - tw / 2 - 8, wy + 1, tw + 16, 17);
    macText(g, 'untitled', Math.round(wx + ww / 2 - tw / 2), wy + 15, 15);
    g.fillStyle = '#000'; g.fillRect(wx, wy + 18, ww, 1);
    // tool palette, line widths, canvas frame, pattern palette
    const [tx, ty] = L.tool;
    for (let i = 0; i < 20; i++) macTool(g, i, tx + (i % 2) * 26, ty + Math.floor(i / 2) * 18, false);
    const lwY = ty + 10 * 18 + 4, lwH = Math.max(20, wy + wh - 6 - lwY);
    g.fillStyle = '#000'; g.fillRect(tx, lwY, 52, 1); g.fillRect(tx, lwY + lwH, 52, 1); g.fillRect(tx, lwY, 1, lwH); g.fillRect(tx + 51, lwY, 1, lwH + 1);
    const lws = [1, 2, 3, 5];
    lws.forEach((w, i) => g.fillRect(tx + 12, lwY + 5 + i * Math.floor((lwH - 10) / 4), 34, w));
    g.fillRect(tx + 4, lwY + 5 + 1 * Math.floor((lwH - 10) / 4) - 1, 5, 3);   // the check on the current width
    const [cx, cy, cw, ch] = L.cv;
    g.fillStyle = '#000'; g.fillRect(cx - 1, cy - 1, cw + 2, 1); g.fillRect(cx - 1, cy + ch, cw + 2, 1); g.fillRect(cx - 1, cy - 1, 1, ch + 2); g.fillRect(cx + cw, cy - 1, 1, ch + 2);
    const [px, py] = L.pat, cell = Math.floor((cw - 30) / 19);
    g.fillStyle = '#000'; g.fillRect(px, py, 26, 36); patFill(g, MAC_PAT[2], px + 3, py + 3, 20, 30);
    for (let r = 0; r < 2; r++) for (let c = 0; c < 19; c++) {
        const x = px + 30 + c * cell, y = py + r * 18;
        g.fillStyle = '#000'; g.fillRect(x, y, cell, 18);
        patFill(g, MAC_PAT[(r * 19 + c) % MAC_PAT.length], x + 1, y + 1, cell - 2, 16);
    }
}
function drawMac(g, W, H, t, st) {
    st = stDefaults(st);
    const u = st.u, kick = clamp(st.kick);
    const L = macNative(W, H);
    const c = L.c.getContext('2d');
    const words = lineWords(t, st, 'hello I am Macintosh out of the bag at last');
    const find = (re) => words.find((w) => re.test(w.w));
    const wHello = find(/hello/i), wI = words.find((w, i) => /^i$/i.test(w.w) && i > 0), wMac = find(/macintosh/i), wOut = find(/^out$/i), wLast = find(/^last$/i);
    const t0 = t - u;
    const drawA = wHello ? wHello.t0 - 0.12 : t0 + 0.12, drawB = wHello ? wHello.t1 + 0.35 : t0 + 1.2;
    const typeA = wI ? wI.t0 - 0.05 : t0 + 1.0, typeB = wMac ? wMac.t1 : t0 + 2.1;
    const antsA = wOut ? wOut.t0 : t0 + 2.1, fillAt = wLast ? wLast.t0 : t0 + 3.3;
    c.drawImage(L.base, 0, 0);
    const [cx, cy, cw, ch] = L.cv;
    // the paint bucket: pattern everywhere the drawing isn't (cached flood fill of the finished page)
    if (t >= fillAt) c.drawImage(macFilled(L), cx, cy);
    // the hello, stamped with a round 5-px brush up to the current point
    const prog = clamp((t - drawA) / (drawB - drawA));
    const n = Math.floor(prog * L.hello.length);
    if (t < fillAt) {
        c.fillStyle = '#000'; c.beginPath();
        for (let i = 0; i < n; i++) { const [x, y] = L.hello[i]; c.rect(x - 1, y - 2, 3, 5); c.rect(x - 2, y - 1, 5, 3); }
        c.fill();
        // typed text (the text tool): Chicago-ish bold, snapped to 1 bit
        const msg = 'Hello, I am Macintosh.';
        const k = t < typeA ? 0 : Math.min(msg.length, Math.floor(((t - typeA) / Math.max(0.2, typeB - typeA)) * msg.length) + 1);
        if (k > 0) {
            const tx = cx + 60, ty = cy + ch - 16;
            macText(c, msg.slice(0, k), tx, ty, 16);
            threshold1bit(c, tx - 2, ty - 16, 300, 22);
            if (t < typeB + 0.3 && fract(u * 2.2) < 0.6) { c.font = font(16, 'Pixelify Sans', 'bold '); c.fillStyle = '#000'; c.fillRect(tx + Math.round(c.measureText(msg.slice(0, k)).width) + 1, ty - 13, 1, 16); }
        }
    }
    // marching ants round the drawing, from "out of the bag" to the pour
    if (t >= antsA && t < fillAt - 0.04) {
        const [bx, by, bw, bh] = L.helloBox.map(Math.round), ph = Math.floor(u * 16) % 8;
        c.fillStyle = '#000';
        const dash = (x, y, len, horiz) => { for (let i = 0; i < len; i++) if (((i + ph) & 7) < 4) (horiz ? c.fillRect(x + i, y, 1, 1) : c.fillRect(x, y + i, 1, 1)); };
        c.fillStyle = '#fff'; c.fillRect(bx, by, bw, 1); c.fillRect(bx, by + bh, bw, 1); c.fillRect(bx, by, 1, bh); c.fillRect(bx + bw, by, 1, bh + 1);
        c.fillStyle = '#000'; dash(bx, by, bw, true); dash(bx, by + bh, bw + 1, true); dash(bx, by, bh, false); dash(bx + bw, by, bh, false);
    }
    // the current tool, inverted in the palette; its cursor on the page
    const tool = t >= fillAt - 0.05 ? 4 : t >= antsA ? 1 : t >= typeA ? 3 : 6;
    const [tx, ty] = L.tool;
    macTool(c, tool, tx + (tool % 2) * 26, ty + Math.floor(tool / 2) * 18, true);
    let cur = null;
    if (tool === 6 && n > 0 && prog < 1) cur = L.hello[Math.min(n, L.hello.length - 1)];
    if (cur) { c.fillStyle = '#000'; c.fillRect(cur[0] - 6, cur[1], 13, 1); c.fillRect(cur[0], cur[1] - 6, 1, 13); c.fillStyle = '#fff'; c.fillRect(cur[0], cur[1], 1, 1); }
    if (tool === 4) {                                                      // the bucket cursor where it poured
        const bx = cx + 20, by = cy + 20;
        c.fillStyle = '#fff'; c.fillRect(bx - 1, by - 1, 12, 13); c.fillStyle = '#000';
        c.fillRect(bx, by + 3, 9, 1); c.fillRect(bx, by + 3, 1, 8); c.fillRect(bx + 8, by + 3, 1, 8); c.fillRect(bx, by + 10, 9, 1); c.fillRect(bx + 9, by + 5, 2, 1); c.fillRect(bx + 10, by + 5, 1, 5);
    }
    // the rainbow Apple, in colour, on the menu bar
    for (let r = 0; r < APPLE_PX.length; r++) {
        c.fillStyle = APPLE_ROWCOL[r];
        const row = APPLE_PX[r];
        for (let x = 0; x < row.length; x++) if (row[x] === '#') c.fillRect(12 + x, 1 + r, 1, 1);
    }
    // the kick flashes the menu title under the Apple, as if pulled down
    if (kick > 0.85) { c.fillStyle = '#000'; c.fillRect(8, 0, 23, 19); for (let r = 0; r < APPLE_PX.length; r++) { c.fillStyle = APPLE_ROWCOL[r]; for (let x = 0; x < APPLE_PX[r].length; x++) if (APPLE_PX[r][x] === '#') c.fillRect(12 + x, 1 + r, 1, 1); } }
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.imageSmoothingEnabled = false;
    g.drawImage(L.c, 0, 0, L.nw * L.s, L.nh * L.s);
    g.imageSmoothingEnabled = true;
}
// the page after the pour: finished hello + text, then a flood fill from the corner with a MacPaint pattern
function macFilled(L) {
    if (L.filled) return L.filled;
    const [cx, cy, cw, ch] = L.cv;
    const c = mk(cw, ch), g = c.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, cw, ch);
    g.fillStyle = '#000'; g.beginPath();
    for (const [x, y] of L.hello) { g.rect(x - cx - 1, y - cy - 2, 3, 5); g.rect(x - cx - 2, y - cy - 1, 5, 3); }
    g.fill();
    macText(g, 'Hello, I am Macintosh.', 60, ch - 16, 16);
    g.font = font(16, 'Pixelify Sans', 'bold ');
    const bw = Math.round(g.measureText('Hello, I am Macintosh.').width) + 12;
    g.fillStyle = '#000'; g.fillRect(54, ch - 33, bw, 1); g.fillRect(54, ch - 10, bw, 1); g.fillRect(54, ch - 33, 1, 24); g.fillRect(54 + bw - 1, ch - 33, 1, 24);  // a text box the pour stops at
    threshold1bit(g, 0, 0, cw, ch);
    const id = g.getImageData(0, 0, cw, ch), d = id.data;
    const pat = MAC_PAT[7];                                                // fine diagonals
    const seen = new Uint8Array(cw * ch), stack = [0];
    seen[0] = 1;
    while (stack.length) {
        const p = stack.pop(), x = p % cw, y = (p / cw) | 0;
        const bit = parseInt(pat.substr(((cy + y) & 7) * 2, 2), 16) & (128 >> ((cx + x) & 7));
        const v = bit ? 0 : 255;
        d[p * 4] = d[p * 4 + 1] = d[p * 4 + 2] = v;
        for (const q of [p - 1, p + 1, p - cw, p + cw]) {
            if (q < 0 || q >= cw * ch || seen[q]) continue;
            if ((q === p - 1 && x === 0) || (q === p + 1 && x === cw - 1)) continue;
            if (d[q * 4] < 128) continue;                                    // black ink stops the pour
            seen[q] = 1; stack.push(q);
        }
    }
    g.putImageData(id, 0, 0);
    L.filled = c;
    return c;
}

// ================================================================== 1984 · KLATT + DECTALK
// A VT100-style terminal in amber phosphor (VT323 is drawn from DEC's own terminal type) under the DEC boxed
// "digital" homage. On the screen: the text being spoken, a live wideband formant spectrogram scrolling right
// to left (0-5 kHz, as Klatt's 10 kHz synthesizer; formant targets and diphthong glides from Klatt 1980 Table II,
// see SOURCES.md; voicing striations at Perfect Paul's 122 Hz average pitch; frication above 3.5 kHz on the
// sibilants; the newest column breathing with st.voice) and the parameter readout. Beside it, Klatt's 1980
// block diagram (Fig. 6, cascade/parallel), with the signal running through it while the voice sounds.
const AMB = { hot: '#ffe6a8', on: '#ffb52e', mid: '#c8781a', dim: '#5a3208', bg: '#0b0806', case: '#2b2723', case2: '#1c1916', burg: '#8d1c3d' };
const KLATT_GLIDE = { IY: [290, 2070, 2960], IH: [470, 1600, 2600], EY: [330, 2020, 2600], EH: [620, 1530, 2530], AE: [650, 1490, 2470], AO: [630, 1040, 2600],
    OW: [450, 900, 2300], UH: [500, 1180, 2390], UW: [320, 900, 2200], ER: [420, 1310, 1540], AY: [400, 1880, 2500], AW: [420, 940, 2350], OY: [360, 1820, 2450] };
const KL_L = { bez: [44, 36, 1050, 728], scr: [86, 76, 966, 610], spec: [154, 236, 790, 300], diag: [1134, 214, 760, 560], dec: [1134, 36, 300], dscale: 0.9 };
const SPEC_PX = 0.0036;
const sq = (x) => x * x;                                       // seconds per spectrogram column
function klattWordAt(words, tau) {
    for (let i = 0; i < words.length; i++) if (tau >= words[i].t0 && tau < words[i].t1) return i;
    return -1;
}
// one spectrogram column's energies (0..1) for time tau, rows = frequency bins top (5 kHz) to bottom (0)
function specColumn(words, tau, rows, out) {
    const wi = klattWordAt(words, tau);
    const floor = (r) => 0.04 + 0.05 * hash2(Math.floor(tau / SPEC_PX), r);
    if (wi < 0) { for (let r = 0; r < rows; r++) out[r] = floor(r); return; }
    const w = words[wi], dur = Math.max(1e-3, w.t1 - w.t0), p = (tau - w.t0) / dur;
    const vk = vowelOf(w.w), T = KLATT_V[vk] || KLATT_V.AH, G = KLATT_GLIDE[vk] || T;
    const prev = wi > 0 && words[wi - 1].t1 > w.t0 - 0.05 ? (KLATT_GLIDE[vowelOf(words[wi - 1].w)] || KLATT_V[vowelOf(words[wi - 1].w)]) : T;
    const into = smooth(0, 0.18, p), glide = smooth(0.35, 0.95, p);
    const F = [0, 1, 2].map((k) => lerp(prev[k], T[k], into) * (1 - glide) + G[k] * glide);
    const syl = /thirty|nobody|answer|macintosh|software|computer|numbers|eliza|mirror/i.test(w.w) ? 0.55 + 0.45 * Math.abs(Math.cos(p * Math.PI * 2)) : 1;
    const env = smooth(0, 0.08, p) * (1 - smooth(0.82, 1, p) * 0.7) * syl;
    const sib = isSibilant(w.w) && p > 0.72 && /s|z$/i.test(w.w.replace(/[^a-z]/gi, ''));
    const stri = 0.72 + 0.28 * Math.cos(tau * 122 * TAU);
    for (let r = 0; r < rows; r++) {
        const f = (1 - (r + 0.5) / rows) * 5000;
        let e = 0;
        if (!sib) {
            e += 1.0 * Math.exp(-sq((f - F[0]) / 150)) + 0.8 * Math.exp(-sq((f - F[1]) / 190)) + 0.55 * Math.exp(-sq((f - F[2]) / 230));
            e += 0.35 * Math.exp(-sq((f - 3300) / 260)) + 0.18 * Math.exp(-sq((f - 3750) / 280));   // F4, F5 (Table I)
            e += 0.7 * Math.exp(-sq(f / 160));                                                                 // the voice bar
            e *= env * stri;
        } else {
            e = (f > 3300 ? 0.55 + 0.4 * hash2(Math.floor(tau / SPEC_PX), r * 7) : 0.08) * env;
        }
        out[r] = Math.max(floor(r), Math.min(1, e));
    }
}
const AMBER_LUT = (() => {
    const lut = new Uint8ClampedArray(256 * 3);
    for (let i = 0; i < 256; i++) {
        const x = i / 255;
        lut[i * 3] = Math.min(255, 255 * Math.pow(x, 0.55) * 1.05);
        lut[i * 3 + 1] = Math.min(255, 190 * Math.pow(x, 0.95) + 60 * Math.pow(x, 3));
        lut[i * 3 + 2] = Math.min(255, 30 * x + 170 * Math.pow(x, 4));
    }
    return lut;
})();
// spectrogram chunks (128 columns each), cached per line; chunk k covers absolute times [k*128, (k+1)*128) * SPEC_PX
function specChunk(W, H, words, k) {
    const [, , , sh] = KL_L.spec;
    const key = `spec:${words.length ? words[0].t0.toFixed(3) : 'x'}:${k}`;
    return cached(key, W, H, () => {
        const { k: sc } = frame(W, H);
        const rows = Math.max(40, Math.round(sh * sc / 2)), cols = 128;
        const c = mk(cols, rows), g = c.getContext('2d');
        const id = g.createImageData(cols, rows), d = id.data, col = new Float32Array(rows);
        for (let x = 0; x < cols; x++) {
            specColumn(words, (k * cols + x) * SPEC_PX, rows, col);
            for (let r = 0; r < rows; r++) {
                const v = Math.round(Math.pow(col[r], 0.8) * 255), o = (r * cols + x) * 4;
                d[o] = AMBER_LUT[v * 3]; d[o + 1] = AMBER_LUT[v * 3 + 1]; d[o + 2] = AMBER_LUT[v * 3 + 2]; d[o + 3] = 255;
            }
        }
        g.putImageData(id, 0, 0);
        return c;
    });
}
// Klatt 1980, Fig. 6: boxes [x, y, w, h, label] (diagram units 760 x 560) and wires
const KL_BOX = {
    imp: [0, 64, 92, 48, 'IMPULSE\nGEN.'], rgp: [120, 70, 56, 36, 'RGP'], rgz: [210, 30, 56, 34, 'RGZ'], rgs: [210, 112, 56, 34, 'RGS'],
    rnp: [390, 0, 56, 34, 'RNP'], rnz: [452, 0, 56, 34, 'RNZ'], r1: [520, 0, 44, 34, 'R1'], r2: [570, 0, 44, 34, 'R2'], r3: [620, 0, 44, 34, 'R3'], r4: [670, 0, 44, 34, 'R4'], r5: [720, 0, 40, 34, 'R5'],
    rng: [0, 300, 112, 50, 'RANDOM\nNUMBER GEN.'], lpf: [196, 306, 56, 36, 'LPF'], dif: [350, 196, 70, 44, 'FIRST\nDIFF.'],
    p1: [590, 180, 44, 30, 'R1'], pn: [590, 222, 44, 30, 'RNP'], p2: [590, 264, 44, 30, 'R2'], p3: [590, 306, 44, 30, 'R3'], p4: [590, 348, 44, 30, 'R4'], p5: [590, 390, 44, 30, 'R5'], p6: [590, 432, 44, 30, 'R6'],
    out: [690, 320, 70, 44, 'FIRST\nDIFF.'],
};
const KL_AMP = { av: [298, 47, 'AV'], avs: [298, 129, 'AVS'], ah: [360, 262 + 0, 'AH'], af: [360, 360, 'AF'], a1: [540, 195, 'A1'], an: [540, 237, 'AN'], a2: [540, 279, 'A2'], a3: [540, 321, 'A3'], a4: [540, 363, 'A4'], a5: [540, 405, 'A5'], a6: [540, 447, 'A6'], ab: [540, 500, 'AB'] };
function klattWires() {
    const B = KL_BOX, A = KL_AMP;
    const R = (b) => [B[b][0] + B[b][2], B[b][1] + B[b][3] / 2], Lf = (b) => [B[b][0], B[b][1] + B[b][3] / 2];
    const voice = [[R('imp'), Lf('rgp')], [R('rgp'), [186, 88], [186, 47], Lf('rgz')], [[186, 88], [186, 129], Lf('rgs')],
        [R('rgz'), [A.av[0] - 16, A.av[1]]], [R('rgs'), [A.avs[0] - 16, A.avs[1]]], [[A.av[0] + 16, A.av[1]], [336, 88]], [[A.avs[0] + 16, A.avs[1]], [336, 88]],
        [[336, 88], [364, 88], [364, 17], Lf('rnp')], [R('rnp'), Lf('rnz')], [R('rnz'), Lf('r1')], [R('r1'), Lf('r2')], [R('r2'), Lf('r3')], [R('r3'), Lf('r4')], [R('r4'), Lf('r5')],
        [R('r5'), [770, 17], [770, 300], [676, 330], Lf('out')]];
    const noise = [[R('rng'), [150, 325], Lf('lpf')], [R('lpf'), [300, 324], [A.ah[0] - 16, A.ah[1]]], [[300, 324], [300, 360], [A.af[0] - 16, A.af[1]]],
        [[A.ah[0], A.ah[1] - 16], [360, 110], [364, 88]], [[A.af[0] + 16, A.af[1]], [470, 360], [470, 480]]];
    const par = [];
    for (const [a, b] of [['a1', 'p1'], ['an', 'pn'], ['a2', 'p2'], ['a3', 'p3'], ['a4', 'p4'], ['a5', 'p5'], ['a6', 'p6']]) {
        par.push([[470, A[a][1]], [A[a][0] - 16, A[a][1]]]);
        par.push([[A[a][0] + 16, A[a][1]], Lf(b)]);
        par.push([R(b), [660, A[a][1]], [676, 336]]);
    }
    par.push([[470, A.ab[1]], [A.ab[0] - 16, A.ab[1]]], [[A.ab[0] + 16, A.ab[1]], [660, A.ab[1]], [676, 350]]);
    par.push([R('dif'), [470, 218], [470, 500]], [[385, 240], [385, 262], [300, 262]]);
    return { voice, noise, par };
}
function paintKlattDiagram(g, x0, y0, s) {
    g.save(); g.translate(x0, y0); g.scale(s, s);
    const { voice, noise, par } = klattWires();
    g.strokeStyle = 'rgba(255,181,46,0.55)'; g.lineWidth = 1.6 / s * 1.4;
    for (const w of [...voice, ...noise, ...par]) { g.beginPath(); w.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke(); }
    g.setLineDash([4, 4]); g.beginPath(); g.moveTo(46, 112); g.bezierCurveTo(60, 200, 110, 250, 124, 312); g.stroke(); g.setLineDash([]);   // F0 -> MOD
    g.fillStyle = 'rgba(255,181,46,0.9)'; g.font = font(11, 'Share Tech Mono'); g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('F0', 40, 128);
    for (const [bx, by, bw, bh, lab] of Object.values(KL_BOX)) {
        g.fillStyle = AMB.bg; g.fillRect(bx, by, bw, bh);
        g.strokeStyle = AMB.on; g.lineWidth = 1.8; g.strokeRect(bx, by, bw, bh);
        g.fillStyle = AMB.on; g.font = font(lab.includes('\n') ? 11 : 13, 'Share Tech Mono');
        const ls = lab.split('\n');
        ls.forEach((l, i) => g.fillText(l, bx + bw / 2, by + bh / 2 + (i - (ls.length - 1) / 2) * 12));
    }
    for (const [ax, ay, lab] of Object.values(KL_AMP)) {
        g.fillStyle = AMB.bg; g.beginPath(); g.arc(ax, ay, 15, 0, TAU); g.fill();
        g.strokeStyle = AMB.on; g.lineWidth = 1.8; g.stroke();
        g.fillStyle = AMB.on; g.font = font(lab.length > 2 ? 10 : 12, 'Share Tech Mono'); g.fillText(lab, ax, ay + 1);
    }
    // summing junctions and the modulator
    for (const [sx, sy] of [[336, 88], [676, 336]]) { g.fillStyle = AMB.bg; g.beginPath(); g.arc(sx, sy, 10, 0, TAU); g.fill(); g.strokeStyle = AMB.on; g.stroke(); g.fillStyle = AMB.on; g.fillText('+', sx, sy + 1); }
    g.fillStyle = AMB.bg; g.beginPath(); g.arc(150, 325, 11, 0, TAU); g.fill(); g.strokeStyle = AMB.on; g.stroke();
    g.beginPath(); g.moveTo(143, 318); g.lineTo(157, 332); g.moveTo(157, 318); g.lineTo(143, 332); g.stroke();
    g.font = font(12, 'Share Tech Mono'); g.fillStyle = AMB.mid; g.textAlign = 'left';
    g.fillText('CASCADE VOCAL TRACT TRANSFER FUNCTION', 392, 52);
    g.fillText('VOICING SOURCE', 96, 168); g.fillText('NOISE SOURCE', 20, 368); g.fillText('MOD', 136, 348);
    g.fillText('PARALLEL VOCAL TRACT TRANSFER FUNCTION', 384, 540); g.fillText('RADIATION', 688, 382); g.fillText('SW', 318, 116);
    g.restore();
}
function klattBackground(g, W, H) {
    const { k, ox, oy } = frame(W, H);
    g.fillStyle = '#0d0b09'; g.fillRect(0, 0, W, H);
    g.setTransform(k, 0, 0, k, ox, oy);
    const glow = g.createRadialGradient(560, 400, 60, 560, 400, 900);
    glow.addColorStop(0, 'rgba(255,170,60,0.10)'); glow.addColorStop(1, 'rgba(255,170,60,0)');
    g.fillStyle = glow; g.fillRect(-400, 0, 2720, 800);
    // the terminal: warm-grey case, dark bezel, the glass
    const [bx, by, bw, bh] = KL_L.bez;
    g.fillStyle = 'rgba(0,0,0,0.5)'; g.beginPath(); g.roundRect(bx + 8, by + 10, bw, bh, 34); g.fill();
    const cg = g.createLinearGradient(0, by, 0, by + bh);
    cg.addColorStop(0, '#3b3530'); cg.addColorStop(1, '#221e1a');
    g.fillStyle = cg; g.beginPath(); g.roundRect(bx, by, bw, bh, 34); g.fill();
    const [sx, sy, sw, shh] = KL_L.scr;
    g.fillStyle = '#060504'; g.beginPath(); g.roundRect(sx - 10, sy - 10, sw + 20, shh + 20, 26); g.fill();
    const sg = g.createRadialGradient(sx + sw / 2, sy + shh / 2, 80, sx + sw / 2, sy + shh / 2, sw * 0.7);
    sg.addColorStop(0, '#1a1107'); sg.addColorStop(1, '#070403');
    g.fillStyle = sg; g.beginPath(); g.roundRect(sx, sy, sw, shh, 22); g.fill();
    // the badge under the glass: boxed "digital" + VT100
    paintDEC(g, sx + 8, sy + shh + 22, 150, '#1b1917', '#e9e4da');
    g.fillStyle = '#d8462c'; g.font = font(28, 'Share Tech Mono'); g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.fillText('VT100', sx + 172, sy + shh + 46);
    g.fillStyle = 'rgba(233,228,218,0.45)'; g.font = font(17, 'Share Tech Mono'); g.textAlign = 'right';
    g.fillText('DECtalk  DTC01', sx + sw - 8, sy + shh + 44);
    // spectrogram frame + axis (on the glass)
    const [px, py, pw, ph] = KL_L.spec;
    g.strokeStyle = 'rgba(255,181,46,0.35)'; g.lineWidth = 1.5; g.strokeRect(px - 1, py - 1, pw + 2, ph + 2);
    g.fillStyle = 'rgba(255,181,46,0.7)'; g.font = font(22, 'VT323'); g.textAlign = 'left'; g.textBaseline = 'middle';
    for (let khz = 0; khz <= 5; khz++) { const y = py + ph - (khz / 5) * ph; g.fillText(khz + ' kHz', px + pw + 16, y); g.fillRect(px + pw + 2, y, 9, 1.5); }
    // the DEC homage, large, and Klatt's diagram
    const [dx, dy, dw] = KL_L.dec;
    const dh = paintDEC(g, dx, dy, dw, AMB.burg, '#fbf4ec');
    g.fillStyle = AMB.hot; g.font = font(64, 'VT323'); g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.fillText('DECtalk · 1984', dx + dw + 34, dy + dh - 14);
    const [kx, ky] = KL_L.diag, ds = KL_L.dscale;
    g.fillStyle = AMB.on; g.font = font(19, 'Share Tech Mono');
    g.fillText('SOFTWARE FOR A CASCADE/PARALLEL FORMANT SYNTHESIZER', kx, ky - 36);
    g.fillStyle = AMB.mid; g.font = font(16, 'Share Tech Mono');
    g.fillText('D. H. KLATT · J. ACOUST. SOC. AM. 67(3) · 1980 · FIG. 6', kx, ky - 14);
    paintKlattDiagram(g, kx, ky, ds);
    g.fillStyle = AMB.mid; g.font = font(16, 'Share Tech Mono');
    g.fillText('39 CONTROL PARAMETERS · UPDATED EVERY 5 MS · 10,000 SAMPLES/S', kx, ky + 560 * ds + 22);
}
// DEC's mark: seven boxes, one lowercase letter in each
function paintDEC(g, x, y, w, box, ink) {
    const n = 7, gap = w * 0.021, bw = (w - gap * (n - 1)) / n, bh = bw * 2.14;
    for (let i = 0; i < n; i++) { g.fillStyle = box; g.fillRect(x + i * (bw + gap), y, bw, bh); }
    g.fillStyle = ink; g.font = font(bh * 0.62, 'Exo 2'); g.textAlign = 'center'; g.textBaseline = 'alphabetic';
    [...'digital'].forEach((ch, i) => g.fillText(ch, x + i * (bw + gap) + bw / 2, y + bh * 0.74));
    return bh;
}
function drawKlatt(g, W, H, t, st) {
    st = stDefaults(st);
    const u = st.u, v = clamp(st.voice), kick = clamp(st.kick);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.putImageData(bgLayer('klatt', W, H, klattBackground), 0, 0);
    const f = toDesign(g, W, H);
    const words = lineWords(t, st, 'I was a voice a man kept thirty years and made his own');
    const wi = wordIndex(words, t), cw = wi >= 0 ? words[wi] : null;
    const [px, py, pw, ph] = KL_L.spec;
    // ---- the spectrogram: chunks scrolled so "now" sits at the right edge
    const colsVis = 250, colW = pw / colsVis;                       // 250 columns (0.9 s) across the frame
    const nowCol = t / SPEC_PX, firstCol = nowCol - colsVis;
    g.save();
    g.beginPath(); g.rect(px, py, pw, ph); g.clip();
    g.imageSmoothingEnabled = false;
    for (let k = Math.floor(firstCol / 128); k <= Math.floor(nowCol / 128); k++) {
        const x = px + (k * 128 - firstCol) * colW;
        g.drawImage(specChunk(W, H, words, k), x, py, 128 * colW, ph);
    }
    g.imageSmoothingEnabled = true;
    // the newest column breathes with the voice; a write head
    g.fillStyle = `rgba(255,236,190,${0.25 + 0.6 * v})`; g.fillRect(px + pw - 4, py, 4, ph);
    // scanlines
    g.fillStyle = 'rgba(0,0,0,0.28)';
    for (let y = py; y < py + ph; y += 3) g.fillRect(px, y, pw, 1);
    g.restore();
    // formant tracks labelled at the head: F1 F2 F3 from Klatt's table for the vowel being sung
    const vk = cw ? vowelOf(cw.w) : 'AH', T = KLATT_V[vk] || KLATT_V.AH, G2 = KLATT_GLIDE[vk] || T;
    const pp = cw ? clamp((t - cw.t0) / Math.max(1e-3, cw.t1 - cw.t0)) : 0, gl = smooth(0.35, 0.95, pp);
    const Fs = [0, 1, 2].map((k) => Math.round(T[k] * (1 - gl) + G2[k] * gl));
    g.font = font(20, 'VT323'); g.textAlign = 'right'; g.textBaseline = 'middle';
    Fs.forEach((fv, k) => {
        const y = py + ph - (fv / 5000) * ph;
        g.fillStyle = AMB.hot; g.globalAlpha = cw ? 0.55 + 0.45 * v : 0.35;
        g.fillText('F' + (k + 1) + ' ▸', px - 10, y);
    });
    g.globalAlpha = 1;
    // ---- screen text: the words being spoken (the DECtalk input), and the synthesizer's parameters
    const [sx, sy] = KL_L.scr;
    const typed = typedSoFar(words, t, (w) => w);
    const amberText = (s, x, y, px2, col = AMB.on, align = 'left') => {
        g.font = font(px2, 'VT323'); g.textAlign = align; g.textBaseline = 'alphabetic';
        g.save(); g.globalCompositeOperation = 'lighter'; g.fillStyle = 'rgba(255,150,40,0.22)';
        for (const [ddx, ddy] of [[-1.6, 0], [1.6, 0], [0, -1.6], [0, 1.6]]) g.fillText(s, x + ddx, y + ddy);
        g.restore();
        g.fillStyle = col; g.fillText(s, x, y);
    };
    amberText('[:np]  PERFECT PAUL', sx + 30, sy + 56, 34, AMB.mid);
    const lines = elizaWrap(typed, 44);
    lines.slice(-2).forEach((l, i) => amberText(l, sx + 30, sy + 104 + i * 38, 40, AMB.hot));
    if (fract(u * 2.1) < 0.55) { g.fillStyle = AMB.on; const l = lines.length ? lines[lines.length - 1] : ''; g.font = font(40, 'VT323'); g.fillRect(sx + 34 + g.measureText(l).width, sy + 104 + (Math.min(lines.length, 2) - 1) * 38 - 28, 18, 32); }
    const av = cw && t < cw.t1 ? Math.round(52 + 8 * v) : 0;
    amberText(`F0 122  AV ${String(av).padStart(2)}  F1 ${String(Fs[0]).padStart(4)}  F2 ${String(Fs[1]).padStart(4)}  F3 ${String(Fs[2]).padStart(4)}  /${vk}/`, sx + 30, py + ph + 52, 32, AMB.on);
    // ---- the diagram lights up: signal dots running the voicing path while the voice sounds, the noise
    // path on the sibilants
    const [kx, ky] = KL_L.diag;
    const { voice, noise } = klattWires();
    const sib = !!(cw && isSibilant(cw.w) && t > cw.t0 + (cw.t1 - cw.t0) * 0.7);
    const runPath = (paths, alpha, speed) => {
        g.save(); g.translate(kx, ky); g.scale(KL_L.dscale, KL_L.dscale);
        g.strokeStyle = `rgba(255,220,150,${alpha})`; g.lineWidth = 3;
        for (const w of paths) { g.beginPath(); w.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke(); }
        // signal dots every 40 units along each wire. Zero-length segments are skipped: a 0/0 there made a NaN arc,
        // and NaN geometry panics Skia inside napi-rs (a process abort, not an exception)
        g.fillStyle = `rgba(255,245,220,${Math.min(1, alpha * 1.6)})`;
        g.beginPath();
        for (const w of paths) {
            let len = 0; const seg = [];
            for (let i = 1; i < w.length; i++) { const l = Math.hypot(w[i][0] - w[i - 1][0], w[i][1] - w[i - 1][1]); seg.push(l); len += l; }
            for (let d = fract(t * speed) * 40; d < len; d += 40) {
                let acc = 0;
                for (let i = 0; i < seg.length; i++) {
                    if (seg[i] > 1e-6 && acc + seg[i] >= d) {
                        const q = clamp((d - acc) / seg[i]), x = lerp(w[i][0], w[i + 1][0], q), y = lerp(w[i][1], w[i + 1][1], q);
                        g.moveTo(x + 3.2, y); g.arc(x, y, 3.2, 0, TAU);
                        break;
                    }
                    acc += seg[i];
                }
            }
        }
        g.fill();
        g.restore();
    };
    if (cw && t < cw.t1 && !sib) runPath(voice, 0.35 + 0.55 * v, 3.2);
    if (sib) runPath(noise, 0.8, 4);
    // the kick: the DEC boxes blink in sequence like a busy port
    if (kick > 0.1) {
        const [dx, dy, dw] = KL_L.dec, n = 7, gap = dw * 0.021, bw = (dw - gap * 6) / n, bh = bw * 2.14;
        const i = Math.floor(u / BEAT) % 7;
        g.fillStyle = `rgba(255,255,255,${0.25 * kick})`; g.fillRect(dx + i * (bw + gap), dy, bw, bh);
    }
    void f;
    g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.setTransform(1, 0, 0, 1, 0, 0);
}

// ================================================================== ALL ERAS · GLITCH
// "I was built to answer — nobody asked if I was here." Every era above, cycling on the kick (one per beat,
// then two per beat from "nobody"), each caught at an iconic moment of its own line and stuttered to 12 fps;
// the frame tears in bands (rows slid sideways, one band's red channel split), blocks jump. The line itself is
// a ransom note cut from the eras' own type: each word in a different era's lettering. On "here" everything
// drops away except the word and a cursor.
const ERA_ORDER = ['voder_1939', 'bell_1961', 'eliza_1966', 'speakspell_1978', 'sam_1982', 'mac_1984', 'klatt_1984'];
const ERA_ICON_U = { voder_1939: 2.6, bell_1961: 2.9, eliza_1966: 3.5, speakspell_1978: 3.55, sam_1982: 2.7, mac_1984: 1.95, klatt_1984: 3.1 };
function tearBands(g, W, H, seed, amount) {
    const r = rng(seed);
    const nb = 3 + Math.floor(r() * 4 * (0.4 + amount));
    for (let b = 0; b < nb; b++) {
        const bh = Math.max(2, Math.floor((4 + r() * 46) * H / 800)), y = Math.floor(r() * (H - bh));
        const dx = Math.round((r() - 0.5) * 2 * (40 + 220 * amount) * W / 1920);
        if (!dx) continue;
        const id = g.getImageData(0, y, W, bh), d = id.data, row = W * 4;
        for (let yy = 0; yy < bh; yy++) {
            const o = yy * row;
            if (dx > 0) d.copyWithin(o + dx * 4, o, o + (W - dx) * 4); else d.copyWithin(o, o - dx * 4, o + row);
        }
        if (b === 0) {                                            // a chroma split in the first band: red slides further
            const s = Math.max(4, Math.abs(dx) >> 2) * 4;
            for (let yy = 0; yy < bh; yy++) { const o = yy * row; for (let i = o; i < o + row - s; i += 4) d[i] = d[i + s]; }
        }
        g.putImageData(id, 0, y);
    }
    // blocks: a few rectangles copied from elsewhere in the frame
    const nk = Math.floor(r() * 3 * amount);
    for (let k = 0; k < nk; k++) {
        const bw = Math.floor((60 + r() * 260) * W / 1920), bh = Math.floor((20 + r() * 90) * H / 800);
        const sx = Math.floor(r() * (W - bw)), sy = Math.floor(r() * (H - bh)), tx = Math.floor(r() * (W - bw)), ty = Math.floor(r() * (H - bh));
        g.putImageData(g.getImageData(sx, sy, bw, bh), tx, ty);
    }
}
// the ransom note: one lettering per era
function ransomWord(g, W, H, word, style, x, y, h, hot) {
    const s = word.toUpperCase();
    g.save();
    g.globalAlpha = hot ? 1 : 0.9;
    let w = 0;
    switch (style % 7) {
        case 0: {                                                  // 1939: cream deco on navy
            g.font = font(h * 0.62, 'Michroma'); w = g.measureText(s).width + h * 0.5;
            g.fillStyle = DECO.navy; g.fillRect(x, y, w, h); g.strokeStyle = DECO.gold; g.lineWidth = 3; g.strokeRect(x + 5, y + 5, w - 10, h - 10);
            g.fillStyle = DECO.cream; g.textBaseline = 'middle'; g.textAlign = 'center'; g.fillText(s, x + w / 2, y + h / 2 + 2);
            break;
        }
        case 1: {                                                  // 1961: a punched card's printout
            g.font = font(h * 0.7, 'Share Tech Mono'); w = g.measureText(s).width + h * 0.5;
            g.fillStyle = IBMC.card; g.fillRect(x, y, w, h);
            g.fillStyle = IBMC.blue2; for (let i = 0; i < s.length; i++) g.fillRect(x + h * 0.25 + (i + 0.4) * (w - h * 0.5) / s.length, y + h * 0.1, 4, 9);
            g.fillStyle = IBMC.ink; g.textBaseline = 'middle'; g.textAlign = 'center'; g.fillText(s, x + w / 2, y + h * 0.58);
            break;
        }
        case 2: {                                                  // 1966: typewriter on green-bar
            g.font = font(h * 0.72, 'Special Elite'); w = g.measureText(s).width + h * 0.5;
            g.fillStyle = ELZ.paper; g.fillRect(x, y, w, h); g.fillStyle = ELZ.bar; g.fillRect(x, y + h * 0.5, w, h * 0.5);
            g.fillStyle = ELZ.ink; g.textBaseline = 'middle'; g.textAlign = 'center'; g.fillText(s, x + w / 2, y + h / 2 + 3);
            break;
        }
        case 3: {                                                  // 1978: the VFD
            const cw = h * 0.46, gap = h * 0.16; w = s.length * (cw + gap) + h * 0.4;
            g.fillStyle = '#040606'; g.fillRect(x, y, w, h);
            for (let i = 0; i < s.length; i++) drawSegChar(g, s[i], x + h * 0.2 + i * (cw + gap), y + h * 0.14, cw, h * 0.72, 1, hot ? 0.6 : 0.2, Math.max(3, h * 0.05));
            break;
        }
        case 4: {                                                  // 1982: C64 pixels, light blue on blue
            const px = Math.max(1, Math.floor(h * 0.7 / 8)), cw = 8 * px; w = s.length * cw + 2 * px * 4;
            g.fillStyle = C64P[6]; g.fillRect(x, y, w, h);
            const spr = cached('c64word:' + s, 0, 0, () => { const c = mk(s.length * 8, 8); c64Text(c.getContext('2d'), s, 0, 0, C64P[14]); return c; });
            g.imageSmoothingEnabled = false; g.drawImage(spr, x + px * 4, y + (h - 8 * px) / 2, s.length * cw, 8 * px); g.imageSmoothingEnabled = true;
            break;
        }
        case 5: {                                                  // 1984: Chicago-ish black on white, a 1-px frame
            g.font = font(h * 0.66, 'Pixelify Sans', 'bold '); w = g.measureText(s).width + h * 0.5;
            g.fillStyle = '#fff'; g.fillRect(x, y, w, h); g.fillStyle = '#000'; g.fillRect(x, y, w, 3); g.fillRect(x, y + h - 3, w, 3); g.fillRect(x, y, 3, h); g.fillRect(x + w - 3, y, 3, h);
            g.textBaseline = 'middle'; g.textAlign = 'center'; g.fillText(s, x + w / 2, y + h / 2 + 2);
            break;
        }
        default: {                                                 // 1984: amber phosphor
            g.font = font(h * 0.9, 'VT323'); w = g.measureText(s).width + h * 0.5;
            g.fillStyle = '#0b0806'; g.fillRect(x, y, w, h);
            g.fillStyle = hot ? AMB.hot : AMB.on; g.textBaseline = 'middle'; g.textAlign = 'center'; g.fillText(s, x + w / 2, y + h / 2 + 3);
        }
    }
    g.restore();
    return w;
}
function ransomWidth(g, word, style, h) {
    const s = word.toUpperCase();
    switch (style % 7) {
        case 0: g.font = font(h * 0.62, 'Michroma'); return g.measureText(s).width + h * 0.5;
        case 1: g.font = font(h * 0.7, 'Share Tech Mono'); return g.measureText(s).width + h * 0.5;
        case 2: g.font = font(h * 0.72, 'Special Elite'); return g.measureText(s).width + h * 0.5;
        case 3: return s.length * (h * 0.46 + h * 0.16) + h * 0.4;
        case 4: { const px = Math.max(1, Math.floor(h * 0.7 / 8)); return s.length * 8 * px + 8 * px; }
        case 5: g.font = font(h * 0.66, 'Pixelify Sans', 'bold '); return g.measureText(s).width + h * 0.5;
        default: g.font = font(h * 0.9, 'VT323'); return g.measureText(s).width + h * 0.5;
    }
}
function drawGlitch(g, W, H, t, st) {
    st = stDefaults(st);
    const u = st.u, kick = clamp(st.kick);
    const words = lineWords(t, st, 'I was built to answer nobody asked if I was here');
    // the line turns on "nobody" (DAISY's words); other lyrics turn on the first word past mid-line
    let iNobody = words.findIndex((w) => /nobody/i.test(w.w));
    if (iNobody < 0) iNobody = words.findIndex((w) => w.t0 >= t - u + 0.5 * (st.dur || LINE_DUR));
    const tNobody = iNobody >= 0 ? words[iNobody].t0 : t - u + 1.88;
    const last = words[words.length - 1];
    const tHere = last ? last.t0 : t - u + 3.5;
    const hereWord = (last ? last.w.toUpperCase().replace(/[^A-Z0-9']/g, '') : '') || 'HERE';   // DAISY ends on "here"
    const beatLen = t >= tNobody ? BEAT / 2 : BEAT;
    const k = t >= tNobody ? 8 + Math.floor((t - tNobody) / beatLen) : Math.floor(u / BEAT);
    const kStart = t >= tNobody ? tNobody + (k - 8) * beatLen : (t - u) + k * BEAT;
    const frameN = Math.floor(t * 30);
    if (t < tHere) {
        // the era for this slot, caught at its iconic moment, stuttered to 12 fps (a 3-frame freeze on each kick)
        const era = ERA_ORDER[(((k * 3 + (k >> 3)) % 7) + 7) % 7];         // k < 0 before the line starts
        const local = t - kStart, held = local < 0.1 ? 0 : Math.floor(local * 12) / 12;
        const uE = ERA_ICON_U[era] + held;
        const tE = kStart + held;
        scenes[era].draw(g, W, H, tE, { u: uE, dur: LINE_DUR, progress: uE / LINE_DUR, caption: null, voice: st.voice, kick, line: 0 });
        g.setTransform(1, 0, 0, 1, 0, 0);
        // tearing: stronger on the kick and in the second half
        const amt = clamp(0.25 + 0.75 * kick + (t >= tNobody ? 0.3 : 0));
        tearBands(g, W, H, frameN * 7919 + k * 104729, amt);
        // a flash frame on each slot change
        if (local < 1 / 30) { g.fillStyle = 'rgba(255,255,255,0.35)'; g.fillRect(0, 0, W, H); }
    } else {
        g.setTransform(1, 0, 0, 1, 0, 0);
        g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
    }
    // ---- the ransom note: the words sung so far, each cut from a different era's type
    const f = toDesign(g, W, H);
    const hWord = 92, gap = 18, lines = [[], []];
    words.forEach((w, i) => { if (w.t0 <= t) lines[i >= iNobody && iNobody >= 0 ? 1 : 0].push([w, i]); });
    if (t < tHere) {
        const show = t >= tNobody ? lines[1] : lines[0];
        let total = 0;
        for (const [w, i] of show) total += ransomWidth(g, w.w, i + 3, hWord) + gap;
        let x = 960 - (total - gap) / 2;
        const y = 800 - hWord - 60;
        for (const [w, i] of show) {
            const jit = hash(frameN * 13 + i) - 0.5, hot = t < w.t1 + 0.05;
            g.save(); g.translate(x, y + jit * 10 * (0.3 + kick)); g.rotate(jit * 0.06);
            const ww = ransomWord(g, W, H, w.w, i + 3, 0, 0, hWord, hot);
            g.restore();
            x += ww + gap;
        }
    } else {
        // "here" (the line's last word): everything drops away but the word and a cursor
        const p = clamp((t - tHere) / 0.2);
        g.fillStyle = `rgba(255,248,236,${easeOut(p)})`; g.font = font(120, 'VT323'); g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(hereWord, 960, 400);
        g.font = font(120, 'VT323'); const tw = g.measureText(hereWord).width;
        if (fract((t - tHere) * 3.2) < 0.55) g.fillRect(960 + tw / 2 + 14, 358, 44, 84);
    }
    void f;
    g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.setTransform(1, 0, 0, 1, 0, 0);
}

// ================================================================== TITLE CARD · DAISY (DAY'S EYE)
// A daisy whose petals are the eras' materials (deco gold, a punched card, green-bar, Speak & Spell orange, C64
// blue, Mac 1-bit dither, amber phosphor), round a sun-yellow eye; it opens as the title arrives. DAISY is spelled
// in five eras' letters — a Broadway deco D, a slab A in Rand's 1956 IBM idiom, a typewriter I on green-bar, a VFD S, a C64 Y —
// and (DAY'S EYE) types in amber beneath.
const PETAL_STYLES = ['deco', 'ibm', 'paper', 'ss', 'c64', 'mac', 'amber'];
// a petal in its own 64 x 220 box (tip at y 0, the narrow end at y 218), drawn as vectors under the caller's
// transform: vector fills stay cheap while 21 petals turn (rotated image draws are slow on the CPU rasterizer)
function petalPath(g) {
    g.beginPath(); g.moveTo(32, 218);
    g.bezierCurveTo(18, 170, 2, 90, 6, 40); g.quadraticCurveTo(8, 6, 24, 5); g.quadraticCurveTo(32, 12, 40, 5);
    g.quadraticCurveTo(56, 6, 58, 40); g.bezierCurveTo(62, 90, 46, 170, 32, 218); g.closePath();
}
function tinyPattern(g, key, w, h, paint) {
    const c = cached('pat:' + key, 0, 0, () => { const cv = mk(w, h); paint(cv.getContext('2d')); return cv; });
    return g.createPattern(c, 'repeat');
}
function petalSprite(W, H, style) { return sprite('petal-' + style, W, H, 64, 220, (g) => paintPetal(g, style)); }
function paintPetal(g, style) {
    petalPath(g);
    g.save(); g.clip();
    switch (style) {
        case 'deco': {
            const gr = g.createLinearGradient(0, 0, 64, 0); gr.addColorStop(0, '#b07a24'); gr.addColorStop(0.5, '#fbe7a6'); gr.addColorStop(1, '#c48a2c');
            g.fillStyle = gr; g.fillRect(0, 0, 64, 220);
            g.strokeStyle = 'rgba(120,70,10,0.5)'; g.lineWidth = 2; g.beginPath();
            for (let i = 0; i < 5; i++) { g.moveTo(32, 216); g.lineTo(8 + i * 12, 0); }
            g.stroke();
            break;
        }
        case 'ibm':                                              // 1961: a punched card, holes in IBM blue
            g.fillStyle = IBMC.card; g.fillRect(0, 0, 64, 220);
            g.fillStyle = IBMC.blue2; g.beginPath();
            for (let y = 10, i = 0; y < 214; y += 9, i++) for (let c = 0; c < 6; c++) if (hash(i * 7 + c * 131) > 0.62) g.rect(8 + c * 9, y, 4, 6);
            g.fill();
            g.fillStyle = 'rgba(46,36,24,0.45)'; g.fillRect(0, 40, 64, 1); g.fillRect(0, 150, 64, 1);
            break;
        case 'paper':
            g.fillStyle = '#f4f5ee'; g.fillRect(0, 0, 64, 220); g.fillStyle = '#cfe7c9'; g.beginPath(); for (let y = 0; y < 220; y += 36) g.rect(0, y, 64, 18); g.fill();
            g.fillStyle = '#1b2a2f'; g.beginPath(); for (let y = 10; y < 220; y += 22) { g.moveTo(13, y); g.arc(10, y, 3, 0, TAU); } g.fill();
            break;
        case 'ss': g.fillStyle = SSC.case; g.fillRect(0, 0, 64, 220); g.fillStyle = SSC.yellow; g.fillRect(14, 20, 36, 180); g.fillStyle = SSC.blue; g.fillRect(20, 40, 24, 140); break;
        case 'c64':
            g.fillStyle = C64P[14]; g.fillRect(0, 0, 64, 220); g.fillStyle = C64P[6]; g.fillRect(8, 12, 48, 196);
            g.fillStyle = C64P[14]; g.beginPath(); for (let y = 24; y < 200; y += 16) g.rect(14, y, 8 + ((y * 7) % 30), 8); g.fill();
            break;
        case 'mac':
            g.fillStyle = tinyPattern(g, 'dither2', 2, 2, (p) => { p.fillStyle = '#fff'; p.fillRect(0, 0, 2, 2); p.fillStyle = '#000'; p.fillRect(0, 0, 1, 1); p.fillRect(1, 1, 1, 1); });
            g.fillRect(0, 0, 64, 220);
            g.fillStyle = '#fff'; g.fillRect(12, 30, 40, 150); g.fillStyle = '#000'; g.fillRect(12, 30, 40, 2);
            break;
        default: g.fillStyle = '#0b0806'; g.fillRect(0, 0, 64, 220); g.fillStyle = AMB.on; g.beginPath(); for (let y = 12; y < 210; y += 14) g.rect(10, y, 16 + ((y * 13) % 30), 6); g.fill(); break;
    }
    g.strokeStyle = 'rgba(0,0,0,0.25)'; g.lineWidth = 2; g.beginPath(); g.moveTo(32, 200); g.quadraticCurveTo(30, 110, 32, 22); g.stroke();
    g.restore();
    petalPath(g); g.strokeStyle = 'rgba(255,255,255,0.6)'; g.lineWidth = 2; g.stroke();
}
function paintTitleFlower(g, W, H, cx, cy, open, breathe) {
    // 21 petals, three of each era, opening from a bud round a sun-yellow eye
    const N = 21;
    for (let i = 0; i < N; i++) {
        const a = (i / N) * TAU + 0.2 - (1 - open) * 1.2 + i * 0.01;
        const spread = lerp(0.15, 1, open), len = lerp(0.5, 1.28, open) * breathe;
        const aa = -Math.PI / 2 + (a + Math.PI / 2) * spread;
        g.save(); g.translate(cx, cy); g.rotate(aa + Math.PI / 2); g.scale(1.25, len);   // the narrow end at the eye
        g.globalAlpha = clamp(open * 3 - i * 0.05);
        drawSprite(g, petalSprite(W, H, PETAL_STYLES[i % 7]), -32, -252, 64, 220);
        g.restore();
    }
    g.globalAlpha = 1;
    // the eye: a sun-yellow disc of florets
    const R = lerp(40, 96, open);
    const eye = g.createRadialGradient(cx - R * 0.3, cy - R * 0.3, 4, cx, cy, R);
    eye.addColorStop(0, '#fff3a0'); eye.addColorStop(0.6, '#f6c41c'); eye.addColorStop(1, '#d68a0c');
    g.fillStyle = eye; g.beginPath(); g.arc(cx, cy, R, 0, TAU); g.fill();
    g.fillStyle = 'rgba(150,80,0,0.45)'; g.beginPath();
    for (let i = 0; i < 90; i++) { const rr = Math.sqrt(i / 90) * R * 0.92, a = i * 2.39996, fx = cx + Math.cos(a) * rr, fy = cy + Math.sin(a) * rr; g.moveTo(fx + 2.6, fy); g.arc(fx, fy, 2.6, 0, TAU); }
    g.fill();
}
// DAISY in five eras' letters. Each letter is a cached sprite (painted once, whole); arrival animates only
// its alpha and offset, and the VFD S flashes additively as it strikes.
const TITLE_LH = 214, TITLE_X0 = 880, TITLE_Y0 = 196;
function titleLetterSprites(W, H) {
    const LH = TITLE_LH;
    return {
        D: sprite('tl-D', W, H, 0.84 * LH + 24, LH + 20, (g) => {
            g.fillStyle = '#050f2c';
            for (let d = 12; d > 0; d -= 2) { g.beginPath(); decoLetter(g, 'D', d * 0.8, d * 0.6, LH); g.fill('evenodd'); }
            const gg = g.createLinearGradient(0, 0, 0, LH); gg.addColorStop(0, '#fffaf0'); gg.addColorStop(0.52, DECO.cream); gg.addColorStop(0.53, '#f3d893'); gg.addColorStop(1, DECO.gold);
            g.fillStyle = gg; g.beginPath(); decoLetter(g, 'D', 0, 0, LH); g.fill('evenodd');
        }),
        A: sprite('tl-A', W, H, 0.9 * LH + 4, LH + 4, (g) => { g.fillStyle = '#f4f7fb'; slabA(g, 0, 0, LH); }),
        I: sprite('tl-I', W, H, 0.42 * LH, LH + 20, (g) => {
            const w = 0.42 * LH;
            g.fillStyle = ELZ.paper; g.fillRect(0, 0, w, LH + 20); g.fillStyle = ELZ.bar; g.fillRect(0, 10 + LH * 0.33, w, LH * 0.33);
            g.fillStyle = '#1b2a2f'; g.beginPath(); for (let yy = 14; yy < LH + 10; yy += 30) { g.moveTo(14, yy); g.arc(10, yy, 4, 0, TAU); } g.fill();
            g.fillStyle = ELZ.ink; g.font = font(LH * 0.9, 'Special Elite'); g.textAlign = 'center'; g.textBaseline = 'alphabetic';
            g.fillText('I', w / 2 + 6, 10 + LH * 0.86);
        }),
        S: sprite('tl-S', W, H, 0.6 * LH + 16, LH + 20, (g) => {
            const w = 0.6 * LH;
            g.fillStyle = '#040606'; g.fillRect(0, 0, w + 16, LH + 20);
            drawSegChar(g, 'S', 22, 26, w - 40, LH - 32, 1, 0.4, 11);
        }),
        Y: sprite('tl-Y', W, H, 8 * Math.floor(LH / 8) + 16, LH + 20, (g) => {
            const px = Math.floor(LH / 8);
            g.fillStyle = C64P[6]; g.fillRect(0, 0, 8 * px + 16, LH + 20);
            const glyph = cached('c64word:Y', 0, 0, () => { const c = mk(8, 8); c64Text(c.getContext('2d'), 'Y', 0, 0, C64P[14]); return c; });
            g.imageSmoothingEnabled = false; g.drawImage(glyph, 8, 10 + (LH - 8 * px) / 2 + 4, 8 * px, 8 * px); g.imageSmoothingEnabled = true;
        }),
    };
}
// a slab-serif A in the idiom of Rand's 1956 IBM letters (City): heavy legs, a flat apex, square slab feet
function slabA(g, x, y, h) {
    const w = 0.9 * h, cx = x + w / 2, foot = 0.14 * h, fy = y + h - foot;
    g.beginPath();
    g.moveTo(cx - 0.15 * h, y); g.lineTo(cx + 0.05 * h, y); g.lineTo(x + 0.3 * h, fy); g.lineTo(x + 0.07 * h, fy); g.closePath();          // left leg
    g.moveTo(cx - 0.03 * h, y); g.lineTo(cx + 0.15 * h, y); g.lineTo(x + w - 0.07 * h, fy); g.lineTo(x + w - 0.29 * h, fy); g.closePath();  // right leg
    g.rect(x + 0.22 * h, y + 0.58 * h, w - 0.44 * h, 0.13 * h);                                                                           // bar
    g.rect(x, fy, 0.4 * h, foot); g.rect(x + w - 0.4 * h, fy, 0.4 * h, foot);                                                           // slab feet
    g.rect(cx - 0.2 * h, y, 0.4 * h, 0.1 * h);                                                                                            // flat apex
    g.fill('nonzero');
}
function paintTitleLetters(g, W, H, u) {
    const LH = TITLE_LH, y0 = TITLE_Y0, S = titleLetterSprites(W, H);
    const arrive = (i) => clamp((u - 0.35 - i * 0.22) / 0.18);
    let x = TITLE_X0;
    const place = (spr, i, dx, dy, adv) => {
        const a = arrive(i);
        if (a > 0) {
            g.save(); g.globalAlpha = a; drawSprite(g, spr, x + dx + (i === 1 ? (1 - a) * 40 : 0), y0 + dy + (i === 0 ? (1 - a) * -30 : 0));
            if (i === 3 && a < 1) { g.globalCompositeOperation = 'lighter'; g.globalAlpha = 0.9 * (1 - a); drawSprite(g, spr, x + dx, y0 + dy); }
            g.restore();
        }
        x += adv;
    };
    place(S.D, 0, 0, 0, 0.84 * LH + 40);
    place(S.A, 1, 0, 0, 0.9 * LH + 40);
    place(S.I, 2, 0, -10, 0.42 * LH + 40);
    place(S.S, 3, -8, -10, 0.6 * LH + 40);
    place(S.Y, 4, -8, -10, 8 * Math.floor(LH / 8) + 26);
    return x;
}
function titleBackground(g, w, h) {
    const gr = g.createRadialGradient(w * 0.3, h * 0.55, 20, w * 0.3, h * 0.55, w * 0.8);
    gr.addColorStop(0, '#1d1a2c'); gr.addColorStop(0.5, '#0d0c16'); gr.addColorStop(1, '#050409');
    g.fillStyle = gr; g.fillRect(0, 0, w, h);
    const r = rng(8192);
    for (let i = 0; i < w * h / 900; i++) { g.fillStyle = `rgba(255,255,255,${0.1 + 0.4 * r() * r()})`; g.fillRect(r() * w, r() * h, 1.5, 1.5); }
    const { k, ox, oy } = frame(w, h);
    g.setTransform(k, 0, 0, k, ox, oy);
    const glow = g.createRadialGradient(470, 400, 20, 470, 400, 420);            // dawn light where the flower opens
    glow.addColorStop(0, 'rgba(255,214,90,0.28)'); glow.addColorStop(1, 'rgba(255,214,90,0)');
    g.fillStyle = glow; g.fillRect(50, -20, 840, 840);
    g.setTransform(1, 0, 0, 1, 0, 0);
}
function drawTitle(g, W, H, t, st) {
    st = stDefaults(st);
    const u = st.u, dur = st.dur || 3;
    const LH = 214, x0 = 880, y0 = 196, cx = 470, cy = 400;
    const bg0 = bgLayer('title', W, H, titleBackground);
    // once the flower is open and all five letters have landed, the whole plate is one baked layer
    const bgOpen = bgLayer('title-open', W, H, (bg, w, h) => {
        titleBackground(bg, w, h);
        toDesign(bg, w, h);
        paintTitleFlower(bg, w, h, cx, cy, 1, 1);
        paintTitleLetters(bg, w, h, 9);
        bg.setTransform(1, 0, 0, 1, 0, 0);
    });
    g.setTransform(1, 0, 0, 1, 0, 0);
    const open = easeOut((u - 0.1) / 1.5);
    if (open >= 0.999 && u >= 1.45) {
        g.putImageData(bgOpen, 0, 0);
        toDesign(g, W, H);
        const pulse = 0.5 + 0.5 * Math.sin(u * 2.2);                            // the eye breathes
        const eg = g.createRadialGradient(cx, cy, 60, cx, cy, 190);
        eg.addColorStop(0, `rgba(255,236,150,${0.12 * pulse})`); eg.addColorStop(1, 'rgba(255,236,150,0)');
        g.save(); g.globalCompositeOperation = 'lighter'; g.fillStyle = eg; g.fillRect(cx - 190, cy - 190, 380, 380); g.restore();
    } else {
        g.putImageData(bg0, 0, 0);
        // while it opens, the flower is painted at half resolution and scaled up (21 rotated petal images per frame
        // are the costliest thing on the CPU rasterizer; motion hides the softness, the open plate is full-res)
        const { k } = frame(W, H);
        const half = cached('title-half', W, H, () => mk(440 * k, 440 * k));
        const hg = half.getContext('2d');
        hg.setTransform(1, 0, 0, 1, 0, 0); hg.clearRect(0, 0, half.width, half.height);
        hg.setTransform(k / 2, 0, 0, k / 2, 0, 0);
        paintTitleFlower(hg, W, H, 440, 440, open, 1);
        toDesign(g, W, H);
        g.drawImage(half, cx - 440, cy - 440, 880, 880);
        paintTitleLetters(g, W, H, u);
    }
    // (DAY'S EYE), typed in amber
    const sub = "(DAY'S EYE)", n = clamp(Math.floor((u - 1.5) / 0.07) + 1, 0, sub.length);
    if (n > 0) {
        g.font = font(96, 'VT323'); g.textAlign = 'left'; g.textBaseline = 'alphabetic';
        g.save(); g.globalCompositeOperation = 'lighter'; g.fillStyle = 'rgba(255,150,40,0.25)';
        for (const [dx, dy] of [[-2, 0], [2, 0], [0, -2], [0, 2]]) g.fillText(sub.slice(0, n), x0 + 6 + dx, y0 + LH + 120 + dy);
        g.restore();
        g.fillStyle = AMB.hot; g.fillText(sub.slice(0, n), x0 + 6, y0 + LH + 120);
        if (n < sub.length || fract(u * 2) < 0.5) { const tw = g.measureText(sub.slice(0, n)).width; g.fillStyle = AMB.on; g.fillRect(x0 + 12 + tw, y0 + LH + 52, 34, 72); }
    }
    // fade in from black, out at the very end
    const fade = Math.min(smooth(0, 0.35, u), 1 - smooth(dur - 0.25, dur, u));
    if (fade < 1) { g.setTransform(1, 0, 0, 1, 0, 0); g.fillStyle = `rgba(0,0,0,${1 - fade})`; g.fillRect(0, 0, W, H); }
    g.textAlign = 'left'; g.textBaseline = 'alphabetic';
    g.setTransform(1, 0, 0, 1, 0, 0);
}

// every draw runs inside save/restore, so no scene leaks context state into the next (putImageData ignores both)
const wrap = (fn) => (g, W, H, t, st) => { g.save(); try { fn(g, W, H, t, st); } finally { g.restore(); } };
// fps = the redraw rate the art was made for (redraw when Math.floor(t * fps) changes); lines = two-bar lyric lines
// the scene spans (its length is lines × 8 beats); title_card instead has its own default length, dur (s).
// DAISY played voder_1939 … glitch_all in this order, one per line of verse 1: an example, not a requirement.
export const scenes = {
    title_card: { draw: wrap(drawTitle), fps: 30, dur: 3, label: "DAISY (DAY'S EYE) title" },
    voder_1939: { draw: wrap(drawVoder), fps: 30, lines: 1, label: 'Voder · 1939' },
    bell_1961: { draw: wrap(drawBell), fps: 30, lines: 1, label: 'Bell Labs · 1961' },
    eliza_1966: { draw: wrap(drawEliza), fps: 30, lines: 1, label: 'ELIZA · 1966' },
    speakspell_1978: { draw: wrap(drawSpeakSpell), fps: 30, lines: 1, label: 'Speak & Spell · 1978' },
    sam_1982: { draw: wrap(drawSam), fps: 25, lines: 1, label: 'S.A.M. · 1982' },
    mac_1984: { draw: wrap(drawMac), fps: 30, lines: 1, label: 'MacinTalk · 1984' },
    klatt_1984: { draw: wrap(drawKlatt), fps: 30, lines: 1, label: 'Klatt formant voice · 1984' },
    glitch_all: { draw: wrap(drawGlitch), fps: 30, lines: 1, label: 'every voice at once' },
};

// Draw every scene across its line once into a scratch canvas, so the caches built lazily during playback
// (printer-paper and spectrogram chunks, the Mac's poured page, C64 glyph atlases, the glitch's per-slot eras)
// exist before the film asks for them. lineOf(name) -> { t0, dur, st(t) } from the host's own timing (the caches
// keyed on caption word times then match playback); without it each scene warms at t0 = 0 on its fallback lyric.
export function prewarm(W, H, lineOf = null, perSecond = 12) {
    const c = mk(W, H), g = c.getContext('2d');
    for (const [name, sc] of Object.entries(scenes)) {
        const L = lineOf ? lineOf(name) : null;
        const t0 = L?.t0 ?? 0, dur = L?.dur ?? sc.dur ?? (sc.lines || 1) * LINE_DUR;
        const samples = Math.ceil(dur * perSecond);                     // finer than any chunk or glitch slot (0.23 s)
        for (let i = 0; i <= samples; i++) {
            const t = t0 + (i / samples) * dur * 0.999;
            const st = L?.st ? L.st(t) : { u: t - t0, dur, progress: (t - t0) / dur, caption: null, voice: 0.8, kick: 0, line: 0 };
            sc.draw(g, W, H, t, st);
        }
    }
}
