"""eidoblend.sets.unknown_force.bin: THE BIN, a reusable canyon of thrown-away paper with a giant trash can, the
Blender 5.2 EEVEE edition of eidoverse/sets/unknown_force/bin.js (made for the UNKNOWN FORCE music video; free to use
in any piece).

A canyon of thrown-away paper in the dark, Futurist papier colle: giant pages, crumpled boulders, cut coloured papers
and typographic fragments (THE FUTURE IS, THREAD 1/47, MANIFESTO, a black Carra wedge, a red disc). At its head, half
buried, a giant rusted trash can (Poly Haven "Metal Trash Can", CC0, from the shared model library), stickered and
tagged, filled with the discourse; a performer's mark walks up the paper inside it to the lip. Paper keeps drifting
down out of the dark.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend.sets.unknown_force import bin as B
    b = B.build(scene)                          # opts as bin.js: sky, lights, atlas_scale, sheets, balls, falling
    performer_root.parent = b.parts['mark']     # the mark (faces -Y: three's +Z) climbs out of the can
    for f in range(f0, f1 + 1):                 # per frame on your clock, KEYED
        t = (f - f0) / fps
        b.update(t, {'climb': B.ease_in(t, 1.0, 17.0), 'glow': 1, 'wind': 0.4, 'hush': 0}, frame=f)
        b.key_camera(cam_obj, 'binWide', frame=f, push=2.0, u=t / 20.0)
    b.finish(); b.apply_render_settings(scene)  # the keys made LINEAR; AgX, the set's fog

Set-local, Blender's axes (three (x, y, z) -> (x, -z, y)): the can's axis is the root's vertical, its rim 6.2 m up;
the canyon runs toward -Y (three's +Z, the cameras' side); a paper cliff closes it behind the can (+Y). Inside the can
the paper fill is a slope from the back (4.25 m) up to the brim at the front (6.2 m); the mark walks up it with climb.

Ported line for line: the heap's shape (heap_height), the page atlas (bin_pages), the stickers painted into the can's
material through cylindrical coordinates, the deterministic placement of every sheet, boulder, fragment and readable
page (bin.js's mulberry32 stream, call for call), the collage underlayer, the cut shapes, the falling paper (Geometry
Nodes evaluating bin.js's vertex shader on keyed time and wind, with its exact per-sheet hashes), the street lamp, the
lights and the sky. The sheets are realized meshes (bin.js instanced them; the per-sheet cell and shade ride as point
attributes).

What the JS module exports, and where it is here: heapHeight -> heap_height (a Blender ground point) and
heap_height_three (bin.js's own axes); build -> Bin: group, parts, cams, update(t, state, frame), focal_point(),
key_camera, animate, make_cameras, apply_render_settings, finish, dispose. BRIDGE (the song seconds the set was made
for) is left out: this edition is the set, not the video; its moving parts (the mark's climb, the light inside the
can, the falling paper, the hush) take their own state on any clock, and ease_in(t, t0, t1) ramps one between two
times. The pure half (no Blender): heap_height, placement, cams_three, draw_stickers, draw_cut_shapes, sheet_geo,
crumple_geo, pcg_hash.
"""
from __future__ import annotations

import math
import os
import tempfile

import numpy as np

try:
    import bpy
    from mathutils import Matrix, Vector
except ImportError:                                     # pragma: no cover
    bpy = None

from . import bin_pages as PAGES
from .race import (GB, NB, V, Geo, Keyer, box_geo, cd, compose, cylinder_geo, empty, icosahedron_geo, image_from_array,
                   lin_hex, make_collection, mesh_object, new_material, output, plane_geo, principled, quat_axis_angle,
                   quat_euler, quat_mul, quat_unit_vectors, sphere_geo, to_blender, unlit, light, _no_shadow, _vt,
                   _isnum, quat_to_blender, _dispose_set, ease_in)

D2R = math.pi / 180
H = 6.2                                 # the can's rim height (m): a giant bin, about 3.5 x her height
rng = PAGES.rng                          # mulberry32, as bin.js


def clamp01(x):
    return max(0.0, min(1.0, x))


def smooth(a, b, x):
    k = clamp01((x - a) / (b - a))
    return k * k * (3 - 2 * k)


def lerp(a, b, k):
    return a + (b - a) * k


def _i32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def _imul(a, b):
    return _i32((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF))


def hash2(x, y):
    """bin.js hash2: Math.imul hashing of the integer lattice (x | 0, y | 0)."""
    xi, yi = _i32(int(x)), _i32(int(y))
    h = _imul(xi, 374761393) ^ _imul(yi, 668265263)
    h = _imul(h ^ ((h & 0xFFFFFFFF) >> 13), 1274126177)
    return ((h ^ ((h & 0xFFFFFFFF) >> 16)) & 0xFFFFFFFF) / 4294967296.0


def vnoise(x, y):
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    a, b, c, d = hash2(xi, yi), hash2(xi + 1, yi), hash2(xi, yi + 1), hash2(xi + 1, yi + 1)
    return lerp(lerp(a, b, u), lerp(c, d, u), v)


def fbm(x, y):
    return vnoise(x, y) * 0.55 + vnoise(x * 2.1 + 17, y * 2.1 - 9) * 0.3 + vnoise(x * 4.3 - 5, y * 4.3 + 3) * 0.15


def heap_height_three(x, z, R=1.66):
    """bin.js heapHeight(x, z, R) in its own axes (three's ground (x, z)): the canyon floor, its paper walls, the
    cliff behind the can and the mound banked against it."""
    ax, side = abs(x), (0 if x < 0 else 1)
    half = 3.3 + max(0.0, z) * 0.11 + (fbm(z * 0.09, side * 7) - 0.5) * 1.6
    h = 0.12 + fbm(x * 0.35, z * 0.35) * 0.45
    wall_top = 7.5 + 6 * fbm(z * 0.05 + 3, side * 13) + (3 if z < -2 else 0)
    wall = wall_top * smooth(half, half + 5.5 + 2 * fbm(z * 0.13, side * 5 + 2), ax)
    h = max(h, wall + (fbm(x * 0.6, z * 0.6) - 0.5) * 0.9 * smooth(half, half + 2, ax))
    cliff = (13 + 4 * fbm(x * 0.07, 9)) * smooth(-3.0, -12, z)
    h = max(h, cliff + (fbm(x * 0.5, z * 0.5) - 0.5) * 1.2 * smooth(-3, -6, z))
    r = math.hypot(x, z)
    back = smooth(1.5, -2.5, z)
    mound = (1.15 + 2.6 * back + 0.5 * fbm(math.atan2(x, z) * 2, 3)) * (1 - smooth(R + 0.2, R + 6.5, r))
    return max(h, mound)


def heap_height(x, y, R=1.66):
    """The heap's height (Blender z) at the set-local ground point (x, y): bin.js heapHeight(x, -y, R)."""
    return heap_height_three(x, -y, R)


def pcg_hash(u):
    """three TSL's hash(): PCG on the seed's uint (WGSL's saturating float -> u32), -> [0, 1)."""
    u = np.asarray(u, np.float64)
    s = np.where(u > 0, np.floor(u), 0).astype(np.uint64) & 0xFFFFFFFF
    state = (s * 747796405 + 2891336453) & 0xFFFFFFFF
    word = (((state >> ((state >> 28) + 4)) ^ state) * 277803737) & 0xFFFFFFFF
    res = ((word >> 22) ^ word) & 0xFFFFFFFF
    return res.astype(np.float64) / 4294967296.0


def cams_three(R, y_fill):
    """bin.js's cams in its own numbers (three's set-local axes), which depend on the can's radius R."""
    return {
        'binWide': {'pos': [0.8, 2.3, 14.0], 'target': [0, 3.9, 0], 'fov': 42},
        'climb': {'pos': [1.7, H + 1.05, R + 3.6], 'target': [0, H + 0.45, R - 0.5], 'fov': 40},
        'paperClose': {'pos': [-2.3, 1.8, R + 6.2], 'target': [0.3, 0.8, R + 1.6], 'fov': 38},
        'topDown': {'pos': [0.9, H + 7.5, 3.2], 'target': [0, y_fill + 0.6, 0.2], 'fov': 44},
    }


