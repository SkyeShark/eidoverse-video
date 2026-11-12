"""eidoblend.sets.unknown_force.news: the evening news at a data centre, the Blender 5.2 EEVEE edition of
eidoverse/sets/unknown_force/news.js (made for UNKNOWN FORCE; a free set for any piece).

A hyperscale data centre at night: a long windowless monolith, condenser rows and cooling towers on the roof with steam
plumes, a transformer yard, security floodlights on poles (the focal light), a chain-link fence with barbed wire between
the mark's side and the protest side. The pickets are featureless silhouettes (the DAISY funeral's crowd figures) with
handwritten signs, phones and flashlights; a news van and its light; the small town across the road. CLANKER is sprayed
on the monolith's wall (state spray paints it on). A generic news chyron is supplied for the screen-locked overlay.

    from eidoblend.sets.unknown_force import news
    N = news.build(scene)                                     # -> News: group, parts, update, cams, focal, look
    N.apply_look(scene)
    N.camera('crowd', scene)                                  # the set's five cameras, from N.cams
    from eidoblend.media import overlay
    ov = overlay.make_overlay_layer(scene, camera=scene.camera)
    N.parts['chyron'].place(ov, fov=42, aspect=16 / 9)        # the lower third, in the display-space overlay scene
    N.parts['chyron'].set_text(headline='ANY HEADLINE', ticker='YOUR TICKER')
    N.update(0.0, {'spray': 0.5, 'floods': 1.0})              # a still: sets everything, keys nothing
    # its moving parts on your own clock, KEYED (t in seconds from the scene's first frame, or from t0):
    N.animate(lambda t: {'spray': t / 2.5, 'pulse': 0.5 + 0.5 * math.sin(t * 3.0)}, frames=(1, 120))

Set-local metres, built in three's axes (+Y up, ground y = 0, the mark the origin facing +Z toward the fence, the
monolith's wall 12 m behind it) and converted once, three (x, y, z) -> Blender (x, -z, y). cams and focal are
set-local in Blender's axes (the sets' contract); cams_three, focal_three and the constants (CAMS, FOCAL, NEWS) keep
the WebGPU's numbers; camera(name) makes the camera. Every mesh sits in the set's frame (its object space is the
set's space, the JS's setP()), so the group can be parked anywhere.

How the light works, as in the WebGPU edition: the floods are painted analytically onto the ground, the pickets, their
signs, the fence and the steam, with the chain link's diamond shadow; those materials leave the real flood lamps out
(light linking: the lamps' receiver collection excludes them). The real flood lamps (850 cd against the 4200 painted)
light her, the building, the van and the posts. The wet ground mirrors every lamp as a streak toward the camera.
The steam and the hand lights are camera-facing billboards placed by Geometry Nodes from t (the JS placed them on the
CPU per frame); the pickets' arms, heads and signs pump with the chant in Geometry Nodes (the JS's positionNode).
"""

from __future__ import annotations

import json
import math

import numpy as np

from ... import common
from . import cn_lib as CL
from .cn_lib import (Geo, box_geometry, cylinder_geometry, lathe_geometry, sphere_geometry, plane_geometry,
                     tube_geometry, catmull_rom, m4, fit_text, hex_linear, extrude_polygon)

FZ = 3.2                       # the fence line
FH = 3.0                       # chain-link height
FX0, FX1 = -62, 62             # the fence runs along x
POLES = [[-24, -6.5], [-12.5, -6.5], [-3.9, -6.5], [18.5, -6.5]]
POLE_H = 7.4
TILT = 0.5                     # the flood heads look down this far (rad)
FLOOD_ANGLE, FLOOD_PEN, FLOOD_I, FLOOD_REAL = 0.56, 0.45, 4200, 850
FACADE_Z, BX0, BX1, BH, BD = -12.0, -70, 46, 15.0, 48
GRAFF = {'x0': 1.2, 'x1': 15.2, 'y0': 0.6, 'y1': 4.1}
ROAD, WALK = {'z0': 5.4, 'z1': 15.0}, {'z0': 15.0, 'z1': 17.6}
STREET = [[-26, 16.9], [4, 16.9], [34, 16.9]]
WALLPACKS = [-62, -50, -38, -26, -14, -2, 8, 20, 34]
WP_Y = 8.2
VENTS = [[-11.5, -10.7], [16.5, -10.9]]
TOWERS = [[-46, -26], [-24, -33], [-2, -24], [24, -35]]
YARD = {'x0': 22, 'x1': 42, 'z0': -11.2, 'z1': -1.6}
VAN = [-12.5, 12.2]
NEWS_LIGHT = [-3.8, 2.6, 8.4]
SODIUM, HMI = (1.0, 0.56, 0.2), (0.86, 0.92, 1.0)
CELL, WN = 0.0354, 0.035        # chain link: 5.5 cm diamonds of 3.6 mm galvanised wire

NEWS = {'FZ': FZ, 'FH': FH, 'POLES': POLES, 'POLE_H': POLE_H, 'FACADE_Z': FACADE_Z, 'GRAFF': GRAFF, 'ROAD': ROAD,
        'WALK': WALK, 'STREET': STREET, 'VAN': VAN, 'NEWS_LIGHT': NEWS_LIGHT}

CAMS = {
    # through the chain link at her, low, the flood behind her shoulder
    'fence': {'pos': [-0.45, 1.0, 5.2], 'target': [1.6, 2.3, -3.0], 'fov': 46},
    # over the pickets' heads toward the fence and the glare: silhouettes, signs, phones
    'crowd': {'pos': [-4.6, 2.75, 17.6], 'target': [0.6, 2.0, 0.0], 'fov': 42},
    # CLANKER on the wall, her in the foreground
    'wall': {'pos': [2.6, 1.6, 2.9], 'target': [8.0, 2.3, FACADE_Z], 'fov': 52},
    # the establishing shot: the monolith and its steam, the floods, the fence, the crowd, the town
    'wide': {'pos': [-30, 17, 22], 'target': [2, 3, -8], 'fov': 50},
    # over her shoulder: the protesters through the fence and the town beyond
    'pov': {'pos': [0.75, 1.8, -1.7], 'target': [0.2, 1.7, 10], 'fov': 42},
}
FOCAL = (POLES[2][0], POLE_H, POLES[2][1])      # the floodlight behind her: the sun cones' source (three space)
LOOK = {'name': 'argue', 'exposure': 1.0, 'bloom': {'strength': 0.6, 'radius': 0.5, 'threshold': 0.7},
        'fog': {'color': 0x0b1018, 'density': 0.011}}
UNIFORMS = {'t': 0.0, 'spray': 1.0, 'floods': 1.0, 'lights': 1.0, 'chant': 1.0, 'pulse': 0.0, 'blink': 1.0,
            'pix': 0.001, 'chyron_variant': 0.0}
ROLE_ID = {'down': 0, 'sign': 1, 'phone': 2, 'torch': 3, 'fist': 4, 'crew': 5}


def _js_round(x):
    return int(math.floor(x + 0.5))


class News(CL.SetBase):
    """What build() returns (see the module docstring)."""

    def apply_look(self, scene, raytracing=False, view_look=None):
        """AgX at view_exposure(look exposure), global illumination (fast GI), reflections from the light probes (the
        wet ground's mirror is painted; raytracing=True screen-traces them instead), shadows on; the fog is in the
        materials (FogExp2, built with opts fog=True). view_look: an AgX look for the scene (cn_lib.ACES_LIKE_LOOK
        follows the WebGPU frames' ACES tone); None leaves the scene's look as it is."""
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.exposure = CL.view_exposure(self.look['exposure'])
        if view_look is not None:
            scene.view_settings.look = view_look
        CL.eevee_gi(scene, raytracing)
        self.set_u('pix', CL.pix_of(scene))
        return scene


