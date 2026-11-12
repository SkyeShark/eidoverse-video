"""The volumetric EXAMPLES: explosions, fire and smoke (sdf_raymarch_loader.js's createSdfVolume examples), and the
lights their emission casts.

    explosion_ring    expanding smoke-ring detonation: a torus easing outward over a 4.5 s loop, the smoke rolling
                      round the tube's own axis, heat cooling to grey (make(speed=))
    flame             torch flame: the classic 2D simplex-fbm flame revolved round y (make(strength=, speed=))
    smoke             rising, widening grey-blue plume (make(speed=, density=))
    gyroid_fireball   cellular fireball: gyroid fbm, ignition -> fireball -> smoke puff -> gone on a 3 s loop
                      (make(speed=, seed=, density=))
    bonfire           bonfire: noise-shaped flames in a swaying teardrop envelope, broken smoke on a wind-bent axis
                      (make(speed=, density=))
    candle_flame      candle flame at real size (0.16 m), the blue hollow base, a thin smoke thread (make(speed=,
                      density=))
    fire              large roaring blaze: tapered-box footprint, licking tongues, a hollow torn smoke column to 5 m
                      (make(speed=, density=))
    nuclear_blast     mushroom cloud: cap, stem, trail, base surge and ground pad, rolling noise, cooling heat, late
                      dispersal on a 20 s loop, 19 m tall by default (make(speed=, heat=, density=, size=))
    (explosion, the pyroclastic fireball, is a surface SDF: examples_solids.py)

Each sample() is the engine's TSL, written in GLSL node for node, so the volume, its reference march and the engine
compute the same field. A volume is a real Volume object (eidoblend.sdf.volume): each frame's grids are an OpenVDB
file, EEVEE lights, shadows and mixes it with the scene, and the camera may go inside it.

    from eidoblend.sdf import EXAMPLES
    from eidoblend.sdf.examples_volumes import light_from_emission, light_from_surface, fit_volume_range, build_still

    fire = EXAMPLES['bonfire'].make(location=(0, 0, 0), cache_dir=os.path.join(out, 'sdf_cache'), build=False)
    fire.bake(1, 96)                         # one .vdb per frame: the saved .blend plays and renders any frame
    rig = light_from_emission(fire)          # keyed lamps carrying the fire's light onto the scene (see below)
    fit_volume_range(scene, scene.camera, [fire])
    build_still(fire, 2.5)                   # or a still at t = 2.5 s, in a file of its own

make() options: the engine's knobs (speed, density, strength, seed, heat, size), look='lit' (the fire + smoke
examples: the fire emits, the smoke scatters the scene's light), fit=False (the engine's box instead of GRID_BOUNDS,
the box the medium fills over its loop), and every create_sdf_volume option (cells, voxel, location, cache_dir ...).

THE ENGINE'S ANIMATION. The engine's sample() read three's global `time` through memoised TSL nodes (_anim and
_animMemo, rebuilt per make() so no two materials shared node objects). In GLSL the animation is a function of uTime
computed in sample(); there is nothing to memoise or reset. Each volume keeps its own uniforms (the engine's E._u were
shared by every instance of an example: make({speed}) changed them all). bake() samples uTime = frame time, one grid
per frame.

LIGHT ON THE SCENE. EEVEE draws a volume's emission but does not light surfaces with it (the floor beside a bonfire
takes nothing from its flames: tests/sdf_volumes/test_volume_lights.py), so a fire lights its surroundings with
lights. light_from_emission() reads each baked frame's grids back and keys point lights from them: power = 4 pi x the
emission that escapes the volume (each voxel's emission x its mean transmittance to the box along the six axes, x
its volume), placed at the escaping light's centroid, sized to its spread, coloured by it; several lights for a
spread-out medium (the mushroom cloud's cap and ring). light_from_surface() does the same for an emissive SDF solid
(the pyroclastic `explosion`), whose glow EEVEE's fast GI gathers only from what is on screen: pi x radiance x area
x each face's escape fraction, the lamps inside the solid with the solid taken out of their shadows (shadow
linking).
"""

from __future__ import annotations

import math
import os

import numpy as np

from .spec import register_example

# ------------------------------------------------------------------------------------------------ explosion_ring --
# Expanding smoke-ring detonation (the engine's TSL port, 2026-07-05, of a torus-based volumetric nuke): a torus that
# eases outward over a ~4.5 s loop while the volume inside the tube rotates around the tube's own axis (the rolling
# smoke), density from a 4-octave noise stack in the rotated space, a heat -> colour palette that cools as the loop
# progresses, and a decay fade. The source's ground shadow / glow, camera shake and vignette were scene-level work
# and are not part of the placeable. Live knob: uSpeed.
_RING_EXTRA = r"""
// post(sum)'s contrast curve, folded into the medium: the grids raise each sample's density to uFoldGamma (thin
// wisps fade, the core stays), material_settings scale the result. The reference march keeps the engine's sample()
// and its post (SDF_VIEW_DEPENDENT is 1 only there), unless a fit asks for the fold in it too.
#ifndef RING_FOLD_IN_REFERENCE
#define RING_FOLD_IN_REFERENCE 0
#endif
#if SDF_VIEW_DEPENDENT && !RING_FOLD_IN_REFERENCE
#define RING_FOLD_GAMMA 1.0
#else
#define RING_FOLD_GAMMA uFoldGamma
#endif
struct RingAnim { float t; float rotT; float decay; float radius; float thickness; };
RingAnim ringAnim() {
    RingAnim A;
    A.t = mod(uTime * uSpeed, 4.5) * 4.0;
    A.rotT = pow(A.t * 0.2, 1.2);
    A.decay = 1.0 - smoothstep(7.0, 20.0, A.t);
    // easeOut(min(t, 2), 0.01, 1, 2): u = min(t, 2) / 2 -> 0.01 + u (2 - u)
    float u = min(A.t, 2.0) / 2.0;
    float ease = u * (2.0 - u) + 0.01;
    float r = clamp(ease, 0.0, 1.0) * 0.1;
    A.radius = r * 1.2 + A.t * 0.02;
    A.thickness = r * 2.0;
    return A;
}
float ringTorus(vec3 p, float tx, float ty) {
    vec2 q = vec2(length(p.xz) - tx, p.y);
    return length(q) - ty;
}
// rotate the volume inside the tube around the tube's own axis (the rolling smoke); up is tilted 0.01 in z so
// cross() never degenerates on the axis
vec3 ringSamplePos(vec3 rp, float radius, float rotT) {
    vec3 up = vec3(0.0, 1.0, 0.01);
    vec3 fw = normalize(vec3(rp.x, 0.0, rp.z));
    vec3 pIn = fw * radius;
    vec3 rt = cross(fw, up);
    vec3 lp = rp - pIn;
    vec3 l = vec3(dot(fw, lp), dot(up, lp), dot(rt, lp));      // into the tube frame (transpose of [fw, up, rt])
    float c = cos(rotT), s = sin(rotT);
    vec3 l2 = vec3(l.x * c - l.y * s, l.x * s + l.y * c, l.z);  // rotz(-rotT)
    return fw * l2.x + up * l2.y + rt * l2.z + pIn;           // back out of the tube frame
}
vec3 ringHeatToColor(float heat) {
    vec3 col = mix(vec3(0.0), vec3(1.0, 0.3, 0.0), clamp(heat * 15.0 - 2.0, 0.0, 1.0));
    col = mix(col, vec3(1.0, 1.0, 0.6), clamp(heat * 15.1 - 4.0, 0.0, 1.0));
    col = mix(col, vec3(1.0, 0.9, 0.8), clamp(heat * 190.0 - 60.0, 0.0, 1.0));
    return col;
}
"""

_RING_SAMPLE = r"""
SdfSample sample(vec3 p) {
    RingAnim A = ringAnim();
    // torus distance, noise-roughened (the dot(v, v) surface wobble)
    vec3 v = cos(A.t * 0.15 + p * 15.0) + sin(A.t * 0.25 + p * 10.0);
    float dRough = ringTorus(p, A.radius, A.thickness) - dot(v, v) * 0.005;
    // in-tube density shaping: 1 inside the tube, feathering at the wall (the source's reversed-edge
    // smoothstep(0, -thick / 2, d), in the defined-order form)
    float wall = 1.0 - smoothstep(A.thickness * -0.5, 0.0, dRough);
    // 4-octave noise stack in the ROTATED space (the rolling smoke)
    vec3 sp = ringSamplePos(p, A.radius, A.rotT);
    float d = vnoise(sp * 22.0) * 0.8;
    d += vnoise(sp * 70.0) * 0.4;
    d += vnoise(sp * 100.0) * 0.2;
    d += vnoise(sp * 350.0) * 0.45 * d;
    float density = clamp((wall * d - 0.4) / 0.8, 0.0, 1.0);
    // heat cools as the loop progresses; low heat reads as grey smoke
    float heat = density / max(1.0, A.t * 0.5 - 0.1);
    float smoke = heat / 0.03;
    vec3 col = smoke < 1.0 ? vec3(smoke * 0.5) : ringHeatToColor(heat);
    // per-sample opacity (density x the source's 0.024 x decay), zeroed below the ground line the source stopped
    // at; two-speed stepping: 1 cm strides through empty space, 1.5 mm inside the roughened tube
    float alpha = pow(density, RING_FOLD_GAMMA) * 0.024 * A.decay * step(-0.2, p.y);
    float stp = dRough > 0.0 ? 0.01 : 0.0015;
    return sdfSample(col, alpha, stp);
}"""

# the source's contrast + alpha shaping (its sqrt() was display encoding, skipped as the engine did)
_RING_POST = r"""
vec4 post(vec4 sum) {
    return vec4(smoothstep(0.0, 0.3, sum.xyz), smoothstep(0.0, 0.95, sum.w));
}"""

# ------------------------------------------------------------------------------------------------------- flame --
# Torch flame (the engine's TSL port, 2026-07-05, of a classic 2D simplex-fbm flame), REVOLVED around the y axis into
# a placeable volumetric fire: the 2D field is symmetric in x, so q.x becomes the radial distance |p.xz| exactly. Its
# own gradient-simplex noise and rotated-octave fbm (signed: the flame shape depends on it, so not the library's value
# noise), the teardrop field, the downward-scrolling turbulence, the orange -> yellow -> white palette and the late
# smoke veil. The flame occupies y in [0, ~1.4], base at y = 0. Knobs: uStrength (1..5, the turbulence scale of the
# source's five side-by-side flames), uSpeed.
_FLAME_EXTRA = r"""
// signed 2D gradient hash (the source's): -1..1 per component
vec2 flameHash2(vec2 p) {
    vec2 q = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(q) * 43758.5453123) * 2.0 - 1.0;
}
// 2D simplex noise (signed, ~ -1..1)
float flameNoise2(vec2 p) {
    const float K1 = 0.366025404;
    const float K2 = 0.211324865;
    vec2 i = floor(p + (p.x + p.y) * K1);
    vec2 a = p - i + (i.x + i.y) * K2;
    vec2 o = a.x > a.y ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec2 b = a - o + K2;
    vec2 c = a - 1.0 + 2.0 * K2;
    vec3 h = max(vec3(0.5) - vec3(dot(a, a), dot(b, b), dot(c, c)), vec3(0.0));
    vec3 h4 = h * h * h * h;
    vec3 n = h4 * vec3(dot(a, flameHash2(i)), dot(b, flameHash2(i + o)), dot(c, flameHash2(i + 1.0)));
    return dot(n, vec3(70.0));
}
// rotated-octave fbm, remapped to 0..1 (m2 = [1.6 1.2; -1.2 1.6])
vec2 flameM2(vec2 v) { return vec2(v.x * 1.6 - v.y * 1.2, v.x * 1.2 + v.y * 1.6); }
float flameFbm2(vec2 uv) {
    float f = flameNoise2(uv) * 0.5000;
    vec2 q = flameM2(uv);
    f += flameNoise2(q) * 0.2500; q = flameM2(q);
    f += flameNoise2(q) * 0.1250; q = flameM2(q);
    f += flameNoise2(q) * 0.0625;
    return f * 0.5 + 0.5;
}
"""

