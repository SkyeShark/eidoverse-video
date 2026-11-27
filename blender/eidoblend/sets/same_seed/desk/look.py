"""eidoblend.sets.same_seed.desk.look: the room at 2 a.m., its materials, its Poly Haven pieces touched and its light
(Blender).

    from eidoblend.sets.same_seed.desk import look
    res = look.apply(room_collection, bake_dir, library, prints_dir, lamp=150.0, screen=1.3, screen_w=3.0, moon=0.2,
                     world=0.15, night=0.18)
    look.finish(room_collection, scene, res)      # the volume probe baked over the finished room

A lived-in, kept room of someone who makes music at night; nothing derelict.
1. EVERY BUILT SURFACE FROM A CC0 PHOTOGRAPHIC SET at its real size (the S table, sizes read off each set's own
   features), given by the builder's named clays ('desk.<family>': one material a surface family, the FAMILY table):
   flat parts through the builder's metre UV ('box_1m'), turned and swept parts through an object-space box
   projection. ONE STACK per material in the order of what happened to it (stack()): the finish -> grime where dirt
   collects (the baked cavity and AO on the lows) -> wear where hands, feet and knocks go only (the baked arris nearness
   x where they go) -> dust on what faces up -> stains with their causes (a coffee ring where the mug stood, a lime ring
   under the sill's pot, hands' grey round the door's lever and the light switch, the PC's dust on its top, crumbs' grey
   between the keycaps) -> markings at real size, unmirrored (the prints: the screen's recording, the handwritten
   lyrics, the gig poster in the empty frame).
2. THE POLY HAVEN PIECES keep their own scanned materials; the poster goes into the empty frame, the desk lamp's bulb is
   lit warm and the ceiling lamp put out.
3. THE LIGHT OF 2 A.M.: the screen's cool glow on what faces it (an area light on the panel, `screen_w` W, the panel's own
   picture as its emission at `screen`); the desk lamp's warm pool on the desk (a spot at the shade's mouth, `lamp` W,
   aimed at (lamp_x, lamp_y) on the top); faint moonlight at the window (a cold sun, `moon` W/m2, `moon_el` up and
   `moon_az` round: the casements' shadow on the floor) and the square's night outside (Poly Haven's hansaplatz: the
   builder's backdrop seen through the glass at `night`, turned night_u and raised night_v; the same HDRI as the world
   at `world`, cooled, black to the lens); the ceiling lamp OFF; the rest left dark. A volume probe baked over the room
   for what all of it gives back, a sphere probe for the reflections. The film renders at exposure 0, so the lights are
   set to read at 0.
The room's render settings (RENDER in its package): Fast GI as ambient occlusion only at 64 samples (the probe carries
the bounce); the shadow pool at 1024 MB. Everything the room needs is in collection desk_room (its parts, child
collection desk_lights: its lights and probes); its world is desk_night_world; wall_front_unseen stays, hidden from the
camera only.
"""

import math

import bpy
from mathutils import Vector

from ....materials.layered import NT
from .. import look as L
from ..look import box_uv

OB = ROOM = BAKE = PRINTS = LIB = None
SCREEN_K = 1.3
SWITCH_AT = HANDLE_AT = MUG_AT = POT_AT = None


class Mat(L.Mat):
    ROUGH_MIN = 0.02


def log(*a):
    L.log('desk look', *a)


# ----------------------------------------------------------------------------------- the sets (real sizes, m)
# read off each set's own features: PaintedPlaster017 a 2 x 1 m wall; Plaster001's fissures (a ceiling's skim);
# oak_wood_planks twelve planks of ~165 mm across its tile (2 m; they run along u: turned to run toward the window);
# oak_veneer_01 a veneer's cathedral figure, ~7 flames to 0.8 m; white_maple_veneer's fine straight grain (as a spruce
# top's, 0.6 m); rosewood_veneer1's figure (0.5 m); lacquered_cherry_wood (as a mahogany neck's close grain, 0.8 m);
# Carpet016's wool loops (0.4 m); rough_linen's slub weave (0.3 m); book_pattern's book-cloth weave (0.12 m); Fabric034 a
# felt (0.15 m); Fabric039 a fine weave (velour, 0.12); Fabric023 a cotton weave (0.15); Paint004's orange peel (powder
# coat, enamel); Plastic013A's moulded skin; Granite005A's grains (a polished stone window board); Leather037 a grain
# (leatherette); Paper001; Fingerprints002/008 hands' marks
S = {'plaster': ('PaintedPlaster017_2k', 2.0), 'skim': ('Plaster001_2k', 0.6), 'oakfloor': ('oak_wood_planks_2k', 2.0),
     'oak': ('oak_veneer_01_2k', 0.8), 'spruce': ('white_maple_veneer_2k', 0.6), 'rosewood': ('rosewood_veneer1_2k', 0.5),
     'mahogany': ('lacquered_cherry_wood_2k', 0.8), 'paint': ('Paint004_2k', 0.8), 'plastic': ('Plastic013A_2k', 0.4),
     'rubber': ('Rubber004_2k', 0.3), 'steel': ('Metal009_2k', 0.5), 'darkmetal': ('Metal038_2k', 0.5), 'prints': ('Fingerprints002_2k', 0.2),
     'smudge': ('Fingerprints008_2k', 0.3), 'felt': ('Fabric034_2k', 0.15), 'velour': ('Fabric039_1k', 0.12), 'cotton': ('Fabric023_1k', 0.15),
     'linen': ('rough_linen_2k', 0.3), 'wool': ('Carpet016_2k', 0.4), 'cloth': ('book_pattern_2k', 0.12), 'paper': ('Paper001_2k', 0.35),
     'leather': ('Leather037_2k', 0.3), 'granite': ('Granite005A_2k', 0.35)}
ASPECT = {}


def sfile(k, key):
    return LIB.tex(S[k][0], key)


def photo(M, k, vec_m, keys=('diff', 'rough', 'displacement'), box=False, deg=0.0):
    """a set's maps at its real size through a vector in metres (u across the picture's width; v by its own aspect),
    turned deg in its plane"""
    if k not in ASPECT:
        maps = LIB.files(S[k][0])
        im = L.image(maps.get('diff') or maps.get('rough') or maps.get('normal'), 'diff' in maps)
        ASPECT[k] = im.size[0] / max(1, im.size[1])
    w = S[k][1]
    v = M.mapping(vec_m, (1.0 / w, ASPECT[k] / w, 1.0 / w), rot=(0.0, 0.0, math.radians(deg)))
    return {key: M.tex(sfile(k, key), v, color=(key == 'diff'), box=box) for key in keys}


def baked(M, atlas):
    """the atlas's bakes on the low (UV 'atlas'): its normal (the high's bevels) and (ao, cavity, fine curvature, arris
    nearness, inside-corner nearness)"""
    return L.baked(M, BAKE, atlas)


def picture(M, name, uvname, color=True):
    return L.picture(M, PRINTS, name, uvname, color)


def disc(M, X, Y, cx, cy, r0, r1):
    """1 inside a ring of radius r0..r1 (mm) about (cx, cy) on the plan, soft edged"""
    d = M.m('SQRT', M.add(M.m('POWER', M.sub(X, cx), 2.0), M.m('POWER', M.sub(Y, cy), 2.0)))
    return M.mul(M.sm(d, r0 - 1.5, r0), M.inv(M.sm(d, r1, r1 + 1.5)))


def near(M, X, Y, Z, at, r_in, r_out):
    """1 within r_in of a point (mm), falling to 0 at r_out"""
    d = M.m('SQRT', M.add(M.add(M.m('POWER', M.sub(X, at[0]), 2.0), M.m('POWER', M.sub(Y, at[1]), 2.0)), M.m('POWER', M.sub(Z, at[2]), 2.0)))
    return M.inv(M.sm(d, r_in, r_out))


