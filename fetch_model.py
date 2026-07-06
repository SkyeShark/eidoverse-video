#!/usr/bin/env python3
"""Fetch 3D models from Poly Haven, Smithsonian, NASA, and NIH 3D.

Searches four sources automatically (in order of speed):
- Poly Haven: furniture, plants, tools, nature, industrial objects (REST API)
- Smithsonian 3D: fossils, artifacts, dinosaurs, animals, history (Puppeteer scrape)
- NASA: spacecraft, rovers, telescopes, planets (GitHub API + Puppeteer fallback)
- NIH 3D: brains, organs, molecules, cells, neurons, viruses, anatomy (Puppeteer scrape)

(AmbientCG is used for textures + HDRIs, not models — its 3D assets ship only
as USD/Blender/MaterialX, which GLTFLoader can't load. See fetch_texture.py.)

Outputs an embedded .gltf file (textures inlined as data URIs) ready to load
via render_scene.mjs's `assets` config. Also renders a 512x512 _preview.jpg
next to the model showing it from a 3/4 iso angle with bounding box, axis
labels (+X/-X/+Y/+Z/-Z), and the filename + dimensions overlaid as text —
the agent should READ this preview before placing the model in a scene to
verify the right thing was downloaded and which way it faces.

LOCAL models (custom_models / assets/models) are referenced IN PLACE — the
match prints the canonical absolute path + a cached preview, and is NEVER
copied into the caller's cwd (copying multi-MB meshes per work folder bled the
disk). Downloaded online models still land in cwd as model_embedded.gltf.

Usage:
    python3 fetch_model.py "fire hydrant"
    python3 fetch_model.py ArmChair_01
    python3 fetch_model.py "apollo lunar module"
    python3 fetch_model.py --list-local        # catalog of local models (path + dims + preview)
    python3 fetch_model.py --build-previews     # pre-render cached previews for all local models (run once, GPU)
"""
import requests
import json
import os
import sys
import struct
import re
import base64
import shutil
import subprocess
import tempfile
import glob
import random
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================================
# Preview rendering — drops an orientation/identity PNG next to the downloaded
# model so the agent can immediately see what it got and which way it faces.
# ============================================================================

# ──────────────────────────────────────────────────────────────────────────
# DENO + WebGPU preview path (eidoverse pipeline)
# ──────────────────────────────────────────────────────────────────────────
#
# The old _PREVIEW_SCENE_JS below uses Playwright/Firefox + WebGL +
# document.fonts + canvas-2D to bake axis labels and the title overlay.
# Under the new eidoverse Deno+WebGPU pipeline none of that is available,
# so we:
#   1. Bake all text labels (title + axis names) as transparent PNGs via
#      Pillow in this Python script, BEFORE invoking the renderer.
#   2. Hand those PNGs to the Deno scene as base64 assets.
#   3. Deno scene uses WebGPURenderer + LineBasicMaterial for axis rays +
#      SpriteMaterial with the pre-baked label textures.
# Output is functionally identical: 512x512 _preview.jpg with bbox,
# colored axes (red X / green Y / blue Z), labels, and a title plate.

_PREVIEW_SCENE_DENO_JS = r"""
// Single-frame orientation preview for a downloaded 3D model. Loads the
// model, draws colored axis labels (+X/-X/+Y/+Z/-Z) at the bbox face
// centers, draws a yellow bbox wireframe, an AxesHelper, and a faint
// ground grid. A title plate in the top-left shows the filename and
// model dimensions. Output is a single rendered frame the human or
// agent inspects before placing the model in a scene.
//
// Text is rendered via canvas-2D drawn inside the scene and wrapped as
// a CanvasTexture. Each label is a Mesh + PlaneGeometry oriented to
// face the camera. Title plate is the same in a screen-space ortho
// camera composited after the main scene.

// Build a transparent-bg canvas with a single label drawn in `color` +
// black stroke for readability. Returns { canvas, width, height }.
function _drawLabelCanvas(text, color, fontPx) {
    const measure = document.createElement('canvas').getContext('2d');
    const font = 'bold ' + fontPx + 'px "DejaVu Sans", "Liberation Sans", sans-serif';
    measure.font = font;
    const textW = Math.ceil(measure.measureText(text).width);
    const padX = 16, padY = 12;
    const w = textW + padX * 2;
    const h = fontPx + padY * 2;
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, w, h);
    ctx.font = font;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = 8;
    ctx.strokeStyle = 'rgba(0,0,0,0.85)';
    ctx.strokeText(text, w / 2, h / 2);
    ctx.fillStyle = color;
    ctx.fillText(text, w / 2, h / 2);
    return { canvas: c, width: w, height: h };
}

// Build a title plate canvas: filename + dimensions on a dark
// translucent rectangle. Returns { canvas, width, height }.
function _drawTitleCanvas(title, subtitle) {
    const measure = document.createElement('canvas').getContext('2d');
    const titleFont = 'bold 22px "DejaVu Sans", "Liberation Sans", sans-serif';
    const subFont   = '16px "DejaVu Sans", "Liberation Sans", sans-serif';
    measure.font = titleFont;
    const tW = Math.ceil(measure.measureText(title).width);
    measure.font = subFont;
    const sW = Math.ceil(measure.measureText(subtitle).width);
    const padX = 14, padY = 10, lineGap = 6;
    const titleH = 26, subH = 18;
    const w = Math.max(tW, sW) + padX * 2;
    const h = titleH + subH + lineGap + padY * 2;
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d');
    ctx.fillStyle = 'rgba(0,0,0,0.72)';
    ctx.fillRect(0, 0, w, h);
    ctx.textBaseline = 'top';
    ctx.font = titleFont;
    ctx.fillStyle = '#ffffff';
    ctx.fillText(title, padX, padY);
    ctx.font = subFont;
    ctx.fillStyle = '#cccccc';
    ctx.fillText(subtitle, padX, padY + titleH + lineGap);
    return { canvas: c, width: w, height: h };
}

function _canvasToTexture(canvas) {
    // The engine's CanvasTexture shim now sets flipY=true automatically
    // so canvas-top maps to mesh-top without per-texture intervention.
    return new THREE.CanvasTexture(canvas);
}


globalThis.setup = async function() {
    const renderer = new THREE.WebGPURenderer({
        canvas, antialias: false,
        adapter: GPU_ADAPTER, device: GPU_DEVICE,
    });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    await renderer.init();

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#2a2a38');

    // Three-point lighting so every side of the model reads
    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(4, 6, 3);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xbbccff, 0.5);
    fill.position.set(-4, 2, -2);
    scene.add(fill);
    const rim = new THREE.DirectionalLight(0xffe0b0, 0.4);
    rim.position.set(0, 3, -5);
    scene.add(rim);

    // Load model via the harness-wired GLTFLoader (DRACO + DataTexture
    // migration already installed by render_scene.mjs).
    const loader = new globalThis.GLTFLoader();
    let gltf;
    try {
        gltf = await new Promise((res, rej) =>
            loader.parse(globalThis.b64toArrayBuffer(globalThis.ASSETS.model), '', res, rej));
    } catch (e) {
        console.error('[preview] GLTFLoader failed:', e.message || e);
        const camera = new THREE.PerspectiveCamera(45, WIDTH/HEIGHT, 0.1, 100);
        camera.position.set(0, 0, 3);
        globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;
        return;
    }
    const model = gltf.scene;
    scene.add(model);

    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z) || 1;

    // Emit bbox on stdout so the Python caller can pick it up if its
    // own gltf parser couldn't extract dimensions.
    console.log('[PREVIEW_BBOX] ' + size.x + ' ' + size.y + ' ' + size.z);

    // ── Modular-kit / asset-library detection (name-based) ──
    // Many fetched models are KITS: a parts library laid out as a catalog
    // (door_*/window_* across 50m; 3 plant variants in a row; bananas + 4
    // singles) rather than one finished object — placing the whole gltf.scene
    // scatters every piece. Distinguishing a kit from a finished ASSEMBLY
    // (e.g. a coffee cart with mugs ON it) can't be done spatially — both are
    // separate objects in space. The reliable signal is the PART NAMES: a kit
    // is enumerated variants of the same item (bananas_a/b/c/d, beaker_s/m/l,
    // searsia_lucida_a..g) and/or a large library; an assembly is a few
    // distinct functional parts (cart, mugs, props). We grade on that and let
    // the preview be the tiebreaker for ambiguous cases.
    try {
        // Top-level parts (descend single-child wrapper nodes, like loadKit).
        let host = model;
        while (host.children && host.children.length === 1 &&
               host.children[0].children && host.children[0].children.length > 1) host = host.children[0];
        const parts = [];
        for (const ch of host.children) {
            let has = false;
            ch.traverse((o) => { if (o.isMesh) has = true; });
            if (has) parts.push(ch.name || '(unnamed)');
        }
        if (parts.length >= 2) {
            // Stem a part name to its base type: strip a trailing _LODn first
            // (Poly Haven plants bury the variant letter before it), then peel
            // trailing enumeration (_NN / _a..z / _small|med|large).
            const stem = (s) => {
                let x = String(s).toLowerCase().replace(/_lod\d+$/, '');
                let prev;
                do { prev = x;
                    x = x.replace(/_(\d+)$/, '').replace(/_[a-z]$/, '')
                         .replace(/_(small|med|medium|large|xl|sm|lg|s|m|l)$/, '');
                } while (x !== prev);
                return x;
            };
            const fam = {};
            for (const p of parts) { const k = stem(p); fam[k] = (fam[k] || 0) + 1; }
            const families = Object.entries(fam).sort((a, b) => b[1] - a[1]);
            const inMulti = Object.values(fam).filter(v => v >= 2).reduce((a, b) => a + b, 0);
            const pct = Math.round(100 * inMulti / parts.length);
            const famStr = families.slice(0, 8).map(([k, v]) => v > 1 ? `${k}×${v}` : k).join(', ')
                + (families.length > 8 ? ', …' : '');
            // LIKELY KIT when dominated by repeated variants (≥50%) OR a large
            // library (≥8 parts). Otherwise a few distinct parts → ambiguous.
            if (pct >= 50 || parts.length >= 8) {
                console.log('[KIT_INFO] LIKELY A MODULAR KIT / ASSET-LIBRARY: ' + parts.length + ' named parts'
                    + (pct >= 50 ? ', ' + pct + '% in repeated variant-families' : '') + ' (' + famStr + '). '
                    + 'These are parts laid out for ASSEMBLY, not one finished model — placing the whole gltf.scene '
                    + 'scatters them. Use globalThis.loadKit(gltf): kit.list() / kit.get(name) / kit.family(prefix) '
                    + 'return named, origin-centered parts to place / array / combine. Pick one, or build from several.');
            } else {
                console.log('[KIT_INFO] ' + parts.length + ' named parts (' + famStr + '). Could be a finished '
                    + 'assembly (place it whole) OR a small set to split — JUDGE FROM THIS PREVIEW. If the parts '
                    + 'should be used separately, globalThis.loadKit(gltf) exposes them individually (origin-centered).');
            }
        }
    } catch (e) { console.error('[preview] kit-detect failed:', e.message || e); }

    // Axes — red X, green Y, blue Z. LineBasicMaterial works under
    // WebGPURenderer (it auto-wraps to a Node material internally).
    const axesLen = maxDim * 0.75;
    const axes = new THREE.AxesHelper(axesLen);
    if (axes.material) axes.material.depthTest = false;
    axes.position.copy(center);
    axes.renderOrder = 999;
    scene.add(axes);

    function addRay(color, dir) {
        const mat = new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true, opacity: 0.55 });
        const geo = new THREE.BufferGeometry().setFromPoints([
            center.clone(),
            center.clone().add(new THREE.Vector3(dir[0] * axesLen, dir[1] * axesLen, dir[2] * axesLen)),
        ]);
        const line = new THREE.Line(geo, mat);
        line.renderOrder = 999;
        scene.add(line);
    }
    addRay(0xff0000, [-1, 0, 0]);
    addRay(0x0000ff, [0, 0, -1]);

    const bboxHelper = new THREE.Box3Helper(box, 0xffff00);
    scene.add(bboxHelper);

    const gridSize = maxDim * 2.6;
    const grid = new THREE.GridHelper(gridSize, 12, 0x666688, 0x3a3a4a);
    grid.position.set(center.x, Math.min(0, box.min.y), center.z);
    scene.add(grid);

    // (PNG-to-DataTexture loader removed — no longer needed; the legacy
    // in-scene sprite labels are baked in Pillow post-render instead.)
    // Label sprites — THREE.SpriteNodeMaterial is the NodeMaterial-aware
    // version of SpriteMaterial that's actually wired into the WebGPU
    // backend's texture path. Plain SpriteMaterial crashes in writeTexture
    // because its diffuse map isn't routed through a TextureNode.
    // Axis labels at the bbox face centers, oriented to face the camera.
    // Mid-tone label colors — saturated #88ff88 / #ff7777 / #7777ff get
    // picked up by the UnrealBloom pass in the autoenhance pipeline and
    // bloom into glowing blobs. Darker, less-luminant variants stay below
    // the bloom threshold while still being clearly red/green/blue.
    const labelSpecs = [
        { text: '+Y', color: '#3eaa3e', pos: [center.x,           box.max.y + maxDim * 0.10, center.z] },
        { text: '+X', color: '#c64a4a', pos: [box.max.x + maxDim * 0.10, center.y,           center.z] },
        { text: '-X', color: '#c64a4a', pos: [box.min.x - maxDim * 0.10, center.y,           center.z] },
        { text: '+Z', color: '#4a5fc6', pos: [center.x,           center.y,           box.max.z + maxDim * 0.10] },
        { text: '-Z', color: '#4a5fc6', pos: [center.x,           center.y,           box.min.z - maxDim * 0.10] },
    ];
    // Labels as Sprites — auto-billboard to face the camera regardless of
    // model orientation, no manual lookAt math needed.
    for (const spec of labelSpecs) {
        const { canvas, width, height } = _drawLabelCanvas(spec.text, spec.color, 56);
        const tex = _canvasToTexture(canvas);
        const mat = new THREE.SpriteMaterial({
            map: tex,
            transparent: true,
            depthTest: false,
            depthWrite: false,
            toneMapped: false,
        });
        const s = new THREE.Sprite(mat);
        const aspect = width / height;
        const scl = maxDim * 0.18;
        s.scale.set(scl * aspect, scl, 1);
        s.position.set(spec.pos[0], spec.pos[1], spec.pos[2]);
        s.renderOrder = 1000;
        scene.add(s);
    }

    // Camera — 3/4 iso framed off the bbox diagonal so thin/long objects
    // (swords, pencils) still fill the frame.
    const camera = new THREE.PerspectiveCamera(35, WIDTH/HEIGHT, 0.01, 10000);
    const diag = Math.sqrt(size.x*size.x + size.y*size.y + size.z*size.z);
    const dist = Math.max(diag, maxDim) * 1.35;
    camera.position.set(
        center.x + dist * 0.85,
        center.y + dist * 0.78,
        center.z + dist * 0.85,
    );
    camera.lookAt(center.x, center.y + maxDim * 0.05, center.z);

    // Title plate — filename + dimensions in the top-left corner.
    // Placed at a fixed world position derived from the camera's basis
    // vectors so it sits in the upper-left of the view frustum at a
    // known distance from the camera.
    const filename = (globalThis.PREVIEW_FILENAME || 'model');
    const dimStr = size.x.toFixed(2) + ' x ' + size.y.toFixed(2) + ' x ' + size.z.toFixed(2);
    const title = _drawTitleCanvas(filename, dimStr);
    const titleTex = _canvasToTexture(title.canvas);
    // Use the same material setup as the label sprites (which render
    // right-side-up) — depthTest/renderOrder differences caused the
    // earlier 180°-flip artifact.
    const titleSprite = new THREE.Sprite(new THREE.SpriteMaterial({
        map: titleTex,
        transparent: true,
        depthTest: false,
        depthWrite: false,
        toneMapped: false,
    }));
    titleSprite.center.set(0.5, 0.5);
    const titleDist = camera.position.distanceTo(new THREE.Vector3(center.x, center.y, center.z)) * 0.45;
    const fovRad = camera.fov * Math.PI / 180;
    const viewH = 2 * titleDist * Math.tan(fovRad / 2);
    const viewW = viewH * camera.aspect;
    const pxToWorld = viewH / HEIGHT;
    const tWorldW = title.width * pxToWorld;
    const tWorldH = title.height * pxToWorld;
    const padW = 12 * pxToWorld;
    titleSprite.scale.set(tWorldW, tWorldH, 1);
    // Compute the world-space target position: at `titleDist` in front of
    // the camera along its -Z, then shifted up-left by half-frustum minus
    // padding and half-sprite.
    camera.updateMatrixWorld(true);
    const camForward = new THREE.Vector3();
    camera.getWorldDirection(camForward);              // points where camera looks
    const camRight = new THREE.Vector3().crossVectors(camForward, camera.up).normalize();
    const camUp    = new THREE.Vector3().crossVectors(camRight, camForward).normalize();
    const titlePos = new THREE.Vector3()
        .copy(camera.position)
        .addScaledVector(camForward,  titleDist)
        .addScaledVector(camRight,   -(viewW / 2 - padW - tWorldW / 2))
        .addScaledVector(camUp,        viewH / 2 - padW - tWorldH / 2);
    titleSprite.position.copy(titlePos);
    titleSprite.renderOrder = 1000;
    scene.add(titleSprite);

    globalThis._r = renderer; globalThis._s = scene; globalThis._c = camera;
};

globalThis.renderFrame = async function(t) {
    await globalThis._r.renderAsync(globalThis._s, globalThis._c);
};
"""




