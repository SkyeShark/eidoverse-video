// audit_core.js — extractable sensor-core primitives (Phase A.1; design:
// work/sol_collab/PROPOSALS.md, hardening: work/sol_collab/REVIEW_PHASE_A.md).
//
// Exports (no engine imports, no globals):
//   createLedger()                                   -> structured results
//   buildInventory(THREE, scene [, opts])            -> canonical bodies + leaves
//   mapDeclarations(THREE, scene, inventory [, opts])-> declaration accounting
//   coverageRecords(decl, inventory)                 -> ledger records (source of truth)
//   digestFromLedger(ledger [, runtimeLines])        -> persisted text digest
//   snapshotPolicy(globalsSource)                    -> immutable policy snapshot
//
// The invariant is OBSERVABILITY: every obligation is measured, replaced by a
// measurable contract, or reported unknown. Declarations label outcomes
// (DECLARED_EXCEPTION) — they never erase geometry, and they are persisted
// regardless of scope. Identity rules (review findings 1-5):
//   - a leaf is one mesh's OWN geometry (never subtree bounds); InstancedMesh
//     instances are virtual leaves; BatchedMesh is an explicit SKIPPED;
//   - leaves merge into one body only on embedding evidence WITHIN a shared
//     provenance root (or explicit registration) — bare collision between
//     unrelated geometry can never redefine identity, and an invisible
//     enclosing hull glues nothing;
//   - leaf IDs are mesh UUIDs (stable under reparenting); labels are copied
//     strings, not live references;
//   - descriptors (L, R, dims) come from LOCAL geometry x world scale —
//     invariant under rigid rotation; degenerate/extreme values are flagged
//     with a conditioning state instead of silently participating.
// Shared-runtime caveat (PROPOSALS.md:15): userData-stamped provenance is
// tamper-EVIDENT, not tamper-proof; engine adapters should prefer private
// WeakMaps where clone semantics allow.

// ---------------------------------------------------------------------------
// Ledger
// ---------------------------------------------------------------------------
const OUTCOMES = ['PASS', 'WARN', 'SKIPPED'];
const DISPOSITIONS = ['ENFORCED', 'DECLARED_EXCEPTION', 'CONTRACT_VALIDATED'];
const CLASSES = ['CORRECTNESS', 'REVIEW', 'INFO'];

export function createLedger() {
    const records = [];
    return {
        record(entry) {
            const r = Object.freeze({
                check: String(entry.check || 'unknown'),
                outcome: OUTCOMES.includes(entry.outcome) ? entry.outcome : 'SKIPPED',
                disposition: DISPOSITIONS.includes(entry.disposition) ? entry.disposition : 'ENFORCED',
                class: CLASSES.includes(entry.class) ? entry.class : 'CORRECTNESS',
                confidence: Number.isFinite(entry.confidence) ? entry.confidence : 1,
                bodies: Object.freeze((entry.bodies || []).map(String)),
                invariant: String(entry.invariant || ''),
                metrics: Object.freeze(JSON.parse(JSON.stringify(entry.metrics || {}))),
                declarations: Object.freeze((entry.declarations || []).map(String)),
                message: String(entry.message || ''),
                time: Number.isFinite(entry.time) ? entry.time : null,
            });
            records.push(r);
            return r;
        },
        get records() { return records.slice(); },
        summarize() {
            const by = (key) => records.reduce((m, r) => ((m[r[key]] = (m[r[key]] || 0) + 1), m), {});
            return { total: records.length, byOutcome: by('outcome'), byDisposition: by('disposition'), byClass: by('class') };
        },
        // clean = nothing warned, nothing was declared away, nothing material
        // was skipped. A disabled or excepted check can never produce clean.
        isClean() {
            return !records.some((r) =>
                r.outcome === 'WARN'
                || r.disposition === 'DECLARED_EXCEPTION'
                || (r.outcome === 'SKIPPED' && r.class === 'CORRECTNESS'));
        },
        toJSON() { return { summary: this.summarize(), clean: this.isClean(), records }; },
    };
}

