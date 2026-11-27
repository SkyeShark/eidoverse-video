// eidoverse/sets/town/street.js — what stands in the town's streets and yards; each function returns a mesh builder
// (mb.js). Metres; each thing in its own space, standing on z = 0 (+Z up).
//
//   car(kind, burnt)      a saloon, a pickup, a van: ONE lofted body each: sections along its length with a sill, a
//                         waist, a belt line and a narrower roof, its wheel arches cut in the sill line, its screens and
//                         side glass as the body's own faces, wheels in the arches; burnt: a shell sitting on its rims
//   palm(rng, light)      a date palm: a thin ringed trunk and a ball of sixty fronds set round it by the golden angle,
//                         the young ones standing, the old ones hanging; light: fewer fronds and leaflets, for the far edge
//   tree(rng)             a broad-leaved yard tree: a rounded crown of several masses with a broken edge of leaf sprays
//   dish()                an offset dish on its pole, its feed on its arm
//   pole(rng), lampPost() a concrete pole with its arms and insulators (a transformer on some); a road's lamp
//   mosque(rng)           a neighbourhood mosque: a hall with pointed windows, a portal, a pointed dome on its drum and
//                         two small ones, a minaret with its gallery and cap, a walled yard
//   stall(rng), bicycle(), tWall()   a market stall under its awning; a child's bicycle; a blast wall's section
import { V, M4, MB, place } from './mb.js';
import * as K from './kit.js';

function lerpTab(tab, x) {
    if (x <= tab[0][0]) return tab[0][1];
    for (let i = 0; i < tab.length - 1; i++) {
        const [x0, v0] = tab[i], [x1, v1] = tab[i + 1];
        if (x <= x1) return v0 + (v1 - v0) * (x - x0) / (x1 - x0);
    }
    return tab[tab.length - 1][1];
}
const r3 = (x) => parseFloat(x.toFixed(3));

// ================================================================================================ cars
const CARS = {
    saloon: {
        axles: [-1.35, 1.35], wr: 0.31, track: 0.74,
        zl: [[-2.2, 0.78], [-2.1, 0.88], [-1.25, 0.93], [-1.05, 0.90], [0.95, 0.88], [1.1, 0.85], [2.0, 0.74], [2.2, 0.62]],
        zr: [[-2.2, 0.80], [-2.1, 0.90], [-1.25, 0.95], [-0.7, 1.40], [0.3, 1.42], [0.95, 0.90], [1.1, 0.87], [2.0, 0.76], [2.2, 0.64]],
        hr: [[-2.2, 0.60], [-2.1, 0.76], [-1.25, 0.76], [-0.7, 0.62], [0.3, 0.62], [0.95, 0.76], [2.0, 0.74], [2.2, 0.58]],
        hw: [[-2.2, 0.68], [-2.1, 0.83], [-1.0, 0.85], [1.0, 0.85], [2.0, 0.82], [2.2, 0.66]],
        st: [-2.2, -2.1, -1.9, -0.7, -0.3, -0.22, 0.3, 0.62, 0.95, 1.9, 2.05, 2.2], top_glass: [[-1.25, -0.7], [0.3, 0.95]], side_glass: [[-0.7, -0.3], [-0.22, 0.3]] },
    pickup: {
        axles: [-1.6, 1.6], wr: 0.36, track: 0.76, cab_back: -0.25,
        zl: [[-0.25, 1.0], [1.55, 1.0], [1.7, 0.98], [2.45, 0.88], [2.6, 0.76]],
        zr: [[-0.25, 1.70], [1.0, 1.72], [1.55, 1.03], [1.7, 1.0], [2.45, 0.9], [2.6, 0.78]],
        hr: [[-0.25, 0.66], [1.0, 0.66], [1.55, 0.78], [2.45, 0.76], [2.6, 0.62]],
        hw: [[-0.25, 0.87], [1.5, 0.87], [2.45, 0.84], [2.6, 0.7]],
        st: [-0.25, 0.28, 0.36, 1.0, 1.28, 1.55, 2.3, 2.47, 2.6], top_glass: [[1.0, 1.55]], side_glass: [[-0.25, 0.28], [0.36, 1.0]] },
    van: {
        axles: [-1.45, 1.5], wr: 0.33, track: 0.78,
        zl: [[-2.45, 1.0], [1.55, 1.05], [2.0, 1.0], [2.35, 0.9], [2.45, 0.7]],
        zr: [[-2.45, 1.86], [-2.3, 1.94], [1.45, 1.95], [2.05, 1.08], [2.35, 0.94], [2.45, 0.72]],
        hr: [[-2.45, 0.78], [1.45, 0.78], [2.05, 0.82], [2.45, 0.66]],
        hw: [[-2.45, 0.86], [-2.35, 0.9], [2.0, 0.9], [2.35, 0.86], [2.45, 0.72]],
        st: [-2.45, -2.35, -0.6, -0.52, 0.4, 0.48, 1.45, 1.75, 2.05, 2.3, 2.45], top_glass: [[1.45, 2.05]], side_glass: [[-2.1, -0.6], [-0.52, 0.4], [0.48, 1.45]] },
};

