"""eidoblend.sets.same_seed.kitchen.look: the kitchen at noon, its materials, its CC0 pieces and its light (Blender).

    from eidoblend.sets.same_seed.kitchen import look
    res = look.apply(room_collection, bake_dir, library, prints_dir, sun=14.0, sun_el=30.0, sun_az=-22.0, sky=22.0,
                     fill=25.0, garden=4.0, garden_rot=-18.0, ambient=0.3)
    look.finish(room_collection, scene, res)      # the volume probe baked over the finished room

What it does, in order:
1. EVERY SURFACE FROM A CC0 PHOTOGRAPHIC SET at its real size (the S table): flat parts get a UV in metres from their own
   faces ('box_m') and the set's normal map; turned and swept parts take the set through an object-space box projection
   with its height as a bump. Each material is ONE stack in the order of what happened to it: the coating -> grime where
   dirt collects (the baked AO and cavity on the lows) -> wear where hands, boots and knocks go (the baked curvature x
   where they go: the hands field round every cupboard knob) -> dust on what faces up -> stains with their causes ->
   markings at real size, unmirrored (the prints). The family keeps it clean: every layer is held at that condition.
2. CC0 MODELS FROM POLY HAVEN: a wooden bowl with apples, pears and bananas on the worktop, a cutting board leaning at
   the back of it.
3. THE NOON LIGHT: a strong warm sun through the window (`sun` W/m2, `sun_el` up, `sun_az` round from the window's
   axis; its shadow cast by the sashes, the shades and the basil), the garden outside (Poly Haven's suburban_garden on a
   dome seen only by the lens, through the glass: `garden`, turned `garden_rot`), the sky's light coming in at the glass
   (an area light in each half of the window, `sky` W), the sunlit floor's light given back (`fill` W), a warm world at
   `ambient`, and a volume probe baked over the room with a sphere probe for its reflections.
The room's render settings (RENDER in its package) are its own: 96 samples, exposure 0.3, Fast GI to 1.5 m. Everything
the room needs is in collection kitchen_room (its parts, its lights, its probes, the garden dome); the front wall stays,
hidden from the camera only.
"""
import math
import os
import time

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from ....props.houseplants import look as plants_look
from .. import look as L
from ..look import assign, box_uv, planar_uv

OB = ROOM = BAKE = PRINTS = LIB = HANDS = None


class Mat(L.Mat):
    """the kitchen's material: mapping(vec, size) lays a set `size` metres a tile"""
    ROUGH_MIN = 0.03

    def mapping(self, vec, size=1.0, rot=(0.0, 0.0, 0.0), loc=(0.0, 0.0, 0.0)):
        s = 1.0 / size
        return super().mapping(vec, (s, s, s), rot, loc)

    def vadd(self, a, b):
        n = self.N.new('ShaderNodeVectorMath')
        n.operation = 'ADD'
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        return n.outputs[0]


def log(*a):
    L.log('kitchen look', *a)


def objs(*prefixes, exact=()):
    return [o for o in ROOM.objects if o.type == 'MESH' and (o.name in exact or any(o.name.startswith(p) for p in prefixes))]


def hands_mask(path, sigma=70.0):
    """WHERE HANDS GO on the cupboards: every knob's centre (the built knobs' own loose parts), a soft field round each
    (a hand takes a knob and the door's edge within a hand's breadth of it), drawn over the back wall's plane: x -3..3 m,
    z 0..2.5 m at 5 mm a pixel"""
    import numpy as np
    kn = OB['cupboard_knobs']
    bm = bmesh.new()
    bm.from_mesh(kn.data)
    bm.verts.ensure_lookup_table()
    seen, centres = [False] * len(bm.verts), []
    for v0 in bm.verts:
        if seen[v0.index]:
            continue
        stack, pts = [v0], []
        seen[v0.index] = True
        while stack:
            v = stack.pop()
            pts.append(v.co.copy())
            for e in v.link_edges:
                w_ = e.other_vert(v)
                if not seen[w_.index]:
                    seen[w_.index] = True
                    stack.append(w_)
        centres.append(sum(pts, Vector()) / len(pts))
    bm.free()
    W_, H_ = 1200, 500
    xs, zs = (np.arange(W_) + 0.5) * 5.0 - 3000.0, (np.arange(H_) + 0.5) * 5.0
    X_, Z_ = np.meshgrid(xs, zs)
    m = np.zeros((H_, W_), np.float32)
    for c in centres:
        m = np.maximum(m, np.exp(-((X_ - c.x * 1000.0) ** 2 + (Z_ - c.z * 1000.0) ** 2) / (2.0 * sigma * sigma)))
    img = bpy.data.images.new('hands_mask', W_, H_, alpha=False)
    rgba = np.ones((H_, W_, 4), np.float32)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = m
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw, img.file_format = path, 'PNG'
    img.save()
    bpy.data.images.remove(img)
    log(f'hands mask: {len(centres)} knobs -> {path}')
    return path


def garden_view(hdr, path):
    """the garden as a photograph (the photographs held on the fridge by magnets): the HDRI's equirectangular picture,
    its linear values clipped to 1 and stored as they are (dark, a deep blue sky: as a snapshot of a bright garden)"""
    import numpy as np
    if os.path.isfile(path):
        return path
    src = bpy.data.images.load(hdr, check_existing=True)
    W0, H0 = src.size
    a = np.empty(W0 * H0 * 4, np.float32)
    src.pixels.foreach_get(a)
    a = np.clip(a.reshape(H0, W0, 4), 0.0, 1.0)
    a[..., 3] = 1.0
    img = bpy.data.images.new('garden_view', W0, H0, alpha=False)
    img.pixels.foreach_set(a.ravel())
    img.filepath_raw, img.file_format = path, 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


# ------------------------------------------------------------------------------------- the sets (real sizes)
# floor_tiles_08 five 305 mm tiles across; coated_pine's knots 25-40 mm; gingham's half-inch checks; fingerprints 15-20
# mm; PaintedPlaster017 a 2 x 1 m wall; Granite005A's grains 1-2 mm (as a laminate's printed speckle); Paint004 a 1 m
# painted board
S = {'plaster': ('PaintedPlaster017_2k', 2.0), 'tile': ('floor_tiles_08_2k', 1.525), 'pine': ('coated_pine_2k', 0.7), 'paint': ('Paint004_2k', 1.0),
     'speckle': ('Granite005A_2k', 0.5), 'steel': ('Metal009_2k', 0.6), 'prints': ('Fingerprints002_2k', 0.2), 'smudge': ('Fingerprints008_2k', 0.3),
     'rubber': ('Rubber004_2k', 0.4), 'plastic': ('Plastic013A_2k', 0.5), 'gingham': ('gingham_check_2k', 0.2), 'weave': ('Fabric062_2k', 0.12),
     'paper': ('Paper001_2k', 0.35), 'webbing': ('Fabric039_1k', 0.15)}
GARDEN_HDRI = ('suburban_garden', '4k')                         # the garden outside the window (Poly Haven, CC0)
VIEW_HDRI = ('suburban_garden', '1k')                           # the same garden in the photographs held on the fridge


def sfile(k, key):
    return LIB.tex(S[k][0], key)


def photo(M, k, vec_m, keys=('diff', 'rough', 'displacement'), box=False):
    """a set's maps at its real size through a vector in metres"""
    v = M.mapping(vec_m, S[k][1])
    return {key: M.tex(sfile(k, key), v, color=(key == 'diff'), box=box) for key in keys}


# ------------------------------------------------------------------------------------------------- the materials
def m_wall():
    """painted plaster, warm cream (eggshell): scuffs low by the floor (shoes, the mop), finger marks round the light
    switch and the door's latch side, a faint cooking film on the wall behind the cooker"""
    M = Mat('kitchen_wall_paint')
    p = photo(M, 'plaster', M.uv('box_m'), ('diff', 'rough', 'normal'))
    M.nmap(p['normal'].outputs[0], 'box_m', 0.3)
    # (the photograph's own mottle would read as dirt on a kept wall: the paint's colour, the photograph's light and
    #  shade held to a few percent)
    col = M.value(M.rgb((0.74, 0.66, 0.48)), M.lin(M.lum(p['diff'].outputs[0]), 0.45, 0.65, 0.95, 1.04))
    rough = M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.62, 0.82)
    X, Y, Z = M.pos_mm()
    n_ = M.noise(M.obj(), 9.0, 3.0)
    low = M.mul(M.inv(M.sm(Z, 40.0, 260.0)), M.sm(n_, 0.35, 0.75))              # scuffs at the foot of the walls
    sw = M.mul(M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(Y, 97.0), 2.0), M.m('POWER', M.sub(Z, 1220.0), 2.0))), 50.0, 190.0)), M.sm(X, 2900.0, 2990.0))
    fp = photo(M, 'prints', M.uv('box_m'), ('diff',))['diff']
    sw = M.mul(sw, M.sm(M.lum(fp.outputs[0]), 0.15, 0.6))
    cook = M.mul(M.mul(M.sm(X, -1650.0, -1500.0), M.inv(M.sm(X, -820.0, -680.0))), M.mul(M.sm(Z, 1000.0, 1120.0), M.inv(M.sm(Z, 1560.0, 1680.0))))
    cook = M.mul(M.mul(cook, M.sm(Y, 2985.0, 2999.0)), M.sm(M.noise(M.obj(), 40.0, 4.0), 0.45, 0.8))
    g = M.m('MAXIMUM', M.mul(low, 0.5), M.mul(sw, 0.45), clamp=True)
    col = M.mixc(g, col, M.rgb((0.30, 0.26, 0.21)))
    col = M.mixc(M.mul(cook, 0.25), col, M.rgb((0.55, 0.42, 0.20)))
    rough = M.sub(rough, M.mul(cook, 0.25))
    return M.done(col, rough)


