// coat_film_maps.js (THE COAT'S RIG ROUND, human/aletheia/coat_rig, 11-18, Opus 5.5): a COPY of the coat round's
// coat_design/material/engine/coat_film.js (sha1 07c5bfdc, read only), changed in two places for the LOW and its bake
// (every change is marked "(coat_rig 11-18)"; staged/coat_film_maps.diff is the diff against the source):
//   1. opts.normalMap (a texture on TEXCOORD_1, tangent space, the TANGENT attribute's frame): the film's own normal in all
//      three passes is the baked one (the drape's folds), wherever the source read normalView (the T pass's view
//      cosine, the S pass's waves and flakes, the G pass's light);
//   2. bindingMaterial(B, { normalMap, glowMap, glow }): the bound edges and the collar on the same baked normals, and
//      their GLOWING OUTERMOST 3.5 mm (the design's 'piping') from the glow mask (TEXCOORD_1) instead of a strip of faces.
// Without opts.normalMap / glowMap every material is the source's, to the bit.
// THE SOURCE'S HEADER:
// coat_film.js: THE COATS' MATERIALS for the design round (coat design, the study, 11-11, Fable 5.2). A study module in
// my folder; nothing live. three r184 WebGPU / TSL, NodeMaterials only. Its numbers are ../coat_film.json (every
// constant with its reason) and the film's two tables ../data/coat_film_luts.json (scripts/c11_mixed_film.py): the
// scene hands both in.
//
// ALETHEIA'S FILM IS ONE FILM (the owner, 11-11: "it should not be half one color half the other color ... very
// importantly mixed blue and pink with iridescence between the too"). There is no pink film and no blue film here and
// no attribute that says which half a panel belongs to: every piece of film is the same laminate, a pink-tinted skin
// on each side of a dichroic core (COAT_STUDY.md B.1 and C; c11_mixed_film.py says what the core does). Its colour at
// a point depends on two things only: the angle it is seen at, and how thick the film is there.
//   lut_T  (cos of the view angle, thickness) -> what one sheet lets through          (linear sRGB)
//   lut_F0 (cos of the view angle, thickness) -> the base colour of what it mirrors   (three's metal: F0)
// THREE WAYS TO MIX (opts.mix), the lead's three:
//   'i'    the angle alone: the thickness is the nominal one everywhere
//   'ii'   + a slow drift of the thickness over each sheet (F.drift, pools F.drift_scale_m long): soft pools of pink
//          and of blue with violet between them, which move as the film bends
//   'iii'  (ii) + a fine pearl sparkle: a share of the surface is tiny tilted mirrors of the same layer
// THREE DRAWS PER PIECE OF FILM, none writes depth:
//   T  multiplies what is behind by the sheet's transmittance            (MeshBasicNodeMaterial, dst *= T)
//   S  adds what the sheet mirrors: the lights and the environment       (a metal whose colour is lut_F0, dst += S)
//   G  adds the film's own soft light where light falls on either side   (a diffuse + a back-lit lobe, dst += G):
//      a veil in the colour the film lets through THERE + the pink skins' fluorescence along the sheet
// Multiplying commutes and adding commutes, so layers of film need NO SORTING among themselves ('free'). What that
// gives up: a nearer sheet does not tint what a farther sheet mirrors and glows. 'sided' draws a piece's back faces
// first (T S G) and then its front faces (T S G): exact for a closed convex piece (a sleeve).
//
// WHERE IT COMES FROM: the 11-09 material round's coat_materials.js (human/aletheia/coats/material/engine/, read for
// what it learned about the material, never for the coat's design). KEPT from it: the idea (a thin sheet is a
// transmittance that multiplies what is behind it, plus the light the sheet itself sends back: draws that commute),
// the G-buffer identities, the shell's N.V clamp. CHANGED in this round:
//   1. ONE FILM instead of a pink dye and a blue dye; its colour from two computed tables instead of three's
//      single-layer iridescence (a single layer cannot change the BODY colour: it only tints the highlights).
//   2. THE BOUND EDGES AND SEAM TAPES ARE THEIR OWN OPAQUE MESH (bindingMaterial), drawn with the opaque world and
//      writing depth. In the old pack they were texels of the film (T = 0, no depth): a film layer behind a binding
//      still added its light on top of it, and a binding behind a film was not tinted by that film.
//   3. ONE DRAW PER PASS: forceSinglePass. three r184 draws a transparent DoubleSide material twice (back faces, then
//      front faces: Renderer.js renderObject); the blends commute, so the split bought nothing.
//   4. THE GLOW is its own draw, lit from both sides (three's MeshSSSNodeMaterial forward lobe for the far side).
//   5. SSR: the multiply pass scales the G-buffer's metalness by the film's transmittance, so the engine's
//      screen-space reflections (added after the scene pass, over whatever is metal in the G-buffer) do not paint an
//      untinted mirror over chrome that lies UNDER the film (her arms in the sleeves, her port rings, her buckles).
// REQUIRES a linear scene pass (a render target: the engine's auto-enhance), as before: straight to the canvas three
// would tone map each pass before its blend.
const THREE = globalThis.THREE;

