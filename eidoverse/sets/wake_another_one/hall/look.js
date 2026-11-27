// eidoverse/sets/wake_another_one/hall/look.js — the hall's look over its layout: the geometry and light plan of the
// Blender edition's hall.look (its materials are mats.js, its lights and outdoors world.js). No three.js.
//
//   const X = look(lay, { trees: true });    // after new Layout(...).run(): rebuilds the layout's meshes in place
//
// In the Blender edition's order:
//   materials   the table of every material by name (MATERIALS: layered over CC0 scans fetched by ID, or one of the
//               special kinds: the floor, the painted lines, the wall liner, the field, the yard, emitters, glass)
//   geometry    plain boxes get bevels, a wear band, baked cavity and UVs in metres (md.fin: kit.finish runs in
//               hall.js); the racks, the roller tracks, the strip lights, the lectern, the pendant, the chain link and
//               the dock are rebuilt with real sections (shell.js, machines.js); the lectern's printer is new (printer_ctl
//               feed). Every object, its name, origin and parenting stay as the layout made them
//   light       the strip lights as continuous rows of area lights, none casting a shadow; the dock's low sun with its
//               shadow; the meter's own lamp; the air (a haze with a switch)
//   settings    the printer's camera and an 85 mm down the line; the meter cabinet 80 mm off the wall's dado
import { MB, PI, meshData } from './kit.js';
import { Node, M4 } from './graph.js';
import { srgb, RAD } from './build.js';
import * as shell from './shell.js';
import * as machines from './machines.js';

// THE COLOUR SCHEME: the machines' white and teal plus one safety colour
export const WHITE = srgb('#d9e0df');
export const TEAL = srgb('#398b91');
export const ZINC = [0.60, 0.62, 0.64];
export const GREASE = [0.022, 0.019, 0.016];
export const ENAMEL = srgb('#e5dfd2');
export const DEEP_TEAL = TEAL.map((c) => c * 0.6);
export const YELLOW = srgb('#d6a21f');
export const LINE_YELLOW = [0.60, 0.39, 0.06];
export const HAZARD_BLACK = [0.022, 0.022, 0.024];
const CHIP_W = { amount: 0.5, primer: [0.34, 0.35, 0.36], metal: [0.56, 0.57, 0.58], metal_rough: 0.34 };
// THE CAMERA IS BALANCED TO THE HALL'S LAMPS (the balance is in the lights' colours): lamps of 4500 K under a camera
// set to 4460 K read clean and slightly cool; the low sun at the dock (3000 K) warm gold beside them
export const WB_K = 4460.0, LAMP_K = 4500.0, SUN_K = 3000.0;

// an approximate linear-sRGB colour of a blackbody at k Kelvin (eidoblend.look.lighting.blackbody_rgb)
export function blackbody(k) {
    const t = k / 100.0;
    let r, g, b;
    if (t <= 66) { r = 255.0; g = 99.4708025861 * Math.log(t) - 161.1195681661; b = t <= 19 ? 0.0 : 138.5177312231 * Math.log(t - 10) - 305.0447927307; }
    else { r = 329.698727446 * ((t - 60) ** -0.1332047592); g = 288.1221695283 * ((t - 60) ** -0.0755148492); b = 255.0; }
    const lin = [r, g, b].map((v) => Math.min(255.0, Math.max(0.0, v)) / 255.0).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    const m = Math.max(...lin);
    return lin.map((c) => c / m);
}
export function balanced(k) {
    const a = blackbody(k), b = blackbody(WB_K), c = a.map((v, i) => v / b[i]), m = Math.max(...c);
    return c.map((v) => v / m);
}

