// sky.glsl -- the eidoverse sky, ported 1:1 from Eanpa Engine's engine/sky_system.js (TSL) to GLSL.
//
// It runs in Blender's own GPU module (bake/baker.py) and renders, per film frame:
//   mode 0  the CAMERA LAYERS for the exact screen rays of the bake camera; uOutput picks the layer:
//             0 composite (background, shield, clouds)   1 clouds alone, premultiplied RGBA
//             2 background alone (atmosphere, stars, moon, celestial body, moon dust)
//             3 the shield alone, premultiplied RGBA (shieldworld)
//   mode 1  the ENVIRONMENT: an equirect in Blender's Environment Texture convention, for world lighting
//   mode 2  the CLOUD SHADOW map: transmittance toward the cloud key over a top-down square
// EEVEE then uses those images natively: the world shows them, the sun lamp carries the key, a caster
// plane carries the cloud shadows, and the sky elements (the ringworld band, the shattered moon) composite
// the shield and clouds over themselves. The density, lighting and celestial maths below are ours, line for
// line; only the host changed. All maths is in three.js world space (Y up), exactly like the source. The
// baker converts Blender's Z-up camera/directions into it: three (x, y, z) = Blender (x, z, -y).
//
// World switches (defines, set by the baker per sky world; the JS builds the same branches at build time):
//   RING_ON        the ringworld's ring-native deck (opts.ringCurve): the RING_* constants come with it
//   HAS_CELESTIAL  a celestial body shaded in the sky (opts.celestial): the red giant (redgiant.js, code generated
//                  by bake/celestial.py) or any body that supplies celestial(dir, col)
//   HAS_SHIELD     the planetary hex shield (redgiant.js attach)
//   HAS_DUST       the shattered moon's volumetric accretion dust (asteroid_moon.js), generated code
//   HAS_RING_ENV   the analytic band in the environment (sky_system.js ringEnvTrace via bakeEnv ringworld)
// and the planet's radius R_EARTH (opts.earthRadius).
//
// Names follow the TSL uniforms (u.largeT -> uLargeT ...). Comments that explain WHY a term exists live in
// the JS source; the ones kept here say where a line came from when that is not obvious.

#ifndef RING_ON
#define RING_ON 0
#endif
#ifndef HAS_CELESTIAL
#define HAS_CELESTIAL 0
#endif
#ifndef HAS_SHIELD
#define HAS_SHIELD 0
#endif
#ifndef HAS_DUST
#define HAS_DUST 0
#endif
#ifndef HAS_RING_ENV
#define HAS_RING_ENV 0
#endif
#ifndef RING_PHASE
#define RING_PHASE 0.0
#endif

// ---- analytic 3D value noise (engine/sky_noise.js) ----
float hashA(vec3 p) {
    vec3 q = fract(p * 0.3183099 + vec3(0.1, 0.17, 0.13)) * 17.0;
    return fract(q.x * q.y * q.z * (q.x + q.y + q.z));
}
float noise3A(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    vec3 sm = f * f * (3.0 - 2.0 * f);
    float nx0 = mix(hashA(i), hashA(i + vec3(1, 0, 0)), sm.x);
    float nx1 = mix(hashA(i + vec3(0, 1, 0)), hashA(i + vec3(1, 1, 0)), sm.x);
    float nx2 = mix(hashA(i + vec3(0, 0, 1)), hashA(i + vec3(1, 0, 1)), sm.x);
    float nx3 = mix(hashA(i + vec3(0, 1, 1)), hashA(i + vec3(1, 1, 1)), sm.x);
    return mix(mix(nx0, nx1, sm.y), mix(nx2, nx3, sm.y), sm.z);
}
vec3 rotM(vec3 p) {
    return vec3(dot(p, vec3(0.0, 0.8, 0.6)), dot(p, vec3(-0.8, 0.36, -0.48)), dot(p, vec3(-0.6, -0.48, 0.64)));
}
float fbm3A(vec3 p) {
    float f = noise3A(p) * 0.5;
    p = rotM(p) * 2.02;
    f += noise3A(p) * 0.25;
    p = rotM(p) * 2.03;
    f += noise3A(p) * 0.125;
    return f;
}
// Hoskins' bounded 2D->1D hash, the production per-pixel march phase (hashScreen)
float hashScreen(vec2 pIn) {
    vec3 a = fract(vec3(pIn.x, pIn.y, pIn.x) * vec3(0.1031, 0.1030, 0.0973));
    float d = dot(a, vec3(a.y, a.z, a.x) + 33.33);
    vec3 b = a + d;
    return fract((b.x + b.y) * b.z);
}
// the sin-free Hoskins hash21 the red giant, the shield and the ring use (house style)
float h21(vec2 p) {
    vec3 a = fract(vec3(p.x, p.y, p.x) * 0.1031);
    float d = dot(a, vec3(a.y, a.z, a.x) + 33.33);
    vec3 b = a + d;
    return fract((b.x + b.y) * b.z);
}

#ifndef R_EARTH
#define R_EARTH 6371000.0
#endif
const float PI = 3.14159265358979;

// ---- weather map: 512^2 1/f field, .r macro coverage, .g puff field (sampled RAW, repeat, linear) ----
float wSampleL(vec2 uv) { return textureLod(weatherTex, uv, 0.0).r; }
float wSampleS(vec2 uv) { return textureLod(weatherTex, uv, 0.0).g; }

float shellFar(vec3 org, vec3 dir, float s) {
    float ocy = org.y + R_EARTH;
    float b = dot(dir, vec3(org.x, ocy, org.z)) * 2.0;
    float c = org.x * org.x + org.z * org.z + (org.y - s) * (org.y + s + 2.0 * R_EARTH);
    float D = max(b * b - c * 4.0, 0.0);
    return c * -2.0 / (b + sqrt(D));
}

// ---- RINGWORLD deck (opts.ringCurve): a rounded-corner chord profile, R-relative constants ----
#if RING_ON
float ringDeckY(float zq) {
    float uz = clamp(abs(zq) - RING_ZFLAT, 0.0, RING_ARC_W * 0.999);
    return RING_BASE + RING_ARC_RAD - sqrt(max(RING_ARC_RAD * RING_ARC_RAD - uz * uz, 1.0));
}
float ringSlopeAt(vec3 p) { return (ringDeckY(p.z + 60.0) - ringDeckY(p.z - 60.0)) / 120.0; }
float ringZShear(vec3 p, float ch) { return ringSlopeAt(p) * ch * (RING_THICK * RING_SHEAR_K); }
float ringStrip(vec3 p) {
    float wMask = 1.0 - smoothstep(RING_LOCAL_HALF * 0.66, RING_LOCAL_HALF * 1.3, abs(p.x));
    return wMask * (1.0 - smoothstep(RING_VISIBLE_END - RING_END_FADE, RING_VISIBLE_END, abs(p.z)));
}
float stormContainAt(vec3 p) {
    float progress = smoothstep(RING_ZFLAT, RING_VISIBLE_END, abs(p.z));
    float halfWidth = mix(RING_LOCAL_HALF, RING_WISP_CURVE_HALF, progress);
    float width = 1.0 - smoothstep(halfWidth * 0.72, halfWidth * 1.22, abs(p.x));
    float end = 1.0 - smoothstep(RING_VISIBLE_END - RING_END_FADE, RING_VISIBLE_END, abs(p.z));
    return width * end;
}
#endif

