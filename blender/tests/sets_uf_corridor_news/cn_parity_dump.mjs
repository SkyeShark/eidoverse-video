// cn_parity_dump.mjs: builds the WebGPU editions of the corridor and the evening news (eidoverse/sets/unknown_force/
// corridor.js, news.js and their cn_lib.js, untouched) headless in Deno and dumps what the Blender port must reproduce:
// every canvas-made DataTexture (the door relief, the plaque, the post, the poll, the patch, the badge, the graffiti,
// the sign atlas, the livery, the chyron ...) as raw RGBA, the post's layout, a typed post and a recount, the cap's
// flight onto a head, the doors and lights after update(), the pickets (positions, roles, signs), the steam puffs and
// the hand lights placed for a camera, and cn_lib's pure helpers (the mulberry32 streams, fitText sizes, build_mips,
// box_blur / normal_tex numbers).
//
//   cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_corridor_news/cn_parity_dump.mjs
//
// The texture library: fetchPBR answers with the main checkout's cache (EIDO_ASSET_CACHE, or mainCheckout()'s below)
// and loadImageTexture with a 1x1 placeholder: no PBR pixels are compared, only what the sets draw themselves.
// Writes blender/tests/sets_uf_corridor_news/out/parity/{cn.json, tex_<set>_<i>_<w>x<h>.bin} (test_parity.py compares).
const W = await import('npm:three@0.184.0/webgpu');
const TSL = await import('npm:three@0.184.0/tsl');
const napi = await import('npm:@napi-rs/canvas@0.1.69');
const root = Deno.cwd().replace(/\\/g, '/');
const EIDO = new URL('file:///' + root.replace(/^\/+/, '') + '/eidoverse/');
const outDir = root + '/blender/tests/sets_uf_corridor_news/out/parity';
await Deno.mkdir(outDir, { recursive: true });
// the checkout that holds the untracked shared folders, found as blender/tests/_where.py's main_checkout() finds it:
// EIDO_MAIN_CHECKOUT, else the main worktree when this checkout is a linked git worktree (its .git is a file
// "gitdir: <main>/.git/worktrees/<name>"), else this checkout
const mainCheckout = () => {
    const env = Deno.env.get('EIDO_MAIN_CHECKOUT');
    if (env) return env.replace(/\\/g, '/');
    try {
        const line = Deno.readTextFileSync(`${root}/.git`).trim();
        if (line.startsWith('gitdir:')) {
            let g = line.slice(7).trim().replace(/\\/g, '/');
            if (!/^([A-Za-z]:)?\//.test(g)) g = `${root}/${g}`;            // a relative gitdir: from this checkout
            return g.split('/').slice(0, -3).join('/');
        }
    } catch { /* .git is the repository's own folder: this is the main checkout */ }
    return root;
};
const CACHE = (Deno.env.get('EIDO_ASSET_CACHE') || `${mainCheckout()}/eidoverse/assets/cache`).replace(/\\/g, '/');

// every DataTexture the sets make, in creation order (cn_lib's dataTex / envTex go through THREE.DataTexture)
let made = [];
class DT extends W.DataTexture {
    constructor(...a) { super(...a); made.push(this); }
}
const T = { ...W, ...TSL, DataTexture: DT };

globalThis.fetchPBR = async (id, { res = '1k' } = {}) => {
    const dir = `${CACHE}/textures/${id}_${res}`;
    let files = [];
    try { files = [...Deno.readDirSync(dir)].map((e) => e.name); } catch { /* not fetched: any readable file stands in */ }
    const pick = (re) => { const f = files.find((n) => re.test(n)); return f ? `${dir}/${f}` : `${root}/eidoverse/sets/unknown_force/README.md`; };
    return { files: { diff: pick(/_Color\./), normal: pick(/_NormalGL\./), rough: pick(/_Roughness\./), ao: pick(/_AmbientOcclusion\./),
        metal: pick(/_Metalness\./), displacement: pick(/_Displacement\./) } };
};
globalThis.loadImageTexture = async () => { const t = new W.DataTexture(new Uint8Array([128, 128, 255, 255]), 1, 1); t.needsUpdate = true; return t; };
// a GLB reader standing in for GLTFLoader: meshes (position, normal, COLOR_0 -> color, index) under their node names
globalThis.GLTFLoader = class {
    async parseAsync(buf) {
        const dv = new DataView(buf);
        const jl = dv.getUint32(12, true);
        const g = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 20, jl)));
        const binOff = 20 + jl + 8;
        const acc = (i) => {
            const a = g.accessors[i], bv = g.bufferViews[a.bufferView];
            const n = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 }[a.type];
            const C = { 5126: Float32Array, 5123: Uint16Array, 5125: Uint32Array, 5121: Uint8Array }[a.componentType];
            const off = binOff + (bv.byteOffset || 0) + (a.byteOffset || 0);
            const raw = new C(buf.slice(off, off + a.count * n * C.BYTES_PER_ELEMENT));
            if (a.normalized && C !== Float32Array) { const f = new Float32Array(raw.length); const mx = C === Uint16Array ? 65535 : 255; for (let k = 0; k < raw.length; k++) f[k] = raw[k] / mx; return [f, n]; }
            return [raw, n];
        };
        const scene = new W.Group();
        for (const nd of g.nodes) {
            if (nd.mesh === undefined) continue;
            const pr = g.meshes[nd.mesh].primitives[0];
            const geo = new W.BufferGeometry();
            const A = pr.attributes;
            geo.setAttribute('position', new W.BufferAttribute(...acc(A.POSITION)));
            if (A.NORMAL !== undefined) geo.setAttribute('normal', new W.BufferAttribute(...acc(A.NORMAL)));
            if (A.COLOR_0 !== undefined) geo.setAttribute('color', new W.BufferAttribute(...acc(A.COLOR_0)));
            if (pr.indices !== undefined) { const [ix] = acc(pr.indices); geo.setIndex(new W.BufferAttribute(ix, 1)); }
            const m = new W.Mesh(geo, new W.MeshStandardMaterial());
            m.name = nd.name || g.meshes[nd.mesh].name;
            scene.add(m);
        }
        return { scene };
    }
};

