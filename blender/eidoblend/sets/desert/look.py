"""eidoblend.sets.desert.look: the desert round a town, as a Blender collection; and lenses on it. Blender:

    from eidoblend.sets.desert import look
    D = look.build('work/desert')               # from <work>/build (land.py and mesh.py made it): the collection 'desert'
    look.shoot(D, 'work/desert/stills', town=(840, 300))   # the views, the town built beside it, under the town's light

What it makes, all in ONE collection 'desert' (the town's own metres; no lights: the town's sun lights it):
  desert_ground  the land (land.py, meshed by mesh.py: a restricted quadtree, crack-free, about 2.6 M faces from 2 m
                 cells round the town to 256 m at 30 km), its masks as point attributes (d_town, d_sand, d_sheet,
                 d_bed, d_bar, d_esc, d_mtn, d_apron)
  desert_scrub   the scrub: low shrubs, each on the sand it caught (a nebkha), thick along the wadis
  desert.ground  ONE material: THE TOWN'S OWN GROUND first (eidoblend.sets.town.materials ground_plain through
                 fam_ground: the same sets in the same object metres, so where the desert rises out of the town's
                 plane there is no seam), then by cause: desert pavement and the aprons' gravel, the wadis' pale beds
                 and their bars, the tracks (in the town's own track colour, so they go on from the town's), the sand
                 sheet, the dunes (ripples on the windward sides, smooth slip faces), the escarpment (beds of limestone
                 and marl in its cliff band, scree on its talus, caprock on top), the ranges' dark rock and debris; and
                 the air past the town's haze box: aerial perspective by distance from the lens (AIR: the far ranges
                 pale and blue-grey, the near desert warm). Its CC0 sets: cc0_sets.json beside this file, and the
                 town's own.
Put 'desert' at the town's origin, unrotated, unscaled (its materials read OBJECT metres, as the town's do), and give
the scene the town's settings (town.eevee: the volumes out to 3.5 km) and a camera clip_end of 33 km or more. The
desert lies UNDER the town's plane (z -0.5) wherever the town has anything on the ground and rises through z 0 about
25 m out, so the town's own ground plane stays as it is.
"""
import json
import math
import os
import time

import bpy
import numpy as np
from mathutils import Vector

from ..town import materials as TM
from ..town import world as TW

HERE = os.path.dirname(os.path.abspath(__file__))
TM.REG.update(json.load(open(os.path.join(HERE, 'cc0_sets.json'), encoding='utf-8'))['sets'])     # (the desert's sets beside the town's)
MASKS = ('town', 'sand', 'sheet', 'bed', 'bar', 'esc', 'mtn', 'apron')
# THE AIR past the town's haze box (world.AIR: 5.2 km across; past its walls only the material can thin the land into
# the sky): extinction per metre past d0, and the colour the far land goes to (the sky low down, dusty). It starts
# where the town's box has already greyed the land and thins it slowly to the ranges at 25 km
AIR = dict(d0=4000.0, sigma=2.5e-5, color=(0.60, 0.62, 0.66), strength=1.0)
RING = ((0.0, 0.0), (-380.0, 0.0), (380.0, 0.0))
LOOKS = (('mY', 270.0), ('pY', 90.0), ('mX', 180.0), ('pX', 0.0))
BUILD = None                                                     # <work>/build of the desert being made (build() sets it)


class Desert:
    """what build() made: collection, ground, scrub, work"""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def build(work, collection=None, log=print):
    """the collection 'desert' from <work>/build -> Desert"""
    global BUILD
    BUILD = os.path.join(os.path.abspath(work), 'build')
    t0 = time.time()
    if collection is None:
        collection = bpy.data.collections.new('desert')
        bpy.context.scene.collection.children.link(collection)
    g = ground(collection)
    s = scrub(collection)
    for img in bpy.data.images:                                      # (the marks travel inside the file)
        if img.filepath and os.path.basename(img.filepath) in ('near_marks.png', 'mid_marks.png') and not img.packed_file:
            img.pack()
    placed = sum(len(o.data.polygons) for o in collection.objects if o.type == 'MESH')
    log(f'[desert] built: {len(collection.objects)} objects, {placed} placed faces, {time.time() - t0:.1f} s')
    return Desert(collection=collection, ground=g, scrub=s, work=os.path.abspath(work), placed_faces=placed)


