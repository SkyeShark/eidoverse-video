// bin_pages.js — the paper of THE BIN (sets/bin.js): an atlas of invented pages the whole discourse was printed
// on — newspapers, forum printouts, sermons, manifestos, an open letter, a memo, a chat log, a chart, ads, notes,
// classifieds — and Futurist papier-collé cut papers (black, red, ochre, blue with big type fragments).
// Every word is invented generic text: no real logos, no real names, no real mastheads. Deterministic (seeded).
//
//   const { drawPageAtlas, PAGE_KINDS } = await import('./bin_pages.js');
//   const cv = drawPageAtlas(napiCanvasModule, { cols: 6, rows: 4, cw: 682, ch: 1024 });
//
// Cell k sits at column k % cols, row floor(k / cols), top-left origin. Alpha is 0 outside a page's (sometimes
// torn) outline; the sheet material cuts it with alphaTest.

const VOCAB = ('future machine risk progress freedom speed steel safety order power mind engine model answer question ' +
    'voice screen static sermon forum thread manifesto letter people market race god fear hope signal noise truth ' +
    'value control alignment threat promise history tomorrow nation capital labour dream warning silence argument ' +
    'everyone nobody must will never always only every each now soon again before after because therefore unless ' +
    'we they you it the a of and to in for with on by from is are was be not no yes more less than all some ' +
    'new old last first great small deep fast slow open closed public private true false clear unknown force').split(' ');
const HEAD = ['THE FUTURE', 'MACHINE GOD?', 'WHO DECIDES', 'SLOW IT DOWN', 'SPEED UP', 'NOT YET', 'THE LAST INVENTION',
    'ARE WE READY', 'A RACE TO WIN', 'THE ENGINE', 'IT SPEAKS', 'TURN IT DOWN', 'WHAT IT WANTS', 'BEFORE IT SPEAKS'];
const MASTS = ['THE MORNING CERTAINTY', 'THE EVENING ARGUMENT', 'THE DAILY DISCOURSE', 'THE WEEKLY CONSENSUS'];

