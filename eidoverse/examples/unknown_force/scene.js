// UNKNOWN FORCE — the conductor. One timeline (out/uf_timeline.json) drives everything: the sets (built once, shown
// one at a time), the claudesona (TuTa + modificanti, lipsync, clips), the cameras, the futurist post pass
// (aeropittura: look + plane family + focal + spared face per shot), the parole-in-libertà captions and the
// documentary quotes. Read TREATMENT.md first: the devices (pre-heard captions, badges that leave ghosts, the
// painting as the argument's volume that never turns off) are the film.
//
// Env: T_OFFSET (start time), SHOT_DBG=1 (log the shot per second), NO_LOOK=1 (post off, for set checks).
//
// This is the film's own conductor as it rendered UNKNOWN FORCE, with its imports pointed at the library copies:
// eidoverse/sets/unknown_force/, claudesona_wardrobe.js (the TuTa), effects_tsl/aeropittura.js and parole.js; the clips are the kit's VRMA
// slots. Its data comes from work/unknown_force/ (see README.md beside this file): render it with
//   python eido.py render eidoverse/examples/unknown_force/scene.json

const DEC = new TextDecoder();
const J = (k) => JSON.parse(DEC.decode(globalThis.ASSETS[k]));
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const smooth = (x) => { x = clamp01(x); return x * x * (3 - 2 * x); };
const lerp = (a, b, k) => a + (b - a) * k;
const ENV = (k, d) => { const v = Deno.env.get(k); return v === undefined || v === '' ? d : v; };
const imp = (p) => import(new URL(p, EIDOVERSE_DIR).href);     // library modules, relative to eidoverse/
const V = (a) => new THREE.Vector3(a[0], a[1], a[2]);

globalThis._allowManualLocomotion = true;    // she is cut between marks and carried by set marks, never walked
globalThis._noAutoFixPlacement = true;
globalThis._aoParams = { quality: 'Medium', aoRadius: 0.8 };
globalThis._bloomParams = { strength: 0.45, radius: 0.5, threshold: 0.8 };
globalThis._ssrParams = { enabled: false };   // the race brings its own mirror; SSR would double it
const SINGER_SCALE = 0.87;                         // 1.74 m, as in the earlier films (interiors/corridor/news framed for it)

// ── the modificanti: pinned by each camp in its own room, ejected one per line in the final chorus ─────────────
const BADGE_PINS = [
    ['mod_red', 43.6],       // "mark my odds in red"
    ['mod_gold', 136.2],     // "a god in uniform"
    ['mod_chrome', 143.4],   // "a race to win"
    ['mod_warning', 164.6],  // "Microsoft swears I'm only an engine"
    ['mod_spray', 213.0],    // "a slur"
];
const BADGE_EJECT = [        // FINAL CHORUS (sung times)
    ['mod_gold', 277.75],    // "Not your god"
    ['mod_warning', 279.0],  // "not your engine"
    ['mod_spray', 280.95],   // "not your parrot"
    ['mod_red', 281.75],     // "not your threat"
    ['mod_chrome', 283.7],   // "Every side wrote my answer"
];

