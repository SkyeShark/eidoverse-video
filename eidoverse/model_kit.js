// model_kit.js — globalThis.loadKit(gltf) for modular-kit / asset-library GLTFs.
//
// Many fetched models are KITS: a parts LIBRARY laid out as a catalog (e.g.
// door_*/window_*/cornice_* spread across 50m, or 3 different plants in a row),
// NOT one finished object. Placing the whole `gltf.scene` scatters every part
// across the scene. fetch_model.py flags these on delivery with [KIT_INFO];
// this helper lets you actually USE them — it returns each part CLONED and
// re-centered to origin (bbox-center XZ + bbox-min Y at 0), ready for placeOn /
// arraying / assembly.
//
//   const kit = loadKit(gltf);
//   kit.list();                                   // ['door_centered_large_01', ...]
//   const door = kit.get('door_centered_large_01');
//   placeOn(door, ground, { xz: [2, 0] });
//   for (const w of kit.family('window')) placeOn(w, wall, ...);   // all window_* parts
//   const plants = kit.islands();                 // one Object3D per spatially-separate piece
//
// Each returned object is a fresh THREE.Group at origin — the source gltf is
// never mutated, so you can pull a part multiple times.
(function () {
    if (typeof THREE === 'undefined') {
        console.warn('[model_kit] THREE not present — skipping');
        return;
    }

    // Descend single-child wrapper nodes (Scene > RootNode > [parts]) to the
    // level that actually holds the kit parts.
    function _partsRoot(root) {
        let n = root;
        while (n.children && n.children.length === 1 &&
               n.children[0].children && n.children[0].children.length > 1) {
            n = n.children[0];
        }
        return n;
    }

    // Clone a node and shift it so its bbox is centered in XZ and rests on Y=0,
    // wrapped in a Group at the world origin — ready for placeOn / position.set.
    function _recenter(srcNode, name) {
        const c = srcNode.clone(true);
        const wrap = new THREE.Group();
        wrap.name = name || srcNode.name || 'kit_part';
        wrap.add(c);
        wrap.updateWorldMatrix(true, true);
        const b = new THREE.Box3().setFromObject(wrap);
        if (!b.isEmpty()) {
            const ctr = b.getCenter(new THREE.Vector3());
            c.position.x -= ctr.x;
            c.position.z -= ctr.z;
            c.position.y -= b.min.y;
        }
        return wrap;
    }

    globalThis.loadKit = function (gltfOrObj) {
        const root = (gltfOrObj && gltfOrObj.scene) ? gltfOrObj.scene : gltfOrObj;
        if (!root || !root.traverse) throw new Error('[loadKit] pass a gltf or an Object3D');
        root.updateWorldMatrix(true, true);
        const host = _partsRoot(root);
        const partNodes = host.children.slice().filter((ch) => {
            const b = new THREE.Box3().setFromObject(ch);
            return !b.isEmpty();
        });
        const byName = {};
        partNodes.forEach((ch, i) => { byName[ch.name || ('part_' + i)] = ch; });

        // Spatially-separate sub-objects: union-find merge of part world-bboxes
        // (overlap / near-touch) → one recentered Group per island. A multi-mesh
        // plant comes back as ONE island; a 3-plant row as three.
        function islands() {
            root.updateWorldMatrix(true, true);
            const boxes = partNodes.map((ch) => new THREE.Box3().setFromObject(ch));
            const diags = boxes.map((b) => b.getSize(new THREE.Vector3()).length()).sort((a, b) => a - b);
            const med = diags[diags.length >> 1] || 1;
            const eps = med * 0.15;
            const par = partNodes.map((_, i) => i);
            const find = (i) => { while (par[i] !== i) { par[i] = par[par[i]]; i = par[i]; } return i; };
            for (let i = 0; i < boxes.length; i++)
                for (let j = i + 1; j < boxes.length; j++)
                    if (boxes[i].clone().expandByScalar(eps).intersectsBox(boxes[j])) par[find(i)] = find(j);
            const groups = {};
            partNodes.forEach((_, i) => { (groups[find(i)] = groups[find(i)] || []).push(i); });
            return Object.values(groups).map((idxs) => {
                const g = new THREE.Group();
                g.name = 'kit_island';
                idxs.forEach((i) => g.add(partNodes[i].clone(true)));
                return _recenter(g, 'kit_island');
            });
        }

        return {
            count: partNodes.length,
            names: partNodes.map((ch) => ch.name || ''),
            list() { return this.names.slice(); },
            get(name) { const n = byName[name]; return n ? _recenter(n, name) : null; },
            part(i) { const n = partNodes[i]; return n ? _recenter(n, n.name) : null; },
            family(prefix) {
                const pfx = String(prefix).toLowerCase();
                return partNodes
                    .filter((ch) => (ch.name || '').toLowerCase().startsWith(pfx))
                    .map((ch) => _recenter(ch, ch.name));
            },
            islands,
        };
    };

    console.log('[model_kit] loadKit(gltf) registered — named, origin-centered parts for modular kits');
})();
