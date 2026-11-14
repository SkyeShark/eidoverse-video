"""The vehicles at night: their real lamps at the guide's night level (make(lamp_power=8)) lighting a dark road, a
keyed drive with a keyed repaint, and the jet from behind. The daylight tests cannot show the lamps (at a 3 W/m2 sun a
headlight pool is faint by design), so their seats, aim and colour are judged here.

    cd <main checkout> && bash run_blender.sh \
        <worktree>/blender/tests/sdf_vehicles/test_vehicles_night_lamps.py [-- quality=balanced lamp_power=8
        w=960 h=540]
    (a GPU job: 6 GB VRAM, 16 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)

PASS lines: every lamp sits just outside its vehicle's solid, facing the part it belongs to (the SDF is positive at
the light, and the nearest surface is that lamp's part), so its own body does not shadow it; seen from above with the
vehicles hidden from the camera, each car's headlights light the road
ahead of it and none behind it (the light map with the headlights minus the one without), the cyberpunk sedan's
underglow tints the road beside its sills toward its uPaint, and the jet's afterburners light the ground under its
tail; on a keyed drive the lamps ride with the car, and a keyed repaint reaches the underglow lamps through their
drivers.
Writes out/night_lamps.png (the beauty shot and the light map from above),
out/night_drive.png (frames 1, 24 and 48 of the cyberpunk sedan driven 8 m and repainted magenta -> cyan) and
out/jet_tail.png (the jet from behind and below, and straight from behind: the canted fins, the plumes, the
afterburners' light).
"""

import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vcommon as V  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend import sdf  # noqa: E402
from eidoblend.sdf.vehicles import parts as P  # noqa: E402
from eidoblend.sdf.vehicles.vehicle import _set_interpolation  # noqa: E402

A = V.args()
W, H = int(A.get('w', '960')), int(A.get('h', '540'))
QUALITY = A.get('quality', 'balanced')
POWER = float(A.get('lamp_power', '8'))
CACHE = os.path.join(V.OUT, 'cache_night')
EX = sdf.EXAMPLES
# each lamp role's part id (the map()'s material id the light belongs to)
ROLE_PART = {'head': 'head', 'tail': 'tail', 'underglow': 'underglow', 'afterburner': 'plume'}


def night_stage():
    """A dark road under a night sky: the city HDRI at 1.5 % (a city's glow, for reflections), a faint blue moon."""
    V.purge()
    sc = V.stage(W, H, 16, hdri=True, hdri_strength=0.015, sun_energy=0.0, ground_size=90.0,
                 ground_color=(0.045, 0.045, 0.05), ground_roughness=0.55, ground_metallic=0.0)
    ld = bpy.data.lights.new('moon', 'SUN')
    ld.energy = 0.04
    ld.color = (0.62, 0.72, 1.0)
    ld.angle = math.radians(0.5)
    ob = bpy.data.objects.new('moon', ld)
    sc.collection.objects.link(ob)
    ob.rotation_euler = Vector(V.three(-3.0, 8.0, 2.0)).normalized().to_track_quat('Z', 'Y').to_euler()
    return sc


def lamp_seats(car):
    """[(lamp name, role, field at the light, part at the nearest surface)] in the SDF's own frame."""
    prog = car.program
    ids = P.IDS[car.kind]
    out = []
    for ob in car.lamps:
        b = ob.location                                   # parented without an inverse: the car's local frame
        p3 = np.array([[b.x, b.z, -b.y]], np.float32)     # Blender (x, y, z) -> three (x, z, -y)
        d = float(prog.dist(p3)[0][0])
        g = prog.grad(p3, 0.0005)[2][0]
        g = g / max(1e-9, float(np.linalg.norm(g)))
        q = (p3 - g[None, :] * d).astype(np.float32)        # one Newton step onto the surface
        q = (q - g[None, :] * float(prog.dist(q)[0][0])).astype(np.float32)
        mid = int(round(float(prog.dist(q)[1][0])))
        out.append((ob.name, ob['sdf_vehicle_lamp'], d, ids.get(mid, str(mid))))
    return out


def render_exr(path):
    sc = bpy.context.scene
    fmt = sc.render.image_settings
    keep = fmt.file_format
    fmt.media_type = 'IMAGE'                               # (Blender 5.2: the media type before the format)
    fmt.file_format = 'OPEN_EXR'
    fmt.color_depth = '32'
    ok = V.render(path)
    fmt.media_type = 'IMAGE'
    fmt.file_format = keep
    return ok


def read_exr(path):
    import OpenImageIO as oiio
    return np.asarray(oiio.ImageBuf(path).get_pixels(oiio.FLOAT))[..., :3]    # row 0 at the top


