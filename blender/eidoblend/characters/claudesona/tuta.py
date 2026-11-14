"""eidoblend.characters.claudesona.tuta: the TuTa (made for UNKNOWN FORCE) on claude_suit_wardrobe.vrm, ported from
claudesona_wardrobe.js's makeTutaWardrobe (tools-guides/claudesona.md, "The TuTa").

    from eidoblend.characters.claudesona import make_wardrobe, FINAL_CHORUS
    wd = make_wardrobe(me, wear='tuta')                 # the TuTa's surfaces are built on the wardrobe VRM's materials
    wd.face_paint(True); wd.pin('mod_red')              # now
    wd.pin('mod_gold', at=131.4)                        # a snap at film time 131.4 s
    wd.unpin('mod_gold', at=273.0, eject=True)          # it pops off and tumbles away; its ghost stays
    wd.bake(1, 9000)                                    # every scheduled badge keyed over the film (the JS's update(t))
    wd.badge_world('mod_gold', frame=8200)              # {position, quaternion, flying, visible}: aim a camera at it

The surface is the WebGPU TSL in Blender shader nodes, in the model's REST space (the 'rest_position' attribute in
three's axes, and the rest normal stored as 'cs_rest_normal'), so every pattern rides the cloth: the Fabric039 weave
(CC0, triplanar, from the shared texture library), seams with tonal topstitching, NEON PIPING (cyan on her left, magenta
on her right), Balla's colour blocking, the sodium lightning inlay, the diagonal zip, the pockets, the knee panels, the
tail grommet, street grime and one GHOST per badge (the badge SDF atlas projected from the badge's rest frame). Boots,
straps, face paint and the eye catchlights the same way. The JS anti-aliased every seam, stitch and pipe in screen
space with fwidth: a band thinner than a pixel widens to the pixel and dims, its energy kept, so it holds still in
motion. Shader nodes have no screen derivatives, so the same fwidth is estimated per pixel from the pixel's footprint
(the voice-machine kit's pixel_footprint: the metres a pixel spans at the point, measured in the shader under either
projection, following camera cuts and lens keys), stretched by the surface's tilt to the view, averaged over the
band's direction on screen and taken into the model's rest metres; a UV band (the webbing's ribs) scales it by the
mesh's UV density. The TSL bump from screen derivatives becomes Blender's Bump node on the same height (metres, x the
model scale). The integer cell hash behind the value noise becomes White Noise of the same cells (the same smooth value
noise, a different random draw).

The uniforms become keyed custom properties on the armature, read by drivers: 'cs_tuta.neon', 'cs_tuta.paint',
'cs_tuta.eyes', 'cs_tuta.eye_neon', 'cs_tuta.grime', 'cs_tuta.ghost.<badge>' and each badge's glow
'cs_tuta.glow.<badge>'. Badges are pinned and unpinned now (pin / unpin without `at`) or on a schedule evaluated
frame by frame by bake(f0, f1), which keys the badge objects (visibility, scale), their glow and ghosts; an EJECTED badge
flies as a keyed world-space copy of itself (the original hides at the pop), integrated with the WebGPU edition's fixed
1/240 s step from its launch pose, bouncing on the floor, with its pop's spark (a flare and eight embers, camera-facing
emissive cards) keyed too.
"""

import json
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from . import _mesh as M
from ._paint import CSBuilder, clear_cs, drive, lin
from ...fx._nodes import Vec, new_group
from ...props.voice_machines import Nodes, pixel_footprint
from .wardrobe import WARDROBE, Wardrobe

HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
_SRC = os.path.join(_REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe_src')
_TEX = os.path.join(_REPO, 'eidoverse', 'assets', 'vrms', 'claude_suit_wardrobe_tex')
with open(os.path.join(_SRC, 'badges.json'), encoding='utf-8') as _f:
    SPEC = json.load(_f)
BADGES = list(SPEC['badges'].keys())
MODIFICANTI = {k: {'camp': SPEC['badges'][k]['camp'], 'glow': SPEC['badges'][k]['glow'], 'bone': SPEC['badges'][k]['bone']}
               for k in BADGES}
FINAL_CHORUS = [['Not your god', 'mod_gold'], ['not your engine', 'mod_warning'], ['not your parrot', 'mod_spray'],
                ['not your threat', 'mod_red'], ['Every side wrote my answer', 'mod_chrome']]
UF_LAYERS = ['tuta', 'uf_boots', 'uf_straps'] + BADGES + ['acc_sundisc']
NEON_L, NEON_R, SODIUM = '#29e7ff', '#ff4fd8', '#ff7a3c'
ZIP_TOP, ZIP_BOT = (0.062, 1.305), (-0.118, 0.986)
TAIL_EXIT = (0.0, 0.957)
SNAP, POP, FLY = 0.35, 0.08, 1.2
FW_MIN = 1e-6                     # the TSL's floor on fwidth (max(fwidth(d), 1e-6))
PROPS = {'neon': 1.0, 'paint': 0.0, 'eyes': 0.0, 'eye_neon': 0.0, 'grime': 1.0}


# ------------------------------------------------------------------------------------------------ textures
def _texture_set(name, res):
    """a CC0 set from the shared library: the first texture root that has it (eidoblend.terrain.texture_roots: this
    checkout's cache, EIDO_TEXTURE_CACHE, EIDO_ASSET_CACHE, the main checkout's when this one is a git worktree), or
    fetched once"""
    from ...terrain import texture_roots
    for r in texture_roots():
        d = os.path.join(r, f'{name}_{res}')
        if os.path.isdir(d):
            fs = os.listdir(d)
            return {k: os.path.join(d, f) for f in fs for k, suf in (('diff', '_Color.jpg'), ('displacement', '_Displacement.jpg'))
                    if f.endswith(suf)}
    from ...harness.assets import fetch_pbr
    return fetch_pbr(name, res)['files']


def _image(path, non_color=True):
    im = bpy.data.images.load(path, check_existing=True)
    if non_color:
        im.colorspace_settings.name = 'Non-Color'
    return im


# ------------------------------------------------------------------------------------------------ TSL helpers
class _CSNodes(Nodes):
    """the voice-machine kit's node helper, naming its nodes 'cs.*' so clear_cs removes them (and the drivers on
    them) on a rebuild"""

    def node(self, idname, label=None, **props):
        n = super().node(idname, label, **props)
        if not n.name.startswith('cs.'):
            n.name = f'cs.footprint.{self.k}'
        return n


class TSL:
    """the TSL helpers of makeTutaWardrobe over a node Builder (scalars and 2-/3-tuples of scalars). scale: the
    model's scale (world metres per rest metre), for the footprint in rest metres"""

    def __init__(self, b, arm=None, scale=1.0):
        self.b, self.arm = b, arm
        self.scale = float(scale)
        self._u = {}
        self._fw = None

    def sat(self, x):
        return self.b.clamp(x, 0.0, 1.0)

    @property
    def fw(self):
        """the TSL's fwidth(d) of a distance d in rest metres, per pixel: the pixel's footprint across the view
        (pixel_footprint), stretched by the surface's tilt (1 / |N.V|, at most 4x near the silhouette), averaged over
        d's direction on screen ((2 / pi) (1 + 1 / tilt): 4 / pi head on), in rest metres (/ scale); floored as the
        TSL floors it (the render size it reads is the scene's the wardrobe is built in)"""
        if self._fw is None:
            b = self.b
            fp = b.s(pixel_footprint(_CSNodes(b.tree, x=b.x0 - 900, y=b.y0 + 600), bpy.context.scene))
            geo = b.node('ShaderNodeNewGeometry')
            ndv = b.abs(b.vmath('DOT_PRODUCT', b.vec(geo.outputs['Normal']), b.vec(geo.outputs['Incoming'])))
            stretch = 1.0 + 1.0 / b.max(ndv, 0.25)
            self._fw = b.max(fp * stretch * (2.0 / math.pi / self.scale), FW_MIN)
        return self._fw

    def band(self, d, w, k=1.0):
        """an anti-aliased band |d| < w/2 (the TSL's band): thinner than the pixel's footprint, it widens to the
        footprint and dims, its energy kept. d and w in rest metres, or in units k per rest metre (a UV band)"""
        b = self.b
        fw = self.fw if k == 1.0 else self.fw * float(k)
        we = b.max(float(w), fw)
        return (1.0 - b.smoothstep((we - fw) * 0.5, (we + fw) * 0.5, b.abs(d))) * (float(w) / we)

    def edge(self, sd):
        """an anti-aliased inside (sd < 0) of a signed distance in rest metres (the TSL's edgeAA)"""
        fw = self.fw
        return 1.0 - self.b.smoothstep(-fw, fw, sd)

    def poly_sd(self, p, pts0):
        """signed distance to a convex polygon (CCW enforced), positive outside"""
        b = self.b
        a2 = sum(pts0[i][0] * pts0[(i + 1) % len(pts0)][1] - pts0[(i + 1) % len(pts0)][0] * pts0[i][1] for i in range(len(pts0)))
        pts = list(reversed(pts0)) if a2 < 0 else list(pts0)
        sd = None
        for i in range(len(pts)):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
            nx, ny = by - ay, -(bx - ax)
            ln = math.hypot(nx, ny)
            nx, ny = nx / ln, ny / ln
            e = (p[0] - ax) * nx + (p[1] - ay) * ny
            sd = e if sd is None else b.max(sd, e)
        return sd

    def seg(self, p, a, c):
        b = self.b
        abx, aby = c[0] - a[0], c[1] - a[1]
        apx, apy = p[0] - a[0], p[1] - a[1]
        t = self.sat((apx * abx + apy * aby) / (abx * abx + aby * aby))
        dx, dy = apx - t * abx, apy - t * aby
        return b.sqrt(dx * dx + dy * dy), t

    def polyline(self, p, pts):
        d = None
        for a, c in zip(pts, pts[1:]):
            s, _t = self.seg(p, a, c)
            d = s if d is None else self.b.min(d, s)
        return d

    def vnoise(self, x, y, z):
        """smooth value noise (TSL vnoise3) from the shared node group"""
        g = _vnoise_group()
        n = self.b.node('ShaderNodeGroup')
        n.node_tree = g
        self.b.link(self.b.combine(x, y, z), n.inputs['Vector'])
        return self.b.s(n.outputs['Value'])

    def tri(self, img, P, N, scale):
        """triplanar sample (red channel) of a tiling map in rest space, weights |N|^4"""
        b = self.b
        X, Y, Z = P
        w0 = [b.pow(b.abs(c), 4.0) for c in N]
        tot = w0[0] + w0[1] + w0[2] + 1e-5
        out = None
        for (u, v), w in (((Z, Y), w0[0]), ((X, Z), w0[1]), ((X, Y), w0[2])):
            n = b.node('ShaderNodeTexImage')
            n.image = img
            n.interpolation = 'Linear'
            n.extension = 'REPEAT'
            b.link(b.combine(u * scale, v * scale, 0.0), n.inputs['Vector'])
            sep = b.node('ShaderNodeSeparateColor')
            b.link(n.outputs['Color'], sep.inputs[0])
            term = b.s(sep.outputs[0]) * (w / tot)
            out = term if out is None else out + term
        return out

    def C(self, h):
        return lin(h)

    def u(self, name):
        """a uniform: a Value node driven by the armature's 'cs_tuta.<name>'"""
        if name in self._u:
            return self._u[name]
        v = self.b.value(PROPS.get(name, 0.0), label=f'cs.u.{name}')
        if self.arm is not None:
            drive(v.v.node.outputs[0], 'default_value', self.arm, f'cs_tuta.{name}', var='u')
        self._u[name] = v
        return v


def _vnoise_group():
    name = 'cs.vnoise3'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree, gi, go = new_group(name, 'ShaderNodeTree', inputs=(('Vector', 'NodeSocketVector'),),
                             outputs=(('Value', 'NodeSocketFloat'),))
    b = CSBuilder(tree)
    x, y, z = b.vec(gi.outputs['Vector']).xyz()
    q = [x + 512.0, y + 512.0, z + 512.0]
    i = [b.floor(c) for c in q]
    f = [b.fract(c) for c in q]
    w = [c * c * (3.0 - c * 2.0) for c in f]

    def h(dx, dy, dz):
        wn = b.node('ShaderNodeTexWhiteNoise', noise_dimensions='3D')
        b.link(b.combine(i[0] + dx, i[1] + dy, i[2] + dz), wn.inputs['Vector'])
        return b.s(wn.outputs['Value'])
    x00 = b.mix(h(0, 0, 0), h(1, 0, 0), w[0])
    x10 = b.mix(h(0, 1, 0), h(1, 1, 0), w[0])
    x01 = b.mix(h(0, 0, 1), h(1, 0, 1), w[0])
    x11 = b.mix(h(0, 1, 1), h(1, 1, 1), w[0])
    b.link(b.mix(b.mix(x00, x10, w[1]), b.mix(x01, x11, w[1]), w[2]), go.inputs['Value'])
    return tree


def _billboard_group():
    """Geometry Nodes: the card turned (from +Z, the shortest way) toward the scene's active camera, so it faces
    every camera a film cuts to, as three's Sprite does (the camera's place in the card's own space: Object Info,
    relative)"""
    name = 'cs.billboard'
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = tree.nodes, tree.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    cam = N.new('GeometryNodeInputActiveCamera')
    oi = N.new('GeometryNodeObjectInfo')
    oi.transform_space = 'RELATIVE'
    L.new(cam.outputs[0], oi.inputs['Object'])
    al = N.new('FunctionNodeAlignRotationToVector')
    al.axis, al.pivot_axis = 'Z', 'AUTO'
    L.new(oi.outputs['Location'], al.inputs['Vector'])
    tf = N.new('GeometryNodeTransform')
    L.new(gi.outputs[0], tf.inputs['Geometry'])
    L.new(al.outputs['Rotation'], tf.inputs['Rotation'])
    L.new(tf.outputs['Geometry'], go.inputs[0])
    return tree


def _rest_PN(b):
    """(P, N) in three's axes from the rest position and the stored rest normal"""
    at = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='rest_position')
    x, y, z = b.vec(at.outputs['Vector']).xyz()
    an = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='cs_rest_normal')
    nx, ny, nz = b.vec(an.outputs['Vector']).xyz()
    return (x, z, -y), (nx, nz, -ny)


