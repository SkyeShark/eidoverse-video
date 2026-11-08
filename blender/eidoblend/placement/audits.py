"""The placement audits, ported from eidoverse/scene_placement.js: run after a scene is built,
before it renders (run_placement_audits is the hook the harness calls).

They work on whole PLACED objects (parentless, not cameras or lights; through a lone wrapper), so a
multi-part desk is one thing. Warnings are observations to look at in the probe frames; resting
contact is construction, not a defect. Declarations (object custom properties):
  no_support_check   a deliberate flyer (drone, lamp, bird)       allow_intersect  overlap is meant
  no_clipping_check  leave this subtree out of every check         assembly         parts of one machine
  no_z_fight_check   an intentional flush decal                    no_facing_check  a panel's overlap is meant
  no_intrusion_check a deliberate crushed-by-the-line gag          eido_seated      a seated character
  _sunk_placement / _support_targets: written by place_on / snap_to_ground / scatter_on.
Scene flags (scene custom properties): eido_auto_fix_placement (run the repair pass first),
eido_no_auto_placement_check (skip the audits).
"""
import re

import bpy
from mathutils import Vector

from . import _world as W
from .helpers import support_under_footprint

_AXES = (Vector((1, 0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, -1, 0)),
         Vector((0, 0, 1)), Vector((0, 0, -1)))
SEATED_GAP = 0.06          # m: an object this close above its recorded support's real surface is seated on it
_LINE_RE = re.compile(r'conveyor|belt|assembly.?line|production.?line|treadmill|escalator', re.I)


def _p(tag, msg):
    print('[%s] %s' % (tag, msg))


def _seated(o):
    return W.flag(o, 'eido_seated')


def _pairs(E, tol, exhaustive):
    """(i, j), i < j, in the engine's all-pairs order. Without a repair pass (the audits the runner runs on every
    build) only pairs whose x ranges come within `tol` are visited (a sweep along x: every check here needs that
    much contact, so nothing is lost and a scene of thousands of pieces stays fast). The repair pass moves objects
    as it goes, so it keeps the engine's full loop."""
    n = len(E)
    if exhaustive:
        for i in range(n):
            for j in range(i + 1, n):
                yield i, j
        return
    order = sorted(range(n), key=lambda k: E[k]['box'][0].x)
    out = []
    for a in range(n):
        ia = order[a]
        reach = E[ia]['box'][1].x + tol
        for b in range(a + 1, n):
            ib = order[b]
            if E[ib]['box'][0].x > reach:
                break
            out.append((ia, ib) if ia < ib else (ib, ia))
    out.sort()
    yield from out


def _supported_by(root, other_root, other_mesh):
    for s in W.support_targets(root):
        if s == other_root or W.is_ancestor(s, other_mesh) or W.is_ancestor(other_mesh, s):
            return True
    return False


