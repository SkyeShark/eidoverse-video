// ocean/faces_atlas.js — the drawn faces of the ocean: an N x N atlas of gentle brush-line portraits,
// eyes closed, every one a different person (age, hair, glasses, beards, scarves, freckles...).
// Stylized and non-identifiable by construction: they share one feature LAYOUT (the layout the sea's
// analytic relief is sculpted from), so the drawing and the relief sit on each other.
//
// Face-cell coordinates: x, y in [-0.5, 0.5], +y up (forehead); eyes y≈0.055, mouth y≈-0.20.
// Channels: R = crisp line art, G = soft halo of the lines (blurred), B = face fill mask.
//
//   drawFaceAtlas(makeCanvas, { n: 8, cell: 256, seed }) -> canvas (RGBA)

import { rng } from './util.js';

export const LAYOUT = {
    eyeX: 0.125, eyeY: 0.055, browY: 0.135, noseTipY: -0.075, mouthY: -0.200, chinY: -0.365,
    headA: 0.30, headB: 0.42, headCY: 0.02,
};

// Catmull-Rom through control points -> dense polyline
function sampleCurve(pts, per = 10) {
    if (pts.length < 3) {
        const out = [];
        for (let i = 0; i <= per; i++) out.push([pts[0][0] + (pts[1][0] - pts[0][0]) * i / per, pts[0][1] + (pts[1][1] - pts[0][1]) * i / per]);
        return out;
    }
    const P = [pts[0], ...pts, pts[pts.length - 1]];
    const out = [];
    for (let i = 1; i < P.length - 2; i++) {
        const [p0, p1, p2, p3] = [P[i - 1], P[i], P[i + 1], P[i + 2]];
        for (let j = 0; j < per; j++) {
            const t = j / per, t2 = t * t, t3 = t2 * t;
            const f = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
            out.push([f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1])]);
        }
    }
    out.push(pts[pts.length - 1]);
    return out;
}

