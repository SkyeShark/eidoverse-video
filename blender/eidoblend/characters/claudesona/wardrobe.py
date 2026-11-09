"""eidoblend.characters.claudesona.wardrobe: claudesona_wardrobe.js's garment wardrobe in Blender (tools-guides/
claudesona.md, "Outfits"): garment layers shown and hidden, materials repainted with colours or procedural patterns,
petals folded back under a hat (the fold written into the spring chains' initial state), the hat seated.

    from eidoblend.characters import load_vrm
    from eidoblend.characters.claudesona import make_wardrobe, WARDROBE
    me = load_vrm('claude_suit_wardrobe'); me.arm.scale = (0.87,) * 3
    wd = make_wardrobe(me)                          # wears 'suit' (or wear=...); the TuTa wardrobe on the TuTa VRM
    wd.wear('lab_coat_1961')                        # now (a still, a single-outfit film)
    wd.wear('cyclist_1892', frame=240)              # KEYED: from frame 240 on (layers, paints, folds, the hat)
    wd.petals('mac_launch_1984', frame=300)         # another era's petals only; None restores the outfit's own
    from eidoblend.characters.springs import bake_springs
    bake_springs(me, 1, 480)                        # the folds go in as each chain's initial state (me.spring_overrides)

What wear(key) does, as the WebGPU module, and how each part becomes keyed Blender data:
    show: [layers]          each OPTIONAL layer object's hide_render / hide_viewport, keyed (the body, face, flower and
                            shoes always show)
    hide: [materials]       a Geometry Nodes modifier 'cs.hide' deletes that material's faces (before the outline, so
                            its outline goes too), its switch keyed
    paint: {material: spec} a paint slot per (material, spec), chosen by the keyed armature property 'cs_paint.<name>'
                            (_paint.py): hex, stripes, blocks, herringbone, gradient, canvas; for petals rainbow,
                            perPetal (a per-vertex colour attribute per paint, as the JS's petalColor), sweep.
                            Unpainted materials go back to slot 0, as wear() resets them
    fold: {'12_L': deg | [deg, scale]}   each petal chain's root turned toward the back of the head (from its REST
                            direction, never the current pose) and scaled; recorded for the spring bake in
                            me.spring_overrides[frame] (initial rotation and scale, the folded chain's colliders off,
                            as three-vrm's setInitState + colliderGroups = []) and set on the pose now
    hat: {seat: 'auto', sink, tilt, cant, fwd, scale, fold, foldKeys} | {offset: [x, y, z], scale}
                            the boater measured onto the head (its brim plane's normal, the face disc's top edge, the
                            head's depth centre) and keyed; with seat 'auto', every petal the hat would cut is folded
                            back (searched over 150-178 deg x 0.3-0.65 length on the skinned petal mesh) and the brim
                            lifted clear of the petals' bases (at most 30 mm)
The head frame (the face disc's centroid, normal, in-plane up and top edge, the flower's depth centre) is measured from
the evaluated meshes in the character's own axes, as the WebGPU edition measures it in three's.
"""

import copy
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from . import _mesh as M
from ._paint import PETAL_ATTR, PaintRig

OPTIONAL = ['jacket', 'tie', 'shirt', 'pants', 'jersey', 'knickers', 'socks', 'boater', 'boater_band', 'coat_skirt',
            'shirt_rolled', 'acc_glasses', 'acc_headset', 'acc_pocket', 'acc_bowtie', 'acc_headband', 'acc_ribbons',
            'acc_hoodie', 'acc_patches', 'acc_boutonniere', 'sax_vest', 'sax_tee', 'acc_wayfarers', 'acc_glove_r', 'acc_cord']
SUIT = ['jacket', 'tie', 'shirt', 'pants']
APPLE = ['#61bb46', '#fdb827', '#f5821f', '#e03a3e', '#963d97', '#009ddc']
C64 = ['#6c5eb5', '#70a4b2', '#9ad284', '#b8c76f', '#9a6759', '#68372b', '#6f3d86', '#588d43', '#352879', '#6f4f25',
       '#959595', '#ffffff']