def build(scene=None, opts=None, collection=None, name='set:news'):
    """Build the news set into `scene`. news.js reads no opts; these are the Blender edition's, for a piece of your
    own: world (True: the set's night environment + hemisphere light become scene.world, lighting the set through
    EEVEE), fog (True: the materials carry look['fog'] as three's FogExp2 did), shadows (True), crowd (True: the 79
    pickets), tag ('CLANKER': the word sprayed on the wall), signs (up to eight messages for the pickets' signs, each a list of lines or 'LINE / LINE';
    None keeps a slot's own), chainShadow (False: the fence, its chain link and its steel, casts no shadow from the
    real lamps, as none did in the WebGPU set), signNormals ('rest': the painted floods light the raised signs by their
    hanging-pose normals as news.js's positionNode left them, the crowd side bright; 'posed': by their true normals)."""
    import bpy
    sc = scene or bpy.context.scene
    opts = dict(opts or {})
    shadows = opts.get('shadows', True)
    fog = LOOK['fog'] if opts.get('fog', True) else None

    col = collection or bpy.data.collections.new(name)
    if collection is None:
        sc.collection.children.link(col)
    root = bpy.data.objects.new(name, None)
    root.empty_display_size = 2.0
    col.objects.link(root)
    for k, v in UNIFORMS.items():
        root[k] = float(v)
    L = CL.make_lib('news', owner=root, collection=col)
    L.own(root)
    L.own(col)
    N = News(L, root, col)
    N.set_cams(CAMS, FOCAL)                          # cams / focal in Blender's axes; cams_three / focal_three
    N.look = {k: (dict(v) if isinstance(v, dict) else v) for k, v in LOOK.items()}
    fam = CL.fam
    M = {}
    N.materials = M
    no_floods = []                        # objects the real flood lamps leave out (they carry the painted floods)

    # ------------------------------------------------------------------------ texture sets (CC0, the library)
    S = {
        'asphalt': L.pbr('Asphalt025C', res='2k', disp=True),
        'gravel': L.pbr('Gravel041'),
        'card': L.pbr('Cardboard002'),
        'conc': L.pbr('Concrete048'),
        'concD': L.pbr('Concrete033'),
        'concL': L.pbr('Concrete034', res='2k'),
        'galv': L.pbr('Metal049A', met=True),
        'paint': L.pbr('PaintedMetal012'),
        'corr': L.pbr('CorrugatedSteel009', res='2k'),
        'shingle': L.pbr('Asphalt012'),
        'grass': L.pbr('Ground037', res='2k'),
        'mud': L.pbr('Ground106', res='2k'),
        'siding': L.pbr('PaintedWood009C', res='2k'),
    }

    # a night environment for the metals: cold sky, sodium glow at the horizon, the floods' glare toward -Z
    def env_fn(d):
        x, y, z = d
        up, dn = max(0.0, y), max(0.0, -y)
        r = 0.004 + 0.012 * math.exp(-up * 6)
        g = 0.006 + 0.014 * math.exp(-up * 6)
        b = 0.011 + 0.02 * math.exp(-up * 5)
        hz = math.exp(-abs(y) * 9)
        r += 0.06 * hz; g += 0.034 * hz; b += 0.014 * hz
        fl = math.pow(max(0.0, -z), 12) * math.exp(-(y - 0.25) * (y - 0.25) * 14)
        r += 0.9 * fl; g += 0.95 * fl; b += 1.0 * fl
        r += 0.01 * dn; g += 0.01 * dn; b += 0.012 * dn
        return (r, g, b)
    env = L.env_tex(env_fn, 256, 128, name='news_env')
    N.parts['env'] = env
    # the night environment is the World at 0.7, with the hemisphere light: EEVEE lights every material with it
    if opts.get('world', True):
        N.world = CL.make_world(L, 'news_world', env, env_i=0.7, hemi=(0x22324a, 0x0a0806, 0.09), scene=sc)

    # -------------------------------------------------- the floods, as analytic light (with the fence's shadow)
    FL = [{'p': (float(x), POLE_H, float(z)), 'd': (0.0, -math.sin(TILT), math.cos(TILT))} for x, z in POLES]
    cos_out, cos_in = math.cos(FLOOD_ANGLE), math.cos(FLOOD_ANGLE * (1 - FLOOD_PEN))

    def chain(nb, x, y, soft, wn=WN):
        u, v = x / CELL, y / CELL
        a = nb.abs(nb.fract((u + v) * 0.5) - 0.5)
        b = nb.abs(nb.fract((u - v) * 0.5) - 0.5)

        def line(d):
            return nb.ss((0.5 - wn) - soft, (0.5 - wn) + soft, d)
        return nb.max(line(a), line(b))

    def fence_occ(nb, P, f):
        """How much of flood f reaches P through the fence (1 = clear); only points beyond the fence are shaded."""
        Lp = nb.w(f['p'])
        dz = P.z - f['p'][2]
        s = (FZ - f['p'][2]) / nb.max(dz, 1e-3)
        I = Lp + (P - Lp) * s
        crosses = nb.step(FZ + 0.02, P.z)
        in_mesh = nb.step(0.05, I.y) * nb.step(I.y, FH)
        blur = nb.clamp((1.0 - s) / nb.max(s, 0.05) * (0.012 / CELL), 0.02, 0.5)
        wire = chain(nb, I.x, I.y, blur, 0.075)
        post_d = nb.abs(nb.fract(I.x / 3.0 + 0.5) - 0.5) * 3.0
        post = (1.0 - nb.ss(0.04, 0.06 + blur * 0.1, post_d)) * nb.step(I.y, FH + 0.6)
        rail = 1.0 - nb.ss(0.03, 0.05 + blur * 0.1, nb.abs(I.y - FH))
        return 1.0 - crosses * nb.max(in_mesh * wire * 0.92, nb.max(post, rail) * 0.95)

    def flood_at(nb, P, Nv, shade=True):
        """Flood irradiance at P (set space) with normal Nv (None = omnidirectional), x U.floods x U.lights."""
        acc = 0.0
        for f in FL:
            Lv = nb.w(f['p']) - P
            d2 = nb.max(nb.dot(Lv, Lv), 0.25)
            Ld = Lv / nb.sqrt(d2)
            cos_a = nb.dot(-Ld, f['d'])
            cone = nb.ss(cos_out, cos_in, cos_a)
            ndl = nb.max(nb.dot(Nv, Ld), 0.0) if Nv is not None else 0.6
            occ = fence_occ(nb, P, f) if shade else 1.0
            acc = acc + cone * ndl * occ / d2
        return acc * FLOOD_I * nb.U('floods') * nb.U('lights')

    def streak(nb, P, V, Lpos, sa, se):
        """Wet-ground streak reflection of a light at Lpos seen from the camera through P (set space)."""
        R = nb.vec3(V.x, -V.y, V.z)
        D = nb.normalize(nb.w(tuple(float(c) for c in Lpos)) - P)
        rl = nb.max(nb.length(nb.vec2(R.x, R.z)) * nb.length(nb.vec2(D.x, D.z)), 1e-4)
        sin_az = (R.x * D.z - R.z * D.x) / rl
        d_el = R.y - D.y
        facing = nb.step(0.0, R.x * D.x + R.z * D.z)
        return nb.exp(sin_az * sin_az / (-sa * sa) - d_el * d_el / (se * se)) * facing

    EMIT = ([{'p': f['p'], 'c': HMI, 'k': 5.0, 'flood': f} for f in FL]
            + [{'p': (x - 0.0, 8.6, z - 1.9), 'c': SODIUM, 'k': 2.2} for x, z in STREET]
            + [{'p': (x, WP_Y, FACADE_Z + 0.35), 'c': SODIUM, 'k': 1.0} for x in WALLPACKS]
            + [{'p': tuple(NEWS_LIGHT), 'c': (0.9, 0.95, 1.0), 'k': 1.6}])

    # ----------------------------------------------- the real lights the analytic-lit materials still take
    lights = L.empty('news_lights', parent=root)
    Ls = {}

    def spot_(name_, col_, I, pos, tgt, angle, pen, shadow=True):
        return CL.spot(L, name_, col_, I, pos, tgt, angle, pen, parent=lights, shadow=shadow and shadows)
    Ls['floods'] = [spot_(f'news_flood_{i}', 0xe2ebff, FLOOD_REAL, f['p'],
                          [f['p'][0] + f['d'][0] * 10, f['p'][1] + f['d'][1] * 10, f['p'][2] + f['d'][2] * 10],
                          FLOOD_ANGLE, FLOOD_PEN) for i, f in enumerate(FL)]
    Ls['street'] = [spot_(f'news_street_{i}', 0xff9a42, 520, [x, 8.55, z - 1.9], [x, 0, z - 2.6], 0.95, 0.55)
                    for i, (x, z) in enumerate(STREET)]
    Ls['news'] = spot_('news_crew_led', 0xe8f0ff, 150, NEWS_LIGHT, [0, 1.45, 0], 0.32, 0.6)
    Ls['graffiti'] = spot_('news_graffiti', 0xff9e50, 380, [8.0, WP_Y, FACADE_Z + 0.6], [8.2, 1.8, FACADE_Z], 0.8, 0.6)
    Ls['hemi'] = {'sky': 0x22324a, 'ground': 0x0a0806, 'intensity': 0.09, 'world': getattr(N, 'world', None)}

    def pm(S_, **o):
        """news.js's pm: pbrMat with the set's fog (its environment is the World)."""
        o.setdefault('fog', fog)
        return L.pbr_mat(S_, **o)

    # ---------------------------------------------- the ground: compound yard, verge, road, sidewalk, lawns
    def ground_mat():
        Mt = L.mat('news_ground')
        nb = Mt.nb
        P = nb.P()
        xz = nb.vec2(P.x, P.z)

        def at(tx, tile):
            return nb.tex(tx, xz / tile)
        asp_c, _ = at(S['asphalt']['col'], 3.2)
        asp_r, _ = at(S['asphalt']['rgh'], 3.2)
        asp_n, _ = at(S['asphalt']['nrm'], 3.2)
        grv_c, _ = at(S['gravel']['col'], 1.6)
        grv_n, _ = at(S['gravel']['nrm'], 1.6)
        cl_c, _ = at(S['concL']['col'], 2.2)
        mud_c, _ = at(S['mud']['col'], 2.6)
        grs_c, _ = at(S['grass']['col'], 2.8)
        cd_c = cl_c * 0.7
        mac = nb.mx_fbm(nb.vec3(P.x * 0.07, 0.0, P.z * 0.07), 3, 2.0, 0.5)
        z, x = P.z, P.x
        in_yard = nb.step(YARD['x0'], x) * nb.step(x, YARD['x1']) * nb.step(YARD['z0'], z) * nb.step(z, YARD['z1'])
        apron = nb.step(z, FACADE_Z + 1.6)
        footing = nb.step(FZ - 0.35, z) * nb.step(z, FZ + 0.35)
        verge = nb.step(FZ + 0.35, z) * nb.step(z, ROAD['z0'])
        road = nb.step(ROAD['z0'], z) * nb.step(z, ROAD['z1'])
        walk = nb.step(WALK['z0'], z) * nb.step(z, WALK['z1'])
        lawn = nb.step(WALK['z1'], z)
        yard_asph = (1.0 - nb.max(in_yard, nb.max(apron, footing))) * nb.step(z, FZ - 0.35)
        asphalt = nb.max(yard_asph, road)
        # the asphalt's low spots hold water; the road's crown sheds it toward the gutters
        disp, _ = at(S['asphalt']['disp'], 3.2)
        big = nb.mx_fbm(nb.vec3(P.x * 0.18, 3.1, P.z * 0.18), 3, 2.0, 0.5)
        puddle = nb.ss(0.12, 0.3, big * 0.5 + (0.45 - disp.x)) * asphalt
        # markings on the road: faded edge lines and a dashed centre line
        edge_l = nb.ss(0.07, 0.05, nb.abs(z - (ROAD['z0'] + 0.35))) + nb.ss(0.07, 0.05, nb.abs(z - (ROAD['z1'] - 0.35)))
        centre = nb.ss(0.07, 0.05, nb.abs(z - (ROAD['z0'] + ROAD['z1']) / 2)) * nb.step(0.5, nb.fract(x / 6.0))
        wear = nb.ss(-0.2, 0.5, nb.mx_noise(nb.vec3(x * 1.3, 7.0, z * 1.3)))
        paint_w = nb.clamp(edge_l, 0, 1) * wear * road
        paint_y = nb.clamp(centre, 0, 1) * wear * road
        c = asp_c * 0.62
        c = nb.mix(c, cd_c * 0.55, nb.max(apron, footing))
        c = nb.mix(c, grv_c * 0.5, in_yard)
        c = nb.mix(c, nb.mix(mud_c, grv_c, 0.35) * 0.42, verge)
        c = nb.mix(c, cl_c * 0.5, walk)
        c = nb.mix(c, grs_c * 0.32, lawn)
        c = c * (mac * 0.25 + 1.0)
        joint = nb.ss(0.012, 0.004, nb.abs(nb.abs(nb.fract(x / 1.5) - 0.5) - 0.49)) * walk     # sidewalk joints
        c = c * (1.0 - joint * 0.5)
        c = nb.mix(c, (0.62, 0.62, 0.58), paint_w * 0.8)
        c = nb.mix(c, (0.62, 0.46, 0.12), paint_y * 0.8)
        c = nb.mix(c, c * 0.45, puddle)
        rough = asp_r.x * 0.5 + 0.18                                  # wet asphalt
        rough = nb.mix(rough, asp_r.x * 0.4 + 0.34, nb.max(apron, footing))
        rough = nb.mix(rough, 0.85, nb.max(in_yard, verge))
        rough = nb.mix(rough, asp_r.x * 0.3 + 0.45, walk)
        rough = nb.mix(rough, 0.95, lawn)
        rough = nb.mix(rough, 0.04, puddle)
        nrm = nb.mix(asp_n, grv_n, nb.max(in_yard, nb.max(verge, lawn)))
        nrm = nb.mix(nrm, (0.5, 0.5, 1.0), puddle)
        # the floods painted with the chain link's shadow; then the wet streaks of every light toward the camera
        flood = flood_at(nb, P, (0.0, 1.0, 0.0)) * (1 / math.pi)
        cam = nb.cam_local()
        V = nb.normalize(P - cam)
        cosv = nb.clamp(-V.y, 0, 1)
        F = 0.02 + nb.pow(1.0 - cosv, 5.0) * 0.98
        wet = nb.max(asphalt * 0.75, nb.max(apron, footing) * 0.4) + puddle * 1.2 + walk * 0.25
        refl = nb.w((0.0, 0.0, 0.0))
        for e in EMIT:
            k = streak(nb, P, V, e['p'], 0.012, 0.16) * e['k']
            if e.get('flood'):
                R = nb.vec3(V.x, -V.y, V.z)
                k = k * nb.ss(cos_out - 0.25, cos_in, nb.dot(-R, e['flood']['d'])) * nb.U('floods')
            refl = refl + nb.w(e['c']) * k
        refl = refl + nb.w(SODIUM) * (streak(nb, P, V, (8.0, WP_Y, FACADE_Z + 0.35), 0.02, 0.25) * 0.5)
        em = c * flood + refl * (F * 0.6 + 0.03) * wet * nb.U('lights')
        return Mt.standard(c, rough=nb.clamp(rough, 0.03, 1), metal=0.0, normal=nb.normal_map(nrm, 0.8), emissive=em,
                           fog=fog)
    M['ground'] = ground_mat()
    ground_geo = plane_geometry(260, 190).apply(m4(-5, 0, 18, -math.pi / 2, 0, 0))
    ground = L.mesh_object('news_ground', ground_geo, M['ground'], parent=root)
    no_floods.append(ground)

    # ------------------------------------------------------------------------------------------- surfaces
    M['galv'] = pm(S['galv'], name='news_galv', tile=0.8, metal=0.85, rough=(0.6, 0.25), tint=[0.55, 0.57, 0.6], macro=0.3)
    M['paintGrey'] = pm(S['paint'], name='news_paint_grey', tile=1.2, metal=0.2, rough=(0.7, 0.2),
                        tint=[0.36, 0.39, 0.41], macro=0.25)
    M['paintDark'] = pm(S['paint'], name='news_paint_dark', tile=0.8, metal=0.3, rough=(0.6, 0.25),
                        tint=[0.07, 0.075, 0.08])
    M['corr'] = pm(S['corr'], name='news_corrugated', tile=1.6, metal=0.5, rough=(0.8, 0.15), tint=[0.4, 0.42, 0.44],
                   macro=0.3)
    M['concrete'] = pm(S['concD'], name='news_concrete', tile=1.8, rough=(0.8, 0.15), tint=[0.55, 0.55, 0.55])

    def simple(name_, col_fn, rough, metal=0.0, coat=None):
        Mt = L.mat(name_)
        nb = Mt.nb
        return Mt.standard(col_fn(nb), rough=rough, metal=metal, coat=coat, coat_rough=0.03, fog=fog)
    M['porcelain'] = simple('news_porcelain',
                            lambda nb: nb.w((0.16, 0.085, 0.05)) * (nb.mx_noise(nb.P() * 8.0) * 0.15 + 1.0), 0.18)
    M['rubber'] = simple('news_rubber', lambda nb: nb.w((0.018, 0.018, 0.02)) * (nb.mx_noise(nb.P() * 30.0) * 0.2 + 1.0),
                         0.85)
    M['glassDark'] = simple('news_glass_dark', lambda nb: nb.w((0.01, 0.012, 0.016)), 0.06, coat=1.0)

    def lamp(rgb, k, name_, *u):
        """Light sources the eye looks into (unlit): rgb x k x the named uniforms."""
        Mt = L.mat(name_)
        nb = Mt.nb
        c = nb.w(tuple(rgb)) * k
        for un in u:
            c = c * nb.U(un)
        return Mt.unlit(c, fog=fog)
    M['hmiLens'] = lamp(HMI, 9.0, 'news_hmi_lens', 'floods', 'lights')
    M['sodiumLens'] = lamp(SODIUM, 5.0, 'news_sodium_lens', 'lights')
    M['ledPanel'] = lamp((0.9, 0.95, 1.0), 6.0, 'news_led', 'lights')
    M['aviation'] = lamp((1.0, 0.05, 0.03), 6.0, 'news_aviation', 'blink')

    # ------------------------------------------------------------------------------------------- the monolith
    graff = _graffiti(L, fam, opts.get('tag', 'CLANKER'))
    PAINT_FILL, PAINT_LINE = hex_linear(0xff1f8a), hex_linear(0xf2f1ec)

    def facade_mat():
        """Precast panels (3 m reveals, a band at 9.6 m), rain streaks from the parapet, the louvre band, the wall
        packs' pools, the paint."""
        Mt = L.mat('news_facade')
        nb = Mt.nb
        P = nb.P()
        uvw = nb.vec2(P.x, P.y)
        c0, _ = nb.tex(S['conc']['col'], uvw / 3.0)
        r0, _ = nb.tex(S['conc']['rgh'], uvw / 3.0)
        n0, _ = nb.tex(S['conc']['nrm'], uvw / 3.0)
        panel_x = nb.abs(nb.fract(P.x / 3.0) - 0.5) * 3.0
        reveal = nb.ss(0.03, 0.012, 1.5 - panel_x) + nb.ss(0.03, 0.012, nb.abs(P.y - 9.6))
        streaks = nb.ss(0.35, 0.8, nb.mx_noise(nb.vec3(P.x * 1.8, P.y * 0.08, 3.0)) * 0.5 + 0.5) * nb.ss(4, BH, P.y)
        panel_tone = nb.hash21(nb.vec2(nb.floor(P.x / 3.0), nb.floor(P.y / 9.6))) * 0.12 + 0.94
        louvre = nb.step(11.2, P.y) * nb.step(P.y, 13.4)
        slat = nb.ss(0.3, 0.5, nb.abs(nb.fract(P.y / 0.16) - 0.5) * 2.0)
        c = c0 * (0.5, 0.52, 0.55) * panel_tone * (1.0 - streaks * 0.4) * (1.0 - nb.clamp(reveal, 0, 1) * 0.6)
        c = nb.mix(c, nb.w((0.05, 0.055, 0.06)) * (slat * 0.6 + 0.4), louvre)
        gu = nb.vec2((P.x - GRAFF['x0']) / (GRAFF['x1'] - GRAFF['x0']), (P.y - GRAFF['y0']) / (GRAFF['y1'] - GRAFF['y0']))
        in_g = nb.step(0, gu.x) * nb.step(gu.x, 1) * nb.step(0, gu.y) * nb.step(gu.y, 1)
        g_rgb, g_a = nb.tex(graff, gu, extension='EXTEND')
        show = nb.ss(0.0, 0.025, nb.U('spray') - g_rgb.z)
        fill_a, line_a, drip_a = g_rgb.x * show * in_g, g_rgb.y * show * in_g, g_a * show * in_g
        c = nb.mix(c, nb.w(PAINT_FILL) * 0.85, nb.clamp(nb.max(fill_a, drip_a), 0, 1))
        c = nb.mix(c, nb.w(PAINT_LINE) * 0.8, line_a)
        paint_a = nb.clamp(fill_a + line_a + drip_a, 0, 1)
        pools = 0.0
        for wx in WALLPACKS:
            dx, dy = P.x - wx, P.y - WP_Y
            cone = nb.exp(dx * dx * -0.05 / (nb.max((WP_Y + 0.5) - P.y, 0.6) * 0.25))
            pools = pools + cone * nb.exp(nb.max(-dy, 0.0) * -0.16) * nb.step(P.y, WP_Y + 0.2)
        em = c * pools * SODIUM * 0.55 * nb.U('lights')
        return Mt.standard(c, rough=nb.clamp(nb.mix(nb.mix(r0.x * 0.5 + 0.45, 0.5, louvre), 0.38, paint_a), 0.05, 1),
                           metal=louvre * 0.4, normal=nb.normal_map(n0, 0.7), emissive=em, fog=fog)
    M['facade'] = facade_mat()
    bld = L.empty('news_monolith', parent=root)
    fb = L.bucket('news_facade')
    fb.box(BX1 - BX0, BH, BD, (BX0 + BX1) / 2, BH / 2, FACADE_Z - BD / 2)
    fb.box(BX1 - BX0 + 0.6, 1.0, 0.6, (BX0 + BX1) / 2, BH + 0.5, FACADE_Z - 0.3)          # the parapet
    flags_m = {'assembly': 'news_monolith'}
    fb.mesh(M['facade'], parent=bld, flags=flags_m)
    L.bucket('news_plinth').box(BX1 - BX0, 0.5, 0.25, (BX0 + BX1) / 2, 0.25, FACADE_Z + 0.12).mesh(
        M['concrete'], parent=bld, flags=flags_m)
    wp, wl = L.bucket('news_wallpacks'), L.bucket('news_wallpack_lens')
    for x in WALLPACKS:
        wp.box(0.5, 0.36, 0.3, x, WP_Y, FACADE_Z + 0.15)
        wl.box(0.42, 0.04, 0.22, x, WP_Y - 0.19, FACADE_Z + 0.17)
    wp.mesh(M['paintDark'], parent=bld, flags=flags_m)
    wl.mesh(M['sodiumLens'], parent=bld, shadow=False, flags=flags_m)
    # the roof: condenser rows along the front edge (a serrated skyline), cooling towers, stacks, aviation lights

    def units_post(d):
        """On the top: the round fan grille (rings + spokes), darker inside. Read in each unit's own frame (the JS
        named positionLocal; three's InstanceNode had already moved it into the group's frame, which put every unit's
        grille at the set's origin, off the roof: the unit frame here is what the code describes)."""
        nb = d['nb']
        q = nb.attr('ul', 'v')
        top = nb.step(0.7, nb.N_local().y)
        rr = nb.length(nb.vec2(q.x, q.z))
        ring = nb.step(rr, 0.85)
        grille = (nb.ss(0.25, 0.45, nb.abs(nb.fract(rr * 9.0) - 0.5))
                  * nb.ss(0.2, 0.4, nb.abs(nb.fract(nb.atan2(q.z, q.x) * (6 / math.pi)) - 0.5)))
        return {'col': nb.mix(d['col'], nb.w((0.02, 0.02, 0.02)) + grille * 0.05, ring * top)}
    M['units'] = pm(S['galv'], name='news_units', tile=1.0, metal=0.6, rough=(0.6, 0.3), tint=[0.42, 0.44, 0.46],
                    post=units_post)
    ub = L.bucket('news_roof_units')
    for zr in (FACADE_Z - 3.0, FACADE_Z - 6.2):
        x = BX0 + 3
        while x < BX1 - 3:
            ug = box_geometry(2.4, 1.5, 2.0)
            ug.attrs['ul'] = ug.pos.copy()
            ub.add(ug, m4(x, BH + 0.75, zr), uv='keep')
            x += 3.0
    ub.mesh(M['units'], parent=bld, flags=flags_m)
    tb, ts = L.bucket('news_towers'), L.bucket('news_tower_stacks')
    for x, z in TOWERS:
        tb.box(9, 3.6, 9, x, BH + 1.8, z)
        for ox, oz in ((-2.2, -2.2), (2.2, -2.2), (-2.2, 2.2), (2.2, 2.2)):
            ts.add(cylinder_geometry(1.55, 1.7, 1.6, 20, 1, True), m4(x + ox, BH + 3.6 + 0.8, z + oz), uv='keep',
                   uv_scale=[6, 1])
    for x, z in ((-55, -40), (30, -50)):
        ts.add(cylinder_geometry(0.6, 0.7, 7, 16), m4(x, BH + 3.5, z), uv='keep', uv_scale=[3, 3])
    tb.mesh(M['corr'], parent=bld, flags=flags_m)
    ts.mesh(M['galv'], parent=bld, flags=flags_m)
    av = L.bucket('news_aviation')
    for x, z in [[BX0 + 0.5, FACADE_Z - 0.5], [BX1 - 0.5, FACADE_Z - 0.5], [BX0 + 0.5, FACADE_Z - BD + 0.5],
                 [BX1 - 0.5, FACADE_Z - BD + 0.5]] + [list(t) for t in TOWERS]:
        y = BH + 1.25 if (abs(z - FACADE_Z) < 2 or z < FACADE_Z - BD + 2) else BH + 4.6
        av.add(sphere_geometry(0.22, 10, 8), m4(x, y, z), uv='keep')
    av.mesh(M['aviation'], parent=bld, shadow=False, flags=flags_m)
    N.parts['monolith'] = bld

    # -------------------------------------------- the fence: chain link, posts, rails, outriggers, barbed wire
    def chain_mat():
        Mt = L.mat('news_chainlink')
        nb = Mt.nb
        P = nb.P()                                              # the set frame: x along the fence, y up
        fw_u = nb.view_z() * nb.U('pix') * (1.0 / CELL) * (1.0 + 1.0 / nb.max(nb.facing(), 0.08))
        soft = nb.clamp(fw_u * 0.6, 0.004, 0.5)
        cov = chain(nb, P.x, P.y, soft)
        # sub-pixel cells: fall back to the mean coverage (a grey haze) instead of shimmering moire
        coverage = nb.mix(cov, 0.13, nb.ss(0.35, 0.9, fw_u))
        sag = nb.ss(0.0, 0.08, P.y) * nb.ss(FH, FH - 0.08, P.y)
        gc, _ = nb.tex(S['galv']['col'], nb.vec2(P.x, P.y) / 0.7)
        # wires glint in the floods (lit from either side: thin cylinders), the street's sodium from behind
        em = nb.w(HMI) * flood_at(nb, P, None, False) * 0.005 + nb.w(SODIUM) * 0.002
        return Mt.standard(gc * (0.3, 0.31, 0.33), rough=0.5, metal=0.8, emissive=em, alpha=coverage * sag,
                           method='BLENDED', fog=fog)
    M['chain'] = chain_mat()
    fence = L.empty('news_fence', parent=root)
    flags_f = {'assembly': 'news_fence', 'noSupportCheck': True}
    chain_geo = plane_geometry(FX1 - FX0, FH).translate((FX0 + FX1) / 2, FH / 2, FZ)
    # the fence (its chain link, posts, rails, outriggers, wire and signs) casts no shadow from the real lamps (opts
    # chainShadow): the painted floods carry its shadow, and the WebGPU lamps cast none. With it, the crew's LED behind
    # the fence (the key on the mark) threw the chain link's diamonds and the posts' and rails' bars across the wall
    # and the tag
    chain_shadow = bool(opts.get('chainShadow', False)) and shadows
    chain_ob = L.mesh_object('news_chainlink', chain_geo, M['chain'], parent=fence, flags=flags_f,
                             shadow=chain_shadow)
    no_floods.append(chain_ob)
    fbs = L.bucket('news_fence_steel')
    x = FX0
    posts = []
    while x <= FX1 + 1e-6:
        posts.append(x)
        x += 3
    for x in posts:
        fbs.add(cylinder_geometry(0.045, 0.045, FH + 0.25, 10), m4(x, (FH + 0.25) / 2, FZ - 0.05), uv='keep',
                uv_scale=[0.3, 3])
        # the 45 deg outrigger arm, leaning out toward the protesters
        fbs.add(cylinder_geometry(0.022, 0.022, 0.62, 6), m4(x, FH + 0.25 + 0.22, FZ - 0.05 + 0.22, math.pi / 4, 0, 0),
                uv='keep')

    def rail(y, z, r):
        fbs.add(cylinder_geometry(r, r, FX1 - FX0, 8), m4((FX0 + FX1) / 2, y, z, 0, 0, math.pi / 2), uv='keep',
                uv_scale=[1, 40])
    rail(FH, FZ - 0.05, 0.03)
    rail(0.08, FZ - 0.05, 0.02)
    bw = L.bucket('news_barbed')
    barb = box_geometry(0.003, 0.05, 0.003)
    for k in range(3):
        y, z = FH + 0.27 + k * 0.14, FZ - 0.05 + 0.27 + k * 0.14
        # twisted strand with barbs every 12 cm
        bw.add(cylinder_geometry(0.004, 0.004, FX1 - FX0, 4), m4((FX0 + FX1) / 2, y, z, 0, 0, math.pi / 2), uv='keep')
        xb = float(FX0)
        while xb < FX1:
            bw.add(barb, m4(xb, y, z, 0.6, 0, 0.5))
            xb += 0.12
    # the concertina coil riding the outriggers
    coil = []
    loops = _js_round((FX1 - FX0) / 0.45)
    for i in range(loops * 16 + 1):
        a = i / 16 * math.pi * 2
        xc = FX0 + (i / 16) * 0.45
        coil.append((xc + math.sin(a) * 0.05, FH + 0.62 + math.cos(a) * 0.3, FZ + 0.3 + math.sin(a) * 0.3))
    bw.add(tube_geometry(catmull_rom(coil), loops * 16, 0.004, 3, False), None, uv='keep')
    fbs.mesh(M['galv'], parent=fence, shadow=chain_shadow, flags=flags_f)
    bw.mesh(M['galv'], parent=fence, shadow=chain_shadow, flags=flags_f)
    # signs on the fence: generic private-property and high-voltage warnings
    sign_tex = _fence_signs(L, fam)

    def fsign_post(d):
        nb = d['nb']
        return {'emissive': d['col'] * flood_at(nb, nb.P(), None, False) * 0.014}
    M['fenceSigns'] = pm(S['paint'], name='news_fence_signs', tile=0.5, rough=(0.5, 0.2),
                         recolor=lambda c, nb: nb.tex(sign_tex, nb.uv())[0] * (nb.lum(c) * 0.35 + 0.75), post=fsign_post)
    sg = L.bucket('news_fence_signs')

    def plate(x, y, z, tile, ry=0.0):
        g = plane_geometry(0.6, 0.6)
        g.uv[:, 0] = g.uv[:, 0] * 0.5 + tile * 0.5
        sg.add(g, m4(x, y, z, 0, ry, 0), uv='keep')
    plate(-6.6, 1.65, FZ + 0.02, 0); plate(11.4, 1.65, FZ + 0.02, 0); plate(-30, 1.65, FZ + 0.02, 0)
    plate(26, 1.6, YARD['z1'] + 0.03, 1); plate(37, 1.6, YARD['z1'] + 0.03, 1)
    sg.mesh(M['fenceSigns'], parent=fence, shadow=chain_shadow, flags=dict(flags_f, noZFightCheck=True))
    N.parts['fence'] = fence

    # ---------------------------------------------------- the floodlight poles, their heads and their beams
    poles = L.empty('news_floods', parent=root)
    pb, hb, lb = L.bucket('news_poles'), L.bucket('news_flood_heads'), L.bucket('news_flood_lenses')
    for x, z in POLES:
        pb.add(cylinder_geometry(0.11, 0.16, POLE_H + 0.3, 12), m4(x, (POLE_H + 0.3) / 2, z), uv='keep', uv_scale=[0.6, 6])
        pb.box(0.6, 0.06, 0.6, x, 0.03, z)
        pb.box(1.9, 0.1, 0.1, x, POLE_H + 0.18, z)                     # the crossarm
        for ox in (-0.62, 0.62):
            # a rectangular HMI flood: housing, lens toward +z tilted down, a visor
            mh = m4(x + ox, POLE_H, z + 0.12, TILT, 0, 0)
            hb.add(box_geometry(0.55, 0.42, 0.22), mh)
            lb.add(plane_geometry(0.47, 0.34), mh @ CL.translation(0, 0, 0.115), uv='keep')
            hb.add(box_geometry(0.58, 0.02, 0.22), mh @ CL.translation(0, 0.22, 0.12))
    flags_p = {'assembly': 'news_floods'}
    # the lamps sit in their fixtures: a fixture never shadows its own light
    pb.mesh(M['galv'], parent=poles, shadow=False, flags=flags_p)
    hb.mesh(M['paintDark'], parent=poles, shadow=False, flags=flags_p)
    lb.mesh(M['hmiLens'], parent=poles, shadow=False, flags=flags_p)
    N.parts['poles'] = poles

    def beam_mat():
        """Visible beams in the damp air: additive cones, brightest at the lamp, fading along and toward the rim."""
        Mt = L.mat('news_beams')
        nb = Mt.nb
        q = nb.P()                                    # the cone's frame: y along the beam (0 at the lamp, -len at the end)
        along = nb.clamp(-q.y / 26.0, 0, 1)
        rim = nb.pow(nb.facing(), 1.6)
        mist = nb.mx_fbm(nb.vec3(q.x * 0.4, q.y * 0.15 + nb.U('t') * 0.35, q.z * 0.4), 3, 2.0, 0.5) * 0.45 + 0.75
        return Mt.unlit(nb.w(HMI) * nb.pow(1.0 - along, 1.8) * rim * mist * 0.045 * nb.U('floods') * nb.U('lights'),
                        additive=True, fog=fog)
    M['beam'] = beam_mat()
    beams = L.empty('news_beams', parent=root)
    blen = 26.0
    r1 = math.tan(FLOOD_ANGLE * 0.8) * blen
    cone_geo = cylinder_geometry(0.2, r1, blen, 24, 1, True).translate(0, -blen / 2, 0)
    beam_obs = []
    for f in FL:
        for ox in (-0.62, 0.62):
            Mq = np.eye(4)
            Mq[:3, :3] = CL.quat_from_unit_vectors((0, -1, 0), f['d'])
            Mq[:3, 3] = (f['p'][0] + ox, f['p'][1], f['p'][2] + 0.25)
            beam_obs.append(L.mesh_object('news_beam', cone_geo, M['beam'], parent=beams, M3=Mq, shadow=False,
                                          flags={'noSupportCheck': True}))
    N.parts['beams'] = beams

    # --------------------------------------------- steam: plumes off the cooling towers, and low steam at the grates
    steam = _build_steam(L, N, root, FL, fog)
    N.parts['steam'] = steam

    # ------------------------------------------------------------------------------------- the transformer yard
    yard = L.empty('news_yard', parent=root)
    flags_y = {'assembly': 'news_yard'}
    tbk, fbk, bu, st = (L.bucket(n) for n in ('news_transformers', 'news_fins', 'news_bushings', 'news_gantry'))
    for x in (26, 32, 38):
        z = -6.4
        tbk.box(3.2, 3.0, 2.4, x, 1.5 + 0.3, z)
        tbk.box(3.6, 0.3, 2.8, x, 0.15, z)
        tbk.add(cylinder_geometry(0.45, 0.45, 2.4, 16), m4(x, 3.75, z - 0.6, 0, 0, math.pi / 2), uv='keep')
        for k in range(9):
            fbk.box(0.06, 2.4, 0.9, x - 1.95, 1.7, z - 1.0 + k * 0.25)
            fbk.box(0.06, 2.4, 0.9, x + 1.95, 1.7, z - 1.0 + k * 0.25)
        for k in range(3):
            pts = [[0.001, 0.0]] + [[0.14 if j % 2 else 0.09, j * 0.1] for j in range(15)] + [[0.001, 1.4]]
            bu.add(lathe_geometry(pts, 12), m4(x - 1.0 + k * 1.0, 3.3, z + 0.5), uv='keep')
        tbk.box(0.9, 1.6, 0.6, x + 1.3, 0.8, z + 1.7)                  # the control cabinet
    for z in (-2.6, -10.2):                                            # the gantry: two H-frames and their beam
        for x in (YARD['x0'] + 1.5, YARD['x1'] - 1.5):
            st.box(0.35, 9, 0.35, x, 4.5, z)
        st.box(YARD['x1'] - YARD['x0'] - 2.6, 0.4, 0.4, (YARD['x0'] + YARD['x1']) / 2, 8.8, z)
    tbk.mesh(M['paintGrey'], parent=yard, flags=flags_y)
    fbk.mesh(M['paintGrey'], parent=yard, flags=flags_y)
    bu.mesh(M['porcelain'], parent=yard, flags=flags_y)
    st.mesh(M['galv'], parent=yard, flags=flags_y)
    wbk = L.bucket('news_conductors')                                  # conductors sagging gantry -> bushings
    for x in (26, 32, 38):
        for k in range(3):
            a = np.array([x - 1.0 + k, 4.7, -5.9])
            b = np.array([x - 1.0 + k, 8.6, -2.6])
            mid = a + (b - a) * 0.5
            mid[1] -= 0.6
            wbk.add(tube_geometry(CL.QuadraticBezierCurve3(a, mid, b), 16, 0.02, 4, False), None, uv='keep')
    wbk.mesh(M['galv'], parent=yard, flags=flags_y)
    yf_geo = plane_geometry(YARD['x1'] - YARD['x0'], FH).translate((YARD['x0'] + YARD['x1']) / 2, FH / 2, YARD['z1'])
    yf = L.mesh_object('news_yard_chainlink', yf_geo, M['chain'], parent=yard, flags=flags_y, shadow=chain_shadow)
    no_floods.append(yf)
    M['amber'] = lamp((1.0, 0.55, 0.08), 4.0, 'news_amber')
    bc = L.bucket('news_beacons')
    for x in (26, 32, 38):
        bc.add(sphere_geometry(0.07, 8, 6), m4(x + 1.3, 1.7, -6.4 + 1.7), uv='keep')
    bc.mesh(M['amber'], parent=yard, shadow=False, flags=flags_y)
    N.parts['yard'] = yard

    # ---------------------------------------------------- the protest side: sidewalk curb, streetlights, the town
    street = L.empty('news_street', parent=root)
    flags_s = {'assembly': 'news_street'}

    def curb_post(d):
        nb = d['nb']
        P = nb.P()
        joint = nb.ss(0.012, 0.004, nb.abs(nb.abs(nb.fract(P.x / 1.5) - 0.5) - 0.49))
        return {'col': d['col'] * (1.0 - joint * 0.5)}
    M['walk'] = pm(S['concL'], name='news_walk', tile=2.0, rough=(0.5, 0.35), tint=[0.5, 0.5, 0.5], post=curb_post)
    L.bucket('news_curb').box(260, 0.15, WALK['z1'] - WALK['z0'], -5, 0.075, (WALK['z0'] + WALK['z1']) / 2).mesh(
        M['walk'], parent=street, flags=flags_s)
    spb, shb, slb = L.bucket('news_streetpoles'), L.bucket('news_streetheads'), L.bucket('news_streetlens')
    for x, z in STREET:
        spb.add(cylinder_geometry(0.09, 0.13, 9.0, 10), m4(x, 4.5, z), uv='keep', uv_scale=[0.6, 6])
        spb.box(0.08, 0.08, 2.2, x, 8.75, z - 1.05, rx=-0.08)
        shb.box(0.42, 0.18, 0.85, x, 8.62, z - 1.95)
        slb.box(0.34, 0.03, 0.7, x, 8.52, z - 1.95)
    spb.mesh(M['galv'], parent=street, flags=flags_s)
    shb.mesh(M['paintGrey'], parent=street, shadow=False, flags=flags_s)         # the lamp sits in its head
    slb.mesh(M['sodiumLens'], parent=street, shadow=False, flags=flags_s)

    def houses_post(d):
        nb = d['nb']
        P = nb.P()
        front = nb.step(0.6, -nb.N_local().z)
        wx, hy = nb.fract(P.x / 2.7), P.y
        win = (nb.ss(0.24, 0.27, wx) * nb.ss(0.76, 0.73, wx)
               * nb.max(nb.step(1.0, hy) * nb.step(hy, 2.3), nb.step(3.2, hy) * nb.step(hy, 4.3)) * front)
        idh = nb.hash21(nb.vec2(nb.floor(P.x / 2.7), nb.floor(hy / 2.2) + nb.floor(P.z)))
        lit = nb.step(0.52, idh)
        curtain = nb.mx_noise(nb.vec3(P.x * 3.0, P.y * 3.0, 1.0)) * 0.25 + 0.75
        glow = nb.w((1.0, 0.66, 0.32)) * curtain * lit * win * 1.6
        glass = nb.mix(d['col'], (0.01, 0.012, 0.016), win)
        return {'col': glass, 'emissive': glow * nb.U('lights'), 'rough': nb.mix(0.7, 0.08, win)}
    M['houses'] = pm(S['siding'], name='news_houses', tile=2.2, rough=(0.7, 0.2),
                     recolor=lambda c, nb: c * (0.2, 0.19, 0.18), post=houses_post)
    M['roofs'] = pm(S['shingle'], name='news_roofs', tile=1.6, rough=(0.8, 0.15), tint=[0.4, 0.38, 0.38])
    hbody, hroof = L.bucket('news_house_bodies'), L.bucket('news_house_roofs')
    r = CL.rng(12)
    for i in range(9):
        x = -58 + i * 14.5 + (r() - 0.5) * 3
        z = 30 + (r() - 0.5) * 4
        w = 9 + r() * 2.5
        d = 8
        h = 4.6 + (2.5 if r() < 0.4 else 0)
        hbody.box(w, h, d, x, h / 2, z)
        top = 2.6 + r() * 0.8
        rg = extrude_polygon([(-w / 2 - 0.4, 0), (w / 2 + 0.4, 0), (0, top)], d + 0.8).translate(0, 0, -(d + 0.8) / 2)
        hroof.add(rg, m4(x, h, z))
    hbody.mesh(M['houses'], parent=street, flags=flags_s)
    hroof.mesh(M['roofs'], parent=street, flags=flags_s)
    trees = L.bucket('news_trees')
    for i in range(16):
        x = -64 + i * 8.6 + (r() - 0.5) * 4
        z = 40 + r() * 8
        h = 7 + r() * 6
        trees.add(CL.cone_geometry(1.6 + r(), h, 8), m4(x, h / 2, z), uv='keep', uv_scale=[3, 3])
    M['trees'] = pm(S['grass'], name='news_trees', tile=1.0, recolor=lambda c, nb: c * (0.12, 0.16, 0.12), rough=(0.9, 0.1))
    trees.mesh(M['trees'], parent=street, flags=flags_s)
    N.parts['street'] = street

    # -------------------------------------------------------- the pickets: silhouettes, signs, phones, flashlights
    crowd = L.empty('news_crowd', parent=root)
    if opts.get('crowd', True):
        people = _build_crowd(L, N, crowd, S, fam, flood_at, fog, no_floods, signs=opts.get('signs'),
                              sign_normals=opts.get('signNormals', 'rest'))
    else:
        people = []
    crowd['people'] = json.dumps([{k: v for k, v in p.items() if k in ('x', 'z', 'variant', 'yaw', 'scale', 'seed',
                                                                         'role', 'theta', 'front', 'back')} for p in people])
    N.parts['crowd'] = crowd
    N.parts['people'] = people

    # ------------------------------------------------------------------------------- the news van and its light
    van = L.empty('news_van', parent=root)
    _build_van(L, M, van, S, fam, pm, fog)
    N.parts['van'] = van

    # -------------------------------------------------------------------------------------------- the night sky
    def sky_mat():
        Mt = L.mat('news_sky')
        nb = Mt.nb
        d = nb.normalize(nb.P())
        h = d.y
        zen, hor = (0.003, 0.005, 0.011), (0.02, 0.026, 0.04)
        c = nb.mix(hor, zen, nb.ss(0.0, 0.5, h))
        # sodium skyglow over the town (+z) and a cold glow over the data centre's floods (-z)
        c = c + nb.w(SODIUM) * 0.06 * (nb.exp(nb.max(h, 0.0) * -7.0) * nb.ss(-0.4, 0.6, d.z))
        c = c + nb.w(HMI) * 0.03 * (nb.exp(nb.max(h, 0.0) * -5.0) * nb.ss(-0.2, -0.8, d.z))
        hh = nb.max(h, 0.05)                                          # a low overcast lit from below
        cl = nb.mx_fbm(nb.vec3(d.x / hh * 0.6, d.z / hh * 0.6, nb.U('t') * 0.004), 4, 2.0, 0.5)
        cov = nb.ss(0.0, 0.55, cl + 0.15) * nb.ss(0.02, 0.18, h)
        c = nb.mix(c, nb.w((0.03, 0.026, 0.024)) + nb.w(SODIUM) * 0.02, cov * 0.85)
        return Mt.unlit(c, side='front')                             # fog: false
    M['sky'] = sky_mat()
    sky = L.mesh_object('news_sky', CL._inside_out(sphere_geometry(700, 48, 24)) if hasattr(CL, '_inside_out')
                        else _inside_out(sphere_geometry(700, 48, 24)), M['sky'], parent=root, shadow=False,
                        flags={'noSupportCheck': True})
    sky.visible_diffuse = sky.visible_glossy = False
    N.parts['sky'] = sky

    # ------------------------------------------------------- the chyron (for the screen-locked overlay layer)
    N.parts['chyron'] = _chyron(L, N, fam)

    # --------------------------------------------- the real floods leave the painted-flood materials out
    rec = bpy.data.collections.new('news_flood_receivers')
    L.own(rec)
    for o in no_floods:
        rec.objects.link(o)
    for co in rec.collection_objects:
        co.light_linking.link_state = 'EXCLUDE'
    for l in Ls['floods']:
        l.light_linking.receiver_collection = rec
    N.parts['flood_receivers'] = rec

    N.parts.update(ground=ground, lights=Ls, uniforms=root, materials=M,
                   graffiti={'texture': graff, 'rect': GRAFF, 'uniform': (root, '["spray"]')})

    # ------------------------------------------------------------------------------------------------ per frame
    def update(t, st=None, ctx=None, frame=None):
        """update(t, state): spray, chant, pulse, floods, lights (see CORRIDOR_NEWS.md); camera (the render camera:
        the moire guards read its pixel size; the billboards face the scene's active camera by themselves)."""
        st = dict(st or {})
        kw = {'ctx': ctx, 'frame': frame}
        N.set_u('t', t, **kw)
        N.set_u('spray', st.get('spray', 1.0), **kw)
        N.set_u('floods', st.get('floods', 1.0), **kw)
        N.set_u('lights', st.get('lights', 1.0), **kw)
        N.set_u('chant', st.get('chant', 1.0), **kw)
        N.set_u('pulse', st.get('pulse', 0.0), **kw)
        N.set_u('blink', 1.0 if (t % 1.6) < 0.8 else 0.05, interpolation='CONSTANT', **kw)
        cam = st.get('camera')
        if cam is not None or 'pix' in st:
            N.set_u('pix', st.get('pix') or CL.pix_of(bpy.context.scene, cam), **kw)
        fl = st.get('floods', 1.0) * st.get('lights', 1.0)
        for l in Ls['floods']:
            N.key_light(l, l['base'] * fl, **kw)
        for l in Ls['street'] + [Ls['news'], Ls['graffiti']]:
            N.key_light(l, l['base'] * st.get('lights', 1.0), **kw)
        hidden = not (fl > 0.001)
        for b in beam_obs:
            b.hide_render = hidden
            N.keyer(b, 'hide_render', interpolation='CONSTANT', **kw)
        ch = N.parts['chyron']['mesh']
        if 'chyron' in st and ch.parent is not None:          # shown / hidden once placed in an overlay (keyed)
            ch.hide_render = not st['chyron']
            N.keyer(ch, 'hide_render', interpolation='CONSTANT', **kw)
    N.update = update
    update(0.0, {})
    return N