float atmoHeight(vec3 p) {
#if RING_ON
    // DRAPE the layer on the slope: height measured normal to the envelope (a profile coordinate, not metres)
    float bigY = ringDeckY(p.z);
    float slope = ringSlopeAt(p);
    float cosT = 1.0 / sqrt(slope * slope + 1.0);
    return uCloudStart + (p.y - bigY) * cosT * uCloudHeight / RING_THICK;
#else
    return (p.y * (p.y + 2.0 * R_EARTH) + p.x * p.x + p.z * p.z)
        / (length(vec3(p.x, p.y + R_EARTH, p.z)) + R_EARTH);
#endif
}
float wallLower(vec3 p) {
    float wdx = p.x - uWallCloud.x;
    float wdz = p.z - uWallCloud.y;
    float r2 = uWallCloud.z * uWallCloud.z;
    return uWallCloud.w * exp(-(wdx * wdx + wdz * wdz) / r2);
}

#if RING_ON
#define RING_ZW(p, ch) ringZShear(p, ch)
#define RING_STRIP(p) ringStrip(p)
#else
#define RING_ZW(p, ch) 0.0
#define RING_STRIP(p) 1.0
#endif

// ---- density (cloudsAt / cheapDensity / smoothDensity) ----
float cloudsAt(vec3 pIn, out float ch) {
    vec3 p = pIn * uStretch;
    float atmoH = atmoHeight(pIn);
    ch = clamp((atmoH - (uCloudStart - wallLower(pIn) * 260.0)) / uCloudHeight, 0.0, 1.0);
    float zW = RING_ZW(pIn, ch);
    vec3 p1 = p + vec3(-uDisp.x, 0.0, -uDisp.z);
    float largeWeather = clamp((wSampleL(vec2(p1.z + zW, p1.x) * (-0.00005 * uWScale)) - uLargeT) * uLargeA, 0.0, 2.0);
    vec3 p2 = p1 + vec3(-uDisp.z * 0.4, 0.0, uDisp.x * 0.4);
    float weather2 = max(wSampleS(vec2(p2.z + zW, p2.x) * (0.00005 * uWScale) + vec2(0.37, 0.11)) - uWeatherT, 0.0) / 0.72;
    float weather = largeWeather * weather2 * smoothstep(0.0, 0.5, ch) * (1.0 - smoothstep(0.5, 1.0, ch));
    float shapeExp = 0.3 + 1.5 * smoothstep(0.2, 0.5, ch);
    float cloudShape = pow(max(weather, 1e-6), shapeExp);
    vec3 p3 = p2 + vec3(uTime * 12.3, 0.0, 0.0);
    float den1 = max(cloudShape - fbm3A(p3 * (0.01 * uDScale)) * 0.7, 0.0);
    vec3 p4 = p3 + vec3(0.0, uTime * 15.2, 0.0);
    float den2 = max(den1 - fbm3A(p4 * (0.05 * uDScale)) * 0.2, 0.0);
    return largeWeather * uFinalMul * min(den2 * 5.0, 1.0) * RING_STRIP(pIn);
}
float cheapDensity(vec3 pIn) {
    vec3 p = pIn * uStretch;
    float ch = clamp((atmoHeight(pIn) - uCloudStart) / uCloudHeight, 0.0, 1.0);
    float zW = RING_ZW(pIn, ch);
    vec3 p1 = p + vec3(-uDisp.x, 0.0, -uDisp.z);
    float lw = clamp((wSampleL(vec2(p1.z + zW, p1.x) * (-0.00005 * uWScale)) - uLargeT) * uLargeA, 0.0, 2.0);
    vec3 p2 = p1 + vec3(-uDisp.z * 0.4, 0.0, uDisp.x * 0.4);
    float w2 = max(wSampleS(vec2(p2.z + zW, p2.x) * (0.00005 * uWScale) + vec2(0.37, 0.11)) - uWeatherT, 0.0) / 0.72;
    float weather = lw * w2 * smoothstep(0.0, 0.5, ch) * (1.0 - smoothstep(0.5, 1.0, ch));
    float shape = pow(max(weather, 1e-6), 0.3 + 1.5 * smoothstep(0.2, 0.5, ch));
    vec3 p3 = p2 + vec3(uTime * 12.3, 0.0, 0.0);
    float den = max(shape - fbm3A(p3 * (0.01 * uDScale)) * 0.7, 0.0);
    return lw * uFinalMul * min(den * 5.0, 1.0) * RING_STRIP(pIn);
}
float smoothDensity(vec3 pIn) {
    vec3 p = pIn * uStretch;
    float ch = clamp((atmoHeight(pIn) - (uCloudStart - wallLower(pIn) * 260.0)) / uCloudHeight, 0.0, 1.0);
    float zW = RING_ZW(pIn, ch);
    vec3 p1 = p + vec3(-uDisp.x, 0.0, -uDisp.z);
    float lw = clamp((wSampleL(vec2(p1.z + zW, p1.x) * (-0.00005 * uWScale)) - uLargeT) * uLargeA, 0.0, 2.0);
    vec3 p2 = p1 + vec3(-uDisp.z * 0.4, 0.0, uDisp.x * 0.4);
    float w2 = max(wSampleS(vec2(p2.z + zW, p2.x) * (0.00005 * uWScale) + vec2(0.37, 0.11)) - uWeatherT, 0.0) / 0.72;
    float weather = lw * w2 * smoothstep(0.0, 0.5, ch) * (1.0 - smoothstep(0.5, 1.0, ch));
    float shape = pow(max(weather, 1e-6), 0.3 + 1.5 * smoothstep(0.2, 0.5, ch));
    return lw * uFinalMul * min(shape * 3.5, 1.0) * RING_STRIP(pIn);
}

