// eidoverse/sets/town/kit.js — what stands on a roof, what a room held, and what a strike leaves on the ground; each
// function writes into a mesh builder (mb.js) at a place. Metres, the town's frame (+Z up).
//
// Each piece is built as the thing is made: a tank is a moulded shell with its ribs and its lid, standing on a stand of
// angle iron with a brace on every side; a cooler is a pan, four posts, a lid and three pads, with its duct going into
// the roof; washing hangs folded over a slack line between two posts; an iron bed, a table and plastic chairs, a shade
// on four posts, a solar heater, an aerial, blocks stacked for the storey to come.
// RUBBLE: a heap is a slumped mound at the angle loose stuff lies at, with its pieces ON it: many small, few large (a
// power law), blocks that came out of the walls whole, shards of slab lying flat on the slope, the biggest pieces low;
// and a thin field of small pieces thrown past its foot.
import { V, M4, place, catenary } from './mb.js';

export const CLOTH = ['cloth0', 'cloth0', 'cloth1', 'cloth2', 'cloth3', 'cloth4', 'cloth5', 'cloth6', 'cloth7', 'cloth8'];

export function smooth(x) {
    x = Math.min(1.0, Math.max(0.0, x));
    return x * x * (3.0 - 2.0 * x);
}

// ================================================================================================ rubble
// one broken piece about s across, lying at c as it fell: a lump of concrete, a hollow block out of a wall (0.4 x 0.2
// x 0.2, or half of one), a shard of slab
export function chunk(b, rng, c, s, m, kind = 'lump', rz = null) {
    let hx, hy, hz, jit;
    if (kind === 'block') { hx = 0.2 * rng.choice([1.0, 1.0, 0.5]); hy = 0.1; hz = 0.1; jit = 0.06; }
    else if (kind === 'shard') { hx = s / 2.0; hy = s * rng.uniform(0.28, 0.45); hz = Math.min(0.1, s * 0.16); jit = 0.22; }
    else { hx = s / 2.0; hy = s * rng.uniform(0.3, 0.5); hz = s * rng.uniform(0.2, 0.4); jit = 0.32; }
    const a = rz === null ? rng.uniform(0.0, 6.283) : rz;
    const M = place(c, a, rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5));
    const p = [];
    for (const [sx, sy, sz] of [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]]) {
        const x = hx * (sx + rng.uniform(-jit, jit) * 2.0);
        const y = hy * (sy + rng.uniform(-jit, jit) * 2.0);
        const z = hz * (sz + rng.uniform(-jit, jit) * 2.0);
        p.push(M4.apply(M, [x, y, z]));
    }
    b.hexa(p, m);
}

// a broken piece of slab's outline about w x d, counter-clockwise: some edges still the straight edges it was cast
// with, the others bitten in unevenly, and where two broken edges meet the corner is gone
export function ragged(rng, w, d, n = 8, jit = 0.28) {
    const hw = w / 2.0, hd = d / 2.0;
    const C = [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]];
    const broken = [0, 1, 2, 3].map(() => rng.random() < 0.62);
    if (!broken.some(Boolean)) broken[rng.randrange(4)] = true;
    const out = [];
    for (let k = 0; k < 4; k++) {
        const a = C[k], c = C[(k + 1) % 4];
        if (broken[k] && broken[(k + 3) % 4]) {
            const f = rng.uniform(0.12, 0.4);
            const g = rng.uniform(0.0, 0.2);
            out.push([a[0] * (1.0 - f), a[1] * (1.0 - g)]);
        } else out.push(a);
        if (broken[k]) {
            const m = rng.randrange(1, 4);
            for (let q = 1; q <= m; q++) {
                const t = (q + rng.uniform(-0.3, 0.3)) / (m + 1);
                const bite = rng.uniform(0.03, jit);
                out.push([(a[0] + (c[0] - a[0]) * t) * (1.0 - bite), (a[1] + (c[1] - a[1]) * t) * (1.0 - bite)]);
            }
        }
    }
    return out;
}

// a piece of floor or wall lying where it came down (or leaning): top is what was its face
export function slab_piece(b, rng, c, w, d, tilt, top, { side = 'concrete_broken', bottom = 'ceiling', thick = 0.2, rz = null, rx = null } = {}) {
    const a = rz === null ? rng.uniform(0.0, 6.283) : rz;
    const x = rx === null ? rng.uniform(-tilt, tilt) : rx;
    const M = place(c, a, x, rng.uniform(-tilt, tilt) * 0.6);
    b.plate(ragged(rng, w, d), M, thick, top, side, bottom);
    return M;
}