export function car(kind = 'saloon', { burnt = false, load = null, rng = null } = {}) {
    const S = CARS[kind];
    const b = new MB();
    const [PA, GL] = burnt ? ['car_burnt', 'car_in'] : ['car', 'car_glass'];
    const sink = burnt ? 0.13 : 0.0;                                 // (a burnt car sits on its rims)
    const base = 0.2, zc = S.wr, r_arch = S.wr + 0.07;
    const zb = (x) => {
        let z = base;
        for (const xa of S.axles) if (Math.abs(x - xa) < r_arch) z = Math.max(z, zc + Math.sqrt(r_arch ** 2 - (x - xa) ** 2));
        return z;
    };
    const xset = new Set(S.st);
    for (const xa of S.axles) for (const q of [-0.97, -0.72, -0.38, 0.0, 0.38, 0.72, 0.97]) xset.add(r3(xa + q * r_arch));
    const x_lo = S.st[0], x_hi = S.st[S.st.length - 1];
    const xs = [...xset].filter((x) => x_lo <= x && x <= x_hi).sort((a, c) => a - c);
    const rings = [];
    for (const x of xs) {
        const hw = lerpTab(S.hw, x), hr = lerpTab(S.hr, x), zl = lerpTab(S.zl, x), zr = lerpTab(S.zr, x);
        const end = Math.min(x - x_lo, x_hi - x);
        const zbb = zb(x) + (end < 0.05 ? 0.12 : 0.0);
        const right = [[0.0, zbb], [0.8 * hw, zbb], [hw, Math.min(zbb + 0.13, zl - 0.1)], [hw, Math.min(Math.max(zbb + 0.2, 0.6), zl - 0.04)], [0.965 * hw, zl],
            [hr, Math.max(zl + 0.01, zr - 0.06)], [0.72 * hr, zr], [0.0, zr]];
        const ring = right.map(([y, z]) => [x, y, z - sink]);
        for (let k = right.length - 2; k >= 1; k--) ring.push([x, -right[k][0], right[k][1] - sink]);
        rings.push(ring);
    }
    const n = rings[0].length;
    const base_i = b.verts(rings.flat());
    const inside = (x0, x1, spans) => spans.some(([a, c]) => a - 1e-6 <= x0 && x1 <= c + 1e-6);
    for (let s = 0; s < xs.length - 1; s++) {
        const tg = inside(xs[s], xs[s + 1], S.top_glass), sg = inside(xs[s], xs[s + 1], S.side_glass);
        for (let k = 0; k < n; k++) {
            let m;
            if (k === 0 || k === n - 1) m = 'steel_dark';
            else if (k === 4 || k === 9) m = sg ? GL : PA;           // (beside a screen this strip is the pillar)
            else if (k >= 5 && k <= 8) m = tg ? GL : PA;
            else m = PA;
            const a = base_i + s * n + k, c = base_i + s * n + (k + 1) % n;
            b.face([a, c, c + n, a + n], m, true);
        }
    }
    b.poly(rings[rings.length - 1], PA);                             // its nose
    if (S.cab_back !== undefined) {                                  // a pickup: the cab's back, its window; then the bed
        b.poly([...rings[0]].reverse(), PA);
        const x = S.cab_back - 0.005;
        b.quad([x, 0.5, 1.12 - sink], [x, -0.5, 1.12 - sink], [x, -0.5, 1.55 - sink], [x, 0.5, 1.55 - sink], GL);
        const x0 = -2.6, x1 = S.cab_back, zf_ = 0.62 - sink, zt = 1.04 - sink;
        b.box([x0, -0.80, zf_ - 0.04], [x1, 0.80, zf_], 'car_bed', { skip: 'z-' });
        for (const sy of [-1, 1]) b.box([x0, Math.min(sy * 0.8, sy * 0.87), 0.46 - sink], [x1, Math.max(sy * 0.8, sy * 0.87), zt], PA, { skip: 'x+' });
        b.box([x0 - 0.05, -0.87, 0.5 - sink], [x0, 0.87, zt], PA);
        b.box([x0 + 0.1, -0.55, 0.3 - sink], [x1, 0.55, zf_ - 0.04], 'steel_dark', { skip: 'z+x+' });
        if (load && rng) {                                           // what it carries
            const nl = rng.randrange(3, 7);
            for (let i = 0; i < nl; i++) {
                const px = rng.uniform(x0 + 0.4, x1 - 0.4), py = rng.uniform(-0.5, 0.5);
                if (load === 'sacks') b.lathe([[0.02, 0.0], [0.26, 0.05], [0.3, 0.16], [0.24, 0.27], [0.02, 0.3]], [px, py, zf_ + rng.uniform(0.0, 0.25)], 'sack', { n: 8 });
                else if (load === 'barrels') K.barrel(b, px, py, zf_, rng.choice(['barrel_blue', 'barrel_rust']));
                else {
                    const s_ = rng.uniform(0.35, 0.6);
                    const hz = s_ * rng.uniform(0.6, 1.0);
                    b.box([px - s_ / 2, py - s_ / 2, zf_], [px + s_ / 2, py + s_ / 2, zf_ + hz], rng.choice(['cardboard', 'crate', 'wood_pale']), { skip: 'z-' });
                }
            }
        }
    } else b.poly([...rings[0]].reverse(), PA);
    const hwf = lerpTab(S.hw, x_hi), hwb = lerpTab(S.hw, S.cab_back !== undefined ? -2.6 : x_lo);
    const xb = S.cab_back !== undefined ? -2.65 : x_lo;
    b.box([x_hi - 0.02, -hwf - 0.06, 0.3 - sink], [x_hi + 0.09, hwf + 0.06, 0.5 - sink], 'bumper', { skip: 'x-' });
    b.box([xb - 0.09, -hwb - 0.06, 0.3 - sink], [xb + 0.02, hwb + 0.06, 0.5 - sink], 'bumper', { skip: 'x+' });
    const zh = lerpTab(S.zl, x_hi) - 0.05 - sink;
    for (const sy of [-1, 1]) {
        b.box([x_hi - 0.03, sy * hwf * 0.9 - 0.14, zh - 0.07], [x_hi + 0.012, sy * hwf * 0.9 + 0.14, zh + 0.05], burnt ? 'car_in' : 'lamp_clear', { skip: 'x-' });
        b.box([xb - 0.012, sy * hwb * 0.92 - 0.1, 0.62 - sink], [xb + 0.03, sy * hwb * 0.92 + 0.1, 0.8 - sink], burnt ? 'car_in' : 'lamp_red', { skip: 'x+' });
    }
    const r = S.wr * (burnt ? 0.62 : 1.0);
    for (const xa of S.axles) {
        for (const sy of [-1, 1]) {
            const M = place([xa, sy * S.track, r], 0.0, Math.PI / 2.0);
            if (burnt) b.lathe([[0.05, -0.08], [r, -0.09], [r, 0.09], [0.05, 0.08]], [0.0, 0.0, 0.0], 'car_burnt', { n: 12, M });
            else {
                b.lathe([[r * 0.62, -0.1], [r * 0.93, -0.105], [r, -0.06], [r, 0.06], [r * 0.93, 0.105], [r * 0.62, 0.1]], [0.0, 0.0, 0.0], 'tyre', { n: 14, M });
                b.lathe(sy > 0 ? [[0.02, -0.085 * sy], [r * 0.6, -0.095 * sy]] : [[r * 0.6, 0.095], [0.02, 0.085]], [0.0, 0.0, 0.0], 'hub', { n: 10, M });
            }
        }
    }
    return b;
}