# ===================================================================================== the night lineup ===
sc = night_stage()
LINEUP = [('stylized_modern_sedan', -5.5, 0.0, {'paint_color': 0x8a1b1b}),
          ('stylized_cyberpunk_sedan', -1.5, 0.0, {'paint_color': 0xff2bd6}),
          ('stylized_sci_fi_sleek_car', 2.5, 0.0, {}),
          ('stylized_fighter_jet', 8.5, 1.2, {'camo': 'sky'})]
cars = []
t0 = time.perf_counter()
for name, x, hover, opts in LINEUP:
    car = EX[name].make(name=f'night_{name}', cache_dir=CACHE, quality=QUALITY, lamp_power=POWER,
                        location=(x, 0.0, 0.0), log=None, **opts)
    car.place_on_ground(0.0)
    car.object.location.z += hover
    cars.append(car)
print(f'[night] four vehicles built in {time.perf_counter() - t0:.1f} s', flush=True)
bpy.context.view_layer.update()

# every lamp just outside its body, at its own part
bad, n = [], 0
for car in cars:
    for lname, role, d, part in lamp_seats(car):
        n += 1
        if not (0.0 < d < 0.15 and part == ROLE_PART[role]):
            bad.append(f'{lname}: field {d:.3f}, nearest part {part}')
        else:
            print(f'[night] {lname}: {d * 100:.1f} cm off its {part}', flush=True)
V.check('every lamp sits just outside its vehicle, at its own part (no lamp inside or shadowed by its body)',
        n == 4 + 6 + 4 + 2 and not bad, f'{n} lamps' + (f'; off: {bad}' if bad else ''))

# the beauty shot
cam = V.C.camera((-1.5, -15.5, 3.4), (2.2, -1.2, 0.7), lens=26.0, name='cam_night')
shots = []
p = os.path.join(V.OUT, '_night_eevee.png')
V.check('night beauty renders (EEVEE)', V.render(p), p)
shots.append(p)

# the light map: the road from above, the vehicles hidden from the camera (they still cast their shadows), once with
# every lamp and once with the headlights off: the difference is the headlights' own light
for car in cars:
    car.object.visible_camera = False
S, CX, CY = 26.0, 2.5, -2.0
top = V.C.camera((CX, CY, 40.0), (CX, CY, 0.0), name='cam_top')
top.rotation_euler = (0.0, 0.0, 0.0)
top.data.type = 'ORTHO'
top.data.ortho_scale = S
top.data.clip_end = 100.0
sc.camera = top
exr = os.path.join(V.OUT, '_night_lightmap.exr')
V.check('light map renders', render_exr(exr), exr)
img = read_exr(exr)
heads = [ob for car in cars for ob in car.lamps if ob.get('sdf_vehicle_lamp') == 'head']
for ob in heads:
    ob.hide_render = True
exr_off = os.path.join(V.OUT, '_night_lightmap_no_heads.exr')
render_exr(exr_off)
img_heads = img - read_exr(exr_off)
for ob in heads:
    ob.hide_render = False
px = S / W


def box(x0, x1, y0, y1, a=None):
    """Mean linear colour over a world-space box (Blender x, y) of the light map (or of `a`, an image like it)."""
    a = img if a is None else a
    i0, i1 = int((x0 - (CX - S / 2)) / px), int((x1 - (CX - S / 2)) / px)
    top_y = CY + S * H / W / 2
    j0, j1 = int((top_y - y1) / px), int((top_y - y0) / px)
    a = a[max(0, j0):max(1, j1), max(0, i0):max(1, i1)]
    return a.reshape(-1, 3).mean(axis=0)


def lum(c):
    return float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])


ratios = {}
for car, (name, x, _hover, _o) in zip(cars[:3], LINEUP[:3]):
    bb = np.array([car.object.matrix_world @ Vector(c) for c in car.object.bound_box])
    front, rear = float(bb[:, 1].min()), float(bb[:, 1].max())
    ahead = lum(box(x - 0.7, x + 0.7, front - 5.0, front - 1.0, img_heads))
    behind = lum(box(x - 0.7, x + 0.7, rear + 1.0, rear + 5.0, img_heads))
    ratios[name] = (ahead, behind, lum(box(x - 0.7, x + 0.7, front - 5.0, front - 1.0)))
V.check('each car\'s headlights light the road ahead of it, and none behind it (the light map with the headlights '
        'minus without)', all(a > 0.004 and a > 20.0 * max(b, 0.0) for a, b, _t in ratios.values()),
        '; '.join(f'{k}: their light ahead {a:.4f} of {t:.4f}, behind {b:.5f}' for k, (a, b, t) in ratios.items()))
