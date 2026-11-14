"""example_asset_use.py: the quiet room and the showroom as free assets in a new piece. Each set is built with the
piece's own art, keyed on the piece's own clock (animate), cut between the set's cameras with timeline markers, and
rendered by jumping into the keyed timeline. The sets alone, no performer.

  quiet room   its own centre whiteboard (drawn with interiors_lib's marker kit, handed over as a Canvas), its own
               essay page (a picture file) and its own dot-matrix sign (a numpy array): build(art={...}); the crate
               shipped over 1.0-3.0 s and the launch lights over 2.8-3.6 s (animate(ship_t=..., sale=...)); cuts
               hatch -> crate.
  showroom     the LED wall playing a 24-frame image sequence (build(screen_media=...), letterboxed in LED black by
               screen_fit 'fit'), its own placard (a painter: art={'warning': fn}), the turntable at 0.35 rad/s and a
               blackout over 3.4-3.9 s (animate(spin=..., lights=(3.4, 3.9, 1, 0))), the LED wall's camera following
               the cuts (animate(camera=a function of the frame)). With ffmpeg on the PATH the same cards are encoded
               to an H.264 clip and read back as a movie (media_image: source MOVIE, its length and size).

    bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_interiors/example_asset_use.py [--set quiet_room|showroom|both] [--fps 30]
        [--save] [--keep_blend] [--no_render] [--samples 16] [--res 960x540]
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

Stills: out/asset/<set>_<cam>_f<frame>.png and out/asset/asset_sheet.jpg. --save writes each set's .blend, opens it
again, re-renders one still from the file alone and compares it with the render made before saving (the keys, the
drivers, the markers and the clip on the wall carry the shot); --keep_blend keeps the file.
"""
import colorsys
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as T  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sets.unknown_force import interiors_lib as L  # noqa: E402
from eidoblend.sets.unknown_force import quiet_room as QR  # noqa: E402
from eidoblend.sets.unknown_force import showroom as SR  # noqa: E402

A = T.args({'set': 'both', 'fps': 30, 'samples': 16, 'res': '960x540', 'save': False, 'keep_blend': False,
            'no_render': False})
OUT = os.path.join(T.OUT, 'asset')
MEDIA = os.path.join(OUT, 'media')
os.makedirs(MEDIA, exist_ok=True)
N_CARDS = 24
CARD = (1280, 720)                     # 16:9 cards on the 13 x 5.6 m wall: letterboxed


# ================================================================================================ the piece's own art
def my_board(ctx, W, H):
    """a whiteboard of the piece's own, in the set's marker kit (the room derives the ink's matte from it)."""
    r = L.rng(4242)
    L.board_base(ctx, W, H, r, ghosts=[{'t': 'agenda', 'x': 0.58, 'y': 0.22, 's': 0.07},
                                       {'t': 'v2?', 'x': 0.8, 'y': 0.7, 's': 0.09}])
    L.marker(ctx, 'OPEN QUESTIONS', 120, 260, size=190, color='#15171b', r=r)
    L.mline(ctx, [[120, 300], [1500, 292]], w=9, color='#15171b', r=r)
    for i, (txt, col) in enumerate((('1. who is it for?', '#15171b'), ('2. what does it want?', '#c4121c'),
                                    ('3. when do we stop?', '#1d3d8f'))):
        L.marker(ctx, txt, 170, 560 + i * 280, size=140, color=col, r=r)
    L.mring(ctx, 1080, 790, 420, 130, r=r, color='#c4121c', w=8)
    L.marrow(ctx, 2350, 1100, 1560, 830, w=9, color='#c4121c', r=r)
    L.marker(ctx, 'ask it!', 2250, 1230, size=150, color='#c4121c', r=r)


