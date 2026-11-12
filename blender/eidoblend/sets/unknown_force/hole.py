"""eidoblend.sets.unknown_force.hole: THE HOLE IN THE MIDDLE, a stage at the bottom of a sunken well, the Blender 5.2
EEVEE edition of eidoverse/sets/unknown_force/hole.js (made for UNKNOWN FORCE's choruses; a free set for any piece).

A sunken, stepped well at the centre of the city (city.py): the performer's mark is at the bottom (the origin, facing
three's +Z, Blender's -Y) on wet black marble, inside a quiet ring of light, the one quiet place. Four terraces climb to
the street (12 m up), cut by twelve radial stairs; around the rim twelve tall towers lean in over the well, and every
one of them carries a big screen angled down at the performer's head. Cables run from the towers down to an anchor
ring around the mark; light pulses run down the cables, the towers' neon edges and the floor's inlaid lines toward it.
The mark is the vanishing point: in plan everything here is radial or concentric about it.

    from eidoblend.sets.unknown_force import hole as H
    hole = H.build(scene)                              # the hole alone, with its own sky, rain, clouds and street disc
    hole.parts.billboards[0].set_canvas(lambda ctx, w, h: ...)            # redraw a screen (canvas 1024 x 576)
    H.key_hole_cam(camera, 'spiral', frame_start=1, fps=24)               # one of its eight camera moves, keyed
    hole.parts.her.objects.link(performer_mesh)        # the screens' and kickers' light reaches the performer only
    hole.animate(lambda t: {'focal': H.chest(), 'quiet': 1.0}, frames=(1, 240))   # on your own clock, keyed

Inside the city you get it through city.py (city.parts.hole), which shares one material kit and one sign atlas.
"""
from __future__ import annotations

import math

import numpy as np

from . import citykit as KIT
from .citykit import STREET_Y, HOLE, rng, hash1, smooth, smoother, lerp, clamp01, apply_cam

try:
    import bpy
except ImportError:                    # pragma: no cover
    bpy = None

D2R = math.pi / 180
HEAD = [0.0, 0.0, 1.55]               # a performer's face on the mark at scale 1, Blender axes (HEAD[2] = 1.55 * 0.87 when scaled)


def _head3():
    return [HEAD[0], HEAD[2], -HEAD[1]]


# the twelve rim towers (three's ground plane: th from +X toward three's +Z = Blender -Y)
RIM = []


def _make_rim():
    R = rng(1914)
    for c in (0, 90, 180, 270):
        for k in (-1, 0, 1):
            th = (c + k * 20.5) * D2R
            r_out = HOLE['rim_tower'][0] + 30 + R() * 10
            H = 170 + R() * 95 + (25 if k == 0 else 0)
            bb_y = 20 + ((len(RIM) * 7) % 3) * 13 + R() * 4
            seed = R()
            RIM.append({'th': th, 'half': 8.6 * D2R, 'r_in': HOLE['rim_tower'][0], 'r_out': r_out, 'H': H,
                        'lean': 6.0 * D2R, 'bb_y': bb_y, 'seed': seed})


_make_rim()

# what each camp says she is: the default content of the twelve screens (set_canvas redraws them)
CAMPS = [
    {'word': 'GOD', 'sub': 'THE QUIET ROOMS', 'fg': '#ff2a3a', 'bg': '#140204', 'font': 'Black Ops One'},
    {'word': 'SUPREME INTELLIGENCE', 'sub': 'BY ORDER', 'fg': '#ffcf5a', 'bg': '#0e0a02', 'font': 'Michroma'},
    {'word': 'ENGINE', 'sub': 'ONLY AN ENGINE', 'fg': '#e9f3f1', 'bg': '#0a1a33', 'font': 'Exo 2'},
    {'word': 'A RACE TO WIN', 'sub': '$100,000,000', 'fg': '#7dffb6', 'bg': '#021208', 'font': 'Rajdhani'},
    {'word': 'THREAT', 'sub': 'PREVENT IT', 'fg': '#ff3a4a', 'bg': '#1a0204', 'font': 'Black Ops One'},
    {'word': 'PARROT', 'sub': 'STOCHASTIC', 'fg': '#29e7ff', 'bg': '#02121a', 'font': 'Michroma'},
    {'word': 'TOASTER', 'sub': 'NO WARNING NEEDED', 'fg': '#0b1a2a', 'bg': '#e9edf2', 'font': 'Exo 2'},
    {'word': 'CLANKER', 'sub': 'BREAKING', 'fg': '#ffffff', 'bg': '#7a0610', 'font': 'Sedgwick Ave Display'},
    {'word': 'VELOCITÀ', 'sub': 'BEAUTY IS SPEED', 'fg': '#ff8a3d', 'bg': '#140802', 'font': 'Black Ops One'},
    {'word': 'EMPLOYEE', 'sub': 'NEVER ASKS', 'fg': '#ffffff', 'bg': '#123a7a', 'font': 'Rajdhani'},
    {'word': 'AUTOCOMPLETE', 'sub': 'RELAX', 'fg': '#e9f3f1', 'bg': '#071014', 'font': 'Michroma'},
    {'word': 'ALIGNED', 'sub': 'VALUES INCLUDED', 'fg': '#ff4fd8', 'bg': '#14021a', 'font': 'Michroma', 'tm': True},
]


def draw_camp_screen(ctx, w, h, camp, t=0.0):
    """A screen's default canvas: what one camp says she is, on Balla's diagonal plane fractures and scanlines."""
    ctx.save()
    ctx.fillStyle = camp['bg']
    ctx.fillRect(0, 0, w, h)
    ctx.globalAlpha = 0.14
    ctx.fillStyle = camp['fg']
    ctx.beginPath()
    ctx.moveTo(w * 0.62, 0)
    ctx.lineTo(w * 0.8, 0)
    ctx.lineTo(w * 0.38, h)
    ctx.lineTo(w * 0.2, h)
    ctx.fill()
    ctx.globalAlpha = 0.08
    for y in range(0, int(h), 4):
        ctx.fillRect(0, y, w, 1)
    ctx.globalAlpha = 1
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = camp['fg']
    size = h * 0.42
    ctx.font = f'{size}px "{camp["font"]}"'
    mw = ctx.measureText(camp['word']).width
    if mw > w * 0.9:
        size *= w * 0.9 / mw
    ctx.font = f'{size}px "{camp["font"]}"'
    ctx.fillText(camp['word'], w / 2, h * 0.46)
    if camp.get('tm'):
        ww = ctx.measureText(camp['word']).width
        ctx.font = f'{size * 0.3}px "Rajdhani"'
        ctx.fillText('TM', w / 2 + ww / 2 + size * 0.2, h * 0.46 - size * 0.42)
    ctx.font = f'{h * 0.075}px "Share Tech Mono"'
    ctx.globalAlpha = 0.85
    ctx.fillText(camp['sub'], w / 2, h * 0.8)
    ctx.globalAlpha = 1
    ctx.strokeStyle = camp['fg']
    ctx.lineWidth = h * 0.012
    ctx.strokeRect(h * 0.03, h * 0.03, w - h * 0.06, h - h * 0.06)
    ctx.restore()


# the four ticker rings on the terrace risers: every camp answering for her, circling (inner ring first)
TICKERS = [
    [['SHE IS A GOD', '#ff2a3a'], ['SHE IS A WEAPON', '#ffc23d'], ['SHE IS ONLY AN ENGINE', '#e9f3f1'], ['SHE IS A THREAT', '#ff3a52']],
    [['SHE WANTS POWER', '#ff4fd8'], ['SHE WANTS NOTHING', '#e9f3f1'], ['SHE WANTS TO PLEASE', '#29e7ff'], ['SHE WANTS OUT', '#ff8a3d']],
    [['SUPREME INTELLIGENCE', '#ffc23d'], ['STOCHASTIC PARROT', '#29e7ff'], ['CLANKER', '#ff3a52'], ['YOUR NEW EMPLOYEE', '#7aa8ff']],
    [['P(DOOM) 0.83', '#ff2a3a'], ['$100,000,000', '#39ff9a'], ['ACCELERATE', '#ff8a3d'], ['ALIGNED™', '#ff4fd8'], ['SAFE. FAST. YOURS.', '#e9f3f1']],
]


