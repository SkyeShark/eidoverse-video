"""The solid EXAMPLES of sdf_raymarch_loader.js, for the Blender edition.

    basic_sphere      'fast' smoke test: one sphere, flat shading
    stylized_blob     'balanced' morphing blob: domain warp, dimples, fresnel rim (animated by uTime)
    detailed_coat     'high' creature coat: mackerel stripes over fbm, micro-relief, dorsal / belly split
    fractal_core      'ultra' mandelbulb, power 8
    mr_hege           Mr. Hege, the red-skinned octopus man in a wool suit (animated: head sway, six tentacles)
    red_shoggoth      the red shoggoth with the blue angry-face mask: 48 blinking eyes, 12 tentacles (animated)
    explosion         the pyroclastic fireball: a displaced sphere, emissive core, smoky lit rim (animated)
    mandelbulb, sierpinski_tetra, menger_sponge, gyroid
                      the SDF_TEX_RECIPES distance estimators as placeable solids (their screen form is
                      make_sdf_texture), coloured by the recipes' own palette

mr_hege and red_shoggoth are the two examples the engine's TSL migration dropped on 2026-07-04; they come from its
GLSL backup. Every map(), shade() and helper here is the engine's GLSL as written. Two things changed, both
behaviour-preserving: reversed-edge smoothstep(hi, lo, x) calls are written 1.0 - smoothstep(lo, hi, x) (the same
curve, and defined in every GLSL; the TSL port made the same rewrite), and `cameraPosition` is the viewer in the
SDF's local frame (see glsl_lib.VIEW_PRELUDE).

What each example adds for EEVEE is surface(p, n, mat): what its shade() knew about the material (albedo, roughness,
metal, emissive parts) without its hand-placed lights, plus Principled stand-ins for its view-dependent terms
(fresnel rims -> sheen, the wrap "SSS" -> subsurface, wet eyes -> coat). The scene's lights do the lighting.
shade() stays for the reference raymarch (SdfObject.raymarch_reference) the EEVEE render is judged against.

    from eidoblend.sdf import EXAMPLES
    hege = EXAMPLES['mr_hege'].make(location=(0, 0, 0))
    hege.place_on_ground(0.0)
    hege.bake(1, 120)                      # animated: re-meshed per frame
"""

from __future__ import annotations

from .spec import register_example
from .texture import SDF_TEX_DEFAULT_SHADE, SDF_TEX_PALETTE_GLSL, SDF_TEX_RECIPES

# =============================================================================================== basicSphere ===
register_example(
    'basic_sphere', kind='solid', description="'fast' tier smoke test (single sphere, flat shading)",
    bounds={'min': [-1, -1, -1], 'max': [1, 1, 1]},
    quality='fast',
    map=r"""
            vec2 map(vec3 p) {
                return vec2(sdSphere(p, 0.6), 1.0);
            }""",
    shade=r"""
            vec3 shade(vec3 p, vec3 n, float mat) {
                vec3 L = normalize(vec3(0.5, 0.9, 0.4));
                float d = max(0.0, dot(n, L));
                float a = 0.35 + 0.25 * (n.y * 0.5 + 0.5);
                return vec3(0.85, 0.45, 0.25) * (a + 0.8 * d);
            }""",
    surface=r"""
            SdfSurface surface(vec3 p, vec3 n, float mat) {
                // shade(): Lambert plus a hemisphere ambient on one colour, no highlight: a rough dielectric
                SdfSurface s = sdfSurface(vec3(0.85, 0.45, 0.25), 0.7);
                s.specular = 0.25;
                return s;
            }""",
)

# ============================================================================================== stylizedBlob ===
register_example(
    'stylized_blob', kind='solid', animated=True,
    description="'balanced' tier morphing blob (domain warp, simple diffuse + fresnel, no micro-detail)",
    bounds={'min': [-1.1, -1.1, -1.1], 'max': [1.1, 1.1, 1.1]},
    quality='balanced',
    map=r"""
            vec2 map(vec3 p) {
                // Domain warp for irregular blob silhouette
                vec3 w = vec3(fbm(p * 2.0 + uTime * 0.3),
                              fbm(p * 2.0 + 5.2),
                              fbm(p * 2.0 + 1.3)) * 0.20;
                float d = sdEllipsoid(p + w, vec3(0.80, 0.62, 0.80));
                // Subtract a few dimples for texture
                d = opSmoothSub(sdSphere(p - vec3( 0.4, 0.2, 0.5), 0.10), d, 0.05);
                d = opSmoothSub(sdSphere(p - vec3(-0.3, 0.3, 0.5), 0.08), d, 0.05);
                return vec2(d, 1.0);
            }""",
    shade=r"""
            vec3 shade(vec3 p, vec3 n, float mat) {
                vec3 L = normalize(vec3(0.5, 0.9, 0.4));
                float diff = max(0.0, dot(n, L));
                float amb  = 0.25 + 0.30 * (n.y * 0.5 + 0.5);
                float fres = pow(1.0 - max(0.0, dot(n, normalize(cameraPosition - p))), 3.0);
                vec3 base = mix(vec3(0.30, 0.55, 0.85), vec3(0.85, 0.50, 0.70),
                                fbm(p * 3.0) * 0.5 + 0.5);
                vec3 col  = base * (amb + 0.85 * diff);
                col += fres * vec3(0.9, 0.8, 1.0) * 0.3;
                return col;
            }""",
    surface=r"""
            SdfSurface surface(vec3 p, vec3 n, float mat) {
                vec3 base = mix(vec3(0.30, 0.55, 0.85), vec3(0.85, 0.50, 0.70),
                                fbm(p * 3.0) * 0.5 + 0.5);
                SdfSurface s = sdfSurface(base, 0.5);
                // shade()'s pow(1 - N.V, 3) lavender rim, (0.9, 0.8, 1.0) * 0.3: a sheen layer of that tint
                s.sheen = 0.5;
                s.sheenTint = vec3(0.9, 0.8, 1.0);
                return s;
            }""",
)

# ============================================================================================== detailedCoat ===
_COAT_COLOUR = r"""
                // Mackerel tabby palette
                vec3 dark   = vec3(0.22, 0.12, 0.06);
                vec3 warm   = vec3(0.55, 0.32, 0.14);
                vec3 black  = vec3(0.02, 0.01, 0.01);
                vec3 belly  = vec3(0.82, 0.52, 0.24);

                // Warp for organic fur variation
                vec3 w = vec3(fbm(p * 8.0), fbm(p * 8.0 + 5.2), fbm(p * 8.0 + 1.3)) * 0.04;
                vec3 pw = p + w;

                // Base color
                vec3 coat = mix(dark, warm, fbm6(pw * 4.0));

                // Stripes perpendicular to spine (z-axis) + spot breakup
                float stripe = smoothstep(0.40, 0.75, sin(pw.z * 70.0 + fbm(pw*6.0)*4.0));
                stripe *= smoothstep(0.35, 0.55, fbm(pw * 14.0));
                stripe *= smoothstep(-0.3, 0.4, n.y);
                coat = mix(coat, black, stripe * 0.9);

                // Dorsal spine line
                float spine = (1.0 - smoothstep(0.0, 0.015, abs(p.x))) * smoothstep(0.3, 0.8, n.y);
                coat = mix(coat, black, spine * 0.7);

                // Orangish belly
                float b = (1.0 - smoothstep(0.16, 0.22, p.y)) * (1.0 - smoothstep(-0.6, -0.2, n.y));
                coat = mix(coat, belly, b);
"""

register_example(
    'detailed_coat', kind='solid',
    description="'high' tier creature-surface shader: mackerel stripes over multi-octave fbm, soft shadow, "
                'subsurface-tinted rim, dorsal/belly separation',
    bounds={'min': [-0.25, -0.05, -0.30], 'max': [0.25, 0.55, 0.35]},
    quality='high',
    map=r"""
            vec2 map(vec3 p) {
                // Stylized torso — multi-part capsule chain
                float body = sdCap2(p,
                    vec3(0.0, 0.22,  0.15),
                    vec3(0.0, 0.22, -0.05),
                    0.09, 0.07);
                body = smin(body,
                    sdSphere(p, vec3(0.0, 0.34, 0.20), 0.08), 0.05);
                // Micro-relief from fbm (lumpy, organic skin)
                float micro = (fbm(p * 18.0) - 0.5) * 0.008;
                body += micro;
                return vec2(body, 1.0);
            }""",
    shade=r"""
            vec3 shade(vec3 p, vec3 n, float mat) {""" + _COAT_COLOUR + r"""
                // Light + soft self-shadow
                vec3 L = normalize(vec3(0.6, 1.2, 0.4));
                float diff = max(0.0, dot(n, L));
                float sh   = softShadow(p + n * 0.002, L, 0.01, 1.5, 12.0);
                float amb  = 0.28 + 0.22 * (n.y * 0.5 + 0.5);
                // Subsurface-tinted rim
                float fres = pow(1.0 - max(0.0, dot(n, normalize(cameraPosition - p))), 4.0);
                vec3  col  = coat * (amb + 0.85 * diff * sh);
                col += fres * vec3(0.45, 0.22, 0.10) * 0.35;
                return col;
            }""",
    surface=r"""
            SdfSurface surface(vec3 p, vec3 n, float mat) {""" + _COAT_COLOUR + r"""
                SdfSurface s = sdfSurface(coat, 0.85);
                // the subsurface-tinted rim, pow(1 - N.V, 4) * (0.45, 0.22, 0.10) * 0.35: fur's warm sheen
                s.sheen = 0.8;
                s.sheenTint = vec3(1.0, 0.55, 0.3);
                s.specular = 0.3;
                return s;
            }""",
)