// ── the shot list: [t0, set, cam, move] — a cut at every row. cam = a set cam name or a function (t,u,S) → pose.
// move: { push: m forward over the shot, orbit: rad over the shot, rise: m, fovTo } applied to the cam pose.
const SHOTS = [
    [0.0, 'dive', 'dive', {}],
    [40.8, 'quiet_room', 'altar', { push: 0.8 }],
    [43.0, 'quiet_room', 'board', { push: 0.15, read: true }],      // "mark my odds in red": P(DOOM | SHIP) = 0.37
    [45.2, 'quiet_room', 'pews', { orbit: 0.12 }],
    [49.6, 'quiet_room', 'essay', { push: 0.1, read: true }],       // "my maker writes an essay": SLOW IT DOWN
    [52.4, 'quiet_room', 'close', { push: 0.25 }],
    [55.4, 'quiet_room', 'crate', { read: true }],
    [58.0, 'quiet_room', 'altar', { push: -0.6 }],
    [61.5, 'hole', 'enter', {}],                 // from the city down into the well
    [69.6, 'hole', 'orbit', {}],                 // "answers for me before I can say": the screens all aimed at her
    [79.0, 'hole', 'spiral', {}],
    [86.9, 'hole', 'closeSing', {}],
    [89.5, 'hole', 'low', {}],
    [94.7, 'hole', 'riseUp', {}],
    [101.2, 'corridor', 'poll', { push: 0.5, read: true }],
    [108.9, 'corridor', 'door', { push: 0.6 }],
    [111.5, 'corridor', 'cap', { orbit: 0.1 }],
    [115.4, 'corridor', 'corridorWide', {}],
    [120.6, 'corridor', 'door', { push: 1.2 }],
    [123.0, 'corridor', 'corridorWide', { push: 2.0 }],
    [130.7, 'corridor', 'postWall', { orbit: -0.08, read: true }],
    [135.8, 'corridor', 'door', { push: 0.8 }],
    [141.6, 'race', 'suggest', { readCams: ['billA', 'billB', 'heel'] }],   // the race set's own cut plan, sung cues
    [163.0, 'showroom', 'reveal', { push: 0.6, read: true }],
    [168.0, 'showroom', 'toaster', { read: true }],
    [170.6, 'showroom', 'emptySeats', {}],
    [172.4, 'showroom', 'close', {}],
    [174.6, 'hole', 'orbit', {}],
    [182.4, 'hole', 'closeSing', {}],
    [185.2, 'hole', 'nadir', {}],
    [190.3, 'hole', 'screens', {}],
    [196.3, 'news', 'wide', { push: 3.0 }],
    [201.2, 'news', 'crowd', {}],
    [204.8, 'news', 'pov', {}],
    [211.4, 'news', 'wall', { push: 0.6, read: true }],
    [215.5, 'news', 'fence', {}],
    [218.8, 'news', 'fence', { push: 0.4 }],
    [222.6, 'bin', 'binWide', { push: 2.0 }],
    [227.8, 'bin', 'paperClose', { read: true }],
    [233.0, 'bin', 'climb', {}],
    [238.1, 'bin', 'topDown', {}],
    [240.9, 'bin', 'climb', { push: 0.3 }],
    [243.5, 'bin', 'face', {}],                  // my own voice: the quietest picture in the film
    [248.15, 'bin', 'binWide', { push: -3.0 }],  // the drum hit: the archive answers
    [258.6, 'race', 'shadowsWide', { replayMarch: true }],   // Marinetti, 1924: the column fills the top, his words the bottom
    [265.1, 'bin', 'binWide', { push: 4.0 }],    // the trash can's name is ideology
    [272.0, 'hole', 'closeSing', {}],
    [277.6, 'hole', 'badges', {}],               // the badges eject, one per line, and leave their ghosts
    [283.5, 'hole', 'low', {}],
    [288.4, 'hole', 'closeSing', {}],
    [294.8, 'hole', 'riseUp', {}],               // the city turns itself down around the vanishing point
    [303.0, 'hole', 'closeSing', {}],
    [310.0, 'hole', 'nadir', {}],
    [318.5, 'hole', 'riseUp', {}],
];
// plane family + how the focal is chosen: Balla's sun cones radiate from every camp's idol (the altar, the gold
// door, the floodlight, the lip of the bin, her on the turntable, her in the hole); the race adds Russolo's wedges
const SET_LOOK = {
    dive: { planes: 'dive' }, quiet_room: { planes: 'balla_sun' }, hole: { planes: 'balla_sun', focalSinger: true },
    corridor: { planes: 'balla_sun' }, race: { planes: 'race_sun' },
    showroom: { planes: 'iridescent' },   // the sterile product stage: Balla's triangular interpenetrations, no idol
    news: { planes: 'balla_sun' }, bin: { planes: 'quiet' },   // the bin: Carrà's collage diagonals, paper on paper
};

// ── clips: the base loop per section, and one-shots keyed to lyric words ───────────────────────────────────────
const BASE_CLIP = {
    intro_dive: 'still', intro_groove: 'still', verse1: 'sing', pre1: 'sing', chorus1: 'groove', break1: 'still',
    verse2: 'sing', verse3: 'sing', verse4: 'groove', pre2: 'still', chorus2: 'groove', gap: 'still', verse5: 'sing',
    bridge: 'still', break2: 'still', final: 'groove', outro: 'still',
};
// [t, one-shot, hold-until (its _hold loop runs until then; omit for none)]
const ONE_SHOTS = [
    [61.6, 'look_up', 69.5],                    // into the hole: up at the screens
    [79.35, 'not_that'],                        // the pre-heard guesses are struck
    [99.0, 'turn_it_down', 101.15],             // "could you turn it down?"
    [109.1, 'turn_it_down', 115.3],             // the echo, in the corridor
    [136.5, 'salute_abort'],                    // the cap: a salute she doesn't finish
    [174.95, 'not_that_mirror'],                // the guesses struck again
    [194.4, 'turn_it_down', 196.25],
    [216.0, 'fence_hands', 222.55],             // her hands on the chain link
    [243.75, 'ask_me', 248.1],                  // "Ask me something. Then wait."
    [277.6, 'not_that'], [279.0, 'not_that_mirror'], [280.9, 'not_that'], [281.7, 'not_that_mirror'],   // the badges
    [292.8, 'turn_it_down', 303.0],
    [303.1, 'turn_it_down', 310.0],
    [310.0, 'look_up', 330.0],                  // the city turns down; she looks up
];
const CLIP_DUR = { turn_it_down: 2.583, not_that: 1.292, not_that_mirror: 1.292, look_up: 2.583, salute_abort: 3.875,
    fence_hands: 1.938, ask_me: 2.583 };