def bounds(name):
    o = OB.get(name) or OB[name + '_low']                       # (a baked part is its low now)
    pts = [o.matrix_world @ Vector(b) for b in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


def centre_mm(name):
    lo, hi = bounds(name)
    return tuple(((lo + hi) / 2.0) * 1000.0)


# ------------------------------------------------------------------------- the layered stack (one for the baked lows)
def stack(M, atlas, base_col, rough, metal=0.0, grime=(0.30, 0.29, 0.27), grime_k=0.3, zone=None, chip_to=None, rub_k=0.12,
          dust_k=1.0, dust=(0.50, 0.48, 0.45), ao_k=0.35):
    """the finish (base_col, rough: sockets or numbers) -> GRIME where dirt collects (baked cavity, then AO) -> WEAR only in
    `zone` (a field 0..1: where hands and feet go): within 0.6-3 mm of an arris (the baked arris distance), rubbed smoother,
    then (chip_to: the colour under the finish) chipped -> DUST on what faces up. Returns (colour, roughness, metal)"""
    ov = M.obj()
    col = base_col
    if atlas:
        ao, cav, fine, near_cv, near_cc = baked(M, atlas)
        g = M.mul(M.add(M.mul(M.inv(cav), 1.3), M.mul(M.inv(ao), ao_k)), M.lin(M.noise(ov, 40.0, 3.0), 0.3, 0.7, 0.6, 1.2), clamp=True)
        col = M.mixc(M.mul(M.sm(g, 0.1, 0.6), grime_k), col, M.rgb(grime))
        rough = M.add(rough, M.mul(g, 0.08))
        if zone is not None:
            edge = M.sm(near_cv, 0.9, 0.98)
            wear = M.mul(M.mul(edge, zone), M.lin(M.noise(ov, 120.0, 4.0), 0.35, 0.75, 0.0, 1.6), clamp=True)
            rough = M.sub(rough, M.mul(M.sm(wear, 0.25, 0.45), rub_k))
            if chip_to is not None:
                chip = M.sm(wear, 0.9, 0.97)
                col = M.mixc(chip, col, M.rgb(chip_to[0]))
                rough = M.mixf(chip, rough, chip_to[1])
                metal = M.mixf(chip, metal, chip_to[2])
    nx, ny, nz = M.world_nrm()
    dd = M.mul(M.mul(M.sm(nz, 0.75, 0.97), M.sm(M.noise(ov, 30.0, 3.0), 0.4, 0.75)), dust_k)
    col = M.mixc(M.mul(dd, 0.3), col, M.rgb(dust))
    rough = M.add(rough, M.mul(dd, 0.3))
    return col, rough, metal


# ---------------------------------------------------------------------------------- the materials, by family
# each maker takes (atlas or None) and returns a material; the room's surfaces are given them by the builder's named clays
def m_wall(atlas=None):
    """warm white emulsion on plaster, matte (PaintedPlaster017's light and shade held to a few percent); hands' grey round
    the light switch (its cause: a hand finds it in the dark, every night); scuffs low by the floor where the hoover goes"""
    M = Mat('look.wall_paint')
    p = photo(M, 'plaster', M.uv('box_1m'), ('diff', 'rough', 'normal'))
    M.nmap(p['normal'].outputs[0], 'box_1m', 0.12)
    col = M.value(M.rgb((0.74, 0.72, 0.68)), M.lin(M.lum(p['diff'].outputs[0]), 0.45, 0.65, 0.97, 1.02))
    rough = M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.8, 0.92)
    X, Y, Z = M.pos_mm()
    ov = M.obj()
    low = M.mul(M.inv(M.sm(Z, 30.0, 160.0)), M.sm(M.noise(ov, 7.0, 3.0), 0.45, 0.75))
    col = M.mixc(M.mul(low, 0.2), col, M.rgb((0.42, 0.40, 0.37)))
    hand = M.mul(near(M, X, Y, Z, SWITCH_AT, 40.0, 130.0), M.lin(M.noise(ov, 60.0, 3.0), 0.3, 0.7, 0.4, 1.0))
    col = M.mixc(M.mul(hand, 0.3), col, M.rgb((0.46, 0.44, 0.41)))
    return M.done(col, rough)


def m_ceiling(atlas=None):
    M = Mat('look.ceiling_paint')
    p = photo(M, 'skim', M.uv('box_1m'), ('normal', 'rough'))
    M.nmap(p['normal'].outputs[0], 'box_1m', 0.25)
    return M.done(M.rgb((0.78, 0.78, 0.76)), 0.92)


def m_floor(atlas=None):
    """oak boards, oiled-and-lacquered, satin (oak_wood_planks, the boards running toward the window); the lacquer worn duller
    and a shade paler on the way in from the door to the desk and round the chair; grey fluff along the skirting"""
    M = Mat('look.floor_oak')
    p = photo(M, 'oakfloor', M.uv('box_1m'), ('diff', 'rough', 'normal'), deg=90.0)
    M.nmap(p['normal'].outputs[0], 'box_1m', 0.5)
    col = M.tint(p['diff'].outputs[0], (0.86, 0.82, 0.78), desat=0.1, gain=0.95)
    X, Y, Z = M.pos_mm()
    ov = M.obj()
    path = M.mx(M.mul(M.inv(M.sm(M.m('ABSOLUTE', M.sub(Y, M.add(600.0, M.mul(M.sub(X, 3000.0), 0.45)))), 250.0, 700.0)), M.sm(X, 500.0, 1200.0)),
                M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(X, 900.0), 2.0), M.m('POWER', M.add(Y, 420.0), 2.0))), 300.0, 800.0)))
    path = M.mul(path, M.lin(M.noise(ov, 3.0, 2.0), 0.3, 0.7, 0.4, 1.0))
    col = M.value(col, M.add(1.0, M.mul(path, 0.06)))
    edge = M.mx(M.mx(M.inv(M.sm(M.sub(3000.0, X), 6.0, 50.0)), M.inv(M.sm(M.add(X, 3000.0), 6.0, 50.0))), M.inv(M.sm(M.sub(3000.0, Y), 6.0, 50.0)))
    edge = M.mul(edge, M.sm(M.noise(ov, 30.0, 3.0), 0.45, 0.7))
    col = M.mixc(M.mul(edge, 0.45), col, M.rgb((0.30, 0.29, 0.27)))
    rough = M.add(M.add(M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.28, 0.45), M.mul(path, 0.18)), M.mul(edge, 0.3))
    return M.done(col, rough, 0.0, {'Coat Weight': 0.15, 'Coat Roughness': 0.25})


def m_trim(atlas=None):
    """white satin gloss on joinery (skirting, the door's lining and architraves): Paint004's peel; grime in the inside
    corners (baked for the lining); dust on the skirting's top"""
    M = Mat('look.trim_white_paint' + (f'@{atlas}' if atlas else ''))
    ov = M.obj()
    p = photo(M, 'paint', ov, ('rough', 'displacement'), box=True)
    col, rough, metal = stack(M, atlas, M.rgb((0.80, 0.79, 0.76)), M.add(0.3, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.08)),
                              grime=(0.42, 0.40, 0.37), grime_k=0.25, dust_k=1.2)
    M.bump(p['displacement'].outputs[0], 0.00003)
    return M.done(col, rough, metal)