// ---- numerical Mie phase (+ the extended-source soften option) ----
float phaseMie(float c) {
    float p1 = c + 0.8194068;
    float raw = exp(c * -65.0 - 55.0) * 9.805233e-6
        + exp(p1 * p1 * -83.70334) * 0.1388198
        + exp(c * 7.810083) * 2.054747e-3
        + exp(c * -4.552125e-12) * 2.600563e-2;
    return uPhaseSoften > 0.0 ? mix(raw, 0.09, uPhaseSoften) : raw;
}

// ---- sun march: Beer + two multiple-scattering octaves + powder ----
float lightRay(vec3 p, float phaseF, float dC, float mu, float ch, float j0) {
    float stepL = clamp(uCloudHeight * 2.2, 380.0, 700.0) / float(N_LIGHT);
    float detailedDen = 0.0;
    float massDen = 0.0;
    if (uLightCacheDirect < 0.999) {
        for (int j = 0; j < N_LIGHT; j++) detailedDen += cheapDensity(p + uLightDir * stepL * (j0 + float(j)));
    }
    if (uLightCacheDirect > 0.001) {
        for (int j = 0; j < N_LIGHT; j++) massDen += smoothDensity(p + uLightDir * stepL * (j0 + float(j))) * 0.25;
    }
    float den = mix(detailedDen, massDen, clamp(uLightCacheDirect, 0.0, 1.0));
    float scatter = mix(uMsFloor, 1.0, 1.0 - smoothstep(0.0, 0.96, mu));
    float beers = exp(-stepL * den)
        + exp(-stepL * den * 0.1) * scatter * 0.5
        + exp(-stepL * den * 0.02) * scatter * 0.4;
    float powdered = 0.05 + pow(max(min(dC * 8.5, 1.0), 1e-6), 0.3 + ch * 5.5) * 1.5;
    float lit = mix(powdered, 1.0, clamp(den * 0.4, 0.0, 1.0));
    return beers * phaseF * mix(1.0, lit, uLightK);
}

// ---- analytic mares'-tail plumes: the in-repo eidoverse cirrus (sky_system.js), used when the Eanpa
// ice-trail atlas (assets/sky/cirrus_ice_trails.png) is not present ----
float cirrusPlumes(vec3 wa, float wispN, float wispPatch) {
    vec2 cellP = wa.xz * 0.00013;
    vec2 cid = floor(cellP);
    vec2 loc = fract(cellP) - vec2(0.5);
    float angleR = hashA(vec3(cid.x, cid.y, 1.7));
    float shapeR = hashA(vec3(cid.x, cid.y, 5.9));
    float widthR = hashA(vec3(cid.x, cid.y, 9.2));
    float presenceR = hashA(vec3(cid.x, cid.y, 13.6));
    float cx = (hashA(vec3(cid.x, cid.y, 17.3)) - 0.5) * 0.13;
    float cy = (hashA(vec3(cid.x, cid.y, 21.8)) - 0.5) * 0.13;
    float x = loc.x - cx;
    float y = loc.y - cy;
    float dx = angleR - 0.5;
    float dy = shapeR - 0.5;
    float inv = 1.0 / max(length(vec2(dx, dy)), 0.08);
    float cs = dx * inv;
    float sn = dy * inv;
    float along = x * cs + y * sn;
    float across0 = y * cs - x * sn;
    float len = shapeR * 0.13 + 0.28;
    float width = widthR * 0.046 + 0.048;
    float u = along / len;
    float bend = u * (angleR - 0.5) * (width * 0.42) + u * u * (shapeR - 0.5) * (width * 1.55);
    float across = across0 - bend;
    float taper = 1.0 - smoothstep(0.52, 1.0, abs(u));
    float coreW = width * (taper * 0.72 + 0.20) * 0.34;
    float core = 1.0 - smoothstep(coreW * 0.16, coreW, abs(across));
    float branchGate = smoothstep(-0.18, 0.72, u) * taper;
    float sep = width * (smoothstep(-0.4, 0.85, u) * 1.05 + 0.42);
    float upper = (1.0 - smoothstep(coreW * 0.10, coreW * 0.82, abs(across - sep))) * 0.52 * branchGate;
    float lower = (1.0 - smoothstep(coreW * 0.08, coreW * 0.72, abs(across + sep * 0.78))) * 0.36 * branchGate;
    float plume = (1.0 - smoothstep(width * 0.55, width * 2.85, abs(across))) * (wispN * 0.08 + 0.12) * taper;
    float breakMask = smoothstep(0.36, 0.70, wispN) * 0.72 + 0.28;
    float presence = smoothstep(0.20, 0.48, presenceR);
    return min(core + upper + lower + plume, 0.96) * taper * breakMask * presence
        * (smoothstep(0.08, 0.60, wispPatch) * 0.32 + 0.68);
}

// ---- high clouds: wisp sheets, cirrus ice-trail atlas, severe-weather canopy ----
float highCloudAlphaAt(vec3 pC) {
    vec3 wa = pC + vec3(-uDisp.x, 0.0, -uDisp.z);
    float wispPatch = fbm3A(wa * 0.00016 + vec3(4.7, 1.3, -2.1));
    float wispWarp = fbm3A(wa * 0.00031 + vec3(-1.7, 3.1, 5.3)) - 0.44;
    float wispBend = fbm3A(wa * 0.00009 + vec3(8.2, -1.4, 2.7)) - 0.44;
    vec3 wispP = wa * uWispStretch * uWispScale + vec3(
        wispWarp * 1.8 + wispBend * 1.4,
        wispWarp * 0.35,
        wispWarp * -1.2 + wispBend * 0.7);
    float wispN = fbm3A(wispP);
    float sheet = smoothstep(uWispThreshold, uWispThreshold + 0.24, wispN) * smoothstep(0.30, 0.62, wispPatch);
    float wispShape = sheet;
    if (uWispFilament >= 0.55) {
        vec2 shear = normalize(uSkyWind.xz + vec2(0.001));
        float along = dot(wa.xz, shear);
        float across = dot(wa.xz, vec2(-shear.y, shear.x));
        vec2 cuv = vec2(along, across) / 18000.0 + vec2(0.24, 0.47);
        float fibers = uHasCirrus > 0 ? texture(cirrusTex, cuv).r * 0.82
                                      : cirrusPlumes(wa, wispN, wispPatch);
        wispShape = uWispFilament > 0.85 ? fibers : mix(sheet, fibers, smoothstep(0.55, 0.85, uWispFilament));
    }
    float canopyField = smoothstep(0.18, 0.56, wispPatch * 0.72 + (wispBend + 0.44) * 0.28);
    float canopyDetail = smoothstep(0.20, 0.82, wispN) * 0.45 + 0.55;
    float canopyShape = max(wispShape, canopyField * uWispFloor * canopyDetail);
    return min(canopyShape * uWispOn * uWispStrength * uWispOpacity, 0.88);
}

