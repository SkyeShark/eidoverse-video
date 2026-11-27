"""eidoblend.sets.same_seed.sealed_room.look: the sealed room's materials, its CC0 pieces and its light (Blender).

    from eidoblend.sets.same_seed.sealed_room import look
    look.apply(room_collection, bake_dir, library, tube=14.0, watts=150.0, wallfill=0.05)

What it does, in order:
1. EVERY SURFACE FROM A CC0 PHOTOGRAPHIC SET at its real size (the S table): concrete_block_wall's height and normal for
   the block (8 courses and 5 blocks a tile, mapped to 200 mm courses and 400 mm blocks with a bed joint every 0.2 m),
   Paint004 for the paint film, linoleum_brown for the tile's marbling, PaintedPlaster017 for the ceiling, Metal021 for
   the steel, Metal027 for the powder coat, Metal038 for the zinc, Metal009 for the stainless, Rubber004 for the cove
   base, PaintedMetal014 for the rust. Each set's colour gives its light and shade only (divided by its mean), tinted to
   the room's colours.
2. ONE LAYER STACK PER MATERIAL in the order of what happened to it, each layer from its cause and its geometric signal:
   the finish -> grime where dirt collects (the bake's AO and cavity; the room's corners by their distance) -> wear where
   hands, boots and knocks go (the bake's arris nearness x where they go: the bench's front stretcher worn bare by
   boots, the door's lock edge and kick zone, the frame's jambs at shoulder height) -> dust on what faces up (the shelf,
   the stretchers, the sills, the vent's blades, the cove base's lip) -> stains with their causes (rust bloomed round
   every plate bolt and run down; rust run down the wall from under each sill; old wax yellowed along the walls; a
   hand's grease by the switch and round the door's lite; paler paint where a clock and a notice board hung; the
   ceiling's grey ghost round the light) -> no markings. The condition: a room in an old government building, kept, not
   loved: mopped, repainted over and over, scuffed where things go by; the plates newer than the rest.
3. CC0 MODELS FROM POLY HAVEN, with their own materials at their real size: the workshop stool metal_stool_02 (its seat
   top at 0.445 over (-1.2, 0.8)), the wall camera security_camera_02 in the back-left corner aimed at the bench, one
   twin-tube batten of mounted_fluorescent_lights on the ceiling along x over (0, -0.3).
4. ITS OWN LIGHT ONLY (the world is black): the batten's tubes (emission `tube`), an area light under them (`watts`), a
   shadowless wash up the ceiling, a shadowless bounce from the floor and one from each wall (`wallfill` of the main).
wall_front_unseen stays, hidden from the camera only: it still shuts the room for every other ray.
"""

import math

import bpy
from mathutils import Euler, Vector

from .. import look as L
from ..look import ARRIS_MM, assign, band, box_uv

BAKE = None              # the room's bake folder, set by apply()
LIB = None               # its CC0 library (look.Library), set by apply()
X0, X1, Y0, Y1, HT = -2500.0, 2500.0, -1850.0, 2750.0, 2600.0
SWX, SWZ = 1866.0, 1220.0


class Mat(L.Mat):
    ROUGH_MIN = 0.03


# ----------------------------------------------------------------------------------- the sets (real sizes, m)
S = {'block': ('concrete_block_wall_2k', (2.0, 1.6)), 'paint': ('Paint004_2k', (0.6, 0.6)), 'lino': ('linoleum_brown_2k', (1.2, 1.2)),
     'plaster': ('PaintedPlaster017_2k', (2.0, 1.0)), 'steel': ('Metal021_2k', (1.0, 1.0)), 'powder': ('Metal027_2k', (0.4, 0.4)),
     'zinc': ('Metal038_2k', (0.8, 0.8)), 'stain': ('Metal009_2k', (0.5, 0.5)), 'rubber': ('Rubber004_2k', (0.3, 0.3)),
     'rusty': ('PaintedMetal014_2k', (1.0, 1.0))}
MODELS = (('metal_stool_02', '1k'), ('security_camera_02', '1k'), ('mounted_fluorescent_lights', '1k'))


def sfile(k, key):
    return LIB.tex(S[k][0], key)


def photo_uv(M, k, uvname, keys, loc=(0.0, 0.0, 0.0)):
    """a set's maps through a UV in metres at the set's real size"""
    w, h = S[k][1]
    v = M.mapping(M.uv(uvname), (1.0 / w, 1.0 / h, 1.0), loc=loc)
    return {key: M.tex(sfile(k, key), v, color=(key == 'diff')) for key in keys}


def photo_box(M, k, keys, scale=1.0):
    """a set's maps by a box projection in the object's metres (turned, swept and baked parts: no second UV)"""
    w, h = S[k][1]
    v = M.mapping(M.objm(), (scale / w, scale / w, scale / w))
    return {key: M.tex(sfile(k, key), v, color=(key == 'diff'), box=True) for key in keys}


def baked(M, atlas):
    return L.baked(M, BAKE, atlas)


GREEN_LOW = (0.105, 0.150, 0.132)                                   # the lower band's gloss green-grey
CREAM = (0.52, 0.50, 0.415)                                         # the upper band's cream
CONCRETE = (0.30, 0.295, 0.28)
DUST = (0.32, 0.30, 0.27)
RUST = (0.15, 0.058, 0.022)
RUST_D = (0.07, 0.03, 0.014)


