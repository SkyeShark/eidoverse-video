// eidoverse/sets/wake_another_one/hall/hall_test.mjs — the hall's machines move as the Blender edition's do:
//   deno test -A --no-lock eidoverse/sets/wake_another_one/hall/hall_test.mjs
// The numbers on the right are the Blender edition's test's (blender/tests/sets_wake_another_one/test_hall.py, the
// small hall): its drivers are ported one function each (build.js, look.js), so the same controls put every part in
// the same place. No GPU: the layout, the look's geometry and the rig run without three.js.
import { plan, animate, CONTROLS } from '../hall.js';
import { M4 } from './graph.js';
import { finish, detail, openEdges, MB } from './kit.js';

const assert = (x, m = 'Assertion failed') => { if (!x) throw Error(m); };
const near = (a, b, e, m = '') => assert(Math.abs(a - b) <= e, `${m}: ${a} versus ${b}`);
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

const { lay, X } = plan({ small: true, look: true, trees: true });
const S = lay.S;
const st = { run: 10.0, along_offset: 0.0, hoist_offset: 0.0, travel: 0.0, swap: 1.0, crowd_run: lay.CROWD_MAX, press: 0.0, meter: 3861, feed: 0.0 };
const at = (name, k = {}) => { Object.assign(st, k); S.evaluate(st); return M4.pos(S.world(S.get(name))); };

Deno.test('the layout: the small hall, its cameras, its controls, the carton', () => {
    assert(lay.report.lines.lines === 3 && lay.report.lines.units === 30, `lines ${JSON.stringify(lay.report.lines)}`);
    for (const c of ['cam_aisle_out', 'cam_aisle_in', 'cam_station', 'cam_dock', 'cam_drums', 'cam_line_long', 'cam_top_unit1', 'cam_printer', 'cam_line_85']) {
        assert(lay.cams[c], `camera ${c}`);
    }
    assert(Object.keys(lay.cams).length === 22, `${Object.keys(lay.cams).length} cameras (Blender: 22)`);
    for (const c of ['gantry_ctl', 'track_ctl', 'crowd_ctl', 'meter_cabinet_ctl', 'gantry_pendant', 'printer_ctl']) assert(lay.controls[c], `control ${c}`);
    assert(Object.keys(CONTROLS).length === 10, 'the ten controls');
    const m = lay.report.carton;
    near(m.hood_height, lay.L.carton.size[2] - lay.L.carton.seam_z, 1e-6, 'the hood\'s height');
    assert(lay.report.stock_cartons.near === 108 && lay.report.stock_cartons.far === 486, `stock ${JSON.stringify(lay.report.stock_cartons)} (Blender: 108 near, 486 far)`);
    assert(X.lights.filter((l) => l.type === 'strip').length === 16, 'sixteen strip lights (Blender: 16)');
    near(lay.report.dock_sun.elevation_deg, 17.823, 1e-3, 'the dock sun\'s elevation');
});

Deno.test('run 0 -> 1 lifts unit 0\'s hood and sets it in stack slot 0; run 1.3 has the bridge over unit 1, its ring down', () => {
    const h0 = at('line_00_hood_0', { run: 0.0 });
    const park = at('gantry_bridge')[1];
    const up = at('line_00_hood_0', { run: 0.5 });
    near(up[2] - h0[2], 0.685, 5e-4, 'the hood lifted at run 0.5 (Blender 0.000 -> 0.685 m)');
    const inSlot = at('line_00_hood_0', { run: 1.0 }), slot0 = at('line_00_stack_slot_0');
    near(dist(inSlot, slot0), 0.0, 1e-7, 'unit 0\'s hood in slot 0 at run 1.0');
    near(park, -1.45, 1e-9, 'the bridge parked');
    const by = at('gantry_bridge', { run: 1.3 })[1], ring = at('gantry_ring')[2];
    near(by, 1.2, 1e-4, 'run 1.3: the bridge over unit 1 (Blender 1.200)');
    near(ring, 1.572, 5e-4, 'run 1.3: the ring down (Blender 1.572 m)');
    const by2 = at('gantry_bridge', { along_offset: 0.5 })[1];
    near(by2 - by, 0.5, 1e-9, 'along_offset 0.5 moves the bridge 0.5000 m');
    at('gantry_bridge', { along_offset: 0.0, run: 10.0 });
});