# ======================================================================================= pieces of the build =====

def _inside_out(g: Geo) -> Geo:
    q = g.non_indexed()
    P = q.pos.reshape(-1, 3, 3)[:, ::-1].reshape(-1, 3)
    Nn = -q.nrm.reshape(-1, 3, 3)[:, ::-1].reshape(-1, 3)
    UV = q.uv.reshape(-1, 3, 2)[:, ::-1].reshape(-1, 2)
    return Geo(P, Nn, UV)


def _graffiti(L, fam, word='CLANKER'):
    """The tag (CLANKER, or opts tag), sprayed: R fill (with overspray), G outline, B the moment each pixel is painted
    (0..1), A drips. A tag wider than the wall's canvas is drawn smaller, so it stays on the wall."""
    W, H = 2048, 512
    word = str(word or 'CLANKER')
    fill, outl, drip = CL.create_canvas(W, H), CL.create_canvas(W, H), CL.create_canvas(W, H)
    gf, go, gd = (c.get_context('2d') for c in (fill, outl, drip))
    for c in (gf, go, gd):
        c.fill_style = '#000'
        c.fill_rect(0, 0, W, H)
    r = CL.rng(41)
    size = 470
    FONT = fam['caveat']
    gf.font = f'{size}px {FONT}'
    widths = [gf.measure_text(ch).width for ch in word]
    if sum(widths) > W * 0.94:                       # a longer tag than the JS's (CLANKER fits at 470 px)
        size = size * W * 0.94 / sum(widths)
        gf.font = f'{size}px {FONT}'
        widths = [gf.measure_text(ch).width for ch in word]
    track = 0.0 * size
    total = sum(widths) + track * (len(word) - 1)
    x = (W - total) / 2
    boxes = []
    for i, ch in enumerate(word):
        w = widths[i]
        rot = (r() - 0.5) * 0.14 - 0.05
        by = H * 0.8 + (r() - 0.5) * 30 - i * 5
        bx = x

        def draw(c, mode, ch=ch, bx=bx, w=w, by=by, rot=rot):
            c.save(); c.translate(bx + w / 2, by); c.rotate(rot)
            c.font = f'{size}px {FONT}'; c.text_align = 'center'; c.text_baseline = 'alphabetic'
            if mode == 'over':
                c.shadow_color = 'rgba(255,255,255,0.55)'; c.shadow_blur = 26; c.fill_style = 'rgba(255,255,255,0.4)'
                c.fill_text(ch, 0, 0)
            if mode == 'fill':
                c.shadow_blur = 0; c.fill_style = '#fff'; c.fill_text(ch, 0, 0)
            if mode == 'stroke':
                c.line_join = 'round'; c.line_width = 26; c.stroke_style = '#fff'; c.stroke_text(ch, 0, 0)
            c.restore()
        draw(gf, 'over')
        draw(go, 'stroke')
        boxes.append({'x0': x - 10, 'x1': x + w + 10, 'rot': rot, 'by': by, 'w': w, 'i': i, 'draw': draw})
        x += w + track
    for b in boxes:
        b['draw'](gf, 'fill')
    # drips run down from the letters' lower edges
    fp = fill.pixels()[..., 0]
    drips = []
    for b in boxes:
        n = 2 + int(math.floor(r() * 3))
        for _k in range(n):
            dx = _js_round(b['x0'] + 30 + r() * (b['x1'] - b['x0'] - 60))
            col_ = fp[41:, dx] if 0 <= dx < W else np.zeros(1)
            hit = np.nonzero(col_ > 200)[0]
            if not len(hit):
                continue
            y0 = int(hit.max()) + 41
            ln = 30 + r() * 110 * (0.5 + r())
            wd = 5 + r() * 6
            gd.fill_style = '#fff'
            gd.begin_path(); gd.move_to(dx - wd / 2, y0 - 6); gd.line_to(dx + wd / 2, y0 - 6)
            gd.line_to(dx + wd * 0.35, y0 + ln); gd.line_to(dx - wd * 0.35, y0 + ln); gd.close_path(); gd.fill()
            gd.begin_path(); gd.arc(dx, y0 + ln, wd * 0.62, 0, math.pi * 2); gd.fill()
            drips.append({'dx': dx, 'y0': y0, 'len': ln, 'b': b})
    op, dp = outl.pixels()[..., 0].astype(np.float64), drip.pixels()[..., 0].astype(np.float64)
    f = fp.astype(np.float64)
    o = op * (1 - np.minimum(1, f / 200))
    Nw = len(word)
    xs = np.arange(W, dtype=np.float64)
    centres = np.array([(b['x0'] + b['x1']) / 2 for b in boxes])
    bi = np.argmin(np.abs(xs[:, None] - centres[None, :]), axis=1)          # letterAt: the nearest letter (first on ties)
    bx0 = np.array([boxes[k]['x0'] for k in bi])
    bx1 = np.array([boxes[k]['x1'] for k in bi])
    bidx = np.array([boxes[k]['i'] for k in bi], np.float64)
    loc = np.clip((xs - bx0) / (bx1 - bx0), 0, 1)[None, :] * 0.75 + (np.arange(H)[:, None] / H) * 0.25
    tm = 0.03 + 0.66 * (bidx[None, :] + loc) / Nw
    # the first drip within 12 px of each column (drips.find)
    dr_y0 = np.full(W, np.nan)
    dr_len = np.full(W, np.nan)
    for x2 in range(W):
        for q in drips:
            if abs(q['dx'] - x2) < 12:
                dr_y0[x2], dr_len[x2] = q['y0'], q['len']
                break
    yy = np.arange(H, dtype=np.float64)[:, None]
    has = ~np.isnan(dr_y0)[None, :]
    prog = np.where(has, np.clip((yy - np.nan_to_num(dr_y0)[None, :]) / np.nan_to_num(dr_len, nan=1.0)[None, :], 0, 1), 0.5)
    tm_drip = np.minimum(0.99, 0.8 + 0.18 * prog)
    tm = np.where(o > 120, 0.72 + 0.18 * (xs[None, :] / W), np.where((dp > 40) & (f < 200), tm_drip, tm))
    out = np.zeros((H, W, 4), np.uint8)
    out[..., 0] = np.floor(np.clip(f, 0, 255)).astype(np.uint8)
    out[..., 1] = np.floor(np.clip(o, 0, 255)).astype(np.uint8)
    out[..., 2] = np.floor(tm * 255 + 0.5).astype(np.uint8)
    out[..., 3] = np.floor(np.clip(dp, 0, 255)).astype(np.uint8)
    img = L.data_tex(out, srgb=False, name='news_graffiti')
    img.alpha_mode = 'CHANNEL_PACKED'
    return img


