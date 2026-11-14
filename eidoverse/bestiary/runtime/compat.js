// compat.js (A2, wave 6; ROADMAP §3 A2, PARITY_MATRIX §A): THE OLD CREATOR'S CALLS ON CLAUDE'S CREATURES. makeCreature
// (eidoverse/creature_builder.js) is a stylised low-poly builder; the Bestiary builds realistic PBR bases. This module maps
// every one of makeCreature's option keys onto a Bestiary recipe field or call (KEY_TABLE: mapped / approx / waiting on a
// named round / ignored by design), and gives the old api on the result.
//
//   const c = await Bestiary.fromMakeCreature(makeCreature.human({ shirt: 0x6ba0c7, hair: 'long', build: 'feminine' }));
//   scene.add(c.group); c.walkTo(1, 2); c.speed = 0.4; c.say('hello'); c.anchor('head').add(thing);
//
//   const c = Bestiary.makeCreature(opts);   // THE DROP-IN: synchronous like makeCreature (c.group now, the creature
//   scene.add(c.group);                      // loading into it; calls made before it is ready are replayed in order);
//   ...  await Bestiary.ready();             // once, after setup: every creature loaded and started where it was put
//   Bestiary.installCompat();                // globalThis.makeCreature -> Bestiary.makeCreature (opt-in; the old builder
//                                            // stays as Bestiary.oldMakeCreature, and makeCreature.human / .random)
//   Bestiary.keyReport(opts)                 // { mapped, approx, waiting, ignored, unknown }: what this call became
//
// WHERE NO REALISTIC BASE EXISTS YET (quad, serpent, bird, spider, fish, snail, aqua, squid: lanes D0a / D1-D11), the
// stance's KEY_TABLE row says so and the drop-in returns the OLD creator's creature for that call (logged): a production
// scene keeps rendering while those bases are built; nothing is dropped silently (the key report lists it).
//
// THE OLD API on the result: group, update(t), speed / turn (properties), walkTo(x, z, speed), setHeading(a), fly(alt, speed),
// land(), say(o), talking (property), setTalkEnvelope(fn), hasJaw, anchor(n), parts(n), headBone, bones, skeleton, legs,
// dismemberManifest / dismemberCoverage; plus .bestiary (the creature: its own api) and .plan (the recipe and the key report).
const THREE = globalThis.THREE;

