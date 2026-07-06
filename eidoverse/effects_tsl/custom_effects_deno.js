// custom_effects_deno.js — central registry for TSL post-process effects
// in the WebGPU/Deno pipeline. The TSL replacement for the old WebGL
// custom_effects.js (which is still used as the ShaderPass-based fallback
// path; this module is the new pipeline's home).
//
// Architecture:
//   Each effect is its own file in `_webgpu_poc/effects_tsl/`. Each one
//   exposes `<EffectName>FX.applyTo({ scene, camera, opts })` which:
//     1. (optionally) attaches scene-side geometry (e.g. underwater bubbles)
//     2. Sets globalThis._autoEnhanceColorHook to splice into autoenhance
//   This module wraps those individual entry points behind a unified
//   registry + selector API.
//
// Public API:
//   CustomEffectsDeno.applyTo({
//       scene,              // THREE.Scene
//       camera,             // THREE.Camera
//       effects: 'underwater'                       // single
//             | ['vhs_tape']                        // array (single only for v0)
//             | ['underwater', 'vhs_tape'],         // multi (NOT YET — see note)
//       opts: { underwater: {...}, vhs_tape: {...} },
//   });
//
//   CustomEffectsDeno.register(name, factoryFn);
//
//   factoryFn signature: ({ scene, camera, opts }) => { update, uniforms, ... }
//   The factory MUST set globalThis._autoEnhanceColorHook itself.
//
// Multi-effect chaining note:
//   Each effect today samples its color input as a TextureNode (so it can
//   neighbor-sample for blurs etc.). Stacking N effects in one frame requires
//   render-to-texture between effects so each sees its predecessor's output
//   as a real texture. Not built yet. For now applyTo accepts only one
//   effect; passing multiple logs a warning and uses the first.
//
// Pipeline rules (see project_no_webgl_no_cpu_in_new_pipeline.md):
//   - NodeMaterial only, no WebGL fallbacks in this layer.
//   - GPU work only — no CPU per-frame loops, no CPU texture baking.
//   - Effects in `effects_tsl/` are backbone tools; the safety-net code
//     lives in render_scene.mjs, NOT here.

