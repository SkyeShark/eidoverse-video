// eidoverse/sets/wake_another_one/hall/build.js — the hall's layout, from layout.json: a port of the Blender edition's
// eidoblend.sets.wake_another_one.hall.build. No three.js (the machines' tests read it in plain deno).
//
//   const lay = new Layout(layout, { small }).run();   // every part, rigged, in flat colours; lay.report says what it made
//
// What it makes, as the Blender layout's collections (graph.js): hall_shell (floor with the tracks' pits cut out,
// walls, roof, strip lights, the office window), racks and boxes_stock (closed cartons on points), line_module (ONE
// line's fixed parts, instanced at every line), lines (per line NN: line_NN, its units line_NN_unit_K, its lead mark,
// its instancers), line_hero (the hero line's own driven parts), machinery (the hero crane, its pendant, the main track
// and its stream, every other line's crane), meter_cabinet, returns_cage, dock, cameras, layout_lights, marks, and
// assets (only drawn through instancers).
// THE MACHINES are driven by the controls (CONTROLS, hall.js): each of the Blender edition's simple-expression drivers
// is one function here (Scene.drive), evaluated in order by Scene.evaluate(state); the lookup curves are the same
// keys (a smoothstep sampled at eleven points, linear between them); the hoods' COPY_TRANSFORMS switches are parent
// switches (Node.copy).
// FRAMES: line_NN_unit_K and line_NN_lead have local -Y as the way a body there faces and +X its left; a unit IS its
// tray's frame (a body stands at the carton's body_mark in it).
import { MB, PI } from './kit.js';
import { Scene, Node, M4 } from './graph.js';
import * as CARTON from './carton.js';

export const RAD = (d) => d * PI / 180.0;

// '#rrggbb' -> linear rgb
export function srgb(h) {
    return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255.0).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
}

// the keys of a smoothstep ramp from (a, y0) to (b, y1), eleven of them (a driver's lookup curve: linear between)
export function ramp(a, b, y0 = 0.0, y1 = 1.0, n = 10) {
    const out = [];
    for (let i = 0; i <= n; i++) {
        const t = i / n, s = t * t * (3 - 2 * t);
        out.push([a + (b - a) * t, y0 + (y1 - y0) * s]);
    }
    return out;
}

// a curve's value at x: linear between its keys, constant past its ends (keys inserted at one x keep the last)
export function lookup(keys, x) {
    const k = [];
    for (const p of keys) { const j = k.findIndex((q) => q[0] === p[0]); if (j >= 0) k[j] = p; else k.push(p); }
    k.sort((a, b) => a[0] - b[0]);
    if (x <= k[0][0]) return k[0][1];
    for (let i = 1; i < k.length; i++) if (x <= k[i][0]) return k[i - 1][1] + (k[i][1] - k[i - 1][1]) * (x - k[i - 1][0]) / (k[i][0] - k[i - 1][0]);
    return k[k.length - 1][1];
}
const clamp = (x, a, b) => Math.min(Math.max(x, a), b);

// a flush roller track in its pit: rollers across `axis`' travel, tops at z 0; curbs along the two long sides (gap:
// a (lo, hi) stretch of the low-coordinate side's curb left open). T: layout.line.track
export function track_mesh(mb, T, x0, x1, y0, y1, axis, gap = null) {
    const d = T.pit_depth, r = T.roller_d / 2;
    mb.quad([[x0, y0, -d], [x1, y0, -d], [x1, y1, -d], [x0, y1, -d]], 1);
    mb.quad([[x0, y0, 0], [x1, y0, 0], [x1, y0, -d], [x0, y0, -d]], 1);
    mb.quad([[x1, y0, 0], [x1, y1, 0], [x1, y1, -d], [x1, y0, -d]], 1);
    mb.quad([[x1, y1, 0], [x0, y1, 0], [x0, y1, -d], [x1, y1, -d]], 1);
    mb.quad([[x0, y1, 0], [x0, y0, 0], [x0, y0, -d], [x0, y1, -d]], 1);
    const p = T.roller_pitch, cw = T.curb_w, ch = T.curb_h;
    if (axis === 'y') {
        let k = Math.floor((y0 + r) / p - 0.5) + 1;
        while ((k + 0.5) * p <= y1 - r - 0.004) { mb.cyl([(x0 + x1) / 2, (k + 0.5) * p, -r], r, (x1 - x0) - 0.08, 'x', 10, 0); k++; }
        for (const [xs, side] of [[x0 - cw / 2, 0], [x1 + cw / 2, 1]]) {
            let segs = [[y0, y1]];
            if (gap && side === 0) segs = [[y0, gap[0]], [gap[1], y1]];
            for (const [a, b] of segs) if (b - a > 0.01) mb.span([xs - cw / 2, a, 0], [xs + cw / 2, b, ch], 0);
        }
    } else {
        let k = Math.floor((x0 + r) / p - 0.5) + 1;
        while ((k + 0.5) * p <= x1 - r - 0.004) { mb.cyl([(k + 0.5) * p, (y0 + y1) / 2, -r], r, (y1 - y0) - 0.08, 'y', 10, 0); k++; }
        for (const ys of [y0 - cw / 2, y1 + cw / 2]) mb.span([x0, ys - cw / 2, 0], [x1, ys + cw / 2, ch], 0);
    }
}

// a floor of quads with rectangular holes (x0, x1, y0, y1) left out
export function floorWithHoles(name, x0, x1, y0, y1, holes, material, z = 0.0) {
    const xs = [...new Set([x0, x1, ...holes.flatMap((h) => [h[0], h[1]]).filter((x) => x0 < x && x < x1)])].sort((a, b) => a - b);
    const ys = [...new Set([y0, y1, ...holes.flatMap((h) => [h[2], h[3]]).filter((y) => y0 < y && y < y1)])].sort((a, b) => a - b);
    const mb = new MB();
    for (let i = 0; i < xs.length - 1; i++) {
        for (let j = 0; j < ys.length - 1; j++) {
            const cx = (xs[i] + xs[i + 1]) / 2, cy = (ys[j] + ys[j + 1]) / 2;
            if (holes.some((h) => h[0] < cx && cx < h[1] && h[2] < cy && cy < h[3])) continue;
            mb.quad([[xs[i], ys[j], z], [xs[i + 1], ys[j], z], [xs[i + 1], ys[j + 1], z], [xs[i], ys[j + 1], z]]);
        }
    }
    return mb.mesh(name, [material], false);
}

// a camera at pos aimed at aim (its frame's top toward `up`): { pos, aim, up, lens (mm, 36 mm sensor), ortho, focus }
export function lookAt(pos, aim, lens = 50.0, up = [0, 0, 1], ortho = null) {
    return { pos: [...pos], aim: [...aim], up: [...up], lens, ortho, focus: Math.hypot(aim[0] - pos[0], aim[1] - pos[1], aim[2] - pos[2]) };
}

// ======================================================================================================== the layout
export class Layout {
    constructor(L, { small = false, log = console.log } = {}) {
        this.L = L; this.small = !!small; this.log = log;
        this.T0 = performance.now();
        this.report = { small: this.small, steps: [] };
        this.S = new Scene();
        this.meshes = new Map();
        this.M = {};                                                   // the flat colours, by material name
        this.controls = {}; this.cams = {};
        const H = L.hall, sm = H.small || {};
        this.ROWS = small ? (sm.rows ?? 2) : H.rows;
        this.LANES = small ? H.lanes_x.slice(0, sm.lanes ?? 2) : H.lanes_x;
        [this.HX0, this.HX1] = H.x;
        this.HY0 = small ? (sm.y0 ?? -45.0) : H.y[0];
        this.HY1 = H.y[1];
        this.LN = L.line;
        this.PITCH = this.LN.pitch;
        this.YAW = RAD(this.LN.tray_yaw);
        this.G = L.gantry;
        this.ST = this.LN.stack;
    }

