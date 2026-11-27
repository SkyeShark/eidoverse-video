"""eidoblend.props.helicopter.look: the helicopter's masks and materials. It renders as its HIGH: what a material needs
is stored on the high's own vertices, and a layer stack reads it.

    from eidoblend.props.helicopter import look
    look.apply(bpy.data.collections['helicopter_high'], decals_dir)     # masks on every part, then the materials

THE MASKS (vertex_masks): each part's sharp edges taken BEFORE its bevel, then its final mesh brought into the
aircraft's space and cut until no edge is over a part's cap (5 cm on the hull, 3.5 cm on the big panels, 1.4 cm on the
small parts), and the colour attribute 'masks' written on every vertex: R the nearness of an EXPOSED convex arris (a
distance, so the wear band is set in the material), G of an inside corner, B the openness near (rays to 0.1 m), A the
openness far (to 0.5 m). The turning parts go back under their rotor's Empty afterwards.

THE CONDITION, one for the whole aircraft: a working machine in a dry, dusty country: flown daily, washed seldom,
serviced always. Each layer from its cause:
    paint    a flat chemical-agent-resistant drab, chalked by the sun in fields a metre across, every frame and stringer
             showing as its row of rivet heads, every joint as a fine dark seam (decals.py's pictures, laid through the
             hull from each side); the stencils, read true from each side
    dust     pale and thin everywhere, thick on the belly and the lower flanks (the rotor's wash off the ground), on what
             faces up, round the rivet heads and in the seams
    soot     from the two exhausts back along the boom's upper flanks, streaked along the flow; the exhaust ducts and
             their shields are painted with the airframe and take the same streaked soot
    oil      runs down the cabin's sides under the gearbox
    wear     paint rubbed and chipped where boots and hands go (the sills, the kick steps, the door's edges); bright
             steel only where it is steel
    inside   quilted blankets on the walls and ceiling; a non-skid floor, scuffed at the doors and down the aisle; grey
             cloth seats
    glass    tinted, a film of dust on it; the blades black with a bright erosion strip along the leading edge
"""

from __future__ import annotations

import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from ...materials.layered import NT
from . import datum as D

BIG = ('hull', 'spine_fairing', 'nacelle_', 'tail_pylon', 'stabilator', 'main_blade_', 'cabin_door_', 'exhaust_duct_', 'exhaust_shield_', 'pane_')


# ------------------------------------------------------------------------------------------------ the masks ---

def bake_edges(parts, maxe):
    """Each part's own sharp edges BEFORE its bevel (convex with their outward direction, and concave), then its final
    mesh (modifiers applied) in the aircraft's space, cut by planes until no edge is over maxe(o) metres and
    triangulated; every part left at identity with no parent. -> {name: (convex, concave)}"""
    dg = bpy.context.evaluated_depsgraph_get()
    arris = {}
    for o in parts:
        M = o.matrix_world.copy()
        b0 = bmesh.new()
        b0.from_mesh(o.data)
        b0.transform(M)
        b0.normal_update()
        conv, conc = [], []
        for e in b0.edges:
            if len(e.link_faces) != 2:
                continue
            a = e.calc_face_angle_signed(0.0)
            if a > math.radians(30.0):
                n = e.link_faces[0].normal + e.link_faces[1].normal
                if n.length > 1e-6:
                    conv.append((e.verts[0].co.copy(), e.verts[1].co.copy(), n.normalized()))
            elif a < -math.radians(30.0):
                conc.append((e.verts[0].co.copy(), e.verts[1].co.copy()))
        b0.free()
        arris[o.name] = (conv, conc)
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        me.transform(M)
        o.modifiers.clear()
        old = o.data
        o.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
        bm = bmesh.new()
        bm.from_mesh(me)
        cap = maxe(o) if callable(maxe) else maxe
        # cut by planes a cap apart along each axis, then triangulate once (halving long edges instead fans out across a
        # bevel's hair-thin strips)
        for a in range(3):
            lo = min(v.co[a] for v in bm.verts)
            hi = max(v.co[a] for v in bm.verts)
            k = int((hi - lo) / cap)
            nrm = Vector((0.0, 0.0, 0.0))
            nrm[a] = 1.0
            for i in range(1, k + 1):
                p = Vector((0.0, 0.0, 0.0))
                p[a] = lo + (hi - lo) * i / (k + 1)
                bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6, plane_co=p, plane_no=nrm)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        for e in bm.edges:
            e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(34))
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
        bm.free()
        me.update()
    return arris