// ================================================================================================ trees
// light: a palm for the far edge of the town (fewer fronds, two leaflets a length where the near ones have three)
export function palm(rng, { hgt = null, light = false } = {}) {
    const b = new MB();
    hgt = hgt || rng.uniform(6.5, 11.5);
    const l0 = rng.uniform(-1.0, 1.0), l1 = rng.uniform(-1.0, 1.0);
    const lean = V.mul([l0, l1, 0.0], rng.uniform(0.0, 0.9));
    const n = 16;
    const pts = [];
    for (let s = 0; s <= n; s++) pts.push(V.add(V.add([0, 0, -0.2], V.mul(lean, (s / n) ** 2)), [0, 0, (hgt + 0.2) * s / n]));
    b.path(pts, (t) => (0.34 - 0.10 * Math.min(1.0, t * 5.0)) * (1.0 - 0.12 * t) + (t > 0.94 ? 0.07 : 0.0), 'palm_trunk', { n: 9 });
    const top = pts[pts.length - 1];
    const N = !light ? rng.randrange(62, 78) : rng.randrange(40, 48);
    const per = !light ? 3 : 2;
    for (let k = 0; k < N; k++) {
        const q = k / (N - 1.0);                                     // 0 the youngest, at the heart; 1 the oldest, hanging
        const az = k * 2.39996 + rng.uniform(-0.15, 0.15);           // the golden angle
        const el = (80.0 - 132.0 * q ** 0.85 + rng.uniform(-7.0, 7.0)) * Math.PI / 180;
        const Lf = rng.uniform(3.3, 4.4) * (0.55 + 0.45 * Math.min(1.0, q * 3.0));
        const dead = q > 0.9 && rng.random() < 0.6;
        const m = dead ? 'frond_dead' : (q > 0.62 ? 'frond_old' : 'frond');
        const rad = [Math.cos(az), Math.sin(az), 0.0];
        const tan = [-Math.sin(az), Math.cos(az), 0.0];
        const nseg = 9;
        let p = V.add(V.add(top, V.mul(rad, 0.22)), [0, 0, 0.1 - 0.5 * q]);
        const spine = [p];
        const droop = rng.uniform(0.9, 1.5) + (dead ? 0.8 : 0.0);
        for (let s = 0; s < nseg; s++) {
            const e = el - droop * ((s + 0.5) / nseg) ** 1.6;
            p = V.add(p, V.mul(V.add(V.mul(rad, Math.cos(e)), [0, 0, Math.sin(e)]), Lf / nseg));
            spine.push(p);
        }
        const sp = spine.filter((_, i) => i % 2 === 0);
        if (nseg % 2) sp.push(spine[spine.length - 1]);
        b.path(sp, (t) => 0.028 - 0.02 * t, !dead ? 'frond_old' : 'frond_dead', { n: 3 });
        for (let s = 0; s < nseg; s++) {
            const a = spine[s], c = spine[s + 1];
            const t = V.norm(V.sub(c, a));
            const up = V.cross(t, tan);                              // the frond's own 'up': square to its rachis
            const sfrac = (s + 0.5) / nseg;
            const ll = 0.52 * Math.sin(Math.PI * (0.12 + 0.86 * sfrac)) ** 0.7;
            for (let j = 0; j < per; j++) {
                const o = V.lerp(a, c, (j + rng.uniform(0.2, 0.8)) / per);
                for (const sg of [-1.0, 1.0]) {
                    const dir = V.norm(V.add(V.add(V.mul(t, 0.55), V.mul(tan, sg * 0.75)), V.mul(up, 0.34 - 0.5 * sfrac)));
                    const tip = V.sub(V.add(o, V.mul(dir, ll * rng.uniform(0.85, 1.1))), [0, 0, 0.1 * ll]);
                    const hw = !light ? 0.035 : 0.055;
                    b.poly([V.sub(o, V.mul(t, hw)), V.add(o, V.mul(t, hw)), tip], m);
                }
            }
        }
    }
    const nd = rng.randrange(0, 5);
    for (let k = 0; k < nd; k++) {                                   // bunches of dates under the crown
        const az = rng.uniform(0.0, 6.283);
        const rad = [Math.cos(az), Math.sin(az), 0.0];
        const p0 = V.sub(V.add(top, V.mul(rad, 0.25)), [0, 0, 0.3]);
        const f1 = rng.uniform(0.5, 0.9), f2 = rng.uniform(0.5, 1.0);
        const p1 = V.sub(V.add(p0, V.mul(rad, f1)), [0, 0, f2]);
        b.path([p0, V.add(V.lerp(p0, p1, 0.5), [0, 0, 0.2]), p1], 0.02, 'dates', { n: 3 });
        b.lathe([[0.02, -0.42], [0.11, -0.32], [0.13, -0.12], [0.06, 0.0]], p1, 'dates', { n: 6 });
    }
    return b;
}