    say(...a) { this.log(`[hall ${((performance.now() - this.T0) / 1000).toFixed(1).padStart(6)} s] ${a.join(' ')}`); }
    step(what) { this.say(what); this.report.steps.push([+((performance.now() - this.T0) / 1000).toFixed(1), what]); }

    run() {
        this.collections();
        this.materials();
        this.step('1. the carton'); this.carton();
        this.step('2. the line module'); this.module();
        this.step('3. the controls and the other lines\' moving copies'); this.controlEmpties();
        this.step('4. the shell: floor, walls, roof, lights, the office window'); this.linesPlan(); this.shell();
        this.step('5. racks and stock'); this.racks();
        this.step(`6. the lines: ${this.LINES.length} of them`); this.lines();
        this.step('7. the hero line: its hoods, the two cartons at unit_0, its crane'); this.hero();
        this.step('8. the main track, its stream, the spurs'); this.mainTrack();
        this.step('9. the meter cabinet and its drums'); this.meter();
        this.step('10. the returns cage and its cartons'); this.cage();
        this.step('11. the dock door and the apron'); this.dock();
        this.step('12. the cameras'); this.cameras();
        this.step('13. the layout\'s light'); this.light();
        return this;
    }

    // ------------------------------------------------------------------------------------------------ scene helpers
    mesh(md) { this.meshes.set(md.name, md); return md.name; }
    newOb(name, mesh, coll, loc = [0, 0, 0], rz = 0.0, parent = null) {
        return this.S.add(new Node(name, { mesh, loc, rot: [0, 0, rz], parent }), coll);
    }
    empty(name, loc, coll, rz = 0.0, parent = null) { return this.newOb(name, null, coll, loc, rz, parent); }
    inst(name, what, loc, coll, rz = 0.0, parent = null) { const o = this.empty(name, loc, coll, rz, parent); o.inst = what; return o; }
    points(name, pts, source, coll, rz = 0.0, parent = null) {
        const o = this.empty(name, [0, 0, 0], coll, 0.0, parent);
        o.points = { pts, rz, source };
        return o;
    }
    world(name) { return this.S.world(typeof name === 'string' ? this.S.get(name) : name); }

    collections() {
        this.S.coll('hall');
        this.C = {};
        for (const n of ['hall_shell', 'racks', 'boxes_stock', 'line_module', 'lines', 'line_hero', 'machinery', 'meter_cabinet', 'returns_cage',
            'dock', 'cameras', 'layout_lights', 'marks', 'assets']) this.C[n] = this.S.coll(n, 'hall');
        this.S.colls.get('assets').excluded = true;
    }

    mat(name, rgb, rough = 0.5, metal = 0.0, emit = null, strength = 0.0) {
        if (!this.M[name]) this.M[name] = { rgb, rough, metal, emit, strength };
        return name;
    }

    // flat colours for the layout, under the names the look rebuilds in place
    materials() {
        const m = this.mat.bind(this);
        m('hall_concrete', [0.42, 0.43, 0.43], 0.62); m('hall_wall_panel', [0.70, 0.72, 0.73], 0.6); m('hall_roof', [0.55, 0.57, 0.59], 0.7);
        m('steel_galv', [0.55, 0.57, 0.58], 0.38, 0.85); m('steel_dark', [0.06, 0.065, 0.07], 0.5, 0.6);
        m('machine_white', srgb('#d9e0df'), 0.42); m('machine_teal', srgb('#398b91'), 0.42); m('rubber_black', [0.02, 0.02, 0.02], 0.8);
        m('rack_upright', [0.62, 0.65, 0.67], 0.45, 0.3); m('rack_beam', [0.36, 0.40, 0.43], 0.45, 0.3); m('floor_line_paint', [0.78, 0.80, 0.80], 0.55);
        m('strip_light_glow', [0.9, 0.93, 1.0], 0.4, 0.0, [0.82, 0.90, 1.0], 6.0); m('office_frosted_glow', [0.9, 0.86, 0.78], 0.6, 0.0, [1.0, 0.86, 0.66], 4.0);
        m('paper_placeholder', [0.80, 0.78, 0.72], 0.7); m('glass_placeholder', [0.25, 0.30, 0.33], 0.05); m('cabinet_grey', [0.33, 0.36, 0.37], 0.5, 0.4);
        m('drum_white', [0.82, 0.82, 0.80], 0.5); m('drum_ink', [0.015, 0.015, 0.015], 0.6); m('dock_apron', [0.50, 0.48, 0.45], 0.7);
        m('carton_board', [0.80, 0.78, 0.72], 0.65); m('carton_insert', [0.52, 0.48, 0.41], 0.85);
    }

    // ------------------------------------------------------------------------------------------------ 1. the carton
    carton() {
        const CT = CARTON.build(this.L.carton);
        for (const md of Object.values(CT.meshes)) this.mesh(md);
        const A = 'assets';
        this.CT = {};
        for (const [key, names] of Object.entries(CT.sets)) {
            const c = this.S.coll('carton_' + key, A);
            for (const nm of names) this.newOb(`carton_${key}|${nm}`, nm, c);
            this.CT[key] = c;
        }
        this.report.carton = CT.meas;
        this.SEAM = CT.meas.seam_z; this.HOOD_H = CT.meas.hood_height;
        this.RING_TO_ORIGIN = this.G.ring_to_hood_bottom + this.SEAM;          // the ring over a hood set's origin
        this.Z_TOP = this.G.ring_top;
        this.Z_TRAY = this.RING_TO_ORIGIN;                                    // the ring's height gripping a hood on a tray
        this.N_SLOTS = this.ST.cols * this.ST.levels;
    }

    // the origin of a hood set standing in the stack's slot j (its hood's foot is SEAM above it)
    slotXYZ(j) {
        const ST = this.ST;
        return [ST.x, ST.y0 - ST.col_pitch * Math.floor(j / ST.levels), ST.base_h + this.HOOD_H * (j % ST.levels) - this.SEAM];
    }