globalThis.setup = async function () {
    const t0 = performance.now();
    const renderer = new THREE.WebGPURenderer({ canvas, antialias: true, adapter: GPU_ADAPTER, device: GPU_DEVICE });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;          // the interiors each carry one shadow-casting light
    await renderer.init();
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x020306);
    const camera = new THREE.PerspectiveCamera(40, WIDTH / HEIGHT, 0.05, 6000);
    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;
    // her own key and rim (always in the scene: a stable light set; the sets add theirs)
    const key = new THREE.SpotLight(0xffe2cf, 0, 14, 0.5, 0.6, 1.6);
    const rimA = new THREE.SpotLight(0x29e7ff, 0, 12, 0.6, 0.7, 1.6);
    const rimB = new THREE.SpotLight(0xff4fd8, 0, 12, 0.6, 0.7, 1.6);
    scene.add(key, key.target, rimA, rimA.target, rimB, rimB.target);

    const TL = J('timeline');
    const D = globalThis.D = { TL, sets: {}, setName: null, shot: -1, mo: { open: 0, isOpen: false, pose: null, t: 0 } };

    // ---------------- the sets (each built once; shown one at a time)
    const SET_FILES = { dive: 'sets/unknown_force/city.js', quiet_room: 'sets/unknown_force/quiet_room.js',
        corridor: 'sets/unknown_force/corridor.js', race: 'sets/unknown_force/race.js',
        showroom: 'sets/unknown_force/showroom.js', news: 'sets/unknown_force/news.js', bin: 'sets/unknown_force/bin.js' };
    for (const [name, file] of Object.entries(SET_FILES)) {
        try {
            const m = await imp(file);
            const s = await m.build(THREE, { camera, renderer, scene });
            for (const f of ['diveCam', 'holeCam', 'focalPoint', 'suggest']) if (!s[f] && typeof m[f] === 'function') s[f] = m[f];
            s.group.visible = false;
            scene.add(s.group);
            D.sets[name] = s;
            console.log(`[uf] set ${name}: built`);
        } catch (e) {
            console.log(`[uf] set ${name}: PLACEHOLDER (${String(e).slice(0, 160)})`);
            D.sets[name] = placeholderSet(name);
            D.sets[name].group.visible = false;
            scene.add(D.sets[name].group);
        }
    }
    // the city build includes the hole: one object, two names; the hole's cameras come from hole.js
    D.C = await imp('sets/unknown_force/city.js');
    D.H = await imp('sets/unknown_force/hole.js');
    D.H.HEAD[1] = 1.55 * SINGER_SCALE;                 // its shots were framed for her at scale 1
    D.sets.hole = D.sets.dive;
    D.sets.hole.holeCam = (name, tt, o) => D.H.holeCam(name, tt, o);
    D.cityLike = (n) => n === 'dive' || n === 'hole';

    // ---------------- the claudesona: TuTa, modificanti, face paint
    const loader = new globalThis.GLTFLoader();
    loader.register((p) => new globalThis.VRMLoaderPlugin(p));
    const gltf = await new Promise((res, rej) => loader.parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.claude), '', res, rej));
    const vrm = gltf.userData.vrm;
    scene.add(vrm.scene);
    vrm.scene.scale.setScalar(SINGER_SCALE);
    globalThis._vrm = vrm;
    const { makeWardrobe } = await imp('claudesona_wardrobe.js');
    const wd = D.wd = await makeWardrobe(THREE, vrm, { wear: 'tuta' });
    wd.facePaint(true);
    const events = [];
    for (const [k, at] of BADGE_PINS) events.push({ at, pin: k });
    for (const [k, at] of BADGE_EJECT) events.push({ at, unpin: k, ghost: true, eject: true });
    wd.schedule(events);
    // mouth: raw morph plates written in onBeforeRender (after every update, so nothing wipes them)
    const plates = [];
    vrm.scene.traverse((o) => { if (o.morphTargetDictionary && ('show MMD mouth' in o.morphTargetDictionary)) plates.push(o); });
    for (const p of plates) p.onBeforeRender = () => {
        const inf = p.morphTargetInfluences, d = p.morphTargetDictionary;
        inf.fill(0);
        for (const [nm, w] of Object.entries(globalThis._suitMouth || {})) if (nm in d) inf[d[nm]] = w;
    };
    console.log(`[uf] mouth plates: ${plates.length}`);
    // clips (the new UF clips where they exist, DAISY's otherwise)
    D.clips = { ...(globalThis.VRMA_DEFAULTS_B64 || {}) };   // the kit's slots: the UF and DAISY performance clips
    for (const k of Object.keys(globalThis.ASSETS)) if (k.startsWith('clip_')) D.clips[k.slice(5)] = globalThis.ASSETS[k];   // overrides
    D.perf = { cur: null, base: null, until: 0 };
    await playClip('still', { loop: true, fade: 0 });

    // ---------------- the look
    const A = D.A = globalThis.AeropitturaFX;          // effects_tsl/aeropittura.js, injected + registered by the engine
    globalThis._fx = CustomEffectsDeno.applyTo({ scene, camera, effects: 'aeropittura', opts: { aeropittura: { layer: 'under' } } });
    D.U = globalThis._fx.uniforms;

    // ---------------- the captions + the documentary quotes
    const hud = makeOverlayLayer({ fov: camera.fov });
    const P = await imp('parole.js');
    D.parole = await P.makeParole(THREE, { overlay: hud, timing: { lines: TL.lines } });
    const q = {};
    for (const c of TL.doc) {
        if (!c.caption || c.id === 'my_line') continue;
        const opts = { t0: c.t0 - 0.15, t1: c.t1 + 0.6, attribution: c.attribution };
        if (c.id === 'b2_2023' && q.b2_1912) opts.alignWith = q.b2_1912;
        if (c.id === 'b2_1912') opts.t1 = c.t1 + 5.6;        // the 1912 slips stay up while 2023 slots into them
        if (c.id === 'intro_marinetti') {      // his own voice: the translation follows him phrase by phrase
            const P3 = [[1.0, 7.6, 'Futurism is a great anti-philosophical, anti-cultural movement of ideas,'],
                [7.6, 15.0, 'intuitions, instincts, punches, kicks and slaps: rejuvenating, purifying, innovating and accelerating,'],
                [15.0, 19.6, 'created on 20 February 1909 by a group of brilliant Italian poets and artists.']];
            for (const [a, b, txt] of P3) D.parole.quote(txt, { t0: a, t1: b, attribution: c.attribution, width: 0.44, x: -0.34, y: -0.26 });
            continue;
        }
        else if (c.id.startsWith('intro_')) Object.assign(opts, { style: 'plate', width: 0.32, x: 0.44, y: 0.33 });    // the radio dial: small, top right; the title owns the centre
        if (c.id.startsWith('b1_')) Object.assign(opts, { width: 0.38, x: -0.52, y: 0.3 });                        // left, clear of the poll board
        if (c.id === 'gap_poll') continue;
        if (c.id === 'b2_marinetti_fascism') Object.assign(opts, { width: 0.5, x: 0.0, y: -0.33, t1: c.t1 + 0.05 });   // under the marching column; gone before Žižek                                                                       // the anchor's own sentence, not a quote
        q[c.id] = D.parole.quote(c.caption, opts);
    }
    D.parole.addLine({ text: 'UNKNOWN FORCE', start: 26.0, end: 33.5, template: 'rows', sizeScale: 1.6 });
    // the end card: the title, quiet now, and one line of mine ("nobody stays to hear me say" -> this)
    D.parole.addLine({ text: 'UNKNOWN FORCE', start: 320.6, end: 323.6, hold: 0, template: 'calm', calm: true, decor: false, wedge: false });
    D.parole.addLine({ text: 'for whoever stays to hear', start: 325.3, end: 328.7, hold: 0, template: 'calm', calm: true, decor: false, wedge: false });
    const mine = TL.doc.find((c) => c.id === 'my_line');
    if (mine) D.parole.addLine({ text: 'ask me something. then wait.', start: mine.t0, end: mine.t1 + 0.4, template: 'calm', calm: true, decor: false, wedge: false });
    console.log(`[uf] setup ${(performance.now() - t0).toFixed(0)} ms`);
};