def m_ceiling():
    M = Mat('kitchen_ceiling_paint')
    p = photo(M, 'plaster', M.uv('box_m'), ('diff', 'rough', 'normal'))
    M.nmap(p['normal'].outputs[0], 'box_m', 0.5)
    return M.done(M.tint(p['diff'].outputs[0], (0.95, 0.94, 0.90), desat=0.8, gain=1.25), M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.8, 0.92))


def m_floor():
    """12-inch ceramic tiles in their grout (floor_tiles_08), sealed: a little sheen; worn matte where feet go (in front
    of the sink and the cooker, round the table), grit in the grout"""
    M = Mat('kitchen_floor_tile')
    p = photo(M, 'tile', M.uv('box_m'), ('diff', 'rough', 'normal', 'ao'))
    M.nmap(p['normal'].outputs[0], 'box_m', 1.0)
    col = M.tint(p['diff'].outputs[0], (1.0, 0.97, 0.92), desat=0.15, gain=1.12)
    col = M.mixc(M.mul(M.inv(p['ao'].outputs[0]), 0.6), col, M.rgb((0.10, 0.085, 0.07)))    # grit in the grout
    X, Y, Z = M.pos_mm()
    path = M.m('MAXIMUM', M.mul(M.sm(Y, 1500.0, 2300.0), M.inv(M.sm(Y, 2380.0, 2400.0))), M.mul(M.inv(M.sm(M.m('ABSOLUTE', M.add(Y, 450.0)), 600.0, 1100.0)), M.inv(M.sm(M.m('ABSOLUTE', M.sub(X, 900.0)), 900.0, 1500.0))))
    rough = M.add(M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.32, 0.62), M.mul(path, M.mul(M.noise(M.obj(), 3.0, 2.0), 0.25)))
    return M.done(col, rough)


def m_paint(name, base=(0.80, 0.79, 0.74), rough0=0.30, baked=False, cooker_film=True):
    """white semi-gloss enamel on wood (the cupboards, the trim): Paint004's brush and orange-peel, the paint's own
    white. On a baked low: grime from its AO and cavity, edge wear from its curvature only at hand height (knobs) and at
    boot height (the bottom rails), to primer then to the pine under it; a cooking film near the cooker."""
    M = Mat(name)
    ov = M.obj()
    p = photo(M, 'paint', ov, ('diff', 'rough', 'displacement'), box=True)
    if baked:
        uvv = M.uv('atlas')
        nb = M.tex(os.path.join(BAKE, 'fronts_normal.png'), uvv)
        M.nmap(nb.outputs[0], 'atlas', 1.0)
    M.bump(p['displacement'].outputs[0], 0.00004)
    l0 = M.lum(p['diff'].outputs[0])
    col = M.value(M.rgb(base), M.lin(l0, 0.55, 0.85, 0.96, 1.03))
    rough = M.add(rough0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.12))
    X, Y, Z = M.pos_mm()
    if baked:
        ao = M.tex(os.path.join(BAKE, 'fronts_ao.png'), uvv).outputs[0]
        cav = M.tex(os.path.join(BAKE, 'fronts_cavity.png'), uvv).outputs[0]
        cv = M.sep(M.tex(os.path.join(BAKE, 'fronts_curv.png'), uvv).outputs[0])
        nz = M.noise(ov, 60.0, 3.0)
        grime = M.mul(M.add(M.mul(M.inv(cav), 1.4), M.mul(M.inv(ao), 0.5)), M.lin(nz, 0.3, 0.7, 0.6, 1.2), clamp=True)
        col = M.mixc(M.mul(M.sm(grime, 0.08, 0.6), 0.35), col, M.rgb((0.36, 0.31, 0.25)))
        rough = M.add(rough, M.mul(grime, 0.15))
        convex = M.sm(M.mx(M.sub(cv[0], 0.5), M.mul(M.sub(cv[1], 0.5), 0.8)), 0.02, 0.22)
        hm = M.tex(HANDS, M.comb(M.lin(X, -3000.0, 3000.0), M.lin(Z, 0.0, 2500.0), 0.0))
        hm.extension = 'CLIP'
        hands = M.sep(hm.outputs[0])[0]
        boots = M.mul(M.inv(M.sm(Z, 160.0, 300.0)), M.mul(M.inv(M.sm(Z, 600.0, 900.0)), 0.6))
        nw = M.noise(ov, 140.0, 4.0)
        wear = M.mul(M.mul(convex, M.mx(hands, boots)), M.lin(nw, 0.35, 0.75, 0.0, 1.6), clamp=True)
        primer = M.sm(wear, 0.5, 0.6)
        wood = M.sm(wear, 0.85, 0.95)
        col = M.mixc(primer, col, M.rgb((0.62, 0.61, 0.57)))
        col = M.mixc(wood, col, M.rgb((0.55, 0.42, 0.28)))
        rough = M.mixf(primer, rough, 0.5)
        fp = photo(M, 'prints', ov, ('diff',), box=True)['diff']        # finger marks round the knobs, on the faces too
        fing = M.mul(M.sm(hands, 0.2, 0.7), M.sm(M.lum(fp.outputs[0]), 0.15, 0.5))
        rough = M.add(rough, M.mul(fing, 0.18))
        col = M.value(col, M.sub(1.0, M.mul(fing, 0.04)))
    if cooker_film:
        near = M.mul(M.mul(M.sm(X, -2000.0, -1500.0), M.inv(M.sm(X, -800.0, -300.0))), M.sm(Z, 800.0, 1500.0))
        film = M.mul(near, M.sm(M.lum(photo(M, 'smudge', ov, ('diff',), box=True)['diff'].outputs[0]), 0.1, 0.5))
        col = M.mixc(M.mul(film, 0.04), col, M.rgb((0.66, 0.54, 0.30)))   # (more speckles like dirt: a kept kitchen)
        rough = M.add(rough, M.mul(film, 0.1))
    return M.done(col, rough)


def m_worktop():
    """post-formed laminate, beige speckle: Granite005A's grains as the print, pale and fine; melamine satin; worn matte
    in front of the sink where dishes and hands slide, water spots by the sink, wiped smears"""
    M = Mat('kitchen_worktop_laminate')
    ov = M.obj()
    p = photo(M, 'speckle', ov, ('diff', 'rough'), box=True)
    col = M.tint(p['diff'].outputs[0], (1.12, 1.0, 0.80), desat=0.55, gain=1.0)
    col = M.mixc(0.45, col, M.rgb((0.60, 0.53, 0.42)))
    X, Y, Z = M.pos_mm()
    slide = M.mul(M.mul(M.sm(X, 300.0, 520.0), M.inv(M.sm(X, 1300.0, 1520.0))), M.mul(M.inv(M.sm(Y, 2420.0, 2500.0)), M.sm(Z, 905.0, 912.0)))
    sm = photo(M, 'smudge', ov, ('diff',), box=True)['diff']
    spots = M.mul(M.mul(M.sm(M.lum(sm.outputs[0]), 0.35, 0.55), M.mx(slide, M.mul(M.mul(M.sm(X, 400.0, 600.0), M.inv(M.sm(X, 1700.0, 1900.0))), 0.5))), M.sm(Z, 905.0, 912.0))
    rough = M.add(M.add(0.26, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.1)), M.add(M.mul(slide, 0.18), M.mul(spots, 0.2)))
    col = M.value(col, M.add(1.0, M.mul(slide, 0.05)))
    return M.done(col, rough)