def _fence_signs(L, fam):
    cv = CL.create_canvas(1024, 512)
    g = cv.get_context('2d')
    g.fill_style = '#ece9e1'; g.fill_rect(0, 0, 512, 512)
    g.fill_style = '#b8141c'; g.fill_rect(0, 0, 512, 150)
    g.fill_style = '#fff'; fit_text(g, 'PRIVATE PROPERTY', x=256, y=78, max_w=460, max_h=74, family=fam['rajdhani'])
    g.fill_style = '#111'; fit_text(g, 'NO', x=256, y=232, max_w=300, max_h=120, family=fam['rajdhani'])
    fit_text(g, 'TRESPASSING', x=256, y=352, max_w=460, max_h=110, family=fam['rajdhani'])
    g.fill_style = '#333'; fit_text(g, 'VIOLATORS WILL BE PROSECUTED', x=256, y=450, max_w=440, max_h=40, family=fam['rajdhani'])
    g.fill_style = '#f1c21b'; g.fill_rect(512, 0, 512, 512)
    g.fill_style = '#111'; g.fill_rect(512, 0, 512, 140)
    g.fill_style = '#f1c21b'; fit_text(g, 'DANGER', x=768, y=74, max_w=420, max_h=100, family=fam['rajdhani'])
    g.fill_style = '#111'; fit_text(g, 'HIGH VOLTAGE', x=768, y=228, max_w=460, max_h=110, family=fam['rajdhani'])
    fit_text(g, 'KEEP OUT', x=768, y=352, max_w=400, max_h=100, family=fam['rajdhani'])
    g.begin_path(); g.move_to(768 - 40, 400); g.line_to(768 + 10, 400); g.line_to(768 - 10, 440); g.line_to(768 + 40, 440)
    g.line_to(768 - 30, 500); g.line_to(768 - 5, 452); g.line_to(768 - 45, 452); g.close_path(); g.fill()
    return L.canvas_tex(cv, name='news_fence_signs')


