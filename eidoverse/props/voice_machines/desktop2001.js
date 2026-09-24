// desktop2001.js — a 2001 desktop PC (beige mid-tower, 17" CRT, powered speakers, 104-key keyboard, wheel mouse)
// for DAISY's museum of voices. The CRT shows an early-2000s desktop: a generic green hill under a blue sky (drawn
// here, not the real wallpaper), a Luna-blue taskbar whose Start button carries our homage of the four-tile flag, and
// a small Narrator dialog the film fills with text. The XP sticker on the tower and the flag keys are baked homages.
//
//   const { build } = await import(new URL('props/voice_machines/desktop2001.js', EIDOVERSE_DIR).href);
//   const pc = await build(THREE, {});
//   scene.add(pc.group);
//   pc.parts.screen.setText('reading screens');        // the dialog's message (\n for a second line)
//   // per frame: pc.update(t, { power: 0..1, voice: 0..1 })
//   //   power = CRT raster (switch-on) + power LEDs;  voice = its own voice → the screen brightens, the speaker
//   //   cloth glows from within, the tower's drive light flickers with the speech
//
// Pack: eidoverse/assets/models/voice_machines/ (README.md, SOURCES.md).
// Geometry + materials: the pack's desktop2001.glb from blender/build_desktop2001.py — the tower body with cover seams,
// PSU and slot covers, its front bezel moulding (bays, floppy, CD-ROM with tray/eject/jack/volume, power + reset,
// LED windows, intake slots, sticker pocket); the CRT with a drafted opening, control strip, smooth tapered vented
// hood and swivel foot; speakers with fabric grilles (AmbientCG Fabric082A), knob and LED; the keyboard (three
// drafted wells, 104 dished keys, legends, lock LEDs); the mouse; cables. AmbientCG scans, AO grime, edge wear baked.
// Metres, +Y up, resting on y = 0, facing +Z.
// parts: monitor, tower, keyboard, speakers, screen {mesh, setText, text, power, screen}, leds {…}, speaker {mesh, set(v)}.
// Draw calls: ~16 (5 baked sets, the screen, 10 LED lenses).