export function tree(rng) {
    const b = new MB();
    const hgt = rng.uniform(3.2, 5.5);
    const tx = rng.uniform(-0.3, 0.3), ty = rng.uniform(-0.3, 0.3);
    const top = [tx, ty, hgt * 0.55];
    b.path([[0, 0, -0.1], [top[0] * 0.3, top[1] * 0.3, hgt * 0.3], top], (t) => 0.19 - 0.08 * t, 'trunk', { n: 7 });
    const masses = [];
    const nm = rng.randrange(4, 8);
    for (let k = 0; k < nm; k++) {
        const a = rng.uniform(0.0, 6.283);
        const d = rng.uniform(0.3, 1.5);
        const c = V.add(top, [d * Math.cos(a), d * Math.sin(a), rng.uniform(0.2, 1.7)]);
        const r = rng.uniform(1.0, 1.9);
        masses.push([c, r]);
        b.path([V.sub(top, [0, 0, 0.3]), V.lerp(top, c, 0.6), c], (t) => 0.09 - 0.05 * t, 'trunk', { n: 5 });
        const nu = 10, nv = 7;
        const P = [];
        for (let j = 1; j < nv; j++) {
            const row = [];
            for (let i = 0; i < nu; i++) {
                const th = 2 * Math.PI * i / nu, ph = Math.PI * j / nv;
                const rr = r * 0.9 * (1.0 + rng.uniform(-0.12, 0.12));
                row.push(V.add(c, [rr * Math.sin(ph) * Math.cos(th), rr * Math.sin(ph) * Math.sin(th), 0.72 * rr * Math.cos(ph)]));
            }
            P.push(row);
        }
        const base = b.grid([...P].reverse(), 'leaf', { smooth: true, wrap_u: true });
        b.face([...Array(nu).keys()].map((i) => base + (nv - 2) * nu + i), 'leaf', true);
        b.face([...Array(nu).keys()].reverse().map((i) => base + i), 'leaf', true);
    }
    // its leaves: sprays all over each mass and standing a little off it, each a twig's worth, turned every way
    for (const [c, r] of masses) {
        for (let i = 0; i < 150; i++) {
            const th = rng.uniform(0.0, 6.283), ph = Math.acos(rng.uniform(-0.55, 1.0));
            const d = [Math.sin(ph) * Math.cos(th), Math.sin(ph) * Math.sin(th), 0.72 * Math.cos(ph)];
            const o = V.add(c, V.mul(d, r * rng.uniform(0.9, 1.16)));
            const q0 = rng.uniform(-1, 1), q1 = rng.uniform(-1, 1), q2 = rng.uniform(-1, 1);
            let a1 = V.cross(d, [q0, q1, q2]);
            if (V.len(a1) < 1e-3) continue;
            a1 = V.norm(a1);
            const a2 = V.norm(V.add(V.cross(d, a1), V.mul(d, rng.uniform(-0.5, 0.5))));
            const s = rng.uniform(0.16, 0.3);
            const mm = rng.random() < 0.85 ? 'leaf' : 'leaf_dry';
            b.poly([V.sub(V.sub(o, V.mul(a1, s)), V.mul(a2, s * 0.5)), V.sub(V.add(o, V.mul(a1, s)), V.mul(a2, s * 0.5)), V.add(o, V.mul(a2, s * 1.3))], mm);
        }
    }
    return b;
}

// ================================================================================================ small things
// an offset dish on its pole: built looking along -y and up; the town turns every one the same way
export function dish(dark = false, size = 1.0) {
    const b = new MB();
    const m = dark ? 'dish_dark' : 'dish';
    b.tube([0.0, 0.06, 0.0], [0.0, 0.06, 0.95], 0.028, 'steel_dark', { n: 6 });
    const c = [0.0, -0.1, 1.02];
    const M = place(c, 0.0, 52.0 * Math.PI / 180, 0.0, size);
    const R = 0.5;
    b.lathe([[0.03, 0.0003], [0.2, 0.0125], [0.36, 0.04], [R, 0.078]], [0.0, 0.0, 0.0], m, { n: 16, M });
    b.lathe([[R, 0.078], [R + 0.012, 0.07], [R, 0.062]], [0.0, 0.0, 0.0], m, { n: 16, M });          // its rolled rim
    b.box([-0.07, -0.02, 0.9], [0.07, 0.1, 1.06], 'steel_dark');                                    // the clamp behind it
    const a = M4.apply(M, [0.0, -R, 0.078]), f = M4.apply(M, [0.0, -0.12, 0.66]);
    b.beam(a, f, 0.02, 0.02, 'steel_dark');
    b.lathe([[0.03, -0.05], [0.035, 0.0], [0.03, 0.07], [0.015, 0.09]], [0.0, 0.0, 0.0], 'plastic_white', { n: 6, M: place(f, 0.0, (52.0 + 180.0) * Math.PI / 180) });
    return b;
}