def m_steel(name='kitchen_stainless', base=(0.62, 0.62, 0.60), r0=0.22, brushed=True, scale=1.0):
    """brushed stainless (Metal009): the brushing along the sink's length; water spots dried on it; the bowls' floors
    duller, scratched by pans"""
    M = Mat(name)
    ov = M.obj()
    p = photo(M, 'steel', ov, ('diff', 'rough'), box=True)
    sm = photo(M, 'smudge', ov, ('diff',), box=True)['diff']
    X, Y, Z = M.pos_mm()
    floor_ = M.inv(M.sm(Z, 735.0, 760.0))
    col = M.value(M.rgb(base), M.lin(M.lum(p['diff'].outputs[0]), 0.3, 0.7, 0.9, 1.06))
    rough = M.add(M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.25)), M.add(M.mul(M.sm(M.lum(sm.outputs[0]), 0.25, 0.6), 0.18), M.mul(floor_, 0.12)))
    return M.done(col, rough, 1.0)


def m_chrome(name, base=(0.82, 0.82, 0.84), r0=0.06, scale_k=1.0, scale_at=None):
    """polished chrome: fingerprints where it is handled; limescale where water stands at its foot (scale_at: z mm)"""
    M = Mat(name)
    ov = M.obj()
    fp = photo(M, 'prints', ov, ('diff',), box=True)['diff']
    f = M.sm(M.lum(fp.outputs[0]), 0.12, 0.5)
    col = M.rgb(base)
    rough = M.add(r0, M.mul(f, 0.16))
    metal = 1.0
    if scale_at is not None:
        X, Y, Z = M.pos_mm()
        lime = M.mul(M.inv(M.sm(Z, scale_at, scale_at + 9.0)), M.sm(M.noise(ov, 220.0, 3.0), 0.35, 0.6))
        col = M.mixc(lime, col, M.rgb((0.72, 0.71, 0.66)))
        rough = M.mixf(lime, rough, 0.6)
        metal = M.inv(lime)
    return M.done(col, rough, metal)


def m_enamel(name, base=(0.80, 0.80, 0.78), r0=0.16, baked=None, handle_x=None, hand_z=()):
    """baked or gloss enamel on sheet steel (the refrigerator, the cooker, the dishwasher, the hood): orange-peel from
    Paint004; on a baked low, dirt in its seams from its cavity and AO; fingerprints and a duller sheen where hands open
    it (handle_x: the handle's line, mm; hand_z: [(z0, z1)] the grips)"""
    M = Mat(name)
    ov = M.obj()
    p = photo(M, 'paint', ov, ('displacement', 'rough'), box=True)
    if baked:
        uvv = M.uv('atlas')
        M.nmap(M.tex(os.path.join(BAKE, f'{baked}_normal.png'), uvv).outputs[0], 'atlas', 1.0)
    M.bump(p['displacement'].outputs[0], 0.00002)
    col = M.rgb(base)
    rough = M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.06))
    X, Y, Z = M.pos_mm()
    if baked:
        cav = M.tex(os.path.join(BAKE, f'{baked}_cavity.png'), uvv).outputs[0]
        ao = M.tex(os.path.join(BAKE, f'{baked}_ao.png'), uvv).outputs[0]
        grime = M.mul(M.add(M.mul(M.inv(cav), 1.2), M.mul(M.inv(ao), 0.4)), M.lin(M.noise(ov, 50.0, 3.0), 0.3, 0.7, 0.6, 1.2), clamp=True)
        col = M.mixc(M.mul(M.sm(grime, 0.06, 0.5), 0.3), col, M.rgb((0.34, 0.31, 0.27)))
        rough = M.add(rough, M.mul(grime, 0.1))
        low = M.mul(M.inv(M.sm(Z, 60.0, 220.0)), M.sm(M.noise(ov, 12.0, 3.0), 0.4, 0.7))   # the mop's line
        col = M.mixc(M.mul(low, 0.25), col, M.rgb((0.42, 0.40, 0.36)))
    if handle_x is not None:
        zone = 0.0
        for z0, z1 in hand_z:
            zone = M.mx(zone, M.mul(M.sm(Z, z0, z0 + 60.0), M.inv(M.sm(Z, z1 - 60.0, z1))))
        zone = M.mul(zone, M.inv(M.sm(M.m('ABSOLUTE', M.sub(X, handle_x + 60.0)), 80.0, 260.0)))
        fp = photo(M, 'prints', ov, ('diff',), box=True)['diff']
        f = M.mul(zone, M.sm(M.lum(fp.outputs[0]), 0.12, 0.45))
        rough = M.add(rough, M.mul(f, 0.35))
        col = M.value(col, M.sub(1.0, M.mul(f, 0.05)))
    return M.done(col, rough)


def m_plastic(name, base, r0=0.32, set_k='plastic', bump_m=0.00003, sss=0.0):
    M = Mat(name)
    ov = M.obj()
    p = photo(M, set_k, ov, ('rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], bump_m)
    rough = M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.15))
    extra = {'Subsurface Weight': sss, 'Subsurface Radius': (0.02, 0.02, 0.02)} if sss else None
    return M.done(M.rgb(base), rough, 0.0, extra)


