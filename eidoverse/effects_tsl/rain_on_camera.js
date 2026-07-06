// rain_on_camera.js — rain-on-the-lens: droplets that bead, drift and
// streak on the camera lens, as a TSL screen-space colour hook for the
// WebGPU pipeline.
//
// LENS effect: pure screen-space (raw uv), so droplets stay LOCKED to the
// camera at a FIXED size — they do NOT reproject/zoom when the 3D camera
// moves (unlike depth/world-projected effects). It refracts + wet-blurs the
// rendered scene through animated drops/trails/static droplets on the glass.
//
// Public API: RainOnCameraFX.applyTo({ scene, camera, opts })
// opts:
//   dropSize   float — drop radius (default 0.2)
//   amount     float — overall rain strength / opacity (default 1.0)
//   speed      float — fall speed multiplier (default 1.0)
//   blurSize   float — wet out-of-focus blur radius in px (default 26)
//   resolution [w,h] — for aspect + blur radius (default [1920,1080])
//   directions int   — blur directions (default 12)
//   quality    int   — blur samples/direction (default 3)
(function () {
    'use strict';
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[rain_on_camera] THREE global not present — skipping'); return; }

    function applyTo(args) {
        args = args || {};
        const opts = args.opts ?? args;
        const {
            Fn, vec2, vec3, vec4, float, uniform, uv, convertToTexture,
            sin, cos, fract, floor, abs, clamp, max, min, dot, length, smoothstep, mix,
        } = THREE;

        const res = opts.resolution || [1920, 1080];
        const ASPECT = res[0] / res[1];
        const SIZE = opts.dropSize != null ? opts.dropSize : 0.2;
        const DIRS = opts.directions | 0 || 12;
        const QUAL = opts.quality | 0 || 3;
        const BLURPX = opts.blurSize != null ? opts.blurSize : 9;

        const uAmount = uniform(opts.amount != null ? opts.amount : 1.0);
        const uSpeed = uniform(opts.speed != null ? opts.speed : 1.0);
        const uTime = uniform(0);
        const dSize = float(SIZE);
        const RADX = float(BLURPX / res[0]), RADY = float(BLURPX / res[1]);

        const S = (a, b, t) => smoothstep(a, b, t);
        const N = (t) => fract(sin(t.mul(12345.564)).mul(7658.76));
        const Saw = (b, t) => S(float(0), b, t).mul(S(float(1), b, t));
        const N13 = (p) => {
            let p3 = fract(vec3(p, p, p).mul(vec3(0.1031, 0.11369, 0.13787)));
            p3 = p3.add(dot(p3, p3.yzx.add(19.19)));
            return fract(vec3(
                p3.x.add(p3.y).mul(p3.z),
                p3.x.add(p3.z).mul(p3.y),
                p3.y.add(p3.z).mul(p3.x),
            ));
        };

        // Drops(uv,t) → vec2(mask, trail)
        const Drops = (uvIn, t) => {
            const UV = uvIn;
            let uvg = vec2(uvIn.x, uvIn.y.add(t.mul(0.8)));
            const a = vec2(6.0, 1.0);
            const grid = a.mul(2.0);
            let id = floor(uvg.mul(grid));
            uvg = vec2(uvg.x, uvg.y.add(N(id.x)));
            id = floor(uvg.mul(grid));
            const n = N13(id.x.mul(35.2).add(id.y.mul(2376.1)));
            const st = fract(uvg.mul(grid)).sub(vec2(0.5, 0.0));
            let x = n.x.sub(0.5);
            const yv = UV.y.mul(20.0);
            const distort = sin(yv.add(sin(yv)));
            x = x.add(distort.mul(float(0.5).sub(abs(x))).mul(n.z.sub(0.5)));
            x = x.mul(0.7);
            const ti = fract(t.add(n.z));
            const y = Saw(float(0.85), ti).sub(0.5).mul(0.9).add(0.5);
            const p = vec2(x, y);
            const d = length(st.sub(p).mul(vec2(a.y, a.x)));
            const Drop = S(dSize, float(0), d);
            const r = smoothstep(float(1), y, st.y).sqrt();
            const cd = abs(st.x.sub(x));
            const trail = S(dSize.mul(0.5).add(0.03).mul(r), dSize.mul(0.5).sub(0.05).mul(r), cd);
            const trailFront = S(float(-0.02), float(0.02), st.y.sub(y));
            const trailF = trail.mul(trailFront);
            // droplets (only the live second definition from the shader)
            let y2 = UV.y.add(N(id.x));
            y2 = fract(y2.mul(10.0)).add(st.y.sub(0.5));
            const dd = length(st.sub(vec2(x, y2)));
            const droplets = S(dSize.mul(N(id.x)), float(0), dd);
            const m = Drop.add(droplets.mul(r).mul(trailFront));
            return vec2(m, trailF);
        };

        const StaticDrops = (uvIn, t) => {
            let uvg = uvIn.mul(30.0);
            const id = floor(uvg);
            uvg = fract(uvg).sub(0.5);
            const n = N13(id.x.mul(107.45).add(id.y.mul(3543.654)));
            const p = n.xy.sub(0.5).mul(0.5);
            const d = length(uvg.sub(p));
            const fade = Saw(float(0.025), fract(t.add(n.z)));
            return S(dSize, float(0), d).mul(fract(n.z.mul(10.0))).mul(fade);
        };

        const Rain = (uvIn, t) => {
            const s = StaticDrops(uvIn, t);
            const r1 = Drops(uvIn, t);
            const r2 = Drops(uvIn.mul(1.8), t);
            let c = s.add(r1.x).add(r2.x);
            c = S(float(0.3), float(1.0), c);
            return vec2(c, max(r1.y, r2.y));
        };

        globalThis._autoEnhanceColorHook = (colorOut) => {
            const sceneTex = convertToTexture(colorOut);
            const BISECT = (typeof Deno !== 'undefined' && Deno.env.get('RAIN_BISECT')) | 0;
            if (BISECT === 1) return Fn(() => sceneTex.sample(uv()))();
            return Fn(() => {
                // raw screen uv → fixed-size, camera-locked lens space.
                // y is NEGATED: our screen uv is y-down, the lens-space math
                // is y-up — without the flip the rain falls UP.
                const screen = uv();
                const ruv = screen.sub(0.5).mul(vec2(ASPECT, -1.0));  // aspect-corrected, centered, y-up
                const UV = screen.sub(0.5).mul(0.9).add(0.5);          // slight inset like the original
                const t = uTime.mul(0.2).mul(uSpeed);

                // STATEMENT FORM, not expression form: hoist every shared
                // subgraph into .toVar() and accumulate with addAssign. The
                // chained-.add() version re-inlined the full 3x Rain graph
                // into every blur tap — one titanic nested expression that
                // Naga rejects ('fragment_RTT' ShaderModule invalid → black).
                const c = Rain(ruv, t).toVar();
                if (BISECT === 2) return vec4(c.x, c.x, c.y, 1.0);
                const e = vec2(0.001, 0.0);
                const cx = Rain(ruv.add(e), t).x.toVar();
                const cy = Rain(ruv.add(vec2(e.y, e.x)), t).x.toVar();
                // y term negated back into screen space (ruv is y-flipped)
                const n = vec2(cx.sub(c.x), c.x.sub(cy)).mul(uAmount).toVar();
                const baseUV = UV.add(n).toVar();

                if (BISECT === 3) return vec4(sceneTex.sample(baseUV).rgb, 1.0);
                // wet out-of-focus gaussian blur, sampled through the refraction
                const Pi = 6.28318530718;
                const col = sceneTex.sample(baseUV).rgb.toVar();
                let taps = 1;
                for (let di = 0; di < DIRS; di++) {
                    const d = (di / DIRS) * Pi;
                    const dir = [Math.cos(d), Math.sin(d)];
                    for (let qi = 1; qi <= QUAL; qi++) {
                        const i = qi / QUAL;
                        const off = vec2(dir[0] * i, dir[1] * i).mul(vec2(RADX, RADY));
                        col.addAssign(sceneTex.sample(baseUV.add(off)).rgb);
                        taps++;
                    }
                }
                col.divAssign(taps);
                if (BISECT === 4) return vec4(col, 1.0);

                // composite: faithful to the original's LOD focus — drops AND
                // trails reveal the SHARP image (water in contact wipes the
                // mist), wet blur only on the bare glass between them. No
                // brighten/darken term: the original never tints trails.
                const tex = sceneTex.sample(baseUV).rgb.toVar();
                const cyc = clamp(c.y.mul(uAmount), float(0), float(1)).toVar();
                const focusMask = max(S(float(0.1), float(0.3), c.x), cyc).toVar();
                col.assign(mix(col, tex, focusMask));
                return vec4(col, 1.0);
            })();
        };

        return { uniforms: { amount: uAmount, speed: uSpeed, time: uTime }, update(tt) { uTime.value = tt || 0; } };
    }

    globalThis.RainOnCameraFX = { applyTo };
    console.log('[rain_on_camera] RainOnCameraFX.applyTo registered');
})();
