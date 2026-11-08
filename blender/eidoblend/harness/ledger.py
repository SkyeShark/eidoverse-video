"""eidoblend.harness.ledger: eidoverse/audit_core.js ported, whole. Plain Python (no bpy: harness.audits feeds it
the scene's leaves and declarations).

    create_ledger()                                        -> Ledger: structured results
    snapshot_policy(src)                                   -> the scene-wide flags, captured once
    build_inventory(leaves, embed_frac, explicit_bodies)   -> canonical bodies + leaves
    map_declarations(inventory, nodes, seated)             -> declaration accounting
    coverage_records(decl, inventory, policy, missing_checks, systemic_frac)  -> ledger records (source of truth)
    digest_from_ledger(ledger, runtime_lines, run_id, status)                 -> the persisted text digest

The invariant is the engine's, OBSERVABILITY: every obligation is measured, replaced by a measurable contract, or
reported unknown. Declarations label outcomes (DECLARED_EXCEPTION); they never erase geometry, and they are persisted
whatever their scope. Identity rules, as audit_core.js has them:
  - a leaf is one object's OWN geometry (never subtree bounds); each instance (a collection instance, a Geometry Nodes
    instance) is a virtual leaf of its own;
  - leaves merge into one body only on embedding evidence WITHIN a shared provenance (or an explicit registration,
    which is recorded, never honoured): collision between unrelated geometry never redefines identity, and an
    invisible enclosing hull glues nothing;
  - leaf ids are object names ('name#instance' for an instance), labels are copied strings;
  - descriptors (L, R, dims) come from LOCAL extents x world scale (invariant under rigid rotation); degenerate or
    extreme values carry a conditioning state instead of silently taking part.

Every check the runner makes is a record in one ledger; the digest files (<out>.audit.txt and .audit.json) are built
FROM the ledger and written on every exit path, so an absent audit file means the audit never ran, never that it was
clean.

    record   check, outcome (PASS | WARN | SKIPPED), disposition (ENFORCED | DECLARED_EXCEPTION | CONTRACT_VALIDATED),
             class (CORRECTNESS | REVIEW | INFO), confidence, bodies, invariant, metrics, declarations, message, time
    clean    nothing warned, nothing was declared away, nothing material (CORRECTNESS) was skipped

Flags. The WebGPU edition's globals and userData flags, in snake_case (the JS spelling is accepted too):

    scene-wide (a module-level name in the scene script, or a scene custom property):
        _no_auto_placement_check  _no_motion_check  _no_locomotion_check  _allow_manual_locomotion
        _no_opacity_check  _auto_fix_placement
    per object (an object custom property; it covers the object and everything parented under it):
        allow_intersect  no_clipping_check  no_support_check  _sunk_placement  no_motion_check  no_intrusion_check
        no_z_fight_check  no_facing_check  assembly (a tag string); a seated character (eido_seated) joins 'support'
"""

from __future__ import annotations

import copy
import json
import math
import time as _time

OUTCOMES = ('PASS', 'WARN', 'SKIPPED')
DISPOSITIONS = ('ENFORCED', 'DECLARED_EXCEPTION', 'CONTRACT_VALIDATED')
CLASSES = ('CORRECTNESS', 'REVIEW', 'INFO')

GLOBAL_FLAGS = ('_no_auto_placement_check', '_no_motion_check', '_no_locomotion_check', '_allow_manual_locomotion',
                '_no_opacity_check', '_auto_fix_placement')
GLOBAL_FLAG_ALIASES = {'_noAutoPlacementCheck': '_no_auto_placement_check', '_noMotionCheck': '_no_motion_check',
                       '_noLocomotionCheck': '_no_locomotion_check',
                       '_allowManualLocomotion': '_allow_manual_locomotion', '_noOpacityCheck': '_no_opacity_check',
                       '_autoFixPlacement': '_auto_fix_placement',
                       # the placement family's scene custom properties
                       'eido_no_auto_placement_check': '_no_auto_placement_check',
                       'eido_auto_fix_placement': '_auto_fix_placement'}