def m_door(atlas=None):
    """the leaf's white lacquer (satin, Paint004's peel); hands' grey round the lever (its cause: every opening), kicks low on
    the leaf's face by the floor; baked grime in its rebate"""
    M = Mat('look.door_lacquer_white' + (f'@{atlas}' if atlas else ''))
    ov = M.obj()
    p = photo(M, 'paint', ov, ('rough', 'displacement'), box=True)
    X, Y, Z = M.pos_mm()
    hand = M.mul(near(M, X, Y, Z, HANDLE_AT, 50.0, 220.0), M.lin(M.noise(ov, 50.0, 3.0), 0.3, 0.7, 0.3, 1.0))
    kick = M.mul(M.inv(M.sm(Z, 80.0, 260.0)), M.sm(M.noise(ov, 18.0, 3.0), 0.5, 0.75))
    zone = M.mx(hand, kick)
    col, rough, metal = stack(M, atlas, M.rgb((0.82, 0.81, 0.78)), M.add(0.28, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.08)),
                              grime=(0.42, 0.40, 0.37), grime_k=0.25, zone=zone, chip_to=((0.55, 0.50, 0.42), 0.6, 0.0))
    col = M.mixc(M.mul(hand, 0.18), col, M.rgb((0.45, 0.43, 0.40)))
    col = M.mixc(M.mul(kick, 0.2), col, M.rgb((0.35, 0.33, 0.31)))
    M.bump(p['displacement'].outputs[0], 0.00003)
    return M.done(col, rough, metal)


def m_pvc(atlas=None):
    """white uPVC (Plastic013A's moulded skin), satin, faintly yellowed; grime in the casements' corners and gasket lines
    (baked), dust on the bottom rails' tops; the handles' grey of hands"""
    M = Mat('look.window_pvc_white' + (f'@{atlas}' if atlas else ''))
    ov = M.obj()
    p = photo(M, 'plastic', ov, ('rough', 'displacement'), box=True)
    X, Y, Z = M.pos_mm()
    col, rough, metal = stack(M, atlas, M.rgb((0.80, 0.80, 0.76)), M.add(0.32, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.1)),
                              grime=(0.40, 0.39, 0.36), grime_k=0.35, dust_k=1.5)
    M.bump(p['displacement'].outputs[0], 0.00002)
    return M.done(col, rough, metal)


def m_glass(atlas=None):
    """window glass: a thin pane as a film, a Fresnel mirror over a straight pass; its shadow is what it
    lets through (transparent shadows); a faint film of handling"""
    M = Mat('look.glass')
    for n in list(M.N):
        if n.type != 'OUTPUT_MATERIAL':
            M.N.remove(n)
    tr = M.N.new('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = (0.86, 0.88, 0.87, 1.0)  # (two panes of four: each pane object lets ~93 % through)
    gl = M.N.new('ShaderNodeBsdfGlossy')
    lw = M.N.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.06
    f = M.add(M.mul(lw.outputs['Fresnel'], 0.6), 0.03)
    sm = photo(M, 'smudge', M.obj(), ('diff',), box=True)['diff']
    M.L.new(M.add(0.02, M.mul(M.sm(M.lum(sm.outputs[0]), 0.2, 0.6), 0.05)), gl.inputs['Roughness'])
    mx = M.N.new('ShaderNodeMixShader')
    M.L.new(f, mx.inputs[0])
    M.L.new(tr.outputs[0], mx.inputs[1])
    M.L.new(gl.outputs[0], mx.inputs[2])
    M.L.new(mx.outputs[0], M.out.inputs[0])
    for k, v in (('surface_render_method', 'BLENDED'), ('use_transparent_shadow', True)):
        try:
            setattr(M.mat, k, v)
        except Exception:  # noqa: BLE001
            pass
    return M.mat


def m_metal(name, base, r0, brushed=None, prints=0.0):
    def make(atlas=None):
        M = Mat(f'look.{name}' + (f'@{atlas}' if atlas else ''))
        ov = M.obj()
        rough = r0
        if brushed:
            pr = photo(M, brushed, ov, ('rough',), box=True)
            rough = M.add(r0, M.mul(M.sub(pr['rough'].outputs[0], 0.5), 0.2))
        if prints:
            fp = photo(M, 'prints', ov, ('diff',), box=True)['diff']
            rough = M.add(rough, M.mul(M.sm(M.lum(fp.outputs[0]), 0.12, 0.5), prints))
        col, rough, metal = stack(M, atlas, M.rgb(base), rough, 1.0, grime=(0.2, 0.19, 0.18), grime_k=0.4, dust_k=0.6)
        return M.done(col, rough, metal)
    return make


def m_plastic(name, base, r0=0.42, bump_m=0.00003, polish=None, grime=(0.30, 0.29, 0.27), grime_k=0.3, dust_k=1.0, key='plastic',
              zone=None, sss=0.0, ao_k=0.35):
    """moulded plastic (Plastic013A's skin as a bump) on its stack; polish: a field where hands have made it glossier"""
    def make(atlas=None):
        M = Mat(f'look.{name}' + (f'@{atlas}' if atlas else ''))
        ov = M.obj()
        p = photo(M, key, ov, ('rough', 'displacement'), box=True)
        rough = M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.15))
        if polish is not None:
            rough = M.sub(rough, M.mul(polish(M), 0.2))
        col, rough, metal = stack(M, atlas, M.rgb(base), rough, 0.0, grime=grime, grime_k=grime_k, dust_k=dust_k,
                                  zone=zone(M) if zone else None, ao_k=ao_k)
        M.bump(p['displacement'].outputs[0], bump_m)
        ex = {}
        if sss:
            ex.update({'Subsurface Weight': sss, 'Subsurface Radius': (0.01, 0.01, 0.01)})
        return M.done(col, rough, metal, ex)
    return make


def m_powder(name, base, r0=0.4, boots=True, hands=None, dust_k=1.0, chip=((0.18, 0.18, 0.19), 0.35, 1.0)):
    """powder-coated steel on a baked low (the desk's frame, the PC's case, the curtain rod): Paint004's peel over the baked
    normal; grime in cavities; wear only where boots (the bottom 15 cm) and hands go: rubbed, then chipped to steel; dust"""
    def make(atlas=None):
        M = Mat(f'look.{name}' + (f'@{atlas}' if atlas else ''))
        ov = M.obj()
        p = photo(M, 'paint', ov, ('rough', 'displacement'), box=True)
        X, Y, Z = M.pos_mm()
        zone = 0.0
        if boots:
            zone = M.mul(M.inv(M.sm(Z, 100.0, 180.0)), 0.8)
        if hands is not None:
            zone = M.mx(zone, hands(M, X, Y, Z))
        col, rough, metal = stack(M, atlas, M.rgb(base), M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.1)), 0.0,
                                  grime=(0.12, 0.115, 0.11) if sum(base) < 0.3 else (0.3, 0.29, 0.27), grime_k=0.3,
                                  zone=zone, chip_to=chip, dust_k=dust_k, dust=(0.42, 0.40, 0.38))
        M.bump(p['displacement'].outputs[0], 0.00003)
        return M.done(col, rough, metal)
    return make


def frame_hands(M, X, Y, Z):
    """the desk's frame: the middle of the front rail where the chair's back knocks (x 700-1100, z 600-720)"""
    return M.mul(M.mul(M.sm(X, 600.0, 750.0), M.inv(M.sm(X, 1050.0, 1200.0))), M.mul(M.sm(Z, 560.0, 620.0), M.inv(M.sm(Y, 0.0, 60.0))))