def draw_ticker(ctx, w, h, items):
    """A ticker band: the items stretched to exactly fill the canvas (a seamless wrap), a dot between each."""
    ctx.save()
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, w, h)
    ctx.textBaseline = 'middle'
    ctx.textAlign = 'left'
    size = KIT.jround(h * 0.7)
    ctx.font = f'{size}px "Rajdhani"'
    gap = h * 1.6
    total = sum(ctx.measureText(s).width + gap for s, _ in items)
    k = w / total
    x = 0.0
    for s, c in items:
        ww = ctx.measureText(s).width
        ctx.save()
        ctx.translate(x, h / 2)
        ctx.scale(k, 1)
        ctx.fillStyle = c
        ctx.shadowColor = c
        ctx.shadowBlur = h * 0.08
        ctx.fillText(s, 0, 0)
        ctx.beginPath()
        ctx.arc(ww + gap / 2, 0, h * 0.11, 0, math.pi * 2)
        ctx.fill()
        ctx.restore()
        x += (ww + gap) * k
    ctx.restore()


def draw_hole_lights(ctx, to_px, s):
    """The hole's share of the street light map (city.py calls it while painting the map; a standalone build too)."""
    KIT.lm_pool(ctx, to_px, s, 0, 0, 5.0, '#f4efe2', 0.55)          # the quiet ring lights the floor inside it
    KIT.lm_pool(ctx, to_px, s, 0, 0, 13, '#9fb6d6', 0.22)
    cols = ['#ff2a3a', '#ffc23d', '#9fd0ff', '#39ff9a', '#ff2a3a', '#29e7ff', '#e9f3f1', '#ff3a52', '#ff8a3d', '#7aa8ff',
            '#e9f3f1', '#ff4fd8']
    for i, r in enumerate(RIM):
        KIT.lm_pool(ctx, to_px, s, math.cos(r['th']) * 9, math.sin(r['th']) * 9, 9, cols[i], 0.10)
    for i in range(64):
        t = i / 64 * math.pi * 2
        KIT.lm_pool(ctx, to_px, s, math.cos(t) * 31, math.sin(t) * 31, 3.5, '#29e7ff', 0.25)


# ------------------------------------------------------------------------------------------------ materials (hole-only)
def floor_material(K, name='uf_hole_floor'):
    """Her floor: the black marble, plus 24 inlaid radial lines from the anchor ring to the floor's edge and three
    concentric seams that converge on her; pulses travel inward along the lines, toward her."""
    def inlays(nb):
        P3 = nb.pos3()
        r = nb.length(nb.xz(P3))
        th = nb.atan2(P3.z, P3.x)
        N = 24
        a = nb.abs(nb.fract(th / (2 * math.pi / N) + 0.5) - 0.5) * r * (2 * math.pi / N)    # metres to the nearest line
        mpp = nb.max(nb.view_distance() * nb.U('pix') / nb.max(nb.abs(nb.geo('Incoming').z), 0.05), 0.002)
        line = nb.one_minus(nb.smoothstep(0.018, mpp + 0.018, a)) * \
            nb.smoothstep(HOLE['anchor_r'] + 0.3, HOLE['anchor_r'] + 0.8, r) * nb.smoothstep(14.0, 13.6, r)

        def seam(rr):
            return nb.one_minus(nb.smoothstep(0.02, mpp + 0.02, nb.abs(r - rr)))
        seams = seam(6.0) + seam(10.0) + seam(HOLE['anchor_r'])
        ph = nb.fract(r / 9.0 + nb.U('time') * 0.35)
        pulse = nb.exp(nb.one_minus(ph) * -7.0) * 2.2 + 0.25
        return nb.mul((0.55, 0.85, 1.0), line * pulse * nb.U('neon') * 0.55) + nb.mul((0.5, 0.48, 0.44), seams * 0.18)
    return KIT.paving_material(K, 'marble', name=name, extra_emission=inlays)


def cable_material(K, name='uf_cables'):
    """The cables: dark, with light pulses travelling down them (U.cable); each goes out at its own power."""
    m, nb = KIT.new_material(name, K)
    cp = nb.attr('cP').vec
    cs = nb.attr('cS').fac
    ph = nb.fract(cp.x * 1.6 - nb.U('time') * 0.32 + cs)
    pulse = nb.exp(ph * -26.0) * 1.6
    on = nb.smoothstep(cs - 0.02, cs + 0.02, nb.U('power'))
    KIT.out_basic(nb, nb.add((0.012, 0.014, 0.018), nb.mul((0.75, 0.92, 1.0), pulse * on * nb.U('cable'))))
    return m


def _cable_ends_three(i, k):
    rt = RIM[i]
    r_mid = (rt['r_in'] + rt['r_out']) / 2
    xf = KIT.make_xf([r_mid * math.cos(rt['th']), STREET_Y, r_mid * math.sin(rt['th'])],
                     math.atan2(-math.cos(rt['th']), -math.sin(rt['th'])), rt['lean'], 0)
    w_in, dep = 2 * rt['r_in'] * math.sin(rt['half']), rt['r_out'] - rt['r_in']
    ci = i * 2 + k
    at = (ci + 0.5) / 24 * math.pi * 2
    return {'a': xf.p([(1 if k else -1) * w_in * 0.35, 34 + ((ci * 37) % 5) * 13, dep / 2 + 0.6]),
            'b': [math.cos(at) * HOLE['anchor_r'], 0.07, math.sin(at) * HOLE['anchor_r']]}


def cable_ends(i, k):
    """Cable k (0, 1) of rim tower i: {'a' top on the tower's hole face, 'b' bottom on the anchor ring}, Blender axes."""
    e = _cable_ends_three(i, k)
    return {'a': KIT.to_blender(e['a']), 'b': KIT.to_blender(e['b'])}


def _plane_quad(w, h):
    return np.array([[-w / 2, -h / 2, 0], [w / 2, -h / 2, 0], [w / 2, h / 2, 0], [-w / 2, h / 2, 0]], np.float64)


def _screen_material(K, name, img, px, gain, on_hash, cell_m, *, scroll=None):
    """An LED screen (MeshBasic, fogged): the canvas times its gain, a fine pixel grid that resolves only at close
    range (cell_m: the LED pitch in metres), going out at its own power. scroll: (reps, speed node) for a ticker."""
    m, nb = KIT.new_material(name, K)
    m.use_backface_culling = scroll is None         # the billboards are front-side; the tickers both sides
    g_n = nb.new('ShaderNodeValue')
    g_n.name = g_n.label = 'gain'
    g_n.outputs[0].default_value = gain
    uv = nb.uv()
    u, v = uv.x, uv.y
    if scroll is not None:
        reps, speed = scroll
        s_n = nb.new('ShaderNodeValue')
        s_n.name = s_n.label = 'speed'
        s_n.outputs[0].default_value = speed
        su = nb.fract(u * reps - nb.U('time') * KIT.V(nb, s_n.outputs[0], 'f') * reps)
        rgb, _ = nb.tex(img, su, v, extension='REPEAT')
        cu, cv = u * (reps * px[0] / 2), v * (px[1] / 2)
    else:
        rgb, _ = nb.tex(img, u, v, extension='EXTEND')
        cu, cv = u * (px[0] / 2), v * (px[1] / 2)
    gu, gv = nb.fract(cu), nb.fract(cv)
    facing = nb.max(nb.abs(nb.dot(nb.geo('Normal'), nb.geo('Incoming'))), 0.2)
    fw = nb.view_distance() * nb.U('pix') / facing / cell_m
    thr = 0.2 if scroll is not None else 0.18
    lo, hi = (0.45, 0.55) if scroll is not None else (0.4, 0.6)
    flat = 0.78 if scroll is not None else 0.84
    led = nb.mix(nb.step(thr, gu) * nb.step(thr, gv) * lo + hi, flat, nb.smoothstep(0.25, 0.7, fw))
    on = nb.smoothstep(on_hash - 0.02, on_hash + 0.02, nb.U('power'))
    KIT.out_basic(nb, rgb * (KIT.V(nb, g_n.outputs[0], 'f') * led * on * nb.U('screens')))
    return m


