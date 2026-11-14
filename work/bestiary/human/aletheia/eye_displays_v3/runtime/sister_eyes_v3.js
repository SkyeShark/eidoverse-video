// THE SISTERS' CYBER EYES, v3: ONE DISPLAY SYSTEM, A STYLE PER CREATURE (STAGED in work/bestiary/human/aletheia/
// eye_displays_v3/: nothing live imports it). Copied 11-10 from eye_displays_v2/runtime/sister_eyes_v2.js (sha1
// f4c5ccd9c4d2, Fable 5.2's; v2 stays as it is). v3 adds:
//   STYLES     the style parameter: v2's four options are styles 1-4 (their marks, tails and glow as v2 had them) and
//              four new techniques join them (5 phosphor trace, 6 halftone dots, 7 counter-rotating, 8 glyph spiral).
//              A creature chooses one by name (styleGlb(name): that style's glb; attachSisterEyes reads the rest from
//              it). Every style runs the SAME state system below.
//   the beam (style 5), the dot field (style 6), the second spin node (style 7), a sister's own mark (style 8):
//              see TRACE, HALFTONE, SPIN2 and lineMaterial.
//   bindToFace the displays driven by a face's VRM expressions, the way my robot face's displays are driven.
// (fix r1, 11-10 after check_r1: eye_displays_v3/check_r1_NOTES.md) a blink now closes the lids from wherever a mood
// holds them (guardWeights / lidShare); bindToFace only LISTENS to the face (a probe reads what three-vrm applied; the
// face's own weights, binds and overrides are untouched) and unbinds; styleGlb throws on a name that is not a style;
// style 8's strokes hand their light to a carrier line as they go under 1.5 px (GLYPH8).
// (fix r2, 11-10 after check_r2: eye_displays_v3/fix_r2_NOTES.md) a face whose look-at sets no look expression (the
// Bestiary's bone look-at) glances the display from the look-at's own yaw / pitch (lookAtGaze); style 8's DEFAULT draws
// her name's letters as they were drawn before fix r1 at her head's distance and nearer, the carrier only further off,
// the whole name at once (GLYPH8.far); opts.glyphCarrier 'per_stroke' is fix r1's rule, 'off' the strokes alone.
// v2's header, kept (it says what the runtime does):
//
// THE SISTERS' CYBER EYES, v2: the displays' runtime (STAGED in work/bestiary/human/aletheia/eye_displays_v2/: nothing
// live imports it). r2_eyes' runtime (r2_eyes/staged/runtime/sister_eyes.js) with THE GRAPHICS AND THE GLOW replaced,
// after the owner's verdict on it ("oblong oval squished spirals", "solid lighter color in a circle", "proper graphics for the
// new eyes with proper glowing").
//
// KEPT from r2_eyes, as it was: the STATE SYSTEM: EYE_STATES (each state's keys, spin, pulse and glow), the VRM emotion
// map, the easing of every driven parameter, the pulse's integrated phase, the blink (a scheduled two-shutter wipe:
// 0.10 s closing, 0.05 s held, 0.16 s opening), the gaze, the guard's rule (the lids' summed weight and the scales' each
// at most 1), the spinning marks' look keys re-solved in their turned frame, the API (setState, setGaze, blink, set,
// clear, update). The marks are still my robot face's kind (plane meshes with morph targets, unskinned, riding the head).
//
// NEW:
// (1) THE MARKS are whatever the option's glb carries (scripts/eye_display_v2.py: four options), found by their extras
//     (role 'line' | 'lid'). None is a ground disc, nothing is stretched: there is no oval node.
// (2) THE GLOW: every lit mark is a GLOW LINE. Its strip carries the line's cross coordinates (uv = (a, b): a across,
//     -1 .. 1 between the rails; b 0 along the line and 1 where a cap column carries its end on), so each pixel knows how
//     far it is from the line: dn = |(a, b)| (0 on the line, 1 at the halo's reach). The pixel's light is PROFILE over
//     dn: a HOT CORE (narrow, the eye's colour pulled toward white: every hue's core at one luminance), the BODY (the
//     eye's colour, full), the HALO (the soft falloff, zero at the strip's rail), each widened by the pixel's footprint
//     and dimmed to match (a line thinner than a pixel keeps its light and does not crawl as it turns). Lit marks ADD to
//     the screen (additive, no depth write, nothing in the G-buffer: their own alpha is 0 and their light is the
//     output), so where pixels are off HER OWN BLACK GLASS shows, reflections and all.
// (3) THE LIDS ARE SHUTTERS, NOT GEOMETRY ON SCREEN: a lid is still a mesh with a shape key per state (what the state
//     system and a VRM's expressions drive), but it is not drawn. Each frame its edge (the edge row of its grid, at the
//     weights it holds) goes to the lit marks as 25 heights, and a lit pixel behind a lid is switched off, the cut
//     softened over one pixel. (An opaque lid would be a black sticker on her glass; a depth-only one, tried first,
//     changed the engine's ambient occlusion round the eyes.) The lids' lit edges are glow lines like the rest.
// (4) THE DISPLAY'S ROUND MASK: lit pixels end at the screen's active radius.
// (5) option 4's SCAN: a pulse running out along the arm (each vertex's phase).
// (6) THE GAZE no longer slides a disc: the look keys carry each vertex by (1 - r / r_look) of the gaze, so nothing
//     leaves the screen and the guard holds no gaze.
// (No mrtNode: the engine's usual way to keep a glow out of the G-buffer leaves a material with no output at all in any
// pass that has no G-buffer, the engine's first frame and its ambient occlusion's own pass among them: an invalid
// pipeline, logged each time. The alpha-0 surface does the same job in every pass.)
//
//   const SE = await import(url_of('sister_eyes_v2.js'));
//   const eyes = SE.attachSisterEyes(root, { sister: 'aletheia', toneMapping: renderer.toneMapping });
//                                                                     // root: an option glb's scene
//   eyes.setState('alarmed');  eyes.setGaze(0.4, -0.2);  eyes.blink();  eyes.set({ spin: -2.0 });
//   eyes.update(t, dt);                                                 // per frame
//
// (v3) THE STYLES a creature chooses from (scripts/eye_display_v3.py STYLES: the same numbers, names and slugs). The
// creator's creature spec carries one name (e.g. eyes: { display: 'halftone_dots' }); styleGlb gives its glb.
export const STYLES = {
    single_arm: { n: 1, slug: '1_single_arm_spiral', title: 'single-arm spiral' },
    double_arm: { n: 2, slug: '2_double_arm_spiral', title: 'double-arm spiral' },
    tick_ring: { n: 3, slug: '3_spiral_in_tick_ring', title: 'spiral in a tick ring' },
    segment_scan: { n: 4, slug: '4_segmented_scan_spiral', title: 'segmented scan spiral' },
    phosphor_trace: { n: 5, slug: '5_phosphor_trace_spiral', title: 'phosphor trace spiral' },
    halftone_dots: { n: 6, slug: '6_halftone_dot_spiral', title: 'halftone dot spiral' },
    counter_rotating: { n: 7, slug: '7_counter_rotating_nested_spirals', title: 'counter-rotating nested spirals' },
    glyph_spiral: { n: 8, slug: '8_glyph_spiral_her_name', title: 'glyph spiral: her name' },
};
// (fix r1, after check_r1) a name that is not a style throws, naming the styles: it used to give style 1's glb silently
export const styleGlb = (name, dir = 'work/bestiary/human/aletheia/eye_displays_v3/glb') => {
    const s = Object.hasOwn(STYLES, name) ? STYLES[name] : null;
    if (!s) throw new Error(`sister eyes: no display style '${name}' (the styles: ${Object.keys(STYLES).join(', ')})`);
    return `${dir}/eye_display_style_${s.slug}.glb`;
};

