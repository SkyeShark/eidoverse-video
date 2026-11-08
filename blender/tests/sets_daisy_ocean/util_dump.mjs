// util_dump.mjs <out.json>: the untouched eidoverse/sets/ocean/util.js run headless: rng streams, the shot maths and
// buildMips on a fixed odd-sized RGBA8 image, dumped for test_util_parity.py.
//   deno run --no-config --no-lock -A util_dump.mjs <out.json>
const here = new URL('.', import.meta.url);
const U = await import(new URL('../../../eidoverse/sets/ocean/util.js', here).href);
const out = { rng: {}, maths: [], mips: [] };
for (const seed of [1, 5, 11, 23, 29, 2026]) {
    const R = U.rng(seed);
    out.rng[seed] = Array.from({ length: 64 }, () => R());
}
for (let i = 0; i < 200; i++) {
    const u = -2 + i * 0.05, a = 0.3 + (i % 7) * 0.4, b = a + 0.2 + (i % 5) * 0.5;
    out.maths.push([u, a, b, U.clamp01(u), U.smooth(u), U.lerp(a, b, u), U.seg(u, a, b), U.ease(u, a, b)]);
}
// a 37 x 23 RGBA8 image from a fixed LCG (odd edges exercise the clamped taps)
const W = 37, H = 23, data = new Uint8Array(W * H * 4);
let s = 12345;
for (let i = 0; i < data.length; i++) { s = (Math.imul(s, 1103515245) + 12345) >>> 0; data[i] = (s >>> 16) & 255; }
out.src = { w: W, h: H, data: Array.from(data) };
for (const L of U.buildMips(data, W, H)) out.mips.push({ w: L.width, h: L.height, data: Array.from(L.data) });
out.assets = { OCEAN_ASSETS: U.OCEAN_ASSETS, MODELS: U.MODELS, ENGINE_ASSETS: U.ENGINE_ASSETS };
Deno.writeTextFileSync(Deno.args[0], JSON.stringify(out));
console.log('[util_dump] wrote', Deno.args[0]);