// ---------------------------------------------------------------------------
// Policy snapshot — one immutable capture of the global gates, taken with the
// same truthiness the gates use. Non-boolean truthy values are recorded as
// such (review finding 10): `_noMotionCheck = 1` disables exactly like true.
// ---------------------------------------------------------------------------
export const GLOBAL_FLAGS = [
    '_noAutoPlacementCheck', '_noMotionCheck', '_noLocomotionCheck',
    '_allowManualLocomotion', '_noOpacityCheck', '_autoFixPlacement',
];

export function snapshotPolicy(src) {
    const snap = { flags: {}, nonBoolean: {} };
    for (const f of GLOBAL_FLAGS) {
        const v = src[f];
        snap.flags[f] = !!v;                            // effective truthiness — matches the gates
        if (v !== undefined && typeof v !== 'boolean') snap.nonBoolean[f] = typeof v;
    }
    return Object.freeze({ flags: Object.freeze(snap.flags), nonBoolean: Object.freeze(snap.nonBoolean) });
}

// ---------------------------------------------------------------------------
// Inventory — leaves and canonical bodies.
// ---------------------------------------------------------------------------
export function buildInventory(THREE, scene, opts = {}) {
    let embedFrac = Number(opts.embedFrac);
    if (!Number.isFinite(embedFrac)) embedFrac = 0.25;
    embedFrac = Math.min(0.95, Math.max(0.05, embedFrac));
    const provenanceOf = typeof opts.provenanceOf === 'function' ? opts.provenanceOf : defaultProvenance;

    scene.updateMatrixWorld(true);

    const leaves = [];
    const notes = [];   // {kind, message} — conditioning / unsupported states
    const corner = new THREE.Vector3();
    (function walk(o, visChain) {
        const effVis = visChain && o.visible !== false;
        if (o.isMesh || o.isBatchedMesh) collectLeaves(o, effVis);
        for (const c of o.children) walk(c, effVis);
    })(scene, true);

    function collectLeaves(mesh, effVis) {
        const geo = mesh.geometry;
        const pos = geo && geo.getAttribute && geo.getAttribute('position');
        if (!pos) return;
        if (mesh.isBatchedMesh) {
            notes.push({ kind: 'SKIPPED', message: `BatchedMesh '${mesh.name || '(unnamed)'}' is not virtualized yet — its ${pos.count} vertices are UNAUDITED, not passed.` });
            return;
        }
        if (!geo.boundingBox) geo.computeBoundingBox();
        const lb = geo.boundingBox;
        if (!lb || !isFinite(lb.min.x)) {
            notes.push({ kind: 'SKIPPED', message: `mesh '${mesh.name || '(unnamed)'}' has non-finite local bounds — UNAUDITED.` });
            return;
        }
        const triCount = geo.index ? geo.index.count / 3 : pos.count / 3;
        const localSize = lb.getSize(new THREE.Vector3());
        const label = nameChain(mesh);
        const prov = provenanceOf(mesh);
        const makeLeaf = (worldMatrix, idSuffix) => {
            // world AABB from the 8 LOCAL bbox corners of THIS mesh's own
            // geometry — subtree bounds are never used (review finding 1)
            const box = new THREE.Box3();
            for (const cx of [lb.min.x, lb.max.x]) for (const cy of [lb.min.y, lb.max.y]) for (const cz of [lb.min.z, lb.max.z]) {
                box.expandByPoint(corner.set(cx, cy, cz).applyMatrix4(worldMatrix));
            }
            const scl = new THREE.Vector3().setFromMatrixScale(worldMatrix);
            // rotation-invariant local dims: local extents x world scale
            const dims = [localSize.x * Math.abs(scl.x), localSize.y * Math.abs(scl.y), localSize.z * Math.abs(scl.z)];
            const nz = dims.filter((d) => d > 0).sort((a, b) => a - b);
            const conditioning =
                dims.some((d) => !Number.isFinite(d) || d > 1e12) ? 'overflow'
                : nz.length === 0 ? 'degenerate'
                : nz.length < 3 ? 'planar'
                : 'ok';
            leaves.push({
                id: mesh.uuid + (idSuffix || ''),
                label, box, dims,
                L: nz.length ? nz[Math.floor((nz.length - 1) / 2)] : 0,   // median NON-ZERO side
                R: nz.length ? Math.hypot(dims[0], dims[1], dims[2]) / 2 : 0,
                triCount, conditioning,
                effectiveVisible: effVis,
                deforming: !!mesh.isSkinnedMesh || (geo.morphAttributes && Object.keys(geo.morphAttributes).length > 0),
                provenance: prov,
                mesh,
            });
        };
        if (mesh.isInstancedMesh) {
            // each instance is a VIRTUAL LEAF (review finding 4) — the
            // aggregate AABB (empty space included) is never used
            const im = new THREE.Matrix4();
            const wm = new THREE.Matrix4();
            for (let i = 0; i < mesh.count; i++) {
                mesh.getMatrixAt(i, im);
                wm.multiplyMatrices(mesh.matrixWorld, im);
                makeLeaf(wm, `#${i}`);
            }
        } else {
            makeLeaf(mesh.matrixWorld, '');
        }
    }

    // --- merge leaves into bodies: embedding evidence WITHIN a provenance
    // root only (review finding 2). No provenance => leaf stands alone; the
    // scene's own collisions can never redefine identity.
    const parent = leaves.map((_, i) => i);
    const find = (i) => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
    const union = (a, b) => { const ra = find(a), rb = find(b); if (ra !== rb) parent[rb] = ra; };
    const byProv = new Map();
    leaves.forEach((l, i) => {
        if (!l.provenance) return;
        if (!byProv.has(l.provenance)) byProv.set(l.provenance, []);
        byProv.get(l.provenance).push(i);
    });
    for (const idxs of byProv.values()) {
        for (let a = 0; a < idxs.length; a++) {
            for (let b = a + 1; b < idxs.length; b++) {
                const la = leaves[idxs[a]], lb2 = leaves[idxs[b]];
                if (overlapFraction(la.box, lb2.box) >= embedFrac) union(idxs[a], idxs[b]);
            }
        }
    }
    // explicit registrations: label bodies; a registration spanning leaves
    // that the embedding rule did NOT merge is a coalescence declaration —
    // recorded, never silently honored (review finding 3 / PROPOSALS §1.1)
    const coalescenceDeclarations = [];
    if (opts.explicitBodies) {
        for (const root of opts.explicitBodies) {
            const memberIdx = [];
            root.traverse((d) => leaves.forEach((l, i) => { if (l.mesh === d) memberIdx.push(i); }));
            if (memberIdx.length > 1) {
                const roots = new Set(memberIdx.map(find));
                if (roots.size > 1) {
                    coalescenceDeclarations.push({
                        label: nameChain(root), leafCount: memberIdx.length, islands: roots.size,
                    });
                }
            }
        }
    }

    const groups = new Map();
    leaves.forEach((l, i) => {
        const r = find(i);
        if (!groups.has(r)) groups.set(r, []);
        groups.get(r).push(l);
    });

    const bodies = [];
    let n = 0;
    for (const members of groups.values()) {
        const box = new THREE.Box3();
        for (const m of members) box.union(m.box);
        const vis = members.some((m) => m.effectiveVisible);
        const tri = members.reduce((s, m) => s + m.triCount, 0);
        const conditioning = members.some((m) => m.conditioning === 'overflow') ? 'overflow'
            : members.every((m) => m.conditioning === 'degenerate') ? 'degenerate' : 'ok';
        bodies.push({
            id: `body_${n++}`,
            label: members[0].label,
            leafIds: members.map((m) => m.id),
            box,
            L: median(members.map((m) => m.L).filter((x) => x > 0)) || 0,
            R: Math.max(...members.map((m) => m.R)),
            triCount: tri,
            effectiveVisible: vis,
            deforming: members.some((m) => m.deforming),
            conditioning,
            provenance: members[0].provenance,
            // physical = participates in coverage denominators; hidden,
            // zero-triangle, and degenerate geometry cannot dilute fractions
            // (review finding 8)
            physical: vis && tri > 0 && conditioning === 'ok',
        });
    }

    const leafToBody = new Map();
    const meshLeafIds = new Map();   // mesh object -> its leaf ids (for declaration mapping)
    for (const b of bodies) for (const lid of b.leafIds) leafToBody.set(lid, b);
    for (const l of leaves) {
        if (!meshLeafIds.has(l.mesh)) meshLeafIds.set(l.mesh, []);
        meshLeafIds.get(l.mesh).push(l.id);
    }

    return {
        bodies, leaves, leafToBody, meshLeafIds,
        physicalBodies: bodies.filter((b) => b.physical),
        notes, coalescenceDeclarations,
        meshCount: new Set(leaves.map((l) => l.mesh)).size,
    };
}