def tree(parts):
    """One BVH over every part (as they stand: at identity)."""
    tris_v, tris_i = [], []
    for o in parts:
        base = len(tris_v)
        tris_v += [v.co.copy() for v in o.data.vertices]
        tris_i += [tuple(base + i for i in p.vertices) for p in o.data.polygons]
    return BVHTree.FromPolygons(tris_v, tris_i)


def _canon(k, seed):
    r, out = random.Random(seed), []
    for i in range(k):
        u, v = (i + r.random()) / k, r.random()
        rr, ph = math.sqrt(u), 2.0 * math.pi * v
        out.append((rr * math.cos(ph), rr * math.sin(ph), math.sqrt(1.0 - u)))
    return out


C24, C8 = _canon(24, 1), _canon(8, 2)


def vertex_masks(parts, arris, bvh, step, arris_cap, crease_cap, near, far, bias):
    """The colour attribute 'masks' on every vertex (see the module doc). step: the arris samples' spacing (m);
    arris_cap / crease_cap: the distances that read 0; near / far: the openness rays' reach; bias: their start's
    lift. Returns the number of vertices written."""
    def occluded(p, n, dirs, reach):
        t = n.orthogonal().normalized()
        b = n.cross(t)
        nr = tot = 0
        for x, y, z in dirs:
            h = bvh.ray_cast(p, t * x + b * y + n * z, reach)
            if h[0] is not None:
                tot += 1
                if h[3] < near:
                    nr += 1
        return nr, tot

    def samples(edges, exposed):
        pts = []
        for e in edges:
            p0, p1 = e[0], e[1]
            k = max(1, int((p1 - p0).length / step))
            keep = True
            for i in range(k + 1):
                p = p0.lerp(p1, i / k)
                if exposed and i % 6 == 0:
                    keep = occluded(p + e[2] * (bias * 2.0), e[2], C8, near)[1] <= 4
                if keep:
                    pts.append(p)
        if not pts:
            return None
        kd = KDTree(len(pts))
        for i, p in enumerate(pts):
            kd.insert(p, i)
        kd.balance()
        return kd
    total = 0
    for o in parts:
        me = o.data
        conv, conc = arris[o.name]
        kd, kc = samples(conv, True), samples(conc, False)
        arr = np.zeros((len(me.vertices), 4), np.float32)
        for v in me.vertices:
            n = v.normal
            nr, tot = occluded(v.co + n * bias, n, C24, far)
            d = kd.find(v.co)[2] if kd else 1e3
            dc = kc.find(v.co)[2] if kc else 1e3
            arr[v.index] = (d, max(0.0, 1.0 - dc / crease_cap), 1.0 - nr / 24.0, 1.0 - tot / 24.0)
        # the arris was measured as the SHARP corner; the surface there is the bevel's crest, a little inside it: take
        # that off part by part, so 0 is the crest on every part
        near_d = arr[:, 0][arr[:, 0] < arris_cap * 0.375]
        d0 = float(np.percentile(near_d, 10)) if len(near_d) > 20 else 0.0
        arr[:, 0] = np.clip(1.0 - np.maximum(arr[:, 0] - d0, 0.0) / arris_cap, 0.0, 1.0)
        ca = me.color_attributes.get('masks') or me.color_attributes.new('masks', 'FLOAT_COLOR', 'POINT')
        ca.data.foreach_set('color', arr.ravel())
        total += len(me.vertices)
        if 'flat_faces_flat' not in o.modifiers:
            w = o.modifiers.new('flat_faces_flat', 'WEIGHTED_NORMAL')
            w.keep_sharp = True
    return total


# ------------------------------------------------------------------------------------------------ the stack ---

class MNT(NT):
    def masks(self):
        """(arris nearness, inside-corner nearness, openness near, openness far) from the 'masks' attribute"""
        at = self.N.new('ShaderNodeAttribute')
        at.attribute_name = 'masks'
        sep = self.N.new('ShaderNodeSeparateColor')
        self.L.new(at.outputs['Color'], sep.inputs[0])
        return sep.outputs[0], sep.outputs[1], sep.outputs[2], at.outputs['Alpha']