// ---- Dark Thunderstorm: the sealed lowest 1.1-1.45 km of the cumulonimbus ----
float stormLayerBottom() { return uCloudStart - 280.0; }
float stormLayerDepth() { return clamp(uCloudHeight * 2.85, 1100.0, 1450.0); }
float stormLayerBase(vec3 pIn) {
#if RING_ON
    return ringDeckY(pIn.z) - RING_BASE + stormLayerBottom();
#else
    return stormLayerBottom();
#endif
}
float stormAltitude(vec3 pIn) {
#if RING_ON
    return pIn.y - stormLayerBase(pIn);
#else
    return atmoHeight(pIn) - stormLayerBottom();
#endif
}
void stormFieldAt(vec3 pIn, float mediumDetail, float fineDetail,
                  out float extinction, out float h, out float macro, out float billow, out float detail,
                  out float core, out float scud) {
    float depth = stormLayerDepth();
    float altitude = stormAltitude(pIn);
    h = clamp(altitude / depth, 0.0, 1.0);
    float envelope = smoothstep(0.0, 0.045, h) * (1.0 - smoothstep(0.94, 1.0, h));
    vec3 drift = pIn + vec3(-uDisp.x * 0.62, uTime * 1.15, -uDisp.z * 0.62);
    float warp = noise3A(rotM(drift * 0.00031) + vec3(1.7, -3.1, 4.6));
    float wc = warp - 0.5;
    vec3 warped = drift + vec3(wc * 380.0, wc * -180.0, wc * 280.0);
    macro = noise3A(rotM(warped * 0.00062) + vec3(3.7, -1.9, 5.1));
    float giant = noise3A(rotM(drift * 0.000117) + vec3(-2.9, 6.3, -7.7));
    float rawBillow = noise3A(rotM(warped * 0.00185) + vec3(-6.2, 2.7, 1.4));
    float rawDetail = noise3A(rotM(warped * 0.0054) + vec3(8.4, -4.3, -2.6));
    billow = mix(0.5, rawBillow, clamp(mediumDetail, 0.0, 1.0));
    detail = mix(0.5, rawDetail, clamp(fineDetail, 0.0, 1.0));
    float ruffledH = h + (macro - 0.5) * 0.38 + (giant - 0.5) * 0.20 + (billow - 0.5) * 0.16;
    float organicCore = smoothstep(0.13, 0.56, ruffledH);
    float guaranteedCore = smoothstep(0.30, 0.58, h) * (1.0 - smoothstep(0.92, 0.985, h));
    core = max(organicCore * 0.92, guaranteedCore);
    float lowerWindow = smoothstep(0.01, 0.065, h) * (1.0 - smoothstep(0.30, 0.52, h));
    float middleWindow = smoothstep(0.10, 0.20, h) * (1.0 - smoothstep(0.50, 0.72, h));
    float scudField = macro * 0.28 + billow * 0.44 + detail * 0.28;
    float lowerScud = smoothstep(0.48, 0.70, scudField + (0.22 - h) * 0.28) * lowerWindow;
    float middleScud = smoothstep(0.56, 0.78, macro * 0.40 + detail * 0.60 + (0.42 - h) * 0.16) * middleWindow;
    scud = max(lowerScud, middleScud * 0.74);
    float deepCoreH = h + (macro - 0.5) * 0.14 + (billow - 0.5) * 0.04;
    float floorExtinction = mix(0.00035, 0.0160, smoothstep(0.38, 0.55, deepCoreH));
    float regionVar = 0.85 + giant * 0.30;
    float coreExtinction = core * (0.010 + billow * 0.015) * regionVar;
    float scudExtinction = scud * (0.015 + detail * 0.018) * regionVar;
    extinction = envelope * (floorExtinction + coreExtinction + scudExtinction);
#if RING_ON
    extinction *= stormContainAt(pIn);
#endif
}
float stormShadowExtinctionAt(vec3 pIn) {
    float h = clamp(stormAltitude(pIn) / stormLayerDepth(), 0.0, 1.0);
    float envelope = smoothstep(0.0, 0.045, h) * (1.0 - smoothstep(0.94, 1.0, h));
    float e = envelope * mix(0.00035, 0.0160, smoothstep(0.38, 0.55, h));
#if RING_ON
    e *= stormContainAt(pIn);
#endif
    return e;
}
#if RING_ON
// the storm layer's crossing along a ray over the curved deck (six bisection steps, as in the JS)
float stormRingTAt(vec3 org, vec3 dir, float layerOffset, float stormDy) {
    float layerY = stormLayerBottom() + layerOffset;
    float tLo = (layerY - org.y) / stormDy;
    float tHi = (layerY + RING_RISE - org.y) / stormDy;
    for (int s = 0; s < 6; s++) {
        float tMid = (tLo + tHi) * 0.5;
        vec3 pMid = org + dir * tMid;
        if (org.y + stormDy * tMid < ringDeckY(pMid.z) - RING_BASE + layerY) tLo = tMid; else tHi = tMid;
    }
    return (tLo + tHi) * 0.5;
}
#endif