function defaultProvenance(mesh) {
    let p = mesh;
    while (p) { if (p.userData && p.userData.__srcAsset) return String(p.userData.__srcAsset); p = p.parent; }
    return null;
}
function nameChain(o) {
    let p = o;
    while (p) { if (p.name) return String(p.name); p = p.parent; }
    return '(unnamed)';
}
function median(a) {
    if (!a.length) return 0;
    const s = a.slice().sort((x, y) => x - y);
    return s[Math.floor((s.length - 1) / 2)];
}
// per-axis overlap fractions multiplied — never three raw world lengths, so
// extreme scales cannot overflow (review finding 2, boxVolume note)
function overlapFraction(a, b) {
    let frac = 1;
    for (const ax of ['x', 'y', 'z']) {
        const lo = Math.max(a.min[ax], b.min[ax]);
        const hi = Math.min(a.max[ax], b.max[ax]);
        if (hi <= lo) return 0;
        const minLen = Math.min(a.max[ax] - a.min[ax], b.max[ax] - b.min[ax]);
        frac *= minLen > 0 ? Math.min(1, (hi - lo) / minLen) : 1;
    }
    return frac;
}

// ---------------------------------------------------------------------------
// Declaration accounting — leaf-ID unions per flag, then per SENSOR.
// ---------------------------------------------------------------------------
export const OBJECT_FLAGS = [
    'allowIntersect', 'noClippingCheck', 'noSupportCheck', '_sunkPlacement',
    'noMotionCheck', 'noIntrusionCheck', 'noZFightCheck', 'noFacingCheck',
];
// which declarations bypass which sensor (review finding 7): aliases union.
// `assembly` joins clipping because legacy deep-clipping exempts same-tag
// pairs; seated exemptions join support when provided via opts.seatedObjects.
export const SENSOR_ALIASES = {
    clipping: ['allowIntersect', 'noClippingCheck', 'assembly'],
    support: ['noSupportCheck', '_sunkPlacement', 'seated'],
    motion: ['noMotionCheck'],
    facing: ['noFacingCheck'],
    zfight: ['noZFightCheck'],
    intrusion: ['noIntrusionCheck'],
};