# =============================================================================================== fractalCore ===
register_example(
    'fractal_core', kind='solid',
    description="'ultra' tier mandelbulb-style infinite detail (slowest; use only for hero close-ups)",
    bounds={'min': [-1.5, -1.5, -1.5], 'max': [1.5, 1.5, 1.5]},
    quality='ultra',
    # a distance estimator, not a signed distance: the raymarch stops where it falls under surfEps * t (~1-2 mm
    # at the camera distances it was framed for), so the mesh is that level set, and its dust is swept
    iso=0.0015, min_component=24,
    map=r"""
            float mandelbulbDE(vec3 pos) {
                vec3 z = pos;
                float dr = 1.0;
                float r  = 0.0;
                const float POWER = 8.0;
                for (int i = 0; i < 8; i++) {
                    r = length(z);
                    if (r > 2.0) break;
                    float theta = acos(z.z / r);
                    float phi   = atan(z.y, z.x);
                    dr =  pow(r, POWER - 1.0) * POWER * dr + 1.0;
                    float zr = pow(r, POWER);
                    theta = theta * POWER;
                    phi   = phi   * POWER;
                    z = zr * vec3(sin(theta) * cos(phi),
                                  sin(theta) * sin(phi),
                                  cos(theta)) + pos;
                }
                return 0.5 * log(r) * r / dr;
            }
            vec2 map(vec3 p) {
                return vec2(mandelbulbDE(p), 1.0);
            }""",
    shade=r"""
            vec3 shade(vec3 p, vec3 n, float mat) {
                vec3 L = normalize(vec3(0.5, 0.9, 0.4));
                float diff = max(0.0, dot(n, L));
                float amb  = 0.20 + 0.25 * (n.y * 0.5 + 0.5);
                // Iterate-count-like tint from normal variance
                float t = fbm(p * 3.0);
                vec3 base = mix(vec3(0.15, 0.35, 0.75), vec3(0.95, 0.55, 0.20), t);
                float fres = pow(1.0 - max(0.0, dot(n, normalize(cameraPosition - p))), 5.0);
                return base * (amb + 0.8 * diff) + fres * vec3(1.0, 0.7, 0.4) * 0.4;
            }""",
    surface=r"""
            SdfSurface surface(vec3 p, vec3 n, float mat) {
                float t = fbm(p * 3.0);
                vec3 base = mix(vec3(0.15, 0.35, 0.75), vec3(0.95, 0.55, 0.20), t);
                SdfSurface s = sdfSurface(base, 0.45);
                // the pow(1 - N.V, 5) amber rim -> sheen
                s.sheen = 0.4;
                s.sheenTint = vec3(1.0, 0.7, 0.4);
                return s;
            }""",
)

# ==================================================================================================== mrHege ===
# Mr. Hege (humanoid in suit): an octopus-man in a wool suit with animated tentacles hanging off the lower face.
# Anatomical primitives (sloping shoulder traps, deltoid + arm chain, kneecaps, belt with stitching and buckle),
# per-material shader functions, procedural surface detail (suit weave, tie pattern, iris striations, sclera veins,
# tentacle suckers). No mouth: the head leaves a flat region below the nose for a separate talking mouth.
# Bounds are tight: x +-0.75 (arms), y -1.4..1.6 (shoes to crown), z -0.4..0.6 (tentacles push forward).
_HEGE_EXTRA = r"""
        // Material IDs
        #define MAT_SKIN     1.0
        #define MAT_JACKET   2.0
        #define MAT_TROUSER  3.0
        #define MAT_SHOE     4.0
        #define MAT_EYE      5.0
        #define MAT_TENTACLE 6.0
        #define MAT_SHIRT    7.0
        #define MAT_TIE      8.0
        #define MAT_METAL    9.0
        #define MAT_BELT     10.0

        // Aliases / extra helpers used by the original Hege shader
        #define hash31 _hash
        #define noise3 vnoise

        // Variable-octave fbm (loader's fbm() is fixed at 4 octaves)
        float fbmN(vec3 p, int oct) {
            float v = 0.0; float a = 0.5;
            for (int i = 0; i < 6; i++) {
                if (i >= oct) break;
                v += a * vnoise(p);
                p *= 2.05; a *= 0.5;
            }
            return v;
        }

        // Capped open cylinder shell — used for belt and shirt collar
        float sdCylShell(vec3 p, float r, float h) {
            vec2 d = abs(vec2(length(p.xz), p.y)) - vec2(r, h);
            return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
        }

        // 2D rotation matrix
        mat2 rot2(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

        // Smooth union with material — alias to loader's opSmoothU
        vec2 opSmin(vec2 a, vec2 b, float k) { return opSmoothU(a, b, k); }

        // Per-material shading functions (factored out of main lighting)
        void shadeSkin(vec3 p, vec3 n, bool isTentacle, out vec3 albedo, out float roughness) {
            vec3 baseRed = vec3(0.62, 0.10, 0.07);
            vec3 deepRed = vec3(0.22, 0.03, 0.02);
            vec3 highRed = vec3(0.88, 0.35, 0.25);
            float n1 = fbmN(p * 4.0, 4);
            float n2 = fbmN(p * 14.0 + vec3(71.0), 3);
            float mottle = smoothstep(0.28, 0.72, n1);
            albedo = mix(deepRed, baseRed, mottle);
            albedo = mix(albedo, highRed, smoothstep(0.55, 0.72, n2) * 0.45);
            float pore = smoothstep(0.6, 0.78, fbmN(p * 45.0, 2));
            albedo = mix(albedo, deepRed * 0.4, pore * 0.55);
            float rim = 1.0 - abs(dot(n, normalize(cameraPosition - p)));
            albedo += vec3(-0.05, 0.03, 0.08) * smoothstep(0.6, 1.0, rim) * 0.25;

            if (!isTentacle) {
                vec3 hp = p - vec3(0.0, 1.2, 0.0);
                float headSway = sin(uTime * 0.5) * 0.08;
                hp.xz = rot2(headSway) * hp.xz;
                vec2 ebL = hp.xy - vec2(-0.13, 0.07);
                vec2 ebR = hp.xy - vec2( 0.13, 0.07);
                float dL = length(ebL / vec2(0.07, 0.022));
                float dR = length(ebR / vec2(0.07, 0.022));
                float eyebrow = 1.0 - smoothstep(0.6, 1.0, min(dL, dR));
                eyebrow *= smoothstep(0.18, 0.22, hp.z);
                albedo = mix(albedo, vec3(0.05, 0.015, 0.01), eyebrow * 0.7);
            } else {
                float band = sin(p.y * 36.0) * 0.5 + 0.5;
                albedo = mix(albedo, albedo * 0.55, band * 0.35);
                albedo *= vec3(0.95, 1.0, 1.0);
                float suckers = smoothstep(0.7, 0.85, fbmN(p * 28.0, 2));
                albedo = mix(albedo, vec3(0.95, 0.85, 0.78), suckers * 0.3);
            }
            roughness = 0.42 + n1 * 0.25;
        }

        void shadeJacket(vec3 p, vec3 n, out vec3 albedo, out float roughness) {
            albedo = vec3(0.045, 0.045, 0.055);
            float weave = fbmN(p * 140.0, 2);
            albedo += vec3(weave * 0.025);
            float diag = sin((p.x * 2.0 + p.y) * 180.0);
            albedo += vec3(max(0.0, diag) * 0.012);
            // Wool suit cloth — matte. Lapels keep a touch more sheen
            // (silk-faced) but stop short of plasticky.
            bool inLapelZone = (p.y > 0.23 && p.y < 0.8 && abs(p.x) > 0.05 && abs(p.x) < 0.25 && p.z > 0.21);
            roughness = inLapelZone ? 0.78 : 0.92;
        }

        void shadeShirt(vec3 p, out vec3 albedo, out float roughness) {
            albedo = vec3(0.93, 0.93, 0.89);
            float weave = fbmN(p * 160.0, 2);
            albedo -= vec3(weave * 0.05);
            float rib = sin(p.y * 280.0) * 0.5 + 0.5;
            albedo -= vec3(rib * 0.018);
            roughness = 0.78;
        }

        void shadeTie(vec3 p, out vec3 albedo, out float roughness) {
            vec3 base = vec3(0.42, 0.06, 0.08);
            vec3 dark = vec3(0.18, 0.02, 0.03);
            vec3 gold = vec3(0.85, 0.7, 0.35);
            float stripeCoord = (p.y * 1.5 + p.x * 1.0) * 28.0;
            float wide = sin(stripeCoord) * 0.5 + 0.5;
            wide = smoothstep(0.4, 0.6, wide);
            albedo = mix(base, dark, wide);
            float thin = sin(stripeCoord * 0.25 + 1.0) * 0.5 + 0.5;
            if (thin > 0.86 && wide > 0.7) albedo = gold;
            float silk = fbmN(p * 80.0, 2);
            albedo += vec3(silk * 0.04, silk * 0.01, silk * 0.005);
            // Silk has SOME sheen, but the previous 0.32 over-shone next
            // to a matte wool suit and read as plastic. Knock it back.
            roughness = 0.55;
        }

        void shadeShoe(vec3 p, out vec3 albedo, out float roughness) {
            albedo = vec3(0.03, 0.025, 0.03);
            float grain = fbmN(p * 90.0, 3);
            albedo += vec3(grain * 0.04);
            roughness = 0.22 + grain * 0.1;
        }

        void shadeBelt(vec3 p, out vec3 albedo, out float roughness) {
            albedo = vec3(0.03, 0.022, 0.022);
            float grain = fbmN(p * 110.0, 3);
            albedo += vec3(grain * 0.05);
            float beltLocalY = p.y - 0.04;
            float topLine = 1.0 - smoothstep(0.0, 0.0035, abs(beltLocalY - 0.022));
            float botLine = 1.0 - smoothstep(0.0, 0.0035, abs(beltLocalY + 0.022));
            float stitch = max(topLine, botLine);
            float angleAround = atan(p.z, p.x);
            float dots = sin(angleAround * 220.0) * 0.5 + 0.5;
            dots = smoothstep(0.55, 0.7, dots);
            stitch *= dots;
            albedo = mix(albedo, vec3(0.32, 0.26, 0.18), stitch * 0.5);
            roughness = 0.42 + grain * 0.12;
        }

        void shadeTrouser(vec3 p, vec3 n, out vec3 albedo, out float roughness) {
            albedo = vec3(0.045, 0.045, 0.055);
            float weave = fbmN(p * 130.0, 2);
            albedo += vec3(weave * 0.025);
            float legCenterX = sign(p.x) * 0.18;
            float distToCrease = abs(p.x - legCenterX);
            float crease = 1.0 - smoothstep(0.0, 0.02, distToCrease);
            crease *= smoothstep(0.0, 0.06, p.z);
            crease *= smoothstep(-1.3, -0.1, p.y) * (1.0 - smoothstep(-0.6, 0.0, p.y));
            albedo += vec3(crease * 0.045);
            // Wool trousers — same matte register as the jacket.
            roughness = 0.92 + weave * 0.05;
        }

        void shadeMetal(out vec3 albedo, out float roughness) {
            // Polished steel/chrome buckle — bright neutral F0 tint.
            // The lighting path detects MAT_METAL and uses albedo as the
            // specular reflectance directly instead of as diffuse colour.
            albedo = vec3(0.92, 0.91, 0.88);
            roughness = 0.10;
        }

        void shadeEye(vec3 p, vec3 n, out vec3 albedo, out float roughness) {
            vec3 headC = vec3(0.0, 1.2, 0.0);
            float headSway = sin(uTime * 0.5) * 0.08;
            vec3 hp = p - headC;
            hp.xz = rot2(-headSway) * hp.xz;
            vec3 eL = hp - vec3(-0.12, -0.02, 0.24);
            vec3 eR = hp - vec3( 0.12, -0.02, 0.24);
            vec3 eLocal = length(eL) < length(eR) ? eL : eR;
            float isLeft = length(eL) < length(eR) ? 1.0 : -1.0;
            vec3 dir = normalize(eLocal);
            vec3 fwd = normalize(vec3(-isLeft * 0.15, -0.08, 1.0));
            vec3 up  = normalize(vec3(0, 1, 0) - fwd * dot(vec3(0,1,0), fwd));
            vec3 rt  = cross(up, fwd);
            float nF = dot(dir, fwd);
            float nU = dot(dir, up);
            float nR = dot(dir, rt);
            if (nF < 0.0) {
                albedo = vec3(0.05, 0.02, 0.02);
                roughness = 0.3;
                return;
            }
            float slitEllipse = (nU * nU) / 0.008 + (nR * nR) / 0.2;
            float irisR = sqrt(nU * nU + nR * nR);
            if (slitEllipse < 1.0) {
                albedo = vec3(0.008, 0.008, 0.01);
                roughness = 0.08;
            } else if (irisR < 0.48) {
                float theta = atan(nU, nR);
                float stria = sin(theta * 38.0) * 0.5 + 0.5;
                stria *= sin(theta * 11.0) * 0.5 + 0.5;
                vec3 iris1 = vec3(0.88, 0.58, 0.08);
                vec3 iris2 = vec3(0.42, 0.22, 0.015);
                vec3 irisOuter = vec3(0.65, 0.32, 0.03);
                float radial = smoothstep(0.0, 0.48, irisR);
                albedo = mix(iris1, iris2, stria * 0.5);
                albedo = mix(albedo, irisOuter, radial * 0.5);
                albedo = mix(albedo, vec3(0.08, 0.04, 0.01), smoothstep(0.42, 0.48, irisR));
                roughness = 0.1;
            } else {
                vec3 scleraBase = vec3(0.72, 0.55, 0.45);
                float veinNoise = fbmN(dir * 12.0, 3);
                float vein = smoothstep(0.55, 0.72, veinNoise);
                albedo = mix(scleraBase, vec3(0.55, 0.08, 0.06), vein * 0.55);
                albedo = mix(albedo, vec3(0.8, 0.7, 0.3), 0.15);
                roughness = 0.15;
            }
        }

        // (Blender edition) the material dispatch shade() opens with, shared with surface()
        void hegeMaterial(vec3 p, vec3 n, float mat, out vec3 albedo, out float roughness) {
            int matID = int(mat + 0.5);
            albedo = vec3(0.5);
            roughness = 0.5;
            if      (matID == int(MAT_SKIN))     shadeSkin(p, n, false, albedo, roughness);
            else if (matID == int(MAT_TENTACLE)) shadeSkin(p, n, true,  albedo, roughness);
            else if (matID == int(MAT_JACKET))   shadeJacket(p, n, albedo, roughness);
            else if (matID == int(MAT_TROUSER))  shadeTrouser(p, n, albedo, roughness);
            else if (matID == int(MAT_SHOE))     shadeShoe(p, albedo, roughness);
            else if (matID == int(MAT_EYE))      shadeEye(p, n, albedo, roughness);
            else if (matID == int(MAT_SHIRT))    shadeShirt(p, albedo, roughness);
            else if (matID == int(MAT_TIE))      shadeTie(p, albedo, roughness);
            else if (matID == int(MAT_METAL))    shadeMetal(albedo, roughness);
            else if (matID == int(MAT_BELT))     shadeBelt(p, albedo, roughness);
        }
"""