# ================================================================================================= the land's mesh
def ground(col):
    z = np.load(os.path.join(BUILD, 'desert_mesh.npz'))
    co, quads, tris = z['co'], z['quads'], z['tris']
    me = bpy.data.meshes.new('desert_ground')
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    loops = np.concatenate([quads.ravel(), tris.ravel()]).astype(np.int32)
    me.loops.add(len(loops))
    me.loops.foreach_set('vertex_index', loops)
    nq, nt = len(quads), len(tris)
    me.polygons.add(nq + nt)
    me.polygons.foreach_set('loop_start', np.concatenate([np.arange(nq) * 4, nq * 4 + np.arange(nt) * 3]).astype(np.int32))
    try:
        me.polygons.foreach_set('loop_total', np.concatenate([np.full(nq, 4), np.full(nt, 3)]).astype(np.int32))
    except (AttributeError, TypeError, RuntimeError):
        pass                                                         # (read only in this Blender: it follows the starts)
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(nq + nt, bool))
    for m in MASKS:
        a = me.attributes.new('d_' + m, 'FLOAT', 'POINT')
        a.data.foreach_set('value', z['a_' + m].astype(np.float32))
    me.validate(clean_customdata=False)
    o = bpy.data.objects.new('desert_ground', me)
    col.objects.link(o)
    me.materials.append(ground_material())
    print(f'[desert] ground: {len(me.vertices)} vertices, {len(me.polygons)} faces', flush=True)
    return o


# ================================================================================================= its material
def _attr(t, name):
    def mk():
        a = t.N.new('ShaderNodeAttribute')
        a.attribute_type, a.attribute_name = 'GEOMETRY', name
        return a.outputs['Fac']
    return t.once('da:' + name, mk)


def _marks(t, X, Y):
    """the marks finer than the mesh (desert_land.py marks()): the 1 m image within 2 km, the 4 m one to 8 km.
    (R tracks, G beds and bars, B the bars' crests, A the sand sheet)"""
    out = []
    for fn, half in (('near_marks.png', 2048.0), ('mid_marks.png', 8192.0)):
        img = bpy.data.images.load(os.path.join(BUILD, fn), check_existing=True)
        img.colorspace_settings.name = 'Non-Color'
        img.alpha_mode = 'CHANNEL_PACKED'
        u = t.m('DIVIDE', t.add(X, half), 2.0 * half)
        v = t.m('DIVIDE', t.add(Y, half), 2.0 * half)
        n = t.N.new('ShaderNodeTexImage')
        n.image, n.interpolation, n.extension = img, 'Linear', 'CLIP'
        t.L.new(t.comb(u, v, 0.0), n.inputs['Vector'])
        sep = t.N.new('ShaderNodeSeparateColor')
        t.L.new(n.outputs['Color'], sep.inputs[0])
        inside = t.mul(t.inv(t.sm(t.m('ABSOLUTE', X), half - 60.0, half - 10.0)), t.inv(t.sm(t.m('ABSOLUTE', Y), half - 60.0, half - 10.0)))
        out.append(([sep.outputs[0], sep.outputs[1], sep.outputs[2], n.outputs['Alpha']], inside))
    (near, w_n), (mid, w_m) = out
    return [t.mixf(w_n, t.mul(m_, w_m), n_) for n_, m_ in zip(near, mid)]


def strata(t, e, P):
    """the escarpment's beds by its own height over the floor (e, metres: the plateau stands about 200 m): a pale hard
    caprock band at the top, a buff cliff under it, a pale ledge, a grey-green marl band, the lower slopes greyer; each
    boundary a little warped, and few of them (thin beds every few metres would draw contour lines over every wall)"""
    warp = t.mul(t.sub(t.noise(P, 1.0 / 380.0, 2.0, off=(3.0, 1.0, 0.0)), 0.5), 12.0)
    f = t.m('DIVIDE', t.add(e, warp), 200.0)
    col = (0.36, 0.32, 0.26, 1.0)                                      # the lower slopes
    for lo, w, rgb in ((0.34, 0.03, (0.43, 0.41, 0.35)),             # the marl band, grey-green
                       (0.55, 0.015, (0.50, 0.45, 0.36)),            # a pale ledge
                       (0.61, 0.02, (0.44, 0.38, 0.29)),             # the buff cliff
                       (0.84, 0.012, (0.54, 0.49, 0.40))):           # the caprock
        col = t.mixc(t.sm(f, lo - w, lo + w), col, (*rgb, 1.0))
    return col