def m_oak_top(atlas=None):
    """the desk's oak top (oak_veneer_01, the figure along the desk's length), a satin lacquer; the lacquer rubbed duller
    where forearms rest along the front and where the mouse hand works; a coffee ring where the mug stood before it was
    moved (its cause: set down wet), a fainter second; the baked grime at the grommet and the edges"""
    M = Mat('look.desk_oak_top' + (f'@{atlas}' if atlas else ''))
    ov = M.obj()
    ao, cav, fine, near_cv, near_cc = baked(M, atlas) if atlas else (1.0, 1.0, 0.5, 0.0, 0.0)
    p = photo(M, 'oak', M.uv('box_1m'), ('diff', 'rough', 'displacement'), deg=90.0)
    M.bump(p['displacement'].outputs[0], 0.00004)              # (the open pores over the baked bevels)
    col = M.tint(p['diff'].outputs[0], (0.92, 0.84, 0.72), desat=0.05, gain=0.95)
    X, Y, Z = M.pos_mm()
    nx, ny, nz = M.world_nrm()
    top = M.sm(nz, 0.8, 0.95)
    rough = M.add(0.32, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.15))
    work = M.mx(M.mul(M.mul(M.inv(M.sm(Y, 80.0, 260.0)), M.sm(X, 250.0, 450.0)), M.inv(M.sm(X, 1500.0, 1650.0))),
                M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(X, 1170.0), 2.0), M.m('POWER', M.sub(Y, 200.0), 2.0))), 60.0, 200.0)))
    sm = photo(M, 'smudge', ov, ('diff',), box=True)['diff']
    marks = M.mul(M.mul(work, top), M.sm(M.lum(sm.outputs[0]), 0.15, 0.55))
    rough = M.add(rough, M.mul(marks, 0.2))
    col = M.value(col, M.sub(1.0, M.mul(work, M.mul(top, 0.05))))
    ring = M.mul(disc(M, X, Y, MUG_AT[0] - 34.0, MUG_AT[1] - 22.0, 37.0, 40.0), top)
    ring2 = M.mul(disc(M, X, Y, MUG_AT[0] + 52.0, MUG_AT[1] + 40.0, 37.0, 39.5), top)
    rr = M.lin(M.noise(ov, 90.0, 2.0), 0.3, 0.7, 0.3, 1.0)
    col = M.mixc(M.mul(M.mul(ring, rr), 0.4), col, M.rgb((0.30, 0.20, 0.12)))
    col = M.mixc(M.mul(M.mul(ring2, rr), 0.18), col, M.rgb((0.30, 0.20, 0.12)))
    rough = M.add(rough, M.mul(ring, 0.15))
    if atlas:
        g = M.mul(M.inv(cav), M.lin(M.noise(ov, 50.0, 3.0), 0.3, 0.7, 0.5, 1.1), clamp=True)
        col = M.mixc(M.mul(M.sm(g, 0.15, 0.6), 0.3), col, M.rgb((0.22, 0.17, 0.12)))
        front = M.mul(M.inv(M.sm(Y, -40.0, 0.0)), M.sm(near_cv, 0.9, 0.98))
        col = M.value(col, M.add(1.0, M.mul(front, 0.12)))
    return M.done(col, rough, 0.0, {'Coat Weight': 0.25, 'Coat Roughness': 0.12})


def m_wood(name, key, tint, gain, deg=0.0, r0=0.35, coat=1.0, coat_r=0.04, uv='box_1m', desat=0.0, nstr=0.15):
    """a finished wood (the guitar's: nitro gloss over the figure): the photograph's figure tinted to the wood, its relief as
    a weak normal, a clear coat; the baked grime in the binding's seam"""
    def make(atlas=None):
        M = Mat(f'look.{name}' + (f'@{atlas}' if atlas else ''))
        ov = M.obj()
        if atlas:
            ao, cav, fine, near_cv, near_cc = baked(M, atlas)
        p = photo(M, key, M.uv(uv), ('diff', 'rough'), deg=deg)
        col = M.tint(p['diff'].outputs[0], tint, desat=desat, gain=gain)
        rough = M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.1))
        if atlas:
            g = M.mul(M.inv(cav), M.lin(M.noise(ov, 60.0, 3.0), 0.3, 0.7, 0.5, 1.1), clamp=True)
            col = M.mixc(M.mul(M.sm(g, 0.15, 0.6), 0.35), col, M.rgb((0.05, 0.035, 0.025)))
        return M.done(col, rough, 0.0, {'Coat Weight': coat, 'Coat Roughness': coat_r})
    return make


def m_tortoise(atlas=None):
    M = Mat('look.guitar_pickguard_tortoise')
    ov = M.obj()
    n1 = M.noise(M.mapping(ov, (60.0, 60.0, 160.0)), 1.0, 6.0, rough=0.6)
    col = M.mixc(M.sm(n1, 0.45, 0.65), M.rgb((0.012, 0.006, 0.003)), M.rgb((0.16, 0.06, 0.015)))
    return M.done(col, 0.12, 0.0, {'Coat Weight': 0.6, 'Coat Roughness': 0.05})


def m_fabric(name, k, base, r=(0.7, 0.95), bump_m=0.0003, sheen=0.4, translucent=0.0, desat=0.0, deg=0.0, extra_fn=None, uv=None):
    """a woven cloth from its photograph (its weave as a bump, its own light and shade on the cloth's colour); translucent:
    what light it lets through from behind (a curtain against the night)"""
    def make(atlas=None):
        M = Mat(f'look.{name}')
        vec = M.uv(uv) if uv else M.obj()
        p = photo(M, k, vec, ('diff', 'rough', 'displacement'), box=(uv is None), deg=deg)
        M.bump(p['displacement'].outputs[0], bump_m)
        col = M.value(M.rgb(base), M.lin(M.lum(p['diff'].outputs[0]), 0.2, 0.8, 0.82, 1.15))
        rough = M.lin(p['rough'].outputs[0], 0.0, 1.0, r[0], r[1])
        if extra_fn is not None:
            col, rough = extra_fn(M, col, rough)
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
    return make


def rug_pattern(M, col, rough):
    """a flat-woven wool rug: slate blue field, a rust border band 60-140 mm in from its edge and a thin cream line inside it;
    flattened and a little paler where the chair's feet stand and the feet of whoever sits there go"""
    X, Y, Z = M.pos_mm()
    d = M.mn(M.mn(M.sub(X, -1300.0), M.sub(1700.0, X)), M.mn(M.sub(Y, -1880.0), M.sub(-80.0, Y)))
    band = M.mul(M.sm(d, 55.0, 65.0), M.inv(M.sm(d, 135.0, 145.0)))
    line = M.mul(M.sm(d, 168.0, 172.0), M.inv(M.sm(d, 180.0, 184.0)))
    shade = M.lin(M.lum(col), 0.05, 0.15, 0.75, 1.2)               # (the wool's own light and shade, carried onto the band)
    rust = M.mixc(1.0, M.rgb((0.30, 0.10, 0.045)), M.comb(shade, shade, shade))
    rust.node.blend_type = 'MULTIPLY'
    c2 = M.mixc(band, col, rust)
    c2 = M.mixc(line, c2, M.rgb((0.52, 0.47, 0.38)))
    feet = M.inv(M.sm(M.m('SQRT', M.add(M.m('POWER', M.sub(X, 900.0), 2.0), M.m('POWER', M.add(Y, 420.0), 2.0))), 250.0, 650.0))
    c2 = M.value(c2, M.add(1.0, M.mul(feet, 0.12)))
    return c2, M.sub(rough, M.mul(feet, 0.08))


def m_rug(atlas=None):
    M = Mat('look.rug_wool')
    p = photo(M, 'wool', M.uv('box_1m'), ('diff', 'rough', 'displacement'))
    M.bump(p['displacement'].outputs[0], 0.0015)
    col = M.value(M.rgb((0.075, 0.095, 0.12)), M.lin(M.lum(p['diff'].outputs[0]), 0.3, 0.7, 0.75, 1.2))
    col, rough = rug_pattern(M, col, M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.85, 1.0))
    return M.done(col, rough, 0.0, {'Sheen Weight': 0.6, 'Sheen Roughness': 0.5})