_FLAME_SAMPLE = r"""
SdfSample sample(vec3 p) {
    float strength = uStrength;
    float T3 = max(3.0, strength * 1.25) * uTime * uSpeed;
    // revolve the 2D flame field: q.x = radial distance, q.y = height - 0.25
    vec2 q = vec2(length(p.xz), p.y - 0.25);
    float n = flameFbm2(q * strength - vec2(0.0, 1.0) * T3);
    float c = 1.0 - pow(max(0.0, length(q * vec2(q.y * 1.5 + 1.8, 0.75)) - n * max(0.0, q.y + 0.25)), 1.2) * 16.0;
    // max(0, y) before pow: pow(x < 0, y) is NaN
    float c1 = clamp(n * c * (1.5 - pow(max(0.0, p.y) * 1.25, 4.0)), 0.0, 1.0);
    // palette: orange base -> yellow -> white-hot core
    vec3 col = vec3(c1 * 1.5, c1 * c1 * c1 * 1.5, c1 * c1 * c1 * c1 * c1 * c1);
    // late smoke veil (the source's "just added" line)
    float veil = pow(flameFbm2(q * strength * 1.25 - vec2(0.0, 1.0) * T3), 2.0);
    col = mix(col, vec3(pow(veil, 2.0)), clamp(0.75 - (col.x + col.y + col.z) / 3.0, 0.0, 1.0));
    // per-sample opacity from the flame field, fading toward the tip, GATED by the flame intensity c1 (ungated, the
    // fat noise-inflated column of positive c rendered as a milky slab round the fire)
    float a = clamp(c, 0.0, 1.0) * smoothstep(0.02, 0.22, c1) * (1.0 - pow(clamp(p.y / 1.4, 0.0, 1.0), 3.0));
    return sdfSample(col, a * 0.22, 0.028);
}"""

# ------------------------------------------------------------------------------------------------------- smoke --
# Smoke column (an original volumetric example of the engine, 2026-07-05): a rising, widening plume. Density = a
# radial column profile (radius grows with height) gated by two upward-advected fbm fields (one fine, one slow
# billow), faded in at the base and dissipating at the top. Grey-blue, darker at the base. Knobs: uSpeed, uDensity.
_SMOKE_SAMPLE = r"""
SdfSample sample(vec3 p) {
    float t = uTime * uSpeed;
    float h = clamp(p.y / 2.4, 0.0, 1.0);
    // column profile: radius widens with height, soft wall
    float rad = h * 0.5 + 0.14;
    float core = 1.0 - smoothstep(rad * 0.35, rad, length(p.xz));
    // two advected turbulence fields (scroll down = smoke rises)
    float fine = fbm(p * 3.2 + vec3(0.0, -0.95, 0.0) * t);
    float billow = fbm(p * 1.4 + vec3(0.22, -0.6, 0.0) * t + 7.3);
    float dens = core * smoothstep(0.28, 0.74, fine * 0.65 + billow * 0.55);
    // fade in at the base, dissipate at the top
    dens = dens * smoothstep(0.0, 0.18, p.y) * (1.0 - smoothstep(1.8, 2.55, p.y));
    // grey-blue, darker at the base, faint warm lift where dense
    vec3 col = mix(vec3(0.16, 0.16, 0.17), vec3(0.52, 0.54, 0.58), h) + dens * 0.05;
    return sdfSample(col, dens * 0.09 * uDensity, 0.05);
}"""

# --------------------------------------------------------------------------------------------- gyroid_fireball --
# Gyroid fireball (the engine's TSL port, 2026-07-23, of a compact cellular-explosion shader): the gyroid fbm
# "spice" (8 octaves, lacunarity 1.7, running-sum z warp), the lifecycle curves (growth pow .2 / fade pow 9 / burn
# pow .4 / advance pow .4), the cos(vec3(1, 2, 3) * 5.5 + n.y) palette on the field gradient, the burn-to-smoke blend
# and radius = .3 * noise * growth with the .05 feather. The source's screen-space cell grid and blue-noise dither
# were 2D tricks the engine dropped; uSeed stands in for the per-cell id. Loops ~3 s / uSpeed: ignition -> fireball
# -> smoke puff -> gone. Knobs: uSpeed, uSeed, uDensity.
_GYROID_EXTRA = r"""
float gyroid(vec3 p) { return dot(cos(p), sin(p.yzx)); }
// the source fbm verbatim: 8 octaves, a /= 1.7, z warped by the running sum
float gyroidFbm(vec3 p) {
    float result = 0.0;
    vec3 q = p;
    float a = 0.5;
    for (int i = 0; i < 8; i++) {
        q = vec3(q.x, q.y, q.z + result * 0.1);
        result += abs(gyroid(q / a) * a);
        a /= 1.7;
    }
    return result;
}
struct GyroidAnim { float cycle; float growth; float fade; float burn; float advance; };
GyroidAnim gyroidAnim() {
    float timeline = uTime * uSpeed / 3.0 + uSeed;
    float ax = fract(timeline);
    GyroidAnim A;
    A.cycle = floor(timeline);
    A.growth = pow(ax, 0.2);
    A.fade = 1.0 - pow(ax, 9.0);
    A.burn = 1.0 - pow(ax, 0.4);
    A.advance = pow(ax, 0.4);
    return A;
}
"""

_GYROID_SAMPLE = r"""
SdfSample sample(vec3 p) {
    GyroidAnim A = gyroidAnim();
    // the field is sampled in FULL 3D at every point (a direction-only field flattens into a shaded balloon); the z
    // advance pushes fresh noise through the volume per cycle, like the source's ray.z advance
    float drift = A.advance * 2.0 + A.cycle * 7.77 + uSeed * 196.128;
    vec3 q = vec3(p.x * 3.1, p.y * 3.1, p.z * 3.1 + drift);
    float noise = gyroidFbm(q);
    // silhouette: direction-noise radius (the blobby outline), grown
    float r = max(length(p), 1e-4);
    vec3 nd = p / r;
    float outline = gyroidFbm(vec3(nd.x, nd.y, nd.z + drift));
    float radius = min(outline * 0.3 * A.growth, 0.62);
    float shell = 1.0 - smoothstep(0.0, 0.06, r - radius);
    // interior filaments: the 3D field thresholded, so the inside has structure and gaps
    float fil = smoothstep(0.35, 0.95, noise);
    float dens = shell * (fil * 0.75 + 0.25);
    // 3D field gradient -> shading normal (the source's e-offset trick)
    const float e = 0.14;
    float nx = gyroidFbm(q + vec3(e, 0.0, 0.0));
    float ny = gyroidFbm(q + vec3(0.0, e, 0.0));
    vec3 nrm = normalize(vec3(noise - nx, noise - ny, noise - 1.0));
    // palette + burn-to-smoke blend (source constants); the hot phase is pushed past 1.0 so the core blooms
    vec3 col = cos(vec3(5.5, 11.0, 16.5) + nrm.y) + 0.2;
    col = col * (A.burn * 1.6 + 0.8);
    float smokeK = noise - A.burn * 2.0;
    float shade = nrm.y * 0.5 + 0.5;
    col = mix(col, vec3(max(smokeK * shade * 0.55, 0.0)), smoothstep(0.0, 0.1, smokeK));
    col = max(col, vec3(0.0));
    float alpha = dens * A.fade * 0.30 * uDensity;
    // two-speed: stride the empty space, resolve the shell + interior
    float stp = (r - radius) > 0.14 ? 0.05 : 0.016;
    return sdfSample(col, alpha, stp);
}"""

# ----------------------------------------------------------------------------------------------------- bonfire --
# Bonfire (the engine's v3, 2026-07-23): the fire is a teardrop ENVELOPE x the ring's cascading vnoise stack advected
# upward fast, thresholded (the flame shapes come from 3D noise, not from any primitive), with a whole-body sway and
# width pulse; plus a noise-gated broken smoke plume on a wind-bent axis that dissipates mid-box. Base at y = 0.
# Knobs: uSpeed, uDensity.
_FIRE_PARTS_STRUCT = r"""
// the fire and smoke parts of one point (sample() mixes them as the engine did; the lit form keeps them apart)
struct FireParts { float fdens; float sdens; vec3 fireCol; vec3 smokeCol; float fireAlpha; float smokeAlpha;
                   float stp; };
"""

_BONFIRE_EXTRA = _FIRE_PARTS_STRUCT + r"""
FireParts bonfireParts(vec3 p) {
    float t = uTime * uSpeed;
    FireParts F;
    // ---- fire: the teardrop envelope x the cascading vnoise stack advected upward, thresholded ----
    vec3 rise = vec3(0.0, t * 2.6, 0.0);
    vec3 sp = p - rise;
    float nf = vnoise(sp * 3.0) * 0.8;
    nf += vnoise(sp * 8.5) * 0.4;
    nf += vnoise(sp * 15.0) * 0.2;
    nf += vnoise(sp * 38.0) * 0.45 * nf;
    float hy = clamp(p.y / 1.15, 0.0, 1.0);
    // whole-body sway + width pulse: the envelope axis BENDS with a height-growing low-frequency wander and the
    // radius breathes
    float swx = (vnoise(vec3(t * 0.9, p.y * 1.4, 0.0)) - 0.5) * hy * hy * 0.60;
    float swz = (vnoise(vec3(7.0, p.y * 1.4, t * 0.7)) - 0.5) * hy * hy * 0.44;
    float pulse = (vnoise(vec3(t * 1.6, p.y * 2.2, 3.0)) - 0.5) * 0.36 + 1.0;
    float rEnv = (0.34 * pow(1.0 - hy, 0.75) + 0.04) * pulse;
    float env = (1.0 - smoothstep(rEnv * 0.5, rEnv + 0.10, length(vec2(p.x - swx, p.z - swz))))
              * smoothstep(-0.02, 0.08, p.y) * (1.0 - smoothstep(0.85, 1.2, p.y));
    F.fdens = clamp((env * nf - 0.43) / 0.45, 0.0, 1.0);
    float c1 = clamp(F.fdens * (1.8 - p.y * 1.1), 0.0, 1.0);
    // torch palette: orange base -> yellow -> white-hot core; the noise modulates the interior
    F.fireCol = vec3(c1 * 1.8, c1 * c1 * c1 * 1.8, c1 * c1 * c1 * c1 * c1 * c1 * 1.4) * (nf * 0.42 + 0.62);
    // ---- broken smoke: noise-gated puffs on a wind-bent axis, dissipated by y ~ 2.1 ----
    float h01 = clamp((p.y - 0.55) / 1.45, 0.0, 1.0);
    float cx = h01 * h01 * 0.22 + sin(t * 0.6 + p.y * 1.3) * h01 * 0.05;
    float cz = h01 * 0.1 * cos(t * 0.45);
    float rr = length(vec2(p.x - cx, p.z - cz));
    float prof = 1.0 - smoothstep(h01 * 0.34 + 0.06, h01 * 0.5 + 0.14, rr);
    float bil = fbm(p * 1.8 + vec3(0.16, -0.8, 0.03) * t);
    float fin = fbm(p * 4.4 + vec3(0.0, -1.5, 0.1) * t + 9.1);
    float gate = smoothstep(0.55, 0.80, bil * 0.65 + fin * 0.48);
    F.sdens = prof * gate * smoothstep(0.50, 0.95, p.y) * (1.0 - smoothstep(1.55, 2.10, p.y))
            // fade before the bounds walls: the box must never slice smoke
            * (1.0 - smoothstep(0.58, 0.85, length(p.xz)));
    float ember = 1.0 - smoothstep(0.6, 1.15, p.y);
    F.smokeCol = mix(vec3(0.10, 0.10, 0.105), vec3(0.38, 0.37, 0.365), h01) + vec3(0.42, 0.18, 0.05) * ember * 0.5;
    F.fireAlpha = F.fdens * 0.28 * uDensity;
    F.smokeAlpha = F.sdens * 0.05 * uDensity;
    float far = length(p.xz) - 0.78;
    F.stp = far > 0.1 ? 0.06 : 0.022;
    return F;
}
"""