export function drawFaceAtlas(makeCanvas, { n = 8, cell = 256, seed = 11 } = {}) {
    const S = cell, N = n;
    const line = makeCanvas(S * N, S * N);
    const halo = makeCanvas(S * N, S * N);
    const fill = makeCanvas(S * N, S * N);
    const gl = line.getContext('2d'), gf = fill.getContext('2d');
    for (const g of [gl, gf]) { g.fillStyle = '#000'; g.fillRect(0, 0, S * N, S * N); }
    const R = rng(seed);
    const pick = (a) => a[Math.floor(R() * a.length)];
    const jit = (a) => (R() - 0.5) * 2 * a;
    const L = LAYOUT;
    const HAIRS = ['long', 'wavy', 'short', 'curly', 'bun', 'bald', 'braids', 'scarf', 'bangs', 'side', 'pony', 'locs'];

    for (let k = 0; k < N * N; k++) {
        const ox = (k % N) * S, oy = Math.floor(k / N) * S;
        const X = (x) => ox + (x + 0.5) * S, Y = (y) => oy + (0.5 - y) * S;
        const g = gl;
        g.save();
        g.beginPath(); g.rect(ox + 3, oy + 3, S - 6, S - 6); g.clip();
        g.strokeStyle = '#fff'; g.fillStyle = '#fff';
        g.lineCap = 'round'; g.lineJoin = 'round';
        const LW = S * 0.021;
        // a tapered brush stroke: thick in the middle, fine at both ends (ink, not wire)
        const brush = (pts, m = 1, t0 = 0.22, t1 = 0.22) => {
            const s = sampleCurve(pts, 9);
            for (let i = 0; i < s.length - 1; i++) {
                const u = (i + 0.5) / (s.length - 1);
                const taper = Math.min(1, u / Math.max(0.01, t0), (1 - u) / Math.max(0.01, t1));
                g.lineWidth = LW * m * (0.28 + 0.72 * Math.sin(Math.min(1, taper) * Math.PI / 2));
                g.beginPath(); g.moveTo(X(s[i][0]), Y(s[i][1])); g.lineTo(X(s[i + 1][0]), Y(s[i + 1][1])); g.stroke();
            }
        };
        const dot = (x, y, r) => { g.beginPath(); g.arc(X(x), Y(y), r * S, 0, Math.PI * 2); g.fill(); };
        const oval = (x, y, rx, ry, m = 0.7) => {
            const pts = [];
            for (let i = 0; i <= 16; i++) { const a = i / 16 * Math.PI * 2; pts.push([x + Math.cos(a) * rx, y + Math.sin(a) * ry]); }
            brush(pts, m, 0.02, 0.02);
        };

        // ---- who: every face its own person
        const age = pick(['child', 'young', 'young', 'adult', 'adult', 'adult', 'elder', 'elder']);
        const hair = HAIRS[(k * 7 + Math.floor(R() * 3)) % HAIRS.length];
        const fw = age === 'child' ? 1.05 : 0.9 + R() * 0.13;            // face width
        const chin = age === 'child' ? 0.85 : 0.8 + R() * 0.35;          // chin pointiness
        const turn = jit(0.035);                                          // a slight three-quarter turn
        const smile = 0.12 + R() * 0.6;
        const glasses = age !== 'child' && R() < 0.15;
        const beard = (age === 'adult' || age === 'elder') && R() < 0.18;
        const moust = !beard && (age === 'adult' || age === 'elder') && R() < 0.1;
        const freckles = R() < 0.16;
        const earring = R() < 0.18;
        const lashes = R() < 0.65;
        const lost = R() < 0.5 ? -1 : 1;                                   // the side whose contour breaks

        // ---- contour: cheek-jaw-chin; one side breaks at the cheek (lost edge), the far side of a turn slims
        const cx = L.headA * fw, top = 0.17;
        const sideW = (s) => cx * (1 - s * turn * 1.6);
        for (const s of [-1, 1]) {
            const w = sideW(s);
            const pts = [[s * w * 0.96, top], [s * w * 1.02, 0.03], [s * w * 0.9, -0.14], [s * w * (0.6 + 0.12 * (1 - chin)), -0.285],
                [s * 0.1 * chin + turn * 0.5, L.chinY + 0.004], [turn * 0.6, L.chinY]];
            if (s === lost) { brush(pts.slice(0, 2), 0.9, 0.3, 0.6); brush(pts.slice(2), 1.0, 0.4, 0.15); }
            else brush(pts, 1.05, 0.12, 0.15);
        }
        if (R() < 0.55) {                                                 // neck
            brush([[-0.1 + turn, -0.33], [-0.11 + turn, -0.42], [-0.12 + turn, -0.47]], 0.75, 0.3, 0.6);
            brush([[0.1 + turn, -0.33], [0.105 + turn, -0.42], [0.11 + turn, -0.47]], 0.75, 0.3, 0.6);
        }

        // ---- closed eyes: the lid line bows down, fine lashes beneath
        for (const s of [-1, 1]) {
            const ex = s * L.eyeX * (0.96 + 0.04 * fw) + turn * (s === Math.sign(turn) ? 0.6 : 1.2), ey = L.eyeY + jit(0.004);
            const w = (age === 'child' ? 0.058 : 0.052) * (s * turn > 0 ? 0.9 : 1.0);
            brush([[ex - s * w, ey + 0.007], [ex - s * w * 0.35, ey - 0.019], [ex + s * w * 0.4, ey - 0.017], [ex + s * w, ey + 0.003]], 1.0, 0.25, 0.3);
            if (lashes) for (let j = 0; j < 3; j++) {
                const t = 0.3 + j * 0.22, lx = ex - s * w + s * 2 * w * t;
                const ly = ey - 0.019 * Math.sin(t * Math.PI) - 0.004;
                brush([[lx, ly], [lx + s * 0.007 * (j - 0.5), ly - 0.018]], 0.42, 0.1, 0.9);
            }
            if (age === 'elder') brush([[ex + s * 0.068, ey + 0.012], [ex + s * 0.092, ey - 0.002]], 0.38, 0.2, 0.8);
            const bh = L.browY + jit(0.008), arch = 0.008 + R() * 0.02;       // brows
            brush([[ex - s * 0.066, bh - 0.01], [ex - s * 0.01, bh + arch], [ex + s * 0.07, bh - 0.006]],
                age === 'child' ? 0.55 : 0.75 + R() * 0.5, 0.15, 0.6);
        }
        if (glasses) {
            oval(-L.eyeX + turn, L.eyeY, 0.072, 0.058, 0.62);
            oval(L.eyeX + turn, L.eyeY, 0.072, 0.058, 0.62);
            brush([[-L.eyeX + turn + 0.072, L.eyeY + 0.012], [turn, L.eyeY + 0.026], [L.eyeX + turn - 0.072, L.eyeY + 0.012]], 0.6, 0.05, 0.05);
        }

        // ---- nose: one line down the side, curling into the nostril
        const ns = turn !== 0 ? Math.sign(turn) : 1;
        brush([[ns * 0.03 + turn, 0.105], [ns * 0.034 + turn * 1.3, 0.0], [ns * 0.042 + turn * 1.6, -0.058],
            [ns * 0.03 + turn * 1.6, -0.09], [-ns * 0.006 + turn * 1.5, -0.096]], 0.95, 0.35, 0.15);
        if (R() < 0.6) brush([[-ns * 0.028 + turn * 1.4, -0.086], [-ns * 0.043 + turn * 1.4, -0.094]], 0.55, 0.3, 0.3);

        // ---- mouth: a soft closed smile, a separate small lower-lip stroke
        const my = L.mouthY, lift = 0.01 + smile * 0.022, mx = turn * 1.2;
        brush([[mx - 0.078, my + lift], [mx - 0.03, my - 0.004], [mx + 0.03, my - 0.004], [mx + 0.078, my + lift]], 0.95, 0.3, 0.3);
        if (R() < 0.65) brush([[mx - 0.03, my - 0.042], [mx, my - 0.049], [mx + 0.03, my - 0.042]], 0.55, 0.35, 0.35);

        // ---- facial hair, freckles, earrings, age
        if (beard) for (let j = 0; j < 16; j++) {
            const t = j / 15, s = t < 0.5 ? -1 : 1, u = Math.abs(t - 0.5) * 2;
            const bx = s * u * cx * 0.86 + turn, by = -0.21 - (1 - u) * 0.16 - u * 0.05;
            brush([[bx, by], [bx * 1.04, by - 0.04]], 0.5, 0.2, 0.8);
        }
        if (beard || moust) brush([[mx - 0.07, my + 0.026], [mx, my + 0.037], [mx + 0.07, my + 0.026]], 1.15, 0.3, 0.3);
        if (freckles) for (let j = 0; j < 12; j++) { const s = j % 2 ? 1 : -1; dot(s * (0.1 + R() * 0.08) + turn, -0.02 - R() * 0.06, 0.0045); }
        if (earring) { oval(-cx - 0.018, -0.07, 0.012, 0.014, 0.5); oval(cx + 0.018, -0.07, 0.012, 0.014, 0.5); }
        if (age === 'elder') {
            brush([[-0.09, 0.225], [0, 0.232], [0.09, 0.222]], 0.35, 0.3, 0.3);
            brush([[mx - 0.066, my + 0.065], [mx - 0.086, my + 0.012]], 0.38, 0.3, 0.5);
            brush([[mx + 0.066, my + 0.065], [mx + 0.086, my + 0.012]], 0.38, 0.3, 0.5);
        }

        // ---- hair: flowing tapered strokes framing the face
        const crown = 0.43 + jit(0.01), hw = cx + 0.035;
        const flow = (s, x0, y0, len, sway, m = 0.8, curl = 0) => {        // one strand from the crown, down one side
            const pts = [[x0, y0]];
            for (let q = 1; q <= 5; q++) {
                const f = q / 5;
                const x = s * (Math.abs(x0) + (hw + 0.035 - Math.abs(x0)) * Math.min(1, f * 2.2) + f * 0.035) + Math.sin(f * 5.5 + sway) * 0.02 * (1 + curl);
                pts.push([x, y0 - (y0 - len) * f]);
            }
            brush(pts, m, 0.15, 0.5);
        };
        const crownArc = (m = 1) => brush([[-hw, 0.16], [-hw * 0.95, 0.31], [-0.1, crown], [0.1, crown], [hw * 0.95, 0.31], [hw, 0.16]], m, 0.2, 0.2);
        const earC = (s) => brush([[s * (cx + 0.004), 0.07], [s * (cx + 0.034), 0.05], [s * (cx + 0.03), -0.015], [s * (cx + 0.005), -0.032]], 0.65, 0.2, 0.3);
        switch (hair) {
            case 'long': case 'wavy': {
                const sw = hair === 'wavy' ? 1.6 : 0.3;
                crownArc(0.9);
                brush([[0.03, crown - 0.01], [-0.06, 0.34], [-0.18, 0.27], [-hw + 0.02, 0.15]], 0.85, 0.2, 0.6);   // parting sweep
                for (const s of [-1, 1]) for (let j = 0; j < 3; j++) flow(s, s * (0.06 + j * 0.07), crown - 0.02 - j * 0.03, -0.3 - j * 0.05 - R() * 0.1, R() * 6, 0.8 - j * 0.12, sw);
                break;
            }
            case 'locs': {
                crownArc(0.9);
                for (const s of [-1, 1]) for (let j = 0; j < 4; j++) {
                    const x0 = s * (hw - 0.02 + j * 0.02);
                    brush([[x0, 0.25 - j * 0.02], [x0 + s * 0.02, 0.05 - j * 0.02], [x0 + s * 0.015, -0.2 - j * 0.03]], 0.7, 0.1, 0.4);
                }
                break;
            }
            case 'pony': {
                crownArc(0.95);
                brush([[-0.02, crown - 0.01], [-0.12, 0.31], [-hw + 0.02, 0.16]], 0.8, 0.2, 0.6);
                brush([[hw - 0.01, 0.33], [hw + 0.07, 0.31], [hw + 0.11, 0.12], [hw + 0.09, -0.12], [hw + 0.05, -0.25]], 1.0, 0.1, 0.6);
                break;
            }
            case 'short': case 'side': {
                brush([[-hw, 0.12], [-hw * 0.98, 0.3], [-0.05, crown], [hw * 0.98, 0.3], [hw, 0.12]], 1.0, 0.15, 0.15);
                if (hair === 'side') brush([[-0.16, 0.39], [0.02, 0.35], [0.18, 0.3], [hw - 0.02, 0.2]], 0.8, 0.2, 0.6);
                else brush([[-0.2, 0.33], [-0.05, 0.3], [0.12, 0.32]], 0.6, 0.3, 0.5);
                earC(-1); earC(1);
                break;
            }
            case 'curly': {
                for (let j = 0; j < 22; j++) {
                    const a = Math.PI * (0.02 + 0.96 * j / 21), rr = 0.34 + R() * 0.05;
                    const x = Math.cos(a) * (hw + 0.07), y = 0.1 + Math.sin(a) * rr;
                    const r0 = 0.024 + R() * 0.012, a0 = R() * 6;
                    const pts = [];
                    for (let q = 0; q <= 10; q++) { const b = a0 + q / 10 * Math.PI * 1.5; pts.push([x + Math.cos(b) * r0, y + Math.sin(b) * r0]); }
                    brush(pts, 0.6, 0.2, 0.3);
                }
                brush([[-hw + 0.03, 0.2], [0, 0.3], [hw - 0.03, 0.2]], 0.55, 0.3, 0.3);
                break;
            }
            case 'bun': {
                crownArc(0.95);
                oval(0.0, crown + 0.035, 0.07, 0.048, 0.9);
                brush([[-0.18, 0.28], [-0.05, 0.33], [0.1, 0.32]], 0.5, 0.3, 0.5);
                break;
            }
            case 'bald': {
                brush([[-hw, 0.12], [-hw * 0.96, 0.3], [0, crown - 0.015], [hw * 0.96, 0.3], [hw, 0.12]], 1.0, 0.15, 0.15);
                earC(-1); earC(1);
                break;
            }
            case 'braids': {
                crownArc(0.9);
                brush([[0, crown - 0.01], [0, 0.3]], 0.5, 0.2, 0.2);
                for (const s of [-1, 1]) {                                   // a herringbone plait down each side
                    const xx = s * (hw + 0.03);
                    brush([[xx - 0.03, 0.16], [xx - 0.032, -0.36]], 0.45, 0.1, 0.3);
                    brush([[xx + 0.03, 0.16], [xx + 0.028, -0.36]], 0.45, 0.1, 0.3);
                    for (let q = 0; q < 8; q++) {
                        const yy = 0.14 - q * 0.062;
                        brush([[xx - 0.028, yy + 0.022], [xx, yy - 0.012]], 0.55, 0.3, 0.3);
                        brush([[xx + 0.028, yy + 0.022], [xx, yy - 0.012]], 0.55, 0.3, 0.3);
                    }
                    brush([[xx - 0.012, -0.37], [xx, -0.43], [xx + 0.012, -0.37]], 0.5, 0.2, 0.2);
                }
                break;
            }
            case 'scarf': {
                brush([[-hw - 0.045, -0.08], [-hw - 0.05, 0.24], [0, crown + 0.03], [hw + 0.05, 0.24], [hw + 0.045, -0.08]], 1.1, 0.1, 0.1);
                brush([[-hw + 0.01, 0.2], [0, 0.305], [hw - 0.01, 0.2]], 0.75, 0.2, 0.2);
                brush([[-hw - 0.045, -0.08], [-0.2, -0.38], [0, -0.44], [0.2, -0.38], [hw + 0.045, -0.08]], 0.9, 0.1, 0.1);
                brush([[-0.12, 0.38], [0.02, 0.33], [0.16, 0.36]], 0.4, 0.3, 0.3);
                break;
            }
            case 'bangs': {
                crownArc(0.95);
                for (let j = 0; j < 6; j++) {
                    const x0 = -hw + 0.04 + j * (2 * hw - 0.08) / 5;
                    brush([[x0 + 0.02, 0.35 - Math.abs(j - 2.5) * 0.02], [x0, 0.27], [x0 - 0.012, 0.22]], 0.6, 0.2, 0.7);
                }
                for (const s of [-1, 1]) brush([[s * hw, 0.25], [s * (hw + 0.03), 0.02], [s * (hw + 0.02), -0.18]], 0.8, 0.2, 0.6);
                break;
            }
        }
        g.restore();

        // ---- fill mask (soft face oval) for a faint inner glow
        const ff = gf;
        const grd = ff.createRadialGradient(X(0), Y(0), 0, X(0), Y(0), S * 0.4);
        grd.addColorStop(0, 'rgba(255,255,255,0.9)'); grd.addColorStop(0.7, 'rgba(255,255,255,0.35)'); grd.addColorStop(1, 'rgba(255,255,255,0)');
        ff.save();
        ff.translate(X(0), Y(L.headCY));
        ff.scale(cx / 0.4, L.headB / 0.4);
        ff.translate(-X(0), -Y(L.headCY));
        ff.fillStyle = grd; ff.beginPath(); ff.arc(X(0), Y(L.headCY), S * 0.4, 0, Math.PI * 2); ff.fill();
        ff.restore();
    }

    // halo: the line art blurred (napi canvas supports ctx.filter); draw the NATIVE canvas under a shim
    const gh = halo.getContext('2d');
    gh.fillStyle = '#000'; gh.fillRect(0, 0, S * N, S * N);
    gh.filter = `blur(${Math.round(S * 0.022)}px)`;
    gh.drawImage(line._napi ?? line, 0, 0);
    gh.filter = 'none';

    // pack R = line, G = halo, B = fill, A = 255 straight into texture rows (bottom row first), no extra canvas
    const W = S * N;
    const a = gl.getImageData(0, 0, W, W).data, b = gh.getImageData(0, 0, W, W).data, c = gf.getImageData(0, 0, W, W).data;
    const data = new Uint8Array(W * W * 4);
    for (let y = 0; y < W; y++) {
        const src = y * W * 4, dst = (W - 1 - y) * W * 4;
        for (let x = 0; x < W * 4; x += 4) {
            data[dst + x] = a[src + x]; data[dst + x + 1] = Math.min(255, b[src + x] * 1.6); data[dst + x + 2] = c[src + x]; data[dst + x + 3] = 255;
        }
    }
    return { data, w: W, h: W };
}
