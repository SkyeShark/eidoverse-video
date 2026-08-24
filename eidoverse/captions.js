// captions.js — globalThis.makeCaptions: word-timed captions with active-word highlight on the overlay layer. Usage: AGENTS.md.
(function () {
    function normalizeWords(input) {
        const flat = [];
        for (const item of input) {
            if (Array.isArray(item.words)) flat.push(...item.words);
            else flat.push(item);
        }
        return flat.map((w) => ({
            text: (w.text ?? w.word ?? '').trim(),
            startMs: w.startMs ?? Math.round(w.start * 1000),
            endMs: w.endMs ?? Math.round(w.end * 1000),
        })).filter((w) => w.text.length > 0);
    }

    globalThis.makeCaptions = function makeCaptions({
        words = [],
        layer = null,
        fov = 50,
        style = {},
    } = {}) {
        const S = {
            font: 'bold 64px sans-serif',
            color: '#FFFFFF',
            highlightColor: '#FF9F1C',
            strokeColor: 'rgba(0,0,0,0.92)',
            strokeWidth: 9,
            background: 'rgba(0,0,0,0.40)',
            backgroundPad: 22,
            backgroundRadius: 16,
            y: -0.62,
            widthFrac: 0.86,
            maxWordsPerPage: 6,
            maxGapMs: 900,
            holdMs: 260,
            uppercase: false,
            px: 1536,
            ...style,
        };

        const pages = [];
        let cur = null;
        for (const w of normalizeWords(words)) {
            const gapBreak = cur && (w.startMs - cur.endMs) > S.maxGapMs;
            const fullBreak = cur && cur.words.length >= S.maxWordsPerPage;
            if (!cur || gapBreak || fullBreak) {
                cur = { words: [], startMs: w.startMs, endMs: w.endMs };
                pages.push(cur);
            }
            cur.words.push(w);
            cur.endMs = w.endMs;
            if (/[.!?]$/.test(w.text)) cur = null;
        }

        const H_FRAC = 0.16;
        const canvas = document.createElement('canvas');
        canvas.width = S.px;
        canvas.height = Math.round(S.px * H_FRAC);
        const ctx = canvas.getContext('2d');

        const tex = new THREE.CanvasTexture(canvas);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.generateMipmaps = false;
        tex.minFilter = THREE.LinearFilter;
        const mat = new THREE.MeshBasicNodeMaterial({
            map: tex, transparent: true, depthTest: false, opacity: 0,
        });

        const hud = layer ?? globalThis.makeOverlayLayer({ fov });
        const camFov = hud.camera?.fov ?? fov;
        const halfH = Math.tan(camFov * Math.PI / 360);
        const halfW = halfH * ((globalThis.WIDTH || 1280) / (globalThis.HEIGHT || 720));
        const planeW = halfW * 2 * S.widthFrac;
        const planeH = planeW * H_FRAC;
        const mesh = new THREE.Mesh(new THREE.PlaneGeometry(planeW, planeH), mat);
        mesh.renderOrder = 998;
        mesh.position.set(0, S.y * halfH, -1);
        hud.add(mesh);

        const roundedRect = (c, x, y, w, h, r) => {
            c.beginPath();
            c.moveTo(x + r, y);
            c.arcTo(x + w, y, x + w, y + h, r);
            c.arcTo(x + w, y + h, x, y + h, r);
            c.arcTo(x, y + h, x, y, r);
            c.arcTo(x, y, x + w, y, r);
            c.closePath();
        };

        const basePx = (() => {
            const m = S.font.match(/(\d+(?:\.\d+)?)px/);
            return m ? parseFloat(m[1]) : 64;
        })();
        const fontAt = (px) => S.font.replace(/\d+(?:\.\d+)?px/, `${px}px`);

        function draw(page, activeIdx) {
            const W = canvas.width, H = canvas.height;
            ctx.clearRect(0, 0, W, H);
            const texts = page.words.map((w) =>
                S.uppercase ? w.text.toUpperCase() : w.text);

            let px = basePx;
            let widths = [];
            let spaceW = 0;
            let total = Infinity;
            for (; px >= 18; px -= Math.max(1, Math.round(px * 0.08))) {
                ctx.font = fontAt(px);
                spaceW = ctx.measureText(' ').width;
                widths = texts.map((t) => ctx.measureText(t).width);
                total = widths.reduce((a, b) => a + b, 0) + spaceW * (texts.length - 1);
                if (total <= W * 0.92) break;
            }

            const lineH = px * 1.25;
            const yMid = H / 2;
            if (S.background) {
                ctx.fillStyle = S.background;
                roundedRect(ctx,
                    (W - total) / 2 - S.backgroundPad,
                    yMid - lineH / 2 - S.backgroundPad * 0.5,
                    total + S.backgroundPad * 2,
                    lineH + S.backgroundPad,
                    S.backgroundRadius);
                ctx.fill();
            }

            ctx.textBaseline = 'middle';
            let x = (W - total) / 2;
            texts.forEach((t, i) => {
                if (S.strokeWidth > 0) {
                    ctx.lineWidth = S.strokeWidth;
                    ctx.strokeStyle = S.strokeColor;
                    ctx.lineJoin = 'round';
                    ctx.strokeText(t, x, yMid);
                }
                ctx.fillStyle = i === activeIdx ? S.highlightColor : S.color;
                ctx.fillText(t, x, yMid);
                x += widths[i] + spaceW;
            });
        }

        let lastKey = '';
        function update(tSeconds) {
            const ms = tSeconds * 1000;
            let page = null;
            for (const p of pages) {
                if (ms >= p.startMs && ms <= p.endMs + S.holdMs) { page = p; break; }
            }
            if (!page) {
                if (lastKey !== 'off') { mat.opacity = 0; lastKey = 'off'; }
                return;
            }
            let active = -1;
            page.words.forEach((w, i) => {
                if (ms >= w.startMs && ms < w.endMs) active = i;
            });
            const key = pages.indexOf(page) + ':' + active;
            if (key === lastKey) return;
            lastKey = key;
            mat.opacity = 1;
            draw(page, active);
            tex.needsUpdate = true;
        }

        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('makeCaptions');
        return {
            update, mesh, pages, layer: hud, style: S,
            dispose() { mesh.removeFromParent(); mat.dispose(); tex.dispose(); },
        };
    };
})();
