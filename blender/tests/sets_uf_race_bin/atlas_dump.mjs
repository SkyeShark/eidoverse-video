// atlas_dump.mjs: draws the WebGPU edition's page atlas (eidoverse/sets/unknown_force/bin_pages.js, untouched) with
// the fonts parole.js registers, on @napi-rs/canvas, at a chosen scale, for canvas_parity.py to compare with the
// Blender port's own atlas (bin_pages.draw_page_atlas).
//   cd <worktree> && deno run --no-config --no-lock --cached-only -A blender/tests/sets_uf_race_bin/atlas_dump.mjs [scale=0.5]
// Writes blender/tests/sets_uf_race_bin/out/parity/bin_atlas_<cw>x<ch>.png.
const root = Deno.cwd().replace(/\\/g, '/');
const eido = new URL('file:///' + root.replace(/^\/+/, '') + '/eidoverse/');
const PAROLE = await import(new URL('parole.js', eido).href);
const NAPI = await PAROLE.registerFonts();
const PAGES = await import(new URL('sets/unknown_force/bin_pages.js', eido).href);
const scale = Number(Deno.args[0] ?? 0.5);
const cw = Math.round(682 * scale), ch = Math.round(1024 * scale);
const cv = PAGES.drawPageAtlas((w, h) => NAPI.createCanvas(w, h), { cols: 6, rows: 4, cw, ch });
const outDir = root + '/blender/tests/sets_uf_race_bin/out/parity';
await Deno.mkdir(outDir, { recursive: true });
await Deno.writeFile(`${outDir}/bin_atlas_${cw}x${ch}.png`, cv.toBuffer('image/png'));
console.log('[atlas_dump] wrote', `${outDir}/bin_atlas_${cw}x${ch}.png`);
Deno.exit(0);
