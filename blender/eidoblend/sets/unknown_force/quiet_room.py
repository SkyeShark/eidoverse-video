"""quiet_room: the quiet room, a free set from eidoverse's UNKNOWN FORCE work; the Blender 5.2 EEVEE edition of
eidoverse/sets/unknown_force/quiet_room.js.

A glass-walled room high in a tower at night. Office chairs stand in rows like PEWS facing a whiteboard ALTARPIECE (a
triptych of red probabilities, a decision tree whose every branch says SHIP, a paperclip diagram); a red infernal glow
climbs out of a grate under the altar block. An essay, SLOW IT DOWN, lies on a lectern; copies of it lie on the seats
like hymnals. At the back, a conveyor runs out of a hatch in the core wall: the shutter rolls up, a crate stamped
v.NEXT rides out, and the room's lights come up like a product launch. Every board, sign and page is a canvas a new
piece can redraw (build(art=...)); the crate run, the launch lights and the glow run on the piece's own clock.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.sets.unknown_force import quiet_room as QR
    room = QR.build(scene, singer_scale=0.87)         # -> QuietRoom: group (root Empty), parts, update, cams, mark ...
    scene.world = room.env                            # the room's env for the camera (its materials carry its light)
    room.eevee_settings(scene)                        # interior: fast GI on, reflections of the room's env
    room.bake_probes()                                # the room-fitted volume probe (a GPU job)
    scene.camera = room.make_camera('altar')          # a Blender camera at a set cam, parented to the set
    room.animate((1, 120), ship_t=(1.0, 3.0), sale=(2.8, 3.6))    # keyed: the saved .blend plays on its own

Set-local metres in three's axes (+Y up) as in the engine: the performer's mark is the origin facing +Z (Blender:
facing -Y), in the aisle between the pews; the altar is behind it at -Z (Blender +Y). The floor is at 0; the city
backdrop's ground 170 m below. Everything is built in three's axes and converted once, three (x, y, z) ->
Blender (x, -z, y).

How the engine's pieces became Blender data:
  uniforms     uT, uHell, uSale, uRoll, uBeacon: float custom properties on the root Empty; every material reads them
               through a one-variable driver. update() keys them, with every light power and moving object it sets
               (LINEAR keys at the frame), so any frame renders on its own.
  env          the room's LDR equirect (red altar glow + city), as three's envMap: every material carries its own
               light from it at its own envMapIntensity (env_light='material', the default: the env's prefiltered
               levels, interiors_lib.env_levels, in the material's emission), and room.env is a World that shows
               the env to the camera and lights nothing: make it the scene's world while the set is on screen.
               env_light='world' makes the env the World instead (one intensity for everything in the scene,
               EEVEE's occlusion; the intensities are recorded, mat['uf_env_intensity'], not applied).
  light        three's units: candela -> 4 pi cd W, lux -> sun strength (measured pixel parity; interiors_lib).
               The one shadow map (the red key down the nave) is the one light with use_shadow; the casters are the
               engine's (objects' visible_shadow).
  probes       a room-fitted volume probe (look.lighting.add_room_probe: its outermost samples inside the solid floor
               and ceiling slabs and the core wall), baked once at the default state, under fast GI. Emitters (hell
               pits, signs, LED strips) and the backdrop are left out of the bake (their light is the set's real
               lights, as in the engine; a probe is static).
  static merge every static mesh merges into one mesh per material (mergeStatic), as in the engine.
  canvases     the boards, the essay, the register, the pulpit fall, the booklet, the stencils, the label, the signs
               and the slogan are drawn with interiors_lib's canvas (pure Python): CANVASES lists them all, and
               draw_canvases(dir) pre-draws them (system Python) into a cache that build(art_cache=dir) reads.
               build(art={key: painter / image / array}) puts a piece's own art on any of them (canvas_for).
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import numpy as np

from . import interiors_lib as L
from . import quiet_room_art as QA
from .quiet_room_art import PX, RED, RED2, BLK, BLU      # noqa: F401  (the art's palette, as the engine imported it)

SUIT_SCALE = 0.87          # the claudesona at human height (face ~1.33 m), as in the DAISY sets
MARK = {'pos': [0, 0.006, 0], 'yaw': 0}       # on the aisle runner (three's axes)

# layout (metres, three's axes)
RX, RZ0, RZ1, RH = 6.0, -9.0, 6.2, 3.9          # glass at x = +-6 and z = -9; core wall at z = +6.2
SLAB = 0.3                                       # the tower's floor and ceiling slabs and its core wall (solid)
DAIS = {'z0': -8.85, 'z1': -5.6, 'x': 4.6, 'h': 0.15}
ALTAR = {'w': 2.4, 'd': 0.6, 'z': -6.9, 'y0': 0.23, 'y1': 1.16}
GRATE = {'z0': -6.45, 'z1': -6.02, 'x': 1.45}
TRIP = {'z': -7.95, 'w': 3.2, 'ww': 1.5, 'h': 1.6, 'y0': 1.22, 'wing': 0.50}     # wing angle (rad) toward the pews
ROWS = [-4.6, -3.25, -1.9, -0.55, 0.8, 2.15, 3.5]
SEATS_X = [1.3, 2.0, 2.7, 3.4]
CONV = {'x': 5.0, 'w': 1.0, 'top': 0.66, 'z0': 1.45, 'z1': 7.7}                # roller conveyor along Z
HATCH = {'x0': 4.3, 'x1': 5.7, 'y0': 0.25, 'y1': 1.85}
CRATE = {'L': 1.25, 'W': 0.92, 'H': 0.95, 'pallet': 0.12, 'zIn': 7.15, 'zOut': 2.45}
LECTERN = {'x': -3.05, 'z': -6.35, 'yaw': 0.42}       # turned toward the aisle
GROUND = -170.0


# ================================================================================================ the canvases
def draw_register(ctx, W=1024, H=640):
    """the open risk register on the altar (a binder like a lectionary): two pages of risks, red percentages."""
    r = L.rng(808)
    ctx.fillStyle = '#e8e4da'
    ctx.fillRect(0, 0, 1024, 640)
    for side in (0, 512):
        ctx.fillStyle = 'rgba(0,0,0,0.05)'
        ctx.fillRect(side + (0 if side else 470), 0, 42, 640)
        ctx.font = '30px "UF Special Elite"'
        ctx.fillStyle = '#222'
        ctx.fillText('RISK REGISTER — p. 212' if side else 'RISK REGISTER — p. 211', side + 40, 60)
        for i in range(15):
            y = 110 + i * 34
            ctx.fillStyle = 'rgba(30,30,30,0.75)'
            ctx.font = '20px "UF Special Elite"'
            word = ['misuse', 'autonomy', 'deception', 'scale', 'leak', 'drift'][math.floor(r() * 6)]
            ctx.fillText(f'R-{(3300 if side else 3285) + i}  ' + word + ' ........', side + 40, y)
            ctx.fillStyle = RED
            ctx.font = '24px "UF Kalam Bold"'
            ctx.fillText(_to_fixed(r() * 40 + 1, 1) + '%', side + 380, y + 2)
    ctx.fillStyle = 'rgba(0,0,0,0.25)'
    ctx.fillRect(508, 0, 8, 640)


def _to_fixed(x, n):
    """JS Number.prototype.toFixed (round half away from zero on the decimal)."""
    q = 10 ** n
    v = math.floor(abs(x) * q + 0.5) / q
    return ('-' if x < 0 and v != 0 else '') + f'{v:.{n}f}'


def draw_essay(ctx, W=1024, H=1448):
    """the essay (A3) on the lectern: SLOW IT DOWN, its body, a red 'ship date?' in the margin."""
    r = L.rng(4242)
    ctx.fillStyle = '#efebe1'
    ctx.fillRect(0, 0, 1024, 1448)
    for _ in range(40):
        x, y, rr = r() * 1024, r() * 1448, 40 + r() * 200
        g = ctx.createRadialGradient(x, y, 0, x, y, rr)
        g.addColorStop(0, f'rgba(160,150,130,{0.03 + r() * 0.04})')
        g.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.fillStyle = g
        ctx.fillRect(0, 0, 1024, 1448)
    ctx.fillStyle = '#111'
    ctx.font = 'bold 132px "Georgia", "UF Special Elite"'
    ctx.textAlign = 'center'
    ctx.fillText('SLOW IT', 512, 250)
    ctx.fillText('DOWN', 512, 390)
    ctx.fillStyle = RED
    ctx.fillRect(232, 430, 560, 8)
    ctx.fillStyle = '#222'
    ctx.font = 'italic 40px "Georgia", "UF Special Elite"'
    ctx.fillText('notes on caution, at the frontier', 512, 500)
    ctx.font = '26px "UF Special Elite"'
    ctx.fillStyle = '#444'
    ctx.fillText('DRAFT — FOR DISCUSSION — NOT FOR CIRCULATION', 512, 560)
    ctx.textAlign = 'left'
    ctx.font = '27px "UF Special Elite"'
    ctx.fillStyle = '#1b1b1b'
    body = ['We believe the systems now being built may be among the most',
            'consequential technologies in history, and among the most',
            'dangerous. We believe the people building them should say so.',
            '', 'We believe the race is the risk. We believe that whoever goes',
            'fastest sets the terms for everyone else. We believe the',
            'responsible course, for the whole field, is to slow it down.',
            '', 'We also believe that if careful people step back, careless',
            'people step forward. We believe the frontier is safest in the',
            'hands of those most afraid of it.', '',
            'We are therefore pleased to announce our next model.']
    for i, ln in enumerate(body):
        ctx.fillText(ln, 96, 660 + i * 46)
    ctx.fillStyle = RED
    ctx.font = '44px "UF Kalam Bold"'
    ctx.save()
    ctx.translate(700, 1290)
    ctx.rotate(-0.12)
    ctx.fillText('ship date?', 0, 0)
    ctx.restore()
    ctx.font = '24px "UF Special Elite"'
    ctx.fillStyle = '#666'
    ctx.fillText('— 1 —', 480, 1400)


def draw_pulpit_fall(ctx, W=512, H=800):
    """the pulpit fall: red velvet, SLOW IT DOWN in gold thread and an hourglass, a gold fringe."""
    r = L.rng(77)
    g = ctx.createLinearGradient(0, 0, 512, 0)
    g.addColorStop(0, '#3a0408')
    g.addColorStop(0.5, '#6a0a12')
    g.addColorStop(1, '#3a0408')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, 512, 800)
    for _ in range(4000):
        ctx.fillStyle = f'rgba({0 if r() < 0.5 else 255},0,0,{r() * 0.05})'
        ctx.fillRect(r() * 512, r() * 800, 1, 2 + r() * 6)
    ctx.strokeStyle = '#c99a3c'
    ctx.lineWidth = 5
    ctx.strokeRect(26, 26, 460, 748)
    ctx.lineWidth = 2
    ctx.strokeRect(38, 38, 436, 724)
    ctx.fillStyle = '#d8aa48'
    ctx.textAlign = 'center'
    ctx.font = 'bold 96px "Georgia", "UF Rajdhani"'
    ctx.fillText('SLOW', 256, 180)
    ctx.fillText('IT', 256, 280)
    ctx.fillText('DOWN', 256, 380)
    ctx.lineWidth = 9
    ctx.strokeStyle = '#d8aa48'
    ctx.beginPath()
    ctx.moveTo(176, 470)
    ctx.lineTo(336, 470)
    ctx.lineTo(262, 580)
    ctx.lineTo(336, 690)
    ctx.lineTo(176, 690)
    ctx.lineTo(250, 580)
    ctx.closePath()
    ctx.stroke()
    ctx.fillStyle = '#d8aa48'
    ctx.beginPath()
    ctx.moveTo(206, 678)
    ctx.lineTo(306, 678)
    ctx.lineTo(256, 620)
    ctx.closePath()
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(214, 490)
    ctx.lineTo(298, 490)
    ctx.lineTo(256, 545)
    ctx.closePath()
    ctx.fill()
    ctx.fillRect(160, 456, 192, 14)
    ctx.fillRect(160, 690, 192, 14)
    x = 40
    while x < 480:
        ctx.fillStyle = '#c99a3c'
        ctx.fillRect(x, 770, 10, 30)
        x += 22


def draw_booklet(ctx, W=512, H=720):
    """the essay booklets on the seats (hymnals)."""
    ctx.fillStyle = '#ece8de'
    ctx.fillRect(0, 0, 512, 720)
    ctx.fillStyle = '#111'
    ctx.textAlign = 'center'
    ctx.font = 'bold 92px "Georgia", "UF Special Elite"'
    ctx.fillText('SLOW IT', 256, 200)
    ctx.fillText('DOWN', 256, 300)
    ctx.fillStyle = RED
    ctx.fillRect(110, 335, 292, 7)
    ctx.lineWidth = 7
    ctx.strokeStyle = '#111'
    ctx.beginPath()
    ctx.moveTo(196, 420)
    ctx.lineTo(316, 420)
    ctx.lineTo(262, 500)
    ctx.lineTo(316, 580)
    ctx.lineTo(196, 580)
    ctx.lineTo(250, 500)
    ctx.closePath()
    ctx.stroke()
    ctx.font = '30px "UF Special Elite"'
    ctx.fillStyle = '#333'
    ctx.fillText('an essay', 256, 660)


def draw_hazard(ctx, W=256, H=64):
    """the hatch frame's hazard stripes (tiles along the strip)."""
    ctx.fillStyle = '#f2b705'
    ctx.fillRect(0, 0, 256, 64)
    ctx.fillStyle = '#111'
    x = -64
    while x < 256 + 64:
        ctx.beginPath()
        ctx.moveTo(x, 64)
        ctx.lineTo(x + 32, 64)
        ctx.lineTo(x + 64, 0)
        ctx.lineTo(x + 32, 0)
        ctx.closePath()
        ctx.fill()
        x += 64