// ------------------------------------------------------------------------------------------------ the film's tables
// L: data/coat_film_luts.json ({ cos, thickness, lut_T, lut_F0 }: lut[thickness][cos] = [r, g, b]). Two half-float
// textures, u = cos of the view angle, v = thickness over [thickness[0], thickness[last]]
export function filmLuts(L) {
    const nc = L.cos.length, nt = L.thickness.length, h = THREE.DataUtils.toHalfFloat;
    const make = (rows) => {
        const data = new Uint16Array(nc * nt * 4);
        for (let j = 0; j < nt; j++) {
            for (let i = 0; i < nc; i++) {
                const k = 4 * (j * nc + i), c = rows[j][i];
                data[k] = h(Math.max(0, c[0])); data[k + 1] = h(Math.max(0, c[1])); data[k + 2] = h(Math.max(0, c[2])); data[k + 3] = h(1);
            }
        }
        const t = new THREE.DataTexture(data, nc, nt, THREE.RGBAFormat, THREE.HalfFloatType);
        t.minFilter = THREE.LinearFilter; t.magFilter = THREE.LinearFilter; t.generateMipmaps = false;
        t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
        t.colorSpace = THREE.NoColorSpace;
        t.needsUpdate = true;
        return t;
    };
    // G (11-11 07:2x): the fluorescent dye's own light toward the viewer, per unit of light falling on the face (c11's
    // lut_G, from coat_film.json fluor_*); older tables have none
    return { T: make(L.lut_T), F0: make(L.lut_F0), G: L.lut_G ? make(L.lut_G) : null, nc, nt, t0: L.thickness[0],
        t1: L.thickness[nt - 1] };
}

// ------------------------------------------------------------------------------------------------ helpers
// a film mesh's own data: the attribute `layers` (1 one sheet, 2 a doubled piece: a cuff band, a collar); a mesh
// without it is opts.layers (1)
function filmLayers(geometry, opts) {
    const { attribute, float } = THREE;
    return geometry.getAttribute('layers') ? attribute('layers', 'float') : float(opts.layers ?? 1.0);
}

