"""The vehicle EXAMPLES of sdf_raymarch_loader.js, for the Blender edition.

    stylized_modern_sedan      a contemporary 4-door notchback: rounded-box body and cabin, A/C pillar planes,
                               side-window tunnels, wheel arches, door / hood / trunk shut-lines, annular tyres
                               with dished alloy rims and chrome caps, lamps, grille, mirrors, handles, belt trim;
                               make(paint_color=, paint_roughness=)
    stylized_cyberpunk_sedan   the same body with LED headlight bar, stacked round tail lamps, roof pods, gill
                               vents, hood louvers, trunk chevrons, hex grille, rocker underglow, accent strips,
                               chrome dome hubcaps, asymmetric racing stripes and the ALETH8APO badge plate;
                               make(paint_color=, paint_roughness=, decal_text=)
    stylized_sci_fi_sleek_car  a compact built from cylinder sections, a pure-metal body (uMetalColor is F0),
                               glass patches, sphere lamps, hex-tiled chrome hubcaps; make(metal_color=,
                               paint_roughness=)
    stylized_fighter_jet       hull, swept wings, stabilisers, canted fins, engine pods with bores, turbine faces
                               and exhaust struts, bubble canopy, emissive plumes, wing AAMs and a centreline bomb;
                               make(camo='silver' | 'sky' | 'desert' | 'forest')

They come from the engine's GLSL backup (its TSL edition kept their geometry and swapped the HDRI lookup for
procedural sky stand-ins). Every map(), shade() and helper is the engine's GLSL as written. Two changes, neither
of which alters a result: reversed-edge smoothstep(hi, lo, x) is written 1.0 - smoothstep(lo, hi, x) (the same
curve; the TSL port's rstep), and two pure colour helpers (the cyberpunk's stripeMaskFn, the jet's _jetCamoColor)
moved from shade into extra so surface() can call them too. (The badge branch's texture2D compiles as it is.)
One change follows the public engine where its TSL differs from the backup: the jet's canted fins. The TSL turns
them with (x c - y s, x s + y c), splayed outward as the comment's "F-18 style" says; the backup's
`pFin.xy *= _jetRot2(0.2)` multiplied the row vector by the matrix, the opposite turn, and leaned them inward. Every
other map() number of the two editions is the same.

Two ways to build one:
  EXAMPLES['stylized_cyberpunk_sedan'].make(paint_color=0xff2bd6)     the film build (vehicles.vehicle): the mesh
        with one Blender material per part, every pattern drawn per pixel (fleck, stripes, hex grille, hex hubcaps,
        badge glyphs, camo edges, lamp cores), live uniforms on the object, real lamps, and EEVEE's own
        reflections where the engine had sampleEnvMap
  create_sdf_object(EXAMPLES['stylized_cyberpunk_sedan'])             the engine's generic path: surface() below
        baked into an atlas or the vertices, like every other SDF example (coarser: patterns at texel size)

shade() is the engine's own lit look, part of the spec as the engine wrote it; bound to the world's HDRI by
register_sdf_helper, its sampleEnvMap sees what EEVEE lights with.
"""

from __future__ import annotations

from string import Template

from .spec import register_example
from .vehicles import parts as P
from .vehicles.badge import decal_texture_array
from .vehicles.vehicle import (make_cyberpunk_sedan, make_fighter_jet, make_modern_sedan, make_sci_fi_sleek_car,
                               VEHICLE_VOXEL)


def _branch_body(part):
    """surface() lines for a plain part from its parts-table entry (head-on lamp cores)."""
    lines = ['s = sdfSurface(%s, %s);' % (P.glsl_vec3(part.get('albedo', (0.8, 0.8, 0.8))),
                                          P.glsl_float(part.get('roughness', 0.5)))]
    if part.get('metallic'):
        lines.append('s.metallic = %s;' % P.glsl_float(part['metallic']))
    if 'specular' in part:
        lines.append('s.specular = %s;' % P.glsl_float(part['specular']))
    if part.get('coat'):
        lines.append('s.coat = %s;' % P.glsl_float(part['coat']))
    if 'emission' in part:
        k = P.core_head_on(part['core'])
        lines.append('s.emission = %s * %s;' % (P.glsl_vec3(part['emission']), P.glsl_float(k)))
    return lines


def _surface(kind, special):
    """SdfSurface surface(p, n, mat): one branch per material id, from parts.PARTS[kind]; `special` gives the GLSL
    of the parts drawn by a pattern (paint, grille, badge, hubcaps, camo ...)."""
    table, ids = P.PARTS[kind], P.IDS[kind]
    out = ['        SdfSurface surface(vec3 p, vec3 n, float mat) {',
           '            int matID = int(mat + 0.5);',
           '            SdfSurface s = sdfSurface(vec3(0.5), 0.5);']
    first = True
    for mid in sorted(ids):
        name = ids[mid]
        body = special[name].strip('\n').split('\n') if name in special else _branch_body(table[name])
        out.append('            %sif (matID == %d) {      // %s' % ('' if first else '} else ', mid, name))
        out += ['                ' + ln.strip() if not ln.startswith(' ' * 16) else ln for ln in body]
        first = False
    out += ['            }', '            return s;', '        }']
    return '\n'.join(out)


def _t(src, **kw):
    return Template(src).substitute(**kw)


# ========================================================================================= stylizedModernSedan ===
# A contemporary 4-door car assembled from rounded boxes, rounded capped cylinders for wheels, and CSG cuts for door
# / hood / trunk shut-lines, side-window cutouts (notchback) and wheel arches. 8 materials: body paint, tinted glass,
# rubber tyres, machined-alloy rims, chrome trim / caps, emissive headlights, emissive red tail lights, matte black
# plastic for the grille and intakes. Bounds are tight to the geometry: x +-1.05 (mirror housing), y 0..1.55 (the
# tyres: sdRCapCylX's outer radius is r = 0.36 itself, rnd only bevels the edge, so tyres centred at y 0.36 touch
# y = 0; the source comment's "0.05" misread the primitive, its bounds say 0), z +-2.4. Quality 'high': the wheel
# hub's boolean detail (the dish carve's k = 0.01, the ~5 mm air gap between cap and rim) needs it.
_MODERN_EXTRA = r"""
        // Material IDs — match the per-material branches in shade().
        #define MAT_PAINT     0.0
        #define MAT_GLASS     1.0
        #define MAT_TIRE      2.0
        #define MAT_RIM       3.0
        #define MAT_CHROME    4.0
        #define MAT_HEAD      5.0
        #define MAT_TAIL      6.0
        #define MAT_PLASTIC   8.0

        uniform vec3  uPaint;
        uniform float uRough;

        // Rounded box that shrinks the half-extents by r before adding
        // the round bevel — produces a tighter, more accurate rounded
        // box than the simple "sdBox(p, b) - r" form.
        float sdRBox(vec3 p, vec3 b, float r) {
            vec3 q = abs(p) - b + r;
            return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0) - r;
        }
        // Capped cylinder along the X axis, half-height h, radius r.
        float sdCapCylX(vec3 p, float h, float r) {
            vec2 d = vec2(length(p.yz), abs(p.x)) - vec2(r, h);
            return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
        }
        // Same as sdCapCylX with a rounded edge bevel — used for tires
        // and rim discs so the silhouette catches a highlight.
        float sdRCapCylX(vec3 p, float h, float r, float rnd) {
            vec2 d = vec2(length(p.yz), abs(p.x)) - vec2(r - rnd, h - rnd);
            return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - rnd;
        }
        // Quadratic smooth ops. Tighter falloff than the boilerplate's
        // cubic smin — preserves the car's crisp paneled silhouette.
        float opSU(float a, float b, float k) {
            float h = max(k - abs(a - b), 0.0) / k;
            return min(a, b) - h * h * k * 0.25;
        }
        float opSS(float a, float b, float k) {
            float h = max(k - abs(-a - b), 0.0) / k;
            return max(-a, b) + h * h * k * 0.25;
        }
        float opSI(float a, float b, float k) {
            float h = max(k - abs(a - b), 0.0) / k;
            return max(a, b) + h * h * k * 0.25;
        }

        vec2 sdCar(vec3 p) {
            // Mirror across X for left/right symmetry — every primitive
            // below is built once and reflects automatically.
            vec3 pm = vec3(abs(p.x), p.y, p.z);

            // === LOWER BODY ===
            float body = sdRBox(p - vec3(0.0, 0.60, 0.0), vec3(0.86, 0.40, 2.15), 0.18);
            float fCap = sdRBox(p - vec3(0.0, 0.60,  2.10), vec3(0.78, 0.38, 0.08), 0.28);
            float rCap = sdRBox(p - vec3(0.0, 0.60, -2.10), vec3(0.80, 0.39, 0.08), 0.26);
            body = opSU(body, fCap, 0.10);
            body = opSU(body, rCap, 0.10);
            // Hood crease — subtle raise along the centerline.
            float hoodCrease = sdRBox(p - vec3(0.0, 0.97, 1.45), vec3(0.35, 0.02, 0.65), 0.02);
            body = opSU(body, hoodCrease, 0.18);

            // === CABIN (greenhouse) ===
            // Notchback profile: A-pillar rakes ~42° from horizontal,
            // C-pillar tips FORWARD as it rises (real sedan geometry).
            float cabin = sdRBox(p - vec3(0.0, 1.20, -0.40), vec3(0.83, 0.20, 1.00), 0.14);
            vec3 aPillarN  = normalize(vec3(0.0, 1.11,  1.0));
            vec3 aPillarP0 = vec3(0.0, 1.04, 0.60);
            float aPillar = dot(p - aPillarP0, aPillarN);
            cabin = opSI(cabin, aPillar, 0.04);
            vec3 cPillarN  = normalize(vec3(0.0, 1.25, -1.0));
            vec3 cPillarP0 = vec3(0.0, 1.04, -1.40);
            float cPillar = dot(p - cPillarP0, cPillarN);
            cabin = opSI(cabin, cPillar, 0.04);

            float shell = opSU(body, cabin, 0.10);

            // === SIDE WINDOW CUTOUTS ===
            // Notchback rear cut at z=-0.72; B-pillar restored at z=-0.05.
            float winCut = sdRBox(p - vec3(0.0, 1.20, -0.06), vec3(0.96, 0.16, 0.76), 0.06);
            winCut = max(winCut, aPillar + 0.03);
            winCut = max(winCut, -(p.z + 0.72) + 0.03);
            float bPillar = sdBox(p - vec3(0.0, 1.20, -0.05), vec3(0.96, 0.20, 0.030));
            winCut = max(winCut, -bPillar);
            shell = opSS(winCut, shell, 0.02);

            // === WHEEL ARCHES (subtract outer wheel-well wall) ===
            float archInner = 0.45 - pm.x;
            float wfC = max(length(pm.yz - vec2(0.36,  1.40)) - 0.46, archInner);
            float wrC = max(length(pm.yz - vec2(0.36, -1.40)) - 0.46, archInner);
            shell = opSS(wfC, shell, 0.025);
            shell = opSS(wrC, shell, 0.025);

            // === DOOR / HOOD / TRUNK SHUT-LINES (thin grooves) ===
            float d1       = sdBox(p - vec3(0.0, 0.62,  0.60), vec3(0.96, 0.38, 0.006));
            float d2       = sdBox(p - vec3(0.0, 0.62, -0.05), vec3(0.96, 0.38, 0.006));
            float d3       = sdBox(p - vec3(0.0, 0.62, -0.72), vec3(0.96, 0.38, 0.006));
            float hoodCut  = sdBox(p - vec3(0.0, 0.97,  0.65), vec3(0.96, 0.06, 0.006));
            float trunkCut = sdBox(p - vec3(0.0, 0.97, -1.45), vec3(0.96, 0.06, 0.006));
            float cuts = min(min(min(d1, d2), d3), min(hoodCut, trunkCut));
            cuts = max(cuts, p.y - 1.00);   // only below roof
            cuts = max(cuts, 0.20 - p.y);   // don't cut into rocker
            shell = max(shell, -cuts);

            vec2 res = vec2(shell, MAT_PAINT);

            // === GLASS ===
            float glassBox = sdRBox(p - vec3(0.0, 1.20, -0.06), vec3(0.83, 0.15, 0.76), 0.06);
            glassBox = max(glassBox, aPillar + 0.03);
            glassBox = max(glassBox, -(p.z + 0.72) + 0.03);
            glassBox = max(glassBox, -bPillar);
            // Windshield slab on the A-pillar plane.
            float wsP = abs(dot(p - aPillarP0, aPillarN)) - 0.012;
            float wsB = sdBox(p - vec3(0.0, 1.22, 0.40), vec3(0.72, 0.18, 0.25));
            float windshield = max(wsP, wsB);
            // Rear window slab on the C-pillar plane.
            float rwP = abs(dot(p - cPillarP0, cPillarN)) - 0.012;
            float rwB = sdBox(p - vec3(0.0, 1.22, -1.175), vec3(0.72, 0.18, 0.28));
            float rearGlass = max(rwP, rwB);
            float glass = min(min(glassBox, windshield), rearGlass);
            res = opU(res, vec2(glass, MAT_GLASS));

            // === WHEELS ===
            // Tires are annular cylinders so the rim disc is visible
            // through the centre hole.
            vec3 pWF = pm - vec3(0.70, 0.36,  1.40);
            vec3 pWR = pm - vec3(0.70, 0.36, -1.40);
            float tireOutF  = sdRCapCylX(pWF, 0.115, 0.36, 0.05);
            float tireOutR  = sdRCapCylX(pWR, 0.115, 0.36, 0.05);
            float tireHoleF = sdCapCylX(pWF, 0.13, 0.20);
            float tireHoleR = sdCapCylX(pWR, 0.13, 0.20);
            float tireF  = max(tireOutF, -tireHoleF);
            float tireRe = max(tireOutR, -tireHoleR);
            res = opU(res, vec2(min(tireF, tireRe), MAT_TIRE));

            // Rim disc with recessed dish + chrome cap. The rim assembly
            // (rim + dish + cap) is shifted +27mm outboard from a "flush
            // with tire face" position so the rim's flat outboard face
            // sits ~15mm IN FRONT of the tire's outboard face. Up close
            // this reads as a deep-dish wheel where the rim lip protrudes
            // slightly past the tire sidewall before the dish indent
            // recesses inward to the chrome cap. At LOD distance the
            // dish-carve detail collapses but the rim's solid flat face
            // remains decisively in front of the tire's flat face — opU
            // picks rim metal across the entire wheel-centre radial zone,
            // giving a clean silver disc inside the tire annulus instead
            // of a rim/tire material flicker.
            float rimRad   = 0.205;
            float rimHalfW = 0.085;
            vec3 rimOffset = vec3(0.045, 0.0, 0.0);
            float rimF  = sdRCapCylX(pWF - rimOffset, rimHalfW, rimRad, 0.012);
            float rimRe = sdRCapCylX(pWR - rimOffset, rimHalfW, rimRad, 0.012);
            float dishF = sdRCapCylX(pWF - vec3(0.087, 0.0, 0.0), 0.05, rimRad - 0.04, 0.01);
            float dishR = sdRCapCylX(pWR - vec3(0.087, 0.0, 0.0), 0.05, rimRad - 0.04, 0.01);
            rimF  = opSS(dishF, rimF, 0.01);
            rimRe = opSS(dishR, rimRe, 0.01);
            res = opU(res, vec2(min(rimF, rimRe), MAT_RIM));

            // Chrome centre cap (also +27mm outboard with the rim assembly).
            float capF = sdRCapCylX(pWF - vec3(0.072, 0.0, 0.0), 0.04, 0.05, 0.012);
            float capR = sdRCapCylX(pWR - vec3(0.072, 0.0, 0.0), 0.04, 0.05, 0.012);
            res = opU(res, vec2(min(capF, capR), MAT_CHROME));

            // === HEADLIGHTS / TAILLIGHTS ===
            vec3 hlP = pm - vec3(0.58, 0.68,  2.18);
            float hl = sdRBox(hlP, vec3(0.22, 0.07, 0.05), 0.04);
            res = opU(res, vec2(hl, MAT_HEAD));
            vec3 tlP = pm - vec3(0.58, 0.68, -2.18);
            float tl = sdRBox(tlP, vec3(0.26, 0.07, 0.04), 0.03);
            res = opU(res, vec2(tl, MAT_TAIL));

            // === GRILLE / LOWER INTAKE ===
            float grille    = sdRBox(p - vec3(0.0, 0.55, 2.24), vec3(0.46, 0.08, 0.02), 0.03);
            float lowIntake = sdRBox(p - vec3(0.0, 0.33, 2.22), vec3(0.62, 0.07, 0.02), 0.03);
            res = opU(res, vec2(min(grille, lowIntake), MAT_PLASTIC));

            // === SIDE MIRRORS ===
            vec3 smP = pm - vec3(0.94, 1.07, 0.42);
            float mir = sdRBox(smP, vec3(0.05, 0.04, 0.075), 0.025);
            float arm = sdRBox(pm - vec3(0.83, 1.05, 0.42), vec3(0.045, 0.014, 0.025), 0.012);
            float mirror = opSU(mir, arm, 0.04);
            res = opU(res, vec2(mirror, MAT_PAINT));

            // === DOOR HANDLES (chrome) ===
            float h1 = sdRBox(pm - vec3(0.85, 0.80,  0.30), vec3(0.015, 0.015, 0.09), 0.01);
            float h2 = sdRBox(pm - vec3(0.85, 0.80, -0.40), vec3(0.015, 0.015, 0.09), 0.01);
            res = opU(res, vec2(min(h1, h2), MAT_CHROME));

            // === WINDOW BELT TRIM (thin chrome strip) ===
            float trim = sdRBox(p - vec3(0.0, 0.99, -0.06), vec3(0.81, 0.008, 0.78), 0.004);
            trim = max(trim, aPillar + 0.02);
            trim = max(trim, -(p.z + 0.72) + 0.02);
            res = opU(res, vec2(trim, MAT_CHROME));

            return res;
        }"""