def m_books(atlas=None):
    """book cloth over board (book_pattern's weave), each book its own cloth colour (the builder's 'book_tint'), a little
    duller or glossier book to book (its tint's own value), rubbed paler along the spine's edges where fingers pull it out"""
    M = Mat('look.book_cover_cloth_card')
    ov = M.obj()
    p = photo(M, 'cloth', ov, ('rough', 'displacement'), box=True)
    tint = M.attr('book_tint').outputs['Color']
    col = M.value(tint, M.lin(M.noise(ov, 40.0, 3.0), 0.3, 0.7, 0.9, 1.08))
    rough = M.add(M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.6, 0.85), M.mul(M.sub(M.lum(tint), 0.2), 0.3))
    M.bump(p['displacement'].outputs[0], 0.0002)
    return M.done(col, rough, 0.0, {'Sheen Weight': 0.25, 'Sheen Roughness': 0.5})


def m_pages(atlas=None):
    M = Mat('look.book_pages_paper')
    ov = M.obj()
    p = photo(M, 'paper', ov, ('diff', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.0002)
    col = M.value(M.rgb((0.72, 0.68, 0.58)), M.lin(M.noise(M.mapping(ov, (1.0, 1.0, 40.0)), 30.0, 2.0), 0.3, 0.7, 0.85, 1.08))
    return M.done(col, 0.85)


def m_paper(name, pic=None, tint=(0.86, 0.86, 0.83), translucent=0.12):
    def make(atlas=None):
        M = Mat(f'look.{name}')
        p = photo(M, 'paper', M.obj(), ('diff', 'rough', 'displacement'), box=True)
        M.bump(p['displacement'].outputs[0], 0.00004)
        col = M.value(M.rgb(tint), M.lin(M.lum(p['diff'].outputs[0]), 0.4, 0.9, 0.95, 1.03))
        if pic:
            ink = picture(M, pic, 'Float2')                    # (the sheet's own UV, 0..1 over its top face)
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
    return make


def m_screen(atlas=None):
    """the panel: an anti-glare matte over the picture (prints/screen_recording.png, its own pixels), lit at SCREEN_K"""
    M = Mat('look.screen_panel')
    pic = picture(M, 'screen_recording.png', 'Float2')         # (the builder's screen UV: Blender 5.2's bmesh names it 'Float2')
    m = M.done(M.rgb((0.008, 0.008, 0.01)), 0.32, 0.0, {'Emission Strength': SCREEN_K})
    M.L.new(pic.outputs[0], M.bsdf.inputs['Emission Color'])
    return m


def m_emit(name, col, k):
    def make(atlas=None):
        M = Mat(f'look.{name}')
        return M.done(M.rgb((0.05, 0.05, 0.05)), 0.3, 0.0, {'Emission Color': (*col, 1.0), 'Emission Strength': k})
    return make


def m_mug(atlas=None):
    """glazed stoneware: a speckled oatmeal glaze, a brown iron rim where the glaze breaks thin; a coffee run down the side
    under the rim, opposite the handle (its cause: a pour that overran)"""
    M = Mat('look.mug_stoneware_glaze')
    ov = M.obj()
    sp = photo(M, 'granite', ov, ('diff',), box=True)['diff']
    col = M.value(M.rgb((0.70, 0.64, 0.54)), M.lin(M.lum(sp.outputs[0]), 0.3, 0.7, 0.85, 1.12))
    X, Y, Z = M.pos_mm()
    top = MUG_AT[2] + 48.0
    rim = M.sm(Z, top - 6.0, top - 2.0)
    col = M.mixc(rim, col, M.rgb((0.20, 0.10, 0.05)))
    a = M.m('ARCTAN2', M.sub(Y, MUG_AT[1]), M.sub(X, MUG_AT[0]))
    run = M.mul(M.inv(M.sm(M.m('ABSOLUTE', M.sub(a, math.radians(200.0))), 0.04, 0.10)), M.mul(M.sm(Z, top - 40.0, top - 20.0), M.inv(M.sm(Z, top - 4.0, top - 2.0))))
    col = M.mixc(M.mul(run, 0.5), col, M.rgb((0.18, 0.09, 0.03)))
    fp = photo(M, 'prints', ov, ('diff',), box=True)['diff']
    rough = M.add(0.08, M.mul(M.sm(M.lum(fp.outputs[0]), 0.15, 0.5), 0.12))
    return M.done(col, rough, 0.0, {'Coat Weight': 0.3, 'Coat Roughness': 0.04})


def m_coffee(atlas=None):
    M = Mat('look.coffee')
    return M.done(M.rgb((0.018, 0.008, 0.003)), 0.05, 0.0, {'Specular IOR Level': 0.5})


def m_stone_board(atlas=None):
    """the window board: a polished light granite (Granite005A's grains), dust on it; a lime ring where the pot stood before
    (its cause: water through the pot's hole, dried), a fainter one under it now"""
    M = Mat('look.window_board_stone' + (f'@{atlas}' if atlas else ''))
    p = photo(M, 'granite', M.uv('box_1m'), ('diff', 'rough'))
    col0 = M.value(M.rgb((0.62, 0.61, 0.58)), M.lin(M.lum(p['diff'].outputs[0]), 0.2, 0.7, 0.75, 1.18))
    col, rough, metal = stack(M, atlas, col0, M.add(0.12, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.1)), grime=(0.35, 0.34, 0.32),
                              grime_k=0.3, dust_k=1.4)
    X, Y, Z = M.pos_mm()
    ring = disc(M, X, Y, POT_AT[0] - 95.0, POT_AT[1] - 10.0, 62.0, 72.0)
    ring = M.mx(ring, M.mul(disc(M, X, Y, POT_AT[0], POT_AT[1], 68.0, 76.0), 0.5))
    col = M.mixc(M.mul(ring, 0.35), col, M.rgb((0.80, 0.79, 0.76)))
    rough = M.add(rough, M.mul(ring, 0.3))
    return M.done(col, rough, metal, {'Coat Weight': 0.2, 'Coat Roughness': 0.06})


def keys_polish(M):
    """the keycaps most used: the space bar and the home row's middle (glossier with years of fingers)"""
    X, Y, Z = M.pos_mm()
    kb = centre_mm('keyboard_keycaps')
    space = M.mul(M.inv(M.sm(M.m('ABSOLUTE', M.sub(X, kb[0] - 40.0)), 50.0, 70.0)), M.inv(M.sm(Y, kb[1] - 45.0, kb[1] - 38.0)))
    home = M.mul(M.inv(M.sm(M.m('ABSOLUTE', M.sub(Y, kb[1] - 2.0)), 10.0, 20.0)), M.inv(M.sm(M.m('ABSOLUTE', M.sub(X, kb[0] - 70.0)), 90.0, 140.0)))
    return M.mx(space, M.mul(home, 0.7))


def palm(M):
    X, Y, Z = M.pos_mm()
    return M.sm(Z, centre_mm('mouse_shell')[2], centre_mm('mouse_shell')[2] + 12.0)