// what came down, lying as loose stuff lies. rx, ry: its half-widths; h: its height; paints: the colours its plaster
// was; clip: (x0, y0, x1, y1) nothing may lie outside (a floor's edge); over: how far a piece may hang over that edge
export function heap(b, rng, cx, cy, rx, ry, h, z0 = 0.0, { pieces = null, plates = 0, paints = [], clip = null, field = true, m = 'rubble', plate_top = 'floor', over = 0.0 } = {}) {
    const nseg = 20, nring = 6;
    const ph = [0, 1, 2, 3, 4].map(() => rng.uniform(0.0, 6.283));
    const R = (th) => {
        const e = 1.0 / Math.sqrt((Math.cos(th) / rx) ** 2 + (Math.sin(th) / ry) ** 2);
        return e * (1.0 + 0.20 * Math.sin(2.0 * th + ph[0]) + 0.12 * Math.sin(3.0 * th + ph[1]) + 0.07 * Math.sin(5.0 * th + ph[2]));
    };
    const Hh = (rho, th) => h * (1.0 - smooth(rho)) ** 1.1 * (1.0 + 0.22 * Math.sin(3.0 * th + ph[3]) * rho + 0.12 * Math.sin(4.0 * th + ph[4]) * rho);
    const inside = (x, y, pad = 0.0) => clip === null || (clip[0] + pad <= x && x <= clip[2] - pad && clip[1] + pad <= y && y <= clip[3] - pad);
    const clamp = (x, y) => (clip === null ? [x, y] : [Math.min(Math.max(x, clip[0] + 0.02), clip[2] - 0.02), Math.min(Math.max(y, clip[1] + 0.02), clip[3] - 0.02)]);
    const P = [];
    for (let q = nring; q >= 0; q--) {                               // from its foot in to its top
        const rho = Math.max(q / nring, 0.06);
        const row = [];
        for (let k = 0; k < nseg; k++) {
            const th = 2.0 * Math.PI * k / nseg;
            const r = R(th) * rho;
            const [x, y] = clamp(cx + r * Math.cos(th), cy + r * Math.sin(th));
            const z = z0 + Hh(rho, th) + ((0 < q && q < nring) ? rng.uniform(-0.07, 0.07) * Math.sqrt(h) : 0.0) - (q === nring ? 0.03 : 0.0);
            const jx = rng.uniform(-0.05, 0.05) * (q < nring ? 1 : 0);
            const jy = rng.uniform(-0.05, 0.05) * (q < nring ? 1 : 0);
            row.push([x + jx, y + jy, z]);
        }
        P.push(row);
    }
    const base = b.grid(P, m, { smooth: true, wrap_u: true });
    b.face([...Array(nseg).keys()].map((k) => base + nring * nseg + k), m, true);
    const n = pieces !== null ? pieces : Math.trunc(14 + 7.0 * rx * ry);
    const kinds = ['lump', 'lump', 'lump', 'block', 'block', 'shard', 'shard'];
    for (let i = 0; i < n; i++) {
        const th = rng.uniform(0.0, 6.283);
        const s = Math.min(1.15, 0.16 * rng.random() ** -0.55);      // many small, few large
        const rho = Math.min(1.2, rng.uniform(0.1, 1.15) ** 0.75 + 0.25 * Math.max(0.0, s - 0.35));
        const r = R(th) * rho;
        const x = cx + r * Math.cos(th), y = cy + r * Math.sin(th);
        if (!inside(x, y, Math.max(0.0, s * 0.5 - over))) continue;
        const kd = rng.choice(kinds);
        let mm;
        if (paints.length && kd !== 'block' && rng.random() < 0.22) mm = rng.choice(paints);
        else mm = kd === 'block' ? 'block' : rng.choice(['rubble', 'concrete', 'concrete_broken']);
        chunk(b, rng, [x, y, z0 + Hh(Math.min(rho, 1.0), th) + s * 0.14], s, mm, kd);
    }
    for (let i = 0; i < plates; i++) {                               // shards of slab, flat on the slope
        const th = rng.uniform(0.0, 6.283);
        const rho = rng.uniform(0.15, 0.75);
        const r = R(th) * rho;
        const x = cx + r * Math.cos(th), y = cy + r * Math.sin(th);
        const w = rng.uniform(1.1, Math.min(3.4, 0.9 * (rx + ry)));
        if (!inside(x, y, w * 0.5)) continue;
        const slope = Math.atan2(h, 0.7 * (rx + ry));
        const M = place([x, y, z0 + Hh(rho, th) + 0.16], th, 0.0, slope * rng.uniform(0.5, 1.3) + rng.uniform(-0.15, 0.15));
        const out = ragged(rng, w, w * rng.uniform(0.55, 0.9));
        const tm = (paints.length && rng.random() < 0.4) ? rng.choice(paints) : plate_top;
        b.plate(out, M, 0.2, tm, 'concrete_broken', 'ceiling');
    }
    if (field && clip === null) {                                    // thrown past its foot: small, thinning out
        for (let i = 0; i < Math.trunc(n / 2); i++) {
            const th = rng.uniform(0.0, 6.283);
            const r = R(th) * (1.0 + rng.random() ** 1.6 * 1.3);
            const s = rng.uniform(0.1, 0.32);
            const mm = rng.choice(['rubble', 'concrete', 'block']);
            chunk(b, rng, [cx + r * Math.cos(th), cy + r * Math.sin(th), z0 + s * 0.12], s, mm, rng.choice(['lump', 'block', 'shard']));
        }
    }
}