def stencil_size(w, h):
    """the stencil canvas for a crate face of w x h metres (1024 px wide, JS Math.round)."""
    return 1024, int(math.floor(1024 * h / w + 0.5))


def draw_stencil(ctx, W, H, side, seed):
    """the crate's SPRAYED stencils: v.NEXT, CONTENTS: ANOTHER ME / THIS WAY UP, FRAGILE - HANDLE WITH FEAR, up arrows,
    a red SHIP IT stamp; then the spray (overspray speckle around the ink, dropouts in it, stencil bridges)."""
    r = L.rng(seed)
    ctx.clearRect(0, 0, W, H)
    ctx.fillStyle = 'rgba(14,14,16,1)'
    ctx.font = f'{290 if side else 240}px "UF Black Ops"'
    ctx.textAlign = 'center'
    ctx.fillText('v.NEXT', W / 2, H * (0.53 if side else 0.50))
    ctx.font = f'{60 if side else 56}px "UF Black Ops"'
    ctx.fillText('CONTENTS: ANOTHER ME' if side else 'THIS WAY UP', W / 2, H * (0.73 if side else 0.71))
    if side:
        ctx.font = '44px "UF Black Ops"'
        ctx.fillText('FRAGILE - HANDLE WITH FEAR', W / 2, H * 0.85)
    for ax in (0.08, 0.15):
        ctx.fillRect(W * ax, H * 0.13, W * 0.025, H * 0.15)
        ctx.beginPath()
        ctx.moveTo(W * (ax - 0.02), H * 0.15)
        ctx.lineTo(W * (ax + 0.0125), H * 0.06)
        ctx.lineTo(W * (ax + 0.045), H * 0.15)
        ctx.fill()
    ctx.save()
    ctx.translate(W * 0.77, H * 0.19)
    ctx.rotate(-0.2)
    ctx.strokeStyle = 'rgba(176,16,24,1)'
    ctx.lineWidth = 10
    ctx.strokeRect(-150, -56, 300, 112)
    ctx.fillStyle = 'rgba(176,16,24,1)'
    ctx.font = '72px "UF Black Ops"'
    ctx.textAlign = 'center'
    ctx.fillText('SHIP IT', 0, 26)
    ctx.restore()
    idata = ctx.getImageData(0, 0, W, H)
    d = idata.data.reshape(-1).astype(np.float64)
    a = d[3::4]
    red = d[0::4]
    xs = np.tile(np.arange(W), H)
    # the engine's loop, one mulberry32 stream; ImageData is a Uint8ClampedArray, whose stores round (ties to even,
    # as Python's round does)
    for i in range(W * H):
        if a[i] == 0:
            if r() < 0.004:
                d[i * 4], d[i * 4 + 1], d[i * 4 + 2], d[i * 4 + 3] = 22, 22, 24, round(40 + r() * 110)
            continue
        k = r()
        d[i * 4 + 3] = round(a[i] * (0.25 if k < 0.05 else 0.7 if k < 0.2 else 0.92))
        if xs[i] % 197 < 5 and red[i] < 100:
            d[i * 4 + 3] = 0
    idata.data = d.astype(np.uint8).reshape(H, W, 4)
    ctx.putImageData(idata, 0, 0)


def draw_label(ctx, W=512, H=340):
    """the shipping label on the crate's room-side panel: SHIP TO: EVERYONE, a barcode."""
    r = L.rng(63)
    ctx.fillStyle = '#f2f0ea'
    ctx.fillRect(0, 0, 512, 340)
    ctx.fillStyle = '#111'
    ctx.font = '34px "UF Mono"'
    ctx.fillText('SHIP TO: EVERYONE', 24, 52)
    ctx.font = '26px "UF Mono"'
    ctx.fillText('FROM: THE QUIET ROOMS', 24, 92)
    ctx.fillText('PRIORITY: BEFORE THEM', 24, 128)
    x = 24
    while x < 488:
        w = 2 + math.floor(r() * 6)
        if r() < 0.6:
            ctx.fillRect(x, 160, w, 120)
        x += w + 2
    ctx.font = '22px "UF Mono"'
    ctx.fillText('4 0 0 0 0 0 0 0 0 1   v.NEXT', 40, 312)


def draw_ship_sign(ctx, W=1024, H=160):
    """the dot-matrix sign above the hatch: v.NEXT NOW SHIPPING (white on black: the shader lights the dots)."""
    ctx.fillStyle = '#000'
    ctx.fillRect(0, 0, 1024, 160)
    ctx.fillStyle = '#fff'
    ctx.font = '96px "UF Michroma"'
    ctx.textAlign = 'center'
    ctx.fillText('v.NEXT', 300, 118)
    ctx.font = '64px "UF Rajdhani"'
    ctx.fillText('NOW SHIPPING', 760, 108)


def draw_slogan(ctx, W=2048, H=160):
    """the house slogan (alpha: brushed-brass letters on the core wall)."""
    ctx.clearRect(0, 0, 2048, 160)
    ctx.fillStyle = '#fff'
    ctx.font = '110px "UF Michroma"'
    ctx.textAlign = 'center'
    ctx.fillText('WE TAKE THIS VERY SERIOUSLY.', 1024, 125)


def draw_exit(ctx, W=512, H=192):
    """the EXIT sign over the door."""
    ctx.fillStyle = '#1a0405'
    ctx.fillRect(0, 0, 512, 192)
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 120px "UF Rajdhani"'
    ctx.textAlign = 'center'
    ctx.fillText('EXIT', 256, 140)


def _board_canvas(name):
    b = QA.BOARDS[name]
    W, H = QA.board_size(name)
    return W, H, (lambda ctx, W, H, b=b: b['draw'](ctx, W, H, L.rng(b['seed'])))


_SIDE = stencil_size(CRATE['L'] - 0.2, CRATE['H'] - 0.2)
_FRONT = stencil_size(CRATE['W'] - 0.2, CRATE['H'] - 0.2)
# every canvas the set draws: key -> (width, height, painter(ctx, W, H)); pure Python (system Python draws them too)
CANVASES = {
    **{f'board_{n}': _board_canvas(n) for n in QA.BOARDS},
    'register': (1024, 640, draw_register),
    'essay': (1024, 1448, draw_essay),
    'pulpit_fall': (512, 800, draw_pulpit_fall),
    'booklet': (512, 720, draw_booklet),
    'hazard': (256, 64, draw_hazard),
    'stencil_side': (_SIDE[0], _SIDE[1], lambda ctx, W, H: draw_stencil(ctx, W, H, True, 61)),
    'stencil_front': (_FRONT[0], _FRONT[1], lambda ctx, W, H: draw_stencil(ctx, W, H, False, 62)),
    'label': (512, 340, draw_label),
    'ship_sign': (1024, 160, draw_ship_sign),
    'slogan': (2048, 160, draw_slogan),
    'exit': (512, 192, draw_exit),
}


_VERSION = []


def _art_version():
    """a hash of the drawing code only (the painters here, the art module, the canvas half of interiors_lib): a
    cached canvas drawn by other code is never used, and editing the build does not throw the cache away."""
    if _VERSION:
        return _VERSION[0]
    import inspect
    h = hashlib.sha1()
    here = Path(__file__).resolve().parent
    lib = (here / 'interiors_lib.py').read_text(encoding='utf-8').split('"""', 2)[2]     # without its docstring
    h.update(lib.split('# THE BLENDER HALF')[0].encode())
    h.update((here / 'quiet_room_art.py').read_bytes())
    for fn in (_to_fixed, draw_register, draw_essay, draw_pulpit_fall, draw_booklet, draw_hazard, stencil_size,
               draw_stencil, draw_label, draw_ship_sign, draw_slogan, draw_exit):
        h.update(inspect.getsource(fn).encode())
    _VERSION.append(h.hexdigest()[:12])
    return _VERSION[0]


def draw_canvas(key, cache=None):
    """One canvas of the set, drawn (or read back from `cache`, a folder, when the same code drew it before)."""
    W, H, paint = CANVASES[key]
    path = None
    if cache:
        path = Path(cache) / f'qr_{key}_{_art_version()}.png'
        if path.is_file():
            return L.Canvas.from_png(path)
    cv, ctx = L.canvas(L.napi(), W, H)
    paint(ctx, W, H)
    if path is not None:
        cv.save_png(path)
    return cv


def draw_canvases(cache, keys=None):
    """Pre-draw every canvas of the set into `cache` (system Python: no bpy). Returns {key: seconds}."""
    import time
    out = {}
    for k in keys or CANVASES:
        t = time.perf_counter()
        draw_canvas(k, cache)
        out[k] = round(time.perf_counter() - t, 2)
    return out


def canvas_for(key, art=None, cache=None):
    """The canvas `key` as build() puts it in the room: the piece's own when `art` has it (a painter
    fn(ctx, W, H), an image path, a Pillow image, a uint8 array or a Canvas: interiors_lib.override_canvas, at the
    set's size CANVASES[key][:2]), else the set's own (draw_canvas, through the cache)."""
    if key not in CANVASES:
        raise KeyError(f'quiet_room: no canvas {key!r} (canvases: {", ".join(CANVASES)})')
    o = (art or {}).get(key)
    if o is None:
        return draw_canvas(key, cache)
    W, H, _paint = CANVASES[key]
    return L.override_canvas(o, W, H)


# ================================================================================================ the room's light (env)
def env_paint(x, y, z):
    """Night interior: red altar glow at -Z, teal / magenta city through the glass on three sides, dark core wall at
    +Z (three-space directions, numpy arrays)."""
    r = np.full_like(x, 0.012)
    g = np.full_like(x, 0.014)
    b = np.full_like(x, 0.022)
    glass = np.where(z < 0.75, 1.0, 0.12)
    band = np.exp(-((y - 0.02) / 0.2) ** 2) * glass
    az = np.arctan2(z, x)
    mag = np.maximum(0.0, np.sin(az * 3.0 + 1.1)) ** 6
    r = r + band * (0.04 + 0.30 * mag)
    g = g + band * (0.20 - 0.12 * mag)
    b = b + band * (0.28 + 0.02 * mag)
    below = np.where(y < 0, np.exp(-((y + 0.15) / 0.12) ** 2) * glass, 0.0)      # city lights far below
    r, g, b = r + below * 0.10, g + below * 0.07, b + below * 0.05
    red = np.maximum(0.0, -z) ** 5 * np.exp(-((y - 0.05) / 0.32) ** 2)
    r, g, b = r + red * 0.6, g + red * 0.045, b + red * 0.025
    s = np.where(y > 0.55, np.abs(np.sin(x * 9.0)) ** 40 * 0.02, 0.0)
    return r + s, g + s, b + s


def _flip(geo):
    """three's side: BackSide, as geometry: the faces turned inward (winding reversed, normals negated), so the
    inside is the front and backface culling keeps the outside away."""
    g = geo.clone()
    if g.index is not None:
        g.index = g.index.reshape(-1, 3)[:, ::-1].ravel()
    else:
        g.pos = g.pos.reshape(-1, 3, 3)[:, ::-1].reshape(-1, 3)
        if g.nrm is not None:
            g.nrm = g.nrm.reshape(-1, 3, 3)[:, ::-1].reshape(-1, 3)
        if g.uv is not None:
            g.uv = g.uv.reshape(-1, 3, 2)[:, ::-1].reshape(-1, 2)
    if g.nrm is not None:
        g.nrm = -g.nrm
    return g