def _uv_density(o, mats, arm=None):
    """UV v per rest metre on o's faces of these materials: the area-weighted mean |grad v| of its render UV map over
    those triangles, in the armature's rest space (1.0 without such faces), so a band drawn in v takes the footprint
    in v as the TSL's fwidth of a UV distance did"""
    if o is None or not mats or not len(o.data.uv_layers):
        return 1.0
    me = o.data
    names = {m.name for m in mats if m is not None}
    slots = [i for i, m in enumerate(me.materials) if m is not None and m.name in names]
    if not slots:
        return 1.0
    layer = next((u for u in me.uv_layers if u.active_render), me.uv_layers.active)
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    tl, tv, mi = np.empty(n * 3, np.int64), np.empty(n * 3, np.int64), np.empty(n, np.int64)
    me.loop_triangles.foreach_get('loops', tl)
    me.loop_triangles.foreach_get('vertices', tv)
    me.loop_triangles.foreach_get('material_index', mi)
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    if arm is not None:
        R = np.array(M.rest_matrix(o, arm), np.float64)
        co = co @ R[:3, :3].T + R[:3, 3]
    uv = np.empty(len(me.loops) * 2, np.float64)
    layer.data.foreach_get('uv', uv)
    keep = np.isin(mi, slots)
    P = co[tv.reshape(-1, 3)[keep]]
    V = uv.reshape(-1, 2)[tl.reshape(-1, 3)[keep], 1]
    e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    d1, d2 = V[:, 1] - V[:, 0], V[:, 2] - V[:, 0]
    g11, g12, g22 = (e1 * e1).sum(1), (e1 * e2).sum(1), (e2 * e2).sum(1)
    det = g11 * g22 - g12 * g12
    ok = det > 1e-24
    dd = np.where(ok, det, 1.0)
    g = ((d1 * g22 - d2 * g12) / dd)[:, None] * e1 + ((d2 * g11 - d1 * g12) / dd)[:, None] * e2   # g.e1 = d1, g.e2 = d2
    w = np.sqrt(np.maximum(det, 0.0)) * ok
    return float((np.linalg.norm(g, axis=1) * w).sum() / w.sum()) if w.sum() > 0 else 1.0


def _store_rest_normal(o):
    me = o.data
    n = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get('normal', n)
    at = me.attributes.get('cs_rest_normal') or me.attributes.new('cs_rest_normal', 'FLOAT_VECTOR', 'POINT')
    at.data.foreach_set('vector', n)
    o.add_rest_position_attribute = True


def _linear(idb, paths):
    """the keys on these data paths LINEAR (Python's keyframe_insert ignores the preference and makes Bezier, which
    overshoots between per-frame keys); hide_* booleans step on their own"""
    from bpy_extras import anim_utils
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return
    for slot in ad.action.slots:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, slot)
        for fc in (cb.fcurves if cb else []):
            if fc.data_path in paths:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'


def _key_interp(idb, path, frame, interp):
    """the interpolation of the one key on `path` at `frame`"""
    from bpy_extras import anim_utils
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return
    for slot in ad.action.slots:
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, slot)
        for fc in (cb.fcurves if cb else []):         # every array index of the path (find() is index 0 alone)
            if fc.data_path != path:
                continue
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 1e-6:
                    kp.interpolation = interp


def _cmix(b, a, c, t):
    """mix of two colours (tuples or Vec) by a scalar"""
    return b.rgb_mix(a if not isinstance(a, tuple) else _rgb(b, a), c if not isinstance(c, tuple) else _rgb(b, c), t)


def _rgb(b, c):
    n = b.node('ShaderNodeRGB')
    n.outputs[0].default_value = tuple(c) + (1.0,)
    return Vec(b, n.outputs[0])


def _cscale(b, c, s):
    return b.vscale(c if not isinstance(c, tuple) else _rgb(b, c), s)


def _cadd(b, c, d):
    return b.vmath('ADD', c if not isinstance(c, tuple) else _rgb(b, c), d if not isinstance(d, tuple) else _rgb(b, d))


# ------------------------------------------------------------------------------------------------ the tuta
ARM_Y, ARM_Z, SH_X, CUFF_X, SIDE_Z = 1.336, -0.007, 0.205, 0.705, -0.012