cx = LINEUP[1][1]
sill = (box(cx - 1.5, cx - 0.95, -1.0, 1.0) + box(cx + 0.95, cx + 1.5, -1.0, 1.0)) / 2
mx = LINEUP[0][1]
plain = (box(mx - 1.5, mx - 0.95, -1.0, 1.0) + box(mx + 0.95, mx + 1.5, -1.0, 1.0)) / 2
V.check('the underglow tints the road beside the cyberpunk sedan\'s sills toward its uPaint (magenta)',
        sill[0] > 2.0 * sill[1] and sill[2] > 1.5 * sill[1] and lum(sill) > 2.0 * lum(plain),
        f'beside the sills {sill.round(4).tolist()}, beside the modern sedan {plain.round(4).tolist()}')
jet = cars[3]
jb = np.array([jet.object.matrix_world @ Vector(c) for c in jet.object.bound_box])
jx = LINEUP[3][1]
under_tail = lum(box(jx - 1.4, jx + 1.4, float(jb[:, 1].max()) - 0.6, float(jb[:, 1].max()) + 1.6))
ahead_jet = lum(box(jx - 1.4, jx + 1.4, float(jb[:, 1].min()) - 3.0, float(jb[:, 1].min()) - 0.8))
V.check('the afterburners light the ground under the jet\'s tail', under_tail > 4.0 * ahead_jet,
        f'under the tail {under_tail:.3f}, ahead of the nose {ahead_jet:.4f}')
lm = V.save_linear_png(os.path.join(V.OUT, '_night_lightmap.png'), img[::-1], exposure=1.0)
shots.append(lm)
os.remove(exr)
os.remove(exr_off)
V.sheet(shots, os.path.join(V.OUT, 'night_lamps.png'), cols=2)
for car in cars:
    car.object.visible_camera = True

# ================================================================================= a keyed drive at night ===
sc = night_stage()
car = EX['stylized_cyberpunk_sedan'].make(name='night_drive', cache_dir=CACHE, quality=QUALITY, lamp_power=POWER,
                                          paint_color='magenta', log=None)
car.place_on_ground(0.0)
sc.frame_start, sc.frame_end = 1, 48
ob = car.object
for f, y in ((1, 2.0), (48, -6.0)):
    ob.location.y = y
    ob.keyframe_insert('location', index=1, frame=f)
for f in (1, 48):
    _set_interpolation(ob, 'location', f, 'LINEAR')
car.key_uniform('uPaint', frame=1, value='magenta')
car.key_uniform('uPaint', frame=48, value='cyan')
cam = V.C.camera((9.0, -3.2, 1.8), (0.0, -2.6, 0.55), lens=22.0, name='cam_drive')
shots = []
for f in (1, 24, 48):
    sc.frame_set(f)
    p = os.path.join(V.OUT, f'_night_drive_f{f}.png')
    V.render(p)
    shots.append(p)
sc.frame_set(48)
dg = bpy.context.evaluated_depsgraph_get()
ug = [o for o in car.lamps if o.get('sdf_vehicle_lamp') == 'underglow']
heads = [o for o in car.lamps if o.get('sdf_vehicle_lamp') == 'head']
ug_col = tuple(ug[0].evaluated_get(dg).data.color)
head_y = heads[0].matrix_world.translation.y
want_head_y = -6.0 + (-2.26)                   # the car's origin at y -6, its headlight 2.26 m ahead (three z)
V.check('a keyed drive carries the lamps with the car', abs(head_y - want_head_y) < 0.02,
        f'headlight at y {head_y:.3f} on frame 48 (want {want_head_y:.3f})')
V.check('a keyed repaint reaches the underglow lamps (drivers on the live uniform)',
        np.allclose(ug_col, P.linear_color('cyan'), atol=2e-3), f'underglow lamp colour {np.round(ug_col, 3).tolist()}')
V.sheet(shots, os.path.join(V.OUT, 'night_drive.png'), cols=3)

# ======================================================================================= the jet's tail ===
V.purge()
sc = V.stage(W, H, 16)
jet = EX['stylized_fighter_jet'].make(name='tail_jet', cache_dir=CACHE, quality=QUALITY, camo='desert', log=None)
jet.place_on_ground(0.0)
jet.object.location.z += 1.2
bpy.context.view_layer.update()
c = jet.object.matrix_world.translation
shots = []
V.C.camera((c.x - 4.2, c.y + 8.5, c.z - 0.9), (c.x, c.y + 1.0, c.z + 0.1), lens=40.0, name='cam_tail_low')
p = os.path.join(V.OUT, '_jet_tail_low.png')
V.render(p)
shots.append(p)
V.C.camera((c.x, c.y + 12.0, c.z + 0.35), (c.x, c.y, c.z + 0.2), lens=50.0, name='cam_tail_rear')
p = os.path.join(V.OUT, '_jet_tail_rear.png')
V.check('the jet from behind renders', V.render(p), p)
shots.append(p)
V.sheet(shots, os.path.join(V.OUT, 'jet_tail.png'), cols=2)

V.summary()