// a concrete pole 9.5 m: two arms across the street's line with their insulators; some carry a transformer, some a
// lamp on an arm. Its wires hang from (0, -0.8 | 0 | 0.8, 9.1) and (0, -0.5 | 0.5, 8.35): the layout strings them
export function pole(rng, kind = 'plain') {
    const b = new MB();
    b.tube([0, 0, -0.3], [0, 0, 9.5], 0.17, 'pole', { n: 8, r1: 0.10 });
    for (const [z, half] of [[8.95, 0.9], [8.2, 0.6]]) {
        b.beam([0, -half, z], [0, half, z], 0.07, 0.07, 'steel_dark');
        for (const sy of [-1, 1]) b.beam([0.0, sy * half * 0.7, z], [0.0, sy * 0.1, z - 0.45], 0.012, 0.04, 'steel_dark');
    }
    for (const [y, z] of [[-0.8, 8.95], [0.0, 9.5], [0.8, 8.95], [-0.5, 8.2], [0.5, 8.2]])
        b.lathe([[0.03, 0.0], [0.05, 0.04], [0.03, 0.07], [0.05, 0.1], [0.02, 0.14]], [0.0, y, z < 9.4 ? z + 0.035 : z - 0.04], 'insulator', { n: 6 });
    if (kind === 'transformer') {
        b.beam([-0.45, -0.3, 5.6], [0.45, -0.3, 5.6], 0.06, 0.06, 'steel_dark');
        b.beam([-0.45, 0.3, 5.6], [0.45, 0.3, 5.6], 0.06, 0.06, 'steel_dark');
        b.box([0.2, -0.28, 5.63], [0.78, 0.28, 6.5], 'zinc_old');
        for (let q = 0; q < 5; q++) b.box([0.78, -0.24 + q * 0.12, 5.7], [0.86, -0.22 + q * 0.12, 6.4], 'zinc_old', { skip: 'x-' });   // its fins
        for (const q of [-0.15, 0.0, 0.15]) {
            b.lathe([[0.03, 0.0], [0.05, 0.06], [0.03, 0.12], [0.05, 0.18], [0.015, 0.24]], [0.5, q, 6.5], 'insulator', { n: 6 });
            b.path([[0.5, q, 6.74], [0.25, q * 2.0, 7.6], [0.0, q * 3.3, 8.2]], 0.008, 'wire', { n: 3 });
        }
    } else if (kind === 'lamp') {
        const side = rng.choice([-1.0, 1.0]);
        b.path([[0, 0, 7.6], [0, side * 0.5, 8.0], [0, side * 1.2, 8.15], [0, side * 1.8, 8.12]], 0.03, 'steel_dark', { n: 5 });
        b.box([-0.13, side * 1.8 - 0.32, 8.03], [0.13, side * 1.8 + 0.32, 8.14], 'lamp_head', { mats: { 'z-': 'lamp_clear' } });
    }
    return b;
}

// a road's lamp: a tapered steel column of 9 m, one arm or two over the lanes, a lantern at each
export function lampPost(two = true) {
    const b = new MB();
    b.box([-0.2, -0.2, 0.0], [0.2, 0.2, 0.25], 'concrete', { skip: 'z-' });
    b.tube([0, 0, 0.2], [0, 0, 9.0], 0.11, 'zinc', { n: 8, r1: 0.055 });
    for (const side of (two ? [-1.0, 1.0] : [1.0])) {
        b.path([[0, 0, 8.9], [0, side * 0.35, 9.35], [0, side * 1.0, 9.55], [0, side * 1.7, 9.5]], 0.035, 'zinc', { n: 5 });
        b.box([-0.14, Math.min(side * 1.5, side * 2.25), 9.4], [0.14, Math.max(side * 1.5, side * 2.25), 9.53], 'lamp_head', { mats: { 'z-': 'lamp_clear' } });
    }
    return b;
}

// a child's bicycle: 16 inch wheels, a diamond frame, its bars, its saddle, two small wheels to hold it up
export function bicycle(m = 'bike_red') {
    const b = new MB();
    const r = 0.2;
    const wheel = (x, rr = r, y = 0.0, n = 14) => {
        const M = place([x, y, rr], 0.0, Math.PI / 2.0);
        b.lathe([[rr - 0.03, -0.014], [rr - 0.006, -0.02], [rr, 0.0], [rr - 0.006, 0.02], [rr - 0.03, 0.014], [rr - 0.034, 0.0], [rr - 0.03, -0.014]], [0, 0, 0], 'tyre', { n, M });
        for (let q = 0; q < 4; q++) {
            const a = q * Math.PI / 4.0;
            const d = V.mul([Math.cos(a), 0.0, Math.sin(a)], rr - 0.03);
            b.beam(V.sub([x, y, rr], d), V.add([x, y, rr], d), 0.004, 0.004, 'chrome');
        }
    };
    wheel(-0.36);
    wheel(0.36);
    const ra = [-0.36, 0, 0.2], bb = [-0.03, 0, 0.21], sc = [-0.15, 0, 0.5], ht = [0.24, 0, 0.56], hb = [0.265, 0, 0.44], fa = [0.36, 0, 0.2];
    for (const [a, c, rad] of [[ra, bb, 0.011], [bb, sc, 0.015], [sc, ht, 0.014], [bb, hb, 0.016], [ra, sc, 0.009], [hb, fa, 0.012], [ht, hb, 0.017]]) b.tube(a, c, rad, m, { n: 5 });
    b.tube(sc, V.add(sc, [-0.035, 0, 0.1]), 0.011, 'chrome', { n: 5 });
    b.box([-0.3, -0.05, 0.6], [-0.1, 0.05, 0.635], 'tyre');
    b.tube(ht, V.add(ht, [-0.02, 0, 0.12]), 0.011, 'chrome', { n: 5 });
    b.beam([0.22, -0.2, 0.68], [0.22, 0.2, 0.68], 0.02, 0.02, 'chrome');
    for (const sy of [-1, 1]) {
        b.box([0.19, sy * 0.2 - 0.04, 0.665], [0.25, sy * 0.2 + 0.04, 0.695], 'tyre');
        b.beam([-0.03, sy * 0.05, 0.21], [-0.03 + sy * 0.08, sy * 0.07, 0.21 - sy * 0.06], 0.012, 0.012, 'chrome');
        b.box([-0.06 + sy * 0.08, sy * 0.06, 0.2 - sy * 0.06 - 0.01], [0.0 + sy * 0.08, sy * 0.12, 0.2 - sy * 0.06 + 0.01], 'tyre');
        b.beam([-0.36, sy * 0.02, 0.2], [-0.36, sy * 0.15, 0.06], 0.01, 0.01, 'chrome');
        wheel(-0.36, 0.055, sy * 0.15, 8);
    }
    return b;
}