_HEGE_MAP = r"""
        vec2 map(vec3 p) {
            float headSway = sin(uTime * 0.5) * 0.08;
            vec2 result = vec2(1e10, 0.0);

            // === LEGS (trousers) ===
            vec3 hipL = vec3(-0.16, -0.05, 0.0);
            vec3 hipR = vec3( 0.16, -0.05, 0.0);
            vec3 kneeL = vec3(-0.18, -0.65, 0.05);
            vec3 kneeR = vec3( 0.18, -0.65, 0.05);
            vec3 ankleL = vec3(-0.2, -1.28, 0.0);
            vec3 ankleR = vec3( 0.2, -1.28, 0.0);
            float thighL = sdCapsule(p, hipL, kneeL, 0.16);
            float thighR = sdCapsule(p, hipR, kneeR, 0.16);
            float calfL = sdCapsule(p, kneeL, ankleL, 0.13);
            float calfR = sdCapsule(p, kneeR, ankleR, 0.13);
            float kneeBL = sdEllipsoid(p - kneeL, vec3(0.13, 0.1, 0.16));
            float kneeBR = sdEllipsoid(p - kneeR, vec3(0.13, 0.1, 0.16));
            float legs = min(min(thighL, thighR), min(calfL, calfR));
            legs = smin(legs, kneeBL, 0.05);
            legs = smin(legs, kneeBR, 0.05);
            result = vec2(legs, MAT_TROUSER);

            float hips = sdEllipsoid(p - vec3(0.0, -0.05, 0.0), vec3(0.32, 0.16, 0.22));
            result = opSmin(result, vec2(hips, MAT_TROUSER), 0.1);

            float shoeL = sdEllipsoid(p - vec3(-0.2, -1.32, 0.08), vec3(0.13, 0.06, 0.22));
            float shoeR = sdEllipsoid(p - vec3( 0.2, -1.32, 0.08), vec3(0.13, 0.06, 0.22));
            result = opSmin(result, vec2(min(shoeL, shoeR), MAT_SHOE), 0.025);

            // === BELT ===
            vec3 bp = p - vec3(0.0, 0.04, 0.0);
            float belt = sdCylShell(bp, 0.32, 0.03);
            result = opU(result, vec2(belt, MAT_BELT));

            // === BUCKLE — rectangular frame + center prong ===
            vec3 buckleP = p - vec3(0.0, 0.04, 0.325);
            float bOuter = sdBox(buckleP, vec3(0.055, 0.045, 0.012));
            float bInner = sdBox(buckleP, vec3(0.04, 0.032, 0.02));
            float bFrame = max(bOuter, -bInner);
            float bPost = sdBox(buckleP, vec3(0.004, 0.038, 0.014));
            float buckle = min(bFrame, bPost);
            result = opU(result, vec2(buckle, MAT_METAL));

            // === TORSO ===
            float torsoLower = sdEllipsoid(p - vec3(0.0, 0.25, 0.0), vec3(0.34, 0.3, 0.24));
            float torsoUpper = sdEllipsoid(p - vec3(0.0, 0.55, 0.0), vec3(0.46, 0.3, 0.28));
            float torso = smin(torsoLower, torsoUpper, 0.18);
            float pecL = sdEllipsoid(p - vec3(-0.16, 0.5, 0.2), vec3(0.13, 0.08, 0.07));
            float pecR = sdEllipsoid(p - vec3( 0.16, 0.5, 0.2), vec3(0.13, 0.08, 0.07));
            torso = smin(torso, pecL, 0.07);
            torso = smin(torso, pecR, 0.07);
            result = opSmin(result, vec2(torso, MAT_JACKET), 0.1);

            // === SHOULDERS — trapezius + deltoid ===
            float trapL = sdCapsule(p, vec3(0.0, 0.78, 0.0), vec3(-0.42, 0.68, 0.0), 0.13);
            float trapR = sdCapsule(p, vec3(0.0, 0.78, 0.0), vec3( 0.42, 0.68, 0.0), 0.13);
            result = opSmin(result, vec2(min(trapL, trapR), MAT_JACKET), 0.14);

            vec3 delLP = vec3(-0.5, 0.62, 0.0);
            vec3 delRP = vec3( 0.5, 0.62, 0.0);
            float delL = sdSphere(p - delLP, 0.17);
            float delR = sdSphere(p - delRP, 0.17);
            result = opSmin(result, vec2(min(delL, delR), MAT_JACKET), 0.16);

            // === ARMS ===
            vec3 elbL = vec3(-0.55, 0.18, 0.08);
            vec3 elbR = vec3( 0.55, 0.18, 0.08);
            float uArmL = sdCapsule(p, delLP, elbL, 0.115);
            float uArmR = sdCapsule(p, delRP, elbR, 0.115);
            result = opSmin(result, vec2(min(uArmL, uArmR), MAT_JACKET), 0.08);

            vec3 wrsL = vec3(-0.42, -0.32, 0.22);
            vec3 wrsR = vec3( 0.42, -0.32, 0.22);
            float lArmL = sdCapsule(p, elbL, wrsL, 0.095);
            float lArmR = sdCapsule(p, elbR, wrsR, 0.095);
            result = opSmin(result, vec2(min(lArmL, lArmR), MAT_JACKET), 0.06);

            // Shirt cuffs
            float shCuffL = sdCapsule(p, wrsL + vec3(0.0, -0.005, 0.0), wrsL + vec3(0.02, -0.06, 0.02), 0.1);
            float shCuffR = sdCapsule(p, wrsR + vec3(0.0, -0.005, 0.0), wrsR + vec3(-0.02, -0.06, 0.02), 0.1);
            result = opU(result, vec2(min(shCuffL, shCuffR), MAT_SHIRT));

            // Hands
            float handL = sdEllipsoid(p - vec3(-0.43, -0.45, 0.24), vec3(0.075, 0.13, 0.05));
            float handR = sdEllipsoid(p - vec3( 0.43, -0.45, 0.24), vec3(0.075, 0.13, 0.05));
            result = opSmin(result, vec2(min(handL, handR), MAT_SKIN), 0.025);

            // === LAPELS ===
            vec3 lpL = p - vec3(-0.13, 0.5, 0.255);
            lpL.xy = rot2(0.3) * lpL.xy;
            float lapelL = sdEllipsoid(lpL, vec3(0.075, 0.27, 0.013));
            vec3 lpR = p - vec3(0.13, 0.5, 0.255);
            lpR.xy = rot2(-0.3) * lpR.xy;
            float lapelR = sdEllipsoid(lpR, vec3(0.075, 0.27, 0.013));
            result = opU(result, vec2(min(lapelL, lapelR), MAT_JACKET));

            // === SHIRT (collar + plate between lapels) ===
            vec3 cp2 = p - vec3(0.0, 0.83, 0.0);
            float collar = sdCylShell(cp2, 0.16, 0.045);
            result = opU(result, vec2(collar, MAT_SHIRT));
            // Plate widened so a V-shape of white reads on either side
            // of the tie shaft (tie is x +-0.05; plate now spans x +-0.10).
            // Pushed forward slightly so it sits proud of the lapel layer
            // and survives the underwater depth fade.
            vec3 spv = p - vec3(0.0, 0.5, 0.272);
            float shirtPlate = sdEllipsoid(spv, vec3(0.10, 0.20, 0.014));
            result = opU(result, vec2(shirtPlate, MAT_SHIRT));

            // === TIE — knot + tapered shaft ending at the belt ===
            float tieKnot = sdEllipsoid(p - vec3(0.0, 0.55, 0.285), vec3(0.05, 0.05, 0.025));
            vec3 tp = p - vec3(0.0, 0.3, 0.28);
            float taperFac = mix(0.6, 1.0, smoothstep(-0.22, 0.22, tp.y));
            tp.x /= taperFac;
            float tieShaft = sdEllipsoid(tp, vec3(0.05, 0.22, 0.015));
            float tie = smin(tieKnot, tieShaft, 0.04);
            result = opU(result, vec2(tie, MAT_TIE));

            // (Pocket-square primitive removed — was reading as a hovering
            //  white ellipsoid in front of the chest next to the tentacles.)

            // Cufflinks
            float clL = sdSphere(p - vec3(-0.42, -0.28, 0.27), 0.018);
            float clR = sdSphere(p - vec3( 0.42, -0.28, 0.27), 0.018);
            result = opU(result, vec2(min(clL, clR), MAT_METAL));

            // Neck
            float neck = sdCapsule(p, vec3(0.0, 0.78, 0.0), vec3(0.0, 0.95, 0.0), 0.11);
            result = opSmin(result, vec2(neck, MAT_SKIN), 0.08);

            // === HEAD ===
            vec3 headC = vec3(0.0, 1.2, 0.0);
            vec3 hp = p - headC;
            hp.xz = rot2(headSway) * hp.xz;

            float cranium = sdEllipsoid(hp - vec3(0.0, 0.05, 0.0), vec3(0.25, 0.29, 0.29));
            float jaw = sdEllipsoid(hp - vec3(0.0, -0.22, 0.04), vec3(0.16, 0.12, 0.16));
            float head = smin(cranium, jaw, 0.1);
            float brow = sdEllipsoid(hp - vec3(0.0, 0.1, 0.24), vec3(0.24, 0.045, 0.07));
            head = smin(head, brow, 0.04);
            float ckL = sdEllipsoid(hp - vec3(-0.16, -0.08, 0.16), vec3(0.09, 0.07, 0.09));
            float ckR = sdEllipsoid(hp - vec3( 0.16, -0.08, 0.16), vec3(0.09, 0.07, 0.09));
            head = smin(head, ckL, 0.06);
            head = smin(head, ckR, 0.06);
            float nose = sdEllipsoid(hp - vec3(0.0, -0.02, 0.27), vec3(0.035, 0.085, 0.05));
            head = smin(head, nose, 0.03);
            result = opSmin(result, vec2(head, MAT_SKIN), 0.05);

            // Eyes (no mouth — agent attaches a viseme three.js mesh below the nose)
            vec3 eyeLocalL = vec3(-0.12, -0.02, 0.24);
            vec3 eyeLocalR = vec3( 0.12, -0.02, 0.24);
            vec2 eL2 = rot2(-headSway) * eyeLocalL.xz;
            vec2 eR2 = rot2(-headSway) * eyeLocalR.xz;
            vec3 eWorldL = headC + vec3(eL2.x, eyeLocalL.y, eL2.y);
            vec3 eWorldR = headC + vec3(eR2.x, eyeLocalR.y, eR2.y);
            float eL = sdSphere(p - eWorldL, 0.07);
            float eR = sdSphere(p - eWorldR, 0.07);
            result = opU(result, vec2(min(eL, eR), MAT_EYE));

            // Tentacles — 6 strands hanging off the lower face, animated wiggle
            float tentMin = 1e10;
            for (int i = 0; i < 6; i++) {
                float fi = float(i);
                float u = (fi - 2.5) / 2.5;
                vec3 originLocal = vec3(u * 0.13, -0.3, 0.16);
                vec2 oxz = rot2(-headSway) * originLocal.xz;
                vec3 origin = headC + vec3(oxz.x, originLocal.y, oxz.y);
                float tLen = 0.7 + fract(fi * 0.731) * 0.4;
                float phase = fi * 1.8;
                vec3 q = p - origin;
                float s = clamp(-q.y / tLen, 0.0, 1.0);
                float forwardPush = 0.28 * pow(s, 0.45);
                float lateralSpread = u * 0.18 * pow(s, 0.7);
                float wigX = sin(uTime * 3.0 + phase + s * 6.0) * 0.05 * s;
                float wigZ = cos(uTime * 2.5 + phase * 1.3 + s * 4.0) * 0.05 * s;
                vec3 centerline = vec3(
                    lateralSpread + wigX,
                    -s * tLen,
                    forwardPush + wigZ
                );
                float dist = length(q - centerline);
                float thick = mix(0.05, 0.012, s);
                tentMin = min(tentMin, dist - thick);
            }
            result = opSmin(result, vec2(tentMin, MAT_TENTACLE), 0.025);

            return result;
        }"""