// ================================================================================================ on the roof
// a stand of angle iron: four legs, a frame round their heads, slats across, a brace up each side
export function stand(b, x, y, z, w, d, h, m = 'steel_dark') {
    const L = 0.05;
    const c = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([sx, sy]) => [x + sx * w / 2.0, y + sy * d / 2.0]);
    for (const [px, py] of c) {
        b.beam([px, py, z], [px, py, z + h], L, L, m, { up: [1.0, 0.0, 0.0] });
        b.box([px - 0.07, py - 0.07, z], [px + 0.07, py + 0.07, z + 0.012], m, { skip: 'z-' });
    }
    for (let k = 0; k < 4; k++) {
        const [ax, ay] = c[k], [bx, by] = c[(k + 1) % 4];
        b.beam([ax, ay, z + h - L / 2.0], [bx, by, z + h - L / 2.0], L, L, m);
        if (h > 0.5) b.beam([ax, ay, z + 0.1], [bx, by, z + h - 0.1], 0.012, 0.04, m);
    }
    for (const q of [0.25, 0.5, 0.75]) b.beam([x - w / 2.0 + w * q, y - d / 2.0, z + h - 0.015], [x - w / 2.0 + w * q, y + d / 2.0, z + h - 0.015], 0.05, 0.03, m);
}

// a moulded water tank, a thousand litres: two ribs pressed round it, a shoulder, a screwed lid
export function tank_poly(b, x, y, z, m = 'tank_white') {
    b.lathe([[0.52, 0.0], [0.55, 0.04], [0.55, 0.38], [0.53, 0.41], [0.55, 0.44], [0.55, 0.80], [0.53, 0.83], [0.55, 0.86], [0.55, 1.06], [0.46, 1.17], [0.25, 1.23]], [x, y, z], m, { n: 14 });
    b.lathe([[0.25, 1.23], [0.25, 1.28], [0.21, 1.295], [0.02, 1.30]], [x, y, z], 'tank_cap', { n: 14 });
    return 1.30;
}

// a galvanised tank of pressed panels: its rim, its hatch, the pipe in at the top
export function tank_steel(b, rng, x, y, z, rz = 0.0, m = 'zinc') {
    const M = place([x, y, z], rz);
    const s = rng.choice([0.5, 0.6, 0.6]), h = rng.choice([0.9, 1.0, 1.2]);
    b.box([-s, -s, 0.0], [s, s, h], m, { skip: 'z-', M });
    for (const [sx, sy, u] of [[-1, 0, [0, 1]], [1, 0, [0, 1]], [0, -1, [1, 0]], [0, 1, [1, 0]]]) {
        const a = [sx * s - u[0] * s, sy * s - u[1] * s, h];
        const c = [sx * s + u[0] * s, sy * s + u[1] * s, h];
        b.beam(M4.apply(M, a), M4.apply(M, c), 0.05, 0.05, m);
    }
    b.box([-0.25, -0.25, h], [0.2, 0.2, h + 0.045], m, { skip: 'z-', M });
    b.tube(M4.apply(M, [s * 0.6, s * 0.6, h]), M4.apply(M, [s * 0.6, s * 0.6, h + 0.28]), 0.022, 'steel_dark', { n: 5 });
    return h;
}

// a tank lying in two cradles: dished ends, its filler on top
export function tank_lying(b, x, y, z, rz = 0.0, m = 'zinc', L = 1.8, r = 0.45) {
    const M = M4.mul(place([x, y, z + r + 0.22], rz), place([-L / 2.0, 0.0, 0.0], 0.0, 0.0, Math.PI / 2.0));
    b.lathe([[0.02, 0.0], [r * 0.68, 0.035], [r * 0.95, 0.11], [r, 0.2], [r, L - 0.2], [r * 0.95, L - 0.11], [r * 0.68, L - 0.035], [0.02, L]], [0.0, 0.0, 0.0], m, { n: 14, M });
    const M2 = place([x, y, z], rz);
    for (const q of [-0.55, 0.55]) b.box([q - 0.07, -r * 0.8, 0.0], [q + 0.07, r * 0.8, 0.34], 'concrete', { skip: 'z-', M: M2 });
    b.tube(M4.apply(M2, [0.3, 0.0, 2 * r + 0.2]), M4.apply(M2, [0.3, 0.0, 2 * r + 0.3]), 0.07, 'steel_dark', { n: 6 });
}