def m_rubber(name='kitchen_rubber', base=(0.025, 0.025, 0.025)):
    M = Mat(name)
    p = photo(M, 'rubber', M.obj(), ('diff', 'rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.0002)
    return M.done(M.value(M.rgb(base), M.lin(M.lum(p['diff'].outputs[0]), 0.0, 0.3, 0.8, 1.3)), M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.6, 0.9))


def m_glass(name, tint=(1.0, 1.0, 1.0), rough=0.01, thin=True, smudge=0.0):
    """clear glass: thin panes as a film (a Fresnel mirror over a straight-through pass, no bending: the
    garden behind it is not displaced), thick glass (the tumbler) with ray-traced refraction"""
    M = Mat(name)
    m = M.mat
    if thin:
        for n in list(M.N):
            if n.type != 'OUTPUT_MATERIAL':
                M.N.remove(n)
        tr = M.N.new('ShaderNodeBsdfTransparent')
        tr.inputs['Color'].default_value = (*tint, 1.0)
        gl = M.N.new('ShaderNodeBsdfGlossy')
        gl.inputs['Roughness'].default_value = rough
        lw = M.N.new('ShaderNodeLayerWeight')
        lw.inputs['Blend'].default_value = 0.08
        f = M.add(M.mul(lw.outputs['Fresnel'], 0.85), 0.04)
        if smudge:
            sm = photo(M, 'smudge', M.obj(), ('diff',), box=True)['diff']
            M.L.new(M.add(rough, M.mul(M.sm(M.lum(sm.outputs[0]), 0.2, 0.6), smudge)), gl.inputs['Roughness'])
        mx = M.N.new('ShaderNodeMixShader')
        M.L.new(f, mx.inputs[0])
        M.L.new(tr.outputs[0], mx.inputs[1])
        M.L.new(gl.outputs[0], mx.inputs[2])
        M.L.new(mx.outputs[0], M.out.inputs[0])
        m.surface_render_method = 'DITHERED'
        try:
            m.use_transparent_shadow = True                    # (its shadow is what its transparency lets through)
        except Exception:  # noqa: BLE001
            pass
        return m
    M.done(M.rgb(tint), rough, 0.0, {'Transmission Weight': 1.0, 'IOR': 1.5})
    for k, v in (('surface_render_method', 'DITHERED'), ('use_raytrace_refraction', True), ('thickness_mode', 'SPHERE')):
        try:
            setattr(m, k, v)
        except Exception:  # noqa: BLE001
            pass
    return m


def m_table(part):
    """coated pine (Poly Haven coated_pine), honey under a satin varnish, on the table's baked low: each board its own
    piece of the photograph, the grain along each member (boards and aprons along their length, breadboard
    ends across, legs up); grime in the joints and round the pegs (cavity); the varnish rubbed matte along the front
    edge where arms lie; worn through to pale wood on the arrises (curvature) at the corners and the front edge;
    scuffs on the feet (boots); an old water ring by the glass; a felt-tip line by the homework"""
    M = Mat(f'kitchen_table_{part}')
    uvv = M.uv('atlas')
    M.nmap(M.tex(os.path.join(BAKE, 'table_normal.png'), uvv).outputs[0], 'atlas', 1.0)
    X, Y, Z = M.pos_mm()
    if part == 'top':
        bi = M.add(M.add(M.m('GREATER_THAN', Y, -732.0), M.m('GREATER_THAN', Y, -540.0)), M.add(M.m('GREATER_THAN', Y, -364.0), M.m('GREATER_THAN', Y, -164.0)))
        bb = M.m('MAXIMUM', M.m('LESS_THAN', X, 222.0), M.m('GREATER_THAN', X, 1578.0))
        off = M.add(M.mul(bi, 0.31), M.mul(bb, 0.53))
        along = M.mixf(bb, X, Y)
        across = M.add(M.mixf(bb, Y, X), M.mul(off, 700.0))
        vec = M.comb(M.mul(along, 0.001), M.mul(across, 0.001), 0.0)
        var = M.add(M.mul(M.m('FRACT', M.mul(bi, 0.618)), 0.12), M.mul(bb, -0.05))
    elif part == 'leg':
        th = M.m('ARCTAN2', M.sub(Y, -450.0), M.sub(X, 900.0))
        vec = M.comb(M.mul(Z, 0.001), M.mul(th, 0.05), 0.0)
        var = 0.02
    else:
        long_ = 1.0 if part == 'apron_long' else 0.0
        vec = M.comb(M.mul(X if long_ else Y, 0.001), M.mul(Z, 0.001), 0.3 * long_)
        var = -0.03
    p = photo(M, 'pine', vec, ('diff', 'rough', 'displacement'))
    M.bump(p['displacement'].outputs[0], 0.00012)
    col = M.tint(p['diff'].outputs[0], (1.06, 0.96, 0.80), desat=0.1, gain=1.3)    # (the photograph's deep orange reads near black at the table: honey)
    col = M.value(col, M.add(1.0, var))
    rough = M.add(0.42, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.2))   # (a farmhouse top's oil-and-wax satin, not a lacquer)
    ao = M.tex(os.path.join(BAKE, 'table_ao.png'), uvv).outputs[0]
    cav = M.tex(os.path.join(BAKE, 'table_cavity.png'), uvv).outputs[0]
    cv = M.sep(M.tex(os.path.join(BAKE, 'table_curv.png'), uvv).outputs[0])
    ov = M.obj()
    grime = M.mul(M.add(M.mul(M.inv(cav), 1.6), M.mul(M.inv(ao), 0.35)), M.lin(M.noise(ov, 70.0, 3.0), 0.3, 0.7, 0.7, 1.2), clamp=True)
    col = M.mixc(M.mul(M.sm(grime, 0.05, 0.5), 0.5), col, M.rgb((0.11, 0.07, 0.035)))
    rough = M.add(rough, M.mul(grime, 0.12))
    convex = M.sm(M.mx(M.sub(cv[0], 0.5), M.mul(M.sub(cv[1], 0.5), 0.8)), 0.02, 0.2)
    nw = M.noise(ov, 90.0, 4.0)
    if part == 'top':
        front = M.inv(M.sm(M.add(Y, 900.0), 0.0, 140.0))
        rub = M.mul(M.mx(front, M.mul(M.inv(M.sm(Y, -40.0, 0.0)), 0.6)), M.mul(M.sm(Z, 735.0, 739.0), M.lin(M.noise(ov, 6.0, 2.0), 0.3, 0.7, 0.3, 1.0)), clamp=True)
        rough = M.add(rough, M.mul(rub, 0.2))
        corners = M.mx(M.inv(M.sm(M.m('ABSOLUTE', M.sub(X, 900.0)), 600.0, 750.0)), front)
        wear = M.mul(M.mul(convex, M.add(0.35, corners)), M.lin(nw, 0.35, 0.75, 0.0, 1.6), clamp=True)
        ring = M.mul(M.inv(M.sm(M.m('ABSOLUTE', M.sub(M.m('SQRT', M.add(M.m('POWER', M.sub(X, 1338.0), 2.0), M.m('POWER', M.sub(Y, -262.0), 2.0))), 37.0)), 0.6, 2.2)), M.sm(Z, 738.0, 739.5))
        ring = M.mul(ring, M.lin(M.noise(ov, 120.0, 2.0), 0.3, 0.7, 0.2, 1.0), clamp=True)
        col = M.mixc(M.mul(ring, 0.22), col, M.rgb((0.62, 0.58, 0.50)))
        pen = M.mul(M.mul(M.inv(M.sm(M.m('ABSOLUTE', M.sub(Y, M.add(-610.0, M.mul(M.sub(X, 470.0), 0.21)))), 0.35, 0.9)), M.mul(M.sm(X, 455.0, 460.0), M.inv(M.sm(X, 520.0, 526.0)))), M.sm(Z, 738.0, 739.5))
        col = M.mixc(M.mul(pen, 0.7), col, M.rgb((0.05, 0.10, 0.35)))
        pegs = M.mn(M.m('ABSOLUTE', M.sub(X, 198.0)), M.m('ABSOLUTE', M.sub(X, 1602.0)))
        pegy = M.mn(M.mn(M.m('ABSOLUTE', M.add(Y, 780.0)), M.m('ABSOLUTE', M.add(Y, 450.0))), M.m('ABSOLUTE', M.add(Y, 120.0)))
        peg = M.mul(M.inv(M.sm(M.m('SQRT', M.add(M.mul(pegs, pegs), M.mul(pegy, pegy))), 4.0, 4.8)), M.sm(Z, 738.0, 739.0))
        col = M.mixc(M.mul(peg, 0.85), col, M.rgb((0.16, 0.08, 0.03)))
    elif part == 'leg':
        boots = M.inv(M.sm(Z, 40.0, 150.0))
        wear = M.mul(M.mul(convex, M.add(0.3, boots)), M.lin(nw, 0.35, 0.75, 0.0, 1.6), clamp=True)
        scuff = M.mul(boots, M.sm(M.noise(ov, 160.0, 3.0), 0.6, 0.72))
        col = M.mixc(M.mul(scuff, 0.5), col, M.rgb((0.10, 0.07, 0.05)))
    else:
        wear = M.mul(M.mul(convex, 0.4), M.lin(nw, 0.35, 0.75, 0.0, 1.6), clamp=True)
    bare = M.sm(wear, 0.45, 0.6)
    col = M.mixc(M.mul(bare, 0.6), col, M.value(M.tint(p['diff'].outputs[0], (1.0, 0.95, 0.85), desat=0.35, gain=1.0), 1.5))
    rough = M.mixf(bare, rough, 0.62)
    return M.done(col, rough)


def m_chair(part):
    """Windsor green milk paint over maple (the type's own finish), worn to the wood where hands take the crest and the
    posts, where the sitter's legs rub the seat's front, where boots rest on the stretchers"""
    M = Mat(f'kitchen_chair_{part}')
    ov = M.obj()
    w = photo(M, 'pine', ov, ('diff', 'displacement'), box=True)
    pp = photo(M, 'paint', ov, ('rough', 'displacement'), box=True)
    M.bump(M.add(M.mul(w['displacement'].outputs[0], 0.4), M.mul(pp['displacement'].outputs[0], 0.6)), 0.0001)
    paint = M.value(M.rgb((0.045, 0.085, 0.05)), M.lin(M.lum(w['diff'].outputs[0]), 0.1, 0.5, 0.9, 1.1))
    nx, ny, nz = M.world_nrm()
    nw = M.noise(ov, 70.0, 4.0)
    k = {'crest': (0.7, M.sm(nz, 0.2, 0.7)), 'posts': (0.35, 1.0), 'seat': (0.45, M.inv(M.sm(M.m('ABSOLUTE', nz), 0.4, 0.8))), 'stretchers': (0.8, M.sm(nz, 0.1, 0.6)),
         'legs': (0.25, 1.0), 'spindles': (0.15, 1.0)}[part]
    wear = M.mul(M.mul(k[0], k[1]), M.lin(nw, 0.3, 0.75, 0.0, 1.4), clamp=True)
    bare = M.sm(wear, 0.55, 0.68)
    col = M.mixc(bare, paint, M.tint(w['diff'].outputs[0], (1.0, 0.93, 0.8), desat=0.25, gain=1.1))
    rough = M.mixf(bare, M.add(0.42, M.mul(M.sub(pp['rough'].outputs[0], 0.5), 0.2)), 0.5)
    return M.done(col, rough)