// a market stall: four poles, an awning lashed over them and sagging, a table under it, crates of what is sold
export function stall(rng) {
    const b = new MB();
    const w = rng.uniform(2.2, 3.2), d = rng.uniform(1.6, 2.2);
    const hf = rng.uniform(2.0, 2.3), hb = rng.uniform(2.3, 2.6);
    for (const x of [-w / 2, w / 2]) {
        b.tube([x, -d / 2, 0], [x, -d / 2, hf], 0.022, 'steel_dark', { n: 5 });
        b.tube([x, d / 2, 0], [x, d / 2, hb], 0.022, 'steel_dark', { n: 5 });
    }
    const am = rng.choice(['awn:0', 'awn:1', 'awn:2', 'awn:3', 'awn:4', 'awn:5', 'tarp_blue', 'tarp_sand', 'tarp_white', 'tarp_green']);
    const nu = 5, nv = 4;
    const sag = rng.uniform(0.06, 0.2);
    const P = [];
    for (let j = 0; j <= nv; j++) {
        const row = [];
        for (let i = 0; i <= nu; i++) row.push([-w / 2 - 0.25 + (w + 0.5) * i / nu, -d / 2 - 0.35 + (d + 0.5) * j / nv,
            hf + (hb - hf) * j / nv - sag * Math.sin(Math.PI * i / nu) * Math.sin(Math.PI * j / nv) - (j === 0 ? 0.12 : 0.0)]);
        P.push(row);
    }
    b.grid(P, am, { smooth: true });
    b.box([-w / 2 + 0.1, -d / 2 + 0.1, 0.72], [w / 2 - 0.1, d / 2 - 0.5, 0.76], 'wood_pale');
    for (const x of [-w / 2 + 0.15, w / 2 - 0.15]) for (const y of [-d / 2 + 0.15, d / 2 - 0.55]) b.beam([x, y, 0.0], [x, y, 0.72], 0.04, 0.04, 'wood', { up: [1.0, 0.0, 0.0] });
    let x = -w / 2 + 0.3;
    while (x < w / 2 - 0.5) {
        const cw = rng.uniform(0.4, 0.6);
        const y0 = rng.uniform(-d / 2 + 0.15, -d / 2 + 0.3);
        let z = 0.76;
        const nl = rng.randrange(1, 3);
        for (let lay = 0; lay < nl; lay++) {
            const mm = rng.choice(['crate', 'wood_pale', 'plastic_red', 'plastic_blue']);
            const top = rng.choice(['fruit_orange', 'fruit_red', 'fruit_green', 'fruit_yellow', 'fruit_green']);
            b.box([x, y0, z], [x + cw, y0 + 0.36, z + 0.2], mm, { skip: 'z-', top });
            z += 0.2;
        }
        x += cw + rng.uniform(0.03, 0.15);
    }
    const ns = rng.randrange(0, 4);
    for (let i = 0; i < ns; i++) {                                   // sacks on the ground by it
        const sx = rng.uniform(-w / 2, w / 2), sy = d / 2 - rng.uniform(0.0, 0.4);
        b.lathe([[0.02, 0.0], [0.24, 0.04], [0.3, 0.2], [0.26, 0.42], [0.1, 0.55], [0.02, 0.56]], [sx, sy, 0.0], 'sack', { n: 8 });
    }
    return b;
}

// one section of a blast wall: 3.6 m of concrete on a spread foot, a lifting eye's recess at its head
export function tWall() {
    const b = new MB();
    const prof = [[-0.6, 0.0], [0.6, 0.0], [0.6, 0.25], [0.18, 0.7], [0.12, 3.6], [-0.12, 3.6], [-0.18, 0.7], [-0.6, 0.25]];
    for (let i = 0; i < prof.length; i++) {
        const [ya, za] = prof[i], [yb, zb_] = prof[(i + 1) % prof.length];
        b.quad([0.6, ya, za], [-0.6, ya, za], [-0.6, yb, zb_], [0.6, yb, zb_], 'concrete');
    }
    b.poly([...prof].reverse().map(([y, z]) => [-0.6, y, z]), 'concrete');
    b.poly(prof.map(([y, z]) => [0.6, y, z]), 'concrete');
    return b;
}

// ================================================================================================ the mosque
// a pointed opening in a wall already built round its box (a0..a1, b0..its point): the two spandrels that make the box
// an arch, its curved reveal, its jambs, and what stands at its back
function arch(b, P, a0, a1, b0, bs, depth, m, back, n = 5) {
    const am = (a0 + a1) / 2.0, hw = (a1 - a0) / 2.0;
    const rise = hw * 1.1;
    const bt = bs + rise;
    const left = [];
    for (let k = 0; k <= n; k++) {
        const t = 90.0 * k / n * Math.PI / 180;
        left.push([am - hw * Math.cos(t) ** 0.8, bs + rise * Math.sin(t)]);
    }
    const right = [...left].reverse().map(([a, z]) => [2 * am - a, z]);
    b.poly([...left.map(([a, z]) => P(a, z)), P(a0, bt)], m);
    b.poly([...right.map(([a, z]) => P(a, z)), P(a1, bt)], m);
    const curve = [...left, ...right.slice(1)];
    for (let i = 0; i < curve.length - 1; i++) {
        const [a_, z_] = curve[i], [c_, y_] = curve[i + 1];
        b.quad(P(a_, z_, depth), P(c_, y_, depth), P(c_, y_), P(a_, z_), m);
    }
    b.quad(P(a0, b0), P(a0, b0, depth), P(a0, bs, depth), P(a0, bs), m);
    b.quad(P(a1, b0, depth), P(a1, b0), P(a1, bs), P(a1, bs, depth), m);
    b.quad(P(a0, b0), P(a1, b0), P(a1, b0, depth), P(a0, b0, depth), m);
    b.poly([P(a0, b0, depth), P(a1, b0, depth), ...[...curve].reverse().map(([a, z]) => P(a, z, depth))], back);
    return bt;
}

