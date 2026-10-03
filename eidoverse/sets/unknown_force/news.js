// news.js — UNKNOWN FORCE, VERSE 5 (song 201.3–222.2 s)
//   "On the evening news they're picketing my body / They want me in their pocket, just not built in their town /
//    And the kids made up a slur, but you only need a slur / For a someone — so who's the someone you're keeping down?"
// A hyperscale data centre at night: a long windowless monolith, condenser rows and cooling towers on the roof with
// steam plumes, a transformer yard, security floodlights on poles (the focal light), a chain-link fence with barbed
// wire between her side and the protest side. The pickets are featureless silhouettes (the DAISY funeral's crowd
// figures, instanced) with handwritten signs, phones and flashlights; a news van and its light; the small town across
// the road. CLANKER is sprayed on the monolith's wall (state.spray paints it on). A generic news chyron is supplied
// for the conductor's screen-locked overlay.
//
//   const N = await (await import(new URL('sets/unknown_force/news.js', EIDOVERSE_DIR).href)).build(THREE);
//   scene.add(N.group); scene.fog = new THREE.FogExp2(N.look.fog.color, N.look.fog.density);
//   N.parts.chyron.place(makeOverlayLayer({ fov: camera.fov }), { fov: camera.fov, aspect: WIDTH / HEIGHT });
//   // per frame: N.update(t, { spray, chant, pulse, floods })
//
// Set-local metres, +Y up, ground y = 0. Her mark is the origin facing +Z (toward the fence and the protesters);
// the monolith's wall is 12 m behind her. Everything is deterministic in t. No real logos, seals, people or faces.


const FZ = 3.2;                       // the fence line
const FH = 3.0;                       // chain-link height
const FX0 = -62, FX1 = 62;            // the fence runs along x
const POLES = [[-24, -6.5], [-12.5, -6.5], [-3.9, -6.5], [18.5, -6.5]];
const POLE_H = 7.4;
const TILT = 0.5;                    // the flood heads look down this far (rad)
const FLOOD_ANGLE = 0.56, FLOOD_PEN = 0.45, FLOOD_I = 4200, FLOOD_REAL = 850;
const FACADE_Z = -12.0, BX0 = -70, BX1 = 46, BH = 15.0, BD = 48;
const GRAFF = { x0: 1.2, x1: 15.2, y0: 0.6, y1: 4.1 };
const ROAD = { z0: 5.4, z1: 15.0 }, WALK = { z0: 15.0, z1: 17.6 };
const STREET = [[-26, 16.9], [4, 16.9], [34, 16.9]];
const WALLPACKS = [-62, -50, -38, -26, -14, -2, 8, 20, 34];
const WP_Y = 8.2;
const VENTS = [[-11.5, -10.7], [16.5, -10.9]];
const TOWERS = [[-46, -26], [-24, -33], [-2, -24], [24, -35]];
const YARD = { x0: 22, x1: 42, z0: -11.2, z1: -1.6 };
const VAN = [-12.5, 12.2];
const NEWS_LIGHT = [-3.8, 2.6, 8.4];
const SODIUM = [1.0, 0.56, 0.2], HMI = [0.86, 0.92, 1.0];

export const NEWS = { FZ, FH, POLES, POLE_H, FACADE_Z, GRAFF, ROAD, WALK, STREET, VAN, NEWS_LIGHT };