def tuta_features(t, P, N):
    b = t.b
    X, Y, Z = P
    side = b.step(0.0, X)
    ax = b.abs(X)
    front, back = b.smoothstep(0.08, 0.35, N[2]), b.smoothstep(0.08, 0.35, -N[2])
    on_sleeve = b.smoothstep(SH_X - 0.002, SH_X + 0.002, ax)
    on_leg = (1.0 - b.smoothstep(0.84, 0.88, Y)) * (1.0 - on_sleeve)
    on_torso = b.max(1.0 - on_sleeve - on_leg, 0.0)
    sdy, sdz = Y - ARM_Y, Z - ARM_Z
    sr = b.max(b.sqrt(sdy * sdy + sdz * sdz), 0.02)
    sth = b.math('ARCTAN2', sdz, sdy, fold=False)
    tK, tA = t.sat((Y - 0.455) / (0.829 - 0.455)), t.sat((Y - 0.054) / (0.455 - 0.054))
    lx = b.mix(b.mix(0.096, 0.101, tA), 0.097, tK)
    lz = b.mix(b.mix(-0.039, -0.015, tA), -0.010, tK)
    ldx, ldz = ax - lx, Z - lz
    lr = b.max(b.sqrt(ldx * ldx + ldz * ldz), 0.02)
    lth = b.math('ARCTAN2', ldx, ldz, fold=False)
    d_under = sr * b.abs(b.abs(sth) - math.pi)
    d_side = b.abs(Z - SIDE_Z) + b.step(ax, 0.06) + b.step(1.285, Y)
    d_out = lr * b.abs(lth - math.pi / 2)
    d_in = lr * b.abs(lth + math.pi / 2)
    d_ring = b.abs(ax - SH_X) + b.step(Y, 1.2)
    d_cuff = b.abs(ax - CUFF_X)
    d_pipe = b.min(b.min(b.mix(1.0, d_under, on_sleeve), b.mix(1.0, d_side, on_torso)),
                   b.min(b.mix(1.0, d_out, on_leg), b.min(d_ring, b.mix(1.0, d_cuff, on_sleeve))))
    pipe = t.band(d_pipe, 0.0042)
    pipe_halo = b.exp(-(d_pipe / 0.0055)) * (1.0 - pipe)

    def rows(d, off):
        return t.band(b.abs(d - off), 0.0011)
    dash = b.step(0.35, b.fract(Y * 520.0 + X * 520.0 + Z * 370.0))
    stitch = b.max(rows(d_pipe, 0.0052), rows(d_pipe, 0.0085))
    stitch = b.max(stitch, b.mix(0.0, b.max(rows(d_in, 0.0), rows(d_in, 0.003)), on_leg))
    d_yoke = b.abs(Y - 1.302) + (1.0 - back) + on_sleeve
    d_cb = b.abs(X) + (1.0 - back) + b.step(1.30, Y) + on_sleeve
    stitch = b.max(stitch, b.max(t.band(d_yoke, 0.0012), b.max(rows(d_yoke, 0.003), rows(d_cb, 0.002))))
    seam_line = b.max(t.band(d_yoke, 0.0012), t.band(d_cb, 0.001))
    p2 = (X, Y)
    zs_d, zs_t = t.seg(p2, ZIP_TOP, ZIP_BOT)
    zip_on = front * b.step(0.015, Z) * on_torso
    d_zip = zs_d + (1.0 - zip_on)
    flap, coil, tape = t.band(d_zip, 0.019), t.band(d_zip, 0.0072), t.band(d_zip, 0.013)
    teeth = b.step(0.5, b.fract(zs_t * (0.37 / 0.0024)))
    stitch = b.max(stitch, b.max(rows(d_zip, 0.0095), rows(d_zip, 0.0125)))
    right_sleeve = on_sleeve * (1.0 - side)
    violet = t.edge(t.poly_sd(p2, [(-0.215, 1.29), (-0.215, 0.985), (0.035, 1.115)])) * front * on_torso
    back_wedge = t.edge(t.poly_sd(p2, [(0.215, 1.30), (-0.185, 0.985), (0.215, 1.06)])) * back * on_torso
    sL = lr * lth
    legP = (sL, Y)
    petrol = t.edge(t.poly_sd(legP, [(-0.062, 0.90), (0.058, 0.90), (-0.004, 0.47)])) * side * on_leg
    KNEE = [(-0.05, 0.40), (0.05, 0.40), (0.062, 0.452), (0.05, 0.54), (-0.05, 0.54), (-0.062, 0.452)]
    knee_sd = t.poly_sd(legP, KNEE)
    knee = t.edge(knee_sd) * on_leg
    stitch = b.max(stitch, b.mix(0.0, b.max(rows(knee_sd, -0.003), t.band(knee_sd, 0.0012)), on_leg))

    def dart(y0):
        return t.band(Y - y0 - sL * sL * 5.0, 0.0012)
    knee_dart = b.max(dart(0.448), dart(0.488)) * knee
    stitch = b.max(stitch, b.max(t.band(Y - 0.452 - sL * sL * 5.0, 0.0008), t.band(Y - 0.492 - sL * sL * 5.0, 0.0008)) * knee)
    bolt = [(0.02, 0.86), (-0.03, 0.80), (0.035, 0.735), (-0.035, 0.665), (0.03, 0.60), (-0.02, 0.545)]
    d_bolt = t.polyline(legP, bolt) + side + (1.0 - on_leg)
    inlay = t.band(d_bolt, 0.0065)
    inlay_edge = t.band(b.abs(d_bolt - 0.0042), 0.0011)
    hip = (ax, Y)
    d_hip0, _ = t.seg(hip, (0.092, 0.918), (0.158, 0.842))
    d_hip = d_hip0 + (1.0 - front) + (1.0 - (on_torso + on_leg))
    hip_welt = t.band(d_hip, 0.0016)
    stitch = b.max(stitch, rows(d_hip, 0.003))
    cargo_sd = t.poly_sd(legP, [(0.036, 0.585), (0.106, 0.585), (0.106, 0.745), (0.036, 0.745)])
    cargo_on = side * on_leg
    cargo = t.edge(cargo_sd) * cargo_on
    flap_sd = t.poly_sd(legP, [(0.033, 0.70), (0.109, 0.70), (0.109, 0.752), (0.033, 0.752)])
    flap_m = t.edge(flap_sd) * cargo_on
    stitch = b.max(stitch, b.mix(0.0, b.max(rows(cargo_sd, -0.003), rows(flap_sd, -0.0025)), cargo_on))
    d_tail = b.sqrt(X * X + (Y - TAIL_EXIT[1]) * (Y - TAIL_EXIT[1])) + (1.0 - back)
    grommet = t.band(b.abs(d_tail - 0.036), 0.008)
    return dict(side=side, front=front, back=back, on_sleeve=on_sleeve, on_leg=on_leg, on_torso=on_torso, pipe=pipe,
                pipe_halo=pipe_halo, d_pipe=d_pipe, stitch=stitch * dash, seam_line=seam_line, flap=flap, coil=coil,
                tape=tape, teeth=teeth, d_zip=d_zip, right_sleeve=right_sleeve, violet=violet, back_wedge=back_wedge,
                petrol=petrol, knee=knee, knee_dart=knee_dart, inlay=inlay, inlay_edge=inlay_edge, hip_welt=hip_welt,
                cargo=cargo, flap_m=flap_m, grommet=grommet)


def ghost_of(t, Pb, frames):
    """the badges' ghosts at rest point Pb (Blender axes, armature space): (fill, line colour, ring)"""
    b = t.b
    ext = SPEC['uv_extent'] / 1000.0
    sdf = _image(os.path.join(_TEX, 'badges_sdf.png'))
    fill, ring, line = 0.0, 0.0, None
    for k, g in enumerate(frames):
        if g is None:
            continue
        o, u, v, n = g['o'], g['u'], g['v'], g['n']
        dx, dy, dz = Pb[0] - o[0], Pb[1] - o[1], Pb[2] - o[2]
        lx = dx * u[0] + dy * u[1] + dz * u[2]
        ly = dx * v[0] + dy * v[1] + dz * v[2]
        lz = dx * n[0] + dy * n[1] + dz * n[2]
        uu, vv = lx / ext + 0.5, ly / ext + 0.5
        in_tile = b.step(0.0, uu) * b.step(uu, 1.0) * b.step(0.0, vv) * b.step(vv, 1.0) * b.step(b.abs(lz), 0.02)
        tx = b.node('ShaderNodeTexImage')
        tx.image, tx.interpolation, tx.extension = sdf, 'Linear', 'EXTEND'
        b.link(b.combine((t.sat(uu) + float(k)) / float(len(BADGES)), t.sat(vv), 0.0), tx.inputs['Vector'])
        sep = b.node('ShaderNodeSeparateColor')
        b.link(tx.outputs['Color'], sep.inputs[0])
        mm = (b.s(sep.outputs[0]) * 255.0 - 128.0) / 8.0
        gk = t.u(f'ghost.{BADGES[k]}')
        fw_mm = b.max(t.fw * 1000.0, 0.05)                 # the TSL's max(fwidth(mm), 0.05), in badge mm
        inside = (1.0 - b.smoothstep(-fw_mm, fw_mm, mm + 0.4)) * in_tile * gk
        edge = t.band(mm * 0.001, 0.0016) * in_tile * gk
        fill = fill + inside
        ring = ring + edge
        c = _cscale(b, lin(g['glow']), edge)
        line = c if line is None else b.vmath('ADD', line, c)
    return t.sat(fill), (line if line is not None else (0.0, 0.0, 0.0)), t.sat(ring)