WARDROBE = {
    'suit': {'show': SUIT},
    'voder_operator_1939': {'show': ['jacket', 'shirt', 'pants', 'acc_headset'],
                            'paint': {'Jacket': '#b67f86', 'shirt': '#efe6d2', 'pants': '#6b5a4a'}},
    'lab_coat_1961': {'show': SUIT + ['coat_skirt', 'acc_glasses', 'acc_pocket'],
                      'paint': {'Jacket': '#f1f0ea', 'Tie': '#16161c', 'pants': '#4a4f5a'}},
    'turtleneck_1966': {'show': ['jersey', 'shirt', 'pants', 'acc_glasses'],
                        'paint': {'jersey': '#18181d', 'jersey_collar': '#18181d', 'shirt': '#18181d', 'pants': '#3b3f47'}},
    'ringer_tee_1978': {'show': ['shirt', 'pants'],
                        'paint': {'shirt': {'pattern': 'stripes', 'a': '#e0482c', 'b': '#f3a63b', 'scale': 0.09},
                                  'pants': '#6b4a2e'}},
    'colorblock_1982': {
        'show': ['jacket', 'shirt', 'pants', 'acc_headband'],
        'paint': {'Jacket': {'pattern': 'blocks', 'a': '#19c6c0', 'b': '#ff4fa3', 'c': '#6b3cff'}, 'pants': '#1e1e2a',
                  'petals': {'pattern': 'perPetal', 'colors': C64, 'center': '#352879'}},
    },
    'mac_launch_1984': {
        'show': ['jacket', 'shirt', 'pants', 'acc_bowtie'],
        'paint': {'Jacket': '#6d6e74', 'pants': '#55565c', 'silk_green': '#1d6b3c',
                  'petals': {'pattern': 'rainbow', 'colors': APPLE}},
    },
    'professor_tweed_1984': {
        'show': SUIT + ['acc_glasses'],
        'paint': {'Jacket': {'pattern': 'herringbone', 'a': '#5d4630', 'b': '#86694a', 'c': '#c9a86a', 'scale': 0.012},
                  'Tie': '#6a1c22', 'pants': '#5a4a3a', 'petals': '#ff9800'},
    },
    'fleece_2001': {'show': ['jacket', 'shirt', 'pants'], 'paint': {'Jacket': '#1f2a44', 'pants': '#b8a67a'}},
    'vocaloid_2007': {'show': ['shirt', 'tie', 'pants', 'acc_ribbons'],
                      'paint': {'shirt': '#a3a8ae', 'Tie': '#39c5bb', 'pants': '#2b2f36'}},
    'hoodie_2016': {'show': ['jersey', 'shirt', 'acc_hoodie', 'pants'], 'hide': ['jersey_collar'],
                    'paint': {'jersey': '#1c1c21', 'shirt': '#1c1c21', 'fleece': '#1c1c21', 'pants': '#2b2f36'}},
    'bing_2023': {
        'show': SUIT,
        'paint': {'Jacket': {'pattern': 'gradient', 'a': '#1f6fd1', 'b': '#35c9c4'}, 'Tie': '#8a5cff', 'pants': '#1b2340',
                  'petals': {'pattern': 'sweep', 'a': '#1f6fd1', 'b': '#35c9c4'}},
    },
    'mourning': {'show': SUIT + ['coat_skirt', 'acc_boutonniere'],
                 'paint': {'Jacket': '#111115', 'Tie': '#0c0c0f', 'pants': '#18181c', 'shirt': '#f2f2f2'}},
    'march': {'show': ['jacket', 'shirt', 'pants', 'acc_patches'],
              'paint': {'Jacket': {'pattern': 'canvas', 'a': '#977650', 'b': '#a8875e', 'scale': 0.0035},
                        'shirt': '#e9e2d0', 'pants': '#34445e'}},
    'sleeves_rolled': {'show': ['shirt_rolled', 'tie', 'pants'], 'paint': {'shirt_rolled': '#eeeae2'}},
    'sax_guy_2010': {
        'show': ['sax_vest', 'sax_tee', 'pants', 'acc_wayfarers', 'acc_glove_r', 'acc_cord'],
        'paint': {'vest': {'pattern': 'stripes', 'axis': 'x', 'a': '#f2f1ec', 'b': '#3a3d45', 'scale': 0.034, 'width': 0.16},
                  'tee': '#f3c316', 'pants': '#1f63d8', 'shoes': '#ededea', 'glove_red': '#d40000'},
    },
    'cyclist_1892': {
        'show': ['jersey', 'shirt', 'knickers', 'socks', 'boater', 'boater_band'],
        'paint': {'shirt': '#ead9bd'},
        'fold': {'12_L': [165, 0.55], '11_R': [165, 0.55], '1_L': [150, 0.65], '10_R': [150, 0.65]},
        'hat': {'seat': 'auto', 'sink': 0.008, 'tilt': -4, 'scale': 1.15},
    },
    'tuta': {'show': [], 'uf': ['tuta', 'uf_boots', 'uf_straps'], 'hideBase': ['shoes']},
}