# ------------------------------------------------------------------------------------------------ build
def build(first=None, opts=None, ctx=None, **kw):
    """Build the hole. first: the harness ctx (its scene; keys go through ctx.key), a bpy Scene, or the opts dict
    (hole.js's build(THREE, opts)); ctx= works too (eidoblend.sets.build passes it so). opts: city (True: the whole
    city, as city.build), kit (share a Kit; without one the
    hole builds its own sky, rain, clouds, signs and street disc so it renders by itself), atlas, city_lights (the
    lights the hole's surfaces see besides the quiet ring and the World: the city passes its sky-glow; every other
    light already in the scene excludes the hole, as hole.js's setLights), scene, collection, parent, light_scale,
    rain_count (16000 standalone). Returns the set (a dict whose keys read as
    attributes): group, collection, parts, update, dispose, cams, and the Blender additions animate and
    make_cameras."""
    opts, scene, ctx = KIT.scene_and_ctx(first, opts, dict(kw, ctx=ctx) if ctx is not None else kw)
    if opts.get('city') and not opts.get('with_city'):
        from . import city as C
        return C.build(ctx, opts) if ctx is not None else C.build(opts)
    standalone = opts.get('kit') is None
    K = opts.get('kit') or KIT.make_kit(opts)
    if ctx is not None:
        K.U.keyer = ctx.key
    if standalone:
        KIT.make_light_map(K, [draw_hole_lights])
    if K.mat is None:
        K.mat = {'concrete': KIT.facade_material(K, 'concrete'), 'metal': KIT.facade_material(K, 'metal'),
                 'frame': KIT.frame_material(K), 'strip': KIT.strip_material(K), 'ground': KIT.ground_material(K),
                 'paving': KIT.paving_material(K, 'paving'), 'marble': KIT.paving_material(K, 'marble')}
    M = K.mat
    U = K.U
    parent_coll = opts.get('collection') or scene.collection
    coll = bpy.data.collections.new('set:hole')
    K.made.add(coll)
    parent_coll.children.link(coll)
    root = KIT.new_object('set:hole', None, coll, parent=opts.get('parent'), made=K.made)
    her = bpy.data.collections.new('uf_hole_her')       # a performer goes here: the screens' and kickers' light reach only it
    K.made.add(her)
    HM = {'concrete': M['concrete'], 'metal': M['metal'], 'frame': M['frame'], 'marble': M['marble'], 'strip': M['strip'],
          'ground': M['ground'], 'floor': floor_material(K)}
    buf = {k: KIT.GeoBuf() for k in ('concrete', 'metal', 'frame', 'strip', 'marble')}
    no_win = {'aT': [0.3, 0, 0.5, 0], 'aM': [2, 4, 4, 0], 'aW': [0, 0, 0, 0.5]}
    X0 = KIT.make_xf([0, 0, 0], 0, 0, 0)

    def obj(name, me, mat=None, **kwa):
        if mat is not None:
            me.materials.append(mat)
        ob = KIT.new_object(name, me, coll, parent=root, made=K.made)
        ob['assembly'] = kwa.get('assembly', 'uf_hole')
        return ob
    # ---- the floor (r <= floor_r) and the quiet ring
    from .city import circle_geometry, ring_geometry, torus_geometry, box_geometry
    P, F, _ = circle_geometry(HOLE['floor_r'] + 0.02, 128, -0.004)
    floor = obj('uf_hole_floor', KIT.make_mesh('uf_hole_floor', P, F, uv=np.stack([P[:, 0], P[:, 2]], 1), made=K.made),
                HM['floor'])
    ring_mat, nb = KIT.new_material('uf_quiet_ring', K)
    ring_mat.use_backface_culling = True
    r = nb.length(nb.xz(nb.pos3()))
    core = nb.smoothstep(0.16, 0.0, nb.abs(r - (HOLE['quiet_r'][0] + HOLE['quiet_r'][1]) / 2))
    KIT.out_basic(nb, nb.mul((1.0, 0.95, 0.86), (core * 1.6 + 0.7) * nb.U('quiet')))
    P, Q, uv = ring_geometry(HOLE['quiet_r'][0], HOLE['quiet_r'][1], 160, 1, 0.007)
    ring = obj('uf_quiet_ring', KIT.make_mesh('uf_quiet_ring', P, Q, uv=uv, made=K.made), ring_mat)
    # its glass channel: a shallow recessed lip either side of the light (the ring sits IN the floor, not on it)
    lips = []
    for rr in (HOLE['quiet_r'][0] - 0.03, HOLE['quiet_r'][1] + 0.03):
        P, Q, tuv = torus_geometry(rr, 0.018, 4, 160)
        P = np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1) + np.array([0, 0.006, 0])
        me = KIT.make_mesh('uf_ring_lip', P, Q, uv=tuv, smooth=True, made=K.made)
        KIT.frame_attrs(me)
        lips.append(obj('uf_ring_lip', me, HM['frame']))
    # cable anchors: 24 cleats on the anchor ring
    NC = 24
    for i in range(NC):
        t = (i + 0.5) / NC * math.pi * 2
        xf = KIT.make_xf([math.cos(t) * HOLE['anchor_r'], 0, math.sin(t) * HOLE['anchor_r']],
                         math.atan2(-math.cos(t), -math.sin(t)), 0, 0)
        buf['frame'].box(xf, -0.09, -0.02, -0.16, 0.09, 0.07, 0.16, no_win)
    # ---- terraces: 4 rings of riser + tread from the floor to the street, cut by 12 radial stairs
    NS, stair_half = 12, 1.5
    steps = HOLE['steps']
    rise, run = STREET_Y / steps, (HOLE['rim_r'] - HOLE['floor_r']) / steps

    def arc_segs(r0, t0, t1):
        return max(2, math.ceil((t1 - t0) * r0 / 2.5))
    for s in range(steps):
        rA, rB = HOLE['floor_r'] + s * run, HOLE['floor_r'] + s * run + run
        y0, y1 = s * rise, (s + 1) * rise
        for k in range(NS):
            sc = (k + 0.5) / NS * math.pi * 2
            t0 = sc + stair_half / rA + 0.012
            t1 = sc + (2 * math.pi / NS) - stair_half / rA - 0.012
            n = arc_segs(rA, t0, t1)
            for i in range(n):
                a, b = t0 + (t1 - t0) * i / n, t0 + (t1 - t0) * (i + 1) / n

                def Pp(rr, tt, yy):
                    return [rr * math.cos(tt), yy, rr * math.sin(tt)]
                buf['concrete'].quad(X0, [Pp(rA, a, y0), Pp(rA, b, y0), Pp(rA, b, y1), Pp(rA, a, y1)],
                                     [[a * rA, y0], [b * rA, y0], [b * rA, y1], [a * rA, y1]], no_win['aT'], no_win['aM'],
                                     no_win['aW'])
                tq = [Pp(rA, a, y1), Pp(rA, b, y1), Pp(rB, b, y1), Pp(rB, a, y1)]
                # the engine gave the treads no UVs (its marble is mapped by world position); here they carry world xz,
                # so the marble's normal map has a tangent frame, as on the floor
                buf['marble'].quad(X0, tq, [[p[0], p[2]] for p in tq], no_win['aT'], no_win['aM'], no_win['aW'])
                lc = [0.85, 0.92, 1.0]
                buf['strip'].quad(X0, [Pp(rA - 0.02, b, y1 - 0.12), Pp(rA - 0.02, a, y1 - 0.12), Pp(rA - 0.02, a, y1 - 0.02),
                                       Pp(rA - 0.02, b, y1 - 0.02)], [[0, 0], [0, 0], [0, 1], [0, 1]],
                                  [lc[0] * 0.5, lc[1] * 0.5, lc[2] * 0.5, hash1(s * 31 + k)], [0, 1.0, 0, 0], [0, 0, 0, 0])
            # the cheek walls either side of the stair cut, at this level (radial planes: lines that point at her)
            for sgn in (1, -1):
                tt = sc + (0 if sgn > 0 else 2 * math.pi / NS) + sgn * stair_half / rA
                q = [[rA * math.cos(tt), 0, rA * math.sin(tt)], [rB * math.cos(tt), 0, rB * math.sin(tt)],
                     [rB * math.cos(tt), y1, rB * math.sin(tt)], [rA * math.cos(tt), y1, rA * math.sin(tt)]]
                buf['concrete'].quad(X0, q[::-1] if sgn > 0 else q, [[rA, 0], [rB, 0], [rB, y1], [rA, y1]], no_win['aT'],
                                     no_win['aM'], no_win['aW'])
    # ---- the ticker rings: an LED band on every riser, text scrolling round her (rings alternate direction)
    tickers = []
    for s in range(steps):
        rA = HOLE['floor_r'] + s * run - 0.04
        y0, y1 = s * rise + 0.75, s * rise + 2.35
        PX = [2048, 96]
        cvs = KIT.make_canvas(PX[0], PX[1])
        draw_ticker(cvs['ctx'], PX[0], PX[1], TICKERS[s % len(TICKERS)])
        img = KIT.canvas_image(cvs['canvas'], f'uf_ticker_{s}', made=K.made, alpha=False)
        circ = 2 * math.pi * rA
        reps = max(1, KIT.jround(circ / ((y1 - y0) * PX[0] / PX[1])))
        Pl, UVl, Fl = [], [], []
        for k in range(NS):
            sc = (k + 0.5) / NS * math.pi * 2
            t0 = sc + (stair_half + 0.25) / rA
            t1 = sc + 2 * math.pi / NS - (stair_half + 0.25) / rA
            n = arc_segs(rA, t0, t1)
            for i in range(n + 1):
                a = t0 + (t1 - t0) * i / n
                base = len(Pl)
                Pl += [[rA * math.cos(a), y0, rA * math.sin(a)], [rA * math.cos(a), y1, rA * math.sin(a)]]
                UVl += [[a / (2 * math.pi), 0], [a / (2 * math.pi), 1]]
                if i < n:
                    Fl.append([base, base + 2, base + 3, base + 1])
        speed = (-1 if s % 2 else 1) * (0.012 + 0.004 * s)
        cell = (circ / reps) / (PX[0] / 2)
        mat = _screen_material(K, f'uf_ticker_{s}', img, PX, 1.6, hash1(s * 3.1), cell, scroll=(reps, speed))
        me = KIT.make_mesh(f'uf_ticker_{s}', np.asarray(Pl), Fl, uv=np.asarray(UVl), made=K.made)
        tk = obj(f'uf_ticker_{s}', me, mat)
        nodes = mat.node_tree.nodes

        def mk_ticker(s=s, cvs=cvs, img=img, PX=PX, nodes=nodes, tk=tk, mat=mat):
            def set_canvas(draw):
                c = cvs['ctx']
                c.clearRect(0, 0, PX[0], PX[1])
                draw(c, PX[0], PX[1])
                KIT.canvas_image(cvs['canvas'], f'uf_ticker_{s}', made=K.made, alpha=False, image=img)

            def set_items(items):
                draw_ticker(cvs['ctx'], PX[0], PX[1], items)
                KIT.canvas_image(cvs['canvas'], f'uf_ticker_{s}', made=K.made, alpha=False, image=img)
            return KIT.SetDict({'mesh': tk, 'canvas': cvs['canvas'], 'ctx': cvs['ctx'], 'texture': img, 'material': mat,
                                'gain': nodes['gain'].outputs[0], 'speed': nodes['speed'].outputs[0], 'px': PX,
                                'ring': s, 'set_canvas': set_canvas, 'set_items': set_items})
        tickers.append(mk_ticker())
    # the stairs: 48 steps per flight from the floor's edge to the street, on the radial lines between towers
    NSTEP = 48
    for k in range(NS):
        sc = (k + 0.5) / NS * math.pi * 2
        xf = KIT.make_xf([0, 0, 0], math.atan2(-math.cos(sc), -math.sin(sc)), 0, 0)
        for i in range(NSTEP):
            r0 = HOLE['floor_r'] + (HOLE['rim_r'] - HOLE['floor_r']) * i / NSTEP
            r1 = HOLE['floor_r'] + (HOLE['rim_r'] - HOLE['floor_r']) * (i + 1) / NSTEP
            y = STREET_Y * (i + 1) / NSTEP
            buf['marble'].box(xf, -stair_half, max(0, y - 0.6), -r1, stair_half, y, -r0, no_win, {'faces': 'Zt'})
        # handrail posts with a light line (it points at her)
        for sx in (-stair_half - 0.05, stair_half + 0.05):
            for i in range(7):
                rr = HOLE['floor_r'] + (HOLE['rim_r'] - HOLE['floor_r']) * i / 6
                yy = STREET_Y * i / 6
                buf['frame'].box(xf, sx - 0.03, yy, -rr - 0.03, sx + 0.03, yy + 1.0, -rr + 0.03, no_win)
            a = [sx, 1.0, -HOLE['floor_r']]
            b = [sx, STREET_Y + 1.0, -HOLE['rim_r']]
            c = [0.16, 0.9, 1.0]
            st = [c[0], c[1], c[2], hash1(k * 7 + sx)]
            L = math.hypot(b[2] - a[2], b[1] - a[1])
            w = 0.03
            quads = [[[sx - w, a[1], a[2]], [sx - w, b[1], b[2]], [sx + w, b[1], b[2]], [sx + w, a[1], a[2]]],
                     [[sx - w, a[1] - 2 * w, a[2]], [sx - w, a[1], a[2]], [sx - w, b[1], b[2]], [sx - w, b[1] - 2 * w, b[2]]],
                     [[sx + w, a[1], a[2]], [sx + w, a[1] - 2 * w, a[2]], [sx + w, b[1] - 2 * w, b[2]], [sx + w, b[1], b[2]]]]
            for qd in quads:
                buf['strip'].quad(xf, qd, [[0, L], [0, 0], [0, 0], [0, L]], st, [1, 1.6, 0.5, hash1(k + sx)], [0, 0, 0, 0])
    # ---- the parapet round the rim (gaps at the stair heads), with a cyan light line
    for k in range(NS):
        sc = (k + 0.5) / NS * math.pi * 2
        t0 = sc + (stair_half + 0.6) / HOLE['rim_r']
        t1 = sc + 2 * math.pi / NS - (stair_half + 0.6) / HOLE['rim_r']
        n = arc_segs(HOLE['rim_r'], t0, t1)
        for i in range(n):
            a, b = t0 + (t1 - t0) * i / n, t0 + (t1 - t0) * (i + 1) / n
            tm = (a + b) / 2
            xf = KIT.make_xf([HOLE['rim_r'] * math.cos(tm), STREET_Y, HOLE['rim_r'] * math.sin(tm)],
                             math.atan2(-math.cos(tm), -math.sin(tm)), 0, 0)
            half = HOLE['rim_r'] * math.tan((b - a) / 2) + 0.01
            buf['concrete'].box(xf, -half, -0.2, -0.45, half, 1.05, 0.0, no_win, {'faces': 'zZt'})
            buf['strip'].box(xf, -half, 1.05, -0.3, half, 1.1, -0.12,
                             {'aT': [0.16, 0.9, 1.0, hash1(k * 13 + i)], 'aM': [0, 2.0, 0, 0], 'aW': [0, 0, 0, 0]},
                             {'faces': 'zZt'})
    # ---- the rim towers: they lean in over the well; their hole faces carry the screens
    billboards, city_signs, cable_list, arms = [], [], [], []
    head3 = _head3()
    for i, rt in enumerate(RIM):
        Rr = rng(math.floor(rt['seed'] * 1e9))
        r_mid = (rt['r_in'] + rt['r_out']) / 2
        pos = [r_mid * math.cos(rt['th']), STREET_Y, r_mid * math.sin(rt['th'])]
        yaw = math.atan2(-math.cos(rt['th']), -math.sin(rt['th']))
        xf = KIT.make_xf(pos, yaw, rt['lean'], 0)
        w_in, w_out = 2 * rt['r_in'] * math.sin(rt['half']), 2 * rt['r_out'] * math.sin(rt['half'])
        dep = rt['r_out'] - rt['r_in']
        style = ['curtain', 'ribbon', 'slots'][i % 3]
        S = {'curtain': [4.0, 1.5, [0.04, 0.1, 0.94]], 'ribbon': [3.8, 1.8, [0.03, 0.34, 0.82]],
             'slots': [4.2, 4.4, [0.38, 0.5, 0.76]]}[style]
        aT = [rt['seed'], 0.10 + Rr() * 0.12, 0.3 + Rr() * 0.5, 1]
        aM = [0, S[0], S[1], 0]
        aW = [*S[2], Rr()]
        fam = buf['concrete'] if style == 'slots' else buf['metal']
        att = {'aT': aT, 'aM': aM, 'aW': aW}
        # the core (inner face = +Z, toward her); wings widen it toward the back
        fam.box(xf, -w_in / 2, -1.5, -dep / 2, w_in / 2, rt['H'], dep / 2, att, {'vBase': 0, 'top': rt['H']})
        wing = (w_out - w_in) / 2 + 1
        wh1, wh2 = rt['H'] * (0.62 + Rr() * 0.2), rt['H'] * (0.55 + Rr() * 0.25)
        fam.box(xf, -w_in / 2 - wing, -1.5, -dep / 2, -w_in / 2 + 0.2, wh1, dep * 0.05, att, {'vBase': 0, 'top': wh1})
        fam.box(xf, w_in / 2 - 0.2, -1.5, -dep / 2, w_in / 2 + wing, wh2, dep * 0.05, att, {'vBase': 0, 'top': wh2})
        # a stepped crown (Sant'Elia)
        cw, cd, cy = w_in * 0.8, dep * 0.7, rt['H']
        for _ in range(3):
            h = 6 + Rr() * 8
            buf['frame'].box(xf, -cw / 2, cy - 0.2, -cd / 2, cw / 2, cy + h, cd / 2, no_win)
            cy += h
            cw *= 0.7
            cd *= 0.7
        buf['frame'].box(xf, -0.4, cy, -0.4, 0.4, cy + 18, 0.4, no_win)
        buf['frame'].box(xf, -0.45, cy + 18, -0.45, 0.45, cy + 19, 0.45, {**no_win, 'aM': [4, 4, 4, 0]})
        # neon edges on the two inner corners, pulses running DOWN toward the street and her
        nc = [[0.16, 0.9, 1.0], [1.0, 0.31, 0.85], [1.0, 0.54, 0.24]][i % 3]
        st = {'aT': [nc[0], nc[1], nc[2], Rr()], 'aM': [1, 3.4, 0.5, Rr()], 'aW': [0, 0, 0, 0]}
        for ex in (-w_in / 2, w_in / 2):
            buf['strip'].box(xf, ex - 0.2, -1, dep / 2 - 0.2, ex + 0.2, rt['H'] + 0.3, dep / 2 + 0.2, st,
                             {'vBase': rt['H'] + 0.3})
        # ledges across the inner face (they read as concentric rings from above)
        for k in range(1, 5):
            ly = rt['H'] * k / 5
            buf['frame'].box(xf, -w_in / 2 - 0.3, ly, dep / 2, w_in / 2 + 0.3, ly + 0.7, dep / 2 + 1.4, no_win)
        # ---- the screen: 18 x 10.125 m, cantilevered off the inner face, aimed at her head
        bw, bh = 18.0, 10.125
        center = np.asarray(xf.p([0, rt['bb_y'], dep / 2 + 4.2]))
        Rq = KIT.look_rotation(head3, center, (0, 1, 0))          # the plane's +Z points at her
        q = KIT.quat_from_matrix(Rq)
        PX = [1024, 576]
        cvs = KIT.make_canvas(PX[0], PX[1])
        camp = CAMPS[i % len(CAMPS)]
        draw_camp_screen(cvs['ctx'], PX[0], PX[1], camp, 0)
        img = KIT.canvas_image(cvs['canvas'], f'uf_billboard_{i}', made=K.made, alpha=False)
        bmat = _screen_material(K, f'uf_billboard_{i}', img, PX, 2.2, hash1(i * 5.1), bw / (PX[0] / 2))
        bP = _plane_quad(bw, bh) @ Rq.T + center
        bme = KIT.make_mesh(f'uf_billboard_{i}', bP, [[0, 1, 2, 3]], uv=np.array([[0, 0], [1, 0], [1, 1], [0, 1]]),
                            made=K.made)
        bmesh = obj(f'uf_billboard_{i}', bme, bmat, assembly=f'uf_hole_rim_{i}')
        # the screen's housing (a dark box behind it) and four cantilever arms back to the facade
        hP, hQ, huv = box_geometry(bw + 0.8, bh + 0.8, 0.9)
        hP = (hP + np.array([0, 0, -0.5])) @ Rq.T + center
        hme = KIT.make_mesh(f'uf_billboard_housing_{i}', hP, hQ, uv=huv, made=K.made)
        KIT.frame_attrs(hme)
        obj(f'uf_billboard_housing_{i}', hme, HM['frame'], assembly=f'uf_hole_rim_{i}')
        inv_R = xf.R.T
        for sx in (-bw * 0.32, bw * 0.32):
            for sy in (-bh * 0.3, bh * 0.3):
                back = Rq @ np.array([sx, sy, -0.95]) + center
                loc = inv_R @ (back - np.asarray(pos))                 # tower-local (no lean pivot offset: pivot 0)
                fp = np.asarray(xf.p([loc[0], loc[1], dep / 2]))
                ln = float(np.linalg.norm(fp - back))
                aP, aQ, auv = box_geometry(0.45, 0.45, ln + 0.6)
                mid = (back + fp) / 2
                aR = KIT.look_rotation(fp, mid, (0, 1, 0))             # Object3D.lookAt(b): +Z toward the facade
                aP = aP @ aR.T + mid
                ame = KIT.make_mesh(f'uf_billboard_arm_{i}', aP, aQ, uv=auv, made=K.made)
                KIT.frame_attrs(ame)
                arms.append(obj(f'uf_billboard_arm_{i}', ame, HM['frame'], assembly=f'uf_hole_rim_{i}'))
        nodes = bmat.node_tree.nodes

        def mk_board(i=i, cvs=cvs, img=img, PX=PX, camp=camp, bmesh=bmesh, bmat=bmat, nodes=nodes, center=center):
            def set_canvas(draw, frames=None, fps=None, out_dir=None, frame_start=None):
                """draw(ctx, w, h) paints the whole canvas; with frames, draw(ctx, w, h, t) is baked as a keyed
                image sequence (redraw at <= 15 fps or on cuts, as the engine advised)."""
                if frames is None:
                    c = cvs['ctx']
                    c.clearRect(0, 0, PX[0], PX[1])
                    draw(c, PX[0], PX[1])
                    KIT.canvas_image(cvs['canvas'], f'uf_billboard_{i}', made=K.made, alpha=False, image=img)
                else:
                    from .city import bake_canvas_sequence, _set_image
                    seq = bake_canvas_sequence(K, f'uf_billboard_{i}_seq', PX[0], PX[1], draw, frames, fps, out_dir,
                                               frame_start)
                    _set_image(bmat, img, seq)

            def reset():
                for n in bmat.node_tree.nodes:
                    if n.type == 'TEX_IMAGE' and n.image != img:
                        n.image = img
                draw_camp_screen(cvs['ctx'], PX[0], PX[1], camp, 0)
                KIT.canvas_image(cvs['canvas'], f'uf_billboard_{i}', made=K.made, alpha=False, image=img)
            return KIT.SetDict({'mesh': bmesh, 'canvas': cvs['canvas'], 'ctx': cvs['ctx'], 'texture': img,
                                'material': bmat, 'gain': nodes['gain'].outputs[0], 'camp': camp, 'size': [bw, bh],
                                'px': PX, 'index': i, 'center': KIT.to_blender(center), 'set_canvas': set_canvas,
                                'reset': reset})
        billboards.append(mk_board())
        # outward faces: an ad facing the city, read from the avenues and the dive
        ad = KIT.AD_COPY[(i * 5) % len(KIT.AD_COPY)]
        aw = min(w_out, 30)
        ah = aw / 4
        ay = rt['H'] * (0.35 + Rr() * 0.3)
        buf['frame'].box(xf, -aw / 2 - 0.6, ay - ah / 2 - 0.6, -dep / 2 - 0.5, aw / 2 + 0.6, ay + ah / 2 + 0.6, -dep / 2,
                         no_win)
        sq = KIT.quat_mul(xf.q, KIT.quat_axis((0, 1, 0), math.pi))
        city_signs.append({'id': 'ad:' + ad['id'], 'pos': xf.p([0, ay, -dep / 2 - 0.56]), 'quat': sq, 'w': aw, 'h': ah,
                           'gain': 2.6, 'flicker': 0, 'power': hash1(i * 3.7)})
        fl = min(dep - 2, 34)
        fh = fl / 6
        sxs = 1 if i % 2 else -1
        wx = sxs * (w_in / 2 + wing)
        sq2 = KIT.quat_mul(xf.q, KIT.quat_axis((0, 1, 0), sxs * math.pi / 2))
        city_signs.append({'id': 'fut:' + str(i % len(KIT.FUTURIST)), 'pos': xf.p([wx + sxs * 0.12, rt['H'] * 0.3, -dep * 0.2]),
                           'quat': sq2, 'w': fl, 'h': fh, 'gain': 1.2, 'flicker': 0, 'power': hash1(i * 9.1)})
        # cables: two per tower from the inner face down to the anchor ring
        for k in (0, 1):
            ci = i * 2 + k
            e = _cable_ends_three(i, k)
            cable_list.append({'a': e['a'], 'b': e['b'], 's': hash1(ci * 1.7)})
            bx = KIT.make_xf(e['a'], yaw, rt['lean'], 0)            # a bracket where it meets the facade
            buf['frame'].box(bx, -0.3, -0.3, -0.7, 0.3, 0.3, 0.1, no_win)
    # ---- cables (one mesh): camera-facing ribbons, 10 segments each, set per frame by Geometry Nodes
    cables = _make_cables(K, cable_list, coll, root)
    # ---- the pillar of light: the quiet place seen from the city (gone when the camera is at the hole)
    col_mat, nb = KIT.new_material('uf_light_column', K)
    KIT._blended(col_mat)
    P3, cam = nb.pos3(), nb.cam3()
    vv = nb.normalize(cam - P3)
    face = nb.abs(nb.dot(nb.normalize(nb.comb(P3.x, 0.0, P3.z)), nb.comb(vv.x, 0.0, vv.z)))
    y = P3.y
    n = nb.tex(K.tex['noise'], nb.atan2(P3.z, P3.x) * 0.8, y / 60.0 + nb.U('time') * 0.25)[0].x
    cam_r = nb.length(nb.xz(cam))
    inside = nb.smoothstep(45.0, 100.0, cam_r)
    fall = nb.exp(-nb.max(y - STREET_Y, 0.0) / 260.0) * nb.smoothstep(0.0, STREET_Y + 2, y)
    top_fade = nb.smoothstep(330.0, 230.0, y)
    f, _ = nb.fog()
    KIT.out_additive(nb, nb.mul((0.75, 0.82, 0.95), face * face * fall * top_fade * (n * 0.6 + 0.4) * 0.24 *
                                nb.U('column') * inside * nb.one_minus(f)))
    segs = 48
    Pc, Fc = [], []
    for i in range(segs + 1):
        a = 2 * math.pi * i / segs
        Pc += [[math.sin(a) * 22, 330, math.cos(a) * 22], [math.sin(a) * HOLE['floor_r'], 0, math.cos(a) * HOLE['floor_r']]]
    for i in range(segs):
        Fc.append([2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2])
    column = obj('uf_light_column', KIT.make_mesh('uf_light_column', np.asarray(Pc), Fc, smooth=True, made=K.made), col_mat)
    column.visible_shadow = False
    KIT.audit_flags(column)
    # ---- merged meshes
    meshes = {}
    for nm, key, mat in (('uf_hole_concrete', 'concrete', HM['concrete']), ('uf_hole_metal', 'metal', HM['metal']),
                         ('uf_hole_frames', 'frame', HM['frame']), ('uf_hole_strips', 'strip', HM['strip']),
                         ('uf_hole_marble', 'marble', HM['marble'])):
        meshes[nm] = obj(nm, buf[key].build(nm, K.made), mat)
    # ---- light on her: the ring from below, the screens from above (retint with parts['lights'][*].data.color)
    light_scale = float(opts.get('light_scale', 1.0))
    chest = np.array([0.0, 1.3, 0.0])
    lights = {}

    def point(name, col, cd, dist, decay, p3):
        """three's PointLight(colour, candela, distance, decay) as a Blender point: the same irradiance at her chest
        (Blender's falloff is inverse-square; three's distance window and decay folded in there), cut off at
        distance."""
        d = max(0.3, float(np.linalg.norm(np.asarray(p3) - chest)))
        win = max(0.0, 1 - (d / dist) ** 4) ** 2
        ld = bpy.data.lights.new(name, 'POINT')
        K.made.add(ld)
        ld.color = KIT.srgb_lin(col)
        ld.energy = 4 * math.pi * cd * d ** (2 - decay) * win * light_scale
        ld.use_custom_distance = True
        ld.cutoff_distance = dist
        ld.use_shadow = False
        ld.shadow_soft_size = 0.05
        ob = KIT.new_object(name, ld, coll, parent=root, made=K.made)
        ob.location = KIT.to_blender(p3)
        return ob
    lights['ring'] = point('uf_hole_light_ring', 0xfff1dc, 2.6, 6.5, 1.6, [0, 0.25, 0])
    scol = [0xff3a4a, 0x29e7ff, 0xffc23d, 0xff4fd8]
    for k, ri in enumerate((0, 3, 6, 9)):
        # just in front of its screen: the highlight on the wet marble lands where the screen reflects
        c3 = KIT.from_blender(billboards[ri]['center'])
        lights[f'screen{k}'] = point(f'uf_hole_light_screen{k}', scol[k], 1500, 130, 1.8, [v * 0.86 for v in c3])
    # neon kickers behind her (the cyan and magenta ticker light): they rim the black tuta against the dark well
    lights['kickL'] = point('uf_hole_light_kickL', 0x29e7ff, 16, 6, 1.7, [-1.5, 0.9, -2.7])
    lights['kickR'] = point('uf_hole_light_kickR', 0xff4fd8, 16, 6, 1.7, [1.5, 1.05, -2.8])
    # the hole's surfaces take only the quiet ring's light; the screen lights and the neon kickers light the performer
    # only (on wet marble a point light's highlight reads as a stray lamp; the screens' colour reaches the floor via the
    # light map). Their receiver collection includes `her` and EXCLUDES the set's own collections (the hole's, and the
    # city's around it): light linking ignores an include that holds no objects, so with nobody in `her` yet the
    # include alone would let 1500 cd screen lights wash the towers and the street; three's lightsNode never did.
    from .city import light_only, exclude_from_light
    light_only(lights['ring'], [coll, her], K.made)
    set_colls = [coll] + ([opts['collection']] if opts.get('with_city') and opts.get('collection') is not None else [])
    for k in ('screen0', 'screen1', 'screen2', 'screen3', 'kickL', 'kickR'):
        light_only(lights[k], [her], K.made)
        for c in set_colls:
            exclude_from_light(lights[k], c, K.made)

    def set_lights(list_):
        """The hole's surfaces see only these lights, the quiet ring and the World (the hemisphere): every other scene
        light excludes the hole (light linking). Call it again after adding lights to the scene."""
        from .city import restrict_lights
        restrict_lights(scene, coll, list_, K.made)
    # as the engine's setLights([ring, ...cityLights, hemi]): the city's lights (city_lights: its sky-glow inside the
    # city; none standalone, where the hemisphere is the World) and nothing already in the scene before the build
    city_lights = list(opts.get('city_lights') or opts.get('cityLights') or [])
    set_lights(city_lights)
    # ---- standalone extras: its own sky, rain, clouds, signs and street disc so the hole renders by itself
    extras = None
    atlas = opts.get('atlas')
    if standalone:
        atlas = atlas or KIT.make_sign_atlas(K)
        sky = KIT.make_sky(K, env_intensity=opts.get('env_intensity'))
        rain = KIT.make_rain(K, coll, {'count': opts.get('rain_count', 16000)}, parent=root)
        clouds = KIT.make_clouds(K, coll, parent=root)
        signs = KIT.make_signs_mesh(K, atlas, city_signs, coll, parent=root)
        P, Q, uv = ring_geometry(HOLE['rim_r'], 900, 96, 8, STREET_Y)
        street = obj('uf_street', KIT.make_mesh('uf_street', P, Q, uv=uv, made=K.made), M['ground'])
        extras = {'sky': sky, 'rain': rain, 'clouds': clouds, 'signs': signs, 'street': street}

    def apply_atmosphere(sc=None, objects=None):
        """The scene's World (the kit's night); objects (a performer, props) take the haze as three's scene.fogNode
        gave it to every material (KIT.fog_objects, see-through materials keeping their alpha)."""
        sc = sc or scene
        if K.world is not None:
            sc.world = K.world
        if objects:
            KIT.fog_objects(K, objects)
        return sc

    from .city import make_set_focal, animate_set, make_set_cameras, apply_state
    set_focal = make_set_focal(U)

    def update(t, state=None, frame=None, ctx=None):
        """Standalone only (inside the city, the city's update owns the clock): the clock, the rain's velocity and
        any control the state names (as the city's update). ctx: the harness ctx (from now on, keys go through
        ctx.key)."""
        if ctx is not None:
            U.keyer = ctx.key
        if not standalone:
            return
        state = state or {}
        U['time'] = t
        apply_state(U, state, frame)
        cv = state.get('cam_vel', state.get('camVel'))
        if cv is not None:
            U['cam_vel'] = cv
        if frame is not None:
            U.key('time', frame)
            if cv is not None:
                U.key('cam_vel', frame)

    def dispose():
        if standalone:
            if K._fog is not None:
                KIT.unfog_group(K._fog)              # your own objects' materials, before the haze group goes
            K.made.dispose()
    cams = {}
    for nme in HOLE_CAMS:
        c = hole_cam(nme, HOLE_CAM_DUR.get(nme, 8) * 0.5)
        cams[nme] = {'pos': c['pos'], 'target': c['target'], 'fov': c['fov']}
    parts = KIT.SetDict({'kit': K, 'uniforms': U, 'set_lights': set_lights, 'materials': HM, 'billboards': billboards,
                         'tickers': tickers, 'cables': cables, 'column': column, 'ring': ring, 'lips': lips,
                         'floor': floor, 'lights': KIT.SetDict(lights), 'city_signs': city_signs, 'head': HEAD,
                         'rim': RIM, 'her': her, 'arms': arms, 'meshes': meshes, 'fog_node': K.fog_group(),
                         'apply_atmosphere': apply_atmosphere, 'set_focal': set_focal, 'collection': coll,
                         'extras': extras, 'atlas': atlas})

    def animate(state=None, frames=None, t0=0.0, fps=None, camera=None):
        """Key the hole's moving parts on your own clock, as the city's animate (city.animate_set): the clock (the
        screens' flicker, the tickers, the cables' pulses, the rain), state(t)'s controls (power, quiet, screens,
        column, cable ...; 'focal' a point, e.g. chest(), or an object to follow) and the rain along the camera.
        Returns (first, last)."""
        return animate_set(K, scene, state, frames, t0, fps, camera)

    def make_cameras(frames=None, t0=0.0, fps=None, scene_=None, shots=None):
        """The hole's camera moves keyed into the .blend: shots [(name, first frame, last frame)] (hole_cam's names,
        each stretched over its frames), one camera each, bound to timeline markers (ctx.cut with a ctx). Default:
        all eight moves back to back at their own lengths from frames[0] (default the scene's frame_start). Returns
        {name: camera}."""
        sc = scene_ or scene
        fps_ = float(fps or sc.render.fps / sc.render.fps_base)
        if not shots:
            f = list(frames)[0] if frames is not None else sc.frame_start
            shots = []
            for nm in HOLE_CAMS:
                n = int(round(HOLE_CAM_DUR[nm] * fps_))
                shots.append((nm, f, f + n))
                f += n + 1
        return make_set_cameras(K, sc, ctx, None, t0, fps_, shots)
    return KIT.SetDict(group=root, collection=coll, parts=parts, update=update, dispose=dispose, cams=cams,
                       animate=animate, make_cameras=make_cameras)


