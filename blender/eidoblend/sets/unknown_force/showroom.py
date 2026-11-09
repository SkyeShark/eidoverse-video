"""showroom: the showroom, a free set from eidoverse's UNKNOWN FORCE work; the Blender 5.2 EEVEE edition of
eidoverse/sets/unknown_force/showroom.js.

A cold white product-launch stage in a black void. A big white turntable is the product's place; behind it a 13 m
LED wall shows an ENGINE assembly drawing whose exploded parts all point their callouts at whoever stands on it.
Beside it, on a white plinth under its own spotlight, a chrome toaster with the only warning ever written for a
toaster: THIS APPLIANCE IS NOT CONSCIOUS. Rows of empty theatre seats, their seats folded up, fade into the dark.
The LED wall plays any picture, movie or image sequence a new piece gives it (build(screen_media=...)); every
printed thing is a canvas it can redraw (build(art=...)); the turntable, the wall's progress bar, the blackout and
the beams run on the piece's own clock.

    from eidoblend.sets.unknown_force import showroom as SR
    show = SR.build(scene)                                 # -> Showroom: group, parts, update, cams, mark ...
    scene.world = show.env
    show.eevee_settings(scene); show.bake_probes()
    rider.parent = show.parts['turntable']['platter']      # anything on the mark turns with the platter
    show.animate((1, 240), spin=lambda t: 0.35 * t, seq=(0.0, 6.0), lights=(7.0, 7.5, 1.0, 0.0))

Set-local metres in three's axes (+Y up). The mark is the origin, facing +Z (Blender: facing -Y), on the turntable's
top (y = 0); the stage deck is at y = -0.14 and the auditorium floor at y = -1.04 (the set extends below y = 0 by
design). The set is enclosed in its own black void; its lights live in the set's collection (show(False) hides them).
Camera far: 60 m is plenty (make_camera uses 100).

How the engine's pieces became Blender data: as quiet_room.py describes (uniforms on the root Empty read through
drivers, keyed by update(); the env as every material's own light at its own intensity (env_light='material': the
chrome x 2.2, the seats x 0.25), show.env the World the camera sees; three's light units; static merging; canvases
drawn by pure Python painters listed in CANVASES and cacheable with draw_canvases). Specific to the showroom:
  void         the 44 x 22 x 46 m black box is seen by the camera only: it is left out of the probes, so the probe
               bake and the reflections see the set's env (softbox strips, the bounce card, the wall glow, the floor
               bounce), as every engine material saw its envMap through the void
  toaster      three-bvh-csg's slots: Blender's exact Boolean (DIFFERENCE), the slot walls in the dark element
               material; the decals the engine pulled forward with polygonOffset sit 0.6 mm off their surface
  LED wall     the RGB-dot structure fades in where fwidth(px) is small: here the screen-pixel footprint at the
               wall (view distance x the camera's pixel angle / the facing); the pixel angle is the uniform
               uPixelAngle, which update() computes from the shot's camera and keys. screen_media plays a clip
               there through the Image Texture node's image user (frame_start, cyclic, auto refresh), fitted to
               the wall's 13 x 5.6 m (screen_fit 'fit' letterboxes in LED black, 'fill' crops, 'stretch')
  beams        additive cones (three's AdditiveBlending, SRC_ALPHA, ONE: colour x a x a over the frame)
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np

from . import interiors_lib as L
from . import showroom_art as SA
from .showroom_art import SCREEN, SEQBAR

SUIT_SCALE = 0.87
MARK = {'pos': [0, 0, 0], 'yaw': 0, 'parent': 'turntable.platter'}

STAGE = {'y': -0.14, 'x': 9.0, 'z0': -6.4, 'z1': 3.4}
FLOOR_Y = -1.04
TT = {'r': 1.5}
SCR = {'w': SCREEN['w'], 'h': SCREEN['h'], 'y0': 0.45, 'z': -5.7}
PLINTH = {'x': -3.2, 'z': 0.45, 'w': 0.56, 'h': 1.06}
ROWS, ROW0, ROWP, RISE, SEATP = 14, 4.9, 1.05, 0.24, 0.6
TRUSS = {'y': 7.0, 'zs': [2.0, -3.4], 'x': 9.5}


# ================================================================================================ the canvases
def draw_platter(ctx, W=2048, H=2048):
    """the turntable's top: white lacquer printed with rings, 5 degree ticks, degree numbers, a gaffer-tape X at the
    mark and its label."""
    c, R = W / 2, W / 2 - 4
    ctx.fillStyle = '#eef0f2'
    ctx.fillRect(0, 0, W, W)
    ctx.strokeStyle = 'rgba(70,80,96,0.18)'
    rr = 0.1
    while rr < 1.0:
        ctx.lineWidth = 2 if rr > 0.66 else 1.2
        ctx.beginPath()
        ctx.arc(c, c, R * rr, 0, math.pi * 2)
        ctx.stroke()
        rr += 0.0333
    ctx.fillStyle = '#3b4656'
    for d in range(0, 360, 5):
        a = d * math.pi / 180
        long_ = d % 30 == 0
        r0, r1 = R * (0.86 if long_ else 0.91), R * 0.965
        ctx.save()
        ctx.translate(c, c)
        ctx.rotate(a)
        ctx.fillRect(r0, -(4 if long_ else 2), r1 - r0, 8 if long_ else 4)
        if long_:
            ctx.translate(R * 0.79, 0)
            ctx.rotate(math.pi / 2)
            ctx.font = '46px "UF Michroma"'
            ctx.textAlign = 'center'
            ctx.fillText(str(d), 0, 16)
        ctx.restore()
    ctx.strokeStyle = 'rgba(59,70,86,0.5)'
    ctx.lineWidth = 6
    ctx.beginPath()
    ctx.arc(c, c, R * 0.98, 0, math.pi * 2)
    ctx.stroke()
    ctx.save()
    ctx.translate(c, c)
    for a in (0.785, -0.785):
        ctx.save()
        ctx.rotate(a)
        ctx.fillStyle = '#5d7088'
        ctx.fillRect(-150, -22, 300, 44)
        ctx.fillStyle = 'rgba(255,255,255,0.08)'
        for i in range(30):
            ctx.fillRect(-150 + i * 10, -22, 2, 44)
        ctx.restore()
    ctx.fillStyle = '#3b4656'
    ctx.font = '40px "UF Mono"'
    ctx.textAlign = 'center'
    ctx.fillText('UNIT 01', 0, 230)
    ctx.restore()


def platter_roughness(R, G, B, A, X, Y):
    """the platter's roughness from its print (vectorised derivedTexture): lacquer glossy, ink and tape matte."""
    mx, mn = np.maximum(np.maximum(R, G), B), np.minimum(np.minimum(R, G), B)
    sat, lum = (mx - mn) / 255, (R + G + B) / 765
    v = 0.12 + np.where(lum < 0.6, 0.25, 0.0) + np.where((sat > 0.1) & (lum < 0.6), 0.5, 0.0)
    q = np.floor(np.clip(v, 0, 1) * 255 + 0.5)
    return q, q, q


def draw_toast(ctx, W=512, H=512):
    """toast: a browned crust, a golden crumb, 1600 toasted pores."""
    r = L.rng(99)
    ctx.fillStyle = '#7a3f12'
    ctx.fillRect(0, 0, 512, 512)
    g = ctx.createRadialGradient(256, 300, 40, 256, 300, 300)
    g.addColorStop(0, '#d9a25b')
    g.addColorStop(0.7, '#c27f37')
    g.addColorStop(1, '#8a4a18')
    ctx.fillStyle = g
    ctx.fillRect(28, 28, 456, 456)
    for _ in range(1600):
        x, y, rr = 30 + r() * 452, 30 + r() * 452, 1 + r() * 4
        ctx.fillStyle = f'rgba({90 + r() * 40},{45 + r() * 20},{15},{0.25 + r() * 0.4})'
        ctx.beginPath()
        ctx.ellipse(x, y, rr, rr * (0.5 + r()), r() * 3, 0, math.pi * 2)
        ctx.fill()