// every material of the hall, by name: { kind: 'layered', scan, res, ...layered()'s options (mats.js) }, or one of the
// special kinds. post: a named hook of mats.js (fork_wear, roller_wear, tread, hand_edge, hazard, dado)
export function materials(L, lay) {
    const lay_ = (scan, o) => ({ kind: 'layered', scan, res: o.res || '2k', ...o });
    const M = {
        machine_white: lay_('Metal049A', { tile: 0.55, tint: ENAMEL, rough: 0.36, chips: CHIP_W, dirt: 0.65, dust: 0.32, scratches: 0.35, smudges: 0.3 }),
        machine_teal: lay_('Metal049A', { tile: 0.55, tint: TEAL, rough: 0.36, chips: { amount: 0.55, primer: [0.40, 0.43, 0.42], metal: [0.56, 0.57, 0.58] }, dirt: 0.65, dust: 0.35, scratches: 0.4, smudges: 0.3 }),
        steel_galv: lay_('Metal049A', { tile: 0.5, tint: ZINC, rough: 0.37, metal: 1.0, normal: 0.35, spangle: 1.0, polish: 0.6, dirt: 0.65, dust: 0.35, scratches: 0.25, smudges: 0.2, fine: 0.5 }),
        steel_dark: lay_('Metal027', { tile: 0.45, rough: 0.48, metal: 'map', normal: 0.6, polish: 0.7, dirt: 0.5, dust: 0.45, scratches: 0.35, smudges: 0.35, fine: 0.5 }),
        rubber_black: lay_('Rubber004', { tile: 0.28, tint: [0.020, 0.020, 0.021], rough: 0.74, normal: 0.8, dirt: 0.4, dirt_col: [0.10, 0.09, 0.08], dust: 0.5, scratches: 0.15, smudges: 0.4, world_var: false }),
        rack_upright: lay_('Metal049A', { tile: 0.5, tint: DEEP_TEAL, rough: 0.40, normal: 0.35, chips: { amount: 0.5, primer: [0.33, 0.34, 0.35], metal: [0.56, 0.57, 0.58] }, dirt: 0.7, dust: 0.3, scratches: 0.4, smudges: 0.15, post: 'fork_wear', post_arg: L.racks.levels_z }),
        rack_beam: lay_('Metal049A', { tile: 0.5, tint: [0.66, 0.68, 0.70], rough: 0.38, metal: 1.0, normal: 0.35, spangle: 0.8, polish: 0.5, dirt: 0.7, dust: 0.6, scratches: 0.4, smudges: 0.2 }),
        cabinet_grey: lay_('Metal049A', { tile: 0.5, tint: ENAMEL, rough: 0.42, chips: { amount: 0.16, primer: [0.42, 0.40, 0.36] }, dirt: 0.7, dust: 0.6, scratches: 0.4, smudges: 0.5 }),
        drum_white: lay_('Plastic010', { tile: 0.2, tint: [0.78, 0.775, 0.74], rough: 0.40, normal: 0.4, var: 0.4, world_var: false, dirt: 0.8, dust: 0.0, scratches: 0.25, smudges: 0.3 }),
        drum_ink: lay_('Plastic010', { tile: 0.2, tint: [0.012, 0.012, 0.013], rough: 0.5, normal: 0.3, var: 0.3, world_var: false, dirt: 0.0, dust: 0.0, scratches: 0.2, smudges: 0.2 }),
        plastic_white: lay_('Plastic010', { tile: 0.22, tint: [0.76, 0.73, 0.66], rough: 0.40, normal: 0.5, polish: 0.5, dirt: 0.7, dust: 0.45, scratches: 0.35, smudges: 0.6, fine: 0.44 }),
        plastic_teal: lay_('Plastic010', { tile: 0.22, tint: TEAL, rough: 0.42, normal: 0.5, polish: 0.9, dirt: 0.8, dust: 0.1, scratches: 0.5, smudges: 0.9, world_var: false, fine: 0.5 }),
        steel_brushed: lay_('Metal009', { tile: 0.3, rough: 0.30, metal: 1.0, normal: 0.5, polish: 0.9, dirt: 0.6, dust: 0.12, scratches: 0.5, smudges: 0.7, world_var: false, post: 'hand_edge' }),
        steel_zinc: lay_('Metal009', { tile: 0.3, tint: [0.66, 0.67, 0.68], rough: 0.27, metal: 1.0, normal: 0.25, var: 0.0, world_var: false, polish: 0.5, dirt: 0.85, dirt_col: GREASE, dust: 0.0, scratches: 0.0, smudges: 0.0, grain: 0.0, post: 'roller_wear' }),
        track_pit: lay_('Concrete034', { res: '2k', tile: 1.2, tint: [0.085, 0.083, 0.080], rough: 0.86, normal: 0.8, var: 0.0, world_var: false, dirt: 0.0, dust: 0.0, scratches: 0.0, smudges: 0.0, grain: 0.0 }),
        tread_plate: lay_('Metal049A', { tile: 0.5, tint: ZINC, rough: 0.40, metal: 1.0, normal: 0.3, spangle: 0.6, polish: 0.7, dirt: 0.8, dust: 0.5, scratches: 0.5, smudges: 0.2, post: 'tread' }),
        chain_galv: lay_('Metal049A', { tile: 0.4, tint: ZINC, rough: 0.36, metal: 1.0, normal: 0.2, spangle: 0.4, polish: 0.0, dirt: 0.0, dust: 0.0, scratches: 0.0, smudges: 0.0 }),
        yard_concrete: lay_('Concrete034', { res: '2k', tile: 2.4, rough: 0.8, normal: 1.0, dirt: 0.6, dust: 0.4, scratches: 0.0, smudges: 0.0 }),
        paper_placeholder: lay_('Paper001', { tile: 0.3, tint: [0.80, 0.78, 0.72], rough: 0.7, normal: 0.7, var: 0.4, world_var: false, dirt: 0.25, dust: 0.0, scratches: 0.0, smudges: 0.2 }),
        carton_board: lay_('Paper001', { tile: 0.45, tint: [0.70, 0.68, 0.62], rough: 0.62, normal: 0.5, var: 0.5, world_var: false, dirt: 0.4, dust: 0.35, scratches: 0.0, smudges: 0.3 }),
        carton_insert: lay_('Paper001', { tile: 0.25, tint: [0.42, 0.38, 0.31], rough: 0.85, normal: 1.0, var: 0.6, world_var: false, dirt: 0.3, dust: 0.2, scratches: 0.0, smudges: 0.0 }),
        safety_yellow: lay_('Metal049A', { tile: 0.5, tint: YELLOW, rough: 0.42, chips: { amount: 0.8, primer: [0.30, 0.30, 0.31], metal: [0.50, 0.51, 0.52] }, dirt: 0.8, dust: 0.35, scratches: 0.6, smudges: 0.3 }),
        column_paint: lay_('Metal049A', { tile: 0.5, tint: [0.56, 0.585, 0.60], rough: 0.45, chips: { amount: 0.35 }, dirt: 0.6, dust: 0.45, scratches: 0.3, smudges: 0.2 }),
        wall_concrete: lay_('Concrete034', { res: '4k', tile: 2.4, tint: [0.68, 0.68, 0.665], rough: 0.62, normal: 0.3, dirt: 0.7, dust: 0.25, scratches: 0.0, smudges: 0.3, post: 'dado' }),
        plastic_grey: lay_('Plastic010', { tile: 0.3, tint: [0.36, 0.38, 0.40], rough: 0.45, normal: 0.5, dirt: 0.6, dust: 0.4, scratches: 0.3, smudges: 0.4 }),
        belt_webbing: lay_('Rubber004', { tile: 0.06, tint: [0.035, 0.035, 0.04], rough: 0.8, normal: 1.0, var: 0.5, world_var: false, dirt: 0.3, dust: 0.0, scratches: 0.0, smudges: 0.0 }),
        plate_alu: lay_('Metal009', { tile: 0.3, tint: [0.74, 0.75, 0.76], rough: 0.36, metal: 0.5, normal: 0.4, var: 0.4, world_var: false, polish: 0.3, dirt: 0.5, dust: 0.0, scratches: 0.4, smudges: 0.5, fine: 0.5 }),
        brass: lay_('Metal009', { tile: 0.2, tint: [0.78, 0.57, 0.22], rough: 0.30, metal: 1.0, normal: 0.4, var: 0.4, world_var: false, polish: 0.6, dirt: 0.6, dust: 0.0, scratches: 0.6, smudges: 0.6, fine: 0.4 }),
        station_white: lay_('Metal049A', { tile: 0.55, tint: ENAMEL, rough: 0.36, chips: { ...CHIP_W, amount: 0.08 }, dirt: 0.6, dust: 0.3, scratches: 0.4, smudges: 0.45 }),
        curtain_white: lay_('Metal049A', { tile: 0.5, tint: [0.64, 0.66, 0.68], rough: 0.36, metal: 1.0, normal: 0.35, spangle: 0.7, polish: 0.5, dirt: 0.8, dust: 0.5, scratches: 0.5, smudges: 0.3 }),
        hazard_yellow: lay_('Metal049A', { tile: 0.5, tint: YELLOW, rough: 0.42, chips: { amount: 0.8, primer: [0.30, 0.30, 0.31], metal: [0.50, 0.51, 0.52] }, dirt: 0.8, dust: 0.35, scratches: 0.6, smudges: 0.3, post: 'hazard' }),
        cable_grey: lay_('Rubber004', { tile: 0.28, tint: [0.33, 0.34, 0.35], rough: 0.6, normal: 0.6, dirt: 0.4, dust: 0.6, scratches: 0.1, smudges: 0.3, world_var: false }),
        trailer_white: lay_('Metal049A', { tile: 0.8, tint: [0.66, 0.67, 0.68], rough: 0.40, chips: { amount: 0.3 }, dirt: 0.8, dust: 0.3, scratches: 0.4, smudges: 0.4 }),
    };
    // the floor's lanes and the racks' feet, in world metres from the layout
    const LANES = lay.LANES;
    const lanes = { fixed: [[2.95, 1.35]], cross: [[lay.HX0 + 2.0, 5.9, 18.3, 2.3]] };
    if (LANES.length > 1) lanes.periodic = [LANES[1] + 3.0, LANES.length > 2 ? Math.abs(LANES[1] - LANES[2]) : 7.8, 1.35, -7.6];
    M.hall_concrete = { kind: 'floor', racks_x: [[-6.5, -4.3, [-6.5, -4.3]], [6.2, 7.3, [6.2]], [-71.5, -70.4, [-70.4]]], lanes };
    M.floor_line_paint = { kind: 'floor_paint', colour: LINE_YELLOW };
    M.floor_hazard_paint = { kind: 'floor_paint', colour: LINE_YELLOW, stripes: 0.30 };
    M.hall_wall_panel = { kind: 'wall_liner' };
    M.hall_roof = { kind: 'wall_liner', lap_v: -1000.0, scuff: false, value: 0.66 };
    M.yard_field = { kind: 'field' };
    M.dock_apron = { kind: 'yard' };
    const LAMP = balanced(LAMP_K);
    M.strip_light_glow = { kind: 'emitter', colour: LAMP, strength: 7.0, falloff: [0, 0.029] };
    M.office_frosted_glow = { kind: 'frosted', colour: blackbody(3300.0), strength: 2.6 };
    M.glass_placeholder = { kind: 'glass' };
    M.printer_led = { kind: 'emitter', colour: [0.35, 1.0, 0.75], strength: 3.0, body: [0.2, 0.6, 0.45] };
    return M;
}