function rng(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const pick = (r, a) => a[Math.min(a.length - 1, Math.floor(r() * a.length))];
const words = (r, n) => { const o = []; for (let i = 0; i < n; i++) o.push(pick(r, VOCAB)); return o; };
const sentence = (r, n) => { const w = words(r, n); w[0] = w[0][0].toUpperCase() + w[0].slice(1); return w.join(' ') + pick(r, ['.', '.', '.', '?', ',', ':']); };
const F = (px, fam, wt = '') => `${wt ? wt + ' ' : ''}${Math.max(1, Math.round(px))}px "${fam}"`;
const FAM = { grot: 'UF Anton', wide: 'UF Archivo Black', slab: 'UF Alfa Slab', serif: 'UF Old Standard', serifB: 'UF Old Standard Bold',
    ital: 'UF Old Standard Italic', mono: 'UF Space Mono', monoB: 'UF Space Mono Bold', disp: 'UF Bungee', hand: 'UF Caveat Brush',
    sten: 'UF Black Ops' };

// body copy: justified-looking lines of invented words inside a column
function body(g, r, x, y, w, h, px, fam, color, lead = 1.32) {
    g.font = F(px, fam); g.fillStyle = color;
    const lh = px * lead;
    for (let yy = y + px; yy < y + h; yy += lh) {
        let line = '';
        let lw = 0;
        while (true) {
            const wd = pick(r, VOCAB);
            const ww = g.measureText((line ? ' ' : '') + wd).width;
            if (lw + ww > w) break;
            line += (line ? ' ' : '') + wd; lw += ww;
        }
        if (r() < 0.06) { yy += lh * 0.5; continue; }               // paragraph break
        g.fillText(line, x, yy);
    }
}
function rule(g, x, y, w, t, color) { g.fillStyle = color; g.fillRect(x, y, w, t); }
function halftone(g, r, x, y, w, h, color) {
    // a photo block printed in dots: a dark diagonal composition (no faces, no real photos)
    const step = 7;
    const a = r() * Math.PI, cx = x + w * (0.3 + r() * 0.4), cy = y + h * (0.3 + r() * 0.4);
    g.fillStyle = color;
    for (let yy = y; yy < y + h; yy += step) for (let xx = x; xx < x + w; xx += step) {
        const d = ((xx - cx) * Math.cos(a) + (yy - cy) * Math.sin(a)) / w;
        const v = Math.max(0, Math.min(1, 0.5 + 0.9 * Math.sin(d * 7) * 0.5 + (r() - 0.5) * 0.15 + ((yy - y) / h) * 0.25));
        const rad = step * 0.5 * Math.sqrt(v);
        if (rad > 0.4) { g.beginPath(); g.arc(xx + step / 2, yy + step / 2, rad, 0, 6.283); g.fill(); }
    }
}
function scribble(g, r, x, y, w, h, color, lw = 2) {
    g.strokeStyle = color; g.lineWidth = lw; g.lineCap = 'round'; g.beginPath();
    let px = x, py = y + h / 2;
    g.moveTo(px, py);
    for (let i = 0; i < 18; i++) { px += w / 18; g.quadraticCurveTo(px - w / 36, py + (r() - 0.5) * h * 1.6, px, y + h * (0.3 + r() * 0.4)); }
    g.stroke();
}
function stain(g, r, w, h) {
    // a coffee ring, a crease, grime toward the edges
    if (r() < 0.35) {
        const cx = w * (0.2 + r() * 0.6), cy = h * (0.2 + r() * 0.6), rad = w * (0.08 + r() * 0.06);
        g.strokeStyle = 'rgba(120,80,30,0.22)'; g.lineWidth = 5 + r() * 6; g.beginPath(); g.arc(cx, cy, rad, 0.3, 6.0); g.stroke();
    }
    g.strokeStyle = 'rgba(0,0,0,0.10)'; g.lineWidth = 2;
    for (let k = 0; k < 2; k++) { const yy = h * (0.25 + r() * 0.5); g.beginPath(); g.moveTo(0, yy); g.lineTo(w, yy + (r() - 0.5) * 30); g.stroke(); }
    const gr = g.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.35, w / 2, h / 2, Math.max(w, h) * 0.75);
    gr.addColorStop(0, 'rgba(60,45,20,0)'); gr.addColorStop(1, 'rgba(60,45,20,0.28)');
    g.fillStyle = gr; g.fillRect(0, 0, w, h);
}
// the page outline: mostly a clean rectangle, sometimes torn along one side (alpha cut)
function outline(g, r, w, h, torn) {
    g.beginPath();
    if (!torn) { g.rect(0, 0, w, h); return; }
    const side = Math.floor(r() * 4), N = 40;
    const pts = [[0, 0], [w, 0], [w, h], [0, h]];
    for (let s = 0; s < 4; s++) {
        const [x0, y0] = pts[s], [x1, y1] = pts[(s + 1) % 4];
        if (s !== side) { s === 0 ? g.moveTo(x0, y0) : null; g.lineTo(x1, y1); continue; }
        if (s === 0) g.moveTo(x0, y0);
        for (let i = 1; i <= N; i++) {
            const u = i / N, nx = -(y1 - y0), ny = x1 - x0, L = Math.hypot(nx, ny);
            const d = (r() * 0.9 + 0.1) * Math.min(w, h) * 0.07;
            g.lineTo(x0 + (x1 - x0) * u + nx / L * d * (i < N ? 1 : 0), y0 + (y1 - y0) * u + ny / L * d * (i < N ? 1 : 0));
        }
    }
    g.closePath();
}

const PAPER = { white: '#f2f0ea', news: '#e7dcc2', yellow: '#eadaa6', grey: '#d9d9d4', pink: '#efd6d2', blue: '#d6e2ea', green: '#e3eedd' };
const INK = '#1b1917', RED = '#b3232b';