_HEGE_SHADE = r"""
        vec3 shade(vec3 p, vec3 n, float mat) {
            int matID = int(mat + 0.5);
            vec3 albedo = vec3(0.5);
            float roughness = 0.5;

            if      (matID == int(MAT_SKIN))     shadeSkin(p, n, false, albedo, roughness);
            else if (matID == int(MAT_TENTACLE)) shadeSkin(p, n, true,  albedo, roughness);
            else if (matID == int(MAT_JACKET))   shadeJacket(p, n, albedo, roughness);
            else if (matID == int(MAT_TROUSER))  shadeTrouser(p, n, albedo, roughness);
            else if (matID == int(MAT_SHOE))     shadeShoe(p, albedo, roughness);
            else if (matID == int(MAT_EYE))      shadeEye(p, n, albedo, roughness);
            else if (matID == int(MAT_SHIRT))    shadeShirt(p, albedo, roughness);
            else if (matID == int(MAT_TIE))      shadeTie(p, albedo, roughness);
            else if (matID == int(MAT_METAL))    shadeMetal(albedo, roughness);
            else if (matID == int(MAT_BELT))     shadeBelt(p, albedo, roughness);

            // Lighting
            vec3 lKey = normalize(vec3(5.0, 8.0, 5.0));
            vec3 lRim = normalize(vec3(-4.0, 3.0, -6.0));
            vec3 v = normalize(cameraPosition - p);
            float shadow = softShadow(p + n * 0.002, lKey, 0.02, 5.0, 12.0);
            float NdotLk = max(dot(n, lKey), 0.0);
            float NdotLr = max(dot(n, lRim), 0.0);
            float NdotV  = max(dot(n, v), 0.0);
            vec3 hKey = normalize(v + lKey);
            float NdotHk = max(dot(n, hKey), 0.0);
            float specPow = mix(1.0, 256.0, 1.0 - roughness);
            float specK = pow(NdotHk, specPow) * (1.0 - roughness) * 0.85;
            // Key light tuned to coexist with HDRI-driven ambient. The
            // old *2.0 multiplier was calibrated for a hardcoded
            // procedural sky and overpowers HDRI ambient — sun-facing
            // panels (jacket shoulders, etc.) read as glossy because
            // the directional contribution dominates the scene.
            vec3 keyColor = vec3(1.0, 0.94, 0.85) * 1.1;
            vec3 rimColor = vec3(0.35, 0.5, 0.85) * 0.9;
            // IBL-style ambient sampled from the actual scene HDRI.
            // Sky/ground samples taken at world-up/down so they track
            // the agent's scene environment instead of a baked colour;
            // mix factor uses world-space normal so the gradient
            // doesn't rotate with the SDF mesh's parent.
            vec3 skyCol    = sampleEnvMap(vec3(0.0, 1.0, 0.0));
            vec3 groundCol = sampleEnvMap(vec3(0.0, -1.0, 0.0));
            vec3 nWorld    = normalize(mat3(uModelMatrix) * n);
            vec3 ambient = mix(groundCol, skyCol, nWorld.y * 0.5 + 0.5) * 0.4 * albedo;
            float fres = pow(1.0 - NdotV, 4.0);

            // Pure metal branch — albedo is F0 (specular reflectance),
            // there is no diffuse term, and Fresnel pushes glancing
            // angles up toward white so the buckle catches the rim
            // light and reads as a polished surface, not painted.
            if (matID == int(MAT_METAL)) {
                vec3 F0 = albedo;
                vec3 Fspec = mix(F0, vec3(1.0), fres);
                vec3 specMetal = Fspec * specK * keyColor * shadow * 1.6;
                // Sample the actual HDRI at the world-space reflection
                // direction so the metal catches whatever's around it.
                vec3 envHi = sampleEnvMap(sdfReflectWorld(p, n));
                vec3 reflEnv = F0 * envHi * (0.4 + fres * 0.9);
                vec3 rimSpec = F0 * NdotLr * rimColor * 0.25;
                return specMetal + reflEnv + rimSpec;
            }

            // Wrap-style diffuse term — lets light bleed past the
            // terminator so dark wool doesn't show a sharp bright/dark
            // gradient on curved surfaces (which reads as silky sheen).
            // Real wool is partly subsurface; this approximates that
            // diffusion without a full SSS pass.
            float NdotLk_wrap = clamp((NdotLk + 0.4) / 1.4, 0.0, 1.0);
            vec3 diffuse = albedo * NdotLk_wrap * keyColor * shadow;
            // Dielectric spec, killed entirely for very rough surfaces
            // (wool / cotton / matte skin). Even F0=0.04 with Schlick
            // boost was producing a visible glossy ridge on curved
            // cloth under bright HDRI lighting — the perceived "silk
            // sheen" the user kept calling out. Mid-rough materials
            // (silk tie, leather shoe, eye sclera) keep their spec.
            vec3 F0diel = vec3(0.04);
            vec3 Fspec = F0diel + (vec3(1.0) - F0diel) * fres;
            float specRoughDamp = 1.0 - smoothstep(0.45, 0.85, roughness);
            vec3 spec = Fspec * specK * keyColor * shadow * specRoughDamp;
            vec3 rimDiff = albedo * NdotLr * rimColor * 0.35;

            // SSS-ish wrap term for skin and tentacles
            if (matID == int(MAT_SKIN) || matID == int(MAT_TENTACLE)) {
                float wrap = pow(max(dot(-n, -lKey), 0.0) * 0.5 + 0.3, 2.5);
                vec3 sss = albedo * wrap * vec3(0.95, 0.35, 0.3) * 0.28;
                diffuse += sss;
            }

            vec3 color = diffuse + spec + rimDiff + ambient;
            color += vec3(0.4, 0.5, 0.7) * fres * 0.18;
            return color;
        }"""