// THE THICKNESS over the sheet, as a factor of the nominal film (uv in METRES along the sheet). mix 'i': 1 everywhere.
// 'ii' / 'iii': a slow drift, pools F.drift_scale_m long and 2.5 x longer along the film's machine direction (v).
// opts.forceT (a number) overrules it (the chart's thin and thick strips)
function filmThickness(F, opts) {
    const { uv, float, vec3, sin } = THREE;
    if (opts.forceT != null) return float(opts.forceT);
    if ((opts.mix || 'i') === 'i' || !(F.drift > 0)) return float(1.0);
    const p = uv().add(float(opts.seed ?? 0.0).mul(3.7));
    const sx = 1.0 / F.drift_scale_m, sy = sx / (F.drift_aniso ?? 2.5);
    let n;
    if (THREE.mx_noise_float) {
        // two octaves of Perlin noise (about -0.8 .. 0.8 together), domain-warped a little so the pools are not blobs
        const q = vec3(p.x.mul(sx), p.y.mul(sy), float(opts.seed ?? 0.0).add(0.37));
        const w = THREE.mx_noise_float(q.mul(0.6).add(vec3(11.3, 4.1, 0.0)));
        n = THREE.mx_noise_float(q.add(vec3(w.mul(0.6), w.mul(-0.4), 0.0))).mul(0.85)
            .add(THREE.mx_noise_float(q.mul(2.3).add(vec3(5.2, 1.3, 2.8))).mul(0.3));
    } else {
        n = sin(p.x.mul(sx * 5.1).add(sin(p.y.mul(sy * 4.3)).mul(1.7))).mul(0.55).add(sin(p.x.mul(sx * 2.2).sub(p.y.mul(sy * 3.1)).add(1.3)).mul(0.35));
    }
    // POOLS (F.drift_gain; 11-11 05:45): the noise goes through an S-curve that is flat at both ends, so most of a
    // sheet lies near the thin end or the thick end and the change between them is a band: pools of one colour and
    // of the other with the third between them. Without it (the plain clamp below) the thickness sat within a third
    // of the drift nearly everywhere and a face-on sheet was one colour. F.drift_bias leans the sheet's share toward
    // the thick end (in units of the noise)
    let shaped = n.mul(1.25).clamp(-1.0, 1.0);
    if (F.drift_gain != null && THREE.smoothstep) {
        const e = 1.0 / F.drift_gain;
        shaped = THREE.smoothstep(float(-e), float(e), n.add(float(F.drift_bias ?? 0.0))).mul(2.0).sub(1.0);
    }
    return float(1.0).add(shaped.mul(float(F.drift)));
}

// the tables' coordinate for a view cosine and a thickness factor
function lutUV(LUT, cosV, thick) {
    const { vec2 } = THREE;
    const u = cosV.clamp(0.0, 1.0).mul((LUT.nc - 1) / LUT.nc).add(0.5 / LUT.nc);
    const v = thick.sub(LUT.t0).div(LUT.t1 - LUT.t0).clamp(0.0, 1.0).mul((LUT.nt - 1) / LUT.nt).add(0.5 / LUT.nt);
    return vec2(u, v);
}

// THE PEARL (mix 'iii'): the shading normal of the mirror pass. A share F.sparkle of the cells (F.sparkle_size_mm) is a
// flake: a tiny mirror of the same layer leaning up to F.sparkle_tilt_deg off the film's face, so it mirrors another
// part of the room and takes the table's colour at ITS angle. Where a pixel covers more than a cell the flakes fade
// out (a minified field of sparkles aliases into crawling noise: the weave tile's rule, COAT_STUDY C)
function pearlNormal(F, base) {
    const { uv, float, vec3, floor, fwidth, hash } = THREE;
    const cells = uv().mul(1000.0 / F.sparkle_size_mm);
    const id = floor(cells);
    const seed = id.x.add(id.y.mul(1973.0)).add(7.0);
    const isFlake = hash(seed).lessThan(float(F.sparkle)).select(float(1.0), float(0.0));
    const tilt = vec3(hash(seed.add(17.0)), hash(seed.add(41.0)), hash(seed.add(89.0))).mul(2.0).sub(1.0);
    const fp = fwidth(cells);
    const fade = float(1.0).sub(fp.x.max(fp.y).sub(0.45).div(0.55)).clamp(0.0, 1.0);
    const k = Math.tan(F.sparkle_tilt_deg * Math.PI / 180);
    return { normal: base.add(tilt.mul(isFlake.mul(fade).mul(k))).normalize(), fade };
}

// THE FILM'S WAVINESS (the mirror pass's normal): a calendered film is never optically flat. Its faces lean by a few
// degrees in slow waves (F.waviness: the slope; F.waviness_scale_m: their length, 2.2 x longer along the machine
// direction), so a flat panel's mirror image of the room breaks into soft streaks and the colour, which follows the
// angle, wobbles with them. (The first engine look, 11-11 05:00: a flat sheet with a flat normal mirrored one patch of
// the studio, evenly: it read as a sheet of coloured gel, not as film.) The geometry is not moved.
function wavyNormal(F, opts, base = null) {
    const { uv, float, vec3 } = THREE;
    const normalView = base || THREE.normalView;                // (coat_rig 11-18) the baked normal when there is one
    if (!(F.waviness > 0) || !THREE.mx_noise_vec3 || opts.noWaves) return normalView;
    const s = float(opts.seed ?? 0.0);
    const p = uv().mul(1.0 / F.waviness_scale_m).add(s.mul(1.9));
    const w = THREE.mx_noise_vec3(vec3(p.x, p.y.div(2.2), s.add(2.1)));
    return normalView.add(vec3(w.x, w.y, 0.0).mul(float(F.waviness))).normalize();
}

