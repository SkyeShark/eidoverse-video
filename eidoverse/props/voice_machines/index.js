// eidoverse/props/voice_machines/index.js — eight historical voice machines, 1939 → 2001, built by name.
//
// Dynamic ESM (scene scripts are eval'd, so import inside setup()):
//   const VM = await import(new URL('props/voice_machines/index.js', EIDOVERSE_DIR).href);
//   const voder = await VM.buildMachine('voder', THREE);          // → { group, parts, update(t, state), dispose() }
//   scene.add(voder.group);
//   // per frame: voder.update(t, { power: 1, voice: 0..1 })
//
// Every module can also be imported on its own (props/voice_machines/<name>.js exports build(THREE, opts)).
// Assets live in eidoverse/assets/models/voice_machines/ (README.md, SOURCES.md) and are resolved from the
// modules' own URLs, so the working directory does not matter. Guide: tools-guides/props-and-sets.md.
//
// All machines: metres, +Y up, resting on y = 0, front facing +Z, deterministic in t. `footprint` is the
// measured bounding box [width x, height y, depth z] of the built group (metres) and `center` its XZ centre
// offset from the origin (add its negation to group.position to centre the machine on a pedestal).

export const MACHINES = {
    voder: {
        year: 1939, title: 'Bell Labs Voder (New York World\'s Fair)', era: 1,
        text: null, drive: '{ voice, power } or { keys[10], wrist, stops[3], quiet, pedal, level, power }',
        footprint: [1.28, 1.70, 1.32], center: [0.0, -0.32],
    },
    mainframe: {
        year: 1961, title: 'IBM 7090-era computer room (the Bell Labs "Daisy Bell")', era: 1,
        text: null, drive: '{ tapeSpeed | tapeStop | tapePos, voice, power } — call in time order',
        footprint: [4.58, 1.87, 2.81], center: [0.0, 0.64],
    },
    teletype: {
        year: 1966, title: 'Teletype ASR-33 on its pedestal (ELIZA)', era: 1,
        text: 'update(t, { text, nChars }) or parts.paper.setText(fullText, nChars)', drive: '{ text, nChars, voice, power }',
        footprint: [0.60, 1.07, 0.76], center: [0.0, -0.12],
    },
    speakspell: {
        year: 1978, title: 'Texas Instruments Speak & Spell', era: 2,
        text: 'parts.display.setText(\'LOVE\') (≤ 8 characters)', drive: '{ power, voice }',
        footprint: [0.18, 0.26, 0.10], center: [0.0, -0.03],
    },
    c64: {
        year: 1982, title: 'Commodore 64 with its colour monitor', era: 2,
        text: 'parts.screen.setText([lines], cursorOn) or update state { lines, cursorOn }', drive: '{ power, voice, lines?, cursorOn? }',
        footprint: [0.41, 0.34, 0.69], center: [0.0, -0.09],
    },
    mac1984: {
        year: 1984, title: 'Macintosh 128K with keyboard and mouse', era: 2,
        text: 'parts.screen.setText(\'hello\')', drive: '{ power, voice }',
        footprint: [0.45, 0.34, 0.50], center: [0.06, 0.05],
    },
    dectalk: {
        year: 1984, title: 'DECtalk DTC01 speech synthesizer', era: 2,
        text: null, drive: '{ power, voice, leds?: [power, speech, back] }',
        footprint: [0.46, 0.10, 0.31], center: [0.0, 0.0],
    },
    desktop2001: {
        year: 2001, title: 'Early-2000s desktop PC (CRT, tower, speakers, keyboard, mouse)', era: 2,
        text: 'parts.screen.setText(\'reading screens\')', drive: '{ power, voice }',
        footprint: [1.15, 0.45, 0.91], center: [0.0, 0.03],
    },
};

export const NAMES = Object.keys(MACHINES);

// the module for one machine (its build() plus any extras, e.g. voder's pattern(t))
export async function loadMachine(name) {
    if (!MACHINES[name]) throw new Error(`[voice_machines] unknown machine '${name}' (have: ${NAMES.join(', ')})`);
    return await import(new URL(`./${name}.js`, import.meta.url).href);
}

// build one machine by name → { group, parts, update(t, state), dispose() } (+ the module's own extras)
export async function buildMachine(name, THREE, opts = {}) {
    const mod = await loadMachine(name);
    const m = await mod.build(THREE, opts);
    m.group.userData.voiceMachine = { name, ...MACHINES[name] };
    return m;
}
