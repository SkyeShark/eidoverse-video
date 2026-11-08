// art_reference.mjs: the WebGPU edition's canvas art for the two UNKNOWN FORCE interiors, drawn by the ORIGINAL
// modules (eidoverse/sets/unknown_force/*_art.js + interiors_lib.js) with @napi-rs/canvas, saved as PNG references for
// the Blender port's parity test (test_art_parity.py). Also dumps the numbers the pure helpers must reproduce: the
// mulberry32 streams, a build_mips checksum and the shared noise texture.
//
//   deno run --no-config --no-lock --node-modules-dir=none --cached-only -A art_reference.mjs <out_dir>
import * as L from '../../../eidoverse/sets/unknown_force/interiors_lib.js';
import * as QA from '../../../eidoverse/sets/unknown_force/quiet_room_art.js';
import * as SA from '../../../eidoverse/sets/unknown_force/showroom_art.js';

const out = Deno.args[0] || './out/ref';
Deno.mkdirSync(out, { recursive: true });
const N = await L.napi();
const save = async (cv, name) => {
    const png = await cv.encode('png');
    Deno.writeFileSync(`${out}/${name}.png`, png);
};

// the quiet room's five boards, exactly as quiet_room.js sizes and seeds them (960 texels per metre)
for (const [name, b] of Object.entries(QA.BOARDS)) {
    const W = Math.round(b.w * 960 / 8) * 8, H = Math.round(b.h * 960 / 8) * 8;
    const [cv, ctx] = L.canvas(N, W, H);
    b.draw(ctx, W, H, L.rng(b.seed));
    await save(cv, `board_${name}`);
}
// the showroom's printed matter, at the sizes showroom.js draws them
{
    const [c, x] = L.canvas(N, SA.SCREEN.W, SA.SCREEN.H); SA.drawEngineSheet(x, c.width, c.height); await save(c, 'engine_sheet');
}
{ const [c, x] = L.canvas(N, 920, 1240); SA.drawWarning(x, 920, 1240); await save(c, 'warning'); }
{ const [c, x] = L.canvas(N, 512, 180); SA.drawRatingPlate(x, 512, 180); await save(c, 'rating_plate'); }
{ const [c, x] = L.canvas(N, 256, 256); SA.drawDial(x, 256, 256); await save(c, 'dial'); }
// the marker primitives alone on a small sheet (one per row), so a mismatch can be pinned to one of them
{
    const [c, x] = L.canvas(N, 1200, 700);
    x.fillStyle = '#ffffff'; x.fillRect(0, 0, 1200, 700);
    const r = L.rng(7);
    L.marker(x, 'P(DOOM | SHIP) = 0.37', 40, 110, { size: 90, r });
    L.marker(x, 'centred, rotated', 600, 230, { size: 60, r, align: 'center', rot: -0.08, color: '#15171b' });
    L.mline(x, [[40, 300], [400, 330], [700, 280], [1150, 320]], { w: 10, r });
    L.mline(x, [[40, 380], [1150, 380]], { w: 6, r, dashed: [28, 22], color: '#a50d18' });
    L.marrow(x, 60, 600, 400, 460, { w: 7, r, head: 30, color: '#15171b' });
    L.mring(x, 800, 560, 220, 90, { w: 8, r });
    await save(c, 'primitives');
}
// numbers: rng streams, build_mips checksum, noise texture
const streams = {};
for (const s of [1, 101, 202, 4242, 0xdeadbeef]) { const r = L.rng(s); streams[s] = Array.from({ length: 12 }, () => r()); }
const W = 7, H = 5, data = new Uint8Array(W * H * 4);
for (let i = 0; i < data.length; i++) data[i] = (i * 37 + 11) % 256;
const mips = L.buildMips(data, W, H, false), mipsA = L.buildMips(data, W, H, true);
const sum = (lv) => lv.map((l) => [l.width, l.height, Array.from(l.data).reduce((a, b) => a + b, 0)]);
const THREE = { DataTexture: class { constructor(d, w, h) { this.image = { data: d, width: w, height: h }; this.userData = {}; } }, RGBAFormat: 0,
    UnsignedByteType: 0, SRGBColorSpace: 'srgb', NoColorSpace: '', RepeatWrapping: 1, ClampToEdgeWrapping: 0,
    LinearFilter: 0, LinearMipmapLinearFilter: 0 };
const nt = L.noiseTexture(THREE);
Deno.writeFileSync(`${out}/noise_rgba.bin`, nt.image.data);
Deno.writeTextFileSync(`${out}/numbers.json`, JSON.stringify({ streams, mips: sum(mips), mipsAlpha: sum(mipsA),
    smooth: [0, 0.25, 0.5, 0.9].map(L.smooth), ramp: [L.ramp(0.3, 0.2, 0.4), L.ramp(-1, 0, 1)] }, null, 1));
console.log('[art_reference] wrote', out);