_MODERN_MAP = r"""
        vec2 map(vec3 p) { return sdCar(p); }"""

_MODERN_SHADE = r"""
        // Procedural studio sky used as the chrome / glass / paint
        // environment lookup. Self-contained — doesn't read scene
        // textures, so the SDF still composites correctly into the
        // user's actual scene through the depth buffer.
        vec3 sedanSky(vec3 rd) {
            float t = clamp(rd.y * 0.5 + 0.5, 0.0, 1.0);
            vec3 zen = vec3(0.02, 0.025, 0.035);
            vec3 hor = vec3(0.22, 0.20, 0.18);
            vec3 col = mix(hor, zen, pow(t, 0.6));
            vec3 keyDir = normalize(vec3(0.4, 0.55, 0.25));
            col += vec3(1.1, 0.95, 0.75) * pow(max(dot(rd, keyDir), 0.0), 6.0) * 0.6;
            vec3 fillDir = normalize(vec3(-0.55, 0.35, -0.5));
            col += vec3(0.35, 0.45, 0.6) * pow(max(dot(rd, fillDir), 0.0), 3.0) * 0.25;
            col += vec3(0.9, 0.6, 0.3) * 0.08 * exp(-abs(rd.y) * 18.0);
            return col;
        }

        // Cheap AO from a few sphere-trace samples along the surface
        // normal. Keeps wheel-well shadowing and panel-corner contact
        // shading even when the agent doesn't enable GTAO.
        float sedanAO(vec3 p, vec3 n) {
            float occ = 0.0; float sca = 1.0;
            for (int i = 0; i < 5; i++) {
                float hr = 0.01 + 0.14 * float(i) / 4.0;
                float dd = map(p + n * hr).x;
                occ += (hr - dd) * sca;
                sca *= 0.92;
            }
            return clamp(1.0 - 2.5 * occ, 0.0, 1.0);
        }

        vec3 shade(vec3 p, vec3 n, float mat) {
            int matID = int(mat + 0.5);

            vec3 SUN_DIR = normalize(vec3(0.45, 0.78, 0.30));
            vec3 V    = normalize(cameraPosition - p);
            vec3 rd   = -V;
            vec3 H    = normalize(SUN_DIR + V);
            float NdL = max(dot(n, SUN_DIR), 0.0);
            float NdV = max(dot(n, V), 0.0);
            float NdH = max(dot(n, H), 0.0);

            float sh   = softShadow(p + n * 0.004, SUN_DIR, 0.01, 12.0, 24.0);
            float ao   = sedanAO(p, n);
            float fres = pow(1.0 - NdV, 5.0);
            // Env reflection sampled from the actual scene HDRI when
            // available, falling back to neutral mid-gray. Same change
            // as cyberpunk sedan — both cars now reflect whatever
            // lighting the agent sets up via scene.environment.
            vec3 envR  = sampleEnvMap(sdfReflectWorld(p, n));
            vec3 sun   = vec3(1.15, 1.05, 0.85);
            vec3 sky   = sampleEnvMap(vec3(0.0, 1.0, 0.0));
            vec3 col;

            if (matID == int(MAT_PAINT)) {
                // Matte metallic paint — picks up the env HDRI but
                // softly (rough surface scatters reflections), with
                // a per-position metallic-fleck speckle. No clearcoat
                // pop. Reads as a real sedan finish, not a showroom
                // mirror.
                vec3 base = uPaint;
                float rough = max(uRough, 0.35);
                float metallic = 0.55;
                // Two-scale fleck noise — coarse + fine — so the body
                // reads as metallic paint rather than flat colour.
                float fleckHi = fract(sin(dot(floor(p * 320.0), vec3(12.9, 78.2, 37.7))) * 43758.5);
                float fleckLo = fract(sin(dot(floor(p * 80.0),  vec3(45.3, 19.7, 91.1))) * 24831.7);
                float fleck = mix(fleckLo, fleckHi, 0.6);
                vec3 fleckTint = base + (fleck - 0.5) * 0.08;
                vec3 diffuse = fleckTint * (NdL * sh * sun * 0.6 + sky * ao * 0.30);
                float a = rough * rough;
                float D = a / (3.14159 * pow(NdH * NdH * (a - 1.0) + 1.0, 2.0));
                vec3 F = mix(vec3(0.04), base, metallic);
                vec3 sunSpec = sun * D * F * sh * 0.7;
                // Keep meaningful env reflection scaled by roughness —
                // matte but still picks up the HDRI.
                vec3 envCol  = envR * F * (1.0 - rough * 0.6);
                col = diffuse + envCol + sunSpec;
                col *= mix(0.65, 1.0, ao);
            }
            else if (matID == int(MAT_GLASS)) {
                vec3 tint = vec3(0.01, 0.012, 0.018);
                col = tint + envR * (fres * 0.9 + 0.08);
                col += sky * 0.02;
                col += sun * pow(NdH, 80.0) * sh * 0.6;
            }
            else if (matID == int(MAT_TIRE)) {
                vec3 base = vec3(0.025, 0.025, 0.028);
                col = base * (NdL * sh * sun + sky * ao + 0.04);
                col += envR * 0.03 * fres;
            }
            else if (matID == int(MAT_RIM)) {
                // Polished alloy. Dropped roughness so the carved dish
                // and rim lip pick up the HDRI clearly — chrome cap
                // and rim metal now read in the same family rather
                // than rim-as-painted-grey + cap-as-mirror.
                vec3 base = vec3(0.62, 0.62, 0.66);
                vec3 F = mix(vec3(0.04), base, 0.85);
                col  = base * (NdL * sh * sun * 0.25 + sky * ao * 0.4);
                col += envR * F * (fres * 0.5 + 0.6);
                col += sun * pow(NdH, 200.0) * sh * 1.2;
            }
            else if (matID == int(MAT_CHROME)) {
                col = envR * (fres * 0.85 + 0.5);
                col += sun * pow(NdH, 200.0) * sh * 2.0;
                col *= 0.95;
            }
            else if (matID == int(MAT_HEAD)) {
                vec3 emit = vec3(1.6, 1.55, 1.35);
                float core = pow(1.0 - fres, 3.0);
                col  = emit * (0.55 + core * 1.4);
                col += envR * fres * 0.5;
                col += sun * pow(NdH, 200.0) * sh * 1.2;
            }
            else if (matID == int(MAT_TAIL)) {
                vec3 redEmit = vec3(1.9, 0.10, 0.05);
                float core = mix(0.7, 1.2, pow(1.0 - fres, 2.0));
                col  = redEmit * core;
                col += envR * fres * 0.25;
                col += vec3(1.0, 0.4, 0.3) * pow(NdH, 80.0) * sh * 0.4;
            }
            else {
                // MAT_PLASTIC — matte black grille / lower intake.
                vec3 base = vec3(0.02, 0.02, 0.022);
                col = base * (NdL * sh * sun * 0.5 + sky * ao) + envR * fres * 0.1;
                col += sun * pow(NdH, 12.0) * sh * 0.15;
            }

            return col;
        }"""