// Colours (study_refs.md: her RIGHT red / gold, her LEFT blue / purple; L = her left, +X).
export const SISTERS = {
    aletheia: { R: { glow: '#F91A24', day: [1.1407, -0.0925, -0.0307], dayStep: [1.1198, -0.0911, -0.0283] },
        L: { glow: '#00AEFF', day: [-0.0584, 0.2922, 0.8564] } },
    // gain: r2_eyes measured the purple's own level (at the luminance-matching 1.31 the tone curve's shoulder turns it
    // toward magenta; at 0.65 it reads 5 deg off, as the red does)
    aporia: { R: { glow: '#FED516', day: [0.6852, 0.4694, -0.0649] },
        L: { glow: '#8C0AF4', gain: 0.65, day: [0.1538, -0.0869, 0.5667] } },
};
// (v3) v2's OPEN COLOUR POINTS, as two treatments a scene may ask for (opts.treatment); with neither, the colours are
// v2's exactly. Studied in scripts/d10_colour.py on three r184's own curves, then in the engine (NOTES 11-10).
//   day: true      DAYLIGHT READS AS THE STUDIO. AgX mixes every channel into the others before its curve (its inset),
//                  so a bright red gains green and blue: v2's day red body was sRGB 209 84 73, a coral, at every level
//                  (AgX's saturation for a pure red falls with level: 0.87 at 0.2, 0.68 at 0.7). Under AgX only, the
//                  eye's body colour C (linear, its gain in) is swapped for `day`, solved (d10 solve: least squares over
//                  the body and halo, the close camera's footprint) so AgX returns the studio's ACES colours: red body
//                  225 35 46 (studio 250 41 42), halo 170 0 4. Its green and blue may be negative: light the display
//                  takes back out of the inset's crosstalk, on her black glass. The core keeps v2's colour (near-white
//                  either way). Studio and dark (ACES) are untouched by it.
//   redStep: true  THE RED A STEP LOWER: Aletheia's red eye at RED_STEP of its level in every light (v2's d08: red's
//                  own channel sat at 254+ over 1.6 - 4.2 % of the display in studio and dark, its body's band); under
//                  AgX with `day` it uses `dayStep`, solved for the stepped studio look
export const RED_STEP = 0.9;

// THE LINE'S PROFILE over dn (0 on the line .. 1 at the strip's rail): three Gaussians (sigma in dn; amp linear, x the
// eye's colour). hot.lum: the hot core's colour is the eye's colour mixed toward white until its luminance is this (so
// the red's, the blue's, the gold's and the purple's cores are equally bright; a core is never pure white). The halo is
// windowed by (1 - dn^2)^2 so it is exactly zero at the rail. (scripts/d03_preview.py reads this literal: keep it JSON)
// TUNED IN THE ENGINE on her head (look/d04_tune_*.png, cache/d04_tune_*.json: six candidates in the studio, the day
// and the dark, the two eyes / one eye close / her head): a core hot enough to pass the engine's default bloom
// threshold (luminance 0.85) at its very centre and no wider; a body at the level where the tone curve still holds the
// hue (the red's body leaves its hue past ~1.0); a halo wide and strong enough that the line reads as a light with no
// bloom at all (a scene with a high bloom threshold, as my robot body's, shows the drawn glow alone)
export const PROFILE = {
    "hot": { "sigma": 0.055, "amp": 1.8, "lum": 0.50 },
    "body": { "sigma": 0.27, "amp": 0.90 },
    "halo": { "sigma": 0.74, "amp": 0.58 },
    "footprint": 0.55
};

// THE STATES (r2_eyes', unchanged): keys (the marks' morph targets), spin (turns per second, + counter-clockwise seen
// from the front: the way the arm winds out), pulse (hz, depth: the glow's breath), glow (x the profile)
export const EYE_STATES = {
    neutral: { keys: {}, spin: 0.10, pulse: { hz: 0.25, depth: 0.08 }, glow: 1.0 },
    calm: { keys: { calm: 1 }, spin: 0.05, pulse: { hz: 0.18, depth: 0.16 }, glow: 0.85 },
    focused: { keys: { focused: 1 }, spin: 0.55, pulse: { hz: 0.0, depth: 0.0 }, glow: 1.2 },
    alarmed: { keys: { alarmed: 1 }, spin: -1.6, pulse: { hz: 3.0, depth: 0.35 }, glow: 1.3 },
    delighted: { keys: { delighted: 1 }, spin: 0.9, pulse: { hz: 1.6, depth: 0.22 }, glow: 1.15 },
    sad: { keys: { sad: 1 }, spin: 0.03, pulse: { hz: 0.15, depth: 0.10 }, glow: 0.7 },
};
export const VRM_EMOTION = { happy: 'delighted', angry: 'focused', sad: 'sad', relaxed: 'calm', surprised: 'alarmed' };

// eye_display_v2.py's numbers (the glb's root extras carry them too; these are the defaults)
const SCREEN = { rActive: 14.20, rFull: 13.70 };                                     // mm
const SCALE = { widen: 1.12, narrow: 0.80, calm: 0.94, focused: 0.86, alarmed: 1.14, delighted: 1.04, sad: 0.97 };
const LOOK = { lookUp: [0.0, 3.2], lookDown: [0.0, -3.2], lookLeft: [4.0, 0.0], lookRight: [-4.0, 0.0] };   // mm
const LID_KEYS = ['blink', 'calm', 'focused', 'delighted', 'sad'];
const LID_COLS = 25;                                   // a shutter's columns (the lid grid's: its node's extras say)
// THE LEVEL UNDER EACH TONE CURVE (opts.toneMapping: the renderer's): the profile is tuned under ACES. AgX turns a bright
// saturated light pastel (measured on her right eye in the day scene, look/d04_day_levels.png: the red's body at level 1.0
// sRGB 226 117 106, saturation 0.53; at 0.7 208 87 75, 0.64; at 0.5 193 71 62, 0.68, the hue the same): under AgX the
// displays run at 0.7, a truer colour that still reads at a distance in daylight
export const TONE_LEVEL = { AgX: 0.7 };
// option 4's scan: sweeps per second = base + perSpin x |spin| ; a segment flares to `peak` as the pulse passes and
// settles to `rest` (x its level); tail: the share of a sweep the flare takes to die
export const SCAN = { base: 0.45, perSpin: 0.55, rest: 0.50, peak: 1.55, tail: 0.22 };
// (v3) STYLE 5's BEAM, the phosphor trace: sweeps a second = base + perSpin x |spin| (the scan's rule). A point the beam
// passed `age` sweeps ago glows floor + (1 - floor) exp(-age / tau) (the phosphor's afterglow) in its body and halo; its
// hot core x (hotRest x that + hotFresh x exp(-age / freshTau)) (the flash just behind the beam is the hottest); the
// beam's own spot at the head: a round Gaussian `spot` mm in radius, x spotAmp, in the hot core's colour.
// (scripts/d03_preview.py reads these literals: keep them JSON)
export const TRACE = {
    "base": 0.42, "perSpin": 0.45, "floor": 0.30, "tau": 0.50, "freshTau": 0.05, "hotRest": 0.45, "hotFresh": 1.00,
    "spot": 0.55, "spotAmp": 1.30
};
// (tuned 11-10 03:20 on the CPU look, tmp/tune_trace_*.png: a floor of 0.6 read as a spark running on option 1; 0.30
// over tau 0.5 reads as a beam writing, the fresh trace hot and the old one dim; its light's balance as v2's scan's)
// (v3) STYLE 6's DOTS, the halftone: a dot is drawn at size = field^power of its full size and is off below `off` of
// it; its light x size^gainPower (a small dot is also dimmer: the fringe of the arm does not sparkle as bright as its
// crest)
export const HALFTONE = {
    "power": 0.75, "off": 0.12, "gainPower": 0.6
};
// (v3) STYLE 7's second spin node: its turn x the spin (the outer family turns against the inner)
export const SPIN2 = {
    "ratio": -0.65
};
// (fix r1) STYLE 8 AT A DISTANCE. Her name's strokes are 0.25 - 0.84 mm strips: at her head's distance (0.78 m) under
// 2 px, further off (1.9 m) under 1 px, where they drop out of the raster (the footprint widening keeps a line's light
// only inside its own strip): check_r1 measured 3 - 7 % of style 1's light at 1.9 m. So the name's light is ALSO drawn
// prefiltered: a carrier line along the text path, its emission the strokes' own light per unit length (energy-matched:
// scripts/eye_display_v3.py carrier8), a mipmap of the text. q = the strokes' width in pixels where they are drawn (the
// carrier knows it from its own width x rho, its TEXCOORD_1.y): the strokes fade out from q1 to q0 and the carrier
// fades in as they go, so close up her name is the strokes alone and far off the carrier alone, the same light.
// The strokes are drawn as they always were down to 1.5 px (her head at 0.78 m keeps its outer letters, as the owner saw
// them: the lead, 11-10, "keep it as it is"); under 0.75 px (all of them at 1.9 m) the carrier alone.
// (fix r2, after check_r2) THAT RULE TOOK HER INNER LETTERS AT HER HEAD: at the films' head camera (0.78 m) her strokes
// are 0.9 - 2.0 px wide, so the inner 1.5 turns' letters became the carrier line (check_r2 r07: 370 - 434 px over 8
// levels, both sisters, every light). The owner likes the letters. opts.glyphCarrier now chooses (GLYPH_CARRIER):
//   'far' (THE DEFAULT)  the WHOLE name by one number: her WIDEST stroke's width in pixels in the picture (ref_mm: 2 x
//                 0.20 x 2.10 mm, eye_display_v3.py G8 hs x the top cap height, over the display's mm per pixel at the
//                 pixel: lineMaterial). Over far.q1 (1.8 px: her outer capitals 4.4 px tall, about the smallest a
//                 letter can be drawn) every stroke is drawn as it was before fix r1 and the carrier is off; under
//                 far.q0 (0.9 px) the carrier alone; between, the name cross-fades as a whole (no letter goes before
//                 another, the two shares add to 1). At the films' cameras (1280 x 720, 24 deg): her head, 2.02 px:
//                 letters only, the frame is 'off's pixel for pixel; hand-over from 0.87 m to 1.66 m from the head
//                 target; the far camera, 0.77 px: the carrier alone (fix r1's far look within 2 levels).
//                 MEASURED (fix_r2/scripts/s04, the display's own light x style 1's, 15 frames a camera, studio): 0.183
//                 at her head, 0.168 - 0.198 from 0.90 to 1.70 m, 0.175 at 1.90 m; letters alone fall 0.183 -> 0.059.
//                 (A hand-over starting later, at 1.4 px, was tried: letters only out to 1.0 m, but the light dipped to
//                 0.131 at 1.15 m before the carrier caught it, and flickered 3.4 % as the spiral turned.)
//   'per_stroke'  fix r1's rule (q0, q1 above): each stroke hands over as IT goes under 1.5 px. At her head the small
//                 inner letters are already the line: cleaner, 7 % more light there (0.196), fewer letters.
//   'off'         her name's strokes alone at every distance, as before fix r1; no carrier is drawn.
// (scripts/d03_preview.py reads this literal: keep it JSON)
export const GLYPH8 = {
    "q0": 0.75, "q1": 1.5,
    "far": { "ref_mm": 0.84, "q0": 0.9, "q1": 1.8 }
};
export const GLYPH_CARRIER = ['far', 'per_stroke', 'off'];          // (fix r2) opts.glyphCarrier; the first the default

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const smooth = (x) => { const t = clamp01(x); return t * t * (3 - 2 * t); };