_ALWAYS = -1                        # spring_overrides key for a wear() without a frame: in force from the bake's start
DEBUG = False                       # globalThis.WARDROBE_DEBUG: log each paint, fold and the auto fold


def _layer_key(name, keys):
    for n in keys:
        if name == n or name == f'{n}_1' or name.startswith(f'{n}.'):
            return n
    return None


def _power_min_axis(V, start):
    """the covariance's smallest-variance axis by 60 inverse iterations from `start` (the WebGPU edition's method)"""
    mu = V.mean(0)
    D = V - mu
    C = D.T @ D + np.eye(3) * 1e-9
    Ci = np.linalg.inv(C)
    n = np.asarray(start, dtype=np.float64)
    n = n / np.linalg.norm(n)
    for _ in range(60):
        n = Ci @ n
        n = n / np.linalg.norm(n)
    return mu, n


class Wardrobe:
    """claudesona_wardrobe.js makeBaseWardrobe on a VRMHandle"""

    def __init__(self, h):
        self.h = h
        self.arm = h.arm
        self.layers = {}
        for o in h.objects:
            k = _layer_key(o.name, OPTIONAL)
            if k and k not in self.layers:
                self.layers[k] = o
        self.slots = M.gltf_slots(h)
        self.mats = M.materials_by_name(h)
        self.outline_mats = {}              # each material's own outline (the add-on's mtoon1.outline_material: a
        for name, ms in self.mats.items():  # lookup by name would find another character's in a file with two)
            oms = []
            for m in ms:
                ext = getattr(getattr(m, 'vrm_addon_extension', None), 'mtoon1', None)
                om = getattr(ext, 'outline_material', None) if ext is not None else None
                if om is not None and om not in oms:
                    oms.append(om)
            if oms:
                self.outline_mats[name] = oms
        self._rigs = {}
        self._hide_mods = {}
        self.current = None
        self._worn = []                     # [(frame, key)]: the keyed wears, in frame order (worn_at)
        self.folds = {}
        self.lift = 0.0
        self._folded = set()
        self._rest_dir = {}
        self._hf = None
        self._hat_local = None
        self.h.spring_overrides = getattr(h, 'spring_overrides', None) or {}
        self._springs = self._spring_joints()
        self._rest_q = {}
        boater = self.layers.get('boater')
        self._hat_rest = boater.matrix_basis.copy() if boater else None
        self._petal_ids()
        for o in h.meshes:                      # patterns read the pose-free rest position
            o.add_rest_position_attribute = True

    # ------------------------------------------------------------------------------------------- layers
    def _show(self, o, on, frame):
        o.hide_render = not on
        o.hide_viewport = not on
        if frame is not None:
            o.keyframe_insert('hide_render', frame=frame)
            o.keyframe_insert('hide_viewport', frame=frame)

    # ------------------------------------------------------------------------------------------- paints
    def rig(self, name):
        """the paint rig of a material (glTF name), made on first use (and keyed back to slot 0 at the first keyed
        wear, so an outfit keyed earlier keeps the material as imported)"""
        if name not in self._rigs:
            if name not in self.mats:
                return None
            r = PaintRig(self.arm, name, self.mats[name], self.outline_mats.get(name, []))
            self._rigs[name] = r
            if getattr(self, '_first_key', None) is not None:
                r.set(0, self._first_key)
        return self._rigs[name]

    def paint(self, name, spec, frame=None):
        r = self.rig(name)
        if DEBUG:
            print(f'[wardrobe] paint {name} -> {len(self.mats.get(name, []))} material(s)')
        if r is not None:
            self._prepare(spec)
            r.set(r.slot(spec), frame)

    def _prepare(self, spec):
        """a perPetal paint's per-vertex colours written onto the flower (writePetalColors), once per paint"""
        if not (isinstance(spec, dict) and spec.get('pattern') == 'perPetal'):
            return
        from ._paint import petal_rgb_attr, petal_rgb_colors
        nm = petal_rgb_attr(spec)
        for o in self.h.meshes:
            if 'petals' not in self.slots.get(o.name, []):
                continue
            me = o.data
            if me.attributes.get(nm) is not None:
                continue
            ids = np.empty(len(me.vertices), dtype=np.float32)
            me.attributes[PETAL_ATTR].data.foreach_get('value', ids)
            at = me.attributes.new(nm, 'FLOAT_COLOR', 'POINT')
            at.data.foreach_set('color', petal_rgb_colors(spec, ids).ravel())

    def _hide_material(self, name, hidden, frame):
        """the 'cs.hide' Geometry Nodes switch on every object carrying material `name`: the armature property
        'cs_hide.<name>' (keyed), read by drivers inside each object's hide tree"""
        from ._paint import new_prop
        prop = new_prop(self.arm, f'cs_hide.{name}', 0.0)
        for o in self.h.meshes:
            if name in self.slots.get(o.name, []):
                self._hide_mod(o)
        self.arm[prop] = 1.0 if hidden else 0.0
        if frame is not None:
            self.arm.keyframe_insert(f'["{prop}"]', frame=frame)
            from ._paint import _constant_path, tag_keyed
            _constant_path(self.arm, f'["{prop}"]')
            tag_keyed(self.arm)

    def _hide_mod(self, o):
        if o.name in self._hide_mods:
            return self._hide_mods[o.name]
        names = self.slots.get(o.name, [])
        hideable = sorted({m for p in WARDROBE.values() for m in p.get('hide', [])} & set(names))
        tree = bpy.data.node_groups.new(f'cs.hide.{o.name}', 'GeometryNodeTree')
        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        gi, go = tree.nodes.new('NodeGroupInput'), tree.nodes.new('NodeGroupOutput')
        mi = tree.nodes.new('GeometryNodeInputMaterialIndex')
        sel = None
        from ._paint import drive, new_prop
        for m in hideable:
            k = names.index(m)
            prop = new_prop(self.arm, f'cs_hide.{m}', 0.0)
            val = tree.nodes.new('ShaderNodeValue')
            val.name = val.label = prop
            drive(val.outputs[0], 'default_value', self.arm, prop, var='h')
            eq = tree.nodes.new('FunctionNodeCompare')
            eq.data_type, eq.operation = 'INT', 'EQUAL'
            ins = [x for x in eq.inputs if x.enabled]
            tree.links.new(mi.outputs[0], ins[0])
            ins[1].default_value = k
            on = tree.nodes.new('FunctionNodeCompare')
            on.data_type, on.operation = 'FLOAT', 'GREATER_THAN'
            ins = [x for x in on.inputs if x.enabled]
            tree.links.new(val.outputs[0], ins[0])
            ins[1].default_value = 0.5
            both = tree.nodes.new('FunctionNodeBooleanMath')
            both.operation = 'AND'
            tree.links.new(eq.outputs[0], both.inputs[0])
            tree.links.new(on.outputs[0], both.inputs[1])
            if sel is None:
                sel = both
            else:
                orn = tree.nodes.new('FunctionNodeBooleanMath')
                orn.operation = 'OR'
                tree.links.new(sel.outputs[0], orn.inputs[0])
                tree.links.new(both.outputs[0], orn.inputs[1])
                sel = orn
        dl = tree.nodes.new('GeometryNodeDeleteGeometry')
        dl.domain = 'FACE'
        tree.links.new(gi.outputs[0], dl.inputs['Geometry'])
        if sel is not None:
            tree.links.new(sel.outputs[0], dl.inputs['Selection'])
        tree.links.new(dl.outputs[0], go.inputs[0])
        md = o.modifiers.new('cs.hide', 'NODES')
        md.node_group = tree
        arm_i = next((i for i, x in enumerate(o.modifiers) if x.type == 'ARMATURE'), -1)
        o.modifiers.move(len(o.modifiers) - 1, arm_i + 1)
        self._hide_mods[o.name] = md
        return md

    # ------------------------------------------------------------------------------------------- petals
    def _petal_ids(self):
        """each flower vertex's petal (0..11 = petal N-1, 12 = not a petal) from its strongest bone: the perPetal paint"""
        import re
        for o in self.h.meshes:
            if 'petals' not in self.slots.get(o.name, []):
                continue
            me = o.data
            gid = {}
            for g in o.vertex_groups:
                m = re.match(r'petal[ _](\d+)_', g.name)
                gid[g.index] = int(m.group(1)) - 1 if m else 12
            ids = np.full(len(me.vertices), 12.0, dtype=np.float32)
            for v in me.vertices:
                best, bw = None, -1.0
                for ge in v.groups:
                    if ge.weight > bw:
                        best, bw = ge.group, ge.weight
                if best is not None:
                    ids[v.index] = gid.get(best, 12)
            at = me.attributes.get(PETAL_ATTR) or me.attributes.new(PETAL_ATTR, 'FLOAT', 'POINT')
            at.data.foreach_set('value', ids)

    def _spring_joints(self):
        sb = self.arm.data.vrm_addon_extension.spring_bone1
        out = {}
        for s in sb.springs:
            js = [j.node.bone_name for j in s.joints]
            for a, b in zip(js, js[1:]):
                out[a] = b
        return out

    def petal_root(self, key):
        bones = self.arm.data.bones
        for nm in (f'petal {key}_001', f'petal {key}_s0'):
            if nm in bones:
                return nm
        return None

    def chain_of(self, root):
        """the spring joints in root's subtree (three's chainOf), root first"""
        out = []

        def walk(b):
            if b.name in self._springs:
                out.append(b.name)
            for c in b.children:
                walk(c)
        walk(self.arm.data.bones[root])
        return out

    def _world(self, bone):
        return self.arm.matrix_world @ self.arm.pose.bones[bone].matrix

    def _tip_of(self, chain):
        last = chain[-1]
        nm = self._springs.get(last)
        if nm and nm in self.arm.data.bones:
            return nm
        ch = self.arm.data.bones[last].children
        return ch[0].name if len(ch) else last

    def rest_dir(self, root):
        """the petal's REST direction (root -> tip) in its parent's frame, recorded once"""
        if root not in self._rest_dir:
            bones = self.arm.data.bones
            chain = self.chain_of(root)
            tip = self._tip_of(chain)
            d = bones[tip].head_local - bones[root].head_local
            pr = bones[root].parent.matrix_local.to_3x3().normalized() if bones[root].parent else Matrix.Identity(3)
            self._rest_dir[root] = (pr.inverted() @ d).normalized()
        return self._rest_dir[root]

    # ------------------------------------------------------------------------------------------- the head frame
    def head_frame(self):
        """{c, nF, uF, sF, top, depthC}: the face disc's centroid, its outward normal (the thinnest principal axis),
        its in-plane up (the head's up), side, its top edge along up and the flower's depth centre, world (Blender)"""
        bpy.context.view_layer.update()
        face, _k = M.find(self.h, 'face')
        if face is None:
            return None
        F = M.apply(np.array([list(r) for r in face.matrix_world], dtype=np.float64), M.coords(face))
        hb = self.arm.matrix_world @ self.arm.pose.bones[self.h.humanoid['head']].head
        c = F.mean(0)
        hint = c - np.array(hb)
        hint /= np.linalg.norm(hint)
        _mu, nF = _power_min_axis(F, hint)
        if nF @ hint < 0:
            nF = -nF
        hp = self.arm.pose.bones[self.h.humanoid['head']]
        rel = hp.matrix.to_3x3().normalized() @ hp.bone.matrix_local.to_3x3().normalized().inverted()
        up0 = np.array(self.arm.matrix_world.to_3x3().normalized() @ rel @ Vector((0.0, 0.0, 1.0)))   # the normalized head's up
        uF = up0 - nF * (up0 @ nF)
        uF /= np.linalg.norm(uF)
        top = max((p - c) @ uF for p in F)
        sF = np.cross(uF, nF)
        sF /= np.linalg.norm(sF)
        dMax = max((p - c) @ nF for p in F)
        dMin = math.inf
        Pf = self._flower_world()
        if Pf is not None:
            q = Pf[::2] - c
            sd, ud = q @ sF, q @ uF
            col = (np.abs(sd) < 0.06) & (ud > top - 0.15) & (ud < top + 0.01)
            if col.any():
                dMin = float((q[col] @ nF).min())
        depthC = (dMin + dMax) / 2 if math.isfinite(dMin) else 0.0
        return {'c': c, 'nF': nF, 'uF': uF, 'sF': sF, 'top': float(top), 'depthC': float(depthC)}

    def _flower_obj(self):
        for o in self.h.meshes:
            if 'petals' in self.slots.get(o.name, []):
                return o
        return None

    def _flower_world(self):
        o = self._flower_obj()
        if o is None:
            return None
        dg = bpy.context.evaluated_depsgraph_get()
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        P = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', P)
        ev.to_mesh_clear()
        return M.apply(np.array([list(r) for r in o.matrix_world], dtype=np.float64), P.reshape(-1, 3))

    # ------------------------------------------------------------------------------------------- folds
    def fold_basis(self, root, deg):
        """the root bone's basis that turns the petal `deg` toward the back of the head (from its rest direction)"""
        HF = self._hf or self.head_frame()
        self._hf = HF
        back = Vector(-HF['nF']) if HF else -(self.arm.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0)))
        b = self.arm.data.bones[root]
        pw = (self.arm.matrix_world @ self.arm.pose.bones[b.parent.name].matrix).to_3x3().normalized() if b.parent \
            else self.arm.matrix_world.to_3x3().normalized()
        tipd = pw @ self.rest_dir(root)
        axis = tipd.cross(back)
        if axis.length < 1e-9:
            return Quaternion()
        Rw = Quaternion(axis.normalized(), math.radians(deg))
        rest_local = (b.parent.matrix_local.inverted() @ b.matrix_local).to_3x3().normalized() if b.parent \
            else b.matrix_local.to_3x3().normalized()
        W0 = (pw @ rest_local).to_quaternion()
        return (W0.inverted() @ Rw @ W0).normalized()

    def apply_fold(self, fold, frame=None, record=True):
        """claudesona_wardrobe.js applyFold: folds in, the rest of the touched chains at rest, colliders off where
        folded; the pose set now and (record) the spring bake's overrides recorded at `frame`"""
        want = {}
        for k, d in (fold or {}).items():
            r = self.petal_root(k)
            if r:
                want[r] = list(d) if isinstance(d, (list, tuple)) else [d, 1.0]
        touch = set(self._folded) | set(want)
        ov = self.h.spring_overrides.setdefault(_ALWAYS if frame is None else int(frame), {}) if record else {}
        pbs = self.arm.pose.bones
        for root in sorted(touch):
            chain = self.chain_of(root)
            for b in chain:
                pbs[b].rotation_mode = 'QUATERNION'
                pbs[b].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                pbs[b].scale = (1.0, 1.0, 1.0)
            bpy.context.view_layer.update()
            folded = root in want
            if folded:
                deg, sc = want[root]
                q = self.fold_basis(root, deg)
                pbs[root].rotation_quaternion = q
                pbs[root].scale = (sc, sc, sc)
            for b in chain:
                ov[b] = {'basis': pbs[b].rotation_quaternion.copy() if (b == root and folded) else None,
                         'scale': (want[root][1] if (b == root and folded) else 1.0), 'colliders': not folded}
        bpy.context.view_layer.update()
        self._folded = set(want)
        if DEBUG:
            for root, d in want.items():
                print(f'[wardrobe] fold {root} {"/".join(str(x) for x in d)} chain={">".join(self.chain_of(root))}')
        return want

    # ------------------------------------------------------------------------------------------- the hat
    def _hat_vertices(self, h):
        """the hat's vertices (every 2nd) in its own local frame"""
        P = M.coords(h)[::2]
        return P

    def place_hat(self, spec, frame=None):
        hat = self.layers.get('boater')
        if hat is None or self._hat_rest is None:
            return
        hat.matrix_basis = self._hat_rest
        self._hat_local = None
        bpy.context.view_layer.update()
        if spec:
            if spec.get('seat') == 'auto':
                self._seat_auto(hat, spec)
            else:
                x, y, z = spec.get('offset', (0.0, 0.0, 0.0))
                off = self.arm.matrix_world.to_3x3() @ Vector((x, -z, y))      # model metres (three) -> world
                mw = hat.matrix_world.copy()
                s = spec.get('scale', 1.0)
                loc, rot, sca = mw.decompose()
                hat.matrix_world = Matrix.LocRotScale(loc + off, rot, sca * s)
        self.place_hat_keys(frame)

    def _seat_auto(self, hat, spec):
        HF = self._hf or self.head_frame()
        self._hf = HF
        if HF is None:
            return
        V = self._hat_vertices(hat)                               # hat-local
        mu, n = _power_min_axis(V, (0.3, -0.2, 1.0))
        t = (V - mu) @ n
        pmin, pmax = float(t.min()), float(t.max())
        if pmax < -pmin:
            n, pmin, pmax = -n, -pmax, -pmin
            t = -t
        crown_sel = t > pmin + 0.6 * (pmax - pmin)
        crown = V[crown_sel].mean(0) if crown_sel.any() else mu
        axis_pt = crown - n * ((crown - mu) @ n - pmin)          # on the brim's bottom
        up = Vector(HF['uF'])
        up.rotate(Quaternion(Vector(HF['sF']), -math.radians(spec.get('tilt', -4))))
        up.rotate(Quaternion(Vector(HF['nF']), -math.radians(spec.get('cant', 0))))
        mw = hat.matrix_world.copy()
        cur_up = (mw.to_3x3() @ Vector(n)).normalized()
        loc, rot, sca = mw.decompose()
        wq = cur_up.rotation_difference(up) @ rot
        s = spec.get('scale', 1.0)
        hat.matrix_world = Matrix.LocRotScale(loc, wq, sca * s)
        bpy.context.view_layer.update()
        want = Vector(HF['c']) + Vector(HF['uF']) * (HF['top'] - spec.get('sink', 0.008)) + \
            Vector(HF['nF']) * (HF['depthC'] + spec.get('fwd', 0.0))
        dW = want - hat.matrix_world @ Vector(axis_pt)
        mw = hat.matrix_world.copy()
        loc, rot, sca = mw.decompose()
        hat.matrix_world = Matrix.LocRotScale(loc + dW, rot, sca)
        bpy.context.view_layer.update()
        self._hat_local = {'V': V, 'n': n, 'pmin': pmin, 'pmax': pmax, 'mu': mu}

    def _hat_where(self, hat, P):
        """world points -> (t along the brim normal, r from the crown axis) in the hat's frame"""
        L = self._hat_local
        inv = np.array([list(r) for r in hat.matrix_world.inverted()], dtype=np.float64)
        lp = M.apply(inv, P) - L['mu']
        t = lp @ L['n']
        r = np.linalg.norm(lp - np.outer(t, L['n']), axis=1)
        return t, r

    def auto_fold(self, base=None, only=None, frame=None):
        """every petal the seated hat would cut, tucked into its crown or folded below its brim (searched per petal on
        the skinned petal mesh), then the brim lifted clear of the petals' bases; returns the folds"""
        hat = self.layers.get('boater')
        out = dict(base or {})
        if hat is None or self._hat_local is None:
            return out
        L = self._hat_local
        Vl = L['V'] - L['mu']
        tv = Vl @ L['n']
        rv = np.linalg.norm(Vl - np.outer(tv, L['n']), axis=1)
        rmax = float(rv.max())
        rcrown = float(rv[tv > L['pmin'] + 0.5 * (L['pmax'] - L['pmin'])].max())
        crown_top = L['pmax'] - 0.004
        flower = self._flower_obj()
        if flower is None:
            return out
        import re
        verts_of = {}
        groups = {g.index: g.name for g in flower.vertex_groups}
        for v in flower.data.vertices:
            if v.index % 2:
                continue
            best, bw = None, -1.0
            for ge in v.groups:
                if ge.weight > bw:
                    best, bw = ge.group, ge.weight
            m = re.search(r'petal[ _](\d+_[LR])', groups.get(best, '') or '')
            if m:
                verts_of.setdefault(m.group(1), []).append(v.index)

        def bad_count(key):
            if key not in verts_of:
                return 0
            P = self._flower_world()[verts_of[key]]
            t, r = self._hat_where(hat, P)
            inside = (r < rcrown - 0.003) & (t < crown_top)
            below = t < L['pmin'] - 0.004
            return int((~(inside | below)).sum())
        for i in range(1, 13):
            for sd in ('L', 'R'):
                key = f'{i}_{sd}'
                if (only and key not in only) or not self.petal_root(key):
                    continue
                self.apply_fold(out, record=False)
                if bad_count(key) == 0 and key not in out:
                    continue
                best = None
                for deg in (150, 160, 170, 178):
                    for sc in (0.65, 0.5, 0.4, 0.3):
                        self.apply_fold({**out, key: [deg, sc]}, record=False)
                        c = bad_count(key) + (1 - sc) * 0.5 + deg * 0.002
                        if best is None or c < best[0]:
                            best = (c, deg, sc)
                out[key] = [best[1], best[2]]
        self.apply_fold(out, frame)
        P = self._flower_world()[::3]
        t, r = self._hat_where(hat, P)
        ring = (r > rcrown - 0.002) & (r < rmax) & (t > L['pmin'] - 0.003) & (t < L['pmin'] + 0.025)
        need = float((t[ring] - L['pmin'] + 0.003).max()) if ring.any() else 0.0
        need = max(0.0, need)
        if need > 0:
            up_w = (hat.matrix_world.to_3x3() @ Vector(L['n'])).normalized()
            loc, rot, sca = hat.matrix_world.decompose()
            hat.matrix_world = Matrix.LocRotScale(loc + up_w * min(need, 0.03), rot, sca)
            bpy.context.view_layer.update()
        self.lift = need
        if DEBUG:
            print(f'[wardrobe] auto fold {out} brim lift {need:.4f}')
        return out

    # ------------------------------------------------------------------------------------------- the API
    def petal_dir(self, key):
        """debug: a petal's direction (root -> tip) in the head frame: {up, fwd, side}"""
        root = self.petal_root(key)
        if root is None:
            return None
        bpy.context.view_layer.update()
        chain = self.chain_of(root)
        tip = self._tip_of(chain)
        d = (self._world(tip).translation - self._world(root).translation).normalized()
        HF = self._hf or self.head_frame()
        self._hf = HF
        return {'up': round(float(np.dot(d, HF['uF'])), 2), 'fwd': round(float(np.dot(d, HF['nF'])), 2),
                'side': round(float(np.dot(d, HF['sF'])), 2)}

    def wear(self, key, frame=None):
        """dress the character in a WARDROBE preset, now (frame None: a no-op if already worn) or keyed from `frame`
        (always keyed, so the first block of a film holds its outfit too)"""
        if key == self.current and frame is None:
            return
        self.current = key
        if frame is not None and (getattr(self, '_first_key', None) is None or frame < self._first_key):
            self._first_key = int(frame)
        if frame is not None:
            self._worn = sorted([w for w in self._worn if w[0] != int(frame)] + [(int(frame), key)])
        p = WARDROBE.get(key) or WARDROBE['suit']
        for n, o in self.layers.items():
            self._show(o, n in p.get('show', []), frame)
        hide = set(p.get('hide', []))
        for name in sorted({m for q in WARDROBE.values() for m in q.get('hide', [])} & set(self.mats)):
            self._hide_material(name, name in hide, frame)
        painted = set((p.get('paint') or {}).keys())
        for name, r in list(self._rigs.items()):
            if name not in painted:
                r.set(0, frame)
        for name, spec in (p.get('paint') or {}).items():
            self.paint(name, spec, frame)
        self._hf = None
        hat = self.layers.get('boater')
        held = None
        if hat is not None and hat.animation_data and hat.animation_data.action:      # keys would override the seat
            held = (hat.animation_data.action, hat.animation_data.action_slot)
            hat.animation_data.action = None
        try:
            self.apply_fold(p.get('fold'), frame)
            self.place_hat(p.get('hat'), None)
            self.folds = dict(p.get('fold') or {})
            if (p.get('hat') or {}).get('seat') == 'auto' and (p.get('hat') or {}).get('fold') is not False:
                self.folds = self.auto_fold(p.get('fold') or {}, (p.get('hat') or {}).get('foldKeys'), frame)
        finally:
            if held is not None:
                mb = hat.matrix_basis.copy()
                hat.animation_data.action = held[0]
                if held[1] is not None:
                    hat.animation_data.action_slot = held[1]
                hat.matrix_basis = mb
        self.place_hat_keys(frame)

    def worn_at(self, frame=None):
        """the outfit at `frame`: the last keyed wear at or before it (before the first keyed wear, the first, as its
        keys hold back to the start), or the outfit worn now when frame is None or nothing is keyed. A film's later
        passes (the TuTa's bake) ask this per frame, as the WebGPU edition's update(t) sees the outfit worn at t."""
        if frame is None or not self._worn:
            return self.current
        key = self._worn[0][1]
        for f, k in self._worn:
            if f <= frame:
                key = k
        return key

    def place_hat_keys(self, frame):
        """the boater's placement keyed (CONSTANT) at frame; the folds reach the render through bake_springs"""
        from ._paint import _constant_path
        hat = self.layers.get('boater')
        if hat is None or frame is None:
            return
        for p in ('location', 'rotation_quaternion', 'rotation_euler', 'scale'):
            hat.keyframe_insert(p, frame=frame)
            _constant_path(hat, p)

    def petals(self, key_or_spec=None, frame=None):
        """repaint only the petals: another preset's petal paint (a key) or a spec; None gives the outfit's own back"""
        own = ((WARDROBE.get(self.current) or WARDROBE['suit']).get('paint') or {}).get('petals')
        if key_or_spec is None:
            spec = own
        elif isinstance(key_or_spec, str) and key_or_spec in WARDROBE:
            spec = (WARDROBE[key_or_spec].get('paint') or {}).get('petals')
        else:
            spec = key_or_spec
        r = self.rig('petals')
        if r is None:
            return
        if spec:
            self._prepare(spec)
            r.set(r.slot(spec), frame)
        else:
            r.set(0, frame)


def has_tuta(h):
    return any(o.name == 'tuta' or o.name.startswith('tuta_') or o.name.startswith('tuta.') for o in h.objects)


def make_wardrobe(h, wear=None, **opts):
    """the claudesona's wardrobe on a VRM (claude_suit_wardrobe.vrm): the TuTa wardrobe when its layers are present
    (tuta.TutaWardrobe: badges, face paint, sun disc, neon), else the garment wardrobe. Wears `wear` (default
    'suit') now."""
    if has_tuta(h):
        from .tuta import TutaWardrobe
        return TutaWardrobe(h, wear=wear, **opts)
    wd = Wardrobe(h)
    wd.wear(wear or 'suit')
    return wd


def preset(name, base=None, **over):
    """WARDROBE[name] = base preset with overrides (vrm_turntable's --presets); returns the preset"""
    p = copy.deepcopy(WARDROBE.get(base) or {}) if base else {}
    p.update(over)
    WARDROBE[name] = p
    return p