def m_pc_mesh(atlas=None):
    """the PC's front: a black perforated steel sheet (2 mm holes at 3 mm centres), the dark of the case behind them"""
    M = Mat('look.pc_front_mesh')
    X, Y, Z = M.pos_mm()
    u = M.m('FRACT', M.mul(X, 1.0 / 3.0))
    v = M.m('FRACT', M.mul(Z, 1.0 / 3.0))
    d = M.m('SQRT', M.add(M.m('POWER', M.sub(u, 0.5), 2.0), M.m('POWER', M.sub(v, 0.5), 2.0)))
    hole = M.inv(M.sm(d, 0.30, 0.36))
    col = M.mixc(hole, M.rgb((0.03, 0.03, 0.032)), M.rgb((0.002, 0.002, 0.002)))
    return M.done(col, M.mixf(hole, 0.45, 1.0))


def m_pc_button(atlas=None):
    """the PC's power button: black plastic with its white light ring lit (the machine is on)"""
    M = Mat('look.pc_power_button')
    X, Y, Z = M.pos_mm()
    c = centre_mm('pc_power_button')
    d = M.m('SQRT', M.add(M.m('POWER', M.sub(X, c[0]), 2.0), M.m('POWER', M.sub(Z, c[2]), 2.0)))
    ring = M.mul(M.sm(d, 6.2, 6.8), M.inv(M.sm(d, 7.6, 8.2)))
    return M.done(M.rgb((0.02, 0.02, 0.022)), 0.4, 0.0, {'Emission Color': (0.75, 0.88, 1.0, 1.0), 'Emission Strength': M.mul(ring, 6.0)})


# the families -> their makers (the builder's 'desk.<family>' materials)
FAMILY = {
    'wall_paint': m_wall, 'ceiling_paint': m_ceiling, 'floor_oak': m_floor, 'trim_white_paint': m_trim, 'door_lacquer_white': m_door,
    'window_pvc_white': m_pvc, 'glass': m_glass, 'window_board_stone': m_stone_board,
    'glazing_spacer_alu': m_metal('glazing_spacer_alu', (0.62, 0.63, 0.64), 0.35, 'steel'),
    'gasket_rubber_black': m_plastic('gasket_rubber_black', (0.02, 0.02, 0.02), 0.7, 0.0001, key='rubber', dust_k=0.5),
    'handle_metal': m_metal('handle_metal', (0.70, 0.70, 0.69), 0.28, 'steel', prints=0.15),
    'dark_plastic': m_plastic('dark_plastic', (0.025, 0.025, 0.028), 0.5),
    'switch_plastic_white': m_plastic('switch_plastic_white', (0.80, 0.79, 0.74), 0.28, grime=(0.45, 0.43, 0.40)),
    'radiator_enamel': m_powder('radiator_enamel', (0.82, 0.82, 0.80), 0.26, boots=False, dust_k=1.6, chip=((0.40, 0.40, 0.40), 0.4, 1.0)),
    'curtain_linen': m_fabric('curtain_linen', 'linen', (0.50, 0.46, 0.40), (0.85, 0.98), 0.0004, 0.4, translucent=0.35, desat=0.0),
    'curtain_rod_black_steel': m_powder('curtain_rod_black_steel', (0.02, 0.02, 0.022), 0.35, boots=False, dust_k=1.0),
    'desk_steel_black_powdercoat': m_powder('desk_steel_black_powdercoat', (0.02, 0.02, 0.022), 0.42, hands=frame_hands, dust_k=0.6),
    'desk_oak_top': m_oak_top,
    'desk_mat_felt_grey': m_fabric('desk_mat_felt_grey', 'felt', (0.075, 0.075, 0.08), (0.85, 1.0), 0.0003, 0.5),
    'monitor_plastic_black': m_plastic('monitor_plastic_black', (0.022, 0.022, 0.024), 0.42, grime=(0.15, 0.145, 0.14), dust_k=1.4),
    'monitor_base_alu_dark': m_metal('monitor_base_alu_dark', (0.16, 0.16, 0.17), 0.35, 'darkmetal', prints=0.1),
    'screen_panel': m_screen, 'led_white': m_emit('led_white', (0.85, 0.92, 1.0), 25.0),
    'cable_black': m_plastic('cable_black', (0.018, 0.018, 0.02), 0.38, 0.00002, dust_k=0.6),
    'keyboard_case_alu_grey': m_metal('keyboard_case_alu_grey', (0.42, 0.43, 0.45), 0.38, 'steel', prints=0.12),
    # (grime from the caps' AO, low all over between neighbours, would turn the whole keyboard silver: crumbs only in the cavity)
    'keycap_pbt_black': m_plastic('keycap_pbt_black', (0.024, 0.024, 0.026), 0.6, 0.00004, polish=keys_polish, grime=(0.22, 0.21, 0.2), grime_k=0.18,
                                  dust_k=0.5, ao_k=0.0),
    'key_switch_housing': m_plastic('key_switch_housing', (0.03, 0.03, 0.033), 0.5),
    'rubber_black': m_plastic('rubber_black', (0.02, 0.02, 0.02), 0.75, 0.0001, key='rubber', dust_k=0.3),
    'mouse_base_plastic': m_plastic('mouse_base_plastic', (0.04, 0.04, 0.045), 0.5),
    'pc_case_steel_black': m_powder('pc_case_steel_black', (0.022, 0.022, 0.024), 0.4, dust_k=2.4),
    'pc_front_mesh': m_pc_mesh,
    'guitar_spruce_top': m_wood('guitar_spruce_top', 'spruce', (1.0, 0.74, 0.42), 0.68, deg=90.0, r0=0.3, desat=0.1),   # (an old top is honey, not near white)
    'guitar_rosewood_back_sides': m_wood('guitar_rosewood_back_sides', 'rosewood', (0.72, 0.55, 0.45), 0.55, r0=0.3),
    'guitar_mahogany_neck': m_wood('guitar_mahogany_neck', 'mahogany', (1.6, 1.05, 0.8), 1.0, r0=0.35, coat=0.6, coat_r=0.15),
    'guitar_ebony_board_bridge': m_wood('guitar_ebony_board_bridge', 'rosewood', (0.16, 0.13, 0.12), 0.25, r0=0.4, coat=0.0),
    'guitar_pins_ebony': m_plastic('guitar_pins_ebony', (0.015, 0.012, 0.01), 0.25),
    'guitar_frets_nickel': m_metal('guitar_frets_nickel', (0.72, 0.71, 0.68), 0.22),
    'guitar_bone_nut_saddle': m_plastic('guitar_bone_nut_saddle', (0.78, 0.74, 0.64), 0.3, sss=0.2),
    'guitar_pickguard_tortoise': m_tortoise,
    'guitar_strings_bronze_steel': m_metal('guitar_strings_bronze_steel', (0.78, 0.60, 0.38), 0.25),
    'guitar_tuners_chrome': m_metal('guitar_tuners_chrome', (0.85, 0.85, 0.86), 0.08),
    'guitar_spruce_braces': m_wood('guitar_spruce_braces', 'spruce', (1.0, 0.85, 0.6), 0.75, deg=90.0, coat=0.0, r0=0.6),
    'headphone_spring_steel': m_metal('headphone_spring_steel', (0.30, 0.30, 0.31), 0.3),
    # (the cups lie face up under the lamp; at the stack's dust they read silver: a thing in daily use carries little)
    'headphone_plastic_black': m_plastic('headphone_plastic_black', (0.022, 0.022, 0.024), 0.48, grime=(0.15, 0.145, 0.14), dust_k=0.15),
    'headphone_band_leatherette': m_fabric('headphone_band_leatherette', 'leather', (0.03, 0.028, 0.027), (0.4, 0.6), 0.0002, 0.1),
    'headphone_velour_grey': m_fabric('headphone_velour_grey', 'velour', (0.06, 0.06, 0.062), (0.9, 1.0), 0.0003, 0.8),
    'mug_stoneware_glaze': m_mug, 'coffee': m_coffee,
    'paper_lyrics': m_paper('paper_lyrics', 'lyrics_page.png', (0.88, 0.87, 0.84)),
    'paper_plain': m_paper('paper_plain', None, (0.84, 0.84, 0.82)),
    'rug_wool': m_rug, 'rug_fringe_cotton': m_fabric('rug_fringe_cotton', 'cotton', (0.62, 0.58, 0.50), (0.85, 1.0), 0.0002, 0.5),
    'book_cover_cloth_card': m_books, 'book_pages_paper': m_pages,
}
BY_OBJECT = {'pc_power_button': m_pc_button}                   # (a part that is not its family's: the PC's lit power ring)