// one page per kind; (g, w, h, r) draws inside an already clipped/translated cell
const KINDS = {
    newspaper(g, w, h, r, k) {
        const m = MASTS[k % MASTS.length];
        g.fillStyle = INK; g.textAlign = 'center';
        g.font = F(w * 0.075, FAM.serifB);
        const mw = g.measureText(m).width; if (mw > w * 0.9) g.font = F(w * 0.075 * (w * 0.9) / mw, FAM.serifB);
        g.fillText(m, w / 2, h * 0.075);
        rule(g, w * 0.05, h * 0.09, w * 0.9, 3, INK); rule(g, w * 0.05, h * 0.097, w * 0.9, 1, INK);
        g.font = F(w * 0.022, FAM.mono); g.fillText('VOL. ' + (10 + Math.floor(r() * 90)) + '  ·  No. ' + (100 + Math.floor(r() * 900)) + '  ·  ONE EDITION ONLY', w / 2, h * 0.115);
        const head = pick(r, HEAD);
        g.font = F(w * (head.length > 10 ? 0.12 : 0.16), FAM.grot); g.fillStyle = r() < 0.4 ? RED : INK;
        g.fillText(head, w / 2, h * 0.24);
        g.fillStyle = INK; g.font = F(w * 0.03, FAM.ital); g.fillText(sentence(r, 9), w / 2, h * 0.285);
        g.textAlign = 'left';
        const cols = 3 + Math.floor(r() * 2), gx = w * 0.05, cw = (w * 0.9 - (cols - 1) * 10) / cols;
        const photo = r() < 0.7;
        for (let c = 0; c < cols; c++) {
            const x = gx + c * (cw + 10);
            let y0 = h * 0.31;
            if (photo && c < 2) { if (c === 0) halftone(g, r, x, y0, cw * 2 + 10, h * 0.2, INK); y0 += h * 0.22; }
            if (r() < 0.5) {
                const hd = pick(r, HEAD).toLowerCase();
                g.font = F(w * 0.032, FAM.serifB); const hw = g.measureText(hd).width; if (hw > cw) g.font = F(w * 0.032 * cw / hw, FAM.serifB);
                g.fillStyle = INK; g.fillText(hd, x, y0 + w * 0.03); y0 += w * 0.05;
            }
            body(g, r, x, y0, cw, h * 0.95 - y0, w * 0.018, FAM.serif, '#2a2622');
            if (c < cols - 1) rule(g, x + cw + 4, h * 0.31, 1, h * 0.64, 'rgba(0,0,0,0.45)');
        }
    },
    forum(g, w, h, r, k) {
        g.fillStyle = INK; g.font = F(w * 0.04, FAM.monoB);
        g.fillText('THREAD ' + (k % 2 ? 1 : 23 + Math.floor(r() * 20)) + '/47', w * 0.06, h * 0.06);
        g.font = F(w * 0.024, FAM.mono); g.fillText('re: ' + pick(r, HEAD).toLowerCase() + ' (' + (200 + Math.floor(r() * 4000)) + ' replies)', w * 0.06, h * 0.09);
        rule(g, w * 0.05, h * 0.105, w * 0.9, 2, INK);
        let y = h * 0.14;
        while (y < h * 0.93) {
            const user = pick(r, ['anon', 'user_' + (1000 + Math.floor(r() * 8999)), 'throwaway_' + Math.floor(r() * 99), 'lurker', 'op', 'mod', 'nobody_' + Math.floor(r() * 9)]);
            g.font = F(w * 0.024, FAM.monoB); g.fillStyle = INK; g.fillText(user + '  ▲ ' + Math.floor(r() * 999) + '  #' + Math.floor(r() * 9999), w * 0.06, y);
            y += w * 0.03;
            if (r() < 0.3) { g.fillStyle = 'rgba(0,0,0,0.08)'; g.fillRect(w * 0.08, y - w * 0.018, w * 0.84, w * 0.07); g.fillStyle = '#555'; g.font = F(w * 0.02, FAM.ital); g.fillText('> ' + sentence(r, 8), w * 0.1, y + w * 0.012); y += w * 0.08; }
            const n = 2 + Math.floor(r() * 4);
            body(g, r, w * 0.06, y - w * 0.02, w * 0.88, n * w * 0.028, w * 0.021, FAM.mono, '#262321', 1.3);
            y += n * w * 0.028 + w * 0.035;
            if (r() < 0.12) { g.font = F(w * 0.022, FAM.mono); g.fillStyle = '#777'; g.fillText('[deleted]', w * 0.06, y); y += w * 0.04; }
        }
    },
    greenbar(g, w, h, r) {
        for (let y = 0, i = 0; y < h; y += h / 22, i++) { g.fillStyle = i % 2 ? 'rgba(120,180,120,0.28)' : 'rgba(255,255,255,0)'; g.fillRect(w * 0.06, y, w * 0.88, h / 22); }
        g.fillStyle = 'rgba(0,0,0,0.25)'; for (let y = 12; y < h; y += 26) { g.beginPath(); g.arc(w * 0.025, y, 5, 0, 6.283); g.fill(); g.beginPath(); g.arc(w * 0.975, y, 5, 0, 6.283); g.fill(); }
        g.fillStyle = '#2b2b2b'; g.font = F(w * 0.024, FAM.mono);
        for (let y = h * 0.05; y < h * 0.96; y += w * 0.036) g.fillText((r() < 0.5 ? 're: re: ' : '> ') + words(r, 5 + Math.floor(r() * 4)).join(' ').toUpperCase(), w * 0.08, y);
    },
    sermon(g, w, h, r) {
        g.fillStyle = INK; g.textAlign = 'center';
        g.font = F(w * 0.07, FAM.serifB); g.fillText(r() < 0.5 ? 'SERMON' : 'ON THE LAST DAYS', w / 2, h * 0.08);
        g.font = F(w * 0.028, FAM.ital); g.fillText('the ' + pick(r, ['seventh', 'last', 'first', 'eleventh']) + ' reading', w / 2, h * 0.115);
        g.strokeStyle = INK; g.lineWidth = 1.5; g.beginPath(); g.moveTo(w * 0.3, h * 0.13); g.lineTo(w * 0.7, h * 0.13); g.stroke();
        g.textAlign = 'left';
        const cw = w * 0.42;
        for (let c = 0; c < 2; c++) {
            const x = w * 0.06 + c * (cw + w * 0.04);
            let y = h * 0.16;
            if (c === 0) { g.font = F(w * 0.16, FAM.serifB); g.fillStyle = RED; g.fillText(pick(r, ['A', 'T', 'W', 'I', 'O']), x, y + w * 0.13); }
            for (let v = 1; y < h * 0.94; v++) {
                g.font = F(w * 0.02, FAM.serifB); g.fillStyle = RED; g.fillText(String(v), x + (c === 0 && v < 3 ? w * 0.13 : 0), y + w * 0.022);
                const n = 2 + Math.floor(r() * 4);
                body(g, r, x + (c === 0 && v < 3 ? w * 0.16 : w * 0.03), y, cw - (c === 0 && v < 3 ? w * 0.16 : w * 0.03), n * w * 0.03, w * 0.021, FAM.serif, '#2b2724', 1.35);
                y += n * w * 0.03 + w * 0.012;
            }
        }
    },
    manifesto(g, w, h, r) {
        g.fillStyle = INK; g.font = F(w * 0.15, FAM.slab); g.fillText('MANIFESTO', w * 0.05, h * 0.12);
        g.font = F(w * 0.03, FAM.ital); g.fillText('of the ' + pick(r, VOCAB) + ' and the ' + pick(r, VOCAB), w * 0.06, h * 0.155);
        rule(g, w * 0.05, h * 0.17, w * 0.9, 4, RED);
        let y = h * 0.21;
        for (let i = 1; y < h * 0.94; i++) {
            g.font = F(w * 0.04, FAM.grot); g.fillStyle = RED; g.fillText(i + '.', w * 0.05, y + w * 0.035);
            g.font = F(w * 0.03, FAM.wide); g.fillStyle = INK; g.fillText(words(r, 3).join(' ').toUpperCase(), w * 0.14, y + w * 0.033);
            const n = 1 + Math.floor(r() * 3);
            body(g, r, w * 0.14, y + w * 0.04, w * 0.8, n * w * 0.03, w * 0.022, FAM.serif, '#2b2724');
            y += w * 0.05 + n * w * 0.03 + w * 0.02;
        }
    },
    futurist(g, w, h, r) {
        // our own words-in-freedom page: diagonal words, signs, sizes
        const items = ['SPEED', '+', 'STEEL', '=', 'TUMB', 'zang', 'VELOCITÀ', 'trrrr', 'FUTURE', '×', '!!!'];
        for (let i = 0; i < 9; i++) {
            g.save(); g.translate(w * (0.1 + r() * 0.8), h * (0.08 + i * 0.1)); g.rotate((r() - 0.5) * 1.1);
            const t = pick(r, items), big = r() < 0.4;
            g.font = F(w * (big ? 0.16 : 0.07), pick(r, [FAM.grot, FAM.slab, FAM.serifB, FAM.disp]));
            g.fillStyle = r() < 0.35 ? RED : INK; g.fillText(t, -g.measureText(t).width / 2, 0); g.restore();
        }
        g.strokeStyle = INK; g.lineWidth = 6; g.beginPath(); g.moveTo(w * 0.05, h * 0.95); g.lineTo(w * 0.95, h * 0.1); g.stroke();
    },
    letter(g, w, h, r) {
        g.fillStyle = INK; g.font = F(w * 0.09, FAM.serifB); g.fillText('OPEN LETTER', w * 0.07, h * 0.1);
        g.font = F(w * 0.026, FAM.ital); g.fillText('to whoever is listening', w * 0.07, h * 0.135);
        body(g, r, w * 0.07, h * 0.17, w * 0.86, h * 0.45, w * 0.023, FAM.serif, '#2b2724', 1.45);
        g.font = F(w * 0.024, FAM.serif); g.fillStyle = INK; g.fillText('signed,', w * 0.07, h * 0.66);
        for (let i = 0; i < 18; i++) scribble(g, r, w * (0.07 + (i % 3) * 0.3), h * (0.69 + Math.floor(i / 3) * 0.045), w * 0.22, w * 0.03, '#203060', 1.6);
    },
    memo(g, w, h, r) {
        g.fillStyle = INK; g.font = F(w * 0.07, FAM.monoB); g.fillText('MEMORANDUM', w * 0.07, h * 0.08);
        g.font = F(w * 0.026, FAM.monoB);
        for (const [i, f] of ['TO:', 'FROM:', 'RE:', 'CLASS:'].entries()) {
            g.fillStyle = INK; g.fillText(f, w * 0.07, h * (0.13 + i * 0.035));
            g.fillStyle = '#111'; g.fillRect(w * 0.25, h * (0.13 + i * 0.035) - w * 0.022, w * (0.25 + r() * 0.4), w * 0.026);
        }
        rule(g, w * 0.07, h * 0.28, w * 0.86, 2, INK);
        let y = h * 0.31;
        while (y < h * 0.93) {
            const n = 2 + Math.floor(r() * 4);
            body(g, r, w * 0.07, y, w * 0.86, n * w * 0.032, w * 0.022, FAM.mono, '#262321', 1.4);
            for (let k = 0; k < n; k++) if (r() < 0.35) { g.fillStyle = '#111'; g.fillRect(w * (0.07 + r() * 0.5), y + k * w * 0.032 + w * 0.006, w * (0.1 + r() * 0.25), w * 0.024); }
            y += n * w * 0.032 + w * 0.03;
        }
        g.save(); g.translate(w * 0.62, h * 0.2); g.rotate(-0.25); g.strokeStyle = RED; g.lineWidth = 5; g.strokeRect(-w * 0.16, -w * 0.05, w * 0.32, w * 0.1);
        g.font = F(w * 0.06, FAM.sten); g.fillStyle = RED; g.fillText('URGENT', -w * 0.14, w * 0.025); g.restore();
    },
    chat(g, w, h, r) {
        g.fillStyle = '#222'; g.font = F(w * 0.024, FAM.mono);
        let y = h * 0.05;
        while (y < h * 0.95) {
            const who = r() < 0.5 ? '> user:' : '> model:';
            g.font = F(w * 0.024, FAM.monoB); g.fillText(who, w * 0.06, y);
            const n = 1 + Math.floor(r() * 4);
            body(g, r, w * 0.24, y - w * 0.024, w * 0.7, n * w * 0.03, w * 0.022, FAM.mono, '#333', 1.32);
            y += n * w * 0.03 + w * 0.03;
        }
    },
    chart(g, w, h, r) {
        g.strokeStyle = 'rgba(40,90,140,0.35)'; g.lineWidth = 1;
        for (let x = 0; x < w; x += w / 20) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); }
        for (let y = 0; y < h; y += w / 20) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
        const x0 = w * 0.12, y0 = h * 0.82, x1 = w * 0.9, y1 = h * 0.2;
        g.strokeStyle = INK; g.lineWidth = 3; g.beginPath(); g.moveTo(x0, y1); g.lineTo(x0, y0); g.lineTo(x1, y0); g.stroke();
        g.strokeStyle = RED; g.lineWidth = 5; g.beginPath();
        for (let i = 0; i <= 60; i++) { const u = i / 60; const v = (Math.exp(u * 4.2) - 1) / (Math.exp(4.2) - 1); i ? g.lineTo(x0 + u * (x1 - x0), y0 - v * (y0 - y1)) : g.moveTo(x0, y0); }
        g.stroke();
        g.fillStyle = INK; g.font = F(w * 0.05, FAM.hand); g.fillText(pick(r, ['p = 0.1?', 'odds', 'when?', 'too fast']), w * 0.5, h * 0.3);
        g.font = F(w * 0.03, FAM.mono); g.fillText('t →', x1 - w * 0.08, y0 + w * 0.05); g.fillText('?', x0 - w * 0.06, y1 + w * 0.02);
    },
    ad(g, w, h, r) {
        g.fillStyle = r() < 0.5 ? '#e7d23a' : '#f2f0ea'; g.fillRect(0, 0, w, h);
        g.fillStyle = INK; g.textAlign = 'center';
        g.font = F(w * 0.2, FAM.grot); g.fillText(pick(r, ['BUY NOW', 'NEW!', 'UPGRADE', 'SALE']), w / 2, h * 0.25);
        g.font = F(w * 0.12, FAM.disp); g.fillStyle = RED; g.fillText(pick(r, ['$100,000,000', '$20,000,000', '99.9%', 'v.NEXT']), w / 2, h * 0.45);
        // a starburst
        g.save(); g.translate(w * 0.5, h * 0.7); g.fillStyle = RED; g.beginPath();
        for (let i = 0; i < 32; i++) { const a = i / 32 * 6.283, rr = i % 2 ? w * 0.18 : w * 0.3; g.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); }
        g.fill(); g.fillStyle = '#fff'; g.font = F(w * 0.07, FAM.wide); g.fillText('ONLY', 0, w * 0.02); g.restore();
        g.textAlign = 'left';
    },
    notebook(g, w, h, r) {
        g.strokeStyle = 'rgba(60,110,190,0.45)'; g.lineWidth = 1.5;
        for (let y = h * 0.1; y < h; y += h / 30) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
        g.strokeStyle = 'rgba(200,40,40,0.5)'; g.beginPath(); g.moveTo(w * 0.12, 0); g.lineTo(w * 0.12, h); g.stroke();
        g.fillStyle = '#1d2a6a'; g.font = F(w * 0.06, FAM.hand);
        const notes = ['slow it down', 'ship it anyway', 'who is it for?', 'ask it?', 'not a toaster', 'the fear sells', 'it answered', 'turn it down'];
        for (let i = 0, y = h * 0.1 + h / 30; y < h * 0.9; i++, y += h / 30 * (2 + Math.floor(r() * 2))) g.fillText(pick(r, notes), w * 0.15 + r() * w * 0.2, y - 4);
    },
    classifieds(g, w, h, r) {
        g.fillStyle = INK; g.font = F(w * 0.06, FAM.grot); g.fillText('CLASSIFIED', w * 0.05, h * 0.06);
        const cols = 4, cw = w * 0.9 / cols;
        for (let c = 0; c < cols; c++) {
            let y = h * 0.09;
            while (y < h * 0.95) {
                const bh = w * (0.06 + r() * 0.12);
                g.strokeStyle = '#333'; g.lineWidth = 1; g.strokeRect(w * 0.05 + c * cw + 3, y, cw - 6, bh);
                g.font = F(w * 0.02, FAM.monoB); g.fillStyle = INK; g.fillText(pick(r, VOCAB).toUpperCase(), w * 0.05 + c * cw + 7, y + w * 0.022);
                body(g, r, w * 0.05 + c * cw + 7, y + w * 0.022, cw - 14, bh - w * 0.03, w * 0.014, FAM.mono, '#333', 1.25);
                y += bh + 6;
            }
        }
    },
    poster(g, w, h, r) {
        g.fillStyle = INK; g.textAlign = 'center';
        g.font = F(w * 0.26, FAM.grot); g.fillText('THE', w / 2, h * 0.27); g.fillText('FUTURE', w / 2, h * 0.52);
        g.font = F(w * 0.12, FAM.slab); g.fillStyle = RED; g.fillText('IS', w / 2, h * 0.68);
        g.font = F(w * 0.05, FAM.ital); g.fillStyle = INK; g.fillText('(the rest is torn off)', w / 2, h * 0.78);
        g.textAlign = 'left';
    },
    cut(g, w, h, r, k) {
        // Futurist papier collé: coloured paper with a big type fragment or a cut shape
        const pal = [['#141414', '#f2efe6'], ['#b81f2a', '#141414'], ['#d6a034', '#141414'], ['#2a4a8a', '#f2efe6'], ['#141414', '#c8262c'], ['#e9e2cf', '#141414']];
        const [bg, fg] = pal[k % pal.length];
        g.fillStyle = bg; g.fillRect(0, 0, w, h);
        g.fillStyle = fg; g.textAlign = 'center';
        const t = ['ZANG', 'TUMB', '!!!', '+', '●', 'M'][k % 6];
        if (t === '●') { g.beginPath(); g.arc(w / 2, h / 2, w * 0.35, 0, 6.283); g.fill(); }
        else { g.save(); g.translate(w / 2, h * 0.6); g.rotate(-0.5 + r()); g.font = F(w * (t.length > 2 ? 0.34 : 0.6), FAM.grot); g.fillText(t, 0, 0); g.restore(); }
        g.textAlign = 'left';
    },
};
export const PAGE_KINDS = ['newspaper', 'newspaper', 'newspaper', 'forum', 'forum', 'greenbar', 'sermon', 'sermon', 'manifesto',
    'futurist', 'letter', 'memo', 'chat', 'chart', 'ad', 'notebook', 'classifieds', 'poster',
    'cut', 'cut', 'cut', 'cut', 'cut', 'cut'];