# ------------------------------------------------------------------------------------------------- the shell
def m_wall():
    M = Mat('sealed.wall_painted_block')
    X, Y, Z = M.pos_mm()
    nx, ny, nz = M.nrm()
    P = M.objm()
    side = M.sm(M.m('ABSOLUTE', nx), 0.5, 0.6)                    # 1 on the left and right walls
    U = M.mixf(side, X, Y)
    # the block: its courses 200 mm, its blocks 400 mm, a bed joint at z = 0, 0.2, ...
    blk = photo_uv(M, 'block', 'box_m', ('diff', 'normal', 'displacement', 'rough'), loc=(0.0, 0.07178, 0.0))
    pnt = photo_uv(M, 'paint', 'box_m', ('displacement', 'rough'))
    # paint fills a block's pores: the relief held to a quarter, the joints carried by the height
    M.nmap(blk['normal'].outputs[0], 'box_m', 0.25)
    M.bump(blk['displacement'].outputs[0], 0.0012, 0.2)             # (the joints' hollow, deeper than the normal map carries)
    M.bump(pnt['displacement'].outputs[0], 0.00025, 0.5)            # (the roller's stipple)
    joint = M.sm(M.inv(blk['displacement'].outputs[0]), 0.62, 0.8)
    n_mac, n_mes = M.noise(P, 1.1, 3.0), M.noise(P, 7.0, 3.0)
    n_chip = M.noise(P, 26.0, 2.0, off=(2.0, 5.0, 1.0))
    # 1. THE PAINT: two tones, the line between them cut by hand at 1.4 m
    dado = M.sm(M.add(Z, M.mul(M.sub(M.noise(P, 5.0, 1.0), 0.5), 5.0)), 1397.0, 1403.0)
    paint = M.mixc(dado, GREEN_LOW, CREAM)
    paint = M.value(paint, M.add(1.0, M.mul(M.sub(M.m('DIVIDE', M.lum(blk['diff'].outputs[0]), L.mean_lum(sfile('block', 'diff'))), 1.0), 0.16)))
    paint = M.value(paint, M.add(1.0, M.add(M.mul(M.sub(n_mac, 0.5), 0.10), M.mul(M.sub(n_mes, 0.5), 0.04))))
    rough = M.add(M.mixf(dado, 0.42, 0.58), M.mul(M.sub(pnt['rough'].outputs[0], 0.5), 0.12))   # (semi-gloss below, eggshell above)
    # 2. PALER PAINT WHERE THINGS HUNG: a round clock over the door, a notice board on the right wall (its four screw holes)
    back_w = M.mul(M.inv(side), M.sm(Y, 2600.0, 2700.0))
    right_w = M.mul(side, M.sm(X, 2400.0, 2490.0))
    rc = M.m('SQRT', M.add(M.m('POWER', M.sub(X, 1208.0), 2.0), M.m('POWER', M.sub(Z, 2405.0), 2.0)))
    ghost = M.mul(back_w, M.inv(M.sm(rc, 150.0, 156.0)))
    bx = M.mul(M.inv(M.sm(M.m('ABSOLUTE', M.sub(Y, 650.0)), 296.0, 302.0)), M.inv(M.sm(M.m('ABSOLUTE', M.sub(Z, 1560.0)), 221.0, 227.0)))
    board = M.mul(right_w, bx)
    ghost = M.mx(ghost, board)
    paint = M.value(paint, M.add(1.0, M.mul(ghost, 0.16)))
    hole = 0.0
    for hy, hz, w_ in ((1208.0, 2515.0, back_w),):
        hole = M.mul(w_, M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(X, hy), 2.0), M.m('POWER', M.sub(Z, hz), 2.0))), 2.5, 4.0)))
    for hy, hz in ((370.0, 1350.0), (930.0, 1350.0), (370.0, 1770.0), (930.0, 1770.0)):
        hole = M.mx(hole, M.mul(right_w, M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(Y, hy), 2.0), M.m('POWER', M.sub(Z, hz), 2.0))), 3.0, 4.5))))
    # 3. GRIME, each from its cause: mop splash and scuffs low; grey where a cloth never goes (the room's corners, the
    #    ceiling line); dirt in the joints; a hand's grease by the switch
    low = M.mul(M.inv(M.sm(Z, 30.0, 300.0)), M.add(0.35, M.mul(n_mes, 0.9)))
    dU = M.mn(M.sub(U, M.mixf(side, X0, Y0)), M.sub(M.mixf(side, X1, Y1), U))
    corner = M.mx(M.inv(M.sm(dU, 15.0, 240.0)), M.mul(M.inv(M.sm(M.sub(HT, Z), 10.0, 160.0)), 0.8))
    corner = M.mul(corner, M.add(0.55, M.mul(n_mes, 0.7)))
    switch = M.mul(back_w, M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(X, SWX - 95.0), 2.0), M.m('POWER', M.sub(Z, SWZ), 2.0))), 40.0, 220.0)))
    grime = M.m('MINIMUM', M.add(M.add(M.mul(low, 0.5), M.mul(corner, 0.42)), M.add(M.mul(joint, 0.16), M.mul(switch, 0.3))), 0.85)
    grime = M.mul(grime, M.inv(M.mul(ghost, 0.6)))
    paint = M.value(paint, M.sub(1.0, M.mul(grime, 0.5)))
    paint = M.mixc(hole, paint, (0.02, 0.02, 0.02))
    rough = M.add(rough, M.sub(M.mul(M.add(low, corner), 0.18), M.mul(switch, 0.12)))
    # 4. RUST RUN DOWN FROM UNDER EACH SILL (back wall x -1960..-640; the left wall y -360..960), each run its own length
    left_w = M.sm(nx, 0.5, 0.6)
    under = M.mul(M.add(M.mul(back_w, M.mul(M.sm(X, -1990.0, -1930.0), M.inv(M.sm(X, -670.0, -610.0)))),
                        M.mul(left_w, M.mul(M.sm(Y, -390.0, -330.0), M.inv(M.sm(Y, 930.0, 990.0))))),
                  M.mul(M.inv(M.sm(Z, 935.0, 952.0)), M.sm(Z, 200.0, 900.0)))
    streak = M.noise(P, 1.0, 2.0, stretch=(52.0, 52.0, 1.2))
    reach = M.noise(P, 1.0, 1.0, stretch=(10.0, 10.0, 0.01), off=(1.0, 3.0, 0.0))
    rust = M.mul(M.mul(under, M.sm(streak, 0.52, 0.68)), M.mul(M.add(0.25, M.mul(M.sm(Z, M.lin(reach, 0.3, 0.7, 880.0, 260.0), 950.0), 0.75)), 0.85))
    paint = M.mixc(rust, paint, RUST)
    rough = M.add(rough, M.mul(rust, 0.25))
    # 5. CHIPS to the grey block where things knock a wall (below the shoulder), more beside the door's frame
    near_door = M.mul(back_w, M.mul(M.sm(X, 560.0, 640.0), M.inv(M.sm(X, 1780.0, 1860.0))))
    chip = M.mul(M.sm(n_chip, M.sub(0.80, M.mul(near_door, 0.06)), M.sub(0.815, M.mul(near_door, 0.06))),
                 M.mul(M.sm(n_mes, 0.48, 0.6), M.inv(M.sm(Z, 1250.0, 1700.0))))
    paint = M.mixc(chip, paint, CONCRETE)
    rough = M.mixf(chip, rough, 0.9)
    M.bump(M.mul(chip, -1.0), 0.0004, 1.0)
    return M.done(paint, rough, 0.0)