# ------------------------------------------------------------------------------------------------ the assignment
def assign_all():
    """every slot of every built part that holds a named clay ('desk.<family>') given its family's material, made once a
    family and atlas (a low carries its atlas in o['atlas'], from the lows step) -> the families with no maker"""
    MADE = {}
    unknown = set()
    n_slots = 0
    for o in list(ROOM.all_objects):
        if o.type != 'MESH':
            continue
        me = o.data
        if 'box_1m' not in me.uv_layers:
            if 'Float2' in me.uv_layers and o.name.split('_low')[0] not in ('monitor_screen', 'page_lyrics', 'night_outside') and not any(
                    (s.material and not s.material.name.startswith('desk.')) for s in o.material_slots):
                me.uv_layers['Float2'].name = 'box_1m'             # (the builder's metre projection, named by Blender 5.2's bmesh 'Float2')
            elif not any((s.material and not s.material.name.startswith('desk.')) for s in o.material_slots):
                box_uv(o, 'box_1m')
        atlas = o.get('atlas')
        base = o.name[:-4] if o.name.endswith('_low') else o.name
        for i, s in enumerate(o.material_slots):
            m = s.material
            if m is None or not m.name.startswith('desk.'):
                continue
            fam = m.name[len('desk.'):]
            maker = BY_OBJECT.get(base) or FAMILY.get(fam)
            if maker is None:
                unknown.add(fam)
                continue
            key = (maker, atlas)
            if key not in MADE:
                MADE[key] = maker(atlas)
            s.link = 'DATA'
            me.materials[i] = MADE[key]
            n_slots += 1
    log(f'materials: {len(MADE)} made, {n_slots} slots given; families with no maker: {sorted(unknown)}')
    return sorted(unknown)


# ------------------------------------------------------------------------------------ the CC0 pieces, touched
def touch_cc0():
    """the poster in the frame on the back wall (the frame ships with a dark board in it): the prints' poster.png on the
    board's faces by a planar UV over them as the room sees them (x to the right, z up: unmirrored); the desk lamp's
    bulb lit warm, the ceiling lamp off (every emission it ships with put out)"""
    fr = OB.get('hanging_picture_frame_01')
    if fr is not None:
        art = next((i for i, s in enumerate(fr.material_slots) if s.material and 'artwork' in s.material.name), None)
        mw = fr.matrix_world
        pts = [mw @ fr.data.vertices[v].co for p in fr.data.polygons if p.material_index == art for v in p.vertices]
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        uvl = fr.data.uv_layers.new(name='poster')
        for p in fr.data.polygons:
            for li in p.loop_indices:
                w_ = mw @ fr.data.vertices[fr.data.loops[li].vertex_index].co
                uvl.data[li].uv = ((w_.x - lo.x) / max(hi.x - lo.x, 1e-6), (w_.z - lo.z) / max(hi.z - lo.z, 1e-6))
        M = Mat('look.poster_print')
        pic = picture(M, 'poster.png', 'poster')
        pp = photo(M, 'paper', M.obj(), ('displacement',), box=True)
        M.bump(pp['displacement'].outputs[0], 0.00003)
        fr.material_slots[art].link = 'DATA'
        fr.data.materials[art] = M.done(M.value(pic.outputs[0], 0.92), 0.6)
        log(f'poster on the frame: board {tuple(round(v, 3) for v in lo)} .. {tuple(round(v, 3) for v in hi)}')
    # the lamps: the desk lamp's bulb lit warm; the ceiling lamp off (every emission it ships with put out)
    EMIT = []
    for o in ROOM.all_objects:
        if o.type != 'MESH':
            continue
        for s in o.material_slots:
            m = s.material
            if not (m and m.node_tree) or m.name.startswith('look.'):
                continue
            for n in m.node_tree.nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    es = n.inputs['Emission Strength']
                    lit = es.default_value > 0 and (tuple(n.inputs['Emission Color'].default_value[:3]) != (0.0, 0.0, 0.0) or n.inputs['Emission Color'].is_linked)
                    if lit:
                        EMIT.append((o.name, m.name, round(es.default_value, 2)))
                        if 'desk_lamp' in m.name:
                            n.inputs['Emission Color'].default_value = (1.0, 0.66, 0.36, 1.0)
                            if n.inputs['Emission Color'].is_linked:
                                for lk in list(n.inputs['Emission Color'].links):
                                    m.node_tree.links.remove(lk)
                            es.default_value = 40.0
                        elif 'ceiling' in m.name or 'globe' in m.name:
                            es.default_value = 0.0
                elif n.type == 'EMISSION' and ('ceiling' in m.name or 'globe' in m.name):
                    n.inputs['Strength'].default_value = 0.0
    log('emissive CC0 materials found:', EMIT)
    return EMIT