export function mapDeclarations(THREE, scene, inventory, opts = {}) {
    const declarations = [];      // {flag, sourceLabel, leafIds:Set, bodies:Set}
    const leafUnionByFlag = new Map();

    const addLeaves = (flag, node, leafSet) => {
        const bodySet = new Set();
        for (const lid of leafSet) { const b = inventory.leafToBody.get(lid); if (b) bodySet.add(b); }
        if (!leafSet.size) return;
        declarations.push({ flag, sourceLabel: nameChain(node), leafIds: leafSet, bodies: bodySet });
        if (!leafUnionByFlag.has(flag)) leafUnionByFlag.set(flag, new Set());
        for (const lid of leafSet) leafUnionByFlag.get(flag).add(lid);
    };

    scene.traverse((node) => {
        const ud = node.userData || {};
        for (const flag of OBJECT_FLAGS) {
            if (!ud[flag]) continue;
            const leafSet = new Set();
            node.traverse((d) => { for (const lid of inventory.meshLeafIds.get(d) || []) leafSet.add(lid); });
            addLeaves(flag, node, leafSet);
        }
        if (ud.assembly) {
            const leafSet = new Set();
            node.traverse((d) => { for (const lid of inventory.meshLeafIds.get(d) || []) leafSet.add(lid); });
            if (leafSet.size) {
                const bodySet = new Set();
                for (const lid of leafSet) { const b = inventory.leafToBody.get(lid); if (b) bodySet.add(b); }
                declarations.push({ flag: 'assembly', tag: String(ud.assembly), sourceLabel: nameChain(node), leafIds: leafSet, bodies: bodySet });
                if (!leafUnionByFlag.has('assembly')) leafUnionByFlag.set('assembly', new Set());
                for (const lid of leafSet) leafUnionByFlag.get('assembly').add(lid);
            }
        }
    });
    for (const o of opts.seatedObjects || []) {
        const leafSet = new Set();
        o.traverse?.((d) => { for (const lid of inventory.meshLeafIds.get(d) || []) leafSet.add(lid); });
        addLeaves('seated', o, leafSet);
    }

    // body coverage per flag from the LEAF union (review finding 6: sharding
    // a flag across all leaves of a body equals flagging its parent)
    const unionByFlag = new Map();
    for (const [flag, leafSet] of leafUnionByFlag) {
        const full = new Set(), partial = new Set();
        for (const b of inventory.bodies) {
            const covered = b.leafIds.filter((lid) => leafSet.has(lid)).length;
            if (covered === 0) continue;
            (covered >= b.leafIds.length ? full : partial).add(b);
        }
        unionByFlag.set(flag, { full, partial, leafCount: leafSet.size, nodes: declarations.filter((d) => d.flag === flag).length });
    }

    // per-sensor unions across aliases
    const unionBySensor = new Map();
    for (const [sensor, aliases] of Object.entries(SENSOR_ALIASES)) {
        const leafSet = new Set();
        for (const a of aliases) for (const lid of leafUnionByFlag.get(a) || []) leafSet.add(lid);
        if (!leafSet.size) continue;
        const full = new Set(), partial = new Set();
        for (const b of inventory.bodies) {
            const covered = b.leafIds.filter((lid) => leafSet.has(lid)).length;
            if (covered === 0) continue;
            (covered >= b.leafIds.length ? full : partial).add(b);
        }
        unionBySensor.set(sensor, { full, partial, leafCount: leafSet.size });
    }

    const assemblies = new Map();  // tag -> Set<body>
    for (const d of declarations) {
        if (d.flag !== 'assembly') continue;
        if (!assemblies.has(d.tag)) assemblies.set(d.tag, new Set());
        for (const b of d.bodies) assemblies.get(d.tag).add(b);
    }

    return { declarations, unionByFlag, unionBySensor, assemblies };
}