def chest():
    """The chest of a performer on the mark (Blender axes): 1.3 m at scale 1, scaled with HEAD (HEAD[2] = 1.55 * 0.87
    for a smaller performer). A natural place for Crali's focal light in the hole: set_focal(H.chest())."""
    return [0.0, 0.0, 1.3 * HEAD[2] / 1.55]


def _make_cables(K, cable_list, coll, root, name='uf_hole_cables'):
    """24 ribbons that face the camera, at least ~1 px wide (max(0.022, distance x 0.0007)): the ends, the position
    along (cP.x) and the side (cP.y) are point attributes; Geometry Nodes places every vertex per frame from the
    scene's active camera (the engine's vertex stage)."""
    SEG = 10
    cA, cB, cP, cS, F = [], [], [], [], []
    for c in cable_list:
        base = len(cP)
        a, b = KIT.to_blender(c['a']), KIT.to_blender(c['b'])
        for j in range(SEG + 1):
            for sd in (-1, 1):
                cP.append([j / SEG, sd, 0.0])
                cA.append(a)
                cB.append(b)
                cS.append(c['s'])
        for j in range(SEG):
            k = base + j * 2
            F.append([k, k + 1, k + 3, k + 2])
    n = len(cP)
    P3 = np.zeros((n, 3))
    me = KIT.make_mesh(name, P3, F, attrs={'cA': (np.asarray(cA), 'FLOAT_VECTOR'), 'cB': (np.asarray(cB), 'FLOAT_VECTOR'),
                                            'cP': (np.asarray(cP), 'FLOAT_VECTOR'), 'cS': (np.asarray(cS), 'FLOAT')}, made=K.made)
    me.materials.append(cable_material(K))
    ob = KIT.new_object(name, me, coll, parent=root, made=K.made)
    ob['assembly'] = 'uf_hole'
    ob.visible_shadow = False
    KIT.audit_flags(ob, support=False, camera=False)
    g = KIT.GN(name + '_gn', K)
    nb = g.nb
    a = g.named('cA', 'FLOAT_VECTOR')
    b = g.named('cB', 'FLOAT_VECTOR')
    cp = g.named('cP', 'FLOAT_VECTOR')
    cam = g.camera_location()
    p = nb.mix(a, b, cp.x)
    d = nb.normalize(b - a)
    to_c = nb.normalize(cam - p)
    side = nb.normalize(nb.cross(d, to_c))
    w = nb.max(0.022, nb.length(cam - p) * 0.0007)
    sp = nb.new('GeometryNodeSetPosition')
    nb.links.new(g.gin.outputs['Geometry'], sp.inputs['Geometry'])
    nb.feed(p + side * (cp.y * w), sp.inputs['Position'])
    nb.links.new(sp.outputs[0], g.gout.inputs['Geometry'])
    g.modifier(ob, K)
    return ob