SOCKETS = (('Base Color', 'NodeSocketColor', (0.02, 0.02, 0.02, 1)), ('Base Metal', 'NodeSocketFloat', 0.0), ('Base Rough', 'NodeSocketFloat', 0.45),
           ('Mottle', 'NodeSocketFloat', 0.04), ('Grain', 'NodeSocketFloat', 3e-6),
           ('Worn Color', 'NodeSocketColor', (0.8, 0.8, 0.8, 1)), ('Worn Metal', 'NodeSocketFloat', 1.0), ('Worn Rough', 'NodeSocketFloat', 0.36),
           ('Wear Band', 'NodeSocketFloat', 0.45), ('Wear', 'NodeSocketFloat', 1.0),
           ('Rub Value', 'NodeSocketFloat', 1.4), ('Rub Rough', 'NodeSocketFloat', -0.06),
           ('Polish', 'NodeSocketFloat', 0.5), ('Polish Rough', 'NodeSocketFloat', -0.12), ('Polish Value', 'NodeSocketFloat', 0.0),
           ('Dust', 'NodeSocketFloat', 0.8), ('Dust Color', 'NodeSocketColor', (0.36, 0.30, 0.22, 1)), ('Dust Up', 'NodeSocketFloat', 0.12),
           ('Grime', 'NodeSocketFloat', 0.7),
           ('Marking', 'NodeSocketFloat', 0.0), ('Marking Color', 'NodeSocketColor', (0.7, 0.7, 0.68, 1)),
           ('Soot', 'NodeSocketFloat', 0.0), ('Soot Color', 'NodeSocketColor', (0.012, 0.011, 0.010, 1)),
           ('Height', 'NodeSocketFloat', 0.0), ('Rough Add', 'NodeSocketFloat', 0.0),
           ('Scuff Extra', 'NodeSocketFloat', 0.0), ('Tint', 'NodeSocketColor', (1, 1, 1, 1)),
           ('Dust Add', 'NodeSocketFloat', 0.0))