STICK = [   # cell (4x2), theta (deg, 0 = three's +Z front), y (m), width (m of arc), height (m), finish
    {'c': 0, 'th': 28, 'y': 3.55, 'w': 1.25, 'h': 0.86, 'rough': 0.55},                 # NO DUMPING
    {'c': 1, 'th': -38, 'y': 4.45, 'w': 1.5, 'h': 0.5, 'rough': 0.5},                   # KEEP LID CLOSED
    {'c': 2, 'th': 2, 'y': 2.05, 'w': 3.6, 'h': 0.36, 'rough': 0.6},                    # hazard band
    {'c': 3, 'th': -12, 'y': 2.95, 'w': 1.9, 'h': 0.95, 'rough': 0.85, 'paint': True},  # stencil BIN 01
    {'c': 4, 'th': 62, 'y': 2.35, 'w': 1.7, 'h': 1.05, 'rough': 0.8, 'paint': True},    # spray tag
    {'c': 5, 'th': -74, 'y': 3.3, 'w': 1.45, 'h': 2.05, 'rough': 0.92},                 # wheat-pasted poster, peeling
    {'c': 6, 'th': 112, 'y': 3.9, 'w': 0.9, 'h': 0.9, 'rough': 0.5},                    # round sticker
    {'c': 7, 'th': -128, 'y': 2.6, 'w': 1.6, 'h': 0.7, 'rough': 0.6},                   # warning label
]