# the engine's sample(): smoke and fire colours mixed by their share, one alpha
_PARTS_SAMPLE = r"""
SdfSample sample(vec3 p) {
    FireParts F = %(parts)s(p);
    float w = F.fdens / max(F.fdens + F.sdens, 0.001);
    vec3 col = mix(F.smokeCol, F.fireCol, w);
    return sdfSample(col, F.fireAlpha + F.smokeAlpha, F.stp);
}"""

# the lit form (look='lit'): the same two media kept apart, so the smoke scatters the scene's light (and the fire's,
# through light_from_emission's lamps) instead of glowing its hand-lit grey. Each part's opacity over the engine's
# stride converts as the engine contract does (density = -ln(1 - alpha) / step); the fire emits its colour per
# metre of its own density, the smoke's colour becomes its scattering colour. %(smoke_albedo)s maps the engine's
# lit-grey smoke colour to an albedo (a darker colour was a darker, sootier smoke).
_PARTS_MEDIUM = r"""
SdfMedium medium(vec3 p) {
    FireParts F = %(parts)s(p);
    float stp = max(F.stp, 1e-4);
    float sf = -log(1.0 - clamp(F.fireAlpha, 0.0, 0.9999)) / stp;
    float ss = -log(1.0 - clamp(F.smokeAlpha, 0.0, 0.9999)) / stp;
    float dens = sf + ss;
    vec3 albedo = dens > 1e-6 ? clamp(%(smoke_albedo)s, 0.0, 1.0) * (ss / dens) : vec3(0.0);
    return sdfMedium(dens, albedo, max(F.fireCol, vec3(0.0)) * sf);
}"""

# ------------------------------------------------------------------------------------------------ candle_flame --
# Candle flame (the engine's TSL port, 2026-07-23, of a raymarched candle's flame; the candle / table / plate scene of
# the source is not part of it): the teardrop SDF (a sphere in a vertically warped space, radius pinched with
# height), the HOLLOW BASE subtraction that makes the blue zone above the wick, the three-channel anchored sway noise
# (base pinned, tip flickers), the blue -> warm height palette and brightness from the SDF's interior depth; plus a
# delicate smoke thread off the tip. Base at y = 0; the flame ~0.16 m tall, the smoke to ~0.6 m: real candle scale.
# Knobs: uSpeed, uDensity.
_CANDLE_EXTRA = r"""
// the source's getFlameMovement: three low-frequency noise channels at different speeds, dead-zone shaped,
// anchored at the base
vec3 candleSway(vec3 p, float t) {
    float n1 = (vnoise(p * 0.3 + vec3(0.4, 4.5, 0.5) * t) - 0.5) * 0.5;
    float n2 = (vnoise(p * 0.1 + vec3(0.5, 2.8, 0.3) * (t + 100.0)) - 0.5) * 0.4;
    float n3 = (vnoise(p * 0.3 + vec3(0.6, 3.2, 0.4) * (t + 200.0)) - 0.5) * 0.5;
    vec3 nf = vec3(n1, n2, n3);
    nf = sign(nf) * smoothstep(0.07, 1.0, abs(nf));
    return nf * 2.2 * smoothstep(-0.17, 0.25, p.y);
}
// the source's map_flame, in its own local units
float candleFlameDf(vec3 pl, float t) {
    vec3 fm = candleSway(pl, t);
    vec3 p2 = pl - fm;
    float hollow = length(p2 * vec3(1.0, 0.5, 1.0) + vec3(0.0, 0.04, 0.0)) - 0.04;    // hollow base (the blue zone)
    vec2 px = p2.xz * (p2.y * 1.7 + 1.0);                                         // taper
    float ya = max(abs(p2.y), 1e-4);
    float yw = p2.y / (0.6 + 1.8 / pow(ya, p2.y * 1.3 + 0.2));                    // the teardrop vertical warp
    float df = length(vec3(px.x, yw, px.y)) - 0.07;
    return max(df, -hollow);
}
FireParts candleParts(vec3 p) {
    float t = uTime * uSpeed * 0.37;
    FireParts F;
    // world -> the shader's flame-local frame (flame centred near 0, bottom at ~ -0.12): base at y = 0, ~0.16 tall
    const float S = 0.45;
    vec3 pl = vec3(p.x / S, p.y / S - 0.17, p.z / S);
    float df = candleFlameDf(pl, t);
    // brightness from interior depth (the source's density march)
    F.fdens = clamp((-df + 0.002) * 26.0, 0.0, 1.0);
    // blue at the hollow base -> warm body (the source's palette and heights)
    F.fireCol = mix(vec3(0.12, 0.08, 0.94), vec3(1.25, 0.9, 0.55) * 2.0, smoothstep(-0.16, -0.02, pl.y));
    // the smoke thread off the tip: thin gaussian round a swaying line, broken by rising noise, gone by y ~ 0.55
    float h = clamp((p.y - 0.17) / 0.38, 0.0, 1.0);
    vec3 sw = candleSway(vec3(0.0, p.y * 2.0, 0.0), t) * 0.045;
    float rr = length(vec2(p.x - sw.x - h * h * 0.03, p.z - sw.z));
    // tiny tapering billows: the thread widens into puffs, then disperses (`thread` is a reserved word of the
    // NVIDIA GLSL compiler, so the source's name is threadMask here)
    float threadW = (h * 0.052 + 0.006) * (1.0 - h * 0.4);
    float threadMask = 1.0 - smoothstep(threadW * 0.25, threadW, rr);
    vec3 spc = vec3(p.x, p.y - t * 1.4, p.z);
    float nSm = vnoise(spc * 14.0) * 0.8;
    nSm += vnoise(spc * 38.0) * 0.4;
    nSm += vnoise(spc * 90.0) * 0.45 * nSm;
    F.sdens = clamp((threadMask * nSm - 0.34) / 0.55, 0.0, 1.0) * smoothstep(0.16, 0.24, p.y)
            * (1.0 - smoothstep(0.42, 0.58, p.y));
    F.smokeCol = vec3(0.30, 0.30, 0.31);
    F.fireAlpha = F.fdens * 0.5 * uDensity;
    F.smokeAlpha = F.sdens * 0.028 * uDensity;
    // tiny volume: fine strides only where the flame / thread lives
    float nearD = min(df, rr - 0.05);
    F.stp = nearD > 0.08 ? 0.03 : 0.0055;
    return F;
}
"""