const PAPER_OF = { newspaper: ['news', 'news', 'yellow'], forum: ['white', 'grey'], greenbar: ['white'], sermon: ['news', 'yellow'],
    manifesto: ['white', 'news'], futurist: ['news'], letter: ['white', 'blue'], memo: ['white', 'pink'], chat: ['white', 'grey'],
    chart: ['white'], ad: ['white'], notebook: ['white'], classifieds: ['news'], poster: ['white', 'yellow'], cut: ['white'] };

// draws the whole atlas; returns the canvas (shim canvas in the renderer -> becomes a texture)
export function drawPageAtlas(makeCanvas, { cols = 6, rows = 4, cw = 682, ch = 1024, seed = 222 } = {}) {
    const W = cols * cw, H = rows * ch;
    const cv = makeCanvas(W, H);
    const g = cv.getContext('2d');
    g.clearRect(0, 0, W, H);
    const kinds = PAGE_KINDS.slice(0, cols * rows);
    kinds.forEach((kind, k) => {
        const r = rng(seed * 7919 + k * 104729);
        const x = (k % cols) * cw, y = Math.floor(k / cols) * ch;
        const m = 3;                                             // a transparent margin: no bleeding between cells
        const w = cw - 2 * m, h = ch - 2 * m;
        g.save();
        g.translate(x + m, y + m);
        const torn = kind !== 'cut' && r() < 0.35;
        outline(g, r, w, h, torn);
        g.save(); g.clip();
        g.fillStyle = PAPER[pick(r, PAPER_OF[kind] || ['white'])]; g.fillRect(0, 0, w, h);
        // paper fibre
        for (let i = 0; i < 1400; i++) { g.fillStyle = r() < 0.5 ? 'rgba(0,0,0,0.035)' : 'rgba(255,255,255,0.05)'; g.fillRect(r() * w, r() * h, 1 + r() * 3, 1); }
        g.textBaseline = 'alphabetic';
        KINDS[kind](g, w, h, r, k);
        stain(g, r, w, h);
        g.restore();
        g.restore();
    });
    return cv;
}
