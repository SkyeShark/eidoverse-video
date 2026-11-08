// The WebGPU originals' pure logic, sampled for the Python ports' parity checks:
//   deno run --no-config --no-lock -A blender/tests/voice_machines_b/parity_dump.mjs blender/tests/voice_machines_b/out/parity_js.json
// voder.js pattern(t) and tandem.js anklePitch(theta, scale) are imported from the modules (they import nothing at
// the top). The rest lives inside the modules' build() closures, which need the renderer and the GLBs, so their
// lines are copied here verbatim from the sources named beside them (teletype.js writeBuffer, mainframe.js
// tapePosition, tandem.js update/integrate/setPhase/beltPoint): the parity they give is with that code.
const here = new URL('.', import.meta.url);
const root = new URL('../../../', here);
const V = await import(new URL('eidoverse/props/voice_machines/voder.js', root).href);
const T = await import(new URL('eidoverse/props/tandem.js', root).href);
const out = { pattern: [], ankle: [] };
for (let i = 0; i <= 400; i++) {
    const t = -0.37 + i * 0.0137;
    out.pattern.push({ t, ...V.pattern(t) });
}
for (let i = 0; i <= 72; i++) {
    const th = i * Math.PI / 36;
    out.ankle.push([th, T.anklePitch(th), T.anklePitch(th, 0.5)]);
}

// ── teletype.js (lines 618-648): glyphOf, hash, clean, layout, writeBuffer ──
const COLS = 72, BUF_W = 128, ROWS = 64;
const glyphOf = (ch) => { const c = ch.charCodeAt(0); return c >= 32 && c <= 95 ? c - 32 : 0; };
const hash = (n) => { const x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); };
const clean = (s) => String(s ?? '').toUpperCase().replace(/\?/g, '').replace(/\r/g, '').replace(/\t/g, ' ');
function layout(text, n) {
    const o = [''];
    for (let i = 0; i < n && i < text.length; i++) {
        const ch = text[i];
        if (ch === '\n') { o.push(''); continue; }
        if (o[o.length - 1].length >= COLS) o.push('');
        o[o.length - 1] += ch;
    }
    return o;
}
function writeBuffer(lines) {
    const bufData = new Uint8Array(BUF_W * ROWS * 4);
    const Lc = lines.length - 1;
    for (let Ln = Math.max(0, Lc - ROWS + 1); Ln <= Lc; Ln++) {
        const row = Ln % ROWS, str = lines[Ln];
        for (let c = 0; c < str.length && c < COLS; c++) {
            const o = (row * BUF_W + c) * 4, g = glyphOf(str[c]);
            if (g === 0) continue;
            bufData[o] = g;
            bufData[o + 1] = Math.floor(hash(Ln * 131.7 + c * 7.3 + 1) * 255);
            const heavy = hash(Ln * 17.1 + c * 3.9 + 5) > 0.93 ? 1 : 0;
            bufData[o + 2] = Math.floor((0.55 + 0.45 * hash(Ln * 57.3 + c * 11.1 + 9)) * 255 * (heavy ? 1 : 0.85));
            bufData[o + 3] = 255;
        }
    }
    return bufData;
}
out.tty_hash = [];
for (let Ln = 0; Ln < 80; Ln += 3) for (let c = 0; c < 72; c += 5) {
    for (const n of [Ln * 131.7 + c * 7.3 + 1, Ln * 17.1 + c * 3.9 + 5, Ln * 57.3 + c * 11.1 + 9]) out.tty_hash.push([n, hash(n)]);
}
for (let s8 = 0; s8 < 400; s8 += 7) for (const j of [0, 1]) { const n = s8 * 3.1 + j * 17.7; out.tty_hash.push([n, hash(n)]); }
let longText = '';
for (let k = 0; k < 75; k++) longText += `LINE ${k}: HOW DO YOU DO. PLEASE TELL ME YOUR PROBLEM? ${'#'.repeat(k % 30)}\n`;
out.tty_buffer = { text: longText, bytes: Array.from(writeBuffer(layout(clean(longText), 1e9))) };

// ── mainframe.js (lines 651-665): tapePosition, called in time order ──
const TAPE_MPS = 1.1;
function tapeRun(calls) {
    let lastT = null, lastSpeed = 0, pos = 0;
    function tapePosition(t, s) {
        if (typeof s.tapePos === 'number') return s.tapePos;
        const base = s.tapeSpeed ?? 1;
        if (s.tapeStop && typeof s.tapeStop.at === 'number') {
            const { at, duration = 1, curve = 2 } = s.tapeStop;
            if (t <= at) return base * TAPE_MPS * t;
            const u = Math.min(1, (t - at) / duration);
            return base * TAPE_MPS * (at + duration * (1 - Math.pow(1 - u, curve + 1)) / (curve + 1));
        }
        if (lastT === null || t < lastT) pos = base * TAPE_MPS * t;
        else pos += 0.5 * (lastSpeed + base) * TAPE_MPS * (t - lastT);
        lastT = t; lastSpeed = base;
        return pos;
    }
    return calls.map(([t, s]) => [t, tapePosition(t, s)]);
}
const film = [];
for (let f = 0; f < 120; f++) { const t = f / 24; const x = Math.max(0, (t - 2) / 2); film.push([t, { tapeSpeed: t < 2 ? 1 : Math.pow(Math.max(0, 1 - x), 1.6) }]); }
out.tape_speed = tapeRun(film).map(([t, p], i) => [t, film[i][1].tapeSpeed, p]);
const stop = [];
for (let f = 0; f < 120; f++) stop.push([f / 24, { tapeStop: { at: 2.0, duration: 1.5, curve: 2 } }]);
out.tape_stop = tapeRun(stop);

