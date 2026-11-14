"""The judge's views (SURFACING_DESIGN.md section 6) and the camera they share with the renders (numpy; no bpy):

    from surfacing_judge import views as V
    plan = V.load()                      # views.json: {recipe: dict(reference, params, views=[...])}
    v = V.view('canyon', 'approach_walk')
    cam = V.Camera.from_view(v, centre, ground_z)     # the pinhole review_views.py builds in Blender
    px, py, depth = cam.project(x, y, z)              # world points into the 960 x 540 picture
    V.photo_path(v)                      # the view's photograph, or None
    V.photo_ground(v, shape)             # the photograph's ground as a mask (the regions marked in photos.json)
    V.check(stack, v)                    # does this camera see its subject on this terrain? (check_views.py)
    V.preview(stack, v)                  # the view as grey clay, ray-cast on the saved levels (no render)
    V.viewpoint(stack, target, distance) # Terrain.viewpoint's rule on a saved terrain: a standing point that sees
                                         # the target (how make_views.py moves a failing camera)

views.json has the shape of the review's out/review/views_plan.json (recipes at the top, each with its views), so
any tool that takes that plan takes this file (review_views.py --plan, its default now). A view is the review's
unless its `origin` says otherwise:
    name, kind ('eye' | 'aerial'), caption
    cam        [x, y] metres from the main tile's centre (x east, y north)
    cam_z      ['ground', metres above the ground there] or ['abs', z]
    aim        [x, y, z]: x, y from the tile's centre, z absolute
    lens       mm on a 36 mm wide sensor
    frame      where the aim lands in the picture, 0..1 from the left and from the top
    focus      hero levels around the camera (it must stand in the main tile)
    photo      the matched photograph, relative to blender/tests/terrain/out/ (the packages' fetch_photos.py scripts
               bring them), or null
    origin     'review'; 'review, moved: <what failed and what changed>'; 'review, kept: <why>'; 'judge: <the kind
               of view added>'
    crops      optional: the two boxes [x0, y0, x1, y1] (render pixels) the board enlarges; else board.py picks them
The recipe's `reference` (its extent is the terrain's size) and `params` (its knobs) are what make_terrain is called
with. Photographs carry their regions in photos.json, keyed by the photograph's path (fractions of its width and
height, from its top left): `ground` boxes (the land the render's ground is compared with: no sky, water, buildings
or people), and named `regions` where a view compares two kinds of ground (cliff against talus, floor against wall).
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

from . import HERE, OUT_ROOT

VIEWS_JSON = os.path.join(HERE, 'views.json')
PHOTOS_JSON = os.path.join(HERE, 'photos.json')
SIZE = (960, 540)
SENSOR_MM = 36.0


# --------------------------------------------------------------------------------------------- the camera ---

class Camera:
    """A pinhole with a level horizon: eye (x, y, z), forward (unit), lens in mm on a 36 mm wide sensor."""

    def __init__(self, eye, forward, lens):
        self.eye = np.asarray(eye, np.float64)
        f = np.asarray(forward, np.float64)
        self.f = f / np.linalg.norm(f)
        r = np.cross(self.f, (0.0, 0.0, 1.0))
        self.r = r / max(np.linalg.norm(r), 1e-12)
        self.u = np.cross(self.r, self.f)
        self.lens = float(lens)

    @classmethod
    def from_aim(cls, eye, target, frame=(0.5, 0.5), lens=35.0, size=SIZE):
        """The camera at eye that puts target at frame (0..1 from the left, from the top): the review's rule
        (review_views.aim_camera)."""
        dx, dy, dz = (float(target[i]) - float(eye[i]) for i in range(3))
        yaw_t = math.atan2(dy, dx)
        pitch_t = math.atan2(dz, math.hypot(dx, dy))
        u = (frame[0] - 0.5) * SENSOR_MM / lens
        v = (0.5 - frame[1]) * SENSOR_MM * size[1] / size[0] / lens
        yaw = yaw_t + math.atan(u)
        pitch = pitch_t - math.atan(v)
        return cls(eye, (math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)), lens)

    @classmethod
    def from_heading(cls, eye, heading_deg, pitch_deg, lens=35.0):
        """The camera a render record describes: eye, compass heading (0 north, 90 east) and pitch, in degrees."""
        h, p = math.radians(heading_deg), math.radians(pitch_deg)
        return cls(eye, (math.sin(h) * math.cos(p), math.cos(h) * math.cos(p), math.sin(p)), lens)

    @classmethod
    def from_record(cls, rec):
        """The camera of a review_views.py record (camera, heading_deg, pitch_deg, lens), or None."""
        if not rec or 'camera' not in rec:
            return None
        return cls.from_heading(rec['camera'], rec['heading_deg'], rec['pitch_deg'], rec.get('lens', 35.0))

    @classmethod
    def from_view(cls, v, centre, ground_z):
        """A view's camera on a terrain: centre = the main tile's centre (x, y); ground_z = the ground under the
        camera (used when cam_z is ['ground', dz])."""
        ex, ey = v['cam'][0] + centre[0], v['cam'][1] + centre[1]
        kind, dz = v['cam_z']
        ez = float(ground_z) + float(dz) if kind == 'ground' else float(dz)
        return cls.from_aim((ex, ey, ez), (v['aim'][0] + centre[0], v['aim'][1] + centre[1], v['aim'][2]),
                            v.get('frame', (0.5, 0.5)), v['lens'])

    @property
    def heading_deg(self):
        """Compass degrees the camera looks toward (0 north, 90 east)."""
        return (90.0 - math.degrees(math.atan2(self.f[1], self.f[0]))) % 360.0

    @property
    def pitch_deg(self):
        return math.degrees(math.asin(max(-1.0, min(1.0, float(self.f[2])))))

    def project(self, x, y, z, size=SIZE):
        """World points -> (pixel x, pixel y, depth along the view axis); behind the camera the depth is <= 0."""
        W, H = size
        d = np.stack([np.asarray(x, np.float64) - self.eye[0], np.asarray(y, np.float64) - self.eye[1],
                      np.asarray(z, np.float64) - self.eye[2]], -1)
        zc = d @ self.f
        fpx = self.lens / SENSOR_MM * W
        s = fpx / np.where(np.abs(zc) < 1e-9, 1e-9, zc)
        return W / 2.0 + (d @ self.r) * s, H / 2.0 - (d @ self.u) * s, zc

    def rays(self, nx=48, ny=27, size=SIZE):
        """Unit directions through the centres of an nx x ny grid of the picture: (ny, nx, 3), row 0 the top."""
        W, H = size
        fpx = self.lens / SENSOR_MM * W
        px = (np.arange(nx) + 0.5) / nx * W - W / 2.0
        py = H / 2.0 - (np.arange(ny) + 0.5) / ny * H
        d = (self.f[None, None, :] * fpx + px[None, :, None] * self.r[None, None, :]
             + py[:, None, None] * self.u[None, None, :])
        return d / np.linalg.norm(d, axis=2, keepdims=True)


def raycast(height_at, eye, dirs, far, near=2.0, growth=1.02, min_step=1.0):
    """Where rays from eye first meet the ground: distances (the shape of dirs without its last axis; inf for sky).
    Steps grow by `growth` per step from `near` (at least min_step), and a hit is placed by one linear step back."""
    eye = np.asarray(eye, np.float64)
    D = np.asarray(dirs, np.float64).reshape(-1, 3)
    hit = np.full(len(D), np.inf)
    live = np.ones(len(D), bool)
    t0 = float(near)
    g0 = eye[2] + t0 * D[:, 2] - height_at(eye[0] + t0 * D[:, 0], eye[1] + t0 * D[:, 1])
    while t0 < far and live.any():
        t1 = min(max(t0 * growth, t0 + min_step), far)
        i = np.flatnonzero(live)
        g1 = eye[2] + t1 * D[i, 2] - height_at(eye[0] + t1 * D[i, 0], eye[1] + t1 * D[i, 1])
        under = g1 < 0.0
        if under.any():
            a, b = g0[i][under], g1[under]
            hit[i[under]] = t0 + (t1 - t0) * np.clip(a / np.maximum(a - b, 1e-9), 0.0, 1.0)
            live[i[under]] = False
        g0[i] = g1
        t0 = t1
    return hit.reshape(np.asarray(dirs).shape[:-1])


# ----------------------------------------------------------------------------------------- the views file ---

_PLAN = None
_PHOTOS = None


def load(path=None):
    """{recipe: dict(reference, params, views)} from views.json, read once. A path makes that file the plan every
    later call returns (a tool's --plan: another set of cameras in this format; the review's own
    out/review/views_plan.json reads too, its photograph paths as they are)."""
    global _PLAN
    if path is None and _PLAN is not None:
        return _PLAN
    with open(path or VIEWS_JSON, encoding='utf-8') as f:
        _PLAN = json.load(f)
    return _PLAN


def photos():
    """{photograph (relative to out/): dict(ground=[boxes], regions={name: [boxes]}, note)} from photos.json."""
    global _PHOTOS
    if _PHOTOS is None:
        _PHOTOS = {}
        if os.path.exists(PHOTOS_JSON):
            with open(PHOTOS_JSON, encoding='utf-8') as f:
                _PHOTOS = json.load(f)
    return _PHOTOS


def view(recipe, name):
    for v in load()[recipe]['views']:
        if v['name'] == name:
            return v
    raise KeyError(f'no view {name!r} of {recipe!r}; its views: '
                   + ', '.join(v['name'] for v in load()[recipe]['views']))


def kind_of(v):
    """'eye' (a person standing: within 10 m of the ground) or 'aerial'."""
    k = v.get('kind')
    if k:
        return k
    return 'eye' if v['cam_z'][0] == 'ground' and float(v['cam_z'][1]) <= 10.0 else 'aerial'


def photo_path(v):
    """The view's photograph on this machine, or None (no photograph, or not fetched here)."""
    p = v.get('photo')
    if not p:
        return None
    full = p if os.path.isabs(p) else os.path.join(OUT_ROOT, p.replace('/', os.sep))
    return full if os.path.exists(full) else None