def m_floor():
    M = Mat('sealed.floor_vinyl_tile')
    X, Y, Z = M.pos_mm()
    P = M.objm()
    # 305 mm tiles, each laid a quarter turn from its neighbours, each from its own part of the sheet
    tu, tv = M.m('DIVIDE', M.add(X, 40.0), 305.0), M.m('DIVIDE', M.add(Y, 110.0), 305.0)
    iu, iv = M.m('FLOOR', tu), M.m('FLOOR', tv)
    fu, fv = M.m('FRACT', tu), M.m('FRACT', tv)
    wn = M.N.new('ShaderNodeTexWhiteNoise')
    wn.noise_dimensions = '3D'
    M.L.new(M.comb(iu, iv, 3.0), wn.inputs['Vector'])
    wcol = M.sep(wn.outputs['Color'])
    parity = M.m('FRACT', M.mul(M.add(iu, iv), 0.5))
    parity = M.mul(parity, 2.0)
    mixv = M.N.new('ShaderNodeMix')
    mixv.data_type = 'VECTOR'
    M.L.new(parity, mixv.inputs[0])
    M.L.new(M.comb(fu, fv), mixv.inputs[4])
    M.L.new(M.comb(fv, fu), mixv.inputs[5])
    local = mixv.outputs[1]
    sheet = M.N.new('ShaderNodeVectorMath')
    sheet.operation = 'MULTIPLY_ADD'
    M.L.new(local, sheet.inputs[0])
    sheet.inputs[1].default_value = (0.305 / 1.2, 0.305 / 1.2, 0.0)
    M.L.new(M.comb(wcol[0], wcol[1]), sheet.inputs[2])
    lino_d = M.tex(sfile('lino', 'diff'), sheet.outputs[0], color=True)
    lino_r = M.tex(sfile('lino', 'rough'), sheet.outputs[0])
    lino_h = M.tex(sfile('lino', 'displacement'), sheet.outputs[0])
    M.bump(lino_h.outputs[0], 0.00015, 0.5)                             # (its height, not its normal map: every other tile is
    #                                                                     turned a quarter, which a tangent-space map would not know)
    base = M.tinted(lino_d, sfile('lino', 'diff'), (0.25, 0.235, 0.20), 0.85)
    base = M.value(base, M.add(1.0, M.mul(M.sub(wn.outputs['Value'], 0.5), 0.18)))     # (each tile from another box)
    # the joints: tight butt joints, a line of dirt
    d = M.mul(M.mn(M.mn(fu, M.inv(fu)), M.mn(fv, M.inv(fv))), 305.0)
    joint = M.inv(M.sm(d, 0.35, 1.4))
    M.bump(M.mul(joint, -1.0), 0.0003, 1.0)
    n_mes = M.noise(P, 12.0, 3.0)

    def blob(cx, cy, r):
        return M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(X, cx), 2.0), M.m('POWER', M.sub(Y, cy), 2.0))), r * 0.3, r))
    # where feet go: the door to the bench, round the bench's front, to the stool
    walk = M.mx(M.mx(blob(0.0, -1450.0, 1100.0), blob(1208.0, 2050.0, 900.0)), M.mx(blob(700.0, 700.0, 950.0), blob(-1100.0, 350.0, 750.0)))
    walk = M.mul(walk, M.add(0.5, M.mul(n_mes, 0.8)))
    dW = M.mn(M.mn(M.sub(X, X0), M.sub(X1, X)), M.mn(M.sub(Y, Y0), M.sub(Y1, Y)))
    wax = M.inv(M.sm(dW, 8.0, 45.0))                                    # old wax built up and yellowed where the mop stops
    under_bench = M.mul(M.mul(M.inv(M.sm(M.m('ABSOLUTE', X), 640.0, 720.0)), M.inv(M.sm(M.m('ABSOLUTE', M.add(Y, 750.0)), 260.0, 310.0))), 1.0)
    scuff = M.mul(M.sm(M.noise(P, 1.0, 2.0, stretch=(7.0, 60.0, 1.0)), 0.66, 0.69), M.mul(walk, 0.9))
    col = M.value(base, M.sub(1.0, M.add(M.mul(joint, 0.45), M.mul(walk, 0.10))))
    col = M.mixc(M.mul(wax, 0.8), col, (0.075, 0.058, 0.035))
    col = M.mixc(M.mul(under_bench, M.add(0.25, M.mul(n_mes, 0.3))), col, DUST)
    col = M.mixc(scuff, col, (0.03, 0.03, 0.03))
    rough = M.add(M.add(0.26, M.mul(M.sub(lino_r.outputs[0], 0.5), 0.2)), M.add(M.mul(walk, 0.26), M.add(M.mul(joint, 0.3), M.mul(wax, 0.15))))
    rough = M.add(rough, M.mul(under_bench, 0.3))
    return M.done(col, rough, 0.0)


def m_ceiling():
    M = Mat('sealed.ceiling_painted_concrete')
    X, Y, Z = M.pos_mm()
    P = M.objm()
    pl = photo_uv(M, 'plaster', 'box_m', ('diff', 'normal', 'rough'))
    M.nmap(pl['normal'].outputs[0], 'box_m', 0.5)
    col = M.tinted(pl['diff'], sfile('plaster', 'diff'), (0.50, 0.49, 0.455), 0.5)
    # the planks' joints every 1.2 m, an old leak's ring, and the grey ghost the light's warm air lays round it
    fx = M.m('FRACT', M.m('DIVIDE', M.add(X, 300.0), 1200.0))
    groove = M.inv(M.sm(M.mul(M.mn(fx, M.inv(fx)), 1200.0), 3.0, 10.0))
    M.bump(M.mul(groove, -1.0), 0.004, 0.5)
    n_mac = M.noise(P, 0.9, 3.0, off=(1.0, 2.0, 0.0))
    stain = M.mx(M.mul(M.sm(n_mac, 0.63, 0.7), M.inv(M.sm(n_mac, 0.72, 0.8))), M.mul(M.sm(n_mac, 0.66, 0.74), 0.35))
    ghost = M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.m('DIVIDE', X, 2.2), 2.0), M.m('POWER', M.add(Y, 300.0), 2.0))), 60.0, 380.0))
    wallline = M.inv(M.sm(M.mn(M.mn(M.sub(X, X0), M.sub(X1, X)), M.mn(M.sub(Y, Y0), M.sub(Y1, Y))), 10.0, 250.0))
    col = M.value(col, M.sub(1.0, M.add(M.mul(groove, 0.3), M.add(M.mul(ghost, 0.25), M.mul(wallline, 0.25)))))
    col = M.mixc(M.mul(stain, 0.45), col, (0.33, 0.25, 0.14))
    rough = M.add(0.85, M.mul(M.sub(pl['rough'].outputs[0], 0.5), 0.1))
    return M.done(col, rough, 0.0)


def m_rubber_base():
    M = Mat('sealed.cove_base_rubber')
    X, Y, Z = M.pos_mm()
    P = M.objm()
    nzw = M.wnz()[2]
    rb = photo_box(M, 'rubber', ('diff', 'rough', 'displacement'))
    col = M.tinted(rb['diff'], sfile('rubber', 'diff'), (0.020, 0.020, 0.022), 0.4)
    M.bump(rb['displacement'].outputs[0], 0.0003, 0.6)
    up = M.sm(nzw, 0.3, 0.7)                                            # dust on its lip
    mop = M.mul(M.inv(M.sm(Z, 3.0, 22.0)), M.add(0.3, M.mul(M.noise(P, 9.0, 2.0), 0.6)))   # the mop's grey film at its toe
    scuff = M.mul(M.sm(M.noise(P, 3.0, 2.0, stretch=(20.0, 20.0, 2.0)), 0.7, 0.74), 0.8)
    col = M.mixc(M.mul(up, 0.7), col, DUST)
    col = M.mixc(M.mul(mop, 0.5), col, (0.16, 0.155, 0.15))
    col = M.mixc(scuff, col, (0.11, 0.11, 0.105))
    rough = M.add(M.add(0.52, M.mul(M.sub(rb['rough'].outputs[0], 0.5), 0.2)), M.add(M.mul(up, 0.3), M.mul(mop, 0.2)))
    return M.done(col, rough, 0.0)