// ---- the cloud dome body: premultiplied RGBA (cloudBody) ----
vec4 cloudBody(vec3 dir, vec3 org, float baseJit, float transientLightScale) {
#if RING_ON
    // RING MODE MARCH WINDOW: from the camera to the ray's exit from the ring cylinder (axis through y = 0, as the
    // JS measured against the real mesh), clipped to the deck's slab
    float aQ = dir.y * dir.y + dir.z * dir.z + 1e-6;
    float bQ = dir.y * org.y + dir.z * org.z;
    float cQ = org.y * org.y + org.z * org.z - RING_R * RING_R * 0.99;
    float tFar = (-bQ + sqrt(max(bQ * bQ - aQ * cQ, 0.0))) / aQ;
    float dyMag = max(abs(dir.y), 1e-4);
    float dyS = dir.y / max(abs(dir.y), 1e-6);
    float dySafe = dyS * dyMag;
    float tA = (RING_SLAB_LO - org.y) / dySafe;
    float tB = (RING_SLAB_HI - org.y) / dySafe;
    float t0 = max(min(tA, tB), 0.0);
    float t1 = min(min(max(tA, tB), tFar), uFadeDist);
#else
    float sTop = uCloudStart + uCloudHeight;
    float t0 = shellFar(org, dir, uCloudStart);
    float t1 = min(shellFar(org, dir, sTop), uFadeDist * 1.1);
#endif
    float stepS = max(t1 - t0, 0.0) / float(N_MARCH);
    float mu = dot(uLightDir, dir);
    float phaseF = phaseMie(mu);
    vec3 colSum = vec3(0.0);
    float trSum = 0.0;
    bool marchVisible = dir.y > 0.008 && t0 < uFadeDist;
    float lumaKey = max(max(max(uLightColor.x, uLightColor.y), uLightColor.z), 0.0001);
    vec3 keyChroma = uLightColor / lumaKey;
    float celestialK = clamp(uCelestialVis, 0.0, 1.0);
    float canopyGate = smoothstep(0.6, 0.98, uStormCanopy) * (1.0 - celestialK);
    if (marchVisible && uFinalMul > 0.0001) {
        for (int k = 0; k < M_PASS; k++) {
            float Trk = 1.0;
            vec3 colk = vec3(0.0);
            float jitK = fract(baseJit + float(k) / float(M_PASS));
            float jitL = fract(fract(baseJit * 73.1063) + float(k) * 0.6180339887);
            vec3 p = org + dir * t0 + dir * stepS * jitK;
            for (int i = 0; i < N_MARCH; i++) {
                if (Trk <= 0.008) break;
                float ch;
                float dens = cloudsAt(p, ch);
                if (dens > 0.0) {
                    float intensity = lightRay(p, phaseF, dens, mu, ch, jitL);
                    vec3 clearAmb = uAmbSky * (0.5 + ch * 0.6) + uAmbGround * max(1.0 - ch * 2.0, 0.0);
                    vec3 amb = mix(clearAmb, vec3(dot(clearAmb, vec3(0.2126, 0.7152, 0.0722))) * keyChroma, uWeatherGrey);
                    vec3 canopySkylight = vec3(0.028, 0.029, 0.032) * (0.30 + ch * 0.70) * canopyGate;
                    vec3 ambGrey = mix(amb, vec3(dot(amb, vec3(0.34, 0.45, 0.21))) * 0.42, canopyGate);
                    vec3 radiance = ((ambGrey + uLightColor * intensity * celestialK) * uCloudRadiance * uCloudRadianceScale
                        + canopySkylight) * dens;
                    float trStep = exp(-dens * stepS);
                    colk += Trk * (radiance - radiance * trStep) / max(dens, 1e-6);
                    Trk *= trStep;
                }
                p += dir * stepS;
            }
            colSum += colk;
            trSum += Trk;
        }
    } else {
        trSum = float(M_PASS);
    }
    vec3 col = colSum / float(M_PASS);
    float Tr = trSum / float(M_PASS);

    float wispA = 0.0;
    if (uWispOn > 0.0001) {
        float hitT = shellFar(org, dir, uCloudStart + uCloudHeight + 1000.0);
        float wispRange = 1.0 - smoothstep(uFadeDist * 0.55, uFadeDist * 1.25, hitT);
        float wispAlpha = highCloudAlphaAt(org + dir * hitT) * wispRange;
        wispA = wispAlpha;
        float pk = max(max(max(uLightColor.x, uLightColor.y), uLightColor.z), 0.0001);
        vec3 wispRadiance = mix(uWispColor, vec3(dot(uWispColor, vec3(0.2126, 0.7152, 0.0722))) * (uLightColor / pk), uWeatherGrey);
        col += Tr * wispRadiance * wispAlpha * uCloudRadiance * uCloudRadianceScale;
    }

    float stormA = 0.0;
    vec3 stormRgb = vec3(0.0);
    if (uStormCanopy > 0.0001 && dir.y > 0.0005) {
        float stormDepth = stormLayerDepth();
#if RING_ON
        float stormDy = max(dir.y, 0.003);
        float stormNearT = stormRingTAt(org, dir, 0.0, stormDy);
        float stormFarT = stormRingTAt(org, dir, stormDepth, stormDy);
#else
        float stormBaseY = stormLayerBottom();
        float stormNearT = shellFar(org, dir, stormBaseY);
        float stormFarT = shellFar(org, dir, stormBaseY + stormDepth);
#endif
        float stormSegment = min(max(stormFarT - stormNearT, 1.0), 18000.0);
        float stormStep = stormSegment / float(N_STORM_STEPS);
        float stormMediumRange = 1.0 - smoothstep(6500.0, 16000.0, stormNearT);
        float stormFineRange = 1.0 - smoothstep(3000.0, 10500.0, stormNearT);
        float stormTrSum = 0.0;
        vec3 stormVolumeSum = vec3(0.0);
        float boundedStormFlash = clamp(uStrike.w, 0.0, 1.15) * transientLightScale;
        for (int sp = 0; sp < N_STORM_PASSES; sp++) {
            float stormTr = 1.0;
            vec3 stormVolumeRgb = vec3(0.0);
            float stormJitter = fract(baseJit + float(sp) / float(N_STORM_PASSES));
            vec3 stormP = org + dir * (stormNearT + stormStep * stormJitter);
            for (int i = 0; i < N_STORM_STEPS; i++) {
                if (stormTr <= 0.0015) break;
                float ext, h, macro, billow, detail, core, scud;
                stormFieldAt(stormP, stormMediumRange, stormFineRange, ext, h, macro, billow, detail, core, scud);
                float stormTrStep = exp(-ext * stormStep);
                float overheadTau = ext * (stormDepth * (1.0 - h)) * 0.42;
                float groundTau = ext * (stormDepth * h) * 0.12;
                float upwardVisibility = exp(-overheadTau);
                float groundVisibility = exp(-groundTau);
                float foldLight = clamp(0.06 + macro * 0.11 + billow * 0.15 + detail * 0.08
                    + upwardVisibility * 0.38 + groundVisibility * 0.18 - scud * 0.10, 0.0, 1.0);
                vec3 stormBaseRadiance = mix(vec3(0.0040, 0.0044, 0.0052), vec3(0.046, 0.048, 0.052), pow(foldLight, 1.32))
                    + uAmbGround * groundVisibility * 0.007
                    + uAmbSky * upwardVisibility * 0.0032;
                float strikeDistance = length(stormP.xz - uStrike.xz);
                float strikeReach = exp(strikeDistance * -0.00082) * 0.94 + 0.025;
                vec3 strikeRadiance = uFlashColor * boundedStormFlash * strikeReach * (0.42 + scud * 0.24 + core * 0.10);
                stormVolumeRgb += stormTr * (stormBaseRadiance + strikeRadiance) * (1.0 - stormTrStep);
                stormTr *= stormTrStep;
                stormP += dir * stormStep;
            }
            stormTrSum += stormTr;
            stormVolumeSum += stormVolumeRgb;
        }
        float stormTrAvg = stormTrSum / float(N_STORM_PASSES);
        float stormBoundary = uStormCanopy * smoothstep(0.0005, 0.012, dir.y);
        stormA = (1.0 - stormTrAvg) * stormBoundary;
        stormRgb = stormVolumeSum / float(N_STORM_PASSES) * stormBoundary;
    }

    float distFade = 1.0 - smoothstep(uFadeDist * 0.35, uFadeDist, t0);
    float horizFade = smoothstep(0.008, 0.06, dir.y);
    float fade = distFade * horizFade;
    float cover = 1.0 - Tr * (1.0 - wispA);
    float ordinaryA = cover * fade;
    vec3 ordinaryRgb = col * uCloudTint * fade;
    float cloudA = stormA + ordinaryA * (1.0 - stormA);
    vec3 stormFrontRgb = stormRgb + ordinaryRgb * (1.0 - stormA);
    vec3 underlayerFrontRgb = ordinaryRgb + stormRgb * (1.0 - ordinaryA);
    float settledUnderlayerFront = smoothstep(0.96, 0.995, uStormCanopy) * (1.0 - smoothstep(0.005, 0.08, uCelestialVis));
    vec3 cloudRgb = mix(stormFrontRgb, underlayerFrontRgb, settledUnderlayerFront);

    // below-cloud atmosphere: haze shafts + world rain curtains (20 x 6 march)
    float shaft = 0.0;
    float trH = 1.0;
    if ((uShaftK > 0.0005 || uPrecipK > 0.0005) && dir.y > 0.0) {
        float tEnd = min(t0, 6000.0);
        float stepH = tEnd / 20.0;
        float sy = max(uLightDir.y, 0.08);
        float segL = uCloudHeight / sy;
        vec3 hp = org + dir * stepH * (baseJit * 0.5 + 0.3);
        for (int i = 0; i < 20; i++) {
#if RING_ON
            // ring mode: atmoHeight is a profile coordinate, the shaft maths needs physical y
            float hEnter = max(RING_SLAB_LO + 20.0 - hp.y, 0.0) / sy;
#else
            float hEnter = max(uCloudStart - atmoHeight(hp), 0.0) / sy;
#endif
            float od = 0.0;
            for (int j = 0; j < 6; j++) {
                od += smoothDensity(hp + uLightDir * (hEnter + segL * ((float(j) + 0.5) / 6.0)));
            }
            float vis = exp(-od * (segL / 6.0));
            float cp1z = hp.z - uDisp.z;
            float cp1x = hp.x - uDisp.x;
            float cellCov = clamp((wSampleL(vec2(cp1z, cp1x) * (-0.00005 * uWScale)) - uLargeT) * uLargeA, 0.0, 2.0);
            float tCur = stepH * (float(i) + 0.5);
            float colTex = wSampleS(vec2(cp1z, cp1x) * 0.0008 + vec2(0.61, 0.23));
            float colMod = mix(colTex * 1.1 + 0.25, 0.8, smoothstep(900.0, 2600.0, tCur));
#if RING_ON
            float belowBase = 1.0 - smoothstep((RING_SLAB_LO + 20.0) * 0.55, RING_SLAB_LO + 20.0, hp.y);
#else
            float belowBase = 1.0 - smoothstep(uCloudStart * 0.55, uCloudStart, atmoHeight(hp));
#endif
            float ordinaryPrecipGate = smoothstep(uPrecipLo, uPrecipHi, cellCov);
            float stormPrecipGate = mix(0.72, 1.0, colTex);
            float precipGate = mix(ordinaryPrecipGate, stormPrecipGate, clamp(uStormCanopy, 0.0, 1.0));
            float precip = uPrecipK * precipGate * colMod * ((1.0 - float(i) / 20.0 * 0.5) * 2.1e-4) * (belowBase * 0.5 + 0.5);
#if RING_ON
            // ring mode: curtains off pending their own tune (the JS: they woke up as hard rectangular walls)
            float altPhys = hp.y;
            float rho = uShaftDen * uShaftK * exp(altPhys / -900.0);
#else
            float altPhys = atmoHeight(hp);
            float rho = uShaftDen * uShaftK * exp(altPhys / -900.0) + precip;
#endif
            shaft += trH * (vis * 0.75 + 0.25) * rho * stepH;
            trH *= exp(-rho * stepH);
            hp += dir * stepH;
        }
    }
    float shaftSun = clamp(uCelestialVis, 0.0, 1.0);
    float shaftSkylight = mix(1.0, 0.30, clamp(uStormCanopy, 0.0, 1.0));
    vec3 shaftCol = (uLightColor * uCloudDim * (phaseF * 0.7 + 0.055) * shaftSun
        + uAmbSky * uCloudDim * 2.4 * shaftSkylight) * shaft * horizFade;
    float coverT = 1.0 - (1.0 - cloudA) * trH;
    return vec4((cloudRgb + shaftCol) * uSolarSkyVis, coverT);
}