def ground_material():
    m = bpy.data.materials.get('desert.ground')
    if m is not None:
        return m
    m = bpy.data.materials.new('desert.ground')
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    t = TM.T(nt)
    P = t.P0()
    X, Y, Z = t.xyz0()
    nz = t.nz()
    # 1. THE TOWN'S OWN GROUND (its sets, its fronts, its regional tint, its scrub dots): the plain goes on from it
    col, rough, _, h = TM.fam_ground(t, 'ground', None)
    a = {k: _attr(t, 'd_' + k) for k in MASKS}
    away = t.sm(a['town'], 40.0, 260.0)                               # (nothing of the desert's own at the crossing)
    R, G, B, A = _marks(t, X, Y)
    # 2. desert pavement on the older surfaces between the channels, and the aprons' gravel: two sizes of older surface,
    #    darker, and the whole floor past 1.5 km going to the grey-brown of varnished gravel
    pav = t.mx(t.sm(t.noise(P, 1.0 / 650.0, 3.0, off=(11.0, 3.0, 0.0)), 0.50, 0.62), t.mul(t.sm(t.noise(P, 1.0 / 210.0, 3.0, off=(2.0, 8.0, 0.0)), 0.56, 0.66), 0.7))
    pav = t.mul(t.mul(pav, away), t.inv(t.mx(G, A)))
    # (varnished gravel is near brown-black: dark and strong enough to hold through the town's dust at 1 km)
    c_pav = t.tint(t.ncol('stony', P, 'FLAT', k=0.55), (0.20, 0.175, 0.145))
    col = t.mixc(t.mul(pav, 0.86), col, c_pav)
    # the other end of the same surfaces: pale silt where the sheet floods spread out and dried
    silt = t.mul(t.mul(t.inv(t.sm(t.noise(P, 1.0 / 650.0, 3.0, off=(11.0, 3.0, 0.0)), 0.37, 0.46)), away), t.inv(t.mx(G, A)))
    c_silt = t.tint(t.ncol('mud_cracked', P, 'FLAT', k=0.6), (0.47, 0.41, 0.31))
    col = t.mixc(t.mul(silt, 0.65), col, c_silt)
    far = t.mul(t.sm(a['town'], 1200.0, 4500.0), 0.42)
    col = t.mixc(far, col, t.tint(t.ncol('gravel_ground', P, 'FLAT', k=0.6), (0.30, 0.27, 0.22)))
    # the floor's drainage lines: finer, darker silt, the scrub along them (land.py RILL)
    rill = t.mul(t.sm(B, 0.12, 0.75), away)
    c_rill = t.tint(t.ncol('dry_ground', P, 'FLAT', k=0.7), (0.20, 0.17, 0.13))
    col = t.mixc(t.mul(rill, 0.8), col, c_rill)
    apr = t.mul(t.sm(a['apron'], 1.5, 30.0), away)
    c_apr = t.tint(t.ncol('sandy_gravel', P, 'FLAT', k=0.7), (0.43, 0.38, 0.30))
    col = t.mixc(t.mul(apr, 0.75), col, c_apr)
    # 3. the wadis: pale beds of sand and grit, their bars greyer with the scrub on them
    in_bed = t.mx(t.sm(G, 0.30, 0.55), t.mul(t.sm(a['bed'], 0.3, 0.9), t.inv(t.sm(t.m('ABSOLUTE', X), 7900.0, 8100.0))))
    c_bed = t.tint(t.ncol('gravel_sand', P, 'FLAT', k=0.75), (0.47, 0.41, 0.32))
    col = t.mixc(t.mul(in_bed, 0.85), col, c_bed)
    on_bar = t.sm(G, 0.68, 0.95)
    c_bar = t.tint(t.ncol('sandy_gravel', P, 'FLAT', k=0.8), (0.37, 0.33, 0.26))
    col = t.mixc(t.mul(on_bar, 0.8), col, c_bar)
    # 4. the tracks: packed, paler, in the town's own track set and tint (town materials' track_surface)
    trk = t.sm(R, 0.08, 0.6)
    c_trk = t.value(t.tint(t.ncol('gravel_ground', P, 'FLAT', k=0.85), (0.38, 0.32, 0.23)), t.add(0.95, t.mul(t.noise(P, 0.08, 3.0), 0.22)))
    col = t.mixc(t.mul(trk, 0.9), col, c_trk)
    rough = t.mixf(trk, rough, 0.88)
    # 5. the sand sheet round the dunes, and the dunes: ripples on the windward sides, smooth slip faces
    sheet = t.mul(t.sm(A, 0.15, 0.9), away)
    c_sheet = t.tint(t.ncol('pale_sand', P, 'FLAT', k=1.0), (0.47, 0.37, 0.25))
    col = t.mixc(t.mul(sheet, 0.7), col, c_sheet)
    dune = t.sm(a['sand'], 0.25, 2.5)
    slip = t.inv(t.sm(nz, 0.86, 0.93))
    c_rip = t.tint(t.ncol('dune_ripples', P, 'FLAT', k=0.9), (0.56, 0.40, 0.24))      # (a warm orange sand)
    c_slip = t.tint(t.ncol('pale_sand', P, 'FLAT', k=1.0), (0.58, 0.43, 0.27))
    c_dune = t.mixc(slip, c_rip, c_slip)
    c_dune = t.value(c_dune, t.add(0.9, t.mul(t.sm(a['sand'], 2.0, 40.0), 0.12)))     # (thin sand in the troughs a little greyer)
    col = t.mixc(dune, col, c_dune)
    h = t.mixf(dune, h, t.mul(t.height('dune_ripples', P, 'FLAT'), t.inv(slip)))
    # 6. the escarpment: beds in its cliff band, scree on its talus, caprock on its top
    esc = t.sm(a['esc'], 0.5, 6.0)
    cliff = t.inv(t.sm(nz, 0.45, 0.72))
    talus = t.mul(t.inv(t.sm(nz, 0.80, 0.95)), t.inv(cliff))
    top = t.mul(t.sm(nz, 0.93, 0.985), t.sm(a['esc'], 110.0, 170.0))
    # (a 3.6 m rock tile is a pixel at 1.5 km: the same scans again at 40 m and 112 m give the joints and ledges at the
    #  size the lens sees; desert varnish runs down from the rim)
    grain = t.vm('MULTIPLY', t.ncol('cliff_rock', P, 'BOX', k=0.8),
                 t.vm('MULTIPLY', t.ncol('cliff_rock', P, 'BOX', k=0.9, scale=11.0), t.ncol('cliff_warm', P, 'BOX', k=0.7, scale=28.0)))
    varnish = t.sm(t.noise(P, 1.0, 3.0, off=(7.0, 2.0, 0.0), stretch=(1.0 / 21.0, 1.0 / 21.0, 1.0 / 240.0)), 0.47, 0.70)
    c_cliff = t.value(t.tint(grain, strata(t, a['esc'], P)), t.inv(t.mul(varnish, 0.42)))
    c_scree = t.tint(t.ncol('scree', P, 'BOX', k=0.6), (0.37, 0.32, 0.26))
    c_cap = t.tint(t.ncol('caprock', P, 'FLAT', k=0.8), (0.36, 0.31, 0.24))
    col = t.mixc(t.mul(esc, t.mul(talus, 0.9)), col, c_scree)
    col = t.mixc(t.mul(esc, t.mul(top, 0.8)), col, c_cap)
    col = t.mixc(t.mul(esc, cliff), col, c_cliff)
    # 7. the ranges and inselbergs: dark rock on the steep, dark debris below it (near charcoal at 5 km, dark enough
    #    to hold through the dust)
    mtn = t.sm(a['mtn'], 0.5, 6.0)
    deb = t.inv(t.sm(nz, 0.88, 0.975))
    steep = t.inv(t.sm(nz, 0.55, 0.85))
    c_deb = t.tint(t.ncol('dark_gravel', P, 'FLAT', k=0.6), (0.135, 0.12, 0.105))
    c_rock = t.tint(t.vm('MULTIPLY', t.ncol('dark_rock', P, 'BOX', k=0.45), t.ncol('cliff_rock', P, 'BOX', k=0.8, scale=14.0)), (0.075, 0.07, 0.064))
    col = t.mixc(t.mul(mtn, deb), col, c_deb)
    col = t.mixc(t.mul(mtn, steep), col, c_rock)
    rocky = t.mx(t.mul(esc, t.mx(cliff, talus)), t.mul(mtn, deb))
    h = t.mixf(rocky, h, t.add(t.height('cliff_rock', P, 'BOX', k=0.6), t.height('cliff_rock', P, 'BOX', scale=11.0, k=0.35)))
    rough = t.mixf(rocky, rough, 0.9)
    # 8. the land's slow variation at the kilometre (one weather, many grounds: 11.41)
    col = t.value(col, t.add(0.93, t.mul(t.noise(P, 1.0 / 2400.0, 2.0, off=(5.0, 9.0, 0.0)), 0.14)))
    bs = t.N.new('ShaderNodeBsdfPrincipled')
    t.put(bs.inputs['Base Color'], col)
    t.put(bs.inputs['Roughness'], rough)
    bp = t.N.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value, bp.inputs['Distance'].default_value = 1.0, 1.0
    t.L.new(h, bp.inputs['Height'])
    t.L.new(bp.outputs[0], bs.inputs['Normal'])
    # 9. THE AIR past the town's haze box: the land thinned into the sky's low colour by its distance from the lens
    cam = t.N.new('ShaderNodeCameraData')
    far = t.m('MAXIMUM', t.sub(cam.outputs['View Distance'], AIR['d0']), 0.0)
    fog = t.inv(t.m('EXPONENT', t.mul(far, -AIR['sigma'])))
    em = t.N.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*AIR['color'], 1.0)
    em.inputs['Strength'].default_value = AIR['strength']
    mix = t.N.new('ShaderNodeMixShader')
    t.L.new(fog, mix.inputs[0])
    t.L.new(bs.outputs[0], mix.inputs[1])
    t.L.new(em.outputs[0], mix.inputs[2])
    t.L.new(mix.outputs[0], out.inputs['Surface'])
    print(f'[desert] desert.ground: {len(nt.nodes)} nodes', flush=True)
    return m


