"""eidoblend.sets.same_seed.lab.look: the lab's materials, its CC0 pieces, its light and its probes (Blender).

    from eidoblend.sets.same_seed.lab import look
    res = look.apply(room_collection, bake_dir, library, prints_dir, world=4.5, sun=30.0, panel=8.0, sun_el=38.0,
                     sun_az=70.0, screen=1.6, clamp=4.0)
    look.finish(room_collection, scene, res)      # the volume probe baked over the finished room

The brightest and kindest room of the film, a clean, cared-for room in daily use; every layer held to that.
1. EVERY SURFACE FROM A CC0 PHOTOGRAPHIC SET at its real size (the S table): flat parts through a UV in metres from their
   own faces ('box_m') with the set's normal map, turned and swept parts through an object-space box projection with
   the set's height as a bump. ONE STACK per material in the order of what happened to it: the finish -> grime where
   dirt collects (the baked AO and cavity on the lows) -> wear where hands, feet and knocks go (the baked arris
   nearness x where they go) -> dust on what faces up -> stains with their causes (a coffee ring by the mug, the warm
   air's grey over each radiator, the supply air's halo round the diffuser) -> markings at real size, unmirrored (the
   prints: the screen's document, the clipboard's form, the notice; the whiteboard's old marker ghosts).
2. THE HOUSEPLANTS' LOOK (eidoblend.props.houseplants.look).
3. CC0 MODELS FROM POLY HAVEN where the room was missing what its people leave: a wall clock over the whiteboard, a
   pencil cup with a pencil and a pen, a yellow pad.
4. ITS LIGHT: Poly Haven's pretoria_gardens outside (its own sun clamped to `clamp`, turned so its sky stands behind
   the lamp; what lights the room has its ground taken down and is cooled a little, what the lens sees through the
   glass is the sky as it is; strength `world`), a SUN lamp through the windows (`sun` W/m2 at `sun_el` degrees,
   `sun_az` degrees round from +x toward +y), the eight LED panels of the ceiling (`panel` W each, their diffusers
   glowing to match), a volume probe baked over the room for what it all gives back (its box reaches 6 cm past every
   surface of the room), a sphere probe for the reflections. The screen glows at `screen`.
The room's render settings (RENDER in its package): Fast GI as ambient occlusion only at 64 samples (the probe carries
the bounce); the shadow pool at 1024 MB. wall_front_unseen stays, hidden from the camera only.
"""

import math
import os

import bpy
from mathutils import Matrix, Vector

from ....materials.layered import NT
from ....props.houseplants import look as plants_look
from .. import look as L
from ..look import assign, box_uv, planar_uv

BAKE = LIB = PRINTS = None
SCREEN_K = 1.6


class Mat(L.Mat):
    ROUGH_MIN = 0.02


# ----------------------------------------------------------------------------------- the sets (real sizes, m)
# PaintedPlaster017 a 2 x 1 m wall; Plaster001's fissures a few mm (as a mineral tile's); Granite005A's grains 1-2 mm (a
# mineral tile's grey speckle); linoleum_brown's marbling a sheet's 1.2 m; Paint004's orange peel (powder coat, enamel);
# Plastic013A's moulded skin; Fabric039's weave 1.5 mm (upholstery); Fabric062's screen weave under 1 mm (a roller
# blind's); Fabric034 a felt; Paper001; Cardboard002 a hardboard; Fingerprints002/008 hands' marks
S = {'plaster': ('PaintedPlaster017_2k', 2.0), 'tile': ('Plaster001_2k', 0.5), 'speckle': ('Granite005A_2k', 0.35),
     'lino': ('linoleum_brown_2k', 1.2), 'paint': ('Paint004_2k', 0.8), 'plastic': ('Plastic013A_2k', 0.4), 'rubber': ('Rubber004_2k', 0.3),
     'steel': ('Metal009_2k', 0.5), 'prints': ('Fingerprints002_2k', 0.2), 'smudge': ('Fingerprints008_2k', 0.3), 'weave': ('Fabric039_1k', 0.12),
     'screenfab': ('Fabric062_2k', 0.10), 'felt': ('Fabric034_2k', 0.15), 'paper': ('Paper001_2k', 0.35), 'board': ('Cardboard002_1k', 0.3)}
ASPECT = {}
RADIATORS = ((-3250.0, -1650.0), (600.0, 2200.0))


def sfile(k, key):
    return LIB.tex(S[k][0], key)


def photo(M, k, vec_m, keys=('diff', 'rough', 'displacement'), box=False):
    """a set's maps at its real size through a vector in metres (u across the picture's width; v by its own aspect)"""
    if k not in ASPECT:
        im = L.image(sfile(k, 'diff'), True)
        ASPECT[k] = im.size[0] / max(1, im.size[1])
    w = S[k][1]
    v = M.mapping(vec_m, (1.0 / w, ASPECT[k] / w, 1.0 / w))
    return {key: M.tex(sfile(k, key), v, color=(key == 'diff'), box=box) for key in keys}


def baked(M, atlas):
    return L.baked(M, BAKE, atlas)


def picture(M, name, uvname, color=True):
    return L.picture(M, PRINTS, name, uvname, color)


# ------------------------------------------------------------------------------------------------- materials
def m_wall(name='lab_wall_paint', above_radiators=True):
    """white emulsion on plaster, matte: the paint's own white with the plaster's light and shade held to a few
    percent; the warm air's grey film on the wall over each radiator (convection carries dust up the wall); scuffs low
    by the floor where the mop and the castors go"""
    M = Mat(name)
    p = photo(M, 'plaster', M.uv('box_m'), ('diff', 'rough', 'normal'))
    M.nmap(p['normal'].outputs[0], 'box_m', 0.12)
    col = M.value(M.rgb((0.80, 0.80, 0.78)), M.lin(M.lum(p['diff'].outputs[0]), 0.45, 0.65, 0.97, 1.02))
    rough = M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.78, 0.9)
    X, Y, Z = M.pos_mm()
    nz = M.noise(M.obj(), 7.0, 3.0)
    low = M.mul(M.inv(M.sm(Z, 30.0, 180.0)), M.sm(nz, 0.4, 0.75))
    col = M.mixc(M.mul(low, 0.25), col, M.rgb((0.45, 0.44, 0.42)))
    if above_radiators:
        plume = 0.0
        for xa, xb in RADIATORS:
            band = M.mul(M.sm(X, xa - 60.0, xa + 120.0), M.inv(M.sm(X, xb - 120.0, xb + 60.0)))
            plume = M.mx(plume, M.mul(band, M.mul(M.sm(Z, 640.0, 700.0), M.inv(M.sm(Z, 840.0, 870.0)))))
        streak = M.lin(M.noise(M.mapping(M.obj(), (30.0, 30.0, 3.0)), 1.0, 2.0), 0.3, 0.7, 0.5, 1.0)
        plume = M.mul(M.mul(plume, M.sm(Y, 2985.0, 2999.0)), streak)
        col = M.mixc(M.mul(plume, 0.22), col, M.rgb((0.42, 0.41, 0.40)))
    return M.done(col, rough)


