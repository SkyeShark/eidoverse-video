// text_3d.js
//
// Extruded 3D text from any TTF baked into the sandbox. Wraps three's
// TextGeometry + a runtime TTF → typeface-JSON converter (via
// opentype.js) so agents don't have to ship pre-converted font files.
//
// Use this when you want actual 3D-extruded letters — title cards,
// hero text, branded screen content, glyphs the camera can fly through.
// For flat HUD overlays / lower-thirds / subtitles, use satori_ui.mjs
// instead (HTML/CSS to texture, much cheaper).
//
// Agent API
// ---------
//
//   import { createText3D } from globalThis.EIDOVERSE_DIR + 'text_3d.js';
//
//   const title = await createText3D("EIDOVERSE", {
//       fontPath: '/usr/share/fonts/truetype/custom/Audiowide-Regular.ttf',
//       size: 1.2,
//       depth: 0.18,             // extrusion thickness; 0 = flat geometry
//       curveSegments: 6,
//       bevelEnabled: true,
//       bevelSize: 0.02,
//       bevelThickness: 0.02,
//       material: new THREE.MeshStandardNodeMaterial({
//           color: 0xff2d95, metalness: 0.6, roughness: 0.3,
//           emissive: 0xff2d95, emissiveIntensity: 0.4,
//       }),
//       center: true,            // recenter geometry around origin
//   });
//   title.position.set(0, 2, -5);
//   scene.add(title);
//
// Available fonts (baked into the sandbox at /usr/share/fonts/truetype/custom/):
//   - Audiowide-Regular.ttf       — wide sci-fi display
//   - BlackOpsOne-Regular.ttf     — heavy military-stencil
//   - CaveatBrush-Regular.ttf     — brush handwriting
//   - Creepster-Regular.ttf       — horror display
//   - Exo2.ttf                    — modern geometric sans
//   - Kalam-Bold.ttf / Regular    — informal handwriting
//   - Michroma-Regular.ttf        — wide techno mono
//   - Monoton-Regular.ttf         — striped retro display
//   - Orbitron.ttf                — futuristic sans
//   - PixelifySans.ttf            — pixel sans-serif
//   - PressStart2P-Regular.ttf    — 8-bit pixel
//   - Rajdhani-Bold.ttf           — narrow techno
//   - SedgwickAveDisplay-Regular  — script display
//   - ShareTechMono-Regular.ttf   — techno monospace
//   - Silkscreen-Bold.ttf / Regular — pixel bitmap
//   - SpecialElite-Regular.ttf    — typewriter
//   - VT323-Regular.ttf           — CRT terminal
//
// Or pass any other TTF path you've fetched / placed in your work dir.

import opentype from 'npm:opentype.js@1.3.4';
import { Font } from 'npm:three@0.184.0/addons/loaders/FontLoader.js';
import { TextGeometry } from 'npm:three@0.184.0/addons/geometries/TextGeometry.js';

const _fontCache = new Map();

async function loadFont(fontPath) {
    if (_fontCache.has(fontPath)) return _fontCache.get(fontPath);

    const buf = await Deno.readFile(fontPath);
    const otf = opentype.parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));

    // Convert opentype.js glyph paths → Facetype JSON shape that
    // three.js's Font class consumes. The shape is documented in
    // three/examples/jsm/loaders/FontLoader.js: each glyph has
    // { ha (horizontal advance), x_min, x_max, o (path commands as
    // a single string of tokens) }.
    const glyphs = {};
    for (const g of Object.values(otf.glyphs.glyphs)) {
        const ch = g.unicode == null ? null : String.fromCharCode(g.unicode);
        if (ch == null) continue;
        const path = g.getPath(0, 0, otf.unitsPerEm);
        const tokens = [];
        for (const cmd of path.commands) {
            // Three.js's parser uses negated Y because it draws from top.
            switch (cmd.type) {
                case 'M': tokens.push('m', cmd.x, -cmd.y); break;
                case 'L': tokens.push('l', cmd.x, -cmd.y); break;
                case 'Q': tokens.push('q', cmd.x, -cmd.y, cmd.x1, -cmd.y1); break;
                case 'C': tokens.push('b', cmd.x, -cmd.y, cmd.x1, -cmd.y1, cmd.x2, -cmd.y2); break;
                case 'Z': break; // Three.js auto-closes
            }
        }
        glyphs[ch] = {
            ha: g.advanceWidth,
            x_min: g.xMin ?? 0,
            x_max: g.xMax ?? 0,
            o: tokens.join(' '),
        };
    }

    const json = {
        glyphs,
        familyName: otf.names.fontFamily?.en ?? otf.names.fullName?.en ?? 'Unknown',
        ascender: otf.ascender,
        descender: otf.descender,
        underlinePosition: -100,
        underlineThickness: 50,
        boundingBox: {
            yMin: otf.tables.head?.yMin ?? -200,
            xMin: otf.tables.head?.xMin ?? -100,
            yMax: otf.tables.head?.yMax ?? 1000,
            xMax: otf.tables.head?.xMax ?? 1000,
        },
        resolution: otf.unitsPerEm,
        original_font_information: { format: 0 },
    };

    const font = new Font(json);
    _fontCache.set(fontPath, font);
    return font;
}

export async function createText3D(text, opts = {}) {
    if (!opts.fontPath) throw new Error('createText3D: fontPath is required');
    const THREE = globalThis.THREE;

    const font = await loadFont(opts.fontPath);
    const geo = new TextGeometry(text, {
        font,
        size: opts.size ?? 1.0,
        depth: opts.depth ?? 0.15,
        curveSegments: opts.curveSegments ?? 6,
        bevelEnabled: opts.bevelEnabled ?? true,
        bevelThickness: opts.bevelThickness ?? 0.02,
        bevelSize: opts.bevelSize ?? 0.015,
        bevelOffset: opts.bevelOffset ?? 0,
        bevelSegments: opts.bevelSegments ?? 3,
    });
    if (opts.center !== false) geo.center();

    const mat = opts.material ?? new THREE.MeshStandardNodeMaterial({
        color: 0xffffff, metalness: 0.4, roughness: 0.3,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = mesh.receiveShadow = true;
    return mesh;
}
