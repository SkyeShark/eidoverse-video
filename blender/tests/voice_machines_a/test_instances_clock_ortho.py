"""Probe: the era-2 machines the way a new film uses them, beyond one machine on its own (renders through the GPU slot).

From the main checkout:
    HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \\
        <worktree>/blender/tests/voice_machines_a/test_instances_clock_ortho.py \\
        [-- --only two,turned,clock,ortho,footprint]

two     two C64s built without names into one screen folder, each with its own text, power and voice: separate roots,
        channels, screens and frame files, shared baked meshes -> out/verify/two_c64_one_desk.png
turned  the 2001 desktop turned 35 degrees on the desk, voice 0 vs 1: the speaker cloth's glow stays centred on its
        drivers (object space), the screen keeps its raster -> out/verify/desktop2001_turned_voice.png
clock   a film clock that is not the default: 30 fps, the scene starting at frame 1001 (eido_frame0 1001). The text
        changes at t = 1 s and must draw on frame 1031, not a frame early or late; the frames before the range show
        the first drawing (the hold), never magenta. Then the blend is saved and reopened with scripts off and frame
        1031 rendered again -> out/verify/clock_30fps_from_1001.png
ortho   the Macintosh seen from across the room through a perspective and an orthographic camera at the same scale:
        the dithered desktop must read as an even grey in both -> out/verify/mac_far_persp_vs_ortho.png
footprint  pixel_footprint and pixel_angle rendered as values on a plane square to the view (float EXR, read back)
        against the camera's own metres per pixel: landscape and portrait perspective, orthographic (no images kept)
Prints PASS / FAIL lines for what it measures.
"""
import math
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _stage as S  # noqa: E402
from eidoblend.props import voice_machines as VM  # noqa: E402

A = S.args()
ONLY = set(A[A.index('--only') + 1].split(',')) if '--only' in A else {'two', 'turned', 'clock', 'ortho', 'footprint'}
RENDER = '--no-render' not in A            # --no-render: the checks that need no image (no GPU slot)
OUT = S.OUT / 'verify'
WORK = OUT / 'work_instances'


def check(ok, what):
    return S.check(what, ok)


def world_bounds(objs):
    bpy.context.view_layer.update()
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            v = o.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, v))
            hi = Vector(map(max, hi, v))
    return lo, hi


def centre_of(o):
    lo, hi = world_bounds([o])
    return (lo + hi) / 2


def place(m, x=0.0, y=0.0):
    cx, cy = VM.MACHINES[m.name]['center']
    m.group.location = (x - cx, y - cy, S.DESK_Z)
    bpy.context.view_layer.update()


def png_array(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert('RGB')).astype(np.float64)


def strip(paths, out, labels=None, h=300):
    from PIL import Image, ImageDraw
    ims = [Image.open(p).convert('RGB') for p in paths]
    ims = [im.resize((int(im.width * h / im.height), h), Image.Resampling.LANCZOS) for im in ims]
    sheet = Image.new('RGB', (sum(im.width for im in ims) + 6 * (len(ims) - 1), h + 20), (20, 20, 22))
    x = 0
    for i, im in enumerate(ims):
        sheet.paste(im, (x, 20))
        if labels:
            ImageDraw.Draw(sheet).text((x + 4, 4), labels[i], fill=(220, 220, 220))
        x += im.width + 6
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f'[sheet] {out}')
    return out


def fc_value(obj, prop, frame):
    fc = S.fcurve(obj, f'["{prop}"]')
    return None if fc is None else fc.evaluate(frame)


def screen_box(sc, cam, o, pad=0):
    bpy.context.view_layer.update()
    pts = [S.project(sc, cam, o.matrix_world @ Vector(c)) for c in o.bound_box]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    W, H = sc.render.resolution_x, sc.render.resolution_y
    return (max(0, int(min(xs)) - pad), max(0, int(min(ys)) - pad), min(W, int(max(xs)) + pad + 1),
            min(H, int(max(ys)) + pad + 1))


def stage(frames=(1, 2), res=(960, 540), samples=16, fps=24, width=1.8):
    sc = S.fresh_scene(res=res, samples=samples, frames=frames, fps=fps)
    S.desk_room(sc, width=width)
    return sc