OBJECT_FLAGS = ('allow_intersect', 'no_clipping_check', 'no_support_check', '_sunk_placement', 'no_motion_check',
                'no_intrusion_check', 'no_z_fight_check', 'no_facing_check')
OBJECT_FLAG_ALIASES = {'allowIntersect': 'allow_intersect', 'noClippingCheck': 'no_clipping_check',
                       'noSupportCheck': 'no_support_check', '_sunkPlacement': '_sunk_placement',
                       'sunk_placement': '_sunk_placement', 'noMotionCheck': 'no_motion_check',
                       'noIntrusionCheck': 'no_intrusion_check', 'noZFightCheck': 'no_z_fight_check',
                       'no_zfight_check': 'no_z_fight_check', 'noFacingCheck': 'no_facing_check'}
# which declarations bypass which sensor: aliases union ('assembly' joins clipping, 'seated' joins support)
SENSOR_ALIASES = {
    'clipping': ('allow_intersect', 'no_clipping_check', 'assembly'),
    'support': ('no_support_check', '_sunk_placement', 'seated'),
    'motion': ('no_motion_check',),
    'facing': ('no_facing_check',),
    'zfight': ('no_z_fight_check',),
    'intrusion': ('no_intrusion_check',),
}
# the checks each global disable switches off (each becomes a SKIPPED record: unobserved, not passed)
GATED_CHECKS = {
    '_no_auto_placement_check': ('clipping', 'support', 'zfight', 'facing', 'density', 'intrusion'),
    '_no_motion_check': ('motion.envelope',),
    '_no_locomotion_check': ('motion.locomotion',),
    '_allow_manual_locomotion': ('motion.locomotion.disposition',),
    '_no_opacity_check': ('opacity',),
}
# gated checks that do not exist in Blender: switching them off changes nothing, and the digest says so
NOT_IN_BLENDER = {'opacity': "the engine's NodeMaterial '.opacity' binding check (three.js only: Blender's alpha "
                             'always binds)'}


def _freeze(v):
    return json.loads(json.dumps(v, default=str))


def _typeof(v) -> str:
    """JavaScript's typeof for a flag's value, so the digest reads as the engine's did ('non-boolean number')."""
    if isinstance(v, bool):
        return 'boolean'
    if isinstance(v, (int, float)):
        return 'number'
    if isinstance(v, str):
        return 'string'
    if callable(v):
        return 'function'
    return 'object'


# ---------------------------------------------------------------------------------------------------- ledger ---

class Ledger:
    def __init__(self):
        self._records = []

    def record(self, check='unknown', outcome='SKIPPED', disposition='ENFORCED', cls='CORRECTNESS', confidence=1.0,
               bodies=(), invariant='', metrics=None, declarations=(), message='', time=None, **kw):
        if 'class' in kw:
            cls = kw.pop('class')
        conf = confidence if isinstance(confidence, (int, float)) and math.isfinite(confidence) else 1.0
        r = {
            'check': str(check or 'unknown'),
            'outcome': outcome if outcome in OUTCOMES else 'SKIPPED',
            'disposition': disposition if disposition in DISPOSITIONS else 'ENFORCED',
            'class': cls if cls in CLASSES else 'CORRECTNESS',
            'confidence': float(conf),
            'bodies': [str(b) for b in bodies],
            'invariant': str(invariant or ''),
            'metrics': _freeze(metrics or {}),
            'declarations': [str(d) for d in declarations],
            'message': str(message or ''),
            'time': time if isinstance(time, (int, float)) and math.isfinite(time) else None,
        }
        self._records.append(r)
        return copy.deepcopy(r)

    def extend(self, records, note=''):
        """Re-record persisted records (a reused build's audits), optionally prefixing their message."""
        for r in records:
            r = dict(r)
            if note:
                r['message'] = f'{note}{r.get("message", "")}'
            r['cls'] = r.pop('class', 'CORRECTNESS')
            self.record(**r)

    @property
    def records(self):
        return copy.deepcopy(self._records)

    def summarize(self):
        def by(key):
            m = {}
            for r in self._records:
                m[r[key]] = m.get(r[key], 0) + 1
            return m
        return {'total': len(self._records), 'by_outcome': by('outcome'), 'by_disposition': by('disposition'),
                'by_class': by('class')}

    def is_clean(self):
        """Clean = nothing warned, nothing was declared away, nothing material was skipped. A disabled or excepted
        check can never produce clean."""
        return not any(r['outcome'] == 'WARN' or r['disposition'] == 'DECLARED_EXCEPTION'
                       or (r['outcome'] == 'SKIPPED' and r['class'] == 'CORRECTNESS') for r in self._records)

    def to_json(self):
        return {'summary': self.summarize(), 'clean': self.is_clean(), 'records': self.records}