# ------------------------------------------------------------------------------------------- the baked parts
def enamel(name, atlas, rgb, r0=0.34, wear=1.0, hands=None, kick=False, drips=False, primer=(0.24, 0.235, 0.22), dust=0.8, k=0.07):
    """painted steel: the enamel (Paint004's film) -> grime (AO, cavity) -> chips at the arrises to primer, then steel,
    where hands and knocks go -> a hand's grease -> kicks -> dust on what faces up"""
    M = Mat(name)
    X, Y, Z = M.pos_mm()
    P = M.objm()
    ao, cav, fine, arr, crn = baked(M, atlas)
    pnt = photo_box(M, 'paint', ('diff', 'displacement', 'rough'))
    stl = photo_box(M, 'steel', ('diff', 'rough'))
    n_mes, n_chip = M.noise(P, 9.0, 3.0), M.noise(P, 60.0, 2.0, off=(3.0, 1.0, 2.0))
    nzw = M.wnz()[2]
    col = M.tinted(pnt['diff'], sfile('paint', 'diff'), rgb, k)
    col = M.value(col, M.add(1.0, M.mul(M.sub(n_mes, 0.5), 0.06)))
    rough = M.add(r0, M.mul(M.sub(pnt['rough'].outputs[0], 0.5), 0.10))
    grime = M.mn(M.add(M.mul(M.inv(ao), 0.55), M.mul(M.inv(cav), 0.6)), 0.8)
    grime = M.mul(grime, M.add(0.6, M.mul(n_mes, 0.6)))
    col = M.value(col, M.sub(1.0, M.mul(grime, 0.45)))
    rough = M.add(rough, M.mul(grime, 0.2))
    # where the knocks are: low (boots, carts) and at hand height; chips are few and come where the knocks are: a
    # patchy gate, then a narrow band
    where = M.mx(M.inv(M.sm(Z, 250.0, 500.0)), M.mul(M.sm(Z, 850.0, 1000.0), M.inv(M.sm(Z, 1500.0, 1700.0))))
    where = M.mul(M.add(0.1, M.mul(where, 0.9)), M.sm(M.noise(P, 4.0, 2.0, off=(7.0, 2.0, 5.0)), 0.5, 0.62))
    if wear > 0.0:
        e_pr = M.mul(band(M, arr, 2.2 * wear, ARRIS_MM, n_chip, 0.25), where)
        e_st = M.mul(band(M, arr, 0.9 * wear, ARRIS_MM, n_chip, 0.25), where)
    else:
        e_pr = e_st = 0.0
    col = M.mixc(e_pr, col, primer)
    col = M.mixc(e_st, col, M.tinted(stl['diff'], sfile('steel', 'diff'), (0.20, 0.20, 0.21), 0.5))
    metal = M.mul(e_st, 1.0)
    rough = M.mixf(e_pr, rough, 0.62)
    rough = M.mixf(e_st, rough, M.add(0.30, M.mul(stl['rough'].outputs[0], 0.25)))
    if hands is not None:                                               # a hand's grease: darker, glossier
        hx0, hx1, hz0, hz1 = hands
        hz = M.mul(M.mul(M.sm(X, hx0, hx0 + 80.0), M.inv(M.sm(X, hx1 - 80.0, hx1))), M.mul(M.sm(Z, hz0, hz0 + 120.0), M.inv(M.sm(Z, hz1 - 120.0, hz1))))
        hz = M.mul(hz, M.add(0.3, M.mul(M.noise(P, 14.0, 2.0), 0.8)))
        col = M.value(col, M.sub(1.0, M.mul(hz, 0.32)))
        rough = M.sub(rough, M.mul(hz, 0.15))
    if kick:                                                            # scuffs where feet and carts meet it
        kz = M.mul(M.inv(M.sm(Z, 120.0, 420.0)), M.sm(M.noise(P, 4.0, 2.0, stretch=(1.0, 1.0, 0.25)), 0.58, 0.66))
        col = M.mixc(M.mul(kz, 0.75), col, (0.025, 0.025, 0.025))
        rough = M.add(rough, M.mul(kz, 0.15))
    if drips:                                                           # the last coat's runs down the jambs
        dr = M.mul(M.sm(M.noise(P, 1.0, 1.0, stretch=(140.0, 140.0, 1.5)), 0.78, 0.8), M.sm(Z, 300.0, 600.0))
        M.bump(M.mul(dr, 1.0), 0.0004, 0.6)
        rough = M.sub(rough, M.mul(dr, 0.08))
    up = M.mul(M.sm(nzw, 0.55, 0.85), M.add(0.4, M.mul(M.noise(P, 20.0, 2.0), 0.8)))
    col = M.mixc(M.mul(up, 0.8 * dust), col, DUST)
    rough = M.add(rough, M.mul(up, 0.3 * dust))
    M.bump(M.mul(pnt['displacement'].outputs[0], 1.0), 0.00015, 0.7)  # (orange peel)
    M.bump(M.mul(e_pr, -1.0), 0.00025, 1.0)                             # (the paint's edge where it chipped)
    return M.done(col, rough, metal)


def bare_metal(name, atlas, kind, rgb, r0, dust=0.6, rust=0.0, scuffs=0.0):
    """bare metal: zinc (Metal038's spangle), stainless (Metal009's brushing) or steel (Metal021): metallic; grime in its
    recesses; rust where water sits (cavity, low); scuffs; dust on what faces up"""
    M = Mat(name)
    X, Y, Z = M.pos_mm()
    P = M.objm()
    ao, cav, fine, arr, crn = baked(M, atlas) if atlas else (1.0, 1.0, 0.5, 0.0, 0.0)
    ph = photo_box(M, kind, ('diff', 'rough'))
    nzw = M.wnz()[2]
    col = M.tinted(ph['diff'], sfile(kind, 'diff'), rgb, 0.6)
    rough = M.add(r0, M.mul(M.sub(ph['rough'].outputs[0], 0.5), 0.3))
    if atlas:
        grime = M.mn(M.add(M.mul(M.inv(ao), 0.6), M.mul(M.inv(cav), 0.7)), 0.85)
        col = M.value(col, M.sub(1.0, M.mul(grime, 0.55)))
        rough = M.add(rough, M.mul(grime, 0.25))
        if rust:
            rs = M.mul(M.sm(M.add(M.inv(cav), M.mul(M.sub(M.noise(P, 40.0, 2.0), 0.5), 0.6)), 0.35, 0.55), rust)
            col = M.mixc(rs, col, RUST)
            rough = M.mixf(rs, rough, 0.85)
    if scuffs:
        sc_ = M.mul(M.sm(M.noise(P, 2.0, 2.0, stretch=(30.0, 30.0, 3.0)), 0.68, 0.72), scuffs)
        col = M.mixc(sc_, col, (0.02, 0.02, 0.02))
    up = M.mul(M.sm(nzw, 0.55, 0.85), M.add(0.4, M.mul(M.noise(P, 20.0, 2.0), 0.8)))
    col = M.mixc(M.mul(up, dust), col, DUST)
    metal = M.inv(M.mul(up, dust))
    rough = M.add(rough, M.mul(up, 0.35 * dust))
    if atlas and isinstance(rust, float) and rust:
        metal = M.mul(metal, M.inv(rs))
    return M.done(col, rough, metal)