def my_essay_png(path):
    """the essay page as a picture file (any image works; it is resized to the set's 1024 x 1448 page)."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new('RGB', (1024, 1448), (243, 240, 232))
    d = ImageDraw.Draw(im)
    big = ImageFont.truetype(str(L.FONT_DIR / 'SpecialElite-Regular.ttf'), 104)
    small = ImageFont.truetype(str(L.FONT_DIR / 'SpecialElite-Regular.ttf'), 40)
    d.text((512, 150), 'FIELD NOTES', font=big, fill=(28, 28, 32), anchor='mm')
    d.text((512, 255), 'what the room was for', font=small, fill=(150, 30, 34), anchor='mm')
    d.line([(150, 320), (874, 320)], fill=(28, 28, 32), width=4)
    rng = np.random.default_rng(7)
    y = 400
    for para in range(5):
        for _ln in range(5):
            w = int(724 * (0.62 if _ln == 4 else rng.uniform(0.86, 1.0)))
            d.rectangle([150, y, 150 + w, y + 14], fill=(70, 70, 78))
            y += 38
        y += 40
    im.save(path)
    return path


def my_sign_array(W=1024, H=160):
    """the dot-matrix sign as a uint8 RGBA array (row 0 at the top), amber on black."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(str(L.FONT_DIR / 'Michroma-Regular.ttf'), 70)
    d.text((W // 2, H // 2), 'ARRIVALS  2', font=f, fill=(255, 176, 60, 255), anchor='mm')
    return np.asarray(im, np.uint8)


def my_placard(ctx, W, H):
    """the toaster's placard, redrawn by a painter fn(ctx, W, H) on the set's canvas (920 x 1240)."""
    ctx.fillStyle = '#f4f6f8'
    ctx.fillRect(0, 0, W, H)
    ctx.strokeStyle = '#0d1626'
    ctx.lineWidth = 12
    ctx.strokeRect(24, 24, W - 48, H - 48)
    ctx.fillStyle = '#1d6fd1'
    ctx.fillRect(48, 48, W - 96, 230)
    ctx.fillStyle = '#ffffff'
    ctx.font = '170px "UF Rajdhani"'
    ctx.textAlign = 'left'
    ctx.fillText('NOTICE', 90, 225)
    ctx.fillStyle = '#0d1626'
    ctx.font = '104px "UF Rajdhani"'
    for i, ln in enumerate(('THIS EXHIBIT', 'IS ON LOAN.')):
        ctx.fillText(ln, 90, 470 + i * 118)
    ctx.font = '52px "UF Rajdhani"'
    for i, ln in enumerate(('Please do not touch the toast.', 'Ask a member of staff', 'for a demonstration.')):
        ctx.fillText(ln, 90, 800 + i * 74)


def make_cards():
    """the LED wall's clip: 24 numbered 16:9 cards, each its own hue, a white disc crossing the lower third and a
    white border (which shows where the letterbox starts)."""
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(str(L.FONT_DIR / 'Michroma-Regular.ttf'), 150)
    paths = []
    for i in range(N_CARDS):
        r, g, b = colorsys.hsv_to_rgb(i / N_CARDS, 0.85, 0.95)
        im = Image.new('RGB', CARD, (int(r * 255), int(g * 255), int(b * 255)))
        d = ImageDraw.Draw(im)
        x = 110 + i * (CARD[0] - 220) / (N_CARDS - 1)
        d.ellipse([x - 70, 520 - 70, x + 70, 520 + 70], fill=(255, 255, 255))
        d.rectangle([0, 0, CARD[0] - 1, CARD[1] - 1], outline=(255, 255, 255), width=14)
        d.text((60, 40), f'{i + 1:02d}', font=f, fill=(255, 255, 255))
        p = os.path.join(MEDIA, f'card_{i + 1:04d}.png')
        im.save(p)
        paths.append(p)
    return paths


def card_rgb(frame):
    """the card a scene frame shows (the clip starts on frame 1 and loops)."""
    i = (frame - 1) % N_CARDS
    return np.array(colorsys.hsv_to_rgb(i / N_CARDS, 0.85, 0.95))


# ================================================================================================ helpers
def new_scene(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = name
    sc.render.fps = int(A['fps'])
    return sc


def cut(sc, cams, rows):
    """timeline markers binding each camera from its frame on (rows: [(frame, cam name)])."""
    for f, nm in rows:
        sc.timeline_markers.new(f'cut_{nm}_{f}', frame=f).camera = cams[nm]
    return lambda fr: cams[[nm for f, nm in rows if f <= fr][-1]]


def patch(path, scene, cam, world_point, half=6):
    """the mean linear-ish RGB (0..1, as rendered) of a small square around a world point seen by `cam`."""
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0
    p = world_to_camera_view(scene, cam, world_point)
    H, W = a.shape[:2]
    x, y = int(p.x * W), int((1 - p.y) * H)
    if not (half <= x < W - half and half <= y < H - half and p.z > 0):
        return None
    return a[y - half:y + half + 1, x - half:x + half + 1].reshape(-1, 3).mean(0)


def render(sc, cam, frame, path):
    T.render_still(sc, cam, frame, path)
    mean, clip, black = T.stats(path)
    return mean, clip


def save_reload(sc, name, frame, ref_path):
    """save the .blend, open it again, re-render `frame` from the file alone and compare."""
    blend = os.path.join(OUT, f'{name}.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    mb = os.path.getsize(blend) / 2 ** 20
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc2 = bpy.context.scene
    sc2.frame_set(frame)
    p2 = ref_path.replace('.png', '_reloaded.png')
    sc2.render.filepath = p2
    bpy.ops.render.render(write_still=True)
    from PIL import Image
    a = np.asarray(Image.open(ref_path).convert('RGB'), np.float32)
    b = np.asarray(Image.open(p2).convert('RGB'), np.float32)
    mad = float(np.abs(a - b).mean())
    T.check(f'{name}: the saved .blend plays on its own (frame {frame} re-rendered from the file, its camera from '
            'the markers)', mad < 2.0, f'mean |dRGB| {mad:.2f} / 255, {mb:.0f} MB')
    if not A['keep_blend']:
        os.remove(blend)
        os.remove(p2)


# ================================================================================================ the quiet room
def quiet_room():
    sc = new_scene('asset_quiet_room')
    W, H = (int(v) for v in A['res'].split('x'))
    fps = int(A['fps'])
    n = 4 * fps
    sc.frame_start, sc.frame_end = 1, n
    essay = my_essay_png(os.path.join(OUT, 'my_essay.png'))
    board_cv = L.override_canvas(my_board, *QR.CANVASES['board_center'][:2])        # a Canvas, drawn once here
    sign = my_sign_array()
    tb = time.perf_counter()
    room = QR.build(sc, art_cache=T.ART, probe_spacing=0.45, probe_samples=512,
                    art={'board_center': board_cv, 'essay': essay, 'ship_sign': sign})
    T.check('quiet room built with its own centre board (a Canvas), essay (a picture file) and sign (an array)', True,
            f'{time.perf_counter() - tb:.1f} s')

    # the piece's art is what the materials sample, pixel for pixel (Blender images: row 0 at the bottom)
    def image_of(ob, skip='rough'):
        return next(nd.image for nd in ob.data.materials[0].node_tree.nodes
                    if nd.bl_idname == 'ShaderNodeTexImage' and nd.image and skip not in nd.image.name)

    def rgba8(img):
        w, h = img.size
        return np.round(np.array(img.pixels[:], np.float32).reshape(h, w, 4)[::-1] * 255)
    face = room.parts['boards']['center']
    d_board = float(np.abs(rgba8(image_of(face)) - board_cv.rgba8()).max())
    essay_img = bpy.data.images['ufqr_essay']
    from PIL import Image
    want_essay = np.asarray(Image.open(essay).convert('RGBA'), np.float32)
    d_essay = float(np.abs(rgba8(essay_img) - want_essay).max())
    sign_img = bpy.data.images['ufqr_ship_sign']
    d_sign = float(np.abs(rgba8(sign_img) - sign.astype(np.float32)).max())
    T.check("the piece's art is on the board face, the lectern's page and the sign, exact (max |d| in 8-bit levels)",
            d_board <= 1 and d_essay <= 1 and d_sign <= 1, f'board {d_board:.0f}, essay {d_essay:.0f}, '
            f'sign {d_sign:.0f}')
    try:
        QR.build(sc, art={'board_centre': my_board}, probe=False)
        typo = False
    except KeyError:
        typo = True
    T.check('build(art=) refuses a key that names no canvas (a typo would keep the set\'s own art)', typo)

    # the piece's clock: 4 s at its fps; the crate ships over 1.0-3.0 s, the launch lights come up over 2.8-3.6 s;
    # its cuts: the page, the hatch while the crate rides out, the shipped crate, the board under the launch lights
    keyed = room.animate((1, n), ship_t=(1.0, 3.0), sale=(2.8, 3.6))
    cams = {nm: room.make_camera(nm) for nm in ('hatch', 'crate', 'board', 'essay')}
    plan = [(1, 'essay'), (25, 'hatch'), (91, 'crate'), (111, 'board')]
    cam_at = cut(sc, cams, plan)
    y_in, y_out = L.to_blender((0, 0, QR.CRATE['zIn']))[1], L.to_blender((0, 0, QR.CRATE['zOut']))[1]
    cy = {}
    for f in (1, n // 2, n):
        sc.frame_set(f)
        cy[f] = room.parts['crate']['group'].location.y             # Blender y = -z (three): it rises as it ships
    wrong = []
    for f in (1, 24, 25, 60, 91, 110, 111, n):
        sc.frame_set(f)
        if sc.camera is not cam_at(f):
            wrong.append(f)
    T.check(f'{n} frames keyed on the piece\'s clock: the crate in the tunnel at frame 1, out at the stop at {n}; the '
            'markers cut essay -> hatch -> crate -> board', abs(cy[1] - y_in) < 1e-4 and abs(cy[n] - y_out) < 0.04 and
            cy[1] < cy[n // 2] < cy[n] and not wrong and len(keyed) == n,
            f'crate y {cy[1]:.2f} -> {cy[n // 2]:.2f} -> {cy[n]:.2f} m (stop {y_out:.2f}); wrong cuts {wrong}')
    if A['no_render']:
        return []

    T.render_setup(sc, (W, H), int(A['samples']), bloom=True)
    sc.world = room.env
    room.eevee_settings(sc)
    sc.frame_set(1)
    secs = room.bake_probes(sc)
    T.check('room probe baked at the first frame (the rest state)', bool(secs), f'{secs}')
    outs, stats = [], {}
    for cam, f in (('essay', 12), ('hatch', 25), ('hatch', 60), ('crate', 110), ('board', n)):     # on their cuts
        path = os.path.join(OUT, f'quiet_room_{cam}_f{f:03d}.png')
        mean, clip = render(sc, cams[cam], f, path)
        stats[(cam, f)] = mean
        T.check(f'quiet room {cam} at frame {f}: exposed', 0.02 < mean < 0.75 and clip < 0.04,
                f'mean {mean:.3f}, clipped {100 * clip:.2f} %')
        outs.append(path)
    T.check('the launch reads on screen: the shipped crate under the launch lights brighter than the hatch at rest',
            stats[('crate', 110)] > stats[('hatch', 25)], f"{stats[('crate', 110)]:.3f} > {stats[('hatch', 25)]:.3f}")
    if A['save']:
        sc.camera = None
        save_reload(sc, 'asset_quiet_room', 60, outs[2])
    return outs


# ================================================================================================ the showroom
def showroom():
    sc = new_scene('asset_showroom')
    W, H = (int(v) for v in A['res'].split('x'))
    fps = int(A['fps'])
    n = 4 * fps
    sc.frame_start, sc.frame_end = 1, n
    sc.render.resolution_x, sc.render.resolution_y = W, H
    cards = make_cards()
    tb = time.perf_counter()
    show = SR.build(sc, art_cache=T.ART, probe_spacing=0.6, probe_samples=512, screen_media=cards[0],
                    art={'warning': my_placard})
    scr = show.parts['screen']
    md = scr['media']
    iu = md.get('image_user') if md else None
    wall_aspect = SR.SCREEN['w'] / SR.SCREEN['h']
    want_sx = wall_aspect / (CARD[0] / CARD[1])
    T.check('showroom built: the LED wall plays a 24-card image sequence from frame 1, looping, letterboxed (fit), '
            'no progress bar over it; its own placard', md is not None and scr['image'].source == 'SEQUENCE' and
            md['frames'] == N_CARDS and iu is not None and iu.frame_duration == N_CARDS and iu.frame_start == 1 and
            iu.use_cyclic and abs(md['scale'][0] - want_sx) < 1e-6 and md['scale'][1] == 1.0 and not scr['seq_bar'],
            f'{time.perf_counter() - tb:.1f} s; {md and md["frames"]} frames, scale {md and md["scale"]}')
    # the fit maths both ways, and 'fill'
    def near(a, b):
        return all(abs(x - y) < 1e-9 for x, y in zip(a, b))
    ok_fit = (near(SR.screen_fit_scale(16 / 9, 'fit'), (wall_aspect / (16 / 9), 1.0)) and
              near(SR.screen_fit_scale(4.0, 'fit'), (1.0, 4.0 / wall_aspect)) and
              near(SR.screen_fit_scale(16 / 9, 'fill'), (1.0, (16 / 9) / wall_aspect)) and
              near(SR.screen_fit_scale(4.0, 'fill'), (wall_aspect / 4.0, 1.0)) and
              SR.screen_fit_scale(16 / 9, 'stretch') == (1.0, 1.0))
    T.check("screen_fit_scale: 'fit' letterboxes a narrow or a wide clip, 'fill' crops, 'stretch' leaves it", ok_fit)
    # a movie: the same cards encoded with ffmpeg (when it is on the PATH) and read back as one
    ff = shutil.which('ffmpeg')
    if ff:
        mp4 = os.path.join(MEDIA, 'cards.mp4')
        try:
            subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(fps), '-i',
                            os.path.join(MEDIA, 'card_%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', mp4],
                           check=True, timeout=120)
            mimg, minfo = L.media_image(mp4, name='asset_movie_check')
            T.check('media_image: an H.264 movie reads as a MOVIE of 24 frames at 1280 x 720',
                    mimg.source == 'MOVIE' and minfo['frames'] == N_CARDS and minfo['size'] in (None, CARD),
                    f"{mimg.source}, {minfo}")
            bpy.data.images.remove(mimg)
        except (OSError, subprocess.SubprocessError) as e:
            print(f'SKIP media_image movie check: ffmpeg could not run here ({e})', flush=True)
    else:
        print('SKIP media_image movie check: no ffmpeg on the PATH', flush=True)
    lone = os.path.join(MEDIA, 'poster.png')                 # no frame number in its name: a still
    shutil.copyfile(cards[5], lone)
    still_img, still_info = L.media_image(lone, name='asset_still_check')
    T.check('media_image: an unnumbered picture is a still (1 frame, its size read)', still_info['frames'] == 1 and
            still_img.source == 'FILE' and still_info['size'] == CARD, f'{still_img.source}, {still_info}')
    bpy.data.images.remove(still_img)

    cams = {nm: show.make_camera(nm) for nm in ('wall', 'reveal', 'toaster')}
    cam_at = cut(sc, cams, [(1, 'wall'), (31, 'reveal'), (61, 'toaster'), (91, 'reveal')])
    keyed = show.animate((1, n), spin=lambda t: 0.35 * t, lights=(3.4, 3.9, 1.0, 0.0), camera=cam_at)
    sc.frame_set(n)
    a_end = show.parts['turntable']['platter'].rotation_euler.z
    T.check(f'{n} frames keyed: the turntable at 0.35 rad/s, the blackout over 3.4-3.9 s',
            abs(a_end - 0.35 * keyed[n]) < 1e-4 and abs(show.root['uLights']) < 1e-6 and len(keyed) == n,
            f'spin {a_end:.3f} rad at {keyed[n]:.2f} s, lights {show.root["uLights"]:.2f}')
    if A['no_render']:
        return []

    T.render_setup(sc, (W, H), int(A['samples']), bloom=True)
    sc.world = show.env
    show.eevee_settings(sc)
    sc.frame_set(1)
    secs = show.bake_probes(sc)
    T.check('stage probe baked', bool(secs), f'{secs}')
    root = show.root.matrix_world

    def wall_point(u, v):
        x = (u - 0.5) * SR.SCR['w']
        y = SR.SCR['y0'] + v * SR.SCR['h']
        return root @ Vector(L.to_blender((x, y, SR.SCR['z'] + 0.002)))
    outs, rows = [], {}
    for cam, f in (('wall', 1), ('wall', 13), ('reveal', 40), ('toaster', 70), ('reveal', n)):
        path = os.path.join(OUT, f'showroom_{cam}_f{f:03d}.png')
        mean, clip = render(sc, cams[cam], f, path)
        rows[(cam, f)] = (path, mean)
        T.check(f'showroom {cam} at frame {f}: exposed', 0.015 < mean < 0.75 and clip < 0.05,
                f'mean {mean:.3f}, clipped {100 * clip:.2f} %')
        outs.append(path)
    # the clip on the wall: the card each frame shows, at the wall's centre; LED black in the letterbox
    msgs, ok = [], True
    for f in (1, 13):
        c = patch(rows[('wall', f)][0], sc, cams['wall'], wall_point(0.5, 0.55))
        bar = patch(rows[('wall', f)][0], sc, cams['wall'], wall_point(0.04, 0.55))
        want = card_rgb(f)
        if c is None or bar is None:
            ok = False
            msgs.append(f'frame {f}: the wall point is off screen')
            continue
        dom = int(np.argmax(want))                     # the card's dominant channel leads on screen too
        hue_ok = c[dom] > 1.2 * np.delete(c, dom).max() if dom == 0 else min(c[1], c[2]) > 1.2 * c[0]
        ok = ok and hue_ok and bar.mean() < 0.35 * c.mean()
        msgs.append(f'frame {f}: centre {np.round(c, 2)} (card {np.round(want, 2)}), letterbox {np.round(bar, 2)}')
    T.check('the LED wall shows card 1 at frame 1 and card 13 at frame 13 (the hue at its centre), LED black in the '
            'letterbox', ok, '; '.join(msgs))
    # the blackout takes the set's lights (the toaster spot, key, top light, beams, lenses) and leaves the set's env,
    # which lights every material as the engine's envMap did (the white deck keeps ~90 %): the placard the toaster
    # spot is aimed at must fall well below its lit value
    lit, dark = rows[('reveal', 40)][1], rows[('reveal', n)][1]
    placard = root @ Vector(L.to_blender((SR.PLINTH['x'], 0.5, SR.PLINTH['z'] + 0.29)))
    p_lit = patch(rows[('reveal', 40)][0], sc, cams['reveal'], placard, half=3)
    p_dark = patch(rows[('reveal', n)][0], sc, cams['reveal'], placard, half=3)
    T.check("the blackout reads: the toaster's placard loses its spot at the end, the frame darkens (the LED wall "
            'plays on)', dark < lit and p_lit is not None and p_dark is not None and p_dark.mean() < 0.7 * p_lit.mean(),
            f'frame mean {lit:.3f} -> {dark:.3f}; placard {None if p_lit is None else round(float(p_lit.mean()), 3)}'
            f' -> {None if p_dark is None else round(float(p_dark.mean()), 3)}')
    if A['save']:
        sc.camera = None
        save_reload(sc, 'asset_showroom', 13, rows[('wall', 13)][0])
    return outs


def main():
    outs = []
    if A['set'] in ('quiet_room', 'both'):
        outs += quiet_room()
    if A['set'] in ('showroom', 'both'):
        outs += showroom()
    if outs:
        T.sheet(outs, os.path.join(OUT, 'asset_sheet.jpg'), cols=5, width=1600)
    return T.done()


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(rc)
