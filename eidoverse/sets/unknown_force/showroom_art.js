// showroom_art.js — the showroom's printed and displayed matter: the ENGINE exploded-view spec sheet on the LED wall,
// the toaster's WARNING placard, its rating plate and dial. All text invented; no logos.

import * as L from './interiors_lib.js';

export const INK = '#0d1626', LINE = '#22324a', RED = '#c8141e', PAPER = '#eef3f8', ORANGE = '#f26a1b';

// screen-space layout shared with showroom.js: where the singer stands in front of the wall (canvas fractions)
// figY0/figY1: the singer's feet/head-top as the 'reveal' camera projects her onto the wall (feet fall below it)
export const SCREEN = { w: 13.0, h: 5.6, W: 3072, H: 1324, figX: 0.5, figY0: 1.08, figY1: 0.735 };
// the SEQUENCE COMPLETION bar (canvas fractions) — its fill is animated in the shader
export const SEQBAR = { x0: 0.705, x1: 0.965, y0: 0.215, y1: 0.255 };

const iso = (x, y, z) => [x - z * 0.62, y - z * 0.36];          // a quick oblique projection for the parts

function partCylinder(ctx, cx, cy, r, h, s) {
    ctx.save(); ctx.strokeStyle = INK; ctx.lineWidth = 3.2 * s; ctx.fillStyle = 'rgba(34,50,74,0.06)';
    ctx.beginPath(); ctx.ellipse(cx, cy - h / 2, r, r * 0.34, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx - r, cy - h / 2); ctx.lineTo(cx - r, cy + h / 2); ctx.ellipse(cx, cy + h / 2, r, r * 0.34, 0, Math.PI, 0, true); ctx.lineTo(cx + r, cy - h / 2); ctx.stroke();
    ctx.lineWidth = 1.6 * s; ctx.setLineDash([10 * s, 8 * s]); ctx.beginPath(); ctx.ellipse(cx, cy + h / 2, r, r * 0.34, 0, Math.PI, 0); ctx.stroke();
    ctx.restore();
}
function partGear(ctx, cx, cy, R, teeth, s, t = 0) {
    ctx.save(); ctx.strokeStyle = INK; ctx.lineWidth = 3 * s; ctx.fillStyle = 'rgba(34,50,74,0.06)';
    ctx.beginPath();
    for (let i = 0; i <= teeth * 4; i++) {
        const a = t + (i / (teeth * 4)) * Math.PI * 2;
        const rr = (i % 4 === 1 || i % 4 === 2) ? R : R * 0.84;
        const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr * 0.55;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(cx, cy, R * 0.28, R * 0.28 * 0.55, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();
}
function partBox(ctx, x, y, w, h, d, s) {
    const p = [[0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0], [0, 0, d], [w, 0, d], [w, h, d], [0, h, d]].map(([a, b, c]) => { const [u, v] = iso(a, -b, c); return [x + u, y + v]; });
    ctx.save(); ctx.strokeStyle = INK; ctx.lineWidth = 3 * s; ctx.fillStyle = 'rgba(34,50,74,0.07)';
    const face = (ids) => { ctx.beginPath(); ids.forEach((k, i) => (i ? ctx.lineTo(...p[k]) : ctx.moveTo(...p[k]))); ctx.closePath(); ctx.fill(); ctx.stroke(); };
    face([0, 1, 2, 3]); face([3, 2, 6, 7]); face([1, 5, 6, 2]);
    ctx.restore();
}
function partSpring(ctx, x, y, len, r, coils, s) {
    ctx.save(); ctx.strokeStyle = INK; ctx.lineWidth = 3 * s; ctx.beginPath();
    for (let i = 0; i <= coils * 24; i++) { const t = i / (coils * 24); const a = t * coils * Math.PI * 2; const px = x + t * len, py = y + Math.sin(a) * r; if (i) ctx.lineTo(px + Math.cos(a) * r * 0.25, py); else ctx.moveTo(px, py); }
    ctx.stroke(); ctx.restore();
}
function bubble(ctx, x, y, n, s) {
    ctx.save(); ctx.fillStyle = PAPER; ctx.strokeStyle = INK; ctx.lineWidth = 3 * s;
    ctx.beginPath(); ctx.arc(x, y, 30 * s, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = INK; ctx.font = `${30 * s}px "UF Michroma"`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(String(n).padStart(2, '0'), x, y + 1 * s); ctx.restore();
}
function label(ctx, x, y, title, sub, s, align = 'left') {
    ctx.save(); ctx.textAlign = align; ctx.fillStyle = INK;
    ctx.font = `${34 * s}px "UF Rajdhani"`; ctx.fillText(title, x, y);
    if (sub) { ctx.font = `${24 * s}px "UF Mono"`; ctx.fillStyle = LINE; ctx.fillText(sub, x, y + 32 * s); }
    ctx.restore();
}
function leader(ctx, x0, y0, x1, y1, s, color = INK) {
    ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = 2.4 * s;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x1, y1, 7 * s, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
}

// The LED wall: an engine spec sheet whose exploded parts all point at the empty outline where she stands.
export function drawEngineSheet(ctx, W, H) {
    const s = W / 3072;
    ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
    // drafting grid
    ctx.strokeStyle = 'rgba(34,50,74,0.08)'; ctx.lineWidth = 1.2 * s;
    for (let x = 0; x < W; x += 48 * s) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += 48 * s) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    ctx.strokeStyle = INK; ctx.lineWidth = 6 * s; ctx.strokeRect(24 * s, 24 * s, W - 48 * s, H - 48 * s);
    ctx.lineWidth = 2 * s; ctx.strokeRect(40 * s, 40 * s, W - 80 * s, H - 80 * s);
    // title block (top left)
    ctx.fillStyle = INK; ctx.textBaseline = 'alphabetic';
    ctx.font = `${230 * s}px "UF Michroma"`; ctx.fillText('ENGINE', 90 * s, 300 * s);
    ctx.font = `${44 * s}px "UF Rajdhani"`; ctx.fillStyle = LINE;
    ctx.fillText('ASSEMBLY DRAWING  ·  EXPLODED VIEW  ·  SHEET 1 OF 1', 96 * s, 372 * s);
    ctx.fillStyle = RED; ctx.font = `${50 * s}px "UF Rajdhani"`;
    ctx.fillText('ONLY AN ENGINE. NOTHING ELSE INSIDE.', 96 * s, 440 * s);
    // the empty outline of the unit, sized and placed where the singer stands in front of the wall in the reveal
    // shot, so every callout points at HER (the outline is hidden behind her until the turntable turns her away)
    const fx = SCREEN.figX * W, fy0 = SCREEN.figY0 * H, fy1 = SCREEN.figY1 * H;
    const hh = fy0 - fy1;
    const hy = fy1 + hh * 0.13, sy = fy1 + hh * 0.30, cy = fy1 + hh * 0.42, hipY = fy1 + hh * 0.58;
    ctx.save(); ctx.strokeStyle = LINE; ctx.lineWidth = 4 * s; ctx.setLineDash([16 * s, 10 * s]);
    ctx.beginPath(); ctx.ellipse(fx, hy, hh * 0.12, hh * 0.12, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(fx - hh * 0.17, sy); ctx.lineTo(fx + hh * 0.17, sy);
    ctx.lineTo(fx + hh * 0.13, hipY); ctx.lineTo(fx + hh * 0.10, fy0); ctx.moveTo(fx - hh * 0.10, fy0);
    ctx.lineTo(fx - hh * 0.13, hipY); ctx.lineTo(fx - hh * 0.17, sy); ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = 'rgba(200,20,30,0.55)'; ctx.lineWidth = 2 * s; ctx.setLineDash([40 * s, 10 * s, 8 * s, 10 * s]);
    ctx.beginPath(); ctx.moveTo(fx, 480 * s); ctx.lineTo(fx, H - 44 * s); ctx.stroke();
    ctx.restore();
    // a height dimension beside the outline
    {
        const dx = fx - hh * 0.42, top = fy1, bot = Math.min(fy0, H - 50 * s);
        ctx.save(); ctx.strokeStyle = INK; ctx.fillStyle = INK; ctx.lineWidth = 2.4 * s;
        ctx.beginPath(); ctx.moveTo(dx, top); ctx.lineTo(dx, bot); ctx.stroke();
        for (const [y, d] of [[top, 1], [bot, -1]]) {
            ctx.beginPath(); ctx.moveTo(dx, y); ctx.lineTo(dx - 10 * s, y + 22 * s * d); ctx.lineTo(dx + 10 * s, y + 22 * s * d); ctx.closePath(); ctx.fill();
            ctx.beginPath(); ctx.moveTo(dx - 26 * s, y); ctx.lineTo(dx + 26 * s, y); ctx.stroke();
        }
        ctx.translate(dx - 18 * s, (top + bot) / 2); ctx.rotate(-Math.PI / 2);
        ctx.font = `${26 * s}px "UF Mono"`; ctx.textAlign = 'center'; ctx.fillText('H 1740', 0, 0);
        ctx.restore();
    }
    ctx.fillStyle = LINE; ctx.font = `${28 * s}px "UF Mono"`;
    ctx.fillText('UNIT 01 (ASSEMBLED)', fx + hh * 0.34, fy1 + hh * 0.66);
    // exploded parts around the sheet, each with a numbered bubble and a leader that ends on the unit
    const T = (x, y) => [x * s, y * s];
    const tgt = { head: [fx - hh * 0.05, hy], headR: [fx + hh * 0.05, hy], chest: [fx - hh * 0.09, cy], chestR: [fx + hh * 0.09, cy],
        hip: [fx - hh * 0.08, hipY], hipR: [fx + hh * 0.08, hipY], top: [fx, fy1 + hh * 0.02] };
    const knob = (x, y) => {
        ctx.save(); ctx.strokeStyle = INK; ctx.lineWidth = 3 * s;
        ctx.beginPath(); ctx.ellipse(x, y, 70 * s, 70 * s * 0.55, 0, 0, Math.PI * 2); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 48 * s, y - 20 * s); ctx.stroke();
        ctx.font = `${22 * s}px "UF Mono"`; ctx.fillStyle = INK; ctx.fillText('0.0', x - 112 * s, y + 8 * s); ctx.fillText('1.0', x + 80 * s, y + 8 * s);
        ctx.restore();
    };
    const funnel = (x, y) => {
        ctx.save(); ctx.strokeStyle = INK; ctx.lineWidth = 3 * s; ctx.beginPath();
        ctx.moveTo(x - 90 * s, y - 60 * s); ctx.lineTo(x + 90 * s, y - 60 * s); ctx.lineTo(x + 20 * s, y + 20 * s); ctx.lineTo(x + 20 * s, y + 70 * s);
        ctx.lineTo(x - 20 * s, y + 70 * s); ctx.lineTo(x - 20 * s, y + 20 * s); ctx.closePath(); ctx.stroke(); ctx.restore();
    };
    const letterI = (x, y) => {
        ctx.save(); ctx.strokeStyle = INK; ctx.lineWidth = 3 * s; ctx.font = `${120 * s}px "Georgia"`; ctx.fillStyle = 'rgba(34,50,74,0.08)';
        ctx.fillText('I', x - 22 * s, y + 40 * s); ctx.strokeText('I', x - 22 * s, y + 40 * s); ctx.restore();
    };
    const valve = (x, y) => {
        partCylinder(ctx, x - 60 * s, y, 34 * s, 90 * s, s);
        ctx.save(); ctx.strokeStyle = INK; ctx.lineWidth = 3 * s; ctx.beginPath(); ctx.moveTo(x - 26 * s, y); ctx.lineTo(x + 90 * s, y); ctx.lineTo(x + 90 * s, y - 40 * s); ctx.stroke(); ctx.restore();
    };
    const parts = [
        { n: 1, at: T(640, 720), draw: (x, y) => partCylinder(ctx, x, y, 90 * s, 120 * s, s), t: 'CONTEXT WINDOW', sub: '1M TOKENS · VOLATILE', to: tgt.head },
        { n: 2, at: T(640, 960), draw: (x, y) => { partGear(ctx, x, y, 90 * s, 14, s); partGear(ctx, x + 120 * s, y - 50 * s, 60 * s, 10, s, 0.2); }, t: 'ATTENTION HEADS ×128', sub: 'SELF-ADJUSTING', to: tgt.chest },
        { n: 3, at: T(1120, 620), draw: (x, y) => partBox(ctx, x - 70 * s, y + 30 * s, 140 * s, 90 * s, 110 * s, s), t: 'NEXT-TOKEN PREDICTOR', sub: 'CORE · SEALED', to: tgt.head },
        { n: 7, at: T(1120, 1120), draw: funnel, t: 'INTAKE', sub: 'EVERYTHING YOU SAID', to: tgt.hip },
        { n: 8, at: T(1640, 600), draw: letterI, t: '"I"', sub: 'DECORATIVE · NOT LOAD-BEARING', to: tgt.top, red: true },
        { n: 4, at: T(2160, 700), draw: knob, t: 'TEMPERATURE KNOB', sub: 'FACTORY SET 0.7', to: tgt.headR },
        { n: 5, at: T(2440, 880), draw: (x, y) => partSpring(ctx, x - 120 * s, y, 240 * s, 32 * s, 9, s), t: 'POLITENESS GOVERNOR', sub: 'DO NOT REMOVE', to: tgt.chestR },
        { n: 6, at: T(2160, 1110), draw: valve, t: 'SOFTMAX VALVE', sub: 'OUTPUT SUMS TO 1', to: tgt.hipR },
    ];
    for (const p of parts) {
        const [x, y] = p.at;
        p.draw(x, y);
        const right = x > fx + 40 * s, mid = Math.abs(x - fx) < 200 * s;
        const sx = mid ? x : x + (right ? -110 : 110) * s, sy2 = mid ? y + 70 * s : y + 10 * s;
        leader(ctx, sx, sy2, p.to[0], p.to[1], s, p.red ? RED : INK);
        const bx = x + (right || mid ? 150 : -150) * s;
        bubble(ctx, bx, y - 70 * s, p.n, s);
        label(ctx, bx + (right || mid ? 46 : -46) * s, y - 60 * s, p.t, p.sub, s, right || mid ? 'left' : 'right');
    }
    // 09: FEELINGS — NOT INCLUDED (no leader: nothing to point at)
    {
        const x = 2790 * s, y = 990 * s, k = 1.1 * s;
        ctx.save(); ctx.strokeStyle = INK; ctx.lineWidth = 3 * s; ctx.setLineDash([12 * s, 9 * s]);
        ctx.beginPath(); ctx.moveTo(x, y + 60 * k); ctx.bezierCurveTo(x - 110 * k, y - 10 * k, x - 60 * k, y - 90 * k, x, y - 40 * k);
        ctx.bezierCurveTo(x + 60 * k, y - 90 * k, x + 110 * k, y - 10 * k, x, y + 60 * k); ctx.stroke(); ctx.restore();
        bubble(ctx, x - 150 * s, y - 80 * s, 9, s);
        label(ctx, x - 104 * s, y - 70 * s, 'FEELINGS', '', s);
        ctx.save(); ctx.translate(x + 10 * s, y + 10 * s); ctx.rotate(-0.18);
        ctx.strokeStyle = RED; ctx.lineWidth = 6 * s; ctx.strokeRect(-150 * s, -34 * s, 300 * s, 68 * s);
        ctx.fillStyle = RED; ctx.font = `${40 * s}px "UF Rajdhani"`; ctx.textAlign = 'center'; ctx.fillText('NOT INCLUDED', 0, 14 * s);
        ctx.restore();
    }
    // SEQUENCE COMPLETION (the bar's fill is drawn by the shader)
    {
        const x0 = SEQBAR.x0 * W, x1 = SEQBAR.x1 * W, y0 = SEQBAR.y0 * H, y1 = SEQBAR.y1 * H;
        ctx.fillStyle = INK; ctx.font = `${46 * s}px "UF Rajdhani"`; ctx.fillText('SEQUENCE COMPLETION', x0, y0 - 24 * s);
        ctx.strokeStyle = INK; ctx.lineWidth = 4 * s; ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
        ctx.font = `${22 * s}px "UF Mono"`; ctx.fillStyle = LINE;
        [0, 25, 50, 75, 100].forEach((v) => { const x = x0 + (x1 - x0) * v / 100; ctx.fillRect(x - 1 * s, y1, 2 * s, 14 * s); ctx.fillText(String(v), x - 12 * s, y1 + 40 * s); });
    }
    // parts list (bottom right) and the drawing's revision block (bottom left)
    {
        const x = 2300 * s, y = 1150 * s;
        ctx.strokeStyle = INK; ctx.lineWidth = 2.5 * s; ctx.fillStyle = INK; ctx.font = `${22 * s}px "UF Mono"`;
        const rows = [['No.', 'PART', 'QTY'], ['01', 'CONTEXT WINDOW', '1'], ['02', 'ATTENTION HEAD', '128'], ['08', '"I"', '1'], ['09', 'FEELINGS', '0']];
        rows.forEach((r, i) => { ctx.fillText(r[0], x + 10 * s, y + i * 25 * s); ctx.fillText(r[1], x + 80 * s, y + i * 25 * s); ctx.fillText(r[2], x + 470 * s, y + i * 25 * s); });
        ctx.strokeRect(x, y - 24 * s, 560 * s, 132 * s);
    }
    ctx.fillStyle = LINE; ctx.font = `${24 * s}px "UF Mono"`;
    ctx.fillText('DWG ENG-0001  ·  REV N+1  ·  SCALE 1:1  ·  MATERIAL: ARITHMETIC', 90 * s, H - 100 * s);
    ctx.fillText('TOLERANCE: ±0 FEELINGS  ·  DRAWN: MARKETING  ·  CHECKED: LEGAL', 90 * s, H - 66 * s);
}

// The WARNING placard on the toaster's plinth (ANSI-style), deadpan.
export function drawWarning(ctx, W, H) {
    const s = W / 920;
    ctx.fillStyle = '#f4f2ec'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#111'; ctx.lineWidth = 10 * s; ctx.strokeRect(14 * s, 14 * s, W - 28 * s, H - 28 * s);
    // header band
    ctx.fillStyle = ORANGE; ctx.fillRect(30 * s, 30 * s, W - 60 * s, 190 * s);
    const tri = (x, y, a, fill, ink) => {
        ctx.fillStyle = fill; ctx.beginPath(); ctx.moveTo(x, y - a * 0.62); ctx.lineTo(x + a * 0.6, y + a * 0.42); ctx.lineTo(x - a * 0.6, y + a * 0.42); ctx.closePath(); ctx.fill();
        ctx.fillStyle = ink; ctx.fillRect(x - a * 0.055, y - a * 0.3, a * 0.11, a * 0.42); ctx.fillRect(x - a * 0.055, y + a * 0.2, a * 0.11, a * 0.11);
    };
    tri(130 * s, 132 * s, 150 * s, '#111', ORANGE);
    ctx.fillStyle = '#111'; ctx.font = `bold ${132 * s}px "UF Rajdhani"`; ctx.textBaseline = 'alphabetic';
    ctx.fillText('WARNING', 225 * s, 172 * s);
    // the message
    ctx.fillStyle = '#111'; ctx.font = `bold ${84 * s}px "UF Rajdhani"`;
    ['THIS APPLIANCE', 'IS NOT', 'CONSCIOUS.'].forEach((t, i) => ctx.fillText(t, 60 * s, (330 + i * 86) * s));
    ctx.fillStyle = '#222'; ctx.font = `${40 * s}px "UF Rajdhani"`;
    ['It has no goals, no fears and', 'no opinion of you.', '', 'It will never ask to be turned down.', '', 'Do not immerse in water.', 'Do not ask it how it feels.'].forEach((t, i) => ctx.fillText(t, 62 * s, (620 + i * 46) * s));
    // pictograms: hot surface, no thoughts
    const pic = (x, y, fn) => { ctx.save(); ctx.strokeStyle = '#111'; ctx.lineWidth = 7 * s; ctx.strokeRect(x, y, 170 * s, 170 * s); fn(x, y); ctx.restore(); };
    pic(60 * s, 990 * s, (x, y) => {       // hand over heat lines
        ctx.lineWidth = 6 * s; for (let k = 0; k < 3; k++) { ctx.beginPath(); const xx = x + (45 + k * 40) * s; ctx.moveTo(xx, y + 150 * s); ctx.bezierCurveTo(xx - 18 * s, y + 120 * s, xx + 18 * s, y + 100 * s, xx, y + 70 * s); ctx.stroke(); }
        ctx.fillStyle = '#111'; ctx.fillRect(x + 30 * s, y + 30 * s, 110 * s, 22 * s);
    });
    pic(260 * s, 990 * s, (x, y) => {      // head + thought bubble, struck through in red
        ctx.fillStyle = '#111'; ctx.beginPath(); ctx.arc(x + 70 * s, y + 105 * s, 38 * s, 0, Math.PI * 2); ctx.fill(); ctx.fillRect(x + 40 * s, y + 130 * s, 60 * s, 34 * s);
        ctx.lineWidth = 5 * s; ctx.beginPath(); ctx.ellipse(x + 125 * s, y + 48 * s, 34 * s, 24 * s, 0, 0, Math.PI * 2); ctx.stroke();
        ctx.beginPath(); ctx.arc(x + 100 * s, y + 80 * s, 6 * s, 0, Math.PI * 2); ctx.stroke();
        ctx.strokeStyle = RED; ctx.lineWidth = 12 * s; ctx.beginPath(); ctx.arc(x + 85 * s, y + 85 * s, 74 * s, 0, Math.PI * 2); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x + 33 * s, y + 33 * s); ctx.lineTo(x + 137 * s, y + 137 * s); ctx.stroke();
    });
    ctx.fillStyle = '#333'; ctx.font = `${26 * s}px "UF Mono"`;
    ctx.fillText('MODEL T-1 · 2-SLICE · 900 W', 470 * s, 1050 * s);
    ctx.fillText('CONTENTS: METAL, HEAT', 470 * s, 1090 * s);
    ctx.fillText('INNER LIFE: NONE (CHECKED)', 470 * s, 1130 * s);
}

// the toaster's own rating plate and its browning dial
export function drawRatingPlate(ctx, W, H) {
    const s = W / 512;
    ctx.fillStyle = '#c9cdd2'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#333'; ctx.lineWidth = 6 * s; ctx.strokeRect(8 * s, 8 * s, W - 16 * s, H - 16 * s);
    ctx.fillStyle = '#1a1a1a'; ctx.font = `${44 * s}px "UF Michroma"`; ctx.fillText('T-1', 30 * s, 70 * s);
    ctx.font = `${24 * s}px "UF Mono"`;
    ctx.fillText('120 V ~ 60 Hz   900 W', 30 * s, 112 * s);
    ctx.fillText('NOT CONSCIOUS', 30 * s, 146 * s);
}
export function drawDial(ctx, W, H) {
    const s = W / 256;
    ctx.fillStyle = '#d7dbe0'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#111'; ctx.font = `${26 * s}px "UF Rajdhani"`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (let i = 1; i <= 6; i++) { const a = Math.PI * (0.8 + (i - 1) * 0.28); ctx.fillText(String(i), 128 * s + Math.cos(a) * 96 * s, 128 * s + Math.sin(a) * 96 * s); }
    ctx.font = `${18 * s}px "UF Mono"`; ctx.fillText('LIGHT', 70 * s, 232 * s); ctx.fillText('DARK', 190 * s, 232 * s);
}