// ================================================================================================ THE KEY TABLE
// [status, what it becomes, the round it waits on (waiting rows)]. status: 'mapped' (the same feature, realistic), 'approx'
// (the nearest realistic thing: the second column says how it differs), 'waiting' (no realistic version yet: the old creator
// builds it, or the key does nothing on a Bestiary base), 'ignored' (by design: the stylised builder's own construction knobs)
const M = 'mapped', A = 'approx', Wt = 'waiting', I = 'ignored';
export const KEY_TABLE = {
    // ---- body plan (creature_builder.js 627-660)
    stance: [A, "'biped' / headType 'skull' -> the human (B1, VRM); 'octopus' -> the octopus; 'insect' -> the stag beetle; quad / serpent / bird / spider / fish / snail -> the old creator", 'D0a wolf (quad), D1 hawk (bird), D5 snake (serpent), D4 tarantula (spider), D3 koi (fish), D7 snail'],
    legPairs: [A, 'infers the stance as the old creator does (0 serpent, 1 biped, 2 quad, 3 insect, 4+ spider); a count on a base: its own legs', 'D-last body-plan grammar (leg count)'],
    headType: [M, "'skull' (makeCreature.human) -> the human; 'tube' -> the base's own head"],
    build: [A, "'feminine' -> sex F, else M (the canonical bases; a phenotype slider waits on H5); 'thick' etc. on other bases: none", 'H5 phenotypes, E1 knobs'],
    squid: [Wt, 'the octopus (no squid mantle, fins or feeding tentacles)', 'D8 squid'],
    aqua: [Wt, 'the old creator (aqua mammal)', 'D10 dolphin'],
    caudal: [Wt, 'the old creator', 'D3 koi, D10 dolphin'],
    radial: [I, "the old tube's ring segments (a sculpted mesh has its own)"],
    ringsPerSpan: [I, "the old tube's rings per span"],
    taperStart: [I, "the old tube's end taper"],
    taperEnd: [I, "the old tube's end taper"],
    // ---- proportions (654-661, 729, 788, 882, 1078, 1128)
    bodyLength: [A, 'octopus: none; beetle: the whole body scaled to it; human: none (her own height)', 'E1 knobs (staged) / H5'],
    bodyRadius: [A, 'octopus: the size (the arm reach matched to the old one: bodyRadius and tentacleLength together)', 'E1 knobs'],
    neck: [Wt, 'none on the bases (their own necks)', 'E1 knobs'],
    tail: [Wt, 'none (no tailed base in the runtime yet)', 'D0a wolf, E1 knobs'],
    legLength: [Wt, 'none (the bases keep their own legs)', 'E1 knobs (staged)'],
    armLength: [Wt, 'none', 'E1 knobs (staged)'],
    headScale: [Wt, 'none', 'E1 knobs (staged)'],
    legSpread: [Wt, 'none', 'E1 knobs'],
    bodyTilt: [Wt, 'none (the bird stance)', 'D1 hawk'],
    tailRadius: [Wt, 'none', 'E1 knobs'],
    tentacleLength: [A, 'octopus: the size (with bodyRadius: the old arm reach)', 'E1 knobs (arm length alone)'],
    seed: [M, "create's seed (the motion's phases, the human's identity when given)"],
    // ---- head and face (1196-1366, 1384-1590, 1680-1860)
    eyes: [Wt, 'the base\'s own eyes (count and arrangement: none)', 'E1 (eye ports)'],
    eyeColor: [A, "human: the iris colour (the display hex as the ciliary albedo); other bases: none", 'E1 (eye colour uniform on every eye, staged)'],
    pupil: [Wt, "none ('slit': the octopus's is horizontal by anatomy)", 'E4 eye families'],
    eyelids: [Wt, 'none (the human blinks; a resting lid height waits)', 'B-lane face rest pose'],
    muzzle: [Wt, 'none', 'D0a wolf (canid head)'],
    ears: [Wt, 'none', 'D0a wolf (point), E4 ear family (flop), D9 tiger (round)'],
    earScale: [Wt, 'none', 'E4 ear family'],
    fangs: [Wt, 'none', 'D0a wolf (teeth), E4'],
    tusks: [Wt, 'none', 'E4 (horn generator)'],
    tuskLength: [Wt, 'none', 'E4'],
    buckTeeth: [Wt, 'none', 'E4'],
    horns: [Wt, 'none', 'D6 red deer (the horn generator)'],
    hornStyle: [Wt, 'none', 'D6'],
    hornLength: [Wt, 'none', 'D6'],
    hornColor: [Wt, 'none', 'D6'],
    beak: [Wt, "none (the octopus's beak is its own)", 'D1 hawk (the beak swap)'],
    beakHook: [Wt, 'none', 'D1'],
    beakWidth: [Wt, 'none', 'D1'],
    beakColor: [Wt, 'none', 'D1'],
    trunk: [Wt, 'none', 'E4 (proboscidean organ family)'],
    nose: [Wt, "none ('star' and the stylised noses)", 'E4'],
    mouth: [Wt, 'none (the stylised mouth line)', 'E4'],
    whiskers: [Wt, 'none', 'E5 F4'],
    gills: [Wt, 'none (the axolotl has its own)', 'E4 (the axolotl donor)'],
    gillColor: [Wt, 'none', 'E4'],
    antennae: [A, "insect: the beetle's own antennae; other bases: none", 'C12 mech_antenna, E4'],
    hair: [A, "human: B6's coats (spiky, mohawk, curly, long, bob, bun, ponytail as named; 'cap' and every other value the old creator drew as its default cap -> crop; 'none' bare; bob on a man -> crop)", 'B4/B6 polish (crop, long, curly)'],
    hairColor: [A, 'human: the pigment model (natural tones by the black / brown / blonde presets, red by hue, grey by low chroma, any other hue a dye over bleached blonde)'],
    hairBand: [Wt, 'none (the tie on a bun or ponytail)', 'B4'],
    // ---- limbs (632-650, 974-1110, 1127, 1983-2122)
    feet: [A, "human: shoes (the outfit's); 'paw' / 'hoof' / 'webbed' / 'lizard' / 'talon': none", 'D0a (paw), D6 (hoof), D2 (lizard), D1 (talon), E4 (webbed)'],
    hoofColor: [Wt, 'none', 'D6'],
    footColor: [Wt, 'none', 'D-lane feet'],
    hands: [M, "the human's hands (built in)"],
    claws: [Wt, 'none', 'D0b lobster (crusher + cutter)'],
    clawColor: [Wt, 'none', 'D0b'],
    tentacles: [A, 'octopus: its 8 arms (another count: 8)', 'D-last'],
    backTentacles: [Wt, "none (the sisters' back tentacles are the octopus's C5 mech tentacle, the lead's call: HX1's are rejected, REMIX_LIBRARY §5; their runtime air-mode solver waits)", 'ALETHEIA_PLAN (C5 mech tentacle on the back ports)'],
    backTentacleLength: [Wt, 'none', 'ALETHEIA_PLAN (C5 mech tentacle on the back ports)'],
    tailStyle: [Wt, 'none', 'D1 (fan), D2 / D10 (paddle)'],
    tailCarry: [Wt, 'none', 'D0a wolf'],
    wings: [A, "insect: the beetle's elytra and hindwings at rest (fly() lifts the body; no flapping); other bases: none", 'D1 hawk (feather), D11 monarch, E4 (bat)'],
    wingType: [Wt, "none on the beetle; 'butterfly' (a moth / butterfly): the old creator keeps the whole creature", 'D1, D11, E4'],
    wingSpan: [Wt, 'none', 'D1, D11'],
    wingColor: [Wt, 'none', 'D1, D11'],
    fins: [Wt, 'none', 'D3 koi'],
    finScale: [Wt, 'none', 'D3'],
    caudalScale: [Wt, 'none', 'D3'],
    shell: [Wt, 'none', 'D7 snail'],
    shellColor: [Wt, 'none', 'D7'],
    shellScale: [Wt, 'none', 'D7'],
    spikes: [Wt, 'none', 'D2 monitor (spikes, osteoderms)'],
    spikeColor: [Wt, 'none', 'D2'],
    armor: [Wt, 'none', 'D2'],
    armorColor: [Wt, 'none', 'D2'],
    // ---- skin, pattern, material (564-626, 2444-2510)
    color: [A, "human: the skin tone (when skin is not given); octopus: the runtime tint that makes the old colour its mean albedo (the tint multiplies the baked albedo: old / its mean 0.42 0.34 0.33, capped x2); beetle: the hex as its tint (a hue on the near-black chitin, not the old brightness)", 'E2 (skin library + reskin)'],
    skin: [A, "human: the skin tone (the identity's melanin and blood nearest in L*a*b* on the skin LUT; past the human gamut the rest as a tint)"],
    belly: [Wt, 'none (the old down-normal lightening; the bases have their own ventral tone)', 'E2 / remix zones'],
    accent: [Wt, 'none (a zone recolour is the remix\'s)', 'E2 / remix zones'],
    pattern: [A, "octopus: 'spots' -> its white-spot display, 'stripes' -> its dark bands; other bases: none", 'E2 (spots and stripes on every base)'],
    roughness: [I, 'the PBR maps own it'],
    map: [I, 'a texture over the old tube UVs (the bases have baked UV sets)'],
    normalMap: [I, 'as map'],
    roughnessMap: [I, 'as map'],
    outfit: [M, "human: B2's garments (shirt -> the tee's or shirt's dye, pants -> the trousers', shoes -> the shoes'; the old collar band + elbow sleeve -> the tee; null bare)", 'B2b (darts, waistband)'],
    tie: [M, "human: the necktie (the outfit becomes shirt_ls_tie; its colour the tie's dye)"],
    // ---- accessories (2268-2440)
    hat: [A, "'top' -> the top hat; 'officer' -> the peaked cap; 'cap' -> the peaked cap (a peak, not a ball cap); 'beanie' / 'cowboy': none", 'B5 (beanie, cowboy, a ball cap)'],
    hatColor: [A, "the hat's felt / crown zone"],
    hatBand: [A, "the hat's band zone"],
    glasses: [M, 'the round glasses (fitted on seat_glasses)'],
    glassesColor: [A, 'the frames\' plating'],
    sunglasses: [A, "the round glasses with a dark lens (their palette's glass zone tints the transmissive lens; the frame is round, not a sunglasses frame)", 'B5 (a sunglasses frame)'],
    helmet: [Wt, 'none', 'B5 (space helmet, hard hat)'],
    helmetColor: [Wt, 'none', 'B5'],
    mask: [Wt, 'none', 'B5 (smile and frown masks)'],
    maskColor: [Wt, 'none', 'B5'],
    maskInk: [Wt, 'none', 'B5'],
    // ---- robot / cyborg (570-580, 642-644, 2455-2510)
    robot: [A, "octopus: the cyborg octopus (C5b's build: plates on the mantle, eye implants, two mech tentacles); insect: the cyborg stag beetle; a PERSON (robot: true alone): the old creator (a person with robot hands is not a whole-body robot)", 'C7 (the robot:true preset over every base), C5 (arms, legs), C13 (machine head)'],
    robotParts: [A, "human 'arms' -> my robot's hands at both wrists (C3); octopus 'tentacles' / 'head' -> the cyborg octopus; insect any -> the cyborg beetle; human 'head' / 'legs' / 'body' / 'neck': none", 'C13 (head), C5 (legs), C7 (body), C11 (tail)'],
    robotColor: [Wt, 'none (the robot hand keeps its finish)', 'C6 (robotColor through the MASKS tint)'],
    // ---- motion (2524-3142)
    speed: [M, 'the spine\'s speed(v) (m/s; the old default 0.5 walks forward, 0 stands)'],
    turn: [M, "the spine's turn(w) (rad/s)"],
    heading: [M, 'the start heading (setHeading)'],
    gait: [Wt, "none ('walk' / 'trot' / 'gallop' on a quad)", 'D0a wolf gaits'],
    stride: [I, 'the base\'s gait owns its stride'],
    auto: [M, "create's auto (self-animating unless false; then update(t))"],
    groundY: [M, 'the ground height (the human\'s controller stands on it; other bases sit at it)'],
    swimDepth: [Wt, 'none', 'D3 koi'],
    waveAmp: [Wt, 'none (the serpent\'s S-wave)', 'D5'],
    waveLength: [Wt, 'none', 'D5'],
    headLift: [Wt, 'none', 'D5'],
};
// the sub-keys and makeCreature.human's own arguments (its options are spread over its result)
export const SUBKEY_TABLE = {
    'outfit.shirt': [M, "the top's dye zone"], 'outfit.pants': [M, "the trousers' dye zone"], 'outfit.shoes': [M, "the shoes' dye zone"],
    'outfit.collarY': [I, 'the old colour band heights'], 'outfit.hipY': [I, 'the old colour band heights'], 'outfit.ankleY': [I, 'the old colour band heights'],
    'human.shirt': [M, 'outfit.shirt'], 'human.pants': [M, 'outfit.pants'], 'human.shoes': [M, 'outfit.shoes'],
};

