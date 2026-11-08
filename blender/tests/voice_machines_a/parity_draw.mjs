// The WebGPU originals' screen drawings (drawC64, drawMac, drawDesktop + drawFlag, drawSpeakerGlyph), run unchanged
// in Deno with Skia (@napi-rs/canvas, the canvas the engine's makeScreen drew on) for the Python ports' parity test:
//   deno run --no-config --no-lock --node-modules-dir=none --cached-only -A \
//       blender/tests/voice_machines_a/parity_draw.mjs <out_dir> [cases.json]
// The draw functions are closures inside each module's build(), so their source is cut out of the module text and
// evaluated with the names they close over (CW, CH, FONT8, K.makeCanvas / rng / rr, title, clock).
// cases.json: [{machine: 'c64' | 'mac1984' | 'desktop2001', name, lines?, cursor?, blink?, text?, title?, clock?}].
import { createCanvas } from 'npm:@napi-rs/canvas@0.1.69';

const here = new URL('.', import.meta.url);
const root = new URL('../../../', here);
const src = (n) => Deno.readTextFileSync(new URL(`eidoverse/props/voice_machines/${n}.js`, root));

function cut(text, head) {                       // a function's source, by brace matching from its header
    const a = text.indexOf(head);
    if (a < 0) throw new Error('missing ' + head);
    let i = text.indexOf('{', a), depth = 0;
    for (; i < text.length; i++) {
        const c = text[i];
        if (c === '{') depth++;
        else if (c === '}') { depth--; if (depth === 0) return text.slice(a, i + 1); }
    }
    throw new Error('unbalanced ' + head);
}
const rng = (seed) => {
    let s = ((seed | 0) * 2654435761) >>> 0;
    return () => {
        s = (s + 0x6D2B79F5) >>> 0;
        let t = s;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
};
const rr = (ctx, x, y, w, h, r) => {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
};
const K = { makeCanvas: (w, h) => createCanvas(w, h), rng, rr };

const c64 = src('c64'), mac = src('mac1984'), desk = src('desktop2001');
const font8 = c64.slice(c64.indexOf('const G = (s)'), c64.indexOf('};', c64.indexOf('const FONT8')) + 2);
const drawC64 = new Function('CW', 'CH', `${font8}\n${cut(c64, 'function drawC64(')}\nreturn drawC64;`)(768, 576);
const drawMac = new Function('K', 'title', `${cut(mac, 'function drawMac(')}\nreturn drawMac;`);
const drawDesktop = new Function('K', 'title', 'clock',
    `${cut(desk, 'function drawDesktop(')}\n${cut(desk, 'function drawFlag(')}\n${cut(desk, 'function drawSpeakerGlyph(')}\nreturn drawDesktop;`);

const out = Deno.args[0];
Deno.mkdirSync(out, { recursive: true });
const cases = Deno.args[1] ? JSON.parse(Deno.readTextFileSync(Deno.args[1])) : [
    { machine: 'c64', name: 'c64_boot', lines: ['', '    **** SPEECH BASIC V2 ****', '', ' 64K RAM SYSTEM  38911 BASIC BYTES FREE', '', 'READY.'], cursor: true, blink: 1 },
    { machine: 'c64', name: 'c64_say', lines: ['READY.', 'SAY "I WAS A MOUTH"', 'I WAS A MOUTH', 'READY.'], cursor: true, blink: 0 },
    { machine: 'mac1984', name: 'mac_hello', text: 'hello', title: 'Note' },
    { machine: 'mac1984', name: 'mac_two', text: 'I was a mouth\nand a voice', title: 'MacinTalk' },
    { machine: 'desktop2001', name: 'desktop_reading', text: 'reading screens', title: 'Narrator', clock: '10:23 PM' },
    { machine: 'desktop2001', name: 'desktop_wrap', text: 'I read every screen to you aloud\nthen I sang', title: 'Narrator', clock: '11:59 PM' },
];
for (const c of cases) {
    let cv;
    if (c.machine === 'c64') {
        cv = createCanvas(768, Math.round(768 * 0.218 / 0.282));
        drawC64(cv.getContext('2d'), { lines: c.lines, cursor: c.cursor, blinkPhase: c.blink });
    } else if (c.machine === 'mac1984') {
        cv = createCanvas(512, Math.round(512 * 0.1207 / 0.1806));
        drawMac(K, c.title ?? 'Note')(cv.getContext('2d'), { text: c.text });
    } else {
        cv = createCanvas(1024, Math.round(1024 * 0.262 / 0.345));
        drawDesktop(K, c.title ?? 'Narrator', c.clock ?? '10:23 PM')(cv.getContext('2d'), { text: c.text });
    }
    Deno.writeFileSync(`${out}/${c.name}.png`, await cv.encode('png'));
    console.log(c.name, cv.width, cv.height);
}
