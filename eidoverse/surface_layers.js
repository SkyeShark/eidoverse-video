// surface_layers.js — make AGENT-BUILT geometry look built.
//
// Fetched GLBs arrive with authored UVs and baked-in wear. Geometry you make
// yourself — a lathe revolve, an extruded moulding, a boolean cut — arrives
// clean, and clean is what makes procedural sets read as grey-box. Two things
// are missing, and this module supplies both:
//
//   1. TEXEL DENSITY. Different constructors produce UVs on different
//      scales. ExtrudeGeometry's WorldUVGenerator is already metric; Lathe,
//      Cylinder, Box and Sphere are all normalised 0..1 across the surface.
//      So the SAME stone texture comes out fine on an extruded step and
//      smeared across a 13 m revolved basin. `normalizeTexelDensity` fixes
//      that WITHOUT throwing the authored UVs away — it measures each mesh's
//      real UV-per-metre and scales the existing layout to a common target,
//      so bevel/boolean UV islands stay exactly as the constructor laid them
//      out and only their SCALE moves.
//
//      (This is what the `uvByWorld` line in AGENTS.md was reaching for. A
//      world-space UV REPROJECTION is the wrong tool: it discards the bevel
//      and cap islands that ExtrudeGeometry/CSG generate, and it seams badly
//      on anything that isn't axis-aligned. Normalising the density of the
//      UVs you already have keeps the good layout and fixes the real defect.)
//
//   2. WEAR THAT FOLLOWS THE FORM. A boolean cut has no dirt in its inside
//      corner and no polish on its outside edge, because nothing measured
//      the form. `makeLayeredMaterial` measures it in the shader, and
//      `makeLayeredMaterial` composites weathering layers driven by those
//      masks plus world-space bands, slope, and triplanar grunge.
//      Grime collects where the geometry is concave, wear brightens the
//      convex edges, silt lines sit at a world height, dust settles on
//      up-facing planes. All GPU-side; the masks cost one setup pass.
//
// API (all on globalThis, no import):
//   normalizeTexelDensity(objects, { metresPerTile, report })
//   makeLayeredMaterial({ base, layers, grunge })
//   layerSurface(objects, { layers, grunge, metresPerTile, ao })   ← the one-liner
//
// ⚠ normalizeTexelDensity is geometry AUTHORING — one attribute write at build
// time, same class as computeVertexNormals()/computeTangents(), on geometry
// that was itself just constructed on the CPU. The MASKS are pure GPU.