// ================================================================================================ THE PLAN (opts -> recipe)
function stanceOf(opts) {
    const lp = opts.legPairs ?? 2;
    return opts.stance ?? (lp === 0 ? 'serpent' : lp === 1 ? 'biped' : lp === 3 ? 'insect' : lp >= 4 ? 'spider' : 'quad');
}
const HAIR_OK = ['spiky', 'mohawk', 'curly', 'long', 'bob', 'bun', 'ponytail'];
// THE OLD COLOUR ON THE OCTOPUS (11-09): the old creator's colour was its creature's albedo; the octopus's palette tint
// MULTIPLIES its baked albedo (bestiary.js skinMaterial: base.rgb.mul(U.tint)), whose mean is this (linear, the head atlas:
// tests/r03_albedo_mean.py; the realistic and C5b's cyborg glbs agree within 0.006). The tint old / mean gives the octopus
// the old colour as its mean (with the hex itself as the tint, amc7_broadcast's magenta octopus under the table read dark
// plum, urban_pacification's red one maroon); capped at 2 so the skin's light texels keep their detail. The beetle keeps
// the hex as its tint: its chitin's mean is 0.02 (a match would need x40 on a near-black ground), so the hex is its hue
const OCTOPUS_ALBEDO_MEAN = [0.4223, 0.3412, 0.3269];
function octopusTint(hex) {
    const c = new THREE.Color(hex);   // (linear: a hex is read as sRGB under three's colour management)
    const m = OCTOPUS_ALBEDO_MEAN;
    return new THREE.Color(Math.min(2, c.r / m[0]), Math.min(2, c.g / m[1]), Math.min(2, c.b / m[2]));
}
// THE CYBORG OCTOPUS (C5b's assembled build: the C3 plates and feed baked on the mantle; recipe.py CYBORG_OCTOPUS's parts):
// the eye implants and the knuckled mech tentacles on arm7 / arm3; the hose only with the seed it was drawn for (3)
const CYBORG_OCTOPUS = {
    path: 'work/bestiary/cyborg_c5b/assembled/octopus.glb',
    parts: [
        { kind: 'eye_implant', variant: 'lens', socket: 'socket_eye_L', path: 'work/bestiary/cyborg_c4/eye_implant_lens.glb' },
        { kind: 'eye_implant', variant: 'lens', socket: 'socket_eye_R', path: 'work/bestiary/cyborg_c4/eye_implant_lens.glb' },
        { kind: 'mech_tentacle', variant: 'knuckled', chain: 'arm7', cut: 8, path: 'work/bestiary/cyborg_c5/mech_tentacle.glb' },
        { kind: 'mech_tentacle', variant: 'knuckled', chain: 'arm3', cut: 8, path: 'work/bestiary/cyborg_c5/mech_tentacle.glb' },
    ],
    hose: { kind: 'hose', chain: 'arm7', source: 'plates', seed: 3, path: 'work/bestiary/cyborg_c5b/hose/cyborg_hose_arm7_s3.glb' },
    glow: { glow: [0.0, 0.5, 1.0], intensity: 2.0, rate: 1.0, pulse: 0.25 },
};
// a HUMAN-LIKE biped (the human preset's skull head, or a biped with no animal face or feet); an animal biped (a muzzle,
// ears, a beak, horns ...) waits on the body-plan grammar and the head families
const ANIMAL_FACE = ['muzzle', 'ears', 'beak', 'trunk', 'horns', 'tusks', 'fangs', 'buckTeeth', 'whiskers', 'gills', 'shell'];
export function planFromMakeCreature(opts = {}) {
    const stance = stanceOf(opts);
    const animal = ANIMAL_FACE.some((k) => opts[k]) || (opts.feet && opts.feet !== 'shoe');
    const humanLike = opts.headType === 'skull' || (stance === 'biped' && !animal);
    // robot: true on a person is a whole-body robot (the old plating): a person with robot hands is not that (C7 waits)
    const robotPerson = humanLike && opts.robot === true && !opts.robotParts;
    const human = humanLike && !robotPerson;
    // (a butterfly-winged insect is a moth or a butterfly, not a beetle: the old creator keeps it until D11's monarch lands;
    // vlf_moth_phase5's "coherence moth", labelled MOTH on its screen, read as a dark stag beetle through the beetle, 11-09)
    const lepidopteran = stance === 'insect' && opts.wingType === 'butterfly';
    const base = human ? 'human' : stance === 'octopus' ? 'octopus' : stance === 'insect' && !lepidopteran ? 'stag_beetle' : null;
    const create = { species: base, seed: opts.seed ?? 1, auto: opts.auto };
    const after = [];          // calls made on the creature once it stands where the scene put it
    const report = { stance, base: base || 'old creator', mapped: [], approx: [], waiting: [], ignored: [], unknown: [] };
    if (robotPerson) report.waiting.push('robot: a whole-body robot person (C7 robot:true preset; C5 arms and legs)');
    if (lepidopteran) report.waiting.push("wingType 'butterfly': a moth / butterfly (D11 monarch)");
    if (stance === 'biped' && animal && opts.headType !== 'skull') report.waiting.push('stance: an animal biped (D-last body-plan grammar, E4 heads)');
    const note = (k, why) => {
        const row = KEY_TABLE[k];
        if (!row && SUBKEY_TABLE[`human.${k}`]) { report.mapped.push(`${k} (outfit.${k})`); return; }
        if (!row) { report.unknown.push(k); return; }
        const [st] = row;
        const bucket = st === M ? 'mapped' : st === A ? 'approx' : st === Wt ? 'waiting' : 'ignored';
        report[bucket].push(why ? `${k}: ${why}` : k);
    };
    for (const k of Object.keys(opts)) if (opts[k] !== undefined) note(k);
    if (!base) return { base: null, stance, create: null, after, report };
    if (human) {
        create.sex = opts.build === 'feminine' ? 'F' : 'M';
        // the identity: the old seed rolls one (the reference identities only without a seed)
        if (opts.seed == null) create.identity = 'reference';
        // the outfit: the old one is a colour band suit (shirt / pants / shoes, a collar, sleeves to the elbow) -> the tee;
        // a tie -> the long-sleeved shirt and tie; outfit null -> bare
        const o = opts.outfit;
        if (o) {
            create.outfit = { top: opts.tie != null ? 'shirt_ls_tie' : 'tee', shirt: o.shirt, pants: o.pants, shoes: o.shoes,
                ...(opts.tie != null ? { tie: opts.tie } : {}) };
        }
        // the hair: the old named styles as named, every other value (cap, short, ...) the old default cap -> crop
        const hv = opts.hair;
        if (hv && hv !== 'none') {
            const style = HAIR_OK.includes(hv) ? hv : 'crop';
            create.hair = { style: create.sex === 'M' && style === 'bob' ? 'crop' : style, colour: opts.hairColor ?? 0x3a2a1a };
        }
        const skin = opts.skin ?? opts.color;
        if (skin != null) create.skin = skin;
        if (opts.eyeColor != null) create.eyes = opts.eyeColor;
        if (opts.glasses || opts.sunglasses) {
            // sunglasses: the round glasses with a dark lens (their palette's glass zone tints the transmissive lens)
            const pal = { ...(opts.glassesColor != null ? { plating: opts.glassesColor } : {}),
                ...(opts.sunglasses ? { glass: 0x1c1c1e } : {}) };
            create.glasses = Object.keys(pal).length ? { palette: pal } : true;
        }
        if (opts.hat) {
            const name = opts.hat === 'top' ? 'top_hat' : (opts.hat === 'officer' || opts.hat === 'cap') ? 'peaked_cap' : null;
            if (name) {
                const pal = {};
                if (opts.hatColor != null) pal[name === 'top_hat' ? 'felt' : 'crown'] = opts.hatColor;
                if (opts.hatBand != null) pal.band = opts.hatBand;
                create.hat = { name, ...(Object.keys(pal).length ? { palette: pal } : {}) };
            }
        }
        const rp = opts.robotParts || (opts.robot ? ['arms'] : []);
        if (rp.includes('arms')) create.hand = 'robot';
        create.groundY = opts.groundY;
    } else if (base === 'octopus') {
        // the size: the old arm reach (0.16 R + tentacleLength R', R = bodyRadius / 0.3) over the octopus's own (its group)
        const os = (opts.bodyRadius ?? 0.22) / 0.3;
        create.reach = 0.16 * os + (opts.tentacleLength ?? 1.05) * os;
        if (opts.color != null) create.tint = opts.color;
        if (opts.pattern === 'spots') create.display = { spots: 1.0 };
        if (opts.pattern === 'stripes' || opts.pattern === 'stripe') create.display = { dark: 0.8 };
        // robot: the cyborg octopus (C5b's: plates baked, eye implants, two mech tentacles; the hose only at its seed)
        const rp = opts.robotParts || [];
        if (opts.robot === true || rp.includes('tentacles') || rp.includes('head')) {
            create.path = CYBORG_OCTOPUS.path;
            create.cyborg = { ...CYBORG_OCTOPUS.glow, parts: [...CYBORG_OCTOPUS.parts, ...((opts.seed ?? 1) === 3 ? [CYBORG_OCTOPUS.hose] : [])] };
        }
    } else if (base === 'stag_beetle') {
        // the size: the old body length (default 0.85 m: a giant bug) over the beetle's own; the hero glb (x10) and a scale
        create.size = 'hero';
        create.length = opts.bodyLength ?? 0.85;
        if (opts.color != null) create.tint = opts.color;
        // robot: the cyborg beetle (its built variant)
        if (opts.robot === true || (opts.robotParts || []).length) create.variant = 'cyborg';
    }
    create.heading = opts.heading;
    const speed = opts.speed ?? (human && opts.headType === 'skull' ? 0.45 : 0.5);
    return { base, stance, create, after, report, speed, turn: opts.turn ?? 0, groundY: opts.groundY ?? null };
}
export function keyReport(opts) { return planFromMakeCreature(opts).report; }

