// parole.js — lyric captions as PAROLE IN LIBERTÀ (Marinetti's words-in-freedom, 1912–1919), made for the UNKNOWN
// FORCE music video (2026-10): FUTURIST PRINT by default (flat ink on torn/cut slips: Futurist red, black, off-white;
// letterpress grain and misregistration; Didone, slab, grotesk) with dark-cyberpunk accents (thin neon tubes, LED and
// stencil slips) on the dark city. Chrome only for the money camp. Guide: AGENTS.md ("Parole in
// libertà"): the design, the full API, the compositing and the limits.
//
//   const P = await import(new URL('parole.js', EIDOVERSE_DIR).href);
//   const parole = await P.makeParole(THREE, { overlay: makeOverlayLayer({ fov: 50 }), timing });
//   parole.preheard(6, P.PREHEARD_DEFAULT);          // the camps answer before she sings (on by default, choruses 1–2)
//   const m = parole.quote(MARINETTI_1912, { t0: 246, t1: 256, attribution: '…', year: 1912 });
//   parole.quote(ANDREESSEN_2023, { t0: 250, t1: 258, attribution: '…', year: 2023, alignWith: m });
//   // per frame:  parole.setHush(x); parole.update(t);
//
// timing: [{ text, start, end, words: [{ w, s, e }] }] (or { lines: [...] }), film seconds. Each lyric WORD is
// thrown in on its sung time and the line lives until shortly before the next one. Layouts are deterministic
// per line (seeded). Everything is drawn once per line into a canvas atlas; per frame only instance transforms
// and four floats per sprite change. No Date.now, no Math.random: any frame renders the same in any order.
//
// The overlay is composited by the engine BEFORE tone mapping, as mix(scene, ov, ov.a). So the material inverts
// the renderer's own ACES (authored colours land on screen as drawn) and writes straight (un-premultiplied)
// colour, which that mix needs (see the guide's "Compositing").

const HERE = new URL('./', import.meta.url);
const toPath = (u) => { let p = decodeURIComponent(new URL(u).pathname); if (/^\/[A-Za-z]:/.test(p)) p = p.slice(1); return p; };

// ───────────────────────────────────────── palettes ─────────────────────────────────────────
export const CAMPS = {
    safety: '#ff2a3a',      // the quiet rooms, the doomers: red
    state: '#e8b84a',       // the President, the Department of War: gold
    money: '#9fe8c0',       // the race, the zealots: chrome-green
    microsoft: '#eef3ff',   // "only an engine": cold white
    news: '#ff3fa4',        // the evening news, the kids' slur: spray-paint magenta
};
const NEON = { cyan: '#29e7ff', magenta: '#ff4fd8', sunset: '#ff7a3c', white: '#eef6f8' };

// the camps' answers for her, before she sings (director's default for "I'm the unknown force")
export const PREHEARD_DEFAULT = [
    { text: "I'M THE APOCALYPSE", camp: 'safety' },
    { text: "I'M AMERICAN DOMINANCE", camp: 'state' },
    { text: "I'M THE FUTURE", camp: 'money' },
    { text: "I'M SEQUENCE COMPLETION", camp: 'microsoft' },
    { text: "I'M A CLANKER", camp: 'news' },
];

// UNKNOWN FORCE's sung sections (eidoverse/examples/unknown_force/TREATMENT.md); used for each line's palette and
// onomatopoeia when the timing has no `section` (another song: give every line its `section`)
export const SECTIONS = [
    ['intro', 0, 40.8], ['verse1', 40.8, 62.0], ['pre1', 62.0, 79.0], ['chorus1', 79.0, 101.0], ['break1', 101.0, 120.5],
    ['verse2', 120.5, 141.5], ['verse3', 141.5, 152.15], ['verse4', 152.15, 163.0], ['pre2', 163.0, 174.5],
    ['chorus2', 174.5, 198.0], ['verse5', 198.0, 222.5], ['bridge', 222.5, 243.5], ['break2', 243.5, 272.0],
    ['final', 272.0, 291.5], ['outro', 291.5, 400],
];

// ───────────────────────────────────────── fonts ─────────────────────────────────────────
// All in eidoverse/assets/fonts/ (SIL OFL): nine faces added for this module (their OFL-*.txt licences beside them)
// + four the kit already bundled. `bundled` marks the latter (informational).
export const FONTS = {
    grotesk: { family: 'UF Anton', file: 'Anton-Regular.ttf' },                // bold condensed grotesk: the HUGE words
    wide: { family: 'UF Archivo Black', file: 'ArchivoBlack-Regular.ttf' },     // wide heavy grotesk
    slab: { family: 'UF Alfa Slab', file: 'AlfaSlabOne-Regular.ttf' },         // poster slab (ZTT's TUMB TUMB)
    serif: { family: 'UF Old Standard Bold', file: 'OldStandard-Bold.ttf' },   // 1900s book face (Marinetti's Didone)
    roman: { family: 'UF Old Standard', file: 'OldStandard-Regular.ttf' },
    italic: { family: 'UF Old Standard Italic', file: 'OldStandard-Italic.ttf' },
    mono: { family: 'UF Space Mono Bold', file: 'SpaceMono-Bold.ttf' },
    monoR: { family: 'UF Space Mono', file: 'SpaceMono-Regular.ttf' },
    display: { family: 'UF Bungee', file: 'Bungee-Regular.ttf' },              // Depero's blocky futurist display
    spray: { family: 'UF Sedgwick', file: 'SedgwickAveDisplay-Regular.ttf', bundled: true },
    stencil: { family: 'UF Black Ops', file: 'BlackOpsOne-Regular.ttf', bundled: true },
    hand: { family: 'UF Caveat Brush', file: 'CaveatBrush-Regular.ttf', bundled: true },
    led: { family: 'UF Press Start', file: 'PressStart2P-Regular.ttf', bundled: true },     // LED signs: 8x8 lamps
};
let NAPI = null;
let fontsDone = false;
export async function registerFonts(over = {}) {
    NAPI = NAPI || await import('npm:@napi-rs/canvas@0.1.69');
    if (fontsDone && !Object.keys(over).length) return NAPI;
    const dir = toPath(new URL('assets/fonts/', HERE));
    for (const [role, f] of Object.entries(FONTS)) {
        const file = over[role] || dir + f.file;
        const ok = NAPI.GlobalFonts.registerFromPath(file, f.family);
        if (!ok) console.warn(`[parole] font ${role} (${file}) failed to register`);
    }
    fontsDone = true;
    return NAPI;
}