// ---- transmittance toward the cloud key (tslCloudTransmittance) ----
float cloudTransmittanceN(vec3 pW, int nSteps) {
    float dy = max(uLightDir.y, 0.001);
    float stormK = clamp(uStormCanopy, 0.0, 1.0);
#if RING_ON
    float shadowBottom = mix(ringDeckY(pW.z), stormLayerBase(pW), stormK);
    float shadowDepth = mix(RING_THICK, stormLayerDepth(), stormK);
    float hEnter = max(shadowBottom - pW.y, 0.0) / dy;
    float segL = shadowDepth / dy;
#else
    float shadowBottom = mix(uCloudStart, stormLayerBottom(), stormK);
    float shadowDepth = mix(uCloudHeight, stormLayerDepth(), stormK);
    float hEnter = max(shellFar(pW, uLightDir, shadowBottom), 0.0);
    float segL = max(shellFar(pW, uLightDir, shadowBottom + shadowDepth) - hEnter, 0.0);
#endif
    float od = 0.0;
    // Eanpa skips the march once a sealed canopy makes celestial visibility zero, because the scene key is then
    // zero too. The shadow-map pass (mode 2) marches anyway: the ringworld's band sun is never dimmed by weather,
    // and its cloud-shadow twin reads this map, so a sealed storm must still shadow the band beneath it.
    bool celestialOn = uCelestialVis > 0.001 || uMode == 2;
    if (celestialOn) {
        for (int i = 0; i < N_CLOUD_SHADOW; i++) {
            if (i >= nSteps) break;
            if (od * (segL / float(nSteps)) > 9.0) break;
            float along = hEnter + segL * ((float(i) + 0.5) / float(nSteps));
            vec3 sp = pW + uLightDir * along;
            float ordinaryExt = 0.0;
            float stormExt = 0.0;
            if (stormK < 0.999) { float chs; ordinaryExt = cloudsAt(sp, chs); }
            if (stormK > 0.001) stormExt = stormShadowExtinctionAt(sp);
            od += mix(ordinaryExt, stormExt, stormK);
        }
    }
    float opticalDepth = od * (segL / float(nSteps));
    float occ = 1.0 - exp(-opticalDepth);
    float cloudMass = max(smoothstep(0.0001, 0.02, uFinalMul), smoothstep(0.0001, 0.02, uStormCanopy));
    float lowTransmission = 1.0 - occ * cloudMass;
    float iceOpacity = 0.0;
    if (uWispOn > 0.0001 && celestialOn && uLightDir.y > 0.001) {
        float hitT = shellFar(pW, uLightDir, uCloudStart + uCloudHeight + 1000.0);
        iceOpacity = highCloudAlphaAt(pW + uLightDir * hitT) * mix(0.22, 0.42, 1.0 - uWispFilament);
    }
    return lowTransmission * (1.0 - iceOpacity);
}
float cloudTransmittance(vec3 pW) { return cloudTransmittanceN(pW, N_CLOUD_SHADOW); }