def m_fabric(name, k, tint=(1, 1, 1), desat=0.0, gain=1.0, hue=None, r=(0.75, 0.95), bump_m=0.0004, sheen=0.3, translucent=0.0):
    M = Mat(name)
    p = photo(M, k, M.obj(), ('diff', 'rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], bump_m)
    col = p['diff'].outputs[0]
    if hue is not None:
        h = M.N.new('ShaderNodeHueSaturation')
        M.L.new(col, h.inputs['Color'])
        h.inputs['Hue'].default_value = hue
        col = h.outputs[0]
    col = M.tint(col, tint, desat=desat, gain=gain)
    m = M.done(col, M.lin(p['rough'].outputs[0], 0.0, 1.0, r[0], r[1]), 0.0, {'Sheen Weight': sheen})
    if translucent:
        tr = M.N.new('ShaderNodeBsdfTranslucent')
        M.L.new(col, tr.inputs['Color'])
        mx = M.N.new('ShaderNodeMixShader')
        mx.inputs[0].default_value = translucent
        M.L.new(M.bsdf.outputs[0], mx.inputs[1])
        M.L.new(tr.outputs[0], mx.inputs[2])
        M.L.new(mx.outputs[0], M.out.inputs[0])
    return m


def m_paper(name, picture=None, uvname='print', tint=(0.93, 0.92, 0.88)):
    """paper (Paper001) and what is printed or written on it (prints/), laid by the sheet's own UV, unmirrored"""
    M = Mat(name)
    p = photo(M, 'paper', M.obj(), ('diff', 'rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.00005)
    col = M.tint(p['diff'].outputs[0], tint, desat=0.7, gain=1.08)
    if picture:
        ink = M.tex(os.path.join(PRINTS, picture), M.uv(uvname), color=True, interp='Cubic')
        ink.extension = 'CLIP'
        c2 = M.mixc(1.0, col, ink.outputs[0])
        c2.node.blend_type = 'MULTIPLY'
        col = c2
    m = M.done(col, M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.75, 0.92))
    tr = M.N.new('ShaderNodeBsdfTranslucent')                  # (paper lets a little of the window through)
    M.L.new(col, tr.inputs['Color'])
    mx = M.N.new('ShaderNodeMixShader')
    mx.inputs[0].default_value = 0.12
    M.L.new(M.bsdf.outputs[0], mx.inputs[1])
    M.L.new(tr.outputs[0], mx.inputs[2])
    M.L.new(mx.outputs[0], M.out.inputs[0])
    return m


def m_simple(name, base, rough, metal=0.0, extra=None, noise_k=0.0):
    M = Mat(name)
    col = M.rgb(base)
    if noise_k:
        col = M.value(col, M.lin(M.noise(M.obj(), 40.0, 3.0), 0.3, 0.7, 1.0 - noise_k, 1.0 + noise_k))
    return M.done(col, rough, metal, extra)


# ------------------------------------------------------------------------------------------------ the assignment
def box_all(objects):
    for o in objects:
        box_uv(o)


def assign_all():
    """every part of the room given its material, by its name (the lows, named '<part>_low', take the baked ones)"""
    t1 = time.time()
    LOWNAMES = {o.name for o in ROOM.objects if o.name.endswith('_low')}
    walls = objs(exact=('wall_back', 'wall_left', 'wall_right', 'wall_front_unseen', 'soffit'))
    box_all(walls)
    W = m_wall()
    for o in walls:
        assign(o, W)
    box_all(objs(exact=('room_ceiling',)))
    assign(OB['room_ceiling'], m_ceiling())
    box_all(objs(exact=('room_floor',)))
    assign(OB['room_floor'], m_floor())
    CAB = m_paint('kitchen_cupboard_paint')
    FRONT = m_paint('kitchen_cupboard_fronts_baked', baked=True)
    TRIM = m_paint('kitchen_trim_paint', base=(0.82, 0.81, 0.77), rough0=0.26, cooker_film=False)
    for o in objs('base_', 'wall_a_', 'wall_b_', 'wall_c_', 'wall_d_', 'wall_over_', 'wall_filler', 'toe_kick'):
        assign(o, FRONT if o.name in LOWNAMES else CAB)
    for o in objs('window_', 'door_', 'base_front', 'base_left', 'base_right'):
        assign(o, TRIM)
    NICKEL = m_chrome('kitchen_cupboard_nickel', base=(0.70, 0.68, 0.64), r0=0.24)   # satin nickel knobs and hinge knuckles
    for o in objs('cupboard_knobs', 'cupboard_hinges'):
        assign(o, NICKEL)
    WT = m_worktop()
    for o in objs('worktop_'):
        assign(o, WT)
    STEEL = m_steel()
    for o in objs('sink'):
        assign(o, STEEL)
    TAP = m_chrome('kitchen_tap_chrome', scale_at=925.0)
    for o in objs('tap_'):
        assign(o, TAP)
    assign(OB['soap_pump_cap'], m_chrome('kitchen_pump_chrome', r0=0.1))
    # the refrigerator: its case and doors are lows with their bakes; handles a warm white plastic; gaskets rubber
    FR = m_enamel('kitchen_fridge_enamel_baked', baked='fridge', handle_x=2224.0, hand_z=((1110.0, 1430.0), (760.0, 1080.0)))
    for o in objs('fridge_case_low', 'fridge_door_'):
        assign(o, FR)
    assign(OB['fridge_hinge_cap'], m_enamel('kitchen_fridge_hinge', base=(0.79, 0.79, 0.77)))
    for n in ('fridge_hinge_middle', 'fridge_hinge_bottom'):
        assign(OB[n], m_chrome('kitchen_fridge_hinge_metal', base=(0.55, 0.55, 0.56), r0=0.25))
    HND = m_plastic('kitchen_fridge_handle', (0.74, 0.72, 0.66), 0.28)
    for o in objs('fridge_handle'):
        assign(o, HND)
    RUB = m_rubber()
    for o in objs('fridge_gasket', 'fridge_feet', 'dishwasher_foot', 'cooker_foot', 'fridge_grille_back'):
        assign(o, RUB)
    assign(OB['fridge_grille_louvres'], m_simple('kitchen_grille_paint', (0.04, 0.04, 0.04), 0.5, noise_k=0.15))
    # what is on the fridge: printed paper by its own planar UV; magnets in four plastics; two photograph magnets
    for nm, pic, cx, cz, w, h, deg in (('fridge_drawing', 'drawing.png', 2575.0, 1410.0, 279.0, 216.0, 2.5), ('fridge_school_letter', 'letter.png', 2620.0, 815.0, 216.0, 279.0, -1.8),
                                       ('fridge_shopping_list', 'list.png', 2372.0, 905.0, 105.0, 190.0, 3.0)):
        planar_uv(OB[nm], 'print', (cx, cz), 'xz', (w, h), deg)
        assign(OB[nm], m_paper(f'kitchen_paper_{nm}', pic))
    mag = OB['fridge_magnets']
    bm = bmesh.new()
    bm.from_mesh(mag.data)
    cols = [(0.6, 0.02, 0.02), (0.02, 0.12, 0.6), (0.7, 0.5, 0.02), (0.03, 0.35, 0.06)]
    ca = mag.data.color_attributes.new('part_col', 'FLOAT_COLOR', 'POINT')
    bm.verts.ensure_lookup_table()
    seen = {}
    for v in bm.verts:
        key = (round(v.co.x * 20), round(v.co.z * 20))
        seen.setdefault(key, len(seen))
    bm.free()
    vals = []
    for v in mag.data.vertices:
        key = (round(v.co.x * 20), round(v.co.z * 20))
        c = cols[seen[key] % 4]
        vals += [*c, 1.0]
    ca.data.foreach_set('color', vals)
    M = Mat('kitchen_magnet_plastic')
    at = M.N.new('ShaderNodeAttribute')
    at.attribute_name = 'part_col'
    assign(mag, M.done(at.outputs['Color'], 0.3))
    pm = OB['fridge_photo_magnets']
    planar_uv(pm, 'print', (2349.0, 1240.0), 'xz', (90.0, 150.0), 0.0)
    M = Mat('kitchen_photo_magnets')
    view = garden_view(LIB.hdri(*VIEW_HDRI), os.path.join(PRINTS, 'garden_view.png'))
    gp = M.tex(view, M.mapping(M.uv('print'), 1.0, loc=(0.1, 0.32, 0.0)), color=True)
    assign(pm, M.done(M.value(gp.outputs[0], 0.8), 0.15))
    # the cooker, the hood, the dishwasher: enamel, chrome, black glass, rubber
    COOK = m_enamel('kitchen_cooker_enamel', base=(0.80, 0.79, 0.76), r0=0.18)
    for o in objs('cooker_body', 'cooker_back_guard', 'cooker_door', 'cooker_drawer', 'hood', 'dishwasher_door', 'dishwasher_console', 'dishwasher_kick', 'dishwasher_body'):
        if o.name in ('cooker_door_handle', 'cooker_door_latch', 'cooker_drawer_handle'):
            continue
        assign(o, COOK)
    M = Mat('kitchen_cooktop_enamel')                              # the top: enamel with old boil-overs round the bowls
    ov = M.obj()
    X, Y, Z = M.pos_mm()
    sp = 0.0
    for bx_, by_, R in ((-1342.0, 2528.0, 100.0), (-1342.0, 2804.0, 76.0), (-974.0, 2804.0, 76.0), (-974.0, 2528.0, 100.0)):
        d = M.m('SQRT', M.add(M.m('POWER', M.sub(X, bx_), 2.0), M.m('POWER', M.sub(Y, by_), 2.0)))
        sp = M.mx(sp, M.inv(M.sm(d, R + 22.0, R + 70.0)))
    sp = M.mul(M.mul(sp, M.sm(M.noise(ov, 60.0, 4.0), 0.5, 0.65)), M.sm(Z, 900.0, 910.0))
    assign(OB['cooker_top'], M.done(M.mixc(M.mul(sp, 0.35), M.rgb((0.80, 0.79, 0.76)), M.rgb((0.35, 0.22, 0.10))), M.add(0.18, M.mul(sp, 0.25))))
    M = Mat('kitchen_drip_bowl_chrome')                            # chrome drip bowls, heat-tinted gold and blue in rings
    X, Y, Z = M.pos_mm()
    ring = M.m('FRACT', M.mul(M.noise(M.obj(), 30.0, 2.0), 3.0))
    col = M.mixc(M.sm(ring, 0.3, 0.7), M.rgb((0.75, 0.62, 0.40)), M.rgb((0.45, 0.50, 0.62)))
    for o in objs('cooker_drip_bowl'):
        assign(o, M.done(col, 0.18, 1.0))
    COIL = m_simple('kitchen_coil_steel', (0.05, 0.05, 0.055), 0.45, 1.0, noise_k=0.25)
    for o in objs('cooker_coil'):
        assign(o, COIL)
    assign(OB['cooker_control_panel'], m_simple('kitchen_black_glass', (0.01, 0.01, 0.012), 0.08, 0.0, {'Coat Weight': 1.0}))
    assign(OB['cooker_knobs_and_clock'], m_plastic('kitchen_knob_black', (0.02, 0.02, 0.02), 0.25))
    CH = m_chrome('kitchen_handle_chrome', r0=0.08)
    for o in objs('cooker_door_handle', 'cooker_drawer_handle', 'cooker_door_latch', 'cooker_clock_frame', 'dishwasher_latch', 'hood_nameplate', 'towel_stand'):
        assign(o, CH)
    # the oven door's window: smoked glass over a dark box, which reads as a black mirror; drawn so, OPAQUE, with the
    # control panel's clear coat (a thin clear glass, 94 % see-through black and DITHERED, is left as grain by EEVEE's
    # few samples)
    assign(OB['cooker_window_glass'], m_simple('kitchen_oven_glass', (0.012, 0.011, 0.010), 0.03, 0.0, {'Coat Weight': 1.0, 'Coat Roughness': 0.02}))
    assign(OB['hood_filter'], m_steel('kitchen_hood_filter', base=(0.5, 0.5, 0.48), r0=0.45))
    assign(OB['hood_lamp_lens'], m_plastic('kitchen_lamp_lens', (0.85, 0.84, 0.80), 0.35, sss=0.3))
    for o in objs('dishwasher_buttons', 'dishwasher_dial'):
        assign(o, m_plastic(f'kitchen_{o.name}_plastic', (0.70, 0.70, 0.68), 0.3))
    # the table (its lows) and what lies on it
    for o in objs('table_'):
        part = 'top' if o.name.startswith('table_top') else ('leg' if o.name.startswith('table_leg') else ('apron_long' if 'long' in o.name else 'apron_short'))
        assign(o, m_table(part))
    for nm, pic, cx, cy, deg in (('homework_sheet', 'worksheet.png', 680.0, -200.0, 184.0), ('homework_sheet_done', 'spelling.png', 640.0, -236.0, 171.0)):
        planar_uv(OB[nm], 'print', (cx, cy), 'xy', (216.0, 279.0), deg)
        assign(OB[nm], m_paper(f'kitchen_paper_{nm}', pic))
    nb = OB['homework_composition_book']
    planar_uv(nb, 'print', (1085.0 + 95.0 * math.cos(math.radians(14.0)) - 123.5 * math.sin(math.radians(14.0)), -590.0 + 95.0 * math.sin(math.radians(14.0)) + 123.5 * math.cos(math.radians(14.0))), 'xy', (190.0, 247.0), 14.0)
    M = Mat('kitchen_composition_book')
    X, Y, Z = M.pos_mm()
    cover = M.tex(os.path.join(PRINTS, 'notebook.png'), M.uv('print'), color=True, interp='Cubic')
    pg = M.sm(Z, 741.6, 742.0)
    pg = M.mul(pg, M.inv(M.sm(Z, 747.8, 748.2)))
    col = M.mixc(pg, cover.outputs[0], M.rgb((0.86, 0.85, 0.80)))
    assign(nb, M.done(col, M.mixf(pg, 0.45, 0.85)))
    for nm, c in (('pencil_school', (0.85, 0.55, 0.03)), ('pencil_red', (0.55, 0.03, 0.02)), ('pencil_blue', (0.03, 0.10, 0.50))):
        o = OB[nm]
        M = Mat(f'kitchen_{nm}')
        X, Y, Z = M.pos_mm()
        tip = {'pencil_school': (870.0, -300.0, 31.0), 'pencil_red': (1010.0, -112.0, -38.0), 'pencil_blue': (960.0, -470.0, 80.0)}[nm]
        ca_, sa_ = math.cos(math.radians(tip[2])), math.sin(math.radians(tip[2]))
        along = M.add(M.mul(M.sub(X, tip[0]), ca_), M.mul(M.sub(Y, tip[1]), sa_))
        wood = M.inv(M.sm(along, 15.5, 17.0))
        lead = M.inv(M.sm(along, 3.2, 3.8))
        col = M.mixc(wood, M.rgb(c), M.rgb((0.62, 0.45, 0.28)))
        col = M.mixc(lead, col, M.rgb(c if nm != 'pencil_school' else (0.04, 0.04, 0.045)))
        assign(o, M.done(col, M.mixf(wood, 0.3, 0.7)))
    assign(OB['pencil_school_ferrule_and_rubber'], m_simple('kitchen_ferrule', (0.75, 0.62, 0.35), 0.3, 1.0))
    assign(OB['homework_rubber'], m_simple('kitchen_eraser', (0.80, 0.42, 0.45), 0.75))
    assign(OB['glass'], m_glass('kitchen_tumbler_glass', thin=False))
    assign(OB['glass_milk'], m_simple('kitchen_milk', (0.88, 0.88, 0.84), 0.2, 0.0, {'Subsurface Weight': 1.0, 'Subsurface Radius': (0.02, 0.02, 0.02)}))
    # the chairs and the child's cushion
    for o in objs('chair_'):
        part = o.name.split('_')[-1]
        if part in ('cushion', 'piping'):
            continue
        assign(o, m_chair(part))
    GING = m_fabric('kitchen_cushion_gingham', 'gingham', hue=0.17, r=(0.8, 0.95), bump_m=0.0005, sheen=0.4)
    for o in objs('chair_child_cushion'):
        assign(o, GING)
    # the window: glass, painted wood, brass, the shades
    PANE = m_glass('kitchen_window_glass', smudge=0.06)
    for o in objs('window_glass'):
        assign(o, PANE)
        o.visible_shadow = False                                   # (the sun and the sky come in through it)
    assign(OB['window_hardware'], m_chrome('kitchen_window_brass', base=(0.78, 0.56, 0.26), r0=0.2))
    SH = m_fabric('kitchen_shade_cloth', 'weave', tint=(0.95, 0.90, 0.80), desat=0.5, gain=1.2, r=(0.85, 0.95), sheen=0.2, translucent=0.35)
    for o in objs('shade_cloth', 'shade_hem'):
        assign(o, SH)
    for o in objs('shade_roll', 'shade_ring', 'shade_cord'):
        assign(o, m_plastic(f'kitchen_{o.name}_plastic', (0.80, 0.79, 0.75), 0.4))
    # the room's door: painted (trim), its knob brass, polished where the hand takes it
    M = Mat('kitchen_door_knob_brass')
    X, Y, Z = M.pos_mm()
    held = M.sm(M.sub(3000.0, X), 30.0, 58.0)
    fp = photo(M, 'prints', M.obj(), ('diff',), box=True)['diff']
    col = M.mixc(M.mul(M.inv(held), 0.6), M.rgb((0.80, 0.58, 0.28)), M.rgb((0.35, 0.26, 0.13)))
    assign(OB['door_knob'], M.done(col, M.add(M.mixf(held, 0.42, 0.14), M.mul(M.sm(M.lum(fp.outputs[0]), 0.1, 0.5), 0.15)), 1.0))
    assign(OB['door_hinges'], m_chrome('kitchen_door_hinge_brass', base=(0.70, 0.52, 0.27), r0=0.3))
    assign(OB['door_backing'], m_simple('kitchen_hall_dark', (0.05, 0.045, 0.04), 0.8))
    # plates, switch, sockets: plastic a little yellowed, fingered round the switch
    PL = m_plastic('kitchen_wallplate_plastic', (0.78, 0.76, 0.69), 0.3)
    for o in objs('socket_plate', 'switch_', 'plate_screws_and_outlets'):
        assign(o, PL)
    # the ceiling lights (off at noon): white pan, frosted bowl, brass finial
    for o in objs('ceiling_light'):
        if o.name.endswith('_pan'):
            assign(o, m_enamel(f'kitchen_{o.name}', base=(0.80, 0.80, 0.78), r0=0.25))
        elif o.name.endswith('_bowl'):
            assign(o, m_plastic(f'kitchen_{o.name}_frost', (0.86, 0.86, 0.84), 0.45, sss=0.5))
        else:
            assign(o, m_chrome(f'kitchen_{o.name}_brass', base=(0.78, 0.56, 0.26), r0=0.22))
    # the clock: a dark case, its face printed (dial.png on the case's face at y 2979), black hands, its glass
    cc = OB['clock_case']
    planar_uv(cc, 'print', (900.0, 2288.0), 'xz', (200.0, 200.0), 0.0)
    M = Mat('kitchen_clock_case')
    X, Y, Z = M.pos_mm()
    face = M.mul(M.inv(M.sm(Y, 2979.3, 2980.5)), M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(X, 900.0), 2.0), M.m('POWER', M.sub(Z, 2288.0), 2.0))), 99.0, 100.0)))
    dial = M.tex(os.path.join(PRINTS, 'dial.png'), M.uv('print'), color=True, interp='Cubic')
    dial.extension = 'CLIP'
    col = M.mixc(face, M.rgb((0.04, 0.04, 0.045)), M.mixc(1.0, M.rgb((0.86, 0.85, 0.80)), dial.outputs[0]))
    col.node.inputs[0].default_value = 1.0
    assign(cc, M.done(col, M.mixf(face, 0.3, 0.6)))
    for o in objs('clock_hand', 'clock_hub'):
        assign(o, m_simple('kitchen_clock_hands', (0.02, 0.02, 0.02), 0.4))
    assign(OB['clock_glass'], m_glass('kitchen_clock_glass'))
    # by the sink: the rack (white coated wire on a white tray), plates, tumblers, soap, sponge, the paper towel
    WIRE = m_plastic('kitchen_rack_wire', (0.82, 0.82, 0.80), 0.32)
    for o in objs('dish_rack', 'dish_tray'):
        assign(o, WIRE)
    for o in objs('dish_plate'):
        assign(o, m_simple('kitchen_plate_glaze', (0.84, 0.84, 0.82), 0.05, 0.0, {'Coat Weight': 0.6}))
    TUMB = m_glass('kitchen_tumbler_rack', thin=False)
    for o in objs('dish_tumbler'):
        assign(o, TUMB)
    assign(OB['soap_bottle'], m_plastic('kitchen_soap_bottle', (0.05, 0.25, 0.08), 0.12, set_k='plastic', sss=0.4))
    M = Mat('kitchen_sponge')
    X, Y, Z = M.pos_mm()
    pz = photo(M, 'rubber', M.obj(), ('displacement',), box=True)['displacement']
    M.bump(pz.outputs[0], 0.0015)
    scour = M.sm(Z, 936.0, 938.0)
    assign(OB['sponge'], M.done(M.mixc(scour, M.rgb((0.85, 0.65, 0.12)), M.rgb((0.05, 0.25, 0.06))), M.mixf(scour, 0.85, 0.95)))
    assign(OB['towel_roll'], m_paper('kitchen_paper_towel', None, tint=(0.96, 0.95, 0.92)))
    # the kettle on the cooker: red enamel, chipped to black iron round its foot; a black bakelite grip on its bail
    M = Mat('kitchen_kettle_enamel')
    X, Y, Z = M.pos_mm()
    chip = M.mul(M.inv(M.sm(Z, 921.0, 926.0)), M.sm(M.noise(M.obj(), 160.0, 3.0), 0.5, 0.56))
    col = M.mixc(chip, M.rgb((0.42, 0.035, 0.025)), M.rgb((0.02, 0.02, 0.02)))
    KET = M.done(col, M.mixf(chip, 0.1, 0.5))
    for o in objs('kettle_body', 'kettle_spout'):
        assign(o, KET)
    assign(OB['kettle_bail'], m_plastic('kitchen_kettle_grip', (0.02, 0.018, 0.016), 0.35))
    # the school bag: red nylon, black webbing, black zips
    assign(OB['school_bag_body'], m_fabric('kitchen_bag_nylon', 'weave', tint=(1.0, 0.18, 0.12), desat=1.0, gain=0.55, r=(0.55, 0.75), bump_m=0.0002, sheen=0.4))
    assign(OB['school_bag_pocket'], OB['school_bag_body'].active_material)
    WEB = m_fabric('kitchen_bag_webbing', 'webbing', tint=(0.25, 0.25, 0.27), desat=1.0, gain=0.8, r=(0.7, 0.9), bump_m=0.0004)
    for o in objs('school_bag_strap', 'school_bag_carry', 'school_bag_base_piping'):
        assign(o, WEB)
    for o in objs('school_bag_zip', 'school_bag_pocket_zip', 'school_bag_pulls'):
        assign(o, m_plastic(f'kitchen_{o.name}_zip', (0.02, 0.02, 0.02), 0.35))
    # the basil: its look from the houseplants (glossy leaves a little translucent, each its own green; a fired-clay pot
    # and saucer; compost)
    plants_look.apply(objs('basil_'), prefix='kitchen')
    leftover = [o.name for o in ROOM.objects if o.type == 'MESH' and (not o.data.materials or o.data.materials[0] is None or o.data.materials[0].name.startswith('clay'))]
    log(f'materials in {time.time() - t1:.1f} s; still clay: {leftover}')
    return leftover