# ================================================================================================= the scrub
def shrub_templates(rng, kinds=4):
    """low desert shrubs (camelthorn, saltbush; tamarisk by the wadis when grown large), each a few irregular lobes of
    twigs over the low mound of sand it caught: (vertices, faces, material per face) at unit size"""
    out = []
    for k in range(kinds):
        V, F, M = [], [], []

        def lobe(cx, cy, cz, r, hz, seg=6, rings=3):                  # (6 x 3: about 0.4 M faces for 6,000 shrubs)
            base = len(V)
            jit = rng.uniform(0.78, 1.22, (rings + 1, seg))
            for i in range(rings + 1):
                th = math.pi * i / rings
                for j in range(seg):
                    ph = 2 * math.pi * j / seg + (0.5 * i)
                    rr = r * math.sin(th) * (jit[i, j] if 0 < i < rings else 1.0)
                    V.append((cx + rr * math.cos(ph), cy + rr * math.sin(ph), cz + hz * math.cos(th) * (jit[i, j] if 0 < i < rings else 1.0)))
            for i in range(rings):
                for j in range(seg):
                    a_, b_ = base + i * seg + j, base + i * seg + (j + 1) % seg
                    c_, d_ = base + (i + 1) * seg + (j + 1) % seg, base + (i + 1) * seg + j
                    if i == 0:
                        F.append((a_, d_, c_))
                    elif i == rings - 1:
                        F.append((a_, b_, d_))
                    else:
                        F.append((a_, b_, c_, d_)[::-1])
                    M.append(0)
        n_l = 2 + k % 3
        for li in range(n_l):
            ang = rng.uniform(0, 6.283)
            d = 0.0 if li == 0 else rng.uniform(0.25, 0.55)
            r = rng.uniform(0.45, 0.62) if li == 0 else rng.uniform(0.28, 0.45)
            lobe(d * math.cos(ang), d * math.sin(ang), 0.42 + r * 0.55, r, r * rng.uniform(0.62, 0.85))
        # the mound of sand round its foot
        base = len(V)
        seg = 9
        V.append((0.0, 0.0, 0.32))
        for ring, (rr, zz) in enumerate(((0.75, 0.24), (1.55, 0.0))):
            for j in range(seg):
                ph = 2 * math.pi * j / seg
                q = rng.uniform(0.85, 1.15)
                V.append((rr * q * math.cos(ph) * 1.15, rr * q * math.sin(ph), zz - (0.06 if ring == 1 else 0.0)))
        for j in range(seg):
            F.append((base, base + 1 + j, base + 1 + (j + 1) % seg))
            M.append(1)
            a_, b_ = base + 1 + j, base + 1 + (j + 1) % seg
            F.append((a_, a_ + seg, b_ + seg, b_))
            M.append(1)
        out.append((np.array(V, np.float32), F, M))
    return out