// ---------------------------------------------------------------------------
// Coverage -> ledger records (the SOURCE OF TRUTH — the text digest is built
// from these, so no threshold can drop a declaration from persistence).
// ---------------------------------------------------------------------------
export function coverageRecords(decl, inventory, policy, opts = {}) {
    const systemicFrac = opts.systemicFrac ?? 0.5;
    const nPhys = inventory.physicalBodies.length || 1;
    const recs = [];

    recs.push({
        check: 'coverage.inventory', outcome: 'PASS', class: 'INFO',
        invariant: 'bodies are inferred from geometry and provenance, never grouping',
        metrics: {
            bodies: inventory.bodies.length,
            physicalBodies: inventory.physicalBodies.length,
            leaves: inventory.leaves.length,
            meshes: inventory.meshCount,
            nonPhysical: inventory.bodies.length - inventory.physicalBodies.length,
        },
        message: `inventory: ${inventory.bodies.length} canonical bodies (${inventory.leaves.length} leaves, ${inventory.meshCount} meshes; ${inventory.bodies.length - inventory.physicalBodies.length} hidden/degenerate excluded from coverage denominators)`,
    });

    for (const note of inventory.notes) {
        recs.push({ check: 'coverage.inventory', outcome: 'SKIPPED', class: 'CORRECTNESS', message: note.message });
    }
    for (const c of inventory.coalescenceDeclarations) {
        recs.push({
            check: 'coverage.identity', outcome: 'WARN', disposition: 'DECLARED_EXCEPTION', class: 'REVIEW',
            message: `explicit body registration '${c.label}' spans ${c.islands} disconnected islands (${c.leafCount} leaves) — a registration labels evidence; it cannot merge what geometry does not join.`,
        });
    }

    // global disables — per-gated-check SKIPPED records (review finding 15)
    const gatedChecks = {
        _noAutoPlacementCheck: ['clipping', 'support', 'zfight', 'facing', 'density', 'intrusion'],
        _noMotionCheck: ['motion.envelope'],
        _noLocomotionCheck: ['motion.locomotion'],
        _allowManualLocomotion: ['motion.locomotion.disposition'],
        _noOpacityCheck: ['opacity'],
    };
    for (const [flag, checks] of Object.entries(gatedChecks)) {
        if (!policy?.flags?.[flag]) continue;
        const nb = policy.nonBoolean[flag] ? ` (non-boolean ${policy.nonBoolean[flag]} value — treated as truthy by the gate)` : '';
        for (const c of checks) {
            recs.push({
                check: c, outcome: 'SKIPPED', disposition: 'DECLARED_EXCEPTION', class: 'CORRECTNESS',
                declarations: [flag],
                message: flag === '_allowManualLocomotion'
                    ? `${flag}=true${nb} — locomotion findings are sampled but their final disposition is suppressed.`
                    : `GLOBAL DISABLE ${flag}=true${nb} — '${c}' DID NOT RUN. Every obligation it covers is UNOBSERVED, not passed.`,
            });
        }
    }
    for (const [flag, t] of Object.entries(policy?.nonBoolean || {})) {
        if (!policy.flags[flag]) {
            recs.push({ check: 'coverage.policy', outcome: 'WARN', class: 'REVIEW', message: `${flag} holds a non-boolean ${t} that is falsy — confirm this is intentional.` });
        }
    }
    for (const name of opts.missingChecks || []) {
        recs.push({ check: name, outcome: 'SKIPPED', class: 'CORRECTNESS', message: `check implementation '${name}' is missing — its obligations are UNOBSERVED.` });
    }

    // every object-flag declaration persists, regardless of scope (finding 8)
    for (const d of decl.declarations) {
        const bodyLabels = [...d.bodies].slice(0, 4).map((b) => b.label);
        const blanket = d.bodies.size > 1;
        recs.push({
            check: `coverage.${d.flag}`, outcome: blanket ? 'WARN' : 'PASS',
            disposition: 'DECLARED_EXCEPTION', class: blanket ? 'CORRECTNESS' : 'REVIEW',
            bodies: [...d.bodies].map((b) => b.id),
            declarations: [d.flag + (d.tag ? `:${d.tag}` : '')],
            metrics: { leaves: d.leafIds.size, bodies: d.bodies.size },
            message: `${d.flag}${d.tag ? ` '${d.tag}'` : ''} @ '${d.sourceLabel}' covers ${d.leafIds.size} leaf/leaves across ${d.bodies.size} bod${d.bodies.size === 1 ? 'y' : 'ies'}${blanket ? ` — GROUP-BLANKET (${bodyLabels.join(', ')}${d.bodies.size > 4 ? ', …' : ''}); one declaration covering many bodies is a blanket exemption, not a decision` : ''}.`,
        });
    }

    // per-sensor systemic coverage — escalation only changes emphasis; the
    // exact fraction is always recorded
    for (const [sensor, u] of decl.unionBySensor) {
        const physFull = [...u.full].filter((b) => b.physical).length;
        const physPart = [...u.partial].filter((b) => b.physical).length;
        const frac = physFull / nPhys;
        recs.push({
            check: `coverage.sensor.${sensor}`,
            outcome: frac >= systemicFrac ? 'WARN' : 'PASS',
            disposition: 'DECLARED_EXCEPTION', class: frac >= systemicFrac ? 'CORRECTNESS' : 'REVIEW',
            metrics: { fullBodies: physFull, partialBodies: physPart, physicalBodies: nPhys, fraction: +frac.toFixed(3), leafCount: u.leafCount },
            message: `sensor '${sensor}': declarations (all aliases) fully cover ${physFull}/${nPhys} physical bodies (${Math.round(frac * 100)}%)${physPart ? ` + ${physPart} partially` : ''}${frac >= systemicFrac ? ' — SYSTEMIC COVERAGE: mass opt-out defeats the audit; each exemption must be a per-part decision' : ''}.`,
        });
    }

    // assembly tags: report the exact legacy pair scope they hide — no
    // connectivity claims either way (review finding 9)
    for (const [tag, bodies] of decl.assemblies) {
        const nb = bodies.size;
        if (nb < 2) continue;
        const hiddenPairs = (nb * (nb - 1)) / 2;
        recs.push({
            check: 'coverage.assembly', outcome: 'WARN', disposition: 'DECLARED_EXCEPTION', class: 'REVIEW',
            declarations: [`assembly:${tag}`],
            metrics: { bodies: nb, hiddenPairObligations: hiddenPairs },
            message: `assembly '${tag}' spans ${nb} canonical bodies — legacy clipping exempts up to ${hiddenPairs} internal pair obligation(s) under this tag. Whether these parts genuinely join is not measured yet; pair contracts (Phase B) replace this.`,
        });
    }

    return recs;
}