    // ------------------------------------------------------------------------------------------------ 2. the line module
    module() {
        const { L, LN, G, ST } = this;
        const CM = this.C.line_module;
        const T = LN.track, hw = T.half_width;
        let mb = new MB();
        track_mesh(mb, T, -hw, hw, T.y0, T.y1, 'y', [-hw, hw]);
        this.newOb('line_track', this.mesh(mb.mesh('line_track', ['steel_galv', 'steel_dark'])), CM);
        mb = new MB();                                                 // the hood stack's base
        const ya = ST.y0 + ST.col_pitch / 2, yb = ST.y0 - ST.col_pitch * (ST.cols - 0.5);
        mb.span([ST.x - 0.475, yb, 0], [ST.x + 0.475, ya, ST.base_h]);
        for (let c = 0; c <= ST.cols; c++) {
            const y = ya - ST.col_pitch * c;
            mb.span([ST.x - 0.475, y - 0.012, ST.base_h], [ST.x + 0.475, y + 0.012, ST.base_h + 0.02]);
        }
        this.newOb('line_hood_stack_base', this.mesh(mb.mesh('line_hood_stack_base', ['steel_galv'])), CM);
        const LE = LN.lectern, lx = LE.x, ly = LE.y;                   // the lectern
        mb = new MB();
        mb.span([lx - 0.24, ly - 0.20, 0], [lx + 0.24, ly + 0.20, 0.012]);
        mb.span([lx - 0.04, ly - 0.04, 0.012], [lx + 0.04, ly + 0.04, LE.top_h - 0.06]);
        mb.span([lx - 0.26, ly - 0.15, 0.54], [lx + 0.26, ly + 0.15, 0.552]);
        mb.span([lx - 0.26, ly + 0.138, 0.552], [lx + 0.26, ly + 0.15, 0.60]);
        this.newOb('line_lectern', this.mesh(mb.mesh('line_lectern', ['steel_galv'])), CM);
        mb = new MB();
        const w = LE.top_w, d = LE.top_d;
        mb.span([-w / 2, -d / 2, -0.012], [w / 2, d / 2, 0]);
        mb.span([-w / 2, -d / 2, 0], [w / 2, -d / 2 + 0.012, 0.022]);
        mb.span([-w / 2, d / 2 - 0.05, 0], [w / 2, d / 2 - 0.045, 0.010]);
        const top = this.newOb('line_lectern_top', this.mesh(mb.mesh('line_lectern_top', ['steel_galv'])), CM, [lx, ly, LE.top_h]);
        top.rot = [RAD(LE.tilt), 0, 0];                                // low toward -Y, where the station stands
        mb = new MB();                                                 // the crane's runway
        const zt = G.rail_top;
        G.rail_x.forEach((rx, i) => {
            const posts = i === 0 ? G.post_y_west : G.post_y_east;
            mb.span([rx - 0.07, G.rail_y[0], zt - 0.26], [rx + 0.07, G.rail_y[1], zt]);
            mb.span([rx - 0.035, G.rail_y[0], zt], [rx + 0.035, G.rail_y[1], zt + 0.03], 1);
            for (const py of posts) {
                mb.span([rx - 0.07, py - 0.07, 0], [rx + 0.07, py + 0.07, zt - 0.26]);
                mb.span([rx - 0.16, py - 0.16, 0], [rx + 0.16, py + 0.16, 0.016]);
            }
            const hwt = G.hang_w / 2;
            for (const py of G.hang_y) {
                mb.span([rx - hwt, py - hwt, zt], [rx + hwt, py + hwt, L.hall.roof_z]);
                mb.span([rx - 0.12, py - 0.12, zt], [rx + 0.12, py + 0.12, zt + 0.02]);
                mb.span([rx - 0.14, py - 0.14, L.hall.roof_z - 0.02], [rx + 0.14, py + 0.14, L.hall.roof_z]);
            }
        });
        for (const ty of G.rail_y) mb.span([G.rail_x[0], ty - 0.06, zt - 0.22], [G.rail_x[1], ty + 0.06, zt - 0.04]);
        this.newOb('line_crane_runway', this.mesh(mb.mesh('line_crane_runway', ['machine_white', 'steel_galv'])), CM);
        const P = G.pendant;                                           // the pendant's mast
        mb = new MB();
        mb.cyl([P.mast_x, P.y, (P.hang_z + 0.05) / 2], 0.03, P.hang_z + 0.05, 'z', 12, 0);
        mb.cyl([P.mast_x, P.y, 0.008], 0.11, 0.016, 'z', 16, 0);
        mb.span([P.mast_x, P.y - 0.02, P.hang_z], [P.x + 0.03, P.y + 0.02, P.hang_z + 0.04], 0);
        this.newOb('line_pendant_mast', this.mesh(mb.mesh('line_pendant_mast', ['machine_white'])), CM);
        mb = new MB();                                                 // floor lines
        const MK = LN.marks;
        for (const x of [MK.x_a, MK.x_b, G.rail_x[0] - 0.25]) {
            mb.quad([[x - MK.line_w / 2, G.rail_y[0], 0.002], [x + MK.line_w / 2, G.rail_y[0], 0.002], [x + MK.line_w / 2, G.rail_y[1], 0.002], [x - MK.line_w / 2, G.rail_y[1], 0.002]]);
        }
        const sx = lx, sy = ly - LE.stand_back;
        for (const [a, b] of [[[sx - 0.35, sy - 0.30], [sx + 0.35, sy - 0.26]], [[sx - 0.35, sy + 0.26], [sx + 0.35, sy + 0.30]],
            [[sx - 0.35, sy - 0.30], [sx - 0.31, sy + 0.30]], [[sx + 0.31, sy - 0.30], [sx + 0.35, sy + 0.30]]]) {
            mb.quad([[a[0], a[1], 0.002], [b[0], a[1], 0.002], [b[0], b[1], 0.002], [a[0], b[1], 0.002]]);
        }
        this.newOb('line_floor_lines', this.mesh(mb.mesh('line_floor_lines', ['floor_line_paint'], false)), CM);
        // what stands on a line, as instanced sets
        const A = 'assets';
        this.C_TRAYS = this.S.coll('line_trays', A);                  // units 0..9's trays
        this.C_TRAYS_HERO = this.S.coll('line_trays_hero', A);        // units 1..9's (unit_0's swap on the hero line)
        for (let K = 0; K < LN.units; K++) {
            this.inst(`tray_${K}`, this.CT.tray, [0, K * this.PITCH, 0], this.C_TRAYS, this.YAW);
            if (K >= 1) this.inst(`tray_hero_${K}`, this.CT.tray, [0, K * this.PITCH, 0], this.C_TRAYS_HERO, this.YAW);
        }
        this.C_PROPS = this.S.coll('line_props_placeholders', A);
        this.lecternDressing(this.C_PROPS, top);
        this.C_DRESS = this.S.coll('line_dressing', A);               // every other line's: the placeholders, a pendant that does not move
        this.inst('dressing_props', this.C_PROPS, [0, 0, 0], this.C_DRESS);
        this.pendant(this.C_DRESS, null, 'pendant_static');
    }

    // the crane's hanging control: a cable from its arm, a body at hand height, a button facing -Y
    pendant(coll, parent, name) {
        const P = this.G.pendant;
        if (!this.meshes.has('pendant_body')) {
            let mb = new MB();
            mb.cyl([0, 0, (P.hang_z + P.z + 0.12) / 2 - P.z], 0.006, P.hang_z - P.z - 0.12, 'z', 8, 1);
            mb.span([-0.035, -0.0275, -0.12], [0.035, 0.0275, 0.12], 0);
            mb.cyl([0, 0, 0.13], 0.016, 0.03, 'z', 24, 1);
            mb.cyl([0, -0.030, -0.03], 0.011, 0.006, 'y', 32, 1);
            mb.cyl([0, -0.0285, P.button_z - P.z], 0.023, 0.003, 'y', 40, 1);
            this.mesh(mb.mesh('pendant_body', ['machine_teal', 'steel_dark']));
            mb = new MB();
            mb.cyl([0, -0.006, 0], 0.018, 0.012, 'y', 40, 0);
            this.mesh(mb.mesh('pendant_button', ['machine_white']));
        }
        const body = this.newOb(name, 'pendant_body', coll, [P.x, P.y, P.z], 0.0, parent);
        const button = this.newOb(name + '_button', 'pendant_button', coll, [0, -0.0275, P.button_z - P.z], 0.0, body);
        return [body, button];
    }

    // blank stand-ins on the lectern's top (a clipboard, a stack of cards, pencils, a closed notebook), and empties
    // where real ones go (place_*)
    lecternDressing(coll, top) {
        const par = this.empty('lectern_top_frame', [...top.loc], coll);
        par.rot = [...top.rot];
        let mb = new MB();
        mb.span([-0.285, -0.19, 0], [-0.045, 0.14, 0.006], 0);
        mb.span([-0.280, -0.185, 0.006], [-0.050, 0.11, 0.009], 1);
        mb.span([-0.215, 0.105, 0.006], [-0.115, 0.14, 0.020], 2);
        this.newOb('ph_clipboard', this.mesh(mb.mesh('ph_clipboard', ['steel_dark', 'paper_placeholder', 'steel_galv'])), coll, [0, 0, 0], 0, par);
        mb = new MB();
        mb.span([0.16, 0.0, 0], [0.265, 0.148, 0.022], 0);
        this.newOb('ph_cards', this.mesh(mb.mesh('ph_cards', ['paper_placeholder'])), coll, [0, 0, 0], 0, par);
        mb = new MB();
        for (let i = 0; i < 3; i++) mb.cyl([0.05, 0.195 + 0.009 * i, 0.0045], 0.0037, 0.175, 'x', 6, 0);
        this.newOb('ph_pencils', this.mesh(mb.mesh('ph_pencils', ['steel_dark'])), coll, [0, 0, 0], 0, par);
        mb = new MB();
        mb.span([-0.02, -0.17, 0], [0.13, 0.04, 0.012], 0);
        this.newOb('ph_notebook', this.mesh(mb.mesh('ph_notebook', ['steel_dark'])), coll, [0, 0, 0], 0, par);
        for (const [nm, loc] of [['place_clipboard', [-0.165, -0.025, 0.006]], ['place_notebook', [0.055, -0.065, 0.0]],
            ['place_cards', [0.2125, 0.074, 0.0]], ['place_pencils', [0.05, 0.204, 0.0]]]) this.empty(nm, loc, coll, 0, par);
        return par;
    }

