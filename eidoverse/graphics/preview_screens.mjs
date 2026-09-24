// preview_screens.mjs — render canvas screen scenes to PNGs without the 3D engine (Deno + @napi-rs/canvas / Skia).
// Guide: tools-guides/motion-graphics.md ("Canvas screen scenes"). Run from the repository root.
//
//   deno run -A eidoverse/graphics/preview_screens.mjs <module…> <scene> [u…]     PNGs at u seconds into the scene
//   deno run -A eidoverse/graphics/preview_screens.mjs <module…> --sheet [scene…]  contact sheet, --moments per scene
//   deno run -A eidoverse/graphics/preview_screens.mjs <module…> --bench [scene…]  draw cost in ms at --W×--H
//
// <module> is a scene module (e.g. eidoverse/graphics/era_screens_1939_1984.js); give one or more. Other bare words
// are scene names (all scenes when none are named) and, in the single-scene form, the times u.
// Options:
//   --W 1920 --H 800   canvas size          --out <dir | file.png>   default work/screens_preview/
//   --moments 5        frames per scene     --bpm 128                the song's tempo (a line = two 4/4 bars)
//   --at 0             film time of each scene's start
//   --cues <json>      per-scene starts: { "<scene>": t0 } or { "<scene>": { "t0": s, "dur": s } } (overrides --at)
//   --lyrics <json>    captions: align_lyrics.py output, [{ text, t0, t1, words: [{ w, t0, t1 }] }], or a timeline
//                      { captions, hits: { kick: [s…] }, envelopes: { <singer>: [0..1 per frame] }, visemes_fps }
//   --refs <dir>       reference images named <scene prefix>_*.png|jpg, shown beside each sheet row
// Without --lyrics, st is synthetic: caption null (each scene falls back to DAISY's own words), a kick on every
// beat from the scene's start, and a voice level that pulses once per beat.
import { createCanvas, loadImage } from 'npm:@napi-rs/canvas@0.1.69';

