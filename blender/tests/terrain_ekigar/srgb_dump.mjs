// Ekigar's sRGB helpers (src/export/ops.js): the SRGB_TO_LINEAR table and linearToSRGB at a few values, as JSON on
// stdout, for test_bake_parity.py.
//     deno run --no-config --no-lock -A srgb_dump.mjs <ekigar root>
const root = Deno.args[0].replace(/\\/g, '/');
const m = await import('file:///' + root + '/src/export/ops.js');
const xs = [-0.2, 0, 0.001, 0.0031308, 0.004, 0.05, 0.2, 0.5, 0.75, 1, 1.5];
console.log(JSON.stringify({ table: Array.from(m.SRGB_TO_LINEAR), xs, oetf: xs.map(m.linearToSRGB) }));
