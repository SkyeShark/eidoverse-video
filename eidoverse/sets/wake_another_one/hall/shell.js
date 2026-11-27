// eidoverse/sets/wake_another_one/hall/shell.js — the hall's skin and what hangs on it: the walls, the dock's door,
// the services, the guards, the yard beyond the door. A port of the Blender edition's hall._shell.
//
// Called by look.js with X (the look's namespace: lay, M, L, the hall's numbers, fin, swap, model, say). Every part is
// a real section: profiled sheet with its ribs, precast panels with their joints, rolled steel with its flanges,
// plates with their bolts, channels, tubes with their bends. The detail pass (kit.finish) runs later in hall.js on
// every mesh that carries md.fin.
import { MB, c_section, i_section, meshData, PI } from './kit.js';

const RAD = (d) => d * PI / 180;
export const DADO_Z = 2.4;          // the precast dado's top: the profiled liner stands on it
export const DADO_T = 0.09;         // how far the dado stands into the hall
export const RIB = 0.040;           // how far the liner's crowns stand into the hall
export const TRAY_Z = 5.9;          // the cable tray's bottom

// numpy's arange for a float step
export function arange(a, b, s) { const out = []; for (let k = 0; ; k++) { const v = a + k * s; if (s > 0 ? v >= b : v <= b) break; out.push(v); } return out; }
export function linspace(a, b, n) { return [...Array(n).keys()].map((i) => a + (b - a) * i / (n - 1)); }
const V3 = { add: (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]], sub: (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]], mul: (a, k) => [a[0] * k, a[1] * k, a[2] * k],
    dot: (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2], cross: (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]] };

// ====================================================================================================== profiled sheet
// Profiled steel sheet as ONE open mesh: trapezoidal ribs every `pitch`, `depth` high. A run is a rectangle of sheet:
// [o, d, n, e, u0, u1, t0, t1] = origin, the direction across the ribs, the direction the ribs stand toward, the
// direction they run along, and its extent across (u) and along (t). UV = (u, t) in metres.
export function ribbedSheet(name, runs, material, pitch = 0.2, depth = 0.028, stand = 0.012) {
    const prof = [[0.0, 0.0], [0.10, 0.0], [0.125, 1.0], [0.175, 1.0]];
    const dep = (u) => {
        const f = (((u / pitch) % 1.0) + 1.0) % 1.0 * 0.2;
        const pts = [...prof, [0.2, 0.0]];
        for (let i = 0; i < pts.length - 1; i++) {
            const [a, da] = pts[i], [b, db] = pts[i + 1];
            if (a <= f && f <= b) return da + (db - da) * (f - a) / (b - a);
        }
        return 0.0;
    };
    const verts = [], faces = [], uvv = [];
    for (const [o, d, n, e, u0, u1, t0, t1] of runs) {
        const us = [u0];
        let k = Math.floor(u0 / pitch);
        while (k * pitch < u1) {
            for (const [off] of prof) { const u = (k + off / 0.2) * pitch; if (u0 + 1e-6 < u && u < u1 - 1e-6) us.push(u); }
            k++;
        }
        us.push(u1);
        const flip = V3.dot(V3.cross(d, e), n) < 0;
        const base = verts.length;
        for (const u of us) {
            const p = V3.add(V3.add(o, V3.mul(d, u)), V3.mul(n, stand + depth * dep(u)));
            verts.push(V3.add(p, V3.mul(e, t0)), V3.add(p, V3.mul(e, t1)));
            uvv.push([u, t0], [u, t1]);
        }
        for (let i = 0; i < us.length - 1; i++) {
            const a = base + 2 * i, b = base + 2 * i + 2, c = base + 2 * i + 3, dd = base + 2 * i + 1;
            faces.push(flip ? [a, dd, c, b] : [a, b, c, dd]);
        }
    }
    return meshData(name, [material], verts, faces, { uv: faces.flatMap((f) => f.flatMap((i) => uvv[i])) });
}