// a path or URL -> an importable file URL (relative paths resolve from the working directory)
export function toUrl(p) {
    if (/^(file|https?):/i.test(p)) return p;
    let abs = String(p).replaceAll('\\', '/');
    if (!/^([A-Za-z]:)?\//.test(abs)) abs = Deno.cwd().replaceAll('\\', '/') + '/' + abs;
    return new URL('file://' + (abs.startsWith('/') ? '' : '/') + encodeURI(abs)).href;
}

// import scene modules, register their fonts, set the tempo; returns [{ name, sc, mod }] in module order
export async function loadScenes(modPaths, bpm = 128) {
    const out = [];
    for (const p of modPaths) {
        const mod = await import(toUrl(p));
        if (mod.registerFonts) await mod.registerFonts();
        if (mod.setTempo) mod.setTempo(bpm);
        for (const [name, sc] of Object.entries(mod.scenes || {})) out.push({ name, sc, mod, path: p });
    }
    return out;
}

// captions (+ kicks and loudness envelopes when the file is a timeline) from align_lyrics.py output, scene-format
// captions, or a timeline object
export async function loadLyrics(file) {
    const j = JSON.parse(await Deno.readTextFile(file));
    const raw = Array.isArray(j) ? j : (j.captions || j.lines || []);
    const captions = raw.map((c) => ({
        text: c.text ?? '', t0: c.t0 ?? c.start, t1: c.t1 ?? c.end, singer: c.singer ?? null,
        words: (c.words || []).map((w) => ({ w: String(w.w ?? w.word ?? '').trim(), t0: w.t0 ?? w.start, t1: w.t1 ?? w.end })),
    })).filter((c) => Number.isFinite(c.t0)).sort((a, b) => a.t0 - b.t0);
    return {
        captions,
        kicks: Array.isArray(j) ? null : (j.hits?.kick || null),
        envelopes: Array.isArray(j) ? null : (j.envelopes || null),
        envFps: (!Array.isArray(j) && j.visemes_fps) || 30,
    };
}

// st for a scene at film time t: { u, dur, progress, caption, voice, kick, line }
export function makeTiming({ bpm = 128, at = 0, cues = null, lyrics = null } = {}) {
    const BEAT = 60 / bpm, LINE = 8 * BEAT;
    const kicks = lyrics?.kicks || null;
    const kickAt = (t, t0) => {
        if (!kicks) { const x = t - t0; return x < 0 ? 0 : Math.exp(-(x % BEAT) / 0.09); }
        let lo = 0, hi = kicks.length - 1, k = -1;
        while (lo <= hi) { const m = (lo + hi) >> 1; if (kicks[m] <= t) { k = m; lo = m + 1; } else hi = m - 1; }
        return k < 0 ? 0 : Math.exp(-(t - kicks[k]) / 0.09);
    };
    const cueOf = (name, sc) => {
        const c = cues?.[name];
        const t0 = typeof c === 'number' ? c : (c?.t0 ?? at);
        const lines = sc.dur ? 1 : (sc.lines || 1);
        return { t0, dur: (typeof c === 'object' && c?.dur) || sc.dur || lines * LINE, lines };
    };
    const stAt = (name, sc, t) => {
        const cue = cueOf(name, sc), u = t - cue.t0;
        const line = Math.max(0, Math.min(cue.lines - 1, Math.floor(u / LINE)));
        const l0 = cue.t0 + line * LINE, l1 = sc.dur ? cue.t0 + cue.dur : l0 + LINE;
        const caption = lyrics ? (lyrics.captions.find((c) => c.t0 >= l0 - 0.05 && c.t0 < l1) || null) : null;
        let voice = 0.5 + 0.4 * Math.abs(Math.sin(Math.PI * u / BEAT));
        if (lyrics) {
            const env = caption && lyrics.envelopes ? lyrics.envelopes[caption.singer] : null;
            voice = env ? (env[Math.max(0, Math.min(env.length - 1, Math.round(t * lyrics.envFps)))] || 0) : (caption ? voice : 0);
        }
        return { u, dur: cue.dur, progress: u / cue.dur, caption, voice, kick: kickAt(t, cue.t0), line };
    };
    return { BEAT, LINE, cueOf, stAt };
}

async function main() {
    const args = [...Deno.args];
    const opt = (name, dflt) => { const i = args.indexOf('--' + name); if (i < 0) return dflt; const v = args[i + 1]; args.splice(i, 2); return v; };
    const flag = (name) => { const i = args.indexOf('--' + name); if (i < 0) return false; args.splice(i, 1); return true; };
    const W = +opt('W', 1920), H = +opt('H', 800), OUT = opt('out', null), MOMENTS = Math.max(1, +opt('moments', 5));
    const BPM = +opt('bpm', 128), AT = +opt('at', 0), CUES = opt('cues', null), LYR = opt('lyrics', null), REFS = opt('refs', null);
    const SHEET = flag('sheet'), BENCH = flag('bench');
    const isMod = (a) => /\.m?js$/i.test(a);
    const modPaths = args.filter(isMod), rest = args.filter((a) => !isMod(a));
    if (!modPaths.length) {
        console.log('usage: preview_screens.mjs <module…> <scene> [u…] | --sheet [scene…] | --bench [scene…]  (see the header)');
        Deno.exit(1);
    }
    const ALL = await loadScenes(modPaths, BPM);
    const T = makeTiming({
        bpm: BPM, at: AT,
        cues: CUES ? JSON.parse(await Deno.readTextFile(CUES)) : null,
        lyrics: LYR ? await loadLyrics(LYR) : null,
    });
    const names = rest.filter((a) => Number.isNaN(+a));
    const pick = names.length ? names.map((n) => ALL.find((x) => x.name === n) || (console.log(`unknown scene ${n}; have: ${ALL.map((x) => x.name).join(', ')}`), Deno.exit(1))) : ALL;
    const render = (x, t, w = W, h = H) => {
        const c = createCanvas(w, h), g = c.getContext('2d'), st = T.stAt(x.name, x.sc, t);
        const a = performance.now();
        x.sc.draw(g, w, h, t, st);
        return { c, ms: performance.now() - a, st };
    };
    const fmt = (v) => (Math.round(v * 100) / 100).toFixed(2);
    const mkdirFor = (file) => { const d = file.replace(/[\\/][^\\/]*$/, ''); if (d && d !== file) Deno.mkdirSync(d, { recursive: true }); };

    if (BENCH) {
        // prewarm as a host would at load, then per scene: one first play at the scene's fps, and the quietest of
        // three 45-frame passes (the host is shared; the quietest pass is the honest cost of the draw)
        for (const mod of new Set(pick.map((x) => x.mod))) {
            if (!mod.prewarm) continue;
            const a = performance.now();
            mod.prewarm(W, H, (name) => { const x = ALL.find((y) => y.name === name); const cue = T.cueOf(name, x.sc); return { t0: cue.t0, dur: cue.dur, st: (t) => T.stAt(name, x.sc, t) }; });
            console.log(`prewarm ${fmt(performance.now() - a)} ms`);
        }
        for (const x of pick) {
            const cue = T.cueOf(x.name, x.sc), fps = x.sc.fps || 30;
            const c = createCanvas(W, H), g = c.getContext('2d');
            let first = 0;
            for (let f = 0; f < cue.dur * fps; f++) {
                const t = cue.t0 + f / fps, st = T.stAt(x.name, x.sc, t), a = performance.now();
                x.sc.draw(g, W, H, t, st);
                first = Math.max(first, performance.now() - a);
            }
            let best = null;
            for (let pass = 0; pass < 3; pass++) {
                const n = 45, times = [];
                for (let i = 0; i < n; i++) {
                    const t = cue.t0 + (i / n) * cue.dur, st = T.stAt(x.name, x.sc, t), a = performance.now();
                    x.sc.draw(g, W, H, t, st);
                    times.push(performance.now() - a);
                }
                times.sort((p, q) => p - q);
                const mean = times.reduce((s, v) => s + v, 0) / n;
                if (!best || mean < best.mean) best = { mean, p50: times[n >> 1], p90: times[Math.floor(n * 0.9)], max: times[n - 1] };
            }
            console.log(`${x.name.padEnd(18)} mean ${fmt(best.mean)} ms   p50 ${fmt(best.p50)}   p90 ${fmt(best.p90)}   max ${fmt(best.max)}   first-play max ${fmt(first)}`);
        }
    } else if (SHEET) {
        const tw = 480, th = Math.round(tw * H / W), pad = 10, lab = 26, refW = REFS ? 300 : 0;
        let refFiles = [];
        if (REFS) { try { refFiles = [...Deno.readDirSync(REFS)].map((e) => e.name).filter((n) => /\.(png|jpe?g)$/i.test(n)).sort(); } catch { } }
        const x0 = pad + (refW ? refW + pad : 0);
        const sheet = createCanvas(x0 + MOMENTS * (tw + pad), pad + pick.length * (th + lab + pad));
        const sg = sheet.getContext('2d');
        sg.fillStyle = '#16161a'; sg.fillRect(0, 0, sheet.width, sheet.height);
        sg.textBaseline = 'top';
        for (let r = 0; r < pick.length; r++) {
            const x = pick[r], cue = T.cueOf(x.name, x.sc), y = pad + r * (th + lab + pad);
            sg.font = '18px "Share Tech Mono"'; sg.fillStyle = '#e8e4d8';
            sg.fillText(`${x.name}  ·  ${x.sc.label || ''}  ·  ${fmt(cue.dur)} s at ${x.sc.fps || 30} fps`, pad, y + 2);
            if (refW) {
                const prefix = x.name.split('_')[0] + '_';
                const mine = refFiles.filter((f) => f.startsWith(prefix)).slice(0, 2);
                for (let i = 0; i < mine.length; i++) {
                    try {
                        const img = await loadImage(REFS.replace(/[\\/]?$/, '/') + mine[i]);
                        const bh = (th - (mine.length - 1) * 4) / mine.length, s = Math.min(refW / img.width, bh / img.height);
                        sg.drawImage(img, pad + (refW - img.width * s) / 2, y + lab + i * (bh + 4) + (bh - img.height * s) / 2, img.width * s, img.height * s);
                    } catch { }
                }
            }
            for (let i = 0; i < MOMENTS; i++) {
                const f = MOMENTS === 1 ? 0.5 : 0.04 + (0.92 * i) / (MOMENTS - 1);
                const t = cue.t0 + f * cue.dur, { c, ms } = render(x, t);
                const xx = x0 + i * (tw + pad);
                sg.drawImage(c, xx, y + lab, tw, th);
                sg.font = '14px "Share Tech Mono"'; sg.fillStyle = 'rgba(0,0,0,0.6)'; sg.fillRect(xx, y + lab, 150, 20);
                sg.fillStyle = '#e8e4d8'; sg.fillText(`u ${fmt(t - cue.t0)}  ${fmt(ms)} ms`, xx + 4, y + lab + 3);
            }
        }
        const file = OUT && /\.png$/i.test(OUT) ? OUT : (OUT || 'work/screens_preview') + '/screens_sheet.png';
        mkdirFor(file);
        await Deno.writeFile(file, sheet.toBuffer('image/png'));
        console.log(`[preview_screens] sheet (${pick.length} scenes × ${MOMENTS}) -> ${file}`);
    } else {
        const x = names.length ? pick[0] : null;
        if (!x) { console.log('name a scene, or use --sheet / --bench; scenes: ' + ALL.map((y) => y.name).join(', ')); Deno.exit(1); }
        const cue = T.cueOf(x.name, x.sc);
        const times = rest.filter((a) => !Number.isNaN(+a)).map(Number);
        if (!times.length) for (let i = 0; i < MOMENTS; i++) times.push((MOMENTS === 1 ? 0.5 : 0.04 + 0.92 * i / (MOMENTS - 1)) * cue.dur);
        const dir = OUT || 'work/screens_preview';
        Deno.mkdirSync(dir, { recursive: true });
        for (const u of times) {
            const t = cue.t0 + u, { c, ms, st } = render(x, t);
            const file = `${dir}/${x.name}_${fmt(u)}.png`;
            await Deno.writeFile(file, c.toBuffer('image/png'));
            console.log(`[preview_screens] ${file}  u=${fmt(st.u)} line=${st.line} voice=${fmt(st.voice)} kick=${fmt(st.kick)}  ${fmt(ms)} ms`);
        }
    }
}

if (import.meta.main) await main();