// ================================================================================================ THE OLD API
const pending = [];
export async function ready() {
    // every drop-in creature loaded and started where the scene put it (call once setup has placed them)
    const all = pending.splice(0);
    await Promise.all(all.map((f) => f()));
}

function makeFacade(opts, plan) {
    const group = new THREE.Group();
    group.name = `bestiary_compat_${plan.base}`;
    group.rotation.order = 'YXZ';
    Object.assign(group.userData, { allowIntersect: true, noSupportCheck: true, isCreature: true });
    const isHuman = plan.base === 'human';
    const st = { speed: plan.speed, turn: plan.turn, target: null, talking: false, queue: [], c: null, placeholders: {},
        failed: null, walkQueued: false };
    // the start heading: the human's is its group's (the controller starts facing it); a base's a setHeading on its spine
    if (opts.heading != null) {
        if (isHuman) group.rotation.y = opts.heading;
        else st.queue.push((c) => c.setHeading(opts.heading));
    }
    let warned = false;
    const B = () => globalThis.Bestiary;
    // (a base's controls read its group against its parent (locomotion.js parentToP): each call runs with the creature in
    // its life place in the sizer, not the shift that shows its root at the group's origin (step()))
    const inLife = (fn) => {
        const g = isHuman ? null : st.c.group;
        if (!g) return fn(st.c);
        const x = g.position.x, z = g.position.z;
        g.position.x = 0; g.position.z = 0;
        try { return fn(st.c); } finally { g.position.x = x; g.position.z = z; }
    };
    const call = (fn) => {
        if (st.c) { try { return inLife(fn); } catch (e) { if (!warned) { warned = true; console.warn(`[compat] ${plan.base}: ${e.message}`); } } }
        else st.queue.push(fn);
        return undefined;
    };
    // THE SIZE (a Bestiary base, not the human): the old creature's size (the octopus's arm reach, the bug's length) is a
    // DISPLAY scale. The bases' motion works in world metres at life size (the octopus's arms are laid on the sand by world
    // heights and its bind-measured reach: scaled x2.6 they curled to 0.64 m and floated 5 cm, b1_motion compat_octo,
    // 11-09), so each update runs with this group and the sizer at scale 1 and the scale goes back after it: the pose is
    // the life one, shown at the old size about the ground point. The old api's distances and speeds are the scene's
    // metres: walkTo's point and speed and fly's altitude are divided by the shown scale into the creature's own
    const sizer = new THREE.Group();
    sizer.name = 'compat_size';
    group.add(sizer);
    const shown = () => group.scale.x * sizer.scale.x;
    // THE ROOT MOTION (a base): the old creator moved its group (group.position += forward * speed * dt), so what a scene
    // hangs on the group travels with the creature (kronos_kult_0715's eyes, laser beams and crown on hero.group) and a
    // scene that reads group.position follows it. A base walks its own root in the sizer: each update runs it in a fixed
    // LIFE FRAME (scale 1, upright, at the placement it had at ready, the root where it left it: its world-space state, the
    // arms laid on the sand, stays continuous whatever the scene does to the group), then the root's move is handed to the
    // group in the scene's frame and size and the root is shown at the group's origin (step())
    const life = { pos: new THREE.Vector3(), root: new THREE.Vector3(), r0: new THREE.Vector3(), y0: 0, t: null };
    // a point of the group's parent -> the creature's frame: the human's group IS the placement (its frame the parent's);
    // a Bestiary base's frame is the sizer's, unscaled (the update's own), its root at life.root there
    const toLocal = (x, z) => {
        if (plan.base === 'human') return [x, z];
        group.updateWorldMatrix(true, false);
        const p = new THREE.Vector3(x, 0, z);
        if (group.parent) p.applyMatrix4(group.parent.matrixWorld);
        const q = group.getWorldQuaternion(new THREE.Quaternion()).invert();
        const o = group.getWorldPosition(new THREE.Vector3());
        p.sub(o).applyQuaternion(q).divideScalar(shown());
        return [life.root.x + p.x, life.root.z + p.z];
    };
    const per = (v) => (plan.base === 'human' || v == null ? v : v / shown());
    // (a base turns toward the point at the old creator's turn rate, 1.4 rad/s (its maxTurn off the serpent): the planner's
    // own 0.8 put kronos_kult_0715's hero 4.5 s behind the old one, b1_motion vs_old_kronos)
    const walkTo = (c, x, z, v) => {
        const [lx, lz] = toLocal(x, z);
        return c.walkTo(lx, lz, isHuman ? { speed: per(v), radius: per(0.25) } : { speed: per(v), radius: per(0.25), turnRate: 1.4 });
    };
    // A STAND-IN FOR THE SETUP: the group is empty until the creature has loaded, but a scene measures it right away
    // (placeOn / snapToGround / faceToward seat a bbox: an empty one placed it at NaN): an undrawn box of the old
    // creature's size, feet at the origin, until ready() puts the creature in it
    const dims = isHuman ? [0.5, plan.create.sex === 'F' ? 1.62 : 1.76, 0.3]
        : plan.create.reach ? [2 * plan.create.reach, 0.27 * plan.create.reach, 2 * plan.create.reach]
            : [0.6 * (plan.create.length || 0.85), 0.35 * (plan.create.length || 0.85), plan.create.length || 0.85];
    const proxy = new THREE.Mesh(new THREE.BoxGeometry(...dims), new THREE.MeshBasicNodeMaterial());
    proxy.material.visible = false;
    proxy.position.y = dims[1] / 2;
    proxy.name = 'compat_standin';
    proxy.castShadow = false; proxy.receiveShadow = false;
    group.add(proxy);
    const limbs = !isHuman ? [] : [[true, -1], [true, 1], [false, -1], [false, 1]].map(([isArm, side]) => {
        const rec = { isArm, side }, spare = {};
        for (const k of ['hip', 'knee', 'ankle', 'foot']) {
            Object.defineProperty(rec, k, { enumerable: true, get() {
                const L = st.c?.limbs?.find((l) => l.isArm === isArm && l.side === side);
                return L?.[k] || (spare[k] ||= new THREE.Object3D());
            } });
        }
        return rec;
    });
    const s0 = new THREE.Vector3(), p0 = new THREE.Vector3(), q0 = new THREE.Quaternion(), mv = new THREE.Vector3();
    const rw = new THREE.Vector3();
    // the root bone (the schedulers walk it: locomotion.js root.position.copy(body.p)); its xz in the sizer and its height
    // over the ground, life frame
    const rootAt = () => {
        const r = st.c?.bones?.get?.('root');
        if (!r) return null;
        r.updateWorldMatrix(true, false);
        r.getWorldPosition(rw);
        return [rw.x - life.pos.x, rw.z - life.pos.z, rw.y - (plan.groundY ?? 0)];
    };
    let thrown = false;
    const step = (t) => {
        const c = st.c, gy = plan.groundY ?? 0;
        // (a bare speed set since the last update and no walkTo after it: now)
        if (st.speedDirty) { st.speedDirty = false; try { inLife((cc) => cc.speed(per(st.speed))); } catch (_) { /* */ } }
        p0.copy(group.position); q0.copy(group.quaternion); s0.copy(group.scale);
        const k = sizer.scale.x;
        // the life frame (above)
        group.position.set(life.pos.x, gy, life.pos.z); group.quaternion.identity();
        group.scale.set(1, 1, 1); sizer.scale.set(1, 1, 1); sizer.position.y = 0;
        c.group.position.x = 0; c.group.position.z = 0;
        group.updateMatrixWorld(true);
        try { c.update(t); } catch (e) { if (!thrown) { thrown = true; console.error(`[compat] ${plan.base} update: ${e.message}\n${e.stack}`); } }
        // the root's move this update -> the group's, in the scene's frame and size; the creature shifted back so its root
        // stays where the group shows it (life.root: the root's move since ready, life.r0 its place then)
        // (a move faster than the creature could go is a change of mode, not a step: the flight's glide puts the root on its
        // own body point, 0.25 m off the standing root on the beetle (b1_motion compat_beetle_fly): the creature is re-centred
        // on the group and the group stays, as the old creature's did)
        const r = rootAt();
        mv.set(0, 0, 0);
        if (r) {
            const rx = r[0] - life.r0.x, rz = r[1] - life.r0.z;
            mv.set(rx - life.root.x, 0, rz - life.root.z);
            const dtm = life.t == null ? 1 / 30 : Math.max(1 / 240, Math.abs(t - life.t));
            if (mv.length() * s0.x * k > Math.max(1.0, 2 * Math.abs(st.speed)) * dtm + 0.005) mv.set(0, 0, 0);
            life.root.set(rx, 0, rz);
        }
        life.t = t;
        // THE OLD ALTITUDE (fly / land): the old creator's body approached its altitude at 1.5 / s (airY += (alt - airY) *
        // dt * 1.5, in the scene's metres: a 9.3 m drone came down to 2.15 in ~2 s); the base's own flight eases at 0.5 m/s
        // of its size (sunny_market_civic_drones' beetles reached the stalls ~6 s after the old drones). The base flies as
        // it flies (wings, legs tucked, pitch); the sizer lifts it so its body shows at the old altitude
        let sy = 0;
        if (st.fly) {
            const f = st.fly, dtf = f.t == null ? 1 / 30 : Math.max(0, t - f.t);
            f.t = t;
            f.air += (f.target - f.air) * Math.min(1, dtf * 1.5);
            const own = r ? Math.max(0, r[2] - life.y0) : 0;
            sy = f.air / s0.x - own * k;
            if (f.target <= 0 && f.air < 0.005) st.fly = null;
        }
        c.group.position.x = -life.root.x; c.group.position.z = -life.root.z;
        mv.multiplyScalar(s0.x * k).applyQuaternion(q0);
        // (the old creator stands its group on groundY (default 0) every update: a scene's own y is overwritten, as there)
        group.position.set(p0.x + mv.x, gy, p0.z + mv.z);
        group.quaternion.copy(q0); group.scale.copy(s0); sizer.scale.setScalar(k); sizer.position.y = sy;
        group.updateMatrixWorld(true);
    };
    const api = {
        group, plan,
        get bestiary() { return st.c; },
        get speed() { return st.speed; },
        set speed(v) {
            st.speed = v;
            // a base's bare speed waits for its next update (step()): a walkTo in the same frame takes it as its own speed,
            // as the old api did (`hero.speed = 1.18; hero.walkTo(5.5, 0)`: applied at once, the base set off forward, was
            // brought to rest, turned, then walked: the planner's order, kronos_kult_0715's hero 4.5 s late)
            if (!isHuman && st.c && !(st.target && v > 0.01)) { st.target = null; st.speedDirty = true; return; }
            call((c) => {
                if (st.target && v > 0.01) return walkTo(c, st.target.x, st.target.z, v);
                st.target = null;
                return c.speed(per(v));
            });
        },
        get turn() { return st.turn; },
        set turn(w) { st.turn = w; call((c) => c.turn(w)); },
        walkTo(x, z, speed) {
            st.target = { x, z };
            st.speedDirty = false;
            if (speed != null) st.speed = speed; else if (st.speed < 0.05) st.speed = 0.5;
            const v = st.speed;
            if (!st.c) st.walkQueued = true;
            call((c) => walkTo(c, x, z, v));
        },
        setHeading(a) {
            // before the human starts, its group's heading is its start heading
            if (isHuman && !st.c) { group.rotation.y = a; return; }
            call((c) => c.setHeading(a));
        },
        // the old fly: the altitude (approached at 1.5 / s: step()) and the forward speed (none given: at least 0.9 m/s, the
        // old cruise); the base flies at its own pace underneath, shown at the old altitude
        fly(alt = 1.6, speed) {
            if (!isHuman) st.fly = { target: alt, air: st.fly ? st.fly.air : 0, t: st.fly ? st.fly.t : null };
            api.speed = speed != null ? speed : Math.max(st.speed, 0.9);
            call((c) => c.fly(per(alt)));
        },
        land() { if (st.fly) st.fly.target = 0; call((c) => c.land()); },
        say(o) { call((c) => c.say(o)); return api; },
        get talking() { return st.c ? !!st.c.talking : st.talking; },
        set talking(v) { st.talking = v; call((c) => { c.talking = v; }); },
        setTalkEnvelope(fn) { call((c) => c.setTalkEnvelope(fn)); return api; },
        get hasJaw() { return st.c ? !!st.c.hasJaw : true; },
        anchor(n) {
            // the human's anchors are its own; a base's is a child of its anchor that undoes the display size (a prop the scene
            // sizes in metres keeps its metres); before the creature is ready, a placeholder the scene can add to, moved onto
            // the real anchor at ready
            const real = st.c?.anchor?.(n);
            if (real && isHuman) return real;
            if (!st.placeholders[n]) {
                const p = new THREE.Group();
                p.name = `compat_anchor_${n}`;
                if (real) { real.add(p); p.scale.setScalar(1 / sizer.scale.x); } else group.add(p);
                st.placeholders[n] = p;
            }
            return st.placeholders[n];
        },
        parts(n) { return st.c?.parts?.(n) || []; },
        get headBone() { return st.c ? (st.c.headBone || st.c.anchor?.('head') || null) : api.anchor('head'); },
        get bones() { return st.c ? (st.c.bones instanceof Map ? [...st.c.bones.values()] : (st.c.bones || [])) : []; },
        get skeleton() { return st.c?.skeleton || null; },
        // the old limb records, stable from the call on (a scene keeps them from setup: memesai_prospector's
        // legs.find((l) => l.isArm && l.side < 0)); each field the creature's own node once it is ready, a stand-in before
        get legs() { return limbs; },
        dismemberManifest: null,
        dismemberCoverage: { unsupported: ['the Bestiary dismember manifest (ring records as detach sites) waits on A2b'] },
        update(t) {
            if (!st.c || opts.auto !== false) return;
            if (isHuman) st.c.update(t); else step(t);
        },
        get failed() { return st.failed; },
    };
    // the creature, loading now; started at ready() where the scene has put the group. A base runs through step() (the
    // facade's own entry in _autoCreatures when the old call was self-animating), the human through its own
    const C = plan.create;
    const loading = (async () => {
        const o = { ...C, auto: isHuman ? opts.auto : false };
        delete o.reach; delete o.length;
        if (isHuman) Object.assign(o, { group, deferStart: true });
        else o.pose = { groundY: plan.groundY ?? 0 };
        return await B().create(o);
    })();
    loading.catch((e) => { st.failed = e; console.error(`[compat] ${plan.base} failed to load: ${e.message}`); });
    pending.push(async () => {
        let c;
        try { c = await loading; } catch (e) { return; }
        if (plan.base === 'human') {
            // the controller starts where the scene put the group (its height the ground unless groundY says)
            await c.start({ groundY: plan.groundY ?? undefined });
        } else {
            sizer.add(c.group);
            // the size: matched to the old creature's (octopus: the arm reach; beetle: the body length), from its rest box
            // at life size ON ITS GROUND (the octopus lays its arms on the sand at groundY's world height: measured before the
            // group stood there they curled up to it, 0.16 m for the kaiju's 3 m roof, b1 c01_facades 11-09); the sizer shows
            // it at that scale, the motion stays at life (step())
            // (measured in the life frame step() runs it in: upright at the placement's xz, scale 1; the scene's placement,
            // turn and scale on its group kept, the root shown at the group's origin)
            const gy = plan.groundY ?? 0;
            const pScene = group.position.clone(), qScene = group.quaternion.clone(), sScene = group.scale.clone();
            life.pos.set(pScene.x, 0, pScene.z);
            group.position.set(life.pos.x, gy, life.pos.z); group.quaternion.identity();
            group.scale.set(1, 1, 1); sizer.scale.set(1, 1, 1);
            group.updateMatrixWorld(true);
            c.update(0);
            c.group.updateMatrixWorld(true);
            const box = new THREE.Box3().setFromObject(c.group, true);
            const r0 = rootAt();
            if (r0) { life.r0.set(r0[0], 0, r0[1]); life.y0 = r0[2]; }   // (y0: the root's height standing, for fly)
            life.root.set(0, 0, 0);
            group.position.copy(pScene); group.quaternion.copy(qScene); group.scale.copy(sScene);
            const sz = box.getSize(new THREE.Vector3());
            const k = C.reach ? C.reach / Math.max(1e-6, 0.5 * Math.max(sz.x, sz.z))
                : C.length ? C.length / Math.max(1e-6, sz.z) : 1;
            sizer.scale.setScalar(k);
            console.log(`[compat] ${plan.base} sized to the old creature: ${C.reach ? `arm reach ${C.reach.toFixed(3)} m` : `length ${C.length} m`}`
                + ` over its own ${(C.reach ? 0.5 * Math.max(sz.x, sz.z) : sz.z).toFixed(3)} m -> shown x${k.toFixed(3)}`);
            // (the old colour: the octopus's mean albedo becomes it (octopusTint above); the beetle takes the hex as its tint)
            if (C.tint != null) c.palette?.({ tint: plan.base === 'octopus' ? octopusTint(C.tint) : C.tint });
            if (C.display) c.setDisplay?.(C.display);
            group.position.y = plan.groundY ?? 0;
            if (opts.auto !== false) (globalThis._autoCreatures || (globalThis._autoCreatures = [])).push(step);
        }
        group.remove(proxy);
        proxy.geometry.dispose();
        st.c = c;
        // the anchors the scene used before: onto the real ones, their children kept in their frames (a base's anchor is inside
        // the display size: the placeholder undoes it, so a prop the scene sized in metres keeps its metres)
        for (const [n, p] of Object.entries(st.placeholders)) {
            const a = c.anchor?.(n);
            if (!a) continue;
            a.add(p);
            p.position.set(0, 0, 0); p.quaternion.identity(); p.scale.setScalar(isHuman ? 1 : 1 / sizer.scale.x);
        }
        // the old defaults (speed 0.5 walks forward) and every call queued before the creature was ready, in order
        const q = st.queue.splice(0);
        // (in the creature's own metres: the old speed is the scene's, a base is shown at its size; per())
        if (!st.walkQueued && st.speed > 0.01 && !st.target) { try { c.speed(per(st.speed)); } catch (_) { /* */ } }
        if (st.turn) { try { c.turn(st.turn); } catch (_) { /* */ } }
        for (const f of q) { try { f(c); } catch (e) { console.warn(`[compat] replay: ${e.message}`); } }
        console.log(`[compat] ${plan.stance} -> ${plan.base}: mapped ${plan.report.mapped.length}, approx ${plan.report.approx.length}, `
            + `waiting ${plan.report.waiting.length} (${plan.report.waiting.join(', ')}), unknown ${plan.report.unknown.join(', ') || 'none'}`);
    });
    return api;
}