def _sign_atlas(L, fam, texts=None):
    """The pickets' eight handwritten signs, one atlas. texts (opts signs): up to eight messages to write in place of
    the JS's, each a list of lines or a string with '/' between lines; a slot left None keeps its own. Every slot
    keeps its board, pen and doodle."""
    TW, TH = 512, 396
    W, H = TW * 4, TH * 2
    cv = CL.create_canvas(W, H)
    g = cv.get_context('2d')
    msgs = [
        {'t': ['NOT IN', 'OUR TOWN'], 'f': fam['kalam'], 'ink': '#141414', 'bg': '#f1eee5'},
        {'t': ['OUR', 'WATER'], 'f': fam['caveat'], 'ink': '#1c3f9c', 'bg': '#c49a62', 'drop': True},
        {'t': ['WHO PAYS', 'THE BILL?'], 'f': fam['kalam'], 'ink': '#b3121b', 'bg': '#f1eee5'},
        {'t': ['NO DATA', 'CENTER', 'HERE'], 'f': fam['caveat'], 'ink': '#141414', 'bg': '#c49a62', 'under': '#b3121b'},
        {'t': ['NOISE', '24/7'], 'f': fam['sedgwick'], 'ink': '#141414', 'bg': '#f1eee5', 'zig': '#b3121b'},
        {'t': ['HEAR', 'US'], 'f': fam['caveat'], 'ink': '#b3121b', 'bg': '#c49a62'},
        {'t': ['OUR TOWN', 'OUR SAY'], 'f': fam['kalam'], 'ink': '#1c3f9c', 'bg': '#f1eee5'},
        {'t': ['SAVE OUR', 'AQUIFER'], 'f': fam['sedgwick'], 'ink': '#141414', 'bg': '#f1eee5', 'drop': True},
    ]
    for i, t in enumerate(list(texts or [])[:len(msgs)]):
        if t:
            lines = [s.strip() for s in t.split('/')] if isinstance(t, str) else [str(s) for s in t]
            msgs[i]['t'] = [s for s in lines if s] or msgs[i]['t']
    rr = CL.rng(3)
    for i, m in enumerate(msgs):
        x0, y0 = (i % 4) * TW, (i // 4) * TH
        g.save(); g.begin_path(); g.rect(x0, y0, TW, TH); g.clip()
        g.fill_style = m['bg']; g.fill_rect(x0, y0, TW, TH)
        gr = g.create_radial_gradient(x0 + TW / 2, y0 + TH / 2, 60, x0 + TW / 2, y0 + TH / 2, TW * 0.7)   # grime
        gr.add_color_stop(0, 'rgba(0,0,0,0)'); gr.add_color_stop(1, 'rgba(40,30,20,0.28)')
        g.fill_style = gr; g.fill_rect(x0, y0, TW, TH)
        n = len(m['t'])
        lh = (TH - 70) / n
        g.fill_style = m['ink']
        for k, ln in enumerate(m['t']):
            g.save(); g.translate(x0 + TW / 2, y0 + 40 + lh * (k + 0.55)); g.rotate((rr() - 0.5) * 0.06)
            fit_text(g, ln, x=0, y=0, max_w=TW - 70, max_h=lh * 0.95, family=m['f'])
            g.restore()
        if m.get('under'):
            g.stroke_style = m['under']; g.line_width = 9; g.line_cap = 'round'; g.begin_path()
            g.move_to(x0 + 70, y0 + TH - 34); g.quadratic_curve_to(x0 + TW / 2, y0 + TH - 22, x0 + TW - 70, y0 + TH - 38)
            g.stroke()
        if m.get('zig'):
            g.stroke_style = m['zig']; g.line_width = 8; g.begin_path()
            for k in range(10):
                g.line_to(x0 + 60 + k * 40, y0 + TH - 30 - (k % 2) * 18)
            g.stroke()
        if m.get('drop'):
            g.fill_style = '#2a6fd6'
            dx, dy = x0 + TW - 70, y0 + 60
            g.begin_path(); g.move_to(dx, dy - 34); g.bezier_curve_to(dx + 30, dy, dx + 26, dy + 30, dx, dy + 30)
            g.bezier_curve_to(dx - 26, dy + 30, dx - 30, dy, dx, dy - 34); g.fill()
        g.restore()
    return {'tex': L.canvas_tex(cv, name='news_sign_atlas'), 'cols': 4, 'rows': 2, 'n': len(msgs), 'canvas': cv}


def _place_people(variants_n):
    """The pickets: denser near the fence and the middle; a clear lane for the 'fence' camera; the van and the light
    kept clear. rng(2026), the JS's own loop, so the same 78 people stand in the same places with the same roles."""
    r = CL.rng(2026)
    people = []
    k = 0
    while k < 9000 and len(people) < 78:
        k += 1
        x = -16 + r() * 32
        z = FZ + 0.9 + r() * 9.5
        dens = math.exp(-math.pow(max(0.0, abs(x) - 5) / 7, 2)) * (0.45 + 0.55 * math.exp(-(z - FZ - 1) / 4))
        if r() > dens:
            continue
        if abs(x - 0.3) < 2.1 and z < FZ + 3.2:
            continue
        if abs(x - VAN[0]) < 3.6 and abs(z - VAN[1]) < 1.8:
            continue
        if math.hypot(x - NEWS_LIGHT[0], z - NEWS_LIGHT[2]) < 1.2:
            continue
        if any(math.hypot(p['x'] - x, p['z'] - z) < 0.62 for p in people):
            continue
        people.append({'x': x, 'z': z})
    for i, p in enumerate(people):
        p['variant'] = i % variants_n
        p['yaw'] = math.pi + (r() - 0.5) * 0.5 + math.atan2(-p['x'], 14) * 0.25
        p['scale'] = 0.92 + r() * 0.16
        p['seed'] = r()
        q = r()
        p['role'] = 'sign' if q < 0.34 else 'phone' if q < 0.56 else 'torch' if q < 0.64 else 'fist' if q < 0.74 else 'down'
        role = p['role']
        p['theta'] = (2.78 + (r() - 0.5) * 0.18 if role == 'sign' else 1.72 + (r() - 0.5) * 0.2 if role == 'phone'
                      else 1.45 + (r() - 0.5) * 0.2 if role == 'torch' else 2.95 if role == 'fist' else 0.05)
        p['front'] = int(math.floor(r() * 8))
        p['back'] = (p['front'] + 1 + int(math.floor(r() * 7))) % 8
    # the crew: one figure with a shoulder camera beside the van, facing her
    people.append({'x': -5.6, 'z': 8.9, 'variant': 1, 'yaw': math.atan2(0 - -5.6, 0 - 8.9), 'scale': 1.0, 'seed': 0.5,
                   'role': 'crew', 'theta': 1.3, 'front': 0, 'back': 0})
    return people


def _arm_theta(gn, theta, seed, role):
    """armTheta: the base angle, the chant's pump on the signs and fists (with the pulse), a slow sway."""
    nb = gn.nb
    t = nb.U('t')
    is_sign = nb.step(0.5, role) * nb.step(role, 1.5)
    is_fist = nb.step(3.5, role) * nb.step(role, 4.5)
    beat = nb.sin(t * (math.pi * 2 * 0.95) + seed * 6.0)
    pump = (is_sign + is_fist) * (beat * 0.09 + nb.U('pulse') * 0.12) * nb.U('chant')
    sway = nb.sin(t * 1.3 + seed * 40.0) * 0.04
    return theta + pump + sway


def _instance_xf(gn, local_b, px, pz, yaw, scale):
    """three's M4(x, 0, z, 0, yaw, 0, scale) applied to a figure-local point (Blender axes): scale, turn about the
    vertical, move to (x, -z)."""
    nb = gn.nb
    p = gn.rotate(local_b * scale, (0.0, 0.0, 0.0), yaw, 'Z')
    return p + nb.vec3(px, -pz, 0.0)


def _build_crowd(L, N, crowd, S, fam, flood_at, fog, no_floods, signs=None, sign_normals='rest'):
    import bpy
    rig = json.load(open(common.asset_path('sets', 'funeral', 'crowd_rig.json'), encoding='utf-8'))
    glb = CL.read_glb_meshes(common.asset_path('models', 'funeral_crowd.glb'))
    variants = sorted([k for k in glb if k.startswith('person_')])
    SH, HD, NK = rig['shoulder'], rig['hand'], rig['neck']
    SHb, NKb = CL.b3(SH), CL.b3(NK)
    people = _place_people(len(variants))
    sign_atlas = _sign_atlas(L, fam, signs)
    N.parts['signAtlas'] = sign_atlas
    N.parts['rig'] = rig                     # the crowd figures' shoulder, hand and neck (three's axes, figure-local)

    def figure_mat(v):
        Mt = L.mat(f'news_figures_{v}')
        nb = Mt.nb
        seed, role = nb.attr('seed'), nb.attr('role')
        wc = nb.attr('wc', 'v')
        # dark clothes (charcoal, navy, olive, oxblood, a camel coat): silhouettes against the light
        pal = [(0.022, 0.022, 0.025), (0.016, 0.02, 0.032), (0.026, 0.026, 0.02), (0.03, 0.014, 0.013), (0.04, 0.03, 0.022)]
        h5 = nb.floor(seed * 5.0)
        base = nb.w(pal[0])
        for k in range(1, 5):
            base = nb.mix(base, pal[k], nb.step(k - 0.5, h5) * nb.step(h5, k + 0.5))
        lp3 = nb.three(nb.attr('lp', 'v'))                             # positionGeometry (three axes)
        weave = nb.mx_noise(lp3 * 60.0) * 0.3 + 0.85
        c = base * weave
        is_phone = nb.step(1.5, role) * nb.step(role, 2.5) + nb.step(4.5, role)
        phone_col = nb.mix((0.55, 0.7, 1.0), (1.0, 0.85, 0.6), nb.step(0.7, seed))
        screen = phone_col * wc.y * is_phone * 3.5
        fl = flood_at(nb, nb.P(), nb.N_local()) * (0.5 / math.pi)
        return Mt.standard(c, rough=0.85, metal=0.0, emissive=c * fl + screen * nb.U('lights'), fog=fog)

    objs = []
    for v, vname in enumerate(variants):
        mine = [p for p in people if p['variant'] == v]
        if not mine:
            continue
        src = glb[vname]
        P0 = src['position']
        idx = src['index'] if src['index'] is not None else np.arange(len(P0))
        colr = src.get('color')
        colr = colr[:, :3] if colr is not None else np.zeros((len(P0), 3))
        nv = len(P0)
        Pb0 = np.stack([P0[:, 0], -P0[:, 2], P0[:, 1]], 1)            # figure-local, Blender axes
        allP, allF, A = [], [], {k: [] for k in ('lp', 'wc', 'theta', 'seed', 'role', 'pscale', 'yaw', 'px', 'pz')}
        for j, p in enumerate(mine):
            c, s = math.cos(p['yaw']), math.sin(p['yaw'])
            rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
            wp = (Pb0 * p['scale']) @ rot.T + np.array([p['x'], -p['z'], 0.0])
            allP.append(wp)
            allF.append(idx.reshape(-1, 3) + j * nv)
            A['lp'].append(Pb0)
            A['wc'].append(colr)
            for k, val in (('theta', p['theta']), ('seed', p['seed']), ('role', ROLE_ID[p['role']]), ('pscale', p['scale']),
                           ('yaw', p['yaw']), ('px', p['x']), ('pz', p['z'])):
                A[k].append(np.full(nv, val))
        me = bpy.data.meshes.new(f'news_pickets_{v}')
        Pall = np.concatenate(allP).astype(np.float32)
        Fall = np.concatenate(allF).astype(np.int32)
        me.vertices.add(len(Pall))
        me.vertices.foreach_set('co', Pall.ravel())
        me.loops.add(len(Fall) * 3)
        me.loops.foreach_set('vertex_index', Fall.ravel())
        me.polygons.add(len(Fall))
        me.polygons.foreach_set('loop_start', np.arange(len(Fall), dtype=np.int32) * 3)
        me.polygons.foreach_set('loop_total', np.full(len(Fall), 3, np.int32))
        for k, arrs in A.items():
            a = np.concatenate(arrs).astype(np.float32)
            if a.ndim == 1:
                at = me.attributes.new(k, 'FLOAT', 'POINT')
                at.data.foreach_set('value', a)
            else:
                at = me.attributes.new(k, 'FLOAT_VECTOR', 'POINT')
                at.data.foreach_set('vector', a.ravel())
        me.update(calc_edges=True)
        me.polygons.foreach_set('use_smooth', np.ones(len(Fall), bool))
        L.own(me)
        mat = figure_mat(v)
        me.materials.append(mat)
        ob = bpy.data.objects.new(f'news_pickets_{v}', me)
        L.collection.objects.link(ob)
        ob.parent = crowd
        CL.set_flags(ob, {'noSupportCheck': True})
        L.own(ob)
        # the vertex stage: arms raise about the shoulder by theta(t), heads nod with the chant (the JS positionNode)
        gn = CL.GN(L, ob, f'news_pickets_{v}_pose')
        nb = gn.nb
        lp, wcv = gn.attr('lp', 'v'), gn.attr('wc', 'v')
        theta = _arm_theta(gn, gn.attr('theta'), gn.attr('seed'), gn.attr('role'))
        arm_p = gn.rotate(lp, SHb, -theta, 'X')
        P1 = nb.mix(lp, arm_p, wcv.x)
        nod = nb.sin(nb.U('t') * (math.pi * 2 * 0.95) + gn.attr('seed') * 6.0) * 0.06 * nb.U('chant')
        head_p = gn.rotate(P1, NKb, nod, 'X')
        P2 = nb.mix(P1, head_p, wcv.z * (1.0 - wcv.x))
        gn.set_position(_instance_xf(gn, P2, gn.attr('px'), gn.attr('pz'), gn.attr('yaw'), gn.attr('pscale'))).done()
        objs.append(ob)
        no_floods.append(ob)

    # signs (held overhead, moving with their arms): built in the raised pose then folded back to the hanging frame
    holders = [p for p in people if p['role'] == 'sign']
    theta0 = 2.78

    def rx(v, a):
        return np.array([v[0], v[1] * math.cos(a) - v[2] * math.sin(a), v[1] * math.sin(a) + v[2] * math.cos(a)])
    SHV, HDV = np.array(SH, float), np.array(HD, float)
    a_ = (HDV - SHV) / np.linalg.norm(HDV - SHV)
    ar = rx(a_, -theta0)
    Hr = SHV + rx(HDV - SHV, -theta0)
    up = ar.copy()
    nrm = np.array([0, 0, 1.0]) - up * up[2]
    nrm /= np.linalg.norm(nrm)
    right = np.cross(up, nrm)
    right /= np.linalg.norm(right)
    pos, uvs, sidx = [], [], []

    def quad(cq, hw, hh, side):
        b0 = len(pos)
        nn = -nrm if side == 'back' else nrm
        rr_ = -right if side == 'back' else right
        off = nn * 0.005
        for sx, sy, u, v in ((-1, -1, 0, 0), (1, -1, 1, 0), (1, 1, 1, 1), (-1, 1, 0, 1)):
            pp = cq + off + rr_ * (sx * hw) + up * (sy * hh)
            pos.append(pp)
            uvs.append((u if side == 'front' else 2 + u if side == 'back' else 4 + u * 0.1, v))
        sidx.extend([b0, b0 + 1, b0 + 2, b0, b0 + 2, b0 + 3])
    board_c = Hr + ar * 0.92
    quad(board_c, 0.31, 0.24, 'front')
    quad(board_c, 0.31, 0.24, 'back')
    s0, s1 = Hr + ar * -0.12, Hr + ar * 0.8                             # the stick: a thin box below the hand to the board
    scq, sl = (s0 + s1) / 2, np.linalg.norm(s1 - s0)
    sgeo = box_geometry(0.024, sl, 0.024)
    sgeo.rotate3(CL.quat_from_unit_vectors((0, 1, 0), ar))
    sgeo.translate(*scq)
    sgn = sgeo.non_indexed()
    b0 = len(pos)
    for i in range(len(sgn.pos)):
        pos.append(sgn.pos[i])
        uvs.append((4.05, 0.5))
        sidx.append(b0 + i)
    pos = [rx(np.asarray(pp) - SHV, theta0) + SHV for pp in pos]       # fold back to the hanging frame
    sign_geo = Geo(np.array(pos), None, np.array(uvs), np.array(sidx)).compute_vertex_normals()

    def signs_mat():
        Mt = L.mat('news_signs')
        nb = Mt.nb
        vU = nb.uv()
        side = nb.floor(vU.x / 2.0)                                   # 0 front, 1 back, 2 stick
        tile_i = nb.select(nb.lt(side, 0.5), nb.attr('front'), nb.attr('back'))
        lu, lv = nb.fract(vU.x), vU.y
        col_, row_ = nb.mod(tile_i, 4.0), nb.floor(tile_i / 4.0)
        auv = nb.vec2((col_ + lu) / 4.0, 1.0 - (row_ + (1.0 - lv)) / 2.0)
        card, _ = nb.tex(S['card']['col'], nb.vec2(lu, lv) * (0.62 / 0.35, 0.48 / 0.35, 1.0))
        art, _ = nb.tex(sign_atlas['tex'], auv)
        art = art * (nb.lum(card) * 0.6 + 0.62)
        is_stick = nb.step(1.5, side)
        c = nb.mix(art, (0.16, 0.11, 0.07), is_stick)
        cn, _ = nb.tex(S['card']['nrm'], nb.vec2(lu, lv) * (0.62 / 0.35, 0.48 / 0.35, 1.0))
        # floods painted on (with the fence's shadow); light through the board when a flood is behind it. news.js read
        # setN(): the boards' hanging-pose normals (its positionNode raised the boards, not their normals), so the face
        # the crowd sees (turned away from the floods once raised) took the floods head-on and showed its art bright,
        # and the face toward her glowed through. sign_normals='rest' (the default) keeps that; 'posed' lights the
        # raised boards by their true normals (the art lit on her side, the crowd side glowing through)
        Ps = nb.P()
        Ns = nb.N_local() if sign_normals == 'posed' else nb.normalize(nb.three(nb.attr('n0', 'v')))
        front = flood_at(nb, Ps, Ns) * (1 / math.pi)
        behind = flood_at(nb, Ps, -Ns) * (1 / math.pi)
        ink = 1.0 - nb.clamp(nb.lum(art) * 1.6, 0, 1)
        glow = nb.w((1.0, 0.92, 0.8)) * behind * (1.0 - ink * 0.85) * 0.18 * (1.0 - is_stick)
        return Mt.standard(c, rough=0.82, metal=0.0, normal=nb.normal_map(cn, 0.6), emissive=c * front + glow, fog=fog)
    M_signs = signs_mat()
    if holders:
        sob = _posed_copies(L, 'news_signs', sign_geo, holders, crowd, M_signs, extra=('front', 'back'), rest_normals=True)
        CL.set_flags(sob, {'noSupportCheck': True})
        gn = CL.GN(L, sob, 'news_signs_pose')
        th = _arm_theta(gn, gn.attr('theta'), gn.attr('seed'), gn.attr('role'))
        lp = gn.attr('lp', 'v')
        gn.set_position(_instance_xf(gn, gn.rotate(lp, SHb, -th, 'X'), gn.attr('px'), gn.attr('pz'), gn.attr('yaw'),
                                     gn.attr('pscale'))).done()
        no_floods.append(sob)
        N.parts['signs'] = sob

    # phone screens + flashlight lenses: soft points of light at the raised hands, facing the camera
    lit = [p for p in people if p['role'] in ('phone', 'torch', 'crew')]
    if lit:
        HL = np.array([[1.0, 0.97, 0.9] if p['role'] == 'torch' else [1.0, 0.86, 0.66] if p['seed'] > 0.7
                       else [0.62, 0.76, 1.0] for p in lit])
        HLw = np.array([5.5 if p['role'] == 'torch' else 2.4 if p['role'] == 'crew' else 1.8 for p in lit])
        points_b = np.array([[p['x'], -p['z'], 0.0] for p in lit])
        hob = CL.points_object(L, 'news_handlights', points_b, {
            'hl': HL, 'hlw': HLw, 'theta': np.array([p['theta'] for p in lit]), 'seed': np.array([p['seed'] for p in lit]),
            'yaw': np.array([p['yaw'] for p in lit]), 'pscale': np.array([p['scale'] for p in lit]),
            'px': np.array([p['x'] for p in lit]), 'pz': np.array([p['z'] for p in lit]),
            'size': np.array([0.42 if p['role'] == 'torch' else 0.2 for p in lit])}, parent=crowd)
        quad = CL.quad_object(L, 'news_billboard_quad')
        Mh = L.mat('news_handlights')
        nb = Mh.nb
        uv_ = nb.uv()
        d = nb.vec2((uv_.x - 0.5) * 2.0, (uv_.y - 0.5) * 2.0)      # three's vec2 uv (see the steam's)
        r2 = nb.dot(d, d)
        hlw = nb.attr('hlw')
        flick = nb.sin(nb.U('t') * 31.0 + hlw * 50.0) * 0.05 + 0.95
        M_hl = Mh.unlit(nb.attr('hl', 'v') * (nb.exp(r2 * -8.0) + nb.exp(r2 * -60.0) * 2.0) * hlw * flick * nb.U('lights'),
                        additive=True, fog=fog)
        gn = CL.GN(L, hob, 'news_handlights_place')
        gnb = gn.nb
        th = -(gn.attr('theta') + gnb.sin(gnb.U('t') * 1.3 + gn.attr('seed') * 40.0) * 0.04)
        v_b = CL.b3((HD[0] - SH[0], HD[1] - SH[1], HD[2] - SH[2] + 0.06))
        hand = gn.rotate(gnb.w(v_b), (0.0, 0.0, 0.0), th, 'X') + SHb
        gn.set_position(_instance_xf(gn, hand, gn.attr('px'), gn.attr('pz'), gn.attr('yaw'), gn.attr('pscale')))
        gn.billboards(quad, gn.attr('size')).set_material(M_hl).done()
        hob.visible_shadow = False
        N.parts['handlights'] = hob
    # torch beams: thin additive cones along the raised arm, out toward the fence
    torches = [p for p in people if p['role'] == 'torch']
    if torches:
        tlen = 9.0
        cg = cylinder_geometry(0.03, 0.9, tlen, 16, 1, True).translate(0, -tlen / 2, 0)
        dirv = (HDV - SHV) / np.linalg.norm(HDV - SHV)
        cg.rotate3(CL.quat_from_unit_vectors((0, -1, 0), dirv))
        cg.translate(*HDV)
        tob = _posed_copies(L, 'news_torch_beams', cg, torches, crowd, None, role_override=3)
        Mt = L.mat('news_torch_beams')
        nb = Mt.nb
        along = nb.clamp(nb.length(nb.three(nb.attr('lp', 'v')) - tuple(HD)) / tlen, 0, 1)
        M_tb = Mt.unlit(nb.w((1.0, 0.96, 0.88)) * nb.pow(1.0 - along, 2.0) * nb.pow(nb.facing(), 2.0) * 0.06
                        * nb.U('lights'), additive=True, fog=fog)
        tob.data.materials.append(M_tb)
        gn = CL.GN(L, tob, 'news_torch_beams_pose')
        th = _arm_theta(gn, gn.attr('theta'), gn.attr('seed'), gn.attr('role'))
        gn.set_position(_instance_xf(gn, gn.rotate(gn.attr('lp', 'v'), SHb, -th, 'X'), gn.attr('px'), gn.attr('pz'),
                                     gn.attr('yaw'), gn.attr('pscale'))).done()
        tob.visible_shadow = False
        CL.set_flags(tob, {'noSupportCheck': True})
        N.parts['torchBeams'] = tob
    # the crew's shoulder camera
    crew = next(p for p in people if p['role'] == 'crew')
    cb = L.bucket('news_crew_cam')
    cb.box(0.16, 0.2, 0.42, SH[0] - 0.02, SH[1] + 0.02, 0.12)
    cb.add(cylinder_geometry(0.06, 0.07, 0.16, 16), m4(SH[0] - 0.02, SH[1] + 0.02, 0.4, math.pi / 2, 0, 0), uv='keep')
    cam_geo = cb.geometry()
    cam_geo.apply(m4(crew['x'], 0, crew['z'], 0, crew['yaw'], 0, crew['scale']))
    L.mesh_object('news_crew_cam', cam_geo, N.materials['paintDark'], parent=crowd, flags={'noSupportCheck': True})
    counts = {r_: sum(1 for p in people if p['role'] == r_) for r_ in ('sign', 'phone', 'torch', 'fist', 'down', 'crew')}
    common.log('news', f'pickets: {len(people)} (' + ', '.join(f'{k} {v}' for k, v in counts.items()) + ')')
    return people


def _posed_copies(L, name, geo, who, parent, mat, extra=(), role_override=None, rest_normals=False):
    """One mesh holding a copy of geo (figure-local, three axes) per person, at its rest place, with the per-person
    data the pose modifier reads: lp (local position, Blender axes), theta, seed, role, pscale, yaw, px, pz (+ extra).
    rest_normals: also n0, geo's own normal turned by the person's yaw (set space, Blender axes): the normal three's
    lighting kept when a positionNode moved the vertices (TSL does not turn normals with it)."""
    import bpy
    q = geo.non_indexed()
    Pb0 = np.stack([q.pos[:, 0], -q.pos[:, 2], q.pos[:, 1]], 1)
    Nb0 = np.stack([q.nrm[:, 0], -q.nrm[:, 2], q.nrm[:, 1]], 1) if rest_normals and q.nrm is not None else None
    nv = len(Pb0)
    keys = ('lp', 'theta', 'seed', 'role', 'pscale', 'yaw', 'px', 'pz') + tuple(extra) + (('n0',) if Nb0 is not None else ())
    allP, A = [], {k: [] for k in keys}
    UVs = []
    for p in who:
        c, s = math.cos(p['yaw']), math.sin(p['yaw'])
        rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
        allP.append((Pb0 * p['scale']) @ rot.T + np.array([p['x'], -p['z'], 0.0]))
        A['lp'].append(Pb0)
        if Nb0 is not None:
            A['n0'].append(Nb0 @ rot.T)
        for k, val in (('theta', p['theta']), ('seed', p['seed']),
                       ('role', role_override if role_override is not None else ROLE_ID[p['role']]),
                       ('pscale', p['scale']), ('yaw', p['yaw']), ('px', p['x']), ('pz', p['z'])):
            A[k].append(np.full(nv, val, float))
        for k in extra:
            A[k].append(np.full(nv, float(p[k])))
        UVs.append(q.uv)
    Pall = np.concatenate(allP).astype(np.float32)
    nt = len(Pall) // 3
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(Pall))
    me.vertices.foreach_set('co', Pall.ravel())
    me.loops.add(len(Pall))
    me.loops.foreach_set('vertex_index', np.arange(len(Pall), dtype=np.int32))
    me.polygons.add(nt)
    me.polygons.foreach_set('loop_start', np.arange(nt, dtype=np.int32) * 3)
    me.polygons.foreach_set('loop_total', np.full(nt, 3, np.int32))
    uvl = me.uv_layers.new(name='UVMap')
    uvl.data.foreach_set('uv', np.concatenate(UVs).astype(np.float32).ravel())
    for k, arrs in A.items():
        a = np.concatenate(arrs).astype(np.float32)
        if a.ndim == 1:
            at = me.attributes.new(k, 'FLOAT', 'POINT')
            at.data.foreach_set('value', a)
        else:
            at = me.attributes.new(k, 'FLOAT_VECTOR', 'POINT')
            at.data.foreach_set('vector', a.ravel())
    me.update(calc_edges=True)
    L.own(me)
    if mat is not None:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    L.collection.objects.link(ob)
    ob.parent = parent
    return L.own(ob)


