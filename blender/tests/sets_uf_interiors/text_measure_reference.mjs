// text_measure_reference.mjs: Skia's measureText (@napi-rs/canvas, the engine's canvas) for runs of text in the
// interiors' fonts, as JSON on stdout, for test_art_parity.py's text layout check (Fonts.layout: unhinted advances +
// GPOS pair kerning). The fonts are registered as interiors_lib.js registers them.
//
//   deno run --no-config --no-lock --cached-only -A text_measure_reference.mjs '<json [[font, text], ...]>'
import * as L from '../../../eidoverse/sets/unknown_force/interiors_lib.js';

const N = await L.napi();
const [cv, ctx] = L.canvas(N, 8, 8);
const runs = JSON.parse(Deno.args[0]);
console.log(JSON.stringify(runs.map(([font, text]) => { ctx.font = font; return ctx.measureText(text).width; })));