// THE GUARD (r2_eyes' guardWeights; its blink rule changed 11-10, fix r1 after check_r1): saturate; the MOODS' lids
// (calm focused delighted sad) held to a sum of 1 among themselves and the scales' sum to 1 (a key in both takes the
// smaller factor). r2_eyes also held the gaze so its sliding disc stayed on the panel: the looks here never move the
// outer turn, so there is nothing to hold.
// THE BLINK IS NOT ONE MORE MOOD. r2_eyes summed it with the moods' lids (v2 kept that; v2's films never blink in a
// mood), so angry + blink gave each 0.5 and left the display 0.235 open, sad + blink 0.386: a blink during a lid mood
// never closed the display, and it shrank the mood's scale on the lit marks as well. Now a blink is in no group here;
// lidShare closes the lids from wherever the mood holds them.
const LID_MOODS = LID_KEYS.filter((k) => k !== 'blink');
export function guardWeights(raw) {
    const w = {};
    for (const k in raw) w[k] = clamp01(+raw[k] || 0);
    const fac = {};
    for (const group of [LID_MOODS, Object.keys(SCALE)]) {
        const tot = group.reduce((a, k) => a + (w[k] || 0), 0), f = tot > 1 ? 1 / tot : 1;
        for (const k of group) fac[k] = Math.min(fac[k] ?? 1, f);
    }
    const out = {};
    for (const k in w) out[k] = w[k] * (fac[k] ?? 1);
    return out;
}
// THE LIDS' WEIGHTS (the shutters and their lit edges, nothing else): each mood's lid pose x (1 - blink), so a blink
// of weight b moves the lids b of the way from the mood's pose to closed: blink 1 closes the display in every mood, and
// the lids' summed weight stays <= 1 (r2_eyes' bar: no pose overshoots). The lit marks keep guardWeights' weights: a
// blink moves no spiral. With no blink, or no mood, these are guardWeights' own (v2's films: see NOTES, fix r1)
export function lidShare(w) {
    const b = w.blink || 0, out = { ...w };
    for (const k of LID_MOODS) if (out[k] !== undefined) out[k] *= 1 - b;
    return out;
}

// (fix r2, after check_r2) THE GAZE OF A LOOK-AT THAT TURNS HER EYE JOINTS AND SETS NO EXPRESSION. A Bestiary face's VRM
// (eidoverse/bestiary/forge/vrm.py) has a look-at of type BONE: its eye joints turn and no look expression is ever set,
// so the display read no gaze at all (check_r2 r04: her eyes 25 deg to her left, the display's gaze 0.000 mm). On such
// a face, while none of the four look expressions has a value (one that has leads, as before), the four looks' weights
// are taken from the look-at's own yaw / pitch (degrees; yaw + toward her left, pitch + DOWN), each as THE SHARE OF ITS
// TRAVEL THE LOOK-AT TURNS HER EYE BY, 0 .. 1, the way a look expression's weight is the share of its range:
//   three-vrm turns an eye by map.outputScale x saturate(angle / map.inputMaxValue), so the share is
//   saturate(angle / map.inputMaxValue) (a map with no input given: three-vrm's 90 deg; a map that turns nothing, 0);
//   WHICH map is the bone applier's own choice (three-vrm-core 3.5.2 VRMLookAtBoneApplier.applyYawPitch, module lines
//   2752 - 2778), mirrored here so the display stops where her eye joints stop:
//     sideways  the eye turning OUTWARD: rangeMapHorizontalOuter, both ways (one gaze for both displays, as the look
//               expressions give; three-vrm's expression applier reads the same map);
//     up        (pitch < 0) rangeMapVerticalDOWN;   down (pitch > 0) rangeMapVerticalUP.
//   The bone applier reads the two vertical maps the other way round from its expression applier (2840 - 2846: lookUp
//   from VerticalUp, lookDown from VerticalDown). On hb1's human (maps: outer 25, inner 25, down 25, up 22, 1:1) her
//   eye joints therefore stop at 25 deg UP and 22 deg DOWN, and the display follows THEM: 20 deg down is 20 / 22 of
//   her eye's travel and of the display's glance (fix_r2/scripts/s01 measures her joints, not the maps: if a later
//   three-vrm reads its maps differently that test fails and names this function).
// A look-at of type expression (my robot face's) writes the look expressions itself: nothing is taken from it here.
// null: nothing to take.
const LOOK_RANGE_DEFAULT = 90;                // deg: three-vrm 3.5.2 VRMLookAtLoaderPlugin's input for a map that has none
function lookAtGaze(face, em, look) {
    const la = face?.lookAt, ap = la?.applier;
    if (!ap || ap.expressions) return null;           // no look-at, or one that sets the look expressions itself
    for (const q in look) if ((em.getValue(q) || 0) > 0) return null;       // a look expression is driven: it leads
    const yaw = +la.yaw || 0, pitch = +la.pitch || 0;
    const share = (map, x) => (x > 0 && map?.outputScale !== 0 ?
        clamp01(x / Math.max(1e-6, map?.inputMaxValue ?? LOOK_RANGE_DEFAULT)) : 0);
    return { lookLeft: share(ap.rangeMapHorizontalOuter, yaw), lookRight: share(ap.rangeMapHorizontalOuter, -yaw),
        lookUp: share(ap.rangeMapVerticalDown, -pitch), lookDown: share(ap.rangeMapVerticalUp, pitch) };
}

