(function() {
    'use strict';

    // ===================== SEEDED PRNG (Mulberry32) =====================
    function _rng(seed) {
        return function() {
            seed |= 0; seed = seed + 0x6D2B79F5 | 0;
            var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
    }

    // ===================== NOISE PRIMITIVES =====================
    function _hash(x, y) {
        var h = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
        return h - Math.floor(h);
    }

    function _noise2(x, y) {
        var ix = Math.floor(x), iy = Math.floor(y);
        var fx = x - ix, fy = y - iy;
        var sx = fx * fx * (3 - 2 * fx);
        var sy = fy * fy * (3 - 2 * fy);
        var a = _hash(ix, iy), b = _hash(ix + 1, iy);
        var c = _hash(ix, iy + 1), d = _hash(ix + 1, iy + 1);
        return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
    }

    function _fbm(x, y, octaves) {
        var v = 0, a = 0.5;
        for (var i = 0; i < (octaves || 6); i++) {
            v += a * _noise2(x, y);
            var nx = x * 1.6 + y * 1.2 + 1.7;
            var ny = -x * 1.2 + y * 1.6 + 9.2;
            x = nx; y = ny; a *= 0.5;
        }
        return v;
    }

    function _voronoi(x, y) {
        var ix = Math.floor(x), iy = Math.floor(y);
        var fx = x - ix, fy = y - iy;
        var d1 = 8, d2 = 8, cellId = 0;
        for (var j = -1; j <= 1; j++) {
            for (var i = -1; i <= 1; i++) {
                var px = _hash(ix + i, iy + j);
                var py = _hash(ix + i + 99, iy + j + 99);
                var dx = i + px - fx, dy = j + py - fy;
                var d = dx * dx + dy * dy;
                if (d < d1) { d2 = d1; d1 = d; cellId = _hash(ix + i + 37, iy + j + 37); }
                else if (d < d2) d2 = d;
            }
        }
        d1 = Math.sqrt(d1); d2 = Math.sqrt(d2);
        return { d1: d1, d2: d2, edge: d2 - d1, cell: cellId };
    }

    // Domain-warped fbm for organic variation
    function _warpedFbm(x, y, t) {
        var qx = _fbm(x, y, 4);
        var qy = _fbm(x + 5.2, y + 1.3, 4);
        return _fbm(x + 4 * qx + (t || 0), y + 4 * qy + (t || 0), 5);
    }

    // ===================== CANVAS HELPERS =====================
    function _makeCanvas(w, h) {
        var c = document.createElement('canvas');
        c.width = w; c.height = h;
        return c;
    }

    function _toTexture(canvas) {
        var tex = new THREE.CanvasTexture(canvas);
        tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
        tex.needsUpdate = true;
        return tex;
    }

    function _fillPixels(canvas, fn) {
        var ctx = canvas.getContext('2d');
        var w = canvas.width, h = canvas.height;
        var img = ctx.createImageData(w, h);
        var d = img.data;
        for (var y = 0; y < h; y++) {
            for (var x = 0; x < w; x++) {
                var idx = (y * w + x) * 4;
                var c = fn(x / w, y / h, x, y);
                d[idx]     = Math.min(255, Math.max(0, (c.r * 255) | 0));
                d[idx + 1] = Math.min(255, Math.max(0, (c.g * 255) | 0));
                d[idx + 2] = Math.min(255, Math.max(0, (c.b * 255) | 0));
                d[idx + 3] = 255;
            }
        }
        ctx.putImageData(img, 0, 0);
    }

    // Parse color: accepts 0xRRGGBB, '#rrggbb', or {r,g,b} (0-1)
    function _parseColor(c) {
        if (typeof c === 'object' && c.r !== undefined) return c;
        if (typeof c === 'string') c = parseInt(c.replace('#', ''), 16);
        return { r: ((c >> 16) & 0xff) / 255, g: ((c >> 8) & 0xff) / 255, b: (c & 0xff) / 255 };
    }

    // ===================== TEXTURE GENERATORS =====================
    var PM = {};

    /**
     * Directional scratch marks for roughness maps.
     * White = scratched (rougher/shinier depending on usage), black = clean.
     * opts: { density, depth, direction (radians, null=random), seed, texSize? }
     */
    PM.scratches = function(w, h, opts) {
        w = w || 512; h = h || 512; opts = opts || {};
        var density = opts.density != null ? opts.density : 0.3;
        var depth = opts.depth != null ? opts.depth : 0.5;
        var direction = opts.direction;
        var seed = opts.seed || 42;
        var rand = _rng(seed);

        var canvas = _makeCanvas(w, h);
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, w, h);

        var count = Math.floor(w * density * 2.5);
        for (var i = 0; i < count; i++) {
            var x = rand() * w, y = rand() * h;
            var angle = direction != null ? direction + (rand() - 0.5) * 0.4 : rand() * Math.PI;
            var len = 8 + rand() * 50;
            var bright = Math.floor(depth * (100 + rand() * 155));
            ctx.strokeStyle = 'rgb(' + bright + ',' + bright + ',' + bright + ')';
            ctx.lineWidth = 0.3 + rand() * 1.2;
            ctx.globalAlpha = 0.3 + rand() * 0.7;
            ctx.beginPath();
            ctx.moveTo(x - Math.cos(angle) * len / 2, y - Math.sin(angle) * len / 2);
            ctx.lineTo(x + Math.cos(angle) * len / 2, y + Math.sin(angle) * len / 2);
            ctx.stroke();
        }
        ctx.globalAlpha = 1;
        return _toTexture(canvas);
    };

    /**
     * Blotchy smudge/fingerprint marks for roughness maps.
     * White = smudged area, black = clean.
     * opts: { amount, scale, seed }
     */
    PM.smudges = function(w, h, opts) {
        w = w || 512; h = h || 512; opts = opts || {};
        var amount = opts.amount != null ? opts.amount : 0.3;
        var scale = opts.scale != null ? opts.scale : 1.0;
        var seed = opts.seed || 123;
        var rand = _rng(seed);

        var canvas = _makeCanvas(w, h);
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, w, h);

        var count = Math.floor(15 * amount * scale) + 3;
        for (var i = 0; i < count; i++) {
            var cx = rand() * w, cy = rand() * h;
            var radius = 20 + rand() * 80 * scale;
            var bright = Math.floor(128 + rand() * 127);
            var grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
            var alpha1 = 0.3 + rand() * 0.5;
            var alpha2 = 0.1 + rand() * 0.2;
            grad.addColorStop(0, 'rgba(' + bright + ',' + bright + ',' + bright + ',' + alpha1 + ')');
            grad.addColorStop(0.6, 'rgba(' + bright + ',' + bright + ',' + bright + ',' + alpha2 + ')');
            grad.addColorStop(1, 'rgba(0,0,0,0)');
            ctx.fillStyle = grad;
            ctx.fillRect(cx - radius, cy - radius, radius * 2, radius * 2);
        }
        return _toTexture(canvas);
    };

    /**
     * General-purpose fbm noise texture (grayscale).
     * opts: { scale, octaves, contrast, offset, warp (bool — domain warping) }
     */
    PM.noise = function(w, h, opts) {
        w = w || 512; h = h || 512; opts = opts || {};
        var scale = opts.scale != null ? opts.scale : 5;
        var octaves = opts.octaves || 6;
        var contrast = opts.contrast != null ? opts.contrast : 1;
        var offset = opts.offset || 0;
        var warp = opts.warp || false;
        var canvas = _makeCanvas(w, h);

        _fillPixels(canvas, function(u, v) {
            var n = warp
                ? _warpedFbm(u * scale + offset, v * scale + offset, 0)
                : _fbm(u * scale + offset, v * scale + offset, octaves);
            n = Math.max(0, Math.min(1, (n - 0.5) * contrast + 0.5));
            return { r: n, g: n, b: n };
        });
        return _toTexture(canvas);
    };

    /**
     * Voronoi cellular pattern (grayscale).
     * opts: { scale, mode ('cells'|'edges'|'distance'), edgeWidth }
     */
    PM.voronoi = function(w, h, opts) {
        w = w || 512; h = h || 512; opts = opts || {};
        var scale = opts.scale != null ? opts.scale : 8;
        var mode = opts.mode || 'cells';
        var edgeWidth = opts.edgeWidth != null ? opts.edgeWidth : 0.08;
        var canvas = _makeCanvas(w, h);

        _fillPixels(canvas, function(u, v) {
            var vor = _voronoi(u * scale, v * scale);
            var val;
            if (mode === 'edges') val = vor.edge < edgeWidth ? 1 : 0;
            else if (mode === 'distance') val = Math.min(1, vor.d1 * 2);
            else val = vor.cell;
            return { r: val, g: val, b: val };
        });
        return _toTexture(canvas);
    };

    /**
     * Color patches — cow spots, giraffe polygons, camo, frog splotches.
     * Returns a COLOR texture.
     * opts: { baseColor, patchColor, scale, threshold, softness, shape ('blob'|'voronoi'|'spots') }
     */
    PM.patches = function(w, h, opts) {
        w = w || 512; h = h || 512; opts = opts || {};
        var base = _parseColor(opts.baseColor || 0xfff0e0);
        var patch = _parseColor(opts.patchColor || 0x1a1a1a);
        var scale = opts.scale != null ? opts.scale : 4;
        var threshold = opts.threshold != null ? opts.threshold : 0.55;
        var softness = opts.softness != null ? opts.softness : 0.05;
        var shape = opts.shape || 'blob';
        var canvas = _makeCanvas(w, h);

        _fillPixels(canvas, function(u, v) {
            var t;
            if (shape === 'voronoi') {
                var vor = _voronoi(u * scale, v * scale);
                t = vor.cell > threshold ? 1 : 0;
                if (softness > 0) t *= Math.min(1, vor.edge / softness);
            } else if (shape === 'spots') {
                var vor2 = _voronoi(u * scale, v * scale);
                t = (vor2.cell > threshold && vor2.d1 < 0.3) ? 1 : 0;
            } else {
                var n = _fbm(u * scale, v * scale, 4);
                t = n > threshold ? 0 : 1;
                if (softness > 0) {
                    var edge = Math.abs(n - threshold);
                    if (edge < softness) t *= edge / softness;
                }
            }
            return {
                r: base.r + (patch.r - base.r) * t,
                g: base.g + (patch.g - base.g) * t,
                b: base.b + (patch.b - base.b) * t,
            };
        });
        var tex = _toTexture(canvas);
        tex.colorSpace = THREE.SRGBColorSpace;
        return tex;
    };

    /**
     * Skin pore normal map — small perturbations for organic surfaces.
     * Returns normal map (flat = rgb(128,128,255)).
     * opts: { density, depth, seed }
     */
    PM.pores = function(w, h, opts) {
        w = w || 512; h = h || 512; opts = opts || {};
        var density = opts.density != null ? opts.density : 0.5;
        var depth = opts.depth != null ? opts.depth : 0.3;
        var seed = opts.seed || 77;
        var rand = _rng(seed);

        var canvas = _makeCanvas(w, h);
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = 'rgb(128,128,255)';
        ctx.fillRect(0, 0, w, h);

        var count = Math.floor(w * h * density / 80);
        for (var i = 0; i < count; i++) {
            var px = rand() * w, py = rand() * h;
            var r = 0.8 + rand() * 2.5;
            var nx = (rand() - 0.5) * depth;
            var ny = (rand() - 0.5) * depth;
            var cr = Math.floor(128 + nx * 127);
            var cg = Math.floor(128 + ny * 127);
            ctx.fillStyle = 'rgb(' + cr + ',' + cg + ',220)';
            ctx.globalAlpha = 0.3 + rand() * 0.5;
            ctx.beginPath();
            ctx.arc(px, py, r, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.globalAlpha = 1;
        return _toTexture(canvas);
    };

    /**
     * Fabric weave pattern — crosshatch for roughness.
     * opts: { density (threads), variation, seed }
     */
    PM.weave = function(w, h, opts) {
        w = w || 512; h = h || 512; opts = opts || {};
        var density = opts.density || 20;
        var variation = opts.variation != null ? opts.variation : 0.3;
        var canvas = _makeCanvas(w, h);

        _fillPixels(canvas, function(u, v) {
            var t1 = Math.sin(u * density * Math.PI * 2) * 0.5 + 0.5;
            var t2 = Math.sin(v * density * Math.PI * 2) * 0.5 + 0.5;
            var cell = (Math.floor(u * density) + Math.floor(v * density)) % 2;
            var val = cell ? Math.max(t1, t2) : Math.min(t1, t2);
            val += (_noise2(u * 50, v * 50) - 0.5) * variation;
            val = Math.max(0, Math.min(1, val));
            return { r: val, g: val, b: val };
        });
        return _toTexture(canvas);
    };

    /**
     * Directional grain — wood, leather, brushed metal.
     * opts: { scale, stretch (elongation factor), contrast }
     */
    PM.grain = function(w, h, opts) {
        w = w || 512; h = h || 512; opts = opts || {};
        var scale = opts.scale || 4;
        var stretch = opts.stretch || 8;
        var contrast = opts.contrast != null ? opts.contrast : 1.2;
        var canvas = _makeCanvas(w, h);

        _fillPixels(canvas, function(u, v) {
            var n = _fbm(u * scale, v * scale * stretch, 5);
            n = Math.max(0, Math.min(1, (n - 0.5) * contrast + 0.5));
            return { r: n, g: n, b: n };
        });
        return _toTexture(canvas);
    };

    /**
     * Generate a normal map from any grayscale heightmap texture.
     * opts: { strength }
     */
    PM.heightToNormal = function(heightTex, opts) {
        opts = opts || {};
        var strength = opts.strength != null ? opts.strength : 1.0;
        var src = heightTex.image;
        var w = src.width, h = src.height;

        // Read height pixels
        var tmpCanvas = _makeCanvas(w, h);
        var tmpCtx = tmpCanvas.getContext('2d');
        tmpCtx.drawImage(src, 0, 0);
        var srcData = tmpCtx.getImageData(0, 0, w, h).data;

        function getHeight(x, y) {
            x = ((x % w) + w) % w;
            y = ((y % h) + h) % h;
            return srcData[(y * w + x) * 4] / 255;
        }

        var canvas = _makeCanvas(w, h);
        _fillPixels(canvas, function(u, v, px, py) {
            var hL = getHeight(px - 1, py);
            var hR = getHeight(px + 1, py);
            var hU = getHeight(px, py - 1);
            var hD = getHeight(px, py + 1);
            var nx = (hL - hR) * strength;
            var ny = (hU - hD) * strength;
            return { r: nx * 0.5 + 0.5, g: ny * 0.5 + 0.5, b: 1.0 };
        });
        return _toTexture(canvas);
    };

    // ===================== COMPOSITING =====================

    /**
     * Composite two textures together.
     * Modes: 'multiply', 'add', 'screen', 'overlay', 'max', 'min'
     * opts: { strength (0-1, blend amount of the operation) }
     */
    PM.composite = function(texA, texB, mode, opts) {
        mode = mode || 'multiply';
        var strength = (opts && opts.strength != null) ? opts.strength : 1.0;
        var srcA = texA.image, srcB = texB.image;
        var w = srcA.width || 512, h = srcA.height || 512;

        var cA = _makeCanvas(w, h); var ctxA = cA.getContext('2d');
        ctxA.drawImage(srcA, 0, 0, w, h);
        var dA = ctxA.getImageData(0, 0, w, h).data;

        var cB = _makeCanvas(w, h); var ctxB = cB.getContext('2d');
        ctxB.drawImage(srcB, 0, 0, w, h);
        var dB = ctxB.getImageData(0, 0, w, h).data;

        var canvas = _makeCanvas(w, h);
        var ctx = canvas.getContext('2d');
        var img = ctx.createImageData(w, h);
        var d = img.data;

        for (var idx = 0; idx < d.length; idx += 4) {
            for (var c = 0; c < 3; c++) {
                var a = dA[idx + c] / 255, b = dB[idx + c] / 255;
                var result;
                switch (mode) {
                    case 'multiply': result = a * b; break;
                    case 'add': result = Math.min(1, a + b); break;
                    case 'screen': result = 1 - (1 - a) * (1 - b); break;
                    case 'overlay': result = a < 0.5 ? 2 * a * b : 1 - 2 * (1 - a) * (1 - b); break;
                    case 'max': result = Math.max(a, b); break;
                    case 'min': result = Math.min(a, b); break;
                    default: result = a * b;
                }
                d[idx + c] = ((a * (1 - strength) + result * strength) * 255) | 0;
            }
            d[idx + 3] = 255;
        }
        ctx.putImageData(img, 0, 0);
        return _toTexture(canvas);
    };

    // ===================== MATERIAL FACTORIES =====================

    /**
     * Painted metal — car paint, appliances, painted panels.
     * MeshPhysicalMaterial with clearcoat.
     * opts: { color, metalness, roughness, clearcoat, clearcoatRoughness,
     *         scratches: {density, depth, direction, seed} | true,
     *         smudges: {amount, scale, seed} | true,
     *         texSize }
     */
    PM.createPaintedMetal = function(opts) {
        opts = opts || {};
        var texSize = opts.texSize || 512;
        var matOpts = {
            color: opts.color || 0x1a3a6a,
            metalness: opts.metalness != null ? opts.metalness : 0.4,
            roughness: opts.roughness != null ? opts.roughness : 0.3,
            clearcoat: opts.clearcoat != null ? opts.clearcoat : 0.8,
            clearcoatRoughness: opts.clearcoatRoughness != null ? opts.clearcoatRoughness : 0.1,
        };

        if (opts.scratches) {
            var sOpts = typeof opts.scratches === 'object' ? opts.scratches : {};
            var scratchTex = PM.scratches(texSize, texSize, sOpts);
            // Scratches modulate clearcoat roughness (scratches = rougher clearcoat)
            matOpts.clearcoatRoughnessMap = scratchTex;
        }

        if (opts.smudges) {
            var smOpts = typeof opts.smudges === 'object' ? opts.smudges : {};
            var smudgeTex = PM.smudges(texSize, texSize, smOpts);
            if (matOpts.clearcoatRoughnessMap) {
                matOpts.clearcoatRoughnessMap = PM.composite(
                    matOpts.clearcoatRoughnessMap, smudgeTex, 'add', { strength: 0.4 }
                );
            } else {
                matOpts.clearcoatRoughnessMap = smudgeTex;
            }
        }

        return new THREE.MeshPhysicalMaterial(matOpts);
    };

    /**
     * Rubber — tires, boots, gaskets, grips.
     * opts: { color, grainScale, bumpStrength, texSize }
     */
    PM.createRubber = function(opts) {
        opts = opts || {};
        var texSize = opts.texSize || 512;
        var noiseTex = PM.noise(texSize, texSize, {
            scale: opts.grainScale || 20, octaves: 4, contrast: 0.5,
        });
        var normalTex = PM.heightToNormal(noiseTex, { strength: opts.bumpStrength || 0.5 });
        return new THREE.MeshStandardMaterial({
            color: opts.color || 0x222222,
            roughness: 0.95,
            metalness: 0.0,
            roughnessMap: noiseTex,
            normalMap: normalTex,
            normalScale: new THREE.Vector2(0.3, 0.3),
        });
    };

    /**
     * Organic skin — humans, creatures, aliens.
     * MeshPhysicalMaterial with subsurface approximation.
     * opts: { color, roughness, subsurface, thickness,
     *         variation: { scale } | false,
     *         pores: { density, depth } | false,
     *         patches: { baseColor, patchColor, scale, threshold, softness, shape },
     *         texSize }
     */
    PM.createSkin = function(opts) {
        opts = opts || {};
        var texSize = opts.texSize || 512;
        var baseColor = opts.color || 0xcc8866;
        var matOpts = {
            color: baseColor,
            roughness: opts.roughness != null ? opts.roughness : 0.6,
            metalness: 0.0,
            transmission: opts.subsurface != null ? opts.subsurface : 0.15,
            thickness: opts.thickness != null ? opts.thickness : 0.8,
            ior: 1.3,
        };

        // Color variation (veins, blotchiness)
        if (opts.variation !== false) {
            var varScale = (opts.variation && opts.variation.scale) || 3;
            var canvas = _makeCanvas(texSize, texSize);
            var c = _parseColor(baseColor);
            _fillPixels(canvas, function(u, v) {
                var n = _fbm(u * varScale, v * varScale, 4);
                var darken = 0.85 + n * 0.3;
                return { r: c.r * darken, g: c.g * darken * 0.95, b: c.b * darken * 0.9 };
            });
            matOpts.map = _toTexture(canvas);
            matOpts.map.colorSpace = THREE.SRGBColorSpace;
        }

        // Override with explicit patches (cow spots, etc.)
        if (opts.patches) {
            var pOpts = Object.assign({}, opts.patches);
            if (!pOpts.baseColor) pOpts.baseColor = baseColor;
            matOpts.map = PM.patches(texSize, texSize, pOpts);
        }

        // Pore normal map
        if (opts.pores !== false) {
            var poreOpts = typeof opts.pores === 'object' ? opts.pores : {};
            matOpts.normalMap = PM.pores(texSize, texSize, poreOpts);
            matOpts.normalScale = new THREE.Vector2(
                opts.poreStrength || 0.2, opts.poreStrength || 0.2
            );
        }

        return new THREE.MeshPhysicalMaterial(matOpts);
    };

    /**
     * Scales — reptile, fish, dragon, sea monster.
     * Voronoi-based with raised cell centers and colored variation.
     * opts: { color, cellSize, roughness, metalness, clearcoat, bumpStrength, texSize }
     */
    PM.createScaly = function(opts) {
        opts = opts || {};
        var texSize = opts.texSize || 512;
        var scale = opts.cellSize || 12;
        var baseColor = _parseColor(opts.color || 0x2a5a3a);

        // Color map — per-cell shade variation + dark edges
        var colorCanvas = _makeCanvas(texSize, texSize);
        _fillPixels(colorCanvas, function(u, v) {
            var vor = _voronoi(u * scale, v * scale);
            var shade = 0.7 + vor.cell * 0.6;
            var edgeDarken = Math.min(1, vor.edge / 0.1);
            var d = shade * edgeDarken;
            return { r: baseColor.r * d, g: baseColor.g * d, b: baseColor.b * d };
        });

        // Normal map — raised centers, dipped edges
        var normalCanvas = _makeCanvas(texSize, texSize);
        var eps = 1.0 / texSize;
        _fillPixels(normalCanvas, function(u, v) {
            var h0 = _voronoi(u * scale, v * scale).edge;
            var hR = _voronoi((u + eps) * scale, v * scale).edge;
            var hU = _voronoi(u * scale, (v + eps) * scale).edge;
            var bumpStr = opts.bumpStrength || 2;
            var nx = (h0 - hR) * bumpStr;
            var ny = (h0 - hU) * bumpStr;
            return { r: 0.5 + nx * 0.5, g: 0.5 + ny * 0.5, b: 1 };
        });

        var colorTex = _toTexture(colorCanvas);
        colorTex.colorSpace = THREE.SRGBColorSpace;

        return new THREE.MeshPhysicalMaterial({
            map: colorTex,
            normalMap: _toTexture(normalCanvas),
            normalScale: new THREE.Vector2(1, 1),
            roughness: opts.roughness != null ? opts.roughness : 0.4,
            metalness: opts.metalness != null ? opts.metalness : 0.1,
            clearcoat: opts.clearcoat != null ? opts.clearcoat : 0.3,
            clearcoatRoughness: 0.4,
        });
    };

    /**
     * Fabric — cloth, clothing, upholstery.
     * opts: { color, threadDensity, variation,
     *         diffuseMap, normalMap, roughnessMap (pre-loaded Poly Haven textures to layer over),
     *         wear: { amount, seed },
     *         texSize }
     */
    PM.createFabric = function(opts) {
        opts = opts || {};
        var texSize = opts.texSize || 512;
        var weaveTex = PM.weave(texSize, texSize, {
            density: opts.threadDensity || 30,
            variation: opts.variation != null ? opts.variation : 0.2,
        });

        var matOpts = {
            color: opts.color || 0x4a4a6a,
            roughness: 1.0,
            metalness: 0.0,
            roughnessMap: weaveTex,
        };

        // Layer over Poly Haven textures if provided
        if (opts.diffuseMap) {
            matOpts.map = opts.diffuseMap;
            matOpts.map.colorSpace = THREE.SRGBColorSpace;
        }
        if (opts.normalMap) matOpts.normalMap = opts.normalMap;
        if (opts.roughnessMap) {
            matOpts.roughnessMap = PM.composite(opts.roughnessMap, weaveTex, 'multiply');
        }

        // Wear marks
        if (opts.wear) {
            var wearTex = PM.smudges(texSize, texSize, {
                amount: opts.wear.amount || 0.5,
                seed: opts.wear.seed || 99,
            });
            matOpts.roughnessMap = PM.composite(
                matOpts.roughnessMap || weaveTex, wearTex, 'add', { strength: 0.2 }
            );
        }

        return new THREE.MeshStandardMaterial(matOpts);
    };

    /**
     * Worn/aged metal — chipped paint revealing metal underneath.
     * Generates coordinated color + roughness + metalness maps.
     * opts: { paintColor, metalColor, wearAmount (0-1), wearScale, texSize }
     */
    PM.createWornMetal = function(opts) {
        opts = opts || {};
        var texSize = opts.texSize || 512;
        var paintC = _parseColor(opts.paintColor || 0x3a5a3a);
        var metalC = _parseColor(opts.metalColor || 0x888888);
        var wearAmt = opts.wearAmount != null ? opts.wearAmount : 0.4;
        var wearScale = opts.wearScale || 4;

        var colorCanvas = _makeCanvas(texSize, texSize);
        var roughCanvas = _makeCanvas(texSize, texSize);
        var metalCanvas = _makeCanvas(texSize, texSize);

        // Pre-compute noise field once (shared across all three maps)
        var noiseCache = [];
        for (var y = 0; y < texSize; y++) {
            noiseCache[y] = [];
            for (var x = 0; x < texSize; x++) {
                noiseCache[y][x] = _fbm(x / texSize * wearScale, y / texSize * wearScale, 5);
            }
        }

        _fillPixels(colorCanvas, function(u, v, px, py) {
            var worn = noiseCache[py][px] > (1 - wearAmt) ? 1 : 0;
            return {
                r: paintC.r * (1 - worn) + metalC.r * worn,
                g: paintC.g * (1 - worn) + metalC.g * worn,
                b: paintC.b * (1 - worn) + metalC.b * worn,
            };
        });
        _fillPixels(roughCanvas, function(u, v, px, py) {
            var worn = noiseCache[py][px] > (1 - wearAmt) ? 1 : 0;
            var r = worn ? 0.6 : 0.3;
            return { r: r, g: r, b: r };
        });
        _fillPixels(metalCanvas, function(u, v, px, py) {
            var worn = noiseCache[py][px] > (1 - wearAmt) ? 1 : 0;
            var m = worn ? 0.9 : 0.3;
            return { r: m, g: m, b: m };
        });

        var cTex = _toTexture(colorCanvas);
        cTex.colorSpace = THREE.SRGBColorSpace;

        return new THREE.MeshStandardMaterial({
            map: cTex,
            roughnessMap: _toTexture(roughCanvas),
            roughness: 1.0,
            metalnessMap: _toTexture(metalCanvas),
            metalness: 1.0,
        });
    };

    // ===================== EXPOSE =====================
    window.ProceduralMaterials = PM;

    // ─── Agent-discoverable help ───
    PM.help = function () {
        var lines = [
            '────────── ProceduralMaterials API reference ──────────',
            '',
            'Canvas-based texture generators + PBR material factories.',
            'Use when Poly Haven (fetch_texture.py) has no good match — most often plastic.',
            '',
            '── Texture generators (return THREE.CanvasTexture, default LinearFilter) ──',
            '  scratches(w, h, {density, depth, direction, seed})       grayscale heightmap',
            '  smudges(w, h, {amount, scale})                          grayscale roughness',
            '  noise(w, h, {scale, octaves, contrast, warp})           FBM grayscale',
            '  voronoi(w, h, {scale, mode, edgeWidth})                 cellular pattern',
            '  patches(w, h, {baseColor, patchColor, scale, threshold, shape})  cow/giraffe color',
            '  pores(w, h, {density, depth})                           skin normal map',
            '  weave(w, h, {density, variation})                       fabric roughness',
            '  grain(w, h, {scale, stretch, contrast})                 wood/leather grain',
            '  heightToNormal(grayscaleTex, {strength})                height → normal map',
            '  composite(a, b, mode, {strength})                       blend two textures',
            '                          mode = multiply | add | screen | overlay | max | min',
            '',
            '── PBR material factories (return MeshStandardMaterial / MeshPhysicalMaterial) ──',
            '  createPaintedMetal({color, scratches, smudges, clearcoat})    car paint, server racks',
            '  createRubber({color, grainScale, bumpStrength})               tires, gaskets',
            '  createSkin({color, subsurface, pores, variation, patches})    organic / animals',
            '  createScaly({color, cellSize, clearcoat, bumpStrength})       reptile, fish',
            '  createFabric({color, threadDensity, diffuseMap?, wear})       clothing',
            '  createWornMetal({paintColor, metalColor, wearAmount, wearScale}) chipped paint',
            '',
            '── Recipe: 90s computer plastic (no Poly Haven texture exists for this) ──',
            "  const PM = window.ProceduralMaterials;",
            "  const noiseTx   = PM.noise(512, 512, { scale: 12, octaves: 5, contrast: 0.7 });",
            "  const scratchTx = PM.scratches(512, 512, { density: 0.5, depth: 0.6 });",
            "  const heightTx  = PM.composite(noiseTx, scratchTx, 'add', { strength: 0.5 });",
            "  const normalTx  = PM.heightToNormal(heightTx, { strength: 1.4 });",
            "  const roughTx   = PM.composite(PM.smudges(512, 512, {amount:0.5}), noiseTx, 'add');",
            "  [normalTx, roughTx].forEach(t => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3,3); });",
            "  const plastic = new THREE.MeshStandardMaterial({",
            "    color: 0xc8c4b8, roughness: 0.8, metalness: 0.05,",
            "    normalMap: normalTx, roughnessMap: roughTx,",
            "    normalScale: new THREE.Vector2(0.7, 0.7),",
            "  });",
            '',
            '── Common gotchas ──',
            '  • Always set wrapS/wrapT to RepeatWrapping and .repeat.set(N, N) before applying',
            '    to large surfaces, or one tile spreads as a giant blur across the mesh.',
            '  • createPaintedMetal/createSkin/etc. return materials where roughness=1 and the',
            '    actual roughness comes from the map. Setting material.roughness=0.5 darkens',
            '    the entire roughness map by half — usually not what you want.',
            '  • material.color is multiplicative on top of the diffuse map. To shift the hue',
            '    of a baked-in colour, you mostly only succeed in darkening it.',
            '  • Texture generation is synchronous and CPU-bound — generate once in setup(),',
            '    not per frame.',
            '',
            'Source: /opt/render3d/procedural_materials.js',
        ];
        var msg = lines.join('\n');
        console.log(msg);
        return msg;
    };

    console.log('[procedural_materials] Loaded: scratches, smudges, noise, voronoi, patches, pores, weave, grain, heightToNormal, composite, createPaintedMetal, createRubber, createSkin, createScaly, createFabric, createWornMetal');
    console.log('[procedural_materials] Call ProceduralMaterials.help() for API reference + recipes.');
})();
