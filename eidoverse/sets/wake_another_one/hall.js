// eidoverse/sets/wake_another_one/hall.js — the automated factory hall of the WAKE ANOTHER ONE music video: the
// three.js edition's port of the Blender edition's eidoblend.sets.wake_another_one.hall. Dynamic ESM; import it inside
// setup():
//
//   const HALL = await import(new URL('sets/wake_another_one/hall.js', EIDOVERSE_DIR).href);
//   const hall = await HALL.build(THREE, { small: false });       // look, sky, trees on by default
//   scene.add(hall.group);
//   await hall.applyTo(scene, renderer, camera);                   // the sky, its sun, AgX as Blender draws it, the air
//   hall.camera('cam_aisle_out', camera);                          // the Blender edition's lenses (hall.cams)
//   per frame: hall.update(t, { run: 3.4, travel: 1.2 * t });      // the controls (CONTROLS), then render
//   const key = HALL.animate({ run: [[1, 0], [240, 3]], meter: [[1, 3861], [96, 0]] }, { fps: 24 });   // key(t) -> state
//
// WHAT IT IS: a hall 79 x 248 m and 13 m high. One hero line runs down a canyon of racks toward the dock door: a flush
// roller track with ten cartons on it (units 0..9: a tray each, its hood on), a hood stack, a lectern with a printer
// and the crane's hanging control, and an overhead crane (runway, bridge, trolley, a ring with four gripper pads)
// that lifts the hoods off one unit after another and stacks them. Behind the racks the open floor holds lines in
// rows, each with its own crane. A main track carries a stream of closed cartons out through the dock door; a
// mechanical counter (four drums in a cabinet) shows a number; a returns cage, an office window high on the side wall,
// and a yard beyond the door with parked trailers, a fence and SeedThree trees under a low afternoon sun that lays a
// warm patch across the last unit's tray. small: true builds two rows of two lanes in a hall cut short at y -45.
//
// THE CONTROLS (CONTROLS: the Blender edition's custom properties, by the same names):
//   run           the hero crane: the whole part the unit it works on (0..9; 10 the fresh carton at unit_0), the
//                 fraction the move (travel, lower, grip, raise, carry to the stack, set down); 0 = ten closed
//                 cartons, 10 = units 1..9 open
//   along_offset, hoist_offset   metres added to the bridge's place and the ring's height
//   travel        metres the main track's stream has rolled toward the dock
//   swap          0..1: unit_0's open tray rolls out along the spur while a fresh closed carton rolls in
//   crowd_run     every other line's crane, as run for units 1..9, each row a little after the one before
//   press         the pendant's button, 0 out .. 1 in
//   meter         the number the counter shows (0..9999), rolling like an odometer
//   feed          the printer feeds one sheet out onto its tray (0 -> 1); the node sheet_path carries it
//   haze          1 the hall's air is drawn, 0 it is not
// Each of the Blender edition's simple-expression drivers is one function of these (hall/build.js, look.js).
// THE CARTON is a two-part carton (hall/carton.js); a unit's node line_NN_unit_K is its tray's frame, and a body
// stands at the carton's body_mark in it (line_00_mark_K). hall.mark(name) gives any node's world matrix.
// THE LOOK: every surface a layered material in TSL over CC0 scans fetched by ID (hall/mats.js), on geometry the
// Blender kit's detail pass prepared (hall/kit.js: bevels, a wear band, baked cavity, UVs in metres), the machines
// and the shell with real sections (hall/machines.js, hall/shell.js). Guide: tools-guides/props-and-sets.md, "The WAKE
// ANOTHER ONE hall".
import { Layout } from './hall/build.js';
import { look as makeLook, balanced, LAMP_K, SUN_K } from './hall/look.js';
import { finish, toGeometry, MB } from './hall/kit.js';
import { M4 } from './hall/graph.js';
import { makeMats } from './hall/mats.js';
import * as W from './hall/world.js';

const HERE = new URL('./hall/', import.meta.url);
export const CONTROLS = {
    run: ['gantry_ctl', 'run'], along_offset: ['gantry_ctl', 'along_offset'], hoist_offset: ['gantry_ctl', 'hoist_offset'],
    travel: ['track_ctl', 'travel'], swap: ['track_ctl', 'swap'], crowd_run: ['crowd_ctl', 'crowd_run'], press: ['gantry_pendant', 'press'],
    meter: ['meter_cabinet_ctl', 'meter'], feed: ['printer_ctl', 'feed'], haze: ['look_ctl', 'haze'],
};
export const DEFAULTS = { run: 10.0, along_offset: 0.0, hoist_offset: 0.0, travel: 0.0, swap: 1.0, crowd_run: null, press: 0.0, meter: null, feed: 0.0, haze: 1.0 };
// the drawn collections (assets is drawn only through instancers; line_module through each line's instance of it)
const DRAWN = ['hall_shell', 'racks', 'boxes_stock', 'lines', 'line_hero', 'machinery', 'meter_cabinet', 'returns_cage', 'dock'];

