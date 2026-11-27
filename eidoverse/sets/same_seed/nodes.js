// sets/same_seed/nodes.js — a Blender shader node graph (exported as JSON by
// eidoverse/assets/sets/same_seed_src/export_room.py) rebuilt as a TSL material, node for node: the maths, the
// smoothsteps, the mixes, Blender's noise, the photographs laid by UV or box projection at their real size, the
// normal maps and bumps, the masks from the point and the normal in the object's own space, then a Principled BSDF as
// a MeshPhysicalNodeMaterial.
//
//   const G = makeGraphs(THREE, { image: async (ref, { interp }) => texture, isCameraRay: uniform(1) });
//   const mat = await G.material(graph, { name, lighting, attrs });   // graph: { nodes, links, output, settings }
//   const bg = await G.world(worldGraph);                              // -> { color }: a node for scene.backgroundNode
//
// Blender's space is Z-up and three's Y-up: every point, direction and normal a graph reads is taken into Blender's
// frame (x, -z, y) before the graph's maths and brought back at the end, so the graph's numbers mean what they meant.
// Vertex data the export wrote: _uv_<name> (Blender's own UVs), _tangent_<name> (MikkTSpace, for normal maps),
// _orco (Generated coordinates), _attr_<name> (colour attributes); `attrs` names the ones the meshes carry.
// Closures are blended as their parameters (Mix Shader); a Translucent BSDF is taken as a diffuse one and a
// Transparent BSDF as the closure's opacity. A node it does not know logs once and reads as 0.

import { makeNoise } from './noise.js';