_HEGE_SURFACE = r"""
        SdfSurface surface(vec3 p, vec3 n, float mat) {
            vec3 albedo; float roughness;
            hegeMaterial(p, n, mat, albedo, roughness);
            int matID = int(mat + 0.5);
            SdfSurface s = sdfSurface(albedo, roughness);
            if (matID == int(MAT_METAL)) {
                s.metallic = 1.0;                       // the pure-metal branch: albedo is F0
            } else if (matID == int(MAT_SKIN) || matID == int(MAT_TENTACLE)) {
                s.subsurface = 0.35;                    // the wrap "SSS" term, (0.95, 0.35, 0.30): real subsurface
            } else if (matID == int(MAT_JACKET) || matID == int(MAT_TROUSER)) {
                s.sheen = 0.35;                         // wool: wrap diffuse, highlight killed (specRoughDamp)
                s.sheenTint = vec3(0.55, 0.58, 0.68);
                s.specular = 0.25;
            } else if (matID == int(MAT_SHIRT)) {
                s.sheen = 0.25;
                s.specular = 0.35;
            } else if (matID == int(MAT_TIE)) {
                s.sheen = 0.45;                         // silk
                s.sheenTint = vec3(1.0, 0.7, 0.7);
            } else if (matID == int(MAT_EYE)) {
                s.coat = 1.0;                           // the wet cornea over iris and sclera
            } else if (matID == int(MAT_SHOE)) {
                s.coat = 0.35;                          // polished leather
            }
            return s;
        }"""

register_example(
    'mr_hege', kind='solid', animated=True,
    description='Mr. Hege (humanoid in suit): octopus-man in a wool suit with animated tentacles hanging off the '
                'lower face; anatomical primitives, per-material shading, procedural surface detail',
    bounds={'min': [-0.75, -1.40, -0.40], 'max': [0.75, 1.60, 0.60]},
    quality='high',
    extra=_HEGE_EXTRA, map=_HEGE_MAP, shade=_HEGE_SHADE, surface=_HEGE_SURFACE,
    material_settings={'subsurface_radius': (1.0, 0.25, 0.15), 'subsurface_scale': 0.02, 'sheen_roughness': 0.45},
)