// the marks of one eye: every mesh under display_<side> (the lids, their edges, the fixed marks) and under spin_<side>
// (the turning marks); a mark's role, level and half-width are its node's extras
function findEye(root, side) {
    const display = root.getObjectByName(`display_${side}`), spin = root.getObjectByName(`spin_${side}`);
    const spin2 = root.getObjectByName(`spin2_${side}`);                 // (v3: style 7's outer family)
    const marks = [];
    if (display) display.traverse((o) => {
        if (!o.isMesh) return;
        let turning = 0;
        for (let p = o; p && p !== display; p = p.parent) if (p === spin) turning = 1; else if (p === spin2) turning = 2;
        const node = o.userData?.role ? o : o.parent;                    // (a multi-primitive mesh nests under its node)
        const x = node.userData || {};
        const name = (node.name || o.name).replace(new RegExp(`_${side}$`), '');
        marks.push({ mesh: o, name, turning,
            role: x.role || 'line', level: x.level ?? 1.0, lid: x.lid || null, mask: x.mask_mm || null,
            feature: x.feature || null, path: x.path_mm || 0, field: x.field || null, sister: x.sister || null,
            half: x.half_mm || 1.0, rLook: x.r_look_mm || 11.4, pathPts: x.path_pts || null, emitPts: x.emit_pts || null,
            // (fix r1) a shutter or a shutter's lit edge: it takes the lids' weights (lidShare)
            lidMark: (x.role || 'line') === 'lid' || name.startsWith('edge') });
    });
    return { side, display, spin, spin2, marks };
}

// (v3) STYLE 6's FIELD at a point q of the field's own frame (mm): scripts/eye_display_v3.py field6, line for line (v2's
// arm as a Gaussian across it, width sigma x the arm's tip and tail, height its emission; round past both ends; the
// brightest of the three nearest turns). Angles wrap by fract (WGSL's % keeps the dividend's sign)
function halftoneField(q, F) {
    const { float, length, atan, exp, clamp, smoothstep, round, max, fract } = globalThis.THREE;
    const TAU = 2 * Math.PI, T = F.turns, phiMax = TAU * T, kr = (F.r1 - F.r0) / phiMax;
    const sm = (x) => smoothstep(0.0, 1.0, x);
    const r = length(q), th = atan(q.y, q.x);
    const phi0 = fract(th.sub(F.end_deg * Math.PI / 180).add(phiMax).div(TAU)).mul(TAU);
    const n = round(r.sub(F.r0).sub(phi0.mul(kr)).div(TAU * kr));
    let best = float(0.0);
    for (const dk of [-1, 0, 1]) {
        const phi = phi0.add(n.add(dk).mul(TAU));
        const pc = clamp(phi, 0.0, phiMax);
        const t = pc.div(TAU);
        const ra = pc.mul(kr).add(F.r0);
        const tl = sm(t.sub(T - F.tail).div(F.tail));
        const wf = sm(t.div(F.grow)).mul(1 - F.tip).add(F.tip).mul(float(1.0).sub(tl.mul(1 - F.tail_to)));
        const em = sm(t.div(0.6 * F.grow)).mul(0.15).add(0.85).mul(float(1.0).sub(tl.mul(F.tail_dim)));
        const dr = r.sub(ra), da = phi.sub(pc).mul(ra), s = wf.mul(F.sigma);
        best = max(best, exp(dr.mul(dr).add(da.mul(da)).div(s.mul(s).mul(2.0)).negate()).mul(em));
    }
    return best;
}

// A SHUTTER read off its lid mesh: the edge row's heights (mm) per column, at rest and per shape key
function readLid(mk) {
    const g = mk.mesh.geometry, L = mk.lid, pos = g.attributes.position, dict = mk.mesh.morphTargetDictionary || {};
    const at = (attr, i) => attr.getY(i * L.rows + L.edge_row) * 1000.0;
    const base = Float32Array.from({ length: L.cols }, (_, i) => at(pos, i));
    const keys = {};
    for (const k in dict) {
        const d = g.morphAttributes.position[dict[k]];                   // (glTF: relative)
        keys[k] = Float32Array.from({ length: L.cols }, (_, i) => at(d, i) + (g.morphTargetsRelative ? 0 : -base[i]));
    }
    return { base, keys, x0: L.x0, x1: L.x1, cols: L.cols, up: L.side === 'up', now: Float32Array.from(base) };
}