_MODERN_SURFACE = _surface('modern', {
    'paint': _t(r"""
                // uPaint +- a two-scale metallic fleck, F = mix(0.04, base, 0.55), roughness floored at 0.35; its
                // sharp env reflection, scaled by (1 - 0.6 rough), is the clear coat
                float fleckHi = fract(sin(dot(floor(p * 320.0), vec3(12.9, 78.2, 37.7))) * 43758.5);
                float fleckLo = fract(sin(dot(floor(p * 80.0),  vec3(45.3, 19.7, 91.1))) * 24831.7);
                float fleck = mix(fleckLo, fleckHi, 0.6);
                s = sdfSurface(clamp(uPaint + (fleck - 0.5) * 0.08, 0.0, 1.0), max(uRough, $floor));
                s.metallic = $metallic;
                s.coat = $coat;""", floor=P.glsl_float(P.PAINT_FLOOR['modern']),
                metallic=P.glsl_float(P.MODERN['paint']['metallic']), coat=P.glsl_float(P.MODERN['paint']['coat'])),
})

register_example(
    'stylized_modern_sedan', kind='solid', make=make_modern_sedan,
    description='contemporary 4-door notchback sedan: CSG panels and shut-lines, dished alloy wheels, 8 materials; '
                'make(paint_color, paint_roughness)',
    bounds={'min': [-1.05, 0.0, -2.4], 'max': [1.05, 1.55, 2.4]},
    quality='high', voxel=VEHICLE_VOXEL['modern'],
    uniforms={'uPaint': ('color', P.MODERN_DEFAULTS['uPaint']), 'uRough': P.MODERN_DEFAULTS['uRough']},
    extra=_MODERN_EXTRA, map=_MODERN_MAP, shade=_MODERN_SHADE, surface=_MODERN_SURFACE,
    material_settings={'coat_roughness': 0.11},      # 0.25 x paintRoughness 0.45 (shading.py)
)