def draw_exit(ctx, W=256, H=96):
    """the green EXIT signs at the back corners."""
    ctx.fillStyle = '#021a0c'
    ctx.fillRect(0, 0, 256, 96)
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 66px "UF Rajdhani"'
    ctx.textAlign = 'center'
    ctx.fillText('EXIT', 128, 72)


# every canvas the set draws: key -> (width, height, painter(ctx, W, H)); pure Python
CANVASES = {
    'engine_sheet': (SCREEN['W'], SCREEN['H'], SA.draw_engine_sheet),
    'platter': (2048, 2048, draw_platter),
    'warning': (920, 1240, SA.draw_warning),
    'dial': (256, 256, SA.draw_dial),
    'rating_plate': (512, 180, SA.draw_rating_plate),
    'toast': (512, 512, draw_toast),
    'exit': (256, 96, draw_exit),
}
_VERSION = []


def _art_version():
    """a hash of the drawing code only (these painters, the art module, the canvas half of interiors_lib)."""
    if _VERSION:
        return _VERSION[0]
    import inspect
    h = hashlib.sha1()
    here = Path(__file__).resolve().parent
    lib = (here / 'interiors_lib.py').read_text(encoding='utf-8').split('"""', 2)[2]     # without its docstring
    h.update(lib.split('# THE BLENDER HALF')[0].encode())
    h.update((here / 'showroom_art.py').read_bytes())
    for fn in (draw_platter, draw_toast, draw_exit):
        h.update(inspect.getsource(fn).encode())
    _VERSION.append(h.hexdigest()[:12])
    return _VERSION[0]


def draw_canvas(key, cache=None):
    """One canvas of the set, drawn (or read back from `cache` when the same code drew it before)."""
    W, H, paint = CANVASES[key]
    path = None
    if cache:
        path = Path(cache) / f'sr_{key}_{_art_version()}.png'
        if path.is_file():
            return L.Canvas.from_png(path)
    cv, ctx = L.canvas(L.napi(), W, H)
    paint(ctx, W, H)
    if path is not None:
        cv.save_png(path)
    return cv


def draw_canvases(cache, keys=None):
    """Pre-draw every canvas of the set into `cache` (system Python). Returns {key: seconds}."""
    import time
    out = {}
    for k in keys or CANVASES:
        t = time.perf_counter()
        draw_canvas(k, cache)
        out[k] = round(time.perf_counter() - t, 2)
    return out


def canvas_for(key, art=None, cache=None):
    """The canvas `key` as build() puts it in the set: the piece's own when `art` has it (a painter fn(ctx, W, H),
    an image path, a Pillow image, a uint8 array or a Canvas, at CANVASES[key][:2]: interiors_lib.override_canvas),
    else the set's own (draw_canvas, through the cache)."""
    if key not in CANVASES:
        raise KeyError(f'showroom: no canvas {key!r} (canvases: {", ".join(CANVASES)})')
    o = (art or {}).get(key)
    if o is None:
        return draw_canvas(key, cache)
    W, H, _paint = CANVASES[key]
    return L.override_canvas(o, W, H)


SCREEN_FITS = ('fit', 'fill', 'stretch')


def screen_fit_scale(aspect, fit='fit', wall=SCREEN['w'] / SCREEN['h']):
    """How a picture of `aspect` (w / h) sits on the LED wall: the (sx, sy) its uv is scaled by about the centre,
    uv' = (uv - 0.5) * (sx, sy) + 0.5 ('fit': the whole picture, LED black beside or above it; 'fill': the wall
    covered, the picture cropped; 'stretch': (1, 1))."""
    if fit not in SCREEN_FITS:
        raise ValueError(f'screen_fit: {fit!r} (want one of {", ".join(SCREEN_FITS)})')
    if fit == 'stretch' or not aspect or abs(aspect - wall) < 1e-6:
        return 1.0, 1.0
    k = wall / aspect                       # > 1: the picture is narrower than the wall
    if fit == 'fit':
        return (k, 1.0) if k > 1 else (1.0, 1.0 / k)
    return (1.0, 1.0 / k) if k > 1 else (k, 1.0)


# ================================================================================================ the room's light (env)
def env_paint(x, y, z):
    """the room's light: a black void, two softbox strips overhead, the LED wall behind (-Z), a faint grey floor
    bounce, a tall soft bounce card out front (product photography: what makes chrome read as chrome in a void)."""
    v = np.full_like(x, 0.006)
    wall = np.where((z < -0.55) & (y > -0.08) & (y < 0.42), np.minimum(1.0, (-z - 0.55) * 5) * 0.75, 0.0)
    strip = (np.exp(-((y - 0.93) / 0.03) ** 2) + np.exp(-((y - 0.80) / 0.025) ** 2) * 0.7) * (np.abs(x) < 0.85)
    floor_ = np.where(y < -0.02, (0.10 + 0.22 * np.minimum(1.0, (-y - 0.02) * 4))
                      * (1 - 0.6 * np.maximum(0.0, -y - 0.6)), 0.0)
    card = np.where((z > 0.35) & (np.abs(x) < 0.75),
                    np.exp(-((y - 0.12) / 0.28) ** 2) * 0.32 * np.minimum(1.0, (z - 0.35) * 3), 0.0)
    sides = np.where(np.abs(x) > 0.8, np.exp(-((y - 0.3) / 0.25) ** 2) * 0.07, 0.0)
    v = v + wall + strip * 1.0 + floor_ + card + sides
    return v * 0.94, v * 0.97, v * 1.0


def _flip(geo):
    g = geo.clone()
    if g.index is not None:
        g.index = g.index.reshape(-1, 3)[:, ::-1].ravel()
    if g.nrm is not None:
        g.nrm = -g.nrm
    return g


# ================================================================================================ the set
class Showroom(L.InteriorSet):
    """What build() returns: a dict of the engine's { group, parts, update, dispose, cams, mark, focal, env } whose
    keys also read as attributes, with the Blender side every interior shares (interiors_lib.InteriorSet)."""

    CLIP_END = 100.0               # the void is 44 x 22 x 46 m
    STATE = {'spin': 0.0, 'seq': 0.997, 'lights': 1.0, 'beams': 1.0, 'screen': 1.0}   # update()'s keys (animate)

    def animate(self, frames, t0=0.0, fps=None, ctx=None, camera=None, **state):
        """InteriorSet.animate (the set keyed over `frames` on its own clock; spin, seq, lights, beams, screen as
        state curves), with the LED wall's camera: an object, a function of the frame (a cut between cameras), or
        None (the scene's camera when animate runs)."""
        kw = (lambda f: {'camera': camera(f)}) if callable(camera) else {'camera': camera}
        return super().animate(frames, t0=t0, fps=fps, ctx=ctx, update_kw=kw, **state)

    def _apply(self, t, st, camera=None):
        self.root['uT'] = float(t)
        self.root['uPixelAngle'] = L.camera_pixel_angle(self.sb.scene, camera)
        self._platter.ob.rotation_euler = (0.0, 0.0, float(st.get('spin', 0.0) or 0.0))   # three's rotation.y
        self.root['uSeq'] = L.clamp01(st.get('seq', 0.997))
        lights = L.clamp01(st.get('lights', 1.0))
        self.root['uLights'] = lights
        self.root['uBeams'] = L.clamp01(st.get('beams', 1.0))
        self.root['uScreen'] = 0.66 * float(st.get('screen', 1.0))
        lt = self._lights
        lt['key'].ob.data.energy = lt['key'].watts(1.5 * lights)
        lt['rim'].ob.data.energy = lt['rim'].watts(2.2 * (0.4 + 0.6 * lights))
        lt['toasterSpot'].ob.data.energy = lt['toasterSpot'].watts(26 * lights)
        lt['seatSpill'].ob.data.energy = lt['seatSpill'].watts(22 * lights)
        lt['top'].ob.data.energy = lt['top'].watts(12 * lights)

    def update(self, t, state=None, frame=None, ctx=None, key=True, camera=None):
        """update(t, {spin, seq, lights, beams, screen}): the set at time t (seconds on the piece's clock: the
        progress bar's scan), keyed at `frame` (or ctx.frame_at(t), or the current frame); key=False only sets the
        values. camera: the shot's camera, whose pixel footprint the LED wall's dot structure follows (default: the
        scene's camera when update runs; pass it when markers switch cameras). A clip on the wall (screen_media)
        plays on the scene's frames, not on t."""
        self._apply(t, state or {}, camera)
        if key:
            f = self._frame(t, frame, ctx)
            k = self._keyer(ctx)
            for u in ('uT', 'uSeq', 'uLights', 'uBeams', 'uScreen', 'uPixelAngle'):
                k.key(self.root, f'["{u}"]', f)
            k.key(self._platter.ob, 'rotation_euler', f)
            for nm in ('key', 'rim', 'toasterSpot', 'seatSpill', 'top'):
                k.key(self._lights[nm].ob.data, 'energy', f)
        return self

    def set_spin(self, a, frame=None, ctx=None, key=True):
        """parts['turntable']['setSpin'](a): the platter's turn (radians), keyed when a frame is given."""
        self._platter.ob.rotation_euler = (0.0, 0.0, float(a))
        if key and (frame is not None or ctx is not None):
            self._keyer(ctx).key(self._platter.ob, 'rotation_euler', self._frame(0.0, frame, ctx))