# -------------------------------------------------------------------------------------------------------- fire --
# Fire: a large roaring blaze (the engine's, 2026-07-23, from a tapered-box volumetric fire and a smoke-column
# shader). Body: the tapered-box FOOTPRINT as an envelope x a cascading vnoise stack advected upward, hard
# thresholded, a per-sample 3-channel wobble, the outer -> mid -> core palette driven by heat and modulated by the
# noise. Smoke: a hollow sin^4 shell column torn by height-growing ridged turbulence and swirl, dispersing by y ~ 4.9.
# Base at y = 0; fire ~2.4 m tall, smoke to ~5 m. Knobs: uSpeed, uDensity.
_FIRE_EXTRA = r"""
// the source's get_noise_value (a tiled 3D texture there): the engine's value noise
float fireNoise(vec3 p, float sf, float toff) { return vnoise(p * (sf * 2.2) + vec3(0.0, 1.0, 0.0) * toff); }
// the source's get_per_sample_wobble: three offset noise channels, centred
vec3 fireWobble(vec3 p, float strength, float freq, float tWob) {
    float wx = fireNoise(p + vec3(100.0, 0.0, 0.0), freq, tWob);
    float wy = fireNoise(p + vec3(0.0, 200.0, 0.0), freq, tWob * 1.2);
    float wz = fireNoise(p + vec3(0.0, 0.0, 300.0), freq, tWob * 0.8);
    return vec3(wx - 0.5, wy - 0.5, wz - 0.5) * strength;
}
FireParts fireParts(vec3 p) {
    float t = uTime * uSpeed;
    float tSdf = t * 0.54;       // source: TIME * 0.027 * 20
    float tWob = t * 0.162;      // source: TIME * 0.027 * 6
    FireParts F;
    const float H = 2.45, W = 2.25, TAPER = 0.425;
    vec3 lp = p - vec3(0.0, H * 0.5, 0.0);                  // box centred at H / 2
    float nh = clamp(p.y / H, 0.0, 1.0);
    // tapered box + advected-noise distortion (the flame body)
    float taper = max(1.0 - nh * TAPER, 0.01);
    vec3 tp = vec3(lp.x / taper, lp.y, lp.z / taper);
    float d = sdBox(tp, vec3(W * 0.5, H * 0.5, W * 0.5))
            + fireNoise(lp + fireWobble(lp, 2.0, 0.125, tWob), 0.225, tSdf) * 0.3;
    // density: the tapered FOOTPRINT envelope x the cascading vnoise stack advected upward fast, hard thresholded;
    // the y-compressed noise domain elongates the features VERTICALLY (licking tongues, not cauliflower)
    vec3 wobD = fireWobble(p, 1.4, 0.1375, tWob);
    vec3 sp2 = (p + wobD * 0.4 - vec3(0.0, t * 2.8, 0.0)) * vec3(1.0, 0.55, 1.0);
    float nf = vnoise(sp2 * 1.6) * 0.8;
    nf += vnoise(sp2 * 4.4) * 0.4;
    nf += vnoise(sp2 * 8.0) * 0.2;
    nf += vnoise(sp2 * 19.0) * 0.45 * nf;
    // whole-body sway + width pulse: break the static cone silhouette
    float swX = (vnoise(vec3(t * 0.7, p.y * 0.5, 1.0)) - 0.5) * nh * nh * 1.1;
    float swZ = (vnoise(vec3(4.0, p.y * 0.5, t * 0.55)) - 0.5) * nh * nh * 0.8;
    float pulseF = (vnoise(vec3(t * 1.2, p.y * 0.8, 9.0)) - 0.5) * 0.30 + 1.0;
    float rad = length(vec2(p.x - swX, p.z - swZ)) / (taper * W * 0.5) * (nh * 0.8 + 1.0) * pulseF;
    float env = (1.0 - smoothstep(0.30, 1.0, rad)) * smoothstep(-0.02, 0.15, p.y) * (1.0 - smoothstep(1.45, 2.45, p.y));
    F.fdens = clamp((env * nf - 0.43) / 0.45, 0.0, 1.0);
    // palette: the source's outer -> mid -> core stops driven by heat, noise-modulated
    float c1 = clamp(F.fdens * (1.55 - p.y * 0.45), 0.0, 1.0);
    vec3 col = mix(vec3(0.8, 0.01, 0.0), vec3(1.0, 0.625, 0.0), smoothstep(0.10, 0.60, c1));
    col = mix(col, vec3(1.0, 0.9, 0.5), smoothstep(0.80, 1.0, c1));
    F.fireCol = col * (nf * 0.42 + 0.62) * 2.0;
    // smoke: a hollow sin^4 shell displaced laterally by HEIGHT-GROWING ridged turbulence (coherent at the fire,
    // torn to shreds up high), with a height-growing swirl; curve-faded taper at the top
    float h2 = clamp((p.y - 2.0) / 2.8, 0.0, 1.0);
    float g = clamp((p.y - 1.9) * 0.55, 0.0, 2.0);
    float ang = (vnoise(p * 0.4 - vec3(0.0, t * 0.4, 0.0)) - 0.5) * g * 0.9;     // swirl: rotate xz by noise x g
    float ca = cos(ang), sa = sin(ang);
    float rx0 = p.x * ca - p.z * sa;
    float rz0 = p.x * sa + p.z * ca;
    // ridged 5-octave turbulence at the advected position (lacunarity 2.7)
    vec3 q = vec3(rx0, p.y - t * 1.1, rz0) * 0.55;
    float tX = 0.0, tZ = 0.0, oof = 1.0;
    for (int i = 0; i < 5; i++) {
        tX += abs(vnoise(q) * 2.0 - 1.0) * oof;
        tZ += abs(vnoise(q + 41.7) * 2.0 - 1.0) * oof;
        oof *= 0.5;
        q *= 2.7;
    }
    float dispX = (tX - 1.0) * g * 0.55;
    float dispZ = (tZ - 1.0) * g * 0.55;
    float sx = rx0 + dispX + g * 0.10;                     // the wind drift grows too
    float sz = rz0 + dispZ;
    // hollow shell: sin^4 of the normalised radial coordinate (|sin|^4, the same value: at rxn = 1, everywhere
    // outside the shell, float sin(pi) is -8.7e-8, and GLSL's pow of a negative base is undefined, NaN on some GPUs,
    // which would zero the whole sample, fire included, since 0 x NaN is NaN)
    float rxn = clamp((sx * sx + sz * sz) * 2.6 - (p.y - 2.0) * 0.16, 0.0, 1.0);
    float shell = pow(abs(sin(rxn * 3.141592653589793)), 4.0);
    F.sdens = shell * smoothstep(2.0, 2.7, p.y) * pow(1.0 - smoothstep(3.3, 4.9, p.y), 1.6)
            // fade before the bounds walls: the swirl-displaced column must never be sliced flat by the box
            * (1.0 - smoothstep(1.05, 1.42, length(p.xz)));
    F.smokeCol = mix(vec3(0.075, 0.072, 0.072), vec3(0.30, 0.29, 0.285), clamp(h2 + tX * 0.15, 0.0, 1.0))
               + vec3(0.5, 0.2, 0.04) * (1.0 - smoothstep(2.0, 2.9, p.y)) * 0.4;
    // alpha calibrated to the 0.045 fine stride (the bonfire's optical depth)
    F.fireAlpha = F.fdens * 0.33 * uDensity;
    F.smokeAlpha = F.sdens * 0.055 * uDensity;
    float far = min(d, length(lp.xz) - 1.15);
    F.stp = far > 0.25 ? 0.11 : 0.045;
    return F;
}
"""

# ------------------------------------------------------------------------------------------------ nuclear_blast --
# Nuclear blast (the engine's, 2026-07-23): the screen-space SDF mushroom-cloud raymarcher (effects_tsl/
# nuclear_explosion.js, see nuclear_explosion.py) reborn as a PLACED volume. Cap (squashed sphere, easeOut rise and
# swell) + stem (WIDER at top) + a trail bulge riding under the cap + the base-surge torus + a ground pad, all
# sminCubic-fused; noise sampled at ADVECTED positions (weighted cross-section rolls in the cap and the surge ring);
# density = SDF-depth falloff x a 4-octave cascade; late-loop SPATIAL dispersal (wisps dissolve first, the dense core
# last); heat = core-distance falloff cooling over the loop; a near-black smoke band under the fire ramp. uScale
# shrinks the original's ~100 m units into the placeable (the base surge is capped radially to stay in the bounds).
# Loops 20 s / uSpeed. Base at y = 0. Knobs: uSpeed, uHeat, uDensity, uScale (make(size=)).
_NUKE_COMMON = r"""
float nukeEaseOut(float t) { return 1.0 - pow(1.0 - t, 3.0); }
float nukeSminCubic(float a, float b, float k) {
    float h = max(k - abs(a - b), 0.0) / k;
    return min(a, b) - h * h * h * k / 6.0;
}
vec2 nukeRot2(vec2 v, float a) {
    float c = cos(a), s = sin(a);
    return vec2(v.x * c - v.y * s, v.x * s + v.y * c);
}
struct NukeAnim {
    float tnLoop; float tn; float capY; float capR; float stemTop; float stemBaseR; float stemTopR;
    float trailRise; float trailY; float trailR; float surgeR; float ringTube; float padH; float ringFade;
    float coolFactor;
};
// the original's timeline (tn = the first 60 % of the loop); surgeCap caps the base-surge radius (the placed
// example keeps it in its bounds; the effect lets it run to 20)
NukeAnim nukeAnim(float tnLoop, float surgeCap) {
    NukeAnim A;
    A.tnLoop = tnLoop;
    float tn = clamp(tnLoop / 0.6, 0.0, 1.0);
    A.tn = tn;
    A.capY = mix(1.0, 8.0, nukeEaseOut(clamp(tn / 0.55, 0.0, 1.0))) + tn;
    A.capR = mix(0.5, 4.6, nukeEaseOut(clamp(tn / 0.50, 0.0, 1.0))) + tn * 0.5;
    A.stemBaseR = mix(0.30, 1.1, nukeEaseOut(clamp(tn / 0.40, 0.0, 1.0)));
    A.stemTopR = mix(0.70, 2.2, nukeEaseOut(clamp(tn / 0.50, 0.0, 1.0)));
    A.stemTop = A.capY - 0.6;
    A.trailRise = clamp((tn - 0.10) / 0.5, 0.0, 1.0);
    A.trailY = mix(1.0, A.capY * 0.60, A.trailRise);
    A.trailR = mix(0.4, 2.4, A.trailRise);
    A.surgeR = min(mix(2.0, 16.0, nukeEaseOut(clamp(tn / 0.7, 0.0, 1.0))) + tn * 4.0, surgeCap);
    float ringPeak = smoothstep(0.0, 0.4, tn);
    A.ringFade = 1.0 - smoothstep(0.4, 1.0, tn);
    A.ringTube = mix(0.4, 2.2, ringPeak) * mix(0.15, 1.0, A.ringFade);
    A.padH = mix(0.6, 1.8, nukeEaseOut(clamp(tn / 0.5, 0.0, 1.0))) * mix(0.3, 1.0, A.ringFade);
    A.coolFactor = 1.0 - smoothstep(0.4, 0.85, tnLoop);
    return A;
}
// the unified mushroom SDF in ORIGINAL local units (the original mapScene)
float nukeMap(vec3 p, NukeAnim A) {
    vec3 qc = (p - vec3(0.0, A.capY, 0.0)) / vec3(1.0, 0.78, 1.0);
    float dCap = length(qc) - A.capR;
    float hS = clamp(p.y / max(A.stemTop, 0.001), 0.0, 1.0);
    float rS = mix(A.stemBaseR, A.stemTopR, pow(hS, 0.7));
    float dStem = max(length(p.xz) - rS, max(p.y - A.stemTop, -p.y));
    vec3 qt = (p - vec3(0.0, A.trailY, 0.0)) / vec3(1.3, 0.9, 1.3);
    float dTrail = length(qt) - A.trailR;
    float radial = length(p.xz) - A.surgeR;
    float dRing = length(vec2(radial, p.y - A.ringTube * 0.6)) - A.ringTube;
    float padR = A.surgeR - A.ringTube * 0.4;
    // (the original's reversed-edge smoothstep(padR, padR * 0.2, r), in the defined-order form)
    float heightAtR = A.padH * (1.0 - smoothstep(padR * 0.2, padR, length(p.xz)));
    float dPad = max(length(p.xz) - padR, max(p.y - heightAtR, -p.y));
    float dSurge = nukeSminCubic(dRing, dPad, 0.6);
    float dStemCap = nukeSminCubic(dStem, dCap, 0.6);
    float dTrailed = nukeSminCubic(dStemCap, dTrail, mix(0.2, 0.5, A.trailRise));
    return nukeSminCubic(dTrailed, dSurge, mix(0.3, 1.0, A.ringFade));
}
// the original's palette: a near-black smoke band under the fire ramp
vec3 nukeHeatToColor(float heat) {
    float smokeMix = clamp(heat / 0.08, 0.0, 1.0);
    vec3 smokeCol = mix(vec3(0.012), vec3(0.18, 0.16, 0.14), smokeMix);
    vec3 c = mix(vec3(0.0), vec3(1.0, 0.30, 0.0), clamp(heat * 12.0 - 1.0, 0.0, 1.0));
    c = mix(c, vec3(1.6, 1.0, 0.5), clamp(heat * 14.0 - 5.0, 0.0, 1.0));
    c = mix(c, vec3(2.5, 1.9, 1.2), clamp(heat * 30.0 - 18.0, 0.0, 1.0));
    return mix(c, smokeCol, step(heat, 0.08));
}
// the late-loop spatial dispersal: the density threshold rises in the mushroom region so wisps dissolve first
float nukeShape(float density0, vec3 p, NukeAnim A) {
    float radialDist = length(p.xz);
    float mushroomRegion = clamp(smoothstep(2.5, 5.0, p.y)
                                 + (1.0 - smoothstep(2.5, 6.0, radialDist)) * smoothstep(0.5, 2.5, p.y), 0.0, 1.0);
    float dispersal = smoothstep(0.75, 1.0, A.tnLoop) * mushroomRegion;
    float lowT = mix(0.3, 1.1, dispersal);
    return clamp((density0 - lowT) / 0.6, 0.0, 1.0);
}
float nukeCascade(vec3 sp) {
    float nb = vnoise(sp * 0.8) * 0.8;
    nb += vnoise(sp * 2.2) * 0.4;
    nb += vnoise(sp * 5.0) * 0.2;
    nb += vnoise(sp * 13.0) * 0.45 * nb;
    return nb;
}
"""

