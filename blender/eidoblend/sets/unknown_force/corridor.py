"""eidoblend.sets.unknown_force.corridor: the gold corridor of power, the Blender 5.2 EEVEE edition of
eidoverse/sets/unknown_force/corridor.js (made for UNKNOWN FORCE; a free set for any piece).

A corridor of power at night, 10 m wide, 12 m high, 46 m long: black marble with gold veins, gilded Futurist-Deco
stepped pilasters and ribs, a lacquered coffered ceiling, a red carpet runner, sconces that throw Balla fans of gold
up the marble, four octagonal lanterns, a mirror floor with a gold sunburst, and at the end a bronze-gold double door
under an engraved plaque (SUPREME / INTELLIGENCE), a poll board beside it, a 13 m LED wall that posts in capitals, a
uniform on a tailor's stand, a peaked cap on a velvet cushion, and the AI FORCE mission patch.

    from eidoblend.sets.unknown_force import corridor
    C = corridor.build(scene, {'postText': 'ANY POST, IN CAPITALS', 'tally': [49, 39, 12]})
    C.parts['postWall'].set_text('A NEW POST', name='MINISTRY OF ANYTHING')   # the LED wall reposts
    C.parts['poll'].set_tally(512000, 418000, 141000, stamp=False)         # a recount
    C.apply_look(scene)                                          # view exposure, EEVEE settings the set was lit for
    C.bake_probes(scene)                                         # the corridor's volume probe (a GPU job)
    cam = C.camera('door', scene)                                # the set's five cameras, from C.cams
    C.update(0.0, {'open': 0.4, 'post': 0.5})                    # a still: sets everything, keys nothing
    # its moving parts on your own clock, KEYED (t in seconds from the scene's first frame, or from t0):
    C.animate(lambda t: {'post': t / 1.5, 'capOn': t - 2.0, 'capHead': (armature, 'head'), 'open': (t - 4.0) / 2},
              frames=(1, 168))
    C.apply_post(scene)                                          # the suggested look: bloom + aeropittura 'argue'

Set-local metres. The JS built it in three's axes (+Y up, floor y = 0, the mark the origin facing +Z, the door 24 m
behind it at -Z); it is built here the same way and converted once, three (x, y, z) -> Blender (x, -z, y): the floor
is z = 0, the mark faces -Y, the door is at y = +24. cams and focal are set-local in Blender's axes (the sets'
contract, eidoblend.sets.unknown_force); cams_three, focal_three and the module's constants (CAMS, FOCAL, CORRIDOR)
keep the WebGPU's own numbers so they read against CORRIDOR_NEWS.md; camera(name) makes the camera.

Everything animated is keyed: update(t, state, ctx) keys the root's custom properties (the materials' uniforms, read
through drivers), the doors' pivots, the cap, the lights, the post's typing and the shafts' visibility. Text is
material (canvas images packed into the .blend), never geometry; no real seals or logos.
"""

from __future__ import annotations

import math

import numpy as np

from . import cn_lib as CL
from .cn_lib import (Geo, box_geometry, cylinder_geometry, lathe_geometry, torus_geometry, sphere_geometry,
                     circle_geometry, plane_geometry, tube_geometry, catmull_rom, m4, fit_text, hex_linear)

HW = 5.0                     # half width: the wall faces are x = +-5
HC = 12.0                    # ceiling
ZN, ZD = 22.0, -24.0         # near end wall, door wall
SLAB = 0.4                   # the walls', floor's and ceiling's thickness (a closed shell)
PIL = [18, 14, 10, 6, 2, -2, -6, -10, -14, -18, -22]
SCR = {'z0': -16.6, 'z1': -3.4, 'y0': 1.5, 'y1': 7.5}         # the LED wall on the right (+x) wall
SCR_SKIP = {-6, -10, -14}                                      # right-wall pilasters behind it
LANT = [12, 4, -4, -12]                                        # pendant lanterns (z)
LANT_Y = 8.55                                                  # lantern glass centre height
SCONCE_Y = 3.8
DOOR_HW, DOOR_H = 3.2, 8.0
PATCH = {'z': -4.0, 'y': 6.2, 'r': 1.25}                       # on the left (-x) wall
UNIFORM_AT = [-3.75, -4.6]
CAP_AT = [-2.45, -1.3]
POLL_AT = [-3.15, -19.0]
WARM = (1.0, 0.62, 0.3)

CORRIDOR = {'HW': HW, 'HC': HC, 'ZN': ZN, 'ZD': ZD, 'SCR': SCR, 'PATCH': PATCH, 'DOOR_HW': DOOR_HW, 'DOOR_H': DOOR_H,
            'CAP_AT': CAP_AT, 'UNIFORM_AT': UNIFORM_AT, 'POLL_AT': POLL_AT}

CAMS = {
    # her in the foreground, the door, the plaque and the poll board down the axis
    'door': {'pos': [0.55, 1.25, 6.2], 'target': [0, 4.6, ZD], 'fov': 38},
    # Crali's dive down the gold tunnel: one-point perspective onto the door
    'corridorWide': {'pos': [0, 2.4, 19.5], 'target': [0, 4.2, ZD], 'fov': 44},
    # the LED wall at an angle with her in the left of frame
    'postWall': {'pos': [-3.0, 1.6, 4.6], 'target': [HW, 4.4, -10.5], 'fov': 46},
    # the cap on its cushion, the uniform and the patch beyond
    'cap': {'pos': [-1.35, 1.42, 0.25], 'target': [CAP_AT[0] - 0.25, 1.12, CAP_AT[1] - 0.6], 'fov': 34},
    # the poll board, the door beyond it
    'poll': {'pos': [-0.9, 2.3, -12.6], 'target': [POLL_AT[0] - 0.35, 2.45, POLL_AT[1]], 'fov': 40},
}
FOCAL = (0.0, 5.2, ZD + 0.2)          # the door: the aeropittura's sun cones come from here (three space)
LOOK = {'name': 'argue', 'exposure': 1.0, 'bloom': {'strength': 0.55, 'radius': 0.5, 'threshold': 0.7}, 'fog': None}

UNIFORMS = {'t': 0.0, 'open': 0.0, 'gap': 1.0, 'screen': 1.0, 'lights': 1.0, 'flick': 1.0, 'beyond': 0.0,
            'pix': 0.001, 'post_variant': 0.0, 'post_n': 0.0, 'post_cursor': 0.0, 'poll_variant': 0.0}


def _gray(v):
    c = int(math.floor(max(0.0, min(1.0, v)) * 255 + 0.5))
    return f'rgb({c},{c},{c})'


def _ease(x):
    k = max(0.0, min(1.0, x))
    return k * k * (3 - 2 * k)


def _js_round(x):
    return int(math.floor(x + 0.5))


ImageVariants = CL.ImageVariants


# ============================================================================================= build ============

class Corridor(CL.SetBase):
    """What build() returns (see the module docstring)."""

    def apply_look(self, scene, raytracing=False, view_look=None):
        """The settings the set was lit for: AgX at view_exposure(look exposure); EEVEE with global illumination
        (fast GI over the corridor's baked probe: bake_probes()) and reflections from the light probes (the floor's
        mirror is painted, analytically, as in the WebGPU edition, and the metals reflect the set's environment);
        raytracing=True screen-traces the reflections instead; shadows on. view_look: an AgX look for the scene
        ('AgX - Medium High Contrast' follows three's ACES Filmic, the WebGPU frames' tone, to a few levels:
        cn_lib.ACES_LIKE_LOOK); None leaves the scene's look as it is (the pipeline's plain AgX)."""
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.exposure = CL.view_exposure(self.look['exposure'])
        if view_look is not None:
            scene.view_settings.look = view_look
        CL.eevee_gi(scene, raytracing)
        self.set_u('pix', CL.pix_of(scene))
        return scene