// ---------------------------------------------------------------------------
// Persisted digest — built FROM the ledger (review finding 16). Runtime
// console warnings are a separate section, not the source of truth.
// ---------------------------------------------------------------------------
export function digestFromLedger(ledger, runtimeLines = [], meta = {}) {
    const recs = ledger.records;
    const s = [];
    s.push(`AUDIT DIGEST${meta.runId ? ` — run ${meta.runId}` : ''}${meta.status ? ` — status: ${meta.status}` : ''}`);
    const sum = ledger.summarize();
    s.push(`records: ${sum.total} | outcomes: ${fmt(sum.byOutcome)} | dispositions: ${fmt(sum.byDisposition)} | clean: ${ledger.isClean()}`);
    const section = (title, filter) => {
        const rows = recs.filter(filter);
        if (!rows.length) return;
        s.push('', `== ${title} (${rows.length})`);
        for (const r of rows) s.push(`  [${r.check}] ${r.outcome}/${r.disposition} — ${r.message}`);
    };
    section('warnings', (r) => r.outcome === 'WARN');
    section('declared exceptions (non-warning)', (r) => r.disposition === 'DECLARED_EXCEPTION' && r.outcome !== 'WARN');
    section('skipped / unobserved', (r) => r.outcome === 'SKIPPED');
    section('info', (r) => r.outcome === 'PASS' && r.disposition === 'ENFORCED');
    if (runtimeLines.length) {
        s.push('', `== runtime warnings (console) (${runtimeLines.length})`);
        for (const l of runtimeLines) s.push('  ' + l.split('\n')[0]);
    }
    s.push('', 'REVIEW GATE — the digest measures correctness, not quality. VIEW the probe frames (and the video, if anything moves) and judge the LOOK before reporting this render done.');
    return s.join('\n') + '\n';
}
function fmt(o) { return Object.entries(o).map(([k, v]) => `${k}:${v}`).join(' '); }