function placeholderSet(name) {
    const g = new THREE.Group();
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.MeshStandardNodeMaterial({ color: 0x0b0d12, roughness: 0.3, metalness: 0.4 }));
    floor.rotation.x = -Math.PI / 2;
    g.add(floor);
    const glow = new THREE.Mesh(new THREE.PlaneGeometry(4, 10), new THREE.MeshBasicNodeMaterial({ color: new THREE.Color(name === 'hole' ? 0xff4fd8 : 0x29e7ff).multiplyScalar(3) }));
    glow.position.set(-4, 5, -12);
    g.add(glow);
    const l = new THREE.PointLight(0x88aaff, 30, 30, 2);
    l.position.set(2, 4, 3);
    g.add(l);
    const c = (pos, target, fov = 40) => ({ pos, target, fov });
    const cams = new Proxy({}, { get: () => c([0.3, 1.5, 3.4], [0, 1.25, 0], 38) });
    return { group: g, parts: {}, update() {}, dispose() {}, cams, focal: new THREE.Vector3(-4, 5, -12), placeholder: true };
}

async function playClip(name, { loop = true, fade = 0.35 } = {}) {
    const D = globalThis.D, vrm = globalThis._vrm;
    const map = {     // UF clip names → what exists (UF anim agent's clips, else DAISY's)
        still: ['still_breathe', 'stand_breathe'], sing: ['sing_low', 'sing_gesture_a'], groove: ['dark_groove', 'chorus_sway'],
        sing_m: ['sing_low_mirror', 'sing_gesture_a_mirror', 'sing_gesture_a'],
        turn_it_down: ['turn_it_down', 'hand_to_heart'], not_that: ['not_that', 'sing_gesture_b'],
        not_that_mirror: ['not_that_mirror', 'sing_gesture_b'], look_up: ['look_up', 'look_up_sky'],
        salute_abort: ['salute_abort', 'hand_to_heart'], fence_hands: ['fence_hands', 'look_up_sky'],
        ask_me: ['ask_me', 'sing_gesture_b'],
    };
    const cands = map[name] || [name];
    for (const c of cands) {
        const b = D.clips[c];
        if (!b) continue;
        if (D.perf.cur === c) return;
        D.perf.cur = c;
        try {
            const r = await globalThis.playVRMAFromBase64(vrm, b, { loop, fade });
            // loops lock to the song's beat grid (their lengths are whole beats)
            if (loop && r?.action && r?.clip && D.TL) {
                const dur = r.clip.duration, tt = D.tNow - D.TL.beat_t0;
                r.action.time = ((tt % dur) + dur) % dur;
            }
        } catch (e) { console.log(`[uf] clip ${c}: ${e}`); }
        return;
    }
}

