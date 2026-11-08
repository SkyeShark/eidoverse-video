"""look/audit.py: the audit ledger for Blender scenes. audit_core.js ported: structured records, the scene inventory
(leaves and canonical bodies), declarations (an object's opt-outs) and their coverage, the persisted digest.

The invariant is the WebGPU one, OBSERVABILITY: every obligation is measured, replaced by a measurable contract, or
reported unknown. A declaration labels an outcome (DECLARED_EXCEPTION); it never erases geometry, and it is persisted
whatever its scope. Records are plain dicts, so any family's check can emit them without importing this module:
    {'check': 'framing', 'outcome': 'PASS'|'WARN'|'SKIPPED', 'disposition': 'ENFORCED'|'DECLARED_EXCEPTION'|...,
     'class': 'CORRECTNESS'|'REVIEW'|'INFO', 'metrics': {...}, 'message': '...'}

    from eidoblend.look import audit
    led = audit.Ledger()
    for r in camera_audit.camera_motion_audit(scene): led.record(r)
    inv = audit.build_inventory(scene)
    decl = audit.map_declarations(scene, inv)
    for r in audit.coverage_records(decl, inv, audit.snapshot_policy(scene)): led.record(r)
    led.write('out/film')            # out/film.audit.json + out/film.audit.txt (the digest)

Blender mapping: a leaf is one evaluated object's own geometry, or one instance of it (depsgraph.object_instances:
Geometry Nodes scatters and collection instances are virtual leaves). Declarations are object custom properties, in
snake_case (allow_intersect, no_clipping_check, ...; assembly = '<tag>'), inherited by children. Policy flags (the
WebGPU globals) are scene custom properties: no_auto_placement_check, no_motion_check, ... Provenance (what may merge
into one body) is the 'src_asset' custom property up the parent chain.
"""
import json
import os

import bpy
from mathutils import Vector

OUTCOMES = ('PASS', 'WARN', 'SKIPPED')
DISPOSITIONS = ('ENFORCED', 'DECLARED_EXCEPTION', 'CONTRACT_VALIDATED')
CLASSES = ('CORRECTNESS', 'REVIEW', 'INFO')
GLOBAL_FLAGS = ('no_auto_placement_check', 'no_motion_check', 'no_locomotion_check', 'allow_manual_locomotion',
                'no_opacity_check', 'auto_fix_placement')
OBJECT_FLAGS = ('allow_intersect', 'no_clipping_check', 'no_support_check', 'sunk_placement', 'no_motion_check',
                'no_intrusion_check', 'no_z_fight_check', 'no_facing_check')
SENSOR_ALIASES = {
    'clipping': ('allow_intersect', 'no_clipping_check', 'assembly'),
    'support': ('no_support_check', 'sunk_placement', 'seated'),
    'motion': ('no_motion_check',),
    'facing': ('no_facing_check',),
    'zfight': ('no_z_fight_check',),
    'intrusion': ('no_intrusion_check',),
}


# ---------------------------------------------------------------------------------------------------------- ledger
class Ledger:
    def __init__(self):
        self._records = []

    def record(self, entry):
        """Normalise and keep one record (unknown outcomes become SKIPPED, as in audit_core.js)."""
        r = {
            'check': str(entry.get('check', 'unknown')),
            'outcome': entry.get('outcome') if entry.get('outcome') in OUTCOMES else 'SKIPPED',
            'disposition': entry.get('disposition') if entry.get('disposition') in DISPOSITIONS else 'ENFORCED',
            'class': entry.get('class') if entry.get('class') in CLASSES else 'CORRECTNESS',
            'confidence': float(entry.get('confidence', 1.0)),
            'bodies': [str(b) for b in entry.get('bodies', [])],
            'invariant': str(entry.get('invariant', '')),
            'metrics': json.loads(json.dumps(entry.get('metrics', {}), default=str)),
            'declarations': [str(d) for d in entry.get('declarations', [])],
            'message': str(entry.get('message', '')),
            'time': entry.get('time'),
        }
        self._records.append(r)
        return r

    @property
    def records(self):
        return list(self._records)

    def summarize(self):
        def by(k):
            out = {}
            for r in self._records:
                out[r[k]] = out.get(r[k], 0) + 1
            return out
        return {'total': len(self._records), 'by_outcome': by('outcome'), 'by_disposition': by('disposition'),
                'by_class': by('class')}

    def is_clean(self):
        """Nothing warned, nothing was declared away, nothing material was skipped."""
        return not any(r['outcome'] == 'WARN' or r['disposition'] == 'DECLARED_EXCEPTION'
                       or (r['outcome'] == 'SKIPPED' and r['class'] == 'CORRECTNESS') for r in self._records)

    def to_json(self):
        return {'summary': self.summarize(), 'clean': self.is_clean(), 'records': self._records}

    def write(self, base, runtime_lines=(), meta=None):
        """<base>.audit.json and <base>.audit.txt (the digest)."""
        os.makedirs(os.path.dirname(os.path.abspath(base)), exist_ok=True)
        with open(base + '.audit.json', 'w', encoding='utf-8') as fh:
            json.dump(self.to_json(), fh, indent=1)
        with open(base + '.audit.txt', 'w', encoding='utf-8') as fh:
            fh.write(digest_from_ledger(self, runtime_lines, meta or {}))
        return base + '.audit.json', base + '.audit.txt'


