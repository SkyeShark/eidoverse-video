// eidoverse/sets/town/layout.js — the town's plan: every building, street, pole, car, palm and yard, as mesh builders
// placed many times. No three.js here: plan() returns designs (name -> mb.js builder) and placements; index.js turns
// them into instanced meshes. A port of the Blender edition's eidoblend.sets.town.layout, draw for draw: the same seed
// and extent plan the same town.
//
// THE TOWN'S OWN SPACE (+Z up): x along the main road (y = -14, 11 m wide, a kerbed median with lamps and palms),
// streets along x every 40-46 m (YSTREETS), cross streets along y every 46-78 m, extent (ex, ey) metres of blocks;
// z = 0 the ground. Beyond the blocks the town does not stop at a ruled line: its streets run on as tracks, and houses
// run on along them, fewer and further apart, each on its walled lot, among walled plots and palm groves.
//
// Every kind of thing draws from a stream of chance of its own (R(stream, k): the seed's), so changing one never moves
// another. Each building is made once (a pool of designs per kind) and placed many times. DAMAGE is an option, off by
// default: damage true places strikes from the seed (about one per 3 ha), or give [[x, y, reach], ...].
import { PyRandom, pyRound } from './pyrandom.js';
import { MB, catenary } from './mb.js';
import * as K from './kit.js';
import * as ST from './street.js';
import { House } from './house.js';

// the streets along x: [y, width]; the main road is the 11 m one. A town of another height keeps those inside it
export const YSTREETS = [[-146.0, 6.0], [-100.0, 6.0], [-58.0, 7.0], [-14.0, 11.0], [30.0, 7.0], [74.0, 6.0], [118.0, 6.0], [150.0, 6.0]];
export const MOSQUE = [-78.0, -22.0, 36.0, 71.0];                    // its square: x0, x1, y0, y1
export const DISH_TURN = 205.0 * Math.PI / 180 + Math.PI;            // every dish looks at the same satellite
export const ASPHALT_PAST = [30.0, 10.0];                            // how far the asphalt runs past the outer streets

// strikes placed by a stream of the seed: about one per 3.15 ha of blocks, each with its reach
export function planStrikes(rng, ex, ey, n = null) {
    n = n === null ? Math.max(1, pyRound(ex * ey / 31500.0)) : n;
    const out = [];
    for (let i = 0; i < 80 * n; i++) {
        if (out.length >= n) break;
        const x = rng.uniform(-ex / 2 + 20.0, ex / 2 - 20.0), y = rng.uniform(-ey / 2 + 10.0, ey / 2 - 10.0);
        const r = rng.uniform(28.0, 45.0);
        if (out.every(([a, b, c]) => Math.hypot(x - a, y - b) > 0.8 * (r + c))) out.push([pyRound(x, 1), pyRound(y, 1), pyRound(r, 1)]);
    }
    return out;
}

// where a bomb met the street: a dished pit with a lip of what it threw up, pieces thrown out round it
function crater(b, rng, cx, cy, r, z = 0.03) {
    const n = 18;
    const prof = [[1.9, 0.0], [1.45, 0.10], [1.12, 0.34], [0.94, 0.28], [0.7, 0.10], [0.42, 0.03], [0.15, 0.0]];
    const wob = [...Array(n)].map(() => rng.uniform(0.8, 1.2));
    const P = prof.map(([q, h]) => [...Array(n).keys()].map((k) => [cx + r * q * wob[k] * Math.cos(2 * Math.PI * k / n), cy + r * q * wob[k] * Math.sin(2 * Math.PI * k / n),
        z + h * (r / 3.0) * rng.uniform(0.7, 1.3) - (q > 1.8 ? 0.04 : 0.0)]));
    const base = b.verts(P.flat());
    for (let j = 0; j < prof.length - 1; j++) {
        for (let k = 0; k < n; k++) {
            const a = base + j * n + k, c_ = base + j * n + (k + 1) % n;
            b.face([a, c_, c_ + n, a + n], j >= 3 ? 'crater' : 'rubble', true);
        }
    }
    b.face([...Array(n).keys()].map((k) => base + (prof.length - 1) * n + k), 'crater', true);
    const np = Math.trunc(14 + 6 * r);
    for (let i = 0; i < np; i++) {
        const a = rng.uniform(0.0, 6.283), d = r * (0.9 + rng.random() ** 1.5 * 2.6);
        const s = rng.uniform(0.12, 0.5);
        const m = rng.choice(['rubble', 'concrete', 'road']), kd = rng.choice(['lump', 'shard']);
        K.chunk(b, rng, [cx + d * Math.cos(a), cy + d * Math.sin(a), z + s * 0.14], s, m, kd);
    }
}