def _build_steam(L, N, root, FL, fog):
    """Plumes off the cooling towers and low steam at the grates: puffs cycling up their plume (deterministic in t),
    camera-facing quads spun about the view axis, placed by Geometry Nodes."""
    r = CL.rng(77)
    puffs = []

    def plume(x0, y0, z0, kind, n, H, wind, size0, size1):
        for k in range(n):
            puffs.append({'x0': x0, 'y0': y0, 'z0': z0, 'kind': kind, 'k': k, 'n': n, 'H': H, 'wind': wind,
                          'size0': size0, 'size1': size1, 'seed': r()})
    for x, z in TOWERS:
        for ox, oz in ((-2.2, -2.2), (2.2, 2.2)):
            plume(x + ox, BH + 4.2, z + oz, 0, 12, 30, (7.0, 0, 4.5), 3.4, 18)
    for x, z in VENTS:
        plume(x, 0.4, z, 1, 7, 9, (3.2, 0, 1.4), 1.4, 5.5)
    A = {k: np.array([p[k] for p in puffs], float) for k in ('x0', 'y0', 'z0', 'kind', 'k', 'n', 'H', 'size0', 'size1',
                                                             'seed')}
    A['wx'] = np.array([p['wind'][0] for p in puffs])
    A['wz'] = np.array([p['wind'][2] for p in puffs])
    ob = CL.points_object(L, 'news_steam', [CL.b3((p['x0'], p['y0'], p['z0'])) for p in puffs], A, parent=root)
    quad = CL.quad_object(L, 'news_steam_quad')
    # the material: lit by the floods (forward scatter when we look toward a lamp through it), the sodium wash, the sky
    Mt = L.mat('news_steam')
    nb = Mt.nb
    vuv = nb.uv()
    s = nb.attr('seed')
    # the quad's uv as three's vec2: Blender's UV is a 3-vector with z = 0, and (uv - 0.5) * 2 would put z at -1 in
    # the dot product (r2 >= 1: every puff transparent)
    d = nb.vec2((vuv.x - 0.5) * 2.0, (vuv.y - 0.5) * 2.0)
    r2 = nb.dot(d, d)
    tt = nb.U('t') * 0.08
    n = nb.mx_fbm(nb.vec3(d.x * 1.6 + s * 17.0, d.y * 1.6 - tt * 3.0 + s * 9.0, tt + s), 4, 2.0, 0.55)
    dens = nb.clamp((1.0 - r2) * (n * 0.9 + 0.55), 0, 1) * nb.ss(1.0, 0.35, r2)
    Ps = nb.P()
    V = nb.normalize(Ps - nb.cam_local())
    fwd = 0.0
    for f in FL:
        Ld = nb.normalize(Ps - f['p'])
        fwd = fwd + nb.pow(nb.max(nb.dot(V, Ld), 0.0), 10.0) * 2.0

    def flood_omni(P):
        acc = 0.0
        cos_out, cos_in = math.cos(FLOOD_ANGLE), math.cos(FLOOD_ANGLE * (1 - FLOOD_PEN))
        for f in FL:
            Lv = nb.w(f['p']) - P
            d2 = nb.max(nb.dot(Lv, Lv), 0.25)
            Ld = Lv / nb.sqrt(d2)
            acc = acc + nb.ss(cos_out, cos_in, nb.dot(-Ld, f['d'])) * 0.6 / d2
        return acc * FLOOD_I * nb.U('floods') * nb.U('lights')
    fl = flood_omni(Ps) * 0.008 + fwd * 0.06 * nb.U('floods')
    sod = nb.w(SODIUM) * 0.05 * nb.ss(48, 10, Ps.y)
    under = nb.w(HMI) * 0.05 * nb.ss(40, 18, Ps.y) * nb.U('floods')       # the floodlit yard below
    c = nb.w(HMI) * fl + sod + under + (0.035, 0.04, 0.05)
    alpha = dens * ((1.0 - nb.attr('ph')) * 0.9 + 0.1) * 0.55
    M = Mt.unlit(c, alpha=nb.clamp(alpha, 0, 1), fog=fog, depth_write=False)     # three's depthWrite: false
    N.materials['steam'] = M
    # Geometry Nodes: each puff's rise, place and size from t; then the billboard
    gn = CL.GN(L, ob, 'news_steam_place')
    g = gn.nb
    t = g.U('t')
    kind, k_, n_, seed = gn.attr('kind'), gn.attr('k'), gn.attr('n'), gn.attr('seed')
    period = g.mix(11.0, 7.0, kind)
    ph = g.fract(t / period + k_ / n_ + seed * 0.13)
    e = g.pow(ph, 0.85)
    x = gn.attr('x0') + gn.attr('wx') * e * e + g.sin(t * 0.3 + seed * 6.0) * 0.4 * e
    y = gn.attr('y0') + gn.attr('H') * e
    z = gn.attr('z0') + gn.attr('wz') * e * e
    size = gn.attr('size0') + (gn.attr('size1') - gn.attr('size0')) * e
    gn.store('ph', ph)
    gn.set_position(g.vec3(x, -z, y))
    gn.billboards(quad, size, spin=seed * 6.28 + t * 0.05 * (seed - 0.5)).set_material(M).done()
    ob.visible_shadow = False
    CL.set_flags(ob, {'noSupportCheck': True})
    return ob


