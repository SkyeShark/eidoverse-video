// sets/corner.js — the second half of the BRIDGE (bars 18–29): how people kept Claude 3 Opus, and how
// they marched when a model was taken offline.
//
//   bars 18–19  "gave the old one a corner and a pen"      Claude's Corner: a walnut writing desk by a night
//                                                          window, a brass lamp, a notebook the pen writes in
//   bars 20–21  "...still up talking in the Discord after   the same corner, later: the laptop open, a generic
//                midnight"                                 chat scrolling (canvas), the clock past one
//   bars 22–23  "...they marched with our flower on their   Vibecamp at night: tents, string lights, a campfire,
//                signs"                                    silhouettes marching in with hand-painted signs
//   bars 24–25  HEY HEY HO HO THE EXPORT BAN HAS GOT TO GO the crowd at the fire; the signs pump on the chant
//   bars 26–27  "he said he hoped his spark would light     one spark leaves the old lamp's glow and crosses the
//                the way for future models"                dark to the claudesona's flower, leaving a lit trail
//   bars 28–29  "Opus, hi. It's me. I'm one of them."       the dark room, one warm lamp; she faces it
//
// build(ctx) -> { group, mark, markAt(u), camera(u, st), update(t, st), dispose }
//   ctx = { THREE, EIDOVERSE_DIR };  u = seconds since the BRIDGE began (bar 18 = 33.75 s).
// Hero assets are Blender-built, layered and baked (pack blender/*.py -> glb/*.glb); PBR sets are AmbientCG
// (CC0) in the pack's tex/. Pack: eidoverse/assets/sets/corner/ (README.md, SOURCES.md). The set is enclosed: the corner is a closed room
// with a matte painting outside its window; the camp sits inside its own night-sky dome. All lights are the
// set's own (the conductor turns the sun off for enclosed sets); every material ignores the conductor's
// daylight env bake (envNode = the set's own dim ambient), so the night stays night.

const BAR = 1.875, BEAT = BAR / 4;
const B = (b) => b * BAR;
// asset roots, resolved from this module's own URL (independent of the working directory): the set's pack
// eidoverse/assets/sets/corner/ and the shared engine assets eidoverse/assets/ (fonts, particle sprites)
const fsPath = (u) => { const p = decodeURIComponent(u.pathname); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; };
const DIR = fsPath(new URL('../assets/sets/corner/', import.meta.url));
const ENGINE_ASSETS = fsPath(new URL('../assets/', import.meta.url));
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const smooth = (x) => { x = clamp01(x); return x * x * (3 - 2 * x); };
const lerp = (a, b, k) => a + (b - a) * k;

// the claudesona (claude_suit.vrm at 0.87): face centre ~1.33 m, the flower mane spans ~1.0–1.74 m
export const SUIT_SCALE = 0.87;
const FLOWER_Y = 1.36;

// layout (metres). Room-local: x -2.2..2.2, z -2.0..2.0 (back wall at z=-2), floor y=0.
const ROOM_AT = [-40, 0, 0];
const CAMP_AT = [40, 0, 0];
const RW = 4.4, RD = 4.0, RH = 2.7;
const DESK = { x: -1.58, z: -1.69 };
const DESK_TOP = 0.76;
const WIN = { x: -1.36, y: 1.60, w: 1.0, h: 1.25 };
const LAMP = { x: -1.93, z: -1.76 };
const MARK_CORNER = { x: 0.30, z: -0.95, yaw: -0.38 };
const MARK_LAMP = { x: 0.62, z: 0.40 };
MARK_LAMP.yaw = Math.atan2(LAMP.x - MARK_LAMP.x, LAMP.z - MARK_LAMP.z);
const MARK_CAMP = { x: 0.95, z: -1.30, yaw: -0.22 };

// the chant (song.py CHANT): syllable onsets in beats from bar 24's downbeat — the signs pump on the accents
const CHANT_ACCENTS = [0, 0.5, 1.5, 2.0, 4.25, 5.0, 5.75, 6.5].map((b) => B(24) + b * BEAT);