// ====================================================================================================== the walls
// the dado (precast panels, 6 m, a real joint between each), the liner above it (profiled sheet), the flashing between
// them, the portal frames (columns with base plates and haunches, rafters), the gable posts; the roof's deck as
// profiled sheet on its purlins -> the rafters' y
export function walls(X) {
    const { L } = X, { HX0, HX1, HY0, HY1, RZ } = X;
    const [dx0, dx1] = L.dock.door_x, dh = L.dock.door_h;
    const fa = dx0 - 0.24, fb = dx1 + 0.24;
    const Z = [0, 0, 1];
    const runs = [[[HX1, 0, 0], [0, 1, 0], [-1, 0, 0], Z, HY0, HY1, DADO_Z, RZ], [[HX0, 0, 0], [0, 1, 0], [1, 0, 0], Z, HY0, HY1, DADO_Z, RZ],
        [[0, HY0, 0], [1, 0, 0], [0, 1, 0], Z, HX0, HX1, DADO_Z, RZ], [[0, HY1, 0], [1, 0, 0], [0, -1, 0], Z, HX0, fa, DADO_Z, RZ],
        [[0, HY1, 0], [1, 0, 0], [0, -1, 0], Z, fb, HX1, DADO_Z, RZ], [[0, HY1, 0], [1, 0, 0], [0, -1, 0], Z, fa, fb, dh + 0.25, RZ]];
    X.ob('hall_liner', X.mesh(ribbedSheet('hall_liner', runs, 'hall_wall_panel')), X.C.hall_shell);
    X.ob('hall_roof_deck', X.mesh(ribbedSheet('hall_roof_deck', [[[0, 0, RZ], [0, 1, 0], [0, 0, -1], [1, 0, 0], HY0, HY1, HX0, HX1]], 'hall_roof', 0.25, 0.045, 0.004)),
        X.C.hall_shell);
    let mb = new MB();
    mb.span([HX0 - X.WT, HY0 - X.WT, RZ], [HX1 + X.WT, HY1 + X.WT, RZ + 0.25]);
    X.replace(mb.mesh('hall_roof', ['hall_roof']));                     // the layout's slab without its box beams
    // ---- the dado
    mb = new MB();
    const t = DADO_T;
    const panels = (a, b, place) => {                                // 6 m panels from a to b, the first joint at a
        let u = a;
        while (u < b - 0.05) {
            let v = Math.min(u + 6.0, b);
            if (b - v < 1.2) v = b;                                    // no sliver at the end: the last panel takes it
            place(u + 0.01, v - 0.01);
            u = v;
        }
    };
    panels(-HY1, -HY0, (a, b) => mb.span([HX1 - t, -b, 0.0], [HX1, -a, DADO_Z]));
    panels(-HY1, -HY0, (a, b) => mb.span([HX0, -b, 0.0], [HX0 + t, -a, DADO_Z]));
    panels(HX0 + t, HX1 - t, (a, b) => mb.span([a, HY0, 0.0], [b, HY0 + t, DADO_Z]));
    panels(-fa, -(HX0 + t), (a, b) => mb.span([-b, HY1 - t, 0.0], [-a, HY1, DADO_Z]));
    panels(fb, HX1 - t, (a, b) => mb.span([a, HY1 - t, 0.0], [b, HY1, DADO_Z]));
    X.ob('hall_dado', X.mesh(X.fin(mb.mesh('hall_dado', ['wall_concrete']), 0.008, 0.035, 0.10, 0.0)), X.C.hall_shell);
    // ---- the flashing on the dado's top: a folded galvanized trim with a drip
    mb = new MB();
    const trim = (o, d, n, u0, u1) => {
        for (const [n0, n1, z0, z1] of [[0.004, t + 0.012, DADO_Z, DADO_Z + 0.0025], [t + 0.0095, t + 0.012, DADO_Z - 0.022, DADO_Z], [0.004, 0.0065, DADO_Z, DADO_Z + 0.06]]) {
            const p = V3.add(V3.add(o, V3.mul(d, u0)), V3.mul(n, n0)), q = V3.add(V3.add(o, V3.mul(d, u1)), V3.mul(n, n1));
            mb.span([Math.min(p[0], q[0]), Math.min(p[1], q[1]), z0], [Math.max(p[0], q[0]), Math.max(p[1], q[1]), z1]);
        }
    };
    trim([HX1, 0, 0], [0, 1, 0], [-1, 0, 0], HY0, HY1);
    trim([HX0, 0, 0], [0, 1, 0], [1, 0, 0], HY0, HY1);
    trim([0, HY0, 0], [1, 0, 0], [0, 1, 0], HX0, HX1);
    trim([0, HY1, 0], [1, 0, 0], [0, -1, 0], HX0, fa);
    trim([0, HY1, 0], [1, 0, 0], [0, -1, 0], fb, HX1);
    X.ob('hall_dado_flashing', X.mesh(X.fin(mb.mesh('hall_dado_flashing', ['steel_galv']), 0.0008, 0.006, 0.0)), X.C.hall_shell);
    // ---- the frames: columns at the side walls under every rafter, the rafters, posts on the gables
    mb = new MB();
    const COL = i_section(0.30, 0.20, 0.012, 0.008, 0.012);
    const RAF = i_section(0.40, 0.20, 0.014, 0.009, 0.012);
    const zRaf = RZ - 0.60;
    const framesY = [];
    for (let y = HY1 - 6.0; y > HY0 + 1.0; y -= 12.0) framesY.push(y);
    for (const y of framesY) {
        mb.prism(RAF, HX0, HX1, 'x', 0, [y, zRaf + 0.20]);
        for (const [wx, s] of [[HX1, -1], [HX0, 1]]) {
            mb.prism(COL.map(([u, v]) => [wx + v, y + u]), 0.02, zRaf, 'z', 0);
            mb.span([Math.min(wx, wx + s * 0.27), y - 0.17, 0.0], [Math.max(wx, wx + s * 0.27), y + 0.17, 0.02], 0);
            for (const sy of [-1, 1]) {
                mb.bolt([wx + s * 0.215, y + sy * 0.125, 0.0265], 0.015, 0.012, 'z', 1);
                mb.cyl([wx + s * 0.215, y + sy * 0.125, 0.04], 0.007, 0.016, 'z', 8, 1);
            }
            const xa = wx + s * 0.15, xb = wx + s * 1.55;               // the haunch
            mb.prism([[xa, zRaf], [xb, zRaf], [xa, zRaf - 0.55]], y - 0.0045, y + 0.0045, 'y', 0);
            mb.bar([xa, y, zRaf - 0.55], [xb, y, zRaf], 0.20, 0.014, 0);
            mb.span([Math.min(xa, xa + s * 0.012), y - 0.10, zRaf - 0.60], [Math.max(xa, xa + s * 0.012), y + 0.10, zRaf], 0);
            for (const bz of [zRaf - 0.08, zRaf - 0.22, zRaf - 0.40]) for (const sy of [-1, 1]) mb.bolt([xa + s * 0.018, y + sy * 0.065, bz], 0.013, 0.011, 'x', 1, false);
        }
    }
    const posts = [...arange(fa - 3.16, HX0 + 3.0, -6.0), fb + 1.6];
    for (const [wy, s, xs] of [[HY1, -1, posts], [HY0, 1, [...posts, -1.6]]]) {
        for (const x of xs) {
            mb.prism(COL.map(([u, v]) => [x + u, wy + v]), 0.02, RZ - 0.21, 'z', 0);
            mb.span([x - 0.17, Math.min(wy, wy + s * 0.27), 0.0], [x + 0.17, Math.max(wy, wy + s * 0.27), 0.02], 0);
            for (const sx of [-1, 1]) mb.bolt([x + sx * 0.125, wy + s * 0.215, 0.0265], 0.015, 0.012, 'z', 1);
        }
    }
    X.ob('hall_structure', X.mesh(X.fin(mb.mesh('hall_structure', ['column_paint', 'steel_galv']), 0.004, 0.022, 0.10, 0.0)), X.C.hall_shell);
    X.say(`   walls: frames at ${framesY.length} rafters`);
    return framesY;
}