const out = {};
const dumpTex = (set, list) => list.map((t, i) => {
    const im = t.image, d = im.data;
    const half = d instanceof Uint16Array;
    const name = `tex_${set}_${i}_${im.width}x${im.height}${half ? '_half' : ''}.bin`;
    Deno.writeFileSync(`${outDir}/${name}`, new Uint8Array(d.buffer, d.byteOffset, d.byteLength));
    return { i, file: name, w: im.width, h: im.height, half, srgb: t.colorSpace === W.SRGBColorSpace };
});
const v3 = (v) => [v.x, v.y, v.z];
const q4 = (q) => [q.x, q.y, q.z, q.w];

// ---------------------------------------------------------------------------------------- cn_lib's pure helpers
{
    const { makeLib, fitText } = await import(new URL('sets/unknown_force/cn_lib.js', EIDO).href);
    const L = await makeLib(T, new URL('sets/unknown_force/', EIDO));
    const streams = {};
    for (const s of [1, 2026, 41, 77, 99, 17, 118, 12, 3, 5, 0xdeadbeef]) { const r = L.rng(s); streams[s] = Array.from({ length: 16 }, () => r()); }
    const cv = L.createCanvas(1024, 256), g = cv.getContext('2d');
    const fits = [];
    for (const [txt, fam, maxW, maxH, track, weight] of [['SUPREME', 'michroma', 1380, 175, 0.16, ''], ['INTELLIGENCE', 'michroma', 1520, 132, 0.16, ''],
        ['WHAT SHALL WE CALL IT?', 'audiowide', 880, 80, 0.03, ''], ['LOSING BADLY', 'blackops', 540, 100, 0, ''],
        ['PRIVATE PROPERTY', 'rajdhani', 460, 74, 0, ''], ['NOT IN', 'kalam', 442, 155, 0, ''], ['AQUIFER', 'sedgwick', 442, 155, 0, ''],
        ['RESIDENTS PICKET AI DATA CENTER', 'rajdhani', 1720, 84, 0, ''], ['NIGHT DESK 88', 'rajdhani', 330, 34, 0.08, ''],
        ['Opponents cite water use, round-the-clock noise and power bills', 'exo', 1720, 38, 0, '']]) {
        fits.push({ txt, fam, maxW, maxH, track, size: fitText(g, txt, { x: 512, y: 128, maxW, maxH, family: L.fam[fam], weight, track }) });
    }
    const widths = {};
    for (const [fam, px, txt, weight] of [['exo', 120, 'AMERICANISM, NOT EFFECTIVE ALTRUISM', 'bold'], ['exo', 54, 'DEPARTMENT OF WAR', 'bold'],
        ['caveat', 470, 'C', ''], ['caveat', 470, 'L', ''], ['caveat', 470, 'A', ''], ['caveat', 470, 'N', ''], ['caveat', 470, 'K', ''],
        ['caveat', 470, 'E', ''], ['caveat', 470, 'R', ''], ['rajdhani', 40, 'TOWN HALL MEETING THURSDAY 7 PM', ''],
        ['michroma', 46, 'S', ''], ['blackops', 92, 'A', '']]) {
        g.font = `${weight} ${px}px ${L.fam[fam]}`.trim();
        widths[`${fam}|${px}|${weight}|${txt}`] = g.measureText(txt).width;
    }
    const data = new Uint8Array(7 * 5 * 4);
    for (let i = 0; i < data.length; i++) data[i] = (i * 37 + 11) % 256;
    const mips = L.buildMips(data, 7, 5).map((l) => [l.width, l.height, Array.from(l.data).reduce((a, b) => a + b, 0)]);
    const fld = new Float32Array(9 * 6);
    for (let i = 0; i < fld.length; i++) fld[i] = ((i * 7919) % 97) / 97;
    const blur = Array.from(L.boxBlur(fld, 9, 6, 2, 2));
    made = [];
    const hc = L.createCanvas(32, 24), hg = hc.getContext('2d');
    hg.fillStyle = '#000'; hg.fillRect(0, 0, 32, 24); hg.fillStyle = '#fff'; hg.fillRect(8, 6, 14, 10);
    hg.beginPath(); hg.arc(24, 16, 5, 0, Math.PI * 2); hg.fillStyle = 'rgb(128,128,128)'; hg.fill();
    const hf = L.heightField(hc, { blur: 2 });
    const nt = L.normalTex(hf, 6);
    const hpix = Array.from(L.canvasPixels(hc).filter((_, k) => k % 4 === 0));
    out.lib = { streams, fits, widths, mips, blur, height: Array.from(hf.h), heightCanvas: hpix,
        normal: Array.from(nt.image.data), hash: [[0, 3], [1, 3], [-2, 3], [17.31, 4.0], [3.5, -7.25]] };
    out.lib.smooth = [[0, 1, -0.5], [0, 1, 0.25], [0.2, 0.4, 0.33], [1, 0, 0.3]].map(([a, b, x]) => L.smooth(a, b, x));
}

