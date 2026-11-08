// parole_export.mjs — run the parole-in-libertà lyric layer (eidoverse/parole.js, unchanged) headless in Deno and
// export it for Blender: every group's canvas atlas as a PNG, and per frame each live sprite's pose (in the overlay
// camera's local space, which Blender's overlay camera shares: looking down -Z, +Y up) and its four parameters.
// Driven by blender/eidoblend/media/parole.py; guide: tools-guides/motion-graphics.md.
//
//   deno run -A --no-config --node-modules-dir=none --cached-only parole_export.mjs <job.json>
//
// job = { out, width, height, fov (the overlay camera's vertical degrees), timing (lines, as makeParole takes),
//         opts: { styleOverrides?, preheardDefault?, spare? }, addLines?: [spec], quotes?: [{ text, opts }] (alignWith
//         = an earlier quote's index), preheard?: [{ line, alternatives?, opts? }],
//         frames: { first, last, fps, frame0 }, spare?: { "<frame>": { x, y, r } | null }, hush?: { "<frame>": v } | v }
// Out: <out>/parole.json { F, PX, W, H, groups: [{ id, name, order, atlas, w, h, rects: [[ax, ay, cw, ch]] }],
//        frames: [{ f, live: [[gid, [[k, x, y, z, qw, qx, qy, qz, sx, sy, alpha, reveal, bright, desat], …]], …] }] }
// The pose is parole's writeGPU, verbatim in its maths: spriteOf, position (x F, y F, -depth), Euler (rx, ry, rot)
// in 'YXZ' order, scale (w sc F, h sc F).
const job = JSON.parse(await Deno.readTextFile(Deno.args[0]));
const OUT = job.out;
await Deno.mkdir(OUT, { recursive: true });
const P = await import(new URL('../../../../eidoverse/parole.js', import.meta.url).href);

const parole = await P.makeParole(null, Object.assign({}, job.opts || {}, {
    overlay: null, width: job.width, height: job.height, fov: job.fov, timing: job.timing || [],
}));
for (const spec of job.addLines || []) parole.addLine(spec);
const qh = [];
for (const q of job.quotes || []) {
    const o = Object.assign({}, q.opts || {});
    if (o.alignWith !== undefined && o.alignWith !== null) o.alignWith = qh[o.alignWith];
    qh.push(parole.quote(q.text, o));
}
for (const p of job.preheard || []) parole.preheard(p.line, p.alternatives ?? P.PREHEARD_DEFAULT, p.opts || {});

const F = parole.F, PX = parole.PX;
// parole.js's own helpers (module-private there): a sprite's centre and size from its placed text box
const rotPt = (x, y, a) => { const c = Math.cos(a), s = Math.sin(a); return [x * c - y * s, x * s + y * c]; };
function spriteOf(p) {
    const c = p.cell;
    const bx = (c.ox + (c.box ? (c.box.l + c.box.r) * 0.5 : 0)), by = (c.oy + (c.box ? (c.box.t + c.box.b) * 0.5 : 0));
    const dx = (c.cw * 0.5 - (c.box ? bx : c.cw * 0.5)) / PX, dy = -(c.ch * 0.5 - (c.box ? by : c.ch * 0.5)) / PX;
    const [ox, oy] = rotPt(dx * p.sc, dy * p.sc, p.rot);
    return { x: p.x + ox, y: p.y + oy, w: c.cw / PX, h: c.ch / PX };
}
// three's Quaternion.setFromEuler, order 'YXZ'
function quatYXZ(x, y, z) {
    const c1 = Math.cos(x / 2), c2 = Math.cos(y / 2), c3 = Math.cos(z / 2);
    const s1 = Math.sin(x / 2), s2 = Math.sin(y / 2), s3 = Math.sin(z / 2);
    return [c1 * c2 * c3 + s1 * s2 * s3,                  // w
        s1 * c2 * c3 + c1 * s2 * s3,                      // x
        c1 * s2 * c3 - s1 * c2 * s3,                      // y
        c1 * c2 * s3 - s1 * s2 * c3];                     // z
}
const r6 = (v) => Math.round(v * 1e6) / 1e6;

const groups = new Map();
const frames = [];
const { first, last, fps, frame0 = 1 } = job.frames;
const perFrame = (m, f) => (m && typeof m === 'object' ? m[String(f)] : m);
for (let f = first; f <= last; f++) {
    const t = (f - frame0) / fps;
    const sp = perFrame(job.spare, f);
    if (sp !== undefined) parole.setSpare(sp);
    const hu = perFrame(job.hush, f);
    if (hu !== undefined && hu !== null) parole.setHush(hu);
    const live = [];
    for (const { G, B, states } of parole.frameStates(t)) {
        let g = groups.get(G);
        if (!g) {
            g = { id: groups.size, name: G.name, order: G.order || 0, atlas: `atlas_${String(groups.size).padStart(3, '0')}.png`,
                w: B.atlas.w, h: B.atlas.h, rects: B.sprites.map((s) => [s.cell.ax, s.cell.ay, s.cell.cw, s.cell.ch]) };
            await Deno.writeFile(`${OUT}/${g.atlas}`, B.atlas.canvas.toBuffer('image/png'));
            groups.set(G, g);
        }
        const rows = [];
        for (let k = 0; k < B.sprites.length; k++) {
            const s = states[k];
            if (!s || s.alpha <= 0.002) continue;
            const q = spriteOf({ cell: s.p.cell, x: s.x, y: s.y, rot: s.rot, sc: s.sc });
            const d = s.depth ?? 1;
            const [qw, qx, qy, qz] = quatYXZ(s.rx || 0, s.ry || 0, s.rot);
            rows.push([k, r6(q.x * F), r6(q.y * F), r6(-d), r6(qw), r6(qx), r6(qy), r6(qz),
                r6(Math.max(1e-6, q.w * s.sc * F)), r6(Math.max(1e-6, q.h * s.sc * F)),
                r6(s.alpha), r6(s.reveal ?? 1), r6(s.bright ?? 1), r6(s.desat ?? 0)]);
        }
        live.push([g.id, rows]);
    }
    frames.push({ f, live });
}
const W = job.width, H = job.height;
await Deno.writeTextFile(`${OUT}/parole.json`, JSON.stringify({ F, PX, W, H, groups: [...groups.values()], frames }));
console.log(JSON.stringify({ out: OUT, frames: frames.length, groups: groups.size,
    sprites: [...groups.values()].reduce((a, g) => a + g.rects.length, 0) }));
Deno.exit(0);