def lit_band(png, box, frac=0.3):
    """How far a C64 raster is open: the height in rows of the band (first to last row) of a pixel box's middle
    third whose blue exceeds its red by more than `frac` of the way from the box's least blue row to its bluest.
    The raster is blue and lavender; the room the dark glass mirrors is grey, so its reflections never count."""
    x0, y0, x1, y1 = box
    a = png_array(png)[y0:y1, x0:x1]
    mid = a[:, a.shape[1] // 3: 2 * a.shape[1] // 3]
    rows = (mid[..., 2] - mid[..., 0]).mean(axis=1)
    lit = np.nonzero(rows > rows.min() + (rows.max() - rows.min()) * frac)[0]
    return int(lit[-1] - lit[0] + 1) if len(lit) else 0


# ------------------------------------------------------------------------------------------------------- two ---
def probe_two():
    sc = stage(frames=(1, 2))
    shared = WORK / 'two'
    a = VM.build_machine('c64', screen_dir=str(shared))
    b = VM.build_machine('c64', screen_dir=str(shared))
    place(a, -0.24, 0.0)
    place(b, 0.24, 0.0)
    a.parts['screen'].set_text(['READY.', 'SAY "ONE"', 'ONE', 'READY.'], 'solid')
    b.parts['screen'].set_text(['READY.', 'SAY "THE OTHER ONE"', 'THE OTHER ONE', 'READY.', 'LIST', '10 PRINT "TWO"',
                                '20 GOTO 10'], 'solid')
    a.update(0.0, {'power': 1.0, 'voice': 0.0})
    b.update(0.0, {'power': 0.3, 'voice': 1.0})
    sa, sb = a.screens[0], b.screens[0]
    check(a.group.name != b.group.name and sa.image != sb.image and sa.prefix != sb.prefix,
          f'two C64s without names: roots {a.group.name!r} / {b.group.name!r}, screens {sa.image.name!r} / '
          f'{sb.image.name!r}')
    fa, fb = sa._file(1), sb._file(1)
    same_dir = fa.parent == fb.parent
    differ = fa.is_file() and fb.is_file() and fa.read_bytes() != fb.read_bytes()
    check(same_dir and differ, f'one screen folder, two frame sequences side by side ({fa.name}, {fb.name}), each '
                               f'its own drawing')
    check(a.parts['computer'].data == b.parts['computer'].data and
          a.parts['screen'].mesh.data != b.parts['screen'].mesh.data,
          'the baked case mesh is shared, each tube has its own mesh and material')
    pa, pb = fc_value(a.group, 'power', 1), fc_value(b.group, 'power', 1)
    la, lb = fc_value(a.group, 'led_monitor', 1), fc_value(b.group, 'led_monitor', 1)
    check(abs(pa - 1.0) < 1e-6 and abs(pb - 0.3) < 1e-6 and abs(la - 0.75) < 1e-6 and abs(lb - 1.35) < 1e-6,
          f'each root keys its own channels (power {pa:g} / {pb:g}, monitor LED {la:g} / {lb:g})')
    if not RENDER:
        return
    cam = S.camera(sc, (0, -1, 1), (0, 0, 1), lens=40)
    objs = a.objects + b.objects
    lo, hi = world_bounds(objs)
    c = (lo + hi) / 2
    cam.location = c + Vector((0.12, -1.25, 0.32))
    S.look_at(cam, c)
    S.key_light(sc, c, dist=1.3, power=55.0)
    p = S.render(OUT / 'two_c64_one_desk.png', 1)
    check(S.magenta_fraction(p) == 0.0, 'two C64s render, no magenta')
    na = lit_band(p, screen_box(sc, cam, a.parts['screen'].mesh))
    nb = lit_band(p, screen_box(sc, cam, b.parts['screen'].mesh))
    check(nb > 0 and na > nb * 1.8, f'the first raster is fully open, the second still opening at power 0.3 '
                                    f'(lit band {na} vs {nb} rows)')


# ---------------------------------------------------------------------------------------------------- turned ---
def probe_turned():
    sc = stage(frames=(1, 2), width=2.2)
    pc = VM.build_machine('desktop2001', screen_dir=str(WORK / 'turned'))
    place(pc, 0.0, 0.0)
    pc.group.rotation_euler = (0.0, 0.0, math.radians(-35.0))
    pc.update(0.0, {'power': 1.0, 'voice': 0.0})
    pc.update(1 / 24, {'power': 1.0, 'voice': 1.0})
    pc.parts['leds']['tw_hdd'].set(1.0, frame=2)
    bpy.context.view_layer.update()
    if not RENDER:
        return
    cam = S.camera(sc, (0, -1, 1), (0, 0, 1), lens=35)
    lo, hi = world_bounds(pc.objects)
    c = (lo + hi) / 2
    cam.location = c + Vector((0.35, -1.55, 0.55))
    S.look_at(cam, c)
    S.key_light(sc, c, dist=1.4, power=10.0)
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.3
    p0, p1 = S.render(WORK / 'turned_0.png', 1), S.render(WORK / 'turned_1.png', 2)
    strip([p0, p1], OUT / 'desktop2001_turned_voice.png', ['turned 35 deg, voice 0', 'voice 1'], h=400)
    a0, a1 = png_array(p0), png_array(p1)
    # the driver centres as cloth_material computes them (object space), carried to the turned machine
    cloth = pc.parts['speaker'].mesh
    co = np.array([v.co[:] for v in cloth.data.vertices])
    mid = (co[:, 0].min() + co[:, 0].max()) / 2
    worst = 0.0
    for side in (co[:, 0] < mid, co[:, 0] >= mid):
        ctr = co[side].mean(axis=0)
        w = cloth.matrix_world @ Vector((ctr[0], ctr[1], ctr[2] + 0.012))
        px, py = S.project(sc, cam, w)
        # the glow the voice adds, inside this speaker's projected panel
        pts = [S.project(sc, cam, cloth.matrix_world @ Vector(q)) for q in co[side]]
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        x0, y0, x1, y1 = int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1
        g = np.clip((a1[y0:y1, x0:x1] - a0[y0:y1, x0:x1]).sum(axis=2), 0, None)
        if g.sum() <= 0:
            check(False, 'the speaker cloth glows with the voice')
            return
        yy, xx = np.mgrid[y0:y1, x0:x1]
        gx, gy = (g * xx).sum() / g.sum(), (g * yy).sum() / g.sum()
        size = max(x1 - x0, y1 - y0)
        worst = max(worst, math.hypot(gx - px, gy - py) / size)
    check(worst < 0.2, f'turned: each cloth glows around its own driver (glow centroid within {worst * 100:.0f} % of '
                       f'the panel size of the driver centre)')
    tb = screen_box(sc, cam, pc.parts['screen'].mesh)
    m = a1[tb[1]:tb[3], tb[0]:tb[2]].mean()
    check(m > 40 and S.magenta_fraction(p1) == 0.0, f'turned: the screen still shows its desktop (mean {m:.0f})')


# ----------------------------------------------------------------------------------------------------- clock ---
def probe_clock():
    f0, f1 = 1001, 1061
    sc = stage(frames=(f0, f1), res=(640, 360), samples=8, fps=30)
    sc['eido_frame0'] = f0
    c = VM.build_machine('c64', screen_dir=str(WORK / 'clock'), lines=['READY.'], cursor_on='solid')
    place(c)
    for f in range(f0, f1 + 1):
        t = (f - f0) / 30
        if f == 1031:
            c.parts['screen'].set_text(['READY.', 'SAY "CLOCK"', 'CLOCK', 'READY.'], 'solid')
        c.update(t, {'power': min(1.0, t / 0.5), 'voice': 0.0})
    scr = c.screens[0]
    check(c.frame_at(1.0) == 1031 and scr.f0 == f0 and int(scr.image['eido_frame_start']) == f0,
          f'clock: t = 1 s is frame {c.frame_at(1.0)} at 30 fps from 1001; the sequence starts at '
          f'{scr.image["eido_frame_start"]}')
    b30, b31 = scr._file(30).read_bytes(), scr._file(31).read_bytes()
    check(scr.drawn == 2 and b30 == scr._file(1).read_bytes() and b31 != b30,
          f'clock: one redraw, at frame 1031 (file 31); files 1-30 hold the first drawing ({scr.drawn} drawings)')
    check(abs(fc_value(c.group, 'power', 1001)) < 1e-6 and abs(fc_value(c.group, 'power', 1016) - 1.0) < 1e-6,
          'clock: power keyed on the film clock (0 at frame 1001, 1 at 1016 = 0.5 s)')
    if not RENDER:
        return
    tube = c.parts['screen'].mesh
    ct = centre_of(tube)
    cam = S.camera(sc, ct + Vector((0.04, -0.55, 0.06)), ct, lens=50)
    S.key_light(sc, ct, dist=1.2, power=40.0)
    box = screen_box(sc, cam, tube)
    frames = (995, 1016, 1030, 1031)
    paths = [S.render(WORK / f'clock_{f}.png', f) for f in frames]
    x0, y0, x1, y1 = box
    reg = {f: png_array(p)[y0:y1, x0:x1] for f, p in zip(frames, paths)}

    def changed(a, b):                          # pixels of the tube that change by more than 25 levels
        return int((np.abs(a - b).max(axis=2) > 25).sum())
    n_same, n_new = changed(reg[1016], reg[1030]), changed(reg[1030], reg[1031])
    check(n_same < 5 and n_new > 60, f'clock: the new text appears on frame 1031, not before ({n_same} pixels '
                                     f'change from 1016 to 1030, {n_new} from 1030 to 1031)')
    check(all(S.magenta_fraction(p) == 0.0 for p in paths), 'clock: frame 995 (before the range) is not magenta')
    # saved and reopened with scripts off: the drivers are plain AVERAGE drivers, the screens are files
    blend = WORK / 'clock' / 'clock_30fps.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.wm.open_mainfile(filepath=str(blend), load_ui=False, use_scripts=False)
    sc2 = bpy.context.scene
    reopened = S.render(WORK / 'clock_1031_reopened.png', 1031)
    n_re = changed(png_array(reopened)[y0:y1, x0:x1], reg[1031])
    check(sc2.frame_start == f0 and not bpy.app.autoexec_fail and n_re < 5,
          f'clock: reopened with scripts off, frame 1031 draws the same ({n_re} pixels of the tube differ)')
    strip(paths + [reopened], OUT / 'clock_30fps_from_1001.png',
          ['f995 (before the range)', 'f1016 (t 0.5 s)', 'f1030', 'f1031 (t 1 s: new text)',
           'f1031 reopened, scripts off'], h=260)


# ----------------------------------------------------------------------------------------------------- ortho ---
def probe_ortho():
    sc = stage(frames=(1, 1))
    m = VM.build_machine('mac1984', screen_dir=str(WORK / 'ortho'))
    place(m)
    m.update(0.0, {'power': 1.0, 'voice': 0.0})
    if not RENDER:
        return
    tube = m.parts['screen'].mesh
    ct = centre_of(tube)
    S.key_light(sc, ct, dist=1.3, power=40.0)
    off = Vector((0.25, -2.6, 0.35))
    cam = S.camera(sc, ct + off, ct, lens=50)
    persp = S.render(WORK / 'ortho_persp.png', 1)
    half = math.atan(cam.data.sensor_width / 2 / cam.data.lens)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 2 * off.length * math.tan(half)              # the same metres per pixel at the Mac
    ortho = S.render(WORK / 'ortho_ortho.png', 1)
    strip([persp, ortho], OUT / 'mac_far_persp_vs_ortho.png', ['perspective, 2.6 m', 'orthographic, same scale'],
          h=360)
    out = []
    for p in (persp, ortho):
        cam.data.type = 'PERSP' if p == persp else 'ORTHO'
        bpy.context.view_layer.update()
        # the 50 % desktop left of the window (canvas x 4..60, y 60..200), well inside the dither
        q0 = S.project(sc, cam, ct + Vector((-0.086, 0.0, 0.03)))
        q1 = S.project(sc, cam, ct + Vector((-0.070, 0.0, -0.02)))
        x0, x1 = sorted((int(q0[0]), int(q1[0])))
        y0, y1 = sorted((int(q0[1]), int(q1[1])))
        lum = png_array(p)[y0:y1 + 1, x0:x1 + 1].mean(axis=2)
        out.append((lum.std(), lum.mean(), lum.shape))
    (sp, mp, shp), (so, mo, sho) = out
    check(sp < 9 and so < 9 and abs(mp - mo) < 12,
          f'ortho: the dithered desktop is an even grey through both cameras (std {sp:.1f} / {so:.1f}, mean '
          f'{mp:.0f} / {mo:.0f} over {shp[1]} x {shp[0]} px)')


# ------------------------------------------------------------------------------------------------- footprint ---
def probe_footprint():
    """pixel_footprint and pixel_angle against the camera's own numbers: a plane square to the view, its emission
    the measured value, rendered to a float EXR and read back, through a landscape and a portrait perspective camera
    and an orthographic one (the screens' scanline fade and the Macintosh's filter read this measure)."""
    import bmesh
    d = 2.0
    cases = (('landscape 50 mm', (480, 270), 'PERSP', 50.0), ('portrait 24 mm', (270, 480), 'PERSP', 24.0),
             ('orthographic 1.6 m', (480, 270), 'ORTHO', 1.6))
    for tag, res, kind, v in cases:
        sc = S.fresh_scene(res=res, samples=1, frames=(1, 1))
        sc.view_settings.view_transform = 'Standard'
        sc.eevee.use_raytracing = False
        sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
        cd = bpy.data.cameras.new('fp_cam')
        cd.type = kind
        if kind == 'PERSP':
            cd.lens = v
        else:
            cd.ortho_scale = v
        cam = bpy.data.objects.new('fp_cam', cd)
        sc.collection.objects.link(cam)
        cam.location = (0.0, -d, 0.0)
        cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)          # looking along +Y
        sc.camera = cam
        me = bpy.data.meshes.new('fp_plane')
        bm = bmesh.new()
        for x, z in ((-5, -5), (5, -5), (5, 5), (-5, 5)):
            bm.verts.new((x, 0.0, z))
        bm.faces.new(bm.verts)
        bm.to_mesh(me)
        bm.free()
        plane = bpy.data.objects.new('fp_plane', me)
        sc.collection.objects.link(plane)
        mat = bpy.data.materials.new('fp_measure')
        if mat.node_tree is None:
            mat.use_nodes = True
        t = mat.node_tree
        t.nodes.clear()
        out = t.nodes.new('ShaderNodeOutputMaterial')
        em = t.nodes.new('ShaderNodeEmission')
        t.links.new(em.outputs[0], out.inputs['Surface'])
        nb = VM.Nodes(t)
        k = 100.0
        fp = nb.mul(VM.pixel_footprint(nb, sc), k)                       # metres per pixel x 100 -> red
        pa = nb.mul(VM.pixel_angle(nb, sc), k * d) if kind == 'PERSP' else 0.0  # angle x depth x 100 -> green
        nb.link(nb.comb(fp, pa, 0.0), em.inputs['Color'])
        me.materials.append(mat)
        W, H = res
        if kind == 'PERSP':
            want = d * 2.0 * (cd.sensor_width / 2.0 / cd.lens) / max(W, H)    # sensor fit AUTO: the larger side
        else:
            want = cd.ortho_scale / max(W, H)
        if not RENDER:
            continue
        r = sc.render
        r.image_settings.media_type = 'IMAGE'
        r.image_settings.file_format = 'OPEN_EXR'
        r.image_settings.color_depth = '32'
        path = WORK / f'footprint_{kind.lower()}_{W}x{H}.exr'
        path.parent.mkdir(parents=True, exist_ok=True)
        r.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(path))
        px = np.array(img.pixels[:], np.float64).reshape(H, W, 4)
        yy, xx = np.mgrid[0:H, 0:W]
        away = (np.abs(xx + 0.5 - W / 2) + np.abs(yy + 0.5 - H / 2)) > 3      # the 1-pixel fallback at the centre
        ratio = px[..., 0][away] / (want * k)
        msg = f'footprint {tag}: pixel_footprint / the camera\'s metres per pixel = {ratio.min():.4f} .. ' \
              f'{ratio.max():.4f} ({want * 1000:.3f} mm a pixel)'
        ok = abs(ratio.min() - 1) < 0.01 and abs(ratio.max() - 1) < 0.01
        if kind == 'PERSP':
            ra = px[..., 1][away] / (want * k)
            msg += f'; pixel_angle x depth {ra.min():.4f} .. {ra.max():.4f}'
            ok = ok and abs(ra.min() - 1) < 0.01 and abs(ra.max() - 1) < 0.01
        check(ok, msg)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    for key, fn in (('two', probe_two), ('turned', probe_turned), ('clock', probe_clock), ('ortho', probe_ortho),
                    ('footprint', probe_footprint)):
        if key not in ONLY:
            continue
        try:
            fn()
        except Exception:
            import traceback
            traceback.print_exc()
            check(False, f'{fn.__name__} ran to the end')
    shutil.rmtree(WORK, ignore_errors=True)
    S.summary('test_instances_clock_ortho')


main()
