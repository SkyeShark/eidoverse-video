// The masks where the rest of the port reads them (PORT_PLAN.md 8.2 row P7): api.js's generate() makes a terrain's
// masks with masks.js computeStack on the level runner's own fields, Terrain.save writes them as api.py caches them
// (float16 for the bounded ones) and Terrain.load reads them back, t.mask(name).at(x, z) samples them, and run.js's
// `where` evaluates an expression that names a mask through masks.js compute.
//
//     deno run --config deno.json --frozen --unstable-webgpu --allow-all eidoverse/terrain/tests/masks/api_masks_test.mjs
//         (on a shared machine, behind $EIDO_GPU_WRAP)
//
// The terrain is real_place at draft quality (its DEM op is in the checkout; a stage whose package has not landed is
// skipped by the runner, as run.js says), so its masks are not compared with a Blender run here: masks_test.mjs does
// that on Blender's own saves. Writes tests/out/masks/api_masks_test.json and a save in tests/out/masks/api_save/.

import * as G from '../../core/gpu.js';
import * as E from '../../core/expr.js';
import { Fields } from '../../core/fields.js';
import { generate, Terrain } from '../../api.js';
import * as M from '../../masks.js';
import * as RUN from '../../run.js';
import * as C from '../parity/_common.mjs';

const W = C.W;
const T = new C.Checks('masks in the API: generate, save, load, at, where');
const R = await G.init();
const res = {};
const quiet = () => {};

const t = await generate({ recipe: 'real_place', quality: 'draft', seed: 1, cache: false, log: quiet });
const names = t.masks.names();
res.skipped_stages = t.info.skipped_stages;
res.masks = names;
res.mask_skipped = t.masks.skipped();
res.seconds = t.info.seconds;
// every default mask made, or skipped on every level with masks.py's reason (an input this terrain lacks)
const skipped = res.mask_skipped;
const missing = M.DEFAULT_NAMES.filter((n) => !names.includes(n) &&
    !t.levels.every((lv) => typeof skipped[lv.index]?.[n] === 'string' && skipped[lv.index][n].length > 0));
const why = [...new Set(Object.values(skipped).flatMap((s) => Object.entries(s).map(([k, v]) => `${k}: ${v}`)))];
T.ok('generate: every default mask of every level made by masks.js, or skipped saying why', missing.length === 0,
    missing.length ? `neither made nor skipped: ${missing.join(', ')}` : `${names.length} made; skipped ${why.join('; ')}`);
let finite = true, inRange = true;
for (let i = 0; i < t.levels.length; i++) {
    const lv = t.levels[i];
    for (const nm of names) {
        let a;
        try {
            a = t.mask(nm).array(i);
        } catch (_e) {
            continue;
        }
        if (a.length !== lv.n * lv.n) finite = false;
        for (let k = 0; k < a.length; k++) {
            if (!Number.isFinite(a[k])) finite = false;
            if (M.MASKS[M.parseName(nm)[0]][0] === '0-1' && (a[k] < 0 || a[k] > 1)) inRange = false;
        }
    }
}
T.ok('every mask of every level finite, of the level\'s size', finite);
T.ok('every 0-1 mask in [0, 1]', inRange);
// t.mask(name).at(x, z): the finest level holding the point (three.js frame: z = -y)
const main = t.levels.find((lv) => lv.role === 'main');
const [cx, cy] = main.centre;
const s1 = t.mask('slope').at(cx, -cy);
const j = Math.floor((cy - main.y0) / main.cell - 0.5), i = Math.floor((cx - main.x0) / main.cell - 0.5);
const arr = t.mask('slope').array('main');
const near = [arr[j * main.n + i], arr[j * main.n + i + 1], arr[(j + 1) * main.n + i], arr[(j + 1) * main.n + i + 1]];
T.ok('t.mask(\'slope\').at(x, z) lies among the four cells around the point', s1 >= Math.min(...near) - 1e-6 && s1 <= Math.max(...near) + 1e-6,
    `${s1.toFixed(3)} in [${Math.min(...near).toFixed(3)}, ${Math.max(...near).toFixed(3)}]`);
// save and load
const dir = W.out('masks/api_save');
await t.save(`${dir}/real_place_draft`);
const t2 = await Terrain.load(`${dir}/real_place_draft`, { build: false, log: quiet });
let same = true, halfOk = true;
const bounded = ['0-1', '-1..1', 'deg'];
for (let li = 0; li < t.levels.length; li++) {
    for (const nm of names) {
        let a, b;
        try {
            a = t.mask(nm).array(li);
            b = t2.mask(nm).array(li);
        } catch (_e) {
            continue;
        }
        const half = bounded.includes(M.MASKS[M.parseName(nm)[0]][0]);
        const stored = t2.masks._stack[li].get(nm);
        if (half !== (stored.dtype === '<f2')) halfOk = false;
        for (let k = 0; k < a.length; k++) {
            const want = half ? new Float16Array([a[k]])[0] : a[k];
            if (b[k] !== want) {
                same = false;
                break;
            }
        }
    }
}
T.ok('Terrain.save writes the bounded masks as float16 and the rest as float32 (api.py _cache_dtype)', halfOk);
T.ok('Terrain.load reads every mask back as save wrote it', same);
// run.js where: an expression naming a mask is evaluated on masks.js compute's GPU fields
const lv = t.levels[t.levels.length - 1];
const fields = new Fields(lv, null, R);
fields.set('h', R.field(lv.n, lv.n, 1, t.fields(lv.index).h));
fields.set('A', R.field(lv.n, lv.n, 1, t.fields(lv.index).A));
const w = await RUN.whereMask(E.parse('slope / 45'), fields, lv);
const got = await R.read(w);
w.destroy();
const m = await M.compute(fields, { cell: lv.cell, x0: lv.x0, y0: lv.y0, names: ['slope'] });
const slope = await R.read(m.slope);
m.dispose();
fields.dispose?.();
let worst = 0;
for (let k = 0; k < got.length; k++) worst = Math.max(worst, Math.abs(got[k] - Math.min(Math.max(slope[k] / 45, 0), 1)));
T.ok("run.js whereMask('slope / 45') reads masks.js compute's slope", worst <= 1e-6, `worst ${worst}`);
t.dispose?.();
t2.dispose?.();
T.extra = res;
G.shutdown();
const code = T.done(null);
Deno.writeTextFileSync(`${W.out('masks')}/api_masks_test.json`, JSON.stringify({ test: T.title, date: new Date().toISOString(),
    checks: T.rows.length, failed: T.rows.filter((r) => !r.passed).map((r) => r.check), ...res, rows: T.rows }, null, 1));
Deno.exit(code);