// ------------------------------------------------------------------------------------------------- the corridor
{
    made = [];
    const C = await (await import(new URL('sets/unknown_force/corridor.js', EIDO).href)).build(T, { postText: 'AMERICANISM, NOT EFFECTIVE ALTRUISM' });
    const P = C.parts;
    const built = made.slice();
    out.corridor = { tex: dumpTex('corridor', built), cams: C.cams, focal: v3(C.focal), look: C.look };
    out.corridor.post = { layout: P.postWall.state.layout, text: P.postWall.state.text };
    // typing: half the post, then the whole; the post's DataTexture is redrawn in place (the same object)
    const postTex = P.postWall.texture;
    C.update(1.0, { post: 0.5 });
    out.corridor.typed = dumpTex('corridor_typed', [postTex])[0];
    C.update(1.0, { post: 1 });
    // a recount (the poll board's DataTexture redrawn in place)
    P.poll.setTally(512000, 418000, 141000);
    const pollTex = built.find((t) => t.image.width === 1024 && t.image.height === 1456);
    out.corridor.recount = dumpTex('corridor_recount', [pollTex])[0];
    // the cap's flight: a head at a place and a turn of its own
    const head = new W.Object3D();
    head.position.set(0.12, 1.47, 0.05); head.rotation.set(0.1, -0.3, 0.05);
    C.group.add(head);
    out.corridor.cap = [0, 0.25, 0.5, 1].map((capOn) => {
        C.update(2.0, { capOn, capHead: head, open: 0.4, lights: 0.8, screen: 0.6, beyond: 0.7, gap: 0.5 });
        const cap = P.cap;
        return { capOn, pos: v3(cap.position), q: q4(cap.quaternion), s: v3(cap.scale) };
    });
    out.corridor.update = {
        pivotL: P.doors.left.rotation.y, pivotR: P.doors.right.rotation.y,
        U: Object.fromEntries(Object.entries(P.uniforms).map(([k, u]) => [k, u.value])),
        lights: Object.fromEntries(Object.entries(P.lights).map(([k, l]) => [k, l.intensity])),
        shafts: P.shafts.visible,
    };
    out.corridor.capRest = { pos: v3(P.capRest.position), q: q4(P.capRest.quaternion) };
    out.corridor.capFit = { pos: v3(P.capFit.pos), rot: [P.capFit.rot.x, P.capFit.rot.y, P.capFit.rot.z], scale: P.capFit.scale };
    out.corridor.lightsBase = Object.fromEntries(Object.entries(P.lights).map(([k, l]) => [k, { base: l.userData.base,
        pos: v3(l.position), target: l.target ? v3(l.target.position) : null, angle: l.angle ?? null, penumbra: l.penumbra ?? null,
        color: l.color ? [l.color.r, l.color.g, l.color.b] : null }]));
    let tris = 0, meshes = 0;
    C.group.traverse((o) => { if (o.isMesh) { meshes++; const g = o.geometry; tris += (g.index ? g.index.count : g.attributes.position.count) / 3; } });
    out.corridor.counts = { meshes, tris };
    C.dispose();
}