// (coat_rig 11-18) the film's own normal: the baked one (tangent space on TEXCOORD_1) or the geometry's
function baseNormal(opts) {
    if (!opts.normalMap) return THREE.normalView;
    return THREE.normalMap(THREE.texture(opts.normalMap, THREE.uv(1)));
}

function passMesh(geometry, material, order, name) {
    const m = new THREE.Mesh(geometry, material);
    m.renderOrder = order;
    m.castShadow = false;
    m.receiveShadow = true;
    m.name = name;
    m.userData.noClippingCheck = true;
    m.userData.filmPass = name.slice(-1);
    return m;
}

function gbufferIdentity(mat, kind, metalScale) {
    // the engine's scene pass writes normal and metal / roughness beside the colour, each attachment following the
    // material's blend: under the multiply the identity is 1, under the add 0. metalScale (the multiply pass only):
    // what the metalness under the film is multiplied by (change 5 at the top)
    if (globalThis._noAutoEnhance) return;
    const { mrt, vec4, float } = THREE;
    if (kind === 'T') mat.mrtNode = mrt({ normal: vec4(1.0), metalrough: vec4(metalScale ?? float(1.0), 1.0, 1.0, 1.0) });
    else mat.mrtNode = mrt({ normal: vec4(0.0), metalrough: vec4(0.0) });
}

function multiplyBlend(m) {
    m.transparent = true;
    m.depthWrite = false;
    m.toneMapped = false;
    m.blending = THREE.CustomBlending;
    m.blendEquation = THREE.AddEquation;
    m.blendSrc = THREE.ZeroFactor;
    m.blendDst = THREE.SrcColorFactor;
    m.blendEquationAlpha = THREE.AddEquation;
    m.blendSrcAlpha = THREE.ZeroFactor;
    m.blendDstAlpha = THREE.OneFactor;
}

function addBlend(m) {
    m.transparent = true;
    m.depthWrite = false;
    m.blending = THREE.AdditiveBlending;
    m.premultipliedAlpha = true;                                // One / One: the lit result added as it is
}

// (THE DESIGN ROUND, run 14, 11-13) A THIN FILM IS LIT FROM THE SIDE THE EYE IS ON. Both faces of the sheet are the same
// surface, so the lighting normal of the mirror and glow draws is turned toward the eye wherever it points away, as the
// CPU preview (d17) has always done. Without it a sheet whose triangles wind against their normals (the coat's backs
// and sleeves did, 11-13) is a DoubleSide "back face", three flips its normal into the coat, and the mirror draw sees
// N.V < 0: its Fresnel term goes to 1 and the sheet mirrors the room in white (engine stills lgTS, 11-13 16:16)
function faceEye(n) {
    const { float, positionViewDirection } = THREE;
    return n.mul(n.dot(positionViewDirection).lessThan(float(0.0)).select(float(-1.0), float(1.0)));
}