// ====================================================================================================== the dock door
// the dock's roller shutter, open: its frame, the two guides, the last laths under the coil, the coil on its barrel
// between two bracket plates, the drive and its hand chain, the bottom rail and seal; the bollards; corner guards on
// the jambs; the control station beside it -> { control, motor } (where their conduits go)
export function dockDoor(X) {
    const { L } = X, { HY1, WT } = X;
    const [dx0, dx1] = L.dock.door_x, dh = L.dock.door_h;
    const [FR, GALV, CURT, RUB, YEL, DARK, TEAL] = [0, 1, 2, 3, 4, 5, 6];
    const mb = new MB();
    const yf = HY1 - 0.06;
    for (const x of [dx0 - 0.12, dx1 + 0.12]) mb.span([x - 0.12, yf, 0], [x + 0.12, HY1 + WT + 0.06, dh + 0.25], FR);
    mb.span([dx0 - 0.24, yf, dh], [dx1 + 0.24, HY1 + WT + 0.06, dh + 0.25], FR);
    for (const x of [dx0 - 0.12, dx1 + 0.12]) {
        mb.span([x - 0.19, yf - 0.11, 0.0], [x + 0.19, yf, 0.012], GALV);
        for (const sx of [-1, 1]) mb.bolt([x + sx * 0.15, yf - 0.06, 0.018], 0.012, 0.01, 'z', GALV);
    }
    const yc = yf - 0.048;
    for (const [s, x] of [[1, dx0 - 0.075], [-1, dx1 + 0.075]]) {
        mb.prism(c_section(0.085, 0.08, 0.004).map(([u, v]) => [x + s * u, yc + v]), 0.0, dh + 0.50, 'z', GALV);
        for (const z of arange(0.35, dh + 0.3, 0.75)) {
            mb.box([x - s * 0.03, yc + 0.02, z], [0.06, 0.05, 0.06], GALV);
            mb.bolt([x - s * 0.03, yc - 0.008, z], 0.009, 0.007, 'y', GALV);
        }
    }
    const lath = [[-0.007, 0.0], [0.007, 0.0], [0.012, 0.022], [0.012, 0.072], [0.007, 0.097], [-0.007, 0.097], [-0.002, 0.072], [-0.002, 0.022]];
    const yr = yc - 0.29, zr = dh + 0.62, rr = 0.28;
    const xl0 = dx0 - 0.068, xl1 = dx1 + 0.068;
    for (let z = dh - 0.10; z < zr; z += 0.1) mb.prism(lath, xl0, xl1, 'x', CURT, [yc, z]);
    mb.span([xl0, yc - 0.03, dh - 0.16], [xl1, yc + 0.03, dh - 0.10], GALV);
    mb.span([xl0, yc - 0.022, dh - 0.19], [xl1, yc + 0.022, dh - 0.16], RUB);
    const nL = 28, coil = [];
    for (let i = 0; i < nL * 3; i++) {
        const a = 2 * PI * i / (nL * 3), r = rr - (i % 3 === 0 ? 0.009 : 0.0);
        coil.push([Math.cos(a) * r, Math.sin(a) * r]);
    }
    mb.prism(coil, dx0 - 0.10, dx1 + 0.10, 'x', CURT, [yr, zr]);
    mb.cyl([(dx0 + dx1) / 2, yr, zr], 0.055, dx1 - dx0 + 0.56, 'x', 20, DARK);
    const yw = HY1 - RIB - 0.002;
    for (const x of [dx0 - 0.24, dx1 + 0.24]) {
        mb.span([x - 0.006, yr - 0.34, zr - 0.34], [x + 0.006, yw, zr + 0.34], GALV);
        mb.span([x - 0.06, yw - 0.012, zr - 0.34], [x + 0.06, yw, zr + 0.34], GALV);
        for (const bz of [-0.26, 0.0, 0.26]) for (const sx of [-1, 1]) mb.bolt([x + sx * 0.038, yw - 0.0165, zr + bz], 0.011, 0.009, 'y', GALV);
        mb.cyl([x, yr, zr], 0.085, 0.05, 'x', 20, DARK);
    }
    const xm = dx0 - 0.24, sd = -1;                                  // the drive, outboard of the west bracket
    mb.cyl([xm + sd * 0.22, yr, zr], 0.085, 0.34, 'x', 24, DARK);
    for (let i = 0; i < 9; i++) mb.cyl([xm + sd * (0.10 + 0.03 * i), yr, zr], 0.094, 0.006, 'x', 24, DARK);
    mb.box([xm + sd * 0.07, yr, zr - 0.02], [0.11, 0.19, 0.24], DARK);
    mb.box([xm + sd * 0.24, yr - 0.10, zr + 0.06], [0.11, 0.07, 0.09], DARK);
    const xc = xm + sd * 0.42;
    mb.cyl([xc, yr, zr], 0.12, 0.022, 'x', 28, GALV);
    mb.cyl([xc, yr, zr], 0.03, 0.05, 'x', 12, DARK);
    for (const sy of [-1, 1]) mb.rod([xc, yr + sy * 0.115, zr], [xc, yr + sy * 0.115, 1.25], 0.0045, 6, GALV);
    mb.tube(mb.arc([xc, yr, 1.25], 0.115, PI, 2 * PI, 'x', 8), 0.0045, 6, GALV);
    for (const x of [dx0 - 0.5, dx1 + 0.5]) {                         // the bollards
        mb.cyl([x, HY1 - 1.2, 0.56], 0.085, 1.10, 'z', 24, YEL);
        mb.cyl([x, HY1 - 1.2, 1.125], 0.085, 0.03, 'z', 24, YEL, true, 0.06);
        mb.cyl([x, HY1 - 1.2, 0.006], 0.16, 0.012, 'z', 24, GALV);
        for (let k = 0; k < 4; k++) {
            const a = PI / 4 + k * PI / 2;
            mb.bolt([x + Math.cos(a) * 0.125, HY1 - 1.2 + Math.sin(a) * 0.125, 0.0175], 0.012, 0.01, 'z', GALV);
        }
    }
    mb.prism([[dx0 - 0.20, yf - 0.006], [dx0 + 0.006, yf - 0.006], [dx0 + 0.006, HY1 + 0.03], [dx0, HY1 + 0.03], [dx0, yf], [dx0 - 0.20, yf]], 0.012, 1.5, 'z', YEL);
    mb.prism([[dx1 + 0.20, yf - 0.006], [dx1 + 0.20, yf], [dx1, yf], [dx1, HY1 + 0.03], [dx1 - 0.006, HY1 + 0.03], [dx1 - 0.006, yf - 0.006]], 0.012, 1.5, 'z', YEL);
    const cx = dx0 - 1.05, cz = 1.32, ys = HY1 - DADO_T;             // the control station: up, stop, down
    mb.box([cx, ys - 0.035, cz], [0.10, 0.07, 0.26], TEAL);
    [0.075, 0.0, -0.075].forEach((dz, k) => {
        mb.cyl([cx, ys - 0.072, cz + dz], 0.019, 0.006, 'y', 24, RUB);
        mb.cyl([cx, ys - 0.078, cz + dz], 0.014, 0.008, 'y', 24, k === 1 ? GALV : DARK);
    });
    X.replace(X.fin(mb.mesh('dock_door', ['column_paint', 'steel_galv', 'curtain_white', 'rubber_black', 'hazard_yellow', 'steel_dark', 'plastic_teal']), 0.003, 0.016, 0.08, 0.0));
    return { control: [cx, ys - 0.035, cz + 0.13], motor: [xm + sd * 0.24, yr - 0.10, zr + 0.105] };
}

