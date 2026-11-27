// eidoverse/sets/wake_another_one/hall/machines.js — the hall's machines as modelled assets: the crane (its runway,
// bridge, trolley, belts, ring and gripper pads) and the meter cabinet. A port of the Blender edition's
// hall._machines. The layout places and rigs them as plain boxes; here every one of their meshes is rebuilt IN ITS
// OWN FRAME with real sections, under the layout's mesh names, so every object, origin, parent and driver stays as
// the layout made it.
import { MB, i_section, PI } from './kit.js';
import { linspace } from './shell.js';

// a small geared motor at c, its shaft along `axis`, the motor on the side s (+1 / -1) of its gearbox: finned housing,
// fan cowl, terminal box, the gearbox block with its cover's bolts
function gearMotor(mb, c, axis, s, dark, galv, r = 0.07, ln = 0.24) {
    const i = 'xyz'.indexOf(axis);
    const [j, k] = [0, 1, 2].filter((n) => n !== i);
    const at = (d, e = [0.0, 0.0]) => { const p = [...c]; p[i] += d * s; p[j] += e[0]; p[k] += e[1]; return p; };
    const g = 0.11;
    const size = [g * 1.25, g * 1.25, g * 1.25];
    size[i] = g;
    mb.box(at(0.0), size, dark);
    mb.cyl(at(g / 2 + ln / 2), r, ln, axis, 24, dark);
    for (let n = 0; n < Math.trunc(ln / 0.022) - 1; n++) mb.cyl(at(g / 2 + 0.02 + 0.022 * n), r * 1.12, 0.005, axis, 24, dark);
    mb.cyl(at(g / 2 + ln + 0.02), r * 1.05, 0.04, axis, 24, dark);
    const tb = [0.07, 0.07, 0.07];
    tb[i] = 0.09;
    mb.box(at(g / 2 + ln * 0.45, [0.0, r + 0.025]), tb, dark);
    mb.cyl(at(g / 2 + ln * 0.45, [0.045, r + 0.025]), 0.011, 0.02, 'xyz'[j], 6, galv);
    for (const [a, b] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) mb.bolt(at(-g / 2 - 0.004, [a * g * 0.5, b * g * 0.5]), 0.008, 0.006, axis, galv, false);
}