// THE DROP-IN (synchronous, like makeCreature)
export function compatMakeCreature(opts = {}) {
    const plan = planFromMakeCreature(opts);
    if (!plan.base) {
        const old = globalThis.Bestiary?.oldMakeCreature || globalThis.makeCreature;
        const what = plan.stance === 'insect' ? "a butterfly-winged insect (a moth / butterfly: D11 monarch)" : `stance '${plan.stance}'`;
        console.log(`[compat] ${what} has no realistic base yet (${KEY_TABLE.stance[2]}): the old creator builds it`);
        const c = old(opts);
        c.plan = plan;
        return c;
    }
    return makeFacade(opts, plan);
}
// THE ASYNC FORM: the creature loaded and started (where the group stands now)
export async function fromMakeCreature(opts = {}) {
    const c = compatMakeCreature(opts);
    await ready();
    return c;
}
// THE GLOBAL SWAP (opt-in): makeCreature's calls go to the drop-in; its presets stay (they only build options)
export function installCompat() {
    const B = globalThis.Bestiary;
    const old = globalThis.makeCreature;
    if (!old || old.__bestiaryCompat) return;
    B.oldMakeCreature = old;
    const shim = (opts) => compatMakeCreature(opts);
    shim.__bestiaryCompat = true;
    shim.human = old.human;
    shim.random = old.random;
    globalThis.makeCreature = shim;
}