# Legacy WebGL preview JS kept for fallback if the Deno renderer isn't
# available in this sandbox (e.g. running from outside the codex container).
_PREVIEW_SCENE_JS = r"""
// Auto-generated by fetch_model.py — single-frame orientation preview
window.setup = async function() {
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(WIDTH, HEIGHT);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#2a2a38');

    // Three-point lighting so every side of the model is legible
    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(4, 6, 3);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xbbccff, 0.5);
    fill.position.set(-4, 2, -2);
    scene.add(fill);
    const rim = new THREE.DirectionalLight(0xffe0b0, 0.4);
    rim.position.set(0, 3, -5);
    scene.add(rim);

    // Load the model — register DRACOLoader for compressed NASA GLBs etc.
    const loader = new GLTFLoader();
    try {
        if (typeof DRACOLoader !== 'undefined') {
            const dracoLoader = new DRACOLoader();
            dracoLoader.setDecoderPath('https://www.gstatic.com/draco/v1/decoders/');
            loader.setDRACOLoader(dracoLoader);
        }
    } catch (e) { /* non-fatal — only matters for draco-compressed models */ }
    let gltf;
    try {
        gltf = await new Promise((res, rej) =>
            loader.parse(b64toArrayBuffer(window.ASSETS.model), '', res, rej));
    } catch (e) {
        console.error('[preview] GLTFLoader failed:', e.message || e);
        // Still set up the render state so renderFrame() doesn't crash on undefined
        const camera = new THREE.PerspectiveCamera(45, WIDTH/HEIGHT, 0.1, 100);
        camera.position.set(0, 0, 3);
        window._r = renderer; window._s = scene; window._c = camera;
        window._noAutoIdle = true;
        return;
    }
    const model = gltf.scene;
    scene.add(model);

    // Bounding box of the raw model — three.js is authoritative because it
    // handles Draco/quantized/morph targets that the Python parser can't read
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z) || 1;

    // Emit bbox on stdout so fetch_model.py can print it if Python's parser failed
    console.log('[PREVIEW_BBOX] ' + size.x + ' ' + size.y + ' ' + size.z);

    // ORIGIN / PIVOT classification. Agents kept assuming the pivot is the
    // geometric CENTER and setting position.y for that — but many GLBs
    // (characters, props authored standing on a floor) have their origin at the
    // BASE, so a "centered" y floats or sinks them. State where (0,0,0) actually
    // sits inside the bbox, in words, so the agent doesn't have to infer it from
    // the rendered axes.
    const _cls = (lo, hi, sz) => {
        const t = 1e-4 + sz * 0.08;
        if (Math.abs(lo) <= t) return 'min';
        if (Math.abs(hi) <= t) return 'max';
        if (Math.abs((lo + hi) / 2) <= t) return 'center';
        return (0 < lo || 0 > hi) ? 'outside' : 'offset';
    };
    const _oy = _cls(box.min.y, box.max.y, size.y);
    const _yWord = _oy === 'min'
        ? 'at the BASE — y=0 is the model BOTTOM, so it rests directly ON a surface (do NOT add half-height)'
        : _oy === 'center'
        ? 'CENTERED vertically — y=0 is mid-height, so to stand it on a floor add half the height (or just use placeOn)'
        : _oy === 'max'
        ? 'at the TOP — y=0 is the model TOP, so it hangs DOWN from y'
        : _oy === 'outside'
        ? 'OUTSIDE the bbox vertically (origin is away from the geometry)'
        : 'OFFSET vertically (origin is not at base/center/top)';
    console.log('[ORIGIN_INFO] Pivot/origin: ' + _yWord
        + '. Lateral: X ' + _cls(box.min.x, box.max.x, size.x) + ', Z ' + _cls(box.min.z, box.max.z, size.z)
        + '. bbox(modelspace) Y[' + box.min.y.toFixed(3) + '..' + box.max.y.toFixed(3) + ']'
        + ' X[' + box.min.x.toFixed(3) + '..' + box.max.x.toFixed(3) + ']'
        + ' Z[' + box.min.z.toFixed(3) + '..' + box.max.z.toFixed(3) + ']'
        + '. PREFER placeOn/placeAgainst (they seat the bbox, ignoring origin) over a hand-set position.y.');

    // Axes — red X, green Y (up), blue Z. AxesHelper only shows +X/+Y/+Z;
    // we extend with line segments to show -X and -Z too so both ends of the
    // lateral axes are visible and the agent can identify which face is which.
    //
    // CRITICAL: re-center all decorations on the BBOX CENTER, not world (0,0,0).
    // Many models have their origin offset from their geometric center, which
    // would otherwise put the axes/grid/labels in the wrong place relative to
    // the model.
    const axesLen = maxDim * 0.75;
    const axes = new THREE.AxesHelper(axesLen);
    if (axes.material) axes.material.depthTest = false;
    axes.position.copy(center);
    axes.renderOrder = 999;
    scene.add(axes);
    // Negative X/-Z rays (slightly dimmer so +axes stay visually dominant)
    function addRay(color, dir) {
        const mat = new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true, opacity: 0.55 });
        const geo = new THREE.BufferGeometry().setFromPoints([
            center.clone(),
            center.clone().add(new THREE.Vector3(dir[0] * axesLen, dir[1] * axesLen, dir[2] * axesLen)),
        ]);
        const line = new THREE.Line(geo, mat);
        line.renderOrder = 999;
        scene.add(line);
    }
    addRay(0xff0000, [-1, 0, 0]);  // -X
    addRay(0x0000ff, [0, 0, -1]);  // -Z

    // Bounding-box wireframe (yellow) — Box3Helper already follows the box
    const bboxHelper = new THREE.Box3Helper(box, 0xffff00);
    scene.add(bboxHelper);

    // Ground grid centered under the model (NOT under world origin)
    const gridSize = maxDim * 2.6;
    const grid = new THREE.GridHelper(gridSize, 12, 0x666688, 0x3a3a4a);
    grid.position.set(center.x, Math.min(0, box.min.y), center.z);
    scene.add(grid);

    // Text labels just outside each bbox face (per-axis, not a uniform offset).
    // Sprite size scaled down; they're small annotations, not banners.
    //
    // FONT-READY RACE: Firefox headless fires ctx.fillText before the CSS font
    // has finished resolving through fontconfig, so the first few labels render
    // as tofu boxes while later ones look fine. Preload the exact font we use
    // via document.fonts.load() + .ready and only then start drawing.
    const LABEL_FONT = 'bold 56px "DejaVu Sans", "Liberation Sans", sans-serif';
    try {
        await document.fonts.load(LABEL_FONT);
        await document.fonts.ready;
    } catch (e) { /* non-fatal — worst case we get the old race */ }

    function makeLabel(text, color) {
        // Transparent canvas, just the text with a black outline for
        // readability against any background. Sprites are auto-excluded from
        // the auto-enhance GTAO pass in render_scene.mjs so the canvas alpha
        // stays true through the upload.
        const ctx0 = document.createElement('canvas').getContext('2d');
        ctx0.font = LABEL_FONT;
        const textW = Math.ceil(ctx0.measureText(text).width);
        const padX = 16, padY = 12;
        const w = textW + padX * 2;
        const h = 56 + padY * 2;

        const c = document.createElement('canvas');
        c.width = w; c.height = h;
        const ctx = c.getContext('2d', { alpha: true });
        ctx.clearRect(0, 0, w, h);
        ctx.font = LABEL_FONT;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        // Black stroke under the colored fill so the text is readable on any
        // backdrop without a box behind it.
        ctx.lineWidth = 8;
        ctx.strokeStyle = 'rgba(0,0,0,0.85)';
        ctx.strokeText(text, w / 2, h / 2);
        ctx.fillStyle = color;
        ctx.fillText(text, w / 2, h / 2);

        const tex = new THREE.CanvasTexture(c);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.minFilter = THREE.LinearFilter;
        tex.magFilter = THREE.LinearFilter;
        tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
        tex.generateMipmaps = false;
        const mat = new THREE.SpriteMaterial({
            map: tex,
            depthTest: false,
            transparent: true,
        });
        const sprite = new THREE.Sprite(mat);
        sprite.renderOrder = 1000;
        const scl = maxDim * 0.15;
        sprite.scale.set(scl * (w / h), scl, 1);
        return sprite;
    }
    const margin = maxDim * 0.10;  // labels sit just past bbox edges (tight)
    function placeLabel(text, color, pos) {
        const s = makeLabel(text, color);
        s.position.set(pos[0], pos[1], pos[2]);
        scene.add(s);
    }
    // Labels positioned just past each bbox face, on the perpendicular axes
    // running through the bbox CENTER (not world origin).
    placeLabel('+Y',  '#88ff88', [center.x,           box.max.y + margin, center.z]);
    placeLabel('+X',  '#ff7777', [box.max.x + margin, center.y,           center.z]);
    placeLabel('-X',  '#ff7777', [box.min.x - margin, center.y,           center.z]);
    placeLabel('+Z',  '#7777ff', [center.x,           center.y,           box.max.z + margin]);
    placeLabel('-Z',  '#7777ff', [center.x,           center.y,           box.min.z - margin]);

    // Camera — 3/4 iso, framed tightly enough that the model fills most of
    // the frame while still leaving the +Y / +X / -X / +Z / -Z labels
    // visible inside the viewport. Distance derived from the bbox DIAGONAL
    // (not just maxDim) so thin/long objects like swords or pencils don't
    // end up tiny in the center — diagonal captures the full spatial extent.
    const camera = new THREE.PerspectiveCamera(35, WIDTH/HEIGHT, 0.01, 10000);
    const diag = Math.sqrt(size.x*size.x + size.y*size.y + size.z*size.z);
    const dist = Math.max(diag, maxDim) * 1.35;
    camera.position.set(
        center.x + dist * 0.85,
        center.y + dist * 0.78,
        center.z + dist * 0.85,
    );
    // Aim slightly above center so the +Y label doesn't crowd the top edge
    // (and doesn't overlap with the title overlay in the top-left corner).
    camera.lookAt(center.x, center.y + maxDim * 0.05, center.z);

    // ────────────────────────────────────────────────────────────────────
    // Title overlay — filename + dimensions in the top-left corner.
    // Rendered as a Sprite in a separate UI scene with an OrthographicCamera
    // sized in pixels. Second render pass composites it over the main scene
    // with autoClear=false. No Pillow needed — this is all three.js.
    // The dimensions come from three.js's authoritative bbox (computed above),
    // so they're correct even when the Python GLTF parser couldn't read them.
    // ────────────────────────────────────────────────────────────────────
    const PREVIEW_TITLE = __PREVIEW_TITLE__;
    const sub = size.x.toFixed(2) + ' x ' + size.y.toFixed(2) + ' x ' + size.z.toFixed(2);

    const TITLE_FONT = 'bold 22px "DejaVu Sans", "Liberation Sans", sans-serif';
    const SUB_FONT   = '16px "DejaVu Sans", "Liberation Sans", sans-serif';
    try {
        await document.fonts.load(TITLE_FONT);
        await document.fonts.load(SUB_FONT);
        await document.fonts.ready;
    } catch (e) { /* non-fatal */ }

    function makeTitleSprite(title, subtitle) {
        const mc = document.createElement('canvas').getContext('2d');
        mc.font = TITLE_FONT;
        const titleW = Math.ceil(mc.measureText(title).width);
        mc.font = SUB_FONT;
        const subW = Math.ceil(mc.measureText(subtitle).width);

        const padX = 14, padY = 10, lineGap = 6;
        const titleH = 26, subH = 18;
        const w = Math.max(titleW, subW) + padX * 2;
        const h = titleH + subH + lineGap + padY * 2;

        const c = document.createElement('canvas');
        c.width = w; c.height = h;
        const ctx = c.getContext('2d', { alpha: true });
        ctx.fillStyle = 'rgba(0,0,0,0.72)';
        ctx.fillRect(0, 0, w, h);
        ctx.textBaseline = 'top';
        ctx.font = TITLE_FONT;
        ctx.fillStyle = '#ffffff';
        ctx.fillText(title, padX, padY);
        ctx.font = SUB_FONT;
        ctx.fillStyle = '#cccccc';
        ctx.fillText(subtitle, padX, padY + titleH + lineGap);

        const tex = new THREE.CanvasTexture(c);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.minFilter = THREE.LinearFilter;
        tex.magFilter = THREE.LinearFilter;
        tex.generateMipmaps = false;
        const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
            map: tex, depthTest: false, transparent: true,
        }));
        sprite.scale.set(w, h, 1);
        sprite.userData.w = w;
        sprite.userData.h = h;
        return sprite;
    }

    const uiScene = new THREE.Scene();
    const uiCam = new THREE.OrthographicCamera(-WIDTH/2, WIDTH/2, HEIGHT/2, -HEIGHT/2, 1, 10);
    uiCam.position.z = 5;
    const titleSprite = makeTitleSprite(PREVIEW_TITLE, sub);
    // Top-left of viewport with 12px padding (sprite is center-anchored).
    const pad = 12;
    titleSprite.position.set(
        -WIDTH/2 + pad + titleSprite.userData.w / 2,
         HEIGHT/2 - pad - titleSprite.userData.h / 2,
         0,
    );
    uiScene.add(titleSprite);

    window._r = renderer; window._s = scene; window._c = camera;
    window._uiScene = uiScene; window._uiCam = uiCam;
    window._noAutoIdle = true;
};

window.renderFrame = function(t) {
    window._r.render(window._s, window._c);
    // Composite title overlay without clearing the beauty pass underneath.
    window._r.autoClear = false;
    window._r.render(window._uiScene, window._uiCam);
    window._r.autoClear = true;
};
"""