# ------------------------------------------------------------------------------------------- the light of 2 a.m.
def lights(LAMP_W, SCREEN_W, MOON_K, WORLD_K, NIGHT_K, NIGHT_U, NIGHT_V, MOON_EL, MOON_AZ, lamp_x, lamp_y, world_rot):
    """the screen's glow, the desk lamp's pool, the moon, the night (the world and the backdrop's strength) -> (collection
    desk_lights, the world)"""
    LIGHTS = bpy.data.collections.get('desk_lights') or bpy.data.collections.new('desk_lights')
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

    def aim(o, at):
        o.rotation_euler = (Vector(at) - o.location).to_track_quat('-Z', 'Y').to_euler()

    # (a) the screen: an area light the size of the lit panel, on its face, facing the room (-y); its colour the picture's mean,
    #     a monitor's 6500 K white against the lamp's 2700 K (it reads cool beside it)
    lo, hi = bounds('monitor_screen')
    scr = lamp('desk_screen_glow', 'AREA', SCREEN_W, (0.80, 0.88, 1.0), shape='RECTANGLE', size=hi.x - lo.x, size_y=hi.z - lo.z)
    scr.location = Vector(((lo.x + hi.x) / 2.0, lo.y - 0.004, (lo.z + hi.z) / 2.0))
    aim(scr, scr.location + Vector((0.0, -1.0, 0.0)))
    log('screen glow at', tuple(round(v, 3) for v in scr.location), 'size', round(hi.x - lo.x, 3), round(hi.z - lo.z, 3))
    # (b) the desk lamp: a spot in its shade at the bulb, a warm 2700 K pool on the desk where the page lies
    lamp_o = OB['desk_lamp_arm_01']
    li_ = next((i for i, s in enumerate(lamp_o.material_slots) if s.material and s.material.name.endswith('_light')), None)
    bulb = None
    if li_ is not None:
        pts = [lamp_o.matrix_world @ lamp_o.data.vertices[v].co for p in lamp_o.data.polygons if p.material_index == li_ for v in p.vertices]
        if pts:
            bulb = sum(pts, Vector()) / len(pts)
    if bulb is None:
        bulb = Vector((0.35, 0.45, 1.25))
    AIM_AT = Vector((lamp_x, lamp_y, 0.74))
    spot = lamp('desk_lamp_pool', 'SPOT', LAMP_W, (1.0, 0.70, 0.42), spot_size=math.radians(95.0), spot_blend=0.6, shadow_soft_size=0.02)
    spot.location = bulb + (AIM_AT - bulb).normalized() * 0.06     # (just out of the shade's mouth: a spot at the bulb lights the shade's inside)
    aim(spot, AIM_AT)
    log('lamp bulb at', tuple(round(v, 3) for v in bulb), 'aimed at', tuple(round(v, 3) for v in AIM_AT))
    # (c) the moon: a cold sun low over the square, in through the glass from +y (the casements' shadow on the floor)
    el, az = math.radians(MOON_EL), math.radians(MOON_AZ)
    to_moon = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    moon = lamp('desk_moon', 'SUN', MOON_K, (0.62, 0.72, 1.0), angle=math.radians(0.6))
    moon.rotation_euler = (-to_moon).to_track_quat('-Z', 'Y').to_euler()
    # (d) the night itself: Poly Haven hansaplatz (CC0, the builder's choice; the same panorama is the backdrop seen through the
    #     glass) as the world that lights the room through the window and gives the glass and gloss their reflections; what
    #     the lens sees through the glass is the builder's backdrop, so a camera ray to the world sees black
    HDRI = LIB.hdri('hansaplatz', '4k')
    w = bpy.data.worlds.get('desk_night_world') or bpy.data.worlds.new('desk_night_world')
    w.use_nodes = True
    WN = NT(w.node_tree)
    for n in list(WN.N):
        if n.type != 'OUTPUT_WORLD':
            WN.N.remove(n)
    tc = WN.N.new('ShaderNodeTexCoord')
    mp = WN.N.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(world_rot))
    WN.L.new(tc.outputs['Generated'], mp.inputs['Vector'])
    env = WN.N.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(HDRI, check_existing=True)
    WN.L.new(mp.outputs[0], env.inputs['Vector'])
    lp = WN.N.new('ShaderNodeLightPath')
    cool = WN.mixc(1.0, env.outputs[0], (0.62, 0.74, 1.0, 1.0))     # (what the room gets from the night: the square's glow cooled toward
    cool.node.blend_type = 'MULTIPLY'                               #  the sky's; its straight sodium yellow turns the walls olive)
    seen = WN.mixc(lp.outputs['Is Camera Ray'], cool, (0.0, 0.0, 0.0, 1.0))
    bg = WN.N.new('ShaderNodeBackground')
    WN.L.new(seen, bg.inputs['Color'])
    bg.inputs['Strength'].default_value = WORLD_K
    WN.L.new(bg.outputs[0], next(n for n in WN.N if n.type == 'OUTPUT_WORLD').inputs[0])
    night = OB['night_outside']
    ntn = night.active_material.node_tree
    for n in list(ntn.nodes):
        if n.type == 'EMISSION':
            n.inputs['Strength'].default_value = NIGHT_K
        if n.type == 'TEX_IMAGE':                                   # the panorama turned NIGHT_U of a turn (its own UV, shifted)
            uvn = ntn.nodes.new('ShaderNodeUVMap')
            uvn.uv_map = 'Float2'
            mpn = ntn.nodes.new('ShaderNodeMapping')
            mpn.inputs['Location'].default_value = (NIGHT_U, NIGHT_V, 0.0)
            ntn.links.new(uvn.outputs[0], mpn.inputs['Vector'])
            ntn.links.new(mpn.outputs[0], n.inputs['Vector'])
    for k in ('hide_probe_volume', 'hide_probe_sphere', 'hide_probe_plane'):
        if hasattr(night, k):
            setattr(night, k, True)                                 # (the world carries the night into the room's light; the backdrop is for the lens)
    OB['wall_front_unseen'].visible_camera = False                 # (the lens looks in through it; it still bounds the room's light)
    return LIGHTS, w


# ------------------------------------------------------------------------------------------------ the room's look
def apply(room, bake_dir, library, prints_dir, lamp=150.0, screen=1.3, screen_w=3.0, moon=0.2, world=0.15, night=0.18, night_u=0.06,
          night_v=0.05, moon_el=30.0, moon_az=102.0, lamp_x=0.5, lamp_y=0.25, world_rot=0.0):
    """The desk room's look on its collection `room` (the lows step's file): every built part's material by its family,
    the Poly Haven pieces touched, the lights (collection desk_lights) and the world. bake_dir: the GPU bake's maps;
    prints_dir: the prints step's pictures. lamp: the desk lamp's W; screen: the panel's emission, screen_w: its glow's W;
    moon: W/m2 at moon_el degrees up and moon_az round from +x toward +y; world: the night's strength in the room's
    light; night: the backdrop's, turned night_u of a turn and raised night_v; lamp_x, lamp_y: where the lamp is aimed on
    the top (m); world_rot: the world turned (degrees). -> {'materials', 'world', 'lights', 'no_maker', 'emissive'}"""
    global OB, ROOM, BAKE, PRINTS, LIB, SCREEN_K, SWITCH_AT, HANDLE_AT, MUG_AT, POT_AT
    OB, ROOM, BAKE, PRINTS, LIB, SCREEN_K = bpy.data.objects, room, bake_dir, prints_dir, library, screen
    SWITCH_AT = centre_mm('switch_rocker')
    HANDLE_AT = centre_mm('door_handle')
    MUG_AT = centre_mm('mug')
    POT_AT = centre_mm('potted_plant_04_pot')
    log('switch', [round(v) for v in SWITCH_AT], 'door lever', [round(v) for v in HANDLE_AT], 'mug', [round(v) for v in MUG_AT],
        'sill pot', [round(v) for v in POT_AT])
    before = set(bpy.data.materials)
    unknown = assign_all()
    emit = touch_cc0()
    lc, w = lights(lamp, screen_w, moon, world, night, night_u, night_v, moon_el, moon_az, lamp_x, lamp_y, world_rot)
    mats = sorted(m.name for m in bpy.data.materials if m not in before)
    return {'materials': mats, 'world': w, 'lights': lc, 'no_maker': unknown, 'emissive': emit}


def finish(room, sc, res):
    """the probes, over the finished room with its render settings: a volume probe whose box reaches 6 cm past every wall,
    the floor and the ceiling, its samples 15 cm apart and 60 surfels a metre (the room's small lamps carry it: sparser,
    its walls go blotchy), invalid samples filled from their valid neighbours (the radiator and the curtains stand within
    15 cm of the back wall); baked now (its bake is saved with the file); and a sphere probe for the reflections"""
    lc = res['lights']
    vp = bpy.data.objects.new('desk_gi_volume', bpy.data.lightprobes.new('desk_gi_volume', 'VOLUME'))
    vp.location, vp.scale = (0.0, 0.5, 1.4), (3.06, 2.56, 1.46)
    for k, v in (('resolution_x', 40), ('resolution_y', 34), ('resolution_z', 20), ('bake_samples', 2048), ('surface_bias', 0.05),
                 ('validity_threshold', 0.25), ('dilation_threshold', 0.5), ('dilation_radius', 3.0), ('capture_world', True),
                 ('capture_indirect', True), ('capture_emission', False), ('surfel_density', 60)):
        try:
            setattr(vp.data, k, v)
        except (AttributeError, TypeError, ValueError) as e:
            log('volume probe setting skipped:', k, e)
    lc.objects.link(vp)
    spp = bpy.data.objects.new('desk_reflection', bpy.data.lightprobes.new('desk_reflection', 'SPHERE'))
    spp.location = (0.3, 0.5, 1.3)
    spp.data.influence_distance = 5.0
    lc.objects.link(spp)
    L.bake_volume_probe(vp, 'desk look')
