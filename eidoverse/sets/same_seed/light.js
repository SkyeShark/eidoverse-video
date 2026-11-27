// sets/same_seed/light.js — a SAME SEED room's light in three.js: its Blender lights as three.js lights, the bounce
// its volume probe carried as a grid of irradiance (L1 spherical harmonics in three 3D textures, baked by Cycles at
// each cell, sampled per pixel by position and normal), and its reflection probe's panorama as the reflections.
//
//   const L = makeLight(THREE);
//   const lights = L.lights(room.json.lights, { shadows: true });     // -> [Object3D], each light at its place
//   const env = L.environment(room.json, reflectionTexture);           // -> () => LightingNode for a material's setupEnvironment
//
// Units: a SUN's strength (W/m2) is a DirectionalLight's intensity; an AREA's power P (W) over its w x h is a
// RectAreaLight of P / (pi w h); a SPOT's or POINT's P is P / (4 pi) for SpotLight / PointLight (physical decay 2).

export function makeLight(THREE) {
    const T = THREE;
    const { vec3, texture3D, positionWorld, normalWorld, normalView, positionViewDirection, cameraViewMatrix,
        pmremTexture, roughness, clearcoatRoughness, clearcoatNormalView, pow, clamp, max } = T;

    // An area light's shadow, soft as the light's size makes it (percentage-closer soft shadows over its rectangle).
    // One cube map from the light's centre (three's point-light shadow, so the whole hemisphere it lights is covered),
    // its colour holding each texel's distance from the light. Per pixel: a search over the directions near the
    // pixel's for what stands between it and the light (the blockers found, the nearest to the light leading), then
    // the light's rectangle seen from the pixel through a blocker at that distance: a direction (x, y) on the light
    // (metres, its own axes) crosses it at an angle (x, y) * (1 / blocker - 1 / pixel) from the pixel's, and the
    // share of those directions with nothing nearer the light than the pixel is the light it gets. A blocker near the
    // light (the conduit along the ceiling) spreads its shadow wide and faint, one near the pixel (a bench foot) keeps
    // it sharp. Each direction is tested against the pixel's own plane where the direction meets it, so a sloped
    // surface does not shade itself.
    const AREA = { search: 16, taps: 32, nearest: 0.1, widest: 0.45, bias: 0.005, slope: 0.002, margin: 0.01, soft: 0.01 };
    const GOLDEN = 2.399963229728653;
    // tap i of n over the unit disk: at radius sqrt((i + .5) / n), even over the area; dense: (i + .5) / n, packed
    // toward the centre (the search finds a near silhouette first)
    const disk = (i, n, dense) => {
        const k = T.float(i).add(0.5).div(T.float(n));
        const a = T.float(i).mul(GOLDEN);
        return T.vec2(a.cos(), a.sin()).mul(dense ? k : k.sqrt());
    };
    // the distance map read at a direction from the light as three reads the depth cube beside it (WebGPU's faces:
    // y flipped), without the environment's rotation and flip a colour cube gets
    let DistanceCube = null;
    const distanceAt = (map, v, far) => {
        if (!DistanceCube) {
            DistanceCube = class extends T.CubeTextureNode {
                static get type() { return 'SameSeedDistanceCubeNode'; }
                setupUV(builder, uvNode) { return uvNode; }
            };
        }
        return new DistanceCube(map, T.vec3(v.x, v.y.negate(), v.z)).level(0).r.mul(far);
    };
    // (a TSL function, so every material that reads the shadow gets its own copy of the loops: three builds a light's
    // shadow node once and hands it to each material)
    function areaShadowFilter({ distanceMap, toFragment, shadow, light }) {
        const far = T.reference('far', 'float', shadow.camera).setGroup(T.renderGroup);
        const near = T.reference('near', 'float', shadow.camera).setGroup(T.renderGroup);
        const size = T.reference('mapSize', 'vec2', shadow).setGroup(T.renderGroup);
        const hw = T.reference('width', 'float', light).setGroup(T.renderGroup).mul(0.5);
        const hh = T.reference('height', 'float', light).setGroup(T.renderGroup).mul(0.5);
        const ax = T.uniform(new T.Vector3()).setGroup(T.renderGroup)
            .onRenderUpdate(() => new T.Vector3().setFromMatrixColumn(light.matrixWorld, 0).normalize());
        const ay = T.uniform(new T.Vector3()).setGroup(T.renderGroup)
            .onRenderUpdate(() => new T.Vector3().setFromMatrixColumn(light.matrixWorld, 1).normalize());
        // (the tap counts as uniforms: a shader compiler cannot unroll the loops, which with a hundred materials each
        // reading three of these shadows (the kitchen) took a minute to compile)
        const searchN = T.uniform(AREA.search, 'int').setGroup(T.renderGroup);
        const tapsN = T.uniform(AREA.taps, 'int').setGroup(T.renderGroup);
        return T.Fn(() => areaShadowBody({ distanceMap, toFragment, far, near, size, hw, hh, ax, ay, searchN, tapsN }))();
    }
    function areaShadowBody({ distanceMap, toFragment, far, near, size, hw, hh, ax, ay, searchN, tapsN }) {
        const r = T.length(toFragment).toVar();
        const dir = toFragment.div(r).toVar();
        const n = T.normalWorldGeometry;                   // (the surface's own, not its bump's)
        const nP = T.dot(n, toFragment).toVar();
        // the pixel's own plane along v: where v meets it (clamped to r / 2 .. 2 r), r where v runs off it; less a
        // margin (the search's is wider: a surface just behind the pixel's is no blocker to size the penumbra by)
        const reference = (v, margin = 0.0) => {
            const nv = T.dot(n, v);
            const t = nv.mul(nP).greaterThan(0.0).select(nP.div(nv).clamp(r.mul(0.5), r.mul(2.0)), r);
            return t.mul(1.0 - AREA.slope - margin).sub(AREA.bias);
        };
        const tap = (s, sx, sy) => dir.add(ax.mul(s.x.mul(sx))).add(ay.mul(s.y.mul(sy))).normalize();
        const visibility = T.float(1.0).toVar();
        T.If(r.lessThan(far).and(r.greaterThan(near)), () => {
            // the search: every direction a blocker nearer than `nearest` metres to the light could shade it from
            const ks = T.float(1.0 / AREA.nearest).sub(r.reciprocal()).max(0.0);
            const sx = hw.mul(ks).min(AREA.widest), sy = hh.mul(ks).min(AREA.widest);
            // (each blocker's spread k = 1 / distance - 1 / r weighed by how near the pixel's own direction it stands,
            // and the widest found leads: under a bench top its legs' feet take the top's soft penumbra, not their own
            // sharp one, and the size changes smoothly from pixel to pixel)
            const k2 = T.float(0.0).toVar(), k3 = T.float(0.0).toVar(), found = T.float(0.0).toVar();
            const blocker = (v, w) => {
                const d = distanceAt(distanceMap, v, far);
                T.If(d.lessThan(reference(v, AREA.margin)), () => {
                    const k = d.max(0.01).reciprocal().sub(r.reciprocal()).max(1e-4);
                    k2.addAssign(k.mul(k).mul(w));
                    k3.addAssign(k.mul(k).mul(k).mul(w));
                    found.addAssign(w);
                });
            };
            blocker(dir, 1.0);
            T.Loop(searchN, ({ i }) => {
                const s = disk(i, searchN, true);
                blocker(tap(s, sx, sy), T.float(1.0).sub(s.length().mul(0.9)));
            });
            T.If(found.greaterThan(0.0), () => {
                // the light through that blocker: its rectangle as angles at the pixel, at least a texel and a half
                const k = k3.div(k2);
                const least = T.float(3.0).div(size.x);
                const fx = hw.mul(k).clamp(least, AREA.widest), fy = hh.mul(k).clamp(least, AREA.widest);
                // (the disk turned per pixel, as three's own point shadows turn theirs: a fine grain, as EEVEE's soft
                // shadows have, where a fixed disk would step the penumbra in bands)
                const turn = T.interleavedGradientNoise(T.screenCoordinate.xy).mul(6.28318530718).toVar();
                const c = turn.cos().toVar(), sn = turn.sin().toVar();
                const lit = T.float(0.0).toVar();
                T.Loop(tapsN, ({ i }) => {
                    const d = disk(i, tapsN, false);
                    const v = tap(T.vec2(d.x.mul(c).sub(d.y.mul(sn)), d.x.mul(sn).add(d.y.mul(c))), fx, fy);
                    lit.addAssign(distanceAt(distanceMap, v, far).sub(reference(v)).div(AREA.soft).add(0.5).clamp(0.0, 1.0));
                });
                visibility.assign(lit.div(T.float(tapsN)));
            });
        });
        return visibility;
    }
    let AreaShadowNode = null;   // (made on first use: T is the caller's three)
    function areaShadowNode(light) {
        if (!AreaShadowNode) {
            AreaShadowNode = class extends T.PointShadowNode {
                static get type() { return 'SameSeedAreaShadowNode'; }
                setupRenderTarget(shadow, builder) {
                    const rt = super.setupRenderTarget(shadow, builder);
                    rt.shadowMap.texture.type = T.HalfFloatType;     // (its colour: the distance, over the far plane)
                    return rt;
                }
                renderShadow(frame) {
                    // three's shadow-pass material (one per light) writes the distance from the light as its colour
                    const m = frame.scene.overrideMaterial;
                    if (!this.distanceOut) {
                        const L = this.light, at = new T.Vector3();
                        const o = T.uniform(new T.Vector3()).onRenderUpdate(() => L.getWorldPosition(at));
                        const far = T.uniform(1.0).onRenderUpdate(() => this.shadow.camera.far);
                        this.distanceOut = T.vec4(T.vec3(T.positionWorld.distance(o).div(far)), 1.0);
                    }
                    if (m && m.outputNode !== this.distanceOut) { m.outputNode = this.distanceOut; m.needsUpdate = true; }
                    super.renderShadow(frame);
                }
                setupShadowFilter(builder, { shadowTexture, shadowCoord, shadow }) {
                    return areaShadowFilter({ distanceMap: shadowTexture, toFragment: shadowCoord.xyz, shadow, light: this.light });
                }
            };
        }
        return new AreaShadowNode(light);
    }
    let rectShadowsPatched = false;
    function patchRectShadows() {
        if (rectShadowsPatched) return;
        rectShadowsPatched = true;
        const base = T.RectAreaLightNode.prototype.setupShadowNode;
        T.RectAreaLightNode.prototype.setupShadowNode = function () {
            return this.light.shadow && this.light.shadow.isPointLightShadow ? areaShadowNode(this.light) : base.call(this);
        };
    }

    let ltcReady = false;
    async function ensureLTC() {
        if (ltcReady) return;
        const { RectAreaLightTexturesLib } = await import('npm:three@0.184.0/addons/lights/RectAreaLightTexturesLib.js');
        T.RectAreaLightNode.setLTC(RectAreaLightTexturesLib.init());
        ltcReady = true;
    }

    // the room's lights; a shadow-casting light's map covers the room (bounds: { min, max } in metres). reach: each
    // light ends where EEVEE ends it (its influence); false lets it fall off as far as its light goes, as Cycles does
    async function lights(rows, { shadows = true, bounds = null, shadowSize = 2048, maxAreaShadows = 3, reach = true } = {}) {
        const out = [];
        const span = bounds ? new T.Vector3().fromArray(bounds.max).sub(new T.Vector3().fromArray(bounds.min)).length() : 12.0;
        const influence = (r) => (reach ? r.influence || 0 : 0);
        // each shadow map is one more texture every material samples (WebGPU allows 16 a stage): a room with more
        // shadowed area lights than maxAreaShadows (the lab's eight panels) keeps their light and drops their shadows
        const areaShadows = (rows || []).filter((r) => r.type === 'rectArea' && r.shadow).length <= maxAreaShadows;
        for (const r of rows || []) {
            const col = new T.Color(r.color[0], r.color[1], r.color[2]);
            const pos = new T.Vector3().fromArray(r.position), dir = new T.Vector3().fromArray(r.direction).normalize();
            let L;
            if (r.type === 'directional') {
                L = new T.DirectionalLight(col, r.intensity);
                const c = bounds ? new T.Vector3().fromArray(bounds.min).add(new T.Vector3().fromArray(bounds.max)).multiplyScalar(0.5) : new T.Vector3();
                const R = bounds ? new T.Vector3().fromArray(bounds.max).sub(new T.Vector3().fromArray(bounds.min)).length() * 0.6 : 8;
                L.position.copy(c).addScaledVector(dir, -R * 2);
                L.target.position.copy(c);
                out.push(L.target);
                if (shadows && r.shadow) {
                    L.castShadow = true;
                    const s = L.shadow;
                    s.mapSize.set(shadowSize, shadowSize);
                    s.camera.left = -R; s.camera.right = R; s.camera.top = R; s.camera.bottom = -R;
                    s.camera.near = 0.1; s.camera.far = R * 4;
                    s.bias = -0.0004; s.normalBias = 0.02;
                    s.radius = Math.max(1, (r.angle || 0.01) * 300);
                }
            } else if (r.type === 'rectArea') {
                await ensureLTC();
                L = new T.RectAreaLight(col, r.intensity, r.width, r.height);
                L.position.copy(pos);
                const m = new T.Matrix4().fromArray(r.matrix);
                L.quaternion.setFromRotationMatrix(new T.Matrix4().extractRotation(m));
                if (influence(r)) {
                    // EEVEE's reach, as three's point lights end theirs: (1 - (d / r)^4)^2 from the light's centre
                    // (the colour and the centre follow the light: its intensity, colour and place stay live)
                    const light = L, tc = new T.Color(), tp = new T.Vector3();
                    const c = T.uniform(new T.Color()).onRenderUpdate(() => tc.copy(light.color).multiplyScalar(light.intensity));
                    const at = T.uniform(new T.Vector3()).onRenderUpdate(() => light.getWorldPosition(tp));
                    const d = T.positionWorld.sub(at).length();
                    const w = T.float(1.0).sub(d.div(influence(r)).pow(4.0)).clamp(0.0, 1.0);
                    L.colorNode = c.mul(w.mul(w));
                }
                if (shadows && r.shadow && areaShadows) {
                    // three's rect lights cast no shadow of their own: a cube map from the light's centre darkens its
                    // light where the room hides it, as soft as the light's size makes it (areaShadowFilter, above)
                    patchRectShadows();
                    const PointLightShadow = new T.PointLight().shadow.constructor;   // (not exported by name)
                    L.shadow = new PointLightShadow();
                    const size = Math.min(shadowSize, 512);
                    L.shadow.mapSize.set(size, size);
                    L.shadow.camera.near = 0.02;
                    L.shadow.camera.far = Math.max(4.0, influence(r) || span);
                    L.shadow.camera.updateProjectionMatrix();
                    L.shadow.normalBias = 0.01;
                    L.shadow.clearColor = new T.Color(1, 1, 1);       // (an empty texel of the distance map: the far plane)
                    L.shadow.clearAlpha = 1;
                    L.castShadow = true;
                }
            } else if (r.type === 'spot') {
                L = new T.SpotLight(col, r.intensity, influence(r), r.angle, r.penumbra, 2);
                L.position.copy(pos);
                L.target.position.copy(pos).add(dir);
                out.push(L.target);
                if (shadows && r.shadow) {
                    L.castShadow = true;
                    L.shadow.mapSize.set(shadowSize, shadowSize);
                    L.shadow.camera.near = 0.05;
                    L.shadow.camera.far = Math.max(4.0, span);           // (three's own far, 500 m, when it has no reach)
                    L.shadow.bias = -0.0002; L.shadow.normalBias = 0.01;
                    L.shadow.radius = Math.max(1, (r.radius || 0.02) * 60);
                }
            } else {
                L = new T.PointLight(col, r.intensity, influence(r), 2);
                L.position.copy(pos);
                if (shadows && r.shadow) {
                    L.castShadow = true;
                    L.shadow.mapSize.set(1024, 1024);
                    L.shadow.camera.near = 0.05;
                    L.shadow.camera.far = Math.max(4.0, span);
                }
            }
            L.name = r.name;
            L.userData.blender = r.blender;
            out.push(L);
        }
        return out;
    }

    // the grid's three textures: per cell (L00.rgb, L1-1.r), (L1-1.gb, L10.rg), (L10.b, L11.rgb), radiance SH (three's
    // basis order 0: Y00, 1: Y1-1 (y), 2: Y10 (z), 3: Y11 (x))
    function gridTextures(grid) {
        const [nx, ny, nz] = grid.res;
        const n = nx * ny * nz;
        const packs = [new Float32Array(n * 4), new Float32Array(n * 4), new Float32Array(n * 4)];
        for (let i = 0; i < n; i++) {
            const sh = grid.sh[i];
            const flat = [...sh[0], ...sh[1], ...sh[2], ...sh[3]];
            for (let k = 0; k < 12; k++) packs[k >> 2][i * 4 + (k & 3)] = flat[k];
        }
        return packs.map((a) => {
            const h = new Uint16Array(a.length);
            for (let i = 0; i < a.length; i++) h[i] = T.DataUtils.toHalfFloat(a[i]);
            const t = new T.Data3DTexture(h, nx, ny, nz);
            t.type = T.HalfFloatType;
            t.format = T.RGBAFormat;
            t.minFilter = t.magFilter = T.LinearFilter;
            t.wrapS = t.wrapT = t.wrapR = T.ClampToEdgeWrapping;
            t.unpackAlignment = 1;
            t.needsUpdate = true;
            return t;
        });
    }

    // the bounce at a point (L1: band 0 and 1 of the irradiance, as three's getShIrradianceAt weighs them)
    function gridIrradiance(grid, texs) {
        const lo = new T.Vector3().fromArray(grid.min), hi = new T.Vector3().fromArray(grid.max);
        const [nx, ny, nz] = grid.res;
        // cell centres sit half a cell in from the box: the texture's texel centres
        const uvw = positionWorld.sub(vec3(lo.x, lo.y, lo.z)).div(vec3(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z));
        const p = clamp(uvw, vec3(0.5 / nx, 0.5 / ny, 0.5 / nz), vec3(1 - 0.5 / nx, 1 - 0.5 / ny, 1 - 0.5 / nz));
        const a = texture3D(texs[0], p), b = texture3D(texs[1], p), c = texture3D(texs[2], p);
        const L00 = a.xyz, L1m1 = vec3(a.w, b.x, b.y), L10 = vec3(b.z, b.w, c.x), L11 = c.yzw;
        const n = normalWorld;
        return L00.mul(0.886227).add(L1m1.mul(2.0 * 0.511664).mul(n.y)).add(L10.mul(2.0 * 0.511664).mul(n.z)).add(L11.mul(2.0 * 0.511664).mul(n.x)).max(vec3(0.0));
    }

    // the irradiance of L2 radiance harmonics known now (three's basis), at the shading normal
    function shConstant(sh) {
        const v = (i) => vec3(sh[i][0], sh[i][1], sh[i][2]);
        const n = normalWorld, x = n.x, y = n.y, z = n.z;
        let e = v(0).mul(0.886227).add(v(1).mul(2.0 * 0.511664).mul(y)).add(v(2).mul(2.0 * 0.511664).mul(z)).add(v(3).mul(2.0 * 0.511664).mul(x));
        if (sh.length >= 9) {
            e = e.add(v(4).mul(2.0 * 0.429043).mul(x).mul(y)).add(v(5).mul(2.0 * 0.429043).mul(y).mul(z))
                .add(v(6).mul(z.mul(z).mul(0.743125).sub(0.247708))).add(v(7).mul(2.0 * 0.429043).mul(x).mul(z))
                .add(v(8).mul(0.429043).mul(x.mul(x).sub(y.mul(y))));
        }
        return e.max(vec3(0.0));
    }

    // the room's environment for its own materials: diffuse from the grid (everything but the lamps' own light,
    // the world's through the openings included), specular from the reflection panorama, scaled by how much light
    // the point has against the panorama's centre (the reflection probe's normalization: a corner or the underside of
    // a table reflects the room darker)
    function environment(room, reflection = null, { bounce = 1.0, reflect = 1.0 } = {}) {
        const grid = room.grid || null;
        const texs = grid ? gridTextures(grid) : null;
        const uBounce = T.uniform(bounce), uReflect = T.uniform(reflect);
        const env = reflection ? pmremTexture(reflection) : null;
        const lum = (c) => T.dot(c, vec3(0.2126, 0.7152, 0.0722));
        class RoomLightingNode extends T.LightingNode {
            static get type() { return 'SameSeedRoomLightingNode'; }
            setup(builder) {
                const gi = texs ? gridIrradiance(grid, texs).mul(uBounce) : null;
                if (gi) builder.context.iblIrradiance.addAssign(gi);
                if (env) {
                    const radianceDir = (rough, nView) => {
                        let r = positionViewDirection.negate().reflect(nView);
                        r = pow(rough, 4).mix(r, nView).normalize();
                        return r.transformDirection(cameraViewMatrix);
                    };
                    let k = uReflect;
                    if (gi && room.reflection && room.reflection.sh) {
                        const at = shConstant(room.reflection.sh);
                        k = k.mul(clamp(lum(gi).div(max(lum(at), 1e-4)), 0.0, 1.5));
                    }
                    const rad = pmremTexture(reflection, radianceDir(roughness, normalView), roughness).mul(k);
                    builder.context.radiance.addAssign(rad);
                    const cc = builder.context.lightingModel.clearcoatRadiance;
                    if (cc) cc.addAssign(pmremTexture(reflection, radianceDir(clearcoatRoughness, clearcoatNormalView), clearcoatRoughness).mul(k));
                }
            }
        }
        const make = () => new RoomLightingNode();
        make.uniforms = { bounce: uBounce, reflect: uReflect };
        make.gridTextures = texs;
        make.irradiance = () => (texs ? gridIrradiance(grid, texs) : vec3(0.0));     // (the grid's irradiance at a point)
        return make;
    }

    return { lights, environment, gridTextures, ensureLTC };
}
