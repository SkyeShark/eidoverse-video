// weather_system.js — weather layer composing with the eidoverse sky system
// (task #40, v2 after Skye's lookdev critique of v1).
//
// Replaces the old screenspace rain pass the way sky_system replaced the
// old screenspace clouds. v2 fixes the three v1 sins:
//   · SKY COUPLING: weather greys/darkens the live TOD palette every frame
//     (storms stay stormy through a day cycle) and dims cloud radiance via
//     the sky's cloudDim hook — no more blue-sky rain.
//   · WORLD-ANCHORED RAIN: streak positions are tiled in WORLD space around
//     the camera (mod-wrap), so the field stands still while the camera moves
//     through it; billboards use the camera-right uniform (no overhead flip).
//   · WATER-LOOK STREAKS: bright-core/soft-edge cross profile, sun-forward
//     glint (backlit rain lights up), per-state length/speed/tilt/dashing.
// Plus deterministic LIGHTNING (hash-scheduled double-pulse, no RNG).
//
//   eval sky_system.js first, then:
//   const weather = await makeWeatherSystem({ scene, sky });
//   weather.wrapScene();                  // wetness on existing materials
//   weather.setWeather('storm', 1.0);     // see WEATHER table below
//   // per frame: weather.update(t, camera)
//
// States: clear · drizzle · sunshower · overcast · rain · storm (great-plains
// towering deck + lightning) · hurricane (sheared sheets of rain) · darkstorm
// (near-black green-cast sky, heavy lightning).
// Colored/alien rain (task #41): uniforms.rainColor + wetTint.
(function () {
    const T3 = globalThis.THREE;
    const {
        uniform, Fn, vec2, vec3, vec4, float, instanceIndex, positionLocal,
        uv, fract, floor, mix, clamp, smoothstep, dot, normalize, max, min,
        pow, abs, exp, sin, cos, length, cameraPosition, normalWorld, positionWorld,
        materialColor, materialRoughness,
    } = T3;
    const atan2w = T3.atan2 || T3.atan;
    const V = (x, y, z) => new T3.Vector3(x, y, z);

    //           clouds     overrides                                              sunDim grey dark greyTint           rain  wet  windK len  fall dash lightning
    const WEATHER = {
        clear:     { clouds: 'clear',   over: {},                                                 sunDim: 1.00, grey: 0.00, dark: 1.00, greyTint: [1, 1, 1],        rain: 0.00, wet: 0.00, windK: 0.0, len: 0.30, fall: 1.0, dash: 0.0, lightning: 0.00 },
        drizzle:   { clouds: 'stratus', over: { largeT: 0.10, finalMul: 0.14 },                   sunDim: 0.70, grey: 0.35, dark: 0.88, greyTint: [1, 1, 1],        rain: 0.45, wet: 0.40, windK: 0.3, len: 0.09, fall: 0.5, dash: 0.8, lightning: 0.00, horMul: 0.92, cellLo: 0.35, cellHi: 0.65 },
        sunshower: { clouds: 'cumulus', over: { largeT: 0.50, weatherT: 0.34 },                   sunDim: 0.92, grey: 0.05, dark: 1.00, greyTint: [1, 1, 1],        rain: 0.45, wet: 0.55, windK: 0.5, len: 0.2, fall: 0.9, dash: 0.0, lightning: 0.00, cellLo: 0.85, cellHi: 1.25 },
        overcast:  { clouds: 'stratus', over: { largeT: 0.05, finalMul: 0.20 },                   sunDim: 0.45, grey: 0.60, dark: 0.75, greyTint: [1, 1, 1],        rain: 0.00, wet: 0.15, windK: 0.4, len: 0.3, fall: 1.0, dash: 0.0, lightning: 0.00, horMul: 0.85, cellLo: 0.5, cellHi: 0.9 },
        rain:      { clouds: 'stratus', over: { largeT: 0.02, finalMul: 0.26, height: 320 },      sunDim: 0.30, grey: 0.75, dark: 0.55, greyTint: [1, 1, 1],        rain: 0.70, wet: 0.85, windK: 1.0, len: 0.22, fall: 1.0, dash: 0.0, lightning: 0.00, horMul: 0.75, cellLo: 0.5, cellHi: 0.85 },
        storm:     { clouds: 'cumulus', over: { largeT: 0.12, largeA: 4.0, finalMul: 0.34, start: 550, height: 950 }, sunDim: 0.18, grey: 0.80, dark: 0.42, greyTint: [1, 1, 1], rain: 1.00, wet: 1.00, windK: 2.2, len: 0.3, fall: 1.2, dash: 0.0, lightning: 0.30, horMul: 0.6, cellLo: 1.0, cellHi: 1.45, distant: 0.5 },
        hurricane: { clouds: 'stratus', over: { largeT: 0.00, finalMul: 0.40, start: 380, height: 520 }, sunDim: 0.12, grey: 0.90, dark: 0.30, greyTint: [1, 1, 1], rain: 1.00, wet: 1.00, windK: 4.5, len: 0.45, fall: 1.4, dash: 0.0, lightning: 0.12, horMul: 0.55, cellLo: 0.35, cellHi: 0.7, dense: 1.4, distant: 0.3 },
        noreaster: { clouds: 'stratus', over: { largeT: 0.00, largeA: 2.2, finalMul: 0.50, start: 240, height: 400 }, sunDim: 0.10, grey: 0.95, dark: 0.26, greyTint: [0.92, 0.97, 1.06], rain: 1.00, wet: 1.00, windK: 6.5, len: 0.60, fall: 1.6, dash: 0.0, lightning: 0.05, horMul: 0.5, cellLo: 0.10, cellHi: 0.35, dense: 1.9, distant: 0.15 },
        darkstorm: { clouds: 'cumulus', over: { largeT: 0.08, largeA: 5.0, finalMul: 0.40, start: 500, height: 1100 }, sunDim: 0.07, grey: 0.92, dark: 0.18, greyTint: [0.80, 1.0, 0.86], rain: 0.90, wet: 1.00, windK: 1.6, len: 0.28, fall: 1.1, dash: 0.0, lightning: 0.85, horMul: 0.45, cellLo: 0.9, cellHi: 1.4, distant: 0.8 },
    };

    globalThis.makeWeatherSystem = async function makeWeatherSystem({ scene, sky, opts = {} } = {}) {
        const N_RAIN = opts.rainCount ?? 16000;
        const RAD = opts.rainRadius ?? 45;     // world tile half-extent (m)
        const HGT = opts.rainHeight ?? 24;     // vertical recycle height (m)
        const N_SPLASH = opts.splashCount ?? 1200;
        const GROUND_Y = opts.groundY ?? 0;
        const P = RAD * 2;

        const u = {
            time: uniform(0),
            camPos: uniform(V(0, 0, 0)),
            camRight: uniform(V(1, 0, 0)),
            rainK: uniform(0),
            fallSpeed: uniform(opts.fallSpeed ?? 11),
            fallMul: uniform(1),
            windVec: uniform(V(0, 0, 0)),        // horizontal wind (m/s), state-driven
            streakLen: uniform(0.4),
            streakW: uniform(0.014),
            dashK: uniform(0),
            rainColor: uniform(V(0.72, 0.78, 0.86)),   // alien rains recolor this
            wetness: uniform(0),
            wetTint: uniform(V(1, 1, 1)),
            puddleK: uniform(opts.puddles ?? 1),
            cellLo: uniform(0.9),
            cellHi: uniform(1.45),
            denseA: uniform(1),
        };

        // ---------------- world-space rain (instanced streaks) ----------------
        // deterministic: every streak's world position is a pure function of
        // (instanceIndex, time, wind) tiled around the camera — same frame in,
        // same pixels out, and the field does NOT translate with the camera.
        const hashI = (n, k) => {
            const q = fract(float(n).mul(0.1031).add(k * 0.61803));
            const q2 = q.mul(q.add(33.33));
            return fract(q2.mul(q2.add(q)));
        };
        // ALL weather quads stay OUT of the auto-enhance G-buffer: alpha-blended
        // billboards smear garbage normals/metalrough over their footprint and
        // GTAO/SSR stamp hard dark marks on them (the task-#18 smoke-square
        // lesson — rain rendered as brown chunks until this).
        const noGBuffer = (mat) => {
            if (T3.mrt && T3.vec4) mat.mrtNode = T3.mrt({ normal: T3.vec4(0), metalrough: T3.vec4(0) });
            return mat;
        };
        const rainGeo = new T3.PlaneGeometry(1, 1);
        rainGeo.translate(0, 0.5, 0);            // pivot at streak bottom
        const rainMat = noGBuffer(new T3.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, fog: false, side: T3.DoubleSide }));
        {
            const h1 = hashI(instanceIndex, 1), h2 = hashI(instanceIndex, 2), h3 = hashI(instanceIndex, 3);
            const fall = u.fallSpeed.mul(u.fallMul);
            // world-tiled coordinates: streak lives at hash*P + k*P (+ wind drift),
            // rendered in the tile containing the camera
            const wtX = u.windVec.x.mul(u.time);
            const wtZ = u.windVec.z.mul(u.time);
            const px = u.camPos.x.add(fract(h1.add(wtX.sub(u.camPos.x).div(P))).sub(0.5).mul(P));
            const pz = u.camPos.z.add(fract(h2.add(wtZ.sub(u.camPos.z).div(P))).sub(0.5).mul(P));
            const py = u.camPos.y.add(fract(h3.sub(u.time.mul(fall).div(HGT)).sub(u.camPos.y.div(HGT))).sub(0.35).mul(HGT));
            const base = vec3(px, py, pz);
            // streak axis = velocity direction (wind shear tilts it)
            const streakDir = normalize(vec3(u.windVec.x, fall.negate(), u.windVec.z));
            // distance shaping: fade the nearest ~2 m (no lens-sized blobs) and
            // thicken far streaks so they don't alias away — rain must read as
            // LAYERS in depth, not a handful of near strokes at the camera
            const dist = base.sub(cameraPosition).length();
            const nearFade = smoothstep(0.9, 2.6, dist);
            const lenI = u.streakLen.mul(h1.mul(0.5).add(0.75));
            // width follows length at the drop texture's 1:8 aspect
            const wThick = lenI.mul(0.125).mul(h2.mul(0.4).add(0.8)).mul(float(1).add(dist.mul(0.012)));
            const wp = base
                .add(u.camRight.mul(positionLocal.x.mul(wThick)))
                .add(streakDir.mul(positionLocal.y.mul(lenI)));
            rainMat.positionNode = wp;
            // WATER DROP texture (user-supplied): glassy teardrop with trailing
            // tail — alpha is the streak shape, RGB carries the glass highlights.
            // Drop head must sit at the FALLING end (uv.y=1 along streakDir).
            const dropTexN = opts.textures?.drop ? T3.texture(opts.textures.drop) : null;
            // drop texture arrives upside-down (Skye) — rotate UVs 180°
            const texC = dropTexN ? dropTexN.sample(vec2(float(1).sub(uv().x), float(1).sub(uv().y))) : null;
            const xProf = pow(max(float(1).sub(abs(uv().x.mul(2).sub(1))), 0), 1.6);
            const endFade = smoothstep(0.0, 0.18, uv().y).mul(smoothstep(1.0, 0.72, uv().y));
            const shapeA = texC ? texC.a : xProf.mul(endFade);
            const viewDir = normalize(base.sub(cameraPosition));
            const sunGlint = sky
                ? pow(max(dot(viewDir, sky.uniforms.sunDir), 0), 6).mul(1.6).add(0.6)
                : float(1);
            // WORLD gating: streaks only materialize where the weather map says
            // this cell is raining — walk out from under the cell and the rain
            // stops around you while the far curtains keep falling on the cells
            const cellGate = sky ? smoothstep(u.cellLo, u.cellHi, sky.tslCoverage(vec2(px, pz))) : float(1);
            const countGate = smoothstep(h1, h1.add(0.001), u.rainK);
            // texture ALPHA is the shape; RGB under transparent pixels is black
            // (premultiplied-style) and drags dark fringes in if multiplied —
            // color comes from the lit rainColor alone
            rainMat.colorNode = u.rainColor.mul(sunGlint).mul(1.15);
            rainMat.opacityNode = shapeA.mul(nearFade).mul(cellGate)
                .mul(float(0.24).add(h3.mul(0.10)).mul(u.denseA))
                .mul(countGate).mul(clamp(u.rainK.mul(2), 0, 1));
        }
        const rainInst = new T3.InstancedMesh(rainGeo, rainMat, N_RAIN);
        rainInst.frustumCulled = false;
        rainInst.userData.noSupportCheck = true;
        rainInst.userData.noWet = true;
        rainInst.visible = false;
        scene.add(rainInst);

        // ---------------- ground splashes (the world-anchor cue) ----------------
        // expanding rings at ground level, tiled in world space like the streaks;
        // each instance cycles ring-out on its own hash phase. Flat-ground v1
        // (opts.groundY) — terrain scenes can disable via splashCount: 0.
        const SP = RAD;   // splash tile half-extent (tighter than rain)
        const splashGeo = new T3.PlaneGeometry(1, 1);
        splashGeo.rotateX(-Math.PI / 2);
        const splashMat = noGBuffer(new T3.MeshBasicNodeMaterial({ transparent: true, depthWrite: false, fog: false }));
        {
            const s1 = hashI(instanceIndex, 11), s2 = hashI(instanceIndex, 12), s3 = hashI(instanceIndex, 13);
            const px = u.camPos.x.add(fract(s1.sub(u.camPos.x.div(SP * 2))).sub(0.5).mul(SP * 2));
            const pz = u.camPos.z.add(fract(s2.sub(u.camPos.z.div(SP * 2))).sub(0.5).mul(SP * 2));
            const phase = fract(s3.mul(9.7).add(u.time.mul(2.4)));
            const ringR = phase.mul(0.13).add(0.015);
            splashMat.positionNode = vec3(px, GROUND_Y + 0.015, pz)
                .add(positionLocal.mul(vec3(ringR.mul(2), 1, ringR.mul(2))));
            const rr = uv().sub(0.5).length().mul(2);
            const ring = smoothstep(0.55, 0.8, rr).mul(smoothstep(1.0, 0.85, rr));
            const cellGateS = sky ? smoothstep(u.cellLo, u.cellHi, sky.tslCoverage(vec2(px, pz))) : float(1);
            const countGate = smoothstep(s1, s1.add(0.001), u.rainK);
            splashMat.colorNode = u.rainColor.mul(1.15);
            splashMat.opacityNode = ring.mul(float(1).sub(phase)).mul(0.30).mul(cellGateS).mul(countGate).mul(clamp(u.rainK.mul(2), 0, 1));
        }
        const splashInst = new T3.InstancedMesh(splashGeo, splashMat, N_SPLASH);
        splashInst.frustumCulled = false;
        splashInst.userData.noSupportCheck = true;
        splashInst.userData.noWet = true;
        splashInst.visible = false;
        scene.add(splashInst);

        // ---------------- lightning (deterministic schedule + visible bolt) ----------------
        const bolt = new T3.PointLight(0xcfe0ff, 0, 1500, 1.2);
        bolt.userData.noSupportCheck = true;
        scene.add(bolt);
        const jsHash = (n) => {
            let x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
            return x - Math.floor(x);
        };
        // visible strike: jagged camera-facing ribbon, REBUILT per strike from
        // the strike-interval hash (unique shape each strike, deterministic).
        const boltK = uniform(0);
        const boltMat = noGBuffer(new T3.MeshBasicNodeMaterial({
            transparent: true, depthWrite: false, fog: false,
            blending: T3.AdditiveBlending, side: T3.DoubleSide,
        }));
        {
            const prof = max(float(1).sub(abs(uv().x.mul(2).sub(1))), 0);
            const core = pow(prof, 6).mul(1.3).add(pow(prof, 1.6).mul(0.42)); // white-hot core + wide glow in one ribbon
            const cloudFade = smoothstep(0.0, 0.14, uv().y); // top dissolves INTO the deck
            const boltTexN = opts.textures?.bolt ? T3.texture(opts.textures.bolt) : null;
            const texA = boltTexN ? boltTexN.sample(uv()).a : float(1);
            boltMat.colorNode = vec3(0.72, 0.80, 1.0).mul(boltK.mul(26));
            boltMat.opacityNode = core.mul(texA).mul(cloudFade).mul(clamp(boltK.mul(3), 0, 1));
        }
        const boltGeo = new T3.BufferGeometry();
        const boltMesh = new T3.Mesh(boltGeo, boltMat);
        boltMesh.frustumCulled = false; boltMesh.visible = false;
        boltMesh.userData.noSupportCheck = true; boltMesh.userData.noWet = true;
        scene.add(boltMesh);
        let boltInterval = -1;
        const rebuildBolt = (I, camera, gx, gz) => {
            const rng = (i) => jsHash(I * 131.7 + i * 17.3);
            // start slightly INSIDE the deck — bolts come from the clouds
            const topY = (sky ? sky.uniforms.cloudStart.value : 500) * 1.04;
            const pos = [], uvs = [], idx = [];
            const addRibbon = (pts, w0, w1) => {
                const b0 = pos.length / 3;
                const toCam = V(camera.position.x - gx, 0, camera.position.z - gz).normalize();
                for (let i = 0; i < pts.length; i++) {
                    const t = i / (pts.length - 1);
                    const dirSeg = (i < pts.length - 1)
                        ? V(...pts[i + 1]).sub(V(...pts[i])).normalize()
                        : V(...pts[i]).sub(V(...pts[i - 1])).normalize();
                    const right = dirSeg.clone().cross(toCam).normalize();
                    const w = (w0 + (w1 - w0) * t) / 2;
                    const p = pts[i];
                    pos.push(p[0] - right.x * w, p[1] - right.y * w, p[2] - right.z * w);
                    pos.push(p[0] + right.x * w, p[1] + right.y * w, p[2] + right.z * w);
                    uvs.push(0, t, 1, t);
                    if (i > 0) {
                        const a = b0 + (i - 1) * 2;
                        idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
                    }
                }
            };
            // main channel: fine tortuosity over a drifting trunk line
            const N = 22;
            const spine = [];
            let x = gx + (rng(2) - 0.5) * 70, z = gz + (rng(4) - 0.5) * 70;
            for (let i = 0; i < N; i++) {
                const t = i / (N - 1);
                const y = topY * (1 - t) + 2 * t;
                if (i > 0) {
                    const amp = 26 * (1 - t * 0.45);
                    x += (rng(10 + i) - 0.5) * amp + (gx - x) * 0.16;
                    z += (rng(30 + i) - 0.5) * amp + (gz - z) * 0.16;
                }
                if (i === N - 1) { x = gx; z = gz; }
                spine.push([x, y, z]);
            }
            addRibbon(spine, 4.2, 1.0);
            // recursive branching: forks off the trunk, sub-forks off forks
            const branchFrom = (parent, seed, w0, depth) => {
                const k = 3 + Math.floor(rng(seed) * (parent.length - 6));
                const bp = [];
                let bx = parent[k][0], bz = parent[k][2];
                const n = 7 - depth * 2;
                for (let i = 0; i < n; i++) {
                    const t = i / (n - 1);
                    bp.push([bx, parent[k][1] * (1 - t * (0.45 + rng(seed + 1) * 0.25)), bz]);
                    bx += (rng(seed + 10 + i) - 0.25) * 30; bz += (rng(seed + 40 + i) - 0.5) * 30;
                }
                addRibbon(bp, w0, w0 * 0.2);
                if (depth < 2 && rng(seed + 5) > 0.4) branchFrom(bp, seed * 3 + 7, w0 * 0.5, depth + 1);
            };
            const nBranch = 2 + Math.floor(rng(50) * 3);
            for (let b = 0; b < nBranch; b++) branchFrom(spine, 60 + b * 23, 1.8, 1);
            boltGeo.setAttribute('position', new T3.Float32BufferAttribute(pos, 3));
            boltGeo.setAttribute('uv', new T3.Float32BufferAttribute(uvs, 2));
            boltGeo.setIndex(idx);
            boltGeo.computeBoundingSphere();
            return { gx, gz };
        };

        // ---------------- wetness material response ----------------
        const hash2 = (p) => {
            const q = fract(p.mul(0.3183099).add(vec2(0.13, 0.27))).mul(17);
            return fract(q.x.mul(q.y).mul(q.x.add(q.y)));
        };
        const vnoise2 = (p) => {
            const i = floor(p), f = fract(p);
            const sm = f.mul(f).mul(f).mul(f.mul(f.mul(6).sub(15)).add(10)); // quintic: C2, no lattice creases
            const a = hash2(i), b = hash2(i.add(vec2(1, 0)));
            const c = hash2(i.add(vec2(0, 1))), d = hash2(i.add(vec2(1, 1)));
            return mix(mix(a, b, sm.x), mix(c, d, sm.x), sm.y);
        };
        const wrapped = new Set();
        const wrapMaterial = (mat) => {
            if (!mat || wrapped.has(mat) || !mat.isNodeMaterial) return false;
            wrapped.add(mat);
            const upMask = clamp(normalWorld.y, 0, 1).pow(2).mul(u.wetness);
            const flat = smoothstep(0.985, 0.998, normalWorld.y);
            const pn = vnoise2(positionWorld.xz.mul(0.55)).add(vnoise2(positionWorld.xz.mul(0.13)).mul(0.6));
            const puddle = smoothstep(1.05, 1.25, pn).mul(flat).mul(u.puddleK).mul(smoothstep(0.35, 0.9, u.wetness));
            const baseCol = mat.colorNode ?? materialColor;
            const baseRough = mat.roughnessNode ?? materialRoughness;
            // wetness reads through GLOSS/reflection, not blackness — mild
            // darkening only (heavy albedo crush made black splotches)
            const darkened = baseCol.mul(mix(float(1), float(0.68), upMask.mul(0.85)).mul(mix(float(1), float(0.62), puddle)));
            mat.colorNode = darkened.mul(mix(vec3(1, 1, 1), u.wetTint, upMask.mul(0.6)));
            mat.roughnessNode = mix(mix(baseRough, float(0.10), upMask.mul(0.8)), float(0.035), puddle);
            mat.needsUpdate = true;
            return true;
        };
        const wrapScene = () => {
            let n = 0;
            scene.traverse((o) => {
                if (!o.isMesh || o.userData.noWet) return;
                if (sky && sky.domes && sky.domes.includes(o)) return;
                const mats = Array.isArray(o.material) ? o.material : [o.material];
                for (const m of mats) if (wrapMaterial(m)) n++;
            });
            console.log(`[weather] wetness wrapped ${n} materials`);
            if (sky && sky.wrapCloudShadows) sky.wrapCloudShadows(scene, 0.5);
            return n;
        };

        const state = { name: 'clear', k: 1, def: WEATHER.clear };
        // ---- smooth weather transitions: lerp every uniform setWeather touches
        // plus a BLENDED live state.def, so per-frame readers (palette greying,
        // lightning probability, ring-cloud coverage) ease instead of popping
        const _transScalars = () => {
            const s = [u.rainK, u.wetness, u.denseA, u.streakLen, u.fallMul, u.dashK, u.cellLo, u.cellHi];
            if (sky) s.push(sky.uniforms.cloudDim, sky.uniforms.sunDiscI, sky.uniforms.precipK, sky.uniforms.precipLo, sky.uniforms.precipHi,
                sky.uniforms.largeT, sky.uniforms.largeA, sky.uniforms.weatherT, sky.uniforms.finalMul,
                sky.uniforms.wScale, sky.uniforms.dScale, sky.uniforms.cloudStart, sky.uniforms.cloudHeight, sky.uniforms.lightK);
            return s;
        };
        const _transVecs = () => {
            const v = [u.windVec];
            if (sky) { v.push(sky.uniforms.skyWind, sky.uniforms.stretch); }
            return v;
        };
        const _capture = () => ({
            s: _transScalars().map((x) => x.value),
            v: _transVecs().map((x) => x.value.clone()),
        });
        const _apply = (a, b, k) => {
            _transScalars().forEach((x, i) => { x.value = a.s[i] + (b.s[i] - a.s[i]) * k; });
            _transVecs().forEach((x, i) => { x.value.lerpVectors(a.v[i], b.v[i], k); });
        };
        const _lerpDef = (a, b, k) => {
            const out = { ...b };
            for (const key of Object.keys(out)) {
                const av = a[key], bv = b[key];
                if (typeof bv === 'number') out[key] = (typeof av === 'number' ? av : bv) + (bv - (typeof av === 'number' ? av : bv)) * k;
                else if (Array.isArray(bv) && Array.isArray(av)) out[key] = bv.map((c, i) => av[i] + (c - av[i]) * k);
                else out[key] = k < 0.5 ? (av ?? bv) : bv;
            }
            return out;
        };
        const sys = {
            uniforms: u, state, rain: rainInst, bolt, WEATHER,
            // smooth transition to another weather state over `dur` seconds.
            // Fully agent-tunable — pass 60-120 for a naturally rolling front;
            // the default is a films-scale slow build, NOT the demo-reel pace.
            transitionTo(name, k = 1, dur = 45) {
                const fromDef = { ...state.def }, fromK = state.k, fromName = state.name;
                const snap = _capture();
                sys.setWeather(name, k);            // writes targets + swaps state
                const target = _capture();
                _apply(snap, snap, 0);              // restore current values
                sys._trans = { fromDef, fromK, fromName, toDef: { ...state.def }, toK: k, toName: name, snap, target, t0: null, dur };
                sys._transS = 0;
                rainInst.visible = true;            // visibility resolves when the blend completes
                splashInst.visible = N_SPLASH > 0;
            },
            setWeather(name, k = 1) {
                const w = WEATHER[name] || WEATHER.clear;
                state.name = name; state.k = k; state.def = w;
                if (sky) {
                    sky.setClouds(w.clouds, w.over);
                    sky.uniforms.cloudDim.value = Math.max(0.1, 1 - (1 - w.sunDim) * k);
                    sky.uniforms.sunDiscI.value = 48 * Math.max(0.02, 1 - w.grey * k * 0.98);
                    sky.uniforms.precipK.value = w.rain * k * (w.dense ?? 1);   // world rain curtains under dense cells
                }
                u.rainK.value = w.rain * k;
                u.wetness.value = w.wet * k;
                u.windVec.value.set(1.0, 0, 0.22).normalize().multiplyScalar(w.windK * 3.2);
                u.denseA.value = w.dense ?? 1;
                if (sky && sky.uniforms.skyWind) {
                    // ONE wind: clouds aloft move with the surface wind (faster),
                    // so rain shear, cell drift, and cloud motion agree
                    sky.uniforms.skyWind.value.set(u.windVec.value.x * 1.6 + 2, 0, u.windVec.value.z * 1.6 + 6);
                }
                u.streakLen.value = w.len;
                u.fallMul.value = w.fall;
                u.dashK.value = w.dash;
                u.cellLo.value = w.cellLo ?? 0.9;
                u.cellHi.value = w.cellHi ?? 1.45;
                if (sky && sky.uniforms.precipLo) { sky.uniforms.precipLo.value = (w.cellLo ?? 0.9) + 0.05; sky.uniforms.precipHi.value = (w.cellHi ?? 1.45) + 0.1; }
                rainInst.visible = (w.rain * k) > 0.001;
                splashInst.visible = rainInst.visible && N_SPLASH > 0;
                return w;
            },
            sunDim() { return Math.max(0.1, 1 - (1 - state.def.sunDim) * state.k); },
            wrapMaterial, wrapScene,
            update(t, camera) {
                u.time.value = t;
                // drive an active weather transition
                if (sys._trans) {
                    const tr = sys._trans;
                    if (tr.t0 === null) tr.t0 = t;
                    let s = Math.min(1, (t - tr.t0) / tr.dur);
                    s = s * s * (3 - 2 * s);                        // ease
                    _apply(tr.snap, tr.target, s);
                    state.def = _lerpDef(tr.fromDef, tr.toDef, s);
                    state.k = tr.fromK + (tr.toK - tr.fromK) * s;
                    sys._transS = s;
                    if (s >= 1) {
                        state.def = tr.toDef; state.k = tr.toK;
                        rainInst.visible = (state.def.rain * state.k) > 0.001;
                        splashInst.visible = rainInst.visible && N_SPLASH > 0;
                        sys._trans = null;
                    }
                }
                if (camera) {
                    u.camPos.value.copy(camera.position);
                    const e = camera.matrixWorld.elements;
                    u.camRight.value.set(e[0], e[1], e[2]).normalize();
                }
                // grey/darken the LIVE sky palette (tracks TOD changes) + flash
                if (sky) {
                    const w = state.def, k = state.k, pal = sky.state.palette;
                    let flash = 0;
                    if (w.lightning > 0) {
                        const I = Math.floor(t * 1.9);
                        if (jsHash(I) < w.lightning * k) {
                            const p = t * 1.9 - I;
                            const env = Math.exp(-p * 13) + 0.55 * Math.exp(-(p - 0.14) * (p - 0.14) * 700);
                            flash = env * (0.45 + 0.55 * jsHash(I + 7));
                        }
                        if (flash > 0.03 && camera) {
                            if (boltInterval !== I) {
                                boltInterval = I;
                                // strike a DENSE WORLD CELL: probe the live weather
                                // map (camera-independent) — the storm strikes where
                                // the storm IS; a far strike is a small distant fork
                                const cx = opts.stormCenter?.[0] ?? 0, cz = opts.stormCenter?.[1] ?? 0;
                                const R = opts.stormRange ?? 700;
                                let sx = cx + (jsHash(I * 7 + 11) - 0.5) * 2 * R;
                                let sz = cz + (jsHash(I * 7 + 29) - 0.5) * 2 * R;
                                if (sky) {
                                    for (let q = 0; q < 12; q++) {
                                        const qx = cx + (jsHash(I * 13 + q * 3 + 1) - 0.5) * 2 * R;
                                        const qz = cz + (jsHash(I * 13 + q * 3 + 2) - 0.5) * 2 * R;
                                        if (sky.weatherAt(qx, qz) > 1.3) { sx = qx; sz = qz; break; }
                                    }
                                }
                                state.strike = { x: sx, z: sz };
                                rebuildBolt(I, camera, sx, sz);
                            }
                            boltMesh.visible = true;
                            if (state.strike) bolt.position.set(state.strike.x, 120, state.strike.z);
                        } else {
                            boltMesh.visible = false;
                        }
                    } else {
                        boltMesh.visible = false;
                    }
                    boltK.value = flash;
                    bolt.intensity = flash * 260;
                    // distant sheet lightning (harsher storms): faint horizon
                    // glow on its own schedule, no bolt, no local light
                    let flashD = 0;
                    if ((w.distant ?? 0) > 0) {
                        const I2 = Math.floor(t * 3.3) + 101;
                        if (jsHash(I2 * 1.71) < w.distant * k) {
                            const p2 = t * 3.3 - Math.floor(t * 3.3);
                            flashD = Math.exp(-p2 * 9) * 0.32 * (0.4 + 0.6 * jsHash(I2 + 13));
                        }
                    }
                    const g = w.grey * k, d = 1 - (1 - w.dark) * k, gt = w.greyTint;
                    // horMul: storms need the horizon DARKER than its luminance,
                    // not just desaturated — the bright haze band reads sunny
                    const horMul = 1 - (1 - (w.horMul ?? 1)) * k;
                    const mixG = (rgb, s) => {
                        const l = (rgb[0] * 0.35 + rgb[1] * 0.5 + rgb[2] * 0.15) * s;
                        return [
                            (rgb[0] + (l * gt[0] - rgb[0]) * g) * d * s + flash * 0.30,
                            (rgb[1] + (l * gt[1] - rgb[1]) * g) * d * s + flash * 0.34,
                            (rgb[2] + (l * gt[2] - rgb[2]) * g) * d * s + flash * 0.44,
                        ];
                    };
                    sky.uniforms.zenith.value.set(...mixG(pal.zen, 1.0));
                    const hz = mixG(pal.hor, horMul);
                    sky.uniforms.horizon.value.set(hz[0] + flashD * 0.55, hz[1] + flashD * 0.60, hz[2] + flashD * 0.78);
                }
            },
            dispose() { scene.remove(rainInst, splashInst, bolt, boltMesh); },
        };
        return sys;
    };
    console.log('[weather_system] makeWeatherSystem v2 — world-tiled deterministic rain, water-look streaks, live palette greying, hash-scheduled lightning, wetness/puddles');
})();
