// Stills of a WebXR page from headless Chrome, for checking without a headset (guide: tools-guides/webxr.md).
//
//   node eidoverse/xr/shot.mjs <page-url> <out-dir> "query" ["query" ...]
//   node eidoverse/xr/shot.mjs http://127.0.0.1:8894/eidoverse/xr/example.html work/_shots "t=4&street=0,10" "t=4&view=table"
//
// Each query is appended to the page URL; the page renders that moment and sets window.__shot = 'ready' (or
// 'error: …'), then the still is saved as <out-dir>/<query>.png. It goes through the same WebGL2 backend the
// headset uses. Printed per still: how long it took, window.__shotInfo if the page sets one, and every
// exception and console error/warning. Env: CHROME (browser binary), SHOT_SIZE (default 1600x900),
// SHOT_TIMEOUT (seconds per still, default 60).
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [page, outDir, ...queries] = process.argv.slice(2);
if (!page || !outDir || !queries.length) {
  console.error('usage: node eidoverse/xr/shot.mjs <page-url> <out-dir> "query" ["query" ...]');
  process.exit(2);
}
const CANDIDATES = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome',
  '/usr/bin/chromium', '/usr/bin/chromium-browser', 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'];
const CHROME = process.env.CHROME || CANDIDATES.find((p) => existsSync(p));
if (!CHROME) { console.error('no Chrome found: set CHROME to a Chrome/Chromium binary'); process.exit(2); }
const [W, H] = (process.env.SHOT_SIZE || '1600x900').split('x').map(Number);
const TIMEOUT = +(process.env.SHOT_TIMEOUT || 60) * 1000;
mkdirSync(outDir, { recursive: true });

const port = 9300 + Math.floor(Math.random() * 600);
const prof = join(tmpdir(), `eido_xr_shot_${port}`);
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  `--window-size=${W},${H}`, '--enable-gpu', '--ignore-gpu-blocklist', '--use-angle=' + (process.platform === 'darwin' ? 'metal' : 'default'),
  '--disable-features=MacAppCodeSignClone', '--no-first-run', '--autoplay-policy=no-user-gesture-required', 'about:blank'],
{ stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ok = false;
for (let i = 0; i < 100 && !ok; i++) { try { await fetch(`http://127.0.0.1:${port}/json/version`); ok = true; } catch { await sleep(150); } }
if (!ok) { console.error('Chrome did not start'); chrome.kill(); process.exit(1); }
const tgt = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
await sleep(200);
const ws = new WebSocket(tgt.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0; const pend = new Map();
ws.addEventListener('message', (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); }
  if (d.method === 'Runtime.exceptionThrown') console.log('  EXCEPTION', d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text);
  if (d.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(d.params.type))
    console.log('  console.' + d.params.type, d.params.args.map((a) => a.value ?? a.description).join(' ').slice(0, 400));
});
const cmd = (method, params = {}) => new Promise((r) => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (e) => (await cmd('Runtime.evaluate', { expression: e, returnByValue: true })).result?.result?.value;
await cmd('Runtime.enable'); await cmd('Page.enable');
await cmd('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });

let failed = 0;
for (const q of queries) {
  const t0 = Date.now();
  await cmd('Page.navigate', { url: page + (page.includes('?') ? '&' : '?') + q });
  let st = '';
  while (!st && Date.now() - t0 < TIMEOUT) { st = await ev('window.__shot || ""'); if (!st) await sleep(150); }
  const shot = await cmd('Page.captureScreenshot', { format: 'png' });
  const file = join(outDir, q.replace(/[^a-z0-9.=,-]+/gi, '_') + '.png');
  writeFileSync(file, Buffer.from(shot.result.data, 'base64'));
  const info = await ev('window.__shotInfo ? JSON.stringify(window.__shotInfo) : ""');
  if (st !== 'ready') failed++;
  console.log(`${q}: ${st || 'TIMEOUT'} in ${((Date.now() - t0) / 1000).toFixed(1)} s -> ${file}${info ? '  ' + info : ''}`);
}
await cmd('Browser.close');
await sleep(400);
try { chrome.kill(); } catch { /* already gone */ }
rmSync(prof, { recursive: true, force: true });
process.exit(failed ? 1 : 0);