// tslCloudShadow(p, strength): the transmittance as a scene light's attenuation (gated to daylight, below the deck)
float cloudShadowAt(vec3 pW, float strength, int nSteps) {
    float transmittance = cloudTransmittanceN(pW, nSteps);
    float daylight = smoothstep(-0.005, 0.012, uLightDir.y);
    float belowDeck = 1.0 - smoothstep(uCloudStart, uCloudStart + uCloudHeight, atmoHeight(pW));
    return 1.0 - (1.0 - transmittance) * strength * uCloudShadowStrength * daylight * belowDeck;
}

// ---- background + celestial body (bgBody) ----
// Texture v: the WebGPU loaders (render_scene.mjs loadImageTexture, three's TextureLoader) both put the
// image's bottom row at v = 0, which is exactly GL's order for Blender's bottom-row-first pixels: no flip.
vec2 equirectUV3(vec3 d) {
    return vec2(atan(d.z, d.x) / (PI * 2.0) + 0.5, acos(clamp(d.y, -1.0, 1.0)) / PI);
}

//@@CELESTIAL@@

vec3 bgBody(vec3 dir, int withDisc) {
    float upK = pow(clamp(dir.y * 1.35 + 0.02, 0.0, 1.0), 0.55);
    vec3 col = mix(uHorizon, uZenith, upK);
    float mu = dot(dir, uSunDir);
    col += uSunColor * pow(max(mu, 0.0), 6.0) * 0.35 * (1.0 - upK);
    float moonDisc = 0.0;
    if (uHasMoon > 0) {
        moonDisc = smoothstep(uMoonCos, uMoonCos + 0.0004, dot(dir, uMoonDir));
    }
    if (uHasStars > 0) {
        float ra = uTime * 0.004;
        vec3 dR = vec3(dir.x * cos(ra) - dir.z * sin(ra), dir.y, dir.x * sin(ra) + dir.z * cos(ra));
        vec3 st = textureLod(starTex, equirectUV3(dR), 0.0).rgb;
        vec3 starTerm = st * st * uStarFade * 1.6;
        if (uHasMoon > 0) starTerm *= (1.0 - moonDisc);
        col += starTerm;
        col += uSkyGlow;
    }
    if (uHasMoon > 0) {
        float sinR = sqrt(1.0 - uMoonCos * uMoonCos);
        float lx = dot(dir, uMoonRight) / sinR;
        float ly = dot(dir, uMoonUp) / sinR;
        float r2 = clamp(lx * lx + ly * ly, 0.0, 1.0);
        float nz = sqrt(1.0 - r2);
        float lon = atan(nz, lx);
        float lat = asin(clamp(ly, -1.0, 1.0));
        vec2 muv = vec2(lon / (PI * 2.0) + 0.25, 0.5 - lat / PI);
        vec3 albedo = textureLod(moonTex, muv, 0.0).rgb;
        vec3 nWorld = uMoonRight * lx + uMoonUp * ly + uMoonDir * (-nz);
        float lit = max(dot(nWorld, uSunDir), 0.03);
        col += albedo * lit * moonDisc * 2.2 * (uMoonLightK * 0.5 + 0.5);
    }
#if HAS_CELESTIAL
    // CUSTOM CELESTIAL hook (opts.celestial), riding the weather-visibility gate of the default disc
    col = mix(col, celestial(dir, col), clamp(uCelestialVis, 0.0, 1.0));
#endif
    float disc = smoothstep(0.99995, 0.999985, mu);
    if (withDisc > 0) col += uSunColor * disc * uSunDiscI * uCelestialVis * uSolarVis;
    col += uSunColor * pow(max(mu, 0.0), 900.0) * 3.0 * uSunGlowI * uCelestialVis;
    col += uSunColor * pow(max(mu, 0.0), 60.0) * 0.22 * uSunGlowI * uCelestialVis;
    return col * uSolarSkyVis;
}

// ---- the planetary hex shield (redgiant.js attach): premultiplied RGBA, drawn between the sky and the clouds ----
#if HAS_SHIELD
float sphereFarOrigin(vec3 org, vec3 dir, float r) {
    float b = dot(org, dir);
    float c = dot(org, org) - r * r;
    return -b + sqrt(max(b * b - c, 0.0));
}
vec4 shieldLayer(vec3 dirV, vec3 org) {
    // the dome is a sphere about the world origin; its pattern reads the direction of the point hit (positionWorld)
    vec3 dir = normalize(org + dirV * sphereFarOrigin(org, dirV, SHIELD_R));
    vec2 p = dir.xz / max(dir.y, 0.05) * HEXSCALE;
    vec2 r = vec2(1.0, 1.7320508);
    vec2 hh = r * 0.5;
    vec2 a2 = mod(p, r) - hh;
    vec2 b2 = mod(p - hh, r) - hh;
    float useA = step(length(a2), length(b2));
    vec2 gv = mix(b2, a2, useA);
    vec2 id = p - gv;
    vec2 ha = abs(gv);
    float hexD = max(dot(ha, vec2(0.5, 0.8660254)), ha.x);
    float edge = smoothstep(0.40, 0.485, hexD);
    float ch = h21(id * 0.37 + 7.7);
    float shim = (sin(uStarT * (ch * 0.6 + 0.4) + ch * 31.0) * 0.5 + 0.5) * 0.1;
    float hits = 0.0;
    for (int i = 0; i < 5; i++) {
        vec4 imp = uImpact(i);
        float age = uStarT - imp.z;
        float d = length(id - imp.xy);
        float lit = step(abs(d - age * 30.0), 1.4);
        hits += lit * (h21(id + float(i) * 3.7) * 0.5 + 0.75) * exp(age * -1.5) * step(0.0, age) * imp.w;
    }
    float faceK = smoothstep(-0.2, 0.7, dot(dir, uStarDir)) * 0.7 + 0.3;
    float horizon = smoothstep(0.03, 0.38, dir.y);
    float cellGlow = hits + shim * faceK;
    float opacityRaw = (edge * faceK * 0.05 + cellGlow * (edge * 0.5 + 0.5) * 0.45) * horizon;
    float cloudOcc = 1.0;
    if (opacityRaw > 1e-4) {
        // clouds always read in front of the lattice: dimmed by the deck's shadow column where the view ray crosses it
        vec3 deckP = dir * (uCloudStart / max(dir.y, 0.06));
        cloudOcc = cloudShadowAt(deckP, 0.92, N_SHIELD_OCC);
    }
    vec3 color = uShieldColor * (edge + cellGlow * 1.5 + 0.15);
    float opacity = clamp(opacityRaw * cloudOcc, 0.0, 1.0);
    return vec4(color * opacity, opacity);
}
#endif