def surface_group(name='helicopter_surface', arris_mm=4.0, k=1.0):
    """The layer stack on the vertex masks, as a node group with one input per number (SOCKETS): coating -> handling
    polish -> grime -> markings -> wear in two stages (rub, then chip to what lies beneath) -> soot -> a thin dust.
    arris_mm: how many wear units the masks' R channel spans (its distance cap over the unit: 3 for the aircraft's 30 mm
    over 10 mm); k: the breakup's scale against a hand-held thing's (the aircraft 0.25)."""
    g = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    for nm, typ, dv in SOCKETS:
        g.interface.new_socket(nm, in_out='INPUT', socket_type=typ).default_value = dv
    g.interface.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    t = MNT(g)
    I = t.N.new('NodeGroupInput').outputs
    out = t.N.new('NodeGroupOutput')
    e_close, c_close, open_s, open_l = t.masks()
    P = t.obj()
    n_macro, n_gate = t.noise(P, 16.0 * k, 2.0), t.noise(P, 11.0 * k, 2.0, off=(3.1, 1.7, 0.4))
    n_meso, n_fine = t.noise(P, 85.0 * k, 3.0), t.noise(P, 650.0 * k, 2.0)
    n_nick, n_grain = t.noise(P, 420.0 * k, 2.0, off=(0.7, 2.3, 5.1)), t.noise(P, 3500.0 * k, 1.0)
    c_macro, c_meso, c_fine = t.sub(n_macro, 0.5), t.sub(n_meso, 0.5), t.sub(n_fine, 0.5)
    col = t.mixc(1.0, I['Base Color'], I['Tint'])
    col.node.blend_type = 'MULTIPLY'
    col = t.value(col, t.add(1.0, t.add(t.mul(t.mul(c_macro, 2.0), I['Mottle']), t.mul(c_meso, I['Mottle']))))
    rough = t.add(I['Base Rough'], t.add(t.mul(c_fine, 0.06), t.mul(c_macro, 0.04)))
    pol = t.mul(t.mul(t.sm(open_l, 0.5, 0.9), t.sm(n_gate, 0.42, 0.62)), I['Polish'])
    rough = t.add(rough, t.mul(pol, I['Polish Rough']))
    col = t.value(col, t.add(1.0, t.mul(pol, I['Polish Value'])))
    rec = t.sm(t.inv(open_s), 0.2, 0.7)
    crease = t.sm(c_close, 0.45, 0.95)
    gr = t.mul(t.mul(t.mx(t.mul(rec, 0.8), t.mul(crease, 0.6)), t.add(0.6, t.mul(c_meso, 0.8))), I['Grime'], clamp=True)
    col = t.value(col, t.sub(1.0, t.mul(gr, 0.35)))
    rough = t.add(rough, t.mul(gr, 0.1))
    col = t.mixc(t.mul(I['Marking'], 0.92), col, I['Marking Color'])
    rough = t.mixf(I['Marking'], rough, 0.55)
    d_mm = t.mul(t.inv(e_close), arris_mm)
    gate = t.sm(n_gate, 0.40, 0.72)
    wd = t.add(d_mm, t.add(t.mul(c_fine, 0.35), t.mul(c_meso, 0.25)))
    rub = t.inv(t.sm(t.sub(wd, t.mul(t.add(0.15, t.mul(t.mul(gate, gate), 0.5)), I['Wear'])), -0.04, 0.04))
    rub = t.mx(rub, t.sm(t.add(I['Scuff Extra'], t.mul(c_fine, 0.6)), 0.55, 0.62))
    wb = t.sub(t.mul(t.mul(t.mul(gate, t.mul(gate, gate)), I['Wear Band']), I['Wear']), 0.13)
    chip = t.inv(t.sm(t.sub(t.add(d_mm, t.add(t.mul(c_fine, 0.5), t.mul(c_meso, 0.3))), wb), -0.025, 0.025))
    nick = t.mul(t.mul(t.mul(t.sm(n_nick, 0.87, 0.89), gate), t.sm(open_l, 0.55, 0.85)), I['Wear'], clamp=True)
    chip = t.mx(chip, nick)
    col = t.value(col, t.add(1.0, t.mul(rub, I['Rub Value'])))
    rough = t.add(rough, t.mul(rub, I['Rub Rough']))
    col = t.mixc(chip, col, I['Worn Color'])
    metal = t.mx(t.mul(chip, I['Worn Metal']), t.mul(t.inv(chip), I['Base Metal']))
    rough = t.mixf(chip, rough, I['Worn Rough'])
    st = t.sm(t.add(I['Soot'], t.mul(c_meso, 0.5)), 0.3, 0.8)
    col = t.mixc(t.mul(st, 0.92), col, I['Soot Color'])
    rough = t.mixf(st, rough, 0.9)
    metal = t.mul(metal, t.inv(st))
    up = t.sm(t.nrm()[2], 0.6, 0.95)
    deep = t.sm(t.inv(open_s), 0.45, 0.85)
    tight = t.sm(c_close, 0.78, 0.98)
    lay = t.add(t.add(t.mx(t.mul(deep, 0.9), t.mul(tight, 0.8)), t.mul(up, I['Dust Up'])), I['Dust Add'])
    dust = t.mul(t.mul(t.sm(t.add(lay, t.add(t.mul(c_fine, 0.6), t.mul(c_meso, 0.3))), 0.55, 0.85), I['Dust']), t.inv(chip), clamp=True)
    col = t.mixc(t.mul(dust, 0.38), col, I['Dust Color'])
    rough = t.mixf(t.mul(dust, 0.7), rough, 0.9)
    metal = t.mul(metal, t.inv(t.mul(dust, 0.5)))
    h = t.add(t.add(I['Height'], t.mul(t.sub(n_grain, 0.5), I['Grain'])), t.sub(t.mul(dust, 8e-6), t.mul(chip, 12e-6)))
    bump = t.N.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value, bump.inputs['Distance'].default_value = 1.0, 1.0
    t.L.new(h, bump.inputs['Height'])
    bs = t.N.new('ShaderNodeBsdfPrincipled')
    t.L.new(col, bs.inputs['Base Color'])
    t.L.new(t.m('MINIMUM', metal, 1.0, clamp=True), bs.inputs['Metallic'])
    t.L.new(t.m('MAXIMUM', t.add(rough, I['Rough Add']), 0.07, clamp=True), bs.inputs['Roughness'])
    t.L.new(bump.outputs[0], bs.inputs['Normal'])
    t.L.new(bs.outputs[0], out.inputs[0])
    return g