def m_ceiling_tile():
    """a mineral fibre tile: white, its face fissured and pin-holed (Plaster001's relief at 0.5 m), its grey speckle
    (Granite005A held to a few percent); a grey halo round the supply-air diffuser (the air's dust)"""
    M = Mat('lab_ceiling_tile')
    p = photo(M, 'tile', M.uv('box_m'), ('normal', 'rough'))
    M.nmap(p['normal'].outputs[0], 'box_m', 0.6)
    sp = photo(M, 'speckle', M.uv('box_m'), ('diff',))['diff']
    col = M.value(M.rgb((0.85, 0.86, 0.86)), M.lin(M.lum(sp.outputs[0]), 0.3, 0.7, 0.95, 1.02))
    X, Y, Z = M.pos_mm()
    d = M.m('SQRT', M.add(M.m('POWER', M.add(X, 300.0), 2.0), M.m('POWER', M.sub(Y, 1700.0), 2.0)))     # (the diffuser's cell, (-300, 1700))
    halo = M.mul(M.mul(M.inv(M.sm(d, 330.0, 620.0)), M.sm(d, 300.0, 340.0)), M.lin(M.noise(M.obj(), 9.0, 3.0), 0.3, 0.7, 0.5, 1.0))
    col = M.mixc(M.mul(halo, 0.35), col, M.rgb((0.36, 0.36, 0.35)))
    return M.done(col, 0.92)


def m_paint_metal(name, base=(0.80, 0.80, 0.78), r0=0.32, peel=0.00003):
    """white powder coat or stove enamel on steel or aluminium (the T grid, the frames, the panel rims): Paint004's
    orange peel as a bump, the paint's own colour; dust where it faces up"""
    M = Mat(name)
    ov = M.obj()
    p = photo(M, 'paint', ov, ('rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], peel)
    nx, ny, nz = M.world_nrm()
    dust = M.mul(M.sm(nz, 0.7, 0.95), M.sm(M.noise(ov, 25.0, 3.0), 0.45, 0.75))
    col = M.mixc(M.mul(dust, 0.25), M.rgb(base), M.rgb((0.52, 0.50, 0.47)))
    rough = M.add(M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.08)), M.mul(dust, 0.25))
    return M.done(col, rough)


def m_floor():
    """sheet linoleum, a cool light grey, marbled (linoleum_brown's marbling, its colour taken to a cool grey),
    satin-polished; duller where feet go (the way in from the door to the bench and round the chair) and in arcs of
    castor tracks round the chair; grey fluff along the skirting where the mop leaves it"""
    M = Mat('lab_floor_linoleum')
    p = photo(M, 'lino', M.uv('box_m'), ('diff', 'rough', 'normal'))
    M.nmap(p['normal'].outputs[0], 'box_m', 0.35)
    col = M.value(M.rgb((0.34, 0.36, 0.37)), M.lin(M.lum(p['diff'].outputs[0]), 0.15, 0.45, 0.85, 1.12))
    X, Y, Z = M.pos_mm()
    ov = M.obj()
    walk = M.mx(M.mul(M.inv(M.sm(M.m('ABSOLUTE', M.sub(X, M.add(300.0, M.mul(Y, 0.25)))), 300.0, 900.0)), M.inv(M.sm(Y, 600.0, 1100.0))),
                M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(X, 1200.0), 2.0), M.m('POWER', M.add(Y, 750.0), 2.0))), 250.0, 750.0)))
    walk = M.mul(walk, M.lin(M.noise(ov, 3.0, 2.0), 0.3, 0.7, 0.4, 1.0))
    dist = M.m('SQRT', M.add(M.m('POWER', M.sub(X, 1200.0), 2.0), M.m('POWER', M.add(Y, 750.0), 2.0)))
    arcs = M.mul(M.sm(M.m('SINE', M.mul(dist, 0.09)), 0.92, 1.0), M.mul(M.inv(M.sm(dist, 450.0, 700.0)), M.sm(dist, 200.0, 260.0)))
    arcs = M.mul(arcs, M.sm(M.noise(ov, 4.0, 2.0), 0.45, 0.6))
    edge = M.mx(M.mx(M.inv(M.sm(M.sub(4000.0, X), 10.0, 60.0)), M.inv(M.sm(M.add(X, 4000.0), 10.0, 60.0))), M.inv(M.sm(M.sub(3000.0, Y), 10.0, 60.0)))
    edge = M.mul(edge, M.sm(M.noise(ov, 30.0, 3.0), 0.45, 0.7))
    col = M.mixc(M.mul(edge, 0.4), col, M.rgb((0.25, 0.24, 0.23)))
    col = M.mixc(M.mul(arcs, 0.12), col, M.rgb((0.30, 0.31, 0.32)))
    rough = M.add(M.add(M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.22, 0.4), M.mul(walk, 0.16)), M.mul(arcs, 0.12))
    return M.done(col, rough)


def m_powder(name, atlas, base, r0=0.38, hands=None, boots=True, dust_k=1.0):
    """POWDER-COATED STEEL ON A BAKED LOW (the bench's frame, the pedestal, the radiators): the coat's orange peel
    (Paint004) over the baked normal; grime where dirt collects (baked cavity and AO); WEAR where hands and feet go only
    (hands: a field (fn of X, Y, Z mm -> 0..1); boots: the bottom 15 cm), from the baked arris nearness: rubbed glossy,
    then chipped to the grey steel under it; dust on what faces up"""
    M = Mat(name)
    ov = M.obj()
    ao, cav, fine, near_cv, near_cc = baked(M, atlas)
    p = photo(M, 'paint', ov, ('rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.00003)
    X, Y, Z = M.pos_mm()
    col = M.rgb(base)
    rough = M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.1))
    grime = M.mul(M.add(M.mul(M.inv(cav), 1.3), M.mul(M.inv(ao), 0.35)), M.lin(M.noise(ov, 40.0, 3.0), 0.3, 0.7, 0.6, 1.2), clamp=True)
    col = M.mixc(M.mul(M.sm(grime, 0.1, 0.6), 0.3), col, M.rgb((0.30, 0.29, 0.27)))
    rough = M.add(rough, M.mul(grime, 0.1))
    zone = 0.0
    if hands is not None:
        zone = hands(M, X, Y, Z)
    if boots:
        zone = M.mx(zone, M.mul(M.inv(M.sm(Z, 120.0, 200.0)), 0.8))
    edge = M.sm(near_cv, 0.9, 0.98)                             # (within 0.6-3 mm of an arris: 30 mm range)
    nw = M.noise(ov, 120.0, 4.0)
    wear = M.mul(M.mul(edge, zone), M.lin(nw, 0.35, 0.75, 0.0, 1.6), clamp=True)
    rub = M.sm(wear, 0.25, 0.45)
    chip = M.sm(wear, 0.9, 0.97)                                # (chips are few: a kept room)
    rough = M.sub(rough, M.mul(rub, 0.12))
    col = M.mixc(chip, col, M.rgb((0.30, 0.30, 0.29)))
    metal = M.mul(chip, 1.0)
    rough = M.mixf(chip, rough, 0.42)
    nx, ny, nz = M.world_nrm()
    dust = M.mul(M.mul(M.sm(nz, 0.75, 0.97), M.sm(M.noise(ov, 30.0, 3.0), 0.4, 0.75)), dust_k)
    col = M.mixc(M.mul(dust, 0.3), col, M.rgb((0.50, 0.48, 0.45)))
    rough = M.add(rough, M.mul(dust, 0.3))
    return M.done(col, rough, metal)