// an evaporative cooler: a pan, four corner posts, a lid, a wetted pad in three sides, its duct out of the fourth and
// down through the roof; on short legs
export function cooler(b, x, y, z, rz = 0.0) {
    const M = place([x, y, z], rz);
    const s = 0.45, z0 = 0.3, z1 = 1.2;
    for (const sx of [-1, 1]) {
        for (const sy of [-1, 1]) {
            b.beam(M4.apply(M, [sx * (s - 0.03), sy * (s - 0.03), 0.0]), M4.apply(M, [sx * (s - 0.03), sy * (s - 0.03), z0]), 0.04, 0.04, 'steel_dark', { up: [1.0, 0.0, 0.0] });
            b.beam(M4.apply(M, [sx * s, sy * s, z0]), M4.apply(M, [sx * s, sy * s, z1]), 0.07, 0.07, 'cooler', { up: [1.0, 0.0, 0.0] });
        }
    }
    b.box([-s + 0.02, -s + 0.02, z0 + 0.1], [s - 0.02, s - 0.02, z1 - 0.06], 'cooler_pad', { skip: 'z-z+', M });
    b.box([-s - 0.02, -s - 0.02, z0], [s + 0.02, s + 0.02, z0 + 0.12], 'cooler', { M });
    b.box([-s - 0.02, -s - 0.02, z1 - 0.07], [s + 0.02, s + 0.02, z1], 'cooler', { skip: 'z-', M });
    b.box([-0.2, s - 0.02, z0 + 0.25], [0.2, s + 0.42, z0 + 0.65], 'zinc_old', { skip: 'y-', M });
    b.box([-0.2, s + 0.02, 0.0], [0.2, s + 0.42, z0 + 0.25], 'zinc_old', { skip: 'z-z+', M });
}

// a split unit's outdoor half: its case, the fan's grille, two feet; M places it (it looks along its own -y)
export function condenser(b, M) {
    b.box([-0.4, -0.15, 0.06], [0.4, 0.15, 0.61], 'ac', { M });
    const ring = [];
    for (let k = 0; k < 12; k++) ring.push(M4.apply(M, [-0.1 + 0.21 * Math.cos(2 * Math.PI * k / 12), -0.158, 0.335 + 0.21 * Math.sin(2 * Math.PI * k / 12)]));
    b.poly(ring, 'ac_fan');
    for (const q of [-0.3, 0.3]) b.box([q - 0.03, -0.17, 0.0], [q + 0.03, 0.17, 0.06], 'steel_dark', { skip: 'z+', M });
}

// a thermosiphon heater: two glazed collectors on a frame at forty degrees, its tank lying along their top
export function solar_heater(b, x, y, z, rz = 0.0) {
    const M = place([x, y, z], rz);
    const T = M4.mul(M, place([0.0, -0.75, 0.25], 0.0, 40.0 * Math.PI / 180));
    b.box([-1.0, 0.0, 0.0], [1.0, 1.9, 0.07], 'frame_alu', { top: 'solar', M: T });
    const top = M4.apply(T, [0.0, 1.95, 0.25]);
    const M3 = M4.mul(place(top, rz), place([-0.75, 0.0, 0.0], 0.0, 0.0, Math.PI / 2.0));
    b.lathe([[0.02, 0.0], [0.2, 0.03], [0.24, 0.1], [0.24, 1.4], [0.2, 1.47], [0.02, 1.5]], [0.0, 0.0, 0.0], 'tank_white', { n: 10, M: M3 });
    for (const sx of [-0.9, 0.9]) {
        const a = M4.apply(M, [sx, 0.7, 0.0]);
        b.beam(a, M4.apply(T, [sx, 1.8, 0.0]), 0.04, 0.04, 'steel_dark', { up: [1.0, 0.0, 0.0] });
        b.beam(M4.apply(M, [sx, -0.7, 0.0]), M4.apply(T, [sx, 0.05, 0.0]), 0.04, 0.04, 'steel_dark', { up: [1.0, 0.0, 0.0] });
        b.beam(M4.apply(M, [sx, -0.7, 0.03]), V.add(a, [0.0, 0.0, 0.03]), 0.04, 0.04, 'steel_dark');
    }
}