export async function build(THREE, opts = {}) {
    const { title = 'Narrator', clock = '10:23 PM' } = opts;
    const K = await eraKit(THREE);
    const { uniform, texture: tex } = THREE;
    const disposables = [];
    const track = (x) => { disposables.push(x); return x; };
    const group = new THREE.Group(); group.name = 'desktop2001';
    const root = await K.loadGLB(new URL('../../assets/models/voice_machines/desktop2001.glb', import.meta.url));
    const meshes = [];
    root.traverse((o) => { if (o.isMesh) meshes.push(o); });
    const one = (n) => { const m = meshes.find((x) => x.name === n); if (!m) throw new Error('[desktop2001] GLB is missing ' + n); return m; };
    const mon = one('pc_mon'), tower = one('pc_tower'), kb = one('pc_kb'), spk = one('pc_spk');
    for (const m of [mon, tower, kb, spk]) { m.material = track(K.bakedMaterial(m.material)); m.castShadow = m.receiveShadow = true; group.add(m); }
    // speaker cloth: its baked weave, lit from within by the voice
    const cloth = one('glowcloth_spk');
    const clothLevel = uniform(0);
    const cm = track(K.bakedMaterial(cloth.material));
    // warm light behind the weave, brightest over each driver and falling off to the panel edges; the open
    // threads (dark in the scan) let more of it through
    const pos = cloth.geometry.attributes.position, mid = (() => { let a = Infinity, b = -Infinity; for (let i = 0; i < pos.count; i++) { a = Math.min(a, pos.getX(i)); b = Math.max(b, pos.getX(i)); } return (a + b) / 2; })();
    const centre = (side) => { const c = new THREE.Vector3(); let n = 0; for (let i = 0; i < pos.count; i++) if ((pos.getX(i) < mid) === side) { c.x += pos.getX(i); c.y += pos.getY(i); c.z += pos.getZ(i); n++; } return c.divideScalar(Math.max(1, n)); };
    const cL = centre(true), cR = centre(false);
    const P = THREE.positionLocal;
    const dL = P.sub(THREE.vec3(cL.x, cL.y + 0.012, cL.z)).length(), dR = P.sub(THREE.vec3(cR.x, cR.y + 0.012, cR.z)).length();
    const cone = THREE.smoothstep(0.075, 0.005, THREE.min(dL, dR));
    const weave = THREE.float(1).sub(tex(cm.map).r.mul(2.2)).clamp(0.25, 1.0);
    cm.emissiveNode = K.lin('#ffae5c').mul(weave).mul(cone.mul(0.85).add(0.15)).mul(clothLevel).mul(1.25);
    cloth.material = cm; group.add(cloth);
    // LEDs
    const leds = {};
    const led = (name, col, lens) => { const L = K.ledMaterial(col, lens); track(L.mat); const m = one(name); m.material = L.mat; group.add(m); leds[name.replace(/^led_/, '')] = { mesh: m, level: L.level, set(v) { L.level.value = Math.max(0, v); } }; };
    led('led_mon', '#46ff5a', '#1a5a24'); led('led_tw_power', '#46ff5a', '#1a5a24'); led('led_tw_hdd', '#ffb020', '#6a4a10');
    led('led_tw_cd', '#46ff5a', '#1a5a24'); led('led_spk', '#46ff5a', '#1a5a24');
    for (let i = 0; i < 3; i++) led('led_kb' + i, '#46ff5a', '#1a5a24');

    // the CRT: the desktop canvas (1024 × 768) under the glass
    const TW = 0.345, TH = 0.262;
    const power = uniform(1), gain = uniform(1);
    const scrState = { text: '', dirty: true };
    const scr = K.eraScreen({ width: TW, height: TH, px: 1024, draw: (ctx) => drawDesktop(ctx, scrState) });
    track(scr.tex);
    const tube = one('screen_crt');
    K.flipUV(tube.geometry);
    tube.material = track(K.screenMaterial({
        tex: scr.tex, power, gain: gain.mul(0.95), flipV: true, glass: '#0c0e0e', rough: 0.3, coatRough: 0.03,
        barrel: 0.012, scan: 0, corner: 0.02, vignette: 0.08, crtOn: true,
    }));
    group.add(tube);

    const setText = (s) => { const t = String(s ?? ''); if (t !== scrState.text) { scrState.text = t; scrState.dirty = true; } };
    setText(opts.text ?? 'reading screens');
    scr.redraw(0); scrState.dirty = false;
    const speaker = { mesh: cloth, set(v) { clothLevel.value = Math.max(0, v); } };
    const parts = { monitor: mon, tower, keyboard: kb, speakers: spk, screen: { mesh: tube, setText, get text() { return scrState.text; }, power, screen: scr.scr }, leds, speaker };
    function update(t, state = {}) {
        const p = Math.max(0, state.power ?? 1), v = Math.max(0, Math.min(1, state.voice ?? 0));
        const on = p > 0.02;
        power.value = p;
        gain.value = 1 + 0.25 * v;
        speaker.set(on ? v * 0.8 : 0);
        leds.mon.set(on ? 1 : 0.15);                                 // amber-ish standby is out of scope: dim green
        leds.tw_power.set(1); leds.spk.set(1); leds.kb0.set(1); leds.kb1.set(0); leds.kb2.set(0);
        // the drive light flickers with speech (deterministic in t)
        const flick = (Math.sin(t * 61.0) + Math.sin(t * 37.3 + 1.7)) > 0.6 ? 1 : 0.1;
        leds.tw_hdd.set(on && v > 0.15 ? flick : 0.02);
        leds.tw_cd.set(0);
        if (state.text !== undefined) setText(state.text);
        if (scrState.dirty) { scr.redraw(t); scrState.dirty = false; }
    }
    function dispose() {
        group.traverse((o) => { if (o.isMesh) o.geometry.dispose(); });
        for (const d of disposables) d.dispose?.();
        scr.scr.mesh.geometry.dispose(); scr.scr.material.dispose();
    }
    return { group, parts, update, dispose };

    // ── the desktop: sky, clouds, the hill, icons, taskbar with Start + tray, the Narrator dialog, a pointer ──
    function drawDesktop(ctx, st) {
        const W = 1024, H = 768, TB = 30;
        // sky
        const sky = ctx.createLinearGradient(0, 0, 0, H * 0.7);
        sky.addColorStop(0, '#1f5fd6'); sky.addColorStop(0.55, '#4d93ec'); sky.addColorStop(1, '#a9d2fa');
        ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);
        // soft clouds (seeded, deterministic)
        const r = K.rng(2001);
        ctx.save(); ctx.filter = 'blur(10px)';
        for (let i = 0; i < 14; i++) {
            const cx = r() * W, cy = 60 + r() * 260, rw = 60 + r() * 150;
            ctx.fillStyle = `rgba(255,255,255,${0.25 + r() * 0.35})`;
            for (let k = 0; k < 5; k++) { ctx.beginPath(); ctx.ellipse(cx + (k - 2) * rw * 0.35, cy + (r() - 0.5) * 18, rw * 0.45, rw * 0.22, 0, 0, Math.PI * 2); ctx.fill(); }
        }
        ctx.restore();
        // a far hill and the near green hill (our own gentle rise, left to right)
        const hill = (y0, amp, ph, c0, c1) => {
            const g = ctx.createLinearGradient(0, y0 - amp, 0, H);
            g.addColorStop(0, c0); g.addColorStop(1, c1);
            ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(0, H);
            for (let x = 0; x <= W; x += 8) ctx.lineTo(x, y0 - amp * Math.sin((x / W) * Math.PI * 0.9 + ph) - amp * 0.25 * Math.sin((x / W) * 5.1 + ph * 3));
            ctx.lineTo(W, H); ctx.closePath(); ctx.fill();
        };
        hill(H * 0.66, 38, 1.9, '#5f9b3a', '#2f6a1e');
        hill(H * 0.78, 120, 0.55, '#7fcf3f', '#2e7d18');
        // light on the grass: a few streaks
        ctx.save(); ctx.globalAlpha = 0.12; ctx.strokeStyle = '#eaffc0'; ctx.lineWidth = 2;
        for (let i = 0; i < 60; i++) { const x = r() * W, y = H * 0.62 + r() * H * 0.3; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 3, y - 7); ctx.stroke(); }
        ctx.restore();
        // desktop icons
        const icon = (x, y, kind, label) => {
            ctx.save();
            if (kind === 'pc') { ctx.fillStyle = '#dfe6ee'; ctx.fillRect(x + 6, y + 4, 36, 26); ctx.fillStyle = '#3b82d8'; ctx.fillRect(x + 9, y + 7, 30, 20); ctx.fillStyle = '#c9d2dc'; ctx.fillRect(x + 16, y + 31, 16, 5); ctx.fillRect(x + 10, y + 36, 28, 4); }
            else if (kind === 'docs') { ctx.fillStyle = '#f4d56b'; ctx.beginPath(); ctx.moveTo(x + 4, y + 10); ctx.lineTo(x + 18, y + 10); ctx.lineTo(x + 22, y + 6); ctx.lineTo(x + 44, y + 6); ctx.lineTo(x + 44, y + 38); ctx.lineTo(x + 4, y + 38); ctx.closePath(); ctx.fill(); ctx.fillStyle = '#fff'; ctx.fillRect(x + 12, y + 12, 24, 20); }
            else { ctx.fillStyle = '#e8eef4'; ctx.beginPath(); ctx.moveTo(x + 10, y + 10); ctx.lineTo(x + 38, y + 10); ctx.lineTo(x + 34, y + 40); ctx.lineTo(x + 14, y + 40); ctx.closePath(); ctx.fill(); ctx.strokeStyle = '#8aa'; ctx.lineWidth = 2; for (let k = 0; k < 3; k++) { ctx.beginPath(); ctx.moveTo(x + 17 + k * 7, y + 14); ctx.lineTo(x + 18 + k * 6, y + 37); ctx.stroke(); } }
            ctx.font = '13px Tahoma, Verdana, sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = '#000'; ctx.fillText(label, x + 25, y + 57); ctx.fillStyle = '#fff'; ctx.fillText(label, x + 24, y + 56);
            ctx.restore();
        };
        icon(18, 18, 'pc', 'My Computer'); icon(18, 98, 'docs', 'My Documents'); icon(18, H - TB - 90, 'bin', 'Recycle Bin');
        // taskbar
        const tb = ctx.createLinearGradient(0, H - TB, 0, H);
        tb.addColorStop(0, '#3f8cf3'); tb.addColorStop(0.12, '#2463da'); tb.addColorStop(0.9, '#1c4fc4'); tb.addColorStop(1, '#163e9e');
        ctx.fillStyle = tb; ctx.fillRect(0, H - TB, W, TB);
        // start button: green pill with the flag and an italic "start"
        const sg = ctx.createLinearGradient(0, H - TB, 0, H);
        sg.addColorStop(0, '#5eb95e'); sg.addColorStop(0.2, '#3c9a3c'); sg.addColorStop(1, '#2d7d2d');
        ctx.fillStyle = sg; ctx.beginPath(); ctx.moveTo(0, H - TB); ctx.lineTo(88, H - TB); ctx.quadraticCurveTo(106, H - TB, 106, H - TB / 2); ctx.quadraticCurveTo(106, H, 88, H); ctx.lineTo(0, H); ctx.closePath(); ctx.fill();
        drawFlag(ctx, 10, H - TB + 5, 22, 20);
        ctx.font = 'italic bold 21px "Franklin Gothic Medium", Trebuchet MS, Tahoma, sans-serif'; ctx.fillStyle = '#fff'; ctx.textAlign = 'left';
        ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowOffsetX = 1; ctx.shadowOffsetY = 1; ctx.fillText('start', 38, H - 9); ctx.shadowColor = 'transparent';
        // the running task + tray + clock
        ctx.fillStyle = '#3c80ef'; K.rr(ctx, 118, H - TB + 3, 160, TB - 6, 3); ctx.fill();
        ctx.font = '12px Tahoma, sans-serif'; ctx.fillStyle = '#fff'; ctx.fillText(title, 142, H - 11);
        ctx.fillStyle = '#e8eaf0'; ctx.beginPath(); ctx.arc(130, H - TB / 2, 5, 0, Math.PI * 2); ctx.fill();
        const tray = ctx.createLinearGradient(0, H - TB, 0, H);
        tray.addColorStop(0, '#16a7f4'); tray.addColorStop(1, '#0d7fd8');
        ctx.fillStyle = tray; ctx.fillRect(W - 118, H - TB, 118, TB);
        ctx.font = '12px Tahoma, sans-serif'; ctx.fillStyle = '#fff'; ctx.textAlign = 'right'; ctx.fillText(clock, W - 10, H - 10);
        ctx.fillStyle = '#ffd24a'; ctx.beginPath(); ctx.arc(W - 96, H - TB / 2, 5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#e6e6e6'; ctx.fillRect(W - 82, H - TB / 2 - 5, 9, 10);
        // the dialog (big enough to read on film)
        const dw = 600, dh = 250, dx = Math.round((W - dw) / 2) + 40, dy = 188;
        ctx.save();
        ctx.shadowColor = 'rgba(0,0,0,0.35)'; ctx.shadowBlur = 16; ctx.shadowOffsetX = 5; ctx.shadowOffsetY = 6;
        ctx.fillStyle = '#0831d9'; K.rr(ctx, dx, dy, dw, dh, 8); ctx.fill();
        ctx.restore();
        const tbar = ctx.createLinearGradient(0, dy, 0, dy + 34);
        tbar.addColorStop(0, '#3a8cf6'); tbar.addColorStop(0.15, '#0a5ee4'); tbar.addColorStop(0.85, '#0550d6'); tbar.addColorStop(1, '#0342b8');
        ctx.fillStyle = tbar; K.rr(ctx, dx, dy, dw, 40, 8); ctx.fill(); ctx.fillRect(dx, dy + 20, dw, 20);
        ctx.fillStyle = '#ece9d8'; ctx.fillRect(dx + 4, dy + 38, dw - 8, dh - 42);
        ctx.font = 'bold 17px Tahoma, Trebuchet MS, sans-serif'; ctx.fillStyle = '#fff'; ctx.textAlign = 'left';
        ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowOffsetX = 1; ctx.shadowOffsetY = 1; ctx.fillText(title, dx + 34, dy + 27); ctx.shadowColor = 'transparent';
        drawSpeakerGlyph(ctx, dx + 10, dy + 11, 18);
        ctx.fillStyle = '#e04a2a'; K.rr(ctx, dx + dw - 32, dy + 7, 25, 25, 4); ctx.fill();
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(dx + dw - 26, dy + 13); ctx.lineTo(dx + dw - 13, dy + 26); ctx.moveTo(dx + dw - 13, dy + 13); ctx.lineTo(dx + dw - 26, dy + 26); ctx.stroke();
        drawSpeakerGlyph(ctx, dx + 34, dy + 78, 64);
        // the message: large Tahoma, wrapped to the panel
        const lines = [];
        ctx.font = 'bold 44px Tahoma, Verdana, sans-serif';
        for (const para of (st.text || '').split('\n')) {
            let cur = '';
            for (const w of para.split(/\s+/)) { const tst = cur ? cur + ' ' + w : w; if (ctx.measureText(tst).width > dw - 170 && cur) { lines.push(cur); cur = w; } else cur = tst; }
            lines.push(cur);
        }
        ctx.fillStyle = '#111'; ctx.textAlign = 'left';
        lines.slice(0, 3).forEach((ln, i) => ctx.fillText(ln, dx + 128, dy + 108 + i * 52 - (Math.min(3, lines.length) - 1) * 18));
        // OK button
        ctx.fillStyle = '#f4f3ee'; K.rr(ctx, dx + dw - 132, dy + dh - 52, 110, 34, 4); ctx.fill();
        ctx.strokeStyle = '#003c74'; ctx.lineWidth = 1.5; K.rr(ctx, dx + dw - 132, dy + dh - 52, 110, 34, 4); ctx.stroke();
        ctx.font = '17px Tahoma, sans-serif'; ctx.fillStyle = '#000'; ctx.textAlign = 'center'; ctx.fillText('OK', dx + dw - 77, dy + dh - 29);
        // pointer
        const px = dx + dw - 70, py = dy + dh - 20;
        ctx.fillStyle = '#fff'; ctx.strokeStyle = '#000'; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px, py + 22); ctx.lineTo(px + 5, py + 17); ctx.lineTo(px + 9, py + 26); ctx.lineTo(px + 12, py + 25); ctx.lineTo(px + 8, py + 16); ctx.lineTo(px + 15, py + 16); ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    function drawFlag(ctx, x, y, w, h) {              // the four waving tiles, homage
        const cols = ['#f25022', '#7fba00', '#00a4ef', '#ffb900'];
        const wave = (u) => Math.sin(u * Math.PI * 1.1 + 0.3) * 0.07;
        [[0, 0], [1, 0], [0, 1], [1, 1]].forEach(([i, j], k) => {
            const u0 = i * 0.5 + (i ? 0.03 : 0), u1 = (i + 1) * 0.5 - (i ? 0 : 0.03), v0 = j * 0.5 + (j ? 0.03 : 0), v1 = (j + 1) * 0.5 - (j ? 0 : 0.03);
            ctx.fillStyle = cols[k]; ctx.beginPath();
            for (let s = 0; s <= 8; s++) { const u = u0 + (u1 - u0) * s / 8; const X = x + u * w - (v0 + wave(u)) * w * 0.06, Y = y + (v0 + wave(u)) * h; s ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); }
            for (let s = 8; s >= 0; s--) { const u = u0 + (u1 - u0) * s / 8; ctx.lineTo(x + u * w - (v1 + wave(u)) * w * 0.06, y + (v1 + wave(u)) * h); }
            ctx.closePath(); ctx.fill();
        });
    }
    function drawSpeakerGlyph(ctx, x, y, s) {           // Narrator's speaker-and-waves glyph
        ctx.save();
        ctx.fillStyle = '#e8e8e8'; ctx.strokeStyle = '#3a3a3a'; ctx.lineWidth = Math.max(1, s * 0.05);
        ctx.beginPath(); ctx.moveTo(x, y + s * 0.35); ctx.lineTo(x + s * 0.22, y + s * 0.35); ctx.lineTo(x + s * 0.5, y + s * 0.1); ctx.lineTo(x + s * 0.5, y + s * 0.9); ctx.lineTo(x + s * 0.22, y + s * 0.65); ctx.lineTo(x, y + s * 0.65); ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.strokeStyle = '#2a6fd6'; ctx.lineWidth = Math.max(1.2, s * 0.07);
        for (let k = 1; k <= 3; k++) { ctx.beginPath(); ctx.arc(x + s * 0.5, y + s * 0.5, s * 0.14 * k + s * 0.04, -0.7, 0.7); ctx.stroke(); }
        ctx.restore();
    }
}