// THE GLOW LINE's material for one eye (see the header). U: the eye's uniforms. turning: the mark rides the spin node
// (its pixels' place on the display is its own turned by the spin); shuttered: the lids switch its pixels off (every
// lit mark but the lids' own edges); mask: the mark's own round mask [full inside, none past] (mm) instead of the
// display's (option 3's lid edges end at its ring)
// (v3) o: { turning: 0 | 1 | 2 (the node the mark rides: none, spin, spin2), shuttered, mask, feature: null | 'trace' |
// 'halftone', path (the trace's length, mm), field (the halftone's FIELD6) }. A mark with no feature on no second node
// builds exactly v2's node graph (every v3 term below is added only when its feature asks for it).
function lineMaterial(eye, colours, U, level, o) {
    const THREE = globalThis.THREE;
    const { turning, shuttered, mask, feature } = o;
    const { uv, attribute, vec2, vec3, vec4, float, exp, length, sqrt, max, clamp, mix, smoothstep, dFdx, dFdy,
        positionLocal, fract, floor, pow, abs } = THREE;
    const C = vec3(U.C.r, U.C.g, U.C.b), Chot = vec3(U.Chot.r, U.Chot.g, U.Chot.b);
    const ab = uv(), a = ab.x, b = ab.y;
    const u1 = uv(1);                       // (v3) TEXCOORD_1: a line's local half-width (mm, x) | a dot's centre (mm)
    // (v3) THE HALFTONE: the dot's centre taken back through the state (the gaze's look field by two fixed-point steps,
    // the scale keys' weight, the spin: scripts/d03_preview.py pattern_point), the field there, the dot at its size
    let size = null, dotGain = null;
    if (feature === 'halftone') {
        const F = o.field, cs = U.spinCS;
        let Y = u1.div(U.sEff);
        for (let k = 0; k < 2; k++)
            Y = u1.sub(U.gaze.mul(clamp(float(1.0).sub(length(Y).div(F.r_look_mm)), 0.0, 1.0))).div(U.sEff);
        const q = vec2(cs.x.mul(Y.x).add(cs.y.mul(Y.y)), cs.x.mul(Y.y).sub(cs.y.mul(Y.x)));
        const s = pow(halftoneField(q, F), HALFTONE.power);
        size = max(s, 1e-3);
        dotGain = pow(size, HALFTONE.gainPower).mul(smoothstep(HALFTONE.off * 0.85, HALFTONE.off, s));
    }
    const dn = size ? length(vec2(a, b)).div(size) : length(vec2(a, b));
    // the pixel's footprint in dn (the cross coordinate's change per pixel): each Gaussian is widened by it and keeps
    // its integral
    const w0 = max(length(vec2(dFdx(a), dFdy(a))), length(vec2(dFdx(b), dFdy(b)))).mul(U.footprint);
    const w = size ? w0.div(size) : w0;
    const g = (sigma) => {
        const se = sqrt(sigma.mul(sigma).add(w.mul(w)));
        const x = dn.div(se);
        return exp(x.mul(x).negate()).mul(sigma.div(se));
    };
    const win = clamp(float(1.0).sub(dn.mul(dn)), 0.0, 1.0);
    const col = attribute('color', 'vec4');                              // (emission factor, phase, -, -)
    // the scan: x = how far behind the pulse this vertex's phase is (0 .. 1 of a sweep); the flare dies over `tail`
    const x = fract(U.scan.sub(col.y));
    const scan = mix(float(1.0), U.scanRest.add(U.scanPeak.sub(U.scanRest).mul(exp(x.div(U.scanTail).negate()))), U.scanOn);
    // the pixel's place on the display (mm; x her left, y up)
    // (fix r2) THE BEAM'S SPOT is the one mark the runtime carries by its MESH's position (update: spotAt, mm, in the
    // spin node's frame), which positionLocal does not hold: its pixels' place is their own + that. Without it the spot
    // was masked and shuttered as if it sat at the screen's centre: it showed on the closed part of the screen whenever
    // the beam's head passed behind a lid (focused), vanished where the centre was behind one (delighted), and a sliver
    // of it stayed through a blink (found in style 5's own films: fix_r2_NOTES).
    const pm = feature === 'spot' ? positionLocal.xy.mul(1000.0).add(U.spotAt) : positionLocal.xy.mul(1000.0);
    const CSn = turning === 2 ? U.spin2CS : U.spinCS;
    const pd = turning ? vec2(pm.x.mul(CSn.x).sub(pm.y.mul(CSn.y)), pm.x.mul(CSn.y).add(pm.y.mul(CSn.x))) : pm;
    // (v3) a halftone dot is gated at its centre: an LED is on or off, never cut in two (a quarter-pitch soft edge)
    const gp = feature === 'halftone' ? u1 : pd;
    // the display's round mask
    let gate = float(1.0).sub(mask ? smoothstep(mask[0], mask[1], length(gp)) : smoothstep(U.rFull, U.rActive, length(gp)));
    if (shuttered) {
        // the shutters: the lids' edge heights at this pixel's column (x: up, y: down), the cut one pixel soft
        const u = clamp(gp.x.sub(U.lidX0).div(U.lidX1.sub(U.lidX0)), 0.0, 1.0).mul(LID_COLS - 1);
        const i = clamp(floor(u), 0.0, LID_COLS - 2);
        const e0 = U.lids.element(i.toInt()), e1 = U.lids.element(i.toInt().add(1));
        const edge = mix(e0, e1, u.sub(i));
        const px = feature === 'halftone' ? float(0.2) : max(length(vec2(dFdx(pd.y), dFdy(pd.y))), 1e-4);
        gate = gate.mul(smoothstep(px.negate(), px, edge.x.sub(gp.y))).mul(smoothstep(px.negate(), px, gp.y.sub(edge.y)));
    }
    let bodyHalo = g(U.bodySigma).mul(U.bodyAmp).add(g(U.haloSigma).mul(win).mul(win).mul(U.haloAmp));
    let hot = g(U.hotSigma).mul(U.hotAmp);
    if (feature === 'trace') {
        // (v3) THE BEAM: age = how long ago (sweeps) the beam passed this point; the phosphor's afterglow on the body
        // and halo, the flash just behind the beam on the hot core
        const age = fract(U.beam.sub(col.y));
        const persist = float(1.0).sub(U.trFloor).mul(exp(age.div(U.trTau).negate())).add(U.trFloor);
        const fresh = exp(age.div(U.trFresh).negate());
        bodyHalo = bodyHalo.mul(persist);
        hot = hot.mul(U.trHotRest.mul(persist).add(U.trHotFresh.mul(fresh)));
    }
    if (feature === 'spot') {
        // (v3) THE BEAM'S SPOT, its own round dot (the runtime carries it to the head): a hot round Gaussian TRACE.spot
        // mm in radius over the dot's own glow, widened by the pixel's footprint and keeping its integral (2D)
        const sg = U.trSpot.div(o.half), se2 = sg.mul(sg).add(w.mul(w));
        hot = hot.add(exp(dn.mul(dn).div(se2).negate()).mul(sg.mul(sg).div(se2)).mul(U.trSpotAmp));
        bodyHalo = bodyHalo.mul(U.spotEmit);
        hot = hot.mul(U.spotEmit);
    }
    // (fix r1) STYLE 8's strokes and their carrier (see GLYPH8): q = the strokes' width in pixels here (a strip's cross
    // coordinate a runs -1 .. 1 across it, so 2 / |grad| is its width; the carrier's own width x rho, TEXCOORD_1.y)
    // (fix r2) o.glyphCarrier (GLYPH8): 'per_stroke' is fix r1's rule above, node for node; 'far' (the default) keys the
    // WHOLE name to one number, the display's scale in the picture here: mm of the display per pixel = sqrt |det| of the
    // mark's own place (pm, mm) over the pixel grid. It is the same at one pixel for every stroke, whichever way the
    // stroke runs, and for the carrier under it (a strip's own cross coordinate is not: on a screen seen at an angle it
    // changes with the strip's direction), so the strokes' share and the carrier's add to 1 at every pixel. 'off': no
    // fade, and the carrier is not drawn (attachSisterEyes).
    let lod = null;
    if ((feature === 'glyphs' || feature === 'carrier') && o.glyphCarrier !== 'off') {
        let f;
        if (o.glyphCarrier === 'per_stroke') {
            const g1 = max(length(vec2(dFdx(a), dFdy(a))), length(vec2(dFdx(b), dFdy(b))));
            const wpx = float(2.0).div(max(g1, 1e-6));
            f = smoothstep(GLYPH8.q0, GLYPH8.q1, feature === 'carrier' ? wpx.mul(u1.y) : wpx);
        } else {
            const G = { ...GLYPH8.far, ...(o.glyphFar || {}) };
            const jx = dFdx(pm), jy = dFdy(pm);
            const mmPerPx = sqrt(abs(jx.x.mul(jy.y).sub(jx.y.mul(jy.x))));
            f = smoothstep(G.q0, G.q1, float(G.ref_mm).div(max(mmPerPx, 1e-6)));
        }
        lod = feature === 'carrier' ? float(1.0).sub(f) : f;
    }
    let light = C.mul(bodyHalo).add(Chot.mul(hot));
    if (dotGain) light = light.mul(dotGain);
    if (lod) light = light.mul(lod);
    const m = new THREE.MeshBasicNodeMaterial();
    // THE LIGHT IS THE OUTPUT, THE SURFACE IS NOTHING: the output carries the light at alpha 1 (additive: it adds), the
    // material's own alpha is 0. The engine's G-buffer attachments (normal, metal / rough) take a material's alpha and
    // its blending, so a glow adds nothing to them (ambient occlusion and reflections see her glass, not the strips)
    m.outputNode = vec4(light.mul(col.x).mul(level).mul(scan).mul(gate).mul(U.glow).mul(U.pulse).mul(U.level), 1.0);
    m.opacityNode = float(0.0);
    m.transparent = true;
    m.blending = THREE.AdditiveBlending;
    m.depthWrite = false;
    m.fog = false;
    // the marks lie 0.2 - 0.4 mm over her glass: at a distance that is under the depth buffer's step, so they are also
    // held in front of it in depth units
    m.polygonOffset = true;
    m.polygonOffsetFactor = -1;
    m.polygonOffsetUnits = -4;
    m.name = `sister_eye_line_${eye.side}`;
    return m;
}