// one thing hung over a line from a to c: folded over it, the front hanging `drop`, the back less; it bellies a little
export function cloth_on_line(b, rng, a, c, drop, m, back = null) {
    a = V.v3(a); c = V.v3(c);
    let u = V.sub(c, a);
    const w = V.len(u);
    u = V.mul(u, 1 / w);
    const n = [-u[1], u[0], 0.0];
    back = back === null ? drop * rng.uniform(0.25, 0.95) : back;
    const mid = V.mul(V.add(a, c), 0.5);
    const belly = rng.uniform(0.02, 0.06);
    for (const [sgn, dz] of [[1.0, drop], [-1.0, back]]) {
        const o = V.mul(n, 0.012 * sgn);
        const top = [V.add(a, o), V.add(mid, o), V.add(c, o)];
        const b0 = V.add(V.sub(V.add(a, o), [0, 0, dz]), V.mul(u, rng.uniform(0.0, 0.04)));
        const b1 = V.sub(V.add(V.add(mid, o), V.mul(n, belly * sgn)), [0, 0, dz * rng.uniform(0.96, 1.03)]);
        const b2 = V.sub(V.sub(V.add(c, o), [0, 0, dz]), V.mul(u, rng.uniform(0.0, 0.04)));
        const bot = [b0, b1, b2];
        for (let k = 0; k < 2; k++) {
            const pts = sgn > 0 ? [bot[k], bot[k + 1], top[k + 1], top[k]] : [bot[k + 1], bot[k], top[k], top[k + 1]];
            b.poly(pts, m);
        }
    }
    b.quad(V.add(a, V.mul(n, 0.012)), V.add(c, V.mul(n, 0.012)), V.sub(c, V.mul(n, 0.012)), V.sub(a, V.mul(n, 0.012)), m);
}

// washing on the roof: two posts with a bar across each, slack lines between them, what a family wears on them
export function washing(b, rng, p0, p1, z, { posts = true, lines = 2 } = {}) {
    p0 = [p0[0], p0[1], z]; p1 = [p1[0], p1[1], z];
    const u = V.norm(V.sub(p1, p0));
    const n = [-u[1], u[0], 0.0];
    const hgt = 1.85, half = lines > 1 ? 0.3 : 0.0;
    if (posts) {
        for (const p of [p0, p1]) {
            b.tube(p, V.add(p, [0, 0, hgt]), 0.025, 'steel_dark', { n: 5 });
            if (lines > 1) b.beam(V.sub(V.add(p, [0, 0, hgt]), V.mul(n, half + 0.05)), V.add(V.add(p, [0, 0, hgt]), V.mul(n, half + 0.05)), 0.03, 0.03, 'steel_dark');
        }
    }
    for (let q = 0; q < lines; q++) {
        const off = V.mul(n, lines > 1 ? half * (2 * q - 1) : 0.0);
        const pts = catenary(V.add(V.add(p0, off), [0, 0, hgt]), V.add(V.add(p1, off), [0, 0, hgt]), rng.uniform(0.08, 0.2), 8);
        b.path(pts, 0.004, 'wire', { n: 3 });
        let k = rng.uniform(0.04, 0.3);                              // along the line, 0..1
        const L = V.len(V.sub(p1, p0));
        while (k < 0.9) {
            const w = rng.choice([0.35, 0.45, 0.5, 0.6, 0.7, 0.9, 1.4, 1.9]) / L;
            if (k + w > 0.96) break;
            const i0 = k * 8.0, i1 = (k + w) * 8.0;
            const a = V.lerp(pts[Math.trunc(i0)], pts[Math.min(Math.trunc(i0) + 1, 8)], i0 - Math.trunc(i0));
            const c = V.lerp(pts[Math.trunc(i1)], pts[Math.min(Math.trunc(i1) + 1, 8)], i1 - Math.trunc(i1));
            const wide = w * L > 1.2;
            const drop = wide ? rng.uniform(0.9, 1.3) : rng.uniform(0.35, 0.85);
            const mm = wide ? rng.choice(['cloth0', 'cloth0', 'rug:0', 'rug:1', 'cloth3']) : rng.choice(CLOTH);
            cloth_on_line(b, rng, a, c, drop, mm);
            k += w + rng.uniform(0.02, 0.22) / L * 3.0;
        }
    }
}

// a carpet, or a sheet, aired over a parapet: down its inside, across its top, down its outside (P: a point on the
// parapet's OUTER face at its middle; u along it; n out of it; zt the parapet's top)
export function rug_over(b, rng, P, u, n, zt, t, m = null, w = null) {
    P = [P[0], P[1], 0.0]; u = [u[0], u[1], 0.0]; n = [n[0], n[1], 0.0];
    w = w || rng.uniform(1.2, 2.2);
    m = m || rng.choice(['rug:0', 'rug:1', 'rug:2', 'rug:3', 'cloth1', 'cloth8']);
    const z = [0, 0, zt + 0.012];
    const d_out = rng.uniform(0.45, 1.05), d_in = rng.uniform(0.25, 0.6);
    const cols = [0, 1, 2, 3].map((k) => V.add(P, V.mul(u, w * (k / 3.0 - 0.5))));
    const hem = [0, 1, 2, 3].map(() => d_out * rng.uniform(0.9, 1.06));
    const out_top = cols.map((c) => V.add(V.add(c, V.mul(n, 0.015)), z));
    const out_bot = cols.map((c, k) => V.sub(V.add(V.add(c, V.mul(n, 0.02 + rng.uniform(0.0, 0.05))), z), [0, 0, hem[k]]));
    const in_top = cols.map((c) => V.add(V.sub(c, V.mul(n, t + 0.015)), z));
    const in_bot = cols.map((c) => V.sub(V.add(V.sub(c, V.mul(n, t + 0.02)), z), [0, 0, d_in]));
    b.grid([out_bot, out_top, in_top, in_bot], m, { smooth: false });
}

