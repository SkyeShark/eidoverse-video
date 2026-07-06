// bw_halftone.js — TSL port of custom_effects.js::bw_halftone.
// Classic 45° newspaper-print halftone: rotated dot lattice driven by
// two interference cosines, modulated by source luminance, mapped from
// inkColor → paperColor.
//
// Public API:
//   BWHalftoneFX.applyTo({ opts });
//
// Options:
//   threshold  float — gray-clamp threshold (default 0.4)
//   dotSize    float — dot lattice scale (default 1.8)
//   angle      float — screen rotation in degrees (default 45)
//   inkColor   [r,g,b] — dark colour (default [0, 0, 0])
//   paperColor [r,g,b] — light colour (default [1, 1, 1])
//   opacity    float — final blend with original (default 1.0)
//   width/height int — output res (defaults to globalThis.WIDTH/HEIGHT)

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[bw_halftone] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function buildHook({ opts }) {
        const {
            uniform, Fn, vec2, vec3, vec4, float, uv, screenCoordinate,
            sin, cos, mix, clamp, max,
        } = THREE;

        const w = opts.width  ?? globalThis.WIDTH  ?? 1280;
        const h = opts.height ?? globalThis.HEIGHT ?? 720;
        const ink   = opts.inkColor   ?? [0, 0, 0];
        const paper = opts.paperColor ?? [1, 1, 1];

        const u = {
            iResolution: uniform(new THREE.Vector2(w, h)),
            threshold:   uniform(opts.threshold ?? 0.4),
            dotSize:     uniform(opts.dotSize   ?? 1.8),
            screenAngle: uniform(opts.angle     ?? 45.0),
            inkColor:    uniform(new THREE.Vector3(ink[0],   ink[1],   ink[2])),
            paperColor:  uniform(new THREE.Vector3(paper[0], paper[1], paper[2])),
            opacity:     uniform(opts.opacity ?? 1.0),
        };

        const DEG_TO_RAD = Math.PI / 180.0;

        return {
            uniforms: u,
            update(/* t */) {},
            setResolution(width, height) {
                u.iResolution.value.set(width, height);
            },
            hook(colorIn) {
                const colorTex = THREE.convertToTexture(colorIn);
                return Fn(() => {
                    const uvBase = uv();
                    const src = colorTex.sample(uvBase);

                    // Aspect-corrected screen coords keyed off width.
                    // gl_FragCoord-equivalent: uv * iResolution.
                    const ratio = u.iResolution.y.div(u.iResolution.x);
                    const cx = uvBase.x;  // already in [0,1] which == fragCoord.x/res.x
                    const cy = uvBase.y.mul(ratio);
                    const dst = vec2(cx, cy);
                    const rotCenter = vec2(0.5, ratio.mul(0.5));
                    const shift = dst.sub(rotCenter);

                    const angleRad = u.screenAngle.mul(DEG_TO_RAD);
                    const sa = sin(angleRad);
                    const ca = cos(angleRad);
                    const d = float(Math.PI).div(u.dotSize).mul(680.0);

                    // added(sh, sa, ca, c, d) = 0.5 + 0.25*cos((sh.x*sa+sh.y*ca + c.x)*d)
                    //                              + 0.25*cos((sh.x*ca-sh.y*sa + c.y)*d)
                    const t1 = shift.x.mul(sa).add(shift.y.mul(ca)).add(rotCenter.x).mul(d);
                    const t2 = shift.x.mul(ca).sub(shift.y.mul(sa)).add(rotCenter.y).mul(d);
                    const raster = float(0.5).add(cos(t1).mul(0.25)).add(cos(t2).mul(0.25));

                    const avg = src.r.mul(0.2125).add(src.g.mul(0.7154)).add(src.b.mul(0.0721));
                    const denom = max(float(1).sub(u.threshold), 0.0001);
                    const gray = clamp(
                        raster.mul(u.threshold).add(avg).sub(u.threshold).div(denom),
                        0, 1,
                    );

                    const col = mix(u.inkColor, u.paperColor, gray);
                    return mix(src, vec4(col, 1.0), u.opacity);
                })();
            },
        };
    }

    function applyTo(args) {
        const opts = (args && args.opts) ?? args ?? {};
        const built = buildHook({ opts });

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth, sceneNormal, sceneMR) => {
            return built.hook(colorOut, sceneDepth, sceneNormal, sceneMR);
        };

        return {
            update(t) { built.update(t); },
            setResolution(w, h) { built.setResolution(w, h); },
            uniforms: built.uniforms,
        };
    }

    globalThis.BWHalftoneFX = { applyTo };
    console.log('[bw_halftone] BWHalftoneFX.applyTo registered');
})();
