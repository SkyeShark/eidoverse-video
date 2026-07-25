// Current-frame spatial sky downsampling — the Eanpa "balanced" tier's
// signature optimization, ported for the offline renderer.
//
// The real sky domes are reparented into private offscreen scenes and
// rendered at reduced resolution for the CURRENT camera each frame; two
// screen-space proxy shells composite them back into the main pass at the
// domes' draw slots. Deliberately NO temporal history or reprojection —
// the former frame-graph accumulated the same screen UV under camera
// motion and produced pinned/skipping cloud copies.
//
// Host differences vs the browser original (src/cloudspatial.js):
//   - render size comes from options (the offline host has no innerWidth)
//   - proxy materials stamp zero MRT outputs like the real domes so the
//     G-buffer passes (GTAO/SSR) see sky pixels, not garbage
//
// Usage (scene setup, after makeSkySystem + weather + bakeEnv):
//   const { makeSpatialCloudPass } = await import(globalThis.EIDOVERSE_DIR + 'cloud_spatial.js');
//   const spatial = makeSpatialCloudPass(THREE, renderer, camera,
//       { div: 2, width: WIDTH, height: HEIGHT });
//   spatial.attach(scene, sky);
//   // per frame, BEFORE renderAsync: await spatial.render();
// Pair with makeSkySystem opts.cloudPasses = 3 for the full balanced tier.