// ======================================================================================================== the look
export function look(lay, { trees = true, log = console.log } = {}) {
    const T0 = performance.now();
    const say = (...a) => log(`[look ${((performance.now() - T0) / 1000).toFixed(1).padStart(6)} s] ${a.join(' ')}`);
    const L = lay.L, S = lay.S;
    S.coll('look_assets', 'assets');
    S.coll('look_light_and_air', 'hall');
    const X = {
        lay, L, S, say, C: { ...lay.C, look_assets: 'look_assets', air: 'look_light_and_air' },
        HX0: lay.HX0, HX1: lay.HX1, HY0: lay.HY0, HY1: lay.HY1, RZ: L.hall.roof_z, WT: L.hall.wall_t,
        models: [], fence: null, trees: [], lights: [], report: { steps: [] },
        mesh: (md) => lay.mesh(md),
        // the detail pass's settings for a mesh (kit.finish runs in hall.js): bevel, inset, cavity distance, ground
        fin: (md, bevel = 0.0025, inset = 0.014, cavity = 0.10, ground = null) => { md.fin = { bevel, inset, cavity, ground }; return md; },
        replace: (md) => { lay.meshes.set(md.name, md); return md.name; },
        ob: (name, mesh, coll, loc = [0, 0, 0], rz = 0.0, parent = null) => lay.newOb(name, mesh, coll, loc, rz, parent),
        asset: (name, mesh) => lay.newOb(name, mesh, 'look_assets'),
        model: (asset, loc, rz) => X.models.push({ asset, loc, rz }),
        finishNamed: (name, o = {}) => {
            const md = lay.meshes.get(name);
            if (!md) { say(`   (no mesh named ${name}: skipped)`); return; }
            X.fin(md, o.bevel ?? 0.0025, o.inset ?? 0.014, o.cavity ?? 0.10, o.ground ?? null);
        },
    };
    const step = (w) => { say(w); X.report.steps.push(w); };
    step('1. materials: every layout material rebuilt in place, layered over a scan');
    X.M = materials(L, lay);
    step('2a. the shell: outer masses, purlins, the floor\'s lines, the walls, the roof\'s deck'); lookShell(X);
    step('2b. the racks: punched uprights, braced frames on bolted footplates, step beams on connectors, decks'); racks(X);
    step('2c. the roller tracks: turned rollers on hexagon axles in bearing caps, side frames, screwed kerbs'); tracks(X);
    step('2d. the strip lights: continuous rows of 1.5 m luminaires on hangers'); stripLights(X);
    step('2e. the station: the lectern, its printer, the pendant'); station(X);
    step('2f. the returns cage: woven chain link'); chainLink(X);
    step('2g. the dock: the door, the yard, the services');
    const door = shell.dockDoor(X);
    shell.yard(X, trees);
    shell.services(X, door);
    lay.meshes.get('dock_threshold').mats[0] = 'tread_plate';
    step('2h. the machines, the cartons and every other built mesh'); theRest(X);
    step('3. light: continuous strip rows, the dock sun, the air'); light(X);
    step('4. settings: the printer\'s camera, the 85 mm, the cabinet off the wall'); settings(X);
    X.report.seconds = +((performance.now() - T0) / 1000).toFixed(1);
    return X;
}

// ------------------------------------------------------------------------------------------------ 2a. the shell
function lookShell(X) {
    const { lay, L } = X, { HX0, HX1, HY0, HY1 } = X;
    const WT_ = L.hall.wall_t, RZ = L.hall.roof_z, D = L.dock, CS = X.C.hall_shell;
    let mb = new MB();
    const TH = 3.0;                                                    // thick masses outside the 0.3 m shell: nothing sees them
    mb.span([HX0 - TH, HY0 - TH, -TH], [HX1 + TH, HY1 + WT_, -0.14]);
    mb.span([HX0 - TH, HY0 - TH, -0.14], [HX0 - WT_, HY1 + WT_, RZ + TH]);
    mb.span([HX1 + WT_, HY0 - TH, -0.14], [HX1 + TH, HY1 + TH, RZ + TH]);
    mb.span([HX0 - WT_, HY0 - TH, -0.14], [HX1 + WT_, HY0 - WT_, RZ + TH]);
    mb.span([HX0 - WT_, HY0 - WT_, RZ + 0.25], [HX1 + WT_, HY1 + WT_, RZ + TH]);
    // behind the dock wall the hall is closed too, but for a TUNNEL in front of the door, the sun's way in
    mb.span([HX0 - TH, HY1 + WT_, -0.14], [D.door_x[0] - 2.5, HY1 + TH, RZ + TH]);
    mb.span([D.door_x[1] + 1.2, HY1 + WT_, -0.14], [HX1 + WT_, HY1 + TH, RZ + TH]);
    mb.span([D.door_x[0] - 2.5, HY1 + WT_, D.door_h + 1.3], [D.door_x[1] + 1.2, HY1 + TH, RZ + TH]);
    const mass = X.ob('hall_outer_mass', X.mesh(mb.mesh('hall_outer_mass', ['yard_concrete'])), CS);
    mass.props.note = 'thick masses outside the hall\'s shell and under its floor: they keep the sun out but for the door';
    mass.shadowOnly = true;                                            // (Blender: visible_camera False)
    mb = new MB();
    for (let x = HX1 - 1.2; x > HX0 + 0.5; x -= 2.4) {                // purlins under the deck, along the hall
        mb.prism([[-0.03, -0.20], [0.03, -0.20], [0.03, -0.185], [0.004, -0.185], [0.004, -0.012], [0.03, -0.012], [0.03, 0.0], [-0.03, 0.0]], HY0 + 0.05, HY1 - 0.05, 'y', 0, [x, RZ]);
    }
    X.ob('hall_purlins', X.mesh(X.fin(mb.mesh('hall_purlins', ['steel_galv']), 0.002, 0.01, 0.0)), CS);
    const LN = L.line, GA = L.gantry, LE = LN.lectern, MK = LN.marks;
    const segs = [MK.x_a, MK.x_b, GA.rail_x[0] - 0.25].map((x) => [[x, GA.rail_y[0]], [x, GA.rail_y[1]], MK.line_w]);
    const sx = LE.x, sy = LE.y - LE.stand_back;
    segs.push([[sx - 0.35, sy - 0.28], [sx + 0.35, sy - 0.28], 0.04], [[sx - 0.35, sy + 0.28], [sx + 0.35, sy + 0.28], 0.04],
        [[sx - 0.33, sy - 0.30], [sx - 0.33, sy + 0.30], 0.04], [[sx + 0.33, sy - 0.30], [sx + 0.33, sy + 0.30], 0.04]);
    X.replace(paintedLines('line_floor_lines', segs, 'floor_line_paint'));
    const ye = HY1 - 0.55;                                            // black-and-yellow at the dock's edge, broken where the main track runs out
    const edge = [[[D.door_x[0] + 0.05, ye], [lay.MX - lay.MHW - 0.09, ye], 0.30], [[lay.MX + lay.MHW + 0.09, ye], [D.door_x[1] - 0.05, ye], 0.30]];
    X.ob('dock_edge_hazard', X.mesh(paintedLines('dock_edge_hazard', edge, 'floor_hazard_paint')), X.C.dock);
    X.framesY = shell.walls(X);
}

// floor lines as a mesh whose UV says where the paint's edges are: segs [[(x0, y0), (x1, y1), width]]; each is two
// strips, edge to middle to edge; UV = (metres in from the nearer edge, metres along)
export function paintedLines(name, segs, material, z = 0.002) {
    const verts = [], faces = [], uvv = [];
    for (const [a, b, w] of segs) {
        const A = [a[0], a[1], z], B = [b[0], b[1], z];
        const ln = Math.hypot(B[0] - A[0], B[1] - A[1]);
        const d = [(B[0] - A[0]) / ln, (B[1] - A[1]) / ln];
        const n = [-d[1], d[0]];
        const n0 = verts.length;
        for (const [t, v] of [[A, 0.0], [B, ln]]) for (const [s, u] of [[-0.5, 0.0], [0.0, w / 2], [0.5, 0.0]]) {
            verts.push([t[0] + n[0] * s * w, t[1] + n[1] * s * w, z]);
            uvv.push([u, v]);
        }
        faces.push([n0, n0 + 3, n0 + 4, n0 + 1], [n0 + 1, n0 + 4, n0 + 5, n0 + 2]);
    }
    return meshData(name, [material], verts, faces, { uv: faces.flatMap((f) => f.flatMap((i) => uvv[i])) });
}