def hands_bench(M, X, Y, Z):
    """the bench: the front edge of the top where forearms and hands rest, the pedestal's drawer fronts round each bow
    handle (the handles at z 251, 388, 525 mm, x 2540 mm)"""
    front = M.mul(M.inv(M.sm(Y, 820.0, 900.0)), M.sm(Z, 850.0, 880.0))
    hz = 0.0
    for zc in (251.0, 388.0, 525.0):
        hz = M.mx(hz, M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(X, 2540.0), 2.0), M.m('POWER', M.sub(Z, zc), 2.0))), 60.0, 160.0)))
    return M.mx(front, hz)


def m_laminate_top():
    """the bench's top: white high-pressure laminate (Plastic013A's moulded skin, the laminate's satin) on its baked low;
    its edge band a shade greyer; finger smears where hands work (by the keyboard and the mouse, along the front); a
    coffee ring by the white mug (the mug was set down wet); grime only in the band's seam; the front arris rubbed"""
    M = Mat('lab_bench_top_laminate')
    ov = M.obj()
    ao, cav, fine, near_cv, near_cc = baked(M, 'bench')
    p = photo(M, 'plastic', ov, ('rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.00002)
    X, Y, Z = M.pos_mm()
    nx, ny, nz = M.world_nrm()
    top = M.sm(nz, 0.8, 0.95)
    col = M.mixc(top, M.rgb((0.74, 0.74, 0.72)), M.rgb((0.84, 0.84, 0.82)))
    rough = M.add(M.mixf(top, 0.3, 0.42), M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.08))
    sm = photo(M, 'smudge', ov, ('diff',), box=True)['diff']
    fp = photo(M, 'prints', ov, ('diff',), box=True)['diff']
    work = M.mx(M.mul(M.inv(M.sm(Y, 850.0, 1000.0)), 0.8),
                M.mul(M.mul(M.sm(X, 1850.0, 1950.0), M.inv(M.sm(X, 2650.0, 2750.0))), M.mul(M.sm(Y, 960.0, 1000.0), M.inv(M.sm(Y, 1180.0, 1260.0)))))
    marks = M.mul(M.mul(work, top), M.mx(M.sm(M.lum(sm.outputs[0]), 0.2, 0.55), M.sm(M.lum(fp.outputs[0]), 0.15, 0.5)))
    rough = M.add(rough, M.mul(marks, 0.18))
    col = M.value(col, M.sub(1.0, M.mul(marks, 0.03)))
    ring = M.inv(M.sm(M.m('ABSOLUTE', M.sub(M.m('SQRT', M.add(M.m('POWER', M.sub(X, 812.0), 2.0), M.m('POWER', M.sub(Y, 1238.0), 2.0))), 39.0)), 0.5, 2.0))
    ring = M.mul(M.mul(ring, top), M.lin(M.noise(ov, 90.0, 2.0), 0.3, 0.7, 0.3, 1.0))
    col = M.mixc(M.mul(ring, 0.35), col, M.rgb((0.42, 0.30, 0.20)))
    grime = M.mul(M.inv(cav), M.lin(M.noise(ov, 50.0, 3.0), 0.3, 0.7, 0.5, 1.1), clamp=True)
    col = M.mixc(M.mul(M.sm(grime, 0.15, 0.6), 0.25), col, M.rgb((0.35, 0.34, 0.32)))
    front = M.mul(M.inv(M.sm(Y, 810.0, 860.0)), M.sm(near_cv, 0.9, 0.98))
    col = M.value(col, M.sub(1.0, M.mul(front, 0.06)))
    return M.done(col, rough)


def m_plastic(name, base, r0=0.42, bump_m=0.00003, sss=0.0, polish=None, key='plastic', extra=None):
    """moulded plastic (Plastic013A's skin as a bump); polish: a field where hands have made it glossier (a mouse's
    back, a key's top)"""
    M = Mat(name)
    ov = M.obj()
    p = photo(M, key, ov, ('rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], bump_m)
    rough = M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.15))
    if polish is not None:
        rough = M.sub(rough, M.mul(polish(M), 0.2))
    ex = dict(extra or {})
    if sss:
        ex.update({'Subsurface Weight': sss, 'Subsurface Radius': (0.01, 0.01, 0.01)})
    return M.done(M.rgb(base), rough, 0.0, ex)


def m_metal(name, base=(0.80, 0.80, 0.80), r0=0.22, brushed=False, prints=0.0):
    M = Mat(name)
    ov = M.obj()
    rough = r0
    if brushed:
        p = photo(M, 'steel', ov, ('rough',), box=True)
        rough = M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.2))
    if prints:
        fp = photo(M, 'prints', ov, ('diff',), box=True)['diff']
        rough = M.add(rough, M.mul(M.sm(M.lum(fp.outputs[0]), 0.12, 0.5), prints))
    return M.done(M.rgb(base), rough, 1.0)


