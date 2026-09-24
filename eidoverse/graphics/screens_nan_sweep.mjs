// screens_nan_sweep.mjs — crash guard for canvas screen scenes. Non-finite geometry (NaN/Infinity reaching arc,
// lineTo, drawImage, …) makes Skia inside @napi-rs/canvas panic and abort the whole process, so a render dies with
// it. This patches the 2D context so any non-finite numeric argument throws a JS error with a stack instead, then
// draws every scene at every 60-fps frame from 0.5 s before its start to 0.5 s past its end, at three canvas sizes:
//   - no caption (each scene's own fallback words),
//   - a caption of other words with awkward timing (zero-length, empty, punctuation-only, single letters, a word
//     starting before the line and one running past it),
//   - your captions, when --lyrics (and optionally --cues) are given (see preview_screens.mjs),
// plus one draw per scene with no st at all. Exit code 1 on any failure. Re-run after every scene edit.
//
//   deno run -A eidoverse/graphics/screens_nan_sweep.mjs [module…] [--bpm 128] [--lyrics <json>] [--cues <json>]
// Default modules: every era_screens_*.js beside this file.
import { createCanvas } from 'npm:@napi-rs/canvas@0.1.69';
import { loadScenes, loadLyrics, makeTiming } from './preview_screens.mjs';

const args = [...Deno.args];
const opt = (name, dflt) => { const i = args.indexOf('--' + name); if (i < 0) return dflt; const v = args[i + 1]; args.splice(i, 2); return v; };
const BPM = +opt('bpm', 128), LYR = opt('lyrics', null), CUES = opt('cues', null);
let modPaths = args.filter((a) => /\.m?js$/i.test(a));
if (!modPaths.length) {
    const here = new URL('./', import.meta.url);
    modPaths = [...Deno.readDirSync(here)].map((e) => e.name).filter((n) => /^era_screens_.*\.js$/.test(n)).sort().map((n) => new URL(n, here).href);
}

// guard every numeric 2D-context entry point
const proto = Object.getPrototypeOf(createCanvas(1, 1).getContext('2d'));
const METHODS = ['arc', 'arcTo', 'moveTo', 'lineTo', 'bezierCurveTo', 'quadraticCurveTo', 'rect', 'roundRect', 'ellipse', 'fillRect',
    'strokeRect', 'clearRect', 'drawImage', 'fillText', 'strokeText', 'createLinearGradient', 'createRadialGradient', 'translate',
    'scale', 'rotate', 'setTransform', 'transform', 'getImageData', 'putImageData', 'createImageData'];
let calls = 0;
for (const m of METHODS) {
    const orig = proto[m];
    if (typeof orig !== 'function') continue;
    proto[m] = function (...a) {
        calls++;
        for (let i = 0; i < a.length; i++) {
            const v = a[i];
            if (typeof v === 'number' && !Number.isFinite(v)) throw new Error(`non-finite arg ${i} to ${m}(${a.map(String).join(', ')})`);
            if (Array.isArray(v) && v.some((x) => typeof x === 'number' && !Number.isFinite(x))) throw new Error(`non-finite radii to ${m}`);
        }
        return orig.apply(this, a);
    };
}

const ALL = await loadScenes(modPaths, BPM);
const cues = CUES ? JSON.parse(await Deno.readTextFile(CUES)) : null;
const T = makeTiming({ bpm: BPM, cues, lyrics: LYR ? await loadLyrics(LYR) : null });   // your captions
const TS = makeTiming({ bpm: BPM, cues });                                                // synthetic st
// other words, awkwardly timed (seconds from the line's start)
const ODD = [['—', -0.3, -0.1], ['we', 0, 0], ['were', 0.1, 0.4], ['all', 0.4, 0.4], ['the', 0.5, 0.9], ['voices', 0.9, 1.6], ['', 1.6, 1.7],
    ['in', 1.7, 1.9], ['a', 1.9, 2.0], ['machine,', 2.0, 2.9], ['L', 2.9, 3.0], ['O', 3.0, 3.1], ['forever', 3.1, 4.6]];
const oddCaption = (l0) => ({ text: ODD.map((w) => w[0]).join(' '), t0: l0 - 0.3, t1: l0 + 4.6, words: ODD.map(([w, a, b]) => ({ w, t0: l0 + a, t1: l0 + b })) });

const variants = [['no caption', (x, t) => TS.stAt(x.name, x.sc, t)],
    ['other words', (x, t) => { const st = TS.stAt(x.name, x.sc, t), cue = TS.cueOf(x.name, x.sc); return { ...st, caption: oddCaption(cue.t0 + st.line * TS.LINE) }; }]];
if (LYR) variants.push(['your captions', (x, t) => T.stAt(x.name, x.sc, t)]);

let draws = 0, failures = 0;
const t0 = performance.now();
for (const [W, H] of [[1920, 800], [1280, 533], [1024, 576]]) {
    const c = createCanvas(W, H), g = c.getContext('2d');
    for (const x of ALL) {
        try { x.sc.draw(g, W, H, 0, undefined); draws++; }
        catch (e) { failures++; console.log(`FAIL ${x.name} ${W}x${H} st=undefined: ${e.message}\n${(e.stack || '').split('\n').slice(1, 4).join('\n')}`); }
        for (const [vname, stOf] of variants) {
            const cue = (vname === 'your captions' ? T : TS).cueOf(x.name, x.sc);
            const f0 = Math.round((cue.t0 - 0.5) * 60), f1 = Math.round((cue.t0 + cue.dur + 0.5) * 60);
            for (let f = f0; f <= f1; f++) {
                const t = f / 60;                                            // a 60-fps host's frame times
                try { x.sc.draw(g, W, H, t, stOf(x, t)); draws++; }
                catch (e) { failures++; console.log(`FAIL ${x.name} ${W}x${H} ${vname} t=${t.toFixed(4)} u=${(t - cue.t0).toFixed(4)}: ${e.message}\n${(e.stack || '').split('\n').slice(1, 4).join('\n')}`); break; }
            }
        }
    }
}
console.log(`${draws} draws of ${ALL.length} scenes, ${calls} guarded canvas calls, ${failures} failures (${((performance.now() - t0) / 1000).toFixed(1)} s)`);
if (failures) Deno.exit(1);