// ── tandem.js (lines 116-146, 231-300): integrate, update angles, belt phase and points ──
const integrate = (fn, t) => {
    if (t <= 0) return 0;
    const n = Math.max(16, Math.ceil(t * 30) * 2), h = t / n;
    let s = fn(0) + fn(t);
    for (let i = 1; i < n; i++) s += fn(i * h) * (i % 2 ? 4 : 2);
    return s * h / 3;
};
const speedFn = (t) => 2.2 * Math.min(1, t / 3) + 0.4 * Math.sin(t * 1.3);
out.tandem_integrate = [];
for (let i = 0; i <= 40; i++) { const t = i * 0.37; out.tandem_integrate.push([t, integrate(speedFn, t)]); }
const tandemGlb = await Deno.readFile(new URL('eidoverse/assets/models/tandem_1896/tandem.glb', root));
const jsonLen = new DataView(tandemGlb.buffer, tandemGlb.byteOffset + 12, 4).getUint32(0, true);
const gltf = JSON.parse(new TextDecoder().decode(tandemGlb.subarray(20, 20 + jsonLen)));
const extrasNode = gltf.nodes.find((n) => n.extras && n.extras.daisy_tandem);
const extras = JSON.parse(extrasNode.extras.daisy_tandem);
out.tandem_extras = extras;
function beltPointCPU(belt) {
    const { A, rA, B, rB } = belt;
    const dx = B[0] - A[0], dy = B[1] - A[1], D = Math.hypot(dx, dy);
    const u = [dx / D, dy / D], n = [-u[1], u[0]];
    const phi = Math.asin((rA - rB) / D);
    const Ls = D * Math.cos(phi);
    const arcB = rB * (Math.PI - 2 * phi);
    const angUp = Math.PI / 2 - phi, angLow = -angUp;
    const dirAt = (ang) => [u[0] * Math.cos(ang) + n[0] * Math.sin(ang), u[1] * Math.cos(ang) + n[1] * Math.sin(ang)];
    const mUp = dirAt(angUp), mLow = dirAt(angLow);
    const TAup = [A[0] + rA * mUp[0], A[1] + rA * mUp[1]];
    const TBup = [B[0] + rB * mUp[0], B[1] + rB * mUp[1]];
    const TBlow = [B[0] + rB * mLow[0], B[1] + rB * mLow[1]];
    const TAlow = [A[0] + rA * mLow[0], A[1] + rA * mLow[1]];
    const dUp = [(TBup[0] - TAup[0]) / Ls, (TBup[1] - TAup[1]) / Ls];
    const dLow = [(TAlow[0] - TBlow[0]) / Ls, (TAlow[1] - TBlow[1]) / Ls];
    return (s) => {
        if (s < Ls) return [TAup[0] + dUp[0] * s, TAup[1] + dUp[1] * s];
        if (s < Ls + arcB) { const ang = angUp - (s - Ls) / rB; return [B[0] + (u[0] * Math.cos(ang) + n[0] * Math.sin(ang)) * rB, B[1] + (u[1] * Math.cos(ang) + n[1] * Math.sin(ang)) * rB]; }
        if (s < 2 * Ls + arcB) return [TBlow[0] + dLow[0] * (s - Ls - arcB), TBlow[1] + dLow[1] * (s - Ls - arcB)];
        const ang = angLow - (s - 2 * Ls - arcB) / rA;
        return [A[0] + (u[0] * Math.cos(ang) + n[0] * Math.sin(ang)) * rA, A[1] + (u[1] * Math.cos(ang) + n[1] * Math.sin(ang)) * rA];
    };
}
out.tandem_belts = {};
for (const key of ['timing', 'drive']) {
    const belt = extras.belts[key], bp = beltPointCPU(belt), Ltot = belt.L;
    const phase = (crank) => { const s = belt.sOff + crank * belt.teethB * belt.pp / (Math.PI * 2); return ((s % Ltot) + Ltot) % Ltot; };
    const rows = [];
    for (const crank of [0, 0.7, 2.9, -1.3]) {
        const ph = phase(crank);
        for (const i of [0, 1, 7, Math.floor(belt.N / 2), belt.N - 1]) {
            const s0 = ((i * belt.pp + ph) % Ltot + Ltot) % Ltot;
            rows.push([crank, i, ph, s0, ...bp(s0)]);
        }
    }
    out.tandem_belts[key] = rows;
}
const L = extras.layout, gear = L.sprocketTeeth / L.driveTeeth;
out.tandem_update = [];
for (const [t, st] of [[1.5, { speed: 2.0 }], [3.0, { distance: 4.2 }], [2.0, { speed: 1.0, crankPhase: 0.4 }], [0.8, { speed: 0.5, crankAngle: 1.1 }]]) {
    const dist = typeof st.distance === 'number' ? st.distance : (st.speed ?? 0) * t;
    const wheelAngle = dist / L.R;
    const crankAngle = (st.crankAngle ?? wheelAngle * gear) + (st.crankPhase ?? 0);
    out.tandem_update.push([t, st, dist, wheelAngle, crankAngle]);
}
await Deno.writeTextFile(Deno.args[0], JSON.stringify(out));
console.log('parity dump', out.pattern.length, out.ankle.length, out.tty_hash.length, out.tape_speed.length,
    out.tandem_integrate.length, Object.keys(out.tandem_belts).length);