def scrub(col):
    z = np.load(os.path.join(BUILD, 'scrub.npz'))
    pos, rot, sc, kind = z['pos'], z['rot'], z['scale'], z['kind']
    rng = np.random.default_rng(41)
    T = shrub_templates(rng)
    verts, faces, mats, rnd = [], [], [], []
    base = 0
    for p, r, s, k in zip(pos, rot, sc, kind):
        V, F, M = T[int(k)]
        c, s_ = math.cos(r), math.sin(r)
        v = V * s
        v = np.column_stack([v[:, 0] * c - v[:, 1] * s_ + p[0], v[:, 0] * s_ + v[:, 1] * c + p[1], v[:, 2] + p[2] - 0.12 * s])
        verts.append(v)
        faces += [tuple(i + base for i in f) for f in F]
        mats += M
        rnd.append(np.full(len(V), rng.random(), np.float32))
        base += len(V)
    V = np.concatenate(verts).astype(np.float32)
    me = bpy.data.meshes.new('desert_scrub')
    me.from_pydata(V.tolist(), [], faces)
    me.polygons.foreach_set('material_index', np.array(mats, np.int32))
    me.polygons.foreach_set('use_smooth', np.ones(len(faces), bool))
    a = me.attributes.new('shrub_rnd', 'FLOAT', 'POINT')
    a.data.foreach_set('value', np.concatenate(rnd))
    me.materials.append(scrub_material())
    me.materials.append(ground_material())                             # (the mound: the ground it is, in the same metres)
    o = bpy.data.objects.new('desert_scrub', me)
    col.objects.link(o)
    print(f'[desert] scrub: {len(pos)} shrubs, {len(me.polygons)} faces', flush=True)
    return o