_NUKE_EXTRA = _NUKE_COMMON + r"""
// weighted cross-section rolls (the original's advection, If-free)
vec3 nukeAdvect(vec3 p, NukeAnim A) {
    float radialDist = max(length(p.xz), 1e-4);
    vec2 outward = p.xz / radialDist;
    float t = uTime;
    // base-surge roll
    float torusW = exp(abs(radialDist - A.surgeR) * -0.4) * exp(abs(p.y - 1.0) * -0.4)
                 * smoothstep(0.35, 0.6, radialDist);
    vec2 cr1 = nukeRot2(vec2(radialDist - A.surgeR, p.y - 1.0), t * 0.25);
    vec2 xz1 = outward * (cr1.x + A.surgeR);
    vec3 torusPos = vec3(xz1.x, cr1.y + 1.0, xz1.y);
    // cap roll round the cap's vortex ring
    float capW = exp(abs(p.y - A.capY) * -0.18) * exp(max(radialDist - A.capR, 0.0) * -0.3)
               * smoothstep(0.15, 0.35, radialDist);
    float tubeR = A.capR * 0.65;
    vec2 cr2 = nukeRot2(vec2(radialDist - tubeR, p.y - A.capY), t * 0.35);
    vec2 xz2 = outward * (cr2.x + tubeR);
    vec3 capPos = vec3(xz2.x, cr2.y + A.capY, xz2.y);
    vec3 adv = mix(p, torusPos, torusW);
    adv = mix(adv, capPos, capW);
    return adv;
}
"""

_NUKE_SAMPLE = r"""
SdfSample sample(vec3 pw) {
    NukeAnim A = nukeAnim(fract(uTime * uSpeed / 20.0), 6.6);
    float S = uScale;
    vec3 p = pw / S;                       // original local units
    float d = nukeMap(p, A);
    // density: SDF-depth falloff x the original's 4-octave cascade at advected positions
    float falloff = clamp(d / -0.8, 0.0, 1.0);
    float density0 = falloff * nukeCascade(nukeAdvect(p, A));
    float dens = nukeShape(density0, p, A);
    // heat: core-distance falloff, cooling over the loop (the original)
    float coreDist = length(p - vec3(0.0, A.capY * 0.85, 0.0));
    float coreTerm = exp(coreDist * -0.18);
    float heat = clamp((dens * coreTerm + coreTerm * 0.6) * A.coolFactor * uHeat, 0.0, 1.0);
    vec3 col = nukeHeatToColor(heat);
    float alpha = dens * 0.20 * uDensity;
    // two-speed march: strides in ORIGINAL-local units scaled by uScale, so density per stride stays calibrated at
    // any size
    float stp = d > 0.5 ? 0.30 * S : 0.075 * S;
    return sdfSample(col, alpha, stp);
}"""


# ============================================================================================ example registry ====
def _uniform_opts(o, names, ex):
    """The engine's make(opts) knobs ({speed: 2} -> uSpeed = 2) taken out of o into the volume's own uniforms."""
    u = dict(ex.get('uniforms') or {})
    for key, name in names.items():
        for k in (key, name):
            if k in o:
                u[name] = float(o.pop(k))
    return u


class LiveUniforms:
    """vol.sdf_live_uniforms: the engine's vol.userData.sdfLiveUniforms (E._u), for one volume. live['uSpeed'] reads
    the value; live['uSpeed'] = 2.0 (or live['speed']) sets it for the next build / bake (a baked volume keeps the
    grids it baked: bake again, or key a knob per frame with bake(controls=lambda frame, t: {'uDensity': ...}))."""

    def __init__(self, vol, names):
        self._vol = vol
        self._names = list(names)

    def _name(self, k):
        return k if k in self._names else 'u' + k[:1].upper() + k[1:]

    def __getitem__(self, k):
        return self._vol.program.get_uniform(self._name(k))

    def __setitem__(self, k, v):
        self._vol.program.set_uniform(self._name(k), v)

    def keys(self):
        return list(self._names)

    def items(self):
        return [(k, self[k]) for k in self._names]

    def __repr__(self):
        return 'LiveUniforms(%s)' % ', '.join(f'{k}={self[k]!r}' for k in self._names)


# The grid box: where each example's medium can be over its whole loop (measured at 24 times on a coarse grid, then
# padded; tests/sdf_volumes/test_volume_examples.py checks no medium reaches a box face). The engine's boxes were
# raymarch boxes, loose, costing only march steps; a grid spends its voxels over the whole box, so the explosion
# ring (a 1.4 m ring in a 2.4 m box) gets 1.7x the resolution in each axis from its own box. make(fit=False) keeps
# the engine's box; examples whose medium fills theirs keep it.
GRID_BOUNDS = {
    'explosion_ring': {'min': [-0.72, -0.23, -0.72], 'max': [0.72, 0.26, 0.72]},
    'flame': {'min': [-0.34, 0.0, -0.34], 'max': [0.34, 1.2, 0.34]},
    'smoke': {'min': [-0.74, 0.0, -0.74], 'max': [0.74, 2.6, 0.74]},
    'gyroid_fireball': {'min': [-0.7, -0.7, -0.7], 'max': [0.7, 0.7, 0.7]},
    'bonfire': {'min': [-0.9, 0.0, -0.9], 'max': [0.9, 2.2, 0.9]},
    'candle_flame': {'min': [-0.1, 0.0, -0.1], 'max': [0.1, 0.6, 0.1]},
    'fire': {'min': [-1.5, 0.0, -1.5], 'max': [1.5, 4.95, 1.5]},
}


def _maker(knobs, lit=None, bounds_fn=None):
    """The example's make(opts): knobs {engine option: uniform}; lit = the GLSL medium of its look='lit' form;
    bounds_fn(o) -> bounds the engine's make() set from its options (nuclearBlast's size)."""
    def make(ex, opts=None, **kw):
        from .volume import create_sdf_volume
        o = dict(opts or {}, **kw)
        look = o.pop('look', 'engine')
        fit = o.pop('fit', True)
        if look not in ('engine', 'lit'):
            raise ValueError(f"{ex.name}.make: look is 'engine' (the engine's colours, glowing) or 'lit' (fire "
                             f"emits, smoke scatters the scene's light), not {look!r}")
        u = _uniform_opts(o, knobs, ex)
        spec = dict(ex)
        if fit and ex.name in GRID_BOUNDS:
            spec['bounds'] = GRID_BOUNDS[ex.name]
        if bounds_fn is not None:
            spec['bounds'] = bounds_fn(u)
        if look == 'lit':
            if lit is None:
                raise ValueError(f"{ex.name}.make: look='lit' is for the examples that carry both fire and smoke "
                                 f"(bonfire, candle_flame, fire, nuclear_blast); {ex.name} has one medium: pass "
                                 f"sample_as='albedo' to light it")
            spec['medium'] = lit
            spec['sample'] = None
        build = o.pop('build', True)
        vol = create_sdf_volume(spec, uniforms=u, build=False, **o)
        vol.example = ex.name
        vol.look = look
        vol.sdf_live_uniforms = LiveUniforms(vol, sorted(set(knobs.values())))
        if build:
            vol.build()
        return vol
    return make


# the explosion ring's post(sum), folded (fit=1 of test_volume_examples.py prints these)
RING_POST_FOLD = {'gamma': 1.75, 'density_scale': 2.1, 'emission_scale': 3.0}


def _parts(name, smoke_albedo='F.smokeCol'):
    return (_PARTS_SAMPLE % {'parts': name},
            _PARTS_MEDIUM % {'parts': name, 'smoke_albedo': smoke_albedo})


register_example(
    'explosion_ring', kind='volume', animated=True, make=_maker({'speed': 'uSpeed'}),
    description='expanding smoke-ring detonation: a torus easing outward over a 4.5 s loop, the smoke rolling round '
                'the tube, heat cooling to grey',
    bounds={'min': [-1.2, -0.25, -1.2], 'max': [1.2, 1.0, 1.2]}, steps=320,
    uniforms={'uSpeed': 1.0, 'uFoldGamma': RING_POST_FOLD['gamma']}, extra=_RING_EXTRA, sample=_RING_SAMPLE,
    post=_RING_POST,
    # post(sum) reshaped the engine's composited pixel (a contrast curve on colour and alpha); a physical volume has
    # no composited pixel, so the curve is folded into the medium: each sample's density to a power (thin wisps
    # fade, the core holds), then denser and brighter (fitted against the reference march with post over the loop:
    # tests/sdf_volumes/test_volume_examples.py fit=1)
    material_settings={'density_scale': RING_POST_FOLD['density_scale'],
                       'emission_scale': RING_POST_FOLD['emission_scale']},
)

register_example(
    'flame', kind='volume', animated=True, make=_maker({'strength': 'uStrength', 'speed': 'uSpeed'}),
    description='torch flame: the 2D simplex-fbm flame revolved round y, orange base to white-hot core',
    bounds={'min': [-0.65, 0.0, -0.65], 'max': [0.65, 1.45, 0.65]}, steps=56,
    uniforms={'uStrength': 3.0, 'uSpeed': 1.0}, extra=_FLAME_EXTRA, sample=_FLAME_SAMPLE,
)

register_example(
    'smoke', kind='volume', animated=True, make=_maker({'speed': 'uSpeed', 'density': 'uDensity'}),
    description='rising, widening grey-blue smoke plume',
    bounds={'min': [-0.95, 0.0, -0.95], 'max': [0.95, 2.6, 0.95]}, steps=80,
    uniforms={'uSpeed': 1.0, 'uDensity': 1.0}, sample=_SMOKE_SAMPLE,
)

register_example(
    'gyroid_fireball', kind='volume', animated=True,
    make=_maker({'speed': 'uSpeed', 'seed': 'uSeed', 'density': 'uDensity'}),
    description='cellular gyroid fireball: ignition, fireball, smoke puff, gone, on a 3 s loop',
    bounds={'min': [-0.75, -0.75, -0.75], 'max': [0.75, 0.75, 0.75]}, steps=56,
    uniforms={'uSpeed': 1.0, 'uSeed': 0.0, 'uDensity': 1.0}, extra=_GYROID_EXTRA, sample=_GYROID_SAMPLE,
)

# look='lit': the engine's smoke greys were lit appearances; as albedos they are lifted so the brightest smoke of
# each example scatters ~0.75 of the light (the bonfire's top 0.38 -> x 2), keeping the engine's gradient
_BONFIRE_SAMPLE, _BONFIRE_MEDIUM = _parts('bonfireParts', 'F.smokeCol * 2.0')
register_example(
    'bonfire', kind='volume', animated=True, make=_maker({'speed': 'uSpeed', 'density': 'uDensity'},
                                                         lit=_BONFIRE_MEDIUM),
    description='bonfire: noise-shaped flames in a swaying teardrop envelope, broken smoke on a wind-bent axis',
    bounds={'min': [-0.9, 0.0, -0.9], 'max': [0.9, 2.8, 0.9]}, steps=92,
    uniforms={'uSpeed': 1.0, 'uDensity': 1.0}, extra=_BONFIRE_EXTRA, sample=_BONFIRE_SAMPLE,
)