def build(scene=None, opts=None, collection=None, name='set:corridor'):
    """Build the corridor into `scene` (default: the context scene). opts: postText, tally, capFitPos, capFitRot,
    capFitScale (the JS options) and the Blender edition's own: world (True: the set's environment + hemisphere light
    become scene.world), shadows (True: the set's spot lights cast shadows; its fixtures never shadow their own
    light), ibl ('material': each material's own environment light, as three; 'world': the environment as the
    world), plaque (('SUPREME', 'INTELLIGENCE'): the two lines engraved over the door)."""
    import bpy
    from mathutils import Matrix, Vector
    sc = scene or bpy.context.scene
    opts = dict(opts or {})
    shadows = opts.get('shadows', True)

    col = collection or bpy.data.collections.new(name)
    if collection is None:
        sc.collection.children.link(col)
    root = bpy.data.objects.new(name, None)
    root.empty_display_size = 1.0
    col.objects.link(root)
    for k, v in UNIFORMS.items():
        root[k] = float(v)
    L = CL.make_lib('corridor', owner=root, collection=col)
    L.own(root)
    L.own(col)
    C = Corridor(L, root, col)
    C.set_cams(CAMS, FOCAL)                          # cams / focal in Blender's axes; cams_three / focal_three
    C.look = dict(LOOK)
    fam = CL.fam

    # ------------------------------------------------------------------- texture sets (CC0, AmbientCG: the library)
    S = {
        'marble': L.pbr('Marble016', res='2k'),         # black marble, white veins -> gold veins
        'goldH': L.pbr('Metal042A', met=True),           # polished, lightly hammered gold
        'goldF': L.pbr('Metal048B', met=True),           # gold with fingerprints
        'goldI': L.pbr('Metal048C', met=True),           # impure, rough gold
        'bronze': L.pbr('Metal008', met=True),           # scratched bronze
        'pile': L.pbr('Fabric023'),                      # cut pile: the runner, the velvet
        'twill': L.pbr('Fabric077'),                     # twill: the uniform
        'lacq': L.pbr('PaintedMetal012', ao=True),
        'wood': L.pbr('Wood066'),
    }

    # ----------------------------------------------------- the room's light, as an environment for the metals
    def env_fn(d):
        x, y, z = d
        r, g, b = 0.010, 0.007, 0.005
        down = max(0.0, -y)
        r += 0.03 * down; g += 0.005 * down; b += 0.004 * down
        up = max(0.0, y)
        axis = math.exp(-x * x * 10) * math.pow(up, 0.7)
        r += 0.12 * axis; g += 0.075 * axis; b += 0.03 * axis
        door = math.pow(max(0.0, -z), 60) * math.exp(-(y - 0.15) * (y - 0.15) * 10)
        r += 1.6 * door; g += 0.95 * door; b += 0.35 * door
        side = math.pow(abs(x), 5) * max(0.0, 0.45 + y) * (0.6 + 0.4 * math.cos(z * 9))
        r += 0.2 * side; g += 0.12 * side; b += 0.05 * side
        scr = math.pow(max(0.0, x), 3) * math.pow(max(0.0, -z + 0.2), 2) * max(0.0, 0.6 - abs(y - 0.2))
        r += 0.18 * scr; g += 0.22 * scr; b += 0.28 * scr
        return (r, g, b)
    env = L.env_tex(env_fn, 256, 128, name='corridor_env')
    C.parts['env'] = env
    # three gave each material this environment as its own envMap at its own intensity, and the scene none (her VRM is
    # lit by the set's lamps and its hemisphere light only). opts ibl='material' (the default) does the same: each
    # material adds its image-based light (cn_lib NB.ibl) and the world is the hemisphere term alone. ibl='world':
    # the environment is the world at 0.75 instead (one intensity for all, and it lights her too).
    ibl_mode = opts.get('ibl', 'material')
    if ibl_mode == 'material':
        L.ibl_env(env_fn, env_img=env, name='corridor_env')
    if opts.get('world', True):
        C.world = CL.make_world(L, 'corridor_world', env if ibl_mode == 'world' else None, env_i=0.75,
                                hemi=(0x3a2a1a, 0x0a0405, 0.06), scene=sc)

    goldC = hex_linear(0xd8a23f)

    def gold_vein(nb, c):
        """Marble016's white veins -> gold veins over a warm black."""
        v = nb.ss(0.07, 0.42, nb.lum(c))
        col_ = nb.mix(c * (0.5, 0.44, 0.4) + (0.005, 0.0035, 0.0025), nb.w(goldC) * (v * 0.4 + 0.5), v)
        return col_, v

    def fan(nb, z, y, side):
        """The sconce fan: a Balla sun-cone of gold thrown up the marble from each sconce (bay centres z = 16 ... -20);
        side = the sign of the wall's x; the right wall has no sconces behind the LED wall."""
        k = nb.clamp(nb.floor((16.0 - z) / 4.0 + 0.5), 0, 9)
        zc = 16.0 - k * 4.0
        dz, dy = z - zc, y - SCONCE_Y
        ang = nb.atan2(dz, nb.max(dy, 0.001))
        up = nb.ss(-0.05, 0.3, dy)
        cone = nb.ss(0.66, 0.5, nb.abs(ang)) * up
        ribs = nb.ss(0.06, 0.2, nb.abs(nb.fract(ang * (6.0 / math.pi) + 0.5) - 0.5)) * 0.6 + 0.4
        fall = nb.exp(nb.max(dy, 0.0) * -0.36)
        core = nb.exp((dz * dz + (dy - 0.1) * (dy - 0.1)) * -9.0)
        mdy = nb.min(dy, 0.0)
        below = nb.exp(dz * dz * -1.4 + mdy * mdy * -2.6) * 0.16 * (1.0 - up)
        off = nb.step(0.0, side) * nb.step(-16.5, zc) * nb.step(zc, -3.5)
        return (cone * ribs * fall + core * 0.45 + below) * (1.0 - off)

    def fan_soft(nb, z, y, side, dist):
        """The same fan softened for the floor's mirror (no ribs or hot core; blurrier the further the ray goes)."""
        k = nb.clamp(nb.floor((16.0 - z) / 4.0 + 0.5), 0, 9)
        zc = 16.0 - k * 4.0
        dz, dy = z - zc, y - SCONCE_Y
        blur = nb.clamp(dist * 0.04, 0.05, 0.4)
        ang = nb.atan2(dz, nb.max(dy, 0.001))
        cone = (1.0 - nb.ss(0.4 - blur, 0.62 + blur, nb.abs(ang))) * nb.ss(-0.2, 0.6, dy)
        fall = nb.exp(nb.max(dy, 0.0) * -0.3)
        off = nb.step(0.0, side) * nb.step(-16.5, zc) * nb.step(zc, -3.5)
        return cone * fall * 0.8 * (1.0 - off)

    def flick(nb):
        return nb.U('flick')

    M = {}
    C.materials = M

    # the marble walls: book-matched slabs 2.4 m wide, gold veins, the sconce fans painted on as light. The slabs'
    # texture uv (book-matched, a hashed offset per pair) is computed per vertex on mesh edges (UVBook, see
    # book_match): the JS sampled it with explicit gradients so the jumps drew no seam; EEVEE takes them on edges.
    def marble_mat():
        Mt = L.mat('corridor_marble')
        nb = Mt.nb
        tuv = nb.uv('UVBook')
        c0, _ = nb.tex(S['marble']['col'], tuv)
        col_, v = gold_vein(nb, c0)
        r0, _ = nb.tex(S['marble']['rgh'], tuv)
        nt, _ = nb.tex(S['marble']['nrm'], tuv)
        P = nb.P()
        side = nb.sign(P.x)
        on_wall = nb.ss(HW - 0.2, HW - 0.02, nb.abs(P.x))           # only the side-wall faces carry fans
        f = fan(nb, P.z, P.y, side) * on_wall
        em = nb.w(WARM) * f * (nb.lum(col_) * 3.0 + 0.022) * nb.U('lights') * flick(nb)
        return Mt.standard(col_, rough=nb.clamp(r0.x * 0.3 + 0.05 + v * 0.14, 0.04, 1.0), metal=v * 0.75,
                           normal=nb.normal_map(nt, 0.35), emissive=em, ibl=L.ibl(0.9))
    M['marble'] = marble_mat()

    # gold: polished hammered gilding (pilasters, frames, ribs, rails)
    M['gold'] = L.pbr_mat(S['goldH'], name='corridor_gold', tile=1.1, metal='map', rough=(0.5, 0.2), macro=0.3,
                          macro_scale=0.6, tint=[0.78, 0.58, 0.32], nrm=0.7, env_i=L.env_i(0.7))
    # fluted gold: the pilaster faces carry vertical flutes (period 12.5 cm, aligned to every pilaster)
    flute_cv = CL.create_canvas(64, 4)
    gfl = flute_cv.get_context('2d')
    for x in range(64):
        s_ = abs(math.sin((x + 0.5) / 64 * math.pi))
        v_ = _js_round(255 * math.pow(s_, 0.6))
        gfl.fill_style = f'rgb({v_},{v_},{v_})'
        gfl.fill_rect(x, 0, 1, 4)
    flute_tex = L.canvas_tex(flute_cv, srgb=False, wrap=CL.REPEAT, name='corridor_flute')

    def flute_post(d):
        nb = d['nb']
        h, _ = nb.tex(flute_tex, nb.uv() * (8.0, 0.25, 1.0))
        # TSL bumpMap(tex, 0.55) tilts by 0.55 x the height change per PIXEL (its surface derivatives are
        # normalised), so the flutes deepen with distance; Blender's Bump takes a height in metres: 0.55 x the pixel's
        # footprint on the surface (view depth x the 'pix' uniform, stretched by the view angle) is the same tilt
        return {'normal': nb.bump(h.x, strength=1.0, distance=nb.view_z() * nb.U('pix') * 0.55
                                  / nb.max(nb.facing(), 0.08))}
    M['goldFluted'] = L.pbr_mat(S['goldH'], name='corridor_gold_fluted', tile=1.1, metal='map', rough=(0.5, 0.22),
                                tint=[0.78, 0.57, 0.31], macro=0.3, macro_scale=0.6, post=flute_post,
                                env_i=L.env_i(0.7))
    M['goldTrim'] = L.pbr_mat(S['goldF'], name='corridor_gold_trim', tile=0.8, metal='map', rough=(0.6, 0.14),
                              tint=[0.82, 0.64, 0.38], env_i=L.env_i(0.75))
    M['bronze'] = L.pbr_mat(S['bronze'], name='corridor_bronze', tile=0.9, metal=1, rough=(0.8, 0.1),
                            tint=[0.75, 0.55, 0.35], env_i=L.env_i(0.9))

    # the LED wall's post exists before the floor (the floor mirrors it): see further down for the wall itself
    SW, SH = SCR['z1'] - SCR['z0'], SCR['y1'] - SCR['y0']
    post_vars = ImageVariants(L, 'corridor_post', 'post_variant')

    # the floor: diagonal 1.6 m slabs of the same marble with gold inlay joints, a black border band, a Balla
    # sunburst inlaid before the door; it mirrors the room's light (analytic reflections of the fans, the LED wall,
    # the lanterns and the door) and the light that leaks under the door.
    def floor_mat():
        Mt = L.mat('corridor_floor')
        nb = Mt.nb
        P = nb.P()
        q = nb.vec2(P.x + P.z, P.z - P.x) * (0.70710678 / 1.6)
        f = nb.fract(q)
        tUV = nb.uv('UVTile')                                         # f * 0.62 + hash(cell) * 4, per tile, on edges
        c0, _ = nb.tex(S['marble']['col'], tUV)
        r0, _ = nb.tex(S['marble']['rgh'], tUV)
        vc, v = gold_vein(nb, c0)
        de = nb.min(nb.min(f.x, 1.0 - f.x), nb.min(f.y, 1.0 - f.y)) * 1.6
        joint = 1.0 - nb.ss(0.007, 0.013, de)
        ax = nb.abs(P.x)
        band = nb.step(HW - 0.62, ax)
        band_lines = nb.ss(0.03, 0.018, nb.abs(ax - (HW - 0.62))) + nb.ss(0.018, 0.01, nb.abs(ax - (HW - 0.48)))
        dzD = P.z - ZD
        rD = nb.length(nb.vec2(P.x, dzD))
        th = nb.atan2(P.x, nb.max(dzD, 0.001))
        rays = nb.step(0.5, nb.fract(th * (15 / math.pi) + 0.5))
        front = nb.step(0.0, dzD)
        sun = (nb.step(rD, 4.4) * nb.step(1.3, rD) * rays + nb.step(rD, 1.05)
               + nb.ss(0.05, 0.03, nb.abs(rD - 4.55)) + nb.ss(0.04, 0.022, nb.abs(rD - 1.18))) * front
        inlay = nb.clamp(joint * (1.0 - band) * nb.step(4.7, rD) + band_lines + sun, 0, 1)
        band_col = vc * nb.mix(1.0, 0.35, band)
        col_ = nb.mix(band_col, nb.w(goldC) * 0.9, inlay)
        rough = nb.mix(r0.x * 0.25 + 0.035 + v * 0.1, 0.16, inlay)
        metal = nb.mix(v * 0.7 * (1.0 - band), 1.0, inlay)
        nt, _ = nb.tex(S['marble']['nrm'], tUV)
        # ---- analytic reflections of the emitters (a polished floor reads by what it mirrors)
        cam = nb.cam_local()
        V = nb.normalize(P - cam)
        R = nb.vec3(V.x, -V.y, V.z)
        sx = nb.select(nb.gt(R.x, 0.0), 1.0, -1.0)
        tW = (sx * (HW - 0.03) - P.x) / nb.select(nb.gt(nb.abs(R.x), 1e-4), R.x, sx * 1e-4)
        tD = nb.select(nb.lt(R.z, -1e-4), ((ZD + 0.12) - P.z) / nb.min(R.z, -1e-4), 1e4)
        hitW, hitD = P + R * tW, P + R * tD
        wall_first = nb.lt(tW, tD)
        fanR = fan_soft(nb, hitW.z, hitW.y, sx, tW)
        su = (hitW.z - SCR['z0']) / (SCR['z1'] - SCR['z0'])
        sv = (hitW.y - SCR['y0']) / (SCR['y1'] - SCR['y0'])
        in_scr = nb.step(0, su) * nb.step(su, 1) * nb.step(0, sv) * nb.step(sv, 1) * nb.step(0.0, sx)
        # texture(post).level(lvl), lvl = clamp(tW * 0.35 + 1.5, 1.5, 6): two pre-blurred copies, mixed by level
        lvl = nb.clamp(tW * 0.35 + 1.5, 1.5, 6.0)
        b1, _ = post_vars.sample(nb, 'blur1', nb.vec2(su, sv))
        b2, _ = post_vars.sample(nb, 'blur2', nb.vec2(su, sv))
        scr_refl = nb.mix(b1, b2, nb.clamp((lvl - 1.5) / 4.5, 0, 1)) * in_scr * nb.U('screen') * 0.9
        emitW = nb.w(WARM) * fanR * 0.32 + scr_refl
        # the door: the gap of light down the middle and under it, the lit gold portal, the blaze when it opens
        dx, dyh = nb.abs(hitD.x), hitD.y
        seam = nb.exp(dx * dx * -900.0) * nb.step(dyh, DOOR_H) * nb.U('gap')
        portal = nb.step(dx, 4.3) * nb.step(dyh, 10.9) * 0.06
        opening = nb.step(dx, nb.U('open') * DOOR_HW) * nb.step(dyh, DOOR_H) * nb.U('beyond') * 2.2
        emitD = nb.w((1.0, 0.72, 0.4)) * (seam * 1.5 + portal + opening)
        lanternR = nb.w((0.0, 0.0, 0.0))
        for zl in LANT:
            w_ = nb.w((0.0, LANT_Y, float(zl))) - P
            s_ = nb.dot(w_, R)
            d2 = nb.dot(w_, w_) - s_ * s_
            lanternR = lanternR + nb.w((1.0, 0.7, 0.4)) * (nb.exp(d2 * -2.5) * nb.step(0, s_) * 0.45)
        emit = nb.select(wall_first, emitW, emitD) + lanternR
        cosv = nb.clamp(-V.y, 0, 1)
        F = 0.04 + nb.pow(1.0 - cosv, 5.0) * 0.96
        gloss = nb.clamp(1.0 - rough * 2.2, 0, 1)
        tint = nb.mix((1.0, 1.0, 1.0), nb.w(goldC) * 1.3, metal)
        refl = emit * F * gloss * tint
        # light leaking under the door, and pools under the lanterns
        under = (nb.exp(nb.max(P.z - ZD, 0.0) * -5.0) * nb.ss(3.35, 3.0, ax)
                 * (nb.U('gap') * 0.6 + nb.U('open') * nb.U('beyond') * 1.6))
        pools = 0.0
        for zl in LANT:
            pools = pools + nb.exp((P.x * P.x + (P.z - zl) * (P.z - zl)) * -0.22)
        em = (refl + nb.w((1.0, 0.66, 0.32)) * under * 0.9 + col_ * pools * WARM * 0.04) * nb.U('lights')
        return Mt.standard(col_, rough=nb.clamp(rough, 0.03, 1), metal=metal, normal=nb.normal_map(nt, 0.25),
                           emissive=em, ibl=L.ibl(0.45))

    # the red runner: crimson cut pile with two woven gold border stripes, a walked-flat path, lantern pools
    # (no envMap in the WebGPU set: the runner takes no environment light)
    def carpet_post(d):
        nb, col_, rough = d['nb'], d['col'], d['rough']
        P = d['P']
        ex = 1.4 - nb.abs(P.x)
        s1 = nb.ss(0.022, 0.012, nb.abs(ex - 0.11))
        s2 = nb.ss(0.012, 0.006, nb.abs(ex - 0.17))
        gold = nb.clamp(s1 + s2, 0, 1)
        path = nb.exp(P.x * P.x * -3.0) * 0.18
        pools = 0.0
        for zl in LANT:
            pools = pools + nb.exp((P.x * P.x + (P.z - zl) * (P.z - zl)) * -0.3)
        c = nb.mix(col_ * (1.0 - path), nb.hex(0xb8862e), gold * 0.85)
        return {'col': c, 'rough': nb.mix(rough, 0.45, gold),
                'emissive': c * (pools * 0.05 + 0.002) * WARM * nb.U('lights')}
    M['carpet'] = L.pbr_mat(S['pile'], name='corridor_carpet', tile=0.55, physical=True, nrm=0.9, rough=(0.4, 0.55),
                            sheen=1.0, sheen_roughness=0.45, sheen_color=0x7a1820,
                            recolor=lambda c, nb: nb.w((0.36, 0.022, 0.03)) * (nb.lum(c) * 2.4 + 0.18),
                            post=carpet_post)

    # the ceiling: black lacquer coffers with gold border lines, warmed above the lanterns
    def ceiling_post(d):
        nb, col_, rough = d['nb'], d['col'], d['rough']
        P = d['P']
        zr = nb.fract((P.z - 2.0) / 4.0) * 4.0                        # 0..4 between ribs
        ez, ex = nb.min(zr, 4.0 - zr), HW - nb.abs(P.x)
        line = (nb.ss(0.03, 0.015, nb.abs(ez - 0.55)) * nb.step(0.55, ex)
                + nb.ss(0.03, 0.015, nb.abs(ex - 0.55)) * nb.step(0.55, ez))
        g = nb.clamp(line, 0, 1)
        glow = 0.0
        for zl in LANT:
            glow = glow + nb.exp((P.x * P.x * 0.25 + (P.z - zl) * (P.z - zl)) * -0.18)
        c = nb.mix(col_, nb.w(goldC) * 0.8, g)
        return {'col': c, 'rough': nb.mix(rough, 0.2, g), 'metal': g,
                'emissive': nb.w(WARM) * glow * (c * 3.0 + 0.004) * 0.25 * nb.U('lights')}
    M['ceiling'] = L.pbr_mat(S['lacq'], name='corridor_ceiling', tile=2.0,
                             recolor=lambda c, nb: nb.w((0.012, 0.009, 0.007)) * (nb.lum(c) * 1.5 + 0.6),
                             rough=(0.3, 0.12), nrm=0.4, post=ceiling_post, env_i=L.env_i(0.5))

    # warm frosted glass (sconce fans, lantern panes, torchere bowls): self-lit
    def glass_mat():
        Mt = L.mat('corridor_glass')
        nb = Mt.nb
        n = nb.mx_noise(nb.P() * 9.0) * 0.12 + 1.0
        return Mt.unlit(nb.w((1.0, 0.68, 0.36)) * 1.5 * n * flick(nb) * nb.U('lights'), side='double')
    M['glass'] = glass_mat()

    # ------------------------------------------------------------------------------------------- architecture
    B = {k: L.bucket(f'corridor_{k}') for k in ('marble', 'gold', 'flute', 'trim', 'bronze', 'glass')}
    B['flute'].name = 'corridor_gold_fluted'
    LEN, ZM = ZN - ZD, (ZN + ZD) / 2
    # walls (a 0.4 m slab behind each face, running past the end walls so the corners are closed), the near end wall,
    # the door wall around its opening
    for s in (-1, 1):
        B['marble'].box(0.4, HC, LEN + 0.8, s * (HW + 0.2), HC / 2, ZM)
    B['marble'].box(2 * HW, HC, 0.4, 0, HC / 2, ZN + 0.2)
    B['marble'].box(HW - DOOR_HW, HC, 0.4, -(HW + DOOR_HW) / 2, HC / 2, ZD - 0.2)
    B['marble'].box(HW - DOOR_HW, HC, 0.4, (HW + DOOR_HW) / 2, HC / 2, ZD - 0.2)
    B['marble'].box(2 * DOOR_HW, HC - 9.85, 0.4, 0, (HC + 9.85) / 2, ZD - 0.2)
    B['marble'].box(2 * DOOR_HW, 1.85, 0.3, 0, 8.975, ZD - 0.15)               # the transom's backing
    # skirting + dado rail along both walls
    for s in (-1, 1):
        B['bronze'].box(0.04, 0.26, LEN, s * (HW - 0.02), 0.13, ZM)
        B['trim'].box(0.06, 0.07, LEN, s * (HW - 0.03), 1.1, ZM)
        B['gold'].box(0.75, 0.42, LEN, s * (HW - 0.375), 10.81, ZM)             # cornice band
        B['gold'].box(0.5, 0.14, LEN, s * (HW - 0.25), 10.53, ZM)               # its stepped soffit
    # pilasters: a marble plinth, a stepped gilded shaft (fluted front), a corbelled Deco capital
    for s in (-1, 1):
        for zp in PIL:
            if s > 0 and zp in SCR_SKIP:
                continue

            def X_(d, s=s):
                return s * (HW - d / 2)
            B['marble'].box(0.66, 0.72, 1.46, X_(0.66), 0.36, zp)
            B['gold'].box(0.62, 0.06, 1.42, X_(0.62), 0.75, zp)
            B['gold'].box(0.18, 8.9, 1.2, X_(0.18), 5.23, zp)
            B['gold'].box(0.34, 8.9, 0.9, X_(0.34), 5.23, zp)
            B['flute'].box(0.5, 8.9, 0.6, X_(0.5), 5.23, zp)
            B['gold'].box(0.56, 0.3, 0.72, X_(0.56), 9.83, zp)
            B['gold'].box(0.62, 0.3, 0.98, X_(0.62), 10.13, zp)
            B['gold'].box(0.7, 0.32, 1.32, X_(0.7), 10.44, zp)
    # ribs across the ceiling at every pilaster: a stepped gilded beam
    for zp in PIL:
        B['gold'].box(2 * HW, 0.75, 0.6, 0, HC - 0.375, zp)
        B['gold'].box(2 * HW - 1.4, 0.24, 0.34, 0, HC - 0.87, zp)
    # the ceiling and floor slabs (0.4 m, as the walls), running over and under the walls
    ceilB = L.bucket('corridor_ceiling').box(2 * HW + 0.8, SLAB, LEN + 0.8, 0, HC + SLAB / 2, ZM)
    floorB = L.bucket('corridor_floor').box(2 * HW + 0.8, SLAB, LEN + 0.8, 0, -SLAB / 2, ZM)
    # the runner (2.8 m wide), from the near end to the door's threshold
    carpetB = L.bucket('corridor_carpet').box(2.8, 0.014, ZN - (ZD + 0.35), 0, 0.007, (ZN + ZD + 0.35) / 2, scale=1)

    # sconces on the bays (both walls; none behind the LED wall); the pendant lanterns down the axis
    for s in (-1, 1):
        for k in range(10):
            zc = 16 - 4 * k
            if s > 0 and -16.5 <= zc <= -3.5:
                continue
            x0 = s * (HW - 0.02)
            B['gold'].box(0.05, 0.62, 0.42, x0 - s * 0.025, SCONCE_Y - 0.05, zc)
            th0 = 0.0 if s < 0 else math.pi
            B['glass'].add(cylinder_geometry(0.34, 0.07, 0.5, 18, 1, True, th0, math.pi), m4(x0, SCONCE_Y + 0.02, zc),
                           uv='keep')
            for a in (0.35, 0.8, 1.25):                                     # three gilded ribs over the glass
                for sg in (-1, 1):
                    ang = th0 + math.pi / 2 + sg * (math.pi / 2 - a)
                    rr = 0.2
                    B['gold'].box(0.025, 0.52, 0.025, x0 + math.sin(ang) * rr, SCONCE_Y + 0.02, zc + math.cos(ang) * rr)
            B['gold'].box(0.3, 0.05, 0.05, x0 - s * 0.15, SCONCE_Y - 0.25, zc)   # the bracket
    for zl in LANT:
        y0 = LANT_Y - 0.75
        R8 = m4(0, y0, zl, 0, math.pi / 8, 0)
        B['glass'].add(lathe_geometry([[0.001, 0.25], [0.3, 0.25], [0.3, 1.0], [0.001, 1.0]], 8), R8, uv='keep')
        B['gold'].add(lathe_geometry([[0.001, -0.06], [0.08, -0.06], [0.14, 0.04], [0.2, 0.12], [0.28, 0.18],
                                      [0.33, 0.25], [0.33, 0.29], [0.31, 0.29], [0.31, 0.25]], 8), R8)
        B['gold'].add(lathe_geometry([[0.31, 0.98], [0.37, 1.0], [0.37, 1.07], [0.27, 1.1], [0.27, 1.18], [0.17, 1.2],
                                      [0.17, 1.28], [0.07, 1.3], [0.05, 1.36], [0.001, 1.36]], 8), R8)
        for i in range(8):                                                   # mullions at the octagon's corners
            a = i * math.pi / 4 + math.pi / 8
            B['gold'].box(0.03, 0.76, 0.03, math.sin(a) * 0.3, y0 + 0.62, zl + math.cos(a) * 0.3)
        B['gold'].add(lathe_geometry([[0.298, 0.6], [0.318, 0.6], [0.318, 0.64], [0.298, 0.64]], 8), R8)
        B['gold'].box(0.04, HC - (y0 + 1.36), 0.04, 0, (HC + y0 + 1.36) / 2, zl)     # the rod to the ceiling

    # ------------------------------------------------- the portal: a stepped gilded architrave and a Deco crown
    zf = ZD
    for s in (-1, 1):
        B['gold'].box(0.3, 9.85, 0.6, s * (DOOR_HW + 0.15), 9.85 / 2, zf + 0.3)
        B['gold'].box(0.4, 10.5, 0.42, s * (DOOR_HW + 0.5), 10.5 / 2, zf + 0.21)
        B['gold'].box(0.4, 10.9, 0.26, s * (DOOR_HW + 0.9), 10.9 / 2, zf + 0.13)
    B['gold'].box(2 * DOOR_HW + 0.6, 0.3, 0.6, 0, 10.0, zf + 0.3)
    B['gold'].box(2 * DOOR_HW + 1.4, 0.4, 0.42, 0, 10.35, zf + 0.21)
    B['gold'].box(2 * DOOR_HW + 2.2, 0.4, 0.26, 0, 10.75, zf + 0.13)
    B['gold'].box(5.2, 0.36, 0.32, 0, 11.13, zf + 0.16)
    B['gold'].box(3.2, 0.34, 0.36, 0, 11.48, zf + 0.18)
    B['gold'].box(1.6, 0.36, 0.4, 0, 11.82, zf + 0.2)
    B['gold'].box(2 * DOOR_HW, 0.1, 0.5, 0, DOOR_H + 0.05, zf + 0.25)          # the transom bar
    # torcheres flanking the door
    for s in (-1, 1):
        x, z = s * 3.95, ZD + 1.45
        B['gold'].add(lathe_geometry([[0.001, 0], [0.26, 0], [0.26, 0.08], [0.2, 0.08], [0.2, 0.16], [0.13, 0.16],
                                      [0.13, 0.24], [0.06, 0.3], [0.05, 1.9], [0.08, 1.95], [0.08, 2.0], [0.05, 2.05]], 8),
                      m4(x, 0, z, 0, math.pi / 8, 0))
        B['glass'].add(lathe_geometry([[0.05, 2.05], [0.22, 2.18], [0.36, 2.32], [0.38, 2.34]], 16), m4(x, 0, z),
                       uv='keep')
        B['gold'].add(torus_geometry(0.375, 0.018, 6, 24), m4(x, 2.34, z, math.pi / 2, 0, 0))

    # -------------------------------------------------- relief textures: the door leaves and the plaque
    door_rel = _door_relief(L)
    M['doorL'] = _door_mat(L, S, door_rel, False)
    M['doorR'] = _door_mat(L, S, door_rel, True)
    plaque = _plaque_relief(L, opts.get('plaque', ('SUPREME', 'INTELLIGENCE')))
    M['plaque'] = _plaque_mat(L, S, plaque)

    # ------------------------------------------------------------------------------------ meshes of the room
    room = L.empty('corridor_room', parent=root)
    C.parts['room'] = room

    def add_mesh(b, mat, shadow=True, **fl):
        return b.mesh(mat, parent=room, shadow=shadow, flags=fl or None)

    marble_geo = _book_match(B['marble'].geometry())
    m_marble = L.mesh_object('corridor_marble', marble_geo, M['marble'], parent=room)
    add_mesh(B['gold'], M['gold'], noSupportCheck=True)
    add_mesh(B['flute'], M['goldFluted'], noSupportCheck=True)
    add_mesh(B['trim'], M['goldTrim'], noSupportCheck=True, allowIntersect=True)
    add_mesh(B['bronze'], M['bronze'], noSupportCheck=True, allowIntersect=True)
    sconce_glass = add_mesh(B['glass'], M['glass'], shadow=False, noSupportCheck=True)  # glowing shades: no shadow
    add_mesh(ceilB, M['ceiling'], noSupportCheck=True)
    M['floor'] = floor_mat()
    floor_geo = _tile_uv(floorB.geometry())
    L.mesh_object('corridor_floor', floor_geo, M['floor'], parent=room)
    add_mesh(carpetB, M['carpet'], noZFightCheck=True)

    # the plaque (on the transom) and the doors (each on its hinge pivot)
    plaque_ob = L.mesh_object('corridor_plaque', plane_geometry(2 * DOOR_HW, 1.7), M['plaque'], parent=room,
                              M3=m4(0, DOOR_H + 0.1 + 0.85, zf + 0.06), flags={'noSupportCheck': True})
    doors = L.empty('corridor_doors', parent=room)
    pivotL = L.empty('door_pivot_left', parent=doors, M3=m4(-DOOR_HW, 0, zf - 0.11))
    pivotR = L.empty('door_pivot_right', parent=doors, M3=m4(DOOR_HW, 0, zf - 0.11))
    for pv in (pivotL, pivotR):
        pv.rotation_mode = 'XYZ'
    leaf_geo = box_geometry(DOOR_HW, DOOR_H, 0.22)
    leafL = L.mesh_object('door_left', leaf_geo, M['doorL'], parent=pivotL, M3=m4(DOOR_HW / 2, DOOR_H / 2, 0),
                          flags={'assembly': 'corridor_doors', 'noSupportCheck': True})
    leafR = L.mesh_object('door_right', leaf_geo, M['doorR'], parent=pivotR, M3=m4(-DOOR_HW / 2, DOOR_H / 2, 0),
                          flags={'assembly': 'corridor_doors', 'noSupportCheck': True})
    ring_geo = torus_geometry(0.17, 0.024, 10, 28)
    for pv, sxp in ((pivotL, 1), (pivotR, -1)):
        L.mesh_object('door_pull', ring_geo, M['goldTrim'], parent=pv, M3=m4(sxp * (DOOR_HW - 0.31), 1.12, 0.15))
    # the seam of light between the leaves
    Ms = L.mat('corridor_door_seam')
    nbs = Ms.nb
    M['seam'] = Ms.unlit(nbs.w((1.0, 0.75, 0.42)) * 4.0 * nbs.U('gap') * (1.0 - nbs.ss(0.02, 0.12, nbs.U('open'))),
                         additive=True)
    seam = L.mesh_object('door_seam', plane_geometry(0.05, DOOR_H), M['seam'], parent=doors,
                         M3=m4(0, DOOR_H / 2, zf + 0.012), shadow=False)
    # beyond the door: a room of light (only seen through the opening); three's BackSide: the box's winding is
    # reversed so its inside faces are its front
    Mb = L.mat('corridor_beyond')
    nbb = Mb.nb
    q = nbb.P()
    cb = nbb.exp(q.x * q.x * -0.05 + (q.y - 4.0) * (q.y - 4.0) * -0.04)
    M['beyond'] = Mb.unlit(nbb.w((1.0, 0.78, 0.48)) * (cb * 2.6 + 0.35) * (nbb.U('beyond') * 0.9 + 0.1), side='front')
    beyond = L.mesh_object('corridor_beyond', _inside_out(box_geometry(12, 12, 9)), M['beyond'], parent=room,
                           M3=m4(0, 6, zf - 4.9), shadow=False, flags={'noSupportCheck': True})
    # god-ray shafts through the opening (additive wedge), only while the door opens
    Msh = L.mat('corridor_shafts')
    nbh = Msh.nb
    q = nbh.P()
    along = nbh.clamp((q.z - ZD) / 26.0, 0, 1)
    spread = DOOR_HW * 1.0 + along * 4.0
    edge = (1.0 - nbh.ss(spread * 0.25, spread, nbh.abs(q.x))) * nbh.ss(0, 0.5, q.y)
    nsh = nbh.mx_noise(nbh.vec3(q.x * 0.6, q.y * 0.15, nbh.U('t') * 0.05)) * 0.35 + 0.75
    M['shafts'] = Msh.unlit(nbh.w((1.0, 0.76, 0.45)) * nbh.pow(1.0 - along, 2.2) * edge * nsh
                            * (nbh.U('open') * nbh.U('beyond')) * 0.07, additive=True)
    z0s, z1s = ZD + 0.05, 2.0
    sv_ = [[-DOOR_HW, 0.03, z0s], [DOOR_HW, 0.03, z0s], [DOOR_HW, DOOR_H, z0s], [-DOOR_HW, DOOR_H, z0s],
           [-DOOR_HW - 4, 0.03, z1s], [DOOR_HW + 4, 0.03, z1s], [DOOR_HW + 4, 2.2, z1s], [-DOOR_HW - 4, 2.2, z1s]]
    sidx = [0, 1, 5, 0, 5, 4, 1, 2, 6, 1, 6, 5, 2, 3, 7, 2, 7, 6, 3, 0, 4, 3, 4, 7]
    shaft_geo = Geo(sv_, None, np.zeros((8, 2)), sidx).compute_vertex_normals()
    shafts = L.mesh_object('corridor_shafts', shaft_geo, M['shafts'], parent=room, shadow=False, weld=False,
                           flags={'noSupportCheck': True})

    # --------------------------------------------------------------- the LED wall: a post in capital letters
    PW_ = 2048
    PH_ = _js_round(2048 * SH / SW)
    post_state = {'text': '', 'name': 'DEPARTMENT OF WAR', 'meta': 'Official account · now',
                  'stats': ['18.2K', '41.7K', '196K', '11.4M'], 'layout': None, 'reveal': 1.0, 'shown': 0,
                  'variant': 0, 'variants': {}}

    def make_post_variant(text, name_, meta, stats):
        """Draw a post fully revealed (the colour), its typing order (each body character's index, so the shader
        shows the first n), the cursor's place after every n, and two blurred copies for the floor's mirror."""
        cv = CL.create_canvas(PW_, PH_)
        g = cv.get_context('2d')
        st = {'text': text, 'name': name_, 'meta': meta, 'stats': stats, 'layout': None}
        geo_ = _draw_post(g, PW_, PH_, st, 1.0, fam)
        rgba = cv.pixels()
        idx = _post_index_map(PW_, PH_, st, geo_, fam)
        lut = _post_cursor_lut(st, geo_, fam, PW_, PH_)
        tag = f'{len(post_vars.items)}'
        col_img = L.data_tex(rgba, srgb=True, name=f'corridor_post_{tag}')
        idx_img = L.own(CL.image_from_rgba(f'corridor_post_order_{tag}', idx, srgb=False, interpolation='Closest',
                                           extension='EXTEND'))
        lut_img = L.own(CL.image_from_rgba(f'corridor_post_cursor_{tag}', lut, srgb=False, top_down=False,
                                           interpolation='Closest', extension='EXTEND'))
        from PIL import Image as _Im
        pim = _Im.fromarray(rgba, 'RGBA')
        b1 = np.asarray(pim.resize((PW_ // 4, PH_ // 4), _Im.Resampling.BOX).resize((PW_ // 8, PH_ // 8), _Im.Resampling.BOX))
        b2 = np.asarray(pim.resize((PW_ // 32, max(2, PH_ // 32)), _Im.Resampling.BOX))
        b1_img = L.data_tex(b1, srgb=True, name=f'corridor_post_blur1_{tag}')
        b2_img = L.data_tex(b2, srgb=True, name=f'corridor_post_blur2_{tag}')
        return {'color': col_img, 'order': idx_img, 'cursor': lut_img, 'blur1': b1_img, 'blur2': b2_img}, st, (geo_, cv)

    post_meta = {}

    def set_text(s, name=None, meta=None, stats=None, reveal=1.0, ctx=None, frame=None):
        """setText(str, {name, meta, stats, reveal}): repost in capitals. At build time it replaces the shown post;
        inside update (ctx / frame given) the switch is keyed (CONSTANT)."""
        text = ' '.join(str(s or '').upper().split())
        if name is not None:
            post_state['name'] = str(name)
        if meta is not None:
            post_state['meta'] = str(meta)
        if stats is not None:
            post_state['stats'] = list(stats)
        sig = (text, post_state['name'], post_state['meta'], tuple(post_state['stats']))
        found = post_state['variants'].get(sig)
        if found is None:
            imgs, st, (geo_, cv_) = make_post_variant(text, post_state['name'], post_state['meta'], post_state['stats'])
            vi = post_vars.add(imgs, sig=sig)
            post_meta[vi] = (st, geo_, cv_)
            post_state['variants'][sig] = vi
            found = vi
        post_state['text'] = text
        post_state['layout'] = post_meta[found][0]['layout']
        post_state['variant'] = found
        post_state['reveal'] = float(reveal)
        post_state['shown'] = _js_round(len(text) * float(reveal))
        C.set_u('post_variant', found, ctx=ctx, frame=frame, interpolation='CONSTANT')
        C.set_u('post_n', post_state['shown'], ctx=ctx, frame=frame, interpolation='CONSTANT')
        C.set_u('post_cursor', 1.0 if reveal < 1 else 0.0, ctx=ctx, frame=frame, interpolation='CONSTANT')
        return found

    set_text(opts.get('postText', 'AI DOMINANT!'))

    def screen_mat():
        Mt = L.mat('corridor_ledwall')
        nb = Mt.nb
        u0 = nb.uv()
        c, _ = post_vars.sample(nb, 'color', u0)
        order, _ = post_vars.sample(nb, 'order', u0)
        idx = nb.round(order.x * 255.0)
        shown = nb.step(idx, nb.U('post_n') + 0.5)                    # 0 = not body text: always there
        c = nb.mix(CL.hex_linear(0x090c12), c, shown)                  # an untyped letter shows the card behind it
        # the cursor: a gold bar after the n-th character (its place per n in a lookup row)
        cur, _ = post_vars.sample(nb, 'cursor', nb.vec2((nb.U('post_n') + 0.5) / 256.0, 0.5))
        px, py = u0.x * PW_, (1.0 - u0.y) * PH_
        cin = (nb.step(cur.x, px) * nb.step(px, cur.x + cur.z) * nb.step(cur.y, py)
               * nb.step(py, cur.y + nb.comp(cur, 2) * (0.86 / 0.09)))
        c = nb.mix(c, CL.hex_linear(0xc9973a), cin * nb.U('post_cursor'))
        cells = (SW / 0.012, SH / 0.012, 1.0)
        g2 = nb.abs(nb.fract(u0 * cells) - 0.5)
        dotm = nb.ss(0.5, 0.32, nb.max(g2.x, g2.y))
        fw = nb.fwidth_est(1.0 / 0.012)
        grid = nb.mix(dotm * 0.9 + 0.3, 0.78, nb.ss(0.2, 0.7, fw))
        # the LED wall's 0.5 m tiles: a faint dark seam between them (fades out when sub-pixel)
        tq = nb.abs(nb.fract(u0 * (SW / 0.5, SH / 0.5, 1.0)) - 0.5)
        tfw = nb.fwidth_est(1.0 / 0.5)
        seam_t = nb.ss(0.494, 0.499, nb.max(tq.x, tq.y)) * (1.0 - nb.ss(0.004, 0.02, tfw))
        scan = nb.ss(0.0, 0.03, nb.abs(nb.fract(u0.y - nb.U('t') * 0.11) - 0.5)) * 0.06 + 0.94
        return Mt.unlit(c * grid * scan * (1.0 - seam_t * 0.6) * nb.U('screen') * 1.7)
    M['screen'] = screen_mat()
    screen = L.mesh_object('corridor_ledwall', plane_geometry(SW, SH), M['screen'], parent=room,
                           M3=m4(HW - 0.07, (SCR['y0'] + SCR['y1']) / 2, (SCR['z0'] + SCR['z1']) / 2, 0, -math.pi / 2, 0),
                           shadow=False, flags={'noSupportCheck': True})
    fb = L.bucket('corridor_screen_frame')                           # its stepped gilded frame
    zc_, yc_ = (SCR['z0'] + SCR['z1']) / 2, (SCR['y0'] + SCR['y1']) / 2
    for d, w_, o in ((0.16, 0.22, 0.0), (0.28, 0.14, 0.2)):
        fb.box(d, w_, SW + 2 * (o + w_), HW - d / 2, SCR['y1'] + o + w_ / 2, zc_)
        fb.box(d, w_, SW + 2 * (o + w_), HW - d / 2, SCR['y0'] - o - w_ / 2, zc_)
        fb.box(d, SH + 2 * o, w_, HW - d / 2, yc_, SCR['z0'] - o - w_ / 2)
        fb.box(d, SH + 2 * o, w_, HW - d / 2, yc_, SCR['z1'] + o + w_ / 2)
    fb.mesh(M['gold'], parent=room, flags={'noSupportCheck': True})

    class PostWall(dict):
        def set_text(self, s, **o):
            return set_text(s, **o)
        setText = set_text

        @property
        def texture(self):
            return post_vars.items[post_state['variant']]['color']

        @property
        def canvas(self):
            """The shown post's canvas, drawn in full (the LED wall's shader types it: post_n characters)."""
            return post_meta[post_state['variant']][2]
    C.parts['postWall'] = PostWall(mesh=screen, variants=post_vars, state=post_state)

    # ------------------------------------------------------------------- the poll board beside the door
    poll_opts = {'title': 'WHAT SHALL WE CALL IT?', 'sub': 'OFFICIAL POLL  ·  ONE VOTE PER PERSON',
                 'names': ['SUPERIOR INTELLIGENCE', 'EXTREME INTELLIGENCE', 'SUPREME INTELLIGENCE'],
                 'footnote': 'THE ONE BEING NAMED MAY NOT VOTE', 'stamp': 'LOSING BADLY'}
    poll_vars = ImageVariants(L, 'corridor_poll', 'poll_variant')
    tally_now = [list(opts.get('tally', [588214, 471902, 144215]))]

    def set_tally(a, b, c, ctx=None, frame=None, **o):
        """setTally(superior, extreme, supreme, {title, sub, names, footnote, stamp}): repaint the board (keyed
        CONSTANT inside update)."""
        tally = [max(0, _js_round(v or 0)) for v in (a, b, c)]
        poll_opts.update({k: v for k, v in o.items() if k in ('title', 'sub', 'names', 'footnote', 'stamp')})
        sig = (tuple(tally), tuple(sorted((k, str(v)) for k, v in poll_opts.items())))
        pix = _draw_poll(tally, poll_opts, fam)
        vi = poll_vars.add({'board': L.data_tex(pix, srgb=True, name=f'corridor_poll_{len(poll_vars.items)}')}, sig=sig)
        tally_now[0] = tally
        C.set_u('poll_variant', vi, ctx=ctx, frame=frame, interpolation='CONSTANT')
        return vi
    set_tally(*tally_now[0])

    def poll_mat():
        Mt = L.mat('corridor_poll')
        nb = Mt.nb
        u0 = nb.uv()
        s_rgb, leaf = poll_vars.sample(nb, 'board', u0)
        tuv = u0 * (2.4 / 0.8, 3.41 / 0.8, 1.0)
        lr, _ = nb.tex(S['lacq']['rgh'], tuv)
        gr, _ = nb.tex(S['goldF']['rgh'], tuv)
        ln, _ = nb.tex(S['lacq']['nrm'], tuv)
        pool = nb.exp((1.0 - u0.y) * -2.2) * (1.0 - nb.abs(u0.x - 0.5) * 0.9)          # its brass picture light
        em = s_rgb * pool * nb.mix(0.3, 0.55, leaf) * (1.0, 0.85, 0.62) * nb.U('lights')
        return Mt.standard(s_rgb, rough=nb.clamp(nb.mix(lr.x * 0.25 + 0.12, gr.x * 0.3 + 0.12, leaf), 0.05, 1),
                           metal=leaf, normal=nb.normal_map(ln, 0.25), emissive=em, ibl=L.ibl(1.0))
    M['poll'] = poll_mat()
    poll = L.empty('corridor_poll', parent=room,
                   M3=m4(POLL_AT[0], 0, POLL_AT[1], 0, math.atan2(0 - POLL_AT[0], 6 - POLL_AT[1]) + 0.18, 0))
    L.mesh_object('poll_board', plane_geometry(2.4, 3.41), M['poll'], parent=poll, M3=m4(0, 0.72 + 1.705, 0.05),
                  flags={'assembly': 'corridor_poll'})
    pb = L.bucket('poll_frame')
    pb.box(2.54, 3.55, 0.06, 0, 0.72 + 1.705, 0)                     # the lacquered panel's gilded edge
    pb.box(0.08, 2.6, 0.08, -0.98, 1.3, -0.07)                        # legs
    pb.box(0.08, 2.6, 0.08, 0.98, 1.3, -0.07)
    pb.box(0.08, 3.0, 0.08, 0, 1.35, -0.78, rx=-0.28)                # the easel's back leg
    pb.box(2.2, 0.06, 0.1, 0, 0.7, 0.0)                               # the ledge
    pb.box(1.5, 0.05, 0.14, 0, 4.24, 0.1)                             # the picture light's arm + hood
    pb.box(1.4, 0.09, 0.05, 0, 4.2, 0.2, rx=0.5)
    pb.mesh(M['goldTrim'], parent=poll, flags={'assembly': 'corridor_poll'})
    L.mesh_object('poll_back', box_geometry(2.48, 3.48, 0.04), M['ceiling'], parent=poll,
                  M3=m4(0, 0.72 + 1.705, 0.012), flags={'assembly': 'corridor_poll'})
    L.mesh_object('poll_lamp', box_geometry(1.36, 0.025, 0.03), M['glass'], parent=poll, M3=m4(0, 4.15, 0.22),
                  shadow=False, flags={'assembly': 'corridor_poll'})

    class Poll(dict):
        def set_tally(self, a, b, c, **o):
            return set_tally(a, b, c, **o)
        setTally = set_tally

        @property
        def tally(self):
            return list(tally_now[0])
    C.parts['poll'] = Poll(group=poll, variants=poll_vars, options=poll_opts)

    # ------------------------------------------------------- the AI FORCE mission patch (original; embroidered)
    patch_tex = _patch_textures(L, fam)

    def patch_mat(wall):
        Mt = L.mat('corridor_patch' if wall else 'uniform_patch')
        nb = Mt.nb
        s_rgb, s_a = nb.tex(patch_tex['col'], nb.uv())
        pn, _ = nb.tex(patch_tex['nrm'], nb.uv())
        gl = nb.ss(0.3, 0.9, s_a)
        em = None
        if wall:
            # disc-local coordinates -> the corridor's (the disc faces +x on the -x wall: local x -> -z, y -> up)
            qd = (nb.uv() - 0.5) * (2 * PATCH['r'])
            em = s_rgb * fan(nb, PATCH['z'] - qd.x, qd.y + PATCH['y'], -1.0) * WARM * 0.35 * nb.U('lights')
        # alphaTest 0.5 on step(0.002, a): a binary cut-out (EEVEE's dithered path draws it exactly)
        return Mt.standard(s_rgb, rough=nb.mix(0.78, 0.32, gl), metal=gl * 0.9, normal=nb.normal_map(pn, 1.0),
                           emissive=em, alpha=nb.step(0.5, nb.step(0.002, s_a)), side='front', ibl=L.ibl(0.8))
    M['patch'] = patch_mat(True)
    M['patchSmall'] = patch_mat(False)
    patch = L.empty('corridor_patch', parent=room, M3=m4(-HW + 0.09, PATCH['y'], PATCH['z'], 0, math.pi / 2, 0))
    CL.set_flags(patch, {'noSupportCheck': True})
    L.mesh_object('patch_back', _rot_x(cylinder_geometry(PATCH['r'] + 0.06, PATCH['r'] + 0.06, 0.04, 64), math.pi / 2,
                                       (0, 0, -0.03)), M['ceiling'], parent=patch, flags={'assembly': 'corridor_patch'})
    L.mesh_object('patch_ring', torus_geometry(PATCH['r'] + 0.03, 0.045, 10, 96), M['gold'], parent=patch,
                  M3=m4(0, 0, -0.01), flags={'assembly': 'corridor_patch'})
    L.mesh_object('patch_cloth', circle_geometry(PATCH['r'], 96), M['patch'], parent=patch,
                  flags={'assembly': 'corridor_patch'})
    C.parts['patch'] = patch

    # ------------------------------------------------------------------------- the uniform on a tailor's stand
    M['wool'] = L.pbr_mat(S['twill'], name='uniform_wool', tile=0.18, nrm=1.0, rough=(0.4, 0.55), physical=True,
                          sheen=0.6, sheen_roughness=0.5, sheen_color=0x1a2440,
                          recolor=lambda c, nb: nb.w((0.03, 0.038, 0.07)) * (nb.lum(c) * 2.0 + 0.45), env_i=L.env_i(0.45))
    M['sash'] = L.pbr_mat(S['pile'], name='uniform_sash', tile=0.2, physical=True, sheen=0.8, sheen_roughness=0.4,
                          sheen_color=0x8a1822, recolor=lambda c, nb: nb.w((0.42, 0.03, 0.04)) * (nb.lum(c) * 2.0 + 0.3),
                          rough=(0.5, 0.35), env_i=L.env_i(0.5))
    M['leather'] = L.pbr_mat(S['lacq'], name='uniform_leather', tile=0.4,
                             recolor=lambda c, nb: nb.w((0.012, 0.01, 0.009)) * (nb.lum(c) * 1.5 + 0.6), rough=(0.3, 0.12),
                             env_i=L.env_i(0.9))
    M['wood'] = L.pbr_mat(S['wood'], name='stand_wood', tile=0.6, tint=[0.45, 0.3, 0.22], rough=(0.8, 0.1),
                          env_i=L.env_i(0.5))
    uniform_ = L.empty('corridor_uniform', parent=room,
                       M3=m4(UNIFORM_AT[0], 0, UNIFORM_AT[1], 0, math.atan2(0 - UNIFORM_AT[0], 6 - UNIFORM_AT[1]), 0))
    _build_uniform(L, M, uniform_)
    C.parts['uniform'] = uniform_

    # ----------------------------------------------------- the pedestal, the velvet cushion and the peaked cap
    M['velvet'] = L.pbr_mat(S['pile'], name='cushion_velvet', tile=0.12, physical=True, sheen=1.0, sheen_roughness=0.35,
                            sheen_color=0xa0242c, rough=(0.5, 0.4),
                            recolor=lambda c, nb: nb.w((0.3, 0.018, 0.026)) * (nb.lum(c) * 2.0 + 0.25), env_i=L.env_i(0.4))
    M['patent'] = L.pbr_mat(S['lacq'], name='cap_patent', tile=0.3, physical=True, clearcoat=1.0,
                            clearcoat_roughness=0.06, side='double', recolor=lambda c, nb: nb.w((0.006, 0.006, 0.007)),
                            rough=(0.2, 0.08), nrm=0.15, env_i=L.env_i(1.2))
    braid_cv = CL.create_canvas(128, 32)
    bg2 = braid_cv.get_context('2d')
    for x in range(-32, 160, 8):
        bg2.stroke_style = '#fff'
        bg2.line_width = 3
        bg2.begin_path()
        bg2.move_to(x, 0)
        bg2.line_to(x + 16, 32)
        bg2.stroke()
    braid_n = L.normal_tex(CL.height_field(braid_cv, blur=1), 3, wrap=CL.REPEAT, name='cap_braid_nrm')

    def braid_post(d):
        nb = d['nb']
        bn, _ = nb.tex(braid_n, nb.uv() * (24.0, 1.0, 1.0))
        return {'normal': nb.normal_map(bn, 1.2)}
    M['braid'] = L.pbr_mat(S['goldF'], name='cap_braid', tile=0.15, metal=1, rough=(0.4, 0.15), tint=[1.0, 0.82, 0.5],
                           post=braid_post, env_i=L.env_i(1.1))

    pedestal = L.empty('corridor_pedestal', parent=room, M3=m4(CAP_AT[0], 0, CAP_AT[1], 0, 0.35, 0))
    # the marble material reads the book-matched slab uv (UVBook): the pedestal's box carries its own, as the walls do
    # (without it the texture sampled one texel and the pedestal came out a flat beige block)
    L.mesh_object('pedestal_marble', _book_match(L.bucket('pedestal_marble').box(0.46, 0.8, 0.46, 0, 0.52, 0).geometry()),
                  M['marble'], parent=pedestal)
    (L.bucket('pedestal_gold').box(0.62, 0.12, 0.62, 0, 0.06, 0).box(0.54, 0.05, 0.54, 0, 0.145, 0)
     .box(0.56, 0.06, 0.56, 0, 0.95, 0).box(0.5, 0.025, 0.5, 0, 0.91, 0).mesh(M['gold'], parent=pedestal))
    C.parts['pedestal'] = pedestal
    cushion = L.empty('corridor_cushion', parent=room, M3=m4(CAP_AT[0], 0.98, CAP_AT[1], 0, 0.35, 0))
    _build_cushion(L, M, cushion)
    C.parts['cushion'] = cushion

    cap = L.empty('corridor_cap', parent=root)
    cap.rotation_mode = 'QUATERNION'
    _build_cap(L, M, cap, S)
    cap_rest = L.empty('corridor_cap_rest', parent=room, M3=m4(CAP_AT[0], 0.98 + 0.108, CAP_AT[1], -0.02, 0.35 + 0.5, 0))
    cap.matrix_basis = cap_rest.matrix_basis.copy()
    cap_fit = {'pos': list(opts.get('capFitPos', [0, 0.13, 0.095])), 'rot': list(opts.get('capFitRot', [-0.1, 0, 0])),
               'scale': float(opts.get('capFitScale', 1.0))}
    C.parts.update(cap=cap, capRest=cap_rest, capFit=cap_fit)

    # ------------------------------------------------------------------------------------------------ lights
    lights = L.empty('corridor_lights', parent=root)
    W_ = {}

    def spot_(key, col_, I, pos, tgt, angle, pen, shadow=True):
        W_[key] = CL.spot(L, f'corridor_{key}', col_, I, pos, tgt, angle, pen, parent=lights, shadow=shadow and shadows)
        return W_[key]
    spot_('key', 0xffd6a0, 300, [1.2, 9.2, 8.0], [0, 1.25, 0], 0.3, 0.8)
    # raking floor uplights on the door (their mirror images fall upward, away from the corridor's cameras)
    spot_('doorL', 0xffc06e, 170, [-2.3, 0.12, ZD + 2.6], [-0.9, 6.5, ZD], 0.42, 0.6)
    spot_('doorR', 0xffc06e, 170, [2.3, 0.12, ZD + 2.6], [0.9, 6.5, ZD], 0.42, 0.6)
    # a picture light raking down the plaque from under the crown
    spot_('plaque', 0xffdcaa, 40, [0, 10.75, ZD + 1.35], [0, 8.6, ZD], 0.62, 0.5)
    spot_('beyond', 0xffe9c8, 0, [0, 4.2, ZD - 2.5], [0, 0.6, 6], 0.3, 0.6)
    spot_('poll', 0xffdcaa, 110, [POLL_AT[0] + 1.8, 7.4, POLL_AT[1] + 4.2], [POLL_AT[0], 2.4, POLL_AT[1]], 0.36, 0.6)
    spot_('cap', 0xffe2b8, 30, [CAP_AT[0] + 0.7, 4.4, CAP_AT[1] + 1.4], [CAP_AT[0], 1.05, CAP_AT[1]], 0.22, 0.7)
    spot_('uniform', 0xffd8a8, 150, [UNIFORM_AT[0] + 2.0, 5.6, UNIFORM_AT[1] + 2.4], [UNIFORM_AT[0], 1.2, UNIFORM_AT[1]],
          0.26, 0.7)
    # the LED wall's glow and the fill sit where geometry glows round them (the fill is inside a lantern): no shadow
    W_['screen'] = CL.point(L, 'corridor_screen', 0xc8dcff, 14, [HW - 1.4, 4.4, -10.0], parent=lights, shadow=False)
    W_['fill'] = CL.point(L, 'corridor_fill', 0xffb070, 9, [0, 8.2, -4.0], parent=lights, shadow=False)
    W_['hemi'] = {'sky': 0x3a2a1a, 'ground': 0x0a0405, 'intensity': 0.06, 'world': getattr(C, 'world', None)}
    W_['beyond'].data.energy = 0.0
    W_['beyond']['three_cd_open'] = 1500.0
    C.parts['lights'] = W_
    C.parts.update(doors={'group': doors, 'left': pivotL, 'right': pivotR, 'leafL': leafL, 'leafR': leafR, 'seam': seam},
                   plaque=plaque_ob, beyond=beyond, shafts=shafts, sconces=sconce_glass, marble=m_marble)
    C.parts['uniforms'] = root
    C.parts['materials'] = M
    # the corridor's volume probe (look.lighting.add_room_probe: its outermost samples inside the 0.4 m shell, the
    # door's opening onto the room beyond), parented to the set: C.bake_probes() bakes it
    if opts.get('probe', True):
        from ...look import lighting as LL
        a, b = CL.b3((-HW, 0.0, ZN)), CL.b3((HW, HC, ZD))
        pr = LL.add_room_probe(sc, f'{name}:probe', tuple(min(p, q) for p, q in zip(a, b)),
                               tuple(max(p, q) for p, q in zip(a, b)), wall=SLAB,
                               spacing=float(opts.get('probe_spacing', 0.6)),
                               samples=int(opts.get('probe_samples', 1024)), collection=col)
        pr.parent = root
        pr.matrix_parent_inverse = Matrix.Identity(4)
        L.own(pr.data)
        L.own(pr)
        C.parts['probe'] = pr

    # --------------------------------------------------------------------------------------------- per frame
    last = {'post': None, 'tally': None}

    def update(t, st=None, ctx=None, frame=None):
        """update(t, state): state keys open, beyond, gap, postText, post, screen, tally, capOn, capHead, lights (see
        CORRIDOR_NEWS.md), plus camera (for the pixel footprint the LED wall's moire guard reads). Keys every value it
        sets when ctx or frame is given."""
        st = dict(st or {})
        kw = {'ctx': ctx, 'frame': frame}
        C.set_u('t', t, **kw)
        open_ = _ease(st.get('open', 0.0))
        C.set_u('open', open_, **kw)
        C.set_u('beyond', st.get('beyond', 1.0), **kw)
        C.set_u('gap', st.get('gap', 1.0), **kw)
        C.set_u('screen', st.get('screen', 1.0), **kw)
        lvl = st.get('lights', 1.0)
        C.set_u('lights', lvl, **kw)
        C.set_u('flick', 1 + 0.025 * math.sin(t * 2.3) + 0.015 * math.sin(t * 5.7 + 1.3), **kw)   # the lanterns' breath
        cam = st.get('camera')
        if cam is not None or 'pix' in st:
            C.set_u('pix', st.get('pix') or CL.pix_of(bpy.context.scene, cam), **kw)
        ang = open_ * 1.62
        pivotL.rotation_euler = (0.0, 0.0, ang)
        pivotR.rotation_euler = (0.0, 0.0, -ang)
        C.keyer(pivotL, 'rotation_euler', **kw)
        C.keyer(pivotR, 'rotation_euler', **kw)
        for k in ('key', 'doorL', 'doorR', 'plaque', 'poll', 'cap', 'uniform', 'screen', 'fill'):
            e = W_[k]['base'] * lvl
            if k == 'screen':
                e *= st.get('screen', 1.0)
            C.key_light(W_[k], e, **kw)
        C.key_light(W_['beyond'], CL.cd_watts(1500 * open_ * st.get('beyond', 1.0)), **kw)
        shafts.hide_render = not (open_ > 0.002)
        C.keyer(shafts, 'hide_render', interpolation='CONSTANT', **kw)
        if st.get('postText') is not None and st['postText'] != last['post']:
            last['post'] = st['postText']
            set_text(st['postText'], **kw)
        if st.get('post') is not None:
            k_ = max(0.0, min(1.0, float(st['post'])))
            n_ = _js_round(len(post_state['text']) * k_)
            post_state['shown'], post_state['reveal'] = n_, k_
            C.set_u('post_n', n_, interpolation='CONSTANT', **kw)
            C.set_u('post_cursor', 1.0 if k_ < 1 else 0.0, interpolation='CONSTANT', **kw)
        if st.get('tally') and str(list(st['tally'])) != last['tally']:
            last['tally'] = str(list(st['tally']))
            set_tally(*st['tally'], **kw)
        if ctx is not None or frame is not None:
            # the shown post and board keyed on every keyed frame: a later repost's first key would otherwise
            # hold back to the start (an F-curve extrapolates its first key) and show the new post too early
            C.set_u('post_variant', post_state['variant'], interpolation='CONSTANT', **kw)
            C.set_u('poll_variant', C.group['poll_variant'], interpolation='CONSTANT', **kw)
        # the cap: cushion -> head along an arc (capOn 0..1, capHead: the normalized head bone, see _cap_head)
        on = _ease(st.get('capOn', 0.0))
        head = st.get('capHead')
        rest_w = _world_of(cap_rest)
        if head is not None and on > 0:
            Hm = _cap_head_matrix(head)
            fit = Matrix(CL.to_blender_matrix(m4(*cap_fit['pos'], *cap_fit['rot'], cap_fit['scale'])).tolist())
            Mb = Hm @ fit
            pa, qa, sa = rest_w.decompose()
            pb_, qb, sb = Mb.decompose()
            p = pa.lerp(pb_, on)
            p.z += math.sin(on * math.pi) * 0.45                     # three's +y: Blender's +z
            q_ = qa.slerp(qb, on)
            s_ = sa.lerp(sb, on)
            Mw = Matrix.LocRotScale(p, q_, s_)
            ml = _world_of(root).inverted() @ Mw
            loc, rot, scl = ml.decompose()
        else:
            loc, rot, scl = (_world_of(root).inverted() @ rest_w).decompose()
            scl = Vector((1.0, 1.0, 1.0))
        cap.location, cap.rotation_quaternion, cap.scale = loc, rot, scl
        C.key_transform(cap, **kw)

    C.update = update
    C.parts['postWall']['update'] = update
    update(0.0, {})
    return C


# ======================================================================================= pieces of the build =====

def _world_of(ob):
    """An object's world matrix from its parent chain's local matrices (valid without a depsgraph update)."""
    from mathutils import Matrix
    M = Matrix.Identity(4)
    chain = []
    o = ob
    while o is not None:
        chain.append(o)
        o = o.parent
    for o in reversed(chain):
        M = M @ (o.matrix_parent_inverse if o.parent is not None else Matrix.Identity(4)) @ o.matrix_basis
    return M


def _cap_head_matrix(head):
    """capHead: an (armature, bone name) pair (the bone's normalized frame, as three-vrm's), a Matrix, or an object
    (its world matrix)."""
    from mathutils import Matrix
    if isinstance(head, (tuple, list)) and len(head) == 2 and hasattr(head[0], 'pose'):
        return CL.normalized_bone_matrix(head[0], head[1])
    if isinstance(head, Matrix):
        return head
    return head.matrix_world.copy()


def _inside_out(g: Geo) -> Geo:
    """three's BackSide: the triangles' winding and normals reversed, so the inside is the front."""
    q = g.non_indexed()
    P = q.pos.reshape(-1, 3, 3)[:, ::-1].reshape(-1, 3)
    Nn = -q.nrm.reshape(-1, 3, 3)[:, ::-1].reshape(-1, 3)
    UV = q.uv.reshape(-1, 3, 2)[:, ::-1].reshape(-1, 2)
    return Geo(P, Nn, UV)


def _rot_x(g: Geo, a, t=(0.0, 0.0, 0.0)) -> Geo:
    """A mesh whose rotation.x and position were set (baked in)."""
    return g.copy().apply(m4(t[0], t[1], t[2], a, 0, 0))


def _book_match(g: Geo) -> Geo:
    """The marble walls' book-matched slabs: cut at every 2.4 m of the box uv's u (the slab edges and the mirror
    lines), then UVBook = (|fract(u / 4.8) x 2 - 1| x 0.85, v / 2.4 + hash21(pair, 3) x 5) per vertex."""
    u_all = g.uv[:, 0]
    k0, k1 = math.floor(u_all.min() / 2.4) - 1, math.ceil(u_all.max() / 2.4) + 1
    q = CL.slice_tris(g, lambda gg: gg.uv[:, 0], [k * 2.4 for k in range(k0, k1 + 1)])
    uv = q.uv.reshape(-1, 3, 2)
    w = uv[..., 0] / 2.4 * 0.5                                    # uu * 0.5
    wc = w.mean(1)
    pair = np.floor(wc)
    fr = w - pair[:, None]
    sgn = np.where((wc - pair) * 2 - 1 >= 0, 1.0, -1.0)
    bu = sgn[:, None] * (fr * 2 - 1)
    h = CL.hash21_np(pair, np.full_like(pair, 3.0)).astype(np.float64)
    tv = uv[..., 1] / 2.4 + h[:, None] * 5.0
    q.attrs['UVBook'] = np.stack([bu * 0.85, tv], -1).reshape(-1, 2)
    return q


def _tile_uv(g: Geo) -> Geo:
    """The floor's diagonal 1.6 m slabs: cut along both diagonal families (q = ((x + z), (z - x)) x 0.7071 / 1.6 at
    every integer), then UVTile = fract(q) x 0.62 + (hash21(cell), hash21(cell + 17.31)) x 4 per vertex."""
    k = 0.70710678 / 1.6

    def qx(gg):
        return (gg.pos[:, 0] + gg.pos[:, 2]) * k

    def qy(gg):
        return (gg.pos[:, 2] - gg.pos[:, 0]) * k
    a, b = qx(g), qy(g)
    q = CL.slice_tris(g, qx, range(int(math.floor(a.min())) - 1, int(math.ceil(a.max())) + 2))
    q = CL.slice_tris(q, qy, range(int(math.floor(b.min())) - 1, int(math.ceil(b.max())) + 2))
    QX, QY = qx(q).reshape(-1, 3), qy(q).reshape(-1, 3)
    cx, cy = np.floor(QX.mean(1)), np.floor(QY.mean(1))
    fx, fy = QX - cx[:, None], QY - cy[:, None]
    hx = CL.hash21_np(cx, cy).astype(np.float64)
    hy = CL.hash21_np(cx + 17.31, cy + 17.31).astype(np.float64)
    q.attrs['UVTile'] = np.stack([fx * 0.62 + hx[:, None] * 4.0, fy * 0.62 + hy[:, None] * 4.0], -1).reshape(-1, 2)
    return q


def _door_relief(L):
    """One leaf (the left; the right mirrors it): 3.2 x 8.0 m at 200 px/m; canvas x = 640 is the meeting stile."""
    W, H = 640, 1600
    cv = CL.create_canvas(W, H)
    g = cv.get_context('2d')
    g.fill_style = _gray(0.42)
    g.fill_rect(0, 0, W, H)
    g.stroke_style = _gray(0.85); g.line_width = 32; g.stroke_rect(16, 16, W - 32, H - 32)
    g.stroke_style = _gray(0.66); g.line_width = 7; g.stroke_rect(46, 46, W - 92, H - 92)
    # kick plate with grooves
    g.fill_style = _gray(0.72); g.fill_rect(56, H - 140, W - 112, 84)
    g.fill_style = _gray(0.58)
    for y in range(H - 128, H - 60, 16):
        g.fill_rect(64, y, W - 128, 4)
    # the sunburst: rays fan out from the stile at 2.7 m (Balla's sun, split between the two leaves)
    cx, cy = W, H - 540
    N = 11
    for i in range(N):
        a0 = math.pi / 2 + i * math.pi / N
        a1 = a0 + math.pi / N
        r1 = 470 if i % 2 else 575
        g.begin_path()
        g.move_to(cx + math.cos(a0) * 120, cy - math.sin(a0) * 120)
        g.line_to(cx + math.cos(a0) * r1, cy - math.sin(a0) * r1)
        g.line_to(cx + math.cos((a0 + a1) / 2) * (r1 + 30), cy - math.sin((a0 + a1) / 2) * (r1 + 30))
        g.line_to(cx + math.cos(a1) * r1, cy - math.sin(a1) * r1)
        g.line_to(cx + math.cos(a1) * 120, cy - math.sin(a1) * 120)
        g.close_path()
        g.fill_style = _gray(0.56 if i % 2 else 0.8)
        g.fill()
        g.stroke_style = _gray(0.3)
        g.line_width = 5
        g.stroke()
    g.begin_path(); g.arc(cx, cy, 112, math.pi / 2, math.pi * 1.5); g.fill_style = _gray(0.97); g.fill()
    g.begin_path(); g.arc(cx, cy, 84, math.pi / 2, math.pi * 1.5); g.stroke_style = _gray(0.68); g.line_width = 9; g.stroke()
    g.begin_path(); g.arc(cx, cy, 52, math.pi / 2, math.pi * 1.5); g.fill_style = _gray(1.0); g.fill()
    # a raised rail at 5.2 m and the stepped ziggurat above it (mirrored across the stile into one figure)
    g.fill_style = _gray(0.8)
    g.fill_rect(56, H - 1060, W - 112, 22)
    steps = [[560, 0.6], [450, 0.68], [340, 0.76], [230, 0.84], [120, 0.92]]
    yb = H - 1080
    for i, (w, lv) in enumerate(steps):
        hh = 70 + i * 6
        g.fill_style = _gray(lv)
        g.fill_rect(W - w, yb - hh, w, hh)
        yb -= hh
    g.fill_style = _gray(0.95)
    g.fill_rect(W - 40, yb - 200, 40, 200)                         # the central spire
    for i in range(6):
        g.fill_style = _gray(0.7)
        g.fill_rect(W - 120 - i * 70, yb - 150 + i * 22, 14, 150 - i * 22)
    # fluting down the hinge side
    for i in range(4):
        x0 = 74 + i * 24
        gr = g.create_linear_gradient(x0, 0, x0 + 20, 0)
        gr.add_color_stop(0, _gray(0.62)); gr.add_color_stop(0.5, _gray(0.3)); gr.add_color_stop(1, _gray(0.62))
        g.fill_style = gr
        g.fill_rect(x0, 600, 20, H - 760)
    # the pull's rosette
    g.begin_path(); g.arc(W - 62, H - 250, 42, 0, math.pi * 2); g.fill_style = _gray(0.95); g.fill()
    g.begin_path(); g.arc(W - 62, H - 250, 26, 0, math.pi * 2); g.fill_style = _gray(0.7); g.fill()
    hf = CL.height_field(cv, blur=3)
    wide = CL.box_blur(hf['h'], W, H, 14, 2)
    cav = np.clip((wide - hf['h']) * 4.5, 0, 1).astype(np.float32)
    return {'nrm': L.normal_tex(hf, 14, name='corridor_door_nrm'),
            'mask': L.pack_tex([hf['h'], cav, None, None], W, H, name='corridor_door_mask'), 'canvas': cv}


def _door_mat(L, S, rel, mirror):
    Mt = L.mat('corridor_door_' + ('r' if mirror else 'l'))
    nb = Mt.nb
    u0 = nb.uv()
    ruv = nb.vec2(1.0 - u0.x if mirror else u0.x, u0.y)
    tuv = nb.vec2(u0.x * 3.2, u0.y * 8.0) / 1.3
    mk, _ = nb.tex(rel['mask'], ruv)
    h, cav = mk.x, mk.y
    gI, _ = nb.tex(S['goldI']['col'], tuv)
    gB, _ = nb.tex(S['bronze']['col'], tuv)
    gI, gB = gI * (1.0, 0.84, 0.58), gB * (0.5, 0.36, 0.22)
    dark = nb.clamp(cav * 1.5 + nb.max(0.5 - h, 0.0) * 0.8, 0, 1)
    gr, _ = nb.tex(S['goldI']['rgh'], tuv)
    nt, _ = nb.tex(rel['nrm'], ruv)
    return Mt.standard(nb.mix(gI, gB, dark), rough=nb.clamp(gr.x * 0.45 + 0.22 + dark * 0.3 - h * 0.06, 0.12, 1),
                       metal=nb.mix(1.0, 0.75, dark), normal=nb.normal_map(nt, 1.0, flip_x=mirror), ibl=L.ibl(0.7))


def _plaque_relief(L, lines=('SUPREME', 'INTELLIGENCE')):
    """The plaque: engraved, black-enamel-filled letters in a polished gold transom, 6.4 x 1.7 m. lines: the two
    lines engraved (opts plaque), each fitted to its own line of the transom."""
    W, H = 2048, 544
    cv = CL.create_canvas(W, H)
    g = cv.get_context('2d')
    mk = CL.create_canvas(W, H)
    gm = mk.get_context('2d')
    gm.fill_style = '#000'
    gm.fill_rect(0, 0, W, H)
    g.fill_style = _gray(0.72)
    g.fill_rect(0, 0, W, H)
    g.stroke_style = _gray(1.0); g.line_width = 30; g.stroke_rect(15, 15, W - 30, H - 30)
    g.stroke_style = _gray(0.86); g.line_width = 7; g.stroke_rect(52, 52, W - 104, H - 104)
    for sx in (1, -1):                                             # Deco end ornaments: stepped bars
        x0 = 80 if sx > 0 else W - 80
        for i in range(4):
            hh, ww = 260 - i * 56, 26
            g.fill_style = _gray(0.95 - i * 0.05)
            g.fill_rect(x0 + sx * i * 40 - (ww if sx < 0 else 0), H / 2 - hh / 2, ww, hh)
    l1, l2 = (list(lines) + ['', ''])[:2]
    for txt, y, size, maxW in ((str(l1).upper(), 215, 175, 1380), (str(l2).upper(), 400, 132, 1520)):
        if not txt:
            continue
        g.fill_style = _gray(0.12)
        fit_text(g, txt, x=W / 2, y=y, max_w=maxW, max_h=size, family=CL.fam['michroma'], track=0.16)
        gm.fill_style = '#fff'
        fit_text(gm, txt, x=W / 2, y=y, max_w=maxW, max_h=size, family=CL.fam['michroma'], track=0.16)
    # a thin engraved rule between the lines, with a centre lozenge
    g.fill_style = _gray(0.3)
    g.fill_rect(520, 300, W - 1040, 6)
    g.save(); g.translate(W / 2, 303); g.rotate(math.pi / 4); g.fill_rect(-14, -14, 28, 28); g.restore()
    hf = CL.height_field(cv, blur=2)
    ink = CL.height_field(mk, blur=1)
    return {'nrm': L.normal_tex(hf, 10, name='corridor_plaque_nrm'),
            'mask': L.pack_tex([hf['h'], ink['h'], None, None], W, H, name='corridor_plaque_mask'), 'W': W, 'H': H,
            'canvas': cv, 'ink_canvas': mk}


def _plaque_mat(L, S, plaque):
    Mt = L.mat('corridor_plaque')
    nb = Mt.nb
    u0 = nb.uv()
    tuv = nb.vec2(u0.x * 6.4, u0.y * 1.7) / 0.9
    mk, _ = nb.tex(plaque['mask'], u0)
    ink = mk.y
    gold, _ = nb.tex(S['goldF']['col'], tuv)
    gr, _ = nb.tex(S['goldF']['rgh'], tuv)
    nt, _ = nb.tex(plaque['nrm'], u0)
    return Mt.standard(nb.mix(gold * (1.02, 0.86, 0.58), (0.012, 0.01, 0.009), ink),
                       rough=nb.clamp(nb.mix(gr.x * 0.35 + 0.24, 0.45, ink), 0.05, 1), metal=nb.mix(1.0, 0.0, ink),
                       normal=nb.normal_map(nt, 1.0), ibl=L.ibl(0.75))


# ------------------------------------------------------------------------------------------------ the post ---

def _round_rect(g, x, y, w, h, r):
    g.begin_path()
    g.move_to(x + r, y)
    g.line_to(x + w - r, y)
    g.quadratic_curve_to(x + w, y, x + w, y + r)
    g.line_to(x + w, y + h - r)
    g.quadratic_curve_to(x + w, y + h, x + w - r, y + h)
    g.line_to(x + r, y + h)
    g.quadratic_curve_to(x, y + h, x, y + h - r)
    g.line_to(x, y + r)
    g.quadratic_curve_to(x, y, x + r, y)
    g.close_path()


def _wrap(g, text, size, family, max_w):
    g.font = f'bold {size}px {family}'
    words = [w for w in text.split() if w]
    lines, cur = [], ''
    for w in words:
        try_l = cur + ' ' + w if cur else w
        if g.measure_text(try_l).width <= max_w or not cur:
            cur = try_l
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    widest = max([g.measure_text(ln).width for ln in lines] + [0])
    return lines, widest


def _layout_post(g, text, box, fam):
    lo, hi, best = 40.0, 300.0, {'size': 40.0, 'lines': [text]}
    for _ in range(18):
        size = (lo + hi) / 2
        lines, widest = _wrap(g, text, size, fam['exo'], box['w'])
        hgt = len(lines) * size * 1.04
        if widest <= box['w'] and hgt <= box['h']:
            best = {'size': size, 'lines': lines}
            lo = size
        else:
            hi = size
    return best


def _draw_post(g, W, H, ps, reveal, fam):
    """drawPost: the post card (a generic emblem avatar, the account's name, a check badge, the body in capitals,
    the action row). Returns the body's layout: box, size, lines and each line's baseline y."""
    g.fill_style = '#030408'
    g.fill_rect(0, 0, W, H)
    cx, cy, cw, ch = W * 0.055, H * 0.06, W * 0.89, H * 0.88
    _round_rect(g, cx, cy, cw, ch, 30)
    g.fill_style = '#090c12'
    g.fill()
    g.line_width = 5
    g.stroke_style = '#222a39'
    g.stroke()
    # header: a generic emblem avatar (three gold Deco chevrons in a ring, no seal), the name, a check badge, the meta
    ar = H * 0.072
    ax, ay = cx + 60 + ar, cy + 50 + ar
    g.begin_path(); g.arc(ax, ay, ar, 0, math.pi * 2); g.fill_style = '#05070b'; g.fill()
    g.line_width = ar * 0.12; g.stroke_style = '#c9973a'; g.stroke()
    g.fill_style = '#d9a845'
    for i in range(3):
        yy = ay + ar * 0.42 - i * ar * 0.38
        w2 = ar * 0.62 - i * ar * 0.08
        g.begin_path(); g.move_to(ax - w2, yy); g.line_to(ax, yy - ar * 0.3); g.line_to(ax + w2, yy)
        g.line_to(ax + w2, yy + ar * 0.14); g.line_to(ax, yy - ar * 0.16); g.line_to(ax - w2, yy + ar * 0.14)
        g.close_path(); g.fill()
    g.text_align = 'left'
    g.text_baseline = 'middle'
    g.fill_style = '#f3f5f9'
    g.font = f'bold {_js_round(H * 0.058)}px {fam["exo"]}'
    nx = ax + ar + 34
    g.fill_text(ps['name'], nx, ay - ar * 0.3)
    nw = g.measure_text(ps['name']).width
    bx, by = nx + nw + 26 + H * 0.024, ay - ar * 0.3
    g.begin_path(); g.arc(bx, by, H * 0.024, 0, math.pi * 2); g.fill_style = '#c9973a'; g.fill()
    g.stroke_style = '#05070b'; g.line_width = H * 0.008; g.begin_path()
    g.move_to(bx - H * 0.011, by); g.line_to(bx - H * 0.002, by + H * 0.009); g.line_to(bx + H * 0.013, by - H * 0.01)
    g.stroke()
    g.fill_style = '#7b8495'
    g.font = f'{_js_round(H * 0.04)}px {fam["exo"]}'
    g.fill_text(ps['meta'], nx, ay + ar * 0.48)
    g.fill_style = '#5b6372'
    for i in range(3):
        g.begin_path(); g.arc(cx + cw - 80 + i * 22, ay - ar * 0.3, 6, 0, math.pi * 2); g.fill()
    # the body: huge capitals, laid out once per text so typing never reflows
    box = {'x': cx + 64, 'y': ay + ar + 34, 'w': cw - 128, 'h': ch - (ay + ar + 34 - cy) - H * 0.15}
    if not ps.get('layout'):
        ps['layout'] = _layout_post(g, ps['text'], box, fam)
    size, lines = ps['layout']['size'], ps['layout']['lines']
    total = len(ps['text'])
    budget = _js_round(total * max(0.0, min(1.0, reveal)))
    g.font = f'bold {size}px {fam["exo"]}'
    g.fill_style = '#f6f7fb'
    g.text_baseline = 'alphabetic'
    block_h = len(lines) * size * 1.04
    yy = box['y'] + (box['h'] - block_h) / 2 + size * 0.86
    baselines = []
    y_ = yy
    for _ln in lines:
        baselines.append(y_)
        y_ += size * 1.04
    last_x, last_y = box['x'], yy
    for ln in lines:
        shown = ln[:max(0, budget)]
        budget -= len(ln) + 1
        if shown:
            g.fill_text(shown, box['x'], yy)
        last_x = box['x'] + g.measure_text(shown).width
        last_y = yy
        if budget < 0:
            break
        yy += size * 1.04
    if reveal < 1:
        g.fill_style = '#c9973a'
        g.fill_rect(last_x + size * 0.08, last_y - size * 0.78, size * 0.09, size * 0.86)
    # the action row: reply, repost, like, views (generic glyphs) + counts
    ry = cy + ch - H * 0.075
    g.stroke_style = '#6d7586'; g.fill_style = '#6d7586'; g.line_width = 5
    g.font = f'{_js_round(H * 0.038)}px {fam["exo"]}'
    g.text_baseline = 'middle'

    def ic0(x):
        _round_rect(g, x - 22, ry - 18, 44, 32, 10); g.stroke()
        g.begin_path(); g.move_to(x - 8, ry + 14); g.line_to(x - 14, ry + 26); g.line_to(x + 2, ry + 14); g.stroke()

    def ic1(x):
        g.begin_path(); g.move_to(x - 24, ry - 4); g.line_to(x - 24, ry - 16); g.line_to(x + 14, ry - 16); g.stroke()
        g.begin_path(); g.move_to(x + 24, ry + 4); g.line_to(x + 24, ry + 16); g.line_to(x - 14, ry + 16); g.stroke()

    def ic2(x):
        g.begin_path(); g.move_to(x, ry + 20); g.bezier_curve_to(x - 40, ry - 6, x - 16, ry - 30, x, ry - 10)
        g.bezier_curve_to(x + 16, ry - 30, x + 40, ry - 6, x, ry + 20); g.stroke()

    def ic3(x):
        for i in range(3):
            g.fill_rect(x - 18 + i * 14, ry + 16 - (12 + i * 10), 9, 12 + i * 10)
    for i, ic in enumerate((ic0, ic1, ic2, ic3)):
        x = cx + 120 + i * (cw - 220) / 3.4
        ic(x)
        g.fill_text(ps['stats'][i] if i < len(ps['stats']) else '', x + 40, ry)
    return {'box': box, 'size': size, 'lines': lines, 'baselines': baselines}


def _post_index_map(W, H, ps, geo, fam):
    """Each body character's typing index (1-based, the JS budget's order: a line's characters, then one for the
    line break) over its band: the shader shows index <= n. 0 elsewhere (always shown)."""
    out = np.zeros((H, W, 4), np.uint8)
    out[..., 3] = 255
    cv = CL.create_canvas(4, 4)
    g = cv.get_context('2d')
    size = geo['size']
    g.font = f'bold {size}px {fam["exo"]}'
    off = 0
    for ln, base in zip(geo['lines'], geo['baselines']):
        y0 = int(max(0, math.floor(base - size * 1.0)))
        y1 = int(min(H, math.ceil(base + size * 0.3)))
        prev = geo['box']['x']
        for i in range(len(ln)):
            xr = geo['box']['x'] + g.measure_text(ln[:i + 1]).width
            xa, xb = int(max(0, math.floor(prev))), int(min(W, math.ceil(xr)))
            if i == 0:
                xa = int(max(0, math.floor(prev - size * 0.2)))
            if i == len(ln) - 1:
                xb = int(min(W, math.ceil(xr + size * 0.2)))
            out[y0:y1, xa:xb, 0] = min(255, off + i + 1)
            prev = xr
        off += len(ln) + 1
    return out


def _post_cursor_lut(ps, geo, fam, W, H):
    """For n = 0..255 shown characters: the cursor bar's x, y (canvas pixels), its width (and height = 0.86/0.09 x
    width), as the JS loop leaves lastX / lastY. One row of 256 float texels."""
    cv = CL.create_canvas(4, 4)
    g = cv.get_context('2d')
    size = geo['size']
    g.font = f'bold {size}px {fam["exo"]}'
    lut = np.zeros((1, 256, 4), np.float32)
    lines, box = geo['lines'], geo['box']
    for n in range(256):
        budget = n
        yy = geo['baselines'][0] if geo['baselines'] else box['y']
        last_x, last_y = box['x'], yy
        for j, ln in enumerate(lines):
            shown = ln[:max(0, budget)]
            budget -= len(ln) + 1
            last_x = box['x'] + g.measure_text(shown).width
            last_y = geo['baselines'][j]
            if budget < 0:
                break
        lut[0, n] = (last_x + size * 0.08, last_y - size * 0.78, size * 0.09, 1.0)
    return lut


# ------------------------------------------------------------------------------------------------ the poll ---

def _nice_unit(x):
    e = math.pow(10, math.floor(math.log10(max(1, x))))
    for k in (1, 2, 5, 10):
        if k * e >= x:
            return k * e
    return 10 * e


def _fmt_int(v):
    v = float(v)
    return f'{int(v):,}' if v.is_integer() else f'{v:,}'


def _draw_poll(tally, po, fam):
    """drawPoll: albedo in RGB, the gold-leaf mask (metalness) in A. RGBA8 rows top-down."""
    PW, PH = 1024, 1456
    A, Mk = CL.create_canvas(PW, PH), CL.create_canvas(PW, PH)
    g, gm = A.get_context('2d'), Mk.get_context('2d')
    g.fill_style = '#080605'; g.fill_rect(0, 0, PW, PH)
    gm.fill_style = '#000'; gm.fill_rect(0, 0, PW, PH)

    def both(fn):
        g.save(); gm.save()
        fn(g, '#cfa148')
        fn(gm, '#fff')
        g.restore(); gm.restore()

    def frame_(c, col):                                            # gold-leaf frame, stepped corners
        c.stroke_style = col; c.line_width = 12; c.stroke_rect(22, 22, PW - 44, PH - 44)
        c.line_width = 3; c.stroke_rect(44, 44, PW - 88, PH - 88)
        c.fill_style = col
        for x, y in ((44, 44), (PW - 44, 44), (44, PH - 44), (PW - 44, PH - 44)):
            c.fill_rect(x - 14, y - 14, 28, 28)
    both(frame_)

    def title(c, col):                                             # heavy type: it has to survive the brushwork
        c.fill_style = col
        fit_text(c, po['title'], x=PW / 2, y=120, max_w=880, max_h=80, family=fam['audiowide'], track=0.03)
    both(title)
    g.fill_style = '#ddd2b8'
    fit_text(g, po['sub'], x=PW / 2, y=196, max_w=800, max_h=42, family=fam['rajdhani'], track=0.1)

    def divider(c, col):                                           # the Deco divider: rules with a stepped lozenge
        c.fill_style = col
        c.fill_rect(84, 240, 370, 6); c.fill_rect(PW - 454, 240, 370, 6)
        c.save(); c.translate(PW / 2, 243); c.rotate(math.pi / 4); c.fill_rect(-18, -18, 36, 36); c.restore()
        c.fill_rect(PW / 2 - 76, 237, 32, 12); c.fill_rect(PW / 2 + 44, 237, 32, 12)
    both(divider)
    total = sum(tally) or 1
    mx = max(max(tally), 1)
    unit = _nice_unit(mx / 40)
    min_i = tally.index(min(tally))
    for i, v in enumerate(tally):
        y0 = 284 + i * 322

        def name_(c, col, i=i, y0=y0):
            c.fill_style = col
            fit_text(c, po['names'][i], x=76, y=y0 + 40, max_w=870, max_h=62, family=fam['audiowide'], align='left')
        both(name_)
        # tally marks: hand-painted groups of five
        marks = _js_round(v / unit)
        g.stroke_style = '#ece2c8'; g.line_cap = 'round'; g.line_width = 12
        r = CL.rng(17 + i * 101)
        for k in range(marks):
            grp, j = k // 5, k % 5
            gx, top, bot = 88 + grp * 104, y0 + 88, y0 + 188
            if gx > PW - 130:
                break
            if j < 4:
                x = gx + j * 19 + (r() - 0.5) * 3
                g.begin_path()
                xa = x + (r() - 0.5) * 5
                ya = top + r() * 6
                xb = x + (r() - 0.5) * 5
                yb = bot - r() * 6
                g.move_to(xa, ya); g.line_to(xb, yb); g.stroke()
            else:
                g.begin_path(); g.move_to(gx - 12, bot - 14); g.line_to(gx + 72, top + 12); g.stroke()
        bx, bw, by, bh = 80, 640, y0 + 212, 60                          # the bar
        g.fill_style = '#1d1813'
        g.fill_rect(bx, by, bw, bh)

        def bar(c, col, v=v, by=by):
            c.fill_style = col
            c.fill_rect(bx, by, bw * v / mx, bh)
        both(bar)
        pct = _js_round(100 * v / total)
        g.fill_style = '#f2e9d2'
        fit_text(g, f'{pct}%', x=PW - 76, y=by + bh / 2 + 2, max_w=230, max_h=104, family=fam['rajdhani'], align='right')
        if i == min_i and po.get('stamp') and v < 0.6 * mx:
            # a red rubber stamp across the losing row, distressed (the ink skips); it lifts the leaf's metalness
            def stamp(col):
                scv = CL.create_canvas(640, 190)
                sg = scv.get_context('2d')
                sg.translate(320, 95)
                sg.stroke_style = col; sg.line_width = 13; sg.stroke_rect(-298, -72, 596, 144)
                sg.fill_style = col
                fit_text(sg, po['stamp'], x=0, y=6, max_w=540, max_h=100, family=fam['blackops'])
                sg.global_composite_operation = 'destination-out'
                rr = CL.rng(99)
                for _k in range(1100):
                    ax_ = (rr() - 0.5) * 620
                    ay_ = (rr() - 0.5) * 160
                    rad = rr() * 3.6 + 0.5
                    sg.begin_path(); sg.arc(ax_, ay_, rad, 0, math.pi * 2); sg.fill()
                return scv
            for c, col in ((g, '#c0141f'), (gm, '#000')):
                c.save(); c.translate(PW * 0.6, y0 + 142); c.rotate(-0.16); c.draw_image(stamp(col), -320, -95); c.restore()
    g.fill_style = '#ddd2b8'
    fit_text(g, f'EACH MARK = {_fmt_int(unit)} VOTES   ·   VOTES CAST {_fmt_int(total)}', x=PW / 2, y=PH - 178,
             max_w=880, max_h=42, family=fam['rajdhani'], track=0.04)
    if po.get('footnote'):
        def foot(c, col):
            c.fill_style = col
            fit_text(c, po['footnote'], x=PW / 2, y=PH - 108, max_w=860, max_h=46, family=fam['rajdhani'], track=0.1)
        both(foot)
    a, m = A.pixels(), Mk.pixels()
    out = a.copy()
    out[..., 3] = m[..., 0]
    return out


# ----------------------------------------------------------------------------------------------- the patch ---

def _patch_textures(L, fam):
    """The AI FORCE mission patch (an original roundel): albedo (alpha: the cut-out and the gold-thread mask) and the
    stitch relief's normal map, at 1024 px."""
    W = 1024
    c = W / 2
    al, ht, an, mt = (CL.create_canvas(W, W) for _ in range(4))
    g, gh, ga, gm = (cv.get_context('2d') for cv in (al, ht, an, mt))
    for x, col in ((g, 'rgba(0,0,0,0)'), (gh, '#000'), (ga, '#000'), (gm, '#000')):
        x.fill_style = col
        x.fill_rect(0, 0, W, W)

    def disc(ctx, r, col):
        ctx.begin_path(); ctx.arc(c, c, r, 0, math.pi * 2); ctx.fill_style = col; ctx.fill()

    def ring(ctx, r0, r1, col):
        ctx.begin_path(); ctx.arc(c, c, r1, 0, math.pi * 2); ctx.arc(c, c, r0, 0, math.pi * 2, True)
        ctx.fill_style = col; ctx.fill()

    def code(k):                                     # 0..180 = a fixed angle (deg); 200 = tangential; 220 = radial
        return f'rgb({k},{k},{k})'
    # merrowed border (gold), the text band (oxblood), a thin gold ring, the night field (navy)
    ring(g, 470, 508, '#c8962f'); ring(gh, 470, 508, code(235)); ring(ga, 470, 508, code(220)); ring(gm, 470, 508, '#fff')
    ring(g, 350, 470, '#5e0b14'); ring(gh, 350, 470, code(120)); ring(ga, 350, 470, code(200))
    ring(g, 336, 352, '#d4a23c'); ring(gh, 336, 352, code(200)); ring(ga, 336, 352, code(200)); ring(gm, 336, 352, '#fff')
    fld = g.create_radial_gradient(c, c - 80, 40, c, c, 336)
    fld.add_color_stop(0, '#22468c'); fld.add_color_stop(1, '#0c1b44')
    disc(g, 336, fld); disc(gh, 336, code(90)); disc(ga, 336, code(35))
    r = CL.rng(5)                                                   # stars
    for _k in range(9):
        a = r() * math.pi * 2
        d = 120 + r() * 190
        x, y = c + math.cos(a) * d, c + math.sin(a) * d
        s = 6 + r() * 9
        for ctx, col in ((g, '#eef2ff'), (gh, code(150)), (ga, code(0))):
            ctx.begin_path(); ctx.move_to(x, y - s); ctx.line_to(x + s * 0.3, y - s * 0.3); ctx.line_to(x + s, y)
            ctx.line_to(x + s * 0.3, y + s * 0.3); ctx.line_to(x, y + s); ctx.line_to(x - s * 0.3, y + s * 0.3)
            ctx.line_to(x - s, y); ctx.line_to(x - s * 0.3, y - s * 0.3); ctx.close_path()
            ctx.fill_style = col; ctx.fill()

    def orbit(ctx, col, w, a0=0.0, a1=math.pi * 2):                # silver, an ellipse tilted on the diagonal
        ctx.save(); ctx.translate(c, c + 20); ctx.rotate(-0.42)
        ctx.begin_path(); ctx.ellipse(0, 0, 268, 92, 0, a0, a1); ctx.stroke_style = col; ctx.line_width = w; ctx.stroke()
        ctx.restore()
    orbit(g, '#c9d1dc', 16, math.pi, math.pi * 2); orbit(gh, code(185), 16, math.pi, math.pi * 2)
    orbit(ga, code(200), 16, math.pi, math.pi * 2)

    def chip(ctx, body, pin, die):                                  # the chip (gold): a die with pins
        ctx.save(); ctx.translate(c, c + 20); ctx.rotate(-0.42)
        ctx.fill_style = pin
        for k in range(-3, 4):
            ctx.fill_rect(k * 20 - 5, -96, 10, 22); ctx.fill_rect(k * 20 - 5, 74, 10, 22)
            ctx.fill_rect(-96, k * 20 - 5, 22, 10); ctx.fill_rect(74, k * 20 - 5, 22, 10)
        ctx.fill_style = body; ctx.fill_rect(-76, -76, 152, 152)
        ctx.fill_style = die; ctx.fill_rect(-46, -46, 92, 92)
        ctx.restore()
    chip(g, '#d19b32', '#b9c2cc', '#20160a'); chip(gh, code(170), code(140), code(130)); chip(ga, code(0), code(90), code(45))
    chip(gm, '#fff', '#000', '#000')
    g.save(); g.translate(c, c + 20); g.rotate(-0.42); g.stroke_style = '#d6a23a'; g.line_width = 5   # the die's traces
    for x0, y0, x1, y1 in ((-34, -30, 0, -30), (0, -30, 0, 10), (0, 10, 30, 10), (-30, 26, 12, 26), (12, 26, 12, 40),
                           (-20, -12, -20, 14)):
        g.begin_path(); g.move_to(x0, y0); g.line_to(x1, y1); g.stroke()
    g.restore()

    def rocket(ctx, body_c, fin_c, trail_c, w_trail):              # rising on the diagonal, a gold trail
        ctx.save(); ctx.translate(c + 110, c - 150); ctx.rotate(0.72)
        tg = ctx.create_linear_gradient(0, 40, 0, 360)
        if isinstance(trail_c, str):
            tg.add_color_stop(0, trail_c); tg.add_color_stop(1, trail_c)
        else:
            tg.add_color_stop(0, trail_c[0]); tg.add_color_stop(1, trail_c[1])
        ctx.fill_style = tg
        ctx.begin_path(); ctx.move_to(-w_trail, 60); ctx.line_to(w_trail, 60); ctx.line_to(4, 380); ctx.line_to(-4, 380)
        ctx.close_path(); ctx.fill()
        ctx.fill_style = fin_c
        ctx.begin_path(); ctx.move_to(-26, 20); ctx.line_to(-58, 76); ctx.line_to(-24, 62); ctx.close_path(); ctx.fill()
        ctx.begin_path(); ctx.move_to(26, 20); ctx.line_to(58, 76); ctx.line_to(24, 62); ctx.close_path(); ctx.fill()
        ctx.fill_style = body_c
        ctx.begin_path(); ctx.move_to(0, -120); ctx.bezier_curve_to(34, -80, 30, 10, 26, 64)
        ctx.line_to(-26, 64); ctx.bezier_curve_to(-30, 10, -34, -80, 0, -120); ctx.close_path(); ctx.fill()
        ctx.restore()
    rocket(g, '#eef0f4', '#b3121d', ['#ffcf5a', 'rgba(255,140,40,0)'], 24)
    rocket(gh, code(200), code(170), code(110), 24)
    rocket(ga, code(52), code(140), code(52), 24)
    rocket(gm, '#000', '#000', ['#fff', '#000'], 24)
    # the orbit's near half passes in front of the rocket
    orbit(g, '#c9d1dc', 16, 0, math.pi); orbit(gh, code(190), 16, 0, math.pi); orbit(ga, code(200), 16, 0, math.pi)
    orbit(gm, '#000', 16, 0, math.pi)

    def arc_text(ctx, text, rr, size, family, top, col, track=0.12):
        ctx.save(); ctx.font = f'{size}px {family}'; ctx.fill_style = col; ctx.text_align = 'center'
        ctx.text_baseline = 'middle'
        widths = [ctx.measure_text(ch).width + track * size for ch in text]
        total = sum(widths)
        a = (-math.pi / 2 if top else math.pi / 2) + (-1 if top else 1) * total / rr / 2
        for i, ch in enumerate(text):
            w = widths[i] / rr
            am = a + (1 if top else -1) * w / 2
            ctx.save(); ctx.translate(c + math.cos(am) * rr, c + math.sin(am) * rr)
            ctx.rotate(am + (math.pi / 2 if top else -math.pi / 2)); ctx.fill_text(ch, 0, 0); ctx.restore()
            a += (1 if top else -1) * w
        ctx.restore()
    for ctx, col in ((g, '#e1ad3f'), (gh, code(230)), (ga, code(90)), (gm, '#fff')):
        arc_text(ctx, 'AI FORCE', 410, 92, fam['blackops'], True, col, 0.18)
    for ctx, col in ((g, '#dfe3ea'), (gh, code(215)), (ga, code(90))):
        arc_text(ctx, 'SCIT LOCUM SUUM', 412, 46, fam['michroma'], False, col, 0.1)
    # stitch height: the region's elevation + satin ridges along each region's direction
    hp = ht.pixels()[..., 0].astype(np.float64)
    ap_ = an.pixels()[..., 0].astype(np.float64)
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float64)
    base = hp / 255.0
    k = ap_
    radial = np.arctan2(yy - c, xx - c)
    ang = np.where(k >= 210, radial, np.where(k >= 190, radial + math.pi / 2, k * math.pi / 180))
    per = 5.0
    sn = np.sin(((xx * np.cos(ang) + yy * np.sin(ang)) * 2 * math.pi) / per)
    h = np.where(base <= 0, 0.0, base * 0.75 + 0.12 * (0.5 + 0.5 * sn) * base).astype(np.float32)
    hb = {'h': CL.box_blur(h.reshape(-1), W, W, 1, 1), 'W': W, 'H': W}
    alp, mp = al.pixels().astype(np.float64), mt.pixels()[..., 0].astype(np.float64)
    shade = 0.82 + 0.3 * (hb['h'].reshape(W, W) - (hp / 255.0) * 0.75) / 0.12
    out = np.zeros((W, W, 4), np.uint8)
    for ch in range(3):
        out[..., ch] = np.floor(np.clip(alp[..., ch] * shade, 0, 255)).astype(np.uint8)
    out[..., 3] = np.where(alp[..., 3] > 8, np.maximum(1, mp), 0).astype(np.uint8)
    return {'col': L.data_tex(out, srgb=True, name='corridor_patch_col'),
            'nrm': L.normal_tex(hb, 7, name='corridor_patch_nrm')}


# --------------------------------------------------------------------------------------- the uniform's stand ---

def _build_uniform(L, M, parent):
    torso_pts = [[0.001, 0.8], [0.15, 0.8], [0.172, 0.86], [0.165, 0.95], [0.148, 1.02], [0.155, 1.1], [0.172, 1.2],
                 [0.183, 1.29], [0.18, 1.36], [0.165, 1.415], [0.13, 1.46], [0.085, 1.5], [0.062, 1.53], [0.06, 1.58],
                 [0.001, 1.585]]

    def r_at(y):
        for i in range(1, len(torso_pts)):
            r0, y0 = torso_pts[i - 1]
            r1, y1 = torso_pts[i]
            if y0 <= y <= y1:
                return r0 + (r1 - r0) * (y - y0) / max(1e-6, y1 - y0)
        return 0.05
    SX, SZ = 1.27, 0.78
    torso = lathe_geometry(torso_pts, 48).scale(SX, 1, SZ)
    wb = L.bucket('uniform_wool').add(torso, None, uv='keep', uv_scale=[1.2, 1])
    for s in (-1, 1):                                    # empty sleeves hanging from the shoulders, slightly forward
        curve = catmull_rom([(s * 0.205, 1.4, 0.0), (s * 0.235, 1.18, 0.03), (s * 0.24, 0.92, 0.07)])
        wb.add(tube_geometry(curve, 16, 0.052, 14, False), None, uv='keep', uv_scale=[3, 1])
    flags = {'assembly': 'corridor_uniform'}
    wb.mesh(M['wool'], parent=parent, flags=flags)
    gb = L.bucket('uniform_gold')
    # the high collar's braid, the cuffs, the front piping, the buttons, the epaulettes and their fringe
    gb.add(cylinder_geometry(0.066, 0.066, 0.016, 32, 1, True), m4(0, 1.574, 0, 0, 0, 0, [SX * 0.98, 1, SZ * 1.05]),
           uv='keep')
    for s in (-1, 1):
        gb.add(torus_geometry(0.05, 0.007, 6, 20), m4(s * 0.24, 0.95, 0.068, math.pi / 2 - 0.12, 0, 0))
    for k in range(6):
        y = 1.0 + k * 0.075
        for xo in (-0.055, 0.055):
            r = r_at(y)
            zf = SZ * math.sqrt(max(0.0, r * r - (xo / SX) * (xo / SX)))
            gb.add(sphere_geometry(0.011, 10, 8), m4(xo, y, zf + 0.004, 0, 0, 0, [1, 1, 0.55]))
    for s in (-1, 1):
        gb.add(cylinder_geometry(0.06, 0.06, 0.018, 24), m4(s * 0.17, 1.445, 0.0, 0, 0, s * 0.42, [1, 1, 0.75]))
        for k in range(15):
            a = -math.pi * 0.55 + k * (math.pi * 1.1 / 14)
            fx = s * (0.17 + math.cos(a) * 0.058 * math.cos(0.42))
            fz = math.sin(a) * 0.045
            gb.add(cylinder_geometry(0.0045, 0.0045, 0.075, 5), m4(fx + s * 0.025, 1.4, fz, 0, 0, s * 0.2))
    for sag, w in ((0.06, 0.0065), (0.1, 0.006)):               # the aiguillette: gold cords, shoulder to chest
        cu = catmull_rom([(-0.19, 1.42, 0.04), (-0.15, 1.36 - sag, 0.13), (-0.07, 1.3 - sag * 0.6, 0.15),
                          (-0.045, 1.33, 0.14)])
        gb.add(tube_geometry(cu, 24, w, 6, False), None, uv='keep')
    gb.box(0.06, 0.05, 0.012, 0, 1.02, SZ * r_at(1.02) + 0.012)   # the belt's buckle
    gb.mesh(M['goldTrim'], parent=parent, flags=flags)
    belt = cylinder_geometry(r_at(1.02) + 0.006, r_at(1.02) + 0.006, 0.045, 48, 1, True).scale(SX, 1, SZ)
    L.bucket('uniform_leather').add(belt, m4(0, 1.02, 0), uv='keep', uv_scale=[4, 1]).mesh(M['leather'], parent=parent,
                                                                                         flags=flags)
    # the red sash, right shoulder to left hip, laid over the front: a flat band on the cloth
    sash_pts = []
    for k in range(15):
        s = k / 14
        y = 1.43 - s * 0.47
        x = -0.16 + s * 0.31
        r = r_at(y)
        zf = SZ * math.sqrt(max(0.0, r * r - (x / SX) * (x / SX))) + 0.007
        sash_pts.append((x, y, zf))
    sc_ = catmull_rom(sash_pts)
    N = 48
    pos, uvs, idx = [], [], []
    for i in range(N + 1):
        s = i / N
        p = np.array(sc_.get_point_at(s))
        tg = np.array(sc_.get_tangent_at(s))
        n = np.array([p[0] / (SX * SX), 0.0, p[2] / (SZ * SZ)])
        n = n / (np.linalg.norm(n) or 1.0)
        w = np.cross(tg, n)
        w = w / (np.linalg.norm(w) or 1.0) * 0.05
        lift = n * 0.003
        pos += [(p[0] + w[0] + lift[0], p[1] + w[1], p[2] + w[2] + lift[2]),
                (p[0] - w[0] + lift[0], p[1] - w[1], p[2] - w[2] + lift[2])]
        uvs += [(s * 6, 0), (s * 6, 1)]
        if i < N:
            a = 2 * i
            idx += [a, a + 1, a + 2, a + 1, a + 3, a + 2]
    sash = Geo(pos, None, uvs, idx).compute_vertex_normals()
    L.mesh_object('uniform_sash', sash, M['sash'], parent=parent, flags=flags)
    # the ribbon bar (invented colours) and the AI FORCE patch on the left sleeve
    rb_cv = CL.create_canvas(256, 96)
    rg = rb_cv.get_context('2d')
    cols = [['#7a0d16', '#d7a03a', '#0d1b3d'], ['#d7a03a', '#eef0f4', '#7a0d16'], ['#0d1b3d', '#d7a03a', '#0d1b3d'],
            ['#eef0f4', '#7a0d16', '#eef0f4'], ['#3a5d2a', '#d7a03a', '#3a5d2a'], ['#7a0d16', '#0d1b3d', '#7a0d16']]
    for i, cs in enumerate(cols):
        x, y = (i % 3) * 85, (i // 3) * 48
        for j, cc in enumerate(cs):
            rg.fill_style = cc
            rg.fill_rect(x + [0, 28, 57][j], y, [28, 29, 28][j], 46)
    rb_img = L.canvas_tex(rb_cv, name='uniform_ribbons')
    Mr = L.mat('uniform_ribbons')
    rbc, _ = Mr.nb.tex(rb_img, Mr.nb.uv())
    M['ribbons'] = Mr.standard(rbc, rough=0.55, ibl=L.ibl(1.0))
    L.mesh_object('uniform_ribbons', plane_geometry(0.1, 0.038), M['ribbons'], parent=parent,
                  M3=m4(0.075, 1.31, SZ * r_at(1.31) + 0.01, 0, 0.32, 0), flags=flags)
    L.mesh_object('uniform_patch', circle_geometry(0.045, 40), M['patchSmall'], parent=parent,
                  M3=m4(0.292, 1.3, 0.03, 0, math.pi / 2 - 0.12, 0), flags=flags)
    # the stand: a brass pole on a wooden tripod
    sb = L.bucket('stand_brass').add(cylinder_geometry(0.016, 0.016, 0.78, 12), m4(0, 0.4, 0), uv='keep')
    sb.add(cylinder_geometry(0.03, 0.035, 0.06, 16), m4(0, 0.13, 0), uv='keep')
    sb.mesh(M['goldTrim'], parent=parent, flags=flags)
    wbk = L.bucket('stand_wood')
    for k in range(3):
        a = k * math.pi * 2 / 3 + 0.4
        wbk.add(box_geometry(0.034, 0.03, 0.42), m4(math.sin(a) * 0.2, 0.06, math.cos(a) * 0.2, -0.22, a, 0))
    wbk.mesh(M['wood'], parent=parent, flags=flags)


def _build_cushion(L, M, parent):
    """A squared pillow: a sphere pushed to a superellipse, thinner at the edges; gold piping and four tassels."""
    g = sphere_geometry(1, 48, 24)
    P = g.pos
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    sx = np.sign(x) * np.power(np.abs(x), 0.32) * 0.215
    sz = np.sign(z) * np.power(np.abs(z), 0.32) * 0.215
    edge = np.maximum(np.abs(sx), np.abs(sz)) / 0.215
    g.pos = np.stack([sx, y * 0.06 * (1.05 - 0.55 * np.power(edge, 3)), sz], 1)
    g.compute_vertex_normals()
    flags = {'assembly': 'corridor_pedestal'}
    L.mesh_object('cushion_velvet', g, M['velvet'], parent=parent, M3=m4(0, 0.06, 0), flags=flags)
    pipe = []
    for k in range(65):
        a = k / 64 * math.pi * 2
        cx, sz2 = math.cos(a), math.sin(a)
        pipe.append((math.copysign(math.pow(abs(cx), 0.32), cx) * 0.216 if cx != 0 else 0.0, 0.06,
                     math.copysign(math.pow(abs(sz2), 0.32), sz2) * 0.216 if sz2 != 0 else 0.0))
    pg = L.bucket('cushion_gold').add(tube_geometry(catmull_rom(pipe, True), 128, 0.006, 6, True), None, uv='keep')
    for x_, z_ in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        pg.add(CL.cone_geometry(0.018, 0.07, 10), m4(x_ * 0.215, 0.025, z_ * 0.215))
        pg.add(sphere_geometry(0.013, 10, 8), m4(x_ * 0.215, 0.064, z_ * 0.215))
    pg.mesh(M['braid'], parent=parent, flags=flags)


def _build_cap(L, M, cap, S):
    """The cap: origin = the centre of the headband's lower edge, visor toward +Z (three), metres (a 58-60 cm head)."""
    band = cylinder_geometry(0.097, 0.095, 0.056, 64, 1, True).translate(0, 0.028, 0)
    crown = lathe_geometry([[0.097, 0.054], [0.108, 0.066], [0.124, 0.08], [0.138, 0.092], [0.145, 0.1], [0.143, 0.106],
                            [0.13, 0.11], [0.08, 0.112], [0.001, 0.113]], 64)
    P = crown.pos.copy()                                  # the saddle: the front rides up, the back drops a little
    x, y, z = P[:, 0], P[:, 1].copy(), P[:, 2] * 1.07
    zn = z / 0.155
    hi = y > 0.07
    y = np.where(hi, y + 0.034 * np.power(np.maximum(0, zn), 1.6) * np.minimum(1, (y - 0.07) / 0.03)
                 - 0.008 * np.maximum(0, -zn), y)
    crown.pos = np.stack([x * 0.97, y, z], 1)
    crown.compute_vertex_normals()
    flags = {'assembly': 'corridor_cap'}
    cw = L.bucket('cap_wool').add(band, None, uv='keep', uv_scale=[3.5, 0.3]).add(crown, None, uv='keep', uv_scale=[3.5, 0.6])
    cw.mesh(M['wool'], parent=cap, flags=flags)
    braid = cylinder_geometry(0.0995, 0.0975, 0.032, 64, 1, True).translate(0, 0.03, 0)
    cb = L.bucket('cap_braid').add(braid, None, uv='keep', uv_scale=[6, 1])
    cord = []
    for k in range(25):
        a = -1.05 + k * 2.1 / 24
        cord.append((math.sin(a) * 0.101, 0.016 - math.cos(a * 1.2) * 0.004, math.cos(a) * 0.101))
    cb.add(tube_geometry(catmull_rom(cord), 32, 0.0035, 6, False), None, uv='keep')
    for s in (-1, 1):
        cb.add(sphere_geometry(0.007, 10, 8), m4(s * math.sin(1.08) * 0.1, 0.017, math.cos(1.08) * 0.1))
    # the visor: a curved peak from the band's lower front, sloping down
    NA, NR = 32, 6
    pos, idx, uvs = [], [], []

    def vpt(a, s, top):
        ext = 0.07 * math.pow(math.cos(a / 1.25 * math.pi / 2), 0.7)
        r = 0.096 + s * ext
        y_ = 0.006 - s * ext * 0.5 - s * s * 0.012 * (1 + abs(a)) + (0.0035 if top else 0)
        return (math.sin(a) * r * 0.99, y_, math.cos(a) * r * 1.03)
    for top in (True, False):
        base = len(pos)
        for i in range(NA + 1):
            for j in range(NR + 1):
                a, s = -1.25 + 2.5 * i / NA, j / NR
                pos.append(vpt(a, s, top))
                uvs.append((i / NA, s))
        for i in range(NA):
            for j in range(NR):
                a0 = base + i * (NR + 1) + j
                a1 = a0 + NR + 1
                idx += ([a0, a1, a0 + 1, a1, a1 + 1, a0 + 1] if top else [a0, a0 + 1, a1, a1, a0 + 1, a1 + 1])
    vg = Geo(pos, None, uvs, idx).compute_vertex_normals()
    L.mesh_object('cap_visor', vg, M['patent'], parent=cap, flags=flags)
    edge = []
    for i in range(41):
        a = -1.25 + 2.5 * i / 40
        x_, y_, z_ = vpt(a, 1, True)
        edge.append((x_, y_ - 0.0015, z_))
    cb.add(tube_geometry(catmull_rom(edge), 48, 0.0028, 5, False), None, uv='keep')
    cb.mesh(M['braid'], parent=cap, flags=flags)
    # the badge: a winged chip (original), gold
    bd_cv = CL.create_canvas(256, 192)
    bd = bd_cv.get_context('2d')
    bd.clear_rect(0, 0, 256, 192)
    bd.fill_style = '#fff'
    for s in (-1, 1):
        for k in range(4):
            bd.begin_path()
            x0, y0 = 128 + s * 34, 86 + k * 14
            bd.move_to(x0, y0); bd.line_to(x0 + s * (96 - k * 16), y0 - 26 + k * 6)
            bd.line_to(x0 + s * (90 - k * 16), y0 - 14 + k * 6); bd.line_to(x0, y0 + 10)
            bd.close_path(); bd.fill()
    bd.fill_rect(100, 66, 56, 56)
    for k in range(4):
        bd.fill_rect(104 + k * 14, 56, 6, 10)
        bd.fill_rect(104 + k * 14, 122, 6, 10)
    bd.begin_path(); bd.move_to(128, 18); bd.line_to(136, 40); bd.line_to(158, 42); bd.line_to(140, 54)
    bd.line_to(146, 76 - 12); bd.line_to(128, 54); bd.line_to(110, 64); bd.line_to(116, 54); bd.line_to(98, 42)
    bd.line_to(120, 40); bd.close_path(); bd.fill()
    bd.fill_style = 'rgba(0,0,0,1)'
    bd.global_composite_operation = 'destination-out'
    bd.fill_rect(114, 80, 28, 28)
    bd.global_composite_operation = 'source-over'
    bd_tex = L.canvas_tex(bd_cv, srgb=False, name='cap_badge_mask')
    Mbd = L.mat('cap_badge')
    nb = Mbd.nb
    gc, _ = nb.tex(S['goldF']['col'], nb.uv() * 0.5)
    op, _ = nb.tex(bd_tex, nb.uv())
    M['badge'] = Mbd.standard(gc * (1.05, 0.86, 0.55), rough=0.22, metal=1.0, alpha=nb.step(0.5, op.x), ibl=L.ibl(1.3))
    L.mesh_object('cap_badge', plane_geometry(0.075, 0.056), M['badge'], parent=cap, M3=m4(0, 0.093, 0.156, -0.42, 0, 0),
                  flags=flags)