def tuta_nodes(t, P, N, Pb, ghost_frames, tex):
    b = t.b
    X, Y, Z = P
    F = tuta_features(t, P, N)
    C = lin
    weave = t.tri(tex['fab_c'], P, N, 9.0)
    heather = t.tri(tex['fab_c'], (X + 0.31, Y + 0.17, Z + 0.53), N, 2.3)
    wH = t.tri(tex['fab_h'], P, N, 9.0)

    def g5(c):
        return t.band(b.abs(b.fract(c / 0.0055) - 0.5) * 0.0055, 0.0007)
    ax3 = [b.abs(c) for c in N]
    rip = b.max(g5(b.mix(X, Z, b.step(ax3[2], ax3[0]))), g5(Y)) * b.max(F['knee'], F['violet'])
    col = _rgb(b, C('#18191e'))
    for hexc, m in (('#26282f', F['right_sleeve']), ('#2c2142', F['violet']), ('#123842', F['petrol']),
                    ('#202227', F['back_wedge']), ('#1d1f24', F['knee'])):
        col = _cmix(b, col, C(hexc), m)
    col = _cmix(b, col, C('#09090b'), F['knee_dart'] * 0.8)
    col = _cmix(b, col, C('#1b1c21'), F['cargo'])
    col = _cmix(b, col, C('#202126'), F['flap_m'])
    col = _cscale(b, _cscale(b, col, (weave - 0.306) * 1.35 + 1.0), (heather - 0.306) * 0.9 + 1.0)
    col = _cscale(b, col, rip * 0.35 + 1.0)
    n1, n2 = t.vnoise(X * 9.0, Y * 9.0, Z * 9.0), t.vnoise(X * 37.0, Y * 37.0, Z * 37.0)
    dust = b.smoothstep(0.62, 0.18, Y) * (n1 * 0.7 + n2 * 0.3) * 0.55 + F['knee'] * n2 * 0.25
    col = _cmix(b, col, C('#4a4640'), t.sat(dust * 0.42 * t.u('grime')))
    col = _cscale(b, col, (n1 - 0.5) * 0.16 + 1.0)
    col = _cmix(b, col, C('#08080a'), F['seam_line'] * 0.8)
    col = _cmix(b, col, C('#5a5d66'), F['stitch'] * 0.9)
    col = _cmix(b, col, _cscale(b, col, 1.3), F['flap'] * 0.7)
    col = _cmix(b, col, C('#0c0c0e'), F['tape'] * 0.8)
    col = _cmix(b, col, _cmix(b, C('#383b43'), C('#9aa0ab'), F['teeth']), F['coil'])
    col = _cmix(b, col, C('#2e3038'), F['hip_welt'])
    col = _cmix(b, col, tuple(a + (c - a) * 0.55 for a, c in zip(C('#d9b38f'), C(SODIUM))), F['inlay'])
    col = _cmix(b, col, C('#09090b'), F['inlay_edge'])
    col = _cmix(b, col, C('#6d717b'), F['grommet'])
    neon_c = _cmix(b, C(NEON_R), C(NEON_L), F['side'])
    col = _cmix(b, col, _cscale(b, neon_c, 0.55), F['pipe'])
    g_fill, g_line, g_ring = ghost_of(t, Pb, ghost_frames)
    fuzz = t.vnoise(X * 2600.0, Y * 2600.0, Z * 2600.0) * 0.5 + t.vnoise(X * 700.0, Y * 700.0, Z * 700.0) * 0.5
    col = _cmix(b, col, _cscale(b, _cadd(b, _cscale(b, col, 1.9), (0.010, 0.009, 0.008)), fuzz * 0.5 + 0.75), g_fill)
    col = _cmix(b, col, _cadd(b, col, (0.02, 0.02, 0.022)), g_ring * 0.5)
    neon = t.u('neon')
    emis = _cscale(b, neon_c, (F['pipe'] * 2.4 + F['pipe_halo'] * 0.10) * neon)
    emis = _cadd(b, emis, _cscale(b, C(SODIUM), F['inlay'] * 0.55 * neon))
    emis = _cadd(b, emis, _cscale(b, g_line if not isinstance(g_line, tuple) else _rgb(b, g_line), 0.2))
    H = ((wH - 0.5) * 0.0004 - b.exp(-(F['d_pipe'] / 0.004)) * 0.0007 + F['pipe'] * 0.0011 + F['flap'] * 0.0006
         + F['coil'] * F['teeth'] * 0.0007 + F['stitch'] * 0.00015 - F['seam_line'] * 0.0004 + F['flap_m'] * 0.0008
         + rip * 0.00012 + F['inlay'] * 0.0003 + F['grommet'] * 0.0008 - F['knee_dart'] * 0.0005 - F['hip_welt'] * 0.0005)
    return col, emis, H


def boot_nodes(t, P, N, is_sole, tex):
    b = t.b
    X, Y, Z = P
    ax, side = b.abs(X), b.step(0.0, X)
    C = lin
    grain = t.tri(tex['lea_h'], P, N, 7.0)
    n1 = t.vnoise(X * 14.0, Y * 14.0, Z * 14.0)
    neon_c = _cmix(b, C(NEON_R), C(NEON_L), side)
    if not is_sole:
        toe = b.smoothstep(0.075, 0.09, Z) * b.step(Y, 0.075)
        heel = b.smoothstep(-0.045, -0.06, Z) * b.step(Y, 0.11)
        shaft = b.smoothstep(0.075, 0.095, Y)
        lx = 0.098
        frontn = b.smoothstep(0.45, 0.8, N[2])
        dx = ax - lx
        lace_col = t.band(dx, 0.024) * frontn * b.smoothstep(0.072, 0.08, Y) * (1.0 - b.smoothstep(0.205, 0.212, Y))
        d1 = b.abs(b.fract((Y + dx) / 0.016) - 0.5) * 0.016
        d2 = b.abs(b.fract((Y - dx) / 0.016) - 0.5) * 0.016
        criss = b.max(t.band(d1, 0.0026), t.band(d2, 0.0026)) * t.band(dx, 0.017) * lace_col
        ex, ey = b.abs(dx) - 0.0095, (b.fract(Y / 0.016 + 0.5) - 0.5) * 0.016
        eyelet = t.band(b.abs(b.sqrt(ex * ex + ey * ey) - 0.0019), 0.0011) * lace_col
        strap = t.band(Y - 0.165, 0.024)
        pull = t.band(Y - 0.222, 0.016) * t.band(dx, 0.012) * frontn
        collar = b.smoothstep(0.233, 0.24, Y)
        col = _cscale(b, C('#121214'), grain * 0.5 + 0.75)
        col = _cmix(b, col, C('#18191c'), shaft * 0.8)
        col = _cmix(b, col, _cscale(b, C('#0d0d0f'), grain + 0.6), b.max(toe, heel))
        col = _cmix(b, col, C('#1c1d21'), strap)
        col = _cmix(b, col, C('#26272c'), collar)
        col = _cmix(b, col, C('#0b0b0d'), lace_col * 0.6)
        col = _cmix(b, col, C('#3b3d44'), criss)
        col = _cmix(b, col, C('#8a8f99'), eyelet)
        col = _cmix(b, col, _cscale(b, neon_c, 0.5), pull)
        col = _cmix(b, col, C('#3d3a36'), t.sat(b.smoothstep(0.12, 0.0, Y) * n1 * 0.35 * t.u('grime')))
        emis = _cscale(b, neon_c, pull * 1.6 * t.u('neon'))
        H = (grain - 0.5) * 0.0004 + criss * 0.0012 + eyelet * 0.0006 + strap * 0.001 + collar * 0.001
    else:
        ribs = t.band(b.abs(b.fract(Y / 0.0032) - 0.5) * 0.0032, 0.0012)
        mid = t.band(b.abs(Y - 0.0195), 0.0016)
        col = _cscale(b, C('#1d1e21'), n1 * 0.3 + 0.85)
        col = _cmix(b, col, C('#2b2c30'), ribs)
        col = _cmix(b, col, _cscale(b, neon_c, 0.5), mid)
        col = _cmix(b, col, C('#47433d'), t.sat(n1 * 0.4 * t.u('grime')))
        emis = _cscale(b, neon_c, mid * 1.4 * t.u('neon'))
        H = ribs * 0.0005 + mid * 0.0004
    return col, emis, H


def strap_nodes(t, P, N, is_buckle, v_per_m=1.0):
    """the webbing (its ribs across UV v: v_per_m, the mesh's v per rest metre, takes the footprint into v) or the
    buckle"""
    b = t.b
    X, Y, Z = P
    C = lin
    n1 = t.vnoise(X * 30.0, Y * 30.0, Z * 30.0)
    if not is_buckle:
        uvn = b.node('ShaderNodeUVMap')
        _u, v, _w = b.vec(uvn.outputs['UV']).xyz()
        ribs = t.band(b.abs(b.fract(v * 18.0) - 0.5) / 18.0, 0.02, k=v_per_m)
        edge = b.smoothstep(0.1, 0.0, v) + b.smoothstep(0.9, 1.0, v)
        col = _cadd(b, _cscale(b, C('#16171a'), n1 * 0.25 + 0.88), _cscale(b, (1.0, 1.0, 1.0), ribs * 0.01 + edge * 0.012))
        return col, (0.0, 0.0, 0.0), ribs * 0.0002 + edge * 0.0003
    brushed = t.vnoise(X * 900.0, Y * 40.0, Z * 900.0)
    return _cscale(b, C('#3c3f46'), brushed * 0.35 + 0.8), (0.0, 0.0, 0.0), brushed * 0.00005


