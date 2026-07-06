// screen.js — globalThis.makeScreen: the CANONICAL animated screen /
// display panel. Laptop telemetry, wall monitors, holo-panels, jumbotron
// content, dashboards — any surface whose IMAGE is drawn with canvas-2D
// and changes over time.
//
// The recipe (extracted from a production scene that got it right):
//   canvas-2D  →  CanvasTexture (sRGB, no mips, linear filters)
//   →  UNLIT MeshBasicNodeMaterial with toneMapped:false
//   →  redraw + refresh per frame (self-updating via the engine loop).
// Unlit + toneMapped:false is what makes it read as an EMISSIVE display
// with exact UI colors — a lit material would dim the pixels with the
// room lighting and the tonemapper would shift the palette.
//
//   const screen = globalThis.makeScreen({
//       width: 0.64, height: 0.36,       // world size (metres)
//       px: 768,                         // canvas width px (height follows aspect)
//       draw(ctx, t, w, h) {             // REQUIRED — plain canvas-2D, t in seconds
//           ctx.fillStyle = '#041018'; ctx.fillRect(0, 0, w, h);
//           ctx.strokeStyle = '#27e0a0'; ctx.beginPath();
//           for (let x = 0; x < w; x += 4) {
//               const y = h * 0.5 + Math.sin(x * 0.02 + t * 3.0) * h * 0.3;
//               x ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
//           }
//           ctx.stroke();
//       },
//   });
//   screen.mesh.position.set(0, 1.4, -2);   // place like any mesh
//   scene.add(screen.mesh);
//   // that's it — it self-updates every frame (opts.auto). For manual
//   // control pass auto:false and call screen.update(t) in renderFrame.
//
// opts: draw (required), width 0.64, height 0.36, px 768,
//       fps 0 (0 = redraw every frame; e.g. 12 throttles to ~12fps for a
//              retro/terminal feel and saves CPU on complex draws),
//       lit false (true = MeshStandardNodeMaterial — a screen that IS
//              affected by scene light, e.g. a switched-off glossy panel),
//       transparent true (draw with alpha for floating holo-panels;
//              false = opaque monitor face, writes depth),
//       doubleSided false, auto true.
// Returns { mesh, material, texture, canvas, ctx, update(t) }.
//
// Rules of the road: this replaces every hand-rolled canvas-screen
// pattern — do NOT hand-build CanvasTexture screens in scenes anymore.
// Full-frame HUDs / lower thirds still go through makeOverlayLayer
// (screen-locked); makeScreen is for displays that live IN the world.
// Screen-space glitch/scanline/CRT looks are still CustomEffectsDeno's
// job — don't fake them in the draw() callback.
(function () {
    globalThis.makeScreen = function makeScreen(opts = {}) {
        const {
            draw,
            width = 0.64, height = 0.36,
            px = 768,
            fps = 0,
            lit = false,
            transparent = true,
            doubleSided = false,
            auto = true,
        } = opts;
        if (typeof draw !== 'function') {
            throw new Error('[makeScreen] opts.draw(ctx, t, w, h) is required — plain canvas-2D drawing, t in seconds');
        }

        const pw = Math.max(2, Math.round(px));
        const ph = Math.max(2, Math.round(px * (height / width)));
        const canvasEl = document.createElement('canvas');
        canvasEl.width = pw;
        canvasEl.height = ph;
        const ctx = canvasEl.getContext('2d');
        draw(ctx, 0, pw, ph);

        const texture = new THREE.CanvasTexture(canvasEl);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.generateMipmaps = false;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.needsUpdate = true;

        const MatCls = lit ? THREE.MeshStandardNodeMaterial : THREE.MeshBasicNodeMaterial;
        const material = new MatCls({
            map: texture,
            transparent,
            depthWrite: !transparent,
            toneMapped: false,
            side: doubleSided ? THREE.DoubleSide : THREE.FrontSide,
        });

        const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height), material);
        mesh.userData.isScreen = true;

        let last = -Infinity;
        const update = (t) => {
            if (fps > 0 && (t - last) < 1.0 / fps) return;
            last = t;
            draw(ctx, t, pw, ph);
            if (texture.refresh) texture.refresh();
            texture.needsUpdate = true;
        };

        if (auto) {
            (globalThis._autoScreens || (globalThis._autoScreens = [])).push(update);
        }

        return { mesh, material, texture, canvas: canvasEl, ctx, update };
    };

    // ── makeVideoScreen: a VIDEO playing on an in-world panel ──
    // Takes the sprite atlas produced by eidoverse/video_to_sprite.mjs
    // (atlas texture + parsed *_info.json) and owns the whole recipe:
    // same screen material as makeScreen (sRGB, unlit, toneMapped:false)
    // plus the per-frame UV stepping, self-updating via the engine loop.
    // Never hand-roll the offset math or a raw material for this.
    //
    //   const info = JSON.parse(new TextDecoder().decode(b64toArrayBuffer(ASSETS.videoInfo)));
    //   const spriteTex = await globalThis.loadImageTexture(ASSETS.videoSprite);
    //   const tv = globalThis.makeVideoScreen({ texture: spriteTex, info, width: 1.6 });
    //   scene.add(tv.mesh);   // position over the TV/monitor's screen face
    //
    // opts: texture + info (required), width 1.6, height (defaults to the
    //       video's true aspect), speed 1, loop true, transparent false,
    //       doubleSided false, auto true.
    // Returns { mesh, material, texture, update(t), setFrame(n) }.
    //
    // FEED IT AN IMAGE-FILE ATLAS loaded via loadImageTexture (what the
    // tool outputs). A CanvasTexture used AS an atlas hits upload quirks
    // on this stack (wrong/flipped tiles, dither garbage) — for drawn
    // content use makeScreen; for video, the image atlas.
    globalThis.makeVideoScreen = function makeVideoScreen(opts = {}) {
        const {
            texture, info,
            width = 1.6, height,
            speed = 1.0, loop = true,
            transparent = false, doubleSided = false, auto = true,
        } = opts;
        if (!texture || !info || !info.cols || !info.rows || !info.totalFrames) {
            throw new Error('[makeVideoScreen] needs { texture, info } — the atlas texture + parsed *_info.json from video_to_sprite.mjs');
        }
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.generateMipmaps = false;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
        texture.repeat.set(1 / info.cols, 1 / info.rows);
        texture.needsUpdate = true;

        const material = new THREE.MeshBasicNodeMaterial({
            map: texture,
            toneMapped: false,
            transparent,
            depthWrite: !transparent,
            side: doubleSided ? THREE.DoubleSide : THREE.FrontSide,
        });
        const h = height || width * ((info.frameHeight || 9) / (info.frameWidth || 16));
        const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, h), material);
        mesh.userData.isScreen = true;

        const setFrame = (f) => {
            const n = info.totalFrames;
            const frame = loop ? ((f % n) + n) % n : Math.min(Math.max(f, 0), n - 1);
            texture.offset.set(
                (frame % info.cols) / info.cols,
                1 - (Math.floor(frame / info.cols) + 1) / info.rows);
        };
        setFrame(0);
        const update = (t) => setFrame(Math.floor(t * info.fps * speed));
        if (auto) {
            (globalThis._autoScreens || (globalThis._autoScreens = [])).push(update);
        }
        return { mesh, material, texture, update, setFrame };
    };
})();