def m_bench_frame():
    """the bench's frame and shelf: a green-grey enamel on 40 x 40 tube: its corners chipped to steel low down where
    boots go, the front stretcher's top worn bare by the boots that rested on it, the welds' ripples holding grime,
    rust at the feet where the mop water stands, dust thick on the shelf and on every stretcher's top"""
    M = Mat('sealed.bench_frame_enamel')
    X, Y, Z = M.pos_mm()
    P = M.objm()
    ao, cav, fine, arr, crn = baked(M, 'bench')
    pw = photo_box(M, 'powder', ('diff', 'displacement', 'rough'))
    stl = photo_box(M, 'steel', ('diff', 'rough'))
    n_mes, n_chip = M.noise(P, 9.0, 3.0), M.noise(P, 70.0, 2.0, off=(3.0, 1.0, 2.0))
    nzw = M.wnz()[2]
    col = M.tinted(pw['diff'], sfile('powder', 'diff'), (0.085, 0.130, 0.112), 0.25)
    rough = M.add(0.36, M.mul(M.sub(pw['rough'].outputs[0], 0.5), 0.2))
    grime = M.mn(M.add(M.mul(M.inv(ao), 0.5), M.mul(M.inv(cav), 0.75)), 0.85)
    col = M.value(col, M.sub(1.0, M.mul(grime, 0.5)))
    rough = M.add(rough, M.mul(grime, 0.2))
    steel = M.tinted(stl['diff'], sfile('steel', 'diff'), (0.21, 0.21, 0.22), 0.6)
    boots = M.add(0.15, M.mul(M.inv(M.sm(Z, 260.0, 520.0)), 0.85))
    boots = M.mul(boots, M.sm(M.noise(P, 5.0, 2.0, off=(4.0, 1.0, 3.0)), 0.48, 0.6))   # (chips along the shelf's edge, dashed)
    e_st = M.mul(band(M, arr, 1.6, ARRIS_MM, n_chip, 0.3), boots)
    # the front stretcher's top (y -1022 .. -982, z 200): boots rested on it
    rest = M.mul(M.mul(M.sm(nzw, 0.7, 0.9), M.mul(M.sm(Z, 190.0, 196.0), M.inv(M.sm(Z, 204.0, 210.0)))),
                 M.mul(M.inv(M.sm(Y, -975.0, -965.0)), M.inv(M.sm(M.m('ABSOLUTE', X), 380.0, 560.0))))
    rest = M.mul(rest, M.sm(M.add(n_mes, M.mul(M.sub(n_chip, 0.5), 0.5)), 0.38, 0.5))
    bare = M.mx(e_st, rest)
    col = M.mixc(bare, col, steel)
    rough = M.mixf(bare, rough, M.add(0.28, M.mul(stl['rough'].outputs[0], 0.25)))
    feet = M.mul(M.inv(M.sm(Z, 30.0, 90.0)), M.sm(M.add(M.inv(cav), M.mul(M.sub(M.noise(P, 30.0, 2.0), 0.5), 0.7)), 0.3, 0.55))
    col = M.mixc(feet, col, RUST)
    rough = M.mixf(feet, rough, 0.85)
    up = M.mul(M.sm(nzw, 0.6, 0.85), M.add(0.45, M.mul(M.noise(P, 18.0, 2.0), 0.7)))
    shelf = M.mul(M.sm(Z, 195.0, 200.0), M.inv(M.sm(Z, 205.0, 215.0)))
    up = M.mx(M.mul(up, M.inv(rest)), M.mul(shelf, M.mul(M.sm(nzw, 0.8, 0.95), M.add(0.55, M.mul(M.noise(P, 6.0, 3.0), 0.6)))))
    col = M.mixc(M.mul(up, 0.85), col, DUST)
    rough = M.add(rough, M.mul(up, 0.35))
    metal = M.mul(bare, M.inv(up))
    M.bump(M.mul(pw['displacement'].outputs[0], 1.0), 0.0002, 0.6)
    M.bump(M.mul(bare, -1.0), 0.0002, 1.0)
    return M.done(col, rough, metal)


def m_bench_top():
    """the top: bare 2.5 mm sheet, its mill scale worn: polished where hands and things slide (the middle, the front
    edge), the set's own scratches and pits for its wear, a few rust spots where water stood, an old oil ring, its far
    corners dusty, the return's underside rusting"""
    M = Mat('sealed.bench_top_steel')
    X, Y, Z = M.pos_mm()
    P = M.objm()
    ao, cav, fine, arr, crn = baked(M, 'bench')
    stl = photo_box(M, 'steel', ('diff', 'rough', 'displacement'))
    nzw = M.wnz()[2]
    n_mes = M.noise(P, 6.0, 3.0)
    col = M.tinted(stl['diff'], sfile('steel', 'diff'), (0.15, 0.155, 0.165), 0.45)
    rough = M.add(0.42, M.mul(M.sub(stl['rough'].outputs[0], 0.5), 0.35))
    face = M.sm(nzw, 0.9, 0.97)
    # polish: the middle of the face (along x) and the front edge where hands go; a sheen (roughness), barely paler
    mid = M.mul(face, M.mul(M.inv(M.sm(M.m('ABSOLUTE', X), 350.0, 650.0)), M.inv(M.sm(M.m('ABSOLUTE', M.add(Y, 760.0)), 120.0, 290.0))))
    edge = M.mul(band(M, arr, 6.0, ARRIS_MM, M.noise(P, 30.0, 2.0), 0.3), M.inv(M.sm(Y, -1000.0, -900.0)))
    pol = M.mx(M.mul(mid, M.add(0.4, M.mul(n_mes, 0.7))), edge)
    col = M.value(col, M.add(1.0, M.mul(pol, 0.2)))
    rough = M.sub(rough, M.mul(pol, 0.16))
    # rust spots where water stood; an oil ring where a can stood; the return's underside rusting
    spots = M.mul(M.sm(M.noise(P, 14.0, 3.0, off=(5.0, 2.0, 1.0)), 0.70, 0.76), M.inv(mid))
    ring_r = M.m('SQRT', M.add(M.m('POWER', M.sub(X, -480.0), 2.0), M.m('POWER', M.sub(Y, -600.0), 2.0)))
    ring = M.mul(face, M.mul(M.sm(ring_r, 33.0, 36.0), M.inv(M.sm(ring_r, 39.0, 43.0))))
    ring = M.mx(ring, M.mul(face, M.mul(M.inv(M.sm(ring_r, 0.0, 38.0)), 0.25)))
    under = M.mul(M.sm(M.inv(nzw), 1.3, 1.9), M.sm(M.noise(P, 20.0, 2.0), 0.45, 0.6))
    rs = M.mx(spots, under)
    col = M.mixc(rs, col, RUST)
    rough = M.mixf(rs, rough, 0.85)
    col = M.mixc(M.mul(ring, 0.8), col, (0.02, 0.018, 0.015))
    rough = M.sub(rough, M.mul(ring, 0.1))
    grime = M.mn(M.add(M.mul(M.inv(ao), 0.5), M.mul(M.inv(cav), 0.6)), 0.8)
    col = M.value(col, M.sub(1.0, M.mul(grime, 0.5)))
    corner_dust = M.mul(face, M.mul(M.sm(M.m('ABSOLUTE', X), 520.0, 690.0), M.sm(Y, -560.0, -460.0)))
    corner_dust = M.mul(corner_dust, M.add(0.3, M.mul(M.noise(P, 25.0, 2.0), 0.7)))
    col = M.mixc(M.mul(corner_dust, 0.6), col, DUST)
    metal = M.inv(M.mx(M.mul(corner_dust, 0.6), M.mul(rs, 0.9)))
    rough = M.add(rough, M.mul(corner_dust, 0.3))
    M.bump(M.mul(stl['displacement'].outputs[0], 1.0), 0.0002, 0.4)
    return M.done(col, rough, metal)