export function makeGraphs(THREE, ctx) {
    const T = THREE;
    const { Fn, float, vec2, vec3, vec4, mat3, attribute, texture, uv, positionLocal, positionWorld,
        positionView, normalLocal, normalWorld, cameraPosition, cameraViewMatrix, modelWorldMatrix,
        modelWorldMatrixInverse, frontFacing, dFdx, dFdy, equirectUV, mix, clamp, select, abs, floor,
        sqrt, pow, max, min, normalize, cross, dot, length, sin, cos, tan, asin, acos, atan, exp, log, sign,
        fract, mod, reflect, transformDirection, screenUV } = T;
    const N = makeNoise(T);
    const warned = new Set();
    const warn = (msg) => { if (!warned.has(msg)) { warned.add(msg); console.warn('[same_seed nodes] ' + msg); } };

    // frames: Blender (x, y, z) Z-up <-> three (x, z, -y) Y-up
    const toBl = (v) => vec3(v.x, v.z.negate(), v.y);
    const fromBl = (v) => vec3(v.x, v.z, v.y.negate());
    const LUMA = [0.2126729, 0.7151522, 0.0721750];
    const luma = (c) => dot(vec3(c), vec3(...LUMA));

    // ------------------------------------------------------------------------------------------ values
    // every value is { t: 'float' | 'vec3' | 'color' | 'shader', v: node | closure, a?: alpha node }
    // numbers known when the material is built (so mixes of them can be done here, not in the shader)
    const CONST = new WeakMap();
    const K = (x) => { const n = float(x); CONST.set(n, x); return n; };
    const KV = (a) => { const n = vec3(a[0], a[1], a[2]); CONST.set(n, [a[0], a[1], a[2]]); return n; };
    const F = (v) => ({ t: 'float', v: typeof v === 'number' ? K(v) : v });
    const V = (v) => ({ t: 'vec3', v });
    const Cc = (v, a) => ({ t: 'color', v, a });
    function asFloat(x) {
        if (x.t === 'float') return x.v;
        if (x.t === 'color') return luma(x.v);
        if (x.t === 'vec3') return x.v.x.add(x.v.y).add(x.v.z).div(3.0);
        return float(0.0);
    }
    function asVec(x) {
        if (x.t === 'float') return vec3(x.v, x.v, x.v);
        if (x.t === 'vec3' || x.t === 'color') return vec3(x.v);
        return vec3(0.0);
    }
    const asColor = asVec;
    function constant(val, want) {
        if (Array.isArray(val)) {
            if (want === 'float') return F(val.slice(0, 3).reduce((a, b) => a + b, 0) / Math.min(3, val.length));
            const v3_ = KV([val[0], val[1] ?? val[0], val[2] ?? val[0]]);
            return want === 'color' || val.length === 4 ? Cc(v3_, K(val[3] ?? 1.0)) : V(v3_);
        }
        if (typeof val === 'boolean') return F(val ? 1.0 : 0.0);
        if (typeof val === 'number') return want === 'vec3' || want === 'color' ? (want === 'color' ? Cc(KV([val, val, val]), K(1)) : V(KV([val, val, val]))) : F(val);
        return want === 'shader' ? { t: 'shader', v: null } : F(0.0);
    }

    // ------------------------------------------------------------------------------------------ geometry
    const objPos = () => toBl(positionLocal);
    const worldPos = () => toBl(positionWorld);
    const worldNrm = () => toBl(normalize(normalWorld));
    const incoming = () => toBl(normalize(cameraPosition.sub(positionWorld)));
    // a UV map by name (Blender's own (u, v)); the mesh's first map when it has no such attribute
    const uvLayer = (name, attrs) => {
        const a = '_uv_' + attrName(name || '');
        if (name && attrs && attrs.has(a + '=uv')) {             // (the map the mesh carries as its TEXCOORD_0)
            const u = uv();
            return vec3(u.x, float(1.0).sub(u.y), 0.0);
        }
        if (name && (!attrs || attrs.has(a))) return vec3(attribute(a, 'vec2'), 0.0);
        if (name) warn(`no UV map ${name} on a mesh: its first map is read`);
        const u = uv();
        return vec3(u.x, float(1.0).sub(u.y), 0.0);
    };
    const attrName = (s) => String(s).replace(/[^A-Za-z0-9]/g, '_').toLowerCase();
    const objNormalFromWorld = (nBl) => toBl(normalize(fromBl(nBl).mul(mat3(modelWorldMatrix))));   // (M^T n: world -> object for normals)

    // Euler XYZ (radians) -> mat3 columns, Blender's
    function eulerMat(r) {
        const [x, y, z] = r;
        const cx = Math.cos(x), sx = Math.sin(x), cy = Math.cos(y), sy = Math.sin(y), cz = Math.cos(z), sz = Math.sin(z);
        // R = Rz * Ry * Rx (rows)
        return [[cy * cz, sx * sy * cz - cx * sz, cx * sy * cz + sx * sz],
                [cy * sz, sx * sy * sz + cx * cz, cx * sy * sz - sx * cz],
                [-sy, sx * cy, cx * cy]];
    }
    const mulRows = (R, v) => vec3(dot(vec3(...R[0]), v), dot(vec3(...R[1]), v), dot(vec3(...R[2]), v));
    const transpose = (R) => [[R[0][0], R[1][0], R[2][0]], [R[0][1], R[1][1], R[2][1]], [R[0][2], R[1][2], R[2][2]]];

    // ------------------------------------------------------------------------------------------ colour helpers
    const rgb2hsv = Fn(([c]) => {
        const cmax = max(c.r, max(c.g, c.b)), cmin = min(c.r, min(c.g, c.b)), cdelta = cmax.sub(cmin);
        const v = cmax;
        const s = select(cmax.notEqual(0.0), cdelta.div(cmax), float(0.0));
        const d = max(cdelta, 1e-20);
        const cr = cmax.sub(c.r).div(d), cg = cmax.sub(c.g).div(d), cb = cmax.sub(c.b).div(d);
        let h = select(c.r.equal(cmax), cb.sub(cg), select(c.g.equal(cmax), float(2.0).add(cr).sub(cb), float(4.0).add(cg).sub(cr)));
        h = h.div(6.0);
        h = select(h.lessThan(0.0), h.add(1.0), h);
        h = select(s.equal(0.0), float(0.0), h);
        return vec3(h, s, v);
    }).setLayout({ name: 'bl_rgb_to_hsv', type: 'vec3', inputs: [{ name: 'c', type: 'vec3' }] });
    const hsv2rgb = Fn(([hsv]) => {
        const h = hsv.x, s = hsv.y, v = hsv.z;
        const hh = select(h.equal(1.0), float(0.0), h).mul(6.0);
        const i = floor(hh), f = hh.sub(i);
        const p = v.mul(float(1.0).sub(s)), q = v.mul(float(1.0).sub(s.mul(f))), t = v.mul(float(1.0).sub(s.mul(float(1.0).sub(f))));
        const c0 = vec3(v, t, p), c1 = vec3(q, v, p), c2 = vec3(p, v, t), c3 = vec3(p, q, v), c4 = vec3(t, p, v), c5 = vec3(v, p, q);
        const r = select(i.lessThan(0.5), c0, select(i.lessThan(1.5), c1, select(i.lessThan(2.5), c2, select(i.lessThan(3.5), c3, select(i.lessThan(4.5), c4, c5)))));
        return select(s.equal(0.0), vec3(v, v, v), r);
    }).setLayout({ name: 'bl_hsv_to_rgb', type: 'vec3', inputs: [{ name: 'hsv', type: 'vec3' }] });

    const safeDiv = (a, b) => select(b.notEqual(0.0), a.div(b), float(0.0));
    const fresnelDielectric = (cosi, eta) => {
        const c = abs(cosi);
        const g = eta.mul(eta).sub(1.0).add(c.mul(c));
        const gs = sqrt(max(g, 0.0));
        const A = gs.sub(c).div(gs.add(c));
        const B = c.mul(gs.add(c)).sub(1.0).div(c.mul(gs.sub(c)).add(1.0));
        return select(g.greaterThan(0.0), A.mul(A).mul(0.5).mul(B.mul(B).add(1.0)), float(1.0));
    };

    // ------------------------------------------------------------------------------------------ the evaluator
    async function evaluate(graph, opts = {}) {
        const nodes = graph.nodes, links = new Map(), cache = new Map();
        for (const [fn, fs, tn, ts] of graph.links) links.set(tn + '\u0000' + ts, [fn, fs]);
        const textures = new Map();

        function tex(ref, interp) {
            if (!ref) return Promise.resolve(null);
            const key = JSON.stringify(ref) + '|' + interp;
            if (!textures.has(key)) textures.set(key, ctx.image(ref, { interp }));
            return textures.get(key);
        }

        async function input(name, id, want) {
            const l = links.get(name + '\u0000' + id);
            if (l) return await output(l[0], l[1]);
            const n = nodes[name];
            const val = n && n.in ? n.in[id] : undefined;
            return constant(val, want);
        }
        const inF = async (name, id) => asFloat(await input(name, id, 'float'));
        const inV = async (name, id) => asVec(await input(name, id, 'vec3'));
        const inC = async (name, id) => asColor(await input(name, id, 'color'));
        const has = (name, id) => links.has(name + '\u0000' + id);
        const def = (name, id, d) => { const v = nodes[name]?.in?.[id]; return v === undefined ? d : v; };

        async function output(name, sock) {
            const key = name + '\u0000' + sock;
            if (!cache.has(key)) cache.set(key, compute(name, sock));
            return await cache.get(key);
        }

        async function compute(name, sock) {
            const n = nodes[name];
            if (!n) { warn(`link from a missing node ${name}`); return F(0); }
            if (n.mute) {
                const pass = n.mute.find((m) => m[1] === sock || m[0] === sock);
                return pass ? await input(name, pass[0], 'vec3') : F(0);
            }
            const P = n.props || {};
            switch (n.type) {
            case 'ShaderNodeValue': return F(typeof P.out === 'number' ? P.out : 0.0);
            case 'ShaderNodeRGB': return Cc(vec3(...(Array.isArray(P.out) ? P.out : [0.5, 0.5, 0.5]).slice(0, 3)), float(1));
            case 'ShaderNodeTexCoord': {
                if (sock === 'Object') return V(objPos());
                if (sock === 'Generated') {
                    if (opts.world) return V(opts.dirBl());
                    if (opts.attrs && !opts.attrs.has('_orco')) { warn('no Generated coordinates on a mesh: its object space is read'); return V(objPos()); }
                    return V(attribute('_orco', 'vec3'));
                }
                if (sock === 'UV') return V(uvLayer(null, opts.attrs));
                if (sock === 'Normal') return V(toBl(normalize(normalLocal)));
                if (sock === 'Camera') return V(positionView);
                if (sock === 'Window') return V(vec3(screenUV.x, float(1.0).sub(screenUV.y), 0.0));
                if (sock === 'Reflection') return V(toBl(reflect(positionWorld.sub(cameraPosition).normalize(), normalize(normalWorld))));
                return V(vec3(0.0));
            }
            case 'ShaderNodeNewGeometry': {
                if (sock === 'Position') return V(worldPos());
                if (sock === 'Normal') return V(worldNrm());
                if (sock === 'True Normal') return V(toBl(normalize(cross(dFdx(positionWorld), dFdy(positionWorld)))));
                if (sock === 'Incoming') return V(incoming());
                if (sock === 'Backfacing') return F(select(frontFacing, float(0.0), float(1.0)));
                if (sock === 'Pointiness') return F(0.5);
                return F(0.0);
            }
            case 'ShaderNodeUVMap': return V(uvLayer(P.uv_map || null, opts.attrs));
            case 'ShaderNodeAttribute': {
                const an = '_attr_' + attrName(P.attribute_name);
                if (P.attribute_type && P.attribute_type !== 'GEOMETRY') warn(`Attribute ${P.attribute_type} read as 0`);
                if ((P.attribute_type && P.attribute_type !== 'GEOMETRY') || (opts.attrs && !opts.attrs.has(an))) {
                    if (opts.attrs && !opts.attrs.has(an)) warn(`no attribute ${P.attribute_name} on a mesh: read as 0`);
                    return sock === 'Alpha' ? F(1.0) : (sock === 'Fac' ? F(0.0) : Cc(KV([0, 0, 0]), K(1)));
                }
                const a = attribute(an, 'vec4');
                if (sock === 'Color') return Cc(a.xyz, a.w);
                if (sock === 'Vector') return V(a.xyz);
                if (sock === 'Fac') return F(a.x.add(a.y).add(a.z).div(3.0));
                return F(a.w);
            }
            case 'ShaderNodeObjectInfo': {
                if (sock === 'Location') return V(toBl(modelWorldMatrix.mul(vec4(0, 0, 0, 1)).xyz));
                if (sock === 'Random') return F(0.5);
                return F(0.0);
            }
            case 'ShaderNodeLightPath': {
                if (sock === 'Is Camera Ray') return F(ctx.isCameraRay);
                if (sock === 'Is Shadow Ray' || sock === 'Is Reflection Ray' || sock === 'Is Transmission Ray' || sock === 'Is Glossy Ray' || sock === 'Is Diffuse Ray' || sock === 'Is Singular Ray' || sock === 'Is Volume Scatter Ray') return F(0.0);
                if (sock === 'Ray Length') return F(length(positionView));
                return F(0.0);
            }
            case 'ShaderNodeSeparateXYZ': {
                const v = await inV(name, 'Vector');
                return F(sock === 'X' ? v.x : sock === 'Y' ? v.y : v.z);
            }
            case 'ShaderNodeCombineXYZ': return V(vec3(await inF(name, 'X'), await inF(name, 'Y'), await inF(name, 'Z')));
            case 'ShaderNodeSeparateColor': {
                let c = await inC(name, 'Color');
                if (P.mode === 'HSV') c = rgb2hsv(c);
                else if (P.mode === 'HSL') warn('Separate Color HSL read as HSV');
                if (P.mode === 'HSL') c = rgb2hsv(c);
                return F(sock === 'Red' ? c.x : sock === 'Green' ? c.y : c.z);
            }
            case 'ShaderNodeCombineColor': {
                const c = vec3(await inF(name, 'Red'), await inF(name, 'Green'), await inF(name, 'Blue'));
                return Cc(P.mode === 'RGB' || !P.mode ? c : hsv2rgb(c), float(1));
            }
            case 'ShaderNodeMath': return F(await math(name, P));
            case 'ShaderNodeVectorMath': return await vmath(name, P, sock);
            case 'ShaderNodeMapRange': return await mapRange(name, P);
            case 'ShaderNodeClamp': {
                const x = await inF(name, 'Value'), a = await inF(name, 'Min'), b = await inF(name, 'Max');
                return F(P.clamp_type === 'RANGE' ? clamp(x, min(a, b), max(a, b)) : min(max(x, a), b));
            }
            case 'ShaderNodeMix': return await mixNode(name, P);
            case 'ShaderNodeMixRGB': return await mixRGB(name, P);
            case 'ShaderNodeHueSaturation': {
                const c = await inC(name, 'Color'), fac = await inF(name, 'Fac');
                const hue = await inF(name, 'Hue'), sat = await inF(name, 'Saturation'), val = await inF(name, 'Value');
                const hsv = rgb2hsv(c);
                const h = fract(hsv.x.add(hue).add(0.5)), s = clamp(hsv.y.mul(sat), 0.0, 1.0), v = hsv.z.mul(val);
                const out = hsv2rgb(vec3(h, s, v));
                return Cc(mix(c, out, fac), float(1));
            }
            case 'ShaderNodeRGBToBW': return F(luma(await inC(name, 'Color')));
            case 'ShaderNodeInvert': {
                const c = await inC(name, 'Color'), fac = await inF(name, 'Fac');
                return Cc(mix(c, vec3(1.0).sub(c), fac), float(1));
            }
            case 'ShaderNodeGamma': {
                const c = await inC(name, 'Color'), g = await inF(name, 'Gamma');
                return Cc(select(c.greaterThan(vec3(0.0)), pow(max(c, vec3(1e-20)), vec3(g)), c), float(1));
            }
            case 'ShaderNodeBrightContrast': {
                const c = await inC(name, 'Color'), b = await inF(name, 'Bright'), k = await inF(name, 'Contrast');
                const a = float(1.0).add(k), bb = b.sub(k.mul(0.5));
                return Cc(max(c.mul(a).add(bb), vec3(0.0)), float(1));
            }
            case 'ShaderNodeValToRGB': return await ramp(name, P, sock);
            case 'ShaderNodeRGBCurve': case 'ShaderNodeFloatCurve': case 'ShaderNodeVectorCurve': return await curves(name, P, n.type);
            case 'ShaderNodeMapping': return V(await mapping(name, P));
            case 'ShaderNodeVectorTransform': return V(await vtransform(name, P));
            case 'ShaderNodeTexNoise': {
                if ((P.noise_dimensions || '3D') !== '3D') warn(`Noise Texture ${P.noise_dimensions} read as 3D`);
                if (P.noise_type && P.noise_type !== 'FBM') warn(`Noise Texture ${P.noise_type} read as fBm`);
                const co = has(name, 'Vector') ? await inV(name, 'Vector') : objPos();
                const numbers = ['Scale', 'Detail', 'Roughness', 'Lacunarity', 'Distortion'].map((k) => { if (has(name, k)) warn(`Noise Texture: a linked ${k} is read as its number`); return def(name, k, { Scale: 5, Detail: 2, Roughness: 0.5, Lacunarity: 2, Distortion: 0 }[k]); });
                if (numbers[4]) warn('Noise Texture distortion is not read');
                const fac = N.noise(co, { scale: numbers[0], detail: numbers[1], roughness: numbers[2], lacunarity: numbers[3], normalize: P.normalize !== false });
                if (sock === 'Color') {
                    const off = (k) => vec3(100.0 + k * 13.7, 100.0 + k * 31.1, 100.0 + k * 7.3);
                    return Cc(vec3(fac, N.noise(co.add(off(1)), { scale: numbers[0], detail: numbers[1], roughness: numbers[2], lacunarity: numbers[3] }),
                        N.noise(co.add(off(2)), { scale: numbers[0], detail: numbers[1], roughness: numbers[2], lacunarity: numbers[3] })), float(1));
                }
                return F(fac);
            }
            case 'ShaderNodeTexWhiteNoise': {
                const co = await inV(name, 'Vector');
                if ((P.noise_dimensions || '3D') !== '3D') warn(`White Noise ${P.noise_dimensions} read as 3D`);
                return sock === 'Color' ? Cc(N.whiteColor(co), float(1)) : F(N.white(co));
            }
            case 'ShaderNodeTexVoronoi': {
                const co = has(name, 'Vector') ? await inV(name, 'Vector') : objPos();
                if (P.feature !== 'F1' || P.distance !== 'EUCLIDEAN') warn(`Voronoi ${P.feature}/${P.distance} read as F1 Euclidean`);
                return F(N.voronoiF1(co, { scale: def(name, 'Scale', 5), randomness: def(name, 'Randomness', 1) }));
            }
            case 'ShaderNodeTexImage': return await image(name, P, sock);
            case 'ShaderNodeTexEnvironment': {
                const t = await tex(P.image, P.interpolation);
                const dir = has(name, 'Vector') ? await inV(name, 'Vector') : (opts.world ? opts.dirBl() : incoming().negate());
                if (!t) return Cc(vec3(0.0), float(1));
                const s = texture(t, equirectUV(normalize(fromBl(dir))));
                return Cc(s.rgb, float(1));
            }
            case 'ShaderNodeNormalMap': return V(await normalMapNode(name, P));
            case 'ShaderNodeBump': return V(await bumpNode(name, P));
            case 'ShaderNodeFresnel': {
                const ior = await inF(name, 'IOR');
                const nrm = has(name, 'Normal') ? await inV(name, 'Normal') : worldNrm();
                const I = incoming();
                const eta = select(frontFacing, max(ior, 1e-5), float(1.0).div(max(ior, 1e-5)));
                return F(fresnelDielectric(dot(I, normalize(nrm)), eta));
            }
            case 'ShaderNodeLayerWeight': {
                const blend = await inF(name, 'Blend');
                const nrm = has(name, 'Normal') ? await inV(name, 'Normal') : worldNrm();
                const I = incoming();
                const eta = max(float(1.0).sub(blend), 1e-5);
                const cosi = dot(I, normalize(nrm));
                if (sock === 'Fresnel') return F(fresnelDielectric(cosi, select(frontFacing, float(1.0).div(eta), eta)));
                const b = clamp(blend, 0.0, 0.99999);
                const e = select(b.lessThan(0.5), b.mul(2.0), float(0.5).div(float(1.0).sub(b)));
                return F(float(1.0).sub(pow(abs(cosi), e)));
            }
            // closures
            case 'ShaderNodeBsdfPrincipled': return { t: 'shader', v: await principled(name) };
            case 'ShaderNodeEmission': case 'ShaderNodeBackground': {
                const c = await inC(name, 'Color'), s = await inF(name, 'Strength');
                return { t: 'shader', v: closure({ kind: 'emission', emission: c.mul(s), color: vec3(0.0) }) };
            }
            case 'ShaderNodeBsdfTransparent': return { t: 'shader', v: closure({ kind: 'transparent', opacity: float(0.0) }) };
            case 'ShaderNodeBsdfDiffuse': case 'ShaderNodeBsdfTranslucent': {
                const nrm = has(name, 'Normal') ? await inV(name, 'Normal') : null;
                return { t: 'shader', v: closure({ color: await inC(name, 'Color'), rough: K(1.0), metal: K(0.0), normal: nrm }) };
            }
            case 'ShaderNodeBsdfGlossy': case 'ShaderNodeBsdfAnisotropic': {
                const nrm = has(name, 'Normal') ? await inV(name, 'Normal') : null;
                return { t: 'shader', v: closure({ color: await inC(name, 'Color'), rough: await inF(name, 'Roughness'), metal: float(1.0), normal: nrm }) };
            }
            case 'ShaderNodeBsdfGlass': case 'ShaderNodeBsdfRefraction': {
                return { t: 'shader', v: closure({ color: await inC(name, 'Color'), rough: await inF(name, 'Roughness'), metal: float(0.0), transmission: float(1.0), ior: await inF(name, 'IOR') }) };
            }
            case 'ShaderNodeMixShader': {
                const f = await inF(name, 'Fac');
                const a = (await input(name, 'Shader', 'shader')).v || closure({});
                const b = (await input(name, 'Shader_001', 'shader')).v || closure({});
                return { t: 'shader', v: mixClosures(a, b, f) };
            }
            case 'ShaderNodeAddShader': {
                const a = (await input(name, 'Shader', 'shader')).v || closure({});
                const b = (await input(name, 'Shader_001', 'shader')).v || closure({});
                return { t: 'shader', v: addClosures(a, b) };
            }
            default:
                warn(`node ${n.type} is not rebuilt (read as 0)`);
                return F(0.0);
            }
        }

        async function math(name, P) {
            const op = P.operation || 'ADD';
            const a = await inF(name, 'Value'), b = await inF(name, 'Value_001');
            const c = ['MULTIPLY_ADD', 'COMPARE', 'SMOOTH_MIN', 'SMOOTH_MAX', 'WRAP'].includes(op) ? await inF(name, 'Value_002') : null;
            let r;
            switch (op) {
            case 'ADD': r = a.add(b); break;
            case 'SUBTRACT': r = a.sub(b); break;
            case 'MULTIPLY': r = a.mul(b); break;
            case 'DIVIDE': r = safeDiv(a, b); break;
            case 'MULTIPLY_ADD': r = a.mul(b).add(c); break;
            case 'POWER': r = select(a.greaterThanEqual(0.0), pow(max(a, 0.0), b), select(fract(b).equal(0.0), pow(abs(a), b).mul(select(mod(abs(b), 2.0).equal(1.0), float(-1.0), float(1.0))), float(0.0))); break;
            case 'LOGARITHM': r = select(a.greaterThan(0.0).and(b.greaterThan(0.0)), log(a).div(log(b)), float(0.0)); break;
            case 'SQRT': r = select(a.greaterThan(0.0), sqrt(max(a, 0.0)), float(0.0)); break;
            case 'INVERSE_SQRT': r = select(a.greaterThan(0.0), float(1.0).div(sqrt(max(a, 1e-30))), float(0.0)); break;
            case 'ABSOLUTE': r = abs(a); break;
            case 'EXPONENT': r = exp(a); break;
            case 'MINIMUM': r = min(a, b); break;
            case 'MAXIMUM': r = max(a, b); break;
            case 'LESS_THAN': r = select(a.lessThan(b), float(1.0), float(0.0)); break;
            case 'GREATER_THAN': r = select(a.greaterThan(b), float(1.0), float(0.0)); break;
            case 'SIGN': r = sign(a); break;
            case 'COMPARE': r = select(abs(a.sub(b)).lessThanEqual(max(c, 1e-5)), float(1.0), float(0.0)); break;
            case 'SMOOTH_MIN': { const h = max(c.sub(abs(a.sub(b))), 0.0).div(max(c, 1e-20)); r = select(c.notEqual(0.0), min(a, b).sub(h.mul(h).mul(h).mul(c).div(6.0)), min(a, b)); break; }
            case 'SMOOTH_MAX': { const h = max(c.sub(abs(a.negate().sub(b.negate()))), 0.0).div(max(c, 1e-20)); r = select(c.notEqual(0.0), max(a, b).add(h.mul(h).mul(h).mul(c).div(6.0)), max(a, b)); break; }
            case 'ROUND': r = floor(a.add(0.5)); break;
            case 'FLOOR': r = floor(a); break;
            case 'CEIL': r = floor(a).add(select(fract(a).greaterThan(0.0), float(1.0), float(0.0))); break;
            case 'TRUNC': r = select(a.greaterThanEqual(0.0), floor(a), floor(a.negate()).negate()); break;
            case 'FRACT': r = a.sub(floor(a)); break;
            case 'MODULO': r = select(b.notEqual(0.0), a.sub(b.mul(select(a.div(b).greaterThanEqual(0.0), floor(a.div(b)), floor(a.div(b).negate()).negate()))), float(0.0)); break;
            case 'FLOORED_MODULO': r = select(b.notEqual(0.0), a.sub(floor(a.div(b)).mul(b)), float(0.0)); break;
            case 'WRAP': { const range = b.sub(c); r = select(range.notEqual(0.0), a.sub(range.mul(floor(a.sub(c).div(range)))), c); break; }
            case 'SNAP': r = select(b.notEqual(0.0), floor(a.div(b)).mul(b), float(0.0)); break;
            case 'PINGPONG': { const m = select(b.notEqual(0.0), abs(fract(a.sub(b).div(b.mul(2.0))).mul(b.mul(2.0)).sub(b)), float(0.0)); r = m; break; }
            case 'SINE': r = sin(a); break;
            case 'COSINE': r = cos(a); break;
            case 'TANGENT': r = tan(a); break;
            case 'ARCSINE': r = asin(clamp(a, -1.0, 1.0)); break;
            case 'ARCCOSINE': r = acos(clamp(a, -1.0, 1.0)); break;
            case 'ARCTANGENT': r = atan(a); break;
            case 'ARCTAN2': r = atan(a, b); break;
            case 'SINH': r = exp(a).sub(exp(a.negate())).mul(0.5); break;
            case 'COSH': r = exp(a).add(exp(a.negate())).mul(0.5); break;
            case 'TANH': { const e2 = exp(a.mul(2.0)); r = e2.sub(1.0).div(e2.add(1.0)); break; }
            case 'RADIANS': r = a.mul(Math.PI / 180); break;
            case 'DEGREES': r = a.mul(180 / Math.PI); break;
            default: warn(`Math ${op} read as ADD`); r = a.add(b);
            }
            return P.use_clamp ? clamp(r, 0.0, 1.0) : r;
        }

        async function vmath(name, P, sock) {
            const op = P.operation || 'ADD';
            const a = await inV(name, 'Vector'), b = await inV(name, 'Vector_001');
            let r = null, f = null;
            switch (op) {
            case 'ADD': r = a.add(b); break;
            case 'SUBTRACT': r = a.sub(b); break;
            case 'MULTIPLY': r = a.mul(b); break;
            case 'DIVIDE': r = vec3(safeDiv(a.x, b.x), safeDiv(a.y, b.y), safeDiv(a.z, b.z)); break;
            case 'MULTIPLY_ADD': r = a.mul(b).add(await inV(name, 'Vector_002')); break;
            case 'SCALE': r = a.mul(await inF(name, 'Scale')); break;
            case 'CROSS_PRODUCT': r = cross(a, b); break;
            case 'DOT_PRODUCT': f = dot(a, b); break;
            case 'LENGTH': f = length(a); break;
            case 'DISTANCE': f = length(a.sub(b)); break;
            case 'NORMALIZE': r = select(length(a).greaterThan(0.0), normalize(a), vec3(0.0)); break;
            case 'ABSOLUTE': r = abs(a); break;
            case 'MINIMUM': r = min(a, b); break;
            case 'MAXIMUM': r = max(a, b); break;
            case 'FLOOR': r = floor(a); break;
            case 'FRACTION': r = fract(a); break;
            case 'SNAP': r = floor(a.div(b)).mul(b); break;
            case 'SINE': r = sin(a); break;
            case 'COSINE': r = cos(a); break;
            case 'REFLECT': r = reflect(a, normalize(b)); break;
            case 'PROJECT': r = b.mul(safeDiv(dot(a, b), dot(b, b))); break;
            default: warn(`Vector Math ${op} read as ADD`); r = a.add(b);
            }
            if (sock === 'Value') return F(f ?? length(r));
            return V(r ?? vec3(f, f, f));
        }

        async function mapRange(name, P) {
            if (P.data_type === 'FLOAT_VECTOR') warn('Map Range on vectors read per component of x');
            const x = await inF(name, 'Value');
            const a0 = await inF(name, 'From Min'), a1 = await inF(name, 'From Max');
            const b0 = await inF(name, 'To Min'), b1 = await inF(name, 'To Max');
            const it = P.interpolation_type || 'LINEAR';
            let t = safeDiv(x.sub(a0), a1.sub(a0));
            let r;
            if (it === 'SMOOTHSTEP' || it === 'SMOOTHERSTEP') {
                t = clamp(t, 0.0, 1.0);
                t = it === 'SMOOTHSTEP' ? t.mul(t).mul(float(3.0).sub(t.mul(2.0))) : t.mul(t).mul(t).mul(t.mul(t.mul(6.0).sub(15.0)).add(10.0));
                r = b0.add(t.mul(b1.sub(b0)));
            } else if (it === 'STEPPED') {
                const steps = await inF(name, 'Steps');
                t = safeDiv(floor(t.mul(steps.add(1.0))), steps);
                r = b0.add(t.mul(b1.sub(b0)));
                if (P.clamp) r = clamp(r, min(b0, b1), max(b0, b1));
            } else {
                r = b0.add(t.mul(b1.sub(b0)));
                if (P.clamp) r = clamp(r, min(b0, b1), max(b0, b1));
            }
            return F(r);
        }

        async function mixNode(name, P) {
            const dt = P.data_type || 'FLOAT';
            if (dt === 'FLOAT') {
                let f = await inF(name, 'Factor_Float');
                if (P.clamp_factor !== false) f = clamp(f, 0.0, 1.0);
                return F(mix(await inF(name, 'A_Float'), await inF(name, 'B_Float'), f));
            }
            if (dt === 'VECTOR') {
                let f = P.factor_mode === 'NON_UNIFORM' ? await inV(name, 'Factor_Vector') : await inF(name, 'Factor_Float');
                if (P.clamp_factor !== false) f = clamp(f, 0.0, 1.0);
                return V(mix(await inV(name, 'A_Vector'), await inV(name, 'B_Vector'), f));
            }
            let f = await inF(name, 'Factor_Float');
            if (P.clamp_factor !== false) f = clamp(f, 0.0, 1.0);
            const a = await inC(name, 'A_Color'), b = await inC(name, 'B_Color');
            let r = blend(P.blend_type || 'MIX', a, b, f);
            if (P.clamp_result) r = clamp(r, 0.0, 1.0);
            return Cc(r, float(1));
        }

        async function mixRGB(name, P) {
            let f = await inF(name, 'Fac');
            f = clamp(f, 0.0, 1.0);
            const a = await inC(name, 'Color1'), b = await inC(name, 'Color2');
            let r = blend(P.blend_type || 'MIX', a, b, f);
            if (P.use_clamp) r = clamp(r, 0.0, 1.0);
            return Cc(r, float(1));
        }

        function blend(type, a, b, f) {
            switch (type) {
            case 'MIX': return mix(a, b, f);
            case 'MULTIPLY': return mix(a, a.mul(b), f);
            case 'ADD': return a.add(b.mul(f));
            case 'SUBTRACT': return a.sub(b.mul(f));
            case 'SCREEN': return vec3(1.0).sub(vec3(1.0).sub(b.mul(f)).mul(vec3(1.0).sub(a)));
            case 'DIVIDE': return mix(a, vec3(safeDiv(a.x, b.x), safeDiv(a.y, b.y), safeDiv(a.z, b.z)), f);
            case 'DIFFERENCE': return mix(a, abs(a.sub(b)), f);
            case 'EXCLUSION': return max(mix(a, a.add(b).sub(a.mul(b).mul(2.0)), f), vec3(0.0));
            case 'DARKEN': return mix(a, min(a, b), f);
            case 'LIGHTEN': return mix(a, max(a, b), f);
            case 'OVERLAY': {
                const lo = a.mul(b).mul(2.0), hi = vec3(1.0).sub(vec3(1.0).sub(a).mul(vec3(1.0).sub(b)).mul(2.0));
                return mix(a, select(a.lessThan(vec3(0.5)), lo, hi), f);
            }
            case 'SOFT_LIGHT': {
                const scr = vec3(1.0).sub(vec3(1.0).sub(b).mul(vec3(1.0).sub(a)));
                return mix(a, vec3(1.0).sub(a).mul(b).mul(a).add(a.mul(scr)), f);
            }
            case 'LINEAR_LIGHT': return a.add(b.mul(2.0).sub(1.0).mul(f));
            default: warn(`blend ${type} read as MIX`); return mix(a, b, f);
            }
        }

        async function ramp(name, P, sock) {
            const r = P.ramp;
            const x = clamp(await inF(name, 'Fac'), 0.0, 1.0);
            const els = (r?.elements || [[0, [0, 0, 0, 1]], [1, [1, 1, 1, 1]]]).slice().sort((p, q) => p[0] - q[0]);
            let c = vec4(...els[0][1]);
            for (let i = 1; i < els.length; i++) {
                const [p0, c0] = els[i - 1], [p1, c1] = els[i];
                let t = clamp(x.sub(p0).div(Math.max(1e-6, p1 - p0)), 0.0, 1.0);
                if (r.interpolation === 'CONSTANT') t = select(x.greaterThanEqual(p1), float(1.0), float(0.0));
                else if (r.interpolation === 'EASE') t = t.mul(t).mul(float(3.0).sub(t.mul(2.0)));
                c = select(x.greaterThanEqual(p0), mix(vec4(...c0), vec4(...c1), t), c);
            }
            if (sock === 'Alpha') return F(c.w);
            return Cc(c.xyz, c.w);
        }

        async function curves(name, P, type) {
            const cs = P.curves || [];
            const lut = (vals, x) => {
                const n = vals.length - 1;
                const t = clamp(x, 0.0, 1.0).mul(n);
                let out = float(vals[0]);
                for (let i = 0; i < n; i++) out = select(t.greaterThanEqual(i), mix(float(vals[i]), float(vals[i + 1]), clamp(t.sub(i), 0.0, 1.0)), out);
                return out;
            };
            if (type === 'ShaderNodeFloatCurve') return F(lut(cs[0] || [0, 1], await inF(name, 'Value')));
            const c = type === 'ShaderNodeRGBCurve' ? await inC(name, 'Color') : await inV(name, 'Vector');
            const fac = await inF(name, 'Fac');
            const comb = cs[3] || null;
            const ch = (i, x) => { let v = cs[i] ? lut(cs[i], x) : x; if (comb && type === 'ShaderNodeRGBCurve') v = lut(comb, v); return v; };
            if (cs.length > 32) warn('curve sampled coarsely');
            const out = vec3(ch(0, c.x), ch(1, c.y), ch(2, c.z));
            return type === 'ShaderNodeRGBCurve' ? Cc(mix(c, out, fac), float(1)) : V(mix(c, out, fac));
        }

        async function mapping(name, P) {
            const v = await inV(name, 'Vector');
            const loc = await inV(name, 'Location'), scale = await inV(name, 'Scale');
            const rotLinked = has(name, 'Rotation');
            const rot = def(name, 'Rotation', [0, 0, 0]);
            if (rotLinked) warn('Mapping: a linked rotation is read as its number');
            const R = eulerMat(rot);
            const isIdent = rot.every((x) => Math.abs(x) < 1e-9);
            const type = P.vector_type || 'POINT';
            if (type === 'POINT') return (isIdent ? v.mul(scale) : mulRows(R, v.mul(scale))).add(loc);
            if (type === 'TEXTURE') {
                const d = v.sub(loc);
                return (isIdent ? d : mulRows(transpose(R), d)).div(scale);
            }
            if (type === 'VECTOR') return isIdent ? v.mul(scale) : mulRows(R, v.mul(scale));
            return normalize(isIdent ? v.div(scale) : mulRows(R, v.div(scale)));
        }

        async function vtransform(name, P) {
            const v = await inV(name, 'Vector');
            const vt = P.vector_type || 'VECTOR', from = P.convert_from || 'WORLD', to = P.convert_to || 'OBJECT';
            if (from === to) return v;
            const toWorld = (x) => {
                if (from === 'WORLD') return x;
                if (from === 'OBJECT') {
                    if (vt === 'POINT') return toBl(modelWorldMatrix.mul(vec4(fromBl(x), 1.0)).xyz);
                    if (vt === 'NORMAL') return toBl(normalize(transformDirection(fromBl(x), modelWorldMatrix)));
                    return toBl(transformDirection(fromBl(x), modelWorldMatrix));
                }
                warn('Vector Transform from CAMERA read as WORLD');
                return x;
            };
            const w = toWorld(v);
            if (to === 'WORLD') return w;
            if (to === 'OBJECT') {
                if (vt === 'POINT') return toBl(modelWorldMatrixInverse.mul(vec4(fromBl(w), 1.0)).xyz);
                if (vt === 'NORMAL') return objNormalFromWorld(w);
                return toBl(fromBl(w).mul(mat3(modelWorldMatrix)));
            }
            if (to === 'CAMERA') {
                if (vt === 'POINT') return cameraViewMatrix.mul(vec4(fromBl(w), 1.0)).xyz;
                return transformDirection(fromBl(w), cameraViewMatrix);
            }
            return w;
        }

        async function image(name, P, sock) {
            const t = await tex(P.image, P.interpolation);
            if (!t) return sock === 'Alpha' ? F(1.0) : Cc(vec3(1.0, 0.0, 1.0), float(1));
            const co = has(name, 'Vector') ? await inV(name, 'Vector') : uvLayer(null, opts.attrs);
            let s;
            if (P.projection === 'BOX') s = boxSample(t, co, P.projection_blend ?? 0.0);
            else {
                let u = co.xy;
                const ext = P.extension || 'REPEAT';
                if (ext === 'MIRROR') u = abs(fract(u.mul(0.5)).mul(2.0).sub(1.0)).oneMinus();
                s = texture(t, ext === 'EXTEND' || ext === 'CLIP' ? clamp(u, 0.0, 1.0) : u);
                if (ext === 'CLIP') {
                    const inside = select(u.x.greaterThanEqual(0.0).and(u.x.lessThanEqual(1.0)).and(u.y.greaterThanEqual(0.0)).and(u.y.lessThanEqual(1.0)), float(1.0), float(0.0));
                    s = s.mul(inside);
                }
            }
            if (sock === 'Alpha') return F(P.image?.alpha === 'NONE' ? float(1.0) : s.a);
            return Cc(s.rgb, s.a);
        }

        // Blender's box projection (an image laid from the three object axes, blended where they meet), in the
        // object-space normal's frame
        function boxSample(t, co, blendAmt) {
            const Ns = objNormalFromWorld(worldNrm());
            const Na = abs(Ns);
            const n = Na.div(Na.x.add(Na.y).add(Na.z));
            const limit = 0.5 + 0.5 * blendAmt;
            const cx = n.x.greaterThan(n.x.add(n.y).mul(limit)).and(n.x.greaterThan(n.x.add(n.z).mul(limit)));
            const cy = n.y.greaterThan(n.x.add(n.y).mul(limit)).and(n.y.greaterThan(n.y.add(n.z).mul(limit)));
            const cz = n.z.greaterThan(n.x.add(n.z).mul(limit)).and(n.z.greaterThan(n.y.add(n.z).mul(limit)));
            const lim1 = 1.0 - limit;
            const b = Math.max(blendAmt, 1e-6);
            const xy = clamp(n.x.div(n.x.add(n.y)).sub(0.5 * (1 - blendAmt)).div(b), 0.0, 1.0);
            const yz = clamp(n.y.div(n.y.add(n.z)).sub(0.5 * (1 - blendAmt)).div(b), 0.0, 1.0);
            const xz = clamp(n.x.div(n.x.add(n.z)).sub(0.5 * (1 - blendAmt)).div(b), 0.0, 1.0);
            const k = (2.0 * limit - 1.0) || 1e-6;
            const three = (c) => c.mul(2.0 - limit).add(limit - 1.0).div(k);
            // the seven zones, as Blender's node_tex_image_box
            const wx = select(cx, float(1.0), select(cy.or(cz), float(0.0),
                blendAmt > 0 ? select(n.z.lessThan(n.y.add(n.x).mul(lim1)), xy, select(n.x.lessThan(n.y.add(n.z).mul(lim1)), float(0.0), select(n.y.lessThan(n.x.add(n.z).mul(lim1)), xz, three(n.x)))) : float(1.0)));
            const wy = select(cy, float(1.0), select(cx.or(cz), float(0.0),
                blendAmt > 0 ? select(n.z.lessThan(n.y.add(n.x).mul(lim1)), float(1.0).sub(xy), select(n.x.lessThan(n.y.add(n.z).mul(lim1)), yz, select(n.y.lessThan(n.x.add(n.z).mul(lim1)), float(0.0), three(n.y)))) : float(0.0)));
            const wz = select(cz, float(1.0), select(cx.or(cy), float(0.0),
                blendAmt > 0 ? select(n.z.lessThan(n.y.add(n.x).mul(lim1)), float(0.0), select(n.x.lessThan(n.y.add(n.z).mul(lim1)), float(1.0).sub(yz), select(n.y.lessThan(n.x.add(n.z).mul(lim1)), float(1.0).sub(xz), three(n.z)))) : float(0.0)));
            const ux = vec2(select(Ns.x.lessThan(0.0), float(1.0).sub(co.y), co.y), co.z);
            const uy = vec2(select(Ns.y.greaterThan(0.0), float(1.0).sub(co.x), co.x), co.z);
            const uz = vec2(select(Ns.z.greaterThan(0.0), float(1.0).sub(co.y), co.y), co.x);
            return texture(t, ux).mul(wx).add(texture(t, uy).mul(wy)).add(texture(t, uz).mul(wz));
        }

        // a world-space normal (Blender's frame) from the surface's own, where the graph has bent nothing yet
        async function normalIn(name, id) {
            return has(name, id) ? normalize(await inV(name, id)) : worldNrm();
        }

        async function normalMapNode(name, P) {
            const strength = await inF(name, 'Strength');
            const c = (await inC(name, 'Color')).mul(2.0).sub(1.0);
            const Nw = worldNrm();
            if ((P.space || 'TANGENT') !== 'TANGENT') {
                if (P.space === 'OBJECT') return normalize(mix(Nw, toBl(normalize(transformDirection(fromBl(c), modelWorldMatrix))), max(strength, 0.0)));
                return normalize(mix(Nw, c, max(strength, 0.0)));
            }
            let Tw, Bw;
            const tname = '_tangent_' + attrName(P.uv_map || 'uvmap');
            if (opts.attrs && opts.attrs.has(tname)) {
                const ta = attribute(tname, 'vec4');
                const tw = normalize(transformDirection(ta.xyz, modelWorldMatrix));
                const sgn = select(frontFacing, float(1.0), float(-1.0));
                Tw = toBl(tw).mul(sgn);
                Bw = cross(Nw, Tw).mul(ta.w);
            } else {
                // (no tangent written for this UV: the frame from the UV's own screen derivatives)
                const u = uvLayer(P.uv_map || null, opts.attrs);
                const dp1 = toBl(dFdx(positionWorld)), dp2 = toBl(dFdy(positionWorld));
                const duv1 = dFdx(u.xy), duv2 = dFdy(u.xy);
                const dp2perp = cross(dp2, Nw), dp1perp = cross(Nw, dp1);
                const t = dp2perp.mul(duv1.x).add(dp1perp.mul(duv2.x));
                const b = dp2perp.mul(duv1.y).add(dp1perp.mul(duv2.y));
                const inv = float(1.0).div(sqrt(max(dot(t, t), dot(b, b))).max(1e-20));
                Tw = t.mul(inv); Bw = b.mul(inv);
            }
            const n = normalize(Tw.mul(c.x).add(Bw.mul(c.y)).add(Nw.mul(c.z)));
            return normalize(mix(Nw, n, max(strength, 0.0)));
        }

        async function bumpNode(name, P) {
            const strength = max(await inF(name, 'Strength'), 0.0);
            let dist = await inF(name, 'Distance');
            const h = await inF(name, 'Height');
            const Nin = await normalIn(name, 'Normal');
            const Nt = fromBl(Nin);
            if (P.invert) dist = dist.negate();
            dist = select(frontFacing, dist, dist.negate());
            const dPdx = dFdx(positionWorld), dPdy = dFdy(positionWorld);
            const Rx = cross(dPdy, Nt), Ry = cross(Nt, dPdx);
            const det = dot(dPdx, Rx);
            const surf = Rx.mul(dFdx(h)).add(Ry.mul(dFdy(h)));
            const r = normalize(abs(det).mul(Nt).sub(dist.mul(sign(det)).mul(surf)));
            return toBl(normalize(mix(Nt, r, strength)));
        }

        async function principled(name) {
            const g = async (id) => await inF(name, id);
            const col = await inC(name, 'Base Color');
            const nrm = has(name, 'Normal') ? normalize(await inV(name, 'Normal')) : null;
            const cl = {
                color: col, metal: await g('Metallic'), rough: await g('Roughness'), ior: await g('IOR'),
                opacity: await g('Alpha'), normal: nrm,
                emission: (await inC(name, 'Emission Color')).mul(await g('Emission Strength')),
                coat: await g('Coat Weight'), coatRough: await g('Coat Roughness'),
                transmission: await g('Transmission Weight'),
                sheen: await g('Sheen Weight'), sheenTint: await inC(name, 'Sheen Tint'), sheenRough: await g('Sheen Roughness'),
                specular: await g('Specular IOR Level'), specularTint: await inC(name, 'Specular Tint'),
                subsurface: await g('Subsurface Weight'),
                consts: {
                    coat: !has(name, 'Coat Weight') ? def(name, 'Coat Weight', 0) : 1,
                    transmission: !has(name, 'Transmission Weight') ? def(name, 'Transmission Weight', 0) : 1,
                    sheen: !has(name, 'Sheen Weight') ? def(name, 'Sheen Weight', 0) : 1,
                    alpha: !has(name, 'Alpha') ? def(name, 'Alpha', 1) : 0.5,
                    emission: has(name, 'Emission Strength') || has(name, 'Emission Color') ? 1 : (def(name, 'Emission Strength', 0) * Math.max(...(def(name, 'Emission Color', [0, 0, 0, 1]).slice(0, 3)))),
                    specular: has(name, 'Specular IOR Level') ? 0.5 : def(name, 'Specular IOR Level', 0.5),
                    subsurface: !has(name, 'Subsurface Weight') ? def(name, 'Subsurface Weight', 0) : 1,
                },
            };
            return closure(cl);
        }

        const out = graph.output && nodes[graph.output];
        let surf = null;
        if (out) {
            const r = await input(graph.output, 'Surface', 'shader');
            surf = r.t === 'shader' ? r.v : closure({ emission: asColor(r) });
        }
        return { surface: surf || closure({}) };
    }

    // ------------------------------------------------------------------------------------------ closures
    // kind: 'bsdf' (reflects), 'emission' (light only), 'transparent' (lets through); consts: what is known at build
    // time (1 or more: the feature is used)
    function closure(c) {
        const kind = c.kind || (c.transparent ? 'transparent' : (c.emissionOnly ? 'emission' : 'bsdf'));
        return Object.assign({ color: KV([0.8, 0.8, 0.8]), metal: K(0.0), rough: K(0.5), ior: K(1.5), opacity: K(1.0),
            normal: null, emission: KV([0, 0, 0]), coat: K(0.0), coatRough: K(0.03), transmission: K(0.0),
            sheen: K(0.0), sheenTint: KV([1, 1, 1]), sheenRough: K(0.5), specular: K(0.5), specularTint: KV([1, 1, 1]),
            subsurface: K(0.0), seeThrough: false }, c,
            { kind, consts: Object.assign({ coat: 0, transmission: 0, sheen: 0, alpha: kind === 'transparent' ? 0 : 1,
                emission: kind === 'emission' ? 1 : 0, specular: 0.5, subsurface: 0 }, c.consts || {}) });
    }
    const KEYS = ['metal', 'rough', 'ior', 'coat', 'coatRough', 'transmission', 'sheen', 'sheenTint', 'sheenRough', 'specular', 'specularTint', 'subsurface'];
    // a mix of two numbers known now is a number (WebGPU's compiler refuses some builtins on constants alone)
    const cval = (n) => (n && CONST.has(n) ? CONST.get(n) : null);
    const same = (x, y) => (typeof x === 'number' && typeof y === 'number') ? x === y
        : (Array.isArray(x) && Array.isArray(y) && x.length === y.length && x.every((v, i) => v === y[i]));
    function fmix(a, b, f) {
        const va = cval(a), vb = cval(b), vf = cval(f);
        if (va !== null && vb !== null) {
            if (same(va, vb)) return a;
            if (typeof va === 'number' && typeof vb === 'number' && typeof vf === 'number') return float(va + (vb - va) * vf);
        }
        return mix(a, b, f);
    }
    // Mix Shader: (1 - f) a + f b, as parameters
    function mixClosures(a, b, f) {
        const fa = float(1.0).sub(f);
        const C = (k) => Math.max(a.consts[k] ?? 0, b.consts[k] ?? 0);
        const consts = { coat: C('coat'), transmission: C('transmission'), sheen: C('sheen'), emission: C('emission'),
            specular: (a.consts.specular === 0.5 && b.consts.specular === 0.5) ? 0.5 : 1, subsurface: C('subsurface'), alpha: 1 };
        if (a.kind === 'transparent' || b.kind === 'transparent') {
            const [s, wt] = a.kind === 'transparent' ? [b, f] : [a, fa];      // (the other closure, weighing wt)
            if (s.kind === 'transparent') return closure({ kind: 'transparent', opacity: float(0.0) });
            const out = closure(Object.assign({}, s, { kind: s.kind, opacity: s.opacity.mul(wt), seeThrough: true }));
            out.consts = Object.assign({}, s.consts, { alpha: 0.5 });
            return out;
        }
        if (a.kind === 'emission' && b.kind === 'emission') return closure({ kind: 'emission', emission: fmix(a.emission, b.emission, f), consts });
        const out = closure({ kind: 'bsdf' });
        const src = a.kind === 'emission' ? b : (b.kind === 'emission' ? a : null);
        if (src) {                                                  // a reflection with light of its own
            Object.assign(out, Object.fromEntries(KEYS.map((k) => [k, src[k]])));
            out.color = src.color.mul(src === a ? fa : f);
            out.normal = src.normal;
        } else {
            for (const k of KEYS) out[k] = fmix(a[k], b[k], f);
            out.color = fmix(a.color, b.color, f);
            out.normal = a.normal && b.normal ? normalize(mix(a.normal, b.normal, f)) : (a.normal || b.normal);
        }
        out.emission = a.emission.mul(fa).add(b.emission.mul(f));
        out.opacity = fmix(a.opacity, b.opacity, f);
        out.seeThrough = a.seeThrough || b.seeThrough;
        out.consts = consts;
        out.consts.alpha = Math.min(a.consts.alpha, b.consts.alpha);
        return out;
    }
    function addClosures(a, b) {
        const out = mixClosures(a, b, float(0.5));
        out.emission = a.emission.add(b.emission);
        if (out.kind === 'bsdf') out.color = (a.kind === 'bsdf' ? a.color : vec3(0)).add(b.kind === 'bsdf' ? b.color : vec3(0));
        out.opacity = max(a.opacity, b.opacity);
        return out;
    }

    // a closure as a MeshPhysicalNodeMaterial (MeshStandardNodeMaterial when it needs nothing more; an emission
    // alone is unlit)
    function toMaterial(cl, settings, label) {
        const k = cl.consts || {};
        const s = settings || {};
        if (cl.kind === 'emission') {
            const m = new T.MeshBasicNodeMaterial();
            m.name = label;
            m.colorNode = vec4(cl.emission, 1.0);
            m.side = s.backface_culling ? T.FrontSide : T.DoubleSide;
            m.fog = false;
            return m;
        }
        const physical = k.coat > 0 || k.transmission > 0 || k.sheen > 0 || k.specular !== 0.5;
        const m = physical ? new T.MeshPhysicalNodeMaterial() : new T.MeshStandardNodeMaterial();
        m.name = label;
        m.colorNode = vec4(cl.color, 1.0);
        m.metalnessNode = clamp(cl.metal, 0.0, 1.0);
        m.roughnessNode = clamp(cl.rough, 0.0, 1.0);
        if (cl.normal) m.normalNode = transformDirection(fromBl(cl.normal), cameraViewMatrix).normalize();
        if (k.emission > 0) m.emissiveNode = cl.emission;
        if (physical) {
            if (k.coat > 0) { m.clearcoatNode = clamp(cl.coat, 0.0, 1.0); m.clearcoatRoughnessNode = clamp(cl.coatRough, 0.0, 1.0); }
            if (k.transmission > 0) { m.transmissionNode = clamp(cl.transmission, 0.0, 1.0); m.iorNode = cl.ior; m.thicknessNode = float(0.0); }
            if (k.sheen > 0) { m.sheenNode = cl.sheenTint.mul(cl.sheen); m.sheenRoughnessNode = clamp(cl.sheenRough, 0.0, 1.0); }
            m.specularIntensityNode = cl.specular.mul(2.0);
            m.specularColorNode = cl.specularTint;
        }
        if (k.alpha < 1 || s.surface_render_method === 'BLENDED') {
            m.opacityNode = clamp(cl.opacity, 0.0, 1.0);
            if (cl.seeThrough || s.surface_render_method === 'BLENDED') {     // glass and films blend over what is behind
                m.transparent = true;
                m.depthWrite = false;
            } else {                                                        // a picture's alpha cuts it out
                m.alphaTest = 0.5;
            }
        }
        if (k.transmission > 0) m.transparent = true;
        m.side = s.backface_culling ? T.FrontSide : T.DoubleSide;
        return m;
    }

    // graph: a material's export; attrs: the vertex attributes its meshes carry (a Set of names); lighting: () -> a
    // LightingNode for the material's environment (the room's bounce and reflections)
    async function material(graph, { name = 'blender', lighting = null, attrs = null } = {}) {
        const { surface } = await evaluate(graph, { attrs });
        const m = toMaterial(surface, graph.settings, name);
        if (lighting && m.isMeshStandardNodeMaterial) m.setupEnvironment = function () { return lighting(); };
        return m;
    }

    // a world graph: { color } the colour seen along the view direction (scene.backgroundNode), with the Light Path's
    // camera ray as ctx.isCameraRay holds it
    async function world(graph) {
        const { surface } = await evaluate(graph, { world: true, dirBl: () => toBl(normalize(T.positionWorldDirection)) });
        return { color: surface.emission, surface };
    }

    return { material, world, evaluate, toBl, fromBl };
}
