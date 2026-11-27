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

    // an area light's shadow: a cube depth map from the light's centre (three's point-light shadow, so the whole
    // hemisphere it lights is covered), read through 16 compares over a Vogel disk of `radius` texels, turned per pixel
    const softPointShadow = T.Fn(({ depthTexture, bd3D, dp, shadow }) => {
        const radius = T.reference('radius', 'float', shadow).setGroup(T.renderGroup);
        const mapSize = T.reference('mapSize', 'vec2', shadow).setGroup(T.renderGroup);
        const ts = radius.div(mapSize.x);
        const ad = T.abs(bd3D);
        const tangent = T.normalize(T.cross(bd3D, ad.x.greaterThan(ad.z).select(T.vec3(0, 1, 0), T.vec3(1, 0, 0))));
        const bitangent = T.cross(bd3D, tangent);
        const N = 16;                                      // (one fixed disk: each tap is a bilinear compare, so the
        let sum = T.float(0.0);                            //  penumbra comes out smooth, with no per-pixel grain)
        for (let i = 0; i < N; i++) {
            const s = T.vogelDiskSample(i, N, T.float(0.7));
            sum = sum.add(T.cubeTexture(depthTexture, bd3D.add(tangent.mul(s.x).add(bitangent.mul(s.y)).mul(ts))).compare(dp));
        }
        return sum.div(N);
    });
    let rectShadowsPatched = false;
    function patchRectShadows() {
        if (rectShadowsPatched) return;
        rectShadowsPatched = true;
        const base = T.RectAreaLightNode.prototype.setupShadowNode;
        T.RectAreaLightNode.prototype.setupShadowNode = function () {
            return this.light.shadow && this.light.shadow.isPointLightShadow ? T.pointShadow(this.light) : base.call(this);
        };
    }

    let ltcReady = false;
    async function ensureLTC() {
        if (ltcReady) return;
        const { RectAreaLightTexturesLib } = await import('npm:three@0.184.0/addons/lights/RectAreaLightTexturesLib.js');
        T.RectAreaLightNode.setLTC(RectAreaLightTexturesLib.init());
        ltcReady = true;
    }

    // the room's lights; a shadow-casting light's map covers the room (bounds: { min, max } in metres)
    async function lights(rows, { shadows = true, bounds = null, shadowSize = 2048, maxAreaShadows = 3 } = {}) {
        const out = [];
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
                if (r.influence) {
                    // EEVEE's reach, as three's point lights end theirs: (1 - (d / r)^4)^2 from the light's centre
                    // (the colour and the centre follow the light: its intensity, colour and place stay live)
                    const light = L, tc = new T.Color(), tp = new T.Vector3();
                    const c = T.uniform(new T.Color()).onRenderUpdate(() => tc.copy(light.color).multiplyScalar(light.intensity));
                    const at = T.uniform(new T.Vector3()).onRenderUpdate(() => light.getWorldPosition(tp));
                    const d = T.positionWorld.sub(at).length();
                    const w = T.float(1.0).sub(d.div(r.influence).pow(4.0)).clamp(0.0, 1.0);
                    L.colorNode = c.mul(w.mul(w));
                }
                if (shadows && r.shadow && areaShadows) {
                    // three's rect lights cast no shadow of their own: a cube depth map from the light's centre
                    // darkens its light where the room hides it, softened about as much as the light's size would
                    patchRectShadows();
                    const PointLightShadow = new T.PointLight().shadow.constructor;   // (not exported by name)
                    L.shadow = new PointLightShadow();
                    const size = Math.min(shadowSize, 512);
                    L.shadow.mapSize.set(size, size);
                    L.shadow.camera.near = 0.02;
                    L.shadow.camera.far = Math.max(4.0, r.influence || 12.0);
                    L.shadow.camera.updateProjectionMatrix();
                    L.shadow.bias = -0.001;
                    L.shadow.normalBias = 0.02;
                    const texel = 1.5 * 2 / size;                       // (a cube texel a metre and a half away)
                    L.shadow.radius = Math.max(1.5, Math.min(24, 0.35 * Math.sqrt(r.width * r.height) / texel));
                    L.shadow.filterNode = softPointShadow;
                    L.castShadow = true;
                }
            } else if (r.type === 'spot') {
                L = new T.SpotLight(col, r.intensity, r.influence || 0, r.angle, r.penumbra, 2);
                L.position.copy(pos);
                L.target.position.copy(pos).add(dir);
                out.push(L.target);
                if (shadows && r.shadow) {
                    L.castShadow = true;
                    L.shadow.mapSize.set(shadowSize, shadowSize);
                    L.shadow.camera.near = 0.05;
                    L.shadow.bias = -0.0002; L.shadow.normalBias = 0.01;
                    L.shadow.radius = Math.max(1, (r.radius || 0.02) * 60);
                }
            } else {
                L = new T.PointLight(col, r.intensity, r.influence || 0, 2);
                L.position.copy(pos);
                if (shadows && r.shadow) {
                    L.castShadow = true;
                    L.shadow.mapSize.set(1024, 1024);
                    L.shadow.camera.near = 0.05;
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