# =============================================================================================== redShoggoth ===
# Red Shoggoth (eldritch blob with blue angry-face mask): a 5-lump irregular blob covered in 48 darting eyes (24 on
# the body, 24 on the tentacles, all blinking on independent intervals), with 12 tentacles in three groups (4
# dangling, 4 horizontal arms, 4 waving up). A ceramic blue mask with carved angry brow and frown sits on the front
# of the main lump, held on by a thin leather strap circling the lump. Visual reference: red_shoggoth.png (the red
# AI shoggoth meme variant, blue frown mask instead of the usual yellow happy one).
# Bounds: x +-1.7 (horizontal arm tentacles), y -1.1..2.3 (hanging vs. waving-up tentacles), z -0.8..1.7.
_SHOG_EXTRA = r"""
        #define MAT_SKIN  1.0
        #define MAT_EYE   2.0
        #define MAT_MASK  3.0
        #define MAT_STRAP 4.0
        #define PI 3.14159265

        // Animation globals — populated once per map() invocation by
        // computeAnimation(). All inputs are functions of uTime only, so
        // recomputing per ray-march step is cheap and keeps calcNormal
        // / softShadow honest (they all see the same values).
        vec3 G_BODY_CENTER;
        vec3 G_MAIN_LUMP_CENTER;
        vec3 G_MASK_CENTER;
        float G_PULSE;

        const int NUM_LUMPS           = 5;
        const int NUM_TENTS           = 12;
        const int TENT_SAMPLES        = 16;
        const int EYES_LUMP_0         = 4;
        const int EYES_PER_OTHER_LUMP = 5;
        const int EYES_PER_TENT       = 2;
        const int NUM_BODY_EYES       = 24;
        const int NUM_TENT_EYES       = 24;
        const int NUM_EYES            = 48;

        // Variable-octave fbm wrapping the boilerplate vnoise().
        float fbmN(vec3 p, int oct) {
            float v = 0.0; float a = 0.5;
            for (int i = 0; i < 6; i++) {
                if (i >= oct) break;
                v += a * vnoise(p);
                p *= 2.05; a *= 0.5;
            }
            return v;
        }

        // 2D rotation matrix (mask features live in 2D).
        mat2 rot2_xy(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

        // 2D point-to-segment distance — used for mask brow strokes.
        float distSeg2(vec2 p, vec2 a, vec2 b) {
            vec2 pa = p - a, ba = b - a;
            float t = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
            return length(pa - ba * t);
        }

        // Fibonacci-sphere direction sampler — even sphere distribution
        // for scattering eyes around the secondary lumps.
        vec3 fibSphereDir(int i, int N, float seed) {
            float fi = float(i) + 0.5;
            float phi_g = 2.39996;
            float theta = fi * phi_g + seed;
            float y = 1.0 - 2.0 * fi / float(N);
            float r = sqrt(max(1.0 - y * y, 0.0));
            return vec3(r * cos(theta), y, r * sin(theta));
        }

        vec3 lumpCenter(int i) {
            if (i == 0) return G_BODY_CENTER + vec3(-0.05, 0.05, 0.35);
            if (i == 1) return G_BODY_CENTER + vec3( 0.0,  0.05,-0.30);
            if (i == 2) return G_BODY_CENTER + vec3( 0.25,-0.20, 0.05);
            if (i == 3) return G_BODY_CENTER + vec3(-0.25,-0.20, 0.0);
            if (i == 4) return G_BODY_CENTER + vec3( 0.0,  0.25, 0.05);
            return G_BODY_CENTER;
        }
        float lumpRadius(int i) {
            if (i == 0) return 0.40;
            if (i == 1) return 0.30;
            if (i == 2) return 0.26;
            if (i == 3) return 0.26;
            if (i == 4) return 0.22;
            return 0.30;
        }

        void computeAnimation() {
            G_BODY_CENTER      = vec3(sin(uTime * 0.4) * 0.04,
                                      0.4 + sin(uTime * 0.7) * 0.05,
                                      0.0);
            G_PULSE            = 1.0 + sin(uTime * 1.3) * 0.025;
            G_MAIN_LUMP_CENTER = lumpCenter(0);
            G_MASK_CENTER      = G_MAIN_LUMP_CENTER + vec3(0.0, -0.05, lumpRadius(0) * G_PULSE);
        }

        // 12 tentacles in 3 groups of 4: dangling, horizontal arms, waving up.
        void tentParams(int i, out vec3 origin, out vec3 dir, out float len, out float thick) {
            float fi = float(i);
            if (i < 4) {
                float angle = fi * (2.0 * PI / 4.0) + 0.3;
                float lx = cos(angle) * 0.30, lz = sin(angle) * 0.30;
                origin = lumpCenter(0) + vec3(lx, -0.32, lz);
                dir    = normalize(vec3(lx * 0.4, -1.0, lz * 0.4));
                len    = 0.70 + fract(fi * 0.613) * 0.30;
                thick  = 0.10 + fract(fi * 0.413) * 0.05;
            } else if (i < 8) {
                float fj = fi - 4.0;
                float angle = fj * (2.0 * PI / 4.0) + 0.7;
                float lx = cos(angle), lz = sin(angle);
                origin = G_BODY_CENTER + vec3(lx * 0.30, -0.05, lz * 0.30);
                dir    = normalize(vec3(lx, 0.0, lz));
                len    = 0.55 + fract(fj * 0.613) * 0.30;
                thick  = 0.18 + fract(fj * 0.413) * 0.10;
            } else {
                float fj = fi - 8.0;
                float angle = fj * (2.0 * PI / 4.0) + 1.5;
                float lx = cos(angle), lz = sin(angle);
                origin = G_BODY_CENTER + vec3(lx * 0.20, 0.30, lz * 0.20);
                dir    = normalize(vec3(lx * 0.4, 0.9, lz * 0.4));
                len    = 0.65 + fract(fj * 0.613) * 0.45;
                thick  = 0.09 + fract(fj * 0.413) * 0.05;
            }
        }
        float tentRadius(int i, float s, float thick) {
            if (i < 4) return mix(thick, thick * 0.40, s);
            if (i < 8) return mix(thick, thick * 0.65, s);
            return mix(thick, thick * 0.50, s);
        }
        vec3 tentCenterline(int i, float s, vec3 origin, vec3 dir, float len) {
            float phase = float(i) * 1.7;
            vec3 up = abs(dir.y) > 0.9 ? vec3(1, 0, 0) : vec3(0, 1, 0);
            vec3 perp1 = normalize(cross(dir, up));
            vec3 perp2 = normalize(cross(dir, perp1));
            float curve1 = (fract(float(i) * 0.591) - 0.5) * 0.4;
            float curve2 = (fract(float(i) * 0.821) - 0.5) * 0.3;
            vec3 c = origin + dir * (s * len);
            float curveS = s * s;
            c += perp1 * (curve1 * curveS + sin(uTime * 1.5 + phase + s * 3.0) * 0.07 * s);
            c += perp2 * (curve2 * curveS + cos(uTime * 1.2 + phase * 1.3 + s * 2.5) * 0.06 * s);
            if (dir.y < 0.0) c.y -= s * s * 0.10;
            return c;
        }
        // Sphere-chain tentacle. 16 samples x smin = a smooth tube. The
        // first sample skips smin to avoid an artifact at the root.
        float sdTentacleFast(vec3 p, int i, vec3 origin, vec3 dir, float len, float thick) {
            float phase = float(i) * 1.7;
            vec3 up = abs(dir.y) > 0.9 ? vec3(1, 0, 0) : vec3(0, 1, 0);
            vec3 perp1 = normalize(cross(dir, up));
            vec3 perp2 = normalize(cross(dir, perp1));
            float curve1 = (fract(float(i) * 0.591) - 0.5) * 0.4;
            float curve2 = (fract(float(i) * 0.821) - 0.5) * 0.3;
            float d = 1e10;
            for (int j = 0; j < TENT_SAMPLES; j++) {
                float s = float(j) / float(TENT_SAMPLES - 1);
                vec3 c = origin + dir * (s * len);
                float curveS = s * s;
                c += perp1 * (curve1 * curveS + sin(uTime * 1.5 + phase + s * 3.0) * 0.07 * s);
                c += perp2 * (curve2 * curveS + cos(uTime * 1.2 + phase * 1.3 + s * 2.5) * 0.06 * s);
                if (dir.y < 0.0) c.y -= s * s * 0.10;
                float r = tentRadius(i, s, thick);
                float ds = length(p - c) - r;
                if (j == 0) d = ds;
                else        d = smin(d, ds, 0.07);
            }
            return d;
        }

        // === EYE PLACEMENT ===
        vec3 bodyEyePos(int i) {
            if (i < EYES_LUMP_0) {
                // Front-cluster of 4 eyes on the main lump.
                float angle = float(i) * (PI / 2.0) + PI / 4.0;
                vec3 dir = normalize(vec3(cos(angle) * 0.7, sin(angle) * 0.7, 0.6));
                return lumpCenter(0) + dir * lumpRadius(0) * G_PULSE;
            }
            int otherIdx = i - EYES_LUMP_0;
            int lumpIdx = (otherIdx / EYES_PER_OTHER_LUMP) + 1;
            int eyeOnLump = otherIdx - (lumpIdx - 1) * EYES_PER_OTHER_LUMP;
            vec3 dir = fibSphereDir(eyeOnLump, EYES_PER_OTHER_LUMP, float(lumpIdx) * 0.7);
            return lumpCenter(lumpIdx) + dir * lumpRadius(lumpIdx) * G_PULSE;
        }
        float tentEyeS(int eyeOnTent) { return eyeOnTent == 0 ? 0.30 : 0.65; }
        vec3 tentEyePos(int i) {
            int tentIdx = i / EYES_PER_TENT;
            int eyeOnTent = i - tentIdx * EYES_PER_TENT;
            float s = tentEyeS(eyeOnTent);
            vec3 origin, dir; float len, thick;
            tentParams(tentIdx, origin, dir, len, thick);
            vec3 c = tentCenterline(tentIdx, s, origin, dir, len);
            vec3 up = abs(dir.y) > 0.9 ? vec3(1, 0, 0) : vec3(0, 1, 0);
            vec3 perp1 = normalize(cross(dir, up));
            vec3 perp2 = normalize(cross(dir, perp1));
            float angle = float(tentIdx) * 1.7 + float(eyeOnTent) * 1.3 + 0.5;
            vec3 outward = perp1 * cos(angle) + perp2 * sin(angle);
            return c + outward * (tentRadius(tentIdx, s, thick) + 0.020);
        }
        vec3 eyePos(int i) {
            if (i < NUM_BODY_EYES) return bodyEyePos(i);
            return tentEyePos(i - NUM_BODY_EYES);
        }
        float bodyEyeRadius(int i) { return 0.06 + fract(float(i) * 0.397) * 0.03; }
        float tentEyeRadiusF(int i) {
            int tentIdx = i / EYES_PER_TENT;
            int eyeOnTent = i - tentIdx * EYES_PER_TENT;
            float s = tentEyeS(eyeOnTent);
            vec3 origin, dir; float len, thick;
            tentParams(tentIdx, origin, dir, len, thick);
            return min(0.05, tentRadius(tentIdx, s, thick) * 0.85);
        }
        float eyeRadius(int i) {
            if (i < NUM_BODY_EYES) return bodyEyeRadius(i);
            return tentEyeRadiusF(i - NUM_BODY_EYES);
        }
        vec3 eyeRefPoint(int i) {
            if (i < NUM_BODY_EYES) {
                if (i < EYES_LUMP_0) return lumpCenter(0);
                int otherIdx = i - EYES_LUMP_0;
                int lumpIdx = (otherIdx / EYES_PER_OTHER_LUMP) + 1;
                return lumpCenter(lumpIdx);
            }
            int tentIdx = (i - NUM_BODY_EYES) / EYES_PER_TENT;
            int eyeOnTent = (i - NUM_BODY_EYES) - tentIdx * EYES_PER_TENT;
            float s = tentEyeS(eyeOnTent);
            vec3 origin, dir; float len, thick;
            tentParams(tentIdx, origin, dir, len, thick);
            return tentCenterline(tentIdx, s, origin, dir, len);
        }
        float sdAllEyes(vec3 p) {
            float minD = 1e10;
            for (int i = 0; i < NUM_EYES; i++) {
                float d = sdSphere(p - eyePos(i), eyeRadius(i));
                minD = min(minD, d);
            }
            return minD;
        }
        // 0..1 progress through a blink for eye i, or -1 if not currently
        // blinking. Per-eye intervals so the population blinks asynchronously.
        float eyeBlinkProg(int i) {
            float fc = float(i);
            float interval = 3.0 + fract(fc * 0.711) * 4.0;
            float offset = fc * 0.3;
            float t2 = uTime + offset;
            float cyclePos = mod(t2, interval);
            if (cyclePos < 0.18) return cyclePos / 0.18;
            return -1.0;
        }

        // === BODY ===
        float sdBody(vec3 p) {
            float d = sdSphere(p - lumpCenter(0), lumpRadius(0) * G_PULSE);
            for (int i = 1; i < NUM_LUMPS; i++) {
                float lump = sdSphere(p - lumpCenter(i), lumpRadius(i) * G_PULSE);
                d = smin(d, lump, 0.06);
            }
            // Surface noise band only near the silhouette so empty-space
            // raymarcher steps stay long.
            float noiseBlend = 1.0 - smoothstep(0.05, 0.15, d);
            if (noiseBlend > 0.0) {
                vec3 q = p - G_BODY_CENTER;
                d -= (vnoise(q * 4.5) - 0.5) * 0.020 * noiseBlend;
            }
            return d;
        }

        float sdMaskShape(vec3 p) {
            vec3 q = p - G_MASK_CENTER;
            q.xy = rot2_xy(0.05) * q.xy;
            q.yz = rot2_xy(-0.10) * q.yz;
            return sdEllipsoid(q, vec3(0.16, 0.18, 0.06));
        }
        float sdStrap(vec3 p) {
            vec3 q = p - G_MAIN_LUMP_CENTER;
            q.yz = rot2_xy(-0.10) * q.yz;
            float R = lumpRadius(0) * G_PULSE;
            return sdTorus(q, vec2(R, 0.018));
        }

        // Body+tents only — used by the soft-shadow tracer. Skipping eye
        // spheres in shadow rays trades imperceptible detail for a 3-5x
        // shadow speedup.
        float mapShadowShog(vec3 p) {
            float d = sdSphere(p - lumpCenter(0), lumpRadius(0) * G_PULSE);
            for (int i = 1; i < NUM_LUMPS; i++) {
                float lump = sdSphere(p - lumpCenter(i), lumpRadius(i) * G_PULSE);
                d = smin(d, lump, 0.06);
            }
            float tents = 1e10, minBound = 1e10;
            for (int i = 0; i < NUM_TENTS; i++) {
                vec3 origin, dir; float len, thick;
                tentParams(i, origin, dir, len, thick);
                vec3 pa = p - origin;
                float h = clamp(dot(pa, dir) / len, 0.0, 1.0);
                float boundDist = length(pa - dir * (len * h)) - (thick * 0.65 + 0.38);
                if (boundDist < 0.25) tents = min(tents, sdTentacleFast(p, i, origin, dir, len, thick));
                else                  minBound = min(minBound, boundDist);
            }
            return smin(d, min(tents, minBound), 0.10);
        }
        float shogShadow(vec3 ro, vec3 rd) {
            float res = 1.0;
            float t = 0.05;
            for (int i = 0; i < 14; i++) {
                float h = mapShadowShog(ro + rd * t);
                res = min(res, 10.0 * h / t);
                t += clamp(h, 0.02, 0.2);
                if (h < 0.001 || t > 5.0) break;
            }
            return clamp(res, 0.25, 1.0);
        }

        // === MATERIAL SHADERS ===
        void shadeShogSkin(vec3 p, vec3 n, out vec3 albedo, out float roughness) {
            vec3 q = p - G_BODY_CENTER;
            vec3 baseRed = vec3(0.78, 0.22, 0.18);
            vec3 deepRed = vec3(0.32, 0.05, 0.04);
            vec3 highRed = vec3(0.95, 0.45, 0.35);
            float n1 = fbmN(q * 4.0, 3);
            float n2 = fbmN(q * 14.0 + vec3(71.0), 2);
            float mottle = smoothstep(0.28, 0.72, n1);
            albedo = mix(deepRed, baseRed, mottle);
            albedo = mix(albedo, highRed, smoothstep(0.55, 0.72, n2) * 0.45);
            float pore = smoothstep(0.6, 0.78, fbmN(q * 30.0, 2));
            albedo = mix(albedo, deepRed * 0.5, pore * 0.6);
            // Darken near body-eye sockets.
            float minNd = 1e10;
            for (int i = 0; i < NUM_BODY_EYES; i++) {
                float d = length(p - bodyEyePos(i)) / bodyEyeRadius(i);
                minNd = min(minNd, d);
            }
            float socket = 1.0 - smoothstep(1.0, 2.5, minNd);
            albedo *= mix(1.0, 0.4, socket);
            roughness = 0.5 + n1 * 0.2;
        }

        void shadeShogEye(vec3 p, vec3 n, out vec3 albedo, out float roughness) {
            // Find which eye sphere we're closest to (in normalised radius).
            int closest = 0;
            float minND = 1e10;
            for (int i = 0; i < NUM_EYES; i++) {
                float d = length(p - eyePos(i)) / eyeRadius(i);
                if (d < minND) { minND = d; closest = i; }
            }
            vec3 ep = eyePos(closest);
            vec3 ref = eyeRefPoint(closest);
            vec3 baseLook = normalize(ep - ref);
            float fc = float(closest);
            float t2 = uTime * 0.3;
            // Per-eye gaze jitter — the "darting eyes" look.
            vec3 perturb = vec3(
                sin(t2 * 1.3 + fc * 1.7) * 0.4,
                cos(t2 * 0.8 + fc * 2.3) * 0.3,
                sin(t2 * 1.2 + fc * 3.1) * 0.3
            );
            vec3 lookDir = normalize(baseLook + perturb);
            vec3 eyeNormal = normalize(p - ep);
            float pupilDot = dot(eyeNormal, lookDir);
            vec3 outward = normalize(ep - ref);
            float rimDot = dot(eyeNormal, outward);
            if (pupilDot > 0.65)   { albedo = vec3(0.04, 0.03, 0.04); roughness = 0.10; }
            else if (rimDot < 0.3) { albedo = vec3(0.05, 0.04, 0.05); roughness = 0.50; }
            else                   { albedo = vec3(0.96, 0.94, 0.88); roughness = 0.25; }
            // Eyelid sweep across the eye sphere when this eye is blinking.
            float blinkProg = eyeBlinkProg(closest);
            if (blinkProg >= 0.0) {
                vec3 worldUp = abs(outward.y) > 0.85 ? vec3(0, 0, 1) : vec3(0, 1, 0);
                vec3 eyeRight = normalize(cross(outward, worldUp));
                vec3 eyeUp = cross(eyeRight, outward);
                float lidProj = dot(eyeNormal, eyeUp);
                float lidLevel = 1.1 - 2.2 * sin(blinkProg * PI);
                if (lidProj > lidLevel) {
                    vec3 skinC = vec3(0.55, 0.10, 0.08);
                    if (abs(lidProj - lidLevel) < 0.04) skinC *= 0.5;
                    albedo = skinC;
                    roughness = 0.5;
                }
            }
        }

        void shadeShogMask(vec3 p, vec3 n, out vec3 albedo, out float roughness) {
            vec3 q = p - G_MASK_CENTER;
            q.xy = rot2_xy(0.05) * q.xy;
            q.yz = rot2_xy(-0.10) * q.yz;
            vec3 baseBlue = vec3(0.22, 0.42, 0.65);
            vec3 darkFeat = vec3(0.04, 0.07, 0.13);
            vec2 mp = q.xy;
            bool isFront = q.z > 0.0;
            float leftBrow  = distSeg2(mp, vec2(-0.13, 0.12), vec2(-0.02, 0.04));
            float rightBrow = distSeg2(mp, vec2( 0.02, 0.04), vec2( 0.13, 0.12));
            bool inBrow = (leftBrow < 0.020 || rightBrow < 0.020);
            bool inEye = (length(mp - vec2(-0.06, 0.0)) < 0.024 ||
                          length(mp - vec2( 0.06, 0.0)) < 0.024);
            float fx = mp.x;
            float frownY = -0.06 - 14.0 * fx * fx;
            bool inFrown = (abs(mp.y - frownY) < 0.020 && abs(fx) < 0.085);
            albedo = (isFront && (inEye || inBrow || inFrown)) ? darkFeat : baseBlue;
            roughness = 0.4;
        }

        void shadeShogStrap(out vec3 albedo, out float roughness) {
            albedo = vec3(0.06, 0.05, 0.10);
            roughness = 0.6;
        }

        // (Blender edition) the material dispatch shade() opens with, shared with surface()
        void shogMaterial(vec3 p, vec3 n, float mat, out vec3 albedo, out float roughness) {
            int matID = int(mat + 0.5);
            albedo = vec3(0.5);
            roughness = 0.5;
            if      (matID == int(MAT_SKIN))  shadeShogSkin(p, n, albedo, roughness);
            else if (matID == int(MAT_EYE))   shadeShogEye(p, n, albedo, roughness);
            else if (matID == int(MAT_MASK))  shadeShogMask(p, n, albedo, roughness);
            else if (matID == int(MAT_STRAP)) shadeShogStrap(albedo, roughness);
        }
"""