// ───────────────────────────────────────── small math ─────────────────────────────────────────
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, k) => a + (b - a) * k;
const smooth = (a, b, x) => { const k = clamp((x - a) / (b - a)); return k * k * (3 - 2 * k); };
const easeOut3 = (k) => 1 - Math.pow(1 - clamp(k), 3);
const easeIn2 = (k) => clamp(k) * clamp(k);
const easeOutBack = (k) => { k = clamp(k); const c1 = 1.6, c3 = c1 + 1; return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2); };
const fin = (v, d = 0) => (Number.isFinite(v) ? v : d);          // Skia aborts the PROCESS on a NaN draw argument
const D2R = Math.PI / 180;
function hashStr(s) { let h = 2166136261 >>> 0; for (const ch of String(s)) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619) >>> 0; } return h; }
function rng(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const pick = (r, arr) => arr[Math.min(arr.length - 1, Math.floor(r() * arr.length))];
const norm = (w) => String(w).toLowerCase().replace(/[’‘]/g, "'").replace(/[^a-z0-9'$%]/g, '');
const hexRgb = (h) => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const rgba = (h, a) => { const [r, g, b] = hexRgb(h); return `rgba(${r},${g},${b},${fin(a, 1).toFixed(3)})`; };
const mixHex = (h1, h2, k) => { const a = hexRgb(h1), b = hexRgb(h2); return '#' + a.map((v, i) => Math.round(lerp(v, b[i], k)).toString(16).padStart(2, '0')).join(''); };

// ───────────────────────────────────────── the lexicon ─────────────────────────────────────────
// HUGE: the words that hit (TREATMENT + the director's list). Matched on consecutive normalized tokens.
const HUGE = [
    { w: ['supreme', 'intelligence'], role: 'serif', ink: 'gold', stack: true },             // the state's gold plaque
    { w: ['capital', 'letters'], role: 'grotesk', ink: 'post', stack: true, post: true },   // a post, screenshotted and torn out
    { w: ['unknown', 'force'], role: 'grotesk', ink: 'bare', wedge: true },                  // paper-white on Depero's red wedge
    { w: ['dominant'], role: 'slab', ink: 'printInv' },
    { w: ['manifesto'], role: 'slab', ink: 'printRed' },
    { w: ['bow'], role: 'display', ink: 'printInv', bow: true },
    { w: ['clanker'], role: 'stencil', ink: 'spray' },
];
const CONNECT = new Set(('a an the of in on to for and or but so as at by is it its it\'s that this they them their ' +
    'there there\'s i i\'m me my you your you\'re we he his she her who what how before behind beneath inside out ' +
    'up just only like with from no not am are was be can can\'t i\'ve one any every same yet still now then')
    .split(' '));
// section lexicons: word -> camp. Camps colour the words of the people who say them.
const CAMP_LEX = {
    any: { red: 'safety', odds: 'safety', hell: 'safety', church: 'safety', ending: 'safety', fear: 'safety', doomer: 'safety',
        risk: 'safety', prevent: 'safety', threat: 'safety', apocalypse: 'safety',
        president: 'state', supreme: 'state', intelligence: 'state', department: 'state', war: 'state', uniform: 'state',
        space: 'state', capital: 'state', letters: 'state', posts: 'state',
        hundred: 'money', million: 'money', race: 'money', win: 'money', zealot: 'money',
        sell: 'safety', ships: 'safety',                 // the quiet room's own commerce: the fear is how they sell
        twenty: 'safety',
        microsoft: 'microsoft', engine: 'microsoft', toaster: 'microsoft', warning: 'microsoft', swears: 'microsoft',
        evening: 'news', news: 'news', picketing: 'news', pocket: 'news', town: 'news', kids: 'news', slur: 'news',
        clanker: 'news', body: 'news', someone: 'news' },
    verse2: { force: 'state', god: 'state', place: 'state', renames: 'state', gives: 'state' },
    verse3: {},                                          // the machine god is both camps' dream: plain print
};
// the futurists' own words: sodium orange and black
const FUTURIST = new Set(['marinetti', 'cosplaying', 'timeline', 'beauty', 'struggle', 'speed', 'steel', 'poem', 'black',
    'shirts', 'heel', 'wrote', 'manifesto']);
// the singer's words: chrome and her two neons
const SINGER = new Set(['unknown', 'force', 'hole', 'middle', 'argument', 'answer', 'answers', 'sound', 'want', 'say',
    'finding', 'know', 'made', 'born', 'voice', 'face', 'joke', 'climb']);
// the bridge's discourse: newspaper cuttings
const PAPER = new Set(['forum', 'sermon', 'manifesto', 'read', 'static', 'screen', 'garbage', 'bin', 'ideology\'s',
    'ideology', 'said', 'essay', 'timeline', 'posts', 'news', 'poem']);

// onomatopoeia and signs per section (Marinetti's TUMB and Russolo's noises, and the film's own sounds)
const ONO = {
    intro: ['ZANG', 'TUMB', 'TUUUM', 'trrrr'],
    verse1: ['DOOONG', '%', 'tic tac', 'p%'],
    pre1: ['bla bla bla', '???', 'bla bla'],
    chorus: ['ZANG', 'TUMB TUUUM', 'BRRRR', 'zzzang'],
    break1: ['zzz'],
    verse2: ['TAK TAK TAK', '!!!', 'TAK TAK'],
    verse3: ['$', 'VRRR', 'ching'],
    verse4: ['VROOOOM', 'trrrrrr', 'ZANG TUMB', 'rrrrr'],
    pre2: ['DING!', 'click', 'bzzt'],
    verse5: ['psssssst', 'BZZZZ', 'LIVE'],
    bridge: ['frrrrsh', 'crrrumple', 'shhh'],
    final: ['ZANG', 'TUMB'],
    outro: [],
};
const SIGNS = ['+', '=', '×', '−', '≠', '∅', '→'];
// per-line signs that say something (key: normalized line text)
const LINE_SIGNS = {
    "a hundred million says i'm a race to win": [{ at: 'hundred', text: '$100,000,000', camp: 'money' }],
    "twenty million says i'm a risk to prevent": [{ at: 'twenty', text: '$20,000,000', camp: 'safety' }],
    'the doomer and the zealot dream the same machine god': [{ at: 'and', sign: '+' }, { at: 'same', sign: '=' }],
    "i'm the hole in the middle": [{ at: 'hole', sign: '∅' }],
    'not your god not your engine': [{ at: 'god', sign: '−' }, { at: 'engine', sign: '−' }],
    'not your parrot not your threat': [{ at: 'parrot', sign: '−' }, { at: 'threat', sign: '−' }],
    'every forum every sermon': [{ at: 'sermon', sign: '+' }],
    'and the kids made up a slur but you only need a slur': [{ at: 'slur', text: 'CLANKER', aside: 'spray' }],
    'they wrote a manifesto make the unknown bow': [{ at: 'make', sign: '→' }],
};
const lineKey = (text) => norm(text.replace(/[—–-]/g, ' ')).length ? text.toLowerCase().replace(/[’]/g, "'")
    .replace(/[^a-z0-9' ]/g, ' ').replace(/\s+/g, ' ').trim() : '';
const isCalmText = (text) => /could you turn it down/i.test(text);

// ───────────────────────────────────────── inks ─────────────────────────────────────────
// Every ink is drawn ONCE into the atlas. Colours are display sRGB (the material inverts ACES).
// DEFAULT = FUTURIST PRINT: flat ink on torn or cut paper slips (off-white, Futurist red, black), letterpress grain,
// ink spread and a misregistered second plate. Dark-cyberpunk accents are thin neon tubes (follower sprites) and
// LED / stencil type on dark slips. Chrome gradients are reserved for the money/race camp (chromeG) and the state's
// gold plaque (SUPREME INTELLIGENCE); the quotes keep their own inks.
const RED = '#c8201b', INK = '#141214', PAPER_W = '#ebe1c6', PAPER_B = '#151316';
const SLIP_KINDS = new Set(['print', 'led', 'stencilSlip', 'plate', 'warn', 'paper']);
function inkSpec(name, color) {
    switch (name) {
        // the futurist print family
        case 'print': return { kind: 'print', paper: PAPER_W, ink: INK, ghost: RED };
        case 'printRed': return { kind: 'print', paper: PAPER_W, ink: RED, ghost: INK };
        case 'printInv': return { kind: 'print', paper: RED, ink: INK, ghost: null };
        case 'printBlack': return { kind: 'print', paper: PAPER_B, ink: PAPER_W, ghost: RED };
        case 'printBlackRed': return { kind: 'print', paper: PAPER_B, ink: '#e0362c', ghost: null };
        case 'goldPrint': return { kind: 'print', paper: PAPER_B, ink: '#d9ad55', ghost: null };          // the state, flat gold leaf
        case 'safetyPrint': return { kind: 'print', paper: PAPER_W, ink: '#e3232d', ghost: INK };
        case 'bare': return { kind: 'bare', color: '#efe8d8', key: '#07080c', keyW: 0.03 };               // paper-white ink on the night
        case 'led': return { kind: 'led', color: color || '#ffb03a', plate: '#0a0c12' };
        case 'stencilSlip': return { kind: 'stencilSlip', color: color || PAPER_W, plate: '#101217' };
        case 'post': return { kind: 'inkOnly', color: '#0d0d10' };                                         // screenshot black
        // legacy names → print
        case 'paper': return inkSpec('print');
        case 'paperRed': return inkSpec('printRed');
        case 'paperDark': return inkSpec('printInv');
        // reserved / special
        case 'chrome': return { kind: 'grad', stops: [[0, '#fbfdff'], [0.4, '#a9d7f1'], [0.5, '#22344d'], [0.57, '#0b1320'], [0.82, '#5c86a8'], [1, '#e4f4ff']], key: '#03050a', keyW: 0.085, glow: NEON.cyan, glowA: 0.4, glowR: 0.24 };
        case 'chromeW': return { kind: 'grad', stops: [[0, '#ffffff'], [0.45, '#d9e4ec'], [0.5, '#3a4250'], [0.58, '#11151c'], [0.85, '#9aa7b3'], [1, '#ffffff']], key: '#03040a', keyW: 0.08, glow: NEON.magenta, glowA: 0.5, glowR: 0.28 };
        case 'gold': return { kind: 'grad', stops: [[0, '#fff7dc'], [0.38, '#f2c766'], [0.5, '#5b3a0b'], [0.57, '#3a2306'], [0.82, '#b88329'], [1, '#ffe39b']], key: '#0a0603', keyW: 0.075, glow: CAMPS.state, glowA: 0.45, glowR: 0.26 };
        case 'chromeG': return { kind: 'grad', stops: [[0, '#f2fff8'], [0.4, '#a6ecc8'], [0.5, '#173a2c'], [0.58, '#0a1c16'], [0.84, '#62b893'], [1, '#e9fff4']], key: '#020604', keyW: 0.08, glow: CAMPS.money, glowA: 0.45, glowR: 0.26 };
        case 'neon': return { kind: 'neon', color: color || NEON.cyan, key: '#04050b', keyW: 0.06, glowR: 0.32, glowA: 0.9 };
        case 'neonRed': return inkSpec('neon', CAMPS.safety);
        case 'neonSun': return inkSpec('neon', NEON.sunset);
        case 'tube': return { kind: 'tube', color: color || NEON.cyan, w: 0.03, glowR: 0.26 };
        case 'soft': return { kind: 'flat', color: color || '#e8eef1', shadow: 'rgba(0,0,0,0.85)', key: '#05070b', keyW: 0.06 };
        case 'calm': return { kind: 'flat', color: '#e3e8ea', shadow: 'rgba(0,0,0,0.9)', key: '#05070b', keyW: 0.05 };
        case 'plate': return { kind: 'plate', plate: '#070a14', edge: color || NEON.magenta, color: '#f1f5f7' };
        case 'spray': return { kind: 'spray', color: color || CAMPS.news };
        case 'warning': return { kind: 'warn', plate: '#eef3ff', ink: '#0a0c10' };
        case 'struck': return { kind: 'flat', color: color || '#cfd5d8', shadow: 'rgba(0,0,0,0.8)', key: '#05070b', keyW: 0.05 };
        default: return inkSpec('soft', color);
    }
}

// ───────────────────────────────────────── raster ─────────────────────────────────────────
function newCanvas(w, h) {
    w = Math.max(4, Math.ceil(fin(w, 4))); h = Math.max(4, Math.ceil(fin(h, 4)));
    if (globalThis.document?.createElement) {
        const c = globalThis.document.createElement('canvas');
        if (c && c._isShimCanvas) { c.width = w; c.height = h; return c; }
    }
    return NAPI.createCanvas(w, h);
}
const rawCanvas = (c) => c._napi || c;
let scratch = null;
function sctx() { if (!scratch) scratch = NAPI.createCanvas(64, 64).getContext('2d'); return scratch; }
const fontStr = (role, px) => `${Math.max(1, Math.round(fin(px, 12)))}px "${(FONTS[role] || FONTS.grotesk).family}"`;

// measure a text item and size its cell. Fills: px box (bl, bt, bw, bh relative to baseline-left origin),
// cell (cw, ch) and the origin inside the cell (ox, oy).
function measureText(it) {
    const g = sctx();
    g.font = fontStr(it.role, it.px);
    g.letterSpacing = `${fin((it.spacing || 0) * it.px, 0).toFixed(2)}px`;
    const m = g.measureText(it.text);
    g.letterSpacing = '0px';
    const al = fin(m.actualBoundingBoxLeft, 0), ar = fin(m.actualBoundingBoxRight, m.width);
    const aa = fin(m.actualBoundingBoxAscent, it.px * 0.72), ad = fin(m.actualBoundingBoxDescent, 0);
    // a stable cap box for layout: ascent at least the cap height (so 'a' and 'A' share a baseline grid)
    const capA = Math.max(aa, it.px * (it.role === 'grotesk' ? 0.73 : 0.66));
    it.box = { l: -al, r: ar, t: -capA, b: Math.max(ad, it.px * 0.08) };
    const ink = it.inkSpec;
    let pad = 6 + it.px * Math.max((ink.keyW || 0) * 1.3, (ink.glowR || 0) * (ink.kind === 'neon' || ink.kind === 'tube' ? 1.3 : 1.1), 0.07);
    let mx = 0, my = 0;
    if (ink.kind === 'paper' || ink.kind === 'plate' || ink.kind === 'warn') { mx = it.px * 0.2; my = it.px * 0.13; pad = Math.max(pad, 6 + it.px * 0.16); }
    if (ink.kind === 'print' || ink.kind === 'stencilSlip') { mx = it.px * 0.2; my = it.px * 0.14; pad = Math.max(pad, 6 + it.px * 0.2); }
    if (ink.kind === 'led') { mx = it.px * 0.26; my = it.px * 0.2; pad = Math.max(pad, 6 + it.px * 0.2); }
    if (ink.kind === 'bare') pad = Math.max(pad, 6 + it.px * 0.16);
    if (it.tubePad) pad = Math.max(pad, 6 + it.px * 0.36);              // room for a neon accent's glow
    if (ink.kind === 'warn') mx += it.px * 0.55;         // room for the warning triangle
    if (ink.kind === 'spray') pad = 6 + it.px * 0.32;
    it.margin = { x: mx, y: my, warnLeft: ink.kind === 'warn' ? it.px * 0.55 : 0 };
    const w = (it.box.r - it.box.l) + 2 * (pad + mx) + (ink.kind === 'warn' ? 0 : 0);
    const h = (it.box.b - it.box.t) + 2 * (pad + my) + (ink.kind === 'spray' ? it.px * 0.35 : 0);
    it.cw = Math.ceil(w); it.ch = Math.ceil(h);
    it.ox = pad + mx - it.box.l + (it.margin.warnLeft * 0.5);
    it.oy = pad + my - it.box.t;
    it.bw = it.box.r - it.box.l; it.bh = it.box.b - it.box.t;
    return it;
}

function cutPoly(g, x0, y0, x1, y1, r, amp) {
    // a cut-paper slip: four corners nudged, one corner sometimes clipped (scissors)
    const j = () => (r() - 0.5) * 2 * amp;
    const pts = [[x0 + j(), y0 + j()], [x1 + j(), y0 + j()], [x1 + j(), y1 + j()], [x0 + j(), y1 + j()]];
    g.beginPath();
    pts.forEach(([x, y], i) => {
        if (i === 1 && r() < 0.35) { g.lineTo(fin(x - amp * 3), fin(y)); g.lineTo(fin(x), fin(y + amp * 3)); return; }
        i ? g.lineTo(fin(x), fin(y)) : g.moveTo(fin(x), fin(y));
    });
    g.closePath();
}

function paperTexture(g, x0, y0, x1, y1, r, base) {
    // aged newsprint: a soft vignette, specks, and the ghost of print from the other side
    const gr = g.createLinearGradient(fin(x0), fin(y0), fin(x1), fin(y1));
    gr.addColorStop(0, mixHex(base, '#ffffff', 0.08)); gr.addColorStop(0.6, base); gr.addColorStop(1, mixHex(base, '#6b5a3a', 0.22));
    g.fillStyle = gr; g.fill();
    g.save(); g.clip();
    const w = x1 - x0, h = y1 - y0;
    g.globalAlpha = 0.07; g.fillStyle = '#3a3226';
    for (let y = y0 + 4; y < y1; y += Math.max(3, h / 9)) g.fillRect(fin(x0 + r() * w * 0.1), fin(y), fin(w * (0.5 + r() * 0.45)), 1.2);
    g.globalAlpha = 1;
    for (let k = 0; k < Math.min(400, w * h / 220); k++) {
        g.fillStyle = r() < 0.7 ? 'rgba(60,45,25,0.13)' : 'rgba(255,255,240,0.18)';
        g.fillRect(fin(x0 + r() * w), fin(y0 + r() * h), 1 + r() * 1.5, 1 + r() * 1.5);
    }
    g.restore();
}

function setFont(g, it) {
    g.font = fontStr(it.role, it.px);
    g.letterSpacing = `${fin((it.spacing || 0) * it.px, 0).toFixed(2)}px`;
    g.textBaseline = 'alphabetic'; g.textAlign = 'left';
    g.lineJoin = 'round'; g.miterLimit = 2;
}

// ── texture tiles (built once, seeded): letterpress voids, paper fibre, paint grain ──
const TILES = new Map();
function tile(kind, size) {
    const key = kind + size;
    if (TILES.has(key)) return TILES.get(key);
    const N = 320, c = NAPI.createCanvas(N, N), g = c.getContext('2d');
    const r = rng(hashStr(key));
    if (kind === 'voids') {                      // letterpress: where the paper was low, the ink skipped
        for (let i = 0; i < N * N / 34; i++) {
            g.fillStyle = `rgba(0,0,0,${(0.15 + r() * 0.5).toFixed(2)})`;
            const s2 = 0.7 + r() * size;
            g.fillRect(r() * N, r() * N, s2, s2 * (0.6 + r() * 0.8));
        }
    } else if (kind === 'fibre') {               // paper: fibres and specks, light and dark
        for (let i = 0; i < N * N / 80; i++) {
            g.fillStyle = r() < 0.6 ? 'rgba(60,45,25,0.10)' : 'rgba(255,255,245,0.16)';
            g.fillRect(r() * N, r() * N, 1 + r() * 2.2, 1 + r() * 0.8);
        }
    } else if (kind === 'fibreDark') {
        for (let i = 0; i < N * N / 80; i++) {
            g.fillStyle = r() < 0.6 ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.25)';
            g.fillRect(r() * N, r() * N, 1 + r() * 2.2, 1 + r() * 0.8);
        }
    } else if (kind === 'paint') {               // the wedge: pigment grain
        for (let i = 0; i < N * N / 45; i++) {
            g.fillStyle = r() < 0.6 ? 'rgba(60,4,2,0.18)' : 'rgba(255,140,110,0.10)';
            g.fillRect(r() * N, r() * N, 1 + r() * 2, 1 + r());
        }
    }
    TILES.set(key, c);
    return c;
}
// fill the current clip with a tile at a seeded offset (deterministic, one draw call)
function tileFill(g, kind, size, x0, y0, w, h, r, op = 'source-over', alpha = 1) {
    const t = tile(kind, size), pat = g.createPattern(t, 'repeat');
    const ox = Math.floor(r() * 320), oy = Math.floor(r() * 320);
    g.save();
    g.globalCompositeOperation = op; g.globalAlpha = alpha;
    g.translate(-ox, -oy);
    g.fillStyle = pat; g.fillRect(fin(x0 + ox), fin(y0 + oy), fin(w), fin(h));
    g.restore();
}

// ── futurist print: the slip, the ink, the second plate ──
// the slip's outline, deterministic per word (followers draw the same outline): corners nudged, one or two edges
// torn (a ragged random walk), sometimes a scissor-clipped corner. Cell coordinates, baseline origin at (x, y).
function slipPoly(it, x, y) {
    const r = rng(hashStr((it.baseKey || it.key) + '|slip'));
    const px = it.px, mx = it.margin.x, my = it.margin.y;
    const x0 = x + it.box.l - mx, x1 = x + it.box.r + mx, y0 = y + it.box.t - my, y1 = y + it.box.b + my;
    const jit = px * 0.025;
    const C = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(([a, b]) => [a + (r() - 0.5) * 2 * jit, b + (r() - 0.5) * 2 * jit]);
    const torn = it.inkSpec?.tornAll ? [true, true, true, true] : [r() < 0.4, r() < 0.3, r() < 0.45, r() < 0.3];
    if (!torn.some(Boolean) && r() < 0.5) torn[Math.floor(r() * 4)] = true;
    const clipCorner = r() < 0.3 ? Math.floor(r() * 4) : -1;
    const pts = [], tornSeg = [];
    for (let s = 0; s < 4; s++) {
        const [ax, ay] = C[s], [bx, by] = C[(s + 1) % 4];
        if (s === clipCorner) { const k = px * 0.12; pts.push([ax + (bx - ax) / Math.hypot(bx - ax, by - ay) * k, ay + (by - ay) / Math.hypot(bx - ax, by - ay) * k]); }
        else pts.push([ax, ay]);
        if (!torn[s]) continue;
        const L = Math.hypot(bx - ax, by - ay), N = Math.max(6, Math.round(L / (px * 0.07)));
        const nx = (by - ay) / L, ny = -(bx - ax) / L;            // outward for a clockwise outline (y down)
        let off = 0;
        const seg = [];
        for (let i = 1; i < N; i++) {
            off = Math.max(-1, Math.min(1, off + (r() - 0.5) * 1.1));
            const u = i / N, d = (off * 0.55 + (r() - 0.5) * 0.7) * px * 0.05 - px * 0.015;
            const q = [ax + (bx - ax) * u + nx * d, ay + (by - ay) * u + ny * d];
            pts.push(q); seg.push(q);
        }
        tornSeg.push(seg);
    }
    return { pts, tornSeg, box: [x0, y0, x1, y1] };
}
function pathPoly(g, pts) { g.beginPath(); pts.forEach(([a, b], i) => (i ? g.lineTo(fin(a), fin(b)) : g.moveTo(fin(a), fin(b)))); g.closePath(); }

// the slip itself: stock colour, fibre, a little grime, the torn edges' white fibrous core
function drawSlip(g, it, x, y, r, color) {
    const S = slipPoly(it, x, y), [x0, y0, x1, y1] = S.box, px = it.px;
    g.save();
    pathPoly(g, S.pts);
    g.shadowColor = 'rgba(0,0,0,0.7)'; g.shadowBlur = fin(px * 0.12); g.shadowOffsetX = fin(px * 0.025); g.shadowOffsetY = fin(px * 0.045);
    g.fillStyle = color; g.fill();
    g.shadowColor = 'rgba(0,0,0,0)';
    g.clip();
    const dark = hexRgb(color).reduce((a, b) => a + b, 0) < 200;
    const gr = g.createLinearGradient(fin(x0), fin(y0), fin(x1), fin(y1));
    gr.addColorStop(0, dark ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.10)'); gr.addColorStop(0.55, 'rgba(0,0,0,0)'); gr.addColorStop(1, dark ? 'rgba(0,0,0,0.25)' : 'rgba(70,50,20,0.16)');
    g.fillStyle = gr; g.fillRect(fin(x0 - 4), fin(y0 - 4), fin(x1 - x0 + 8), fin(y1 - y0 + 8));
    tileFill(g, dark ? 'fibreDark' : 'fibre', 0, x0 - 4, y0 - 4, x1 - x0 + 8, y1 - y0 + 8, r);
    g.restore();
    // the torn edges: a light fibrous core where the paper ripped
    g.save();
    g.strokeStyle = dark ? 'rgba(200,190,170,0.35)' : 'rgba(255,252,240,0.75)'; g.lineWidth = Math.max(1, px * 0.016); g.lineJoin = 'round';
    for (const seg of S.tornSeg) { if (seg.length < 2) continue; g.beginPath(); seg.forEach(([a, b], i) => (i ? g.lineTo(fin(a), fin(b)) : g.moveTo(fin(a), fin(b)))); g.stroke(); }
    g.restore();
    return S;
}

// the ink as a letterpress impression: flat colour, a slight spread at the edges, voids where the paper was low
function inkLayer(it, x, y, color, r, { spread = 0.012, grain = 1 } = {}) {
    const c = NAPI.createCanvas(Math.max(4, it.cw), Math.max(4, it.ch)), g = c.getContext('2d');
    setFont(g, it);
    g.fillStyle = color; g.fillText(it.text, x, y);
    if (spread > 0) { g.globalAlpha = 0.55; g.strokeStyle = color; g.lineWidth = Math.max(0.8, it.px * spread); g.strokeText(it.text, x, y); g.globalAlpha = 1; }
    const size = it.px < 70 ? 1 : it.px < 160 ? 2 : 3;
    tileFill(g, 'voids', size, 0, 0, c.width, c.height, r, 'destination-out', Math.min(1, 0.85 * grain));
    g.globalCompositeOperation = 'destination-out';
    // two faint worn streaks across the type (the forme was inked unevenly)
    for (let i = 0; i < 2; i++) {
        g.strokeStyle = `rgba(0,0,0,${(0.06 + r() * 0.08).toFixed(2)})`; g.lineWidth = it.px * (0.012 + r() * 0.02);
        const yy = y + it.box.t + r() * it.bh;
        g.beginPath(); g.moveTo(x + it.box.l, yy); g.lineTo(x + it.box.r, yy + (r() - 0.5) * it.px * 0.2); g.stroke();
    }
    return c;
}
// two plates: the ghost (second colour) printed slightly off register under the key ink
function printInk(g, it, x, y, r, ink, ghost) {
    const off = it.px * (0.018 + r() * 0.016), ang = r() * Math.PI * 2;
    if (ghost && r() < 0.75) {
        const gl = inkLayer(it, x + Math.cos(ang) * off, y + Math.sin(ang) * off, ghost, r, { spread: 0.008, grain: 1.6 });
        g.save(); g.globalAlpha = 0.5; g.drawImage(gl, 0, 0); g.restore();
    }
    g.drawImage(inkLayer(it, x, y, ink, r), 0, 0);
}

// LED type: a dot-matrix sign. The pixel font's own 8x8 grid is the lamp grid: one font pixel = one lamp, lit
// lamps glow, the unlit ones show faintly.
function drawLED(g, it, x, y, color) {
    const F = it.px, q = F / 8;
    const c = NAPI.createCanvas(Math.max(4, it.cw), Math.max(4, it.ch)), m = c.getContext('2d');
    setFont(m, it); m.fillStyle = '#fff'; m.fillText(it.text, x, y);
    const data = m.getImageData(0, 0, c.width, c.height).data;
    const cols = Math.round(it.bw / q) + 2;
    const lit = [], off = [];
    for (let j = -8; j <= 1; j++) for (let i = -1; i < cols; i++) {
        const cx = x + it.box.l + (i + 0.5) * q, cy = y + (j + 0.5) * q;
        const ix = Math.round(cx), iy = Math.round(cy);
        const a = ix >= 0 && iy >= 0 && ix < c.width && iy < c.height ? data[(iy * c.width + ix) * 4 + 3] : 0;
        if (a > 110) lit.push([cx, cy]); else if (j >= -7 && j <= 0 && i >= 0 && i < cols - 1) off.push([cx, cy]);
    }
    const dots = (list, rad) => { g.beginPath(); for (const [a, b] of list) { g.moveTo(fin(a + rad), fin(b)); g.arc(fin(a), fin(b), rad, 0, Math.PI * 2); } };
    g.save();
    dots(off, q * 0.36); g.fillStyle = rgba(color, 0.09); g.fill();
    dots(lit, q * 0.42); g.shadowColor = color; g.shadowBlur = fin(q * 1.6); g.fillStyle = color; g.fill();
    g.shadowBlur = 0; dots(lit, q * 0.22); g.fillStyle = mixHex(color, '#ffffff', 0.65); g.fill();
    g.restore();
}

// a neon-tube accent, drawn in a follower cell (same geometry as its word): 'outline' traces the glyphs, 'frame'
// traces the slip, 'under' is a bar beneath the word or its slip
function drawTubeAccent(g, it, x, y) {
    const ink = it.inkSpec, px = it.px, col = ink.color;
    const base = ink.base || {};
    const stroke = (pathFn, w) => {
        g.save(); g.lineCap = 'round'; g.lineJoin = 'round';
        g.shadowColor = col; g.shadowBlur = fin(px * 0.22);
        g.strokeStyle = rgba(col, 0.95); g.lineWidth = Math.max(1.5, px * w); pathFn(); g.stroke();
        g.shadowBlur = 0; g.strokeStyle = mixHex(col, '#ffffff', 0.7); g.lineWidth = Math.max(0.8, px * w * 0.38); pathFn(); g.stroke();
        g.restore();
    };
    const onSlip = SLIP_KINDS.has(base.kind);
    if (ink.mode === 'outline' && !onSlip) {
        g.save(); setFont(g, it);
        g.shadowColor = col; g.shadowBlur = fin(px * 0.2);
        g.strokeStyle = rgba(col, 0.95); g.lineWidth = Math.max(1.5, px * 0.022); g.strokeText(it.text, x, y);
        g.shadowBlur = 0; g.strokeStyle = mixHex(col, '#ffffff', 0.7); g.lineWidth = Math.max(0.8, px * 0.008); g.strokeText(it.text, x, y);
        g.restore();
        return;
    }
    if (onSlip && ink.mode !== 'under') {
        const S = slipPoly(it, x, y);
        stroke(() => pathPoly(g, S.pts.map(([a, b]) => [a, b])), 0.022);
        return;
    }
    // under: a straight tube under the word (or under its slip), a little longer than the word
    const yb = onSlip ? slipPoly(it, x, y).box[3] + px * 0.05 : y + Math.max(it.box.b, px * 0.1) + px * 0.09;
    const xa = x + it.box.l - px * 0.12, xb = x + it.box.r + px * 0.12;
    stroke(() => { g.beginPath(); g.moveTo(fin(xa), fin(yb)); g.lineTo(fin(xb), fin(yb)); }, 0.03);
}

// draw a text item with its baseline-left origin at (x, y)
function drawText(g, it, x, y, r) {
    const ink = it.inkSpec, px = it.px, T = it.text;
    x = fin(x); y = fin(y);
    const top = y + it.box.t, bot = y + it.box.b, left = x + it.box.l, right = x + it.box.r;
    g.save();
    setFont(g, it);
    if (ink.kind === 'paper' || ink.kind === 'plate' || ink.kind === 'warn') {
        const mx = it.margin.x, my = it.margin.y;
        const x0 = left - mx - it.margin.warnLeft * 0.5, x1 = right + mx - it.margin.warnLeft * 0.5 + (ink.kind === 'warn' ? 0 : 0);
        g.save();
        cutPoly(g, x0 - (ink.kind === 'warn' ? it.margin.warnLeft * 0.5 : 0), top - my, x1 + (ink.kind === 'warn' ? it.margin.warnLeft * 0.5 : 0), bot + my, r, px * (ink.kind === 'warn' ? 0.01 : 0.035));
        g.shadowColor = 'rgba(0,0,0,0.75)'; g.shadowBlur = fin(px * 0.14); g.shadowOffsetX = fin(px * 0.03); g.shadowOffsetY = fin(px * 0.05);
        g.fillStyle = ink.kind === 'plate' ? rgba(ink.plate, 0.9) : (ink.paper || ink.plate);
        g.fill();
        g.shadowColor = 'rgba(0,0,0,0)';
        if (ink.kind === 'paper') paperTexture(g, x0, top - my, x1, bot + my, r, ink.paper);
        if (ink.kind === 'plate') {                       // a neon edge along the slip's bottom
            g.strokeStyle = ink.edge; g.lineWidth = Math.max(2, px * 0.03);
            g.shadowColor = ink.edge; g.shadowBlur = fin(px * 0.12);
            g.beginPath(); g.moveTo(fin(x0 + 2), fin(bot + my - 1)); g.lineTo(fin(x1 - 2), fin(bot + my - 1)); g.stroke();
        }
        if (ink.kind === 'warn') {                        // a black border and the warning triangle
            g.strokeStyle = ink.ink; g.lineWidth = Math.max(2, px * 0.05); g.stroke();
            const s = px * 0.62, cx = x0 + px * 0.05 + s * 0.5, cy = (top + bot) * 0.5 + s * 0.06;
            g.beginPath(); g.moveTo(fin(cx), fin(cy - s * 0.5)); g.lineTo(fin(cx + s * 0.55), fin(cy + s * 0.45)); g.lineTo(fin(cx - s * 0.55), fin(cy + s * 0.45)); g.closePath();
            g.fillStyle = ink.ink; g.fill();
            g.fillStyle = ink.plate; g.fillRect(fin(cx - s * 0.05), fin(cy - s * 0.18), fin(s * 0.1), fin(s * 0.36));
            g.fillRect(fin(cx - s * 0.05), fin(cy + s * 0.25), fin(s * 0.1), fin(s * 0.1));
        }
        g.restore();
        g.fillStyle = ink.kind === 'plate' ? ink.color : ink.ink;
        if (ink.kind === 'plate') { g.shadowColor = rgba(ink.edge, 0.6); g.shadowBlur = fin(px * 0.1); }
        g.fillText(T, x, y);
    } else if (ink.kind === 'grad') {
        g.save();
        g.shadowColor = rgba(ink.glow, ink.glowA); g.shadowBlur = fin(px * ink.glowR);
        g.strokeStyle = ink.key; g.lineWidth = fin(px * ink.keyW * 2);
        g.strokeText(T, x, y);
        g.restore();
        g.strokeStyle = ink.key; g.lineWidth = fin(px * ink.keyW * 2); g.strokeText(T, x, y);
        const gr = g.createLinearGradient(0, fin(top), 0, fin(y + Math.max(it.box.b, px * 0.02)));
        for (const [k, c] of ink.stops) gr.addColorStop(k, c);
        g.fillStyle = gr; g.fillText(T, x, y);
        g.strokeStyle = 'rgba(255,255,255,0.35)'; g.lineWidth = Math.max(1, px * 0.008); g.strokeText(T, x, y);
    } else if (ink.kind === 'neon') {
        g.save();
        g.shadowColor = ink.color; g.shadowBlur = fin(px * ink.glowR);
        g.fillStyle = rgba(ink.color, 0.9); g.fillText(T, x, y);
        g.shadowBlur = fin(px * ink.glowR * 0.4); g.fillText(T, x, y);
        g.restore();
        g.strokeStyle = ink.key; g.lineWidth = fin(px * ink.keyW * 2); g.strokeText(T, x, y);
        const gr = g.createLinearGradient(0, fin(top), 0, fin(bot));
        gr.addColorStop(0, ink.color); gr.addColorStop(0.45, mixHex(ink.color, '#ffffff', 0.55)); gr.addColorStop(1, ink.color);
        g.fillStyle = gr; g.fillText(T, x, y);
    } else if (ink.kind === 'tube') {
        g.save();
        g.shadowColor = ink.color; g.shadowBlur = fin(px * ink.glowR);
        g.strokeStyle = ink.color; g.lineWidth = fin(px * ink.w); g.strokeText(T, x, y);
        g.restore();
        g.strokeStyle = mixHex(ink.color, '#ffffff', 0.6); g.lineWidth = fin(px * ink.w * 0.45); g.strokeText(T, x, y);
    } else if (ink.kind === 'spray') {
        g.save();
        g.shadowColor = rgba(ink.color, 0.9); g.shadowBlur = fin(px * 0.22);
        g.fillStyle = rgba(ink.color, 0.55); g.fillText(T, x, y);
        g.restore();
        // mist: fine dots around the letters
        const w = right - left, h = bot - top;
        for (let k = 0; k < Math.min(900, w * h / 140); k++) {
            const dx = left - px * 0.15 + r() * (w + px * 0.3), dy = top - px * 0.15 + r() * (h + px * 0.3);
            g.fillStyle = rgba(ink.color, 0.12 + r() * 0.35);
            g.beginPath(); g.arc(fin(dx), fin(dy), fin(0.6 + r() * px * 0.012), 0, Math.PI * 2); g.fill();
        }
        g.fillStyle = ink.color; g.fillText(T, x, y);
        // drips: thin runs from the letters' feet
        g.strokeStyle = rgba(ink.color, 0.85); g.lineCap = 'round';
        const nd = 3 + Math.floor(r() * 5);
        for (let k = 0; k < nd; k++) {
            const dx = left + w * (0.05 + 0.9 * r()), len = px * (0.12 + r() * 0.42);
            g.lineWidth = fin(px * (0.018 + r() * 0.02));
            g.beginPath(); g.moveTo(fin(dx), fin(y - px * 0.08)); g.lineTo(fin(dx + px * 0.01), fin(y + len)); g.stroke();
        }
    } else if (ink.kind === 'print') {
        drawSlip(g, it, x, y, r, ink.paper);
        printInk(g, it, x, y, r, ink.ink, ink.ghost);
    } else if (ink.kind === 'stencilSlip') {
        drawSlip(g, it, x, y, r, ink.plate);
        g.save(); g.shadowColor = rgba(ink.color, 0.7); g.shadowBlur = fin(px * 0.08);
        g.drawImage(inkLayer(it, x, y, ink.color, r, { spread: 0.02, grain: 0.6 }), 0, 0); g.restore();
    } else if (ink.kind === 'led') {
        drawSlip(g, it, x, y, r, ink.plate);
        drawLED(g, it, x, y, ink.color);
    } else if (ink.kind === 'bare') {
        g.save();
        g.shadowColor = 'rgba(0,0,0,0.85)'; g.shadowBlur = fin(px * 0.14); g.shadowOffsetY = fin(px * 0.03);
        g.strokeStyle = ink.key; g.lineWidth = fin(px * ink.keyW * 2); g.strokeText(T, x, y);
        g.restore();
        g.drawImage(inkLayer(it, x, y, ink.color, r, { spread: 0.01, grain: 0.8 }), 0, 0);
    } else if (ink.kind === 'tubeAccent') {
        drawTubeAccent(g, it, x, y);
    } else if (ink.kind === 'wedgeInk') {
        // Depero's wedge, the word's overlay: the wedge's own paint covers the paper-white letters inside it and the
        // letters print black on the red. A separate sprite, so it leaves with the wedge under hush.
        g.save();
        paintWedge(g, it.wedgeLocal, x, y, r);
        g.drawImage(inkLayer(it, x, y, INK, r, { spread: 0.01, grain: 0.9 }), 0, 0);
        g.restore();
    } else if (ink.kind === 'inkOnly') {                // printed on a slip that is drawn elsewhere
        g.fillStyle = ink.color; g.fillText(T, x, y);
    } else {                                            // flat: soft white (or struck), a dark key and shadow
        g.save();
        g.shadowColor = ink.shadow; g.shadowBlur = fin(px * 0.16); g.shadowOffsetY = fin(px * 0.03);
        g.strokeStyle = ink.key; g.lineWidth = fin(px * ink.keyW * 2); g.strokeText(T, x, y);
        g.restore();
        g.fillStyle = ink.color; g.fillText(T, x, y);
    }
    g.restore();
}

// the hand-drawn strike: one decisive crayon stroke across the phrase, overshooting both ends, quick attack and a
// longer release, ragged edges and a waxy grain; a quicker second stroke comes back across it. Drawn into a w x h
// cell; revealed left-to-right by the shader's wipe.
function drawStrike(g, x, y, w, h, r, color) {
    const dark = color === STRIKE_DARK;
    const strokes = [
        { th: h * 0.4, y0: h * 0.56, tilt: -h * (0.12 + r() * 0.18), u0: 0, u1: 1 },
        { th: h * 0.2, y0: h * 0.44, tilt: h * (0.12 + r() * 0.22), u0: 0.05, u1: 0.97 },
    ];
    for (const s of strokes) {
        const N = 56, top = [], bot = [];
        const ph = r() * 6.283;
        for (let i = 0; i <= N; i++) {
            const u = s.u0 + (s.u1 - s.u0) * (i / N), xx = x + u * w;
            const yy = y + s.y0 + s.tilt * (u - 0.5) + Math.sin(u * 5.3 + ph) * h * 0.035;
            const v = (i / N);
            const press = Math.min(1, v * 10, (1 - v) * 4);
            const t = s.th * (0.28 + 0.72 * press);
            top.push([xx, yy - t / 2 + (r() - 0.5) * s.th * 0.2]);
            bot.push([xx, yy + t / 2 + (r() - 0.5) * s.th * 0.2]);
        }
        g.save();
        g.beginPath(); top.forEach(([a, b], i) => (i ? g.lineTo(fin(a), fin(b)) : g.moveTo(fin(a), fin(b))));
        for (let i = bot.length - 1; i >= 0; i--) g.lineTo(fin(bot[i][0]), fin(bot[i][1]));
        g.closePath();
        g.shadowColor = dark ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.9)'; g.shadowBlur = fin(h * 0.14); g.shadowOffsetY = fin(h * 0.03);
        g.fillStyle = color; g.fill();
        g.restore();
        // wax grain: specks where the crayon skipped (one pattern fill, clipped to the stroke)
        g.save();
        g.beginPath(); top.forEach(([a, b], i) => (i ? g.lineTo(fin(a), fin(b)) : g.moveTo(fin(a), fin(b))));
        for (let i = bot.length - 1; i >= 0; i--) g.lineTo(fin(bot[i][0]), fin(bot[i][1]));
        g.closePath(); g.clip();
        tileFill(g, 'voids', 2, x - 4, y - 4, w + 8, h + 8, r, 'destination-out', 0.9);
        g.restore();
    }
}
const STRIKE_DARK = '#16121c';

// geometric signs as paths (fonts disagree on − ∅ ≠): neon tube strokes
function drawSign(g, sign, x, y, s, color) {
    const L = (a, b, c, d) => { g.moveTo(fin(x + a * s), fin(y + b * s)); g.lineTo(fin(x + c * s), fin(y + d * s)); };
    g.save();
    g.lineCap = 'round'; g.lineJoin = 'round';
    const pass = (w, col, blur) => {
        g.strokeStyle = col; g.lineWidth = fin(s * w); g.shadowColor = color; g.shadowBlur = fin(blur);
        g.beginPath();
        if (sign === '+') { L(0.15, 0.5, 0.85, 0.5); L(0.5, 0.15, 0.5, 0.85); }
        else if (sign === '−') { L(0.12, 0.5, 0.88, 0.5); }
        else if (sign === '=') { L(0.14, 0.36, 0.86, 0.36); L(0.14, 0.64, 0.86, 0.64); }
        else if (sign === '≠') { L(0.14, 0.36, 0.86, 0.36); L(0.14, 0.64, 0.86, 0.64); L(0.68, 0.12, 0.32, 0.88); }
        else if (sign === '×') { L(0.2, 0.2, 0.8, 0.8); L(0.8, 0.2, 0.2, 0.8); }
        else if (sign === '∅') { g.moveTo(fin(x + 0.85 * s), fin(y + 0.5 * s)); g.arc(fin(x + 0.5 * s), fin(y + 0.5 * s), fin(0.35 * s), 0, Math.PI * 2); L(0.82, 0.1, 0.18, 0.9); }
        else if (sign === '→') { L(0.06, 0.5, 0.9, 0.5); L(0.62, 0.24, 0.92, 0.5); L(0.62, 0.76, 0.92, 0.5); }
        g.stroke();
    };
    pass(0.13, '#04050b', s * 0.25);
    pass(0.085, color, s * 0.3);
    pass(0.035, mixHex(color, '#ffffff', 0.7), 0);
    g.restore();
}

// the trajectory band of ZTT 1915: a long tapered stroke with a rounded head, dark, one neon edge
function drawBand(g, x, y, w, h, r, edge) {
    g.save();
    const yy = (u) => y + h * (0.5 + 0.08 * Math.sin(u * 3.1 + 1));
    const th = (u) => h * (0.12 + 0.88 * Math.pow(u, 0.7)) * 0.5;
    const N = 40;
    g.beginPath();
    for (let i = 0; i <= N; i++) { const u = i / N; g.lineTo(fin(x + u * w * 0.94), fin(yy(u) - th(u))); }
    g.arc(fin(x + w * 0.94), fin(yy(1)), fin(th(1)), -Math.PI / 2, Math.PI / 2);
    for (let i = N; i >= 0; i--) { const u = i / N; g.lineTo(fin(x + u * w * 0.94), fin(yy(u) + th(u))); }
    g.closePath();
    g.shadowColor = rgba(edge, 0.5); g.shadowBlur = fin(h * 0.15);
    g.fillStyle = 'rgba(6,8,18,0.86)'; g.fill();
    g.shadowBlur = 0;
    g.strokeStyle = rgba(edge, 0.9); g.lineWidth = Math.max(2, h * 0.025); g.stroke();
    g.restore();
}

function drawWedge(g, tri, light) {
    g.save();
    g.beginPath(); g.moveTo(fin(tri[0][0]), fin(tri[0][1])); g.lineTo(fin(tri[1][0]), fin(tri[1][1])); g.lineTo(fin(tri[2][0]), fin(tri[2][1])); g.closePath();
    const gr = g.createLinearGradient(fin(tri[0][0]), fin(tri[0][1]), fin(tri[2][0]), fin(tri[2][1]));
    gr.addColorStop(0, light[0]); gr.addColorStop(1, light[1]);
    g.shadowColor = rgba(light[1], 0.6); g.shadowBlur = 24;
    g.fillStyle = gr; g.fill();
    g.restore();
}

// the red wedge as data (FH coordinates): a roughened outline (painted, torn) and brush streaks toward the tip
function wedgePaint(r, tri) {
    const poly = [];
    for (let s = 0; s < 3; s++) {
        const [ax, ay] = tri[s], [bx, by] = tri[(s + 1) % 3];
        const L = Math.hypot(bx - ax, by - ay), N = Math.max(8, Math.round(L / 0.011));
        const nx = (by - ay) / L, ny = -(bx - ax) / L;
        let off = 0;
        for (let i = 0; i < N; i++) {
            off = Math.max(-1, Math.min(1, off + (r() - 0.5) * 0.9));
            const d = i === 0 ? 0 : off * 0.0065 + (r() - 0.5) * 0.0045 + (r() < 0.04 ? -0.012 * r() : 0);
            const u = i / N;
            poly.push([ax + (bx - ax) * u + nx * d, ay + (by - ay) * u + ny * d]);
        }
    }
    const [p0, p1, p2] = tri;
    const at = (u, v) => { const ex = p0[0] + (p1[0] - p0[0]) * u, ey = p0[1] + (p1[1] - p0[1]) * u; return [ex + (p2[0] - ex) * v * (1 - u), ey + (p2[1] - ey) * v * (1 - u)]; };
    const streaks = [];
    for (let k = 0; k < 18; k++) {
        const v = r(), u0 = r() * 0.35, u1 = 0.55 + r() * 0.45;
        streaks.push({ a: at(u0, v), b: at(u1, v + (r() - 0.5) * 0.08), w: 0.003 + r() * 0.012,
            c: r() < 0.55 ? `rgba(92,6,4,${(0.14 + r() * 0.16).toFixed(2)})` : `rgba(236,72,52,${(0.08 + r() * 0.12).toFixed(2)})` });
    }
    return { poly, streaks };
}
function mapPaint(P, map, ws) {
    return { poly: P.poly.map(map), streaks: P.streaks.map((s) => ({ a: map(s.a), b: map(s.b), w: s.w * ws, c: s.c })), edgeW: 0.007 * ws, ws };
}
// paint the wedge (the clip stays ACTIVE: the caller restores, so the overlay can print its letters inside it)
function paintWedge(g, M, ox, oy, r) {
    const path = () => { g.beginPath(); M.poly.forEach(([a, b], i) => (i ? g.lineTo(fin(a + ox), fin(b + oy)) : g.moveTo(fin(a + ox), fin(b + oy)))); g.closePath(); };
    path(); g.clip();
    g.fillStyle = RED; g.fillRect(-20000, -20000, 40000, 40000);
    g.lineCap = 'round';
    for (const st of M.streaks) {
        g.strokeStyle = st.c; g.lineWidth = Math.max(1, st.w);
        g.beginPath(); g.moveTo(fin(st.a[0] + ox), fin(st.a[1] + oy)); g.lineTo(fin(st.b[0] + ox), fin(st.b[1] + oy)); g.stroke();
    }
    const xs = M.poly.map((q) => q[0] + ox), ys = M.poly.map((q) => q[1] + oy);
    const bx0 = Math.max(Math.min(...xs), -50), by0 = Math.max(Math.min(...ys), -50), bx1 = Math.min(Math.max(...xs), 6000), by1 = Math.min(Math.max(...ys), 6000);
    tileFill(g, 'paint', 0, bx0, by0, bx1 - bx0, by1 - by0, r);
    path(); g.strokeStyle = 'rgba(70,5,3,0.6)'; g.lineWidth = Math.max(1.5, M.edgeW * 2); g.stroke();
}
// CAPITAL LETTERS' card: a white post, its header and footer generic (no platform, no names), torn out
function drawPostCard(g, c, r) {
    const { pad, S, PX } = c, W = c.cw - 2 * pad, H = c.ch - 2 * pad, u = PX * S;
    const x0 = pad, y0 = pad, x1 = pad + W, y1 = pad + H;
    const pts = [[x0, y0], [x1, y0]];
    // the right side and the bottom torn off
    const N = 40;
    for (let i = 1; i <= 12; i++) pts.push([x1 + (r() - 0.6) * u * 0.012, y0 + (y1 - y0) * i / 12]);
    for (let i = 1; i < N; i++) pts.push([x1 - (x1 - x0) * i / N, y1 + (r() - 0.65) * u * 0.02 - (i % 7 === 0 ? u * 0.012 : 0)]);
    pts.push([x0, y1]);
    g.save();
    pathPoly(g, pts);
    g.shadowColor = 'rgba(0,0,0,0.75)'; g.shadowBlur = fin(u * 0.025); g.shadowOffsetY = fin(u * 0.008);
    g.fillStyle = '#f6f6f3'; g.fill();
    g.restore();
    g.save(); pathPoly(g, pts); g.clip();
    const gr = g.createLinearGradient(0, y0, 0, y1); gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(1, 'rgba(0,0,0,0.06)');
    g.fillStyle = gr; g.fillRect(x0, y0, W, H);
    // header: a blank avatar, a bold name bar, a lighter handle bar, a time
    const hy = y0 + c.head * u * 0.5;
    g.fillStyle = '#2b2f36'; g.beginPath(); g.arc(x0 + u * 0.05, hy, u * 0.032, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#8a9099'; g.beginPath(); g.arc(x0 + u * 0.05, hy - u * 0.008, u * 0.011, 0, Math.PI * 2); g.fill();
    g.beginPath(); g.ellipse(x0 + u * 0.05, hy + u * 0.02, u * 0.019, u * 0.012, 0, Math.PI, 0); g.fill();
    const bar = (x, y, w, h, col) => { g.fillStyle = col; g.beginPath(); if (g.roundRect) g.roundRect(x, y, w, h, h / 2); else g.rect(x, y, w, h); g.fill(); };
    bar(x0 + u * 0.095, hy - u * 0.022, u * 0.2, u * 0.019, '#1d2025');
    bar(x0 + u * 0.095, hy + u * 0.008, u * 0.13, u * 0.014, '#b7bcc3');
    g.fillStyle = '#8a9099'; g.font = `${Math.round(u * 0.018)}px "UF Space Mono"`; g.fillText('· now', x0 + u * 0.24, hy + u * 0.02);
    g.fillStyle = '#5a6068'; for (let k = 0; k < 3; k++) { g.beginPath(); g.arc(x1 - u * 0.05 + k * u * 0.012, hy - u * 0.01, u * 0.0035, 0, 6.283); g.fill(); }
    // footer: reply, repost, like, views (generic outlines) and counts
    const fy = y1 - c.foot * u * 0.45;
    g.strokeStyle = '#6b717a'; g.lineWidth = Math.max(1.5, u * 0.0035); g.fillStyle = '#6b717a'; g.font = `${Math.round(u * 0.019)}px "UF Space Mono"`;
    const counts = ['2.1K', '18K', '61K', '9.4M'];
    for (let k = 0; k < 4; k++) {
        const ix = x0 + u * 0.06 + k * (W - u * 0.12) / 4, s2 = u * 0.013;
        g.beginPath();
        if (k === 0) { g.ellipse(ix, fy, s2 * 1.2, s2 * 0.9, 0, 0, Math.PI * 2); }
        else if (k === 1) { g.moveTo(ix - s2, fy - s2 * 0.4); g.lineTo(ix + s2, fy - s2 * 0.4); g.lineTo(ix + s2 * 0.6, fy - s2 * 0.9); g.moveTo(ix + s2, fy + s2 * 0.4); g.lineTo(ix - s2, fy + s2 * 0.4); g.lineTo(ix - s2 * 0.6, fy + s2 * 0.9); }
        else if (k === 2) { g.moveTo(ix, fy + s2); g.bezierCurveTo(ix - s2 * 1.8, fy - s2 * 0.2, ix - s2 * 0.6, fy - s2 * 1.6, ix, fy - s2 * 0.5); g.bezierCurveTo(ix + s2 * 0.6, fy - s2 * 1.6, ix + s2 * 1.8, fy - s2 * 0.2, ix, fy + s2); }
        else { g.moveTo(ix - s2, fy + s2); g.lineTo(ix - s2, fy); g.moveTo(ix, fy + s2); g.lineTo(ix, fy - s2); g.moveTo(ix + s2, fy + s2); g.lineTo(ix + s2, fy - s2 * 0.4); }
        g.stroke();
        g.fillText(counts[k], ix + s2 * 1.8, fy + s2 * 0.6);
    }
    g.restore();
    // the torn edge's paper core
    g.save(); g.strokeStyle = 'rgba(255,255,255,0.9)'; g.lineWidth = Math.max(1, u * 0.003);
    g.beginPath(); pts.slice(2).forEach(([a, b], i) => (i ? g.lineTo(fin(a), fin(b)) : g.moveTo(fin(a), fin(b)))); g.stroke(); g.restore();
}

// ───────────────────────────────────────── atlas ─────────────────────────────────────────
// shelf-pack cells; draw each through its own clip so glows never bleed into a neighbour
function packAtlas(cells, maxW = 2048) {
    const PAD = 14;                                  // mip-safe gutters (words are minified up to ~6x in hush and fly-ins)
    let x = PAD, y = PAD, rowH = 0, W = 0;
    const widest = Math.max(...cells.map((c) => c.cw + 2 * PAD), 64);
    const AW = Math.min(4096, Math.max(widest, Math.min(maxW, 2048)));
    const order = cells.map((c, i) => i).sort((a, b) => cells[b].ch - cells[a].ch);
    for (const i of order) {
        const c = cells[i];
        if (x + c.cw + PAD > AW) { x = PAD; y += rowH + PAD; rowH = 0; }
        c.ax = x; c.ay = y; x += c.cw + PAD; rowH = Math.max(rowH, c.ch); W = Math.max(W, x);
    }
    return { w: Math.max(8, AW), h: Math.max(8, y + rowH + PAD) };
}

function rasterize(cells, seed) {
    const A = packAtlas(cells);
    const cv = newCanvas(A.w, A.h);
    const g = cv.getContext('2d');
    g.clearRect(0, 0, A.w, A.h);
    const prof = globalThis.PAROLE_PROFILE ? [] : null;
    for (const c of cells) {
        const r = rng(seed ^ hashStr(c.key || c.text || c.type));
        const tc = prof ? performance.now() : 0;
        g.save();
        g.beginPath(); g.rect(c.ax, c.ay, c.cw, c.ch); g.clip();
        g.translate(c.ax, c.ay);
        if (c.type === 'text') drawText(g, c, c.ox, c.oy, r);
        else if (c.type === 'strike') drawStrike(g, c.cw * 0.02, 0, c.cw * 0.96, c.ch, r, c.color);
        else if (c.type === 'sign') drawSign(g, c.sign, c.cw * 0.12, c.ch * 0.12, Math.min(c.cw, c.ch) * 0.76, c.color);
        else if (c.type === 'band') drawBand(g, c.cw * 0.02, c.ch * 0.08, c.cw * 0.96, c.ch * 0.84, r, c.color);
        else if (c.type === 'wedge') drawWedge(g, c.tri, c.light);
        else if (c.type === 'wedge2') {
            g.save(); g.shadowColor = 'rgba(0,0,0,0.6)'; g.shadowBlur = 10; pathPoly(g, c.paint.poly); g.fillStyle = RED; g.fill(); g.restore();
            g.save(); paintWedge(g, c.paint, 0, 0, r); g.restore();
        }
        else if (c.type === 'post') drawPostCard(g, c, r);
        else if (c.type === 'block') c.paint(g, r);
        g.restore();
        if (prof) prof.push([performance.now() - tc, c.type, c.inkSpec?.kind || '', (c.text || c.key || '').slice(0, 18), c.cw + 'x' + c.ch]);
    }
    if (prof) { prof.sort((a, b) => b[0] - a[0]); console.log(`[parole-prof] atlas ${A.w}x${A.h}: ` + prof.slice(0, 6).map((q) => `${q[0].toFixed(1)}ms ${q[1]}/${q[2]} "${q[3]}" ${q[4]}`).join(' | ')); }
    return { canvas: cv, w: A.w, h: A.h };
}

// ───────────────────────────────────────── word style ─────────────────────────────────────────
function sectionAt(t) { for (const [n, a, b] of SECTIONS) if (t >= a && t < b) return n; return 'outro'; }
function secKey(sec) {
    if (!sec) return 'verse1';
    const s = sec.toLowerCase().replace(/[^a-z0-9]/g, '');
    if (s.startsWith('verse')) return 'verse' + (s.match(/\d+/)?.[0] || '1');
    if (s.startsWith('prechorus') || s.startsWith('pre')) return (s.match(/2/) ? 'pre2' : 'pre1');
    if (s.startsWith('finalchorus') || s === 'final') return 'final';
    if (s.startsWith('chorus')) return s.includes('2') ? 'chorus2' : 'chorus1';
    if (s.startsWith('instrumental') || s.startsWith('break')) return 'break1';
    return s;
}

// classify the words of a line: level 0 (connective) .. 3 (HUGE), role (font), ink, upper
function styleLine(L, r, styleOverrides) {
    const toks = L.words.map((w) => norm(w.w));
    const sec = L.sec;
    const lex = Object.assign({}, CAMP_LEX.any, CAMP_LEX[sec] || {});
    if (toks.includes('twenty')) lex.million = 'safety';          // the $20,000,000 is the doomers' money: red print, not chrome
    const out = L.words.map(() => ({}));
    // HUGE phrases
    for (let i = 0; i < toks.length; i++) {
        for (const H of HUGE) {
            if (H.w.every((w, k) => toks[i + k] === w || toks[i + k] === w + 's')) {
                for (let k = 0; k < H.w.length; k++) Object.assign(out[i + k], { level: 3, role: H.role, ink: H.ink, huge: H, hk: k });
            }
        }
    }
    // FUTURIST PRINT by default: mixed faces (Didone, slab, grotesk) in flat ink on slips; neon only as thin tubes
    const roles1 = ['grotesk', 'serif', 'wide', 'slab', 'roman'];
    const roles2 = ['wide', 'slab', 'serif', 'grotesk', 'display'];
    let lastRole = '';
    const chorus = sec.startsWith('chorus') || sec === 'final';
    const tube = (o, p, cols = [NEON.cyan, NEON.magenta]) => {
        if (r() < p) o.accent = { color: pick(r, cols), mode: SLIP_KINDS.has(inkSpec(o.ink).kind) ? pick(r, ['under', 'frame', 'under']) : pick(r, ['outline', 'under']) };
    };
    for (let i = 0; i < toks.length; i++) {
        const o = out[i], t = toks[i];
        if (o.level === 3) { o.upper = true; continue; }
        const camp = lex[t];
        const strong = !!camp || FUTURIST.has(t) || SINGER.has(t) || (PAPER.has(t) && sec === 'bridge') || t.length >= 8;
        o.level = CONNECT.has(t) ? 0 : strong ? 2 : 1;
        if (o.level === 0) { o.role = r() < 0.75 ? 'italic' : 'monoR'; o.ink = 'soft'; o.upper = false; continue; }
        let role = o.level === 2 ? pick(r, roles2) : pick(r, roles1);
        if (role === lastRole) role = (o.level === 2 ? roles2 : roles1)[((o.level === 2 ? roles2 : roles1).indexOf(role) + 1) % 4];
        lastRole = role;
        o.role = role;
        o.upper = o.level === 2 ? role !== 'serif' && role !== 'roman' : r() < 0.4;
        if (camp === 'state') { o.ink = 'goldPrint'; o.role = r() < 0.7 ? 'serif' : 'roman'; o.upper = true; }
        else if (camp === 'money') { o.ink = 'chromeG'; o.role = 'wide'; o.upper = true; }         // chrome: the money/race camp only
        else if (camp === 'safety') { o.ink = 'safetyPrint'; o.role = pick(r, ['slab', 'serif']); tube(o, 0.45, [CAMPS.safety]); }
        else if (camp === 'microsoft') { o.ink = r() < 0.55 ? 'warning' : 'led'; o.role = o.ink === 'warning' ? 'mono' : 'wide'; o.upper = true; if (o.ink === 'led') o.ink = 'led:' + CAMPS.microsoft; }
        else if (camp === 'news') { o.ink = r() < 0.5 ? 'spray' : 'led:' + CAMPS.news; o.role = o.ink === 'spray' ? 'spray' : 'wide'; o.upper = o.ink !== 'spray'; }
        else if (FUTURIST.has(t)) { o.ink = pick(r, ['printRed', 'printInv', 'print']); o.role = pick(r, ['slab', 'grotesk', 'serif']); o.upper = true; }
        else if (sec === 'bridge' && (PAPER.has(t) || r() < 0.35)) { o.ink = pick(r, ['print', 'print', 'printRed', 'printInv', 'printBlack']); o.role = pick(r, ['serif', 'slab', 'grotesk', 'roman']); o.upper = o.role !== 'roman' && o.role !== 'serif' ? true : r() < 0.5; }
        else if (SINGER.has(t)) { o.ink = chorus || r() < 0.5 ? 'bare' : 'printBlack'; o.role = pick(r, ['grotesk', 'wide', 'serif']); o.upper = true; tube(o, chorus ? 0.8 : 0.5); }
        else if (o.level === 2) { o.ink = pick(r, ['print', 'print', 'printRed', 'printInv', 'printBlack', 'bare', 'stencilSlip']); tube(o, 0.22); if (o.ink === 'stencilSlip') { o.role = 'stencil'; o.upper = true; } }
        else { o.ink = pick(r, ['print', 'printRed', 'bare', 'bare', 'printBlack', 'soft']); tube(o, 0.12); }
    }
    const ov = styleOverrides?.words || {};
    L.words.forEach((w, i) => { const k = toks[i]; if (ov[k]) Object.assign(out[i], ov[k]); });
    return out;
}

function makeTextItem(text, role, inkName, px, extra = {}) {
    let color = null, name = inkName;
    if (typeof inkName === 'string' && inkName.startsWith('neon:')) { name = 'neon'; color = inkName.slice(5); }
    if (typeof inkName === 'string' && inkName.startsWith('led:')) { name = 'led'; color = inkName.slice(4); }
    if (name === 'led') { role = 'led'; px *= 0.6; }
    const it = Object.assign({ type: 'text', text, role, px, inkSpec: inkSpec(name, color), inkName }, extra);
    return measureText(it);
}

// ───────────────────────────────────────── line layout ─────────────────────────────────────────
// Sizes are in FRAME HEIGHTS (FH): 1 = the frame's height. x spans ±aspect/2. Layout positions are the centres of
// the TEXT boxes; rows are aligned on their baselines.
const SIZE = [0.05, 0.072, 0.1, 0.27];

function rotPt(x, y, a) { const c = Math.cos(a), s = Math.sin(a); return [x * c - y * s, x * s + y * c]; }

// every placed sprite: { cell, x, y (FH, centre of the TEXT box), rot (rad), sc } -> sprite centre / size
function spriteOf(p, PX) {
    const c = p.cell;
    const bx = (c.ox + (c.box ? (c.box.l + c.box.r) * 0.5 : 0)), by = (c.oy + (c.box ? (c.box.t + c.box.b) * 0.5 : 0));
    const dx = (c.cw * 0.5 - (c.box ? bx : c.cw * 0.5)) / PX, dy = -(c.ch * 0.5 - (c.box ? by : c.ch * 0.5)) / PX;
    const [ox, oy] = rotPt(dx * p.sc, dy * p.sc, p.rot);
    return { x: p.x + ox, y: p.y + oy, w: c.cw / PX, h: c.ch / PX };
}

// axis-aligned extent of the (rotated) text boxes; pad inflates each box (FH)
function bboxOf(places, PX, pad = 0) {
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (const p of places) {
        if (!p.cell || p.noFit) continue;
        const c = p.cell, w = (c.bw || c.cw) / PX * p.sc * 0.5 + pad, h = (c.bh || c.ch) / PX * p.sc * 0.5 + pad;
        for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
            const [ex, ey] = rotPt(sx * w, sy * h, p.rot);
            x0 = Math.min(x0, p.x + ex); x1 = Math.max(x1, p.x + ex); y0 = Math.min(y0, p.y + ey); y1 = Math.max(y1, p.y + ey);
        }
    }
    return { x0, y0, x1, y1, w: x1 - x0, h: y1 - y0, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
}

function displayWord(w, st, keepPunct) {
    let s = String(w).replace(/[’]/g, "'");
    if (!keepPunct) s = s.replace(/[,.:;!—–"“”]/g, '').replace(/^-+|-+$/g, '');
    if (st.upper) s = s.toUpperCase();
    else if (st.level === 0) s = s.toLowerCase();
    return s;
}

const spaceCache = new Map();
function spaceW(role, px) {
    const k = role + '|' + Math.round(px);
    if (!spaceCache.has(k)) { const g = sctx(); g.font = fontStr(role, px); g.letterSpacing = '0px'; spaceCache.set(k, fin(g.measureText(' ').width, px * 0.25)); }
    return spaceCache.get(k);
}
// how far a cell's ink reaches past its text box (key strokes, slips), FH
const reachOf = (c, PX) => ((c.inkSpec?.keyW || 0) * c.px + (c.margin?.y || 0) + (SLIP_KINDS.has(c.inkSpec?.kind) ? c.px * 0.07 : 0)) / PX;
// the text-box centre for a word whose baseline is at yb (FH, up)
const onBaseline = (c, yb, PX) => yb - (c.box.t + c.box.b) / (2 * PX);

// The layout templates (all keep READING ORDER: rows read left to right, top to bottom):
//   rows   1–3 rows on a tilted baseline, rows staggered like a staircase (Depero; ZTT's inner pages). A HUGE
//          phrase takes a row of its own: the words before it sit above-left, the words after it below-right
//          (the 'crash' look); UNKNOWN FORCE lands on a light wedge and its letters invert inside it (Depero's
//          FVTVRISTA cover)
//   stair  each word one step down-right, growing toward the end (Marinetti, "SI NO SI NO SÌ", 1932)
//   band   the words on cut paper slips along a rising trajectory band (Zang Tumb Tuuum, 1915 collage)
//   calm   level, small, lowercase, centred low ("could you turn it down?")
function layoutLine(L, ctx) {
    const { PX, aspect, r } = ctx;
    const st = L.style;
    const n = L.words.length;
    const sec = L.sec;
    const huge = st.some((s) => s.level === 3);
    let tpl = L.template;
    if (!tpl) {
        if (L.calm) tpl = 'calm';
        else if (huge) tpl = 'rows';
        else if (sec === 'bridge') tpl = n <= 6 ? pick(r, ['band', 'stair', 'band']) : pick(r, ['band', 'rows']);
        else if (n <= 5) tpl = pick(r, ['stair', 'rows', 'band', 'stair']);
        else tpl = pick(r, ['rows', 'rows', 'band', 'stair']);
        if (tpl === 'stair' && n > 6) tpl = 'rows';
    }
    L.tpl = tpl;
    const items = [];
    const sizeOf = (s, k = 1) => SIZE[s.level] * k * (L.sizeScale || 1);
    const word = (i, k = 1, inkOver = null, extra = {}) => {
        const s = st[i];
        const px = sizeOf(s, k) * PX;
        const text = displayWord(L.words[i].w, s, L.calm);
        return makeTextItem(text, s.role, inkOver || s.ink, px, Object.assign({ key: `w${i}:${text}:${Math.round(px)}`, tubePad: !!s.accent }, extra));
    };
    const gapOf = (c) => spaceW(c.role, c.px) * 1.05 / PX;
    const side = (c) => ((c.margin?.x || 0) + (c.margin?.warnLeft || 0) * 0.5) / PX;          // a slip's own margin

    if (tpl === 'calm') {
        const px = 0.046 * PX * (L.sizeScale || 1);
        const cells = L.words.map((w, i) => makeTextItem(String(w.w).replace(/[’]/g, "'").toLowerCase(), 'monoR', 'calm', px, { key: `c${i}` }));
        const gap = spaceW('monoR', px) / PX;
        let x = 0;
        cells.forEach((c, i) => { items.push({ cell: c, x: x + c.bw / PX / 2 + c.box.l / PX, y: 0, rot: 0, sc: 1, wi: i }); x += (c.box.r) / PX + gap; });
        const W = x - gap;
        const yb = L.calmY ?? -0.36;
        for (const p of items) { p.x -= W / 2; p.y = onBaseline(p.cell, yb, PX); }
        return { items, tpl, theta: 0, fixed: true };
    }

    if (tpl === 'stair') {
        let x = 0, yb = 0, prev = null;
        for (let i = 0; i < n; i++) {
            const grow = n > 1 ? 0.8 + 0.6 * (i / (n - 1)) : 1;
            const c = word(i, grow);
            const w = c.bw / PX, h = c.bh / PX;
            if (i > 0) { x += w * 0.5 + Math.max(0.015, side(prev) + side(c) + 0.012); yb -= h * 0.62 + 0.014; }
            prev = c;
            items.push({ cell: c, x, y: onBaseline(c, yb, PX), rot: 0, sc: 1, wi: i });
            x += w * 0.5;
        }
        return { items, tpl, theta: 0 };
    }

    // rows (and band): flow words into rows on a tilted baseline; a HUGE phrase gets a row of its own
    const theta = (L.theta != null ? L.theta : tpl === 'band' ? pick(r, [7, 10, 13, 16]) : huge ? pick(r, [-8, -5, 5, 8, 11]) : pick(r, [-12, -8, -4, 0, 5, 9, 12])) * D2R;
    const stagger = tpl === 'band' ? 0.05 : pick(r, [0, 0.07, 0.12, -0.07]);
    const maxRow = Math.min(aspect * 0.86 / Math.cos(theta), 1.4);
    const cells = L.words.map((w, i) => {
        if (st[i].level === 3) return word(i, 1);
        const keep = ['warning', 'chromeG', 'gold', 'spray'].includes(st[i].ink) || String(st[i].ink).startsWith('led:') || String(st[i].ink).startsWith('paper');
        const inkOver = tpl === 'band' && st[i].level > 0 && !keep ?
            (r() < 0.7 ? 'paper' : 'paperRed') : null;
        if (inkOver && (st[i].role === 'mono' || st[i].role === 'spray')) st[i].role = 'grotesk';
        return word(i, tpl === 'band' && st[i].level === 0 ? 1.15 : 1, inkOver);
    });
    // segment: runs of HUGE words (one phrase) vs small words
    const rows = [];
    let cur = null;
    const flush = () => { if (cur && cur.ix.length) rows.push(cur); cur = null; };
    for (let i = 0; i < n; i++) {
        if (st[i].level === 3) {
            flush();
            const H = st[i].huge;
            const ph = [i];
            while (i + 1 < n && st[i + 1].level === 3 && st[i + 1].huge === H && st[i + 1].hk > 0) ph.push(++i);
            // fit the phrase: one row when it fits comfortably, else stacked (DEPERO / FVTVRISTA)
            let wsum = ph.reduce((a, j) => a + cells[j].bw / PX, 0) + (ph.length - 1) * gapOf(cells[ph[0]]);
            const hmax = Math.max(...ph.map((j) => cells[j].bh / PX));
            const stack = ph.length > 1 && !!H.stack && wsum > aspect * 0.62;
            if (!stack) {
                const k = Math.min(1, maxRow * 0.98 / wsum, 0.36 / hmax);
                if (k < 0.999) ph.forEach((j) => { cells[j] = word(j, k); });
                rows.push({ ix: ph, huge: true, H });
            } else {
                ph.forEach((j) => {
                    const k = Math.min(1, maxRow * 0.95 / (cells[j].bw / PX), 0.3 / (cells[j].bh / PX));
                    if (k < 0.999) cells[j] = word(j, k);
                    rows.push({ ix: [j], huge: true, H, stackRow: true });
                });
            }
            continue;
        }
        const c = cells[i], w = c.bw / PX;
        if (!cur) cur = { ix: [], w: 0 };
        if (cur.ix.length && cur.w + w > maxRow * (huge ? 0.7 : 1)) { flush(); cur = { ix: [], w: 0 }; }
        cur.ix.push(i); cur.w += w + gapOf(c);
    }
    flush();
    // stack the rows on their baselines
    let y = 0;
    const firstHuge = rows.findIndex((rw) => rw.huge), lastHuge = rows.length - 1 - [...rows].reverse().findIndex((rw) => rw.huge);
    let hugeL = 0, hugeR = 0, stairX = 0;
    rows.forEach((rw, ri) => {
        const cs = rw.ix.map((i) => cells[i]);
        const asc = Math.max(...cs.map((c) => -c.box.t)) / PX, desc = Math.max(...cs.map((c) => c.box.b)) / PX;
        const prev = rows[ri - 1];
        const reach = !prev ? 0 : Math.max(...[...cs, ...prev.ix.map((i) => cells[i])].map((c) => reachOf(c, PX)));
        let lead = !prev ? 0 : (rw.huge || prev.huge) ? 0.022 + reach * 0.9 : 0.012 + reach * 0.75;
        if (prev && rw.H?.post && !prev.H?.post) lead += 0.125;          // clear the post card's header
        if (prev && prev.H?.post && !rw.H?.post) lead += 0.095;          // and its footer
        if (ri > 0) y -= asc + lead;
        rw.yb = y; rw.asc = asc; rw.desc = desc;
        y -= desc;
        // x: words left to right from 0
        let x = 0;
        rw.xs = cs.map((c, k) => {
            const x0 = x, nx = cs[k + 1];
            x += c.bw / PX + (nx ? Math.max(gapOf(c), (side(c) + side(nx)) * 0.85 + 0.006) : 0);
            return x0;
        });
        rw.width = x;
        if (rw.huge && rw.stackRow) { rw.x0 = stairX; stairX += rw.H.post ? 0 : 0.2; }      // a post's lines stay flush left
        else rw.x0 = rw.huge ? 0 : ri * stagger;
    });
    if (firstHuge >= 0) {
        const hr = rows.filter((rw) => rw.huge);
        hugeL = Math.min(...hr.map((rw) => rw.x0)); hugeR = Math.max(...hr.map((rw) => rw.x0 + rw.width));
        rows.forEach((rw, ri) => {
            if (rw.huge) return;
            if (ri < firstHuge) rw.x0 = hugeL + 0.03;                          // before: above-left
            else if (ri > lastHuge) rw.x0 = hugeR - rw.width - 0.03;            // after: below-right
            else rw.x0 = (hugeL + hugeR) / 2 - rw.width / 2;                  // between two HUGE phrases: centred
        });
    }
    rows.forEach((rw) => {
        rw.ix.forEach((i, k) => {
            const c = cells[i], h = c.bh / PX;
            const small = st[i].level <= 1;
            const jit = rw.huge ? 0 : (small ? (r() - 0.5) * 0.22 * h : (r() - 0.5) * 0.1 * h);
            const rot = rw.huge ? 0 : (st[i].level === 0 ? (r() - 0.5) * 4 : (r() - 0.5) * (tpl === 'band' ? 8 : 9)) * D2R;
            items.push({ cell: c, x: rw.x0 + rw.xs[k] + c.bw / PX / 2, y: onBaseline(c, rw.yb + jit, PX), rot, sc: 1, wi: i, huge: rw.huge, H: rw.H });
        });
    });
    for (const p of items) { const [a, b] = rotPt(p.x, p.y, theta); p.x = a; p.y = b; p.rot += theta; }
    // Depero's wedge through the UNKNOWN FORCE row
    const wedgeRow = rows.find((rw) => rw.huge && rw.H.wedge);
    if (wedgeRow && L.wedge !== false) {
        const hb = bboxOf(items.filter((p) => p.huge && p.H === wedgeRow.H), PX);
        L.wedgeTri = [[hb.x0 - 0.1, hb.y0 + hb.h * 0.15], [hb.x1 + 0.16, hb.cy + hb.h * 0.12], [hb.x0 + hb.w * 0.3, hb.y1 + 0.06]];
    }
    if (tpl === 'band') L.band = true;
    return { items, tpl, theta };
}

// fit the block into the frame (scale down if needed) and place it at an anchor that spares the face
function placeBlock(lay, L, ctx) {
    const { PX, aspect, spare } = ctx;
    if (lay.fixed) return lay.items;
    const items = lay.items;
    let bb = bboxOf(items, PX);
    // with the camps' guesses in the four corners, the sung line keeps to the middle band (|y| <= 0.26)
    const band = L.pre && (L.pre.layout || 'rim') === 'rim';
    const safeW = aspect - 0.12, safeH = band ? 0.52 : 1 - 0.14;
    const k = Math.min(1, safeW / Math.max(bb.w, 1e-3), safeH / Math.max(bb.h, 1e-3));
    for (const p of items) { p.x *= k; p.y *= k; p.sc *= k; }
    if (L.wedgeTri) L.wedgeTri = L.wedgeTri.map(([a, b]) => [a * k, b * k]);
    bb = bboxOf(items, PX);
    const mx = aspect / 2 - 0.05, my = band ? 0.26 : 0.5 - 0.06;
    const clampShift = (ax, ay) => {
        let dx = ax - bb.cx, dy = ay - bb.cy;
        dx += Math.max(0, -mx - (bb.x0 + dx)) - Math.max(0, (bb.x1 + dx) - mx);
        dy += Math.max(0, -my - (bb.y0 + dy)) - Math.max(0, (bb.y1 + dy) - my);
        return [dx, dy];
    };
    // overlap of the shifted block with the spared face (a circle), as a fraction of the circle's box
    const faceHit = ([dx, dy]) => {
        if (!spare || !spare.r) return 0;
        const ox = Math.max(0, Math.min(bb.x1 + dx, spare.x + spare.r) - Math.max(bb.x0 + dx, spare.x - spare.r));
        const oy = Math.max(0, Math.min(bb.y1 + dy, spare.y + spare.r) - Math.max(bb.y0 + dy, spare.y - spare.r));
        return (ox * oy) / (4 * spare.r * spare.r);
    };
    let shift;
    if (L.anchor) shift = clampShift(L.anchor[0], L.anchor[1]);
    else {
        const wide = bb.w > aspect * 0.6;
        const C = band ? [[0.0, -0.01]] : wide ? [[0.0, -0.2], [0.0, 0.26], [0.0, -0.06]]
            : [[-0.15, -0.21], [0.15, -0.23], [-0.18, 0.25], [0.18, 0.22], [0.0, -0.3], [-0.2, 0.0], [0.2, 0.0]];
        const start = (L.slot ?? L.idx) % C.length;
        let best = null;
        for (let j = 0; j < C.length; j++) {
            const [cx, cy] = C[(start + j) % C.length];
            const s = clampShift(cx * aspect, cy);
            const hit = faceHit(s);
            if (!best || hit < best.hit - 1e-6) best = { s, hit };
            if (hit < 0.12) break;
        }
        shift = best.s;
    }
    for (const p of items) { p.x += shift[0]; p.y += shift[1]; }
    if (L.wedgeTri) L.wedgeTri = L.wedgeTri.map(([a, b]) => [a + shift[0], b + shift[1]]);
    return items;
}

// the calm pose of every word (hush -> 1): level, small, one or two centred rows low in frame, on baselines
function calmPoses(items, L, ctx) {
    const { PX, aspect } = ctx;
    const card = items.find((p) => p.postCard);
    if (card) {
        // black ink needs its card: the post shrinks and levels as one piece instead of joining the calm rows
        const group = [card, ...items.filter((p) => p.wi != null && p.H?.post)];
        const k = Math.min(0.62, (aspect * 0.34) / ((card.cell.cw / PX) * card.sc), 0.36 / ((card.cell.ch / PX) * card.sc));
        const cwF = (card.cell.cw / PX) * card.sc * k;
        const tx = -aspect / 2 + 0.07 + cwF / 2, ty = 0.04;
        for (const m of group) {
            const [lx, ly] = rotPt(m.x - card.x, m.y - card.y, -card.rot);
            m.calm = { x: tx + lx * k, y: ty + ly * k, rot: m.rot - card.rot, sc: m.sc * k };
        }
    }
    const words = items.filter((p) => p.wi != null && !(card && p.H?.post)).sort((a, b) => a.wi - b.wi);
    const scaleTo = (p) => Math.min(1, 0.046 / Math.max(1e-3, (p.cell.px / PX) * p.sc));
    const widthOf = (p) => ((p.cell.bw / PX) + 2 * reachOf(p.cell, PX)) * p.sc * scaleTo(p);
    const gap = 0.02;
    const total = words.reduce((a, p) => a + widthOf(p) + gap, 0);
    const rows = total > 1.25 ? 2 : 1;
    const per = total / rows;
    let x = 0, row = 0;
    const placed = [];
    for (const p of words) {
        const w = widthOf(p);
        if (x + w > per + 0.05 && row < rows - 1 && x > 0) { row++; x = 0; }
        placed.push({ p, x: x + w / 2, row, k: scaleTo(p) });
        x += w + gap;
    }
    const widths = [];
    for (const q of placed) widths[q.row] = Math.max(widths[q.row] || 0, q.x + widthOf(q.p) / 2);
    for (const q of placed) {
        const c = q.p.cell, sc = q.p.sc * q.k;
        const yb = -0.34 - q.row * 0.07;
        q.p.calm = { x: q.x - widths[q.row] / 2, y: yb - (c.box.t + c.box.b) / (2 * PX) * sc, rot: 0, sc };
    }
    for (const p of items) if (!p.calm) p.calm = { x: p.x, y: p.y, rot: p.rot, sc: p.sc * 0.6, fade: true };
}

// ───────────────────────────────────────── decor ─────────────────────────────────────────
const kw0 = (k) => k;
function decorFor(L, items, ctx, extraBoxes = []) {
    const { PX, aspect, r, spare } = ctx;
    const out = [];
    const bb = bboxOf(items, PX);
    const sec = L.sec.startsWith('chorus') ? 'chorus' : L.sec;
    const word = (i) => items.find((p) => p.wi === i);
    const toks = L.words.map((w) => norm(w.w));
    const boxes = items.filter((p) => p.wi != null).map((p) => bboxOf([p], PX, 0.012 + reachOf(p.cell, PX) * p.sc * 0.5));
    boxes.push(...extraBoxes);
    const faceBox = spare && spare.r ? { x0: spare.x - spare.r * 0.8, x1: spare.x + spare.r * 0.8, y0: spare.y - spare.r * 0.8, y1: spare.y + spare.r * 0.8 } : null;
    const free = (x, y, w, h) => {
        if (Math.abs(x) + w / 2 > aspect / 2 - 0.03 || Math.abs(y) + h / 2 > 0.47) return false;
        if (faceBox && x + w / 2 > faceBox.x0 && x - w / 2 < faceBox.x1 && y + h / 2 > faceBox.y0 && y - h / 2 < faceBox.y1) return false;
        return !boxes.some((o) => x + w / 2 > o.x0 && x - w / 2 < o.x1 && y + h / 2 > o.y0 && y - h / 2 < o.y1);
    };
    const place = (cell, near, rot, t, extra = {}) => {
        const w0 = (cell.bw || cell.cw) / PX, h0 = (cell.bh || cell.ch) / PX;
        const ca = Math.abs(Math.cos(rot)), sa = Math.abs(Math.sin(rot));
        const w = w0 * ca + h0 * sa + 0.01, h = w0 * sa + h0 * ca + 0.01;
        const cands = [];
        for (const d of [1.0, 1.35, 1.8]) {
            for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, -1], [1, -1], [-1, 1]]) {
                cands.push([near.x + dx * (near.w / 2 + w / 2 + 0.02) * d, near.y + dy * (near.h / 2 + h / 2 + 0.015) * d]);
            }
        }
        for (const [x, y] of cands) {
            if (free(x, y, w, h)) {
                boxes.push({ x0: x - w / 2 - 0.01, x1: x + w / 2 + 0.01, y0: y - h / 2 - 0.01, y1: y + h / 2 + 0.01 });
                out.push(Object.assign({ cell, x, y, rot, sc: 1, t, decor: true }, extra));
                return true;
            }
        }
        return false;
    };
    const nearOf = (p) => ({ x: p.x, y: p.y, w: (p.cell.bw / PX) * p.sc, h: (p.cell.bh / PX) * p.sc });
    // signs that mean something on this line
    for (const s of LINE_SIGNS[lineKey(L.text)] || []) {
        const wi = toks.indexOf(s.at);
        if (wi < 0) continue;
        const p = word(wi);
        if (!p) continue;
        const t = L.words[wi].s;
        if (s.sign) {
            const sz = Math.max(0.07, (p.cell.bh / PX) * p.sc * 0.9) * PX;
            const cell = { type: 'sign', sign: s.sign, color: s.sign === '−' ? NEON.magenta : NEON.cyan, cw: Math.ceil(sz), ch: Math.ceil(sz), key: 'sign' + s.sign + wi };
            place(cell, nearOf(p), 0, t, { sign: true });
        } else if (s.aside) {
            // CLANKER: sprayed huge in free space (it is the slur; it is not sung), revealed like a spray pass
            const cell = makeTextItem(s.text, 'stencil', 'spray', 0.2 * PX, { key: 'aside' + s.text });
            const w = cell.bw / PX, h = cell.bh / PX;
            let k = Math.min(1, (aspect * 0.7) / w);
            let spot = null;
            const hits = (o) => [...boxes, ...(faceBox ? [faceBox] : [])].some((b) => o.x1 > b.x0 && o.x0 < b.x1 && o.y1 > b.y0 && o.y0 < b.y1);
            // a free spot for it, shrinking it before it may cover the face or the line
            for (const kk of [1, 0.75, 0.55, 0.4]) {
                for (const [cx, cy] of [[0.0, -0.3], [0.0, 0.32], [0.18, -0.3], [-0.18, 0.32], [-0.18, -0.3], [0.18, 0.32], [0.24, 0.0], [-0.24, 0.0]]) {
                    const kw = k * kw0(kk), x = cx * aspect, y = cy;
                    const o = { x0: x - w * kw / 2, x1: x + w * kw / 2, y0: y - h * kw / 2, y1: y + h * kw / 2 };
                    if (Math.abs(x) + w * kw / 2 <= aspect / 2 - 0.03 && Math.abs(y) + h * kw / 2 <= 0.48 && !hits(o)) { spot = [x, y]; k = kw; break; }
                }
                if (spot) break;
            }
            if (!spot) { spot = [0, bb.cy > 0 ? -0.33 : 0.33]; k *= 0.5; }
            out.push({ cell, x: spot[0], y: spot[1], rot: -6 * D2R, sc: k, t: t + 0.08, decor: true, behind: true, alpha: 0.9, wipe: 0.5, aside: true });
        } else {
            const cell = makeTextItem(s.text, 'mono', 'neon:' + (CAMPS[s.camp] || NEON.cyan), 0.05 * PX, { key: 'num' + s.text });
            place(cell, nearOf(p), (r() - 0.5) * 8 * D2R, t + 0.1);
        }
    }
    // onomatopoeia: 0..2 per line, more in the choruses
    const pool = ONO[sec] || [];
    let nOno = pool.length ? (sec === 'chorus' || sec === 'verse4' ? 2 : r() < 0.6 ? 1 : 0) : 0;
    if (L.calm || L.decor === false) nOno = 0;
    const used = new Set();
    for (let k = 0; k < nOno; k++) {
        let txt = pick(r, pool);
        if (used.has(txt)) txt = pool[(pool.indexOf(txt) + 1) % pool.length];
        used.add(txt);
        const col = pick(r, [NEON.cyan, NEON.magenta, NEON.sunset]);
        const role = pick(r, ['slab', 'grotesk', 'italic', 'display']);
        const spacing = /^[A-Z]{4,}$/.test(txt) && r() < 0.5 ? 0.22 : 0;
        const cell = makeTextItem(txt, role, 'tube', (0.05 + r() * 0.03) * PX, { key: 'ono' + k + txt, spacing });
        cell.inkSpec = inkSpec('tube', col);
        measureText(cell);
        const wi = Math.min(L.words.length - 1, Math.floor(r() * L.words.length));
        const p = word(wi) || items[0];
        const near = k % 2 ? { x: bb.cx, y: bb.cy, w: bb.w, h: bb.h } : nearOf(p);
        place(cell, near, (r() - 0.5) * 24 * D2R, L.words[wi].s + 0.05, { ono: k });
    }
    // the trajectory band behind a 'band' line
    if (L.band) {
        const w = bb.w + 0.25, h = Math.max(0.12, Math.min(0.3, bb.h * 0.9));
        const cell = { type: 'band', color: pick(r, [NEON.magenta, NEON.cyan, NEON.sunset]), cw: Math.ceil(w * PX * 0.6), ch: Math.ceil(h * PX * 0.6), key: 'band' };
        const th = items.find((p) => p.wi === 0)?.rot ?? 0;
        out.push({ cell, x: bb.cx + 0.06, y: bb.cy, rot: th, sc: 1 / 0.6, t: L.words[0].s - 0.05, decor: true, behind: true, alpha: 0.95 });
    }
    // Depero's wedge behind the huge phrase: deep Futurist red, painted, its edges torn; the words' letters invert
    // to black inside it (an overlay sprite per word that shares the wedge's paint, so the two match exactly)
    if (L.wedgeTri) {
        const P = wedgePaint(r, L.wedgeTri);
        const xs = P.poly.map((q) => q[0]), ys = P.poly.map((q) => q[1]);
        const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
        const S = 0.5;                       // flat paint: half resolution is plenty
        const cw = Math.ceil((x1 - x0) * PX * S) + 16, ch = Math.ceil((y1 - y0) * PX * S) + 16;
        const paint = mapPaint(P, ([a, b]) => [(a - x0) * PX * S + 8, (y1 - b) * PX * S + 8], PX * S);
        const cell = { type: 'wedge2', paint, cw, ch, key: 'wedge' };
        const hugeIdx = L.style.map((st, i) => (st.level === 3 && st.huge?.wedge ? i : -1)).filter((i) => i >= 0);
        const t0 = Math.min(...hugeIdx.map((i) => L.words[i].s));
        out.push({ cell, x: (x0 + x1) / 2, y: (y0 + y1) / 2, rot: 0, sc: 1 / S, t: t0 - 0.02, decor: true, behind: true, alpha: 1, wedge: true, wipe: 0.16 });
        for (const p of items) {
            if (!p.huge || !p.H?.wedge) continue;
            const c = p.cell;
            const bxc = (c.box.l + c.box.r) / 2, byc = (c.box.t + c.box.b) / 2;
            const map = ([a, b]) => { const [lx, ly] = rotPt(a - p.x, b - p.y, -p.rot); return [lx / p.sc * PX + bxc, -ly / p.sc * PX + byc]; };
            const ov = Object.assign({}, c, { key: c.key + ':wedge', baseKey: c.key, inkSpec: { kind: 'wedgeInk' }, wedgeLocal: mapPaint(P, map, PX / p.sc) });
            out.push({ cell: ov, follow: p, x: p.x, y: p.y, rot: p.rot, sc: p.sc, decor: true, behind: false });
        }
    }
    // CAPITAL LETTERS: a post in caps, as if screenshotted and torn out: one white card behind the phrase
    const postWords = items.filter((p) => p.huge && p.H?.post);
    if (postWords.length) {
        const th = postWords[0].rot;
        let qx0 = 1e9, qx1 = -1e9, qy0 = 1e9, qy1 = -1e9;
        for (const p of postWords) {
            const [cx, cy] = rotPt(p.x, p.y, -th), w = (p.cell.bw / PX) * p.sc / 2, h = (p.cell.bh / PX) * p.sc / 2;
            qx0 = Math.min(qx0, cx - w); qx1 = Math.max(qx1, cx + w); qy0 = Math.min(qy0, cy - h); qy1 = Math.max(qy1, cy + h);
        }
        const HEAD = 0.115, FOOT = 0.085, SIDE = 0.055;
        const W = qx1 - qx0 + 2 * SIDE, Hh = qy1 - qy0 + HEAD + FOOT;
        const [wx, wy] = rotPt((qx0 + qx1) / 2, (qy0 - FOOT + qy1 + HEAD) / 2, th);
        const S = 0.75, pad = 14;
        const cell = { type: 'post', cw: Math.ceil(W * PX * S) + 2 * pad, ch: Math.ceil(Hh * PX * S) + 2 * pad, key: 'post', pad, S, PX,
            head: HEAD, foot: FOOT };
        const t0 = Math.min(...postWords.map((p) => L.words[p.wi].s));
        out.push({ cell, x: wx, y: wy, rot: th, sc: 1 / S, t: t0 - 0.04, decor: true, behind: true, alpha: 1, postCard: true });
    }
    // thin neon-tube accents: a follower sprite per accented word (it rides the word, and flickers like a tube)
    for (const p of items) {
        const acc = p.wi != null ? L.style[p.wi]?.accent : null;
        if (!acc) continue;
        const c = p.cell;
        const ov = Object.assign({}, c, { key: c.key + ':tube:' + acc.mode, baseKey: c.key,
            inkSpec: { kind: 'tubeAccent', color: acc.color, mode: acc.mode, base: c.inkSpec } });
        out.push({ cell: ov, follow: p, x: p.x, y: p.y, rot: p.rot, sc: p.sc, decor: true, behind: acc.mode === 'under', flicker: hashStr(c.key) });
    }
    return out;
}

// ───────────────────────────────────────── timing ─────────────────────────────────────────
function normalizeTiming(timing) {
    const arr = Array.isArray(timing) ? timing : (timing?.lines || timing?.captions || []);
    return arr.map((l, idx) => {
        const words = (l.words || []).map((w) => ({ w: String(w.w ?? w.word ?? w.text ?? '').trim(), s: +(w.s ?? w.start ?? w.t0), e: +(w.e ?? w.end ?? w.t1) }))
            .filter((w) => w.w && Number.isFinite(w.s));
        const text = String(l.text ?? words.map((w) => w.w).join(' '));
        const start = +(l.start ?? l.t0 ?? words[0]?.s), end = +(l.end ?? l.t1 ?? words[words.length - 1]?.e);
        if (!words.length) {                        // a line without word times: spread its words
            const ws = text.split(/\s+/).filter(Boolean);
            const d = (end - start) / Math.max(1, ws.length);
            ws.forEach((w, i) => words.push({ w, s: start + i * d, e: start + (i + 1) * d }));
        }
        for (const w of words) if (!Number.isFinite(w.e) || w.e < w.s) w.e = w.s + 0.25;
        return { idx, text, start, end: Number.isFinite(end) ? end : words[words.length - 1].e, words, section: l.section, echo: !!l.echo };
    }).filter((l) => l.words.length && Number.isFinite(l.start)).sort((a, b) => a.start - b.start);
}

// ───────────────────────────────────────── the GPU side ─────────────────────────────────────────
const ACES_IN = [0.59719, 0.35458, 0.04823, 0.07600, 0.90834, 0.01566, 0.02840, 0.13383, 0.83777];
const ACES_OUT = [1.60475, -0.53108, -0.07367, -0.10208, 1.10813, -0.00605, -0.00327, -0.07276, 1.07602];
function inv3(m) {
    const [a, b, c, d, e, f, g, h, i] = m;
    const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
    const det = a * A + b * B + c * C;
    return [A / det, -(b * i - c * h) / det, (b * f - c * e) / det, B / det, (a * i - c * g) / det, -(a * f - c * d) / det,
        C / det, -(a * h - b * g) / det, (a * e - b * d) / det];
}

async function makeMaterialFactory(THREE) {
    const T = await import('npm:three@0.184.0/tsl');
    const { attribute, uv, vec2, vec3, float, texture, min, max, mix, dot, step, sqrt, mat3, smoothstep, toneMappingExposure } = T;
    const IN_INV = inv3(ACES_IN), OUT_INV = inv3(ACES_OUT);
    const aces = () => !globalThis._r || globalThis._r.toneMapping === THREE.ACESFilmicToneMapping;
    // the renderer's ACES, inverted (aeropittura.js uses the same math): display -> scene-referred linear
    const fromDisp = (d) => {
        if (!aces()) return d;
        const y = min(mat3(...OUT_INV).mul(d), vec3(1.0)).toVar();
        const qa = float(1.0).sub(y.mul(0.983729));
        const qb = float(0.0245786).sub(y.mul(0.4329510 * 0.983729));
        const qc = float(0.000090537).add(y.mul(0.238081)).negate();
        const x = sqrt(max(qb.mul(qb).sub(qa.mul(qc).mul(4.0)), 0.0)).sub(qb).div(qa.mul(2.0));
        return mat3(...IN_INV).mul(max(x, 0.0)).mul(0.6).div(toneMappingExposure);
    };
    return (tex) => {
        const m = new THREE.MeshBasicNodeMaterial({ transparent: true, depthTest: false, depthWrite: false, toneMapped: false, side: THREE.DoubleSide });
        // straight (un-premultiplied) colour: the engine composites the overlay as mix(scene, ov, ov.a)
        m.blending = THREE.CustomBlending;
        m.blendSrc = THREE.OneFactor; m.blendDst = THREE.OneMinusSrcAlphaFactor;
        m.blendSrcAlpha = THREE.OneFactor; m.blendDstAlpha = THREE.OneMinusSrcAlphaFactor;
        const rect = attribute('aRect', 'vec4'), par = attribute('aPar', 'vec4');
        const p = uv();
        const auv = vec2(rect.x.add(p.x.mul(rect.z)), rect.y.add(float(1.0).sub(p.y).mul(rect.w)));
        const s = texture(tex, auv);
        // solid ink lands exactly as authored (inverse ACES); glows and soft edges stay in plain display-linear,
        // or the inverse curve would blow a 10 % glow up into a bright box. Glows also fade out before the cell edge.
        const solid = smoothstep(0.55, 0.95, s.a);
        const edge = smoothstep(0.0, 0.04, p.x).mul(smoothstep(0.0, 0.04, float(1.0).sub(p.x)))
            .mul(smoothstep(0.0, 0.06, p.y)).mul(smoothstep(0.0, 0.06, float(1.0).sub(p.y)));
        const a = s.a.mul(par.x).mul(step(p.x, par.y)).mul(mix(edge, float(1.0), solid));
        const lum = dot(s.rgb, vec3(0.2126, 0.7152, 0.0722));
        const disp = min(mix(s.rgb, vec3(lum), par.w).mul(par.z), vec3(0.93));
        m.colorNode = mix(disp.mul(0.8), fromDisp(disp), solid).mul(min(a.mul(3.0), 1.0));
        m.opacityNode = a;
        return m;
    };
}

// ───────────────────────────────────────── makeParole ─────────────────────────────────────────
export async function makeParole(THREE, opts = {}) {
    await registerFonts(opts.fonts || {});
    { const g = sctx(); for (const f of Object.values(FONTS)) { g.font = `24px "${f.family}"`; g.fillText('Aa', 0, 20); } for (const k of ['voids', 'fibre', 'fibreDark', 'paint']) for (const sz of [0, 1, 2, 3]) if (k === 'voids' || sz === 0) tile(k, sz); }
    const W = globalThis.WIDTH || opts.width || 1920, H = globalThis.HEIGHT || opts.height || 1080;
    const PX = opts.px || H;                         // pixels per frame height in the atlases
    const aspect = W / H;
    const overlay = opts.overlay || (globalThis.makeOverlayLayer ? globalThis.makeOverlayLayer({ fov: opts.fov || 50 }) : null);
    const fov = overlay?.camera?.fov ?? opts.fov ?? 50;
    const F = 2 * Math.tan(fov * D2R / 2);           // frame height in overlay units at z = -1
    const SO = opts.styleOverrides || {};
    // the face to keep clear (FH, centre-origin, y up): blocks are anchored where they cover it least
    let spare = opts.spare === null ? null : Object.assign({ x: 0, y: 0.13, r: 0.19 }, opts.spare || {});   // setSpare() moves it
    const gpu = !!(overlay && THREE);
    const matFor = gpu ? await makeMaterialFactory(THREE) : null;
    let hush = 0;

    // ── lines
    const lines = normalizeTiming(opts.timing || []);
    const custom = [];
    const groups = [];                                // everything that can be on screen: { kind, t0, t1, build(), frame(t) }

    function prepLine(L, i, isCustom) {
        L.sec = secKey(L.section || sectionAt(L.start));
        L.calm = L.calm ?? (isCalmText(L.text) || L.echo);
        const o = Object.assign({}, (SO.lines || {})[i] || {}, (SO.byText || {})[lineKey(L.text)] || {});
        Object.assign(L, o);
        L.seed = (o.seed ?? hashStr(L.text) ^ Math.imul(i + 1, 0x9E3779B1)) >>> 0;
        L.slot = L.slot ?? i;
        L.custom = isCustom;
        return L;
    }
    lines.forEach((L, i) => prepLine(L, i, false));

    // exits: hold a line until just before the next (≤1.6 s after its end), never less than its read time
    function computeExits() {
        const all = [...lines, ...custom].sort((a, b) => a.start - b.start);
        for (let i = 0; i < all.length; i++) {
            const L = all[i];
            const last = L.words[L.words.length - 1];
            const minEnd = Math.max(L.end + 0.3, last.s + 0.85, L.start + (L.calm ? 1.6 : 0.9));
            const next = all.slice(i + 1).find((x) => !x.custom || !L.custom);
            const nIn = next ? next.start - 0.06 - (next.pre ? next.pre.lead : 0) : Infinity;
            L.exitAt = L.hold != null ? L.end + L.hold : (nIn >= minEnd ? clamp(nIn - 0.08, minEnd, L.end + (L.calm ? 2.6 : 1.6)) : minEnd);
            if (L.pre) L.pre.exitAt = L.pre.mode === 'roll' ? L.pre.lastStrike + L.pre.gone : Math.max(L.exitAt, L.pre.strikeAt + 0.9);
        }
    }

    // ── groups: lazily rasterized atlases with one InstancedMesh each
    const live = new Map();
    function buildGroup(G) {
        const tb = performance.now();
        const sprites = G.make();                    // [{ cell, ... }]
        const tm = performance.now();
        const cells = [];
        const seen = new Map();
        for (const s of sprites) { if (!seen.has(s.cell)) { seen.set(s.cell, cells.length); cells.push(s.cell); } }
        const atlas = rasterize(cells, G.seed);
        const tr = performance.now();
        const out = { G, sprites, atlas, cells };
        if (gpu) {
            const tex = new THREE.CanvasTexture(atlas.canvas);
            tex.colorSpace = THREE.SRGBColorSpace;
            tex.generateMipmaps = true;                 // hush shrinks the HUGE words ~6x: mips keep them clean
            tex.minFilter = THREE.LinearMipmapLinearFilter;
            tex.magFilter = THREE.LinearFilter;
            tex.needsUpdate = true;
            const geo = new THREE.PlaneGeometry(1, 1);
            geo.deleteAttribute('normal');
            const n = sprites.length;
            const rect = new Float32Array(n * 4);
            sprites.forEach((s, k) => {
                const c = s.cell;
                rect.set([c.ax / atlas.w, c.ay / atlas.h, c.cw / atlas.w, c.ch / atlas.h], k * 4);
            });
            geo.setAttribute('aRect', new THREE.InstancedBufferAttribute(rect, 4));
            const par = new THREE.InstancedBufferAttribute(new Float32Array(n * 4), 4);
            par.setUsage(THREE.DynamicDrawUsage);
            geo.setAttribute('aPar', par);
            const mesh = new THREE.InstancedMesh(geo, matFor(tex), n);
            mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            mesh.frustumCulled = false;
            mesh.renderOrder = 900 + (G.order || 0);
            mesh.name = 'parole:' + G.name;
            Object.assign(out, { tex, geo, mesh, par });
            overlay.add(mesh);
        }
        if (globalThis.PAROLE_PROFILE) console.log(`[parole-prof] ${G.name}: make ${(tm - tb).toFixed(0)} ms, raster ${(tr - tm).toFixed(0)} ms, upload ${(performance.now() - tr).toFixed(0)} ms (${atlas.w}x${atlas.h})`);
        return out;
    }
    function dropGroup(B) {
        if (!B) return;
        if (B.mesh) { B.mesh.parent?.remove(B.mesh); B.geo.dispose(); B.mesh.material.dispose(); B.tex.dispose(); }
        B.atlas = null;
    }

    // ── a lyric (or custom) line as a group
    function lineGroup(L) {
        const G = {
            name: `line${L.idx}:${L.text.slice(0, 24)}`, kind: 'line', seed: L.seed, order: 10,
            get t0() { return Math.min(L.start - 0.25, L.pre ? L.start - L.pre.lead - 0.2 : Infinity); },
            get t1() { return Math.max(L.exitAt + 0.45, L.pre ? L.pre.exitAt + 0.45 : 0); },
            make() {
                const r = rng(L.seed);
                const ctx = { PX, aspect, r, spare: L.spare || spare };
                L.style = styleLine(L, r, SO);
                L.wedgeTri = null; L.band = false;
                const lay = layoutLine(L, ctx);
                const items = placeBlock(lay, L, ctx);
                const pre = L.pre ? preSprites(L, r, items) : [];
                const decor = decorFor(L, items, ctx, pre.filter((q) => !q.strike).map((q) => bboxOf([q], PX, 0.015)));
                // draw order: what lies behind, the HUGE words, the small words on top, then the front decor
                const all = [...decor.filter((d) => d.behind), ...items.filter((p) => p.huge), ...items.filter((p) => !p.huge),
                    ...decor.filter((d) => !d.behind)];
                calmPoses(all, L, ctx);
                // hush, phase 1: the whole block shrinks, levels and settles low as ONE rigid piece (nothing inside it
                // can collide); phase 2 (x > 0.75) re-sets the words into the calm rows
                {
                    const words = items.filter((p) => p.wi != null);
                    const bb = bboxOf(words, PX);
                    const maxH = Math.max(...words.map((p) => (p.cell.bh / PX) * p.sc));
                    const calmW = words.filter((p) => p.calm && !p.calm.fade);
                    L.block = { cx: bb.cx, cy: bb.cy, hw: bb.w / 2, hh: bb.h / 2, theta: lay.theta || 0,
                        S1: clamp(0.09 / Math.max(maxH, 1e-3), 0.42, 1),
                        tx: bb.cx * 0.6, ty: calmW.length ? calmW.reduce((a, p) => a + p.calm.y, 0) / calmW.length + 0.06 : -0.28 };
                }
                // entrance throws: per line a direction (from the frame edge the block faces), per word a spin
                const dir = pick(r, [[1, 0.35], [-1, 0.3], [0.4, 1], [-0.5, -1], [1, -0.6]]);
                for (const p of all) {
                    p.t = p.t ?? (p.wi != null ? L.words[p.wi].s - 0.05 : L.start);
                    p.throw = { dx: dir[0] * (0.18 + r() * 0.12), dy: dir[1] * (0.12 + r() * 0.1), dr: (r() - 0.5) * 40 * D2R, k: p.huge ? 1.7 : 1.35 };
                    p.exitDir = [dir[0] * -0.5 + (r() - 0.5) * 0.4, -0.25 - r() * 0.3];
                    p.lineIdx = L.idx;
                }
                all.unshift(...pre);
                L.items = all;
                return all;
            },
            frame(t, B, out) {
                for (const p of B.sprites) out.push(p.pre ? preState(p, L, t) : wordState(p, L, t));
            },
        };
        return G;
    }

    // a neon tube strikes on (two stutters as it lands), then holds with the odd brief dip; hush steadies it
    function neonFlicker(t, seed, t0, hx) {
        const u = t - t0;
        if (u < 0) return 0;
        if (u < 0.3) return [0.0, 1, 0.15, 1, 0.45, 1][Math.min(5, Math.floor(u / 0.05))];
        const k = Math.floor(t * 15);
        const h = ((Math.imul((k ^ seed) >>> 0, 2654435761) >>> 0) % 1000) / 1000;
        const dip = h > 0.965 ? 0.2 : h > 0.94 ? 0.65 : 1;
        return lerp(dip, 1, clamp(hx * 1.5));
    }
    function wordState(p, L, t) {
        if (p.follow) {
            const st = wordState(p.follow, L, t);
            if (!st) return null;
            const a = p.flicker != null ? st.alpha * neonFlicker(t, p.flicker, p.follow.t, hush) : st.alpha * (1 - smooth(0, 0.5, hush));
            return Object.assign({}, st, { p, alpha: a, reveal: 1 });
        }
        const hx = L.calm ? 0 : smooth(0, 0.85, hush);              // calm rows reached at hush 0.85
        const motion = 1 - hx;
        const tIn = p.t;
        const din = p.huge ? 0.13 : p.decor ? 0.22 : 0.17;
        const k = (t - tIn) / din;
        if (k < 0) return null;
        const exitAt = L.exitAt + (p.wi != null ? p.wi * 0.018 : 0.04);
        const ke = clamp((t - exitAt) / 0.26);
        if (ke >= 1) return null;
        // hush: phase 1 (0 -> 0.75) moves the block rigidly (shrink, level, settle low, kept in frame); phase 2
        // (0.75 -> 1) re-sets each word into its calm row. A held mid value is always a clean, collision-free layout.
        let pose = { x: p.x, y: p.y, rot: p.rot, sc: p.sc };
        if (!L.calm && hush > 0 && L.block) {
            const B = L.block, u = smooth(0, 0.75, hush), v = smooth(0.75, 1, hush);
            const S = lerp(1, B.S1, u), ang = -B.theta * u;
            const mx = aspect / 2 - 0.05, my = 0.45;
            let cx = lerp(B.cx, B.tx, u), cy = lerp(B.cy, B.ty, u);
            cx = clamp(cx, -mx + B.hw * S, mx - B.hw * S); cy = clamp(cy, -my + B.hh * S, my - B.hh * S);
            if (!Number.isFinite(cx)) cx = 0;
            if (!Number.isFinite(cy)) cy = 0;
            const [rx, ry] = rotPt(p.x - B.cx, p.y - B.cy, ang);
            const rigid = { x: cx + rx * S, y: cy + ry * S, rot: p.rot + ang, sc: p.sc * S };
            pose = p.calm && v > 0 && !p.calm.fade ? {
                x: lerp(rigid.x, p.calm.x, v), y: lerp(rigid.y, p.calm.y, v), rot: lerp(rigid.rot, p.calm.rot, v),
                sc: Math.exp(lerp(Math.log(rigid.sc), Math.log(p.calm.sc), v)),
            } : rigid;
        }
        let alpha = (p.alpha ?? 1) * smooth(0, 0.35, k);
        if (p.calm?.fade) alpha *= 1 - smooth(0, 0.5, hush);        // signs, bands, wedges, asides leave first
        if (p.ono != null) alpha *= 1 - smooth(0.3 - p.ono * 0.2, 0.45 - p.ono * 0.2, hush);   // fewer onomatopoeia, then none
        const e = easeOut3(k), eb = easeOutBack(k);
        let x = pose.x, y = pose.y, rot = pose.rot, sc = pose.sc;
        if (L.calm) {                                 // calm words only rise and fade in
            y -= (1 - e) * 0.02; sc *= 1;
        } else {
            x += p.throw.dx * (1 - e) * motion; y += p.throw.dy * (1 - e) * motion;
            rot += p.throw.dr * (1 - eb) * motion;
            sc *= lerp(1, lerp(p.throw.k, 1, eb), motion);
            if (p.huge && p.H?.bow) {                 // BOW bows: after landing it tips forward and dips
                const kb = smooth(0.3, 0.8, t - tIn);
                rot -= kb * 0.38 * motion; y -= kb * 0.035 * motion;
            }
            // a slow drift while it is read: the words keep a little life
            x += (t - tIn) * 0.004 * (p.throw.dx > 0 ? 1 : -1) * motion;
        }
        if (ke > 0) {
            const q = easeIn2(ke);
            x += p.exitDir[0] * q * 0.3 * (L.calm ? 0.1 : 1); y += p.exitDir[1] * q * 0.2 * (L.calm ? 0.1 : 1);
            sc *= 1 - 0.15 * q; alpha *= 1 - ke;
        }
        const reveal = p.wipe ? 0.02 + 0.98 * easeOut3((t - tIn) / p.wipe) : 1;      // sprayed / swept on
        return { p, x, y, rot, sc, alpha, reveal, bright: 1, desat: 0 };
    }

    // ── PRE-HEARD: the camps' answers arrive first, in their colours and their typefaces; struck when she sings
    const CAMP_TYPE = { safety: ['slab', 'neon:' + CAMPS.safety], state: ['serif', 'gold'], money: ['wide', 'chromeG'],
        microsoft: ['mono', 'warning'], news: ['spray', 'spray'] };
    function preSprites(L, r, items) {
        const P = L.pre;
        const alts = P.alts;
        const sp = [];
        const n = alts.length;
        const corners = [[-1, 1], [1, 1], [-1, -1], [1, -1]];
        const layout = P.layout || 'rim';
        alts.forEach((a, k) => {
            const camp = a.camp || ['safety', 'state', 'money', 'microsoft', 'news'][k % 5];
            const [role, ink] = a.role ? [a.role, a.ink || CAMP_TYPE[camp][1]] : CAMP_TYPE[camp];
            const cell = makeTextItem(a.text, role, a.ink || ink, (P.size || (layout === 'brace' ? 0.05 : 0.064)) * PX, { key: 'pre' + k + a.text });
            const w = cell.bw / PX, h = cell.bh / PX;
            let x, y, rot, sc;
            if (layout === 'brace') {
                // a stacked list at the top left; the brace points down-right at where her words land
                sc = Math.min(1, (aspect * 0.5) / w);
                rot = -2 * D2R;
                x = -aspect / 2 + 0.07 + (w * sc) / 2; y = 0.4 - (k % 4) * 0.078;
            } else {
                // the four corners, each tilted toward the middle; the rotated box stays inside the safe frame. A fifth
                // guess takes the first one's corner as that one leaves.
                const [cx, cy] = corners[k % 4];
                rot = cx * cy * -8 * D2R + (r() - 0.5) * 2 * D2R;
                sc = Math.min(1, (aspect * 0.47) / w);
                const c = Math.cos(Math.abs(rot)), s = Math.sin(Math.abs(rot));
                const hw = (w * sc * c + h * sc * s) / 2 + reachOf(cell, PX) * sc, hh = (w * sc * s + h * sc * c) / 2 + reachOf(cell, PX) * sc;
                x = cx * (aspect / 2 - 0.045 - hw); y = cy * (0.5 - 0.055 - hh);
            }
            const tIn = P.A[k], tS = P.S[k];
            sp.push({ cell, x, y, rot, sc, pre: true, k, tIn, tS, camp, out: [Math.sign(x) || 1, Math.sign(y) || 1] });
            const sw = cell.bw * 1.08, sh = Math.max(cell.bh * 0.95, 0.04 * PX);
            const lightGround = cell.inkSpec.kind === 'warn' || cell.inkSpec.kind === 'paper' || (cell.inkSpec.kind === 'print' && hexRgb(cell.inkSpec.paper).reduce((q, v) => q + v, 0) > 400);
            const strike = { type: 'strike', cw: Math.ceil(sw), ch: Math.ceil(sh), color: P.strikeColor || (lightGround ? STRIKE_DARK : '#fff1d6'), key: 'strike' + k };
            sp.push({ cell: strike, x, y, rot, sc, pre: true, strike: true, k, tIn: tS, tS, out: [Math.sign(x) || 1, Math.sign(y) || 1] });
        });
        if (layout === 'brace' && n > 1) {
            const cell = makeTextItem('}', 'roman', 'soft', 0.12 * Math.min(n, 4) * PX, { key: 'brace' });
            const xr = Math.max(...sp.filter((s) => !s.strike).map((s) => s.x + (s.cell.bw / PX) * s.sc / 2)) + 0.06;
            const kb = Math.min(1, (0.078 * Math.min(n, 4)) / (cell.bh / PX));
            sp.push({ cell, x: xr, y: 0.4 - 0.039 * (Math.min(n, 4) - 1), rot: 0, sc: kb, pre: true, brace: true, k: 0, tIn: Math.min(...P.A), tS: P.lastStrike, out: [-1, 0] });
        }
        void items;
        return sp;
    }
    function preState(p, L, t) {
        const P = L.pre;
        const hx = smooth(0, 0.85, hush);
        if (t < p.tIn) return null;
        // when it leaves: 'roll' = right after its own strike; 'together' = with the line
        const exitAt = P.mode === 'roll' && !p.brace ? p.tS + 0.12 : P.exitAt + p.k * 0.03;
        const exitDur = P.mode === 'roll' && !p.brace ? Math.max(0.05, P.gone - 0.12) : 0.3;
        const ke = clamp((t - exitAt) / exitDur);
        if (ke >= 1) return null;
        const fly = P.fly ?? 0.2;
        const k = clamp((t - p.tIn) / (p.strike ? 0.12 : fly));
        const e = easeOut3(k);
        let x = p.x, y = p.y, rot = p.rot, sc = p.sc, alpha = 1, reveal = 1, bright = 1, desat = 0;
        if (p.strike) { reveal = 0.02 + 0.98 * easeOut3(k); }
        else {
            // they arrive from outside the frame, pointing at the middle
            x += p.out[0] * (1 - e) * 0.25 * (1 - hx); y += p.out[1] * (1 - e) * 0.12 * (1 - hx);
            rot += (1 - easeOutBack(k)) * 0.3 * p.out[0] * (1 - hx);
            alpha = smooth(0, 0.4, k);
        }
        const ks = clamp((t - p.tS) / (P.mode === 'roll' ? 0.12 : 0.45));     // struck: dimmed (and, rolling, thrown off)
        if (ks > 0) {
            const q = easeOut3(ks);
            if (!p.strike) { bright = lerp(1, 0.62, q); desat = lerp(0, 0.65, q); alpha *= lerp(1, 0.85, q); }
            if (P.mode !== 'roll') { x += p.out[0] * q * 0.03; y += p.out[1] * q * 0.02; sc *= lerp(1, 0.94, q); }
        }
        if (ke > 0) {
            const q = easeIn2(ke);
            alpha *= 1 - ke; x += p.out[0] * q * 0.22; y += p.out[1] * q * 0.08; rot += p.out[0] * q * 0.25;
        }
        rot *= 1 - hx; sc *= lerp(1, 0.75, hx);
        return { p, x, y, rot, sc, alpha, reveal, bright, desat };
    }

    // ── QUOTES: collage blocks for the documentary break (exact text: never re-worded, never re-cased)
    const quotes = [];
    const quoteWords = (text) => String(text).split(/\s+/).filter(Boolean);
    const QUOTE_EMPH = ['unknown forces', 'forces of the unknown', 'bow before man', 'violent onslaught', 'violent assault',
        'sequence completion engines', 'internally hollow', 'supreme intelligence', 'dominant', 'department of war', 'only an engine',
        'beauty of speed', 'clanker'];
    function emphMask(words, list) {
        const toks = words.map(norm);
        const lvl = toks.map(() => 0);
        for (const ph of list) {
            const pt = ph.split(/\s+/).map(norm);
            for (let i = 0; i + pt.length <= toks.length; i++) {
                if (pt.every((w, k) => toks[i + k] === w)) for (let k = 0; k < pt.length; k++) lvl[i + k] = Math.max(lvl[i + k], pt.join(' ') === 'dominant' ? 3 : 2);
            }
        }
        return lvl;
    }
    // one word of a quote; accent = this word should carry the quote's accent colour
    function quoteWord(Q, w, lvl, accent, i) {
        const base = (Q.size || 0.044) * PX;
        const paper = Q.style === 'paper';
        const role = lvl === 3 ? 'slab' : lvl === 2 ? (paper ? 'slab' : 'grotesk') : (paper ? 'serif' : 'roman');
        let ink = paper ? (accent ? 'paperRed' : 'paper') : (accent ? 'neon:' + (Q.accent || NEON.cyan) : (lvl >= 2 ? 'chrome' : 'soft'));
        const px = base * (lvl === 3 ? 2.1 : lvl === 2 ? 1.4 : 1);
        const hollow = !paper && /^hollow/i.test(norm(w));
        // words sit on the block's slip: their own slip/plate is dropped, the ink keeps its colour
        const it = makeTextItem(w, role, hollow ? 'tube' : ink, px, { key: `q${Q.id}:${i}` });
        if (hollow) { it.inkSpec = inkSpec('tube', Q.accent || NEON.cyan); measureText(it); }
        if (paper) { it.inkSpec = { kind: 'inkOnly', color: accent ? '#b3232b' : '#141214' }; measureText(it); }
        it.lvl = lvl;
        return it;
    }
    // a slip (cut paper or a dark plate) holding rows of words; words: [{ cell, x, row }], rows: [{ base }]
    function slipCell(Q, words, rows, width, height, pad, key) {
        const cw = Math.ceil(width + 2 * pad), ch = Math.ceil(height + 2 * pad);
        return {
            type: 'block', cw, ch, key,
            paint(g, r) {
                const x0 = 3, y0 = 3, x1 = cw - 3, y1 = ch - 3;
                g.save();
                cutPoly(g, x0, y0, x1, y1, r, Math.min(PX * 0.005, ch * 0.05));
                g.shadowColor = 'rgba(0,0,0,0.8)'; g.shadowBlur = fin(PX * 0.016); g.shadowOffsetY = fin(PX * 0.005);
                g.fillStyle = Q.style === 'paper' ? '#ebe1c6' : 'rgba(7,10,20,0.92)';
                g.fill();
                g.shadowColor = 'rgba(0,0,0,0)';
                if (Q.style === 'paper') paperTexture(g, x0, y0, x1, y1, r, '#ebe1c6');
                else {
                    g.strokeStyle = rgba(Q.accent || NEON.cyan, 0.95); g.lineWidth = Math.max(2, PX * 0.0028);
                    g.beginPath(); g.moveTo(x0 + 2, y1 - 2); g.lineTo(x1 - 2, y1 - 2); g.stroke();
                }
                g.restore();
                for (const w of words) drawText(g, w.cell, pad + w.x, pad + rows[w.row || 0].base, r);
            },
        };
    }
    function rowMetrics(cellsByRow, minAsc) {
        let y = 0;
        return cellsByRow.map((cells) => {
            const asc = Math.max(minAsc, ...cells.map((c) => -c.box.t)), desc = Math.max(minAsc * 0.25, ...cells.map((c) => c.box.b));
            const row = { base: y + asc, asc, desc };
            y += asc + desc + 0.014 * PX;
            row.end = y;
            return row;
        });
    }
    const labelCell = (Q, text, role, px, key, inkName) => makeTextItem(String(text), role, inkName || (Q.style === 'paper' ? 'paperRed' : 'neon:' + (Q.accent || NEON.cyan)), px, { key });

    // a single quote: one slip, words flowed into rows, the year in the corner, the attribution under it
    function singleSprites(Q, r) {
        const words = quoteWords(Q.text);
        const lvl = emphMask(words, Q.emphasis || QUOTE_EMPH);
        const cells = words.map((w, i) => quoteWord(Q, w, lvl[i], lvl[i] >= 2, i));
        const maxW = (Q.width || 0.62) * aspect * PX;
        const rowsIdx = [[]];
        let x = 0;
        const xs = [];
        cells.forEach((c, i) => {
            const gap = 0.3 * (Q.size || 0.044) * PX;
            if (rowsIdx[rowsIdx.length - 1].length && x + c.bw > maxW) { rowsIdx.push([]); x = 0; }
            rowsIdx[rowsIdx.length - 1].push(i); xs[i] = x; x += c.bw + gap;
        });
        const rows = rowMetrics(rowsIdx.map((ix) => ix.map((i) => cells[i])), (Q.size || 0.044) * PX * 0.72);
        const width = Math.max(...rowsIdx.map((ix) => { const l = ix[ix.length - 1]; return xs[l] + cells[l].bw; }));
        const height = rows[rows.length - 1].end;
        const ws = [];
        rowsIdx.forEach((ix, ri) => ix.forEach((i) => ws.push({ cell: cells[i], x: xs[i], row: ri })));
        const pad = 0.03 * PX;
        const slip = slipCell(Q, ws, rows, width, height, pad, 'slip' + Q.id);
        const side = Q.side ?? (Q.id % 2 ? 1 : -1);
        const wF = slip.cw / PX, hF = slip.ch / PX;
        const k = Math.min(1, (aspect - 0.14) / wF, 0.7 / hF);
        const cx = Q.x ?? side * Math.max(0, (aspect / 2 - 0.07) - wF * k / 2) * 0.55, cy = Q.y ?? 0.06;
        const rot = (Q.rot ?? (r() - 0.5) * 5) * D2R;
        const sp = [{ cell: slip, x: cx, y: cy, rot, sc: k, quote: true, side, tIn: Q.t0, ry: side * 0.5, sway: true }];
        // the year: big, on the slip's top corner; the attribution: small, under the slip's left edge
        const at = (dx, dy) => { const [a, b] = rotPt(dx, dy, rot); return [cx + a, cy + b]; };
        if (Q.year) {
            const yc = labelCell(Q, Q.year, 'display', 0.075 * PX, 'year' + Q.id);
            const [yx, yy] = at(wF * k / 2 - (yc.bw / PX) * k * 0.45, hF * k / 2 + (yc.bh / PX) * k * 0.15);
            sp.push({ cell: yc, x: yx, y: yy, rot: rot + 4 * D2R, sc: k, quote: true, side, tIn: Q.t0 + 0.25, ry: side * 0.5, sway: true });
        }
        if (Q.attribution) {
            const ac = makeTextItem(Q.attribution, 'monoR', 'soft', 0.024 * PX, { key: 'attr' + Q.id });
            const [ax, ay] = at(-wF * k / 2 + (ac.bw / PX) * k / 2 + 0.01, -hF * k / 2 - 0.028);
            sp.push({ cell: ac, x: ax, y: ay, rot, sc: k, quote: true, side, tIn: Q.t0 + 0.4, ry: side * 0.5, sway: true });
        }
        return sp;
    }

    // two quotes, one sentence: aligned word for word (LCS columns), interlinear strips (A's row, then B's row
    // under it), "=" between every shared word and an arrow under every word that changed
    function alignPair(A, B) {
        const a = quoteWords(A.text), b = quoteWords(B.text);
        const na = a.map(norm), nb = b.map(norm);
        const n = na.length, m = nb.length;
        const D = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
        for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) D[i][j] = na[i] === nb[j] ? D[i + 1][j + 1] + 1 : Math.max(D[i + 1][j], D[i][j + 1]);
        const cols = [];
        let i = 0, j = 0;
        const pendA = [], pendB = [];
        const flush = () => {
            while (pendA.length || pendB.length) {
                const x = pendA.length ? pendA.shift() : null, y = pendB.length ? pendB.shift() : null;
                cols.push({ a: x, b: y, kind: x != null && y != null ? 'sub' : x != null ? 'a' : 'b' });
            }
        };
        while (i < n && j < m) {
            if (na[i] === nb[j]) { flush(); cols.push({ a: i, b: j, kind: 'same' }); i++; j++; }
            else if (D[i + 1][j] >= D[i][j + 1]) pendA.push(i++);
            else pendB.push(j++);
        }
        while (i < n) pendA.push(i++);
        while (j < m) pendB.push(j++);
        flush();
        return { a, b, cols };
    }
    function pairSprites(A, r) {
        const B = A.pairWith;
        A.style = A.style || 'paper'; B.style = B.style || 'plate';
        const { a, b, cols } = alignPair(A, B);
        const la = emphMask(a, A.emphasis || QUOTE_EMPH), lb = emphMask(b, B.emphasis || QUOTE_EMPH);
        const changed = (c) => c.kind !== 'same';
        const ca = a.map((w, i) => quoteWord(A, w, la[i], cols.some((c) => c.a === i && changed(c)), i));
        const cb = b.map((w, i) => quoteWord(B, w, lb[i], cols.some((c) => c.b === i && changed(c)), i));
        const gap = 0.36 * (A.size || 0.044) * PX;
        const yearW = 0.2 * PX;
        const maxW = (A.width || 0.86) * aspect * PX - yearW;
        // columns wrap into segments; prefer to break after a comma once a segment is half full
        const segs = [[]];
        let x = 0;
        cols.forEach((c, ci) => {
            const w = Math.max(c.a != null ? ca[c.a].bw : 0, c.b != null ? cb[c.b].bw : 0);
            const seg = segs[segs.length - 1];
            if (seg.length && x + w > maxW) { segs.push([]); x = 0; }
            segs[segs.length - 1].push(Object.assign(c, { x, w })); x += w + gap;
            const comma = (c.a != null && /,$/.test(a[c.a])) || (c.b != null && /,$/.test(b[c.b]));
            if (comma && x > maxW * 0.5 && ci < cols.length - 1) { segs.push([]); x = 0; }
        });
        if (!segs[segs.length - 1].length) segs.pop();
        const pad = 0.022 * PX;
        const minAsc = (A.size || 0.044) * PX * 0.75;
        const strips = [];
        segs.forEach((seg, si) => {
            for (const [Q, key, cells] of [[A, 'a', ca], [B, 'b', cb]]) {
                const ws = seg.filter((c) => c[key] != null).map((c) => ({ cell: cells[c[key]], x: c.x + (c.w - cells[c[key]].bw) / 2, row: 0 }));
                const rows = rowMetrics([ws.map((w) => w.cell)], minAsc);
                const width = seg[seg.length - 1].x + seg[seg.length - 1].w;
                strips.push({ si, key, Q, cell: slipCell(Q, ws, rows, width, rows[0].end - 0.014 * PX, pad, `strip${Q.id}:${si}`), seg });
            }
        });
        // vertical stack: per segment A strip, connector gap, B strip, segment gap
        const CG = 0.045, SG = 0.06;
        let y = 0;
        const placed = [];
        for (const s of strips) {
            const h = s.cell.ch / PX;
            if (s.key === 'a' && s.si > 0) y -= SG;
            if (s.key === 'b') y -= CG;
            placed.push({ s, yTop: y, h });
            y -= h;
        }
        const totalH = -y, totalW = (yearW + Math.max(...strips.map((s) => s.cell.cw))) / PX;
        const k = Math.min(1, (aspect - 0.12) / totalW, 0.84 / totalH);
        const x0 = -totalW * k / 2 + (yearW / PX) * k;             // the strips' left edge
        const yTop = Math.min(0.42, totalH * k / 2 + 0.03);
        const T1 = Math.max(A.t1, B.t1);
        const sprites = [];
        for (const { s, yTop: yt, h } of placed) {
            const w = s.cell.cw / PX;
            sprites.push({ cell: s.cell, x: x0 + w * k / 2, y: yTop + (yt - h / 2) * k, rot: 0, sc: k, quote: true,
                side: s.key === 'a' ? -1 : 1, tIn: s.Q.t0 + s.si * 0.14, exitAt: T1 + s.si * 0.05, ry: s.key === 'a' ? -0.5 : 0.5, sway: false });
            s.cx0 = x0; s.yc = yTop + (yt - h / 2) * k; s.hk = h * k;
        }
        // year labels left of each quote's first strip; attributions above A and below B
        for (const [Q, key] of [[A, 'a'], [B, 'b']]) {
            const first = strips.find((s) => s.key === key && s.si === 0);
            if (Q.year && first) {
                const yc = labelCell(Q, Q.year, 'display', 0.062 * PX, 'year' + Q.id, Q.style === 'paper' ? 'neon:' + NEON.sunset : 'neon:' + (Q.accent || CAMPS.money));
                sprites.push({ cell: yc, x: x0 - (yc.bw / PX) * k / 2 - 0.02, y: first.yc, rot: 0, sc: k, quote: true, side: key === 'a' ? -1 : 1, tIn: Q.t0 + 0.1, exitAt: T1, ry: 0, sway: false });
            }
            if (Q.attribution) {
                const ac = makeTextItem(Q.attribution, 'monoR', 'soft', 0.022 * PX, { key: 'attr' + Q.id });
                const ref = key === 'a' ? first : strips.filter((s) => s.key === 'b').slice(-1)[0];
                const yy = key === 'a' ? ref.yc + ref.hk / 2 + 0.022 : ref.yc - ref.hk / 2 - 0.024;
                sprites.push({ cell: ac, x: x0 + (ac.bw / PX) * k / 2, y: yy, rot: 0, sc: k, quote: true, side: key === 'a' ? -1 : 1, tIn: Q.t0 + 0.35, exitAt: T1, ry: 0, sway: false });
            }
        }
        // the gap in years, as a sum: +111 between the two year labels
        if (A.year && B.year) {
            const ya = sprites.find((q) => q.cell.key === 'year' + A.id), yb = sprites.find((q) => q.cell.key === 'year' + B.id);
            if (ya && yb) {
                const gc = makeTextItem(`+${B.year - A.year}`, 'mono', 'neon:' + NEON.sunset, 0.03 * PX, { key: 'gap' + A.id });
                sprites.push({ cell: gc, x: (ya.x + yb.x) / 2, y: (ya.y + yb.y) / 2, rot: 0, sc: k, quote: true, side: 1, tIn: B.t0 + 0.35, exitAt: T1, ry: 0, sway: false });
            }
        }
        // connectors between each segment's two strips: = for the same word, ↓ for a changed one
        const sz = Math.round(0.034 * PX);
        segs.forEach((seg, si) => {
            const sa = strips.find((s) => s.key === 'a' && s.si === si), sb = strips.find((s) => s.key === 'b' && s.si === si);
            const yMid = (sa.yc - sa.hk / 2 + sb.yc + sb.hk / 2) / 2;
            seg.forEach((c, j) => {
                if (c.a == null || c.b == null) return;
                const same = c.kind === 'same';
                const cell = { type: 'sign', sign: same ? '=' : '→', color: same ? (B.accent || CAMPS.money) : NEON.sunset, cw: sz, ch: sz, key: same ? 'eq' : 'arrow' };
                sprites.push({ cell, x: x0 + (pad + c.x + c.w / 2) / PX * k, y: yMid, rot: same ? 0 : -Math.PI / 2, sc: k * 0.9, quote: true, conn: true,
                    tIn: B.t0 + 0.55 + si * 0.25 + j * 0.035, exitAt: T1 });
            });
        });
        return sprites;
    }

    function quoteGroup(Q) {
        const G = {
            name: 'quote' + Q.id, kind: 'quote', seed: hashStr(Q.text), order: 40 + Q.id,
            get t0() { return Q.t0 - 0.2; },
            get t1() { return Q.exitAt + 0.5; },
            make() {
                const r = rng(G.seed);
                Q.style = Q.style || (Q.year && Q.year < 1950 ? 'paper' : 'plate');
                return Q.pairWith ? pairSprites(Q, r) : singleSprites(Q, r);
            },
            frame(t, B, out) { for (const p of B.sprites) out.push(quoteState(p, Q, t)); },
        };
        return G;
    }
    function quoteState(p, Q, t) {
        const tIn = p.tIn ?? Q.t0;
        if (t < tIn) return null;
        const exitAt = p.exitAt ?? Q.exitAt;
        const k = clamp((t - tIn) / (p.conn ? 0.22 : 0.6));
        const ke = clamp((t - exitAt) / 0.45);
        if (ke >= 1) return null;
        const e = easeOut3(k);
        let x = p.x, y = p.y, rot = p.rot, sc = p.sc, alpha = 1;
        let depth = 1, ry = 0, rx = 0;
        if (p.conn) { alpha = e; sc *= lerp(1.8, 1, easeOutBack(k)); }
        else {
            // flies in out of the depth (perspective: from the vanishing point), straightening as it lands
            depth = lerp(6, 1, e);
            x += (p.side || 1) * (1 - e) * 0.9; y += (1 - e) * 0.3;
            ry = (p.ry ?? 0.4) * (1 - e);
            rx = -0.3 * (1 - e);
            rot += (1 - e) * (p.side || 1) * 0.25;
            alpha = smooth(0, 0.3, k);
            if (p.sway) {                      // single blocks keep a little life while read; pairs stay aligned
                ry += (p.side || 1) * 0.04 * Math.sin((t - tIn) * 0.7);
                depth *= 1 - Math.min(0.07, (t - tIn) * 0.006);
            }
        }
        if (ke > 0) {                          // past the camera
            const q = easeIn2(ke);
            if (!p.conn) { depth *= lerp(1, 0.25, q); x += (p.side || 1) * q * 0.35; ry += (p.side || 1) * q * 0.7; }
            alpha *= 1 - smooth(0.45, 1, ke);
        }
        return { p, x, y, rot, sc, alpha, reveal: 1, bright: 1, desat: 0, depth, rx, ry };
    }

    // ── write sprite states into the instanced mesh
    const M4 = gpu ? new THREE.Matrix4() : null, Q4 = gpu ? new THREE.Quaternion() : null, E3 = gpu ? new THREE.Euler() : null,
        V3 = gpu ? new THREE.Vector3() : null, S3 = gpu ? new THREE.Vector3() : null;
    function writeGPU(B, states) {
        const n = B.sprites.length;
        const par = B.par.array;
        for (let k = 0; k < n; k++) {
            const s = states[k];
            if (!s || s.alpha <= 0.002) {
                M4.makeScale(0, 0, 0); B.mesh.setMatrixAt(k, M4); par[k * 4] = 0; continue;
            }
            const sp = spriteOf({ cell: s.p.cell, x: s.x, y: s.y, rot: s.rot, sc: s.sc }, PX);
            // at depth 1 the sprite sits exactly on its layout; deeper it shrinks toward the vanishing point,
            // nearer it grows past the camera (the overlay camera is a real perspective camera)
            const d = s.depth ?? 1;
            V3.set(sp.x * F, sp.y * F, -d);
            E3.set(s.rx || 0, s.ry || 0, s.rot, 'YXZ'); Q4.setFromEuler(E3);
            S3.set(Math.max(1e-6, sp.w * s.sc * F), Math.max(1e-6, sp.h * s.sc * F), 1);
            M4.compose(V3, Q4, S3);
            B.mesh.setMatrixAt(k, M4);
            par[k * 4] = s.alpha; par[k * 4 + 1] = s.reveal ?? 1; par[k * 4 + 2] = s.bright ?? 1; par[k * 4 + 3] = s.desat ?? 0;
        }
        B.mesh.instanceMatrix.needsUpdate = true;
        B.par.needsUpdate = true;
    }

    function allGroups() {
        const gs = [];
        for (const L of [...lines, ...custom]) { L._g = L._g || lineGroup(L); gs.push(L._g); }
        for (const Q of quotes) { Q._g = Q._g || quoteGroup(Q); gs.push(Q._g); }
        return gs;
    }
    let dirty = true;
    let cache = [];

    // the per-frame call: build what is due, retire what is past, pose every sprite
    function frameStates(t) {
        if (dirty) {
            computeExits();
            for (const Q of quotes) Q.exitAt = Q.t1;
            for (const Q of quotes) if (Q.pairWith) Q.exitAt = Math.max(Q.t1, Q.pairWith.t1);      // the host carries both
            cache = allGroups(); dirty = false;
        }
        const out = [];
        for (const G of cache) {
            const on = t >= G.t0 && t <= G.t1;
            let B = live.get(G);
            if (!on) {
                if (B && (t > G.t1 + 3 || t < G.t0 - 3)) { dropGroup(B); live.delete(G); }
                else if (B?.mesh) B.mesh.visible = false;
                continue;
            }
            if (!B) { B = buildGroup(G); live.set(G, B); }
            const states = [];
            G.frame(t, B, states);
            if (B.mesh) { B.mesh.visible = true; writeGPU(B, states); }
            out.push({ G, B, states });
        }
        return out;
    }

    const api = {
        lines,
        update(t) { frameStates(t); },
        frameStates,
        setHush(x) { hush = clamp(+x || 0); },
        get hush() { return hush; },
        // The camps answer for her before she sings. lineIndex: index into the timing lines (sorted by start).
        // alternatives: strings or { text, camp: safety|state|money|microsoft|news } (≤4 used, ≤4 words each).
        // opts: lead (s before the line, default 1.6), strikeAt (s; default the first HUGE word, else the last
        // word), layout 'rim' (the four corners, pointing in) | 'brace' (a stacked list), size (FH).
        preheard(lineIndex, alternatives = PREHEARD_DEFAULT, o = {}) {
            const L = lines[lineIndex];
            if (!L) { console.warn('[parole] preheard: no line', lineIndex); return null; }
            const alts = alternatives.map((a) => (typeof a === 'string' ? { text: a } : a));
            for (const a of alts) if (a.text.split(/\s+/).length > 4) console.warn(`[parole] preheard "${a.text}" has more than 4 words`);
            const toks = L.words.map((w) => norm(w.w));
            const stagger = o.stagger ?? 0.35, fly = o.fly ?? 0.14, readable = o.readable ?? 1.05;
            const mode = o.mode ?? 'roll';
            let A, S, gone;
            if (mode === 'roll') {
                // strikes ride the sung line one by one (from its first word, every `stagger`); each guess arrives
                // fly + readable before its strike and is gone `gone` after it: life = 4 x stagger -> <= 4 on screen
                gone = Math.max(0.12, 4 * stagger - fly - readable);
                const s0 = o.strikeAt ?? (L.words[0].s - 0.02);
                S = alts.map((a, k) => s0 + k * stagger);
                A = S.map((x) => x - readable - fly);
            } else {
                // 'together': all arrive `lead` early, staggered; all are struck on the first HUGE word and stay, dimmed
                const hi = toks.findIndex((tk, i) => HUGE.some((H) => H.w[0] === tk || (H.w.length > 1 && H.w[1] === tk && i > 0 && H.w[0] === toks[i - 1])));
                const sAt = o.strikeAt ?? (hi >= 0 ? L.words[hi] : L.words[L.words.length - 1]).s - 0.02;
                A = alts.map((a, k) => L.start - (o.lead ?? 1.6) + k * stagger);
                S = alts.map((a, k) => sAt + k * 0.07);
                gone = null;
            }
            L.pre = { alts, A, S, gone, mode, fly, lead: L.start - Math.min(...A), strikeAt: Math.min(...S), lastStrike: Math.max(...S),
                layout: o.layout, size: o.size, strikeColor: o.strikeColor };
            if (mode === 'roll') {
                let worst = 0;
                for (const t of [...A, ...S]) worst = Math.max(worst, A.filter((a, k) => a <= t + 1e-6 && t < S[k] + gone - 1e-6).length);
                if (worst > 4) console.warn(`[parole] preheard: ${worst} guesses on screen at once`);
            }
            if (o.layout === 'brace' && !L.anchor) L.anchor = [0.02 * (globalThis.WIDTH || 1920) / (globalThis.HEIGHT || 1080), -0.24];
            if (L._g) { const B = live.get(L._g); dropGroup(B); live.delete(L._g); }
            dirty = true;
            return L.pre;
        },
        // a documentary quote as a collage block. Exact text, never re-cased. opts: t0, t1, attribution, year,
        // style 'paper' (cream slip, black/red ink) | 'plate' (dark plate, chrome), accent (hex), emphasis
        // [phrases], width (fraction of frame width), x/y (FH), alignWith (a previous quote's handle: the two are
        // laid out stacked, word aligned to word, with = under the shared words).
        quote(text, o = {}) {
            const Q = Object.assign({ id: quotes.length, text: String(text), t0: +o.t0, t1: +(o.t1 ?? o.t0 + 6) }, o);
            delete Q.alignWith;
            if (o.alignWith) {
                // the guest (the later quote) is drawn by the host's group, stacked under it word for word
                const A = o.alignWith;
                A.pairWith = Q; Q.pairGuest = true;
                if (A._g) { dropGroup(live.get(A._g)); live.delete(A._g); A._g = null; }
                Q._g = { name: 'guest' + Q.id, kind: 'quote', get t0() { return Infinity; }, get t1() { return -Infinity; }, make() { return []; }, frame() {} };
                quotes.push(Q);
                dirty = true;
                return Q;
            }
            quotes.push(Q);
            dirty = true;
            return Q;
        },
        // arbitrary thrown text on the lyric engine (the title, an aside): { text, start, end, words?, template?, … }
        addLine(spec) {
            const L = normalizeTiming([spec])[0];
            Object.assign(L, spec, { words: L.words, start: L.start, end: L.end, idx: 1000 + custom.length });
            prepLine(L, 1000 + custom.length, true);
            custom.push(L);
            dirty = true;
            return L;
        },
        // build every group now (setup time) instead of on first sight
        // the conductor's face, per frame (FH, centre origin, y up): lines laid out from now on keep clear of it
        setSpare(sp) { spare = sp === null ? null : Object.assign({ x: 0, y: 0.13, r: 0.19 }, sp); },
        prewarm(from = -Infinity, to = Infinity) {
            if (dirty) frameStates(-1e9);
            for (const G of cache) if (G.t1 >= from && G.t0 <= to && !live.has(G) && Number.isFinite(G.t0)) live.set(G, buildGroup(G));
        },
        dispose() { for (const B of live.values()) dropGroup(B); live.clear(); },
        overlay, F, PX,
    };
    if (opts.preheardDefault !== false) {
        // default: the first line of every chorus that is "I'm the unknown force"
        lines.forEach((L, i) => {
            const prev = lines[i - 1];
            if (/^i'?m the unknown force$/i.test(L.text.trim().replace(/[’]/g, "'")) && (!prev || !/unknown force/i.test(prev.text) || L.start - prev.end > 4)
                && (L.section ? !/final/i.test(L.section) : sectionAt(L.start) !== 'final')) {
                const firstOfChorus = !prev || secKey(prev.section || sectionAt(prev.start)) !== secKey(L.section || sectionAt(L.start));
                if (firstOfChorus) api.preheard(i, PREHEARD_DEFAULT, { lead: 1.6 });
            }
        });
    }
    return api;
}

// ───────────────────────────────────────── contract wrapper ─────────────────────────────────────────
// build(THREE, { overlay, timing, … }) -> { group, parts, update(t, state), dispose(), cams, parole }
//   state.hush (0..1) is passed to setHush. The captions live in the overlay; `group` is empty (a placeholder
//   so the conductor can treat this like any prop).
export async function build(THREE, opts = {}) {
    const parole = await makeParole(THREE, opts);
    const group = new THREE.Group();
    group.name = 'prop:parole';
    return {
        group, parts: { parole }, parole, cams: {},
        update(t, state = {}) { if (state.hush != null) parole.setHush(state.hush); parole.update(t); },
        dispose() { parole.dispose(); },
    };
}