// the three materials of one face set (side: THREE.DoubleSide for the order-free film, BackSide / FrontSide for 'sided')
function filmMaterials(geometry, F, LUT, opts, side) {
    const { float, vec3, texture, positionViewDirection, luminance } = THREE;
    const normalView = baseNormal(opts);                        // (coat_rig 11-18) the baked normal, or the geometry's
    const layers = filmLayers(geometry, opts);
    const thick = filmThickness(F, opts);
    const mix = opts.mix || 'i';
    // pass T: what the sheet lets through (the film's own face, never a flake's) -------------------------------
    const cosV = normalView.dot(positionViewDirection).abs().clamp(1.0e-3, 1.0);
    let T1 = texture(LUT.T, lutUV(LUT, cosV, thick)).rgb;
    // (THE DESIGN ROUND, run 14, 11-13; absent or 0 = the study's film) F.dye_pool: the magenta dye's green cut follows
    // the laminate's thickness, as glow_pool has its light follow it (a calendered laminate thins skins and core
    // together): in the thin, blue-passing lanes the green comes back by this share (w 0 at the thinnest, 1 at the
    // thickest), so the blue state is a clear CYAN-blue (the lead, 17:16: "her blue is a clear, bright cyan-blue; ours
    // turns indigo-violet in the shadowed panels": two layers of a 0.46-green blue over the grey are indigo)
    if (F.dye_pool > 0 && F.drift > 0) {
        const w = thick.sub(1.0 - F.drift).div(2.0 * F.drift).clamp(0.0, 1.0);
        const back = float(F.dye_pool).mul(float(1.0).sub(w));
        T1 = vec3(T1.r, T1.g.add(float(1.0).sub(T1.g).mul(back).mul(T1.b)), T1.b);
    }
    const T = T1.pow(vec3(layers)).mul(float(1.0).sub(float(F.haze).mul(layers)).max(0.0));
    const mT = new THREE.MeshBasicNodeMaterial();
    mT.colorNode = opts.debugT ? vec3(1.0) : T;
    multiplyBlend(mT);
    mT.side = side;
    mT.forceSinglePass = true;
    gbufferIdentity(mT, 'T', opts.keepMetalUnder ? null : luminance(T).clamp(0.0, 1.0));
    // pass S: what the sheet mirrors. A metal: its base colour IS its reflectance face-on (lut_F0), three's Schlick
    // term adds the plain faces' white toward grazing ----------------------------------------------------------
    const mS = new THREE.MeshPhysicalNodeMaterial();
    let rough = float(F.roughness);
    let nS = faceEye(wavyNormal(F, opts, normalView));          // the film's own slow waves, on the eye's side
    if (mix === 'iii' && F.sparkle > 0) {
        const P = pearlNormal(F, nS);
        nS = P.normal;
        // beyond the distance where single flakes show, the pearl is a soft widening of the highlight
        rough = rough.add(float(1.0).sub(P.fade).mul(F.sparkle * 2.0));
    }
    if (nS !== THREE.normalView) mS.normalNode = nS;
    // the mirror's colour at the angle of the face that mirrors (the wave's, the flake's)
    const cosS = nS.dot(positionViewDirection).abs().clamp(1.0e-3, 1.0);
    let F0 = texture(LUT.F0, lutUV(LUT, cosS, thick)).rgb;
    // (THE DESIGN ROUND, 11-11 14:2x, Opus 5.5; a neutral hook: absent or 0 = the study's film, unchanged) F.mirror_neutral
    // draws the coloured mirror toward its own grey by that share. The film mirrors the complement of what it passes
    // (blue pools mirror violet-pink), and over her black suit that violet showed on EVERY pool: the CPU tries of the
    // design round counted 44-76 % violet on her coat (design_NOTES.md, run 4)
    if (F.mirror_neutral > 0) F0 = THREE.mix(F0, vec3(luminance(F0)), float(F.mirror_neutral));
    // a doubled piece: the second sheet's mirror seen through the first, there and back
    const F0n = F0.mul(float(1.0).add(layers.sub(1.0).mul(luminance(T1.mul(T1))))).min(vec3(1.0));
    mS.colorNode = opts.noSheen ? vec3(0.04) : F0n;
    mS.metalnessNode = float(1.0);
    mS.roughnessNode = rough;
    addBlend(mS);
    mS.side = side;
    mS.forceSinglePass = true;
    gbufferIdentity(mS, 'L');
    // pass G: THE FILM'S OWN SOFT LIGHT, a diffuse with no highlight of its own + the forward lobe for light arriving
    // on the far side. It is what the film looks like over her black suit, where nothing comes through from behind.
    // (The first engine look, 11-11 05:00, had ONE fixed pink here: every swatch over her suit was one flat plum
    // sheet with no blue anywhere.) Its parts:
    //   the LUSTRE  F.lustre: the pearl of the dichroic core, a broad soft lobe IN THE COLOUR THE FILM MIRRORS at that
    //               point and angle (lut_F0): violet on the nominal film, blue where it is thick, pink where it is
    //               thin or slanted. A real interference layer shows the colour it MIRRORS over a dark ground and the
    //               colour it LETS THROUGH over a light one
    //   the GLOW    the pink skins' fluorescence: F.glow_flat everywhere + F.glow by the path through the film (none
    //               face-on, most along the sheet: a fold's flank, a sleeve's side, an edge)
    //   (F.veil     a veil in the colour the film LETS THROUGH, to the power F.veil_power: tried on the CPU preview at
    //               05:40, maroon and navy over her suit; 0 unless coat_film.json sets it)
    // Pink glow + violet lustre is her pictures' plum over the black suit; glow + pink lustre the hot pink pools
    //   (11-11 07:2x, the sixth run) the DYE'S LIGHT toward the viewer is its own table (LUT.G, c11 from fluor_*),
    //   and the lustre is the stack's own haze (F.lustre) in every mix + the pearl flakes' lobe (F.pearl_lustre) in 'iii'
    let mG = null;
    const lustreK = (F.lustre ?? 0.0) + (mix === 'iii' ? (F.pearl_lustre ?? 0.0) : 0.0);
    if ((F.veil > 0 || F.glow > 0 || F.glow_flat > 0 || lustreK > 0 || LUT.G) && !opts.noGlow) {
        const Base = THREE.MeshSSSNodeMaterial || THREE.MeshPhysicalNodeMaterial;
        mG = new Base();
        const Vp = T1.max(vec3(1.0e-4)).pow(vec3(F.veil_power ?? 3.0));
        const edge = float(1.0).div(cosV).sub(1.0).clamp(0.0, F.glow_edge_max ?? 3.0);
        // (THE DESIGN ROUND, run 14, 11-13; absent = the study's even veil) F.veil_face: the share of the veil where the
        // film FACES the eye, rising to the whole veil as the path through the sheet lengthens (1/cos - 1 reaching
        // F.veil_span): a film's scattered body colour gathers at grazing angles, in its folds and at its edges, and a
        // face-on sheet stays clear (the lead, 17:16: through her film the black suit reads crisp and dark; through ours
        // it went milky over the legs, the sleeves and the lower back)
        const vFace = F.veil_face ?? 1.0;
        const vk = vFace >= 1.0 ? float(1.0)
            : float(vFace).add(float(1.0 - vFace).mul(edge.div(float(F.veil_span ?? 1.0)).clamp(0.0, 1.0)));
        const veil = Vp.div(Vp.r.max(Vp.g).max(Vp.b)).mul(float(F.veil ?? 0.0)).mul(vk);
        const lustre = texture(LUT.F0, lutUV(LUT, cosV, thick)).rgb.mul(float(lustreK));
        let fluor = vec3(...F.glow_colour).mul(float(F.glow_flat ?? 0.0).add(float(F.glow ?? 0.0).mul(edge)));
        if (LUT.G) fluor = fluor.add(texture(LUT.G, lutUV(LUT, cosV, thick)).rgb);
        // (THE DESIGN ROUND, 11-11 14:2x; a neutral hook: absent or 0 = the study's film) F.glow_pool: the pink skins'
        // light follows the laminate's thickness (a calendered laminate thins skins and core together: the thick,
        // pink-passing pools carry more dye than the thin, blue-passing ones): w 0 at the thinnest, 1 at the thickest,
        // mixed in by this share. Without it the pink glow lay over the blue pools too and turned them violet
        if (F.glow_pool > 0 && F.drift > 0) {
            const w = thick.sub(1.0 - F.drift).div(2.0 * F.drift).clamp(0.0, 1.0);
            fluor = fluor.mul(float(1.0 - F.glow_pool).add(w.mul(F.glow_pool)));
        }
        const glow = veil.add(lustre).add(fluor).mul(layers);
        mG.normalNode = faceEye(normalView);                    // (run 14) lit on the eye's side, as the mirror
        mG.colorNode = glow;
        mG.roughnessNode = float(1.0);
        mG.metalnessNode = float(0.0);
        mG.specularIntensityNode = float(0.0);                  // the highlights are pass S's
        if (Base === THREE.MeshSSSNodeMaterial && F.glow_backlit > 0) {
            mG.thicknessColorNode = glow.mul(float(F.glow_backlit));
            mG.thicknessDistortionNode = float(0.25);
            mG.thicknessPowerNode = float(1.5);
            mG.thicknessScaleNode = float(1.0);
            mG.thicknessAmbientNode = float(0.0);
            mG.thicknessAttenuationNode = float(1.0 / Math.PI);
        }
        addBlend(mG);
        mG.side = side;
        mG.forceSinglePass = true;
        gbufferIdentity(mG, 'L');
    }
    return [mT, mS, mG];
}