def check_clipping(scene=None, auto_fix=False, exclude=(), max_fix_iters=3):
    """Pairs of placed objects whose bounds intersect (data, mostly resting contact), plus a mesh-
    accurate DEEP-interpenetration pass that names any object substantially INSIDE another (>=18% of
    its sampled points enclosed: >=5 of 6 axis rays hit the other). auto_fix pushes apart only
    substantial overlaps (never ground-scale geometry, never two seated objects). Returns the pairs."""
    scene = scene or bpy.context.scene
    W.update()
    dg = W.depsgraph()
    roots = W.placed_roots(scene)
    root_set = set(roots)
    meshes = []
    for r in roots:
        meshes += W.collect(r, exclude)
    E = [{'m': m, 'box': W.box_of_object(m, dg), 'root': W.root_of(m, root_set)} for m in meshes]
    report, moved = [], 0
    for i, j in _pairs(E, 0.0, auto_fix):
        a, b = E[i], E[j]
        if a['root'] == b['root'] or _seated(a['root']) or _seated(b['root']):
            continue
        if _supported_by(a['root'], b['root'], b['m']) or _supported_by(b['root'], a['root'], a['m']):
            continue
        if W.is_ancestor(a['m'], b['m']) or W.is_ancestor(b['m'], a['m']):
            continue
        if not W.boxes_intersect(a['box'], b['box']):
            continue
        report.append({'a': a['m'], 'b': b['m'], 'ar': a['root'], 'br': b['root']})
        if not auto_fix:
            continue
        ov = W.box_overlap(a['box'], b['box'])
        thin = lambda e: min(W.box_size(e['box']))
        band = min(0.04, max(0.008, 0.3 * min(thin(a), thin(b))))
        if min(ov) < band:
            continue                                       # touch / rest, not clipping
        allow = lambda o: W.flag(o, 'allow_intersect')
        if allow(a['root']) or allow(b['root']) or allow(a['m']) or allow(b['m']):
            continue
        span = lambda e: max(e['box'][1].x - e['box'][0].x, e['box'][1].y - e['box'][0].y)
        ag, bg = span(a) > 20, span(b) > 20
        if ag and bg:
            continue
        a_seat = bool(W.support_targets(a['root']))
        b_seat = bool(W.support_targets(b['root']))
        mover = b['root']
        if ag:
            mover = b['root']
        elif bg:
            mover = a['root']
        elif b_seat and not a_seat:
            mover = a['root']
        elif b_seat and a_seat:
            continue
        moved += 1
        for _ in range(max_fix_iters):
            a['box'] = W.box_of_object(a['m'], W.depsgraph())
            b['box'] = W.box_of_object(b['m'], W.depsgraph())
            if not W.boxes_intersect(a['box'], b['box']):
                break
            ov = W.box_overlap(a['box'], b['box'])
            ax = min(range(3), key=lambda k: ov[k])
            ca = a['box'][0][ax] + a['box'][1][ax]
            cb = b['box'][0][ax] + b['box'][1][ax]
            sgn = 1 if cb > ca else -1
            if mover == a['root']:
                sgn = -sgn
            d = Vector((0, 0, 0))
            d[ax] = ov[ax] * sgn * 0.55
            W.move_world(mover, d)
    if report:
        _p('check_clipping', 'measured %d contact/overlap pair(s): this is data, not defects: parts that '
           'join are SUPPOSED to touch (a brace in its socket, a rail on its post). Nothing here asks for '
           'action; the probe frames judge whether any pair looks wrong.%s'
           % (len(report), (' Separated %d.' % moved) if auto_fix else ''))
        for p in report[:10]:
            print('  %s <=> %s' % (W.name_of(p['ar'] or p['a']), W.name_of(p['br'] or p['b'])))
        if len(report) > 10:
            print('  ...and %d more' % (len(report) - 10))
    deep = _deep_interpenetration(report)
    for r in report:
        r['deep'] = any((d['small'], d['big']) in ((r['ar'], r['br']), (r['br'], r['ar'])) for d in deep)
    return report