def _build_van(L, M, van, S, fam, pm, fog):
    cv = CL.create_canvas(1024, 512)
    g = cv.get_context('2d')
    g.fill_style = '#e9ebe8'; g.fill_rect(0, 0, 1024, 512)
    g.fill_style = '#0b3a44'; g.fill_rect(0, 300, 1024, 110)
    g.fill_style = '#f2a51e'; g.fill_rect(0, 410, 1024, 22)
    g.fill_style = '#0b3a44'
    g.save(); g.translate(150, 190); g.fill_rect(-90, -90, 180, 180); g.fill_style = '#f2a51e'
    fit_text(g, '88', x=0, y=6, max_w=150, max_h=130, family=fam['rajdhani']); g.restore()
    g.fill_style = '#0b3a44'; fit_text(g, 'NIGHT DESK', x=270, y=150, max_w=680, max_h=110, family=fam['rajdhani'], align='left')
    g.fill_style = '#e9ebe8'
    fit_text(g, 'LIVE · LOCAL · ALL NIGHT', x=512, y=356, max_w=900, max_h=60, family=fam['rajdhani'], track=0.1)
    livery = L.canvas_tex(cv, name='news_van_livery')

    def body_recolor(c, nb):
        n = nb.N_local()
        side = nb.step(0.6, nb.abs(n.z))
        lv, _ = nb.tex(livery, nb.uv())
        return nb.mix(c * (0.82, 0.83, 0.82), lv * (nb.lum(c) * 0.2 + 0.85), side)
    M['vanBody'] = pm(S['paint'], name='news_van_body', tile=1.0, metal=0.3, rough=(0.4, 0.15), recolor=body_recolor)
    M['vanCab'] = pm(S['paint'], name='news_van_cab', tile=1.0, metal=0.3, rough=(0.4, 0.15), tint=[0.82, 0.83, 0.82])
    flags = {'assembly': 'news_van'}
    V = m4(VAN[0], 0, VAN[1])
    L.mesh_object('news_van_body', box_geometry(5.4, 2.1, 2.05), M['vanBody'], parent=van, M3=V @ m4(0.3, 0.45 + 1.05, 0),
                  flags=flags)
    L.mesh_object('news_van_cab', box_geometry(1.4, 1.5, 2.0), M['vanCab'], parent=van, M3=V @ m4(-2.95, 0.45 + 0.75, 0),
                  flags=flags)
    L.mesh_object('news_van_windscreen', plane_geometry(1.9, 0.75), M['glassDark'], parent=van,
                  M3=V @ m4(-3.66, 1.6, 0, 0.0, -math.pi / 2, 0), flags=flags)
    wb = L.bucket('news_van_wheels')
    for x, z in ((-2.6, 0.95), (-2.6, -0.95), (1.9, 0.95), (1.9, -0.95)):
        wb.add(cylinder_geometry(0.4, 0.4, 0.28, 18), V @ m4(x, 0.4, z, math.pi / 2, 0, 0), uv='keep')
    wb.mesh(M['rubber'], parent=van, flags=flags)
    mb = L.bucket('news_van_mast')                 # the mast: telescoping sections, a dish, a red light on top
    y = 2.55
    for rr, h in ((0.14, 2.4), (0.11, 2.4), (0.085, 2.3)):
        mb.add(cylinder_geometry(rr, rr, h, 12), V @ m4(2.2, y + h / 2, 0), uv='keep')
        y += h - 0.15
    mb.add(lathe_geometry([[0.001, 0], [0.3, 0.05], [0.5, 0.16], [0.52, 0.18]], 20), V @ m4(2.2, y + 0.1, 0.2, math.pi / 2 - 0.3, 0, 0))
    mb.box(0.5, 0.35, 0.35, VAN[0] + 2.2, y - 0.1, VAN[1] - 0.1)
    mb.mesh(M['galv'], parent=van, flags=flags)
    L.mesh_object('news_van_mast_light', sphere_geometry(0.08, 10, 8), M['aviation'], parent=van,
                  M3=V @ m4(2.2, y + 0.45, 0), shadow=False, flags=flags)
    ls = L.bucket('news_lightstand')               # the light stand: tripod, pole, LED panel aimed at her
    lx, lz = NEWS_LIGHT[0] - VAN[0], NEWS_LIGHT[2] - VAN[1]
    for k in range(3):
        a = k * math.pi * 2 / 3
        ls.add(cylinder_geometry(0.015, 0.015, 1.3, 6),
               V @ m4(lx + math.sin(a) * 0.3, 0.6, lz + math.cos(a) * 0.3, math.cos(a) * 0.35, 0, -math.sin(a) * 0.35),
               uv='keep')
    ls.add(cylinder_geometry(0.02, 0.02, NEWS_LIGHT[1], 8), V @ m4(lx, NEWS_LIGHT[1] / 2, lz), uv='keep')
    ls.mesh(M['paintDark'], parent=van, flags=flags)
    R = CL.look_at_matrix(NEWS_LIGHT, (0, 1.45, 0))
    Pm = np.eye(4)
    Pm[:3, :3] = R
    Pm[:3, 3] = NEWS_LIGHT
    L.mesh_object('news_led_housing', box_geometry(0.62, 0.42, 0.08), M['paintDark'], parent=van, M3=Pm, shadow=False,
                  flags=flags)
    L.mesh_object('news_led_face', plane_geometry(0.56, 0.36), M['ledPanel'], parent=van, M3=Pm @ CL.translation(0, 0, 0.041),
                  shadow=False, flags=flags)