Deno.test('swap rolls unit 0\'s tray out; travel rolls the stream; the meter, the button and the printer', () => {
    const t0 = at('line_00_tray_a', { swap: 0.0 }), t1 = at('line_00_tray_a', { swap: 0.6 });
    near(t0[0], 0.0, 1e-9, 'tray_a at unit 0');
    near(t1[0], -3.0, 1e-9, 'swap 0.6: tray_a on the main track (Blender x -3.000)');
    near(t1[1], 13.1, 5e-3, 'swap 0.6: tray_a down the main track (Blender y 13.10)');
    const s0 = at('stream_box_00', { swap: 1.0 }), s1 = at('stream_box_00', { travel: 1.0 });
    near(dist(s0, s1), 1.0, 1e-9, 'travel 1 m rolls a stream carton 1.0000 m');
    at('stream_box_00', { travel: 0.0, meter: 1234 });
    const tenths = lay.DRUMS.map((d) => (((d.rot[0] / 0.6283185) % 10) + 10) % 10);
    [4, 3, 2, 1].forEach((w, k) => near(tenths[k], w, 0.01, `the meter shows 1234: drum ${k}`));
    const b0 = at('gantry_pendant_button', { press: 0.0 }), b1 = at('gantry_pendant_button', { press: 1.0 });
    near(dist(b0, b1) * 1000, 6.0, 1e-6, 'press moves the button 6.00 mm');
    const p0 = at('sheet_path', { press: 0.0, feed: 0.0 }), p1 = at('sheet_path', { feed: 1.0 }), out = at('sheet_out');
    near(dist(p1, out), 0.0, 1e-7, 'feed 1: the sheet lies at sheet_out');
    near(dist(p0, p1) * 1000, 157.9, 0.05, 'feed carries the sheet 157.9 mm onto the tray');
    at('sheet_path', { feed: 0.0, meter: 3861 });
});

Deno.test('animate keys a control on frames as the Blender edition does', () => {
    const key = animate({ run: [[1, 2.0], [49, 3.0]] }, { fps: 24 });
    near(key((25 - 1) / 24).run, 2.5, 1e-9, 'frame 25 reads 2.5');
    const by = at('gantry_bridge', key((25 - 1) / 24))[1];
    near(by, 2.4, 1e-4, 'the bridge at frame 25 (Blender y 2.400)');
    at('gantry_bridge', { run: 10.0 });
});

Deno.test('the detail pass keeps a closed shell closed and makes the wear band', () => {
    const mb = new MB();
    mb.span([0, 0, 0], [0.4, 0.2, 0.1]);
    mb.cyl([1, 0, 0], 0.03, 0.9, 'x', 28, 0);
    mb.bolt([2, 0, 0], 0.012, 0.01, 'z', 0);
    const md = mb.mesh('probe', ['a']);
    const r = detail(md, { bevel: 0.0025, inset: 0.014 });
    assert(openEdges(md) === 0, 'no open edge');
    // the box's 12; the 28-sided rod's two cap rings (its 12.9 degree side edges stay smooth); the bolt's hex head
    // (6 sides, 2 rings) and its 12-sided washer's two rings (its 30 degree sides stay smooth)
    assert(r.bevelled_edges === 12 + 2 * 28 + (6 + 2 * 6) + 2 * 12, `bevelled edges ${r.bevelled_edges}`);
    const w = md.soup.wear;
    assert(w.some((v) => v === 1) && w.some((v) => v === 0), 'wear runs 1 on the arris to 0 on the inset loop');
    assert(typeof finish === 'function');
});