def material(name, group, params, extra=None, pictures=None):
    """An instance of the stack; `extra(t, inputs)` wires what is the part's own (pictures, regions)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = group
    for k, v in params.items():
        gn.inputs[k].default_value = v
    nt.links.new(gn.outputs[0], next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL').inputs[0])
    if extra:
        extra(MNT(nt, pictures), gn.inputs)
    return m


# ------------------------------------------------------------------------------------------- its materials ---

X0, X1, Z0, Z1 = -4700.0, 9500.0, -500.0, 3400.0               # the pictures' rectangle, side on (decals.py)
DUST = (0.34, 0.29, 0.21, 1)
SOOT = (0.016, 0.015, 0.013, 1)
# the drab: dark, browner than green
PAINT = {'Base Color': (0.036, 0.036, 0.028, 1), 'Base Rough': 0.78, 'Mottle': 0.07, 'Grain': 1.5e-5, 'Worn Color': (0.33, 0.34, 0.32, 1),
         'Worn Metal': 0.45, 'Worn Rough': 0.5, 'Wear Band': 0.75, 'Wear': 0.75, 'Rub Value': 0.3, 'Rub Rough': -0.1, 'Polish': 0.25,
         'Polish Rough': -0.08, 'Dust': 0.62, 'Dust Up': 0.9, 'Grime': 0.9, 'Marking Color': (0.010, 0.010, 0.010, 1)}
TURNING = ('hub_', 'cuff_', 'pitch_horns', 'dampers', 'bifilar', 'swashplate_', 'scissors_', 'slip_ring_cap', 'tail_rotor_hub', 'tail_rotor_pitch_beam',
           'mast_boot', 'intake_bullet', 'intake_struts')
GREY = ('seat_', 'ceiling_rails', 'pilot_seat_rails', 'door_hangers', 'floor_lashing_pans')


def paint_extra(t, I):
    """the airframe's own: rivets, seams and fasteners as height, the stencils, the sun's chalking, the soot aft of the
    exhausts, the oil under the gearbox, the dust on the belly and lower flanks, the boots at the sills"""
    X, Y, Z = t.pos_mm()
    nx, ny, nz = t.nrm()
    P = t.obj()
    side = t.sm(t.m('ABSOLUTE', ny), 0.45, 0.7)
    img, _g = t.picture({'file': 'skin_side.png', 'u': ['x', X0, X1], 'v': ['z', Z0, Z1]})
    sep = t.N.new('ShaderNodeSeparateColor')
    t.L.new(img.outputs['Color'], sep.inputs[0])
    riv, seam, fast = t.mul(sep.outputs[0], side), t.mul(sep.outputs[1], side), t.mul(sep.outputs[2], side)
    t.L.new(t.sub(t.add(t.mul(riv, 0.0006), t.mul(fast, 0.00025)), t.mul(seam, 0.0009)), I['Height'])
    left, gl = t.picture({'file': 'marks_left.png', 'u': ['x', X0, X1], 'v': ['z', Z0, Z1]}, facing=(1, -1))
    right, gr = t.picture({'file': 'marks_right.png', 'u': ['x', X0, X1], 'v': ['z', Z0, Z1]}, facing=(1, 1))
    t.L.new(t.mx(t.mul(left.outputs['Color'], gl), t.mul(right.outputs['Color'], gr)), I['Marking'])
    # soot back along the boom from the exhausts, streaked along the flow; the sun's chalking in fields a metre across;
    # rain's and the wash rack's runs down the flanks
    lo = t.lin(X, 3000.0, 8000.0, 800.0, 470.0, clamp=True)
    streak = t.noise(P, 1.0, 3.0, stretch=(0.5, 7.0, 7.0))
    exhaust = t.mul(t.mul(t.mul(t.sm(X, 2500.0, 3500.0), t.inv(t.sm(X, 6500.0, 10400.0))), t.sm(Z, lo, t.add(lo, 420.0))), t.add(0.45, t.mul(streak, 0.75)))
    field = t.sub(t.noise(P, 0.55, 3.0, off=(1.0, 4.0, 2.0)), 0.5)
    runs = t.mul(t.sub(t.noise(P, 1.0, 2.0, stretch=(22.0, 22.0, 0.5), off=(5.0, 2.0, 0.0)), 0.5), side)
    tone = t.sub(t.add(t.add(1.0, t.mul(field, 0.34)), t.mul(runs, 0.22)), t.mul(exhaust, 0.62))
    t.L.new(tone, I['Tint'])
    t.L.new(t.mul(exhaust, 0.12), I['Rough Add'])
    # oil down the sides under the gearbox; grime in every seam
    run = t.sm(t.noise(P, 1.0, 2.0, stretch=(16.0, 16.0, 0.6), off=(3.0, 1.0, 0.0)), 0.56, 0.76)
    oil = t.mul(t.mul(t.mul(t.sm(X, -700.0, -300.0), t.inv(t.sm(X, 1300.0, 1800.0))), t.mul(t.sm(Z, 700.0, 1480.0), side)), t.mul(run, 0.7))
    t.L.new(t.mx(t.mul(seam, 0.7), oil), I['Soot'])
    # dust: the belly and the lower flanks (a film that thins upward), the boom, round the rivet heads and in the seams
    low = t.inv(t.sm(Z, -200.0, 900.0))
    t.L.new(t.add(t.add(t.mul(low, 0.95), t.mul(t.sm(X, 3000.0, 9000.0), 0.15)), t.add(t.mul(riv, 0.3), t.mul(seam, 0.35))), I['Dust Add'])
    # boots at the two sills and the kick steps
    sill = t.mul(t.mul(t.sm(X, D.DOOR_X0 - 150.0, D.DOOR_X0), t.inv(t.sm(X, D.DOOR_X1, D.DOOR_X1 + 150.0))), t.inv(t.sm(Z, -40.0, 190.0)))
    t.L.new(t.mul(sill, 0.6), I['Scuff Extra'])


def quilt_extra(t, I):
    """the blankets: pillows 160 mm square between stitched lines"""
    X, Y, Z = t.pos_mm()
    a = t.m('ABSOLUTE', t.m('SINE', t.mul(X, math.pi / 160.0)))
    b = t.m('ABSOLUTE', t.m('SINE', t.mul(t.add(Y, Z), math.pi / 160.0)))
    pillow = t.m('POWER', t.mul(a, b), 0.45)
    t.L.new(t.mul(pillow, 0.007), I['Height'])
    t.L.new(t.mul(t.inv(t.sm(pillow, 0.0, 0.35)), 0.6), I['Soot'])


def floor_extra(t, I):
    """non-skid grit; worn where boots go: the two sills, the aisle"""
    X, Y, Z = t.pos_mm()
    P = t.obj()
    t.L.new(t.mul(t.sub(t.noise(P, 1400.0, 1.0), 0.5), 0.0005), I['Height'])
    door = t.mul(t.mul(t.sm(X, D.DOOR_X0 - 100.0, D.DOOR_X0 + 200.0), t.inv(t.sm(X, D.DOOR_X1 - 200.0, D.DOOR_X1 + 100.0))), t.sm(t.m('ABSOLUTE', Y), 620.0, 1050.0))
    aisle = t.mul(t.inv(t.sm(t.m('ABSOLUTE', Y), 150.0, 420.0)), 0.5)
    t.L.new(t.mul(t.mx(door, aisle), 0.62), I['Scuff Extra'])
    t.L.new(t.mul(t.mx(door, aisle), 0.25), I['Dust Add'])


def cloth_extra(t, I):
    """a plain weave, seen only close"""
    X, Y, Z = t.pos_mm()
    w = t.mul(t.m('SINE', t.mul(t.add(X, Y), 2.6)), t.m('SINE', t.mul(t.add(Z, t.mul(Y, 0.3)), 2.6)))
    t.L.new(t.mul(w, 0.00018), I['Height'])


def custom(name, pictures):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n_ in list(nt.nodes):
        if n_.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n_)
    t = MNT(nt, pictures)
    bs = t.N.new('ShaderNodeBsdfPrincipled')
    t.L.new(bs.outputs[0], next(n_ for n_ in nt.nodes if n_.type == 'OUTPUT_MATERIAL').inputs[0])
    return m, t, bs


def glass_material(prefix, pictures):
    """tinted glass, a thin film of dust on it in soft fields"""
    m, t, bs = custom(prefix + 'glass', pictures)
    P = t.obj()
    film = t.mul(t.sm(t.noise(P, 2.2, 3.0), 0.4, 0.85), 0.16)
    t.L.new(t.mixc(film, (0.008, 0.013, 0.010, 1.0), (0.30, 0.26, 0.19, 1.0)), bs.inputs['Base Color'])
    t.L.new(t.add(0.03, t.mul(film, 0.5)), bs.inputs['Roughness'])
    t.L.new(t.add(0.55, t.mul(film, 0.6)), bs.inputs['Alpha'])
    m.surface_render_method = 'BLENDED'
    m.use_transparency_overlap = False
    m.use_backface_culling = False
    return m


def blade_material(prefix, pictures):
    """black paint; a bright erosion strip along the leading edge from a little outboard of the root; dust; the trailing
    edge chalked"""
    m, t, bs = custom(prefix + 'blade', pictures)
    P = t.obj()
    at = t.N.new('ShaderNodeAttribute')
    at.attribute_name = 'blade'
    sep = t.N.new('ShaderNodeSeparateColor')
    t.L.new(at.outputs['Color'], sep.inputs[0])
    chord, span = sep.outputs[0], sep.outputs[1]
    strip = t.mul(t.inv(t.sm(chord, 0.085, 0.10)), t.sm(span, 0.10, 0.12))
    pit = t.noise(P, 260.0, 2.0)
    n_big = t.noise(P, 2.0, 3.0)
    paint = t.value((0.020, 0.021, 0.022, 1.0), t.add(0.85, t.mul(n_big, 0.5)))
    dust = t.mul(t.sm(t.add(t.mul(t.sm(chord, 0.5, 1.0), 0.45), t.noise(P, 14.0, 3.0)), 0.7, 1.05), 0.22)
    paint = t.mixc(dust, paint, (0.30, 0.26, 0.19, 1.0))
    col_ = t.mixc(strip, paint, t.value((0.50, 0.50, 0.51, 1.0), t.add(0.8, t.mul(pit, 0.4))))
    t.L.new(col_, bs.inputs['Base Color'])
    t.L.new(t.mul(strip, 1.0), bs.inputs['Metallic'])
    t.L.new(t.mixf(strip, t.add(0.62, t.mul(dust, 0.3)), t.add(0.3, t.mul(pit, 0.18))), bs.inputs['Roughness'])
    return m


def plain(prefix, name, rgb, rough, pictures, metal=0.0, emit=None, strength=0.0):
    m, t, bs = custom(prefix + name, pictures)
    bs.inputs['Base Color'].default_value = (*rgb, 1.0)
    bs.inputs['Roughness'].default_value, bs.inputs['Metallic'].default_value = rough, metal
    if emit:
        bs.inputs['Emission Color'].default_value = (*emit, 1.0)
        bs.inputs['Emission Strength'].default_value = strength
    return m


def materials(pictures, prefix='helicopter.'):
    """Every material of the aircraft by its role: {'paint', 'paint_turning', 'frame_grey', 'armour', 'liner', 'floor',
    'fabric', 'rubber', 'tyre', 'steel', 'dark', 'glass', 'blade', 'lens_red', 'lens_green', 'lens_clear', 'screen'}."""
    G = surface_group(prefix + 'surface', arris_mm=3.0, k=0.25)

    def M_(name, extra=None, **kw):
        kw.setdefault('Dust Color', DUST)
        kw.setdefault('Soot Color', SOOT)
        return material(prefix + name, G, kw, extra, pictures)

    return {
        'paint': M_('paint', paint_extra, **PAINT),
        'paint_turning': M_('paint_turning', **dict(PAINT, **{'Base Color': (0.026, 0.027, 0.028, 1), 'Base Rough': 0.5, 'Mottle': 0.06, 'Polish': 0.8,
                                                              'Polish Rough': -0.14, 'Dust': 0.5, 'Wear': 1.0, 'Worn Color': (0.5, 0.5, 0.5, 1), 'Worn Metal': 1.0})),
        'frame_grey': M_('frame_grey', **dict(PAINT, **{'Base Color': (0.16, 0.17, 0.165, 1), 'Base Rough': 0.55, 'Mottle': 0.05, 'Worn Color': (0.6, 0.6, 0.6, 1),
                                                        'Worn Metal': 1.0, 'Wear': 1.1, 'Dust': 0.6})),
        'armour': M_('armour', **dict(PAINT, **{'Base Color': (0.035, 0.040, 0.034, 1), 'Base Rough': 0.6, 'Wear': 1.2, 'Dust': 0.7})),
        'liner': M_('liner_quilt', quilt_extra, **{'Base Color': (0.040, 0.046, 0.041, 1), 'Base Rough': 0.62, 'Mottle': 0.1, 'Wear': 0.3,
                                                   'Worn Color': (0.2, 0.2, 0.19, 1), 'Worn Metal': 0.0, 'Polish': 0.4, 'Dust': 0.5, 'Dust Up': 0.2,
                                                   'Grime': 1.0, 'Soot Color': (0.014, 0.015, 0.014, 1)}),
        'floor': M_('floor_nonskid', floor_extra, **{'Base Color': (0.040, 0.041, 0.044, 1), 'Base Rough': 0.86, 'Mottle': 0.1, 'Worn Color': (0.45, 0.45, 0.45, 1),
                                                     'Worn Metal': 0.9, 'Worn Rough': 0.45, 'Wear Band': 1.0, 'Wear': 1.0, 'Rub Value': 0.5, 'Polish': 0.0,
                                                     'Dust': 0.55, 'Dust Up': 1.0, 'Grime': 1.0}),
        'fabric': M_('seat_cloth', cloth_extra, **{'Base Color': (0.13, 0.135, 0.13, 1), 'Base Rough': 0.95, 'Mottle': 0.1, 'Wear': 0.0, 'Polish': 0.3,
                                                   'Polish Value': 0.2, 'Dust': 0.8, 'Dust Up': 0.4, 'Grime': 1.0}),
        'rubber': M_('rubber', **{'Base Color': (0.014, 0.014, 0.015, 1), 'Base Rough': 0.62, 'Mottle': 0.08, 'Wear': 0.0, 'Polish': 0.0, 'Dust': 0.8,
                                  'Dust Up': 0.5, 'Grime': 0.6}),
        'tyre': M_('tyre', **{'Base Color': (0.016, 0.016, 0.017, 1), 'Base Rough': 0.8, 'Mottle': 0.1, 'Wear': 0.0, 'Polish': 0.0, 'Dust': 1.0,
                              'Dust Up': 0.8, 'Dust Add': 0.3, 'Grime': 0.8}),
        'steel': M_('bright_steel', **{'Base Color': (0.60, 0.60, 0.61, 1), 'Base Metal': 1.0, 'Base Rough': 0.24, 'Mottle': 0.1, 'Wear': 0.0,
                                       'Polish': 0.6, 'Dust': 0.4, 'Grime': 0.7}),
        'dark': M_('black_console', **{'Base Color': (0.012, 0.012, 0.013, 1), 'Base Rough': 0.5, 'Mottle': 0.05, 'Worn Color': (0.3, 0.3, 0.3, 1),
                                       'Wear': 0.6, 'Dust': 0.6, 'Grime': 0.6}),
        'glass': glass_material(prefix, pictures), 'blade': blade_material(prefix, pictures),
        'lens_red': plain(prefix, 'lens_red', (0.45, 0.02, 0.015), 0.15, pictures, emit=(1.0, 0.05, 0.03), strength=3.0),
        'lens_green': plain(prefix, 'lens_green', (0.02, 0.4, 0.12), 0.15, pictures, emit=(0.05, 1.0, 0.3), strength=2.0),
        'lens_clear': plain(prefix, 'lens_clear', (0.55, 0.55, 0.5), 0.2, pictures, metal=0.6),
        'screen': plain(prefix, 'screen', (0.006, 0.01, 0.008), 0.12, pictures, emit=(0.15, 0.6, 0.3), strength=0.9),
    }


def which(o, clay):
    """the material a part's slot takes, from the slot's clay role and the part's name"""
    n_ = o.name
    if clay == 'clay_glass':
        if n_.startswith(('beacon_', 'position_light_l')):
            return 'lens_red'
        if n_.startswith('position_light_r'):
            return 'lens_green'
        if n_.startswith(('landing_light', 'cabin_dome')):
            return 'lens_clear'
        if n_.startswith('instrument_displays'):
            return 'screen'
        return 'glass'
    if clay == 'clay_rubber':
        return 'tyre' if 'tyre' in n_ else 'rubber'
    if clay in ('clay_dark', 'clay_fabric', 'clay_steel', 'clay_liner', 'clay_floor'):
        return clay[5:]
    if n_.startswith(('main_blade_', 'tail_blade_')):
        return 'blade'
    if n_.startswith(('exhaust_duct_', 'exhaust_shield_')):   # painted with the airframe: its soot streaks aft from them
        return 'paint'
    if n_.startswith('pilot_seat_'):
        return 'armour'
    if n_.startswith(TURNING):
        return 'paint_turning'
    if n_.startswith(GREY):
        return 'frame_grey'
    return 'paint'