// ------------------------------------------------------------------------------------------------ 2b. the racks
function racks(X) {
    const { lay, L } = X, RK = L.racks;
    const DEPTH = RK.depth, BAY = RK.bay, POST_H = RK.post_h;
    const RMATS = ['rack_upright', 'rack_beam', 'steel_galv'];
    let mb = new MB();
    for (const xc of [-0.045, -DEPTH + 0.045]) {
        mb.box([xc, 0.0, 0.006 + (POST_H - 0.006) / 2], [0.09, 0.07, POST_H - 0.006], 0);
        mb.box([xc, 0.0, 0.003], [0.17, 0.125, 0.006], 2);
        for (const sx of [-0.064, 0.064]) {
            mb.bolt([xc + sx, 0.0, 0.0105], 0.011, 0.009, 'z', 2);
            mb.cyl([xc + sx, 0.0, 0.019], 0.005, 0.012, 'z', 8, 2);
        }
        mb.box([xc, 0.0, POST_H + 0.002], [0.094, 0.074, 0.004], 2);
    }
    const SPAN = DEPTH - 0.18, ZB = [0.35, 1.3, 2.9, 4.5];
    for (const z of ZB) {
        mb.box([-DEPTH / 2, -0.012, z], [SPAN, 0.022, 0.04], 2);
        for (const xc of [-0.09 - 0.012, -DEPTH + 0.09 + 0.012]) mb.bolt([xc, -0.012 - 0.015, z], 0.007, 0.006, 'y', 2, false);
    }
    for (let i = 0; i < ZB.length - 1; i++) {
        const dz = ZB[i + 1] - ZB[i] - 0.06, ln = Math.hypot(SPAN, dz);
        const ang = Math.atan2(dz, SPAN) * (i % 2 === 0 ? 1 : -1);
        mb.box([-DEPTH / 2, 0.012, (ZB[i] + ZB[i + 1]) / 2], [ln, 0.022, 0.035], 2, 0.0, 0.0, -ang);
    }
    X.asset('asset_rack_frame', X.mesh(X.fin(mb.mesh('rack_frame', RMATS), 0.002, 0.012, 0.08, 0.0)));
    mb = new MB();
    for (const zt of RK.levels_z) {
        for (const [side, xa, xb, xf] of [[1, -0.055, -0.005, 0.0], [-1, -DEPTH + 0.005, -DEPTH + 0.055, -DEPTH]]) {
            mb.span([xa, 0.037, zt - 0.10], [xb, BAY - 0.037, zt], 1);
            const xl = side > 0 ? xa - 0.014 : xb;
            mb.span([xl, 0.045, zt - 0.046], [xl + 0.014, BAY - 0.045, zt - 0.026], 1);
            const zlo = Math.max(zt - 0.195, 0.012);
            for (const [ya, yb, ys] of [[0.0015, 0.047, 0.035], [BAY - 0.047, BAY - 0.0015, BAY - 0.039]]) {
                mb.span([xf - 0.0045 * (side < 0 ? 1 : 0), ya, zlo], [xf + 0.0045 * (side > 0 ? 1 : 0), yb, zt + 0.012], 1);
                mb.span([Math.min(xa, xf), ys, zlo], [Math.max(xb, xf), ys + 0.004, zt + 0.012], 1);
                const ym = (ya + yb) / 2;
                for (const zr of [zt - 0.045, zt - 0.145]) { if (zr < zlo + 0.012) continue; mb.cyl([xf + side * 0.0065, ym, zr], 0.007, 0.004, 'x', 10, 2); }
                mb.cyl([xf + side * 0.012, ym, zt - 0.095], 0.004, 0.022, 'x', 8, 2);
                mb.cyl([xf + side * 0.022, ym, zt - 0.102], 0.0028, 0.016, 'z', 6, 2);
            }
        }
        const w = (BAY - 0.09) / 3;
        for (let k = 0; k < 3; k++) {
            mb.span([-DEPTH + 0.057, 0.045 + w * k + 0.0015, zt - 0.026], [-0.057, 0.045 + w * (k + 1) - 0.0015, zt - 0.0012], 2);
            mb.span([-DEPTH + 0.057, 0.045 + w * k + 0.0015, zt - 0.05], [-DEPTH + 0.059, 0.045 + w * (k + 1) - 0.0015, zt - 0.026], 2);
        }
    }
    X.asset('asset_rack_bay', X.mesh(X.fin(mb.mesh('rack_bay', RMATS), 0.0018, 0.011, 0.07)));
    let nF = 0, nB = 0;
    const guardRows = [];
    for (const row of RK.rows) {
        const yLo = Math.max(row.y[0], lay.HY0 + 1.0), yHi = row.y[1];
        if (row.face_x < lay.HX0) continue;
        const sgn = row.faces === '+x' ? 1 : -1, fx = row.face_x;
        const m0 = Math.ceil((yLo + 0.6) / BAY), m1 = Math.floor((yHi + 0.6) / BAY);
        const ys = [];
        for (let m = m0; m <= m1; m++) ys.push(-0.6 + BAY * m);
        const rz = sgn > 0 ? 0.0 : PI;
        lay.points(`rack_${row.name}_frames`, ys.map((y) => [fx, y, 0.0]), { node: 'asset_rack_frame' }, X.C.racks, rz);
        lay.points(`rack_${row.name}_bays`, ys.slice(0, -1).map((y) => [fx, sgn > 0 ? y : y + BAY, 0.0]), { node: 'asset_rack_bay' }, X.C.racks, rz);
        guardRows.push([row.name, ys.map((y) => [fx, y, 0.0]), rz]);
        nF += ys.length; nB += ys.length - 1;
    }
    shell.guards(X, guardRows);
    X.S.get('rack_frames').hidden = true;                             // the layout's plain frames, replaced by the instancers
    X.report.racks = { frames: nF, bays: nB };
    X.say('racks:', JSON.stringify(X.report.racks));
}

// ------------------------------------------------------------------------------------------------ 2c. the tracks
function tracks(X) {
    const { lay, L } = X, T = L.line.track, MT = L.main_track;
    const RR = T.roller_d / 2, RL = 2 * T.half_width - 0.08;
    let mb = new MB();
    mb.cyl([0, 0, 0], RR, RL, 'x', 28, 0);
    for (const s of [-1, 1]) {
        mb.cyl([s * (RL / 2 + 0.003), 0, 0], RR * 0.80, 0.006, 'x', 20, 1);
        mb.cyl([s * (RL / 2 + 0.013), 0, 0], 0.0075, 0.016, 'x', 6, 2);
    }
    X.asset('asset_roller', X.mesh(X.fin(mb.mesh('roller', ['steel_zinc', 'rubber_black', 'steel_galv']), 0.0015, 0.012, 0.03)));
    const TMATS = ['steel_galv', 'track_pit', 'steel_dark'];
    // the layout's flush roller track with real parts: the pit (open sheets: the detail pass leaves them), kerbs
    // screwed to the floor, the inner frames the axles sit in; the rollers are points for the instancers
    const track = (mb, px, py, x0, x1, y0, y1, axis, gap = null) => {
        const d = T.pit_depth, r = T.roller_d / 2, p = T.roller_pitch, cw = T.curb_w, ch = T.curb_h;
        mb.quad([[x0, y0, -d], [x1, y0, -d], [x1, y1, -d], [x0, y1, -d]], 1);
        mb.quad([[x0, y0, 0], [x1, y0, 0], [x1, y0, -d], [x0, y0, -d]], 1);
        mb.quad([[x1, y0, 0], [x1, y1, 0], [x1, y1, -d], [x1, y0, -d]], 1);
        mb.quad([[x1, y1, 0], [x0, y1, 0], [x0, y1, -d], [x1, y1, -d]], 1);
        mb.quad([[x0, y1, 0], [x0, y0, 0], [x0, y0, -d], [x0, y1, -d]], 1);
        if (axis === 'y') {
            let k = Math.floor((y0 + r) / p - 0.5) + 1;
            while ((k + 0.5) * p <= y1 - r - 0.004) { px.push([(x0 + x1) / 2, (k + 0.5) * p, -r]); k++; }
            for (const [xs, side] of [[x0 - cw / 2, 0], [x1 + cw / 2, 1]]) {
                let segs = [[y0, y1]];
                if (gap && side === 0) segs = [[y0, gap[0]], [gap[1], y1]];
                for (const [a, b] of segs) {
                    if (b - a <= 0.01) continue;
                    mb.span([xs - cw / 2, a, 0], [xs + cw / 2, b, ch], 0);
                    for (let yy = Math.ceil((a + 0.06) / 0.3) * 0.3 - 0.15; yy < b - 0.05; yy += 0.3) if (yy > a + 0.05) mb.cyl([xs, yy, ch + 0.0006], 0.0065, 0.0016, 'z', 12, 2);
                }
            }
            for (const xi of [x0 + 0.010, x1 - 0.010]) mb.span([xi - 0.006, y0 + 0.003, -0.072], [xi + 0.006, y1 - 0.003, -0.004], 2);
        } else {
            let k = Math.floor((x0 + r) / p - 0.5) + 1;
            while ((k + 0.5) * p <= x1 - r - 0.004) { py.push([(k + 0.5) * p, (y0 + y1) / 2, -r]); k++; }
            for (const ys of [y0 - cw / 2, y1 + cw / 2]) {
                mb.span([x0, ys - cw / 2, 0], [x1, ys + cw / 2, ch], 0);
                for (let xx = Math.ceil((x0 + 0.06) / 0.3) * 0.3 - 0.15; xx < x1 - 0.05; xx += 0.3) if (xx > x0 + 0.05) mb.cyl([xx, ys, ch + 0.0006], 0.0065, 0.0016, 'z', 12, 2);
            }
            for (const yi of [y0 + 0.010, y1 - 0.010]) mb.span([x0 + 0.003, yi - 0.006, -0.072], [x1 - 0.003, yi + 0.006, -0.004], 2);
        }
    };
    const trackObject = (name, build, coll) => {
        const mb = new MB(), px = [], py = [];
        build(mb, px, py);
        X.replace(X.fin(mb.mesh(name, TMATS), 0.002, 0.012, 0.06));
        if (px.length) lay.points(name + '_rollers', px, { node: 'asset_roller' }, coll, 0.0);
        if (py.length) lay.points(name + '_rollers_across', py, { node: 'asset_roller' }, coll, PI / 2);
        return px.length + py.length;
    };
    const hw = T.half_width, { MX, MHW, MY0 } = lay;
    let n = trackObject('line_track', (mb, px, py) => track(mb, px, py, -hw, hw, T.y0, T.y1, 'y', [-hw, hw]), X.C.line_module);
    n += trackObject('main_track', (mb, px, py) => {
        track(mb, px, py, MX - MHW, MX + MHW, MY0, MT.y_turn + MHW, 'y');
        track(mb, px, py, MT.x_end - 0.6, MX - MHW, MT.y_turn - MHW, MT.y_turn + MHW, 'x');
        for (const [, lane, , , Y0] of lay.LINES) if (lane === 0) track(mb, px, py, MX + MHW, -hw, Y0 - hw, Y0 + hw, 'x');
    }, X.C.machinery);
    n += trackObject('inbound_track', (mb, px, py) => track(mb, px, py, -hw, hw, MY0, T.y0, 'y'), X.C.machinery);
    X.report.rollers = { on_the_hero_and_main_tracks: n };
}