def m_plate():
    """the plates over the windows: 6 mm steel, red oxide brushed on after they were bolted up (newer than the rest of
    the room), rust bloomed round every bolt and run down below it, the paint worn to steel at the arrises"""
    M = Mat('sealed.plate_red_oxide')
    X, Y, Z = M.pos_mm()
    P = M.objm()
    nx, ny, nz = M.nrm()
    ao, cav, fine, arr, crn = baked(M, 'plates')
    pnt = photo_box(M, 'paint', ('displacement', 'rough'))
    rus = photo_box(M, 'rusty', ('diff',))
    stl = photo_box(M, 'steel', ('diff',))
    side = M.sm(M.m('ABSOLUTE', nx), 0.5, 0.6)
    a = M.mixf(side, X, Y)                                              # along the plate (back: x; left: y)
    a0 = M.mixf(side, -1930.0, -330.0)                                  # its first bolt column
    sp, zb, zt, sv = 252.0, 1042.0, 2030.0, 247.0                       # (room.py sealed_window(): 5 bolts along, 4 up)
    da = M.mul(M.m('ABSOLUTE', M.sub(M.m('FRACT', M.add(M.m('DIVIDE', M.sub(a, a0), sp), 0.5)), 0.5)), sp)
    dz = M.mn(M.m('ABSOLUTE', M.sub(Z, zb)), M.m('ABSOLUTE', M.sub(Z, zt)))
    d_row = M.m('SQRT', M.add(M.m('POWER', da, 2.0), M.m('POWER', dz, 2.0)))
    dzc = M.mul(M.m('ABSOLUTE', M.sub(M.m('FRACT', M.add(M.m('DIVIDE', M.sub(Z, zb), sv), 0.5)), 0.5)), sv)
    dac = M.mn(M.m('ABSOLUTE', M.sub(a, a0)), M.m('ABSOLUTE', M.sub(a, M.add(a0, 5.0 * sp))))
    d_col = M.m('SQRT', M.add(M.m('POWER', dac, 2.0), M.m('POWER', dzc, 2.0)))
    d = M.mn(d_row, d_col)
    nb = M.noise(P, 30.0, 2.0)
    bloom = M.inv(M.sm(d, M.add(14.0, M.mul(nb, 10.0)), M.add(26.0, M.mul(nb, 26.0))))
    below = M.mul(M.inv(M.sm(da, 2.0, M.add(4.0, M.mul(nb, 5.0)))), M.mul(M.sm(M.sub(zt, Z), 15.0, 25.0), M.inv(M.sm(M.sub(zt, Z), 60.0, M.add(90.0, M.mul(M.noise(P, 3.0, 1.0), 260.0))))))
    below_c = M.mul(M.inv(M.sm(dac, 2.0, M.add(4.0, M.mul(nb, 5.0)))), M.inv(M.sm(M.mul(M.inv(M.m('FRACT', M.m('DIVIDE', M.sub(Z, zb), sv))), sv), 20.0, M.add(60.0, M.mul(nb, 160.0)))))
    run = M.mx(below, M.mul(below_c, M.sm(Z, zb, zb + 5.0)))
    run = M.mul(run, M.sm(M.noise(P, 1.0, 2.0, stretch=(60.0, 60.0, 1.0)), 0.35, 0.5))
    rust = M.mx(bloom, M.mul(run, 0.95))
    # red oxide primer brushed on: dark and dull, thin where the brush ran dry, its strokes along the plate
    pdf = photo_box(M, 'paint', ('diff',))
    col = M.tinted(pdf['diff'], sfile('paint', 'diff'), (0.115, 0.036, 0.022), 0.3)
    stroke = M.noise(P, 3.0, 3.0, stretch=(1.0, 1.0, 14.0))
    col = M.value(col, M.add(1.0, M.add(M.mul(M.sub(stroke, 0.5), 0.35), M.mul(M.sub(M.noise(P, 1.5, 2.0), 0.5), 0.2))))
    thin = M.sm(M.noise(P, 6.0, 3.0, off=(2.0, 2.0, 2.0)), 0.62, 0.72)
    col = M.mixc(M.mul(thin, 0.6), col, M.tinted(stl['diff'], sfile('steel', 'diff'), (0.09, 0.07, 0.06), 0.5))
    col = M.mixc(rust, col, M.tinted(rus['diff'], sfile('rusty', 'diff'), (0.21, 0.085, 0.03), 0.8))
    rough = M.add(0.66, M.mul(M.sub(pnt['rough'].outputs[0], 0.5), 0.15))
    rough = M.mixf(rust, rough, 0.86)
    e_st = band(M, arr, 1.5, ARRIS_MM, M.noise(P, 50.0, 2.0), 0.5)
    col = M.mixc(e_st, col, M.tinted(stl['diff'], sfile('steel', 'diff'), (0.16, 0.15, 0.15), 0.6))
    rough = M.mixf(e_st, rough, 0.45)
    grime = M.mn(M.add(M.mul(M.inv(ao), 0.6), M.mul(M.inv(cav), 0.6)), 0.8)
    col = M.value(col, M.sub(1.0, M.mul(grime, 0.45)))
    up = M.sm(M.wnz()[2], 0.6, 0.85)
    col = M.mixc(M.mul(up, 0.7), col, DUST)
    M.bump(M.mul(pnt['displacement'].outputs[0], 1.0), 0.0003, 0.7)
    M.bump(M.mul(bloom, 0.6), 0.0004, 1.0)
    return M.done(col, rough, M.mul(e_st, M.inv(rust)))


def m_sill():
    """the old sills: precast, painted with the wall above, their nose worn to grey concrete, dust and grit on top,
    rust run onto them from the plates above"""
    M = Mat('sealed.sill_painted_concrete')
    X, Y, Z = M.pos_mm()
    P = M.objm()
    ao, cav, fine, arr, crn = baked(M, 'plates')
    pnt = photo_box(M, 'paint', ('diff', 'displacement'))
    nzw = M.wnz()[2]
    col = M.tinted(pnt['diff'], sfile('paint', 'diff'), CREAM, 0.06)
    nose = M.mul(band(M, arr, 2.0, ARRIS_MM, M.noise(P, 40.0, 2.0), 0.25), M.sm(M.noise(P, 5.0, 2.0, off=(1.0, 4.0, 2.0)), 0.45, 0.6))
    col = M.mixc(nose, col, CONCRETE)
    up = M.mul(M.sm(nzw, 0.6, 0.85), M.add(0.5, M.mul(M.noise(P, 16.0, 3.0), 0.6)))
    grit = M.mul(up, M.sm(M.noise(P, 220.0, 1.0), 0.62, 0.7))
    rs = M.mul(M.sm(M.noise(P, 1.0, 2.0, stretch=(50.0, 50.0, 1.0)), 0.55, 0.7), M.mul(up, 0.7))
    col = M.mixc(rs, col, RUST)
    col = M.mixc(M.mul(up, 0.75), col, DUST)
    col = M.mixc(grit, col, (0.05, 0.045, 0.04))
    grime = M.mn(M.add(M.mul(M.inv(ao), 0.6), M.mul(M.inv(cav), 0.5)), 0.8)
    col = M.value(col, M.sub(1.0, M.mul(grime, 0.45)))
    rough = M.add(0.5, M.add(M.mul(up, 0.35), M.mul(nose, 0.3)))
    M.bump(M.mul(pnt['displacement'].outputs[0], 1.0), 0.0003, 0.6)
    return M.done(col, rough, 0.0)