// a wall with pointed openings [(a0, a1, b0, springing, depth, what stands at its back)]
function archedWall(b, P0, u, n, L, z0, h, m, ops) {
    const P = (a, bb, dp = 0.0) => [P0[0] + u[0] * a - n[0] * dp, P0[1] + u[1] * a - n[1] * dp, z0 + bb];
    const r6 = (x) => parseFloat(x.toFixed(6));
    const boxes = ops.map((o) => [o[0], o[1], o[2], o[3] + (o[1] - o[0]) / 2.0 * 1.1].map(r6));
    const xs = [...new Set([0.0, r6(L), ...boxes.flatMap((o) => o.slice(0, 2))])].sort((a, c) => a - c);
    const zs = [...new Set([0.0, r6(h), ...boxes.flatMap((o) => o.slice(2))])].sort((a, c) => a - c);
    for (let i = 0; i < xs.length - 1; i++) {
        for (let j = 0; j < zs.length - 1; j++) {
            const a0 = xs[i], a1 = xs[i + 1], b0 = zs[j], b1 = zs[j + 1];
            if (boxes.some((o) => o[0] <= a0 + 1e-6 && a1 <= o[1] + 1e-6 && o[2] <= b0 + 1e-6 && b1 <= o[3] + 1e-6)) continue;
            b.quad(P(a0, b0), P(a1, b0), P(a1, b1), P(a0, b1), m);
        }
    }
    for (const o of ops) arch(b, P, o[0], o[1], o[2], o[3], o[4], m, o[5]);
    return P;
}

// a dome that swells a little past its drum and draws up to a point; its finial
function pointedDome(b, c, r, m, n = 20, tall = 1.15) {
    const prof = [[r, 0.0], [r * 1.05, r * 0.14], [r * 1.04, r * 0.34], [r * 0.94, r * 0.58], [r * 0.74, r * 0.82], [r * 0.48, r * 1.0], [r * 0.22, r * 1.11], [0.04, r * tall + 0.02]];
    b.lathe(prof, c, m, { n });
    const zt = r * tall;
    b.lathe([[0.03, 0.0], [0.03, 0.16 * r], [0.09 * r, 0.21 * r], [0.03, 0.27 * r], [0.06 * r, 0.32 * r], [0.02, 0.37 * r], [0.02, 0.52 * r]], [c[0], c[1], c[2] + zt], 'gold', { n: 8 });
}

