"""eidoblend.props.houseplants.look: the houseplants' materials (Blender), from CC0 photographic sets at real size
(cc0.json beside this file) and the leaves' own data (leafdata, leafq: kit.Skin).

    from eidoblend.props.houseplants import look
    look.apply(objects, look.library())          # every plant part among `objects` given its material, by its name

THE LEAVES, their forms untouched: the upper side the species' green (each leaf its own; the newest leaves paler or
bronzed), the midrib pale, the veins where the species has them (the Monstera's primaries down each field's middle and
faint secondaries; the rubber plant's fine laterals and its bronze rim; the corn plant's broad lime band down the
middle, streaked, and its fine parallel veins), a waxy clear coat; the underside paler and duller, its midrib a ridge;
light through the blade (a Translucent BSDF, coloured as backlit leaves are). The basil: glossy and a little
translucent, each leaf its own green. THE REST: potting mix a little damp (Ground048), an unglazed terracotta pot with
the lime the water leaves on its foot (Clay005), a glazed stoneware cylinder in charcoal blue with its speckle
(Granite005A), a fibre-clay planter (Concrete017), expanded-clay pebbles, the corn plant's ringed bark, the coir pole's
fibre, green stems (the rubber plant's turning red-bronze toward its top), moulded plastic for the nursery liner, the
wire ties and the watering can; the basil's pot and saucer in fired clay (floor_tiles_08) and its compost.
"""

import os

from ...materials.photo import Library, Mat, assign, image

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = None
# the sets at their real sizes (metres a tile)
S = {'clay': ('Clay005_2k', 0.4), 'soil': ('Ground048_2k', 0.6), 'speckle': ('Granite005A_2k', 0.35), 'prints': ('Fingerprints002_2k', 0.2),
     'concrete': ('Concrete017_1k', 0.8), 'plastic': ('Plastic013A_2k', 0.4), 'tile': ('floor_tiles_08_2k', 1.525)}
ASPECT = {}


def library():
    """the houseplants' CC0 library (cc0.json)"""
    return Library(os.path.join(HERE, 'cc0.json'))


def sfile(k, key):
    return LIB.tex(S[k][0], key)


def photo(M, k, vec_m, keys=('diff', 'rough', 'displacement'), box=False):
    """a set's maps at its real size through a vector in metres (u across the picture's width; v by its own aspect)"""
    if k not in ASPECT:
        im = image(sfile(k, 'diff'), True)
        ASPECT[k] = im.size[0] / max(1, im.size[1])
    w = S[k][1]
    v = M.mapping(vec_m, (1.0 / w, ASPECT[k] / w, 1.0 / w))
    return {key: M.tex(sfile(k, key), v, color=(key == 'diff'), box=box) for key in keys}