// ====================================================================================================== the crane
export function crane(X) {
    const { L } = X, G = L.gantry, RZ = L.hall.roof_z;
    const [x0, x1] = G.rail_x, [y0, y1] = G.rail_y, zt = G.rail_top, dy = G.girder_dy, gw = G.girder_w, [z0, z1] = G.girder_z;
    const [WH, GALV, RUB, TEAL, DARK, GREY] = [0, 1, 2, 3, 4, 5];
    // (WH: the crane's own paint, a worn safety yellow; its trucks, drives and grippers keep the machines' teal)
    const MATS = ['safety_yellow', 'steel_galv', 'rubber_black', 'machine_teal', 'steel_dark', 'plastic_grey'];
    // ---------------------------------------------------------------- the runway: two rails on posts, tied at their ends
    let mb = new MB();
    const RAIL = i_section(0.26, 0.14, 0.012, 0.008, 0.010);
    G.rail_x.forEach((rx, ri) => {
        const posts = ri === 0 ? G.post_y_west : G.post_y_east;
        mb.prism(RAIL, y0, y1, 'y', WH, [rx, zt - 0.13]);
        mb.span([rx - 0.025, y0 + 0.02, zt], [rx + 0.025, y1 - 0.02, zt + 0.03], GALV);
        for (let y = y0 + 0.3; y < y1 - 0.2; y += 0.6) {
            for (const s of [-1, 1]) {
                mb.box([rx + s * 0.043, y, zt + 0.007], [0.03, 0.05, 0.014], GALV);
                mb.bolt([rx + s * 0.046, y, zt + 0.018], 0.008, 0.006, 'z', GALV, false);
            }
        }
        for (const [ye, s] of [[y0, 1], [y1, -1]]) {
            mb.box([rx, ye + s * 0.06, zt + 0.085], [0.10, 0.05, 0.17], WH);
            mb.cyl([rx, ye + s * 0.11, zt + 0.105], 0.04, 0.05, 'y', 16, RUB);
        }
        for (const py of posts) {
            mb.span([rx - 0.07, py - 0.07, 0.016], [rx + 0.07, py + 0.07, zt - 0.272], WH);
            mb.span([rx - 0.16, py - 0.16, 0.0], [rx + 0.16, py + 0.16, 0.016], WH);
            mb.span([rx - 0.10, py - 0.10, zt - 0.272], [rx + 0.10, py + 0.10, zt - 0.26], WH);
            for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
                mb.bolt([rx + sx * 0.12, py + sy * 0.12, 0.0215], 0.012, 0.011, 'z', GALV);
                mb.cyl([rx + sx * 0.12, py + sy * 0.12, 0.034], 0.006, 0.014, 'z', 8, GALV);
                mb.bolt([rx + sx * 0.052, py + sy * 0.08, zt - 0.277], 0.009, 0.008, 'z', GALV, false);
            }
            for (const s of [-1, 1]) {                                 // gussets at the foot, knee braces under the rail
                mb.prism([[s * 0.07, 0.016], [s * 0.15, 0.016], [s * 0.07, 0.14]], py - 0.004, py + 0.004, 'y', WH, [rx, 0.0]);
                mb.prism([[s * 0.07, 0.016], [s * 0.15, 0.016], [s * 0.07, 0.14]], rx - 0.004, rx + 0.004, 'x', WH, [py, 0.0]);
                if (y0 + 0.3 < py + s * 0.62 && py + s * 0.62 < y1 - 0.3) mb.bar([rx, py + s * 0.07, zt - 0.86], [rx, py + s * 0.62, zt - 0.27], 0.06, 0.06, WH);
            }
        }
        for (const py of G.hang_y) {                                   // a drop tube from the roof steel (no floor post there)
            mb.cyl([rx, py, (zt + RZ - 0.6) / 2], 0.035, RZ - 0.6 - zt, 'z', 16, WH);
            mb.box([rx, py, zt + 0.008], [0.22, 0.22, 0.016], WH);
            mb.box([rx, py, RZ - 0.608], [0.26, 0.26, 0.016], WH);
            for (const sx of [-1, 1]) for (const sy of [-1, 1]) mb.bolt([rx + sx * 0.08, py + sy * 0.08, zt + 0.021], 0.009, 0.008, 'z', GALV, false);
        }
    });
    for (const ty of [y0, y1]) {                                       // the end ties
        mb.span([x0 + 0.07, ty - 0.05, zt - 0.22], [x1 - 0.07, ty + 0.05, zt - 0.05], WH);
        for (const [rx, s] of [[x0, 1], [x1, -1]]) {
            mb.box([rx + s * 0.076, ty, zt - 0.135], [0.012, 0.16, 0.23], WH);
            for (const bz of [-0.08, 0.08]) for (const sy of [-1, 1]) mb.bolt([rx + s * 0.085, ty + sy * 0.062, zt - 0.135 + bz], 0.009, 0.008, 'x', GALV, false);
        }
    }
    const cx = x1 + 0.11;                                              // the conductor rail along the east rail's outer side
    mb.span([cx - 0.02, y0 + 0.2, zt - 0.20], [cx + 0.02, y1 - 0.2, zt - 0.14], GREY);
    for (let y = y0 + 0.5; y < y1 - 0.3; y += 1.2) {
        mb.span([x1 + 0.004, y - 0.015, zt - 0.12], [cx + 0.02, y + 0.015, zt - 0.10], GALV);
        mb.box([cx, y, zt - 0.13], [0.03, 0.03, 0.02], GALV);
    }
    X.replace(X.fin(mb.mesh('line_crane_runway', MATS), 0.004, 0.02, 0.08, 0.0));
    // ---------------------------------------------------------------- the bridge: two box girders on end trucks
    mb = new MB();
    const xa = x0 - 0.22, xb = x1 + 0.22;
    for (const s of [-1, 1]) {
        const yc = s * dy;
        mb.span([xa, yc - gw / 2 + 0.012, z0 + 0.012], [xb, yc + gw / 2 - 0.012, z1 - 0.012], WH);
        mb.span([xa, yc - gw / 2 - 0.015, z0], [xb, yc + gw / 2 + 0.015, z0 + 0.012], WH);
        mb.span([xa, yc - gw / 2 - 0.015, z1 - 0.012], [xb, yc + gw / 2 + 0.015, z1], WH);
        mb.span([xa + 0.05, yc - 0.02, z1], [xb - 0.05, yc + 0.02, z1 + 0.02], GALV);
        for (let x = xa + 0.6; x < xb - 0.3; x += 1.1) mb.box([x, yc + s * (gw / 2 - 0.004), (z0 + z1) / 2], [0.008, 0.016, z1 - z0 - 0.024], WH);
        for (const [xe, se] of [[xa, 1], [xb, -1]]) {
            mb.box([xe + se * 0.07, yc, z1 + 0.05], [0.04, 0.07, 0.06], WH);
            mb.cyl([xe + se * 0.10, yc, z1 + 0.05], 0.022, 0.03, 'x', 12, RUB);
        }
    }
    for (const rx of [x0, x1]) {
        mb.span([rx - 0.10, -0.92, zt + 0.085], [rx + 0.10, 0.92, zt + 0.22], TEAL);
        for (const wy of [-0.78, 0.78]) {
            mb.cyl([rx, wy, zt + 0.105], 0.075, 0.06, 'x', 28, GALV);
            for (const sx of [-1, 1]) {
                mb.cyl([rx + sx * 0.036, wy, zt + 0.105], 0.09, 0.012, 'x', 28, GALV);
                mb.cyl([rx + sx * 0.106, wy, zt + 0.105], 0.045, 0.012, 'x', 20, DARK);
                for (let k = 0; k < 4; k++) {
                    const a = PI / 4 + k * PI / 2;
                    mb.bolt([rx + sx * 0.114, wy + Math.cos(a) * 0.032, zt + 0.105 + Math.sin(a) * 0.032], 0.006, 0.005, 'x', GALV, false);
                }
            }
        }
        for (const sy of [-1, 1]) {
            mb.cyl([rx, sy * 0.945, zt + 0.15], 0.04, 0.05, 'y', 16, RUB);
            for (const bx of [-0.075, 0.075]) for (const by of [-0.05, 0.05]) mb.bolt([rx + bx, sy * dy + by, z1 + 0.004], 0.010, 0.008, 'z', GALV);
        }
    }
    gearMotor(mb, [x0 - 0.16, 0.45, zt + 0.14], 'x', -1, DARK, GALV);
    gearMotor(mb, [x1 + 0.16, 0.45, zt + 0.14], 'x', 1, DARK, GALV);
    const ycr = dy + gw / 2 + 0.07;
    mb.span([xa + 0.3, ycr - 0.02, z1 - 0.10], [xb - 0.3, ycr + 0.02, z1 - 0.04], GREY);
    for (let x = xa + 0.6; x < xb - 0.3; x += 1.1) {
        mb.span([x - 0.015, dy + gw / 2 + 0.015, z1 - 0.03], [x + 0.015, ycr + 0.02, z1 - 0.012], GALV);
        mb.box([x, ycr, z1 - 0.035], [0.03, 0.03, 0.02], GALV);
    }
    mb.box([x1 + 0.11, -0.3, zt - 0.02], [0.05, 0.10, 0.08], DARK);
    mb.bar([x1 + 0.11, -0.3, zt + 0.02], [x1 + 0.06, -0.3, zt + 0.12], 0.02, 0.02, GALV);
    X.replace(X.fin(mb.mesh('crane_bridge', MATS), 0.004, 0.02, 0.08));
    // ---------------------------------------------------------------- the trolley: an open frame (a top view looks through it)
    mb = new MB();
    const ty = dy + 0.14, tx = 0.675, tw = 0.12, za = z1 + 0.02, zb = z1 + 0.14;
    for (const s of [-1, 1]) {
        mb.span([-tx, Math.min(s * ty, s * (ty - tw)), za], [tx, Math.max(s * ty, s * (ty - tw)), zb], WH);
        mb.span([Math.min(s * tx, s * (tx - tw)), -ty + tw, za], [Math.max(s * tx, s * (tx - tw)), ty - tw, zb], WH);
        for (const sx of [-1, 1]) {
            mb.box([sx * (tx - 0.09), s * (ty - 0.09), zb + 0.004], [0.20, 0.20, 0.008], WH);
            for (const [a, b] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) mb.bolt([sx * (tx - 0.09) + a * 0.07, s * (ty - 0.09) + b * 0.07, zb + 0.012], 0.009, 0.007, 'z', GALV, false);
            mb.cyl([sx * 0.40, s * dy, za + 0.05], 0.05, 0.04, 'y', 24, GALV);
            mb.cyl([sx * 0.40, s * (dy - 0.026), za + 0.05], 0.062, 0.010, 'y', 24, GALV);
            mb.cyl([sx * 0.40, s * (dy + 0.04), za + 0.05], 0.022, 0.05, 'y', 12, DARK);
        }
    }
    const zd = z1 + 0.20;
    for (const sy of [-1, 1]) {
        const yd = sy * 0.58;
        mb.cyl([0.06, yd, zd], 0.018, 1.48, 'x', 14, GALV);
        for (const sx of [-1, 1]) {
            mb.cyl([sx * 0.52, yd, zd], 0.060, 0.07, 'x', 28, GALV);
            for (const e of [-1, 1]) mb.cyl([sx * 0.52 + e * 0.038, yd, zd], 0.085, 0.006, 'x', 28, GALV);
            mb.cyl([sx * 0.52, yd, zd], 0.0635, 0.05, 'x', 28, DARK);
            mb.span([sx * 0.52 - 0.025, sy * 0.52 - 0.003, zb], [sx * 0.52 + 0.025, sy * 0.52 + 0.003, zd], DARK);
            mb.box([sx * (tx - tw / 2), yd, zb + 0.042], [0.07, 0.07, 0.084], DARK);
            for (const e of [-1, 1]) mb.bolt([sx * (tx - tw / 2), yd + e * 0.05, zb + 0.004], 0.007, 0.006, 'z', GALV, false);
        }
    }
    mb.span([tx + 0.03, -0.60, zd - 0.06], [tx + 0.075, 0.60, zd + 0.06], TEAL);
    gearMotor(mb, [tx + 0.14, 0.0, zd], 'x', 1, TEAL, GALV, 0.075, 0.26);
    mb.box([-tx - 0.10, 0.25, za + 0.17], [0.16, 0.26, 0.30], GREY);
    mb.box([-tx - 0.183, 0.25, za + 0.17], [0.006, 0.22, 0.26], GREY);
    for (let k = 0; k < 3; k++) mb.cyl([-tx - 0.10, 0.17 + 0.08 * k, za + 0.008], 0.011, 0.024, 'z', 6, GALV);
    mb.span([-tx - 0.10 - 0.02, 0.38, za + 0.05], [-tx - 0.10 + 0.02, ty + 0.10, za + 0.07], GALV);
    mb.box([-tx - 0.10, ty + 0.10, za + 0.02], [0.05, 0.05, 0.08], DARK);
    X.replace(X.fin(mb.mesh('crane_trolley', MATS), 0.003, 0.014, 0.06));
    // ---------------------------------------------------------------- a belt: flat webbing, its two selvedges proud
    mb = new MB();
    mb.span([-0.025, -0.003, -1.0], [0.025, 0.003, 0.0], 0);
    for (const s of [-1, 1]) mb.span([s * 0.0225 - 0.0025, -0.0042, -1.0], [s * 0.0225 + 0.0025, 0.0042, 0.0], 0);
    X.replace(mb.mesh('crane_belt', ['belt_webbing']));
    // ---------------------------------------------------------------- the ring that comes down round a hood
    const ro = G.ring_half_out, ri = G.ring_half_in, rm = (ro + ri) / 2, rw = ro - ri;
    mb = new MB();
    for (const s of [-1, 1]) {
        mb.span([-ro, s * rm - rw / 2, -0.04], [ro, s * rm + rw / 2, 0.04], WH);
        mb.span([s * rm - rw / 2, -ri, -0.04], [s * rm + rw / 2, ri, 0.04], WH);
    }
    for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
        mb.prism([[sx * (ro - 0.005), sy * (ro - 0.005)], [sx * (ro - 0.30), sy * (ro - 0.005)], [sx * (ro - 0.30), sy * (ri + 0.005)],
            [sx * (ri + 0.005), sy * (ri + 0.005)], [sx * (ri + 0.005), sy * (ro - 0.30)], [sx * (ro - 0.005), sy * (ro - 0.30)]], 0.04, 0.046, 'z', WH);
        for (const [a, b] of [[0.06, 0.06], [0.24, 0.06], [0.06, 0.24]]) mb.bolt([sx * (ro - a), sy * (ro - b), 0.05], 0.008, 0.006, 'z', GALV, false);
        for (const e of [-1, 1]) mb.box([sx * 0.52 + e * 0.032, sy * 0.52, 0.078], [0.010, 0.05, 0.064], GALV);
        mb.cyl([sx * 0.52, sy * 0.52, 0.086], 0.008, 0.086, 'x', 12, GALV);
        mb.cyl([sx * 0.52, sy * 0.52, 0.086], 0.012, 0.05, 'x', 14, DARK);
    }
    for (let a = 0; a < 4; a++) {                                      // the four grippers: a cylinder block, guide bushes, air lines
        const ca = Math.round(Math.cos(a * PI / 2)), sa = Math.round(Math.sin(a * PI / 2));
        const W = (p) => [p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca, p[2]];
        const wbox = (c, s_, mi) => mb.box(W(c), a % 2 === 0 ? [s_[0], s_[1], s_[2]] : [s_[1], s_[0], s_[2]], mi);
        const ax = a % 2 === 0 ? 'x' : 'y';
        wbox([rm, 0.0, -0.105], [0.06, 0.20, 0.13], TEAL);
        wbox([rm + 0.033, 0.0, -0.105], [0.006, 0.17, 0.11], GALV);
        for (const e of [-1, 1]) {
            mb.cyl(W([rm - 0.036, e * 0.075, -0.105]), 0.016, 0.014, ax, 16, GALV);
            mb.bolt(W([rm + 0.038, e * 0.07, -0.065]), 0.006, 0.005, ax, GALV, false);
            mb.bolt(W([rm + 0.038, e * 0.07, -0.145]), 0.006, 0.005, ax, GALV, false);
            mb.cyl(W([rm, e * 0.05, -0.034]), 0.007, 0.012, 'z', 8, GALV);
            mb.tube([W([rm, e * 0.05, -0.03]), W([rm + 0.075, e * 0.05, -0.02]), W([rm + 0.085, e * 0.05, 0.03]), W([rm + 0.03, e * 0.06, 0.056]),
                W([rm, e * 0.20, 0.052]), W([rm - 0.005, e * 0.40, 0.052])], 0.004, 6, RUB);
        }
    }
    mb.box([-rm, -rm + 0.02, 0.085], [0.09, 0.14, 0.07], GREY);
    for (let k = 0; k < 4; k++) mb.cyl([-rm + 0.05, -rm - 0.025 + 0.03 * k, 0.085], 0.006, 0.014, 'x', 6, GALV);
    X.replace(X.fin(mb.mesh('crane_ring', MATS), 0.003, 0.012, 0.05));
    // ---------------------------------------------------------------- a gripper's pad: grooved rubber on a plate, a rod, two pins
    mb = new MB();
    mb.span([0.014, -0.12, -0.05], [0.02, 0.12, 0.05], 1);
    mb.span([0.004, -0.118, -0.048], [0.014, 0.118, 0.048], 0);
    for (let k = 0; k < 7; k++) { const y = -0.105 + 0.035 * k; mb.span([0.0, y - 0.011, -0.046], [0.004, y + 0.011, 0.046], 0); }
    mb.cyl([0.065, 0, 0], 0.014, 0.09, 'x', 14, 1);
    for (const e of [-1, 1]) mb.cyl([0.05, e * 0.075, 0], 0.008, 0.06, 'x', 10, 1);
    X.replace(X.fin(mb.mesh('crane_pad', ['rubber_black', 'steel_galv']), 0.0015, 0.006, 0.02));
}