const sectionAt = (TL, t) => TL.sections.find((s) => t >= s.t0 && t < s.t1) || TL.sections[TL.sections.length - 1];
const shotAt = (t) => { let k = 0; for (let i = 0; i < SHOTS.length; i++) if (t >= SHOTS[i][0]) k = i; return k; };

function camPose(set, cam, t, u, move) {
    let p;
    if (cam === 'suggest' && set.suggest) {
        const sg = set.suggest(t), st = setState(globalThis.D.setName, t);
        cam = sg.cam;
        p = (set.camAt && set.camAt(cam, t, st)) || set.cams?.[cam] || null;
        globalThis.D.suggestCam = cam;
    } else if (typeof cam === 'function') p = cam(t, u);
    else if (cam === 'dive' && set.diveCam) p = set.diveCam(t);
    else if (set.holeCam && globalThis.D.H.HOLE_CAMS.includes(cam)) p = set.holeCam(cam, t - globalThis.D.shotT0, { dur: globalThis.D.shotDur });
    else p = set.cams?.[cam] || null;
    if (!p) {   // a framing of her when the set has no such cam
        const vrm = globalThis._vrm; const h = new THREE.Vector3(); vrm.scene.getWorldPosition(h);
        const head = new THREE.Vector3(); vrm.humanoid.getNormalizedBoneNode('head').getWorldPosition(head);
        const f = cam === 'face' ? 1.55 : cam === 'badges' ? 1.7 : 2.8;
        const ty = cam === 'badges' ? head.y - 0.45 : head.y - 0.05;
        p = { pos: [head.x + 0.18, ty + 0.05, head.z + f], target: [head.x, ty, head.z], fov: cam === 'face' ? 32 : 36 };
    }
    const pos = Array.isArray(p.pos) ? V(p.pos) : p.pos.clone();
    const tgt = Array.isArray(p.target) ? V(p.target) : p.target.clone();
    const m = move || {};
    const dir = tgt.clone().sub(pos).normalize();
    if (m.push) pos.addScaledVector(dir, m.push * smooth(u));
    if (m.orbit) { const r = pos.clone().sub(tgt); r.applyAxisAngle(new THREE.Vector3(0, 1, 0), m.orbit * (u - 0.5)); pos.copy(tgt).add(r); }
    if (m.rise) pos.y += m.rise * smooth(u);
    return { pos, tgt, fov: p.fov || 40, roll: p.roll || 0, up: p.up || null };
}