def build(ctx=None, scene=None, singer_scale=None, collection=None, name='set:showroom', art_cache=None, probe=True,
          probe_spacing=0.5, probe_samples=1024, singerScale=None, art=None, screen_media=None, screen_fit='fit',
          seq_bar=None, env_light='material'):
    """build(THREE, opts) -> the showroom (Showroom: a dict whose keys read as attributes). As quiet_room.build
    (ctx / scene, singer_scale, art_cache, probe), and a new piece's options:
      art           {canvas key: its own art} for any of CANVASES (engine_sheet, warning, platter, dial,
                    rating_plate, toast, exit): a painter fn(ctx, W, H), an image path, a Pillow image or an array,
                    resized to the canvas (canvas_for)
      screen_media  the LED wall plays a clip instead of the ENGINE sheet: a movie, an image sequence (its first
                    numbered file) or a still, as a path or {'path', 'start' (the scene frame its first frame plays
                    on, 1), 'loop' (True), 'offset' (frames skipped, 0), 'aspect' (w / h, when Blender cannot read
                    the size)}. It plays on the scene's frames, under the wall's brightness and LED structure
      screen_fit    'fit' (default: the whole clip, LED black beside it), 'fill' (cropped to cover) or 'stretch'
      seq_bar       the SEQUENCE COMPLETION bar (uSeq) over the wall: by default only over the set's own sheet
      env_light     'material' (each material lit by the set's env at its own intensity, as the engine's envMap:
                    the chrome at x 2.2, the seats at x 0.25; the World lights nothing) or 'world' (the env as the
                    World, lighting the whole scene at one intensity)"""
    import bpy
    L.check_art(art, CANVASES, 'showroom.build(art=...)')
    if screen_fit not in SCREEN_FITS:
        raise ValueError(f'showroom.build: screen_fit={screen_fit!r} (want one of {", ".join(SCREEN_FITS)})')
    if env_light not in L.MaterialKit.ENV_LIGHTS:
        raise ValueError(f"showroom.build: env_light={env_light!r} (want 'material' or 'world')")
    scene, ctx = L.scene_and_ctx(ctx, scene)
    ss = singer_scale if singer_scale is not None else singerScale
    singer_scale = SUIT_SCALE if ss is None else ss
    face_y = 1.53 * singer_scale
    sb = L.SetBuilder(name, scene, collection)
    group = sb.root
    out = Showroom(sb, ctx)
    for u, v in (('uT', 0.0), ('uSeq', 0.997), ('uLights', 1.0), ('uBeams', 1.0), ('uScreen', 0.66),
                 ('uPixelAngle', L.DEFAULT_PIXEL_ANGLE)):
        sb.uniform(u, v)
    ENV = sb.track(L.equirect_env(512, 256, env_paint, name='ufsr_env', light=env_light == 'world'))
    sb.track(bpy.data.images[ENV['uf_env_image']])
    K = L.material_kit(sb, env=ENV, prefix='ufsr', env_light=env_light)
    out.kit = K                                              # the set's material kit: a piece's own props lit alike
    tri, pbr, solid = K.tri, K.pbr, K.solid
    S = {i: L.acg(i) for i in ('Terrazzo005', 'Terrazzo003', 'Carpet012', 'Fabric031', 'Metal009', 'Metal027')}

    def img(key, srgb=True):
        cv = canvas_for(key, art, art_cache)
        return sb.track(L.canvas_texture(cv, srgb=srgb, name=f'ufsr_{key}')), cv

    def add(geo, mat, pos=(0, 0, 0), rot=(0, 0, 0), parent=None, cast=True, recv=True, keep=False, name=''):
        m = L.MeshNode(geo, mat, name=name or (mat.name.split('-', 1)[-1] if mat is not None else 'mesh'),
                       cast=cast, recv=recv, keep=keep)
        m.set_position(*pos)
        m.set_rotation(*rot[:3], order=rot[3] if len(rot) > 3 else 'XYZ')
        (parent or group).add(m)
        return m

    def box(w, h, d):
        return L.box_uv(L.box_geometry(w, h, d), 1)

    def rbox(w, h, d, seg=2, r=0.02):
        return L.box_uv(L.rounded_box_geometry(w, h, d, seg, r), 1)

    def cyl(r0, r1, h, seg=24, open_=False):
        return L.box_uv(L.cylinder_geometry(r0, r1, h, seg, 1, open_), 1)

    def grp(nm, parent=None):
        n_ = L.Node(nm)
        (parent or group).add(n_)
        return n_

    # ---------------------------------------------------------------------------------------- materials
    stage_mat = pbr('stage', S['Terrazzo005'], tint=(0.50, 0.52, 0.56), tile=1 / 0.7, rough=0.5, vary=0.10, env_i=0.9)
    floor_mat, g = K.new('aud-floor')                        # auditorium carpet, darkening with distance from the stage
    tuv = g.uv() * (1 / 0.6)
    pile = g.texture(S['Carpet012']['map'], tuv).rgb
    lum = pile.x * 0.3 + pile.y * 0.59 + pile.z * 0.11
    fade = g.exp(g.max(g.position_local().z - 5.0, 0.0) * -0.11)
    g.standard(color=g.vec3(lum) * (0.42, 0.44, 0.50) * (fade * 0.85 + 0.15), roughness=0.95,
               normal=g.normal_map(g.texture(S['Carpet012']['normalMap'], tuv).rgb, 0.8))
    K.envd(floor_mat, 0.2)
    black_mat = solid('black', (0.012, 0.012, 0.014), rough=0.8, vary=0.3, scale=1.5, env_i=0.3)
    brushed = pbr('brushed', S['Metal009'], tint=(0.95, 0.96, 0.98), tile=1 / 0.4, rough=0.55, metal=1, env_i=1.6)
    truss_mat = pbr('truss', S['Metal009'], tint=(0.80, 0.82, 0.85), tile=1 / 0.25, rough=0.8, metal=1, env_i=1.0)
    powder = pbr('powder', S['Metal027'], tint=(0.30, 0.31, 0.33), tile=1 / 0.5, rough=1.0, metal=1, env_i=0.8)
    velvet, g = K.new('velvet')
    n = tri(g, 0.8)
    g.standard(color=g.vec3(0.010, 0.010, 0.012) * (n.z * 0.6 + 0.7), roughness=0.95, metalness=0.0, sheen=1.0,
               sheen_tint=(0.10, 0.10, 0.12), sheen_roughness=0.45)
    K.envd(velvet, 0.3)
    plinth_mat, g = K.new('plinth')                          # white solid surface: soft sheen, faint scuffs low down
    n, n2 = tri(g, 3.0), tri(g, 17.0)
    scuff = g.smoothstep(0.25, 0.0, g.position_local().y + PLINTH['h'] / 2) * n2.x
    g.standard(color=g.vec3(0.86, 0.87, 0.88) * ((n.z - 0.5) * 0.05 + 1) * (1.0 - scuff * 0.25),
               roughness=g.clamp(0.32 + (n.y - 0.5) * 0.12 + (n2.w - 0.5) * 0.08, 0.05, 1.0), metalness=0.0)
    K.envd(plinth_mat, 1.0)
    chrome, g = K.new('chrome')                              # toaster chrome: mirror with fingerprint and wipe smudges
    n, n2 = tri(g, 14.0), tri(g, 55.0)
    smudge = g.smoothstep(0.55, 0.85, n.x) * 0.6 + g.smoothstep(0.62, 0.9, n2.y) * 0.4
    g.standard(color=g.vec3(0.93, 0.94, 0.96) * (1.0 - smudge * 0.06),
               roughness=g.clamp(0.035 + smudge * 0.16, 0.02, 1.0), metalness=1.0, coat=0.0)
    K.envd(chrome, 2.2)
    bakelite = solid('bakelite', (0.012, 0.011, 0.011), rough=0.22, rough_var=0.08, vary=0.25, scale=30, env_i=1.6)
    rubber = solid('rubber', (0.015, 0.015, 0.016), rough=0.75, rough_var=0.1, vary=0.2, scale=20, env_i=0.5)
    slot_mat, g = K.new('toaster-slot')
    wires = g.smoothstep(0.35, 0.5, g.abs(g.fract(g.position_local().y / 0.0065) - 0.5))
    g.standard(color=g.mix((0.012, 0.011, 0.01), (0.18, 0.16, 0.14), wires), roughness=0.6, metalness=0.7)
    K.envd(slot_mat, 0.8)

    # ======================================================================================== VOID, STAGE, AUDITORIUM
    # an enclosing black box (inner faces) so the scene's sky never shows: the launch happens in a void
    void_mat, g = K.new('void')
    n = tri(g, 0.15)
    g.basic(g.vec3(0.0035, 0.0038, 0.0045) * (n.x * 0.8 + 0.6))
    void_mat.use_backface_culling = True
    L.hide_from_probes(void_mat, volume=True, sphere=True)
    add(_flip(L.box_geometry(44, 22, 46).translate(0, 8, 8)), void_mat, cast=False, recv=False, keep=True, name='void')
    stage_g = grp('sr:stage')
    sw, sd = 2 * STAGE['x'], STAGE['z1'] - STAGE['z0']
    top = L.plane_geometry(sw, sd).rotate_x(-math.pi / 2).translate(0, STAGE['y'], (STAGE['z0'] + STAGE['z1']) / 2)
    add(L.box_uv(top, 1), stage_mat, parent=stage_g, cast=False, name='stage')
    # the stage's front fascia: matte black with a cold LED line under the nosing
    add(box(sw, STAGE['y'] - FLOOR_Y, 0.04), black_mat, (0, (STAGE['y'] + FLOOR_Y) / 2, STAGE['z1'] + 0.02), parent=stage_g)
    add(box(sw + 0.02, 0.03, 0.06), brushed, (0, STAGE['y'] - 0.015, STAGE['z1'] + 0.01), parent=stage_g)
    led_m, g = K.new('stage-led')
    g.basic(g.vec3(0.85, 0.93, 1.0) * (g.uniform('uLights') * 3.0 + 0.05))
    L.hide_from_probes(led_m)
    add(box(sw, 0.012, 0.012), led_m, (0, STAGE['y'] - 0.045, STAGE['z1'] + 0.045), parent=stage_g, cast=False,
        keep=True, name='stage-led')
    # auditorium floor and the risers the seats stand on
    af = L.plane_geometry(2 * STAGE['x'] + 2, 22).rotate_x(-math.pi / 2).translate(0, FLOOR_Y, STAGE['z1'] + 11)
    add(L.box_uv(af, 1), floor_mat, parent=stage_g, cast=False, name='aud-floor')
    for k_ in range(1, ROWS):
        z0 = ROW0 + k_ * ROWP - 0.55
        zz = 22.5 - z0
        add(box(2 * STAGE['x'], RISE, zz), floor_mat, (0, FLOOR_Y + (k_ - 0.5) * RISE, z0 + zz / 2), parent=stage_g,
            cast=False)

    # black masking: velvet legs at the sides, a border above the wall, the wall's own black frame
    def drape(w, h, folds):
        dg = L.plane_geometry(w, h, int(math.floor(w * 12 + 0.5)), 1)
        x_ = dg.pos[:, 0]
        dg.pos[:, 2] = 0.09 * np.sin(x_ / w * math.pi * 2 * folds) + 0.03 * np.sin(x_ / w * math.pi * 2 * folds * 2.7)
        return dg.compute_vertex_normals()
    for sx in (-1, 1):
        add(drape(3.2, 9.0, 5), velvet, (sx * (STAGE['x'] - 0.3), STAGE['y'] + 4.5, STAGE['z0'] + 1.8),
            (0, sx * math.pi / 2, 0), stage_g, keep=True, name='leg')
        add(drape(2.4, 9.0, 4), velvet, (sx * (SCR['w'] / 2 + 1.4), STAGE['y'] + 4.5, SCR['z'] - 0.2), parent=stage_g,
            keep=True, name='leg')
    add(drape(SCR['w'] + 4, 1.5, 9), velvet, (0, SCR['y0'] + SCR['h'] + 0.9, SCR['z'] + 0.05), parent=stage_g,
        keep=True, name='border')
    fr = 0.14
    add(box(SCR['w'] + 2 * fr, fr, 0.2), black_mat, (0, SCR['y0'] + SCR['h'] + fr / 2, SCR['z'] - 0.05), parent=stage_g)
    add(box(SCR['w'] + 2 * fr, fr, 0.2), black_mat, (0, SCR['y0'] - fr / 2, SCR['z'] - 0.05), parent=stage_g)
    add(box(fr, SCR['h'], 0.2), black_mat, (-SCR['w'] / 2 - fr / 2, SCR['y0'] + SCR['h'] / 2, SCR['z'] - 0.05),
        parent=stage_g)
    add(box(fr, SCR['h'], 0.2), black_mat, (SCR['w'] / 2 + fr / 2, SCR['y0'] + SCR['h'] / 2, SCR['z'] - 0.05),
        parent=stage_g)
    add(box(SCR['w'], SCR['y0'] - STAGE['y'], 0.3), black_mat, (0, (SCR['y0'] + STAGE['y']) / 2, SCR['z'] - 0.1),
        parent=stage_g)

    # ======================================================================================== THE LED WALL
    screen_g = grp('sr:screen')
    media = None
    if screen_media is not None:
        ms = dict(screen_media) if isinstance(screen_media, dict) else {'path': screen_media}
        sheet_tex, minfo = L.media_image(ms['path'], name='ufsr_screen_media')
        sb.track(sheet_tex)
        size = minfo['size']
        media = {'image': sheet_tex, 'frames': minfo['frames'], 'start': int(ms.get('start', 1)),
                 'loop': bool(ms.get('loop', True)), 'offset': minfo['offset'] + int(ms.get('offset', 0)),
                 'aspect': float(ms.get('aspect') or (size[0] / size[1] if size else 0.0)) or None,
                 'fit': screen_fit if (ms.get('aspect') or size) else 'stretch'}
    else:
        sheet_tex, _cv = img('engine_sheet')
    if seq_bar is None:
        seq_bar = screen_media is None and 'engine_sheet' not in (art or {})
    screen_mat, g = K.new('ledwall')
    p = g.uv()
    if media is not None:
        sx, sy = screen_fit_scale(media['aspect'], media['fit'])
        q = p if (sx, sy) == (1.0, 1.0) else (p - (0.5, 0.5, 0.0)) * (sx, sy, 1.0) + (0.5, 0.5, 0.0)
        col = g.texture(sheet_tex, q, extension='CLIP').rgb             # CLIP: LED black outside the picture
        media['scale'] = (sx, sy)
    else:
        col = g.texture(sheet_tex, p).rgb
    u_seq, u_t = g.uniform('uSeq'), g.uniform('uT')
    if seq_bar:
        # SEQUENCE COMPLETION: the bar fills to uSeq, with a slow scan inside the filled part
        cy = 1.0 - p.y
        in_x = g.step(SEQBAR['x0'] + 0.002, p.x) * g.step(p.x, g.mix(SEQBAR['x0'] + 0.002, SEQBAR['x1'] - 0.002,
                                                                     u_seq))
        in_y = g.step(SEQBAR['y0'] + 0.006, cy) * g.step(cy, SEQBAR['y1'] - 0.006)
        scan = g.smoothstep(0.0, 0.08, g.fract(p.x * 40.0 - u_t * 0.6)) * 0.25 + 0.75
        col = g.mix(col, g.vec3(0.08, 0.12, 0.2) * scan, in_x * in_y)
    # LED pixels: an RGB-dot grid that only appears when the wall is close enough to resolve it
    px_ = p * (SCREEN['W'], SCREEN['H'], 0.0)
    cell = g.fract(px_)
    dotm = g.smoothstep(0.48, 0.30, (cell - (0.5, 0.5, 0.0)).length())
    texel = SCR['w'] / SCREEN['W']
    fw = g.view_distance() * g.pixel_angle() / g.max(g.facing(), 0.15) / texel        # fwidth(px.x), in texels
    resolve = g.smoothstep(0.7, 0.3, fw)
    led = g.mix(1.0, dotm * 1.6 + 0.08, resolve)
    g.basic(col * led * g.uniform('uScreen'))
    L.hide_from_probes(screen_mat)
    if media is not None and sheet_tex.source in ('MOVIE', 'SEQUENCE'):
        # the clip plays on the scene's frames: the Image Texture node's image user
        for n_ in screen_mat.node_tree.nodes:
            if n_.bl_idname == 'ShaderNodeTexImage' and n_.image == sheet_tex:
                iu = n_.image_user
                iu.frame_duration = media['frames']
                iu.frame_start = media['start']
                iu.frame_offset = media['offset']
                iu.use_cyclic = media['loop']
                iu.use_auto_refresh = True
                media['image_user'] = iu
    wall = add(L.plane_geometry(SCR['w'], SCR['h']), screen_mat, (0, SCR['y0'] + SCR['h'] / 2, SCR['z']),
               parent=screen_g, cast=False, recv=False, keep=True, name='ledwall')

    # ======================================================================================== THE TURNTABLE
    tt_g = grp('sr:turntable')
    platter = L.Node('turntable.platter')
    tt_g.add(platter)
    # static base: brushed steel drum with a cold LED line where it meets the stage
    add(cyl(TT['r'] - 0.04, TT['r'] - 0.02, -STAGE['y'] - 0.03, 96, True), brushed, (0, (STAGE['y'] - 0.03) / 2, 0),
        parent=tt_g, name='drum')
    base_led, g = K.new('tt-baseled')
    g.basic(g.vec3(0.8, 0.9, 1.0) * (g.uniform('uLights') * 2.4 + 0.04))
    L.hide_from_probes(base_led)
    add(L.cylinder_geometry(TT['r'] - 0.015, TT['r'] - 0.015, 0.01, 128, 1, True), base_led, (0, STAGE['y'] + 0.012, 0),
        parent=tt_g, cast=False, keep=True, name='tt-baseled')
    # the platter top: white lacquer printed with rings, degree ticks and a tape X at the mark
    ptex, pcv = img('platter')
    prough = sb.track(L.derived_texture(pcv, platter_roughness, name='ufsr_platter_rough'))
    top_m, g = K.new('tt-top')
    pl = g.position_local()
    tuv = g.vec2(pl.x / (2 * TT['r']) + 0.5, -pl.z / (2 * TT['r']) + 0.5)
    n = tri(g, 4.0)
    g.standard(color=g.texture(ptex, tuv).rgb * ((n.z - 0.5) * 0.04 + 1),
               roughness=g.clamp(g.texture(prough, tuv).r + (n.y - 0.5) * 0.06, 0.04, 1.0), metalness=0.0,
               coat=1.0, coat_roughness=0.05)
    K.envd(top_m, 1.4)
    add(L.cylinder_geometry(TT['r'], TT['r'], 0.03, 128), top_m, (0, -0.015, 0), parent=platter, keep=True,
        name='tt-top')
    # the platter's polished rim and its running LED dashes (they show the turn)
    add(L.cylinder_geometry(TT['r'] + 0.006, TT['r'] + 0.006, 0.034, 128, 1, True), chrome, (0, -0.015, 0),
        parent=platter, keep=True, name='tt-rim')
    rim_led, g = K.new('tt-rimled')
    pl = g.position_local()
    a = g.atan2(pl.z, pl.x)
    dash = g.step(0.35, g.fract(a * (36.0 / (2 * math.pi))))
    g.basic(g.vec3(0.85, 0.93, 1.0) * (dash * 2.6 + 0.15) * (g.uniform('uLights') * 0.9 + 0.1))
    L.hide_from_probes(rim_led)
    add(L.cylinder_geometry(TT['r'] + 0.008, TT['r'] + 0.008, 0.006, 192, 1, True), rim_led, (0, -0.026, 0),
        parent=platter, cast=False, keep=True, name='tt-rimled')

    # ======================================================================================== THE TOASTER ON ITS PLINTH
    toaster_g = grp('sr:toaster')
    toaster_g.set_position(PLINTH['x'], STAGE['y'], PLINTH['z'])
    add(rbox(PLINTH['w'], PLINTH['h'], PLINTH['w'], 3, 0.012), plinth_mat, (0, PLINTH['h'] / 2, 0), parent=toaster_g,
        name='plinth')
    # the WARNING placard on the plinth's audience face
    wt, _cv = img('warning')
    wm, g = K.new('warning')
    n = tri(g, 40.0)
    g.standard(color=g.texture(wt, g.uv()).rgb * (n.x * 0.06 + 0.96),
               roughness=g.clamp(0.42 + (n.y - 0.5) * 0.1, 0.2, 1.0), metalness=0.0)
    K.envd(wm, 0.6)
    add(box(0.47, 0.632, 0.006), black_mat, (0, PLINTH['h'] * 0.56, PLINTH['w'] / 2 + 0.003), parent=toaster_g)
    add(L.plane_geometry(0.46, 0.62), wm, (0, PLINTH['h'] * 0.56, PLINTH['w'] / 2 + 0.0065), parent=toaster_g,
        keep=True, cast=False, name='warning')
    # the toaster: a chrome loaf with two real slots (CSG), bakelite lever and knob, feet, toast, a cord to nowhere
    toaster = L.Node('toaster')
    toaster.set_position(0, PLINTH['h'], 0)
    toaster.set_rotation(0, -0.5, 0)
    toaster_g.add(toaster)
    Lx, Hy, Dz, bev, bevT = 0.29, 0.205, 0.19, 0.024, 0.03
    sh = L.Shape()
    w, h, rt, rb = Lx - 2 * bev, Hy - 2 * bev - 0.012, 0.055, 0.012
    sh.move_to(-w / 2 + rb, 0).line_to(w / 2 - rb, 0).quadratic_curve_to(w / 2, 0, w / 2, rb)
    sh.line_to(w / 2, h - rt).quadratic_curve_to(w / 2, h, w / 2 - rt, h)
    sh.line_to(-w / 2 + rt, h).quadratic_curve_to(-w / 2, h, -w / 2, h - rt)
    sh.line_to(-w / 2, rb).quadratic_curve_to(-w / 2, 0, -w / 2 + rb, 0)
    body = L.extrude_geometry(sh, depth=Dz - 2 * bevT, bevel_enabled=True, bevel_size=bev, bevel_thickness=bevT,
                              bevel_segments=7, curve_segments=16)
    body.translate(0, bev + 0.012, -(Dz - 2 * bevT) / 2)
    body.delete_attribute('uv').delete_attribute('normal')
    body = L.merge_vertices(body, 1e-5).compute_vertex_normals()
    # the two slots (one cutter: both boxes merged)
    slot_l, slot_w, slot_d = 0.14, 0.03, 0.11
    c1 = L.box_geometry(slot_l, slot_d + 0.05, slot_w).to_non_indexed().translate(-0.012, Hy - slot_d / 2 + 0.02, 0.043)
    c2 = L.box_geometry(slot_l, slot_d + 0.05, slot_w).to_non_indexed().translate(-0.012, Hy - slot_d / 2 + 0.02, -0.043)
    for c_ in (c1, c2):
        c_.delete_attribute('uv')
    cutter = L.merge_vertices(L.merge_geometries([c1, c2]), 1e-6)
    body_node = L.CSGMeshNode(body, chrome, cutter, slot_mat, name='toaster-body')
    toaster.add(body_node)
    for z_ in (0.043, -0.043):                               # slot floors (dark) so the slots read as deep
        add(box(slot_l, 0.004, slot_w), slot_mat, (-0.012, Hy - slot_d + 0.02, z_), parent=toaster)
    add(rbox(Lx - 0.02, 0.012, Dz - 0.025, 2, 0.004), bakelite, (0, 0.009, 0), parent=toaster)    # base plate + feet
    for x_, z_ in ((-0.12, -0.07), (0.12, -0.07), (-0.12, 0.07), (0.12, 0.07)):
        add(cyl(0.009, 0.008, 0.006, 16), rubber, (x_, 0.003, z_), parent=toaster)
    # lever (up: the toast has popped) in a dark track on the +X end, and the browning knob below it
    add(box(0.004, 0.11, 0.012), slot_mat, (Lx / 2 + 0.0005, 0.12, 0), parent=toaster)
    add(rbox(0.045, 0.016, 0.034, 2, 0.006), bakelite, (Lx / 2 + 0.02, 0.165, 0), parent=toaster)
    add(cyl(0.018, 0.019, 0.016, 32), bakelite, (Lx / 2 + 0.007, 0.06, 0), (0, 0, math.pi / 2), toaster)
    add(cyl(0.007, 0.007, 0.004, 24), chrome, (Lx / 2 + 0.0155, 0.06, 0), (0, 0, math.pi / 2), toaster)
    add(box(0.002, 0.012, 0.003), chrome, (Lx / 2 + 0.0155, 0.068, 0), parent=toaster)
    dt, _cv = img('dial')
    dm, g = K.new('dial')
    g.standard(color=g.texture(dt, g.uv()).rgb, roughness=0.4, metalness=0.3)
    K.envd(dm, 1.0)
    # (the engine drew the dial 0.5 mm inside the end face and won the depth test with polygonOffset; Blender has no
    # depth bias, so the decal sits 0.6 mm outside the surface instead)
    add(L.plane_geometry(0.056, 0.056), dm, (Lx / 2 + 0.0006, 0.06, 0), (0, math.pi / 2, 0), toaster, keep=True,
        cast=False, name='dial')
    rt2, _cv = img('rating_plate')                         # the rating plate on the audience side
    rm, g = K.new('ratingplate')
    g.standard(color=g.texture(rt2, g.uv()).rgb, roughness=0.35, metalness=0.6)
    K.envd(rm, 1.2)
    add(L.plane_geometry(0.06, 0.021), rm, (0.075, 0.045, Dz / 2 + 0.0006), parent=toaster, keep=True, cast=False,
        name='ratingplate')
    # toast: golden slices standing up out of both slots
    bt, _cv = img('toast')
    bm, g = K.new('toast')
    g.standard(color=g.texture(bt, g.uv()).rgb, roughness=0.9, metalness=0.0)
    K.envd(bm, 0.3)
    sl = L.Shape()
    bw, bh = 0.118, 0.118
    sl.move_to(-bw / 2, 0).line_to(bw / 2, 0).line_to(bw / 2, bh * 0.7)
    sl.bezier_curve_to(bw / 2 + 0.012, bh * 0.98, bw * 0.12, bh * 1.04, 0, bh * 0.92)
    sl.bezier_curve_to(-bw * 0.12, bh * 1.04, -bw / 2 - 0.012, bh * 0.98, -bw / 2, bh * 0.7)
    sl.line_to(-bw / 2, 0)
    slice_ = L.extrude_geometry(sl, depth=0.011, bevel_enabled=True, bevel_size=0.002, bevel_thickness=0.002,
                                bevel_segments=2).translate(0, 0, -0.0055)
    slice_.uv = np.stack([(slice_.pos[:, 0] + bw / 2 + 0.014) / (bw + 0.028), slice_.pos[:, 1] / (bh * 1.06)], axis=1)
    for z_ in (0.043, -0.043):
        add(slice_.clone(), bm, (-0.012, Hy - 0.07, z_), parent=toaster, name='toast')
    # the cord: out of the back, across the plinth, over the edge, hanging; it is not plugged into anything
    pts = [(-0.1, 0.02, -Dz / 2), (-0.12, 0.004, -Dz / 2 - 0.06), (-0.06, 0.004, -0.2), (0.05, 0.004, -0.255),
           (0.09, -0.02, -0.282), (0.10, -0.25, -0.285), (0.07, -0.48, -0.29)]
    add(L.box_uv(L.tube_geometry(L.CatmullRomCurve3(pts), 60, 0.0035, 8), 1), rubber, parent=toaster, name='cord')
    add(rbox(0.022, 0.03, 0.014, 2, 0.003), bakelite, (0.07, -0.5, -0.29), (0, 0, 0.1), toaster, name='plug')
    for sx in (-1, 1):
        add(box(0.0015, 0.016, 0.006), chrome, (0.07 + sx * 0.005 - 0.002, -0.522, -0.29), (0, 0, 0.1), toaster)
    toaster_focus = grp('toasterFocus').set_position(PLINTH['x'], STAGE['y'] + PLINTH['h'] + 0.1, PLINTH['z'])

    # ======================================================================================== EMPTY SEATS
    seats_g = grp('sr:seats')
    fab, shell, metal = [], [], []

    def put(arr, geo, pos, rot=(0, 0, 0)):
        geo = L.clean(geo)
        geo.apply_matrix4(L.mat4(L.euler_matrix(*rot), pos))
        arr.append(geo)
    # back (faces -Z, toward the stage), leaning back
    put(fab, L.rounded_box_geometry(0.52, 0.6, 0.075, 2, 0.03), (0, 0.80, 0.22), (0.2, 0, 0))
    put(shell, L.rounded_box_geometry(0.52, 0.62, 0.03, 1, 0.01), (0, 0.80, 0.265), (0.2, 0, 0))
    # the seat cushion FOLDED UP (nobody sits): near-vertical in front of the back
    put(fab, L.rounded_box_geometry(0.48, 0.44, 0.075, 2, 0.03), (0, 0.62, 0.05), (-0.12, 0, 0))
    put(shell, L.rounded_box_geometry(0.46, 0.42, 0.02, 1, 0.008), (0, 0.62, 0.005), (-0.12, 0, 0))
    # one standard + armrest per seat (at +x); the row's first standard comes from its own instance list
    put(metal, L.box_geometry(0.045, 0.62, 0.42), (0.3, 0.31, 0.12))
    put(shell, L.rounded_box_geometry(0.065, 0.035, 0.46, 1, 0.012), (0.3, 0.64, 0.1))
    seat_geo = {k_: L.box_uv(L.merge_geometries(v), 1) for k_, v in (('fab', fab), ('shell', shell), ('metal', metal))}
    seat_fabric, g = K.new('seat-fabric')
    tuv = g.uv() * (1 / 0.18)
    fade = g.exp(g.max(g.position_local().z - 5.0, 0.0) * -0.13)
    n = tri(g, 1.5)
    g.standard(color=g.texture(S['Fabric031']['map'], tuv).rgb * (0.13, 0.135, 0.16) * ((n.z - 0.5) * 0.3 + 1)
               * (fade * 0.9 + 0.1), roughness=0.95,
               normal=g.normal_map(g.texture(S['Fabric031']['normalMap'], tuv).rgb, 1.2))
    K.envd(seat_fabric, 0.25)
    seat_shell, g = K.new('seat-shell')
    n = tri(g, 5.0)
    fade = g.exp(g.max(g.position_local().z - 5.0, 0.0) * -0.13)
    g.standard(color=g.vec3(0.03, 0.031, 0.034) * ((n.z - 0.5) * 0.4 + 1) * (fade * 0.9 + 0.1),
               roughness=g.clamp(0.42 + (n.y - 0.5) * 0.2, 0.1, 1.0), metalness=0.0)
    K.envd(seat_shell, 0.7)
    seat_metal, g = K.new('seat-metal')
    n = tri(g, 6.0)
    fade = g.exp(g.max(g.position_local().z - 5.0, 0.0) * -0.13)
    g.standard(color=g.vec3(0.10, 0.10, 0.11) * ((n.z - 0.5) * 0.4 + 1) * (fade * 0.9 + 0.1),
               roughness=g.clamp(0.55 + (n.y - 0.5) * 0.3, 0.1, 1.0), metalness=1.0)
    K.envd(seat_metal, 0.8)
    seat_pos, end_pos = [], []
    for k_ in range(ROWS):
        z_, y_ = ROW0 + k_ * ROWP, FLOOR_Y + k_ * RISE
        for sx in (-1, 1):
            for i in range(10):
                seat_pos.append((sx * (0.9 + i * SEATP), y_, z_))
            end_pos.append((sx * (0.9 - SEATP), y_, z_))
    seat_meshes = []
    for k_, mat in (('fab', seat_fabric), ('shell', seat_shell), ('metal', seat_metal)):
        im = L.InstancedMeshNode(seat_geo[k_], mat, len(seat_pos), name='seats:' + k_, cast=True, recv=True)
        for i, pp in enumerate(seat_pos):
            im.set_matrix_at(i, L.mat4(t=pp))
        seats_g.add(im)
        seat_meshes.append(im)
    sg = L.clean(L.box_geometry(0.045, 0.62, 0.42)).translate(0.3, 0.31, 0.12)
    im = L.InstancedMeshNode(L.box_uv(sg, 1), seat_metal, len(end_pos), name='seats:ends', cast=True, recv=True)
    for i, pp in enumerate(end_pos):
        im.set_matrix_at(i, L.mat4(t=pp))
    seats_g.add(im)
    seat_meshes.append(im)
    # EXIT signs at the back corners: the only lights out there
    et, _cv = img('exit')
    em, g = K.new('exit')
    g.basic(g.texture(et, g.uv()).rgb * (0.25, 2.2, 0.8))
    L.hide_from_probes(em)
    for sx in (-1, 1):
        add(L.plane_geometry(0.42, 0.16), em, (sx * 8.2, FLOOR_Y + ROWS * RISE + 2.4, 21.9), (0, math.pi, 0), group,
            keep=True, cast=False, name='exit')

    # ======================================================================================== TRUSS, FIXTURES, BEAMS
    rig_g = grp('sr:rig')
    S2 = 0.30                                                # box truss section
    lace = []

    def chord(x0, x1, y, z):
        for dy, dz in ((-S2 / 2, -S2 / 2), (-S2 / 2, S2 / 2), (S2 / 2, -S2 / 2), (S2 / 2, S2 / 2)):
            cgeo = L.cylinder_geometry(0.024, 0.024, x1 - x0, 10).rotate_z(math.pi / 2)
            lace.append(L.clean(cgeo.translate((x0 + x1) / 2, y + dy, z + dz)))
        x_ = x0
        while x_ < x1 - 1e-3:
            for ay, az, by, bz in ((-1, -1, 1, -1), (-1, 1, 1, 1), (-1, -1, -1, 1), (1, -1, 1, 1)):
                A = np.array([x_, y + ay * S2 / 2, z + az * S2 / 2])
                B = np.array([x_ + S2, y + by * S2 / 2, z + bz * S2 / 2])
                ln = float(np.linalg.norm(B - A))
                lg = L.cylinder_geometry(0.011, 0.011, ln, 6).apply_matrix3(L.rot_between((0, 1, 0), B - A))
                lace.append(L.clean(lg.translate(*((A + B) / 2))))
            x_ += S2
    for z_ in TRUSS['zs']:
        chord(-TRUSS['x'], TRUSS['x'], TRUSS['y'], z_)
    tm = L.MeshNode(L.box_uv(L.merge_geometries(lace), 1), truss_mat, name='truss', cast=False)
    rig_g.add(tm)
    for z_ in TRUSS['zs']:                                   # hanging drop wires up into the dark
        for x_ in (-7, 0, 7):
            add(cyl(0.004, 0.004, 6, 6), truss_mat, (x_, TRUSS['y'] + 3.15, z_), parent=rig_g, cast=False)
    # fixtures: black cans on yokes, lenses glowing; three of them throw visible beams through the haze
    lens_mat, g = K.new('lens')
    g.basic(g.vec3(0.9, 0.95, 1.0) * (g.uniform('uLights') * 5.0 + 0.05))
    L.hide_from_probes(lens_mat)
    fixtures = []

    def fixture(x_, z_, target, lit):
        g_ = L.Node('fixture')
        g_.set_position(x_, TRUSS['y'] - 0.32, z_)
        rig_g.add(g_)
        add(box(0.04, 0.22, 0.24), powder, (0, 0.06, 0), parent=g_)
        can = L.Node('can')
        g_.add(can)
        add(cyl(0.12, 0.13, 0.38, 24), powder, (0, -0.08, 0), parent=can)
        add(cyl(0.11, 0.11, 0.01, 24), lens_mat if lit else black_mat, (0, -0.275, 0), parent=can, cast=False,
            keep=bool(lit), name='lens' if lit else 'lens_off')
        dir_ = np.array(target, float) - np.array([x_, TRUSS['y'] - 0.32, z_])
        can.set_from_unit_vectors((0, -1, 0), dir_)          # aim the can (its -Y axis) at the target
        fixtures.append({'g': g_, 'x': x_, 'z': z_, 'target': target, 'lit': lit})
        return g_
    fixture(-0.5, TRUSS['zs'][0], (0, 0.9, 0), True)
    fixture(PLINTH['x'] + 0.2, TRUSS['zs'][0], (PLINTH['x'], PLINTH['h'] + STAGE['y'] + 0.1, PLINTH['z']), True)
    fixture(2.2, TRUSS['zs'][1], (0.3, 1.2, -0.2), True)
    for x_ in (-7.5, -5.5, 4.5, 6.5):
        fixture(x_, TRUSS['zs'][0], (x_ * 0.5, 0, 1), False)
    for x_ in (-6, -2.5, 5.5):
        fixture(x_, TRUSS['zs'][1], (x_ * 0.4, 0, -2), False)
    # visible beams: open cones, additive, bright on axis and fading at the silhouette (a cheap volumetric)
    beam_mat, g = K.new('beam')
    along = g.uv().y                                         # 1 at the source (cone tip), 0 at the base
    n = tri(g, 0.9)
    a = g.pow(g.facing(), 2.0) * g.mix(0.10, 0.42, along) * (n.x * 0.5 + 0.75) * g.uniform('uBeams') \
        * g.uniform('uLights')
    g.basic(g.vec3(0.82, 0.9, 1.0) * a * a, additive=True)      # three's AdditiveBlending: colour * alpha, added
    beam_mat.use_backface_culling = False
    L.hide_from_probes(beam_mat, volume=True, sphere=True)
    beams = []
    for fx in [f_ for f_ in fixtures if f_['lit']]:
        A = np.array([fx['x'], TRUSS['y'] - 0.6, fx['z']])
        B = np.array(fx['target'], float)
        B[1] -= 0.9
        ln = float(np.linalg.norm(B - A))
        cg = L.cone_geometry(ln * 0.17, ln, 40, 1, True).translate(0, -ln / 2, 0)   # tip at the origin, opening down
        m = add(cg, beam_mat, parent=rig_g, cast=False, recv=False, keep=True, name='beam')
        m.position = A
        m.set_from_unit_vectors((0, -1, 0), B - A)
        m.render_order = 5
        beams.append(m)

    # ======================================================================================== LIGHTS
    key = L.LightNode('directional', 0xeef4ff, 1.5, name='key', cast_shadow=True, sun_angle_deg=1.0)
    key.set_position(2.0, 11, 7.5)
    key.target = grp('keyTarget').set_position(-1.0, 0.5, 0)
    group.add(key)
    rim = L.LightNode('directional', 0xd4e6ff, 2.2, name='rim')
    rim.set_position(0.5, 4, -12)
    rim.target = grp('rimTarget').set_position(0, 1, 0)
    group.add(rim)
    toaster_spot = L.LightNode('spot', 0xf6f9ff, 26, 12, 1.4, angle=0.11, penumbra=0.45, name='toasterSpot')
    toaster_spot.set_position(PLINTH['x'] + 0.2, TRUSS['y'] - 0.6, TRUSS['zs'][0])
    toaster_spot.target = grp('toasterSpotTarget').set_position(PLINTH['x'], STAGE['y'] + PLINTH['h'], PLINTH['z'])
    group.add(toaster_spot)
    seat_spill = L.LightNode('spot', 0xdfe8ff, 22, 26, 1.6, angle=0.75, penumbra=1.0, name='seatSpill')
    seat_spill.set_position(0, 1.6, 3.2)
    seat_spill.target = grp('seatSpillTarget').set_position(0, -0.6, 12)
    group.add(seat_spill)
    # the product top light: straight down on the turntable, it gives her black techwear its shoulders from any angle
    top_spot = L.LightNode('spot', 0xf2f7ff, 12, 12, 1.3, angle=0.24, penumbra=0.55, name='topSpot')
    top_spot.set_position(0, TRUSS['y'] - 0.4, 0.4)
    top_spot.target = grp('topTarget')
    group.add(top_spot)
    fill = L.LightNode('directional', 0x9fb8d8, 0.35, name='fill')
    fill.set_position(-6, 3, 8)
    fill.target = grp('fillTarget')
    group.add(fill)

    # ======================================================================================== MERGE STATIC
    for g_ in (stage_g, rig_g):
        L.merge_static(g_)
    L.merge_static(tt_g)                                     # the platter's meshes are kept (it turns)
    platter.keep = True
    toaster.keep = True
    L.merge_static(toaster_g)
    L.merge_static(toaster)

    # ======================================================================================== SHADOW CASTERS
    # the key's shadow map only needs the toaster, its plinth and the turntable rim (a performer on the mark is the
    # piece's own, not the set's); seats, rig, drapes and the stage only receive
    def cast_pick(o):
        if isinstance(o, L.MeshNode):
            k = False
            p_ = o
            while p_ is not None:
                if p_ is toaster_g:
                    k = True
                p_ = p_.parent
            o.cast = k
    group.traverse(cast_pick)

    # ======================================================================================== CAMS + UPDATE
    focal = grp('focal:singer').set_position(0, face_y, 0)
    out['cams_three'] = {                                  # the engine's numbers (three's axes)
        'reveal': {'pos': [0.0, 1.3, 11.5], 'target': [0.0, 1.95, -3.0], 'fov': 40},
        'toaster': {'pos': [-1.55, 1.05, 2.35], 'target': [PLINTH['x'] - 0.02, 0.62, PLINTH['z']], 'fov': 36},
        'emptySeats': {'pos': [0.95, 1.65, -1.15], 'target': [-0.6, -0.3, 11.0], 'fov': 50},
        'close': {'pos': [0.05, face_y + 0.06, 2.05], 'target': [0.0, face_y - 0.04, 0.0], 'fov': 30},
        'wall': {'pos': [3.2, 2.6, 3.5], 'target': [0.0, 2.9, SCR['z']], 'fov': 40},
    }
    sb.emit()
    platter.ob.rotation_mode = 'XYZ'
    out['cams'] = {k: L.cam_to_blender(v) for k, v in out['cams_three'].items()}      # Blender axes
    out['env'] = ENV
    out['focal'] = focal.ob
    out._platter = platter
    out._lights = {'key': key, 'rim': rim, 'toasterSpot': toaster_spot, 'seatSpill': seat_spill, 'fill': fill,
                   'top': top_spot}
    out['parts'] = {
        'turntable': {'group': tt_g.ob, 'platter': platter.ob, 'setSpin': out.set_spin},
        'screen': {'mesh': wall.ob, 'uniforms': {'seq': '["uSeq"]', 'brightness': '["uScreen"]'},
                   'image': sheet_tex, 'media': media, 'seq_bar': bool(seq_bar)},
        'toaster': toaster.ob, 'plinth': toaster_g.ob, 'seats': seats_g.ob, 'rig': rig_g.ob,
        'beams': [b.ob for b in beams],
        'lights': {k_: v.ob for k_, v in out._lights.items()},
        'focal': focal.ob, 'toasterFocus': toaster_focus.ob,
        'uniforms': {u: f'["{u}"]' for u in ('uT', 'uSeq', 'uLights', 'uBeams', 'uScreen')},
    }
    out['mark'] = {'pos': L.to_blender(MARK['pos']), 'yaw': float(MARK['yaw']), 'parent': platter.ob}  # yaw about +Z
    out.nodes = {'group': group, 'toaster': toaster, 'body': body_node, 'seats': seat_meshes, 'beams': beams,
                 'fixtures': fixtures, 'platter': platter}
    out['probe'] = None
    if probe:
        # the stage, the turntable, the plinth and the first rows (the void is left out of the bake: beyond the
        # outermost samples EEVEE fades to the World, which is the set's env, as the engine's materials saw it)
        from ...look import lighting as LL
        from mathutils import Matrix
        lo = np.array(L.to_blender((-STAGE['x'] - 0.5, FLOOR_Y - 0.1, 12.0)))
        hi = np.array(L.to_blender((STAGE['x'] + 0.5, 6.0, STAGE['z0'] - 0.5)))
        mn, mx = np.minimum(lo, hi), np.maximum(lo, hi)
        res = [max(2, int(round((mx[i] - mn[i]) / probe_spacing)) + 1) for i in range(3)]
        cell = [(mx[i] - mn[i]) / (res[i] - 1) for i in range(3)]
        pr = LL.add_volume_probe(sb.scene, f'{name}:probe', tuple((mn + mx) / 2),
                                 tuple(mx[i] - mn[i] + cell[i] for i in range(3)), resolution=res,
                                 samples=probe_samples, collection=sb.coll)
        sb.made['objects'].append(pr)
        sb.made['probes'].append(pr.data)
        pr.parent = sb.root_ob
        pr.matrix_parent_inverse = Matrix.Identity(4)
        out['probe'] = pr
        out['parts']['probe'] = pr
    out.update(0.0, {}, key=False)
    return out