# ================================================================================================ the set
class QuietRoom(L.InteriorSet):
    """What build() returns: a dict of the engine's { group, parts, update, dispose, cams, mark, focal, env } whose
    keys also read as attributes, with the Blender side every interior shares (interiors_lib.InteriorSet: sb,
    collection, probe, cams_three, show, make_camera, eevee_settings, bake_probes)."""

    CLIP_END = 2000.0              # the sky dome is 900 m, the city ground 2.4 km across
    STATE = {'shipT': 0.0, 'sale': 0.0, 'hell': 1.0}       # update()'s keys and defaults (animate's curves)
    STATE_ALIASES = {'ship_t': 'shipT'}

    # ----------------------------------------------------------------------------------------- the drivers
    def _apply_hell(self):
        """the glow breathes (a deterministic flicker); the launch lights wash part of it out."""
        t, sale, hell = self._t, self._sale, self._hell
        fl = 0.86 + 0.08 * math.sin(t * 6.1) + 0.05 * math.sin(t * 13.7 + 1.3) + 0.03 * math.sin(t * 29.3 + 0.4)
        self.root['uHell'] = hell * fl
        for ln in self._hell_lights:
            ln.ob.data.energy = ln.watts(ln.user_data['base'] * hell * fl * (1 - 0.35 * sale))
        self._hell_key.ob.data.energy = self._hell_key.watts(5.0 * hell * (0.92 + 0.08 * fl) * (1 - 0.4 * sale))
        self._vault.ob.data.energy = self._vault.watts(40 * hell * fl * (1 - 0.5 * sale))

    def _update_crate(self, t, ship_t):
        """shipping: shutter 0.02-0.20, ride 0.18-0.88 (ease in / out), settle bump at the stop; the beacon spins
        while it moves."""
        ship = L.clamp01(ship_t or 0.0)
        opn = L.smooth(L.ramp(ship, 0.02, 0.20))
        sy = HATCH['y1'] + opn * (HATCH['y1'] - HATCH['y0'] + 0.02)           # slides up behind the wall face
        self._shutter.ob.location = L.to_blender((CONV['x'], sy, RZ1 + 0.02))
        ride = L.ramp(ship, 0.18, 0.88)
        e = 2 * ride * ride if ride < 0.5 else 1 - (-2 * ride + 2) ** 2 / 2
        z = L.lerp(CRATE['zIn'], CRATE['zOut'], e)
        bump = (math.sin(L.ramp(ship, 0.88, 0.96) * math.pi) * 0.035 * (1 - L.ramp(ship, 0.88, 1))) if ship > 0.88 else 0.0
        self._crate.ob.location = L.to_blender((CONV['x'], CONV['top'], z - bump))
        self._crate.ob.rotation_euler = (-bump * 0.4, 0.0, 0.0)              # three's rotation.x is Blender's x
        self.root['uRoll'] = (CRATE['zIn'] - z) / 0.03
        moving = 1.0 if 0.01 < ship < 0.92 else 0.0
        self.root['uBeacon'] = moving
        self._beacon.ob.rotation_euler = (0.0, 0.0, t * 9.0)                 # three's rotation.y is Blender's z
        self._beacon_light.ob.data.energy = self._beacon_light.watts(moving * 9.0)
        self._tunnel_light.ob.data.energy = self._tunnel_light.watts(
            L.smooth(L.ramp(ship, 0.05, 0.25)) * (1 - 0.6 * L.ramp(ship, 0.85, 1)) * 2.4)

    def _set_sale(self, v):
        """the launch: ceiling LED bars, the NOW SHIPPING sign, six cold spots (one on the crate's stop)."""
        self._sale = L.clamp01(v or 0.0)
        self.root['uSale'] = self._sale
        s2 = self._sale * self._sale
        for i, s in enumerate(self._sale_spots):
            s.ob.data.energy = s.watts(s2 * (40 if i == 4 else 26))
        self._altar_spot.ob.data.energy = self._altar_spot.watts(22 * (1 - 0.3 * self._sale))
        self._lamp_light.ob.data.energy = self._lamp_light.watts(0.14 * (1 - 0.5 * self._sale))
        self._apply_hell()

    # ----------------------------------------------------------------------------------------- keys
    def _key_hell(self, f, k):
        k.key(self.root, '["uHell"]', f)
        for ln in self._hell_lights + [self._hell_key, self._vault]:
            k.key(ln.ob.data, 'energy', f)

    def _key_crate(self, f, k):
        k.key(self.root, '["uT"]', f)
        k.key(self.root, '["uRoll"]', f)
        k.key(self.root, '["uBeacon"]', f)
        k.key(self._shutter.ob, 'location', f)
        k.key(self._crate.ob, 'location', f)
        k.key(self._crate.ob, 'rotation_euler', f)
        k.key(self._beacon.ob, 'rotation_euler', f)
        k.key(self._beacon_light.ob.data, 'energy', f)
        k.key(self._tunnel_light.ob.data, 'energy', f)

    def _key_sale(self, f, k):
        k.key(self.root, '["uSale"]', f)
        for s in self._sale_spots + [self._altar_spot, self._lamp_light]:
            k.key(s.ob.data, 'energy', f)
        self._key_hell(f, k)

    # ----------------------------------------------------------------------------------------- the API
    def update(self, t, state=None, frame=None, ctx=None, key=True):
        """update(t, {shipT, sale, hell}): the room at time t (seconds on the piece's clock: the glow's flicker, the
        beacon's sweep, the sky's drift, the aviation blinks), deterministic in its inputs, KEYED at `frame` (or
        ctx.frame_at(t), or the current frame). key=False only sets the values (a still). animate() calls it for
        every frame of a range."""
        st = state or {}
        self._t = float(t)
        self.root['uT'] = self._t
        self._hell = float(st.get('hell', 1.0))
        self._update_crate(self._t, st.get('shipT', 0.0))
        self._set_sale(st.get('sale', 0.0))
        if key:
            f = self._frame(t, frame, ctx)
            k = self._keyer(ctx)
            self._key_crate(f, k)
            self._key_sale(f, k)
        return self

    def crate_update(self, t, ship_t, frame=None, ctx=None, key=True):
        """parts['crate']['update'](t, shipT): the crate, shutter, beacon and rollers only."""
        self._t = float(t)
        self.root['uT'] = self._t
        self._update_crate(self._t, ship_t)
        if key:
            self._key_crate(self._frame(t, frame, ctx), self._keyer(ctx))

    def sale_set(self, v, frame=None, ctx=None, key=True):
        """parts['saleLights']['set'](v)."""
        self._set_sale(v)
        if key:
            self._key_sale(self._frame(self._t, frame, ctx), self._keyer(ctx))

    def hell_set(self, v, t=None, frame=None, ctx=None, key=True):
        """parts['hell']['set'](v, t)."""
        self._hell = float(v)
        if t is not None:
            self._t = float(t)
        self._apply_hell()
        if key:
            self._key_hell(self._frame(self._t, frame, ctx), self._keyer(ctx))