// ================================================================================================ random(seed)
// ONE CALL, A WHOLE CREATURE (ROADMAP A2): the base, then what that base takes at runtime: the human's sex, identity, hair
// (style and colour), outfit and its colours, glasses / hat, the cyborg roll (the robot hands); the octopus's tint and
// display; the beetle's variant (crystal, ice, cyborg, cyborg_crystal: the elements and the cyborg roll it has built) and
// its iridophore family. The remix's elements, affixes and mutations on the octopus go through remix.js with a block that
// recipe.py resolves (runtime_a2/random_pool.json, written offline by tests/r01_pool.py; used when present). The recipe is
// returned with the creature (c.recipe), so a seed is reproducible and printable.
function rng(seed) {
    let s = (seed | 0) ^ 0x9e3779b9;
    return () => {
        s = Math.imul(s ^ (s >>> 16), 0x85ebca6b); s = Math.imul(s ^ (s >>> 13), 0xc2b2ae35); s ^= s >>> 16;
        return (s >>> 0) / 4294967296;
    };
}
const pick = (r, xs) => xs[Math.floor(r() * xs.length) % xs.length];
export function randomRecipe(seed = 1) {
    const r = rng(seed);
    const base = pick(r, ['human', 'human', 'octopus', 'octopus', 'stag_beetle', 'axolotl']);
    if (base === 'human') {
        const sex = r() < 0.5 ? 'F' : 'M';
        const styles = sex === 'F' ? ['bob', 'bun', 'crop', 'curly', 'long', 'mohawk', 'ponytail', 'spiky']
            : ['bun', 'crop', 'curly', 'long', 'mohawk', 'ponytail', 'spiky'];
        const colours = ['black', 'black', 'brown', 'brown', 'blonde', 'red', 'grey', 0x7a1f8a, 0x1f6aa8];
        const tops = [null, 'tee', 'tee', 'shirt_ss', 'shirt_ls', 'shirt_ls_tie'];
        const top = pick(r, tops);
        const dye = () => new THREE.Color().setHSL(r(), 0.2 + 0.5 * r(), 0.15 + 0.55 * r()).getHex();
        const tones = [0xf1c8a8, 0xe0ac8a, 0xc99170, 0xa8714f, 0x8a5a3c, 0x5e3a24];
        return { species: 'human', seed, sex, skin: pick(r, tones),
            hair: r() < 0.08 ? null : { style: pick(r, styles), colour: pick(r, colours) },
            outfit: top ? { top, shirt: dye(), pants: dye(), shoes: pick(r, [0x221d18, 0x15120f, 0x5a3a22, 0xd8d4cc]),
                ...(top === 'shirt_ls_tie' ? { tie: dye() } : {}) } : null,
            glasses: r() < 0.25, hat: r() < 0.2 ? pick(r, ['peaked_cap', 'top_hat']) : null,
            hand: r() < 0.15 ? 'robot' : null };
    }
    if (base === 'octopus') {
        const tint = new THREE.Color().setHSL(r(), 0.15 + 0.4 * r(), 0.55 + 0.4 * r()).getHex();
        const disp = pick(r, [{}, { spots: 1 }, { dark: 0.6, spots: 0.8 }, { clouds: 1 }, { rings: 1 }, { mottle: 1 }]);
        return { species: 'octopus', seed, tint, display: disp, remixSeed: Math.floor(r() * 1e6) };
    }
    if (base === 'stag_beetle') {
        return { species: 'stag_beetle', seed, variant: pick(r, [null, null, 'crystal', 'ice', 'cyborg', 'cyborg_crystal']),
            family: pick(r, ['none', 'none', 'jewel', 'sapphire', 'oilslick', 'gold']) };
    }
    return { species: 'axolotl', seed };
}
export async function random(seed = 1, opts = {}) {
    const R = randomRecipe(seed);
    const B = globalThis.Bestiary;
    const { remixSeed, display, ...c } = R;
    if (c.variant == null) delete c.variant;
    const api = await B.create({ ...c, ...opts });
    if (display && api.setDisplay) api.setDisplay(display);
    // the octopus's remix (elements, affixes, mutations) from the offline pool, when it is on disk
    if (R.species === 'octopus' && opts.remix !== false) {
        try {
            const pool = JSON.parse(new TextDecoder().decode(Deno.readFileSync(opts.poolPath || 'work/bestiary/runtime_a2/random_pool.json')));
            const block = pool.octopus?.[remixSeed % (pool.octopus?.length || 1)];
            if (block) {
                const RX = await import('./remix.js');
                api.remix = await RX.apply(api, block, { seed });
                R.remix = { element: block.element?.name ?? block.element ?? null, affixes: block.affixes ?? null, pool: remixSeed % pool.octopus.length };
            }
        } catch (_) { /* no pool on disk: the base and its runtime rolls only */ }
    }
    api.recipe = R;
    return api;
}
