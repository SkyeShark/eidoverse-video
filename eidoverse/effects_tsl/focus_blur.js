// focus_blur.js — TSL port of custom_effects.js::focus_blur. Wraps the
// three/addons DepthOfFieldNode (`dof`) so the agent gets proper bokeh
// depth-of-field for free instead of the original GLSL CoC + horizontal
// blur. The built-in handles CoC computation, near/far field separation,
// 64-tap bokeh kernel + blur — much higher quality than the hand-roll.
//
// Public API:
//   FocusBlurFX.applyTo({ camera, opts });
//
// Options:
//   focusObjects  Object3D[] — when set, focusDistance is recomputed each
//                              update(t) from the average view-space
//                              distance of these objects. Lets the agent
//                              point the camera at "the character and
//                              the chrome rock" without computing world-unit
//                              distances. Falls through to focusDistance
//                              when empty/missing. (default: undefined)
//   focusDistance float — focal plane distance in world units (default 5.0).
//                         Used as the fallback / initial value.
//   focalLength   float — out-of-focus falloff distance in world units (default 2.0)
//   bokehScale    float — bokeh kernel scale (default 1.0)
//   opacity       float — final blend (default 1.0)
//
// Depends on:
//   render_common.mjs surfacing `dof` + `perspectiveDepthToViewZ` on
//   the merged THREE namespace.

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[focus_blur] THREE global not present — skipping load');
        return;
    }
    const THREE = globalThis.THREE;

    function applyTo(args) {
        args = args || {};
        const camera = args.camera;
        if (!camera) throw new Error('FocusBlurFX.applyTo: opts.camera required (need camera.near/far for viewZ conversion)');
        const opts = args.opts ?? args;
        if (typeof THREE.dof !== 'function') {
            throw new Error('[focus_blur] THREE.dof missing — render_common.mjs must import addons/tsl/display/DepthOfFieldNode.js');
        }
        if (typeof THREE.perspectiveDepthToViewZ !== 'function') {
            throw new Error('[focus_blur] THREE.perspectiveDepthToViewZ missing');
        }

        // Always a real array so setFocusObjects() can mutate in place
        // even if the agent didn't pass any targets at applyTo time.
        const focusObjects = Array.isArray(opts.focusObjects) ? opts.focusObjects.slice() : [];
        const u = {
            focusDistance: THREE.uniform(opts.focusDistance ?? 5.0),
            focalLength:   THREE.uniform(opts.focalLength   ?? 2.0),
            bokehScale:    THREE.uniform(opts.bokehScale    ?? 1.0),
            opacity:       THREE.uniform(opts.opacity       ?? 1.0),
            camNear:       THREE.uniform(camera.near),
            camFar:        THREE.uniform(camera.far),
        };

        // Compute focusDistance from world positions of the targeted
        // objects, projected onto the camera forward axis. Average rather
        // than min so a small group near the same depth pulls the focal
        // plane to their centroid; outliers don't yank focus to the
        // closest one.
        const _camForward = new THREE.Vector3();
        const _objWorld   = new THREE.Vector3();
        const _toObj      = new THREE.Vector3();
        const recomputeFocus = () => {
            if (focusObjects.length === 0) return;
            camera.updateMatrixWorld();
            camera.getWorldDirection(_camForward);  // unit vec along -Z in world
            let sum = 0, n = 0;
            for (const obj of focusObjects) {
                if (!obj || !obj.getWorldPosition) continue;
                obj.getWorldPosition(_objWorld);
                _toObj.copy(_objWorld).sub(camera.position);
                const fwdDist = _toObj.dot(_camForward);
                if (fwdDist > 0) { sum += fwdDist; n++; }
            }
            if (n > 0) u.focusDistance.value = sum / n;
        };
        // Apply once now so the first frame has a sensible plane.
        recomputeFocus();

        globalThis._autoEnhanceColorHook = (colorOut, sceneDepth /*, sceneNormal, sceneMR */) => {
            const colorTex = THREE.convertToTexture(colorOut);
            const depthTex = THREE.convertToTexture(sceneDepth);
            const d = depthTex.sample(THREE.uv()).r;
            const viewZ = THREE.perspectiveDepthToViewZ(d, u.camNear, u.camFar);
            const dofOut = THREE.dof(colorTex, viewZ, u.focusDistance, u.focalLength, u.bokehScale);
            // Optional opacity blend with original.
            return THREE.Fn(() => THREE.mix(
                colorTex.sample(THREE.uv()),
                dofOut,
                u.opacity,
            ))();
        };

        return {
            uniforms: u,
            update(/* t */) {
                // dof reads camera.near/far via uniforms; refresh in case camera changes.
                u.camNear.value = camera.near;
                u.camFar.value  = camera.far;
                // Re-track focus targets every frame so a moving camera
                // or a moving subject keeps the focal plane glued to it.
                recomputeFocus();
            },
            setFocusObjects(arr) {
                if (!Array.isArray(arr)) throw new Error('FocusBlurFX.setFocusObjects: array required');
                focusObjects.length = 0;
                focusObjects.push(...arr);
                recomputeFocus();
            },
        };
    }

    globalThis.FocusBlurFX = { applyTo };
    console.log('[focus_blur] FocusBlurFX.applyTo registered');
})();