// THE FILM: the meshes to add for one piece of it. opts.order 'free': 3 draws, any order among films (T at `ro`, S
// and G after it). 'sided': 6 draws, back faces then front faces; give a nearer part a higher `ro`. 'sorted': sided,
// every draw at the SAME `ro`: three then sorts the PARTS far to near by their geometry's centre and keeps one
// part's draws in the order they were made
export function filmPasses(geometry, F, LUT, opts = {}) {
    const ro = opts.ro ?? 10;
    const name = opts.name || 'film';
    const order = opts.order || 'free';
    const out = [];
    const add = (mats, base, step, tag) => {
        mats.forEach((mat, i) => { if (mat) out.push(passMesh(geometry, mat, base + step * i, `${name}${tag}_${'TSG'[i]}`)); });
    };
    if (order === 'free') {
        add(filmMaterials(geometry, F, LUT, opts, THREE.DoubleSide), ro, 1, '');
        return out;
    }
    const k = order === 'sorted' ? 0 : 1;
    add(filmMaterials(geometry, F, LUT, opts, THREE.BackSide), ro, k, '_back');
    add(filmMaterials(geometry, F, LUT, opts, THREE.FrontSide), ro + 3 * k, k, '_front');
    return out;
}

// ------------------------------------------------------------------------------------------------ what the engine offers without the passes (for the comparison stills)
// 'alpha': the engine guide's glass recipe (tools-guides/stack-notes.md: alpha opacity carries the see-through), one
// blended draw. 'transmission': three's own transmission, no opacity. Both in the film's face-on pink
export function plainGlassMaterial(F, LUT_json, kind) {
    const { float, vec3 } = THREE;
    const mid = LUT_json.lut_T[(LUT_json.thickness.length - 1) >> 1];
    const c = mid[mid.length - 1];
    const m = new THREE.MeshPhysicalNodeMaterial();
    m.colorNode = vec3(c[0], c[1], c[2]);
    m.roughnessNode = float(F.roughness);
    m.metalnessNode = float(0.0);
    m.ior = F.ior;
    m.side = THREE.DoubleSide;
    if (kind === 'alpha') {
        m.transparent = true;
        m.opacity = 0.3;
        m.transmission = 0.9;
        m.thickness = 0.0004;
    } else {
        m.transmission = 1.0;
        m.thickness = 0.0004;
    }
    return m;
}