def create_ledger() -> Ledger:
    return Ledger()


def canonical_flag(name: str, aliases: dict) -> str:
    return aliases.get(name, name)


# ------------------------------------------------------------------------------------------- policy snapshot ---

def snapshot_policy(src: dict) -> dict:
    """One immutable capture of the scene-wide flags, with the truthiness the gates use. src: {name: value}, either
    spelling. Non-boolean values are recorded as such (a 1 disables exactly like True)."""
    vals = {}
    for k, v in dict(src).items():
        c = canonical_flag(k, GLOBAL_FLAG_ALIASES)
        if c in GLOBAL_FLAGS:
            vals[c] = v
    snap = {'flags': {}, 'non_boolean': {}}
    for f in GLOBAL_FLAGS:
        v = vals.get(f)
        snap['flags'][f] = bool(v)
        if v is not None and not isinstance(v, bool):
            snap['non_boolean'][f] = _typeof(v)
    return snap


def policy_records(policy: dict) -> list:
    """SKIPPED records for every check a global disable switched off, and a note for falsy non-booleans."""
    recs = []
    for flag, checks in GATED_CHECKS.items():
        if not policy['flags'].get(flag):
            continue
        nb = policy['non_boolean'].get(flag)
        nb = f' (non-boolean {nb} value: treated as truthy by the gate)' if nb else ''
        for c in checks:
            if c in NOT_IN_BLENDER:
                recs.append({'check': c, 'outcome': 'PASS', 'class': 'INFO', 'declarations': [flag],
                             'message': f'{flag}=True{nb} switches off {NOT_IN_BLENDER[c]}: there is no such check '
                                        'here, so nothing went unobserved.'})
                continue
            msg = (f'{flag}=True{nb}: locomotion findings are sampled but their final disposition is suppressed.'
                   if flag == '_allow_manual_locomotion' else
                   f"GLOBAL DISABLE {flag}=True{nb}: '{c}' DID NOT RUN. Every obligation it covers is UNOBSERVED, "
                   'not passed.')
            recs.append({'check': c, 'outcome': 'SKIPPED', 'disposition': 'DECLARED_EXCEPTION', 'class': 'CORRECTNESS',
                         'declarations': [flag], 'message': msg})
    for flag, t in policy['non_boolean'].items():
        if not policy['flags'].get(flag):
            recs.append({'check': 'coverage.policy', 'outcome': 'WARN', 'class': 'REVIEW',
                         'message': f'{flag} holds a non-boolean {t} that is falsy: confirm this is intentional.'})
    return recs


# ------------------------------------------------------------------------------------------------- inventory ---