// ====================================================================================================== services
// the cable tray round the hall on its brackets (a 3 m module, instanced), the conduits down from it with their
// saddles, and CC0 fittings (Poly Haven, by ID: a distribution board, a call point, two cameras)
export function services(X, door) {
    const { L } = X, { HX0, HX1, HY0, HY1 } = X;
    const [dx0, dx1] = L.dock.door_x;
    const [GALV, RUB, GREY] = [0, 1, 2];
    let mb = new MB();                                               // the tray module: local +Y along the run, the wall at x 0
    const xa = -0.50, xb = -0.20;
    for (const x of [xa, xb]) {
        mb.span([x - 0.003, -1.5, 0.0], [x + 0.003, 1.5, 0.06], GALV);
        mb.span([x - 0.012, -1.5, 0.054], [x + 0.012, 1.5, 0.06], GALV);
    }
    for (let y = -1.35; y < 1.5; y += 0.3) mb.span([xa, y - 0.015, 0.006], [xb, y + 0.015, 0.024], GALV);
    for (const [x, r, mi, lift] of [[-0.46, 0.011, RUB, 0], [-0.435, 0.008, RUB, 0], [-0.405, 0.014, RUB, 0], [-0.37, 0.009, GREY, 0], [-0.345, 0.009, GREY, 0],
        [-0.31, 0.016, RUB, 0], [-0.275, 0.007, GREY, 0], [-0.255, 0.007, RUB, 0], [-0.42, 0.007, GREY, 0.024]]) {
        const zc = 0.024 + r + lift;
        mb.tube([[x, -1.5, zc], [x + 0.004, -0.5, zc], [x - 0.003, 0.5, zc], [x, 1.5, zc]], r, 8, mi, false);
    }
    mb.span([-0.045, -0.02, -0.30], [0.0, 0.02, 0.12], GALV);
    mb.span([-0.54, -0.018, -0.045], [-0.045, 0.018, 0.0], GALV);
    mb.bar([-0.48, 0, -0.045], [-0.045, 0, -0.28], 0.03, 0.006, GALV);
    for (const bz of [-0.25, 0.08]) mb.bolt([-0.049, 0.0, bz], 0.009, 0.007, 'x', GALV);
    X.asset('asset_cable_tray', X.mesh(X.fin(mb.mesh('cable_tray', ['steel_galv', 'rubber_black', 'cable_grey']), 0.0012, 0.006, 0.035)));
    const east = arange(HY1 - 2.1, HY0 + 1.6, -3.0).map((y) => [HX1, y, TRAY_Z]);
    X.lay.points('cable_tray_east', east, { node: 'asset_cable_tray' }, X.C.hall_shell, 0.0);
    const north = arange(HX1 - 2.0, HX0 + 1.6, -3.0).map((x) => [x, HY1, TRAY_Z]);
    X.lay.points('cable_tray_dock_wall', north, { node: 'asset_cable_tray' }, X.C.hall_shell, PI / 2);
    // conduits: 20 mm tube on saddles; they stand off the dado, step back over its flashing, and bend into the tray
    mb = new MB();
    const R = 0.0105, offLo = DADO_T + 0.02 + R, offHi = RIB + 0.012 + R;
    const saddle = (c, w, off) => {
        const ax = Math.abs(w[0]) > 0.5;
        const reach = off - (c[2] < DADO_Z ? DADO_T : RIB);
        mb.box(V3.add(c, V3.mul(w, reach / 2)), [ax ? reach : 0.03, ax ? 0.03 : reach, 0.02], GALV);
        mb.box(V3.sub(c, V3.mul(w, R + 0.002)), [ax ? 0.004 : 0.038, ax ? 0.038 : 0.004, 0.02], GALV);
    };
    const drop = (x, y, z0, w) => {
        w = [w[0], w[1], 0.0];
        const p0 = V3.sub([x, y, 0.0], V3.mul(w, offLo)), p1 = V3.sub([x, y, 0.0], V3.mul(w, offHi));
        const top = TRAY_Z + 0.11;
        const pts = [[p0[0], p0[1], z0], [p0[0], p0[1], DADO_Z + 0.05]];
        for (let i = 1; i < 6; i++) {
            const f = i / 6.0, q = V3.add(p0, V3.mul(V3.sub(p1, p0), 0.5 - 0.5 * Math.cos(PI * f)));
            pts.push([q[0], q[1], DADO_Z + 0.05 + 0.16 * f]);
        }
        pts.push([p1[0], p1[1], DADO_Z + 0.21], [p1[0], p1[1], top - 0.09]);
        for (let i = 1; i < 7; i++) {
            const a = (PI / 2) * i / 6, q = V3.sub(p1, V3.mul(w, 0.09 * (1.0 - Math.cos(a))));
            pts.push([q[0], q[1], top - 0.09 + 0.09 * Math.sin(a)]);
        }
        const q = V3.sub(p1, V3.mul(w, 0.17));
        pts.push([q[0], q[1], top]);
        mb.tube(pts, R, 10, GALV);
        for (let z = z0 + 0.25; z < DADO_Z - 0.1; z += 0.9) saddle([p0[0], p0[1], z], w, offLo);
        for (let z = DADO_Z + 0.45; z < top - 0.3; z += 0.95) saddle([p1[0], p1[1], z], w, offHi);
    };
    const N = [0, 1, 0], E = [1, 0, 0];
    drop(door.control[0], HY1, door.control[2], N);
    const [mx, my, mz] = door.motor;
    mb.tube([[mx, my + 0.015, TRAY_Z + 0.03], [mx, my + 0.015, TRAY_Z - 0.12], [mx, my, mz + 0.16], [mx, my, mz]], 0.011, 10, RUB);
    const pb = [HX1, 16.4, 1.5];
    for (const dy of [-0.07, 0.07]) drop(HX1, pb[1] + dy, pb[2] + 0.25, E);
    const fa_ = [dx0 - 1.75, HY1, 1.42];
    drop(fa_[0], HY1, fa_[2] + 0.07, N);
    const cam1 = [(dx0 + dx1) / 2 + 1.3, HY1, 6.75], yq = HY1 - offHi;
    mb.tube([[cam1[0], yq, cam1[2] - 0.05], [cam1[0], yq, TRAY_Z + 0.20], ...linspace(0.26, PI / 2, 6).map((a) => [cam1[0], yq - 0.10 * (1 - Math.cos(a)), TRAY_Z + 0.20 - 0.10 * Math.sin(a)]),
        [cam1[0], yq - 0.22, TRAY_Z + 0.10]], R, 10, GALV);
    const cam2 = [HX1, 8.6, 6.75], xq = HX1 - offHi;
    mb.tube([[xq, cam2[1], cam2[2] - 0.05], [xq, cam2[1], TRAY_Z + 0.20], ...linspace(0.26, PI / 2, 6).map((a) => [xq - 0.10 * (1 - Math.cos(a)), cam2[1], TRAY_Z + 0.20 - 0.10 * Math.sin(a)]),
        [xq - 0.22, cam2[1], TRAY_Z + 0.10]], R, 10, GALV);
    X.ob('hall_conduits', X.mesh(X.fin(mb.mesh('hall_conduits', ['steel_galv', 'rubber_black']), 0.0012, 0.006, 0.03)), X.C.hall_shell);
    // the CC0 fittings
    X.model('power_box_01', [HX1 - DADO_T - 0.048, pb[1], pb[2]], -PI / 2);
    X.model('fire_alarm', [fa_[0], HY1 - DADO_T - 0.013, fa_[2]], 0.0);
    X.model('security_camera_01', [cam1[0], HY1 - RIB - 0.28, cam1[2]], 0.0);
    X.model('security_camera_01', [HX1 - RIB - 0.28, cam2[1], cam2[2]], -PI / 2);
    X.say(`   services: tray modules ${east.length} + ${north.length}`);
}