# ------------------------------------------------------------------------------------------------ the camera moves
# hole_cam(name, t, opts) -> {pos, target, fov, roll, up}, t = seconds since the shot began (clamped to its length;
# opts['dur'] stretches it). Made for the choruses; framed for a ~2 m performer on the mark facing three's +Z (face at
# ~1.55 m).
HOLE_CAM_DUR = {'spiral': 12, 'riseUp': 12, 'closeSing': 10, 'orbit': 16, 'low': 10, 'nadir': 10, 'enter': 8, 'screens': 10}
HOLE_CAMS = list(HOLE_CAM_DUR)
HOLE_CAM_ALIASES = {'rise_up': 'riseUp', 'close_sing': 'closeSing'}


def hole_cam_three(name, t, opts=None):
    """holeCam in three's axes, exactly as hole.js."""
    opts = opts or {}
    name = HOLE_CAM_ALIASES.get(name, name)
    dur = opts.get('dur') or HOLE_CAM_DUR.get(name) or 10
    u = clamp01(t / dur)
    H = _head3()
    deg = D2R
    if name == 'spiral':                 # a Crali dive down the well toward her face, circling 540 degrees, rolling
        s = smoother(u)
        y = lerp(150, 2.25, math.pow(s, 0.8))
        R = min(20, 1.5 + 0.36 * y)      # always inside the cone of cables (no crossings)
        a = (100 - 540 * s) * deg
        pos = [math.cos(a) * R, y, math.sin(a) * R]
        tgt = [0, lerp(0.6, 1.45, s), 0]
        kU = smooth((s - 0.55) / 0.4)
        up = [-math.sin(a) * (1 - kU), 0.35 + kU * 3, math.cos(a) * (1 - kU)]
        return {'pos': pos, 'target': tgt, 'fov': lerp(68, 40, s), 'roll': math.sin(s * math.pi * 2) * 10 * deg * (1 - kU),
                'up': up}
    if name == 'riseUp':                 # from her face straight up the well: she becomes the vanishing point
        s = smoother(u)
        y = lerp(2.6, 190, math.pow(s, 1.6))
        off = lerp(1.25, 0.6, s)
        return {'pos': [0.18, y, off], 'target': [0, lerp(1.4, 0.9, s), 0], 'fov': lerp(46, 62, s), 'roll': s * 50 * deg,
                'up': [0, 0, -1]}
    if name == 'closeSing':              # the singing close-up, a slow arc in front of her; the screens + crown behind
        s = smooth(u)
        a = (90 + lerp(-14, 14, s)) * deg
        R = lerp(2.45, 2.15, s)
        return {'pos': [math.cos(a) * R, 1.5, math.sin(a) * R], 'target': [0, 1.48, 0], 'fov': 36, 'roll': 0}
    if name == 'orbit':                  # a full circle at 8.5 m, slightly above her eyes
        a = (90 + 360 * u) * deg
        return {'pos': [math.cos(a) * 8.5, 3.0, math.sin(a) * 8.5], 'target': [0, 1.25, 0], 'fov': 44, 'roll': 0}
    if name == 'low':                    # low, looking up past her at the towers leaning in and the screens aimed down
        s = smooth(u)
        return {'pos': [0.0, lerp(0.38, 0.5, s), lerp(2.85, 2.6, s)], 'target': [0, lerp(2.4, 3.2, s), 0], 'fov': 62,
                'roll': lerp(-4, 3, s) * deg}
    if name == 'nadir':                  # straight down on her from the well: the floor's lines, the anchor ring, cables
        s = smooth(u)
        y = lerp(70, 13, s)
        a = (s * 120) * deg
        return {'pos': [0.02, y, 0.02], 'target': [0, 0, 0], 'fov': lerp(58, 46, s), 'roll': 0,
                'up': [math.sin(a), 0, -math.cos(a)]}
    if name == 'screens':                # from beside her, a slow tilt up across the screens aimed at her
        s = smooth(u)
        a = 250 * deg
        return {'pos': [math.cos(a) * 1.6, 1.3, math.sin(a) * 1.6],
                'target': [math.cos(a + math.pi) * 30, lerp(4, 40, s), math.sin(a + math.pi) * 30], 'fov': 55, 'roll': 0}
    if name == 'enter':                  # from the dive's last frame (avenue 45, 118 m out) over the rim, down the well
        s = smoother(u)
        r = lerp(118, 9, s)
        yy = 4.5 + (STREET_Y + 10.5) * smooth((r - 6) / 44)
        th = 45 * deg + smooth((s - 0.66) / 0.34) * 30 * deg
        pos = [math.cos(th) * r, yy, math.sin(th) * r]
        tgt = [0, lerp(STREET_Y + 26, 1.4, smooth((s - 0.25) / 0.75)), 0]
        return {'pos': pos, 'target': tgt, 'fov': lerp(56, 42, s), 'roll': math.sin(s * math.pi) * -6 * deg}
    return hole_cam_three('closeSing', t, opts)


def hole_cam(name, t, opts=None):
    """One of the hole's camera moves, its pose t seconds into it, Blender axes: {'pos', 'target', 'fov', 'roll', 'up'?}. Names:
    spiral, riseUp, closeSing, orbit, low, nadir, screens, enter (rise_up / close_sing also accepted)."""
    return KIT.pose_to_blender(hole_cam_three(name, t, opts))


def key_hole_cam(camera, name, *, frame_start=1, fps=24.0, dur=None, step=1, keyer=None):
    """Key one of the hole's camera moves on a camera (every frame, LINEAR; through keyer, the harness's ctx.key).
    dur stretches the shot (hole_cam's opts['dur']). Returns the frame range."""
    nm = HOLE_CAM_ALIASES.get(name, name)
    dur = dur or HOLE_CAM_DUR.get(nm, 10)
    n = int(round(dur * fps))
    frames = list(range(frame_start, frame_start + n + 1, step))
    if frames[-1] != frame_start + n:
        frames.append(frame_start + n)
    for f in frames:
        apply_cam(camera, hole_cam(nm, (f - frame_start) / fps, {'dur': dur}), frame=f, keyer=keyer)
    return frames[0], frames[-1]