    // ------------------------------------------------------------------------------------------------ the crane
    // the crane's moving parts as shared meshes: a double-girder bridge, a trolley that is an open frame (a camera
    // above looks through it), four belts, a ring that comes down round a hood, four pads that grip its sides
    gantryMeshes() {
        if (this._gm) return this._gm;
        const G = this.G;
        const [x0, x1] = G.rail_x, dy = G.girder_dy, gw = G.girder_w, [z0, z1] = G.girder_z, zt = G.rail_top;
        const WTS = ['machine_white', 'machine_teal', 'steel_galv'];
        let mb = new MB();
        for (const s of [-1, 1]) {
            mb.span([x0 - 0.22, s * dy - gw / 2, z0], [x1 + 0.22, s * dy + gw / 2, z1], 0);
            mb.span([x0 - 0.22, s * dy - 0.02, z1], [x1 + 0.22, s * dy + 0.02, z1 + 0.02], 2);
        }
        for (const rx of [x0, x1]) {
            mb.span([rx - 0.12, -0.92, zt + 0.03], [rx + 0.12, 0.92, zt + 0.22], 1);
            for (const wy of [-0.78, 0.78]) mb.cyl([rx, wy, zt + 0.03 + 0.075], 0.075, 0.26, 'x', 14, 2);
        }
        mb.cyl([x0 - 0.20, 0.45, zt + 0.14], 0.07, 0.22, 'x', 14, 2);
        this.mesh(mb.mesh('crane_bridge', WTS));
        mb = new MB();
        const ty = dy + 0.14, tx = 0.62, tw = 0.12;
        for (const s of [-1, 1]) {
            mb.span([-tx, s * ty - tw / 2 * s - tw / 2, z1 + 0.02], [tx, s * ty - tw / 2 * s + tw / 2, z1 + 0.14], 0);
            mb.span([s * tx - tw / 2 * s - tw / 2, -ty, z1 + 0.02], [s * tx - tw / 2 * s + tw / 2, ty, z1 + 0.14], 0);
        }
        for (const sx of [-1, 1]) for (const sy of [-1, 1]) mb.cyl([sx * 0.52, sy * 0.52, z1 + 0.20], 0.06, 0.10, 'x', 14, 2);
        mb.span([tx + 0.02, -0.26, z1 + 0.04], [tx + 0.22, 0.26, z1 + 0.30], 1);
        this.mesh(mb.mesh('crane_trolley', WTS));
        mb = new MB();
        mb.span([-0.025, -0.003, -1.0], [0.025, 0.003, 0.0], 0);
        this.mesh(mb.mesh('crane_belt', ['steel_dark']));
        const ro = G.ring_half_out, ri = G.ring_half_in;
        mb = new MB();
        for (const s of [-1, 1]) {
            mb.span([-ro, s * (ro + ri) / 2 - (ro - ri) / 2, -0.04], [ro, s * (ro + ri) / 2 + (ro - ri) / 2, 0.04], 0);
            mb.span([s * (ro + ri) / 2 - (ro - ri) / 2, -ri, -0.04], [s * (ro + ri) / 2 + (ro - ri) / 2, ri, 0.04], 0);
        }
        for (const sx of [-1, 1]) for (const sy of [-1, 1]) mb.span([sx * 0.52 - 0.035, sy * 0.52 - 0.035, 0.04], [sx * 0.52 + 0.035, sy * 0.52 + 0.035, 0.08], 2);
        for (let a = 0; a < 4; a++) {                                  // the pads' hangers
            const ca = Math.cos(a * PI / 2), sa = Math.sin(a * PI / 2), r = (ro + ri) / 2;
            mb.box([r * ca, r * sa, -0.105], a % 2 === 0 ? [0.06, 0.20, 0.13] : [0.20, 0.06, 0.13], 1);
        }
        this.mesh(mb.mesh('crane_ring', WTS));
        mb = new MB();
        mb.span([0.0, -0.12, -0.05], [0.02, 0.12, 0.05], 0);
        mb.cyl([0.065, 0, 0], 0.014, 0.09, 'x', 10, 1);
        this.mesh(mb.mesh('crane_pad', ['rubber_black', 'steel_galv']));
        return (this._gm = true);
    }