// ====================================================================================================== guards
// a U of plate round a post's foot: `half` its inner half width, `reach` how far its two arms run back from the post's
// middle, open toward the unit step `openTo`; two feet with an anchor each
function uGuard(mb, cx, cy, half, reach, h, openTo, t = 0.006, mi = 0, galv = 1) {
    const o = [openTo[0], openTo[1]], s = [-o[1], o[0]];
    const P = (a, b) => [cx - o[0] * a + s[0] * b, cy - o[1] * a + s[1] * b];
    const poly = [P(-reach, -half - t), P(half + t, -half - t), P(half + t, half + t), P(-reach, half + t), P(-reach, half), P(half, half), P(half, -half), P(-reach, -half)];
    mb.prism(poly, 0.008, h, 'z', mi);
    for (const b of [-1, 1]) {
        const q = [cx + s[0] * (b * (half + t + 0.04)), cy + s[1] * (b * (half + t + 0.04))];
        mb.box([q[0], q[1], 0.004], [0.08, 0.08, 0.008], mi);
        mb.bolt([q[0], q[1], 0.013], 0.010, 0.008, 'z', galv);
    }
}

// what keeps trucks off the steel: a U guard at the foot of every rack upright that faces an aisle (one asset,
// instanced with the frames), a barrier across the end of the rack rows at the dock end, a guard round every crane post
export function guards(X, rows) {
    const { L } = X;
    let mb = new MB();
    uGuard(mb, -0.045, 0.0, 0.054, 0.035, 0.40, [-1, 0]);
    X.asset('asset_rack_upright_guard', X.mesh(X.fin(mb.mesh('rack_upright_guard', ['safety_yellow', 'steel_galv']), 0.002, 0.012, 0.06, 0.0)));
    let n = 0;
    for (const [name, pts, rz] of rows) { X.lay.points(`rack_${name}_guards`, pts, { node: 'asset_rack_upright_guard' }, X.C.racks, rz); n += pts.length; }
    mb = new MB();
    const ends = [[-6.62, -4.18, 13.8 + 0.42], [6.08, 7.20, 12.0 + 0.42]];
    for (const [xa, xb, y] of ends) {
        for (const x of [xa, xb]) {
            mb.box([x, y, 0.22], [0.10, 0.10, 0.42], 0);
            mb.box([x, y, 0.445], [0.11, 0.11, 0.012], 0);
            mb.box([x, y, 0.005], [0.22, 0.22, 0.010], 0);
            for (const sx of [-1, 1]) for (const sy of [-1, 1]) mb.bolt([x + sx * 0.08, y + sy * 0.08, 0.015], 0.011, 0.009, 'z', 1);
        }
        for (const z of [0.34, 0.16]) mb.rod([xa + 0.05, y, z], [xb - 0.05, y, z], 0.038, 16, 0);
    }
    X.ob('rack_end_barriers', X.mesh(X.fin(mb.mesh('rack_end_barriers', ['safety_yellow', 'steel_galv']), 0.003, 0.014, 0.06, 0.0)), X.C.racks);
    const GA = L.gantry;
    mb = new MB();
    GA.rail_x.forEach((rx, i) => {
        for (const py of (i === 0 ? GA.post_y_west : GA.post_y_east)) uGuard(mb, rx, py, 0.20, 0.20, 0.45, i === 0 ? [-1, 0] : [1, 0], 0.008);
    });
    X.ob('line_crane_post_guards', X.mesh(X.fin(mb.mesh('line_crane_post_guards', ['hazard_yellow', 'steel_galv']), 0.003, 0.014, 0.06, 0.0)), X.C.line_module);
    X.say(`   guards: ${n} upright guards, ${ends.length} end barriers, crane post guards on every line`);
}