def photo_key(v):
    """The photograph as photos.json names it: its path relative to blender/tests/terrain/out/."""
    p = (v.get('photo') or '').replace('\\', '/')
    marker = '/tests/terrain/out/'
    return p.split(marker, 1)[1] if marker in p else p


def fit_box(w, h, aspect=16.0 / 9.0, bias=0.45):
    """The 16:9 window of a w x h photograph the boards show (its centre across, a little above its middle down, as
    the review's boards crop it): (x0, y0, x1, y1) pixels."""
    if w / h > aspect:
        nw = int(h * aspect)
        x0 = (w - nw) // 2
        return x0, 0, x0 + nw, h
    nh = int(w / aspect)
    top = max(0, min(h - nh, int(bias * (h - nh))))
    return 0, top, w, top + nh


def boxes_mask(boxes, shape):
    """Boxes in fractions of the picture (x0, y0, x1, y1 from the top left) as a boolean mask of `shape` (H, W)."""
    H, W = shape[:2]
    m = np.zeros((H, W), bool)
    for x0, y0, x1, y1 in boxes or []:
        m[int(round(y0 * H)):int(round(y1 * H)), int(round(x0 * W)):int(round(x1 * W))] = True
    return m


def photo_ground(v, shape):
    """The photograph's ground as a mask of `shape` (the whole photograph resized, not its 16:9 window): the
    `ground` boxes marked for it in photos.json; None when it has none."""
    rec = photos().get(photo_key(v))
    if not rec or not rec.get('ground'):
        return None
    return boxes_mask(rec['ground'], shape)


