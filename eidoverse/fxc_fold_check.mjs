// fxc_fold_check.mjs — does FXC still compile the sky's WebGL2 shader the way it compiles a known-clean reference?
//
// FXC (Direct3D's shader compiler, Chrome/Edge's default WebGL2 path on Windows) can treat a variable as
// integer-valued inside nested rolled loops and drop floor(), frac() and t*t from whatever reads it. fbmOf in
// sky_system.js works around it with a dead store; this checks that the workaround still holds. The reference is
// the same HLSL with [fastopt] on every loop that contains a loop (FXC then does not simulate it and does not fold).
// PASS = every non-mov opcode count in the dump's compile equals the reference's.
//
//   node eidoverse/fxc_fold_check.mjs <dump.txt> [--target ps_5_0]   (deno run -A, or bun, also work)
//   node eidoverse/fxc_fold_check.mjs --selftest   FXC must still fold the 21-line repro; else a PASS proves nothing
//
// <dump.txt>: ANGLE's translated shader for the sky's fragment program, from a Windows Chrome/Edge on D3D11 started
// with --enable-privileged-webgl-extensions. Install this before the page creates its shaders (Playwright
// addInitScript, or CDP Page.addScriptToEvaluateOnNewDocument), then call __dumpSky() once the sky has baked:
//   const P = WebGL2RenderingContext.prototype, ss = P.shaderSource; let sky;   // keeps the largest kPass shader
//   P.shaderSource = function (s, src) { if (src.includes('kPass') && !(sky?.[2] > src.length)) sky = [this, s, src.length]; return ss.call(this, s, src); };
//   globalThis.__dumpSky = () => sky[0].getExtension('WEBGL_debug_shaders').getTranslatedShaderSource(sky[1]);
// FXC: $FXC, else the newest Windows Kits x64 fxc.exe. Opt level /O2 is ANGLE's (D3DCOMPILE_OPTIMIZATION_LEVEL2).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const REPRO = `cbuffer C : register(b0) { float a; float d; }
float4 main(float4 pos : SV_Position) : SV_Target {
  float sumFrac = 0, sumFloor = 0, sumSq = 0;
  float q = 0;
  for (int k = 0; k < 8; k++) {
    float tr = 1;
    float p = pos.x + k;
    for (int i = 0; i < 60; i++) {
      if (tr <= 0.008) break;
      q = p * a;
      float s = saturate(q);
      sumFrac += frac(q);
      sumFloor += floor(q);
      sumSq += s * s;
      tr *= d;
      p += d;
    }
  }
  return float4(sumFrac, sumFloor, sumSq, 1);
}`;

const wsl = fs.existsSync('/proc/version') && /microsoft/i.test(fs.readFileSync('/proc/version', 'utf8'));
const winPath = (p) => wsl ? execFileSync('wslpath', ['-w', p], { encoding: 'utf8' }).trim() : p;

function findFxc() {
    if (process.env.FXC) return process.env.FXC;
    const root = wsl ? '/mnt/c/Program Files (x86)/Windows Kits/10/bin' : 'C:\\Program Files (x86)\\Windows Kits\\10\\bin';
    const ver = (v) => v.split('.').map(Number);
    const kits = fs.existsSync(root) ? fs.readdirSync(root).filter((v) => /^10\./.test(v) && fs.existsSync(path.join(root, v, 'x64', 'fxc.exe'))) : [];
    kits.sort((a, b) => { const x = ver(a), y = ver(b); for (let i = 0; i < 4; i++) if (x[i] !== y[i]) return x[i] - y[i]; return 0; });
    if (!kits.length) throw new Error('fxc.exe not found: install the Windows SDK or set FXC');
    return path.join(root, kits.at(-1), 'x64', 'fxc.exe');
}

/** ANGLE's dump holds the source it hands D3DCompile between these markers; anything else is used whole. */
export function compilerInput(text) {
    const m = text.match(/\/\/ COMPILER INPUT HLSL BEGIN\n([\s\S]*?)\/\/ COMPILER INPUT HLSL END/);
    return m ? m[1] : text;
}

/** End of the statement that starts at i (a {...} block, or up to the ;), skipping a for(...) or do header. */
function bodyEnd(src, i) {
    let depth = 0, j = i;
    for (; j < src.length; j++) {
        const c = src[j];
        if (c === '(' || c === '{') depth++;
        else if (c === ')' || c === '}') { depth--; if (depth === 0 && c === '}') return j + 1; }
        else if (c === ';' && depth === 0) return j + 1;
    }
    return j;
}

/** Insert [fastopt] before every for/do whose body contains another for/do. Returns { hlsl, count }. */
export function addFastopt(src) {
    const loops = [...src.matchAll(/\b(for\s*\(|do\b)/g)].map((m) => m.index);
    const marks = [];
    for (const at of loops) {
        let b = at;
        if (src.startsWith('for', at)) { let d = 0; for (b = at + 3; b < src.length; b++) { if (src[b] === '(') d++; else if (src[b] === ')' && --d === 0) { b++; break; } } }
        else b = at + 2;
        const end = bodyEnd(src, b), inner = src.slice(b, end);
        const already = /\[fastopt\]\s*$/.test(src.slice(Math.max(0, at - 16), at));
        if (/\b(for\s*\(|do\b)/.test(inner) && !already) marks.push(at);
    }
    let out = src;
    for (const at of marks.reverse()) out = out.slice(0, at) + '[fastopt] ' + out.slice(at);
    return { hlsl: out, count: marks.length };
}

/** Opcode histogram of an FXC /Fc listing, plus the self-multiplies (t*t) that the fold removes. */
export function opcodes(asm) {
    const h = {};
    for (const raw of asm.split(/\r?\n/)) {
        if (raw.startsWith('//') || !raw.trim()) continue;
        const l = raw.replace(/ \[precise\(\w+\)\]/, '');
        const op = l.match(/^\s*([a-z_0-9]+)/)?.[1]; if (!op) continue;
        h[op] = (h[op] ?? 0) + 1;
        if (/^\s*(mul \S+, (r\d+\.\w+), \2$|mad \S+, (r\d+\.\w+), \3, )/.test(l)) h['(self-multiply)'] = (h['(self-multiply)'] ?? 0) + 1;
    }
    return h;
}

function compile(fxc, hlsl, target, dir, name) {
    const src = path.join(dir, name + '.hlsl'), asm = path.join(dir, name + '.asm');
    fs.writeFileSync(src, hlsl);
    try { execFileSync(fxc, ['/nologo', '/T', target, '/E', 'main', '/O2', '/Fc', winPath(asm), winPath(src)], { stdio: 'pipe', timeout: 900000 }); }
    catch (e) { throw new Error(`fxc failed on ${name}: ${String(e.stderr || e.message).slice(0, 2000)}`); }
    return opcodes(fs.readFileSync(asm, 'utf8'));
}

/** Compiles hlsl and its [fastopt] reference; returns the rows that differ (mov ignored: register shuffles). */
export function check(hlsl, { target = 'ps_5_0', fxc = findFxc() } = {}) {
    const ref = addFastopt(hlsl);
    if (ref.count === 0) throw new Error('no loop containing a loop: this is not the looped sky shader, so there is nothing to check');
    const dir = fs.mkdtempSync(path.join(wsl ? '/mnt/c/Windows/Temp' : os.tmpdir(), 'fxcfold-'));
    try {
        const a = compile(fxc, hlsl, target, dir, 'dump'), b = compile(fxc, ref.hlsl, target, dir, 'reference');
        if (!b.round_ni) throw new Error('reference has no round_ni: no floor() reached the bytecode, so the counts say nothing');
        const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])].filter((k) => k !== 'mov').sort();
        return { fxc, fastoptLoops: ref.count, dump: a, reference: b, diff: keys.filter((k) => (a[k] ?? 0) !== (b[k] ?? 0)) };
    } finally { fs.rmSync(dir, { recursive: true, force: true }); }
}

function report(label, r) {
    const show = ['round_ni', 'frc', '(self-multiply)', 'mad', 'mul', 'add'];
    console.log(`${label}: ${r.fxc}, /O2, ${r.fastoptLoops} loop(s) given [fastopt] in the reference`);
    for (const k of [...new Set([...show, ...r.diff])]) console.log(`  ${k.padEnd(16)} dump ${String(r.dump[k] ?? 0).padStart(5)}  reference ${String(r.reference[k] ?? 0).padStart(5)}${r.diff.includes(k) ? '  <-- differs' : ''}`);
}

if (import.meta.main ?? process.argv[1]?.endsWith('fxc_fold_check.mjs')) {
    const args = process.argv.slice(2), ti = args.indexOf('--target'), target = ti >= 0 ? args[ti + 1] : 'ps_5_0';
    if (args.includes('--selftest')) {
        const r = check(REPRO, { target: 'ps_5_0' }); report('selftest (fold repro)', r);
        if (!r.diff.length) { console.log('SELFTEST FAILED: this FXC does not fold the repro, so a PASS on the sky would prove nothing'); process.exit(1); }
        console.log('selftest ok: this FXC folds the repro and the checker sees it'); process.exit(0);
    }
    const file = args.find((a, i) => !a.startsWith('--') && args[i - 1] !== '--target');
    if (!file) { console.log('usage: fxc_fold_check.mjs <dump.txt> [--target ps_5_0] | --selftest   (see the header)'); process.exit(2); }
    const r = check(compilerInput(fs.readFileSync(file, 'utf8')), { target }); report(file, r);
    console.log(r.diff.length ? `FAIL: FXC folded something the [fastopt] reference keeps (${r.diff.join(', ')})` : 'PASS: same arithmetic as the [fastopt] reference');
    process.exit(r.diff.length ? 1 : 0);
}