// ====================================================================================================== the yard
// a box trailer seen from its rear (y = 0, toward -Y) and its sides: body, door leaves with their lock rods and
// hinges, the under-run bar, three axles, the landing gear
function trailerMesh() {
    const [W, G_, D_, R_] = [0, 1, 2, 3];
    const mb = new MB();
    mb.span([-1.275, 0.04, 1.15], [1.275, 13.6, 4.0], W);
    for (const x of [-1.235, 1.235]) mb.span([x - 0.045, 0.0, 1.10], [x + 0.045, 0.06, 4.02], D_);
    mb.span([-1.28, 0.0, 3.93], [1.28, 0.06, 4.03], D_);
    mb.span([-1.28, 0.0, 1.06], [1.28, 0.06, 1.17], D_);
    for (const s of [-1, 1]) {
        mb.span([Math.min(s * 0.012, s * 1.185), -0.022, 1.19], [Math.max(s * 0.012, s * 1.185), 0.0, 3.91], W);
        for (const x of [0.33, 0.86]) {
            mb.rod([s * x, -0.045, 1.14], [s * x, -0.045, 3.96], 0.016, 10, G_);
            mb.box([s * x, -0.04, 1.95], [0.05, 0.03, 0.26], G_);
            for (const z of [1.16, 3.94]) mb.box([s * x, -0.035, z], [0.07, 0.05, 0.05], G_);
        }
        for (const z of [1.5, 2.3, 3.1, 3.7]) mb.box([s * 1.2, -0.03, z], [0.09, 0.03, 0.12], G_);
    }
    for (const x of [-1.275, 1.275]) for (const z of [1.19, 3.97]) mb.box([x, 6.82, z], [0.02, 13.56, 0.08], G_);
    mb.span([-1.2, 0.03, 0.46], [1.2, 0.13, 0.58], D_);
    for (const x of [-0.6, 0.6]) mb.span([x - 0.04, 0.05, 0.58], [x + 0.04, 0.13, 1.06], D_);
    for (const x of [-0.5, 0.5]) mb.span([x - 0.06, 0.3, 0.82], [x + 0.06, 13.3, 1.15], D_);
    for (const y of [1.7, 3.05, 4.4]) {
        mb.cyl([0, y, 0.52], 0.06, 2.1, 'x', 10, D_);
        for (const x of [-1.06, 1.06]) {
            mb.cyl([x, y, 0.52], 0.52, 0.36, 'x', 28, R_);
            mb.cyl([x + (x > 0 ? 0.16 : -0.16), y, 0.52], 0.27, 0.06, 'x', 20, G_);
        }
    }
    for (const x of [-0.75, 0.75]) mb.span([x - 0.3, 1.02, 0.25], [x + 0.3, 1.035, 0.9], R_);
    for (const x of [-0.55, 0.55]) {
        mb.span([x - 0.06, 11.1, 0.12], [x + 0.06, 11.22, 1.0], D_);
        mb.span([x - 0.14, 11.02, 0.0], [x + 0.14, 11.30, 0.03], D_);
    }
    return mb.mesh('yard_trailer', ['trailer_white', 'steel_galv', 'steel_dark', 'rubber_black']);
}