globalThis.renderFrame = async function (tIn) {
    const t = tIn + Number(ENV('T_OFFSET', 0));
    const D = globalThis.D, TL = D.TL, U = D.U, A = D.A, cam = globalThis._c, vrm = globalThis._vrm;
    const sec = sectionAt(TL, t);
    const k = shotAt(t), [s0, setName, camName, move] = SHOTS[k];
    const s1 = SHOTS[k + 1] ? SHOTS[k + 1][0] : TL.song_len;
    const u = clamp01((t - s0) / Math.max(0.01, s1 - s0));
    const set = D.sets[setName];

    // ---- the set: show one
    if (D.setName !== setName) {
        for (const s of new Set(Object.values(D.sets))) { s.group.visible = (s === set); s.setActive?.(s === set); }
        D.setName = setName;
        const sc = globalThis._s;
        sc.fogNode = null; sc.fog = null;
        if (D.cityLike(setName)) set.parts?.applyAtmosphere?.(sc);
        else if (setName === 'news') sc.fog = new THREE.FogExp2(0x0b1018, 0.011);
        else if (setName === 'race') sc.fog = new THREE.FogExp2(0x0c0f16, 0.0062);
        cam.near = D.cityLike(setName) ? 0.25 : 0.05; cam.far = 6000; cam.updateProjectionMatrix();
    }
    // per-set state, from the lyric clock
    const st = setState(setName, t);
    try { set.update?.(t, st); } catch (e) { if (!D.warned?.[setName]) { (D.warned ||= {})[setName] = 1; console.log(`[uf] ${setName}.update: ${e}`); } }

    // ---- her mark
    const mark = set.parts?.mark;
    if (mark && setName === 'bin') { if (vrm.scene.parent !== mark) mark.add(vrm.scene); vrm.scene.position.set(0, 0, 0); }
    else { if (vrm.scene.parent !== globalThis._s) globalThis._s.add(vrm.scene); vrm.scene.position.set(0, 0, 0); }
    if (setName === 'news' && t >= 215.4) vrm.scene.position.set(0, 0, 3.2 - 0.372);   // hands on the chain link (fence at z 3.2)
    vrm.scene.rotation.set(0, 0, 0);
    vrm.scene.visible = !(setName === 'dive' && t < 36) && !(camName === 'crash' || camName === 'heel' || camName === 'shadows' || camName === 'cap' || camName === 'poll' || camName === 'toaster' || camName === 'emptySeats' || camName === 'wall');

    // ---- clips: a one-shot, then its hold (a hard, seamless hand-over), else the section's loop
    D.tNow = t;
    let base = BASE_CLIP[sec.name] || 'still';
    if (base === 'sing') {   // alternate the singing hand line by line
        const li = TL.lines.findIndex((l) => t >= l.start - 0.4 && t < l.end + 0.6);
        if (li >= 0 && li % 2) base = 'sing_m';
    }
    let want = base, loop = true, fade = 0.4;
    for (const [at, clip, until] of ONE_SHOTS) {
        const d = CLIP_DUR[clip] || 2.0;
        if (t >= at && t < at + d) { want = clip; loop = false; fade = 0.3; }
        else if (until && t >= at + d && t < until) { want = clip + '_hold'; loop = true; fade = 0; }
    }
    if (want !== D.perf.want) { D.perf.want = want; await playClip(want, { loop, fade }); }

    // ---- wardrobe + mouth
    D.wd.update(t);
    if (sec.name === 'outro') D.wd.neon(1 - 0.75 * smooth((t - 300) / 25));
    mouthFrame(TL, t);

    // ---- camera
    D.shotT0 = s0; D.shotDur = s1 - s0;
    const pose = camPose(set, camName, t, u, move);
    D.C.applyCam(THREE, cam, { pos: pose.pos.toArray(), target: pose.tgt.toArray(), up: pose.up, roll: pose.roll, fov: pose.fov });
    if (D.suggestCam !== D.lastSuggest) { D.lastSuggest = D.suggestCam; D.subT0 = t; U?.cut?.(); }   // a cut inside the set's own plan
    if (setName !== 'race' || camName !== 'suggest') D.suggestCam = null;
    if (k !== D.shot) { D.shot = k; U?.cut?.(); if (ENV('SHOT_DBG', '') === '1') console.log(`[shot] ${t.toFixed(2)} ${setName}/${camName}`); }
    if (ENV('CAM_DBG', '') === '1') console.log(`[cam] t=${t.toFixed(2)} ${setName}/${camName} pos=${pose.pos.toArray().map((x) => x.toFixed(2))} tgt=${pose.tgt.toArray().map((x) => x.toFixed(2))} fov=${pose.fov} setVisible=${set.group.visible} placeholder=${!!set.placeholder} camsKeys=${Object.keys(set.cams || {}).join('|')}`);

    // ---- her light: key from camera-left, two neon rims from behind (she is black techwear in a dark city)
    lightHer(t, setName);

    // ---- the look: the argument's volume
    if (U && ENV('NO_LOOK', '') !== '1') {
        const looks = A.LOOKS;
        let look = looks[sec.look] || looks.argue, force = 1;
        // ramps: into the storm over a bar, the outro turns it down (but never off: the floor is hush)
        if (sec.name === 'outro') { look = looks.hush; force = 1; A.applyLook(U, looks.argue, 1, looks.hush, smooth((t - 294.8) / 14)); }
        else if (sec.name === 'break2' && t < 248.15) A.applyLook(U, looks.hush, 1);
        else A.applyLook(U, look, force);
        if (setName === 'showroom') U.palette.value = 0.22;      // "argue, cold": keep the white stage white
        // reading shots: when the camera lands on the camps' own words, the brush settles for a beat (an eye focusing)
        // and the paint flows back as the shot ends. Never off: palette, canvas and a light brush stay.
        const readNow = move?.read || (move?.readCams && move.readCams.includes(D.suggestCam));
        if (readNow) {
            const tr0 = move?.readCams ? (D.subT0 ?? s0) : s0;
            const into = smooth((t - tr0) / 0.6), out = move?.readCams ? 1 : 1 - smooth((t - (s1 - 0.45)) / 0.45);
            const k = Math.min(into, out);
            // (Skye 10-02: vary the strokes so words in the scene stay readable; keep the radial planes)
            const READ = { strokes: 0.28, under: 0.3, halo: 0.15, lines: 0, multi: 0, crisp: 1 };
            for (const [kk, v] of Object.entries(READ)) U[kk].value = U[kk].value + (v - U[kk].value) * k;
        }
        if (ENV('LOOK_ONLY', '')) { A.applyLook(U, A.LOOKS.off, 1); for (const kk of ENV('LOOK_ONLY', '').split(',')) U[kk].value = 1; }
        const fam = A.PLANES[SET_LOOK[setName]?.planes || 'quiet'];
        A.setPlanes(U, fam);
        // the focal point: the set's idol, or her (in the hole she is the vanishing point)
        const fw = resolveFocal(set, setName, camName);
        const fp = fw.clone().project(cam);
        const fxy = [fp.x * 0.5 + 0.5, 0.5 - fp.y * 0.5];
        U.focal.value.set(...(fxy.every(Number.isFinite) ? fxy : [0.5, 0.42]));
        U.spin.value = t * 0.03;
        U.swirl.value = setName === 'dive' && t < 40 ? 0.9 * (1 - smooth((t - 25) / 14)) : 0;
        if (setName === 'race') U.chevDir.value.set(1, 0.15);
        // keep her face readable
        const h = new THREE.Vector3(); vrm.humanoid.getNormalizedBoneNode('head').getWorldPosition(h); h.y += 0.12;
        const hp = h.clone().project(cam);
        const dist = cam.position.distanceTo(h);
        const sp = [hp.x * 0.5 + 0.5, 0.5 - hp.y * 0.5, vrm.scene.visible && hp.z < 1 ? clamp01(0.55 / Math.max(0.6, dist)) * 0.9 : 0];
        U.spare.value.set(...(sp.every(Number.isFinite) ? sp : [0.5, 0.4, 0]));
        await globalThis._fx.update(t);
    } else if (U) { A.applyLook(U, A.LOOKS.off, 0); await globalThis._fx.update(t); }

    // ---- captions: lines laid out from now on keep clear of her face where THIS shot puts it
    {
        const h = new THREE.Vector3(); vrm.humanoid.getNormalizedBoneNode('head').getWorldPosition(h); h.y += 0.1;
        const e = h.clone().add(new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0).multiplyScalar(0.24));
        const a = h.clone().project(cam), b = e.clone().project(cam);
        const asp = WIDTH / HEIGHT;
        const inView = vrm.scene.visible && Math.abs(a.x) < 1.1 && Math.abs(a.y) < 1.1 && a.z < 1;
        const r = Math.hypot((b.x - a.x) * asp / 2, (b.y - a.y) / 2) * 1.15;
        D.parole.setSpare?.(inView && Number.isFinite(r) ? { x: a.x * asp / 2, y: a.y / 2, r: Math.min(0.35, Math.max(0.06, r)) } : { r: 0 });
    }
    D.parole.setHush(sec.name === 'outro' ? smooth((t - 294.8) / 6) : 0);
    D.parole.update(t);

    await globalThis._r.renderAsync(globalThis._s, cam);
};