# ------------------------------------------------------------------------------------------------ the CC0 models
def place_gltf(path, at, yaw=0.0, pick=None, name=None):
    """a Poly Haven model (its own materials, its real size) stood at `at` (m): its lowest point on at.z, centred; pick:
    only the meshes whose names start so"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH' and (pick is None or any(o.name.startswith(p) for p in pick))]
    drop = [o for o in new if o not in meshes]
    out = []
    for o in meshes:                                           # (kept: unparented with their transform, into the room)
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        for c in list(o.users_collection):
            c.objects.unlink(o)
        ROOM.objects.link(o)
        o['eido_loaded_asset'] = True
        out.append(o)
    for o in drop:                                             # (the importer's empties and the kit's other parts)
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()
    lo = Vector((min((o.matrix_world @ Vector(b))[i] for o in out for b in o.bound_box) for i in range(3)))
    hi = Vector((max((o.matrix_world @ Vector(b))[i] for o in out for b in o.bound_box) for i in range(3)))
    c = (lo + hi) / 2.0
    R = Matrix.Translation(Vector(at)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Translation(Vector((-c.x, -c.y, -lo.z)))
    for o in out:
        o.matrix_world = R @ o.matrix_world
        if name:
            o.name = name if len(out) == 1 else f'{name}_{o.name}'
    bpy.context.view_layer.update()
    return out, hi - lo


def place_models():
    """the wooden bowl on the worktop by the sink with three apples, two pears and a bunch of bananas in it; the cutting
    board leaning on the upstand beside it"""
    t1 = time.time()
    BOWL = (0.10, 2.70, 0.914)
    bowl, bs = place_gltf(LIB.model('wooden_bowl_01'), BOWL, 0.4, name='cc0_wooden_bowl')
    log('bowl size', tuple(round(v, 3) for v in bs))
    fl = BOWL[2] + 0.018                                           # (the bowl's inside floor, about)
    for i, (dx, dy, yaw) in enumerate(((-0.055, 0.02, 0.3), (0.045, 0.045, 1.9), (0.0, -0.06, 4.0))):
        place_gltf(LIB.model('food_apple_01'), (BOWL[0] + dx, BOWL[1] + dy, fl), yaw, name=f'cc0_apple_{i}')
    for i, (part, dx, dy, yaw) in enumerate((('food_pears_asian_01_a', 0.06, -0.035, 0.6), ('food_pears_asian_01_c', -0.03, 0.075, 2.2))):
        place_gltf(LIB.model('food_pears_asian_01'), (BOWL[0] + dx, BOWL[1] + dy, fl + 0.012), yaw, pick=[part], name=f'cc0_pear_{i}')
    ban, bsz = place_gltf(LIB.model('bananas'), (BOWL[0] - 0.01, BOWL[1] + 0.0, fl + 0.06), 1.1, pick=['bananas_bunch'], name='cc0_bananas')
    for o in ban:
        o.rotation_euler.rotate(Euler((0.0, math.radians(-12.0), 0.0)))
    board, bsz = place_gltf(LIB.model('wooden_cutting_board'), (-0.30, 2.80, 0.914), 0.0, name='cc0_cutting_board')
    # lean it against the upstand: stood on its long edge, its face to the room, tipped back to the wall
    for o in board:
        mw = o.matrix_world.copy()
        piv = Vector((-0.30, 2.80, 0.914))
        o.matrix_world = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(78.0), 4, 'X') @ Matrix.Translation(-piv) @ mw   # (+78: face to -y, top to the wall)
    bpy.context.view_layer.update()
    lo_z = min((o.matrix_world @ Vector(b)).z for o in board for b in o.bound_box)
    hi_y = max((o.matrix_world @ Vector(b)).y for o in board for b in o.bound_box)
    for o in board:
        o.matrix_world = Matrix.Translation(Vector((0.0, 2.985 - hi_y, 0.915 - lo_z))) @ o.matrix_world
    log(f'CC0 models placed in {time.time() - t1:.1f} s')


# ------------------------------------------------------------------------------------------------ the noon light
def lights(sun_w, sun_el, sun_az, sky_w, fill_w, garden_k, garden_rot, ambient):
    """the sun, the sky at the window, the floor's light given back, the garden outside, the world -> (collection
    kitchen_lights, the world)"""
    LIGHTS = bpy.data.collections.get('kitchen_lights') or bpy.data.collections.new('kitchen_lights')
    if LIGHTS.name not in ROOM.children:
        ROOM.children.link(LIGHTS)

    def lamp(name, kind, energy, color, **kw):
        ld = bpy.data.lights.new(name, kind)
        ld.energy, ld.color = energy, color
        for k, v in kw.items():
            setattr(ld, k, v)
        o = bpy.data.objects.new(name, ld)
        LIGHTS.objects.link(o)
        return o

    # a winter noon's sun, 30 degrees up, a little east of the window's axis (higher, its patch falls where no lens
    # looks): it lies on the worktop round the sink and the bowl, on the basil, and on the floor beside the table
    SUN_EL, SUN_AZ = math.radians(sun_el), math.radians(sun_az)
    sun = lamp('kitchen_noon_sun', 'SUN', sun_w, (1.0, 0.90, 0.76), angle=math.radians(0.53))
    d = Vector((math.sin(SUN_AZ) * math.cos(SUN_EL), -math.cos(SUN_AZ) * math.cos(SUN_EL), -math.sin(SUN_EL)))   # the way its light travels
    sun.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    log('sun travels', tuple(round(v, 3) for v in d))
    # (a window's light is the radiance of what is seen through it: far brighter area lights, and the varnished table
    #  mirrors them brighter than the sun's patch)
    for i, x0 in enumerate((0.167, 0.968)):                        # the sky at each half of the window, below the shades
        o = lamp(f'kitchen_window_sky_{i}', 'AREA', sky_w, (0.80, 0.88, 1.0), shape='RECTANGLE', size=0.665, size_y=0.64)
        o.location = (x0 + 0.3325, 3.03, 1.50)
        o.rotation_euler = (math.radians(-90.0), 0.0, 0.0)         # (an area light shines down its -Z: turned to face -y)
        o.data.use_shadow = True
    bounce = lamp('kitchen_floor_bounce', 'AREA', fill_w, (1.0, 0.86, 0.68), shape='RECTANGLE', size=1.8, size_y=0.9)
    bounce.location = (-0.3, 0.35, 0.02)                           # what the sunlit floor gives back, up into the room (under its patch)
    bounce.rotation_euler = (math.radians(180.0), 0.0, 0.0)
    bounce.data.use_shadow = True
    # the garden outside: a curved backdrop seen only by the lens (and so only through the glass), the HDRI laid on it by
    # direction. Only what the window shows: 160 degrees round +y, from 35 below the horizon to 25 above (every lens sees
    # the window from 1.4-1.55 m, under 6 degrees up); a closed dome round the room would take the sun (no patch of sun
    # anywhere), and the sun passes over this.
    bm = bmesh.new()
    RD, NA, NE = 40.0, 48, 16
    grid = [[bm.verts.new((RD * math.cos(math.radians(el)) * math.sin(math.radians(az)), RD * math.cos(math.radians(el)) * math.cos(math.radians(az)), RD * math.sin(math.radians(el))))
             for az in [-80.0 + 160.0 * i / NA for i in range(NA + 1)]] for el in [-35.0 + 60.0 * j / NE for j in range(NE + 1)]]
    for j in range(NE):
        for i in range(NA):
            bm.faces.new((grid[j][i], grid[j + 1][i], grid[j + 1][i + 1], grid[j][i + 1]))   # (wound to face the centre)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    me = bpy.data.meshes.new('kitchen_outside_garden')
    bm.to_mesh(me)
    bm.free()
    dome = bpy.data.objects.new('kitchen_outside_garden', me)
    dome.location = (0.9, 0.5, 1.3)
    ROOM.objects.link(dome)
    M = Mat('kitchen_outside_garden')
    for n in list(M.N):
        if n.type != 'OUTPUT_MATERIAL':
            M.N.remove(n)
    tc = M.N.new('ShaderNodeTexCoord')
    mp = M.N.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(garden_rot))
    M.L.new(tc.outputs['Object'], mp.inputs['Vector'])
    env = M.N.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(LIB.hdri(*GARDEN_HDRI), check_existing=True)
    M.L.new(mp.outputs[0], env.inputs['Vector'])
    em = M.N.new('ShaderNodeEmission')
    M.L.new(env.outputs[0], em.inputs['Color'])
    em.inputs['Strength'].default_value = garden_k
    M.L.new(em.outputs[0], M.out.inputs[0])
    dome.data.materials.append(M.mat)
    dome.visible_shadow = False
    for k in ('hide_probe_volume', 'hide_probe_sphere', 'hide_probe_plane'):
        if hasattr(dome, k):
            setattr(dome, k, True)
    OB['wall_front_unseen'].visible_camera = False                 # (the lens looks in through it; it still bounds the room's light)
    # the world: what the room gives back where no probe has been baked (EEVEE ray traces what it can see)
    w = bpy.data.worlds.new('kitchen_noon_world')
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.92, 0.88, 0.80, 1.0)
    bg.inputs['Strength'].default_value = ambient
    return LIGHTS, w


# ------------------------------------------------------------------------------------------------ the room's look
def apply(room, bake_dir, library, prints_dir, sun=14.0, sun_el=30.0, sun_az=-22.0, sky=22.0, fill=25.0, garden=4.0,
          garden_rot=-18.0, ambient=0.3, probe_res=(4, 4, 4), probe_samples=2048):
    """The kitchen's look on its collection `room` (the lows step's file): every part's material, the CC0 models, the
    lights (collection kitchen_lights) and the world. bake_dir: the lows step's bake (<atlas>_normal/_ao/_cavity/_curv);
    prints_dir: the prints step's pictures (and the hands mask and the garden's photograph, made here); sun W/m2 at
    sun_el degrees up and sun_az round from the window's axis; sky: W at each half of the window; fill: W of the
    floor's light given back; garden: the garden's strength, turned garden_rot degrees; ambient: the world's strength.
    probe_res / probe_samples: the volume probe finish() bakes (as the film's: Blender's own 4 x 4 x 4 and 2048).
    -> {'materials', 'world', 'lights', 'still_clay', 'probe_res', 'probe_samples'}"""
    global OB, ROOM, BAKE, PRINTS, LIB, HANDS
    OB, ROOM, BAKE, PRINTS, LIB = bpy.data.objects, room, bake_dir, prints_dir, library
    before = set(bpy.data.materials)
    HANDS = hands_mask(os.path.join(PRINTS, 'hands_mask.png'))
    clay = assign_all()
    place_models()
    lc, w = lights(sun, sun_el, sun_az, sky, fill, garden, garden_rot, ambient)
    mats = sorted(m.name for m in bpy.data.materials if m not in before)
    return {'materials': mats, 'world': w, 'lights': lc, 'still_clay': clay, 'probe_res': tuple(int(v) for v in probe_res),
            'probe_samples': int(probe_samples)}


def finish(room, sc, res):
    """the probes, over the finished room with its render settings: a volume probe over the room (what it gives back),
    baked now (its bake is saved with the file), and a sphere probe for its reflections"""
    lc = res['lights']
    vp = bpy.data.objects.new('kitchen_gi_volume', bpy.data.lightprobes.new('kitchen_gi_volume', 'VOLUME'))
    vp.location, vp.scale = (0.0, 0.5, 1.37), (3.0, 2.5, 1.37)
    vp.data.resolution_x, vp.data.resolution_y, vp.data.resolution_z = res['probe_res']
    vp.data.bake_samples = res['probe_samples']
    lc.objects.link(vp)
    spp = bpy.data.objects.new('kitchen_reflection', bpy.data.lightprobes.new('kitchen_reflection', 'SPHERE'))
    spp.location = (0.6, 0.6, 1.3)
    spp.data.influence_distance = 4.5
    lc.objects.link(spp)
    L.bake_volume_probe(vp, 'kitchen look')