_CANDLE_SAMPLE, _CANDLE_MEDIUM = _parts('candleParts', 'F.smokeCol * 2.5')
register_example(
    'candle_flame', kind='volume', animated=True, make=_maker({'speed': 'uSpeed', 'density': 'uDensity'},
                                                              lit=_CANDLE_MEDIUM),
    description='candle flame at real size: blue hollow base, warm teardrop, a thin smoke thread',
    bounds={'min': [-0.16, 0.0, -0.16], 'max': [0.16, 0.62, 0.16]}, steps=56,
    uniforms={'uSpeed': 1.0, 'uDensity': 1.0}, extra=_FIRE_PARTS_STRUCT + _CANDLE_EXTRA, sample=_CANDLE_SAMPLE,
)

_FIRE_SAMPLE, _FIRE_MEDIUM = _parts('fireParts', 'F.smokeCol * 2.5')
register_example(
    'fire', kind='volume', animated=True, make=_maker({'speed': 'uSpeed', 'density': 'uDensity'}, lit=_FIRE_MEDIUM),
    description='large roaring blaze: licking tongues over a tapered footprint, a hollow torn smoke column to 5 m',
    bounds={'min': [-1.5, 0.0, -1.5], 'max': [1.5, 5.1, 1.5]}, steps=130,
    uniforms={'uSpeed': 1.0, 'uDensity': 1.0}, extra=_FIRE_PARTS_STRUCT + _FIRE_EXTRA, sample=_FIRE_SAMPLE,
)

NUCLEAR_BLAST_SCALE = 1.4


def _nuke_bounds(u):
    """The engine's make(): bounds from the size (7.45 x 13.65 original units, scaled)."""
    s = float(u.get('uScale', NUCLEAR_BLAST_SCALE))
    return {'min': [-7.45 * s, 0.0, -7.45 * s], 'max': [7.45 * s, 13.65 * s, 7.45 * s]}


# the nuclear blast's fire and smoke apart (look='lit'): the fire band emits, the smoke band scatters
_NUKE_PARTS = r"""
FireParts nukeParts(vec3 pw) {
    NukeAnim A = nukeAnim(fract(uTime * uSpeed / 20.0), 6.6);
    float S = uScale;
    vec3 p = pw / S;
    float d = nukeMap(p, A);
    float falloff = clamp(d / -0.8, 0.0, 1.0);
    float dens = nukeShape(falloff * nukeCascade(nukeAdvect(p, A)), p, A);
    float coreDist = length(p - vec3(0.0, A.capY * 0.85, 0.0));
    float coreTerm = exp(coreDist * -0.18);
    float heat = clamp((dens * coreTerm + coreTerm * 0.6) * A.coolFactor * uHeat, 0.0, 1.0);
    FireParts F;
    float fire = 1.0 - step(heat, 0.08);          // the palette's fire band (heat > 0.08; smoke at or under it)
    vec3 col = nukeHeatToColor(heat);
    F.fdens = dens * fire;
    F.sdens = dens * (1.0 - fire);
    F.fireCol = col;
    F.smokeCol = col;
    F.fireAlpha = F.fdens * 0.20 * uDensity;
    F.smokeAlpha = F.sdens * 0.20 * uDensity;
    F.stp = d > 0.5 ? 0.30 * S : 0.075 * S;
    return F;
}
"""
# the smoke band's colours (0.012 .. 0.18 grey-brown, hand-lit under the fire) are too dark for an albedo (tripled,
# the cooled cloud still read as black soot under the moon): the lit cloud is dust in the band's hue, its albedo
# 0.3 where the band was darkest to 0.6 where it was lightest
_NUKE_MEDIUM = _PARTS_MEDIUM % {
    'parts': 'nukeParts',
    'smoke_albedo': 'vec3(1.0, 0.89, 0.78) * mix(0.3, 0.6, clamp((F.smokeCol.r - 0.012) / 0.168, 0.0, 1.0))'}

register_example(
    'nuclear_blast', kind='volume', animated=True,
    make=_maker({'speed': 'uSpeed', 'heat': 'uHeat', 'density': 'uDensity', 'size': 'uScale'}, lit=_NUKE_MEDIUM,
                bounds_fn=_nuke_bounds),
    description='mushroom cloud: cap, stem, trail, base surge and pad, rolling noise, cooling heat and late '
                'dispersal on a 20 s loop; 19 m tall at the default size 1.4 (make(size=))',
    bounds=_nuke_bounds({}), steps=300,
    uniforms={'uSpeed': 1.0, 'uHeat': 1.0, 'uDensity': 1.0, 'uScale': NUCLEAR_BLAST_SCALE},
    extra=_FIRE_PARTS_STRUCT + _NUKE_EXTRA + _NUKE_PARTS, sample=_NUKE_SAMPLE,
)

# the engine's camelCase names of the examples (EXAMPLES.explosionRing -> EXAMPLES['explosion_ring'])
ENGINE_NAMES = {'explosionRing': 'explosion_ring', 'flame': 'flame', 'smoke': 'smoke',
                'gyroidFireball': 'gyroid_fireball', 'bonfire': 'bonfire', 'candleFlame': 'candle_flame',
                'fire': 'fire', 'nuclearBlast': 'nuclear_blast'}
VOLUME_EXAMPLES = tuple(ENGINE_NAMES.values())


# ============================================================================================ light on the scene ====
def _read_grid(path, name, dims):
    """One grid of a written frame as a dense numpy array [x][y][z] (Blender local axes), or None."""
    import openvdb as vdb
    try:
        g = vdb.read(path, name)
    except Exception:  # noqa: BLE001 - a frame without that grid
        return None
    shape = tuple(int(x) for x in dims)
    if isinstance(g, vdb.Vec3SGrid):
        a = np.zeros(shape + (3,), np.float32)
    else:
        a = np.zeros(shape, np.float32)
    g.copyToArray(a, ijk=(0, 0, 0))
    return a


def escape_transmittance(density, voxel):
    """Each voxel's mean transmittance to the box along the six axis directions (+x, -x, +y, -y, +z, -z): how much
    of the light it emits leaves the volume, the volume's own self-shadowing of its emission."""
    acc = np.zeros(density.shape, np.float64)
    for ax in range(3):
        c = np.cumsum(density, axis=ax, dtype=np.float64) * voxel
        tot = np.take(c, [-1], axis=ax)
        own = density.astype(np.float64) * voxel
        before = c - own                       # optical depth from the low face to the voxel's near side
        after = tot - c                        # ... and from its far side to the high face
        half = 0.5 * own                       # the voxel's own half-thickness
        acc += np.exp(-(before + half)) + np.exp(-(after + half))
    return (acc / 6.0).astype(np.float32)


def emission_stats(density, emission, voxel, lo, scale=(1.0, 1.0, 1.0), count=1, centres=None, seed=0):
    """The light a frame's grids send out: escaping power (RGB, watts, Blender's light units: 4 pi x radiance per
    metre x volume x escape transmittance), split over `count` clusters (k-means on the escaping emission, started
    from `centres` so a keyed light follows its own lobe). Returns [{'power', 'centre' (local), 'radius' (local
    RMS spread)}], biggest first, and the centres (for the next frame)."""
    s = np.asarray(scale, np.float64)
    vox_world = voxel * s
    dv = float(np.prod(vox_world))
    # the escape transmittance in world units: each axis' optical depth scales with that axis' scale
    dens = density.astype(np.float32)
    if np.allclose(s, s[0]):
        esc = escape_transmittance(dens, voxel * s[0])
    else:
        esc = escape_transmittance(dens, voxel * float(np.cbrt(np.prod(s))))
    lum = emission @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    w = lum * esc
    total = float(w.sum())
    if total <= 0.0:
        return [], centres
    idx = np.nonzero(w > total * 1e-7)
    ww = w[idx].astype(np.float64)
    pts = (np.stack(idx, -1).astype(np.float64) + 0.5) * voxel + lo
    erg = emission[idx].astype(np.float64) * esc[idx][:, None] * (4.0 * math.pi * dv)
    return _cluster_lights(pts, ww, erg, count, centres, seed, voxel)


def _cluster_lights(pts, ww, power, count=1, centres=None, seed=0, floor_radius=0.0):
    """Split emitters (points (N, 3), weights (N,), power (N, 3) watts) over `count` k-means lobes started from
    `centres` (so a keyed light follows its own lobe from frame to frame): [{'power', 'centre', 'radius', 'share'}]
    and the centres."""
    total = float(ww.sum())
    k = max(1, int(count))
    if k == 1 or len(ww) < 8 * k:
        labels = np.zeros(len(ww), np.int64)
        cen = [np.average(pts, axis=0, weights=ww)]
    else:
        rng = np.random.default_rng(seed)
        if centres is None or len(centres) != k:
            c0 = [pts[int(np.argmax(ww))]]
            for _ in range(1, k):            # k-means++ style, weighted by escaping light
                d2 = np.min([((pts - c) ** 2).sum(1) for c in c0], axis=0) * ww
                c0.append(pts[int(rng.choice(len(pts), p=d2 / d2.sum()))])
            cen = np.array(c0)
        else:
            cen = np.array(centres, np.float64)
        for _ in range(12):
            d2 = np.stack([((pts - c) ** 2).sum(1) for c in cen], 1)
            labels = np.argmin(d2, 1)
            for j in range(k):
                m = labels == j
                if m.any() and ww[m].sum() > 0:
                    cen[j] = np.average(pts[m], axis=0, weights=ww[m])
    out = []
    for j in range(len(cen)):
        m = labels == j
        if not m.any() or ww[m].sum() <= 0:
            out.append({'power': np.zeros(3), 'centre': np.array(cen[j]), 'radius': floor_radius, 'share': 0.0})
            continue
        c = np.average(pts[m], axis=0, weights=ww[m])
        r = float(np.sqrt(np.average(((pts[m] - c) ** 2).sum(1), weights=ww[m])))
        out.append({'power': power[m].sum(0), 'centre': c, 'radius': max(r, floor_radius),
                    'share': float(ww[m].sum() / max(total, 1e-30))})
    return out, [o['centre'] for o in out]


class EmissionLights:
    """What light_from_emission returns: .lights (point-light objects, parented to the volume), .frames {frame:
    [stats per light]}, .scale (the multiplier applied), remove()."""

    def __init__(self, vol, lights, frames, scale):
        self.volume = vol
        self.lights = lights
        self.frames = frames
        self.scale = scale

    def total_power(self, frame):
        return sum(float(np.max(s['power'])) for s in self.frames.get(frame, []))

    def remove(self):
        import bpy
        for lo in self.lights:
            ld = lo.data
            bpy.data.objects.remove(lo, do_unlink=True)
            if ld is not None and ld.users == 0:
                bpy.data.lights.remove(ld)
        self.lights = []
        coll = getattr(self, 'blocker_collection', None)
        if coll is not None:
            bpy.data.collections.remove(coll)
            self.blocker_collection = None