# ======================================================================================= stylizedCyberpunkSedan ===
# The modern sedan's notchback proportions with accent-lit body geometry: a full-width LED headlight bar, stacked
# round tail lamps (3 a side), 3 roof pods with slanted faces, gill vents behind the rear wheel, hood louvers beside
# the centre crease, trunk chevron seams, hex grille, rocker underglow, front and rear accent strips, chrome dome
# hubcaps, and a badge plate that samples the uDecal canvas (vehicles/badge.py). The body stays near-black; uPaint
# drives the fresnel rim, the underglow, the accent strips and the grille glow. Asymmetric racing stripes are painted
# by stripeMaskFn: right side hood diagonal, door tape, rocker tape, speed comb, number block, trunk diagonal, dual
# roof; left side rear-door diagonal, fender comb, wedge, trunk parallels, single roof, rocker line.
_CYBER_EXTRA = r"""

        // Material IDs — body paint, glass, wheels, lights, plus the
        // cyberpunk-only emissives (UNDERGLOW, ACCENT, GRILLE) and the
        // procedural BADGE plate that samples uDecal.
        #define MAT_PAINT      0.0
        #define MAT_GLASS      1.0
        #define MAT_TIRE       2.0
        #define MAT_RIM        3.0
        #define MAT_CHROME     4.0
        #define MAT_HEAD       5.0
        #define MAT_TAIL       6.0
        #define MAT_PLASTIC    8.0
        #define MAT_UNDERGLOW  9.0
        #define MAT_ACCENT    10.0
        #define MAT_GRILLE    11.0
        #define MAT_BADGE     12.0

        uniform vec3      uPaint;
        uniform float     uRough;
        uniform sampler2D uDecal;

        // SDF primitives — kept inline so this example reads end-to-end
        // without cross-referencing the modern sedan.
        float sdRBox(vec3 p, vec3 b, float r) {
            vec3 q = abs(p) - b + r;
            return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0) - r;
        }
        float sdCapCylX(vec3 p, float h, float r) {
            vec2 d = vec2(length(p.yz), abs(p.x)) - vec2(r, h);
            return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
        }
        float sdRCapCylX(vec3 p, float h, float r, float rnd) {
            vec2 d = vec2(length(p.yz), abs(p.x)) - vec2(r - rnd, h - rnd);
            return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - rnd;
        }
        // Note: sdEllipsoid is provided by the loader's shared primitive
        // library (auto-injected into every example's fragment shader).
        // The chrome dome below uses it without redeclaring.
        float opSU(float a, float b, float k) {
            float h = max(k - abs(a - b), 0.0) / k;
            return min(a, b) - h * h * k * 0.25;
        }
        float opSS(float a, float b, float k) {
            float h = max(k - abs(-a - b), 0.0) / k;
            return max(-a, b) + h * h * k * 0.25;
        }
        float opSI(float a, float b, float k) {
            float h = max(k - abs(a - b), 0.0) / k;
            return max(a, b) + h * h * k * 0.25;
        }

        vec2 sdCar(vec3 p) {
            vec3 pm = vec3(abs(p.x), p.y, p.z);

            // === LOWER BODY ===
            float body = sdRBox(p - vec3(0.0, 0.60, 0.0), vec3(0.86, 0.40, 2.15), 0.18);
            float fCap = sdRBox(p - vec3(0.0, 0.60,  2.10), vec3(0.78, 0.38, 0.08), 0.28);
            float rCap = sdRBox(p - vec3(0.0, 0.60, -2.10), vec3(0.80, 0.39, 0.08), 0.26);
            body = opSU(body, fCap, 0.10);
            body = opSU(body, rCap, 0.10);
            float hoodCrease = sdRBox(p - vec3(0.0, 0.97, 1.50), vec3(0.35, 0.02, 0.55), 0.02);
            body = opSU(body, hoodCrease, 0.18);

            // === CABIN (notchback profile, A/C-pillars) ===
            float cabin = sdRBox(p - vec3(0.0, 1.20, -0.40), vec3(0.83, 0.20, 1.00), 0.14);
            vec3 aPillarN  = normalize(vec3(0.0, 1.11,  1.0));
            vec3 aPillarP0 = vec3(0.0, 1.04, 0.60);
            float aPillar = dot(p - aPillarP0, aPillarN);
            cabin = opSI(cabin, aPillar, 0.04);
            vec3 cPillarN  = normalize(vec3(0.0, 1.25, -1.0));
            vec3 cPillarP0 = vec3(0.0, 1.04, -1.40);
            float cPillar = dot(p - cPillarP0, cPillarN);
            cabin = opSI(cabin, cPillar, 0.04);

            float shell = opSU(body, cabin, 0.10);

            // === SIDE WINDOW CUTOUTS (notchback rear cut + B-pillar) ===
            float winCut = sdRBox(p - vec3(0.0, 1.20, -0.06), vec3(0.96, 0.16, 0.76), 0.06);
            winCut = max(winCut, aPillar + 0.03);
            winCut = max(winCut, -(p.z + 0.72) + 0.03);
            float bPillar = sdBox(p - vec3(0.0, 1.20, -0.05), vec3(0.96, 0.20, 0.030));
            winCut = max(winCut, -bPillar);
            shell = opSS(winCut, shell, 0.02);

            // === WHEEL ARCHES ===
            float archInner = 0.45 - pm.x;
            float wfC = max(length(pm.yz - vec2(0.36,  1.40)) - 0.46, archInner);
            float wrC = max(length(pm.yz - vec2(0.36, -1.40)) - 0.46, archInner);
            shell = opSS(wfC, shell, 0.025);
            shell = opSS(wrC, shell, 0.025);

            // === DOOR / HOOD / TRUNK SHUT-LINES ===
            float d1       = sdBox(p - vec3(0.0, 0.62,  0.60), vec3(0.96, 0.38, 0.006));
            float d2       = sdBox(p - vec3(0.0, 0.62, -0.05), vec3(0.96, 0.38, 0.006));
            float d3       = sdBox(p - vec3(0.0, 0.62, -0.72), vec3(0.96, 0.38, 0.006));
            float hoodCut  = sdBox(p - vec3(0.0, 0.97,  0.65), vec3(0.96, 0.06, 0.006));
            float trunkCut = sdBox(p - vec3(0.0, 0.97, -1.45), vec3(0.96, 0.06, 0.006));
            float cuts = min(min(min(d1, d2), d3), min(hoodCut, trunkCut));
            cuts = max(cuts, p.y - 1.00);
            cuts = max(cuts, 0.20 - p.y);
            shell = max(shell, -cuts);

            vec2 res = vec2(shell, MAT_PAINT);

            // === GLASS ===
            float glassBox = sdRBox(p - vec3(0.0, 1.20, -0.06), vec3(0.83, 0.15, 0.76), 0.06);
            glassBox = max(glassBox, aPillar + 0.03);
            glassBox = max(glassBox, -(p.z + 0.72) + 0.03);
            glassBox = max(glassBox, -bPillar);
            float wsP = abs(dot(p - aPillarP0, aPillarN)) - 0.012;
            float wsB = sdBox(p - vec3(0.0, 1.22, 0.40), vec3(0.72, 0.18, 0.25));
            float windshield = max(wsP, wsB);
            float rwP = abs(dot(p - cPillarP0, cPillarN)) - 0.012;
            float rwB = sdBox(p - vec3(0.0, 1.22, -1.175), vec3(0.72, 0.18, 0.28));
            float rearGlass = max(rwP, rwB);
            float glass = min(min(glassBox, windshield), rearGlass);
            res = opU(res, vec2(glass, MAT_GLASS));

            // === WHEELS (annular tires + dished rims + chrome caps) ===
            vec3 pWF = pm - vec3(0.70, 0.36,  1.40);
            vec3 pWR = pm - vec3(0.70, 0.36, -1.40);
            float tireOutF  = sdRCapCylX(pWF, 0.115, 0.36, 0.05);
            float tireOutR  = sdRCapCylX(pWR, 0.115, 0.36, 0.05);
            float tireHoleF = sdCapCylX(pWF, 0.13, 0.20);
            float tireHoleR = sdCapCylX(pWR, 0.13, 0.20);
            float tireF  = max(tireOutF, -tireHoleF);
            float tireRe = max(tireOutR, -tireHoleR);
            res = opU(res, vec2(min(tireF, tireRe), MAT_TIRE));

            // === CHROME DOME HUBCAP (cyberpunk-only) ===
            // Classic 20th-century chrome dome — a non-uniformly-scaled
            // sphere (oblate ellipsoid) producing a wide, shallow,
            // genuinely-curved dome. Single primitive: one length() call
            // with Lipschitz compensation via *minScale. No booleans;
            // no Minkowski-sum flat top (which sdRCapCylX would give).
            //
            // Centre at wheel-local X=0.135, base sphere radius 0.24:
            //   - Scale (0.15, 1, 1): squashes X-axis by 6.7×, leaving
            //     a fat YZ disc with a curved X profile.
            //   - YZ-extent: 0.24 — comfortably PAST the tire hole 0.20
            //     so the dome covers the hole edge cleanly. At YZ=0.20,
            //     dome surface is at X=0.156 vs tire face X=0.115 — a
            //     41mm step in front of the tire, no coplanar zone.
            //   - X-extent: 0.135 ± 0.24*0.15 = 0.099 to 0.171. Peak
            //     at X=0.171 (5.6cm past tire face).
            //   - At LOD, the dome dominates the wheel-centre radial
            //     zone (0-0.24). Tire wins beyond YZ=0.24. No z-fight.
            //   - The squashed sphere's gradient is genuinely curved
            //     across the full surface — reads as a domed hubcap,
            //     not a flat disc with a rounded edge.
            vec3 domeFP = (pWF - vec3(0.135, 0.0, 0.0)) / vec3(0.15, 1.0, 1.0);
            vec3 domeRP = (pWR - vec3(0.135, 0.0, 0.0)) / vec3(0.15, 1.0, 1.0);
            float domeF = (length(domeFP) - 0.24) * 0.15;
            float domeR = (length(domeRP) - 0.24) * 0.15;
            res = opU(res, vec2(min(domeF, domeR), MAT_CHROME));

            // === HEADLIGHT BAR (full width, thin LED strip) ===
            float hlBar = sdRBox(p - vec3(0.0, 0.74, 2.20), vec3(0.66, 0.025, 0.04), 0.012);
            res = opU(res, vec2(hlBar, MAT_HEAD));

            // === TAILLIGHTS (3 stacked round disc lenses per side) ===
            vec3 tl1P = pm - vec3(0.66, 0.86, -2.18);
            vec3 tl2P = pm - vec3(0.66, 0.74, -2.18);
            vec3 tl3P = pm - vec3(0.66, 0.62, -2.18);
            float tl1 = max(length(tl1P.xy) - 0.045, abs(tl1P.z) - 0.025);
            float tl2 = max(length(tl2P.xy) - 0.045, abs(tl2P.z) - 0.025);
            float tl3 = max(length(tl3P.xy) - 0.045, abs(tl3P.z) - 0.025);
            float tlStack = min(min(tl1, tl2), tl3);
            res = opU(res, vec2(tlStack, MAT_TAIL));

            // === ROOF PODS (3 paint-material pods, slanted faces) ===
            // Each pod is a thin rounded box clipped by a tilted plane so
            // the upper edge reads as an angled face. Forward pods use a
            // forward-leaning slant; the rear pod tilts the opposite way.
            vec3 pfN = normalize(vec3(0.0, 0.6, 0.8));
            float pf_box = sdRBox(p - vec3(0.0, 1.416, 0.18), vec3(0.10, 0.030, 0.07), 0.014);
            float pf_slant = dot(p - vec3(0.0, 1.43, 0.20), pfN);
            float pod1 = max(pf_box, pf_slant);
            float pmid_box = sdRBox(pm - vec3(0.55, 1.416, 0.05), vec3(0.06, 0.025, 0.07), 0.012);
            float pmid_slant = dot(p - vec3(0.0, 1.43, 0.07), pfN);
            float pod2 = max(pmid_box, pmid_slant);
            vec3 prN = normalize(vec3(0.0, 0.6, -0.8));
            float pr_box = sdRBox(p - vec3(0.0, 1.416, -0.55), vec3(0.11, 0.028, 0.07), 0.014);
            float pr_slant = dot(p - vec3(0.0, 1.43, -0.57), prN);
            float pod3 = max(pr_box, pr_slant);
            float pods = min(min(pod1, pod2), pod3);
            res = opU(res, vec2(pods, MAT_PAINT));

            // === SUBTRACTIVE SURFACE DETAILS ===
            // gather; applied to the body shell at the bottom of this fn

            // GILL VENT (3 vertical slots BEHIND the rear wheel)
            vec3 gillPm = pm - vec3(0.86, 0.78, -2.00);
            float g1 = sdBox(gillPm - vec3(0.0, 0.0,  0.05), vec3(0.014, 0.10, 0.012));
            float g2 = sdBox(gillPm - vec3(0.0, 0.0,  0.00), vec3(0.014, 0.10, 0.012));
            float g3 = sdBox(gillPm - vec3(0.0, 0.0, -0.05), vec3(0.014, 0.10, 0.012));
            float gill = min(min(g1, g2), g3);

            // HOOD LOUVERS (5 diagonal slats flanking the centre crease)
            // Each louver is a tiny capped segment from points lvA→lvB.
            float louvers = 1e9;
            vec3 lvA1 = vec3(0.42, 1.00, 0.85);  vec3 lvB1 = vec3(0.62, 1.00, 1.05);
            vec3 dl1 = (pm - lvA1) - (lvB1 - lvA1) * clamp(dot(pm - lvA1, lvB1 - lvA1) / dot(lvB1 - lvA1, lvB1 - lvA1), 0.0, 1.0);
            louvers = min(louvers, max(length(dl1.xz) - 0.008, abs(dl1.y) - 0.025));
            vec3 lvA2 = vec3(0.42, 1.00, 1.10);  vec3 lvB2 = vec3(0.62, 1.00, 1.30);
            vec3 dl2 = (pm - lvA2) - (lvB2 - lvA2) * clamp(dot(pm - lvA2, lvB2 - lvA2) / dot(lvB2 - lvA2, lvB2 - lvA2), 0.0, 1.0);
            louvers = min(louvers, max(length(dl2.xz) - 0.008, abs(dl2.y) - 0.025));
            vec3 lvA3 = vec3(0.42, 1.00, 1.35);  vec3 lvB3 = vec3(0.62, 1.00, 1.55);
            vec3 dl3 = (pm - lvA3) - (lvB3 - lvA3) * clamp(dot(pm - lvA3, lvB3 - lvA3) / dot(lvB3 - lvA3, lvB3 - lvA3), 0.0, 1.0);
            louvers = min(louvers, max(length(dl3.xz) - 0.008, abs(dl3.y) - 0.025));
            vec3 lvA4 = vec3(0.42, 1.00, 1.60);  vec3 lvB4 = vec3(0.62, 1.00, 1.80);
            vec3 dl4 = (pm - lvA4) - (lvB4 - lvA4) * clamp(dot(pm - lvA4, lvB4 - lvA4) / dot(lvB4 - lvA4, lvB4 - lvA4), 0.0, 1.0);
            louvers = min(louvers, max(length(dl4.xz) - 0.008, abs(dl4.y) - 0.025));
            vec3 lvA5 = vec3(0.42, 1.00, 1.85);  vec3 lvB5 = vec3(0.60, 1.00, 2.00);
            vec3 dl5 = (pm - lvA5) - (lvB5 - lvA5) * clamp(dot(pm - lvA5, lvB5 - lvA5) / dot(lvB5 - lvA5, lvB5 - lvA5), 0.0, 1.0);
            louvers = min(louvers, max(length(dl5.xz) - 0.008, abs(dl5.y) - 0.025));
            float hs3 = sdBox(p - vec3(0.0, 1.04, 0.78), vec3(0.18, 0.025, 0.10));
            float hoodSeams = min(louvers, hs3);

            // DOOR PANEL DIAGONAL SEAMS (mirrored, rotated capsule slabs)
            vec3 dsP1 = pm - vec3(0.86, 0.60, 0.275);
            float caD = cos(0.61), saD = sin(0.61);
            vec3 dsP1r = vec3(dsP1.x, caD*dsP1.y + saD*dsP1.z, -saD*dsP1.y + caD*dsP1.z);
            float ds1 = sdBox(dsP1r, vec3(0.010, 0.005, 0.32));
            vec3 dsP2 = pm - vec3(0.86, 0.60, -0.40);
            vec3 dsP2r = vec3(dsP2.x, caD*dsP2.y - saD*dsP2.z, saD*dsP2.y + caD*dsP2.z);
            float ds2 = sdBox(dsP2r, vec3(0.010, 0.005, 0.32));
            float doorSeams = min(ds1, ds2);

            // TRUNK CHEVRON SEAMS (two diagonals + centre inset panel)
            vec3 ts1A = vec3( 0.0, 1.00, -1.45);
            vec3 ts1B = vec3( 0.42, 1.00, -2.10);
            vec3 ba_ts1 = ts1B - ts1A;
            vec3 pa_ts1 = p - ts1A;
            float h_ts1 = clamp(dot(pa_ts1, ba_ts1) / dot(ba_ts1, ba_ts1), 0.0, 1.0);
            vec3 d_ts1 = pa_ts1 - ba_ts1 * h_ts1;
            float ts1 = max(length(d_ts1.xz) - 0.008, abs(d_ts1.y) - 0.025);
            vec3 ts2A = vec3( 0.0, 1.00, -1.45);
            vec3 ts2B = vec3(-0.42, 1.00, -2.10);
            vec3 ba_ts2 = ts2B - ts2A;
            vec3 pa_ts2 = p - ts2A;
            float h_ts2 = clamp(dot(pa_ts2, ba_ts2) / dot(ba_ts2, ba_ts2), 0.0, 1.0);
            vec3 d_ts2 = pa_ts2 - ba_ts2 * h_ts2;
            float ts2 = max(length(d_ts2.xz) - 0.008, abs(d_ts2.y) - 0.025);
            float ts3 = sdBox(p - vec3(0.0, 1.00, -1.65), vec3(0.18, 0.025, 0.05));
            float trunkSeams = min(min(ts1, ts2), ts3);

            // REAR QUARTER ACCENT LINE (thin horizontal seam)
            float rqLine = sdBox(pm - vec3(0.86, 0.55, -1.55), vec3(0.012, 0.005, 0.55));

            // REAR + FRONT BUMPER PANEL CUTS (two small horizontal panels)
            float rbP1 = sdBox(p - vec3(-0.30, 0.30, -2.20), vec3(0.18, 0.04, 0.012));
            float rbP2 = sdBox(p - vec3( 0.30, 0.30, -2.20), vec3(0.18, 0.04, 0.012));
            float rearBumperPanels = min(rbP1, rbP2);
            float fbP1 = sdBox(p - vec3(-0.30, 0.30, 2.20), vec3(0.18, 0.04, 0.012));
            float fbP2 = sdBox(p - vec3( 0.30, 0.30, 2.20), vec3(0.18, 0.04, 0.012));
            float frontBumperPanels = min(fbP1, fbP2);

            // Apply all subtractive cuts to the body shell only (mat==PAINT
            // and not yet replaced by glass / wheels / pods etc).
            if (res.y < 0.5) {
                float bs = res.x;
                bs = max(bs, -gill);
                bs = max(bs, -hoodSeams);
                bs = max(bs, -doorSeams);
                bs = max(bs, -trunkSeams);
                bs = max(bs, -rqLine);
                bs = max(bs, -rearBumperPanels);
                bs = max(bs, -frontBumperPanels);
                res.x = bs;
            }

            // === REAR QUARTER BADGE PLATE (samples uDecal in shade) ===
            // Flush with the cabin/quarter panel surface.
            float badge = sdRBox(pm - vec3(0.834, 1.15, -0.95), vec3(0.008, 0.045, 0.16), 0.005);
            res = opU(res, vec2(badge, MAT_BADGE));

            // === ACCENT STRIPS (front + rear, emissive uPaint) ===
            float accF = sdRBox(p - vec3(0.0, 0.46,  2.22), vec3(0.56, 0.010, 0.018), 0.005);
            float accR = sdRBox(p - vec3(0.0, 0.46, -2.22), vec3(0.56, 0.010, 0.018), 0.005);
            res = opU(res, vec2(min(accF, accR), MAT_ACCENT));

            // === UNDERGLOW (rocker emissive sliver, between wheels) ===
            float ugStrip = sdRBox(pm - vec3(0.55, 0.21, 0.0), vec3(0.020, 0.012, 0.95), 0.005);
            res = opU(res, vec2(ugStrip, MAT_UNDERGLOW));

            // === HEX GRILLE (procedural cells in shade) ===
            float grille = sdRBox(p - vec3(0.0, 0.55, 2.24), vec3(0.46, 0.08, 0.02), 0.03);
            res = opU(res, vec2(grille, MAT_GRILLE));

            // === LOWER BUMPER INTAKE (matte plastic) ===
            float lowIntake = sdRBox(p - vec3(0.0, 0.33, 2.22), vec3(0.62, 0.07, 0.02), 0.03);
            res = opU(res, vec2(lowIntake, MAT_PLASTIC));

            // === SIDE MIRRORS ===
            vec3 smP = pm - vec3(0.94, 1.07, 0.42);
            float mir = sdRBox(smP, vec3(0.05, 0.04, 0.075), 0.025);
            float arm = sdRBox(pm - vec3(0.83, 1.05, 0.42), vec3(0.045, 0.014, 0.025), 0.012);
            float mirror = opSU(mir, arm, 0.04);
            res = opU(res, vec2(mirror, MAT_PAINT));

            // === DOOR HANDLES (chrome) ===
            float h1 = sdRBox(pm - vec3(0.85, 0.80,  0.30), vec3(0.015, 0.015, 0.09), 0.01);
            float h2 = sdRBox(pm - vec3(0.85, 0.80, -0.40), vec3(0.015, 0.015, 0.09), 0.01);
            res = opU(res, vec2(min(h1, h2), MAT_CHROME));

            // === WINDOW BELT TRIM (chrome strip along cabin belt-line) ===
            float trim = sdRBox(p - vec3(0.0, 0.99, -0.06), vec3(0.81, 0.008, 0.78), 0.004);
            trim = max(trim, aPillar + 0.02);
            trim = max(trim, -(p.z + 0.72) + 0.02);
            res = opU(res, vec2(trim, MAT_CHROME));

            return res;
        }
        // Asymmetric racing-stripe paint mask. RIGHT side (p.x > 0.05)
        // uses diagonal/dual-tape vocabulary; LEFT side (p.x < -0.05)
        // uses wedge/vertical-comb/parallel vocabulary. Returns a 0..1
        // factor used to blend in an off-white decal layer over the dark
        // body. Suppressed inside wheel arches (curved interior reads
        // wrong with stripes designed for flat panels).
        float stripeMaskFn(vec3 p, vec3 n) {
            float m = 0.0;
            vec3 pmA = vec3(abs(p.x), p.y, p.z);
            float aF = length(pmA.yz - vec2(0.36,  1.40)) - 0.48;
            float aR = length(pmA.yz - vec2(0.36, -1.40)) - 0.48;
            bool inArch = (pmA.x > 0.45 && min(aF, aR) < 0.0);
            vec2 pxz = vec2(p.x, p.z);

            if (p.x > 0.05) {
                // (R1) HOOD DIAGONAL — primary thick + parallel thin.
                vec2 hA = vec2(0.18, 1.05), hB = vec2(0.62, 1.95);
                vec2 dirH = normalize(hB - hA);
                vec2 nrmH = vec2(-dirH.y, dirH.x);
                float alongH = dot(pxz - hA, dirH);
                float perpH  = dot(pxz - hA, nrmH);
                float lenH   = length(hB - hA);
                if (n.y > 0.6 && alongH > 0.0 && alongH < lenH) {
                    m = max(m, (1.0 - smoothstep(0.045, 0.06, abs(perpH))));
                    m = max(m, (1.0 - smoothstep(0.008, 0.012, abs(perpH - 0.10))));
                }
                // (R2) DOOR TAPE — vertical primary + parallel thin.
                if (n.x > 0.6) {
                    float dz_main = abs(p.z - 0.42);
                    if (dz_main < 0.06 && p.y > 0.30 && p.y < 0.95) {
                        m = max(m, (1.0 - smoothstep(0.045, 0.06, dz_main)));
                    }
                    float dz_thin = abs(p.z - 0.28);
                    if (dz_thin < 0.012 && p.y > 0.30 && p.y < 0.95) {
                        m = max(m, (1.0 - smoothstep(0.008, 0.012, dz_thin)));
                    }
                }
                // (R3) ROCKER TAPE — dual horizontal lines along lower side.
                if (n.x > 0.6) {
                    float dyA = abs(p.y - 0.42);
                    if (dyA < 0.012 && p.z > -2.00 && p.z < 2.00) {
                        m = max(m, (1.0 - smoothstep(0.008, 0.012, dyA)));
                    }
                    float dyB = abs(p.y - 0.46);
                    if (dyB < 0.006 && p.z > -2.00 && p.z < 2.00) {
                        m = max(m, (1.0 - smoothstep(0.004, 0.006, dyB)));
                    }
                }
                // (R4) REAR QUARTER SPEED COMB — 6 short vertical ticks.
                if (n.x > 0.6 && p.y > 0.55 && p.y < 0.85) {
                    for (int i = 0; i < 6; i++) {
                        float zc = -1.10 - float(i) * 0.06;
                        float dz = abs(p.z - zc);
                        if (dz < 0.012) m = max(m, (1.0 - smoothstep(0.008, 0.012, dz)));
                    }
                }
                // (R5) NUMBER BLOCK — solid plate above the comb.
                if (n.x > 0.6) {
                    float dz_b = abs(p.z + 1.55);
                    float dy_b = abs(p.y - 0.95);
                    if (dz_b < 0.10 && dy_b < 0.045) {
                        float k = (1.0 - smoothstep(0.085, 0.10, dz_b))
                                * (1.0 - smoothstep(0.038, 0.045, dy_b));
                        m = max(m, k);
                    }
                }
                // (R6) TRUNK DIAGONAL — mirror of hood, on trunk top.
                vec2 tA = vec2(0.18, -1.55), tB = vec2(0.62, -2.05);
                vec2 dirT = normalize(tB - tA);
                vec2 nrmT = vec2(-dirT.y, dirT.x);
                float alongT = dot(pxz - tA, dirT);
                float perpT  = dot(pxz - tA, nrmT);
                float lenT   = length(tB - tA);
                if (n.y > 0.6 && alongT > 0.0 && alongT < lenT) {
                    m = max(m, (1.0 - smoothstep(0.04, 0.05, abs(perpT))));
                    m = max(m, (1.0 - smoothstep(0.008, 0.012, abs(perpT - 0.085))));
                }
                // (R7) ROOF RACING STRIPES — dual fore-aft on right side.
                if (n.y > 0.6 && p.y > 1.35 && p.z > -1.30 && p.z < 0.40) {
                    float dxA = abs(p.x - 0.30);
                    if (dxA < 0.04) m = max(m, (1.0 - smoothstep(0.03, 0.04, dxA)));
                    float dxB = abs(p.x - 0.40);
                    if (dxB < 0.010) m = max(m, (1.0 - smoothstep(0.007, 0.010, dxB)));
                }
            }

            if (p.x < -0.05) {
                // (L2) REAR DOOR DIAGONAL — single bold angled band.
                if (n.x < -0.6) {
                    vec2 dA = vec2(-0.55, 0.85), dB = vec2(-0.10, 0.40);
                    vec2 dirD = normalize(dB - dA);
                    vec2 nrmD = vec2(-dirD.y, dirD.x);
                    vec2 pyz = vec2(p.z, p.y);
                    float along_d = dot(pyz - dA, dirD);
                    float perp_d  = abs(dot(pyz - dA, nrmD));
                    float len_d   = length(dB - dA);
                    if (along_d > 0.0 && along_d < len_d && perp_d < 0.05) {
                        m = max(m, (1.0 - smoothstep(0.04, 0.05, perp_d)));
                    }
                }
                // (L3) FRONT-FENDER VERTICAL COMB — 5 horizontal ticks.
                if (n.x < -0.6 && p.z > 1.50 && p.z < 1.85) {
                    for (int i = 0; i < 5; i++) {
                        float yc = 0.45 + float(i) * 0.07;
                        float dy = abs(p.y - yc);
                        if (dy < 0.010) m = max(m, (1.0 - smoothstep(0.007, 0.010, dy)));
                    }
                }
                // (L4) WEDGE BLOCK — triangle test on rear quarter.
                if (n.x < -0.6) {
                    vec2 v0 = vec2(-1.30, 0.95);
                    vec2 v1 = vec2(-1.70, 0.95);
                    vec2 v2 = vec2(-1.50, 0.65);
                    vec2 pp = vec2(p.z, p.y);
                    float s0 = (pp.x - v0.x) * (v1.y - v0.y) - (pp.y - v0.y) * (v1.x - v0.x);
                    float s1 = (pp.x - v1.x) * (v2.y - v1.y) - (pp.y - v1.y) * (v2.x - v1.x);
                    float s2 = (pp.x - v2.x) * (v0.y - v2.y) - (pp.y - v2.y) * (v0.x - v2.x);
                    if ((s0 >= 0.0 && s1 >= 0.0 && s2 >= 0.0)
                     || (s0 <= 0.0 && s1 <= 0.0 && s2 <= 0.0)) {
                        m = max(m, 1.0);
                    }
                }
                // (L5) TRUNK PARALLELS — 3 thin lines on left trunk top.
                if (n.y > 0.6 && p.x < -0.10 && p.x > -0.70 && p.z > -2.05 && p.z < -1.40) {
                    for (int i = 0; i < 3; i++) {
                        float xc = -0.20 - float(i) * 0.16;
                        float dx = abs(p.x - xc);
                        if (dx < 0.008) m = max(m, (1.0 - smoothstep(0.005, 0.008, dx)));
                    }
                }
                // (L6) ROOF — single thin stripe on left side.
                if (n.y > 0.6 && p.y > 1.35 && p.z > -1.30 && p.z < 0.40) {
                    float dxL = abs(p.x + 0.35);
                    if (dxL < 0.012) m = max(m, (1.0 - smoothstep(0.008, 0.012, dxL)));
                }
                // (L7) ROCKER LINE — single horizontal on lower left.
                if (n.x < -0.6) {
                    float dyL = abs(p.y - 0.42);
                    if (dyL < 0.010 && p.z > -2.00 && p.z < 2.00) {
                        m = max(m, (1.0 - smoothstep(0.007, 0.010, dyL)));
                    }
                }
            }

            if (inArch) m = 0.0;
            return m;
        }
"""