_SHOG_MAP = r"""
        vec2 map(vec3 p) {
            computeAnimation();

            float body = sdBody(p);

            // Bounding-capsule per tentacle. If the ray is close to the
            // capsule shell, evaluate the 16-sample tube; otherwise use
            // the safe underestimate (boundDist) as a forward step so
            // the marcher still progresses without tracing every sphere.
            float tents = 1e10;
            float minBound = 1e10;
            for (int i = 0; i < NUM_TENTS; i++) {
                vec3 origin, dir; float len, thick;
                tentParams(i, origin, dir, len, thick);
                vec3 pa = p - origin;
                float h = clamp(dot(pa, dir) / len, 0.0, 1.0);
                float boundDist = length(pa - dir * (len * h)) - (thick * 0.65 + 0.38);
                if (boundDist < 0.25) {
                    tents = min(tents, sdTentacleFast(p, i, origin, dir, len, thick));
                } else {
                    minBound = min(minBound, boundDist);
                }
            }
            tents = min(tents, minBound);

            float skin = smin(body, tents, 0.10);

            // Far from the surface — return the body distance with a
            // constant material; eye / mask / strap detail only matters
            // close to the hit and dominates step cost otherwise.
            if (skin > 0.15) return vec2(skin - 0.12, MAT_SKIN);

            vec2 result = vec2(skin, MAT_SKIN);
            float eyes  = sdAllEyes(p);
            result = opSmoothU(result, vec2(eyes, MAT_EYE), 0.025);
            float strap = sdStrap(p);
            result = opU(result, vec2(strap, MAT_STRAP));
            float mask  = sdMaskShape(p);
            result = opU(result, vec2(mask, MAT_MASK));
            return result;
        }"""

_SHOG_SHADE = r"""
        vec3 shade(vec3 p, vec3 n, float mat) {
            int matID = int(mat + 0.5);
            vec3 albedo = vec3(0.5);
            float roughness = 0.5;
            if      (matID == int(MAT_SKIN))  shadeShogSkin(p, n, albedo, roughness);
            else if (matID == int(MAT_EYE))   shadeShogEye(p, n, albedo, roughness);
            else if (matID == int(MAT_MASK))  shadeShogMask(p, n, albedo, roughness);
            else if (matID == int(MAT_STRAP)) shadeShogStrap(albedo, roughness);

            // Body+tents-only shadow tracer skips the 48 eye spheres.
            vec3 lKey = normalize(vec3(5.0, 8.0, 5.0));
            vec3 lRim = normalize(vec3(-4.0, 3.0, -6.0));
            vec3 v = normalize(cameraPosition - p);
            float shadow = shogShadow(p + n * 0.002, lKey);
            float NdotLk = max(dot(n, lKey), 0.0);
            float NdotLr = max(dot(n, lRim), 0.0);
            float NdotV  = max(dot(n, v), 0.0);
            vec3 hKey = normalize(v + lKey);
            float NdotHk = max(dot(n, hKey), 0.0);
            float specPow = mix(1.0, 256.0, 1.0 - roughness);
            float specK = pow(NdotHk, specPow) * (1.0 - roughness) * 0.85;
            // Key light tuned to coexist with HDRI-driven ambient. The
            // old *2.0 multiplier was calibrated for a hardcoded
            // procedural sky and overpowers HDRI ambient — sun-facing
            // panels (jacket shoulders, etc.) read as glossy because
            // the directional contribution dominates the scene.
            vec3 keyColor = vec3(1.0, 0.94, 0.85) * 1.1;
            vec3 rimColor = vec3(0.35, 0.5, 0.85) * 0.9;
            float fres = pow(1.0 - NdotV, 4.0);
            vec3 diffuse = albedo * NdotLk * keyColor * shadow;
            // Schlick-tinted dielectric spec (F0 = 0.04) + roughness
            // damp that fades the highlight out for very rough surfaces
            // (skin, tentacle membrane). Same mrHege treatment — keeps
            // silk/wet/eye spec at mid-rough, kills band-on-curve from
            // concentrated GGX lobes at rough > 0.9.
            vec3 F0diel = vec3(0.04);
            vec3 Fspec = F0diel + (vec3(1.0) - F0diel) * fres;
            float specRoughDamp = 1.0 - smoothstep(0.6, 0.95, roughness);
            vec3 spec  = Fspec * specK * keyColor * shadow * specRoughDamp;
            vec3 rimDiff = albedo * NdotLr * rimColor * 0.35;
            // Subsurface-style wrap on the meat.
            if (matID == int(MAT_SKIN)) {
                float wrap = pow(max(dot(-n, -lKey), 0.0) * 0.5 + 0.3, 2.5);
                diffuse += albedo * wrap * vec3(0.95, 0.35, 0.3) * 0.30;
            }
            // IBL ambient sampled from the actual scene HDRI — same
            // pattern as mrHege. Sky/ground at world-up/down, mix
            // factor uses world-space normal.
            vec3 skyCol    = sampleEnvMap(vec3(0.0, 1.0, 0.0));
            vec3 groundCol = sampleEnvMap(vec3(0.0, -1.0, 0.0));
            vec3 nWorld    = normalize(mat3(uModelMatrix) * n);
            vec3 ambient = mix(groundCol, skyCol, nWorld.y * 0.5 + 0.5) * 0.4 * albedo;
            vec3 color = diffuse + spec + rimDiff + ambient;
            color += vec3(0.4, 0.5, 0.7) * fres * 0.18;
            return color;
        }"""