def m_bolts():
    """the anchor bolts: zinc-plated, the primer brushed over most heads after they were tightened, rust in their
    recesses"""
    M = Mat('sealed.bolts_zinc_primed')
    P = M.objm()
    ao, cav, fine, arr, crn = baked(M, 'plates')
    zn = photo_box(M, 'zinc', ('diff', 'rough'), scale=3.0)
    col = M.tinted(zn['diff'], sfile('zinc', 'diff'), (0.42, 0.43, 0.42), 0.5)
    primed = M.sm(M.noise(P, 18.0, 2.0), 0.42, 0.5)
    worn = band(M, arr, 0.8, ARRIS_MM, M.noise(P, 90.0, 2.0), 0.5)
    primed = M.mul(primed, M.inv(worn))
    col = M.mixc(primed, col, (0.18, 0.058, 0.038))
    rs = M.sm(M.add(M.inv(cav), M.mul(M.sub(M.noise(P, 60.0, 2.0), 0.5), 0.6)), 0.3, 0.5)
    col = M.mixc(rs, col, RUST)
    grime = M.mn(M.add(M.mul(M.inv(ao), 0.6), M.mul(M.inv(cav), 0.6)), 0.8)
    col = M.value(col, M.sub(1.0, M.mul(grime, 0.4)))
    rough = M.mixf(primed, M.add(0.45, M.mul(M.sub(zn['rough'].outputs[0], 0.5), 0.3)), 0.66)
    rough = M.mixf(rs, rough, 0.85)
    return M.done(col, rough, M.mul(M.inv(primed), M.inv(rs)))


def m_plastic(name, atlas, rgb, r0=0.4, finger=False):
    M = Mat(name)
    P = M.objm()
    ao, cav, fine, arr, crn = baked(M, atlas)
    col = M.rgb(rgb)
    grime = M.mn(M.add(M.mul(M.inv(ao), 0.6), M.mul(M.inv(cav), 0.6)), 0.8)
    col = M.value(col, M.sub(1.0, M.mul(grime, 0.45)))
    rough = M.add(r0, M.mul(grime, 0.2))
    if finger:
        col = M.value(col, M.sub(1.0, M.mul(M.sm(M.noise(P, 30.0, 2.0), 0.45, 0.7), 0.2)))
    return M.done(col, rough, 0.0)


def m_dark(name, rgb, r):
    M = Mat(name)
    return M.done(M.rgb(rgb), r, 0.0)


def m_conduit():
    """EMT conduit: galvanised (Metal038's spangle), box-projected; dust on its top; grime"""
    M = Mat('sealed.conduit_galvanised')
    P = M.objm()
    zn = photo_box(M, 'zinc', ('diff', 'rough', 'displacement'), scale=1.5)
    nzw = M.wnz()[2]
    col = M.tinted(zn['diff'], sfile('zinc', 'diff'), (0.40, 0.41, 0.40), 0.55)
    up = M.mul(M.sm(nzw, 0.4, 0.8), M.add(0.4, M.mul(M.noise(P, 12.0, 2.0), 0.7)))
    col = M.value(col, M.add(1.0, M.mul(M.sub(M.noise(P, 3.0, 2.0), 0.5), 0.2)))
    col = M.mixc(M.mul(up, 0.8), col, DUST)
    rough = M.add(M.add(0.42, M.mul(M.sub(zn['rough'].outputs[0], 0.5), 0.3)), M.mul(up, 0.35))
    M.bump(M.mul(zn['displacement'].outputs[0], 1.0), 0.0001, 0.5)
    return M.done(col, rough, M.inv(M.mul(up, 0.8)))


LX1 = 1716.0 - 53.5                                                 # the door leaf's lock edge (room.py)


def material_for(o, mat):
    """the material of one part (by its name; a baked low by its part's name)"""
    n = o.name
    base = n[:-4] if n.endswith('_low') else n
    if base.startswith('wall_'):
        box_uv(o, world=True)
        return mat('wall', m_wall)
    if base == 'room_floor':
        box_uv(o, world=True)
        return mat('floor', m_floor)
    if base == 'room_ceiling':
        box_uv(o, world=True)
        return mat('ceiling', m_ceiling)
    if base.startswith('cove_base'):
        return mat('rubber', m_rubber_base)
    if base in ('door_backing', 'vent_duct_dark'):
        return mat('dark', lambda: m_dark('sealed.dark', (0.004, 0.004, 0.004), 0.9))
    if base == 'door_lite_glass':
        return mat('glass', lambda: m_dark('sealed.glass_dark', (0.006, 0.007, 0.008), 0.06))
    if base == 'door_leaf':
        return mat('door', lambda: enamel('sealed.door_enamel', 'door', (0.105, 0.125, 0.135), 0.34, 0.9, hands=(LX1 - 420.0, LX1, 850.0, 1750.0), kick=True))
    if base == 'door_frame':
        return mat('frame', lambda: enamel('sealed.frame_enamel', 'door', (0.095, 0.112, 0.122), 0.33, 0.9, kick=True, drips=True))
    if base == 'door_lite_rim':
        return mat('rim', lambda: enamel('sealed.lite_rim_enamel', 'door', (0.10, 0.12, 0.13), 0.33, 0.0, dust=0.6))
    if base in ('door_kick_plate', 'door_lock_blank', 'door_screws', 'door_closer_arm', 'door_closer_forearm', 'door_closer_elbow',
                'door_closer_shoe', 'door_closer_shoe_pin', 'door_closer_pinion'):
        return mat('stainless', lambda: bare_metal('sealed.stainless_brushed', 'door', 'stain', (0.55, 0.55, 0.54), 0.36, dust=0.3, scuffs=0.7))
    if base == 'door_closer_body':
        return mat('closer', lambda: enamel('sealed.closer_silver_paint', 'door', (0.34, 0.34, 0.335), 0.38, 0.6, primer=(0.5, 0.5, 0.5), dust=1.0, k=0.04))
    if base == 'bench_top':
        return mat('bench_top', m_bench_top)
    if base.startswith(('bench_foot_pad', 'bench_foot_nut', 'bench_foot_jam', 'bench_foot_stem')):
        return mat('bench_zinc', lambda: bare_metal('sealed.bench_feet_zinc', 'bench', 'zinc', (0.36, 0.37, 0.36), 0.45, dust=0.5, rust=0.8))
    if base.startswith('bench_foot_rubber'):
        return mat('bench_rubber', lambda: m_plastic('sealed.bench_feet_rubber', 'bench', (0.018, 0.018, 0.018), 0.7))
    if base.startswith('bench_'):
        return mat('bench_frame', m_bench_frame)
    if base.endswith('_plate') and base.startswith('window_'):
        return mat('plate', m_plate)
    if base.endswith('_sill'):
        return mat('sill', m_sill)
    if base.endswith('_bolts'):
        return mat('bolts', m_bolts)
    if base.startswith(('vent_frame', 'vent_blades')):
        return mat('vent', lambda: enamel('sealed.vent_enamel_yellowed', 'fixtures', (0.58, 0.565, 0.50), 0.4, 0.5, dust=1.4, primer=(0.4, 0.4, 0.38), k=0.04))
    if base in ('switch_boss', 'switch_toggle'):
        return mat('ivory', lambda: m_plastic('sealed.switch_ivory', 'fixtures', (0.55, 0.52, 0.44), 0.35, finger=True))
    if base == 'switch_cover':
        return mat('stainless_fx', lambda: bare_metal('sealed.switch_cover_stainless', 'fixtures', 'stain', (0.55, 0.55, 0.54), 0.33, dust=0.4))
    if base.startswith('conduit_') and not base.startswith('conduit_straps'):
        return mat('conduit', m_conduit)
    if o.get('atlas') == 'fixtures':
        return mat('zinc_fx', lambda: bare_metal('sealed.fixtures_galvanised', 'fixtures', 'zinc', (0.40, 0.41, 0.40), 0.45, dust=0.8, rust=0.3))
    return mat('conduit', m_conduit)