def _deep_interpenetration(report):
    W.update()
    dg = W.depsgraph()
    seen, deep = set(), []
    for p in report:
        ra, rb = p['ar'] or p['a'], p['br'] or p['b']
        if ra == rb:
            continue
        key = tuple(sorted((ra.name, rb.name)))
        if key in seen:
            continue
        seen.add(key)
        opt_out = lambda r: W.flag(r, 'allow_intersect') or W.flag(r, 'no_clipping_check')
        if opt_out(ra) or opt_out(rb):
            continue
        if ra.get('assembly') and ra.get('assembly') == rb.get('assembly'):
            continue
        ba, bb = W.tight_box(ra, dg=dg), W.tight_box(rb, dg=dg)
        ov = W.box_overlap(ba, bb)
        if min(ov) <= 0:
            continue
        small_a = W.box_volume(ba) <= W.box_volume(bb)
        small, big = (ra, rb) if small_a else (rb, ra)
        sbox, bbox = (ba, bb) if small_a else (bb, ba)
        if (ov.x * ov.y * ov.z) / W.box_volume(sbox) < 0.12:
            continue
        sm, bm = W.collect(small), W.collect(big)
        if not sm or not bm:
            continue
        cap = 36
        pts = []
        for m in sm:
            co = W.world_verts(m, dg)
            stride = max(1, len(co) // max(1, -(-cap // len(sm))))
            for v in co[::stride]:
                if (bbox[0].x <= v[0] <= bbox[1].x and bbox[0].y <= v[1] <= bbox[1].y
                        and bbox[0].z <= v[2] <= bbox[1].z):
                    pts.append(Vector(v))
                    if len(pts) >= cap:
                        break
            if len(pts) >= cap:
                break
        if len(pts) < 4:
            continue
        far = W.box_size(bbox).length
        rays = W.Rays(bm, dg)
        enclosed = sum(1 for pt in pts if sum(1 for d in _AXES if rays.cast(pt, d, far)) >= 5)
        frac = enclosed / len(pts)
        if frac >= 0.18:
            deep.append({'small': small, 'big': big, 'frac': frac})
    if deep:
        deep.sort(key=lambda d: -d['frac'])
        _p('check_clipping', '⚠ %d object(s) substantially INSIDE another. If they are INDEPENDENT things '
           '(a tree in a car), move the smaller one clear (find_clear_spot helps). If the pair is PARTS OF ONE '
           "MACHINE joined by a weld or socket, that embedding is correct construction: parent the machine "
           "under one root or set obj['assembly'] = '<machine>' on both. Never fix a real joint with an air gap:"
           % len(deep))
        for d in deep:
            print('  %s is ~%d%% inside %s' % (d['small'].name, round(d['frac'] * 100), d['big'].name))
    return deep


def _falls_by_physics(root):
    """An active (dynamic, not animated) rigid body in root's subtree: its rest is where the simulation drops it,
    so where it starts is no placement (the engine had no rigid-body simulation to ask about)."""
    for o in [root] + list(root.children_recursive):
        rb = getattr(o, 'rigid_body', None)
        if rb is not None and rb.enabled and rb.type == 'ACTIVE' and not rb.kinematic:
            return True
    return False


def _transparent_only(root):
    mats = []
    for m in W.collect(root):
        mats += [s.material for s in m.material_slots if s.material]
    if not mats:
        return False
    return all(getattr(mt, 'surface_render_method', '') == 'BLENDED' for mt in mats)


def check_hovering(scene=None, min_gap=0.005, max_gap=1.0, auto_fix=False, exclude=()):
    """Placed objects with no support below: near (a min_gap..max_gap seat gap: measured, often
    invisible), far (> max_gap above the nearest surface) or void (nothing beneath at all). Skips
    objects at ground level, sunk placements, declared flyers (no_support_check), seated characters,
    all-BLENDED (glow) objects, and objects verified on their recorded support. auto_fix snaps only
    'near' gaps down. Returns [{'obj', 'gap', 'kind'}]."""
    scene = scene or bpy.context.scene
    W.update()
    dg = W.depsgraph()
    roots = W.placed_roots(scene, exclude)
    all_meshes = []
    for r in W.placed_roots(scene):
        all_meshes += W.collect(r)
    boxes = {m: W.box_of_object(m, dg) for m in all_meshes}
    # ground level = the lowest surface, not counting things deliberately sunk INTO the ground (a rock buried in the
    # lowest hollow would otherwise lift "ground" under the terrain itself), nor seated characters (a sitter's tail,
    # cloth or a folded leg the clip leaves through the floor would drop "ground" below the floor, and the floor
    # and everything standing on it would read as floating)
    root_set = set(W.placed_roots(scene))
    ground = min((b[0].z for m, b in boxes.items() if not W.flag(W.root_of(m, root_set), '_sunk_placement')
                  and not _seated(W.root_of(m, root_set))), default=0.0)
    report = []
    simulated = []
    for root in roots:
        if W.flag(root, 'no_support_check') or W.flag(root, '_sunk_placement') or _seated(root):
            continue
        if W.flag(root, 'trimesh_collider'):
            continue                                       # the ground itself (make_terrain)
        if _falls_by_physics(root):
            simulated.append(root)                         # gravity places it: judge it in motion, not at frame 1
            continue
        sups = W.support_targets(root)
        if sups:
            s_meshes = W.collect(sups)
            if s_meshes:
                rb = W.tight_box(root, dg=dg)
                rc = W.box_center(rb)
                s2 = support_under_footprint(root, W.Rays(s_meshes, dg), rc.x, rc.y, rb[0].z + 0.01, 11, box=rb)
                if s2 and rb[0].z - s2[0] < SEATED_GAP:
                    continue
                # the rays can slip between thin geometry (a wire rack, slats): the support's real surface
                # under the footprint settles it. (The engine fell back to the support's BOX top here, which
                # also counted a stool whose seat had moved away while its splayed legs still reached under
                # the clock that sat on it.)
                top = W.surface_top_in_footprint(s_meshes, rb, rb[0].z + 0.01, dg)
                if top is not None and rb[0].z - top < SEATED_GAP:
                    continue
        if not W.collect(root):
            continue
        box = W.tight_box(root, dg=dg)
        c = W.box_center(box)
        bz = box[0].z
        if bz <= ground + 0.05:
            continue
        others = [m for m in all_meshes if not W.is_ancestor(root, m)
                  and boxes[m][1].x >= box[0].x and boxes[m][0].x <= box[1].x
                  and boxes[m][1].y >= box[0].y and boxes[m][0].y <= box[1].y
                  and boxes[m][0].z <= bz + 0.01]
        if _transparent_only(root):
            continue
        sup = support_under_footprint(root, W.Rays(others, dg), c.x, c.y, bz + 0.01, 9, box=box) if others else None
        if not sup:
            kind, gap = 'void', 0.0
        else:
            gap = bz - sup[0]
            if gap < min_gap:
                continue
            kind = 'far' if gap > max_gap else 'near'
        report.append({'obj': root, 'gap': gap, 'kind': kind})
        if auto_fix and kind == 'near':
            W.move_world(root, (0, 0, -gap))
    if simulated:
        _p('check_hovering', '%d object(s) under rigid-body simulation are left to physics (they fall and settle '
           'in the baked cache; look at them in motion): %s' % (len(simulated), ', '.join(o.name for o in simulated[:6])))
    near = [r for r in report if r['kind'] == 'near']
    hard = [r for r in report if r['kind'] != 'near']
    if near:
        _p('check_hovering', '%s %d small seating gap(s): usually fine and often invisible on camera; '
           'place_on(obj, surface) seats a piece flush if you want it exact. No action implied:'
           % ('auto-seated' if auto_fix else 'measured', len(near)))
        for r in near[:6]:
            print('  %s: %.3fm above its surface (small)' % (r['obj'].name, r['gap']))
    if hard:
        _p('check_hovering', '%d object(s) have no real support; these will read as floating on camera:' % len(hard))
        for r in hard[:10]:
            if r['kind'] == 'void':
                print('  %s: nothing beneath its footprint at all (place_on(obj, surface) says what it sits on)' % r['obj'].name)
            else:
                print('  %s: %.2fm above the nearest surface (a real gap, not a seating tolerance)' % (r['obj'].name, r['gap']))
        if len(hard) > 10:
            print('  ...and %d more' % (len(hard) - 10))
        print("  (a deliberate flyer (drone, lamp, orb, bird) declares itself with obj['no_support_check'] = True)")
    return report


def check_z_fighting(scene=None, auto_fix=False, exclude=(), eps=0.002, thin=0.06, push=0.004, min_overlap=0.02):
    """A THIN object (extent < `thin` on an axis: a panel, decal, quad) whose face is coplanar within
    eps with another placed object's face and overlaps it on the other two axes. EEVEE z-fights too.
    auto_fix nudges the thin one `push` away. Opt out: obj['no_z_fight_check']. Returns the pairs."""
    scene = scene or bpy.context.scene
    W.update()
    dg = W.depsgraph()
    roots = W.placed_roots(scene)
    root_set = set(roots)
    meshes = []
    for r in roots:
        meshes += [m for m in W.collect(r, exclude) if not W.flag(m, 'no_z_fight_check')]
    E = []
    for m in meshes:
        b = W.box_of_object(m, dg)
        E.append({'m': m, 'box': b, 'root': W.root_of(m, root_set), 'size': W.box_size(b)})
    report = []
    for i, j in _pairs(E, eps, auto_fix):
        a, b = E[i], E[j]
        if a['root'] == b['root'] or W.is_ancestor(a['m'], b['m']) or W.is_ancestor(b['m'], a['m']):
            continue
        for ax in range(3):
            o1, o2 = (ax + 1) % 3, (ax + 2) % 3
            ov1 = min(a['box'][1][o1], b['box'][1][o1]) - max(a['box'][0][o1], b['box'][0][o1])
            ov2 = min(a['box'][1][o2], b['box'][1][o2]) - max(a['box'][0][o2], b['box'][0][o2])
            if ov1 < min_overlap or ov2 < min_overlap:
                continue
            A0, A1, B0, B1 = a['box'][0][ax], a['box'][1][ax], b['box'][0][ax], b['box'][1][ax]
            if not any(abs(p - q) < eps for p, q in ((A0, B0), (A1, B1), (A1, B0), (A0, B1))):
                continue
            ta, tb = a['size'][ax] < thin, b['size'][ax] < thin
            if not ta and not tb:
                continue
            report.append({'a': a['m'], 'b': b['m'], 'axis': 'xyz'[ax]})
            if auto_fix:
                te = a if (ta and (not tb or a['size'][ax] <= b['size'][ax])) else b
                other = b if te is a else a
                sgn = 1 if (te['box'][0][ax] + te['box'][1][ax]) >= (other['box'][0][ax] + other['box'][1][ax]) else -1
                d = Vector((0, 0, 0))
                d[ax] = push * sgn
                W.move_world(te['root'] or te['m'], d)
                te['box'] = W.box_of_object(te['m'], W.depsgraph())
            break
    if report:
        _p('check_z_fighting', '%d coplanar pair(s) share an exact face depth, which flickers on camera. A few '
           'mm either way settles it: sinking slightly into the surface works as well as sitting proud%s:'
           % (len(report), (' (nudged %g mm apart)' % (push * 1000)) if auto_fix else ''))
        for p in report[:8]:
            print('  %s <=> %s (coplanar on %s)' % (p['a'].name, p['b'].name, p['axis']))
        if len(report) > 8:
            print('  ...and %d more' % (len(report) - 8))
    return report


def _textured(o):
    for m in W.collect(o):
        for s in m.material_slots:
            mt = s.material
            if mt and mt.node_tree and any(n.bl_idname == 'ShaderNodeTexImage' and n.image for n in mt.node_tree.nodes):
                return True
    return False


def _character(o):
    p = o
    while p is not None:
        if p.type == 'ARMATURE' or W.flag(p, 'eido_seated'):
            return True
        p = p.parent
    for c in [o] + list(o.children_recursive):
        if any(md.type == 'ARMATURE' for md in getattr(c, 'modifiers', [])):
            return True
    return False


def check_facing(scene=None, min_size=1.2, thin_frac=0.28, buried_at=0.3):
    """Thin, textured, free-standing display panels (billboards, signs, screens): reports the
    clearance on each side of the display axis and warns when one interpenetrates something or is
    blocked on both sides, with pivot-offset evidence. Detector only. Opt out: obj['no_facing_check']."""
    scene = scene or bpy.context.scene
    W.update()
    dg = W.depsgraph()
    lvl1 = [o for o in scene.objects if o.parent is None and o.type not in ('CAMERA', 'LIGHT') and W.visible(o)]
    cands = list(lvl1)
    for r in lvl1:
        cands += [c for c in r.children if c.type not in ('CAMERA', 'LIGHT')]
    E = []
    for o in cands:
        if not W.collect(o):
            continue
        E.append({'o': o, 'box': W.tight_box(o, dg=dg)})
    out = []
    for e in E:
        r = e['o']
        if W.flag(r, 'no_facing_check'):
            continue
        exempt = W.flag(r, 'allow_intersect') or W.flag(r, 'no_clipping_check') or _character(r)
        for c in r.children_recursive:
            if W.flag(c, 'allow_intersect') or W.flag(c, 'no_clipping_check'):
                exempt = True
        if exempt or not _textured(r):
            continue
        s = W.box_size(e['box'])
        dims = [s.x, s.y, s.z]
        mx, mn = max(dims), min(dims)
        thin_ax = dims.index(mn)
        if mx < min_size or mn > thin_frac * mx or thin_ax == 2:
            continue
        k, lat = thin_ax, 1 - thin_ax
        clr = {'+': float('inf'), '-': float('inf')}
        pen = None
        for oth in E:
            if oth is e or W.is_ancestor(oth['o'], r) or W.is_ancestor(r, oth['o']):
                continue
            ov = W.box_overlap(e['box'], oth['box'])
            if all(v > 0.05 for v in ov):
                pen = oth
                continue
            oy = e['box'][0].z < oth['box'][1].z and e['box'][1].z > oth['box'][0].z
            ol = e['box'][0][lat] < oth['box'][1][lat] and e['box'][1][lat] > oth['box'][0][lat]
            if not oy or not ol:
                continue
            gp = oth['box'][0][k] - e['box'][1][k]
            gm = e['box'][0][k] - oth['box'][1][k]
            if gp >= 0:
                clr['+'] = min(clr['+'], gp)
            if gm >= 0:
                clr['-'] = min(clr['-'], gm)
        wc = W.box_center(e['box'])
        piv = (wc - r.matrix_world.translation).length
        note = (' (pivot %.2fm from the visual centre: rotating about the pivot TRANSLATES the panel; '
                'rotate about the centre)' % piv) if piv > 0.15 * mx else ''
        ax = 'xy'[k]
        fmt = lambda v: 'open' if v == float('inf') else '%.2fm' % v
        if pen is not None:
            ov = W.box_overlap(e['box'], pen['box'])
            _p('check_facing', "⚠ display panel '%s' INTERPENETRATES '%s' by (%.2f, %.2f, %.2f)m: wrong rotation "
               "or wrong spot%s. Face it out and clear the massing, or set obj['no_facing_check'] = True "
               "if the overlap is intentional." % (r.name, pen['o'].name, ov.x, ov.y, ov.z, note))
        elif clr['+'] < buried_at and clr['-'] < buried_at:
            _p('check_facing', "⚠ display panel '%s' is BURIED: blocked on both display sides (%s+ %s, %s- %s); "
               "nothing can see its face%s." % (r.name, ax, fmt(clr['+']), ax, fmt(clr['-']), note))
        else:
            _p('check_facing', "'%s' display axis %s: %s+ %s, %s- %s%s"
               % (r.name, ax, ax, fmt(clr['+']), ax, fmt(clr['-']), note))
        out.append({'obj': r, 'penetrated': pen is not None, 'clearance': dict(plus=clr['+'], minus=clr['-'])})
    return out


def check_density(scene=None, min=5, exclude=()):
    """How many distinct top-level things hold visible geometry (an observation, never a demand)."""
    scene = scene or bpy.context.scene
    excl = set(exclude)
    n = sum(1 for o in scene.objects if o.parent is None and o not in excl
            and o.type not in ('CAMERA', 'LIGHT') and W.collect(o))
    if n < min:
        _p('check_density', '%d distinct top-level object(s) placed: a low count sometimes means a scene '
           'reads sparse, and sometimes just good grouping. The probe frames tell which.' % n)
    else:
        _p('check_density', '%d distinct objects placed' % n)
    return n


def check_line_intrusion(scene=None):
    """A tall object planted IN a conveyor / belt / line (named so): base below the line's surface,
    body through it. Items riding the line are fine. Opt out: obj['no_intrusion_check']."""
    scene = scene or bpy.context.scene
    W.update()
    lines = [o for o in scene.objects if _LINE_RE.search(o.name or '') and (o.type in W.GEOM_TYPES or o.type == 'EMPTY')]
    if not lines:
        return []
    off = []
    for line in lines:
        lb = W.tight_box(line)
        if W.box_size(lb).length == 0:
            continue
        top = lb[1].z
        shrink = 0.1 * min(lb[1].x - lb[0].x, lb[1].y - lb[0].y)
        for root in scene.objects:
            if root.parent is not None or root == line or root.type in ('CAMERA', 'LIGHT'):
                continue
            if W.flag(root, 'no_intrusion_check') or _character(root) or W.is_ancestor(root, line) or W.is_ancestor(line, root):
                continue
            if not W.collect(root):
                continue
            ob = W.tight_box(root)
            c = W.box_center(ob)
            inside = lb[0].x + shrink < c.x < lb[1].x - shrink and lb[0].y + shrink < c.y < lb[1].y - shrink
            if inside and ob[0].z < top - 0.25 and ob[1].z > top + 0.3:
                off.append({'obj': root, 'line': line})
                _p('placement', "⚠ RE-RENDER REQUIRED: '%s' is planted IN THE MIDDLE of '%s' (base below its "
                   "surface, body up through it). Something that operates on a line stands BESIDE it: "
                   "station_beside(obj, line, gap=..., forward=...). Intentional: obj['no_intrusion_check'] = True."
                   % (root.name, line.name))
    if not off:
        _p('placement', 'line-intrusion OK (%d transport line(s) checked).' % len(lines))
    return off


def run_placement_audits(scene=None, auto_fix=None):
    """The hook a render harness calls once the scene is built: an opt-in repair pass (scene flag
    eido_auto_fix_placement, or auto_fix=True), then the warn-only audits on the result.
    Returns {'clipping', 'hovering', 'density', 'z_fighting', 'facing', 'line_intrusion', 'floaters',
    'seated_facing'} (seated_facing: sitters seat_on turned away from their chair's facing, as the engine's
    deferred seat check found them)."""
    scene = scene or bpy.context.scene
    if W.flag(scene, 'eido_no_auto_placement_check'):
        _p('placement', "audits skipped (scene['eido_no_auto_placement_check'])")
        return {}
    fix = W.flag(scene, 'eido_auto_fix_placement') if auto_fix is None else auto_fix
    if fix:
        check_clipping(scene, auto_fix=True)
        check_hovering(scene, auto_fix=True)
        check_z_fighting(scene, auto_fix=True)
        _p('repair', 'opt-in placement repair applied: the audits below judge the repaired scene.')
    from .seating import check_seated_facing
    res = {'clipping': check_clipping(scene), 'hovering': check_hovering(scene),
           'density': check_density(scene), 'z_fighting': check_z_fighting(scene),
           'facing': check_facing(scene), 'line_intrusion': check_line_intrusion(scene),
           'seated_facing': check_seated_facing(scene)}
    fl = [h for h in res['hovering'] if h['kind'] in ('void', 'far')]
    res['floaters'] = fl
    if fl:
        _p('placement', "⚠ %d object(s) are genuinely unsupported and will read as floating on camera: %s. "
           "place_on(obj, surface) seats a piece on what it belongs to; a piece meant to fly declares "
           "obj['no_support_check'] = True." % (len(fl), ', '.join(h['obj'].name for h in fl[:6])))
    else:
        _p('placement', 'every solid piece rests on a surface: placement reads grounded.')
    return res