// ------------------------------------------------------------------------------------------------ the bound edges
// an opaque coated tape folded round every edge of the film, and the flat tape over its seams: ordinary opaque
// geometry (it writes depth and casts a shadow). Fluorescent pink: its albedo passes 1 in red (her pictures' edges
// read brighter than the background behind them)
export function bindingMaterial(B, opts = {}) {
    const { float, vec3 } = THREE;
    const m = new THREE.MeshPhysicalNodeMaterial();
    m.colorNode = vec3(...(opts.colour || B.colour));
    m.roughnessNode = float(B.roughness);
    m.metalnessNode = float(0.0);
    // (THE DESIGN ROUND, run 14, 11-13; absent or 0 = the study's tape) B.emissive: a FLUORESCENT pink vinyl sends back
    // more pink than falls on it in pink (it turns the light's blue and green into pink): her pictures' bound edges glow
    // as neon in 10 of 10, with bloom in 4; as a plain albedo the strip read flat pastel beside them
    if (B.emissive > 0) m.emissiveNode = vec3(...(opts.colour || B.colour)).mul(float(B.emissive));
    // (coat_rig 11-18) THE LOW: the baked normals (the drape's folds under the strip), and the GLOW MASK: where it is 1 the
    // strip is the design's glowing piping (opts.glow: { colour, intensity, roughness }: the tube material's numbers),
    // where it is 0 the binding as above, between them a mix (the mask is antialiased at its texel)
    if (opts.normalMap) m.normalNode = THREE.normalMap(THREE.texture(opts.normalMap, THREE.uv(1)));
    if (opts.glowMap && opts.glow) {
        const g = THREE.texture(opts.glowMap, THREE.uv(1)).r;
        const gc = vec3(...opts.glow.colour);
        const base = vec3(...(opts.colour || B.colour));
        m.colorNode = THREE.mix(base, gc.mul(0.25), g);
        m.emissiveNode = THREE.mix(base.mul(float(B.emissive > 0 ? B.emissive : 0.0)), gc.mul(float(opts.glow.intensity)), g);
        m.roughnessNode = THREE.mix(float(B.roughness), float(opts.glow.roughness ?? 0.08), g);
    }
    m.side = THREE.DoubleSide;
    m.name = 'binding';
    return m;
}