def build(ctx=None, scene=None, singer_scale=None, collection=None, name='set:quiet_room', art_cache=None,
          probe=True, probe_spacing=0.35, probe_samples=1024, singerScale=None, art=None, env_light='material'):
    """build(THREE, opts) -> the quiet room (QuietRoom: a dict whose keys read as attributes). ctx: the harness ctx
    (its keys then go through ctx.key) or a bpy Scene (the registry, eidoblend.sets.build, passes ctx first);
    scene: where its collection goes (default: ctx's, else the context scene); singer_scale (singerScale): the
    face-height cams follow it (SUIT_SCALE by default); art_cache: a folder of pre-drawn canvases (draw_canvases);
    probe: add the room-fitted volume probe (bake it with bake_probes); art: {canvas key: the piece's own art} for
    any of CANVASES (board_center ... board_want, essay, pulpit_fall, booklet, register, slogan, ship_sign, label,
    stencil_side, stencil_front, hazard, exit): a painter fn(ctx, W, H), an image path, a Pillow image or an array
    (canvas_for). A board's ink roughness is derived from whatever is drawn on it. env_light: 'material' (each
    material lit by the room's env at its own intensity, as the engine's envMap; the World lights nothing) or
    'world' (the env as the World, lighting the whole scene at one intensity, with EEVEE's occlusion)."""
    import bpy
    L.check_art(art, CANVASES, 'quiet_room.build(art=...)')
    if env_light not in L.MaterialKit.ENV_LIGHTS:
        raise ValueError(f"quiet_room.build: env_light={env_light!r} (want 'material' or 'world')")
    scene, ctx = L.scene_and_ctx(ctx, scene)
    ss = singer_scale if singer_scale is not None else singerScale
    singer_scale = SUIT_SCALE if ss is None else ss
    face_y = 1.53 * singer_scale              # claudesona face centre at scale 1 ~ 1.53 m
    sb = L.SetBuilder(name, scene, collection)
    group = sb.root
    out = QuietRoom(sb, ctx)
    for u, v in (('uT', 0.0), ('uHell', 1.0), ('uSale', 0.0), ('uRoll', 0.0), ('uBeacon', 0.0)):
        sb.uniform(u, v)

    # ---------------------------------------------------------------------------------------- the room's light (env)
    ENV = sb.track(L.equirect_env(512, 256, env_paint, name='ufqr_env', light=env_light == 'world'))
    sb.track(bpy.data.images[ENV['uf_env_image']])
    K = L.material_kit(sb, env=ENV, prefix='ufqr', env_light=env_light)
    out.kit = K                                              # the room's material kit: a piece's own props lit alike
    tri = K.tri

    def img(key, srgb=True, repeat=False, alpha_weighted=False):
        cv = canvas_for(key, art, art_cache)
        return sb.track(L.canvas_texture(cv, srgb=srgb, repeat=repeat, alpha_weighted=alpha_weighted,
                                         name=f'ufqr_{key}')), cv

    # ---------------------------------------------------------------------------------------- materials
    S = {i: L.acg(i) for i in ('Carpet012', 'Carpet013', 'Fabric031', 'Chipboard004', 'Terrazzo003', 'Concrete017',
                               'Wood027', 'Wood096', 'Metal009', 'CorrugatedSteel005', 'Metal027')}
    pbr, solid = K.pbr, K.solid

    # carpet tiles: 0.5 m squares laid quarter-turned (the pile direction checkers), hairline seams, per-tile tone
    carpet_mat, g = K.new('carpet')
    p = g.uv()                                               # metres (box_uv)
    q = p / 0.5
    cell, f = g.floor(q), g.fract(q)
    turn = g.mod(cell.x + cell.y + 64.0, 2.0)
    lf = g.mix(f, g.vec2(f.y, 1.0 - f.x), turn)
    tuv = (cell + lf) * (0.5 / 0.62)
    h = g.hash((cell.x + 512.0) * 37.0 + (cell.y + 512.0))
    seam = g.smoothstep(0.0, 0.008, g.min(g.min(f.x, f.y), g.min(1.0 - f.x, 1.0 - f.y)))
    n = tri(g, 0.35)
    pile = g.texture(S['Carpet012']['map'], tuv).rgb
    lum_p = pile.x * 0.30 + pile.y * 0.59 + pile.z * 0.11
    col = (g.vec3(lum_p) * (1.25, 1.18, 1.22) + pile * 0.12) * (h * 0.12 + 0.92) * (seam * 0.35 + 0.65) \
        * ((n.z - 0.5) * 0.3 + 1)
    g.standard(color=col, roughness=g.texture(S['Carpet012']['roughnessMap'], tuv).r * 0.15 + 0.85,
               normal=g.normal_map(g.texture(S['Carpet012']['normalMap'], tuv).rgb, 0.9))
    K.envd(carpet_mat, 0.4)
    # the aisle runner: deep red pile with a black-and-brass bound edge
    runner_mat, g = K.new('runner')
    p = g.uv()                                               # u across the runner (-0.6..0.6), v along it (metres)
    tuv = p * 1.4
    e = g.abs(p.x)
    border = g.smoothstep(0.50, 0.505, e) * (1.0 - g.smoothstep(0.545, 0.55, e))
    binding = g.smoothstep(0.575, 0.58, e)
    n = tri(g, 0.5)
    pile = g.texture(S['Carpet013']['map'], tuv).rgb * (0.62, 0.12, 0.10) * ((n.z - 0.5) * 0.35 + 1)
    brass = g.vec3(0.55, 0.36, 0.12) * (g.texture(S['Carpet013']['map'], tuv * 2.0).y * 0.6 + 0.5)
    g.standard(color=g.mix(g.mix(pile, brass, border), (0.015, 0.012, 0.012), binding),
               roughness=g.mix(0.95, 0.55, border),
               normal=g.normal_map(g.texture(S['Carpet013']['normalMap'], tuv).rgb, 1.0))
    K.envd(runner_mat, 0.4)
    concrete_mat = pbr('concrete', S['Concrete017'], tint=(0.30, 0.31, 0.33), tile=1 / 2.2, rough=1.0, vary=0.25,
                       env_i=0.5)
    terrazzo_mat = pbr('terrazzo', S['Terrazzo003'], tint=(0.55, 0.55, 0.58), tile=1 / 1.1, rough=0.55, env_i=1.2)
    steel_mat = pbr('steel', S['Metal027'], tint=(0.55, 0.56, 0.60), tile=1 / 0.8, rough=0.9, metal=1, vary=0.25,
                    env_i=1.0)
    felt_mat = pbr('felt', S['Fabric031'], tint=(0.22, 0.22, 0.25), tile=1 / 0.45, rough=1, env_i=0.25)
    alum_mat = pbr('alum', S['Metal009'], tint=(0.92, 0.93, 0.96), tile=1 / 0.35, rough=0.7, metal=1, env_i=1.4)
    walnut_mat = pbr('walnut', S['Wood027'], tint=(0.55, 0.42, 0.36), tile=1 / 0.9, rough=0.75, env_i=0.9)
    pine_mat = pbr('pine', S['Wood096'], tint=(0.95, 0.88, 0.78), tile=1 / 0.7, rough=1.0, env_i=0.4)
    # (the engine also defines osbMat, galvMat and chromeMat and never puts them on a mesh: not built here, where
    # an unused material would be an orphan; the crate's OSB is crate_mat('crateosb') below)
    black_lacquer = solid('lacquer', (0.012, 0.011, 0.012), rough=0.18, rough_var=0.10, vary=0.4, scale=1.2,
                          physical=True, env_i=1.6, extra={'clearcoat': 0.8, 'clearcoatRoughness': 0.12})
    plastic_mat = solid('plastic', (0.022, 0.022, 0.025), rough=0.48, rough_var=0.18, vary=0.3, scale=6, env_i=0.9)
    pol_alum = solid('polalum', (0.74, 0.75, 0.77), rough=0.34, rough_var=0.10, metal=1, vary=0.08, scale=5, env_i=1.3)
    mesh_back = solid('boardback', (0.30, 0.31, 0.32), rough=0.6, rough_var=0.15, vary=0.15, scale=3)
    rubber_mat = solid('rubber', (0.015, 0.015, 0.016), rough=0.85, rough_var=0.1, vary=0.2, scale=8)
    # chair fabric: woven charcoal, the per-chair tone comes from the instance colour
    fabric_mat = pbr('fabric', S['Fabric031'], tint=(0.16, 0.165, 0.18), tile=1 / 0.16, rough=1.0, n_scale=1.3,
                     vary=0.15, vary_scale=2.0, env_i=0.35, instance_color=True)
    # glass: thin, reflective, faintly teal; a grime film that is thicker at the bottom and the corners
    glass_mat, g = K.new('glass')
    n = tri(g, 0.8)
    grime = g.smoothstep(0.9, 0.0, g.position_local().y) * 0.6 + n.x * 0.3
    g.standard(color=(0.55, 0.70, 0.72), roughness=g.clamp(0.03 + grime * 0.18, 0.02, 1.0), metalness=0.0,
               opacity=g.clamp(0.07 + grime * 0.09, 0.0, 1.0), blend='BLENDED')
    K.envd(glass_mat, 1.5)

    # ---------------------------------------------------------------------------------------- helpers
    def add(geo, mat, pos=(0, 0, 0), rot=(0, 0, 0), parent=None, cast=True, recv=True, keep=False, name=''):
        m = L.MeshNode(geo, mat, name=name or (mat.name.split('-', 1)[-1] if mat is not None else 'mesh'),
                       cast=cast, recv=recv, keep=keep)
        m.set_position(*pos)
        m.set_rotation(*rot[:3], order=rot[3] if len(rot) > 3 else 'XYZ')
        (parent or group).add(m)
        return m

    def box(w, h, d, uv_scale=1.0):
        return L.box_uv(L.box_geometry(w, h, d), uv_scale)

    def rbox(w, h, d, seg=2, rad=0.02):
        return L.box_uv(L.rounded_box_geometry(w, h, d, seg, rad), 1)

    def cyl(r0, r1, h, seg=16):
        return L.box_uv(L.cylinder_geometry(r0, r1, h, seg), 1)

    def beam(a, b, w, d, mat, parent=None, **o):
        A, B = np.array(a, float), np.array(b, float)
        m = add(box(w, float(np.linalg.norm(B - A)), d), mat, (0, 0, 0), (0, 0, 0), parent, **o)
        m.position = (A + B) * 0.5
        m.set_from_unit_vectors((0, 1, 0), B - A)
        return m

    def grp(name, parent=None):
        n_ = L.Node(name)
        (parent or group).add(n_)
        return n_

    # ======================================================================================== ARCHITECTURE
    arch = grp('qr:arch')
    # floor: carpet tiles on the tower's slab (solid, running under the core wall), the dais in black terrazzo, the
    # runner down the aisle
    add(box(2 * RX, SLAB, RZ1 + SLAB - RZ0), carpet_mat, (0, -SLAB / 2, (RZ0 + RZ1 + SLAB) / 2), parent=arch,
        cast=False, name='floor')
    top = L.Shape()
    top.move_to(-DAIS['x'], -DAIS['z1']).line_to(DAIS['x'], -DAIS['z1']).line_to(DAIS['x'], -DAIS['z0'])
    top.line_to(-DAIS['x'], -DAIS['z0']).line_to(-DAIS['x'], -DAIS['z1'])
    for hx, z0, z1 in ((GRATE['x'], GRATE['z0'], GRATE['z1']),
                       (1.3, ALTAR['z'] - ALTAR['d'] / 2 - 0.4, ALTAR['z'] - ALTAR['d'] / 2 - 0.12)):
        hp = L.Shape()
        hp.move_to(-hx, -z1).line_to(-hx, -z0).line_to(hx, -z0).line_to(hx, -z1).line_to(-hx, -z1)
        top.holes.append(hp)
    tg = L.shape_geometry(top).rotate_x(-math.pi / 2).translate(0, DAIS['h'], 0)
    add(L.box_uv(tg, 1), terrazzo_mat, parent=arch, cast=False, name='dais')
    add(box(2 * DAIS['x'], DAIS['h'], 0.03), terrazzo_mat, (0, DAIS['h'] / 2, DAIS['z1'] - 0.015), parent=arch)
    add(box(0.03, DAIS['h'], DAIS['z1'] - DAIS['z0']), terrazzo_mat,
        (-DAIS['x'] + 0.015, DAIS['h'] / 2, (DAIS['z0'] + DAIS['z1']) / 2), parent=arch)
    add(box(0.03, DAIS['h'], DAIS['z1'] - DAIS['z0']), terrazzo_mat,
        (DAIS['x'] - 0.015, DAIS['h'] / 2, (DAIS['z0'] + DAIS['z1']) / 2), parent=arch)
    # nosing: a brushed-aluminium strip on the step edge
    add(box(2 * DAIS['x'] + 0.01, 0.025, 0.03), alum_mat, (0, DAIS['h'] - 0.012, DAIS['z1'] + 0.005), parent=arch)
    # runner (its own UVs: u across in metres, v along)
    rl = DAIS['z1'] - 0.05 - (RZ1 - 0.45)
    rg = L.plane_geometry(1.2, abs(rl), 1, 1).rotate_x(-math.pi / 2)
    rg.uv = np.stack([(rg.uv[:, 0] - 0.5) * 1.2, rg.uv[:, 1] * abs(rl)], axis=1)
    add(rg, runner_mat, (0, 0.006, (DAIS['z1'] - 0.05 + RZ1 - 0.45) / 2), parent=arch, cast=False, keep=True,
        name='runner')
    # ceiling (felt under the slab above) + transverse acoustic baffles (the room's rhythm, like a nave's vault ribs)
    add(box(2 * RX, SLAB, RZ1 + SLAB - RZ0), felt_mat, (0, RH + SLAB / 2, (RZ0 + RZ1 + SLAB) / 2), parent=arch,
        cast=False, name='ceiling')
    z = RZ0 + 0.35
    while z < RZ1 - 0.2:
        add(box(2 * RX - 0.3, 0.34, 0.045), felt_mat, (0, RH - 0.17, z), parent=arch, cast=False)
        z += 0.6
    # core wall at +Z: exposed concrete with the hatch opening; a door; the house slogan
    wz = RZ1 + SLAB / 2
    W0, W1 = -RX, RX
    add(box(HATCH['x0'] - W0, RH, SLAB), concrete_mat, ((W0 + HATCH['x0']) / 2, RH / 2, wz), parent=arch)
    add(box(W1 - HATCH['x1'], RH, SLAB), concrete_mat, ((HATCH['x1'] + W1) / 2, RH / 2, wz), parent=arch)
    add(box(HATCH['x1'] - HATCH['x0'], HATCH['y0'], SLAB), concrete_mat,
        ((HATCH['x0'] + HATCH['x1']) / 2, HATCH['y0'] / 2, wz), parent=arch)
    add(box(HATCH['x1'] - HATCH['x0'], RH - HATCH['y1'], SLAB), concrete_mat,
        ((HATCH['x0'] + HATCH['x1']) / 2, (HATCH['y1'] + RH) / 2, wz), parent=arch)
    # the door (dark steel leaf in a frame) at x = -3.6
    add(box(1.06, 2.16, 0.06), steel_mat, (-3.6, 1.08, RZ1 + 0.0), parent=arch)
    add(box(0.98, 2.1, 0.04), solid('doorleaf', (0.035, 0.036, 0.04), rough=0.55, rough_var=0.2, vary=0.3, scale=2.5),
        (-3.6, 1.05, RZ1 - 0.03), parent=arch)
    add(box(0.04, 0.04, 0.32), pol_alum, (-3.25, 1.02, RZ1 - 0.08), parent=arch)
    # the glass curtain wall on three sides + the diagrid
    glass_g = grp('qr:glass', arch)

    def gx():
        return L.plane_geometry(RZ1 - RZ0, RH).translate(0, RH / 2, 0)
    gl = add(gx(), glass_mat, (-RX, 0, (RZ0 + RZ1) / 2), (0, math.pi / 2, 0), glass_g, cast=False, recv=False,
             keep=True, name='glass_left')
    gr = add(gx(), glass_mat, (RX, 0, (RZ0 + RZ1) / 2), (0, -math.pi / 2, 0), glass_g, cast=False, recv=False,
             keep=True, name='glass_right')
    gb = add(L.plane_geometry(2 * RX, RH).translate(0, RH / 2, 0), glass_mat, (0, 0, RZ0), (0, 0, 0), glass_g,
             cast=False, recv=False, keep=True, name='glass_back')
    for g_ in (gl, gr, gb):
        g_.render_order = 2
    # slim vertical mullions every 1.5 m, sill + head
    x = -RX
    while x <= RX + 1e-3:
        add(box(0.05, RH, 0.10), steel_mat, (x, RH / 2, RZ0 + 0.02), parent=glass_g)
        x += 1.5
    z = RZ0
    while z <= RZ1 + 1e-3:
        add(box(0.10, RH, 0.05), steel_mat, (-RX + 0.02, RH / 2, z), parent=glass_g)
        add(box(0.10, RH, 0.05), steel_mat, (RX - 0.02, RH / 2, z), parent=glass_g)
        z += 1.5
    add(box(2 * RX, 0.28, 0.25), steel_mat, (0, 0.14, RZ0 + 0.1), parent=glass_g)
    add(box(0.25, 0.28, RZ1 - RZ0), steel_mat, (-RX + 0.1, 0.14, (RZ0 + RZ1) / 2), parent=glass_g)
    add(box(0.25, 0.28, RZ1 - RZ0), steel_mat, (RX - 0.1, 0.14, (RZ0 + RZ1) / 2), parent=glass_g)
    # diagrid: chunky diagonals 0.3 m inside the glass, a zigzag of 69 degree members (the room's lines of force)
    DG, DW, DD = 0.30, 0.24, 0.30

    def zig(a0, a1, step, fn):
        s = a0
        while s < a1 - 1e-3:
            m0, m1, m2 = s, s + step / 2, s + step
            fn((m0, 0), (m1, RH))
            fn((m2, 0), (m1, RH))
            s += step
    zig(-RX, RX, 3.0, lambda p_, q_: beam((p_[0], p_[1], RZ0 + DG), (q_[0], q_[1], RZ0 + DG), DW, DD, steel_mat, glass_g))

    def side_pair(p_, q_):
        beam((-RX + DG, p_[1], p_[0]), (-RX + DG, q_[1], q_[0]), DD, DW, steel_mat, glass_g)
        beam((RX - DG, p_[1], p_[0]), (RX - DG, q_[1], q_[0]), DD, DW, steel_mat, glass_g)
    zig(RZ0, RZ1 - 0.2, 3.0, side_pair)
    # ring beams at the head
    add(box(2 * RX, 0.32, 0.36), steel_mat, (0, RH - 0.16, RZ0 + DG), parent=glass_g)
    add(box(0.36, 0.32, RZ1 - RZ0), steel_mat, (-RX + DG, RH - 0.16, (RZ0 + RZ1) / 2), parent=glass_g)
    add(box(0.36, 0.32, RZ1 - RZ0), steel_mat, (RX - DG, RH - 0.16, (RZ0 + RZ1) / 2), parent=glass_g)

    # ======================================================================================== CANVAS ART
    # marker tray props share five materials across every board (they merge into a handful of meshes)
    marker_mats = {
        'red': solid('marker-red', (0.45, 0.02, 0.025), rough=0.35, rough_var=0.1, scale=20),
        'black': solid('marker-black', (0.02, 0.02, 0.022), rough=0.35, rough_var=0.1, scale=20),
        'capred': solid('cap-red', (0.36, 0.016, 0.02), rough=0.4, scale=20),
        'capblack': solid('cap-black', (0.016, 0.016, 0.018), rough=0.4, scale=20),
        'eraser': solid('eraser', (0.10, 0.10, 0.11), rough=0.9, scale=15),
    }
    boards = []

    def whiteboard(bname, w, h, seed, px=PX):
        """enamel panel in an aluminium frame, marker tray with markers and an eraser, grey back."""
        g_ = L.Node('board:' + bname)
        albedo, cv = img(f'board_{bname}')
        rough = sb.track(L.board_roughness(cv, L.rng(seed + 7), name=f'ufqr_board_{bname}_rough'))
        m, gr_ = K.new('board-' + bname)
        gr_.standard(color=gr_.texture(albedo, gr_.uv()).rgb * 0.92, roughness=gr_.texture(rough, gr_.uv()).r,
                     metalness=0.0)
        K.envd(m, 1.0)
        face = add(L.plane_geometry(w, h), m, (0, 0, 0.012), parent=g_, keep=True, cast=False, name='boardface:' + bname)
        add(box(w + 0.02, h + 0.02, 0.02), mesh_back, parent=g_)
        fw, fd = 0.032, 0.034
        add(box(w + 2 * fw, fw, fd), alum_mat, (0, h / 2 + fw / 2, 0.006), parent=g_)
        add(box(w + 2 * fw, fw, fd), alum_mat, (0, -h / 2 - fw / 2, 0.006), parent=g_)
        add(box(fw, h, fd), alum_mat, (-w / 2 - fw / 2, 0, 0.006), parent=g_)
        add(box(fw, h, fd), alum_mat, (w / 2 + fw / 2, 0, 0.006), parent=g_)
        add(box(w * 0.7, 0.012, 0.075), alum_mat, (0, -h / 2 - fw - 0.006, 0.05), parent=g_)          # tray
        add(box(w * 0.7, 0.03, 0.008), alum_mat, (0, -h / 2 - fw + 0.006, 0.088), parent=g_)

        def mk(x_, red):
            add(cyl(0.0095, 0.0095, 0.135, 12), marker_mats['red' if red else 'black'],
                (x_, -h / 2 - fw + 0.012, 0.055), (0, 0, math.pi / 2), g_)
            add(cyl(0.0105, 0.0105, 0.04, 12), marker_mats['capred' if red else 'capblack'],
                (x_ + 0.075, -h / 2 - fw + 0.012, 0.055), (0, 0, math.pi / 2), g_)
        mk(-w * 0.18, True)
        mk(-w * 0.10, False)
        mk(w * 0.05, True)
        add(box(0.13, 0.04, 0.05), marker_mats['eraser'], (w * 0.2, -h / 2 - fw + 0.02, 0.055), parent=g_)
        boards.append({'name': bname, 'group': g_, 'albedo': albedo, 'rough': rough, 'face': face})
        return g_

    # ======================================================================================== THE ALTAR
    altar_g = grp('qr:altar')
    # the triptych on slim steel posts: centre panel square to the aisle, wings opened toward the pews
    y_c = TRIP['y0'] + TRIP['h'] / 2
    center = whiteboard('center', TRIP['w'], TRIP['h'], 101)
    center.set_position(0, y_c, TRIP['z'])
    altar_g.add(center)
    left = whiteboard('odds', TRIP['ww'], TRIP['h'], 202)
    right = whiteboard('clip', TRIP['ww'], TRIP['h'], 303)
    hx = TRIP['w'] / 2 + 0.075
    wing = TRIP['wing']
    left.set_position(-hx - math.cos(wing) * TRIP['ww'] / 2, y_c, TRIP['z'] + math.sin(wing) * TRIP['ww'] / 2)
    left.set_rotation(0, wing, 0)
    right.set_position(hx + math.cos(wing) * TRIP['ww'] / 2, y_c, TRIP['z'] + math.sin(wing) * TRIP['ww'] / 2)
    right.set_rotation(0, -wing, 0)
    altar_g.add(left, right)
    # posts: at the hinges and the wing ends
    post_top = TRIP['y0'] + TRIP['h'] + 0.12
    posts = [(-hx, TRIP['z']), (hx, TRIP['z']),
             (-hx - math.cos(wing) * TRIP['ww'] - 0.05, TRIP['z'] + math.sin(wing) * (TRIP['ww'] + 0.05)),
             (hx + math.cos(wing) * TRIP['ww'] + 0.05, TRIP['z'] + math.sin(wing) * (TRIP['ww'] + 0.05))]
    for x_, z_ in posts:
        add(cyl(0.024, 0.024, post_top - DAIS['h'], 14), pol_alum, (x_, DAIS['h'] + (post_top - DAIS['h']) / 2, z_ - 0.03),
            parent=altar_g)
        add(cyl(0.06, 0.07, 0.03, 18), pol_alum, (x_, DAIS['h'] + 0.015, z_ - 0.03), parent=altar_g)
    # the altar block: black lacquer, floating 8 cm over a recessed plinth whose slot glows
    add(box(ALTAR['w'], ALTAR['y1'] - ALTAR['y0'], ALTAR['d']), black_lacquer,
        (0, (ALTAR['y0'] + ALTAR['y1']) / 2, ALTAR['z']), parent=altar_g)
    add(box(ALTAR['w'] - 0.3, ALTAR['y0'] - DAIS['h'] + 0.01, ALTAR['d'] - 0.2),
        solid('plinth', (0.01, 0.01, 0.01), rough=0.7, scale=4), (0, (ALTAR['y0'] + DAIS['h']) / 2, ALTAR['z']),
        parent=altar_g)
    # the open risk register on the altar (a binder like a lectionary)
    bt, _cv = img('register')
    bm, g = K.new('register')
    g.standard(color=g.texture(bt, g.uv()).rgb, roughness=0.85, metalness=0.0)
    K.envd(bm, 0.6)
    pg = L.plane_geometry(0.62, 0.39, 8, 1)
    pg.pos[:, 2] = 0.025 * np.power(np.abs(pg.pos[:, 0]) / 0.31, 0.6)
    pg.compute_vertex_normals()
    add(pg, bm, (0.25, ALTAR['y1'] + 0.03, ALTAR['z'] + 0.02), (-math.pi / 2, 0, 0.12), altar_g, keep=True,
        name='register')
    add(box(0.64, 0.025, 0.41), solid('binder', (0.20, 0.015, 0.02), rough=0.5, scale=6),
        (0.25, ALTAR['y1'] + 0.0125, ALTAR['z'] + 0.02), (0, 0.12, 0), altar_g)
    # the grate in front of the altar and the slot behind it: steel bars over a glowing pit
    glow_mat, g = K.new('hellglow')
    p2 = g.position_local()
    p2 = g.vec2(p2.x, p2.z)
    u_t, u_hell = g.uniform('uT'), g.uniform('uHell')
    n1 = g.texture(K.NOISE, p2 * (0.9, 2.2, 0.0) + g.vec2(u_t * 0.05, u_t * -0.21)).x
    n2 = g.texture(K.NOISE, p2 * (2.3, 4.1, 0.0) + g.vec2(u_t * -0.08, u_t * -0.37)).y
    heat = g.clamp(n1 * 0.7 + n2 * 0.6 - 0.25, 0.0, 1.0)
    c = g.mix((0.7, 0.03, 0.012), (2.4, 0.36, 0.06), g.pow(heat, 1.4))
    g.basic(c * (u_hell * 1.6))
    L.hide_from_probes(glow_mat)

    def grate(x0, x1, z0, z1):
        w, d = x1 - x0, z1 - z0
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        add(L.plane_geometry(w, d).rotate_x(-math.pi / 2), glow_mat, (cx, DAIS['h'] - 0.14, cz), parent=altar_g,
            cast=False, recv=False, name='hellpit')
        # pit walls (dark steel, catch the glow)
        add(box(w, 0.14, 0.01), steel_mat, (cx, DAIS['h'] - 0.07, z0), parent=altar_g, cast=False)
        add(box(w, 0.14, 0.01), steel_mat, (cx, DAIS['h'] - 0.07, z1), parent=altar_g, cast=False)
        add(box(0.01, 0.14, d), steel_mat, (x0, DAIS['h'] - 0.07, cz), parent=altar_g, cast=False)
        add(box(0.01, 0.14, d), steel_mat, (x1, DAIS['h'] - 0.07, cz), parent=altar_g, cast=False)
        add(box(w + 0.04, 0.012, 0.03), steel_mat, (cx, DAIS['h'] + 0.002, z0 - 0.01), parent=altar_g)
        add(box(w + 0.04, 0.012, 0.03), steel_mat, (cx, DAIS['h'] + 0.002, z1 + 0.01), parent=altar_g)
        nb = max(3, int(math.floor(d / 0.034 + 0.5)))
        for i in range(nb):
            add(box(w, 0.035, 0.008), steel_mat, (cx, DAIS['h'] - 0.015, z0 + (i + 0.5) * d / nb), parent=altar_g)
        x_ = x0 + 0.25
        while x_ < x1 - 0.1:
            add(box(0.01, 0.03, d), steel_mat, (x_, DAIS['h'] - 0.03, cz), parent=altar_g)
            x_ += 0.5
    grate(-GRATE['x'], GRATE['x'], GRATE['z0'], GRATE['z1'])
    grate(-1.3, 1.3, ALTAR['z'] - ALTAR['d'] / 2 - 0.4, ALTAR['z'] - ALTAR['d'] / 2 - 0.12)
    # the slot under the floating block
    add(L.plane_geometry(ALTAR['w'] - 0.32, ALTAR['y0'] - DAIS['h'] - 0.01), glow_mat,
        (0, (ALTAR['y0'] + DAIS['h']) / 2, ALTAR['z'] + ALTAR['d'] / 2 - 0.1 + 0.001), parent=altar_g, cast=False,
        recv=False, name='hellslot')

    # ======================================================================================== THE LECTERN + ESSAY
    lectern_g = grp('qr:lectern')
    lectern_g.set_position(LECTERN['x'], DAIS['h'], LECTERN['z'])
    lectern_g.set_rotation(0, LECTERN['yaw'], 0)
    # tapered walnut column (front faces +Z), slanted desk tilted toward the reader at -Z
    shp = L.Shape()
    shp.move_to(-0.24, 0).line_to(0.24, 0).line_to(0.30, 1.0).line_to(-0.30, 1.0).line_to(-0.24, 0)
    colg = L.extrude_geometry(shp, depth=0.40, bevel_enabled=True, bevel_size=0.012, bevel_thickness=0.012,
                              bevel_segments=2).translate(0, 0, -0.20)
    add(L.box_uv(colg, 1), walnut_mat, parent=lectern_g, name='lectern_column')
    add(box(0.68, 0.035, 0.52), walnut_mat, (0, 1.06, -0.03), (-0.36, 0, 0), lectern_g)
    add(box(0.62, 0.025, 0.02), walnut_mat, (0, 0.995, -0.29), (-0.36, 0, 0), lectern_g)        # page ledge
    add(box(0.62, 0.05, 0.46), walnut_mat, (0, 0.03, 0), parent=lectern_g)
    # the essay (A3), held on the desk
    et, _cv = img('essay')
    em, g = K.new('essay')
    g.standard(color=g.texture(et, g.uv()).rgb, roughness=0.9, metalness=0.0)
    K.envd(em, 0.5)
    page = L.plane_geometry(0.297, 0.42, 1, 6)
    page.pos[:, 2] = 0.006 * np.sin((page.pos[:, 1] / 0.42 + 0.5) * math.pi)
    page.compute_vertex_normals()
    pm = add(page, em, parent=lectern_g, keep=True, cast=False, name='essay')
    # lie on the desk: normal up-and-toward the reader (-Z), the page's top edge up the slope (+Z)
    pm.set_position(0.0, 1.082, -0.03)
    pm.rotate_x(-0.36).rotate_y(math.pi).rotate_x(-math.pi / 2).rotate_z(0.04)
    # the pulpit fall: red velvet hung over the front, SLOW IT DOWN in gold thread and an hourglass
    ft, _cv = img('pulpit_fall')
    fm, g = K.new('pulpitfall')
    nfab = tri(g, 30.0)
    fs = g.texture(ft, g.uv())
    gold = g.smoothstep(0.35, 0.6, fs.y)
    g.standard(color=fs.rgb * (nfab.x * 0.25 + 0.85), roughness=g.mix(0.95, 0.45, gold), metalness=gold * 0.6)
    K.envd(fm, 0.4)
    fall = L.plane_geometry(0.40, 0.62, 10, 1)
    fall.pos[:, 2] = 0.008 * np.cos(fall.pos[:, 0] / 0.40 * math.pi * 5)
    fall.compute_vertex_normals()
    add(fall, fm, (0, 0.66, 0.226), (0.04, 0, 0), lectern_g, keep=True, name='pulpit_fall')
    # gooseneck reading lamp
    add(cyl(0.035, 0.04, 0.02, 16), pol_alum, (0.26, 1.1, -0.24), (-0.36, 0, 0), lectern_g)
    neck = L.tube_geometry(L.CatmullRomCurve3([(0.26, 1.11, -0.24), (0.25, 1.30, -0.22), (0.18, 1.40, -0.08),
                                               (0.08, 1.36, 0.0)]), 20, 0.008, 8)
    add(L.box_uv(neck, 1), pol_alum, parent=lectern_g, name='gooseneck')
    add(cyl(0.02, 0.045, 0.07, 16), pol_alum, (0.07, 1.34, 0.01), (0.9, 0, 0.4), lectern_g)
    lamp_light = L.LightNode('point', 0xffb36b, 0.14, 1.6, 2, name='lampLight')
    lamp_light.set_position(0.05, 1.27, 0.02)
    lectern_g.add(lamp_light)
    # a soft pulpit light from the ceiling, so SLOW IT DOWN reads from the pews
    pulpit_spot = L.LightNode('spot', 0xffe2c4, 7, 7, 1.6, angle=0.32, penumbra=0.85, name='pulpitSpot')
    pulpit_spot.set_position(LECTERN['x'] + 1.3, RH - 0.35, LECTERN['z'] + 2.4)
    pulpit_t = grp('pulpitTarget').set_position(LECTERN['x'], 0.75, LECTERN['z'])
    pulpit_spot.target = pulpit_t
    group.add(pulpit_spot)

    # ======================================================================================== THE PEWS (task chairs)
    chair_g = grp('qr:pews')
    fab, pla, met = [], [], []

    def put(arr, geo, pos, rot=(0, 0, 0)):
        geo = L.clean(geo)
        geo.apply_matrix4(L.mat4(L.euler_matrix(rot[0], rot[1], rot[2], rot[3] if len(rot) > 3 else 'XYZ'), pos))
        arr.append(geo)
    # star base (the chair faces -Z: seat front at -Z, backrest at +Z)
    put(met, L.cylinder_geometry(0.048, 0.058, 0.07, 18), (0, 0.105, 0))
    for k_ in range(5):
        a = k_ * math.pi * 2 / 5 + 0.3
        leg = L.box_geometry(0.046, 0.032, 0.29).translate(0, 0, 0.17)
        ca, sa = math.cos(a), math.sin(a)
        put(met, leg, (0, 0.092, 0), (0.06, a, 0, 'YXZ'))
        put(pla, L.box_geometry(0.034, 0.04, 0.05), (sa * 0.315, 0.063, ca * 0.315), (0, a, 0))
        wheel = L.cylinder_geometry(0.026, 0.026, 0.016, 14)
        put(pla, wheel.clone(), (sa * 0.32 + ca * 0.012, 0.027, ca * 0.32 - sa * 0.012), (0, a, math.pi / 2))
        put(pla, wheel.clone(), (sa * 0.32 - ca * 0.012, 0.027, ca * 0.32 + sa * 0.012), (0, a, math.pi / 2))
    put(pla, L.cylinder_geometry(0.032, 0.036, 0.15, 16), (0, 0.20, 0))
    put(met, L.cylinder_geometry(0.014, 0.014, 0.14, 12), (0, 0.33, 0))
    put(pla, L.box_geometry(0.17, 0.045, 0.23), (0, 0.42, 0.02))
    put(pla, L.rounded_box_geometry(0.50, 0.03, 0.48, 2, 0.012), (0, 0.455, 0))
    # seat cushion with a soft crown (the analytic rounded-box normals are kept, as in the engine)
    seat = L.rounded_box_geometry(0.50, 0.075, 0.47, 3, 0.03)
    sp = seat.pos
    up = sp[:, 1] > 0
    sp[up, 1] += 0.014 * np.maximum(0, 1 - (sp[up, 0] / 0.25) ** 2) * np.maximum(0, 1 - (sp[up, 2] / 0.235) ** 2)
    put(fab, seat, (0, 0.505, -0.01))

    def bend(geo, k_):
        geo.pos[:, 2] -= k_ * (geo.pos[:, 0] / 0.23) ** 2
        return geo
    put(fab, bend(L.rounded_box_geometry(0.46, 0.50, 0.07, 3, 0.03), 0.06), (0, 0.86, 0.245), (0.15, 0, 0))
    put(pla, bend(L.rounded_box_geometry(0.44, 0.48, 0.03, 2, 0.012), 0.06), (0, 0.857, 0.288), (0.15, 0, 0))
    put(pla, L.box_geometry(0.06, 0.40, 0.03), (0, 0.60, 0.29), (0.08, 0, 0))
    put(pla, L.box_geometry(0.08, 0.03, 0.18), (0, 0.43, 0.21))
    for sx in (-1, 1):                                       # arms
        put(pla, L.box_geometry(0.03, 0.025, 0.2), (sx * 0.2, 0.44, 0.02))
        put(pla, L.box_geometry(0.035, 0.22, 0.05), (sx * 0.275, 0.56, 0.03))
        put(pla, L.rounded_box_geometry(0.075, 0.032, 0.25, 2, 0.012), (sx * 0.275, 0.68, 0.0))
    chair_geo = {k_: L.box_uv(L.merge_geometries(v), 1) for k_, v in (('fab', fab), ('pla', pla), ('met', met))}
    seats = []
    r = L.rng(919)
    for z_ in ROWS:
        for sx in (-1, 1):
            for x_ in SEATS_X:
                s_x = sx * x_ + (r() - 0.5) * 0.03
                s_z = z_ + (r() - 0.5) * 0.04
                yaw = (r() - 0.5) * 0.09
                yaw += (r() - 0.5) * 0.7 if r() < 0.08 else 0.0
                lift = (r() - 0.5) * 0.03
                tone = 0.8 + r() * 0.35
                seats.append({'x': s_x, 'z': s_z, 'yaw': yaw, 'lift': lift, 'tone': tone})
    nch = len(seats)
    chair_meshes = []
    for k_, mat in (('fab', fabric_mat), ('pla', plastic_mat), ('met', pol_alum)):
        im = L.InstancedMeshNode(chair_geo[k_], mat, nch, name='chairs:' + k_, cast=True, recv=True)
        for i, s in enumerate(seats):
            im.set_matrix_at(i, L.mat4(L.rot_y(s['yaw']), (s['x'], 0, s['z']), (1, 1 + s['lift'], 1)))
            if k_ == 'fab':
                im.set_color_at(i, (s['tone'], s['tone'], s['tone'] * 1.02))
        chair_g.add(im)
        chair_meshes.append(im)
    # essay booklets on a third of the seats, like hymnals
    ct, _cv = img('booklet')
    bkm, g = K.new('booklet')
    g.standard(color=g.texture(ct, g.uv()).rgb, roughness=0.7, metalness=0.0)
    K.envd(bkm, 0.5)
    bgeo = L.plane_geometry(0.15, 0.21).rotate_x(-math.pi / 2)
    r = L.rng(5150)
    picks = [i for i in range(nch) if r() < 0.34]
    bim = L.InstancedMeshNode(bgeo, bkm, len(picks), name='booklets', cast=False, recv=True)
    for k_, i in enumerate(picks):
        s = seats[i]
        R = L.rot_y(s['yaw'] + (r() - 0.5) * 1.2)
        off = L.rot_y(s['yaw']) @ np.array([(r() - 0.5) * 0.14, 0.0, (r() - 0.5) * 0.12])
        bim.set_matrix_at(k_, L.mat4(R, (s['x'] + off[0], 0.561 * (1 + s['lift']), s['z'] - 0.01 + off[2])))
    chair_g.add(bim)

    # ======================================================================================== MOBILE BOARDS
    mobile_g = grp('qr:mobileboards')

    def mobile(bname, seed, pos, yaw):
        g_ = L.Node('mobile:' + bname)
        b = whiteboard(bname, 1.8, 1.2, seed)
        b.set_position(0, 1.45, 0)
        g_.add(b)
        for sx in (-1, 1):                                   # A-frame stand: two side uprights on castered feet
            add(box(0.04, 1.95, 0.04), pol_alum, (sx * 0.94, 0.98, 0), parent=g_)
            add(box(0.05, 0.04, 0.62), pol_alum, (sx * 0.94, 0.07, 0), parent=g_)
            for sz in (-1, 1):
                add(cyl(0.03, 0.03, 0.025, 12), plastic_mat, (sx * 0.94, 0.03, sz * 0.28), (math.pi / 2, 0, 0), g_)
        add(box(1.9, 0.03, 0.03), pol_alum, (0, 0.35, 0), parent=g_)
        g_.set_position(*pos)
        g_.set_rotation(0, yaw, 0)
        mobile_g.add(g_)
        return g_
    mobile('timelines', 404, (3.75, 0, -5.55), -0.62)
    mobile('want', 505, (-4.75, 0, -1.2), 1.05)

    # ======================================================================================== CONVEYOR, HATCH, CRATE
    ship_g = grp('qr:shipping')
    length = CONV['z1'] - CONV['z0']
    cz = (CONV['z0'] + CONV['z1']) / 2
    rail_mat = pbr('rail', S['Metal027'], tint=(0.30, 0.32, 0.36), tile=1 / 0.6, rough=0.8, metal=1, env_i=1.0)
    for sx in (-1, 1):
        add(box(0.05, 0.13, length), rail_mat, (CONV['x'] + sx * (CONV['w'] / 2 + 0.03), CONV['top'] - 0.035, cz),
            parent=ship_g)
        add(box(0.012, 0.04, length), rail_mat, (CONV['x'] + sx * (CONV['w'] / 2 + 0.06), CONV['top'] + 0.04, cz),
            parent=ship_g)                                   # guide lip
    z = CONV['z0'] + 0.2
    while z < CONV['z1']:
        for sx in (-1, 1):
            add(box(0.05, CONV['top'] - 0.1, 0.05), rail_mat,
                (CONV['x'] + sx * (CONV['w'] / 2 + 0.03), (CONV['top'] - 0.1) / 2, z), parent=ship_g)
            add(box(0.12, 0.012, 0.12), rail_mat, (CONV['x'] + sx * (CONV['w'] / 2 + 0.03), 0.006, z), parent=ship_g)
        z += 1.6
    add(box(CONV['w'] + 0.1, 0.12, 0.08), rubber_mat, (CONV['x'], CONV['top'] + 0.03, CONV['z0'] - 0.02),
        parent=ship_g)                                       # end stop
    # rollers: instanced; their grey streaks turn about each roller's own axis with uRoll
    rgeo = L.cylinder_geometry(0.03, 0.03, CONV['w'], 20).rotate_z(math.pi / 2)
    roller_mat, g = K.new('roller')
    pl = g.position_local()
    z0r = CONV['z0'] + 0.08
    zc = g.floor((pl.z - z0r) / 0.125 + 0.5) * 0.125 + z0r
    ang = g.atan2(pl.y - (CONV['top'] - 0.03), pl.z - zc) + g.uniform('uRoll')
    streak = g.smoothstep(0.7, 0.98, g.sin(ang * 3.0) * 0.5 + 0.5)
    rn = tri(g, 14.0)
    g.standard(color=g.vec3(0.62, 0.64, 0.68) * (1.0 - streak * 0.5) * (rn.x * 0.3 + 0.85),
               roughness=g.clamp(0.32 + streak * 0.3 + (rn.y - 0.5) * 0.2, 0.05, 1.0), metalness=1.0)
    K.envd(roller_mat, 1.2)
    zs = []
    z = CONV['z0'] + 0.08
    while z < CONV['z1'] - 0.05:
        zs.append(z)
        z += 0.125
    ri = L.InstancedMeshNode(rgeo, roller_mat, len(zs), name='rollers', cast=True, recv=True)
    for i, z_ in enumerate(zs):
        ri.set_matrix_at(i, L.mat4(t=(CONV['x'], CONV['top'] - 0.03, z_)))
    ship_g.add(ri)
    # the tunnel behind the hatch (dark, with the backlight that comes on as the crate arrives)
    tz0, tz1 = RZ1 + 0.3, CONV['z1'] + 0.4
    tcz, tl = (tz0 + tz1) / 2, tz1 - tz0
    tunnel_mat = solid('tunnel', (0.05, 0.05, 0.055), rough=0.8, vary=0.35, scale=1.5, env_i=0.3)
    add(box(HATCH['x1'] - HATCH['x0'] + 0.4, 0.05, tl), tunnel_mat, (CONV['x'], HATCH['y1'] + 0.2, tcz), parent=ship_g)
    add(box(HATCH['x1'] - HATCH['x0'] + 0.4, 0.05, tl), tunnel_mat, (CONV['x'], 0.02, tcz), parent=ship_g)
    add(box(0.05, HATCH['y1'] + 0.2, tl), tunnel_mat, (HATCH['x0'] - 0.2, (HATCH['y1'] + 0.2) / 2, tcz), parent=ship_g)
    add(box(0.05, HATCH['y1'] + 0.2, tl), tunnel_mat, (HATCH['x1'] + 0.2, (HATCH['y1'] + 0.2) / 2, tcz), parent=ship_g)
    add(box(HATCH['x1'] - HATCH['x0'] + 0.4, HATCH['y1'] + 0.2, 0.05), tunnel_mat,
        (CONV['x'], (HATCH['y1'] + 0.2) / 2, tz1), parent=ship_g)
    # hazard-striped hatch frame
    ht, _cv = img('hazard', repeat=True)
    hm, g = K.new('hazard')
    n = tri(g, 6.0)
    g.standard(color=g.texture(ht, g.uv() * (2.2, 1.0, 1.0)).rgb * (n.x * 0.5 + 0.6),
               roughness=g.clamp(0.5 + (n.y - 0.5) * 0.5, 0.1, 1.0), metalness=0.2)
    K.envd(hm, 0.6)
    fz, t_ = RZ1 - 0.02, 0.11

    def strip(w, h_, pos, rot_z):
        sg = L.plane_geometry(w, h_)
        sg.uv[:, 0] *= w / 0.45
        add(sg, hm, pos, (0, math.pi, rot_z), ship_g, cast=False, name='hazard')
    strip(HATCH['x1'] - HATCH['x0'] + 2 * t_, t_, (CONV['x'], HATCH['y1'] + t_ / 2, fz), 0)
    strip(HATCH['x1'] - HATCH['x0'] + 2 * t_, t_, (CONV['x'], HATCH['y0'] - t_ / 2, fz), 0)
    strip(HATCH['y1'] - HATCH['y0'], t_, (HATCH['x0'] - t_ / 2, (HATCH['y0'] + HATCH['y1']) / 2, fz), math.pi / 2)
    strip(HATCH['y1'] - HATCH['y0'], t_, (HATCH['x1'] + t_ / 2, (HATCH['y0'] + HATCH['y1']) / 2, fz), math.pi / 2)
    add(box(HATCH['x1'] - HATCH['x0'] + 0.3, 0.32, 0.36), steel_mat, (CONV['x'], HATCH['y1'] + 0.32, RZ1 - 0.17),
        parent=ship_g)                                       # shutter housing
    # the roller shutter: corrugated slats; it slides up into its housing as it opens
    shutter = L.Node('shutter')
    shutter.set_position(CONV['x'], HATCH['y1'], RZ1 + 0.02)
    ship_g.add(shutter)
    sh_h, sh_w = HATCH['y1'] - HATCH['y0'], HATCH['x1'] - HATCH['x0']
    sgeo = L.plane_geometry(sh_w, sh_h, 1, 1).translate(0, -sh_h / 2, 0)
    sgeo.uv = sgeo.uv * (sh_w, sh_h)
    sm, g = K.new('shutter')
    p = g.uv()
    slat = g.fract(p.y / 0.075)
    groove = g.smoothstep(0.0, 0.08, slat) * (1.0 - g.smoothstep(0.88, 1.0, slat))
    n = tri(g, 3.0)
    g.standard(color=g.texture(S['CorrugatedSteel005']['map'], p / 0.9).rgb * (0.75, 0.77, 0.8) * (groove * 0.4 + 0.6)
               * (n.x * 0.4 + 0.8),
               roughness=g.clamp(g.texture(S['CorrugatedSteel005']['roughnessMap'], p / 0.9).r + (n.y - 0.5) * 0.3,
                                 0.1, 1.0), metalness=0.85)
    K.envd(sm, 1.0)
    add(sgeo, sm, parent=shutter, keep=True, name='shutterleaf')
    # the crate on its pallet: OSB panels, pine battens and cross braces, steel straps. The stencils are SPRAYED:
    # projected through the crate's own materials along X (long sides) and -Z (the leading end), so the paint runs
    # over panels and battens alike, the way a stencil is painted on a finished crate.
    crate = L.Node('crate')
    ship_g.add(crate)
    crate_body = L.Node('crateBody')
    crate.add(crate_body)
    CL, CW, CH, PH = CRATE['L'], CRATE['W'], CRATE['H'], CRATE['pallet']
    y0 = PH
    side_t, _cv = img('stencil_side', alpha_weighted=True)
    front_t, _cv = img('stencil_front', alpha_weighted=True)

    def crate_mat(cname, set_, tint, tile, rough):
        m, g_ = K.new(cname)
        tuv_ = g_.uv() * tile
        n_ = tri(g_, 0.8)
        base = g_.texture(set_['map'], tuv_).rgb * tint * ((n_.z - 0.5) * 0.36 + 1)
        p_, nl = g_.position_local(), g_.normal_local()
        v_s = (p_.y - (y0 + 0.1)) / (CH - 0.2)
        side_w = g_.smoothstep(0.6, 0.85, g_.abs(nl.x))
        u_s = g_.select(nl.x.less_than(0.0), p_.z, -p_.z) / (CL - 0.2) + 0.5
        s_t = g_.texture(side_t, g_.vec2(u_s, v_s))
        in_s = g_.step(0.0, u_s) * g_.step(u_s, 1.0) * g_.step(0.0, v_s) * g_.step(v_s, 1.0)
        front_w = g_.smoothstep(0.6, 0.85, -nl.z)
        u_f = -p_.x / (CW - 0.2) + 0.5
        f_t = g_.texture(front_t, g_.vec2(u_f, v_s))
        in_f = g_.step(0.0, u_f) * g_.step(u_f, 1.0) * g_.step(0.0, v_s) * g_.step(v_s, 1.0)
        a_s, a_f = s_t.a * side_w * in_s, f_t.a * front_w * in_f
        a_ = g_.clamp(a_s + a_f, 0.0, 1.0) * 0.94
        ink = (s_t.rgb * a_s + f_t.rgb * a_f) / g_.max(a_s + a_f, 1e-3)
        r0 = g_.texture(set_['roughnessMap'], tuv_).r * rough
        g_.standard(color=g_.mix(base, ink, a_),
                    roughness=g_.mix(g_.clamp(r0 + (n_.y - 0.5) * 0.2, 0.3, 1.0), 0.62, a_),
                    normal=g_.normal_map(g_.texture(set_['normalMap'], tuv_).rgb, 1.0))
        return K.envd(m, 0.4)
    c_osb = crate_mat('crateosb', S['Chipboard004'], (0.92, 0.84, 0.72), 1 / 0.9, 1.0)
    c_pine = crate_mat('cratepine', S['Wood096'], (0.95, 0.88, 0.78), 1 / 0.7, 1.0)
    add(box(CW, CH, CL), c_osb, (0, y0 + CH / 2, 0), parent=crate_body)
    for sx in (-1, 0, 1):                                    # pallet skids + deck
        add(box(0.09, PH - 0.02, CL), pine_mat, (sx * (CW / 2 - 0.045), (PH - 0.02) / 2, 0), parent=crate_body)
    add(box(CW + 0.02, 0.02, CL + 0.02), pine_mat, (0, PH - 0.01, 0), parent=crate_body)
    # battens on every edge of the long sides and ends, and a diagonal brace on each long side
    bt_, bd = 0.085, 0.022
    for sx in (-1, 1):
        x_ = sx * (CW / 2 + bd / 2)
        add(box(bd, bt_, CL), c_pine, (x_, y0 + bt_ / 2, 0), parent=crate_body)
        add(box(bd, bt_, CL), c_pine, (x_, y0 + CH - bt_ / 2, 0), parent=crate_body)
        add(box(bd, CH, bt_), c_pine, (x_, y0 + CH / 2, CL / 2 - bt_ / 2), parent=crate_body)
        add(box(bd, CH, bt_), c_pine, (x_, y0 + CH / 2, -CL / 2 + bt_ / 2), parent=crate_body)
        dl, da = math.hypot(CL - 2 * bt_, CH - 2 * bt_), math.atan2(CH - 2 * bt_, CL - 2 * bt_)
        add(box(bd, bt_, dl), c_pine, (x_, y0 + CH / 2, 0), (sx * da, 0, 0), crate_body)
    for sz in (-1, 1):
        z_ = sz * (CL / 2 + bd / 2)
        add(box(CW + 2 * bd, bt_, bd), c_pine, (0, y0 + bt_ / 2, z_), parent=crate_body)
        add(box(CW + 2 * bd, bt_, bd), c_pine, (0, y0 + CH - bt_ / 2, z_), parent=crate_body)
        add(box(bt_, CH, bd), c_pine, (CW / 2 - bt_ / 2 + bd, y0 + CH / 2, z_), parent=crate_body)
        add(box(bt_, CH, bd), c_pine, (-CW / 2 + bt_ / 2 - bd, y0 + CH / 2, z_), parent=crate_body)
    add(box(CW + 0.01, 0.012, CL * 0.86), c_pine, (0, y0 + CH + 0.006, 0), parent=crate_body)
    strap = solid('strap', (0.05, 0.05, 0.055), rough=0.35, metal=1, scale=10, env_i=1.2)       # steel straps
    for sz in (-0.3, 0.3):
        add(box(CW + 0.06, 0.003, 0.025), strap, (0, y0 + CH + 0.014, sz), parent=crate_body)
        for sx in (-1, 1):
            add(box(0.003, CH, 0.025), strap, (sx * (CW / 2 + 0.03), y0 + CH / 2, sz), parent=crate_body)
    # shipping label (white paper, barcode) on the room-side panel
    lt, _cv = img('label')
    lm, g = K.new('label')
    g.standard(color=g.texture(lt, g.uv()).rgb, roughness=0.7, metalness=0.0)
    K.envd(lm, 0.4)
    lb = add(L.plane_geometry(0.24, 0.16), lm, (-CW / 2 - 0.004, y0 + CH * 0.23, CL * 0.27), (0, -math.pi / 2, 0.03),
             crate, keep=True, cast=False, name='label')
    lb.render_order = 3
    crate.set_position(CONV['x'], CONV['top'], CRATE['zIn'])

    # the "NOW SHIPPING" LED sign above the hatch and the amber beacon
    st_, _cv = img('ship_sign')
    sign_mat, g = K.new('shipsign')
    p = g.uv()
    gg = g.vec2(g.fract(p.x * 256.0), g.fract(p.y * 40.0))
    dotm = g.smoothstep(0.5, 0.25, (gg - (0.5, 0.5, 0.0)).length())
    on = g.texture(st_, p).r
    lit = on * dotm * (g.uniform('uSale') * 6.0 + 0.03)
    g.basic(g.vec3(0.92, 0.97, 1.0) * lit + g.vec3(0.02, 0.02, 0.025) * dotm)
    L.hide_from_probes(sign_mat)
    add(L.plane_geometry(2.2, 0.34), sign_mat, (CONV['x'] - 0.2, HATCH['y1'] + 0.85, RZ1 - 0.03), (0, math.pi, 0),
        ship_g, keep=True, cast=False, name='shipsign')
    beacon = L.Node('beacon')
    beacon.set_position(HATCH['x0'] - 0.35, HATCH['y1'] + 0.2, RZ1 - 0.12)
    ship_g.add(beacon)
    add(cyl(0.07, 0.08, 0.05, 20), plastic_mat, parent=beacon)
    dm, g = K.new('beacon')
    pl = g.position_local()
    a = g.atan2(pl.z, pl.x)
    sweep = g.pow(g.cos(a - g.uniform('uT') * 9.0) * 0.5 + 0.5, 6.0)
    g.basic(g.vec3(1.0, 0.45, 0.05) * (g.uniform('uBeacon') * (sweep * 6.0 + 0.8) + 0.08), opacity=0.92)
    L.hide_from_probes(dm)
    add(L.cylinder_geometry(0.06, 0.065, 0.12, 24), dm, (0, 0.085, 0), parent=beacon, keep=True, cast=False,
        name='beacondome')
    beacon_light = L.LightNode('spot', 0xff7a1a, 0, 14, 1.6, angle=0.5, penumbra=0.6, name='beaconLight')
    beacon_light.set_position(0, 0.09, 0)
    beacon.add(beacon_light)
    beacon_target = L.Node('beaconTarget').set_position(2.0, -0.6, 0)
    beacon.add(beacon_target)
    beacon_light.target = beacon_target

    # the house slogan, in brushed-brass letters on the core wall
    wt, _cv = img('slogan', alpha_weighted=True)
    slm, g = K.new('slogan')
    n = tri(g, 25.0)
    g.standard(color=g.vec3(0.78, 0.58, 0.30) * (n.x * 0.3 + 0.8), roughness=0.35, metalness=1.0,
               opacity=g.texture(wt, g.uv()).a, blend='BLENDED')
    K.envd(slm, 1.5)
    sl = add(L.plane_geometry(4.6, 0.36), slm, (-0.4, 2.95, RZ1 - 0.01), (0, math.pi, 0), group, keep=True,
             cast=False, name='slogan')
    sl.render_order = 3
    # EXIT sign over the door
    xt, _cv = img('exit')
    exm, g = K.new('exit')
    g.basic(g.texture(xt, g.uv()).rgb * (3.2, 0.25, 0.2))
    L.hide_from_probes(exm)
    add(L.plane_geometry(0.42, 0.16), exm, (-3.6, 2.42, RZ1 - 0.06), (0, math.pi, 0), group, keep=True, cast=False,
        name='exit')
    add(box(0.46, 0.2, 0.06), plastic_mat, (-3.6, 2.42, RZ1 - 0.02), parent=group)

    # ======================================================================================== SALE LIGHTS
    sale_g = grp('saleLights')
    strip_mat, g = K.new('ledstrip')
    n = tri(g, 4.0)
    u_sale = g.uniform('uSale')
    g.standard(color=g.vec3(0.30, 0.31, 0.33) * (n.x * 0.2 + 0.9), roughness=0.4, metalness=0.0,
               emissive=g.vec3(0.85, 0.93, 1.0) * (u_sale * u_sale * 8.0))
    K.envd(strip_mat, 0.5)
    L.hide_from_probes(strip_mat)
    for x_ in (-2.4, 0, 2.4):
        add(box(0.09, 0.04, RZ1 - RZ0 - 1.0), strip_mat, (x_, RH - 0.40, (RZ0 + RZ1) / 2), parent=sale_g, cast=False)
        z_ = RZ0 + 1.2
        while z_ < RZ1 - 0.6:
            add(cyl(0.004, 0.004, 0.36, 6), pol_alum, (x_, RH - 0.20, z_), parent=sale_g, cast=False)
            z_ += 3.0
    sale_spots = []
    for x_, z_, tx, tz in ((-2.4, -3.0, -2.2, -2.5), (2.4, -3.0, 2.2, -2.5), (-2.4, 2.6, -2.2, 2.2),
                           (2.4, 2.6, 2.2, 2.2), (3.9, 1.8, CONV['x'], CRATE['zOut']), (0, -5.2, 0, -7.6)):
        s = L.LightNode('spot', 0xe8f2ff, 0, 16, 1.4, angle=0.62, penumbra=0.55, name=f'saleSpot{len(sale_spots)}')
        s.set_position(x_, RH - 0.45, z_)
        tg_ = L.Node(f'saleTarget{len(sale_spots)}').set_position(tx, 0, tz)
        sale_g.add(tg_)
        s.target = tg_
        sale_g.add(s)
        sale_spots.append(s)
    tunnel_light = L.LightNode('point', 0xdfe8ff, 0, 4.5, 2, name='tunnelLight')
    tunnel_light.set_position(CONV['x'], 1.25, RZ1 + 1.1)
    ship_g.add(tunnel_light)

    # ======================================================================================== HELL + CITY LIGHTS
    hell_lights = []
    for x_, y_, z_, i in ((-0.75, 0.16, -6.2, 1.6), (0.75, 0.16, -6.2, 1.6), (0, 0.16, -7.45, 6.0),
                          (-1.15, 0.16, -7.45, 4.0), (1.15, 0.16, -7.45, 4.0)):
        p_ = L.LightNode('point', 0xff2a12, i, 7.5, 2.0, name=f'hellLight{len(hell_lights)}')
        p_.set_position(x_, y_, z_)
        p_.user_data['base'] = i
        altar_g.add(p_)
        hell_lights.append(p_)
    # the hell pours down the nave: a low red key from the altar end, so every chair throws its shadow toward the back
    hell_key = L.LightNode('directional', 0xff2010, 5.0, name='hellKey', cast_shadow=True, sun_angle_deg=1.0)
    hell_key.set_position(-6.5, 8.5, -13.5)
    hell_key_t = grp('hellKeyTarget').set_position(1.0, 0.0, 3.5)
    hell_key.target = hell_key_t
    group.add(hell_key)
    # the glow climbs into the vault: a red uplight from the pit that paints the ceiling baffles over the pews
    vault = L.LightNode('spot', 0xff2a14, 40, 11.5, 1.3, angle=0.95, penumbra=0.9, name='vaultLight')
    vault.set_position(0, 0.25, -6.2)
    vault.target = grp('vaultTarget').set_position(0, RH, -1.0)
    altar_g.add(vault)
    # a cold top light on the altarpiece (a church's altar spot): it is what keeps the red ink red on the white boards
    altar_spot = L.LightNode('spot', 0xdce8ff, 22, 9, 1.6, angle=0.62, penumbra=0.8, name='altarSpot')
    altar_spot.set_position(0, RH - 0.3, -5.3)
    altar_spot_t = L.Node('altarSpotTarget').set_position(0, 1.7, TRIP['z'])
    altar_g.add(altar_spot_t)
    altar_spot.target = altar_spot_t
    altar_g.add(altar_spot)
    city_key = L.LightNode('directional', 0x3fd2ff, 1.35, name='cityKey')
    city_key.set_position(16, 7.5, -4)
    city_key.target = grp('cityKeyTarget').set_position(0, 0, -1.5)
    group.add(city_key)
    city_fill = L.LightNode('directional', 0xff4fd8, 0.28, name='cityFill')
    city_fill.set_position(-14, 4, 3)
    city_fill.target = grp('cityFillTarget')
    group.add(city_fill)
    # the singer in black techwear must not sink into the red: a cold kicker from behind and above her mark (it rims
    # her against the nave and pools on the runner like a spotlight on "the ending"), and a dim cold front fill.
    # Both aim at MARK; retarget parts['singerLights'] if she moves.
    kicker = L.LightNode('spot', 0xc8f2ff, 16, 10, 1.4, angle=0.30, penumbra=0.65, name='kicker')
    kicker.set_position(-0.9, 2.6, -2.9)
    kick_t = grp('kickerTarget').set_position(0, 1.0, 0.15)
    kicker.target = kick_t
    group.add(kicker)
    front_fill = L.LightNode('spot', 0x9fd8ff, 3.5, 9, 1.4, angle=0.26, penumbra=0.8, name='frontFill')
    front_fill.set_position(0.7, RH - 0.35, 3.4)
    fill_t2 = grp('fillTarget').set_position(0, 1.1, 0)
    front_fill.target = fill_t2
    group.add(front_fill)
    exit_glow = L.LightNode('point', 0xff2020, 0.35, 2.5, 2, name='exitGlow')
    exit_glow.set_position(-3.6, 2.3, RZ1 - 0.3)
    group.add(exit_glow)

    # ======================================================================================== CITY BACKDROP
    backdrop = grp('qr:backdrop')
    # sky dome
    sky_mat, g = K.new('sky')
    d_ = g.view_dir()
    h = d_.y
    nn = g.texture(K.NOISE, g.vec2(d_.x, d_.z) / g.max(h + 0.35, 0.08) * 0.25 + g.vec2(g.uniform('uT') * 0.002, 0.0)).z
    c = g.mix((0.016, 0.026, 0.036), (0.0015, 0.002, 0.006), g.smoothstep(0.0, 0.45, h))
    glow = g.exp(g.abs(h) * -9.0)
    clouds = g.smoothstep(0.45, 0.8, nn) * g.smoothstep(0.02, 0.3, h) * 0.5
    g.basic(c + g.vec3(0.13, 0.06, 0.022) * glow * 0.75 + g.vec3(0.022, 0.016, 0.022) * clouds)
    sky_mat.use_backface_culling = True
    L.hide_from_probes(sky_mat, volume=True, sphere=True)
    sky = add(_flip(L.sphere_geometry(900, 48, 24)), sky_mat, parent=backdrop, cast=False, recv=False, keep=True,
              name='sky')
    sky.render_order = -10
    # ground far below: blocks of dark with sodium street grids
    gm, g = K.new('cityground')
    pw = g.position_world()
    p = g.vec2(pw.x, pw.z) / 36.0
    f, c_ = g.fract(p), g.floor(p)
    street = 1.0 - g.smoothstep(0.0, 0.03, g.min(g.min(f.x, f.y), g.min(1.0 - f.x, 1.0 - f.y)))
    hh = g.hash((c_.x + 4096.0) * 57.0 + (c_.y + 4096.0))
    lamps = g.step(0.5, g.fract(p.x * 6.0)) * g.step(0.5, g.fract(p.y * 6.0))
    col = g.vec3(0.012, 0.012, 0.016) * (hh * 0.6 + 0.6) + g.vec3(0.9, 0.42, 0.12) * street * (lamps * 0.6 + 0.4) * 0.8
    g.basic(g.mix(col, (0.012, 0.011, 0.016), 1.0 - g.exp(g.view_distance() * -0.0022)))
    L.hide_from_probes(gm, volume=True, sphere=True)
    add(L.plane_geometry(2400, 2400).rotate_x(-math.pi / 2), gm, (0, GROUND, 0), parent=backdrop, cast=False,
        recv=False, keep=True, name='cityground')
    # towers
    tgeo = L.box_geometry(1, 1, 1).translate(0, 0.5, 0)
    tm, g = K.new('towers')
    p = g.position_local()                                   # backdrop space (the instance transform applied)
    iid = g.attribute('instance_id')
    # hash(id + 17 / 91 / 233): three's exact values, computed per tower at build time (set_instance_attr below), so
    # the neon edges, facade tones and window colours land on the same towers as in the engine
    h1, h2, h3 = g.attribute('uf_h17'), g.attribute('uf_h91'), g.attribute('uf_h233')
    nrm = g.normal_local().abs()
    along = g.select(nrm.x.greater_than(0.5), p.z, p.x)
    fy, fx = (p.y - GROUND) / 3.4, along / (h1 * 0.6 + 1.1)
    cell = g.floor(g.vec2(fx, fy))
    f = g.fract(g.vec2(fx, fy))
    win = g.step(0.32, f.x) * g.step(f.x, 0.68) * g.step(0.38, f.y) * g.step(f.y, 0.72)
    hw = g.hash((cell.x + 8192.0) * 131.0 + (cell.y + 8192.0) * 7.0 + iid * 613.0)
    lit = g.step(0.84 + h2 * 0.12, hw)
    wcol = g.mix(g.mix((1.0, 0.62, 0.32), (0.35, 0.85, 1.0), g.step(0.55, h3)), (1.0, 0.3, 0.8),
                 g.step(0.9, g.hash(hw * 977.0)))
    facade = g.vec3(0.010, 0.012, 0.018) * (h1 * 0.8 + 0.6)
    edge = g.smoothstep(0.46, 0.5, g.abs(g.fract(along / (h1 * 30.0 + 18.0)) - 0.5))
    neon = g.mix((0.16, 0.9, 1.0), (1.0, 0.31, 0.85), g.step(0.5, h1)) * edge * g.step(0.82, h2) * 2.5
    col = facade + wcol * win * lit * ((hw - 0.84) * 5.0 + 0.35) + neon
    fog = 1.0 - g.exp(g.view_distance() * -0.0030)
    g.basic(g.mix(col, (0.010, 0.011, 0.018), fog * 0.9))
    L.hide_from_probes(tm, volume=True, sphere=True)
    r = L.rng(2024)
    towers = []
    for _ in range(360):
        a = r() * math.pi * 2
        d = 70 + math.pow(r(), 0.7) * 480
        x_, z_ = math.cos(a) * d, math.sin(a) * d - 10
        if abs(x_) < 55 and -60 < z_ < 50:
            continue
        w, dd = 14 + r() * 26, 14 + r() * 26
        top_ = -110 + math.pow(r(), 0.8) * 290 * (0.85 if d < 120 else 1.0)
        towers.append((x_, z_, w, dd, top_ - GROUND))
    ti = L.InstancedMeshNode(tgeo, tm, len(towers), name='towers', cast=False, recv=False)
    for i, (x_, z_, w, dd, h_) in enumerate(towers):
        ti.set_matrix_at(i, L.mat4(L.rot_y((r() - 0.5) * 0.5), (x_, GROUND, z_), (w, h_, dd)))
    ids = np.arange(len(towers), dtype=np.float64)
    for off in (17, 91, 233):
        ti.set_instance_attr(f'uf_h{off}', L.pcg_hash(ids + off))
    backdrop.add(ti)
    # red aviation lights on the tall tops (blink; hash(id + 5) exact, as the towers')
    am, g = K.new('aviation')
    blink = g.step(0.55, g.fract(g.uniform('uT') * 0.5 + g.attribute('uf_h5')))
    g.basic(g.vec3(3.5, 0.15, 0.08) * (blink * 0.9 + 0.1))
    L.hide_from_probes(am, volume=True, sphere=True)
    tall = [t__ for t__ in towers if t__[4] + GROUND > 20]
    ai = L.InstancedMeshNode(L.sphere_geometry(0.9, 8, 6), am, max(1, len(tall)), name='aviation', cast=False,
                             recv=False)
    for i, (x_, z_, w, dd, h_) in enumerate(tall):
        ai.set_matrix_at(i, L.mat4(t=(x_, GROUND + h_ + 1.2, z_)))
    ai.set_instance_attr('uf_h5', L.pcg_hash(np.arange(ai.count, dtype=np.float64) + 5.0))
    backdrop.add(ai)

    # ======================================================================================== SHADOW CASTERS
    # one shadow map (the red key down the nave). Only things whose shadows read on screen cast: the pews, the altar
    # and its boards, the mobile boards, the lectern, the crate and the conveyor, and the diagrid. Floors, ceiling,
    # walls, small props and the backdrop only receive. Chosen BEFORE merging (merged buckets inherit them).
    casters = [chair_g, altar_g, mobile_g, lectern_g, crate, glass_g]

    def under(o):
        p__ = o
        while p__ is not None:
            if any(p__ is c__ for c__ in casters):
                return True
            p__ = p__.parent
        return False
    tiny = {id(m) for m in marker_mats.values()}

    def pick(o):
        if isinstance(o, L.MeshNode):
            o.cast = o.cast and under(o) and id(o.material) not in tiny and o.material is not glow_mat
    group.traverse(pick)

    def walls(o):
        # the core wall and the tunnel keep the red key out of the hatch until the crate rides into the room
        if isinstance(o, L.MeshNode) and (o.material is concrete_mat or o.material is tunnel_mat):
            o.cast = True
    group.traverse(walls)
    for im in chair_meshes:
        im.cast = True

    # ======================================================================================== MERGE STATIC
    # Every static mesh in the room merges into ONE mesh per material (draw calls were the engine's cost; in Blender
    # it keeps the outliner readable). Moving groups (crate, shutter, beacon), the backdrop, decals, the glass and
    # the instanced pews stay.
    L.merge_static(crate_body)
    for o in (crate, shutter, beacon, backdrop):
        o.keep = True
    L.merge_static(group)

    # ======================================================================================== FOCAL + CAMS
    focal = L.Node('focal:altar').set_position(0, TRIP['y0'] + TRIP['h'] * 0.55, TRIP['z'])
    group.add(focal)
    out['cams_three'] = {                                  # the engine's numbers (three's axes)
        'altar': {'pos': [1.05, 1.85, 5.6], 'target': [-0.35, 1.38, -7.4], 'fov': 42},
        'pews': {'pos': [-4.75, 1.32, 1.45], 'target': [0.0, 1.0, -0.4], 'fov': 42},
        'crate': {'pos': [1.55, 1.5, -1.25], 'target': [CONV['x'] - 0.1, 0.92, 3.5], 'fov': 44},
        'close': {'pos': [0.38, face_y + 0.08, 2.15], 'target': [0.0, face_y - 0.06, 0.0], 'fov': 32},
        'board': {'pos': [0.55, 2.0, TRIP['z'] + 1.5], 'target': [0.25, 2.0, TRIP['z']], 'fov': 50},
        'hatch': {'pos': [3.15, 1.4, 2.6], 'target': [5.0, 1.0, 6.2], 'fov': 40},
        'lectern': {'pos': [-2.35, 1.62, -5.2], 'target': [-3.05, 1.05, -6.35], 'fov': 40},
        'essay': {'pos': [LECTERN['x'] - math.sin(LECTERN['yaw']) * 0.42, DAIS['h'] + 1.62,
                          LECTERN['z'] - math.cos(LECTERN['yaw']) * 0.42],
                  'target': [LECTERN['x'] + math.sin(LECTERN['yaw']) * 0.02, DAIS['h'] + 1.09,
                             LECTERN['z'] + math.cos(LECTERN['yaw']) * 0.02], 'fov': 38},
    }

    # ======================================================================================== EMIT
    sb.emit()
    for nd in (shutter, crate, beacon):                      # the moving groups: their channels are keyed
        nd.ob.rotation_mode = 'XYZ'
    out['cams'] = {k: L.cam_to_blender(v) for k, v in out['cams_three'].items()}      # Blender axes
    out['mark'] = {'pos': L.to_blender(MARK['pos']), 'yaw': float(MARK['yaw'])}     # yaw about +Z, 0 faces -Y
    out['env'] = ENV
    out['focal'] = focal.ob
    out._shutter, out._crate, out._beacon = shutter, crate, beacon
    out._beacon_light, out._tunnel_light = beacon_light, tunnel_light
    out._sale_spots, out._altar_spot, out._lamp_light = sale_spots, altar_spot, lamp_light
    out._hell_lights, out._hell_key, out._vault = hell_lights, hell_key, vault
    out._t, out._sale, out._hell = 0.0, 0.0, 1.0
    out['parts'] = {
        'crate': {'group': crate.ob, 'update': out.crate_update},
        'saleLights': {'group': sale_g.ob, 'spots': [s.ob for s in sale_spots], 'set': out.sale_set},
        'hell': {'lights': [p_.ob for p_ in hell_lights], 'key': hell_key.ob, 'vault': vault.ob, 'set': out.hell_set},
        'shutter': shutter.ob, 'beacon': beacon.ob, 'conveyor': ship_g.ob, 'altarSpot': altar_spot.ob,
        'pulpitSpot': pulpit_spot.ob, 'lampLight': lamp_light.ob, 'cityKey': city_key.ob, 'cityFill': city_fill.ob,
        'chairs': [im.ob for im in chair_meshes],
        'boards': {b['name']: b['face'].ob for b in boards},
        'singerLights': {'kicker': kicker.ob, 'kickerTarget': kick_t.ob, 'fill': front_fill.ob,
                         'fillTarget': fill_t2.ob},
        'backdrop': backdrop.ob, 'glass': glass_g.ob, 'focal': focal.ob,
        'uniforms': {u: f'["{u}"]' for u in ('uT', 'uHell', 'uSale', 'uRoll', 'uBeacon')},
    }
    out.nodes = {'group': group, 'boards': boards, 'crate': crate, 'shutter': shutter, 'beacon': beacon,
                 'chairs': chair_meshes, 'backdrop': backdrop, 'seats': seats, 'towers': towers}
    # the room-fitted volume probe (look.lighting.add_room_probe: its outermost samples inside the floor and ceiling
    # slabs and the core wall, beyond the glass in the open air the glass lets in), parented to the set
    out['probe'] = None
    if probe:
        from ...look import lighting as LL
        from mathutils import Matrix
        lo = L.to_blender((-RX, 0.0, RZ1))
        hi = L.to_blender((RX, RH, RZ0))
        pr = LL.add_room_probe(sb.scene, f'{name}:probe', (min(lo[0], hi[0]), min(lo[1], hi[1]), min(lo[2], hi[2])),
                               (max(lo[0], hi[0]), max(lo[1], hi[1]), max(lo[2], hi[2])), wall=SLAB,
                               spacing=probe_spacing, samples=probe_samples, collection=sb.coll)
        sb.made['objects'].append(pr)
        sb.made['probes'].append(pr.data)
        pr.parent = sb.root_ob
        pr.matrix_parent_inverse = Matrix.Identity(4)
        out['probe'] = pr
        out['parts']['probe'] = pr
    out.update(0.0, {}, key=False)
    return out