export function attachSisterEyes(root, opts = {}) {
    const THREE = globalThis.THREE;
    const sister = SISTERS[opts.sister || 'aletheia'];
    const P = { ...PROFILE, ...(opts.profile || {}) };
    const meta = root.getObjectByName('sister_eyes_v3')?.userData || root.getObjectByName('sister_eyes_v2')?.userData ||
        root.userData || {};
    const level = (opts.level ?? 1.0) * (opts.toneMapping === THREE.AgXToneMapping ? TONE_LEVEL.AgX : 1.0);
    const scanOn = opts.scan ?? !!meta.scan;
    const look = meta.look_mm || LOOK;
    // (fix r2) style 8's carrier rule (GLYPH8): a name that is not one throws, naming them (as styleGlb does)
    const glyphCarrier = opts.glyphCarrier ?? GLYPH_CARRIER[0];
    if (!GLYPH_CARRIER.includes(glyphCarrier))
        throw new Error(`sister eyes: no glyphCarrier '${glyphCarrier}' (the choices: ${GLYPH_CARRIER.join(', ')})`);
    const eyes = ['L', 'R'].map((s) => findEye(root, s));
    for (const e of eyes) {
        const c = new THREE.Color(sister[e.side].glow);                  // (linear: Color.set converts)
        const lum = 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
        // ONE BRIGHTNESS FOR EVERY HUE (r2_eyes' rule, measured there): the eye's colour x (0.21 / its luminance) ^ 0.5
        // (0.21 the red's), held to 0.5 .. 1.5; a colour's own measured `gain` wins (the purple)
        const gain = sister[e.side].gain ?? Math.min(1.5, Math.max(0.5, Math.sqrt(0.21 / Math.max(lum, 1e-3))));
        let C = { r: c.r * gain, g: c.g * gain, b: c.b * gain };
        // the hot core's colour: toward white until its luminance is PROFILE.hot.lum
        const k = clamp01((P.hot.lum - lum * gain) / Math.max(1e-3, 1 - lum * gain));
        let Chot = { r: C.r * (1 - k) + k, g: C.g * (1 - k) + k, b: C.b * (1 - k) + k };
        // (v3) the treatments (see SISTERS)
        const tr = opts.treatment || {};
        const red = sister[e.side].dayStep !== undefined;                // Aletheia's red eye
        const step = tr.redStep && red ? RED_STEP : 1.0;
        if (tr.day && opts.toneMapping === THREE.AgXToneMapping && sister[e.side].day) {
            const dv = step !== 1.0 ? sister[e.side].dayStep : sister[e.side].day;
            C = { r: dv[0], g: dv[1], b: dv[2] };
        }
        C = { r: C.r * step, g: C.g * step, b: C.b * step };
        Chot = { r: Chot.r * step, g: Chot.g * step, b: Chot.b * step };
        const U = e.U = {
            C, Chot, glow: THREE.uniform(1.0), pulse: THREE.uniform(1.0), level: THREE.uniform(level),
            scan: THREE.uniform(0.0), scanOn: THREE.uniform(scanOn ? 1.0 : 0.0), scanRest: THREE.uniform(SCAN.rest),
            scanPeak: THREE.uniform(SCAN.peak), scanTail: THREE.uniform(SCAN.tail),
            hotSigma: THREE.uniform(P.hot.sigma), hotAmp: THREE.uniform(P.hot.amp),
            bodySigma: THREE.uniform(P.body.sigma), bodyAmp: THREE.uniform(P.body.amp),
            haloSigma: THREE.uniform(P.halo.sigma), haloAmp: THREE.uniform(P.halo.amp),
            footprint: THREE.uniform(P.footprint), rFull: THREE.uniform(meta.screen?.r_full_mm ?? SCREEN.rFull),
            rActive: THREE.uniform(meta.screen?.r_active_mm ?? SCREEN.rActive),
            spinCS: THREE.uniform(new THREE.Vector2(1, 0)),
            lids: THREE.uniformArray(Array.from({ length: LID_COLS }, () => new THREE.Vector2(99, -99)), 'vec2'),
            lidX0: THREE.uniform(-15.4), lidX1: THREE.uniform(15.4),
            // (v3) the second spin node; the beam and its phosphor; the halftone's state (the scale keys' summed
            // weight as one scale, the gaze's offset on the screen in mm)
            spin2CS: THREE.uniform(new THREE.Vector2(1, 0)), beam: THREE.uniform(0.0),
            trFloor: THREE.uniform(TRACE.floor), trTau: THREE.uniform(TRACE.tau), trFresh: THREE.uniform(TRACE.freshTau),
            trHotRest: THREE.uniform(TRACE.hotRest), trHotFresh: THREE.uniform(TRACE.hotFresh),
            trSpot: THREE.uniform(TRACE.spot), trSpotAmp: THREE.uniform(TRACE.spotAmp),
            sEff: THREE.uniform(1.0), gaze: THREE.uniform(new THREE.Vector2(0, 0)), spotEmit: THREE.uniform(1.0),
            spotAt: THREE.uniform(new THREE.Vector2(0, 0)),      // (fix r2) where the beam's spot is carried to (mm)
        };
        e.lids = {};
        const mats = new Map();
        for (const mk of e.marks) {
            mk.mesh.frustumCulled = false;
            mk.mesh.castShadow = mk.mesh.receiveShadow = false;
            if (mk.role === 'lid') {
                const L = readLid(mk);
                e.lids[L.up ? 'up' : 'dn'] = { ...L, mesh: mk.mesh };
                U.lidX0.value = L.x0; U.lidX1.value = L.x1;
                mk.mesh.visible = false;                                 // a shutter is never drawn
                continue;
            }
            if (mk.sister && mk.sister !== (opts.sister || 'aletheia')) {   // (v3) the other sister's own mark
                mk.mesh.visible = false;
                continue;
            }
            if (mk.feature === 'carrier' && glyphCarrier === 'off') {       // (fix r2) the strokes alone
                mk.mesh.visible = false;
                continue;
            }
            const edge = mk.name.startsWith('edge');
            const key = `${mk.level}|${mk.turning}|${edge}|${mk.mask}|${mk.feature}|${mk.path}|${mk.half}`;
            if (!mats.has(key)) mats.set(key, lineMaterial(e, sister[e.side], U, mk.level, { turning: mk.turning,
                shuttered: !edge, mask: mk.mask, feature: mk.feature, path: mk.path, field: mk.field, half: mk.half,
                glyphCarrier, glyphFar: opts.glyphFar }));
            mk.mesh.material = mats.get(key);
            mk.mesh.renderOrder = 2;
            // (the engine's ambient occlusion draws `transparent` things once more to keep occlusion off them: these
            // are light on her glass, not a surface, so they stay out of that pass)
            mk.mesh.userData.treatAsOpaque = true;
        }
    }
    const N0 = EYE_STATES.neutral;
    const st = {
        state: 'neutral', target: {}, cur: { spin: N0.spin, glow: 1, hz: N0.pulse.hz, depth: N0.pulse.depth },
        keyCur: {}, gaze: [0, 0], gazeCur: [0, 0], angle: { L: 0, R: 0 }, phase: 0, scan: 0,
        blink: { next: opts.autoBlink === false ? Infinity : 1.5, queue: [] }, rng: (opts.seed ?? 7) >>> 0,
        overrides: {}, angle2: { L: 0, R: 0 }, beam: opts.beam0 ?? 0.0,              // (v3) the second node; the beam
    };
    const rand = () => { st.rng = (st.rng * 1664525 + 1013904223) >>> 0; return st.rng / 4294967296; };
    const api = {
        eyes, state: st, meta,
        setState(name, weight = 1) {                 // a state's keys, spin, pulse and glow become the targets
            const S = EYE_STATES[name] || EYE_STATES.neutral;
            st.state = name;
            st.target = { keys: Object.fromEntries(Object.entries(S.keys).map(([k, v]) => [k, v * weight])),
                spin: S.spin, hz: S.pulse.hz, depth: S.pulse.depth, glow: S.glow };
        },
        setGaze(x, y) { st.gaze = [Math.max(-1, Math.min(1, x)), Math.max(-1, Math.min(1, y))]; },  // + her left, + up
        blink(at = null) { st.blink.queue.push(at ?? st.time ?? 0); },     // now, or at a time (several may queue)
        set(o) { Object.assign(st.overrides, o); },  // { spin, glow, hz, depth, keys: {...} } held over the state's
        clear() { st.overrides = {}; },
        // (v3) the face whose expressions drive the displays; (fix r1) link: bindToFace's probe and map (null: none)
        setFace(vrm, link = null) { st.face = vrm; st.link = link; },
        update(t, dt) {
            st.time = t;
            const tg = { ...st.target, ...st.overrides };
            const k = (tau) => 1 - Math.exp(-Math.max(0, dt) / tau);
            // the driven parameters, eased
            for (const [p, tau] of [['spin', 0.35], ['glow', 0.25], ['hz', 0.3], ['depth', 0.3]])
                st.cur[p] += ((tg[p] ?? st.cur[p]) - st.cur[p]) * k(tau);
            // on a VRM the emotions' weights blend the states' parameters over neutral
            // ((v3) the face set by bindToFace / setFace, or opts.vrm as v2 had it; and the pulse blends too)
            const face = st.face || opts.vrm, em = face?.expressionManager;
            // (fix r1) a face bound by bindToFace is read through its probe: each expression's weight AS THREE-VRM
            // APPLIED IT to her own morphs this frame (a blink her face blocks is 0 here too)
            const link = st.link;
            let PR = link?.probe.morphTargetInfluences;
            // (fix r2) ON A BOUND FACE whose look-at turns her eye joints and sets no look expression (a bone look-at,
            // the Bestiary's): its gaze as the four looks' weights (lookAtGaze), read in the probe's place, so
            // everything that reads a look follows it: the gaze offset below (the turning marks, the halftone's field,
            // the beam's spot) and every fixed mark carrying a look key (style 7's ring). The face's own probe is not
            // written. (opts.vrm without bindToFace is v2's way, the caller's own binds: it reads the look expressions
            // as it always did.)
            const gz = link ? lookAtGaze(face, em, look) : null;
            if (gz) {
                const buf = link.looks || (link.looks = new Array(PR.length));
                for (let i = 0; i < PR.length; i++) buf[i] = PR[i];
                for (const q in gz) if (link.slot[q] !== undefined) buf[link.slot[q]] = gz[q];
                PR = buf;
            }
            const val = link ? (nm) => (link.slot[nm] === undefined ? 0 : PR[link.slot[nm]] || 0) :
                (nm) => (em ? em.getValue(nm) || 0 : 0);
            if (em) {
                let sum = 0;
                const acc = { spin: 0, glow: 0, hz: 0, depth: 0 };
                for (const [vrm, s] of Object.entries(VRM_EMOTION)) {
                    const w = Math.max(val(vrm), val(s));                         // the preset or the custom
                    if (!w) continue;
                    sum += w;
                    acc.spin += w * EYE_STATES[s].spin; acc.glow += w * EYE_STATES[s].glow;
                    acc.hz += w * EYE_STATES[s].pulse.hz; acc.depth += w * EYE_STATES[s].pulse.depth;
                }
                if (sum > 0) {
                    const f = Math.min(1, sum);
                    st.cur.spin = (1 - f) * N0.spin + acc.spin / sum * f;
                    st.cur.glow = (1 - f) * N0.glow + acc.glow / sum * f;
                    st.cur.hz = (1 - f) * N0.pulse.hz + acc.hz / sum * f;
                    st.cur.depth = (1 - f) * N0.pulse.depth + acc.depth / sum * f;
                }
            }
            // the pulse: the phase integrates the rate (a rate change never jumps the wave); the scan likewise
            st.phase += 2 * Math.PI * st.cur.hz * dt;
            st.scan += (SCAN.base + SCAN.perSpin * Math.abs(st.cur.spin)) * dt;
            st.beam += (TRACE.base + TRACE.perSpin * Math.abs(st.cur.spin)) * dt;          // (v3) style 5's beam
            const pulse = 1 - st.cur.depth + st.cur.depth * (0.5 + 0.5 * Math.sin(st.phase));
            // the blink: scheduled every 2.5 .. 6 s (opts.autoBlink false: only when asked), 0.10 s closing (eased in),
            // 0.05 s held, 0.16 s opening
            if (t >= st.blink.next) { st.blink.queue.push(t); st.blink.next = t + 2.5 + 3.5 * rand(); }
            let wb = 0;
            st.blink.queue = st.blink.queue.filter((t0) => t - t0 < 0.31);
            for (const t0 of st.blink.queue) {
                const u = t - t0;
                wb = Math.max(wb, u < 0 ? 0 : u < 0.10 ? smooth(u / 0.10) : u < 0.15 ? 1 :
                    1 - smooth((u - 0.15) / 0.16));
            }
            // the keys: the state's (eased), the gaze's looks (eased), the blink, through the guard
            const want = { ...(tg.keys || {}) };
            for (const kk of new Set([...Object.keys(want), ...Object.keys(st.keyCur)])) {
                const c = st.keyCur[kk] || 0;
                st.keyCur[kk] = c + ((want[kk] || 0) - c) * k(0.15);
            }
            for (let i = 0; i < 2; i++) st.gazeCur[i] += (st.gaze[i] - st.gazeCur[i]) * k(0.08);
            const raw = { ...st.keyCur, blink: Math.max(wb, st.keyCur.blink || 0),
                lookLeft: Math.max(0, st.gazeCur[0]), lookRight: Math.max(0, -st.gazeCur[0]),
                lookUp: Math.max(0, st.gazeCur[1]), lookDown: Math.max(0, -st.gazeCur[1]) };
            const w = guardWeights(raw), wl = lidShare(w);       // (fix r1) the lit marks' and the lids' weights
            // (fix r1) ON A FACE BOUND BY bindToFace: each eye's display keys from what three-vrm applied, the glb's
            // binds summed per key, through the same guard and the same blink share (faceKeys)
            const fw = link ? faceKeys(link, eyes, PR) : null;
            // the gaze's offset on the screen (mm)
            const lw = link ? Object.fromEntries(Object.keys(look).map((q) => [q, clamp01(val(q))])) :
                em ? Object.fromEntries(Object.keys(look).map((q) => [q, em.getValue(q) || 0])) : w;
            let dx = 0, dy = 0;
            for (const q in look) { dx += (lw[q] || 0) * look[q][0]; dy += (lw[q] || 0) * look[q][1]; }
            const ux = Math.abs(look.lookLeft[0]), uy = Math.abs(look.lookUp[1]);
            // (v3) the halftone's state as one scale: the scale keys' weights x each key's scale (on a bound face: the
            // eye's own guarded weights, the ones its lit marks take; on opts.vrm, v2's way: its expressions' values,
            // the emotion presets read as their keys, through the guard)
            const ws = em && !link ? guardWeights(Object.fromEntries(Object.keys(SCALE).map((q) => [q, Math.max(em.getValue(q) || 0,
                ...Object.entries(VRM_EMOTION).filter(([, s]) => s === q).map(([v]) => em.getValue(v) || 0))]))) : w;
            const sEffOf = (side) => {
                const W_ = fw ? fw[side].lit : ws;
                let s_ = 1;
                for (const q in SCALE) s_ += (W_[q] || 0) * (SCALE[q] - 1);
                return s_;
            };
            for (const e of eyes) {
                const sEff = sEffOf(e.side);
                e.U.glow.value = st.cur.glow;
                e.U.pulse.value = pulse;
                e.U.scan.value = st.scan;
                e.U.beam.value = st.beam;
                e.U.sEff.value = sEff;
                e.U.gaze.value.set(dx, dy);
                // the spin node's turn about the screen's axis (z), integrated
                st.angle[e.side] += 2 * Math.PI * st.cur.spin * dt;
                const a = st.angle[e.side], c = Math.cos(a), s = Math.sin(a);
                if (e.spin) e.spin.rotation.z = a;
                e.U.spinCS.value.set(c, s);
                // (v3) the second node turns against the first
                st.angle2[e.side] += 2 * Math.PI * st.cur.spin * SPIN2.ratio * dt;
                const a2 = st.angle2[e.side], c2 = Math.cos(a2), s2 = Math.sin(a2);
                if (e.spin2) e.spin2.rotation.z = a2;
                e.U.spin2CS.value.set(c2, s2);
                for (const mk of e.marks) {
                    if (mk.feature === 'spot' && mk.pathPts) {
                        // (v3) THE BEAM'S SPOT carried to the head: the path at the beam's phase, the state's scale and
                        // the gaze (turned back by the spin) applied as the keys apply them to the line
                        const pp = mk.pathPts, u = (st.beam - Math.floor(st.beam)) * (pp.length - 1);
                        const i0 = Math.min(Math.floor(u), pp.length - 2), f = u - i0;
                        const px = pp[i0][0] + f * (pp[i0 + 1][0] - pp[i0][0]), py = pp[i0][1] + f * (pp[i0 + 1][1] - pp[i0][1]);
                        const lf = clamp01(1 - Math.hypot(px, py) / mk.rLook);
                        const gx = c * dx + s * dy, gy = -s * dx + c * dy;
                        mk.mesh.position.set((sEff * px + lf * gx) * 1e-3, (sEff * py + lf * gy) * 1e-3, 0);
                        e.U.spotAt.value.set(sEff * px + lf * gx, sEff * py + lf * gy);     // (fix r2) lineMaterial's pm
                        const ep = mk.emitPts;
                        e.U.spotEmit.value = ep ? ep[Math.round((u / (pp.length - 1)) * (ep.length - 1))] : 1;
                    }
                    const dict = mk.mesh.morphTargetDictionary, inf = mk.mesh.morphTargetInfluences;
                    if (!dict || !inf) continue;
                    if (fw) {
                        // (fix r1) the display's own marks, from the face (each mark's own drivers x the eye's guard)
                        const F = fw[e.side], gw = mk.lidMark ? F.lid : F.lit, d = link.drive.get(mk);
                        for (const kk in dict) {
                            const r = F.raw[kk] || 0;
                            inf[dict[kk]] = r > 0 ? markSum(d, kk, PR) * (gw[kk] || 0) / r : 0;
                        }
                    } else if (!em) for (const kk in dict) inf[dict[kk]] = (mk.lidMark ? wl : w)[kk] || 0;
                    if (!mk.turning || dict.lookLeft === undefined) continue;
                    // A TURNING MARK'S LOOKS IN ITS TURNED FRAME (r2_eyes'): the gaze's screen offset turned back by
                    // the spin, expressed in its four look keys (a weight may pass 1: morphs are linear)
                    const [cn, sn] = mk.turning === 2 ? [c2, s2] : [c, s];
                    const lx = cn * dx + sn * dy, ly = -sn * dx + cn * dy;
                    inf[dict.lookLeft] = Math.max(0, lx) / ux;
                    inf[dict.lookRight] = Math.max(0, -lx) / ux;
                    inf[dict.lookUp] = Math.max(0, ly) / uy;
                    inf[dict.lookDown] = Math.max(0, -ly) / uy;
                }
                // THE SHUTTERS: each lid's edge at the weights its mesh holds, to the lit marks
                let open = 0;
                const arr = e.U.lids.array;
                for (let i = 0; i < LID_COLS; i++) {
                    for (const [which, L] of Object.entries(e.lids)) {
                        const dict = L.mesh.morphTargetDictionary, inf = L.mesh.morphTargetInfluences;
                        let y = L.base[i];
                        for (const kk in L.keys) y += (inf[dict[kk]] || 0) * L.keys[kk][i];
                        L.now[i] = y;
                        if (which === 'up') arr[i].x = y; else arr[i].y = y;
                    }
                    open += clamp01((Math.min(arr[i].x, 14.2) - Math.max(arr[i].y, -14.2)) / 28.4);
                }
                e.open = open / LID_COLS;                                // the share of the screen the lids leave lit
            }
            return fw || w;
        },
    };
    api.setState('neutral');
    return api;
}