def scrub_material():
    m = bpy.data.materials.new('desert.scrub')
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    t = TM.T(nt)
    r = _attr(t, 'shrub_rnd')
    pal = t.palette(r, [(0.075, 0.085, 0.05), (0.12, 0.125, 0.08), (0.16, 0.13, 0.08), (0.10, 0.11, 0.075), (0.19, 0.17, 0.12)])
    P = t.P0()
    twig = t.add(0.7, t.mul(t.noise(P, 3.5, 3.0), 0.6))                 # (twigs and the gaps between them)
    col = t.value(pal, twig)
    col = t.mixc(t.mul(t.sm(t.nz(), 0.4, 0.95), 0.35), col, TM.DUST)   # (the dust on what faces up)
    bs = t.N.new('ShaderNodeBsdfPrincipled')
    t.put(bs.inputs['Base Color'], col)
    bs.inputs['Roughness'].default_value = 0.9
    t.L.new(bs.outputs[0], next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL').inputs['Surface'])
    return m


# ================================================================================================= the shots
def views(work=None, log=print):
    """[(name, pos, target, lens)]: a ring from 75 m at (0, 0), (-380, 0), (380, 0) toward -y, +y, -x, +x (8 degrees
    down, 35 mm: ring_c_mY ...), and two close looks found in the land: the nearest cliff band, the nearest high dunes"""
    build_dir = os.path.join(os.path.abspath(work), 'build') if work else BUILD
    out = []
    for (x, y) in RING:
        for nm, az in LOOKS:
            d = Vector((math.cos(math.radians(az)), math.sin(math.radians(az)), -math.tan(math.radians(8.0))))
            out.append((f'ring_{"c" if x == 0 else ("w" if x < 0 else "e")}_{nm}', (x, y, 75.0), tuple(Vector((x, y, 75.0)) + d * 100.0), 35))
    try:
        zB = np.load(os.path.join(build_dir, 'land_B.npz'))
        half, cell = float(zB['half']), float(zB['cell'])
        h, esc, sand = zB['h'], zB['esc'], zB['sand']
        gy, gx = np.gradient(h.astype(np.float32), cell)
        slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        n = h.shape[0]
        c = (np.arange(n) + 0.5) * cell - half
        XX, YY = np.meshgrid(c, c)
        cand = (esc > 60) & (slope > 40) & (YY > 0)
        k = np.argmin(np.where(cand, np.hypot(XX, YY), 1e12))
        tx, ty, tz = float(XX.flat[k]), float(YY.flat[k]), float(h.flat[k])
        d = Vector((tx, ty, 0.0)).normalized()
        out.append(('close_cliff_and_talus', (tx - d.x * 1300.0, ty - d.y * 1300.0, 95.0), (tx, ty, tz * 0.75), 50))
        cand = (sand > 25) & (YY < -1500) & (np.abs(XX) < 2500)
        k = np.argmin(np.where(cand, np.hypot(XX, YY + 1500), 1e12))
        tx, ty, tz = float(XX.flat[k]), float(YY.flat[k]), float(h.flat[k])
        out.append(('close_dunes', (tx + 250.0, ty + 1000.0, 75.0), (tx, ty, tz * 0.6), 45))
        log(f'[desert] close looks: cliff at ({out[-2][2][0]:.0f}, {out[-2][2][1]:.0f}), dunes at ({tx:.0f}, {ty:.0f}, {tz:.0f})')
    except (OSError, ValueError, KeyError) as e:
        log(f'[desert] close looks not found: {e}')
    return out


def shoot(D, folder, town=None, res=(960, 540), samples=16, only=None, things=True, log=print):
    """the views into `folder` as PNG, under the town's light (its sun and the sky family's sky, baked per view) and
    settings; town: (ex, ey) builds eidoblend.sets.town at that extent beside the desert (its own lenses pull_back_35mm
    and across_to_the_edge_40mm are added). -> {name: path}"""
    from .. import town as TOWN
    from ..town import views as TV
    sc = bpy.context.scene
    vs = views(D.work, log)
    if town is not None:
        T = TOWN.build(extent=town, things=things, log=log)
        vs += [v for v in T.views() if v[0] in ('pull_back_35mm', 'across_to_the_edge_40mm')]
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = int(res[0]), int(res[1]), 100
    cd = bpy.data.cameras.new('desert_lens')
    cd.clip_start, cd.clip_end = 1.0, 40000.0
    cam = bpy.data.objects.new('desert_lens', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    TV.aim(cam, *vs[0][1:])
    sky = TOWN.light(sc, cam, sky='sky', cache_dir=os.path.join(os.path.abspath(folder), 'sky_cache'), log=log)
    TOWN.eevee(sc, samples)
    os.makedirs(folder, exist_ok=True)
    sc.render.image_settings.file_format = 'PNG'
    out = {}
    for name, pos, aim, lens in vs:
        if only and not any(q in name for q in only.split(',')):
            continue
        TV.aim(cam, pos, aim, lens)
        sky.bake(sc.frame_current, sc.frame_current, log=lambda *m: None)
        p = os.path.join(os.path.abspath(folder), name + '.png')
        sc.render.filepath = p
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        out[name] = p
        log(f'[desert] rendered {name} in {time.time() - t1:.1f} s')
    return out