// ------------------------------------------------------------------------------------------------ 2d. strip lights
function stripLights(X) {
    const { lay, L } = X, H = L.hall, LZ = H.lights_z, RZ = H.roof_z, MOD = 1.5;
    let mb = new MB();
    mb.prism([[-0.036, 0.0], [0.036, 0.0], [0.036, 0.034], [0.022, 0.068], [-0.022, 0.068], [-0.036, 0.034]], -MOD / 2 + 0.002, MOD / 2 - 0.002, 'y', 0);
    mb.span([-0.029, -MOD / 2 + 0.012, -0.011], [0.029, MOD / 2 - 0.012, 0.0005], 1);
    for (const s of [-1, 1]) mb.span([-0.038, s * (MOD / 2 - 0.008) - 0.006, -0.012], [0.038, s * (MOD / 2 - 0.008) + 0.006, 0.07], 0);
    X.asset('asset_luminaire', X.mesh(X.fin(mb.mesh('luminaire', ['plastic_white', 'strip_light_glow']), 0.0025, 0.008, 0.03)));
    mb = new MB();
    mb.cyl([0, 0, (RZ - 0.2 - LZ - 0.07) / 2 + 0.07], 0.0025, RZ - 0.2 - LZ - 0.07, 'z', 6, 0);
    mb.box([0, 0, 0.078], [0.05, 0.03, 0.016], 0);
    X.asset('asset_luminaire_hanger', X.mesh(mb.mesh('luminaire_hanger', ['steel_galv'])));
    X.LIGHT_ROWS = H.light_rows_x.filter((x) => !(x < lay.HX0 || (lay.small && x < lay.LANES[lay.LANES.length - 1] - 4)));
    const N_MOD = Math.floor((lay.HY1 - 1.0 - (lay.HY0 + 1.0)) / MOD);
    X.ROW_Y1 = lay.HY1 - 1.0;
    X.ROW_Y0 = X.ROW_Y1 - N_MOD * MOD;
    const lum = [], hang = [];
    for (const x of X.LIGHT_ROWS) for (let k = 0; k < N_MOD; k++) {
        lum.push([x, X.ROW_Y1 - MOD * (k + 0.5), LZ]);
        if (k % 2 === 0) hang.push([x, X.ROW_Y1 - MOD * (k + 0.5), LZ]);
    }
    lay.points('strip_light_rows', lum, { node: 'asset_luminaire' }, X.C.hall_shell);
    lay.points('strip_light_hangers', hang, { node: 'asset_luminaire_hanger' }, X.C.hall_shell);
    X.S.get('strip_lights').hidden = true;                            // the layout's boxes, replaced by the rows
    X.report.luminaires = { rows: X.LIGHT_ROWS.length, modules: lum.length, row_y: [X.ROW_Y0, X.ROW_Y1] };
}