// (v3) THE DISPLAYS DRIVEN BY A FACE'S EXPRESSIONS. (fix r1, after check_r1: rewritten.) The first pass copied my robot
// face's way (the robot body's build, read only: its rig export binds every VRM expression to the face marks'
// morph targets and sets happy / relaxed to block blink; robot_face.js installMouthGuard rescales expression weights
// around expressionManager.update): its guard scaled the FACE'S OWN weights during the update, so every bind of those
// expressions moved with them (her own blink 0.5 when angry; her smile 0.8 -> 0.444 during a blocked blink), and it
// ran before three-vrm's own blink block (a blink happy blocks still shrank delighted and opened the display). The robot
// face can do that because its mouth expressions drive nothing but its own marks; a human face binds blink and the
// moods to her own lids, brows and smile. So the display now ONLY LISTENS:
//   const VRM = await import('npm:@pixiv/three-vrm@3.5.2');
//   const link = SE.bindToFace(vrm, eyes, { VRM });   ONCE (vrm: a loaded VRM, or anything with an expressionManager)
//   per frame: drive the face (em.setValue, the look-at), vrm.update(dt), THEN eyes.update(t, dt)
//   link.unbind()                                      the face exactly as it was before; the display runs on its own
// (1) THE PROBE: one morph slot per expression the display listens to, bound at weight 1 to that expression, on a mesh
//     in no scene. three-vrm's update writes each slot with the weight it applied to the face's own morphs (its blink /
//     look-at / mouth overrides and isBinary included): the display reads THAT, so a blink the face blocks is 0 here as
//     on her own lids, and nothing of three-vrm's logic is repeated here.
// (2) THE DISPLAY'S OWN MAP: the binds the style's glb carries (root extras `binds`: eye_display_v3.py expression_binds:
//     the five emotion presets, blink, blinkLeft / blinkRight, the four looks, the custom calm focused alarmed delighted
//     widen narrow -> [(mark node, key, weight)]); eyes.update sums each key's drivers per eye, holds them with the
//     guard and the lids' blink share (guardWeights, lidShare: setState's own rule) and writes the DISPLAY'S marks;
//     the moods' spin, pulse and glow, the gaze, the halftone's scale and the beam's spot from the same weights.
// (3) What the face gets: the probe's binds, and an expression of each bound name it lacks (registered, so a caller
//     drives the customs as any expression). Its own weights, binds and overrides are never touched: whether happy
//     blocks blink is the face's own setting (my robot face's VRM blocks it; the Bestiary's VRM writer, forge/vrm.py,
//     writes 'none'). The display follows the blink three-vrm APPLIED. (fix r2, after check_r2) On a face whose lids
//     are its expressions' binds (my robot face) that is the face's own blink, blocked or not; on a Bestiary face the
//     lids are moved from each expression's VALUE (bestiary/runtime/human_face_eval.js line 53, em.getValue, which no
//     override changes), so a block there shuts her lids and holds the display open: leave the Bestiary's 'none' (the
//     blink's value is then what three-vrm applies: her lids and the display close together, in a mood or out of one).
// (4) One display per face: binding another (a style switch) unbinds the one before; unbind parks its marks at 0.
// (5) (fix r2) The gaze: the face's look expressions as three-vrm applied them; when its look-at sets none (a bone
//     look-at: the Bestiary's), the look-at's own yaw / pitch through its range maps (lookAtGaze).
// Returns { binds, customs, expressions, unbind } (counts and names, for the log).
const BOUND = new WeakMap();                          // a face's expression manager -> the display bound to it
function markSum(d, key, P) {                         // a display key's weight on one mark: its drivers x their weights
    let v = 0;
    if (d && d[key]) for (const [s, wt] of d[key]) v += (P[s] || 0) * wt;
    return v;
}
// an expression's display key and its eye (null: both): a preset its state's key (VRM_EMOTION), blink / blinkLeft /
// blinkRight the lids' 'blink', any other name (the customs, the looks) its own
const keyOfExpr = (nm) => VRM_EMOTION[nm] || (nm.startsWith('blink') ? 'blink' : nm);
const eyeOfExpr = (nm) => (nm === 'blinkLeft' ? 'L' : nm === 'blinkRight' ? 'R' : null);
// per eye: each display key's raw weight (the applied weights of the expressions that drive it on that eye, summed:
// blink + blinkLeft on her left lids; a key no mark of the style carries counts too: the halftone's scale), the lit
// marks' weights (the guard) and the lids' (the blink share). (fix r2) P: the probe's weights, the looks from a bone
// look-at in their slots (update)
function faceKeys(link, eyes, P = link.probe.morphTargetInfluences) {
    const out = {};
    for (const e of eyes) {
        const raw = {};
        for (const nm in link.slot) {
            const side = eyeOfExpr(nm);
            if (side && side !== e.side) continue;
            const k = keyOfExpr(nm);
            raw[k] = (raw[k] || 0) + (P[link.slot[nm]] || 0);
        }
        const lit = guardWeights(raw);
        out[e.side] = { raw, lit, lid: lidShare(lit) };
    }
    return out;
}
export function bindToFace(vrm, eyes, { VRM }) {
    const THREE = globalThis.THREE;
    const em = vrm.expressionManager;
    BOUND.get(em)?.unbind();                          // one display per face
    const binds = eyes.meta.binds || {};
    const customs = [];
    for (const name of Object.keys(binds)) {
        if (em.getExpression(name)) continue;
        em.registerExpression(new VRM.VRMExpression(name));
        customs.push(name);
    }
    const names = Object.keys(binds);
    const probe = new THREE.Mesh();
    probe.name = 'sister_eyes_face_probe';
    probe.morphTargetInfluences = names.map(() => 0);
    const slot = Object.fromEntries(names.map((nm, i) => [nm, i]));
    const probeBinds = names.map((nm, i) => {
        const b = new VRM.VRMExpressionMorphTargetBind({ primitives: [probe], index: i, weight: 1 });
        em.getExpression(nm).addBind(b);
        return [nm, b];
    });
    const marks = new Map();
    for (const e of eyes.eyes) for (const mk of e.marks) marks.set(`${mk.name}_${e.side}`, mk);
    const drive = new Map();                          // mark -> { key: [[probe slot, weight], ...] }
    let n = 0;
    for (const [name, list] of Object.entries(binds)) {
        for (const [node, key, weight] of list) {
            const mk = marks.get(node);
            if (mk?.mesh.morphTargetDictionary?.[key] === undefined) continue;
            const d = drive.get(mk) || {};
            (d[key] = d[key] || []).push([slot[name], weight]);
            drive.set(mk, d);
            n++;
        }
    }
    const handle = {
        binds: n, customs, expressions: names.length,
        unbind() {
            for (const [nm, b] of probeBinds) em.getExpression(nm)?.deleteBind(b);
            for (const nm of customs) { const ex = em.getExpression(nm); if (ex) em.unregisterExpression(ex); }
            if (BOUND.get(em) === handle) BOUND.delete(em);
            if (eyes.state.link !== link) return;            // (the display has since been bound to another face)
            eyes.setFace(null);
            for (const e of eyes.eyes) for (const mk of e.marks) mk.mesh.morphTargetInfluences?.fill(0);
        },
    };
    const link = { probe, slot, drive, handle };
    BOUND.set(em, handle);
    eyes.setFace(vrm, link);
    return handle;
}