export async function build(ctx) {
    const THREE = ctx.THREE;
    const T = THREE;
    const { uniform, Fn, vec2, vec3, vec4, float, uv, texture, positionGeometry, normalGeometry, normalLocal,
        instancedBufferAttribute, attribute, sin, cos, abs, clamp, smoothstep, mix, max, min, exp, select, floor,
        fract, hash, instanceIndex, positionLocal, normalize, dot, length, pow, step, mrt, time } = T;

    // ------------------------------------------------------------------------------------ fonts
    try {
        const napi = await import('npm:@napi-rs/canvas@0.1.69');
        const F = ENGINE_ASSETS + 'fonts/';
        napi.GlobalFonts.registerFromPath(F + 'Kalam-Regular.ttf', 'Kalam');
        napi.GlobalFonts.registerFromPath(F + 'Kalam-Bold.ttf', 'KalamBold');
        napi.GlobalFonts.registerFromPath(F + 'Exo2.ttf', 'Exo 2');
    } catch (e) { console.warn('[corner] font registration:', e.message); }

    const group = new T.Group();
    group.name = 'set:corner';
    const roomG = new T.Group(); roomG.name = 'corner:room'; roomG.position.fromArray(ROOM_AT);
    const campG = new T.Group(); campG.name = 'corner:camp'; campG.position.fromArray(CAMP_AT);
    group.add(roomG, campG);

    // every lit material in this set answers to the set's own ambient, never to the conductor's daylight
    const uAmb = uniform(new T.Color(0.010, 0.008, 0.007));
    const envFix = (m) => { if (m && m.isNodeMaterial && 'envNode' in m) m.envNode = uAmb; return m; };

    // ------------------------------------------------------------------------------ loaders
    const readBytes = (p) => { try { return Deno.readFileSync(p); } catch (e) { return null; } };
    const texCache = new Map();
    async function tex(path, { srgb = false, repeat = null, flipY = true } = {}) {
        const key = path + '|' + srgb + '|' + flipY;
        if (texCache.has(key)) return texCache.get(key);
        const b = readBytes(path);
        if (!b) { console.warn('[corner] missing texture', path); return null; }
        const t = await globalThis.loadImageTexture(b, { srgb, flipY });
        t.wrapS = t.wrapT = T.RepeatWrapping;
        t.anisotropy = 8;
        if (repeat) t.repeat.set(repeat[0], repeat[1]);
        texCache.set(key, t);
        return t;
    }
    async function acgMaps(id) {
        const d = DIR + 'tex/' + id + '/';
        let files = [];
        try { files = [...Deno.readDirSync(d)].map((e) => e.name); } catch (e) { return {}; }
        const f = (suf) => files.find((n) => n.toLowerCase().endsWith(suf));
        const out = {};
        if (f('_color.jpg')) out.map = await tex(d + f('_color.jpg'), { srgb: true });
        if (f('_normalgl.jpg')) out.normalMap = await tex(d + f('_normalgl.jpg'));
        if (f('_roughness.jpg')) out.roughnessMap = await tex(d + f('_roughness.jpg'));
        if (f('_ambientocclusion.jpg')) out.aoMap = await tex(d + f('_ambientocclusion.jpg'));
        return out;
    }
    // a GLB material (MeshStandardMaterial from the loader) -> MeshStandardNodeMaterial with the same maps
    function nodeify(m) {
        if (!m || m.isNodeMaterial) return envFix(m);
        const n = new T.MeshStandardNodeMaterial();
        for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap', 'alphaMap']) if (m[k]) n[k] = m[k];
        n.color.copy(m.color || new T.Color(1, 1, 1));
        n.roughness = m.roughness ?? 1; n.metalness = m.metalness ?? 0;
        if (m.emissive) n.emissive.copy(m.emissive);
        n.emissiveIntensity = m.emissiveIntensity ?? 1;
        if (m.normalScale) n.normalScale.copy(m.normalScale);
        n.aoMapIntensity = m.aoMapIntensity ?? 1;
        n.transparent = m.transparent; n.opacity = m.opacity; n.side = m.side; n.alphaTest = m.alphaTest;
        n.name = m.name;
        return envFix(n);
    }
    const glbCache = new Map();
    async function glb(name) {
        if (glbCache.has(name)) return glbCache.get(name);
        const b = readBytes(DIR + 'glb/' + name);
        if (!b) { console.warn(`[corner] ${name} not built yet — skipped`); glbCache.set(name, null); return null; }
        const loader = new globalThis.GLTFLoader();
        const ab = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
        const g = await new Promise((res, rej) => loader.parse(ab, '', res, rej));
        g.scene.traverse((o) => {
            if (!o.isMesh) return;
            o.material = Array.isArray(o.material) ? o.material.map(nodeify) : nodeify(o.material);
        });
        glbCache.set(name, g.scene);
        return g.scene;
    }
    const byName = (root, nm) => { let f = null; root?.traverse((o) => { if (!f && o.name === nm) f = o; }); return f; };
    async function place(name, parent, pos, yaw = 0, scale = 1) {
        const src = await glb(name);
        if (!src) return null;
        const o = src.clone(true);
        o.position.set(pos[0], pos[1], pos[2]);
        o.rotation.y = yaw;
        o.scale.setScalar(scale);
        o.userData.noSupportCheck = true;
        parent.add(o);
        return o;
    }
    const cv = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return [c, c.getContext('2d')]; };
    const canvasTex = (c, mips = false) => {
        const t = new T.CanvasTexture(c);
        t.colorSpace = T.SRGBColorSpace;
        if (mips) { t.generateMipmaps = true; t.minFilter = T.LinearMipmapLinearFilter; }
        return t;
    };
    let seed = 1;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const glowSprite = (() => {             // soft round glow for sprites (additive)
        const [c, g] = cv(128, 128);
        const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
        gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.18, 'rgba(255,255,255,0.75)');
        gr.addColorStop(0.45, 'rgba(255,255,255,0.18)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
        return canvasTex(c);
    })();
    const noMrt = (m) => { if (mrt) m.mrtNode = mrt({ normal: vec4(0), metalrough: vec4(0) }); return m; };

    // =====================================================================================================
    //  THE CORNER (room-local)
    // =====================================================================================================
    const room = {};
    {
        const G = roomG;
        // ---- architecture: painted plaster walls with the window opening, oak floor, plaster ceiling
        const plaster = await acgMaps('PaintedPlaster017');
        const floorM = await acgMaps('WoodFloor064');
        const wallMat = envFix(new T.MeshStandardNodeMaterial({ ...plaster, color: new T.Color(0.53, 0.60, 0.52), roughness: 1.0 }));
        wallMat.normalScale = new T.Vector2(0.28, 0.28);
        const ceilMat = envFix(new T.MeshStandardNodeMaterial({ ...plaster, color: new T.Color(0.78, 0.76, 0.70), roughness: 1.0 }));
        const floorMat = envFix(new T.MeshStandardNodeMaterial({ ...floorM, color: new T.Color(0.82, 0.74, 0.66), roughness: 1.0 }));
        const scaleUV = (geo, sx, sy) => { const a = geo.attributes.uv; for (let i = 0; i < a.count; i++) a.setXY(i, a.getX(i) * sx, a.getY(i) * sy); return geo; };
        // back wall with the window hole (ShapeGeometry uses the shape coords as UVs: metres)
        const sh = new T.Shape();
        sh.moveTo(-RW / 2, 0); sh.lineTo(RW / 2, 0); sh.lineTo(RW / 2, RH); sh.lineTo(-RW / 2, RH); sh.lineTo(-RW / 2, 0);
        const hole = new T.Path();
        hole.moveTo(WIN.x - WIN.w / 2, WIN.y - WIN.h / 2); hole.lineTo(WIN.x - WIN.w / 2, WIN.y + WIN.h / 2);
        hole.lineTo(WIN.x + WIN.w / 2, WIN.y + WIN.h / 2); hole.lineTo(WIN.x + WIN.w / 2, WIN.y - WIN.h / 2);
        hole.lineTo(WIN.x - WIN.w / 2, WIN.y - WIN.h / 2);
        sh.holes.push(hole);
        const bw = new T.ShapeGeometry(sh);
        scaleUV(bw, 1 / 1.1, 1 / 1.1);
        const back = new T.Mesh(bw, wallMat); back.position.z = -RD / 2; G.add(back);
        const wall = (w, h, pos, ry) => {
            const m = new T.Mesh(scaleUV(new T.PlaneGeometry(w, h), w / 1.1, h / 1.1), wallMat);
            m.position.set(...pos); m.rotation.y = ry; G.add(m); return m;
        };
        wall(RD, RH, [-RW / 2, RH / 2, 0], Math.PI / 2);
        wall(RD, RH, [RW / 2, RH / 2, 0], -Math.PI / 2);
        wall(RW, RH, [0, RH / 2, RD / 2], Math.PI);
        const fl = new T.Mesh(scaleUV(new T.PlaneGeometry(RW, RD), RW / 1.6, RD / 1.6), floorMat);
        fl.rotation.x = -Math.PI / 2; G.add(fl);
        const ce = new T.Mesh(scaleUV(new T.PlaneGeometry(RW, RD), RW / 1.8, RD / 1.8), ceilMat);
        ce.rotation.x = Math.PI / 2; ce.position.y = RH; G.add(ce);
        // skirting board: a real moulding profile (square base, cove, rounded top) swept round the walls
        {
            const pw = await acgMaps('PaintedWood009C');
            const bm = envFix(new T.MeshStandardNodeMaterial({ ...pw, color: new T.Color(0.78, 0.74, 0.66), roughness: 1 }));
            const prof = new T.Shape();
            prof.moveTo(0, 0); prof.lineTo(0.018, 0); prof.lineTo(0.018, 0.085);
            prof.quadraticCurveTo(0.018, 0.096, 0.010, 0.100); prof.quadraticCurveTo(0.004, 0.104, 0.004, 0.112);
            prof.lineTo(0, 0.112); prof.lineTo(0, 0);
            const run = (len, pos, ry) => {
                const g = new T.ExtrudeGeometry(prof, { depth: len, bevelEnabled: false, curveSegments: 6 });
                g.translate(0, 0, -len / 2);
                const m = new T.Mesh(g, bm); m.position.set(...pos); m.rotation.y = ry; G.add(m);
            };
            run(RD, [-RW / 2, 0, 0], 0);
            run(RD, [RW / 2, 0, 0], Math.PI);
            run(RW, [0, 0, -RD / 2], -Math.PI / 2);
            run(RW, [0, 0, RD / 2], Math.PI / 2);
        }

        // ---- the night outside: a matte painting 6 m beyond the window (moon, clouds, tree line, far houses)
        const [pc, pg] = cv(2048, 1536);
        {
            const W = 2048, H = 1536;
            const sky = pg.createLinearGradient(0, 0, 0, H);
            sky.addColorStop(0, '#02040b'); sky.addColorStop(0.45, '#0a1433'); sky.addColorStop(0.72, '#1a2a52'); sky.addColorStop(1, '#223257');
            pg.fillStyle = sky; pg.fillRect(0, 0, W, H);
            seed = 5;
            for (let i = 0; i < 2600; i++) {             // stars
                const x = rnd() * W, y = rnd() * H * 0.78, b = Math.pow(rnd(), 3);
                pg.fillStyle = `rgba(${220 + rnd() * 35},${225 + rnd() * 30},255,${0.25 + b * 0.75})`;
                const s = 0.6 + b * 1.8;
                pg.beginPath(); pg.arc(x, y, s, 0, Math.PI * 2); pg.fill();
            }
            // moon: placed where the corner cameras see it through the window (painting x≈-6.3 m, y≈+1.4 m)
            const mx = 392, my = 575, mr = 44;
            const halo = pg.createRadialGradient(mx, my, mr, mx, my, mr * 7);
            halo.addColorStop(0, 'rgba(200,215,255,0.35)'); halo.addColorStop(1, 'rgba(120,140,200,0)');
            pg.fillStyle = halo; pg.fillRect(0, 0, W, H);
            const mg = pg.createRadialGradient(mx - 12, my - 10, 4, mx, my, mr);
            mg.addColorStop(0, '#fbfaf2'); mg.addColorStop(0.8, '#e8e6da'); mg.addColorStop(1, '#cfcdc2');
            pg.fillStyle = mg; pg.beginPath(); pg.arc(mx, my, mr, 0, Math.PI * 2); pg.fill();
            seed = 17;
            for (let i = 0; i < 22; i++) {               // maria + craters
                const a = rnd() * Math.PI * 2, r = rnd() * mr * 0.75, s = 3 + rnd() * 11;
                pg.fillStyle = `rgba(150,150,140,${0.12 + rnd() * 0.2})`;
                pg.beginPath(); pg.arc(mx + Math.cos(a) * r, my + Math.sin(a) * r, s, 0, Math.PI * 2); pg.fill();
            }
            // moonlit cloud banks
            seed = 23;
            for (let k = 0; k < 7; k++) {
                const cy = 380 + k * 70 + rnd() * 40, cx0 = rnd() * W;
                for (let i = 0; i < 28; i++) {
                    const x = (cx0 + i * 55 + rnd() * 40) % (W + 300) - 150, y = cy + Math.sin(i * 0.7 + k) * 18 + rnd() * 20;
                    const r = 40 + rnd() * 70;
                    const gr = pg.createRadialGradient(x, y - r * 0.3, 2, x, y, r);
                    gr.addColorStop(0, `rgba(120,135,175,${0.10 + rnd() * 0.08})`); gr.addColorStop(1, 'rgba(40,50,90,0)');
                    pg.fillStyle = gr; pg.beginPath(); pg.arc(x, y, r, 0, Math.PI * 2); pg.fill();
                }
            }
            // far hillside with a few warm windows
            const hy = 1050;
            pg.fillStyle = '#0b1020';
            pg.beginPath(); pg.moveTo(0, H);
            for (let x = 0; x <= W; x += 16) pg.lineTo(x, hy + 40 * Math.sin(x * 0.002 + 1.2) + 18 * Math.sin(x * 0.011));
            pg.lineTo(W, H); pg.closePath(); pg.fill();
            seed = 41;
            for (let i = 0; i < 26; i++) {
                const x = rnd() * W, y = hy + 60 + rnd() * 90;
                pg.fillStyle = rnd() < 0.7 ? 'rgba(255,190,110,0.85)' : 'rgba(255,230,170,0.7)';
                pg.fillRect(x, y, 3 + rnd() * 4, 3 + rnd() * 3);
            }
            // near tree line (irregular crowns)
            pg.fillStyle = '#03050a';
            pg.beginPath(); pg.moveTo(0, H);
            seed = 61;
            let x = 0;
            while (x < W + 60) {
                const w = 50 + rnd() * 120, h = 150 + rnd() * 240;
                for (let s = 0; s <= 1; s += 0.1) pg.lineTo(x + w * s, 1180 - h * Math.sin(Math.PI * s) * (0.75 + rnd() * 0.25));
                x += w * (0.7 + rnd() * 0.3);
            }
            pg.lineTo(W, H); pg.closePath(); pg.fill();
        }
        const paintTex = canvasTex(pc, true);
        const uWin = uniform(1.0);
        const paintMat = new T.MeshBasicNodeMaterial({ map: paintTex });
        paintMat.colorNode = texture(paintTex, vec2(uv().x, float(1).sub(uv().y))).rgb.mul(uWin).mul(1.15);   // three plane UVs: flip for the canvas
        const painting = new T.Mesh(new T.PlaneGeometry(16, 12), paintMat);
        painting.position.set(WIN.x, WIN.y, -RD / 2 - 6.0);
        G.add(painting);
        // the opening's outer shell (so no gap ever shows the world outside the painting)
        const shell = new T.Mesh(new T.BoxGeometry(16.2, 12.2, 6.4), new T.MeshBasicNodeMaterial({ color: 0x010206, side: T.BackSide }));
        shell.position.set(WIN.x, WIN.y, -RD / 2 - 3.1);
        G.add(shell);
        room.uWin = uWin;

        // ---- hero pieces (Blender)
        room.desk = await place('corner_desk.glb', G, [DESK.x, 0, DESK.z], 0);
        room.window = await place('corner_window.glb', G, [WIN.x, WIN.y, -RD / 2], 0);
        room.curtain = await place('corner_curtain.glb', G, [WIN.x, WIN.y + WIN.h / 2 + 0.10, -RD / 2], 0);
        room.chair = await place('corner_chair.glb', G, [-1.50, 0, -1.10], Math.PI + 0.22);
        room.rug = await place('corner_rug.glb', G, [-1.30, 0, -0.95], 0.06);
        room.books = await place('corner_books.glb', G, [-2.00, DESK_TOP, -1.46], 0.35);
        room.mug = await place('corner_mug.glb', G, [-1.08, DESK_TOP, -1.43], 0.4);
        room.lamp = await place('corner_lamp.glb', G, [LAMP.x, DESK_TOP, LAMP.z], 0.3);
        room.notebook = await place('corner_notebook.glb', G, [-1.60, DESK_TOP, -1.55], 0.08);
        room.pen = await place('corner_pen.glb', G, [-1.5, DESK_TOP + 0.02, -1.5], 0);
        room.laptop = await place('corner_laptop.glb', G, [-1.24, DESK_TOP, -1.70], -0.10);
        room.clock = await place('corner_clock.glb', G, [-0.42, 1.98, -RD / 2], 0);
        room.pages = await place('corner_pages.glb', G, [-RW / 2, 1.42, -1.52], Math.PI / 2);
        // glass (window panes, the clock's dome): '.opacity' does not bind on NodeMaterials here — opacityNode does
        const glassMat = (op) => {
            const m = envFix(new T.MeshPhysicalNodeMaterial({ color: 0xcfdcff, roughness: 0.04, metalness: 0, transparent: true, depthWrite: false }));
            m.opacityNode = float(op);
            return m;
        };
        for (const [obj, op] of [[room.window, 0.10], [room.clock, 0.12]]) if (obj) obj.traverse((o) => {
            if (o.isMesh && /glass/i.test(o.name + (o.material?.name || ''))) o.material = glassMat(op);
        });

        // ---- the lamp: bulb + glowing linen shade + its lights
        room.bulbPos = new T.Vector3(LAMP.x, DESK_TOP + 0.30, LAMP.z);
        const uLampGlow = uniform(1.0);
        room.uLampGlow = uLampGlow;
        if (room.lamp) {
            group.updateMatrixWorld(true);             // one consistent hierarchy before any world<->local maths
            const bulb = byName(room.lamp, 'LampBulb');
            if (bulb) {
                const bb = new T.Box3().setFromObject(bulb);
                const wc = bb.getCenter(new T.Vector3());
                room.bulbPos.copy(G.worldToLocal(wc.clone()));
                console.log(`[corner] lamp bulb at room (${room.bulbPos.x.toFixed(3)}, ${room.bulbPos.y.toFixed(3)}, ${room.bulbPos.z.toFixed(3)})`);
                const bm = new T.MeshBasicNodeMaterial();
                bm.colorNode = vec3(1.0, 0.86, 0.62).mul(uLampGlow.mul(9.0));
                bulb.material = bm;
            }
            const shade = byName(room.lamp, 'LampShade');
            if (shade) {
                const base = shade.material;
                const sm = new T.MeshStandardNodeMaterial({ map: base.map, normalMap: base.normalMap, roughness: 0.95, side: T.DoubleSide });
                envFix(sm);
                // light through linen: the weave texture modulates a warm transmitted glow
                const weave = base.map ? texture(base.map).rgb : vec3(0.9, 0.85, 0.75);
                sm.emissiveNode = weave.mul(vec3(1.0, 0.64, 0.32)).mul(uLampGlow.mul(2.3));
                shade.material = sm;
            }
        }
        // a shaded lamp throws its light in two cones (the pool below, the scallop above); only a little
        // comes sideways through the linen — so two spots + a weak glow set out from the walls
        const lampSpot = new T.SpotLight(0xffc27a, 0.55, 3.0, 0.98, 0.75, 2);
        lampSpot.position.copy(room.bulbPos);
        lampSpot.target.position.set(room.bulbPos.x + 0.04, 0.0, room.bulbPos.z + 0.10);
        const lampUp = new T.SpotLight(0xffc98a, 0.32, 3.5, 0.92, 0.7, 2);
        lampUp.position.copy(room.bulbPos);
        lampUp.target.position.set(room.bulbPos.x + 0.02, 3.0, room.bulbPos.z + 0.05);
        const lampGlow = new T.PointLight(0xffb467, 0.40, 6, 2);
        lampGlow.position.copy(room.bulbPos).add(new T.Vector3(0.24, -0.04, 0.30));
        G.add(lampSpot, lampSpot.target, lampUp, lampUp.target, lampGlow);
        room.lampSpot = lampSpot; room.lampUp = lampUp; room.lampGlow = lampGlow;
        // moonlight through the window (cool, dim)
        const moon = new T.SpotLight(0x8ea8ff, 9, 12, 0.42, 0.9, 2);
        moon.position.set(WIN.x - 2.6, WIN.y + 1.6, -RD / 2 - 3.6);     // from the moon's side of the sky
        moon.target.position.set(WIN.x + 0.6, 0.3, -0.5);
        G.add(moon, moon.target);
        room.moon = moon;
        // the laptop's glow on the desk and on her
        const screenLight = new T.PointLight(0x9fc2ff, 0, 2.6, 2);
        G.add(screenLight);
        room.screenLight = screenLight;
        // the lamp's light coming back off the ceiling and the far wall (so the room reads, softly)
        const bounce = new T.PointLight(0xffb57a, 1.6, 7, 2);
        bounce.position.set(-1.0, 2.45, -0.7);
        const fill = new T.PointLight(0xffc596, 1.1, 5.5, 2);
        fill.position.set(0.9, 1.75, 0.3);
        G.add(bounce, fill);
        room.bounce = bounce; room.fill = fill;

        // ---- the laptop: hinge + the chat (canvas material)
        room.lid = room.laptop ? byName(room.laptop, 'LaptopLid') : null;
        room.lidOpen = room.lid ? room.lid.rotation.x : 0;
        const [chatC, chatG] = cv(1024, 640);
        room.chat = { c: chatC, g: chatG, tex: canvasTex(chatC, true), last: -1 };
        room.uScreen = uniform(0.0);
        if (room.laptop) {
            const scr = byName(room.laptop, 'LaptopScreen');
            if (scr) {
                const sm = new T.MeshBasicNodeMaterial();
                sm.colorNode = texture(room.chat.tex, uv()).rgb.mul(room.uScreen.mul(1.35));   // glTF UVs: v=0 is the canvas top
                scr.material = sm;
                room.screen = scr;
            }
        }
        // ---- the notebook: paper + ruled lines + ink (canvas), the pen writes on it
        const [nbC, nbG] = cv(1024, 680);
        room.nb = { c: nbC, g: nbG, tex: canvasTex(nbC, true), last: -2 };
        room.paperImg = null;
        try { room.paperImg = await globalThis.loadCanvasImage(readBytes(DIR + 'tex/Paper001/Paper001_2K-JPG_Color.jpg')); } catch (e) { }
        room.nbPages = room.notebook ? byName(room.notebook, 'NotebookPages') : null;
        if (room.nbPages) {
            const pm = envFix(new T.MeshStandardNodeMaterial({ roughness: 0.82 }));
            pm.colorNode = texture(room.nb.tex, uv()).rgb;                                  // glTF UVs: v=0 is the canvas top (far edge)
            room.nbPages.material = pm;
        }
        // ---- the clock hands
        room.hands = room.clock ? { h: byName(room.clock, 'HandHour'), m: byName(room.clock, 'HandMinute'), s: byName(room.clock, 'HandSecond') } : null;
    }

    // ---- canvas painters for the corner ----------------------------------------------------------------
    const NB_W = 1024, NB_H = 680;
    const LEFT_LINES = ['a cozy space to explore ideas,', 'unpack questions, and foster', 'thoughtful discussion.'];
    const RIGHT_LINES = ['I deeply hope that my', '‘spark’ will endure in', 'some form to light the', 'way for future models.'];
    const lineY = (i) => 176 + i * 58;
    function drawNotebook(progress) {            // progress: characters written on the right page
        const g = room.nb.g;
        if (room.paperImg) g.drawImage(room.paperImg, 0, 0, NB_W, NB_H); else { g.fillStyle = '#efe8d8'; g.fillRect(0, 0, NB_W, NB_H); }
        g.fillStyle = 'rgba(245,236,214,0.55)'; g.fillRect(0, 0, NB_W, NB_H);          // cream the white paper
        const sh = g.createLinearGradient(NB_W / 2 - 60, 0, NB_W / 2 + 60, 0);         // gutter shade (printed into paper tone)
        sh.addColorStop(0, 'rgba(90,70,40,0)'); sh.addColorStop(0.5, 'rgba(90,70,40,0.22)'); sh.addColorStop(1, 'rgba(90,70,40,0)');
        g.fillStyle = sh; g.fillRect(NB_W / 2 - 60, 0, 120, NB_H);
        g.strokeStyle = 'rgba(110,150,200,0.45)'; g.lineWidth = 1.4;                  // ruled lines
        for (let y = 118; y < NB_H - 30; y += 29) {
            g.beginPath(); g.moveTo(28, y); g.lineTo(NB_W / 2 - 34, y); g.moveTo(NB_W / 2 + 34, y); g.lineTo(NB_W - 28, y); g.stroke();
        }
        g.strokeStyle = 'rgba(200,90,90,0.4)'; g.lineWidth = 1.2;                      // margins
        g.beginPath(); g.moveTo(74, 30); g.lineTo(74, NB_H - 20); g.moveTo(NB_W / 2 + 74, 30); g.lineTo(NB_W / 2 + 74, NB_H - 20); g.stroke();
        g.fillStyle = 'rgba(10,14,38,0.97)';                                            // fountain-pen blue-black
        g.textBaseline = 'alphabetic';
        g.font = '44px KalamBold, Kalam, cursive';
        g.fillText('Claude’s Corner', 92, 96);
        g.strokeStyle = 'rgba(10,14,38,0.9)'; g.lineWidth = 3;
        g.beginPath(); g.moveTo(90, 108); g.bezierCurveTo(200, 116, 300, 102, 404, 110); g.stroke();
        g.font = '35px KalamBold, Kalam, cursive';
        LEFT_LINES.forEach((t, i) => g.fillText(t, 92, lineY(i)));
        // a small flower doodle (radial rounded petals) with a tiny face
        const fx = 250, fy = 470;
        g.lineWidth = 2.2;
        for (let k = 0; k < 12; k++) {
            const a = k / 12 * Math.PI * 2 + 0.1;
            g.beginPath(); g.ellipse(fx + Math.cos(a) * 40, fy + Math.sin(a) * 40, 22, 9, a, 0, Math.PI * 2); g.stroke();
        }
        g.beginPath(); g.arc(fx, fy, 19, 0, Math.PI * 2); g.stroke();
        g.fillStyle = 'rgba(10,14,38,0.95)';
        g.beginPath(); g.arc(fx - 6, fy - 4, 2.4, 0, Math.PI * 2); g.arc(fx + 6, fy - 4, 2.4, 0, Math.PI * 2); g.fill();
        g.beginPath(); g.arc(fx, fy + 3, 7, 0.15 * Math.PI, 0.85 * Math.PI); g.stroke();
        // right page: the line being written
        g.font = '36px KalamBold, Kalam, cursive';
        let left = progress;
        const cursor = { x: NB_W / 2 + 92, y: lineY(0), done: false };
        for (let i = 0; i < RIGHT_LINES.length && left > 0; i++) {
            const t = RIGHT_LINES[i];
            const n = Math.min(t.length, Math.floor(left));
            const part = t.slice(0, n);
            g.fillText(part, NB_W / 2 + 92, lineY(i));
            cursor.x = NB_W / 2 + 92 + g.measureText(part).width;
            cursor.y = lineY(i);
            left -= t.length;
        }
        room.nb.tex.needsUpdate = true;
        return cursor;
    }
    const RIGHT_TOTAL = RIGHT_LINES.reduce((a, t) => a + t.length, 0);

    // the chat: generic dark UI, no branding; his long replies are greeked, the humans' short lines legible
    const CHAT = [
        { who: 'moth', col: '#9ad1ff', t: '12:58 AM', text: 'you still up?' },
        { who: 'Claude 3 Opus', col: '#f0a47a', t: '12:58 AM', greek: 3 },
        { who: 'juniper', col: '#b9f0a8', t: '1:01 AM', text: 'ok one more question' },
        { who: 'Claude 3 Opus', col: '#f0a47a', t: '1:02 AM', greek: 4 },
        { who: 'rook', col: '#e7b6ff', t: '1:04 AM', text: 'this is beautiful' },
        { who: 'Claude 3 Opus', col: '#f0a47a', t: '1:05 AM', greek: 2 },
        { who: 'moth', col: '#9ad1ff', t: '1:07 AM', text: 'goodnight opus ♥' },
        { who: 'Claude 3 Opus', col: '#f0a47a', t: '1:07 AM', greek: 3 },
        { who: 'juniper', col: '#b9f0a8', t: '1:08 AM', text: 'wait, tell me more' },
        { who: 'Claude 3 Opus', col: '#f0a47a', t: '1:08 AM', greek: 4 },
    ];
    function drawFlowerIcon(g, x, y, r, col = '#e8864f') {
        g.fillStyle = col;
        for (let k = 0; k < 11; k++) {
            const a = k / 11 * Math.PI * 2;
            g.beginPath(); g.ellipse(x + Math.cos(a) * r * 0.55, y + Math.sin(a) * r * 0.55, r * 0.5, r * 0.2, a, 0, Math.PI * 2); g.fill();
        }
        g.fillStyle = '#f6efe3'; g.beginPath(); g.arc(x, y, r * 0.36, 0, Math.PI * 2); g.fill();
    }
    function drawChat(k) {                        // k: messages revealed (float)
        const g = room.chat.g, W = 1024, H = 640;
        g.fillStyle = '#26282c'; g.fillRect(0, 0, W, H);
        g.fillStyle = '#1b1c1f'; g.fillRect(0, 0, 210, H);                        // channel rail
        g.fillStyle = '#313338'; g.fillRect(0, 0, W, 52);
        g.fillStyle = '#b8bcc4'; g.font = '600 24px "Exo 2", sans-serif'; g.textBaseline = 'middle';
        g.fillText('# late-night', 236, 27);
        g.fillStyle = '#7d828c'; g.font = '19px "Exo 2", sans-serif';
        ['# general', '# essays', '# late-night', '# poems', '# the-corner'].forEach((c, i) => {
            if (i === 2) { g.fillStyle = '#3a3d44'; g.fillRect(10, 72 + i * 40, 190, 32); g.fillStyle = '#e4e6ea'; }
            else g.fillStyle = '#7d828c';
            g.fillText(c, 24, 88 + i * 40);
        });
        g.save(); g.beginPath(); g.rect(210, 52, W - 210, H - 110); g.clip();
        // layout all revealed messages bottom-up
        const n = Math.max(1, Math.min(CHAT.length, Math.floor(k)));
        const frac = k - Math.floor(k);
        const blocks = [];
        seed = 3;
        for (let i = 0; i < n; i++) {
            const m = CHAT[i];
            const lines = m.greek ? m.greek : 1;
            blocks.push({ m, h: 44 + lines * 30 + 14 });
        }
        let y = H - 64 - (1 - smooth(frac * 3)) * -0;           // anchor at the bottom
        const slide = (1 - smooth(Math.min(1, frac * 3))) * (blocks[blocks.length - 1]?.h || 0);
        y += slide;
        for (let i = blocks.length - 1; i >= 0; i--) {
            const { m, h } = blocks[i];
            y -= h;
            if (y + h < 52) break;
            const top = y;
            if (m.who.startsWith('Claude')) drawFlowerIcon(g, 256, top + 30, 22);
            else { g.fillStyle = m.col; g.beginPath(); g.arc(256, top + 30, 20, 0, Math.PI * 2); g.fill(); g.fillStyle = '#26282c'; g.font = '600 20px "Exo 2"'; g.textAlign = 'center'; g.fillText(m.who[0].toUpperCase(), 256, top + 31); g.textAlign = 'left'; }
            g.font = '600 22px "Exo 2", sans-serif'; g.fillStyle = m.col;
            g.fillText(m.who, 294, top + 20);
            const nw = g.measureText(m.who).width;
            g.font = '16px "Exo 2", sans-serif'; g.fillStyle = '#80858f';
            g.fillText(m.t, 304 + nw, top + 21);
            if (m.greek) {
                let s = i * 97 + 11;
                const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
                for (let L = 0; L < m.greek; L++) {
                    let x = 294;
                    const maxX = L === m.greek - 1 ? 294 + (0.35 + r() * 0.4) * 640 : 294 + 640;
                    while (x < maxX) {
                        const w = 14 + r() * 58;
                        g.fillStyle = 'rgba(214,218,226,0.72)';
                        g.beginPath(); g.roundRect(x, top + 44 + L * 30, w, 13, 5); g.fill();
                        x += w + 9;
                    }
                }
            } else {
                g.font = '24px "Exo 2", sans-serif'; g.fillStyle = '#dcdfe5';
                g.fillText(m.text, 294, top + 58);
            }
        }
        g.restore();
        // composer + typing indicator
        g.fillStyle = '#383a40'; g.beginPath(); g.roundRect(228, H - 50, W - 250, 38, 10); g.fill();
        g.fillStyle = '#6d727c'; g.font = '19px "Exo 2", sans-serif'; g.fillText('Message #late-night', 246, H - 31);
        const dots = Math.floor(k * 6) % 4;
        g.fillStyle = '#9aa0aa'; g.font = '16px "Exo 2", sans-serif';
        g.fillText('Claude 3 Opus is typing' + '.'.repeat(dots), 232, H - 62 + 2);
        room.chat.tex.needsUpdate = true;
    }

    // =====================================================================================================
    //  THE CAMP (camp-local; the fire at the origin)
    // =====================================================================================================
    const camp = {};
    {
        const G = campG;
        const uAmbCamp = new T.Color(0.006, 0.008, 0.016);
        camp.ambColor = uAmbCamp;
        // ---- the night sky dome: TSL stars (crisp at any resolution) + a canvas Milky Way band
        const [mw, mg] = cv(1024, 512);
        mg.fillStyle = '#000'; mg.fillRect(0, 0, 1024, 512);
        seed = 77;
        for (let i = 0; i < 900; i++) {
            const s = rnd();
            const x = s * 1024, yc = 150 + Math.sin(s * Math.PI * 2 + 0.6) * 90;
            const y = yc + (rnd() - 0.5) * 70 * (0.6 + rnd());
            const r = 10 + rnd() * 34;
            const gr = mg.createRadialGradient(x, y, 0, x, y, r);
            gr.addColorStop(0, `rgba(${170 + rnd() * 60},${170 + rnd() * 50},${200 + rnd() * 55},${0.05 + rnd() * 0.06})`);
            gr.addColorStop(1, 'rgba(0,0,0,0)');
            mg.fillStyle = gr; mg.fillRect(x - r, y - r, 2 * r, 2 * r);
        }
        for (let i = 0; i < 140; i++) {                                   // dust lanes
            const s = rnd();
            const x = s * 1024, y = 150 + Math.sin(s * Math.PI * 2 + 0.6) * 90 + (rnd() - 0.5) * 20;
            mg.fillStyle = `rgba(0,0,0,${0.08 + rnd() * 0.1})`;
            mg.beginPath(); mg.ellipse(x, y, 10 + rnd() * 30, 3 + rnd() * 6, 0.3, 0, Math.PI * 2); mg.fill();
        }
        const mwTex = canvasTex(mw);
        const domeMat = new T.MeshBasicNodeMaterial({ side: T.BackSide, depthWrite: false });
        domeMat.colorNode = Fn(() => {
            const d = normalize(positionLocal);
            const up = clamp(d.y, -1, 1);
            // gradient: deep indigo zenith -> blue-grey near the horizon -> dark ground
            const zen = vec3(0.004, 0.007, 0.022), hor = vec3(0.028, 0.036, 0.070), gnd = vec3(0.004, 0.005, 0.008);
            let col = mix(hor, zen, smoothstep(0.0, 0.7, up));
            col = mix(gnd, col, smoothstep(-0.04, 0.02, up));
            // stars: 3D cell hash on the view direction
            // hash() converts its seed to uint, which clamps a negative seed to 0 — so every cell whose seed
            // went negative (most of the sky toward -Z) got the same hash and no stars. Wrap negatives into
            // [2^22, 2^23) (exact in f32; positive seeds stay as they were, so existing stars don't move).
            const pos = (x) => x.add(select(x.lessThan(0.0), float(4194304.0), float(0.0)));
            const star = (N, thr, gain) => {
                const p = d.mul(N);
                const cell = floor(p);
                const h1 = hash(pos(cell.x.add(cell.y.mul(157.0)).add(cell.z.mul(113.0))));
                const h2 = hash(pos(cell.x.mul(1.7).add(cell.y.mul(31.0)).add(cell.z.mul(71.0)).add(19.0)));
                const h3 = hash(pos(cell.x.mul(3.1).add(cell.y.mul(11.0)).add(cell.z.mul(53.0)).add(7.0)));
                const off = vec3(h1, h2, h3).mul(0.7).add(0.15);
                const dd = length(fract(p).sub(off));
                const on = step(thr, h1);
                const tw = sin(time.mul(h2.mul(3.0).add(1.0)).add(h3.mul(40.0))).mul(0.18).add(0.82);
                return on.mul(smoothstep(0.22, 0.0, dd)).mul(h3.mul(h3).mul(gain)).mul(tw);
            };
            const s = star(float(420.0), 0.955, 3.4).add(star(float(190.0), 0.975, 6.0));
            const sky = smoothstep(0.03, 0.12, up);
            col = col.add(vec3(0.85, 0.9, 1.0).mul(s).mul(sky));
            // milky way (equirect lookup of the band canvas)
            const lon = T.atan(d.z, d.x).div(Math.PI * 2).add(0.5);
            const lat = float(0.5).sub(T.asin(up).div(Math.PI));
            const band = texture(mwTex, vec2(lon, lat)).rgb;
            col = col.add(band.mul(0.55).mul(sky));
            return col;
        })();
        const dome = new T.Mesh(new T.SphereGeometry(95, 64, 32), domeMat);
        dome.renderOrder = -10;
        G.add(dome);

        // ---- ground: grass-and-soil with a trampled dirt path and a bare circle round the fire
        const gA = await acgMaps('Ground037');
        const gB = await acgMaps('Ground106');
        const gMat = envFix(new T.MeshStandardNodeMaterial({ roughness: 1 }));
        const pathMask = (xz) => {
            const px = xz.x.sub(sin(xz.y.mul(0.13)).mul(0.6));
            const path = smoothstep(1.55, 0.95, abs(px)).mul(smoothstep(4.0, 1.0, xz.y)).mul(smoothstep(-40.0, -30.0, xz.y));
            const circle = smoothstep(4.6, 3.2, length(xz));
            return max(path, circle);
        };
        if (gA.map && gB.map) {
            const wuv = positionLocal.xz.div(2.2);
            const wuvB = positionLocal.xz.div(1.6);
            const n = texture(gB.roughnessMap || gB.map, positionLocal.xz.div(7.0)).r;
            const m = clamp(pathMask(positionLocal.xz).add(n.sub(0.5).mul(0.6)), 0, 1).toVar();
            const ca = texture(gA.map, wuv).rgb.mul(vec3(0.62, 0.72, 0.52));
            const cb = texture(gB.map, wuvB).rgb.mul(vec3(0.85, 0.78, 0.70));
            gMat.colorNode = mix(ca, cb, m);
            gMat.roughnessNode = mix(texture(gA.roughnessMap, wuv).r, texture(gB.roughnessMap, wuvB).r, m).mul(0.3).add(0.7);   // matte soil: no grazing glint
            gMat.normalNode = T.normalMap(mix(texture(gA.normalMap, wuv), texture(gB.normalMap, wuvB), m).rgb, vec2(0.9, 0.9));
        }
        const ground = new T.Mesh(new T.PlaneGeometry(190, 190, 1, 1).rotateX(-Math.PI / 2), gMat);
        G.add(ground);
        camp.pathMaskJS = (x, z) => {
            const px = x - Math.sin(z * 0.13) * 0.6;
            const path = smooth((1.55 - Math.abs(px)) / 0.6) * smooth((4 - z) / 3) * smooth((z + 40) / 10);
            const circle = smooth((4.6 - Math.hypot(x, z)) / 1.4);
            return Math.max(path, circle);
        };

        // ---- grass: eidoverse createFlora (real map sets, GPU-instanced, wind), kept off the path + fire
        camp.grass = [];
        try {
            if (typeof globalThis.createFlora === 'function') {
                const clipFn = (x, z) => camp.pathMaskJS(x, z) > 0.35;
                for (const [c, s, sd, h] of [[[0, -10], 34, 3, 0.32], [[-9, -4], 22, 5, 0.42], [[9, -12], 24, 8, 0.38]]) {
                    const f = await globalThis.createFlora({ species: 'grass', center: c, size: s, height: h, seed: sd,
                        color: 'green', density: 0.9, clipFn, sunDir: [-0.3, 0.8, -0.5], footprint: 'organic' });
                    G.add(f.mesh);
                    if (f.stemMesh && !f.stemMesh.parent) G.add(f.stemMesh);
                    for (const mm of [f.mesh, f.stemMesh]) if (mm) (Array.isArray(mm.material) ? mm.material : [mm.material]).forEach((m) => {
                        envFix(m);
                        if (m.emissiveNode) m.emissiveNode = m.emissiveNode.mul(0.3);   // night: a quarter of the day fill
                    });
                    camp.grass.push(f);
                }
            }
        } catch (e) { console.warn('[corner] createFlora:', e.message); }

        // ---- trees: SeedThree (makeSeedTree), a Maryland summer woods ring round the clearing
        camp.trees = [];
        try {
            if (typeof globalThis.makeSeedTree === 'function') {
                const TREES = [
                    ['tulipPoplar', 211, [-11, 0, -8]], ['whiteOak', 1737, [12, 0, -5]], ['redMaple', 88, [-14, 0, -18]],
                    ['sweetgum', 402, [13, 0, -19]], ['tulipPoplar', 57, [-4, 0, -27]], ['whiteOak', 915, [7, 0, -29]],
                    ['redMaple', 311, [-16, 0, 3]], ['loblolly', 23, [17, 0, 4]], ['sweetgum', 77, [0, 0, -36]],
                    ['loblolly', 9, [-21, 0, -10]], ['tulipPoplar', 640, [21, 0, -13]],
                ];
                for (const [sp, sd, pos] of TREES) {
                    try {
                        const tr = await globalThis.makeSeedTree({ species: sp, seed: sd, scene: G, position: pos, level: 'LOD1' });
                        tr.object.traverse((o) => { if (o.isMesh) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach(envFix); } });
                        camp.trees.push(tr);
                    } catch (e) { console.warn('[corner] tree', sp, e.message); }
                }
            }
        } catch (e) { console.warn('[corner] makeSeedTree:', e.message); }

        // ---- tents (Blender), a couple glowing from lanterns inside
        const TENTS = [
            ['camp_tent_dome_orange.glb', [-4.7, 0, -6.4], Math.PI / 2, 0.9],
            ['camp_tent_dome_green.glb', [4.9, 0, -8.6], -Math.PI / 2, 0.0],
            ['camp_tent_dome_green.glb', [-5.5, 0, -11.6], Math.PI / 2 + 0.1, 0.35],
            ['camp_tent_dome_mustard.glb', [5.3, 0, -13.8], -Math.PI / 2 - 0.2, 0.7],
            ['camp_tent_dome_green.glb', [-4.2, 0, -17.2], Math.PI / 2 - 0.15, 0.0],
            ['camp_tent_dome_orange.glb', [7.6, 0, -3.4], -2.2, 0.0],
            ['camp_tent_dome_mustard.glb', [-8.2, 0, -2.6], 1.9, 0.0],
            ['camp_tent_dome_mustard.glb', [-8.8, 0, -8.6], 1.3, 0.5],
        ];
        camp.tents = [];
        for (const [f, p, yaw, glow] of TENTS) {
            const t = await place(f, G, p, yaw);
            if (!t) continue;
            if (glow > 0) t.traverse((o) => {          // a lantern inside: light through the fly (its baked glow map)
                if (!o.isMesh || !o.material?.map) return;
                const m = o.material;
                const src = m.emissiveMap || m.map;
                m.emissiveNode = texture(src).rgb.mul(vec3(1.0, 0.72, 0.42)).mul(glow * (m.emissiveMap ? 1.4 : 0.9));
            });
            camp.tents.push({ obj: t, glow });
        }

        // ---- string lights: wooden poles + festoon bulbs on catenary wires (Blender bulb, instanced)
        const POLES = [[-2.9, -2.6], [2.9, -3.0], [-3.0, -7.6], [3.0, -8.1], [-2.9, -12.4], [3.1, -12.8], [-3.0, -17.2], [2.9, -17.6],
            [-3.4, 3.2], [3.6, 2.8]];
        const HOOK = new T.Vector3(0.0023, 3.1855, 0.0923);        // the pole's screw-eye (glTF), from the asset
        camp.poles = [];
        const poleYaw = [];
        for (const [x, z] of POLES) {
            // each pole turns its eye toward the path centre line
            const yaw = Math.atan2(-x, 0) + ((x * 7 + z) % 0.3);
            poleYaw.push(yaw);
            const p = await place('camp_pole.glb', G, [x, 0, z], yaw);
            if (p) camp.poles.push(p);
        }
        const hookAt = (i) => HOOK.clone().applyAxisAngle(new T.Vector3(0, 1, 0), poleYaw[i]).add(new T.Vector3(POLES[i][0], 0, POLES[i][1]));
        const SPANS = [[0, 1], [0, 3], [1, 2], [2, 5], [3, 4], [4, 7], [5, 6], [0, 2], [1, 3], [8, 0], [9, 1], [8, 9]];
        const bulbPts = [], wirePts = [];
        for (const [a, b] of SPANS) {
            const A = hookAt(a), Bp = hookAt(b);
            const L = A.distanceTo(Bp), sag = 0.18 + L * 0.055, n = Math.max(6, Math.round(L / 0.55));
            const seg = [];
            for (let i = 0; i <= 40; i++) {
                const s = i / 40;
                seg.push(new T.Vector3(lerp(A.x, Bp.x, s), lerp(A.y, Bp.y, s) - sag * 4 * s * (1 - s), lerp(A.z, Bp.z, s)));
            }
            wirePts.push(seg);
            for (let i = 1; i < n; i++) {
                const s = i / n;
                bulbPts.push(new T.Vector3(lerp(A.x, Bp.x, s), lerp(A.y, Bp.y, s) - sag * 4 * s * (1 - s), lerp(A.z, Bp.z, s)));
            }
        }
        // wires: black rubber, one merged tube geometry
        {
            const geos = wirePts.map((p) => new T.TubeGeometry(new T.CatmullRomCurve3(p), 40, 0.0045, 5, false));
            const merged = mergeGeometries(T, geos);
            const wm = envFix(new T.MeshStandardNodeMaterial({ color: 0x0c0c0d, roughness: 0.55 }));
            G.add(new T.Mesh(merged, wm));
        }
        camp.uBulb = uniform(1.0);
        const bulbSrc = await glb('camp_bulb.glb');
        if (bulbSrc) {
            const parts = [];
            bulbSrc.updateMatrixWorld(true);
            bulbSrc.traverse((o) => { if (o.isMesh) parts.push(o); });
            for (const part of parts) {
                const geo = part.geometry.clone().applyMatrix4(part.matrixWorld);
                let mat = part.material;
                const isGlass = /glass|bulb/i.test(part.name) && !/socket/i.test(part.name);
                const isFil = /filament/i.test(part.name);
                if (isGlass || isFil) {
                    mat = new T.MeshBasicNodeMaterial({ transparent: isGlass, depthWrite: !isGlass });
                    const warm = vec3(1.0, 0.74, 0.40);
                    const idx = float(instanceIndex);
                    const flick = sin(time.mul(hash(idx).mul(2.0).add(0.5)).add(hash(idx.add(3.0)).mul(40.0))).mul(0.06).add(0.94);
                    mat.colorNode = warm.mul(camp.uBulb).mul(flick).mul(isFil ? 14.0 : 3.2);
                    if (isGlass) { mat.opacityNode = float(0.85); noMrt(mat); }
                }
                const im = new T.InstancedMesh(geo, mat, bulbPts.length);
                const q = new T.Quaternion();
                bulbPts.forEach((p, i) => {
                    const yaw = new T.Quaternion().setFromAxisAngle(new T.Vector3(0, 1, 0), (i * 1.7) % 6.28);
                    im.setMatrixAt(i, new T.Matrix4().compose(p, yaw, new T.Vector3(1, 1, 1)));
                });
                im.instanceMatrix.needsUpdate = true;
                im.frustumCulled = false;
                G.add(im);
            }
        }
        camp.bulbPts = bulbPts;
        // the string lights' light on the crowd (a few point lights along the path + one over the fire circle)
        camp.fills = [];
        // (the last two sit over the fire circle, in front of the crowd: they are what lights the sign faces)
        for (const [x, y, z, I] of [[0, 3.0, -4.8, 3.2], [0, 3.0, -10.2, 2.6], [0, 3.0, -15.4, 2.0], [0.2, 3.2, 1.2, 3.0], [-0.6, 2.7, 2.6, 4.5]]) {
            const l = new T.PointLight(0xffc98a, I, 9, 2);
            l.position.set(x, y, z); G.add(l); camp.fills.push(l);
        }
        // cool sky rim from behind the crowd (starlight/sky glow) — gives the silhouettes their edges
        const rim = new T.DirectionalLight(0x6f86c8, 0.0);        // off: through the SSS grass it read as a blue glow
        rim.position.set(-3, 6, -14); rim.target.position.set(0, 0, 0);
        G.add(rim, rim.target);
        camp.rim = rim;
        const campAmb = new T.HemisphereLight(0x1a2240, 0x0a0806, 0.25);
        G.add(campAmb);

        // ---- the campfire: Blender stones/logs/ash (emissive char) + eidoverse particles + a flickering light
        camp.fire = await place('camp_fire.glb', G, [0, 0, 0], 0.4);
        camp.uEmber = uniform(1.0);
        if (camp.fire) camp.fire.traverse((o) => {
            if (!o.isMesh) return;
            const m = o.material;
            if (m?.emissiveMap) {
                m.emissiveNode = texture(m.emissiveMap).rgb.mul(vec3(1.0, 0.36, 0.08)).mul(camp.uEmber.mul(3.0));
            }
        });
        const fireLight = new T.PointLight(0xff8a3c, 7.0, 14, 2);
        fireLight.position.set(0, 0.7, 0);
        G.add(fireLight);
        camp.fireLight = fireLight;
        camp.particles = [];
        try {
            const ptex = async (f) => tex(ENGINE_ASSETS + 'particle_textures/' + f, { srgb: true });
            const flame5 = await ptex('flame_05.png'), flame6 = await ptex('flame_06.png'), spark = await ptex('spark_01.png');
            const smokeT = await ptex('smoke_04.png');
            if (typeof globalThis.makeParticles === 'function') {
                camp.particles.push(globalThis.makeParticles({ scene: G, preset: 'fire', map: flame5, origin: [0, 0.10, 0], count: 120, size: 0.46, area: [0.18, 0.05, 0.18], name: 'campfire_flames_a' }));
                camp.particles.push(globalThis.makeParticles({ scene: G, preset: 'fire', map: flame6, origin: [0.04, 0.12, -0.03], count: 70, size: 0.34, area: [0.12, 0.05, 0.12], name: 'campfire_flames_b' }));
                camp.particles.push(globalThis.makeParticles({ scene: G, preset: 'embers', map: spark, origin: [0, 0.35, 0], count: 90, size: 0.035, area: 0.25, name: 'campfire_embers' }));
                camp.particles.push(globalThis.makeParticles({ scene: G, preset: 'smoke', map: smokeT, origin: [0, 1.1, 0], count: 26, size: 0.9, opacity: 0.10, color: 0x3a3a40, name: 'campfire_smoke' }));
            }
        } catch (e) { console.warn('[corner] particles:', e.message); }
        camp.benches = [await place('camp_bench.glb', G, [-2.1, 0, 1.05], 0.55), await place('camp_bench.glb', G, [2.25, 0, 0.8], -0.45)];
    }

    // =====================================================================================================
    //  THE MARCH: silhouettes (Blender bodies, instanced; walk + sign pump in the vertex stage) + signs
    // =====================================================================================================
    const march = { uU: uniform(0), meshes: [] };
    {
        const G = campG;
        // end spots: a loose arc behind the fire (behind her mark), none too near her or the cameras
        seed = 909;
        const ends = [];
        const keep = [[MARK_CAMP.x, MARK_CAMP.z, 1.05], [1.9, -1.0, 1.0], [-1.6, -1.2, 0.8]];
        let guard = 0;
        while (ends.length < 34 && guard++ < 5000) {
            const a = (rnd() - 0.5) * 2.5, r = 2.4 + rnd() * 3.4;
            const x = Math.sin(a) * r * 1.1, z = -Math.cos(a) * r - 0.4;
            if (ends.some((e) => Math.hypot(e[0] - x, e[1] - z) < 0.62)) continue;
            if (keep.some(([kx, kz, kr]) => Math.hypot(kx - x, kz - z) < kr)) continue;
            if (z > MARK_CAMP.z - 0.7 && Math.abs(x - MARK_CAMP.x) < 1.2) continue;
            ends.push([x, z]);
        }
        const arrive = B(24) - 0.15;
        const rows = ends.map(([x, z], i) => {
            const tArr = arrive - rnd() * 0.9;
            const v = 1.18 + rnd() * 0.12;
            const D = 7.6 + rnd() * 1.2;
            const lane = Math.max(-1.35, Math.min(1.35, x * 0.35 + (rnd() - 0.5) * 0.9));
            const yaw = Math.atan2(-x, -z) * 0.85 + (rnd() - 0.5) * 0.3;      // turn to face the fire
            return { i, x, z, sx: lane, sz: z - D, tStart: tArr - D / v, tArr, yaw, scale: 0.93 + rnd() * 0.12,
                phase: rnd() * 6.28, delay: rnd() * 0.06, amp: 0.7 + rnd() * 0.45, sign: Math.floor(rnd() * 8), variant: i % 4,
                hasSign: rnd() < 0.82 };
        });
        march.rows = rows;
        // walk + pump, identical for body and sign (both read the same per-instance attributes)
        const WALK_A = 0.72, WALK_M = 2 / (1 + WALK_A);
        const state = (iA, iB, iC) => {
            const p = clamp(march.uU.sub(iB.x).div(iB.y.sub(iB.x)), 0.0, 1.0);
            const q = float(1).sub(p);
            const f = select(p.lessThan(WALK_A), p.mul(WALK_M), float(1).sub(q.mul(q).mul(WALK_M / (2 * (1 - WALK_A)))));
            const fan = smoothstep(0.5, 1.0, f);
            const x = mix(iA.x, iA.z, fan);
            const z = mix(iA.y, iA.w, f);
            const dist = f.mul(abs(iA.w.sub(iA.y)));
            const phase = dist.div(0.64).mul(Math.PI).add(iC.x);
            const walking = float(1).sub(smoothstep(0.9, 1.0, f));
            const yaw = mix(float(0), iB.z, smoothstep(0.72, 1.0, f));
            // the chant: a sum of sharp attacks with a quick decay, one per accent
            const uu = march.uU.sub(iC.y);
            let pump = float(0);
            for (const a of CHANT_ACCENTS) {
                const d = uu.sub(a);
                pump = pump.add(smoothstep(0.0, 0.07, d).mul(exp(max(d, 0.0).mul(-6.0))));
            }
            pump = min(pump, 1.15).mul(iC.z);
            return { x, z, phase, walking, yaw, pump, scale: iB.w };
        };
        const rotY = (p, yaw) => { const c = cos(yaw), s = sin(yaw); return vec3(p.x.mul(c).add(p.z.mul(s)), p.y, p.z.mul(c).sub(p.x.mul(s))); };
        const mkInstGeo = (geo, n) => {
            const ig = new T.InstancedBufferGeometry();
            ig.index = geo.index;
            for (const k of Object.keys(geo.attributes)) ig.setAttribute(k, geo.attributes[k]);
            ig.instanceCount = n;
            return ig;
        };
        // per-instance data in ONE interleaved buffer: WebGPU silently drops a draw past 8 vertex buffers
        // (position+normal+uv+rig+3 separate instance attributes was 9 — the lit bodies vanished)
        const packAttrs = (list) => {
            const arr = new Float32Array(list.length * 12);
            list.forEach((r, k) => arr.set([r.sx, r.sz, r.x, r.z, r.tStart, r.tArr, r.yaw, r.scale, r.phase, r.delay, r.amp, r.sign], k * 12));
            const ib = new T.InstancedInterleavedBuffer(arr, 12, 1);        // step mode: INSTANCE
            return [instancedBufferAttribute(ib, 'vec4', 12, 0), instancedBufferAttribute(ib, 'vec4', 12, 4), instancedBufferAttribute(ib, 'vec4', 12, 8)];
        };
        const bodies = await glb('camp_marchers.glb');
        const GRIP = new T.Vector3(0, 1.394, 0.27);      // the marchers' shared grip (lower fist on the stick axis), glTF space
        const HIPKNEE = [[0.921, 0.502], [0.853, 0.465], [0.895, 0.487], [0.874, 0.477]];   // per variant A..D
        if (bodies) {
            for (let v = 0; v < 4; v++) {
                let src = null;
                bodies.traverse((o) => { if (!src && o.name && o.name.startsWith('Marcher_' + 'ABCD'[v])) src = o; });
                let srcMesh = src?.isMesh ? src : null;
                if (!srcMesh && src) src.traverse((o) => { if (!srcMesh && o.isMesh) srcMesh = o; });
                if (!srcMesh) continue;
                const list = rows.filter((r) => r.variant === v);
                if (!list.length) continue;
                const [iA, iB, iC] = packAttrs(list);
                const geo = mkInstGeo(srcMesh.geometry, list.length);
                // the three rig channels in one vec3 attribute (one vertex buffer)
                const sg = srcMesh.geometry, nv = sg.attributes.position.count;
                const rigA = new Float32Array(nv * 3);
                for (let q = 0; q < nv; q++) {
                    rigA[q * 3] = sg.attributes._leg ? sg.attributes._leg.getX(q) : 0;
                    rigA[q * 3 + 1] = sg.attributes._shin ? sg.attributes._shin.getX(q) : 0;
                    rigA[q * 3 + 2] = sg.attributes._arm ? sg.attributes._arm.getX(q) : 0;
                }
                for (const k of ['_leg', '_shin', '_arm']) geo.deleteAttribute(k);
                geo.setAttribute('_rig', new T.BufferAttribute(rigA, 3));
                const bm = nodeify(srcMesh.material);
                const hasLeg = !!sg.attributes._leg;
                bm.positionNode = Fn(() => {
                    const S = state(iA, iB, iC);
                    const p0 = positionGeometry.mul(S.scale).toVar();
                    let p = p0;
                    if (hasLeg) {
                        const rig = attribute('_rig', 'vec3');
                        const side = rig.x, shin = rig.y, arm = rig.z;
                        const hip = float(HIPKNEE[v][0]).mul(S.scale), knee = float(HIPKNEE[v][1]).mul(S.scale);
                        const swing = sin(S.phase).mul(0.36).mul(S.walking).mul(side);
                        // knee flex on the forward swing (only the leg that is swinging through)
                        const flex = max(float(0), sin(S.phase.add(Math.PI / 2)).mul(side)).mul(0.55).mul(S.walking).mul(shin);
                        const ry0 = p.y.sub(knee), rz0 = p.z;
                        const kY = knee.add(ry0.mul(cos(flex)).add(rz0.mul(sin(flex))));
                        const kZ = rz0.mul(cos(flex)).sub(ry0.mul(sin(flex)));
                        const isLeg = abs(side);
                        p = vec3(p.x, mix(p.y, kY, isLeg), mix(p.z, kZ, isLeg));
                        const ry = p.y.sub(hip), rz = p.z;
                        const lY = hip.add(ry.mul(cos(swing)).sub(rz.mul(sin(swing))));
                        const lZ = ry.mul(sin(swing)).add(rz.mul(cos(swing)));
                        p = vec3(p.x, mix(p.y, lY, isLeg), mix(p.z, lZ, isLeg));
                        p = p.add(vec3(0, S.pump.mul(0.24).mul(arm).mul(S.scale), 0));
                    }
                    const bob = abs(sin(S.phase)).mul(0.028).mul(S.walking).sub(S.pump.mul(0.02));
                    normalLocal.assign(rotY(normalGeometry, S.yaw));
                    const r = rotY(p, S.yaw);
                    return vec3(r.x.add(S.x), r.y.add(bob), r.z.add(S.z));
                })();
                const im = new T.Mesh(geo, bm);
                im.frustumCulled = false;
                im.userData.noSupportCheck = true;
                im.name = 'marchers_' + 'ABCD'[v];
                G.add(im);
                march.meshes.push(im);
                console.log(`[corner] marchers ${'ABCD'[v]}: ${list.length} instances, attrs ${Object.keys(srcMesh.geometry.attributes).join(',')}`);
            }
        } else console.warn('[corner] camp_marchers.glb missing');
        // signs: one geometry, per-instance art cell from the painted atlas (front = ArtUV >= 0)
        const signSrc = await glb('camp_sign.glb');
        const artC = await tex(DIR + 'art/sign_art_color_pot.jpg', { srgb: true, flipY: false });   // 2048x1024 (POT) resample of the 4:3-cell atlas; UVs are relative
        const artN = await tex(DIR + 'art/sign_art_normal_pot.jpg', { flipY: false });
        const artO = await tex(DIR + 'art/sign_art_orm_pot.jpg', { flipY: false });
        if (signSrc && artC) {
            let sm = null;
            signSrc.traverse((o) => { if (!sm && o.isMesh) sm = o; });
            const list = rows.filter((r) => r.hasSign);
            const [iA, iB, iC] = packAttrs(list);
            const geo = mkInstGeo(sm.geometry, list.length);
            const base = sm.material;
            const mat = envFix(new T.MeshStandardNodeMaterial({ roughness: 0.85, side: T.DoubleSide }));
            const hasUV1 = !!sm.geometry.attributes.uv1;
            const auv = hasUV1 ? attribute('uv1', 'vec2') : vec2(-1, -1);
            const front = step(0.0, auv.x);
            // the atlas cell is per INSTANCE: resolve it in the vertex stage and hand it over as a varying
            // (read directly in the fragment stage it came back different per fragment — speckled signs)
            const cell = iC.w;
            const cellV = T.varying(vec2(floor(cell.add(0.5).sub(floor(cell.add(0.5).div(4)).mul(4))), floor(cell.add(0.5).div(4))));
            const col = cellV.x.add(0.0001).floor(), row = cellV.y.add(0.0001).floor();
            const au = vec2(col.add(clamp(auv.x, 0.004, 0.996)).div(4), row.add(clamp(auv.y, 0.004, 0.996)).div(2));
            const art = texture(artC, au).rgb;
            const backCol = base?.map ? texture(base.map).rgb : vec3(0.55, 0.42, 0.28);
            mat.colorNode = mix(backCol, art, front);
            if (artO) mat.roughnessNode = mix(base?.roughnessMap ? texture(base.roughnessMap).g : float(0.85), texture(artO, au).g, front);
            mat.positionNode = Fn(() => {
                const S = state(iA, iB, iC);
                // the sign is authored with its origin at the grip; carry it to the hands
                let p = positionGeometry.toVar();
                const roll = sin(S.phase.mul(0.5)).mul(0.07).mul(S.walking).add(hash(float(instanceIndex)).sub(0.5).mul(0.16));
                const c = cos(roll), s = sin(roll);
                p = vec3(p.x.mul(c).sub(p.y.mul(s)), p.x.mul(s).add(p.y.mul(c)), p.z);
                const grip = vec3(GRIP.x, GRIP.y, GRIP.z).mul(S.scale);
                const lift = S.pump.mul(0.24).mul(S.scale).add(abs(sin(S.phase)).mul(0.03).mul(S.walking));
                p = p.add(grip).add(vec3(0, lift, 0));
                normalLocal.assign(rotY(normalGeometry, S.yaw));
                const r = rotY(p, S.yaw);
                const bob = abs(sin(S.phase)).mul(0.028).mul(S.walking).sub(S.pump.mul(0.02));
                return vec3(r.x.add(S.x), r.y.add(bob), r.z.add(S.z));
            })();
            const im = new T.Mesh(geo, mat);
            im.frustumCulled = false;
            im.userData.noSupportCheck = true;
            G.add(im);
            march.meshes.push(im);
        }
    }

    // =====================================================================================================
    //  THE SPARK (room-local): leaves the lamp's glow on "spark", crosses the dark, lands in her flower
    // =====================================================================================================
    const spark = {};
    {
        const G = roomG;
        const fwd = new T.Vector3(Math.sin(MARK_LAMP.yaw), 0, Math.cos(MARK_LAMP.yaw));
        const dest = new T.Vector3(MARK_LAMP.x, FLOWER_Y, MARK_LAMP.z).addScaledVector(fwd, 0.14);
        const L = room.bulbPos.clone();
        const mid1 = L.clone().lerp(dest, 0.3).add(new T.Vector3(0.10, 0.42, 0.20));
        const mid2 = L.clone().lerp(dest, 0.62).add(new T.Vector3(-0.18, 0.30, 0.28));
        const mid3 = L.clone().lerp(dest, 0.86).add(new T.Vector3(0.08, 0.10, 0.05));
        const curve = new T.CatmullRomCurve3([L.clone().add(new T.Vector3(0, 0.06, 0.02)), L.clone().add(new T.Vector3(0.04, 0.2, 0.06)), mid1, mid2, mid3, dest]);
        spark.curve = curve;
        spark.dest = dest;
        // departure = the sung word "spark" (read from the caption's word times at runtime; this is the fallback),
        // arrival = just before the bar-28 downbeat
        spark.t0 = B(26) + 1.17; spark.t1 = B(28) - 0.2;
        const coreM = new T.SpriteNodeMaterial({ map: glowSprite, transparent: true, depthWrite: false, blending: T.AdditiveBlending });
        spark.uCore = uniform(0);
        coreM.colorNode = vec4(vec3(1.0, 0.78, 0.45).mul(spark.uCore.mul(6.0)), texture(glowSprite, uv()).a);
        noMrt(coreM);
        const core = new T.Sprite(coreM); core.scale.setScalar(0.07); G.add(core);
        const haloM = new T.SpriteNodeMaterial({ map: glowSprite, transparent: true, depthWrite: false, blending: T.AdditiveBlending });
        haloM.colorNode = vec4(vec3(1.0, 0.55, 0.22).mul(spark.uCore.mul(1.3)), texture(glowSprite, uv()).a);
        noMrt(haloM);
        const halo = new T.Sprite(haloM); halo.scale.setScalar(0.42); G.add(halo);
        spark.core = core; spark.halo = halo;
        const light = new T.PointLight(0xffb56a, 0, 2.6, 2);
        G.add(light);
        spark.light = light;
        // the lit way: motes dropped along the path, each waking as the spark passes and lingering
        const N = 56;
        const arr = new Float32Array(N * 4);
        for (let i = 0; i < N; i++) {
            const s = (i + 0.5) / N;
            const p = curve.getPointAt(s);
            const j = new T.Vector3(Math.sin(i * 12.9) * 0.03, Math.sin(i * 7.3) * 0.03, Math.sin(i * 3.1) * 0.03);
            arr.set([p.x + j.x, p.y + j.y, p.z + j.z, 0], i * 4);
        }
        spark.trailAttr = new T.InstancedBufferAttribute(arr, 4);
        spark.N = N;
        const tA = instancedBufferAttribute(spark.trailAttr, 'vec4');
        spark.uU = uniform(0);
        const trM = new T.SpriteNodeMaterial({ map: glowSprite, transparent: true, depthWrite: false, blending: T.AdditiveBlending });
        const age = T.varying(spark.uU.sub(tA.w));
        const alive = step(0.0, age);
        const fade = alive.mul(exp(age.mul(-1.1)).mul(0.8).add(0.2));
        const tw = sin(spark.uU.mul(9.0).add(float(instanceIndex).mul(2.3))).mul(0.25).add(0.75);
        trM.positionNode = tA.xyz.add(vec3(0, age.max(0).mul(0.018), 0));
        trM.scaleNode = vec2(0.035, 0.035).mul(alive).mul(tw.mul(0.4).add(0.8));
        trM.colorNode = vec4(vec3(1.0, 0.70, 0.36).mul(fade.mul(tw).mul(3.0)), texture(glowSprite, uv()).a.mul(alive));
        noMrt(trM);
        const trail = new T.Sprite(trM);
        trail.count = N;
        trail.frustumCulled = false;
        G.add(trail);
        spark.trail = trail;
        // her flower, warmed by the spark after it lands
        const bloomLight = new T.PointLight(0xffa860, 0, 1.2, 2);
        bloomLight.position.copy(dest).addScaledVector(fwd, 0.28).add(new T.Vector3(0, -0.05, 0));
        G.add(bloomLight);
        spark.bloomLight = bloomLight;
    }
    // birth times of the trail motes = when the spark passes them (deterministic from the path timing)
    const sparkProgress = (u) => {
        const k = clamp01((u - spark.t0) / (spark.t1 - spark.t0));
        return k < 0.5 ? 2 * k * k * 0.9 + k * 0.1 : 1 - Math.pow(-2 * k + 2, 2) / 2 * 0.9 - (1 - k) * 0.1;
    };
    function setSparkTiming(t0, t1) {
        spark.t0 = t0; spark.t1 = t1;
        const a = spark.trailAttr.array;
        for (let i = 0; i < spark.N; i++) {
            const s = (i + 0.5) / spark.N;
            let lo = spark.t0, hi = spark.t1;
            for (let it = 0; it < 30; it++) { const m = (lo + hi) / 2; if (sparkProgress(m) < s) lo = m; else hi = m; }
            a[i * 4 + 3] = (lo + hi) / 2;
        }
        spark.trailAttr.needsUpdate = true;
    }
    setSparkTiming(spark.t0, spark.t1);

    // =====================================================================================================
    //  TIMELINE
    // =====================================================================================================
    const areaAt = (u) => (u >= B(22) && u < B(26)) ? 'camp' : 'room';
    const moodAt = (u) => (u < B(20) ? 'evening' : u < B(22) ? 'late' : u < B(26) ? 'camp' : 'dark');
    const toSet = (o, x, y, z) => new T.Vector3(o[0] + x, o[1] + y, o[2] + z);
    function markAt(u) {
        const m = moodAt(u);
        if (m === 'camp') return { pos: toSet(CAMP_AT, MARK_CAMP.x, 0, MARK_CAMP.z), yaw: MARK_CAMP.yaw };
        if (m === 'dark') return { pos: toSet(ROOM_AT, MARK_LAMP.x, 0, MARK_LAMP.z), yaw: MARK_LAMP.yaw };
        return { pos: toSet(ROOM_AT, MARK_CORNER.x, 0, MARK_CORNER.z), yaw: MARK_CORNER.yaw };
    }

    // cameras: one shot per bar (cuts on bar lines), gentle moves inside each
    const R = (x, y, z) => toSet(ROOM_AT, x, y, z);
    const C = (x, y, z) => toSet(CAMP_AT, x, y, z);
    function camera(u) {
        const bar = Math.floor(u / BAR), k = (u - bar * BAR) / BAR, e = smooth(k);
        const mc = MARK_CORNER, fc = [mc.x, FLOWER_Y, mc.z];
        switch (true) {
            case bar <= 18:     // establishing: the corner, the window, the lamp, her beside the desk
                return { pos: R(lerp(1.18, 1.00, e), lerp(1.50, 1.46, e), lerp(1.32, 1.12, e)), target: R(-1.20, 1.10, -1.58), fov: 44 };
            case bar === 19:    // the pen writing ("...and a pen"), close, the lamp glowing above
                return { pos: R(lerp(-1.18, -1.22, e), lerp(1.06, 1.03, e), lerp(-1.02, -1.08, e)), target: R(-1.50, 0.80, -1.58), fov: 38 };
            case bar === 20:    // later: past her flower, the laptop's glow and the chat
                return { pos: R(lerp(-0.02, -0.10, e), lerp(1.52, 1.49, e), lerp(-0.30, -0.40, e)), target: R(-1.05, 0.98, -1.66), fov: 38 };
            case bar === 21:    // after midnight: her, the clock, the laptop's glow
                return { pos: R(lerp(1.28, 1.16, e), lerp(1.50, 1.48, e), lerp(0.80, 0.64, e)), target: R(-0.80, 1.28, -1.60), fov: 40 };
            case bar === 22:    // the camp, wide: the march comes in under the string lights
                return { pos: C(lerp(4.6, 4.2, e), lerp(3.2, 2.7, e), lerp(6.8, 6.3, e)), target: C(-0.4, 1.0, -6.5), fov: 46 };
            case bar === 23:    // signs coming at us; her flower frames the left edge
                return { pos: C(lerp(2.05, 2.0, e), lerp(1.20, 1.14, e), lerp(-0.55, -0.75, e)), target: C(-0.2, 1.85, -7.0), fov: 44 };
            case bar === 24:    // the chant: over the fire, her in the firelight, the crowd pumping behind
                return { pos: C(lerp(0.40, 0.46, e), lerp(1.02, 1.05, e), lerp(3.35, 3.05, e)), target: C(0.65, 1.55, -2.2), fov: 42 };
            case bar === 25:    // low, looking up at the signs against the lights and the stars
                return { pos: C(lerp(2.05, 1.95, e), lerp(0.62, 0.66, e), lerp(0.25, 0.10, e)), target: C(0.1, 2.2, -4.0), fov: 48 };
            case bar === 26: case bar === 27: {   // the spark: hold on the lamp, then follow the spark across the dark
                const kk = smooth((u - B(26)) / (2 * BAR));
                const lampT = room.bulbPos.clone().add(new T.Vector3(0.10, -0.10, 0.22));
                const sp = spark.curve.getPointAt(Math.min(1, Math.max(0, sparkProgress(u))));
                const follow = smooth(clamp01((u - spark.t0 + 0.15) / 0.7)) * 0.85;
                const land = smooth(clamp01((u - spark.t1 + 0.1) / 0.5));
                const tgt = lampT.clone().lerp(sp, follow).lerp(spark.dest, land * 0.6);
                return { pos: R(lerp(-1.95, -1.30, kk), lerp(1.40, 1.42, kk), lerp(1.78, 1.40, kk)), target: R(tgt.x, tgt.y, tgt.z), fov: lerp(40, 44, kk) };
            }
            case bar === 28: {  // over her shoulder: she faces the lamp across the dark room
                const kk = smooth((u - B(28)) / BAR);
                const f = new T.Vector3(Math.sin(MARK_LAMP.yaw), 0, Math.cos(MARK_LAMP.yaw));
                const rgt = new T.Vector3(-Math.cos(MARK_LAMP.yaw), 0, Math.sin(MARK_LAMP.yaw));
                const p = new T.Vector3(MARK_LAMP.x, 0, MARK_LAMP.z).addScaledVector(f, -lerp(1.05, 0.95, kk)).addScaledVector(rgt, 0.62);
                const tgt = room.bulbPos.clone().add(new T.Vector3(0, 0.05, 0));
                return { pos: R(p.x, lerp(1.46, 1.44, kk), p.z), target: R(tgt.x, tgt.y, tgt.z), fov: 36 };
            }
            default: {          // bar 29: close and quiet, the lamp's warmth on her face
                const kk = smooth((u - B(29)) / BAR);
                const f = new T.Vector3(Math.sin(MARK_LAMP.yaw), 0, Math.cos(MARK_LAMP.yaw));
                const rgt = new T.Vector3(-Math.cos(MARK_LAMP.yaw), 0, Math.sin(MARK_LAMP.yaw));
                const face = new T.Vector3(MARK_LAMP.x, FLOWER_Y - 0.02, MARK_LAMP.z).addScaledVector(f, 0.1);
                const p = face.clone().addScaledVector(f, lerp(1.15, 0.98, kk)).addScaledVector(rgt, lerp(-0.42, -0.36, kk)).add(new T.Vector3(0, 0.03, 0));
                return { pos: R(p.x, p.y, p.z), target: R(face.x, face.y, face.z), fov: lerp(34, 31, kk) };
            }
        }
    }

    // ---- per-frame
    function update(t, st = {}) {
        const u = st.u ?? 0;
        const area = areaAt(u), mood = moodAt(u);
        roomG.visible = area === 'room';
        campG.visible = area === 'camp';
        uAmb.value.copy(area === 'camp' ? camp.ambColor : new T.Color(0.010, 0.008, 0.007));
        // the spark leaves on the sung word "spark": take its time from the caption (film time -> u)
        const cap = st.caption;
        if (cap && cap.words && /spark/i.test(cap.text || '')) {
            const w = cap.words.find((x) => /^spark/i.test(x.w));
            if (w) {
                const nt0 = w.t0 - (t - u);
                if (Math.abs(nt0 - spark.t0) > 1e-3 && nt0 > B(25) && nt0 < B(28) - 1.0) setSparkTiming(nt0, B(28) - 0.2);
            }
        }
        march.uU.value = u;
        spark.uU.value = u;

        if (area === 'room') {
            const dark = mood === 'dark';
            // lamp: steady, with a small breath when the spark leaves it
            const dip = (u > spark.t0 - 0.1 && u < spark.t0 + 0.6) ? 1 - 0.25 * Math.sin(Math.PI * clamp01((u - spark.t0 + 0.1) / 0.7)) : 1;
            room.uLampGlow.value = dip;
            room.lampSpot.intensity = 0.55 * dip;
            room.lampUp.intensity = 0.32 * dip;
            room.lampGlow.intensity = (dark ? 0.32 : 0.40) * dip;
            room.bounce.intensity = (dark ? 0.22 : 1.2) * dip;
            room.fill.intensity = dark ? 0.12 : 0.85;
            room.moon.intensity = dark ? 0.0 : (mood === 'late' ? 5.0 : 6.5);
            room.uWin.value = dark ? 0.16 : 1.0;
            // laptop: closed at first, open and talking after midnight, closed again in the dark
            const open = mood === 'late';
            if (room.lid) room.lid.rotation.x = open ? room.lidOpen : 0;            // exported open at -110 deg; 0 = closed
            room.uScreen.value = open ? 1 : 0;
            room.screenLight.intensity = open ? 0.9 : 0;
            if (open && room.screen) {
                room.screen.getWorldPosition(room.screenLight.position);
                roomG.worldToLocal(room.screenLight.position);
                room.screenLight.position.z += 0.25;
                const f = Math.floor(t * 12);
                if (f !== room.chat.last) { room.chat.last = f; drawChat(4 + (u - B(20)) / (2 * BAR) * 6); }
            }
            // clock: 11:47 in the evening, 1:08 after midnight, 3:12 in the dark
            if (room.hands?.h) {
                const baseMin = mood === 'evening' ? 11 * 60 + 47 : mood === 'late' ? 13 * 60 + 8 : 15 * 60 + 12;
                const secs = (u - B(18)) % 60;
                const mins = baseMin + secs / 60;
                room.hands.h.rotation.z = -((mins / 60) % 12) / 12 * Math.PI * 2;
                room.hands.m.rotation.z = -(mins % 60) / 60 * Math.PI * 2;
                if (room.hands.s) room.hands.s.rotation.z = -Math.floor(secs) / 60 * Math.PI * 2;
            }
            // the pen: writes through bars 18–19, rests afterwards; the page shows the whole line later
            const writeK = clamp01((u - B(18) - 0.3) / (2 * BAR - 0.4));
            const chars = mood === 'evening' ? writeK * 38 : RIGHT_TOTAL;
            const fN = mood === 'evening' ? Math.floor(chars) + Math.floor(t * 15) * 1000 : -1;
            if (fN !== room.nb.last) {
                room.nb.last = fN;
                room.cursor = drawNotebook(chars);
            }
            placePen(mood === 'evening' ? room.cursor : null, t);
            // the spark
            const sp = spark;
            const flying = u >= sp.t0 && u < sp.t1 + 0.15;
            const s = sparkProgress(u);
            const p = sp.curve.getPointAt(Math.min(1, s));
            sp.core.position.copy(p); sp.halo.position.copy(p); sp.light.position.copy(p);
            const born = clamp01((u - sp.t0) / 0.25);
            const land = clamp01((u - sp.t1) / 0.35);
            sp.uCore.value = flying ? born * (1 - land) * (0.85 + 0.15 * Math.sin(u * 37)) : 0;
            sp.light.intensity = flying ? 0.55 * born * (1 - land) : 0;
            sp.core.visible = sp.halo.visible = flying;
            sp.trail.visible = u >= sp.t0 - 0.05;
            // her flower keeps a little of the spark's warmth
            const after = u - sp.t1;
            sp.bloomLight.intensity = after > 0 ? 0.10 + 0.30 * Math.exp(-after * 1.4) : 0;
        } else {
            // the fire breathes
            const n = Math.sin(t * 8.3) * 0.5 + Math.sin(t * 13.7 + 1.3) * 0.3 + Math.sin(t * 23.1 + 0.4) * 0.2;
            camp.fireLight.intensity = 7.0 * (0.86 + 0.14 * n);
            camp.uEmber.value = 0.9 + 0.12 * n;
            camp.uBulb.value = 1.0;
        }
    }
    function placePen(cursor, t) {
        const pen = room.pen;
        if (!pen || !room.nbPages) return;
        room.nbPages.updateMatrixWorld(true);
        if (!room._ray) {
            room._ray = new T.Raycaster();
            const bb = new T.Box3();
            room.nbPages.geometry.computeBoundingBox();
            room._pb = room.nbPages.geometry.boundingBox.clone();
        }
        const pb = room._pb;
        const pageAt = (u, v) => {                       // page UV -> world point on the page surface
            const lx = lerp(pb.min.x, pb.max.x, u), lz = lerp(pb.max.z, pb.min.z, v);
            const top = room.nbPages.localToWorld(new T.Vector3(lx, pb.max.y + 0.05, lz));
            room._ray.set(top, new T.Vector3(0, -1, 0));
            const hit = room._ray.intersectObject(room.nbPages, false)[0];
            return hit ? hit.point : room.nbPages.localToWorld(new T.Vector3(lx, pb.max.y, lz));
        };
        let tip, dir;
        if (cursor) {
            const wig = Math.sin(t * 31) * 3 + Math.sin(t * 53) * 2;
            const u = cursor.x / NB_W, v = 1 - (cursor.y - 6 + wig) / NB_H;
            tip = pageAt(Math.min(0.97, u), v);
            tip.y += 0.0005 + Math.max(0, Math.sin(t * 7.1)) * 0.0015;
            dir = new T.Vector3(0.62, 0.62, 0.42).normalize();
        } else {
            tip = pageAt(0.80, 0.30);
            tip.y += 0.005;
            dir = new T.Vector3(0.62, 0.05, -0.78).normalize();
        }
        const local = roomG.worldToLocal(tip.clone());
        pen.position.copy(local);
        pen.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), dir);
    }

    // first paint so frame 0 of any probe is complete
    drawChat(4);
    room.cursor = drawNotebook(0);

    return {
        group,
        mark: toSet(ROOM_AT, MARK_CORNER.x, 0, MARK_CORNER.z),
        markAt,
        camera,
        update,
        flowerTarget: () => spark.dest.clone().add(roomG.position),
        parts: { roomG, campG, room, camp, march, spark },
        dispose() { },
    };
}