// THE YARD'S TREES, as the Blender edition grows and places them: five SeedThree individuals (species, seed, height),
// duplicated three rows deep behind the fence 48 to 90 m from the door. Each placing is [individual, x, y, turn,
// scale]: numpy's default_rng(11) draws in the Blender edition's _trees, over the five individuals' widths (16.711,
// 29.606, 16.194, 7.029, 22.666 m), the places that would put a crown in the sun's way into the door left empty
// (30 placed, 4 left out). The sun's corridor stays open: a crown there turns the warm patch into leaf shade.
export const TREES = [['tulipPoplar', 4107, 25.0], ['americanSycamore', 2203, 21.0], ['redMaple', 905, 16.5], ['quakingAspen', 618, 15.0], ['whiteOak', 1737, 17.0]];
export const TREE_PLACES = [[0, -63.6343, 71.9964, 0.18025, 1.00045], [3, -54.9491, 74.1411, 0.81537, 0.84113], [1, -42.8274, 72.6094, 3.21306, 0.9307],
    [4, -35.4835, 70.8765, 4.95125, 0.86139], [2, -26.8504, 72.0619, 3.44984, 1.06502], [0, -16.884, 70.5225, 3.03861, 0.98612], [3, -11.0456, 72.458, 5.04024, 0.89059],
    [3, -0.1837, 70.1438, 1.7413, 0.96012], [0, 25.7663, 70.5857, 1.26143, 0.82992], [4, -65.9787, 85.7513, 4.38152, 1.09184], [2, -56.607, 82.135, 6.26061, 0.86795],
    [0, -46.6772, 87.5283, 0.21394, 0.8364], [3, -35.5781, 86.7031, 1.99408, 0.91261], [1, -29.5074, 83.3814, 5.27222, 0.82738], [4, -18.4483, 83.0176, 1.22929, 1.04177],
    [2, -10.8276, 86.7871, 0.16929, 1.08873], [3, 1.8426, 83.5214, 0.11286, 0.84787], [3, 20.8528, 83.7377, 1.6219, 0.91455], [4, 30.8045, 89.528, 2.7394, 0.92221],
    [3, -84.817, 109.4511, 0.42372, 0.832], [1, -72.9222, 102.4313, 4.66077, 1.07357], [4, -60.7985, 108.2607, 4.90737, 1.02768], [2, -47.619, 101.0963, 0.90237, 1.00784],
    [0, -38.2502, 110.008, 4.77023, 1.08841], [3, -28.5442, 104.0318, 6.27548, 0.86892], [1, -16.5663, 102.4204, 0.38255, 0.92717], [4, -1.8703, 107.9091, 3.13062, 0.86792],
    [3, 6.1461, 107.5537, 0.24277, 0.8895], [3, 30.2291, 108.0083, 0.82093, 0.92562], [1, 41.6869, 104.5338, 0.72669, 1.09379]];