// ===== ERA KIT BEGIN — shared helpers for the DAISY era-2 machines (identical copy in speakspell/c64/mac1984/dectalk/desktop2001; edit all five together) =====
async function eraKit(THREE) {
    const {
        Fn, uniform, texture, uv, vec2, vec3, vec4, float, mix, clamp, smoothstep, abs, max, dot, pow, normalize,
        positionLocal, normalLocal, positionWorld, normalWorldGeometry, normalViewGeometry, positionView, dFdx, dFdy,
        cameraPosition, modelWorldMatrix, cos, fwidth, length, min,
    } = THREE;
    const { RoundedBoxGeometry } = await import('npm:three@0.184.0/addons/geometries/RoundedBoxGeometry.js');
    const { mergeGeometries, mergeVertices } = await import('npm:three@0.184.0/addons/utils/BufferGeometryUtils.js');

    // deterministic rng (never Math.random)
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
    const lin = (hex) => { const c = new THREE.Color(hex); return vec3(c.r, c.g, c.b); };     // sRGB hex → linear vec3 node
    const makeCanvas = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };

    // ── CPU mip chains. The stack's auto-mipmap pass samples zero at non-base levels; explicit levels upload fine
    //    (same finding as render_scene.mjs _buildCpuMips). alphaWeighted: colour averaged by alpha, so transparent
    //    texels never darken a decal's edge.
    function buildMips(data, w, h, alphaWeighted) {
        const levels = [{ data, width: w, height: h }];
        let sw = w, sh = h, src = data;
        while (sw > 1 || sh > 1) {
            const dw = Math.max(1, sw >> 1), dh = Math.max(1, sh >> 1);
            const dst = new Uint8Array(dw * dh * 4);
            for (let y = 0; y < dh; y++) {
                const r0 = Math.min(sh - 1, y * 2) * sw, r1 = Math.min(sh - 1, y * 2 + 1) * sw;
                for (let x = 0; x < dw; x++) {
                    const c0 = Math.min(sw - 1, x * 2), c1 = Math.min(sw - 1, x * 2 + 1);
                    const a = (r0 + c0) * 4, b = (r0 + c1) * 4, c = (r1 + c0) * 4, d = (r1 + c1) * 4, o = (y * dw + x) * 4;
                    if (alphaWeighted) {
                        const wa = src[a + 3], wb = src[b + 3], wc = src[c + 3], wd = src[d + 3], ws = wa + wb + wc + wd;
                        for (let k = 0; k < 3; k++) {
                            dst[o + k] = ws > 0
                                ? Math.round((src[a + k] * wa + src[b + k] * wb + src[c + k] * wc + src[d + k] * wd) / ws)
                                : (src[a + k] + src[b + k] + src[c + k] + src[d + k] + 2) >> 2;
                        }
                        dst[o + 3] = (ws + 2) >> 2;
                    } else {
                        for (let k = 0; k < 4; k++) dst[o + k] = (src[a + k] + src[b + k] + src[c + k] + src[d + k] + 2) >> 2;
                    }
                }
            }
            levels.push({ data: dst, width: dw, height: dh });
            sw = dw; sh = dh; src = dst;
        }
        return levels;
    }

    // ── canvas → DataTexture. Rows are flipped on the CPU so canvas-top lands at v = 1 on three.js UVs, which means
    //    the texture works with texture(tex, anyUV) — no hidden repeat/offset matrix to lose on a custom UV.
    function canvasTexture(cv, o = {}) {
        const { srgb = true, mips = true, repeat = false, nearest = false, alphaWeighted = true } = o;
        const w = cv.width, h = cv.height;
        const tex = new THREE.DataTexture(new Uint8Array(w * h * 4), w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
        tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        tex.wrapS = tex.wrapT = repeat ? THREE.RepeatWrapping : THREE.ClampToEdgeWrapping;
        tex.magFilter = nearest ? THREE.NearestFilter : THREE.LinearFilter;
        tex.minFilter = mips ? THREE.LinearMipmapLinearFilter : THREE.LinearFilter;
        tex.generateMipmaps = false;
        tex.anisotropy = 8;
        tex.userData.noMips = true;
        tex.userData._era = { cv, mips, alphaWeighted };
        refreshCanvasTexture(tex);
        return tex;
    }
    function refreshCanvasTexture(tex) {
        const { cv, mips, alphaWeighted } = tex.userData._era;
        const w = cv.width, h = cv.height, row = w * 4;
        const src = cv.getContext('2d').getImageData(0, 0, w, h).data;
        const data = new Uint8Array(w * h * 4);
        for (let y = 0; y < h; y++) data.set(src.subarray((h - 1 - y) * row, (h - y) * row), y * row);
        tex.image = { data, width: w, height: h };
        if (mips) tex.mipmaps = buildMips(data, w, h, alphaWeighted);
        tex.needsUpdate = true;
    }

    // ── makeScreen (eidoverse/screen.js) owns the canvas → texture path for every in-world display. Its texture
    //    uploads canvas rows top-down (it flips through repeat/offset, which a custom-UV sample skips), so screen
    //    materials sample it at (u, 1 - v). This adds CPU mips after each redraw (no shimmer when minified).
    function eraScreen({ width, height, px, draw, nearest = false }) {
        if (typeof globalThis.makeScreen !== 'function') throw new Error('[era] makeScreen missing — load inside the eidoverse renderer');
        const scr = globalThis.makeScreen({ width, height, px, draw, auto: false, transparent: false });
        const tex = scr.texture;
        tex.generateMipmaps = false;
        tex.minFilter = THREE.LinearMipmapLinearFilter;
        tex.magFilter = nearest ? THREE.NearestFilter : THREE.LinearFilter;
        tex.anisotropy = 8;
        const remip = () => {
            const im = tex.image;
            if (im && im.data) tex.mipmaps = buildMips(im.data, im.width, im.height, false);
        };
        remip();
        const redraw = (t) => { scr.update(t); remip(); tex.needsUpdate = true; };
        return { scr, tex, redraw };
    }

    // ── one shared tiling noise (4 independent periodic fbm channels: R period 4, G 8, B 32, A 64 cells per tile)
    function noiseTexture() {
        const KEY = '__daisyEraNoise_v1';
        if (globalThis[KEY]) return globalThis[KEY];
        const N = 256, data = new Uint8Array(N * N * 4);
        const chans = [[4, 5, 11], [8, 4, 23], [32, 3, 37], [64, 2, 53]];
        for (let ch = 0; ch < 4; ch++) {
            const [P, oct, seed] = chans[ch], r = rng(seed), lats = [];
            for (let o = 0; o < oct; o++) {
                const p = P << o, L = new Float32Array(p * p);
                for (let i = 0; i < L.length; i++) L[i] = r();
                lats.push([p, L]);
            }
            for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
                let v = 0, amp = 0.5, tot = 0;
                for (let o = 0; o < oct; o++) {
                    const [p, L] = lats[o], fx = x / N * p, fy = y / N * p;
                    const xi = Math.floor(fx), yi = Math.floor(fy), xf = fx - xi, yf = fy - yi;
                    const X0 = xi % p, X1 = (xi + 1) % p, Y0 = (yi % p) * p, Y1 = ((yi + 1) % p) * p;
                    const u = xf * xf * (3 - 2 * xf), w = yf * yf * (3 - 2 * yf);
                    const a = L[Y0 + X0], b = L[Y0 + X1], c = L[Y1 + X0], d = L[Y1 + X1];
                    v += amp * (a + (b - a) * u + (c - a) * w + (a - b - c + d) * u * w);
                    tot += amp; amp *= 0.5;
                }
                data[(y * N + x) * 4 + ch] = Math.round(255 * v / tot);
            }
        }
        const tex = new THREE.DataTexture(data, N, N, THREE.RGBAFormat, THREE.UnsignedByteType);
        tex.colorSpace = THREE.NoColorSpace;
        tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
        tex.magFilter = THREE.LinearFilter;
        tex.minFilter = THREE.LinearMipmapLinearFilter;
        tex.generateMipmaps = false;
        tex.mipmaps = buildMips(data, N, N, false);
        tex.userData.noMips = true;
        tex.needsUpdate = true;
        globalThis[KEY] = tex;
        return tex;
    }
    const NOISE = noiseTexture();

    // object-space triplanar (the prop can roll in without the grain swimming)
    const triplanar = (scale) => {
        const p = positionLocal.mul(scale);
        const n = abs(normalLocal);
        const w = n.div(max(n.x.add(n.y).add(n.z), 1e-4));
        return texture(NOISE, p.yz).mul(w.x).add(texture(NOISE, p.xz).mul(w.y)).add(texture(NOISE, p.xy).mul(w.z));
    };
    // per-pixel curvature in 1/m (+ convex, − concave); reads the vertex normal, never the shading normal
    const curvature = () => {
        const dNx = dFdx(normalWorldGeometry), dPx = dFdx(positionWorld);
        const dNy = dFdy(normalWorldGeometry), dPy = dFdy(positionWorld);
        return dot(dNx, dPx).div(max(dot(dPx, dPx), 1e-12)).add(dot(dNy, dPy).div(max(dot(dPy, dPy), 1e-12)));
    };
    // surface-gradient bump (Mikkelsen) from a height node in metres → view-space normal
    const bumpNormal = (h) => {
        const N = normalViewGeometry;
        const dpx = dFdx(positionView), dpy = dFdy(positionView);
        const r1 = dpy.cross(N), r2 = N.cross(dpx);
        const det = dot(dpx, r1);
        const grad = det.sign().mul(dFdx(h).mul(r1).add(dFdy(h).mul(r2)));
        return normalize(abs(det).mul(N).sub(grad));
    };

    // ── moulded plastic: base colour + large-scale ageing (yellowing/fading, stronger on up-facing surfaces),
    //    mottling, grime in concave fillets, polished convex edges, a little dust on top, roughness speckle and a
    //    fine orange-peel bump. Optional printed decal (texture with alpha) through decalUV.
    function plastic(o = {}) {
        const {
            color = '#d6ccb0', aged = null, ageAmt = 0.3, grime = '#3e372d', grimeAmt = 0.5, dust = '#b9b3a4',
            dustAmt = 0.12, rough = 0.5, roughVar = 0.12, edge = 0.25, peel = 0.00006, scale = 1,
            decal = null, decalUV = null, decalRough = null, colorNode = null, emissive = null, clearcoat = 0,
            clearcoatRough = 0.12, side = THREE.FrontSide, mottle = 0.08,
        } = o;
        const mat = clearcoat > 0
            ? new THREE.MeshPhysicalNodeMaterial({ clearcoat, clearcoatRoughness: clearcoatRough, side })
            : new THREE.MeshStandardNodeMaterial({ side });
        mat.metalness = 0;
        const nb = triplanar(1.3 * scale);      // r: ~20 cm blotches, g: ~10 cm mottle
        const nm = triplanar(6.0 * scale);      // b: ~5 mm grime breakup, a: ~2.6 mm speckle
        const cv = curvature();
        const edgeM = smoothstep(0.25, 0.9, clamp(cv.mul(0.004), 0, 1));
        const cavM = smoothstep(0.2, 0.85, clamp(cv.mul(-0.004), 0, 1));
        const up = pow(clamp(normalWorldGeometry.y, 0, 1), 2.0);
        let c = colorNode || lin(color);
        c = c.mul(nb.g.sub(0.5).mul(mottle * 2).add(1.0));
        if (aged) c = mix(c, lin(aged), clamp(smoothstep(0.38, 0.72, nb.r.add(up.mul(0.22))).mul(ageAmt), 0, 1));
        c = mix(c, lin(grime), clamp(cavM.mul(grimeAmt).mul(nm.b.add(0.35)), 0, 1));
        c = mix(c, c.mul(1.12), edgeM.mul(edge));
        c = mix(c, lin(dust), clamp(up.mul(dustAmt).mul(smoothstep(0.3, 0.7, nm.r)), 0, 1));
        let r = float(rough).add(nm.a.sub(0.5).mul(roughVar * 2)).sub(edgeM.mul(0.12)).add(up.mul(dustAmt * 0.5));
        if (decal) {
            const duv = decalUV || uv();
            const d = texture(decal, duv);
            // faces mapped outside 0..1 (planarUVFacing) stay unprinted at every mip level
            const inside = THREE.step(0.0, duv.x).mul(THREE.step(0.0, duv.y)).mul(THREE.step(duv.x, 1.0)).mul(THREE.step(duv.y, 1.0));
            const da = d.a.mul(inside);
            c = mix(c, d.rgb, da);
            if (decalRough !== null) r = mix(r, float(decalRough), da);
        }
        mat.colorNode = c;
        mat.roughnessNode = clamp(r, 0.04, 1.0);
        if (peel > 0) mat.normalNode = bumpNormal(triplanar(42 * scale).b.mul(peel));
        if (emissive) mat.emissiveNode = emissive;
        return mat;
    }

    // ── a display behind glass: emissive image under a clear coat, so it reads as a lit screen and still catches
    //    reflections. tex = makeScreen texture (sample flipped) or a canvasTexture (flipV:false). Options:
    //    window [u0,v0,u1,v1] — where the image sits in this mesh's UV (outside: glass only);
    //    parallax (m) — image recessed behind the glass; barrel — CRT pincushion; scan — scanline count;
    //    corner — rounded tube mask radius (fraction of the window); gain — HDR multiplier (bloom).
    function screenMaterial(o) {
        const {
            tex, power, gain = 1.3, glass = '#0b0d0c', rough = 0.32, coat = 1.0, coatRough = 0.035, flipV = true,
            window: win = [0, 0, 1, 1], parallax = 0, faceSize = [1, 1], barrel = 0, scan = 0, scanAmt = 0.3,
            corner = 0, vignette = 0.0, tint = null, bleed = 0, glow = null,
            colorNode = null, roughnessNode = null, coatNode = null, crtOn = false,
        } = o;
        const mat = new THREE.MeshPhysicalNodeMaterial({ roughness: rough, metalness: 0, clearcoat: coat, clearcoatRoughness: coatRough });
        mat.colorNode = colorNode || lin(glass);
        if (roughnessNode) mat.roughnessNode = roughnessNode;
        if (coatNode) mat.clearcoatNode = coatNode;
        mat.emissiveNode = Fn(() => {
            const st = uv().toVar();
            if (parallax > 0) {
                const vW = normalize(cameraPosition.sub(positionWorld));
                const ax = normalize(modelWorldMatrix.mul(vec4(1, 0, 0, 0)).xyz);
                const ay = normalize(modelWorldMatrix.mul(vec4(0, 1, 0, 0)).xyz);
                const az = normalize(modelWorldMatrix.mul(vec4(0, 0, 1, 0)).xyz);
                const vz = max(dot(vW, az), 0.25);
                st.subAssign(vec2(dot(vW, ax).div(vz).mul(parallax / faceSize[0]), dot(vW, ay).div(vz).mul(parallax / faceSize[1])));
            }
            // into window space
            const w = vec2(st.x.sub(win[0]).div(win[2] - win[0]), st.y.sub(win[1]).div(win[3] - win[1])).toVar();
            if (barrel > 0) {
                const cc = w.sub(0.5);
                w.assign(cc.mul(float(1).add(dot(cc, cc).mul(barrel))).add(0.5));
            }
            const wm = w.toVar();                                   // the tube mask never squeezes
            let squeeze = float(1);
            if (crtOn) {   // CRT switch-on: the raster opens from a bright horizontal line as power rises
                squeeze = smoothstep(0.05, 0.7, power).mul(0.99).add(0.01);
                w.assign(vec2(w.x, w.y.sub(0.5).div(squeeze).add(0.5)));
            }
            const s = vec2(w.x, flipV ? float(1).sub(w.y) : w.y);
            const col = texture(tex, s).rgb.toVar();
            if (bleed > 0) {   // horizontal phosphor/chroma bleed: a cheap 3-tap smear
                const dx = float(bleed);
                col.assign(col.mul(0.6).add(texture(tex, s.add(vec2(dx, 0))).rgb.mul(0.2)).add(texture(tex, s.sub(vec2(dx, 0))).rgb.mul(0.2)));
            }
            if (scan > 0) {
                const ph = w.y.mul(scan * Math.PI * 2);
                const fade = clamp(float(1.0).sub(fwidth(w.y.mul(scan)).mul(1.4)), 0, 1);   // no moire when small
                col.mulAssign(float(1).sub(cos(ph).mul(0.5).add(0.5).mul(scanAmt).mul(fade)));
            }
            // inside-the-window mask with rounded corners (the tube's mask), soft edge
            const q = abs(wm.sub(0.5)).mul(2);                      // 0 centre → 1 window edge
            let dist;
            if (corner > 0) {
                const cr = float(corner * 2);
                const k = q.sub(float(1).sub(cr));
                dist = length(max(k, 0)).add(min(max(k.x, k.y), 0)).sub(cr);
            } else dist = max(q.x, q.y).sub(1);
            const inside = float(1).sub(smoothstep(-0.01, 0.003, dist));
            let out = col.mul(inside);
            if (crtOn) {   // outside the opened raster: dark; a collapsed raster burns brighter
                const qy = abs(w.y.sub(0.5)).mul(2);
                out = out.mul(float(1).sub(smoothstep(0.98, 1.0, qy))).mul(float(1).div(squeeze.mul(0.85).add(0.15)).min(3.0));
            }
            if (vignette > 0) out = out.mul(float(1).sub(dot(q, q).mul(vignette * 0.5)));
            if (tint) out = out.mul(lin(tint));
            if (glow) out = out.add(lin(glow).mul(inside).mul(0.02));
            return out.mul(power).mul(gain);
        })();
        return mat;
    }

    // ── small emissive indicator (LED) — a clear-coated dome whose emission is a uniform
    function ledMaterial(color, lensColor = null) {
        const level = uniform(0);
        const mat = new THREE.MeshPhysicalNodeMaterial({ roughness: 0.25, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.05 });
        mat.colorNode = lin(lensColor || color).mul(0.25);
        mat.emissiveNode = lin(color).mul(level).mul(2.2);
        return { mat, level };
    }

    // ── geometry helpers
    const rbox = (w, h, d, r, seg = 3) => {
        const g = new RoundedBoxGeometry(w, h, d, seg, Math.min(r, w / 2 - 1e-5, h / 2 - 1e-5, d / 2 - 1e-5));
        return g;
    };
    const roundedRectShape = (w, h, r, cx = 0, cy = 0, hole = false) => {
        const s = hole ? new THREE.Path() : new THREE.Shape();
        const x0 = cx - w / 2, y0 = cy - h / 2;
        r = Math.min(r, w / 2, h / 2);
        s.moveTo(x0 + r, y0);
        s.lineTo(x0 + w - r, y0); s.quadraticCurveTo(x0 + w, y0, x0 + w, y0 + r);
        s.lineTo(x0 + w, y0 + h - r); s.quadraticCurveTo(x0 + w, y0 + h, x0 + w - r, y0 + h);
        s.lineTo(x0 + r, y0 + h); s.quadraticCurveTo(x0, y0 + h, x0, y0 + h - r);
        s.lineTo(x0, y0 + r); s.quadraticCurveTo(x0, y0, x0 + r, y0);
        return s;
    };
    // bake a transform into a clone, keep only position/normal/uv, non-indexed (so anything merges)
    const bake = (geo, pos = [0, 0, 0], rot = [0, 0, 0], scl = [1, 1, 1]) => {
        let g = geo.index ? geo.toNonIndexed() : geo.clone();
        for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
        if (!g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
        g.morphAttributes = {};
        g.clearGroups();
        const m = new THREE.Matrix4().compose(new THREE.Vector3(...pos),
            new THREE.Quaternion().setFromEuler(new THREE.Euler(...rot)), new THREE.Vector3(...scl));
        g.applyMatrix4(m);
        return g;
    };
    // weld coincident vertices and recompute smooth normals (ExtrudeGeometry ships faceted normals); drops uv
    const smooth = (geo) => {
        const g = geo.index ? geo.toNonIndexed() : geo.clone();
        for (const k of Object.keys(g.attributes)) if (k !== 'position') g.deleteAttribute(k);
        const m = mergeVertices(g, 1e-6);
        m.computeVertexNormals();
        return m;
    };
    const merge = (list) => {
        const g = mergeGeometries(list, false);
        g.computeBoundingBox(); g.computeBoundingSphere();
        return g;
    };
    // planar UV from a local-space rectangle (x0,y0)-(x1,y1) on the XY plane; used for printed cards/keys
    const planarUV = (geo, x0, y0, x1, y1, axes = 'xy') => {
        const p = geo.attributes.position, uvA = new Float32Array(p.count * 2);
        const gu = axes[0] === 'x' ? (i) => p.getX(i) : axes[0] === 'y' ? (i) => p.getY(i) : (i) => p.getZ(i);
        const gv = axes[1] === 'x' ? (i) => p.getX(i) : axes[1] === 'y' ? (i) => p.getY(i) : (i) => p.getZ(i);
        for (let i = 0; i < p.count; i++) {
            uvA[i * 2] = (gu(i) - x0) / (x1 - x0);
            uvA[i * 2 + 1] = (gv(i) - y0) / (y1 - y0);
        }
        geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvA, 2));
        return geo;
    };
    // rounded-rectangle outline points (CCW, n per corner) centred at (cx, cy)
    const rrPoints = (w, h, r, n = 6, cx = 0, cy = 0) => {
        r = Math.min(r, w / 2 - 1e-6, h / 2 - 1e-6);
        const pts = [], cs = [[w / 2 - r, h / 2 - r, 0], [-w / 2 + r, h / 2 - r, 0.5], [-w / 2 + r, -h / 2 + r, 1], [w / 2 - r, -h / 2 + r, 1.5]];
        for (const [x, y, a0] of cs) for (let i = 0; i <= n; i++) {
            const a = (a0 + 0.5 * i / n) * Math.PI;
            pts.push([cx + x + Math.cos(a) * r, cy + y + Math.sin(a) * r]);
        }
        return pts;
    };
    // skin a surface through closed rings of equal point count (arrays of [x,y,z]); smooth normals; uv: u around, v across
    const loftRings = (rings, { flip = false } = {}) => {
        const n = rings[0].length, pos = [], uvs = [], idx = [];
        rings.forEach((ring, j) => ring.forEach((q, i) => { pos.push(q[0], q[1], q[2]); uvs.push(i / n, j / (rings.length - 1)); }));
        for (let j = 0; j < rings.length - 1; j++) for (let i = 0; i < n; i++) {
            const a = j * n + i, b = j * n + (i + 1) % n, c = (j + 1) * n + (i + 1) % n, d = (j + 1) * n + i;
            if (flip) idx.push(a, c, b, a, d, c); else idx.push(a, b, c, a, c, d);
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
        g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
        g.setIndex(idx);
        g.computeVertexNormals();
        return g;
    };
    // a keycap: rounded box whose top face is narrower than its base (sculpted-key taper), y up
    const keycap = (wB, dB, wT, dT, h, r = 0.0012) => {
        const g = rbox(wB, h, dB, r, 2), p = g.attributes.position;
        for (let i = 0; i < p.count; i++) {
            const t = (p.getY(i) + h / 2) / h;
            p.setX(i, p.getX(i) * (1 + (wT / wB - 1) * t));
            p.setZ(i, p.getZ(i) * (1 + (dT / dB - 1) * t));
        }
        g.computeVertexNormals();
        return g;
    };
    // a polyline with rounded corners (quadratic fillets) as a Curve — for bent wire and tubing
    const roundedPolyline = (pts, radius) => {
        const P = pts.map((q) => new THREE.Vector3(...q));
        const path = new THREE.CurvePath();
        let cur = P[0].clone();
        for (let i = 1; i < P.length - 1; i++) {
            const a = P[i - 1], b = P[i], c = P[i + 1];
            const ra = Math.min(radius, a.distanceTo(b) * 0.45), rc = Math.min(radius, b.distanceTo(c) * 0.45);
            const p0 = b.clone().add(a.clone().sub(b).normalize().multiplyScalar(ra));
            const p1 = b.clone().add(c.clone().sub(b).normalize().multiplyScalar(rc));
            if (cur.distanceTo(p0) > 1e-6) path.add(new THREE.LineCurve3(cur.clone(), p0));
            path.add(new THREE.QuadraticBezierCurve3(p0, b.clone(), p1));
            cur = p1;
        }
        path.add(new THREE.LineCurve3(cur.clone(), P[P.length - 1].clone()));
        return path;
    };
    // planar UV only on faces turned toward dir (e.g. [0,0,1] = the front); every other face maps to uv (-0.25,-0.25),
    // which clamps to the canvas corner — keep that corner transparent and the back/bottom stay unprinted
    const planarUVFacing = (geo, x0, y0, x1, y1, axes = 'xy', dir = [0, 0, 1], minDot = 0.35) => {
        planarUV(geo, x0, y0, x1, y1, axes);
        const n = geo.attributes.normal, uvA = geo.attributes.uv;
        for (let i = 0; i < n.count; i += 3) {
            let dsum = 0;
            for (let k = 0; k < 3; k++) dsum += n.getX(i + k) * dir[0] + n.getY(i + k) * dir[1] + n.getZ(i + k) * dir[2];
            if (dsum / 3 < minDot) for (let k = 0; k < 3; k++) uvA.setXY(i + k, -0.25, -0.25);
        }
        uvA.needsUpdate = true;
        return geo;
    };
    const mesh = (geo, mat, name) => { const m = new THREE.Mesh(geo, mat); m.name = name || ''; m.castShadow = true; m.receiveShadow = true; return m; };

    // canvas drawing helpers
    const rr = (ctx, x, y, w, h, r) => {
        r = Math.min(r, w / 2, h / 2);
        ctx.beginPath();
        ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
    };
    const speckle = (ctx, w, h, n, seed, colors, rMax = 1.5, alpha = 0.08) => {
        const r = rng(seed);
        for (let i = 0; i < n; i++) {
            ctx.globalAlpha = alpha * (0.3 + r());
            ctx.fillStyle = colors[Math.floor(r() * colors.length)];
            ctx.beginPath(); ctx.arc(r() * w, r() * h, 0.3 + r() * rMax, 0, Math.PI * 2); ctx.fill();
        }
        ctx.globalAlpha = 1;
    };

    // ── load one of the Blender-built machine GLBs from the library pack (eidoverse/assets/models/voice_machines/<name>.glb)
    async function loadGLB(url) {
        const bytes = await Deno.readFile(url);
        const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        const gltf = await new globalThis.GLTFLoader().parseAsync(buf, '');
        return gltf.scene;
    }
    // glTF material (baked colour / roughness / normal / occlusion maps) → MeshStandardNodeMaterial, same maps
    function bakedMaterial(m, o = {}) {
        const nm = new THREE.MeshStandardNodeMaterial({
            map: m.map || null, normalMap: m.normalMap || null, roughnessMap: m.roughnessMap || null,
            metalnessMap: m.metalnessMap || null, aoMap: m.aoMap || null, aoMapIntensity: o.ao ?? 1.0,
            color: m.color ? m.color.clone() : new THREE.Color(1, 1, 1), roughness: m.roughness ?? 1, metalness: m.metalness ?? 0,
        });
        if (m.normalScale) nm.normalScale.copy(m.normalScale);
        return nm;
    }
    // runtime brushed/plated metal for screws, connector shells and the like
    function metalMaterial(color = '#b8b8bc', rough = 0.32) {
        const mat = new THREE.MeshStandardNodeMaterial({ metalness: 1.0 });
        const n = triplanar(60);
        mat.colorNode = lin(color).mul(n.g.sub(0.5).mul(0.25).add(1));
        mat.roughnessNode = clamp(float(rough).add(n.a.sub(0.5).mul(0.3)), 0.08, 1.0);
        return mat;
    }
    // a surface lit by the machine's voice (behind grilles, cloth, slots): emissive = colour × level
    function glowMaterial(color, base = '#050505') {
        const level = uniform(0);
        const mat = new THREE.MeshStandardNodeMaterial({ roughness: 0.9, metalness: 0 });
        mat.colorNode = lin(base);
        const n = triplanar(25);
        mat.emissiveNode = lin(color).mul(level).mul(n.g.mul(0.5).add(0.75)).mul(2.4);
        return { mat, level };
    }
    // glTF UVs are v-down; the screen material expects v-up like three's own geometry
    function flipUV(geo) {
        const uvA = geo.attributes.uv;
        if (!uvA) return geo;
        for (let i = 0; i < uvA.count; i++) uvA.setY(i, 1 - uvA.getY(i));
        uvA.needsUpdate = true;
        return geo;
    }

    return {
        loadGLB, bakedMaterial, metalMaterial, glowMaterial, flipUV,
        rng, lin, makeCanvas, buildMips, canvasTexture, refreshCanvasTexture, eraScreen, NOISE, triplanar, curvature,
        bumpNormal, plastic, screenMaterial, ledMaterial, rbox, roundedRectShape, bake, merge, planarUV, mesh, rr,
        speckle, uniform, roundedPolyline, smooth, rrPoints, loftRings, keycap, planarUVFacing,
    };
}
// ===== ERA KIT END =====