(function () {
    'use strict';
    if (!globalThis.THREE) {
        console.warn('[custom_effects_deno] THREE global not present — skipping load');
        return;
    }

    const registry = {};

    function register(name, factory) {
        if (typeof factory !== 'function') {
            throw new Error(`CustomEffectsDeno.register("${name}"): factory must be a function`);
        }
        registry[name] = factory;
    }

    function listEffects() {
        return Object.keys(registry);
    }

    // applyTo({ scene, camera, effects, opts }) — apply a screen-space effect.
    // `effects` accepts a comma-separated string or array, but only ONE effect
    // is applied today (multi-effect chaining is unsupported on this GPU
    // backend — see the note in the multi-effect branch below); extras are
    // skipped with a warning. Returns the effect's object ({ update, uniforms }).
    function applyTo(opts) {
        opts = opts || {};
        const { scene, camera, effects } = opts;
        if (!effects) {
            throw new Error('CustomEffectsDeno.applyTo: opts.effects required (string or array)');
        }
        const effectsList = (Array.isArray(effects) ? effects : String(effects).split(','))
            .map((s) => String(s).trim()).filter(Boolean);
        if (!effectsList.length) {
            throw new Error('CustomEffectsDeno.applyTo: opts.effects must contain at least one entry');
        }
        for (const name of effectsList) {
            if (!registry[name]) {
                const known = listEffects().join(', ') || '(none)';
                throw new Error(`CustomEffectsDeno.applyTo: unknown effect "${name}". Registered: ${known}`);
            }
        }

        const optsFor = (name) => (opts.opts && opts.opts[name]) || {};
        const rttFn = globalThis.THREE.rtt || globalThis.rtt;
        const W = globalThis.WIDTH || 1280, H = globalThis.HEIGHT || 720;

        // EFFECT LAYERING vs a screen-space overlay (HUD/lower-thirds):
        //   WORLD-LAYER effects belong UNDER the overlay (they ARE the world /
        //   the thing being filmed — sky, weather, light shafts, the blast, the
        //   water you're submerged in). SIGNAL-LAYER effects belong OVER the
        //   overlay (vhs/glitch/grain/rgb-shift/scanlines process the FINISHED
        //   broadcast signal, HUD included). The engine composites
        //   globalThis._overlayScene between the two stages:
        //       colorHook (world) → overlay → screenHook (signal)
        //   With no overlay the two hooks run back-to-back → identical to before.
        // ALWAYS_UNDER: full-world effects that would look broken composited
        // OVER a HUD (the bug we fixed) — locked under, the layer override is
        // ignored for them. DEFAULT_UNDER: start under but are switchable.
        // Everything else defaults over. Override any switchable effect with
        // opts[name].layer = 'under' | 'over' (e.g. blueprint/cross_hatch read
        // as a world treatment with layer:'under', or a screen filter as-is).
        const ALWAYS_UNDER = new Set([
            'volumetric_clouds', 'nuclear_explosion', 'depth_rain', 'godrays', 'underwater',
        ]);
        const DEFAULT_UNDER = new Set(['depth_fog', 'retro_wireframe']);
        const layerOf = (name) => {
            if (ALWAYS_UNDER.has(name)) return 'under';           // locked
            const l = optsFor(name).layer;
            if (l === 'under' || l === 'over') return l;
            return DEFAULT_UNDER.has(name) ? 'under' : 'over';
        };
        const depthList = effectsList.filter((n) => layerOf(n) === 'under');
        const screenList = effectsList.filter((n) => layerOf(n) === 'over');

        // CHAINING via rtt() materialization (2026-06-11): nesting passes
        // directly crashes wgpu/Mesa-D3D12; materializing each stage into a real
        // render-target texture breaks the nesting. Effect authors: write hooks
        // in STATEMENT FORM (hoist with .toVar(), accumulate with addAssign).
        // buildGroup composes one ordered group of effects into a single hook.
        const buildGroup = (names) => {
            const hooks = [], fxObjs = [];
            for (const name of names) {
                globalThis._autoEnhanceColorHook = null;   // each effect sets this; we capture + relocate it
                const fx = registry[name]({ scene, camera, opts: optsFor(name) });
                hooks.push(globalThis._autoEnhanceColorHook);
                fxObjs.push(fx);
            }
            if (hooks.filter((h) => typeof h === 'function').length > 1 && typeof rttFn !== 'function') {
                console.warn(`[custom_effects_deno] chaining needs TSL rtt() (not on this bundle) — only "${names[0]}" of [${names.join(', ')}] will apply.`);
            }
            const hook = (colorOut, sceneDepth, sceneNormal, sceneMR) => {
                let acc = colorOut;
                for (let i = 0; i < hooks.length; i++) {
                    if (typeof hooks[i] !== 'function') continue;
                    let node = hooks[i](acc, sceneDepth, sceneNormal, sceneMR);
                    if (typeof rttFn === 'function' && i < hooks.length - 1) node = rttFn(node, W, H); // materialize between stages
                    acc = node;
                }
                return acc;
            };
            return { hook, fxObjs };
        };

        globalThis._autoEnhanceColorHook = null;
        globalThis._autoEnhanceScreenHook = null;
        const allFx = [];
        const uniformsByName = {};
        if (depthList.length) {
            const g = buildGroup(depthList);
            globalThis._autoEnhanceColorHook = g.hook;
            depthList.forEach((n, i) => { uniformsByName[n] = g.fxObjs[i]?.uniforms; allFx.push(g.fxObjs[i]); });
        }
        if (screenList.length) {
            const g = buildGroup(screenList);
            globalThis._autoEnhanceScreenHook = g.hook;
            screenList.forEach((n, i) => { uniformsByName[n] = g.fxObjs[i]?.uniforms; allFx.push(g.fxObjs[i]); });
        }
        if (effectsList.length > 1) {
            console.log(`[custom_effects_deno] effects split — under-overlay(depth): [${depthList.join(', ') || 'none'}], over-overlay(screen): [${screenList.join(', ') || 'none'}]`);
        }
        return {
            effects: allFx,
            // Single effect keeps the flat `.uniforms.<x>` shape for back-compat;
            // multiple effects expose `.uniforms.<effectName>.<x>`.
            uniforms: effectsList.length === 1 ? (allFx[0]?.uniforms || {}) : uniformsByName,
            update(t) { for (const f of allFx) { try { f?.update?.(t); } catch (e) {} } },
            setResolution(w, h) { for (const f of allFx) { try { f?.setResolution?.(w, h); } catch (e) {} } },
        };
    }

    // ---- Built-in registrations ----
    // Each effect module installs its own `<Name>FX` global. We pick those
    // up here so the registry has them available without extra wiring.
    if (globalThis.UnderwaterFX && typeof globalThis.UnderwaterFX.applyTo === 'function') {
        register('underwater', globalThis.UnderwaterFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] underwater unavailable — UnderwaterFX not loaded');
    }
    if (globalThis.VHSTapeFX && typeof globalThis.VHSTapeFX.applyTo === 'function') {
        register('vhs_tape', globalThis.VHSTapeFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] vhs_tape unavailable — VHSTapeFX not loaded');
    }
    if (globalThis.CRTFX && typeof globalThis.CRTFX.applyTo === 'function') {
        register('crt', globalThis.CRTFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] crt unavailable — CRTFX not loaded');
    }
    if (globalThis.OldBWFilmFX && typeof globalThis.OldBWFilmFX.applyTo === 'function') {
        register('old_bw_film', globalThis.OldBWFilmFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] old_bw_film unavailable — OldBWFilmFX not loaded');
    }
    if (globalThis.VolumetricCloudsFX && typeof globalThis.VolumetricCloudsFX.applyTo === 'function') {
        register('volumetric_clouds', globalThis.VolumetricCloudsFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] volumetric_clouds unavailable — VolumetricCloudsFX not loaded');
    }
    if (globalThis.NuclearExplosionFX && typeof globalThis.NuclearExplosionFX.applyTo === 'function') {
        register('nuclear_explosion', globalThis.NuclearExplosionFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] nuclear_explosion unavailable — NuclearExplosionFX not loaded');
    }
    if (globalThis.AnamorphicFlareFX && typeof globalThis.AnamorphicFlareFX.applyTo === 'function') {
        register('anamorphic_flare', globalThis.AnamorphicFlareFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] anamorphic_flare unavailable — AnamorphicFlareFX not loaded');
    }
    if (globalThis.SepiaFX && typeof globalThis.SepiaFX.applyTo === 'function') {
        register('sepia', globalThis.SepiaFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] sepia unavailable — SepiaFX not loaded');
    }
    if (globalThis.BleachBypassFX && typeof globalThis.BleachBypassFX.applyTo === 'function') {
        register('bleach_bypass', globalThis.BleachBypassFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] bleach_bypass unavailable — BleachBypassFX not loaded');
    }
    if (globalThis.AfterImageFX && typeof globalThis.AfterImageFX.applyTo === 'function') {
        register('after_image', globalThis.AfterImageFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] after_image unavailable — AfterImageFX not loaded');
    }
    if (globalThis.RGBShiftFX && typeof globalThis.RGBShiftFX.applyTo === 'function') {
        register('rgb_shift', globalThis.RGBShiftFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] rgb_shift unavailable — RGBShiftFX not loaded');
    }
    if (globalThis.RainOnCameraFX && typeof globalThis.RainOnCameraFX.applyTo === 'function') {
        register('rain_on_camera', globalThis.RainOnCameraFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] rain_on_camera unavailable — RainOnCameraFX not loaded');
    }
    if (globalThis.DepthRainFX && typeof globalThis.DepthRainFX.applyTo === 'function') {
        register('depth_rain', globalThis.DepthRainFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] depth_rain unavailable — DepthRainFX not loaded');
    }
    if (globalThis.RadialBlurFX && typeof globalThis.RadialBlurFX.applyTo === 'function') {
        register('radial_blur', globalThis.RadialBlurFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] radial_blur unavailable — RadialBlurFX not loaded');
    }
    if (globalThis.BoxBlurFX && typeof globalThis.BoxBlurFX.applyTo === 'function') {
        register('box_blur', globalThis.BoxBlurFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] box_blur unavailable — BoxBlurFX not loaded');
    }
    if (globalThis.HashBlurFX && typeof globalThis.HashBlurFX.applyTo === 'function') {
        register('hash_blur', globalThis.HashBlurFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] hash_blur unavailable — HashBlurFX not loaded');
    }
    if (globalThis.GodraysFX && typeof globalThis.GodraysFX.applyTo === 'function') {
        register('godrays', globalThis.GodraysFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] godrays unavailable — GodraysFX not loaded');
    }
    if (globalThis.LensflareFX && typeof globalThis.LensflareFX.applyTo === 'function') {
        register('lensflare', globalThis.LensflareFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] lensflare unavailable — LensflareFX not loaded');
    }
    if (globalThis.ChromaticAberrationAlphaFX && typeof globalThis.ChromaticAberrationAlphaFX.applyTo === 'function') {
        register('chromatic_aberration_alpha', globalThis.ChromaticAberrationAlphaFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] chromatic_aberration_alpha unavailable — ChromaticAberrationAlphaFX not loaded');
    }
    if (globalThis.WavyFX && typeof globalThis.WavyFX.applyTo === 'function') {
        register('wavy', globalThis.WavyFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] wavy unavailable — WavyFX not loaded');
    }
    if (globalThis.JitterFX && typeof globalThis.JitterFX.applyTo === 'function') {
        register('jitter', globalThis.JitterFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] jitter unavailable — JitterFX not loaded');
    }
    if (globalThis.MeltFX && typeof globalThis.MeltFX.applyTo === 'function') {
        register('melt', globalThis.MeltFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] melt unavailable — MeltFX not loaded');
    }
    if (globalThis.KaleidoscopeFX && typeof globalThis.KaleidoscopeFX.applyTo === 'function') {
        register('kaleidoscope', globalThis.KaleidoscopeFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] kaleidoscope unavailable — KaleidoscopeFX not loaded');
    }
    if (globalThis.NeonEdgesFX && typeof globalThis.NeonEdgesFX.applyTo === 'function') {
        register('neon_edges', globalThis.NeonEdgesFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] neon_edges unavailable — NeonEdgesFX not loaded');
    }
    if (globalThis.GlitchBarsFX && typeof globalThis.GlitchBarsFX.applyTo === 'function') {
        register('glitch_bars', globalThis.GlitchBarsFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] glitch_bars unavailable — GlitchBarsFX not loaded');
    }
    if (globalThis.BWHalftoneFX && typeof globalThis.BWHalftoneFX.applyTo === 'function') {
        register('bw_halftone', globalThis.BWHalftoneFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] bw_halftone unavailable — BWHalftoneFX not loaded');
    }
    if (globalThis.FocusBlurFX && typeof globalThis.FocusBlurFX.applyTo === 'function') {
        register('focus_blur', globalThis.FocusBlurFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] focus_blur unavailable — FocusBlurFX not loaded');
    }
    if (globalThis.DepthFogFX && typeof globalThis.DepthFogFX.applyTo === 'function') {
        register('depth_fog', globalThis.DepthFogFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] depth_fog unavailable — DepthFogFX not loaded');
    }
    if (globalThis.DitheringFX && typeof globalThis.DitheringFX.applyTo === 'function') {
        register('dithering', globalThis.DitheringFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] dithering unavailable — DitheringFX not loaded');
    }
    if (globalThis.BlueprintFX && typeof globalThis.BlueprintFX.applyTo === 'function') {
        register('blueprint', globalThis.BlueprintFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] blueprint unavailable — BlueprintFX not loaded');
    }
    if (globalThis.CrossHatchFX && typeof globalThis.CrossHatchFX.applyTo === 'function') {
        register('cross_hatch', globalThis.CrossHatchFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] cross_hatch unavailable — CrossHatchFX not loaded');
    }
    if (globalThis.FullToonFX && typeof globalThis.FullToonFX.applyTo === 'function') {
        register('full_toon', globalThis.FullToonFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] full_toon unavailable — FullToonFX not loaded');
    }
    if (globalThis.RetroWireframeFX && typeof globalThis.RetroWireframeFX.applyTo === 'function') {
        register('retro_wireframe', globalThis.RetroWireframeFX.applyTo);
    } else {
        console.warn('[custom_effects_deno] retro_wireframe unavailable — RetroWireframeFX not loaded');
    }
    globalThis.CustomEffectsDeno = { register, applyTo, listEffects, list: listEffects, registry };
    console.log(`[custom_effects_deno] registry ready — ${listEffects().length} effects (pick from the WHOLE list + vary your choice; don't grep-discover, head truncates it): ${listEffects().join(', ')}`);
})();