_CYBER_MAP = r"""
        vec2 map(vec3 p) { return sdCar(p); }"""

_CYBER_SHADE = r"""
        // Neutral procedural env reflection — light-gray dome with a
        // slightly brighter sky and slightly darker ground. NO baked
        // stylization (no magenta horizon, no navy zenith). The
        // cyberpunk sedan is meant to be dropped into arbitrary
        // production scenes — daylight street, indoor showroom, neon
        // alley, sunset highway, etc. — and chrome should read silver
        // in any of them. uPaint drives the cyberpunk character via
        // emissive accents (underglow strip, accent strips, hex grille
        // glow, body fresnel rim), not via env tinting.
        vec3 cyberpunkSky(vec3 rd) {
            float t = clamp(rd.y * 0.5 + 0.5, 0.0, 1.0);
            vec3 ground = vec3(0.40, 0.40, 0.42);
            vec3 sky    = vec3(0.78, 0.80, 0.82);
            return mix(ground, sky, pow(t, 0.7));
        }

        float cyberpunkAO(vec3 p, vec3 n) {
            float occ = 0.0; float sca = 1.0;
            for (int i = 0; i < 5; i++) {
                float hr = 0.01 + 0.14 * float(i) / 4.0;
                float dd = map(p + n * hr).x;
                occ += (hr - dd) * sca;
                sca *= 0.92;
            }
            return clamp(1.0 - 2.5 * occ, 0.0, 1.0);
        }

        vec3 shade(vec3 p, vec3 n, float mat) {
            int matID = int(mat + 0.5);

            vec3 SUN_DIR = normalize(vec3(0.45, 0.78, 0.30));
            vec3 V    = normalize(cameraPosition - p);
            vec3 rd   = -V;
            vec3 H    = normalize(SUN_DIR + V);
            float NdL = max(dot(n, SUN_DIR), 0.0);
            float NdV = max(dot(n, V), 0.0);
            float NdH = max(dot(n, H), 0.0);

            float sh   = softShadow(p + n * 0.004, SUN_DIR, 0.01, 12.0, 24.0);
            float ao   = cyberpunkAO(p, n);
            float fres = pow(1.0 - NdV, 5.0);
            // Env reflection sampled from the actual scene HDRI when
            // available, falling back to a neutral mid-gray. Ambient
            // sky term sampled at world-up so it tracks the actual
            // scene's sky/ceiling rather than a baked stylized colour.
            vec3 envR  = sampleEnvMap(sdfReflectWorld(p, n));
            vec3 sun   = vec3(1.15, 1.05, 0.85);
            vec3 sky   = sampleEnvMap(vec3(0.0, 1.0, 0.0));
            vec3 col;

            if (matID == int(MAT_PAINT)) {
                // Body stays near-black; uPaint shows on the silhouette
                // via fresnel rim. Stripes are off-white racing decals
                // baked on top via stripeMaskFn — non-emissive but
                // self-illuminated so they read on shadowed faces.
                vec3 base = vec3(0.018, 0.018, 0.022);
                float rough = max(uRough, 0.20);
                float metallic = 0.7;
                float sm = stripeMaskFn(p, n);
                vec3 stripeCol = vec3(0.92, 0.90, 0.85);
                base = mix(base, stripeCol, sm);
                rough = mix(rough, 0.55, sm);
                metallic = mix(metallic, 0.0, sm);

                vec3 diffuse = base * (NdL * sh * sun * 0.5 + sky * ao * 0.40);
                float a = max(rough, 0.06); a = a * a;
                float D = a / (3.14159 * pow(NdH * NdH * (a - 1.0) + 1.0, 2.0));
                vec3 F = mix(vec3(0.04), vec3(0.5), metallic);
                vec3 sunSpec = sun * D * F * sh;
                vec3 envCol  = envR * F * (1.0 - rough * 0.8) * 0.7;

                // Accent fresnel rim — uPaint glows on silhouette edges,
                // suppressed where the stripe is painted.
                float rim = pow(1.0 - NdV, 4.0);
                vec3 rimGlow = uPaint * rim * 0.55 * (1.0 - sm);

                col = diffuse + envCol + sunSpec + rimGlow;
                col *= mix(0.55, 1.0, ao);
                col += stripeCol * sm * 0.45;
            }
            else if (matID == int(MAT_GLASS)) {
                vec3 tint = vec3(0.01, 0.012, 0.018);
                col = tint + envR * (fres * 0.9 + 0.08);
                col += sky * 0.02;
                col += sun * pow(NdH, 80.0) * sh * 0.6;
            }
            else if (matID == int(MAT_TIRE)) {
                vec3 base = vec3(0.025, 0.025, 0.028);
                col = base * (NdL * sh * sun + sky * ao + 0.04);
                col += envR * 0.03 * fres;
            }
            else if (matID == int(MAT_RIM)) {
                vec3 base = vec3(0.55, 0.55, 0.58);
                col = base * (NdL * sh * sun * 0.5 + sky * ao);
                col += envR * (fres * 0.7 + 0.25) * 0.9;
                col += sun * pow(NdH, 40.0) * sh;
            }
            else if (matID == int(MAT_CHROME)) {
                // PBR-style chrome — explicitly metalness = 1.0,
                // roughness = 0.0. Pure mirror finish.
                const float metalness = 1.0;
                const float roughness = 0.0;
                // metalness=1: no diffuse term, full env reflection
                //              (F0 = white for chrome, so envR not tinted).
                col = envR * metalness;
                // roughness=0: specular concentrates to a single
                //              point at the exact mirror direction.
                //              Approximated with a very high exponent
                //              that grows as roughness → 0.
                float specExp = mix(64.0, 4096.0, 1.0 - roughness);
                col += sun * pow(NdH, specExp) * sh * 16.0;
            }
            else if (matID == int(MAT_HEAD)) {
                vec3 emit = vec3(1.6, 1.55, 1.35);
                float core = pow(1.0 - fres, 3.0);
                col  = emit * (0.55 + core * 1.4);
                col += envR * fres * 0.5;
                col += sun * pow(NdH, 200.0) * sh * 1.2;
            }
            else if (matID == int(MAT_TAIL)) {
                vec3 redEmit = vec3(1.9, 0.10, 0.05);
                float core = mix(0.7, 1.2, pow(1.0 - fres, 2.0));
                col  = redEmit * core;
                col += envR * fres * 0.25;
                col += vec3(1.0, 0.4, 0.3) * pow(NdH, 80.0) * sh * 0.4;
            }
            else if (matID == int(MAT_UNDERGLOW)) {
                col = uPaint * 2.2;
                col += uPaint * pow(1.0 - fres, 2.0) * 0.6;
            }
            else if (matID == int(MAT_ACCENT)) {
                col = uPaint * 1.5;
                col += uPaint * pow(1.0 - fres, 2.0) * 0.4;
            }
            else if (matID == int(MAT_GRILLE)) {
                // Procedural hex tiling on the grille plate face. Two
                // candidate hex-cell centres per fragment (offset rows);
                // distance to nearest gives wallEdge. Cells glow uPaint;
                // edges read as a dark mesh.
                vec2 gp = vec2(p.x, p.y - 0.55) * 22.0;
                vec2 s  = vec2(1.0, 1.7320508);
                vec2 hC  = (floor( gp           / s) + 0.5) * s;
                vec2 hC2 = (floor((gp - s*0.5) / s) + 0.5) * s + s*0.5;
                float hexD = min(length(gp - hC), length(gp - hC2));
                float wallEdge = smoothstep(0.55, 0.78, hexD);
                vec3 dark = vec3(0.005);
                vec3 glow = uPaint * 0.85;
                col = mix(glow, dark, wallEdge);
                col *= (NdL * sh * 0.4 + 0.6);
                col += envR * fres * 0.15;
            }
            else if (matID == int(MAT_BADGE)) {
                // UV unwrap from the local surface position. The plate
                // bounds (in model space) are pm.x ≈ 0.834, y ∈ [1.105,
                // 1.195], z ∈ [-1.11, -0.79]. v maps the y-extent; u
                // walks the z-extent (reversed on the right side so the
                // text reads left-to-right from outside on both sides).
                vec3 pmS = vec3(abs(p.x), p.y, p.z);
                float u, v;
                v = (pmS.y - 1.105) / 0.09;
                if (p.x > 0.0) {
                    u = (-0.79 - p.z) / 0.32;
                } else {
                    u = (p.z + 1.11) / 0.32;
                }
                vec4 txt = texture2D(uDecal, vec2(u, v));
                vec3 plateBase = vec3(0.012, 0.012, 0.015);
                vec3 plateLit  = plateBase * (NdL * sh * sun * 0.5 + sky * ao);
                plateLit += envR * fres * 0.08;
                plateLit += sun * pow(NdH, 16.0) * sh * 0.15;
                vec3 glyphCol = vec3(1.4, 1.4, 1.4);
                // Limit the decal to outward-facing sides of the plate
                // so it doesn't bleed onto edges or rear face.
                float faceMask = step(0.7, abs(n.x));
                float ink = txt.a * faceMask;
                if (u < 0.0 || u > 1.0 || v < 0.0 || v > 1.0) ink = 0.0;
                col = mix(plateLit, glyphCol, ink);
            }
            else {
                // MAT_PLASTIC — matte black grille intake / lower bumper.
                vec3 base = vec3(0.012, 0.012, 0.015);
                col = base * (NdL * sh * sun * 0.5 + sky * ao) + envR * fres * 0.08;
                col += sun * pow(NdH, 16.0) * sh * 0.15;
            }

            return col;
        }"""