export function makeSpatialCloudPass(THREE, renderer, camera, { div = 2, width: baseW = 1280, height: baseH = 720 } = {}) {
    const T3 = THREE;
    let divisor = Math.max(1, Math.round(div));
    const width = () => Math.max(1, Math.ceil(baseW / divisor));
    const height = () => Math.max(1, Math.ceil(baseH / divisor));
    const makeTarget = (name) => {
        const result = new T3.RenderTarget(width(), height(), {
            depthBuffer: false,
            type: T3.HalfFloatType,
            minFilter: T3.LinearFilter,
            magFilter: T3.LinearFilter,
        });
        result.texture.name = name;
        result.texture.colorSpace = T3.NoColorSpace;
        result.texture.generateMipmaps = false;
        return result;
    };
    const backgroundTarget = makeTarget('eanpa_current_spatial_background');
    const cloudTarget = makeTarget('eanpa_current_spatial_clouds');

    const backgroundScene = new T3.Scene();
    const cloudScene = new T3.Scene();
    const stampMrt = (mat) => {
        if (T3.mrt && T3.vec4 && !globalThis.EANPA_NO_MRT) mat.mrtNode = T3.mrt({ normal: T3.vec4(0), metalrough: T3.vec4(0) });
        return mat;
    };
    const backgroundMaterial = stampMrt(new T3.MeshBasicNodeMaterial({
        depthWrite: false,
        depthTest: true,
        side: T3.BackSide,
        fog: false,
    }));
    backgroundMaterial.toneMapped = true;
    const DIAG0 = (typeof Deno !== 'undefined' && Deno.env.get('EANPA_SPATIAL_DIAG')) || '';
    backgroundMaterial.colorNode = DIAG0 === 'red'
        ? T3.vec3(0, 0, 4)
        : T3.texture(backgroundTarget.texture).sample(DIAG0 === 'uv' ? T3.uv() : T3.screenUV).rgb;
    console.log('[cloud_spatial] screenUV type:', typeof T3.screenUV, DIAG0 ? `DIAG=${DIAG0}` : '(live)');

    const DIAG_EARLY = (typeof Deno !== 'undefined' && Deno.env.get('EANPA_SPATIAL_DIAG')) || '';
    const proxyMaterial = stampMrt(new T3.MeshBasicNodeMaterial(DIAG_EARLY === 'plain'
        ? { transparent: true, depthWrite: false, depthTest: true, side: T3.BackSide, fog: false }
        : {
            transparent: true,
            depthWrite: false,
            depthTest: true,
            side: T3.BackSide,
            fog: false,
            premultipliedAlpha: false,
            blending: T3.CustomBlending,
            blendEquation: T3.AddEquation,
            blendSrc: T3.OneFactor,
            blendDst: T3.OneMinusSrcAlphaFactor,
            blendEquationAlpha: T3.AddEquation,
            blendSrcAlpha: T3.OneFactor,
            blendDstAlpha: T3.OneMinusSrcAlphaFactor,
        }));
    // The source dome writes linear HDR into this target and the proxy is
    // tone-mapped once with the rest of the scene. Hardware linear sampling
    // already performs a four-texel reconstruction.
    proxyMaterial.toneMapped = true;
    // EANPA_SPATIAL_DIAG (env): 'red' = constant color (tests the proxy
    // draw/compose chain with no texture sampling), 'uv' = sample with
    // geometry uv (tests whether screenUV is the break)
    const DIAG = (typeof Deno !== 'undefined' && Deno.env.get('EANPA_SPATIAL_DIAG')) || '';
    const source = T3.texture(cloudTarget.texture);
    const suvNode = DIAG === 'uv' ? T3.uv() : T3.screenUV;
    const current = source.sample(suvNode);
    if (DIAG === 'red') {
        proxyMaterial.colorNode = T3.vec3(4, 0, 0);
        proxyMaterial.opacityNode = T3.float(0.5);
    } else {
        proxyMaterial.colorNode = current.rgb;
        proxyMaterial.opacityNode = current.a;
    }

    // shell must sit INSIDE the camera frustum: beyond camera.far the
    // fragments clip and the proxy silently vanishes (black sky)
    const proxyRadius = Math.min(30000, (camera?.far ?? 60000) * 0.9);
    const proxyGeometry = new T3.SphereGeometry(proxyRadius, 24, 12);
    const backgroundProxy = new T3.Mesh(proxyGeometry, backgroundMaterial);
    backgroundProxy.name = 'current_frame_background_proxy';
    backgroundProxy.userData.noWet = true;
    backgroundProxy.userData.noSupportCheck = true;
    backgroundProxy.renderOrder = -100;
    backgroundProxy.frustumCulled = false;
    const proxy = new T3.Mesh(proxyGeometry, proxyMaterial);
    proxy.name = 'current_frame_cloud_proxy';
    proxy.userData.noWet = true;
    proxy.userData.noSupportCheck = true;
    proxy.renderOrder = -98;
    proxy.frustumCulled = false;

    const savedClearColor = new T3.Color();
    let backgroundDome = null;
    let cloudDome = null;
    let sky = null;
    let attachedScene = null;
    let originalBackgroundToneMapped = null;
    let originalCloudToneMapped = null;
    let disposed = false;

    return {
        proxy,
        backgroundProxy,
        mode: 'spatial-current-frame-sky',
        attach(scene, skyRef) {
            if (disposed) return false;
            if (backgroundDome || cloudDome || attachedScene) return false;
            const nextBackgroundDome = skyRef?.domes?.[0] ?? null;
            const nextCloudDome = skyRef?.domes?.[1] ?? null;
            if (!nextBackgroundDome || !nextCloudDome) return false;
            backgroundDome = nextBackgroundDome;
            cloudDome = nextCloudDome;
            sky = skyRef;
            attachedScene = scene;
            // MeshBasicNodeMaterial normally tone-maps its output. Doing that
            // in this HDR target and again in the main scene made the high/2D
            // layer converge toward the same dull grey in optimized modes.
            originalBackgroundToneMapped = backgroundDome.material?.toneMapped;
            originalCloudToneMapped = cloudDome.material?.toneMapped;
            if (backgroundDome.material) {
                backgroundDome.material.toneMapped = false;
                // the offline domes stamp empty MRT structs for the main
                // pass G-buffer; the offscreen targets here are single-
                // attachment — an MRT fragment against one attachment fails
                // pipeline creation and the target stays black
                this._bgMrt = backgroundDome.material.mrtNode ?? null;
                backgroundDome.material.mrtNode = null;
                backgroundDome.material.needsUpdate = true;
            }
            if (cloudDome.material) {
                cloudDome.material.toneMapped = false;
                this._cloudMrt = cloudDome.material.mrtNode ?? null;
                cloudDome.material.mrtNode = null;
                cloudDome.material.needsUpdate = true;
            }
            backgroundScene.add(backgroundDome);
            cloudScene.add(cloudDome);
            if (DIAG_EARLY !== 'noproxy') scene.add(backgroundProxy, proxy);
            if (sky.uniforms?.frameJit) sky.uniforms.frameJit.value = 0;
            return true;
        },
        async render() {
            if (DIAG_EARLY === 'norender') return;   // bisect: attach-only
            if (disposed || !backgroundDome || !cloudDome) return;
            await sky.prepareOptimizedCaches?.(renderer, camera);
            backgroundProxy.position.copy(camera.position);
            proxy.position.copy(camera.position);
            if (sky.uniforms?.frameJit) sky.uniforms.frameJit.value = 0;
            const previousTarget = renderer.getRenderTarget();
            renderer.getClearColor(savedClearColor);
            const previousAlpha = renderer.getClearAlpha();
            // the offline harness patches renderer.renderAsync to run the
            // whole post pipeline regardless of arguments — use the raw
            // renderer call for these offscreen dome passes
            const raw = globalThis._rawRenderAsync ?? renderer.renderAsync.bind(renderer);
            try {
                renderer.setRenderTarget(backgroundTarget);
                renderer.setClearColor(0x000000, 1);
                await raw(backgroundScene, camera);
                renderer.setRenderTarget(cloudTarget);
                renderer.setClearColor(0x000000, 0);
                await raw(cloudScene, camera);
            } finally {
                renderer.setRenderTarget(previousTarget);
                renderer.setClearColor(savedClearColor, previousAlpha);
            }
        },
        resize(w, h) {
            if (!disposed) {
                if (w) baseW = w;
                if (h) baseH = h;
                backgroundTarget.setSize(width(), height());
                cloudTarget.setSize(width(), height());
            }
        },
        getDivisor() { return divisor; },
        setDivisor(next) {
            if (disposed) return false;
            const resolved = Math.max(1, Math.round(next));
            if (resolved === divisor) return false;
            divisor = resolved;
            backgroundTarget.setSize(width(), height());
            cloudTarget.setSize(width(), height());
            return true;
        },
        getResolution() { return { width: width(), height: height(), divisor }; },
        dispose() {
            if (disposed) return;
            disposed = true;
            backgroundScene.remove(backgroundDome);
            cloudScene.remove(cloudDome);
            if (backgroundDome?.material && originalBackgroundToneMapped !== null) {
                backgroundDome.material.toneMapped = originalBackgroundToneMapped;
                if (this._bgMrt) backgroundDome.material.mrtNode = this._bgMrt;
                backgroundDome.material.needsUpdate = true;
            }
            if (cloudDome?.material && originalCloudToneMapped !== null) {
                cloudDome.material.toneMapped = originalCloudToneMapped;
                if (this._cloudMrt) cloudDome.material.mrtNode = this._cloudMrt;
                cloudDome.material.needsUpdate = true;
            }
            if (attachedScene) {
                // attach() reparents the real domes into private offscreen
                // scenes. Restore them before releasing the pass so disposing
                // this optimization independently cannot make the sky vanish.
                if (backgroundDome) attachedScene.add(backgroundDome);
                if (cloudDome) attachedScene.add(cloudDome);
                attachedScene.remove(backgroundProxy, proxy);
            }
            backgroundTarget.dispose();
            cloudTarget.dispose();
            proxyGeometry.dispose();
            backgroundMaterial.dispose();
            proxyMaterial.dispose();
            backgroundDome = null;
            cloudDome = null;
            sky = null;
            attachedScene = null;
        },
    };
}