def _median(a):
    if not a:
        return 0.0
    s = sorted(a)
    return s[(len(s) - 1) // 2]


def overlap_fraction(a, b) -> float:
    """Per-axis overlap fractions multiplied (never three raw world lengths, so extreme scales cannot overflow).
    a, b: ((min x, y, z), (max x, y, z))."""
    frac = 1.0
    for ax in range(3):
        lo, hi = max(a[0][ax], b[0][ax]), min(a[1][ax], b[1][ax])
        if hi <= lo:
            return 0.0
        mn = min(a[1][ax] - a[0][ax], b[1][ax] - b[0][ax])
        frac *= min(1.0, (hi - lo) / mn) if mn > 0 else 1.0
    return frac


def make_leaf(id, label, box, dims, tri_count, effective_visible=True, deforming=False, provenance=None, owner=None):
    """A leaf as build_inventory takes it: one object's own geometry (or one instance). box = ((min), (max)) in world
    space, dims = its LOCAL extents x world scale, owner = the object name declarations reach it through."""
    dims = [float(d) for d in dims]
    nz = sorted(d for d in dims if d > 0)
    conditioning = ('overflow' if any((not math.isfinite(d)) or d > 1e12 for d in dims)
                    else 'degenerate' if not nz else 'planar' if len(nz) < 3 else 'ok')
    return {'id': str(id), 'label': str(label), 'box': (tuple(map(float, box[0])), tuple(map(float, box[1]))),
            'dims': dims, 'L': nz[(len(nz) - 1) // 2] if nz else 0.0,
            'R': math.sqrt(sum(d * d for d in dims)) / 2 if nz else 0.0, 'tri_count': int(tri_count),
            'conditioning': conditioning, 'effective_visible': bool(effective_visible), 'deforming': bool(deforming),
            'provenance': provenance or None, 'owner': owner if owner is not None else str(id)}


def build_inventory(leaves, embed_frac=0.25, explicit_bodies=(), notes=()) -> dict:
    """Leaves merged into canonical bodies on embedding evidence WITHIN a shared provenance only.

    leaves: make_leaf dicts. explicit_bodies: [(label, {owner names})], registrations to check (never honoured).
    notes: [{'kind': 'SKIPPED', 'message'}] the adapter already has (unaudited geometry).
    Returns {'bodies', 'leaves', 'leaf_to_body', 'owner_leaf_ids', 'physical_bodies', 'notes',
             'coalescence_declarations', 'mesh_count'}."""
    try:
        embed_frac = float(embed_frac)
    except (TypeError, ValueError):
        embed_frac = float('nan')
    if not math.isfinite(embed_frac):
        embed_frac = 0.25
    embed_frac = min(0.95, max(0.05, embed_frac))
    leaves = list(leaves)
    parent = list(range(len(leaves)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    by_prov = {}
    for i, lf in enumerate(leaves):
        if lf['provenance']:
            by_prov.setdefault(lf['provenance'], []).append(i)
    for idxs in by_prov.values():
        # sweep along x: two boxes apart on x have no overlap at all, so only x-overlapping pairs are measured
        # (the engine's all-pairs loop, without its cost on a scatter of thousands of instances)
        idxs = sorted(idxs, key=lambda i: leaves[i]['box'][0][0])
        for a in range(len(idxs)):
            ba = leaves[idxs[a]]['box']
            for b in range(a + 1, len(idxs)):
                bb = leaves[idxs[b]]['box']
                if bb[0][0] >= ba[1][0]:
                    break
                if overlap_fraction(ba, bb) >= embed_frac:
                    union(idxs[a], idxs[b])
    coalescence = []
    for label, owners in explicit_bodies or ():
        owners = set(owners)
        members = [i for i, lf in enumerate(leaves) if lf['owner'] in owners]
        if len(members) > 1:
            roots = {find(i) for i in members}
            if len(roots) > 1:
                coalescence.append({'label': str(label), 'leaf_count': len(members), 'islands': len(roots)})
    groups = {}
    for i, lf in enumerate(leaves):
        groups.setdefault(find(i), []).append(lf)
    bodies = []
    for n, members in enumerate(groups.values()):
        lo = tuple(min(m['box'][0][k] for m in members) for k in range(3))
        hi = tuple(max(m['box'][1][k] for m in members) for k in range(3))
        vis = any(m['effective_visible'] for m in members)
        tri = sum(m['tri_count'] for m in members)
        cond = ('overflow' if any(m['conditioning'] == 'overflow' for m in members)
                else 'degenerate' if all(m['conditioning'] == 'degenerate' for m in members) else 'ok')
        bodies.append({'id': f'body_{n}', 'label': members[0]['label'], 'leaf_ids': [m['id'] for m in members],
                       'box': (lo, hi), 'L': _median([m['L'] for m in members if m['L'] > 0]) or 0.0,
                       'R': max(m['R'] for m in members), 'tri_count': tri, 'effective_visible': vis,
                       'deforming': any(m['deforming'] for m in members), 'conditioning': cond,
                       'provenance': members[0]['provenance'],
                       # physical = takes part in coverage denominators: hidden, zero-triangle and degenerate
                       # geometry cannot dilute fractions
                       'physical': vis and tri > 0 and cond == 'ok'})
    leaf_to_body = {lid: b for b in bodies for lid in b['leaf_ids']}
    owner_leaf_ids = {}
    for lf in leaves:
        owner_leaf_ids.setdefault(lf['owner'], []).append(lf['id'])
    return {'bodies': bodies, 'leaves': leaves, 'leaf_to_body': leaf_to_body, 'owner_leaf_ids': owner_leaf_ids,
            'physical_bodies': [b for b in bodies if b['physical']], 'notes': list(notes or ()),
            'coalescence_declarations': coalescence, 'mesh_count': len({lf['owner'] for lf in leaves})}


# --------------------------------------------------------------------------------------------- declarations ---

def map_declarations(inventory: dict, nodes, seated=()) -> dict:
    """Declaration accounting: leaf-id unions per flag, then per SENSOR.

    nodes: [{'label', 'flags': {flag: value}, 'leaf_ids': set}] (each declaring object with every leaf under it;
    the adapter walks the hierarchy). seated: [{'label', 'leaf_ids'}] seated characters (they join 'support').
    Returns {'declarations', 'union_by_flag', 'union_by_sensor', 'assemblies'}."""
    declarations = []
    leaf_union_by_flag = {}

    def add(flag, node, leaf_set, tag=None):
        leaf_set = set(leaf_set)
        if not leaf_set:
            return
        body_set = {inventory['leaf_to_body'][l]['id'] for l in leaf_set if l in inventory['leaf_to_body']}
        d = {'flag': flag, 'source_label': str(node.get('label', '(unnamed)')), 'leaf_ids': leaf_set,
             'bodies': body_set}
        if tag is not None:
            d['tag'] = str(tag)
        declarations.append(d)
        leaf_union_by_flag.setdefault(flag, set()).update(leaf_set)
    for node in nodes:
        flags = {canonical_flag(k, OBJECT_FLAG_ALIASES): v for k, v in (node.get('flags') or {}).items()}
        for flag in OBJECT_FLAGS:
            if flags.get(flag):
                add(flag, node, node.get('leaf_ids') or ())
        if flags.get('assembly'):
            add('assembly', node, node.get('leaf_ids') or (), tag=flags['assembly'])
    for node in seated or ():
        add('seated', node, node.get('leaf_ids') or ())
    bodies = inventory['bodies']

    def full_partial(leaf_set):
        full, partial = set(), set()
        for b in bodies:
            covered = sum(1 for lid in b['leaf_ids'] if lid in leaf_set)
            if covered == 0:
                continue
            (full if covered >= len(b['leaf_ids']) else partial).add(b['id'])
        return full, partial
    union_by_flag = {}
    for flag, leaf_set in leaf_union_by_flag.items():
        full, partial = full_partial(leaf_set)
        union_by_flag[flag] = {'full': full, 'partial': partial, 'leaf_count': len(leaf_set),
                               'nodes': sum(1 for d in declarations if d['flag'] == flag)}
    union_by_sensor = {}
    for sensor, aliases in SENSOR_ALIASES.items():
        leaf_set = set()
        for a in aliases:
            leaf_set |= leaf_union_by_flag.get(a, set())
        if not leaf_set:
            continue
        full, partial = full_partial(leaf_set)
        union_by_sensor[sensor] = {'full': full, 'partial': partial, 'leaf_count': len(leaf_set)}
    assemblies = {}
    for d in declarations:
        if d['flag'] == 'assembly':
            assemblies.setdefault(d['tag'], set()).update(d['bodies'])
    return {'declarations': declarations, 'union_by_flag': union_by_flag, 'union_by_sensor': union_by_sensor,
            'assemblies': assemblies}


# ------------------------------------------------------------------------------------------ coverage records ---

def coverage_records(decl: dict, inventory: dict, policy: dict = None, missing_checks=(), systemic_frac=0.5) -> list:
    """Coverage -> ledger records, the SOURCE OF TRUTH: the digest is built from these, so no threshold can drop a
    declaration from persistence. The global disables of `policy` and the missing checks come first, as in the
    engine."""
    bodies = inventory['bodies']
    phys_ids = {b['id'] for b in inventory['physical_bodies']}
    by_id = {b['id']: b for b in bodies}
    n_phys = len(phys_ids) or 1
    n_b, n_p = len(bodies), len(phys_ids)
    recs = [{
        'check': 'coverage.inventory', 'outcome': 'PASS', 'class': 'INFO',
        'invariant': 'bodies are inferred from geometry and provenance, never grouping',
        'metrics': {'bodies': n_b, 'physical_bodies': n_p, 'leaves': len(inventory['leaves']),
                    'meshes': inventory['mesh_count'], 'non_physical': n_b - n_p},
        'message': (f"inventory: {n_b} canonical bodies ({len(inventory['leaves'])} leaves, {inventory['mesh_count']} "
                    f'objects; {n_b - n_p} hidden/degenerate excluded from coverage denominators)'),
    }]
    for note in inventory['notes']:
        recs.append({'check': 'coverage.inventory', 'outcome': 'SKIPPED', 'class': 'CORRECTNESS',
                     'message': note['message'] if isinstance(note, dict) else str(note)})
    for c in inventory['coalescence_declarations']:
        recs.append({'check': 'coverage.identity', 'outcome': 'WARN', 'disposition': 'DECLARED_EXCEPTION',
                     'class': 'REVIEW',
                     'message': (f"explicit body registration '{c['label']}' spans {c['islands']} disconnected islands "
                                 f"({c['leaf_count']} leaves): a registration labels evidence; it cannot merge what "
                                 'geometry does not join.')})
    if policy:
        recs += policy_records(policy)
    for name in missing_checks or ():
        recs.append({'check': name, 'outcome': 'SKIPPED', 'class': 'CORRECTNESS',
                     'message': f"check implementation '{name}' is missing: its obligations are UNOBSERVED."})
    # every object-flag declaration persists, regardless of scope
    for d in decl['declarations']:
        nb = len(d['bodies'])
        blanket = nb > 1
        ids = sorted(d['bodies'])
        labels = [by_id[i]['label'] for i in ids[:4] if i in by_id]
        tag = d.get('tag')
        msg = (f"{d['flag']}{f' {tag!r}' if tag else ''} @ '{d['source_label']}' covers {len(d['leaf_ids'])} "
               f"leaf/leaves across {nb} bod{'y' if nb == 1 else 'ies'}")
        if blanket:
            msg += (f" (GROUP-BLANKET: {', '.join(labels)}{', ...' if nb > 4 else ''}); one declaration covering many "
                    'bodies is a blanket exemption, not a decision')
        recs.append({'check': f"coverage.{d['flag']}", 'outcome': 'WARN' if blanket else 'PASS',
                     'disposition': 'DECLARED_EXCEPTION', 'class': 'CORRECTNESS' if blanket else 'REVIEW',
                     'bodies': ids, 'declarations': [d['flag'] + (f':{tag}' if tag else '')],
                     'metrics': {'leaves': len(d['leaf_ids']), 'bodies': nb}, 'message': msg + '.'})
    # per-sensor systemic coverage: escalation only changes emphasis; the exact fraction is always recorded
    for sensor, u in decl['union_by_sensor'].items():
        full = [i for i in u['full'] if i in phys_ids]
        part = [i for i in u['partial'] if i in phys_ids]
        frac = len(full) / n_phys
        systemic = frac >= systemic_frac
        recs.append({'check': f'coverage.sensor.{sensor}', 'outcome': 'WARN' if systemic else 'PASS',
                     'disposition': 'DECLARED_EXCEPTION', 'class': 'CORRECTNESS' if systemic else 'REVIEW',
                     'metrics': {'full_bodies': len(full), 'partial_bodies': len(part), 'physical_bodies': n_phys,
                                 'fraction': round(frac, 3), 'leaf_count': u['leaf_count']},
                     'message': (f"sensor '{sensor}': declarations (all aliases) fully cover {len(full)}/{n_phys} "
                                 f'physical bodies ({round(frac * 100)}%)' + (f' + {len(part)} partially' if part else '')
                                 + (': SYSTEMIC COVERAGE, mass opt-out defeats the audit; each exemption must be a '
                                    'per-part decision' if systemic else '') + '.')})
    # assembly tags: the exact pair scope they hide, no connectivity claims either way
    for tag, ids in decl['assemblies'].items():
        if len(ids) < 2:
            continue
        pairs = len(ids) * (len(ids) - 1) // 2
        recs.append({'check': 'coverage.assembly', 'outcome': 'WARN', 'disposition': 'DECLARED_EXCEPTION',
                     'class': 'REVIEW', 'declarations': [f'assembly:{tag}'],
                     'metrics': {'bodies': len(ids), 'hidden_pair_obligations': pairs},
                     'message': (f"assembly '{tag}' spans {len(ids)} canonical bodies: clipping exempts up to {pairs} "
                                 'internal pair obligation(s) under this tag. Whether these parts genuinely join is '
                                 'not measured.')})
    return recs


# ----------------------------------------------------------------------------------------------------- digest ---

def _fmt(d):
    return ' '.join(f'{k}:{v}' for k, v in d.items())


def digest_from_ledger(ledger: Ledger, runtime_lines=(), run_id='', status='') -> str:
    """The persisted digest, built FROM the ledger. Runtime console warnings are a separate section, not the source
    of truth."""
    recs = ledger.records
    s = [f'AUDIT DIGEST' + (f' - run {run_id}' if run_id else '') + (f' - status: {status}' if status else '')]
    sm = ledger.summarize()
    s.append(f"records: {sm['total']} | outcomes: {_fmt(sm['by_outcome'])} | dispositions: "
             f"{_fmt(sm['by_disposition'])} | clean: {str(ledger.is_clean()).lower()}")

    def section(title, keep):
        rows = [r for r in recs if keep(r)]
        if not rows:
            return
        s.append('')
        s.append(f'== {title} ({len(rows)})')
        for r in rows:
            s.append(f"  [{r['check']}] {r['outcome']}/{r['disposition']} - {r['message']}")

    section('warnings', lambda r: r['outcome'] == 'WARN')
    section('declared exceptions (non-warning)', lambda r: r['disposition'] == 'DECLARED_EXCEPTION' and r['outcome'] != 'WARN')
    section('skipped / unobserved', lambda r: r['outcome'] == 'SKIPPED')
    section('info', lambda r: r['outcome'] == 'PASS' and r['disposition'] == 'ENFORCED')
    if runtime_lines:
        s.append('')
        s.append(f'== runtime warnings (console) ({len(runtime_lines)})')
        for line in runtime_lines:
            s.append('  ' + str(line).split('\n')[0])
    s.append('')
    s.append('REVIEW GATE - the digest measures correctness, not quality. VIEW the probe frames (and the video, if '
             'anything moves) and judge the LOOK before reporting this render done.')
    return '\n'.join(s) + '\n'


def stamp() -> str:
    return _time.strftime('%Y-%m-%dT%H:%M:%S')