// ------------------------------------------------------------------------------------------------ Aporia's shell
// an opaque coated nylon: the dye, the weave's normal at its real pitch (uv in METRES), matte with a soft sheen.
// The sheen is three's lobe with the shading normal kept a hair on the eye's side (runtime/beetle_cuticle.js's fix
// of the lobe's NaN, as the 11-09 fabric: N.V >= 1e-3). weaveTex: a tile loaded through loadImageTexture (the
// engine's image path: a tile fetched through the glb parser never reaches the screen, 11-09 STUDY 3.2)
export function shellMaterial(S, weaveTex, opts = {}) {
    const { float, vec3, uv, texture, fwidth, normalMap, normalView, positionViewDirection, mix } = THREE;
    const m = new THREE.MeshPhysicalNodeMaterial();
    const dye = vec3(...(opts.colour || S.dye));
    m.colorNode = dye;
    let nrm = normalView;
    if (weaveTex && !opts.noWeave) {
        weaveTex.colorSpace = THREE.NoColorSpace;
        weaveTex.wrapS = weaveTex.wrapT = THREE.RepeatWrapping;
        weaveTex.anisotropy = 8;
        const wuv = uv().mul(1000.0 / S.weave_tile_mm);
        const nd = texture(weaveTex, wuv).xyz.mul(2.0).sub(1.0);
        // the yarns fade where a pixel covers more than a sixth of a tile (B2's rule: a minified tile aliases)
        const fp = fwidth(wuv);
        const fade = float(1.0).sub(fp.x.max(fp.y).sub(0.04).div(0.12)).clamp(0.0, 1.0);
        nrm = normalMap(vec3(nd.xy.mul(float(S.weave_strength)).mul(fade), 1.0).normalize().mul(0.5).add(0.5));
    }
    nrm = nrm.add(positionViewDirection.mul(float(1.0e-3).sub(nrm.dot(positionViewDirection)).max(0.0))).normalize();
    m.normalNode = nrm;
    m.roughnessNode = float(S.roughness);
    m.metalnessNode = float(0.0);
    if (!opts.noSheen) {
        m.sheenNode = mix(dye.mul(1.6).min(vec3(1.0)), vec3(1.0), float(S.sheen_white)).mul(float(S.sheen));
        m.sheenRoughnessNode = float(S.sheen_roughness);
    }
    m.side = THREE.DoubleSide;
    m.name = 'aporia_shell';
    return m;
}

// her name plate: METAL (the owner, 11-10: metal is metal: metallic 1), Aporia's dark carbon steel, the raised letters and
// the worn edges bright bare steel. normalTex / maskTex: c00_plate.py (R letters, G rivets, B edges)
export function plateMaterial(P, normalTex, maskTex) {
    const { float, vec3, uv, texture, mix, normalMap } = THREE;
    for (const t of [normalTex, maskTex]) { t.colorSpace = THREE.NoColorSpace; t.anisotropy = 8; }
    const mk = texture(maskTex, uv());
    const bright = mk.r.max(mk.g).max(mk.b.mul(float(P.edge_wear)));
    const m = new THREE.MeshStandardNodeMaterial();
    m.colorNode = mix(vec3(...P.steel), vec3(...P.letters), bright.clamp(0.0, 1.0));
    m.metalnessNode = float(1.0);
    m.roughnessNode = mix(float(P.roughness), float(P.letters_roughness), mk.r.max(mk.g));
    m.normalNode = normalMap(texture(normalTex, uv()));
    m.name = 'aporia_plate';
    return m;
}