// ------------------------------------------------------------------------------------------------ 2e. the station
function station(X) {
    const { lay, L } = X, LE = L.line.lectern, GA = L.gantry;
    const lx = LE.x, ly = LE.y, TOPH = LE.top_h;
    const SM = ['station_white', 'steel_galv', 'steel_dark', 'machine_teal'];
    let mb = new MB();
    mb.box([lx, ly, 0.006], [0.50, 0.42, 0.012], 1);
    for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
        mb.bolt([lx + sx * 0.215, ly + sy * 0.175, 0.0165], 0.011, 0.009, 'z', 1);
        mb.cyl([lx + sx * 0.215, ly + sy * 0.175, 0.025], 0.005, 0.012, 'z', 8, 1);
    }
    mb.box([lx, ly, 0.012 + (TOPH - 0.072) / 2], [0.08, 0.08, TOPH - 0.072], 0);
    for (const sx of [-1, 1]) {
        mb.prism([[sx * 0.04, 0.012], [sx * 0.15, 0.012], [sx * 0.04, 0.13]], ly - 0.003, ly + 0.003, 'y', 0, [lx, 0.0]);
        mb.prism([[sx * 0.04, 0.012], [sx * 0.13, 0.012], [sx * 0.04, 0.13]], lx - 0.003, lx + 0.003, 'x', 0, [ly, 0.0]);
    }
    mb.span([lx - 0.26, ly - 0.15, 0.54], [lx + 0.26, ly + 0.15, 0.545], 0);
    for (const [a, b] of [[[lx - 0.26, ly - 0.15], [lx + 0.26, ly - 0.147]], [[lx - 0.26, ly + 0.147], [lx + 0.26, ly + 0.15]],
        [[lx - 0.26, ly - 0.15], [lx - 0.257, ly + 0.15]], [[lx + 0.257, ly - 0.15], [lx + 0.26, ly + 0.15]]]) {
        mb.span([a[0], a[1], 0.545], [b[0], b[1], a[1] !== ly + 0.147 ? 0.56 : 0.60], 3);
    }
    for (const sx of [-1, 1]) {
        mb.prism([[0.04, 0.54], [0.14, 0.54], [0.04, 0.44]], lx + sx * 0.03 - 0.002, lx + sx * 0.03 + 0.002, 'x', 0, [ly, 0.0]);
        mb.prism([[-0.04, 0.54], [-0.14, 0.54], [-0.04, 0.44]], lx + sx * 0.03 - 0.002, lx + sx * 0.03 + 0.002, 'x', 0, [ly, 0.0]);
    }
    mb.box([lx, ly, TOPH - 0.045], [0.16, 0.14, 0.012], 3, 0.0, RAD(LE.tilt));
    const PRX = lx + 0.50, PRY = ly + 0.02, PRZ = 0.78;                // the printer's platform (level), at the station's right hand
    mb.span([lx + 0.04, PRY - 0.02, PRZ - 0.045], [PRX + 0.14, PRY + 0.02, PRZ - 0.005], 0);
    mb.box([PRX, PRY, PRZ - 0.0025], [0.34, 0.28, 0.005], 0);
    const stZ0 = 0.62, stDx = (PRX - 0.02) - (lx + 0.04), stDz = (PRZ - 0.05) - stZ0;
    mb.box([(lx + 0.04 + PRX - 0.02) / 2, PRY, (stZ0 + PRZ - 0.05) / 2], [Math.hypot(stDx, stDz), 0.024, 0.024], 0, 0.0, 0.0, -Math.atan2(stDz, stDx));
    mb.cyl([lx + 0.048, ly + 0.048, 0.40], 0.0045, 0.72, 'z', 8, 2);
    X.replace(X.fin(mb.mesh('line_lectern', SM), 0.0025, 0.013, 0.08, 0.0));
    const w = LE.top_w, d = LE.top_d;                                  // the sloped top
    mb = new MB();
    mb.span([-w / 2, -d / 2, -0.012], [w / 2, d / 2, 0], 0);
    mb.span([-w / 2, -d / 2, 0], [w / 2, -d / 2 + 0.012, 0.022], 0);
    mb.span([-w / 2, d / 2 - 0.05, 0], [w / 2, d / 2 - 0.045, 0.010], 0);
    mb.cyl([0, -d / 2 + 0.002, -0.006], 0.0075, w, 'x', 16, 0);
    for (const sx of [-1, 1]) mb.span([sx * w / 2 - 0.002 * (sx > 0 ? 1 : 0), -d / 2, -0.034], [sx * w / 2 + 0.002 * (sx < 0 ? 1 : 0), d / 2, -0.012], 0);
    mb.span([-w / 2, d / 2 - 0.002, -0.034], [w / 2, d / 2, -0.012], 0);
    X.replace(X.fin(mb.mesh('line_lectern_top', ['steel_brushed']), 0.002, 0.016, 0.05));
    // the printer: a compact sheet printer, its slot and tray toward the station (-Y). Local frame: the body's foot
    const PM_ = ['plastic_white', 'steel_dark', 'rubber_black', 'machine_teal', 'printer_led', 'steel_galv'];
    const BW = 0.30, BD = 0.24, SLOT_Z0 = 0.096, SLOT_Z1 = 0.106, SLOT_W = 0.222;
    mb = new MB();
    mb.box([0, 0, 0.0445], [BW, BD, 0.079], 0);
    mb.box([0, 0, 0.0855], [BW - 0.008, BD - 0.008, 0.003], 1);
    const yf = -BD / 2 + 0.002, yb = BD / 2 - 0.002;
    mb.span([-BW / 2 + 0.002, yf + 0.03, 0.087], [BW / 2 - 0.002, yb, 0.137], 0);
    mb.span([-BW / 2 + 0.002, yf, 0.087], [-SLOT_W / 2, yf + 0.03, 0.137], 0);
    mb.span([SLOT_W / 2, yf, 0.087], [BW / 2 - 0.002, yf + 0.03, 0.137], 0);
    mb.span([-SLOT_W / 2, yf, SLOT_Z1], [SLOT_W / 2, yf + 0.03, 0.137], 0);
    mb.span([-SLOT_W / 2, yf, 0.087], [SLOT_W / 2, yf + 0.03, SLOT_Z0], 0);
    mb.span([-SLOT_W / 2 + 0.001, yf + 0.0285, SLOT_Z0 + 0.0005], [SLOT_W / 2 - 0.001, yf + 0.0305, SLOT_Z1 - 0.0005], 1);
    mb.cyl([0, yf + 0.016, SLOT_Z1 + 0.001], 0.0032, SLOT_W - 0.008, 'x', 12, 5);
    for (const xr of [-0.084, -0.028, 0.028, 0.084]) {
        mb.cyl([xr, yf + 0.016, SLOT_Z1 + 0.001], 0.0072, 0.016, 'x', 20, 2);
        mb.cyl([xr, yf + 0.009, SLOT_Z0 - 0.0005], 0.004, 0.012, 'x', 12, 0);
    }
    for (const xr of [-0.105, 0.105]) mb.span([xr - 0.0006, yf - 0.0004, SLOT_Z1 + 0.004], [xr + 0.0006, yf + 0.0006, SLOT_Z1 + 0.014], 1);
    mb.span([-BW / 2 + 0.0015, yf - 0.0004, 0.0868], [BW / 2 - 0.0015, yf + 0.0006, 0.0876], 1);
    mb.box([0, 0.012, 0.1385], [0.20, 0.15, 0.003], 0);
    mb.box([0, 0.012, 0.1402], [0.06, 0.012, 0.0012], 3);
    mb.span([-BW / 2 + 0.012, yf - 0.0006, 0.012], [BW / 2 - 0.012, yf + 0.001, 0.052], 0);
    mb.span([-0.05, yf - 0.0016, 0.026], [0.05, yf + 0.0004, 0.038], 1);
    mb.cyl([BW / 2 - 0.026, yf - 0.0004, 0.122], 0.0035, 0.002, 'y', 12, 4);
    mb.cyl([BW / 2 - 0.044, yf - 0.0004, 0.122], 0.0045, 0.002, 'y', 14, 1);
    for (let i = 0; i < 7; i++) mb.span([BW / 2 - 0.0008, -0.06 + 0.018 * i, 0.100], [BW / 2 + 0.0004, -0.06 + 0.018 * i + 0.008, 0.128], 1);
    for (const sx of [-1, 1]) for (const sy of [-1, 1]) mb.cyl([sx * 0.12, sy * 0.09, 0.0025], 0.011, 0.005, 'z', 14, 2);
    mb.cyl([0.09, BD / 2 + 0.006, 0.03], 0.0045, 0.016, 'y', 8, 1);
    const printer = X.ob('line_printer', X.mesh(X.fin(mb.mesh('line_printer', PM_), 0.0035, 0.012, 0.03, 0.0)), X.C.line_module, [PRX, PRY, PRZ]);
    printer.props.note = 'the lectern\'s printer: its slot and tray face -Y, toward the station. One on every line';
    const TRAY_L = 0.165, TILT = RAD(-10.0);
    mb = new MB();
    mb.span([-0.115, -TRAY_L, -0.003], [0.115, 0.0, 0.0], 0);
    for (const sx of [-1, 1]) mb.span([sx * 0.115 - 0.003 * (sx > 0 ? 1 : 0), -TRAY_L, 0.0], [sx * 0.115 + 0.003 * (sx < 0 ? 1 : 0), 0.0, 0.007], 0);
    mb.span([-0.04, -TRAY_L - 0.002, 0.0], [0.04, -TRAY_L + 0.002, 0.012], 0);
    for (const xr of [-0.084, -0.042, 0.0, 0.042, 0.084]) mb.span([xr - 0.0018, -TRAY_L + 0.010, 0.0], [xr + 0.0018, -0.008, 0.0011], 0);
    for (const sx of [-1, 1]) mb.cyl([sx * 0.095, 0.001, -0.0015], 0.004, 0.022, 'x', 12, 0);
    const HINGE = [0.0, yf - 0.001, SLOT_Z0 - 0.004];
    const tray = X.ob('line_printer_tray', X.mesh(X.fin(mb.mesh('line_printer_tray', ['plastic_white']), 0.0018, 0.008, 0.02)), X.C.line_module, HINGE, 0.0, printer);
    tray.rot = [TILT, 0.0, 0.0];
    // the sheet's way (A5, 210 x 148 mm, its long side across): hero line only; a sheet rides sheet_path
    const SHEET = [0.210, 0.148];
    const ctl = lay.empty('printer_ctl', [PRX + 0.25, PRY, PRZ + 0.3], X.C.machinery, 0.0, lay.HERO_ROOT);
    lay.controls.printer_ctl = ctl;
    const restY = HINGE[1] - (SHEET[1] / 2 + 0.006) * Math.cos(TILT), restZ = HINGE[2] - (SHEET[1] / 2 + 0.006) * Math.sin(TILT) + 0.0012;
    const startY = yf + SHEET[1] / 2 + 0.004, startZ = (SLOT_Z0 + SLOT_Z1) / 2;
    const out = lay.empty('sheet_out', [PRX, PRY + restY, PRZ + restZ], X.C.machinery, 0.0, lay.HERO_ROOT);
    out.rot = [TILT, 0.0, 0.0];
    out.props.note = 'where a fed sheet comes to rest on the tray: its centre; local +X its long side, +Y its short side, +Z up';
    const path = lay.empty('sheet_path', [PRX, PRY + startY, PRZ + startZ], X.C.machinery, 0.0, lay.HERO_ROOT);
    path.props.note = 'the sheet\'s travel, driven by feed: parent a sheet here (its centre at this origin, flat in XY)';
    X.S.drive(path, (st) => {
        const q = st.feed ?? 0.0;
        path.loc[1] = PRY + startY + (restY - startY) * q;
        path.loc[2] = PRZ + startZ + (restZ - startZ) * q;
        path.rot[0] = TILT * q;
    });
    X.PR = [PRX, PRY, PRZ];
    X.report.printer = { body_world: [PRX, PRY, PRZ], sheet: SHEET, property: 'feed 0..1' };
    // the pendant: a moulded two-shell station on its cable, a guarded push button
    const P_ = GA.pendant;
    const PMATS = ['plastic_teal', 'rubber_black', 'steel_galv'];
    mb = new MB();
    mb.span([-0.035, -0.0275, -0.12], [0.035, -0.0005, 0.12], 0);
    mb.span([-0.035, 0.0012, -0.12], [0.035, 0.0275, 0.12], 0);
    mb.box([0, 0.00035, 0], [0.066, 0.0018, 0.236], 1);
    mb.cyl([0, 0, 0.13], 0.016, 0.03, 'z', 24, 1);
    [0.0125, 0.011, 0.0095, 0.008].forEach((rr, i) => mb.cyl([0, 0, 0.151 + 0.012 * i], rr, 0.010, 'z', 16, 1));
    mb.cyl([0, 0, (P_.hang_z + P_.z + 0.12) / 2 - P_.z], 0.006, P_.hang_z - P_.z - 0.12, 'z', 10, 1);
    const bz = P_.button_z - P_.z;
    mb.cyl([0, -0.0295, bz], 0.0245, 0.005, 'y', 40, 1);
    mb.cyl([0, -0.0290, -0.03], 0.0135, 0.004, 'y', 28, 1);
    mb.cyl([0, -0.0305, -0.03], 0.0105, 0.005, 'y', 28, 2);
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) mb.cyl([sx * 0.027, -0.0279, sz * 0.108], 0.0034, 0.0014, 'y', 12, 2);
    mb.span([-0.012, -0.0284, 0.086], [0.012, -0.0272, 0.098], 1);
    X.replace(X.fin(mb.mesh('pendant_body', PMATS), 0.0035, 0.009, 0.025));
    mb = new MB();
    mb.cyl([0, -0.006, 0], 0.018, 0.012, 'y', 40, 0);
    mb.cyl([0, -0.0125, 0], 0.0145, 0.0012, 'y', 40, 0);
    X.replace(X.fin(mb.mesh('pendant_button', ['plastic_white']), 0.0016, 0.004, 0.0));
}