// an iron bed on the roof, where people sleep in summer: its frame, its legs, a mattress or the bare frame
export function bed(b, rng, x, y, z, rz = 0.0) {
    const M = place([x, y, z], rz);
    for (const sx of [-0.45, 0.45]) {
        for (const sy of [-0.95, 0.95]) b.beam(M4.apply(M, [sx, sy, 0.0]), M4.apply(M, [sx, sy, sy < 0 ? 0.45 : 0.75]), 0.035, 0.035, 'steel_paint', { up: [1.0, 0.0, 0.0] });
        b.beam(M4.apply(M, [sx, -0.95, 0.4]), M4.apply(M, [sx, 0.95, 0.4]), 0.035, 0.035, 'steel_paint');
    }
    for (const [sy, zz] of [[-0.95, 0.4], [0.95, 0.4], [0.95, 0.72]]) b.beam(M4.apply(M, [-0.45, sy, zz]), M4.apply(M, [0.45, sy, zz]), 0.035, 0.035, 'steel_paint');
    if (rng.random() < 0.7) {
        const mm = rng.random() < 0.6 ? 'mattress' : rng.choice(CLOTH);
        b.box([-0.44, -0.93, 0.42], [0.44, 0.93, 0.54], mm, { skip: 'z-', M });
    } else {
        for (let q = -4; q < 5; q++) b.beam(M4.apply(M, [-0.45, q * 0.2, 0.4]), M4.apply(M, [0.45, q * 0.2, 0.4]), 0.02, 0.01, 'steel_paint');
    }
}

export function chair(b, M, m = 'plastic_white') {
    for (const sx of [-0.19, 0.19]) for (const sy of [-0.19, 0.19]) b.beam(M4.apply(M, [sx, sy, 0.0]), M4.apply(M, [sx * 0.9, sy * 0.9, 0.43]), 0.03, 0.03, m, { up: [1.0, 0.0, 0.0] });
    b.box([-0.22, -0.22, 0.42], [0.22, 0.22, 0.455], m, { M });
    b.box([-0.22, 0.19, 0.455], [0.22, 0.225, 0.85], m, { skip: 'z-', M: M4.mul(M, place([0, 0, 0], 0.0, -0.12)) });
}

export function table_and_chairs(b, rng, x, y, z) {
    const M = place([x, y, z], rng.uniform(0.0, 6.28));
    for (const sx of [-0.32, 0.32]) for (const sy of [-0.32, 0.32]) b.beam(M4.apply(M, [sx, sy, 0.0]), M4.apply(M, [sx, sy, 0.7]), 0.035, 0.035, 'plastic_white', { up: [1.0, 0.0, 0.0] });
    b.box([-0.4, -0.4, 0.7], [0.4, 0.4, 0.735], 'plastic_white', { M });
    const nk = rng.randrange(2, 5);
    for (let k = 0; k < nk; k++) {
        const a = k * Math.PI / 2.0 + rng.uniform(-0.3, 0.3);
        const Mc = M4.mul(M, place([0.75 * Math.sin(a), -0.75 * Math.cos(a), 0.0], a + Math.PI + rng.uniform(-0.4, 0.4)));
        chair(b, Mc, rng.choice(['plastic_white', 'plastic_white', 'plastic_blue', 'plastic_red']));
    }
}

// a shade on four posts: a frame of light section, cloth or a tarpaulin lashed over it and sagging between
export function shade(b, rng, x0, y0, x1, y1, z, m = null, hgt = 2.3) {
    for (const [px, py] of [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]) b.tube([px, py, z], [px, py, z + hgt], 0.03, 'steel_dark', { n: 5 });
    for (const [a, c] of [[[x0, y0], [x1, y0]], [[x1, y0], [x1, y1]], [[x1, y1], [x0, y1]], [[x0, y1], [x0, y0]]]) b.beam([a[0], a[1], z + hgt], [c[0], c[1], z + hgt], 0.04, 0.04, 'steel_dark');
    m = m || rng.choice(['tarp_sand', 'tarp_blue', 'tarp_green', 'tarp_white', 'cloth3', 'awn:4']);
    const nu = 5, nv = 4;
    const sag = rng.uniform(0.08, 0.25);
    const P = [];
    for (let j = 0; j <= nv; j++) {
        const row = [];
        for (let i = 0; i <= nu; i++) row.push([x0 - 0.1 + (x1 - x0 + 0.2) * i / nu, y0 - 0.1 + (y1 - y0 + 0.2) * j / nv,
            z + hgt + 0.03 - sag * Math.sin(Math.PI * i / nu) * Math.sin(Math.PI * j / nv) + rng.uniform(-0.02, 0.02)]);
        P.push(row);
    }
    b.grid(P, m, { smooth: true });
}