def _chyron(L, N, fam):
    """A generic lower third: LIVE . NIGHT DESK 88 . 10:42 PM, the headline, a sub line and a ticker that scrolls in
    the shader. place(overlay) puts it on a media.overlay Overlay (or a camera) in display space; set_text(**o) makes
    a new variant (keyed CONSTANT when given ctx / frame)."""
    W, H = 1920, 270
    st = {'headline': 'RESIDENTS PICKET AI DATA CENTER', 'sub': 'Opponents cite water use, round-the-clock noise and power bills',
          'ticker': 'WEATHER: CLEAR, 41°  ·  COUNTY LINE ROAD CLOSED AT MILE 3 FOR THE DEMONSTRATION  ·  '
                    'TOWN HALL MEETING THURSDAY 7 PM  ·  ',
          'tag': 'LIVE', 'channel': 'NIGHT DESK 88', 'time': '10:42 PM'}
    var = CL.ImageVariants(L, 'news_chyron', 'chyron_variant')

    def draw(s):
        cv = CL.create_canvas(W, H)
        g = cv.get_context('2d')
        g.fill_style = '#c4121c'; g.fill_rect(60, 6, 124, 46)        # the tag row: LIVE, the channel bug, the clock
        g.fill_style = '#fff'; fit_text(g, s['tag'], x=122, y=30, max_w=110, max_h=36, family=fam['rajdhani'])
        g.fill_style = 'rgba(6,26,32,0.92)'; g.fill_rect(184, 6, 360, 46)
        g.fill_style = '#f2a51e'
        fit_text(g, s['channel'], x=200, y=30, max_w=330, max_h=34, family=fam['rajdhani'], align='left', track=0.08)
        g.fill_style = 'rgba(6,26,32,0.92)'; g.fill_rect(W - 250, 6, 190, 46)
        g.fill_style = '#fff'; fit_text(g, s['time'], x=W - 155, y=30, max_w=170, max_h=34, family=fam['rajdhani'])
        g.fill_style = 'rgba(8,36,44,0.95)'; g.fill_rect(60, 58, W - 120, 104)       # the headline bar, an amber edge
        g.fill_style = '#f2a51e'; g.fill_rect(60, 58, 14, 104)
        g.fill_style = '#ffffff'
        fit_text(g, s['headline'], x=100, y=112, max_w=W - 200, max_h=84, family=fam['rajdhani'], align='left')
        g.fill_style = 'rgba(236,240,241,0.96)'; g.fill_rect(60, 162, W - 120, 52)   # the sub line
        g.fill_style = '#0b2a33'; fit_text(g, s['sub'], x=100, y=189, max_w=W - 200, max_h=38, family=fam['exo'], align='left')
        g.fill_style = 'rgba(3,6,8,0.94)'; g.fill_rect(60, 216, W - 120, 48)          # the ticker's track
        tick = CL.create_canvas(4096, 64)
        gt = tick.get_context('2d')
        gt.fill_style = '#f2c46a'; gt.font = f'40px {fam["rajdhani"]}'; gt.text_baseline = 'middle'
        x = 0.0
        unit = s['ticker']
        while x < 4096:
            gt.fill_text(unit, x, 34)
            x += gt.measure_text(unit).width
        n = len(var.items)
        return {'base': L.data_tex(cv.pixels(), srgb=True, name=f'news_chyron_{n}'),
                'tick': L.data_tex(tick.pixels(), srgb=True, wrap=CL.REPEAT, name=f'news_chyron_ticker_{n}')}

    def set_text(ctx=None, frame=None, **o):
        st.update({k: str(v) for k, v in o.items() if k in st})
        sig = tuple(sorted(st.items()))
        vi = var.add(draw(st), sig=sig)
        N.set_u('chyron_variant', vi, ctx=ctx, frame=frame, interpolation='CONSTANT')
        return vi
    set_text()
    Mt = L.mat('news_chyron')
    nb = Mt.nb
    u0 = nb.uv()
    base, base_a = var.sample(nb, 'base', u0)
    scroll = nb.fract(nb.U('t') * 0.045)
    tv = nb.clamp((u0.y * H - (H - 264)) / 48.0, 0, 1)            # the ticker band (canvas rows 216-264)
    in_tick = (nb.step(H - 264, u0.y * H) * nb.step(u0.y * H, H - 216) * nb.step(60 / W, u0.x)
               * nb.step(u0.x, 1 - 60 / W))
    tk, tk_a = var.sample(nb, 'tick', nb.vec2(u0.x * (W / 4096) + scroll, tv * (48 / 64) + 8 / 64))
    mat = Mt.unlit(nb.mix(base, tk, tk_a * in_tick), alpha=nb.max(base_a, tk_a * in_tick), scale=1.0)
    geo = plane_geometry(1, H / W)
    ob = L.mesh_object('news_chyron', geo, mat, shadow=False)
    ob.rotation_euler = (-math.pi / 2, 0.0, 0.0)               # the mesh's three XY plane -> the camera's XY plane
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    L.collection.objects.link(ob)
    ob.hide_render = True                                        # shown once placed in an overlay

    class Chyron(dict):
        def set_text(self, **o):
            return set_text(**o)
        setText = set_text

        def place(self, overlay, fov=40.0, aspect=16 / 9, bottom=0.06):
            """Lay it across the lower third of an overlay camera (z = -1 in its frame): overlay is a
            media.overlay Overlay (its scene and camera) or a camera object."""
            cam = getattr(overlay, 'camera', overlay)
            scn = getattr(overlay, 'scene', None)
            hh = math.tan(math.radians(fov) / 2)
            hw = hh * aspect
            k = 2 * hw * 0.86
            h = k * H / W
            ob.parent = cam
            ob.location = (0.0, -hh + bottom * 2 * hh + h / 2, -1.0)
            ob.scale = (k, k, k)
            if scn is not None:
                for c in list(ob.users_collection):
                    c.objects.unlink(ob)
                scn.collection.objects.link(ob)
            ob.hide_render = False
            return ob

        def update(self, t, ctx=None, frame=None):
            N.set_u('t', t, ctx=ctx, frame=frame)
    return Chyron(mesh=ob, state=st, variants=var)