// ------------------------------------------------------------------------------------------------ 2f. chain link
// chain link as it is woven: every wire a zigzag that hooks its neighbours at each bend, over and under
function chainLink(X) {
    const RC = X.L.returns_cage, [gx0, gx1] = RC.x, [gy0, gy1] = RC.y, gh = RC.h;
    const mb = new MB();
    const woven = (a, b, z0, z1, pitch = 0.07, wire = 0.0032) => {
        const W = Math.hypot(b[0] - a[0], b[1] - a[1]), ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
        const ux = (b[0] - a[0]) / W, uy = (b[1] - a[1]) / W, nx = -uy, ny = ux;
        const nw = Math.trunc(W / pitch), nz = Math.trunc((z1 - z0) / pitch);
        const ln = pitch * Math.SQRT2 + wire;
        const f0 = mb.f.length;
        for (let k = 0; k < nw; k++) for (let j = 0; j < nz; j++) {
            const right = (j + k) % 2 === 0;
            const um = (k + 0.5) * pitch + (W - nw * pitch) / 2, zm = z1 - (j + 0.5) * pitch;
            const off = 0.0013 * (((j % 2 === 0) === right) ? 1 : -1);
            mb.box([a[0] + ux * um + nx * off, a[1] + uy * um + ny * off, zm], [wire, ln, wire], 0, ang - PI / 2, (PI / 4) * (right ? 1 : -1));
        }
        for (let i = f0; i < mb.f.length; i++) mb.sm[i] = true;
    };
    const corners = [[gx0, gy0], [gx1, gy0], [gx1, gy1], [gx0, gy1]];
    woven(corners[0], corners[1], 0.05, gh);
    woven(corners[0], [gx0, gy0 + 1.6], 0.05, gh);
    woven([gx0, gy0 + 3.0], corners[3], 0.05, gh);
    woven([gx0 + 0.25, gy0 + 1.62], [gx0 + 1.55, gy0 + 2.55], 0.05, gh);
    X.replace(mb.mesh('cage_chain_link', ['chain_galv'], false));
}

// ------------------------------------------------------------------------------------------------ 2h. the rest
function theRest(X) {
    const { lay, L } = X;
    machines.crane(X);
    machines.cabinet(X, shell.TRAY_Z);
    const MC_ = L.meter_cabinet;                                       // the meter's own lamp over its window (casts nothing)
    X.lights.push({ type: 'area', name: 'meter_drum_lamp', pos: [(MC_.x[0] + MC_.x[1]) / 2, MC_.y[1] - 0.02, MC_.window_z + 0.075], rot: [RAD(-25.0), 0, 0],
        size: [0.36, 0.012], power: null, opt: 'drum_lamp', colour: 'lamp', reach: 0.30, coll: 'meter_cabinet' });
    const PN = L.gantry.pendant, mx = PN.mast_x, my = PN.y, hz = PN.hang_z;
    let mb = new MB();
    mb.cyl([mx, my, (hz + 0.05) / 2 + 0.006], 0.03, hz + 0.05 - 0.012, 'z', 20, 0);
    mb.cyl([mx, my, 0.006], 0.11, 0.012, 'z', 24, 0);
    mb.cyl([mx, my, hz + 0.052], 0.033, 0.006, 'z', 20, 0);
    for (let k = 0; k < 4; k++) { const a = PI / 4 + k * PI / 2; mb.bolt([mx + Math.cos(a) * 0.08, my + Math.sin(a) * 0.08, 0.0165], 0.010, 0.009, 'z', 1); }
    mb.span([mx, my - 0.02, hz], [PN.x + 0.03, my + 0.02, hz + 0.04], 0);
    mb.prism([[mx + 0.03, hz], [mx + 0.12, hz], [mx + 0.03, hz - 0.09]], my - 0.003, my + 0.003, 'y', 0);
    mb.cyl([PN.x, my, hz - 0.012], 0.012, 0.024, 'z', 12, 1);
    mb.tube([[PN.x, my + 0.026, hz + 0.02], [mx + 0.05, my + 0.026, hz + 0.02], [mx + 0.0, my + 0.036, hz - 0.03], [mx, my + 0.036, 1.32]], 0.006, 8, 2);
    for (const z of [hz - 0.25, 2.0, 1.6]) mb.box([mx, my + 0.036, z], [0.03, 0.016, 0.012], 1);
    mb.box([mx, my + 0.055, 1.22], [0.09, 0.05, 0.14], 3);
    mb.cyl([mx, my + 0.055, 1.30], 0.011, 0.02, 'z', 6, 1);
    X.replace(X.fin(mb.mesh('line_pendant_mast', ['station_white', 'steel_galv', 'rubber_black', 'plastic_grey']), 0.002, 0.01, 0.05, 0.0));
    const ST = L.line.stack;                                           // the hood stack's base: a framed deck, ribs, landing strips, feet
    const ya = ST.y0 + ST.col_pitch / 2, yb = ST.y0 - ST.col_pitch * (ST.cols - 0.5);
    const sx0 = ST.x - 0.475, sx1 = ST.x + 0.475, bh = ST.base_h;
    mb = new MB();
    mb.span([sx0 + 0.02, yb + 0.02, bh - 0.006], [sx1 - 0.02, ya - 0.02, bh], 0);
    for (const [a, b] of [[[sx0, yb], [sx1, yb + 0.04]], [[sx0, ya - 0.04], [sx1, ya]], [[sx0, yb + 0.04], [sx0 + 0.04, ya - 0.04]], [[sx1 - 0.04, yb + 0.04], [sx1, ya - 0.04]]]) {
        mb.span([a[0], a[1], 0.0], [b[0], b[1], bh], 0);
    }
    for (let c = 0; c <= ST.cols; c++) {
        let y = ya - ST.col_pitch * c;
        y = Math.min(Math.max(y, yb + 0.012), ya - 0.012);
        mb.span([sx0 + 0.04, y - 0.012, bh], [sx1 - 0.04, y + 0.012, bh + 0.02], 0);
        if (c < ST.cols) for (const sx of [-0.3, 0.3]) mb.span([ST.x + sx - 0.05, y - ST.col_pitch + 0.08, bh], [ST.x + sx + 0.05, y - 0.08, bh + 0.004], 1);
    }
    for (const x of [sx0 - 0.03, sx1 + 0.03]) for (const y of [yb + 0.12, (ya + yb) / 2, ya - 0.12]) {
        mb.box([x, y, 0.004], [0.06, 0.10, 0.008], 0);
        mb.bolt([x, y, 0.013], 0.010, 0.008, 'z', 0);
    }
    X.replace(X.fin(mb.mesh('line_hood_stack_base', ['steel_galv', 'rubber_black']), 0.003, 0.016, 0.06, 0.0));
    for (const [nm, kw] of [['cage_posts', { bevel: 0.002, inset: 0.01, ground: 0.0 }], ['dock_threshold', { bevel: 0.002, inset: 0.012, cavity: 0.0 }],
        ['office_window', { bevel: 0.003, inset: 0.014 }], ['ph_clipboard', { bevel: 0.0008, inset: 0.004, cavity: 0.02 }],
        ['ph_cards', { bevel: 0.0006, inset: 0.004, cavity: 0.02 }], ['ph_notebook', { bevel: 0.001, inset: 0.004, cavity: 0.02 }],
        ['ph_pencils', { bevel: 0.0004, inset: 0.002, cavity: 0.0 }], ['meter_drum_housing', { bevel: 0.001, inset: 0.006, cavity: 0.0 }],
        ['carton_base', { bevel: 0.0015, inset: 0.012, cavity: 0.06, ground: 0.0 }], ['carton_collar', { bevel: 0.001, inset: 0.006, cavity: 0.04 }],
        ['carton_hood', { bevel: 0.0015, inset: 0.012, cavity: 0.04 }]]) X.finishNamed(nm, kw);
    for (let k = 0; k < L.meter_cabinet.digits; k++) X.finishNamed(`meter_drum_${k}`, { bevel: 0.0012, inset: 0.006, cavity: 0.02 });
    X.S.get('meter_window_glass').hidden = false;                      // real glass now (thin, smudged)
}