def m_plastic(name, base, r0=0.42, bump_m=0.00003, sss=0.0):
    """moulded plastic (Plastic013A's skin as a bump)"""
    M = Mat(name)
    ov = M.obj()
    p = photo(M, 'plastic', ov, ('rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], bump_m)
    rough = M.add(r0, M.mul(M.sub(p['rough'].outputs[0], 0.5), 0.15))
    ex = {}
    if sss:
        ex.update({'Subsurface Weight': sss, 'Subsurface Radius': (0.01, 0.01, 0.01)})
    return M.done(M.rgb(base), rough, 0.0, ex)


def m_soil(name, damp=0.3):
    """potting mix (Ground048: peat and bark), a little damp from the last watering"""
    M = Mat(name)
    p = photo(M, 'soil', M.obj(), ('diff', 'rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.004)
    col = M.tint(p['diff'].outputs[0], (0.75, 0.68, 0.6), desat=0.2, gain=0.8)
    return M.done(col, M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.75 - damp * 0.3, 0.95))


def m_terracotta(name, saucer=False, z0=0.0):
    """an unglazed thrown terracotta pot (Clay005's mottle, warm orange): the lime the water leaves on its foot and lower
    wall (water wicks through the clay and dries white), darker where the clay is still damp from the saucer. z0: the
    height (mm) the pot stands on"""
    M = Mat(name)
    ov = M.obj()
    p = photo(M, 'clay', ov, ('diff', 'rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.0003)
    col = M.tint(p['diff'].outputs[0], (1.25, 0.62, 0.42), desat=0.3, gain=0.62)
    X, Y, Z = M.pos_mm()
    Z = M.sub(Z, z0) if z0 else Z
    lime = M.mul(M.inv(M.sm(Z, 40.0, 150.0)), M.sm(M.noise(ov, 18.0, 4.0), 0.45, 0.7))
    if not saucer:
        damp = M.mul(M.inv(M.sm(Z, 20.0, 60.0)), 0.6)
        col = M.value(col, M.sub(1.0, M.mul(damp, 0.35)))
    col = M.mixc(M.mul(lime, 0.2 if saucer else 0.4), col, M.rgb((0.62, 0.58, 0.52)))
    return M.done(col, M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.75, 0.95))


def m_glazed_pot(name, base=(0.045, 0.06, 0.08)):
    """a glazed stoneware cylinder: a satin charcoal-blue glaze with the stoneware's speckle through it"""
    M = Mat(name)
    ov = M.obj()
    sp = photo(M, 'speckle', ov, ('diff',), box=True)['diff']
    col = M.value(M.rgb(base), M.lin(M.lum(sp.outputs[0]), 0.3, 0.7, 0.85, 1.25))
    fp = photo(M, 'prints', ov, ('diff',), box=True)['diff']
    rough = M.add(0.22, M.mul(M.sm(M.lum(fp.outputs[0]), 0.15, 0.5), 0.12))
    return M.done(col, rough, 0.0, {'Coat Weight': 0.2, 'Coat Roughness': 0.15})


def m_fibre_clay(name):
    """a fibre-clay planter: light warm grey, fine pores (Concrete017)"""
    M = Mat(name)
    p = photo(M, 'concrete', M.obj(), ('diff', 'rough', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.0004)
    col = M.value(M.rgb((0.50, 0.49, 0.46)), M.lin(M.lum(p['diff'].outputs[0]), 0.2, 0.6, 0.85, 1.12))
    return M.done(col, M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.65, 0.85))


def m_leca(name):
    """expanded clay pebbles: fired orange-brown, porous"""
    M = Mat(name)
    p = photo(M, 'clay', M.obj(), ('diff', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.0006)
    col = M.tint(p['diff'].outputs[0], (1.1, 0.55, 0.32), desat=0.2, gain=0.55)
    col = M.value(col, M.lin(M.voronoi(M.obj(), 160.0, 'F1'), 0.0, 0.6, 0.75, 1.1))
    return M.done(col, 0.9)


def m_bark(name, base):
    """the corn plant's canes: a tan, grey-brown bark ringed by old leaf scars (the rings are in the cane's form; the
    colour darkens in each groove: the form's own cavity is read by the light), Ground048's fibres as its grain"""
    M = Mat(name)
    ov = M.obj()
    p = photo(M, 'soil', M.mapping(ov, (1.0, 1.0, 0.25)), ('diff', 'displacement'), box=True)
    M.bump(p['displacement'].outputs[0], 0.0006)
    col = M.value(M.rgb(base), M.lin(M.lum(p['diff'].outputs[0]), 0.1, 0.5, 0.75, 1.15))
    col = M.value(col, M.lin(M.noise(ov, 14.0, 3.0), 0.3, 0.7, 0.85, 1.1))
    return M.done(col, 0.8)


def m_coir(name):
    """the moss pole's coir: coconut fibre wound on a stick, a mid brown with paler and darker strands (fibres a
    millimetre or two thick, a few centimetres long, upright)"""
    M = Mat(name)
    ov = M.obj()
    st = M.mapping(ov, (420.0, 420.0, 30.0))
    n1 = M.noise(st, 1.0, 8.0, rough=0.65)
    n2 = M.noise(M.mapping(ov, (160.0, 160.0, 14.0)), 1.0, 4.0)
    p = photo(M, 'soil', ov, ('diff', 'displacement'), box=True)
    M.bump(M.add(M.mul(p['displacement'].outputs[0], 0.3), M.add(M.mul(n1, 0.5), M.mul(n2, 0.4))), 0.004)
    col = M.value(M.rgb((0.075, 0.045, 0.022)), M.lin(M.add(M.mul(n1, 0.6), M.mul(n2, 0.4)), 0.3, 0.7, 0.55, 1.5))
    return M.done(col, 0.95, 0.0, {'Sheen Weight': 0.5, 'Sheen Roughness': 0.6})


def m_stem(name, base, tip=None, rough=0.45):
    """a green stem or petiole: smooth, a little glossy; tip: a colour it takes toward the plant's top (a rubber plant's
    new red-bronze growth), as (colour, z0 mm, z1 mm)"""
    M = Mat(name)
    ov = M.obj()
    col = M.value(M.rgb(base), M.lin(M.noise(ov, 20.0, 3.0), 0.3, 0.7, 0.85, 1.15))
    if tip:
        X, Y, Z = M.pos_mm()
        col = M.mixc(M.sm(Z, tip[1], tip[2]), col, M.rgb(tip[0]))
    return M.done(col, rough, 0.0, {'Subsurface Weight': 0.15, 'Subsurface Radius': (0.003, 0.006, 0.002)})


LEAF = {   # linear colours of each species, taken down to an albedo; the rubber plant's thick leathery blade lets little light through
    'rubber': dict(top=(0.010, 0.034, 0.010), young=(0.05, 0.045, 0.016), under=(0.06, 0.085, 0.04), rib=(0.20, 0.25, 0.08), rib_w=0.012,
                   trans=(0.16, 0.24, 0.03), r_top=0.16, r_under=0.45, coat=0.22, through=0.06, lat=0.06),
    'monstera': dict(top=(0.016, 0.060, 0.018), young=(0.04, 0.12, 0.028), under=(0.06, 0.12, 0.045), rib=(0.15, 0.28, 0.06), rib_w=0.014,
                     trans=(0.16, 0.32, 0.04), r_top=0.32, r_under=0.5, coat=0.12, through=0.16, lat=0.05),
    'dracaena': dict(top=(0.034, 0.120, 0.020), young=(0.05, 0.15, 0.025), under=(0.06, 0.12, 0.03), rib=(0.14, 0.21, 0.025), rib_w=0.004,
                     trans=(0.26, 0.38, 0.035), r_top=0.40, r_under=0.55, coat=0.04, through=0.28, lat=0.25),
}


def m_leaf(species, name=None):
    """a species' leaves (see the module doc). Every vertex of a blade carries leafdata (along 0..1, across 0..1 with
    the midrib at 0.5, which leaf, how old; its underside's age below zero) and, on the Monstera, leafq (where it lies
    across its vein's field)."""
    P = LEAF[species]
    M = Mat(name or f'houseplant_leaf_{species}')
    ld = M.attr('leafdata')
    sp = M.sep(ld.outputs['Vector'])
    along, across, ident = sp[0], sp[1], sp[2]
    age = ld.outputs['Alpha']
    under = M.inv(M.sm(age, -0.6, -0.4))                        # (0 above, 1 beneath)
    dm = M.m('ABSOLUTE', M.sub(across, 0.5))                    # 0 on the midrib, 0.5 at the margin
    young = M.inv(M.sm(M.m('ABSOLUTE', age), 0.0, 0.25))
    col = M.mixc(M.mul(young, 0.8), M.rgb(P['top']), M.rgb(P['young']))
    col = M.value(col, M.add(0.88, M.mul(ident, 0.24)))         # (each leaf its own green)
    hue = M.N.new('ShaderNodeHueSaturation')
    M.L.new(col, hue.inputs['Color'])
    M.L.new(M.add(0.49, M.mul(ident, 0.02)), hue.inputs['Hue'])
    col = hue.outputs[0]
    ov = M.obj()
    mott = M.noise(ov, 60.0, 3.0)
    col = M.value(col, M.lin(mott, 0.3, 0.7, 0.92, 1.08))
    rib_w = M.mul(P['rib_w'], M.sub(1.0, M.mul(along, 0.65)))
    rib = M.mul(M.inv(M.sm(dm, M.mul(rib_w, 0.6), rib_w)), M.inv(M.sm(along, 0.9, 1.0)))
    veins = 0.0
    if species == 'monstera':
        q = M.attr('leafq').outputs['Fac']
        vw = M.mul(0.05, M.sub(1.0, M.mul(dm, 1.2)))           # (a primary vein thins toward the margin)
        veins = M.mul(M.inv(M.sm(M.m('ABSOLUTE', q), M.mul(vw, 0.5), vw)), M.sm(dm, 0.02, 0.05))
        sec = M.sm(M.m('ABSOLUTE', M.sub(M.m('FRACT', M.mul(q, 3.0)), 0.5)), 0.47, 0.5)
        veins = M.mx(veins, M.mul(sec, P['lat']))                # (the secondaries are faint)
        col = M.value(col, M.add(1.0, M.mul(M.mul(M.sm(dm, 0.05, 0.4), M.sub(0.5, M.m('ABSOLUTE', q))), 0.12)))   # (the blade swells between veins: a little paler)
    elif species == 'rubber':
        lat = M.m('FRACT', M.mul(M.sub(along, M.mul(dm, 0.45)), 34.0))
        veins = M.mul(M.mul(M.sm(M.m('ABSOLUTE', M.sub(lat, 0.5)), 0.46, 0.5), M.sm(dm, 0.02, 0.06)), P['lat'])
        rim = M.sm(dm, 0.475, 0.5)
        col = M.mixc(M.mul(rim, M.add(0.25, M.mul(young, 0.6))), col, M.rgb((0.09, 0.05, 0.02)))
    else:
        # Dracaena fragrans 'Massangeana': a broad lime-yellow band down the middle, streaked along its length, and fine
        # parallel veins the length of the blade
        streak = M.noise(M.comb(M.mul(across, 70.0), M.mul(along, 2.0), M.mul(ident, 10.0)), 1.0, 2.0)
        bw = M.add(0.16, M.mul(M.sub(streak, 0.5), 0.10))
        band = M.inv(M.sm(dm, M.sub(bw, 0.03), M.add(bw, 0.03)))
        band = M.mul(band, M.lin(M.noise(M.comb(M.mul(across, 140.0), M.mul(along, 4.0), 0.0), 1.0, 2.0), 0.3, 0.7, 0.55, 1.0))
        col = M.mixc(M.mul(band, 0.85), col, M.rgb((0.26, 0.34, 0.04)))
        par = M.sm(M.m('ABSOLUTE', M.sub(M.m('FRACT', M.mul(across, 46.0)), 0.5)), 0.42, 0.5)
        veins = M.mul(par, P['lat'])
    col = M.mixc(M.mul(veins, 0.55), col, M.rgb(P['rib']))
    col = M.mixc(rib, col, M.rgb(P['rib']))
    col = M.mixc(under, col, M.mixc(M.mul(rib, 0.5), M.rgb(P['under']), M.rgb(P['rib'])))
    rough = M.mixf(under, M.add(P['r_top'], M.mul(M.sub(mott, 0.5), 0.1)), P['r_under'])
    bump_h = M.add(M.mul(rib, -1.0), M.mul(veins, -0.5))
    M.bump(bump_h, 0.0004)
    M.done(col, rough, 0.0, {'Coat Weight': M.mul(M.inv(under), P['coat']), 'Coat Roughness': 0.12})
    tr = M.N.new('ShaderNodeBsdfTranslucent')
    M.L.new(M.mixc(M.mul(veins, 0.5), M.rgb(P['trans']), M.rgb(tuple(v * 1.3 for v in P['trans']))), tr.inputs['Color'])
    if M.normal is not None:
        M.L.new(M.normal, tr.inputs['Normal'])
    mx = M.N.new('ShaderNodeMixShader')
    mx.inputs[0].default_value = P['through']
    M.L.new(M.bsdf.outputs[0], mx.inputs[1])
    M.L.new(tr.outputs[0], mx.inputs[2])
    M.L.new(mx.outputs[0], M.out.inputs[0])
    try:
        M.out.inputs['Thickness'].default_value = 0.0008
    except (KeyError, AttributeError):
        pass
    return M.mat


class _Mat3(Mat):
    ROUGH_MIN = 0.03


def m_basil_leaf(name, base=(0.022, 0.12, 0.014), stem=False):
    """basil: glossy, a little translucent (the sun through the leaves on a sill); darker toward the stem, each leaf its
    own green"""
    M = _Mat3(name)
    ov = M.obj()
    v = M.voronoi(ov, 140.0, 'F1')
    col = M.value(M.rgb(base), M.lin(M.noise(ov, 90.0, 2.0), 0.3, 0.7, 0.8, 1.25))
    if not stem:
        col = M.mixc(M.mul(M.sm(v, 0.0, 0.4), 0.0), col, M.rgb((0.06, 0.2, 0.03)))
        hs_ = M.N.new('ShaderNodeHueSaturation')
        M.L.new(col, hs_.inputs['Color'])
        M.L.new(M.lin(M.noise(ov, 25.0, 1.0), 0.3, 0.7, 0.47, 0.53), hs_.inputs['Hue'])
        col = hs_.outputs[0]
    m = M.done(col, 0.34 if not stem else 0.5, 0.0, {'Subsurface Weight': 0.0})
    tr = M.N.new('ShaderNodeBsdfTranslucent')
    M.L.new(M.value(col, 1.15), tr.inputs['Color'])
    mx = M.N.new('ShaderNodeMixShader')
    mx.inputs[0].default_value = 0.22 if not stem else 0.1
    M.L.new(M.bsdf.outputs[0], mx.inputs[1])
    M.L.new(tr.outputs[0], mx.inputs[2])
    M.L.new(mx.outputs[0], M.out.inputs[0])
    return m


def m_basil_pot(name):
    """the basil's pot and saucer: fired clay (floor_tiles_08's terracotta, warmer)"""
    M = _Mat3(name)
    w = S['tile'][1]
    v = M.mapping(M.obj(), (1.0 / w, 1.0 / w, 1.0 / w))
    p = {k: M.tex(sfile('tile', k), v, color=(k == 'diff'), box=True) for k in ('diff', 'rough', 'displacement')}
    M.bump(p['displacement'].outputs[0], 0.0002)
    return M.done(M.tint(p['diff'].outputs[0], (1.25, 0.62, 0.38), desat=0.2, gain=1.0), M.lin(p['rough'].outputs[0], 0.0, 1.0, 0.7, 0.9))


def m_compost(name):
    """the basil's compost: dark, a little mottled"""
    M = _Mat3(name)
    col = M.value(M.rgb((0.045, 0.03, 0.02)), M.lin(M.noise(M.obj(), 40.0, 3.0), 0.3, 0.7, 0.65, 1.35))
    return M.done(col, 0.95, 0.0)


# part name (the builders' prefixes) -> material key, and how each key's material is made
PARTS = (('plant_rubber_leaves', 'leaf_rubber'), ('plant_monstera_leaves', 'leaf_monstera'), ('plant_dracaena_leaves', 'leaf_dracaena'),
         ('plant_rubber_stems', 'rubber_stems'), ('plant_monstera_stems', 'monstera_petioles'), ('plant_dracaena_shoots', 'dracaena_shoots'),
         ('plant_dracaena_canes', 'dracaena_bark'), ('plant_monstera_pole', 'coir_pole'), ('plant_monstera_ties', 'tie_wire'),
         ('plant_rubber_soil', 'soil'), ('plant_monstera_soil', 'soil'), ('plant_dracaena_soil', 'soil'), ('plant_dracaena_pebbles', 'leca'),
         ('plant_monstera_pot', 'terracotta_pot'), ('plant_monstera_saucer', 'terracotta_saucer'), ('plant_rubber_pot_liner', 'nursery_pot'),
         ('plant_rubber_pot', 'glazed_pot'), ('plant_dracaena_pot', 'fibre_clay'), ('watering_can', 'watering_can'),
         ('basil_leaves', 'basil_leaf'), ('basil_stems', 'basil_stem'), ('basil_pot', 'basil_pot'), ('basil_saucer', 'basil_pot'),
         ('basil_compost', 'compost'))


def makers(prefix='houseplant', z0=0.0):
    """{key: a function making that key's material}; material names start with `prefix`"""
    P = prefix
    return {
        'leaf_rubber': lambda: m_leaf('rubber', f'{P}_leaf_rubber'), 'leaf_monstera': lambda: m_leaf('monstera', f'{P}_leaf_monstera'),
        'leaf_dracaena': lambda: m_leaf('dracaena', f'{P}_leaf_dracaena'),
        'rubber_stems': lambda: m_stem(f'{P}_rubber_stems', (0.06, 0.09, 0.03), tip=((0.16, 0.05, 0.03), z0 + 900.0, z0 + 1350.0), rough=0.4),
        'monstera_petioles': lambda: m_stem(f'{P}_monstera_petioles', (0.05, 0.13, 0.04), rough=0.35),
        'dracaena_shoots': lambda: m_stem(f'{P}_dracaena_shoots', (0.10, 0.12, 0.04), rough=0.5),
        'dracaena_bark': lambda: m_bark(f'{P}_dracaena_bark', (0.40, 0.31, 0.21)),
        'coir_pole': lambda: m_coir(f'{P}_coir_pole'),
        'tie_wire': lambda: m_plastic(f'{P}_green_tie_wire', (0.03, 0.18, 0.04), 0.3),
        'soil': lambda: m_soil(f'{P}_potting_soil'),
        'leca': lambda: m_leca(f'{P}_leca_pebbles'),
        'terracotta_pot': lambda: m_terracotta(f'{P}_terracotta_pot', z0=z0),
        'terracotta_saucer': lambda: m_terracotta(f'{P}_terracotta_saucer', saucer=True, z0=z0),
        'glazed_pot': lambda: m_glazed_pot(f'{P}_glazed_pot'),
        'nursery_pot': lambda: m_plastic(f'{P}_nursery_pot', (0.025, 0.025, 0.025), 0.55),
        'fibre_clay': lambda: m_fibre_clay(f'{P}_fibre_clay_planter'),
        'watering_can': lambda: m_plastic(f'{P}_watering_can', (0.62, 0.40, 0.01), 0.3, sss=0.15),
        'basil_leaf': lambda: m_basil_leaf(f'{P}_basil_leaf'),
        'basil_stem': lambda: m_basil_leaf(f'{P}_basil_stem', base=(0.06, 0.14, 0.03), stem=True),
        'basil_pot': lambda: m_basil_pot(f'{P}_basil_terracotta'),
        'compost': lambda: m_compost(f'{P}_basil_compost'),
    }


def key_of(name):
    """the material key of a part by its name (Blender's .001 suffixes ignored), or None"""
    base = name.split('.')[0]
    for prefix, key in PARTS:
        if base == prefix:
            return key
    return None


def apply(objects, lib=None, prefix='houseplant', z0=0.0, made=None):
    """Every houseplant part among `objects` given its material (made once per key; `made` a dict to share them between
    calls). lib: the CC0 library (default: this package's cc0.json). z0: the floor the plants stand on (mm), for the
    materials that read height. -> {key: material}"""
    global LIB
    LIB = lib or library()
    made = {} if made is None else made
    mk = makers(prefix, z0)
    for o in objects:
        if o.type != 'MESH':
            continue
        k = key_of(o.name)
        if k is None:
            continue
        if k not in made:
            made[k] = mk[k]()
        assign(o, made[k])
    return made