def create_ledger():
    return Ledger()


def snapshot_policy(scene):
    """One capture of the scene's policy flags (scene custom properties), with the truthiness the gates use."""
    flags, non_bool = {}, {}
    for f in GLOBAL_FLAGS:
        v = scene.get(f)
        flags[f] = bool(v)
        if v is not None and not isinstance(v, bool):
            non_bool[f] = type(v).__name__
    return {'flags': flags, 'non_boolean': non_bool}


# ---------------------------------------------------------------------------------------------------------- inventory
def _name_chain(o):
    p = o
    while p is not None:
        if p.name:
            return p.name
        p = p.parent
    return '(unnamed)'


def _provenance(o):
    p = o
    while p is not None:
        if 'src_asset' in p:
            return str(p['src_asset'])
        p = p.parent
    return None


def _median(a):
    if not a:
        return 0.0
    s = sorted(a)
    return s[(len(s) - 1) // 2]


def _overlap_fraction(a, b):
    """Per-axis overlap fractions multiplied (never raw world volumes)."""
    frac = 1.0
    for ax in range(3):
        lo = max(a[0][ax], b[0][ax])
        hi = min(a[1][ax], b[1][ax])
        if hi <= lo:
            return 0.0
        m = min(a[1][ax] - a[0][ax], b[1][ax] - b[0][ax])
        frac *= min(1.0, (hi - lo) / m) if m > 0 else 1.0
    return frac


def build_inventory(scene, depsgraph=None, embed_frac=0.25, provenance_of=None, explicit_bodies=None,
                    max_instances=20000):
    """Leaves (one per evaluated geometry object or instance) merged into canonical bodies on embedding evidence
    WITHIN a shared provenance only. Returns dict(bodies, leaves, leaf_to_body, object_leaf_ids, physical_bodies,
    notes, coalescence_declarations, mesh_count)."""
    embed_frac = min(0.95, max(0.05, float(embed_frac)))
    prov_of = provenance_of or _provenance
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    leaves, notes = [], []
    n_inst = 0
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type not in ('MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'CURVES', 'POINTCLOUD', 'VOLUME'):
            continue
        orig = ob.original
        if inst.is_instance:
            n_inst += 1
            if n_inst > max_instances:
                continue
        bb = ob.bound_box
        mw = inst.matrix_world.copy()
        cs = [mw @ Vector(c) for c in bb]
        lo = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
        hi = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
        if not all(map(lambda v: v == v and abs(v) < 1e12, list(lo) + list(hi))):
            notes.append({'kind': 'SKIPPED', 'message': f"'{orig.name}' has non-finite bounds: UNAUDITED."})
            continue
        lx = [abs(bb[6][i] - bb[0][i]) for i in range(3)]
        scl = mw.to_scale()
        dims = [lx[i] * abs(scl[i]) for i in range(3)]
        nz = sorted(d for d in dims if d > 0)
        cond = 'overflow' if any(d > 1e12 for d in dims) else ('degenerate' if not nz else ('planar' if len(nz) < 3 else 'ok'))
        tris = 0
        if ob.type == 'MESH' and ob.data is not None:
            tris = sum(max(0, p.loop_total - 2) for p in ob.data.polygons) if len(ob.data.polygons) < 200000 else len(ob.data.polygons) * 2
        parent = inst.parent.original if inst.is_instance and inst.parent else None
        lid = f'{orig.name}#{inst.persistent_id[0]}' if inst.is_instance else orig.name
        leaves.append({
            'id': lid, 'label': _name_chain(orig) if not parent else f'{parent.name}/{orig.name}',
            'box': (lo, hi), 'dims': dims, 'L': nz[(len(nz) - 1) // 2] if nz else 0.0,
            'R': (sum(d * d for d in dims) ** 0.5) / 2 if nz else 0.0, 'tri_count': tris, 'conditioning': cond,
            'visible': not orig.hide_render, 'deforming': any(m.type in ('ARMATURE', 'CLOTH', 'SOFT_BODY') for m in orig.modifiers),
            'provenance': prov_of(orig) if not inst.is_instance else (prov_of(parent) if parent else None),
            'object': orig.name, 'instancer': parent.name if parent else None,
        })
    if n_inst > max_instances:
        notes.append({'kind': 'SKIPPED', 'message': f'{n_inst - max_instances} instances beyond max_instances '
                                                     f'({max_instances}) are UNAUDITED, not passed.'})
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
    for i, l in enumerate(leaves):
        if l['provenance']:
            by_prov.setdefault(l['provenance'], []).append(i)
    for idxs in by_prov.values():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                if _overlap_fraction(leaves[idxs[a]]['box'], leaves[idxs[b]]['box']) >= embed_frac:
                    union(idxs[a], idxs[b])
    coalescence = []
    for root in explicit_bodies or ():
        names = {o.name for o in [root] + list(root.children_recursive)}
        members = [i for i, l in enumerate(leaves) if l['object'] in names]
        if len(members) > 1 and len({find(i) for i in members}) > 1:
            coalescence.append({'label': root.name, 'leaf_count': len(members), 'islands': len({find(i) for i in members})})
    groups = {}
    for i, l in enumerate(leaves):
        groups.setdefault(find(i), []).append(l)
    bodies = []
    for n, members in enumerate(groups.values()):
        lo = Vector((min(m['box'][0].x for m in members), min(m['box'][0].y for m in members), min(m['box'][0].z for m in members)))
        hi = Vector((max(m['box'][1].x for m in members), max(m['box'][1].y for m in members), max(m['box'][1].z for m in members)))
        vis = any(m['visible'] for m in members)
        tri = sum(m['tri_count'] for m in members)
        cond = 'overflow' if any(m['conditioning'] == 'overflow' for m in members) else (
            'degenerate' if all(m['conditioning'] == 'degenerate' for m in members) else 'ok')
        bodies.append({'id': f'body_{n}', 'label': members[0]['label'], 'leaf_ids': [m['id'] for m in members],
                       'box': (lo, hi), 'L': _median([m['L'] for m in members if m['L'] > 0]),
                       'R': max(m['R'] for m in members), 'tri_count': tri, 'visible': vis,
                       'deforming': any(m['deforming'] for m in members), 'conditioning': cond,
                       'provenance': members[0]['provenance'],
                       'physical': vis and tri > 0 and cond == 'ok'})
    leaf_to_body = {lid: b for b in bodies for lid in b['leaf_ids']}
    obj_leaves = {}
    for l in leaves:
        obj_leaves.setdefault(l['object'], []).append(l['id'])
        if l['instancer']:
            obj_leaves.setdefault(l['instancer'], []).append(l['id'])
    return {'bodies': bodies, 'leaves': leaves, 'leaf_to_body': leaf_to_body, 'object_leaf_ids': obj_leaves,
            'physical_bodies': [b for b in bodies if b['physical']], 'notes': notes,
            'coalescence_declarations': coalescence, 'mesh_count': len({l['object'] for l in leaves})}


# ---------------------------------------------------------------------------------------------------------- declarations
def map_declarations(scene, inventory, seated_objects=()):
    """Every object custom property in OBJECT_FLAGS (and 'assembly') as a declaration over its leaves and its
    children's; leaf unions per flag and per sensor (aliases union)."""
    decls, leaf_union = [], {}

    def leaves_under(o):
        s = set()
        for d in [o] + list(o.children_recursive):
            s.update(inventory['object_leaf_ids'].get(d.name, []))
        return s

    def add(flag, o, leafset, tag=None):
        if not leafset:
            return
        bodies = {inventory['leaf_to_body'][lid]['id'] for lid in leafset if lid in inventory['leaf_to_body']}
        decls.append({'flag': flag, 'tag': tag, 'source': o.name, 'leaf_ids': leafset, 'bodies': bodies})
        leaf_union.setdefault(flag, set()).update(leafset)

    for o in scene.objects:
        for flag in OBJECT_FLAGS:
            if o.get(flag):
                add(flag, o, leaves_under(o))
        if o.get('assembly'):
            add('assembly', o, leaves_under(o), tag=str(o['assembly']))
    for o in seated_objects:
        add('seated', o, leaves_under(o))

    def cover(leafset):
        full, part = set(), set()
        for b in inventory['bodies']:
            c = sum(1 for lid in b['leaf_ids'] if lid in leafset)
            if c:
                (full if c >= len(b['leaf_ids']) else part).add(b['id'])
        return full, part
    by_flag = {}
    for flag, ls in leaf_union.items():
        f, p = cover(ls)
        by_flag[flag] = {'full': f, 'partial': p, 'leaf_count': len(ls)}
    by_sensor = {}
    for sensor, aliases in SENSOR_ALIASES.items():
        ls = set()
        for a in aliases:
            ls |= leaf_union.get(a, set())
        if ls:
            f, p = cover(ls)
            by_sensor[sensor] = {'full': f, 'partial': p, 'leaf_count': len(ls)}
    assemblies = {}
    for d in decls:
        if d['flag'] == 'assembly':
            assemblies.setdefault(d['tag'], set()).update(d['bodies'])
    return {'declarations': decls, 'by_flag': by_flag, 'by_sensor': by_sensor, 'assemblies': assemblies}


def coverage_records(decl, inventory, policy, missing_checks=(), systemic_frac=0.5):
    """Ledger records for the inventory, every declaration, global disables and per-sensor coverage (the source of
    truth: the digest is built from these, so no threshold drops a declaration)."""
    phys = {b['id'] for b in inventory['physical_bodies']}
    n_phys = len(phys) or 1
    recs = [{'check': 'coverage.inventory', 'outcome': 'PASS', 'class': 'INFO',
             'invariant': 'bodies are inferred from geometry and provenance, never grouping',
             'metrics': {'bodies': len(inventory['bodies']), 'physical_bodies': len(phys),
                         'leaves': len(inventory['leaves']), 'meshes': inventory['mesh_count']},
             'message': f"inventory: {len(inventory['bodies'])} canonical bodies ({len(inventory['leaves'])} leaves, "
                        f"{inventory['mesh_count']} objects; {len(inventory['bodies']) - len(phys)} hidden/degenerate "
                        f"excluded from coverage denominators)"}]
    for note in inventory['notes']:
        recs.append({'check': 'coverage.inventory', 'outcome': 'SKIPPED', 'class': 'CORRECTNESS', 'message': note['message']})
    for c in inventory['coalescence_declarations']:
        recs.append({'check': 'coverage.identity', 'outcome': 'WARN', 'disposition': 'DECLARED_EXCEPTION', 'class': 'REVIEW',
                     'message': f"explicit body registration '{c['label']}' spans {c['islands']} disconnected islands "
                                f"({c['leaf_count']} leaves): a registration labels evidence; it cannot merge what "
                                f"geometry does not join."})
    gated = {'no_auto_placement_check': ('clipping', 'support', 'zfight', 'facing', 'density', 'intrusion'),
             'no_motion_check': ('motion.envelope',), 'no_locomotion_check': ('motion.locomotion',),
             'allow_manual_locomotion': ('motion.locomotion.disposition',), 'no_opacity_check': ('opacity',)}
    for flag, checks in gated.items():
        if not policy['flags'].get(flag):
            continue
        nb = f" (non-boolean {policy['non_boolean'][flag]} value: treated as truthy)" if flag in policy['non_boolean'] else ''
        for c in checks:
            recs.append({'check': c, 'outcome': 'SKIPPED', 'disposition': 'DECLARED_EXCEPTION', 'class': 'CORRECTNESS',
                         'declarations': [flag],
                         'message': (f'{flag}=true{nb}: locomotion findings are sampled but their disposition is suppressed.'
                                     if flag == 'allow_manual_locomotion' else
                                     f"GLOBAL DISABLE {flag}=true{nb}: '{c}' DID NOT RUN. Every obligation it covers is "
                                     f"UNOBSERVED, not passed.")})
    for flag, t in policy['non_boolean'].items():
        if not policy['flags'].get(flag):
            recs.append({'check': 'coverage.policy', 'outcome': 'WARN', 'class': 'REVIEW',
                         'message': f'{flag} holds a non-boolean {t} that is falsy: confirm this is intentional.'})
    for name in missing_checks:
        recs.append({'check': name, 'outcome': 'SKIPPED', 'class': 'CORRECTNESS',
                     'message': f"check implementation '{name}' is missing: its obligations are UNOBSERVED."})
    for d in decl['declarations']:
        blanket = len(d['bodies']) > 1
        recs.append({'check': f"coverage.{d['flag']}", 'outcome': 'WARN' if blanket else 'PASS',
                     'disposition': 'DECLARED_EXCEPTION', 'class': 'CORRECTNESS' if blanket else 'REVIEW',
                     'bodies': sorted(d['bodies']), 'declarations': [d['flag'] + (f":{d['tag']}" if d['tag'] else '')],
                     'metrics': {'leaves': len(d['leaf_ids']), 'bodies': len(d['bodies'])},
                     'message': f"{d['flag']}{' ' + repr(d['tag']) if d['tag'] else ''} @ '{d['source']}' covers "
                                f"{len(d['leaf_ids'])} leaves across {len(d['bodies'])} bodies"
                                + (': GROUP-BLANKET; one declaration covering many bodies is a blanket exemption, not '
                                   'a decision.' if blanket else '.')})
    for sensor, u in decl['by_sensor'].items():
        full = len(u['full'] & phys)
        part = len(u['partial'] & phys)
        frac = full / n_phys
        recs.append({'check': f'coverage.sensor.{sensor}', 'outcome': 'WARN' if frac >= systemic_frac else 'PASS',
                     'disposition': 'DECLARED_EXCEPTION', 'class': 'CORRECTNESS' if frac >= systemic_frac else 'REVIEW',
                     'metrics': {'full_bodies': full, 'partial_bodies': part, 'physical_bodies': n_phys,
                                 'fraction': round(frac, 3), 'leaf_count': u['leaf_count']},
                     'message': f"sensor '{sensor}': declarations fully cover {full}/{n_phys} physical bodies "
                                f"({round(frac * 100)}%)" + (f' + {part} partially' if part else '')
                                + (': SYSTEMIC COVERAGE; mass opt-out defeats the audit.' if frac >= systemic_frac else '.')})
    for tag, bodies in decl['assemblies'].items():
        nb = len(bodies)
        if nb >= 2:
            recs.append({'check': 'coverage.assembly', 'outcome': 'WARN', 'disposition': 'DECLARED_EXCEPTION',
                         'class': 'REVIEW', 'declarations': [f'assembly:{tag}'],
                         'metrics': {'bodies': nb, 'hidden_pair_obligations': nb * (nb - 1) // 2},
                         'message': f"assembly '{tag}' spans {nb} canonical bodies: clipping exempts up to "
                                    f"{nb * (nb - 1) // 2} internal pair obligation(s) under this tag."})
    return recs


def digest_from_ledger(ledger, runtime_lines=(), meta=None):
    """The persisted text digest, built from the ledger's records (the console is a separate section)."""
    meta = meta or {}
    recs = ledger.records
    s = [f"AUDIT DIGEST{(' -- run ' + meta['run_id']) if meta.get('run_id') else ''}"
         f"{(' -- status: ' + meta['status']) if meta.get('status') else ''}"]
    sm = ledger.summarize()
    fmt = lambda o: ' '.join(f'{k}:{v}' for k, v in o.items())
    s.append(f"records: {sm['total']} | outcomes: {fmt(sm['by_outcome'])} | dispositions: {fmt(sm['by_disposition'])} "
             f"| clean: {ledger.is_clean()}")

    def section(title, keep):
        rows = [r for r in recs if keep(r)]
        if rows:
            s.append('')
            s.append(f'== {title} ({len(rows)})')
            s.extend(f"  [{r['check']}] {r['outcome']}/{r['disposition']} -- {r['message']}" for r in rows)
    section('warnings', lambda r: r['outcome'] == 'WARN')
    section('declared exceptions (non-warning)', lambda r: r['disposition'] == 'DECLARED_EXCEPTION' and r['outcome'] != 'WARN')
    section('skipped / unobserved', lambda r: r['outcome'] == 'SKIPPED')
    section('info', lambda r: r['outcome'] == 'PASS' and r['disposition'] == 'ENFORCED')
    if runtime_lines:
        s += ['', f'== runtime warnings (console) ({len(runtime_lines)})'] + ['  ' + l.split('\n')[0] for l in runtime_lines]
    s += ['', 'REVIEW GATE: the digest measures correctness, not quality. VIEW the probe stills (and the video, if '
              'anything moves) and judge the LOOK before reporting this render done.']
    return '\n'.join(s) + '\n'