// ====================================================================================================== the meter cabinet
// a sheet steel enclosure on a plinth frame, its right side to the east wall: door with a glazed window (bezel,
// gasket, screws), a label plate on rivets, pressed louvres, three hinges, a swing handle, a hasp and its padlock,
// lifting eyes, the back's screwed panel, two conduits up into the cable tray
export function cabinet(X, trayZ) {
    const { L } = X, MC = L.meter_cabinet;
    let [cx0, cx1] = MC.x;
    const [cy0, cy1] = MC.y;
    cx1 = Math.min(cx1, X.HX1 - 0.09 - 0.012);                         // clear of the wall's dado
    const cxm = (MC.x[0] + MC.x[1]) / 2;                               // the window's middle stays where the drums are
    const wz = MC.window_z, [ww, wh] = MC.window, zp = MC.plinth, zt = zp + MC.h, dy = cy1;
    const [PAINT, GALV, DARK, RUB, ALU, BRASS, TEAL] = [0, 1, 2, 3, 4, 5, 6];
    const mb = new MB();
    for (const [a, b] of [[[cx0, cy0], [cx1, cy0 + 0.04]], [[cx0, cy1 - 0.04], [cx1, cy1]], [[cx0, cy0 + 0.04], [cx0 + 0.04, cy1 - 0.04]], [[cx1 - 0.04, cy0 + 0.04], [cx1, cy1 - 0.04]]]) {
        mb.span([a[0] + 0.006, a[1] + 0.006, 0.0], [b[0] - 0.006, b[1] - 0.006, zp], TEAL);
    }
    for (const x of [cx0, cx1]) for (const y of [cy0, cy1]) {
        const sx = x === cx0 ? 1 : -1, sy = y === cy0 ? 1 : -1;
        mb.span([Math.min(x, x + sx * 0.07), Math.min(y, y + sy * 0.07), 0.0], [Math.max(x, x + sx * 0.07), Math.max(y, y + sy * 0.07), zp], TEAL);
    }
    mb.tub([cx0, cy0, zp], [cx1, dy - 0.004, zt], 0.02, PAINT);
    mb.span([cx0 - 0.012, cy0 - 0.012, zt], [cx1 + 0.004, dy + 0.03, zt + 0.012], TEAL);
    for (const x of [cx0 + 0.06, cx1 - 0.06]) for (const y of [cy0 + 0.06, dy - 0.07]) {
        mb.cyl([x, y, zt + 0.018], 0.012, 0.012, 'z', 6, GALV);
        const ring = mb.arc([x, y, zt + 0.045], 0.018, 0.0, 2 * PI, 'y', 12);
        mb.tube([...ring.slice(0, -1), ring[0]], 0.005, 8, GALV, false);
    }
    mb.frame([cx0 + 0.012, dy - 0.004, zp + 0.012], [cx1 - 0.012, dy + 0.002, zt - 0.012], [cx0 + 0.034, zp + 0.034], [cx1 - 0.034, zt - 0.034], RUB);
    const d0 = dy + 0.002, d1 = dy + 0.018, xa = cx0 + 0.008, xb = cx1 - 0.008;
    const hole = [[cxm - ww / 2, wz - wh / 2], [cxm + ww / 2, wz + wh / 2]];
    mb.frame([xa, d0, zp + 0.012], [xb, d1, zt - 0.012], hole[0], hole[1], PAINT);
    const bz = 0.016;
    mb.frame([cxm - ww / 2 - bz, d1, wz - wh / 2 - bz], [cxm + ww / 2 + bz, d1 + 0.005, wz + wh / 2 + bz], hole[0], hole[1], ALU);
    for (const sx of [-1, 0, 1]) for (const sz of [-1, 1]) mb.cyl([cxm + sx * (ww / 2 + bz / 2 - 0.002) * (sx ? 1 : 0), d1 + 0.0056, wz + sz * (wh / 2 + bz / 2)], 0.0042, 0.0014, 'y', 12, GALV);
    const g_ = 0.0035;
    mb.span([cxm - ww / 2, dy + 0.0045, wz + wh / 2 - g_], [cxm + ww / 2, d1 + 0.001, wz + wh / 2], RUB);
    mb.span([cxm - ww / 2, dy + 0.0045, wz - wh / 2], [cxm + ww / 2, d1 + 0.001, wz - wh / 2 + g_], RUB);
    mb.span([cxm - ww / 2, dy + 0.0045, wz - wh / 2 + g_], [cxm - ww / 2 + g_, d1 + 0.001, wz + wh / 2 - g_], RUB);
    mb.span([cxm + ww / 2 - g_, dy + 0.0045, wz - wh / 2 + g_], [cxm + ww / 2, d1 + 0.001, wz + wh / 2 - g_], RUB);
    mb.span([cxm - 0.13, d1, wz + 0.07], [cxm + 0.13, d1 + 0.0025, wz + 0.14], ALU);
    for (const sx of [-1, 1]) for (const sz of [0.078, 0.132]) mb.cyl([cxm + sx * 0.122, d1 + 0.003, wz + sz], 0.0032, 0.0016, 'y', 10, GALV);
    for (let i = 0; i < 7; i++) { const lz = zp + 0.16 + 0.035 * i; mb.prism([[d1, lz], [d1 + 0.011, lz], [d1, lz + 0.024]], cxm - 0.22, cxm + 0.22, 'x', PAINT); }
    for (let i = 0; i < 6; i++) { const lz = zp + 1.45 + 0.035 * i; mb.prism([[cy0, lz], [cy0 - 0.011, lz], [cy0, lz + 0.024]], cxm - 0.22, cxm + 0.22, 'x', PAINT); }
    const bp = 0.0025;
    mb.span([cx0 + 0.03, cy0 - bp, zp + 0.03], [cx1 - 0.03, cy0, zp + 1.38], PAINT);
    for (const z of linspace(zp + 0.05, zp + 1.36, 6)) for (const x of [cx0 + 0.045, cx1 - 0.045]) mb.cyl([x, cy0 - bp - 0.0008, z], 0.0045, 0.0016, 'y', 12, GALV);
    for (const x of linspace(cx0 + 0.045, cx1 - 0.045, 5).slice(1, -1)) for (const z of [zp + 0.05, zp + 1.36]) mb.cyl([x, cy0 - bp - 0.0008, z], 0.0045, 0.0016, 'y', 12, GALV);
    mb.span([cxm - 0.05, cy0 - 0.002, zp + 1.75], [cxm + 0.05, cy0, zp + 1.81], ALU);
    for (const hz of [zp + 0.22, (zp + zt) / 2, zt - 0.22]) {
        mb.cyl([xb + 0.004, d1 - 0.004, hz], 0.008, 0.07, 'z', 12, GALV);
        mb.box([xb - 0.02, d1 + 0.0015, hz], [0.045, 0.003, 0.06], GALV);
    }
    const hx = cx0 + 0.0675;
    mb.box([hx, d1 + 0.004, 1.11], [0.04, 0.008, 0.19], DARK);
    mb.cyl([hx, d1 + 0.016, 1.16], 0.012, 0.018, 'y', 16, DARK);
    mb.tube([[hx, d1 + 0.022, 1.16], [hx, d1 + 0.034, 1.155], [hx, d1 + 0.038, 1.13], [hx, d1 + 0.038, 1.03]], 0.008, 10, DARK);
    mb.cyl([hx, d1 + 0.009, 1.045], 0.006, 0.004, 'y', 12, GALV);
    mb.box([cx0 + 0.0675, d1 + 0.002, 1.28], [0.065, 0.004, 0.06], GALV);
    for (const sx_ of [0.052, 0.084]) mb.bolt([cx0 + sx_ + (sx_ > 0.06 ? 0.012 : -0.012), d1 + 0.0055, 1.262], 0.0045, 0.003, 'y', GALV, false);
    mb.tube([[cx0 + 0.052, d1 + 0.004, 1.285], [cx0 + 0.052, d1 + 0.024, 1.285], ...mb.arc([cx0 + 0.068, d1 + 0.024, 1.285], 0.016, PI, 0.0, 'z', 8).slice(1),
        [cx0 + 0.084, d1 + 0.004, 1.285]], 0.004, 8, GALV);
    const px = cx0 + 0.068, py_ = d1 + 0.031, pz = 1.2235;
    mb.box([px, py_, pz], [0.046, 0.022, 0.050], BRASS);
    mb.tube([[px - 0.012, py_, pz + 0.025], [px - 0.012, py_, pz + 0.058], ...mb.arc([px, py_, pz + 0.058], 0.012, -PI / 2, PI / 2, 'y', 8).slice(1),
        [px + 0.012, py_, pz + 0.025]], 0.0035, 8, GALV);
    mb.cyl([px, py_ - 0.0115, pz - 0.008], 0.005, 0.002, 'y', 12, GALV);
    for (const px2 of [cx1 - 0.10, cx1 - 0.20]) {
        mb.bolt([px2, cy0 + 0.10, zt + 0.018], 0.016, 0.012, 'z', GALV);
        mb.cyl([px2, cy0 + 0.10, (zt + 0.02 + trayZ + 0.03) / 2], 0.0125, trayZ + 0.03 - zt - 0.02, 'z', 12, GALV);
    }
    X.replace(X.fin(mb.mesh('meter_cabinet', ['cabinet_grey', 'steel_galv', 'steel_dark', 'rubber_black', 'plate_alu', 'brass', 'machine_teal']), 0.0018, 0.01, 0.05, 0.0));
}