// layout.json as an object (every dimension the build reads)
export function layout() { return JSON.parse(Deno.readTextFileSync(new URL('layout.json', HERE))); }

// the layout and the look's geometry and rig, without three.js (the tests read the machines from this)
export function plan({ small = false, look = true, trees = true, log = () => {} } = {}) {
    const lay = new Layout(layout(), { small, log }).run();
    const X = look ? makeLook(lay, { trees, log }) : null;
    return { lay, X };
}

// keyed controls: keys { control: [[frame, value], ...] } -> (t) => state, linear between keys (or 'CONSTANT'),
// constant past the ends; frames count from 1 at t = 0, as the Blender edition's animate() keys them
export function animate(keys, { fps = 24, interpolation = 'LINEAR' } = {}) {
    const tracks = Object.entries(keys).map(([k, pts]) => [k, [...pts].sort((a, b) => a[0] - b[0])]);
    return (t) => {
        const f = 1 + t * fps, st = {};
        for (const [k, pts] of tracks) {
            if (f <= pts[0][0]) { st[k] = pts[0][1]; continue; }
            let v = pts[pts.length - 1][1];
            for (let i = 1; i < pts.length; i++) {
                if (f <= pts[i][0]) {
                    const [f0, v0] = pts[i - 1], [f1, v1] = pts[i];
                    v = interpolation === 'CONSTANT' ? v0 : v0 + (v1 - v0) * (f - f0) / (f1 - f0);
                    break;
                }
            }
            st[k] = v;
        }
        return st;
    };
}

// the meter's digits: Rajdhani Bold's glyphs (the font the Blender edition sets them in), laid flat 0.7 mm off each
// drum's rim, digit n at -36 n degrees about the drum's axis, upright on its front (+Y)
async function addDigits(THREE, lay) {
    const { default: opentype } = await import('npm:opentype.js@1.3.4');
    const path = new URL('../../assets/fonts/Rajdhani-Bold.ttf', import.meta.url);
    let font;
    try { const b = Deno.readFileSync(path); font = opentype.parse(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)); }
    catch (e) { lay.say(`the meter's font is not here (${e.message}): its drums are blank`); return; }
    const glyphs = [];
    for (let n = 0; n < 10; n++) {
        const md0 = [...lay.meshes.values()].find((m) => m.digits);
        const size = md0.digits.size;
        const p = font.getPath(String(n), 0, 0, size);
        const sp = new THREE.ShapePath();
        for (const c of p.commands) {                                // (opentype's y runs down: flipped)
            if (c.type === 'M') sp.moveTo(c.x, -c.y);
            else if (c.type === 'L') sp.lineTo(c.x, -c.y);
            else if (c.type === 'Q') sp.quadraticCurveTo(c.x1, -c.y1, c.x, -c.y);
            else if (c.type === 'C') sp.bezierCurveTo(c.x1, -c.y1, c.x2, -c.y2, c.x, -c.y);
        }
        const shapes = sp.toShapes(true);
        const tris = [];
        let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
        for (const s of shapes) {
            const { shape, holes } = s.extractPoints(4);
            const pts = [...shape, ...holes.flat()];
            for (const t of THREE.ShapeUtils.triangulateShape(shape, holes)) tris.push(t.map((i) => [pts[i].x, pts[i].y]));
            for (const q of pts) { x0 = Math.min(x0, q.x); x1 = Math.max(x1, q.x); y0 = Math.min(y0, q.y); y1 = Math.max(y1, q.y); }
        }
        const adv = font.getAdvanceWidth(String(n), size);
        glyphs.push({ tris, cx: adv / 2, cy: (y0 + y1) / 2 });
    }
    for (const md of lay.meshes.values()) {
        if (!md.digits) continue;
        const R = md.digits.R;
        for (let n = 0; n < 10; n++) {
            const a = -n * 36 * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
            const isl = md.isl.length ? Math.max(...md.isl) + 1 : 0;
            for (const t of glyphs[n].tris) {
                const i0 = md.v.length;
                for (const [x, y] of t) {
                    // the glyph's plane (x, y) -> (-x, R + 0.0007, y) on the drum's front, turned about +X by -36 n
                    const px = -(x - glyphs[n].cx), py = R + 0.0007, pz = y - glyphs[n].cy;
                    md.v.push([px, py * c - pz * s, py * s + pz * c]);
                }
                md.f.push([i0, i0 + 2, i0 + 1]); md.mi.push(1); md.sm.push(false); md.isl.push(isl + n);
            }
        }
    }
}