// --------------------------------------------------------------------------------------------- the evening news
{
    made = [];
    const N = await (await import(new URL('sets/unknown_force/news.js', EIDO).href)).build(T, {});
    const P = N.parts;
    out.news = { tex: dumpTex('news', made.slice()), cams: N.cams, focal: v3(N.focal), look: N.look };
    out.news.people = P.crowd.userData.people.map((p) => ({ x: p.x, z: p.z, variant: p.variant, yaw: p.yaw, scale: p.scale, seed: p.seed,
        role: p.role, theta: p.theta, front: p.front, back: p.back }));
    // the billboards placed for a camera (the 'wide' cam), at two times
    const cam = new W.PerspectiveCamera(50, 16 / 9, 0.1, 2000);
    cam.position.set(...N.cams.wide.pos); cam.lookAt(new W.Vector3(...N.cams.wide.target)); cam.updateMatrixWorld(true);
    const steam = P.steam;
    const hand = P.crowd.children.find((o) => o.name === 'news_handlights');
    const inst = (m) => { const o = []; const M = new W.Matrix4(), p = new W.Vector3(), q = new W.Quaternion(), s = new W.Vector3();
        for (let i = 0; i < m.count; i++) { m.getMatrixAt(i, M); M.decompose(p, q, s); o.push([...v3(p), s.x]); } return o; };
    out.news.billboards = [0.0, 2.5, 9.75].map((t) => {
        N.update(t, { camera: cam, chant: 1, pulse: 0.3 });
        return { t, steam: inst(steam), steamPh: Array.from(steam.geometry.attributes.iSteam.array.filter((_, k) => k % 4 === 0)),
            hand: inst(hand) };
    });
    N.update(4.0, { spray: 0.4, floods: 0.5, lights: 0.9, chant: 0.7, pulse: 0.2, camera: cam });
    out.news.update = { U: Object.fromEntries(Object.entries(P.uniforms).filter(([k]) => k !== 'groupInv').map(([k, u]) => [k, u.value])),
        floods: P.lights.floods.map((l) => l.intensity), street: P.lights.street.map((l) => l.intensity), news: P.lights.news.intensity,
        graffiti: P.lights.graffiti.intensity, hemi: P.lights.hemi.intensity, beams: P.beams.visible };
    out.news.chyron = { state: P.chyron.state };
    const ov = new W.Group();
    P.chyron.place(ov, { fov: 42, aspect: 16 / 9 });
    out.news.chyron.place = { pos: v3(P.chyron.mesh.position), scale: P.chyron.mesh.scale.x };
    let tris = 0, meshes = 0;
    N.group.traverse((o) => { if (o.isMesh) { meshes++; const g = o.geometry; tris += ((g.index ? g.index.count : g.attributes.position.count) / 3) * (o.isInstancedMesh ? o.count : 1); } });
    out.news.counts = { meshes, tris };
    N.dispose();
}

await Deno.writeTextFile(`${outDir}/cn.json`, JSON.stringify(out));
console.log('[cn_parity_dump] wrote', outDir, 'corridor textures', out.corridor.tex.length, 'news textures', out.news.tex.length,
    'people', out.news.people.length);
Deno.exit(0);