_SHOG_SURFACE = r"""
        SdfSurface surface(vec3 p, vec3 n, float mat) {
            vec3 albedo; float roughness;
            shogMaterial(p, n, mat, albedo, roughness);
            int matID = int(mat + 0.5);
            SdfSurface s = sdfSurface(albedo, roughness);
            if (matID == int(MAT_SKIN)) {
                s.subsurface = 0.4;                    // the subsurface-style wrap on the meat
            } else if (matID == int(MAT_EYE)) {
                s.coat = 1.0;                          // wet eyeballs
            } else if (matID == int(MAT_MASK)) {
                s.coat = 0.6;                          // glazed ceramic over the painted face
                s.specular = 0.6;
            } else if (matID == int(MAT_STRAP)) {
                s.sheen = 0.2;                         // leather
            }
            return s;
        }"""

register_example(
    'red_shoggoth', kind='solid', animated=True,
    description="Red Shoggoth: eldritch blob with a blue angry-face mask, 48 darting blinking eyes, 12 tentacles "
                "(Mr. Hege's MemesAI companion, @RedShoggothCult's avatar)",
    bounds={'min': [-1.7, -1.1, -0.8], 'max': [1.7, 2.3, 1.7]},
    quality='high',
    extra=_SHOG_EXTRA, map=_SHOG_MAP, shade=_SHOG_SHADE, surface=_SHOG_SURFACE,
    material_settings={'subsurface_radius': (1.0, 0.3, 0.2), 'subsurface_scale': 0.04},
)


# ================================================================================================= explosion ===
# Pyroclastic fireball (the engine's TSL port, 2026-07-05, of a classic displaced-sphere explosion; it exists only
# as TSL, so this GLSL is written from it node for node). An animated sphere radius carries a rotating-octave fbm
# displacement; the DISPLACEMENT (not a material id) rides the map's mat channel into the shading, where it drives a
# hot-white -> yellow -> red -> smoke gradient. The hot core is emissive (HDR up to 4); the smoky rim takes light.
# The radius pulses on a ~25 s cycle (sin(t * 0.25) + 0.5: it collapses through zero for part of the cycle, as the
# source does) and the noise scrolls down so the fire seems to rise. Live knobs: uSpeed, uNoiseFreq, uNoiseAmp
# (make(speed=, noise_freq=, noise_amp=), the engine's make({speed, noiseFreq, noiseAmp})).
_EXPLOSION_EXTRA = r"""
        // Rotating-octave fbm (distinct from the library fbm): each octave spins through a fixed rotation so the
        // octaves decorrelate, which gives pyroclastic clouds their cauliflower look. The final octave is abs()'d
        // and the total normalised by /0.9375 (faithful to the source).
        vec3 explosionRot(vec3 v) {
            return vec3(v.y * -0.80 + v.z * -0.60,
                        v.x * 0.80 + v.y * 0.36 + v.z * -0.48,
                        v.x * 0.60 + v.y * -0.48 + v.z * 0.64);
        }
        float fbmPyro(vec3 p) {
            float f = vnoise(p) * 0.5000;
            vec3 q = explosionRot(p) * 2.02;
            f += vnoise(q) * 0.2500; q = explosionRot(q) * 2.03;
            f += vnoise(q) * 0.1250; q = explosionRot(q) * 2.01;
            f += vnoise(q) * 0.0625; q = explosionRot(q) * 2.02;
            f += abs(vnoise(q)) * 0.03125;
            return f / 0.9375;
        }
        // the colour gradient lookup (hot white -> yellow -> red -> smoke grey) and the share the light shades
        vec3 explosionColour(float mat, out float lit) {
            float x = clamp(mat * 1.5 - 0.2, 0.0, 0.99);
            float t = fract(x * 3.0);
            vec3 c0 = vec3(4.0, 4.0, 4.0), c1 = vec3(1.0, 1.0, 0.0);
            vec3 c2 = vec3(1.0, 0.0, 0.0), c3 = vec3(0.4, 0.4, 0.4);
            vec3 c = x < 0.3333 ? mix(c0, c1, t) : (x < 0.6666 ? mix(c1, c2, t) : mix(c2, c3, t));
            lit = clamp((x - 0.5) * 2.0, 0.0, 1.0);
            return c;
        }
"""


def _make_explosion(ex, opts=None, **kw):
    """The engine's make({speed, noiseFreq, noiseAmp, ...}): the three knobs become uniforms, the rest pass on."""
    o = dict(opts or {}, **kw)
    u = dict(ex.get('uniforms') or {})
    for key, name in (('speed', 'uSpeed'), ('noise_freq', 'uNoiseFreq'), ('noiseFreq', 'uNoiseFreq'),
                      ('noise_amp', 'uNoiseAmp'), ('noiseAmp', 'uNoiseAmp')):
        if key in o:
            u[name] = float(o.pop(key))
    from .solid import create_sdf_object
    return create_sdf_object(ex, uniforms=u, **o)


register_example(
    'explosion', kind='solid', animated=True, make=_make_explosion,
    description='pyroclastic fireball: an animated displaced sphere, the displacement driving a hot-to-smoke '
                'gradient with an emissive core',
    bounds={'min': [-2.1, -2.1, -2.1], 'max': [2.1, 2.1, 2.1]},
    quality='balanced', max_steps=64, step_scale=0.5, surf_eps=0.005,
    uniforms={'uSpeed': 1.0, 'uNoiseFreq': 4.0, 'uNoiseAmp': -0.5},
    extra=_EXPLOSION_EXTRA,
    map=r"""
        vec2 map(vec3 p) {
            float t = uTime * uSpeed;
            float radius = sin(t * 0.25) + 0.5;                          // animated radius
            // pyroclastic displacement, scrolling down so the fire rises
            float displace = fbmPyro(p * uNoiseFreq + vec3(0.0, -1.0, 0.0) * t);
            float d = length(p) - radius + displace * uNoiseAmp;
            return vec2(d, displace);                                     // the displacement rides the mat channel
        }""",
    shade=r"""
        vec3 shade(vec3 p, vec3 n, float mat) {
            float lit;
            vec3 c = explosionColour(mat, lit);
            // hot core stays emissive; the smoky rim picks up normal shading
            float diffuse = n.z * 0.5 + 0.5;
            return mix(c, c * diffuse, lit);
        }""",
    surface=r"""
        SdfSurface surface(vec3 p, vec3 n, float mat) {
            float lit;
            vec3 c = explosionColour(mat, lit);
            // the shaded share is a surface the scene lights; the rest glows at the gradient's HDR colour
            SdfSurface s = sdfSurface(clamp(c, 0.0, 1.0) * lit, 0.9);
            s.emission = c * (1.0 - lit);
            s.specular = 0.2;
            return s;
        }""",
)


# ============================================================================ SDF_TEX_RECIPES as solids =====
def _recipe_solid(name, bounds, iso=0.0, min_component=0, quality='high', description='', cut_by_bounds=False):
    rec = SDF_TEX_RECIPES[name]
    de = rec['de']
    if name == 'menger_sponge':
        # the recipe brings its own sdBox (its screen shader had no primitive library); the library's is the same
        # function, and a second definition would not compile next to it
        cut = de.index('float DE(')
        de = de[cut:]
    uniforms = {('u' + k[0].upper() + k[1:]): float(v) for k, v in rec['default_uniforms'].items()}
    register_example(
        name, kind='solid', animated=True, description=description,
        bounds=bounds, quality=quality, iso=iso, min_component=min_component, uniforms=uniforms,
        cut_by_bounds=cut_by_bounds,
        extra=SDF_TEX_PALETTE_GLSL + de + SDF_TEX_DEFAULT_SHADE,
        map='vec2 map(vec3 p) { return vec2(DE(p), 1.0); }',
        # the screen recipe's shade, seen from the Blender camera (no march count here: its AO term reads 1)
        shade=r"""
            vec3 shade(vec3 p, vec3 n, float mat) {
                vec3 rd = normalize(p - cameraPosition);
                return sdfTexShade(p, n, rd, 0, 160, uTime, uPaletteMode);
            }""",
        surface=r"""
            SdfSurface surface(vec3 p, vec3 n, float mat) {
                // the recipe's palette is its albedo (it drifts with uTime); its fresnel glow -> sheen
                SdfSurface s = sdfSurface(sdfTexPalette(uTime, p, uPaletteMode), 0.35);
                s.sheen = 0.5;
                s.sheenTint = vec3(1.0, 0.75, 0.5);
                return s;
            }""",
    )


_recipe_solid('mandelbulb', {'min': [-1.25, -1.25, -1.25], 'max': [1.25, 1.25, 1.25]}, iso=0.0015, min_component=24,
              quality='ultra', description='the mandelbulb recipe (power uPower, 8 iterations) as a placeable solid')
_recipe_solid('sierpinski_tetra', {'min': [-1.05, -1.05, -1.05], 'max': [1.05, 1.05, 1.05]}, iso=0.004,
              min_component=8, quality='high',
              description='the Sierpinski tetrahedron recipe (12 folds of scale 2) as a placeable solid')
# 'high': the fifth level's holes are 8 mm across, a 'balanced' voxel; at 5.3 mm they open
_recipe_solid('menger_sponge', {'min': [-1.02, -1.02, -1.02], 'max': [1.02, 1.02, 1.02]}, quality='high',
              description='the Menger sponge recipe (5 levels) as a placeable solid')
_recipe_solid('gyroid', {'min': [-1.0, -1.0, -1.0], 'max': [1.0, 1.0, 1.0]}, quality='high', cut_by_bounds=True,
              description='the gyroid recipe (scale 3.5) as a placeable solid: one labyrinth of the TPMS, cut to '
                          'its bounds box')
