// claudesona_face.js — the claudesona's face as digi modelled it (claude_suit.vrm / claude_suit_wardrobe.vrm): a
// lipsync driver built around how its mouth actually works, and an emotion/gaze track keyed to lyrics or dialogue.
//
//   const { installSuitMouth, makeSuitMouth, makeFaceTrack, mergeMax } = await import(new URL('claudesona_face.js', EIDOVERSE_DIR).href);
//   const face = installSuitMouth(vrm);                    // once, after load: owns the 3 face plates' morphs
//   const mouth = makeSuitMouth({ inputMax: 0.35 });       // 0.35 for lipsync.py timelines, 1 for voicebox visemes
//   // per frame, in renderFrame(t):
//   const w = mouth.update(t, visemes[Math.floor(t * visemeFps)]);      // {aa, ih, ou, ee, oh} → raw morph weights
//   face.set(mergeMax(w, emotions.at(t)));                              // written at render time (onBeforeRender)
//
// Guide: AGENTS.md ("claude_suit.vrm — mouth + wardrobe recipes").
// WHY a driver and not a scaled pose: the black mouth is a cavity plate pushed THROUGH the white face by the
// `show MMD mouth` morph, and the reveal is a threshold, not a fade: below ~1.0 the cavity sits behind the face (only
// the painted line shows), above it the cavity pops out and grows. Scaling a viseme pose by loudness therefore makes
// the black part blink out on every consonant dip — one film measured it visible 71 of 255 sung seconds, 716 on/off
// flips. The driver keeps ONE openness signal (fast attack, slow release), opens and closes with hysteresis, HOLDS
// the reveal at `reveal` (1.25) while open and scales only the vowel's shape morphs, and changes the vowel pose only at
// a syllable dip or when the new vowel clearly leads (no mid-vowel pops). Result: visible through the whole phrase,
// open/close only at phrase edges.

const S = 'show MMD mouth';
// the render-verified viseme poses (weights above 1 are intentional and tear-free up to ~2)
export const SUIT_VISEMES = {
    aa: { [S]: 1.6, 'あ': 2.0, JawOpen: 1.5, A: 0.5 },   // big open
    oh: { [S]: 1.2, LipFunnel: 1.0, 'お': 0.8 },          // rounded drop
    ou: { [S]: 0.8, LipPucker: 1.2 },                     // tight pucker
    ee: { [S]: 1.0, 'え': 1.5 },                          // wide + shallow
    ih: { [S]: 0.9, 'い': 1.2 },                          // flat slit
};
const VOWELS = ['aa', 'ih', 'ou', 'ee', 'oh'];

// Own the face plates' morphs: every frame at render time, zero them and write `weights` (so the VRM expression
// pass can't leave stale values, and nothing overwrites ours). Zeroing also removes auto-blink: add `Blink` yourself.
export function installSuitMouth(vrm) {
    const plates = [];
    let weights = {};
    vrm.scene.traverse((o) => { if (o.morphTargetDictionary && (S in o.morphTargetDictionary)) plates.push(o); });
    for (const p of plates) p.onBeforeRender = () => {
        const inf = p.morphTargetInfluences, d = p.morphTargetDictionary;
        inf.fill(0);
        for (const [nm, w] of Object.entries(weights)) if (nm in d) inf[d[nm]] = w;
    };
    return { plates, set(w) { weights = w || {}; }, get weights() { return weights; } };
}

// The lipsync driver. `update(t, frame)` takes the current viseme frame ({aa, ih, ou, ee, oh}, any may be missing)
// and returns raw morph weights for the plates. Time-based smoothing: independent of the render fps.
export function makeSuitMouth({ inputMax = 1, reveal = 1.25, attack = 0.03, release = 0.11, openAt = 0.18,
    closeAt = 0.08, switchDip = 0.3, switchLead = 0.25, blinkEvery = 4.3 } = {}) {
    const M = { open: 0, isOpen: false, pose: null, t: null };
    return {
        state: M,
        update(t, frame = {}) {
            let best = null, bv = 0;
            const val = (k) => Math.min(1, (frame[k] || 0) / inputMax);
            for (const k of VOWELS) if (val(k) > bv) { bv = val(k); best = k; }
            const dt = M.t === null ? 1 / 60 : Math.min(0.1, Math.max(1 / 240, t - M.t));
            M.t = t;
            M.open += (bv - M.open) * (1 - Math.exp(-dt / (bv > M.open ? attack : release)));
            if (!M.isOpen && M.open > openAt) M.isOpen = true;
            else if (M.isOpen && M.open < closeAt) M.isOpen = false;
            const cur = M.pose ? val(M.pose) : 0;
            if (best && (!M.pose || (best !== M.pose && (cur < switchDip || bv > cur + switchLead)))) M.pose = best;
            const out = {};
            if (M.isOpen && M.pose) {
                const s = 0.3 + 0.7 * Math.min(1, M.open);
                for (const [nm, w] of Object.entries(SUIT_VISEMES[M.pose])) out[nm] = w * s;
                out[S] = Math.max(reveal, SUIT_VISEMES[M.pose][S] * s);
            }
            if (blinkEvery > 0) {                             // a blink every few seconds, never mid-word
                const ph = (t % blinkEvery) / 0.18;
                if (ph < 1 && !M.isOpen) out.Blink = Math.sin(ph * Math.PI);
            }
            return out;
        },
    };
}