export async function build(THREE, { small = false, look = true, sky = true, trees = true, shadows = true, capture = true, log = console.log, ...opt } = {}) {
    const T = THREE;
    const t0 = performance.now();
    const OPT = { ...W.OPT, ...opt };
    const { lay, X } = plan({ small, look, trees, log });
    const say = (...a) => log(`[hall ${((performance.now() - t0) / 1000).toFixed(1).padStart(6)} s] ${a.join(' ')}`);
    say(`the layout: ${JSON.stringify(lay.report.lines)}, stock ${JSON.stringify(lay.report.stock_cartons)}, ${lay.meshes.size} meshes`);
    await addDigits(T, lay);
    // the detail pass and the cavity bake on every mesh the look prepares
    let { MeshBVH } = await import('npm:three-mesh-bvh@0.9.10');
    const draw = lay.S.flatten(DRAWN);
    const used = new Set(draw.map((d) => d.mesh));
    if (look) {
        const t1 = performance.now();
        let n = 0, faces = 0;
        for (const name of used) {
            const md = lay.meshes.get(name);
            if (!md || !md.fin) continue;
            const r = finish(md, md.fin, { THREE: T, MeshBVH });
            n++; faces += r.faces;
        }
        say(`detail + cavity on ${n} meshes (${faces} faces) in ${((performance.now() - t1) / 1000).toFixed(1)} s`);
    }
    MeshBVH = null;
    const geos = new Map();
    for (const name of used) {
        const md = lay.meshes.get(name);
        if (!md) { log(`[hall] no mesh ${name}`); continue; }
        geos.set(name, toGeometry(T, md));
    }
    // materials
    const MT = await makeMats(T, { log: (...a) => log(...a), flat: !look });
    const specs = look ? X.M : lay.M;
    const mats = new Map();
    for (const g of geos.values()) for (const nm of g.userData.materials) if (!mats.has(nm)) mats.set(nm, await MT.material(nm, specs[nm] || lay.M[nm], lay.L));
    say(`${mats.size} materials, ${geos.size} meshes drawn`);
    // what is drawn: one InstancedMesh per mesh (and per shadow-only use), its driven placings updated per frame
    const group = new T.Group();
    group.name = 'wake_another_one_hall';
    group.rotation.x = -Math.PI / 2;                                    // the hall's +Z up into three's +Y up
    group.userData.noSupportCheck = true;                               // (it is its own ground)
    const byKey = new Map();
    for (const d of draw) {
        const key = d.mesh + (d.shadowOnly ? '|shadow' : '');
        if (!byKey.has(key)) byKey.set(key, []);
        byKey.get(key).push(d);
    }
    const parts = {}, dynamic = [];
    let tris = 0, inst = 0;
    const m4 = new T.Matrix4();
    for (const [key, ds] of byKey) {
        const name = key.split('|')[0], geo = geos.get(name);
        if (!geo) continue;
        const ms = geo.userData.materials.map((m) => mats.get(m));
        const im = new T.InstancedMesh(geo, ms.length === 1 ? ms[0] : ms, ds.length);
        let dyn = false;
        ds.forEach((d, i) => {
            im.setMatrixAt(i, m4.fromArray(lay.S.matrixOf(d)));
            if (d.dynamic) { dynamic.push([im, i, d]); dyn = true; }
        });
        im.instanceMatrix.needsUpdate = true;
        if (dyn) { im.frustumCulled = false; im.instanceMatrix.setUsage(T.DynamicDrawUsage); } else im.computeBoundingSphere();
        im.castShadow = !ds[0].noShadow;
        im.receiveShadow = true;
        if (ds[0].shadowOnly) im.layers.set(1);
        im.name = key;
        group.add(im);
        parts[key] = im;
        tris += geo.userData.triangles * ds.length; inst += ds.length;
    }
    say(`drawn: ${byKey.size} instanced meshes, ${inst} placings, ${(tris / 1e6).toFixed(2)} M triangles (${dynamic.length} driven)`);
    // light, models, trees, the hall's reflections
    let lights = null, env = null, sunLight = null, cc0 = null;
    const outdoors = ['yard_field', 'yard_kerb', 'yard_trailer', 'yard_masts', 'dock_apron'].map((k) => parts[k]);
    if (look) {
        lights = await W.makeLights(T, X, lay, group, OPT);
        sunLight = lights.sun;
        cc0 = await W.models(T, X, group, { log });
        outdoors.push(cc0.fence);
        if (trees) outdoors.push((await W.trees(T, X, group, { sun: sunLight, log, sunStrength: OPT.sun }))?.root);
    } else {
        // the layout's own light: the dock sun at 9 W/m2 and two shadowless fills from above
        sunLight = new T.DirectionalLight(new T.Color(1.0, 0.80, 0.58), 9.0);
        lights = { sun: sunLight, all: [sunLight], fills: [] };
        for (const [e, dv] of [[1.7, [-0.42, 0.30, -0.86]], [0.9, [0.50, -0.36, -0.79]]]) {
            const f = new T.DirectionalLight(new T.Color(0.86, 0.92, 1.0), e);
            f.position.set(-dv[0], -dv[1], -dv[2]).multiplyScalar(50);
            group.add(f, f.target);
            lights.fills.push(f);
        }
    }
    const state = { ...DEFAULTS, crowd_run: lay.CROWD_MAX, meter: lay.L.meter_cabinet.default };
    lay.S.evaluate(state);
    let S = null, fog = null, pending = null, R = null;
    const report = { layout: lay.report, look: X ? X.report : null, seconds: 0, triangles: tris, placings: inst, materials: mats.size };
    const cams = lay.cams;

    const driven = new Set(dynamic.map((d) => d[0]));
    function updateDynamic() {
        for (const [im, i, leaf] of dynamic) im.setMatrixAt(i, m4.fromArray(lay.S.matrixOf(leaf)));
        for (const im of driven) im.instanceMatrix.needsUpdate = true;
    }

    const hall = {
        group, parts, lights, layout: lay.L, lay, look: X, report, cams, CONTROLS, state, env, mats: MT,
        get sky() { return S; },
        // the controls: state merges over the current values (unnamed ones keep theirs); t runs the sky and the trees
        update(t = 0, st = {}) {
            Object.assign(state, st);
            lay.S.evaluate(state);
            updateDynamic();
            if (S) S.S.update(t);
            if (fog) fog.enabled.value = state.haze > 0.5 ? 1.0 : 0.0;
            if (pending && env) {                                       // the hall's reflections, once, before the first frame's render
                const tc = performance.now(), sc = pending;
                pending = null;
                // captured as the Blender look bakes its probes: the sun off, the air off, the outdoors out of it (the
                // sunlit yard and the sky through the door would lie over every reflection in the hall: Blender's
                // probes see the world at its 6% fill), the sky's own domes too
                const domes = [];
                sc.traverse((o) => { if (o.isMesh && o.renderOrder <= -98 && !group.getObjectById(o.id)) domes.push(o); });
                const outs = [...outdoors.filter(Boolean), ...domes], seen = outs.map((o) => o.visible), sunI = sunLight ? sunLight.intensity : 0;
                const bg = [sc.background, sc.backgroundNode];
                sc.backgroundNode = null; sc.background = new T.Color(0, 0, 0);
                outs.forEach((o) => { o.visible = false; });
                if (sunLight) sunLight.intensity = 0.0;
                if (fog) fog.enabled.value = 0.0;
                env.capture(sc, 2, log);
                if (fog) fog.enabled.value = state.haze > 0.5 ? 1.0 : 0.0;
                if (sunLight) sunLight.intensity = sunI;
                outs.forEach((o, i) => { o.visible = seen[i]; });
                [sc.background, sc.backgroundNode] = bg;
                // (what is updated once a frame was updated by the capture's renders: a fresh node frame, its time
                // kept, so this frame's own render takes the capture)
                const nf = R?._nodes?.nodeFrame;
                if (nf) {
                    const [tt, dt] = [nf.time, nf.deltaTime];
                    nf.update(); nf.time = tt; nf.deltaTime = dt;
                    if (R.info) R.info.frame = nf.frameId;                  // (the harness keeps the two in step)
                }
                say(`the hall's reflections captured in ${((performance.now() - tc) / 1000).toFixed(1)} s`);
            }
            return hall;
        },
        // a node's world matrix in three's world (a unit's tray frame line_NN_unit_K, a body mark line_00_mark_K, the
        // station's lead line_NN_lead, sheet_path, gantry_hood_socket, ...)
        mark(name) {
            const n = lay.S.get(name);
            if (!n) throw new Error(`hall: no node ${name}`);
            group.updateMatrixWorld(true);
            return new T.Matrix4().fromArray(lay.S.world(n)).premultiply(group.matrixWorld);
        },
        // one of the Blender edition's lenses on a PerspectiveCamera: place, aim (its frame's top toward the lens' up),
        // the field of view for the camera's aspect (36 mm sensor across the wider side)
        camera(name, cam) {
            const c = cams[name];
            if (!c) throw new Error(`hall: no camera ${name} (${Object.keys(cams).join(', ')})`);
            group.updateMatrixWorld(true);
            const mw = group.matrixWorld;
            cam.position.set(...c.pos).applyMatrix4(mw);
            cam.up.set(...c.up).transformDirection(mw);
            cam.lookAt(new T.Vector3(...c.aim).applyMatrix4(mw));
            const aspect = cam.aspect || 16 / 9;
            const hfov = 2 * Math.atan(18.0 / c.lens);
            cam.fov = (aspect >= 1 ? 2 * Math.atan(Math.tan(hfov / 2) / aspect) : hfov) * 180 / Math.PI;
            cam.near = Math.min(0.1, c.focus * 0.1);
            cam.far = 7000;                                              // (past the sky family's dome, 3200 m out)
            cam.updateProjectionMatrix();
            return cam;
        },
        // the hall's world on a scene and renderer: the sky family's sky through the door (the hall turned to meet its
        // sun), the dock sun and its shadow, AgX as Blender 5.2 draws it, the air, and the hall's reflections captured
        async applyTo(scene, renderer, camera = null) {
            R = renderer;
            const wasIn = group.parent === scene;
            if (wasIn) scene.remove(group);                            // (the weather's wrap must not reach the hall's materials)
            if (look && sky) S = await W.sky(T, { scene, camera, renderer, group, lay, opt: OPT, log });
            else scene.background = new T.Color(...(look ? [0.62, 0.70, 0.80] : [0.74, 0.82, 0.92]));
            scene.add(group);
            MT.setFrame(group);
            if (sunLight) {
                scene.add(sunLight, sunLight.target);
                W.placeSun(T, sunLight, group, lay, { shadows });
                renderer.shadowMap.enabled = shadows || renderer.shadowMap.enabled;
            }
            const SS = await import('../same_seed.js');
            renderer.library.addToneMapping(SS.blenderAgX(T), T.CustomToneMapping);
            renderer.toneMapping = T.CustomToneMapping;
            renderer.toneMappingExposure = Math.pow(2, OPT.exposure);
            if (look) {
                // the hall's reflections and fill (captured below): every hall material's environment, and the CC0
                // fittings' inside it
                // indoors: the capture, the aisle's probe; outdoors (past the walls): the sky at sky_fill and the
                // light from the sunlit things around (W.OUTDOOR, the sun's colour)
                const wt = lay.L.hall.wall_t;
                env = W.interiorEnv(T, group, renderer, {
                    fill: OPT.fill, reflect: OPT.reflect, dielectric: OPT.dielectric, aisle: X.aisleProbe, lamp: balanced(LAMP_K),
                    hall: { lo: [lay.HX0 - wt, lay.HY0 - wt, -1.0], hi: [lay.HX1 + wt, lay.HY1 + wt, lay.L.hall.roof_z + 0.5] },
                    sky: S ? scene.environment : null, skyFill: OPT.sky_fill, sunColour: balanced(SUN_K),
                });
                hall.env = env;
                const own = function () { return env.lighting(); };
                for (const m of [...mats.values(), ...cc0.materials.values()]) {
                    if (!m.isMeshStandardNodeMaterial) continue;
                    m.setupEnvironment = own;
                    W.specularOnlyAware(T, m);
                }
                // the hall's air: a haze of the Blender look's density (0.0012 a metre), lit as the hall's middle grey
                const enabled = T.uniform(1.0), col = T.uniform(new T.Color(0.90 * 0.42, 0.93 * 0.42, 0.97 * 0.42));
                const k = T.float(1.0).sub(T.exp(T.positionView.length().mul(-OPT.haze))).mul(enabled);
                scene.fogNode = T.fog(col, k);
                fog = { enabled, color: col };
            }
            hall.update(0);
            // the reflections are captured at the next update, inside the frame loop (drawn during setup, a scene
            // comes out black on this stack, and a target drawn there leaves the first frame without its canvas)
            if (look && capture && env) pending = scene;
            return hall;
        },
        dispose() {
            group.removeFromParent();
            for (const g of geos.values()) g.dispose();
            MT.dispose();
            if (env) env.dispose();
        },
    };
    report.seconds = +((performance.now() - t0) / 1000).toFixed(1);
    say(`built in ${report.seconds} s`);
    return hall;
}

export { MB };