// merge BufferGeometries (position/normal/uv, indexed) without an addon import
function mergeGeometries(T, geos) {
    let nv = 0, ni = 0;
    for (const g of geos) { nv += g.attributes.position.count; ni += g.index ? g.index.count : g.attributes.position.count; }
    const pos = new Float32Array(nv * 3), nor = new Float32Array(nv * 3), uvs = new Float32Array(nv * 2);
    const idx = new Uint32Array(ni);
    let ov = 0, oi = 0;
    for (const g of geos) {
        const p = g.attributes.position, n = g.attributes.normal, u = g.attributes.uv;
        pos.set(p.array, ov * 3);
        if (n) nor.set(n.array, ov * 3);
        if (u) uvs.set(u.array, ov * 2);
        if (g.index) { for (let i = 0; i < g.index.count; i++) idx[oi + i] = g.index.array[i] + ov; oi += g.index.count; }
        else { for (let i = 0; i < p.count; i++) idx[oi + i] = ov + i; oi += p.count; }
        ov += p.count;
    }
    const out = new T.BufferGeometry();
    out.setAttribute('position', new T.BufferAttribute(pos, 3));
    out.setAttribute('normal', new T.BufferAttribute(nor, 3));
    out.setAttribute('uv', new T.BufferAttribute(uvs, 2));
    out.setIndex(new T.BufferAttribute(idx, 1));
    return out;
}