def draw_stickers():
    """bin.js drawStickers: a 4 x 2 atlas of 512 px cells (vinyl signs, a stencil, a spray tag, a wheat-pasted
    poster), all text invented. -> (1024, 2048, 4) floats, row 0 the canvas top."""
    C = 512
    g = PAGES.Canvas2D(2048, 1024, ss=2)
    g.clearRect(0, 0, 2048, 1024)
    r = rng(77)

    def cell(k, fn):
        g.save()
        g.translate((k % 4) * C, (k // 4) * C)
        g.beginPath()
        g.rect(0, 0, C, C)
        g.clip()
        fn()
        g.restore()

    def c0():
        g.fillStyle = '#f2efe8'
        g.fillRect(14, 70, C - 28, C - 140)
        g.fillStyle = '#c3242b'
        g.fillRect(14, 70, C - 28, 120)
        g.fillStyle = '#fff'
        g.font = '92px "UF Anton"'
        g.textAlign = 'center'
        g.fillText('NO DUMPING', C / 2, 165)
        g.fillStyle = '#16120f'
        g.font = '40px "UF Archivo Black"'
        g.fillText('OF ANY KIND', C / 2, 268)
        g.font = '28px "UF Space Mono"'
        g.fillText('violators will be heard', C / 2, 330)
        g.fillText('but not answered', C / 2, 366)
        g.strokeStyle = '#16120f'
        g.lineWidth = 6
        g.strokeRect(20, 76, C - 40, C - 152)

    def c1():
        g.fillStyle = '#ecc31f'
        g.fillRect(10, 170, C - 20, 172)
        g.fillStyle = '#121212'
        g.font = '82px "UF Bungee"'
        g.textAlign = 'center'
        g.fillText('KEEP LID', C / 2, 250)
        g.fillText('CLOSED', C / 2, 330)

    def c2():
        g.fillStyle = '#e8c21e'
        g.fillRect(0, 200, C, 112)
        g.fillStyle = '#121212'
        x = -120
        while x < C + 120:
            g.beginPath()
            g.moveTo(x, 312)
            g.lineTo(x + 32, 312)
            g.lineTo(x + 32 + 112, 200)
            g.lineTo(x + 112, 200)
            g.closePath()
            g.fill()
            x += 64

    def c3():
        g.fillStyle = 'rgba(240,236,224,0.25)'
        g.font = '190px "UF Black Ops"'
        g.textAlign = 'center'
        g.shadowColor = 'rgba(240,236,224,0.8)'
        g.shadowBlur = 14
        g.fillText('BIN 01', C / 2, 330)
        g.shadowBlur = 0
        g.fillStyle = '#eeeae0'
        g.fillText('BIN 01', C / 2, 330)

    def c4():
        g.strokeStyle = '#ff3fa4'
        g.lineCap = 'round'
        g.lineJoin = 'round'
        g.shadowColor = 'rgba(255,63,164,0.8)'
        g.shadowBlur = 10
        for s in range(3):
            g.lineWidth = 22 - s * 6
            g.beginPath()
            x, y = 40, 300
            g.moveTo(x, y)
            for _ in range(9):
                x += 48
                cy = y - 160 + r() * 80
                g.quadraticCurveTo(x - 30, cy, x, 260 + r() * 90)
            g.stroke()
        g.lineWidth = 16
        g.beginPath()
        g.moveTo(140, 400)
        g.lineTo(380, 400)
        g.moveTo(140, 450)
        g.lineTo(380, 450)
        g.moveTo(320, 360)
        g.lineTo(200, 490)
        g.stroke()
        g.shadowBlur = 0
        g.fillStyle = 'rgba(255,63,164,0.85)'
        for _ in range(6):
            x0, y0 = 70 + r() * 360, 310 + r() * 40
            g.fillRect(x0, y0, 5, 60 + r() * 120)

    def c5():
        g.fillStyle = '#e9e2cf'
        g.beginPath()
        g.moveTo(40, 10)
        for p in ((470, 22), (480, 380), (430, 420), (450, 500), (30, 500)):
            g.lineTo(*p)
        g.closePath()
        g.fill()
        g.fillStyle = '#16120f'
        g.font = '120px "UF Anton"'
        g.textAlign = 'center'
        g.fillText('THE', C / 2, 150)
        g.fillText('FUTURE', C / 2, 280)
        g.fillStyle = '#c42a2c'
        g.font = '50px "UF Alfa Slab"'
        g.fillText('IS NOT YET', C / 2, 360)
        g.fillStyle = 'rgba(0,0,0,0.18)'
        g.fillRect(30, 440, 450, 60)

    def c6():
        g.fillStyle = '#2a63c9'
        g.beginPath()
        g.arc(C / 2, C / 2, 230, 0, 6.283)
        g.fill()
        g.fillStyle = '#fff'
        g.font = '62px "UF Archivo Black"'
        g.textAlign = 'center'
        g.fillText('PROPERTY', C / 2, 230)
        g.font = '44px "UF Space Mono Bold"'
        g.fillText('OF THE', C / 2, 290)
        g.font = '70px "UF Archivo Black"'
        g.fillText('PUBLIC', C / 2, 360)

    def c7():
        g.fillStyle = '#f4f2ee'
        g.fillRect(10, 150, C - 20, 210)
        g.fillStyle = '#121212'
        g.beginPath()
        g.moveTo(90, 180)
        g.lineTo(160, 320)
        g.lineTo(20, 320)
        g.closePath()
        g.fill()
        g.fillStyle = '#f4f2ee'
        g.fillRect(84, 220, 12, 60)
        g.fillRect(84, 290, 12, 14)
        g.fillStyle = '#121212'
        g.font = '50px "UF Archivo Black"'
        g.textAlign = 'left'
        g.fillText('CONTENTS', 180, 240)
        g.font = '30px "UF Space Mono Bold"'
        g.fillText('MAY SPEAK', 180, 290)
        g.fillText('HANDLE WITH CARE', 180, 330)

    for k, fn in enumerate((c0, c1, c2, c3, c4, c5, c6, c7)):
        cell(k, fn)
    return g.to_float()


def draw_cut_shapes():
    """bin.js's two big cut shapes on one 2048 x 1024 canvas: the black Carra wedge lettered TUMB TUMB / everyone keeps
    asking (left half), the red disc ringed with EVERY FORUM - EVERY SERMON - EVERY MANIFESTO READ (right half)."""
    g = PAGES.Canvas2D(2048, 1024, ss=2)
    g.clearRect(0, 0, 2048, 1024)
    g.fillStyle = '#0d0d0f'
    g.beginPath()
    g.moveTo(20, 980)
    g.lineTo(1000, 40)
    g.lineTo(1010, 330)
    g.closePath()
    g.fill()
    g.save()
    g.translate(330, 760)
    g.rotate(-0.77)
    g.fillStyle = '#efe9da'
    g.font = '120px "UF Anton"'
    g.fillText('TUMB TUMB', 0, 0)
    g.font = '64px "UF Old Standard Italic"'
    g.fillText('everyone keeps asking', 30, 90)
    g.restore()
    g.save()
    g.translate(1536, 512)
    g.fillStyle = '#c42a2c'
    g.beginPath()
    g.arc(0, 0, 470, 0, 6.283)
    g.fill()
    g.fillStyle = '#16120f'
    g.font = '44px "UF Space Mono Bold"'
    ring = ' EVERY FORUM · EVERY SERMON · EVERY MANIFESTO READ ·'
    for i, ch in enumerate(ring):
        g.save()
        g.rotate(i / len(ring) * 6.283)
        g.fillText(ch, -12, -405)
        g.restore()
    g.restore()
    return g.to_float()


def sheet_geo(kind):
    """bin.js sheetGeo: a 1 x 1.5 page, flat with a slight wave (0), curled along its width (1), folded (2)."""
    g = plane_geo(1, 1.5, 6, 9)
    x, y = g.P[:, 0], g.P[:, 1]
    if kind == 0:
        g.P[:, 2] = 0.025 * np.sin(x * 4.0 + y * 2.0)
    elif kind == 1:
        g.P[:, 2] = 0.32 * x * x * 1.6 + 0.04 * np.sin(y * 5)
    else:
        g.P[:, 2] = 0.42 * np.abs(x) - 0.12
    return g.compute_normals()


def crumple_geo():
    """bin.js's crumpled paper: a detail-3 icosahedron, faceted by value noise, squashed, with the page on it."""
    g = icosahedron_geo(1, 3)
    Vn = g.P / np.linalg.norm(g.P, axis=1, keepdims=True)
    P, UV = np.zeros_like(Vn), np.zeros((len(Vn), 2))
    for i, (vx, vy, vz) in enumerate(Vn):
        k = 0.72 + 0.5 * vnoise(vx * 3 + 9, vy * 3 + vz * 2.3) + 0.18 * vnoise(vz * 7 - 3, vx * 7 + vy * 5)
        P[i] = (vx * k, vy * k * 0.85, vz * k)
        UV[i] = (0.5 + math.atan2(vx, vz) / (2 * math.pi), 0.5 + math.asin(max(-1.0, min(1.0, vy))) / math.pi)
    return Geo(P, np.zeros_like(P), UV, g.I).compute_normals()


def _q_from_m3(m):
    """A rotation matrix (3x3) -> three (x, y, z, w) quaternion."""
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = 0.5 / math.sqrt(t + 1.0)
        return ((m[2, 1] - m[1, 2]) * s, (m[0, 2] - m[2, 0]) * s, (m[1, 0] - m[0, 1]) * s, 0.25 / s)
    if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        return (0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s)
    if m[1, 1] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        return ((m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s)
    s = 2.0 * math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
    return ((m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s)


def placement(R, cams, n_sheets=3300, n_balls=300, n_falling=200, cut0=18, ncell=24):
    """bin.js's placement, call for call on its mulberry32 stream rng(2228): {'sheets': [[(matrix 4x4 three, cell,
    shade)] x 3 kinds], 'inner': [...], 'balls': [...], 'falling': [(cell, shade)]}. Pure Python."""
    r = rng(2228)
    y_fill = H - 1.95
    Z_IN, Z_OUT = -0.45, R - 0.42

    def fill_y(x, z):
        return y_fill + (H + 0.06 - y_fill) * smooth(Z_IN, Z_OUT, z) ** 1.25 + 0.05 * math.sin(x * 3.1 + z * 2.3)

    hh = lambda x, z: heap_height_three(x, z, R)

    def normal_at(x, z):
        e = 0.35
        hx = (hh(x + e, z) - hh(x - e, z)) / (2 * e)
        hz = (hh(x, z + e) - hh(x, z - e)) / (2 * e)
        n = np.array([-hx, 1.0, -hz])
        return n / np.linalg.norm(n)

    def blocked(x, z):
        for c in cams.values():
            if math.hypot(x - c['pos'][0], z - c['pos'][2]) < (3.2 if c['pos'][1] < 3 else 1.2):
                return True
        return False

    corridor = lambda x, z: R + 1.0 < z < 24 and abs(x) < 2.2 + z * 0.06

    def pick_cell():
        return cut0 + math.floor(r() * (ncell - cut0)) if r() < 0.16 else math.floor(r() * cut0)

    def sample_spot(near=0.0):
        for _ in range(200):
            x = (r() - 0.5) * 2 * near if near else -24 + r() * 48
            z = (r() - 0.5) * 2 * near if near else -20 + r() * 64
            if math.hypot(x, z) < R + 0.15:
                continue
            if blocked(x, z):
                continue
            n = normal_at(x, z)
            area = 1 / max(0.25, n[1])
            focus = 0.55 + 1.6 * math.exp(-math.hypot(x, z * 0.7) / 9) + (0.6 if (abs(x) < 14 and -14 < z < 36) else 0)
            if r() * 4.5 < area * focus:
                return (x, z, n)
        return (0.0, 8.0, np.array([0.0, 1.0, 0.0]))

    def place(lst, sp, size, lift, cell=None):
        x, z, n = sp
        q = quat_unit_vectors((0, 0, 1), n)
        q = quat_mul(quat_axis_angle(n, r() * math.pi * 2), q)
        standing = r() < 0.09 and not corridor(x, z)
        ta = np.array([r() - 0.5, 0.0, r() - 0.5])
        ta = ta / np.linalg.norm(ta)
        in_corr = corridor(x, z)
        if in_corr:
            size = min(size, 1.3)
        ang = (70 + r() * 20) if standing else (r() - 0.5) * (80 if n[1] < 0.8 else 55) * (0.35 if in_corr else 1)
        q = quat_mul(quat_axis_angle(ta, ang * D2R), q)
        pos = np.array([x, hh(x, z) + lift, z]) + n * (0.04 + r() * 0.1 + (size * 0.6 if standing else 0))
        m = compose(pos, q, (size, size, size))
        c = cell if cell is not None else pick_cell()
        lst.append((m, c, (0.62 + r() * 0.3) * lerp(0.55, 1.0, max(0.0, n[1]))))

    sheets = [[], [], []]
    for _ in range(n_sheets):
        sp = sample_spot()
        size = math.exp(lerp(math.log(0.6), math.log(2.6), r() ** 1.6))
        place(sheets[[0, 0, 0, 1, 1, 2][math.floor(r() * 6)]], sp, size, 0)
    for i in range(520):
        sp = sample_spot(7.5)
        place(sheets[i % 3], sp, math.exp(lerp(math.log(0.35), math.log(1.4), r())), 0)
    inner = []
    for _ in range(110):
        a = r() * math.pi * 2
        rr = math.sqrt(r()) * (R - 0.35)
        x, z = math.sin(a) * rr, math.cos(a) * rr
        at_wall = rr > R - 0.9
        on_path = abs(x) < 0.55 and z > Z_IN - 0.3
        if at_wall and not on_path and z < -0.2:
            ex = -70
        else:
            ex = -90 + (r() - 0.5) * (16 if (on_path or z > -0.2) else 50)
        ey = a + math.pi + (r() - 0.5)
        ez = (r() - 0.5) * 0.6
        q = quat_euler(ex * D2R, ey, ez, 'YXZ')
        front = z > -0.2
        size = (0.4 + r() * 0.5) if on_path else ((0.35 + r() * 0.45) if front else (0.5 + r() * 1.1))
        back = math.cos(a) < -0.2 and at_wall and r() < 0.5
        y = fill_y(x, z) + 0.04 + r() * (0.03 if (on_path or front) else 0.2) + (
            0 if (on_path or front) else (size * 0.55 if back else (size * 0.3 if at_wall else 0)))
        m = compose((x, y, z), q, (size, size, size))
        inner.append((m, pick_cell(), 0.6 + r() * 0.3))
    # the giant typographic fragments, turned to the wide camera; the readable pages at her feet
    kinds = PAGES.PAGE_KINDS
    big = [
        (kinds.index('poster'), (-5.2, 8.6, -8.2), (-0.08, 0.15, -0.09), 6.6),
        (3, (7.4, 6.0, 4.5), (-0.18, -0.25, 0.12), 3.6),
        (kinds.index('manifesto'), (-7.0, 5.2, 2.0), (-0.25, 0.3, 0.22), 4.2),
        (kinds.index('letter'), (6.2, 9.8, -6.0), (0.05, -0.2, -0.12), 4.6),
        (0, (-9.6, 8.2, 9.5), (-0.35, 0.35, 0.15), 4.0),
        (cut0 + 1, (3.9, 3.2, -3.4), (-0.1, -0.2, 0.5), 2.8),
        (cut0, (-3.8, 3.6, -3.0), (0.05, 0.25, -0.42), 2.6),
        (kinds.index('futurist'), (9.4, 4.4, 15.5), (-0.6, -0.4, 0.1), 3.6),
    ]
    wide = cams['binWide']['pos']
    for cell, pos, rot, size in big:
        yaw = math.atan2(wide[0] - pos[0], wide[2] - pos[2])
        q = quat_euler(rot[0], yaw + rot[1], rot[2], 'YXZ')
        sheets[0].append((compose(pos, q, (size, size, size)), cell, 0.95))
    cam_p = np.array(cams['paperClose']['pos'], float)
    read = [(-0.75, R + 1.35, 0, 1.7), (1.0, R + 0.95, 3, 1.5), (0.2, R + 2.6, kinds.index('manifesto'), 1.65),
            (1.75, R + 2.4, 6, 1.4), (-1.7, R + 2.9, kinds.index('letter'), 1.4)]
    for x, z, cell, size in read:
        n = normal_at(x, z)
        d = np.array([x - cam_p[0], 0.0, z - cam_p[2]])
        top = d - n * float(np.dot(d, n))
        top /= np.linalg.norm(top)
        right = np.cross(top, n)
        right /= np.linalg.norm(right)
        m = np.eye(4)
        m[:3, 0], m[:3, 1], m[:3, 2] = right * size, top * size, n * size
        m[:3, 3] = (x, hh(x, z) + 0.06, z)
        sheets[0].append((m, cell, 1.0))
    balls = []
    for i in range(n_balls):
        sp = sample_spot(9) if i < 50 else sample_spot()
        if corridor(sp[0], sp[1]) or math.hypot(sp[0], sp[1] - R) < 3.2:
            continue
        size = math.exp(lerp(math.log(0.35), math.log(1.0 if i < 50 else 1.8), r() ** 1.3))
        q = quat_euler(r() * 6.28, r() * 6.28, r() * 6.28)
        sy = size * (0.8 + r() * 0.3)
        m = compose((sp[0], hh(sp[0], sp[1]) + size * 0.55, sp[1]), q, (size, sy, size))
        balls.append((m, math.floor(r() * cut0), (0.6 + r() * 0.3) * lerp(0.6, 1.0, max(0.0, sp[2][1]))))
    for _ in range(26):
        a = r() * 6.28
        rr = math.sqrt(r()) * (R - 0.6)
        size = 0.35 + r() * 0.5
        q = quat_euler(r() * 6.28, r() * 6.28, r() * 6.28)
        bx, bz = math.sin(a) * rr, math.cos(a) * rr
        if abs(bx) < 0.7 and bz > Z_IN - 0.4:
            continue
        m = compose((bx, fill_y(bx, bz) + size * 0.45, bz), q, (size, size, size))
        balls.append((m, math.floor(r() * cut0), 0.7 + r() * 0.25))
    falling = []
    for _ in range(n_falling):
        c = pick_cell()
        falling.append((c, 0.8 + r() * 0.25))
    return {'sheets': sheets, 'inner': inner, 'balls': balls, 'falling': falling}


def _instances(geo, items):
    """Realize instances: the geometry transformed by each item's matrix, with per-vertex 'cell' and 'shade'."""
    n = len(geo.P)
    Ps, Ns, UVs, Is, cells, shades = [], [], [], [], [], []
    for k, (m, cell, shade) in enumerate(items):
        Ps.append(geo.P @ m[:3, :3].T + m[:3, 3])
        nm = np.linalg.inv(m[:3, :3]).T
        N = geo.N @ nm.T
        Ns.append(N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12))
        UVs.append(geo.UV)
        Is.append(geo.I + k * n)
        cells.append(np.full(n, float(cell)))
        shades.append(np.full(n, float(shade)))
    g = Geo(np.concatenate(Ps), np.concatenate(Ns), np.concatenate(UVs), np.concatenate(Is))
    return g, np.concatenate(cells), np.concatenate(shades)


class Bin:
    """The built set (what bin.js's build returns): group (the root Empty), parts, cams, update, focal_point,
    key_camera, finish, dispose. Build it with build()."""

    def __init__(self, scene=None, sky=True, lights=True, atlas_scale=1.0, sheets=3300, balls=300, falling=200,
                 name='bin', keyer=None, collection=None, cache_dir=None):
        self.scene = scene or bpy.context.scene
        self.opts = dict(sky=sky, lights=lights, atlas_scale=atlas_scale, sheets=sheets, balls=balls, falling=falling)
        self.key = keyer if isinstance(keyer, Keyer) else Keyer(keyer)
        self.col = collection or make_collection(f'set:{name}', self.scene.collection)
        self.group = empty(f'set:{name}', collection=self.col)
        self.group.empty_display_size = 2.0
        self.objects, self.mats, self.parts, self.gn_inputs = [], {}, {}, []
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), 'eidoblend_cache', 'bin_pages')
        self.U = {'time': 0.0, 'wind': 0.35, 'glow': 1.0, 'hush': 0.0}
        self._can()
        self.cams3 = cams_three(self.R, self.y_fill)
        self.cams = {k: {'pos': to_blender(c['pos']), 'target': to_blender(c['target']), 'fov': c['fov']} for k, c in self.cams3.items()}
        self._paper()
        self._mark_and_focal()
        self._lamp()
        if lights:
            self._lights()
        if sky:
            self._world()
        self.parts.update({'mark': self.mark, 'focal': self.focal, 'R': self.R, 'H': H, 'y_fill': self.y_fill,
                           'fill_y': self.fill_y, 'fog': {'color': 0x070a14, 'density': 0.03},
                           'uniforms': self.U, 'page_atlas': self.atlas_img,
                           'page_grid': {'cols': 6, 'rows': 4, 'kinds': PAGES.PAGE_KINDS[:24]}})
        self.update(0.0, {}, frame=None)

    # ------------------------------------------------------------------------------------------- helpers
    def obj(self, name, g, mat, parent=None, **kw):
        ob = mesh_object(name, g, mat, parent=parent or self.group, collection=self.col, **kw)
        if ob is not None:
            self.objects.append(ob)
        return ob

    def fill_y(self, x, y):
        """The paper fill's height inside the can (Blender z) at the set-local ground point (x, y)."""
        return self._fill_y3(x, -y)

    def _fill_y3(self, x, z):
        return self.y_fill + (H + 0.06 - self.y_fill) * smooth(self.Z_IN, self.Z_OUT, z) ** 1.25 + 0.05 * math.sin(x * 3.1 + z * 2.3)

    # ------------------------------------------------------------------------------------------- the can
    def _can(self):
        """Poly Haven's Metal Trash Can (CC0), the rusted one scaled to a 6.2 m giant, its stickers painted INTO its
        material through cylindrical coordinates; the lid leaning against it; the clean can toppled in the cliff."""
        from ...harness import assets
        path = assets.fetch_model_file('metal_trash_can', res='2k')
        kinds = ('objects', 'meshes', 'materials', 'images', 'node_groups')
        before = {k: set(getattr(bpy.data, k)) for k in kinds}
        bpy.ops.import_scene.gltf(filepath=path)
        made = {k: [d for d in getattr(bpy.data, k) if d not in before[k]] for k in kinds}
        imported = made['objects']
        by = {o.name.split('.')[0]: o for o in imported if o.type == 'MESH'}

        def baked(name):
            ob = by[name]
            me = ob.data.copy()
            me.transform(ob.matrix_world)
            return me, ob

        body_me, body_src = baked('metal_trash_can_rust')
        co = np.array([v.co[:] for v in body_me.vertices])
        lo, hi = co.min(0), co.max(0)
        s = H / (hi[2] - lo[2])
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        to_set = Matrix.Diagonal((s, s, s, 1.0)) @ Matrix.Translation((-cx, -cy, -lo[2]))
        self.R = R = ((hi[1] - lo[1]) / 2) * s
        self.s = s
        self.y_fill = H - 1.95
        self.Z_IN, self.Z_OUT = -0.45, R - 0.42
        stick = image_from_array('bin:stickers', draw_stickers(), 'sRGB', top_first=False)
        self.sticker_img = stick
        bin_g = empty('bin', parent=self.group, collection=self.col)
        body_me.transform(to_set)
        body_me.name = 'bin:can'
        can = bpy.data.objects.new('bin:can', body_me)
        self.col.objects.link(can)
        can.parent = bin_g
        can.data.materials.clear()
        can.data.materials.append(self._can_material(body_src.active_material, R))
        self.objects.append(can)
        handles = []
        for nm in ('metal_trash_can_rust_handle_left', 'metal_trash_can_rust_handle_right'):
            me, src = baked(nm)
            me.transform(to_set)
            ob = bpy.data.objects.new('bin:' + nm.split('_')[-1] + '_handle', me)
            self.col.objects.link(ob)
            ob.parent = bin_g
            handles.append(ob)
            self.objects.append(ob)
        # the lid: off, leaning back against the can's front left, its lower rim sunk in the paper (Balla's disc)
        lid_src = by['metal_trash_can_rust_lid']
        lme = lid_src.data.copy()
        lco = np.array([v.co[:] for v in lme.vertices])
        llo, lhi = lco.min(0), lco.max(0)
        lme.transform(Matrix.Diagonal((s, s, s, 1.0)) @ Matrix.Translation(-Vector((llo + lhi) / 2)))
        lid = bpy.data.objects.new('bin:lid', lme)
        self.col.objects.link(lid)
        lid.parent = bin_g
        rl = ((lhi[0] - llo[0]) / 2) * s
        la, lean = -40 * D2R, 21 * D2R
        out = np.array([math.sin(la), 0.0, math.cos(la)])
        nrm = out * math.cos(lean) + np.array([0, math.sin(lean), 0])
        nrm /= np.linalg.norm(nrm)
        q = quat_unit_vectors((0, 1, 0), nrm)
        q = quat_mul(quat_axis_angle(nrm, 0.6), q)
        lid.rotation_mode = 'QUATERNION'
        lid.rotation_quaternion = quat_to_blender(q)
        lid.location = to_blender(out * (R + rl * math.sin(lean) + 0.18) + np.array([0, rl * math.cos(lean) + 0.25, 0]))
        self.objects.append(lid)
        # the clean can, toppled in the cliff
        c2me, _ = baked('metal_trash_can')
        cco = np.array([v.co[:] for v in c2me.vertices])
        clo, chi = cco.min(0), cco.max(0)
        s2 = 3.6 / (chi[2] - clo[2])
        c2me.transform(Matrix.Diagonal((s2, s2, s2, 1.0)) @ Matrix.Translation((-(clo[0] + chi[0]) / 2, -(clo[1] + chi[1]) / 2, -clo[2])))
        top = bpy.data.objects.new('bin:toppled', c2me)
        self.col.objects.link(top)
        top.parent = self.group
        top.rotation_mode = 'QUATERNION'
        top.rotation_quaternion = quat_to_blender(quat_euler(0, -0.55, math.pi / 2 - 0.12))
        top.location = to_blender((7.8, heap_height_three(7.8, -6.5, R) - 0.9, -6.5))
        self.objects.append(top)
        # the import's own objects and meshes are spent (the set keeps baked copies); its materials and maps stay in
        # use by those copies and become the set's own, named bin:..., so dispose() takes them with the set
        for o in imported:
            bpy.data.objects.remove(o, do_unlink=True)
        for me in made['meshes']:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        for ob in handles + [lid, top]:
            ob.data.name = ob.name
        for kind in ('materials', 'node_groups', 'images'):        # materials first: they hold the maps
            coll = getattr(bpy.data, kind)
            for d in made[kind]:
                if d.users == 0:                                     # e.g. the body's own, replaced by its painted copy
                    coll.remove(d)
                    continue
                d.name = 'bin:' + d.name
                if kind == 'materials':
                    self.mats[d.name] = d
        self.parts.update({'bin': bin_g, 'can': can, 'lid': lid, 'toppled': top, 'handles': handles})

    def _can_material(self, src, R):
        """bin.js canMat(painted): the can's own maps, with the eight stickers mixed in through cylindrical
        coordinates; paper peels where the rust noise is high, paint rubs off; each has its own roughness and no
        metalness. Built from the imported glTF material's images."""
        m = src.copy()
        m.name = 'bin:can_painted'
        nt = m.node_tree
        nb = NB(nt)
        bsdf = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
        nb._cache['bsdf'] = bsdf

        def incoming(sock_name):
            s = bsdf.inputs[sock_name]
            if s.is_linked:
                lk = s.links[0]
                return V(nb, lk.from_socket, lk.from_socket.type in ('RGBA', 'VECTOR'))
            dv = s.default_value
            return dv if _isnum(dv) else tuple(dv)[:3]

        base = incoming('Base Color')
        rough = incoming('Roughness')
        metal = incoming('Metallic')
        base_r = nb.sep(base)[0] if isinstance(base, V) else base[0]
        col = base
        p = nb.local3()
        nl = nb.three(V(nb, _vt(nb, nb.geom('Normal'), 'WORLD', 'OBJECT'), True))
        th = nb.atan2(p.x, p.z)
        outward = nb.smoothstep(0.0, 0.25, nb.dot(nb.normalize(nb.vec2(p.x, p.z)), nb.normalize(nb.vec2(nl.x, nl.z))))
        nz = nb.node('ShaderNodeTexNoise', noise_dimensions='3D', normalize=True)
        nz.inputs['Scale'].default_value = 1.0
        nz.inputs['Detail'].default_value = 0.0
        nz.inputs['Distortion'].default_value = 0.0
        nb.put(p * 3.1, nz.inputs['Vector'])
        wear = V(nb, nz.outputs['Fac'], False)
        for st in STICK:
            du = (th - st['th'] * D2R) * R / st['w'] + 0.5
            dv = (p.y - st['y']) / st['h'] + 0.5
            inside = nb.step(0.0, du) * nb.step(du, 1.0) * nb.step(0.0, dv) * nb.step(dv, 1.0)
            cuv = nb.vec2((du + (st['c'] % 4)) / 4.0, (1.0 - dv + (st['c'] // 4)) / 2.0)
            sk, sa = nb.tex(self.sticker_img, cuv, ext='CLIP')
            paint = st.get('paint', False)
            a = sa * inside * outward * nb.smoothstep(0.86 if paint else 0.93, 0.55 if paint else 0.7, wear)
            col = nb.mix(col, sk if paint else sk * nb.mix(0.75, 1.0, base_r), a)
            rough = nb.mix(rough, st['rough'], a)
            metal = nb.mix(metal, 0.0, a)
        for sock, v in (('Base Color', col), ('Roughness', rough), ('Metallic', metal)):
            nb.put(v, bsdf.inputs[sock])
        self.mats['can'] = m
        return m

    # ------------------------------------------------------------------------------------------- the paper
    def sheet_mat(self, name):
        """bin.js sheetMat: the page on the front, its print ghosting through blank stock on the back, alpha-cut torn
        edges at 0.5; the per-sheet cell and shade from point attributes."""
        m = new_material(name)
        nb = NB(m.node_tree)
        cell = nb.attr('cell')
        shade = nb.attr('shade')
        col_i, row = nb.mod(cell, 6.0), nb.floor(cell / 6.0)
        u = nb.uv()
        front = 1.0 - nb.geom('Backfacing')
        fu = nb.mix(1.0 - u.x, u.x, front)
        pg, pa = nb.tex(self.atlas_img, nb.vec2((col_i + fu) / 6.0, (row + (1.0 - u.y)) / 4.0), ext='CLIP')
        stock, _ = nb.tex(self.atlas_img, nb.vec2((col_i + 0.03) / 6.0, (row + 0.03) / 4.0), ext='CLIP')
        back = nb.mix(stock, pg, 0.18)
        c = nb.mix(back, pg, front) * shade * 0.85
        output(nb, principled(nb, c, nb.hash(cell * 13.1) * 0.12 + 0.82, 0.0, alpha=nb.step(0.5, pa)))
        m.use_transparent_shadow = True
        return m

    def _paper(self):
        AS = self.opts['atlas_scale']
        cw, ch = _jr(682 * AS), _jr(1024 * AS)
        atlas = PAGES.draw_page_atlas(cols=6, rows=4, cw=cw, ch=ch, cache_dir=self.cache_dir)
        self.atlas_img = image_from_array('bin:page_atlas', np.asarray(atlas, np.uint8), 'sRGB', top_first=False)
        cut0 = PAGES.PAGE_KINDS.index('cut')
        self.pl = pl = placement(self.R, self.cams3, self.opts['sheets'], self.opts['balls'], self.opts['falling'], cut0, 24)
        sm = self.sheet_mat('bin:sheets')
        self.mats['sheets'] = sm
        paper = empty('bin:paper', parent=self.group, collection=self.col)
        out = {}
        for k, nm, items in ((0, 'paper:flat', pl['sheets'][0]), (1, 'paper:curled', pl['sheets'][1]),
                             (2, 'paper:folded', pl['sheets'][2]), (1, 'paper:inside', pl['inner'])):
            g, cells, shades = _instances(sheet_geo(k), items)
            out[nm] = self.obj(nm, g, sm, parent=paper, attrs={'cell': ('FLOAT', 'POINT', cells), 'shade': ('FLOAT', 'POINT', shades)})
        # crumpled paper: faceted boulders with the page printed on them
        m = new_material('bin:crumpled')
        nb = NB(m.node_tree)
        cell, u = nb.attr('cell'), nb.uv()
        auv = nb.vec2((nb.mod(cell, 6.0) + u.x * 0.92 + 0.04) / 6.0, (nb.floor(cell / 6.0) + (1.0 - u.y) * 0.92 + 0.04) / 4.0)
        tc, _ = nb.tex(self.atlas_img, auv, ext='CLIP')
        output(nb, principled(nb, tc * nb.attr('shade'), 0.9, 0.0))
        self.mats['crumpled'] = m
        g, cells, shades = _instances(crumple_geo(), pl['balls'])
        out['paper:crumpled'] = self.obj('paper:crumpled', g, m, parent=paper, flat=True,
                                         attrs={'cell': ('FLOAT', 'POINT', cells), 'shade': ('FLOAT', 'POINT', shades)})
        # the heap under the sheets: a dark collage underlayer (rotated page tiles), and the fill inside the can
        m = new_material('bin:collage')
        nb = NB(m.node_tree)
        pw = nb.local3()
        xz = nb.vec2(pw.x, pw.z) / 1.7
        tile = nb.floor(xz)
        hc = nb.hash(tile.x * 31.7 + tile.y * 57.3)
        ang = hc * 6.283
        lp = nb.fract(xz) - (0.5, 0.5, 0.0)
        ca, sa = nb.cos(ang), nb.sin(ang)
        rpx, rpy = lp.x * ca - lp.y * sa + 0.5, lp.x * sa + lp.y * ca + 0.5
        cl = nb.floor(hc * cut0)
        auv = nb.vec2((nb.mod(cl, 6.0) + nb.clamp(rpx, 0.02, 0.98)) / 6.0, (nb.floor(cl / 6.0) + nb.clamp(rpy, 0.02, 0.98)) / 4.0)
        tc, _ = nb.tex(self.atlas_img, auv, ext='CLIP')
        output(nb, principled(nb, tc * 0.42 * (nb.hash(tile.y * 13.3 + tile.x) * 0.4 + 0.6), 0.92, 0.0))
        self.mats['collage'] = m
        hg = plane_geo(56, 72, 140, 180).transformed(compose((0, 0, 11), quat_euler(-math.pi / 2, 0, 0), (1, 1, 1)))
        hg.P[:, 1] = [heap_height_three(x, z, self.R) - 0.08 for x, z in zip(hg.P[:, 0], hg.P[:, 2])]
        hg.compute_normals()
        out['heap'] = self.obj('bin:heap', hg, m, parent=paper)
        R = self.R
        fg = plane_geo(2 * R, 2 * R, 28, 28).transformed(compose((0, 0, 0), quat_euler(-math.pi / 2, 0, 0), (1, 1, 1)))
        for i, (x, _y, z) in enumerate(fg.P):
            rr, lim = math.hypot(x, z), R - 0.09
            if rr > lim:
                x, z = x * lim / rr, z * lim / rr
            fg.P[i] = (x, self._fill_y3(x, z), z)
        fg.compute_normals()
        out['fill'] = self.obj('bin:fill', fg, m, parent=paper)
        # the big cut shapes of the collage: the black Carra wedge and the red disc of words
        cut_img = image_from_array('bin:cut_shapes', draw_cut_shapes(), 'sRGB', top_first=False)
        m = new_material('bin:cut_shapes')
        nb = NB(m.node_tree)
        u = nb.uv()
        tc, ta = nb.tex(cut_img, nb.vec2(u.x, 1.0 - u.y), ext='CLIP')
        output(nb, principled(nb, tc, 0.75, 0.0, alpha=nb.step(0.5, ta)))
        m.use_transparent_shadow = True
        self.mats['cut_shapes'] = m
        for u0, w, h, pos, rot, nm in ((0.0, 13, 13, (6.2, 6.6, -10.5), (0.05, -0.35, 0.18), 'bin:wedge'),
                                       (0.5, 4.2, 4.2, (-5.6, 2.6, -1.4), (-0.25, 0.95, -0.12), 'bin:disc')):
            g = plane_geo(w, h)
            g.UV[:, 0] = u0 + g.UV[:, 0] * 0.5
            g = g.transformed(compose(pos, quat_euler(rot[0], rot[1], rot[2], 'YXZ'), (1, 1, 1)))
            out[nm] = self.obj(nm, g, m, parent=paper)
        self._falling(paper)
        out['falling'] = self.falling
        self.parts['paper'] = paper
        self.parts['paper_meshes'] = out

    def _falling(self, parent):
        """Paper drifting down out of the dark: bin.js's vertex shader in Geometry Nodes (keyed time and wind),
        with its exact per-sheet hashes; deterministic in t, kept off the wide lens and out of the lip shot."""
        geo = sheet_geo(1)
        n = len(self.pl['falling'])
        nv = len(geo.P)
        ids = np.arange(n, dtype=np.float64)
        h = np.stack([pcg_hash(ids * 1.37 + 0.11), pcg_hash(ids * 2.71 + 0.37), pcg_hash(ids * 3.33 + 0.59),
                      pcg_hash(ids * 4.91 + 0.73), pcg_hash(ids * 6.17 + 0.19)], 1)
        self.falling_hash = h
        P = np.tile(geo.P, (n, 1))
        g = Geo(np.zeros_like(P), np.tile(geo.N, (n, 1)), np.tile(geo.UV, (n, 1)),
                np.concatenate([geo.I + k * nv for k in range(n)]))
        rep = lambda a: np.repeat(np.asarray(a, float), nv, axis=0)
        attrs = {'rest': ('FLOAT_VECTOR', 'POINT', P), 'h123': ('FLOAT_VECTOR', 'POINT', rep(h[:, :3])),
                 'h45': ('FLOAT_VECTOR', 'POINT', rep(np.stack([h[:, 3], h[:, 4], np.zeros(n)], 1))),
                 'cell': ('FLOAT', 'POINT', rep([c for c, _ in self.pl['falling']])),
                 'shade': ('FLOAT', 'POINT', rep([s for _, s in self.pl['falling']]))}
        ob = self.obj('bin:falling', g, self.mats['sheets'], parent=parent, attrs=attrs, flat=True)
        ob.data.shade_smooth()           # smooth normals from the tumbling geometry (bin.js rotated normalGeometry)
        tree = bpy.data.node_groups.new('bin:falling_gn', 'GeometryNodeTree')
        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        for nm, dv in (('time', 0.0), ('wind', 0.35)):
            tree.interface.new_socket(nm, in_out='INPUT', socket_type='NodeSocketFloat').default_value = dv
        nb = NB(tree)
        gin, gout = nb.node('NodeGroupInput'), nb.node('NodeGroupOutput')

        def named(nm):
            a = nb.node('GeometryNodeInputNamedAttribute', data_type='FLOAT_VECTOR')
            a.inputs['Name'].default_value = nm
            return V(nb, a.outputs['Attribute'], True)
        rest, ha, hb = named('rest'), named('h123'), named('h45')
        h1, h2, h3 = ha.x, ha.y, ha.z
        h4, h5 = hb.x, hb.y
        t = V(nb, gin.outputs['time'], False)
        wind = V(nb, gin.outputs['wind'], False)
        period = h1 * 7.0 + 9.0
        ph = nb.fract(t / period + h2)
        xa, z0 = (h3 - 0.5) * 24.0, h4 * 15.0 - 8.0
        in_lip = nb.step(nb.abs(xa), 2.6) * nb.step(-1.0, z0) * nb.step(z0, 7.0)
        x0 = xa + nb.mix(-3.0, 3.0, nb.math('GREATER_THAN', xa, 0.0)) * in_lip
        size = h5 * h5 * 0.7 + 0.28
        sway = wind * 1.6 + 0.5
        cx2 = x0 + nb.sin(t * (h1 * 0.5 + 0.45) + h2 * 6.28) * sway + wind * ph * 3.0
        cz2 = z0 + nb.cos(t * (h3 * 0.4 + 0.35) + h4 * 6.28) * sway * 0.7
        cy2 = nb.mix(23.0, 0.4, ph)
        ax = t * (h2 * 2.2 + 0.6) + h5 * 6.28
        az = t * (h4 * 1.6 + 0.4) + h1 * 6.28
        fade = nb.smoothstep(0.0, 0.05, ph) * (1.0 - nb.smoothstep(0.93, 1.0, ph))
        v = rest * (size * fade)
        cax, sax, caz, saz = nb.cos(ax), nb.sin(ax), nb.cos(az), nb.sin(az)
        y1 = v.y * cax - v.z * sax
        z1 = v.y * sax + v.z * cax
        x2 = v.x * caz - y1 * saz
        y2 = v.x * saz + y1 * caz
        px, py, pz = x2 + cx2, y2 + cy2, z1 + cz2
        sp = nb.node('GeometryNodeSetPosition')
        nb.links.new(gin.outputs['Geometry'], sp.inputs['Geometry'])
        nb.links.new(nb.vec3(px, -pz, py).out, sp.inputs['Position'])
        nb.links.new(sp.outputs['Geometry'], gout.inputs['Geometry'])
        mod = ob.modifiers.new('bin:falling', 'NODES')
        mod.node_group = tree
        for item in tree.interface.items_tree:
            if item.in_out == 'INPUT' and item.socket_type != 'NodeSocketGeometry':
                self.gn_inputs.append((ob, mod.name, item.identifier, item.name))
        self.falling = ob

    # ------------------------------------------------------------------------------------------- mark, lights, sky
    def _mark_and_focal(self):
        self.mark = empty('bin:mark', parent=self.group, collection=self.col)
        self.focal = empty('bin:focal', parent=self.group, collection=self.col, pos=(0, H + 0.9, self.R - 0.2))

    def _lamp(self):
        """Balla's Street Light (1909): a leaning pole sunk in the paper, its sodium head over the canyon."""
        m = new_material('bin:lamp_steel')
        nb = NB(m.node_tree)
        nz = nb.node('ShaderNodeTexNoise', noise_dimensions='3D', normalize=True)
        nz.inputs['Scale'].default_value = 1.0
        nz.inputs['Detail'].default_value = 0.0
        nz.inputs['Distortion'].default_value = 0.0
        nb.put(nb.local3() * 2.5, nz.inputs['Vector'])
        output(nb, principled(nb, nb.mix((0.05, 0.055, 0.06), (0.16, 0.08, 0.04), V(nb, nz.outputs['Fac'], False)), 0.55, 0.85))
        steel = m
        bulb = unlit('bin:lamp_bulb', lambda nb: nb.v((1.0 * 6.0, 0.55 * 6.0, 0.22 * 6.0)))
        lamp = empty('bin:lamp', parent=self.group, collection=self.col, pos=(6.9, heap_height_three(6.9, 8.6, self.R) - 1.6, 8.6),
                      q=quat_euler(0, 0, 0.16))
        g = GB()
        g.add(cylinder_geo(0.09, 0.13, 8.2, 12), compose((0, 4.1, 0)))
        g.add(cylinder_geo(0.06, 0.06, 1.9, 8), compose((-0.85, 8.05, 0), quat_euler(0, 0, math.pi / 2 - 0.25)))
        g.add(box_geo(0.9, 0.22, 0.42), compose((-1.75, 7.92, 0), quat_euler(0, 0, -0.25)))
        self.obj('bin:lamp_steel', g.build(), steel, parent=lamp)
        bulb_m = compose((-1.75, 7.79, 0), quat_euler(0, 0, -0.25))
        b = self.obj('bin:lamp_bulb', box_geo(0.7, 0.05, 0.3).transformed(bulb_m), bulb, parent=lamp)
        _no_shadow(b)
        lamp_m = compose((6.9, heap_height_three(6.9, 8.6, self.R) - 1.6, 8.6), quat_euler(0, 0, 0.16))
        self.bulb_pos = (lamp_m @ bulb_m)[:3, 3] + np.array([0, -0.35, 0])
        self.parts['lamp'] = lamp

    def _lights(self):
        lg = empty('bin:lights', parent=self.group, collection=self.col)
        mk = lambda nm, kind, hexc, w, **kw: light(nm, kind, lin_hex(hexc), w, parent=lg, collection=self.col, **kw)
        R, yf = self.R, self.y_fill
        L = {}
        L['birth'] = mk('bin:birth', 'SPOT', 0xdfe8ff, cd(320), pos=(2.0, H + 11, 7.5), target=(0, H + 0.4, 0.4),
                        spot_half=15 * D2R, blend=0.55, cutoff=40, radius=0.2)
        L['magenta'] = mk('bin:magenta', 'SUN', 0xff4fd8, 0.9, pos=(-14, 8, -10), target=(0, 0, 0))
        L['cyan'] = mk('bin:cyan', 'SUN', 0x29e7ff, 0.75, pos=(14, 6, -8), target=(0, 0, 0))
        L['sodium'] = mk('bin:sodium', 'POINT', 0xff8a3d, cd(55), pos=tuple(self.bulb_pos), cutoff=16, radius=0.25)
        L['rim'] = mk('bin:rim', 'SPOT', 0xbfe6ff, cd(420), pos=(-1.5, H + 6.5, -9.5), target=(0, H - 1.0, 1.0),
                      spot_half=20 * D2R, blend=0.7, cutoff=30, radius=0.2)
        L['inside'] = mk('bin:inside', 'POINT', 0xffc98a, cd(18), pos=(0, yf + 0.5, -0.3), cutoff=7, radius=0.3)
        L['fill'] = mk('bin:fill', 'SUN', 0x5a4cc0, 0.3, pos=(2, 5, 20), target=(0, 0, 0))
        L['pages'] = mk('bin:pages', 'SPOT', 0xe8ecff, cd(140), pos=(-3.0, 6.5, R + 5.0), target=(0.2, 0.8, R + 1.6),
                        spot_half=26 * D2R, blend=0.8, cutoff=14, radius=0.2)
        self.lights = L
        self.base = {k: l.data.energy for k, l in L.items()}
        self.parts['lights'] = L

    def _world(self):
        """The night over the dump (camera rays), far magenta and sodium city glow beyond the cliff; bin.js's
        hemisphere light (sky 0x1a2742, ground 0x030306, 0.12) for every other ray."""
        w = bpy.data.worlds.new('bin:world')
        w.use_nodes = True
        nt = w.node_tree
        nt.nodes.clear()
        nb = NB(nt)
        tc = nb.node('ShaderNodeTexCoord')
        dB = nb.normalize(V(nb, tc.outputs['Generated'], True))
        d = nb.three(dB)
        glow = nb.smoothstep(0.35, -0.05, d.y) * nb.smoothstep(0.2, -0.9, d.z)
        c0 = nb.mix((0.010, 0.012, 0.03), (0.002, 0.002, 0.006), nb.smoothstep(0.0, 0.6, d.y))
        sky = c0 + nb.mix((0.16, 0.035, 0.12), (0.22, 0.09, 0.03), nb.smoothstep(-0.3, 0.3, d.x)) * (glow * 0.6)
        hemi = nb.mix(lin_hex(0x030306), lin_hex(0x1a2742), nb.step(0.0, dB.z)) * (0.12 / math.pi)
        lp = nb.node('ShaderNodeLightPath')
        col = nb.mix(hemi, sky, V(nb, lp.outputs['Is Camera Ray'], False))
        bg = nb.node('ShaderNodeBackground')
        nb.links.new(col.out, bg.inputs['Color'])
        o = nb.node('ShaderNodeOutputWorld')
        nb.links.new(bg.outputs[0], o.inputs['Surface'])
        self.world = w
        self.parts['sky'] = w

    # ------------------------------------------------------------------------------------------- per frame
    def update(self, t, state=None, frame=None):
        """bin.js update(t, {climb, glow, wind, hush}), KEYED at frame (None: set only). climb 0..1 walks the mark up
        the paper slope inside the can (0 low inside, ~0.5 head and shoulders over the rim, 0.95..1 on the front lip);
        glow scales the warm light inside the can; wind 0..1 drifts the falling paper (it holds its last value, as in
        bin.js); hush 0..1 turns the neon rims, the rim spot and the lamp down."""
        state = dict(state or {})
        self.U['time'] = t
        c = clamp01(state.get('climb', 0) or 0)
        z = lerp(self.Z_IN, self.Z_OUT, smooth(0, 1, c))
        self.mark.location = to_blender((0, self._fill_y3(0, z) + 0.03, z))
        self.mark.rotation_mode = 'QUATERNION'
        self.mark.rotation_quaternion = (1, 0, 0, 0)
        if state.get('wind') is not None:
            self.U['wind'] = float(state['wind'])
        hush = clamp01(state.get('hush', 0) or 0)
        glow = state.get('glow', 1) if state.get('glow') is not None else 1
        self.U['glow'], self.U['hush'] = glow, hush
        if self.opts['lights']:
            L, base = self.lights, self.base
            L['inside'].data.energy = base['inside'] * glow * (0.85 + 0.15 * math.sin(t * 7.1) * math.sin(t * 3.3))
            for k in ('magenta', 'cyan', 'sodium', 'rim'):
                L[k].data.energy = base[k] * (1 - 0.6 * hush)
        for ob, mname, ident, uname in self.gn_inputs:
            getattr(ob.modifiers[mname].properties.inputs, ident).value = float(self.U[uname])
        if frame is None:
            return
        k = self.key
        k(self.mark, 'location', frame)
        if self.opts['lights']:
            for nm in ('inside', 'magenta', 'cyan', 'sodium', 'rim'):
                k(self.lights[nm].data, 'energy', frame)
        for ob, mname, ident, uname in self.gn_inputs:
            k(getattr(ob.modifiers[mname].properties.inputs, ident), 'value', frame)

    def focal_point(self):
        """The world position of the lip where the performer rises (the look's focal point; bin.js focalPoint)."""
        return self.group.matrix_world @ self.focal.matrix_basis.translation

    def key_camera(self, cam, name, frame=None, push=0.0, u=0.0, orbit=0.0):
        """Put a Blender camera on one of the cams (binWide, climb, paperClose, topDown) and key it, with an optional
        move through a shot at u 0..1: push metres along the view by smooth(u), orbit radians about the vertical
        through the target by (u - 0.5)."""
        c = self.cams[name]
        pos, tgt = Vector(c['pos']), Vector(c['target'])
        dr = (tgt - pos).normalized()
        if push:
            pos = pos + dr * (push * smooth(0, 1, u))
        if orbit:
            rr = pos - tgt
            rr.rotate(Matrix.Rotation(orbit * (u - 0.5), 3, 'Z'))
            pos = tgt + rr
        from ...look.camera import look_matrix
        cam.rotation_mode = 'QUATERNION'
        cam.matrix_world = self.group.matrix_world @ look_matrix(pos, tgt, Vector((0.0, 0.0, 1.0)))
        cam.data.sensor_fit = 'VERTICAL'
        cam.data.sensor_height = 24.0
        cam.data.lens = 12.0 / math.tan(math.radians(c['fov']) / 2)
        cam.data.clip_start, cam.data.clip_end = 0.05, 1000.0
        if frame is not None:
            self.key(cam, 'location', frame)
            self.key(cam, 'rotation_quaternion', frame)
            self.key(cam.data, 'lens', frame)

    def finish(self):
        """Give every key the set made its interpolation (LINEAR)."""
        return self.key.finish()

    # ------------------------------------------------------------------------------------------- whole sections
    def animate(self, frames=None, t0=0.0, fps=None, state_fn=None):
        """Key update() over frames (t = t0 at frames[0], your clock): state_fn(t) gives the state ({climb, glow,
        wind, hush}); without it the set idles (the paper falls, the light inside the can flickers, the mark low
        inside). Returns the keys made LINEAR."""
        sc = self.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames or (sc.frame_start, sc.frame_end)
        for f in range(f0, f1 + 1):
            t = t0 + (f - f0) / fps
            self.update(t, state_fn(t) if state_fn else {}, frame=f)
        return self.finish()

    def make_cameras(self, shots, frames=None, t0=0.0, fps=None, scene=None):
        """Your cut as cameras: shots = [(t_start, cam, {push, orbit}), ...] on the same clock as t0 (cam one of
        binWide, climb, paperClose, topDown; push metres along the view and orbit radians, eased through the shot).
        One camera per shot that falls in the frames, keyed every frame with its move, bound to timeline markers at
        the cuts (a shot naming another camera ends the one before it and makes none). Returns {(first frame, cam):
        camera}."""
        from ...look.camera import add_shot
        sc = scene or self.scene
        fps = fps or sc.render.fps / sc.render.fps_base
        f0, f1 = frames or (sc.frame_start, sc.frame_end)
        shots = [(s[0], s[1], s[2] if len(s) > 2 else {}) for s in sorted(shots, key=lambda s: s[0])]
        cams = {}
        col = bpy.data.collections.get('bin:cameras') or make_collection('bin:cameras', self.col)
        for i, (s0, name, mv) in enumerate(shots):
            s1 = shots[i + 1][0] if i + 1 < len(shots) else s0 + 6.0
            fr = [f for f in range(f0, f1 + 1) if s0 <= t0 + (f - f0) / fps < s1]
            if not fr or name not in self.cams:
                continue
            cam = bpy.data.objects.new(f'bin:cam_{name}_{fr[0]}', bpy.data.cameras.new(f'bin:cam_{name}_{fr[0]}'))
            col.objects.link(cam)
            for f in fr:
                t = t0 + (f - f0) / fps
                self.key_camera(cam, name, frame=f, push=mv.get('push', 0.0), orbit=mv.get('orbit', 0.0),
                                u=(t - s0) / (s1 - s0))
            add_shot(sc, f'bin_{name}_{fr[0]}', fr[0], cam)
            cams[(fr[0], name)] = cam
        self.finish()
        self.cameras = cams
        return cams

    def __getitem__(self, k):
        return getattr(self, k)

    def get(self, k, default=None):
        return getattr(self, k, default)

    def keys(self):
        return ['group', 'parts', 'update', 'dispose', 'cams', 'focal_point']

    def apply_render_settings(self, scene=None, fog=True, world=True, bloom=False):
        """AgX, EEVEE ray tracing and global illumination (fast GI), the set's world, and its suggested fog (parts.fog:
        0x070a14, density 0.03). bin.js asks for no bloom of its own; bloom=True adds a soft one (strength 0.45,
        radius 0.5, threshold 0.8: the bloom the music video ran all its sets under)."""
        scene = scene or self.scene
        scene.render.engine = 'BLENDER_EEVEE'
        scene.view_settings.view_transform = 'AgX'
        scene.eevee.use_raytracing = True
        scene.eevee.use_fast_gi = True
        scene.eevee.fast_gi_method = 'GLOBAL_ILLUMINATION'
        if world and self.opts['sky']:
            scene.world = self.world
        done = ['AgX', 'ray tracing', 'fast GI']
        if bloom:                                   # first: the fog splices in after Render Layers, before the bloom
            from ...harness.settings import add_bloom
            done.append(add_bloom(scene, {'threshold': 0.8, 'size': 0.5, 'strength': 0.45}))
        if fog:
            from ...sky.fog import setup_fog
            c = setup_fog(scene, density=0.03, kind='exp2')
            c.outputs[0].default_value = lin_hex(0x070a14) + (1.0,)
            done.append('fog')
        return done

    def dispose(self):
        """bin.js dispose: remove everything the set made (its objects and their meshes, lights and cameras, its
        materials and the images they read, the can's imported maps included, its node groups, its world and its
        collections)."""
        _dispose_set(self.col, set(self.mats.values()), 'bin:', self.world if self.opts['sky'] else None)


def build(ctx=None, **opts):
    """bin.js build(THREE, opts) -> Bin. ctx: the harness ctx (its scene and ctx.key keyer), a scene, or None (the
    current scene). opts: sky (True), lights (True), atlas_scale (1: 4092 x 4096; 0.5 for probes), sheets (3300),
    balls (300), falling (200), keyer (instead of ctx.key), cache_dir (the page atlas's PNG cache; default a temp
    folder: regenerable)."""
    keyer = opts.pop('keyer', None)
    scene = ctx
    if ctx is not None and not isinstance(ctx, bpy.types.Scene):
        scene, keyer = getattr(ctx, 'scene', None), keyer or getattr(ctx, 'key', None)
    return Bin(scene, keyer=keyer, **opts)


def _jr(x):
    return int(math.floor(x + 0.5))