def _render_preview(model_path, dims=None):
    """Render a 512x512 preview of the model.

    Prefers the Deno + WebGPU eidoverse renderer (render_scene.mjs)
    when available — that's the production path under the current codex
    sandbox. Falls back to the legacy WebGL render_scene.mjs (Playwright +
    Firefox + Node) when running outside the codex sandbox.

    Drops `{model_basename}_preview.jpg` next to the model file. Includes
    yellow bounding box wireframe + +X/-X/+Y/+Z/-Z labels + a title plate
    with filename + dimensions so the agent can immediately see what was
    downloaded and which way it faces.

    Returns the preview image path on success, or None on failure (the
    model is still usable in scenes — preview is just a quality-of-life aid).
    """
    if not os.path.exists(model_path):
        return None

    abs_model = os.path.abspath(model_path)
    base = os.path.splitext(os.path.basename(model_path))[0]
    preview_path = os.path.join(os.path.dirname(abs_model) or ".", f"{base}_preview.jpg")

    # Prefer the Deno + WebGPU eidoverse renderer if present.
    deno_renderer_paths = [
        "/workspace/eidoverse/render_scene.mjs",
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "eidoverse", "render_scene.mjs"),
    ]
    deno_renderer = next((p for p in deno_renderer_paths if os.path.exists(p)), None)

    tmp = tempfile.mkdtemp(prefix="fetch_preview_")
    try:
        if deno_renderer is not None:
            # ─── Deno + WebGPU preview path ────────────────────────────
            scene_path = os.path.join(tmp, "scene.js")
            # Stash the source filename as a global so the title plate
            # draws it instead of an unset placeholder.
            scene_js = (
                "globalThis.PREVIEW_FILENAME = "
                + json.dumps(os.path.basename(model_path))
                + ";\n"
                + _PREVIEW_SCENE_DENO_JS
            )
            with open(scene_path, "w", encoding="utf-8") as f:
                f.write(scene_js)

            # No in-scene text labels — they're overlaid in Pillow post.
            out_video = os.path.join(tmp, "preview.mp4")
            config = {
                "width": 512,
                "height": 512,
                "fps": 1,
                # The eidoverse engine expects at least 1 frame's worth of
                # duration; 1/30s is fine. ffmpeg writes a single-frame mp4.
                "duration": 1.0 / 30,
                "script": scene_path,
                "outputVideo": out_video,
                "skipPreflightQA": True,
                "assets": {"model": abs_model},
            }
            config_path = os.path.join(tmp, "config.json")
            with open(config_path, "w") as f:
                json.dump(config, f)

            # Run deno from /workspace so the engine's relative paths
            # (HELPER_MODULES list, render_common.mjs import) resolve.
            proc = subprocess.run(
                [
                    "deno", "run",
                    "--allow-all",
                    "--unstable-webgpu",
                    "--node-modules-dir=auto",
                    deno_renderer,
                    config_path,
                ],
                cwd="/workspace" if os.path.isdir("/workspace") else os.path.dirname(deno_renderer),
                capture_output=True,
                text=True,
                timeout=180,
            )

            # Extract the rendered frame from the mp4
            out_frame = os.path.join(tmp, "frame.jpg")
            if os.path.exists(out_video):
                ff = subprocess.run(
                    ["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
                     "-i", out_video, "-vframes", "1", out_frame],
                    capture_output=True, text=True, timeout=30,
                )
            # Pull bbox out of stdout if Python's parser failed earlier
            if dims is None:
                for line in (proc.stdout or "").splitlines():
                    m = re.search(r'\[PREVIEW_BBOX\]\s+(\S+)\s+(\S+)\s+(\S+)', line)
                    if m:
                        try:
                            dims = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
                        except ValueError:
                            pass
                        break
            # Relay the origin/pivot classification to the agent — where (0,0,0)
            # sits in the bbox (base vs centered vs offset), so it stops
            # assuming the pivot is the geometric center.
            for line in (proc.stdout or "").splitlines():
                i = line.find("[ORIGIN_INFO]")
                if i != -1:
                    print(line[i:])
                    break
            # Relay the modular-kit warning if this model is a parts library
            # laid out for assembly (don't place the whole gltf.scene).
            for line in (proc.stdout or "").splitlines():
                i = line.find("[KIT_INFO]")
                if i != -1:
                    print(line[i:])
                    break

            if not os.path.exists(out_frame):
                print(f"_render_preview (deno): no frame produced. stderr:\n{(proc.stderr or '')[-800:]}")
                # Fall through to the legacy WebGL path below as a backup
            else:
                shutil.copy(out_frame, preview_path)
                print(f"Preview: {preview_path}")
                return preview_path

        # ─── Legacy WebGL preview path (Playwright + Firefox + Node) ───
        scene_path = os.path.join(tmp, "scene_webgl.js")
        scene_js = _PREVIEW_SCENE_JS.replace(
            "__PREVIEW_TITLE__", json.dumps(os.path.basename(model_path))
        )
        with open(scene_path, "w", encoding="utf-8") as f:
            f.write(scene_js)

        out_dir = os.path.join(tmp, "frames")
        os.makedirs(out_dir, exist_ok=True)

        config = {
            "width": 512,
            "height": 512,
            "fps": 1,
            "duration": 0.04,
            "script": scene_path,
            "outputDir": out_dir,
            "outputPattern": "frame_%04d.jpg",
            "assets": {"model": abs_model},
        }
        config_path = os.path.join(tmp, "config.json")
        with open(config_path, "w") as f:
            json.dump(config, f)

        renderer_paths = [
            "/opt/render3d/render_scene.mjs",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_scene.mjs"),
        ]
        renderer = next((p for p in renderer_paths if os.path.exists(p)), None)
        if not renderer:
            print(f"_render_preview: no working renderer found "
                  f"(tried deno: {deno_renderer_paths}, webgl: {renderer_paths})")
            return None

        proc = subprocess.run(
            ["node", renderer, config_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        # Pull bbox out of stdout if Python's parser couldn't get it earlier
        if dims is None:
            for line in (proc.stdout or "").splitlines():
                m = re.search(r'\[PREVIEW_BBOX\]\s+(\S+)\s+(\S+)\s+(\S+)', line)
                if m:
                    try:
                        dims = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
                    except ValueError:
                        pass
                    break

        # Locate the rendered frame
        frames = sorted(glob.glob(os.path.join(out_dir, "frame_*.jpg")))
        if not frames:
            print(f"_render_preview: no frames produced. stderr:\n{(proc.stderr or '')[-800:]}")
            return None

        shutil.copy(frames[0], preview_path)
        # Title + dims overlay is drawn by the three.js scene itself — see
        # _PREVIEW_SCENE_JS. No Pillow compositing needed.
        print(f"Preview: {preview_path}")
        return preview_path
    finally:
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass


def _measure_glb(path):
    """Best-effort dimensions extractor for .gltf or .glb files.

    For .gltf: parses the JSON, walks accessors with POSITION attribute,
    combines their min/max into an overall bbox.

    For .glb: pulls the embedded JSON chunk and does the same.

    Returns (width, height, depth) tuple or None if extraction failed.
    Three.js's bbox via _render_preview is more authoritative for compressed
    or quantized meshes — this is just a fast pre-render hint.
    """
    try:
        ext = os.path.splitext(path)[1].lower()
        gltf = None
        if ext == ".gltf":
            with open(path, "r", encoding="utf-8") as f:
                gltf = json.load(f)
        elif ext == ".glb":
            with open(path, "rb") as f:
                header = f.read(12)
                if header[:4] != b"glTF":
                    return None
                # version, total length
                # JSON chunk header: length (4) + type (4)
                chunk_hdr = f.read(8)
                jlen, jtype = struct.unpack("<II", chunk_hdr)
                if jtype != 0x4E4F534A:  # 'JSON'
                    return None
                jbytes = f.read(jlen)
                gltf = json.loads(jbytes.decode("utf-8"))
        else:
            return None

        if not gltf:
            return None

        accessors = gltf.get("accessors", [])
        meshes = gltf.get("meshes", [])
        nodes = gltf.get("nodes", [])
        # Find every accessor that's used as a POSITION attribute
        pos_accessor_indices = set()
        for m in meshes:
            for prim in m.get("primitives", []):
                idx = prim.get("attributes", {}).get("POSITION")
                if idx is not None:
                    pos_accessor_indices.add(idx)
        if not pos_accessor_indices:
            return None

        bmin = [float("inf")] * 3
        bmax = [float("-inf")] * 3
        for idx in pos_accessor_indices:
            if idx >= len(accessors):
                continue
            a = accessors[idx]
            mn = a.get("min")
            mx = a.get("max")
            if not (isinstance(mn, list) and isinstance(mx, list) and len(mn) >= 3 and len(mx) >= 3):
                continue
            for i in range(3):
                bmin[i] = min(bmin[i], mn[i])
                bmax[i] = max(bmax[i], mx[i])

        if any(x == float("inf") for x in bmin) or any(x == float("-inf") for x in bmax):
            return None
        return (bmax[0] - bmin[0], bmax[1] - bmin[1], bmax[2] - bmin[2])
    except Exception as e:
        print(f"_measure_glb({path}): {e}")
        return None


def _safe_filename(name):
    """Sanitize a string into a safe lowercase filename stem."""
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("_").lower()
    return s or "model"


# ============================================================================
# Puppeteer scraper helper — runs a small Node.js script that loads a URL,
# evaluates an extractor function in the page, and prints JSON to stdout.
# Used by NIH 3D, NASA fallback, and Smithsonian.
# ============================================================================

def _find_chrome_executable():
    """Locate the Chromium binary that puppeteer-core needs.

    puppeteer-core (unlike full `puppeteer`) requires `executablePath` to be
    specified explicitly. The browser lives at a version-pinned path inside
    the docker image's puppeteer cache, so we glob for it instead of
    hardcoding the version.
    """
    candidates = []
    candidates.extend(glob.glob("/opt/render3d/.cache/puppeteer/chrome/*/chrome-linux64/chrome"))
    candidates.extend(glob.glob("/root/.cache/puppeteer/chrome/*/chrome-linux64/chrome"))
    candidates.extend(glob.glob("/home/node/.cache/puppeteer/chrome/*/chrome-linux64/chrome"))
    # System-installed fallbacks
    for p in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
        if os.path.exists(p):
            candidates.append(p)
    # Pick the newest version (lex sort works because version strings sort correctly)
    candidates = sorted(candidates, reverse=True)
    return candidates[0] if candidates else None


def _puppeteer_extract(url, js_code, wait_selector=None, wait_ms=2000, timeout_sec=45, wait_until="networkidle2"):
    """Navigate to `url` with puppeteer-core, run `js_code` in the page, return parsed JSON.

    `js_code` should be the BODY of an async function returning a JSON-serializable
    value (NOT a complete function definition). Example:
        js_code = '''
            const cards = Array.from(document.querySelectorAll('.result'));
            return cards.map(c => ({ id: c.dataset.id, title: c.textContent }));
        '''

    Returns parsed JSON on success, or None if Puppeteer/Node failed.
    """
    # ESM bare-specifier resolution only walks up node_modules from the
    # script's directory, and /opt/render3d is read-only for the `node` user
    # so we can't drop the runner next to the package. Use an absolute
    # file:// URL to puppeteer-core's ESM entry — works from /tmp.
    pup_entry = "file:///opt/render3d/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js"
    chrome_path = _find_chrome_executable()
    if not chrome_path:
        print("_puppeteer_extract: Chromium binary not found in any known cache path")
        return None
    runner_js = (
        f"import * as puppeteerCore from '{pup_entry}';\n"
        "const puppeteer = puppeteerCore.default || puppeteerCore;\n"
        "(async () => {\n"
        "  let browser;\n"
        "  try {\n"
        "    browser = await puppeteer.launch({\n"
        "      headless: true,\n"
        f"      executablePath: {json.dumps(chrome_path)},\n"
        "      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],\n"
        "    });\n"
        "    const page = await browser.newPage();\n"
        "    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36');\n"
        f"    await page.goto({json.dumps(url)}, {{ waitUntil: {json.dumps(wait_until)}, timeout: {timeout_sec * 1000} }});\n"
    )
    if wait_selector:
        runner_js += (
            f"    try {{ await page.waitForSelector({json.dumps(wait_selector)}, {{ timeout: 15000 }}); }}\n"
            f"    catch (e) {{ /* fall through — let extractor return what it can */ }}\n"
        )
    if wait_ms:
        runner_js += f"    await new Promise(r => setTimeout(r, {wait_ms}));\n"
    runner_js += (
        "    const result = await page.evaluate(async () => {\n"
        f"      {js_code}\n"
        "    });\n"
        "    process.stdout.write(JSON.stringify(result));\n"
        "  } catch (e) {\n"
        "    process.stderr.write('PUPPETEER_ERR: ' + (e.message || String(e)) + '\\n');\n"
        "    process.exit(2);\n"
        "  } finally {\n"
        "    if (browser) try { await browser.close(); } catch (e) {}\n"
        "  }\n"
        "})();\n"
    )

    tmp = tempfile.mkdtemp(prefix="pup_extract_")
    try:
        # Write to /opt/render3d so puppeteer-core's relative imports resolve.
        # If that's not writable, fall back to a temp dir with NODE_PATH set.
        runner_path = "/opt/render3d/_pup_extract.mjs"
        try:
            with open(runner_path, "w", encoding="utf-8") as f:
                f.write(runner_js)
        except Exception:
            runner_path = os.path.join(tmp, "_pup_extract.mjs")
            with open(runner_path, "w", encoding="utf-8") as f:
                f.write(runner_js)

        env = os.environ.copy()
        env["NODE_PATH"] = "/opt/render3d/node_modules:" + env.get("NODE_PATH", "")

        proc = subprocess.run(
            ["node", runner_path],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 10,
            env=env,
        )
        if proc.returncode != 0:
            err = (proc.stderr or "").strip()
            print(f"_puppeteer_extract({url}): exit {proc.returncode}: {err[-400:]}")
            return None
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            print(f"_puppeteer_extract: bad JSON output: {proc.stdout[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"_puppeteer_extract({url}): timed out")
        return None
    finally:
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass


def _nih3d_download_entry(entry_id, label):
    """Walk every submission's workflowRun outputFiles for a GLB derivative.

    NIH 3D entries have multiple submissions (versions). Each submission has
    workflowRuns whose outputFiles are the renderer-friendly derivatives —
    that's where the GLBs live (input files are usually PDB / STL / etc).
    Download URL pattern:
        /api/submissions/{submissionId}/runs/{prefectRunId}/output-files/{fileId}
    """
    try:
        meta = requests.get(f"https://3d.nih.gov/api/entries/{entry_id}", timeout=15).json()
    except Exception as e:
        print(f"NIH 3D: API entry fetch failed for {entry_id}: {e}")
        return None

    title = entry_id
    submissions = meta.get("submissions") or []
    if isinstance(meta.get("entry"), dict):
        submissions = submissions or meta["entry"].get("submissions") or []

    # Collect every GLB candidate across all submissions/runs
    candidates = []  # (priority, sub_id, run_id, file_id, filename)
    for sub in submissions:
        sub_id = sub.get("submissionId")
        # Pull a friendly title from the latest submission with metadata
        md = sub.get("metadata") or {}
        if md.get("title"):
            title = md["title"]
        for run in sub.get("workflowRuns") or []:
            run_id = run.get("prefectRunId")
            for f in run.get("outputFiles") or []:
                loc = f.get("s3Location") or ""
                fname = loc.split("/")[-1]
                fid = f.get("fileId")
                lower = fname.lower()
                if not lower.endswith(".glb"):
                    continue
                # Priority: prefer "color" variants, then "vis" (visualizer-tuned), then anything
                pri = 0
                if "color" in lower:
                    pri += 3
                if "vis" in lower:
                    pri += 2
                if "print" in lower:
                    pri += 1
                if sub_id is None or run_id is None or fid is None:
                    continue
                candidates.append((pri, sub_id, run_id, fid, fname))

    if not candidates:
        print(f"NIH 3D: entry {entry_id} has no GLB derivatives in any submission")
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    pri, sub_id, run_id, file_id, fname = candidates[0]

    out_name = _safe_filename(title) + ".glb"
    download_url = f"https://3d.nih.gov/api/submissions/{sub_id}/runs/{run_id}/output-files/{file_id}"
    print(f"NIH 3D: downloading {out_name} (variant: {fname}) from {entry_id}")
    try:
        dl = requests.get(download_url, timeout=180, stream=True)
        if dl.status_code != 200:
            print(f"NIH 3D: download HTTP {dl.status_code}")
            return None
        with open(out_name, "wb") as f:
            for chunk in dl.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        print(f"NIH 3D: download failed: {e}")
        return None

    size = os.path.getsize(out_name)
    if size < 256:
        print(f"NIH 3D: download too small ({size} bytes), discarding")
        os.remove(out_name)
        return None
    print(f"Saved: {out_name} ({size} bytes)")
    dims = _measure_glb(out_name)
    _render_preview(out_name, dims)
    return out_name


# ============================================================================
# Local custom models — /media/custom_models/ inside the docker container
# (mounted from the user's assets folder). Instant lookup, no network. The
# user can drop new .glb files in here without changing any code or docs.
# ============================================================================

_LOCAL_MODEL_DIRS = [
    "/workspace/eidoverse/assets/models",  # canonical (ships inside eidoverse/)
    # repo-relative, so host-side runs (eido.py workflows, --build-previews)
    # find the same library without the container mount
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "eidoverse", "assets", "models"),
    "/media/custom_models",                # mount alias (same files, back-compat)
    os.path.expanduser("~/.eidoverse/custom_models"),
]


def _local_preview_path(src):
    """Canonical cached-preview path that sits NEXT TO a local model."""
    base = os.path.splitext(os.path.basename(src))[0]
    return os.path.join(os.path.dirname(src), f"{base}_preview.jpg")


_FORWARD_AXES_CACHE = None


def _forward_axis_for(src):
    """Curated driveAlong/faceToward forward-axis hint for a model whose nose
    direction is easy to misread from the preview (returns '+x'/'-x'/'+z'/'-z'
    or None). Read from `_forward_axes.json` in the model's dir — and, as a
    fallback, the canonical assets/models dir — keyed by filename stem."""
    global _FORWARD_AXES_CACHE
    if _FORWARD_AXES_CACHE is None:
        _FORWARD_AXES_CACHE = {}
        seen = set()
        for d in [os.path.dirname(src)] + _LOCAL_MODEL_DIRS:
            jp = os.path.join(d, "_forward_axes.json")
            if jp in seen or not os.path.exists(jp):
                continue
            seen.add(jp)
            try:
                with open(jp, encoding="utf-8") as f:
                    for k, v in json.load(f).items():
                        if not k.startswith("_"):
                            _FORWARD_AXES_CACHE.setdefault(k.lower(), v)
            except Exception:
                pass
    stem = os.path.splitext(os.path.basename(src))[0].lower()
    return _FORWARD_AXES_CACHE.get(stem)


def _ensure_local_preview(src, dims=None):
    """Make sure a <name>_preview.jpg exists next to the canonical model.

    Renders it ONCE (GPU) and caches it beside the model so every future
    fetch — and every agent — reuses the same image with zero re-render and,
    crucially, zero .glb copy. Returns the cached preview path, or None if the
    render failed (the model is still usable; the preview is a convenience).
    """
    cached = _local_preview_path(src)
    if os.path.exists(cached):
        return cached
    if dims is None:
        dims = _measure_glb(src)
    try:
        return _render_preview(src, dims)  # writes <name>_preview.jpg beside src
    except Exception as e:
        print(f"Local: preview render failed ({e}); model still usable without it.")
        return None


def _deliver_local_model(path):
    """Reference a local model IN PLACE — never copy the .glb into cwd.

    Local models already live at a canonical path; copying the mesh into every
    work folder that used it bled the disk (the same 2–20 MB glb duplicated per
    scene, repeatedly). Instead: leave the file where it is, ensure a cached
    preview sits beside it, and return the CANONICAL path for the agent to put
    straight into scene.json `assets` — the Deno harness `loadAssets()` reads
    any path, so no local copy is ever needed.
    """
    src = os.path.abspath(path)
    print(f"Local model (referenced IN PLACE — not copied): {src} ({os.path.getsize(src)} bytes)")
    print(f"  → put THIS exact path in your scene.json `assets`. Do NOT copy the .glb into your work folder.")
    dims = _measure_glb(src)
    preview = _ensure_local_preview(src, dims)
    if preview:
        print(f"Preview: {preview}")
    fwd = _forward_axis_for(src)
    if fwd:
        print(f"driveAlong/faceToward forward axis: '{fwd}'  (curated — this model's nose is "
              f"easy to misread from the preview; pass forward:'{fwd}' so it doesn't drive backward)")
    return src


def _all_local_models():
    """Every local model file across the curated dirs (absolute paths)."""
    found = []
    for d in _LOCAL_MODEL_DIRS:
        if not os.path.isdir(d):
            continue
        for ext in ("*.glb", "*.gltf"):
            found.extend(glob.glob(os.path.join(d, ext)))
    return [os.path.abspath(p) for p in found]


def build_local_previews():
    """Pre-render the cached <name>_preview.jpg for every local model that
    lacks one. Run ONCE (GPU) so agents never re-render a local preview and
    never copy a .glb into their work folder. GPU rule: run only when no live
    render is active."""
    models = _all_local_models()
    if not models:
        print("No local models found in: " + ", ".join(_LOCAL_MODEL_DIRS))
        return
    missing = [m for m in models if not os.path.exists(_local_preview_path(m))]
    print(f"Local models: {len(models)} total, {len(missing)} missing a cached preview.")
    for i, m in enumerate(missing, 1):
        print(f"[{i}/{len(missing)}] {os.path.basename(m)}")
        _ensure_local_preview(m)
    print(f"Done. Previews cached next to each model in {', '.join(_LOCAL_MODEL_DIRS)}.")


def list_local_models():
    """Print a catalog of all local models (path + dims + preview) for the
    agent context — so agents reference models IN PLACE instead of fetching
    (and copying) them."""
    models = _all_local_models()
    if not models:
        print("No local models found.")
        return
    print(f"LOCAL MODELS ({len(models)}) — reference these paths directly in scene.json `assets`; never copy them:")
    for m in sorted(models):
        dims = _measure_glb(m)
        dim_str = (f"{dims[0]:.2f}x{dims[1]:.2f}x{dims[2]:.2f}m" if dims else "dims:?")
        prev = _local_preview_path(m)
        prev_str = prev if os.path.exists(prev) else "(no preview cached)"
        fwd = _forward_axis_for(m)
        fwd_str = f"  forward:'{fwd}'" if fwd else ""
        print(f"  {m}  [{dim_str}]  preview: {prev_str}{fwd_str}")


# ============================================================================
# Poly Haven — REST API, the fastest of the four sources. Tries exact ID
# first, then falls back to a tag/category/name search.
# ============================================================================

# Curated synonyms: users say one word, Poly Haven names the asset another.
# Bidirectional pairs are listed once and mirrored at load time below. Keep
# these to high-confidence household/prop vocabulary — over-broad synonyms
# (e.g. mapping "light" → everything) reintroduce the noise word-boundary
# matching was added to kill.
_SYNONYM_SEED = {
    "tv": ["television"], "crt": ["tv", "television"], "telly": ["tv", "television"],
    "couch": ["sofa"], "settee": ["sofa", "couch"],
    "rug": ["carpet"], "mat": ["rug", "carpet"],
    "picture": ["painting", "frame"], "poster": ["frame", "picture"],
    "artwork": ["art", "painting", "frame"], "photo": ["frame", "picture"],
    "fridge": ["refrigerator"], "cooker": ["stove", "oven"],
    "trashcan": ["bin", "garbage"], "trash": ["bin", "garbage", "waste"],
    "pot": ["planter", "vase"], "plant": ["botany", "potted", "houseplant"],
    "couch": ["sofa"], "bookcase": ["bookshelf", "shelf"], "bookshelf": ["shelf"],
}


def _build_synonyms(seed):
    out = {}
    for k, vs in seed.items():
        out.setdefault(k, set()).update(vs)
        for v in vs:  # mirror so the mapping works in both directions
            out.setdefault(v, set()).add(k)
    return out


_SYNONYMS = _build_synonyms(_SYNONYM_SEED)


def _stem(t):
    # Light suffix stripping so "framed"→"frame", "books"→"book",
    # "cooking"→"cook". Only used to ADD a variant, never to replace the
    # original, so an occasional bad stem just scores zero (harmless).
    for suf in ("ing", "ed", "es", "s"):
        if len(t) > len(suf) + 2 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def _expand_term(t):
    """Query term → set of {term, stem, synonyms} variants to match against."""
    variants = {t, _stem(t)}
    variants |= _SYNONYMS.get(t, set())
    return variants


# NOTE: AmbientCG was evaluated as a model source and intentionally NOT wired in.
# Its 3D models ship only as .usdc / .blend / .mtlx / .tres (no glTF/GLB), which
# this pipeline's GLTFLoader can't load and we don't ship a converter. AmbientCG
# IS used for textures + HDRIs (see fetch_texture.py / fetch_hdri.py) where it
# delivers native-loadable assets. Poly Haven covers food/props as GLB.


# ============================================================================
# ALL-SOURCE AGGREGATION + THEME RANKING
# ----------------------------------------------------------------------------
# The legacy fetch_model() tried sources in order and RETURNED ON THE FIRST
# HIT — so a local match short-circuited and the agent never saw the (often
# better-themed) online options. That's why the one damaged/apocalyptic local
# streetlight kept landing in clean scenes: "streetlight" hit local, search
# stopped, the clean Poly Haven lamps were never even fetched.
#
# New design — split FIND from DELIVER:
#   * _find_<source>(query)  → returns CANDIDATES (metadata only, no download)
#     in a common schema: {source, ref, name, text, relevance, exact?, token}.
#     `text` = name + tags + categories + description — the string theme
#     scoring reads. `ref` is whatever _deliver_<source> needs to download.
#   * All five _find_* run IN PARALLEL (threads; the work is network I/O).
#   * Relevance is normalized WITHIN each source to 0–1 so a Smithsonian rank
#     and a Poly Haven score become comparable.
#   * Theme fit is SEMANTIC, not keyword-based: a free embedding model (default
#     Jina, any OpenAI-compatible /v1/embeddings endpoint via env) embeds the
#     theme string and every candidate's descriptive text and scores by cosine
#     similarity — the model actually understands that "clean futuristic city"
#     opposes "apocalyptic destroyed rubble". Theme re-ranks RELATIVE to the
#     candidate set (z-scored), so it reorders similar-relevance items without
#     promoting off-query ones. No embedding key/endpoint → relevance-only.
#   * combined = relevance_norm × theme_mult → rank ALL candidates together,
#     deliver only the winner, and print the alternatives spanning EVERY source
#     with re-fetch tokens. Exact name/id pins still short-circuit.
#
# Eidoverse ships STANDALONE — this stays decoupled from any harness: the
# embedder is a plain HTTP call configured by env, with a graceful fallback.
# ============================================================================

# Embedding endpoint config — provider-agnostic, defaults to Jina's free tier.
# Override any of these for a different provider (HF, Cohere, OpenAI, a local
# server). EIDOVERSE_EMBED_KEY falls back to JINA_AI_KEY so an existing Jina
# key just works; with no key at all, theme ranking is skipped (relevance-only).
_EMBED_URL = os.environ.get("EIDOVERSE_EMBED_URL", "https://api.jina.ai/v1/embeddings")
_EMBED_MODEL = os.environ.get("EIDOVERSE_EMBED_MODEL", "jina-embeddings-v3")
_EMBED_KEY = (os.environ.get("EIDOVERSE_EMBED_KEY")
              or os.environ.get("JINA_AI_KEY")
              or os.environ.get("OPENAI_API_KEY")  # if pointed at OpenAI
              or "").strip()


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _cos(a, b):
    """Cosine of two already-unit-normalized vectors."""
    return sum(x * y for x, y in zip(a, b))


def _embed_texts(texts):
    """Embed a batch of strings via an OpenAI-compatible /v1/embeddings endpoint.

    Returns a list of unit-normalized vectors (one per input), or None if
    embeddings are unavailable — no endpoint reachable, no key where the
    provider needs one, a shape mismatch, or repeated failure. Callers treat
    None as "skip theme ranking" so the tool never hard-breaks. One batched
    call for the whole candidate set, so it's a single round-trip, not N."""
    if not texts:
        return None
    body = {"model": _EMBED_MODEL, "input": texts}
    # Jina v3 supports task-tuned vectors; "text-matching" gives symmetric
    # similarity (theme ↔ object), which is what we want here. Only send it to
    # Jina — other OpenAI-compatible endpoints may reject unknown fields.
    if "jina.ai" in _EMBED_URL:
        body["task"] = "text-matching"
    headers = {"Content-Type": "application/json"}
    if _EMBED_KEY:
        headers["Authorization"] = f"Bearer {_EMBED_KEY}"
    for attempt in range(3):
        try:
            r = requests.post(_EMBED_URL, json=body, headers=headers, timeout=30)
            if r.status_code in (429, 500, 503):
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json().get("data") or []
            vecs = [d.get("embedding") for d in data]
            if len(vecs) != len(texts) or any(v is None for v in vecs):
                print(f"[theme] embedding response shape mismatch "
                      f"({len(vecs)} vs {len(texts)}); ranking by relevance only.")
                return None
            return [_unit(v) for v in vecs]
        except Exception as e:
            if attempt == 2:
                print(f"[theme] embeddings unavailable "
                      f"({type(e).__name__}: {str(e)[:90]}); ranking by relevance only. "
                      f"Set EIDOVERSE_EMBED_KEY (or JINA_AI_KEY) to enable theme fit.")
            else:
                time.sleep(1 + attempt)
    return None


def _apply_theme_ranking(cands, theme):
    """Score each candidate's theme fit by SEMANTIC similarity to `theme` and
    fold it into `combined` as a relative multiplier. Mutates cands in place.

    Cosine similarity is re-centered across the candidate set (z-score): a
    candidate more on-theme than the set average gets a boost, one further off
    (e.g. a ruined prop in a clean scene) gets a penalty — robust to cosine's
    absolute offset. With no theme or no embeddings, theme_mult = 1.0 and
    ranking is pure relevance."""
    for c in cands:
        c["theme_sim"] = None
        c["theme_mult"] = 1.0
        c["combined"] = c["relevance_norm"]

    if not theme:
        return False

    texts = [theme] + [(c.get("text") or c["name"]) for c in cands]
    embs = _embed_texts(texts)
    if not embs:
        return False

    tvec = embs[0]
    sims = []
    for c, cv in zip(cands, embs[1:]):
        s = _cos(tvec, cv)
        c["theme_sim"] = s
        sims.append(s)

    if len(sims) > 1:
        mu = sum(sims) / len(sims)
        sd = (sum((s - mu) ** 2 for s in sims) / len(sims)) ** 0.5 or 1.0
        for c in cands:
            z = (c["theme_sim"] - mu) / sd
            # ±0.32 multiplier per standard deviation of theme fit, clamped so
            # theme reorders but never fully overrides relevance.
            c["theme_mult"] = max(0.30, min(1.70, 1.0 + 0.32 * z))
            c["combined"] = c["relevance_norm"] * c["theme_mult"]
    return True

# ── Per-source FIND functions (candidates only — NO download) ───────────────

def _find_local(query):
    candidates = _all_local_models()
    if not candidates:
        return []
    q_exact = query.strip().lower()
    terms = [t for t in re.split(r"\s+", query.lower()) if t]
    out = []
    for path in candidates:
        fn = os.path.basename(path).lower()
        stem = re.sub(r"\.(glb|gltf)$", "", fn)
        words = re.sub(r"[_\-]+", " ", stem)
        words = re.sub(r"([a-z])([A-Z])", r"\1 \2", words).lower()
        is_exact = (q_exact == fn or q_exact == stem)
        toks = words.split()
        score = 0
        hit_terms = 0
        for term in terms:
            if re.search(r"\b" + re.escape(term) + r"\b", words):
                score += 5
                hit_terms += 1
            # Compound concatenated names ("scifihovercar" → "hovercar", "car"):
            # a term may be a PREFIX or SUFFIX of a token, but NOT an arbitrary
            # infix — `term in stem` matched "tree" inside "s-tree-t" (street)
            # and "meter" inside "perimeter". Prefix/suffix keeps the real
            # compound hits and drops the buried-substring false positives.
            elif len(term) >= 3 and any(
                tok != term and (tok.startswith(term) or tok.endswith(term))
                for tok in toks
            ):
                score += 4
                hit_terms += 1
        if hit_terms >= 2:
            score += (hit_terms - 1) * 3
        if not is_exact and score <= 0:
            continue
        out.append({
            "source": "local",
            "ref": path,
            "name": os.path.basename(path),
            "text": words,
            "relevance": score + (100 if is_exact else 0),
            "exact": is_exact,
            "token": os.path.basename(path),
        })
    return out


def _find_polyhaven(query):
    out = []
    # Exact ID pin
    try:
        resp = requests.get(f"https://api.polyhaven.com/files/{query}", timeout=10)
        if resp.status_code == 200 and "gltf" in resp.json():
            return [{
                "source": "polyhaven", "ref": query, "name": query, "text": query,
                "relevance": 1000, "exact": True, "token": query,
            }]
    except Exception:
        pass

    try:
        catalog = requests.get("https://api.polyhaven.com/assets?t=models", timeout=15).json()
    except Exception as e:
        print(f"Poly Haven: catalog fetch failed: {e}")
        return out

    terms = [t for t in re.split(r"\s+", query.lower()) if t]
    meaningful_terms = [t for t in terms if not t.isdigit()] or terms
    variant_sets = [_expand_term(t) for t in meaningful_terms]

    def _word_in(term, text):
        return re.search(r"\b" + re.escape(term) + r"\b", text) is not None

    def _any_word_in(variants, text):
        return any(_word_in(v, text) for v in variants)

    for mid, info in catalog.items():
        cats = [c.lower() for c in info.get("categories", [])]
        tags = [t.lower() for t in info.get("tags", [])]
        tagset = set(tags)
        tag_tokens = set()
        for tg in tags:
            parts = [w for w in re.split(r"[\s\-/_]+", tg) if w]
            if len(parts) > 1:
                tag_tokens.update(parts)
        name = info.get("name", "").lower()
        mid_lower = mid.lower()

        name_hits = sum(1 for vs in variant_sets if _any_word_in(vs, name) or _any_word_in(vs, mid_lower))
        cat_hits = sum(1 for vs in variant_sets if any(_any_word_in(vs, c) for c in cats))
        tag_hits = sum(1 for vs in variant_sets if any(_any_word_in(vs, tg) for tg in tags))
        exact_tag_hits = sum(1 for vs in variant_sets if vs & tagset)
        tag_token_hits = sum(1 for vs in variant_sets if vs & tag_tokens)

        if name_hits == 0 and cat_hits == 0 and exact_tag_hits == 0 and tag_token_hits == 0:
            continue
        if info.get("polycount", 0) >= 1_000_000:
            continue

        score = name_hits * 5 + exact_tag_hits * 4 + tag_token_hits * 3 + cat_hits * 2 + tag_hits * 1
        if score <= 0:
            continue
        text = " ".join([name, mid_lower, " ".join(cats), " ".join(tags)])
        out.append({
            "source": "polyhaven", "ref": mid, "name": info.get("name", mid),
            "text": text, "relevance": score, "token": mid,
        })
    return out


_NIH_DISCOVER_JS = """
    // NIH 3D discover page is React. Wait briefly for cards then collect them.
    await new Promise(r => setTimeout(r, 1500));
    const out = [];
    const sels = [
        'a[href*="/entries/3DPX"]',
        'a[href*="/entries/"]',
        '.result-card a',
        '.search-result a',
    ];
    let links = [];
    for (const s of sels) {
        links = Array.from(document.querySelectorAll(s));
        if (links.length) break;
    }
    for (const a of links.slice(0, 12)) {
        const href = a.getAttribute('href') || '';
        const m = href.match(/entries\\/(3DPX[-_]?\\d+)/i);
        if (m) {
            out.push({
                id: m[1].toUpperCase().replace('_', '-'),
                title: (a.textContent || '').trim().slice(0, 120),
            });
        }
    }
    const seen = new Set();
    return out.filter(o => !seen.has(o.id) && seen.add(o.id));
"""


def _find_nih3d(query):
    id_match = re.search(r'(3DPX[-_ ]?\d+)', query, re.I)
    if id_match:
        entry_id = id_match.group(1).replace("_", "-").replace(" ", "-").upper()
        return [{
            "source": "nih3d", "ref": entry_id, "name": entry_id, "text": query,
            "relevance": 1000, "exact": True, "token": entry_id,
        }]
    discover_url = f"https://3d.nih.gov/discover?q={requests.utils.quote(query)}&sort=relevance"
    results = _puppeteer_extract(
        discover_url, _NIH_DISCOVER_JS,
        wait_selector="a[href*='/entries/']", wait_ms=1500,
    )
    if not results:
        return []
    n = len(results)
    return [{
        "source": "nih3d", "ref": r["id"], "name": r.get("title") or r["id"],
        "text": (r.get("title") or "") + " " + r["id"],
        "relevance": n - i,  # site relevance order (top = best)
        "token": r["id"],
    } for i, r in enumerate(results)]


_NASA_LISTING_JS = """
    const links = Array.from(document.querySelectorAll('a'))
        .map(a => ({ href: a.href, text: (a.textContent || '').trim().slice(0, 200) }))
        .filter(l => l.href && (l.href.includes('3d-model') || l.href.includes('3d-resources/')));
    return links.slice(0, 30);
"""

_NASA_DETAIL_JS = """
    const links = Array.from(document.querySelectorAll('a'))
        .map(a => a.href)
        .filter(h => /\\.(glb|gltf)(\\?|$)/i.test(h));
    return links.slice(0, 5);
"""


def _find_nasa(query):
    terms = [t for t in re.split(r"\s+", query.lower()) if t]
    out = []
    # 1. GitHub Contents API (fast, no scrape)
    try:
        r = requests.get(
            "https://api.github.com/repos/nasa/NASA-3D-Resources/contents/3D%20Models",
            timeout=15, headers={"Accept": "application/vnd.github+json"},
        )
        if r.status_code == 200:
            for e in r.json():
                if e.get("type") != "dir":
                    continue
                name = e.get("name", "")
                ln = name.lower()
                score = sum(2 if t in ln else 0 for t in terms)
                if terms and all(t in ln for t in terms):
                    score += 3
                if score > 0:
                    out.append({
                        "source": "nasa",
                        "ref": {"kind": "github", "path": e.get("path", ""), "name": name},
                        "name": name, "text": name, "relevance": score, "token": name,
                    })
            if out:
                return out
        else:
            print(f"NASA GitHub API: HTTP {r.status_code} (rate-limited?)")
    except Exception as e:
        print(f"NASA GitHub API failed: {e}")

    # 2. Puppeteer fallback: scrape science.nasa.gov/3d-resources/
    listing = _puppeteer_extract("https://science.nasa.gov/3d-resources/", _NASA_LISTING_JS, wait_ms=2000)
    if not listing:
        return out
    for l in listing:
        text = (l.get("text") or "").lower()
        href = (l.get("href") or "").lower()
        score = sum(1 for t in terms if t in text or t in href)
        if score > 0:
            out.append({
                "source": "nasa",
                "ref": {"kind": "scrape", "href": l.get("href"), "name": l.get("text")},
                "name": l.get("text") or "nasa_model", "text": (l.get("text") or ""),
                "relevance": score, "token": (l.get("text") or "nasa model"),
            })
    return out


_SI_LIST_JS = r"""
    await new Promise(r => setTimeout(r, 1200));
    const out = [];
    const seen = new Set();
    for (const a of document.querySelectorAll('a[href*="/object/3d/"]')) {
        const href = a.getAttribute('href') || '';
        const m = href.match(/\/object\/3d\/([^/:]+):([a-f0-9-]{36})/i);
        if (!m) continue;
        const key = m[2];
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({
            href: a.href,
            slug: m[1],
            uuid: m[2],
            text: (a.textContent || '').trim().slice(0, 200),
        });
        if (out.length >= 12) break;
    }
    return out;
"""

_SI_DETAIL_JS = r"""
    await new Promise(r => setTimeout(r, 2000));
    const collected = new Set();
    for (const a of document.querySelectorAll('a')) {
        const h = a.getAttribute('href') || '';
        if (/\.glb(\?|$|#)/i.test(h)) collected.add(h);
    }
    for (const el of document.querySelectorAll('[data-href], [data-url], [data-download], [data-target]')) {
        for (const attr of ['data-href','data-url','data-download','data-target']) {
            const v = el.getAttribute(attr) || '';
            if (v && /\.glb/i.test(v)) collected.add(v);
        }
    }
    for (const panel of document.querySelectorAll('[id*="tab-download"]')) {
        for (const a of panel.querySelectorAll('a')) {
            const h = a.getAttribute('href') || '';
            if (h) collected.add(h);
        }
    }
    const html = document.documentElement.outerHTML;
    return {
        hits: Array.from(collected),
        html_chunk: html.slice(0, 400000),
    };
"""

_SI_STOP = {"of", "in", "the", "a", "an", "and", "or", "on", "at", "to", "for", "with", "by", "from"}


def _find_smithsonian(query):
    explore_url = f"https://3d.si.edu/explore?edan_q={requests.utils.quote(query)}"
    results = _puppeteer_extract(
        explore_url, _SI_LIST_JS,
        wait_selector="a[href*='/object/3d/']", wait_ms=1500,
    )
    if not results:
        return []

    def _mk(r, rel):
        return {
            "source": "smithsonian",
            "ref": {"href": r["href"], "uuid": r["uuid"], "slug": r["slug"], "text": r.get("text")},
            "name": r.get("text") or r["slug"],
            "text": (r["slug"].replace("-", " ") + " " + (r.get("text") or "")),
            "relevance": rel, "token": r["slug"],
        }

    meaningful = [t for t in re.split(r"\s+", query.lower()) if t and t not in _SI_STOP and len(t) > 2]
    if meaningful:
        min_hits = max(1, (len(meaningful) + 1) // 2)
        scored = []
        for r in results:
            slug = (r.get("slug") or "").lower().replace("-", " ")
            text = (r.get("text") or "").lower()
            hits = sum(1 for t in meaningful if t in slug or t in text)
            if hits >= min_hits:
                scored.append((hits, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [_mk(r, hits) for hits, r in scored]
    n = len(results)
    return [_mk(r, n - i) for i, r in enumerate(results)]


# ── Per-source DELIVER functions (download the chosen candidate) ────────────

def _deliver_polyhaven(model_id, resolution="1k"):
    try:
        files = requests.get(f"https://api.polyhaven.com/files/{model_id}", timeout=10).json()
    except Exception as e:
        print(f"Poly Haven: file metadata failed: {e}")
        return None
    if "gltf" not in files:
        print("Poly Haven: no gltf format available")
        return None

    gltf_data = files["gltf"][resolution]["gltf"]
    main_url = gltf_data["url"]
    main_fname = main_url.split("/")[-1]

    model_dir = f"/tmp/{model_id}"
    os.makedirs(model_dir, exist_ok=True)

    print(f"Downloading {model_id} at {resolution}...")
    resp = requests.get(main_url, timeout=60)
    with open(f"{model_dir}/{main_fname}", "wb") as f:
        f.write(resp.content)

    for fname, fdata in gltf_data.get("include", {}).items():
        filepath = f"{model_dir}/{fname}"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        resp = requests.get(fdata["url"], timeout=60)
        with open(filepath, "wb") as f:
            f.write(resp.content)
        print(f"  {fname} ({len(resp.content)} bytes)")

    with open(f"{model_dir}/{main_fname}") as f:
        gltf = json.load(f)

    for buf in gltf.get("buffers", []):
        uri = buf.get("uri")
        if uri and not uri.startswith("data:"):
            with open(f"{model_dir}/{uri}", "rb") as f:
                data = base64.b64encode(f.read()).decode()
            buf["uri"] = f"data:application/octet-stream;base64,{data}"

    for img in gltf.get("images", []):
        uri = img.get("uri")
        if uri and not uri.startswith("data:"):
            ext = uri.rsplit(".", 1)[-1].lower()
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(
                ext, "application/octet-stream"
            )
            with open(f"{model_dir}/{uri}", "rb") as f:
                data = base64.b64encode(f.read()).decode()
            img["uri"] = f"data:{mime};base64,{data}"

    embedded_path = f"{_safe_filename(model_id)}_embedded.gltf"
    with open(embedded_path, "w") as f:
        json.dump(gltf, f)
    print(f"Done: {embedded_path} ({os.path.getsize(embedded_path)} bytes)")

    nodes_with_mesh = [
        n.get("name", f"node_{i}")
        for i, n in enumerate(gltf.get("nodes", []))
        if n.get("mesh") is not None
    ]
    if len(nodes_with_mesh) > 1:
        print(f"Parts ({len(nodes_with_mesh)}): {', '.join(nodes_with_mesh)}")

    dims = _measure_glb(embedded_path)
    _render_preview(embedded_path, dims)
    return embedded_path


def _deliver_nasa(ref, label=None):
    kind = ref.get("kind")
    if kind == "github":
        path = ref["path"]
        name = ref["name"]
        folder_url = f"https://api.github.com/repos/nasa/NASA-3D-Resources/contents/{requests.utils.quote(path)}"
        fr = requests.get(folder_url, timeout=15, headers={"Accept": "application/vnd.github+json"})
        if fr.status_code != 200:
            return None
        glb_entry = next((f for f in fr.json() if (f.get("name") or "").lower().endswith(".glb")), None)
        if not glb_entry:
            return None
        raw_url = (
            "https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/"
            + requests.utils.quote(path) + "/" + requests.utils.quote(glb_entry["name"])
        )
        out_name = _safe_filename(name) + ".glb"
        print(f"NASA: downloading {out_name}")
        dl = requests.get(raw_url, timeout=120, stream=True)
        if dl.status_code != 200:
            return None
        with open(out_name, "wb") as f:
            for chunk in dl.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        print(f"Saved: {out_name} ({os.path.getsize(out_name)} bytes)")
        dims = _measure_glb(out_name)
        _render_preview(out_name, dims)
        return out_name

    if kind == "scrape":
        href = ref["href"]
        print(f"NASA scrape: detail page {href}")
        files = _puppeteer_extract(href, _NASA_DETAIL_JS, wait_ms=1500)
        if not files:
            return None
        out_name = _safe_filename(ref.get("name") or "nasa_model") + ".glb"
        dl = requests.get(files[0], timeout=120, stream=True)
        if dl.status_code != 200:
            return None
        with open(out_name, "wb") as f:
            for chunk in dl.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        print(f"Saved: {out_name} ({os.path.getsize(out_name)} bytes)")
        dims = _measure_glb(out_name)
        _render_preview(out_name, dims)
        return out_name
    return None


def _deliver_smithsonian(ref):
    cand = ref
    title = cand.get("text") or cand.get("slug") or "smithsonian_model"
    print(f"Smithsonian: detail {cand['href']}")
    detail = _puppeteer_extract(
        cand["href"], _SI_DETAIL_JS,
        wait_ms=2500, wait_until="domcontentloaded", timeout_sec=60,
    )
    if not detail:
        return None

    urls = set(detail.get("hits", []))
    html = detail.get("html_chunk", "")
    if html:
        for m in re.finditer(r'cdn\.3d-api\.si\.edu/([a-f0-9-]{36})/([^\s"\'<>?]+\.glb)', html):
            urls.add(f"https://cdn.3d-api.si.edu/{m.group(1)}/{m.group(2)}")
        for m in re.finditer(r'3d_package:([a-f0-9-]{36})/resources/([^\s"\'<>?]+\.glb)', html):
            urls.add(f"https://3d-api.si.edu/content/document/3d_package:{m.group(1)}/resources/{m.group(2)}")
        for m in re.finditer(r'([a-zA-Z0-9_-]+_std(?:_draco)?\.glb)', html):
            urls.add(
                f"https://3d-api.si.edu/content/document/3d_package:{cand['uuid']}/resources/{m.group(1)}"
            )

    normalized = []
    for u in urls:
        cdn_m = re.search(r'cdn\.3d-api\.si\.edu/([a-f0-9-]{36})/(.+\.glb)', u)
        if cdn_m:
            normalized.append(
                f"https://3d-api.si.edu/content/document/3d_package:{cdn_m.group(1)}/resources/{cdn_m.group(2)}"
            )
            continue
        if 'content/document/3d_package' in u and u.lower().endswith('.glb'):
            normalized.append(u)
            continue
        if u.lower().endswith('.glb') and u.startswith('http'):
            normalized.append(u)

    def _rank(u):
        ul = u.lower()
        if "_std_draco.glb" in ul:
            return 0
        if "_std.glb" in ul:
            return 1
        return 2

    normalized = sorted(set(normalized), key=_rank)
    if not normalized:
        print(f"Smithsonian: no GLB URLs found on detail page for {cand['slug']}")
        return None

    for url in normalized[:3]:
        out_name = _safe_filename(title) + ".glb"
        try:
            print(f"Smithsonian: downloading {url}")
            dl = requests.get(url, timeout=180, stream=True, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36",
                "Referer": cand["href"],
            })
            if dl.status_code != 200:
                print(f"Smithsonian: HTTP {dl.status_code}")
                continue
            with open(out_name, "wb") as f:
                for chunk in dl.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            size = os.path.getsize(out_name)
            if size < 1024:
                print(f"Smithsonian: download too small ({size} bytes), skipping")
                os.remove(out_name)
                continue
            print(f"Saved: {out_name} ({size} bytes)")
            dims = _measure_glb(out_name)
            _render_preview(out_name, dims)
            return out_name
        except Exception as e:
            print(f"Smithsonian: download failed: {e}")
            continue
    return None


def _deliver_candidate(cand, resolution="1k"):
    src = cand["source"]
    try:
        if src == "local":
            return _deliver_local_model(cand["ref"])
        if src == "polyhaven":
            return _deliver_polyhaven(cand["ref"], resolution)
        if src == "nih3d":
            return _nih3d_download_entry(cand["ref"], cand.get("name") or cand["ref"])
        if src == "nasa":
            return _deliver_nasa(cand["ref"], cand.get("name"))
        if src == "smithsonian":
            return _deliver_smithsonian(cand["ref"])
    except Exception as e:
        print(f"[{src}] deliver error: {e}")
        return None
    return None


_FIND_FUNCS = [
    ("local", _find_local),
    ("polyhaven", _find_polyhaven),
    ("nih3d", _find_nih3d),
    ("nasa", _find_nasa),
    ("smithsonian", _find_smithsonian),
]


def _normalize_relevance(cands):
    """Scale relevance to 0–1 WITHIN each source so a Smithsonian rank and a
    Poly Haven score become comparable (top hit of each source → 1.0)."""
    by_src = {}
    for c in cands:
        by_src.setdefault(c["source"], []).append(c)
    for group in by_src.values():
        mx = max((c["relevance"] for c in group), default=0) or 1
        for c in group:
            c["relevance_norm"] = c["relevance"] / mx


def _print_alternatives(cands, delivered):
    others = [c for c in cands if c is not delivered]
    if not others:
        return
    print("\nAlternatives across all sources — re-fetch a specific one by its token:")
    shown = {}
    for c in others:
        bucket = shown.setdefault(c["source"], [])
        if len(bucket) < 3:
            bucket.append(c)
            tok = c.get("token") or c["name"]
            print(f'    [{c["source"]:>11}] python3 fetch_model.py "{tok}"')


def fetch_model(query, theme=None, resolution="1k"):
    """Query EVERY source in parallel, rank all candidates by relevance + theme
    fit, deliver only the winner, and surface alternatives from every source.

    `theme` (optional) = the video's mood/setting (e.g. "clean futuristic city",
    "ruined post-apocalyptic street"). It pushes condition-clashing models down
    so a damaged prop doesn't land in a pristine scene (and vice-versa)."""
    all_cands = []
    exact = []
    with ThreadPoolExecutor(max_workers=len(_FIND_FUNCS)) as ex:
        futs = {ex.submit(fn, query): name for name, fn in _FIND_FUNCS}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                cands = fut.result() or []
            except Exception as e:
                print(f"[{name}] find failed: {e}")
                cands = []
            for c in cands:
                (exact if c.get("exact") else all_cands).append(c)

    # Exact name/id pin → deliver immediately, bypass ranking (the agent asked
    # for THIS specific model — honour it). Prefer local/Poly Haven exacts.
    exact.sort(key=lambda c: c["relevance"], reverse=True)
    for c in exact:
        print(f"Exact match pinned: [{c['source']}] {c['name']}")
        out = _deliver_candidate(c, resolution)
        if out:
            return out

    if not all_cands:
        print(f"No matches in any source for '{query}'. Try different search terms for the same thing.")
        return None

    _normalize_relevance(all_cands)
    # Semantic theme ranking: a real embedding model decides which candidates
    # fit the scene (cosine of theme ↔ each candidate's text), folded in as a
    # relative multiplier on relevance. No theme / no embeddings → relevance-only.
    themed = _apply_theme_ranking(all_cands, theme)
    all_cands.sort(key=lambda c: c["combined"], reverse=True)

    hdr = f"\nAll-source candidates for '{query}'"
    if theme:
        hdr += f"  (theme: {theme})" + ("" if themed else "  [embeddings off → relevance-only]")
    print(hdr + ":")
    for c in all_cands[:12]:
        sim = c.get("theme_sim")
        sim_str = f" sim={sim:+.2f} ×{c['theme_mult']:.2f}" if sim is not None else ""
        print(f"  [{c['source']:>11}] {c['name'][:44]:44}  "
              f"rel={c['relevance_norm']:.2f}{sim_str} → {c['combined']:.2f}")

    # Weighted-random for variety (the same query shouldn't always return the
    # identical model) — but ONLY among genuinely COMPARABLE candidates. The
    # random pool is the top-N filtered to within 80% of the best combined
    # score, so a clearly-worse-themed option (e.g. a clean streetlight when the
    # brief is "bombed-out ruins") is never picked just by chance; when one
    # candidate dominates, the pool collapses to it and the pick is deterministic.
    top_n = all_cands[:8]
    best = top_n[0]["combined"]
    pool = [c for c in top_n if c["combined"] >= 0.80 * best] or top_n[:1]
    weights = [c["combined"] for c in pool]   # all > 0 (relevance_norm × mult)
    try:
        winner = random.choices(pool, weights=weights, k=1)[0]
    except Exception:
        winner = pool[0]
    print(f"\nAuto-pick: [{winner['source']}] {winner['name']} "
          f"(combined {winner['combined']:.2f}; {len(pool)} comparable in pool)")

    order = [winner] + [c for c in all_cands if c is not winner]
    for c in order:
        out = _deliver_candidate(c, resolution)
        if out:
            _print_alternatives(all_cands, delivered=c)
            return out
        print(f"[{c['source']}] delivery failed, trying next-best candidate…")
    print(f"All candidates failed to deliver for '{query}'.")
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python3 fetch_model.py "search terms"')
        print('       python3 fetch_model.py "search terms" --theme "clean futuristic city"')
        print('              ↑ theme = the video\'s mood/setting; ranks models for theme-fit and')
        print('                pushes condition-clashing props down (no damaged streetlight in a clean scene).')
        print('       python3 fetch_model.py --build-previews   # pre-render cached previews for all local models (run once, GPU)')
        print('       python3 fetch_model.py --list-local        # catalog of local models (path + dims + preview) for agent context')
        sys.exit(1)
    if sys.argv[1] == "--build-previews":
        build_local_previews()
        sys.exit(0)
    if sys.argv[1] in ("--list-local", "--list"):
        list_local_models()
        sys.exit(0)

    # Parse: positional query + optional --theme "..." (or --theme=...).
    query = None
    theme = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--theme":
            if i + 1 < len(args):
                theme = args[i + 1]
                i += 2
                continue
            i += 1
            continue
        if a.startswith("--theme="):
            theme = a.split("=", 1)[1]
            i += 1
            continue
        if query is None:
            query = a
        i += 1

    if not query:
        print('Usage: python3 fetch_model.py "search terms" [--theme "mood/setting"]')
        sys.exit(1)
    out = fetch_model(query, theme=theme)
    if out is None:
        sys.exit(2)