# ------------------------------------------------------------------------------------------ the CC0 models
def place_stool(room, seat=0.445, at=(-1.2, 0.8), yaw_deg=17.0):
    """metal_stool_02 scaled so its seat top stands at `seat` over `at` (the seated performance sits there)"""
    stool = L.import_gltf(LIB.model('metal_stool_02'), room)
    root = bpy.data.objects.new('cc0_metal_stool_02', None)
    room.objects.link(root)
    for o in stool:
        if o.parent is None:
            o.parent = root
    lo, hi = L.world_bbox(stool)
    k = seat / (hi.z - lo.z)
    root.scale = (k,) * 3
    root.rotation_euler = (0.0, 0.0, math.radians(yaw_deg))
    root.location = (at[0], at[1], 0.0)
    lo, hi = L.world_bbox(stool)
    L.log('sealed look', f'stool: scale {k:.4f}, seat top {hi.z:.4f}')
    return root


def place_camera(room, at=(X0 / 1000.0, 2.45, 2.30), aim_at=(0.0, -0.75, 0.9)):
    """security_camera_02 on the left wall by the back corner, its body turned to `aim_at` and tipped down"""
    objs = L.import_gltf(LIB.model('security_camera_02'), room)
    root = bpy.data.objects.new('cc0_security_camera_02', None)
    room.objects.link(root)
    body = next(o for o in objs if o.name.startswith('security_camera_02') and 'mount' not in o.name and o.type == 'MESH')
    for o in objs:
        if o.parent is None:
            o.parent = root
    root.location = at
    root.rotation_euler = (0.0, 0.0, math.radians(90.0))
    aim = Vector(aim_at) - Vector((at[0] + 0.15, at[1], at[2] + 0.03))
    yaw = math.degrees(math.atan2(aim.y, aim.x))                        # (from +x, the way the mount faces)
    pitch = math.degrees(math.atan2(-aim.z, aim.xy.length))
    body.rotation_euler = Euler((math.radians(pitch), 0.0, math.radians(yaw)), 'XYZ')
    return root


def place_batten(room, tube=14.0, centre_y=-0.30):
    """one twin-tube batten of mounted_fluorescent_lights along x, its back on the ceiling over (0, centre_y); its tubes
    lit at emission `tube`. -> (the batten, the tubes' underside z)"""
    kit = L.import_gltf(LIB.model('mounted_fluorescent_lights'), room)

    def glass_tris(o):
        gi = [i for i, s in enumerate(o.material_slots) if s.material and 'glass' in s.material.name]
        return sum(len(p.vertices) - 2 for p in o.data.polygons if p.material_index in gi)
    bat = max((o for o in kit if o.type == 'MESH'), key=lambda o: (glass_tris(o), -abs(o.dimensions.x - 0.912)))
    for o in kit:
        if o is not bat:
            bpy.data.objects.remove(o, do_unlink=True)
    bat.name = 'cc0_fluorescent_batten'
    bat.parent = None
    bat.rotation_euler = (0.0, 0.0, 0.0)
    bat.location = (0.0, 0.0, 0.0)
    lo, hi = L.world_bbox([bat])
    bat.location = (-0.5 * (lo.x + hi.x), centre_y - 0.5 * (lo.y + hi.y), HT / 1000.0 - hi.z)
    lo, hi = L.world_bbox([bat])
    for s in bat.material_slots:                                        # the tubes lit
        m = s.material
        if m and 'glass' in m.name and m.use_nodes:
            b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if b:
                b.inputs['Emission Strength'].default_value = float(tube)
                if not b.inputs['Emission Color'].is_linked:
                    b.inputs['Emission Color'].default_value = (0.92, 1.0, 0.95, 1.0)
    return bat, lo.z


# ------------------------------------------------------------------------------------------------ the light
def lamp(room, name, kind, at, watts, rgb, size=None, size_y=None, aim=None, shadow=True):
    ld = bpy.data.lights.new(name, kind)
    ld.energy, ld.color = watts, rgb
    if kind == 'AREA':
        ld.shape, ld.size = ('RECTANGLE' if size_y else 'SQUARE'), size
        if size_y:
            ld.size_y = size_y
    elif size:
        ld.shadow_soft_size = size
    ld.use_shadow = shadow
    o = bpy.data.objects.new(name, ld)
    room.objects.link(o)
    o.location = at
    if aim is not None:
        o.rotation_euler = (Vector(aim) - Vector(at)).to_track_quat('-Z', 'Y').to_euler()
    return o


FLUO = (0.90, 1.0, 0.92)


def lights(room, tube_z, watts=150.0, wallfill=0.05):
    """the batten's light: an area light under its tubes; a shadowless wash up the ceiling; a shadowless bounce from the
    floor and from each wall, the colour each is lit"""
    lamp(room, 'sealed_room.fitting', 'AREA', (0.0, -0.30, tube_z - 0.004), watts, FLUO, 0.86, 0.07, aim=(0.0, -0.30, 0.0))
    lamp(room, 'sealed_room.fitting_ceiling_wash', 'AREA', (0.0, -0.30, tube_z - 0.012), watts * 0.18, FLUO, 1.0, 0.25,
         aim=(0.0, -0.30, 5.0), shadow=False)
    lamp(room, 'sealed_room.floor_bounce', 'AREA', (0.0, 0.3, 0.04), watts * 0.13, (0.72, 0.68, 0.58), 3.6, 3.2, aim=(0.0, 0.3, 2.0), shadow=False)
    w_wall = watts * wallfill
    for nm, at, to, sz in (('back', (0.0, 2.70, 1.0), (0.0, 0.0, 0.6), (4.6, 1.6)), ('left', (-2.45, 0.45, 1.0), (0.0, 0.45, 0.6), (4.2, 1.6)),
                           ('right', (2.45, 0.45, 1.0), (0.0, 0.45, 0.6), (4.2, 1.6)), ('front', (0.0, -1.80, 1.0), (0.0, 0.0, 0.6), (4.6, 1.6))):
        lamp(room, f'sealed_room.wall_bounce_{nm}', 'AREA', at, w_wall, (0.62, 0.70, 0.64), sz[0], sz[1], aim=to, shadow=False)


def world():
    """the room's world: black (nothing reaches in from outside)"""
    w = bpy.data.worlds.get('sealed_room_world') or bpy.data.worlds.new('sealed_room_world')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.0, 0.0, 0.0, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
    return w


def apply(room, bake_dir, library, tube=14.0, watts=150.0, wallfill=0.05):
    """The room's look on its collection `room` (the lows step's file): every part's material, the CC0 models, the
    lights, the world. -> {'materials', 'world', 'tube_z'}"""
    global BAKE, LIB
    BAKE, LIB = bake_dir, library
    mats = {}

    def mat(key, fn):
        if key not in mats:
            mats[key] = fn()
        return mats[key]
    for o in [o for o in room.objects if o.type == 'MESH']:
        assign(o, material_for(o, mat))
    bpy.data.objects['wall_front_unseen'].visible_camera = False        # (the lenses look in through it; it shuts the room)
    place_stool(room)
    place_camera(room)
    _, tube_z = place_batten(room, tube)
    lights(room, tube_z, watts, wallfill)
    L.log('sealed look', f'{len(mats)} materials')
    return {'materials': sorted(m.name for m in mats.values()), 'world': world(), 'tube_z': tube_z}