_CP = P.CYBER['paint']
_CG = P.CYBER['grille']
_CB = P.CYBER['badge']
_CYBER_SURFACE = _surface('cyber', {
    'paint': _t(r"""
                // a near-black gunmetal body (F 0.36 x 0.7) under the racing stripes, off-white dielectric decals;
                // the uPaint rim glow becomes a sheen of that tint, the stripes' self-light a little emission
                float sm = stripeMaskFn(p, n);
                vec3 stripeCol = $stripe;
                s = sdfSurface(mix($body, stripeCol, sm), mix(max(uRough, $floor), $stripe_rough, sm));
                s.metallic = 1.0 - sm;
                s.coat = $coat * (1.0 - sm);
                s.sheen = $rim * (1.0 - sm);
                s.sheenTint = uPaint;
                s.emission = stripeCol * sm * $stripe_glow;""",
                stripe=P.glsl_vec3(_CP['stripe']), body=P.glsl_vec3(_CP['albedo']),
                floor=P.glsl_float(P.PAINT_FLOOR['cyber']), stripe_rough=P.glsl_float(_CP['stripe_roughness']),
                coat=P.glsl_float(_CP['coat']), rim=P.glsl_float(_CP['rim_glow']),
                stripe_glow=P.glsl_float(_CP['stripe_glow'])),
    'underglow': _t(r"""
                s = sdfSurface(vec3(0.0), $r);
                s.specular = $spec;
                s.emission = uPaint * ($k0 + $k1);""", r=P.glsl_float(P.CYBER['underglow']['roughness']),
                spec=P.glsl_float(P.CYBER['underglow']['specular']), k0=P.glsl_float(P.CYBER['underglow']['glow'][0]),
                k1=P.glsl_float(P.CYBER['underglow']['glow'][1])),
    'accent': _t(r"""
                s = sdfSurface(vec3(0.0), $r);
                s.specular = $spec;
                s.emission = uPaint * ($k0 + $k1);""", r=P.glsl_float(P.CYBER['accent']['roughness']),
                spec=P.glsl_float(P.CYBER['accent']['specular']), k0=P.glsl_float(P.CYBER['accent']['glow'][0]),
                k1=P.glsl_float(P.CYBER['accent']['glow'][1])),
    'grille': _t(r"""
                // shade()'s hex tiling on the grille face: cells glow uPaint, the walls are a dark mesh
                vec2 gp = vec2(p.x, p.y - 0.55) * 22.0;
                vec2 hs2 = vec2(1.0, 1.7320508);
                vec2 hC  = (floor(gp / hs2) + 0.5) * hs2;
                vec2 hC2 = (floor((gp - hs2 * 0.5) / hs2) + 0.5) * hs2 + hs2 * 0.5;
                float hexD = min(length(gp - hC), length(gp - hC2));
                float wallEdge = smoothstep(0.55, 0.78, hexD);
                vec3 glow = uPaint * $glow;
                s = sdfSurface(mix(min(glow, vec3(1.0)) * 0.4, $dark, wallEdge), $r);
                s.specular = $spec;
                s.emission = glow * 0.6 * (1.0 - wallEdge);""", glow=P.glsl_float(_CG['cell_glow']),
                dark=P.glsl_vec3(_CG['albedo']), r=P.glsl_float(_CG['roughness']), spec=P.glsl_float(_CG['specular'])),
    'badge': _t(r"""
                // the plate unwrapped from the local position (z walks u, reversed on the right side so the text
                // reads left to right from outside), the canvas alpha as ink on the outward faces only
                float v = (p.y - 1.105) / 0.09;
                float u = p.x > 0.0 ? (-0.79 - p.z) / 0.32 : (p.z + 1.11) / 0.32;
                vec4 txt = texture(uDecal, vec2(u, v));
                float ink = txt.a * step(0.7, abs(n.x));
                if (u < 0.0 || u > 1.0 || v < 0.0 || v > 1.0) ink = 0.0;
                s = sdfSurface(mix($plate, vec3(0.8), ink), $r);
                s.specular = $spec;
                s.emission = $ink * ink;""", plate=P.glsl_vec3(_CB['albedo']), r=P.glsl_float(_CB['roughness']),
                spec=P.glsl_float(_CB['specular']), ink=P.glsl_vec3(_CB['ink'])),
})

register_example(
    'stylized_cyberpunk_sedan', kind='solid', make=make_cyberpunk_sedan,
    description='cyberpunk sedan: near-black body, uPaint rim / underglow / accents / hex grille glow, asymmetric '
                'racing stripes, chrome domes, ALETH8APO badge; make(paint_color, paint_roughness, decal_text)',
    bounds={'min': [-1.05, 0.0, -2.4], 'max': [1.05, 1.55, 2.4]},
    quality='high', voxel=VEHICLE_VOXEL['cyber'],
    uniforms={'uPaint': ('color', P.CYBER_DEFAULTS['uPaint']), 'uRough': P.CYBER_DEFAULTS['uRough']},
    textures={'uDecal': decal_texture_array()},
    extra=_CYBER_EXTRA, map=_CYBER_MAP, shade=_CYBER_SHADE, surface=_CYBER_SURFACE,
    material_settings={'coat_roughness': 0.045, 'sheen_roughness': 0.3},   # 0.25 x paintRoughness 0.18
)


# ======================================================================================== stylizedSciFiSleekCar ===
# A streamlined sci-fi compact built from CYLINDER SECTIONS rather than rounded boxes: the roof-to-side arc is one
# cylinder whose axis sits above the car (length(p.yz) of a shifted p), its lower half visible. The body is METAL:
# uMetalColor is its F0 (silver, gold, copper, anodised blue ...), uRough the brushed-vs-mirror finish. Authored at
# pre-scale with an internal S = 1.5. Bounds: x +-1.10 and z +-2.10 as the engine had them (they hold the shape:
# the fender bulges reach x 0.8925, the ends z 1.935); y -0.0675..1.21, measured. The engine declared y -0.63..1.10:
# its tyres (tori about the axle at pre-scale y 0.20, radius 0.20 + 0.045) bottom out at -0.045 x 1.5 = -0.0675, so
# the placement rule (bounds.min.y on the ground) floated the car 0.56 m up; and the roof arc crests at 1.203, so a
# box ending at 1.10 cut 10 cm off it. The engine's march walked back out of its box and drew the roof anyway; a
# mesh closes at its bounds, so here the bounds hold the whole car.
_SLEEK_EXTRA = r"""
        #define MAT_PAINT   0.0
        #define MAT_GLASS   1.0
        #define MAT_TIRE    2.0
        #define MAT_CHROME  4.0
        #define MAT_HEAD    5.0
        #define MAT_TAIL    6.0

        uniform vec3  uMetalColor;
        uniform float uRough;

        // Main body — built using the cylinder-section technique.
        // length(p.yz) measures distance from the X-axis in the YZ
        // plane. Constraining it below a threshold gives a cylinder
        // along X; clipping the upper half gives the curved roof
        // sweeping in one continuous arc to each side.
        float mapBody(vec3 p0) {
            // Main body shell — cylinder centered ABOVE the car so
            // the visible (lower) half forms the roof arching down
            // to the sides.
            vec3 p = p0 + vec3(0.0, 1.05, 0.0);
            float r = length(p.yz);
            float d = length(max(vec3(abs(p.x) - 0.32, r - 1.78, -p.y + 1.30), 0.0)) - 0.06;
            d = max(d, abs(p.z) - 1.10);

            // Nose tuck — second cylinder section pulled forward
            // and down; smin'd into the body for a sloped nose.
            vec3 pn = p0 + vec3(0.0, 0.55, -0.40);
            float rn = length(pn.yz);
            float dn = length(max(vec3(abs(pn.x) - 0.30, rn - 0.95, -pn.y + 0.70), 0.0)) - 0.05;
            dn = max(dn, abs(pn.z) - 0.55);
            d = smin(d, dn, 0.10);

            // Fender bulges (4 wheels via abs() folding).
            vec3 pf = p0 + vec3(0.0, -0.20, 0.0);
            pf.xz = abs(pf.xz) - vec2(0.42, 0.95);
            pf.x = abs(pf.x);
            float rf = length(pf.yz);
            float df = length(max(vec3(pf.x - 0.06, rf - 0.30, -pf.y - 0.06), 0.0)) - 0.04;
            d = smin(d, df, 0.06);

            // Belt-line indent (thin horizontal subtraction at mid-side).
            vec3 pb = p0;
            float belt = max(
                abs(pb.y - 0.30) - 0.012,
                max(0.32 - abs(pb.x), abs(pb.z) - 1.00)
            );
            d = max(d, -belt + 0.005);

            // Wheel arch carve (cylinder subtraction at each wheel).
            float archCut = max(pf.x - 0.18, length(pf.yz) - 0.26);
            d = max(d, -archCut);

            return d;
        }

        // Capped torus tire — 4 wheels via the same fender folding.
        float mapTire(vec3 p0) {
            vec3 pf = p0 + vec3(0.0, -0.20, 0.0);
            pf.xz = abs(pf.xz) - vec2(0.42, 0.95);
            pf.x = abs(pf.x);
            return length(vec2(max(pf.x - 0.13, 0.0), length(pf.yz) - 0.20)) - 0.045;
        }

        // Body + glass + lights + hubcaps. Internally authored at
        // pre-scale; final SDF distance multiplied by S to give
        // world-space distances the marcher can step through.
        vec2 sdCar(vec3 p) {
            const float S = 1.5;
            vec3 pl = p / S;
            vec3 plm = vec3(abs(pl.x), pl.y, pl.z);

            float body = mapBody(pl);
            vec2 res = vec2(body * S, MAT_PAINT);

            float tire = mapTire(pl);
            res = opU(res, vec2(tire * S, MAT_TIRE));

            // Glass patches — thin shell straddling the body surface,
            // gated to specific regions for windshield / rear / sides.
            float bodyShell = abs(body) - 0.012;

            // Windshield: front-upper roof.
            float wsRegion = max(
                max(pl.z - 0.10, -0.65 - pl.z),
                max(0.42 - pl.y, plm.x - 0.30)
            );
            float windshield = max(bodyShell, wsRegion);

            // Rear glass: rear-upper roof.
            float rwRegion = max(
                max(pl.z - 0.90, 0.30 - pl.z),
                max(0.42 - pl.y, plm.x - 0.30)
            );
            float rearGlass = max(bodyShell, rwRegion);

            // Side window: half-ellipse profile, flat-bottom at the
            // beltline, single curve sweeping front-to-rear.
            vec2 yz_p = vec2(pl.y, pl.z);
            vec2 yz_c = vec2(0.45, -0.05);
            vec2 d_yz = (yz_p - yz_c) / vec2(0.30, 0.60);
            float ellipse = length(d_yz) - 1.0;
            float halfEllipse = max(ellipse, 0.45 - pl.y);
            float swRegion = max(halfEllipse, max(0.32 - plm.x, plm.x - 0.45));
            float sideWin = max(bodyShell, swRegion);

            float glass = min(min(windshield, rearGlass), sideWin);
            res = opU(res, vec2(glass * S, MAT_GLASS));

            // Headlights & taillights — 2 each, hand-tuned positions.
            float hlR = sdSphere(pl - vec3( 0.146, 0.311,  1.080), 0.06);
            float hlL = sdSphere(pl - vec3(-0.154, 0.310,  1.072), 0.06);
            res = opU(res, vec2(min(hlR, hlL) * S, MAT_HEAD));

            float tlR = sdSphere(pl - vec3( 0.151, 0.286, -1.077), 0.06);
            float tlL = sdSphere(pl - vec3(-0.152, 0.281, -1.079), 0.06);
            res = opU(res, vec2(min(tlR, tlL) * S, MAT_TAIL));

            // Chrome hubcap discs filling the wheel wells.
            vec3 wp = pl + vec3(0.0, -0.20, 0.0);
            wp.xz = abs(wp.xz) - vec2(0.42, 0.95);
            wp.x = abs(wp.x);
            float wr = length(wp.yz);
            float hubcap = max(wr - 0.16, max(wp.x - 0.16, 0.10 - wp.x));
            res = opU(res, vec2(hubcap * S, MAT_CHROME));

            return res;
        }"""