    // the moving parts as objects: bridge (moves along y) > trolley (x) > ring (z) > pads; belts hang from the trolley
    makeGantry(prefix, coll, parent = null) {
        this.gantryMeshes();
        const G = this.G, z1 = G.girder_z[1];
        const bridge = this.newOb(prefix + 'bridge', 'crane_bridge', coll, [0, G.park_y, 0], 0, parent);
        const trolley = this.newOb(prefix + 'trolley', 'crane_trolley', coll, [G.trolley_x[0], 0, 0], 0, bridge);
        const ring = this.newOb(prefix + 'ring', 'crane_ring', coll, [0, 0, this.Z_TOP], 0, trolley);
        const pads = [0, 1, 2, 3].map((a) => this.newOb(`${prefix}pad_${a}`, 'crane_pad', coll, [0, 0, -0.105], a * PI / 2, ring));
        const belts = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([sx, sy], i) => this.newOb(`${prefix}belt_${i}`, 'crane_belt', coll, [sx * 0.52, sy * 0.52, z1 + 0.14], 0, trolley));
        const socket = this.empty(prefix + 'hood_socket', [0, 0, -this.RING_TO_ORIGIN], coll, this.YAW, ring);
        socket.props.note = 'a hood set held by the ring has its origin here';
        return { bridge, trolley, ring, pads, belts, socket };
    }

    // THE CRANE'S ONE PROPERTY, run (q): cycle J = min(floor(q), jmax) works on unit unitOf(J, q); f = q - J is the move.
    // hoods: [[hood node, cycle k, slot node]]: on its tray until k + hood_rides[0], on the ring until k + hood_rides[1],
    // then in its slot. offs: the hero's along_offset and hoist_offset (m) added on top. Every line below is one of the
    // Blender edition's drivers (rig_gantry), its lookup curves the same keys
    rigGantry(Gp, qOf, jmax, unitOf, hoods, offs = false) {
        const G = this.G, ST = this.ST, C = G.cycle, lv = ST.levels;
        const curves = {
            ta: [...ramp(...C.travel_a), [1.0, 1.0]],
            tb: [[0.0, 0.0], ...ramp(...C.travel_b), [1.0, 1.0]],
            da: [[0.0, 0.0], ...ramp(...C.lower_a), ...ramp(...C.raise_a, 1.0, 0.0), [1.0, 0.0]],
            db: [[0.0, 0.0], ...ramp(...C.lower_b), ...ramp(...C.raise_b, 1.0, 0.0)],
            gr: [[0.0, 0.0], ...ramp(...C.grip), ...ramp(...C.release, 1.0, 0.0), [1.0, 0.0]],
        };
        const zs0 = ST.base_h - this.SEAM + this.RING_TO_ORIGIN, Z_TOP = this.Z_TOP, Z_TRAY = this.Z_TRAY, HOOD_H = this.HOOD_H, PITCH = this.PITCH;
        const half = this.L.carton.size[0] / 2 + 0.001, z1 = G.girder_z[1];
        const calc = {};
        const S = this.S;
        // the calc empty's properties
        S.drive(Gp.bridge, (st) => {
            const q = qOf(st);
            const J = Math.min(Math.floor(q), jmax);
            const F = Math.min(q - J, 1);
            calc.yu = PITCH * unitOf(J, q);
            calc.ys = ST.y0 - ST.col_pitch * Math.floor(J / lv);
            calc.yp = q < 1 ? G.park_y : ST.y0 - ST.col_pitch * Math.floor((J - 1) / lv);
            calc.zs = zs0 + HOOD_H * (J - lv * Math.floor(J / lv));
            for (const k of Object.keys(curves)) calc[k] = lookup(curves[k], F);
            calc.q = q;
            calc.ao = offs ? (st.along_offset || 0) : 0;
            calc.ho = offs ? (st.hoist_offset || 0) : 0;
            calc.z = Z_TOP - (Z_TOP - Z_TRAY) * calc.da - (Z_TOP - calc.zs) * calc.db + calc.ho;
            Gp.bridge.loc[1] = calc.yp + (calc.yu - calc.yp) * calc.ta + (calc.ys - calc.yu) * calc.tb + calc.ao;
        });
        S.drive(Gp.trolley, () => { Gp.trolley.loc[0] = ST.x * (1 - calc.ta + calc.tb); });
        S.drive(Gp.ring, () => { Gp.ring.loc[2] = calc.z; });
        Gp.pads.forEach((p, a) => {
            const sgn = a < 2 ? 1 : -1;
            S.drive(p, () => { p.loc[a % 2] = sgn * (half + G.pad_stroke * (1 - calc.gr)); });
        });
        for (const b of Gp.belts) S.drive(b, () => { b.scale[2] = (z1 + 0.14 - 0.08) - calc.z; });
        const [a0, a1] = C.hood_rides;
        for (const [hood, k, slot] of hoods) {
            hood.copy = () => (calc.q >= k + a1 ? slot : (calc.q >= k + a0 && calc.q < k + a1 ? Gp.socket : null));
        }
        return calc;
    }

    // ------------------------------------------------------------------------------------------------ 3. the controls
    controlEmpties() {
        const { G, L, LN } = this;
        const CM = this.C.machinery;
        const g = this.empty('gantry_ctl', [G.rail_x[1] + 0.3, -1.6, 2.2], CM);
        const t = this.empty('track_ctl', [L.main_track.x, -1.6, 2.2], CM);
        const c = this.empty('crowd_ctl', [this.LANES[this.LANES.length - 1], -1.6, 2.2], CM);
        this.CROWD_MAX = 9.0 + (L.crowd.variants - 1) * L.crowd.phase_step;
        Object.assign(this.controls, { gantry_ctl: g, track_ctl: t, crowd_ctl: c });
        this.report.crowd_run_max = this.CROWD_MAX;
        this.CROWD = [];
        const NV = L.crowd.variants;
        for (let v = 0; v < NV; v++) {
            const col = this.S.coll(`crowd_moving_${v}`, 'assets');
            const ctl = this.empty(`cm${v}_run`, [0, 0, 0], col);
            const qOf = (st) => clamp((st.crowd_run ?? this.CROWD_MAX) - v * L.crowd.phase_step, 0, 9);
            this.empty(`cm${v}_calc`, [0, 0, 0], col);
            const Gp = this.makeGantry(`cm${v}_`, col);
            this.inst(`cm${v}_hood_0`, this.CT.hood, [0, 0, 0], col, this.YAW);          // unit_0 stays closed
            const hoods = [];
            for (let K = 1; K < LN.units; K++) {
                const h = this.inst(`cm${v}_hood_${K}`, this.CT.hood, [0, K * this.PITCH, 0], col, this.YAW);
                const s = this.empty(`cm${v}_slot_${K - 1}`, this.slotXYZ(K - 1), col, this.YAW);
                hoods.push([h, K - 1, s]);
            }
            ctl.props.run = qOf;
            this.rigGantry(Gp, qOf, 8, (J) => J + 1, hoods);
            this.CROWD.push(col);
        }
    }

    // ------------------------------------------------------------------------------------------------ 4. the shell
    // [nn, lane, row, X0, Y0] for every line: the hero aisle (lane 0) holds the hero line alone
    linesPlan() {
        this.LINES = [];
        this.LANES.forEach((X0, lane) => {
            for (let row = 0; row < (lane === 0 ? 1 : this.ROWS); row++) this.LINES.push([this.LINES.length, lane, row, X0, -row * this.L.hall.row_pitch]);
        });
        const MT = this.L.main_track;
        this.MX = MT.x; this.MHW = MT.half_width;
        this.MY0 = Math.max(MT.y0, this.HY0 + 4.0);
    }

    shell() {
        const { L } = this, H = L.hall, CS = this.C.hall_shell, T = this.LN.track;
        const { HX0, HX1, HY0, HY1, MX, MHW, MY0 } = this;
        const holes = this.LINES.map(([, , , X0, Y0]) => [X0 - T.half_width, X0 + T.half_width, Y0 + T.y0, Y0 + T.y1]);
        for (const [, lane, , , Y0] of this.LINES) if (lane === 0) holes.push([MX + MHW, -T.half_width, Y0 - T.half_width, Y0 + T.half_width]);
        holes.push([MX - MHW, MX + MHW, MY0, HY1 + 1.0]);
        holes.push([-T.half_width, T.half_width, MY0, T.y0]);          // the inbound track
        this.newOb('hall_floor', this.mesh(floorWithHoles('hall_floor', HX0, HX1, HY0, HY1, holes, 'hall_concrete')), CS);
        const D = L.dock, wt = H.wall_t, rz = H.roof_z;
        let mb = new MB();
        mb.span([HX1, HY0 - wt, 0], [HX1 + wt, HY1 + wt, rz]);
        mb.span([HX0 - wt, HY0 - wt, 0], [HX0, HY1 + wt, rz]);
        mb.span([HX0, HY0 - wt, 0], [HX1, HY0, rz]);
        mb.span([HX0, HY1, 0], [D.door_x[0], HY1 + wt, rz]);
        mb.span([D.door_x[1], HY1, 0], [HX1, HY1 + wt, rz]);
        mb.span([D.door_x[0], HY1, D.door_h], [D.door_x[1], HY1 + wt, rz]);
        this.newOb('hall_walls', this.mesh(mb.mesh('hall_walls', ['hall_wall_panel'])), CS);
        mb = new MB();
        mb.span([HX0 - wt, HY0 - wt, rz], [HX1 + wt, HY1 + wt, rz + 0.25]);
        for (let k = 0; k <= Math.floor((HY1 - HY0) / 12); k++) {
            const y = HY1 - 6.0 - 12.0 * k;
            if (y > HY0) mb.span([HX0, y - 0.12, rz - 0.5], [HX1, y + 0.12, rz]);
        }
        this.newOb('hall_roof', this.mesh(mb.mesh('hall_roof', ['hall_roof'])), CS);
        mb = new MB();
        const lz = H.lights_z, ll = H.light_len, lp = H.light_pitch;
        for (const x of H.light_rows_x) {
            if (x < HX0 || (this.small && x < this.LANES[this.LANES.length - 1] - 4)) continue;
            let y = HY1 - 1.0 - ll / 2;
            while (y - ll / 2 > HY0) {
                mb.span([x - 0.07, y - ll / 2, lz], [x + 0.07, y + ll / 2, lz + 0.07], 0);
                mb.span([x - 0.055, y - ll / 2 + 0.03, lz - 0.012], [x + 0.055, y + ll / 2 - 0.03, lz], 1);
                mb.span([x - 0.01, y - 0.01, lz + 0.07], [x + 0.01, y + 0.01, rz - 0.25], 0);
                y -= lp;
            }
        }
        this.newOb('strip_lights', this.mesh(mb.mesh('strip_lights', ['machine_white', 'strip_light_glow'])), CS);
        const OW = L.office_window, ox = OW.wall_x;
        mb = new MB();
        mb.span([ox - 0.10, OW.y[0] - 0.12, OW.z[0] - 0.12], [ox, OW.y[1] + 0.12, OW.z[0]], 0);
        mb.span([ox - 0.10, OW.y[0] - 0.12, OW.z[1]], [ox, OW.y[1] + 0.12, OW.z[1] + 0.12], 0);
        for (let i = 0; i < 5; i++) {
            const y = OW.y[0] + (OW.y[1] - OW.y[0]) * i / 4;
            mb.span([ox - 0.10, y - 0.05, OW.z[0]], [ox, y + 0.05, OW.z[1]], 0);
        }
        mb.span([ox - 0.05, OW.y[0], OW.z[0]], [ox - 0.03, OW.y[1], OW.z[1]], 1);
        this.newOb('office_window', this.mesh(mb.mesh('office_window', ['machine_white', 'office_frosted_glow'])), CS);
    }

    // ------------------------------------------------------------------------------------------------ 5. racks and stock
    racks() {
        const RK = this.L.racks, { HX0, HY0 } = this;
        const count = { near: 0, far: 0 };
        const fm = new MB();
        this.STOCK = [];
        for (const row of RK.rows) {
            const yLo = Math.max(row.y[0], HY0 + 1.0), yHi = row.y[1];
            if (row.face_x < HX0) continue;
            const sgn = row.faces === '+x' ? 1 : -1;
            const fx = row.face_x, bx = fx - sgn * RK.depth, bay = RK.bay;
            const m0 = Math.ceil((yLo + 0.6) / bay), m1 = Math.floor((yHi + 0.6) / bay);
            for (let m = m0; m <= m1; m++) {
                const y = -0.6 + bay * m;
                for (const x of [fx - sgn * 0.045, bx + sgn * 0.045]) fm.span([x - 0.045, y - 0.035, 0], [x + 0.045, y + 0.035, RK.post_h], 0);
                for (const z of [0.35, 1.3, 2.9, 4.5]) fm.span([Math.min(fx, bx) + 0.09, y - 0.02, z - 0.02], [Math.max(fx, bx) - 0.09, y + 0.02, z + 0.02], 0);
                if (m < m1) for (const zt of RK.levels_z) for (const x of [fx - sgn * 0.03, bx + sgn * 0.03]) fm.span([x - 0.025, y + 0.035, zt - 0.10], [x + 0.025, y + bay - 0.035, zt], 1);
            }
            const near = [], far = [];
            const ya = -0.6 + bay * m0, yb = -0.6 + bay * m1;
            const n0 = Math.ceil((ya + 0.3) / RK.stock_pitch), n1 = Math.floor((yb - 0.3) / RK.stock_pitch);
            const aisle = row.name === 'r1_east' || row.name === 'east_wall';
            for (let n = n0; n <= n1; n++) {
                const y = n * RK.stock_pitch;
                for (const zt of RK.levels_z) ((aisle && RK.near_y[0] <= y && y <= RK.near_y[1]) ? near : far).push([fx - sgn * RK.depth / 2, y, zt]);
            }
            for (const [pts, key] of [[near, 'near'], [far, 'far']]) {
                if (!pts.length) continue;
                const o = this.points(`stock_${row.name}_${key}`, pts, { coll: this.CT.closed }, this.C.boxes_stock, sgn > 0 ? this.YAW : -this.YAW);
                o.props.note = 'each point is a closed carton';
                count[key] += pts.length;
                this.STOCK.push(o);
            }
        }
        this.newOb('rack_frames', this.mesh(fm.mesh('rack_frames', ['rack_upright', 'rack_beam'])), this.C.racks);
        this.report.stock_cartons = count;
        this.say('stock cartons on the racks:', JSON.stringify(count));
    }

    // ------------------------------------------------------------------------------------------------ 6. the lines
    lines() {
        const { LN, L } = this, CL = this.C.lines, LE = LN.lectern, NV = L.crowd.variants;
        if (this.LINES.length > 100) throw new Error('more than 100 lines: line_NN would need three digits');
        this.HERO_ROOT = null;
        for (const [nn, lane, row, X0, Y0] of this.LINES) {
            const hero = nn === 0, tag = `line_${String(nn).padStart(2, '0')}`;
            const root = this.empty(tag, [X0, Y0, 0], CL);
            Object.assign(root.props, { lane, row, hero: hero ? 1 : 0, crowd_copy: hero ? -1 : row % NV, delay: hero ? 0.0 : (row % NV) * L.crowd.phase_step });
            this.inst(tag + '_module', this.C.line_module, [0, 0, 0], CL, 0, root);
            for (let K = 0; K < LN.units; K++) this.empty(`${tag}_unit_${K}`, [0, K * this.PITCH, 0], CL, this.YAW, root);
            const lead = this.empty(tag + '_lead', [LE.x, LE.y - LE.stand_back, 0], CL, PI, root);
            lead.props.note = 'the station\'s mark at the lectern; local -Y is the way a body there faces (down the line)';
            if (hero) {
                this.HERO_ROOT = root;
                this.inst(tag + '_trays', this.C_TRAYS_HERO, [0, 0, 0], CL, 0, root);
                this.inst(tag + '_props_placeholders', this.C_PROPS, [0, 0, 0], CL, 0, root);
            } else {
                this.inst(tag + '_trays', this.C_TRAYS, [0, 0, 0], CL, 0, root);
                this.inst(tag + '_dressing', this.C_DRESS, [0, 0, 0], CL, 0, root);
                this.inst(tag + '_moving', this.CROWD[row % NV], [0, 0, 0], CL, 0, root);
            }
        }
        this.report.lines = { lines: this.LINES.length, lanes: this.LANES.length, rows: this.ROWS, units: this.LINES.length * LN.units };
    }

    // ------------------------------------------------------------------------------------------------ 7. the hero line
    hero() {
        const { L, LN, G } = this, MT = L.main_track;
        const CH = this.C.line_hero, CM = this.C.machinery, HR = this.HERO_ROOT, HTAG = HR.name, MX = this.MX;
        const S = this.S;
        const trayA = this.inst(HTAG + '_tray_a', this.CT.tray, [0, 0, 0], CH, this.YAW, HR);
        trayA.props.note = 'the first carton at unit_0: swap rolls it away';
        S.drive(trayA, (st) => {
            const q = st.swap ?? 1.0;
            trayA.loc[0] = MX * clamp(q / 0.3, 0, 1) + (MT.x_end - MX) * clamp((q - 0.9) / 0.1, 0, 1);
            trayA.loc[1] = MT.y_turn * clamp((q - 0.3) / 0.6, 0, 1);
        });
        const trayB = this.inst(HTAG + '_tray_b', this.CT.tray, [0, 0, 0], CH, this.YAW, HR);
        trayB.props.note = 'the fresh carton that swap rolls in to unit_0 along the inbound track';
        S.drive(trayB, (st) => {
            const q = st.swap ?? 1.0, b = MT.swap.b_start_y;
            trayB.loc[1] = b - b * clamp((q - 0.25) / 0.75, 0, 1);
        });
        for (const [nm, par] of [['_unit_0a', trayA], ['_unit_0b', trayB]]) {
            const e = this.empty(HTAG + nm, [0, 0, 0], CH, 0, par);
            e.props.note = 'the tray frame of this carton as it rolls (a body in it rides here)';
        }
        const slots = [];
        for (let j = 0; j < this.N_SLOTS; j++) slots.push(this.empty(`${HTAG}_stack_slot_${j}`, this.slotXYZ(j), CH, this.YAW, HR));
        const hoods = [];
        for (let K = 0; K < LN.units; K++) {
            const par = K === 0 ? trayA : S.get(`${HTAG}_unit_${K}`);
            hoods.push([this.inst(`${HTAG}_hood_${K}`, this.CT.hood, [0, 0, 0], CH, 0, par), K, slots[K]]);
        }
        hoods.push([this.inst(HTAG + '_hood_0b', this.CT.hood, [0, 0, 0], CH, 0, trayB), 10, slots[10]]);
        this.empty('gantry_calc', [G.rail_x[1] + 0.3, -1.6, 2.0], CM);
        this.HG = this.makeGantry('gantry_', CM, HR);
        this.HG.calc = this.rigGantry(this.HG, (st) => st.run ?? 10.0, 10, (J, q) => (q < 10 ? J : 0), hoods, true);
        const [pbody, pbutton] = this.pendant(CM, HR, 'gantry_pendant');
        S.drive(pbutton, (st) => { pbutton.loc[1] = -0.0275 + G.pendant.button_travel * (st.press ?? 0.0); });
        const e = this.empty('gantry_pendant_button_face', [0, -0.012, 0], CM, 0, pbutton);
        e.props.note = 'the centre of the button\'s face (a thumb presses it along +Y)';
        this.controls.gantry_pendant = pbody;
        const CT = L.carton;
        for (let K = 0; K < LN.units; K++) {                          // tray (x, y) -> the line's (-y, x)
            const m = this.empty(`${HTAG}_mark_${K}`, [-CT.body_mark[1], K * this.PITCH + CT.body_mark[0], CT.body_mark[2]], this.C.marks, this.YAW, HR);
            m.props.note = `where a body stands in unit ${K}'s tray (the carton's body_mark); local -Y is the way it faces`;
        }
    }

    // ------------------------------------------------------------------------------------------------ 8. the main track
    mainTrack() {
        const { L, LN } = this, MT = L.main_track, T = LN.track, { MX, MHW, MY0 } = this, CM = this.C.machinery;
        let mb = new MB();
        track_mesh(mb, T, MX - MHW, MX + MHW, MY0, MT.y_turn + MHW, 'y');
        track_mesh(mb, T, MT.x_end - 0.6, MX - MHW, MT.y_turn - MHW, MT.y_turn + MHW, 'x');
        for (const [, lane, , , Y0] of this.LINES) if (lane === 0) track_mesh(mb, T, MX + MHW, -T.half_width, Y0 - T.half_width, Y0 + T.half_width, 'x');
        this.newOb('main_track', this.mesh(mb.mesh('main_track', ['steel_galv', 'steel_dark'])), CM);
        mb = new MB();
        track_mesh(mb, T, -T.half_width, T.half_width, MY0, T.y0, 'y');
        this.newOb('inbound_track', this.mesh(mb.mesh('inbound_track', ['steel_galv', 'steel_dark'])), CM);
        const CSt = this.S.coll('boxes_stream', CM);
        const SPI = MT.stream.pitch, SPH = MT.stream.phase ?? 0.0;
        const legY = MT.y_turn - MY0, pathLen = legY + (MX - MT.x_end);
        const nStream = Math.ceil(pathLen / SPI), loop = nStream * SPI;
        this.STREAM = [];
        for (let i = 0; i < nStream; i++) {
            const b = this.inst(`stream_box_${String(i).padStart(2, '0')}`, this.CT.closed, [MX, MY0, 0], CSt, this.YAW);
            const c = i * SPI + SPH;
            this.S.drive(b, (st) => {
                const q = st.travel ?? 0.0;
                const w = q + c - loop * Math.floor((q + c) / loop);
                b.loc[1] = MY0 + Math.min(w, legY);
                b.loc[0] = MX - Math.max(0, w - legY);
            });
            this.STREAM.push(b);
        }
        this.report.stream = { cartons: nStream, pitch: SPI, phase: SPH, loop_m: Math.round(loop * 1000) / 1000, y_start: MY0 };
    }

    // ------------------------------------------------------------------------------------------------ 9. the meter
    meter() {
        const { L } = this, MC = L.meter_cabinet, CC = this.C.meter_cabinet;
        const [cx0, cx1] = MC.x, [cy0, cy1] = MC.y, cxm = (cx0 + cx1) / 2;
        const wz = MC.window_z, [ww, wh] = MC.window;
        let mb = new MB();
        mb.span([cx0 - 0.03, cy0 - 0.03, 0], [cx1 + 0.03, cy1 + 0.03, MC.plinth], 1);
        const zt = MC.plinth + MC.h, t = 0.02;
        mb.span([cx0, cy0, MC.plinth], [cx1, cy0 + t, zt], 0);
        mb.span([cx0, cy0, MC.plinth], [cx0 + t, cy1, zt], 0);
        mb.span([cx1 - t, cy0, MC.plinth], [cx1, cy1, zt], 0);
        mb.span([cx0, cy0, zt - t], [cx1, cy1, zt], 0);
        mb.span([cx0, cy0, MC.plinth], [cx1, cy1, MC.plinth + t], 0);
        const dy = cy1;
        mb.span([cx0 + 0.015, dy, MC.plinth + 0.015], [cx1 - 0.015, dy + 0.018, wz - wh / 2], 0);
        mb.span([cx0 + 0.015, dy, wz + wh / 2], [cx1 - 0.015, dy + 0.018, zt - 0.015], 0);
        mb.span([cx0 + 0.015, dy, wz - wh / 2], [cxm - ww / 2, dy + 0.018, wz + wh / 2], 0);
        mb.span([cxm + ww / 2, dy, wz - wh / 2], [cx1 - 0.015, dy + 0.018, wz + wh / 2], 0);
        this.newOb('meter_cabinet', this.mesh(mb.mesh('meter_cabinet', ['cabinet_grey', 'steel_galv', 'steel_dark'])), CC);
        mb = new MB();
        mb.quad([[cxm - ww / 2, dy + 0.004, wz - wh / 2], [cxm + ww / 2, dy + 0.004, wz - wh / 2], [cxm + ww / 2, dy + 0.004, wz + wh / 2], [cxm - ww / 2, dy + 0.004, wz + wh / 2]]);
        const glass = this.newOb('meter_window_glass', this.mesh(mb.mesh('meter_window_glass', ['glass_placeholder'], false)), CC);
        glass.hidden = true;                                           // (the look glazes it)
        const e = this.empty('meter_label_place', [cxm, dy + 0.0205, wz + 0.105], CC);
        e.rot = [PI / 2, 0, PI];
        e.props.note = 'a label plate 0.26 x 0.07 m on the door; local +Z out of the door, +Y up';
        this.controls.meter_cabinet_ctl = this.empty('meter_cabinet_ctl', [cxm, cy1 + 0.4, 2.3], CC);
        const R = MC.drum_d / 2, DW = MC.drum_w;
        this.DRUMS = [];
        for (let k = 0; k < MC.digits; k++) {
            mb = new MB();
            mb.cyl([0, 0, 0], R, DW - 0.004, 'x', 40, 0);
            for (const s of [-1, 1]) mb.cyl([s * (DW / 2 - 0.0015), 0, 0], R + 0.003, 0.003, 'x', 40, 1);
            const md = mb.mesh(`meter_drum_${k}`, ['drum_white', 'drum_ink']);
            md.digits = { R, size: 0.36 * MC.drum_d };                   // the glyphs are laid on in hall.js (a font needs three)
            const x = cxm - (MC.digits / 2 - 0.5 - k) * (DW + 0.006);   // k 0 = the units' drum, on the reader's right (-X)
            const drum = this.newOb(`meter_drum_${k}`, this.mesh(md), CC, [x, dy - R - 0.012, wz]);
            const p10 = 10 ** k;
            this.S.drive(drum, (st) => {
                const q = st.meter ?? MC.default;
                const ex = k === 0 ? q : Math.floor(q / p10) + clamp(q - p10 * Math.floor(q / p10) - (p10 - 1), 0, 1);
                drum.rot[0] = 0.6283185 * ex;
            });
            this.DRUMS.push(drum);
        }
        mb = new MB();
        mb.span([cxm - ww / 2 - 0.03, dy - 2 * R - 0.03, wz - R - 0.02], [cxm + ww / 2 + 0.03, dy - 2 * R - 0.025, wz + R + 0.02], 0);
        this.newOb('meter_drum_housing', this.mesh(mb.mesh('meter_drum_housing', ['steel_dark'])), CC);
        this.cab = [cxm, cy1, wz];
    }

    // ------------------------------------------------------------------------------------------------ 10. the cage
    cage() {
        const RC = this.L.returns_cage, CG = this.C.returns_cage;
        const [gx0, gx1] = RC.x, [gy0, gy1] = RC.y, gh = RC.h;
        const corners = [[gx0, gy0], [gx1, gy0], [gx1, gy1], [gx0, gy1]];
        const pm = new MB();
        for (const [px, py] of [...corners, [(gx0 + gx1) / 2, gy0], [gx0, gy0 + 1.6], [gx0, gy0 + 3.0]]) pm.cyl([px, py, gh / 2], 0.03, gh, 'z', 10, 0);
        for (const [a, b] of [[corners[0], corners[1]], [corners[0], corners[3]]]) {
            const ln = Math.hypot(b[0] - a[0], b[1] - a[1]);
            pm.cyl([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, gh], 0.022, ln, Math.abs(b[0] - a[0]) > 0.1 ? 'x' : 'y', 8, 0);
        }
        for (const z of [0.05, gh]) pm.box([gx0 + 0.9, gy0 + 2.085, z], [0.03, 1.6, 0.03], 0, Math.atan2(0.93, 1.3) - PI / 2);
        this.newOb('cage_posts', this.mesh(pm.mesh('cage_posts', ['steel_galv'])), CG);
        const mb = new MB();
        for (const [a, b] of [[corners[0], corners[1]], [corners[0], [gx0, gy0 + 1.6]], [[gx0, gy0 + 3.0], corners[3]], [[gx0 + 0.25, gy0 + 1.62], [gx0 + 1.55, gy0 + 2.55]]]) {
            mb.quad([[a[0], a[1], 0.05], [b[0], b[1], 0.05], [b[0], b[1], gh], [a[0], a[1], gh]]);
        }
        this.newOb('cage_chain_link', this.mesh(mb.mesh('cage_chain_link', ['steel_galv'], false)), CG);
        let cr = 0;
        for (let i = 0; i < 3; i++) {
            for (let j = 0; j < 2; j++) {
                const x = gx0 + 0.75 + 1.0 * i, y = gy1 - 0.65 - 1.05 * j;
                for (let lvl = 0; lvl < 2; lvl++) {
                    if (cr >= RC.cartons || (lvl === 1 && j === 1)) continue;
                    const yaw = -PI / 2 + RAD([7, -4, 3, -9, 5, -2, 8, -6, 2][cr % 9]);
                    this.inst(`cage_carton_${cr}`, this.CT.closed, [x, y, this.L.carton.size[2] * lvl], CG, yaw);
                    cr++;
                }
            }
        }
        this.report.returns_cage = { cartons: cr };
    }

    // ------------------------------------------------------------------------------------------------ 11. the dock
    dock() {
        const { L } = this, H = L.hall, D = L.dock, MT = L.main_track, CD = this.C.dock;
        const { HY1, MX, MHW } = this, wt = H.wall_t;
        const [dx0, dx1] = D.door_x, dh = D.door_h;
        let mb = new MB();
        for (const x of [dx0 - 0.12, dx1 + 0.12]) mb.span([x - 0.12, HY1 - 0.06, 0], [x + 0.12, HY1 + wt + 0.06, dh + 0.25], 0);
        mb.span([dx0 - 0.24, HY1 - 0.06, dh], [dx1 + 0.24, HY1 + wt + 0.06, dh + 0.25], 0);
        mb.cyl([(dx0 + dx1) / 2, HY1 - 0.32, dh + 0.42], 0.26, dx1 - dx0 + 0.3, 'x', 20, 1);
        mb.span([dx0 - 0.2, HY1 - 0.62, dh + 0.12], [dx1 + 0.2, HY1 - 0.02, dh + 0.18], 1);
        for (const x of [dx0 - 0.5, dx1 + 0.5]) mb.cyl([x, HY1 - 1.2, 0.55], 0.085, 1.1, 'z', 14, 2);
        this.newOb('dock_door', this.mesh(mb.mesh('dock_door', ['steel_galv', 'machine_white', 'machine_teal'])), CD);
        const yo = HY1 + wt;
        const outHoles = [[MX - MHW, MX + MHW, yo - 1.0, MT.y_turn + MHW], [MT.x_end - 0.6, MX - MHW, MT.y_turn - MHW, MT.y_turn + MHW]];
        this.newOb('dock_apron', this.mesh(floorWithHoles('dock_apron', -90.0, 60.0, yo, 220.0, outHoles, 'dock_apron')), CD);
        mb = new MB();
        mb.span([dx0, HY1, -0.02], [MX - MHW, yo, 0.0], 0);
        mb.span([MX + MHW, HY1, -0.02], [dx1, yo, 0.0], 0);
        this.newOb('dock_threshold', this.mesh(mb.mesh('dock_threshold', ['steel_galv'])), CD);
    }

    // ------------------------------------------------------------------------------------------------ 12. the cameras
    cameras() {
        const CAM = this.L.cameras, rim = this.L.carton.rim_z;
        const cams = {};
        for (const name of ['cam_top_unit0', 'cam_top_unit1']) {
            const c = CAM[name];
            const px = -c.centre[1], py = c.unit * this.PITCH + c.centre[0];        // the tray's (x, y) -> the line's (-y, x)
            cams[name] = lookAt([px, py, c.z], [px, py, 0], 36.0 * (c.z - rim) / c.frame_width_at_rim, [-1, 0, 0]);
        }
        let c = CAM.cam_line_top;
        cams.cam_line_top = lookAt(c.pos, [c.pos[0], c.pos[1], 0], 50.0, [-1, 0, 0], c.ortho);
        for (const [name, v] of Object.entries(CAM)) {
            if (cams[name] || typeof v !== 'object' || !v.pos) continue;
            cams[name] = lookAt(v.pos, v.aim, v.lens);
        }
        c = CAM.cam_drums;
        const [cxm, cy1, wz] = this.cab;
        cams.cam_drums = lookAt([cxm, cy1 + c.back, wz + 0.03], [cxm, cy1, wz + 0.03], c.lens);
        this.cams = cams;
        this.report.cameras = Object.keys(cams).sort();
    }

    // ------------------------------------------------------------------------------------------------ 13. the light
    // the dock's sun: from +Y, azimuth_off_axis round toward +X, at the elevation where the shadow of the door's head
    // falls at patch_end_y (so the sunlit patch covers unit_9's tray and stops short of unit_8's)
    light() {
        const { L } = this, H = L.hall, S = L.dock.sun;
        const az = RAD(S.azimuth_off_axis);
        const headY = this.HY1 + H.wall_t + 0.06;
        const el = Math.atan(L.dock.door_h * Math.cos(az) / (headY - S.patch_end_y));
        this.SUN_DIR = [-Math.sin(az) * Math.cos(el), -Math.cos(az) * Math.cos(el), -Math.sin(el)];   // the way it travels
        this.report.dock_sun = { elevation_deg: Math.round(el * 180 / PI * 1000) / 1000, azimuth_off_axis_deg: S.azimuth_off_axis, patch_end_y: S.patch_end_y };
    }
}