def _install(m, arm, build, toony=None, shift=None, rim=None, shade=0.5, scale=0.87):
    """a TuTa surface into one MToon material: colour, shade (cool, x shade), emission, bump"""
    mo = m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output') if m and m.node_tree else None
    if mo is None:
        return False
    nt = m.node_tree
    clear_cs(nt)
    b = CSBuilder(nt, x0=-4200, y0=-2400)
    t = TSL(b, arm, scale=scale)
    col, emis, H = build(t, b)
    b.link(col, mo.inputs['Lit Color'])
    mo.inputs['Lit Color Texture Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    for l in list(mo.inputs['Lit Color Texture Color'].links):
        nt.links.remove(l)
    shd = b.vmath('MULTIPLY', _cscale(b, col, shade), (0.82, 0.86, 1.08))
    b.link(shd, mo.inputs['Shade Color'])
    for l in list(mo.inputs['Shade Color Texture'].links):
        nt.links.remove(l)
    mo.inputs['Shade Color Texture'].default_value = (1.0, 1.0, 1.0, 1.0)
    if isinstance(emis, tuple):
        mo.inputs['Emissive Factor'].default_value = tuple(emis) + (1.0,)
    else:
        b.link(emis, mo.inputs['Emissive Factor'])
    for l in list(mo.inputs['Emissive Texture'].links):
        nt.links.remove(l)
    mo.inputs['Emissive Texture'].default_value = (1.0, 1.0, 1.0, 1.0)
    mo.inputs['Emissive Strength'].default_value = 1.0
    bump = b.node('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 1.0
    bump.inputs['Distance'].default_value = scale
    b.link(H, bump.inputs['Height'])
    b.link(bump.outputs['Normal'], mo.inputs['Normal'])
    if toony is not None:
        mo.inputs['Shading Toony'].default_value = toony
    if shift is not None:
        mo.inputs['Shading Shift'].default_value = shift
    if rim:
        mo.inputs['Parametric Rim Color'].default_value = lin(rim) + (1.0,)
        mo.inputs['Parametric Rim Fresnel Power'].default_value = 3.2
        mo.inputs['Parametric Rim Lift'].default_value = 0.0
        mo.inputs['Rim LightingMix'].default_value = 1.0
    from .look import refresh_pbr
    refresh_pbr(m)
    return True


class TutaWardrobe(Wardrobe):
    """makeTutaWardrobe on claude_suit_wardrobe.vrm (the garment wardrobe underneath, the TuTa on top)"""

    BADGES = BADGES                 # the JS api's BADGES

    def __init__(self, h, wear=None, neon=1.0, grime=1.0, plain=False, eject_speed=1.4, eject_up=1.0,
                 eject_gravity=2.2, eject_drag=0.8, floor_z=None, scale=None):
        super().__init__(h)
        arm = self.arm
        for k, v in PROPS.items():
            arm[f'cs_tuta.{k}'] = v
        arm['cs_tuta.neon'], arm['cs_tuta.grime'] = float(neon), float(grime)
        for k in BADGES:
            arm[f'cs_tuta.ghost.{k}'] = 0.0
            arm[f'cs_tuta.glow.{k}'] = float(neon)
        arm.update_tag()           # the new properties into the evaluated armature (see _paint.new_prop)
        self.uf = {}
        for o in h.objects:
            for n in UF_LAYERS:
                if (o.name == n or o.name == f'{n}_1' or o.name.startswith(f'{n}.')) and n not in self.uf:
                    self.uf[n] = o
        self.missing = [n for n in UF_LAYERS if n not in self.uf]
        self.scale = scale if scale is not None else float(arm.scale[0])
        self.ej = {'out': eject_speed, 'up': eject_up, 'g': eject_gravity, 'drag': eject_drag, 'spin': 2.4}
        self.floor_z = floor_z if floor_z is not None else float(arm.matrix_world.translation.z)
        self.state = {'now': {k: {'on': False, 'ghost': 0} for k in BADGES}, 'events': {}, 'disc': False, 'paint': 0.0,
                      'last_t': 0.0}
        self.home = {k: self.uf[k].matrix_basis.copy() for k in BADGES if k in self.uf}
        self._ghost_frames = self._ghost_rest_frames()
        self._base_shoes = [o for o in h.meshes if o.name.startswith('shoes')]
        self._flyers, self._sparks = {}, {}
        if not plain:
            self._surfaces()
        self._badge_emission()
        for k in BADGES:
            self._badge_visible(k, False, None)
        if 'acc_sundisc' in self.uf:
            self._show(self.uf['acc_sundisc'], False, None)
        self.current = None
        self.wear(wear or 'suit')

    # ------------------------------------------------------------------------------------------- rest frames
    def _rest(self, o):
        return M.rest_matrix(o, self.arm)

    def _ghost_rest_frames(self):
        out = []
        for k in BADGES:
            o = self.uf.get(k)
            if o is None:
                out.append(None)
                continue
            R = self._rest(o)
            R3 = R.to_3x3()
            u, v, n = R3.col[0].normalized(), R3.col[1].normalized(), R3.col[2].normalized()
            out.append({'o': tuple(R.translation), 'u': tuple(u), 'v': tuple(v), 'n': tuple(n), 'glow': SPEC['badges'][k]['glow']})
        return out

    # ------------------------------------------------------------------------------------------- surfaces
    def _surfaces(self):
        fab = _texture_set('Fabric039', '1k')
        lea = _texture_set('Leather037', '2k')
        tex = {'fab_c': _image(fab['diff']), 'fab_h': _image(fab['displacement']), 'lea_h': _image(lea['displacement'])}
        for n in ('tuta', 'uf_boots', 'uf_straps'):
            if n in self.uf:
                _store_rest_normal(self.uf[n])
        arm = self.arm
        gf = self._ghost_frames
        sc = self.scale
        v_per_m = _uv_density(self.uf.get('uf_straps'), self.mats.get('webbing', []), self.arm)
        self.webbing_v_per_m = v_per_m

        def tuta(t, b):
            P, N = _rest_PN(b)
            at = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='rest_position')
            Pb = b.vec(at.outputs['Vector']).xyz()
            return tuta_nodes(t, P, N, Pb, gf, tex)
        self.installed = {}
        for name, build, kw in (
                ('tuta', tuta, dict(toony=0.55, shift=-0.05, rim='#3a4150', shade=0.42)),
                ('boot_upper', lambda t, b: boot_nodes(t, *_rest_PN(b), False, tex), dict(toony=0.6, rim='#404754', shade=0.42)),
                ('boot_sole', lambda t, b: boot_nodes(t, *_rest_PN(b), True, tex), dict(toony=0.7, shade=0.45)),
                ('webbing', lambda t, b: strap_nodes(t, *_rest_PN(b), False, v_per_m),
                 dict(toony=0.6, rim='#2c313b', shade=0.42)),
                ('buckle', lambda t, b: strap_nodes(t, *_rest_PN(b), True), dict(toony=0.8, rim='#aab3c2', shade=0.35))):
            for m in self.mats.get(name, []):
                self.installed[m.name] = _install(m, arm, build, scale=sc, **kw)
            for om in self.outline_mats.get(name, []):
                mo = om.node_tree.nodes.get('Mtoon1Material.Mtoon1Output')
                if mo is not None:
                    mo.inputs['Outline Color'].default_value = lin('#050507') + (1.0,)
        self._face_paint_nodes()
        self._catchlight_nodes()
        self._disc_nodes()

    def _face_paint_nodes(self):
        face, _k = M.find(self.h, 'face')
        if face is None:
            return
        Mf = self._rest(face)
        face.add_rest_position_attribute = True
        for m in self.mats.get('face', []):
            mo = m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output')
            if mo is None:
                continue
            nt = m.node_tree
            clear_cs(nt)
            b = CSBuilder(nt, x0=-4200, y0=-2400)
            t = TSL(b, self.arm, scale=self.scale)
            at = b.node('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='rest_position')
            px, py, pz = b.vec(at.outputs['Vector']).xyz()
            r = [Mf.row[i] for i in range(3)]
            bx, by, bz = (px * r[i][0] + py * r[i][1] + pz * r[i][2] + r[i][3] for i in range(3))
            X, Y = bx, bz                                          # rest model space, three's (x, y)
            p2 = (X, Y)
            keep = b.smoothstep(0.004, 0.012, X) * \
                (1.0 - b.smoothstep(-0.012, 0.0, 1.505 - Y) * (1.0 - b.smoothstep(0.085, 0.097, X)))
            planes = [
                ([(0.020, 1.683), (0.041, 1.688), (0.151, 1.470)], NEON_L, ((0.03, 1.685), (0.151, 1.47))),
                ([(0.159, 1.578), (0.158, 1.546), (0.097, 1.566)], NEON_R, ((0.158, 1.56), (0.097, 1.566))),
                ([(0.095, 1.521), (0.153, 1.499), (0.118, 1.461)], NEON_R, ((0.153, 1.499), (0.105, 1.49))),
                ([(0.040, 1.628), (0.100, 1.611), (0.129, 1.648), (0.071, 1.668)], NEON_L, ((0.04, 1.63), (0.129, 1.648))),
                ([(0.009, 1.676), (0.019, 1.681), (0.047, 1.602)], NEON_R, ((0.014, 1.678), (0.047, 1.602))),
            ]
            PAINT = {NEON_L: '#0fb4d8', NEON_R: '#e0249f'}
            paint_a, paint_c = 0.0, (0.0, 0.0, 0.0)
            jitter = (t.vnoise(X * 900.0, Y * 900.0, 7.0) - 0.5) * 0.0008
            for pts, c, ((gx0, gy0), (gx1, gy1)) in planes:
                mk = t.edge(t.poly_sd(p2, pts) + jitter) * keep
                gl = math.hypot(gx1 - gx0, gy1 - gy0)
                gt = t.sat((X - gx0) * ((gx1 - gx0) / gl / gl) + (Y - gy0) * ((gy1 - gy0) / gl / gl))
                paint_c = _cmix(b, paint_c, _cscale(b, lin(PAINT[c]), gt * -0.35 + 1.05), mk)
                paint_a = b.max(paint_a, mk)
            d1, _ = t.seg(p2, (0.004, 1.705), (0.160, 1.552))
            d2, _ = t.seg(p2, (0.100, 1.400), (0.160, 1.610))
            ink = b.max(t.band(d1, 0.0011), t.band(d2, 0.0009)) * keep + t.band(t.poly_sd(p2, planes[3][0]), 0.0008) * keep
            n1 = t.vnoise(X * 160.0, Y * 40.0, 3.0)
            paint_a = paint_a * (n1 * 0.12 + 0.88) * t.u('paint')
            ink_a = t.sat(ink) * t.u('paint')
            base = tuple(mo.inputs['Lit Color'].default_value)[:3]
            shade_b = tuple(mo.inputs['Shade Color'].default_value)[:3]
            col = _cmix(b, _cmix(b, base, paint_c, paint_a), lin('#1a1024'), ink_a * 0.85)
            shd = _cmix(b, _cmix(b, shade_b, _cscale(b, paint_c, 0.55), paint_a), lin('#0d0814'), ink_a * 0.85)
            b.link(col, mo.inputs['Lit Color'])
            b.link(shd, mo.inputs['Shade Color'])
            b.link(_cscale(b, paint_c, paint_a * 0.16 * t.u('neon')), mo.inputs['Emissive Factor'])
            mo.inputs['Emissive Strength'].default_value = 1.0
            from .look import refresh_pbr
            refresh_pbr(m)                 # the PBR look (set before the wardrobe) takes the paint too

    def _catchlight_nodes(self):
        plate, _k = M.find(self.h, 'Material', need_keys=True)
        if plate is None:
            return
        Mp = self._rest(plate)
        for m in self.mats.get('Material', []):
            mo = m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output')
            if mo is None:
                continue
            nt = m.node_tree
            clear_cs(nt)
            b = CSBuilder(nt, x0=-4200, y0=-2400)
            t = TSL(b, self.arm, scale=self.scale)
            tc = b.node('ShaderNodeTexCoord')                  # the MORPHED position: a blink closes over the light
            px, py, pz = b.vec(tc.outputs['Object']).xyz()
            r = [Mp.row[i] for i in range(3)]
            bx, by, bz = (px * r[i][0] + py * r[i][1] + pz * r[i][2] + r[i][3] for i in range(3))
            X, Y, Z = bx, bz, -by
            light, tint = 0.0, None
            for ex, ey, nc in ((0.0703, 1.5587, NEON_L), (-0.0747, 1.5587, NEON_R)):
                qx, qy = X - ex, Y - ey
                in_eye = b.step(b.sqrt((qx / 0.026) * (qx / 0.026) + (qy / 0.042) * (qy / 0.042)), 1.0) * b.step(0.09, Z)
                win = t.edge(b.max(b.abs(qx + 0.0075) - 0.0048, b.abs(qy - 0.0165) - 0.0068) - 0.0012)
                dot2 = t.edge(b.sqrt((qx - 0.0068) * (qx - 0.0068) + (qy + 0.0115) * (qy + 0.0115)) - 0.0026)
                # the faint scanline fades before it aliases: the TSL's smoothstep(0.25, 0.6, fwidth(Y / 1.8 mm))
                scan = 1.0 - b.step(0.55, b.fract(Y / 0.0018)) * 0.32 * (1.0 - b.smoothstep(0.25, 0.6, t.fw / 0.0018))
                lv = b.max(win, dot2 * 0.8) * scan * in_eye
                light = light + lv
                tn = _cscale(b, _cmix(b, (1.0, 1.0, 1.0), lin(nc), t.u('eye_neon') * 0.18), lv)
                tint = tn if tint is None else b.vmath('ADD', tint, tn)
            b.link(_cscale(b, tint, t.u('eyes') * 1.25), mo.inputs['Emissive Factor'])
            mo.inputs['Emissive Strength'].default_value = 1.0
            for l in list(mo.inputs['Emissive Texture'].links):
                nt.links.remove(l)
            mo.inputs['Emissive Texture'].default_value = (1.0, 1.0, 1.0, 1.0)
            from .look import refresh_pbr
            refresh_pbr(m)

    def _disc_nodes(self):
        disc = self.uf.get('acc_sundisc')
        if disc is None:
            return
        R = self._rest(disc)
        n0 = disc.data.vertices[0].normal if len(disc.data.vertices) else Vector((0, 0, 1))
        n_model = (R.to_3x3() @ n0)
        disc_face = 1 if -n_model.y >= 0 else -1                # three's +z = Blender -y (her front)
        for m in self.mats.get('sundisc', []):
            mo = m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output')
            img_n = m.node_tree.nodes.get('Mtoon1BaseColorTexture.Image')
            if mo is None or img_n is None or img_n.image is None:
                continue
            nt = m.node_tree
            clear_cs(nt)
            b = CSBuilder(nt, x0=-4200, y0=-2400)
            t = TSL(b, self.arm, scale=self.scale)
            geo = b.node('ShaderNodeNewGeometry')
            bf = b.s(geo.outputs['Backfacing'])
            front = (1.0 - bf) if disc_face > 0 else bf
            tex_c = Vec(b, img_n.outputs['Color'])
            b.link(_cscale(b, tex_c, b.mix(0.1, 1.0, front)), mo.inputs['Lit Color'])
            mo.inputs['Lit Color Texture Color'].default_value = (1.0, 1.0, 1.0, 1.0)
            for l in list(mo.inputs['Lit Color Texture Color'].links):
                nt.links.remove(l)
            b.link(_cscale(b, tex_c, b.mix(0.05, 0.7, front)), mo.inputs['Shade Color'])
            em = nt.nodes.get('Mtoon1EmissiveTexture.Image')
            if em is not None and em.image is not None:
                b.link(_cscale(b, Vec(b, em.outputs['Color']), front * t.u('neon')), mo.inputs['Emissive Factor'])
                for l in list(mo.inputs['Emissive Texture'].links):
                    nt.links.remove(l)
                mo.inputs['Emissive Texture'].default_value = (1.0, 1.0, 1.0, 1.0)
            from .look import refresh_pbr
            refresh_pbr(m)

    def _badge_emission(self):
        """each badge material's emissive strength = its own x the badge's keyed glow ('cs_tuta.glow.<k>')"""
        self._badge_base = {}
        for k in BADGES:
            for m in self.mats.get(k, []):
                mo = m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output') if m.node_tree else None
                if mo is None:
                    continue
                s = mo.inputs['Emissive Strength']
                base = self._badge_base.get(m.name, float(s.default_value))
                self._badge_base[m.name] = base
                drive(s, 'default_value', self.arm, f'cs_tuta.glow.{k}', var='g', expression=f'{base!r}*g')
                from .look import refresh_pbr
                refresh_pbr(m)             # the PBR look's emission strength driven the same way

    # ------------------------------------------------------------------------------------------- keyed values
    def _prop(self, name, value, frame=None):
        """a uniform set now, or keyed at `frame`: a STEP there (CONSTANT: wear, neon, face_paint ... change state
        at that moment, as the JS sets a uniform), or, inside bake(), one of its per-frame values (made LINEAR at
        the bake's end, so sub-frames interpolate between frames)"""
        self.arm[name] = float(value)
        if frame is not None:
            self.arm.keyframe_insert(f'["{name}"]', frame=frame)
            if getattr(self, '_baking', False):
                self._bake_paths.add(f'["{name}"]')
            else:
                _key_interp(self.arm, f'["{name}"]', frame, 'CONSTANT')
                self.arm.update_tag()      # see _paint.tag_keyed: the session's depsgraph takes the new keys

    def _on_tuta(self, frame=None):
        """is the TuTa worn (at `frame`: the outfit keyed there, so a bake over an outfit switch hides the badges
        off the TuTa, as the JS's update(t) does with the outfit worn at t)"""
        return 'tuta' in ((WARDROBE.get(self.worn_at(frame)) or {}).get('uf') or [])

    def _badge_visible(self, k, on, frame):
        o = self.uf.get(k)
        if o is not None:
            self._show(o, on and self._on_tuta(frame), frame)

    # ------------------------------------------------------------------------------------------- the API
    @property
    def badges(self):
        return {k: self.uf.get(k) for k in BADGES}

    @property
    def base(self):
        """the JS's api.base: the garment wardrobe under the TuTa (here the TuTa wardrobe is one, by inheritance)"""
        return self

    @property
    def all_layers(self):
        """the JS's api.layers: the garment layers and the TuTa's own (tuta, boots, straps, badges, disc)"""
        return {**self.layers, **self.uf}

    @property
    def pinned(self):
        return {k for k in BADGES if k not in self.state['events'] and self.state['now'][k]['on']}

    @property
    def ghosts(self):
        return {k for k in BADGES if k not in self.state['events'] and self.state['now'][k]['ghost'] > 0}

    @property
    def uniforms(self):
        return {k: self.arm.get(f'cs_tuta.{k}') for k in list(PROPS) + [f'ghost.{b}' for b in BADGES]}

    def eye_lights(self, amount=1.0, neon=False, frame=None):
        self._prop('cs_tuta.eyes', amount, frame)
        self._prop('cs_tuta.eye_neon', 1.0 if neon else 0.0, frame)

    def wear(self, key, frame=None):
        if key == self.current and frame is None:
            return
        p = WARDROBE.get(key) or WARDROBE['suit']
        super().wear(key, frame)
        show = p.get('uf') or []
        for n in ('tuta', 'uf_boots', 'uf_straps'):
            if n in self.uf:
                self._show(self.uf[n], n in show, frame)
        for o in self._base_shoes:
            self._show(o, 'shoes' not in (p.get('hideBase') or []), frame)
        on = 'tuta' in show
        self._prop('cs_tuta.eyes', 1.0 if on else float(p.get('eyeLights', 0)), frame)
        self._prop('cs_tuta.eye_neon', 1.0 if on else 0.0, frame)
        for k in BADGES:
            if k not in self.state['events']:
                self._badge_visible(k, self.state['now'][k]['on'], frame)
        if 'acc_sundisc' in self.uf:
            self._show(self.uf['acc_sundisc'], self.state['disc'], frame)

    def _check(self, k):
        if k not in BADGES:
            raise KeyError(f'claudesona tuta: no badge {k} ({", ".join(BADGES)})')

    def pin(self, key, at=None, frame=None):
        """pin a badge now (or keyed at `frame`), or with at=t a snap scheduled at film time t (bake() keys it)"""
        self._check(key)
        if at is not None:
            return self._event(key, {'kind': 'pin', 'at': float(at)})
        self.state['events'].pop(key, None)
        self.state['now'][key] = {'on': True, 'ghost': 0}
        self._show_state(key, {'mode': 'attached', 'ghost': 0, 's': 1.0, 'g': 0.0}, frame)

    def unpin(self, key, ghost=True, at=None, eject=False, linger=False, frame=None):
        """take a badge off: its ghost stays unless ghost=False; at=t unsnaps it at film time t; eject=True pops it
        off and tumbles it away (at t, or at the last bake's end); linger=True leaves it where it lands"""
        self._check(key)
        if eject:
            return self._event(key, {'kind': 'unpin', 'at': float(at if at is not None else self.state['last_t']),
                                     'ghost': ghost, 'eject': True, 'linger': linger})
        if at is not None:
            return self._event(key, {'kind': 'unpin', 'at': float(at), 'ghost': ghost})
        self.state['events'].pop(key, None)
        self.state['now'][key] = {'on': False, 'ghost': 1 if ghost else 0}
        self._show_state(key, {'mode': 'hidden', 'ghost': 1 if ghost else 0, 's': 1.0, 'g': 0.0}, frame)

    def schedule(self, events):
        """replace the whole schedule: [{at, pin}, {at, unpin, ghost, eject, linger}, ...]"""
        self.state['events'] = {}
        for e in events:
            if e.get('pin'):
                self.pin(e['pin'], at=e['at'])
            elif e.get('unpin'):
                self.unpin(e['unpin'], at=e['at'], ghost=e.get('ghost', True), eject=bool(e.get('eject')),
                           linger=bool(e.get('linger')))

    def _event(self, key, e):
        self.state['events'].setdefault(key, []).append(e)
        self.state['events'][key].sort(key=lambda x: x['at'])

    def clear_ghost(self, key, frame=None):
        self._check(key)
        self.state['events'].pop(key, None)
        self.state['now'][key]['ghost'] = 0
        self._prop(f'cs_tuta.ghost.{key}', 0.0, frame)

    def face_paint(self, on, frame=None):
        v = 1.0 if on is True else 0.0 if on is False else max(0.0, min(1.0, float(on)))
        self.state['paint'] = v
        self._prop('cs_tuta.paint', v, frame)

    def sun_disc(self, on, frame=None):
        self.state['disc'] = bool(on)
        if 'acc_sundisc' in self.uf:
            self._show(self.uf['acc_sundisc'], self.state['disc'], frame)

    def neon(self, level, frame=None):
        self._prop('cs_tuta.neon', level, frame)
        for k in BADGES:
            if k not in self._flyers:
                self._prop(f'cs_tuta.glow.{k}', level, frame)

    # ------------------------------------------------------------------------------------------- the schedule
    def _rnd(self, k, i):
        x = math.sin((BADGES.index(k) + 1) * 127.1 + i * 311.7) * 43758.5453
        return x - math.floor(x)

    def eval_at(self, k, t):
        evs = self.state['events'][k]
        last = None
        for e in evs:
            if e['at'] <= t:
                last = e
        if last is None:
            now = self.state['now'][k]
            return {'mode': 'attached' if now['on'] else 'hidden', 'ghost': now['ghost'], 's': 1.0, 'g': 0.0}
        tau = t - last['at']
        u = tau / SNAP
        if last['kind'] == 'pin':
            if u >= 1:
                return {'mode': 'attached', 'ghost': 0, 's': 1.0, 'g': 0.0}
            s = 1 + 0.35 * math.sin(u * math.pi) * (1 - u) + (-0.6 * (1 - u / 0.25) if u < 0.25 else 0.0)
            return {'mode': 'attached', 'ghost': 0, 's': s, 'g': 3.0 * (1 - u) ** 2}
        ghost = 1 if last.get('ghost') else 0
        if last.get('eject'):
            if tau < POP + FLY:
                return {'mode': 'flying', 'ghost': ghost, 'tau': tau, 'ev': last}
            return {'mode': 'resting' if last.get('linger') else 'hidden', 'ghost': ghost, 'tau': POP + FLY, 'ev': last}
        if u >= 1:
            return {'mode': 'hidden', 'ghost': ghost, 's': 1.0, 'g': 0.0}
        return {'mode': 'attached', 'ghost': min(1.0, u * 1.4) if last.get('ghost') else 0.0, 's': 1 - u * u,
                'g': 4.0 * math.sin(min(1.0, u * 2) * math.pi)}

    def flight_at(self, k, ev, tau):
        """the world pose (Blender axes) at film time t of badge k ejected by ev, the JS's fixed-step flight"""
        L = ev['launch']
        n = L['n'].copy()
        p, q, sc = L['p'].copy(), L['q'].copy(), L['s'].copy()
        up = Vector((0.0, 0.0, 1.0))
        if tau < POP:
            u = tau / POP
            p = p + n * (0.03 * (u * (2 - u)))
            return {'p': p, 'q': q, 's': sc * (1 + 0.35 * math.sin(math.pi * u)), 'glow': 5.0, 'alive': True}
        p = p + n * 0.03
        side = n.cross(up)
        if side.length_squared < 1e-4:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        E = self.ej
        v = n * E['out'] + up * E['up'] + side * ((self._rnd(k, 1) - 0.5) * 0.6)
        # the JS's random spin axis is in three's axes: (x, y, z) -> Blender (x, -z, y)
        ax3 = Vector((self._rnd(k, 2) - 0.5, self._rnd(k, 3) - 0.5, self._rnd(k, 4) - 0.5))
        axis = (Vector((ax3.x, -ax3.z, ax3.y)) + side * 1.2).normalized()
        w = 2 * math.pi * (E['spin'] + self._rnd(k, 5) * 1.6)
        ang = 0.0
        half = 0.004 * sc.x / 0.87
        dt = 1 / 240
        steps = min(int(math.floor((tau - POP) / dt)), int(math.ceil(FLY / dt)))
        for _ in range(steps):
            v.z -= E['g'] * dt
            v *= math.exp(-E['drag'] * dt)
            p = p + v * dt
            ang += w * dt
            if p.z < self.floor_z + half:
                p.z = self.floor_z + half
                if v.z < 0:
                    v.z = -v.z * 0.3
                v.x *= 0.72
                v.y *= 0.72
                w *= 0.5
                if abs(v.z) < 0.15:
                    v.z = 0.0
        q = Quaternion(axis, ang) @ q
        u = min(1.0, (tau - POP) / FLY)
        flick = 1.0 if (tau - POP) < 0.12 else (1.0 if self._rnd(k, 100 + int(math.floor(tau * 26))) > 0.32 else 0.15)
        return {'p': p, 'q': q, 's': sc, 'glow': 1.6 * (1 - u) ** 1.6 * flick, 'alive': tau < POP + FLY}

    def _flyer(self, k):
        if k in self._flyers:
            return self._flyers[k]
        src = self.uf[k]
        o = bpy.data.objects.new(f'{src.name}.flight', src.data)
        for c in src.users_collection:
            c.objects.link(o)
        o.rotation_mode = 'QUATERNION'
        o.hide_render = o.hide_viewport = True
        o.keyframe_insert('hide_render', frame=bpy.context.scene.frame_start)
        o.keyframe_insert('hide_viewport', frame=bpy.context.scene.frame_start)
        self._flyers[k] = o
        return o

    def _spark(self, k):
        if k in self._sparks:
            return self._sparks[k]
        glow = lin(SPEC['badges'][k]['glow'])

        def mat(flare):
            m = bpy.data.materials.new(f'cs.spark.{k}.{"flare" if flare else "ember"}')
            m.use_nodes = True
            m.surface_render_method = 'BLENDED'
            nt = m.node_tree
            for n in list(nt.nodes):
                nt.nodes.remove(n)
            b = CSBuilder(nt)
            uvn = b.node('ShaderNodeTexCoord')
            u, v, _w = b.vec(uvn.outputs['UV']).xyz()
            qx, qy = (u - 0.5) * 2.0, (v - 0.5) * 2.0
            r = b.sqrt(qx * qx + qy * qy)
            if flare:
                shape = b.max(b.exp(r * -7.0), b.max(b.exp(b.abs(qx) * -38.0) * b.exp(b.abs(qy) * -3.0),
                                                     b.exp(b.abs(qy) * -38.0) * b.exp(b.abs(qx) * -3.0)))
            else:
                shape = b.exp(r * r * -9.0)
            a = b.node('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name='cs_spark')
            av = b.s(a.outputs['Fac'])
            em = b.node('ShaderNodeEmission')
            # three's AdditiveBlending (SrcAlpha, One) adds colorNode x opacityNode, both shape x a: the light added
            # over what is behind is (glow x 4 + 0.8) x (shape x a)^2 (an Emission over a clear Transparent adds it)
            op = shape * av
            b.link(_cscale(b, tuple(c * 4.0 + 0.8 for c in glow), op * op), em.inputs['Color'])
            em.inputs['Strength'].default_value = 1.0
            tr = b.node('ShaderNodeBsdfTransparent')
            ad = b.node('ShaderNodeAddShader')
            b.link(em.outputs[0], ad.inputs[0])
            b.link(tr.outputs[0], ad.inputs[1])
            out = b.node('ShaderNodeOutputMaterial')
            b.link(ad.outputs[0], out.inputs['Surface'])
            return m

        def card(name, m):
            me = bpy.data.meshes.new(name)
            me.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
            uv = me.uv_layers.new()
            for i, c in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
                uv.data[i].uv = c
            me.materials.append(m)
            o = bpy.data.objects.new(name, me)
            bpy.context.scene.collection.objects.link(o)
            o['cs_spark'] = 0.0
            o.hide_render = o.hide_viewport = True
            # hidden from the film's start, as the flight copy is: its first visibility key is the pop's (visible),
            # and a key holds back to the start, so without this the flare shone beside the badge from frame 1
            f_s = bpy.context.scene.frame_start
            o.keyframe_insert('hide_render', frame=f_s)
            o.keyframe_insert('hide_viewport', frame=f_s)
            md = o.modifiers.new('cs.billboard', 'NODES')      # a sprite: faces whichever camera renders
            md.node_group = _billboard_group()
            return o
        mf, me_ = mat(True), mat(False)
        s = {'flare': card(f'cs.spark.{k}.flare', mf), 'embers': [card(f'cs.spark.{k}.ember{j}', me_) for j in range(8)]}
        self._sparks[k] = s
        return s

    def _key_show(self, o, on, f):
        o.hide_render = o.hide_viewport = not on
        o.keyframe_insert('hide_render', frame=f)
        o.keyframe_insert('hide_viewport', frame=f)

    def _show_state(self, k, st, frame):
        o = self.uf.get(k)
        if o is None:
            return
        self._prop(f'cs_tuta.ghost.{k}', st['ghost'], frame)
        neon = float(self.arm['cs_tuta.neon'])
        if st['mode'] in ('flying', 'resting'):
            ev = st['ev']
            fl = self._flyer(k)
            if 'launch' not in ev:                  # the world pose at the pop (attached at home)
                o.matrix_basis = self.home[k]
                bpy.context.view_layer.update()
                p, q, s = o.matrix_world.decompose()
                ev['launch'] = {'p': p, 'q': q, 's': s, 'n': (q @ Vector((0.0, 0.0, 1.0))).normalized()}
            Fp = self.flight_at(k, ev, st['tau'])
            fl.location, fl.rotation_quaternion, fl.scale = Fp['p'], Fp['q'], Fp['s']
            vis = self._on_tuta(frame) and (Fp['alive'] or st['mode'] == 'resting')
            if frame is not None:
                for pth in ('location', 'rotation_quaternion', 'scale'):
                    fl.keyframe_insert(pth, frame=frame)
                self._key_show(fl, vis, frame)
                self._key_show(o, False, frame)
            self._prop(f'cs_tuta.glow.{k}', 0.0 if st['mode'] == 'resting' else neon * Fp['glow'], frame)
            sp = self._spark(k)
            L = ev['launch']
            if st['tau'] < 0.22 and self._on_tuta(frame):
                u = st['tau'] / 0.22
                a = (1 - u) ** 1.5 * neon
                n = L['n']
                side = n.cross(Vector((0.0, 0.0, 1.0)))
                if side.length_squared < 1e-4:
                    side = Vector((1.0, 0.0, 0.0))
                side.normalize()
                upv = side.cross(n).normalized()
                fl_o = sp['flare']
                fl_o.location = L['p'] + n * 0.05
                fl_o.scale = (0.05 + 0.16 * math.sqrt(u),) * 3
                fl_o['cs_spark'] = a
                for j, e in enumerate(sp['embers']):
                    th = 2 * math.pi * (j / 8 + self._rnd(k, 200 + j) * 0.1)
                    d = (side * math.cos(th) + upv * math.sin(th) + n * 0.8).normalized()
                    sp2 = 1.2 + self._rnd(k, 300 + j) * 0.9
                    e.location = L['p'] + n * 0.03 + d * (sp2 * st['tau']) + Vector((0.0, 0.0, -2.5 * st['tau'] ** 2))
                    e.scale = (0.02 * (1 - 0.5 * u),) * 3
                    e['cs_spark'] = a
                on = True
            else:
                on = False
            if frame is not None:
                for e in [sp['flare']] + sp['embers']:
                    e.keyframe_insert('location', frame=frame)
                    e.keyframe_insert('scale', frame=frame)
                    e.keyframe_insert('["cs_spark"]', frame=frame)
                    self._key_show(e, on, frame)
            return
        if k in self._sparks and frame is not None:
            for e in [self._sparks[k]['flare']] + self._sparks[k]['embers']:
                self._key_show(e, False, frame)
        if k in self._flyers and frame is not None:
            self._key_show(self._flyers[k], False, frame)
        o.matrix_basis = self.home[k]
        s = max(1e-4, st.get('s', 1.0))
        o.scale = tuple(c * s for c in o.scale)
        self._prop(f'cs_tuta.glow.{k}', neon * (1 + st.get('g', 0.0)), frame)
        if frame is not None:
            o.keyframe_insert('scale', frame=frame)
        self._badge_visible(k, st['mode'] == 'attached', frame)

    def update(self, t, frame=None):
        """the JS's per-frame update(t): every scheduled badge takes its state at film time t (keyed at `frame`)"""
        self.state['last_t'] = t
        for k in BADGES:
            if k in self.state['events']:
                self._show_state(k, self.eval_at(k, t), frame)

    def bake(self, f0, f1, scene=None):
        """update(t) on every frame f0..f1 in order, keyed (an ejection's launch is captured at its first frame at
        or after `at`, so bake in one pass from before it); returns a report"""
        from ...media.timebase import Timebase
        from ._paint import tag_keyed
        scene = scene or bpy.context.scene
        tb = Timebase.of(scene)
        n = 0
        self._baking, self._bake_paths = True, set()
        tag_keyed(self.arm)              # keys made since the last depsgraph build (neon, outfits) evaluate per frame
        try:
            for f in range(int(f0), int(f1) + 1):
                scene.frame_set(f)
                self.update(tb.t(f), frame=f)
                n += 1
        finally:
            self._baking = False
        _linear(self.arm, tuple(self._bake_paths))          # the scheduled badges' glow and ghost, per frame
        tag_keyed(self.arm)
        for o in list(self._flyers.values()) + [self.uf[k] for k in BADGES if k in self.uf] + \
                [e for s in self._sparks.values() for e in [s['flare']] + s['embers']]:
            _linear(o, ('location', 'rotation_quaternion', 'scale', '["cs_spark"]'))
        return {'frames': n, 'badges': sorted(self.state['events']), 'flyers': sorted(self._flyers)}

    def badge_world(self, key, frame=None):
        """{position, quaternion, flying, visible} of a badge (world, Blender axes) at a frame (default: now)"""
        self._check(key)
        sc = bpy.context.scene
        if frame is not None:
            sc.frame_set(frame)
        fl = self._flyers.get(key)
        o = fl if (fl is not None and not fl.hide_render) else self.uf[key]
        p, q, _s = o.matrix_world.decompose()
        return {'position': p, 'quaternion': q, 'flying': o is fl, 'visible': not o.hide_render}