def _key(datablock, path, frame, index=-1):
    datablock.keyframe_insert(path, frame=frame, index=index)


def _linear(idblock):
    """Every key on the ID LINEAR (Blender 5.2's keyframe_insert ignores the interpolation preference from
    Python); the harness keys LINEAR by default too."""
    ad = getattr(idblock, 'animation_data', None)
    if ad is None or ad.action is None:
        return
    from bpy_extras import anim_utils
    try:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    except (AttributeError, TypeError, RuntimeError):
        cb = None
    for fc in (cb.fcurves if cb is not None else []):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


# lights per example: a ring or a spread-out cloud needs several lobes, or its one light sits in the empty middle
# (the explosion ring's hole) and over-lights the ground right under it
LIGHT_COUNT = {'explosion_ring': 4, 'nuclear_blast': 3, 'fire': 2}


def _replace_rig(owner, replace):
    """A second light_from_* call on one volume or solid replaces its lamps (two rigs would double its light)."""
    old = getattr(owner, 'emission_lights', None)
    if replace and old is not None and old.lights:
        old.remove()


def light_from_emission(vol, frames=None, count=None, energy_scale=1.0, radius_scale=0.6, min_radius=None,
                        shadows=True, specular=1.0, volume_factor=1.0, name=None, replace=True, log=print):
    """Keyed point lights that carry a baked SDF volume's emission onto the scene, which EEVEE's volume emission does
    not light. Per frame of `frames` (default: the frames vol.bake() wrote; a built still: its one file, unkeyed) it
    reads the frame's density and emission grids back, finds the light that escapes the medium (escape_transmittance)
    and its centroid, and keys `count` point lights there (default: LIGHT_COUNT for the example, else 1; several
    lights take k-means lobes of the escaping light): energy and colour (4 pi x the escaping emission x volume:
    the same watts as a Blender light), location (parented to the volume object, so they move with it) and radius
    (radius_scale x the emission's RMS spread, at least min_radius, a voxel by default). energy_scale multiplies the
    power. specular / volume_factor set the lights' specular and volume factors. Returns EmissionLights.

    A second call replaces the volume's lamps (replace=False keeps both rigs)."""
    import bpy
    _replace_rig(vol, replace)
    if frames is None:
        if 'baked' in vol.grid_info:
            fs, fe = vol.grid_info['baked']
            frames = range(fs, fe + 1)
        else:
            frames = [None]
    if count is None:
        count = LIGHT_COUNT.get(getattr(vol, 'example', None), 1)
    ob = vol.object
    scale = tuple(float(x) for x in ob.matrix_world.to_scale())

    def frame_stats(f, n, centres):
        # a still: the file the Volume shows (build() or build_still()); a baked frame: its own file
        path = (bpy.path.abspath(ob.data.filepath) if f is None
                else os.path.join(vol.cache_dir, f'{vol.stem}_{f:04d}.vdb'))
        dens = _read_grid(path, 'density', vol.dims)
        emis = _read_grid(path, 'emission', vol.dims)
        if dens is None or emis is None:
            raise FileNotFoundError(f'light_from_emission: {path} has no density / emission grid (bake first)')
        dens = dens * float(_material_setting(vol, 'density_scale'))
        emis = emis * float(_material_setting(vol, 'emission_scale'))
        return emission_stats(dens, emis, vol.voxel, vol.lo, scale, n, centres)

    rig = _keyed_lights(vol, ob, list(frames), frame_stats, count, energy_scale, radius_scale,
                        vol.voxel if min_radius is None else min_radius, shadows, specular, volume_factor,
                        name or ob.name + '_glow', log, 'its emission')
    vol.emission_lights = rig
    return rig