// Emotion + gaze, keyed to WORDS and sections rather than seconds, so re-timing the audio can't desync a feeling.
// TL = { sections: [{name, t0, t1}], captions: [{text, t0, t1}] } (the shape voicebox/song timelines use).
// sectionBase: { sectionName: {smile, frown, wide, blush, soft, down, up, jaw} } — the resting feeling of a section.
// lineCues: [[/regex on the caption text/, {smile: 0.6, blush: 0.5}], ...] — a feeling per line, eased in and out.
// closeAfterLast: the eyes close slowly after the last caption (a day's eye closing at dusk); false to disable.
// Channel → morph (render-measured on this face):
//   smile  Smile + MouthSmileLeft/Right: the corners curl up smoothly with the value (Smile alone barely moves)
//   frown  MouthFrown, smooth · wide EyeWide, subtle · down/up EyeLookDown*/EyeLookUp*, subtle
//   soft   EyeClosedLeft/Right as given: up to ~0.5 the eyes only SHRINK to small dots; 0.7–0.9 flattens them into
//          content, sleepy slits; 1 closes them. Use 0.75–0.85 for a soft look.
//   blush  a SWITCH: the blush is a plate revealed like the mouth (hidden below Blush ≈ 0.75), so a scaled weight would
//          never show. blush ≥ 0.3 shows it (Blush 0.85–1.15, a little fuller with the value); below 0.3, none.
//   jaw    a SWITCH for a silent open mouth: jaw ≥ 0.15 reveals the cavity (show MMD mouth at the driver's 1.25) with
//          JawOpen 1.5 × jaw; below, the painted line.
const MORPHS = {
    smile: ['Smile', 'MouthSmileLeft', 'MouthSmileRight'], frown: ['MouthFrown'], wide: ['EyeWide'],
    soft: ['EyeClosedLeft', 'EyeClosedRight'], down: ['EyeLookDownLeft', 'EyeLookDownRight'],
    up: ['EyeLookUpLeft', 'EyeLookUpRight\t'],            // (digi's morph name carries a tab)
};
const SWITCHES = {
    blush: (v) => (v >= 0.3 ? { Blush: 0.85 + 0.3 * Math.min(1, v) } : {}),
    jaw: (v) => (v >= 0.15 ? { [S]: 1.25, JawOpen: 1.5 * Math.min(1, v) } : {}),
};
// Merge weight dicts by per-morph maximum (a lipsync pose and an emotion both may drive the same morph).
export function mergeMax(...ws) {
    const out = {};
    for (const w of ws) for (const [k, v] of Object.entries(w || {})) out[k] = Math.max(out[k] || 0, v);
    return out;
}
const smooth = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export function makeFaceTrack(TL, { sectionBase = {}, lineCues = [], closeAfterLast = true } = {}) {
    const sections = TL.sections || [];
    const cues = [];
    for (const c of TL.captions || []) {
        const hit = lineCues.find(([re]) => re.test(c.text));
        if (hit) cues.push({ t0: c.t0, t1: c.t1, f: hit[1] });
    }
    const lastWord = (TL.captions || []).length ? Math.max(...TL.captions.map((c) => c.t1)) : Infinity;
    return {
        at(t) {
            const sec = sections.find((s) => t >= s.t0 && t < s.t1) || sections[sections.length - 1];
            const f = { ...((sec && sectionBase[sec.name]) || {}) };
            for (const c of cues) {
                const w = smooth(c.t0 - 0.25, c.t0 + 0.4, t) * (1 - smooth(c.t1 + 0.3, c.t1 + 0.9, t));
                if (w <= 0) continue;
                for (const [k, v] of Object.entries(c.f)) f[k] = (f[k] || 0) * (1 - w) + v * w;
                for (const k of Object.keys(f)) if (!(k in c.f)) f[k] *= 1 - 0.6 * w;
            }
            if (closeAfterLast) {
                const dusk = smooth(lastWord - 3.5, lastWord + 1.5, t);
                if (dusk > 0) { f.soft = Math.max(f.soft || 0, 0.92 * dusk); f.smile = Math.max(f.smile || 0, 0.35); }
            }
            const out = {};
            for (const [k, v] of Object.entries(f)) {
                for (const m of MORPHS[k] || []) out[m] = Math.max(out[m] || 0, v);
                for (const [m, w] of Object.entries(SWITCHES[k]?.(v) || {})) out[m] = Math.max(out[m] || 0, w);
            }
            return out;
        },
    };
}