def photo_region(v, name, shape):
    rec = photos().get(photo_key(v))
    if not rec or name not in (rec.get('regions') or {}):
        return None
    return boxes_mask(rec['regions'][name], shape)


# ------------------------------------------------------------------------------------- does the camera see? ---

def main_centre(stack):
    lv = stack.levels[stack.main]
    return lv['x0'] + lv['side'] / 2.0, lv['y0'] + lv['side'] / 2.0


def camera_of(stack, v):
    """(Camera, ground z under it, aim point (x, y, z) in world metres) of a view on a saved terrain."""
    centre = main_centre(stack)
    ex, ey = v['cam'][0] + centre[0], v['cam'][1] + centre[1]
    ground = float(stack.height_at(ex, ey))
    target = np.array([v['aim'][0] + centre[0], v['aim'][1] + centre[1], v['aim'][2]], np.float64)
    return Camera.from_view(v, centre, ground), ground, target


def check(stack, v, grid=(160, 90), far_factor=1.0):
    """A view's camera on a saved terrain (terrain_data.Stack, main and context levels): what it sees.

        eye, heading_deg, pitch_deg, aim_m   the camera, and its distance to the aim
        stands        'main' | 'context' | 'outside': where the camera's foot is
        height_m      the eye above the ground under it
        aim_above_m   the aim's height over the ground under it: about 0 for an aim on the ground or on a wall's
                      face, a large negative number for an aim that only gives a direction (a point along the
                      photograph's heading and pitch, under the far ground) or one sunk in a wall it looks at
        aim_seen      how far toward the aim the ray at it travels before it meets the ground, as a share of the
                      way (1 when it reaches the aim)
        aim_clear_m   the least height of the straight line to the aim over the ground between
        ground, sky   the shares of the picture that are ground and sky (a grid of rays, 160 x 90)
        blocked       the share of the picture's upper two thirds filled by rising ground in front of the camera:
                      ground nearer than a tenth of the way to the aim and nearer than half the distance at which
                      the same ray would meet level ground at the camera's foot (so the near foreground of a
                      camera looking down a plain or over a brink does not count; a wall or a slope rising in
                      front does)
        near_m        the median distance of the ground in the lowest sixth of the picture
        fails         what is wrong, in words ([] when the camera sees its subject)
        warns         what a reader should know (an eye-level camera on a context level draws its foreground at the
                      context's cells)
    A view fails when its camera is outside the terrain or under the ground, when rising ground in front fills over
    a quarter of the upper two thirds of the picture (it faces a wall or a rise), when under 15 % of the picture is
    ground, or when the aim lies on or over the ground (no deeper under it than 3 m or a twentieth of the way) and
    the ray at it meets the ground before 60 % of the way (a nearer rise hides the subject). The straight line to
    an aim on a wall's face ends inside that wall, so a
    dipping line alone is no failure: the renders of the review's floor and prairie views read right with lines
    that dip 50-585 m. The saved main level stands in for the hero levels (an eye-level camera's own footing moves
    by decimetres)."""
    lv = stack.levels[stack.main]
    cam, ground, target = camera_of(stack, v)
    eye = cam.eye
    ex, ey = float(eye[0]), float(eye[1])
    dist = float(np.linalg.norm(target - eye))
    outer = stack.levels[0]
    inside = lambda L, m=0.0: (L['x0'] + m <= ex <= L['x0'] + L['side'] - m      # noqa: E731
                               and L['y0'] + m <= ey <= L['y0'] + L['side'] - m)
    stands = 'main' if inside(lv) else ('context' if inside(outer) else 'outside')
    surf = _surface(stack)
    # the straight line to the aim, from 3 m out to 97 % of the way
    t = np.linspace(min(3.0 / max(dist, 3.0), 0.5), 0.97, 400)
    line = eye[None, :] + t[:, None] * (target - eye)[None, :]
    clear = float((line[:, 2] - surf(line[:, 0], line[:, 1])).min())
    aim_above = float(target[2] - surf(target[0], target[1]))
    far = max(4.0 * dist, 1.5 * outer['side']) * far_factor
    d_aim = (target - eye) / max(dist, 1e-9)
    aim_hit = float(raycast(surf, eye, d_aim[None, :], 1.02 * dist, near=1.5)[0])
    aim_seen = 1.0 if not np.isfinite(aim_hit) else min(aim_hit / max(dist, 1e-9), 1.0)
    rays = cam.rays(*grid)
    hit = raycast(surf, eye, rays, far, near=1.5)
    ny = hit.shape[0]
    is_ground = np.isfinite(hit)
    down = -rays[..., 2]
    level = np.where(down > 1e-6, max(float(eye[2] - ground), 0.5) / np.maximum(down, 1e-6), np.inf)
    rising = (hit < 0.1 * dist) & (hit < 0.5 * level)
    blocked = float(rising[: (2 * ny) // 3].mean())
    low = hit[(5 * ny) // 6:]
    near = float(np.median(low[np.isfinite(low)])) if np.isfinite(low).any() else None
    fails, warns = [], []
    height = float(eye[2] - ground)
    if stands == 'outside':
        fails.append('the camera stands outside the terrain')
    if height < 0.5:
        fails.append(f'the camera is {-height:.0f} m under the ground')
    if kind_of(v) == 'eye' and stands == 'main' and not bool(dry(stack, ex, ey)):
        fails.append('the camera stands in a lake or under the sea')
    if blocked > 0.25:
        fails.append(f'rising ground nearer than a tenth of the way to the aim fills {100 * blocked:.0f} % of the '
                     f'upper picture: the camera faces a wall or a rise')
    if float(is_ground.mean()) < 0.15:
        fails.append(f'only {100 * float(is_ground.mean()):.0f} % of the picture is ground')
    if aim_above > -max(3.0, 0.05 * dist) and aim_seen < 0.6:
        fails.append(f'the aim stands {aim_above:+.0f} m over the ground, and the ray at it meets the ground '
                     f'{100 * aim_seen:.0f} % of the way there: a nearer rise hides the subject')
    if kind_of(v) == 'eye' and stands != 'main':
        warns.append('an eye-level camera on a context level: no hero levels under it, its foreground is drawn at '
                     f"{stack.levels[0]['cell']:.0f}-{stack.levels[max(stack.main - 1, 0)]['cell']:.0f} m cells")
    return dict(eye=[float(x) for x in eye], ground_z=ground, height_m=height, heading_deg=cam.heading_deg,
                pitch_deg=cam.pitch_deg, aim_m=dist, stands=stands, aim_above_m=aim_above, aim_seen=aim_seen,
                aim_clear_m=clear, ground=float(is_ground.mean()), sky=float(1.0 - is_ground.mean()),
                blocked=blocked, near_m=near, fails=fails, warns=warns, hit=hit)


def _surface(stack):
    """Where rays stop on a stack: its surface_at (the ground or the water over it), else its height_at."""
    return getattr(stack, 'surface_at', None) or stack.height_at


def _normals(height_at, x, y, step):
    """Unit ground normals at world points by central differences `step` metres wide (an array or a number)."""
    hx = (height_at(x + step, y) - height_at(x - step, y)) / (2.0 * step)
    hy = (height_at(x, y + step) - height_at(x, y - step)) / (2.0 * step)
    n = np.stack([-hx, -hy, np.ones_like(hx)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def preview(stack, v, size=(240, 135), sun_left_deg=70.0, sun_elev_deg=35.0):
    """The view as grey clay without a render: rays from the camera onto the saved levels (main and context), each
    hit shaded by its ground normal under a sun `sun_left_deg` left of the view (the review renders' rule), fading
    into a sky colour with distance; the aim a red cross. (H, W, 3) uint8. Coarse near an eye-level camera (the
    hero levels are not saved), right in its composition: what it faces, where the horizon lies."""
    nx, ny = size
    cam, _ground, target = camera_of(stack, v)
    D = cam.rays(nx, ny)
    dist = float(np.linalg.norm(target - cam.eye))
    outer = stack.levels[0]
    far = max(4.0 * dist, 1.5 * outer['side'])
    surf = _surface(stack)
    hit = raycast(surf, cam.eye, D, far, near=1.0)
    img = np.zeros((ny, nx, 3))
    rows = np.linspace(0.0, 1.0, ny)[:, None, None]
    img[:] = (1.0 - rows) * np.array([0.42, 0.58, 0.80]) + rows * np.array([0.72, 0.80, 0.90])
    ok = np.isfinite(hit)
    if ok.any():
        P = cam.eye[None, :] + hit[ok][:, None] * D[ok]
        main = stack.levels[stack.main]
        step = np.maximum(main['cell'], 0.004 * hit[ok])
        N = _normals(stack.height_at, P[:, 0], P[:, 1], step)
        yaw = math.atan2(cam.f[1], cam.f[0]) + math.radians(sun_left_deg)
        el = math.radians(sun_elev_deg)
        L = np.array([math.cos(el) * math.cos(yaw), math.cos(el) * math.sin(yaw), math.sin(el)])
        shade = 0.22 + 0.78 * np.clip(N @ L, 0.0, 1.0)
        fog = 1.0 - np.exp(-hit[ok] / (0.45 * outer['side']))
        col = shade[:, None] * np.array([0.62, 0.60, 0.56])
        wet = np.asarray(surf(P[:, 0], P[:, 1]), np.float64) - np.asarray(stack.height_at(P[:, 0], P[:, 1])) > 0.05
        col[wet] = np.array([0.20, 0.33, 0.45])                        # lakes and the sea, flat blue
        img[ok] = col * (1.0 - fog[:, None]) + np.array([0.70, 0.76, 0.84]) * fog[:, None]
    out = (np.clip(img, 0.0, 1.0) * 255.0).astype(np.uint8)
    px, py, zc = cam.project(*target, size=size)
    if zc > 0 and 0 <= px < nx and 0 <= py < ny:
        i, j = int(px), int(py)
        out[j, max(i - 4, 0):i + 5] = (255, 40, 40)
        out[max(j - 4, 0):j + 5, i] = (255, 40, 40)
    return out


def dry(stack, x, y, level='main'):
    """Where a camera can stand: no lake water over the ground (the level's `water` field, metres) and above the sea
    (the terrain's sea level, when it has one). Boolean array of the points' shape."""
    from .terrain_data import bilinear
    i = stack.main if level == 'main' else int(level)
    lv = stack.levels[i]
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    ok = np.ones(np.broadcast(x, y).shape, bool)
    w = stack.fields[i].get('water')
    if w is not None:
        ok &= bilinear(w, lv, x, y) <= 0.05
    sea = (getattr(stack, 'info', None) or {}).get('sea_level')
    if sea is not None:
        ok &= np.asarray(stack.height_at(x, y)) > float(sea) + 0.5
    return ok


def viewpoint(stack, target, distance, eye_height=1.7, heading=None, max_slope_deg=30.0, lens_mm=35.0,
              look_dz=0.0, prefer=None, clearance_m=1.0, within='main', exclude=None):
    """Terrain.viewpoint's rule (terrain/api.py) on a saved terrain: a standing point about `distance` metres from
    `target` ((x, y) or (x, y, z), world metres) from which an eye `eye_height` over the ground sees the target,
    the sight line clearing the ground by clearance_m from 3 m out to 97 % of the way, the footing under
    max_slope_deg and dry (views.dry: Terrain.viewpoint reads the mesh, which runs under lakes and the sea, so it can
    stand a camera on a lake bed), inside the `within` level ('main' or a level index) and outside the `exclude` box
    (x0, y0, x1, y1: the main window, for an eye view that must stand on a context ring). Candidates every 5 degrees
    around the target
    at 0.55-1.5 x the distance, ranked by the heading asked for (compass degrees the camera looks toward), then
    prefer 'low' or 'high', then the distance asked for, then the clearance. Returns dict(eye, target, ground_z,
    heading_deg, pitch_deg, distance, clearance_m, lens_mm), or None when no candidate sees the target. The ground
    is the saved levels' (bilinear on the cells) where Terrain.viewpoint reads the mesh's triangles: a footing
    differs by decimetres."""
    tx, ty = float(target[0]), float(target[1])
    tz = (float(target[2]) if len(target) > 2 else float(stack.height_at(tx, ty))) + look_dz
    lv = stack.levels[stack.main if within == 'main' else int(within)]
    az = np.radians(np.arange(0.0, 360.0, 5.0))
    fac = np.array([1.0, 0.85, 1.15, 0.7, 1.3, 0.55, 1.5])
    A, F = np.meshgrid(az, fac)
    A, F = A.ravel(), F.ravel()
    D = F * float(distance)
    px, py = tx + D * np.sin(A), ty + D * np.cos(A)          # A: compass bearing from the target to the eye
    m = 2.0 * lv['cell']
    ok = (px >= lv['x0'] + m) & (px <= lv['x0'] + lv['side'] - m) & (py >= lv['y0'] + m) & \
         (py <= lv['y0'] + lv['side'] - m)
    if exclude is not None:
        ex0, ey0, ex1, ey1 = exclude
        ok &= ~((px >= ex0) & (px <= ex1) & (py >= ey0) & (py <= ey1))
    if not ok.any():
        return None
    px, py, A, D = px[ok], py[ok], A[ok], D[ok]
    gz = np.asarray(stack.height_at(px, py), np.float64)
    nz = _normals(stack.height_at, px, py, lv['cell'])[:, 2]
    flat = (np.degrees(np.arccos(np.clip(nz, -1, 1))) <= max_slope_deg) & dry(stack, px, py)
    ez = gz + eye_height
    k = 160
    t0 = np.minimum(3.0 / np.maximum(D, 3.0), 0.5)[:, None]
    t = t0 + (0.97 - t0) * np.linspace(0.0, 1.0, k)[None, :]
    lx = px[:, None] + (tx - px[:, None]) * t
    ly = py[:, None] + (ty - py[:, None]) * t
    lz = ez[:, None] + (tz - ez[:, None]) * t
    clear = (lz - _surface(stack)(lx, ly)).min(1)
    good = flat & (clear >= clearance_m)
    if not good.any():
        return None
    score = np.zeros(len(px))
    look_heading = (np.degrees(A) + 180.0) % 360.0
    if heading is not None:
        score -= np.abs((look_heading - heading + 180.0) % 360.0 - 180.0) / 10.0
    if prefer in ('low', 'high'):
        rel = (gz - gz.min()) / max(float(np.ptp(gz)), 1e-6)
        score += (1.0 - rel if prefer == 'low' else rel) * 6.0
    score -= np.abs(D / float(distance) - 1.0) * 4.0
    score += np.minimum(clear, 50.0) / 50.0
    score[~good] = -np.inf
    b = int(np.argmax(score))
    eye = (float(px[b]), float(py[b]), float(ez[b]))
    dist = float(math.hypot(tx - eye[0], ty - eye[1]))
    return dict(eye=eye, target=(tx, ty, tz), ground_z=float(gz[b]), heading_deg=float(look_heading[b]),
                pitch_deg=math.degrees(math.atan2(tz - eye[2], dist)), distance=dist, clearance_m=float(clear[b]),
                lens_mm=float(lens_mm))


# ------------------------------------------------------------------------------------- writing the file ---

_VIEW_KEYS = (('name', 'kind', 'origin'), ('cam', 'cam_z', 'aim', 'lens', 'frame', 'focus'), ('photo',),
              ('crops',), ('caption',))


def dumps(recipes):
    """views.json's text: one view on a few lines (who it is; the camera; the photograph; the caption), so an edit
    to a camera is a one-line diff."""
    def js(x):
        return json.dumps(x, ensure_ascii=False)
    lines = ['{']
    items = list(recipes.items())
    for ri, (recipe, rec) in enumerate(items):
        lines.append(f' {js(recipe)}: {{"reference": {js(rec.get("reference"))}, "params": {js(rec.get("params"))}, '
                     f'"views": [')
        for vi, v in enumerate(rec['views']):
            rows = []
            for keys in _VIEW_KEYS:
                parts = [f'{js(k)}: {js(v[k])}' for k in keys if k in v]
                if parts:
                    rows.append(', '.join(parts))
            extra = [k for k in v if not any(k in keys for keys in _VIEW_KEYS)]
            if extra:
                rows.append(', '.join(f'{js(k)}: {js(v[k])}' for k in extra))
            body = ',\n   '.join(rows)
            lines.append('  {' + body + '}' + (',' if vi + 1 < len(rec['views']) else ''))
        lines.append(' ]}' + (',' if ri + 1 < len(items) else ''))
    lines.append('}')
    return '\n'.join(lines) + '\n'


# ------------------------------------------------------------------- the review's plan as the judge's file ---

def import_review_plan(plan_path, references, params=None):
    """The review's views_plan.json as this module's recipes dict: every view copied with origin 'review', its
    photograph's path made relative to out/. references: {recipe: reference name}; params: {recipe: recipe knobs}.
    (How views.json began; the fixes and the added views were then written into it.)"""
    with open(plan_path, encoding='utf-8') as f:
        plan = json.load(f)
    out = {}
    marker = '/tests/terrain/out/'
    for recipe, rec in plan.items():
        views = []
        for v in rec['views']:
            p = v.get('photo')
            if p:
                p = p.replace('\\', '/')
                p = p.split(marker, 1)[1] if marker in p else os.path.basename(p)
            w = dict(name=v['name'], cam=[round(float(c), 3) for c in v['cam']],
                     cam_z=[v['cam_z'][0], round(float(v['cam_z'][1]), 3)],
                     aim=[round(float(c), 3) for c in v['aim']], lens=float(v['lens']),
                     frame=[float(c) for c in v['frame']], focus=bool(v['focus']), photo=p,
                     caption=v.get('caption', ''), origin='review')
            w['kind'] = kind_of(w)
            views.append(w)
        out[recipe] = dict(reference=references.get(recipe), params=(params or {}).get(recipe), views=views)
    return out