def _keyed_lights(owner, ob, frames, frame_stats, count, energy_scale, radius_scale, min_radius, shadows, specular,
                  volume_factor, name, log, what):
    """`count` point lights parented to `ob`, set (a still, frame None) or keyed per frame from frame_stats(frame,
    count, previous centres) -> ([{'power', 'centre' (ob-local), 'radius'}], centres)."""
    import bpy
    sc = bpy.context.scene
    lights = []
    for j in range(max(1, int(count))):
        ld = bpy.data.lights.new(f'{name}_{j}', 'POINT')
        ld.use_shadow = bool(shadows)
        ld.specular_factor = float(specular)
        ld.volume_factor = float(volume_factor)
        ld.use_custom_distance = True
        lo = bpy.data.objects.new(f'{name}_{j}', ld)
        (ob.users_collection[0] if ob.users_collection else sc.collection).objects.link(lo)
        lo.parent = ob
        lights.append(lo)
    stats = {}
    centres = None
    pmax = 0.0
    for f in frames:
        st, centres = frame_stats(f, len(lights), centres)
        st = sorted(st, key=lambda s: -float(np.max(s['power']))) if f is None else st
        stats[f] = st
        for j, lo in enumerate(lights):
            ld = lo.data
            s = st[j] if j < len(st) else {'power': np.zeros(3), 'centre': np.zeros(3), 'radius': min_radius}
            p = np.asarray(s['power'], np.float64) * float(energy_scale)
            e = float(p.max())
            col = (p / e) if e > 0 else np.ones(3)
            ld.energy = e
            ld.color = tuple(float(c) for c in col)
            ld.shadow_soft_size = float(max(min_radius, radius_scale * s['radius']))
            lo.location = tuple(float(c) for c in s['centre'])
            pmax = max(pmax, e)
            if f is not None:
                _key(ld, 'energy', f)
                _key(ld, 'color', f)
                _key(ld, 'shadow_soft_size', f)
                _key(lo, 'location', f)
    # the scene's light threshold culls a light where its influence falls under it; a custom cutoff where a light
    # of the frames' largest power has faded to ~1e-4 W / m^2 keeps the glow on distant surfaces
    cutoff = float(max(10.0, math.sqrt(max(pmax, 1e-9) / (4.0 * math.pi * 1e-4))))
    for lo in lights:
        lo.data.cutoff_distance = cutoff
        _linear(lo.data)
        _linear(lo)
    rig = EmissionLights(owner, lights, stats, energy_scale)
    if log:
        f0 = frames[len(frames) // 2]
        tot = sum(float(np.max(s['power'])) for s in stats[f0]) * energy_scale
        log(f'[sdf] {ob.name}: {len(lights)} light(s) from {what} over {len(frames)} frame(s); '
            f'{tot:.3g} W at frame {f0}, cutoff {cutoff:.0f} m')
    return rig


def escape_fraction(sdf, points3, normals3, rays=16, steps=48, seed=3):
    """The share of a surface point's Lambertian emission that leaves the solid: `rays` cosine-weighted directions
    round each normal, sphere-traced through the SDF (its own map at the program's uTime, at the spec's step scale)
    until they leave the bounds or hit the surface again. points3 / normals3: (N, 3) in the SDF's three frame.
    A folded emitter (the pyroclastic fireball) sends much of its light into its own folds."""
    prog = sdf.program
    sp = sdf.spec
    rng = np.random.default_rng(seed)
    n = len(points3)
    nrm = np.asarray(normals3, np.float64)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    # a tangent frame per point
    a = np.where(np.abs(nrm[:, :1]) < 0.9, np.array([[1.0, 0.0, 0.0]]), np.array([[0.0, 1.0, 0.0]]))
    tu = np.cross(nrm, a)
    tu /= np.maximum(np.linalg.norm(tu, axis=1, keepdims=True), 1e-12)
    tv = np.cross(nrm, tu)
    u1, u2 = rng.random((2, rays))
    r, phi = np.sqrt(u1), 2.0 * np.pi * u2                  # cosine-weighted hemisphere
    lx, ly, lz = r * np.cos(phi), r * np.sin(phi), np.sqrt(np.maximum(0.0, 1.0 - u1))
    dirs = (tu[:, None, :] * lx[None, :, None] + tv[:, None, :] * ly[None, :, None]
            + nrm[:, None, :] * lz[None, :, None]).reshape(-1, 3)
    lo, hi = np.array(sp.bounds_min), np.array(sp.bounds_max)
    eps = 0.5 * sdf.voxel
    org = (np.asarray(points3, np.float64)[:, None, :] + nrm[:, None, :] * (2.0 * sdf.voxel)).repeat(rays, 1)
    org = org.reshape(-1, 3)
    t = np.zeros(len(org))
    alive = np.ones(len(org), bool)
    hit = np.zeros(len(org), bool)
    k = float(sp.step_scale)
    for _ in range(int(steps)):
        idx = np.nonzero(alive)[0]
        if len(idx) == 0:
            break
        p = org[idx] + dirs[idx] * t[idx, None]
        d, _m = prog.dist(p.astype(np.float32))
        h = d < eps
        hit[idx[h]] = True
        out = np.any((p < lo) | (p > hi), axis=1)
        alive[idx[h | out]] = False
        t[idx] += np.maximum(d.astype(np.float64) * k, eps)
    return 1.0 - hit.reshape(n, rays).mean(1)


def light_from_surface(sdf, frames=None, count=1, energy_scale=1.0, radius_scale=0.6, min_radius=0.05,
                       shadows=True, specular=0.0, volume_factor=1.0, name=None, time_scale=1.0, time_offset=0.0,
                       escape_samples=4096, replace=True, log=print):
    """Keyed point lights for an emissive SDF SOLID (create_sdf_object; the pyroclastic `explosion`): EEVEE's ray
    tracing and fast GI gather an emissive mesh's light only from what is on screen, and a lit scene needs it off
    screen too. Per frame
    (default: the frames sdf.bake() wrote; a still: the mesh as it is) the evaluated mesh's faces are read, the
    SDF's own surface() gives each face's emitted radiance at its centre, and the power is pi x radiance x area (a
    Lambertian emitter) x the material's emission strength. The lights sit at the emitting surface's centroid,
    inside the solid: the solid is taken out of their shadows with shadow linking (its own surface would block
    them), so they light the scene as the glowing skin does. A folded skin sends much of its light into its own
    folds: each face's power is weighted by its escape fraction (escape_fraction: cosine-weighted rays traced
    through the SDF, on `escape_samples` faces). For a baked solid, time_scale / time_offset are the ones bake()
    used (the SDF is traced at each frame's time). The lights carry no specular by default: EEVEE's ray tracing
    already reflects the glowing mesh itself (a volume's lights keep theirs, since no volume is reflected).
    Returns EmissionLights (.escape: the last frame's mean escape fraction). A second call replaces the solid's
    lamps (replace=False keeps both rigs)."""
    import bpy
    _replace_rig(sdf, replace)
    ob = sdf.object
    baked = (getattr(sdf, 'stats', None) or {}).get('baked')
    if frames is None:
        frames = range(baked[0], baked[1] + 1) if baked else [None]
    strength = float((sdf.spec.material_settings or {}).get('emission_strength', 1.0))
    sc = bpy.context.scene
    keep = sc.frame_current
    s3 = np.asarray(ob.matrix_world.to_scale(), np.float64)

    def frame_stats(f, n, centres):
        if f is not None:
            sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        me = ob.evaluated_get(dg).to_mesh()
        try:
            np_ = len(me.polygons)
            if np_ == 0:
                return [], centres
            area = np.empty(np_, np.float32)
            cen = np.empty(np_ * 3, np.float32)
            fnm = np.empty(np_ * 3, np.float32)
            me.polygons.foreach_get('area', area)
            me.polygons.foreach_get('center', cen)
            me.polygons.foreach_get('normal', fnm)
            # a baked frame carries its surface channels per vertex (Import PLY -> 'sdf_emission'): the face's
            # emission is its corners' mean; a still (atlas textures) is evaluated from the SDF below
            em = None
            at = me.attributes.get('sdf_emission')
            if at is not None and at.domain == 'POINT':
                nv = len(me.vertices)
                if at.data_type == 'FLOAT_VECTOR':
                    ev = np.empty(nv * 3, np.float32)
                    at.data.foreach_get('vector', ev)
                    ev = ev.reshape(-1, 3)
                else:
                    ev = np.empty(nv * 4, np.float32)
                    at.data.foreach_get('color', ev)
                    ev = ev.reshape(-1, 4)[:, :3]
                lv = np.empty(len(me.loops), np.int32)
                me.loops.foreach_get('vertex_index', lv)
                ls = np.empty(np_, np.int32)
                lt = np.empty(np_, np.int32)
                me.polygons.foreach_get('loop_start', ls)
                me.polygons.foreach_get('loop_total', lt)
                em = np.add.reduceat(ev[lv].astype(np.float64), ls, axis=0) / lt[:, None]
        finally:
            ob.evaluated_get(dg).to_mesh_clear()
        cen = cen.reshape(-1, 3).astype(np.float64)
        fnm = fnm.reshape(-1, 3).astype(np.float64)
        # the SDF's local three frame: Blender local (x, y, z) -> three (x, z, -y)
        p3 = np.stack([cen[:, 0], cen[:, 2], -cen[:, 1]], -1)
        n3 = np.stack([fnm[:, 0], fnm[:, 2], -fnm[:, 1]], -1)
        if f is not None:
            # the SDF at this frame's time (bake()'s mapping: uTime = time_offset + time_scale (frame - start) / fps)
            fs0 = baked[0] if baked else sc.frame_start
            sdf.program.values['uTime'] = float(time_offset + time_scale * (f - fs0)
                                                / (sc.render.fps / sc.render.fps_base))
        if em is None:
            em = sdf.program.surface_eval(p3.astype(np.float32), project=1)['emission'].astype(np.float64)
        em = np.maximum(em, 0.0) * strength
        a_world = area.astype(np.float64) * float(np.prod(s3)) ** (2.0 / 3.0)
        power = math.pi * em * a_world[:, None]
        lum = power @ np.array([0.2126, 0.7152, 0.0722])
        keep_i = lum > max(float(lum.sum()), 1e-30) * 1e-8
        if not keep_i.any():
            return [], centres
        # what leaves the solid: each face's escape fraction, traced on a power-weighted sample of the faces and
        # carried to every face by its nearest sampled neighbour
        kept = np.nonzero(keep_i)[0]
        rng = np.random.default_rng(5)
        m = min(len(kept), int(escape_samples))
        pick = rng.choice(kept, size=m, replace=False, p=lum[kept] / lum[kept].sum()) if m < len(kept) else kept
        esc_s = escape_fraction(sdf, p3[pick], n3[pick])
        esc = np.empty(len(kept))
        cp = cen[pick]
        cp2 = (cp * cp).sum(1)
        for s0 in range(0, len(kept), 2048):
            blk = cen[kept[s0:s0 + 2048]]
            d2 = cp2[None, :] - 2.0 * blk @ cp.T            # |b - c|^2 up to |b|^2, enough for the argmin
            esc[s0:s0 + 2048] = esc_s[np.argmin(d2, 1)]
        frame_stats.escape = float(np.sum(lum[kept] * esc) / lum[kept].sum())
        pw = power[kept] * esc[:, None]
        return _cluster_lights(cen[kept], lum[kept] * esc, pw, n, centres, 0, min_radius)

    try:
        rig = _keyed_lights(sdf, ob, list(frames), frame_stats, count, energy_scale, radius_scale, min_radius,
                            shadows, specular, volume_factor, name or ob.name + '_glow', log, 'its emissive surface')
    finally:
        sc.frame_set(keep)
    # shadow linking: the solid does not block its own lights (they sit inside it)
    coll = bpy.data.collections.new(ob.name + '_not_blocking_glow')
    coll.objects.link(ob)
    for co in coll.collection_objects:             # (the solid is its only member)
        co.light_linking.link_state = 'EXCLUDE'
    for lo in rig.lights:
        lo.light_linking.blocker_collection = coll
    rig.blocker_collection = coll
    rig.escape = getattr(frame_stats, 'escape', None)
    sdf.emission_lights = rig
    return rig


def build_still(vol, t, log=None):
    """vol.build(t) into a file named for the time (<stem>_t<ms>.vdb). Blender keeps the grids it has loaded from
    a path, so a second build() of one volume, which rewrites <stem>.vdb, renders the first one's grids (measured:
    four stills at four times rendered as one); a file per time shows each. Returns vol."""
    base = vol.stem
    vol.stem = f'{base}_t{int(round(float(t) * 1000.0)):07d}'
    try:
        vol.build(float(t), log=log)
    finally:
        vol.stem = base
    return vol


def _material_setting(vol, key):
    from .volume import DEFAULT_VOLUME_SETTINGS
    return dict(DEFAULT_VOLUME_SETTINGS, **(vol.spec.material_settings or {})).get(key, 1.0)


# ============================================================================================ EEVEE's froxels ====
def _has_volume_material(ob):
    """True when one of the object's materials sends something into its output's Volume socket (a fog box, a smoke
    mesh): EEVEE renders it as a volume, inside the scene's one froxel range."""
    for slot in getattr(ob, 'material_slots', ()):
        m = slot.material
        if m is None or not m.use_nodes or m.node_tree is None:
            continue
        for n in m.node_tree.nodes:
            if n.type == 'OUTPUT_MATERIAL' and 'Volume' in n.inputs and n.inputs['Volume'].is_linked:
                return True
    return False


def _renders(ob):
    return not ob.hide_render and not any(c.hide_render for c in ob.users_collection)


def _world_volume(scene):
    w = scene.world
    if w is None or not w.use_nodes or w.node_tree is None:
        return False
    return any(n.type == 'OUTPUT_WORLD' and 'Volume' in n.inputs and n.inputs['Volume'].is_linked
               for n in w.node_tree.nodes)


def _marker_camera(scene, frame):
    """The camera Blender renders at `frame`: timeline markers with a camera switch it (the marker at or before the
    frame; before the first one, the left-most marker's camera), else scene.camera."""
    marks = sorted((m.frame, m.camera) for m in scene.timeline_markers if m.camera is not None and not m.camera.hide_render)
    if not marks:
        return scene.camera
    before = [c for f, c in marks if f <= frame]
    return before[-1] if before else marks[0][1]


def fit_volume_range(scene, camera=None, volumes=(), frames=None, tile_size='2', samples=128, distribution=0.8,
                     shadows=True, margin=0.25, others=True):
    """EEVEE's volume settings for SDF volumes over `frames`: the froxel depth range, the tile size, the slice
    distribution and volumetric shadows. EEVEE spreads its `samples` depth slices between the range's start and end,
    and a volume outside them does not render at all. The range is the scene's, so it clips EVERY volume, not only
    the ones fitted: it is fitted round the given volumes' boxes and, with others=True, round every other volume
    that renders (Volume objects and meshes with a volume material: a fog box, another fire, a second blast). A
    world volume fills the view, so it keeps the camera's whole clip range (or the custom range already set, if
    wider). camera: one camera; None follows the camera Blender renders each frame (scene.camera, switched by
    timeline markers: the range covers every cut); a list fits all of them. Blender cannot key the range, so it is
    the union over all the frames. Returns (start, end)."""
    import bpy
    from mathutils import Vector
    sc = scene or bpy.context.scene
    ee = sc.eevee
    ee.volumetric_tile_size = str(tile_size)
    ee.volumetric_samples = int(samples)
    ee.volumetric_sample_distribution = float(distribution)
    ee.use_volumetric_shadows = bool(shadows)
    boxes = []                                      # (object, local corners or None = its evaluated bound box)
    given = set()
    for v in volumes:
        ob = v.object if hasattr(v, 'object') else v
        given.add(ob.name)
        if hasattr(v, 'lo'):
            lo, hi = v.lo, v.hi
            boxes.append((ob, [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]))
        else:
            boxes.append((ob, None))
    extra = []
    if others:
        for ob in sc.objects:
            if ob.name in given or not _renders(ob):
                continue
            if ob.type == 'VOLUME' or (ob.type in ('MESH', 'CURVE', 'SURFACE', 'META') and _has_volume_material(ob)):
                boxes.append((ob, None))
                extra.append(ob.name)
    fr = list(frames) if frames is not None else list(range(sc.frame_start, sc.frame_end + 1))
    if isinstance(camera, (list, tuple)):
        cams_at = lambda f: list(camera)                                        # noqa: E731
    elif camera is not None:
        cams_at = lambda f: [camera]                                            # noqa: E731
    else:
        cams_at = lambda f: [c for c in [_marker_camera(sc, f)] if c is not None]  # noqa: E731
    if not boxes or not any(cams_at(f) for f in fr):
        return None
    keep = sc.frame_current
    dmin, dmax = 1e18, 0.0
    seen = {}
    for f in fr:
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for ob, corners in boxes:
            M = ob.matrix_world
            cs = corners if corners is not None else [tuple(c) for c in ob.evaluated_get(dg).bound_box]
            pts.extend(M @ Vector(c) for c in cs)
        for cam in cams_at(f):
            seen[cam.name] = cam
            Mc = cam.matrix_world
            fwd = (Mc.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
            o = Mc.translation
            for p in pts:
                d = (p - o).dot(fwd)
                dmin, dmax = min(dmin, d), max(dmax, d)
    sc.frame_set(keep)
    if not seen:
        return None
    clip_s = min(float(c.data.clip_start) for c in seen.values())
    clip_e = max(float(c.data.clip_end) for c in seen.values())
    start = max(clip_s, dmin - margin)
    end = max(start + 0.01, dmax + margin)
    if _world_volume(sc):
        # the world's volume fills every froxel the camera sees: narrowing the range would cut it off
        was_custom = bool(ee.use_volume_custom_range)
        start = min(start, float(ee.volumetric_start) if was_custom else clip_s)
        end = max(end, float(ee.volumetric_end) if was_custom else clip_e)
    if extra or len(seen) > 1:
        print(f"[sdf] fit_volume_range: {start:.2f} .. {end:.2f} m covers "
              + (f"{len(extra)} other volume(s) ({', '.join(extra[:4])}{' ...' if len(extra) > 4 else ''})"
                 if extra else 'the volumes')
              + (f" from {len(seen)} cameras ({', '.join(seen)})" if len(seen) > 1 else ''), flush=True)
    ee.use_volume_custom_range = True
    ee.volumetric_start, ee.volumetric_end = float(start), float(end)
    return start, end