// ------------------------------------------------------------------------------------------------ 3. light
// the light plan (world.js makes the three.js lights): the strip rows as continuous area lights, none casting a
// shadow; over the hero aisle (the two rows, as far as the fine probe reached in the Blender edition) a light per
// 11-13 m, elsewhere one per 48 m and a beam of 80 degrees; one wide lamp at 6 m that looks up at the roof; the dock
// sun with its shadow; the haze box
function light(X) {
    const { lay, L } = X, H = L.hall, LZ = H.lights_z;
    const SEG_NEAR = 12.0, SEG_FAR = 48.0, NEAR_Y = -72.0, PROBE_Y0 = -14.4;
    const { ROW_Y0, ROW_Y1 } = X;
    X.LIGHT_ROWS.forEach((x, i) => {
        const nearRow = x > -11.5, heroRow = x > -10.0;
        const cuts = [ROW_Y1];
        if (heroRow && ROW_Y0 < PROBE_Y0) for (let k = 0; k < 3; k++) cuts.push(ROW_Y1 - (ROW_Y1 - PROBE_Y0) * (k + 1) / 3);
        if (nearRow && ROW_Y0 < NEAR_Y) {
            const top = cuts[cuts.length - 1], n = Math.max(1, Math.round((top - NEAR_Y) / SEG_NEAR));
            for (let k = 0; k < n; k++) cuts.push(top - (top - NEAR_Y) * (k + 1) / n);
        }
        const rest = cuts[cuts.length - 1] - ROW_Y0;
        if (rest > 0.01) {
            const last = cuts[cuts.length - 1];
            const n = Math.max(1, Math.round(rest / ((nearRow && ROW_Y0 >= NEAR_Y) ? SEG_NEAR : SEG_FAR)));
            for (let k = 0; k < n; k++) cuts.push(last - rest * (k + 1) / n);
        }
        for (let j = 0; j < cuts.length - 1; j++) {
            const ya = cuts[j], yb = cuts[j + 1], ln = ya - yb, yc = (ya + yb) / 2;
            if (ln < 0.01) continue;
            const baked = heroRow && yb >= PROBE_Y0 - 0.01;
            X.lights.push({ type: 'strip', name: `strip_r${String(i).padStart(2, '0')}_s${String(j).padStart(2, '0')}`, pos: [x, yc, LZ - 0.014], size: [0.058, ln],
                perMetre: true, far: !baked, hero: baked, spread: baked ? 170 : 80, reach: 62.0 + ln / 2 });
        }
    });
    X.lights.push({ type: 'bounce', name: 'hall_floor_bounce', pos: [(lay.HX0 + lay.HX1) / 2, (lay.HY0 + lay.HY1) / 2, 6.0], size: [lay.HX1 - lay.HX0, lay.HY1 - lay.HY0] });
    // the hero aisle's fine volume probe (Blender's hall_probe_aisle, baked from emitting boxes under the two hero
    // rows): its box, where the hero rows' lamps give highlights only and the diffuse light is the probe's
    X.aisleProbe = { lo: [-7.2, PROBE_Y0, 0.0], hi: [lay.HX1, lay.HY1 + 0.4, X.RZ] };
    X.lights.push({ type: 'sun', name: 'sun_dock', dir: lay.SUN_DIR });
    X.haze = { lo: [lay.HX0 + 0.05, lay.HY0 + 0.05, 0.03], hi: [lay.HX1 - 0.05, lay.HY1 - 0.02, X.RZ - 0.02] };
    X.report.light = { strip_lights: X.lights.filter((l) => l.type === 'strip').length, kelvin: LAMP_K, white_balance_kelvin: WB_K, sun_kelvin: SUN_K };
}

// ------------------------------------------------------------------------------------------------ 4. settings
function settings(X) {
    const { lay } = X;
    const [PRX, PRY, PRZ] = X.PR;
    lay.cams.cam_printer = { pos: [PRX + 0.06, PRY - 0.66, PRZ + 0.36], aim: [PRX, PRY - 0.20, PRZ + 0.075], up: [0, 0, 1], lens: 70.0, ortho: null };
    lay.cams.cam_line_85 = { pos: [5.0, -5.8, 1.05], aim: [0.16, 4.08, 0.61], up: [0, 0, 1], lens: 85.0, ortho: null };
    // the meter cabinet stands 80 mm off the wall's dado (flush it reads as sunk into the wall), with its own cameras
    for (const o of lay.S.colls.get('meter_cabinet').nodes) if (!o.parent) o.loc[0] -= 0.08;
    for (const l of X.lights) if (l.coll === 'meter_cabinet') l.pos[0] -= 0.08;
    for (const n of ['cam_drums', 'cam_cabinet_window', 'cam_cabinet_lock']) {
        const c = lay.cams[n];
        if (c) { c.pos[0] -= 0.08; c.aim[0] -= 0.08; }               // (moved with its aim: the camera keeps its turn)
    }
    lay.report.cameras = Object.keys(lay.cams).sort();
}

// a node's world matrix and position in the hall's frame (for the tests and the API)
export const worldOf = (lay, name) => lay.S.world(typeof name === 'string' ? lay.S.get(name) : name);
export const posOf = (lay, name) => M4.pos(worldOf(lay, name));
export { Node };