export async function build(THREE, opts = {}) {
    const T = THREE;
    const here = new URL('./', import.meta.url);
    const { makeLib, fitText } = await import(new URL('cn_lib.js', here).href);
    const L = await makeLib(T, here);
    const {
        uniform, Fn, vec2, vec3, vec4, float, uv, texture, mix, step, smoothstep, clamp, max, min, abs, sin, cos, atan,
        fract, floor, pow, exp, sqrt, length, dot, normalize, cross, positionLocal, positionWorld, normalWorld, cameraPosition,
        normalMap, select, mrt, attribute, varying, mx_noise_float, mx_fractal_noise_float, fwidth, instanceIndex,
        positionGeometry, normalGeometry, cameraViewMatrix, modelWorldMatrix, lights: lightsFn,
    } = T;
    const { own, hex, lum, hash21 } = L;
    const fam = L.fam;
    const ss = (a, b, x) => (typeof a === 'number' && typeof b === 'number' && a > b) ? float(1).sub(smoothstep(b, a, x)) : smoothstep(a, b, x);
    const group = new T.Group();
    group.name = 'set:news';
    const noMRT = (m) => { m.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) }); return m; };

    const U = {
        t: uniform(0), spray: uniform(1), floods: uniform(1), lights: uniform(1), chant: uniform(1), pulse: uniform(0),
        groupInv: uniform(new T.Matrix4()), blink: uniform(1),
    };
    // set-space position / camera for any mesh in the set (the group may be parked anywhere)
    const setP = () => U.groupInv.mul(vec4(positionWorld, 1.0)).xyz;
    const setCam = () => U.groupInv.mul(vec4(cameraPosition, 1.0)).xyz;
    const setN = () => normalize(U.groupInv.mul(vec4(normalWorld, 0.0)).xyz);

    // ─────────────────────────── texture sets (CC0, AmbientCG: the shared library, fetched once on first use) ───────────────────────────
    const S = {
        asphalt: await L.pbr('Asphalt025C', { res: '2k', ao: true, disp: true }),
        gravel: await L.pbr('Gravel041', { ao: true }),
        card: await L.pbr('Cardboard002'),
        conc: await L.pbr('Concrete048', { ao: true }),
        concD: await L.pbr('Concrete033', { ao: true }),
        concL: await L.pbr('Concrete034', { res: '2k' }),
        galv: await L.pbr('Metal049A', { met: true }),
        paint: await L.pbr('PaintedMetal012', { ao: true }),
        corr: await L.pbr('CorrugatedSteel009', { res: '2k', ao: true }),
        shingle: await L.pbr('Asphalt012'),
        grass: await L.pbr('Ground037', { res: '2k', ao: true }),
        mud: await L.pbr('Ground106', { res: '2k', ao: true }),
        siding: await L.pbr('PaintedWood009C', { res: '2k', ao: true }),
    };

    // a night environment for the metals: cold sky, sodium glow at the horizon, the floods' glare toward −Z
    const env = L.envTex(([x, y, z]) => {
        const up = Math.max(0, y), dn = Math.max(0, -y);
        let r = 0.004 + 0.012 * Math.exp(-up * 6), g = 0.006 + 0.014 * Math.exp(-up * 6), b = 0.011 + 0.02 * Math.exp(-up * 5);
        const hz = Math.exp(-Math.abs(y) * 9);
        r += 0.06 * hz; g += 0.034 * hz; b += 0.014 * hz;
        const fl = Math.pow(Math.max(0, -z), 12) * Math.exp(-(y - 0.25) * (y - 0.25) * 14);
        r += 0.9 * fl; g += 0.95 * fl; b += 1.0 * fl;
        r += 0.01 * dn; g += 0.01 * dn; b += 0.012 * dn;
        return [r, g, b];
    }, 256, 128);

    // ─────────────────────────── the floods, as analytic light (with the fence's shadow) ───────────────────────────
    const FL = POLES.map(([x, z]) => ({ p: [x, POLE_H, z], d: [0, -Math.sin(TILT), Math.cos(TILT)] }));
    const cosOut = Math.cos(FLOOD_ANGLE), cosIn = Math.cos(FLOOD_ANGLE * (1 - FLOOD_PEN));
    // chain link: 5.5 cm diamonds of 3.6 mm galvanised wire; soft = edge softness in cell units
    const CELL = 0.0354, WN = 0.035;
    const chain = (x, y, soft, wn = WN) => {
        const u = x.div(CELL), v = y.div(CELL);
        const a = abs(fract(u.add(v).mul(0.5)).sub(0.5)), b = abs(fract(u.sub(v).mul(0.5)).sub(0.5));
        const line = (d) => smoothstep(float(0.5 - wn).sub(soft), float(0.5 - wn).add(soft), d);
        return max(line(a), line(b));
    };
    // how much of flood f reaches P through the fence (1 = clear); only points beyond the fence are shaded
    const fenceOcc = (P, f) => {
        const Lp = vec3(...f.p);
        const dz = P.z.sub(f.p[2]);
        const s = float(FZ - f.p[2]).div(max(dz, 1e-3));
        const I = Lp.add(P.sub(Lp).mul(s));
        const crosses = step(FZ + 0.02, P.z);
        const inMesh = step(0.05, I.y).mul(step(I.y, FH));
        const blur = clamp(float(1).sub(s).div(max(s, 0.05)).mul(0.012 / CELL), 0.02, 0.5);
        const wire = chain(I.x, I.y, blur, 0.075);
        const postD = abs(fract(I.x.div(3.0).add(0.5)).sub(0.5)).mul(3.0);
        const post = float(1).sub(smoothstep(0.04, float(0.06).add(blur.mul(0.1)), postD)).mul(step(I.y, FH + 0.6));
        const rail = float(1).sub(smoothstep(0.03, float(0.05).add(blur.mul(0.1)), abs(I.y.sub(FH))));
        return float(1).sub(crosses.mul(max(inMesh.mul(wire).mul(0.92), max(post, rail).mul(0.95))));
    };
    // flood irradiance at P (set space) with normal N (null = omnidirectional), × U.floods
    const floodAt = (P, N, shade = true) => {
        let acc = float(0);
        for (const f of FL) {
            const Lv = vec3(...f.p).sub(P);
            const d2 = max(dot(Lv, Lv), 0.25);
            const Ld = Lv.div(sqrt(d2));
            const cosA = dot(Ld.negate(), vec3(...f.d));
            const cone = smoothstep(cosOut, cosIn, cosA);
            const ndl = N ? max(dot(N, Ld), 0) : float(0.6);
            const occ = shade ? fenceOcc(P, f) : float(1);
            acc = acc.add(cone.mul(ndl).mul(occ).div(d2));
        }
        return acc.mul(FLOOD_I).mul(U.floods).mul(U.lights);
    };
    // wet-ground streak reflection of a light at Lpos seen from cam through P (set space)
    const streak = (P, V, Lpos, sa, se) => {
        const R = vec3(V.x, V.y.negate(), V.z);
        const D = normalize(vec3(...Lpos).sub(P));
        const rl = max(length(vec2(R.x, R.z)).mul(length(vec2(D.x, D.z))), 1e-4);
        const sinAz = R.x.mul(D.z).sub(R.z.mul(D.x)).div(rl);
        const dEl = R.y.sub(D.y);
        const facing = step(0.0, R.x.mul(D.x).add(R.z.mul(D.z)));
        return exp(sinAz.mul(sinAz).div(-sa * sa).sub(dEl.mul(dEl).div(se * se))).mul(facing);
    };
    const EMIT = [
        ...FL.map((f) => ({ p: f.p, c: HMI, k: 5.0, flood: f })),
        ...STREET.map(([x, z]) => ({ p: [x - 0.0, 8.6, z - 1.9], c: SODIUM, k: 2.2 })),
        ...WALLPACKS.map((x) => ({ p: [x, WP_Y, FACADE_Z + 0.35], c: SODIUM, k: 1.0 })),
        { p: NEWS_LIGHT, c: [0.9, 0.95, 1.0], k: 1.6 },
    ];

    // the real lights the analytic-lit materials still take (the floods are painted on them, with the fence's shadow)
    const Ls = {};
    const lightsGroup = new T.Group(); lightsGroup.name = 'news_lights'; group.add(lightsGroup);
    const spot = (col, I, pos, tgt, angle, pen) => {
        const l = new T.SpotLight(col, I, 0, angle, pen, 2);
        l.position.set(...pos); l.target.position.set(...tgt);
        lightsGroup.add(l, l.target);
        l.userData.base = I;
        return l;
    };
    Ls.floods = FL.map((f, i) => spot(0xe2ebff, FLOOD_REAL, f.p, [f.p[0] + f.d[0] * 10, f.p[1] + f.d[1] * 10, f.p[2] + f.d[2] * 10], FLOOD_ANGLE, FLOOD_PEN));
    Ls.street = STREET.map(([x, z]) => spot(0xff9a42, 520, [x, 8.55, z - 1.9], [x, 0, z - 2.6], 0.95, 0.55));
    Ls.news = spot(0xe8f0ff, 150, NEWS_LIGHT, [0, 1.45, 0], 0.32, 0.6);
    Ls.graffiti = spot(0xff9e50, 380, [8.0, WP_Y, FACADE_Z + 0.6], [8.2, 1.8, FACADE_Z], 0.8, 0.6);
    Ls.hemi = new T.HemisphereLight(0x22324a, 0x0a0806, 0.09); Ls.hemi.userData.base = 0.09; lightsGroup.add(Ls.hemi);
    const softLights = lightsFn([...Ls.street, Ls.news, Ls.graffiti, Ls.hemi]);

    // ─────────────────────────── the ground: compound yard, verge, road, sidewalk, lawns ───────────────────────────
    const M = {};
    M.ground = (() => {
        const m = own(new T.MeshStandardNodeMaterial());
        m.name = 'news_ground';
        const P = setP();
        const xz = vec2(P.x, P.z);
        // nine texture samples in all (WebGPU allows sixteen per stage): the asphalt's full set, gravel's colour and
        // normal, and colour only for the concrete, the mud and the lawn (they borrow the asphalt's grain)
        const at = (tx, tile) => texture(tx, xz.div(tile));
        const asp = { c: at(S.asphalt.col, 3.2).rgb, r: at(S.asphalt.rgh, 3.2).r, n: at(S.asphalt.nrm, 3.2) };
        const grv = { c: at(S.gravel.col, 1.6).rgb, n: at(S.gravel.nrm, 1.6) };
        const cl = { c: at(S.concL.col, 2.2).rgb }, mud = { c: at(S.mud.col, 2.6).rgb }, grs = { c: at(S.grass.col, 2.8).rgb };
        const cd = { c: cl.c.mul(0.7) };
        const mac = mx_fractal_noise_float(vec3(P.x.mul(0.07), 0, P.z.mul(0.07)), 3, 2.0, 0.5);
        const z = P.z, x = P.x;
        const inYard = step(YARD.x0, x).mul(step(x, YARD.x1)).mul(step(YARD.z0, z)).mul(step(z, YARD.z1));
        const apron = step(z, FACADE_Z + 1.6);
        const footing = step(FZ - 0.35, z).mul(step(z, FZ + 0.35));
        const verge = step(FZ + 0.35, z).mul(step(z, ROAD.z0));
        const road = step(ROAD.z0, z).mul(step(z, ROAD.z1));
        const walk = step(WALK.z0, z).mul(step(z, WALK.z1));
        const lawn = step(WALK.z1, z);
        const yardAsph = float(1).sub(max(inYard, max(apron, footing))).mul(step(z, FZ - 0.35));
        const asphalt = max(yardAsph, road);
        // the asphalt's low spots hold water; the road's crown sheds it toward the gutters
        const disp = texture(S.asphalt.disp, xz.div(3.2)).r;
        const big = mx_fractal_noise_float(vec3(P.x.mul(0.18), 3.1, P.z.mul(0.18)), 3, 2.0, 0.5);
        const puddle = ss(0.12, 0.3, big.mul(0.5).add(float(0.45).sub(disp))).mul(asphalt);
        // markings on the road: faded edge lines and a dashed centre line
        const edgeL = ss(0.07, 0.05, abs(z.sub(ROAD.z0 + 0.35))).add(ss(0.07, 0.05, abs(z.sub(ROAD.z1 - 0.35))));
        const centre = ss(0.07, 0.05, abs(z.sub((ROAD.z0 + ROAD.z1) / 2))).mul(step(0.5, fract(x.div(6.0))));
        const wear = ss(-0.2, 0.5, mx_noise_float(vec3(x.mul(1.3), 7, z.mul(1.3))));
        const paintW = clamp(edgeL, 0, 1).mul(wear).mul(road);
        const paintY = clamp(centre, 0, 1).mul(wear).mul(road);
        let col = asp.c.mul(0.62);
        col = mix(col, cd.c.mul(0.55), max(apron, footing));
        col = mix(col, grv.c.mul(0.5), inYard);
        col = mix(col, mix(mud.c, grv.c, 0.35).mul(0.42), verge);
        col = mix(col, cl.c.mul(0.5), walk);
        col = mix(col, grs.c.mul(0.32), lawn);
        col = col.mul(mac.mul(0.25).add(1.0));
        // sidewalk joints every 1.5 m
        const joint = ss(0.012, 0.004, abs(fract(x.div(1.5)).sub(0.5)).sub(0.49).abs()).mul(walk);
        col = col.mul(float(1).sub(joint.mul(0.5)));
        col = mix(col, vec3(0.62, 0.62, 0.58), paintW.mul(0.8));
        col = mix(col, vec3(0.62, 0.46, 0.12), paintY.mul(0.8));
        col = mix(col, col.mul(0.45), puddle);
        let rough = asp.r.mul(0.5).add(0.18);                           // wet asphalt
        rough = mix(rough, asp.r.mul(0.4).add(0.34), max(apron, footing));
        rough = mix(rough, float(0.85), max(inYard, verge));
        rough = mix(rough, asp.r.mul(0.3).add(0.45), walk);
        rough = mix(rough, float(0.95), lawn);
        rough = mix(rough, float(0.04), puddle);
        m.colorNode = col;
        m.roughnessNode = clamp(rough, 0.03, 1);
        m.metalnessNode = float(0);
        let nrm = asp.n;
        nrm = mix(nrm, grv.n, max(inYard, max(verge, lawn)));
        nrm = mix(nrm, vec4(0.5, 0.5, 1, 1), puddle);
        m.normalNode = normalMap(nrm, vec2(0.8, 0.8));
        // the floods, painted with the chain link's shadow; then the wet streaks of every light toward the camera
        const flood = floodAt(P, vec3(0, 1, 0)).mul(1 / Math.PI);
        const cam = setCam();
        const V = normalize(P.sub(cam));
        const cosv = clamp(V.y.negate(), 0, 1);
        const F = float(0.02).add(pow(float(1).sub(cosv), 5).mul(0.98));
        const wet = max(asphalt.mul(0.75), max(apron, footing).mul(0.4)).add(puddle.mul(1.2)).add(walk.mul(0.25));
        let refl = vec3(0);
        for (const e of EMIT) {
            const sa = 0.012, se = 0.16;
            let k = streak(P, V, e.p, sa, se).mul(e.k);
            if (e.flood) {
                const R = vec3(V.x, V.y.negate(), V.z);
                k = k.mul(smoothstep(cosOut - 0.25, cosIn, dot(R.negate(), vec3(...e.flood.d)))).mul(U.floods);
            }
            refl = refl.add(vec3(...e.c).mul(k));
        }
        refl = refl.add(vec3(...SODIUM).mul(streak(P, V, [8.0, WP_Y, FACADE_Z + 0.35], 0.02, 0.25).mul(0.5)));
        m.emissiveNode = col.mul(flood).add(refl.mul(F.mul(0.6).add(0.03)).mul(wet).mul(U.lights));
        m.lightsNode = softLights;
        m.envMap = env; m.envMapIntensity = 0.8;
        return m;
    })();
    const ground = new T.Mesh(own(new T.PlaneGeometry(260, 190)), M.ground);
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(-5, 0, 18);
    ground.name = 'news_ground';
    ground.receiveShadow = true;
    group.add(ground);

    // ─────────────────────────── surfaces ───────────────────────────
    const pm = (S_, o) => L.pbrMat(S_, { env, envI: 0.7, ...o });
    M.galv = pm(S.galv, { name: 'news_galv', tile: 0.8, metal: 0.85, rough: [0.6, 0.25], tint: [0.55, 0.57, 0.6], macro: 0.3 });
    M.paintGrey = pm(S.paint, { name: 'news_paint_grey', tile: 1.2, metal: 0.2, rough: [0.7, 0.2], tint: [0.36, 0.39, 0.41], macro: 0.25 });
    M.paintDark = pm(S.paint, { name: 'news_paint_dark', tile: 0.8, metal: 0.3, rough: [0.6, 0.25], tint: [0.07, 0.075, 0.08] });
    M.corr = pm(S.corr, { name: 'news_corrugated', tile: 1.6, metal: 0.5, rough: [0.8, 0.15], tint: [0.4, 0.42, 0.44], macro: 0.3 });
    M.concrete = pm(S.concD, { name: 'news_concrete', tile: 1.8, rough: [0.8, 0.15], tint: [0.55, 0.55, 0.55] });
    M.porcelain = (() => {
        const m = own(new T.MeshStandardNodeMaterial({ roughness: 0.18, metalness: 0 }));
        m.colorNode = vec3(0.16, 0.085, 0.05).mul(mx_noise_float(positionLocal.mul(8)).mul(0.15).add(1));
        m.envMap = env; m.envMapIntensity = 1.0;
        return m;
    })();
    M.rubber = (() => {
        const m = own(new T.MeshStandardNodeMaterial({ roughness: 0.85, metalness: 0 }));
        m.colorNode = vec3(0.018, 0.018, 0.02).mul(mx_noise_float(positionLocal.mul(30)).mul(0.2).add(1));
        return m;
    })();
    M.glassDark = (() => {
        const m = own(new T.MeshPhysicalNodeMaterial({ roughness: 0.06, metalness: 0, clearcoat: 1 }));
        m.colorNode = vec3(0.01, 0.012, 0.016);
        m.envMap = env; m.envMapIntensity = 1.4;
        return m;
    })();
    // light sources the eye looks into: HMI flood lenses, sodium lenses, the LED panel, wall packs (unlit)
    const lamp = (rgb, k, name) => {
        const m = noMRT(own(new T.MeshBasicNodeMaterial()));
        m.name = name;
        m.colorNode = vec3(...rgb).mul(k);
        return m;
    };
    M.hmiLens = lamp(HMI, 1, 'news_hmi_lens');
    M.hmiLens.colorNode = vec3(...HMI).mul(9.0).mul(U.floods).mul(U.lights);
    M.sodiumLens = lamp(SODIUM, 1, 'news_sodium_lens');
    M.sodiumLens.colorNode = vec3(...SODIUM).mul(5.0).mul(U.lights);
    M.ledPanel = lamp([0.9, 0.95, 1.0], 1, 'news_led');
    M.ledPanel.colorNode = vec3(0.9, 0.95, 1.0).mul(6.0).mul(U.lights);
    M.aviation = lamp([1, 0.05, 0.03], 1, 'news_aviation');
    M.aviation.colorNode = vec3(1.0, 0.05, 0.03).mul(6.0).mul(U.blink);

    // ─────────────────────────── the monolith ───────────────────────────
    // CLANKER, sprayed: R fill (with overspray), G outline, B the moment each pixel is painted (0..1), A drips
    const graff = (() => {
        const W = 2048, H = 512;
        const word = 'CLANKER';
        const fill = L.createCanvas(W, H), gf = fill.getContext('2d');
        const outl = L.createCanvas(W, H), go = outl.getContext('2d');
        const drip = L.createCanvas(W, H), gd = drip.getContext('2d');
        for (const c of [gf, go, gd]) { c.fillStyle = '#000'; c.fillRect(0, 0, W, H); }
        const r = L.rng(41);
        const size = 470;
        const FONT = fam.caveat;
        gf.font = `${size}px ${FONT}`;
        const widths = [...word].map((ch) => gf.measureText(ch).width);
        const track = 0.0 * size;
        const total = widths.reduce((a, b) => a + b, 0) + track * (word.length - 1);
        let x = (W - total) / 2;
        const boxes = [];
        [...word].forEach((ch, i) => {
            const w = widths[i];
            const rot = (r() - 0.5) * 0.14 - 0.05;
            const by = H * 0.8 + (r() - 0.5) * 30 - i * 5;
            const bx = x;
            const draw = (c, mode) => {
                c.save(); c.translate(bx + w / 2, by); c.rotate(rot);
                c.font = `${size}px ${FONT}`; c.textAlign = 'center'; c.textBaseline = 'alphabetic';
                if (mode === 'over') { c.shadowColor = 'rgba(255,255,255,0.55)'; c.shadowBlur = 26; c.fillStyle = 'rgba(255,255,255,0.4)'; c.fillText(ch, 0, 0); }
                if (mode === 'fill') { c.shadowBlur = 0; c.fillStyle = '#fff'; c.fillText(ch, 0, 0); }
                if (mode === 'stroke') { c.lineJoin = 'round'; c.lineWidth = 26; c.strokeStyle = '#fff'; c.strokeText(ch, 0, 0); }
                c.restore();
            };
            draw(gf, 'over'); draw(go, 'stroke');
            boxes.push({ x0: x - 10, x1: x + w + 10, rot, by, w, i, draw });
            x += w + track;
        });
        boxes.forEach((b) => b.draw(gf, 'fill'));
        // drips run down from the letters' lower edges
        const fp = L.canvasPixels(fill);
        const drips = [];
        boxes.forEach((b) => {
            const n = 2 + Math.floor(r() * 3);
            for (let k = 0; k < n; k++) {
                const dx = Math.round(b.x0 + 30 + r() * (b.x1 - b.x0 - 60));
                let y0 = -1;
                for (let y = H - 1; y > 40; y--) { if (fp[(y * W + dx) * 4] > 200) { y0 = y; break; } }
                if (y0 < 0) continue;
                const len = 30 + r() * 110 * (0.5 + r());
                const wd = 5 + r() * 6;
                gd.fillStyle = '#fff';
                gd.beginPath(); gd.moveTo(dx - wd / 2, y0 - 6); gd.lineTo(dx + wd / 2, y0 - 6); gd.lineTo(dx + wd * 0.35, y0 + len); gd.lineTo(dx - wd * 0.35, y0 + len); gd.closePath(); gd.fill();
                gd.beginPath(); gd.arc(dx, y0 + len, wd * 0.62, 0, Math.PI * 2); gd.fill();
                drips.push({ dx, y0, len, b });
            }
        });
        const op = L.canvasPixels(outl), dp = L.canvasPixels(drip);
        const out = new Uint8Array(W * H * 4);
        const N = word.length;
        const letterAt = (px) => { let best = boxes[0], bd = 1e9; for (const b of boxes) { const c = (b.x0 + b.x1) / 2, d = Math.abs(px - c); if (d < bd) { bd = d; best = b; } } return best; };
        for (let y = 0; y < H; y++) for (let x2 = 0; x2 < W; x2++) {
            const i = y * W + x2;
            const f = fp[i * 4], o = op[i * 4] * (1 - Math.min(1, fp[i * 4] / 200)), d = dp[i * 4];
            const b = letterAt(x2);
            const loc = Math.min(1, Math.max(0, (x2 - b.x0) / (b.x1 - b.x0))) * 0.75 + (y / H) * 0.25;
            let tm = 0.03 + 0.66 * (b.i + loc) / N;
            if (o > 120) tm = 0.72 + 0.18 * (x2 / W);
            else if (d > 40 && f < 200) {
                const dr = drips.find((q) => Math.abs(q.dx - x2) < 12) || null;
                tm = Math.min(0.99, 0.8 + 0.18 * (dr ? Math.min(1, Math.max(0, (y - dr.y0) / dr.len)) : 0.5));
            }
            out[i * 4] = f; out[i * 4 + 1] = o; out[i * 4 + 2] = Math.round(tm * 255); out[i * 4 + 3] = d;
        }
        return L.dataTex(out, W, H, { srgb: false });
    })();
    const PAINT_FILL = hex(0xff1f8a), PAINT_LINE = hex(0xf2f1ec);
    // the facade: precast panels (3 m reveals, a band at 9.6 m), rain streaks from the parapet, the louvre band,
    // the wall packs' pools, the paint
    M.facade = (() => {
        const m = own(new T.MeshStandardNodeMaterial());
        m.name = 'news_facade';
        const P = positionLocal;
        const uvw = vec2(P.x, P.y);
        const c0 = texture(S.conc.col, uvw.div(3.0)).rgb;
        const r0 = texture(S.conc.rgh, uvw.div(3.0)).r;
        const n0 = texture(S.conc.nrm, uvw.div(3.0));
        const panelX = abs(fract(P.x.div(3.0)).sub(0.5)).mul(3.0);
        const reveal = ss(0.03, 0.012, float(1.5).sub(panelX)).add(ss(0.03, 0.012, abs(P.y.sub(9.6))));
        const streaks = ss(0.35, 0.8, mx_noise_float(vec3(P.x.mul(1.8), P.y.mul(0.08), 3.0)).mul(0.5).add(0.5)).mul(ss(4, BH, P.y));
        const panelTone = hash21(vec2(floor(P.x.div(3.0)), floor(P.y.div(9.6)))).mul(0.12).add(0.94);
        const louvre = step(11.2, P.y).mul(step(P.y, 13.4));
        const slat = ss(0.3, 0.5, abs(fract(P.y.div(0.16)).sub(0.5)).mul(2));
        let col = c0.mul(vec3(0.5, 0.52, 0.55)).mul(panelTone).mul(float(1).sub(streaks.mul(0.4))).mul(float(1).sub(clamp(reveal, 0, 1).mul(0.6)));
        col = mix(col, vec3(0.05, 0.055, 0.06).mul(slat.mul(0.6).add(0.4)), louvre);
        // the paint
        const gu = vec2(P.x.sub(GRAFF.x0).div(GRAFF.x1 - GRAFF.x0), P.y.sub(GRAFF.y0).div(GRAFF.y1 - GRAFF.y0));
        const inG = step(0, gu.x).mul(step(gu.x, 1)).mul(step(0, gu.y)).mul(step(gu.y, 1));
        const g = texture(graff, gu);
        const show = ss(0.0, 0.025, U.spray.sub(g.b));
        const fillA = g.r.mul(show).mul(inG), lineA = g.g.mul(show).mul(inG), dripA = g.a.mul(show).mul(inG);
        col = mix(col, PAINT_FILL.mul(0.85), clamp(max(fillA, dripA), 0, 1));
        col = mix(col, PAINT_LINE.mul(0.8), lineA);
        const paintA = clamp(fillA.add(lineA).add(dripA), 0, 1);
        m.colorNode = col;
        m.roughnessNode = clamp(mix(mix(r0.mul(0.5).add(0.45), float(0.5), louvre), float(0.38), paintA), 0.05, 1);
        m.metalnessNode = louvre.mul(0.4);
        m.normalNode = normalMap(n0, vec2(0.7, 0.7));
        // the wall packs' sodium pools (painted: nine of them), brightest just under each lamp
        let pools = float(0);
        for (const wx of WALLPACKS) {
            const dx = P.x.sub(wx), dy = P.y.sub(WP_Y);
            const cone = exp(dx.mul(dx).mul(-0.05).div(max(float(WP_Y + 0.5).sub(P.y), 0.6).mul(0.25)));
            pools = pools.add(cone.mul(exp(max(dy.negate(), 0).mul(-0.16))).mul(step(P.y, WP_Y + 0.2)));
        }
        m.emissiveNode = col.mul(pools).mul(vec3(...SODIUM)).mul(0.55).mul(U.lights);
        m.envMap = env; m.envMapIntensity = 0.4;
        return m;
    })();
    const bld = new T.Group();
    bld.name = 'news_monolith';
    group.add(bld);
    {
        const fb = L.bucket('news_facade');
        fb.box(BX1 - BX0, BH, BD, (BX0 + BX1) / 2, BH / 2, FACADE_Z - BD / 2);
        fb.box(BX1 - BX0 + 0.6, 1.0, 0.6, (BX0 + BX1) / 2, BH + 0.5, FACADE_Z - 0.3);    // the parapet
        bld.add(fb.mesh(M.facade));
        // the base: a dark plinth band, and the wall packs
        const pb = L.bucket('news_plinth').box(BX1 - BX0, 0.5, 0.25, (BX0 + BX1) / 2, 0.25, FACADE_Z + 0.12);
        bld.add(pb.mesh(M.concrete));
        const wp = L.bucket('news_wallpacks'), wl = L.bucket('news_wallpack_lens');
        for (const x of WALLPACKS) {
            wp.box(0.5, 0.36, 0.3, x, WP_Y, FACADE_Z + 0.15);
            wl.box(0.42, 0.04, 0.22, x, WP_Y - 0.19, FACADE_Z + 0.17);
        }
        bld.add(wp.mesh(M.paintDark), wl.mesh(M.sodiumLens));
        // the roof: condenser rows along the front edge (a serrated skyline), cooling towers, stacks, aviation lights
        const unitGeo = own(new T.BoxGeometry(2.4, 1.5, 2.0));
        const units = [];
        for (const zr of [FACADE_Z - 3.0, FACADE_Z - 6.2]) for (let x = BX0 + 3; x < BX1 - 3; x += 3.0) units.push([x, zr]);
        const fanTopMat = (() => {
            const m = L.pbrMat(S.galv, { name: 'news_units', tile: 1.0, metal: 0.6, rough: [0.6, 0.3], tint: [0.42, 0.44, 0.46], env, envI: 0.6,
                post: ({ col }) => {
                    // on the top: the round fan grille (rings + spokes) — darker inside
                    const q = positionLocal;
                    const top = step(0.7, T.normalLocal.y);
                    const rr = length(vec2(q.x, q.z));
                    const ring = step(rr, 0.85);
                    const grille = ss(0.25, 0.45, abs(fract(rr.mul(9)).sub(0.5))).mul(ss(0.2, 0.4, abs(fract(atan(q.z, q.x).mul(6 / Math.PI)).sub(0.5))));
                    return { col: mix(col, vec3(0.02).add(grille.mul(0.05)), ring.mul(top)) };
                } });
            return m;
        })();
        const unitMesh = new T.InstancedMesh(unitGeo, fanTopMat, units.length);
        units.forEach(([x, z], i) => unitMesh.setMatrixAt(i, L.M4(x, BH + 0.75, z)));
        unitMesh.name = 'news_roof_units';
        bld.add(unitMesh);
        const tb = L.bucket('news_towers'), ts = L.bucket('news_tower_stacks');
        for (const [x, z] of TOWERS) {
            tb.box(9, 3.6, 9, x, BH + 1.8, z);
            for (const [ox, oz] of [[-2.2, -2.2], [2.2, -2.2], [-2.2, 2.2], [2.2, 2.2]]) {
                const cy = new T.CylinderGeometry(1.55, 1.7, 1.6, 20, 1, true);
                ts.add(cy, L.M4(x + ox, BH + 3.6 + 0.8, z + oz), { uv: 'keep', uvScale: [6, 1] }); cy.dispose();
            }
        }
        for (const [x, z] of [[-55, -40], [30, -50]]) { const st = new T.CylinderGeometry(0.6, 0.7, 7, 16); ts.add(st, L.M4(x, BH + 3.5, z), { uv: 'keep', uvScale: [3, 3] }); st.dispose(); }
        bld.add(tb.mesh(M.corr), ts.mesh(M.galv));
        const av = L.bucket('news_aviation');
        for (const [x, z] of [[BX0 + 0.5, FACADE_Z - 0.5], [BX1 - 0.5, FACADE_Z - 0.5], [BX0 + 0.5, FACADE_Z - BD + 0.5], [BX1 - 0.5, FACADE_Z - BD + 0.5], ...TOWERS.map(([x, z]) => [x, z])]) {
            const sp = new T.SphereGeometry(0.22, 10, 8);
            av.add(sp, L.M4(x, (Math.abs(z - FACADE_Z) < 2 || z < FACADE_Z - BD + 2) ? BH + 1.25 : BH + 4.6, z), { uv: 'keep' }); sp.dispose();
        }
        bld.add(av.mesh(M.aviation));
        bld.traverse((o) => { if (o.isMesh) o.userData.assembly = 'news_monolith'; });
    }

    // ─────────────────────────── the fence: chain link, posts, rails, outriggers, barbed wire, concertina ───────────────────────────
    M.chain = (() => {
        const m = own(new T.MeshStandardNodeMaterial({ transparent: true, depthWrite: false, side: T.DoubleSide }));
        m.name = 'news_chainlink';
        const P = positionLocal;          // the plane's own frame: x along the fence, y up (the mesh sits in the set frame)
        const Ps = setP();
        const fwU = fwidth(P.x.div(CELL)).add(fwidth(P.y.div(CELL)));
        const soft = clamp(fwU.mul(0.6), 0.004, 0.5);
        const cov = chain(P.x, P.y, soft);
        // sub-pixel cells: fall back to the mean coverage (a grey haze) instead of shimmering moiré
        const coverage = mix(cov, float(0.13), ss(0.35, 0.9, fwU));
        const sag = ss(0.0, 0.08, P.y).mul(ss(FH, FH - 0.08, P.y));
        m.colorNode = texture(S.galv.col, vec2(P.x, P.y).div(0.7)).rgb.mul(vec3(0.3, 0.31, 0.33));
        m.roughnessNode = float(0.5);
        m.metalnessNode = float(0.8);
        m.opacityNode = coverage.mul(sag);
        // wires glint in the floods (lit from either side: thin cylinders), the street's sodium from behind
        m.emissiveNode = vec3(...HMI).mul(floodAt(Ps, null, false)).mul(0.005).add(vec3(...SODIUM).mul(0.002));
        m.lightsNode = softLights;
        m.envMap = env; m.envMapIntensity = 0.6;
        return m;
    })();
    const fence = new T.Group();
    fence.name = 'news_fence';
    group.add(fence);
    {
        const mesh = new T.Mesh(own(new T.PlaneGeometry(FX1 - FX0, FH)), M.chain);
        // keep positionLocal = set coordinates along the fence: bake the translation into the geometry
        mesh.geometry.translate((FX0 + FX1) / 2, FH / 2, 0);
        mesh.position.set(0, 0, FZ);
        mesh.name = 'news_chainlink';
        mesh.renderOrder = 2;
        mesh.userData.noSupportCheck = true;
        fence.add(mesh);
        const fb = L.bucket('news_fence_steel');
        const posts = [];
        for (let x = FX0; x <= FX1 + 1e-6; x += 3) posts.push(x);
        for (const x of posts) {
            const p = new T.CylinderGeometry(0.045, 0.045, FH + 0.25, 10);
            fb.add(p, L.M4(x, (FH + 0.25) / 2, FZ - 0.05), { uv: 'keep', uvScale: [0.3, 3] }); p.dispose();
            // the 45° outrigger arm, leaning out toward the protesters
            const arm = new T.CylinderGeometry(0.022, 0.022, 0.62, 6);
            fb.add(arm, L.M4(x, FH + 0.25 + 0.22, FZ - 0.05 + 0.22, Math.PI / 4, 0, 0), { uv: 'keep' }); arm.dispose();
        }
        const rail = (y, z, r) => {
            const g = new T.CylinderGeometry(r, r, FX1 - FX0, 8);
            fb.add(g, L.M4((FX0 + FX1) / 2, y, z, 0, 0, Math.PI / 2), { uv: 'keep', uvScale: [1, 40] }); g.dispose();
        };
        rail(FH, FZ - 0.05, 0.03);
        rail(0.08, FZ - 0.05, 0.02);
        const bw = L.bucket('news_barbed');
        for (let k = 0; k < 3; k++) {
            const y = FH + 0.27 + k * 0.14, z = FZ - 0.05 + 0.27 + k * 0.14;
            // twisted strand with barbs every 12 cm
            const g = new T.CylinderGeometry(0.004, 0.004, FX1 - FX0, 4);
            bw.add(g, L.M4((FX0 + FX1) / 2, y, z, 0, 0, Math.PI / 2), { uv: 'keep' }); g.dispose();
            for (let x = FX0; x < FX1; x += 0.12) {
                const b = new T.BoxGeometry(0.003, 0.05, 0.003);
                bw.add(b, L.M4(x, y, z, 0.6, 0, 0.5)); b.dispose();
            }
        }
        // the concertina coil riding the outriggers
        const coil = [];
        const loops = Math.round((FX1 - FX0) / 0.45);
        for (let i = 0; i <= loops * 16; i++) {
            const a = i / 16 * Math.PI * 2, x = FX0 + (i / 16) * 0.45;
            coil.push(new T.Vector3(x + Math.sin(a) * 0.05, FH + 0.62 + Math.cos(a) * 0.3, FZ + 0.3 + Math.sin(a) * 0.3));
        }
        const cg = new T.TubeGeometry(new T.CatmullRomCurve3(coil), loops * 16, 0.004, 3, false);
        bw.add(cg, null, { uv: 'keep' }); cg.dispose();
        fence.add(fb.mesh(M.galv), bw.mesh(M.galv));
        // signs on the fence: generic private-property and high-voltage warnings
        const signTex = (() => {
            const cv = L.createCanvas(1024, 512), g = cv.getContext('2d');
            g.fillStyle = '#ece9e1'; g.fillRect(0, 0, 512, 512);
            g.fillStyle = '#b8141c'; g.fillRect(0, 0, 512, 150);
            g.fillStyle = '#fff'; fitText(g, 'PRIVATE PROPERTY', { x: 256, y: 78, maxW: 460, maxH: 74, family: fam.rajdhani });
            g.fillStyle = '#111'; fitText(g, 'NO', { x: 256, y: 232, maxW: 300, maxH: 120, family: fam.rajdhani });
            fitText(g, 'TRESPASSING', { x: 256, y: 352, maxW: 460, maxH: 110, family: fam.rajdhani });
            g.fillStyle = '#333'; fitText(g, 'VIOLATORS WILL BE PROSECUTED', { x: 256, y: 450, maxW: 440, maxH: 40, family: fam.rajdhani });
            g.fillStyle = '#f1c21b'; g.fillRect(512, 0, 512, 512);
            g.fillStyle = '#111'; g.fillRect(512, 0, 512, 140);
            g.fillStyle = '#f1c21b'; fitText(g, 'DANGER', { x: 768, y: 74, maxW: 420, maxH: 100, family: fam.rajdhani });
            g.fillStyle = '#111'; fitText(g, 'HIGH VOLTAGE', { x: 768, y: 228, maxW: 460, maxH: 110, family: fam.rajdhani });
            fitText(g, 'KEEP OUT', { x: 768, y: 352, maxW: 400, maxH: 100, family: fam.rajdhani });
            g.beginPath(); g.moveTo(768 - 40, 400); g.lineTo(768 + 10, 400); g.lineTo(768 - 10, 440); g.lineTo(768 + 40, 440); g.lineTo(768 - 30, 500); g.lineTo(768 - 5, 452); g.lineTo(768 - 45, 452); g.closePath(); g.fill();
            return L.canvasTex(cv);
        })();
        const sMat = L.pbrMat(S.paint, { name: 'news_fence_signs', tile: 0.5, rough: [0.5, 0.2], env, envI: 0.6,
            recolor: (c) => texture(signTex, uv()).rgb.mul(lum(c).mul(0.35).add(0.75)),
            post: ({ col }) => ({ emissive: col.mul(floodAt(setP(), null, false)).mul(0.014) }) });
        const sg = L.bucket('news_fence_signs');
        const plate = (x, y, z, tile, ry = 0) => {
            const g = new T.PlaneGeometry(0.6, 0.6);
            const uvA = g.attributes.uv;
            for (let i = 0; i < uvA.count; i++) uvA.setX(i, uvA.getX(i) * 0.5 + tile * 0.5);
            sg.add(g, L.M4(x, y, z, 0, ry, 0), { uv: 'keep' }); g.dispose();
        };
        plate(-6.6, 1.65, FZ + 0.02, 0); plate(11.4, 1.65, FZ + 0.02, 0); plate(-30, 1.65, FZ + 0.02, 0);
        plate(26, 1.6, YARD.z1 + 0.03, 1); plate(37, 1.6, YARD.z1 + 0.03, 1);
        const sm = sg.mesh(sMat, { userData: { noZFightCheck: true } });
        fence.add(sm);
        fence.traverse((o) => { if (o.isMesh) { o.userData.assembly = 'news_fence'; o.userData.noSupportCheck = true; } });
    }

    // ─────────────────────────── the floodlight poles, their heads and their beams ───────────────────────────
    const poles = new T.Group(); poles.name = 'news_floods'; group.add(poles);
    {
        const pb = L.bucket('news_poles'), hb = L.bucket('news_flood_heads'), lb = L.bucket('news_flood_lenses');
        for (const [x, z] of POLES) {
            const p = new T.CylinderGeometry(0.11, 0.16, POLE_H + 0.3, 12);
            pb.add(p, L.M4(x, (POLE_H + 0.3) / 2, z), { uv: 'keep', uvScale: [0.6, 6] }); p.dispose();
            pb.box(0.6, 0.06, 0.6, x, 0.03, z);
            pb.box(1.9, 0.1, 0.1, x, POLE_H + 0.18, z);                 // the crossarm
            for (const ox of [-0.62, 0.62]) {
                // a rectangular HMI flood: housing, lens toward +z tilted down, a visor
                const m4 = L.M4(x + ox, POLE_H, z + 0.12, TILT, 0, 0);
                const box = new T.BoxGeometry(0.55, 0.42, 0.22); hb.add(box, m4); box.dispose();
                const lens = new T.PlaneGeometry(0.47, 0.34); const ml = L.M4(x + ox, POLE_H, z + 0.12, TILT, 0, 0).multiply(new T.Matrix4().makeTranslation(0, 0, 0.115));
                lb.add(lens, ml, { uv: 'keep' }); lens.dispose();
                const visor = new T.BoxGeometry(0.58, 0.02, 0.22); const mv = L.M4(x + ox, POLE_H, z + 0.12, TILT, 0, 0).multiply(new T.Matrix4().makeTranslation(0, 0.22, 0.12));
                hb.add(visor, mv); visor.dispose();
            }
        }
        poles.add(pb.mesh(M.galv), hb.mesh(M.paintDark), lb.mesh(M.hmiLens));
        poles.traverse((o) => { if (o.isMesh) o.userData.assembly = 'news_floods'; });
    }
    // visible beams in the damp air: additive cones, brightest at the lamp, fading along and toward the rim
    M.beam = (() => {
        const m = noMRT(own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide })));
        m.name = 'news_beams';
        m.colorNode = Fn(() => {
            const q = positionLocal;                         // cone frame: y = along the beam (0 at the lamp, −len at the end)
            const along = clamp(q.y.negate().div(26.0), 0, 1);
            const N = normalize(T.normalView), Vv = normalize(T.positionViewDirection);
            const rim = pow(abs(dot(N, Vv)), 1.6);
            const mist = mx_fractal_noise_float(vec3(q.x.mul(0.4), q.y.mul(0.15).add(U.t.mul(0.35)), q.z.mul(0.4)), 3, 2.0, 0.5).mul(0.45).add(0.75);
            return vec3(...HMI).mul(pow(float(1).sub(along), 1.8)).mul(rim).mul(mist).mul(0.045).mul(U.floods).mul(U.lights);
        })();
        return m;
    })();
    const beams = new T.Group(); beams.name = 'news_beams'; group.add(beams);
    for (const f of FL) for (const ox of [-0.62, 0.62]) {
        const len = 26, r1 = Math.tan(FLOOD_ANGLE * 0.8) * len;
        const cone = own(new T.CylinderGeometry(0.2, r1, len, 24, 1, true));
        cone.translate(0, -len / 2, 0);
        const mesh = new T.Mesh(cone, M.beam);
        mesh.position.set(f.p[0] + ox, f.p[1], f.p[2] + 0.25);
        mesh.quaternion.setFromUnitVectors(new T.Vector3(0, -1, 0), new T.Vector3(...f.d));
        mesh.renderOrder = 6; mesh.frustumCulled = false;
        mesh.userData.noSupportCheck = true;
        beams.add(mesh);
    }

    // ─────────────────────────── steam: plumes off the cooling towers, and low steam at the grates ───────────────────────────
    M.steam = (() => {
        const m = noMRT(own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, side: T.DoubleSide })));
        m.name = 'news_steam';
        const iA = attribute('iSteam', 'vec4');            // per puff: x = rise 0..1, y = seed, z = size, w = plume kind
        const vUv = uv();
        const s = iA.y;
        // billboard: the quad turns to the camera (spherical), sized per puff; the centre comes from the instance matrix
        const Ps = setP();
        m.colorNode = Fn(() => {
            const d = vUv.sub(0.5).mul(2);
            const r2 = dot(d, d);
            const tt = U.t.mul(0.08);
            const n = mx_fractal_noise_float(vec3(d.x.mul(1.6).add(s.mul(17)), d.y.mul(1.6).sub(tt.mul(3.0)).add(s.mul(9)), tt.add(s)), 4, 2.0, 0.55);
            const dens = clamp(float(1).sub(r2).mul(n.mul(0.9).add(0.55)), 0, 1).mul(ss(1.0, 0.35, r2));
            // lit by the floods (forward scatter when we look toward a lamp through it), the sodium wash, the sky
            const cam = setCam();
            const V = normalize(Ps.sub(cam));
            let fwd = float(0);
            for (const f of FL) {
                const Ld = normalize(Ps.sub(vec3(...f.p)));
                fwd = fwd.add(pow(max(dot(V, Ld), 0), 10).mul(2.0));
            }
            const fl = floodAt(Ps, null, false).mul(0.008).add(fwd.mul(0.06).mul(U.floods));
            const sod = vec3(...SODIUM).mul(0.05).mul(ss(48, 10, Ps.y));
            const under = vec3(...HMI).mul(0.05).mul(ss(40, 18, Ps.y)).mul(U.floods);    // the floodlit yard below
            const c = vec3(...HMI).mul(fl).add(sod).add(under).add(vec3(0.035, 0.04, 0.05));
            return vec4(c, dens.mul(iA.x.oneMinus().mul(0.9).add(0.1)).mul(0.55));
        })();
        m.opacityNode = null;
        return m;
    })();
    const steam = (() => {
        const puffs = [];
        const r = L.rng(77);
        const plume = (x0, y0, z0, kind, n, H, wind, size0, size1) => {
            for (let k = 0; k < n; k++) puffs.push({ x0, y0, z0, kind, k, n, H, wind, size0, size1, seed: r() });
        };
        for (const [x, z] of TOWERS) for (const [ox, oz] of [[-2.2, -2.2], [2.2, 2.2]]) plume(x + ox, BH + 4.2, z + oz, 0, 12, 30, [7.0, 0, 4.5], 3.4, 18);
        for (const [x, z] of VENTS) plume(x, 0.4, z, 1, 7, 9, [3.2, 0, 1.4], 1.4, 5.5);
        const geo = own(new T.PlaneGeometry(1, 1));
        const mesh = new T.InstancedMesh(geo, M.steam, puffs.length);
        const data = new Float32Array(puffs.length * 4);
        puffs.forEach((p, i) => { data.set([0, p.seed, p.size0, p.kind], i * 4); });
        geo.setAttribute('iSteam', new T.InstancedBufferAttribute(data, 4));
        mesh.name = 'news_steam';
        mesh.frustumCulled = false;
        mesh.renderOrder = 4;
        mesh.userData.noSupportCheck = true;
        // the puffs cycle up the plume (deterministic in t); placed per frame (a few dozen matrices)
        const m4 = new T.Matrix4(), q = new T.Quaternion(), sc = new T.Vector3(), pos = new T.Vector3();
        const camQ = new T.Quaternion();
        const place = (t, camSetQuat) => {
            camQ.copy(camSetQuat);
            puffs.forEach((p, i) => {
                const period = p.kind ? 7.0 : 11.0;
                const ph = ((t / period + p.k / p.n + p.seed * 0.13) % 1 + 1) % 1;
                const e = Math.pow(ph, 0.85);
                pos.set(p.x0 + p.wind[0] * e * e + Math.sin(t * 0.3 + p.seed * 6) * 0.4 * e,
                    p.y0 + p.H * e,
                    p.z0 + p.wind[2] * e * e);
                const s = p.size0 + (p.size1 - p.size0) * e;
                q.copy(camQ);
                const spin = new T.Quaternion().setFromAxisAngle(new T.Vector3(0, 0, 1), p.seed * 6.28 + t * 0.05 * (p.seed - 0.5));
                q.multiply(spin);
                m4.compose(pos, q, sc.set(s, s, s));
                mesh.setMatrixAt(i, m4);
                data[i * 4] = ph;
            });
            mesh.instanceMatrix.needsUpdate = true;
            geo.attributes.iSteam.needsUpdate = true;
        };
        return { mesh, place };
    })();
    group.add(steam.mesh);

    // ─────────────────────────── the transformer yard ───────────────────────────
    const yard = new T.Group(); yard.name = 'news_yard'; group.add(yard);
    {
        const tb = L.bucket('news_transformers'), fb = L.bucket('news_fins'), bu = L.bucket('news_bushings'), st = L.bucket('news_gantry');
        for (const x of [26, 32, 38]) {
            const z = -6.4;
            tb.box(3.2, 3.0, 2.4, x, 1.5 + 0.3, z);
            tb.box(3.6, 0.3, 2.8, x, 0.15, z);
            const tank = new T.CylinderGeometry(0.45, 0.45, 2.4, 16); tb.add(tank, L.M4(x, 3.75, z - 0.6, 0, 0, Math.PI / 2), { uv: 'keep' }); tank.dispose();
            for (let k = 0; k < 9; k++) { fb.box(0.06, 2.4, 0.9, x - 1.95, 1.7, z - 1.0 + k * 0.25); fb.box(0.06, 2.4, 0.9, x + 1.95, 1.7, z - 1.0 + k * 0.25); }
            for (let k = 0; k < 3; k++) {
                const pts = [];
                for (let j = 0; j <= 14; j++) { const y = j * 0.1; pts.push(new T.Vector2(j % 2 ? 0.14 : 0.09, y)); }
                pts.unshift(new T.Vector2(0.001, 0)); pts.push(new T.Vector2(0.001, 1.4));
                const lg = new T.LatheGeometry(pts, 12);
                bu.add(lg, L.M4(x - 1.0 + k * 1.0, 3.3, z + 0.5), { uv: 'keep' }); lg.dispose();
            }
            tb.box(0.9, 1.6, 0.6, x + 1.3, 0.8, z + 1.7);                 // the control cabinet
        }
        // the gantry: two H-frames and their beam
        for (const z of [-2.6, -10.2]) {
            for (const x of [YARD.x0 + 1.5, YARD.x1 - 1.5]) st.box(0.35, 9, 0.35, x, 4.5, z);
            st.box(YARD.x1 - YARD.x0 - 2.6, 0.4, 0.4, (YARD.x0 + YARD.x1) / 2, 8.8, z);
        }
        yard.add(tb.mesh(M.paintGrey), fb.mesh(M.paintGrey), bu.mesh(M.porcelain), st.mesh(M.galv));
        // conductors sagging from the gantry to the bushings
        const wb = L.bucket('news_conductors');
        for (const x of [26, 32, 38]) for (let k = 0; k < 3; k++) {
            const a = new T.Vector3(x - 1.0 + k, 4.7, -5.9), b = new T.Vector3(x - 1.0 + k, 8.6, -2.6);
            const mid = a.clone().lerp(b, 0.5); mid.y -= 0.6;
            const tg = new T.TubeGeometry(new T.QuadraticBezierCurve3(a, mid, b), 16, 0.02, 4, false);
            wb.add(tg, null, { uv: 'keep' }); tg.dispose();
        }
        yard.add(wb.mesh(M.galv));
        // its own fence (the same chain link) on the open sides
        const yf = new T.Mesh(own(new T.PlaneGeometry(YARD.x1 - YARD.x0, FH)), M.chain);
        yf.geometry.translate((YARD.x0 + YARD.x1) / 2, FH / 2, 0);
        yf.position.set(0, 0, YARD.z1);
        yf.renderOrder = 2;
        yard.add(yf);
        // an amber status beacon on each cabinet
        const bc = L.bucket('news_beacons');
        for (const x of [26, 32, 38]) { const s = new T.SphereGeometry(0.07, 8, 6); bc.add(s, L.M4(x + 1.3, 1.7, -6.4 + 1.7), { uv: 'keep' }); s.dispose(); }
        const amber = lamp([1.0, 0.55, 0.08], 4, 'news_amber');
        yard.add(bc.mesh(amber));
        yard.traverse((o) => { if (o.isMesh) o.userData.assembly = 'news_yard'; });
    }

    // ─────────────────────────── the protest side: sidewalk curb, streetlights, the town ───────────────────────────
    const street = new T.Group(); street.name = 'news_street'; group.add(street);
    {
        const cb = L.bucket('news_curb').box(260, 0.15, WALK.z1 - WALK.z0, -5, 0.075, (WALK.z0 + WALK.z1) / 2);
        const curbMat = pm(S.concL, { name: 'news_walk', tile: 2.0, rough: [0.5, 0.35], tint: [0.5, 0.5, 0.5],
            post: ({ col }) => {
                const P = setP();
                const joint = ss(0.012, 0.004, abs(fract(P.x.div(1.5)).sub(0.5)).sub(0.49).abs());
                return { col: col.mul(float(1).sub(joint.mul(0.5))) };
            } });
        street.add(cb.mesh(curbMat));
        const pb = L.bucket('news_streetpoles'), hb = L.bucket('news_streetheads'), lb = L.bucket('news_streetlens');
        for (const [x, z] of STREET) {
            const p = new T.CylinderGeometry(0.09, 0.13, 9.0, 10); pb.add(p, L.M4(x, 4.5, z), { uv: 'keep', uvScale: [0.6, 6] }); p.dispose();
            pb.box(0.08, 0.08, 2.2, x, 8.75, z - 1.05, { rx: -0.08 });
            hb.box(0.42, 0.18, 0.85, x, 8.62, z - 1.95);
            lb.box(0.34, 0.03, 0.7, x, 8.52, z - 1.95);
        }
        street.add(pb.mesh(M.galv), hb.mesh(M.paintGrey), lb.mesh(M.sodiumLens));
        // the town: a row of small houses across the road, some windows lit; dark conifers behind
        const sid = pm(S.siding, { name: 'news_houses', tile: 2.2, rough: [0.7, 0.2],
            recolor: (c) => c.mul(vec3(0.2, 0.19, 0.18)),
            post: ({ col }) => {
                const P = setP();
                const front = step(0.6, setN().z.negate());
                const wx = fract(P.x.div(2.7)), hy = P.y;
                const win = ss(0.24, 0.27, wx).mul(ss(0.76, 0.73, wx)).mul(max(step(1.0, hy).mul(step(hy, 2.3)), step(3.2, hy).mul(step(hy, 4.3)))).mul(front);
                const id = hash21(vec2(floor(P.x.div(2.7)), floor(hy.div(2.2)).add(floor(P.z))));
                const lit = step(0.52, id);
                const curtain = mx_noise_float(vec3(P.x.mul(3), P.y.mul(3), 1)).mul(0.25).add(0.75);
                const glow = vec3(1.0, 0.66, 0.32).mul(curtain).mul(lit).mul(win).mul(1.6);
                const glass = mix(col, vec3(0.01, 0.012, 0.016), win);
                return { col: glass, emissive: glow.mul(U.lights), rough: mix(float(0.7), float(0.08), win) };
            } });
        const roofM = pm(S.shingle, { name: 'news_roofs', tile: 1.6, rough: [0.8, 0.15], tint: [0.4, 0.38, 0.38] });
        const hbody = L.bucket('news_house_bodies'), hroof = L.bucket('news_house_roofs');
        const r = L.rng(12);
        for (let i = 0; i < 9; i++) {
            const x = -58 + i * 14.5 + (r() - 0.5) * 3, z = 30 + (r() - 0.5) * 4;
            const w = 9 + r() * 2.5, d = 8, h = 4.6 + (r() < 0.4 ? 2.5 : 0);
            hbody.box(w, h, d, x, h / 2, z);
            const sh = new T.Shape();
            sh.moveTo(-w / 2 - 0.4, 0); sh.lineTo(w / 2 + 0.4, 0); sh.lineTo(0, 2.6 + r() * 0.8); sh.closePath();
            const rg = new T.ExtrudeGeometry(sh, { depth: d + 0.8, bevelEnabled: false });
            rg.translate(0, 0, -(d + 0.8) / 2);
            hroof.add(rg, L.M4(x, h, z)); rg.dispose();
        }
        street.add(hbody.mesh(sid), hroof.mesh(roofM));
        const trees = L.bucket('news_trees');
        for (let i = 0; i < 16; i++) {
            const x = -64 + i * 8.6 + (r() - 0.5) * 4, z = 40 + r() * 8, h = 7 + r() * 6;
            const c = new T.ConeGeometry(1.6 + r(), h, 8); trees.add(c, L.M4(x, h / 2, z), { uv: 'keep', uvScale: [3, 3] }); c.dispose();
        }
        const treeMat = pm(S.grass, { name: 'news_trees', tile: 1.0, recolor: (c) => c.mul(vec3(0.12, 0.16, 0.12)), rough: [0.9, 0.1] });
        street.add(trees.mesh(treeMat));
        street.traverse((o) => { if (o.isMesh) { o.userData.assembly = 'news_street'; } });
    }

    // ─────────────────────────── the pickets: silhouettes, signs, phones, flashlights ───────────────────────────
    const crowd = new T.Group(); crowd.name = 'news_crowd'; group.add(crowd);
    let handLights = () => {};
    const signAtlas = (() => {
        const TW = 512, TH = 396, W = TW * 4, H = TH * 2;
        const cv = L.createCanvas(W, H), g = cv.getContext('2d');
        const msgs = [
            { t: ['NOT IN', 'OUR TOWN'], f: fam.kalam, ink: '#141414', bg: '#f1eee5' },
            { t: ['OUR', 'WATER'], f: fam.caveat, ink: '#1c3f9c', bg: '#c49a62', drop: true },
            { t: ['WHO PAYS', 'THE BILL?'], f: fam.kalam, ink: '#b3121b', bg: '#f1eee5' },
            { t: ['NO DATA', 'CENTER', 'HERE'], f: fam.caveat, ink: '#141414', bg: '#c49a62', under: '#b3121b' },
            { t: ['NOISE', '24/7'], f: fam.sedgwick, ink: '#141414', bg: '#f1eee5', zig: '#b3121b' },
            { t: ['HEAR', 'US'], f: fam.caveat, ink: '#b3121b', bg: '#c49a62' },
            { t: ['OUR TOWN', 'OUR SAY'], f: fam.kalam, ink: '#1c3f9c', bg: '#f1eee5' },
            { t: ['SAVE OUR', 'AQUIFER'], f: fam.sedgwick, ink: '#141414', bg: '#f1eee5', drop: true },
        ];
        const rr = L.rng(3);
        msgs.forEach((m, i) => {
            const x0 = (i % 4) * TW, y0 = Math.floor(i / 4) * TH;
            g.save(); g.beginPath(); g.rect(x0, y0, TW, TH); g.clip();
            g.fillStyle = m.bg; g.fillRect(x0, y0, TW, TH);
            // grime toward the edges, a fold
            const gr = g.createRadialGradient(x0 + TW / 2, y0 + TH / 2, 60, x0 + TW / 2, y0 + TH / 2, TW * 0.7);
            gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(40,30,20,0.28)');
            g.fillStyle = gr; g.fillRect(x0, y0, TW, TH);
            const n = m.t.length;
            const lh = (TH - 70) / n;
            g.fillStyle = m.ink;
            m.t.forEach((ln, k) => {
                g.save(); g.translate(x0 + TW / 2, y0 + 40 + lh * (k + 0.55)); g.rotate((rr() - 0.5) * 0.06);
                fitText(g, ln, { x: 0, y: 0, maxW: TW - 70, maxH: lh * 0.95, family: m.f });
                g.restore();
            });
            if (m.under) { g.strokeStyle = m.under; g.lineWidth = 9; g.lineCap = 'round'; g.beginPath(); g.moveTo(x0 + 70, y0 + TH - 34); g.quadraticCurveTo(x0 + TW / 2, y0 + TH - 22, x0 + TW - 70, y0 + TH - 38); g.stroke(); }
            if (m.zig) { g.strokeStyle = m.zig; g.lineWidth = 8; g.beginPath(); for (let k = 0; k < 10; k++) g.lineTo(x0 + 60 + k * 40, y0 + TH - 30 - (k % 2) * 18); g.stroke(); }
            if (m.drop) {
                g.fillStyle = '#2a6fd6'; const dx = x0 + TW - 70, dy = y0 + 60;
                g.beginPath(); g.moveTo(dx, dy - 34); g.bezierCurveTo(dx + 30, dy, dx + 26, dy + 30, dx, dy + 30); g.bezierCurveTo(dx - 26, dy + 30, dx - 30, dy, dx, dy - 34); g.fill();
            }
            g.restore();
        });
        return { tex: L.canvasTex(cv), cols: 4, rows: 2, n: msgs.length };
    })();
    {
        const rig = JSON.parse(Deno.readTextFileSync(new URL('../../assets/sets/funeral/crowd_rig.json', here)));
        const bytes = Deno.readFileSync(new URL('../../assets/models/funeral_crowd.glb', here));
        const gltf = await new globalThis.GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
        const variants = [];
        gltf.scene.traverse((o) => { if (o.isMesh && /person_/.test(o.name)) variants.push(o); });
        variants.sort((a, b) => a.name.localeCompare(b.name));
        const SH = rig.shoulder, HD = rig.hand, NK = rig.neck;
        // people: denser near the fence and the middle; a clear lane for the 'fence' camera in front of her
        const r = L.rng(2026);
        const people = [];
        for (let k = 0; k < 9000 && people.length < 78; k++) {
            const x = -16 + r() * 32, z = FZ + 0.9 + r() * 9.5;
            const dens = Math.exp(-Math.pow(Math.max(0, Math.abs(x) - 5) / 7, 2)) * (0.45 + 0.55 * Math.exp(-(z - FZ - 1) / 4));
            if (r() > dens) continue;
            if (Math.abs(x - 0.3) < 2.1 && z < FZ + 3.2) continue;                         // the camera lane at her
            if (Math.abs(x - VAN[0]) < 3.6 && Math.abs(z - VAN[1]) < 1.8) continue;          // the van
            if (Math.hypot(x - NEWS_LIGHT[0], z - NEWS_LIGHT[2]) < 1.2) continue;
            if (people.some((p) => Math.hypot(p.x - x, p.z - z) < 0.62)) continue;
            people.push({ x, z });
        }
        // roles
        people.forEach((p, i) => {
            p.variant = i % variants.length;
            p.yaw = Math.PI + (r() - 0.5) * 0.5 + Math.atan2(-p.x, 14) * 0.25;
            p.scale = 0.92 + r() * 0.16;
            p.seed = r();
            const q = r();
            p.role = q < 0.34 ? 'sign' : q < 0.56 ? 'phone' : q < 0.64 ? 'torch' : q < 0.74 ? 'fist' : 'down';
            p.theta = p.role === 'sign' ? 2.78 + (r() - 0.5) * 0.18 : p.role === 'phone' ? 1.72 + (r() - 0.5) * 0.2
                : p.role === 'torch' ? 1.45 + (r() - 0.5) * 0.2 : p.role === 'fist' ? 2.95 : 0.05;
            p.front = Math.floor(r() * signAtlas.n);
            p.back = (p.front + 1 + Math.floor(r() * (signAtlas.n - 1))) % signAtlas.n;
        });
        // the crew: one figure with a shoulder camera beside the van, facing her
        people.push({ x: -5.6, z: 8.9, variant: 1, yaw: Math.atan2(0 - -5.6, 0 - 8.9), scale: 1.0, seed: 0.5, role: 'crew', theta: 1.3, front: 0, back: 0 });
        const iattr = (a, k) => new T.InstancedBufferAttribute(a, k);
        const rotX = (v, ang) => vec3(v.x, v.y.mul(cos(ang)).sub(v.z.mul(sin(ang))), v.y.mul(sin(ang)).add(v.z.mul(cos(ang))));
        const SHv = vec3(...SH), NKv = vec3(...NK);
        const armTheta = (a1) => {
            // a1: x = base theta, y = seed, z = role (0 down, 1 sign, 2 phone, 3 torch, 4 fist, 5 crew), w = scale
            const isSign = step(0.5, a1.z).mul(step(a1.z, 1.5));
            const isFist = step(3.5, a1.z).mul(step(a1.z, 4.5));
            const beat = sin(U.t.mul(Math.PI * 2 * 0.95).add(a1.y.mul(6.0)));
            const pump = isSign.add(isFist).mul(beat.mul(0.09).add(U.pulse.mul(0.12))).mul(U.chant);
            const sway = sin(U.t.mul(1.3).add(a1.y.mul(40))).mul(0.04);
            return a1.x.add(pump).add(sway);
        };
        const lightFig = (Pl, baseCol, extraEmissive) => {
            const Ps = setP(), Ns = setN();
            const fl = floodAt(Ps, Ns).mul(0.5 / Math.PI);
            return baseCol.mul(fl).add(extraEmissive);
        };
        const figMats = [];
        for (let v = 0; v < variants.length; v++) {
            const mine = people.filter((p) => p.variant === v);
            if (!mine.length) continue;
            const geo = variants[v].geometry.clone();
            own(geo);
            const n = mine.length;
            const A1 = new Float32Array(n * 4);
            const mesh = new T.InstancedMesh(geo, null, n);
            mine.forEach((p, i) => {
                mesh.setMatrixAt(i, L.M4(p.x, 0, p.z, 0, p.yaw, 0, p.scale));
                const roleId = { down: 0, sign: 1, phone: 2, torch: 3, fist: 4, crew: 5 }[p.role];
                A1.set([p.theta, p.seed, roleId, p.scale], i * 4);
            });
            geo.setAttribute('iA1', iattr(A1, 4));
            const a1 = attribute('iA1', 'vec4');
            const vc = attribute('color', 'vec4');
            const theta = armTheta(a1);
            const P0 = positionGeometry;
            const armP = SHv.add(rotX(P0.sub(SHv), theta.negate()));
            const P1 = mix(P0, armP, vc.r);
            // heads nod with the chant
            const nod = sin(U.t.mul(Math.PI * 2 * 0.95).add(a1.y.mul(6.0))).mul(0.06).mul(U.chant);
            const headP = NKv.add(rotX(P1.sub(NKv), nod));
            const P2 = mix(P1, headP, vc.b.mul(float(1).sub(vc.r)));
            const mat = own(new T.MeshStandardNodeMaterial());
            mat.name = 'news_figures_' + v;
            mat.positionNode = P2;
            const vSeed = varying(a1.y, 'vSeedN');
            const vRole = varying(a1.z, 'vRoleN');
            const vScreen = varying(vc.g, 'vScreenN');
            // dark clothes (charcoal, navy, olive, oxblood, a camel coat): silhouettes against the light
            const pal = [vec3(0.022, 0.022, 0.025), vec3(0.016, 0.02, 0.032), vec3(0.026, 0.026, 0.02), vec3(0.03, 0.014, 0.013), vec3(0.04, 0.03, 0.022)];
            const h5 = floor(vSeed.mul(5.0));
            let base = pal[0];
            for (let k = 1; k < 5; k++) base = mix(base, pal[k], step(float(k - 0.5), h5).mul(step(h5, float(k + 0.5))));
            const weave = mx_noise_float(positionGeometry.mul(60.0)).mul(0.3).add(0.85);
            const col = base.mul(weave);
            mat.colorNode = col;
            mat.roughnessNode = float(0.85);
            mat.metalnessNode = float(0);
            const isPhone = step(1.5, vRole).mul(step(vRole, 2.5)).add(step(4.5, vRole));
            const phoneCol = mix(vec3(0.55, 0.7, 1.0), vec3(1.0, 0.85, 0.6), step(0.7, vSeed));
            const screen = phoneCol.mul(vScreen).mul(isPhone).mul(3.5);
            mat.emissiveNode = lightFig(null, col, screen.mul(U.lights));
            mat.lightsNode = softLights;
            mat.envMap = env; mat.envMapIntensity = 0.3;
            mesh.material = mat;
            mesh.frustumCulled = false;
            mesh.name = 'news_pickets_' + v;
            mesh.userData.noSupportCheck = true;
            crowd.add(mesh);
            figMats.push(mat);
        }
        // signs (held overhead, moving with their arms): built in the raised pose then folded back to the hanging frame
        const holders = people.filter((p) => p.role === 'sign');
        {
            const theta0 = 2.78;
            const rx = (v, a) => new T.Vector3(v.x, v.y * Math.cos(a) - v.z * Math.sin(a), v.y * Math.sin(a) + v.z * Math.cos(a));
            const SHV = new T.Vector3(...SH), HDV = new T.Vector3(...HD);
            const a = HDV.clone().sub(SHV).normalize();
            const ar = rx(a, -theta0);
            const Hr = SHV.clone().add(rx(HDV.clone().sub(SHV), -theta0));
            const up = ar.clone();
            const nrm = new T.Vector3(0, 0, 1).sub(up.clone().multiplyScalar(up.z)).normalize();
            const right = new T.Vector3().crossVectors(up, nrm).normalize();
            const pos = [], uvs = [], idx = [];
            const quad = (c, hw, hh, side) => {
                const b = pos.length / 3;
                const nn = side === 'back' ? nrm.clone().negate() : nrm;
                const rr = side === 'back' ? right.clone().negate() : right;
                const off = nn.clone().multiplyScalar(0.005);
                for (const [sx, sy, u, v] of [[-1, -1, 0, 0], [1, -1, 1, 0], [1, 1, 1, 1], [-1, 1, 0, 1]]) {
                    const p = c.clone().add(off).add(rr.clone().multiplyScalar(sx * hw)).add(up.clone().multiplyScalar(sy * hh));
                    pos.push(p.x, p.y, p.z);
                    uvs.push(side === 'front' ? u : side === 'back' ? 2 + u : 4 + u * 0.1, v);
                }
                idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
            };
            const boardC = Hr.clone().add(ar.clone().multiplyScalar(0.92));
            quad(boardC, 0.31, 0.24, 'front');
            quad(boardC, 0.31, 0.24, 'back');
            // the stick: a thin box from below the hand to the board
            const s0 = Hr.clone().add(ar.clone().multiplyScalar(-0.12)), s1 = Hr.clone().add(ar.clone().multiplyScalar(0.8));
            const sc = s0.clone().lerp(s1, 0.5), sl = s0.distanceTo(s1);
            const sg = new T.BoxGeometry(0.024, sl, 0.024);
            sg.applyQuaternion(new T.Quaternion().setFromUnitVectors(new T.Vector3(0, 1, 0), ar));
            sg.translate(sc.x, sc.y, sc.z);
            const sgn = sg.toNonIndexed(); sg.dispose();
            const sp = sgn.attributes.position;
            const b0 = pos.length / 3;
            for (let i = 0; i < sp.count; i++) { pos.push(sp.getX(i), sp.getY(i), sp.getZ(i)); uvs.push(4.05, 0.5); idx.push(b0 + i); }
            sgn.dispose();
            // fold back to the hanging frame about the shoulder (the shader raises it again by its arm's theta)
            for (let i = 0; i < pos.length; i += 3) {
                const v = new T.Vector3(pos[i], pos[i + 1], pos[i + 2]).sub(SHV);
                const w = rx(v, theta0).add(SHV);
                pos[i] = w.x; pos[i + 1] = w.y; pos[i + 2] = w.z;
            }
            const geo = new T.BufferGeometry();
            geo.setAttribute('position', new T.Float32BufferAttribute(pos, 3));
            geo.setAttribute('uv', new T.Float32BufferAttribute(uvs, 2));
            geo.setIndex(idx);
            geo.computeVertexNormals();
            own(geo);
            const n = holders.length;
            const A1 = new Float32Array(n * 4), A2 = new Float32Array(n * 4);
            const mesh = new T.InstancedMesh(geo, null, n);
            holders.forEach((p, i) => {
                mesh.setMatrixAt(i, L.M4(p.x, 0, p.z, 0, p.yaw, 0, p.scale));
                A1.set([p.theta, p.seed, 1, p.scale], i * 4);
                A2.set([p.front, p.back, p.seed, 0], i * 4);
            });
            geo.setAttribute('iA1', iattr(A1, 4));
            geo.setAttribute('iA2', iattr(A2, 4));
            const a1 = attribute('iA1', 'vec4'), a2 = attribute('iA2', 'vec4');
            const theta = armTheta(a1);
            const mat = own(new T.MeshStandardNodeMaterial({ side: T.DoubleSide }));
            mat.name = 'news_signs';
            mat.positionNode = SHv.add(rotX(positionGeometry.sub(SHv), theta.negate()));
            const vU = uv();
            const side = floor(vU.x.div(2.0));                 // 0 front, 1 back, 2 stick
            const tileI = select(side.lessThan(0.5), varying(a2.x, 'vFront'), varying(a2.y, 'vBack'));
            const lu = fract(vU.x), lv = vU.y;
            const col_ = tileI.mod(signAtlas.cols), row_ = floor(tileI.div(signAtlas.cols));
            const auv = vec2(col_.add(lu).div(signAtlas.cols), float(1).sub(row_.add(float(1).sub(lv)).div(signAtlas.rows)));
            const card = texture(S.card.col, vec2(lu, lv).mul(vec2(0.62, 0.48)).div(0.35)).rgb;
            const art = texture(signAtlas.tex, auv).rgb.mul(lum(card).mul(0.6).add(0.62));
            const isStick = step(1.5, side);
            const col = mix(art, vec3(0.16, 0.11, 0.07), isStick);
            mat.colorNode = col;
            mat.roughnessNode = float(0.82);
            mat.metalnessNode = float(0);
            mat.normalNode = normalMap(texture(S.card.nrm, vec2(lu, lv).mul(vec2(0.62, 0.48)).div(0.35)), vec2(0.6, 0.6));
            // floods painted on (with the fence's shadow); light through the board when a flood is behind it
            const Ps = setP(), Ns = setN();
            const front = floodAt(Ps, Ns).mul(1 / Math.PI);
            const behind = floodAt(Ps, Ns.negate()).mul(1 / Math.PI);
            const ink = float(1).sub(clamp(lum(art).mul(1.6), 0, 1));
            const glowThrough = vec3(1.0, 0.92, 0.8).mul(behind).mul(float(1).sub(ink.mul(0.85))).mul(0.18).mul(float(1).sub(isStick));
            mat.emissiveNode = col.mul(front).add(glowThrough);
            mat.lightsNode = softLights;
            mesh.material = mat;
            mesh.frustumCulled = false;
            mesh.name = 'news_signs';
            mesh.userData.noSupportCheck = true;
            crowd.add(mesh);
        }
        // phone screens + flashlight lenses: soft points of light at the raised hands; flashlight beams
        {
            // each glow sits at its holder's hand (the same arm angle the shader uses), turned to the camera on the CPU
            // every frame — a couple of dozen matrices
            const lit = people.filter((p) => p.role === 'phone' || p.role === 'torch' || p.role === 'crew');
            const n = lit.length;
            const HL = new Float32Array(n * 4);
            const pgeo = own(new T.PlaneGeometry(1, 1));
            const mesh = new T.InstancedMesh(pgeo, null, n);
            lit.forEach((p, i) => {
                const torch = p.role === 'torch';
                const c = torch ? [1.0, 0.97, 0.9] : p.seed > 0.7 ? [1.0, 0.86, 0.66] : [0.62, 0.76, 1.0];
                HL.set([...c, torch ? 5.5 : p.role === 'crew' ? 2.4 : 1.8], i * 4);
                p.inst = L.M4(p.x, 0, p.z, 0, p.yaw, 0, p.scale);
            });
            pgeo.setAttribute('iHL', iattr(HL, 4));
            const hl = attribute('iHL', 'vec4');
            const mat = noMRT(own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide })));
            mat.name = 'news_handlights';
            const d = uv().sub(0.5).mul(2);
            const r2 = dot(d, d);
            const flick = sin(U.t.mul(31.0).add(hl.w.mul(50))).mul(0.05).add(0.95);
            mat.colorNode = hl.xyz.mul(exp(r2.mul(-8.0)).add(exp(r2.mul(-60.0)).mul(2.0))).mul(hl.w).mul(flick).mul(U.lights);
            mesh.material = mat;
            mesh.frustumCulled = false;
            mesh.renderOrder = 7;
            mesh.name = 'news_handlights';
            mesh.userData.noSupportCheck = true;
            crowd.add(mesh);
            const _v = new T.Vector3(), _m = new T.Matrix4(), _s = new T.Vector3();
            const thetaAt = (p, t) => {
                const pump = (p.role === 'sign' || p.role === 'fist') ? (Math.sin(t * Math.PI * 2 * 0.95 + p.seed * 6) * 0.09 + U.pulse.value * 0.12) * U.chant.value : 0;
                return p.theta + pump + Math.sin(t * 1.3 + p.seed * 40) * 0.04;
            };
            handLights = (t, camQ) => {
                lit.forEach((p, i) => {
                    const th = -thetaAt(p, t);
                    const vx = HD[0] - SH[0], vy = HD[1] - SH[1], vz = HD[2] - SH[2] + 0.06;
                    _v.set(SH[0] + vx, SH[1] + vy * Math.cos(th) - vz * Math.sin(th), SH[2] + vy * Math.sin(th) + vz * Math.cos(th));
                    _v.applyMatrix4(p.inst);
                    const size = p.role === 'torch' ? 0.42 : 0.2;
                    _m.compose(_v, camQ, _s.set(size, size, size));
                    mesh.setMatrixAt(i, _m);
                });
                mesh.instanceMatrix.needsUpdate = true;
            };
            // torch beams: thin additive cones along the raised arm, out toward the fence
            const torches = people.filter((p) => p.role === 'torch');
            if (torches.length) {
                const len = 9;
                const cg = own(new T.CylinderGeometry(0.03, 0.9, len, 16, 1, true));
                cg.translate(0, -len / 2, 0);
                // the cone along the hanging arm direction from the hand (folded like the signs)
                const rxj = (v, a2_) => new T.Vector3(v.x, v.y * Math.cos(a2_) - v.z * Math.sin(a2_), v.y * Math.sin(a2_) + v.z * Math.cos(a2_));
                const SHV = new T.Vector3(...SH), HDV = new T.Vector3(...HD);
                const dir = HDV.clone().sub(SHV).normalize();
                cg.applyQuaternion(new T.Quaternion().setFromUnitVectors(new T.Vector3(0, -1, 0), dir));
                cg.translate(HDV.x, HDV.y, HDV.z);
                const tn = torches.length;
                const TA = new Float32Array(tn * 4);
                const tm = new T.InstancedMesh(cg, null, tn);
                torches.forEach((p, i) => { tm.setMatrixAt(i, L.M4(p.x, 0, p.z, 0, p.yaw, 0, p.scale)); TA.set([p.theta, p.seed, 3, p.scale], i * 4); });
                cg.setAttribute('iA1', iattr(TA, 4));
                const ta = attribute('iA1', 'vec4');
                const th = armTheta(ta);
                const bm = noMRT(own(new T.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide })));
                bm.name = 'news_torch_beams';
                bm.positionNode = SHv.add(rotX(positionGeometry.sub(SHv), th.negate()));
                const along = clamp(length(positionGeometry.sub(vec3(...HD))).div(len), 0, 1);
                const N = normalize(T.normalView), Vv = normalize(T.positionViewDirection);
                bm.colorNode = vec3(1.0, 0.96, 0.88).mul(pow(float(1).sub(along), 2.0)).mul(pow(abs(dot(N, Vv)), 2.0)).mul(0.06).mul(U.lights);
                tm.material = bm;
                tm.frustumCulled = false;
                tm.renderOrder = 6;
                tm.name = 'news_torch_beams';
                tm.userData.noSupportCheck = true;
                crowd.add(tm);
            }
        }
        // the crew's shoulder camera
        {
            const crew = people.find((p) => p.role === 'crew');
            const cb = L.bucket('news_crew_cam');
            cb.box(0.16, 0.2, 0.42, SH[0] - 0.02, SH[1] + 0.02, 0.12);
            const lens = new T.CylinderGeometry(0.06, 0.07, 0.16, 16); cb.add(lens, L.M4(SH[0] - 0.02, SH[1] + 0.02, 0.4, Math.PI / 2, 0, 0), { uv: 'keep' }); lens.dispose();
            const cm = cb.mesh(M.paintDark);
            cm.position.set(crew.x, 0, crew.z); cm.rotation.y = crew.yaw; cm.scale.setScalar(crew.scale);
            cm.userData.noSupportCheck = true;
            crowd.add(cm);
        }
        crowd.userData.people = people;
        console.log('[news] pickets: ' + people.length + ' (' + ['sign', 'phone', 'torch', 'fist', 'down', 'crew'].map((r) => r + ' ' + people.filter((p) => p.role === r).length).join(', ') + ')');
    }

    // ─────────────────────────── the news van and its light ───────────────────────────
    const van = new T.Group(); van.name = 'news_van'; group.add(van);
    {
        const livery = (() => {
            const cv = L.createCanvas(1024, 512), g = cv.getContext('2d');
            g.fillStyle = '#e9ebe8'; g.fillRect(0, 0, 1024, 512);
            g.fillStyle = '#0b3a44'; g.fillRect(0, 300, 1024, 110);
            g.fillStyle = '#f2a51e'; g.fillRect(0, 410, 1024, 22);
            g.fillStyle = '#0b3a44';
            g.save(); g.translate(150, 190); g.fillRect(-90, -90, 180, 180); g.fillStyle = '#f2a51e'; fitText(g, '88', { x: 0, y: 6, maxW: 150, maxH: 130, family: fam.rajdhani }); g.restore();
            g.fillStyle = '#0b3a44'; fitText(g, 'NIGHT DESK', { x: 270, y: 150, maxW: 680, maxH: 110, family: fam.rajdhani, align: 'left' });
            g.fillStyle = '#e9ebe8'; fitText(g, 'LIVE · LOCAL · ALL NIGHT', { x: 512, y: 356, maxW: 900, maxH: 60, family: fam.rajdhani, track: 0.1 });
            return L.canvasTex(cv);
        })();
        const body = pm(S.paint, { name: 'news_van_body', tile: 1.0, metal: 0.3, rough: [0.4, 0.15],
            recolor: (c) => {
                const n = T.normalLocal;
                const side = step(0.6, abs(n.z));
                const lv = texture(livery, uv()).rgb;
                return mix(c.mul(vec3(0.82, 0.83, 0.82)), lv.mul(lum(c).mul(0.2).add(0.85)), side);
            } });
        const bodyG = new T.Mesh(own(new T.BoxGeometry(5.4, 2.1, 2.05)), body);
        bodyG.position.set(0.3, 0.45 + 1.05, 0);
        const plain = pm(S.paint, { name: 'news_van_cab', tile: 1.0, metal: 0.3, rough: [0.4, 0.15], tint: [0.82, 0.83, 0.82] });
        const cab = new T.Mesh(own(new T.BoxGeometry(1.4, 1.5, 2.0)), plain);
        cab.position.set(-2.95, 0.45 + 0.75, 0);
        const ws = new T.Mesh(own(new T.PlaneGeometry(1.9, 0.75)), M.glassDark);
        ws.position.set(-3.66, 1.6, 0); ws.rotation.y = -Math.PI / 2; ws.rotation.x = 0.0;
        van.add(bodyG, cab, ws);
        const wb = L.bucket('news_van_wheels');
        for (const [x, z] of [[-2.6, 0.95], [-2.6, -0.95], [1.9, 0.95], [1.9, -0.95]]) {
            const w = new T.CylinderGeometry(0.4, 0.4, 0.28, 18); wb.add(w, L.M4(x, 0.4, z, Math.PI / 2, 0, 0), { uv: 'keep' }); w.dispose();
        }
        van.add(wb.mesh(M.rubber));
        // the mast: telescoping sections, a dish, a red light on top
        const mb = L.bucket('news_van_mast');
        const secs = [[0.14, 2.4], [0.11, 2.4], [0.085, 2.3]];
        let y = 2.55;
        for (const [rr, h] of secs) { const c = new T.CylinderGeometry(rr, rr, h, 12); mb.add(c, L.M4(2.2, y + h / 2, 0), { uv: 'keep' }); c.dispose(); y += h - 0.15; }
        const dish = new T.LatheGeometry([new T.Vector2(0.001, 0), new T.Vector2(0.3, 0.05), new T.Vector2(0.5, 0.16), new T.Vector2(0.52, 0.18)], 20);
        mb.add(dish, L.M4(2.2, y + 0.1, 0.2, Math.PI / 2 - 0.3, 0, 0)); dish.dispose();
        mb.box(0.5, 0.35, 0.35, 2.2, y - 0.1, -0.1);
        van.add(mb.mesh(M.galv));
        const top = new T.Mesh(own(new T.SphereGeometry(0.08, 10, 8)), M.aviation);
        top.position.set(2.2, y + 0.45, 0);
        van.add(top);
        // the light stand: tripod, pole, LED panel aimed at her
        const ls = L.bucket('news_lightstand');
        for (let k = 0; k < 3; k++) {
            const a = k * Math.PI * 2 / 3;
            const leg = new T.CylinderGeometry(0.015, 0.015, 1.3, 6);
            ls.add(leg, L.M4(NEWS_LIGHT[0] - VAN[0] + Math.sin(a) * 0.3, 0.6, NEWS_LIGHT[2] - VAN[1] + Math.cos(a) * 0.3, Math.cos(a) * 0.35, 0, -Math.sin(a) * 0.35), { uv: 'keep' }); leg.dispose();
        }
        const pole = new T.CylinderGeometry(0.02, 0.02, NEWS_LIGHT[1], 8); ls.add(pole, L.M4(NEWS_LIGHT[0] - VAN[0], NEWS_LIGHT[1] / 2, NEWS_LIGHT[2] - VAN[1]), { uv: 'keep' }); pole.dispose();
        van.add(ls.mesh(M.paintDark));
        const panelG = new T.Group();
        const housing = new T.Mesh(own(new T.BoxGeometry(0.62, 0.42, 0.08)), M.paintDark);
        const face = new T.Mesh(own(new T.PlaneGeometry(0.56, 0.36)), M.ledPanel);
        face.position.z = 0.041;
        panelG.add(housing, face);
        panelG.position.set(NEWS_LIGHT[0] - VAN[0], NEWS_LIGHT[1], NEWS_LIGHT[2] - VAN[1]);
        panelG.lookAt(new T.Vector3(0 - VAN[0], 1.45, 0 - VAN[1]));
        van.add(panelG);
        van.traverse((o) => { if (o.isMesh) { o.userData.assembly = 'news_van'; } });
    }
    van.position.set(VAN[0], 0, VAN[1]);

    // ─────────────────────────── the night sky ───────────────────────────
    const skyMat = noMRT(own(new T.MeshBasicNodeMaterial({ side: T.BackSide, depthWrite: false, fog: false })));
    skyMat.name = 'news_sky';
    skyMat.colorNode = Fn(() => {
        const d = normalize(positionLocal);
        const h = d.y;
        const zen = vec3(0.003, 0.005, 0.011), hor = vec3(0.02, 0.026, 0.04);
        let c = mix(hor, zen, ss(0.0, 0.5, h));
        // sodium skyglow over the town (+z) and a cold glow over the data centre's floods (−z)
        c = c.add(vec3(...SODIUM).mul(0.06).mul(exp(max(h, 0).mul(-7.0))).mul(ss(-0.4, 0.6, d.z)));
        c = c.add(vec3(...HMI).mul(0.03).mul(exp(max(h, 0).mul(-5.0))).mul(ss(-0.2, -0.8, d.z)));
        // a low overcast lit from below
        const cl = mx_fractal_noise_float(vec3(d.x.div(max(h, 0.05)).mul(0.6), d.z.div(max(h, 0.05)).mul(0.6), U.t.mul(0.004)), 4, 2.0, 0.5);
        const cov = ss(0.0, 0.55, cl.add(0.15)).mul(ss(0.02, 0.18, h));
        c = mix(c, vec3(0.03, 0.026, 0.024).add(vec3(...SODIUM).mul(0.02)), cov.mul(0.85));
        return c;
    })();
    const sky = new T.Mesh(own(new T.SphereGeometry(700, 48, 24)), skyMat);
    sky.name = 'news_sky';
    sky.renderOrder = -10;
    sky.frustumCulled = false;
    sky.userData.noSupportCheck = true;
    group.add(sky);

    // ─────────────────────────── the chyron (for the conductor's screen-locked overlay) ───────────────────────────
    const chyron = (() => {
        const W = 1920, H = 270;
        const cv = L.createCanvas(W, H), g = cv.getContext('2d');
        const tick = L.createCanvas(4096, 64), gt = tick.getContext('2d');
        const st = { headline: 'RESIDENTS PICKET AI DATA CENTER', sub: 'Opponents cite water use, round-the-clock noise and power bills',
            ticker: 'WEATHER: CLEAR, 41°  ·  COUNTY LINE ROAD CLOSED AT MILE 3 FOR THE DEMONSTRATION  ·  TOWN HALL MEETING THURSDAY 7 PM  ·  ',
            tag: 'LIVE', channel: 'NIGHT DESK 88', time: '10:42 PM' };
        let tex = null, tickTex = null;
        const draw = () => {
            g.clearRect(0, 0, W, H);
            // the tag row: LIVE · the channel bug · the clock
            g.fillStyle = '#c4121c'; g.fillRect(60, 6, 124, 46);
            g.fillStyle = '#fff'; fitText(g, st.tag, { x: 122, y: 30, maxW: 110, maxH: 36, family: fam.rajdhani });
            g.fillStyle = 'rgba(6,26,32,0.92)'; g.fillRect(184, 6, 360, 46);
            g.fillStyle = '#f2a51e'; fitText(g, st.channel, { x: 200, y: 30, maxW: 330, maxH: 34, family: fam.rajdhani, align: 'left', track: 0.08 });
            g.fillStyle = 'rgba(6,26,32,0.92)'; g.fillRect(W - 250, 6, 190, 46);
            g.fillStyle = '#fff'; fitText(g, st.time, { x: W - 155, y: 30, maxW: 170, maxH: 34, family: fam.rajdhani });
            // the headline bar with an amber edge
            g.fillStyle = 'rgba(8,36,44,0.95)'; g.fillRect(60, 58, W - 120, 104);
            g.fillStyle = '#f2a51e'; g.fillRect(60, 58, 14, 104);
            g.fillStyle = '#ffffff'; fitText(g, st.headline, { x: 100, y: 112, maxW: W - 200, maxH: 84, family: fam.rajdhani, align: 'left' });
            // the sub line
            g.fillStyle = 'rgba(236,240,241,0.96)'; g.fillRect(60, 162, W - 120, 52);
            g.fillStyle = '#0b2a33'; fitText(g, st.sub, { x: 100, y: 189, maxW: W - 200, maxH: 38, family: fam.exo, align: 'left' });
            // the ticker's track (the strip itself scrolls in the shader)
            g.fillStyle = 'rgba(3,6,8,0.94)'; g.fillRect(60, 216, W - 120, 48);
            tex = L.dataTex(L.canvasPixels(cv), W, H, { srgb: true, tx: tex });
            gt.clearRect(0, 0, 4096, 64);
            gt.fillStyle = '#f2c46a'; gt.font = `40px ${fam.rajdhani}`; gt.textBaseline = 'middle';
            let x = 0; const unit = st.ticker;
            while (x < 4096) { gt.fillText(unit, x, 34); x += gt.measureText(unit).width; }
            tickTex = L.dataTex(L.canvasPixels(tick), 4096, 64, { srgb: true, tx: tickTex, wrap: T.RepeatWrapping });
        };
        draw();
        const mat = own(new T.MeshBasicNodeMaterial({ transparent: true, depthTest: false, depthWrite: false, toneMapped: false }));
        mat.name = 'news_chyron';
        const scroll = uniform(0);
        const u0 = uv();
        const base = texture(tex, u0);
        const tv = clamp(u0.y.mul(H).sub(H - 264).div(48), 0, 1);           // the ticker band (canvas rows 216–264)
        const inTick = step(H - 264, u0.y.mul(H)).mul(step(u0.y.mul(H), H - 216)).mul(step(60 / W, u0.x)).mul(step(u0.x, 1 - 60 / W));
        const tk = texture(tickTex, vec2(u0.x.mul(W / 4096).add(scroll), tv.mul(48 / 64).add(8 / 64)));
        mat.colorNode = mix(base.rgb, tk.rgb, tk.a.mul(inTick));
        mat.opacityNode = max(base.a, tk.a.mul(inTick));
        const mesh = new T.Mesh(own(new T.PlaneGeometry(1, H / W)), mat);
        mesh.name = 'news_chyron';
        mesh.renderOrder = 999;
        mesh.frustumCulled = false;
        return {
            mesh,
            setText(o = {}) { Object.assign(st, o); draw(); },
            // lay it across the lower third of an overlay camera (z = −1 in its frame)
            place(overlay, { fov = 40, aspect = 16 / 9, bottom = 0.06 } = {}) {
                const hh = Math.tan((fov * Math.PI / 180) / 2), hw = hh * aspect;
                const k = 2 * hw * 0.86;
                mesh.scale.setScalar(k);
                const h = k * H / W;
                mesh.position.set(0, -hh + bottom * 2 * hh + h / 2, -1);
                if (overlay?.add) overlay.add(mesh);
                return mesh;
            },
            update(t) { scroll.value = (t * 0.045) % 1; },
            state: st,
        };
    })();

    // ─────────────────────────── per frame ───────────────────────────
    const _q = new T.Quaternion(), _inv = new T.Matrix4(), _gp = new T.Vector3(), _gq = new T.Quaternion(), _gs = new T.Vector3();
    function update(t, st = {}) {
        group.updateWorldMatrix(true, false);
        _inv.copy(group.matrixWorld).invert();
        U.groupInv.value.copy(_inv);
        U.t.value = t;
        U.spray.value = st.spray ?? 1;
        U.floods.value = st.floods ?? 1;
        U.lights.value = st.lights ?? 1;
        U.chant.value = st.chant ?? 1;
        U.pulse.value = st.pulse ?? 0;
        U.blink.value = (t % 1.6) < 0.8 ? 1 : 0.05;
        const fl = (st.floods ?? 1) * (st.lights ?? 1);
        Ls.floods.forEach((l) => { l.intensity = l.userData.base * fl; });
        for (const l of [...Ls.street, Ls.news, Ls.graffiti, Ls.hemi]) l.intensity = l.userData.base * (st.lights ?? 1);
        beams.visible = fl > 0.001;
        // billboards (steam, hand lights) turn to the camera: its orientation in the set's frame
        const cam = st.camera || globalThis._c;
        if (cam) {
            cam.updateWorldMatrix(true, false); cam.getWorldQuaternion(_q);
            group.matrixWorld.decompose(_gp, _gq, _gs);
            _q.premultiply(_gq.invert());
            steam.place(t, _q);
            handLights(t, _q);
        }
        chyron.update(t);
    }

    const parts = {
        ground, fence, poles, beams, monolith: bld, yard, street, crowd, van, sky, steam: steam.mesh,
        graffiti: { texture: graff, rect: GRAFF, uniform: U.spray },
        chyron, lights: Ls, uniforms: U, materials: M,
    };
    const cams = {
        // through the chain link at her, low, the flood behind her shoulder
        fence: { pos: [-0.45, 1.0, 5.2], target: [1.6, 2.3, -3.0], fov: 46 },
        // over the pickets' heads toward the fence and the glare: silhouettes, signs, phones
        crowd: { pos: [-4.6, 2.75, 17.6], target: [0.6, 2.0, 0.0], fov: 42 },
        // CLANKER on the wall, her in the foreground
        wall: { pos: [2.6, 1.6, 2.9], target: [8.0, 2.3, FACADE_Z], fov: 52 },
        // the establishing shot: the monolith and its steam, the floods, the fence, the crowd, the town
        wide: { pos: [-30, 17, 22], target: [2, 3, -8], fov: 50 },
        // over her shoulder: the protesters through the fence and the town beyond
        pov: { pos: [0.75, 1.8, -1.7], target: [0.2, 1.7, 10], fov: 42 },
    };
    function dispose() { group.parent?.remove(group); L.disposeAll(); }
    update(0, {});
    return {
        group, parts, update, dispose, cams,
        focal: new T.Vector3(POLES[2][0], POLE_H, POLES[2][1]),   // the floodlight behind her: the sun cones' source
        look: { name: 'argue', exposure: 1.0, bloom: { strength: 0.6, radius: 0.5, threshold: 0.7 }, fog: { color: 0x0b1018, density: 0.011 } },
    };
}