//@@DUST@@

// ---- the ringworld band, traced analytically for the environment (ringEnvTrace) ----
#if HAS_RING_ENV
vec4 ringEnvTrace(vec3 dir) {
    float oy = 2.0 - RING_CENTER_Y;
    float a = max(dir.y * dir.y + dir.z * dir.z, 1e-6);
    float b = oy * dir.y * 2.0;
    float cq = oy * oy - RING_BAND_R * RING_BAND_R;
    float disc = max(b * b - a * cq * 4.0, 0.0);
    float tHit = (-b + sqrt(disc)) / (a * 2.0);
    float hx = dir.x * tHit;
    float hy = oy + dir.y * tHit;
    float hz = dir.z * tHit;
    float inBand = 1.0 - smoothstep(RING_HALF_W - 30.0, RING_HALF_W + 30.0, abs(hx));
    float theta = atan(hz, -hy);                       // 0 at the overhead crest
    // + the band geometry's UV phase (Eanpa keeps the export's angular origin), so the reflections show the same
    // continents the band does
    float uT = (theta + RING_PHASE) / (PI * 2.0) * RING_REPEAT;
    float vT = hx / (RING_HALF_W * 2.0) + 0.5;
    // both maps in image space read row-from-top = vT (glTF map) / 1 - (1 - vT) (the mask): Blender rows run up
    vec3 land = textureLod(ringMapTex, vec2(uT, 1.0 - vT), 0.0).rgb;
    float mraw = textureLod(ringMaskTex, vec2(uT, 1.0 - vT), 0.0).r;
    float wk = 1.0 - smoothstep(0.45, 0.55, mraw);   // mask BLACK = water
    vec3 ringAlbedo = mix(land, vec3(0.03, 0.055, 0.07), wk);
    vec3 nrm = normalize(vec3(0.0, -hy, -hz));
    float lit = clamp(dot(nrm, uSunDir), 0.0, 1.0) * 0.75 + 0.3;
    vec3 col = ringAlbedo * lit * uCloudDim;
    float hazeK = 1.0 - smoothstep(1.2, 3.2, tHit / RING_BAND_R);
    return vec4(col, inBand * hazeK);
}
#endif

// ---- Blender Z-up <-> three Y-up ----
vec3 blenderToThree(vec3 b) { return vec3(b.x, b.z, -b.y); }

void main() {
    vec2 pix = gl_FragCoord.xy;               // window pixel centres (x + 0.5, y + 0.5), row 0 at the bottom
    vec2 uv = pix / uSize;
    if (uMode == 2) {
        // top-down light-column map centred on uOrg (three xz), uShadowExtent metres wide, at ground height
        vec2 xz = uOrg.xz + (uv - 0.5) * uShadowExtent * vec2(1.0, -1.0);
        // Blender image +v is Blender +y = three -z, so v grows toward three -z
        vec3 pW = vec3(xz.x, uShadowY, xz.y);
        float tr = cloudTransmittance(pW);
        FragColor = vec4(tr, tr, tr, 1.0);
        return;
    }
    vec3 dirB;
    if (uMode == 0) {
        // camera layer: Blender camera looks down its local -Z, +Y up, +X right
        vec2 ndc = uv * 2.0 - 1.0;
        vec3 dc = normalize(vec3(ndc.x * uTanHalf.x, ndc.y * uTanHalf.y, -1.0));
        dirB = normalize(uCamRight * dc.x + uCamUp * dc.y + uCamBack * dc.z);
    } else {
        // equirect in Blender's Environment Texture convention:
        //   u = -atan2(d.y, d.x) / 2pi + 0.5,  v = atan2(d.z, hypot(d.x, d.y)) / pi + 0.5
        float phi = (0.5 - uv.x) * 2.0 * PI;
        float theta = (uv.y - 0.5) * PI;
        dirB = vec3(cos(theta) * cos(phi), cos(theta) * sin(phi), sin(theta));
    }
    vec3 dir = normalize(blenderToThree(dirB));
    float baseJit = hashScreen(pix + uJitterSeed);
    int outSel = uMode == 0 ? uOutput : 0;
    vec3 bg = vec3(0.0);
    if (outSel == 0 || outSel == 2) {
        bg = bgBody(dir, uWithDisc);
#if HAS_DUST
        if (uMode == 0) {                     // the dust is a scene object in WebGPU: never in the environment
            vec4 dust = dustLayer(dir, uOrg, pix);
            bg = dust.rgb + (1.0 - dust.a) * bg;
        }
#endif
#if HAS_RING_ENV
        if (uMode == 1) {
            vec4 rt = ringEnvTrace(dir);
            bg = mix(bg, rt.rgb, rt.a);
        }
#endif
    }
    if (outSel == 2) {
        FragColor = vec4(bg, 1.0);
        return;
    }
    vec4 sh = vec4(0.0);
#if HAS_SHIELD
    // the shield is a scene mesh in WebGPU, so bakeEnv never sees it: camera layers only
    if (uMode == 0 && (outSel == 0 || outSel == 3)) sh = shieldLayer(dir, uOrg);
#endif
    if (outSel == 3) {
        FragColor = sh;
        return;
    }
    vec4 cld = cloudBody(dir, uOrg, baseJit, uTransientLight);
    if (outSel == 1) {
        FragColor = cld;
        return;
    }
    vec3 back = sh.rgb + (1.0 - sh.a) * bg;
    vec3 rgb = back * (1.0 - cld.a) + cld.rgb;
    if (uMode == 1) {
        float belowHorizon = 1.0 - smoothstep(-0.35, 0.0, dir.y);
        rgb *= mix(1.0, uBelowHorizonDim, belowHorizon);
    }
    FragColor = vec4(rgb, cld.a);
}