// a column begun for a storey never built: its concrete as far as it was poured, its steel waiting, bent
export function stub(b, rng, x, y, z, h = 0.9, bars = 4, w = 0.3) {
    b.box([x - w / 2, y - w / 2, z], [x + w / 2, y + w / 2, z + h], 'concrete', { skip: 'z-' });
    const S = [[-1, -1], [1, -1], [1, 1], [-1, 1], [0, -1], [0, 1]];
    for (let k = 0; k < bars; k++) {
        const [sx, sy] = S[k % 6];
        const p0 = [x + sx * (w / 2 - 0.04), y + sy * (w / 2 - 0.04), z + h - 0.02];
        const ln = rng.uniform(0.5, 1.0);
        const lean = [rng.uniform(-0.18, 0.18), rng.uniform(-0.18, 0.18), 0.0];
        b.path([p0, V.add(V.add(p0, [0, 0, ln * 0.5]), V.mul(lean, 0.3)), V.add(V.add(p0, [0, 0, ln]), lean)], 0.009, 'rebar', { n: 3 });
    }
}

// blocks stacked for the storey to come, some taken
export function block_pile(b, rng, x, y, z, rz = 0.0) {
    const M = place([x, y, z], rz);
    const nl = rng.randrange(2, 5);
    for (let lay = 0; lay < nl; lay++) {
        const nx_ = rng.randrange(2, 5), ny_ = rng.randrange(2, 4);
        for (let i = 0; i < nx_; i++) {
            for (let j = 0; j < ny_; j++) {
                if (lay && rng.random() < 0.25) continue;
                b.box([i * 0.41, j * 0.205, lay * 0.2], [i * 0.41 + 0.4, j * 0.205 + 0.2, lay * 0.2 + 0.195], 'block', { skip: 'z-', M });
            }
        }
    }
}

export function barrel(b, x, y, z, m = 'barrel_blue', lying = null) {
    const M = lying === null ? null : place([x, y, z + 0.29], lying, 0.0, Math.PI / 2.0);
    const c = M === null ? [x, y, z] : [0.0, 0.0, -0.44];
    b.lathe([[0.27, 0.0], [0.29, 0.02], [0.29, 0.28], [0.3, 0.3], [0.29, 0.32], [0.29, 0.56], [0.3, 0.58], [0.29, 0.6], [0.29, 0.86], [0.27, 0.88]], c, m, { n: 12, cap1: m, cap0: m, M });
}

// what gets left on a roof: a drum, tyres, boards, a box, a gas bottle
export function junk(b, rng, x, y, z) {
    const nj = rng.randrange(2, 5);
    for (let i = 0; i < nj; i++) {
        const px = x + rng.uniform(-0.9, 0.9), py = y + rng.uniform(-0.9, 0.9);
        const k = rng.random();
        if (k < 0.25) {
            const m = rng.choice(['barrel_blue', 'barrel_rust', 'barrel_rust']);
            const lying = rng.random() < 0.3 ? rng.uniform(0, 3.14) : null;
            barrel(b, px, py, z, m, lying);
        } else if (k < 0.45) {
            const nq = rng.randrange(1, 4);
            for (let q = 0; q < nq; q++) b.lathe([[0.2, 0.0], [0.3, 0.02], [0.33, 0.09], [0.3, 0.17], [0.2, 0.19]], [px, py, z + q * 0.19], 'tyre', { n: 10 });
        } else if (k < 0.7) {
            const a = rng.uniform(0.0, 3.14);
            const nq = rng.randrange(2, 6);
            for (let q = 0; q < nq; q++) {
                const o = [px + q * 0.12 * Math.sin(a), py - q * 0.12 * Math.cos(a), z + 0.02 + 0.01 * q];
                const ln = rng.uniform(1.2, 2.6);
                const a1 = a + rng.uniform(-0.08, 0.08), a2 = a + rng.uniform(-0.08, 0.08);
                const d = V.mul([Math.cos(a1), Math.sin(a2), 0.0], ln / 2.0);
                b.beam(V.sub(o, d), V.add(o, d), 0.1, 0.025, rng.choice(['wood', 'wood_pale']));
            }
        } else if (k < 0.88) {
            const s = rng.uniform(0.3, 0.6);
            const hz = s * rng.uniform(0.5, 1.0);
            const m = rng.choice(['cardboard', 'crate', 'wood_pale']);
            b.box([-s / 2, -s / 2, 0.0], [s / 2, s / 2, hz], m, { skip: 'z-', M: place([px, py, z], rng.uniform(0, 3.14)) });
        } else {
            b.lathe([[0.14, 0.0], [0.15, 0.03], [0.15, 0.42], [0.1, 0.52], [0.04, 0.55], [0.04, 0.6]], [px, py, z], rng.choice(['tank_blue', 'tank_red', 'zinc_old']), { n: 8 });
        }
    }
}