export function mosque(rng) {
    const b = new MB();
    const MQ = 'mosque', CO = 'concrete';
    const W = 14.0, D = 12.0, HH = 6.6;
    const walls = [[[0, 0], [1, 0], [0, -1], W], [[W, 0], [0, 1], [1, 0], D], [[W, D], [-1, 0], [0, 1], W], [[0, D], [0, -1], [-1, 0], D]];
    walls.forEach(([P0, u, n, L], q) => {
        const k = L > 13 ? 4 : 3;
        let ops = [...Array(k).keys()].map((i) => [L * (i + 0.5) / k - 0.6, L * (i + 0.5) / k + 0.6, 1.5, 3.9, 0.22, 'glass']);
        if (q === 0) ops = ops.filter((o) => Math.abs((o[0] + o[1]) / 2.0 - L / 2.0) > 2.6);     // the portal stands before it
        archedWall(b, P0, u, n, L, 0.3, HH - 0.3, MQ, ops);
    });
    b.box([-0.25, -0.25, 0.0], [W + 0.25, D + 0.25, 0.3], CO, { skip: 'z-' });                    // its plinth
    b.box([-0.3, -0.3, HH], [W + 0.3, D + 0.3, HH + 0.35], MQ, { skip: 'z-', top: 'roof' });      // its cornice and roof
    const ring = [[-0.3, -0.3], [W + 0.3, -0.3], [W + 0.3, D + 0.3], [-0.3, D + 0.3]];
    b.run(ring, 0.25, HH + 0.35, HH + 1.1, MQ, { closed: true });
    b.run(ring, 0.25, HH + 1.1, HH + 1.18, 'tile_band', { closed: true });
    // the portal: a tall gate standing proud of the hall, a pointed recess in it with the doors at its back
    const px0 = W / 2 - 2.6, px1 = W / 2 + 2.6, pd = 1.3, ph = 8.4;
    for (const [P0, u, n, L, ops] of [[[px0, -pd], [1, 0], [0, -1], px1 - px0, [[1.0, 4.2, 0.0, 4.2, 0.9, 'door_green']]], [[px1, -pd], [0, 1], [1, 0], pd, []],
        [[px0, 0.0], [0, -1], [-1, 0], pd, []]]) archedWall(b, P0, u, n, L, 0.0, ph, MQ, ops);
    b.box([px0 - 0.12, -pd - 0.12, ph], [px1 + 0.12, 0.0, ph + 0.3], MQ, { skip: 'z-' });
    b.quad([px1, 0.0, HH], [px0, 0.0, HH], [px0, 0.0, ph], [px1, 0.0, ph], MQ);                    // its back, above the hall's roof
    b.quad([px0 + 0.5, -pd - 0.012, ph - 1.3], [px1 - 0.5, -pd - 0.012, ph - 1.3], [px1 - 0.5, -pd - 0.012, ph - 0.5], [px0 + 0.5, -pd - 0.012, ph - 0.5], 'tile_band');
    for (let q = 0; q < 3; q++) b.box([px0 + 0.6, -pd - 0.35 * (q + 1), 0.0], [px1 - 0.6, -pd - 0.35 * q, 0.3 * (3 - q) / 3.0], CO, { skip: 'z-y+' });   // its steps
    for (const sx of [px0 + 0.5, px1 - 0.5]) {                       // two small domes on the portal's shoulders
        b.lathe([[0.75, 0.0], [0.75, 0.5]], [sx, -pd / 2, ph + 0.3], MQ, { n: 12 });
        pointedDome(b, [sx, -pd / 2, ph + 0.8], 0.75, 'dome_blue', 12);
    }
    // the dome: an eight-sided drum with a band of tile, the pointed dome on it
    const cx = W / 2, cy = D / 2 + 0.5, r = 3.7;
    b.lathe([[r + 0.25, 0.0], [r + 0.25, 0.3], [r, 0.3], [r, 1.25]], [cx, cy, HH + 0.35], MQ, { n: 24 });
    b.lathe([[r + 0.02, 1.25], [r + 0.02, 1.75]], [cx, cy, HH + 0.35], 'tile_band', { n: 24 });
    b.lathe([[r + 0.1, 1.75], [r + 0.1, 1.95], [r, 1.95]], [cx, cy, HH + 0.35], MQ, { n: 24 });
    pointedDome(b, [cx, cy, HH + 2.3], r, 'dome', 24);
    for (let k = 0; k < 8; k++) {                                    // the drum's windows, between its piers
        const a = 2 * Math.PI * (k + 0.5) / 8;
        const M = place([cx + (r + 0.005) * Math.cos(a), cy + (r + 0.005) * Math.sin(a), HH + 0.75], a + Math.PI / 2.0);
        b.box([-0.3, -0.03, 0.0], [0.3, 0.03, 0.75], 'glass', { M });
    }
    // the minaret: a square foot, a tapering shaft with bands of tile, a gallery on corbels, a lantern, a pointed cap
    const mx = -1.9, my = D - 1.6;
    b.box([mx - 1.25, my - 1.25, 0.0], [mx + 1.25, my + 1.25, 4.2], MQ, { skip: 'z-' });
    b.lathe([[1.5, 4.2], [1.05, 5.0], [1.0, 9.0]], [mx, my, 0.0], MQ, { n: 12 });
    b.lathe([[1.01, 9.0], [1.0, 9.6]], [mx, my, 0.0], 'tile_band', { n: 12 });
    b.lathe([[0.99, 9.6], [0.92, 15.0], [1.1, 15.3], [1.1, 15.5], [1.45, 15.95], [1.55, 16.0], [1.55, 16.15], [0.8, 16.15]], [mx, my, 0.0], MQ, { n: 12 });
    for (let k = 0; k < 12; k++) {                                   // the gallery's rail: a kerb, posts, a rail
        const a0_ = 2 * Math.PI * k / 12, a1_ = 2 * Math.PI * (k + 1) / 12;
        const p = [mx + 1.5 * Math.cos(a0_), my + 1.5 * Math.sin(a0_), 0.0], q = [mx + 1.5 * Math.cos(a1_), my + 1.5 * Math.sin(a1_), 0.0];
        b.beam(V.add(p, [0, 0, 17.05]), V.add(q, [0, 0, 17.05]), 0.07, 0.07, MQ);
        b.beam(V.add(p, [0, 0, 16.15]), V.add(p, [0, 0, 17.05]), 0.06, 0.06, MQ, { up: [1.0, 0.0, 0.0] });
        b.beam(V.add(p, [0, 0, 16.6]), V.add(q, [0, 0, 16.6]), 0.04, 0.04, MQ);
    }
    b.lathe([[0.8, 16.15], [0.74, 19.4], [0.95, 19.6], [0.95, 19.75]], [mx, my, 0.0], MQ, { n: 12 });
    b.lathe([[0.76, 17.9], [0.76, 18.4]], [mx, my, 0.0], 'tile_band', { n: 12 });
    pointedDome(b, [mx, my, 19.75], 0.9, 'dome', 12, 1.6);
    for (let k = 0; k < 3; k++) {                                    // its loudspeakers, on the gallery
        const a = 0.6 + k * 2.1;
        const c = [mx + 1.45 * Math.cos(a), my + 1.45 * Math.sin(a), 17.25];
        b.lathe([[0.05, 0.0], [0.07, 0.12], [0.24, 0.42], [0.25, 0.45]], [0, 0, 0], 'speaker', { n: 10, M: place(c, a - Math.PI / 2.0, -Math.PI / 2.0) });
    }
    // its yard: a low wall with piers and a rail, open before the portal
    const X0 = -5.5, X1 = W + 4.5, Y0 = -7.0, Y1 = D + 3.0;
    const line = [[px0 - 0.5, Y0], [X0, Y0], [X0, Y1], [X1, Y1], [X1, Y0], [px1 + 0.5, Y0]];
    b.run([...line].reverse(), 0.3, 0.0, 0.7, MQ, { top: CO });
    for (let i = 0; i < line.length - 1; i++) {
        const a = line[i], c = line[i + 1];
        const d = [c[0] - a[0], c[1] - a[1], 0.0];
        const k = Math.max(1, Math.trunc(V.len(d) / 3.2));
        for (let q = 0; q <= k; q++) {
            const p = V.add([a[0], a[1], 0.0], V.mul(d, q / k));
            b.box([p[0] - 0.22, p[1] - 0.22, 0.0], [p[0] + 0.22, p[1] + 0.22, 2.0], MQ, { skip: 'z-' });
            if (q < k) {
                const p2 = V.add([a[0], a[1], 0.0], V.mul(d, (q + 1) / k));
                for (const z of [1.1, 1.75]) b.beam(V.add(p, [0, 0, z]), V.add(p2, [0, 0, z]), 0.04, 0.04, 'door_blue');
                for (let s = 1; s < 5; s++) {
                    const pm = V.lerp(p, p2, s / 5.0);
                    b.beam(V.add(pm, [0, 0, 0.7]), V.add(pm, [0, 0, 1.85]), 0.025, 0.025, 'door_blue', { up: [1.0, 0.0, 0.0] });
                }
            }
        }
    }
    return b;
}