// outdoors, as the dock door sees it: the apron (the layout's), a kerb and a chain-link fence (a CC0 kit's double
// panel, instanced), trailers parked at it, three lamp masts, open ground beyond, and the trees (TREE_PLACES)
export function yard(X, trees = true) {
    const FY = 62.0, CD = X.C.dock;
    let mb = new MB();
    mb.quad([[-420.0, FY + 0.35, 0.03], [420.0, FY + 0.35, 0.03], [420.0, 700.0, 0.03], [-420.0, 700.0, 0.03]]);
    X.ob('yard_field', X.mesh(mb.mesh('yard_field', ['yard_field'], false)), CD).outdoor = true;
    mb = new MB();
    mb.span([-90.0, FY + 0.05, 0.0], [60.0, FY + 0.33, 0.13]);
    X.ob('yard_kerb', X.mesh(X.fin(mb.mesh('yard_kerb', ['wall_concrete']), 0.012, 0.04, 0.0)), CD).outdoor = true;
    X.mesh(X.fin(trailerMesh(), 0.006, 0.03, 0.10, 0.0));
    [[-24.6, 43.0, 0.0], [-20.9, 43.4, 0.0], [-12.8, 44.0, 0.0], [7.4, 45.5, 0.0], [-34.5, 46.5, RAD(6.0)]].forEach(([x, y, yaw], i) => {
        const o = X.ob(`yard_trailer_${i}`, 'yard_trailer', CD, [x, y, 0.0], yaw);
        o.props.note = 'a parked box trailer: its rear doors toward the dock';
        o.outdoor = true;
    });
    mb = new MB();
    for (const x of [-31.0, -16.5, 9.5]) {                            // lamp masts (none on the door's own axis)
        mb.cyl([x, FY - 0.6, 5.5], 0.11, 11.0, 'z', 16, 0, true, 0.06);
        mb.cyl([x, FY - 0.6, 0.012], 0.2, 0.024, 'z', 16, 0);
        mb.tube([[x, FY - 0.6, 10.9], [x, FY - 0.6, 11.25], [x, FY - 0.9, 11.42], [x, FY - 1.9, 11.48]], 0.04, 10, 0);
        mb.box([x, FY - 2.15, 11.46], [0.3, 0.62, 0.09], 1);
    }
    X.ob('yard_masts', X.mesh(X.fin(mb.mesh('yard_masts', ['steel_galv', 'steel_dark']), 0.004, 0.02, 0.0)), CD).outdoor = true;
    // the fence: the CC0 kit's double panel (1.914 m) along the kerb
    X.fence = { asset: 'modular_chainlink_fence', mesh: 'modular_chainlink_fence_double', pts: arange(-88.0, 59.0, 1.914).map((x) => [x, FY, 0.13]) };
    X.trees = trees ? TREE_PLACES : [];
    X.say(`   yard: field, kerb, 5 trailers, 3 masts, ${X.fence.pts.length} fence panels, ${X.trees.length} trees`);
}