_SLEEK_MAP = r"""
        vec2 map(vec3 p) { return sdCar(p); }"""

_SLEEK_SHADE = r"""
        vec3 shade(vec3 p, vec3 n, float mat) {
            int matID = int(mat + 0.5);

            vec3 SUN_DIR = normalize(vec3(0.45, 0.78, 0.30));
            vec3 V    = normalize(cameraPosition - p);
            vec3 H    = normalize(SUN_DIR + V);
            float NdL = max(dot(n, SUN_DIR), 0.0);
            float NdV = max(dot(n, V), 0.0);
            float NdH = max(dot(n, H), 0.0);

            float sh   = softShadow(p + n * 0.004, SUN_DIR, 0.01, 12.0, 24.0);
            float fres = pow(1.0 - NdV, 5.0);
            vec3 envR  = sampleEnvMap(sdfReflectWorld(p, n));
            vec3 sun   = vec3(1.15, 1.05, 0.85);
            vec3 sky   = sampleEnvMap(vec3(0.0, 1.0, 0.0));
            vec3 col;

            if (matID == int(MAT_PAINT)) {
                // Pure metal body. uMetalColor IS F0 — the metal's
                // characteristic specular tint (gold = warm yellow,
                // copper = pinkish brown, silver = neutral white,
                // anodized = saturated tints). Schlick fresnel pushes
                // it toward white at glancing angles. No diffuse.
                vec3 F0 = uMetalColor;
                vec3 F  = F0 + (vec3(1.0) - F0) * fres;
                float rough = max(uRough, 0.06);

                float a = rough * rough;
                float D = a / (3.14159 * pow(NdH * NdH * (a - 1.0) + 1.0, 2.0));
                vec3 sunSpec = sun * D * F * sh;

                // Full env reflection scaled by roughness; F0 tints
                // the whole env so the entire body reads as that metal.
                vec3 envCol = envR * F * (1.0 - rough * 0.4);

                col = envCol + sunSpec * 1.5;
                // Tiny F0-tinted ambient bounce so deeply-shadowed
                // metal doesn't go pitch black on dim HDRIs.
                col += F0 * sky * 0.05;
            }
            else if (matID == int(MAT_GLASS)) {
                vec3 tint = vec3(0.01, 0.012, 0.018);
                col = tint + envR * (fres * 0.9 + 0.08);
                col += sun * pow(NdH, 80.0) * sh * 0.6;
            }
            else if (matID == int(MAT_TIRE)) {
                vec3 base = vec3(0.025, 0.025, 0.028);
                col = base * (NdL * sh * sun + sky * 0.3 + 0.04);
                col += envR * 0.03 * fres;
            }
            else if (matID == int(MAT_CHROME)) {
                // Hex-tiled chrome hubcap. Re-apply the same
                // fender folding used in mapBody/sdCar so the
                // hex grid stays centred on each wheel hub for
                // all 4 wheels.
                vec3 wp = p / 1.5 + vec3(0.0, -0.20, 0.0);
                wp.xz = abs(wp.xz) - vec2(0.42, 0.95);
                wp.x  = abs(wp.x);

                // Standard 60° hex tiling on the disc plane
                // (yz, perpendicular to the wheel axle): two
                // offset rectangular lattices, pick the closer
                // centre per fragment.
                vec2 uv = wp.yz * 12.0;
                vec2 r  = vec2(1.0, 1.7320508);
                vec2 hs = r * 0.5;
                vec2 a  = mod(uv,      r) - hs;
                vec2 b  = mod(uv - hs, r) - hs;
                vec2 gv = dot(a, a) < dot(b, b) ? a : b;
                float hexD = max(abs(gv.x) * 0.866 + abs(gv.y) * 0.5, abs(gv.y));
                // 0 deep inside cell, 1 on the cell border.
                float hexEdge = smoothstep(0.40, 0.47, hexD);

                // Cell interior = mirror silver; cell border
                // gets darkened F0 + extra roughness so the
                // hex lattice reads against the HDRI reflection.
                vec3 chromeF0 = vec3(0.95, 0.93, 0.88);
                vec3 F0       = mix(chromeF0, chromeF0 * 0.35, hexEdge);
                vec3 F        = F0 + (vec3(1.0) - F0) * fres;
                float roughC  = mix(0.02, 0.20, hexEdge);

                col  = envR * F * (1.0 - roughC * 0.5);
                col += sun * pow(NdH, mix(1500.0, 80.0, hexEdge)) * sh * mix(16.0, 4.0, hexEdge);
            }
            else if (matID == int(MAT_HEAD)) {
                vec3 emit = vec3(3.6, 3.5, 3.0);
                float core = pow(1.0 - fres, 3.0);
                col  = emit * (0.85 + core * 1.6);
                col += envR * fres * 0.3;
                col += sun * pow(NdH, 200.0) * sh * 1.0;
            }
            else if (matID == int(MAT_TAIL)) {
                vec3 redEmit = vec3(4.5, 0.18, 0.08);
                float core = mix(0.95, 1.5, pow(1.0 - fres, 2.0));
                col  = redEmit * core;
                col += envR * fres * 0.18;
            }
            else {
                col = vec3(0.5);
            }

            return col;
        }"""

_SC = P.SLEEK['chrome']
_SLEEK_SURFACE = _surface('sleek', {
    'paint': _t(r"""
                // pure metal: uMetalColor is F0, Schlick to white at grazing (Principled metallic), no diffuse
                s = sdfSurface(uMetalColor, max(uRough, $floor));
                s.metallic = 1.0;""", floor=P.glsl_float(P.PAINT_FLOOR['sleek'])),
    'chrome': _t(r"""
                // the hex-tiled hubcap: re-folded to the wheel frame, 60-degree hex cells on the disc plane; mirror
                // cells, a darker rougher border
                vec3 wp = p / 1.5 + vec3(0.0, -0.20, 0.0);
                wp.xz = abs(wp.xz) - vec2(0.42, 0.95);
                wp.x  = abs(wp.x);
                vec2 uv = wp.yz * 12.0;
                vec2 r  = vec2(1.0, 1.7320508);
                vec2 hs = r * 0.5;
                vec2 a  = mod(uv,      r) - hs;
                vec2 b  = mod(uv - hs, r) - hs;
                vec2 gv = dot(a, a) < dot(b, b) ? a : b;
                float hexD = max(abs(gv.x) * 0.866 + abs(gv.y) * 0.5, abs(gv.y));
                float hexEdge = smoothstep(0.40, 0.47, hexD);
                vec3 chromeF0 = $f0;
                s = sdfSurface(mix(chromeF0, chromeF0 * $edge, hexEdge), mix($r0, $r1, hexEdge));
                s.metallic = 1.0;""", f0=P.glsl_vec3(_SC['albedo']), edge=P.glsl_float(_SC['edge_scale']),
                r0=P.glsl_float(_SC['roughness']), r1=P.glsl_float(_SC['edge_roughness'])),
})

register_example(
    'stylized_sci_fi_sleek_car', kind='solid', make=make_sci_fi_sleek_car,
    description='sci-fi compact from cylinder sections: a pure-metal body (uMetalColor is F0), glass patches, sphere '
                'lamps, hex-tiled chrome hubcaps; make(metal_color, paint_roughness)',
    bounds={'min': [-1.10, -0.0675, -2.10], 'max': [1.10, 1.21, 2.10]},
    quality='high', voxel=VEHICLE_VOXEL['sleek'],
    uniforms={'uMetalColor': ('vec3', P.SLEEK_DEFAULTS['uMetalColor']), 'uRough': P.SLEEK_DEFAULTS['uRough']},
    extra=_SLEEK_EXTRA, map=_SLEEK_MAP, shade=_SLEEK_SHADE, surface=_SLEEK_SURFACE,
    material_settings={'coat_roughness': 0.05},
)