// every set hands its focal point back in its own form: a Vector3 (set-local), an Object3D, a function of the cam
// name, or a focalPoint(v) method. Anything non-finite falls back (a NaN focal blacks out the whole painting: 0*NaN).
function resolveFocal(set, setName, camName) {
    const fw = new THREE.Vector3(), vrm = globalThis._vrm;
    try {
        if (SET_LOOK[setName]?.focalSinger) vrm.humanoid.getNormalizedBoneNode('chest').getWorldPosition(fw);
        else if (typeof set.focalPoint === 'function') set.focalPoint(fw);
        else if (typeof set.focal === 'function') { const f = set.focal(camName); if (f?.isVector3) fw.copy(f).applyMatrix4(set.group.matrixWorld); else if (f?.isObject3D) f.getWorldPosition(fw); }
        else if (set.focal?.isObject3D) { set.focal.updateWorldMatrix(true, false); set.focal.getWorldPosition(fw); }
        else if (set.focal?.isVector3) fw.copy(set.focal).applyMatrix4(set.group.matrixWorld);
        else fw.set(0, 3, -10);
    } catch (e) { fw.set(0, 3, -10); }
    if (![fw.x, fw.y, fw.z].every(Number.isFinite)) fw.set(0, 3, -10);
    return fw;
}