// the plan of a town. opts: seed, extent [ex, ey], damage (false | true | [[x, y, reach]]), signs (the count of the
// prepared signs: 0 paints the boards plain), edge (metres past its blocks), ystreets, mosque ('auto' | null |
// [x0, x1, y0, y1]), log. -> { designs, placements, strikes, ystreets, xstreets, mosque, paved, sandReach, extent, seed }
export function plan({ seed = 7, extent = [840.0, 300.0], damage = false, signs = [], edge = 170.0, ystreets = null, mosque = 'auto', log = console.log } = {}) {
    const t0 = performance.now();
    const ex_ = +extent[0], ey = +extent[1];
    const R = (stream, k = 0) => new PyRandom(seed * 1000003 + stream * 7919 + k);
    let strikes;
    if (damage === true) strikes = planStrikes(R(14), ex_, ey);
    else if (damage) strikes = damage.map((s) => s.map(Number));
    else strikes = [];
    const YST = (ystreets || YSTREETS.filter((s) => Math.abs(s[0]) <= ey / 2 + 2.0)).map((s) => [...s]);
    if (YST.length < 2) throw new Error(`[town] extent ${extent}: it needs two streets along x at least; give ystreets`);
    let mq;
    if (mosque === 'auto') {
        const fits = MOSQUE[0] > -ex_ / 2 + 10 && MOSQUE[1] < ex_ / 2 - 10 && YST.slice(0, -1).some((a, i) => MOSQUE[2] > a[0] && MOSQUE[3] < YST[i + 1][0]);
        mq = fits ? [...MOSQUE] : null;
    } else mq = mosque ? [...mosque] : null;
    const struck = (x, y) => strikes.reduce((m, [sx, sy, sr]) => Math.min(m, Math.hypot(x - sx, y - sy) / sr), 1e9);
    const designs = new Map();                                       // name -> MB
    const placements = [];
    const put = (name, mesh, x, y, rot = 0.0, z = 0.0, kind = 'other') => {
        const o = { name, mesh, loc: [x, y, z], rot: [0.0, 0.0, rot], kind, tn: {} };
        placements.push(o);
        return o;
    };
    const design = (name, b) => { designs.set(name, b); return name; };
    const PX = ex_ / 2 + ASPHALT_PAST[0], PY = ey / 2 + ASPHALT_PAST[1];
    const sandReach = [ASPHALT_PAST[0] + 4.0, ASPHALT_PAST[1] + 2.0];
    // ---------------------------------------------------------------- the buildings, each made once
    const kinds = ['A', 'B', 'C'].concat(strikes.length ? ['HA', 'HC', 'SA', 'SC'] : []);
    const pools = { A: [], B: [], C: [], HA: [], HC: [], SA: [], SC: [] };
    const order = Object.keys(pools);
    let r = R(1);
    const make = (pool, k, w, d, annex, floors, shops, dmg, low) => {
        if (!kinds.includes(pool)) return;
        const h = new House(R(10 + order.indexOf(pool), k), w, d, floors, { shops, dmg, low, annex, signs });
        const name = design(`town_${pool}_${String(k).padStart(2, '0')}`, h.b);
        pools[pool].push([name, h.anchors, w, h.d, h.zf[h.F]]);
    };
    const AX = [0.0, 3.4, 3.8, 4.4];                                 // how deep the low rooms behind a house run
    // (each call's arguments in Python's order: w, d, annex, floors, then the shop's draw where there is one)
    for (let k = 0; k < 11; k++) { const w = r.uniform(9.5, 17.0), d = r.uniform(9.0, 11.5), a = r.choice(AX), f = r.choice([2, 3, 3, 3, 4, 4, 5]); make('A', k, w, d, a, f, true, 0, false); }
    for (let k = 0; k < 9; k++) { const w = r.uniform(9.5, 16.0), d = r.uniform(8.6, 11.5), a = r.choice(AX), f = r.choice([2, 2, 3, 3, 4]); make('B', k, w, d, a, f, false, 0, false); }
    for (let k = 0; k < 14; k++) { const w = r.uniform(7.5, 12.5), d = r.uniform(6.8, 10.0), a = (k % 4) ? r.choice([...AX.slice(1), 0.0]) : 0.0, f = r.choice([1, 1, 2, 2]); make('C', k, w, d, a, f, false, 0, true); }
    [1, 1, 1, 2, 2, 2, 3, 3, 4].forEach((dm, k) => { const w = r.uniform(10.0, 17.0), d = r.uniform(9.0, 11.5), a = r.choice(AX), f = r.choice([2, 3, 3, 4, 4, 5]), s = r.random() < 0.6; make('HA', k, w, d, a, f, s, dm, false); });
    [2, 2, 3, 4, 4, 1].forEach((dm, k) => { const w = r.uniform(7.5, 12.0), d = r.uniform(6.8, 10.0), a = r.choice(AX), f = r.choice([1, 2, 2]); make('HC', k, w, d, a, f, false, dm, true); });
    for (let k = 0; k < 4; k++) { const w = r.uniform(9.5, 16.0), d = r.uniform(9.0, 11.5), a = r.choice(AX), f = r.choice([2, 3, 3, 4]), s = r.random() < 0.6; make('SA', k, w, d, a, f, s, 5, false); }
    for (let k = 0; k < 3; k++) { const w = r.uniform(7.5, 12.0), d = r.uniform(6.8, 10.0), a = r.choice(AX), f = r.choice([1, 2]); make('SC', k, w, d, a, f, false, 5, true); }
    log(`[town] ${Object.values(pools).reduce((s, v) => s + v.length, 0)} building designs in ${((performance.now() - t0) / 1000).toFixed(1)} s`);
    // ---------------------------------------------------------------- what is placed many times in the streets
    r = R(2);
    const cars = [design('car_saloon', ST.car('saloon')), design('car_saloon_b', ST.car('saloon')), design('car_pickup', ST.car('pickup')),
        design('car_pickup_sacks', ST.car('pickup', { load: 'sacks', rng: r })), design('car_pickup_boxes', ST.car('pickup', { load: 'boxes', rng: r })),
        design('car_van', ST.car('van'))];
    const wrecks = strikes.length ? [design('car_saloon_burnt', ST.car('saloon', { burnt: true })), design('car_pickup_burnt', ST.car('pickup', { burnt: true })),
        design('car_van_burnt', ST.car('van', { burnt: true }))] : [];
    const palms = [0, 1, 2, 3, 4].map((k) => design(`palm_${k}`, ST.palm(R(3, k))));
    const far_palms = [0, 1, 2].map((k) => design(`palm_far_${k}`, ST.palm(R(3, 10 + k), { light: true })));
    const trees = [0, 1, 2, 3].map((k) => design(`tree_${k}`, ST.tree(R(4, k))));    // the yard trees: the town's own
    const putTree = (name, x, y, rot, rng_) => put(name, trees[rng_.randrange(trees.length)], x, y, rot, 0.0, 'trees');
    const dishes = [design('dish', ST.dish(false)), design('dish_dark', ST.dish(true)), design('dish_big', ST.dish(false, 1.5))];
    const poles = {};
    ['plain', 'transformer', 'lamp'].forEach((k, i) => { poles[k] = design(`pole_${k}`, ST.pole(R(5, i), k)); });
    const lamp = design('lamp_post', ST.lampPost(true));
    const stalls = [0, 1, 2, 3, 4].map((k) => design(`stall_${k}`, ST.stall(R(6, k))));
    const bikes = [design('bicycle_red', ST.bicycle('bike_red')), design('bicycle_blue', ST.bicycle('bike_blue'))];
    const twall = strikes.length ? design('t_wall', ST.tWall()) : null;
    // ---------------------------------------------------------------- the streets
    let rng = R(7);
    const xstreets = [];
    let x = -ex_ / 2;
    while (x < ex_ / 2) {
        xstreets.push([x, rng.choice([5.0, 6.0, 6.0, 7.0])]);
        x += rng.uniform(46.0, 78.0);
    }
    const g = new MB();
    g.quad([-1600, -1600, 0], [1600, -1600, 0], [1600, 1600, 0], [-1600, 1600, 0], 'ground');
    for (const [yc, wd] of YST) g.quad([-PX, yc - wd / 2, 0.03], [PX, yc - wd / 2, 0.03], [PX, yc + wd / 2, 0.03], [-PX, yc + wd / 2, 0.03], 'road');
    for (const [xc, wd] of xstreets) g.quad([xc - wd / 2, -PY, 0.025], [xc + wd / 2, -PY, 0.025], [xc + wd / 2, PY, 0.025], [xc - wd / 2, PY, 0.025], 'road:y');
    const st = new MB();                                             // pavements, kerbs, yard walls, wires, what a strike left
    let n_b = 0, n_i = 0;
    const rows = new Map();                                          // each street side's buildings: (x0, x1, front line, how high)
    const houseAt = (pick, ox, oy, rot, in_town = true) => {         // a building placed by its front's left corner
        const [name, anchors, w, d, hz] = pick;
        const cs = Math.cos(rot), sn = Math.sin(rot);
        const o = put(`bld.${String(n_b).padStart(4, '0')}`, name, ox, oy, rot, 0.0, 'buildings');
        o.tn.dust = in_town ? Math.max(0.0, Math.min(1.0, 1.15 - struck(ox + cs * w / 2 - sn * d / 2, oy + sn * w / 2 + cs * d / 2) / 1.2)) : 0.0;
        Object.assign(o.tn, { w, d, h: hz, in: in_town ? 1 : 0 });
        n_b += 1;
        for (const [ax_, ay_, az_] of anchors) {
            if (rng.random() < (name[5] !== 'H' ? 0.85 : 0.4)) {
                const dk = dishes[rng.choice([0, 0, 1, 1, 1, 2])];
                put(`dish.${String(n_i).padStart(5, '0')}`, dk, ox + cs * ax_ - sn * ay_, oy + sn * ax_ + cs * ay_, DISH_TURN + rng.uniform(-0.12, 0.12), az_, 'dishes');
                n_i += 1;
            }
        }
        return o;
    };
    // on a street of the town: side 0, its front at yy looking -y; side 1, looking +y
    const house = (pick, x_, yy, side, in_town = true) => (side === 0 ? houseAt(pick, x_, yy, 0.0, in_town) : houseAt(pick, x_ + pick[2], yy, Math.PI, in_town));
    for (let bi = 0; bi < YST.length - 1; bi++) {
        const [ya, wa] = YST[bi], [yb, wb] = YST[bi + 1];
        const y0 = ya + wa / 2, y1 = yb - wb / 2;
        const pwa = wa > 9 ? 2.4 : 1.5, pwb = wb > 9 ? 2.4 : 1.5;    // the pavement: wider on the main road
        const ym = (y0 + y1) / 2.0;
        for (let xi = 0; xi < xstreets.length - 1; xi++) {
            const [xa, xwa] = xstreets[xi], [xb, xwb] = xstreets[xi + 1];
            const x0 = xa + xwa / 2, x1 = xb - xwb / 2;
            for (const [yy, sgn, pw] of [[y0, 1.0, pwa], [y1, -1.0, pwb]]) {     // a pavement and its banded kerb
                let [lo_, hi_] = [yy, yy + sgn * pw].sort((p, q) => p - q);
                st.box([x0, lo_, 0.0], [x1, hi_, 0.14], 'walk', { skip: 'z-' });
                [lo_, hi_] = [yy - sgn * 0.18, yy].sort((p, q) => p - q);
                st.box([x0 - 0.18, lo_, 0.0], [x1 + 0.18, hi_, 0.16], 'kerb', { skip: 'z-' });
            }
            const in_square = mq !== null && !(x1 < mq[0] || x0 > mq[1] || y1 < mq[2] || y0 > mq[3]);
            const wall_m = rng.choice(['block', 'plaster_w', 'plaster_w', 'brick']);
            if (!in_square) {
                st.run([[x0 + 0.3, ym - 0.1], [x1 - 0.3, ym - 0.1]], 0.2, 0.0, 2.1, wall_m, { top: 'concrete' });   // between the yards
                for (const xe of [x0 + 0.1, x1 - 0.3]) st.box([xe, y0 + pwa + 0.3, 0.0], [xe + 0.2, y1 - pwb - 0.3, 2.1], wall_m, { skip: 'z-', top: 'concrete' });
            }
            for (const [side, yy, yst, wst_] of [[0, y0 + pwa, ya, wa], [1, y1 - pwb, yb, wb]]) {
                x = x0 + rng.uniform(0.0, 1.5);
                const main = wst_ > 9, second = wst_ > 6.5;
                const deep = Math.abs(ym - yy) - 0.5;                // how deep a house may be here
                const dy = side === 0 ? 1.0 : -1.0;
                while (x < x1 - 7.5) {
                    if (rng.random() < 0.05) {                       // an empty lot: rubbish, a heap of spoil
                        const gap = rng.uniform(5.0, 10.0);
                        if (x + gap < x1 && !in_square) {
                            const hy = yy + dy * rng.uniform(3.0, 6.0), rx = rng.uniform(1.2, 2.4), ry = rng.uniform(1.0, 2.0), hh = rng.uniform(0.4, 0.9);
                            K.heap(st, rng, x + gap / 2, hy, rx, ry, hh, 0.0, { pieces: rng.randrange(6, 14), field: false, m: 'ground' });
                            if (rng.random() < 0.5) { const jx = x + gap * rng.uniform(0.2, 0.8), jy = yy + dy * rng.uniform(1.0, 3.0); K.junk(st, rng, jx, jy, 0.0); }
                        }
                        x += gap;
                        continue;
                    }
                    const lowrow = (!main) && (rng.random() < (second ? 0.3 : 0.75));
                    let pool = null;
                    if (strikes.length) {
                        const s_ = struck(x + 6.0, yy + dy * 5.0);
                        if ((s_ < 0.75 && rng.random() < 0.9) || (s_ < 1.15 && rng.random() < 0.55)) pool = lowrow ? 'HC' : 'HA';
                        else if ((s_ < 1.9 && rng.random() < 0.5) || rng.random() < 0.015) pool = lowrow ? 'SC' : 'SA';
                    }
                    if (pool === null) {
                        if (lowrow) pool = 'C';
                        else pool = ((main && rng.random() < 0.85) || (second && rng.random() < 0.45)) ? 'A' : 'B';
                    }
                    let fit = pools[pool].filter((q) => q[3] <= deep);
                    if (!fit.length) fit = [pools[pool].reduce((m, q) => (q[3] < m[3] ? q : m))];
                    const pick = fit[rng.randrange(fit.length)];
                    const [, , w, d, hz] = pick;
                    if (x + w > x1) break;
                    if (in_square && !(x + w < mq[0] || x > mq[1] || (side === 0 ? yy + d : yy) < mq[2] || (side === 0 ? yy : yy - d) > mq[3])) {
                        x += w + 1.0;                                // the mosque's square is kept clear
                        continue;
                    }
                    house(pick, x, yy, side);
                    const rk = `${yst},${side}`;
                    if (!rows.has(rk)) rows.set(rk, []);
                    rows.get(rk).push([x, x + w, yy, hz]);
                    // its yard, what is left of the lot behind it: its own ground, a wall down one side, what is kept there
                    const yback = yy + dy * d;
                    const depth = Math.abs(ym - yback) - 0.1;
                    const gap = rng.choice([0.0, 0.0, 0.0, 1.2, 2.5]);
                    if (depth > 0.8 && !in_square) {
                        const [lo_, hi_] = [yback, ym - 0.1 * dy].sort((p, q) => p - q);
                        st.quad([x, lo_, 0.012], [x + w + gap, lo_, 0.012], [x + w + gap, hi_, 0.012], [x, hi_, 0.012], rng.random() < 0.22 ? 'walk' : 'yard');
                        st.box([x - 0.1, lo_, 0.0], [x + 0.1, hi_, rng.uniform(1.8, 2.3)], wall_m, { skip: 'z-y-y+', top: 'concrete' });
                        if (depth > 2.4) {
                            const cx_ = x + rng.uniform(1.5, Math.max(1.6, w - 1.5)), cy_ = yback + dy * rng.uniform(1.2, Math.max(1.3, depth - 1.2));
                            const k = rng.random();
                            if (k < 0.26) putTree(`tree.${String(n_i).padStart(5, '0')}`, cx_, cy_, rng.uniform(0, 6.28), rng);
                            else if (k < 0.46) { const pm = palms[rng.randrange(palms.length)]; put(`palm.${String(n_i).padStart(5, '0')}`, pm, cx_, cy_, rng.uniform(0, 6.28), 0.0, 'palms'); }
                            else if (k < 0.54 && depth > 5.0 && w > 6.0) {
                                const cm = cars[rng.randrange(cars.length)];
                                const rz = rng.choice([0.0, Math.PI]) + rng.uniform(-0.1, 0.1);
                                put(`car.${String(n_i).padStart(5, '0')}`, cm, x + w / 2, yback + dy * depth / 2, rz, 0.0, 'cars');
                            } else if (k < 0.64 && depth > 3.2) {    // a shed against the back wall, a sheet of zinc for its roof
                                const sx_ = x + rng.uniform(0.3, Math.max(0.4, w - 4.0)), sw_ = rng.uniform(2.4, 3.6);
                                const [ya_, yb_] = [ym - dy * 0.2, ym - dy * Math.min(2.6, depth - 0.4)].sort((p, q) => p - q);
                                st.box([sx_, ya_, 0.0], [sx_ + sw_, yb_, 2.1], 'block', { skip: 'z-' });
                                st.box([sx_ - 0.2, ya_ - 0.2, 2.1], [sx_ + sw_ + 0.2, yb_ + 0.2, 2.16], 'zinc_old');
                            } else if (k < 0.80) K.junk(st, rng, cx_, cy_, 0.0);
                            else if (k < 0.90 && depth > 3.0) K.washing(st, rng, [x + 0.8, cy_], [x + Math.min(w - 0.8, 5.5), cy_], 0.0, { lines: 1 });
                            n_i += 1;
                            if (rng.random() < 0.04) {               // a child's bicycle, left where it was dropped
                                const bx = x + rng.uniform(1.0, w - 1.0), by = yback + dy * rng.uniform(0.6, 1.2);
                                const o = put(`bicycle.${String(n_i).padStart(5, '0')}`, bikes[rng.randrange(2)], bx, by, 0.0, 0.15);
                                o.rot = [82.0 * Math.PI / 180, 0.0, rng.uniform(0, 6.28)];
                            }
                        }
                    }
                    if (gap > 0.0 && !in_square) {                   // the passage beside it: closed by a wall and a steel gate
                        const [yf0, yf1] = [yy, yy + dy * 0.2].sort((p, q) => p - q);
                        st.box([x + w, yf0, 0.0], [x + w + gap, yf1, 2.2], wall_m, { skip: 'z-x-x+', top: 'concrete' });
                        st.box([x + w + 0.15, yf0 - 0.03, 0.05], [x + w + gap - 0.15, yf0 + 0.02, 1.95], rng.choice(['door_green', 'door_blue', 'door_grey', 'door_rust']), { skip: 'y+' });
                    }
                    x += w + gap;
                }
            }
        }
    }
    log(`[town] ${n_b} buildings placed on ${YST.length - 1} rows of blocks, ${xstreets.length} cross streets (${((performance.now() - t0) / 1000).toFixed(1)} s)`);
    // ---------------------------------------------------------------- the mosque on its square; the market beside it
    rng = R(8);
    if (mq !== null) {
        put('mosque', design('mosque', ST.mosque(rng)), mq[0] + 20.0, mq[2] + 12.0, 0.0);
        st.box([mq[0], mq[2], 0.0], [mq[1], mq[3], 0.12], 'walk', { skip: 'z-' });
        for (let k = 0; k < 6; k++) {
            const px = mq[0] + 4.0 + k * 9.6 + rng.uniform(-1.0, 1.0);
            put(`palm.sq${k}`, palms[k % palms.length], px, mq[2] + 2.2 + (k % 2) * 1.2, rng.uniform(0, 6.28), 0.0, 'palms');
        }
        for (let k = 0; k < 9; k++) {                                // stalls down the square's open side and along its street
            const sm = stalls[rng.randrange(stalls.length)];
            const px = mq[1] - 4.0 - (k % 2) * 4.4 + rng.uniform(-0.4, 0.4), py = mq[2] + 7.0 + Math.trunc(k / 2) * 5.6 + rng.uniform(-0.5, 0.5);
            put(`stall.sq${k}`, sm, px, py, Math.PI / 2 * (k % 2 ? 1 : -1) + rng.uniform(-0.12, 0.12), 0.12, 'stalls');
        }
        const below = YST.filter((s) => s[0] < mq[2]);
        const ys_ = below.length ? below.reduce((m, s) => (s[0] > m[0] ? s : m)) : null;
        if (ys_ !== null) {
            for (let k = 0; k < 7; k++) {
                const sm = stalls[rng.randrange(stalls.length)];
                const px = mq[0] - 40.0 + k * 4.8 + rng.uniform(-0.5, 0.5);
                put(`stall.st${k}`, sm, px, ys_[0] + ys_[1] / 2 - 1.3, rng.uniform(-0.1, 0.1), 0.03, 'stalls');
            }
        }
    }
    // ---------------------------------------------------------------- poles and their wires; lamps; cars; palms
    rng = R(9);
    for (const [yc, wd] of YST) {
        const main = wd > 9;
        let prev = null;
        x = -ex_ / 2 + rng.uniform(0, 20);
        const py = yc + wd / 2 + 0.7;
        while (x < ex_ / 2) {
            if (xstreets.some(([xc, xw]) => Math.abs(x - xc) < xw / 2 + 1.0)) x += 4.0;
            const fallen = strikes.length > 0 && struck(x, py) < 0.55 && rng.random() < 0.6;
            const kind = !main ? rng.choice(['plain', 'plain', 'plain', 'transformer', 'lamp', 'lamp']) : rng.choice(['plain', 'plain', 'transformer']);
            const o = put(`pole.${Math.trunc(x)}.${Math.trunc(yc)}`, poles[kind], x, py, 0.0, 0.0, 'poles');
            if (fallen) {                                            // brought down across the street, its wires with it
                const a = rng.uniform(62.0, 84.0) * Math.PI / 180 * rng.choice([-1, 1]);
                o.rot = [a, 0.0, rng.uniform(-0.5, 0.5)];
                prev = null;
            } else {
                if (prev !== null) {
                    for (const [dy, z] of [[-0.8, 9.1], [0.0, 9.62], [0.8, 9.1], [-0.5, 8.36], [0.5, 8.36]])
                        st.path(catenary([prev, py + dy, z], [x, py + dy, z], rng.uniform(0.35, 0.9), 6), 0.014, 'wire', { n: 3 });
                }
                prev = x;
                const nq = rng.randrange(0, 3);
                for (let q = 0; q < nq; q++) {                       // a line down to a house on each side
                    const side = rng.choice([0, 1]);
                    const hits = (rows.get(`${yc},${1 - side}`) || []).filter((f) => f[0] - 4.0 < x && x < f[1] + 4.0);
                    if (hits.length) {
                        const f = hits[0];
                        const tx = Math.min(Math.max(x + rng.uniform(-5.0, 5.0), f[0] + 0.5), f[1] - 0.5);
                        const tz = Math.min(f[3] - 0.3, rng.uniform(3.5, 7.5));
                        st.path(catenary([x, py, 8.3], [tx, f[2], tz], rng.uniform(0.3, 0.8), 5), 0.008, 'wire', { n: 3 });
                    }
                }
            }
            x += rng.uniform(26.0, 34.0);
        }
        if (main) {                                                  // the main road's median: kerbed, a lamp every 32 m
            const edges = [-PX, ...xstreets.flatMap(([xc, xw]) => [xc - xw / 2 - 1.5, xc + xw / 2 + 1.5]), PX].sort((p, q) => p - q);
            for (let i = 0; i + 1 < edges.length; i += 2) {
                const a = edges[i], e = edges[i + 1];
                if (e - a < 3.0) continue;
                st.box([a, yc - 0.42, 0.0], [e, yc + 0.42, 0.18], 'median', { skip: 'z-' });
                st.run([[a, yc - 0.6], [e, yc - 0.6], [e, yc + 0.6], [a, yc + 0.6]], 0.18, 0.0, 0.2, 'kerb:y', { closed: true });
                let xl = a + rng.uniform(4.0, 10.0);
                while (xl < e - 3.0) {
                    if (struck(xl, yc) > 0.35) put(`lamp.${Math.trunc(xl)}`, lamp, xl, yc, 0.0, 0.0, 'lamps');
                    const xp = xl + 16.0 + rng.uniform(-3.0, 3.0);
                    if (xp < e - 2.0 && rng.random() < 0.6 && struck(xp, yc) > 0.5) {
                        const pm = palms[rng.randrange(palms.length)];
                        put(`palm.med${Math.trunc(xp)}`, pm, xp, yc, rng.uniform(0, 6.28), 0.15, 'palms');
                    }
                    xl += 32.0;
                }
            }
        }
        x = -ex_ / 2 + rng.uniform(0, 15);
        while (x < ex_ / 2) {                                        // cars at the kerb, a few on the move; wrecks where it struck
            const near = struck(x, yc);
            const burnt = wrecks.length > 0 && near < 1.0 && rng.random() < 0.6;
            const side = rng.choice([-1, 1]);
            if (burnt) {
                const wm = wrecks[rng.randrange(wrecks.length)];
                const py_ = yc + rng.uniform(-wd / 3, wd / 3);
                put(`car.${Math.trunc(x)}.${Math.trunc(yc)}`, wm, x, py_, rng.uniform(0, 6.28), 0.0, 'cars').tn.dust = 1.0;
            } else if (near > 0.5) {
                const moving = rng.random() < (main ? 0.3 : 0.12);
                const off = moving ? (wd / 4 + (main ? 0.3 : 0.0)) : (wd / 2 - 1.15);
                const cm = cars[rng.randrange(cars.length)];
                put(`car.${Math.trunc(x)}.${Math.trunc(yc)}`, cm, x, yc + side * off, (side > 0 ? Math.PI : 0.0) + rng.uniform(-0.04, 0.04), 0.03, 'cars');
            }
            x += rng.uniform(8.0, 36.0) * (main ? 0.6 : 1.0);
        }
    }
    // ---------------------------------------------------------------- where it struck: the street cratered and strewn
    rng = R(11);
    for (const [sx, sy, sr] of strikes) {
        const [yc, wd] = YST.reduce((m, s) => (Math.abs(s[0] - sy) < Math.abs(m[0] - sy) ? s : m));
        for (let q = 0; q < 2; q++) {                                // one crater in the nearest street, one where it fell
            let cx_, cy_;
            if (q === 0) { cx_ = sx + rng.uniform(-0.3, 0.3) * sr; cy_ = yc + rng.uniform(-0.25, 0.25) * wd; }
            else { cx_ = sx + rng.uniform(-0.4, 0.4) * sr; cy_ = sy + rng.uniform(-0.4, 0.4) * sr; }
            crater(st, rng, cx_, cy_, rng.uniform(1.8, 3.2));
        }
        const nh = rng.randrange(5, 9);
        for (let i = 0; i < nh; i++) {                               // what the buildings shed into the street
            const a = rng.uniform(0.0, 6.283), d = sr * rng.uniform(0.15, 0.9);
            const px = sx + d * Math.cos(a), py = sy + d * Math.sin(a);
            if (YST.some((s) => Math.abs(py - s[0]) < s[1] / 2 + 2.5) || xstreets.some((s) => Math.abs(px - s[0]) < s[1] / 2 + 1.0)) {
                const rx = rng.uniform(1.4, 3.0), ry = rng.uniform(1.2, 2.4), hh = rng.uniform(0.35, 0.9);
                K.heap(st, rng, px, py, rx, ry, hh, 0.03, { pieces: rng.randrange(10, 22), plates: rng.randrange(0, 2) });
            }
        }
    }
    if (strikes.length) {
        const ym_ = YST.reduce((m, s) => (s[1] > m[1] ? s : m));     // a line of blast walls on the main road
        for (let k = 0; k < 9; k++) put(`t_wall.${k}`, twall, 0.467 * ex_ / 2 + (k % 5) * 1.24, ym_[0] + (ym_[1] / 2 + 0.9) * (k < 5 ? 1 : -1), 0.0, 0.14);
    }
    // ---------------------------------------------------------------- the town's edge: it thins out, it does not stop
    rng = R(12);
    const X0 = -ex_ / 2 - 34.0, X1 = ex_ / 2 + 34.0, Y0 = -ey / 2 - 14.0, Y1 = ey / 2 + 14.0;
    const taken = [];
    const EDGE = +edge;
    const edgeSpot = (reach, r_) => {                                // a place past the town's edge, likelier near it than far
        for (let i = 0; i < 30; i++) {
            const d = EDGE * rng.random() ** 1.6 * reach + 6.0;
            let x_, y_;
            if (rng.random() < (ex_ + 2 * d) / (ex_ + ey + 4 * d)) { x_ = rng.uniform(X0 - d, X1 + d); y_ = rng.random() < 0.5 ? Y1 + d : Y0 - d; }
            else { x_ = rng.random() < 0.5 ? X1 + d : X0 - d; y_ = rng.uniform(Y0 - d, Y1 + d); }
            if (YST.some((s) => Math.abs(y_ - s[0]) < s[1] / 2 + r_ && (x_ < X0 || x_ > X1)) || xstreets.some((s) => Math.abs(x_ - s[0]) < s[1] / 2 + r_ && (y_ < Y0 || y_ > Y1))) continue;
            if (taken.every(([tx, ty, tr]) => Math.hypot(x_ - tx, y_ - ty) > r_ + tr)) { taken.push([x_, y_, r_]); return [x_, y_]; }
        }
        return null;
    };
    const lots = [];
    const lotFree = (bx) => lots.every((q) => bx[2] + 1.5 < q[0] || bx[0] - 1.5 > q[2] || bx[3] + 1.5 < q[1] || bx[1] - 1.5 > q[3]);
    const alongTrack = (axis, c0, wd, start, sgn, length) => {       // a track leaving the town at `start` toward sgn
        for (const side of [-1, 1]) {
            let s = rng.uniform(1.0, 12.0);
            while (s < length - 12.0) {
                const keep = (1.0 - s / length) ** 1.3;
                if (rng.random() > 0.12 + 0.7 * keep) { s += rng.uniform(8.0, 26.0); continue; }
                const pick = rng.random() < 0.8 ? pools.C[rng.randrange(pools.C.length)] : pools.B[rng.randrange(pools.B.length)];
                const w = pick[2], d = pick[3];
                const off = wd * 0.5 + rng.uniform(1.0, 3.5);        // from the track's middle to its front
                const a = sgn > 0 ? start + sgn * s : start + sgn * (s + w);
                let bx, at, front;
                if (axis === 'x') {
                    if (side > 0) { bx = [a, c0 + off, a + w, c0 + off + d]; at = [a, c0 + off, 0.0]; front = 'S'; }
                    else { bx = [a, c0 - off - d, a + w, c0 - off]; at = [a + w, c0 - off, Math.PI]; front = 'N'; }
                } else if (side > 0) { bx = [c0 + off, a, c0 + off + d, a + w]; at = [c0 + off, a + w, -Math.PI / 2]; front = 'W'; }
                else { bx = [c0 - off - d, a, c0 - off, a + w]; at = [c0 - off, a, Math.PI / 2]; front = 'E'; }
                const ms = rng.uniform(0.8, 3.0), mb = rng.uniform(2.5, 9.0);
                const lot = { S: [bx[0] - ms, bx[1], bx[2] + ms, bx[3] + mb], N: [bx[0] - ms, bx[1] - mb, bx[2] + ms, bx[3]],
                    W: [bx[0], bx[1] - ms, bx[2] + mb, bx[3] + ms], E: [bx[0] - mb, bx[1] - ms, bx[2], bx[3] + ms] }[front];
                if (!lotFree(lot)) { s += rng.uniform(4.0, 10.0); continue; }
                lots.push(lot);
                taken.push([(lot[0] + lot[2]) / 2, (lot[1] + lot[3]) / 2, 0.55 * Math.max(lot[2] - lot[0], lot[3] - lot[1])]);
                houseAt(pick, at[0], at[1], at[2], false);
                const c_ = [[lot[0], lot[1]], [lot[2], lot[1]], [lot[2], lot[3]], [lot[0], lot[3]]];
                const u_path = { S: [1, 2, 3, 0], N: [3, 0, 1, 2], W: [0, 1, 2, 3], E: [2, 3, 0, 1] }[front];    // its wall: round three sides
                const hw = rng.uniform(1.5, 2.2), wm = rng.choice(['block', 'block', 'plaster_w', 'brick']);
                st.run(u_path.map((q) => c_[q]), 0.2, 0.0, hw, wm, { top: 'concrete' });
                g.quad([lot[0], lot[1], 0.012], [lot[2], lot[1], 0.012], [lot[2], lot[3], 0.012], [lot[0], lot[3], 0.012], 'yard');
                const k = rng.random();
                const px = rng.uniform(lot[0] + 1.0, lot[2] - 1.0), py = rng.uniform(lot[1] + 1.0, lot[3] - 1.0);
                if (!(bx[0] - 1.0 < px && px < bx[2] + 1.0 && bx[1] - 1.0 < py && py < bx[3] + 1.0)) {
                    if (k < 0.4) { const pm = far_palms[rng.randrange(far_palms.length)]; put(`palm.e${lots.length}`, pm, px, py, rng.uniform(0, 6.28), 0.0, 'palms'); }
                    else if (k < 0.6) putTree(`tree.e${lots.length}`, px, py, rng.uniform(0, 6.28), rng);
                    else if (k < 0.75) K.junk(st, rng, px, py, 0.0);
                }
                s += w + 2 * ms + rng.uniform(0.5, 8.0);
            }
        }
    };
    const x_lo = xstreets[0][0] - xstreets[0][1] / 2 - 2.0, x_hi = xstreets[xstreets.length - 1][0] + xstreets[xstreets.length - 1][1] / 2 + 2.0;
    for (const [yc, wd] of YST) {
        for (const sgn of [-1.0, 1.0]) {
            const length = EDGE * rng.uniform(0.55, 1.0);
            const [a, e] = [sgn * PX, sgn * (PX + length)].sort((p, q) => p - q);
            g.quad([a, yc - wd * 0.35, 0.02], [e, yc - wd * 0.35, 0.02], [e, yc + wd * 0.35, 0.02], [a, yc + wd * 0.35, 0.02], 'track');
            const start = sgn > 0 ? x_hi : x_lo;
            alongTrack('x', yc, wd, start, sgn, length + PX - Math.abs(start));
        }
    }
    for (const [xc, wd] of xstreets) {
        for (const sgn of [-1.0, 1.0]) {
            const length = EDGE * rng.uniform(0.35, 0.95);
            const [a, e] = [sgn * PY, sgn * (PY + length)].sort((p, q) => p - q);
            g.quad([xc - wd * 0.35, a, 0.02], [xc + wd * 0.35, a, 0.02], [xc + wd * 0.35, e, 0.02], [xc - wd * 0.35, e, 0.02], 'track:y');
            alongTrack('y', xc, wd, sgn * (ey / 2 + 14.0), sgn, length);
        }
    }
    const n_plots = Math.max(1, pyRound(26 * (ex_ + ey) * EDGE / ((840.0 + 300.0) * 170.0)));
    for (let k = 0; k < n_plots; k++) {                              // walled plots: something growing, or nothing yet
        const w = rng.uniform(18.0, 46.0), d = rng.uniform(16.0, 40.0);
        const p = edgeSpot(1.0, Math.max(w, d) * 0.6);
        if (!p) continue;
        if (rng.random() < 0.7) {
            const hw = rng.uniform(0.9, 1.7), wm = rng.choice(['block', 'brick', 'plaster_w']);
            st.run([[p[0] - w / 2, p[1] - d / 2], [p[0] + w / 2, p[1] - d / 2], [p[0] + w / 2, p[1] + d / 2], [p[0] - w / 2, p[1] + d / 2]], 0.25, 0.0, hw, wm, { closed: true, top: 'concrete' });
        }
        const fm = rng.choice(['field', 'field', 'field_dry', 'yard']);
        const nrow = Math.max(2, Math.trunc(w / rng.uniform(4.0, 8.0)));
        for (let q = 0; q < nrow; q++) {                             // its beds, with the paths between them
            const xa_ = p[0] - w / 2 + 1.0 + (w - 2.0) * q / nrow, xb_ = p[0] - w / 2 + 1.0 + (w - 2.0) * (q + 1) / nrow - 0.7;
            g.quad([xa_, p[1] - d / 2 + 1.0, 0.015], [xb_, p[1] - d / 2 + 1.0, 0.015], [xb_, p[1] + d / 2 - 1.0, 0.015], [xa_, p[1] + d / 2 - 1.0, 0.015], fm);
        }
        const np = rng.randrange(0, 5);
        for (let q = 0; q < np; q++) {
            const pm = far_palms[rng.randrange(far_palms.length)];
            const px = p[0] + rng.uniform(-w / 2, w / 2), py = p[1] + rng.choice([-1, 1]) * (d / 2 - 1.0);
            put(`palm.f${k}.${q}`, pm, px, py, rng.uniform(0, 6.28), 0.0, 'palms');
        }
    }
    const n_groves = Math.max(1, pyRound(7 * n_plots / 26.0));
    for (let k = 0; k < n_groves; k++) {                             // palm groves
        const p = edgeSpot(0.9, 22.0);
        if (!p) continue;
        const nq = rng.randrange(9, 17);
        for (let q = 0; q < nq; q++) {
            const a = rng.uniform(0.0, 6.283), d = 20.0 * Math.sqrt(rng.random());
            const pm = far_palms[rng.randrange(far_palms.length)];
            put(`palm.g${k}.${q}`, pm, p[0] + d * Math.cos(a), p[1] + d * Math.sin(a), rng.uniform(0, 6.28), 0.0, 'palms');
        }
    }
    put('town_ground', design('town_ground', g), 0.0, 0.0, 0.0, 0.0, 'ground');
    put('town_streets', design('town_streets', st), 0.0, 0.0, 0.0, 0.0, 'streets');
    log(`[town] streets, edge and ground (${((performance.now() - t0) / 1000).toFixed(1)} s)`);
    // every placed thing its own number for how near a strike it stands (its materials lay the strike's fall by it)
    for (const o of placements) {
        if (o.tn.dust === undefined) o.tn.dust = (o.name === 'town_ground' || o.name === 'town_streets') ? 0.0 : Math.max(0.0, Math.min(1.0, 1.15 - struck(o.loc[0], o.loc[1]) / 1.2));
    }
    return { designs, placements, strikes, ystreets: YST, xstreets, mosque: mq, paved: [PX, PY], sandReach, extent: [ex_, ey], seed, struck, R };
}