def m_rubber(name='lab_rubber', base=(0.02, 0.02, 0.02)):
    M = Mat(name)
    p = photo(M, 'rubber', M.obj(), ('diff', 'rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.00015)
    return M.done(M.value(M.rgb(base), M.lin(M.lum(p['diff'].outputs[0]), 0.0, 0.3, 0.8, 1.3)), M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.65, 0.9))


def m_glass_thin(name, smudge=0.0):
    """window glass: a thin pane as a film, a Fresnel mirror over a straight pass (the park is not displaced), letting
    about three quarters of the day through (low-E double glazing); its shadow is what it lets through (transparent
    shadows); a faint film of handling and weather"""
    M = Mat(name)
    for n in list(M.N):
        if n.type != 'OUTPUT_MATERIAL':
            M.N.remove(n)
    tr = M.N.new('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = (0.74, 0.77, 0.76, 1.0)
    gl = M.N.new('ShaderNodeBsdfGlossy')
    gl.inputs['Roughness'].default_value = 0.02
    lw = M.N.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.08
    f = M.add(M.mul(lw.outputs['Fresnel'], 0.85), 0.04)
    if smudge:
        sm = photo(M, 'smudge', M.obj(), ('diff',), box=True)['diff']
        M.L.new(M.add(0.02, M.mul(M.sm(M.lum(sm.outputs[0]), 0.2, 0.6), smudge)), gl.inputs['Roughness'])
    mx = M.N.new('ShaderNodeMixShader')
    M.L.new(f, mx.inputs[0])
    M.L.new(tr.outputs[0], mx.inputs[1])
    M.L.new(gl.outputs[0], mx.inputs[2])
    M.L.new(mx.outputs[0], M.out.inputs[0])
    M.mat.surface_render_method = 'BLENDED'
    M.mat.use_transparent_shadow = True
    return M.mat


def m_screen_display():
    """the screen's panel: anti-glare glass over the picture (screen_document.png), its glow SCREEN_K"""
    M = Mat('lab_screen_display')
    pic = picture(M, 'screen_document.png', 'print')
    m = M.done(M.rgb((0.01, 0.01, 0.012)), 0.28, 0.0, {'Emission Strength': float(SCREEN_K)})
    M.L.new(pic.outputs[0], M.bsdf.inputs['Emission Color'])
    return m


def m_ceramic(name, base, r0=0.06, drip=None):
    """glazed stoneware (a mug): a clear glaze's mirror; drip: a coffee run down the outside below the rim (a pour that
    overran), as (angle about the mug's axis, deg; the mug's centre x, y mm)"""
    M = Mat(name)
    ov = M.obj()
    col = M.rgb(base)
    fp = photo(M, 'prints', ov, ('diff',), box=True)['diff']
    rough = M.add(r0, M.mul(M.sm(M.lum(fp.outputs[0]), 0.15, 0.5), 0.12))
    if drip is not None:
        ang, cx, cy = drip
        X, Y, Z = M.pos_mm()
        a = M.m('ARCTAN2', M.sub(Y, cy), M.sub(X, cx))
        da = M.m('ABSOLUTE', M.sub(a, math.radians(ang)))
        run = M.mul(M.inv(M.sm(da, 0.05, 0.12)), M.mul(M.sm(Z, 925.0, 960.0), M.inv(M.sm(Z, 990.0, 996.0))))
        col = M.mixc(M.mul(run, 0.45), col, M.rgb((0.30, 0.16, 0.06)))
    return M.done(col, rough, 0.0, {'Coat Weight': 0.3, 'Coat Roughness': 0.04})


def _liquid(name, base, r0):
    """a drink's still surface: a dark glossy liquid"""
    M = Mat(name)
    return M.done(M.rgb(base), r0, 0.0, {'Specular IOR Level': 0.5})


def m_fabric(name, k, base, r=(0.7, 0.95), bump_m=0.0003, sheen=0.4, translucent=0.0, rub=None):
    """a woven cloth from its photograph (its weave as a bump, its own light and shade on the cloth's colour);
    translucent: what light it lets through from behind (a blind against the day)"""
    M = Mat(name)
    p = photo(M, k, M.obj(), ('diff', 'rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], bump_m)
    col = M.value(M.rgb(base), M.lin(M.lum(p['diff'].outputs[0]), 0.2, 0.8, 0.82, 1.15))
    rough = M.lin(p['rough'].outputs[0], 0.0, 1.0, r[0], r[1])
    if rub is not None:
        rb = rub(M)
        col = M.value(col, M.add(1.0, M.mul(rb, 0.5)))
        rough = M.sub(rough, M.mul(rb, 0.15))
    m = M.done(col, rough, 0.0, {'Sheen Weight': sheen, 'Sheen Roughness': 0.4})
    if translucent:
        tr = M.N.new('ShaderNodeBsdfTranslucent')
        M.L.new(col, tr.inputs['Color'])
        mx = M.N.new('ShaderNodeMixShader')
        mx.inputs[0].default_value = translucent
        M.L.new(M.bsdf.outputs[0], mx.inputs[1])
        M.L.new(tr.outputs[0], mx.inputs[2])
        M.L.new(mx.outputs[0], M.out.inputs[0])
    return m


def m_paper(name, pic=None, uvname='print', tint=(0.86, 0.86, 0.83), translucent=0.12):
    M = Mat(name)
    p = photo(M, 'paper', M.obj(), ('diff', 'rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.00004)
    col = M.value(M.rgb(tint), M.lin(M.lum(p['diff'].outputs[0]), 0.4, 0.9, 0.95, 1.03))
    if pic:
        ink = picture(M, pic, uvname)
        c2 = M.mixc(1.0, col, ink.outputs[0])
        c2.node.blend_type = 'MULTIPLY'
        col = c2
    m = M.done(col, M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.75, 0.92))
    tr = M.N.new('ShaderNodeBsdfTranslucent')
    M.L.new(col, tr.inputs['Color'])
    mx = M.N.new('ShaderNodeMixShader')
    mx.inputs[0].default_value = translucent
    M.L.new(M.bsdf.outputs[0], mx.inputs[1])
    M.L.new(tr.outputs[0], mx.inputs[2])
    M.L.new(mx.outputs[0], M.out.inputs[0])
    return m


def m_whiteboard():
    """the board's enamelled steel: a near-mirror white; the ghosts of old marker in it (whiteboard_ghosts.png at 1 mm
    a pixel: R dark marker, G red, B the eraser's film), each ghost a little duller and stained; a film of handling
    where hands lean on its lower half"""
    M = Mat('lab_whiteboard_enamel')
    g = picture(M, 'whiteboard_ghosts.png', 'print', color=False)
    gs = M.sep(g.outputs[0])
    col = M.rgb((0.84, 0.85, 0.85))
    col = M.mixc(M.mul(gs[0], 1.3), col, M.rgb((0.52, 0.55, 0.62)))
    col = M.mixc(M.mul(gs[1], 1.2), col, M.rgb((0.72, 0.50, 0.50)))
    col = M.mixc(M.mul(gs[2], 0.10), col, M.rgb((0.62, 0.63, 0.65)))
    rough = M.add(0.05, M.add(M.mul(gs[2], 0.12), M.mul(M.add(gs[0], gs[1]), 0.25)))
    fp = photo(M, 'prints', M.obj(), ('diff',), box=True)['diff']
    X, Y, Z = M.pos_mm()
    lean = M.mul(M.inv(M.sm(Z, 1250.0, 1500.0)), M.sm(M.lum(fp.outputs[0]), 0.15, 0.5))
    rough = M.add(rough, M.mul(lean, 0.12))
    return M.done(col, rough, 0.0, {'Coat Weight': 0.5, 'Coat Roughness': 0.03})


def m_markers():
    """four markers in the tray: white barrels, caps black, blue, red, green (along y from 520, 700, 905, 1720 mm)"""
    M = Mat('lab_board_markers')
    X, Y, Z = M.pos_mm()
    col = M.rgb((0.82, 0.82, 0.80))
    for y0, c in ((520.0, (0.02, 0.02, 0.02)), (700.0, (0.02, 0.06, 0.35)), (905.0, (0.45, 0.02, 0.02)), (1720.0, (0.02, 0.22, 0.05))):
        cap = M.mul(M.sm(Y, y0 + 93.0, y0 + 95.5), M.inv(M.sm(Y, y0 + 137.0, y0 + 140.0)))
        col = M.mixc(cap, col, M.rgb(c))
    return M.done(col, 0.35)


def m_magnets():
    M = Mat('lab_board_magnets')
    X, Y, Z = M.pos_mm()
    col = M.rgb((0.55, 0.03, 0.02))
    col = M.mixc(M.inv(M.sm(Y, 1800.0, 1900.0)), M.rgb((0.02, 0.10, 0.45)), col)
    col = M.mixc(M.inv(M.sm(Y, 700.0, 800.0)), col, M.rgb((0.75, 0.55, 0.02)))
    return M.done(col, 0.3)


def m_valve(name, x_head, sign, chrome_mm=58.0):
    """a radiator valve: a chrome body and nut, a white thermostatic head (or the lockshield's white cap) from chrome_mm
    out along the valve's axis (x_head: where it leaves the radiator, mm; sign: which way along x it points)"""
    M = Mat(name)
    X, Y, Z = M.pos_mm()
    along = M.mul(M.sub(X, x_head), sign)
    head = M.sm(along, chrome_mm - 1.0, chrome_mm + 1.0)
    p = photo(M, 'plastic', M.obj(), ('displacement',), box=True)
    M.bump(p['displacement'].outputs[0], 0.00002)
    col = M.mixc(head, M.rgb((0.80, 0.80, 0.80)), M.rgb((0.82, 0.82, 0.80)))
    return M.done(col, M.mixf(head, 0.12, 0.4), M.inv(head))


def m_sprinkler(name):
    M = Mat(name)
    X, Y, Z = M.pos_mm()
    white = M.sm(Z, 2791.0, 2793.0)
    return M.done(M.mixc(white, M.rgb((0.75, 0.62, 0.35)), M.rgb((0.80, 0.80, 0.78))), M.mixf(white, 0.2, 0.4), M.inv(white))


def seat_rub(M):
    """the seat's front edge and the back's middle, where a sitter's legs and back rub the weave"""
    X, Y, Z = M.pos_mm()
    return M.mul(M.sm(Z, 495.0, 515.0), M.inv(M.sm(Z, 540.0, 560.0)))


def keytops(M):
    nx, ny, nz = M.world_nrm()
    return M.sm(nz, 0.85, 0.97)


def mouse_back(M):
    X, Y, Z = M.pos_mm()
    return M.sm(Z, 920.0, 935.0)


def assign_all(room, panel_w):
    """every part of the room its material"""
    OB = bpy.data.objects

    def objs(*prefixes, exact=()):
        return [o for o in room.objects if o.type == 'MESH' and (o.name in exact or any(o.name.startswith(p) for p in prefixes))]

    def mat_once(name, fn):
        return bpy.data.materials.get(name) or fn()
    for o in [o for o in room.objects if o.type == 'MESH']:
        box_uv(o)
    planar_uv(OB['screen_glass'], 'print', (2200.0, 1208.0), 'xz', (598.0, 347.6))
    planar_uv(OB['board_surface'], 'print', (1200.0, 1450.0), 'yz', (1990.0, 990.0), flip_u=True)
    planar_uv(OB['clipboard_sheet'], 'print', (1315.0, 1110.0), 'xy', (210.0, 297.0), deg=-14.0)
    planar_uv(OB['board_sheet'], 'print', (1855.0, 1651.5), 'yz', (210.0, 297.0), flip_u=True)
    WALL = m_wall()
    for o in objs('wall_back', 'wall_left', 'wall_right', 'wall_front_unseen'):
        assign(o, WALL)
    assign(OB['room_slab'], m_paint_metal('lab_slab_unseen', (0.4, 0.4, 0.4), 0.9))
    assign(OB['room_floor'], m_floor())
    assign(OB['skirting'], m_paint_metal('lab_skirting_satin', (0.80, 0.80, 0.78), 0.3))
    assign(OB['window_board'], m_plastic('lab_window_board', (0.80, 0.80, 0.78), 0.3))
    assign(OB['window_sill_outside'], m_metal('lab_sill_outside', (0.55, 0.55, 0.55), 0.5))
    FRAME = m_paint_metal('lab_window_frame_powder', (0.82, 0.82, 0.80), 0.28)
    for o in objs('window_frame', 'window_mullions', 'window_beads', 'window_hinge_covers') + [o for o in objs('window_sash_')
                                                                                                if o.name.endswith(('_frame', '_handle_rose', '_handle_neck', '_handle'))]:
        assign(o, FRAME)
    RUB = m_rubber()
    for o in objs('window_gaskets') + [o for o in objs('window_sash_') if o.name.endswith('_gasket')]:
        assign(o, RUB)
    GLASS = m_glass_thin('lab_window_glass', smudge=0.06)
    for o in objs('window_glass') + [o for o in objs('window_sash_') if o.name.endswith('_glass')]:
        assign(o, GLASS)
        o.visible_shadow = False                               # (the sun comes through the panes: they cast no shadow)
    for o in objs('window_sash_1_stay'):
        assign(o, m_metal('lab_sash_stay_steel', (0.7, 0.7, 0.7), 0.3, brushed=True))
    # the blinds: a light warm-grey screen fabric that the day shines through; anodised hem bars; white plastic ends
    CLOTH = m_fabric('lab_blind_screen_fabric', 'screenfab', (0.62, 0.62, 0.60), r=(0.8, 0.95), bump_m=0.0002, sheen=0.2, translucent=0.35)
    for o in objs('blind_'):
        if o.name.endswith(('_cloth', '_roll')):
            assign(o, CLOTH)
        elif o.name.endswith('_hem_bar'):
            assign(o, mat_once('lab_blind_hem_alu', lambda: m_metal('lab_blind_hem_alu', (0.78, 0.78, 0.78), 0.32)))
        elif o.name.endswith('_cord'):
            assign(o, mat_once('lab_blind_cord', lambda: m_plastic('lab_blind_cord', (0.62, 0.62, 0.62), 0.5)))
        else:
            assign(o, mat_once('lab_white_plastic', lambda: m_plastic('lab_white_plastic', (0.80, 0.80, 0.78), 0.35)))
    # the radiators (lows, baked): white stove enamel, dust on the grille and in the flutes
    RADM = m_powder('lab_radiator_enamel', 'radiators', (0.80, 0.80, 0.78), r0=0.26, hands=None, boots=False, dust_k=1.4)
    for o in objs('radiator_'):
        if o.name.endswith('_fins_dark'):
            assign(o, mat_once('lab_radiator_fins', lambda: m_paint_metal('lab_radiator_fins', (0.08, 0.08, 0.08), 0.6)))
        elif '_valve' in o.name or '_lockshield' in o.name:
            k = int(o.name.split('_')[1])
            xa, xb = RADIATORS[k]
            assign(o, m_valve(o.name + '_mat', xb + 1.0, 1.0) if '_valve' in o.name else m_valve(o.name + '_mat', xa - 1.0, -1.0, 46.0))
        else:
            assign(o, RADM)
    # the ceiling
    assign(OB['ceiling_tiles'], m_ceiling_tile())
    GRID = m_paint_metal('lab_ceiling_grid_white', (0.82, 0.82, 0.80), 0.35)
    for o in objs('ceiling_wall_angle', 'ceiling_grid', 'ceiling_panel_frames', 'ceiling_diffuser', 'ceiling_panel_backs'):
        if o.name == 'ceiling_diffuser_neck_dark':
            assign(o, m_paint_metal('lab_diffuser_neck', (0.03, 0.03, 0.03), 0.6))
        else:
            assign(o, GRID)
    PM = Mat('lab_led_panel_diffuser')
    assign(OB['ceiling_panel_diffusers'], PM.done(PM.rgb((0.85, 0.85, 0.85)), 0.5, 0.0, {'Emission Color': (1.0, 0.97, 0.93, 1.0),
                                                                                          'Emission Strength': panel_w / (math.pi * 0.570 * 0.570)}))
    for o in objs('ceiling_sprinkler_'):
        assign(o, m_sprinkler(o.name + '_mat'))
    assign(OB['ceiling_smoke_detector'], m_plastic('lab_detector_plastic', (0.78, 0.77, 0.72), 0.4))
    assign(OB['floor_box_frame'], m_metal('lab_floor_box_steel', (0.72, 0.72, 0.72), 0.3, brushed=True))
    assign(OB['floor_box_lid'], OB['floor_box_frame'].data.materials[0])
    assign(OB['floor_box_outlet'], m_plastic('lab_floor_box_outlet', (0.1, 0.1, 0.1), 0.45))
    # the bench and its pedestal (lows, baked)
    assign(OB['bench_top_low'], m_laminate_top())
    FRAME_B = m_powder('lab_bench_frame_powder', 'bench', (0.66, 0.68, 0.68), r0=0.36, hands=hands_bench, dust_k=0.3)
    for n in ('bench_legs_low', 'bench_rails_low', 'bench_stretchers_low', 'pedestal_body_low', 'pedestal_cap_low', 'pedestal_fronts_low'):
        assign(OB[n], FRAME_B)
    assign(OB['bench_feet_low'], m_plastic('lab_bench_feet', (0.02, 0.02, 0.02), 0.5))
    assign(OB['pedestal_handles_low'], m_metal('lab_pedestal_handles', (0.85, 0.85, 0.85), 0.18, prints=0.15))
    assign(OB['pedestal_lock_low'], m_metal('lab_pedestal_lock', (0.80, 0.80, 0.78), 0.15))
    assign(OB['pedestal_castors_low'], m_plastic('lab_castor_nylon', (0.02, 0.02, 0.02), 0.4))
    # the chair (lows, baked): a silver-painted aluminium five-star base, black castors, a black gas column, a black
    # textured shell under a black woven seat and back
    CH = Mat('lab_chair_base_silver')
    ao, cav, fine, ncv, ncc = baked(CH, 'chair')
    X_, Y_, Z_ = CH.pos_mm()
    scuff = CH.mul(CH.sm(ncv, 0.85, 0.97), CH.mul(CH.inv(CH.sm(Z_, 110.0, 150.0)), CH.sm(CH.noise(CH.obj(), 140.0, 4.0), 0.5, 0.7)))
    assign(OB['chair_base_low'], CH.done(CH.mixc(scuff, CH.rgb((0.62, 0.63, 0.64)), CH.rgb((0.20, 0.20, 0.20))), CH.add(0.38, CH.mul(CH.inv(ao), 0.15)), CH.inv(scuff)))
    BLACK = m_plastic('lab_chair_black_plastic', (0.022, 0.022, 0.024), 0.55, bump_m=0.00006)
    for n in ('chair_castors_low', 'chair_column_low', 'chair_mechanism_low', 'chair_lever_low', 'chair_seat_shell_low', 'chair_back_shell_low', 'chair_back_mount_low'):
        assign(OB[n], BLACK)
    assign(OB['chair_back_upright_low'], OB['chair_base_low'].data.materials[0])
    UPH = m_fabric('lab_chair_upholstery', 'weave', (0.035, 0.035, 0.038), r=(0.8, 0.95), bump_m=0.0004, sheen=0.5, rub=seat_rub)
    for n in ('chair_seat_cushion_low', 'chair_seat_piping_low', 'chair_back_cushion_low'):
        assign(OB[n], UPH)
    # the screen, the computer, the power, the cables, keyboard and mouse
    SCR = m_plastic('lab_screen_black_plastic', (0.02, 0.02, 0.022), 0.42)
    for n in ('screen_body', 'screen_back', 'screen_hinge', 'screen_neck', 'screen_foot'):
        assign(OB[n], SCR)
    assign(OB['screen_glass'], m_screen_display())
    assign(OB['computer_case'], m_metal('lab_computer_alu', (0.80, 0.80, 0.82), 0.28, brushed=True, prints=0.1))
    assign(OB['computer_feet_and_button'], m_plastic('lab_computer_feet', (0.05, 0.05, 0.05), 0.5))
    WHITE_P = mat_once('lab_white_plastic', lambda: m_plastic('lab_white_plastic', (0.80, 0.80, 0.78), 0.35))
    assign(OB['power_strip'], WHITE_P)
    assign(OB['power_strip_wells_dark'], m_plastic('lab_dark_wells', (0.05, 0.05, 0.05), 0.5))
    RK = Mat('lab_rocker_lit')
    assign(OB['power_strip_rocker'], RK.done(RK.rgb((0.5, 0.05, 0.02)), 0.3, 0.0, {'Emission Color': (1.0, 0.12, 0.03, 1.0), 'Emission Strength': 2.0}))
    assign(OB['power_plugs'], WHITE_P)
    assign(OB['bench_cables'], m_plastic('lab_cable_pvc', (0.025, 0.025, 0.025), 0.45))
    assign(OB['keyboard_cable'], OB['bench_cables'].data.materials[0])
    assign(OB['keyboard_case'], m_plastic('lab_keyboard_case', (0.025, 0.025, 0.027), 0.5))
    assign(OB['keyboard_keys'], m_plastic('lab_keyboard_keys', (0.03, 0.03, 0.032), 0.45, polish=keytops))
    assign(OB['mouse_body'], m_plastic('lab_mouse_body', (0.025, 0.025, 0.027), 0.42, polish=mouse_back))
    assign(OB['mouse_wheel'], RUB)
    # the mugs: a white one with coffee left in it (a drip down its side), a deep blue one with tea and its bag's string
    assign(OB['mug_a'], m_ceramic('lab_mug_white', (0.82, 0.82, 0.80), drip=(150.0, 700.0, 1200.0)))
    assign(OB['mug_a_drink'], _liquid('lab_coffee', (0.025, 0.010, 0.004), 0.03))
    assign(OB['mug_b'], m_ceramic('lab_mug_blue', (0.02, 0.05, 0.16)))
    assign(OB['mug_b_drink'], _liquid('lab_tea', (0.20, 0.06, 0.01), 0.03))
    assign(OB['mug_b_string'], m_fabric('lab_teabag_string', 'paper', (0.8, 0.78, 0.72), sheen=0.1))
    assign(OB['mug_b_tag'], m_paper('lab_teabag_tag', tint=(0.78, 0.62, 0.12)))
    # the clipboard, its form, its pen
    assign(OB['clipboard_board'], m_fabric('lab_clipboard_hardboard', 'board', (0.16, 0.09, 0.045), r=(0.55, 0.7), bump_m=0.0001, sheen=0.0))
    assign(OB['clipboard_paper_stack'], m_paper('lab_paper_stack'))
    assign(OB['clipboard_sheet'], m_paper('lab_clipboard_form', 'clipboard_form.png'))
    CLIP = m_metal('lab_clip_nickel', (0.76, 0.75, 0.72), 0.22, prints=0.1)
    for n in ('clipboard_clip_base', 'clipboard_clip_jaw', 'clipboard_clip_spring', 'clipboard_rivets'):
        assign(OB[n], CLIP)
    assign(OB['clipboard_clip_guards'], RUB)
    assign(OB['pen_barrel'], m_plastic('lab_pen_blue', (0.02, 0.06, 0.28), 0.25, sss=0.2))
    assign(OB['pen_clip'], OB['pen_barrel'].data.materials[0])
    assign(OB['pen_clip_root'], OB['pen_barrel'].data.materials[0])
    # the whiteboard
    assign(OB['board_surface'], m_whiteboard())
    ALU = m_metal('lab_board_frame_anodised', (0.80, 0.80, 0.80), 0.32, brushed=True)
    for n in ('board_frame', 'board_tray'):
        assign(OB[n], ALU)
    GREYP = m_plastic('lab_grey_plastic', (0.20, 0.20, 0.21), 0.45)
    for n in ('board_corners', 'board_tray_ends'):
        assign(OB[n], GREYP)
    assign(OB['board_markers'], m_markers())
    ER = Mat('lab_board_eraser')
    X_, Y_, Z_ = ER.pos_mm()
    felt = photo(ER, 'felt', ER.obj(), ('diff', 'displacement'), box=True)
    ER.bump(felt['displacement'].outputs[0], 0.0004)
    top_ = ER.sm(Z_, 928.5, 930.0)                              # (the felt pad below 929 mm, the moulded grip above)
    assign(OB['board_eraser'], ER.done(ER.mixc(top_, ER.value(ER.rgb((0.12, 0.12, 0.14)), ER.lin(ER.lum(felt['diff'].outputs[0]), 0.3, 0.7, 0.8, 1.2)),
                                               ER.rgb((0.03, 0.03, 0.035))), ER.mixf(top_, 0.95, 0.4)))
    assign(OB['board_magnets'], m_magnets())
    assign(OB['board_sheet'], m_paper('lab_notice', 'notice.png'))
    # the plants
    plants_look.apply([o for o in room.objects if o.type == 'MESH'], prefix='lab')


# --------------------------------------------------------------------------------------------- the CC0 models
def place_gltf(room, path, at, yaw=0.0, pick=None, name=None):
    """a Poly Haven model (its own materials, its real size) stood at `at` (m): its lowest point on at.z, centred;
    pick: only the meshes whose names start so"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH' and (pick is None or any(o.name.startswith(p) for p in pick))]
    drop = [o for o in new if o not in meshes]
    out = []
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        for c_ in list(o.users_collection):
            c_.objects.unlink(o)
        room.objects.link(o)
        o['eido_loaded_asset'] = True
        out.append(o)
    for o in drop:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()
    lo = Vector((min((o.matrix_world @ Vector(b))[i] for o in out for b in o.bound_box) for i in range(3)))
    hi = Vector((max((o.matrix_world @ Vector(b))[i] for o in out for b in o.bound_box) for i in range(3)))
    c_ = (lo + hi) / 2.0
    R = Matrix.Translation(Vector(at)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Translation(Vector((-c_.x, -c_.y, -lo.z)))
    for o in out:
        o.matrix_world = R @ o.matrix_world
        if name:
            o.name = f'{name}_{o.name}'
    bpy.context.view_layer.update()
    return out, hi - lo


def place_models(room):
    """the wall clock over the whiteboard (its face to the room, -x), and on the bench a pencil cup, a pencil, a pen and a
    yellow pad, each lying on the top by itself"""
    clock, cs = place_gltf(room, LIB.model('wall_clock'), (0.0, 0.0, 0.0), 0.0, name='cc0')
    dims = sorted(range(3), key=lambda i: cs[i])
    if dims[0] == 2:                                            # lying on its back: stand it up, face to -y first
        for o in clock:
            o.matrix_world = Matrix.Rotation(math.radians(90.0), 4, 'X') @ o.matrix_world
    elif dims[0] == 0:
        for o in clock:
            o.matrix_world = Matrix.Rotation(math.radians(-90.0), 4, 'Z') @ o.matrix_world
    bpy.context.view_layer.update()
    for o in clock:                                             # face to -y -> face to -x (the room, from the right wall)
        o.matrix_world = Matrix.Rotation(math.radians(-90.0), 4, 'Z') @ o.matrix_world
    bpy.context.view_layer.update()
    lo = Vector((min((o.matrix_world @ Vector(b))[i] for o in clock for b in o.bound_box) for i in range(3)))
    hi = Vector((max((o.matrix_world @ Vector(b))[i] for o in clock for b in o.bound_box) for i in range(3)))
    for o in clock:
        o.matrix_world = Matrix.Translation(Vector((3.999 - hi.x, 1.2 - (lo.y + hi.y) / 2.0, 2.36 - (lo.z + hi.z) / 2.0))) @ o.matrix_world
    bpy.context.view_layer.update()
    sup = LIB.model('stationery_supplies')
    place_gltf(room, sup, (1.43, 1.47, 0.9), 0.3, pick=['stationery_supplies_pencilcup'], name='cc0')
    place_gltf(room, sup, (1.62, 1.33, 0.9), math.radians(20.0), pick=['stationery_supplies_pencil_used'], name='cc0')
    place_gltf(room, sup, (0.52, 1.36, 0.9), math.radians(-35.0), pick=['stationery_supplies_pen_blue'], name='cc0')
    place_gltf(room, LIB.model('office_notepads'), (2.76, 1.02, 0.9), math.radians(-8.0), pick=['office_notepads_yellow_pad'], name='cc0')


# ----------------------------------------------------------------------------------------- the light, the world
def lamp(coll, name, kind, energy, color, **kw):
    ld = bpy.data.lights.new(name, kind)
    ld.energy, ld.color = energy, color
    for k, v in kw.items():
        setattr(ld, k, v)
    o = bpy.data.objects.new(name, ld)
    coll.objects.link(o)
    return o


HDRI_ID, HDRI_RES, HDRI_SUN_AZ = 'pretoria_gardens', '4k', -36.0     # (its sun's direction in Blender's frame, unturned)


def lights(room, sun_w, panel_w, sun_el, sun_az):
    """collection lab_lights in the room: the sun through the windows and an area light under each LED panel"""
    LIGHTS = bpy.data.collections.get('lab_lights') or bpy.data.collections.new('lab_lights')
    if LIGHTS.name not in room.children:
        room.children.link(LIGHTS)
    el, az = math.radians(sun_el), math.radians(sun_az)
    to_sun = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    sun = lamp(LIGHTS, 'lab_sun', 'SUN', sun_w, (1.0, 0.975, 0.945), angle=math.radians(0.6))
    sun.rotation_euler = (-to_sun).to_track_quat('-Z', 'Y').to_euler()
    GXS = [-3600.0 + 600.0 * i for i in range(13)]
    GYS = [-1600.0 + 600.0 * j for j in range(8)]
    CX, CY = [-4000.0] + GXS + [4000.0], [-2000.0] + GYS + [3000.0]
    for k, (i, j) in enumerate(sorted({(i, j) for i in (2, 5, 8, 11) for j in (2, 5)})):
        o = lamp(LIGHTS, f'lab_led_panel_{k}', 'AREA', panel_w, (1.0, 0.97, 0.93), shape='SQUARE', size=0.57)
        o.location = ((CX[i] + CX[i + 1]) / 2000.0, (CY[j] + CY[j + 1]) / 2000.0, 2.7995)
        o.data.use_shadow = True
    return LIGHTS


def make_world(strength, sun_az, clamp):
    """the world 'lab_world': the HDRI turned so its sky stands behind the sun lamp, its own sun clamped to `clamp`; what
    lights the room has its ground taken down and its colour cooled a little (from an upper floor the ground is far
    and below the sill); what the lens sees through the glass is the sky as it is"""
    w = bpy.data.worlds.get('lab_world') or bpy.data.worlds.new('lab_world')
    w.use_nodes = True
    WN = NT(w.node_tree)
    for n in list(WN.N):
        if n.type != 'OUTPUT_WORLD':
            WN.N.remove(n)
    tc = WN.N.new('ShaderNodeTexCoord')
    mp = WN.N.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(HDRI_SUN_AZ - sun_az))
    WN.L.new(tc.outputs['Generated'], mp.inputs['Vector'])
    env = WN.N.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(LIB.hdri(HDRI_ID, HDRI_RES), check_existing=True)
    WN.L.new(mp.outputs[0], env.inputs['Vector'])
    bw = WN.N.new('ShaderNodeRGBToBW')
    WN.L.new(env.outputs[0], bw.inputs[0])
    fac = WN.m('MINIMUM', 1.0, WN.m('DIVIDE', clamp, WN.m('MAXIMUM', bw.outputs[0], 1e-4)))
    sc_ = WN.N.new('ShaderNodeVectorMath')
    sc_.operation = 'SCALE'
    WN.L.new(env.outputs[0], sc_.inputs[0])
    WN.L.new(fac, sc_.inputs['Scale'])
    dsep = WN.N.new('ShaderNodeSeparateXYZ')
    WN.L.new(tc.outputs['Generated'], dsep.inputs[0])
    ground = WN.lin(dsep.outputs[2], -0.12, 0.05, 0.35, 1.0, clamp=True)
    hs_ = WN.N.new('ShaderNodeHueSaturation')
    WN.L.new(sc_.outputs[0], hs_.inputs['Color'])
    WN.L.new(WN.lin(dsep.outputs[2], -0.12, 0.05, 0.25, 0.6, clamp=True), hs_.inputs['Saturation'])
    lit = WN.mixc(1.0, hs_.outputs[0], (0.93, 0.98, 1.06, 1.0))
    lit.node.blend_type = 'MULTIPLY'
    lit2 = WN.N.new('ShaderNodeVectorMath')
    lit2.operation = 'SCALE'
    WN.L.new(lit, lit2.inputs[0])
    WN.L.new(ground, lit2.inputs['Scale'])
    lp = WN.N.new('ShaderNodeLightPath')
    seen = WN.mixc(lp.outputs['Is Camera Ray'], lit2.outputs[0], sc_.outputs[0])
    bg = WN.N.new('ShaderNodeBackground')
    WN.L.new(seen, bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    WN.L.new(bg.outputs[0], next(n for n in WN.N if n.type == 'OUTPUT_WORLD').inputs[0])
    return w


def apply(room, bake_dir, library, prints_dir, world=4.5, sun=30.0, panel=8.0, sun_el=38.0, sun_az=70.0, screen=1.6, clamp=4.0):
    """The lab's look on its collection `room` (the lows step's file): every part's material, the CC0 models, the lights
    (collection lab_lights), the world. -> {'materials', 'world', 'lights'}"""
    global BAKE, LIB, PRINTS, SCREEN_K
    BAKE, LIB, PRINTS, SCREEN_K = bake_dir, library, prints_dir, screen
    before = set(bpy.data.materials)
    assign_all(room, panel)
    place_models(room)
    lc = lights(room, sun, panel, sun_el, sun_az)
    w = make_world(world, sun_az, clamp)
    bpy.data.objects['wall_front_unseen'].visible_camera = False    # (the lens looks in through it; it still bounds the room's light)
    mats = sorted(m.name for m in bpy.data.materials if m not in before)
    L.log('lab look', f'{len(mats)} materials')
    return {'materials': mats, 'world': w, 'lights': lc}


def finish(room, sc, res):
    """the probes, over the finished room with its render settings: a volume probe whose box reaches 6 cm past each
    surface of the room (into the walls' and slabs' own thickness: its outer samples fall inside solid and are left out
    by the bake), baked now (its bake is saved with the file), and a sphere probe for the reflections"""
    lc = res['lights']
    vp = bpy.data.objects.new('lab_gi_volume', bpy.data.lightprobes.new('lab_gi_volume', 'VOLUME'))
    vp.location, vp.scale = (0.0, 0.5, 1.4), (4.06, 2.56, 1.46)
    vp.data.resolution_x, vp.data.resolution_y, vp.data.resolution_z = 32, 20, 12
    vp.data.bake_samples, vp.data.surface_bias = 1024, 0.05
    lc.objects.link(vp)
    spp = bpy.data.objects.new('lab_reflection', bpy.data.lightprobes.new('lab_reflection', 'SPHERE'))
    spp.location = (0.6, 0.4, 1.4)
    spp.data.influence_distance = 6.0
    lc.objects.link(spp)
    L.bake_volume_probe(vp, 'lab look')