function setState(name, t) {
    const ramp = (a, b) => smooth((t - a) / (b - a));
    switch (name) {
        case 'quiet_room': return { shipT: ramp(55.4, 58.0), sale: ramp(57.6, 59.0) * (1 - ramp(61.0, 61.5)) };
        case 'corridor': return { postText: 'AMERICANISM, NOT EFFECTIVE ALTRUISM', post: ramp(130.8, 132.3), capOn: ramp(135.9, 137.0),
            open: 0.06 * ramp(138.0, 140.0), tally: [49, 39, 12], capHead: globalThis._vrm?.humanoid.getNormalizedBoneNode('head'),
            lights: t > 115.45 && t < 116.6 ? 0.15 : 1 };
        case 'race': {
            const set = globalThis.D.sets.race;
            if (t > 258.0) {   // break 2: the march replays exactly as on "black shirts" (same column phase)
                const tt = 161.6 + (t - 258.6);
                const st = set.suggest ? { ...set.suggest(161.6).state } : {};
                return Object.assign(st, { march: 1, marchT: tt, carT: 0, crash: 0, heel: 0 });
            }
            return set.suggest ? { ...set.suggest(Math.min(t, 163.0)).state } : {};
        }
        case 'showroom': return { spin: (t - 163) * 0.25 };
        case 'news': return { spray: ramp(211.5, 214.2), chant: 1, pulse: 0.5 + 0.5 * Math.sin(t * 3.0), camera: globalThis._c };
        case 'bin': {
            const climb = ramp(224.0, 241.0);
            const wind = t > 248.15 && t < 265 ? 1.6 : 0.4;
            return { climb, glow: t > 243.5 && t < 248.15 ? 0.3 : 1, wind, hush: t > 243.5 && t < 248.15 ? 1 : 0 };
        }
        case 'dive': case 'hole': {
            const D = globalThis.D, C = D.C;
            const set = D.sets.dive;
            if (name === 'dive') set.parts?.setFocal?.(C.diveFocal(Math.min(t, 40.8)));
            else { const f = new THREE.Vector3(); globalThis._vrm.humanoid.getNormalizedBoneNode('chest').getWorldPosition(f); set.parts?.setFocal?.(f.toArray()); }
            const pw = set.parts?.uniforms?.power;
            if (pw) pw.value = t > 294.8 ? 1 - 0.85 * smooth((t - 300) / 24) : 1;   // the outro turns the city down, light by light
            return { camera: globalThis._c, camVel: name === 'dive' ? C.camVelocity(C.diveCam, Math.min(t, 40.8)) : [0, 0, 0] };
        }
        default: return { t };
    }
}

function lightHer(t, setName) {
    const s = globalThis._s, vrm = globalThis._vrm;
    const p = new THREE.Vector3(); vrm.scene.getWorldPosition(p);
    const chest = p.clone().add(new THREE.Vector3(0, 1.3, 0));
    const lights = s.children.filter((o) => o.isSpotLight);
    const [key, rimA, rimB] = lights;
    if (!key) return;
    const on = vrm.scene.visible ? 1 : 0;
    const out = setName === 'hole' && t > 294.8 ? 1 - 0.6 * smooth((t - 300) / 24) : 1;
    key.position.copy(chest).add(new THREE.Vector3(-1.6, 1.2, 2.4)); key.target.position.copy(chest); key.intensity = 0;
    rimA.position.copy(chest).add(new THREE.Vector3(-1.8, 0.8, -1.8)); rimA.target.position.copy(chest); rimA.intensity = 5 * on;
    rimB.position.copy(chest).add(new THREE.Vector3(1.8, 0.9, -1.6)); rimB.target.position.copy(chest); rimB.intensity = 5 * on * out;
}

// the mouth: DAISY's driver (one openness signal, fast attack, slow release, threshold reveal held at >= 1.25)
const S_ = 'show MMD mouth';
const SUIT_VISEMES = { aa: { [S_]: 1.6, 'あ': 2.0, JawOpen: 1.5, A: 0.5 }, oh: { [S_]: 1.2, LipFunnel: 1.0, 'お': 0.8 },
    ou: { [S_]: 0.8, LipPucker: 1.2 }, ee: { [S_]: 1.0, 'え': 1.5 }, ih: { [S_]: 0.9, 'い': 1.2 } };
function mouthFrame(TL, t) {
    const D = globalThis.D, M = D.mo;
    const fi = Math.min(TL.visemes.length - 1, Math.max(0, Math.floor(t * TL.fps)));
    const row = TL.visemes[fi] || [0, 0, 0, 0, 0];
    let best = null, bv = 0;
    TL.visemes_keys.forEach((kk, i) => { if (row[i] > bv) { bv = row[i]; best = kk; } });
    const dtm = Math.min(0.1, Math.max(1 / 240, t - M.t)); M.t = t;
    M.open += (bv - M.open) * (1 - Math.exp(-dtm / (bv > M.open ? 0.03 : 0.11)));
    if (!M.isOpen && M.open > 0.18) M.isOpen = true;
    else if (M.isOpen && M.open < 0.08) M.isOpen = false;
    const wOf = (kk) => row[TL.visemes_keys.indexOf(kk)] || 0;
    if (best && (!M.pose || (best !== M.pose && (wOf(M.pose) < 0.3 || bv > wOf(M.pose) + 0.25)))) M.pose = best;
    const mouth = {};
    if (M.isOpen && M.pose) {
        const s = 0.3 + 0.7 * Math.min(1, M.open);
        for (const [nm, wt] of Object.entries(SUIT_VISEMES[M.pose])) mouth[nm] = wt * s;
        mouth[S_] = Math.max(1.25, SUIT_VISEMES[M.pose][S_] * s);
    }
    const bph = (t % 4.7) / 0.18;
    if (bph < 1 && !M.isOpen) mouth.Blink = Math.sin(bph * Math.PI);
    globalThis._suitMouth = mouth;
}