def apply(col, pictures, prefix='helicopter.'):
    """The masks on every mesh part of the collection, then each part's materials. pictures: decals.py's folder.
    Returns {material key: slots}."""
    parts = [o for o in col.objects if o.type == 'MESH']
    parent = {o.name: o.parent for o in parts if o.parent is not None}
    arris = bake_edges(parts, lambda o: 0.05 if o.name == 'hull' else 0.035 if o.name.startswith(BIG) else 0.014)
    for o in parts:                                           # (the turning parts go back under what turns them)
        p = parent.get(o.name)
        if p is not None:
            o.parent = p
            o.matrix_parent_inverse = p.matrix_world.inverted()
    bvh = tree(parts)
    n = vertex_masks(parts, arris, bvh, step=0.004, arris_cap=0.03, crease_cap=0.04, near=0.10, far=0.5, bias=0.001)
    print(f'[helicopter] masks on {n:,} vertices of {len(parts)} parts')
    mats = materials(pictures, prefix)
    count = {}
    for o in parts:
        for i, slot in enumerate(o.data.materials):
            k = which(o, slot.name.split('.')[0] if slot else 'clay')
            o.data.materials[i] = mats[k]
            count[k] = count.get(k, 0) + 1
    print(f'[helicopter] materials {count}')
    return count
