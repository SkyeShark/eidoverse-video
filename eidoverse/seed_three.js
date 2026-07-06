// seed_three.js — globalThis.makeTree: REAL procedural trees & plants via
// SeedThree (github.com/SkyeShark/SeedThree, MIT) — Weber-Penn broadleaves
// and conifers plus L-system desert succulents. Ten species with dialed
// real morphology, textured bark + translucent leaf cards (SSS), LOD
// levels, and TSL wind (time-driven — zero per-frame CPU).
//
//   const oak = await globalThis.makeTree({ species: 'whiteOak', seed: 7 });
//   oak.group.position.set(4, 0, -2); scene.add(oak.group);
//
//   species: whiteOak | redMaple | tulipPoplar | sweetgum | americanBeech
//            | pine | loblolly | douglasFir | joshuaTree | saguaro
//   opts:    seed, position, scale, params (species param overrides),
//            lod ({ meshQuality, lod1Dist, ... } — defaults fine for video),
//            windStrength (0..1, GLOBAL across all trees), windSpeed
//
// SOURCE RESOLUTION (no install step needed): a local checkout wins —
// globalThis.SEEDTHREE_DIR, the SEEDTHREE_DIR env var, a sibling
// ../SeedThree, or ./SeedThree — otherwise the generator is imported
// STRAIGHT FROM GITHUB (deno caches remote modules) and textures are
// fetched once into .cache/seedthree/. Pin SEEDTHREE_REF to lock a
// version. SeedThree and the engine share ONE three instance via the
// deno.json import map — never import three another way.
(function () {
    const THREE = globalThis.THREE;
    if (!THREE) { console.warn('[seed_three] THREE global not present — skipping load'); return; }

    let _mods = null, _dir = null, _remoteBase = null;
    const _assetCache = new Map();
    const REMOTE_REPO = 'SkyeShark/SeedThree';

    const _ref = () => {
        if (globalThis.SEEDTHREE_REF) return globalThis.SEEDTHREE_REF;
        try { const e = Deno.env.get('SEEDTHREE_REF'); if (e) return e; } catch (e) {}
        return 'main';
    };
    const _findDir = () => {
        if (globalThis.SEEDTHREE_DIR) return globalThis.SEEDTHREE_DIR;
        try { const e = Deno.env.get('SEEDTHREE_DIR'); if (e) return e; } catch (e) {}
        for (const cand of [Deno.cwd() + '/../SeedThree', Deno.cwd() + '/SeedThree']) {
            try { Deno.statSync(cand + '/src/core/tree.js'); return cand; } catch (e) {}
        }
        return null;
    };

    const _load = async () => {
        if (_mods) return _mods;
        const dir = _findDir();
        let base;
        if (dir) {
            _dir = String(dir).replace(/[\\/]+$/, '');
            base = 'file:///' + _dir.replace(/\\/g, '/').replace(/^\/+/, '') + '/src/';
            console.log('[seed_three] using local SeedThree at', _dir);
        } else {
            // no checkout: import the generator straight from GitHub (deno
            // caches remote modules; textures are fetched + disk-cached)
            _remoteBase = `https://raw.githubusercontent.com/${REMOTE_REPO}/${_ref()}/`;
            base = _remoteBase + 'src/';
            console.log('[seed_three] no local checkout — importing SeedThree from', _remoteBase);
        }
        const [tree, species, leafCards, yucca, spines, wind] = await Promise.all([
            import(base + 'core/tree.js'),
            import(base + 'species/index.js'),
            import(base + 'core/leaf-cards.js'),
            import(base + 'core/yucca-leaves.js'),
            import(base + 'core/cactus-spines.js'),
            import(base + 'core/wind.js'),
        ]);
        _mods = { tree, species, leafCards, yucca, spines, wind };
        console.log('[seed_three] SeedThree loaded from', _dir, '— species:', Object.keys(species.SPECIES).join(', '));
        return _mods;
    };

    // three's TextureLoader hangs on this deno+wgpu stack — get the bytes
    // (local file, or GitHub fetch cached to .cache/seedthree/) and decode
    // through the engine's loadImageTexture path instead
    const _bytes = async (rel) => {
        if (_dir) return await Deno.readFile(_dir + '/' + rel);
        const cache = Deno.cwd() + '/.cache/seedthree/' + _ref() + '/' + rel;
        try { return await Deno.readFile(cache); } catch (e) {}
        const res = await fetch(_remoteBase + rel);
        if (!res.ok) throw new Error('fetch ' + rel + ': ' + res.status);
        const bytes = new Uint8Array(await res.arrayBuffer());
        try {
            await Deno.mkdir(cache.slice(0, cache.lastIndexOf('/')), { recursive: true });
            await Deno.writeFile(cache, bytes);
        } catch (e) {}
        return bytes;
    };
    const _tex = async (sub, name, srgb) => {
        if (!name) return null;
        try {
            const bytes = await _bytes('assets/' + sub + '/' + name);
            const t = await globalThis.loadImageTexture(bytes, { srgb });
            t.wrapS = t.wrapT = THREE.RepeatWrapping;
            t.anisotropy = 8;
            return t;
        } catch (e) { return null; }
    };

    // port of the app's loadSpeciesAssets (SeedThree src/main.js, MIT) onto
    // the engine's texture path — same fields, same derived-map naming
    const _assets = async (M, sp) => {
        if (_assetCache.has(sp.name)) return _assetCache.get(sp.name);
        const base = sp.bark.replace('_albedo.png', '');
        const leafBase = sp.leaf.replace(/(_albedo)?\.png$/, '');
        const [barkTexture, barkNormal, barkRoughness, leafTexture, leafTranslucency, leafNormal, leafRoughness, leafDryTexture, leafDryestTexture] = await Promise.all([
            _tex('bark', sp.bark, true),
            _tex('bark', base + '_normal.png', false),
            _tex('bark', base + '_roughness.png', false),
            _tex('leaves', sp.leaf, true),
            _tex('leaves', leafBase + '_translucency.png', false),
            _tex('leaves', leafBase + '_normal.png', false),
            _tex('leaves', leafBase + '_roughness.png', false),
            _tex('leaves', leafBase + '_dry_albedo.png', true),
            _tex('leaves', leafBase + '_dryest_albedo.png', true),
        ]);
        const assets = { barkTexture, barkNormal, barkRoughness, leafTexture, leafTranslucency, leafNormal, leafRoughness, leafDryTexture, leafDryestTexture };
        if (sp.cactus) {
            const cb = base.replace(/_skin$/, '_skin_clean');
            assets.barkCleanAlbedo = await _tex('bark', cb + '_albedo.png', true);
            assets.barkCleanNormal = await _tex('bark', cb + '_normal.png', false);
            assets.barkCleanRoughness = await _tex('bark', cb + '_roughness.png', false);
            assets.barkDamage = sp.barkDamage ?? 0.35;
            assets.barkMat = M.tree.makeCactusBarkMaterial(assets);
            assets.spineMat = M.spines.makeSpineMaterial(assets, null);
        } else {
            assets.barkMat = M.tree.makeBarkMaterial(assets);
        }
        if (sp.thatchBark) {
            const tb = sp.thatchBark.replace('_albedo.png', '');
            assets.thatchTexture = await _tex('bark', sp.thatchBark, true);
            assets.thatchNormal = await _tex('bark', tb + '_normal.png', false);
            assets.thatchRoughness = await _tex('bark', tb + '_roughness.png', false);
            assets.thatchBarkMat = M.tree.makeThatchBarkMaterial(assets);
        }
        if (!sp.cactus && sp.foliageType === 'rosette') {
            const y = M.yucca.makeYuccaMaterial(assets, sp.foliage);
            assets.rosetteMat = y.material;
            assets.frondGreenTint = y.greenTint;
            assets.frondDryTint = y.dryTint;
            assets.frondDryestTint = y.dryestTint;
            assets.frondDryness = y.dryness;
        } else if (!sp.cactus) {
            const lf = M.leafCards.makeFoliageMaterial(assets, { ...sp.foliage, mode: 'leaves' });
            assets.leafMat = lf.material; assets.leafCenter = lf.centerUniform;
            assets.leafTintNode = lf.tintNode; assets.leafTintAmount = lf.tintAmount;
            const cf = M.leafCards.makeFoliageMaterial(assets, { ...sp.foliage, mode: 'clusters' });
            assets.clusterMat = cf.material; assets.clusterCenter = cf.centerUniform;
            assets.clusterTintNode = cf.tintNode; assets.clusterTintAmount = cf.tintAmount;
        }
        _assetCache.set(sp.name, assets);
        return assets;
    };

    globalThis.makeTree = async (o = {}) => {
        (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('seed_three');
        const M = await _load();
        const name = o.species ?? 'whiteOak';
        const spBase = M.species.SPECIES[name];
        if (!spBase) throw new Error('makeTree: unknown species "' + name + '" — pick from: ' + Object.keys(M.species.SPECIES).join(', '));
        const sp = o.params ? { ...spBase, params: { ...spBase.params, ...o.params } } : spBase;
        const assets = await _assets(M, sp);
        const { group } = M.tree.buildTree(sp, o.seed ?? 1, assets, o.lod ?? {});
        if (o.scale) group.scale.setScalar(o.scale);
        if (o.position) group.position.fromArray(o.position);
        group.userData.noSupportCheck = true;
        if (o.windStrength != null) M.wind.windStrength.value = o.windStrength;
        if (o.windSpeed != null) M.wind.windSpeed.value = o.windSpeed;
        return { group, species: name, seed: o.seed ?? 1,
            wind: { strength: M.wind.windStrength, speed: M.wind.windSpeed } };
    };

    console.log('[seed_three] makeTree ready — SeedThree procedural trees/plants (10 species; needs a SeedThree checkout)');
})();