(function () {
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[surface_layers] THREE missing'); return; }
    const {
        vec2, vec3, float, mix, clamp, smoothstep, abs, pow, max, dot,
        texture: texNode, positionWorld, normalWorldGeometry, dFdx, dFdy,
    } = THREE;

    // ════════════════════════════════════════════════════════════════════
    // ⚠⚠ THESE TOOLS ARE FOR GEOMETRY YOU BUILT. THEY REFUSE FETCHED ASSETS.
    // ════════════════════════════════════════════════════════════════════
    // A fetched GLB / VRM / kit part carries an AUTHORED UV UNWRAP — islands
    // laid out in 0..1 and corresponding 1:1 to its own texture. Rescaling
    // those UVs does not retile anything: each island simply samples far
    // outside the region it was unwrapped onto (tiling the whole map inside
    // itself under RepeatWrapping, smearing edge pixels under ClampToEdge),
    // and the model comes out as confetti. Worse for a kit part sharing a
    // real ATLAS or trim sheet with its siblings — there the neighbouring
    // pieces' art is what bleeds in. Its material may also be MToon, or carry
    // emissive / alpha / vertex-colour slots that a generic Standard rebuild
    // drops on the floor (a VRM rebuilt as MeshStandardNodeMaterial loses the
    // character).
    //
    // So identification is POSITIVE and structural, not a documented warning:
    //   • render_scene stamps `userData._loadedAsset` on every mesh and
    //     geometry that comes out of GLTFLoader (VRMs included);
    //   • skinned meshes and morph-target meshes are skipped regardless —
    //     they DEFORM, so a world-space AO bake is only valid at bind pose;
    //   • MToon materials are skipped regardless.
    // Anything flagged is dropped from the working set and NAMED in the log,
    // so a caller who hands over a whole scene root gets their props
    // weathered-and-normalised... never, and is told exactly which meshes
    // were skipped and why. `force: true` overrides, and says so loudly.
    const fetchedReason = (m) => {
        if (m.isSkinnedMesh) return 'skinned (deforms — bind-pose bake would be wrong)';
        if (m.morphTargetInfluences && m.morphTargetInfluences.length) return 'has morph targets';
        if (m.userData?._loadedAsset || m.geometry?.userData?._loadedAsset) return 'loaded asset (GLB/VRM/kit)';
        const mats = Array.isArray(m.material) ? m.material : [m.material];
        for (const mm of mats) {
            if (!mm) continue;
            if (mm.isMToonMaterial || /mtoon/i.test(mm.type || '')) return 'MToon material (VRM)';
        }
        let p = m.parent;
        while (p) { if (p.userData?._loadedAsset) return 'child of a loaded asset'; p = p.parent; }
        return null;
    };

    const meshesOf = (objs, opts = {}) => {
        const { force = false, what = 'surface_layers' } = opts;
        const list = Array.isArray(objs) ? objs : [objs];
        const raw = [];
        for (const o of list) {
            if (!o) continue;
            if (o.isMesh) raw.push(o);
            else if (o.traverse) o.traverse((c) => { if (c.isMesh) raw.push(c); });
        }
        const out = [], skipped = [];
        for (const m of raw) {
            const why = fetchedReason(m);
            if (why && !force) skipped.push((m.name || '(unnamed)') + ' — ' + why);
            else out.push(m);
        }
        if (skipped.length) {
            console.warn('[' + what + '] skipped ' + skipped.length
                + ' FETCHED mesh(es) — these have authored UVs/materials and rewriting them'
                + ' corrupts the asset. Pass only geometry you built:\n  ' + skipped.join('\n  '));
        }
        if (force && raw.length !== out.length) {
            console.warn('[' + what + '] ⚠ force:true — operating on fetched assets. Their authored'
                + ' UVs and materials WILL be rewritten. This is almost never what you want.');
        }
        return out;
    };

    // ════════════════════════════════════════════════════════════════════
    // 1. TEXEL DENSITY
    // ════════════════════════════════════════════════════════════════════
    // Measure UV-units-per-metre per triangle, take the MEDIAN (robust to the
    // degenerate slivers every lathe has at its poles and every CSG result has
    // along its cut), then scale the uv attribute so 1 tile spans
    // `metresPerTile` metres of surface on every mesh in the scene.
    //
    // Uses matrixWorld, so a kitbashed `.scale.setScalar(1.7)` clone is
    // measured at the size it actually appears — not at geometry size.
    globalThis.normalizeTexelDensity = function (objects, opts = {}) {
        const { metresPerTile = 1.0, report = true, label = '', force = false } = opts;
        const target = 1 / metresPerTile;              // uv units per metre
        const meshes = meshesOf(objects, { force, what: 'normalizeTexelDensity' });
        const rows = [];
        const pA = new THREE.Vector3(), pB = new THREE.Vector3(), pC = new THREE.Vector3();
        const e1 = new THREE.Vector3(), e2 = new THREE.Vector3(), cr = new THREE.Vector3();

        for (const m of meshes) {
            const geo = m.geometry;
            if (!geo || !geo.attributes.position || !geo.attributes.uv) continue;
            m.updateWorldMatrix(true, false);
            const pos = geo.attributes.position, uvA = geo.attributes.uv;
            const idx = geo.index;
            const triCount = idx ? idx.count / 3 : pos.count / 3;
            const scales = [];
            for (let t = 0; t < triCount; t++) {
                const a = idx ? idx.getX(t * 3) : t * 3;
                const b = idx ? idx.getX(t * 3 + 1) : t * 3 + 1;
                const c = idx ? idx.getX(t * 3 + 2) : t * 3 + 2;
                pA.fromBufferAttribute(pos, a).applyMatrix4(m.matrixWorld);
                pB.fromBufferAttribute(pos, b).applyMatrix4(m.matrixWorld);
                pC.fromBufferAttribute(pos, c).applyMatrix4(m.matrixWorld);
                e1.subVectors(pB, pA); e2.subVectors(pC, pA);
                const wArea = cr.crossVectors(e1, e2).length() * 0.5;
                if (wArea < 1e-9) continue;
                const u0 = uvA.getX(a), v0 = uvA.getY(a);
                const u1 = uvA.getX(b), v1 = uvA.getY(b);
                const u2 = uvA.getX(c), v2 = uvA.getY(c);
                const uvArea = Math.abs((u1 - u0) * (v2 - v0) - (u2 - u0) * (v1 - v0)) * 0.5;
                if (uvArea < 1e-12) continue;
                scales.push(Math.sqrt(uvArea / wArea));    // uv units per metre
            }
            if (!scales.length) {
                rows.push({ name: m.name || '(unnamed)', before: null, after: null, note: 'no usable UVs' });
                continue;
            }
            scales.sort((x, y) => x - y);
            const median = scales[scales.length >> 1];
            const k = target / median;
            // A geometry shared by several meshes (cloneModel / kit.get) must
            // not be scaled twice. If it was already normalised to the same
            // density, skip; if to a DIFFERENT one (same geometry at another
            // world scale), clone it so each instance keeps its own UVs.
            const prev = geo.userData._texelUvPerMetre;
            if (prev != null) {
                if (Math.abs(prev - target) / target < 0.01) {
                    rows.push({ name: m.name || '(unnamed)', before: median, after: target, note: 'shared, already normalised' });
                    continue;
                }
                m.geometry = geo.clone();
            }
            const g2 = m.geometry, uv2 = g2.attributes.uv;
            for (let i = 0; i < uv2.count; i++) uv2.setXY(i, uv2.getX(i) * k, uv2.getY(i) * k);
            uv2.needsUpdate = true;
            g2.userData._texelUvPerMetre = target;
            rows.push({ name: m.name || '(unnamed)', before: median, after: target, k });

            // uv now CARRIES the metric scale, so a texture repeat != 1
            // multiplies on top of it and undoes the normalisation.
            const mats = Array.isArray(m.material) ? m.material : [m.material];
            for (const mat of mats) {
                if (!mat) continue;
                for (const slot of ['map', 'roughnessMap', 'normalMap', 'metalnessMap']) {
                    const t = mat[slot];
                    if (t && (Math.abs(t.repeat.x - 1) > 1e-3 || Math.abs(t.repeat.y - 1) > 1e-3)) {
                        console.warn('[normalizeTexelDensity] ⚠ ' + (m.name || 'mesh') + '.' + slot
                            + ' has repeat ' + t.repeat.x.toFixed(2) + ',' + t.repeat.y.toFixed(2)
                            + ' — that multiplies ON TOP of the normalised UVs. Set repeat to 1'
                            + ' and control tiling with metresPerTile.');
                    }
                    // ⚠ do NOT force RepeatWrapping here. On a mesh we built
                    // the caller wants tiling, but this same loop would flip a
                    // fetched atlas texture off ClampToEdge and bleed its
                    // neighbours. Say what is needed; change nothing shared.
                    if (t && t.wrapS === THREE.ClampToEdgeWrapping) {
                        console.warn('[normalizeTexelDensity] ' + (m.name || 'mesh') + '.' + slot
                            + ' is ClampToEdge — set wrapS/wrapT = RepeatWrapping on it if this'
                            + ' surface should tile.');
                    }
                }
            }
        }
        if (report && rows.length) {
            const ok = rows.filter(r => r.before != null);
            const lo = ok.length ? Math.min(...ok.map(r => r.before)) : 0;
            const hi = ok.length ? Math.max(...ok.map(r => r.before)) : 0;
            console.log('[normalizeTexelDensity]' + (label ? ' ' + label : '') + ' ' + ok.length
                + ' mesh(es) → ' + metresPerTile + ' m/tile. Incoming density spread was '
                + lo.toFixed(3) + '–' + hi.toFixed(3) + ' uv/m ('
                + (lo > 0 ? (hi / lo).toFixed(1) : '∞') + '× mismatch across the set).');
        }
        return rows;
    };


    // ── default grunge: a SEAMLESSLY TILING fbm DataTexture ──────────────
    // Built here rather than via ProceduralMaterials.noise() because that
    // returns a CanvasTexture, which this stack intercepts into a DataTexture
    // carrying repeat(1,-1)/offset(0,1) and ClampToEdge — neither of which
    // survives triplanar world-space sampling. Periodic value noise so the
    // lattice wraps and no seam shows where the tiles meet.
    let _grungeCache = new Map();
    function _grungeTexture(size, seed) {
        const ck = size + ':' + seed;
        if (_grungeCache.has(ck)) return _grungeCache.get(ck);
        const rand = (() => { let s = seed >>> 0; return () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296; })();
        const P = 16;                                  // lattice period
        const lat = new Float32Array(P * P);
        for (let i = 0; i < lat.length; i++) lat[i] = rand();
        const sm = (t) => t * t * (3 - 2 * t);
        const g = (x, y) => lat[((y % P) + P) % P * P + (((x % P) + P) % P)];
        const vn = (x, y) => {
            const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
            const a = g(xi, yi), b = g(xi + 1, yi), c = g(xi, yi + 1), d = g(xi + 1, yi + 1);
            const u = sm(xf), v = sm(yf);
            return (a + (b - a) * u) + ((c + (d - c) * u) - (a + (b - a) * u)) * v;
        };
        const data = new Uint8Array(size * size * 4);
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                // frequencies are integer multiples of the lattice period, so
                // every octave wraps at the texture edge
                let v = 0, amp = 0.5, f = 1;
                for (let o = 0; o < 5; o++) {
                    v += amp * vn(x / size * P * f, y / size * P * f);
                    amp *= 0.5; f *= 2;
                }
                v /= 0.96875;
                const c = Math.max(0, Math.min(255, Math.round(v * 255)));
                const i = (y * size + x) * 4;
                data[i] = data[i + 1] = data[i + 2] = c; data[i + 3] = 255;
            }
        }
        const tex = new THREE.DataTexture(data, size, size, THREE.RGBAFormat, THREE.UnsignedByteType);
        tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
        tex.minFilter = THREE.LinearMipmapLinearFilter;
        tex.magFilter = THREE.LinearFilter;
        tex.generateMipmaps = true;
        tex.needsUpdate = true;
        _grungeCache.set(ck, tex);
        return tex;
    }
    globalThis.grungeTexture = _grungeTexture;

    // ════════════════════════════════════════════════════════════════════
    // 3. LAYERED MATERIAL
    // ════════════════════════════════════════════════════════════════════
    // Composites weathering over a base PBR material using the baked masks
    // plus world-space terms. Every layer is `mix(under, layer, mask)`, so
    // order matters: later layers sit on top.
    //
    // mask kinds:
    //   'cavity'  aOcc — grime, moss, soot. The workhorse.
    //   'crease'  aCurv > 0 — sharper than cavity; dirt lines in inside corners.
    //   'edges'   aCurv < 0 — polish, chipping, bleached exposure on convex edges.
    //   'up'      geometric normal.y^power — dust, silt, snow, settled ash.
    //   'slope'   1 - |geometric normal.y| — runoff streaking on vertical faces.
    //   'below'   world Y below `y`, fading over `fade` — waterline, silt, tide.
    //   'above'   world Y above `y`.
    //   'grunge'  triplanar noise alone.
    //
    // per-layer: { mask, color, roughness, metalness, map, amount, range:[a,b],
    //              power, y, fade, grunge }
    //   amount  peak strength 0..1
    //   range   remap the raw mask through smoothstep(a, b) before use
    //   grunge  0..1 — how much triplanar noise breaks the mask up
    globalThis.makeLayeredMaterial = function (opts = {}) {
        const { base = {}, layers = [], grunge = {} } = opts;
        const mat = new THREE.MeshStandardNodeMaterial({
            map: base.map || null,
            roughnessMap: base.roughnessMap || null,
            normalMap: base.normalMap || null,
            metalnessMap: base.metalnessMap || null,
            color: base.color !== undefined ? base.color : 0xffffff,
            roughness: base.roughness !== undefined ? base.roughness : 0.9,
            metalness: base.metalness !== undefined ? base.metalness : 0.0,
            side: base.side !== undefined ? base.side : THREE.FrontSide,
        });
        if (!layers.length) return mat;

        const gTex = grunge.texture || _grungeTexture(grunge.size || 256, grunge.seed || 1);
        const gScale = grunge.scale !== undefined ? grunge.scale : 0.4;
        // triplanar so the noise holds world scale on every face of a bool'd
        // solid — a single UV sample would swim across the cut faces.
        const triplanar = (tex, scale) => {
            const p = positionWorld.mul(float(scale));
            const n = abs(normalWorldGeometry);
            const s = max(n.x.add(n.y).add(n.z), float(1e-4));
            const w = n.div(s);
            const xz = texNode(tex, vec2(p.x, p.z)).r;
            const zy = texNode(tex, vec2(p.z, p.y)).r;
            const xy = texNode(tex, vec2(p.x, p.y)).r;
            return xz.mul(w.y).add(zy.mul(w.x)).add(xy.mul(w.z));
        };
        const gNoise = gTex ? triplanar(gTex, gScale) : float(0.5);

        // ── PER-PIXEL CURVATURE, in 1/metres, view-independent ───────────
        // ⚠ NOTHING IS BAKED. An earlier draft raycast ambient occlusion and
        // solved discrete curvature on the CPU into vertex attributes — that
        // is precomputing on the CPU a term the GPU should evaluate, and it
        // cannot survive into a real-time world, which is what this pipeline
        // is a prototype for. Dividing each screen-space normal derivative by
        // the squared length of the matching POSITION derivative converts
        // "per pixel" into "per metre", so the mask does not swim as the
        // camera dollies. Sign: + convex, − concave.
        //
        // ⚠ THE TRADE-OFF, stated plainly: derivatives are taken WITHIN a
        // triangle, so this reads a smoothly-varying normal. A bevelled or
        // filleted edge (any ExtrudeGeometry with bevelEnabled, any Lathe)
        // gives a clean gradient across the bevel band — the common case and
        // the one that matters. A HARD boolean corner with split normals
        // gives a thin line instead of a soft gradient, because there is no
        // smooth normal there to differentiate. Model the fillet if you want
        // the dirt: `bevelEnabled: true` is the fix, and it is better
        // modeling anyway.
        // WARNING: normalWorldGeometry, never the SHADING normal. The shading
        // normal already carries the normal map, so differentiating it makes
        // every normal-map TEXEL read as a crease: `edges` lights up along
        // every mortar line and `cavity` darkens the tile faces, and the stone
        // renders as dark glowing circuitry instead of stone. Only looking at
        // the render catches this. normalWorldGeometry is the interpolated
        // VERTEX normal, pre-map -- real form, not surface detail.
        const dNx = dFdx(normalWorldGeometry), dPx = dFdx(positionWorld);
        const dNy = dFdy(normalWorldGeometry), dPy = dFdy(positionWorld);
        const curv = dot(dNx, dPx).div(max(dot(dPx, dPx), float(1e-12)))
            .add(dot(dNy, dPy).div(max(dot(dPy, dPy), float(1e-12))));

        // ⚠ TSL vec3() takes numbers/nodes, NOT a THREE.Color — feed components.
        const rgbNode = (hex) => { const c = new THREE.Color(hex); return vec3(c.r, c.g, c.b); };
        let colorN = mat.map ? texNode(mat.map).rgb.mul(rgbNode(base.color ?? 0xffffff))
            : rgbNode(base.color ?? 0xffffff);
        let roughN = mat.roughnessMap
            ? texNode(mat.roughnessMap).g.mul(float(base.roughness ?? 0.9))
            : float(base.roughness ?? 0.9);
        let metalN = float(base.metalness ?? 0.0);

        for (const L of layers) {
            const range = L.range || [0.2, 0.8];
            // `scale` is the feature size in METRES the mask is tuned to: 0.6 m
            // asks "is this a broad hollow", 0.05 m asks "is this a tight crease".
            const sc = float(L.scale ?? (L.mask === 'crease' ? 0.05 : 0.6));
            let m;
            switch (L.mask) {
                case 'cavity':
                case 'crease': m = smoothstep(float(range[0]), float(range[1]),
                    clamp(curv.negate().mul(sc), 0, 1)); break;
                case 'edges': m = smoothstep(float(range[0]), float(range[1]),
                    clamp(curv.mul(sc), 0, 1)); break;
                case 'up': m = smoothstep(float(range[0]), float(range[1]),
                    pow(clamp(normalWorldGeometry.y, 0, 1), float(L.power ?? 2))); break;
                case 'slope': m = smoothstep(float(range[0]), float(range[1]),
                    float(1).sub(abs(normalWorldGeometry.y))); break;
                case 'below': m = smoothstep(float(L.y ?? 0), float((L.y ?? 0) - (L.fade ?? 0.4)),
                    positionWorld.y); break;
                case 'above': m = smoothstep(float(L.y ?? 0), float((L.y ?? 0) + (L.fade ?? 0.4)),
                    positionWorld.y); break;
                case 'grunge': m = smoothstep(float(range[0]), float(range[1]), gNoise); break;
                default:
                    console.warn('[makeLayeredMaterial] unknown mask "' + L.mask
                        + '" — expected cavity|crease|edges|up|slope|below|above|grunge');
                    continue;
            }
            const gk = L.grunge ?? 0;
            if (gk > 0) m = m.mul(mix(float(1), gNoise.mul(float(1.6)), float(gk)));
            m = clamp(m.mul(float(L.amount ?? 1)), 0, 1);

            const lc = L.map
                ? texNode(L.map).rgb.mul(rgbNode(L.color ?? 0xffffff))
                : rgbNode(L.color ?? 0xffffff);
            colorN = mix(colorN, lc, m);
            if (L.roughness !== undefined) roughN = mix(roughN, float(L.roughness), m);
            if (L.metalness !== undefined) metalN = mix(metalN, float(L.metalness), m);
        }

        mat.colorNode = colorN;
        mat.roughnessNode = clamp(roughN, 0.02, 1.0);
        mat.metalnessNode = clamp(metalN, 0.0, 1.0);
        return mat;
    };

    // ── the one-liner: bake the masks, normalise density, weather the set ──
    // Reads each mesh's EXISTING material for its base maps, so you keep the
    // PBR set fetch_texture gave you and only add the response to form.
    globalThis.layerSurface = function (objects, opts = {}) {
        const meshes = meshesOf(objects, { force: opts.force, what: 'layerSurface' });
        if (!meshes.length) {
            console.warn('[layerSurface] nothing to do — every mesh handed in was a fetched'
                + ' asset. These tools are for geometry you BUILT (lathe / extrude / boolean).');
            return new Map();
        }
        if (opts.metresPerTile) {
            globalThis.normalizeTexelDensity(meshes, {
                metresPerTile: opts.metresPerTile, label: opts.label || '',
            });
        }
        const cache = new Map();
        for (const m of meshes) {
            const src = Array.isArray(m.material) ? m.material[0] : m.material;
            if (!src) continue;
            let out = cache.get(src);
            if (!out) {
                out = globalThis.makeLayeredMaterial({
                    base: {
                        map: src.map, roughnessMap: src.roughnessMap,
                        normalMap: src.normalMap, metalnessMap: src.metalnessMap,
                        color: src.color ? src.color.getHex() : 0xffffff,
                        roughness: src.roughness, metalness: src.metalness,
                        side: src.side,
                    },
                    layers: opts.layers || [],
                    grunge: opts.grunge || {},
                });
                cache.set(src, out);
            }
            m.material = out;
        }
        console.log('[layerSurface] ' + meshes.length + ' mesh(es) → ' + cache.size
            + ' layered material(s), ' + (opts.layers || []).length
            + ' layer(s) each — masks evaluated per-pixel, nothing baked.');
        return cache;
    };

    (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set());
    console.log('[surface_layers] normalizeTexelDensity / makeLayeredMaterial / layerSurface ready');
})();