# =========================================================================================== stylizedFighterJet ===
# A bilateral hull / wing / tail / engine-pod solid built from smooth-unioned ellipsoids, boxes and Z-axis capped
# cylinders, CSG-cut engine bores with turbine faces and exhaust struts, a bubble canopy, emissive plumes, wing-pylon
# AAMs and a centreline bomb. uCamoMode: 0 silver, 1 sky (default), 2 desert, 3 forest; the dark nose cone and the
# wing pinstripes carry through every scheme. Bounds: x +-3.0 as declared (the wing tips reach 2.9); y -0.7374 (the
# bomb fins' lowest corner, -0.55 - (0.25 sin 0.785 + 0.015 cos 0.785)) to 1.15; z -4.1 to 4.30. The engine declared
# y -0.9 (a 16 cm float under its placement rule) and z 3.4: the nose ellipsoid's distance bound shrinks the field
# 10x along its axis, so smin(k = 0.6) with the hull carries the surface out to a long point at z = 4.294; the
# engine's march walked back out of its box to draw it, and a mesh needs it inside. The canted fins splay outward,
# turned as the public engine's TSL map turns them (see the module docstring).
_JET_EXTRA = r"""
        #define MAT_HULL    0.0
        #define MAT_GLASS   1.0
        #define MAT_WEAPON  2.0
        #define MAT_PLUME   3.0

        uniform float uCamoMode;

        // Local helpers — loader doesn't ship a 2D rotation mat or a
        // Z-axis cylinder primitive, so define them in the example's
        // own scope to avoid stomping on agent code.
        mat2 _jetRot2(float a) { float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }
        float _jetCylZ(vec3 p, vec2 h) {
            vec2 d = abs(vec2(length(p.xy), p.z)) - h;
            return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
        }

        vec2 sdJet(vec3 p) {
            vec2 res = vec2(1000.0, 0.0);

            // Bilateral symmetry around the X=0 plane.
            vec3 pSym = p;
            pSym.x = abs(pSym.x);

            // ---- Hull / wings / tail / engine pods (single solid) ----
            float hull = sdEllipsoid(p - vec3(0.0, 0.0, -0.5), vec3(0.45, 0.35, 3.0));
            hull = smin(hull,
                        sdEllipsoid(p - vec3(0.0, -0.05, 1.8), vec3(0.20, 0.15, 1.5)),
                        0.6);

            // Main wings — domain shear gives them a swept silhouette.
            vec3 pWing = pSym - vec3(0.4, 0.0, -0.5);
            pWing.z -= pWing.x * 0.8;
            float wings = sdBox(pWing, vec3(2.5, 0.025, 0.9));
            hull = smin(hull, wings, 0.2);

            // Horizontal stabilizers + canted vertical fins (F-18 style).
            vec3 pTail = pSym - vec3(0.4, 0.0, -2.5);
            pTail.z -= pTail.x * 0.6;
            float rearWing = sdBox(pTail, vec3(1.2, 0.02, 0.5));
            hull = smin(hull, rearWing, 0.15);

            vec3 pFin = pSym - vec3(0.3, 0.4, -2.4);
            // the public engine's rotation (its TSL map: x c - y s, x s + y c), so the fins splay outward,
            // F-18 style; the backup's pFin.xy *= _jetRot2(0.2) multiplied the row vector and leaned them inward
            pFin.xy = _jetRot2(0.2) * pFin.xy;
            pFin.z -= pFin.y * 0.8;
            float fin = sdBox(pFin, vec3(0.02, 0.6, 0.5));
            hull = smin(hull, fin, 0.2);

            // Engine pods — outer shell, then inner-bore subtraction so
            // the intake/exhaust holes punch cleanly through everything
            // we already smin'd above.
            vec3 pEng = pSym - vec3(0.65, -0.05, -1.5);
            float engOuter = _jetCylZ(pEng, vec2(0.35, 1.2));
            float engInner = _jetCylZ(pEng, vec2(0.28, 1.3));
            hull = smin(hull, engOuter, 0.2);
            hull = max(hull, -engInner);

            // Turbine face + exhaust struts (visible inside the bore).
            float turbineFace = _jetCylZ(pEng - vec3(0.0, 0.0, 0.8), vec2(0.28, 0.02));
            vec3 pExh = pEng - vec3(0.0, 0.0, -0.8);
            float exhCone = _jetCylZ(pExh, vec2(0.10, 0.3));
            float struts  = sdBox(pExh, vec3(0.28, 0.015, 0.15));
            struts        = min(struts, sdBox(pExh, vec3(0.015, 0.28, 0.15)));
            hull = min(hull, min(turbineFace, min(exhCone, struts)));

            res = opU(res, vec2(hull, MAT_HULL));

            // ---- Cockpit canopy (bubble glass) ----
            float canopy = sdEllipsoid(p - vec3(0.0, 0.28, 1.2), vec3(0.18, 0.20, 0.8));
            res = opU(res, vec2(canopy, MAT_GLASS));

            // ---- Engine plume (emissive ellipsoid behind each nozzle) ----
            float plume = sdEllipsoid(pEng - vec3(0.0, 0.0, -1.4), vec3(0.18, 0.18, 0.4));
            res = opU(res, vec2(plume, MAT_PLUME));

            // ---- Wing pylons + AAMs (built in the wing-swept frame so
            //      they hang parallel to the wing chord, not world Z). ----
            vec3 pMis = pWing - vec3(1.5, -0.25, 0.0);
            float pylon = sdBox(pMis - vec3(0.0, 0.12, 0.0), vec3(0.015, 0.12, 0.3));
            res = opU(res, vec2(pylon, MAT_HULL));

            float missile = _jetCylZ(pMis, vec2(0.08, 0.8));
            missile = min(missile, sdEllipsoid(pMis - vec3(0.0, 0.0, 0.8), vec3(0.08, 0.08, 0.2)));
            missile = min(missile, sdBox(pMis - vec3(0.0, 0.0, -0.6), vec3(0.20, 0.01, 0.15)));
            missile = min(missile, sdBox(pMis - vec3(0.0, 0.0, -0.6), vec3(0.01, 0.20, 0.15)));
            res = opU(res, vec2(missile, MAT_WEAPON));

            // ---- Centerline bomb (asymmetric — built in unmirrored p) ----
            vec3 pBomb = p - vec3(0.0, -0.55, -0.5);
            float bombPylon = sdBox(pBomb - vec3(0.0, 0.22, 0.0), vec3(0.02, 0.22, 0.4));
            res = opU(res, vec2(bombPylon, MAT_HULL));

            float bomb = _jetCylZ(pBomb, vec2(0.15, 0.9));
            bomb = min(bomb, sdEllipsoid(pBomb - vec3(0.0, 0.0,  0.9), vec3(0.15, 0.15, 0.3)));
            bomb = min(bomb, sdEllipsoid(pBomb - vec3(0.0, 0.0, -0.9), vec3(0.15, 0.15, 0.3)));
            vec3 pbFin = pBomb - vec3(0.0, 0.0, -0.7);
            pbFin.xy *= _jetRot2(0.785);
            bomb = min(bomb, sdBox(pbFin, vec3(0.25, 0.015, 0.15)));
            bomb = min(bomb, sdBox(pbFin, vec3(0.015, 0.25, 0.15)));
            res = opU(res, vec2(bomb, MAT_WEAPON));

            return res;
        }
        // Camo color resolver. The CAMO BLOBS are the only part that
        // varies by mode — the dark nose cone and wing pinstripes carry
        // through every scheme so the silhouette still reads as a
        // military airframe and not a plastic toy.
        vec3 _jetCamoColor(vec3 p, float mode) {
            float blob = fbm(p * 1.6);
            float t = smoothstep(0.50, 0.52, blob);

            vec3 light, dark;
            if (mode < 0.5) {
                // 0 = silver / urban — light pewter on dark gunmetal.
                light = vec3(0.55, 0.57, 0.60);
                dark  = vec3(0.26, 0.27, 0.29);
            } else if (mode < 1.5) {
                // 1 = sky / air-superiority — saturated navy palette.
                //     Tuned dark enough to survive sun + HDRI fill
                //     without clipping at NdL≈1, and deep enough on
                //     blue that it doesn't drift toward neutral grey.
                light = vec3(0.30, 0.40, 0.62);
                dark  = vec3(0.08, 0.14, 0.34);
            } else if (mode < 2.5) {
                // 2 = desert — coyote tan on dark khaki.
                light = vec3(0.52, 0.42, 0.26);
                dark  = vec3(0.28, 0.20, 0.12);
            } else {
                // 3 = forest / woodland — olive on dark green-brown.
                light = vec3(0.30, 0.34, 0.18);
                dark  = vec3(0.12, 0.16, 0.08);
            }
            vec3 col = mix(light, dark, t);

            // Nose cone — dark sensor housing past z = 1.5, all modes.
            col = mix(col, vec3(0.20, 0.21, 0.22), smoothstep(1.5, 1.52, p.z));

            // Wing pinstripes (dark accent + light line) on the outer
            // wing panels. Mirror via abs(p.x) so both wings carry them.
            if (abs(p.x) > 0.6) {
                float ax = abs(p.x);
                col = mix(vec3(0.13), col, smoothstep(0.38, 0.40, abs(ax - 2.0)));
                col = mix(vec3(0.55), col, smoothstep(0.08, 0.10, abs(ax - 1.4)));
            }

            return col;
        }
"""

_JET_MAP = r"""
        vec2 map(vec3 p) { return sdJet(p); }"""

_JET_SHADE = r"""
        vec3 shade(vec3 p, vec3 n, float mat) {
            int matID = int(mat + 0.5);

            vec3 SUN_DIR = normalize(vec3(0.45, 0.78, 0.30));
            vec3 V    = normalize(cameraPosition - p);
            vec3 H    = normalize(SUN_DIR + V);
            float NdL = max(dot(n, SUN_DIR), 0.0);
            float NdV = max(dot(n, V), 0.0);
            float NdH = max(dot(n, H), 0.0);

            float sh   = softShadow(p + n * 0.004, SUN_DIR, 0.01, 12.0, 24.0);
            float fres = pow(1.0 - NdV, 5.0);
            vec3 envR  = sampleEnvMap(sdfReflectWorld(p, n));
            vec3 sun   = vec3(1.15, 1.05, 0.85);
            vec3 sky   = sampleEnvMap(vec3(0.0, 1.0, 0.0));
            vec3 col;

            if (matID == int(MAT_HULL)) {
                // All four schemes (including silver/urban) are painted
                // camo. Diffuse + soft sky fill + low-key dielectric
                // spec + a thin env sheen at grazing angles. Sky fill
                // intentionally low so HDRI brightness doesn't push the
                // mid-tones to white on lighter palettes.
                vec3 base = _jetCamoColor(p, uCamoMode);
                vec3 diffuse = base * (NdL * sh * sun + sky * 0.20 + vec3(0.05));
                vec3 spec    = sun * pow(NdH, 24.0) * sh * 0.25;
                vec3 env     = envR * fres * 0.10;
                col = diffuse + spec + env;
            }
            else if (matID == int(MAT_GLASS)) {
                vec3 tint = vec3(0.02, 0.04, 0.07);
                col = tint + envR * (fres * 0.95 + 0.06);
                col += sun * pow(NdH, 100.0) * sh * 0.7;
            }
            else if (matID == int(MAT_WEAPON)) {
                // Dark olive ordnance with subtle warning bands along the
                // missile/bomb body axis (sin-on-z gives even ribbing).
                vec3 base = vec3(0.20, 0.22, 0.18);
                float band = smoothstep(0.92, 1.0, abs(sin(p.z * 15.0)));
                base *= 1.0 - 0.25 * band;
                vec3 diffuse = base * (NdL * sh * sun + sky * 0.30 + vec3(0.04));
                col = diffuse + sun * pow(NdH, 48.0) * sh * 0.4 + envR * fres * 0.08;
            }
            else if (matID == int(MAT_PLUME)) {
                // Hot core fading to orange/red at the silhouette edge.
                float core = NdV;
                vec3 hot  = vec3(2.4, 2.2, 1.4);
                vec3 cool = vec3(2.0, 0.6, 0.15);
                col = mix(cool, hot, smoothstep(0.0, 0.7, core));
            }
            else {
                col = vec3(0.5);
            }

            return col;
        }"""

_JW = P.JET['weapon']
_JP = P.JET['plume']
_JET_SURFACE = _surface('jet', {
    'hull': _t(r"""
                // the camo paint: diffuse, a low-key highlight and a thin grazing sheen
                s = sdfSurface(_jetCamoColor(p, uCamoMode), $r);
                s.specular = $spec;""", r=P.glsl_float(P.JET['hull']['roughness']),
                spec=P.glsl_float(P.JET['hull']['specular'])),
    'weapon': _t(r"""
                // dark olive ordnance, warning bands along the body axis
                float band = smoothstep(0.92, 1.0, abs(sin(p.z * 15.0)));
                s = sdfSurface($base * (1.0 - $band * band), $r);
                s.specular = $spec;""", base=P.glsl_vec3(_JW['albedo']), band=P.glsl_float(_JW['band']),
                r=P.glsl_float(_JW['roughness']), spec=P.glsl_float(_JW['specular'])),
    'plume': _t(r"""
                // hot core head-on (the rim's orange needs the viewer: the part material draws it per pixel)
                s = sdfSurface(vec3(0.0), 1.0);
                s.specular = 0.0;
                s.emission = $hot;""", hot=P.glsl_vec3(_JP['hot'])),
})

register_example(
    'stylized_fighter_jet', kind='solid', make=make_fighter_jet,
    description="fighter jet: swept wings, canted fins, engine pods with bores, bubble canopy, emissive plumes, AAMs "
                "and a bomb, four camo schemes; make(camo='silver' | 'sky' | 'desert' | 'forest')",
    bounds={'min': [-3.0, -0.7374, -4.1], 'max': [3.0, 1.15, 4.30]},
    quality='high', voxel=VEHICLE_VOXEL['jet'],
    uniforms={'uCamoMode': P.JET_DEFAULTS['uCamoMode']},
    extra=_JET_EXTRA, map=_JET_MAP, shade=_JET_SHADE, surface=_JET_SURFACE,
)