// a television aerial on a thin mast
export function antenna(b, rng, x, y, z) {
    const h = rng.uniform(2.5, 4.5);
    b.tube([x, y, z], [x, y, z + h], 0.018, 'steel_dark', { n: 4, smooth: false });
    const a = rng.uniform(0.0, 6.28);
    const u = [Math.cos(a), Math.sin(a), 0.0], n = [-Math.sin(a), Math.cos(a), 0.0];
    const c = [x, y, z + h - 0.12];
    b.beam(V.sub(c, V.mul(u, 0.6)), V.add(c, V.mul(u, 0.6)), 0.02, 0.02, 'zinc');
    for (let q = 0; q < 6; q++) {
        const p = V.add(c, V.mul(u, -0.55 + q * 0.22));
        const w = 0.34 - 0.03 * q;
        b.beam(V.sub(p, V.mul(n, w)), V.add(p, V.mul(n, w)), 0.012, 0.012, 'zinc');
    }
}

// ================================================================================================ in the rooms
// what a room held, where it stood: against its walls, a carpet on its floor, a fan under its ceiling. Nobody is
// shown: this is theirs.
export function furniture(b, rng, x0, y0, x1, y1, z, h) {
    const cx = (x0 + x1) / 2.0, cy = (y0 + y1) / 2.0;
    if (rng.random() < 0.6) {
        const rw = Math.min(2.6, (x1 - x0) * 0.6), rd = Math.min(1.8, (y1 - y0) * 0.5);
        const px = cx + rng.uniform(-0.3, 0.3), py = cy + rng.uniform(-0.3, 0.3);
        const M = place([px, py, z + 0.012], rng.uniform(-0.1, 0.1));
        b.quad(M4.apply(M, [-rw / 2, -rd / 2, 0]), M4.apply(M, [rw / 2, -rd / 2, 0]), M4.apply(M, [rw / 2, rd / 2, 0]), M4.apply(M, [-rw / 2, rd / 2, 0]), `rug:${rng.randrange(4)}`);
    }
    const k = rng.random();
    const yb = y1 - 0.2;                                              // against the back wall
    if (k < 0.35) {                                                   // a wardrobe, its door hanging open
        const xw = rng.uniform(x0 + 0.3, Math.max(x0 + 0.31, x1 - 1.5));
        b.box([xw, yb - 0.55, z], [xw + 1.2, yb, z + 1.9], 'wood', { skip: 'z-' });
        b.box([0.0, -0.02, 0.05], [0.58, 0.0, 1.85], 'wood', { M: place([xw + 1.2, yb - 0.56, z], rng.uniform(-2.2, -0.6)) });
    } else if (k < 0.65) {                                            // shelves
        const xw = rng.uniform(x0 + 0.3, Math.max(x0 + 0.31, x1 - 1.3));
        for (const q of [0.0, 1.0]) b.box([xw + q * 0.96, yb - 0.3, z], [xw + q * 0.96 + 0.04, yb, z + 1.5], 'wood_pale', { skip: 'z-' });
        for (let q = 0; q < 4; q++) b.box([xw, yb - 0.3, z + 0.1 + q * 0.45], [xw + 1.0, yb, z + 0.13 + q * 0.45], 'wood_pale');
    } else if (k < 0.85) {                                            // a bed
        bed(b, rng, rng.uniform(x0 + 0.8, x1 - 0.8), yb - 1.1, z, rng.uniform(-0.15, 0.15));
    }
    if (rng.random() < 0.4) {                                         // a fan under the ceiling
        const c = [cx, cy, z + h - 0.32];
        b.tube(c, V.add(c, [0, 0, 0.32]), 0.015, 'steel_dark', { n: 4, smooth: false });
        b.lathe([[0.02, -0.05], [0.09, -0.04], [0.09, 0.04], [0.02, 0.05]], c, 'frame_white', { n: 8 });
        const a0 = rng.uniform(0, 2.0);
        for (let q = 0; q < 3; q++) {
            const a = a0 + q * 2.094;
            const d = [Math.cos(a), Math.sin(a), 0.0];
            b.beam(V.add(c, V.mul(d, 0.08)), V.sub(V.add(c, V.mul(d, 0.62)), [0, 0, rng.uniform(0.0, 0.12)]), 0.12, 0.008, 'frame_white');
        }
    }
}
