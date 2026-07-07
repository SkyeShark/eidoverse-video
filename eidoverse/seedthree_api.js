// seedthree_api.js — globalThis.makeSeedTree: procedural trees & plants via
// SeedThree's HEADLESS AGENT API (github.com/SkyeShark/SeedThree, MIT —
// src/api/seedthree.js). A thin adapter over the exact code the SeedThree app
// runs, so a tree grown here is IDENTICAL to one grown in its UI, and presets
// round-trip with the app's Save/Load panel.
//
//   const oak = await globalThis.makeSeedTree({ species: 'whiteOak', seed: 1737, scene, sunLight: sun });
//   console.log(oak.stats.summary);   // { heightMeters, lod0Triangles, ... }
//
// THE SEED IS THE DESIGN: iterate `seed` and read `stats` before touching any
// knob. Discover everything else progressively, exactly like the app's panels:
//   await makeSeedTree.describe()                       // species menu
//   await makeSeedTree.describe('joshuaTree')           // one species' brief + folder index
//   await makeSeedTree.describe('joshuaTree', 'shape')  // open ONE folder of dials
//
// opts: species, seed, controls (dial overrides), level ('LOD0'|...), scene,
//       sunLight, position [x,y,z], textured (default true — the app's real PBR
//       materials; false → headless generate() over placeholders, no GPU needed)
// returns { object, stats, preset, api }
//
// Passthroughs (all async): makeSeedTree.describe / listSpecies / getSchema /
// defaultControls / setWind({strength,speed}) / toPreset / fromPreset / raw()
// (→ the whole module namespace).
//
// SOURCE RESOLUTION (no install step needed): a local checkout wins —
// globalThis.SEEDTHREE_DIR, the SEEDTHREE_DIR env var, a sibling ../SeedThree,
// or ./SeedThree — otherwise the API is imported STRAIGHT FROM GITHUB (deno
// caches remote modules; SEEDTHREE_REF pins a version). Textured materials
// need the checkout's assets/; without one, textured requests degrade to the
// placeholder build with a warning. Containers: clone the checkout —
//   git clone --depth 1 https://github.com/SkyeShark/SeedThree
//
// VERIFIED GOTCHAS (from the API's own eidoverse integration notes):
//   · set `globalThis._noAutoFixPlacement = true` in setup() — the clipping
//     auto-fix dismembers intentionally-overlapping tree geometry (this bridge
//     also marks objects allowIntersect as belt-and-braces)
//   · trees sway by default (windStrength 0.5) — makeSeedTree.setWind() tunes
//   · judge shadowed trees from frame ≥2 (shadow frustum settles a frame late)
(function () {
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[seedthree_api] THREE global not present — skipping load'); return; }

    const REMOTE_REPO = 'SkyeShark/SeedThree';
    let _mod = null, _dir = null;

    const _ref = () => {
        if (globalThis.SEEDTHREE_REF) return globalThis.SEEDTHREE_REF;
        try { const e = Deno.env.get('SEEDTHREE_REF'); if (e) return e; } catch (e) { }
        return 'main';
    };
    const _findDir = () => {
        if (globalThis.SEEDTHREE_DIR) return globalThis.SEEDTHREE_DIR;
        try { const e = Deno.env.get('SEEDTHREE_DIR'); if (e) return e; } catch (e) { }
        for (const cand of [Deno.cwd() + '/../SeedThree', Deno.cwd() + '/SeedThree']) {
            try { Deno.statSync(cand + '/src/api/seedthree.js'); return cand; } catch (e) { }
        }
        return null;
    };
    const _load = async () => {
        if (_mod) return _mod;
        const dir = _findDir();
        let url;
        if (dir) {
            _dir = String(dir).replace(/[\\/]+$/, '');
            url = 'file:///' + _dir.replace(/\\/g, '/').replace(/^\/+/, '') + '/src/api/seedthree.js';
            console.log('[seedthree_api] using local SeedThree at', _dir);
        } else {
            url = `https://raw.githubusercontent.com/${REMOTE_REPO}/${_ref()}/src/api/seedthree.js`;
            console.log('[seedthree_api] no local checkout — importing from GitHub (geometry tier; clone for textured materials)');
        }
        _mod = await import(url);
        return _mod;
    };

    globalThis.makeSeedTree = async function makeSeedTree(opts) {
        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('makeSeedTree');
        opts = opts || {};
        const api = await _load();
        const { species = 'whiteOak', seed = 1, controls, level = 'LOD0', scene, sunLight, position, placeholders } = opts;
        let textured = opts.textured !== false;
        if (textured && !_dir) { console.warn('[seedthree_api] textured build needs a local checkout (assets/) — degrading to placeholder geometry'); textured = false; }
        let object, out;
        if (textured) {
            const loadTexture = async (path, o) => globalThis.loadImageTexture(await Deno.readFile(path), o || {});
            out = await api.createTree({ species, seed, controls, level, sunLight, loadTexture, assetsDir: _dir + '/assets' });
            object = out.object;
        } else {
            out = api.generate({ species, seed, controls, placeholders });
            object = out.group;
        }
        object.userData.allowIntersect = true;   // trees are intentionally-overlapping geometry
        if (position) object.position.set(position[0], position[1], position[2]);
        if (scene) scene.add(object);
        if (!globalThis._noAutoFixPlacement) console.warn('[seedthree_api] set globalThis._noAutoFixPlacement = true in setup() — the placement auto-fix dismembers trees');
        return { object, stats: out.stats, preset: out.preset, api };
    };
    for (const k of ['describe', 'listSpecies', 'getSchema', 'defaultControls', 'setWind', 'toPreset', 'fromPreset', 'skeleton']) {
        globalThis.makeSeedTree[k] = async (...a) => (await _load())[k](...a);
    }
    globalThis.makeSeedTree.raw = () => _load();

    console.log('[seedthree_api] makeSeedTree ready — SeedThree headless agent API (seed-first: iterate `seed`, read stats; describe() for the dial folders)');
})();
